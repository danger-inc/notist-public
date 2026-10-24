# Dokument-Modus von notist: ein kleines Textverarbeitungsprogramm auf Basis von Gtk.TextView.
# Seite (A4) wird unter den Text gezeichnet, Formatierung steckt in TextTags, Tabellen/Linien/Seitenumbrüche
# sind eingebettete Widgets. Das Dokument-Modell (Blöcke) und DOCX/PDF stecken in docfmt.py / render.py.
import base64, copy, datetime, math, os, re

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Graphene", "1.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gdk, GdkPixbuf, Gio, GLib, GObject, Graphene, Gtk, Pango

import docfmt as df
import i18n
from mdnotes import looks_like_markdown as md_detect

A4_W, A4_H, PAGE_M = 794, 1123, 94          # px bei 96 dpi, Rand 2,5 cm
DESK = 28                                    # Abstand Seite ↔ Fensterrand
PAGE_GAP = 28                                # Abstand zwischen zwei Seiten am Bildschirm
STEP = 24                                    # Einzug je Ebene (px bei 100 %)
FONT_SIZES = (8, 9, 10, 10.5, 11, 12, 14, 16, 18, 20, 24, 28, 32, 36, 48, 60, 72)
LINE_SPACINGS = (1.0, 1.15, 1.5, 2.0, 2.5, 3.0)
ZOOMS = (0.5, 0.67, 0.75, 0.9, 1.0, 1.1, 1.25, 1.5, 1.75, 2.0)
PALETTE = ("#000000", "#434343", "#666666", "#999999", "#cccccc", "#ffffff",
           "#c00000", "#e06666", "#ff9900", "#ffd966", "#38761d", "#93c47d",
           "#0b5394", "#6fa8dc", "#674ea7", "#b4a7d6", "#a64d79", "#d5a6bd")
SYMBOLS = ("€", "§", "„", "“", "‚", "‘", "»", "«", "–", "—", "…", "•", "·", "°", "±", "×", "÷", "≈", "≠", "≤",
           "≥", "∞", "√", "½", "¼", "¾", "²", "³", "µ", "‰", "→", "←", "↑", "↓", "⇒", "✓", "✗", "★", "♥", "©",
           "®", "™", "α", "β", "γ", "δ", "π", "Σ", "Ω", "Δ")
HL_PALETTE = ("#ffff00", "#00ff00", "#00ffff", "#ff00ff", "#ffc000", "#ff7f7f", "#c9daf8", "#d9ead3")
CHAR_PREFIX = ("font:", "size:", "fg:", "hl:", "link:")
CHAR_PLAIN = ("b", "i", "u", "s", "sup", "sub")
PARA_PREFIX = ("ps:", "pa:", "pl:", "pi:", "pz:", "m:")
STYLE_TAG = {  # Formatvorlagen im Editor (Größe in pt wie in docfmt.STYLE_FMT)
    "title": dict(weight=800, size_points=26, pixels_below_lines=14),
    "h1": dict(weight=Pango.Weight.BOLD, size_points=20, pixels_above_lines=18, pixels_below_lines=6),
    "h2": dict(weight=Pango.Weight.BOLD, size_points=16, pixels_above_lines=14, pixels_below_lines=4),
    "h3": dict(weight=Pango.Weight.BOLD, size_points=13, pixels_above_lines=10, pixels_below_lines=2),
    "quote": dict(style=Pango.Style.ITALIC),
    "code": dict(family=df.MONO_FONT, size_points=10, pixels_below_lines=0),
}

CSS = """
.writer-tools { margin: 2px 0 6px 0; }
.writer-tools flowboxchild { padding: 0; margin: 0; background: none; outline: none; }
.wgroup { padding: 0 6px 0 0; margin-right: 6px; border-right: 2px solid alpha(@color9, 0.18); }
.wgroup.last { border-right: none; }
button.wt, menubutton.wt > button, togglebutton.wt {
    background: none; box-shadow: none; border: 2px solid transparent; border-radius: 9px;
    min-height: 24px; min-width: 22px; padding: 0 4px; color: @foreground; font-weight: 700; font-size: 13px;
}
button.wt:hover, menubutton.wt > button:hover { background-color: alpha(@color9, 0.14); }
button.wt:checked, menubutton.wt > button:checked { background-color: @color9; color: @background; }
button.wt:disabled { color: alpha(@foreground, 0.3); }
.wt-swatch-bar { min-height: 3px; border-radius: 2px; margin: 0 2px; }
entry.doc-title { background: none; border: none; box-shadow: none; outline: none; padding: 0;
    font-size: 20px; font-weight: 800; color: @foreground; min-height: 32px; }
.desk { background-color: alpha(@background, 0.55); border-radius: 11px; }
.glass .desk { background-color: alpha(@background, 0.25); }
textview.page, textview.page text { background: none; color: @foreground; caret-color: @color9; }
textview.page { font-family: "Noto Sans", "DejaVu Sans", sans-serif; font-size: 11pt; }
textview.page.light, textview.page.light text { color: #1d1d1d; }
textview.page.light text selection { background-color: alpha(#3d7be0, 0.35); color: #1d1d1d; }
textview.page.light { caret-color: #1d1d1d; }
.wtable { border-radius: 0; }
.wtable textview, .wtable textview text { background: none; font-size: 10pt; font-family: "Noto Sans", sans-serif; }
.wtable .cell { border: 0 solid alpha(@foreground, 0.35); padding: 4px 7px; }
.wtable.pad-compact .cell { padding: 1px 5px; }
.wtable.pad-wide .cell { padding: 9px 12px; }
.wtable.b-grid .cell { border-right-width: 1px; border-bottom-width: 1px; }
.wtable.b-grid .cell.firstrow { border-top-width: 1px; }
.wtable.b-grid .cell.firstcolumn { border-left-width: 1px; }
.wtable.b-rows .cell { border-bottom-width: 1px; }
.wtable.b-rows .cell.firstrow { border-top-width: 1px; }
.wtable.b-outer .cell.firstrow { border-top-width: 1px; }
.wtable.b-outer .cell.lastrow { border-bottom-width: 1px; }
.wtable.b-outer .cell.firstcolumn { border-left-width: 1px; }
.wtable.b-outer .cell.lastcol { border-right-width: 1px; }
.wtable.b-none .cell { border-right-width: 1px; border-bottom-width: 1px; border-style: dashed;
    border-color: alpha(@foreground, 0.10); }
.wtable.b-none .cell.lastcol { border-right-width: 0; }
.wtable.b-none .cell.lastrow { border-bottom-width: 0; }
.wtable .cell.head { background-color: alpha(@foreground, 0.08); }
.wtable .cell.head textview, .wtable .cell.firstcol textview { font-weight: 700; }
.wtable .cell.odd { background-color: alpha(@foreground, 0.05); }
.light .wtable .cell { border-color: rgba(0,0,0,0.4); }
.light .wtable.b-none .cell { border-color: rgba(0,0,0,0.10); }
.light .wtable .cell.odd { background-color: rgba(0,0,0,0.04); }
togglebutton.tchip, button.tchip { background: none; background-image: none; box-shadow: none; min-height: 24px;
    padding: 0 6px; border-radius: 6px; border: 1px solid alpha(@primary, 0.25); color: @foreground; font-size: 12px; }
togglebutton.tchip:hover, button.tchip:hover { border-color: @primary; }
togglebutton.tchip:checked { background-color: alpha(@primary, 0.22); border-color: @primary; }
.tsub { font-size: 11px; color: @secondary; }
button.tcol { min-width: 22px; min-height: 22px; padding: 0; font-size: 12px; }
button.tcol.cur { border-color: @foreground; border-width: 2px; }
.wtable textview, .wtable textview text { color: @foreground; }
.light .wtable textview, .light .wtable textview text { color: #1d1d1d; }
.light .wtable .cell.head { background-color: rgba(0,0,0,0.06); }
.tsize-lbl { font-size: 11px; opacity: 0.8; }
.wtable .cell.colsel { box-shadow: inset 0 0 0 2px alpha(@primary, 0.75); }
.wtable-bar button { padding: 0 6px; min-height: 18px; font-size: 11px; border-radius: 7px; }
.whr { min-height: 2px; background-color: alpha(@foreground, 0.4); margin: 9px 0; }
.light .whr { background-color: rgba(0,0,0,0.45); }
.wpb { font-size: 10px; font-weight: 800; letter-spacing: 2px; color: alpha(@foreground, 0.45);
    border-top: 2px dashed alpha(@foreground, 0.3); padding-top: 2px; margin: 8px 0; }
.light .wpb { color: rgba(0,0,0,0.45); border-color: rgba(0,0,0,0.3); }
.findbar { margin: 0 0 6px 0; }
.findbar entry { min-height: 26px; }
.wstatus { font-size: 11px; color: alpha(@foreground, 0.55); }
.wstatus button { padding: 0 6px; min-height: 18px; }
popover.wpop > contents { background-color: alpha(@background, 0.96); background-image: none; border: 1px solid @primary;
    border-radius: 6px; padding: 8px; box-shadow: 0 8px 22px rgba(0,0,0,0.3); margin-top: 4px; }
.glass popover.wpop > contents { background-color: alpha(@background, 0.88); }
popover.wpop.tdesign > contents, .glass popover.wpop.tdesign > contents { background-color: @background; }
button.swatch-b { min-width: 20px; min-height: 20px; padding: 0; border-radius: 6px; border: 2px solid alpha(@foreground, 0.2); }
button.swatch-b:hover { border-color: @foreground; }
.wpop-head { font-size: 12px; font-weight: 800; letter-spacing: 0.3px; color: @primary; padding: 0 2px 4px 2px;
    border-bottom: 1px solid alpha(@primary, 0.25); margin-bottom: 2px; }
/* Menüband (Words) */
.ribbon { background-color: alpha(@background, 0.5); border-radius: 12px; padding: 3px 6px 2px 6px; margin: 4px 0 8px 0; }
.glass .ribbon { background-color: alpha(@background, 0.25); }
.ribbon-tabs { padding-bottom: 2px; }
button.rtab { background: none; background-image: none; border: none; box-shadow: none; border-radius: 8px;
    padding: 0 12px; min-height: 26px; font-weight: 800; font-size: 12px; color: alpha(@foreground, 0.55); }
button.rtab:hover { color: @foreground; background-color: alpha(@color9, 0.1); }
button.rtab:checked { color: @foreground; box-shadow: inset 0 -3px @color9; border-radius: 8px 8px 2px 2px; }
menubutton.file-tab > button { background-color: @color9; background-image: none; color: @background; border: none;
    border-radius: 8px; padding: 0 12px; min-height: 26px; font-weight: 800; font-size: 12px; box-shadow: none; margin-right: 6px; }
menubutton.file-tab > button:hover, menubutton.file-tab > button:checked { background-color: alpha(@color9, 0.85); }
/* Datei-Menü (Words): wie die Popover der Suite – 1 px @primary, 6 px Rundung, Hover gefüllt */
popover.file-menu > contents { border: 1px solid @primary; border-radius: 6px; padding: 6px; min-width: 300px;
    background-color: alpha(@background, 0.96); background-image: none; box-shadow: 0 8px 22px rgba(0,0,0,0.3);
    margin-top: 4px; }
.glass popover.file-menu > contents { background-color: alpha(@background, 0.88); }
.fm-head { padding: 2px 8px 6px 8px; margin-bottom: 2px; border-bottom: 1px solid alpha(@primary, 0.25); }
.fm-title { color: @primary; font-weight: 800; font-size: 13px; }
.fm-sub { color: @secondary; font-size: 11px; }
.fm-sec { padding: 8px 8px 2px 8px; }
.fm-sec-title { color: @primary; font-size: 11px; font-weight: 800; letter-spacing: 0.5px; }
.fm-line { background-color: alpha(@primary, 0.3); min-height: 1px; }
popover.file-menu button.fm-item { background: none; background-image: none; border: none; box-shadow: none;
    border-radius: 4px; padding: 4px 8px; min-height: 0; color: @foreground; font-size: 13px; }
popover.file-menu button.fm-item:hover, popover.file-menu button.fm-item:focus-visible {
    background-color: @primary; color: @on_primary; }
.fm-icon { color: @primary; min-width: 18px; }
.fm-hint { color: alpha(@foreground, 0.45); font-size: 11px; }
popover.file-menu button.fm-item:hover .fm-icon, popover.file-menu button.fm-item:hover .fm-hint { color: @on_primary; }
.ribbon-page { padding: 4px 0 0 0; border-top: 1px solid alpha(@color9, 0.15); }
.rgroup { padding: 2px 10px 0 8px; border-right: 1px solid alpha(@color9, 0.18); }
.rgroup.last { border-right: none; }
.rgroup-cap { font-size: 9px; font-weight: 700; letter-spacing: 0.5px; color: alpha(@foreground, 0.42); margin-top: 1px; }
button.rbig, menubutton.rbig > button { min-width: 50px; padding: 2px 6px; min-height: 44px; }
.rbig-icon { font-size: 19px; }
.rbig-label { font-size: 10.5px; font-weight: 700; }
button.style-chip { background-color: alpha(@foreground, 0.05); background-image: none; border: 2px solid alpha(@color9, 0.18);
    border-radius: 8px; padding: 0 8px; min-height: 30px; box-shadow: none; color: @foreground; font-size: 12px; }
button.style-chip:hover { border-color: alpha(@color9, 0.6); }
button.style-chip:checked { border-color: @color9; background-color: alpha(@color9, 0.16); color: @foreground; }
button.sym-b { min-width: 28px; min-height: 28px; padding: 0; border-radius: 7px; background-image: none; box-shadow: none;
    background-color: alpha(@foreground, 0.06); border: 1px solid transparent; font-size: 15px; }
button.sym-b:hover { border-color: @color9; background-color: alpha(@color9, 0.15); }
.stat-v { font-weight: 800; color: @color9; }
.nav-pane { background-color: alpha(@background, 0.55); border-radius: 11px; padding: 8px 6px; margin-right: 8px; }
.glass .nav-pane { background-color: alpha(@background, 0.25); }
.nav-head { font-size: 11px; font-weight: 800; letter-spacing: 1px; color: @color9; margin: 0 6px 6px 6px; }
.nav-pane list { background: none; }
.nav-pane row { border-radius: 7px; padding: 3px 6px; }
.nav-pane row:hover { background-color: alpha(@color9, 0.12); }
.nav-pane row:selected { background-color: alpha(@color9, 0.22); color: @foreground; }
.nav-h1 { font-weight: 800; font-size: 12px; } .nav-h2 { font-size: 12px; } .nav-h3 { font-size: 11px; color: alpha(@foreground, 0.7); }
.nav-title { font-weight: 800; font-size: 13px; color: @color9; }
.nav-empty { font-size: 11px; color: alpha(@foreground, 0.5); margin: 4px 6px; }
.wtoc { border-top: 1px solid alpha(@foreground, 0.25); border-bottom: 1px solid alpha(@foreground, 0.25); padding: 6px 0; }
.wtoc-title { font-family: "Noto Sans"; font-weight: 800; font-size: 14pt; }
.wtoc-entry { background: none; background-image: none; box-shadow: none; border: none; padding: 1px 2px; min-height: 0;
    font-family: "Noto Sans"; font-size: 11pt; font-weight: 400; border-radius: 4px; }
.wtoc-entry:hover { background-color: alpha(@color9, 0.15); }
.wtoc-l1 { font-weight: 700; }
.wtoc label { font-family: "Noto Sans", sans-serif; }
.wtoc-dots, .wtoc-empty { color: alpha(@foreground, 0.4); }
.light .wtoc-entry, .light .wtoc-title, .light .wtoc-entry label { color: #1d1d1d; }
.light .wtoc { border-color: rgba(0,0,0,0.25); }
button.wtoc-rm { background: none; background-image: none; box-shadow: none; border: none; min-height: 0; padding: 0 6px;
    color: alpha(@foreground, 0.4); }
menubutton.wfn > button { background: none; background-image: none; box-shadow: none; border: none; padding: 0 1px;
    min-height: 0; min-width: 0; margin: 0; font-size: 8pt; font-weight: 800; color: @color9; }
.light menubutton.wfn > button { color: #0b5394; }
menubutton.wfn > button:hover { background-color: alpha(@color9, 0.2); }
textview.wfn-edit, textview.wfn-edit text { background-color: alpha(@foreground, 0.06); }
.hf-help { font-size: 11px; color: alpha(@foreground, 0.6); }
scale.zoom { min-width: 110px; padding: 0 4px; }
scale.zoom trough { min-height: 4px; border-radius: 2px; background-color: alpha(@foreground, 0.15); }
scale.zoom highlight { background-color: @color9; border-radius: 2px; }
scale.zoom slider { min-width: 5px; min-height: 14px; border-radius: 3px; background-color: @foreground; background-image: none;
    box-shadow: none; border: none; margin: -5px 0; }
"""


def rgba(hexstr, alpha=1.0):
    c = Gdk.RGBA()
    c.parse(hexstr)
    c.alpha = alpha
    return c


def pixel_texture(data, w, h):
    """Bilddaten → Gdk.Texture in Anzeigegröße."""
    loader = GdkPixbuf.PixbufLoader()
    loader.write(data)
    loader.close()
    pb = loader.get_pixbuf()
    w, h = max(1, round(w)), max(1, round(h))
    if (w, h) != (pb.get_width(), pb.get_height()):
        pb = pb.scale_simple(w, h, GdkPixbuf.InterpType.BILINEAR)
    return Gdk.Texture.new_for_pixbuf(pb)


class WrapLayout(Gtk.LayoutManager):
    """Kinder nebeneinander, bei Platzmangel in die nächste Zeile (wie Wörter im Fließtext)."""

    def __init__(self, spacing=4, row_spacing=4):
        super().__init__()
        self.spacing, self.row_spacing = spacing, row_spacing

    def do_get_request_mode(self, widget):
        return Gtk.SizeRequestMode.HEIGHT_FOR_WIDTH

    def kids(self, widget):
        c = widget.get_first_child()
        while c:
            if c.should_layout():
                yield c
            c = c.get_next_sibling()

    def rows(self, widget, width):
        rows, cur, x = [], [], 0
        for c in self.kids(widget):
            w = c.measure(Gtk.Orientation.HORIZONTAL, -1)[1]
            if cur and x + self.spacing + w > width:
                rows.append(cur)
                cur, x = [], 0
            x += (self.spacing if cur else 0) + w
            cur.append((c, w))
        if cur:
            rows.append(cur)
        return rows

    def do_measure(self, widget, orientation, for_size):
        kids = list(self.kids(widget))
        if orientation == Gtk.Orientation.HORIZONTAL:
            mins = [c.measure(orientation, -1)[0] for c in kids]
            nats = [c.measure(orientation, -1)[1] for c in kids]
            return max(mins or [0]), sum(nats) + self.spacing * max(0, len(kids) - 1), -1, -1
        width = for_size if for_size > 0 else 10 ** 6
        h = 0
        for i, row in enumerate(self.rows(widget, width)):
            h += max(c.measure(Gtk.Orientation.VERTICAL, w)[1] for c, w in row) + (self.row_spacing if i else 0)
        return h, h, -1, -1

    def do_allocate(self, widget, width, height, baseline):
        y = 0
        for row in self.rows(widget, width):
            rh = max(c.measure(Gtk.Orientation.VERTICAL, w)[1] for c, w in row)
            x = 0
            for c, w in row:
                c.size_allocate(_rect(x, y, w, rh), -1)
                x += w + self.spacing
            y += rh + self.row_spacing


def _accent_css():
    out = []
    for i, c in enumerate(df.TABLE_ACCENTS):
        out.append(f".wtable.acc-{i} .cell {{ border-color: alpha({c}, 0.75); }} "
                   f".wtable.acc-{i}.b-none .cell {{ border-color: alpha({c}, 0.2); }} "
                   f".wtable.acc-{i} .cell.head {{ background-color: {c}; }} "
                   f".wtable.acc-{i} .cell.head textview, .wtable.acc-{i} .cell.head textview text {{ color: #ffffff; }} "
                   f".wtable.acc-{i} .cell.odd {{ background-color: alpha({c}, 0.16); }} "
                   f".wtable.acc-{i} .cell.firstcol {{ background-color: alpha({c}, 0.09); }} "
                   f"button.swatch-b.tcol-{i} {{ background-color: {c}; background-image: none; }}")
    return "\n".join(out)


CSS += _accent_css()


def _rect(x, y, w, h):
    r = Gdk.Rectangle()
    r.x, r.y, r.width, r.height = int(x), int(y), int(w), int(h)
    return r


def tool(label, tip, cb=None, toggle=False, markup=False):
    b = Gtk.ToggleButton() if toggle else Gtk.Button()
    lab = Gtk.Label()
    (lab.set_markup if markup else lab.set_label)(label)
    b.set_child(lab)
    b.set_tooltip_text(tip)
    b.set_focus_on_click(False)
    b.set_can_focus(False)
    b.add_css_class("wt")
    if cb:
        b.connect("toggled" if toggle else "clicked", cb)
    return b


FILE_MENU = (
    (None, (("󰝰", "Öffnen / importieren …", "strg+o", "win.doc-import"),)),
    ("Exportieren", (("󰈬", "Word-Dokument", ".docx", "win.doc-export::docx"),
                     ("󰈙", "LibreOffice-Dokument", ".odt", "win.doc-export::odt"),
                     ("󰈦", "PDF", ".pdf", "win.doc-export::pdf"),
                     ("󰦨", "Text", ".txt", "win.doc-export::txt"),
                     ("󰍔", "Markdown", ".md", "win.doc-export::md"),
                     ("󰖟", "Webseite", ".html", "win.doc-export::html"))),
    ("Weiteres", (("󰐪", "Drucken …", "", "win.doc-print"),
                  ("󰿈", "In ein LaTeX-Dokument umwandeln", "", "win.doc-to-latex"))),
)


def file_menu(entries=FILE_MENU, sub="Wird beim Schreiben automatisch gespeichert", title="Datei", pop=None):
    """Datei-Menü im Stil der Suite: Kopf, Rubriken mit Linie, Einträge mit Symbol und Kürzel rechts.
    Ein Eintrag (Symbol, Text, Kürzel, Aktion[, roh]) – roh=True lässt den Text unverändert (z. B. Ordnernamen).
    pop: vorhandenes Popover neu befüllen."""
    if pop is None:
        pop = Gtk.Popover(has_arrow=False, halign=Gtk.Align.START)
        pop.add_css_class("file-menu")
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
    head = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    head.add_css_class("fm-head")
    t = Gtk.Label(label=i18n.tr(title).lower(), xalign=0)
    t.add_css_class("fm-title")
    head.append(t)
    if sub:
        sl = Gtk.Label(label=sub, xalign=0)
        sl.add_css_class("fm-sub")
        head.append(sl)
    box.append(head)
    for title, items in entries:
        if title:
            row = Gtk.Box(spacing=8)
            row.add_css_class("fm-sec")
            lab = Gtk.Label(label=i18n.tr(title).lower(), xalign=0)
            lab.add_css_class("fm-sec-title")
            line = Gtk.Box(hexpand=True, valign=Gtk.Align.CENTER)
            line.add_css_class("fm-line")
            row.append(lab); row.append(line)
            box.append(row)
        for icon, label, hint, action, *raw in items:
            b = Gtk.Button(focus_on_click=False)
            b.add_css_class("fm-item")
            b.set_action_name(action) if "::" not in action else b.set_detailed_action_name(action)
            r = Gtk.Box(spacing=10)
            i = Gtk.Label(label=icon)
            i.add_css_class("fm-icon")
            l = Gtk.Label(label=label if raw and raw[0] else i18n.tr(label).lower(), xalign=0, hexpand=True,
                          ellipsize=3, max_width_chars=40)
            r.append(i); r.append(l)
            if hint:
                h = Gtk.Label(label=hint)
                h.add_css_class("fm-hint")
                r.append(h)
            b.set_child(r)
            b.connect("clicked", lambda *_: pop.popdown())
            box.append(b)
    pop.set_child(box)
    return pop


