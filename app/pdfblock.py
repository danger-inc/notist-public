# PDF-Anhang in Words: Die Datei liegt sauber in notist/data/pdfs/ (Name = Prüfsumme, gleiche PDFs nur einmal),
# im Dokument steht nur eine Karte {"t": "pdf", "file", "name", "pages"}. Gerendert wird erst auf Knopfdruck.
import hashlib, json, math, os, shutil, subprocess, time

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, Gio, GLib, Graphene, Gsk, Gtk

try:
    gi.require_version("Poppler", "0.18")
    from gi.repository import Poppler
except (ValueError, ImportError):
    Poppler = None
try:
    import cairo
except ImportError:
    cairo = None

import dialogs
import i18n
import paths
from core import plat

PDFS = os.path.join(paths.DATA, "pdfs")

CSS = """
.wpdf { background-color: alpha(@foreground, 0.06); border: 1px solid alpha(@foreground, 0.22); border-radius: 8px;
        padding: 10px; font-family: "Noto Sans", sans-serif; }
.wpdf-name { font-weight: 700; }
.wpdf-sub { opacity: 0.6; font-size: 9pt; }
.wpdf-thumb { border: 1px solid alpha(@foreground, 0.25); border-radius: 2px; }
.wpdf-page { border: 1px solid alpha(@foreground, 0.25); }
.wpdf-zoom { min-width: 0; }
.wpdf-tools button, .wpdf-hdr button, .wpdf-search button, .wpdf-sel button { font-size: 14px; }
.wpdf-sw { min-width: 16px; min-height: 16px; padding: 0; border-radius: 8px; border: 2px solid alpha(@foreground, 0.35); }
.wpdf-sw:hover { border-color: @foreground; }
.wpdf-c-y { background: #ffd400; } .wpdf-c-g { background: #4cd964; } .wpdf-c-b { background: #4aa8ff; } .wpdf-c-r { background: #ff6b9a; }
.wpdf-cnt { font-size: 9pt; opacity: 0.65; min-width: 54px; }
.wpdf-chip { background-color: alpha(@background, 0.9); border: 1px solid alpha(@primary, 0.55); color: @foreground;
             border-radius: 6px; padding: 1px 8px; font-size: 9pt; font-weight: 700; }
.wpdf-search { border-top: 1px solid alpha(@primary, 0.25); border-bottom: 1px solid alpha(@primary, 0.25); padding: 2px 0; }
.wpdf-search entry, .wpdf-search searchentry { min-height: 24px; }
.wpdf-sel { border-top: 1px solid alpha(@primary, 0.25); border-bottom: 1px solid alpha(@primary, 0.25); padding: 3px 0; }
window.wpdf-full { background-color: @background; }
.wpdf.wpdf-dark { background-color: mix(#0e0e0e, @primary, 0.12); border-color: alpha(@primary, 0.5); color: #e6e6e6; }
.wpdf.wpdf-dark .wpdf-name, .wpdf.wpdf-dark button.wt, .wpdf.wpdf-dark .wpdf-chip { color: #e6e6e6; }
.wpdf.wpdf-dark .wpdf-chip { background-color: alpha(#0e0e0e, 0.85); }
.wpdf.wpdf-dark .wpdf-page { border-color: alpha(#ffffff, 0.18); }
window.wpdf-full.wpdf-dark { background-color: mix(#0e0e0e, @primary, 0.12); }
.light .wpdf-name { color: #1d1d1d; }
.light .wpdf { background-color: rgba(0,0,0,0.04); border-color: rgba(0,0,0,0.25); }
"""


def path_of(name):
    return os.path.join(PDFS, os.path.basename(name))


def store(src):
    """PDF in den eigenen Ordner kopieren. → {"file", "name", "pages"} oder None."""
    try:
        data = paths.read_file(src, True)
    except OSError:
        return None
    if not data.startswith(b"%PDF"):
        return None
    name = hashlib.sha256(data).hexdigest()[:24] + ".pdf"
    os.makedirs(PDFS, exist_ok=True)
    dst = path_of(name)
    if not os.path.exists(dst):
        with open(dst, "wb") as f:
            f.write(data)
    return {"file": name, "name": os.path.basename(src), "pages": page_count(dst)}


def page_count(path):
    if Poppler is None:
        return 0
    try:
        return Poppler.Document.new_from_file(Gio.File.new_for_path(path).get_uri(), None).get_n_pages()
    except GLib.Error:
        return 0


def render(doc, i, width, dpr=1, dark=None):
    """Seite i auf Breite `width` (logische Pixel) → (Textur, Höhe)."""
    page = doc.get_page(i)
    pw, ph = page.get_size()
    s = width / max(pw, 1)
    # genau auf Geräte-Pixel runden (dpr darf gebrochen sein, z. B. 1,5): jedes Texel landet auf einem Bildschirm-Pixel
    W, H = max(1, round(pw * s * dpr)), max(1, round(ph * s * dpr))
    img = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    cr = cairo.Context(img)
    cr.set_source_rgb(1, 1, 1)
    cr.paint()
    cr.scale(W / max(pw, 1), H / max(ph, 1))
    page.render(cr)
    img.flush()
    data, stride = bytes(img.get_data()), img.get_stride()
    if dark is not None:
        data = darken(data, W, H, stride, *dark) or data
    tex = Gdk.MemoryTexture.new(W, H, Gdk.MemoryFormat.B8G8R8A8_PREMULTIPLIED, GLib.Bytes.new(data), stride)
    return tex, ph * s


