#!/usr/bin/env python3
# notist: drei Modi (Schalter links oben). "Notizen": einfache Notizen. "Words": Textverarbeitung mit
# Seitenansicht, DOCX/DOC-Import und Export als DOCX/PDF/TXT/MD/HTML (writer.py, docfmt.py, render.py).
# "LaTeX": Quelltext-Editor mit Live-PDF, Vorschlägen und Anleitung für Einsteiger (latex.py, latexdata.py).
# Gespeichert wird automatisch. Daten: ~/.local/share/notes/data/{notes,docs,latex}/*.json (siehe store.py).
# Google-Keep-Abgleich (nur Notizen): siehe sync.py.
import datetime, json, os, re, sys, time
if os.name == "nt":   # Windows/MSYS2: Hilfsprogramme liegen neben python.exe – die Startmenü-Verknüpfung setzt kein PATH
    os.environ["PATH"] = os.path.dirname(sys.executable) + os.pathsep + os.environ.get("PATH", "")

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Pango", "1.0")
from gi.repository import Gdk, Gio, GLib, GObject, Gtk, Pango

HERE = os.path.dirname(os.path.realpath(__file__))
# Reihenfolge: eigene Module, dann (falls vorhanden) Scourge und rice-apps für den gemeinsamen Look,
# zuletzt die mitgelieferten Kopien in vendor/ – so läuft notist auch allein auf anderen Rechnern.
sys.path.insert(0, HERE)
sys.path.insert(1, os.path.expanduser("~/.local/share/scourge"))
sys.path.insert(2, os.path.expanduser("~/.local/share/rice-apps"))
sys.path.append(os.path.join(HERE, "vendor"))
import paths  # noqa: E402
import i18n  # noqa: E402


def _early_lang():
    try:
        with open(paths.PREFS) as f:
            return json.load(f).get("lang", "de")
    except (OSError, ValueError):
        return "de"


i18n.setup(os.environ.get("NOTES_LANG") or _early_lang())   # vor dem ersten Widget


ICON_FONT = os.path.join(HERE, "fonts", "notes-icons.ttf")


def load_icon_font():
    """Mitgelieferte Symbolschrift ("Notes Icons") nur für diesen Prozess laden – so erscheinen die
    Icons auch ohne (passende) Nerd Font auf dem System. Pango ≥ 1.56 kann das selbst, sonst fontconfig."""
    if not os.path.exists(ICON_FONT):
        return False
    try:
        gi.require_version("PangoCairo", "1.0")
        from gi.repository import PangoCairo
        fm = PangoCairo.FontMap.get_default()
        if hasattr(fm, "add_font_file"):
            return bool(fm.add_font_file(ICON_FONT))
    except Exception:
        pass
    try:
        import ctypes, ctypes.util
        fc = ctypes.CDLL(ctypes.util.find_library("fontconfig") or "libfontconfig.so.1")
        fc.FcConfigGetCurrent.restype = ctypes.c_void_p
        fc.FcConfigAppFontAddFile.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        return bool(fc.FcConfigAppFontAddFile(fc.FcConfigGetCurrent(), ICON_FONT.encode()))
    except Exception:
        return False


load_icon_font()
import store as st  # noqa: E402
import glass  # noqa: E402
import docfmt as df  # noqa: E402
import writer as wr  # noqa: E402
import spell  # noqa: E402
import latex as lx  # noqa: E402
lx.ld.localize(i18n.LANG)
import backup  # noqa: E402
import settings as setw  # noqa: E402
import reminders as rem  # noqa: E402
import base64  # noqa: E402
import share  # noqa: E402
import exports as xp  # noqa: E402
import chrome as ch  # noqa: E402
import swipe  # noqa: E402
import recent as rc  # noqa: E402
import linked as lk  # noqa: E402
import mdnotes as md  # noqa: E402
import linguist_link  # noqa: E402

MATUGEN_CSS = os.path.expanduser("~/.cache/matugen/colors.css")
try:  # gleicher Look wie Scourge (live, falls installiert) …
    from scourge import APP_CSS, FALLBACK_COLORS  # noqa: E402
    from editor import EDITOR_CSS  # noqa: E402
except Exception:  # … sonst die mitgelieferte Kopie
    from theme import APP_CSS, EDITOR_CSS, FALLBACK_COLORS  # noqa: E402

APP_ID = os.environ.get("NOTES_APP_ID", "de.invincible.Notist")
GLib.set_prgname(APP_ID)   # auch Nebenfenster (Einstellungen, Verlauf …) melden sich als notist beim Fenstermanager
try:
    VERSION = open(os.path.join(HERE, "VERSION")).read().strip()
except OSError:
    VERSION = "?"
ICON_DIR = os.path.expanduser("~/.local/share/icons/hicolor/scalable/apps")
SHORT_H = 600              # darunter (z. B. Viertel-Kachel): Words-Menüband eingeklappt
COMPACT_W = 960            # darunter (z. B. halber Bildschirm): Liste wandert in ein Dropdown oben
BOX_OPEN, BOX_DONE = "☐", "☑"   # Checklisten: echtes Zeichen am Zeilenanfang, damit Text/Suche/Keep es verstehen
import paths  # noqa: E402
DOCS = paths.DOCS
LATEX = paths.LATEX
KINDS = {  # Modus → (Titel, Icon, Tooltip, Einzahl, Mehrzahl)
    "notes": ("Notizen", "\U000F039A", "Notizen (Alt+1)", "Notiz", "Notizen"),
    "docs": ("Words", "\U000F022C", "Words – Textverarbeitung wie Word (Alt+2)", "Dokument", "Dokumente"),
    "latex": ("LaTeX", "\U000F04A0", "LaTeX – Quelltext mit Live-PDF (Alt+3)", "LaTeX-Dokument", "LaTeX-Dokumente"),
}
PREFS = paths.PREFS
HOME_ICON = "\U000F02DC"
TAB_NAMES = {"notes": "notizen", "docs": "words", "latex": "latex"}
EXPORTS = {"docx": ("Word-Dokument", "*.docx"), "odt": ("LibreOffice-Dokument", "*.odt"), "pdf": ("PDF", "*.pdf"),
           "txt": ("Text", "*.txt"),
           "md": ("Markdown", "*.md"), "html": ("Webseite", "*.html"), "rtf": ("Rich Text", "*.rtf"),
           "epub": ("E-Book", "*.epub"), "tex": ("LaTeX-Quelltext", "*.tex"), "zip": ("LaTeX-Projekt (ZIP)", "*.zip")}
STYLES = ("bold", "italic", "underline", "strike")
BULLET = "•"
LIST_RE = __import__("re").compile(r"^(\s*)(• |(\d+)\. )")
# Farben wie in Google Keep (Name → Farbe); "default" = keine
COLORS = {"default": None, "red": "#f28b82", "orange": "#fbbc04", "yellow": "#fff475", "green": "#ccff90",
          "teal": "#a7ffeb", "blue": "#cbf0f8", "darkblue": "#aecbfa", "purple": "#d7aefb", "pink": "#fdcfe8",
          "brown": "#e6c9a8", "gray": "#e8eaed"}
COLOR_NAMES = {"default": "Keine", "red": "Rot", "orange": "Orange", "yellow": "Gelb", "green": "Grün", "teal": "Türkis",
               "blue": "Hellblau", "darkblue": "Blau", "purple": "Lila", "pink": "Rosa", "brown": "Braun", "gray": "Grau"}
COLOR_CSS = "".join(
    f"list.notes > row.nc-{k} {{ border-left: 6px solid {c}; }}"
    f".editor.nc-{k} {{ background-image: linear-gradient(alpha({c}, 0.10), alpha({c}, 0.10)); border-color: {c}; }}"
    f"button.color-dot.nc-{k} {{ background-color: {c}; }}"
    for k, c in COLORS.items() if c)

CSS = """
window.pb-window, window.pb-window popover > contents, window.dlg { color: @foreground; }
/* Auswahllisten, Zahlenfelder und Schalter überall im selben Stil */
dropdown > button, spinbutton {
    background-color: alpha(@background, 0.55); background-image: none; border: 2px solid alpha(@color9, 0.4);
    border-radius: 11px; box-shadow: none; color: @foreground; min-height: 30px; outline: none; }
dropdown > button { padding: 0 10px; }
dropdown > button:hover, spinbutton:hover { border-color: alpha(@color9, 0.8); }
dropdown > button:checked { border-color: @color9; background-color: alpha(@color9, 0.14); color: @foreground; }
spinbutton:focus-within { border-color: @color9; }
dropdown > button arrow { color: @color9; -gtk-icon-size: 12px; margin-left: 6px; }
.glass dropdown > button, .glass spinbutton { background-color: alpha(@background, 0.3); }
dropdown popover > contents { background-color: @surface_container; background-image: none; border: 2px solid @color9;
    border-radius: 13px; padding: 6px; box-shadow: 0 8px 22px rgba(0,0,0,0.3); color: @foreground; }
dropdown popover > arrow { background-color: @surface_container; border: 2px solid @color9; }
dropdown popover listview, dropdown popover scrolledwindow { background: none; }
dropdown popover listview > row { border-radius: 8px; padding: 5px 10px; margin: 1px 0; color: @foreground; outline: none; }
dropdown popover listview > row:hover { background-color: alpha(@color9, 0.12); }
dropdown popover listview > row:selected { background-color: alpha(@color9, 0.22); color: @foreground; }
dropdown popover listview > row image { color: @color9; }
dropdown popover searchentry, dropdown popover entry { background-color: alpha(@background, 0.55); border: 2px solid alpha(@color9, 0.4);
    border-radius: 10px; box-shadow: none; margin-bottom: 6px; min-height: 28px; color: @foreground; }
dropdown popover searchentry:focus-within { border-color: @color9; }
spinbutton { padding: 0; }
spinbutton > text { padding: 0 4px 0 10px; min-width: 32px; background: none; color: @foreground; }
spinbutton > button { background: none; background-image: none; border: none; box-shadow: none; color: @color9;
    min-width: 26px; min-height: 0; padding: 0; margin: 2px; border-radius: 8px; }
spinbutton > button:hover { background-color: alpha(@color9, 0.16); }
spinbutton > button:active { background-color: @color9; color: @background; }
spinbutton > button:disabled { color: alpha(@foreground, 0.3); background: none; }
switch { background-color: alpha(@foreground, 0.16); background-image: none; border: 2px solid alpha(@color9, 0.35);
    border-radius: 14px; box-shadow: none; min-height: 22px; }
switch:checked { background-color: @color9; border-color: @color9; }
switch slider { background-color: @foreground; background-image: none; border: none; box-shadow: none; border-radius: 10px;
    min-width: 18px; min-height: 18px; margin: 2px; }
switch:checked slider { background-color: @background; }
dropdown.wt > button { min-height: 24px; padding: 0 8px; border-radius: 9px; font-size: 12px; }
spinbutton.wt { min-height: 24px; border-radius: 9px; font-size: 12px; }
spinbutton.wt > button { min-width: 20px; }
.fontrow { font-size: 13px; }
list.notes > row, .settings-side row, button.theme-card, .cmd-list row, .hist-list row { color: @foreground; }
.notes-body { margin: 6px 16px 16px 16px; }
.note-tools { background-color: alpha(@background, 0.5); border-radius: 12px; padding: 4px 6px; margin: 6px 0 10px 0; }
.glass .note-tools { background-color: alpha(@background, 0.25); }
.note-tools dropdown.wt { min-width: 120px; }
list.notes { background: none; }
list.notes > row {
    background-color: @surface_container; border: 2px solid alpha(@color9, 0.22);
    border-radius: 11px; padding: 6px 10px; margin-bottom: 6px; outline: none;
}
list.notes > row:hover { border-color: alpha(@color9, 0.6); }
list.notes > row:selected { border-color: @color9; background-color: alpha(@color9, 0.12); color: @foreground; }
.row-title { font-size: 12px; font-weight: 800; }
.row-snippet { font-size: 11px; color: alpha(@foreground, 0.55); }
.row-date { font-size: 10px; color: alpha(@foreground, 0.42); }
.pin { color: @color9; font-size: 11px; }
button.trash-link {
    background: none; box-shadow: none; border: none; border-radius: 9px; padding: 4px 8px;
    color: alpha(@foreground, 0.55); font-size: 12px; font-weight: 700;
}
button.trash-link:hover { color: @foreground; background-color: alpha(@color9, 0.12); }
.editor {
    background-color: @surface_container; border: 2px solid @color9; border-radius: 15px; padding: 14px 18px 12px 18px;
}
.editor.trash { border-style: dashed; border-color: alpha(@color9, 0.6); }
entry.note-title {
    background: none; border: none; box-shadow: none; outline: none; padding: 0;
    font-size: 20px; font-weight: 800; color: @foreground; min-height: 34px;
}
textview.note-text, textview.note-text text { background: none; color: @foreground; font-size: 14px; }
textview.note-text { caret-color: @color9; }
.sep { background-color: alpha(@color9, 0.25); min-height: 2px; margin: 6px 0 8px 0; }
.fmt button.pb { min-width: 30px; padding: 0 8px; }
.meta { font-size: 11px; color: alpha(@foreground, 0.5); }
.saved { font-size: 11px; font-weight: 800; color: @color9; }
.saving { font-size: 11px; font-weight: 800; color: alpha(@foreground, 0.55); }
.empty-title { font-size: 16px; font-weight: 800; }
/* kompakte Ansicht: Dropdown statt Seitenleiste */
menubutton.switcher > button { background-image: none; background-color: @surface_container; border: 2px solid alpha(@color9, 0.45);
    border-radius: 13px; padding: 2px 10px; min-height: 30px; box-shadow: none; color: @foreground; }
menubutton.switcher > button:hover { border-color: @color9; background-color: @surface_container; }
menubutton.switcher > button:checked { border-color: @color9; background-color: alpha(@color9, 0.14); color: @foreground; }
.glass menubutton.switcher > button:checked { background-color: alpha(@color9, 0.18); }
.switch-chev { color: @color9; font-size: 14px; }
.sheet-title { font-size: 13px; font-weight: 800; color: @color9; letter-spacing: 0.5px; }
button.sheet-btn { min-width: 30px; min-height: 28px; padding: 0; border-radius: 10px; }
.glass menubutton.switcher > button { background-color: alpha(@surface_container, 0.4); }
.switch-title { font-weight: 800; font-size: 13px; }
.switch-sub { font-size: 10px; color: alpha(@foreground, 0.55); }
popover.switch-pop > contents { background-color: @surface_container; background-image: none; border: 2px solid @color9;
    border-radius: 16px; padding: 12px; box-shadow: 0 10px 28px rgba(0,0,0,0.35); margin-top: 6px; }
.glass popover.switch-pop > contents { background-color: alpha(@surface_container, 0.88); }
popover.switch-pop list.notes > row { background-color: alpha(@background, 0.55); }
popover.switch-pop list.notes > row:selected { background-color: alpha(@color9, 0.16); }
.compact .notes-body { margin: 4px 10px 10px 10px; }
.compact .topbar { padding: 10px 10px 4px 10px; }
.compact .editor { padding: 10px 12px 10px 12px; }
.row-prog { font-size: 10px; font-weight: 800; color: @color9; }
.row-labels { font-size: 10px; color: alpha(@color9, 0.85); }
.row-kind { font-size: 11px; color: @color9; }
.list-head { font-size: 10px; font-weight: 800; letter-spacing: 1px; color: alpha(@foreground, 0.5); margin: 8px 4px 4px 4px; }
.label-chips button { background: none; background-image: none; box-shadow: none; border: 2px solid alpha(@color9, 0.25);
    border-radius: 10px; padding: 0 8px; min-height: 22px; font-size: 11px; color: alpha(@foreground, 0.75); }
.label-chips button:checked, .label-chips button.on { background-color: @color9; color: @background; border-color: @color9; }
.label-chips button:hover { border-color: @color9; color: @foreground; }
.label-chips button.on:hover { background-color: alpha(@color9, 0.75); color: @background; }
.lbl-hash { font-size: 14px; font-weight: bold; margin-right: 2px; }
.lbl-sub { font-size: 11px; margin-top: 2px; }
.label-chips flowboxchild, .label-mine flowboxchild { padding: 0; }
.find-all .find-div { min-width: 1px; min-height: 22px; background-color: alpha(@primary, 0.4); margin: 0 4px 0 2px; }
.lchip { background-color: alpha(@color9, 0.16); border: 1px solid alpha(@color9, 0.55); border-radius: 4px; }
.lchip > label { font-size: 11px; padding: 0 6px 0 8px; color: @foreground; }
.lchip > button.lchip-x { background: none; background-image: none; box-shadow: none; border: none;
    border-left: 1px solid alpha(@color9, 0.4); border-radius: 0 3px 3px 0; min-height: 22px; min-width: 0;
    padding: 0 7px; font-size: 11px; color: alpha(@foreground, 0.65); }
.lchip > button.lchip-x:hover { background-color: @tertiary; color: @background; }
button.color-dot { min-width: 26px; min-height: 26px; padding: 0; border-radius: 13px; background-image: none;
    border: 2px solid alpha(@foreground, 0.25); box-shadow: none; }
button.color-dot.nc-default { background-color: @background; }
button.color-dot.active { border-color: @foreground; box-shadow: inset 0 0 0 1px @foreground; }
button.color-dot .cd-none { color: @foreground; font-size: 15px; padding: 0; margin: 0; }
.hist-list row { border-radius: 9px; padding: 6px 10px; }
.hist-list row:selected { background-color: alpha(@color9, 0.25); color: @foreground; }
.hist-when { font-weight: 800; font-size: 12px; } .hist-info { font-size: 11px; color: alpha(@foreground, 0.6); }
.hist-preview { font-size: 12px; }
menubutton.pb.small > button { font-size: 12px; padding: 0 10px; min-height: 22px; border-radius: 11px; }
.rem-now { font-weight: 800; color: @color9; }
.row-rem { font-size: 10px; font-weight: 800; color: @color9; }
.row-rem.past { color: alpha(@foreground, 0.45); }
"""

# Kalender-/musicalist-Look für Kopfleiste, Statuszeile und Bedienelemente (nach CSS geladen → gewinnt)
TUI_CSS = """
.pb-window .tbar, .pb-window .tstatus { font-weight: bold; }
entry.tsearch, searchentry.tsearch, .pb-window searchentry {
    background-color: alpha(@background, 0.45); background-image: none; border: 1px solid alpha(@primary, 0.45);
    border-radius: 4px; color: @foreground; box-shadow: none; min-height: 24px; padding: 0 8px; outline: none; }
searchentry.tsearch:focus-within, .pb-window searchentry:focus-within { border-color: @primary; }
searchentry.tsearch > text > placeholder { color: alpha(@secondary, 0.8); }
searchentry.tsearch image { color: @primary; }
menubutton.switcher > button { background: none; background-image: none; border: none; box-shadow: none;
    border-radius: 4px; padding: 2px 8px; min-height: 0; min-width: 0; color: @primary; }
menubutton.switcher > button:hover { background-color: alpha(@primary, 0.12); color: @foreground; }
menubutton.switcher > button:checked { background-color: alpha(@primary, 0.22); color: @foreground; }
.glass menubutton.switcher > button { background-color: transparent; }
.tbar button.doctab { padding: 2px 6px 2px 9px; }
.tbar button.doctab label { font-weight: bold; }
.tbar .doctab-sep { color: alpha(@foreground, 0.25); }
button.doctab-x { background: none; background-image: none; border: none; box-shadow: none; padding: 0 3px; min-height: 0;
    min-width: 0; color: alpha(@foreground, 0.4); font-size: 11px; border-radius: 4px; }
button.doctab-x:hover { background-color: @tertiary; color: @background; }
.switch-title { font-size: 13px; } .switch-sub { font-size: 10px; color: @secondary; }
.switch-chev { color: @primary; }
popover.switch-pop > contents { border: 1px solid @primary; border-radius: 6px; padding: 10px;
    box-shadow: 0 8px 22px rgba(0,0,0,0.3); margin-top: 4px; }
.sheet-title { color: @primary; }
button.sheet-btn, button.pb.sheet-btn { min-width: 0; min-height: 0; padding: 1px 8px; border-radius: 4px; border-width: 1px; }
/* Statuszeile: kleine umrandete Knöpfe statt Pillen */
.tstatus button.pb, .tstatus togglebutton.pb, .tstatus menubutton.pb > button, .tstatus button.pb.small {
    background: none; background-image: none; box-shadow: none; border: 1px solid alpha(@primary, 0.55);
    border-radius: 4px; padding: 1px 8px; min-height: 0; font-size: 12px; color: @foreground; }
.tstatus menubutton.pb { border: none; padding: 0; background: none; }
.tstatus button.pb:hover, .tstatus menubutton.pb > button:hover, .tstatus menubutton.pb > button:checked,
.tstatus button.pb:checked:hover { background-color: @primary; color: @on_primary; border-color: @primary; }
.tstatus button.pb:checked { background-color: alpha(@primary, 0.22); border-color: @primary; color: @foreground; }
.tstatus .saved { color: @primary; font-size: 12px; } .tstatus .meta { color: @secondary; font-size: 12px; }
/* Editor-Rahmen und Liste schlanker (1 px wie die Kästen in datist/musicalist) */
.editor { border-width: 1px; border-radius: 6px; padding: 12px 16px 10px 16px; }
.editor.trash { border-style: dashed; }
/* Statusleiste: Knöpfe rücken an „übersetzer“ heran */
.tstatus .ed-bar { margin: 0; }
/* Obere Werkzeugleisten (Notizen, Words-Fließend, LaTeX) im filist-Look: flach, Trennlinie darunter, kleine umrandete Knöpfe */
.note-tools, .writer-tools, .flowbar { background: none; border-radius: 0; padding: 2px 2px 4px 2px; margin: 2px 0 8px 0;
    border-bottom: 1px dashed alpha(@primary, 0.3); }
.glass .note-tools { background: none; }
.note-tools button.wt, .note-tools menubutton.wt > button, .note-tools togglebutton.wt,
.writer-tools button.wt, .writer-tools menubutton.wt > button, .writer-tools togglebutton.wt,
.flowbar button.wt, .flowbar menubutton.wt > button, .flowbar togglebutton.wt {
    border: 1px solid transparent; border-radius: 4px; min-height: 24px; padding: 0 6px; font-size: 13px; }
.note-tools button.wt:hover, .note-tools menubutton.wt > button:hover, .writer-tools button.wt:hover,
.writer-tools menubutton.wt > button:hover, .flowbar button.wt:hover, .flowbar menubutton.wt > button:hover {
    background-color: alpha(@primary, 0.16); border-color: alpha(@primary, 0.35); }
.note-tools button.wt:checked, .note-tools menubutton.wt > button:checked, .note-tools togglebutton.wt:checked,
.writer-tools button.wt:checked, .writer-tools menubutton.wt > button:checked, .writer-tools togglebutton.wt:checked,
.flowbar button.wt:checked, .flowbar menubutton.wt > button:checked, .flowbar togglebutton.wt:checked {
    background-color: alpha(@primary, 0.24); color: @foreground; border-color: @primary; }
.note-tools .wgroup, .writer-tools .wgroup { border-right: 1px solid alpha(@primary, 0.3); margin-right: 6px; padding-right: 6px; }
.note-tools .wgroup.last, .writer-tools .wgroup.last { border-right: none; }
.note-tools dropdown.wt > button { border-radius: 4px; }
/* Notizliste wie die Dateiliste in filist: flache Zeilen, Hover/Auswahl als Akzentton, Pfadleiste darüber */
list.notes > row, list.notes > row:hover, list.notes > row:selected { border: none; border-radius: 4px; box-shadow: none; }
list.notes > row { background: none; padding: 4px 8px; margin: 0 2px 1px 2px; }
list.notes > row:hover { background-color: alpha(@primary, 0.08); }
list.notes > row:selected { background-color: alpha(@primary, 0.24); color: @foreground; }
list.notes > row:selected:hover { background-color: alpha(@primary, 0.3); }
list.notes > row:not(:selected), .glass list.notes > row:not(:selected) { background: none; }
.glass list.notes > row:not(:selected):hover { background-color: alpha(@primary, 0.08); }
popover.switch-pop list.notes > row { background: none; }
popover.switch-pop list.notes > row:selected { background-color: alpha(@primary, 0.24); }
.row-title { font-size: 13px; font-weight: bold; }
.nt-path { padding: 0 2px 4px 2px; }
.nt-crumbs { border: 1px solid alpha(@primary, 0.35); border-radius: 4px; padding: 0 4px; min-height: 24px; }
button.nt-crumb { background: none; border: none; box-shadow: none; padding: 1px 6px; min-height: 0; border-radius: 4px;
    color: alpha(@foreground, 0.75); font-weight: bold; font-size: 12px; }
button.nt-crumb:hover { background-color: alpha(@primary, 0.16); color: @foreground; }
button.nt-crumb.last { color: @primary; }
.nt-sep { color: alpha(@foreground, 0.3); }
.nt-count { color: @secondary; font-size: 11px; padding: 0 4px; }
.notes-body { margin: 4px 14px 10px 14px; }
paned.notes-body > separator { min-width: 9px; background: none; background-image: none; border: none; box-shadow: none;
    margin: 0 2px; }
paned.notes-body > separator:hover { background-image: linear-gradient(to right, transparent 4px, alpha(@primary, 0.6) 4px,
    alpha(@primary, 0.6) 5px, transparent 5px); }
.compact .notes-body { margin: 4px 10px 10px 10px; }
.compact .tbar { padding: 8px 10px 4px 10px; }
.home { margin: 4px 14px 6px 14px; }
button.trash-link { border-radius: 4px; font-size: 12px; }
/* Home: Papierkorb-Knopf je Zeile (erst beim Überfahren sichtbar) + Rechtsklick-Menü */
button.tr-del { background: none; border: none; box-shadow: none; min-height: 0; min-width: 0; padding: 1px 6px;
    border-radius: 4px; color: @tertiary; opacity: 0; font-size: 13px; }
.trow-wrap:hover button.tr-del, button.tr-del:focus-visible { opacity: 1; }
button.tr-del:hover { background-color: @tertiary; color: @background; }
popover.home-menu > contents { border: 1px solid @primary; border-radius: 6px; padding: 4px;
    background-color: alpha(@background, 0.95); }
popover.home-menu button.hm-item { background: none; border: none; box-shadow: none; border-radius: 4px;
    padding: 3px 10px; min-height: 0; color: @foreground; }
popover.home-menu button.hm-item:hover { background-color: @primary; color: @on_primary; }
popover.home-menu label.hm-head { font-size: 11px; font-weight: 800; color: @primary; padding: 2px 10px 4px 10px; }
/* Ordner in der Notizen-Seitenleiste */
list.notes > row.folder-row { border: none; background: none; padding: 3px 6px; margin: 2px 0 2px 0; }
list.notes > row.folder-row:hover { background-color: alpha(@primary, 0.1); }
list.notes > row.folder-row.drop { background-color: alpha(@primary, 0.25); }
.folder-chev { color: alpha(@foreground, 0.5); font-size: 11px; min-width: 12px; }
.folder-icon { color: @primary; font-size: 14px; }
.folder-name { font-size: 12px; font-weight: 800; }
.folder-count { font-size: 11px; color: @secondary; }
list.notes > row.in-folder { margin-left: 14px; }
button.folder-add { background: none; border: 1px solid alpha(@primary, 0.45); box-shadow: none; border-radius: 4px;
    padding: 0 7px; min-height: 0; color: @primary; font-size: 13px; }
button.folder-add:hover { background-color: @primary; color: @on_primary; }
popover.folder-pop > contents { padding: 10px 12px; }
.fp-icon { font-size: 15px; }
.fp-where { font-size: 11px; } .fp-hint { font-size: 11px; }
button.tbtn.accent-btn { background-color: alpha(@primary, 0.22); border-color: @primary; }
button.tbtn.accent-btn:hover { background-color: @primary; color: @on_primary; }
button.trow.tfolder.drop { background-color: alpha(@primary, 0.25); }
.doc-acts button.tbtn, button.tbtn.view-sw { font-size: 12px; font-weight: bold; padding: 1px 8px; }
.doc-acts togglebutton.tbtn:checked, .doc-acts button.tbtn:checked { background-color: alpha(@primary, 0.22); border-color: @primary; }
.label-chips button { border-width: 1px; border-radius: 4px; padding: 0 7px; min-height: 20px; }
button.trow .tr-tags { font-size: 11px; color: alpha(@primary, 0.85); }
popover.home-menu .fm-line { min-height: 1px; background-color: alpha(@primary, 0.3); margin: 3px 6px; }
/* übrige GTK-Kontextmenüs (Eingabefelder) im Suite-Stil */
popover.menu > contents { border: 1px solid @primary; border-radius: 6px; padding: 4px;
    background-color: alpha(@background, 0.96); background-image: none; box-shadow: 0 8px 22px rgba(0,0,0,0.3); }
popover.menu modelbutton { border-radius: 4px; padding: 3px 10px; min-height: 0; }
popover.menu modelbutton:hover, popover.menu modelbutton:selected { background-color: @primary; color: @on_primary; }
popover.menu modelbutton:disabled { color: alpha(@foreground, 0.35); }
popover.menu separator { background-color: alpha(@primary, 0.3); margin: 3px 6px; }
.empty-hint { color: @secondary; }
.tbar button.pb.glass-toggle { background: none; background-image: none; box-shadow: none; min-height: 0; min-width: 0;
    border: 1px solid alpha(@primary, 0.55); border-radius: 4px; padding: 1px 8px; color: @foreground; font-size: 13px; }
.tbar button.pb.glass-toggle:checked { background-color: alpha(@primary, 0.22); color: @foreground; }
.tbar button.pb.glass-toggle:hover { background-color: @primary; color: @on_primary; border-color: @primary; }
button.jump-pill { background-color: @primary; background-image: none; color: @on_primary; border: none; box-shadow: none;
    border-radius: 4px; padding: 2px 10px; min-height: 0; font-size: 12px; font-weight: bold; }
button.jump-pill:hover { background-color: mix(@primary, @foreground, 0.2); }
.tbar .toast { border-radius: 4px; padding: 1px 4px 1px 9px; font-size: 12px; margin-right: 6px; }
.tbar .toast button.pb.small { border: 1px solid @on_primary; border-radius: 4px; min-height: 0; padding: 0 6px;
    background: none; color: @on_primary; }
.tbar .toast button.pb.small:hover { background-color: @on_primary; color: @primary; }
/* Auswahllisten, Zahlenfelder, Schalter: schmal wie in der Suite (1 px, 4 px Rundung) */
dropdown > button, spinbutton { border-width: 1px; border-color: alpha(@primary, 0.45); border-radius: 4px;
    min-height: 24px; background-color: alpha(@background, 0.45); }
dropdown > button:hover, spinbutton:hover { border-color: @primary; }
dropdown > button:checked { border-color: @primary; background-color: alpha(@primary, 0.16); }
dropdown > button arrow { color: @primary; }
dropdown popover > contents { border-width: 1px; border-color: @primary; border-radius: 6px; padding: 4px; }
dropdown popover > arrow { border-width: 1px; }
dropdown popover listview > row { border-radius: 4px; padding: 3px 10px; }
dropdown popover searchentry, dropdown popover entry { border-width: 1px; border-radius: 4px; min-height: 24px; }
spinbutton > button { border-radius: 4px; min-width: 22px; }
switch { border-width: 1px; border-color: alpha(@primary, 0.45); border-radius: 4px; min-height: 18px;
    background-color: alpha(@foreground, 0.1); }
switch:checked { background-color: @primary; border-color: @primary; }
switch slider { border-radius: 2px; min-width: 14px; min-height: 14px; margin: 2px; }
/* Aufklappmenüs in Words/LaTeX wie das Datei-Menü: ohne Pfeil, 1 px @primary, Hover gefüllt */
dropdown popover > contents { background-color: alpha(@background, 0.96); background-image: none;
    box-shadow: 0 8px 22px rgba(0,0,0,0.3); }
.glass dropdown popover > contents { background-color: alpha(@background, 0.88); }
dropdown popover listview > row:hover { background-color: @primary; color: @on_primary; }
dropdown popover listview > row:selected { background-color: alpha(@primary, 0.22); color: @foreground; }
dropdown popover listview > row:selected:hover { background-color: @primary; color: @on_primary; }
dropdown popover listview > row image { color: @primary; }
dropdown popover listview > row:hover image { color: @on_primary; }
popover.wpop button.pb, popover.wpop flowbox.cheat button, popover.wpop button.tbtn {
    background: none; background-image: none; box-shadow: none; border: 1px solid alpha(@primary, 0.35);
    border-radius: 4px; min-height: 0; padding: 3px 10px; color: @foreground; font-size: 12px; font-weight: normal; }
popover.wpop button.wt { background: none; background-image: none; box-shadow: none; border: 1px solid transparent;
    border-radius: 4px; min-height: 0; padding: 3px 8px; color: @foreground; }
popover.wpop button.pb:hover, popover.wpop flowbox.cheat button:hover, popover.wpop button.tbtn:hover,
popover.wpop button.wt:hover { background-color: @primary; color: @on_primary; border-color: @primary; }
popover.wpop button.wt:checked { background-color: alpha(@primary, 0.22); border-color: @primary; }
popover.wpop flowbox.cheat > flowboxchild { padding: 0; }
popover.file-menu .fm-sub { margin-top: 1px; }
"""



