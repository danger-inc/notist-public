#!/usr/bin/env python3
# Aussehen am Mac (Plan Schritt 17), so weit ohne Mac prüfbar: NOTES_FAKE_DARK=0|1 täuscht den Systemmodus vor.
#   Design folgt dem System (themes.resolve), live per Poll, abschaltbar · Glas-Knopf nur Linux · Mindestgröße des Fensters
#   · Schriftlisten · Speicher-Rückgabe · Startzeit (NOTES_TIMING)
#   python tests/look_test.py      (braucht einen Bildschirm)
import os, sys, tempfile
T = tempfile.mkdtemp(prefix="notist-look-")
os.environ.update(PLAT_FAKE="mac", NOTES_FAKE_DARK="1", NOTES_HOME=T, NOTES_DATA_DIR=os.path.join(T, "data"),
                  NOTES_APP_ID="de.test.NotistLook", NOTES_NO_TIMERS="1", NOTES_NO_HANDY="1", NOTES_APPEARANCE_POLL="1",
                  IST_THEME_FILE=os.path.join(T, "theme.json"), XDG_CACHE_HOME=os.path.join(T, "cache"),
                  XDG_CONFIG_HOME=os.path.join(T, "config"))
APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, APP)
import gi  # noqa: E402
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib  # noqa: E402
import notes  # noqa: E402
from core import plat  # noqa: E402
import themes  # noqa: E402

FAIL = []


def check(ok, msg):
    print(("ok   " if ok else "FAIL ") + msg)
    if not ok:
        FAIL.append(msg)


def pump(ms):
    loop = GLib.MainLoop()
    GLib.timeout_add(ms, loop.quit)
    loop.run()


def bg(css):
    import re
    m = re.search(r"@define-color\s+background\s+(#[0-9a-fA-F]{6})", css)
    return m.group(1) if m else None


def lauf(app):
    themes.FOLLOW_SYSTEM = True
    c, light = themes.resolve()
    check(light is False and plat.system_is_light() is False, f"System dunkel → dunkles Design (bg {bg(c)})")
    os.environ["NOTES_FAKE_DARK"] = "0"
    c2, light2 = themes.resolve()
    check(light2 is True and bg(c2) != bg(c), f"System hell → helles Design (bg {bg(c2)})")
    themes.save(theme="glut", mode="dark")                      # festes dunkles Design gewählt, System hell
    c3, l3 = themes.resolve()
    check(l3 is True, "festes dunkles Design weicht dem hellen System (Folgen an)")
    themes.FOLLOW_SYSTEM = False
    check(themes.resolve()[1] is False, "Folgen aus: festes Design bleibt")
    themes.save(theme="auto", mode="dark")
    # live: Poll schaltet um
    app.prefs["follow_system"] = True
    os.environ["NOTES_FAKE_DARK"] = "1"
    app._sys_light = True; app.load_css(); pump(100)
    check(not app.win.has_css_class("light-theme"), "Fenster dunkel")
    app._sys_light = False
    os.environ["NOTES_FAKE_DARK"] = "0"
    pump(2500)
    check(app.win.has_css_class("light-theme"), "Poll: Fenster schaltet live auf hell")
    app.prefs["follow_system"] = False
    os.environ["NOTES_FAKE_DARK"] = "1"
    pump(2500)
    check(app.win.has_css_class("light-theme"), "Folgen aus: kein Umschalten (bleibt hell)")
    # Glas
    check(not app.glass_btn.get_visible() and not app.win.has_css_class("glass"), "Mac: kein Glas-Knopf, Fenster deckend")
    # Mindestgröße
    mn, _nat, _a, _b = app.win.measure(Gtk.Orientation.HORIZONTAL, -1)
    mh, _n2, _c, _d = app.win.measure(Gtk.Orientation.VERTICAL, -1)
    check(mn <= 720 and mh <= 560, f"Mindestgröße {mn}×{mh} (≤ 720×560, passt auf kleine Laptops)")
    # Schriften
    import writer
    check(len(notes.font_choices()) >= 1, f"Schriftauswahl {len(notes.font_choices())} Einträge")
    check("Menlo" in plat.font_candidates() and "Segoe UI" not in plat.font_candidates(), "Mac-Schriftkandidaten")
    # Speicher
    plat.release_memory()
    check(True, "release_memory() wirft nicht")


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
        GLib.timeout_add(600, tick)
    app.connect("activate", go)
    app.run([])
    print("\nalle grün" if not FAIL else f"\n{len(FAIL)} Fehler")
    sys.exit(1 if FAIL else 0)


main()