def darken(data, W, H, stride, bg, fg):
    """Lesemodus: Papier → dunkle Fläche (bg), Schrift/graue Linien → helle Schrift (fg). Farbige Pixel (Abbildungen,
    Diagramme, farbige Schrift) behalten ihre Farbe; dazwischen gleitender Übergang."""
    try:
        import numpy as np
    except ImportError:
        return None
    a = np.frombuffer(data, np.uint8).reshape(H, stride // 4, 4)[:, :W].astype(np.float32) / 255.0
    rgb = a[..., 2::-1]                                             # B,G,R → R,G,B
    mx, mn = rgb.max(2), rgb.min(2)
    lum = rgb @ np.array([0.299, 0.587, 0.114], np.float32)
    bgv, fgv = np.array(bg, np.float32), np.array(fg, np.float32)
    gray = bgv + (1.0 - lum)[..., None] * (fgv - bgv)
    w = np.clip((mx - mn - 0.05) / 0.22, 0.0, 1.0)[..., None]
    out = gray * (1 - w) + rgb * w
    res = np.empty((H, stride // 4, 4), np.uint8)
    res[...] = 255
    res[:, :W, 0] = np.clip(out[..., 2] * 255 + 0.5, 0, 255)
    res[:, :W, 1] = np.clip(out[..., 1] * 255 + 0.5, 0, 255)
    res[:, :W, 2] = np.clip(out[..., 0] * 255 + 0.5, 0, 255)
    return res.tobytes()


def device_scale(widget):
    """Echter (auch gebrochener) Skalierungsfaktor des Fensters – get_scale_factor() rundet 1,5 auf 2 und das Bild wurde
    dann weich heruntergerechnet."""
    try:
        surf = widget.get_native().get_surface()
        return max(1.0, float(surf.get_scale()))
    except Exception:
        return float(widget.get_scale_factor() or 1)


def open_in_scourge(path):
    exe = plat.neighbor("scourge-pdf")
    try:
        if exe:
            subprocess.Popen([exe, path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            return True
        return plat.open_external(path)
    except (OSError, GLib.Error):
        return False


def _btn(label, tip, cb):
    b = Gtk.Button(label=label, tooltip_text=tip, focus_on_click=False)
    b.add_css_class("pb"); b.add_css_class("small")
    b.set_cursor_from_name("pointer")
    b.connect("clicked", lambda *_: cb())
    return b


_NOCARET = False


def _nocaret_css():
    """Cursor des Dokuments unsichtbar machen, solange der Fokus in einer PDF liegt (Klasse wpdf-nocaret am TextView)."""
    global _NOCARET
    if _NOCARET:
        return
    _NOCARET = True
    cp = Gtk.CssProvider()
    cp.load_from_string("textview.wpdf-nocaret, textview.wpdf-nocaret text { caret-color: transparent; }")
    Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), cp, Gtk.STYLE_PROVIDER_PRIORITY_USER + 20)


def _tool(label, tip, cb, toggle=False, markup=False):
    """Flacher Werkzeugknopf im Stil der Words-Leiste (Klasse wt); nur Symbol, die Erklärung steht im Tooltip."""
    b = Gtk.ToggleButton() if toggle else Gtk.Button()
    lab = Gtk.Label()
    (lab.set_markup if markup else lab.set_label)(label)
    b.set_child(lab)
    b.set_tooltip_text(i18n.tr(tip))
    b.set_focus_on_click(False)
    b.set_can_focus(False)
    b.add_css_class("wt")
    b.set_cursor_from_name("pointer")
    if cb:
        b.connect("toggled" if toggle else "clicked", lambda *_: cb())
    return b


def _sep():
    b = Gtk.Box(valign=Gtk.Align.CENTER)
    b.add_css_class("fsep")
    return b


I_EYE, I_EYE_OFF, I_SCOURGE, I_SAVE, I_EDIT, I_TRASH = "󰈈", "󰈉", "󰏌", "󰆓", "󰏫", "󰆴"
I_MINUS, I_PLUS, I_PAGE, I_BOOK, I_DARK = "󰍴", "󰐕", "\U000f0224", "\U000f05da", "\U000f1396"
I_SEARCH, I_FULL, I_FULL_OFF = "\U000f0349", "\U000f0293", "\U000f0294"
I_UP, I_DOWN, I_CLOSE, I_QUOTE, I_COPY = "\U000f0143", "\U000f0140", "\U000f0156", "\U000f0757", "\U000f018f"


def block_of(widget):
    """Der PdfBlock, in dem `widget` (z. B. das fokussierte Widget) steckt – sonst None."""
    while widget is not None and not isinstance(widget, PdfBlock):
        widget = widget.get_parent()
    return widget


# --- gemerkte Ansicht je PDF (Zoom, Seite, Lesemodus …) – bewusst NICHT im Dokument, sondern neben den PDFs ---
VIEW_FILE = os.path.join(PDFS, "view.json")
_VIEW = None


def view_get(name):
    global _VIEW
    if _VIEW is None:
        try:
            with open(VIEW_FILE, encoding="utf-8") as f:
                _VIEW = json.load(f)
        except (OSError, ValueError):
            _VIEW = {}
    v = _VIEW.get(name)
    return dict(v) if isinstance(v, dict) else {}


def view_set(name, **kw):
    view_get(name)
    d = _VIEW.setdefault(name, {})
    if all(d.get(k) == v for k, v in kw.items()):
        return
    d.update(kw)
    try:
        os.makedirs(PDFS, exist_ok=True)
        tmp = VIEW_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(_VIEW, f)
        os.replace(tmp, VIEW_FILE)
    except OSError:
        pass


MARK_COLORS = {"y": (1.0, 0.83, 0.0), "g": (0.30, 0.85, 0.39), "b": (0.29, 0.66, 1.0), "r": (1.0, 0.42, 0.60)}

class PageImg(Gtk.Widget):
    """Seitenbild mit fester Größe: misst sich nur nach (w, h), nie nach der Textur – das Seitenverhältnis bleibt immer
    das der PDF-Seite (ein Gtk.Picture wird sonst so groß wie seine Textur und streckt/staucht die Seite)."""

    def __init__(self):
        super().__init__()
        self.tex = None
        self.w, self.h = 100, 100
        self.add_css_class("wpdf-page")

    def set_size(self, w, h):
        self.w, self.h = int(w), int(h)
        self.queue_resize()
        self.queue_draw()

    def set_texture(self, tex):
        self.tex = tex
        self.queue_draw()

    def do_measure(self, orientation, for_size):
        v = self.w if orientation == Gtk.Orientation.HORIZONTAL else self.h
        return v, v, -1, -1

    def do_snapshot(self, snap):
        if self.tex is None:
            return
        r = Graphene.Rect().init(0, 0, self.w, self.h)
        snap.append_scaled_texture(self.tex, Gsk.ScalingFilter.LINEAR, r)


class PdfPage(Gtk.Overlay):
    """Eine Seite der aufgeklappten PDF: Bild + Textauswahl (Ziehen, Doppelklick = Wort, Dreifachklick = Zeile),
    Suchtreffer, Markierungen und anklickbare Links."""

    def __init__(self, block, doc, index):
        super().__init__()
        self.block, self.index = block, index
        self.page = doc.get_page(index)
        self.pw, self.ph = self.page.get_size()
        self.sel = None                    # (x1, y1, x2, y2) in PDF-Punkten
        self.style = Poppler.SelectionStyle.GLYPH
        self.region = None
        self.hits = []                     # Suchtreffer (x1, y1, x2, y2), oben links als Ursprung
        self.cur_hit = -1
        self._links = None
        self._link_down = None
        self.pic = PageImg()
        self.set_child(self.pic)
        self.over = Gtk.DrawingArea(can_target=True, focusable=True)
        self.over.set_draw_func(self.draw)
        self.over.set_cursor_from_name("text")
        self.add_overlay(self.over)
        self.set_halign(Gtk.Align.CENTER)
        self.set_valign(Gtk.Align.START)
        self.w = 100
        drag = Gtk.GestureDrag(button=1)
        drag.connect("drag-begin", self.on_begin)
        drag.connect("drag-update", self.on_update)
        drag.connect("drag-end", self.on_end)
        self.over.add_controller(drag)
        self._drag = drag
        click = Gtk.GestureClick(button=1)
        click.connect("pressed", self.on_pressed)
        click.connect("released", self.on_released)
        self.over.add_controller(click)
        rc = Gtk.GestureClick(button=3)
        rc.connect("pressed", self.on_right)
        self.over.add_controller(rc)
        key = Gtk.EventControllerKey()
        key.connect("key-pressed", self.on_key)
        self.over.add_controller(key)
        mo = Gtk.EventControllerMotion()
        mo.connect("motion", self.on_motion)
        self.over.add_controller(mo)

    # --- Größe / Bild ---
    def set_w(self, w):
        self.w = max(40, int(w))
        self.pic.set_size(self.w, round(self.ph * self.w / max(self.pw, 1)))
        self.over.queue_draw()

    def render(self, dpr):
        cap = 4200                                    # Texturen nicht unbegrenzt groß werden lassen
        d = min(dpr, cap / max(self.w, 1))
        tex, _h = render(self.block.doc, self.index, self.w, max(1.0, d), self.block.dark_spec())
        self.pic.set_texture(tex)

    # --- Auswahl ---
    def pt(self, x, y):
        k = self.pw / max(self.w, 1)
        return (min(max(x * k, 0), self.pw), min(max(y * k, 0), self.ph))

    def set_sel(self, rect, style):
        self.sel, self.style = rect, style
        self.region = None
        if rect is not None and Poppler is not None:
            r = Poppler.Rectangle()
            r.x1, r.y1, r.x2, r.y2 = rect
            try:
                self.region = self.page.get_selected_region(4.0, style, r)
            except Exception:
                self.region = None
        self.over.queue_draw()

    def sel_rects(self):
        """Die markierten Zeilenrechtecke [x, y, w, h] in PDF-Punkten (oben links)."""
        out = []
        if self.region is None:
            return out
        try:
            for i in range(self.region.num_rectangles()):
                r = self.region.get_rectangle(i)
                out.append([r.x / 4, r.y / 4, r.width / 4, r.height / 4])
        except Exception:
            pass
        return out

    def text(self):
        if self.sel is None:
            return ""
        r = Poppler.Rectangle()
        r.x1, r.y1, r.x2, r.y2 = self.sel
        try:
            return self.page.get_selected_text(self.style, r) or ""
        except Exception:
            return ""

    # --- Suche ---
    def set_hits(self, hits, cur=-1):
        self.hits, self.cur_hit = hits, cur
        self.over.queue_draw()

    def find(self, q):
        out = []
        try:
            for r in self.page.find_text_with_options(q, Poppler.FindFlags.IGNORE_DIACRITICS):
                out.append((r.x1, self.ph - r.y2, r.x2, self.ph - r.y1))
        except Exception:
            pass
        return out

    # --- Links ---
    def links(self):
        if self._links is None:
            self._links = []
            try:
                for m in self.page.get_link_mapping():
                    a = m.area
                    self._links.append((a.x1, self.ph - a.y2, a.x2, self.ph - a.y1, m.action))
            except Exception:
                pass
        return self._links

    def link_at(self, x, y):
        px, py = self.pt(x, y)
        for x1, y1, x2, y2, act in self.links():
            if x1 <= px <= x2 and y1 <= py <= y2:
                return act
        return None

    def on_motion(self, ctrl, x, y):
        self.over.set_cursor_from_name("pointer" if self.link_at(x, y) is not None else "text")

    def follow_link(self, act):
        try:
            t = act.type
            if t == Poppler.ActionType.URI:
                uri = act.uri.uri
                if uri.split(":", 1)[0].lower() in ("http", "https", "mailto"):
                    plat.open_external(uri)
            elif t == Poppler.ActionType.GOTO_DEST:
                dest = act.goto_dest.dest
                if dest.type == Poppler.DestType.NAMED:
                    dest = self.block.doc.find_dest(dest.named_dest)
                if dest is not None and dest.page_num:
                    self.block.goto_page(dest.page_num - 1)
        except Exception:
            pass

    # --- Zeichnen ---
    def draw(self, area, cr, w, h):
        k = self.w / max(self.pw, 1)
        cr.scale(k, k)
        cr.set_operator(cairo.OPERATOR_OVER if self.block.dark else cairo.OPERATOR_MULTIPLY)   # Textmarker: Schrift bleibt lesbar
        for m in self.block.marks_on(self.index):
            col = MARK_COLORS.get(m.get("k", "y"), MARK_COLORS["y"])
            for x, y, rw, rh in m.get("r", []):
                if m.get("k") == "u":
                    pr = self.block.accent()
                    cr.set_source_rgba(pr.red, pr.green, pr.blue, 0.95)
                    cr.rectangle(x, y + rh - 1.3, rw, 1.3)
                else:
                    cr.set_source_rgba(*col, 0.4 if self.block.dark else 0.6)
                    cr.rectangle(x, y, rw, rh)
                cr.fill()
        for i, (x1, y1, x2, y2) in enumerate(self.hits):
            on = i == self.cur_hit
            cr.set_source_rgba(1.0, 0.55, 0.0, 0.75 if on else 0.38)
            cr.rectangle(x1 - 1, y1 - 1, x2 - x1 + 2, y2 - y1 + 2)
            cr.fill()
        if self.region is None:
            return
        try:
            n = self.region.num_rectangles()
        except Exception:
            return
        pr = self.block.accent()
        cr.set_source_rgba(pr.red, pr.green, pr.blue, 0.35)
        for i in range(n):
            r = self.region.get_rectangle(i)
            cr.rectangle(r.x / 4, r.y / 4, r.width / 4, r.height / 4)
        cr.fill()

    def on_pressed(self, g, n, x, y):
        self.over.grab_focus()
        self._link_down = self.link_at(x, y) if n == 1 else None
        if n >= 2:
            self._drag.set_state(Gtk.EventSequenceState.CLAIMED)
            px, py = self.pt(x, y)
            self.block.clear_selection(self)
            self.set_sel((px, py, px, py), Poppler.SelectionStyle.WORD if n == 2 else Poppler.SelectionStyle.LINE)
            self.block.selection_done()

    def on_released(self, g, n, x, y):
        act, self._link_down = self._link_down, None
        if act is not None and n == 1 and self.link_at(x, y) is act:
            self.follow_link(act)

    def on_begin(self, g, x, y):
        self._start = self.pt(x, y)
        if self.link_at(x, y) is not None:            # über einem Link erst bei echter Bewegung auswählen
            self._moved = False
            return
        self._moved = True
        g.set_state(Gtk.EventSequenceState.CLAIMED)
        self.over.grab_focus()
        self.block.clear_selection(None)
        self.set_sel(None, Poppler.SelectionStyle.GLYPH)

    def on_update(self, g, dx, dy):
        ok, sx, sy = g.get_start_point()
        if not ok:
            return
        if not self._moved:
            if abs(dx) + abs(dy) < 5:
                return
            self._moved = True
            self._link_down = None
            g.set_state(Gtk.EventSequenceState.CLAIMED)
            self.over.grab_focus()
            self.block.clear_selection(None)
        x2, y2 = self.pt(sx + dx, sy + dy)
        x1, y1 = self._start
        if abs(x2 - x1) + abs(y2 - y1) < 1:
            return
        self.set_sel((x1, y1, x2, y2), Poppler.SelectionStyle.GLYPH)

    def on_end(self, g, dx, dy):
        if self.sel is not None:
            self.block.selection_done()

    def on_key(self, ctrl, keyval, code, state):
        if state & plat.primary_mask() and keyval in (Gdk.KEY_c, Gdk.KEY_C):
            self.block.copy_selection()
            return True
        if state & plat.primary_mask() and keyval in (Gdk.KEY_a, Gdk.KEY_A):
            self.block.select_all()
            return True
        if state & plat.primary_mask() and keyval in (Gdk.KEY_f, Gdk.KEY_F):
            self.block.open_search()
            return True
        if keyval == Gdk.KEY_F3 or (keyval in (Gdk.KEY_g, Gdk.KEY_G) and state & plat.primary_mask()):
            self.block.next_hit(-1 if state & Gdk.ModifierType.SHIFT_MASK else 1)
            return True
        if keyval == Gdk.KEY_Escape:
            self.block.clear_selection(None)
            return True
        return False

    def on_right(self, g, n, x, y):
        self.over.grab_focus()
        px, py = self.pt(x, y)
        mark = self.block.mark_at(self.index, px, py)
        pop = Gtk.Popover(has_arrow=False)
        pop.set_parent(self.over)
        r = Gdk.Rectangle()
        r.x, r.y, r.width, r.height = int(x), int(y), 1, 1
        pop.set_pointing_to(r)
        col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        entries = [(i18n.tr("Kopieren"), self.block.copy_selection),
                   (i18n.tr("Alles auswählen"), self.block.select_all)]
        if self.block.selected_text():
            entries.insert(1, (i18n.tr("Gelb markieren"), lambda: self.block.add_mark("y")))
            entries.insert(2, (i18n.tr("Als Zitat einfügen"), self.block.quote_selection))
        if mark is not None:
            entries.insert(0, (i18n.tr("Markierung entfernen"), lambda: self.block.remove_mark(mark)))
            if mark.get("t"):
                entries.insert(1, (i18n.tr("Markierung als Zitat einfügen"), lambda: self.block.quote_mark(mark)))
        for label, cb in entries:
            b = Gtk.Button(label=label, focus_on_click=False)
            b.add_css_class("pb"); b.add_css_class("small")
            b.connect("clicked", lambda _b, cb=cb: (pop.popdown(), cb()))
            col.append(b)
        pop.set_child(col)
        pop.connect("closed", lambda p: GLib.idle_add(p.unparent))
        pop.popup()


class PdfBlock(Gtk.Box):
    def __init__(self, writer, info):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.writer = writer
        marks = info.get("marks")
        self.info = {"file": info.get("file", ""), "name": info.get("name", "PDF"), "pages": int(info.get("pages") or 0)}
        if isinstance(marks, list) and marks:
            self.info["marks"] = [m for m in marks if isinstance(m, dict)]
        self.doc = None
        self.width = 600
        self.add_css_class("wpdf")
        self.fs = None                                # Vollbild-Fenster
        self.fs_w = 1200
        self.spread = False
        self.dark = False
        self.plist = []
        self.hit_list = []                            # [(Seitenindex, Nr. in page.hits)]
        self.hit_i = -1
        self._search_id = None
        self._search_idle = None
        self._pos_id = None
        self._chip_conn = []
        top = Gtk.Box(spacing=12)
        self.thumb = Gtk.Picture(content_fit=Gtk.ContentFit.CONTAIN, can_shrink=True, valign=Gtk.Align.START)
        self.thumb.add_css_class("wpdf-thumb")
        self.thumb.set_size_request(54, 72)
        top.append(self.thumb)
        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, hexpand=True, valign=Gtk.Align.CENTER)
        self.title = Gtk.Label(label="󰈦 " + self.info["name"], xalign=0, ellipsize=3)
        self.title.add_css_class("wpdf-name")
        self.sub = Gtk.Label(xalign=0)
        self.sub.add_css_class("wpdf-sub")
        text.append(self.title)
        text.append(self.sub)
        btns = Gtk.Box(spacing=2, margin_top=4)
        btns.add_css_class("wpdf-hdr")
        self.view_btn = _tool(I_EYE, "Die Seiten hier in notist anzeigen", self.toggle)
        btns.append(self.view_btn)
        btns.append(_sep())
        btns.append(_tool(I_SCOURGE, "In scourge-pdf öffnen und bearbeiten", self.open_scourge))
        btns.append(_tool(I_SAVE, "Eine Kopie der PDF speichern", self.save_as))
        btns.append(_tool(I_EDIT, "PDF umbenennen", self.rename))
        btns.append(_tool(I_TRASH, "PDF aus dem Dokument entfernen", self.ask_remove))
        text.append(btns)
        top.append(text)
        self.append(top)
        self.zoom = 1.0
        self._wheel, self._wz, self._wz_id = None, None, None
        self._sync = False

        # --- Werkzeugleiste (nur bei aufgeklappter PDF) ---
        self.view_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, visible=False)
        self.tools = Gtk.Box(spacing=2)
        self.tools.add_css_class("wpdf-tools")
        try:
            from writer import WrapLayout
            self.tools.set_layout_manager(WrapLayout(spacing=2, row_spacing=2))
        except Exception:
            pass
        self.tools.append(_tool(I_MINUS, "Verkleinern (Strg+Mausrad, Pinch)", lambda: self.set_zoom(self.zoom / 1.25)))
        self.zoom_lbl = _tool("100 %", "Klick: zurück auf Seitenbreite", lambda: self.set_zoom(1.0))
        self.tools.append(self.zoom_lbl)
        self.tools.append(_tool(I_PLUS, "Vergrößern (Strg+Mausrad, Pinch)", lambda: self.set_zoom(self.zoom * 1.25)))
        self.tools.append(_sep())
        self.tools.append(_tool(I_PAGE, "Ganze Seite ins Bild passen", self.fit_page))
        self.spread_btn = _tool(I_BOOK, "Zwei Seiten nebeneinander", lambda: self._sync or self.toggle_spread(), toggle=True)
        self.tools.append(self.spread_btn)
        self.dark_btn = _tool(I_DARK, "Lesemodus: dunkles Papier und helle Schrift, Farben bleiben", lambda: self._sync or self.toggle_dark(), toggle=True)
        self.tools.append(self.dark_btn)
        self.tools.append(_sep())
        self.tools.append(_tool(I_SEARCH, "In der PDF suchen (Strg+F)", self.open_search))
        self.full_btn = _tool(I_FULL, "Vollbild (Esc beendet)", self.toggle_full)
        self.tools.append(self.full_btn)
        self.view_col.append(self.tools)

        # Suchleiste
        self.searchbar = Gtk.Box(spacing=4, visible=False)
        self.searchbar.add_css_class("wpdf-search")
        self.search_entry = Gtk.SearchEntry(hexpand=True, placeholder_text=i18n.tr("In der PDF suchen"))
        self.search_entry.connect("search-changed", lambda *_: self.search_soon())
        self.search_entry.connect("activate", lambda *_: self.next_hit(1))
        self.search_entry.connect("stop-search", lambda *_: self.close_search())
        sk = Gtk.EventControllerKey()
        sk.connect("key-pressed", self._search_key)
        self.search_entry.add_controller(sk)
        self.search_cnt = Gtk.Label(label="", xalign=1)
        self.search_cnt.add_css_class("wpdf-cnt")
        self.searchbar.append(self.search_entry)
        self.searchbar.append(self.search_cnt)
        self.searchbar.append(_tool(I_UP, "Voriger Treffer (Umschalt+Enter)", lambda: self.next_hit(-1)))
        self.searchbar.append(_tool(I_DOWN, "Nächster Treffer (Enter)", lambda: self.next_hit(1)))
        self.searchbar.append(_tool(I_CLOSE, "Suche schließen (Esc)", self.close_search))
        self.view_col.append(self.searchbar)

        # Auswahlleiste: erscheint, sobald Text markiert ist
        self.selbar = Gtk.Box(spacing=6, visible=False, valign=Gtk.Align.CENTER)
        self.selbar.add_css_class("wpdf-sel")
        for key, tip in (("y", "Gelb markieren"), ("g", "Grün markieren"), ("b", "Blau markieren"), ("r", "Rosa markieren")):
            b = Gtk.Button(tooltip_text=i18n.tr(tip), focus_on_click=False, can_focus=False, valign=Gtk.Align.CENTER)
            b.add_css_class("wpdf-sw"); b.add_css_class("wpdf-c-" + key)
            b.set_cursor_from_name("pointer")
            b.connect("clicked", lambda _b, k=key: self.add_mark(k))
            self.selbar.append(b)
        self.selbar.append(_tool("<u>U</u>", "Unterstreichen", lambda: self.add_mark("u"), markup=True))
        self.selbar.append(_sep())
        self.selbar.append(_tool(I_QUOTE, "Markierten Text als Zitat mit Seitenzahl unter die PDF einfügen", self.quote_selection))
        self.selbar.append(_tool(I_COPY, "Markierten Text kopieren", self.copy_selection))
        self.view_col.append(self.selbar)

        self.pages = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, hexpand=True)
        # Waagerecht scrollbar (Wischen), wenn die Seiten durch Zoom/schmales Fenster breiter sind als der Block;
        # senkrecht scrollt weiter das Dokument (hscroll-Fenster gibt senkrechte Bewegung nach außen).
        self.hsc = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.AUTOMATIC, vscrollbar_policy=Gtk.PolicyType.NEVER,
                                      propagate_natural_height=True, hexpand=True, visible=False)
        self.hsc.set_child(self.pages)
        self.hsc.set_overlay_scrolling(False)
        pinch = Gtk.GestureZoom(propagation_phase=Gtk.PropagationPhase.CAPTURE)
        pinch.connect("begin", lambda g, s: setattr(self, "_z0", self.zoom))
        pinch.connect("scale-changed", lambda g, sc: self.zoom_live(getattr(self, "_z0", 1.0) * sc))
        pinch.connect("end", lambda *_: self.sharpen_soon())
        self.hsc.add_controller(pinch)
        sc = Gtk.EventControllerScroll(flags=Gtk.EventControllerScrollFlags.VERTICAL,
                                       propagation_phase=Gtk.PropagationPhase.CAPTURE)
        sc.connect("scroll", self.on_scroll)
        self.hsc.add_controller(sc)
        # Seitenanzeige schwebt über den Seiten und bleibt beim Scrollen im Bild
        self.ov = Gtk.Overlay()
        self.ov.set_child(self.hsc)
        self.chip = Gtk.Label(label="", halign=Gtk.Align.END, valign=Gtk.Align.START, margin_end=12, margin_top=8,
                              can_target=False, visible=False)
        self.chip.add_css_class("wpdf-chip")
        self.ov.add_overlay(self.chip)
        self.holder = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.holder.append(self.ov)
        self.view_col.append(self.holder)
        self.append(self.view_col)
        self._sharp_id = None
        self._render_id = None
        self.refresh_sub()
        GLib.idle_add(self.load_thumb)
        # Liegt der Fokus in der PDF, malt der Text-Cursor des Dokuments sonst einen riesigen Balken (Zeilenhöhe = Blockhöhe)
        fc = Gtk.EventControllerFocus()
        fc.connect("notify::contains-focus", self._focus_changed)
        self.add_controller(fc)

    def _focus_changed(self, ctrl, _p):
        view = getattr(self.writer, "view", None)
        if view is None:
            return
        _nocaret_css()
        (view.add_css_class if ctrl.get_property("contains-focus") else view.remove_css_class)("wpdf-nocaret")

    def toast(self, msg):
        app = self.writer.win.get_application()
        if app is not None and hasattr(app, "notify"):
            app.notify(msg)

    # --- Modell ---
    def model(self):
        return {"t": "pdf", **self.info}

    def path(self):
        return path_of(self.info["file"])

    def refresh_sub(self):
        n = self.info["pages"]
        ok = os.path.exists(self.path())
        s = (f"{n} Seite" + ("n" if n != 1 else "") if n else "PDF")
        try:
            sz = os.path.getsize(self.path())
            s += f" · {sz / 1048576:.1f} MB" if sz >= 1048576 else f" · {max(1, sz // 1024)} KB"
        except OSError:
            pass
        k = len(self.info.get("marks", []))
        if k:
            s += f" · {k} Markierung" + ("en" if k != 1 else "")
        self.sub.set_label(s if ok else "Datei fehlt im Ordner notist/data/pdfs")

    def open_doc(self):
        if self.doc is None and Poppler is not None and cairo is not None:
            try:
                self.doc = Poppler.Document.new_from_file(Gio.File.new_for_path(self.path()).get_uri(), None)
            except GLib.Error:
                self.doc = None
        return self.doc

    def load_thumb(self):
        doc = self.open_doc()
        if doc is not None and doc.get_n_pages():
            if not self.info["pages"]:
                self.info["pages"] = doc.get_n_pages()
                self.refresh_sub()
            tex, h = render(doc, 0, 108, 2)
            self.thumb.set_paintable(tex)
            self.thumb.set_size_request(54, max(40, round(h / 2)))
        return False

    # --- Ansicht merken ---
    def remember(self, **kw):
        if self.info["file"]:
            view_set(self.info["file"], **kw)

    def scroller(self):
        return self.fs_scroll if self.fs is not None else self.writer.scroll

    # --- Auf-/Zuklappen ---
    def is_open(self):
        return self.view_col.get_visible()

    def toggle(self):
        show = not self.view_col.get_visible()
        if show and not self.plist:
            doc = self.open_doc()
            if doc is None:
                self.toast("Die PDF lässt sich hier nicht anzeigen (poppler fehlt oder Datei fehlt)")
                return
            v = view_get(self.info["file"])
            self.zoom = max(0.4, min(4.0, float(v.get("zoom", 1.0) or 1.0)))
            self.spread = bool(v.get("spread", False))
            self.set_size_request(max(240, self.eff_w()), -1)
            self.dark = bool(v.get("dark", False))
            self.plist = [PdfPage(self, doc, i) for i in range(doc.get_n_pages())]
            self.sync_buttons()
            self.arrange()
            self.layout_pages()
            self.render_all()
            self._restore_page = int(v.get("page", 0) or 0)
        self.view_col.set_visible(show)
        self.hsc.set_visible(show)
        if show:
            self.connect_chip(self.writer.scroll)
            if getattr(self, "_restore_page", 0) > 0:
                n = self._restore_page
                self._restore_page = 0
                for ms in (180, 650):
                    GLib.timeout_add(ms, lambda n=n: (self.goto_page(n, animate=False), False)[1])
        else:
            self.clear_selection(None)
            self.close_search()
        self.remember(open=show)
        self.view_btn.get_child().set_label(I_EYE_OFF if show else I_EYE)
        self.view_btn.set_tooltip_text(i18n.tr("Seiten ausblenden" if show else "Die Seiten hier in notist anzeigen"))
        GLib.timeout_add(60, lambda: (self.writer.invalidate(), False)[1])

    def sync_buttons(self):
        self.zoom_lbl.get_child().set_label(f"{round(self.zoom * 100)} %")
        self._sync = True
        self.spread_btn.set_active(self.spread)
        self.dark_btn.set_active(self.dark)
        self._sync = False
        self.apply_dark_css()

    def arrange(self):
        """Seiten (neu) in die Spalte setzen – einzeln oder paarweise nebeneinander."""
        for pg in self.plist:
            p = pg.get_parent()
            if p is not None:
                p.remove(pg)
        c = self.pages.get_first_child()
        while c is not None:
            nxt = c.get_next_sibling()
            self.pages.remove(c)
            c = nxt
        if self.spread:
            for i in range(0, len(self.plist), 2):
                row = Gtk.Box(spacing=10, halign=Gtk.Align.CENTER)
                for pg in self.plist[i:i + 2]:
                    row.append(pg)
                self.pages.append(row)
        else:
            for pg in self.plist:
                self.pages.append(pg)

    # --- Layout ---
    def avail(self):
        if self.fs is not None:
            return max(240, self.fs_w - 40)
        return max(200, self.eff_w() - 40)

    def eff_w(self):
        """Blockbreite: bei zwei Seiten breiter als die Textspalte, so weit wie der sichtbare Bereich es zulässt."""
        if not self.spread:
            return self.width
        room = 0
        try:
            sc = self.writer.scroll
            ok, pt = self.compute_point(sc, Graphene.Point().init(0, 0))
            room = sc.get_width() - (max(pt.x, 0) if ok else 0) - 24
        except Exception:
            pass
        return int(min(self.width * 1.9, max(self.width * 1.25, room)))

    def base_w(self):
        cap = 2200 if self.spread else 900
        if self.fs is not None:
            cap *= 1.6
        return max(200, min(self.avail(), cap))

    def accent(self):
        ok, c = self.get_style_context().lookup_color("primary")
        if not ok:
            c = Gdk.RGBA(); c.parse("#4a90d9")
        return c

    def layout_pages(self):
        """Alle Seiten im selben Maßstab: die breiteste misst base·zoom, schmalere/kleinere Seiten bleiben proportional
        (Hoch-, Querformat und gemischte Größen behalten ihr Seitenverhältnis)."""
        pgs = self.plist
        if not pgs:
            return
        w = self.base_w()
        if self.spread:
            w = (w - 10) / 2
        k = w * self.zoom / max(max(p.pw for p in pgs), 1)
        for p in pgs:
            p.set_w(p.pw * k)

    def page_list(self):
        return list(self.plist)

    def toggle_spread(self):
        self.spread = not self.spread
        self.set_size_request(max(240, self.eff_w()), -1)
        self.remember(spread=self.spread)
        cur = self.current_page()
        self.sync_buttons()
        self.arrange()
        self.layout_pages()
        self.sharpen_soon()
        GLib.timeout_add(80, lambda: (self.writer.invalidate(), self.goto_page(cur, animate=False), False)[-1])

    def toggle_dark(self):
        self.dark = not self.dark
        self.remember(dark=self.dark)
        self.sync_buttons()
        self.render_all()

    def dark_spec(self):
        """(Papierfarbe, Schriftfarbe) für den Lesemodus, aus der Akzentfarbe des Themas getönt – oder None."""
        if not self.dark:
            return None
        c = self.accent()
        return ((0.055 + 0.12 * c.red * 0.5, 0.055 + 0.12 * c.green * 0.5, 0.06 + 0.12 * c.blue * 0.5),
                tuple(0.90 * (1 - 0.08) + 0.08 * v for v in (c.red, c.green, c.blue)))

    def apply_dark_css(self):
        for w in (self, self.fs):
            if w is not None:
                (w.add_css_class if self.dark else w.remove_css_class)("wpdf-dark")

    # --- Zoom ---
    def on_scroll(self, ctrl, dx, dy):
        if not ctrl.get_current_event_state() & plat.primary_mask():
            return False
        # wie im Dokument (writer.on_scroll): dy aufsummieren, stufenlos, Gegen-Zittern des Touchpads ignorieren
        pad = ctrl.get_unit() == Gdk.ScrollUnit.SURFACE
        now = time.monotonic()
        g = self._wheel
        if g is None or now - g["t"] > 0.25:
            g = self._wheel = {"sum": 0.0, "t": now, "z0": self.zoom}
        g["t"] = now
        g["sum"] += dy                           # Summe der Geste: Zittern hebt sich auf, Richtung = Vorzeichen der Summe
        g["target"] = max(0.4, min(4.0, g["z0"] * math.exp(-g["sum"] * (0.012 if pad else 0.1))))
        self.zoom_live(g["target"])
        return True

    def zoom_live(self, z):
        """Laufende Geste: höchstens alle 50 ms neu anordnen (set_zoom schärft 220 ms nach dem letzten Schritt)."""
        self._wz = z
        if self._wz_id is None:
            self._wz = None
            self.set_zoom(z)
            self._wz_id = GLib.timeout_add(50, self._zoom_live_tick)

    def _zoom_live_tick(self):
        if self._wz is None:
            self._wz_id = None
            return False
        z, self._wz = self._wz, None
        self.set_zoom(z)
        return True

    def set_zoom(self, z):
        z = round(max(0.4, min(4.0, z)), 3)
        if abs(z - self.zoom) < 0.004:
            return
        h = self.hsc.get_hadjustment()
        frac = (h.get_value() + h.get_page_size() / 2) / max(h.get_upper(), 1)
        self.zoom = z
        self.zoom_lbl.get_child().set_label(f"{round(z * 100)} %")
        self.remember(zoom=z)
        self.layout_pages()                       # bis zum Schärfen wird das alte Bild gestreckt
        self.sharpen_soon()
        GLib.idle_add(self._keep_center, frac)
        GLib.timeout_add(80, lambda: (self.writer.invalidate(), False)[1])

    def fit_page(self):
        pgs = self.plist
        if not pgs:
            return
        vh = self.scroller().get_height() or 600
        cur = pgs[self.current_page()]
        hh = max(cur.pic.h, 1)
        self.set_zoom(min(1.0, self.zoom * (vh - 32) / hh))
        GLib.timeout_add(200, lambda: (self.goto_page(self.current_page(), animate=False), False)[1])

    def _keep_center(self, frac):
        h = self.hsc.get_hadjustment()
        h.set_value(max(0, min(frac * h.get_upper() - h.get_page_size() / 2, h.get_upper() - h.get_page_size())))
        return False

    def sharpen_soon(self):
        if self._sharp_id is not None:
            GLib.source_remove(self._sharp_id)
        self._sharp_id = GLib.timeout_add(220, self.render_all)

    def render_all(self):
        """Alle Seiten in der aktuellen Größe scharf rendern – eine pro Leerlauf, damit die Oberfläche flüssig bleibt."""
        self._sharp_id = None
        if self._render_id is not None:
            GLib.source_remove(self._render_id)
        todo = self.page_list()
        dpr = device_scale(self)

        def step():
            if not todo:
                self._render_id = None
                return False
            pg = todo.pop(0)
            if pg.get_parent() is not None:
                pg.render(dpr)
            return True
        step()
        self._render_id = GLib.idle_add(step)
        return False

    # --- Seitenanzeige / Springen ---
    def connect_chip(self, scroll):
        for adj, cid in self._chip_conn:
            try:
                adj.disconnect(cid)
            except Exception:
                pass
        adj = scroll.get_vadjustment()
        self._chip_conn = [(adj, adj.connect("value-changed", lambda *_: self.update_chip()))]
        GLib.idle_add(self.update_chip)

    def _page_y(self, pg):
        ok, pt = pg.compute_point(self.scroller(), Graphene.Point().init(0, 0))
        return pt.y if ok else None

    def current_page(self):
        """Seite in der Mitte des sichtbaren Bereichs (die nächstliegende, wenn die Mitte zwischen zwei Seiten liegt)."""
        sc = self.scroller()
        mid = (sc.get_height() or 600) / 2
        best, bd = 0, 1e9
        for i, pg in enumerate(self.plist):
            y = self._page_y(pg)
            if y is None:
                continue
            h = pg.pic.h
            d = 0 if y <= mid <= y + h else min(abs(y - mid), abs(y + h - mid))
            if d < bd:
                best, bd = i, d
        return best

    def update_chip(self):
        if not self.plist or not self.view_col.get_visible() or not self.get_mapped():
            self.chip.set_visible(False)
            return False
        sc = self.scroller()
        ok, pt = self.ov.compute_point(sc, Graphene.Point().init(0, 0))
        vh = sc.get_height() or 600
        if not ok or pt.y > vh - 30 or pt.y + self.ov.get_height() < 30:
            self.chip.set_visible(False)
            return False
        i = self.current_page()
        self.chip.set_label(f"{i + 1} / {len(self.plist)}")
        self.chip.set_visible(True)
        self.chip.set_margin_top(int(max(8, min(-pt.y + 10, self.ov.get_height() - 36))))
        if self._pos_id is not None:
            GLib.source_remove(self._pos_id)
        self._pos_id = GLib.timeout_add(900, lambda: (setattr(self, "_pos_id", None), self.remember(page=i), False)[-1])
        return False

    def goto_page(self, i, animate=True, y_off=0):
        if not self.plist:
            return
        i = max(0, min(i, len(self.plist) - 1))
        y = self._page_y(self.plist[i])
        if y is None:
            return
        adj = self.scroller().get_vadjustment()
        target = max(0, min(adj.get_value() + y + y_off - 12, adj.get_upper() - adj.get_page_size()))
        if not animate:
            adj.set_value(target)
            return
        start, t0 = adj.get_value(), GLib.get_monotonic_time()

        def step():
            t = min(1.0, (GLib.get_monotonic_time() - t0) / 220000)
            e = 1 - (1 - t) ** 3
            adj.set_value(start + (target - start) * e)
            return t < 1.0
        GLib.timeout_add(16, step)

    # --- Suche ---
    def open_search(self):
        if not self.view_col.get_visible():
            self.toggle()
        self.searchbar.set_visible(True)
        self.search_entry.grab_focus()
        self.search_entry.select_region(0, -1)
        t = self.selected_text()
        if t and "\n" not in t.strip() and len(t) < 80:
            self.search_entry.set_text(t.strip())

    def close_search(self):
        if not self.searchbar.get_visible():
            return
        self.searchbar.set_visible(False)
        self.search_entry.set_text("")
        self.clear_hits()

    def toggle_search(self):
        if self.searchbar.get_visible() and self.search_entry.has_focus():
            self.close_search()
        else:
            self.open_search()

    def _search_key(self, ctrl, keyval, code, state):
        if keyval == Gdk.KEY_Escape:
            self.close_search()
            return True
        if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter) and state & Gdk.ModifierType.SHIFT_MASK:
            self.next_hit(-1)
            return True
        if keyval == Gdk.KEY_F3:
            self.next_hit(-1 if state & Gdk.ModifierType.SHIFT_MASK else 1)
            return True
        return False

    def clear_hits(self):
        if self._search_idle is not None:
            GLib.source_remove(self._search_idle)
            self._search_idle = None
        if self._search_id is not None:
            GLib.source_remove(self._search_id)
            self._search_id = None
        self.hit_list, self.hit_i = [], -1
        for pg in self.plist:
            if pg.hits:
                pg.set_hits([], -1)
        self.search_cnt.set_label("")

    def search_soon(self):
        if self._search_id is not None:
            GLib.source_remove(self._search_id)
        self._search_id = GLib.timeout_add(250, self.run_search)

    def run_search(self):
        """Über alle Seiten suchen – in Häppchen im Leerlauf, damit lange PDFs die Oberfläche nicht anhalten."""
        self._search_id = None
        q = self.search_entry.get_text().strip()
        self.clear_hits()
        if not q:
            return False
        todo = list(range(len(self.plist)))
        state = {"first": True}

        def step():
            for _ in range(8):
                if not todo:
                    break
                i = todo.pop(0)
                pg = self.plist[i]
                hits = pg.find(q)
                pg.hits = hits
                pg.over.queue_draw()
                for j in range(len(hits)):
                    self.hit_list.append((i, j))
                if hits and state["first"]:
                    state["first"] = False
                    self.hit_i = len(self.hit_list) - len(hits)
                    self.show_hit()
            self.update_count(done=not todo, q=q)
            if not todo:
                self._search_idle = None
                return False
            return True
        self._search_idle = GLib.idle_add(step)
        return False

    def update_count(self, done=True, q=""):
        n = len(self.hit_list)
        if not n:
            self.search_cnt.set_label(i18n.tr("kein Treffer") if done else "…")
        else:
            self.search_cnt.set_label(f"{self.hit_i + 1} / {n}" + ("" if done else "+"))

    def show_hit(self):
        for pg in self.plist:
            pg.cur_hit = -1
        if not (0 <= self.hit_i < len(self.hit_list)):
            return
        i, j = self.hit_list[self.hit_i]
        pg = self.plist[i]
        pg.cur_hit = j
        pg.over.queue_draw()
        # Treffer ins Bild holen: nur scrollen, wenn er nicht schon gut sichtbar ist
        x1, y1, x2, y2 = pg.hits[j]
        k = pg.w / max(pg.pw, 1)
        py = self._page_y(pg)
        if py is None:
            return
        vh = self.scroller().get_height() or 600
        ty = py + y1 * k
        if ty < 60 or ty > vh - 80:
            self.goto_page(i, y_off=y1 * k - vh / 3 + 12)

    def next_hit(self, d):
        n = len(self.hit_list)
        if not n:
            return
        self.hit_i = (self.hit_i + d) % n
        self.show_hit()
        self.update_count(done=self._search_idle is None)

    # --- Textauswahl ---
    def clear_selection(self, keep):
        for pg in self.plist:
            if pg is not keep and pg.sel is not None:
                pg.set_sel(None, pg.style)
        if keep is None:
            self.selbar.set_visible(False)

    def selected_text(self):
        parts = [pg.text() for pg in self.plist if pg.sel is not None]
        return "\n".join(t.strip("\n") for t in parts if t.strip())

    def selection_done(self):
        t = self.selected_text()
        self.selbar.set_visible(bool(t))
        if t:                                     # wie unter Linux üblich: Auswahl liegt gleich in der Mittelklick-Ablage
            try:
                self.get_display().get_primary_clipboard().set(t)
            except Exception:
                pass

    def copy_selection(self):
        t = self.selected_text()
        if t:
            self.get_display().get_clipboard().set(t)
            self.toast(i18n.tr("Kopiert"))

    def select_all(self):
        self.clear_selection(None)
        for pg in self.plist:
            pg.set_sel((0, 0, pg.pw, pg.ph), Poppler.SelectionStyle.GLYPH)
        self.selection_done()

    # --- Markierungen ---
    def marks_on(self, index):
        return [m for m in self.info.get("marks", ()) if m.get("p") == index]

    def mark_at(self, index, x, y):
        for m in self.marks_on(index):
            for rx, ry, rw, rh in m.get("r", []):
                if rx <= x <= rx + rw and ry <= y <= ry + rh:
                    return m
        return None

    def add_mark(self, kind):
        new = []
        for pg in self.plist:
            if pg.sel is None:
                continue
            rects = pg.sel_rects()
            if rects:
                new.append({"p": pg.index, "k": kind, "r": [[round(v, 2) for v in r] for r in rects],
                            "t": pg.text().strip()})
        if not new:
            return
        self.writer.checkpoint()
        self.info.setdefault("marks", []).extend(new)
        self.clear_selection(None)
        for pg in self.plist:
            pg.over.queue_draw()
        self.refresh_sub()
        self.writer.changed()

    def remove_mark(self, mark):
        marks = self.info.get("marks", [])
        if mark in marks:
            self.writer.checkpoint()
            marks.remove(mark)
            if not marks:
                self.info.pop("marks", None)
            for pg in self.plist:
                pg.over.queue_draw()
            self.refresh_sub()
            self.writer.changed()

    def quote(self, text, page):
        """Text als Zitat mit Seitenzahl direkt unter die PDF ins Dokument setzen."""
        text = " ".join(text.split())
        if not text:
            return
        w = self.writer
        for anchor, x in w.blocks.items():
            if x is self:
                w.checkpoint()
                it = w.anchor_iter(anchor)
                it.forward_char()
                w.buf.place_cursor(it)
                w.buf.insert_at_cursor("\n" + "„" + text + "“ (S. " + str(page + 1) + ")")
                w.set_style("quote")
                w.changed()
                self.toast(i18n.tr("Zitat eingefügt"))
                return

    def quote_selection(self):
        pgs = [pg for pg in self.plist if pg.sel is not None and pg.text().strip()]
        if pgs:
            self.quote(self.selected_text(), pgs[0].index)
            self.clear_selection(None)

    def quote_mark(self, mark):
        self.quote(mark.get("t", ""), int(mark.get("p", 0)))

    # --- Vollbild ---
    def toggle_full(self):
        if self.fs is not None:
            self.fs.close()
            return
        if not self.plist:
            self.toggle()
            if not self.plist:
                return
        win = Gtk.Window(transient_for=self.writer.win, title=self.info["name"])
        win.add_css_class("wpdf-full")
        win.add_css_class("settings")
        win.set_default_size(1200, 800)
        self.fs = win
        self.fs_scroll = Gtk.ScrolledWindow(vexpand=True, hexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER,
                                            vscrollbar_policy=Gtk.PolicyType.AUTOMATIC)
        # Ansicht aus dem Dokument herausnehmen und im Fenster zeigen
        self.holder.remove(self.ov)
        self.fs_vp = Gtk.Viewport()
        self.fs_vp.set_child(self.ov)
        self.fs_scroll.set_child(self.fs_vp)
        self.holder.append(self.fs_scroll)
        self.holder.set_vexpand(True)
        self.remove(self.view_col)
        self.view_col.set_margin_start(14)
        self.view_col.set_margin_end(14)
        self.view_col.set_margin_top(10)
        self.view_col.set_margin_bottom(6)
        win.set_child(self.view_col)
        self.full_btn.get_child().set_label(I_FULL_OFF)
        key = Gtk.EventControllerKey(propagation_phase=Gtk.PropagationPhase.CAPTURE)

        def on_key(c, kv, code, st):
            if kv == Gdk.KEY_Escape and not self.searchbar.get_visible():
                win.close()
                return True
            if st & plat.primary_mask() and kv in (Gdk.KEY_f, Gdk.KEY_F):
                self.open_search()
                return True
            if kv == Gdk.KEY_F11:
                win.close()
                return True
            if kv in (Gdk.KEY_Page_Down, Gdk.KEY_Right) and not self.search_entry.has_focus():
                self.goto_page(self.current_page() + (2 if self.spread else 1))
                return True
            if kv in (Gdk.KEY_Page_Up, Gdk.KEY_Left) and not self.search_entry.has_focus():
                self.goto_page(self.current_page() - (2 if self.spread else 1))
                return True
            return False
        key.connect("key-pressed", on_key)
        win.add_controller(key)
        win.connect("notify::default-width", lambda *_: self._fs_resized())
        win.connect("close-request", lambda *_: (self._leave_full(), False)[1])
        self.apply_dark_css()
        win.fullscreen()
        win.present()
        self.connect_chip(self.fs_scroll)
        self.fs_w = 1200
        GLib.timeout_add(250, self._fs_resized)

    def _fs_resized(self):
        if self.fs is None:
            return False
        w = self.fs.get_width() or self.fs.get_default_size()[0]
        if w > 100 and abs(w - self.fs_w) > 8:
            self.fs_w = w - 28
            self.layout_pages()
            self.sharpen_soon()
        return False

    def _leave_full(self):
        if self.fs is None:
            return
        cur = self.current_page()
        win, self.fs = self.fs, None
        self.fs_vp.set_child(None)
        self.fs_scroll.set_child(None)
        self.holder.remove(self.fs_scroll)
        self.holder.append(self.ov)
        self.holder.set_vexpand(False)
        for f in (self.view_col.set_margin_start, self.view_col.set_margin_end, self.view_col.set_margin_top,
                  self.view_col.set_margin_bottom):
            f(0)
        par = self.view_col.get_parent()               # (glass.py setzt das Kind in einen Overlay)
        if par is not None:
            par.set_child(None) if hasattr(par, "set_child") else par.remove(self.view_col)
        self.append(self.view_col)
        self.full_btn.get_child().set_label(I_FULL)
        self.layout_pages()
        self.sharpen_soon()
        self.connect_chip(self.writer.scroll)
        GLib.timeout_add(150, lambda: (self.writer.invalidate(), self.goto_page(cur, animate=False), False)[-1])

    def open_scourge(self):
        if not open_in_scourge(self.path()):
            self.toast("scourge-pdf lässt sich nicht starten")

    def save_as(self):
        dlg = Gtk.FileDialog(title="PDF speichern", initial_name=self.info["name"])

        def done(d, res):
            try:
                gf = d.save_finish(res)
                shutil.copyfile(self.path(), gf.get_path())
                self.toast(f"Gespeichert: {gf.get_basename()}")
            except (GLib.Error, OSError):
                pass
        dlg.save(self.writer.win, None, done)

    def ask_remove(self):
        ask_dialog(self.writer.win, "PDF entfernen?",
                   i18n.tr("Die PDF „%s“ wird aus dem Dokument entfernt. Du kannst das mit Strg+Z rückgängig machen.") % self.info["name"],
                   "Entfernen", lambda: self.writer.remove_block(self), danger=True)

    def rename(self):
        def ok(name):
            name = name.strip().replace("/", "_")
            if not name:
                return
            if not name.lower().endswith(".pdf"):
                name += ".pdf"
            if name != self.info["name"]:
                self.writer.checkpoint()
                self.info["name"] = name
                self.title.set_label("󰈦 " + name)
                self.writer.changed()
        ask_dialog(self.writer.win, "PDF umbenennen", "", "Umbenennen", ok, entry=self.info["name"])

    def set_width(self, w):
        old = self.base_w()
        self.width = int(w)
        self.set_size_request(max(240, self.eff_w()), -1)
        if self.plist and self.base_w() != old:
            self.layout_pages()
            self.sharpen_soon()


