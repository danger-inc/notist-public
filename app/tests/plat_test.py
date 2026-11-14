#!/usr/bin/env python3
"""Plattform-Schicht ohne Mac prüfen: PLAT_FAKE=mac|win|linux python tests/plat_test.py  (ohne Aufruf = alle drei).
Prüft Pfade und Befehlszeilen (nichts Systemspezifisches wird ausgeführt) sowie die Einzelinstanz per Socket."""
import datetime, os, plistlib, subprocess, sys, tempfile, time

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.dirname(HERE)


def check(sysname):
    sys.path.insert(0, APP)
    tmp = tempfile.mkdtemp()
    os.environ.pop("NOTES_HOME", None)
    os.environ["NOTES_CACHE_DIR"] = tmp
    from core import plat
    assert plat.SYSTEM == sysname, plat.SYSTEM
    home = os.path.expanduser("~")
    ok = lambda name: print(f"ok    [{sysname}] {name}")  # noqa: E731

    # Ordner
    dh = plat.data_home()
    if sysname == "mac":
        assert dh == home + "/Library/Application Support/notist", dh
        assert plat.docs_dir() == home + "/Documents"
    else:
        assert dh == home + "/.local/share/notes", dh
    os.environ["NOTES_HOME"] = "/tmp/x"
    assert plat.data_home() == "/tmp/x"               # NOTES_HOME gewinnt
    os.environ.pop("NOTES_HOME")
    if sysname == "mac":
        os.environ.pop("NOTES_CACHE_DIR")
        assert plat.cache_dir() == home + "/Library/Caches/notist"
        os.environ["NOTES_CACHE_DIR"] = tmp
    ok("Pfade")

    # Kürzel
    assert plat.primary_mod() == ("Meta" if sysname == "mac" else "Control")
    assert plat.accel("<Control>n") == ("<Meta>n" if sysname == "mac" else "<Control>n")
    assert plat.accel("<Control>Tab") == "<Control>Tab"
    assert plat.accel("<Alt>1") == ("<Meta>1" if sysname == "mac" else "<Alt>1")   # Schritt 14: Bereiche = Cmd+0–3
    ok("Kürzel")

    # Öffnen / Zeigen / Meldung / Mail
    oc = plat.open_cmd("/a b/c.pdf")
    assert oc == {"mac": ["open", "/a b/c.pdf"], "win": ["cmd", "/c", "start", "", "/a b/c.pdf"],
                  "linux": ["xdg-open", "/a b/c.pdf"]}[sysname], oc
    if sysname == "mac":
        assert plat.open_cmd("/x.xlsx", "Numbers") == ["open", "-a", "Numbers", "/x.xlsx"]
        assert plat.reveal_cmd("/x") == ["open", "-R", "/x"]
        n = plat.notify_cmd('Tit"el', "Text")
        assert n[0] == "osascript" and 'with title "Tit\\"el"' in n[2], n
        m = plat.mail_cmds("/p/x.notes", "Betreff")[0]
        assert m[0] == "osascript" and "POSIX file" in m[2] and "Betreff" in m[2]
    elif sysname == "win":
        assert plat.reveal_cmd("/x/y")[0] == "explorer"
        assert plat.notify_cmd("T", "B")[0] == "powershell"
        assert plat.mail_cmds("C:/p.notes", "S")[0][0] == "powershell"
    else:
        assert plat.reveal_cmd("/x") is None
        assert plat.notify_cmd("T", "B") == ["notify-send", "-a", "notist", "-i", "notist", "T", "B"]
        assert plat.mail_cmds("/p", "S")[0][:2] == ["xdg-email", "--subject"]
    ok("Befehlszeilen öffnen/zeigen/melden/mailen")

    # Timer
    when = datetime.datetime(2030, 5, 17, 9, 30)
    argv = ["/usr/bin/python3", "/app/notes.py", "--remind", "abcdef123456789"]
    sc = plat.schedule_cmds("abcdef123456789", when, argv)
    cc = plat.cancel_cmds("abcdef123456789")
    if sysname == "mac":
        label, data = plat.launchd_plist("abcdef123456789", when, argv)
        pl = plistlib.loads(data)
        assert pl["ProgramArguments"] == argv and pl["StartCalendarInterval"] == {"Month": 5, "Day": 17, "Hour": 9, "Minute": 30}
        assert label == "de.notist.notes-erinnerung-abcdef123456" and sc[0][:2] == ["launchctl", "bootstrap"]
        assert cc[0][1] == "bootout"
    elif sysname == "win":
        assert sc[0][:2] == ["schtasks", "/Create"] and "17/05/2030" in sc[0] and "09:30" in sc[0]
        assert cc[0][:2] == ["schtasks", "/Delete"]
    else:
        assert sc[0][:3] == ["systemd-run", "--user", "--unit=notes-erinnerung-abcdef123456"], sc
        assert "--on-calendar=2030-05-17 09:30:00" in sc[0] and sc[0][-4:] == argv
        assert cc[0] == ["systemctl", "--user", "stop", "notes-erinnerung-abcdef123456.timer"]
    os.environ["NOTES_NO_TIMERS"] = "1"
    assert plat.schedule("x" * 12, when, argv) is False and not plat.can_schedule()
    ok("Timer (systemd/launchd/schtasks)")

    # Tectonic
    arch, ext = plat.tectonic_asset("arm64" if sysname == "mac" else "x86_64")
    want = {"mac": ("aarch64-apple-darwin", ".tar.gz"), "win": ("x86_64-pc-windows-msvc", ".zip"),
            "linux": ("x86_64-unknown-linux-musl", ".tar.gz")}[sysname]
    assert (arch, ext) == want, (arch, ext)
    assert plat.tectonic_asset("riscv64")[0] is None
    assert plat.tectonic_exe() == ("tectonic.exe" if sysname == "win" else "tectonic")
    ok("Tectonic-Dateiname")

    # Bibliotheken, Wörterbücher, Speicher
    assert plat.load_lib(["libgibtsnicht.so.9"]) is None
    assert ("/opt/homebrew" in plat._prefixes()) == (sysname == "mac" or os.path.isdir("/opt/homebrew"))
    assert isinstance(plat.dict_dirs(), list)
    plat.release_memory(); plat.limit_arenas()
    assert (plat.libc() is None) == (sysname != "linux")
    assert plat.neighbor("gibt-es-nicht-xyz") is None
    ok("Bibliotheken/Wörterbücher/Speicher")

    # Einzelinstanz per Socket (nur dort echt, wo Unix-Sockets gehen)
    if sysname != "win" or os.name == "nt":
        got = []
        assert plat.forward_to_running(["--note", "1"]) is False           # keiner da
        srv = plat.serve_instance(got.append)
        assert plat.forward_to_running(["--note", "42", "datei.docx"]) is True
        for _ in range(50):
            if got:
                break
            time.sleep(0.05)
        srv.close()
        assert got == [["--note", "42", "datei.docx"]], got
        ok("Einzelinstanz (Weiterleitung per Socket)")


if __name__ == "__main__":
    want = os.environ.get("PLAT_FAKE")
    if want:
        check(want)
    else:
        for s in ("linux", "mac", "win"):
            r = subprocess.run([sys.executable, __file__], env={**os.environ, "PLAT_FAKE": s})
            if r.returncode:
                sys.exit(r.returncode)
        print("alle grün")