def font_dropdown(dd):
    """Schriftauswahl: jede Schrift wird in sich selbst angezeigt, Liste ist durchsuchbar."""
    fac = Gtk.SignalListItemFactory()

    def setup(f, item):
        lab = Gtk.Label(xalign=0)
        lab.add_css_class("fontrow")
        item.set_child(lab)

    def bind(f, item):
        name = item.get_item().get_string()
        lab = item.get_child()
        lab.set_label(name)
        attrs = Pango.AttrList()
        if not name.endswith("…") and name not in ("Standard", "Normal", "Sans", "Serif"):
            attrs.insert(Pango.attr_family_new(name))
        lab.set_attributes(attrs)
    fac.connect("setup", setup)
    fac.connect("bind", bind)
    dd.set_expression(Gtk.PropertyExpression.new(Gtk.StringObject, None, "string"))
    dd.set_enable_search(True)
    try:
        dd.set_search_match_mode(Gtk.StringFilterMatchMode.SUBSTRING)
    except AttributeError:
        pass
    dd.set_list_factory(fac)          # erst danach – set_expression setzt die Anzeige sonst zurück

    def entries(w):
        c = w.get_first_child()
        while c:
            if isinstance(c, Gtk.SearchEntry):
                c.set_placeholder_text("Schrift suchen …")
            entries(c)
            c = c.get_next_sibling()
    entries(dd)
    return dd


def big_label(icon, text):
    """Großer Knopfinhalt wie im Word-Menüband: Symbol oben, Text darunter."""
    v = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
    i = Gtk.Label(label=icon)
    i.add_css_class("rbig-icon")
    t = Gtk.Label(label=text)
    t.add_css_class("rbig-label")
    v.append(i)
    v.append(t)
    return v


def big_tool(icon, text, tip, cb=None, toggle=False):
    b = Gtk.ToggleButton() if toggle else Gtk.Button()
    b.set_child(big_label(icon, text))
    b.set_tooltip_text(tip)
    b.set_focus_on_click(False)
    b.set_can_focus(False)
    b.add_css_class("wt")
    b.add_css_class("rbig")
    if cb:
        b.connect("toggled" if toggle else "clicked", cb)
    return b


def _lower_heads(w):
    """Überschriften in Popovern klein wie im Datei-Menü (Quelltext/Übersetzung bleibt GROSS)."""
    c = w.get_first_child() if w else None
    while c:
        if isinstance(c, Gtk.Label) and c.has_css_class("wpop-head"):
            t = c.get_label()
            if t and t != t.lower():
                low = t.lower()
                if i18n.LANG == "de":
                    low = low.replace("fuss", "fuß")
                c.set_label(low)
        _lower_heads(c)
        c = c.get_next_sibling()


def ist_pop(pop):
    """Popover im Stil der Suite: ohne Pfeil, 1 px @primary, kleine Überschriften (siehe CSS .wpop)."""
    pop.set_has_arrow(False)
    pop.add_css_class("wpop")
    pop.connect("show", lambda p: _lower_heads(p))
    return pop


def ist_tree(root):
    """Alle Auswahllisten und Popover-Knöpfe unter root auf den Suite-Stil bringen."""
    stack = [root]
    while stack:
        w = stack.pop()
        if isinstance(w, Gtk.DropDown):
            c = w.get_first_child()
            while c:
                if isinstance(c, Gtk.Popover):
                    c.set_has_arrow(False)
                c = c.get_next_sibling()
        elif isinstance(w, Gtk.MenuButton):
            p = w.get_popover()
            if p is not None and not p.has_css_class("file-menu") and not p.has_css_class("wpop-done"):
                p.add_css_class("wpop-done")
                ist_pop(p)
        c = w.get_first_child()
        while c:
            stack.append(c)
            c = c.get_next_sibling()


def keep_focus(mb, pop):
    """Popover mit Eingabefeldern: der Knopf muss fokussierbar sein (can_focus=False sperrt in GTK4 auch alles im
    Popover – Felder ließen sich nicht beschreiben). Damit der Knopf dem Editor trotzdem keinen Fokus stiehlt,
    geht der Fokus beim Schließen dorthin zurück, wo er vorher war."""
    mb.set_can_focus(True)
    mb.set_focus_on_click(False)
    mem = {}

    def track_root(*_):
        root = mb.get_root()
        if root is None or getattr(root, "_ist_focus_tracked", False):
            return
        root._ist_focus_tracked = True

        def track(r, _ps):
            f = r.get_focus()
            if f is not None and f.get_ancestor(Gtk.Popover) is None and f.get_ancestor(Gtk.MenuButton) is None:
                r._ist_last_focus = f
        root.connect("notify::focus-widget", track)
        track(root, None)
    mb.connect("realize", track_root)

    def show(_p):                          # „show“ kommt erst, wenn der Fokus schon im Popover ist
        root = mb.get_root()
        mem["w"] = getattr(root, "_ist_last_focus", None) if root else None

    def closed(_p):
        w = mem.pop("w", None)
        if w is None:
            return

        def back():                        # GTK setzt den Fokus erst nach „closed“ auf den Knopf
            root = mb.get_root()
            f = root.get_focus() if root else None
            if w.get_mapped() and (f is None or f is mb or f.is_ancestor(mb) or f.is_ancestor(pop)):
                w.grab_focus()
            return False
        GLib.timeout_add(40, back)
    pop.connect("show", show)
    pop.connect("closed", closed)


def popover_button(label, tip, child, big=False):
    mb = Gtk.MenuButton(tooltip_text=tip, focus_on_click=False)
    if isinstance(label, Gtk.Widget):
        mb.set_child(label)
    else:
        lab = Gtk.Label()
        lab.set_markup(label)
        mb.set_child(lab)
    mb.add_css_class("wt")
    if big:
        mb.add_css_class("rbig")
    pop = ist_pop(Gtk.Popover())
    pop.set_child(child)
    mb.set_popover(pop)
    keep_focus(mb, pop)
    return mb, pop


def close_outside(pop):
    """Popover ohne autohide (Touch-sicher, siehe TableBlock): schließt bei Klick/Tipp außerhalb und mit Esc.
    Der Fenster-Handler sieht auch Tipps ins Popover – die meldet das Popover selbst erst danach, daher im Idle."""
    st = {"t": 0, "ctrl": None}
    inner = Gtk.GestureClick(button=0)
    inner.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
    inner.connect("pressed", lambda *_: st.update(t=GLib.get_monotonic_time()))
    pop.add_controller(inner)
    esc = Gtk.EventControllerKey()
    esc.connect("key-pressed", lambda _c, kv, *_: kv == Gdk.KEY_Escape and (pop.popdown(), True)[1])
    pop.add_controller(esc)

    def late():
        if GLib.get_monotonic_time() - st["t"] > 300_000 and pop.get_visible():
            pop.popdown()
        return False

    def show(*_):
        root = pop.get_root()
        if root is not None and st["ctrl"] is None:
            g = Gtk.GestureClick(button=0)
            g.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
            g.connect("pressed", lambda *_: GLib.idle_add(late))
            root.add_controller(g)
            st["ctrl"] = (root, g)

    def closed(*_):
        if st["ctrl"] is not None:
            root, g = st["ctrl"]
            st["ctrl"] = None
            root.remove_controller(g)
    pop.connect("show", show)
    pop.connect("closed", closed)
    return pop


def calm_handles(tv):
    """Touch: Nach einem Fingertipp zeigt GTK runde Griffpunkte am Cursor. Tippen auf der Tastatur blendet sie
    nicht aus (die Eingabemethode bekommt die Taste zuerst) – sie standen dann als kleine weiße Punkte im Text
    und wanderten mit. Also: Taste → Griffe unsichtbar (CSS ist-typing), nächste Berührung → wieder da."""
    k = Gtk.EventControllerKey()
    k.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
    k.connect("key-pressed", lambda *_: (tv.has_css_class("ist-typing") or tv.add_css_class("ist-typing"), False)[1])
    tv.add_controller(k)
    g = Gtk.GestureClick(button=0)
    g.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
    g.connect("pressed", lambda *_: tv.remove_css_class("ist-typing"))
    tv.add_controller(g)


CSS += """
textview.ist-typing cursor-handle { opacity: 0; }
"""


def pointer_buttons(widget):
    """Knöpfe in Blöcken, die im Textfeld verankert sind, erben sonst dessen Text-Cursor (Strich statt Hand)."""
    if isinstance(widget, (Gtk.Button, Gtk.MenuButton)):
        widget.set_cursor_from_name("pointer")
    c = widget.get_first_child()
    while c is not None:
        pointer_buttons(c)
        c = c.get_next_sibling()