def ask_dialog(parent, title, msg, ok_label, on_ok, danger=False, entry=None):
    """Kleiner Suite-Dialog: Abbrechen / Bestätigen, optional mit Textfeld (on_ok bekommt dann den Text)."""
    win = Gtk.Window(title=i18n.tr(title), transient_for=parent, modal=True, resizable=False, default_width=420)
    win.add_css_class("settings")
    col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, margin_start=16, margin_end=16,
                  margin_top=6, margin_bottom=16)
    if msg:
        col.append(Gtk.Label(label=msg, xalign=0, wrap=True, max_width_chars=48))
    ent = None
    if entry is not None:
        ent = Gtk.Entry(text=entry, hexpand=True)
        col.append(ent)
    row = Gtk.Box(spacing=8, halign=Gtk.Align.END, margin_top=6)
    cancel = Gtk.Button(label=i18n.tr("Abbrechen"), focus_on_click=False)
    ok = Gtk.Button(label=i18n.tr(ok_label), focus_on_click=False)
    for b in (cancel, ok):
        b.add_css_class("pb"); b.add_css_class("small")
        b.set_cursor_from_name("pointer")
    if danger:
        ok.add_css_class("danger")
    cancel.connect("clicked", lambda *_: win.close())

    def go(*_):
        win.close()
        on_ok(ent.get_text() if ent is not None else None) if ent is not None else on_ok()
    ok.connect("clicked", go)
    if ent is not None:
        ent.connect("activate", go)
    row.append(cancel)
    row.append(ok)
    col.append(row)
    dialogs.chrome(win, title, col)
    win.present()
    if ent is not None:
        ent.grab_focus()
        ent.select_region(0, -1)
    else:
        cancel.grab_focus()


