# Seitensatz für den Dokument-Modus: verteilt die Blöcke aus docfmt auf A4-Seiten und zeichnet sie mit
# Pango/Cairo. Dieselben Seiten gehen in die PDF-Ausgabe und an den Drucker (Gtk.PrintOperation).
import base64, html

import cairo
import gi
gi.require_version("Pango", "1.0")
gi.require_version("PangoCairo", "1.0")
gi.require_version("GdkPixbuf", "2.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, GdkPixbuf, GLib, Pango, PangoCairo

import docfmt as df

PAGE_W, PAGE_H = 595.28, 841.89          # A4 in pt (Standard; tatsächlich aus den Seiteneinstellungen)
MARGIN = 70.87                           # 2,5 cm
MM = 72 / 25.4
FN_SIZE = 9                              # Fußnoten (pt)
PARA_AFTER = 8.0
LIST_STEP = 18.0                         # Einzug je Ebene (pt)
BEFORE = {"title": 0, "h1": 14, "h2": 10, "h3": 8}


def span(r):
    t = html.escape(r.get("text", ""))
    a = []
    if r.get("b"):
        a.append('weight="bold"')
    if r.get("i"):
        a.append('style="italic"')
    if r.get("u") or r.get("link"):
        a.append('underline="single"')
    if r.get("s"):
        a.append('strikethrough="true"')
    if r.get("font"):
        a.append(f'font_family="{html.escape(r["font"])}"')
    if r.get("size"):
        a.append(f'size="{round(float(r["size"]) * 1024)}"')
    if r.get("color"):
        a.append(f'foreground="{r["color"]}"')
    elif r.get("link"):
        a.append('foreground="#0563c1"')
    if r.get("hl"):
        a.append(f'background="{r["hl"]}"')
    if r.get("va") == "sup":
        a.append('baseline_shift="superscript" font_scale="superscript"')
    elif r.get("va") == "sub":
        a.append('baseline_shift="subscript" font_scale="subscript"')
    return f"<span {' '.join(a)}>{t}</span>" if a else t


class Paginator:
    def __init__(self, blocks, page=None, title="", toc_pages=None):
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 4, 4)
        self.cr = cairo.Context(surf)
        self.pctx = PangoCairo.create_context(self.cr)
        PangoCairo.context_set_resolution(self.pctx, 72)    # 1 Einheit = 1 pt
        self.page_cfg = df.norm_page(page)
        w, h, (t, r, b, l) = df.page_mm(self.page_cfg)
        self.pw, self.ph = w * MM, h * MM
        self.mt, self.mr, self.mb, self.ml = t * MM, r * MM, b * MM, l * MM
        self.title = title
        self.pages = [[]]
        self.y = self.mt
        self.blocks = blocks
        self.fn_n = 0                 # Fußnoten fortlaufend
        self.fn_page = []             # Fußnoten der aktuellen Seite: [(nummer, layout)]
        self.fn_h = 0.0
        self.toc_pages = toc_pages    # {block-index: seite} aus dem ersten Durchlauf
        self.head_pages = {}          # block-index → seite (für das Inhaltsverzeichnis)

    # ----- Hilfen -----
    @property
    def bottom(self):
        return self.ph - self.mb - self.fn_h

    @property
    def body_w(self):
        return self.pw - self.ml - self.mr

    def new_page(self):
        self.flush_footnotes()
        self.pages.append([])
        self.y = self.mt

    def flush_footnotes(self):
        if not self.fn_page:
            return
        y = self.ph - self.mb - self.fn_h + 6
        self.op("fnsep", self.ml, y - 3, min(140, self.body_w * 0.4))
        for num, lay in self.fn_page:
            self.op("layout", lay, self.ml, y)
            y += lay.get_pixel_extents()[1].height + 2
        self.fn_page, self.fn_h = [], 0.0

    def footnote_layout(self, num, text):
        lay = self.layout(f"<sup>{num}</sup> {html.escape(text)}", self.body_w, font_size=FN_SIZE, spacing=1.0)
        return lay

    def op(self, *a):
        self.pages[-1].append(a)

    def layout(self, markup, width, style="normal", align="left", spacing=1.15, font_size=None):
        lay = Pango.Layout.new(self.pctx)
        size, bold, italic = df.STYLE_FMT.get(style, df.STYLE_FMT["normal"])
        fam = df.MONO_FONT if style == "code" else df.BASE_FONT
        fd = Pango.FontDescription.from_string(f"{fam} {font_size or size}")
        if bold:
            fd.set_weight(Pango.Weight.BOLD)
        if italic:
            fd.set_style(Pango.Style.ITALIC)
        lay.set_font_description(fd)
        lay.set_width(round(width * Pango.SCALE))
        lay.set_wrap(Pango.WrapMode.WORD_CHAR)
        lay.set_alignment({"center": Pango.Alignment.CENTER, "right": Pango.Alignment.RIGHT}.get(
            align, Pango.Alignment.LEFT))
        lay.set_justify(align == "justify")
        lay.set_line_spacing(spacing)
        tabs = Pango.TabArray.new(1, True)
        tabs.set_tab(0, Pango.TabAlign.LEFT, 36)
        lay.set_tabs(tabs)
        lay.set_markup(markup or " ", -1)
        return lay

    def place_layout(self, lay, x, color=(0, 0, 0), bg=None, bar=False, marker=None, fns=(), heading=None):
        """Zeilenweise setzen, bei Bedarf über Seitengrenzen umbrechen. fns: [(byte-index, nummer, text)] –
        Fußnoten landen unten auf der Seite, auf der ihre Nummer steht."""
        it = lay.get_iter()
        first = True
        fns = list(fns)
        while True:
            line = it.get_line_readonly()
            ink, log = it.get_line_extents()
            top = log.y / Pango.SCALE
            h = log.height / Pango.SCALE
            baseline = it.get_baseline() / Pango.SCALE
            mine = [f for f in fns if line.start_index <= f[0] < line.start_index + max(1, line.length)]
            new = [(num, self.footnote_layout(num, text)) for _, num, text in mine]
            extra = sum(l.get_pixel_extents()[1].height + 2 for _, l in new) + (8 if new and not self.fn_page else 0)
            if first:
                origin = top
                if self.y + h > self.bottom - extra and self.y > self.mt:
                    self.new_page()
                    extra = sum(l.get_pixel_extents()[1].height + 2 for _, l in new) + (8 if new else 0)
                start_y = self.y
            elif start_y + (top - origin) + h > self.bottom - extra:
                self.new_page()
                extra = sum(l.get_pixel_extents()[1].height + 2 for _, l in new) + (8 if new else 0)
                start_y = self.y - (top - origin)
            if new:
                self.fn_page += new
                self.fn_h += extra
                fns = [f for f in fns if f not in mine]
            if first and heading is not None:
                self.head_pages[heading] = len(self.pages)
            ly = start_y + (top - origin)
            if bg:
                self.op("rect", self.ml - 4, ly, self.body_w + 8, h, bg)
            if bar:
                self.op("rect", x - 10, ly, 2.5, h, (0.65, 0.65, 0.65))
            if first and marker:
                self.op("text", marker, x - LIST_STEP + 2, start_y + baseline - origin, lay)
            self.op("line", line, x + log.x / Pango.SCALE, start_y + baseline - origin, color, lay)
            self.y = ly + h
            first = False
            if not it.next_line():
                break

    # ----- Blöcke -----
    def paragraph(self, b, marker=None, index=None):
        style = b.get("style", "normal")
        indent = b.get("indent", 0) * LIST_STEP + (LIST_STEP if b.get("list") else 0)
        if style == "quote":
            indent += 24
        x = self.ml + indent
        width = self.body_w - indent
        if self.y > self.mt:
            self.y += BEFORE.get(style, 0)
        seg = []
        heading = index if style in ("h1", "h2", "h3") else None

        def flush_text():
            nonlocal marker, heading
            if not seg and marker is None and any(r.get("img") for r in b["runs"]):
                return
            parts, fns, nbytes = [], [], 0
            for r in seg:
                if r.get("fn") is not None:
                    self.fn_n += 1
                    fns.append((nbytes, self.fn_n, r["fn"]))
                    parts.append(f"<sup>{self.fn_n}</sup>")
                    nbytes += len(str(self.fn_n).encode())
                else:
                    parts.append(span(r))
                    nbytes += len(r.get("text", "").encode())
            markup = "".join(parts)
            lay = self.layout(markup, width, style, b.get("align", "left"), b.get("spacing", 1.15))
            color = (0.35, 0.35, 0.35) if style == "quote" else (0, 0, 0)
            self.place_layout(lay, x, color, bg=(0.95, 0.95, 0.95) if style == "code" else None,
                              bar=style == "quote", marker=marker, fns=fns, heading=heading)
            heading = None
            marker = None
            seg.clear()
        for r in b["runs"]:
            if r.get("img"):
                if seg:
                    flush_text()
                self.image(r, x, width, b.get("align", "left"))
            else:
                seg.append(r)
        if seg or not any(r.get("img") for r in b["runs"]):
            flush_text()
        self.y += 0 if style == "code" else PARA_AFTER

    def image(self, r, x, width, align):
        try:
            loader = GdkPixbuf.PixbufLoader()
            loader.write(base64.b64decode(r["img"]))
            loader.close()
            pb = loader.get_pixbuf()
        except GLib.Error:
            return
        w = (r.get("w") or pb.get_width()) * 0.75
        h = (r.get("h") or pb.get_height()) * 0.75
        if w > width:
            h, w = h * width / w, width
        maxh = self.ph - self.mt - self.mb
        if h > maxh:
            w, h = w * maxh / h, maxh
        if self.y + h > self.bottom:
            self.new_page()
        ix = x + {"center": (width - w) / 2, "right": width - w}.get(align, 0)
        self.op("image", pb, ix, self.y, w, h)
        self.y += h + 4

    def table(self, b):
        rows = b["rows"] or [[""]]
        ncol = max(len(r) for r in rows)
        st = df.table_style(b)
        fr = df.table_widths(st, ncol)
        width = self.body_w
        cws = [width * f for f in fr]
        xs = [self.ml + sum(cws[:c]) for c in range(ncol)]
        pad = {"compact": 2, "normal": 4, "wide": 7}[st["pad"]]
        sides = df.table_border_sides(st)
        bcol = df.hex_rgb(st["accent"]) if st["accent"] else (0.5, 0.5, 0.5)
        lw = 0.9 if st["border"] in ("rows", "outer") else 0.6
        top = self.y
        for ri, row in enumerate(rows):
            lays, looks = [], []
            for c in range(ncol):
                fill, fg, bold = df.table_cell_look(st, ri, c)
                txt = html.escape(row[c] if c < len(row) else "")
                if bold and txt:
                    txt = f"<b>{txt}</b>"
                lays.append(self.layout(txt, cws[c] - 2 * pad, font_size=10, spacing=1.0,
                                        align=df.table_align(st, c)))
                looks.append((fill, fg))
            h = max(l.get_pixel_extents()[1].height for l in lays) + 2 * pad
            if self.y + h > self.bottom and self.y > self.mt:
                if "bottom" in sides and self.y > top:
                    self.op("seg", self.ml, self.y, self.ml + width, self.y, bcol, lw)
                self.new_page()
                top = self.y
                if "top" in sides:
                    self.op("seg", self.ml, self.y, self.ml + width, self.y, bcol, lw)
            if ri == 0 and "top" in sides:
                self.op("seg", self.ml, self.y, self.ml + width, self.y, bcol, lw)
            for c, lay in enumerate(lays):
                fill, fg = looks[c]
                if fill:
                    self.op("rect", xs[c], self.y, cws[c], h, df.hex_rgb("#" + fill))
                self.op("clayout", lay, xs[c] + pad, self.y + pad, df.hex_rgb("#" + fg) if fg else (0, 0, 0))
                if "insideV" in sides and c < ncol - 1:
                    self.op("seg", xs[c] + cws[c], self.y, xs[c] + cws[c], self.y + h, bcol, lw)
            if "left" in sides:
                self.op("seg", self.ml, self.y, self.ml, self.y + h, bcol, lw)
            if "right" in sides:
                self.op("seg", self.ml + width, self.y, self.ml + width, self.y + h, bcol, lw)
            self.y += h
            last = ri == len(rows) - 1
            if (not last and "insideH" in sides) or (last and "bottom" in sides):
                self.op("seg", self.ml, self.y, self.ml + width, self.y, bcol, lw)
        self.y += PARA_AFTER

    def run(self):
        nums = df.list_numbers(self.blocks)
        bullets = "•◦▪"
        for i, b in enumerate(self.blocks):
            if b["t"] == "p":
                marker = None
                if b.get("list") == "bullet":
                    marker = bullets[b.get("indent", 0) % 3]
                elif b.get("list") == "number":
                    marker = f"{nums.get(i, 1)}."
                self.paragraph(b, marker, i)
            elif b["t"] == "table":
                self.table(b)
            elif b["t"] == "hr":
                if self.y + 12 > self.bottom:
                    self.new_page()
                self.op("hr", self.ml, self.y + 6, self.pw - self.mr)
                self.y += 12 + PARA_AFTER
            elif b["t"] == "pb":
                self.new_page()
            elif b["t"] == "toc":
                self.toc()
        self.flush_footnotes()
        self.decorate()
        return self.pages

    def toc(self):
        """Inhaltsverzeichnis: Einträge mit Pünktchen und Seitenzahl (Zahlen aus dem ersten Durchlauf)."""
        self.paragraph(df.para(df.tr("Inhaltsverzeichnis"), style="h2"))
        for level, text, idx in df.headings(self.blocks):
            num = str(self.toc_pages.get(idx, "")) if self.toc_pages else ""
            indent = (level - 1) * 14
            lay = self.layout(("<b>%s</b>" if level == 1 else "%s") % html.escape(text), self.body_w - indent - 30,
                              font_size=11, spacing=1.15)
            h = lay.get_pixel_extents()[1].height
            if self.y + h > self.bottom:
                self.new_page()
            self.op("layout", lay, self.ml + indent, self.y)
            last = lay.get_line_readonly(lay.get_line_count() - 1)
            ink, logical = last.get_pixel_extents()
            nlay = self.layout(num, 30, font_size=11, align="right", spacing=1.0)
            base_y = self.y + h - nlay.get_pixel_extents()[1].height
            self.op("dots", self.ml + indent + logical.width + 4, self.pw - self.mr - 30, base_y + 10)
            self.op("layout", nlay, self.pw - self.mr - 30, base_y)
            self.y += h + 3
        self.y += PARA_AFTER

    def decorate(self):
        """Kopf-/Fußzeile und Seitenzahlen auf jede Seite."""
        cfg, total = self.page_cfg, len(self.pages)
        for i, ops in enumerate(self.pages):
            n = i + 1
            head = df.fill_fields(cfg.get("header", ""), n, total, self.title)
            foot = df.fill_fields(cfg.get("footer", ""), n, total, self.title)
            num = df.page_number_text(cfg, n, total) if cfg["numbers"] != "none" and n >= int(cfg.get("num_from", 1)) else ""
            y_head, y_foot = self.mt / 2, self.ph - self.mb / 2

            def put(text, y_mid, align):
                if not text:
                    return
                lay = self.layout(html.escape(text), self.body_w, font_size=9, align=align, spacing=1.0)
                ops.append(("decor", lay, self.ml, y_mid - lay.get_pixel_extents()[1].height / 2))
            put(head, y_head, "left")
            put(foot, y_foot, "left")
            if num:
                pos = cfg["numbers"]
                put(num, y_head if pos == "header-right" else y_foot,
                    {"footer-center": "center", "footer-left": "left"}.get(pos, "right"))


