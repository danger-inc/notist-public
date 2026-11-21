"""Plattform-Schicht von notist: alles, was je nach System anders geht, an einer Stelle (Linux, Mac, Windows).

SYSTEM ∈ {"linux", "mac", "win"}. `PLAT_FAKE=mac|win|linux` täuscht ein anderes System vor – dann bauen die
Funktionen ihre Pfade/Befehlszeilen für dieses System (Test ohne Mac: tests/plat_test.py); ausgeführt wird dabei nichts
Systemspezifisches. GTK-frei (nur lazy, abgefangen). Umgebungsvariablen NOTES_* gewinnen immer.
"""
import ctypes
import ctypes.util
import datetime
import json
import os
import platform
import re
import shutil
import subprocess
import sys

APP = "notist"


def _system():
    fake = os.environ.get("PLAT_FAKE", "").lower()
    if fake in ("linux", "mac", "win"):
        return fake
    if sys.platform == "darwin":
        return "mac"
    if sys.platform in ("win32", "cygwin", "msys") or os.name == "nt":
        return "win"
    return "linux"


SYSTEM = _system()
FAKE = bool(os.environ.get("PLAT_FAKE"))


def _home():
    return os.path.expanduser("~")


def _which(cmd):
    return shutil.which(cmd)


def _spawn(cmd, **kw):
    """Programm lösen starten (kein Warten). True, wenn es gestartet wurde."""
    try:
        subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         **({"start_new_session": True} if os.name != "nt" else {}), **kw)
        return True
    except OSError:
        return False


def _run(cmd, timeout=15):
    try:
        return subprocess.run(cmd, capture_output=True, timeout=timeout).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


# ---------------- Ordner ----------------
def data_home():
    """Programmordner (Daten, Sicherungen, Werkzeuge). NOTES_HOME gewinnt. Linux/Windows unverändert."""
    if os.environ.get("NOTES_HOME"):
        return os.environ["NOTES_HOME"]
    if SYSTEM == "mac":
        return os.path.join(_home(), "Library", "Application Support", APP)
    return os.path.join(_home(), ".local", "share", "notes")


def cache_dir():
    if os.environ.get("NOTES_CACHE_DIR"):
        return os.environ["NOTES_CACHE_DIR"]
    if SYSTEM == "mac":
        return os.path.join(_home(), "Library", "Caches", APP)
    if SYSTEM == "win":
        return os.path.join(os.environ.get("LOCALAPPDATA") or os.path.join(_home(), "AppData", "Local"), APP, "cache")
    return os.path.join(os.environ.get("XDG_CACHE_HOME") or os.path.join(_home(), ".cache"), "notes")


def docs_dir():
    """„Dokumente“ des Nutzers (darin liegt der notist-Dateiordner)."""
    if os.environ.get("NOTES_DOCS_DIR"):         # Tests: nie in den echten Dokumente-Ordner schreiben
        return os.environ["NOTES_DOCS_DIR"]
    if SYSTEM == "linux":
        d = None
        try:
            from gi.repository import GLib
            d = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_DOCUMENTS)
        except Exception:  # noqa: BLE001
            pass
        return d or os.path.join(_home(), "Dokumente")
    return os.path.join(_home(), "Documents")


def dict_dirs():
    """Ordner mit hunspell-Wörterbüchern (.aff/.dic), vorhandene zuerst nach Vorrang."""
    dirs = [d for d in os.environ.get("DICPATH", "").split(os.pathsep) if d]
    dirs += [os.path.join(data_home(), "hunspell"),          # vom Mac-Installer geladene Wörterbücher (de/en)
             os.path.join(_home(), ".local", "share", "hunspell"), os.path.join(_home(), "Library", "Spelling")]
    dirs += [p + "/share/hunspell" for p in _prefixes()]
    dirs += ["/usr/share/hunspell", "/usr/share/myspell", "/usr/share/myspell/dicts", "/app/share/hunspell",
             "/Library/Spelling", os.path.join(sys.prefix, "share", "hunspell"),
             "/ucrt64/share/hunspell", "/mingw64/share/hunspell"]
    out = []
    for d in dirs:
        if d not in out and os.path.isdir(d):
            out.append(d)
    return out


