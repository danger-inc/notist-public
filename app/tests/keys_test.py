#!/usr/bin/env python3
# Tastentest (Plan Schritt 14): jede Aktion mit Kürzel hat am Mac ein gültiges Kürzel (Cmd statt Strg), keine Doppelbelegung,
# keine Kollision mit System-Kürzeln, Menüleiste verweist nur auf vorhandene Aktionen, Anzeige mit ⌘⌥⇧.
#   python tests/keys_test.py     (täuscht den Mac vor; braucht einen Bildschirm, startet notist mit Testdaten)
import os, sys, tempfile
T = tempfile.mkdtemp(prefix="notist-keys-")
os.environ.update(PLAT_FAKE="mac", NOTES_HOME=T, NOTES_DATA_DIR=os.path.join(T, "data"), NOTES_APP_ID="de.test.NotistKeys",
                  NOTES_NO_TIMERS="1", NOTES_NO_HANDY="1", XDG_CACHE_HOME=os.path.join(T, "cache"),
                  XDG_CONFIG_HOME=os.path.join(T, "config"))
APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, APP)
import gi  # noqa: E402
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk, Gio, GLib  # noqa: E402
import notes, i18n  # noqa: E402
from core import plat  # noqa: E402

# macOS-eigene Kürzel, die notist nie belegen darf (GTK-Schreibweise)
SYSTEM = {"<Meta>h", "<Meta>m", "<Meta>space", "<Meta>Tab", "<Meta>grave", "<Meta><Shift>3", "<Meta><Shift>4", "<Meta><Shift>5",
          "<Meta><Alt>Escape", "<Meta><Alt>h", "<Meta><Alt>d", "<Control><Meta>q"}
FAIL = []


def check(ok, msg):
    print(("ok   " if ok else "FAIL ") + msg)
    if not ok:
        FAIL.append(msg)


def lauf(app):
    acts = [a for a in app.list_action_descriptions()] if hasattr(app, "list_action_descriptions") else []
    names = list(acts)
    seen = {}
    n = 0
    for name in names:
        accs = app.get_accels_for_action(name)
        for a in accs:
            n += 1
            check("<Control>" not in a or "Tab" in a or a == "<Control><Meta>f", f"{name}: {a} ohne Strg (außer Strg+Tab, Ctrl+Cmd+F)")
            check(a not in SYSTEM, f"{name}: {a} kollidiert nicht mit macOS")
            check(not (a.startswith("<Alt>") and a[-1:].isdigit()), f"{name}: {a} keine Alt+Ziffer (Alt = Sonderzeichen am Mac)")
            if a in seen and seen[a] != name:
                check(False, f"Doppelbelegung {a}: {seen[a]} und {name}")
            seen[a] = name
    check(n >= 25, f"{n} Kürzel gesetzt (≥ 25)")
    for want, key in (("win.new", "<Meta>n"), ("win.find", "<Meta>f"), ("win.settings", "<Meta>comma"),
                      ("win.mode-notes", "<Meta>1"), ("win.mode-latex", "<Meta>3"), ("app.quit", "<Meta>q"),
                      ("win.back-home", "<Meta>w")):
        check(key in app.get_accels_for_action(want), f"{want} = {key} (ist: {app.get_accels_for_action(want)})")
    check(app.get_accels_for_action("win.close") == [], "win.close ohne Kürzel (Cmd+Q beendet über app.quit)")
    # Menüleiste: jeder Verweis zeigt auf eine echte Aktion
    mb = app.get_menubar()
    check(mb is not None and mb.get_n_items() >= 4, "Menüleiste gesetzt")
    seen_act = set()

    def walk(m):
        for i in range(m.get_n_items()):
            act = m.get_item_attribute_value(i, "action", None)
            if act:
                seen_act.add(act.get_string())
            for link in ("submenu", "section"):
                sub = m.get_item_link(i, link)
                if sub:
                    walk(sub)
    walk(mb)
    for a in sorted(seen_act):
        scope, _, nm = a.partition(".")
        have = app.win.lookup_action(nm) if scope == "win" else app.lookup_action(nm)
        check(have is not None, f"Menü → {a} existiert")
    # Anzeige
    for src, want in (("Fett (Strg+B)", "Fett (⌘B)"), ("In allen suchen (Strg+Umschalt+F)", "In allen suchen (⇧⌘F)"),
                      ("Alt+1 / 2 / 3", "⌘1 / 2 / 3"), ("Strg+Alt+M", "⌥⌘M")):
        check(i18n.tr(src) == want, f"Anzeige {src!r} → {i18n.tr(src)!r}")
    check(plat.primary_mask() == Gdk.ModifierType.META_MASK, "Tastenabfragen nutzen Cmd (META_MASK)")


def main():
    app = notes.Notes()

    def go(a):
        def tick():
            try:
                lauf(a)
            except Exception as e:  # noqa: BLE001
                import traceback; traceback.print_exc()
                check(False, f"Ausnahme: {e}")
            a.quit()
            return False
        GLib.timeout_add(500, tick)
    app.connect("activate", go)
    app.run([])
    print("\nalle grün" if not FAIL else f"\n{len(FAIL)} Fehler")
    sys.exit(1 if FAIL else 0)


main()
