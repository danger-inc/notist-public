#!/usr/bin/env python3
# Rauchtest (Plan Schritt 5): startet notist mit Testdaten, ruft jede win.-/app.-Aktion, jeden Menüeintrag und
# jeden Knopf der drei Bereiche (Notizen, Words, LaTeX) auf und sammelt Ausnahmen + GTK-CRITICAL.
#   python -X dev -W error::ResourceWarning tests/smoke.py [-v]
# Echte Daten bleiben unberührt (Temp-Ordner); Datei-/Druck-/Mail-Dialoge und Programmstarts sind abgeschaltet.
import os, sys, tempfile, traceback, re

T = tempfile.mkdtemp(prefix="notist-smoke-")
os.environ.update(NOTES_HOME=T, NOTES_DATA_DIR=os.path.join(T, "data"), NOTES_APP_ID="de.test.NotistSmoke",
                  NOTES_NO_TIMERS="1", NOTIST_DATIST_HOME=os.path.join(T, "kalender"),
                  XDG_CACHE_HOME=os.path.join(T, "cache"), XDG_CONFIG_HOME=os.path.join(T, "config"))
APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, APP)
VERBOSE = "-v" in sys.argv
FUNDE = []

import gi  # noqa: E402
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gio, GLib  # noqa: E402
import notes  # noqa: E402
import writer  # noqa: E402
import latex  # noqa: E402

# ---- Fremdwirkung abschalten ------------------------------------------------------------------------------------
for _n in ("open", "save", "select_folder", "open_multiple", "select_multiple_folders"):
    if hasattr(Gtk.FileDialog, _n):
        setattr(Gtk.FileDialog, _n, lambda self, *a, **k: None)
for _c, _n in ((Gtk.PrintOperation, "run"), (Gtk.UriLauncher, "launch"), (Gtk.FileLauncher, "launch")):
    setattr(_c, _n, lambda self, *a, **k: None)
import subprocess  # noqa: E402
_RealPopen = subprocess.Popen
class _FakePopen(_RealPopen):
    def __init__(self, args, *a, **k):
        prog = os.path.basename(args[0] if isinstance(args, (list, tuple)) else str(args).split()[0])
        if prog in ("xdg-open", "xdg-email", "notify-send", "systemd-run", "gio", "systemctl", "xdg-mime", "gtk-launch",
                    "gnumeric", "wl-copy", "wl-paste"):
            args = ["true"]
        super().__init__(args, *a, **k)
        STARTS.append((self, args, "".join(traceback.format_stack(limit=6)[:-1])))
STARTS = []
subprocess.Popen = _FakePopen
import urllib.request, urllib.error  # noqa: E402
def _kein_netz(*a, **k):
    raise urllib.error.URLError("Rauchtest: kein Netz")
urllib.request.urlopen = _kein_netz
Gio.AppInfo.launch_default_for_uri = staticmethod(lambda *a, **k: True)

# ---- Fehler einsammeln ------------------------------------------------------------------------------------------
STEP = ["start"]
def melde(art, text):
    FUNDE.append((STEP[0], art, text.strip()))
    print(f"!! [{STEP[0]}] {art}: {text.strip()[:600]}", file=sys.stderr)

def _hook(et, ev, tb):
    melde("Ausnahme", "".join(traceback.format_exception(et, ev, tb)))
sys.excepthook = _hook
_orig_log_error = notes.log_error
def _log_error(what):
    melde("log_error", what + "\n" + traceback.format_exc())
notes.log_error = _log_error

def _glib_log(domain, level, message, *_):
    melde("GTK-" + ("CRITICAL" if level & GLib.LogLevelFlags.LEVEL_CRITICAL else "WARNING"), f"{domain}: {message}")
for _d in ("Gtk", "Gdk", "GLib", "GLib-GObject", "Pango", "Gio", "GdkPixbuf"):
    GLib.log_set_handler(_d, GLib.LogLevelFlags.LEVEL_CRITICAL | GLib.LogLevelFlags.LEVEL_WARNING, _glib_log, None)
# Tests fassen sich selbst an? Warnungen, die zum Testaufbau gehören, hier ausfiltern:
IGNORIERE = re.compile(r"gdk_frame_timings|Unable to connect to the accessibility bus|Theme parser|Unknown key|Adwaita|portal|dconf", re.I)

def pump(n=6):
    ctx = GLib.MainContext.default()
    for _ in range(n):
        while ctx.iteration(False):
            pass

def tree(w):
    c = w.get_first_child()
    while c:
        yield c
        yield from tree(c)
        c = c.get_next_sibling()

def aufraeumen(app):
    """Zusatzfenster, offene Popover und Dialoge schließen, damit der nächste Schritt sauber startet."""
    for tl in list(Gtk.Window.list_toplevels()):
        if tl is not app.win and tl.get_visible() and not isinstance(tl, Gtk.Popover):
            try:
                tl.destroy() if tl.get_transient_for() is not None or True else None
            except Exception as e:  # noqa: BLE001
                melde("Ausnahme", f"destroy {tl}: {e}")
    for w in tree(app.win):
        if isinstance(w, Gtk.Popover) and w.get_visible():
            w.popdown()
    pump(2)

def probe(app, name, fn, *a):
    STEP[0] = name
    try:
        fn(*a)
    except Exception:  # noqa: BLE001
        melde("Ausnahme", traceback.format_exc())
    pump()
    aufraeumen(app)
    if VERBOSE:
        print("ok", name)