def local_dict_files():
    """Mögliche vorhandene Ding-Wörterbuchdateien (de-en), je System."""
    return ["/usr/share/trans/de-en", "/usr/share/dict/de-en.txt", "/usr/share/ding/de-en.txt"] + \
        [p + "/share/trans/de-en" for p in _prefixes() if p != "/usr"]


def _prefixes():
    """Orte, an denen Homebrew & Co. Bibliotheken ablegen."""
    pre = ["/usr/local", "/usr"]
    if SYSTEM == "mac" or os.path.isdir("/opt/homebrew"):
        pre = ["/opt/homebrew", "/usr/local"] + pre[1:]
    return pre


# ---------------- Programme / Bibliotheken ----------------
def load_lib(names):
    """Erste ladbare Bibliothek aus names (ctypes). Probiert nackt und in den Homebrew-Präfixen; None bei Misserfolg."""
    for name in names:
        cands = [name]
        if SYSTEM != "win":
            cands += [os.path.join(p, "lib", name) for p in _prefixes()]
        for c in cands:
            try:
                return ctypes.CDLL(c)
            except OSError:
                continue
        found = ctypes.util.find_library(name.split(".")[0].replace("lib", "", 1)) if "." in name else None
        if found:
            try:
                return ctypes.CDLL(found)
            except OSError:
                pass
    return None


def extra_bin_dirs():
    """Ordner mit Programmen, die ein Finder-/Dock-Start nicht im PATH hat (Mac: Homebrew, MacTeX, TeX Live)."""
    if SYSTEM != "mac":
        return []
    import glob
    dirs = ["/opt/homebrew/bin", "/usr/local/bin", "/Library/TeX/texbin"]
    dirs += sorted(glob.glob("/usr/local/texlive/*/bin/universal-darwin") + glob.glob("/usr/local/texlive/*/bin/*-darwin"),
                   reverse=True)
    return [d for d in dirs if os.path.isdir(d)]


def fix_path():
    """Fehlende Programmordner an PATH hängen (nur Mac; sonst nichts). → die neu ergänzten Ordner."""
    have = os.environ.get("PATH", "").split(os.pathsep)
    add = [d for d in extra_bin_dirs() if d not in have]
    if add:
        os.environ["PATH"] = os.pathsep.join(have + add)
    return add


def latex_install_hints():
    """Zeilen für „Compiler fehlt“: Paketverwaltung des Systems."""
    if SYSTEM == "mac":
        return ["brew install tectonic                 # klein, lädt Pakete selbst",
                "brew install --cask mactex-no-gui     # vollständiges TeX (groß, ≈ 4 GB)"]
    if SYSTEM == "win":
        return ["pacman -S mingw-w64-ucrt-x86_64-tectonic   # MSYS2-Terminal"]
    return ["sudo pacman -S tectonic            # Arch", "sudo apt install texlive-latex-extra latexmk   # Debian/Ubuntu",
            "sudo dnf install texlive-scheme-medium latexmk   # Fedora"]


def spreadsheet_apps():
    """Tabellenprogramme, die „Öffnen in“ nehmen kann (Mac: Programmname für `open -a`; sonst Programm im PATH)."""
    if SYSTEM == "mac":
        return [n for n in ("Numbers", "Microsoft Excel", "LibreOffice") if any(
            os.path.isdir(os.path.join(d, n + ".app")) for d in ("/Applications", os.path.join(_home(), "Applications")))]
    return [n for n in ("gnumeric", "libreoffice", "localc") if _which(n)]


def libc():
    """glibc oder None (Mac/musl/Windows haben kein malloc_trim)."""
    if SYSTEM != "linux":
        return None
    return load_lib(["libc.so.6"])


def limit_arenas():
    L = libc()
    try:
        if L:
            L.mallopt(-8, 2)           # M_ARENA_MAX
    except Exception:  # noqa: BLE001
        pass


def release_memory():
    """Freigegebenen Speicher ans System zurückgeben: glibc malloc_trim; Mac: malloc_zone_pressure_relief (libSystem)."""
    try:
        if SYSTEM == "mac" and not FAKE:
            L = ctypes.CDLL("/usr/lib/libSystem.B.dylib")
            L.malloc_zone_pressure_relief.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
            L.malloc_zone_pressure_relief(None, 0)
            return
        L = libc()
        if L:
            L.malloc_trim(0)
    except Exception:  # noqa: BLE001
        pass


