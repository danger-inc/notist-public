# Farbschemata. "auto" = Desktop-Farben (matugen, falls vorhanden), sonst das Standard-Design.
# Jedes Design definiert dieselben Farbnamen wie matugen, damit alle CSS-Regeln unverändert funktionieren.

THEMES = {   # key: (Name, hell?, Hintergrund, Schrift, Akzent, Fläche, Zweitfarbe, Drittfarbe)
    "nacht": ("Nacht", False, "#0f1417", "#dfe3e7", "#8fcef3", "#1c2023", "#b5c9d7", "#cac1ea"),
    "glut": ("Glut", False, "#1a120d", "#f0dfd7", "#ffb68e", "#271e19", "#e7bea9", "#cdc78f"),
    "wald": ("Wald", False, "#0f1511", "#dde5dc", "#8fd6a0", "#1a221c", "#b7ccb8", "#a3cddb"),
    "rose": ("Rosé", False, "#181114", "#f0dee4", "#ffb0cd", "#241a1e", "#e0bdc8", "#f0bc95"),
    "lavendel": ("Lavendel", False, "#13121a", "#e5e1ec", "#c8bfff", "#1e1c26", "#c9c3dc", "#ecb8cd"),
    "mitternacht": ("Mitternacht", False, "#000000", "#e8e8e8", "#7cc4ff", "#121212", "#b0c4d4", "#d0b0ff"),
    "papier": ("Papier", True, "#f6f4ef", "#1d1b18", "#3a6ea5", "#ffffff", "#5d6b78", "#7b5aa6"),
    "sand": ("Sand", True, "#fbf3e8", "#2b2118", "#a85a1c", "#fffaf3", "#7a6352", "#5d7a3a"),
    "minze": ("Minze", True, "#eff6f1", "#17221b", "#2e7d4f", "#ffffff", "#4f6a5a", "#2f6f86"),
}
DEFAULT = "nacht"


def css(key):
    name, light, bg, fg, acc, surf, sec, ter = THEMES.get(key, THEMES[DEFAULT])
    outline = "#7a7a7a" if light else "#8a9297"
    lines = [f"@define-color background {bg};", f"@define-color foreground {fg};", f"@define-color cursor {fg};",
             f"@define-color primary {acc};", f"@define-color on_primary {bg};", f"@define-color secondary {sec};",
             f"@define-color tertiary {ter};", f"@define-color surface_container {surf};", f"@define-color outline {outline};",
             f"@define-color color0 {bg};", f"@define-color color1 {acc};", f"@define-color color2 {sec};",
             f"@define-color color3 {ter};", f"@define-color color7 {fg};", f"@define-color color8 {outline};",
             f"@define-color color9 {acc};", f"@define-color color10 {sec};", f"@define-color color11 {ter};",
             f"@define-color color12 {acc};", f"@define-color color15 {fg};"]
    return "\n".join(lines) + "\n"


def is_light(key):
    return THEMES.get(key, THEMES[DEFAULT])[1]