class TableSizePicker(Gtk.Box):
    """Größe einer neuen Tabelle wählen wie in Word: Raster zeigen/ziehen markiert, Klick/Tipp fügt ein.
    Darunter Zahlenfelder für größere Tabellen. on_pick(rows, cols)."""
    ROWS, COLS, CELL, GAP = 8, 10, 22, 4

    def __init__(self, on_pick):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.on_pick = on_pick
        self.hover = (3, 3)
        h = Gtk.Label(label="TABELLE EINFÜGEN", xalign=0)
        h.add_css_class("wpop-head")
        self.append(h)
        step = self.CELL + self.GAP
        self.grid = Gtk.DrawingArea(content_width=self.COLS * step - self.GAP,
                                    content_height=self.ROWS * step - self.GAP, halign=Gtk.Align.START)
        self.grid.add_css_class("tsize")
        self.grid.set_draw_func(self.draw)
        self.grid.set_cursor(Gdk.Cursor.new_from_name("pointer"))
        m = Gtk.EventControllerMotion()
        m.connect("motion", lambda _c, x, y: self.set_hover(*self.at(x, y)))
        self.grid.add_controller(m)
        drag = Gtk.GestureDrag()                      # Touch: Finger ziehen, loslassen = einfügen
        drag.connect("drag-begin", lambda g, x, y: self.set_hover(*self.at(x, y)))
        drag.connect("drag-update", self._drag)
        drag.connect("drag-end", self._drag_end)
        self.grid.add_controller(drag)
        self.append(self.grid)
        self.size_lbl = Gtk.Label(xalign=0)
        self.size_lbl.add_css_class("tsize-lbl")
        self.append(self.size_lbl)
        more = Gtk.Box(spacing=6)
        self.rows_sp = Gtk.SpinButton.new_with_range(1, 50, 1)
        self.cols_sp = Gtk.SpinButton.new_with_range(1, 12, 1)
        for lab, sp in (("zeilen", self.rows_sp), ("spalten", self.cols_sp)):
            sp.add_css_class("wt")
            sp.connect("value-changed", lambda *_: self._spin())
            more.append(Gtk.Label(label=lab))
            more.append(sp)
        more.append(Gtk.Box(hexpand=True))
        ok = Gtk.Button(label="einfügen")
        ok.add_css_class("pb"); ok.add_css_class("small")
        ok.connect("clicked", lambda *_: self.on_pick(int(self.rows_sp.get_value()), int(self.cols_sp.get_value())))
        more.append(ok)
        self.append(more)
        self.reset()

    def reset(self):
        self.set_hover(3, 3)

    def at(self, x, y):
        step = self.CELL + self.GAP
        return (max(1, min(self.ROWS, int(y // step) + 1)), max(1, min(self.COLS, int(x // step) + 1)))

    def set_hover(self, r, c):
        self.hover = (r, c)
        self._quiet = True
        self.rows_sp.set_value(r)
        self.cols_sp.set_value(c)
        self._quiet = False
        self.size_lbl.set_label(f"{r} zeilen × {c} spalten")
        self.grid.queue_draw()

    def _spin(self):
        if getattr(self, "_quiet", False):
            return
        self.hover = (int(self.rows_sp.get_value()), int(self.cols_sp.get_value()))
        self.size_lbl.set_label(f"{self.hover[0]} zeilen × {self.hover[1]} spalten")
        self.grid.queue_draw()

    def _drag(self, g, dx, dy):
        ok, x, y = g.get_start_point()
        if ok:
            self.set_hover(*self.at(x + dx, y + dy))

    def _drag_end(self, g, dx, dy):
        ok, x, y = g.get_start_point()
        if not ok or not (0 <= x + dx < self.grid.get_width() and 0 <= y + dy < self.grid.get_height()):
            return                                    # außerhalb losgelassen = abbrechen
        r, c = self.at(x + dx, y + dy)
        self.set_hover(r, c)
        GLib.idle_add(lambda: (self.on_pick(r, c), False)[1])

    def draw(self, area, cr, w, h):
        fg = area.get_color()
        ok, pr = area.get_style_context().lookup_color("primary")
        if not ok:
            pr = fg
        hr, hc = self.hover
        step = self.CELL + self.GAP
        for r in range(self.ROWS):
            for c in range(self.COLS):
                x, y = c * step, r * step
                on = r < hr and c < hc
                cr.rectangle(x + 0.5, y + 0.5, self.CELL - 1, self.CELL - 1)
                if on:
                    cr.set_source_rgba(pr.red, pr.green, pr.blue, 0.35)
                    cr.fill_preserve()
                    cr.set_source_rgba(pr.red, pr.green, pr.blue, 1)
                else:
                    cr.set_source_rgba(fg.red, fg.green, fg.blue, 0.35)
                cr.set_line_width(1)
                cr.stroke()


# =====================================================================
# Eingebettete Blöcke
# =====================================================================
class TableBlock(Gtk.Box):
    """Tabelle: Zellen aus Text. Leiste beim Bearbeiten: Zeilen/Spalten und „design“ (Kopfzeile, erste Spalte,
    Streifen, Rahmen, Farbe, Abstand, Ausrichtung und Breite je Spalte). Tab/Umschalt+Tab springen durch die
    Zellen (Tab in der letzten Zelle hängt eine Zeile an), Pfeile hoch/runter wechseln die Zeile, Esc verlässt
    die Tabelle."""

    def __init__(self, writer, rows, style=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        self.writer = writer
        self.style = df.table_style({"style": style or {}})
        self.add_css_class("wtable")
        self.bar = Gtk.Box(spacing=4)
        self.bar.add_css_class("wtable-bar")
        for label, tip, cb in (("+ zeile", "Zeile unter der aktuellen einfügen (Tab in der letzten Zelle)",
                                lambda *_: self.add_row()),
                               ("+ spalte", "Spalte rechts einfügen", lambda *_: self.add_col()),
                               ("− zeile", "Aktuelle Zeile entfernen", lambda *_: self.del_row()),
                               ("− spalte", "Aktuelle Spalte entfernen", lambda *_: self.del_col())):
            b = Gtk.Button(label=label, tooltip_text=tip, focus_on_click=False)
            b.add_css_class("pb"); b.add_css_class("small")
            b.connect("clicked", cb)
            self.bar.append(b)
        # Das Popover hängt am Writer statt am Knopf: Popovers in Widgets, die im Textfeld verankert sind,
        # bekommen von GTK keine Größe und bleiben unsichtbar (Tabelleneinstellungen „schlossen sich sofort“).
        self.design_btn = Gtk.Button(label="󰏘 design", tooltip_text="Aussehen der Tabelle", focus_on_click=False)
        self.design_btn.add_css_class("pb"); self.design_btn.add_css_class("small")
        self.design_btn.connect("clicked", lambda *_: self.open_design())
        # autohide=False: mit Grab schließt Hyprland das Popup bei Touch-Tipps hinein („Einstellung antippen →
        # Einstellungen weg“). Schließen daher selbst: Tipp außerhalb der Tabelle, Esc, „design“, Wegscrollen.
        self.design_pop = ist_pop(Gtk.Popover(position=Gtk.PositionType.BOTTOM, autohide=False))
        self.design_pop.add_css_class("tdesign")      # deckend: liegt über Text (Glas machte es unlesbar)
        self.design_pop.set_child(self.build_design())
        esc = Gtk.EventControllerKey()
        esc.connect("key-pressed", lambda _c, kv, *_: kv == Gdk.KEY_Escape and (self.design_pop.popdown(), True)[1])
        self.design_pop.add_controller(esc)
        self._dwatch = None
        self.design_pop.connect("show", lambda *_: self.sync_design())
        self.connect("unrealize", lambda *_: self.drop_design())
        self.bar.append(self.design_btn)
        rm = Gtk.Button(label="󰆴", tooltip_text="Ganze Tabelle entfernen", focus_on_click=False)
        rm.add_css_class("pb"); rm.add_css_class("small")
        rm.connect("clicked", lambda *_: writer.remove_block(self))
        self.bar.append(rm)
        self.rev = Gtk.Revealer(transition_type=Gtk.RevealerTransitionType.SLIDE_DOWN, reveal_child=False)
        self.rev.set_child(self.bar)
        self.append(self.rev)
        self.grid = Gtk.Grid(column_homogeneous=False)
        self.append(self.grid)
        fc = Gtk.EventControllerFocus()
        fc.connect("enter", lambda *_: self.rev.set_reveal_child(True))
        fc.connect("leave", lambda *_: GLib.timeout_add(120, self._maybe_hide_bar))
        self.add_controller(fc)
        # Antippen (Touch/Touchpad): Leiste sofort zeigen; landet der Fokus nicht in der Zelle, selbst hineinsetzen
        tap = Gtk.GestureClick(button=0)
        tap.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        tap.connect("pressed", self._on_tap)
        self.add_controller(tap)
        self._tap_t = 0
        self._pop_t = 0
        ptap = Gtk.GestureClick(button=0)
        ptap.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        ptap.connect("pressed", lambda *_: setattr(self, "_pop_t", GLib.get_monotonic_time()))
        self.design_pop.add_controller(ptap)
        self.design_pop.connect("closed", lambda *_: (self.watch_design(False), self.mark_col(False),
                                                      GLib.timeout_add(80, self.after_design)))
        self.focus = (0, 0)
        self.cells = []
        self.width = 400
        self.set_rows(rows)

    def _maybe_hide_bar(self):
        # verzögert: ein Druck auf „design“ holt kurz den Fokus ins Textfeld, bevor das Popover aufgeht
        if GLib.get_monotonic_time() - self._tap_t < 700_000:     # gerade in die Tabelle getippt
            return False
        if not (self.design_pop.get_visible() or self.has_focus_inside()):
            self.rev.set_reveal_child(False)
        return False

    def _on_tap(self, g, n, x, y):
        self._tap_t = GLib.get_monotonic_time()
        self.rev.set_reveal_child(True)
        hit = self.pick(x, y, Gtk.PickFlags.DEFAULT)
        GLib.timeout_add(250, self._tap_focus, hit)

    def _tap_focus(self, hit):
        if hit is None:
            return False
        root = self.get_root()
        cur = root.get_focus() if root else None
        for row in self.cells:
            for f in row:
                if hit is f or hit.is_ancestor(f):
                    if not (cur is f.tv or (cur is not None and cur.is_ancestor(f))):
                        f.tv.grab_focus()             # angetippte Zelle (auch bei offenem Design)
                    return False
        return False

    # ---------- Zellen ----------
    def has_focus_inside(self):
        root = self.get_root()
        f = root.get_focus() if root else None
        return bool(f and (f.is_ancestor(self) or f.is_ancestor(self.design_pop)))

    def make_cell(self, text, r, c):
        tv = Gtk.TextView(wrap_mode=Gtk.WrapMode.WORD_CHAR, accepts_tab=False, hexpand=True)
        calm_handles(tv)
        tv.get_buffer().set_text(text)
        tv.get_buffer().connect("changed", lambda *_: self.writer.child_changed())
        fc = Gtk.EventControllerFocus()
        fc.connect("enter", lambda *_: self.cell_entered(tv))
        tv.add_controller(fc)
        k = Gtk.EventControllerKey()
        k.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        k.connect("key-pressed", self.on_cell_key, tv)
        tv.add_controller(k)
        frame = Gtk.Box()
        frame.add_css_class("cell")
        frame.append(tv)
        frame.tv = tv
        return frame

    def cell_entered(self, tv):
        self.focus = self.pos_of(tv)
        if self.design_pop.get_visible():         # Design offen: Spalte per Klick wechseln
            self.sync_design()

    def mark_col(self, on=True):
        """Spalte, auf die sich „Spalte N“ im Design bezieht, hervorheben (nur solange es offen ist)."""
        c = self.focus[1] if on else -1
        for row in self.cells:
            for i, f in enumerate(row):
                (f.add_css_class if i == c else f.remove_css_class)("colsel")

    def pos_of(self, tv):
        for r, row in enumerate(self.cells):
            for c, f in enumerate(row):
                if f.tv is tv:
                    return r, c
        return 0, 0

    def rows(self):
        return [[f.tv.get_buffer().get_property("text") for f in row] for row in self.cells]

    def model_style(self):
        return df.table_style_min(self.style)

    def set_rows(self, rows):
        while (ch := self.grid.get_first_child()):
            self.grid.remove(ch)
        rows = rows or [[""]]
        ncol = max(len(r) for r in rows)
        self.cells = []
        for r, row in enumerate(rows):
            line = []
            for c in range(ncol):
                f = self.make_cell(row[c] if c < len(row) else "", r, c)
                self.grid.attach(f, c, r, 1, 1)
                line.append(f)
            self.cells.append(line)
        self.apply_style()
        if self.design_pop.get_visible():
            self.mark_col(True)
            GLib.timeout_add(60, self._design_follow)      # Tabelle höher/niedriger → Popover nachziehen

    def apply_style(self):
        st = self.style
        for k in [c for c in self.get_css_classes() if c.startswith(("b-", "acc-", "pad-"))] + ["stripes"]:
            self.remove_css_class(k)
        self.add_css_class("b-" + st["border"])
        self.add_css_class("pad-" + st["pad"])
        if st["accent"] in df.TABLE_ACCENTS:
            self.add_css_class(f"acc-{df.TABLE_ACCENTS.index(st['accent'])}")
        ncol = len(self.cells[0]) if self.cells else 1
        nrow = len(self.cells)
        for r, row in enumerate(self.cells):
            for c, f in enumerate(row):
                body = r - 1 if st["head"] else r
                for cls, on in (("head", st["head"] and r == 0),
                                ("firstcol", st["first_col"] and c == 0 and not (st["head"] and r == 0)),
                                ("odd", st["stripes"] and body >= 0 and body % 2 == 1),
                                ("lastcol", c == ncol - 1), ("lastrow", r == nrow - 1), ("firstrow", r == 0),
                                ("firstcolumn", c == 0)):
                    (f.add_css_class if on else f.remove_css_class)(cls)
                f.tv.set_justification({"center": Gtk.Justification.CENTER, "right": Gtk.Justification.RIGHT}.get(
                    df.table_align(st, c), Gtk.Justification.LEFT))
        self.set_width(self.width)

    def change(self, fn, focus=None):
        self.writer.checkpoint()
        rows = self.rows()
        fn(rows)
        self.set_rows(rows)
        self.writer.child_changed()
        r, c = focus or self.focus
        self.focus_cell(r, c, later=True)

    def focus_cell(self, r, c, end=False, later=False):
        r = max(0, min(r, len(self.cells) - 1))
        c = max(0, min(c, len(self.cells[0]) - 1))
        self.focus = (r, c)

        def go():
            tv = self.cells[r][c].tv
            tv.grab_focus()
            b = tv.get_buffer()
            b.place_cursor(b.get_end_iter() if end else b.get_start_iter())
            return False
        if later:                       # nach dem Neuaufbau erst, wenn die Zellen stehen
            GLib.idle_add(go)
        else:                           # sofort – schnell weitergetippte Zeichen landen sonst in der alten Zelle
            go()

    def add_row(self, at=None):
        r = self.focus[0] if at is None else at - 1
        self.change(lambda rows: rows.insert(r + 1, [""] * len(rows[0])), (r + 1, 0 if at else self.focus[1]))

    def add_col(self):
        c = self.focus[1]

        def fn(rows):
            for row in rows:
                row.insert(c + 1, "")
            self._insert_col_style(c + 1, len(rows[0]))
        self.change(fn, (self.focus[0], c + 1))

    def del_row(self):
        if len(self.cells) > 1:
            r = self.focus[0]
            self.change(lambda rows: rows.pop(r))

    def del_col(self):
        if len(self.cells[0]) > 1:
            c = self.focus[1]

            def fn(rows):
                for row in rows:
                    row.pop(c)
                for key in ("align", "widths"):
                    v = list(self.style.get(key) or [])
                    if c < len(v):
                        v.pop(c)
                    self.style[key] = v
            self.change(fn)

    def _insert_col_style(self, c, ncol):
        al = list(self.style.get("align") or [])
        if al:
            al.insert(c, "left")
            self.style["align"] = al
        w = list(self.style.get("widths") or [])
        if len(w) == ncol - 1:
            avg = 1.0 / ncol
            w = [x * (1 - avg) for x in w]
            w.insert(c, avg)
            self.style["widths"] = w

    def on_cell_key(self, ctrl, keyval, code, state, tv):
        r, c = self.pos_of(tv)
        nrow, ncol = len(self.cells), len(self.cells[0])
        shift = bool(state & Gdk.ModifierType.SHIFT_MASK)
        if state & (Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.ALT_MASK):
            return False
        buf = tv.get_buffer()
        ins = buf.get_iter_at_mark(buf.get_insert())
        if keyval in (Gdk.KEY_Tab, Gdk.KEY_ISO_Left_Tab, Gdk.KEY_KP_Tab):
            if shift or keyval == Gdk.KEY_ISO_Left_Tab:
                if c > 0:
                    self.focus_cell(r, c - 1, end=True)
                elif r > 0:
                    self.focus_cell(r - 1, ncol - 1, end=True)
            elif c < ncol - 1:
                self.focus_cell(r, c + 1)
            elif r < nrow - 1:
                self.focus_cell(r + 1, 0)
            else:
                self.focus = (r, c)
                self.add_row(at=nrow)
            return True
        if keyval == Gdk.KEY_Escape:
            self.leave(after=True)
            return True
        if keyval in (Gdk.KEY_Up, Gdk.KEY_KP_Up, Gdk.KEY_Down, Gdk.KEY_KP_Down) and not shift:
            up = keyval in (Gdk.KEY_Up, Gdk.KEY_KP_Up)
            y = tv.get_iter_location(ins).y
            edge = tv.get_iter_location(buf.get_start_iter() if up else buf.get_end_iter()).y
            if (up and y <= edge) or (not up and y >= edge):     # oberste/unterste Zeile der Zelle
                if up and r > 0:
                    self.focus_cell(r - 1, c, end=True)
                elif not up and r < nrow - 1:
                    self.focus_cell(r + 1, c)
                else:
                    self.leave(after=not up)
                return True
        return False

    def leave(self, after=True):
        """Cursor in den Text vor/nach der Tabelle setzen."""
        w = self.writer
        for anchor, x in w.blocks.items():
            if x is self:
                it = w.anchor_iter(anchor)
                if after:
                    it.forward_char()
                    if it.get_char() == "\n":
                        it.forward_char()
                    if it.is_end() and not it.starts_line():
                        w.buf.insert(it, "\n")
                        it = w.buf.get_end_iter()
                else:
                    if not it.is_start():
                        it.backward_char()
                w.buf.place_cursor(it)
                w.view.grab_focus()
                return

    # ---------- Design ----------
    def open_design(self):
        host, pop = self.writer, self.design_pop
        if pop.get_visible():                     # „design“ nochmal = zu
            pop.popdown()
            return
        if pop.get_parent() is not host:
            if pop.get_parent() is not None:
                pop.unparent()
            pop.set_parent(host)
        self.rev.set_reveal_child(True)
        if not self.has_focus_inside():           # Fokus zurück in die Zelle (Tippen landet sonst im Text)
            r, c = self.focus
            if r < len(self.cells) and c < len(self.cells[r]):
                self.cells[r][c].tv.grab_focus()
        if not self.place_design():
            return
        self.watch_design(True)
        pop.popup()


    def place_design(self):
        ok, b = self.design_btn.compute_bounds(self.writer)
        if not ok:
            return self.design_pop.get_visible()  # offen: alte Position behalten (Knopf wird gerade neu eingebaut)
        sc = self.writer.scroll
        ok2, top = sc.compute_bounds(self.writer)
        if ok2 and (b.get_y() + b.get_height() < top.get_y() or b.get_y() > top.get_y() + top.get_height()):
            return False                          # Knopf aus dem Bild gescrollt
        # unter (oder über) die ganze Tabelle, nicht an den Knopf: so bleiben alle Spalten frei zum Antippen
        ok3, tb = self.grid.compute_bounds(self.writer)
        if ok3 and tb.get_height() < 600:
            self.design_pop.set_pointing_to(_rect(b.get_x(), tb.get_y(), b.get_width(), tb.get_height()))
        else:
            self.design_pop.set_pointing_to(_rect(b.get_x(), b.get_y(), b.get_width(), b.get_height()))
        return True

    def watch_design(self, on):
        """Solange das Popover offen ist: Tipp/Klick ins Dokument außerhalb der Tabelle schließt es,
        Scrollen schiebt es mit."""
        w = self.writer
        if on and self._dwatch is None:
            root = w.get_root()
            click = Gtk.GestureClick(button=0)
            click.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
            click.connect("pressed", self._design_outside)
            root.add_controller(click)
            adj = w.scroll.get_vadjustment()
            hid = adj.connect("value-changed", lambda *_: GLib.idle_add(self._design_follow))
            self._dwatch = (root, click, adj, hid)
        elif not on and self._dwatch is not None:
            root, click, adj, hid = self._dwatch
            self._dwatch = None
            root.remove_controller(click)
            adj.disconnect(hid)

    def _design_follow(self):
        if self.design_pop.get_visible() and not self.place_design():
            self.design_pop.popdown()
        return False

    def _design_outside(self, g, n, x, y):
        hit = g.get_widget().pick(x, y, Gtk.PickFlags.DEFAULT)
        GLib.idle_add(self._design_outside_late, hit)

    def _design_outside_late(self, hit):
        # das Popover meldet seinen eigenen Tipp erst NACH dem Fenster (Capture läuft von außen nach innen)
        if GLib.get_monotonic_time() - self._pop_t < 300_000:
            return False                          # Tipp ins Popover selbst
        if hit is None or not (hit is self or hit.is_ancestor(self)):
            self.design_pop.popdown()
        elif self.design_pop.get_visible():
            self.sync_design()
        return False

    def drop_design(self):
        """Tabelle verschwindet (gelöscht, Rückgängig, anderes Dokument): Popover vom Writer lösen."""
        pop = self.design_pop
        self.watch_design(False)
        if pop.get_parent() is not None:
            pop.popdown()
            pop.unparent()

    def after_design(self):
        root = self.get_root()
        f = root.get_focus() if root else None
        if self.get_mapped() and (f is None or not (f.is_ancestor(self) or f.is_ancestor(self.design_pop))):
            r, c = self.focus                     # zurück in die Zelle, in der man vorher war (Cursor bleibt)
            if r < len(self.cells) and c < len(self.cells[r]):
                self.cells[r][c].tv.grab_focus()
        self.rev.set_reveal_child(self.get_mapped())
        return False

    def build_design(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, width_request=280)
        h = Gtk.Label(label="TABELLE", xalign=0)
        h.add_css_class("wpop-head")
        box.append(h)
        self.d_sw = {}
        for key, text in (("head", "Kopfzeile"), ("first_col", "Erste Spalte betont"), ("stripes", "Streifen")):
            row = Gtk.Box(spacing=8)
            row.append(Gtk.Label(label=text, xalign=0, hexpand=True))
            sw = Gtk.Switch(valign=Gtk.Align.CENTER)
            sw.connect("notify::active", lambda s, _p, k=key: self.set_opt(k, s.get_active()))
            row.append(sw)
            self.d_sw[key] = sw
            box.append(row)

        def chips(title, items, key):
            box.append(self._sub(title))
            row = Gtk.Box(spacing=3, homogeneous=True)
            group, out = None, {}
            for val, label, tip in items:
                b = Gtk.ToggleButton(label=label, tooltip_text=tip, focus_on_click=False)
                b.add_css_class("tchip")
                if group:
                    b.set_group(group)
                group = group or b
                b.connect("toggled", lambda b, v=val: b.get_active() and self.set_opt(key, v))
                row.append(b)
                out[val] = b
            box.append(row)
            return out
        self.d_border = chips("Rahmen", (("grid", "󰕰 gitter", "Alle Linien"), ("rows", "󰕭 zeilen", "Nur waagerecht"),
                                         ("outer", "󰝣 außen", "Nur der Rand"), ("none", "ohne", "Keine Linien")),
                              "border")
        self.d_pad = chips("Abstand", (("compact", "eng", "Wenig Innenabstand"), ("normal", "normal", ""),
                                       ("wide", "weit", "Viel Innenabstand")), "pad")
        box.append(self._sub("Farbe"))
        sw_row = Gtk.Box(spacing=4)
        self.d_colors = {}
        for col in (None,) + df.TABLE_ACCENTS:
            b = Gtk.Button(focus_on_click=False, tooltip_text="Ohne Farbe" if col is None else col)
            b.add_css_class("swatch-b")
            b.add_css_class("tcol")
            if col is None:
                b.set_label("∅")
            else:
                b.add_css_class(f"tcol-{df.TABLE_ACCENTS.index(col)}")
            b.connect("clicked", lambda _b, v=col: self.set_opt("accent", v))
            sw_row.append(b)
            self.d_colors[col] = b
        box.append(sw_row)
        self.d_colhead = self._sub("Spalte")
        box.append(self.d_colhead)
        crow = Gtk.Box(spacing=3)
        self.d_align = {}
        group = None
        for val, icon, tip in (("left", "󰉢", "Linksbündig"), ("center", "󰉠", "Zentriert"), ("right", "󰉣", "Rechtsbündig")):
            b = Gtk.ToggleButton(label=icon, tooltip_text=tip, focus_on_click=False)
            b.add_css_class("tchip")
            if group:
                b.set_group(group)
            group = group or b
            b.connect("toggled", lambda b, v=val: b.get_active() and self.set_align(v))
            crow.append(b)
            self.d_align[val] = b
        crow.append(Gtk.Box(hexpand=True))
        for icon, tip, d in (("󰍴", "Spalte schmaler", -1), ("󰐕", "Spalte breiter", 1)):
            b = Gtk.Button(label=icon, tooltip_text=tip, focus_on_click=False)
            b.add_css_class("tchip")
            b.connect("clicked", lambda _b, d=d: self.resize_col(d))
            crow.append(b)
        eq = Gtk.Button(label="gleich", tooltip_text="Alle Spalten gleich breit", focus_on_click=False)
        eq.add_css_class("tchip")
        eq.connect("clicked", lambda *_: self.set_opt("widths", []))
        crow.append(eq)
        box.append(crow)
        return box

    @staticmethod
    def _sub(text):
        l = Gtk.Label(label=text, xalign=0, margin_top=4)
        l.add_css_class("tsub")
        return l

    def sync_design(self):
        self._dsync = True
        st = self.style
        for k, sw in self.d_sw.items():
            sw.set_active(bool(st[k]))
        self.d_border[st["border"]].set_active(True)
        self.d_pad[st["pad"]].set_active(True)
        for col, b in self.d_colors.items():
            (b.add_css_class if col == st["accent"] else b.remove_css_class)("cur")
        c = self.focus[1]
        self.d_colhead.set_label(f"Spalte {c + 1}")
        self.d_align[df.table_align(st, c)].set_active(True)
        self.mark_col(True)
        self._dsync = False

    def set_opt(self, key, value):
        if getattr(self, "_dsync", False) or self.style.get(key) == value:
            return
        self.writer.checkpoint()
        self.style[key] = value
        self.apply_style()
        self.writer.child_changed()
        if self.design_pop.get_visible():
            self.sync_design()
            GLib.timeout_add(60, self._design_follow)

    def set_align(self, val):
        if getattr(self, "_dsync", False):
            return
        ncol = len(self.cells[0])
        al = [df.table_align(self.style, c) for c in range(ncol)]
        al[self.focus[1]] = val
        self.set_opt("align", al)

    def resize_col(self, d):
        ncol = len(self.cells[0])
        if ncol < 2:
            return
        w = df.table_widths(self.style, ncol)
        c = self.focus[1]
        new = min(0.85, max(0.06, w[c] + 0.05 * d))
        rest = sum(w) - w[c]
        w = [new if i == c else x * (1 - new) / rest for i, x in enumerate(w)]
        self.set_opt("widths", [round(x, 4) for x in w])

    def set_width(self, w):
        self.width = w
        self.set_size_request(max(80, int(w)), -1)
        if not self.cells:
            return
        ncol = len(self.cells[0])
        fr = df.table_widths(self.style, ncol)
        inner = max(40 * ncol, int(w) - 2)
        for row in self.cells:
            for c, f in enumerate(row):
                f.set_size_request(max(30, int(inner * fr[c])), -1)


class RuleBlock(Gtk.Box):
    def __init__(self, writer):
        super().__init__()
        self.add_css_class("whr")

    def set_width(self, w):
        self.set_size_request(max(80, int(w)), 2)


class BreakBlock(Gtk.Label):
    def __init__(self, writer):
        super().__init__(label="SEITENUMBRUCH", xalign=0.5)
        self.add_css_class("wpb")

    def set_width(self, w):
        self.set_size_request(max(80, int(w)), -1)


class TocBlock(Gtk.Box):
    """Inhaltsverzeichnis: füllt sich selbst aus den Überschriften (mit Seitenzahlen), Klick springt hin."""

    def __init__(self, writer):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.writer = writer
        self.add_css_class("wtoc")
        head = Gtk.Box()
        t = Gtk.Label(label="Inhaltsverzeichnis", xalign=0, hexpand=True)
        t.add_css_class("wtoc-title")
        head.append(t)
        rm = Gtk.Button(label="󰆴", tooltip_text="Inhaltsverzeichnis entfernen", focus_on_click=False)
        rm.add_css_class("wtoc-rm")
        rm.connect("clicked", lambda *_: writer.remove_block(self))
        head.append(rm)
        self.append(head)
        self.list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        self.append(self.list)
        self.entries = None

    def refresh(self, entries):
        if entries == self.entries:
            return
        self.entries = entries
        while (c := self.list.get_first_child()):
            self.list.remove(c)
        if not entries:
            l = Gtk.Label(label="Noch keine Überschriften – Formatvorlage „Überschrift 1–3“ verwenden.", xalign=0)
            l.add_css_class("wtoc-empty")
            self.list.append(l)
        for level, text, line, page in entries:
            b = Gtk.Button(focus_on_click=False)
            b.add_css_class("wtoc-entry")
            row = Gtk.Box(spacing=6, margin_start=18 * (level - 1))
            l = Gtk.Label(label=text, xalign=0, hexpand=True, ellipsize=3)
            if level == 1:
                l.add_css_class("wtoc-l1")
            row.append(l)
            dots = Gtk.Label(label="·" * 6)
            dots.add_css_class("wtoc-dots")
            row.append(dots)
            row.append(Gtk.Label(label=str(page)))
            b.set_child(row)
            b.connect("clicked", lambda *_, ln=line: self.writer.goto_line(ln))
            self.list.append(b)

    def set_width(self, w):
        self.set_size_request(max(80, int(w)), -1)


class FootnoteMark(Gtk.MenuButton):
    """Hochgestellte Fußnotennummer im Text. Klick öffnet den Fußnotentext zum Bearbeiten."""

    def __init__(self, writer, text=""):
        super().__init__(focus_on_click=False, valign=Gtk.Align.START)   # can_focus=False sperrte das Textfeld
        self.writer, self.text = writer, text
        self.add_css_class("wfn")
        self.label = Gtk.Label(label="?")
        self.set_child(self.label)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.head = Gtk.Label(label="FUSSNOTE", xalign=0)
        self.head.add_css_class("wpop-head")
        box.append(self.head)
        self.tv = Gtk.TextView(wrap_mode=Gtk.WrapMode.WORD_CHAR)
        self.tv.add_css_class("wfn-edit")
        self.tv.get_buffer().set_text(text)
        self.tv.get_buffer().connect("changed", self.on_text)
        sc = Gtk.ScrolledWindow(min_content_width=300, min_content_height=90, hscrollbar_policy=Gtk.PolicyType.NEVER)
        sc.set_child(self.tv)
        box.append(sc)
        rm = Gtk.Button(label="󰆴  Fußnote entfernen", halign=Gtk.Align.START)
        rm.add_css_class("pb"); rm.add_css_class("small")
        rm.connect("clicked", lambda *_: (self.get_popover().popdown(), writer.remove_block(self)))
        box.append(rm)
        pop = ist_pop(Gtk.Popover())
        pop.set_child(box)
        pop.connect("show", lambda *_: GLib.idle_add(lambda: self.tv.grab_focus() and False))
        pop.connect("closed", lambda *_: writer.focus_text())
        self.set_popover(pop)
        self.set_tooltip_text(text or "Fußnote")

    def on_text(self, buf):
        self.text = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False)
        self.set_tooltip_text(self.text or "Fußnote")
        self.writer.child_changed()

    def set_number(self, n):
        self.label.set_label(str(n))
        self.head.set_label(f"FUSSNOTE {n}")

    def set_width(self, w):
        pass


# =====================================================================
# Seite
# =====================================================================
class PageView(Gtk.TextView):
    def __init__(self, writer):
        super().__init__(wrap_mode=Gtk.WrapMode.WORD_CHAR, pixels_below_lines=8, accepts_tab=True)
        self.w = writer
        self.add_css_class("page")
        self._last_width = 0

    def do_measure(self, orientation, for_size):
        # Die Seitenränder sind nur Optik: nicht als Mindestbreite melden, sonst kann das Fenster nicht schrumpfen
        mn, nat, mb, nb = Gtk.TextView.do_measure(self, orientation, for_size)
        if orientation == Gtk.Orientation.HORIZONTAL:
            return min(mn, 240), min(nat, 240), -1, -1
        return mn, nat, mb, nb

    def do_size_allocate(self, width, height, baseline):
        Gtk.TextView.do_size_allocate(self, width, height, baseline)
        if width != self._last_width:
            self._last_width = width
            GLib.idle_add(self.w.update_geometry)

    def do_snapshot_layer(self, layer, snap):
        if layer == Gtk.TextViewLayer.BELOW_TEXT:
            self.w.draw_paper(snap)
        else:
            self.w.draw_markers(snap)


class Writer(Gtk.Box):
    """on_change(): Text/Titel geändert. Formatierungs-Status und Ansicht verwaltet der Writer selbst."""

    def __init__(self, win, on_change, settings):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, vexpand=True)
        self.win, self.on_change, self.settings = win, on_change, settings
        self.zoom = settings.get("zoom", 1.0)
        self.light = settings.get("light_paper", False)
        self._loading = False
        self._md_id = None               # wartende Markdown-Prüfung nach dem Tippen
        self._quiet = 0                  # >0: Pufferänderungen gehören zu einem Schritt, der selbst changed() ruft
        self._sync = False
        self.editable = True
        self.active = {}                 # Zeichenformat fürs nächste Tippen: {"b": True, "font": "…", ...}
        self.pending_para = None         # Absatzformat für eine leere letzte Zeile
        self.images = {}                 # Gdk.Texture → {"img", "mime", "w", "h"}
        self.blocks = {}                 # Gtk.TextChildAnchor → Widget
        self.margin_tags = {}            # Einzug-Einheiten → Tag
        self.geo = dict(side=DESK, page_w=A4_W, m=PAGE_M, ml=PAGE_M, scale=1.0, text_w=A4_W - 2 * PAGE_M)
        self.page = df.page_defaults(self.default_margin_mm())
        self.pages = []                  # y-Anfang jeder Seite (Buffer-Koordinaten) für die Seitenmarken
        self.undo_stack, self.redo_stack = [], []
        self.last_state = None
        self._undo_pending = None
        self._numbers = None
        self._pages_id = None
        self._measured, self._settle = None, 0
        self._verify_id, self._verify_n, self._expect = None, 0, 0
        self.search_hits = []
        self.autofmt_prefs = None        # notist setzt hier seine prefs ein (automatisches Formatieren)
        self.extra_bottom = 0            # Luft unter dem Text fürs Mitscrollen (follow.py)
        self.flow = False                # Ansicht „fließend“ (flow.py) statt Seiten
        self.on_view_change = None       # notist: Ansicht pro Dokument merken
        self.build()

    # ================= Aufbau =================
    def build(self):
        self.title = Gtk.Entry(placeholder_text="Dokumenttitel")
        self.title.add_css_class("doc-title")
        self.title.connect("changed", lambda *_: self._loading or self.on_change())
        self.title.connect("activate", lambda *_: self.focus_text())
        k = Gtk.EventControllerKey()
        k.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        k.connect("key-pressed", self.on_title_key)
        self.title.add_controller(k)
        # Titelzeile: rechts daneben setzt notist „anheften“ / „löschen“ ein (title_row)
        self.title.set_hexpand(True)
        self.title_row = Gtk.Box(spacing=6)
        self.title_row.append(self.title)
        self.view_btn = Gtk.Button(focus_on_click=False, valign=Gtk.Align.CENTER)
        self.view_btn.add_css_class("tbtn")
        self.view_btn.add_css_class("view-sw")        # gleiche Schrift wie anheften/löschen daneben
        self.view_btn.connect("clicked", lambda *_: self.set_flow(not self.flow, user=True))
        self.title_row.append(self.view_btn)
        self.append(self.title_row)
        self.ribbon_box = self.build_tools()
        self.append(self.ribbon_box)
        self.flowbar = self.build_flowbar()
        self.append(self.flowbar)
        self.append(self.build_findbar())

        self.view = PageView(self)
        calm_handles(self.view)
        self.buf = self.view.get_buffer()
        self.buf.set_enable_undo(False)              # eigene Rückgängig-Funktion (GTKs kennt keine Formatierung)
        self.make_tags()
        self.buf.connect("insert-text", self.before_insert)
        self.buf.connect_after("insert-text", self.after_insert)
        self.buf.connect("changed", self.on_buffer_changed)
        self.buf.connect("mark-set", self.on_mark_set)
        self.buf.connect_after("delete-range", lambda *_: self.invalidate())
        k = Gtk.EventControllerKey()
        k.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        k.connect("key-pressed", self.on_key)
        self.view.add_controller(k)
        click = Gtk.GestureClick()
        click.connect("released", self.on_click)
        self.view.add_controller(click)
        zoom = Gtk.EventControllerScroll(flags=Gtk.EventControllerScrollFlags.VERTICAL)
        zoom.connect("scroll", self.on_scroll)
        self.view.add_controller(zoom)
        self.view.connect("paste-clipboard", self.on_paste)
        drop = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY)
        drop.connect("drop", self.on_drop)
        self.view.add_controller(drop)

        self.scroll = Gtk.ScrolledWindow(vexpand=True, hexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER)
        self.scroll.set_child(self.view)
        self.scroll.add_css_class("desk")
        desk = Gtk.Box(vexpand=True)
        self.navrev = Gtk.Revealer(transition_type=Gtk.RevealerTransitionType.SLIDE_RIGHT,
                                   reveal_child=self.settings.get("nav", False))
        nav = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, width_request=190)
        nav.add_css_class("nav-pane")
        h = Gtk.Label(label="NAVIGATION", xalign=0)
        h.add_css_class("nav-head")
        nav.append(h)
        self.nav_list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
        self.nav_list.connect("row-activated", lambda lb, row: self.goto_line(row.line))
        nsc = Gtk.ScrolledWindow(vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER)
        nsc.set_child(self.nav_list)
        nav.append(nsc)
        self.navrev.set_child(nav)
        self._nav_id = None
        desk.append(self.navrev)
        desk.append(self.scroll)
        self.append(desk)
        self.append(self.build_status())
        import flow
        self.flowx = flow.FlowMode(self)
        self.apply_paper()
        self.set_flow(False)
        self.load([df.para()], "")

    def build_tools(self):
        """Menüband wie in Word: Reiter Start / Einfügen / Layout / Ansicht, Gruppen mit Beschriftung."""
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        outer.add_css_class("ribbon")
        self.tools = {}

        # ---------- Kopfzeile: Datei, Reiter, Schnellzugriff ----------
        head = Gtk.Box(spacing=2)
        head.add_css_class("ribbon-tabs")
        filebtn = Gtk.MenuButton(tooltip_text="Öffnen, Exportieren, Drucken", can_focus=False)
        filebtn.set_popover(file_menu())
        filebtn.set_child(Gtk.Label(label="󰈙  Datei"))
        filebtn.add_css_class("file-tab")
        head.append(filebtn)
        self.ribbon_stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE, transition_duration=120,
                                      vhomogeneous=False, hhomogeneous=False, interpolate_size=True)
        self.ribbon_rev = Gtk.Revealer(transition_type=Gtk.RevealerTransitionType.SLIDE_DOWN,
                                       reveal_child=not self.settings.get("ribbon_collapsed", False))
        # in einem Scroller: auch aufgeklappt im kleinen Fenster nie höher als der Platz (sonst wird unten abgeschnitten)
        self.ribbon_scroll = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER,
                                                vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
                                                propagate_natural_height=True, child=self.ribbon_stack)
        self.ribbon_rev.set_child(self.ribbon_scroll)
        self._short = False
        self.tab_btns = {}
        group_btn = None
        for key, label in (("start", "Start"), ("insert", "Einfügen"), ("layout", "Layout"), ("view", "Ansicht")):
            b = Gtk.ToggleButton(label=label, focus_on_click=False, can_focus=False)
            b.add_css_class("rtab")
            if group_btn:
                b.set_group(group_btn)
            group_btn = group_btn or b
            b.connect("toggled", self.on_tab, key)
            click = Gtk.GestureClick()
            click.connect("pressed", lambda g, n, x, y, k=key: self.on_tab_click(k, n))
            b.add_controller(click)
            head.append(b)
            self.tab_btns[key] = b
        head.append(Gtk.Box(hexpand=True))
        self.tools["undo"] = tool("󰕌", "Rückgängig (Strg+Z)", lambda *_: self.undo())
        self.tools["redo"] = tool("󰑎", "Wiederholen (Strg+Umschalt+Z)", lambda *_: self.redo())
        self.collapse_btn = tool("󰅃", "Menüband ein-/ausklappen (Strg+F1)", lambda *_: self.toggle_ribbon())
        for w in (self.tools["undo"], self.tools["redo"], self.collapse_btn):
            head.append(w)
        outer.append(head)
        outer.append(self.ribbon_rev)

        def page(key):
            p = Gtk.Box()
            p.set_layout_manager(WrapLayout(spacing=0, row_spacing=4))
            p.add_css_class("ribbon-page")
            self.ribbon_stack.add_named(p, key)
            return p

        def group(parent, caption, *rows, last=False):
            g = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            g.add_css_class("rgroup")
            if last:
                g.add_css_class("last")
            body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3, valign=Gtk.Align.CENTER)
            for r in rows:
                if isinstance(r, (list, tuple)):
                    row = Gtk.Box(spacing=2)
                    for w in r:
                        row.append(w)
                    body.append(row)
                else:
                    body.append(r)
            g.append(body)
            cap = Gtk.Label(label=caption)
            cap.add_css_class("rgroup-cap")
            g.append(cap)
            parent.append(g)
            g.body = body
            return g

        def hbox(*ws, spacing=2):
            b = Gtk.Box(spacing=spacing)
            for w in ws:
                b.append(w)
            return b

        # ================= Start =================
        start = page("start")
        self.fonts = self.font_list()
        self.font_drop = Gtk.DropDown.new_from_strings(self.fonts + ["Andere …"])
        self.font_drop.set_tooltip_text("Schriftart")
        font_dropdown(self.font_drop)
        self.font_drop.add_css_class("wt")
        self.font_drop.set_can_focus(False)
        self.font_drop.set_size_request(150, -1)
        self.font_drop.connect("notify::selected", self.on_font_drop)
        self.size_spin = Gtk.SpinButton.new_with_range(6, 96, 1)
        self.size_spin.set_digits(1)
        self.size_spin.set_tooltip_text("Schriftgröße in pt (Strg+Umschalt+> / <)")
        self.size_spin.add_css_class("wt")
        self.size_spin.set_width_chars(4)
        self.size_spin.connect("value-changed", self.on_size_spin)
        self.size_spin.connect("activate", lambda *_: self.focus_text())
        for key, label, tip in (("b", "<b>F</b>", "Fett (Strg+B)"), ("i", "<i>K</i>", "Kursiv (Strg+I)"),
                                ("u", "<u>U</u>", "Unterstrichen (Strg+U)"), ("s", "<s>S</s>", "Durchgestrichen (Strg+D)"),
                                ("sup", "x<sup>2</sup>", "Hochgestellt (Strg+Umschalt++)"),
                                ("sub", "x<sub>2</sub>", "Tiefgestellt (Strg+#)")):
            self.tools[key] = tool(label, tip, toggle=True, markup=True)
            self.tools[key].connect("toggled", self.on_char_toggle, key)
        self.fg_btn, self.fg_bar = self.color_button("\U000F069E", "Schriftfarbe", PALETTE, "fg", "Automatisch")
        self.hl_btn, self.hl_bar = self.color_button("\U000F0E31", "Texthervorhebung", HL_PALETTE, "hl", "Keine")
        group(start, "Schriftart",
              [self.font_drop, self.size_spin,
               tool("A<sup>+</sup>", "Schrift größer (Strg+Umschalt+>)", lambda *_: self.grow_font(1), markup=True),
               tool("A<sup>−</sup>", "Schrift kleiner (Strg+Umschalt+<)", lambda *_: self.grow_font(-1), markup=True)],
              [*(self.tools[k] for k in CHAR_PLAIN), Gtk.Separator(), self.fg_btn, self.hl_btn,
               tool("󰉥", "Formatierung löschen (Strg+Leertaste)", lambda *_: self.clear_format())])

        for key, icon, tip in (("left", "󰉢", "Linksbündig (Strg+L)"), ("center", "󰉠", "Zentriert (Strg+E)"),
                               ("right", "󰉣", "Rechtsbündig (Strg+R)"), ("justify", "󰉡", "Blocksatz (Strg+J)")):
            self.tools["a:" + key] = tool(icon, tip, toggle=True)
            self.tools["a:" + key].connect("toggled", self.on_align_toggle, key)
        self.tools["bullet"] = tool("󰉹", "Aufzählung (Strg+Umschalt+L)", toggle=True)
        self.tools["bullet"].connect("toggled", self.on_list_toggle, "bullet")
        self.tools["number"] = tool("󰉻", "Nummerierung (Strg+Umschalt+N)", toggle=True)
        self.tools["number"].connect("toggled", self.on_list_toggle, "number")
        sp_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        h = Gtk.Label(label="ZEILENABSTAND", xalign=0)
        h.add_css_class("wpop-head")
        sp_box.append(h)
        self.spacing_btns = {}
        for v in LINE_SPACINGS:
            b = Gtk.ToggleButton(label=f"{v:g}".replace(".", ","))
            b.add_css_class("wt")
            b.connect("clicked", self.on_spacing, v)
            sp_box.append(b)
            self.spacing_btns[v] = b
        sp_btn, self.sp_pop = popover_button("\U000F0278", "Zeilenabstand", sp_box)
        group(start, "Absatz",
              [self.tools["bullet"], self.tools["number"],
               tool("󰉵", "Einzug verkleinern (Umschalt+Tab in Listen)", lambda *_: self.change_indent(-1)),
               tool("󰉶", "Einzug vergrößern (Tab in Listen)", lambda *_: self.change_indent(1)), sp_btn],
              [*(self.tools["a:" + k] for k in ("left", "center", "right", "justify"))])

        # Formatvorlagen als Galerie (sehen aus wie das Ergebnis) + Liste mit allen
        gallery = Gtk.Box(spacing=4)
        self.style_chips = {}
        for key, markup in (("normal", "Standard"), ("title", "<b><big>Titel</big></b>"),
                            ("h1", "<b>Überschrift 1</b>"), ("h2", "<b><small>Überschrift 2</small></b>")):
            b = Gtk.ToggleButton(focus_on_click=False, can_focus=False,
                                 tooltip_text=f"Formatvorlage „{df.STYLE_NAMES[key]}“")
            lab = Gtk.Label()
            lab.set_markup(markup)
            b.set_child(lab)
            b.add_css_class("style-chip")
            b.connect("clicked", lambda btn, k=key: self._sync or self.set_style(k))
            gallery.append(b)
            self.style_chips[key] = b
        self.style_drop = Gtk.DropDown.new_from_strings([df.STYLE_NAMES[s] for s in df.STYLES])
        self.style_drop.set_tooltip_text("Alle Formatvorlagen (Strg+0 Standard, Strg+1…3 Überschriften)")
        self.style_drop.add_css_class("wt")
        self.style_drop.set_can_focus(False)
        self.style_drop.connect("notify::selected", self.on_style_drop)
        group(start, "Formatvorlagen", gallery, hbox(self.style_drop))

        self.tools["find"] = tool("󰍉", "Suchen (Strg+F)", lambda *_: self.show_find())
        group(start, "Suchen", [self.tools["find"]],
              [tool("󰛔", "Suchen & Ersetzen (Strg+H)", lambda *_: self.show_find(replace=True))], last=True)

        # ================= Einfügen =================
        ins = page("insert")
        tbl_holder = {}
        tb_box = TableSizePicker(lambda r, c: (tbl_holder["pop"].popdown(), self.insert_table(r, c)))
        tbl_btn, tbl_pop = popover_button(big_label("󰓫", "Tabelle"), "Tabelle einfügen", tb_box, big=True)
        tbl_holder["pop"] = tbl_pop
        tbl_pop.connect("show", lambda *_: tb_box.reset())
        img_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        h = Gtk.Label(label="BILD", xalign=0)
        h.add_css_class("wpop-head")
        img_box.append(h)
        img_pop_holder = {}

        def img_item(label, cb):
            b = Gtk.Button(label=label)
            b.add_css_class("wt")
            b.connect("clicked", lambda *_: (img_pop_holder["pop"].popdown(), cb()))
            img_box.append(b)
        img_item("Bild aus Datei einfügen …", self.pick_image)
        sub = Gtk.Label(label="Größe des Bilds am Cursor", xalign=0, margin_top=6)
        sub.add_css_class("wstatus")
        img_box.append(sub)
        for pct in (25, 50, 75, 100):
            img_item(f"{pct} % der Seitenbreite", lambda p=pct: self.resize_image(p / 100))
        img_item("Originalgröße", lambda: self.resize_image(None))
        img_btn, img_pop_holder["pop"] = popover_button(big_label("󰋩", "Bild"), "Bild einfügen / Größe ändern",
                                                        img_box, big=True)
        link_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        h = Gtk.Label(label="LINK", xalign=0)
        h.add_css_class("wpop-head")
        link_box.append(h)
        self.link_text = Gtk.Entry(placeholder_text="Angezeigter Text")
        self.link_url = Gtk.Entry(placeholder_text="https://…")
        for e in (self.link_text, self.link_url):
            e.add_css_class("pb")
            e.set_width_chars(28)
            link_box.append(e)
        lrow = Gtk.Box(spacing=6)
        lok = Gtk.Button(label="Übernehmen")
        lok.add_css_class("pb"); lok.add_css_class("small")
        lrm = Gtk.Button(label="Link entfernen")
        lrm.add_css_class("pb"); lrm.add_css_class("small")
        lrow.append(lok)
        lrow.append(lrm)
        link_box.append(lrow)
        self.link_btn, self.link_pop = popover_button(big_label("\U000F0337", "Link"), "Link einfügen (Strg+K)",
                                                      link_box, big=True)
        self.link_pop.connect("show", lambda *_: self.prepare_link())
        lok.connect("clicked", lambda *_: self.apply_link())
        self.link_url.connect("activate", lambda *_: self.apply_link())
        lrm.connect("clicked", lambda *_: self.apply_link(remove=True))
        group(ins, "Tabellen", [tbl_btn])
        group(ins, "Illustrationen", [img_btn])
        group(ins, "Hyperlinks", [self.link_btn])
        group(ins, "Seiten", [big_tool("󰛗", "Seitenumbruch", "Seitenumbruch (Strg+Enter)", lambda *_: self.insert_block("pb")),
                              big_tool("󰍴", "Linie", "Waagerechte Linie", lambda *_: self.insert_block("hr"))])
        sym_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        h = Gtk.Label(label="SONDERZEICHEN", xalign=0)
        h.add_css_class("wpop-head")
        sym_box.append(h)
        grid = Gtk.Grid(row_spacing=3, column_spacing=3)
        sym_holder = {}
        for i, ch in enumerate(SYMBOLS):
            b = Gtk.Button(label=ch, focus_on_click=False)
            b.add_css_class("sym-b")
            b.connect("clicked", lambda _b, c=ch: (sym_holder["pop"].popdown(), self.insert_text(c)))
            grid.attach(b, i % 10, i // 10, 1, 1)
        sym_box.append(grid)
        sym_btn, sym_holder["pop"] = popover_button(big_label("Ω", "Symbol"), "Sonderzeichen einfügen", sym_box, big=True)
        group(ins, "Text", [big_tool("\U000F00F0", "Datum", "Heutiges Datum einfügen", lambda *_: self.insert_date()),
                            sym_btn])
        group(ins, "Verweise", [big_tool("󰉺", "Inhalt", "Inhaltsverzeichnis einfügen – füllt sich selbst aus den Überschriften",
                                         lambda *_: self.insert_block("toc")),
                                big_tool("󰆈", "Fußnote", "Fußnote an der Cursorstelle (Strg+Alt+F)",
                                         lambda *_: self.insert_footnote())], last=True)

        # ================= Layout =================
        lay = page("layout")
        group(lay, "Seite einrichten", [self.page_size_button(), self.page_orient_button(), self.page_margin_button()])
        group(lay, "Kopf- & Fußzeile", [self.page_hf_button(), self.page_num_button()])
        group(lay, "Einzug", [big_tool("󰉵", "Weniger", "Einzug verkleinern", lambda *_: self.change_indent(-1)),
                              big_tool("󰉶", "Mehr", "Einzug vergrößern", lambda *_: self.change_indent(1))])
        sp_row = Gtk.Box(spacing=2)
        self.spacing_chips = {}
        for v in (1.0, 1.15, 1.5, 2.0):
            b = Gtk.ToggleButton(label=f"{v:g}".replace(".", ","), focus_on_click=False, can_focus=False,
                                 tooltip_text=f"Zeilenabstand {v:g}".replace(".", ","))
            b.add_css_class("wt")
            b.connect("clicked", lambda btn, x=v: self._sync or self.on_spacing(btn, x))
            sp_row.append(b)
            self.spacing_chips[v] = b
        group(lay, "Zeilenabstand", sp_row)
        group(lay, "Umbruch", [big_tool("󰛗", "Seite", "Seitenumbruch (Strg+Enter)", lambda *_: self.insert_block("pb"))],
              last=True)

        # ================= Ansicht =================
        view = page("view")
        self.tools["paper"] = big_tool("󰖙", "Helles Papier", "Weißes Papier statt Theme-Farben", toggle=True)
        self.tools["paper"].set_active(self.light)
        self.tools["paper"].connect("toggled", self.on_paper_toggle)
        self.tools["nav"] = big_tool("󰠶", "Navigation", "Überschriften links anzeigen und anspringen", toggle=True)
        self.tools["nav"].set_active(self.settings.get("nav", False))
        self.tools["nav"].connect("toggled", lambda b: self.show_nav(b.get_active()))
        group(view, "Anzeigen", [self.tools["paper"], self.tools["nav"]])
        group(view, "Zoom", [tool("󰍴", "Verkleinern (Strg+−)", lambda *_: self.step_zoom(-1)),
                             tool("100 %", "Originalgröße", lambda *_: self.set_zoom(1.0)),
                             tool("󰐕", "Vergrößern (Strg++)", lambda *_: self.step_zoom(1))],
              [tool("󰹑 Seitenbreite", "Seite füllt die Breite", lambda *_: self.fit_width())])
        self.tool_tail = group(view, "Prüfen", [], last=True).body.get_first_child()   # notist hängt hier die Rechtschreibung an
        self.tool_tail.append(big_tool("󰄨", "Statistik", "Wörter, Zeichen, Absätze zählen", lambda *_: self.show_stats()))

        self.tab_btns[self.settings.get("ribbon_tab", "start")].set_active(True)
        self.update_collapse_icon()
        return outer

    def build_flowbar(self):
        """Leiste der Ansicht „fließend“: Datei, Rückgängig, Zeichen- und Absatzformat, Link, Einfügen und rechts
        Autokorrektur + weitere Einstellungen. Bricht im schmalen Fenster in eine zweite Zeile um."""
        bar = Gtk.Box(spacing=0, visible=False)
        bar.add_css_class("flowbar")
        wrap = Gtk.Box()
        wrap.set_layout_manager(WrapLayout(spacing=2, row_spacing=2))
        wrap.set_hexpand(True)
        bar.append(wrap)
        self.ftools = {}
        fb = Gtk.MenuButton(tooltip_text="Öffnen, Exportieren, Drucken", can_focus=False)
        fb.set_popover(file_menu())
        fb.set_child(Gtk.Label(label="󰈙  Datei"))
        fb.add_css_class("file-tab")
        wrap.append(fb)
        self.flow_undo = tool("󰕌", "Rückgängig (Strg+Z)", lambda *_: self.undo())
        self.flow_redo = tool("󰑎", "Wiederholen (Strg+Umschalt+Z)", lambda *_: self.redo())

        def sep():
            b = Gtk.Box(valign=Gtk.Align.CENTER)
            b.add_css_class("fsep")
            return b

        def tg(key, label, tip, cb, markup=False):
            b = tool(label, tip, lambda btn: self._sync or cb(), toggle=True, markup=markup)
            self.ftools[key] = b
            return b
        group = [self.flow_undo, self.flow_redo, sep(),
                 tg("b", "<b>F</b>", "Fett (Strg+B)", lambda: self.toggle_char("b"), True),
                 tg("i", "<i>K</i>", "Kursiv (Strg+I)", lambda: self.toggle_char("i"), True),
                 tg("u", "<u>U</u>", "Unterstrichen (Strg+U)", lambda: self.toggle_char("u"), True),
                 tg("s", "<s>S</s>", "Durchgestrichen (Strg+D)", lambda: self.toggle_char("s"), True), sep()]
        for st, lab in (("h1", "H1"), ("h2", "H2"), ("h3", "H3")):
            group.append(tg("ps:" + st, lab, f"Überschrift {lab[1]} (Strg+{lab[1]})",
                            lambda st=st: self.set_style("normal" if self.para_at(self.cursor_line())["style"] == st
                                                         else st)))
        group += [tg("bullet", "󰉹", "Aufzählung (Strg+Umschalt+L)", lambda: self.toggle_list("bullet")),
                  tg("number", "󰉻", "Nummerierung (Strg+Umschalt+N)", lambda: self.toggle_list("number")),
                  tg("ps:quote", "󰝗", "Zitat", lambda: self.set_style(
                      "normal" if self.para_at(self.cursor_line())["style"] == "quote" else "quote")),
                  tg("ps:code", "󰅩", "Code", lambda: self.set_style(
                      "normal" if self.para_at(self.cursor_line())["style"] == "code" else "code")), sep()]
        self.flow_link = Gtk.MenuButton(tooltip_text="Link (Strg+K)", focus_on_click=False)
        self.flow_link.set_child(Gtk.Label(label="󰌷"))
        self.flow_link.add_css_class("wt")
        group.append(self.flow_link)
        ins = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        h = Gtk.Label(label="EINFÜGEN", xalign=0)
        h.add_css_class("wpop-head")
        ins.append(h)
        ins_btn, ins_pop = popover_button("󰐕 einfügen …", "Tabelle, Bild, Linie, Inhaltsverzeichnis … (oder „/“ tippen)",
                                          ins)
        import flow as _flow
        for key, icon, name, _k in _flow.BLOCKS:
            if key in ("normal", "h1", "h2", "h3", "bullet", "number", "quote", "code"):
                continue
            b = Gtk.Button(focus_on_click=False)
            b.add_css_class("fm-item")
            r = Gtk.Box(spacing=8)
            ic = Gtk.Label(label=icon)
            ic.add_css_class("fm-icon")
            r.append(ic)
            r.append(Gtk.Label(label=name, xalign=0, hexpand=True))
            b.set_child(r)
            b.connect("clicked", lambda _b, k=key: (ins_pop.popdown(), self.flowx.insert(k)))
            ins.append(b)
        ins_pop.add_css_class("file-menu")
        group.append(ins_btn)
        for w in group:
            wrap.append(w)
        # rechts: Autokorrektur + Einstellungen
        right = Gtk.Box(spacing=2, valign=Gtk.Align.START)
        self.ftools["smart"] = tool("󰁨", "Autokorrektur an/aus (SChreibstift → Schreibstift, Tippfehler)",
                                    lambda b: self._sync or self.toggle_opt("smart"), toggle=True)
        self.ftools["spell"] = tool("󰓆", "Rechtschreibprüfung an/aus",
                                    lambda b: self._sync or self.toggle_opt("spell"), toggle=True)
        right.append(self.ftools["smart"])
        right.append(self.ftools["spell"])
        opts = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, width_request=290)
        h = Gtk.Label(label="SCHREIBEN", xalign=0)
        h.add_css_class("wpop-head")
        opts.append(h)
        self.fopt_sw = {}
        for key, text in (("smart", "Autokorrektur (Tippfehler, SChreibstift)"), ("typo", "Typografie („…“, – , →)"),
                          ("autocap", "Satzanfang groß"), ("markdown", "Markdown beim Tippen (# , - , **)"),
                          ("spell", "Rechtschreibung unterstreichen"), ("typewriter", "Mitscrollen (halbe Seite Luft)")):
            row = Gtk.Box(spacing=8)
            row.append(Gtk.Label(label=text, xalign=0, hexpand=True, wrap=True, max_width_chars=30))
            sw = Gtk.Switch(valign=Gtk.Align.CENTER)
            sw.connect("notify::active", lambda w, _p, k=key: self._sync or self.toggle_opt(k, w.get_active()))
            row.append(sw)
            self.fopt_sw[key] = sw
            opts.append(row)
        h = Gtk.Label(label="ANSICHT", xalign=0, margin_top=6)
        h.add_css_class("wpop-head")
        opts.append(h)
        zrow = Gtk.Box(spacing=4)
        zrow.append(Gtk.Label(label="Zoom", xalign=0, hexpand=True))
        for lab, tip, cb in (("−", "Kleiner (Strg+−)", lambda *_: self.step_zoom(-1)),
                             ("100 %", "Normalgröße", lambda *_: self.set_zoom(1.0)),
                             ("+", "Größer (Strg++)", lambda *_: self.step_zoom(1))):
            b = Gtk.Button(label=lab, tooltip_text=tip, focus_on_click=False)
            b.add_css_class("tchip")
            b.connect("clicked", cb)
            zrow.append(b)
        opts.append(zrow)
        pg = Gtk.Button(label="󰈙  zur seitenansicht (wie word)", focus_on_click=False)
        pg.add_css_class("tchip")
        pg.connect("clicked", lambda *_: (self.fopt_pop.popdown(), self.set_flow(False, user=True)))
        opts.append(pg)
        hint = Gtk.Label(label="„/“ am zeilenanfang öffnet die blöcke · text markieren zeigt eine formatleiste · "
                               "„+“ links neben einer zeile", xalign=0, wrap=True, max_width_chars=36)
        hint.add_css_class("tsub")
        opts.append(hint)
        ob, self.fopt_pop = popover_button("󰒓", "Weitere Einstellungen: Autokorrektur, Typografie, Markdown, Zoom", opts)
        self.fopt_pop.connect("show", lambda *_: self.sync_flowbar())
        right.append(ob)
        bar.append(right)
        return bar

    def cursor_line(self):
        return self.buf.get_iter_at_mark(self.buf.get_insert()).get_line()

    # Optionen (Autokorrektur & Co.) gehören notist – es setzt hier opt_get/opt_set ein
    opt_get = None
    opt_set = None

    def toggle_opt(self, key, value=None):
        if not self.opt_get or not self.opt_set:
            return
        if value is not None and bool(self.opt_get(key)) == bool(value):
            return
        self.opt_set(key)
        self.sync_flowbar()

    def sync_flowbar(self):
        if not getattr(self, "ftools", None) or not self.flow:
            return
        self._sync = True
        try:
            a = self.para_at(self.cursor_line())
            for k in ("b", "i", "u", "s"):
                self.ftools[k].set_active(bool(self.active.get(k)))
            for st in ("h1", "h2", "h3", "quote", "code"):
                self.ftools["ps:" + st].set_active(a["style"] == st)
            self.ftools["bullet"].set_active(a["list"] == "bullet")
            self.ftools["number"].set_active(a["list"] == "number")
            if self.opt_get:
                for k in ("smart", "spell"):
                    self.ftools[k].set_active(bool(self.opt_get(k)))
                for k, sw in self.fopt_sw.items():
                    sw.set_active(bool(self.opt_get(k)))
            for k in ("smart", "spell"):
                self.ftools[k].set_visible(self.opt_get is not None)
        finally:
            self._sync = False

    def open_link(self):
        """Strg+K / Link-Knopf: das Link-Fenster hängt je nach Ansicht am Menüband oder an der Fließend-Leiste."""
        (self.flow_link if self.flow else self.link_btn).popup()

    def _move_link_pop(self):
        want = self.flow_link if self.flow else self.link_btn
        other = self.link_btn if self.flow else self.flow_link
        if want.get_popover() is not self.link_pop:
            other.set_popover(None)
            want.set_popover(self.link_pop)

    def set_flow(self, on, user=False):
        """Ansicht wechseln: „seiten“ (wie Word) ↔ „fließend“ (wie Notion). Inhalt und Datei bleiben gleich."""
        self.flow = bool(on)
        self.flowx.leave()
        self.ribbon_box.set_visible(not self.flow)
        self.flowbar.set_visible(self.flow)
        self._move_link_pop()
        self.sync_flowbar()
        (self.view.add_css_class if self.flow else self.view.remove_css_class)("flow")
        (self.scroll.add_css_class if self.flow else self.scroll.remove_css_class)("flow")
        self.view_btn.set_label("󰈙 seiten" if self.flow else "󰉺 fließend")
        self.view_btn.set_tooltip_text("Zur Seitenansicht wie in Word wechseln" if self.flow else
                                       "Zur fließenden Ansicht wie in Notion wechseln: ohne Seiten, „/“ für Blöcke")
        if self.flow:                       # Seitenabstände weg
            table = self.buf.get_tag_table()
            pgs = []
            table.foreach(lambda t: pgs.append(t) if t.props.name and t.props.name.startswith("pg:") else None)
            for t in pgs:
                self.buf.remove_tag(t, self.buf.get_start_iter(), self.buf.get_end_iter())
            self.pages = [0.0]
        self.apply_paper()
        self.update_geometry()
        if user:
            self.settings["last_view"] = "flow" if self.flow else "page"
            if self.on_view_change:
                self.on_view_change(self.flow)
            self.focus_text()

    def set_compact(self, on):
        """Halbe Bildschirmbreite: Galerie ausblenden (die Liste daneben kann alles), Datei-Knopf nur als Symbol."""
        for b in self.style_chips.values():
            b.get_parent().set_visible(not on)
            break

    # ---------- Seite einrichten (Reiter Layout) ----------
    def page_size_button(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        h = Gtk.Label(label="PAPIERFORMAT", xalign=0)
        h.add_css_class("wpop-head")
        box.append(h)
        holder = {}
        self.size_btns = {}
        for key, (w, hh) in df.PAGE_SIZES.items():
            b = Gtk.ToggleButton(label=f"{key}  ({w:g} × {hh:g} mm)".replace(".", ","))
            b.add_css_class("wt")
            b.get_child().set_xalign(0)
            b.connect("clicked", lambda btn, k=key: self._sync or (holder["pop"].popdown(), self.set_page({**self.page, "size": k})))
            box.append(b)
            self.size_btns[key] = b
        mb, holder["pop"] = popover_button(big_label("󰈔", "Format"), "Papierformat", box, big=True)
        holder["pop"].connect("show", lambda *_: self.sync_page_ui())
        return mb

    def page_orient_button(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        h = Gtk.Label(label="AUSRICHTUNG", xalign=0)
        h.add_css_class("wpop-head")
        box.append(h)
        holder = {}
        self.orient_btns = {}
        for key, label in (("portrait", "󰟇  Hochformat"), ("landscape", "󰟆  Querformat")):
            b = Gtk.ToggleButton(label=label)
            b.add_css_class("wt")
            b.get_child().set_xalign(0)
            b.connect("clicked", lambda btn, k=key: self._sync or (holder["pop"].popdown(), self.set_page({**self.page, "orient": k})))
            box.append(b)
            self.orient_btns[key] = b
        mb, holder["pop"] = popover_button(big_label("󰑊", "Ausrichtung"), "Hoch- oder Querformat", box, big=True)
        holder["pop"].connect("show", lambda *_: self.sync_page_ui())
        return mb

    def page_margin_button(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        h = Gtk.Label(label="SEITENRÄNDER", xalign=0)
        h.add_css_class("wpop-head")
        box.append(h)
        holder = {}
        for name, m in df.MARGIN_PRESETS.items():
            t, r, b_, l = (f"{x / 10:g}".replace(".", ",") for x in m)
            b = Gtk.Button(label=f"{name}   oben {t} · unten {b_} · links {l} · rechts {r} cm")
            b.add_css_class("wt")
            b.get_child().set_xalign(0)
            b.connect("clicked", lambda *_, mm=m: (holder["pop"].popdown(), self.set_page({**self.page, "margins": list(mm)})))
            box.append(b)
        h = Gtk.Label(label="EIGENE (CM)", xalign=0, margin_top=6)
        h.add_css_class("wpop-head")
        box.append(h)
        grid = Gtk.Grid(column_spacing=8, row_spacing=4)
        self.margin_spins = []
        for i, name in enumerate(("Oben", "Rechts", "Unten", "Links")):
            sp = Gtk.SpinButton.new_with_range(0, 8, 0.1)
            sp.set_digits(2)
            sp.add_css_class("wt")
            sp.connect("value-changed", self.on_margin_spin)
            grid.attach(Gtk.Label(label=name, xalign=0), (i % 2) * 2, i // 2, 1, 1)
            grid.attach(sp, (i % 2) * 2 + 1, i // 2, 1, 1)
            self.margin_spins.append(sp)
        box.append(grid)
        mb, holder["pop"] = popover_button(big_label("󰩨", "Ränder"), "Seitenränder", box, big=True)
        holder["pop"].connect("show", lambda *_: self.sync_page_ui())
        return mb

    def on_margin_spin(self, *_):
        if self._sync:
            return
        if getattr(self, "_margin_id", None):
            GLib.source_remove(self._margin_id)
        vals = [round(s.get_value() * 10, 1) for s in self.margin_spins]
        self._margin_id = GLib.timeout_add(300, lambda: (setattr(self, "_margin_id", None),
                                                         self.set_page({**self.page, "margins": vals}), False)[-1])

    def page_hf_button(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        h = Gtk.Label(label="KOPFZEILE", xalign=0)
        h.add_css_class("wpop-head")
        box.append(h)
        self.header_entry = Gtk.Entry(placeholder_text="z. B. {titel}  –  Max Mustermann", width_chars=34)
        self.header_entry.add_css_class("pb")
        box.append(self.header_entry)
        h = Gtk.Label(label="FUSSZEILE", xalign=0)
        h.add_css_class("wpop-head")
        box.append(h)
        self.footer_entry = Gtk.Entry(placeholder_text="z. B. Universität … · {datum}", width_chars=34)
        self.footer_entry.add_css_class("pb")
        box.append(self.footer_entry)
        hint = Gtk.Label(xalign=0, wrap=True, max_width_chars=40, label=(
            "Platzhalter: {seite} {seiten} {titel} {datum}\nSeitenzahlen stellst du daneben unter „Seitenzahl“ ein."))
        hint.add_css_class("hf-help")
        box.append(hint)
        for e, key in ((self.header_entry, "header"), (self.footer_entry, "footer")):
            e.connect("changed", lambda en, k=key: self._sync or self.set_page({**self.page, k: en.get_text()}))
        mb, pop = popover_button(big_label("󰕵", "Kopf/Fuß"), "Kopf- und Fußzeile", box, big=True)
        pop.connect("show", lambda *_: self.sync_page_ui())
        self.hf_pop = pop
        return mb

    def page_num_button(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        h = Gtk.Label(label="SEITENZAHL", xalign=0)
        h.add_css_class("wpop-head")
        box.append(h)
        self.num_pos = Gtk.DropDown.new_from_strings(list(df.NUM_POS.values()))
        self.num_fmt = Gtk.DropDown.new_from_strings(list(df.NUM_FMT.values()))
        self.num_from = Gtk.SpinButton.new_with_range(1, 99, 1)
        for label, w in (("Position", self.num_pos), ("Aussehen", self.num_fmt), ("Ab Seite", self.num_from)):
            r = Gtk.Box(spacing=8)
            r.append(Gtk.Label(label=label, xalign=0, hexpand=True))
            w.add_css_class("wt")
            r.append(w)
            box.append(r)
        hint = Gtk.Label(xalign=0, wrap=True, max_width_chars=34,
                         label="„Ab Seite 2“ lässt z. B. die Titelseite ohne Nummer.")
        hint.add_css_class("hf-help")
        box.append(hint)

        def changed(*_):
            if self._sync:
                return
            self.set_page({**self.page, "numbers": list(df.NUM_POS)[self.num_pos.get_selected()],
                           "num_fmt": list(df.NUM_FMT)[self.num_fmt.get_selected()],
                           "num_from": int(self.num_from.get_value())})
        self.num_pos.connect("notify::selected", changed)
        self.num_fmt.connect("notify::selected", changed)
        self.num_from.connect("value-changed", changed)
        mb, pop = popover_button(big_label("󰎠", "Seitenzahl"), "Seitenzahlen", box, big=True)
        pop.connect("show", lambda *_: self.sync_page_ui())
        return mb

    def sync_page_ui(self):
        p = self.page
        self._sync = True
        for k, b in self.size_btns.items():
            b.set_active(k == p["size"])
        for k, b in self.orient_btns.items():
            b.set_active(k == p["orient"])
        for sp, v in zip(self.margin_spins, p["margins"]):
            sp.set_value(v / 10)
        for e, key in ((self.header_entry, "header"), (self.footer_entry, "footer")):
            if e.get_text() != p.get(key, ""):
                e.set_text(p.get(key, ""))
        self.num_pos.set_selected(list(df.NUM_POS).index(p["numbers"]) if p["numbers"] in df.NUM_POS else 0)
        self.num_fmt.set_selected(list(df.NUM_FMT).index(p["num_fmt"]) if p["num_fmt"] in df.NUM_FMT else 0)
        self.num_from.set_value(p.get("num_from", 1))
        self._sync = False

    def on_tab(self, btn, key):
        if btn.get_active():
            self.ribbon_stack.set_visible_child_name(key)
            self.settings["ribbon_tab"] = key

    def on_tab_click(self, key, n):
        # eingeklappt: ein Klick auf den Reiter klappt wieder auf; Doppelklick klappt ein (wie in Word)
        if n == 2:
            self.toggle_ribbon()
        elif not self.ribbon_rev.get_reveal_child():
            self.toggle_ribbon()

    def toggle_ribbon(self):
        on = not self.ribbon_rev.get_reveal_child()
        self.ribbon_rev.set_reveal_child(on)
        if not self._short:                  # im niedrigen Fenster nur vorübergehend, Einstellung bleibt
            self.settings["ribbon_collapsed"] = not on
        self.update_collapse_icon()

    def set_short(self, on):
        """Niedriges Fenster (z. B. Viertel-Kachel): Menüband eingeklappt, damit die Seite Platz hat.
        Ein Klick auf einen Reiter klappt es trotzdem auf."""
        if on == self._short:
            return
        self._short = on
        self.ribbon_rev.set_reveal_child(False if on else not self.settings.get("ribbon_collapsed", False))
        self.update_collapse_icon()

    def update_collapse_icon(self):
        self.collapse_btn.get_child().set_label("󰅃" if self.ribbon_rev.get_reveal_child() else "󰅀")

    def insert_text(self, text):
        if self.editable:
            self.buf.insert_at_cursor(text)
            self.focus_text()

    def fit_width(self):
        w = self.view.get_width()
        if w > 0:
            self.set_zoom(max(0.5, min(3.0, (w - 2 * 24) / (df.page_mm(self.page)[0] * 96 / 25.4))))

    def show_stats(self):
        txt = self.plain_text()
        words = len(txt.split())
        chars = len(txt.replace("￼", ""))
        nospace = len("".join(txt.split()).replace("￼", ""))
        paras = sum(1 for l in txt.split("\n") if l.strip())
        pages = max(1, len(self.pages))
        lines = [("Seiten", pages), ("Wörter", words), ("Zeichen (mit Leerzeichen)", chars),
                 ("Zeichen (ohne Leerzeichen)", nospace), ("Absätze", paras),
                 ("Lesezeit", f"≈ {max(1, round(words / 220))} Min")]
        sel = self.selection_counts()
        if sel:
            lines += [("Markiert: Wörter", sel[0]), ("Markiert: Zeichen", sel[1])]
        box = Gtk.Grid(row_spacing=4, column_spacing=18)
        h = Gtk.Label(label="STATISTIK", xalign=0)
        h.add_css_class("wpop-head")
        box.attach(h, 0, 0, 2, 1)
        for i, (k, v) in enumerate(lines, start=1):
            box.attach(Gtk.Label(label=k, xalign=0), 0, i, 1, 1)
            l = Gtk.Label(label=f"{v:,}".replace(",", ".") if isinstance(v, int) else v, xalign=1)
            l.add_css_class("stat-v")
            box.attach(l, 1, i, 1, 1)
        pop = ist_pop(Gtk.Popover())
        pop.set_child(box)
        pop.set_parent(self.count_label)
        pop.connect("closed", lambda p: GLib.idle_add(lambda: p.unparent() or False))
        pop.popup()

    def color_button(self, icon, tip, palette, kind, none_label):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        head = Gtk.Label(label=tip, xalign=0)
        head.add_css_class("wpop-head")
        box.append(head)
        grid = Gtk.Grid(row_spacing=4, column_spacing=4)
        cols = 6 if len(palette) > 8 else 4
        holder = {}
        for i, hexc in enumerate(palette):
            b = Gtk.Button(tooltip_text=hexc)
            b.add_css_class("swatch-b")
            area = Gtk.DrawingArea(content_width=16, content_height=16)
            area.set_draw_func(lambda a, cr, w, h, c=hexc: (cr.set_source_rgba(*self._rgb(c)), cr.paint()))
            b.set_child(area)
            b.connect("clicked", lambda _b, c=hexc: (holder["pop"].popdown(), self.set_color(kind, c)))
            grid.attach(b, i % cols, i // cols, 1, 1)
        box.append(grid)
        row = Gtk.Box(spacing=6)
        none = Gtk.Button(label=none_label)
        none.add_css_class("pb"); none.add_css_class("small")
        none.connect("clicked", lambda *_: (holder["pop"].popdown(), self.set_color(kind, None)))
        more = Gtk.Button(label="Eigene …")
        more.add_css_class("pb"); more.add_css_class("small")
        more.connect("clicked", lambda *_: (holder["pop"].popdown(), self.pick_color(kind)))
        row.append(none)
        row.append(more)
        box.append(row)
        inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        lab = Gtk.Label(label=icon)
        bar = Gtk.DrawingArea(content_height=3, content_width=14)
        bar.color = "#e06666" if kind == "fg" else "#ffff00"
        bar.set_draw_func(lambda a, cr, w, h: (cr.set_source_rgba(*self._rgb(a.color)), cr.paint()))
        inner.append(lab)
        inner.append(bar)
        mb = Gtk.MenuButton(tooltip_text=tip, focus_on_click=False)
        mb.set_child(inner)
        mb.add_css_class("wt")
        pop = ist_pop(Gtk.Popover())
        pop.set_child(box)
        mb.set_popover(pop)
        keep_focus(mb, pop)
        holder["pop"] = pop
        return mb, bar

    @staticmethod
    def _rgb(hexc):
        c = rgba(hexc)
        return c.red, c.green, c.blue, 1.0

    def build_findbar(self):
        bar = Gtk.Box()
        bar.set_layout_manager(WrapLayout(spacing=6, row_spacing=4))   # bricht in schmalen Fenstern um
        bar.add_css_class("findbar")
        self.find_entry = Gtk.SearchEntry(placeholder_text="Im Dokument suchen", width_chars=18)
        self.find_entry.add_css_class("pb")
        self.find_entry.connect("search-changed", lambda *_: self.run_search())
        self.find_entry.connect("activate", lambda *_: self.find_step(1))
        self.find_entry.connect("stop-search", lambda *_: self.hide_find())
        self.repl_entry = Gtk.Entry(placeholder_text="Ersetzen durch", width_chars=16)
        self.repl_entry.add_css_class("pb")
        self.repl_entry.connect("activate", lambda *_: self.replace_one())
        self.case_btn = Gtk.ToggleButton(label="Aa", tooltip_text="Groß-/Kleinschreibung beachten")
        self.case_btn.add_css_class("wt")
        self.case_btn.connect("toggled", lambda *_: self.run_search())
        self.find_info = Gtk.Label(label="")
        self.find_info.add_css_class("wstatus")
        bar.append(self.find_entry)
        for lab, tip, cb in (("󰅃", "Vorheriger Treffer (Umschalt+Enter)", lambda *_: self.find_step(-1)),
                             ("󰅀", "Nächster Treffer (Enter)", lambda *_: self.find_step(1))):
            bar.append(tool(lab, tip, cb))
        bar.append(self.case_btn)
        bar.append(self.repl_entry)
        for lab, cb in (("Ersetzen", lambda *_: self.replace_one()), ("Alle ersetzen", lambda *_: self.replace_all())):
            b = Gtk.Button(label=lab, focus_on_click=False)
            b.add_css_class("pb"); b.add_css_class("small")
            b.connect("clicked", cb)
            bar.append(b)
        bar.append(self.find_info)
        bar.append(tool("󰅖", "Schließen (Esc oder Strg+F)", lambda *_: self.hide_find()))
        k = Gtk.EventControllerKey()
        k.connect("key-pressed", self.on_find_key)
        bar.add_controller(k)
        self.findrev = Gtk.Revealer(transition_type=Gtk.RevealerTransitionType.SLIDE_DOWN, reveal_child=False)
        self.findrev.set_child(bar)
        return self.findrev

    def build_status(self):
        bar = Gtk.Box(spacing=6, margin_top=6)
        bar.add_css_class("wstatus")
        self.count_btn = Gtk.Button(focus_on_click=False, can_focus=False, tooltip_text="Statistik anzeigen")
        self.count_btn.add_css_class("wt")
        self.count_label = Gtk.Label(xalign=0, ellipsize=3)
        self.count_btn.set_child(self.count_label)
        self.count_btn.set_hexpand(True)
        self.count_btn.set_halign(Gtk.Align.START)
        self.count_btn.connect("clicked", lambda *_: self.show_stats())
        bar.append(self.count_btn)
        bar.append(tool("󰍴", "Verkleinern (Strg+−)", lambda *_: self.step_zoom(-1)))
        self.zoom_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0.3, 3.0, 0.05)
        self.zoom_scale.add_css_class("zoom")
        self.zoom_scale.set_can_focus(False)
        self.zoom_scale.add_mark(1.0, Gtk.PositionType.BOTTOM, None)
        self.zoom_scale.set_value(self.zoom)
        self.zoom_scale.connect("value-changed", lambda sc: self._sync or self.set_zoom(round(sc.get_value(), 2)))
        bar.append(self.zoom_scale)
        bar.append(tool("󰐕", "Vergrößern (Strg++)", lambda *_: self.step_zoom(1)))
        self.zoom_btn = Gtk.Button(tooltip_text="Auf 100 % (Strg+0 auf dem Ziffernblock)", focus_on_click=False)
        self.zoom_btn.add_css_class("wt")
        self.zoom_btn.connect("clicked", lambda *_: self.set_zoom(1.0))
        bar.append(self.zoom_btn)
        self.zoom_btn.set_label(f"{round(self.zoom * 100)} %")
        return bar

    # ================= Navigationsbereich =================
    def show_nav(self, on):
        self.settings["nav"] = on
        self.navrev.set_reveal_child(on)
        if on:
            self.fill_nav()

    def queue_nav(self):
        if self.navrev.get_reveal_child() and self._nav_id is None:
            self._nav_id = GLib.timeout_add(400, self.fill_nav)

    def fill_nav(self):
        self._nav_id = None
        lb = self.nav_list
        while (r := lb.get_first_child()):
            lb.remove(r)
        n = 0
        for line in range(self.buf.get_line_count()):
            ok, it = self.buf.get_iter_at_line(line)
            names = self.names(it)
            style = next((x[3:] for x in names if x.startswith("ps:")), "normal")
            if style not in ("title", "h1", "h2", "h3"):
                continue
            s, e = self.line_bounds(line)
            text = self.buf.get_text(s, e, False).replace("￼", "").strip()
            if not text:
                continue
            row = Gtk.ListBoxRow()
            row.line = line
            lab = Gtk.Label(label=text, xalign=0, ellipsize=3,
                            margin_start={"title": 0, "h1": 0, "h2": 12, "h3": 24}[style])
            lab.add_css_class("nav-" + style)
            row.set_child(lab)
            lb.append(row)
            n += 1
        if not n:
            l = Gtk.Label(label="Noch keine Überschriften.\nFormatvorlage „Überschrift 1“ (Strg+1)\nmacht eine Zeile zur Überschrift.",
                          xalign=0, wrap=True)
            l.add_css_class("nav-empty")
            lb.append(l)
        return False

    def goto_line(self, line):
        ok, it = self.buf.get_iter_at_line(line)
        self.buf.place_cursor(it)
        self.view.scroll_to_iter(it, 0.05, True, 0, 0.1)
        self.focus_text()

    # ================= Tags =================
    def make_tags(self):
        b = self.buf
        self.zoom_tag = b.create_tag("zoom", scale=self.zoom)      # zuerst angelegt: niedrigste Priorität
        for s, props in STYLE_TAG.items():
            b.create_tag("ps:" + s, **props)
        self.quote_fg = b.create_tag("ps-quote-fg")
        for a, j in (("center", Gtk.Justification.CENTER), ("right", Gtk.Justification.RIGHT),
                     ("justify", Gtk.Justification.FILL)):
            b.create_tag("pa:" + a, justification=j)
        for v in LINE_SPACINGS:
            if v != 1.15:
                b.create_tag(f"pz:{v:g}", line_height=v / 1.15)
        b.create_tag("pl:bullet")
        b.create_tag("pl:number")
        b.create_tag("b", weight=Pango.Weight.BOLD)
        b.create_tag("i", style=Pango.Style.ITALIC)
        b.create_tag("u", underline=Pango.Underline.SINGLE)
        b.create_tag("s", strikethrough=True)
        self.sup_tag = b.create_tag("sup", scale=0.65)
        self.sub_tag = b.create_tag("sub", scale=0.65)
        self.search_tag = b.create_tag("search", background_rgba=rgba("#ffb300", 0.45))
        self.update_rise()

    def update_rise(self):
        self.sup_tag.props.rise = round(5.5 * self.zoom * Pango.SCALE)
        self.sub_tag.props.rise = round(-2.5 * self.zoom * Pango.SCALE)

    def tag(self, name):
        """Tag holen oder bei Bedarf anlegen (für Schrift, Größe, Farben, Links, Einzüge)."""
        t = self.buf.get_tag_table().lookup(name)
        if t:
            return t
        if name.startswith("font:"):
            return self.buf.create_tag(name, family=name[5:])
        if name.startswith("size:"):
            return self.buf.create_tag(name, size_points=float(name[5:]))
        if name.startswith("fg:"):
            return self.buf.create_tag(name, foreground_rgba=rgba(name[3:]))
        if name.startswith("hl:"):
            return self.buf.create_tag(name, background_rgba=rgba(name[3:]))
        if name.startswith("link:"):
            t = self.buf.create_tag(name, underline=Pango.Underline.SINGLE, foreground_rgba=rgba("#4a8fe7"))
            t.url = name[5:]
            return t
        if name.startswith("pi:"):
            return self.buf.create_tag(name)
        if name.startswith("m:"):
            t = self.buf.create_tag(name)
            self.margin_tags[float(name[2:])] = t
            self.size_margin_tag(float(name[2:]), t)
            return t
        return None

    def size_margin_tag(self, units, t):
        g = self.geo
        t.props.left_margin = round(g["side"] + g["ml"] + units * STEP * self.zoom * g["scale"])

    @staticmethod
    def names(it):
        return [t.props.name for t in it.get_tags() if t.props.name]

    def all_tags(self, prefixes=None, plain=()):
        out = []
        self.buf.get_tag_table().foreach(lambda t: out.append(t))
        return [t for t in out if t.props.name and (t.props.name in plain or
                                                    (prefixes and t.props.name.startswith(prefixes)))]

    # ================= Absätze =================
    def line_bounds(self, line):
        ok, s = self.buf.get_iter_at_line(line)
        e = s.copy()
        if not e.ends_line():
            e.forward_to_line_end()
        e2 = e.copy()
        e2.forward_char()           # Zeilenumbruch mitnehmen (trägt das Format leerer Zeilen)
        return s, e2

    def para_at(self, line):
        ok, it = self.buf.get_iter_at_line(line)
        if it.is_end() and self.pending_para and line == self.buf.get_line_count() - 1:
            return dict(self.pending_para)
        a = {"style": "normal", "align": "left", "list": None, "indent": 0, "spacing": 1.15}
        for n in self.names(it):
            if n.startswith("ps:"):
                a["style"] = n[3:]
            elif n.startswith("pa:"):
                a["align"] = n[3:]
            elif n.startswith("pl:"):
                a["list"] = n[3:]
            elif n.startswith("pi:"):
                a["indent"] = int(n[3:])
            elif n.startswith("pz:"):
                a["spacing"] = float(n[3:])
        return a

    def set_para(self, line, a):
        s, e = self.line_bounds(line)
        for t in self.all_tags(PARA_PREFIX, ("ps-quote-fg",)):
            self.buf.remove_tag(t, s, e)
        if s.equal(e):               # leere letzte Zeile: Format merken, bis getippt wird
            self.pending_para = dict(a)
            return
        if line == self.buf.get_line_count() - 1:
            self.pending_para = None
        if a.get("style", "normal") != "normal":
            self.buf.apply_tag(self.tag("ps:" + a["style"]), s, e)
            if a["style"] == "quote":
                self.buf.apply_tag(self.quote_fg, s, e)
        if a.get("align", "left") != "left":
            self.buf.apply_tag(self.tag("pa:" + a["align"]), s, e)
        if a.get("list"):
            self.buf.apply_tag(self.tag("pl:" + a["list"]), s, e)
        if a.get("indent"):
            self.buf.apply_tag(self.tag(f"pi:{a['indent']}"), s, e)
        sp = a.get("spacing", 1.15)
        if sp != 1.15:
            t = self.buf.get_tag_table().lookup(f"pz:{sp:g}") or \
                self.buf.create_tag(f"pz:{sp:g}", line_height=sp / 1.15)
            self.buf.apply_tag(t, s, e)
        units = a.get("indent", 0) + (1 if a.get("list") else 0) + (1.5 if a.get("style") == "quote" else 0)
        self.buf.apply_tag(self.tag(f"m:{units:g}"), s, e)
        self._numbers = None

    def selected_lines(self):
        b = self.buf.get_selection_bounds()
        if b:
            s, e = b
            last = e.get_line() - (1 if e.starts_line() and e.get_line() > s.get_line() else 0)
            return range(s.get_line(), last + 1)
        it = self.buf.get_iter_at_mark(self.buf.get_insert())
        return range(it.get_line(), it.get_line() + 1)

    def edit_paras(self, fn):
        if not self.editable:
            return
        self.checkpoint()
        for ln in self.selected_lines():
            a = self.para_at(ln)
            fn(a)
            self.set_para(ln, a)
        self.changed()
        self.sync_tools()

    # ================= Einfügen-Logik =================
    def before_insert(self, buf, loc, text, length):
        if self._loading:
            return
        self._ins_para = self.para_at(loc.get_line())
        self._ins_line = loc.get_line()
        self._ins_offset = loc.get_offset()
        self._ins_at_end = loc.ends_line()

    def after_insert(self, buf, loc, text, length):
        if self._loading:
            return
        if length == 1 and text in " *_~`" and self.settings.get("markdown", True) and not self._md_id:
            ln = loc.get_line()
            self._md_id = GLib.idle_add(lambda: self.md_live(ln, text))
        if self.flow and text == "/" and not self._quiet:
            self.flowx.start(loc)
        if length == 1 and self.autofmt_prefs is not None and not self._quiet:
            import autofmt
            autofmt.after_type(buf, loc, text, self.autofmt_prefs,
                               skip=lambda it: self.para_at(it.get_line()).get("style") == "code"
                               or any(t.props.name and t.props.name.startswith("link:") for t in it.get_tags()))
        start = buf.get_iter_at_offset(self._ins_offset)
        # Zeichenformat wie in Word: getippter Text übernimmt das aktive Format
        for t in self.all_tags(CHAR_PREFIX, CHAR_PLAIN):
            buf.remove_tag(t, start, loc)
        for k, v in self.active.items():
            name = {"font": "font:", "size": "size:", "fg": "fg:", "hl": "hl:", "link": "link:"}.get(k)
            t = self.tag(name + str(v)) if name else (self.tag(k) if v else None)
            if t:
                buf.apply_tag(t, start, loc)
        buf.apply_tag(self.zoom_tag, start, loc)
        # Absatzformat auf alle berührten Zeilen
        a = self._ins_para
        first, last = self._ins_line, loc.get_line()
        self._loading = True
        for ln in range(first, last + 1):
            pa = dict(a)
            if ln > first and self._ins_at_end and a["style"] in ("title", "h1", "h2", "h3"):
                pa["style"] = "normal"        # nach einer Überschrift geht es normal weiter
            self.set_para(ln, pa)
        self._loading = False

    # ================= Laden / Speichern =================
    def default_margin_mm(self):
        try:
            return float(self.settings.get("margin", 2.5)) * 10      # Einstellung in cm
        except (TypeError, ValueError):
            return 25.0

    def set_page(self, page, notify=True):
        self.page = df.norm_page(page, self.default_margin_mm())
        self.update_geometry()
        self.rescale_images()
        if notify and not self._loading:
            self.on_change()

    def load(self, blocks, title, page=None):
        self.page = df.norm_page(page, self.default_margin_mm())
        self._loading = True
        self.title.set_text(title or "")
        for anchor, w in list(self.blocks.items()):
            if w.get_parent():
                self.view.remove(w)
        self.blocks.clear()
        self.images.clear()
        self.buf.set_text("")
        self.pending_para = None
        paras = []
        for i, b in enumerate(blocks or [df.para()]):
            if i:
                self.buf.insert(self.buf.get_end_iter(), "\n")
            line = self.buf.get_line_count() - 1
            if b["t"] == "p":
                for r in b["runs"]:
                    self.insert_run(r)
                paras.append((line, {k: b.get(k) for k in ("style", "align", "list", "indent", "spacing")}))
            else:
                self.insert_anchor(b)
        for line, a in paras:
            self.set_para(line, a)
        self.buf.apply_tag(self.zoom_tag, self.buf.get_start_iter(), self.buf.get_end_iter())
        self.buf.place_cursor(self.buf.get_start_iter())
        self._loading = False
        self.active = self.char_at_cursor()
        self._numbers = None
        self.last_state = self.to_model()
        self.undo_stack, self.redo_stack = [], []
        self.update_undo_buttons()
        self.sync_tools()
        self.update_counts()
        self.invalidate()
        GLib.idle_add(lambda: self.scroll.get_vadjustment().set_value(0) and False)

    def insert_run(self, r, at=None):
        it = at or self.buf.get_end_iter()
        if r.get("img"):
            self.insert_image_data(base64.b64decode(r["img"]), r.get("mime"), r.get("w"), r.get("h"), it,
                                   b64=r["img"])
            return
        if r.get("fn") is not None:
            self.insert_anchor({"t": "fn", "text": r["fn"]}, it)
            return
        names = []
        for k in CHAR_PLAIN[:4]:
            if r.get(k):
                names.append(k)
        if r.get("va") in ("sup", "sub"):
            names.append(r["va"])
        for k, p in (("font", "font:"), ("size", "size:"), ("color", "fg:"), ("hl", "hl:"), ("link", "link:")):
            if r.get(k):
                names.append(p + (f"{float(r[k]):g}" if k == "size" else str(r[k])))
        tags = [self.tag(n) for n in names]
        self.buf.insert_with_tags(it, r["text"], *[t for t in tags if t])

    def insert_anchor(self, b, at=None):
        it = at or self.buf.get_end_iter()
        anchor = self.buf.create_child_anchor(it)
        w = {"table": lambda: TableBlock(self, b.get("rows"), b.get("style")), "hr": lambda: RuleBlock(self),
             "pb": lambda: BreakBlock(self), "toc": lambda: TocBlock(self),
             "fn": lambda: FootnoteMark(self, b.get("text", ""))}[b["t"]]()
        w.kind = b["t"]
        pointer_buttons(w)
        w.set_width(self.geo["text_w"] - 4)
        w.set_sensitive(self.editable)
        self.view.add_child_at_anchor(w, anchor)
        self.blocks[anchor] = w
        return anchor

    def char_props(self, names):
        r = {}
        for n in names:
            if n in ("b", "i", "u", "s"):
                r[n] = True
            elif n in ("sup", "sub"):
                r["va"] = n
            elif n.startswith("font:"):
                r["font"] = n[5:]
            elif n.startswith("size:"):
                r["size"] = float(n[5:])
            elif n.startswith("fg:"):
                r["color"] = n[3:]
            elif n.startswith("hl:"):
                r["hl"] = n[3:]
            elif n.startswith("link:"):
                r["link"] = n[5:]
        return r

    def to_model(self):
        out = []
        buf = self.buf
        for line in range(buf.get_line_count()):
            ok, s = buf.get_iter_at_line(line)
            e = s.copy()
            if not e.ends_line():
                e.forward_to_line_end()
            anchor = s.get_child_anchor()
            if anchor and anchor in self.blocks and e.get_offset() - s.get_offset() == 1 and \
                    self.blocks[anchor].kind != "fn":
                w = self.blocks[anchor]
                if w.kind == "table":
                    tb = {"t": "table", "rows": w.rows()}
                    if w.model_style():
                        tb["style"] = w.model_style()
                    out.append(tb)
                else:
                    out.append({"t": w.kind})
                continue
            p = df.para(**{k: v for k, v in self.para_at(line).items()})
            it = s.copy()
            while it.compare(e) < 0:
                seg_end = it.copy()
                seg_end.forward_to_tag_toggle(None)
                if seg_end.compare(e) > 0:
                    seg_end = e.copy()
                props = self.char_props(self.names(it))
                txt = buf.get_slice(it, seg_end, True)
                if "￼" in txt:
                    off = it.get_offset()
                    chunk = ""
                    for i, ch in enumerate(txt):
                        if ch == "￼":
                            if chunk:
                                p["runs"].append({**props, "text": chunk})
                                chunk = ""
                            pi = buf.get_iter_at_offset(off + i)
                            tex = pi.get_paintable()
                            anc = pi.get_child_anchor()
                            if tex is not None and tex in self.images:
                                p["runs"].append(dict(self.images[tex]))
                            elif anc is not None and anc in self.blocks and self.blocks[anc].kind == "fn":
                                p["runs"].append({"fn": self.blocks[anc].text, "text": ""})
                        else:
                            chunk += ch
                    if chunk:
                        p["runs"].append({**props, "text": chunk})
                elif txt:
                    p["runs"].append({**props, "text": txt})
                it = seg_end
            p["runs"] = df.merge_runs(p["runs"])
            out.append(p)
        return out

    def plain_text(self):
        txt = self.buf.get_text(self.buf.get_start_iter(), self.buf.get_end_iter(), False)
        extra = [" ".join(" ".join(r) for r in w.rows()) for w in self.blocks.values() if w.kind == "table"]
        extra += [w.text for w in self.blocks.values() if w.kind == "fn" and w.text]
        return "\n".join([txt] + extra).strip()

    def has_media(self):
        return bool(self.images) or any(w.kind in ("table", "hr", "toc") for w in self.blocks.values())

    # ================= Rückgängig =================
    def checkpoint(self):
        """Stand vor einer Formatierungsänderung festhalten."""
        if self._undo_pending:
            GLib.source_remove(self._undo_pending)
            self._undo_pending = None
            self.commit()
        cur = self.to_model()
        off = self.cursor_offset()
        if cur != self.last_state:          # noch nicht übernommenes Tippen wird ein eigener Schritt
            self.undo_stack.append((self.last_state, off))
            self.last_state = cur
        self.undo_stack.append((cur, off))  # Stand vor der Formatierung = ein Schritt
        del self.undo_stack[:-200]
        self._force_next = True

    def changed(self):
        """Nach jeder Änderung: Speichern anstoßen und Rückgängig-Schritt bündeln."""
        if self._loading:
            return
        self.invalidate()
        self.update_counts()
        self.on_change()
        if getattr(self, "_force_next", False):
            self._force_next = False
            self.last_state = self.to_model()
            if self.undo_stack and self.undo_stack[-1][0] == self.last_state:
                self.undo_stack.pop()       # hat sich nichts geändert (z. B. gleiche Schrift gewählt)
            self.redo_stack.clear()
            self.update_undo_buttons()
            return
        if self._undo_pending is None:
            self._before = (self.last_state, self.cursor_offset())
        else:
            GLib.source_remove(self._undo_pending)
        self._undo_pending = GLib.timeout_add(600, self.commit)

    def commit(self):
        self._undo_pending = None
        before = getattr(self, "_before", None)
        cur = self.to_model()
        if before and before[0] != cur:
            self.undo_stack.append(before)
            del self.undo_stack[:-200]
            self.redo_stack.clear()
        self.last_state = cur
        self._before = None
        self.update_undo_buttons()
        return False

    def cursor_offset(self):
        return self.buf.get_iter_at_mark(self.buf.get_insert()).get_offset()

    def restore(self, state, offset):
        title = self.title.get_text()
        stacks = (self.undo_stack, self.redo_stack)
        self.load(state, title, self.page)
        self.undo_stack, self.redo_stack = stacks
        self.buf.place_cursor(self.buf.get_iter_at_offset(min(offset, self.buf.get_char_count())))
        self.view.scroll_mark_onscreen(self.buf.get_insert())
        self.update_undo_buttons()
        self.on_change()

    def undo(self):
        if self._undo_pending:
            GLib.source_remove(self._undo_pending)
            self.commit()
        if not self.undo_stack or not self.editable:
            return
        state, off = self.undo_stack.pop()
        self.redo_stack.append((self.last_state, self.cursor_offset()))
        self.restore(state, off)

    def redo(self):
        if not self.redo_stack or not self.editable:
            return
        state, off = self.redo_stack.pop()
        self.undo_stack.append((self.last_state, self.cursor_offset()))
        self.restore(state, off)

    def update_undo_buttons(self):
        self.tools["undo"].set_sensitive(bool(self.undo_stack) or self._undo_pending is not None)
        self.tools["redo"].set_sensitive(bool(self.redo_stack))
        if getattr(self, "flow_undo", None):
            self.flow_undo.set_sensitive(self.tools["undo"].get_sensitive())
            self.flow_redo.set_sensitive(bool(self.redo_stack))

    # ================= Zeichenformat =================
    def char_at_cursor(self):
        it = self.buf.get_iter_at_mark(self.buf.get_insert())
        if not it.starts_line():
            it.backward_char()        # wie in Word: das Zeichen vor dem Cursor zählt
        names = [n for n in self.names(it) if n in CHAR_PLAIN or n.startswith(CHAR_PREFIX)]
        a = {}
        for n in names:
            if n in CHAR_PLAIN:
                a[n] = True
            else:
                k, v = n.split(":", 1)
                a[{"font": "font", "size": "size", "fg": "fg", "hl": "hl", "link": "link"}[k]] = v
        return a

    def apply_char(self, key, value):
        """key: b/i/u/s/sup/sub (value bool) oder font/size/fg/hl/link (value str|None)."""
        if not self.editable:
            return
        bounds = self.buf.get_selection_bounds()
        prefix = {"font": "font:", "size": "size:", "fg": "fg:", "hl": "hl:", "link": "link:"}.get(key)
        if bounds:
            self.checkpoint()
            s, e = bounds
            if prefix:
                for t in self.all_tags((prefix,)):
                    self.buf.remove_tag(t, s, e)
                if value:
                    self.buf.apply_tag(self.tag(prefix + str(value)), s, e)
            else:
                partner = {"sup": "sub", "sub": "sup"}.get(key)
                if partner and value:
                    self.buf.remove_tag(self.tag(partner), s, e)
                (self.buf.apply_tag if value else self.buf.remove_tag)(self.tag(key), s, e)
            self.changed()
        if value:
            self.active[key] = value
            if key in ("sup", "sub"):
                self.active.pop("sub" if key == "sup" else "sup", None)
        else:
            self.active.pop(key, None)
        self.sync_tools()
        self.focus_text()

    def on_char_toggle(self, btn, key):
        if not self._sync:
            self.apply_char(key, btn.get_active())

    def toggle_char(self, key):
        self.apply_char(key, not self.active.get(key))

    def font_list(self):
        have = {f.get_name() for f in Gtk.Label().get_pango_context().list_families()}
        want = ["Noto Sans", "Noto Serif", "Roboto", "Roboto Condensed", "DejaVu Sans", "DejaVu Serif",
                "Liberation Sans", "Liberation Serif", "Carlito", "Caladea", "Adwaita Sans", "Anton",
                "Noto Sans Mono", "JetBrains Mono", "Space Mono"]
        return [f for f in want if f in have] or ["Sans"]

    def on_font_drop(self, drop, _):
        if self._sync:
            return
        i = drop.get_selected()
        if i >= len(self.fonts):
            def done(dlg, res):
                try:
                    fam = dlg.choose_family_finish(res)
                except GLib.Error:
                    fam = None
                if fam:
                    self.apply_char("font", fam.get_name())
                else:
                    self.sync_tools()
            Gtk.FontDialog(title="Schriftart wählen").choose_family(self.win, None, None, done)
            return
        fam = self.fonts[i]
        self.apply_char("font", None if fam == df.BASE_FONT else fam)

    def current_size(self):
        if self.active.get("size"):
            return float(self.active["size"])
        a = self.para_at(self.buf.get_iter_at_mark(self.buf.get_insert()).get_line())
        return df.STYLE_FMT.get(a["style"], (11,))[0]

    def on_size_spin(self, spin):
        if self._sync:
            return
        v = round(spin.get_value() * 2) / 2
        self.apply_char("size", f"{v:g}")

    def grow_font(self, d):
        cur = self.current_size()
        if d > 0:
            nxt = next((s for s in FONT_SIZES if s > cur), cur + 4)
        else:
            nxt = next((s for s in reversed(FONT_SIZES) if s < cur), max(6, cur - 1))
        self.apply_char("size", f"{nxt:g}")

    def set_color(self, kind, hexc):
        self.apply_char(kind, hexc)
        bar = self.fg_bar if kind == "fg" else self.hl_bar
        if hexc:
            bar.color = hexc
            bar.queue_draw()

    def pick_color(self, kind):
        def done(dlg, res):
            try:
                c = dlg.choose_rgba_finish(res)
            except GLib.Error:
                return
            self.set_color(kind, "#%02x%02x%02x" % (round(c.red * 255), round(c.green * 255), round(c.blue * 255)))
        Gtk.ColorDialog(title="Farbe wählen", with_alpha=False).choose_rgba(self.win, None, None, done)

    def clear_format(self):
        bounds = self.buf.get_selection_bounds()
        if bounds:
            self.checkpoint()
            s, e = bounds
            for t in self.all_tags(CHAR_PREFIX, CHAR_PLAIN):
                self.buf.remove_tag(t, s, e)
            self.changed()
        self.active = {}
        self.edit_paras(lambda a: a.update(style="normal", align="left", spacing=1.15))

    # ================= Absatzformat =================
    def on_style_drop(self, drop, _):
        if not self._sync:
            self.set_style(df.STYLES[drop.get_selected()])

    def set_style(self, style):
        self.edit_paras(lambda a: a.update(style=style, list=None if style in ("title", "h1", "h2", "h3") else a["list"]))
        self.focus_text()

    def on_align_toggle(self, btn, key):
        if self._sync:
            return
        self.edit_paras(lambda a: a.update(align=key))
        self.focus_text()

    def on_list_toggle(self, btn, kind):
        if self._sync:
            return
        on = btn.get_active()
        self.edit_paras(lambda a: a.update(list=kind if on else None,
                                           style="normal" if on and a["style"] in ("title", "h1", "h2", "h3") else a["style"]))
        self.focus_text()

    def toggle_list(self, kind):
        a = self.para_at(self.buf.get_iter_at_mark(self.buf.get_insert()).get_line())
        on = a["list"] != kind
        self.edit_paras(lambda x: x.update(list=kind if on else None))

    def change_indent(self, d):
        self.edit_paras(lambda a: a.update(indent=max(0, min(8, a["indent"] + d))))
        self.focus_text()

    def on_spacing(self, btn, v):
        if self._sync:
            return
        self.sp_pop.popdown()
        self.edit_paras(lambda a: a.update(spacing=v))
        self.focus_text()

    # ================= Einfügen =================
    def insert_date(self):
        self.buf.insert_at_cursor(datetime.date.today().strftime("%d.%m.%Y"))
        self.focus_text()

    def ensure_own_line(self):
        """Cursor auf eine eigene, leere Zeile bringen (für Tabellen, Linien, Seitenumbrüche)."""
        it = self.buf.get_iter_at_mark(self.buf.get_insert())
        if not it.starts_line():
            self.buf.insert(it, "\n")
            it = self.buf.get_iter_at_mark(self.buf.get_insert())
        if not it.ends_line():
            self.buf.insert(it, "\n")
            it = self.buf.get_iter_at_mark(self.buf.get_insert())
            it.backward_char()
        return it

    def insert_block(self, kind, rows=None, style=None):
        if not self.editable:
            return
        self.checkpoint()
        self._loading = True
        it = self.ensure_own_line()
        line = it.get_line()
        self.set_para(line, {"style": "normal", "align": "left", "list": None, "indent": 0, "spacing": 1.15})
        it = self.buf.get_iter_at_line(line)[1]
        self.insert_anchor({"t": kind, "rows": rows, "style": style}, it)
        it = self.buf.get_iter_at_line(line)[1]
        it.forward_char()
        if it.is_end():
            self.buf.insert(it, "\n")
            it = self.buf.get_end_iter()
        else:
            it.forward_char()
        self.buf.place_cursor(it)
        self._loading = False
        self.changed()
        self.focus_text()
        return line

    def insert_table(self, rows, cols):
        line = self.insert_block("table", [[""] * cols for _ in range(rows)])
        if line is not None:
            anchor = self.buf.get_iter_at_line(line)[1].get_child_anchor()
            w = self.blocks.get(anchor)
            if w:
                GLib.idle_add(lambda: w.cells[0][0].tv.grab_focus() and False)

    def anchor_iter(self, anchor):
        r = self.buf.get_iter_at_child_anchor(anchor)
        return r[1] if isinstance(r, tuple) else r

    def remove_block(self, w):
        # Erst ausblenden, dann (nach den Zeiger-Ereignissen) löschen: verschwindet der Block unter dem Zeiger
        # MITTEN im buf.delete, liest GTKs Crossing-Behandlung die Markierung des halb geänderten Puffers → Absturz
        # (Mülleimer der Tabelle).
        if hasattr(w, "drop_design"):
            w.drop_design()
        root = self.view.get_root()
        f = root.get_focus() if root else None
        if f is not None and (f is w or f.is_ancestor(w)):
            for anchor, x in self.blocks.items():
                if x is w:
                    self.buf.place_cursor(self.anchor_iter(anchor))
            self.view.grab_focus()
        w.set_visible(False)
        GLib.timeout_add(50, lambda: (self._remove_block(w), False)[1])

    def _remove_block(self, w):
        for anchor, x in list(self.blocks.items()):
            if x is w:
                self.checkpoint()
                self._quiet += 1
                it = self.anchor_iter(anchor)
                e = it.copy()
                e.forward_char()
                if e.get_char() == "\n" and w.kind != "fn":
                    e.forward_char()
                self.buf.delete(it, e)
                self.blocks.pop(anchor, None)
                self._quiet -= 1
                self.changed()
                self.focus_text()
                return

    def child_changed(self):
        if not self._loading:
            self.changed()

    def insert_image_data(self, data, mime=None, w=None, h=None, at=None, b64=None):
        try:
            iw, ih = df.image_size(data)
            w, h = w or iw, h or ih
            tw = self.geo["text_w"] / (self.zoom * self.geo["scale"])   # Breite in 100-%-Pixeln
            if w > tw:
                w, h = tw, h * tw / w
            tex = pixel_texture(data, w * self.zoom * self.geo["scale"], h * self.zoom * self.geo["scale"])
        except (GLib.Error, ZeroDivisionError):
            return False
        it = at or self.buf.get_iter_at_mark(self.buf.get_insert())
        self.images[tex] = {"img": b64 or base64.b64encode(data).decode(), "mime": mime or df.sniff_mime(data),
                            "w": round(w), "h": round(h)}
        self.buf.insert_paintable(it, tex)
        return True

    def pick_image(self, own_line=False):
        dlg = Gtk.FileDialog(title="Bild einfügen")
        f = Gtk.FileFilter()
        f.set_name("Bilder")
        f.add_mime_type("image/*")
        store = Gio.ListStore.new(Gtk.FileFilter)
        store.append(f)
        dlg.set_filters(store)

        def done(d, res):
            try:
                gf = d.open_finish(res)
            except GLib.Error:
                return
            self.insert_image_file(gf.get_path(), own_line=own_line)
        dlg.open(self.win, None, done)

    def insert_image_file(self, path, own_line=False):
        try:
            data = open(path, "rb").read()
        except OSError:
            return False
        self.checkpoint()
        self._quiet += 1
        if own_line:                       # aus dem Blockmenü: Bild in eine eigene Zeile, Cursor dahinter
            it = self.ensure_own_line()
            self.buf.place_cursor(it)
        ok = self.insert_image_data(data)
        if own_line and ok:
            it = self.buf.get_iter_at_mark(self.buf.get_insert())
            if not it.ends_line():
                self.buf.insert(it, "\n")
            else:
                it.forward_char()
                if it.is_end() and not it.starts_line():
                    self.buf.insert(it, "\n")
                self.buf.place_cursor(it)
        self._quiet -= 1
        self.changed()
        self.focus_text()
        return ok

    def image_near_cursor(self):
        b = self.buf.get_selection_bounds()
        cands = []
        if b:
            it = b[0].copy()
            while it.compare(b[1]) < 0:
                cands.append(it.copy())
                it.forward_char()
        else:
            it = self.buf.get_iter_at_mark(self.buf.get_insert())
            cands.append(it.copy())
            if not it.is_start():
                it.backward_char()
                cands.append(it)
        return [c for c in cands if c.get_paintable() in self.images]

    def resize_image(self, frac):
        hits = self.image_near_cursor()
        if not hits:
            return
        self.checkpoint()
        self._quiet += 1
        for it in reversed(hits):
            tex = it.get_paintable()
            info = self.images.pop(tex)
            data = base64.b64decode(info["img"])
            iw, ih = df.image_size(data)
            if frac is None:
                w, h = iw, ih
            else:
                tw = self.geo["text_w"] / (self.zoom * self.geo["scale"])
                w, h = tw * frac, tw * frac * ih / iw
            off = it.get_offset()
            e = it.copy()
            e.forward_char()
            names = self.names(it)
            self.buf.delete(it, e)
            pos = self.buf.get_iter_at_offset(off)
            self._loading = True
            self.insert_image_data(data, info["mime"], w, h, pos, b64=info["img"])
            s = self.buf.get_iter_at_offset(off)
            e = self.buf.get_iter_at_offset(off + 1)
            for n in names:
                self.buf.apply_tag(self.tag(n) if not n.startswith(("zoom",)) else self.zoom_tag, s, e)
            self._loading = False
        self._quiet -= 1
        self.changed()

    # ================= Markdown =================
    MD_INLINE = (("b", r"(\*\*|__)(?=\S)([^*_\n]+?)(?<=\S)\1$"),
                 ("s", r"(~~)(?=\S)([^~\n]+?)(?<=\S)~~$"),
                 ("code", r"(`)([^`\n]+)`$"),
                 ("i", r"(?<![*\w])(\*)(?=[^\s*])([^*\n]+?)(?<=\S)\*$"),
                 ("i", r"(?<![_\w])(_)(?=[^\s_])([^_\n]+?)(?<=\S)_$"))
    MD_LINE = ((r"^# $", {"style": "h1", "list": None}), (r"^## $", {"style": "h2", "list": None}),
               (r"^###+ $", {"style": "h3", "list": None}), (r"^> $", {"style": "quote", "list": None}),
               (r"^[-*+] $", {"list": "bullet"}), (r"^1[.)] $", {"list": "number"}))

    def md_live(self, line, ch):
        """Markdown-Kürzel beim Tippen: „# “ Überschrift, „- “ / „1. “ Liste, „> “ Zitat,
        **fett**, *kursiv*, ~~durch~~, `code`."""
        self._md_id = None
        buf = self.buf
        cur = buf.get_iter_at_mark(buf.get_insert())
        if cur.get_line() != line or buf.get_has_selection():
            return False
        ok, ls = buf.get_iter_at_line(line)
        before = buf.get_text(ls, cur, False)
        if ch == " ":
            for pat, attrs in self.MD_LINE:
                if re.match(pat, before):
                    a = self.para_at(line)
                    if attrs.get("list") and a.get("list") == attrs["list"]:
                        return False              # schon diese Liste („1. “ in einer Aufzählung wechselt die Art)
                    self.checkpoint()
                    self._loading = True
                    buf.delete(ls, cur)
                    self._loading = False
                    a.update(attrs)
                    self.set_para(line, a)
                    self.changed()
                    self.sync_tools()
                    return False
            return False
        for key, pat in self.MD_INLINE:
            m = re.search(pat, before)
            if not m:
                continue
            mk, inner = len(m.group(1)), len(m.group(2))
            start = ls.get_offset() + m.start()
            self.checkpoint()
            self._loading = True
            buf.delete(buf.get_iter_at_offset(start + mk + inner), buf.get_iter_at_offset(start + 2 * mk + inner))
            buf.delete(buf.get_iter_at_offset(start), buf.get_iter_at_offset(start + mk))
            self._loading = False
            a, b = buf.get_iter_at_offset(start), buf.get_iter_at_offset(start + inner)
            if key == "code":
                for t in self.all_tags(("font:",)):
                    buf.remove_tag(t, a, b)
                buf.apply_tag(self.tag("font:" + df.MONO_FONT), a, b)
            else:
                buf.apply_tag(self.tag(key), a, b)
            buf.place_cursor(b)
            self.active.pop("font" if key == "code" else key, None)    # danach normal weiterschreiben
            self.changed()
            self.sync_tools()
            return False
        return False

    def insert_blocks(self, blocks):
        """Blöcke (z. B. aus Markdown) an der Schreibmarke einfügen; ersetzt die Markierung."""
        buf = self.buf
        self.checkpoint()
        if buf.get_has_selection():
            buf.delete_selection(True, True)
        mark = buf.create_mark(None, buf.get_iter_at_mark(buf.get_insert()), False)
        start_off = buf.get_iter_at_mark(mark).get_offset()
        self._loading = True
        paras = []
        for i, b in enumerate(blocks):
            if i:
                buf.insert(buf.get_iter_at_mark(mark), "\n")
            line = buf.get_iter_at_mark(mark).get_line()
            if b["t"] == "p":
                for r in b["runs"]:
                    self.insert_run(r, buf.get_iter_at_mark(mark))
                paras.append((line, i, {k: b.get(k) for k in ("style", "align", "list", "indent", "spacing")}))
            else:
                self.insert_anchor(b, buf.get_iter_at_mark(mark))
        for line, i, a in paras:
            if i == 0 and (a.get("style") or "normal") == "normal" and not a.get("list"):
                continue                       # erster Absatz übernimmt das Format der Zielzeile
            cur = self.para_at(line)
            cur.update({k: v for k, v in a.items() if v is not None or k == "list"})
            self.set_para(line, cur)
        end = buf.get_iter_at_mark(mark)
        buf.apply_tag(self.zoom_tag, buf.get_iter_at_offset(start_off), end)
        buf.place_cursor(end)
        buf.delete_mark(mark)
        self._loading = False
        self._numbers = None
        self.changed()
        self.sync_tools()
        self.view.scroll_mark_onscreen(buf.get_insert())

    def on_paste(self, view):
        cb = self.view.get_clipboard()
        fmts = cb.get_formats()
        if fmts.contain_gtype(GObject.TYPE_STRING) and self.settings.get("markdown", True):
            view.stop_emission_by_name("paste-clipboard")

            def got_text(c, res):
                try:
                    text = c.read_text_finish(res)
                except GLib.Error:
                    return
                if not text:
                    return
                if md_detect(text):
                    self.insert_blocks(df.markdown_blocks(text))
                else:
                    if self.buf.get_has_selection():
                        self.buf.delete_selection(True, True)
                    self.buf.insert_interactive_at_cursor(text, -1, True)
                    self.view.scroll_mark_onscreen(self.buf.get_insert())
            cb.read_text_async(None, got_text)
            return
        if fmts.contain_gtype(Gdk.Texture) and not fmts.contain_mime_type("text/plain"):
            view.stop_emission_by_name("paste-clipboard")

            def got(c, res):
                try:
                    tex = c.read_texture_finish(res)
                except GLib.Error:
                    return
                if tex:
                    self.checkpoint()
                    self._quiet += 1
                    self.insert_image_data(tex.save_to_png_bytes().get_data(), "image/png")
                    self._quiet -= 1
                    self.changed()
            cb.read_texture_async(None, got)

    def on_drop(self, target, value, x, y):
        files = value.get_files()
        done = False
        for f in files:
            p = f.get_path()
            if p and os.path.splitext(p)[1].lower() in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"):
                done = self.insert_image_file(p) or done
            elif p and os.path.splitext(p)[1].lower() in df.IMPORT_TYPES:
                self.win.activate_action("win.doc-import-path", GLib.Variant("s", p))
                done = True
        return done

    # ================= Links =================
    def prepare_link(self):
        b = self.buf.get_selection_bounds()
        self.link_text.set_text(self.buf.get_text(*b, False) if b else "")
        self.link_url.set_text(self.active.get("link", ""))
        GLib.idle_add(lambda: self.link_url.grab_focus() and False)

    def apply_link(self, remove=False):
        self.link_pop.popdown()
        url = self.link_url.get_text().strip()
        if url and "://" not in url and not url.startswith("mailto:"):
            url = ("mailto:" + url) if "@" in url and "/" not in url else "https://" + url
        b = self.buf.get_selection_bounds()
        if remove or not url:
            if b:
                self.apply_char("link", None)
            else:
                self.extend_link_and(lambda s, e: self.apply_range_link(s, e, None))
            return
        if not b:
            text = self.link_text.get_text() or url
            self.checkpoint()
            it = self.buf.get_iter_at_mark(self.buf.get_insert())
            keep = dict(self.active)
            self.active["link"] = url
            self._quiet += 1
            self.buf.insert(it, text)
            self._quiet -= 1
            self.active = keep
            self.active.pop("link", None)
            self.changed()
        else:
            self.apply_char("link", url)
            self.active.pop("link", None)
        self.focus_text()

    def extend_link_and(self, fn):
        it = self.buf.get_iter_at_mark(self.buf.get_insert())
        t = next((t for t in it.get_tags() if t.props.name and t.props.name.startswith("link:")), None)
        if not t:
            return
        s, e = it.copy(), it.copy()
        if not s.starts_tag(t):
            s.backward_to_tag_toggle(t)
        e.forward_to_tag_toggle(t)
        fn(s, e)

    def apply_range_link(self, s, e, url):
        self.checkpoint()
        for t in self.all_tags(("link:",)):
            self.buf.remove_tag(t, s, e)
        if url:
            self.buf.apply_tag(self.tag("link:" + url), s, e)
        self.changed()

    # ================= Bild anklicken =================
    def image_at(self, x, y):
        """Iter auf dem Bild unter (x, y) in View-Koordinaten oder None."""
        bx, by = self.view.window_to_buffer_coords(Gtk.TextWindowType.WIDGET, int(x), int(y))
        ok, it, _tr = self.view.get_iter_at_position(bx, by)
        if not ok:
            return None
        for cand in (it, it.copy()):
            if cand is not it and not cand.backward_char():
                continue
            if cand.get_paintable() in self.images:
                r = self.view.get_iter_location(cand)
                if r.x - 2 <= bx <= r.x + r.width + 2 and r.y - 2 <= by <= r.y + r.height + 2:
                    return cand
        return None

    def build_image_pop(self):
        pop = Gtk.Popover(has_arrow=False, autohide=True)
        pop.add_css_class("wpop")
        pop.add_css_class("bubble")
        pop.add_css_class("imgpop")
        pop.set_position(Gtk.PositionType.TOP)
        box = Gtk.Box(spacing=1)

        def btn(label, tip, cb):
            b = Gtk.Button(label=label, tooltip_text=tip, focus_on_click=False)
            b.connect("clicked", lambda *_: cb())
            box.append(b)
            return b

        def sep():
            x = Gtk.Box()
            x.add_css_class("bsep")
            box.append(x)
        for pct in (25, 50, 75, 100):
            btn(f"{pct} %", f"{pct} % der Textbreite", lambda p=pct: self.image_action("size", p / 100))
        btn("1:1", "Originalgröße", lambda: self.image_action("size", None))
        sep()
        for key, icon, tip in (("left", "󰉢", "Links"), ("center", "󰉠", "Mittig"), ("right", "󰉣", "Rechts")):
            btn(icon, f"Bild {tip.lower()} ausrichten", lambda k=key: self.image_action("align", k))
        sep()
        btn("󰋩", "Anderes Bild wählen …", lambda: self.image_action("replace"))
        btn("󰆏", "Bild kopieren", lambda: self.image_action("copy"))
        btn("󰆴", "Bild entfernen", lambda: self.image_action("delete"))
        pop.set_child(box)
        pop.set_parent(self.view)
        pop.connect("closed", lambda *_: setattr(self, "_img_off", None))
        self.img_pop = pop

    def show_image_pop(self, it):
        if not getattr(self, "img_pop", None):
            self.build_image_pop()
        e = it.copy()
        e.forward_char()
        self.buf.select_range(it, e)            # Bild sichtbar markiert, Größe/Löschen wirken darauf
        self._img_off = it.get_offset()
        r = self.view.get_iter_location(it)
        x, y = self.view.buffer_to_window_coords(Gtk.TextWindowType.WIDGET, r.x, r.y)
        self.img_pop.set_pointing_to(_rect(x, y, max(1, r.width), max(1, r.height)))
        self.img_pop.popup()

    def image_action(self, what, arg=None):
        off = getattr(self, "_img_off", None)
        if off is None:
            return
        it = self.buf.get_iter_at_offset(off)
        tex = it.get_paintable()
        if tex not in self.images:
            self.img_pop.popdown()
            return
        e = it.copy()
        e.forward_char()
        if what == "size":
            self.buf.select_range(it, e)
            self.resize_image(arg)
            self.img_pop.popdown()
        elif what == "align":
            self.buf.place_cursor(it)
            self.edit_paras(lambda a: a.update(align=arg))
            self.img_pop.popdown()
        elif what == "delete":
            self.img_pop.popdown()
            self.checkpoint()
            self._quiet += 1
            self.buf.delete(it, e)
            self.images.pop(tex, None)
            self._quiet -= 1
            self.changed()
            self.focus_text()
        elif what == "copy":
            data = base64.b64decode(self.images[tex]["img"])
            self.view.get_clipboard().set_content(Gdk.ContentProvider.new_for_bytes(
                self.images[tex].get("mime") or "image/png", GLib.Bytes.new(data)))
            self.img_pop.popdown()
        elif what == "replace":
            self.img_pop.popdown()
            dlg = Gtk.FileDialog(title="Anderes Bild wählen")

            def done(d, res):
                try:
                    path = d.open_finish(res).get_path()
                    data = open(path, "rb").read()
                except (GLib.Error, OSError, AttributeError):
                    return
                cur = self.buf.get_iter_at_offset(off)
                if cur.get_paintable() not in self.images:
                    return
                old = self.images[cur.get_paintable()]
                self.checkpoint()
                self._quiet += 1
                nx = cur.copy()
                nx.forward_char()
                self.images.pop(cur.get_paintable(), None)
                self.buf.delete(cur, nx)
                pos = self.buf.get_iter_at_offset(off)
                try:
                    iw, ih = df.image_size(data)
                    w = old["w"]
                    self.insert_image_data(data, w=w, h=w * ih / max(1, iw), at=pos)
                except Exception:  # noqa: BLE001
                    self.insert_image_data(data, at=pos)
                self._quiet -= 1
                self.changed()
            dlg.open(self.win, None, done)

    def on_click(self, gesture, n, x, y):
        state = gesture.get_current_event_state()
        if n == 1 and not state & (Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SHIFT_MASK) and self.editable:
            it = self.image_at(x, y)
            if it is not None and not self.buf.get_has_selection() or it is not None and \
                    self.buf.get_selection_bounds()[1].get_offset() - self.buf.get_selection_bounds()[0].get_offset() <= 1:
                GLib.idle_add(lambda: (self.show_image_pop(self.image_at(x, y) or it), False)[1])
                return
        if not state & Gdk.ModifierType.CONTROL_MASK:
            return
        bx, by = self.view.window_to_buffer_coords(Gtk.TextWindowType.WIDGET, int(x), int(y))
        ok, it = self.view.get_iter_at_location(bx, by)
        if not ok:
            return
        t = next((t for t in it.get_tags() if t.props.name and t.props.name.startswith("link:")), None)
        if t:
            Gtk.UriLauncher.new(t.props.name[5:]).launch(self.win, None, None)

    # ================= Suchen & Ersetzen =================
    def show_find(self, replace=False):
        self.findrev.set_reveal_child(True)
        b = self.buf.get_selection_bounds()
        if b and b[0].get_line() == b[1].get_line():
            self.find_entry.set_text(self.buf.get_text(*b, False))
        (self.repl_entry if replace and self.find_entry.get_text() else self.find_entry).grab_focus()
        self.run_search()

    def toggle_find(self):
        """Strg+F: Suchleiste öffnen bzw. – wenn sie schon offen ist – schließen."""
        self.hide_find() if self.findrev.get_reveal_child() else self.show_find()

    def hide_find(self):
        self.findrev.set_reveal_child(False)
        self.buf.remove_tag(self.search_tag, self.buf.get_start_iter(), self.buf.get_end_iter())
        self.search_hits = []
        self.focus_text()

    def run_search(self):
        self.buf.remove_tag(self.search_tag, self.buf.get_start_iter(), self.buf.get_end_iter())
        self.search_hits = []
        q = self.find_entry.get_text()
        if not q:
            self.find_info.set_label("")
            return
        flags = Gtk.TextSearchFlags.TEXT_ONLY | Gtk.TextSearchFlags.VISIBLE_ONLY
        if not self.case_btn.get_active():
            flags |= Gtk.TextSearchFlags.CASE_INSENSITIVE
        it = self.buf.get_start_iter()
        while True:
            m = it.forward_search(q, flags, None)
            if not m:
                break
            s, e = m
            self.buf.apply_tag(self.search_tag, s, e)
            self.search_hits.append((s.get_offset(), e.get_offset()))
            it = e
            if len(self.search_hits) > 5000:
                break
        self.find_info.set_label(f"{len(self.search_hits)} Treffer" if self.search_hits else "keine Treffer")

    def find_step(self, d):
        if not self.search_hits:
            self.run_search()
        if not self.search_hits:
            return
        cur = self.cursor_offset()
        b = self.buf.get_selection_bounds()
        if d > 0:
            pos = b[1].get_offset() if b else cur
            hit = next((h for h in self.search_hits if h[0] >= pos), self.search_hits[0])
        else:
            pos = b[0].get_offset() if b else cur
            hit = next((h for h in reversed(self.search_hits) if h[1] <= pos), self.search_hits[-1])
        s, e = self.buf.get_iter_at_offset(hit[0]), self.buf.get_iter_at_offset(hit[1])
        self.buf.select_range(s, e)
        self.view.scroll_to_iter(s, 0.2, False, 0, 0)
        idx = self.search_hits.index(hit) + 1
        self.find_info.set_label(f"{idx} von {len(self.search_hits)}")

    def replace_one(self):
        q = self.find_entry.get_text()
        b = self.buf.get_selection_bounds()
        if b and q and (self.buf.get_text(*b, False) == q or (not self.case_btn.get_active() and
                                                               self.buf.get_text(*b, False).lower() == q.lower())):
            self.checkpoint()
            self._quiet += 1
            s, e = b
            off = s.get_offset()
            self.buf.delete(s, e)
            self.buf.insert(self.buf.get_iter_at_offset(off), self.repl_entry.get_text())
            self._quiet -= 1
            self.changed()
            self.buf.place_cursor(self.buf.get_iter_at_offset(off + len(self.repl_entry.get_text())))
        self.run_search()
        self.find_step(1)

    def replace_all(self):
        self.run_search()
        if not self.search_hits:
            return
        self.checkpoint()
        self._quiet += 1
        rep = self.repl_entry.get_text()
        n = len(self.search_hits)
        for s, e in reversed(self.search_hits):
            si, ei = self.buf.get_iter_at_offset(s), self.buf.get_iter_at_offset(e)
            # Format des ersten ersetzten Zeichens behalten
            keep = self.char_props(self.names(si))
            self.buf.delete(si, ei)
            act = self.active
            self.active = {("fg" if k == "color" else "sup" if v == "sup" else "sub" if v == "sub" else k):
                           (True if k in ("b", "i", "u", "s", "va") else (f"{v:g}" if k == "size" else v))
                           for k, v in keep.items()}
            self.buf.insert(self.buf.get_iter_at_offset(s), rep)
            self.active = act
        self._quiet -= 1
        self.changed()
        self.run_search()
        self.find_info.set_label(f"{n} ersetzt")

    def on_find_key(self, ctrl, keyval, code, state):
        if keyval == Gdk.KEY_Escape:
            self.hide_find()
            return True
        if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter) and state & Gdk.ModifierType.SHIFT_MASK:
            self.find_step(-1)
            return True
        return False

    # ================= Tastatur =================
    def on_title_key(self, ctrl, keyval, code, state):
        if keyval in (Gdk.KEY_Tab, Gdk.KEY_Down) and not state & (Gdk.ModifierType.SHIFT_MASK | Gdk.ModifierType.CONTROL_MASK):
            self.focus_text()
            return True
        return False

    def on_key(self, ctrl, keyval, code, state):
        if keyval == Gdk.KEY_F1 and state & Gdk.ModifierType.CONTROL_MASK:
            self.toggle_ribbon()
            return True
        if self.win.get_focus() is not self.view:
            return False
        if self.flow and self.flowx.on_key(keyval, state):
            return True
        if keyval in (Gdk.KEY_f, Gdk.KEY_F) and state & Gdk.ModifierType.CONTROL_MASK and state & Gdk.ModifierType.ALT_MASK:
            self.insert_footnote()
            return True
        ctrl_on = bool(state & Gdk.ModifierType.CONTROL_MASK)
        shift = bool(state & Gdk.ModifierType.SHIFT_MASK)
        alt = bool(state & Gdk.ModifierType.ALT_MASK)
        k = Gdk.keyval_to_lower(keyval)
        if ctrl_on and not alt:
            acts = {
                Gdk.KEY_z: (self.redo if shift else self.undo), Gdk.KEY_y: self.redo,
                Gdk.KEY_b: lambda: self.toggle_char("b"), Gdk.KEY_i: lambda: self.toggle_char("i"),
                Gdk.KEY_u: lambda: self.toggle_char("u"), Gdk.KEY_d: lambda: self.toggle_char("s"),
                Gdk.KEY_numbersign: lambda: self.toggle_char("sub"),
                Gdk.KEY_e: lambda: self.edit_paras(lambda a: a.update(align="center")),
                Gdk.KEY_r: lambda: self.edit_paras(lambda a: a.update(align="right")),
                Gdk.KEY_j: lambda: self.edit_paras(lambda a: a.update(align="justify")),
                Gdk.KEY_k: lambda: self.open_link(),
                Gdk.KEY_f: self.toggle_find, Gdk.KEY_h: lambda: self.show_find(True),
                Gdk.KEY_space: self.clear_format,
                Gdk.KEY_plus: (lambda: self.toggle_char("sup")) if shift else (lambda: self.step_zoom(1)),
                Gdk.KEY_KP_Add: lambda: self.step_zoom(1), Gdk.KEY_minus: lambda: self.step_zoom(-1),
                Gdk.KEY_KP_Subtract: lambda: self.step_zoom(-1), Gdk.KEY_KP_0: lambda: self.set_zoom(1.0),
                Gdk.KEY_asterisk: lambda: self.toggle_char("sup"),
                Gdk.KEY_greater: lambda: self.grow_font(1), Gdk.KEY_less: lambda: self.grow_font(-1),
                Gdk.KEY_0: lambda: self.set_style("normal"), Gdk.KEY_1: lambda: self.set_style("h1"),
                Gdk.KEY_2: lambda: self.set_style("h2"), Gdk.KEY_3: lambda: self.set_style("h3"),
                Gdk.KEY_Return: lambda: self.insert_block("pb"), Gdk.KEY_KP_Enter: lambda: self.insert_block("pb"),
            }
            if k == Gdk.KEY_l:
                (self.toggle_list("bullet") if shift else self.edit_paras(lambda a: a.update(align="left")))
                return True
            if k == Gdk.KEY_n and shift:
                self.toggle_list("number")
                return True
            if keyval in acts or k in acts:
                (acts.get(keyval) or acts[k])()
                return True
            return False
        if not self.editable:
            return False
        it = self.buf.get_iter_at_mark(self.buf.get_insert())
        line = it.get_line()
        a = self.para_at(line)
        if keyval in (Gdk.KEY_Tab, Gdk.KEY_ISO_Left_Tab) and a["list"] and not self.buf.get_has_selection():
            self.change_indent(-1 if (shift or keyval == Gdk.KEY_ISO_Left_Tab) else 1)
            return True
        if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter) and a["list"] and not shift:
            s, e = self.line_bounds(line)
            if not self.buf.get_text(s, e, True).strip("\n"):
                self.edit_paras(lambda x: x.update(list=None, indent=0))   # leerer Listenpunkt beendet die Liste
                return True
        if keyval == Gdk.KEY_BackSpace and it.starts_line() and not self.buf.get_has_selection():
            if a["list"]:
                self.edit_paras(lambda x: x.update(list=None))
                return True
            if a["indent"]:
                self.change_indent(-1)
                return True
            if a["style"] != "normal" and it.ends_line():
                self.set_style("normal")
                return True
        return False

    def on_scroll(self, ctrl, dx, dy):
        if ctrl.get_current_event_state() & Gdk.ModifierType.CONTROL_MASK:
            self.step_zoom(-1 if dy > 0 else 1)
            return True
        return False

    def focus_text(self):
        self.view.grab_focus()

    # ================= Zustand der Werkzeugleiste =================
    def on_mark_set(self, buf, it, mark):
        if mark.get_name() in ("insert", "selection_bound") and not self._loading:
            self.active = self.char_at_cursor()
            self.sync_tools()
            if not getattr(self, "_count_id", None):        # Zählung live auch für die Markierung
                self._count_id = GLib.timeout_add(60, self._count_tick)

    def _count_tick(self):
        self._count_id = None
        self.update_counts()
        return False

    def selection_counts(self):
        """(wörter, zeichen) der Markierung oder None."""
        b = self.buf.get_selection_bounds()
        if not b:
            return None
        t = self.buf.get_text(b[0], b[1], False).replace("\ufffc", "")
        return len(t.split()), len(t)

    def on_buffer_changed(self, buf):
        if not self._loading and not self._quiet:
            self._numbers = None
            self.changed()
        self.queue_nav()

    def sync_tools(self):
        self._sync = True
        line = self.buf.get_iter_at_mark(self.buf.get_insert()).get_line()
        a = self.para_at(line)
        for k in CHAR_PLAIN:
            self.tools[k].set_active(bool(self.active.get(k)))
        self.style_drop.set_selected(df.STYLES.index(a["style"]) if a["style"] in df.STYLES else 0)
        fam = self.active.get("font") or df.BASE_FONT
        if fam not in self.fonts:
            self.fonts.append(fam)
            self.font_drop.set_model(Gtk.StringList.new(self.fonts + ["Andere …"]))
        self.font_drop.set_selected(self.fonts.index(fam))
        self.size_spin.set_value(self.current_size())
        for k in ("left", "center", "right", "justify"):
            self.tools["a:" + k].set_active(a["align"] == k)
        self.tools["bullet"].set_active(a["list"] == "bullet")
        self.tools["number"].set_active(a["list"] == "number")
        for v, b in self.spacing_btns.items():
            b.set_active(abs(v - a["spacing"]) < 0.01)
        for v, b in self.spacing_chips.items():
            b.set_active(abs(v - a["spacing"]) < 0.01)
        for k, b in self.style_chips.items():
            b.set_active(a["style"] == k)
        self._sync = False
        self.sync_flowbar()

    def set_editable(self, on):
        self.editable = on
        self.view.set_editable(on)
        self.view.set_cursor_visible(on)
        self.title.set_editable(on)
        for w in self.tools.values():
            if w is not self.tools.get("paper") and w is not self.tools.get("find"):
                w.set_sensitive(on)
        for w in (self.style_drop, self.font_drop, self.size_spin, self.fg_btn, self.hl_btn, self.link_btn):
            w.set_sensitive(on)
        for w in self.blocks.values():
            w.set_sensitive(on)

    # ================= Ansicht =================
    def update_geometry(self):
        width = self.view.get_width()
        if width <= 0:
            return False
        if self.flow:
            g = self.flowx.geometry(width)
            self.geo = g
            self.view.set_left_margin(round(g["side"]))
            self.view.set_right_margin(round(g["side"]))
            self.view.set_top_margin(18)
            self.view.set_bottom_margin(round(60 + self.extra_bottom))
            for units, tg in self.margin_tags.items():
                self.size_margin_tag(units, tg)
            for w in self.blocks.values():
                w.set_width(g["text_w"] - 4)
            self.invalidate()
            return False
        w_mm, h_mm, (t, r, b, l) = df.page_mm(self.page)
        px = 96 / 25.4
        pw, ph = w_mm * px, h_mm * px
        page_w = min(pw * self.zoom, width - 2 * 16)
        scale = page_w / (pw * self.zoom)
        k = self.zoom * scale
        side = max(16, (width - page_w) / 2)
        g = dict(side=side, page_w=page_w, page_h=ph * k, scale=scale, k=k, mt=t * px * k, mr=r * px * k,
                 mb=b * px * k, ml=l * px * k, gap=PAGE_GAP)
        g["m"] = g["ml"]
        g["text_w"] = page_w - g["ml"] - g["mr"]
        g["body_h"] = g["page_h"] - g["mt"] - g["mb"]
        self.geo = g
        self.view.set_left_margin(round(side + g["ml"]))
        self.view.set_right_margin(round(side + g["mr"]))
        self.view.set_top_margin(round(DESK + g["mt"]))
        self.view.set_bottom_margin(round(DESK + g["mb"] + self.extra_bottom))
        for units, tg in self.margin_tags.items():
            self.size_margin_tag(units, tg)
        for w in self.blocks.values():
            w.set_width(g["text_w"] - 4)
        self.invalidate()
        return False

    def invalidate(self):
        """Seiten neu berechnen, sobald GTK das Layout fertig hat."""
        self._numbers = None
        if self._pages_id is None:
            self._pages_id = GLib.timeout_add(120, self.compute_pages)
        self.view.queue_draw()

    def content_start(self, i):
        g = self.geo
        return i * (g["page_h"] + g["gap"])

    def page_tag(self, px):
        px = max(0, int(round(px)))
        name = f"pg:{px}"
        t = self.buf.get_tag_table().lookup(name)
        if not t:
            t = self.buf.create_tag(name, pixels_above_lines=px)
        return t

    def compute_pages(self):
        """Echte Seiten: Absätze, die nicht mehr auf die Seite passen, rutschen auf die nächste. Dafür bekommt der
        erste Absatz einer Seite einen Abstand nach oben (Tag pg:<px>). GTK misst Zeilen erst nach und nach im
        Hintergrund – deshalb wird gerechnet, sobald die Höhen stabil sind, und nur Geänderte werden neu gesetzt."""
        self._pages_id = None
        g = self.geo
        if self.flow:                           # fließend: keine Seiten
            self.pages = [0.0]
            self.update_counts()
            self.update_toc_blocks()
            return False
        if "body_h" not in g or self.view.get_width() <= 0:
            return False
        buf, view = self.buf, self.view
        n_lines = buf.get_line_count()
        lines = []
        for line in range(n_lines):
            ok, it = buf.get_iter_at_line(line)
            y, h = view.get_line_yrange(it)
            cur = next((int(t.props.name[3:]) for t in it.get_tags() if t.props.name and t.props.name.startswith("pg:")), None)
            style = next((t.props.name[3:] for t in it.get_tags() if t.props.name and t.props.name.startswith("ps:")), "normal")
            lines.append((it, h, cur, STYLE_TAG.get(style, {}).get("pixels_above_lines", 0), style))
        total = sum(x[1] for x in lines)
        if self._verify_id:
            GLib.source_remove(self._verify_id)
            self._verify_id = None
        if total != self._measured and self._settle < 15:      # noch nicht fertig gemessen: gleich nochmal
            self._measured = total
            self._settle += 1
            self._pages_id = GLib.timeout_add(150, self.compute_pages)
            return False
        self._settle = 0
        forced = set()
        for anchor, w in self.blocks.items():
            if w.kind == "pb" and not anchor.get_deleted():
                forced.add(self.anchor_iter(anchor).get_line() + 1)
        starts, p, y = [0.0], 0, 0.0
        want = {}
        prev = None                     # (zeile, y, höhe, abstand, stil, seite) der vorigen Zeile
        page_of = []
        for line, (it, h, cur, above, style) in enumerate(lines):
            nat = h - ((cur - above) if cur is not None else 0)       # Höhe ohne unseren Seiten-Abstand
            end = self.content_start(p) + g["body_h"]
            if line in forced or (y + nat > end + 0.5 and y > self.content_start(p) + 1 and nat <= g["body_h"] + above):
                p += 1
                starts.append(self.content_start(p))
                if line not in forced and prev and prev[4] in ("h1", "h2", "h3") and prev[5] == p - 1 \
                        and prev[1] > self.content_start(p - 1) + 1 and prev[0] not in want:
                    # Überschrift nicht allein unten stehen lassen: sie wandert mit auf die neue Seite
                    pl, py, pnat, pabove = prev[0], prev[1], prev[2], prev[3]
                    want[pl] = max(0, round(self.content_start(p) - py))
                    if page_of:
                        page_of[-1] = p
                    y = py + pnat - pabove + want[pl]
                    prev = (pl, py, pnat, pabove, prev[4], p)
                    end = self.content_start(p) + g["body_h"]
                    prev = (line, y, nat, above, style, p)
                    page_of.append(p)
                    y += nat
                    continue
                px = max(0, round(self.content_start(p) - y))
                want[line] = px
                prev = (line, y, nat, above, style, p)
                page_of.append(p)
                y = y + nat - above + px
            else:
                prev = (line, y, nat, above, style, p)
                page_of.append(p)
                y += nat
            while y > self.content_start(p) + g["body_h"] + g["mb"] + 1:   # übergroßer Absatz über mehrere Seiten
                p += 1
                starts.append(self.content_start(p))
        changed = False
        for line, (it, h, cur, above, style) in enumerate(lines):
            if want.get(line) == cur:
                continue
            ok, s_ = buf.get_iter_at_line(line)
            e_ = s_.copy()
            if not e_.ends_line():
                e_.forward_to_line_end()
            if e_.equal(s_):
                e_.forward_char()
            if cur is not None:
                buf.remove_tag(self.page_tag(cur), s_, e_)
            if line in want:
                buf.apply_tag(self.page_tag(want[line]), s_, e_)
            changed = True
        if changed:
            self._measured = None
        self.pages = starts
        self.line_page = page_of
        last_end = self.content_start(len(starts) - 1) + g["body_h"]
        self.view.set_bottom_margin(round(max(0, last_end - y) + g["mb"] + DESK + self.extra_bottom))
        self.update_counts()
        self.update_toc_blocks()
        view.queue_draw()
        # Nachkontrolle: wächst danach noch etwas (Inhaltsverzeichnis, Bild, Tabelle), neu umbrechen
        self._expect = y
        self._verify_id = GLib.timeout_add(400, self.verify_pages)
        return False

    def verify_pages(self):
        self._verify_id = None
        n = self.buf.get_line_count()
        total = sum(self.view.get_line_yrange(self.buf.get_iter_at_line(l)[1])[1] for l in range(n))
        if abs(total - self._expect) > 2 and self._verify_n < 6:
            self._verify_n += 1
            self.invalidate()
        else:
            self._verify_n = 0
        return False

    def update_toc_blocks(self):
        """Inhaltsverzeichnisse und Fußnotennummern auf den aktuellen Stand bringen."""
        fns = sorted(((self.anchor_iter(a).get_offset(), w) for a, w in self.blocks.items()
                      if w.kind == "fn" and not a.get_deleted()), key=lambda x: x[0])
        for i, (_, w) in enumerate(fns, start=1):
            w.set_number(i)
        tocs = [w for a, w in self.blocks.items() if w.kind == "toc" and not a.get_deleted()]
        if not tocs:
            return
        import bisect
        entries = []
        for line in range(self.buf.get_line_count()):
            ok, it = self.buf.get_iter_at_line(line)
            style = next((x[3:] for x in self.names(it) if x.startswith("ps:")), "normal")
            if style not in ("h1", "h2", "h3"):
                continue
            s, e = self.line_bounds(line)
            text = self.buf.get_text(s, e, False).strip()
            if not text:
                continue
            lp = getattr(self, "line_page", [])
            page = (lp[line] + 1) if line < len(lp) else max(1, bisect.bisect_right(self.pages, self.view.get_iter_location(it).y + 1))
            entries.append((int(style[1]), text, line, page))
        for w in tocs:
            w.refresh(entries)

    def insert_footnote(self):
        if not self.editable:
            return
        self.checkpoint()
        it = self.buf.get_iter_at_mark(self.buf.get_insert())
        anchor = self.insert_anchor({"t": "fn", "text": ""}, it)
        self.changed()
        self.update_toc_blocks()
        w = self.blocks[anchor]
        GLib.idle_add(lambda: w.popup() and False)

    def draw_paper(self, snap):
        if self.flow:
            return
        g = self.geo
        if "body_h" not in g:
            return
        n = max(1, len(self.pages))
        paper = rgba("#fbfaf6") if self.light else self.paper_color
        vis = self.view.get_visible_rect()
        _, top_y = self.view.window_to_buffer_coords(Gtk.TextWindowType.WIDGET, 0, 0)
        lo, hi = top_y - g["page_h"], top_y + self.view.get_height() + g["page_h"]
        dim = rgba("#000000", 0.45) if self.light else rgba(self.fg_hex, 0.5)
        for i in range(n):
            y0 = self.content_start(i) - g["mt"]
            if y0 > hi or y0 + g["page_h"] < lo:
                continue
            for d, a in ((6, 0.05), (4, 0.07), (2, 0.1)):   # weicher Schatten aus Rechtecken (klappt mit jedem Renderer)
                snap.append_color(rgba("#000000", a), Graphene.Rect().init(g["side"] - d, y0 - d + 2, g["page_w"] + 2 * d,
                                                                           g["page_h"] + 2 * d))
            snap.append_color(paper, Graphene.Rect().init(g["side"], y0, g["page_w"], g["page_h"]))
            self.draw_decor(snap, i, n, y0, dim)

    def decor_texts(self, i, n):
        """(kopf, fuß, nummer, nummer_position) für Seite i (0-basiert)."""
        p = self.page
        head = df.fill_fields(p.get("header", ""), i + 1, n, self.title.get_text())
        foot = df.fill_fields(p.get("footer", ""), i + 1, n, self.title.get_text())
        num = ""
        if p.get("numbers", "none") != "none" and i + 1 >= int(p.get("num_from", 1)):
            num = df.page_number_text(p, i + 1, n)
        return head, foot, num, p.get("numbers", "none")

    def draw_decor(self, snap, i, n, y0, color):
        g = self.geo
        head, foot, num, pos = self.decor_texts(i, n)
        size = max(5.0, 9 * g["k"])
        x_l, x_r = g["side"] + g["ml"], g["side"] + g["page_w"] - g["mr"]

        def put(text, y_mid, align):
            if not text:
                return
            lay = self.view.create_pango_layout(text)
            lay.set_font_description(Pango.FontDescription.from_string(f"{df.BASE_FONT} {size:.1f}"))
            w, h = lay.get_pixel_size()
            x = {"left": x_l, "center": (x_l + x_r - w) / 2, "right": x_r - w}[align]
            snap.save()
            snap.translate(Graphene.Point().init(x, y_mid - h / 2))
            snap.append_layout(lay, color)
            snap.restore()
        y_head = y0 + g["mt"] / 2
        y_foot = y0 + g["page_h"] - g["mb"] / 2
        put(head, y_head, "left")
        put(foot, y_foot, "left")
        if num:
            put(num, y_head if pos == "header-right" else y_foot,
                {"footer-center": "center", "footer-left": "left"}.get(pos, "right"))

    def list_numbers(self):
        if self._numbers is None:
            blocks = []
            for line in range(self.buf.get_line_count()):
                a = self.para_at(line)
                blocks.append({"t": "p", **a})
            self._numbers = df.list_numbers(blocks)
        return self._numbers

    def draw_markers(self, snap):
        """Aufzählungszeichen und Nummern vor Listenabsätzen (+ Hinweise der Ansicht „fließend“)."""
        if self.flow:
            self.flowx.draw(snap)
        tags = [self.buf.get_tag_table().lookup("pl:bullet"), self.buf.get_tag_table().lookup("pl:number")]
        nums = None
        color = rgba("#1d1d1d") if (self.light and not self.flow) else rgba(self.fg_hex)
        for tag in tags:
            it = self.buf.get_start_iter()
            while True:
                if not it.has_tag(tag) and not it.forward_to_tag_toggle(tag):
                    break
                if not it.has_tag(tag):
                    break
                # jede Zeile innerhalb dieses Abschnitts
                end = it.copy()
                end.forward_to_tag_toggle(tag)
                ln = it.get_line()
                last = end.get_line() - (1 if end.starts_line() and end.get_line() > ln else 0)
                for line in range(ln, last + 1):
                    a = self.para_at(line)
                    if a["list"] != tag.props.name[3:]:
                        continue
                    ok, li = self.buf.get_iter_at_line(line)
                    rect = self.view.get_iter_location(li)
                    if a["list"] == "bullet":
                        txt = "•◦▪"[a["indent"] % 3]
                    else:
                        if nums is None:
                            nums = self.list_numbers()
                        txt = f"{nums.get(line, 1)}."
                    lay = self.view.create_pango_layout(txt)
                    size = df.STYLE_FMT.get(a["style"], (11,))[0]
                    names = self.names(li)
                    sz = next((float(n[5:]) for n in names if n.startswith("size:")), size)
                    fd = Pango.FontDescription.from_string(f"Noto Sans {sz * self.zoom:.1f}")
                    lay.set_font_description(fd)
                    ink, logical = lay.get_pixel_extents()
                    _, line_h = self.view.get_line_yrange(li)
                    x = rect.x - STEP * self.zoom * self.geo["scale"] + 2
                    if a["list"] == "number":
                        x = rect.x - logical.width - 6 * self.zoom
                    # Grundlinie: oberste Zeile des Absatzes, Schriftbaseline schätzen
                    y = rect.y + max(0, rect.height - logical.height) / 2
                    snap.save()
                    snap.translate(Graphene.Point().init(x, y))
                    snap.append_layout(lay, color)
                    snap.restore()
                it = end
                if it.is_end():
                    break

    def apply_paper(self):
        light = self.light and not self.flow          # fließend: immer in den App-Farben
        (self.view.add_css_class if light else self.view.remove_css_class)("light")
        (self.scroll.add_css_class if light else self.scroll.remove_css_class)("light")
        self.refresh_colors()

    def refresh_colors(self):
        """Theme-Farben für die selbstgezeichnete Seite (bei dunklem Papier)."""
        ctx = self.view.get_style_context()
        ok, c = ctx.lookup_color("surface_container")
        self.paper_color = c if ok else rgba("#271e19")
        ok, f = ctx.lookup_color("foreground")
        self.fg_hex = f.to_string() if ok else "#f0dfd7"
        self.quote_fg.props.foreground_rgba = rgba("#555555") if self.light else rgba(self.fg_hex, 0.7)
        self.view.queue_draw()

    def on_paper_toggle(self, btn):
        self.light = btn.get_active()
        self.settings["light_paper"] = self.light
        self.apply_paper()
        self.focus_text()

    def set_zoom(self, z):
        z = max(0.3, min(3.0, z))
        if abs(z - self.zoom) < 0.001:
            return
        self.zoom = z
        self.settings["zoom"] = z
        self.zoom_tag.props.scale = z
        self.update_rise()
        self.zoom_btn.set_label(f"{round(z * 100)} %")
        self._sync = True
        self.zoom_scale.set_value(z)
        self._sync = False
        self.update_geometry()
        self.rescale_images()

    def step_zoom(self, d):
        cur = self.zoom
        if d > 0:
            self.set_zoom(next((z for z in ZOOMS if z > cur + 0.001), cur * 1.1))
        else:
            self.set_zoom(next((z for z in reversed(ZOOMS) if z < cur - 0.001), cur / 1.1))

    def rescale_images(self):
        """Bilder passend zum Zoom neu einsetzen (Paintables haben eine feste Größe)."""
        if not self.images:
            return
        self._loading = True
        it = self.buf.get_start_iter()
        spots = []
        while True:
            if it.get_paintable() in self.images:
                spots.append(it.get_offset())
            if not it.forward_char():
                break
        cur = self.cursor_offset()
        for off in reversed(spots):
            s = self.buf.get_iter_at_offset(off)
            tex = s.get_paintable()
            info = self.images.pop(tex)
            names = self.names(s)
            e = s.copy()
            e.forward_char()
            self.buf.delete(s, e)
            pos = self.buf.get_iter_at_offset(off)
            self.insert_image_data(base64.b64decode(info["img"]), info["mime"], info["w"], info["h"], pos,
                                   b64=info["img"])
            s, e = self.buf.get_iter_at_offset(off), self.buf.get_iter_at_offset(off + 1)
            for n in names:
                t = self.buf.get_tag_table().lookup(n)
                if t:
                    self.buf.apply_tag(t, s, e)
        self.buf.place_cursor(self.buf.get_iter_at_offset(cur))
        self._loading = False

    def update_counts(self):
        txt = self.plain_text()
        words = len(txt.split())
        chars = len(txt.replace("￼", ""))
        pages = max(1, len(self.pages))
        y = self.view.get_iter_location(self.buf.get_iter_at_mark(self.buf.get_insert())).y
        cur = max(1, sum(1 for p in self.pages if p <= y))
        sel = self.selection_counts()
        if sel:
            sw, sc = sel
            pre = "" if self.flow else f"Seite {min(cur, pages)} von {pages}  ·  "
            self.count_label.set_label(f"{pre}markiert: {sw:,} von {words:,} Wörtern  ·  {sc:,} von {chars:,} Zeichen"
                                       .replace(",", "."))
            return
        if self.flow:
            self.count_label.set_label(f"{words:,} Wörter  ·  {chars:,} Zeichen  ·  fließend".replace(",", "."))
            return
        self.count_label.set_label(f"Seite {min(cur, pages)} von {pages}  ·  {words:,} Wörter  ·  {chars:,} Zeichen"
                                   .replace(",", "."))