def tiling_desktop():
    """Kachel-Fenstermanager (Hyprland, Sway, …) zeichnen Rahmen selbst – dort ohne Titelleiste.
    Auf GNOME, KDE & Co. behält das Fenster seine normale Titelleiste (Schließen, Verschieben)."""
    env = os.environ
    if env.get("HYPRLAND_INSTANCE_SIGNATURE") or env.get("SWAYSOCK") or env.get("NIRI_SOCKET"):
        return True
    desk = env.get("XDG_CURRENT_DESKTOP", "").lower()
    return any(d in desk for d in ("hyprland", "sway", "river", "niri", "wayfire", "i3", "bspwm", "qtile"))


def install_logo():
    """App-Symbol aus logo/ ins Benutzer-Iconverzeichnis kopieren, falls es dort fehlt oder alt ist."""
    if any(os.path.isfile(os.path.expanduser(f"~/.config/ist-icons/notist{e}")) for e in (".svg", ".png")):
        return              # eigenes Icon (in scourge hinterlegt) nicht überschreiben
    src = os.path.join(HERE, "logo", "notist.svg")
    dst = os.path.join(ICON_DIR, "notist.svg")
    try:
        data = open(src, "rb").read()
        if not os.path.isfile(dst) or open(dst, "rb").read() != data:
            os.makedirs(ICON_DIR, exist_ok=True)
            with open(dst, "wb") as f:
                f.write(data)
    except OSError:
        pass


MIME = "application/x-notes-share"
MIME_XML = f"""<?xml version="1.0" encoding="UTF-8"?>
<mime-info xmlns="http://www.freedesktop.org/standards/shared-mime-info">
  <mime-type type="{MIME}">
    <comment>notist-Datei</comment>
    <comment xml:lang="en">notist file</comment>
    <icon name="application-x-notes-share"/>
    <glob pattern="*.notes" weight="80"/>
  </mime-type>
</mime-info>
"""


def install_mime():
    """.notes-Dateien als eigenen Dateityp anmelden: Doppelklick im Dateimanager öffnet notist (im Hintergrund)."""
    import shutil, subprocess, threading

    def run():
        share = os.path.expanduser("~/.local/share")
        changed = False
        xml = os.path.join(share, "mime", "packages", "notes-share.xml")
        try:
            if not os.path.isfile(xml) or open(xml).read() != MIME_XML:
                os.makedirs(os.path.dirname(xml), exist_ok=True)
                with open(xml, "w") as f:
                    f.write(MIME_XML)
                changed = True
            icon = os.path.join(share, "icons", "hicolor", "scalable", "mimetypes", "application-x-notes-share.svg")
            src = os.path.join(HERE, "logo", "notist.svg")
            if os.path.isfile(src) and not os.path.isfile(icon):
                os.makedirs(os.path.dirname(icon), exist_ok=True)
                shutil.copyfile(src, icon)
            desk = os.path.join(share, "applications", "notist.desktop")
            if os.path.isfile(desk):
                lines = open(desk).read().split("\n")
                out, has = [], False
                for l in lines:
                    if l.startswith("MimeType="):
                        has = True
                        if MIME not in l:
                            l = l.rstrip(";") + ";" + MIME + ";"
                            changed = True
                    out.append(l)
                if not has:
                    out.insert(next((i + 1 for i, l in enumerate(out) if l.startswith("Exec=")), len(out)), f"MimeType={MIME};")
                    changed = True
                if changed:
                    with open(desk, "w") as f:
                        f.write("\n".join(out))
            if changed:
                for cmd in (["update-mime-database", os.path.join(share, "mime")],
                            ["update-desktop-database", os.path.join(share, "applications")],
                            ["xdg-mime", "default", "notist.desktop", MIME]):
                    if shutil.which(cmd[0]):
                        subprocess.run(cmd, capture_output=True, timeout=30)
        except (OSError, subprocess.SubprocessError):
            pass
    threading.Thread(target=run, daemon=True).start()


def nice_date(iso):
    d = datetime.datetime.fromisoformat(iso).astimezone()
    now = datetime.datetime.now().astimezone()
    sec = (now - d).total_seconds()
    if sec < 60:
        return "gerade eben"
    if sec < 3600:
        return f"vor {int(sec // 60)} Min"
    if d.date() == now.date():
        return f"heute {d:%H:%M}"
    if (now.date() - d.date()).days == 1:
        return f"gestern {d:%H:%M}"
    return f"{d:%d.%m.%Y}"