# Aktionen, die das Fenster/den Test beenden oder bewusst ohne Wirkung bleiben sollen
NICHT = {"win.close", "app.quit", "win.fullscreen"}
# Parameter für Aktionen mit Zeichenfolge
PARAM = {"win.doc-export": ["docx", "odt", "pdf", "txt", "md", "html", "rtf", "epub"],
         "win.export-as": ["zip", "md", "txt", "tex"], "win.latex-export": ["pdf", "tex"],
         "win.opt": None, "win.doc-import-path": [os.path.join(T, "gibt-es-nicht.docx")],
         "win.move-folder": ["Smoke"], "app.remind": ["x"], "app.open-note": ["x"], "app.open-settings": [""]}

def aktionen(app, wo):
    out = []
    for prefix, grp in (("win", app.win), ("app", app)):
        for nm in grp.list_actions():
            full = f"{prefix}.{nm}"
            if full in NICHT:
                continue
            act = grp.lookup_action(nm)
            vt = act.get_parameter_type()
            if vt is None:
                out.append((full, lambda g=grp, n=nm: g.activate_action(n, None)))
            else:
                werte = PARAM.get(full)
                if werte is None and full == "win.opt":
                    werte = ["spell", "wrap", "zen", "ruler", "marks", "typewriter", "lines"]
                for v in werte or [""]:
                    out.append((f"{full}::{v}", lambda g=grp, n=nm, v=v: g.activate_action(n, GLib.Variant("s", v))))
    return out

def menue_eintraege(wo):
    """FILE_MENU / LATEX_FILE_MENU: jede Aktion einmal (Namen kommen schon in aktionen() vor, hier die genauen Texte)."""
    menu = latex.LATEX_FILE_MENU if wo == "latex" else writer.FILE_MENU
    for _t, items in menu:
        for icon, label, hint, action, *_r in items:
            if callable(action):
                yield f"Menü {label}", action
            else:
                name, _, val = action.partition("::")
                yield f"Menü {label}", (lambda n=name, v=val: app_.win.activate_action(n.removeprefix("win."),
                                                                           GLib.Variant("s", v) if v else None))

def knoepfe(app):
    out, seen = [], set()
    for w in tree(app.win):
        if id(w) in seen or not w.get_mapped() or not w.get_sensitive():
            continue
        seen.add(id(w))
        if isinstance(w, Gtk.MenuButton):
            out.append((f"MenuButton {w.get_tooltip_text() or w.get_icon_name() or w.get_label()}", lambda w=w: w.popup() if w.get_mapped() else None))
        elif isinstance(w, Gtk.Button) and not isinstance(w, Gtk.MenuButton):
            nm = w.get_tooltip_text() or w.get_label() or w.get_icon_name() or w.get_name() or type(w).__name__
            out.append((f"Knopf {nm}", lambda w=w: w.emit("clicked") if w.get_mapped() else None))
        elif isinstance(w, Gtk.ToggleButton):
            out.append((f"Umschalter {w.get_tooltip_text() or w.get_label()}", lambda w=w: w.emit("clicked") if w.get_mapped() else None))
    return out

app_ = None

def lauf(app):
    global app_
    app_ = app
    pump(20)
    for kind in ("notes", "docs", "latex"):
        probe(app, f"set_kind {kind}", app.set_kind, kind)
        probe(app, f"new_note {kind}", app.new_note)
        pump(10)
        n = app.current
        if n is None:
            melde("Fund", f"{kind}: new_note erzeugt keinen Eintrag"); continue
        # etwas Text, damit Aktionen etwas zu tun haben
        try:
            if kind == "latex":
                n["text"] = "\\documentclass{article}\n\\begin{document}\nHallo Welt\n\\end{document}\n"
            else:
                n["text"] = "Hallo Welt\nZweite Zeile\n"
            app.select(n["id"])
        except Exception:  # noqa: BLE001
            melde("Ausnahme", traceback.format_exc())
        pump(10)
        for name, fn in aktionen(app, kind):
            probe(app, f"{kind}: {name}", fn)
            if app.win is None or not app.win.get_visible():
                melde("Fund", f"{name} hat das Fenster geschlossen"); return
            if app.kind != kind:                       # Aktion wechselt den Modus (mode-*): zurück
                probe(app, f"{kind}: zurück", app.set_kind, kind)
            if app.current is None or app.view != "doc" and kind != "notes":
                probe(app, f"{kind}: neu öffnen", app.new_note)
        for name, fn in menue_eintraege(kind):
            probe(app, f"{kind}: {name}", fn)
        for name, fn in knoepfe(app):
            if re.search(r"schlie|beenden|quit", name, re.I):
                continue
            probe(app, f"{kind}: {name}", fn)
            if app.win is None:
                melde("Fund", f"{name} beendete die App"); return
            if app.kind != kind:
                probe(app, f"{kind}: zurück", app.set_kind, kind)
    STEP[0] = "ende"
    pump(20)

def main():
    app = notes.Notes()
    def go(a):
        def tick():
            try:
                lauf(a)
            finally:
                a.win.get_application()   # noqa
                a.quit()
            return False
        GLib.timeout_add(500, tick)
    app.connect("activate", go)
    app.run([sys.argv[0]])
    for p, args, wo in STARTS:                  # nie abgeholte Kindprozesse (→ ResourceWarning / Zombies)
        if p.poll() is None:
            print(f"? Prozess läuft noch: {args}\n{wo}")
    schlimm = [f for f in FUNDE if not IGNORIERE.search(f[2])]
    print(f"\nsmoke: {len(schlimm)} Funde" + ("" if schlimm else " – sauber"))
    seen = set()
    for step, art, text in schlimm:
        k = (art, text.splitlines()[-1] if art == "Ausnahme" else text)
        if k in seen:
            continue
        seen.add(k)
        print(f"- [{step}] {art}: {text[-500:]}")
    sys.exit(1 if schlimm else 0)

if __name__ == "__main__":
    main()