def system_is_light():
    """Hell/Dunkel des Systems: True/False, None = unbekannt (dann entscheidet die App-Einstellung).
    Mac: `defaults read -g AppleInterfaceStyle` (gibt „Dark“ aus, im hellen Modus Fehler). Test: NOTES_FAKE_DARK=1|0."""
    if os.environ.get("NOTES_FAKE_DARK") in ("0", "1"):
        return os.environ["NOTES_FAKE_DARK"] == "0"
    if SYSTEM != "mac" or FAKE:
        return None
    try:
        r = subprocess.run(["defaults", "read", "-g", "AppleInterfaceStyle"], capture_output=True, text=True, timeout=3)
    except (OSError, subprocess.SubprocessError):
        return None
    return "dark" not in r.stdout.lower()


def can_follow_system():
    return SYSTEM == "mac" or os.environ.get("NOTES_FAKE_DARK") in ("0", "1")


def font_candidates():
    """Zusätzliche Schriften je System für die Schriftlisten (Auswahl nur, wenn installiert)."""
    if SYSTEM == "mac":
        return ["Helvetica Neue", "Avenir Next", "Georgia", "Times New Roman", "Arial", "Menlo", "SF Mono", "Courier New"]
    if SYSTEM == "win":
        return ["Segoe UI", "Calibri", "Cambria", "Arial", "Times New Roman", "Consolas", "Courier New"]
    return []


def primary_mod():
    """Haupt-Kürzeltaste in GTK-Schreibweise: „Control“ (Linux/Windows) oder „Meta“ (Cmd am Mac)."""
    return "Meta" if SYSTEM == "mac" else "Control"


def accel(s):
    """GTK-Tastenkürzel an das System anpassen: „<Control>n“ → am Mac „<Meta>n“. Ausnahmen (Strg+Tab) bleiben."""
    if SYSTEM != "mac" or "Tab" in s:
        return s
    s = re.sub(r"<Alt>(?=[0-3]$)", "<Control>", s)          # Alt+0–3 (Bereiche) → Cmd+0–3
    return s.replace("<Control>", "<Meta>")


_PM = None


def primary_mask():
    """Gdk.ModifierType der Haupt-Kürzeltaste: Strg (Linux/Windows) bzw. Cmd = META_MASK (Mac). Für Tastenabfragen im Code."""
    global _PM
    if _PM is None:
        import gi
        gi.require_version("Gdk", "4.0")
        from gi.repository import Gdk
        _PM = Gdk.ModifierType.META_MASK if SYSTEM == "mac" else Gdk.ModifierType.CONTROL_MASK
    return _PM


def tiling_desktop():
    """Kachel-Fenstermanager (Hyprland, Sway, …) zeichnen Rahmen selbst – dort ohne Titelleiste. Nur Linux."""
    if SYSTEM != "linux":
        return False
    env = os.environ
    if env.get("HYPRLAND_INSTANCE_SIGNATURE") or env.get("SWAYSOCK") or env.get("NIRI_SOCKET"):
        return True
    desk = env.get("XDG_CURRENT_DESKTOP", "").lower()
    return any(d in desk for d in ("hyprland", "sway", "river", "niri", "wayfire", "i3", "bspwm", "qtile"))


def neighbor(name):
    """Pfad eines Nachbarprogramms der Suite (filist, datist, linguist, scourge, scourge-pdf …) oder None → Funktion aus."""
    p = _which(name)
    if p:
        return p
    for d in (os.path.join(_home(), ".local", "bin"), "/opt/homebrew/bin", "/usr/local/bin"):
        c = os.path.join(d, name + (".exe" if SYSTEM == "win" else ""))
        if os.path.isfile(c) and os.access(c, os.X_OK):
            return c
    return None


# ---------------- Öffnen, Papierkorb, Meldungen, Mail ----------------
def open_cmd(path, app=None):
    if SYSTEM == "mac":
        return ["open", "-a", app, path] if app else ["open", path]
    if SYSTEM == "win":
        return [app, path] if app else ["cmd", "/c", "start", "", path]
    return [app, path] if app else ["xdg-open", path]