ERROR_LOG = os.path.join(os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache"), "notes", "fehler.log")


def log_error(what):
    """Fehler mit Traceback nach ~/.cache/notes/fehler.log (und stderr) – für Fehler, die die App nicht
    anhalten dürfen. Die Datei bleibt klein (ältere Hälfte fliegt bei > 200 KB)."""
    import traceback
    text = f"--- {datetime.datetime.now():%Y-%m-%d %H:%M:%S} {what} (notist {VERSION})\n{traceback.format_exc()}"
    print(text, file=sys.stderr)
    try:
        os.makedirs(os.path.dirname(ERROR_LOG), exist_ok=True)
        if os.path.exists(ERROR_LOG) and os.path.getsize(ERROR_LOG) > 200_000:
            with open(ERROR_LOG, encoding="utf-8", errors="replace") as f:
                old = f.read()
            with open(ERROR_LOG, "w", encoding="utf-8") as f:
                f.write(old[len(old) // 2:])
        with open(ERROR_LOG, "a", encoding="utf-8") as f:
            f.write(text)
    except OSError:
        pass


def popup_at(pop, widget, x, y, stable=None):
    """Kontextmenü an (x, y) in widget zeigen – aber an einem Eltern-Widget aufhängen, das Neuaufbauten überlebt.
    Hing es an der Listenzeile und die Liste wurde bei offenem Menü neu gefüllt (Autospeichern, Uhr-Tick),
    stürzte GTK 4.14 (Ubuntu 24.04) ab."""
    from gi.repository import Graphene
    anchor = widget
    if stable is not None and widget.is_ancestor(stable):
        anchor = stable
    else:
        host = widget.get_ancestor(Gtk.Popover)               # Zeile im Aufklapp-Menü: dessen Inhalt
        if host is not None and host.get_child() is not None and widget.is_ancestor(host.get_child()):
            anchor = host.get_child()
    ok, p = widget.compute_point(anchor, Graphene.Point().init(x, y))
    if not ok:
        anchor, p = widget, Graphene.Point().init(x, y)
    pop.set_parent(anchor)
    r = Gdk.Rectangle()
    r.x, r.y, r.width, r.height = int(p.x), int(p.y), 1, 1
    pop.set_pointing_to(r)
    pop.connect("closed", lambda q: GLib.idle_add(lambda: (q.get_parent() and q.unparent(), False)[1]))
    pop.popup()


def show_in_files(path):
    """Datei im Dateimanager zeigen (markiert, über org.freedesktop.FileManager1), sonst den Ordner öffnen."""
    uri = Gio.File.new_for_path(path).get_uri()
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        bus.call_sync("org.freedesktop.FileManager1", "/org/freedesktop/FileManager1",
                      "org.freedesktop.FileManager1", "ShowItems", GLib.Variant("(ass)", ([uri], "")),
                      None, Gio.DBusCallFlags.NONE, 3000, None)
    except Exception:  # noqa: BLE001 – kein Dateimanager mit dieser Schnittstelle
        Gio.AppInfo.launch_default_for_uri(Gio.File.new_for_path(os.path.dirname(path)).get_uri(), None)


def is_empty(n):
    return not n["title"].strip() and not n["text"].strip() and not n.get("media")


def font_choices():
    """(Anzeige, Familie) – Familie None heißt: Standardschrift der App."""
    have = {f.get_name() for f in Gtk.Label().get_pango_context().list_families()}

    def first(*names):
        return next((n for n in names if n in have), None)
    out = [("Standard", None)]
    for label, cands in (("Sans", ("Noto Sans", "DejaVu Sans")), ("Serif", ("Noto Serif", "DejaVu Serif")),
                         ("Plakativ", ("Anton",))):
        fam = first(*cands)
        if fam:
            out.append((label, fam))
    return out


class NotesWindow(Gtk.ApplicationWindow):
    """Meldet Breitenänderungen (auch beim Kacheln durch Hyprland, wo default-width nicht mitläuft)."""

    def __init__(self, on_width, **kw):
        super().__init__(**kw)
        self._on_width, self._w = on_width, 0

    def do_size_allocate(self, width, height, baseline):
        Gtk.ApplicationWindow.do_size_allocate(self, width, height, baseline)
        if (width, height) != self._w:
            self._w = (width, height)
            GLib.idle_add(lambda: self._on_width(width, height) and False)


class NoteTableHost:
    """Was writer.TableBlock von „seinem“ Editor erwartet – hier für Tabellen mitten in Notizen."""

    def __init__(self, app):
        self.app = app

    def checkpoint(self):
        pass                                    # Rückgängig bündelt der Notiz-Verlauf über note_changed()

    def child_changed(self):
        self.app.note_table_changed()

    def goto_line(self, line):
        pass

    def focus_text(self):
        self.app.text.grab_focus()

    def remove_block(self, w):
        self.app.remove_note_table(w)


class Notes(Gtk.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.HANDLES_OPEN)
        self.prefs = self.load_prefs()
        if "doc_lang" not in self.prefs:             # bestehende Einstellungen: bisher war alles deutsch
            loc = (os.environ.get("LC_ALL") or os.environ.get("LANG") or "").lower()
            self.prefs["doc_lang"] = "en" if (not self.prefs and loc.startswith("en")) else "de"
        self.kind = self.prefs.get("kind", "notes")     # Modus: "notes" oder "docs"
        if self.kind not in KINDS:
            self.kind = "notes"
        self.stores = {"notes": st.Store(), "docs": st.Store(DOCS), "latex": st.Store(LATEX)}
        self.last_sel = {}
        self.win = None
        self.current = None
        self.mode = "notes"           # oder "trash"
        self._save_id = None
        self._loading = False
        self._fmt_sync = False
        self._toast_id = None
        self._undo = None
        self.active = set()           # Formatierung für das nächste Tippen (ohne Markierung)
        self._confirm_id = None
        self.label_filter = None      # Schlagwort-Filter der Liste
        self.home_expanded = None     # Home: aufgeklappte Spalte („alle“)
        self.daemon = False           # mit --daemon gestartet: Fenster erst auf Abruf zeigen
        self.quit_on_close = False
        self.version, self.here = VERSION, HERE
        wp = self.prefs.get("writer", {})              # Standardschrift der Formatvorlage „Standard“
        if wp.get("font"):
            df.BASE_FONT = wp["font"]
        if wp.get("size"):
            size = float(wp["size"])
            df.STYLE_FMT["normal"] = (size, False, False)
            df.STYLE_FMT["quote"] = (size, False, True)
        hist = self.prefs.get("history", {})
        st.HISTORY_MINUTES = hist.get("minutes", st.HISTORY_MINUTES)
        st.HISTORY_MAX = hist.get("max", st.HISTORY_MAX)
        start = self.prefs.get("start_kind", "home")
        if start in KINDS:
            self.kind = start
        self.view = "home" if start == "home" else "kind"     # "home" = Übersicht über alle drei Bereiche

    @property
    def store(self):
        return self.stores[self.kind]

    @property
    def docs(self):
        return self.kind == "docs"

    @property
    def tex(self):
        return self.kind == "latex"

    def noun(self, plural=False):
        return KINDS[self.kind][4 if plural else 3]

    def new_label(self):
        return {"notes": "Neue Notiz", "docs": "Neues Dokument", "latex": "Neues LaTeX-Dokument"}[self.kind]

    def load_prefs(self):
        try:
            with open(PREFS) as f:
                return json.load(f)
        except FileNotFoundError:
            return {}
        except (OSError, ValueError):
            try:                                 # kaputte Einstellungen nie stillschweigend überschreiben
                import shutil
                shutil.copy2(PREFS, PREFS + ".kaputt-" + time.strftime("%Y%m%d-%H%M%S"))
            except OSError:
                pass
            return {}

    def save_prefs(self):
        try:
            os.makedirs(os.path.dirname(PREFS), exist_ok=True)
            tmp = PREFS + ".tmp"
            with open(tmp, "w") as f:
                json.dump(self.prefs, f, indent=1)
            os.replace(tmp, PREFS)               # nie halb geschrieben
        except OSError:
            pass

    def keep_running(self):
        """Im Hintergrund weiterleben: nächster Start = Fenster sofort da (kein Python-/GTK-Start)."""
        if not getattr(self, "_held", False):
            self._held = True
            self.hold()

    def background(self):
        # Windows: kein D-Bus → ein neuer Start fände die versteckte Instanz nicht; dort wirklich beenden
        return self.prefs.get("background", True) and not self.quit_on_close and os.name != "nt"

    def really_quit(self, *_):
        self.quit_on_close = True
        if self.win and self.win.get_visible():
            self.win.close()
        else:
            if self.win:
                self.on_close()
            self.quit()

    def do_startup(self):
        Gtk.Application.do_startup(self)
        quit_act = Gio.SimpleAction.new("quit", None)
        quit_act.connect("activate", self.really_quit)
        self.add_action(quit_act)
        for name, cb in (("remind", lambda a, v: self.fire_reminder(v.get_string()) if self.win else None),
                         ("open-note", lambda a, v: self.open_note(v.get_string())),
                         ("open-settings", lambda a, v: (self.do_activate(), self.open_settings(v.get_string() or None)))):
            act = Gio.SimpleAction.new(name, GLib.VariantType.new("s"))
            act.connect("activate", cb)
            self.add_action(act)

    def do_activate(self):
        first = not self.win and not os.path.exists(PREFS)
        if not self.win:
            self.build()
        if self.daemon:             # --daemon: Fenster vorbereiten, aber erst beim nächsten Aufruf zeigen
            self.daemon = False
            self.keep_running()
            return
        getattr(glass, "bring_here", lambda w: None)(self.win)   # offen auf anderem Arbeitsbereich → hierher holen
        self.win.present()
        GLib.idle_add(self.on_shown)
        if first:      # erster Start (z. B. bei Freunden): kurz zeigen, wo Design & Sprache stecken
            GLib.timeout_add(900, lambda: (self.notify("Willkommen! Design und Sprache findest du in den "
                                                       "Einstellungen (Strg+,)"), False)[-1])
        elif not getattr(self, "_news_told", False):
            self._news_told = True
            try:
                import changelog
                if changelog.check_new("notist", VERSION):
                    self.ver_btn.remove_css_class("off")
                    self.ver_btn.add_css_class("news")
                    self.ver_btn.set_label(f"󰋚 v{VERSION}")
                    GLib.timeout_add(900, lambda: (self.notify(f"Neu in v{VERSION} – changelog oben rechts"), False)[-1])
            except Exception as e:
                print("changelog:", e, file=sys.stderr)
        self.check_update()

    def check_update(self):
        """Neuere Version auf GitHub? → Versionsknopf „󰚰 v4.5.0 → v4.6.0“ + einmal Hinweis (Cache 6 h)."""
        try:
            import changelog

            def has_update(latest):
                if getattr(self, "_update_told", None) != latest:
                    self._update_told = latest
                    GLib.timeout_add(1200, lambda: (self.notify(changelog.update_text(latest)), False)[-1])
            getattr(changelog, "check_update", lambda *a: None)("notist", VERSION, has_update)
            if getattr(self, "upd_btn", None):
                self.upd_btn.recheck()
        except Exception as e:
            print("update-check:", e, file=sys.stderr)

    def on_shown(self):
        """Fenster (wieder) sichtbar: neue Dateien im notist-Ordner aufnehmen, offene Datei ggf. neu einlesen."""
        self.scan_files()
        n = self.current
        if n and self.view != "home" and self.mode != "trash" and not self._save_id \
                and self.reload_if_changed(n, self.kind):
            self.current = None
            self.select(n["id"])
            self.notify(f"{os.path.basename(n['file'])} wurde außerhalb geändert – neu eingelesen")
        return False

    def show_changelog(self, parent=None):
        """Changelog-Fenster in den Farben des gewählten Designs."""
        import changelog
        import themes
        colors = themes.resolve()[0]
        if getattr(self, "ver_btn", None):
            self.ver_btn.remove_css_class("news")
            self.ver_btn.add_css_class("off")
            self.ver_btn.set_label(f"v{VERSION}")
        changelog.open_window(parent or self.win, "notist", os.path.join(HERE, "CHANGELOG.md"), key="notist",
                              version=VERSION, colors_css=colors)

    def do_open(self, files, n, hint):
        """notes datei.docx / datei.tex – auch über „Öffnen mit“ im Dateimanager."""
        self.do_activate()
        for f in files:
            p = f.get_path()
            if p and os.path.isfile(p):
                self.import_file(p)

    def load_css(self, *_):
        import themes
        css, light = themes.resolve()           # gewähltes Design, sonst Desktop-Farben (hell/dunkel nach Wahl)
        try:                                    # GTK-Grundthema (Auswahllisten, Menüs) passend hell/dunkel
            Gtk.Settings.get_default().set_property("gtk-application-prefer-dark-theme", not light)
        except TypeError:
            pass
        for w in [self.win] + [x for x in (getattr(self, "_settings_win", None),) if x]:
            if w:
                (w.add_css_class if light else w.remove_css_class)("light-theme")
        wcss = wr.CSS.replace('textview.page { font-family: "Noto Sans"',
                              f'textview.page {{ font-family: "{df.BASE_FONT}", "Noto Sans"').replace(
            "font-size: 11pt; }", f"font-size: {df.STYLE_FMT['normal'][0]:g}pt; }}")
        import dialogs
        extra = ""
        import minical
        import flow
        import translate
        import findbar
        extra += minical.CSS + flow.CSS + findbar.CSS
        self.css.load_from_string(extra + css + APP_CSS + EDITOR_CSS + CSS + COLOR_CSS + wcss + lx.CSS + lx.tx.CSS +
                                  setw.CSS + glass.GLASS_CSS + dialogs.CSS + ch.CSS + swipe.CSS + rc.CSS + TUI_CSS +
                                  translate.CSS)
        if getattr(self, "writer", None):
            GLib.idle_add(lambda: self.writer.refresh_colors() and False)
        if getattr(self, "latex", None):
            GLib.idle_add(lambda: self.latex.refresh_colors() and False)
        GLib.idle_add(self._redraw_all)
        GLib.timeout_add(120, self._retint_text)

    def _retint_text(self):
        """Text-Tags tragen feste Farben (Kästchen ☐ in Notizen, Aufzählungszeichen) → nach Farbwechsel neu setzen."""
        if getattr(self, "text", None) is not None and self.current and not self.docs and not self.tex:
            try:
                self.style_checks()
            except Exception:
                pass
        return False

    def _on_colors_changed(self, _mon, f, other, _ev):
        if os.path.basename(MATUGEN_CSS) not in {x.get_basename() for x in (f, other) if x is not None}:
            return
        if self._css_timer:
            GLib.source_remove(self._css_timer)
        self._css_timer = GLib.timeout_add(250, self._colors_settled)

    def _colors_settled(self):
        self._css_timer = 0
        try:
            src = open(MATUGEN_CSS).read()
        except OSError:
            return False
        if "@define-color" not in src:          # matugen schreibt noch → gleich nochmal
            self._css_timer = GLib.timeout_add(250, self._colors_settled)
            return False
        self.load_css()
        return False

    def _redraw_all(self):
        """Selbst gezeichnete Teile (Kartentitel …) lesen die Farbe beim Zeichnen, GTK zeichnet sie beim
        Farbwechsel aber nicht von selbst neu."""
        def walk(w):
            w.queue_draw()
            c = w.get_first_child()
            while c is not None:
                walk(c)
                c = c.get_next_sibling()
        for win in self.get_windows():
            walk(win)
        return False

    # ================= Aufbau =================
    def build(self):
        install_logo()
        if not os.environ.get("NOTES_NO_TIMERS"):        # Tests fassen das System nicht an
            install_mime()
        self.css = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), self.css,
                                                  Gtk.STYLE_PROVIDER_PRIORITY_USER)
        import themes
        if not themes.exists() and self.prefs.get("theme") in themes.THEMES:      # bisherige Wahl übernehmen
            themes.save(theme=self.prefs["theme"])
        self.load_css()
        self.theme_mon = themes.watch(self.load_css)        # Design in den Einstellungen irgendeiner -ist-App geändert
        # Super+W: matugen schreibt colors.css (teils in mehreren Schritten, teils per Umbenennen) →
        # Ordner beobachten, entprellen, erst laden wenn die Datei vollständig ist (wie in scourge).
        self._css_timer = 0
        self.monitor = Gio.File.new_for_path(os.path.dirname(MATUGEN_CSS)).monitor_directory(
            Gio.FileMonitorFlags.WATCH_MOVES, None)
        self.monitor.set_rate_limit(100)
        self.monitor.connect("changed", self._on_colors_changed)

        self.compact = None
        self.win = NotesWindow(self.on_width, application=self, title="notist")
        self.win.set_default_size(*getattr(glass, "fit_size", lambda w, h: (w, h))(1180, 760))   # kleine Bildschirme
        self.win.set_decorated(not tiling_desktop())
        self.win.set_icon_name("notist")
        self.win.add_css_class("pb-window")
        self.win.connect("close-request", self.on_close)
        for name, cb, keys in (("new", self.new_note, ["<Control>n"]),
                               ("find", lambda *_: self.find_here(), ["<Control>f"]),
                               ("find-all", lambda *_: self.find_everywhere(), ["<Control><Shift>f"]),
                               ("translator", lambda *_: self.toggle_translator(), ["<Control><Shift>t"]),
                               ("delete", self.delete_note, []),   # Strg+Entf löscht im Text das nächste Wort
                               ("pin", lambda *_: self.pin_btn.set_active(not self.pin_btn.get_active()), ["<Control>p"]),
                               ("bold", lambda *_: self.fmt("bold"), ["<Control>b"]),
                               ("italic", lambda *_: self.fmt("italic"), ["<Control>i"]),
                               ("underline", lambda *_: self.fmt("underline"), ["<Control>u"]),
                               ("strike", lambda *_: self.fmt("strike"), ["<Control>d"]),
                               ("checklist", lambda *_: self.toggle_checklist(), ["<Control><Shift>l"]),
                               ("switcher", lambda *_: self.switcher.get_visible() and self.switcher.popup(),
                                ["<Control>t"]),
                               ("mode-home", lambda *_: self.go_home(), ["<Alt>0"]),
                               ("mode-notes", lambda *_: self.set_kind("notes"), ["<Alt>1"]),
                               ("mode-docs", lambda *_: self.set_kind("docs"), ["<Alt>2"]),
                               ("mode-latex", lambda *_: self.set_kind("latex"), ["<Alt>3"]),
                               ("latex-folder", lambda *_: self.open_latex_folder(), []),
                               ("latex-packages", lambda *_: self.latex.open_packages(), []),
                               ("settings", lambda *_: self.open_settings(), ["<Control>comma"]),
                               ("shortcuts", lambda *_: setw.ShortcutsWindow(self.win).present(), ["F1"]),
                               ("archive", lambda *_: self.toggle_archive(), ["<Control><Shift>a"]),
                               ("history", lambda *_: self.show_history(), ["<Control><Shift>h"]),
                               ("latex-to-words", lambda *_: self.convert_current("docs"), []),
                               ("to-latex", lambda *_: self.convert_current("latex"), []),
                               ("tidy", lambda *_: self.tidy_note(), []),
                               ("to-words", lambda *_: self.convert_current("docs"), []),
                               ("share-copy", lambda *_: self.share_copy(), []),
                               ("share-mail", lambda *_: self.share_mail(), []),
                               ("share-file", lambda *_: self.share_file(), []),
                               ("share-bundle", lambda *_: self.share_bundle(), []),
                               ("doc-to-latex", lambda *_: self.convert_current("latex"), []),
                               ("doc-import", lambda *_: self.import_dialog(), ["<Control>o"]),
                               ("doc-print", lambda *_: self.print_doc(), []),
                               ("close", lambda *_: self.win.close(), ["<Control>q"]),
                               ("back-home", lambda *_: self.close_doc_tab() if self.view != "home" else self.leave_to_home(),
                                ["<Control>w"]),
                               ("tab-next", lambda *_: self.cycle_doc_tab(1), ["<Control>Page_Down"]),
                               ("tab-prev", lambda *_: self.cycle_doc_tab(-1), ["<Control>Page_Up"]),
                               ("new-folder-move", lambda *_: self.folder_prompt(self.more_btn, None, move=True), [])):
            act = Gio.SimpleAction.new(name, None)
            act.connect("activate", cb)
            self.win.add_action(act)
            self.set_accels_for_action(f"win.{name}", keys)
        for name, cb in (("opt", lambda a, v: self.toggle_opt(v.get_string())),
                         ("doc-export", lambda a, v: self.export_dialog(v.get_string())),
                         ("export-as", lambda a, v: self.export_dialog(v.get_string())),
                         ("latex-export", lambda a, v: self.latex_export_dialog(v.get_string())),
                         ("doc-import-path", lambda a, v: self.import_file(v.get_string())),
                         ("move-folder", lambda a, v: self.move_to_folder(self.current, v.get_string()))):
            act = Gio.SimpleAction.new(name, GLib.VariantType.new("s"))
            act.connect("activate", cb)
            self.win.add_action(act)

        esc = Gtk.EventControllerKey()       # Bubble-Phase: Suchleisten/Vorschläge bekommen Esc zuerst
        esc.connect("key-pressed", self.on_win_key)
        self.win.add_controller(esc)
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.win.set_child(root)
        self.root_box = root
        top = Gtk.Box(spacing=2)
        top.add_css_class("topbar")
        top.add_css_class("tbar")
        # Marken-Chip + Tabs wie bei datist/musicalist: ⁰ home  ¹ notizen  ² words  ³ latex
        self.brand = Gtk.Button(label="notist", tooltip_text="Zuletzt-Leiste anheften / ausblenden",
                                valign=Gtk.Align.CENTER,
                                focus_on_click=False)
        self.brand.add_css_class("brand")
        self.brand.connect("clicked", lambda *_: self.recent.toggle())
        top.append(self.brand)
        self.home_btn = ch.tab(0, HOME_ICON, "home", "Home – alles auf einen Blick (Alt+0)")
        self.home_btn.connect("toggled", lambda btn: btn.get_active() and self.go_home())
        top.append(self.home_btn)
        self.kind_btns = {}
        group = self.home_btn
        for i, (kind, (_, icon, tip, _, _)) in enumerate(KINDS.items(), 1):
            b = ch.tab(i, icon, TAB_NAMES[kind], tip)
            b.set_group(group)
            b.connect("toggled", lambda btn, k=kind: btn.get_active() and self.set_kind(k))
            top.append(b)
            self.kind_btns[kind] = b
        self.tab_btns = [self.home_btn] + list(self.kind_btns.values())
        # Dropdown für die kompakte Ansicht: zeigt das offene Dokument, klappt Suche + Liste aus
        self.switcher = Gtk.MenuButton(valign=Gtk.Align.CENTER, visible=False,
                                       tooltip_text="Alle Notizen/Dokumente (Strg+T)")
        self.switcher.add_css_class("switcher")
        sw_titles = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)       # nur noch Zwischenspeicher für update_switcher
        self.switch_title = Gtk.Label(xalign=0, ellipsize=3)
        self.switch_sub = Gtk.Label(xalign=0, ellipsize=3)
        self.switch_chev = Gtk.Label(label="\U000F0140")
        self.switcher.set_child(Gtk.Label(label="\U000F035C"))
        self.switch_pop = Gtk.Popover(has_arrow=False)
        self.switch_pop.add_css_class("switch-pop")
        sheet = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        head = Gtk.Box(spacing=8)
        self.sheet_title = Gtk.Label(xalign=0, hexpand=True)
        self.sheet_title.add_css_class("sheet-title")
        head.append(self.sheet_title)
        snew = Gtk.Button(label="󰐕", tooltip_text="Neu (Strg+N)", action_name="win.new")
        snew.add_css_class("pb"); snew.add_css_class("sheet-btn")
        snew.connect("clicked", lambda *_: self.switch_pop.popdown())
        head.append(snew)
        sclose = Gtk.Button(label="󰅃", tooltip_text="Zuklappen (Esc)")
        sclose.add_css_class("pb"); sclose.add_css_class("sheet-btn")
        sclose.connect("clicked", lambda *_: self.switch_pop.popdown())
        head.append(sclose)
        sheet.append(head)
        self.switch_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        sheet.append(self.switch_box)
        self.switch_pop.set_child(sheet)
        self.switch_sheet = sheet
        self.switch_pop.connect("show", self.on_switch_show)
        self.switch_pop.connect("closed", lambda *_: self.switch_chev.set_label("\U000F0140"))
        self.switcher.set_popover(self.switch_pop)
        self.lead_spacer = Gtk.Box(visible=False)
        # Offene Einträge als Tabs (wie bei filist); die Leiste scrollt, statt das Fenster aufzuweiten
        self.open_tabs = {k: [] for k in KINDS}
        self._tabs_sig = None
        self.doc_tabs = Gtk.Box(spacing=2, valign=Gtk.Align.CENTER)
        self.tab_scroll = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.EXTERNAL,
                                             vscrollbar_policy=Gtk.PolicyType.NEVER, hexpand=True, visible=False,
                                             propagate_natural_width=False)
        self.tab_scroll.set_child(self.doc_tabs)
        sep = Gtk.Label(label="│", margin_start=6, margin_end=6)
        sep.add_css_class("doctab-sep")
        self.tab_sep = sep
        top.append(sep)
        top.append(self.tab_scroll)
        self.tab_plus = Gtk.Button(label="+", tooltip_text="Neu (Strg+N)", focus_on_click=False,
                                   valign=Gtk.Align.CENTER, visible=False)
        self.tab_plus.add_css_class("ttab")
        self.tab_plus.connect("clicked", lambda *_: self.new_note())
        top.append(self.tab_plus)
        top.append(self.switcher)
        titles = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True, valign=Gtk.Align.CENTER, visible=False)
        self.titles = titles
        self.top = top
        t = Gtk.Label(label="notist", xalign=0)
        t.add_css_class("app-title")
        self.app_title = t
        self.subtitle = Gtk.Label(xalign=0, ellipsize=3)
        self.subtitle.add_css_class("app-sub")
        titles.append(t)
        titles.append(self.subtitle)
        top.append(titles)
        self.spacer = Gtk.Box(hexpand=True)
        top.append(self.spacer)
        self.toast = Gtk.Box(spacing=6, valign=Gtk.Align.CENTER, visible=False)
        self.toast.add_css_class("toast")
        self.toast_label = Gtk.Label(ellipsize=3, max_width_chars=44)
        self.toast_btn = Gtk.Button(label="Rückgängig")
        self.toast_btn.add_css_class("pb"); self.toast_btn.add_css_class("small")
        self.toast_btn.connect("clicked", lambda *_: self.undo_delete())
        self.toast.append(self.toast_label)
        self.toast.append(self.toast_btn)
        top.append(self.toast)
        self.search = Gtk.SearchEntry(placeholder_text="alle durchsuchen (strg+⇧+f)", width_chars=14, valign=Gtk.Align.CENTER)
        fc = Gtk.EventControllerFocus()
        fc.connect("leave", lambda *_: GLib.idle_add(lambda: self.update_search_vis() and False))
        self.search.add_controller(fc)
        self.search.connect("stop-search", lambda *_: (self.search.set_text(""), self.update_search_vis()))
        self.search.add_css_class("tsearch")
        self.search.connect("search-changed", lambda *_: self.refresh_list())
        top.append(self.search)
        self.open_btn = ch.button("󰝰 öffnen", "Datei öffnen (Strg+O)", action="win.doc-import")
        self.open_btn.set_margin_start(6)
        top.append(self.open_btn)
        self.new_btn = ch.button("󰐕 neu", "Neue Notiz (Strg+N)", action="win.new")
        self.new_btn.set_margin_start(6)
        top.append(self.new_btn)
        # „v4.2.0“ oben rechts → Changelog (wie filist/datist/musicalist); nach einem Update hervorgehoben
        self.ver_btn = Gtk.Button(label=f"v{VERSION}", tooltip_text="changelog – was ist neu?",
                                  valign=Gtk.Align.CENTER, focus_on_click=False, margin_start=6)
        self.ver_btn.add_css_class("tflat")
        self.ver_btn.add_css_class("off")
        self.ver_btn.connect("clicked", lambda *_: self.show_changelog())
        top.append(self.ver_btn)
        import changelog
        self.upd_btn = changelog.update_button("notist", VERSION, notify=self.notify)     # 󰚰 update neben der Version
        top.append(self.upd_btn)
        gear = ch.button("󰒓", "Einstellungen (Strg+,)", action="win.settings")
        gear.set_margin_start(6)
        top.append(gear)
        self.glass_btn = glass.GlassToggle(self.win)
        self.glass_btn.set_margin_start(6)
        top.append(self.glass_btn)
        if tiling_desktop():          # sonst hat das Fenster eine normale Titelleiste mit eigenem ✕
            close = Gtk.Button(label="✕", tooltip_text="Schließen (Strg+Q)", action_name="win.close",
                               valign=Gtk.Align.CENTER, focus_on_click=False)
            close.add_css_class("tclose")
            close.set_margin_start(4)
            top.append(close)
        # Die Kopfleiste darf die Mindestbreite nicht bestimmen: sonst kann das Fenster beim Verkleinern
        # (z. B. Vollbild → halber Bildschirm) nie unter die Schwelle der schmalen Ansicht und wird abgeschnitten.
        top_scroll = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.EXTERNAL,
                                        vscrollbar_policy=Gtk.PolicyType.NEVER, propagate_natural_height=True)
        top_scroll.set_child(top)
        root.append(top_scroll)

        # Seitenleiste | Editor mit ziehbarem Trenner (Breite wird gemerkt: prefs["side_width"])
        body = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL, vexpand=True, wide_handle=False,
                         resize_start_child=False, shrink_start_child=False, resize_end_child=True,
                         shrink_end_child=False)
        body.add_css_class("notes-body")
        self.body = body
        self.main_stack = Gtk.Stack(vexpand=True, transition_type=Gtk.StackTransitionType.CROSSFADE,
                                    transition_duration=120, hhomogeneous=False)
        self.main_stack.add_named(body, "main")
        self.main_stack.add_named(self.build_home(), "home")
        # Zwei Finger nach rechts / Maustaste „zurück“: eine Ebene zurück, am Ende landet man auf Home
        self.nav_back, self.nav_cur, self._nav_id, self._nav_skip = [], None, None, False
        self.swipe = swipe.SwipeBack(self.main_stack, self.can_nav_back, self.nav_go_back,
                                     where=self.swipe_where, target=self.swipe_target,
                                     goto=self.swipe_goto)
        # linker Rand: zuletzt benutzte Einträge des gewählten Bereichs (Klick auf „notist“ heftet sie an)
        self.recent = rc.RecentDrawer(self, self.swipe.widget)
        self.build_jump()
        # rechte untere Ecke: Übersetzer Deutsch ⇄ Englisch (Statusleiste „übersetzer“, Strg+Umschalt+T)
        import translate
        self.translator = translate.Translator(self.prefs, self.save_prefs)
        self.swipe.widget.add_overlay(self.translator)
        root.append(self.recent.widget)

        # linke Spalte: schmale Übersicht + Papierkorb
        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        left.set_size_request(215, -1)
        self.label_box = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, max_children_per_line=6,
                                     column_spacing=4, row_spacing=4, visible=False)
        self.label_box.add_css_class("label-chips")
        left.append(self.label_box)
        self.pathbar = Gtk.Box(spacing=6)
        self.pathbar.add_css_class("nt-path")
        self.crumbs = Gtk.Box(spacing=0, hexpand=True)
        self.crumbs.add_css_class("nt-crumbs")
        self.pathbar.append(self.crumbs)
        self.path_count = Gtk.Label()
        self.path_count.add_css_class("nt-count")
        self.pathbar.append(self.path_count)
        left.append(self.pathbar)
        scroll = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER, vexpand=True)
        self.list_scroll = scroll
        self.listbox = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
        self.listbox.add_css_class("notes")
        self.listbox.connect("row-selected", self.on_row_selected)
        self.listbox.connect("row-activated", self.on_row_activated)
        scroll.set_child(self.listbox)
        left.append(scroll)
        foot = Gtk.Box()
        self.archive_link = Gtk.Button(halign=Gtk.Align.START)
        self.archive_link.add_css_class("trash-link")
        self.archive_link.connect("clicked", lambda *_: self.set_mode("notes" if self.mode == "archive" else "archive"))
        self.trash_link = Gtk.Button(halign=Gtk.Align.START)
        self.trash_link.add_css_class("trash-link")
        self.trash_link.connect("clicked", lambda *_: self.set_mode("notes" if self.mode == "trash" else "trash"))
        foot.append(self.archive_link)
        foot.append(self.trash_link)
        foot.append(Gtk.Box(hexpand=True))
        self.folder_add = Gtk.Button(label="󰉗", tooltip_text="Neuer Ordner", valign=Gtk.Align.CENTER,
                                     focus_on_click=False)
        self.folder_add.add_css_class("folder-add")
        self.folder_add.connect("clicked", lambda b: self.folder_prompt(b, None))
        foot.append(self.folder_add)
        self.foot_new = Gtk.Button(label="󰐕", tooltip_text="Neue Notiz (Strg+N)", valign=Gtk.Align.CENTER,
                                   focus_on_click=False, action_name="win.new", margin_start=4)
        self.foot_new.add_css_class("folder-add")
        foot.append(self.foot_new)
        left.append(foot)
        body.set_start_child(left)
        self.left = left

        self.right = Gtk.Stack(hexpand=True, transition_type=Gtk.StackTransitionType.CROSSFADE)
        # Mindestbreite des Editors darf den Trenner nicht begrenzen (Ubuntu: Schrift größer → Leiste ließ sich kaum ziehen)
        right_wrap = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.EXTERNAL, vscrollbar_policy=Gtk.PolicyType.NEVER,
                                        hexpand=True, vexpand=True, min_content_width=0)
        right_wrap.set_child(self.right)
        body.set_end_child(right_wrap)
        body.set_position(int(self.prefs.get("side_width", 330)))
        body.connect("notify::position", self.on_side_moved)
        self.right.add_named(self.build_editor(), "editor")

        empty = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, valign=Gtk.Align.CENTER,
                        halign=Gtk.Align.CENTER)
        self.empty_icon = Gtk.Label(label="󰠮")
        self.empty_icon.add_css_class("empty-icon")
        self.empty_title = Gtk.Label(label="Noch keine Notizen")
        self.empty_title.add_css_class("empty-title")
        self.empty_hint = Gtk.Label(label="Strg+N oder der Knopf unten legt eine an.", wrap=True,
                                    justify=Gtk.Justification.CENTER)
        self.empty_hint.add_css_class("empty-hint")
        self.empty_btn = Gtk.Button(label="󰐕  Erste Notiz", action_name="win.new", halign=Gtk.Align.CENTER, margin_top=6)
        self.empty_btn.add_css_class("tbtn")
        self.empty_open = Gtk.Button(label="󰝰  Datei öffnen", action_name="win.doc-import", halign=Gtk.Align.CENTER)
        self.empty_open.add_css_class("tbtn")
        for w in (self.empty_icon, self.empty_title, self.empty_hint, self.empty_btn, self.empty_open):
            empty.append(w)
        self.right.add_named(empty, "empty")

        drop = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY)
        drop.connect("drop", self.on_window_drop)
        self.listbox.add_controller(drop)

        # Statuszeile unten (wie datist/musicalist): Speicherstand + Aktionen bzw. Tastenhinweise
        status = Gtk.Box(spacing=12)
        status.add_css_class("tstatus")
        self.home_info = ch.label("", "dim", hexpand=True, ellipsize=True)
        status.append(self.home_info)
        self.ed_bar.set_hexpand(True)
        status.append(self.ed_bar)
        self.hint_box = Gtk.Box(spacing=12)
        for k, v in (("alt+0-3", "bereich"), ("strg+n", "neu"), ("strg+o", "öffnen"), ("strg+,", "einstellungen")):
            self.hint_box.append(ch.hint(k, v))
        status.append(self.hint_box)
        self.trx_btn = Gtk.ToggleButton(label="󰗊 übersetzer", focus_on_click=False, valign=Gtk.Align.END,
                                        tooltip_text="Übersetzer Deutsch ⇄ Englisch (Strg+Umschalt+T)")
        self.trx_btn.add_css_class("pb"); self.trx_btn.add_css_class("small")
        self.trx_btn.set_cursor_from_name("pointer")
        self.trx_btn.connect("toggled", self.on_trx_btn)
        gc = Gtk.GestureClick(button=3)                      # Rechtsklick: linguist-Einstellungen (nur im Hover-Modus)
        gc.connect("pressed", lambda *_: linguist_link.hover_enabled() and linguist_link.launch("--settings"))
        self.trx_btn.add_controller(gc)
        self._trx_sync = False
        self.linguist_mon = linguist_link.watch(self.sync_trx_btn)
        self.sync_trx_btn()
        self.translator.on_toggled = self.translator_toggled
        status.append(self.trx_btn)
        status_scroll = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.EXTERNAL,
                                           vscrollbar_policy=Gtk.PolicyType.NEVER, propagate_natural_height=True)
        status_scroll.set_child(status)
        root.append(status_scroll)
        self.right.connect("notify::visible-child-name", lambda *_: self.update_status_ui())

        wr.ist_tree(self.win)            # Auswahllisten + Popover-Knöpfe im Suite-Stil (ohne Pfeil, kleine Köpfe)
        self.view, start_view = "kind", self.view
        self.apply_kind()
        if start_view == "home":
            self.go_home()
        GLib.timeout_add_seconds(30, self.tick)
        GLib.timeout_add_seconds(15, lambda: self.maybe_backup() and False)
        GLib.timeout_add_seconds(30, self.check_reminders)
        GLib.timeout_add_seconds(3, lambda: self.check_reminders() and False)
        GLib.timeout_add_seconds(1800, self.maybe_backup)

    def build_editor(self):
        ed = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        ed.add_css_class("editor")
        self.editor_box = ed
        # hhomogeneous=False: nur der sichtbare Bereich zählt für die Mindestbreite (sonst bremst der
        # Words-Ribbon auch im Notizen-Modus das Verkleinern des Fensters)
        # vhomogeneous=False: sonst verlangt auch eine Notiz die Mindesthöhe des LaTeX-Editors → in kleinen
        # Fenstern wird unten abgeschnitten (Statuszeile weg, Textfeld bis zum Fensterrand)
        self.kind_stack = Gtk.Stack(vexpand=True, transition_type=Gtk.StackTransitionType.CROSSFADE,
                                    hhomogeneous=False, vhomogeneous=False, interpolate_size=False)
        ed.append(self.kind_stack)
        note = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.kind_stack.add_named(note, "notes")
        self.writer = wr.Writer(self.win, self.on_edit, self.prefs.setdefault("writer", {}))
        self.writer.autofmt_prefs = self.prefs
        self.writer.opt_get = self.opt_value          # Autokorrektur & Co. auch aus der Fließend-Leiste
        self.writer.opt_set = self.toggle_opt
        self.writer.on_view_change = self.on_doc_view
        self.kind_stack.add_named(self.writer, "docs")
        self.title = Gtk.Entry(placeholder_text="Titel")
        self.title.add_css_class("note-title")
        self.title.connect("changed", self.on_edit)
        self.title.connect("activate", lambda *_: self.focus_text())
        # Tab im Titel springt direkt in den Text (nicht durch F/K/U/Schriftart)
        k = Gtk.EventControllerKey()
        k.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        k.connect("key-pressed", self.on_title_key)
        self.title.add_controller(k)
        self.title.set_hexpand(True)
        self.note_title_row = Gtk.Box(spacing=6)
        self.note_title_row.append(self.title)
        note.append(self.note_title_row)

        # Formatierung: gilt für markierten Text, ohne Markierung für das, was man als Nächstes tippt
        fmt = Gtk.Box()
        fmt.set_layout_manager(wr.WrapLayout(spacing=0, row_spacing=4))
        fmt.add_css_class("note-tools")

        def group(*ws, last=False):
            g = Gtk.Box(spacing=2, valign=Gtk.Align.CENTER)
            g.add_css_class("wgroup")
            if last:
                g.add_css_class("last")
            for w in ws:
                g.append(w)
            fmt.append(g)
        self.note_undo_btn = wr.tool("󰕌", "Rückgängig (Strg+Z)", lambda *_: self.note_undo())
        self.note_redo_btn = wr.tool("󰑎", "Wiederholen (Strg+Umschalt+Z)", lambda *_: self.note_redo())
        group(self.note_undo_btn, self.note_redo_btn)
        self.fmt_buttons = {}
        for name, label, tip in (("bold", "<b>F</b>", "Fett (Strg+B)"), ("italic", "<i>K</i>", "Kursiv (Strg+I)"),
                                 ("underline", "<u>U</u>", "Unterstrichen (Strg+U)"),
                                 ("strike", "<s>S</s>", "Durchgestrichen (Strg+D)")):
            b = wr.tool(label, tip, toggle=True, markup=True)
            b.connect("toggled", self.on_fmt_toggled, name)
            self.fmt_buttons[name] = b
        group(*self.fmt_buttons.values())
        self.fonts = font_choices()
        labels = [l for l, _ in self.fonts] + ["Andere …"]
        self.font_drop = Gtk.DropDown.new_from_strings(labels)
        self.font_drop.set_tooltip_text("Schriftart für markierten Text")
        wr.font_dropdown(self.font_drop)
        self.font_drop.add_css_class("wt")
        self.font_drop.set_can_focus(False)
        self.font_drop.connect("notify::selected", self.on_font_selected)
        group(self.font_drop)
        group(wr.tool("󰉹", "Aufzählung – oder einfach „- “ am Zeilenanfang tippen", lambda *_: self.toggle_list("bullet")),
              wr.tool("󰉻", "Nummerierung – oder „1. “ tippen", lambda *_: self.toggle_list("number")),
              wr.tool("\U000F0C52", "Checkliste ein/aus (Strg+Umschalt+L)", lambda *_: self.toggle_checklist()))
        self.spell_btns = []
        self.tbl_btn = wr.tool("󰓫", "Tabelle einfügen", None)
        self.tbl_btn.connect("clicked", lambda b: self.ask_note_table(b))
        group(wr.tool("󰋩", "Bild einfügen – oder einfach mit Strg+V einfügen bzw. hineinziehen",
                      lambda *_: self.pick_note_image()), self.tbl_btn, self.make_spell_btn("wts"), last=True)
        self.fmt_bar = fmt
        note.append(fmt)

        tscroll = Gtk.ScrolledWindow(vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER)
        self.text = Gtk.TextView(wrap_mode=Gtk.WrapMode.WORD_CHAR, top_margin=2, bottom_margin=12,
                                 left_margin=0, right_margin=4, pixels_inside_wrap=2)
        self.text.add_css_class("note-text")
        self.text.add_tick_callback(self._tbl_tick)
        wr.calm_handles(self.text)
        buf = self.text.get_buffer()
        buf.create_tag("bold", weight=Pango.Weight.BOLD)
        buf.create_tag("italic", style=Pango.Style.ITALIC)
        buf.create_tag("underline", underline=Pango.Underline.SINGLE)
        buf.create_tag("strike", strikethrough=True)
        buf.create_tag("listmark", weight=Pango.Weight.BOLD)
        buf.create_tag("box", foreground="#888888", scale=1.3)      # Farbe kommt aus dem Theme (style_checks)
        buf.create_tag("done", strikethrough=True)
        buf.connect("changed", self.on_edit)
        buf.connect("changed", lambda *_: self.note_changed())
        buf.set_enable_undo(False)          # eigener Verlauf: GTKs kennt keine Formatierung
        self.n_undo, self.n_redo, self.n_last, self._n_pending, self._n_before = [], [], None, None, None
        buf.connect("changed", lambda *_: self.queue_checks())
        self.note_images = {}            # Gdk.Texture → {"img", "mime", "w", "h"}
        self.note_tables = {}            # Gtk.TextChildAnchor → writer.TableBlock (Tabellen in Notizen)
        self.note_tbl_host = NoteTableHost(self)
        self.text.connect("paste-clipboard", self.on_note_paste)
        drop = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY)
        drop.connect("drop", self.on_note_drop)
        self.text.add_controller(drop)
        buf.connect_after("insert-text", self.on_inserted)
        click = Gtk.GestureClick()
        click.connect("released", self.on_text_click)
        self.text.add_controller(click)
        motion = Gtk.EventControllerMotion()
        motion.connect("motion", self.on_text_motion)
        self.text.add_controller(motion)
        keys = Gtk.EventControllerKey()
        keys.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        keys.connect("key-pressed", self.on_text_key)
        self.text.add_controller(keys)
        self._checks_id = None
        spell.set_langs(self.prefs.get("spell_langs", list(spell.DEFAULT_LANGS)))
        self.spell_notes = spell.SpellCheck(self.text, lambda: self.spell_on() and not self.docs
                                            and self.mode != "trash")
        self.spell_docs = spell.SpellCheck(self.writer.view, lambda: self.spell_on() and self.docs
                                           and self.mode != "trash")
        # Rechtsklick-Menü (spell.context_menu) nutzt den eigenen Verlauf statt GTKs
        self.spell_notes.undo = (self.note_undo, self.note_redo)
        self.spell_docs.undo = (self.writer.undo, self.writer.redo)
        self.writer.tool_tail.append(self.make_spell_btn("wt"))
        self.latex = lx.LatexEditor(self.win, self.on_edit, self.prefs.setdefault("latex", {}), self.notify)
        self.kind_stack.add_named(self.latex, "latex")
        buf.connect("mark-set", self.on_mark_set)
        tscroll.set_child(self.text)
        import findbar
        self.note_find = findbar.NoteFind(self.text, "notizen", lambda q: self.count_all("notes", q),
                                          self.search_all)
        note.append(self.note_find.widget)
        findbar.attach_all(self.writer.findrev.get_child(), self.writer.find_entry, "dokumenten",
                           lambda q: self.count_all("docs", q), self.search_all)
        findbar.attach_all(self.latex.findrev.get_child(), self.latex.find_entry, "latex-dokumenten",
                           lambda q: self.count_all("latex", q), self.search_all)
        note.append(tscroll)
        self.note_scroll = tscroll
        import follow
        on = lambda: self.opt_value("typewriter")
        self.follows = [
            follow.Follow(self.text, on, lambda px: self.text.set_bottom_margin(12 + px)),
            follow.Follow(self.writer.view, on, lambda px: (setattr(self.writer, "extra_bottom", px),
                                                            self.writer.update_geometry())),
            follow.Follow(self.latex.view, on, lambda px: self.latex.view.set_bottom_margin(40 + px))]

        bar = Gtk.Box(spacing=6)
        bar.add_css_class("ed-bar")
        self.ed_bar = bar
        self.save_state = Gtk.Label(label="󰄬 Gespeichert", tooltip_text="Notizen speichern sich automatisch")
        self.save_state.add_css_class("saved")
        bar.append(self.save_state)
        self.meta = Gtk.Label(xalign=0, hexpand=True, ellipsize=3)
        self.meta.add_css_class("meta")
        bar.append(self.meta)
        self.lang_btn = Gtk.Button(focus_on_click=False, valign=Gtk.Align.CENTER)
        self.lang_btn.add_css_class("pb"); self.lang_btn.add_css_class("small")
        self.lang_btn.set_cursor_from_name("pointer")
        self.lang_btn.connect("clicked", lambda *_: self.set_doc_lang("en" if self.doc_lang() == "de" else "de"))
        bar.append(self.lang_btn)
        self.rem_btn = self.make_reminder_button()
        bar.append(self.rem_btn)
        self.label_btn = self.make_label_button()
        bar.append(self.label_btn)
        self.color_btn = self.make_color_button()
        bar.append(self.color_btn)
        self.share_btn = self.make_share_button()
        bar.append(self.share_btn)
        self.more_btn = self.make_more_button()
        bar.append(self.more_btn)
        # Anheften/Löschen oben rechts in der Titelzeile des jeweiligen Bereichs (place_doc_actions)
        acts = Gtk.Box(spacing=6, valign=Gtk.Align.CENTER)
        acts.add_css_class("doc-acts")
        self.doc_actions = acts
        self.pin_btn = Gtk.ToggleButton(label="󰐃 anheften", tooltip_text="Oben in der Liste halten (Strg+P)",
                                        focus_on_click=False)
        self.pin_btn.full_label = "󰐃 anheften"
        self.pin_btn.add_css_class("tbtn")
        self.pin_btn.connect("toggled", self.on_pin)
        acts.append(self.pin_btn)
        self.del_btn = Gtk.Button(label="󰆴 löschen", tooltip_text="In den Papierkorb", action_name="win.delete",
                                  focus_on_click=False)
        self.del_btn.full_label = "󰆴 löschen"
        self.del_btn.add_css_class("tbtn")
        self.del_btn.add_css_class("danger")
        acts.append(self.del_btn)
        self.restore_btn = Gtk.Button(label="󰦛 wiederherstellen", visible=False, focus_on_click=False)
        self.restore_btn.add_css_class("tbtn")
        self.restore_btn.connect("clicked", lambda *_: self.restore_note())
        acts.append(self.restore_btn)
        self.purge_btn = Gtk.Button(label="󰩹 endgültig löschen", visible=False, focus_on_click=False)
        self.purge_btn.add_css_class("tbtn")
        self.purge_btn.add_css_class("danger")
        self.purge_btn.connect("clicked", lambda *_: self.purge_note())
        acts.append(self.purge_btn)
        self.note_title_row.append(acts)
        return ed

    # ================= Schlagwörter, Farbe, Mehr =================
    def make_label_button(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, width_request=260)
        head = Gtk.Label(label="SCHLAGWÖRTER", xalign=0)
        head.add_css_class("wpop-head")
        box.append(head)
        # Eingabe: „# name“ + Knopf (Enter, Komma oder ＋ fügt hinzu; beim Schließen wird Getipptes übernommen)
        row = Gtk.Box(spacing=4)
        row.add_css_class("lbl-row")
        row.append(ch.label("#", "accent", "lbl-hash"))
        self.label_entry = Gtk.Entry(placeholder_text="schlagwort", hexpand=True, width_chars=14)
        self.label_entry.add_css_class("tsearch")
        self.label_entry.connect("activate", lambda e: self.add_label(e.get_text()))
        self.label_entry.connect("changed", self.on_label_typed)
        row.append(self.label_entry)
        addb = ch.button("󰐕", "Schlagwort hinzufügen (Enter)", callback=lambda: self.add_label(self.label_entry.get_text()))
        row.append(addb)
        box.append(row)
        self.label_mine = Gtk.Box()           # WrapLayout statt FlowBox: FlowBox macht Spalten so breit wie das
        self.label_mine.set_layout_manager(wr.WrapLayout(spacing=6, row_spacing=6))   # längste Schlagwort
        self.label_mine.add_css_class("label-mine")
        box.append(self._wrap_width(self.label_mine))
        self.label_other_head = ch.label("vorschläge", "dim", "lbl-sub")
        box.append(self.label_other_head)
        self.label_flow = Gtk.Box()
        self.label_flow.set_layout_manager(wr.WrapLayout(spacing=6, row_spacing=6))
        self.label_flow.add_css_class("label-chips")
        box.append(self._wrap_width(self.label_flow))
        k = Gtk.EventControllerKey()          # Rücktaste im leeren Feld entfernt das letzte Schlagwort
        k.connect("key-pressed", self.on_label_key)
        self.label_entry.add_controller(k)
        hint = Gtk.Label(label="enter oder komma fügt hinzu · 󰅖 oder rücktaste entfernt · die liste filtert danach",
                         xalign=0, wrap=True, max_width_chars=34)
        hint.add_css_class("tpl-sub")
        box.append(hint)
        mb, pop = wr.popover_button("󰓹", "Schlagwörter vergeben – die Liste lässt sich danach filtern", box)
        mb.remove_css_class("wt")
        mb.add_css_class("pb"); mb.add_css_class("small")
        pop.connect("show", lambda *_: (self.label_entry.set_text(""), self.fill_label_popover(),
                                        GLib.idle_add(lambda: self.label_entry.grab_focus() and False)))
        pop.connect("closed", lambda *_: self.label_entry.get_text().strip() and self.add_label(self.label_entry.get_text()))
        self.label_pop = pop
        return mb

    @staticmethod
    def _wrap_width(flow, width=320):
        """FlowBox auf feste Breite begrenzen: sonst will sie alles in eine Zeile und das Popover wird riesig."""
        sc = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER, vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
                                propagate_natural_height=True, max_content_height=220, min_content_width=width)
        sc.set_child(flow)
        flow.connect("notify::visible", lambda f, _p: sc.set_visible(f.get_visible()))
        return sc

    def all_labels(self):
        """Schlagwörter aus allen drei Bereichen (gemeinsamer Wortschatz)."""
        out = set()
        for store in self.stores.values():
            out |= set(store.labels())
        return out

    def on_label_key(self, ctrl, keyval, code, state):
        if keyval != Gdk.KEY_BackSpace or self.label_entry.get_text() or not self.current:
            return False
        mine = list(self.current.get("labels", []))
        if mine:
            self.set_label(mine[-1], False)
            self.fill_label_popover()
        return True

    def on_label_typed(self, entry):
        text = entry.get_text()
        if "," in text:                     # Komma = fertig mit diesem Schlagwort
            parts = text.split(",")
            for p in parts[:-1]:
                self.add_label(p, refill=False)
            entry.set_text(parts[-1].lstrip())
            entry.set_position(-1)
            self.fill_label_popover()
            return
        self.fill_label_popover()

    def fill_label_popover(self):
        mine = list(self.current.get("labels", [])) if self.current else []
        q = self.label_entry.get_text().strip().lstrip("#").lower()
        for f in (self.label_mine, self.label_flow):
            while (c := f.get_first_child()):
                f.remove(c)
        for l in mine:
            # Chip = Name + eigenes ✕-Feld mit Trennlinie (vorher klebte das ✕ am Text im selben Knopf)
            chip = Gtk.Box(halign=Gtk.Align.START)
            chip.add_css_class("lchip")
            chip.append(Gtk.Label(label="#" + l, ellipsize=3, max_width_chars=22, tooltip_text="#" + l))
            x = Gtk.Button(label="󰅖", tooltip_text=f"„{l}“ entfernen", focus_on_click=False)
            x.add_css_class("lchip-x")
            x.connect("clicked", lambda _b, lab=l: (self.set_label(lab, False), self.fill_label_popover()))
            chip.append(x)
            self.label_mine.append(chip)
        self.label_mine.set_visible(bool(mine))
        others = sorted((l for l in self.all_labels() - set(mine) if q in l.lower()), key=str.lower)
        for l in others[:24]:
            b = Gtk.Button(label="#" + l, tooltip_text="Hinzufügen", focus_on_click=False)
            b.connect("clicked", lambda _b, lab=l: (self.set_label(lab, True), self.label_entry.set_text(""),
                                                    self.fill_label_popover()))
            self.label_flow.append(b)
        self.label_flow.set_visible(bool(others))
        self.label_other_head.set_visible(bool(others))

    def add_label(self, text, refill=True):
        text = " ".join(text.strip().lstrip("#").split())
        self.label_entry.set_text("")
        if not self.current:
            return
        if text:
            if is_empty(self.current):
                self.notify("Erst etwas schreiben, dann verschlagworten")
                return
            self.set_label(text, True)
        if refill:
            self.fill_label_popover()

    def set_label(self, label, on):
        n = self.current
        if not n:
            return
        labels = [l for l in n.get("labels", []) if l != label] + ([label] if on else [])
        n["labels"] = sorted(labels, key=str.lower)
        if not is_empty(n):
            self.store.save(n)
        self.update_label_btn()
        self.refresh_list()

    def update_label_btn(self):
        n = self.current
        labels = n.get("labels", []) if n else []
        lab = self.label_btn.get_child()
        lab.set_label("󰓹 " + ", ".join(labels) if labels and not self.compact else "󰓹")
        lab.set_ellipsize(3)
        lab.set_max_width_chars(18)

    def fill_label_chips(self):
        box = self.label_box
        while (c := box.get_first_child()):
            box.remove(c)
        labels = self.store.labels()
        if self.label_filter and self.label_filter not in labels:
            self.label_filter = None
        box.set_visible(bool(labels) and self.mode != "trash")
        if not labels:
            return
        for l in [None] + labels:
            b = Gtk.ToggleButton(label="Alle" if l is None else "#" + l, active=self.label_filter == l)
            b.connect("toggled", lambda btn, lab=l: btn.get_active() and self.set_label_filter(lab))
            box.append(b)

    def set_label_filter(self, label):
        if label == self.label_filter:
            return
        self.label_filter = label
        GLib.idle_add(lambda: (self.refresh_list(), False)[-1])

    def make_color_button(self):
        grid = Gtk.Grid(row_spacing=6, column_spacing=6)
        head = Gtk.Label(label="FARBE", xalign=0)
        head.add_css_class("wpop-head")
        grid.attach(head, 0, 0, 6, 1)
        self.color_dots = {}
        holder = {}
        for i, key in enumerate(COLORS):
            b = Gtk.Button(tooltip_text=COLOR_NAMES[key])
            if key == "default":      # Symbol genau in der Mitte des Punkts (eigenes Label, keine Innenabstände)
                b.set_child(ch.label("󰂭", "cd-none", xalign=0.5))
                b.get_child().set_halign(Gtk.Align.CENTER)
                b.get_child().set_valign(Gtk.Align.CENTER)
            b.add_css_class("color-dot")
            b.add_css_class("nc-" + key)
            b.connect("clicked", lambda _b, k=key: (holder["pop"].popdown(), self.set_color(k)))
            grid.attach(b, i % 6, 1 + i // 6, 1, 1)
            self.color_dots[key] = b
        mb, pop = wr.popover_button("󰏘", "Farbe der Notiz", grid)
        mb.remove_css_class("wt")
        mb.add_css_class("pb"); mb.add_css_class("small")
        holder["pop"] = pop
        return mb

    def set_color(self, key):
        n = self.current
        if not n:
            return
        n["color"] = key
        if not is_empty(n):
            self.store.save(n)
        self.apply_color()
        self.refresh_list()

    def apply_color(self):
        key = (self.current or {}).get("color", "default") if self.kind == "notes" else "default"
        for k in COLORS:
            self.editor_box.remove_css_class("nc-" + k)
            self.color_dots[k].remove_css_class("active")
        if key in COLORS:
            self.color_dots[key].add_css_class("active")
            if key != "default":
                self.editor_box.add_css_class("nc-" + key)

    def make_more_button(self):
        mb = Gtk.MenuButton(tooltip_text="Verlauf, Archiv, Ordner, Optionen …", can_focus=False)
        mb.set_child(Gtk.Label(label="󰇘 mehr"))
        mb.full_label = "󰇘 mehr"
        mb.add_css_class("pb"); mb.add_css_class("small")
        self.more_pop = Gtk.Popover(has_arrow=False)
        self.more_pop.add_css_class("file-menu")
        mb.set_popover(self.more_pop)
        self.more_btn = mb
        self.fill_more_menu()
        return mb

    def fill_more_menu(self):
        """„Mehr“-Menü im Stil des Datei-Menüs (Verlauf, Archiv, Ordner, Teilen)."""
        if not getattr(self, "more_pop", None):
            return
        entries = [(None, (("󰋚", "Versionsverlauf …", "strg+umschalt+h", "win.history"),
                           ("󰀼", "Aus dem Archiv holen", "", "win.archive") if self.mode == "archive" else
                           ("󰀼", "Archivieren", "strg+umschalt+a", "win.archive")))]
        if self.use_folders():
            cur = (self.current or {}).get("folder") or ""
            items = [("●" if f == cur else "󰉋", f, "", f"win.move-folder::{f}", True) for f in self.folder_names()]
            items.append(("●" if not cur else "󰉖", "Kein Ordner", "", "win.move-folder::"))
            items.append(("󰉗", "Neuer Ordner …", "", "win.new-folder-move"))
            entries.append(("In Ordner verschieben", tuple(items)))
        if self.kind == "notes" and self.mode == "notes":
            entries.append(("Aufräumen", (("󰃢", "Notiz jetzt aufräumen", "", "win.tidy"),)))
        on = lambda b: ("󰄲" if b else "󰄱")
        state = lambda b: "an" if b else "aus"
        opts = []
        if self.kind in ("notes", "docs"):
            for key, text in (("markdown", "Markdown beim Tippen"),
                              ("auto_lists", "Listen automatisch fortsetzen") if self.kind == "notes" else (None, None),
                              ("typo", "„Typografie“ – … → ⇒"), ("autocap", "Satzanfang groß"),
                              ("smart", "Smarte Korrekturen (SChreibstift → Schreibstift)")):
                if key:
                    v = self.opt_value(key)
                    opts.append((on(v), text, state(v), f"win.opt::{key}", key == "typo"))
        v = self.opt_value("typewriter")
        opts.append((on(v), "Mitscrollen (halbe Seite Luft)", state(v), "win.opt::typewriter"))
        if self.kind != "latex":
            v = self.spell_on()
            opts.append((on(v), "Rechtschreibung", state(v), "win.opt::spell"))
        entries.append(("Optionen", tuple(opts)))
        wr.file_menu(entries, sub=self.display_title(self.current) if self.current else "", title="Mehr",
                     pop=self.more_pop)

    def opt_value(self, key):
        import autofmt
        if key in autofmt.DEFAULTS:
            return autofmt.opt(self.prefs, key)
        if key == "spell":
            return self.spell_on()
        return self.prefs.get(key, True)

    def toggle_opt(self, key):
        import autofmt
        v = not self.opt_value(key)
        if key in autofmt.DEFAULTS:
            autofmt.set_opt(self.prefs, key, v)
        elif key == "spell":
            self.spell_btns[0].set_active(v)            # schaltet alle Knöpfe + speichert
            v = self.spell_on()
        else:
            self.prefs[key] = v
            if key == "markdown":
                self.prefs.setdefault("writer", {})["markdown"] = v
        self.save_prefs()
        self.apply_typewriter()
        self.fill_more_menu()
        self.writer.sync_flowbar()
        names = {"markdown": "Markdown beim Tippen", "auto_lists": "Listen fortsetzen", "typo": "Typografie",
                 "autocap": "Satzanfang groß", "typewriter": "Mitscrollen", "spell": "Rechtschreibung",
                 "smart": "Smarte Korrekturen"}
        self.notify(f"{names.get(key, key)}: {'an' if v else 'aus'}")


    def on_doc_view(self, flow):
        """Words-Ansicht (seiten/fließend) gehört zum Dokument."""
        n = self.current
        if n and self.docs:
            n["view"] = "flow" if flow else "page"
            if not is_empty(n):
                self.store.save(n, touch=False)
        self.save_prefs()

    def apply_typewriter(self):
        for f in getattr(self, "follows", []):
            f.update_extra()

    def tidy_note(self):
        import autofmt
        if self.kind != "notes" or not self.current or self.mode != "notes":
            return
        self.note_checkpoint()
        n = autofmt.tidy(self.text.get_buffer())
        self.note_after_format()
        self.notify(f"Aufgeräumt – {n} Stellen" if n else "Schon aufgeräumt")

    def make_share_button(self):
        mb = Gtk.MenuButton(tooltip_text="Teilen, exportieren, umwandeln", can_focus=False)
        mb.set_child(Gtk.Label(label="󰐨 teilen"))
        mb.full_label = "󰐨 teilen"
        mb.add_css_class("pb"); mb.add_css_class("small")
        self.share_pop = Gtk.Popover(has_arrow=False)
        self.share_pop.add_css_class("file-menu")
        mb.set_popover(self.share_pop)
        self.share_pop.connect("show", lambda *_: self.fill_share_menu())
        return mb

    def export_pinned(self):
        return self.prefs.get("export_pinned") or list(xp.DEFAULT_PINNED)

    def toggle_export_pin(self, fmt):
        pins = list(self.export_pinned())
        if fmt in pins:
            pins.remove(fmt)
        else:
            pins.append(fmt)
        self.prefs["export_pinned"] = pins
        self.save_prefs()
        self.fill_share_menu()

    def fill_share_menu(self):
        """„Teilen“: weitergeben, als Datei speichern (angeheftete Formate oben) + in einen anderen Bereich umwandeln
        (das Original bleibt). Rechtsklick auf ein Format heftet es an bzw. löst es."""
        entries = [("Weitergeben", (("󰆏", "Als Text kopieren", "", "win.share-copy"),
                                    ("󰇮", "Per E-Mail senden …", "", "win.share-mail"),
                                    ("󰠮", "Für Freunde mit notist (.notes) …", "", "win.share-bundle")))]
        pins = [f for f in self.export_pinned() if f in xp.FORMATS and self.kind in xp.FORMATS[f][3]]
        rest = [f for f in xp.FORMATS if f not in pins and self.kind in xp.FORMATS[f][3]]

        def item(f):
            icon, name, ext, _k = xp.FORMATS[f]
            return (icon, name, ("󰐃 " if f in pins else "") + ext, f"win.export-as::{f}")
        entries.append(("Als Datei speichern · rechtsklick heftet an", tuple(item(f) for f in pins)))
        if rest:
            entries.append(("Weitere Formate", tuple(item(f) for f in rest)))
        conv = []
        if self.kind in ("notes", "docs"):
            conv.append(("Σ", "In LaTeX umwandeln", "", "win.to-latex"))
        if self.kind in ("notes", "latex"):
            conv.append(("󰈬", "In Words umwandeln", "", "win.to-words"))
        if conv:
            entries.append(("Umwandeln (Original bleibt)", tuple(conv)))
        wr.file_menu(entries, sub=self.display_title(self.current) if self.current else "", title="Teilen",
                     pop=self.share_pop)

        def walk(w):
            if isinstance(w, Gtk.Button) and (w.get_action_name() or "") == "win.export-as":
                fmt = w.get_action_target_value().get_string()
                g = Gtk.GestureClick(button=3)
                g.connect("pressed", lambda *_a, f=fmt: (self.share_pop.popdown(), self.toggle_export_pin(f)))
                w.add_controller(g)
                lp = Gtk.GestureLongPress(touch_only=True)
                lp.connect("pressed", lambda *_a, f=fmt: (self.share_pop.popdown(), self.toggle_export_pin(f)))
                w.add_controller(lp)
            c = w.get_first_child()
            while c is not None:
                walk(c)
                c = c.get_next_sibling()
        walk(self.share_pop.get_child())

    # ================= Teilen =================
    def share_copy(self):
        n = self.current
        if not n:
            return
        self.flush(force=True)
        if self.docs:
            text = df.to_markdown(self.writer.to_model())
        elif self.tex:
            text = share.plain(n, self.kind)
        else:
            text = md.from_note(n["text"], n.get("rich"), n["title"], n.get("images"))
        self.win.get_clipboard().set(text)
        self.notify("In die Zwischenablage kopiert" + ("" if self.tex else " (als Markdown)"))

    def share_export_temp(self):
        """Eintrag als passende Datei in einen temporären Ordner schreiben → Pfad."""
        n = self.current
        self.flush(force=True)
        name = share.safe_name(self.display_title(n))
        d = share.temp_dir()
        if self.docs:
            import render
            path = os.path.join(d, name + ".pdf")
            render.write_pdf(self.writer.to_model(), path, n["title"], self.writer.page)
        elif self.tex:
            pdf = self.latex.pdf_path()
            path = os.path.join(d, name + (".pdf" if pdf else ".tex"))
            if pdf:
                import shutil as _sh
                _sh.copyfile(pdf, path)
            else:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(self.latex.text())
        else:
            path = os.path.join(d, name + ".md")
            with open(path, "w", encoding="utf-8") as f:
                f.write(md.from_note(n["text"], n.get("rich"), n["title"], n.get("images")))
        return path

    def share_mail(self):
        if not self.current:
            return
        try:
            path = self.share_export_temp()
        except Exception as e:  # noqa: BLE001
            self.notify(f"Konnte die Datei nicht erstellen: {e}")
            return
        if share.email(path, self.display_title(self.current)):
            self.notify(f"Mailprogramm geöffnet – {os.path.basename(path)} hängt an")
        else:
            Gio.AppInfo.launch_default_for_uri(Gio.File.new_for_path(os.path.dirname(path)).get_uri(), None)
            self.notify("Kein Mailprogramm gefunden – Ordner mit der Datei geöffnet")

    def share_file(self):
        """Ohne Formatwahl: das erste angeheftete Format dieses Bereichs."""
        pins = [f for f in self.export_pinned() if f in xp.FORMATS and self.kind in xp.FORMATS[f][3]]
        self.export_dialog(pins[0] if pins else ("tex" if self.tex else "md"))

    def share_bundle(self):
        n = self.current
        if not n:
            return
        self.flush(force=True)
        if self.tex:
            self.latex.save_files()
        data = share.bundle(n, self.kind)
        dlg = Gtk.FileDialog(title="Für notist-Freunde speichern",
                             initial_name=share.safe_name(self.display_title(n)) + ".notes")

        def done(d, res):
            try:
                with open(d.save_finish(res).get_path(), "w", encoding="utf-8") as f:
                    f.write(data)
                self.notify("Gespeichert – Freunde öffnen die Datei einfach in notist (Öffnen oder hineinziehen)")
            except (GLib.Error, OSError):
                pass
        dlg.save(self.win, None, done)

    def import_bundle(self, path):
        try:
            kind, n, files = share.read_bundle(path)
        except (OSError, ValueError, KeyError) as e:
            self.notify(f"Konnte {os.path.basename(path)} nicht öffnen: {e}")
            return
        if kind != self.kind:
            self.set_kind(kind)
        self.flush()
        self.store.notes[n["id"]] = n
        self.store.save(n)
        if files:
            share.write_files(n["id"], files)
        self.give_file(n, kind)
        self.search.set_text("")
        self.select(n["id"])
        self.notify(f"„{self.display_title(n)}“ übernommen")

    def jump_to(self, kind, nid):
        self.set_kind(kind)
        self.select(nid)

    # ================= Bilder in Notizen =================
    IMG_SIZES = (("Klein", 180), ("Mittel", 320), ("Groß", 520))

    def note_image_width(self, info):
        maxw = max(120, self.text.get_width() - 30) if self.text.get_width() > 0 else 520
        return min(info.get("w") or 320, maxw)

    def insert_note_image(self, info, at=None):
        try:
            data = base64.b64decode(info["img"])
            iw, ih = df.image_size(data)
            w = self.note_image_width(info) if info.get("w") else min(iw, 320)
            h = ih * w / iw if iw else w
            tex = wr.pixel_texture(data, w, h)
        except (GLib.Error, KeyError, ValueError, ZeroDivisionError, TypeError):
            return False
        info = dict(info, w=round(w))
        buf = self.text.get_buffer()
        it = at or buf.get_iter_at_mark(buf.get_insert())
        self.note_images[tex] = info
        buf.insert_paintable(it, tex)
        return True

    def add_note_image_bytes(self, data):
        if self.mode == "trash" or not self.current:
            return
        info = {"img": base64.b64encode(data).decode(), "mime": df.sniff_mime(data) or "image/png", "w": 0}
        buf = self.text.get_buffer()
        it = buf.get_iter_at_mark(buf.get_insert())
        if not it.starts_line():
            buf.insert(it, "\n")
        if self.insert_note_image(info):
            buf.insert_at_cursor("\n")
            self.on_edit()

    def pick_note_image(self):
        dlg = Gtk.FileDialog(title="Bild einfügen")
        f = Gtk.FileFilter()
        f.set_name("Bilder")
        f.add_mime_type("image/*")
        store = Gio.ListStore.new(Gtk.FileFilter)
        store.append(f)
        dlg.set_filters(store)

        def done(d, res):
            try:
                path = d.open_finish(res).get_path()
                with open(path, "rb") as fh:
                    self.add_note_image_bytes(fh.read())
            except (GLib.Error, OSError):
                pass
        dlg.open(self.win, None, done)

    def on_note_paste(self, view):
        clip = view.get_clipboard()
        formats = clip.get_formats()
        if formats.contain_gtype(GObject.TYPE_STRING) and self.prefs.get("markdown", True):
            GObject.signal_stop_emission_by_name(view, "paste-clipboard")

            def got(c, res):                          # Markdown erkennen und formatiert einfügen
                try:
                    text = c.read_text_finish(res)
                except GLib.Error:
                    return
                if text:
                    self.insert_markdown(text, convert=md.looks_like_markdown(text))
            clip.read_text_async(None, got)
            return
        if formats.contain_gtype(GObject.TYPE_STRING) or not formats.contain_gtype(Gdk.Texture):
            return                                    # normaler Text: GTK macht das selbst
        GObject.signal_stop_emission_by_name(view, "paste-clipboard")

        def done(c, res):
            try:
                tex = c.read_texture_finish(res)
            except GLib.Error:
                return
            self.add_note_image_bytes(tex.save_to_png_bytes().get_data())
        clip.read_texture_async(None, done)

    def insert_markdown(self, text, convert=True):
        """Text an der Schreibmarke einfügen (ersetzt die Markierung); Markdown wird zu Formatierung."""
        buf = self.text.get_buffer()
        rich = []
        if convert:
            text, rich = md.to_note(text)
        self.note_checkpoint()
        buf.begin_user_action()
        if buf.get_has_selection():
            buf.delete_selection(True, True)
        it = buf.get_iter_at_mark(buf.get_insert())
        off = it.get_offset()
        if convert:
            self._loading = True                      # aktive Formatierung nicht auf den Text übertragen
        buf.insert(it, text)
        self._loading = False
        if convert:
            s, e = buf.get_iter_at_offset(off), buf.get_iter_at_offset(off + len(text))
            for tag in self.our_tags():
                buf.remove_tag(tag, s, e)
            for a, b, name in rich:
                tag = self.font_tag(name[5:]) if name.startswith("font:") else buf.get_tag_table().lookup(name)
                if tag:
                    buf.apply_tag(tag, buf.get_iter_at_offset(off + a), buf.get_iter_at_offset(off + b))
        buf.end_user_action()
        self.text.scroll_mark_onscreen(buf.get_insert())
        self.on_edit()
        self.note_after_format()
        self.style_checks()
        if convert and rich:
            self.notify("Markdown übernommen – Strg+Z macht es rückgängig")

    MD_LIVE = (("bold", r"(\*\*|__)(?=\S)([^*_\n]+?)(?<=\S)\1$"),
               ("strike", r"(~~)(?=\S)([^~\n]+?)(?<=\S)~~$"),
               ("code", r"(`)([^`\n]+)`$"),
               ("italic", r"(?<![*\w])(\*)(?=[^\s*])([^*\n]+?)(?<=\S)\*$"),
               ("italic", r"(?<![_\w])(_)(?=[^\s_])([^_\n]+?)(?<=\S)_$"))

    def md_live(self, line):
        """Beim Tippen: **fett**, *kursiv*, _kursiv_, ~~durch~~, `code` werden sofort formatiert."""
        buf = self.text.get_buffer()
        cur = buf.get_iter_at_mark(buf.get_insert())
        if cur.get_line() != line:
            return False
        ok, ls = buf.get_iter_at_line(line)
        before = buf.get_text(ls, cur, False)
        for style, pat in self.MD_LIVE:
            m = re.search(pat, before)
            if not m:
                continue
            mk = len(m.group(1))
            start = ls.get_offset() + m.start()
            inner = len(m.group(2))
            self.note_checkpoint()
            buf.begin_user_action()
            self._loading = True
            e = buf.get_iter_at_offset(start + mk + inner)          # schließende Zeichen
            buf.delete(e, buf.get_iter_at_offset(start + mk + inner + mk))
            s = buf.get_iter_at_offset(start)                         # öffnende Zeichen
            buf.delete(s, buf.get_iter_at_offset(start + mk))
            self._loading = False
            tag = self.font_tag(df.MONO_FONT) if style == "code" else buf.get_tag_table().lookup(style)
            a, b = buf.get_iter_at_offset(start), buf.get_iter_at_offset(start + inner)
            buf.apply_tag(tag, a, b)
            buf.end_user_action()
            buf.place_cursor(b)
            # weiter tippen ohne die Formatierung (wie in anderen Markdown-Editoren)
            self.active = {n for n in self.active if n != tag.props.name}
            self.on_edit()
            self.note_after_format()
            self.update_fmt_buttons()
            return False
        return False

    def on_note_drop(self, target, value, x, y):
        ok = False
        for f in value.get_files():
            p = f.get_path()
            if p and os.path.splitext(p)[1].lower() in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"):
                try:
                    with open(p, "rb") as fh:
                        self.add_note_image_bytes(fh.read())
                    ok = True
                except OSError:
                    pass
        return ok

    def collect_note_images(self):
        """Bilder UND Tabellen in Reihenfolge der Platzhalter (U+FFFC) im Text; Tabellen = {"table": {rows, style}}."""
        buf = self.text.get_buffer()
        out = []
        text = buf.get_slice(buf.get_start_iter(), buf.get_end_iter(), True)
        for i, ch in enumerate(text):
            if ch == "\ufffc":
                it = buf.get_iter_at_offset(i)
                tex = it.get_paintable()
                if tex in self.note_images:
                    out.append(self.note_images[tex])
                elif (blk := self.note_tables.get(it.get_child_anchor())) is not None:
                    out.append({"table": {"rows": blk.rows(), "style": blk.model_style()}})
        return out

    # ================= Tabellen in Notizen =================
    def note_table_width(self):
        """Breite aus dem Fenster statt aus dem Textfeld: dessen Breite wächst sonst mit der Tabelle mit (Rückkopplung)."""
        avail = self.body.get_width() - (self.body.get_position() if self.body.get_start_child() else 0)
        return max(200, avail - 64) if avail > 0 else 560

    def insert_note_table(self, rows, style=None, at=None):
        buf = self.text.get_buffer()
        it = at or buf.get_iter_at_mark(buf.get_insert())
        anchor = buf.create_child_anchor(it)
        blk = wr.TableBlock(self.note_tbl_host, rows, style)
        blk.set_width(self.note_table_width())
        self.text.add_child_at_anchor(blk, anchor)
        self.note_tables[anchor] = blk
        return blk

    def ask_note_table(self, btn):
        if self.mode == "trash" or not self.current or self.docs or self.tex:
            return
        if getattr(self, "_tsize", None) is None:
            pop = wr.close_outside(wr.ist_pop(Gtk.Popover(autohide=False, position=Gtk.PositionType.BOTTOM)))
            pop.set_child(wr.TableSizePicker(self._note_table_picked))
            pop.set_parent(btn)
            self._tsize = pop
        self._tsize.get_child().reset()
        self._tsize.popup()

    def _note_table_picked(self, rows, cols):
        self._tsize.popdown()
        self.text.grab_focus()
        buf = self.text.get_buffer()
        it = buf.get_iter_at_mark(buf.get_insert())
        if not it.starts_line():
            buf.insert(it, "\n")
        blk = self.insert_note_table([[""] * cols for _ in range(rows)])
        buf.insert_at_cursor("\n")
        self.on_edit()
        GLib.idle_add(lambda: blk.cells[0][0].tv.grab_focus() and False)

    def note_table_changed(self):
        if self._loading:
            return
        self.on_edit()
        self.note_changed()

    def remove_note_table(self, w):
        # wie writer.remove_block: erst ausblenden, dann löschen (Absturz, wenn das Widget unter dem Zeiger mitten im Löschen verschwindet)
        w.drop_design()
        self.text.grab_focus()
        w.set_visible(False)

        def go():
            buf = self.text.get_buffer()
            for a, x in list(self.note_tables.items()):
                if x is w:
                    r = buf.get_iter_at_child_anchor(a)
                    it = r[1] if isinstance(r, tuple) else r
                    end = it.copy()
                    end.forward_char()
                    buf.delete(it, end)
                    self.note_tables.pop(a, None)
            self.on_edit()
            return False
        GLib.timeout_add(50, go)

    def relayout_note_tables(self):
        w = self.note_table_width()
        for blk in self.note_tables.values():
            if abs(blk.width - w) > 1:
                blk.set_width(w)

    def _tbl_tick(self, *_):
        w = self.note_table_width()
        if w != getattr(self, "_tbl_w", 0):
            self._tbl_w = w
            self.relayout_note_tables()
        return GLib.SOURCE_CONTINUE

    def image_menu_at(self, x, y):
        bx, by = self.text.window_to_buffer_coords(Gtk.TextWindowType.WIDGET, int(x), int(y))
        ok, it = self.text.get_iter_at_location(bx, by)
        if not ok:
            return False
        tex = it.get_paintable()
        if tex not in self.note_images:
            return False
        off = it.get_offset()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        head = Gtk.Label(label="BILD", xalign=0)
        head.add_css_class("wpop-head")
        box.append(head)
        pop = wr.ist_pop(Gtk.Popover())
        pop.set_child(box)
        pop.set_parent(self.text)
        r = self.text.get_iter_location(it)
        wx, wy = self.text.buffer_to_window_coords(Gtk.TextWindowType.WIDGET, r.x, r.y)
        rect = Gdk.Rectangle()
        rect.x, rect.y, rect.width, rect.height = wx, wy, max(1, r.width), max(1, r.height)
        pop.set_pointing_to(rect)

        def resize(w):
            pop.popdown()
            buf = self.text.get_buffer()
            s, e = buf.get_iter_at_offset(off), buf.get_iter_at_offset(off + 1)
            info = dict(self.note_images.pop(tex, {}), w=w)
            buf.delete(s, e)
            self.insert_note_image(info, buf.get_iter_at_offset(off))
            self.on_edit()

        def remove():
            pop.popdown()
            buf = self.text.get_buffer()
            self.note_images.pop(tex, None)
            buf.delete(buf.get_iter_at_offset(off), buf.get_iter_at_offset(off + 1))
            self.on_edit()

        def save_as():
            pop.popdown()
            info = self.note_images.get(tex, {})
            ext = {"image/jpeg": "jpg", "image/gif": "gif", "image/webp": "webp"}.get(info.get("mime"), "png")
            dlg = Gtk.FileDialog(title="Bild speichern", initial_name=f"bild.{ext}")

            def done(d, res):
                try:
                    with open(d.save_finish(res).get_path(), "wb") as fh:
                        fh.write(base64.b64decode(info["img"]))
                except (GLib.Error, OSError, KeyError):
                    pass
            dlg.save(self.win, None, done)
        for label, w in self.IMG_SIZES:
            b = Gtk.Button(label=f"{label} ({w} px)")
            b.add_css_class("wt")
            b.connect("clicked", lambda *_, w=w: resize(w))
            box.append(b)
        for label, cb in (("󰆓  Speichern unter …", save_as), ("󰆴  Entfernen", remove)):
            b = Gtk.Button(label=label)
            b.add_css_class("wt")
            b.connect("clicked", lambda *_, c=cb: c())
            box.append(b)
        pop.connect("closed", lambda p: GLib.idle_add(lambda: p.unparent() or False))
        pop.popup()
        return True

    # ================= Erinnerungen =================
    def make_reminder_button(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        head = Gtk.Label(label="ERINNERUNG", xalign=0)
        head.add_css_class("wpop-head")
        box.append(head)
        self.rem_now = Gtk.Label(xalign=0)
        self.rem_now.add_css_class("rem-now")
        box.append(self.rem_now)
        self.rem_quick = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.append(self.rem_quick)
        import minical
        self.rem_cal = minical.MiniCal()
        box.append(self.rem_cal)
        tr = Gtk.Box(spacing=6)
        tr.append(ch.label("uhrzeit", "dim"))
        self.rem_h = Gtk.SpinButton.new_with_range(0, 23, 1)
        self.rem_m = Gtk.SpinButton.new_with_range(0, 59, 5)
        for sp in (self.rem_h, self.rem_m):
            sp.set_wrap(True)
            sp.add_css_class("wt")
            sp.connect("output", lambda s: (s.set_text(f"{int(s.get_value()):02d}"), True)[-1])
        tr.append(self.rem_h)
        tr.append(Gtk.Label(label=":"))
        tr.append(self.rem_m)
        box.append(tr)
        row = Gtk.Box(spacing=6)
        setb = ch.button("󰄬 setzen", "Erinnerung zu Tag und Uhrzeit setzen")
        setb.add_css_class("accent-btn")
        clr = ch.button("entfernen", "Erinnerung löschen", danger=True)
        row.append(setb)
        row.append(clr)
        box.append(row)
        info = Gtk.Label(wrap=True, xalign=0, max_width_chars=30,
                         label="Kommt als Benachrichtigung – auch wenn notist geschlossen ist." if rem.has_systemd()
                         else "Kommt als Benachrichtigung, solange notist läuft.")
        info.add_css_class("tpl-sub")
        box.append(info)
        mb, pop = wr.popover_button("󰂚", "Erinnerung", box)
        mb.remove_css_class("wt")
        mb.add_css_class("pb"); mb.add_css_class("small")
        self.rem_pop = pop
        pop.connect("show", lambda *_: self.fill_reminder_popover())

        def custom(*_):
            d = self.rem_cal.get_date()
            dt = datetime.datetime(d.year, d.month, d.day,
                                   int(self.rem_h.get_value()), int(self.rem_m.get_value()))
            self.set_reminder(dt)
        setb.connect("clicked", custom)
        clr.connect("clicked", lambda *_: self.set_reminder(None))
        return mb

    def fill_reminder_popover(self):
        n = self.current or {}
        dt = rem.parse(n.get("reminder"))
        self.rem_now.set_label(("󰂚 " + rem.nice(dt) + (" (erledigt)" if n.get("reminder_done") else ""))
                               if dt else "Keine Erinnerung gesetzt")
        q = self.rem_quick
        while (c := q.get_first_child()):
            q.remove(c)
        for label, when in rem.quick_choices():
            b = Gtk.Button(label=f"{label}  ·  {rem.nice(when)}")
            b.add_css_class("wt")
            b.get_child().set_xalign(0)
            b.connect("clicked", lambda *_, w=when: self.set_reminder(w))
            q.append(b)
        base = dt or datetime.datetime.now() + datetime.timedelta(hours=1)
        self.rem_cal.select(base.date())
        self.rem_h.set_value(base.hour)
        self.rem_m.set_value(base.minute - base.minute % 5)

    def set_reminder(self, dt):
        self.rem_pop.popdown()
        n = self.current
        if not n or is_empty(n):
            self.notify("Erst etwas schreiben, dann erinnern")
            return
        if dt and dt <= datetime.datetime.now():
            self.notify("Dieser Zeitpunkt liegt in der Vergangenheit")
            return
        n["reminder"] = dt.isoformat(timespec="minutes") if dt else None
        n["reminder_done"] = False
        self.store.save(n)
        n["reminder_systemd"] = rem.schedule(n, os.path.join(HERE, "notes.py"))
        self.store.save(n)
        self.update_rem_btn()
        self.refresh_list()
        self.notify(f"Erinnerung: {rem.nice(dt)}" if dt else "Erinnerung entfernt")

    def update_rem_btn(self):
        n = self.current or {}
        dt = rem.parse(n.get("reminder"))
        on = dt and not n.get("reminder_done")
        self.rem_btn.get_child().set_label("󰂚 " + rem.nice(dt) if on and not self.compact else "󰂚")
        (self.rem_btn.add_css_class if on else self.rem_btn.remove_css_class)("active-rem")

    def check_reminders(self):
        now = datetime.datetime.now()
        for kind, store in self.stores.items():
            for n in list(store.notes.values()):
                dt = rem.parse(n.get("reminder"))
                if not dt or n.get("reminder_done") or n["trashed"] or dt > now:
                    continue
                if n.get("reminder_systemd") and (now - dt).total_seconds() < 180:
                    continue                          # das erledigt gleich der systemd-Timer
                self.fire_reminder(n["id"])
        return True

    def fire_reminder(self, nid):
        disk = rem.mark_done(nid)                 # erledigt markieren (verhindert doppelte Meldungen)
        n = None
        for store in self.stores.values():
            if nid in store.notes:
                n = store.notes[nid]
                break
        if n is None or (disk is None and n.get("reminder_done")):
            return
        n["reminder_done"] = True
        title = self.display_title(n, next(k for k, s in self.stores.items() if nid in s.notes))
        body = " ".join(n["text"].replace("\ufffc", "").split())[:140]
        note = Gio.Notification.new(f"󰂚 {title}")
        note.set_body(body or "Erinnerung")
        note.set_default_action(f"app.open-note::{nid}")
        note.add_button("Öffnen", f"app.open-note::{nid}")
        self.send_notification(f"rem-{nid}", note)
        if self.current is n:
            self.update_rem_btn()
        self.refresh_list()

    def open_note(self, nid):
        self.do_activate()
        for kind, store in self.stores.items():
            if nid in store.notes:
                n = store.notes[nid]
                if n["trashed"]:
                    return
                if self.mode != ("archive" if n.get("archived") else "notes"):
                    if kind != self.kind:
                        self.set_kind(kind)
                    self.set_mode("archive" if n.get("archived") else "notes")
                self.jump_to(kind, nid)
                return

    # ================= Umwandeln Words ↔ LaTeX =================
    def convert_current(self, target):
        import convert
        n = self.current
        if not n or self.mode == "trash" or target == self.kind:
            return
        self.flush(force=True)
        title = self.display_title(n)
        if self.kind == "notes":                  # Notiz → Markdown → Blöcke (Formatierung, Listen bleiben)
            blocks = df.markdown_blocks(md.from_note(n["text"], n.get("rich"), "", n.get("images"))) or [df.para()]
        if target == "latex":
            if self.kind != "notes":
                blocks = self.writer.to_model()
            new = self.stores["latex"].create()
            img_dir = os.path.join(lx.FILES, new["id"])
            new["text"] = convert.blocks_to_latex(blocks, n["title"].strip() or title, self.writer.page, img_dir)
        elif self.kind == "notes":
            new = self.stores["docs"].create()
            new["blocks"] = blocks
            new["text"] = df.plain_text(blocks)
            new["media"] = df.has_content(blocks)
        else:
            img_dir = os.path.join(lx.FILES, n["id"])
            self.latex.save_files()
            src = self.latex.text()
            # \input-Dateien einfügen, damit nichts verloren geht
            for m in re.finditer(r"\\(?:input|include)\{([^}]+)\}", src):
                p = os.path.join(img_dir, m.group(1) if m.group(1).endswith(".tex") else m.group(1) + ".tex")
                try:
                    src = src.replace(m.group(0), open(p, encoding="utf-8").read())
                except OSError:
                    pass
            blocks, tex_title = convert.latex_to_blocks(src, img_dir)
            new = self.stores["docs"].create()
            new["blocks"] = blocks
            new["text"] = df.plain_text(blocks)
            new["media"] = df.has_content(blocks)
            title = tex_title or title
        new["title"] = f"{title} ({'LaTeX' if target == 'latex' else 'Words'})"
        new["labels"] = list(n.get("labels", []))
        if n.get("folder"):
            new["folder"] = n["folder"]
        self.stores[target].save(new)
        self.give_file(new, target)
        self.set_kind(target)
        self.select(new["id"])
        self.notify("Umgewandelt – das Original bleibt unverändert" +
                    (". Formeln und eigene Befehle bitte kurz prüfen" if target == "docs" else ""))

    # ================= Archiv =================
    def toggle_archive(self):
        n = self.current
        if not n or self.mode == "trash":
            return
        self.flush(force=True)
        if is_empty(n):
            return
        n["archived"] = not n.get("archived")
        self.store.save(n)
        was_arch = not n["archived"]
        self.current = None
        rest = self.notes_for_mode()
        if rest:
            self.select(rest[0]["id"])
        else:
            self.refresh_list()
        self.notify("Aus dem Archiv geholt" if was_arch else "Archiviert – zu finden unter „Archiv“ links unten")

    # ================= Verlauf =================
    def show_history(self):
        n = self.current
        if not n or self.mode == "trash":
            return
        self.flush(force=True)
        versions = self.store.versions(n)
        win = Gtk.Window(title=f"Verlauf – {self.display_title(n)}", transient_for=self.win, default_width=860,
                         default_height=560)
        win.add_css_class("settings")
        win.add_css_class("pb-window")
        k = Gtk.EventControllerKey()
        k.connect("key-pressed", lambda c, kv, *_: kv == Gdk.KEY_Escape and (win.close() or True))
        win.add_controller(k)
        outer = Gtk.Box()
        import dialogs
        dialogs.chrome(win, win.get_title(), outer)
        side = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        side.add_css_class("settings-side")
        side.set_size_request(230, -1)
        lb = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
        lb.add_css_class("hist-list")
        sc = Gtk.ScrolledWindow(vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER)
        sc.set_child(lb)
        side.append(sc)
        outer.append(side)
        right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, hexpand=True)
        right.add_css_class("settings-page")
        head = Gtk.Label(xalign=0)
        head.add_css_class("set-h")
        right.append(head)
        prev = Gtk.TextView(editable=False, wrap_mode=Gtk.WrapMode.WORD_CHAR, cursor_visible=False,
                            monospace=self.tex)
        prev.add_css_class("hist-preview")
        psc = Gtk.ScrolledWindow(vexpand=True)
        psc.add_css_class("set-row")
        psc.set_child(prev)
        right.append(psc)
        btn = Gtk.Button(label="󰦛  Diese Version wiederherstellen", halign=Gtk.Align.START, sensitive=False)
        btn.add_css_class("pb")
        info = Gtk.Label(xalign=0, wrap=True,
                         label="Der aktuelle Stand wird vorher selbst als Version gesichert – nichts geht verloren.")
        info.add_css_class("set-sub")
        right.append(btn)
        right.append(info)
        outer.append(right)
        if not versions:
            head.set_label("Noch keine früheren Versionen")
            prev.get_buffer().set_text("notist legt beim Schreiben automatisch Versionen an "
                                       f"(höchstens alle {st.HISTORY_MINUTES} Minuten).")
        for when, path in versions:
            r = Gtk.ListBoxRow()
            r.path = path
            v = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            t = Gtk.Label(label=nice_date(when.isoformat()) + f"  ·  {when.astimezone():%H:%M}", xalign=0)
            t.add_css_class("hist-when")
            try:
                data = self.store.load_version(path)
                words = len(data.get("text", "").split())
            except (OSError, ValueError):
                data, words = {}, 0
            r.data = data
            i = Gtk.Label(label=f"{data.get('title') or self.display_title(data) if data else '?'} · {words} Wörter",
                          xalign=0, ellipsize=3)
            i.add_css_class("hist-info")
            v.append(t)
            v.append(i)
            r.set_child(v)
            lb.append(r)

        def selected(_lb, r):
            btn.set_sensitive(bool(r))
            if not r:
                return
            head.set_label(r.data.get("title") or "(ohne Titel)")
            prev.get_buffer().set_text(r.data.get("text", ""))
        lb.connect("row-selected", selected)

        def restore(*_):
            r = lb.get_selected_row()
            if r:
                self.restore_version(r.data)
                win.close()
        btn.connect("clicked", restore)
        if versions:
            lb.select_row(lb.get_row_at_index(0))
        win.present()

    def restore_version(self, data):
        n = self.current
        if not n:
            return
        self.store.snapshot(n, force=True)
        for key in ("title", "text", "rich", "blocks", "media", "labels", "color", "page", "images"):
            if key in data:
                n[key] = data[key]
            elif key in ("blocks", "rich", "images", "page"):
                n.pop(key, None)
        self.store.save(n)
        self.select(n["id"])
        self.notify("Version wiederhergestellt – die vorherige liegt im Verlauf")

    # ================= Einstellungen & Sicherung =================
    def open_settings(self, page=None):
        w = getattr(self, "_settings_win", None)
        if w and w.get_visible():
            w.present()
            return
        self._settings_win = setw.SettingsWindow(self, page)
        self._settings_win.present()

    # ================= Sprache je Dokument =================
    LANG_LABEL = {"de": "DE", "en": "EN"}

    def default_lang(self):
        lang = self.prefs.get("doc_lang")
        if lang in self.LANG_LABEL:
            return lang
        loc = (os.environ.get("LC_ALL") or os.environ.get("LANG") or "de").lower()
        return "en" if loc.startswith("en") else "de"

    def doc_lang(self, n=None):
        n = n or self.current
        lang = n.get("lang") if n else None
        return lang if lang in self.LANG_LABEL else self.default_lang()

    def set_doc_lang(self, lang):
        n = self.current
        if not n or lang not in self.LANG_LABEL or n.get("lang") == lang:
            return
        n["lang"] = lang
        self.stores[self.kind_of(n)].save(n, touch=False)
        self.apply_doc_lang()
        self.notify("Sprache: " + ("Deutsch" if lang == "de" else "Englisch"))

    def apply_doc_lang(self):
        """Sprache des offenen Dokuments: Rechtschreibung (nur dieses Wörterbuch, sonst die Einstellung),
        Anführungszeichen („…“ / “…”) und Anzeige im Chip."""
        import spell
        lang = self.doc_lang()
        have = spell.installed_langs()
        spell.set_langs([lang] if lang in have else self.prefs.get("spell_langs", list(spell.DEFAULT_LANGS)))
        for buf in (self.text.get_buffer(), self.writer.buf, *self.latex.bufs):
            buf.lang = lang
        if self.lang_btn.get_label() != self.LANG_LABEL[lang]:
            self.lang_btn.set_label(self.LANG_LABEL[lang])
        self.lang_btn.set_tooltip_text("Sprache dieses Dokuments: " + ("Deutsch" if lang == "de" else "Englisch") +
                                       " – steuert Rechtschreibung und Anführungszeichen (Klick wechselt)")
        for sc in (self.spell_notes, self.spell_docs, getattr(self.latex, "spell", None)):
            if sc:
                sc.queue(0)

    def set_spell_langs(self, langs):
        spell.set_langs(langs)
        self.save_prefs()
        for b in self.spell_btns:
            self.spell_tooltip(b)
        self.spell_notes.queue(0)
        self.spell_docs.queue(0)
        if getattr(self.latex, "spell", None):
            self.latex.spell.queue(0)

    def set_spell(self, on):
        for b in self.spell_btns:
            if b.get_active() != on:
                b.set_active(on)
        self.prefs["spell"] = on

    def maybe_backup(self):
        if backup.due(self.prefs):
            def done(path, err):
                if err:
                    self.notify(f"Sicherung fehlgeschlagen: {err}")
                self.save_prefs()
            backup.run_async(self.prefs, done)
        return True

    def restore_backup(self, path):
        self.flush(force=True)
        b = backup.defaults(self.prefs)
        try:
            backup.restore(path, os.path.expanduser(b["dir"]))
        except Exception as e:  # noqa: BLE001
            self.notify(f"Wiederherstellen fehlgeschlagen: {e}")
            return
        self.current = None
        for s in self.stores.values():
            s.load()
        self.last_sel = {}
        self.mode = "notes"
        self.apply_kind()
        self.notify("Sicherung wiederhergestellt – der vorherige Stand wurde selbst gesichert")

    # ================= Modus (Notizen / Dokumente) =================
    def set_kind(self, kind):
        if self.view != "home" and kind == self.kind and self.kind_btns[kind].get_active():
            return
        self.view = "kind"
        self.main_stack.set_visible_child_name("main")
        self.label_filter = None
        self.flush()
        self.remember_pos()
        if self.current and is_empty(self.current):
            self.drop_empty(self.current)
        if self.current:
            self.last_sel[self.kind] = self.current["id"]
        self.current = None
        self.kind = kind
        self.prefs["kind"] = kind
        self.save_prefs()
        self.search.set_text("")
        self.apply_kind()

    def apply_kind(self):
        docs = self.docs
        if not self.kind_btns[self.kind].get_active():
            self.kind_btns[self.kind].set_active(True)
        self.kind_stack.set_visible_child_name(self.kind)
        self.place_doc_actions()
        self.app_title.set_label(KINDS[self.kind][0])
        self.place_list()
        self.update_tabs()
        self.update_top_buttons()
        self.new_btn.set_tooltip_text(self.new_label() + " (Strg+N)")
        self.open_btn.set_tooltip_text("LaTeX-Datei (.tex) öffnen (Strg+O)" if self.tex else
                                       "DOCX, DOC, TXT, MD oder HTML öffnen (Strg+O)")
        self.mode = "notes"
        self.apply_trash_ui()
        self.refresh_list()
        visible = self.store.visible()
        want = self.last_sel.get(self.kind)
        if want and want in {n["id"] for n in visible}:
            self._auto_pos = True                 # Rückkehr per Moduswechsel → an die alte Stelle
            self.select(want)
        elif visible:
            self.select(visible[0]["id"])
        else:
            self.show_empty()
        self.update_status_ui()

    def place_doc_actions(self):
        """„anheften“/„löschen“ rechts in die Titelzeile des sichtbaren Bereichs hängen."""
        row = {"notes": self.note_title_row, "docs": self.writer.title_row, "latex": self.latex.title_row}[self.kind]
        if self.doc_actions.get_parent() is not row:
            if self.doc_actions.get_parent():
                self.doc_actions.get_parent().remove(self.doc_actions)
            row.append(self.doc_actions)

    # ================= Home: alle drei Bereiche auf einen Blick =================
    HOME_ROWS = 10

    def build_home(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.add_css_class("home")
        self.home_search = Gtk.SearchEntry(placeholder_text="in allen bereichen suchen (strg+f)",
                                           hexpand=True)
        self.home_search.add_css_class("tsearch")
        self.home_search.connect("search-changed", lambda *_: self.refresh_home())
        self.home_search.connect("activate", lambda *_: self.home_open_first())
        box.append(self.home_search)
        self.home_cols = Gtk.Box(spacing=12, homogeneous=True)
        self.home_panels = {}
        for i, kind in enumerate(KINDS, 1):
            panel = ch.Panel()
            panel.rows = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1, vexpand=True)
            panel.body.append(panel.rows)
            panel.more = ch.button("alle 󰁔", f"Alle {KINDS[kind][4]} anzeigen",
                                   callback=lambda k=kind: self.toggle_home_expand(k))
            fbtn = ch.button("󰉗 ordner", "Neuer Ordner in diesem Bereich")
            fbtn.connect("clicked", lambda b, k=kind: self.folder_prompt(b, None, kind=k))
            foot = ch.hbox(ch.button("󰐕 neu", self.new_label_for(kind), callback=lambda k=kind: self.home_new(k)),
                           fbtn, Gtk.Box(hexpand=True), panel.more, spacing=6)
            foot.set_margin_top(6)
            panel.body.append(foot)
            self.home_panels[kind] = panel
            self.home_cols.append(panel)
        box.append(self.home_cols)
        scroll = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER, vexpand=True, child=box)
        scroll.add_css_class("home-scroll")
        return scroll

    def new_label_for(self, kind):
        return {"notes": "Neue Notiz", "docs": "Neues Dokument", "latex": "Neues LaTeX-Dokument"}[kind]

    def leave_to_home(self):
        """Strg+W / Esc: aus dem geöffneten Eintrag zurück zur Übersicht (schließt nie das Fenster)."""
        if self.view != "home":
            self.go_home()
        elif self.home_expanded:
            self.toggle_home_expand(self.home_expanded)

    def on_win_key(self, ctrl, kv, code, state):
        if kv != Gdk.KEY_Escape or state & (Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SHIFT_MASK |
                                            Gdk.ModifierType.ALT_MASK):
            return False
        if self.view == "home" and not self.home_expanded:
            return False
        self.leave_to_home()
        return True

    # ================= Zurück-Navigation (Wischen, Maustaste) =================
    def nav_loc(self):
        if self.view == "home":
            return ("home", None)
        return (self.kind, self.current["id"] if self.current else None)

    def nav_note(self):
        """Nach einer Navigation: erst im Leerlauf festhalten, damit Zwischenschritte (Bereich wechseln →
        erste Notiz → gewünschte Notiz) nur einen Eintrag ergeben."""
        if self._nav_id is None and hasattr(self, "nav_back"):
            self._nav_id = GLib.idle_add(self.nav_commit)

    def nav_commit(self):
        self._nav_id = None
        loc = self.nav_loc()
        skip, self._nav_skip = self._nav_skip, False
        if loc == self.nav_cur:
            return False
        if loc[0] == "home":
            self.nav_back = []          # Home ist immer das Ende der Zurück-Kette
        elif self.nav_cur and not skip:
            if not self.nav_back or self.nav_back[-1] != self.nav_cur:
                self.nav_back.append(self.nav_cur)
                del self.nav_back[:-50]
        self.nav_cur = loc
        if loc[1]:                      # für die Zuletzt-Leiste links
            ch1 = rc.remember(self.prefs, loc[0], loc[1])
            allk = self.prefs.setdefault("recent_all", [])
            key = f"{loc[0]}:{loc[1]}"
            if not allk or allk[0] != key:
                if key in allk:
                    allk.remove(key)
                allk.insert(0, key)
                del allk[rc.KEEP:]
                ch1 = True
            if ch1:
                self.save_prefs()
        self.queue_recent()
        return False

    def _swipe_title(self, kind, nid):
        if kind == "home":
            return "home"
        n = self.stores[kind].notes.get(nid) if nid and kind in self.stores else None
        t = (n.get("title") or "").strip() if n else ""
        if not t and n:
            t = (n.get("text") or "").strip().split("\n")[0][:28]
        return t or KINDS.get(kind, (kind,))[0].lower()

    def swipe_where(self):
        """2fz-Vorschau: (schlüssel, titel) der aktuellen Ansicht."""
        loc = self.nav_loc()
        key = ("home", self.home_expanded) if loc[0] == "home" else loc
        return key, self._swipe_title(*loc)

    def swipe_target(self):
        """Wohin nav_go_back() führt (gleiche Regeln, ohne den Stapel zu verändern)."""
        if self.view == "home":
            return ("home", None), "home"
        cur = self.nav_loc()
        for kind, nid in reversed(self.nav_back):
            if kind == "home":
                break
            n = self.stores[kind].notes.get(nid) if nid else None
            if nid and (not n or n.get("trashed")):
                continue
            if (kind, nid) == cur:
                continue
            return (kind, nid), self._swipe_title(kind, nid)
        return ("home", None), "home"

    def swipe_goto(self, key):
        """2fz vorwärts zu einer verlassenen Ansicht."""
        kind, nid = key
        self.recent.close()
        if kind == "home":
            self.go_home()
        elif nid:
            n = self.stores[kind].notes.get(nid) if kind in self.stores else None
            if not n or n.get("trashed"):
                return False
            self.home_open(kind, nid)
        elif kind in self.stores:
            self.set_kind(kind)
        else:
            return False
        return True

    def can_nav_back(self):
        return self.view != "home" or bool(self.home_expanded)

    def nav_go_back(self):
        self.recent.close()
        if self.view == "home":
            if self.home_expanded:
                self.toggle_home_expand(self.home_expanded)
            return
        while self.nav_back:
            kind, nid = self.nav_back.pop()
            if kind == "home":
                break
            n = self.stores[kind].notes.get(nid) if nid else None
            if nid and (not n or n.get("trashed")):
                continue                # inzwischen gelöscht → überspringen
            if (kind, nid) == self.nav_loc():
                continue
            self._nav_skip = True
            if nid:
                self.home_open(kind, nid)
            else:
                self.set_kind(kind)
            return
        self.go_home()

    def toggle_home_expand(self, kind):
        self.home_expanded = None if self.home_expanded == kind else kind
        self.refresh_home()

    def go_home(self):
        self.home_expanded = None
        if self.view != "home" or not self.home_btn.get_active():
            self.flush()
            self.remember_pos()
            self.hide_jump()
            if self.current and is_empty(self.current):
                self.drop_empty(self.current)
            if self.current:
                self.last_sel[self.kind] = self.current["id"]
            self.current = None
            self.view = "home"
            self.home_btn.set_active(True)
            self.main_stack.set_visible_child_name("home")
            self.place_list()
            self.update_tabs()
            self.update_top_buttons()
            self.switch_pop.popdown()
        self.home_search.set_text("")
        self.refresh_home()
        self.update_status_ui()
        self.nav_note()

    def refresh_home(self):
        if not hasattr(self, "home_panels"):
            return
        self.queue_recent()
        q = self.home_search.get_text()
        counts = []
        exp = getattr(self, "home_expanded", None)
        opened = self.__dict__.setdefault("home_open_folders", set())
        for i, (kind, panel) in enumerate(self.home_panels.items(), 1):
            panel.set_visible(exp is None or exp == kind)
            store = self.stores[kind]
            items = store.visible(q)
            total = len(store.visible())
            counts.append(f"{total} {KINDS[kind][4 if total != 1 else 3]}")
            hits = " · " + i18n.tr("{} treffer", len(items)) if q.strip() else ""
            # gezeichneter Titel → nicht automatisch übersetzt, daher selbst durch i18n.tr
            panel.set_title(f"<span alpha='70%'>{ch.SUP[i]}</span>{KINDS[kind][1]} {ch.esc(i18n.tr(TAB_NAMES[kind]))}"
                            f"<span alpha='55%'> · {total}{ch.esc(hits)}</span>")
            child = panel.rows.get_first_child()
            while child:
                panel.rows.remove(child)
                child = panel.rows.get_first_child()
            limit = None if exp == kind else self.home_rows()
            shown = 0
            if not q.strip():                       # Ordner oben (aufklappbar), danach Einträge ohne Ordner
                by = {}
                for n in items:
                    by.setdefault(n.get("folder") or "", []).append(n)
                kids = {}
                for f in self.folder_names(kind):
                    kids.setdefault(f.rpartition("/")[0], []).append(f)
                rows = []

                def walk(parent, depth):
                    for f in kids.get(parent, []):
                        c = sum(len(v) for k, v in by.items() if k == f or k.startswith(f + "/"))
                        rows.append(("folder", f, c, depth))
                        if (kind, f) in opened:
                            walk(f, depth + 1)
                            rows.extend(("note", n, None, depth + 1) for n in by.get(f, []))
                walk("", 0)
                rows.extend(("note", n, None, 0) for n in by.get("", []))
            else:
                rows = [("note", n, None, 0) for n in items]
            for typ, obj, c, depth in rows:
                if limit is not None and shown >= limit:
                    break
                w = self.home_folder_row(kind, obj, c, (kind, obj) in opened) if typ == "folder" \
                    else self.home_row(kind, obj)
                w.set_margin_start(14 * depth)
                panel.rows.append(w)
                shown += 1
            if not items and not any(r[0] == "folder" for r in rows):
                panel.rows.append(ch.label("nichts gefunden" if q.strip() else f"noch keine {KINDS[kind][4]}",
                                           "tempty"))
            rest = len(rows) - shown
            if exp == kind:
                panel.more.set_label("󰁍 zurück")
                panel.more.set_tooltip_text("Zurück zur Übersicht (Esc)")
            else:
                panel.more.set_label(f"+{rest} weitere 󰁔" if rest > 0 else "alle 󰁔")
                panel.more.set_tooltip_text(f"Alle {KINDS[kind][4]} anzeigen")
        self.home_info.set_label("▸ " + " · ".join(counts))

    def home_rows(self):
        """Wie viele Zeilen je Spalte auf Home passen: im großen Fenster so viele, wie Platz ist."""
        return getattr(self, "_home_rows", self.HOME_ROWS)

    def fit_home_rows(self, width, height):
        if width >= 1000:                         # Spalten nebeneinander: Höhe ausnutzen
            row_h = 30
            for panel in self.home_panels.values():
                c = panel.rows.get_first_child()
                if c is not None and c.get_height() > 10:
                    row_h = c.get_height() + 1
                    break
            # Kopf, Suche, Spaltentitel, Fuß und Statuszeile abziehen
            n = max(self.HOME_ROWS, int((height - 250) / row_h))
        else:                                      # untereinander (schmal): die Seite scrollt, kurz halten
            n = self.HOME_ROWS
        if n != getattr(self, "_home_rows", None):
            self._home_rows = n
            if self.view == "home":
                self.refresh_home()

    def home_folder_row(self, kind, folder, count, open_):
        b = Gtk.Button(focus_on_click=False, hexpand=True)
        b.add_css_class("trow")
        b.add_css_class("tfolder")
        b.set_child(ch.hbox(ch.label("\U000F0140" if open_ else "\U000F0142", "folder-chev"),
                            ch.label("\U000F0770" if open_ else "\U000F024B", "folder-icon"),
                            ch.label(folder.rpartition("/")[2], "tr-title", hexpand=True, ellipsize=True),
                            ch.label(str(count), "tr-when"), spacing=6))
        b.set_tooltip_text(f"{folder} – klick: auf-/zuklappen · rechtsklick: neu, umbenennen, auflösen")

        def flip(*_):
            key = (kind, folder)
            opened = self.home_open_folders
            opened.discard(key) if key in opened else opened.add(key)
            self.refresh_home()
        b.connect("clicked", flip)
        right = Gtk.GestureClick(button=3)
        right.connect("pressed", lambda g, n, x, y: self.folder_menu(b, folder, x, y, kind=kind))
        b.add_controller(right)
        drop = Gtk.DropTarget.new(GObject.TYPE_STRING, Gdk.DragAction.MOVE)
        drop.connect("enter", lambda *_: (b.add_css_class("drop"), Gdk.DragAction.MOVE)[1])
        drop.connect("leave", lambda *_: b.remove_css_class("drop"))
        drop.connect("drop", lambda t, v, x, y: self.home_drop(v, kind, folder))
        b.add_controller(drop)
        return b

    def home_drop(self, value, kind, folder):
        k, _, nid = (value or "").partition(":")
        n = self.stores.get(k, {}).notes.get(nid) if k in self.stores else None
        if not n or k != kind:
            return False
        self.move_to_folder(n, folder, kind=kind)
        return True

    def home_row(self, kind, n):
        b = Gtk.Button(focus_on_click=False, hexpand=True)
        b.add_css_class("trow")
        title = ch.label(self.display_title(n, kind), "tr-title", hexpand=True, ellipsize=True)
        when = ch.label(nice_date(n["updated"]), "tr-when")
        tags = ch.label("  ".join("#" + l for l in n.get("labels", [])[:3]), "tr-tags", ellipsize=True) \
            if n.get("labels") else None
        if tags:
            tags.set_max_width_chars(16)
        b.set_child(ch.hbox(ch.label("󰐃" if n.get("pinned") else " ", "tr-pin"), title, tags, when, spacing=6))
        b.set_tooltip_text(self.display_title(n, kind))
        b.connect("clicked", lambda *_: self.home_open(kind, n["id"]))
        src = Gtk.DragSource(actions=Gdk.DragAction.MOVE)       # auf einen Ordner ziehen
        src.connect("prepare", lambda s_, x, y: Gdk.ContentProvider.new_for_value(f"{kind}:{n['id']}"))
        src.connect("drag-begin", lambda s_, d: s_.set_icon(Gtk.WidgetPaintable.new(b), 10, 10))
        b.add_controller(src)
        # Löschen direkt aus Home: Papierkorb-Knopf beim Überfahren + Rechtsklick-Menü
        d = Gtk.Button(label="󰆴", tooltip_text="In den Papierkorb", focus_on_click=False, valign=Gtk.Align.CENTER)
        d.add_css_class("tr-del")
        d.connect("clicked", lambda *_: self.home_delete(kind, n["id"]))
        wrap = Gtk.Box(spacing=2)
        wrap.add_css_class("trow-wrap")
        wrap.append(b)
        wrap.append(d)
        self.entry_right_click(wrap, lambda: (kind, n["id"]))
        return wrap

    def home_menu(self, widget, kind, nid, x, y):
        return self.entry_menu(widget, kind, nid, x, y)

    def entry_menu(self, widget, kind, nid, x, y):
        """Rechtsklick auf einen Eintrag – gleich in allen Listen (Home, Liste/Dropdown, Zuletzt-Leiste).
        Gleiche Optik und Auswahl wie „Mehr“ im geöffneten Eintrag, Anheften/Öffnen/Löschen ganz oben."""
        store = self.stores[kind]
        n = store.notes.get(nid)
        if not n:
            return None
        run = lambda fn: (lambda: self.open_then(kind, nid, fn))
        if n.get("trashed"):
            entries = [(None, (("󰦛", "Wiederherstellen", "", lambda: self.restore_entry(kind, n)),
                               ("󰩹", "Endgültig löschen …", "", lambda: self.purge_entry(kind, n))))]
        else:
            top = [("󰏌", "Öffnen", "", lambda: self.home_open(kind, nid)),
                   ("󰐄", "Lösen", "", lambda: self.pin_entry(kind, n, False)) if n.get("pinned") else
                   ("󰐃", "Anheften", "", lambda: self.pin_entry(kind, n, True))]
            entries = [(None, tuple(top))]
            share_items = [("󰆏", "Als Text kopieren", "", run(self.share_copy)),
                           ("󰇮", "Per E-Mail senden …", "", run(self.share_mail)),
                           ("󰈝", "Als Datei speichern …", "", run(self.share_file)),
                           ("󰠮", "Für Freunde mit notist (.notes) …", "", run(self.share_bundle))]
            entries.append(("Teilen", tuple(share_items)))
            more = [("󰋚", "Versionsverlauf …", "strg+umschalt+h", run(self.show_history)),
                    ("󰀼", "Aus dem Archiv holen" if n.get("archived") else "Archivieren", "strg+umschalt+a",
                     run(self.toggle_archive))]
            f = n.get("file")
            if f and os.path.exists(f):
                more += [("󰉋", "Im Dateimanager zeigen", "", lambda: show_in_files(f)),
                         ("󰅍", "Pfad kopieren", "", lambda: (self.win.get_clipboard().set(f), self.notify("Pfad kopiert")))]
            entries.append(("Mehr", tuple(more)))
            cur = n.get("folder") or ""
            fitems = [("󰉋", fo, "", (lambda fo=fo: self.move_to_folder(n, fo, kind=kind)), True)
                      for fo in self.folder_names(kind) if fo != cur][:14]
            if cur:
                fitems.append(("󰉖", "Aus dem Ordner nehmen", "", lambda: self.move_to_folder(n, "", kind=kind)))
            fitems.append(("󰉗", "In neuen Ordner …", "", lambda: self.folder_prompt(
                widget, None, kind=kind, then=lambda fo: self.move_to_folder(n, fo, kind=kind))))
            entries.append(("In Ordner verschieben", tuple(fitems)))
            entries.append((None, (("󰆴", "In den Papierkorb", "", lambda: self.home_delete(kind, nid)),)))
        pop = wr.file_menu(entries, sub={"notes": "Notiz", "docs": "Words", "latex": "LaTeX"}.get(kind, ""),
                           title=self.display_title(n, kind))
        pop.add_css_class("ctx-menu")
        box = pop.get_child()
        pop.set_child(None)
        sc = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER, propagate_natural_height=True,
                                max_content_height=560)
        sc.set_child(box)
        pop.set_child(sc)
        popup_at(pop, widget, x, y, self.swipe.widget)
        return pop

    def entry_right_click(self, widget, kind_nid):
        """Rechtsklick (Maus) und langes Drücken (Touch) auf eine Listenzeile → entry_menu."""
        right = Gtk.GestureClick(button=3)
        right.connect("pressed", lambda g, _n, x, y: (g.set_state(Gtk.EventSequenceState.CLAIMED),
                                                       self.entry_menu(widget, *kind_nid(), x, y)))
        widget.add_controller(right)
        hold = Gtk.GestureLongPress(touch_only=True)
        hold.connect("pressed", lambda g, x, y: (g.set_state(Gtk.EventSequenceState.CLAIMED),
                                                  self.entry_menu(widget, *kind_nid(), x, y)))
        widget.add_controller(hold)

    def open_then(self, kind, nid, fn):
        """Eintrag öffnen und danach fn() ausführen (Teilen usw. arbeitet mit dem offenen Eintrag)."""
        self.home_open(kind, nid)
        GLib.timeout_add(120, lambda: (fn(), False)[1])

    def pin_entry(self, kind, n, on):
        n["pinned"] = on
        if not is_empty(n):
            self.stores[kind].save(n)
        if n is self.current:
            self._loading = True
            self.pin_btn.set_active(on)
            self._loading = False
        self.refresh_home() if self.view == "home" else self.refresh_list()
        self.queue_recent() if hasattr(self, "queue_recent") else None

    def restore_entry(self, kind, n):
        self.stores[kind].restore(n)
        if n is self.current:
            self.set_mode("notes")
            self.select(n["id"])
        else:
            self.refresh_home() if self.view == "home" else self.refresh_list()
        self.notify("Wiederhergestellt")

    def purge_entry(self, kind, n):
        dlg = Gtk.AlertDialog(message=i18n.tr("„{}“ endgültig löschen?", self.display_title(n, kind)),
                              detail=i18n.tr("Das lässt sich nicht rückgängig machen."),
                              buttons=[i18n.tr("Abbrechen"), i18n.tr("Endgültig löschen")],
                              cancel_button=0, default_button=0)

        def done(d, res):
            try:
                if d.choose_finish(res) != 1:
                    return
            except GLib.Error:
                return
            was = n is self.current
            self.stores[kind].delete_forever(n)
            if was:
                self.current = None
                rest = self.store.trashed(self.search.get_text())
                if rest:
                    self.select(rest[0]["id"])
            self.refresh_home() if self.view == "home" else self.refresh_list()
            self.notify("Endgültig gelöscht")
        dlg.choose(self.win, None, done)

    def ask_delete(self, kind, n, then):
        """Vor dem Löschen: Liegt die Datei außerhalb von notist (z. B. Downloads), erst nachfragen –
        nur den Eintrag entfernen oder die Datei mit in den Papierkorb? then(mit_datei)."""
        path = lk.outside(self.prefs, n)
        if not path:
            then(False)
            return
        short = path.replace(os.path.expanduser("~"), "~", 1)
        dlg = Gtk.AlertDialog(
            message=i18n.tr("{} wirklich löschen?", os.path.basename(path)),
            detail=i18n.tr("Diese Datei liegt nicht in notist, sondern hier:") + f"\n{short}\n\n" +
            i18n.tr("„Nur aus notist entfernen“ lässt die Datei, wo sie ist. „Datei auch löschen“ legt sie in den "
                    "Papierkorb des Systems – Rückgängig in notist holt sie zurück."),
            buttons=[i18n.tr("Abbrechen"), i18n.tr("Nur aus notist entfernen"), i18n.tr("Datei auch löschen")],
            cancel_button=0, default_button=1)

        def done(d, res):
            try:
                i = d.choose_finish(res)
            except GLib.Error:
                return
            if i in (1, 2):
                then(i == 2)
        dlg.choose(self.win, None, done)

    def trash_entry(self, kind, n, with_file=False):
        """Eintrag in notists Papierkorb (mit_datei: die Datei zusätzlich in den System-Papierkorb)."""
        if with_file and not lk.trash_file(n):
            self.notify(f"Konnte {os.path.basename(n.get('file') or '')} nicht in den Papierkorb legen "
                        "– nur aus notist entfernt")
        self.stores[kind].trash(n)
        self._undo, self._undo_kind = n, kind
        if self.last_sel.get(kind) == n["id"]:
            self.last_sel.pop(kind, None)
        msg = "In den Papierkorb gelegt – samt Datei" if n.get("file_trashed") else "In den Papierkorb gelegt"
        if self.view == "home":
            self.refresh_home()
        elif n is self.current:
            self.current = None
            rest = self.notes_for_mode()
            if rest:
                self.select(rest[0]["id"])
            else:
                self.refresh_list()
        else:
            self.refresh_list()
        self.notify(msg, undo=True)

    def home_delete(self, kind, nid):
        n = self.stores[kind].notes.get(nid)
        if not n:
            return
        if n is self.current:
            self.flush(force=True)
        self.ask_delete(kind, n, lambda with_file: self.trash_entry(kind, n, with_file))

    def home_open(self, kind, nid):
        self.last_sel[kind] = nid
        self.set_kind(kind)
        if not self.current or self.current["id"] != nid:
            self.select(nid)

    def home_open_first(self):
        q = self.home_search.get_text()
        for kind in KINDS:
            items = self.stores[kind].visible(q)
            if items:
                self.home_open(kind, items[0]["id"])
                return

    def home_new(self, kind):
        self.set_kind(kind)
        self.new_note()

    def update_status_ui(self):
        home = self.view == "home"
        editing = not home and self.right.get_visible_child_name() == "editor"
        self.ed_bar.set_visible(editing)
        self.home_info.set_visible(not editing)
        if not home and not editing:
            self.home_info.set_label("")
        self.hint_box.set_visible(not editing and not self.compact)

    def focus_text(self):
        if self.docs:
            self.writer.focus_text()
            return
        if self.tex:
            self.latex.focus_text()
            return
        buf = self.text.get_buffer()
        if not self.text.has_focus():
            buf.place_cursor(buf.get_end_iter())
        self.text.grab_focus()

    def on_title_key(self, ctrl, keyval, code, state):
        if keyval == Gdk.KEY_Tab and not state & (Gdk.ModifierType.SHIFT_MASK | Gdk.ModifierType.CONTROL_MASK):
            self.focus_text()
            return True
        return False

    def fmt(self, name):
        if self.docs:
            self.writer.toggle_char({"bold": "b", "italic": "i", "underline": "u", "strike": "s"}[name])
        elif self.tex:
            if self.mode != "trash" and self.current:
                if name == "strike":
                    self.latex.insert_snippet("\\sout{" + lx.F + "}" + lx.F, "ulem")
                else:
                    self.latex.wrap({"bold": "textbf", "italic": "textit", "underline": "underline"}[name])
        elif self.mode != "trash":
            b = self.fmt_buttons[name]
            b.set_active(not b.get_active())

    # ================= Rechtschreibung =================
    def spell_on(self):
        return self.prefs.get("spell", True) and spell.speller().available

    def make_spell_btn(self, style):
        b = Gtk.ToggleButton(focus_on_click=False, can_focus=False)
        if style == "wts":                       # klein, für die Notizen-Leiste
            b.set_child(Gtk.Label(label="\U000F04C6"))
            b.add_css_class("wt")
        else:
            b.set_child(wr.big_label("\U000F04C6", "Rechtschreibung") if style == "wt" else Gtk.Label(label="\U000F04C6  ABC"))
            b.add_css_class(style)
        if style == "wt":
            b.add_css_class("rbig")
        if style == "pb":
            b.add_css_class("small")
        self.spell_tooltip(b)
        b.set_active(self.spell_on())
        b.connect("toggled", self.on_spell_toggled)
        self.spell_btns.append(b)
        return b

    def spell_tooltip(self, b):
        sp = spell.speller()
        if sp.available:
            names = " + ".join(spell.LANG_NAMES.get(c, c) for c in sp.codes)
            b.set_tooltip_text(f"Rechtschreibprüfung ({names}) – Rechtsklick auf ein rot "
                               "unterstrichenes Wort zeigt Vorschläge")
        else:
            b.set_tooltip_text(f"Rechtschreibprüfung: Wörterbücher fehlen.\nInstallieren mit: {spell.INSTALL_HINT}")

    def on_spell_toggled(self, btn):
        if getattr(self, "_spell_sync", False):
            return
        on = btn.get_active()
        if on and not spell.speller().available:
            self.notify(f"Wörterbücher fehlen: {spell.INSTALL_HINT}")
            on = False
        self.prefs["spell"] = on
        self.save_prefs()
        self._spell_sync = True
        for b in self.spell_btns:
            b.set_active(on)
        self._spell_sync = False
        self.spell_notes.queue(0)
        self.spell_docs.queue(0)

    # ================= Halbe Bildschirmbreite =================
    def on_width(self, width, height):
        self.set_compact(width < COMPACT_W, height)
        self.writer.set_short(height < SHORT_H)
        self.home_cols.set_orientation(Gtk.Orientation.VERTICAL if width < 1000 else Gtk.Orientation.HORIZONTAL)
        self.fit_home_rows(width, height)
        GLib.idle_add(lambda: self.apply_typewriter() and False)

    # ================= Suchen: erst im Eintrag, dann in allen =================
    def find_here(self):
        """Strg+F: im geöffneten Eintrag suchen (Leiste über dem Text, rechts „alle …“). Ohne Eintrag bzw. auf
        Home geht es wie bisher in die Suche über alle. Dreistufig: 1× öffnen · 2× (Fokus im Text) zurück ins
        Suchfeld mit markiertem Text · 3× (Fokus in der Leiste) schließen."""
        if self.view == "home":
            self.home_search.grab_focus()
            return
        if not self.current or (not self.docs and not self.tex and self.mode == "trash"):
            self.focus_search()
            return
        if self.docs:
            rev, entry, show, hide = self.writer.findrev, self.writer.find_entry, self.writer.show_find, self.writer.hide_find
        elif self.tex:
            rev, entry, show, hide = self.latex.findrev, self.latex.find_entry, self.latex.show_find, self.latex.hide_find
        else:
            nf = self.note_find
            rev, entry, show, hide = nf.rev, nf.entry, nf.show, nf.hide
        if not rev.get_reveal_child():
            show()
            return
        f = self.win.get_focus()
        if f is not None and (f is rev or f.is_ancestor(rev)):
            hide()
        else:
            entry.grab_focus()
            entry.select_region(0, -1)

    def selected_text(self):
        """Markierter Text im offenen Editor (für den Übersetzer) – sonst ""."""
        if self.view == "home" or not self.current:
            return ""
        buf = self.writer.buf if self.docs else self.latex.buf if self.tex else self.text.get_buffer()
        b = buf.get_selection_bounds()
        return buf.get_text(b[0], b[1], False).replace("\ufffc", "") if b else ""

    def on_trx_btn(self, b):
        if self._trx_sync:
            return
        if linguist_link.hover_enabled():                    # Hover-Übersetzer von linguist: Knopf = Schalter
            linguist_link.set_hover_active(b.get_active())
        elif b.get_active() != self.translator.is_open():
            self.toggle_translator(b.get_active())

    def sync_trx_btn(self):
        """Knopf „übersetzer“: Hover-Übersetzer (linguist) aktiviert → Anzeige, ob er an ist; sonst wie immer."""
        hover = linguist_link.hover_enabled()
        self._trx_sync = True
        try:
            if hover:
                on = linguist_link.hover_active()
                self.trx_btn.set_label("󰗊 übersetzer ◢")
                self.trx_btn.set_tooltip_text(
                    "Hover-Übersetzer " + ("an" if on else "aus") + ": Maus in die Bildschirmecke → linguist "
                    "(Klick: an/aus, Rechtsklick: Einstellungen, Strg+Umschalt+T: markierten Text übersetzen)")
                self.trx_btn.set_active(on)
            else:
                self.trx_btn.set_label("󰗊 übersetzer")
                self.trx_btn.set_tooltip_text("Übersetzer Deutsch ⇄ Englisch (Strg+Umschalt+T)")
                self.trx_btn.set_active(self.translator.is_open())
        finally:
            self._trx_sync = False

    def toggle_translator(self, on=None):
        """Übersetzer unten rechts auf/zu; beim Öffnen wird markierter Text gleich übernommen."""
        if linguist_link.hover_enabled():                    # Hover-Modus: Karte von linguist statt Overlay
            linguist_link.popup(self.selected_text())
            return
        tr = self.translator
        on = (not tr.is_open()) if on is None else on
        tr.toggle(on, (self.selected_text() or None) if on else None)

    def translator_toggled(self, on):
        if self.trx_btn.get_active() != on and not linguist_link.hover_enabled():
            self._trx_sync = True
            self.trx_btn.set_active(on)
            self._trx_sync = False
        f = self.win.get_focus()
        if not on and (f is None or f.is_ancestor(self.translator)) and self.view != "home" and self.current:
            self.focus_text()                   # Fokus zurück in den Text

    def find_query(self):
        """Was gerade in der Suchleiste des Eintrags steht (für Strg+Umschalt+F)."""
        if self.docs:
            e, rev = self.writer.find_entry, self.writer.findrev
        elif self.tex:
            e, rev = self.latex.find_entry, self.latex.findrev
        else:
            e, rev = self.note_find.entry, self.note_find.rev
        return e.get_text() if rev.get_reveal_child() else ""

    def find_everywhere(self):
        if self.view == "home":
            self.home_search.grab_focus()
            return
        self.search_all(self.find_query())

    def search_all(self, q):
        """Suche aus der Leiste in die Liste übernehmen (filtert alle Einträge des Bereichs)."""
        if q and self.search.get_text() != q:
            self.search.set_text(q)
        self.focus_search()

    def count_all(self, kind, q):
        store = self.stores.get(kind)
        return len(store.visible(q)) if store else 0

    def update_search_vis(self, force=False):
        """Seitenleisten-Suche nur sichtbar, solange sie Text hat oder gerade gebraucht wird (Strg+Umschalt+F)."""
        if getattr(self, "_list_place", None) == "pop":
            self.search.set_visible(True)
        else:
            self.search.set_visible(self.view != "home" and (force or bool(self.search.get_text())
                                                              or self.search.get_focus_child() is not None))

    def focus_search(self):
        """Strg+F: Suche fokussieren – im schmalen Fenster liegt sie im Dropdown oben, das erst aufgehen muss
        (sonst landete der Fokus in einem unsichtbaren Feld und Tippen ging ins Leere)."""
        if getattr(self, "_list_place", None) == "pop" and self.view != "home":
            if self.switcher.get_visible():
                self.switcher.popup()          # on_switch_show setzt den Fokus in die Suche
            return
        self.update_search_vis(force=True)
        self.search.grab_focus()

    def on_switch_show(self, *_):
        self.switch_chev.set_label("\U000F0143")
        w = self.switcher.get_width()
        self.switch_sheet.set_size_request(max(300, w), -1)
        self.list_scroll.set_max_content_height(max(200, self.win.get_height() - 260))
        self.sheet_title.set_label(f"{KINDS[self.kind][1]}  {i18n.tr(TAB_NAMES[self.kind])} · {len(self.store.visible())}")
        self.refresh_list()
        GLib.idle_add(lambda: self.search.grab_focus() and False)

    def set_compact(self, on, height=None):
        if height:
            self.list_scroll.set_max_content_height(max(200, height - 260))
        if on == self.compact:
            return
        self.compact = on
        (self.win.add_css_class if on else self.win.remove_css_class)("compact")
        self.recent.set_narrow(on)
        self.place_list()
        self.update_tabs()
        self.update_top_buttons()
        for b in (self.pin_btn, self.del_btn):
            b.set_label(b.full_label.split(" ")[0] if on else b.full_label)
        for b in (self.more_btn, self.share_btn):
            b.get_child().set_label(b.full_label.split(" ")[0] if on else b.full_label)
        if self.current:
            self.update_label_btn()
        self.toast_label.set_max_width_chars(16 if on else 44)
        self.update_status_ui()
        self.latex.set_compact(on)
        self.writer.set_compact(on)
        self.update_switcher()

    def on_side_moved(self, paned, _):
        """Trenner gezogen: neue Breite merken (gebündelt, nur wenn die Leiste wirklich links steht)."""
        if self.body.get_start_child() is None or not self.body.get_mapped():
            return
        w = paned.get_position()
        if w < 200 or abs(w - self.prefs.get("side_width", 330)) < 2:
            return
        self.prefs["side_width"] = w
        if getattr(self, "_side_save", None):
            GLib.source_remove(self._side_save)
        self._side_save = GLib.timeout_add(500, lambda: (setattr(self, "_side_save", None), self.save_prefs(), False)[-1])

    def update_top_buttons(self):
        """Schmales Fenster: „neu“ und „öffnen“ stecken in der Leiste links (Maus an den Rand) und unten in der
        Liste, die Versionsnummer in den Einstellungen – so passt die Kopfleiste ganz in die halbe Breite."""
        c = bool(self.compact)
        self.new_btn.set_visible(not c and self.view != "home")
        self.open_btn.set_visible(not c)
        self.ver_btn.set_visible(not c or self.ver_btn.has_css_class("news"))

    def update_tabs(self):
        """Schmal: nur der aktive Tab zeigt seinen Namen (wie bei datist/musicalist)."""
        for b in self.tab_btns:
            b.name_lbl.set_visible(not self.compact or b.get_active())

    def place_list(self):
        """Suche + Liste: links als Seitenleiste (Notizen im breiten Fenster) oder im Dropdown oben
        (schmales Fenster, Words und LaTeX immer). Auf Home gibt es keins von beiden."""
        want = "pop" if (self.compact or self.kind != "notes") else "side"
        if want != getattr(self, "_list_place", None):
            self._list_place = want
            for w in (self.search, self.left):
                if w.get_parent() is self.body:
                    self.body.set_start_child(None)
                elif w.get_parent():
                    w.get_parent().remove(w)
            pop = want == "pop"
            self.list_scroll.set_vexpand(not pop)
            self.list_scroll.set_propagate_natural_height(pop)
            if pop:
                self.search.set_hexpand(True)
                self.left.set_size_request(-1, -1)
                self.switch_box.append(self.search)
                self.switch_box.append(self.left)
            else:
                self.search.set_hexpand(False)
                self.list_scroll.set_max_content_height(-1)
                self.left.set_size_request(215, -1)
                self.left.prepend(self.search)           # keine Suchleiste oben: erscheint hier nur bei Bedarf
                self.body.set_start_child(self.left)
                self.body.set_position(int(self.prefs.get("side_width", 330)))
        home = self.view == "home"
        self.switcher.set_visible(want == "pop" and not home)
        self.lead_spacer.set_visible(False)
        self.spacer.set_visible(home)
        self.tab_scroll.set_visible(not home)
        self.tab_sep.set_visible(not home)
        self.tab_plus.set_visible(not home and not self.compact)
        self.update_search_vis()

    def update_switcher(self):
        n = self.current
        if n:
            title = self.display_title(n)
        else:
            title = "Papierkorb" if self.mode == "trash" else f"Keine {self.noun(True)}"
        self.switch_title.set_label(title)
        self.switch_sub.set_label(self.subtitle.get_label())
        self.update_doc_tabs()

    # ================= Tabs offener Einträge =================
    def update_doc_tabs(self):
        """Tab-Leiste oben: je Bereich die geöffneten Einträge (Reihenfolge des Öffnens). Der aktuelle kommt
        automatisch dazu; gelöschte/archivierte verschwinden. Wird nur neu gebaut, wenn sich etwas ändert."""
        if self.view == "home":
            return
        tabs = self.open_tabs[self.kind]
        n = self.current
        if n and self.mode == "notes" and n["id"] not in tabs:
            tabs.append(n["id"])
        alive = {x["id"] for x in self.store.visible()}
        tabs[:] = [t for t in tabs if t in alive]
        cur = n["id"] if n and n["id"] in tabs else None
        items = [(t, self.display_title(self.store.notes[t])) for t in tabs]
        sig = (self.kind, cur, tuple(items))
        if sig == self._tabs_sig:
            return
        self._tabs_sig = sig
        while (c := self.doc_tabs.get_first_child()):
            self.doc_tabs.remove(c)
        many = len(items) > 1
        group = None
        for i, (nid, title) in enumerate(items):
            b = self.make_doc_tab(nid, i + 1, title, many)
            if group is not None:
                b.set_group(group)
            group = group or b
            b.set_active(nid == cur)
            self.doc_tabs.append(b)
        if cur:
            GLib.idle_add(self.reveal_doc_tab, cur)

    def make_doc_tab(self, nid, num, title, closable):
        b = Gtk.ToggleButton(focus_on_click=False, valign=Gtk.Align.CENTER, tooltip_text=title)
        b.add_css_class("ttab")
        b.add_css_class("doctab")
        b.nid = nid
        key = Gtk.Label(label=ch.SUP[num] if num < 10 else "")
        key.add_css_class("key")
        name = Gtk.Label(label=title, ellipsize=3, max_width_chars=18)
        x = Gtk.Button(label="✕", focus_on_click=False, tooltip_text="Tab schließen (Strg+W)", visible=closable)
        x.add_css_class("doctab-x")
        x.connect("clicked", lambda *_: self.close_doc_tab(nid))
        b.set_child(ch.hbox(key, name, x, spacing=4))
        b.x_btn = x
        b.connect("toggled", lambda btn: btn.get_active() and self.open_doc_tab(nid))
        mid = Gtk.GestureClick(button=2)
        mid.connect("pressed", lambda *_: self.close_doc_tab(nid))
        b.add_controller(mid)
        # das ✕ steckt im Tab-Knopf, der den Klick sonst selbst schluckt → vorher abfangen
        xc = Gtk.GestureClick(button=1, propagation_phase=Gtk.PropagationPhase.CAPTURE)

        def pressed(g, n_press, px, py, btn=b):
            w = btn.pick(px, py, Gtk.PickFlags.DEFAULT)
            if btn.x_btn.get_visible() and w is not None and (w is btn.x_btn or w.is_ancestor(btn.x_btn)):
                g.set_state(Gtk.EventSequenceState.CLAIMED)
                GLib.idle_add(lambda: self.close_doc_tab(nid) and False)
        xc.connect("pressed", pressed)
        b.add_controller(xc)
        return b

    def reveal_doc_tab(self, nid):
        b = self.doc_tabs.get_first_child()
        while b and b.nid != nid:
            b = b.get_next_sibling()
        ok, r = b.compute_bounds(self.doc_tabs) if b else (False, None)
        if ok:
            adj = self.tab_scroll.get_hadjustment()
            if r.get_x() < adj.get_value():
                adj.set_value(r.get_x())
            elif r.get_x() + r.get_width() > adj.get_value() + adj.get_page_size():
                adj.set_value(r.get_x() + r.get_width() - adj.get_page_size())
        return False

    def open_doc_tab(self, nid):
        if self._loading or (self.current and self.current["id"] == nid):
            return
        self.select(nid)
        row = self.listbox.get_first_child()
        while row:
            if getattr(row, "note_id", None) == nid:
                self._loading = True
                self.listbox.select_row(row)
                self._loading = False
                break
            row = row.get_next_sibling()

    def close_doc_tab(self, nid=None):
        """Tab schließen (der Eintrag bleibt erhalten); der letzte Tab führt zurück auf Home."""
        tabs = self.open_tabs[self.kind]
        nid = nid or (self.current and self.current["id"])
        if nid not in tabs:
            return
        i = tabs.index(nid)
        tabs.remove(nid)
        if self.current and self.current["id"] == nid:
            if tabs:
                self.select(tabs[min(i, len(tabs) - 1)])
                self.refresh_list()
            else:
                self.go_home()
        else:
            self._tabs_sig = None
            self.update_doc_tabs()

    def cycle_doc_tab(self, d):
        tabs = self.open_tabs[self.kind]
        if len(tabs) > 1 and self.current and self.current["id"] in tabs:
            self.select(tabs[(tabs.index(self.current["id"]) + d) % len(tabs)])
            self.refresh_list()

    # ================= Checklisten (nur Notizen) =================
    def line_box(self, line):
        buf = self.text.get_buffer()
        ok, it = buf.get_iter_at_line(line)
        ch = it.get_char()
        return ch if ch in (BOX_OPEN, BOX_DONE) else None

    def toggle_checklist(self):
        if self.docs:
            self.writer.toggle_list("bullet")
            return
        if self.tex:
            return
        if self.mode == "trash" or not self.current:
            return
        buf = self.text.get_buffer()
        b = buf.get_selection_bounds()
        if b:
            first, last = b[0].get_line(), b[1].get_line()
            if b[1].starts_line() and last > first:
                last -= 1
        else:
            first = last = buf.get_iter_at_mark(buf.get_insert()).get_line()
        lines = range(first, last + 1)
        remove = all(self.line_box(l) for l in lines)
        buf.begin_user_action()
        for l in lines:
            ok, it = buf.get_iter_at_line(l)
            if remove:
                e = it.copy()
                e.forward_chars(2 if buf.get_text(it, self.iter_plus(it, 2), False)[1:] == " " else 1)
                buf.delete(it, e)
            elif not self.line_box(l):
                buf.insert(it, BOX_OPEN + " ")
        buf.end_user_action()
        self.style_checks()
        self.text.grab_focus()

    @staticmethod
    def iter_plus(it, n):
        e = it.copy()
        e.forward_chars(n)
        return e

    def set_box(self, line, done):
        buf = self.text.get_buffer()
        ok, it = buf.get_iter_at_line(line)
        names = [t for t in it.get_tags() if t.props.name]
        self._loading = True
        buf.delete(it, self.iter_plus(it, 1))
        ok, it = buf.get_iter_at_line(line)
        buf.insert(it, BOX_DONE if done else BOX_OPEN)
        ok, it = buf.get_iter_at_line(line)
        for t in names:
            buf.apply_tag(t, it, self.iter_plus(it, 1))
        self._loading = False
        self.on_edit()
        self.style_checks()

    def box_at(self, x, y):
        """Zeile, wenn (x, y) auf einem Kästchen liegt."""
        bx, by = self.text.window_to_buffer_coords(Gtk.TextWindowType.WIDGET, int(x), int(y))
        ok, it = self.text.get_iter_at_location(bx, by)
        if not ok:
            return None
        line = it.get_line()
        if not self.line_box(line):
            return None
        ok, s = self.text.get_buffer().get_iter_at_line(line)
        r = self.text.get_iter_location(s)
        return line if r.x - 4 <= bx <= r.x + r.width + 4 and r.y <= by <= r.y + r.height else None

    def on_text_click(self, gesture, n, x, y):
        if self.mode == "trash" or n != 1 or self.text.get_buffer().get_has_selection():
            return
        if self.image_menu_at(x, y):
            return
        line = self.box_at(x, y)
        if line is not None:
            self.set_box(line, self.line_box(line) == BOX_OPEN)
            buf = self.text.get_buffer()
            ok, it = buf.get_iter_at_line(line)
            it.forward_to_line_end()
            buf.place_cursor(it)

    def on_text_motion(self, ctrl, x, y):
        self.text.set_cursor_from_name("pointer" if self.box_at(x, y) is not None else "text")

    def line_text(self, line):
        buf = self.text.get_buffer()
        ok, s = buf.get_iter_at_line(line)
        e = s.copy()
        if not e.ends_line():
            e.forward_to_line_end()
        return buf.get_slice(s, e, True)

    def list_key(self, keyval, state):
        """Aufzählungen „• “ und Nummerierungen „1. “: Enter setzt fort, Enter auf leerem Punkt beendet,
        Rücktaste direkt nach dem Zeichen entfernt es, Tab/Umschalt+Tab rücken ein/aus."""
        buf = self.text.get_buffer()
        it = buf.get_iter_at_mark(buf.get_insert())
        line = it.get_line()
        text = self.line_text(line)
        m = LIST_RE.match(text)
        if not m:
            return False
        ok, start = buf.get_iter_at_line(line)
        col = it.get_line_offset()
        if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter) and not state & Gdk.ModifierType.SHIFT_MASK:
            if not text[m.end():].strip():               # leerer Punkt: Liste beenden
                buf.delete(start, self.iter_plus(start, len(text)))
                return True
            nxt = m.group(1) + (f"{int(m.group(3)) + 1}. " if m.group(3) else BULLET + " ")
            buf.insert_at_cursor("\n" + nxt)
            self.text.scroll_mark_onscreen(buf.get_insert())
            return True
        if keyval == Gdk.KEY_BackSpace and col == m.end():
            buf.delete(self.iter_plus(start, len(m.group(1))), self.iter_plus(start, m.end()))
            return True
        if keyval == Gdk.KEY_Tab and not state & Gdk.ModifierType.SHIFT_MASK:
            buf.insert(start, "    ")
            return True
        if keyval == Gdk.KEY_ISO_Left_Tab:
            n = min(4, len(m.group(1)))
            if n:
                buf.delete(start, self.iter_plus(start, n))
            return True
        return False

    def indent_selection(self, back):
        """Tab / Umschalt+Tab bei Markierung: alle berührten Zeilen um 4 Leerzeichen ein-/ausrücken (Markierung bleibt)."""
        buf = self.text.get_buffer()
        a, b = buf.get_selection_bounds()
        first, last = a.get_line(), b.get_line()
        if b.starts_line() and last > first:
            last -= 1
        so, eo = a.get_offset(), b.get_offset()
        self.note_checkpoint()
        buf.begin_user_action()
        for l in range(first, last + 1):
            ok, s = buf.get_iter_at_line(l)
            if back:
                text = self.line_text(l)
                n = 1 if text[:1] == "\t" else len(text) - len(text.lstrip(" "))
                n = min(n, 1 if text[:1] == "\t" else 4)
                if n:
                    buf.delete(s, self.iter_plus(s, n))
                    eo -= n
                    if l == first:
                        so = max(so - n, s.get_offset())
            else:
                buf.insert(s, "    ")
                eo += 4
                if l == first:
                    so += 4 if so > s.get_offset() else 0
        buf.end_user_action()
        buf.select_range(buf.get_iter_at_offset(so), buf.get_iter_at_offset(eo))
        self.note_after_format()

    def toggle_list(self, kind):
        """Markierte Zeilen zu einer Aufzählung/Nummerierung machen – oder wieder zu normalem Text."""
        if self.docs:
            self.writer.toggle_list(kind)
            return
        if self.tex or self.mode == "trash" or not self.current:
            return
        buf = self.text.get_buffer()
        b = buf.get_selection_bounds()
        if b:
            first, last = b[0].get_line(), b[1].get_line()
            if b[1].starts_line() and last > first:
                last -= 1
        else:
            first = last = buf.get_iter_at_mark(buf.get_insert()).get_line()
        lines = range(first, last + 1)

        def has(l):
            m = LIST_RE.match(self.line_text(l))
            return m and (bool(m.group(3)) == (kind == "number"))
        remove = all(has(l) for l in lines)
        buf.begin_user_action()
        for n, l in enumerate(lines, start=1):
            text = self.line_text(l)
            ok, s = buf.get_iter_at_line(l)
            m = LIST_RE.match(text)
            box = 2 if text[:1] in (BOX_OPEN, BOX_DONE) else 0
            if m:
                buf.delete(self.iter_plus(s, len(m.group(1))), self.iter_plus(s, m.end()))
            elif box:
                buf.delete(s, self.iter_plus(s, box if text[1:2] == " " else 1))
            if not remove:
                ok, s = buf.get_iter_at_line(l)
                indent = len(m.group(1)) if m else 0
                buf.insert(self.iter_plus(s, indent), f"{n}. " if kind == "number" else BULLET + " ")
        buf.end_user_action()
        self.style_checks()
        self.text.grab_focus()

    def auto_list(self, line):
        """„- “ oder „* “ am Zeilenanfang wird zu einer Aufzählung."""
        buf = self.text.get_buffer()
        text = self.line_text(line)
        cb = re.match(r"^(\s*)(?:• |[-*] )?\[([ xX]?)\] ", text)      # „[ ] “ / „- [x] “ → Checkliste
        if cb and self.prefs.get("markdown", True) and \
                buf.get_iter_at_mark(buf.get_insert()).get_line_offset() == cb.end():
            ok, s = buf.get_iter_at_line(line)
            p = self.iter_plus(s, len(cb.group(1)))
            buf.begin_user_action()
            buf.delete(p, self.iter_plus(p, cb.end() - len(cb.group(1))))
            ok, s = buf.get_iter_at_line(line)
            buf.insert(self.iter_plus(s, len(cb.group(1))), (BOX_DONE if cb.group(2).strip() else BOX_OPEN) + " ")
            buf.end_user_action()
            self.style_checks()
            return False
        m = re.match(r"^(\s*)[-*] ", text)
        if m and buf.get_iter_at_mark(buf.get_insert()).get_line_offset() == m.end():
            ok, s = buf.get_iter_at_line(line)
            p = self.iter_plus(s, len(m.group(1)))
            buf.begin_user_action()
            buf.delete(p, self.iter_plus(p, 1))
            ok, s = buf.get_iter_at_line(line)
            buf.insert(self.iter_plus(s, len(m.group(1))), BULLET)
            buf.end_user_action()
            self.style_checks()
        return False

    def on_text_key(self, ctrl, keyval, code, state):
        if state & Gdk.ModifierType.CONTROL_MASK and not state & Gdk.ModifierType.ALT_MASK:
            k = Gdk.keyval_to_lower(keyval)
            if k == Gdk.KEY_z:
                (self.note_redo if state & Gdk.ModifierType.SHIFT_MASK else self.note_undo)()
                return True
            if k == Gdk.KEY_y:
                self.note_redo()
                return True
        if self.mode == "trash" or state & (Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.ALT_MASK):
            return False
        buf = self.text.get_buffer()
        if buf.get_has_selection():
            if keyval in (Gdk.KEY_Tab, Gdk.KEY_ISO_Left_Tab) and self.text.get_editable():
                self.indent_selection(keyval == Gdk.KEY_ISO_Left_Tab or bool(state & Gdk.ModifierType.SHIFT_MASK))
                return True                      # Tab ersetzt die Markierung nicht, sondern rückt alle Zeilen ein
            return False
        if self.prefs.get("auto_lists", True) and self.list_key(keyval, state):
            return True
        it = buf.get_iter_at_mark(buf.get_insert())
        line = it.get_line()
        box = self.line_box(line)
        if not box:
            return False
        ok, start = buf.get_iter_at_line(line)
        prefix = 2 if buf.get_text(start, self.iter_plus(start, 2), False)[1:] == " " else 1
        if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter) and not state & Gdk.ModifierType.SHIFT_MASK:
            end = start.copy()
            end.forward_to_line_end()
            if not buf.get_text(self.iter_plus(start, prefix), end, False).strip():
                buf.delete(start, end)              # leerer Punkt: Liste beenden
            else:
                buf.insert_at_cursor("\n" + BOX_OPEN + " ")
            self.text.scroll_mark_onscreen(buf.get_insert())
            return True
        if keyval == Gdk.KEY_BackSpace and it.get_line_offset() == prefix:
            buf.delete(start, self.iter_plus(start, prefix))     # Kästchen weg, Text bleibt
            return True
        return False

    def queue_checks(self):
        if self._checks_id is None and not self.docs:
            self._checks_id = GLib.idle_add(self.style_checks)

    def style_checks(self):
        """Kästchen in Akzentfarbe, erledigte Punkte durchgestrichen und blass."""
        self._checks_id = None
        buf = self.text.get_buffer()
        box, done = buf.get_tag_table().lookup("box"), buf.get_tag_table().lookup("done")
        ok, c = self.text.get_style_context().lookup_color("color9")
        if ok:
            box.props.foreground_rgba = c
        ok, f = self.text.get_style_context().lookup_color("foreground")
        if ok:
            f.alpha = 0.45
            done.props.foreground_rgba = f
        s, e = buf.get_bounds()
        buf.remove_tag(box, s, e)
        buf.remove_tag(done, s, e)
        mark = buf.get_tag_table().lookup("listmark")
        if ok:
            mark.props.foreground_rgba = box.props.foreground_rgba
        buf.remove_tag(mark, s, e)
        for line in range(buf.get_line_count()):
            lm = LIST_RE.match(self.line_text(line))
            if lm:
                ok2, it = buf.get_iter_at_line(line)
                buf.apply_tag(mark, self.iter_plus(it, len(lm.group(1))), self.iter_plus(it, lm.end() - 1))
            ch = self.line_box(line)
            if not ch:
                continue
            ok, it = buf.get_iter_at_line(line)
            buf.apply_tag(box, it, self.iter_plus(it, 1))
            if ch == BOX_DONE:
                end = it.copy()
                end.forward_to_line_end()
                buf.apply_tag(done, self.iter_plus(it, 2) if self.iter_plus(it, 2).compare(end) <= 0 else end, end)
        return False

    # ================= Dokumente: Import / Export =================
    def import_dialog(self):
        dlg = Gtk.FileDialog(title="Datei öffnen")
        store = Gio.ListStore.new(Gtk.FileFilter)
        f = Gtk.FileFilter()
        f.set_name("Alles, was notist kann (Text, Markdown, Word, LibreOffice, LaTeX)")
        for ext in tuple(df.IMPORT_TYPES) + (".tex", ".notes"):
            f.add_pattern("*" + ext)
            f.add_pattern("*" + ext.upper())
        store.append(f)
        fn = Gtk.FileFilter()
        fn.set_name("Von Freunden (.notes)")
        fn.add_pattern("*.notes")
        store.append(fn)
        dlg.set_filters(store)

        def done(d, res):
            try:
                files = d.open_multiple_finish(res)
            except GLib.Error:
                return
            for i in range(files.get_n_items()):
                self.import_file(files.get_item(i).get_path())
        dlg.open_multiple(self.win, None, done)

    def import_file(self, path, kind=None):
        """Datei öffnen: notist bearbeitet sie direkt (keine Kopie). Der Bereich ergibt sich aus der Datei
        (.tex → LaTeX, .docx/.odt → Words, kurze .txt/.md → Notizen); ist das unklar, wird gefragt."""
        if path.lower().endswith(".notes"):
            self.import_bundle(path)
            return
        hit = self.file_index().get(lk.norm(path))
        if hit:                                          # schon verknüpft → diesen Eintrag öffnen
            hkind, n = hit
            if n.get("trashed"):
                self.stores[hkind].restore(n)
            self.home_open(hkind, n["id"])
            self.notify(f"{os.path.basename(path)} geöffnet")
            return
        if kind is None:
            kind = lk.kind_for(path)
            if kind is None:
                self.ask_kind(path)
                return
        try:
            data = lk.read(kind, path)
        except Exception as e:  # noqa: BLE001 – kaputte Dateien sollen die App nicht abstürzen lassen
            self.notify(f"Konnte {os.path.basename(path)} nicht öffnen: {e}")
            return
        target, extra = path, ""
        if not lk.writable(kind, path):
            # z. B. altes .doc: notist kann es lesen, aber nicht schreiben → Änderungen in eine .docx daneben
            stem = os.path.splitext(os.path.basename(path))[0]
            target = lk.unique(os.path.join(os.path.dirname(path), stem + lk.NEW_EXT[kind]))
            extra = f" – Änderungen landen in {os.path.basename(target)} daneben"
        self.flush()
        if self.current and is_empty(self.current):
            self.drop_empty(self.current)
        if self.view == "home" or kind != self.kind:
            self.set_kind(kind)
        if self.mode != "notes":
            self.set_mode("notes")
        n = self.store.create()
        n.update(data)
        n["source"] = path
        n["file"] = target
        n["file_auto"] = False
        if target == path:
            n["file_mtime"] = lk.mtime(path)
        else:
            n["file_ok"] = True                         # neue Datei, kein Original zu schützen
        self.store.save(n)
        if target != path:
            self.sync_file(n, kind)
        self.search.set_text("")
        self.select(n["id"])
        if path.lower().endswith(".doc"):
            extra = " (nur Text – Formatierung steckt im alten Word-Format)" + extra
        elif kind == "latex":
            extra = " – Bilder aus dem Ordner der Datei werden gefunden"
        self.notify(f"{os.path.basename(path)} geöffnet{extra}")

    def ask_kind(self, path):
        """Lange Textdatei: als Notiz oder als Words-Dokument öffnen?"""
        dlg = Gtk.AlertDialog(message=f"{os.path.basename(path)} öffnen als …",
                              detail="Eine längere Textdatei. Notizen sind schlicht und schnell, Words zeigt Seiten "
                                     "mit Überschriften und Layout. Die Datei bleibt, wo sie ist, und wird direkt "
                                     "bearbeitet.",
                              buttons=["Abbrechen", "Notiz", "Words"], cancel_button=0, default_button=1)

        def done(d, res):
            try:
                i = d.choose_finish(res)
            except GLib.Error:
                return
            if i in (1, 2):
                self.import_file(path, "notes" if i == 1 else "docs")
        dlg.choose(self.win, None, done)

    # ================= Dateien: Einträge = echte Dateien =================
    def kind_of(self, n):
        return next((k for k, st_ in self.stores.items() if st_.notes.get(n["id"]) is n), self.kind)

    def file_index(self):
        """Normierter Pfad → (Bereich, Eintrag) über alle Bereiche, auch Papierkorb."""
        out = {}
        for k, store in self.stores.items():
            for n in store.notes.values():
                if n.get("file") and not n["sync"].get("delete_remote"):
                    out[lk.norm(n["file"])] = (k, n)
        return out

    def sync_file(self, n, kind, force=False):
        """Nach dem Speichern: Inhalt in die Datei schreiben (neue Einträge bekommen dabei ihre Datei)."""
        if n.get("trashed"):
            return
        store = self.stores[kind]
        before = (n.get("file"), n.get("file_error"), n.get("file_missing"))
        if not n.get("file") and n.get("want_file"):
            n.pop("want_file", None)
            if not lk.settings(self.prefs)["new_as_files"]:
                store.save(n, touch=False)
                return
            if kind == "latex":
                self.latex_files_along(n)              # schon eingefügte Bilder usw. mitnehmen
            else:
                n["file"] = lk.new_path(self.prefs, kind, n.get("title"), n.get("folder"))
                n["file_auto"] = True
        path = n.get("file")
        if not path:
            return
        # selbst angelegte Datei folgt dem Titel (LaTeX-Projektordner erst beim Verlassen – dort wird kompiliert)
        if n.get("file_auto") and os.path.exists(path) and (kind != "latex" or force):
            new = lk.wanted_path(self.prefs, kind, n)
            lk.move(n, new) if new else None
        if kind == "latex" and n is self.current and self.tex:
            self.latex.set_project(os.path.dirname(n["file"]) if lk.is_project(n) else None,
                                   n.get("source") or n["file"])
        path = n["file"]
        if not n.get("file_auto") and not os.path.exists(path):
            # Original verschoben oder gelöscht: nicht still neu anlegen, der Stand bleibt in notist
            if not n.get("file_missing"):
                n["file_missing"] = True
                self.notify(f"{os.path.basename(path)} ist nicht mehr da – Änderungen bleiben in notist")
        elif lk.needs_confirm(n):
            self.confirm_overwrite(n, kind)
        else:
            mt = lk.mtime(path)
            # außerhalb geändert, während hier bearbeitet wurde: den fremden Stand vorher sichern
            lk.backup_original(n, again=bool(mt and n.get("file_mtime") and abs(mt - n["file_mtime"]) > 0.001))
            try:
                lk.write(kind, n)
                n.pop("file_error", None)
                n.pop("file_missing", None)
            except (OSError, ValueError) as e:
                if not n.get("file_error"):
                    self.notify(f"Konnte nicht in {os.path.basename(path)} schreiben ({getattr(e, 'strerror', None) or e})"
                                " – der Stand ist in notist gesichert")
                n["file_error"] = str(e)
        store.save(n, touch=False)
        if before != (n.get("file"), n.get("file_error"), n.get("file_missing")) and n is self.current:
            self.update_meta()

    def confirm_overwrite(self, n, kind):
        """Word/LibreOffice-Datei zum ersten Mal überschreiben? Einmal fragen, Original wird gesichert."""
        skip = self.__dict__.setdefault("_confirm_skip", set())
        if n["id"] in skip:
            return
        skip.add(n["id"])
        name = os.path.basename(n["file"])
        dlg = Gtk.AlertDialog(
            message=f"{name} direkt überschreiben?",
            detail="notist speichert deine Änderungen direkt in die geöffnete Datei. Manches aus Word oder LibreOffice "
                   "(Kommentare, Textfelder, Makros, besondere Formatierungen) kann notist nicht übernehmen – das "
                   "ginge beim Überschreiben verloren.\n\nVorher legt notist einmal eine Sicherung des Originals an. "
                   "Danach wird ohne Rückfrage gespeichert.",
            buttons=["Später", "Als neue Datei daneben", "Überschreiben"], cancel_button=0, default_button=2)

        def done(d, res):
            try:
                i = d.choose_finish(res)
            except GLib.Error:
                i = 0
            if i == 0:
                return                          # beim nächsten Öffnen erneut fragen; bis dahin nur in notist
            skip.discard(n["id"])
            if i == 1:
                root, ext = os.path.splitext(n["file"])
                n["file"] = lk.unique(f"{root} (notist){ext}")
                n["file_mtime"] = None
                self.notify(f"Änderungen gehen jetzt nach {os.path.basename(n['file'])}")
            n["file_ok"] = True
            self.sync_file(n, kind)
        dlg.choose(self.win, None, done)

    def reload_if_changed(self, n, kind):
        """Datei außerhalb von notist geändert (oder neu heruntergeladen)? Dann frisch einlesen. True = neu geladen."""
        f = n.get("file")
        if not f:
            return False
        mt = lk.mtime(f)
        if mt is None:
            if not n.get("file_auto"):
                n["file_missing"] = True
            return False
        n.pop("file_missing", None)
        if n.get("file_mtime") is not None and abs(mt - n["file_mtime"]) <= 0.001:
            return False
        if n.get("file_mtime") is None and n.get("file_auto"):
            n["file_mtime"] = mt                     # noch nie gelesen, selbst geschrieben: nichts zu tun
            return False
        try:
            lk.load_into(kind, n, f)
        except Exception as e:  # noqa: BLE001
            self.notify(f"Konnte {os.path.basename(f)} nicht neu einlesen: {e}")
            return False
        self.stores[kind].save(n)
        return True

    def scan_files(self):
        """Dateien, die im notist-Ordner liegen, aber noch keinen Eintrag haben, aufnehmen (z. B. hineinkopiert)."""
        import datetime as _dt
        known = set(self.file_index())
        added = 0
        for kind, p, folder in lk.scan(self.prefs, known):
            try:
                data = lk.read(kind, p)
            except Exception:  # noqa: BLE001
                continue
            store = self.stores[kind]
            n = store.create()
            n.update(data)
            n["file"], n["file_auto"], n["file_mtime"] = p, True, lk.mtime(p)
            if folder:
                n["folder"] = folder
            when = _dt.datetime.fromtimestamp(n["file_mtime"] or 0, _dt.timezone.utc).isoformat(timespec="seconds")
            n["created"] = n["updated"] = when
            store.save(n, touch=False)
            added += 1
        if added:
            self.refresh_list()
            self.refresh_home()
        return False

    def files_to_disk(self):
        """Alle Einträge ohne Datei (aus der Zeit vor v4.4) als Dateien in den notist-Ordner legen."""
        count = 0
        self.flush(force=True)
        for kind, store in self.stores.items():
            for n in list(store.notes.values()):
                if n.get("file") or n.get("trashed") or is_empty(n):
                    continue
                n["want_file"] = True
                if kind == "latex":
                    self.latex_files_along(n)
                self.sync_file(n, kind)
                if n.get("file"):
                    count += 1
        return count

    def give_file(self, n, kind):
        """Neu entstandener Eintrag (Umwandeln, von Freunden) → eigene Datei im notist-Ordner."""
        if not lk.settings(self.prefs)["new_as_files"] or n.get("file"):
            return
        if kind == "latex":
            self.latex_files_along(n)
        else:
            n["want_file"] = True
        self.sync_file(n, kind)

    def latex_files_along(self, n):
        """Interne LaTeX-Projektdateien (Bilder, Zusatzdateien) in den neuen Projektordner mitnehmen."""
        old = os.path.join(lx.FILES, n["id"])
        new = lk.new_path(self.prefs, "latex", n.get("title"), n.get("folder"))
        if os.path.isdir(old):
            import shutil as _sh
            _sh.copytree(old, os.path.dirname(new), dirs_exist_ok=True)
        n["file"], n["file_auto"] = new, True
        n.pop("want_file", None)

    def latex_export_dialog(self, fmt):
        if not self.tex or not self.current:
            return
        self.flush(force=True)
        n = self.current
        if fmt == "pdf" and not self.latex.pdf_path():
            self.notify("Noch kein PDF – erst kompilieren (Strg+S)")
            return
        name = "".join(c for c in (self.display_title(n) or "Dokument") if c not in '/\\:*?"<>|')[:80]
        dlg = Gtk.FileDialog(title="PDF speichern" if fmt == "pdf" else ".tex-Datei speichern")
        dlg.set_initial_name(f"{name}.{fmt}")
        src = n.get("source")
        folder = os.path.dirname(src) if src and os.path.isdir(os.path.dirname(src)) else \
            GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_DOCUMENTS) or os.path.expanduser("~")
        dlg.set_initial_folder(Gio.File.new_for_path(folder))

        def done(d, res):
            try:
                path = d.save_finish(res).get_path()
            except GLib.Error:
                return
            if not path.lower().endswith("." + fmt):
                path += "." + fmt
            try:
                if fmt == "pdf":
                    import shutil
                    shutil.copyfile(self.latex.pdf_path(), path)
                else:
                    with open(path, "w", encoding="utf-8") as f:
                        f.write(self.latex.text())
            except OSError as e:
                self.notify(f"Speichern fehlgeschlagen: {e.strerror}")
                return
            self.notify(f"Gespeichert: {os.path.basename(path)}")
        dlg.save(self.win, None, done)

    def open_latex_folder(self):
        if self.tex and self.current:
            d = os.path.join(lx.FILES, self.current["id"])
            os.makedirs(d, exist_ok=True)
            Gio.AppInfo.launch_default_for_uri(Gio.File.new_for_path(d).get_uri(), None)

    def display_title(self, n, kind=None):
        if n["title"].strip():
            return n["title"].strip()
        if (kind or self.kind) == "latex":
            t = lx.ld.doc_title(n["text"])
            if t:
                return t
            body = lx.ld.body_text(n["text"])
            return body[:60] if body else self.new_label()
        lines = [l for l in n["text"].splitlines() if l.strip()]
        return lines[0] if lines else self.new_label()

    def on_window_drop(self, target, value, x, y):
        ok = False
        for f in value.get_files():
            p = f.get_path()
            if p and os.path.splitext(p)[1].lower() in tuple(df.IMPORT_TYPES) + (".tex", ".notes"):
                self.import_file(p)
                ok = True
        return ok

    def export_dialog(self, fmt):
        if not self.current or fmt not in xp.FORMATS or self.kind not in xp.FORMATS[fmt][3]:
            return
        if self.tex and fmt == "pdf" and not self.latex.pdf_path():
            self.notify("Noch kein PDF – erst kompilieren (Strg+S)")
            return
        self.flush(force=True)
        if self.tex:
            self.latex.save_files()
        n = self.current
        label, pattern = EXPORTS[fmt]
        dlg = Gtk.FileDialog(title=f"Als {label} speichern")
        name = share.safe_name(self.display_title(n) or "Dokument")[:80]
        dlg.set_initial_name(f"{name}.{fmt}")
        src = n.get("source")
        folder = os.path.dirname(src) if src and os.path.isdir(os.path.dirname(src)) else \
            GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_DOCUMENTS) or os.path.expanduser("~")
        dlg.set_initial_folder(Gio.File.new_for_path(folder))
        f = Gtk.FileFilter()
        f.set_name(label)
        f.add_pattern(pattern)
        store = Gio.ListStore.new(Gtk.FileFilter)
        store.append(f)
        dlg.set_filters(store)

        def done(d, res):
            try:
                path = d.save_finish(res).get_path()
            except GLib.Error:
                return
            if not path.lower().endswith("." + fmt):
                path += "." + fmt
            self.export_to(path, fmt)
        dlg.save(self.win, None, done)

    def export_blocks(self):
        """Blockmodell des geöffneten Eintrags – Words direkt, Notizen über Markdown."""
        if self.docs:
            return self.writer.to_model()
        n = self.current
        return df.markdown_blocks(md.from_note(n["text"], n.get("rich"), n["title"], n.get("images")))

    def export_to(self, path, fmt):
        n = self.current
        title = n["title"].strip() or self.display_title(n)
        pages = 0
        try:
            if self.tex:
                if fmt == "pdf":
                    import shutil
                    shutil.copyfile(self.latex.pdf_path(), path)
                elif fmt == "zip":
                    xp.zip_dir(self.latex.project_dir(), path)
                else:
                    with open(path, "w", encoding="utf-8") as f:
                        f.write(self.latex.text() if fmt == "tex" else share.plain(n, "latex"))
            else:
                blocks = self.export_blocks()
                page = self.writer.page if self.docs else None
                if fmt == "docx":
                    df.write_docx(blocks, path, title, page)
                elif fmt == "odt":
                    import odf
                    odf.write_odt(blocks, path, title, page)
                elif fmt == "pdf":
                    import render
                    pages = render.write_pdf(blocks, path, title, page)
                elif fmt == "rtf":
                    xp.write_rtf(blocks, path, title)
                elif fmt == "epub":
                    xp.write_epub(blocks, path, title)
                else:
                    if not self.docs and fmt == "md":
                        text = md.from_note(n["text"], n.get("rich"), n["title"], n.get("images"))
                    elif not self.docs and fmt == "txt":
                        text = share.plain(n, "notes")
                    else:
                        text = {"txt": lambda: df.export_text(blocks), "md": lambda: df.to_markdown(blocks),
                                "html": lambda: df.to_html(blocks, title)}[fmt]()
                    with open(path, "w", encoding="utf-8") as f:
                        f.write(text)
        except Exception as e:  # noqa: BLE001
            self.notify(f"Export fehlgeschlagen: {e}")
            return
        extra = f" · {pages} Seite{'n' if pages != 1 else ''}" if fmt == "pdf" and pages else ""
        self.notify(f"Gespeichert: {os.path.basename(path)}{extra}")

    def print_doc(self):
        if not self.docs or not self.current:
            return
        import render
        try:
            render.print_doc(self.writer.to_model(), self.win, self.current["title"], self.writer.page)
        except GLib.Error as e:
            self.notify(f"Drucken fehlgeschlagen: {e.message}")

    # ================= Ordner (Notizen-Seitenleiste) =================
    # Ordner gibt es in allen drei Bereichen, verschachtelt als Pfad („uni/mathe“). Selbst angelegte Dateien
    # liegen im passenden Unterordner von Dokumente/notist/<bereich>/, fremde Dateien bleiben, wo sie sind.
    def use_folders(self):
        return self.mode == "notes"

    def folder_prefs(self, kind=None):
        """(angelegte Ordner, zugeklappte Ordner) des Bereichs – alte Notizen-Listen werden übernommen."""
        kind = kind or self.kind
        by = self.prefs.setdefault("folders_by", {})
        closed = self.prefs.setdefault("folders_closed_by", {})
        if "folders" in self.prefs:                       # bis v4.4: nur Notizen
            by.setdefault("notes", []).extend(f for f in self.prefs.pop("folders") if f not in by.get("notes", []))
            closed.setdefault("notes", []).extend(self.prefs.pop("folders_closed", []))
        return by.setdefault(kind, []), closed.setdefault(kind, [])

    def folder_names(self, kind=None):
        """Alle Ordnerpfade des Bereichs (angelegte, auf der Platte, von Einträgen getragene + deren Eltern)."""
        kind = kind or self.kind
        made, _ = self.folder_prefs(kind)
        names = set(made)
        names |= {n.get("folder") for n in self.stores[kind].notes.values() if n.get("folder") and not n["trashed"]}
        if lk.settings(self.prefs)["new_as_files"]:
            try:
                names |= set(lk.disk_folders(self.prefs, kind))
            except OSError:
                pass
        out = set()
        for f in names:
            parts = f.split("/")
            for i in range(1, len(parts) + 1):
                out.add("/".join(parts[:i]))
        return sorted(out, key=str.lower)

    def fill_folders(self, notes, keep):
        _, closed = self.folder_prefs()
        closed = set(closed)
        by = {}
        for n in notes:
            by.setdefault(n.get("folder") or "", []).append(n)
        names = self.folder_names()
        kids = {}
        for f in names:
            kids.setdefault(f.rpartition("/")[0], []).append(f)

        def count(f):
            return sum(len(v) for k, v in by.items() if k == f or k.startswith(f + "/"))
        sel = None

        def walk(parent, depth):
            nonlocal sel
            for f in kids.get(parent, []):
                c = count(f)
                if self.label_filter and not c:
                    continue
                self.listbox.append(self.folder_row(f, c, f not in closed, depth))
                if f in closed:
                    continue
                walk(f, depth + 1)
                for n in by.get(f, []):
                    row = self.make_row(n)
                    row.add_css_class("in-folder")
                    row.set_margin_start(14 * (depth + 1))
                    self.listbox.append(row)
                    if n["id"] == keep:
                        sel = row
        walk("", 0)
        for n in by.get("", []):
            row = self.make_row(n)
            self.listbox.append(row)
            if n["id"] == keep:
                sel = row
        return sel

    def folder_row(self, name, count, open_, depth=0):
        row = Gtk.ListBoxRow(selectable=False, activatable=True)
        row.add_css_class("folder-row")
        row.folder, row.note_id = name, None
        row.set_margin_start(14 * depth)
        row.set_child(ch.hbox(ch.label("\U000F0140" if open_ else "\U000F0142", "folder-chev"),
                              ch.label("\U000F0770" if open_ else "\U000F024B", "folder-icon"),
                              ch.label(name.rpartition("/")[2], "folder-name", hexpand=True, ellipsize=True),
                              ch.label(str(count), "folder-count"), spacing=6))
        row.set_tooltip_text(f"{name}\nKlick: auf-/zuklappen · Rechtsklick: neu, umbenennen, löschen · "
                             f"Einträge hierher ziehen")
        right = Gtk.GestureClick(button=3)
        right.connect("pressed", lambda g, n, x, y: self.folder_menu(row, name, x, y))
        row.add_controller(right)
        drop = Gtk.DropTarget.new(GObject.TYPE_STRING, Gdk.DragAction.MOVE)
        drop.connect("enter", lambda *_: (row.add_css_class("drop"), Gdk.DragAction.MOVE)[1])
        drop.connect("leave", lambda *_: row.remove_css_class("drop"))
        drop.connect("drop", lambda t, v, x, y: self.drop_on_folder(v, name))
        row.add_controller(drop)
        return row

    def note_drag(self, row):
        """Zeilen lassen sich auf einen Ordner (oder einen Eintrag ohne Ordner) ziehen."""
        src = Gtk.DragSource(actions=Gdk.DragAction.MOVE)
        src.connect("prepare", lambda s, x, y: Gdk.ContentProvider.new_for_value(row.note_id))
        src.connect("drag-begin", lambda s, d: s.set_icon(Gtk.WidgetPaintable.new(row), 10, 10))
        row.add_controller(src)
        drop = Gtk.DropTarget.new(GObject.TYPE_STRING, Gdk.DragAction.MOVE)
        drop.connect("drop", lambda t, v, x, y: self.drop_on_folder(
            v, (self.store.notes.get(row.note_id) or {}).get("folder") or ""))
        row.add_controller(drop)

    def drop_on_folder(self, nid, folder):
        n = self.store.notes.get(nid)
        if not n:
            return False
        self.move_to_folder(n, folder)
        return True

    def move_to_folder(self, n, folder, kind=None, quiet=False):
        kind = kind or self.kind
        folder = lk.clean_folder(folder)
        if not n or (n.get("folder") or "") == folder:
            return
        if self.current is n:
            self.flush(force=True)
        old = n.get("folder") or ""
        if folder:
            n["folder"] = folder
            made, closed = self.folder_prefs(kind)
            if folder not in made:
                made.append(folder)
            for f in list(closed):                 # Ziel (und seine Eltern) aufklappen
                if folder == f or folder.startswith(f + "/"):
                    closed.remove(f)
        else:
            n.pop("folder", None)
        if lk.move_to_folder(self.prefs, kind, n):   # selbst angelegte Datei zieht mit um
            n["file_mtime"] = lk.mtime(n["file"])
            if kind == "latex" and n is self.current and self.tex:
                self.latex.set_project(os.path.dirname(n["file"]) if lk.is_project(n) else None,
                                       n.get("source") or n["file"])
            if old and old not in self.folder_prefs(kind)[0]:
                lk.remove_empty_dirs(self.prefs, kind, old)
        self.stores[kind].save(n, touch=False)
        self.save_prefs()
        self.refresh_list()
        self.refresh_home()
        self.fill_more_menu()
        if not quiet:
            self.notify(f"In „{folder}“ verschoben" if folder else "Aus dem Ordner genommen")

    def toggle_folder(self, name):
        _, closed = self.folder_prefs()
        if name in closed:
            closed.remove(name)
        else:
            closed.append(name)
        self.save_prefs()
        self.refresh_list()

    def create_folder(self, name, kind=None):
        kind = kind or self.kind
        name = lk.clean_folder(name)
        if not name:
            return None
        made, closed = self.folder_prefs(kind)
        if name not in made:
            made.append(name)
        for f in list(closed):
            if name.startswith(f + "/"):
                closed.remove(f)
        if lk.settings(self.prefs)["new_as_files"]:
            try:
                os.makedirs(lk.folder_dir(self.prefs, kind, name), exist_ok=True)
            except OSError:
                pass
        self.save_prefs()
        self.refresh_list()
        self.refresh_home()
        self.fill_more_menu()
        return name

    def folder_prompt(self, anchor, old=None, move=False, parent="", kind=None, then=None):
        """Eingabe im Suite-Stil: neuen Ordner anlegen bzw. umbenennen (Enter bestätigt, Esc bricht ab)."""
        kind = kind or self.kind
        pop = wr.ist_pop(Gtk.Popover())
        pop.add_css_class("folder-pop")
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, width_request=260)
        head = Gtk.Label(label="ORDNER UMBENENNEN" if old else "NEUER ORDNER", xalign=0)
        head.add_css_class("wpop-head")
        box.append(head)
        where = f"{i18n.tr(TAB_NAMES[kind])}{' / ' + parent if parent else ''}"
        if old:
            where += " / " + old.rpartition("/")[0] if "/" in old else ""
        box.append(ch.label(f"in  {where}", "dim", "fp-where", ellipsize=True))
        row = Gtk.Box(spacing=6)
        row.append(ch.label("\U000F024B", "accent", "fp-icon"))
        e = Gtk.Entry(text=(old or "").rpartition("/")[2], placeholder_text="name des ordners", hexpand=True,
                      width_chars=18)
        e.add_css_class("tsearch")
        row.append(e)
        box.append(row)
        hint = ch.label("„/“ legt unterordner an, z. b. uni/mathe" if not old else "enter übernimmt · esc bricht ab",
                        "dim", "fp-hint")
        box.append(hint)
        btns = Gtk.Box(spacing=6, halign=Gtk.Align.END)
        btns.append(ch.button("abbrechen", "Esc", callback=lambda: pop.popdown()))
        okb = ch.button("umbenennen" if old else "anlegen", "Enter")
        okb.add_css_class("accent-btn")
        btns.append(okb)
        box.append(btns)
        pop.set_child(box)
        pop.set_parent(anchor)

        def ok(*_):
            raw = e.get_text().strip()
            name = lk.clean_folder(raw)
            pop.popdown()
            if not name:
                return
            if old:
                base = old.rpartition("/")[0]
                full = f"{base}/{name}" if base else name
                if full != old:
                    self.rename_folder(old, full, kind)
                return
            full = lk.clean_folder(f"{parent}/{name}" if parent else name)
            if move and self.current:
                self.move_to_folder(self.current, full)
            else:
                self.create_folder(full, kind)
                self.notify(f"Ordner „{full}“ angelegt")
            if then:
                then(full)
        e.connect("activate", ok)
        okb.connect("clicked", ok)
        pop.connect("closed", lambda p: GLib.idle_add(lambda: (p.unparent(), False)[1]))
        pop.popup()
        e.grab_focus()

    def folder_menu(self, row, name, x, y, kind=None):
        kind = kind or self.kind
        pop = Gtk.Popover(has_arrow=False)
        pop.add_css_class("home-menu")
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        noun = {"notes": "notiz", "docs": "dokument", "latex": "latex-dokument"}[kind]
        for text, cb in ((f"󰐕  neue {noun} hier" if kind == "notes" else f"󰐕  neues {noun} hier",
                          lambda: self.new_in_folder(kind, name)),
                         ("󰉗  unterordner …", lambda: self.folder_prompt(row, None, parent=name, kind=kind)),
                         ("󰏫  umbenennen …", lambda: self.folder_prompt(row, name, kind=kind)),
                         ("󰆴  ordner auflösen (inhalt bleibt)", lambda: self.delete_folder(name, kind))):
            b = Gtk.Button(label=text, focus_on_click=False)
            b.add_css_class("hm-item")
            b.get_child().set_xalign(0)
            b.connect("clicked", lambda _b, cb=cb: (pop.popdown(), GLib.idle_add(lambda: (cb(), False)[1])))
            box.append(b)
        pop.set_child(box)
        pop.set_parent(row)
        r = Gdk.Rectangle()
        r.x, r.y, r.width, r.height = int(x), int(y), 1, 1
        pop.set_pointing_to(r)
        pop.connect("closed", lambda p: GLib.idle_add(lambda: (p.unparent(), False)[1]))
        pop.popup()

    def new_in_folder(self, kind, folder):
        if self.view == "home" or kind != self.kind:
            self.set_kind(kind)
        self.new_note(folder=folder)

    def rename_folder(self, old, new, kind=None):
        kind = kind or self.kind
        self.flush(force=True)
        moved = lk.rename_dir(self.prefs, kind, old, new) if lk.settings(self.prefs)["new_as_files"] else None
        for n in self.stores[kind].notes.values():
            f = n.get("folder") or ""
            if f == old or f.startswith(old + "/"):
                n["folder"] = new + f[len(old):]
                if moved and n.get("file") and lk.norm(n["file"]).startswith(lk.norm(moved[0]) + os.sep):
                    n["file"] = moved[1] + lk.norm(n["file"])[len(lk.norm(moved[0])):]
                    n["file_mtime"] = lk.mtime(n["file"])
                self.stores[kind].save(n, touch=False)
        made, closed = self.folder_prefs(kind)
        ren = lambda f: new + f[len(old):] if (f == old or f.startswith(old + "/")) else f
        made[:] = list(dict.fromkeys([ren(f) for f in made] + [new]))
        closed[:] = [ren(f) for f in closed]
        self.save_prefs()
        if self.current and self.tex and lk.is_project(self.current):
            self.latex.set_project(os.path.dirname(self.current["file"]),
                                   self.current.get("source") or self.current["file"])
        self.refresh_list()
        self.refresh_home()
        self.fill_more_menu()

    def delete_folder(self, name, kind=None):
        """Ordner auflösen: Einträge (auch aus Unterordnern) wandern eine Ebene höher, nichts wird gelöscht."""
        kind = kind or self.kind
        self.flush(force=True)
        parent = name.rpartition("/")[0]
        for n in list(self.stores[kind].notes.values()):
            f = n.get("folder") or ""
            if f == name or f.startswith(name + "/"):
                rest = f[len(name):].lstrip("/")
                target = "/".join(x for x in (parent, rest) if x)
                if target:
                    n["folder"] = target
                else:
                    n.pop("folder", None)
                if lk.move_to_folder(self.prefs, kind, n):
                    n["file_mtime"] = lk.mtime(n["file"])
                self.stores[kind].save(n, touch=False)
        made, closed = self.folder_prefs(kind)
        lift = lambda f: "/".join(x for x in (parent, f[len(name):].lstrip("/")) if x)
        made[:] = list(dict.fromkeys(lift(f) for f in made if f != name and lift(f)))
        closed[:] = [lift(f) for f in closed if f != name]
        for sub in sorted(lk.disk_folders(self.prefs, kind), key=len, reverse=True):
            if sub == name or sub.startswith(name + "/"):
                lk.remove_empty_dirs(self.prefs, kind, sub)
        self.save_prefs()
        self.refresh_list()
        self.refresh_home()
        self.fill_more_menu()
        self.notify(f"Ordner „{name}“ aufgelöst – der Inhalt ist noch da")

    # ================= Liste =================
    def notes_for_mode(self):
        q = self.search.get_text()
        if self.mode == "trash":
            return self.store.trashed(q)
        if self.mode == "archive":
            return self.store.archived(q, self.label_filter)
        return self.store.visible(q, self.label_filter)

    def queue_recent(self):
        """Angeheftete Zuletzt-Leiste im Leerlauf neu füllen (mehrere Anlässe → einmal)."""
        if getattr(self, "recent", None) and not getattr(self, "_recent_q", None):
            self._recent_q = GLib.idle_add(self._recent_now)

    def _recent_now(self):
        self._recent_q = None
        self.recent.refresh()
        self.queue_datist()
        return False

    def queue_datist(self):
        """Erinnerungen an datist weitergeben (gebündelt, schreibt nur bei Änderungen)."""
        if getattr(self, "_datist_q", None):
            GLib.source_remove(self._datist_q)
        self._datist_q = GLib.timeout_add(800, self._datist_now)

    def _datist_now(self):
        self._datist_q = None
        try:
            rem.export_datist(self.prefs, self.stores)
        except Exception as e:  # noqa: BLE001 – datist ist ein Extra, darf notist nie stören
            print("datist:", e, file=sys.stderr)
        return False

    def update_pathbar(self, notes, keep):
        """Pfadleiste über der Liste (wie in filist): Bereich › Ordner des gewählten Eintrags, rechts die Anzahl."""
        while (c := self.crumbs.get_first_child()):
            self.crumbs.remove(c)
        crumbs = []
        icon, name = KINDS[self.kind][1], KINDS[self.kind][0].lower()
        if self.mode == "trash":
            crumbs.append(("󰆴 papierkorb", lambda: self.set_mode("notes")))
        elif self.mode == "archive":
            crumbs.append(("󰀼 archiv", lambda: self.set_mode("notes")))
        else:
            crumbs.append((f"{icon} {name}", lambda: (setattr(self, "label_filter", None), self.refresh_list())))
            if self.label_filter:
                crumbs.append((f"#{self.label_filter}", lambda: None))
            cur = self.stores[self.kind].notes.get(keep) if keep else None
            fo = (cur.get("folder") if cur else "") or ""
            if fo and self.use_folders():
                acc = ""
                for part in fo.split("/"):
                    acc = f"{acc}/{part}" if acc else part
                    crumbs.append((f"󰉋 {part}", lambda f=acc: self.reveal_folder(f)))
        for i, (text, cb) in enumerate(crumbs):
            if i:
                sep = Gtk.Label(label="›")
                sep.add_css_class("nt-sep")
                self.crumbs.append(sep)
            b = Gtk.Button(label=text, focus_on_click=False)
            b.add_css_class("nt-crumb")
            if i == len(crumbs) - 1:
                b.add_css_class("last")
            b.connect("clicked", lambda *_, f=cb: f())
            self.crumbs.append(b)
        self.path_count.set_label(str(len(notes)))

    def reveal_folder(self, f):
        """Ordner in der Liste aufklappen (Klick auf einen Pfadteil)."""
        _, closed = self.folder_prefs()
        if f in closed:
            closed.remove(f)
            self.save_prefs()
            self.refresh_list()

    def refresh_list(self, keep=None):
        self.queue_recent()
        keep = keep or (self.current and self.current["id"])
        self._loading = True
        while (r := self.listbox.get_first_child()):
            self.listbox.remove(r)
        notes = self.notes_for_mode()
        sel = None
        q = self.search.get_text().strip()
        folders = self.use_folders() and not q
        self.folder_add.set_visible(self.use_folders())
        self.foot_new.set_visible(self.mode == "notes")
        self.foot_new.set_tooltip_text(self.new_label() + " (Strg+N)")
        if folders:
            sel = self.fill_folders(notes, keep)
        else:
            for n in notes:
                row = self.make_row(n)
                self.listbox.append(row)
                if n["id"] == keep:
                    sel = row
        if q and self.mode == "notes":              # Treffer aus den anderen Bereichen darunter
            for kind in KINDS:
                if kind == self.kind:
                    continue
                hits = self.stores[kind].visible(q) + self.stores[kind].archived(q)
                if not hits:
                    continue
                head = Gtk.ListBoxRow(selectable=False, activatable=False)
                hl = Gtk.Label(label=f"{KINDS[kind][1]}  {KINDS[kind][0].upper()} · {len(hits)}", xalign=0)
                hl.add_css_class("list-head")
                head.set_child(hl)
                head.note_id = None
                self.listbox.append(head)
                for n in hits[:20]:
                    self.listbox.append(self.make_row(n, kind))
        if sel:
            self.listbox.select_row(sel)
        self._loading = False
        self.update_pathbar(notes, keep)
        n_trash, n_arch = len(self.store.trashed()), len(self.store.archived())
        self.trash_link.set_label(f"󰆴  Papierkorb ({n_trash})")
        self.archive_link.set_label(f"󰀼  Archiv ({n_arch})")
        self.archive_link.set_visible(self.mode != "trash")
        self.trash_link.set_visible(self.mode != "archive")
        if self.mode == "trash":
            self.subtitle.set_label(f"Papierkorb · {len(notes)} {self.noun(len(notes) != 1)}"
                                    f" · wird nach {st.PURGE_DAYS} Tagen geleert")
            self.trash_link.set_label(f"󰁍  Zurück zu den {self.noun(True)}")
        elif self.mode == "archive":
            self.subtitle.set_label(f"Archiv · {len(notes)} {self.noun(len(notes) != 1)}")
            self.archive_link.set_label(f"󰁍  Zurück zu den {self.noun(True)}")
        else:
            total = len(self.store.visible())
            noun = f"{total} {self.noun(total != 1)}"
            self.subtitle.set_label(noun + (f" · #{self.label_filter}" if self.label_filter else "") +
                                    (f" · {len(notes)} gefunden" if self.search.get_text() else ""))
        self.fill_label_chips()
        GLib.idle_add(lambda: self.update_switcher() and False)
        if not notes:
            self.show_empty()

    def show_empty(self):
        trash = self.mode in ("trash", "archive")
        arch = self.mode == "archive"
        docs = self.docs
        tex = self.tex
        self.empty_icon.set_label("󰀼" if arch else "󰆴" if trash else KINDS[self.kind][1] if self.kind != "notes" else "󰠮")
        self.empty_title.set_label("Archiv ist leer" if arch else "Papierkorb ist leer" if trash else
                                   ("Nichts gefunden" if self.search.get_text() else f"Noch keine {self.noun(True)}"))
        self.empty_hint.set_label(f"Archivierte {self.noun(True)} verschwinden aus der Liste, bleiben aber durchsuchbar. "
                                  "„Mehr → Archivieren“ (Strg+Umschalt+A) legt sie hier ab." if arch else
                                  f"Gelöschte {self.noun(True)} landen hier und lassen sich wiederherstellen." if trash else
                                  ("Strg+N legt ein neues an. Word-Dateien (.docx, .doc) lassen sich öffnen "
                                   "oder einfach hierher ziehen." if docs else
                                   "LaTeX setzt Texte und Formeln wie im Buch. notist erklärt dir alles beim Schreiben – "
                                   "Vorlagen, Vorschläge und eine Anleitung sind eingebaut." if tex else
                                   "Strg+N oder der Knopf unten legt eine an."))
        self.empty_btn.set_label("󰐕  Neues Dokument" if docs else "󰐕  Erstes LaTeX-Dokument" if tex else "󰐕  Erste Notiz")
        self.empty_btn.set_visible(not trash)
        self.empty_open.set_visible((docs or tex) and not trash)
        self.right.set_visible_child_name("empty")
        self.current = None
        self.nav_note()

    def make_row(self, n, kind=None):
        row = Gtk.ListBoxRow()
        row.note_id = n["id"]
        row.kind = kind or self.kind
        if n.get("color", "default") in COLORS and n.get("color") != "default":
            row.add_css_class("nc-" + n["color"])
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        head = Gtk.Box(spacing=6)
        lines = [l for l in n["text"].splitlines() if l.strip()]
        title = self.display_title(n, row.kind)
        if kind and kind != self.kind:
            kl = Gtk.Label(label=KINDS[kind][1])
            kl.add_css_class("row-kind")
            head.append(kl)
        tl = Gtk.Label(label=title, xalign=0, ellipsize=3, hexpand=True)
        tl.add_css_class("row-title")
        head.append(tl)
        if n["pinned"] and self.mode != "trash":
            p = Gtk.Label(label="󰐃")
            p.add_css_class("pin")
            head.append(p)
        boxes = [l for l in n["text"].splitlines() if l.startswith((BOX_OPEN, BOX_DONE))]
        if boxes and not self.docs:
            done = sum(l.startswith(BOX_DONE) for l in boxes)
            pl = Gtk.Label(label=f"\U000F0C52 {done}/{len(boxes)}")
            pl.add_css_class("row-prog")
            head.append(pl)
        rdt = rem.parse(n.get("reminder"))
        if rdt and not n.get("reminder_done"):
            rl = Gtk.Label(label="󰂚 " + rem.nice(rdt))
            rl.add_css_class("row-rem")
            head.append(rl)
        when = n["trashed_at"] if self.mode == "trash" and n["trashed_at"] else n["updated"]
        dl = Gtk.Label(label=nice_date(when))
        dl.add_css_class("row-date")
        head.append(dl)
        box.append(head)
        rest = lines if n["title"].strip() else lines[1:]
        snip = lx.ld.body_text(n["text"])[:100] if row.kind == "latex" else " ".join(rest)[:100]
        if snip:
            sl = Gtk.Label(label=snip.replace("\ufffc", ""), xalign=0, ellipsize=3, max_width_chars=24)
            sl.add_css_class("row-snippet")
            box.append(sl)
        if n.get("labels"):
            ll = Gtk.Label(label="  ".join("#" + l for l in n["labels"]), xalign=0, ellipsize=3, max_width_chars=24)
            ll.add_css_class("row-labels")
            box.append(ll)
        row.set_child(box)
        if row.kind == self.kind and self.mode == "notes":
            self.note_drag(row)
        self.entry_right_click(row, lambda: (row.kind, row.note_id))
        return row

    def on_row_selected(self, lb, row):
        # Im Dropdown folgt die Markierung dem Tastaturfokus (schon beim Aufklappen) – dort zählt nur
        # ein echter Klick/Enter (on_row_activated), sonst würde es sofort wieder zuklappen.
        if self._loading or not row or self.compact or not getattr(row, "note_id", None):
            return
        if row.kind != self.kind:
            self.jump_to(row.kind, row.note_id)
            return
        self.select(row.note_id, from_list=True)

    def on_row_activated(self, lb, row):
        if row is not None and getattr(row, "folder", None) is not None:
            self.toggle_folder(row.folder)
            return
        if not self.compact or not row or not getattr(row, "note_id", None):
            return
        if row.kind != self.kind:
            self.switch_pop.popdown()
            self.jump_to(row.kind, row.note_id)
            return
        self.select(row.note_id, from_list=True)
        self.switch_pop.popdown()
        GLib.idle_add(lambda: self.focus_text() and False)

    def set_mode(self, mode):
        self.flush()
        if self.current and is_empty(self.current):
            self.drop_empty(self.current)
        self.mode = mode
        self.current = None
        self.apply_trash_ui()
        self.fill_more_menu()
        notes = self.notes_for_mode()
        self.refresh_list()
        if notes:
            self.select(notes[0]["id"])

    def apply_trash_ui(self):
        trash = self.mode == "trash"
        for w in (self.pin_btn, self.del_btn, self.fmt_bar, self.label_btn, self.more_btn, self.share_btn, self.rem_btn):
            w.set_visible(not trash)
        self.color_btn.set_visible(not trash and self.kind == "notes")
        for w in (self.restore_btn, self.purge_btn):
            w.set_visible(trash)
        self.title.set_editable(not trash)
        self.text.set_editable(not trash)
        self.text.set_cursor_visible(not trash)
        self.writer.set_editable(not trash)
        self.latex.set_editable(not trash)
        (self.editor_box.add_css_class if trash else self.editor_box.remove_css_class)("trash")

    def select(self, nid, from_list=False):
        self.flush()
        old = self.current
        n = self.store.notes.get(nid)
        auto, self._auto_pos = getattr(self, "_auto_pos", False), False
        if old is not n:
            self.remember_pos()
        if old and old is not n and is_empty(old):
            self.drop_empty(old)
        if old and old is not n and old.get("file_auto") and not is_empty(old):
            self.sync_file(old, self.kind_of(old), force=True)      # Datei/Projektordner nach Titel benennen
        self.current = n
        if not n:
            return
        self.reload_if_changed(n, self.kind)
        self._loading = True
        if self.docs:
            self.writer.load(n.get("blocks") or [df.para()], n["title"], n.get("page"))
            view = n.get("view") or (self.writer.settings.get("last_view", "page") if is_empty(n) else "page")
            self.writer.set_flow(view == "flow")
        elif self.tex:
            self.latex.load(n["id"], n["text"], n["title"], n.get("source") or n.get("file"),
                            proj=os.path.dirname(n["file"]) if lk.is_project(n) else None)
        else:
            self.title.set_text(n["title"])
            self.load_rich(n)
        self.pin_btn.set_active(n["pinned"])
        self._loading = False
        self.active = {t for t in self.tags_at_cursor() if t in STYLES or t.startswith("font:")}
        self.set_saved(True)
        self.update_meta()
        self.update_fmt_buttons()
        self.right.set_visible_child_name("editor")
        self.update_switcher()
        self.apply_color()
        self.update_label_btn()
        self.update_rem_btn()
        self.fill_more_menu()
        if not self.docs:
            self.style_checks()
        if not from_list:
            self.refresh_list(keep=nid)
        self.apply_doc_lang()
        self.nav_note()
        if old is not n:
            self.offer_pos(n, auto)

    def drop_empty(self, n):
        """Leere, nie abgeglichene Notizen hinterlassen keine Spuren."""
        if not n["sync"]["keep_id"] and n["id"] in self.store.notes:
            try:
                os.remove(os.path.join(self.store.path, n["id"] + ".json"))
            except OSError:
                pass
            lk.discard(n)
            self.store.notes.pop(n["id"], None)

    # ================= Formatierung =================
    def font_tag(self, family):
        buf = self.text.get_buffer()
        name = "font:" + family
        tag = buf.get_tag_table().lookup(name)
        return tag or buf.create_tag(name, family=family)

    def our_tags(self):
        out = []
        self.text.get_buffer().get_tag_table().foreach(lambda t: out.append(t))
        return [t for t in out if t.props.name and (t.props.name in STYLES or t.props.name.startswith("font:"))]

    def load_rich(self, n):
        buf = self.text.get_buffer()
        buf.set_text(n["text"])
        self.note_images.clear()
        self.note_tables.clear()
        imgs = n.get("images") or []
        spots = [i for i, ch in enumerate(n["text"]) if ch == "\ufffc"]
        for k, off in reversed(list(enumerate(spots))):
            if k < len(imgs):
                s = buf.get_iter_at_offset(off)
                e = buf.get_iter_at_offset(off + 1)
                buf.delete(s, e)
                if imgs[k].get("table"):
                    t = imgs[k]["table"]
                    self.insert_note_table(t.get("rows"), t.get("style"), buf.get_iter_at_offset(off))
                else:
                    self.insert_note_image(imgs[k], buf.get_iter_at_offset(off))
        for start, end, name in n.get("rich", []):
            tag = self.font_tag(name[5:]) if name.startswith("font:") else buf.get_tag_table().lookup(name)
            if tag:
                buf.apply_tag(tag, buf.get_iter_at_offset(start), buf.get_iter_at_offset(end))
        buf.place_cursor(buf.get_start_iter())
        if not getattr(self, "_n_restoring", False):
            if self._n_pending:
                GLib.source_remove(self._n_pending)
                self._n_pending = None
            self.n_undo, self.n_redo = [], []
            self._n_last_full, self.n_last = self.note_snapshot()
            self.update_note_undo()

    def serialize_rich(self):
        buf = self.text.get_buffer()
        spans = []
        for tag in self.our_tags():
            it = buf.get_start_iter()
            while True:
                if not it.has_tag(tag) and not it.forward_to_tag_toggle(tag):
                    break
                start = it.get_offset()
                it.forward_to_tag_toggle(tag)
                spans.append([start, it.get_offset(), tag.props.name])
                if it.is_end():
                    break
        return sorted(spans)

    def tags_at_cursor(self):
        buf = self.text.get_buffer()
        it = buf.get_iter_at_mark(buf.get_insert())
        if not it.is_start():
            it.backward_char()  # wie in Textprogrammen: das Zeichen vor dem Cursor zählt
        return {t.props.name for t in it.get_tags() if t.props.name}

    def on_mark_set(self, buf, it, mark):
        if mark.get_name() in ("insert", "selection_bound") and not self._loading:
            self.active = {n for n in self.tags_at_cursor() if n in STYLES or n.startswith("font:")}
            self.update_fmt_buttons()
            had = getattr(self, "_had_sel", False)
            self._had_sel = buf.get_has_selection()
            if (had or self._had_sel) and not getattr(self, "_meta_id", None):   # Wortzahl der Markierung live
                self._meta_id = GLib.timeout_add(60, self._meta_tick)

    def _meta_tick(self):
        self._meta_id = None
        self.update_meta()
        return False

    def update_fmt_buttons(self):
        self._fmt_sync = True
        for name, b in self.fmt_buttons.items():
            b.set_active(name in self.active)
        fam = next((n[5:] for n in self.active if n.startswith("font:")), None)
        idx = next((i for i, (_, f) in enumerate(self.fonts) if f == fam), None)
        if idx is None and fam:  # eigene Schrift: in der Liste ergänzen
            self.fonts.append((fam, fam))
            self.font_drop.set_model(Gtk.StringList.new([l for l, _ in self.fonts] + ["Andere …"]))
            idx = len(self.fonts) - 1
        self.font_drop.set_selected(idx or 0)
        self._fmt_sync = False

    # ================= Rückgängig in Notizen (Text + Formatierung) =================
    def note_state(self):
        buf = self.text.get_buffer()
        return (buf.get_slice(buf.get_start_iter(), buf.get_end_iter(), True), tuple(map(tuple, self.serialize_rich())),
                tuple(i.get("img", "")[:40] + str(i.get("w")) + str(i.get("table", "")) for i in self.collect_note_images()))

    def note_cursor(self):
        buf = self.text.get_buffer()
        return buf.get_iter_at_mark(buf.get_insert()).get_offset()

    def note_snapshot(self):
        """Vollständiger Stand zum Wiederherstellen."""
        buf = self.text.get_buffer()
        return {"text": buf.get_slice(buf.get_start_iter(), buf.get_end_iter(), True), "rich": self.serialize_rich(),
                "images": [dict(i) for i in self.collect_note_images()]}, self.note_state()

    def note_changed(self):
        """Getipptes bündeln: ein Schritt pro Tipp-Pause (wie in Words)."""
        if self._loading or getattr(self, "_n_restoring", False) or self.n_last is None:
            return
        if self._n_pending is None:
            self._n_before = (self._n_last_snap(), self.note_cursor())
        else:
            GLib.source_remove(self._n_pending)
        self._n_pending = GLib.timeout_add(600, self.note_commit)

    def _n_last_snap(self):
        return getattr(self, "_n_last_full", None)

    def note_commit(self):
        self._n_pending = None
        before = self._n_before
        full, state = self.note_snapshot()
        if before and before[0] and state != self.n_last:
            self.n_undo.append(before)
            del self.n_undo[:-200]
            self.n_redo.clear()
        self.n_last, self._n_last_full = state, full
        self._n_before = None
        self.update_note_undo()
        return False

    def note_checkpoint(self):
        """Vor einer Formatierung: offenes Tippen abschließen und den jetzigen Stand als Schritt merken."""
        if self._n_pending:
            GLib.source_remove(self._n_pending)
            self.note_commit()
        full, state = self.note_snapshot()
        self._n_fmt_before = ((full, self.note_cursor()), state)

    def note_after_format(self):
        before, state0 = getattr(self, "_n_fmt_before", (None, None))
        full, state = self.note_snapshot()
        if before and state != state0:
            self.n_undo.append(before)
            del self.n_undo[:-200]
            self.n_redo.clear()
        self.n_last, self._n_last_full = state, full
        self.update_note_undo()

    def note_restore(self, snap, offset):
        self._n_restoring = True
        self._loading = True
        self.load_rich(snap)
        self._loading = False
        self._n_restoring = False
        buf = self.text.get_buffer()
        buf.place_cursor(buf.get_iter_at_offset(min(offset, buf.get_char_count())))
        self.text.scroll_mark_onscreen(buf.get_insert())
        full, state = self.note_snapshot()
        self.n_last, self._n_last_full = state, full
        self.style_checks()
        self.on_edit()
        self.update_note_undo()

    def note_undo(self):
        if self.mode == "trash" or not self.current:
            return
        if self._n_pending:
            GLib.source_remove(self._n_pending)
            self.note_commit()
        if not self.n_undo:
            return
        snap, off = self.n_undo.pop()
        self.n_redo.append((self._n_last_full, self.note_cursor()))
        self.note_restore(snap, off)

    def note_redo(self):
        if self.mode == "trash" or not self.n_redo:
            return
        snap, off = self.n_redo.pop()
        self.n_undo.append((self._n_last_full, self.note_cursor()))
        self.note_restore(snap, off)

    def update_note_undo(self):
        if hasattr(self, "note_undo_btn"):
            self.note_undo_btn.set_sensitive(bool(self.n_undo) or bool(self._n_pending))
            self.note_redo_btn.set_sensitive(bool(self.n_redo))

    def apply_to_selection(self, add, remove):
        """Tags auf die Markierung anwenden. Ohne Markierung nur für das nächste Tippen merken."""
        buf = self.text.get_buffer()
        bounds = buf.get_selection_bounds()
        if bounds:
            self.note_checkpoint()
            start, end = bounds
            for tag in remove:
                buf.remove_tag(tag, start, end)
            for tag in add:
                buf.apply_tag(tag, start, end)
            self.note_after_format()
            self.mark_dirty()
        names_add = {t.props.name for t in add}
        names_rm = {t.props.name for t in remove}
        self.active = (self.active - names_rm) | names_add
        self.text.grab_focus()

    def on_fmt_toggled(self, btn, name):
        if self._fmt_sync or not self.current or self.mode == "trash":
            return
        tag = self.text.get_buffer().get_tag_table().lookup(name)
        if btn.get_active():
            self.apply_to_selection([tag], [])
        else:
            self.apply_to_selection([], [tag])

    def on_font_selected(self, drop, _):
        if self._fmt_sync or not self.current:
            return
        i = drop.get_selected()
        if i >= len(self.fonts):  # "Andere …"
            def done(dlg, res):
                try:
                    fam = dlg.choose_family_finish(res)
                except GLib.Error:
                    fam = None
                if fam:
                    self.set_font(fam.get_name())
                else:
                    self.update_fmt_buttons()
            Gtk.FontDialog(title="Schriftart wählen").choose_family(self.win, None, None, done)
            return
        self.set_font(self.fonts[i][1])

    def set_font(self, family):
        old = [t for t in self.our_tags() if t.props.name.startswith("font:")]
        self.apply_to_selection([self.font_tag(family)] if family else [], old)
        self.update_fmt_buttons()

    def on_inserted(self, buf, loc, text, length):
        """Getippter Text übernimmt die gerade aktive Formatierung (wie in Word)."""
        if self._loading:
            return
        if text == " " and not self.docs and loc.get_line_offset() <= 12 and self.prefs.get("auto_lists", True):
            ln = loc.get_line()
            GLib.idle_add(lambda: self.auto_list(ln))
        elif text in ("*", "_", "~", "`") and not self.docs and self.prefs.get("markdown", True):
            ln = loc.get_line()
            GLib.idle_add(lambda: self.md_live(ln))
        if self.kind == "notes" and len(text) == 1:
            import autofmt
            autofmt.after_type(buf, loc, text, self.prefs)
        start = loc.copy()
        start.backward_chars(len(text))
        for tag in self.our_tags():
            if tag.props.name in self.active:
                buf.apply_tag(tag, start, loc)
            else:
                buf.remove_tag(tag, start, loc)

    # ================= Bearbeiten & Speichern =================
    def on_edit(self, *_):
        if self._loading or not self.current or self.mode == "trash":
            return
        if self.docs:
            self.current["title"] = self.writer.title.get_text()
            self.current["text"] = self.writer.plain_text()
            self.current["media"] = self.writer.has_media()
        elif self.tex:
            self.current["title"] = self.latex.title.get_text()
            self.current["text"] = self.latex.text()
        else:
            buf = self.text.get_buffer()
            self.current["title"] = self.title.get_text()
            self.current["text"] = buf.get_slice(buf.get_start_iter(), buf.get_end_iter(), True)
        self.mark_dirty()

    def mark_dirty(self):
        if self._save_id:
            GLib.source_remove(self._save_id)
        self.set_saved(False)
        self._save_id = GLib.timeout_add(500, self.flush)

    def set_saved(self, saved):
        if saved == "error":                               # Speichern selbst ist fehlgeschlagen
            self.save_state.set_label("󰀦 Nicht gespeichert")
            self.save_state.set_tooltip_text(f"Speichern hat nicht geklappt – Details in {ERROR_LOG}")
            self.save_state.set_css_classes(["saving"])
            return
        self.save_state.set_tooltip_text("Notizen speichern sich automatisch")
        self.save_state.set_label("󰄬 Gespeichert" if saved else "󰔟 Speichert …")
        self.save_state.set_css_classes(["saved" if saved else "saving"])

    # ================= Letzte Stelle =================
    # Je Eintrag: Cursor + oberste sichtbare Stelle. Beim Zurückkommen per Moduswechsel (notizen/words/latex/home)
    # springt notist direkt dorthin; sonst (Liste, nach Neustart) kurz ein Knopf „zur letzten stelle“.
    def pos_widgets(self, kind=None):
        kind = kind or self.kind
        if kind == "docs":
            return self.writer.view, self.writer.scroll
        if kind == "latex":
            if self.latex.buf is not self.latex.main_buf:      # Nebendatei offen: Stelle gilt nur für main.tex
                return None, None
            return self.latex.view, self.latex.tscroll
        return self.text, self.note_scroll

    def remember_pos(self):
        n = self.current
        if not n or self.view == "home" or is_empty(n):
            return
        v, sc = self.pos_widgets()
        if v is None:
            return
        buf = v.get_buffer()
        cur = buf.get_iter_at_mark(buf.get_insert()).get_offset()
        y = sc.get_vadjustment().get_value()
        it, top = v.get_line_at_y(int(y))
        pos = [cur, it.get_offset(), int(y - top), int(time.time())]
        self.session_pos = getattr(self, "session_pos", set())
        self.session_pos.add(n["id"])
        allp = self.prefs.setdefault("positions", {})
        allp.pop(n["id"], None)
        allp[n["id"]] = pos
        for k in list(allp)[:-300]:                # nur die letzten 300 Einträge behalten
            allp.pop(k, None)
        self.save_prefs()

    def offer_pos(self, n, auto):
        self.hide_jump()
        pos = self.prefs.get("positions", {}).get(n["id"]) if n else None
        if not pos or (pos[0] == 0 and pos[1] == 0 and pos[2] < 40):
            return
        if auto and self.prefs.get("keep_pos", True) and n["id"] in getattr(self, "session_pos", ()):
            self.restore_pos(n, pos)
        elif self.prefs.get("jump_btn", True):
            self.show_jump(n, pos)

    def restore_pos(self, n, pos):
        """Cursor setzen und hinscrollen – mehrfach, weil Words/LaTeX ihre Zeilenhöhen erst nach und nach kennen."""
        v, sc = self.pos_widgets()
        if v is None:
            return
        self._pos_seq = seq = getattr(self, "_pos_seq", 0) + 1
        if self.docs:
            self.writer.cancel_scroll_reset()
        buf = v.get_buffer()
        adj = sc.get_vadjustment()
        state = {"set": None}

        def apply(first=False):
            if seq != self._pos_seq or self.current is not n or self.view == "home":
                return False
            if not first and state["set"] is not None and abs(adj.get_value() - state["set"]) > 1:
                return False                       # inzwischen selbst gescrollt → nicht dazwischenfunken
            end = buf.get_end_iter().get_offset()
            if first:
                buf.place_cursor(buf.get_iter_at_offset(min(pos[0], end)))
            y, _h = v.get_line_yrange(buf.get_iter_at_offset(min(pos[1], end)))
            adj.set_value(y + pos[2])
            state["set"] = adj.get_value()
            return False
        GLib.timeout_add(30, lambda: apply(True))
        for ms in (160, 450, 1000):
            GLib.timeout_add(ms, apply)

    def build_jump(self):
        self.jump_rev = Gtk.Revealer(transition_type=Gtk.RevealerTransitionType.SLIDE_UP, transition_duration=180,
                                     halign=Gtk.Align.CENTER, valign=Gtk.Align.END, margin_bottom=56)
        b = Gtk.Button(label="󰁅 zur letzten stelle", focus_on_click=False, can_focus=False,
                       tooltip_text="Dorthin springen, wo du zuletzt in diesem Eintrag warst")
        b.add_css_class("jump-pill")
        b.connect("clicked", lambda *_: self.jump_now())
        self.jump_rev.set_child(b)
        self.jump_rev.set_can_target(False)
        hov = Gtk.EventControllerMotion()          # solange die Maus drauf ist, bleibt er
        hov.connect("enter", lambda *_: self._jump_timer(None))
        hov.connect("leave", lambda *_: self._jump_timer(2000))
        b.add_controller(hov)
        self.swipe.widget.add_overlay(self.jump_rev)
        self._jump, self._jump_id = None, None

    def _jump_timer(self, ms):
        if self._jump_id:
            GLib.source_remove(self._jump_id)
            self._jump_id = None
        if ms and self._jump:
            self._jump_id = GLib.timeout_add(ms, lambda: (self.hide_jump(), False)[1])

    def show_jump(self, n, pos):
        self._jump = (n, pos)
        self.jump_rev.set_can_target(True)
        self.jump_rev.set_reveal_child(True)
        self._jump_timer(4000)                      # verschwindet schnell wieder, wie eine Benachrichtigung

    def hide_jump(self):
        if not hasattr(self, "jump_rev"):
            return
        self._jump = None
        self._jump_timer(None)
        self.jump_rev.set_reveal_child(False)
        self.jump_rev.set_can_target(False)

    def jump_now(self):
        if self._jump and self.current is self._jump[0]:
            n, pos = self._jump
            self.restore_pos(n, pos)
            v, _sc = self.pos_widgets()
            if v is not None:
                v.grab_focus()
        self.hide_jump()

    def flush(self, force=False):
        if self._save_id or force:
            if self._save_id:
                GLib.source_remove(self._save_id)
            self._save_id = None
            ok = True
            if self.current and not is_empty(self.current) and self.mode != "trash":
                try:
                    if self.docs:
                        self.current["blocks"] = self.writer.to_model()
                        self.current["text"] = df.plain_text(self.current["blocks"])
                        self.current["page"] = dict(self.writer.page)
                    elif self.tex:
                        self.current["text"] = self.latex.text()
                    else:
                        self.current["rich"] = self.serialize_rich()
                        self.current["images"] = self.collect_note_images()
                        self.current["media"] = any(i.get("img") for i in self.current["images"])
                    self.store.save(self.current)
                except Exception:
                    ok = False
                    log_error("Speichern")
                # Alles danach ist Nachbereitung: ein Fehler dort darf die Anzeige nicht auf „Speichert …“
                # festhalten (so geschehen auf Ubuntu – gespeichert war trotzdem).
                for step in (lambda: self.store.snapshot(self.current),
                             lambda: self.sync_file(self.current, self.kind, force),
                             self.update_meta, self.refresh_list):
                    try:
                        step()
                    except Exception:
                        log_error("Nach dem Speichern")
            self.set_saved(True if ok else "error")
        return False

    def update_meta(self):
        n = self.current
        if n:
            when = f"gelöscht {nice_date(n['trashed_at'])}" if self.mode == "trash" and n["trashed_at"] \
                else f"geändert {nice_date(n['updated'])}"
            if self.kind == "notes" and self.prefs.get("show_words", True):   # Words/LaTeX zählen selbst
                words = len(n["text"].replace("\ufffc", " ").split())
                b = self.text.get_buffer().get_selection_bounds()
                if b:
                    sw = len(self.text.get_buffer().get_text(b[0], b[1], False).replace("\ufffc", " ").split())
                    when += f" · markiert: {sw} von {words} {'Wörtern' if words != 1 else 'Wort'}"
                else:
                    when += f" · {words} Wort{'e' if words != 1 else ''}"
            f = n.get("file")
            if f:
                short = f.replace(os.path.expanduser("~"), "~", 1)
                state = " (fehlt)" if n.get("file_missing") else " (nicht schreibbar)" if n.get("file_error") else ""
                when += f" · 󰈔 {os.path.basename(f)}{state}"
                self.meta.set_tooltip_text(f"Gespeichert direkt in {short}")
            else:
                self.meta.set_tooltip_text("Nur in notist gespeichert (keine Datei)")
            self.meta.set_label(f"· {when}")

    def tick(self):
        self.update_meta()
        if self.view == "home" and not self.home_search.get_text():
            self.refresh_home()          # „vor 3 Min“ aktuell halten
        return True

    def on_pin(self, btn):
        if self._loading or not self.current:
            return
        self.current["pinned"] = btn.get_active()
        if not is_empty(self.current):
            self.store.save(self.current)
        self.refresh_list()

    def new_note(self, *_, folder=None):
        if self.view == "home":               # Strg+N auf Home: im zuletzt benutzten Bereich
            self.set_kind(self.kind)
        if self.mode in ("trash", "archive"):
            self.set_mode("notes")
        title = self.writer.title if self.docs else self.latex.title if self.tex else self.title
        if self.current and is_empty(self.current):
            if folder is not None and (self.current.get("folder") or "") != lk.clean_folder(folder):
                self.move_to_folder(self.current, folder, quiet=True)
            title.grab_focus()
            return
        self.search.set_text("")
        n = self.store.create()
        n["want_file"] = True                      # bekommt beim ersten Speichern eine echte Datei
        if self.label_filter:
            n["labels"] = [self.label_filter]
        if folder:
            n["folder"] = lk.clean_folder(folder)
        if self.docs:
            n["blocks"] = [df.para()]
        self.active = set()
        self.select(n["id"])
        title.grab_focus()

    def delete_note(self, *_):
        n = self.current
        if not n or self.mode == "trash":
            return
        self.flush(force=True)
        if not is_empty(n):
            kind = self.kind
            self.ask_delete(kind, n, lambda with_file: self.trash_entry(kind, n, with_file))
            return
        self.drop_empty(n)
        self._undo = None
        self.current = None
        rest = self.notes_for_mode()
        if rest:
            self.select(rest[0]["id"])
        else:
            self.refresh_list()

    def undo_delete(self):
        if self._undo and self.view == "home":          # aus Home gelöscht: dort bleiben
            self.stores[getattr(self, "_undo_kind", self.kind)].restore(self._undo)
            self._undo = None
            self.toast.set_visible(False)
            self.refresh_home()
            return
        if self._undo:
            if getattr(self, "_undo_kind", self.kind) != self.kind:
                self.set_kind(self._undo_kind)
            self.store.restore(self._undo)
            if self.mode == "trash":
                self.set_mode("notes")
            self.select(self._undo["id"])
            self._undo = None
            self.toast.set_visible(False)

    def restore_note(self):
        n = self.current
        if n:
            self.store.restore(n)
            self.set_mode("notes")
            self.select(n["id"])
            self.notify("Wiederhergestellt")

    def purge_note(self):
        n = self.current
        if not n:
            return
        if not self._confirm_id:  # zweiter Klick bestätigt
            self.purge_btn.set_label("Wirklich? Nochmal klicken")
            self._confirm_id = GLib.timeout_add(3000, self.reset_confirm)
            return
        self.reset_confirm()
        self.store.delete_forever(n)
        self.current = None
        rest = self.store.trashed(self.search.get_text())
        self.refresh_list()
        if rest:
            self.select(rest[0]["id"])
        self.notify("Endgültig gelöscht")

    def reset_confirm(self):
        if self._confirm_id:
            GLib.source_remove(self._confirm_id)
        self._confirm_id = None
        self.purge_btn.set_label("󰩹 Endgültig löschen")
        return False

    def on_close(self, *_):
        self.flush()
        self.remember_pos()
        self.latex.shutdown()
        if backup.due(self.prefs):          # fällige Sicherung noch schnell erledigen
            try:
                b = backup.defaults(self.prefs)
                backup.backup_now(os.path.expanduser(b["dir"]), b["keep"])
                import datetime as _dt
                b["last"] = _dt.datetime.now().isoformat(timespec="seconds")
            except Exception:  # noqa: BLE001
                pass
        if self.current and is_empty(self.current):
            self.drop_empty(self.current)
        self.save_prefs()
        if self.background() and self.win:
            # nicht beenden, nur ausblenden – beim nächsten „notist“ ist das Fenster sofort wieder da
            self.keep_running()
            self.go_home()
            if getattr(self, "_settings_win", None):
                self._settings_win.close()
            self.win.set_visible(False)
            return True
        if getattr(self, "_held", False):
            self._held = False
            GLib.idle_add(lambda: (self.release(), False)[1])
        return False

    def notify(self, msg, undo=False):
        self.toast_label.set_label(msg)
        self.toast_btn.set_visible(undo)
        self.toast.set_visible(True)
        if self._toast_id:
            GLib.source_remove(self._toast_id)
        self._toast_id = GLib.timeout_add(6000, lambda: (self.toast.set_visible(False),
                                                         setattr(self, "_toast_id", None), False)[-1])