def ask_trash_original(parent, src, on_trash):
    """Suite-Dialog nach dem Einfügen: Original in den Papierkorb? Wegklicken, Esc, ✕ oder Fokusverlust = behalten."""
    win = Gtk.Window(title="Original löschen?", transient_for=parent, modal=True, resizable=False,
                     default_width=460)
    win.add_css_class("settings")
    col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, margin_start=16, margin_end=16,
                  margin_top=6, margin_bottom=16)
    short = src.replace(os.path.expanduser("~"), "~", 1)
    msg = Gtk.Label(label=i18n.tr("Die PDF liegt jetzt im notist-Ordner. Die Datei im ursprünglichen Ordner in den "
                                  "Papierkorb legen, damit sie nicht doppelt vorhanden ist?"),
                    xalign=0, wrap=True, max_width_chars=48)
    path = Gtk.Label(label=short, xalign=0, ellipsize=1)
    path.add_css_class("wpdf-sub")
    col.append(msg)
    col.append(path)
    row = Gtk.Box(spacing=8, halign=Gtk.Align.END, margin_top=6)
    keep = Gtk.Button(label=i18n.tr("Original behalten"), focus_on_click=False)
    trash = Gtk.Button(label=i18n.tr("Original in den Papierkorb"), focus_on_click=False)
    for b in (keep, trash):
        b.add_css_class("pb"); b.add_css_class("small")
        b.set_cursor_from_name("pointer")
    trash.add_css_class("danger")
    keep.connect("clicked", lambda *_: win.close())
    state = {"seen": False}

    def do_trash(*_):
        state["seen"] = False
        win.close()
        on_trash()
    trash.connect("clicked", do_trash)
    row.append(keep)
    row.append(trash)
    col.append(row)
    dialogs.chrome(win, "Original löschen?", col)

    def active(w, _p):                    # Wegklicken (anderes Fenster/Außenbereich) = behalten
        if w.is_active():
            state["seen"] = True
        elif state["seen"]:
            w.close()
    win.connect("notify::is-active", active)
    win.present()
    keep.grab_focus()