def open_external(path, app=None):
    """Datei/Ordner/Link mit dem Standardprogramm (oder dem Programm `app`, wenn es das gibt) öffnen. True, wenn gestartet.
    Linux: wie bisher über GIO (Portale, Standardprogramme), Rückfall xdg-open."""
    if app and SYSTEM != "mac" and not _which(app):      # Mac: app ist ein Programmname für `open -a`
        app = None
    if SYSTEM == "linux" and not app and not FAKE:
        try:
            from gi.repository import Gio
            uri = path if "://" in path or path.startswith("mailto:") else Gio.File.new_for_path(path).get_uri()
            Gio.AppInfo.launch_default_for_uri(uri, None)
            return True
        except Exception:  # noqa: BLE001
            pass
    if SYSTEM == "win" and not app and not FAKE and hasattr(os, "startfile"):
        try:
            os.startfile(path)  # noqa: S606
            return True
        except OSError:
            return False
    return _spawn(open_cmd(path, app))


def reveal_cmd(path):
    if SYSTEM == "mac":
        return ["open", "-R", path]
    if SYSTEM == "win":
        return ["explorer", "/select," + path.replace("/", "\\")]
    return None


def reveal(path):
    """Datei im Dateimanager markiert zeigen. Linux: über org.freedesktop.FileManager1, sonst den Ordner öffnen."""
    cmd = reveal_cmd(path)
    if cmd:
        return _spawn(cmd)
    try:
        from gi.repository import Gio, GLib
        uri = Gio.File.new_for_path(path).get_uri()
        Gio.bus_get_sync(Gio.BusType.SESSION, None).call_sync(
            "org.freedesktop.FileManager1", "/org/freedesktop/FileManager1", "org.freedesktop.FileManager1",
            "ShowItems", GLib.Variant("(ass)", ([uri], "")), None, Gio.DBusCallFlags.NONE, 3000, None)
        return True
    except Exception:  # noqa: BLE001 – kein Dateimanager mit dieser Schnittstelle
        return open_external(os.path.dirname(path))


def trash(path):
    """In den System-Papierkorb (wiederherstellbar). True bei Erfolg, sonst bleibt die Datei."""
    if SYSTEM == "linux":
        try:
            from gi.repository import Gio
            Gio.File.new_for_path(path).trash(None)
            return True
        except Exception:  # noqa: BLE001
            return False
    if SYSTEM == "mac":
        esc = path.replace("\\", "\\\\").replace('"', '\\"')
        return _run(["osascript", "-e", f'tell application "Finder" to delete POSIX file "{esc}"'], 30)
    ps = ("Add-Type -AssemblyName Microsoft.VisualBasic; "
          "$p=$args[0]; if (Test-Path -PathType Container $p) "
          "{[Microsoft.VisualBasic.FileIO.FileSystem]::DeleteDirectory($p,'OnlyErrorDialogs','SendToRecycleBin')} "
          "else {[Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile($p,'OnlyErrorDialogs','SendToRecycleBin')}")
    return _run(["powershell", "-NoProfile", "-Command", ps, path], 30)


def untrash(path):
    """Mit trash() weggeworfene Datei zurückholen. Linux: aus dem Freedesktop-Papierkorb; Mac: ~/.Trash; sonst False."""
    if SYSTEM == "linux":
        try:
            from gi.repository import Gio
            tr = Gio.File.new_for_uri("trash:///")
            it = tr.enumerate_children("standard::name,trash::orig-path,trash::deletion-date",
                                       Gio.FileQueryInfoFlags.NONE, None)
            best = None
            for info in it:
                if path in (info.get_attribute_byte_string("trash::orig-path"),
                            info.get_attribute_as_string("trash::orig-path")):
                    when = info.get_attribute_as_string("trash::deletion-date") or ""
                    if best is None or when > best[0]:
                        best = (when, info.get_name())
            if best is None:
                return False
            tr.get_child(best[1]).move(Gio.File.new_for_path(path), Gio.FileCopyFlags.NONE, None, None, None)
            return True
        except Exception:  # noqa: BLE001
            return False
    if SYSTEM == "mac":                # Finder legt die Datei mit demselben Namen in ~/.Trash ab
        cand = os.path.join(_home(), ".Trash", os.path.basename(path))
        if os.path.exists(cand):
            try:
                shutil.move(cand, path)
                return True
            except OSError:
                return False
    return False