def check():
    """notes --check: zeigt, was installiert ist und was fehlt (für install.sh und zur Fehlersuche)."""
    import importlib.util, shutil, subprocess
    plain = "--plain" in sys.argv or not sys.stdout.isatty()
    ok = lambda b: ("ok" if b else "fehlt") if plain else ("\033[32mok\033[0m" if b else "\033[33mfehlt\033[0m")
    t = i18n.tr
    ok_ = ok
    ok = lambda b: t(ok_(b)) if plain else ok_(b).replace("fehlt", t("fehlt"))
    print(f"notist {VERSION}")
    print(f"  {t('Python-Module (gi, cairo)')} ".ljust(36, ".") + f" {ok(all(importlib.util.find_spec(m) for m in ('gi', 'cairo')))}")
    for lib, ver, what in (("Gtk", "4.0", t("Oberfläche")), ("Poppler", "0.18", t("LaTeX-Vorschau")),
                           ("PangoCairo", "1.0", t("PDF-Export"))):
        try:
            gi.require_version(lib, ver)
            good = True
        except ValueError:
            good = False
        print(f"  {lib}-{ver} ({what}) ".ljust(36, ".") + f" {ok(good)}")
    sp = spell.speller()
    print(f"  {t('Rechtschreibung')} ".ljust(36, ".") + f" {ok(sp.available)}" + (f" ({', '.join(sp.langs)})" if sp.available else
                                                                                f" – {spell.INSTALL_HINT}"))
    comps = lx.find_compilers()
    print(f"  {t('LaTeX-Compiler')} ".ljust(36, ".") + f" {ok(bool(comps))}" +
          (f" ({comps[0][0]})" if comps else " – " + t("lässt sich in der App mit einem Klick einrichten")))
    has_notify = bool(shutil.which("notify-send"))
    print(f"  {t('Erinnerungen (notify-send)')} ".ljust(36, ".") + f" {ok(has_notify)}" +
          ("" if has_notify else " – " + t("Paket libnotify-bin (Debian/Ubuntu) bzw. libnotify")))
    print(f"  {t('Symbolschrift (mitgeliefert)')} ".ljust(36, ".") + f" {ok(os.path.exists(ICON_FONT))}")
    print(f"  {t('Fenster')} ".ljust(36, ".") + " " + t("ohne Titelleiste (Kachel-Manager)" if tiling_desktop() else "mit Titelleiste"))
    return 0


