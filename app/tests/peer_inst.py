#!/usr/bin/env python3
# Eine echte notist-Instanz für tests/peer_test.py (Schritt 10): läuft unter Xvfb mit eigenem Zuhause/Datenordner/Port.
# Befehle kommen zeilenweise als JSON auf stdin: {"id": n, "code": "python-Text"} – der Code läuft im GTK-Hauptfaden
# mit `app`, setzt `out = …`; die Antwort geht als eine JSON-Zeile auf stdout ("R " + json).
import json, os, sys, threading, traceback

root = sys.argv[1]
os.environ.update(HOME=os.path.join(root, "home"), NOTES_HOME=root, NOTES_DATA_DIR=os.path.join(root, "data"),
                  NOTES_APP_ID="de.test.NotistPeer" + os.path.basename(root), NOTES_NO_TIMERS="1",
                  NOTIST_DATIST_HOME=os.path.join(root, "kalender"), XDG_CACHE_HOME=os.path.join(root, "cache"),
                  XDG_CONFIG_HOME=os.path.join(root, "config"), NOTES_HANDY_PORT=sys.argv[2])
os.makedirs(os.environ["HOME"], exist_ok=True)
APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, APP)
import gi  # noqa: E402
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gio, GLib  # noqa: E402
import notes  # noqa: E402
import subprocess  # noqa: E402
_P = subprocess.Popen
class _Fake(_P):
    def __init__(self, args, *a, **k):
        if os.path.basename(args[0] if isinstance(args, (list, tuple)) else str(args).split()[0]) in (
                "xdg-open", "notify-send", "systemd-run", "gio", "systemctl", "xdg-mime", "gtk-launch", "wl-copy"):
            args = ["true"]
        super().__init__(args, *a, **k)
subprocess.Popen = _Fake


def reply(i, **kw):
    sys.stdout.write("R " + json.dumps(dict(id=i, **kw), default=str) + "\n")
    sys.stdout.flush()


def main():
    app = notes.Notes()

    def run_cmd(i, code):
        env = {"app": app, "GLib": GLib, "os": os, "json": json, "out": None}
        try:
            exec(code, env)
            reply(i, ok=True, out=env["out"])
        except Exception:  # noqa: BLE001
            reply(i, ok=False, err=traceback.format_exc())
        return False

    def reader():
        for line in sys.stdin:
            try:
                c = json.loads(line)
            except ValueError:
                continue
            if c.get("code") == "quit":
                GLib.idle_add(app.quit)
                return
            GLib.idle_add(run_cmd, c["id"], c["code"])
        GLib.idle_add(app.quit)

    def go(_a):
        threading.Thread(target=reader, daemon=True).start()
        reply(0, ok=True, out="ready")
    app.connect("activate", go)
    app.run([sys.argv[0]])


main()