def notify_cmd(title, body, note_id=None):
    """Befehlszeile für eine Systemmeldung. Mac: terminal-notifier (Klick öffnet den Eintrag, wenn note_id gegeben), sonst
    osascript (Klick öffnet nur die Skripteditor-/Systemanzeige – kein Rücksprung möglich)."""
    if SYSTEM == "mac":
        tn = _which("terminal-notifier") or next((p for p in ("/opt/homebrew/bin/terminal-notifier",
                                                              "/usr/local/bin/terminal-notifier") if os.path.exists(p)), None)
        if tn:
            cmd = [tn, "-title", title, "-message", body or " ", "-group", "notist"]
            if note_id:
                import shlex
                cmd += ["-execute", shlex.join([launcher(), "--note", str(note_id)])]
            return cmd
        q = lambda s: s.replace("\\", "\\\\").replace('"', '\\"')  # noqa: E731
        return ["osascript", "-e", f'display notification "{q(body)}" with title "{q(title)}"']
    if SYSTEM == "win":
        q = lambda s: s.replace("'", "''")  # noqa: E731
        ps = ("Add-Type -AssemblyName System.Windows.Forms; $n=New-Object System.Windows.Forms.NotifyIcon; "
              "$n.Icon=[System.Drawing.SystemIcons]::Information; $n.Visible=$true; "
              f"$n.ShowBalloonTip(8000,'{q(title)}','{q(body)}','Info'); Start-Sleep 9; $n.Dispose()")
        return ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps]
    return ["notify-send", "-a", APP, "-i", APP, title, body]


def notify(title, body="", note_id=None):
    """Systemmeldung. False, wenn es kein Programm dafür gibt (dann zeigt die App selbst eine an)."""
    cmd = notify_cmd(title, body, note_id)
    if not _which(cmd[0]) and not os.path.isabs(cmd[0]):
        return False
    return _spawn(cmd)


def launcher():
    """Programm, das notist startet (Mac: das Bündel notist.app, sonst Python + notes.py)."""
    b = os.path.join(_home(), "Applications", "notist.app", "Contents", "MacOS", "notist")
    if SYSTEM == "mac" and os.path.exists(b):
        return b
    return _which("notist") or os.path.join(_home(), ".local", "bin", "notist")


def mail_cmds(path, subject):
    if SYSTEM == "mac":
        q = lambda s: s.replace("\\", "\\\\").replace('"', '\\"')  # noqa: E731
        script = ('tell application "Mail"\nactivate\nset m to make new outgoing message with properties '
                  f'{{subject:"{q(subject)}", visible:true}}\ntell content of m to make new attachment with properties '
                  f'{{file name:(POSIX file "{q(path)}")}} at after the last paragraph\nend tell')
        return [["osascript", "-e", script]]
    if SYSTEM == "win":
        q = lambda s: s.replace("'", "''")  # noqa: E731
        ps = ("$o=New-Object -ComObject Outlook.Application; $m=$o.CreateItem(0); "
              f"$m.Subject='{q(subject)}'; [void]$m.Attachments.Add('{q(path)}'); $m.Display()")
        return [["powershell", "-NoProfile", "-Command", ps]]
    return [["xdg-email", "--subject", subject, "--attach", path],
            ["thunderbird", "-compose", f"subject='{subject}',attachment='file://{path}'"]]


def mail_with_attachment(path, subject):
    for cmd in mail_cmds(path, subject):
        if _which(cmd[0]) and _spawn(cmd):
            return True
    return False


# ---------------- Erinnerungs-Timer ----------------
def _unit(nid):
    return f"notes-erinnerung-{nid[:12]}"      # wie bisher (laufende systemd-Timer bleiben abbrechbar)


def can_schedule():
    """Kann das System Programme zu einer Uhrzeit starten, auch wenn notist nicht läuft?"""
    if os.environ.get("NOTES_NO_TIMERS"):
        return False
    if SYSTEM == "mac":
        return bool(_which("launchctl"))
    if SYSTEM == "win":
        return bool(_which("schtasks"))
    return bool(_which("systemd-run") and _which("systemctl")) and os.path.isdir(f"/run/user/{os.getuid()}/systemd")


def launchd_plist(nid, when, argv):
    label = "de.notist." + _unit(nid)
    import plistlib
    data = {"Label": label, "ProgramArguments": [str(a) for a in argv],
            "StartCalendarInterval": {"Month": when.month, "Day": when.day, "Hour": when.hour, "Minute": when.minute},
            "RunAtLoad": False}
    return label, plistlib.dumps(data)