if __name__ == "__main__":
    if "--check" in sys.argv:
        sys.exit(check())
    if "--remind" in sys.argv:               # vom systemd-Timer gestartet
        nid = sys.argv[sys.argv.index("--remind") + 1]
        app = Notes()
        app.register(None)
        if app.get_is_remote():                  # notist läuft: dort anzeigen (mit Klick zum Öffnen)
            app.activate_action("remind", GLib.Variant("s", nid))
            sys.exit(0)
        n = rem.mark_done(nid)
        if n:
            import shutil, subprocess
            title = n.get("title") or " ".join(n.get("text", "").split())[:40] or "Erinnerung"
            body = " ".join(n.get("text", "").replace("\ufffc", "").split())[:140]
            if shutil.which("notify-send"):
                subprocess.run(["notify-send", "-a", "notist", "-i", "notist", f"󰂚 {title}", body])
            else:
                note = Gio.Notification.new(f"󰂚 {title}")
                note.set_body(body)
                app.send_notification(f"rem-{nid}", note)
        sys.exit(0)
    if "--version" in sys.argv:
        print(f"notist {VERSION}")
        sys.exit(0)
    if "--settings" in sys.argv:             # notist --settings [seite]: Einstellungen öffnen (z. B. aus scourge)
        i = sys.argv.index("--settings")
        page = sys.argv[i + 1] if len(sys.argv) > i + 1 else ""
        app = Notes()
        app.register(None)
        if app.get_is_remote():
            app.activate_action("open-settings", GLib.Variant("s", page))
            sys.exit(0)
        app.connect("activate", lambda a: GLib.idle_add(lambda: (a.open_settings(page or None), False)[1]))
        sys.exit(app.run([sys.argv[0]]))
    if "--note" in sys.argv:                 # aus datist: Eintrag zur Erinnerung öffnen
        nid = sys.argv[sys.argv.index("--note") + 1]
        app = Notes()
        app.register(None)
        if app.get_is_remote():
            app.activate_action("open-note", GLib.Variant("s", nid))
            sys.exit(0)
        app.connect("activate", lambda a: GLib.idle_add(lambda: (a.open_note(nid), False)[1]))
        sys.exit(app.run([sys.argv[0]]))
    if "--quit" in sys.argv:                 # wirklich beenden (z. B. nach einem Update)
        app = Notes()
        app.register(None)
        if app.get_is_remote():
            app.activate_action("quit", None)
        sys.exit(0)
    if "--daemon" in sys.argv:               # Autostart: im Hintergrund bereithalten (schneller erster Start)
        app = Notes()
        app.register(None)
        if app.get_is_remote():
            sys.exit(0)
        app.daemon = True
        sys.exit(app.run([sys.argv[0]]))
    sys.exit(Notes().run(sys.argv))
