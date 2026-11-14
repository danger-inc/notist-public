#!/usr/bin/env python3
# Systemanbindung am Mac (Plan Schritt 15) – so weit ohne Mac prüfbar: PLAT_FAKE=mac, Fake-HOME, Stub-Programme im PATH
# (osascript/launchctl/open/terminal-notifier schreiben nur ihre Argumente in eine Datei). Was nur ein Mac klären kann,
# steht in PLAN-mac-android.md (Fundliste [15]).
#   python tests/mac_sys_test.py
import json, os, plistlib, stat, sys, tempfile, threading, time
T = tempfile.mkdtemp(prefix="notist-macsys-")
HOME = os.path.join(T, "home"); STUB = os.path.join(T, "stub"); LOG = os.path.join(T, "calls.log")
os.makedirs(HOME); os.makedirs(STUB)
os.environ.update(PLAT_FAKE="mac", HOME=HOME, PATH=STUB + os.pathsep + os.environ["PATH"], NOTES_HOME=os.path.join(T, "n"),
                  NOTES_CACHE_DIR=os.path.join(T, "c"))
os.environ.pop("NOTES_NO_TIMERS", None)
def stub(prog):
    f = os.path.join(STUB, prog)
    with open(f, "w") as fh:
        fh.write(f'#!/bin/sh\nprintf "%s\\n" "{prog} $*" >> "{LOG}"\n')
    os.chmod(f, 0o755)


for _p in ("osascript", "launchctl", "open"):
    stub(_p)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import plat  # noqa: E402

FAIL = []


def check(ok, msg):
    print(("ok   " if ok else "FAIL ") + msg)
    if not ok:
        FAIL.append(msg)


def calls():
    time.sleep(0.4)
    return open(LOG).read() if os.path.exists(LOG) else ""


def reset():
    if os.path.exists(LOG):
        os.remove(LOG)


# Öffnen / Anzeigen / Mail
check(plat.open_cmd("/a b.pdf") == ["open", "/a b.pdf"], "Öffnen = open")
check(plat.reveal_cmd("/a.pdf") == ["open", "-R", "/a.pdf"], "Im Finder zeigen = open -R")
plat.open_external("/tmp/x.txt")
check("open /tmp/x.txt" in calls(), "open_external startet `open`")
reset()
cmd = plat.mail_cmds('/p/"q".pdf', 'Betreff "x"')[0]
check(cmd[0] == "osascript" and 'content of m' in cmd[2] and '\\"q\\"' in cmd[2] and 'Betreff \\"x\\"' in cmd[2],
      "Mail: AppleScript mit Anhang an content of m, Anführungszeichen maskiert")

# Papierkorb: trash über Finder, untrash aus ~/.Trash
ok = plat.trash("/x/y.txt")
check(ok and "osascript" in calls() and 'delete POSIX file "/x/y.txt"' in calls(), "Papierkorb über Finder-AppleScript")
reset()
os.makedirs(os.path.join(HOME, ".Trash"))
tr = os.path.join(HOME, ".Trash", "z.txt"); open(tr, "w").write("hi")
dest = os.path.join(T, "back", "z.txt"); os.makedirs(os.path.dirname(dest))
check(plat.untrash(os.path.join(T, "back", "z.txt")) is True and os.path.exists(dest) and not os.path.exists(tr),
      "Wiederherstellen aus ~/.Trash (gleicher Dateiname)")

# Meldungen
c = plat.notify_cmd("Titel", "Text")
check(c[0] == "osascript" and "display notification" in c[2], "ohne terminal-notifier: osascript-Meldung")
stub("terminal-notifier")
c = plat.notify_cmd("Titel", "Text", "n123")
check(c[0].endswith("terminal-notifier") and "-execute" in c and "--note n123" in c[c.index("-execute") + 1],
      "mit terminal-notifier: Klick ruft `notist --note <id>`")
check(plat.notify("T", "B", "n1") and "terminal-notifier" in calls(), "notify() startet terminal-notifier")
reset()

# Erinnerungs-Timer (launchd)
import datetime  # noqa: E402
when = datetime.datetime.now() + datetime.timedelta(hours=2)
check(plat.schedule("abc123", when, ["/x/notist", "--remind", "abc123"]), "schedule() meldet Erfolg")
pl = os.path.join(HOME, "Library", "LaunchAgents", "de.notist.notes-erinnerung-abc123.plist")
check(os.path.exists(pl) and plistlib.load(open(pl, "rb"))["ProgramArguments"] == ["/x/notist", "--remind", "abc123"],
      "Plist mit Befehl angelegt")
check("launchctl bootstrap gui/" in calls(), "launchctl bootstrap aufgerufen")
plat.cancel("abc123")
check(not os.path.exists(pl), "Timer-Plist beim Abbrechen entfernt")
reset()

# Autostart
check(plat.can_autostart() and not plat.autostart_enabled(), "Autostart: aus am Anfang")
check(plat.set_autostart(True) and plat.autostart_enabled(), "Autostart an")
d = plistlib.load(open(plat.autostart_plist_path(), "rb"))
check(d["RunAtLoad"] is True and d["ProgramArguments"][-1] == "--daemon" and d["Label"] == "de.notist.daemon",
      "LaunchAgent: --daemon, RunAtLoad")
check(plat.set_autostart(False) and not plat.autostart_enabled(), "Autostart aus")
reset()

# Firewall
check("ufw" not in plat.firewall_hint(37527) and "macOS" in plat.firewall_hint(37527), "Firewall-Hinweis ohne ufw")

# Einzelinstanz: zweiter Start schickt Dateien an die laufende Instanz (Finder „Öffnen mit“ bei laufendem notist)
got = []
ev = threading.Event()
srv = plat.serve_instance(lambda argv: (got.append(argv), ev.set()))
check(plat.forward_to_running(["/tmp/a.docx", "--note", "x"]) and ev.wait(3) and got[0] == ["/tmp/a.docx", "--note", "x"],
      "Weiterleitung an laufende Instanz (Socket)")
check(len(plat.instance_endpoint()[1]) < 100, "Socket-Pfad kürzer als das macOS-Limit (104)")
srv.close()
os.remove(plat.instance_endpoint()[1])
check(plat.forward_to_running(["x"]) is False, "ohne Instanz: False (dieser Start läuft selbst)")

print("\nalle grün" if not FAIL else f"\n{len(FAIL)} Fehler")
sys.exit(1 if FAIL else 0)