def paginate(blocks, page=None, title=""):
    """Zwei Durchläufe, falls ein Inhaltsverzeichnis Seitenzahlen braucht. → (Seiten, Paginator)."""
    p = Paginator(blocks, page, title)
    pages = p.run()
    if any(b["t"] == "toc" for b in blocks):
        first = p.head_pages
        p = Paginator(blocks, page, title, toc_pages=first)
        pages = p.run()
        if p.head_pages != first:           # Verzeichnis hat selbst Seiten verschoben → noch einmal
            p = Paginator(blocks, page, title, toc_pages=p.head_pages)
            pages = p.run()
    return pages, p


def heading_pages(blocks, page=None):
    """block-index → Seite (für das Inhaltsverzeichnis in DOCX/ODT)."""
    return paginate(blocks, page)[1].head_pages


def draw_page(cr, ops, scale=1.0):
    cr.save()
    cr.scale(scale, scale)
    for o in ops:
        kind = o[0]
        if kind == "line":
            _, line, x, y, color, _lay = o
            cr.set_source_rgb(*color)
            cr.move_to(x, y)
            PangoCairo.show_layout_line(cr, line)
        elif kind == "text":
            _, text, x, y, lay = o
            l2 = PangoCairo.create_layout(cr)
            PangoCairo.context_set_resolution(l2.get_context(), 72)
            l2.set_font_description(lay.get_font_description())
            l2.set_text(text, -1)
            cr.set_source_rgb(0, 0, 0)
            cr.move_to(x, y - l2.get_baseline() / Pango.SCALE)
            PangoCairo.show_layout(cr, l2)
        elif kind in ("layout", "decor"):
            _, lay, x, y = o
            cr.set_source_rgb(*((0.35, 0.35, 0.35) if kind == "decor" else (0, 0, 0)))
            cr.move_to(x, y)
            PangoCairo.show_layout(cr, lay)
        elif kind == "rect":
            _, x, y, w, h, color = o
            cr.set_source_rgb(*color)
            cr.rectangle(x, y, w, h)
            cr.fill()
        elif kind == "seg":
            _, x0, y0, x1, y1, color, lw = o
            cr.set_source_rgb(*color)
            cr.set_line_width(lw)
            cr.move_to(x0, y0)
            cr.line_to(x1, y1)
            cr.stroke()
        elif kind == "clayout":
            _, lay, x, y, color = o
            cr.set_source_rgb(*color)
            cr.move_to(x, y)
            PangoCairo.show_layout(cr, lay)
        elif kind == "frame":
            _, x, y, w, h = o
            cr.set_source_rgb(0.5, 0.5, 0.5)
            cr.set_line_width(0.6)
            cr.rectangle(x, y, w, h)
            cr.stroke()
        elif kind == "hr":
            _, x0, y, x1 = o
            cr.set_source_rgb(0.5, 0.5, 0.5)
            cr.set_line_width(0.8)
            cr.move_to(x0, y)
            cr.line_to(x1, y)
            cr.stroke()
        elif kind == "fnsep":
            _, x, y, w = o
            cr.set_source_rgb(0.3, 0.3, 0.3)
            cr.set_line_width(0.5)
            cr.move_to(x, y)
            cr.line_to(x + w, y)
            cr.stroke()
        elif kind == "dots":
            _, x0, x1, y = o
            cr.set_source_rgb(0.45, 0.45, 0.45)
            x = x0
            while x < x1 - 2:
                cr.arc(x, y, 0.55, 0, 6.2832)
                cr.fill()
                x += 3.5
        elif kind == "image":
            _, pb, x, y, w, h = o
            cr.save()
            cr.translate(x, y)
            cr.scale(w / pb.get_width(), h / pb.get_height())
            Gdk.cairo_set_source_pixbuf(cr, pb, 0, 0)
            cr.paint()
            cr.restore()
    cr.restore()


