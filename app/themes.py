# Farbschemata: liegen seit v5.1 in istheme.py (gemeinsam mit allen -ist-Apps, Auswahl in ~/.config/ist-theme.json).
# Dieses Modul bleibt als Name für die alten Aufrufe.
from istheme import DEFAULT, THEMES, css, exists, is_light, load, picker, save, watch  # noqa: F401
from istheme import resolve as _resolve
from core import plat

FOLLOW_SYSTEM = False      # Mac: hell/dunkel wie das System (notes.py setzt es aus den Einstellungen)


def resolve(state=None):
    """Wie istheme.resolve, aber mit FOLLOW_SYSTEM bestimmt das System, ob hell oder dunkel (Design „auto“ und feste Designs
    behalten ihre Farben; nur der Modus von „auto“ und die GTK-Grundfarben folgen)."""
    if FOLLOW_SYSTEM:
        light = plat.system_is_light()
        if light is not None:
            st = dict(state or load())
            st["mode"] = "light" if light else "dark"
            if st.get("theme") in THEMES:           # festes Design: nur wählen, wenn es zum System passt, sonst passendes Standarddesign
                if is_light(st["theme"]) != light:
                    st["theme"] = "papier" if light else DEFAULT
            return _resolve(st)
    return _resolve(state)