def schedule_cmds(nid, when, argv):
    """Befehle (Liste von Befehlszeilen) zum Anlegen des Timers; bei Mac zusätzlich die Plist (siehe schedule())."""
    unit = _unit(nid)
    if SYSTEM == "mac":
        label, _ = launchd_plist(nid, when, argv)
        plist = os.path.join(_home(), "Library", "LaunchAgents", label + ".plist")
        return [["launchctl", "bootstrap", f"gui/{os.getuid()}", plist]]
    if SYSTEM == "win":
        tr = subprocess.list2cmdline([str(a) for a in argv])
        return [["schtasks", "/Create", "/F", "/TN", unit, "/SC", "ONCE", "/ST", f"{when:%H:%M}",
                 "/SD", f"{when:%d/%m/%Y}", "/TR", tr]]
    return [["systemd-run", "--user", f"--unit={unit}", f"--on-calendar={when:%Y-%m-%d %H:%M:%S}",
             "--timer-property=AccuracySec=1s", "--collect", *[str(a) for a in argv]]]


def cancel_cmds(nid):
    unit = _unit(nid)
    if SYSTEM == "mac":
        return [["launchctl", "bootout", f"gui/{os.getuid()}/de.notist." + unit]]
    if SYSTEM == "win":
        return [["schtasks", "/Delete", "/F", "/TN", unit]]
    return [["systemctl", "--user", "stop", unit + ".timer"], ["systemctl", "--user", "reset-failed", unit + ".service"]]


def cancel(nid):
    if not can_schedule():
        return
    for cmd in cancel_cmds(nid):
        _run(cmd, 10)
    if SYSTEM == "mac":
        try:
            os.remove(os.path.join(_home(), "Library", "LaunchAgents", "de.notist." + _unit(nid) + ".plist"))
        except OSError:
            pass


def schedule(nid, when, argv):
    """Programm argv zur Zeit `when` (naive Ortszeit) starten, einmalig. True, wenn das System übernimmt;
    False → die App prüft beim Start und per Timer im laufenden Prozess selbst."""
    if not can_schedule() or when <= datetime.datetime.now():
        return False
    cancel(nid)
    if SYSTEM == "mac":
        label, data = launchd_plist(nid, when, argv)
        d = os.path.join(_home(), "Library", "LaunchAgents")
        try:
            os.makedirs(d, exist_ok=True)
            with open(os.path.join(d, label + ".plist"), "wb") as f:
                f.write(data)
        except OSError:
            return False
    return all(_run(c, 10) for c in schedule_cmds(nid, when, argv))


# ---------------- Firewall-Hinweis, Autostart ----------------
def firewall_hint(port):
    """Satz zur Freigabe des Abgleich-Ports, je System."""
    if SYSTEM == "mac":
        return f"Beim ersten Abgleich fragt macOS, ob notist eingehende Verbindungen erlauben darf – „Erlauben“ wählen (Port {port}/tcp)."
    if SYSTEM == "win":
        return f"Windows fragt beim ersten Abgleich nach der Firewall-Freigabe – für private Netzwerke erlauben (Port {port}/tcp)."
    return f"Braucht Port {port}/tcp in der Firewall (z. B. sudo ufw allow {port}/tcp)."


AUTOSTART_LABEL = "de.notist.daemon"


def autostart_plist_path():
    return os.path.join(_home(), "Library", "LaunchAgents", AUTOSTART_LABEL + ".plist")


def can_autostart():
    """Autostart-Schalter in den Einstellungen nur am Mac (Linux: macht der Fenstermanager/Desktop, Windows: Startordner)."""
    return SYSTEM == "mac"


def autostart_enabled():
    return can_autostart() and os.path.exists(autostart_plist_path())