def write_pdf(blocks, path, title="", page=None):
    pages, p = paginate(blocks, page, title)
    surf = cairo.PDFSurface(path, p.pw, p.ph)
    if title:
        try:
            surf.set_metadata(cairo.PDF_METADATA_TITLE, title)
        except AttributeError:
            pass
    cr = cairo.Context(surf)
    for ops in pages:
        draw_page(cr, ops)
        cr.show_page()
    surf.finish()
    return len(pages)


def page_count(blocks, page=None):
    return len(paginate(blocks, page)[0])


def print_doc(blocks, parent, title="", page=None):
    """Druckdialog; die Seiten kommen aus demselben Satz wie das PDF."""
    from gi.repository import Gtk
    pages, p = paginate(blocks, page, title)
    op = Gtk.PrintOperation(job_name=title or "Dokument", n_pages=len(pages), unit=Gtk.Unit.POINTS,
                            embed_page_setup=True)
    setup = Gtk.PageSetup()
    cfg = df.norm_page(page)
    names = {"A4": Gtk.PAPER_NAME_A4, "A5": Gtk.PAPER_NAME_A5, "Letter": Gtk.PAPER_NAME_LETTER}
    setup.set_paper_size(Gtk.PaperSize.new(names.get(cfg["size"], Gtk.PAPER_NAME_A4)))
    setup.set_orientation(Gtk.PageOrientation.LANDSCAPE if cfg["orient"] == "landscape" else Gtk.PageOrientation.PORTRAIT)
    for side in ("top", "bottom", "left", "right"):
        getattr(setup, f"set_{side}_margin")(0, Gtk.Unit.POINTS)
    op.set_default_page_setup(setup)
    op.set_use_full_page(True)

    def draw(op, ctx, n):
        cr = ctx.get_cairo_context()
        s = min(ctx.get_width() / p.pw, ctx.get_height() / p.ph)
        draw_page(cr, pages[n], s)
    op.connect("draw-page", draw)
    return op.run(Gtk.PrintOperationAction.PRINT_DIALOG, parent)