def set_autostart(on):
    """LaunchAgent, der `notist --daemon` bei der Anmeldung startet (Fenster erst auf Abruf, Erinnerungen laufen mit)."""
    if not can_autostart():
        return False
    path = autostart_plist_path()
    uid = os.getuid()
    if not on:
        _run(["launchctl", "bootout", f"gui/{uid}/{AUTOSTART_LABEL}"], 10)
        try:
            os.remove(path)
        except OSError:
            pass
        return True
    import plistlib
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            plistlib.dump({"Label": AUTOSTART_LABEL, "ProgramArguments": [launcher(), "--daemon"], "RunAtLoad": True,
                           "ProcessType": "Interactive"}, f)
    except OSError:
        return False
    _run(["launchctl", "bootout", f"gui/{uid}/{AUTOSTART_LABEL}"], 10)
    return True      # läuft ab der nächsten Anmeldung (sofort starten wäre unnötig: notist ist ja gerade offen)


# ---------------- Tectonic, Dateitypen ----------------
def tectonic_exe():
    return "tectonic.exe" if SYSTEM == "win" else "tectonic"


def tectonic_asset(machine=None):
    """Teil des Release-Dateinamens (Rust-Zieltripel) + Endung für dieses System, z. B. ("x86_64-unknown-linux-musl", ".tar.gz").
    (None, ext) bei nicht unterstütztem Prozessor."""
    m = (machine or platform.machine()).lower()
    if SYSTEM == "win":
        return ({"amd64": "x86_64-pc-windows-msvc", "x86_64": "x86_64-pc-windows-msvc"}.get(m), ".zip")
    if SYSTEM == "mac":
        return ({"arm64": "aarch64-apple-darwin", "aarch64": "aarch64-apple-darwin",
                 "x86_64": "x86_64-apple-darwin"}.get(m), ".tar.gz")
    return ({"x86_64": "x86_64-unknown-linux-musl", "amd64": "x86_64-unknown-linux-musl",
             "aarch64": "aarch64-unknown-linux-musl", "armv7l": "arm-unknown-linux-musleabihf"}.get(m), ".tar.gz")


def register_filetypes(linux_impl=None):
    """Dateityp „.notes“ beim System anmelden. Linux: linux_impl() (MIME-XML + Desktop-Datei, siehe notes.install_mime);
    Mac: steht in der Info.plist der .app (Schritt 12), Windows: im Installer – dort nichts zu tun. → True, wenn aufgerufen."""
    if SYSTEM == "linux" and linux_impl:
        linux_impl()
        return True
    return False


# ---------------- Nur eine Instanz (Mac/Windows) ----------------
def instance_endpoint():
    """(art, adresse): Unix-Socket im Cache-Ordner oder (Windows) lokaler TCP-Port aus einer Datei."""
    d = cache_dir()
    if SYSTEM == "win":
        return "tcp", os.path.join(d, "instance.port")
    return "unix", os.path.join(d, "instance.sock")


def forward_to_running(argv, timeout=2.0):
    """Läuft notist schon? Dann argv an die Instanz schicken. True = weitergeleitet (dieser Prozess kann enden)."""
    import socket
    kind, addr = instance_endpoint()
    try:
        if kind == "unix":
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.settimeout(timeout)
            s.connect(addr)
        else:
            with open(addr, encoding="utf-8") as f:
                port = int(f.read().strip())
            s = socket.create_connection(("127.0.0.1", port), timeout)
        with s:
            s.sendall(json.dumps({"argv": list(argv)}).encode("utf-8") + b"\n")
        return True
    except (OSError, ValueError):
        return False


def serve_instance(handler):
    """Auf Weiterleitungen anderer Starts hören: handler(argv) wird im Hintergrundfaden aufgerufen. → Server-Objekt."""
    import socket
    import threading
    kind, addr = instance_endpoint()
    os.makedirs(os.path.dirname(addr), exist_ok=True)
    if kind == "unix":
        try:
            os.remove(addr)
        except OSError:
            pass
        srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        srv.bind(addr)
    else:
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.bind(("127.0.0.1", 0))
        with open(addr, "w", encoding="utf-8") as f:
            f.write(str(srv.getsockname()[1]))
    srv.listen(4)

    def loop():
        while True:
            try:
                c, _ = srv.accept()
            except OSError:
                return
            try:
                with c:
                    c.settimeout(2)
                    buf = b""
                    while not buf.endswith(b"\n") and len(buf) < 65536:
                        chunk = c.recv(4096)
                        if not chunk:
                            break
                        buf += chunk
                handler(json.loads(buf.decode("utf-8")).get("argv") or [])
            except (OSError, ValueError):
                continue
    threading.Thread(target=loop, daemon=True).start()
    return srv
