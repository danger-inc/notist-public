# Dokument-Modell für den Dokument-Modus von notist und Ein-/Ausgabe als DOCX, DOC, TXT, Markdown und HTML.
#
# Ein Dokument ist eine Liste von Blöcken:
#   {"t": "p", "style": "normal|title|h1|h2|h3|quote|code", "align": "left|center|right|justify",
#    "indent": 0.., "list": None|"bullet"|"number", "spacing": 1.15, "runs": [Lauf, ...]}
#   {"t": "table", "rows": [["Zelle", ...], ...]}        Zellen sind reiner Text (Zeilenumbrüche erlaubt)
#   {"t": "hr"}                                           waagerechte Linie
#   {"t": "pb"}                                           Seitenumbruch
# Ein Lauf ist {"text": ..., "b", "i", "u", "s": True, "va": "sup"|"sub", "font": Familie, "size": pt,
#   "color": "#rrggbb", "hl": "#rrggbb", "link": URL} oder ein Bild {"img": base64, "mime": ..., "w": px, "h": px}.
# DOCX wird ohne Fremdbibliothek gelesen und geschrieben (zip + XML), damit es überall läuft.
import base64, html, io, re, struct, zipfile
import xml.etree.ElementTree as ET

STYLES = ("normal", "title", "h1", "h2", "h3", "quote", "code")
STYLE_NAMES = {"normal": "Standard", "title": "Titel", "h1": "Überschrift 1", "h2": "Überschrift 2",
               "h3": "Überschrift 3", "quote": "Zitat", "code": "Code"}
# Schriftgröße (pt), fett, kursiv je Formatvorlage – gilt für Bearbeitung, PDF und DOCX gleichermaßen
STYLE_FMT = {"normal": (11, False, False), "title": (26, True, False), "h1": (20, True, False),
             "h2": (16, True, False), "h3": (13, True, False), "quote": (11, False, True), "code": (10, False, False)}
BASE_FONT = "Noto Sans"
MONO_FONT = "Noto Sans Mono"
RUN_KEYS = ("b", "i", "u", "s", "va", "font", "size", "color", "hl", "link", "cm", "tc")   # cm: Kommentar-Id, tc: ins|del


# ---------------------------------------------------------------- Seite
PAGE_SIZES = {"A4": (210.0, 297.0), "A5": (148.0, 210.0), "Letter": (215.9, 279.4)}       # mm, hochkant
NUM_POS = {"none": "Keine", "footer-center": "Unten mittig", "footer-right": "Unten rechts",
           "footer-left": "Unten links", "header-right": "Oben rechts"}
NUM_FMT = {"n": "1", "page": "Seite 1", "page-of": "Seite 1 von 3", "dash": "– 1 –"}
MARGIN_PRESETS = {"Normal": (25, 25, 25, 25), "Schmal": (12.7, 12.7, 12.7, 12.7), "Mittel": (25.4, 19.1, 25.4, 19.1),
                  "Breit": (25.4, 50.8, 25.4, 50.8), "Hausarbeit": (25, 35, 20, 25)}   # oben, rechts, unten, links


def page_defaults(margin_mm=25.0):
    m = float(margin_mm)
    return {"size": "A4", "orient": "portrait", "margins": [m, m, m, m], "header": "", "footer": "",
            "numbers": "none", "num_fmt": "n", "num_from": 1,
            "lnum": "off", "lnum_step": 1,            # Zeilennummern: off | continuous | page (je Seite neu)
            "watermark": "", "page_color": "", "border": False,
            "comments": {}, "author": "", "track": False}               # comments: {id: {text, author, time}}


def norm_page(p, margin_mm=25.0):
    out = page_defaults(margin_mm)
    if isinstance(p, dict):
        out.update({k: v for k, v in p.items() if k in out})
    if out["lnum"] not in ("off", "continuous", "page"):
        out["lnum"] = "off"
    try:
        out["lnum_step"] = max(1, min(99, int(out["lnum_step"])))
    except (TypeError, ValueError):
        out["lnum_step"] = 1
    out["watermark"] = str(out["watermark"] or "")[:60]
    out["page_color"] = out["page_color"] if re.fullmatch(r"#[0-9a-fA-F]{6}", str(out["page_color"] or "")) else ""
    out["border"] = bool(out["border"])
    cm = out["comments"] if isinstance(out["comments"], dict) else {}
    out["comments"] = {str(k): v for k, v in cm.items() if isinstance(v, dict)}
    out["author"] = str(out["author"] or "")[:60]
    out["track"] = bool(out["track"])
    if out["size"] not in PAGE_SIZES:
        out["size"] = "A4"
    m = list(out["margins"])[:4] + [25.0] * max(0, 4 - len(out["margins"]))
    out["margins"] = [max(0.0, min(80.0, float(x))) for x in m]
    return out


def page_mm(p):
    """(breite, höhe, (oben, rechts, unten, links)) in mm."""
    p = norm_page(p)
    w, h = PAGE_SIZES[p["size"]]
    if p["orient"] == "landscape":
        w, h = h, w
    return w, h, tuple(p["margins"])


def tr(s, *a):
    try:
        import i18n
        return i18n.tr(s, *a)
    except ImportError:
        return s.format(*a) if a else s


def page_number_text(p, n, total):
    fmt = norm_page(p)["num_fmt"]
    return {"n": f"{n}", "page": tr("Seite {}", n), "page-of": tr("Seite {} von {}", n, total),
            "dash": f"– {n} –"}.get(fmt, f"{n}")


def fill_fields(text, n, total, title=""):
    """Platzhalter in Kopf-/Fußzeile: {seite} {seiten} {titel} {datum}."""
    import datetime
    return (text.replace("{seite}", str(n)).replace("{seiten}", str(total)).replace("{titel}", title or "")
            .replace("{datum}", datetime.date.today().strftime("%d.%m.%Y")))


def headings(blocks):
    """[(ebene 1–3, text, block-index)] für Inhaltsverzeichnis und Navigation."""
    out = []
    for i, b in enumerate(blocks):
        if b["t"] == "p" and b.get("style") in ("h1", "h2", "h3"):
            t = "".join(r.get("text", "") for r in b["runs"]).strip()
            if t:
                out.append((int(b["style"][1]), t, i))
    return out


def para(text="", **kw):
    p = {"t": "p", "style": "normal", "align": "left", "indent": 0, "list": None, "spacing": 1.15, "runs": []}
    p.update(kw)
    if text:
        p["runs"].append({"text": text})
    return p


def plain_text(blocks):
    """Reiner Text – für Suche, Vorschau in der Liste und Wortzählung."""
    out = []
    for b in blocks:
        if b["t"] == "p":
            out.append("".join(r.get("text", "") for r in b["runs"]))
            out.extend(r["fn"] for r in b["runs"] if r.get("fn"))
        elif b["t"] == "table":
            out.extend("\t".join(row) for row in b["rows"])
    return "\n".join(out)


def has_content(blocks):
    return any(b["t"] in ("table", "hr", "toc") or (b["t"] == "p" and any(r.get("img") or r.get("text", "").strip()
                                                                       for r in b["runs"])) for b in blocks)


def merge_runs(runs):
    """Benachbarte Läufe mit gleicher Formatierung zusammenlegen."""
    out = []
    for r in runs:
        if not r.get("img") and not r.get("text") and r.get("fn") is None:
            continue
        if out and not r.get("img") and not out[-1].get("img") and "fn" not in r and "fn" not in out[-1] and \
                all(out[-1].get(k) == r.get(k) for k in RUN_KEYS):
            out[-1]["text"] += r["text"]
        else:
            out.append(dict(r))
    return out


def accept_all(blocks):
    """Alle nachverfolgten Änderungen annehmen (Gelöschtes weg) und Kommentar-Marken entfernen – für Ausgabeformate."""
    if not any(r.get("tc") or r.get("cm") for b in blocks if b["t"] == "p" for r in b["runs"]):
        return blocks
    out = []
    for b in blocks:
        if b["t"] != "p":
            out.append(b)
            continue
        runs = [{k: v for k, v in r.items() if k not in ("cm", "tc")} for r in b["runs"] if r.get("tc") != "del"]
        out.append({**b, "runs": merge_runs(runs)})
    return out


def list_numbers(blocks):
    """Nummer je Absatz für nummerierte Listen (zählt pro Einzugsebene, neu nach Unterbrechung)."""
    nums, counters = {}, {}
    for i, b in enumerate(blocks):
        if b["t"] == "p" and b.get("list") == "number":
            lvl = b.get("indent", 0)
            counters = {k: v for k, v in counters.items() if k <= lvl}
            counters[lvl] = counters.get(lvl, 0) + 1
            nums[i] = counters[lvl]
        elif b["t"] == "p" and b.get("list") == "bullet":
            lvl = b.get("indent", 0)
            counters = {k: v for k, v in counters.items() if k < lvl}
        else:
            counters = {}
    return nums


def image_size(data):
    """(Breite, Höhe) aus PNG/JPEG/GIF-Kopf, ohne Bildbibliothek."""
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return struct.unpack(">II", data[16:24])
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return struct.unpack("<HH", data[6:10])
    if data[:2] == b"\xff\xd8":
        i = 2
        while i < len(data) - 9:
            if data[i] != 0xFF:
                i += 1
                continue
            m = data[i + 1]
            if m in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                h, w = struct.unpack(">HH", data[i + 5:i + 9])
                return w, h
            i += 2 + struct.unpack(">H", data[i + 2:i + 4])[0]
    return 400, 300


def sniff_mime(data):
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:2] == b"\xff\xd8":
        return "image/jpeg"
    if data[:4] == b"GIF8":
        return "image/gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data[:2] == b"BM":
        return "image/bmp"
    return None


# =====================================================================
# DOCX schreiben
# =====================================================================
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
WP = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
PIC = "http://schemas.openxmlformats.org/drawingml/2006/picture"
REL_T = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/"
EMU_PX = 9525                     # 1 px (96 dpi) in EMU
STYLE_IDS = {"title": "Title", "h1": "Heading1", "h2": "Heading2", "h3": "Heading3", "quote": "Quote",
             "code": "Code"}
ALIGN_W = {"left": "left", "center": "center", "right": "right", "justify": "both"}
HIGHLIGHTS = {"yellow": "#ffff00", "green": "#00ff00", "cyan": "#00ffff", "magenta": "#ff00ff", "blue": "#0000ff",
              "red": "#ff0000", "darkBlue": "#000080", "darkCyan": "#008080", "darkGreen": "#008000",
              "darkMagenta": "#800080", "darkRed": "#800000", "darkYellow": "#808000", "darkGray": "#808080",
              "lightGray": "#c0c0c0", "black": "#000000", "white": "#ffffff"}
PAGE_W_TW, PAGE_H_TW, MARGIN_TW = 11906, 16838, 1417       # A4, 2,5 cm Rand (in twips)
CONTENT_W_PX = round((PAGE_W_TW - 2 * MARGIN_TW) / 15)     # 1 px = 15 twips


def esc(s):
    return html.escape(s, quote=True)


def _rpr(r):
    x = []
    if r.get("link"):
        x.append('<w:rStyle w:val="Hyperlink"/>')
    if r.get("font"):
        f = esc(r["font"])
        x.append(f'<w:rFonts w:ascii="{f}" w:hAnsi="{f}" w:cs="{f}" w:eastAsia="{f}"/>')
    if r.get("b"):
        x.append("<w:b/><w:bCs/>")
    if r.get("i"):
        x.append("<w:i/><w:iCs/>")
    if r.get("s"):
        x.append("<w:strike/>")
    if r.get("color"):
        x.append(f'<w:color w:val="{r["color"].lstrip("#").upper()}"/>')
    if r.get("size"):
        x.append(f'<w:sz w:val="{round(float(r["size"]) * 2)}"/><w:szCs w:val="{round(float(r["size"]) * 2)}"/>')
    if r.get("hl"):
        x.append(f'<w:shd w:val="clear" w:color="auto" w:fill="{r["hl"].lstrip("#").upper()}"/>')
    if r.get("u") and not r.get("link"):
        x.append('<w:u w:val="single"/>')
    if r.get("va") in ("sup", "sub"):
        x.append(f'<w:vertAlign w:val="{"superscript" if r["va"] == "sup" else "subscript"}"/>')
    if r.get("link") and not r.get("color"):
        x.append('<w:color w:val="0563C1"/>')
    return f"<w:rPr>{''.join(x)}</w:rPr>" if x else ""


def _now_iso():
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _text_runs(text, rpr):
    out = []
    for j, part in enumerate(text.split("\t")):
        if j:
            out.append(f"<w:r>{rpr}<w:tab/></w:r>")
        if part:
            out.append(f'<w:r>{rpr}<w:t xml:space="preserve">{esc(part)}</w:t></w:r>')
    return "".join(out)


# ---------------- Tabellen-Design ----------------
# b["style"] (nur Abweichungen vom Standard werden gespeichert):
#   head (Kopfzeile), first_col (erste Spalte betont), stripes (Streifen), border grid|rows|outer|none,
#   accent (Farbe "#rrggbb" oder None), pad compact|normal|wide, align [left|center|right je Spalte],
#   widths [Anteile je Spalte, Summe 1]
TABLE_DEFAULT = {"head": True, "first_col": False, "stripes": False, "border": "grid", "accent": None,
                 "pad": "normal", "align": [], "widths": []}
TABLE_ACCENTS = ("#4a78c2", "#3b8f94", "#5a9e4b", "#d9a520", "#e07b2e", "#c9534f", "#8461b8", "#6f7a85")
TABLE_BORDERS = ("grid", "rows", "outer", "none")
TABLE_PADS = {"compact": (20, 70), "normal": (50, 108), "wide": (110, 160)}       # twips oben/unten, links/rechts


def table_style(b):
    st = dict(TABLE_DEFAULT)
    st.update({k: v for k, v in (b.get("style") or {}).items() if k in TABLE_DEFAULT})
    if st["border"] not in TABLE_BORDERS:
        st["border"] = "grid"
    if st["pad"] not in TABLE_PADS:
        st["pad"] = "normal"
    return st


def table_style_min(st):
    """Nur die Abweichungen vom Standard (kleine Dateien, alte Dokumente bleiben gleich)."""
    out = {k: v for k, v in st.items() if k in TABLE_DEFAULT and v != TABLE_DEFAULT[k]}
    if out.get("align") and all(a in (None, "", "left") for a in out["align"]):
        out.pop("align")
    return out


def table_widths(st, ncol):
    w = [float(x) for x in (st.get("widths") or [])][:ncol]
    if len(w) != ncol or any(x <= 0 for x in w):
        return [1.0 / ncol] * ncol
    tot = sum(w)
    return [x / tot for x in w]


def table_align(st, c):
    a = st.get("align") or []
    return a[c] if c < len(a) and a[c] in ("left", "center", "right") else "left"


def hex_rgb(h):
    h = (h or "#808080").lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def tint(h, a):
    """Farbe h mit Weiß gemischt (a = Anteil der Farbe) als „rrggbb“."""
    r, g, b = hex_rgb(h)
    return "".join(f"{round((1 - a + a * x) * 255):02x}" for x in (r, g, b))


def table_cell_look(st, r, c):
    """(füllfarbe "rrggbb" | None, textfarbe "rrggbb" | None, fett) einer Zelle für Exporte."""
    acc = st.get("accent")
    if st["head"] and r == 0:
        return (acc.lstrip("#") if acc else "e8e8e8"), ("ffffff" if acc else None), True
    body_r = r - 1 if st["head"] else r
    fill = None
    if st["stripes"] and body_r % 2 == 1:
        fill = tint(acc or "#808080", 0.14)
    if st["first_col"] and c == 0:
        return fill or (tint(acc, 0.08) if acc else None), None, True
    return fill, None, False


def table_border_sides(st):
    """Welche Linien gezeichnet werden: Menge aus top/bottom/left/right/insideH/insideV."""
    return {"grid": {"top", "bottom", "left", "right", "insideH", "insideV"},
            "rows": {"top", "bottom", "insideH"}, "outer": {"top", "bottom", "left", "right"},
            "none": set()}[st["border"]]


class _DocxWriter:
    def __init__(self):
        self.rels = []        # (id, type, target, external)
        self.media = []       # (name, bytes)
        self.nums = []        # (numId, abstractId) – je Liste eine eigene Nummerierung (Neustart)
        self.img_n = 0
        self.footnotes = []   # Texte, Id = Position + 1
        self.toc_pages = {}   # block-index → Seite (aus render.py)
        self.blocks = []
        self.comments = {}    # id → {text, author, time}
        self.cm_used = []     # Kommentar-Ids in der Reihenfolge ihres Auftretens (Index = w:id)
        self.author = "notist"
        self.tc_n = 0

    def rel(self, typ, target, external=False):
        rid = f"rId{len(self.rels) + 10}"
        self.rels.append((rid, typ, target, external))
        return rid

    def image(self, r):
        data = base64.b64decode(r["img"])
        mime = r.get("mime") or sniff_mime(data) or "image/png"
        ext = {"image/jpeg": "jpeg", "image/gif": "gif", "image/bmp": "bmp", "image/webp": "png"}.get(mime, "png")
        if mime == "image/webp":
            ext = "webp"
        self.img_n += 1
        name = f"image{self.img_n}.{ext}"
        self.media.append((name, data))
        rid = self.rel("image", f"media/{name}")
        w = r.get("w") or image_size(data)[0]
        h = r.get("h") or image_size(data)[1]
        cx, cy = round(w * EMU_PX), round(h * EMU_PX)
        n = self.img_n
        graphic = (f'<wp:cNvGraphicFramePr><a:graphicFrameLocks noChangeAspect="1"/></wp:cNvGraphicFramePr>'
                   f'<a:graphic><a:graphicData uri="{PIC}"><pic:pic>'
                   f'<pic:nvPicPr><pic:cNvPr id="{n}" name="{name}"/><pic:cNvPicPr/></pic:nvPicPr>'
                   f'<pic:blipFill><a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
                   f'<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
                   f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr>'
                   f'</pic:pic></a:graphicData></a:graphic>')
        if r.get("fl") in ("front", "back"):               # schwebend: vor/hinter dem Text, ohne Umfluss
            back = r["fl"] == "back"
            hx, vy = round(r.get("dx", 0) * EMU_PX), round(r.get("dy", 0) * EMU_PX)
            return (f'<w:r><w:drawing><wp:anchor distT="0" distB="0" distL="0" distR="0" simplePos="0" '
                    f'relativeHeight="{n if not back else 0}" behindDoc="{1 if back else 0}" locked="0" '
                    f'layoutInCell="1" allowOverlap="1"><wp:simplePos x="0" y="0"/>'
                    f'<wp:positionH relativeFrom="character"><wp:posOffset>{hx}</wp:posOffset></wp:positionH>'
                    f'<wp:positionV relativeFrom="line"><wp:posOffset>{vy}</wp:posOffset></wp:positionV>'
                    f'<wp:extent cx="{cx}" cy="{cy}"/><wp:effectExtent l="0" t="0" r="0" b="0"/><wp:wrapNone/>'
                    f'<wp:docPr id="{n}" name="Bild {n}"/>{graphic}</wp:anchor></w:drawing></w:r>')
        return (f'<w:r><w:drawing><wp:inline distT="0" distB="0" distL="0" distR="0">'
                f'<wp:extent cx="{cx}" cy="{cy}"/><wp:docPr id="{n}" name="Bild {n}"/>{graphic}'
                f'</wp:inline></w:drawing></w:r>')

    def paragraph(self, b, num_id=None):
        ppr = []
        if b.get("style", "normal") in STYLE_IDS:
            ppr.append(f'<w:pStyle w:val="{STYLE_IDS[b["style"]]}"/>')
        if b.get("list"):
            ppr.append(f'<w:numPr><w:ilvl w:val="{min(8, b.get("indent", 0))}"/><w:numId w:val="{num_id}"/></w:numPr>')
        sp = b.get("spacing", 1.15)
        ppr.append(f'<w:spacing w:after="160" w:line="{round(sp * 240)}" w:lineRule="auto"/>')
        if b.get("indent") and not b.get("list"):
            ppr.append(f'<w:ind w:left="{720 * b["indent"]}"/>')
        if b.get("align", "left") != "left":
            ppr.append(f'<w:jc w:val="{ALIGN_W[b["align"]]}"/>')
        body = []
        if b.get("_bm") is not None:
            body.append(f'<w:bookmarkStart w:id="{b["_bm"]}" w:name="_Toc{b["_bm"]}"/><w:bookmarkEnd w:id="{b["_bm"]}"/>')
        open_cm = None

        def close_cm():
            nonlocal open_cm
            if open_cm is not None:
                n = self.cm_used.index(open_cm)
                body.append(f'<w:commentRangeEnd w:id="{n}"/><w:r><w:commentReference w:id="{n}"/></w:r>')
                open_cm = None
        stamp = _now_iso()
        for r in b["runs"]:
            cm = r.get("cm") if r.get("cm") in self.comments else None
            if cm != open_cm:
                close_cm()
                if cm:
                    if cm not in self.cm_used:
                        self.cm_used.append(cm)
                    body.append(f'<w:commentRangeStart w:id="{self.cm_used.index(cm)}"/>')
                    open_cm = cm
            if r.get("img"):
                body.append(self.image(r))
                continue
            if r.get("fn") is not None:
                self.footnotes.append(r["fn"])
                body.append(f'<w:r><w:rPr><w:rStyle w:val="FootnoteReference"/></w:rPr>'
                            f'<w:footnoteReference w:id="{len(self.footnotes)}"/></w:r>')
                continue
            rpr = _rpr(r)
            txt = _text_runs(r.get("text", ""), rpr)
            if r.get("link"):
                rid = self.rel("hyperlink", r["link"], external=True)
                txt = f'<w:hyperlink r:id="{rid}" w:history="1">{txt}</w:hyperlink>'
            if r.get("tc") in ("ins", "del"):
                self.tc_n += 1
                if r["tc"] == "del":
                    txt = txt.replace("<w:t ", "<w:delText ").replace("</w:t>", "</w:delText>")
                tag = r["tc"]
                txt = f'<w:{tag} w:id="{900 + self.tc_n}" w:author="{esc(self.author)}" w:date="{stamp}">{txt}</w:{tag}>'
            body.append(txt)
        close_cm()
        return f"<w:p><w:pPr>{''.join(ppr)}</w:pPr>{''.join(body)}</w:p>"

    def table(self, b):
        rows = b["rows"] or [[""]]
        ncol = max(len(r) for r in rows)
        st = table_style(b)
        fr = table_widths(st, ncol)
        total = CONTENT_W_PX * 15
        colw = [max(200, round(total * f)) for f in fr]
        grid = "".join(f'<w:gridCol w:w="{w}"/>' for w in colw)
        sides = table_border_sides(st)
        color = (st["accent"] or "#808080").lstrip("#")
        size = 8 if st["border"] in ("rows", "outer") else 4
        border = "".join((f'<w:{s} w:val="single" w:sz="{size}" w:space="0" w:color="{color}"/>' if s in sides
                           else f'<w:{s} w:val="nil"/>')
                          for s in ("top", "left", "bottom", "right", "insideH", "insideV"))
        tb, lr = TABLE_PADS[st["pad"]]
        mar = (f'<w:tblCellMar><w:top w:w="{tb}" w:type="dxa"/><w:left w:w="{lr}" w:type="dxa"/>'
               f'<w:bottom w:w="{tb}" w:type="dxa"/><w:right w:w="{lr}" w:type="dxa"/></w:tblCellMar>')
        look = (f'<w:tblLook w:val="0000" w:firstRow="{int(st["head"])}" w:firstColumn="{int(st["first_col"])}" '
                f'w:noHBand="{int(not st["stripes"])}" w:noVBand="1"/>')
        out = [f'<w:tbl><w:tblPr><w:tblW w:w="5000" w:type="pct"/><w:tblBorders>{border}</w:tblBorders>'
               f'<w:tblLayout w:type="fixed"/>{mar}{look}</w:tblPr><w:tblGrid>{grid}</w:tblGrid>']
        for r, row in enumerate(rows):
            out.append("<w:tr>" + ("<w:trPr><w:tblHeader/></w:trPr>" if st["head"] and r == 0 else ""))
            for c in range(ncol):
                cell = row[c] if c < len(row) else ""
                fill, fg, bold = table_cell_look(st, r, c)
                rpr = (("<w:b/>" if bold else "") + (f'<w:color w:val="{fg}"/>' if fg else ""))
                rpr = f"<w:rPr>{rpr}</w:rPr>" if rpr else ""
                jc = table_align(st, c)
                jc = f'<w:jc w:val="{ {"center": "center", "right": "right"}.get(jc, "left") }"/>'
                ps = "".join(f'<w:p><w:pPr><w:spacing w:after="0"/>{jc}</w:pPr>{_text_runs(line, rpr)}</w:p>'
                             for line in cell.split("\n"))
                shd = f'<w:shd w:val="clear" w:color="auto" w:fill="{fill}"/>' if fill else ""
                out.append(f'<w:tc><w:tcPr><w:tcW w:w="{colw[c]}" w:type="dxa"/>{shd}</w:tcPr>{ps}</w:tc>')
            out.append("</w:tr>")
        out.append("</w:tbl>")
        return "".join(out)

    def body(self, blocks):
        out, prev_list = [], None
        for i, b in enumerate(blocks):
            if b["t"] == "p":
                num_id = None
                if b.get("list"):
                    # zusammenhängende Liste derselben Art teilt sich eine Nummerierung
                    if not prev_list or prev_list[0] != b["list"]:
                        num_id = len(self.nums) + 1
                        self.nums.append((num_id, 0 if b["list"] == "bullet" else 1))
                        prev_list = (b["list"], num_id)
                    num_id = prev_list[1]
                else:
                    prev_list = None
                out.append(self.paragraph(b, num_id))
            else:
                prev_list = None
                if b["t"] == "table":
                    out.append(self.table(b))
                    nxt = blocks[i + 1]["t"] if i + 1 < len(blocks) else None
                    if nxt != "p":           # Word braucht zwischen/nach Tabellen einen Absatz
                        out.append("<w:p/>")
                elif b["t"] == "hr":
                    out.append('<w:p><w:pPr><w:pBdr><w:bottom w:val="single" w:sz="8" w:space="1" '
                               'w:color="808080"/></w:pBdr></w:pPr></w:p>')
                elif b["t"] == "pb":
                    out.append('<w:p><w:r><w:br w:type="page"/></w:r></w:p>')
                elif b["t"] == "toc":
                    out.append(self.toc())
        return "".join(out)

    def toc(self):
        """Word-Feld TOC mit vorberechneten Einträgen (Word/LibreOffice können es später aktualisieren)."""
        out = [f'<w:p><w:pPr><w:pStyle w:val="TOCHeading"/></w:pPr><w:r><w:t>{esc(tr("Inhaltsverzeichnis"))}</w:t></w:r></w:p>',
               '<w:p><w:pPr><w:pStyle w:val="TOC1"/><w:tabs><w:tab w:val="right" w:leader="dot" w:pos="9350"/></w:tabs>'
               '</w:pPr><w:r><w:fldChar w:fldCharType="begin"/></w:r><w:r><w:instrText xml:space="preserve"> TOC \\o "1-3" '
               '\\h \\z \\u </w:instrText></w:r><w:r><w:fldChar w:fldCharType="separate"/></w:r></w:p>']
        for level, text, idx in headings(self.blocks):
            page = self.toc_pages.get(idx, "")
            out.append(f'<w:p><w:pPr><w:pStyle w:val="TOC{level}"/><w:tabs><w:tab w:val="right" w:leader="dot" '
                       f'w:pos="9350"/></w:tabs></w:pPr><w:hyperlink w:anchor="_Toc{idx}" w:history="1">'
                       f'<w:r><w:t xml:space="preserve">{esc(text)}</w:t></w:r><w:r><w:tab/></w:r>'
                       f'<w:r><w:t>{page}</w:t></w:r></w:hyperlink></w:p>')
        out.append('<w:p><w:r><w:fldChar w:fldCharType="end"/></w:r></w:p>')
        return "".join(out)

    def comments_xml(self):
        out = []
        for n, cid in enumerate(self.cm_used):
            c = self.comments[cid]
            author = c.get("author") or self.author
            paras = "".join(f'<w:p><w:r><w:t xml:space="preserve">{esc(line)}</w:t></w:r></w:p>'
                            for line in (c.get("text") or "").split("\n"))
            date = c.get("time") or _now_iso()
            date = date[:19] + "Z" if len(date) >= 19 else date
            out.append(f'<w:comment w:id="{n}" w:author="{esc(author)}" w:date="{esc(date)}" '
                       f'w:initials="{esc(author[:2].upper())}">{paras}</w:comment>')
        return (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:comments xmlns:w="{W}" xmlns:r="{R}">'
                + "".join(out) + "</w:comments>")

    def footnotes_xml(self):
        notes = ['<w:footnote w:type="separator" w:id="-1"><w:p><w:pPr><w:spacing w:after="0" w:line="240" '
                 'w:lineRule="auto"/></w:pPr><w:r><w:separator/></w:r></w:p></w:footnote>',
                 '<w:footnote w:type="continuationSeparator" w:id="0"><w:p><w:pPr><w:spacing w:after="0" w:line="240" '
                 'w:lineRule="auto"/></w:pPr><w:r><w:continuationSeparator/></w:r></w:p></w:footnote>']
        for i, text in enumerate(self.footnotes, start=1):
            notes.append(f'<w:footnote w:id="{i}"><w:p><w:pPr><w:pStyle w:val="FootnoteText"/></w:pPr>'
                         f'<w:r><w:rPr><w:rStyle w:val="FootnoteReference"/></w:rPr><w:footnoteRef/></w:r>'
                         f'<w:r><w:t xml:space="preserve"> {esc(text)}</w:t></w:r></w:p></w:footnote>')
        return (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:footnotes xmlns:w="{W}" xmlns:r="{R}">'
                + "".join(notes) + "</w:footnotes>")


def _hf_xml(kind, text, num, align, title):
    """Kopf- (hdr) oder Fußzeile (ftr): Text links, Seitenzahl als Feld (PAGE/NUMPAGES)."""
    parts = []
    if text:
        # Platzhalter {seite}/{seiten} werden zu Feldern, {titel}/{datum} zu Text
        import datetime
        t = text.replace("{titel}", title or "").replace("{datum}", datetime.date.today().strftime("%d.%m.%Y"))
        for i, chunk in enumerate(re.split(r"(\{seiten?\})", t)):
            if chunk == "{seite}":
                parts.append('<w:fldSimple w:instr=" PAGE "><w:r><w:t>1</w:t></w:r></w:fldSimple>')
            elif chunk == "{seiten}":
                parts.append('<w:fldSimple w:instr=" NUMPAGES "><w:r><w:t>1</w:t></w:r></w:fldSimple>')
            elif chunk:
                parts.append(f'<w:r><w:t xml:space="preserve">{esc(chunk)}</w:t></w:r>')
    paras = []
    if parts:
        paras.append(f'<w:p><w:pPr><w:pStyle w:val="{"Header" if kind == "hdr" else "Footer"}"/></w:pPr>{"".join(parts)}</w:p>')
    if num:
        before, after = num
        jc = {"center": "center", "right": "right"}.get(align, "left")
        r = ""
        if before:
            r += f'<w:r><w:t xml:space="preserve">{esc(before)}</w:t></w:r>'
        r += '<w:fldSimple w:instr=" PAGE "><w:r><w:t>1</w:t></w:r></w:fldSimple>'
        if after == "of":
            r += (f'<w:r><w:t xml:space="preserve"> {esc(tr("von"))} </w:t></w:r>'
                  '<w:fldSimple w:instr=" NUMPAGES "><w:r><w:t>1</w:t></w:r></w:fldSimple>')
        elif after:
            r += f'<w:r><w:t xml:space="preserve">{esc(after)}</w:t></w:r>'
        paras.append(f'<w:p><w:pPr><w:pStyle w:val="{"Header" if kind == "hdr" else "Footer"}"/><w:jc w:val="{jc}"/></w:pPr>{r}</w:p>')
    if not paras:
        paras.append("<w:p/>")
    tag = "w:hdr" if kind == "hdr" else "w:ftr"
    return (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><{tag} xmlns:w="{W}" xmlns:r="{R}">'
            + "".join(paras) + f"</{tag}>")


def _styles_xml():
    def st(sid, name, size, bold=False, italic=False, extra_p="", extra_r="", font=None):
        r = f'<w:sz w:val="{size * 2}"/><w:szCs w:val="{size * 2}"/>'
        if bold:
            r += "<w:b/><w:bCs/>"
        if italic:
            r += "<w:i/><w:iCs/>"
        if font:
            r = f'<w:rFonts w:ascii="{font}" w:hAnsi="{font}" w:cs="{font}"/>' + r
        return (f'<w:style w:type="paragraph" w:styleId="{sid}"><w:name w:val="{name}"/>'
                f'<w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/>'
                f'<w:pPr><w:keepNext/>{extra_p}</w:pPr><w:rPr>{extra_r}{r}</w:rPr></w:style>')
    styles = [
        st("Title", "Title", 26, True, extra_p='<w:spacing w:after="240"/>'),
        st("Heading1", "heading 1", 20, True, extra_p='<w:spacing w:before="360" w:after="120"/><w:outlineLvl w:val="0"/>'),
        st("Heading2", "heading 2", 16, True, extra_p='<w:spacing w:before="240" w:after="120"/><w:outlineLvl w:val="1"/>'),
        st("Heading3", "heading 3", 13, True, extra_p='<w:spacing w:before="200" w:after="80"/><w:outlineLvl w:val="2"/>'),
        st("Quote", "Quote", 11, False, True, extra_p='<w:ind w:left="720" w:right="720"/>',
           extra_r='<w:color w:val="595959"/>'),
        st("Code", "Code", 10, font=MONO_FONT, extra_p='<w:shd w:val="clear" w:color="auto" w:fill="F2F2F2"/>'),
        st("FootnoteText", "footnote text", 9, extra_p='<w:spacing w:after="0" w:line="240" w:lineRule="auto"/>'),
        st("Header", "header", 9, extra_r='<w:color w:val="595959"/>'),
        st("Footer", "footer", 9, extra_r='<w:color w:val="595959"/>'),
        st("TOCHeading", "TOC Heading", 16, True, extra_p='<w:spacing w:before="240" w:after="120"/>'),
        st("TOC1", "toc 1", 11, True, extra_p='<w:spacing w:after="60"/>'),
        st("TOC2", "toc 2", 11, extra_p='<w:spacing w:after="60"/><w:ind w:left="220"/>'),
        st("TOC3", "toc 3", 11, extra_p='<w:spacing w:after="60"/><w:ind w:left="440"/>'),
    ]
    return (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<w:styles xmlns:w="{W}"><w:docDefaults><w:rPrDefault><w:rPr>'
            f'<w:rFonts w:ascii="{BASE_FONT}" w:hAnsi="{BASE_FONT}" w:cs="{BASE_FONT}" w:eastAsia="{BASE_FONT}"/>'
            f'<w:sz w:val="22"/><w:szCs w:val="22"/><w:lang w:val="de-DE"/></w:rPr></w:rPrDefault>'
            f'<w:pPrDefault><w:pPr><w:spacing w:after="160" w:line="276" w:lineRule="auto"/></w:pPr></w:pPrDefault>'
            f'</w:docDefaults><w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/>'
            f'<w:qFormat/></w:style>{"".join(styles)}'
            f'<w:style w:type="character" w:styleId="Hyperlink"><w:name w:val="Hyperlink"/>'
            f'<w:rPr><w:color w:val="0563C1"/><w:u w:val="single"/></w:rPr></w:style>'
            f'<w:style w:type="character" w:styleId="FootnoteReference"><w:name w:val="footnote reference"/>'
            f'<w:rPr><w:vertAlign w:val="superscript"/></w:rPr></w:style></w:styles>')


def _numbering_xml(nums):
    def abstract(aid, bullet):
        lv = []
        for l in range(9):
            if bullet:
                ch = "•◦▪"[l % 3]
                fmt = f'<w:numFmt w:val="bullet"/><w:lvlText w:val="{ch}"/>'
            else:
                kind = ("decimal", "lowerLetter", "lowerRoman")[l % 3]
                fmt = f'<w:numFmt w:val="{kind}"/><w:lvlText w:val="%{l + 1}."/>'
            lv.append(f'<w:lvl w:ilvl="{l}"><w:start w:val="1"/>{fmt}<w:lvlJc w:val="left"/>'
                      f'<w:pPr><w:ind w:left="{720 * (l + 1)}" w:hanging="360"/></w:pPr></w:lvl>')
        return f'<w:abstractNum w:abstractNumId="{aid}"><w:multiLevelType w:val="hybridMultilevel"/>{"".join(lv)}</w:abstractNum>'
    nx = "".join(f'<w:num w:numId="{n}"><w:abstractNumId w:val="{a}"/>'
                 + "".join(f'<w:lvlOverride w:ilvl="{l}"><w:startOverride w:val="1"/></w:lvlOverride>' for l in range(9))
                 + "</w:num>" for n, a in nums)
    return (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:numbering xmlns:w="{W}">'
            f'{abstract(0, True)}{abstract(1, False)}{nx}</w:numbering>')


def write_docx(blocks, path, title="", page=None):
    w = _DocxWriter()
    cfg = norm_page(page)
    if any(b["t"] == "toc" for b in blocks):
        blocks = [dict(b, _bm=i) if b["t"] == "p" and b.get("style") in ("h1", "h2", "h3") else b
                  for i, b in enumerate(blocks)]
        try:
            import render
            w.toc_pages = render.heading_pages(blocks, cfg)
        except Exception:  # noqa: BLE001 – ohne Seitenzahlen geht es auch
            w.toc_pages = {}
    w.blocks = blocks
    w.comments = cfg.get("comments") or {}
    w.author = cfg.get("author") or "notist"
    body = w.body(blocks)
    tw = 1440 / 25.4
    pw, ph, (mt, mr, mb, ml) = page_mm(cfg)
    orient = ' w:orient="landscape"' if cfg["orient"] == "landscape" else ""
    # Kopf-/Fußzeile + Seitenzahl
    pos = cfg["numbers"]
    num = None
    if pos != "none":
        num = {"n": ("", ""), "page": (tr("Seite") + " ", ""), "page-of": (tr("Seite") + " ", "of"),
               "dash": ("– ", " –")}[cfg["num_fmt"]]
    align = {"footer-center": "center", "footer-left": "left"}.get(pos, "right")
    head_num = num if pos == "header-right" else None
    foot_num = num if pos.startswith("footer") else None
    hf = []
    title_pg = num is not None and int(cfg.get("num_from", 1)) > 1
    if cfg["header"] or head_num:
        hf.append(("hdr", "header1.xml", _hf_xml("hdr", cfg["header"], head_num, align, title)))
    if cfg["footer"] or foot_num:
        hf.append(("ftr", "footer1.xml", _hf_xml("ftr", cfg["footer"], foot_num, align, title)))
    if title_pg and hf:          # erste Seite ohne Nummer, aber mit Kopf-/Fußtext
        if cfg["header"] or head_num:
            hf.append(("hdr", "header2.xml", _hf_xml("hdr", cfg["header"], None, align, title)))
        if cfg["footer"] or foot_num:
            hf.append(("ftr", "footer2.xml", _hf_xml("ftr", cfg["footer"], None, align, title)))
    refs = ""
    for kind, name, _xml in hf:
        rid = w.rel("header" if kind == "hdr" else "footer", name)
        typ = "first" if name.endswith("2.xml") else "default"
        refs += f'<w:{"headerReference" if kind == "hdr" else "footerReference"} w:type="{typ}" r:id="{rid}"/>'
    borders = ""
    if cfg.get("border"):
        borders = ('<w:pgBorders w:offsetFrom="page">' + "".join(
            f'<w:{side} w:val="single" w:sz="8" w:space="24" w:color="404040"/>' for side in ("top", "left", "bottom", "right")) +
            '</w:pgBorders>')
    lnum = ""
    if cfg.get("lnum", "off") != "off":
        lnum = (f'<w:lnNumType w:countBy="{int(cfg["lnum_step"])}" '
                f'w:restart="{"newPage" if cfg["lnum"] == "page" else "continuous"}"/>')
    sect = (f'<w:sectPr>{refs}<w:pgSz w:w="{round(pw * tw)}" w:h="{round(ph * tw)}"{orient}/><w:pgMar w:top="{round(mt * tw)}" '
            f'w:right="{round(mr * tw)}" w:bottom="{round(mb * tw)}" w:left="{round(ml * tw)}" w:header="708" w:footer="708" '
            f'w:gutter="0"/>{borders}{lnum}{"<w:titlePg/>" if title_pg else ""}</w:sectPr>')
    doc = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
           f'<w:document xmlns:w="{W}" xmlns:r="{R}" xmlns:wp="{WP}" xmlns:a="{A}" xmlns:pic="{PIC}">'
           f'<w:body>{body}{sect}</w:body></w:document>')
    rels = ['<Relationship Id="rId1" Type="' + REL_T + 'styles" Target="styles.xml"/>',
            '<Relationship Id="rId2" Type="' + REL_T + 'numbering" Target="numbering.xml"/>',
            '<Relationship Id="rId3" Type="' + REL_T + 'footnotes" Target="footnotes.xml"/>']
    if w.cm_used:
        rels.append('<Relationship Id="rId4" Type="' + REL_T + 'comments" Target="comments.xml"/>')
    for rid, typ, target, ext in w.rels:
        mode = ' TargetMode="External"' if ext else ""
        rels.append(f'<Relationship Id="{rid}" Type="{REL_T}{typ}" Target="{esc(target)}"{mode}/>')
    ctypes = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
              '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
              '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
              '<Default Extension="xml" ContentType="application/xml"/>'
              '<Default Extension="png" ContentType="image/png"/><Default Extension="jpeg" ContentType="image/jpeg"/>'
              '<Default Extension="gif" ContentType="image/gif"/><Default Extension="bmp" ContentType="image/bmp"/>'
              '<Default Extension="webp" ContentType="image/webp"/>'
              '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
              '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
              '<Override PartName="/word/numbering.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml"/>'
              '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
              '<Override PartName="/word/footnotes.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footnotes+xml"/>'
              + ('<Override PartName="/word/comments.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.comments+xml"/>'
                 if w.cm_used else "")
              + "".join(f'<Override PartName="/word/{name}" ContentType="application/vnd.openxmlformats-officedocument.'
                        f'wordprocessingml.{"header" if kind == "hdr" else "footer"}+xml"/>' for kind, name, _ in hf)
              + '</Types>')
    root_rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                 '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                 f'<Relationship Id="rId1" Type="{REL_T}officeDocument" Target="word/document.xml"/>'
                 '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
                 '</Relationships>')
    core = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/">'
            f'<dc:title>{esc(title)}</dc:title><dc:creator>notist</dc:creator></cp:coreProperties>')
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", ctypes)
        z.writestr("_rels/.rels", root_rels)
        z.writestr("docProps/core.xml", core)
        z.writestr("word/document.xml", doc)
        z.writestr("word/styles.xml", _styles_xml())
        z.writestr("word/numbering.xml", _numbering_xml(w.nums))
        z.writestr("word/footnotes.xml", w.footnotes_xml())
        if w.cm_used:
            z.writestr("word/comments.xml", w.comments_xml())
        for kind, name, xml in hf:
            z.writestr(f"word/{name}", xml)
        z.writestr("word/_rels/document.xml.rels",
                   '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   + "".join(rels) + "</Relationships>")
        for name, data in w.media:
            z.writestr(f"word/media/{name}", data, compress_type=zipfile.ZIP_STORED)   # PNG/JPEG sind schon komprimiert


# =====================================================================
# DOCX lesen
# =====================================================================
def _q(tag, ns=W):
    return f"{{{ns}}}{tag}"


def _val(el, default=None):
    return el.get(_q("val")) if el is not None and el.get(_q("val")) is not None else default


def _on(el):
    """Schalter wie <w:b/> oder <w:b w:val="false"/>."""
    return el is not None and _val(el, "1") not in ("0", "false", "off", "none")


class _DocxReader:
    def __init__(self, z):
        self.z = z
        self.rels = self._rels("word/_rels/document.xml.rels")
        self.styles = {}       # styleId -> (name, basedOn, rPr, pPr)
        self.default_size = 11
        self.num_fmt = {}      # (numId, ilvl) -> "bullet"/"number"
        self._load_styles()
        self._load_numbering()
        self.footnotes = {}
        fn = self._xml("word/footnotes.xml")
        if fn is not None:
            for f in fn.findall(_q("footnote")):
                if f.get(_q("type")) in ("separator", "continuationSeparator", "continuationNotice"):
                    continue
                self.footnotes[f.get(_q("id"))] = " ".join("".join(t.text or "" for t in p.iter(_q("t"))).strip()
                                                           for p in f.iter(_q("p"))).strip()
        # Kommentare: Word-Id → eigene Id (die Einträge landen in page["comments"])
        self.comments, self.cm_map, self._cm_active, self._tc, self._cm_seen = {}, {}, [], None, set()
        cm = self._xml("word/comments.xml")
        if cm is not None:
            import uuid
            for c in cm.findall(_q("comment")):
                wid = c.get(_q("id"))
                cid = self.cm_map[wid] = str(uuid.uuid4())
                text = "\n".join("".join(t.text or "" for t in p.iter(_q("t"))) for p in c.findall(_q("p")))
                self.comments[cid] = {"text": text.strip(), "author": c.get(_q("author"), ""),
                                      "time": (c.get(_q("date")) or "")[:19]}

    def page(self, body):
        """Seiteneinstellungen aus dem letzten sectPr (Format, Ränder, Kopf-/Fußzeile, Seitenzahl)."""
        pg = page_defaults()
        pg["comments"] = {k: v for k, v in self.comments.items() if k in self._cm_seen}
        sect = body.find(_q("sectPr")) if body is not None else None
        if sect is None:
            return pg
        tw = 25.4 / 1440
        sz = sect.find(_q("pgSz"))
        if sz is not None:
            try:
                w, h = int(sz.get(_q("w"))) * tw, int(sz.get(_q("h"))) * tw
                land = w > h or sz.get(_q("orient")) == "landscape"
                a, b = (min(w, h), max(w, h))
                pg["orient"] = "landscape" if land else "portrait"
                pg["size"] = min(PAGE_SIZES, key=lambda k: abs(PAGE_SIZES[k][0] - a) + abs(PAGE_SIZES[k][1] - b))
            except (TypeError, ValueError):
                pass
        mar = sect.find(_q("pgMar"))
        if mar is not None:
            try:
                pg["margins"] = [round(abs(int(mar.get(_q(k)))) * tw, 1) for k in ("top", "right", "bottom", "left")]
            except (TypeError, ValueError):
                pass
        ln = sect.find(_q("lnNumType"))
        if ln is not None:
            pg["lnum"] = "page" if ln.get(_q("restart")) == "newPage" else "continuous"
            try:
                pg["lnum_step"] = max(1, int(ln.get(_q("countBy"), "1")))
            except ValueError:
                pass
        pg["border"] = sect.find(_q("pgBorders")) is not None
        first_diff = sect.find(_q("titlePg")) is not None and _on(sect.find(_q("titlePg")))
        for ref_tag, key in (("headerReference", "header"), ("footerReference", "footer")):
            for ref in sect.findall(_q(ref_tag)):
                if ref.get(_q("type"), "default") != "default":
                    continue
                target = self.rels.get(ref.get(_q("id", R)), (None,))[0]
                part = self._xml("word/" + target) if target else None
                if part is None:
                    continue
                text, has_page, has_total, jc = [], False, False, "left"
                for p in part.iter(_q("p")):
                    j = p.find(f"{_q('pPr')}/{_q('jc')}")
                    pt = []
                    instr = " ".join((t.text or "") for t in p.iter(_q("instrText")))
                    instr += " ".join(f.get(_q("instr"), "") for f in p.iter(_q("fldSimple")))
                    if "NUMPAGES" in instr:
                        has_total = True
                    if re.search(r"\bPAGE\b", instr):
                        has_page = True
                        jc = _val(j, "left")
                        continue
                    pt = "".join(t.text or "" for t in p.iter(_q("t"))).strip()
                    if pt:
                        text.append(pt)
                pg[key] = " · ".join(text)
                if has_page:
                    pos = "header-right" if key == "header" else {"center": "footer-center", "right": "footer-right",
                                                                 "end": "footer-right"}.get(jc, "footer-left")
                    pg["numbers"] = pos
                    pg["num_fmt"] = "page-of" if has_total else "n"
                    pg["num_from"] = 2 if first_diff else 1
        return pg

    def _xml(self, name):
        try:
            return ET.fromstring(self.z.read(name))
        except (KeyError, ET.ParseError):
            return None

    def _rels(self, name):
        root = self._xml(name)
        out = {}
        if root is not None:
            for r in root:
                out[r.get("Id")] = (r.get("Target"), r.get("TargetMode") == "External")
        return out

    def _load_styles(self):
        root = self._xml("word/styles.xml")
        if root is None:
            return
        d = root.find(f"{_q('docDefaults')}/{_q('rPrDefault')}/{_q('rPr')}/{_q('sz')}")
        if d is not None and _val(d):
            self.default_size = int(_val(d)) / 2
        for s in root.findall(_q("style")):
            name = _val(s.find(_q("name")), "") or ""
            self.styles[s.get(_q("styleId"))] = (name.lower(), _val(s.find(_q("basedOn"))),
                                                 s.find(_q("rPr")), s.find(_q("pPr")))

    def _load_numbering(self):
        root = self._xml("word/numbering.xml")
        if root is None:
            return
        abstract = {}
        for a in root.findall(_q("abstractNum")):
            lv = {}
            for l in a.findall(_q("lvl")):
                lv[l.get(_q("ilvl"))] = "bullet" if _val(l.find(_q("numFmt"))) in ("bullet", "none") else "number"
            abstract[a.get(_q("abstractNumId"))] = lv
        for n in root.findall(_q("num")):
            lv = abstract.get(_val(n.find(_q("abstractNumId"))), {})
            for ilvl, fmt in lv.items():
                self.num_fmt[(n.get(_q("numId")), ilvl)] = fmt

    def style_kind(self, sid):
        seen = set()
        while sid and sid not in seen:
            seen.add(sid)
            name, based, _, _ = self.styles.get(sid, (sid.lower(), None, None, None))
            n = name.replace(" ", "")
            if n in ("title", "titel"):
                return "title"
            m = re.match(r"(heading|überschrift|berschrift)(\d)", n)
            if m:
                return {"1": "h1", "2": "h2"}.get(m.group(2), "h3")
            if "quote" in n or "zitat" in n:
                return "quote"
            if "code" in n or "preformatted" in n or "plaintext" in n:
                return "code"
            if re.match(r"(toc|verzeichnis|inhaltsverzeichnis)\d", n) or n in ("tocheading", "inhaltsverzeichnisüberschrift"):
                return "toc"
            if n.startswith("listbullet") or n.startswith("aufzählungszeichen"):
                return "list:bullet"
            if n.startswith("listnumber") or n.startswith("listennummer"):
                return "list:number"
            sid = based
        return "normal"

    def style_numpr(self, sid):
        seen = set()
        while sid and sid not in seen:
            seen.add(sid)
            _, based, _, ppr = self.styles.get(sid, ("", None, None, None))
            if ppr is not None and ppr.find(_q("numPr")) is not None:
                return ppr.find(_q("numPr"))
            sid = based
        return None

    def run_props(self, rpr, base=None):
        r = dict(base or {})
        if rpr is None:
            return r
        for key, tag in (("b", "b"), ("i", "i")):
            el = rpr.find(_q(tag))
            if el is not None:
                r[key] = _on(el) or None
        u = rpr.find(_q("u"))
        if u is not None:
            r["u"] = _val(u, "single") != "none" or None
        if _on(rpr.find(_q("strike"))) or _on(rpr.find(_q("dstrike"))):
            r["s"] = True
        va = _val(rpr.find(_q("vertAlign")))
        if va in ("superscript", "subscript"):
            r["va"] = "sup" if va == "superscript" else "sub"
        f = rpr.find(_q("rFonts"))
        if f is not None:
            fam = f.get(_q("ascii")) or f.get(_q("hAnsi")) or f.get(_q("cs"))
            if fam:
                r["font"] = fam
        sz = _val(rpr.find(_q("sz")))
        if sz and sz.isdigit():
            r["size"] = int(sz) / 2
        c = _val(rpr.find(_q("color")))
        if c and c.lower() != "auto" and re.fullmatch(r"[0-9a-fA-F]{6}", c):
            r["color"] = "#" + c.lower()
        hl = _val(rpr.find(_q("highlight")))
        if hl and hl in HIGHLIGHTS:
            r["hl"] = HIGHLIGHTS[hl]
        shd = rpr.find(_q("shd"))
        if shd is not None:
            fill = shd.get(_q("fill"))
            if fill and fill.lower() != "auto" and re.fullmatch(r"[0-9a-fA-F]{6}", fill):
                r["hl"] = "#" + fill.lower()
        return {k: v for k, v in r.items() if v is not None}

    def image(self, el):
        blip = el.find(f".//{{{A}}}blip")
        rid = blip.get(_q("embed", R)) if blip is not None else None
        if rid is None:
            im = el.find(".//{urn:schemas-microsoft-com:vml}imagedata")
            rid = im.get(_q("id", R)) if im is not None else None
        if rid not in self.rels:
            return None
        target = self.rels[rid][0]
        path = target.lstrip("/") if target.startswith("/") else "word/" + target
        try:
            data = self.z.read(path)
        except KeyError:
            return None
        mime = sniff_mime(data)
        if not mime:                  # EMF/WMF usw. kann GTK nicht anzeigen
            return None
        ext = el.find(f".//{{{WP}}}extent")
        if ext is not None:
            w, h = round(int(ext.get("cx")) / EMU_PX), round(int(ext.get("cy")) / EMU_PX)
        else:
            w, h = image_size(data)
        out = {"img": base64.b64encode(data).decode(), "mime": mime, "w": max(1, w), "h": max(1, h)}
        anc = el.find(f".//{{{WP}}}anchor")
        if anc is not None and anc.find(f"{{{WP}}}wrapNone") is not None:       # schwebend, ohne Textumfluss
            def off(name):
                v = anc.find(f"{{{WP}}}{name}/{{{WP}}}posOffset")
                try:
                    return round(int(v.text) / EMU_PX)
                except (AttributeError, TypeError, ValueError):
                    return 0
            out.update(fl="back" if anc.get("behindDoc") in ("1", "true") else "front", dx=off("positionH"),
                       dy=off("positionV"))
        return out

    def runs_of(self, el, base, link=None, out=None):
        """Läufe eines Absatzes; liefert Liste mit Läufen und dem Marker "PB" für Seitenumbrüche."""
        out = [] if out is None else out
        for c in el:
            tag = c.tag.split("}")[-1]
            if tag == "r":
                props = self.run_props(c.find(_q("rPr")), base)
                rs = c.find(_q("rPr"))
                if rs is not None and rs.find(_q("rStyle")) is not None:
                    st = self.styles.get(_val(rs.find(_q("rStyle"))))
                    if st:
                        props = self.run_props(rs, self.run_props(st[2], base))
                if self._cm_active:
                    props["cm"] = self._cm_active[-1]
                if self._tc:
                    props["tc"] = self._tc
                if link:
                    props["link"] = link
                    if props.get("color") == "#0563c1":   # Standard-Linkfarbe nicht als eigene Farbe merken
                        props.pop("color")
                    props.pop("u", None)                  # Links sind ohnehin unterstrichen
                for x in c:
                    xt = x.tag.split("}")[-1]
                    if xt in ("t", "delText"):
                        out.append({**props, "text": x.text or ""})
                    elif xt == "tab":
                        out.append({**props, "text": "\t"})
                    elif xt in ("br", "cr"):
                        out.append("PB" if x.get(_q("type")) == "page" else "BR")
                    elif xt == "noBreakHyphen":
                        out.append({**props, "text": "-"})
                    elif xt == "footnoteReference":
                        out.append({"fn": self.footnotes.get(x.get(_q("id")), ""), "text": ""})
                    elif xt in ("drawing", "pict", "object"):
                        img = self.image(x)
                        if img:
                            out.append(img)
                    elif xt == "sym":
                        try:
                            out.append({**props, "text": chr(int(x.get(_q("char")), 16))})
                        except (TypeError, ValueError):
                            pass
            elif tag == "hyperlink":
                rid = c.get(_q("id", R))
                url = self.rels.get(rid, (None,))[0] if rid else None
                self.runs_of(c, base, url or link, out)
            elif tag == "commentRangeStart":
                cid = self.cm_map.get(c.get(_q("id")))
                if cid:
                    self._cm_active.append(cid)
                    self._cm_seen.add(cid)
            elif tag == "commentRangeEnd":
                cid = self.cm_map.get(c.get(_q("id")))
                if cid in self._cm_active:
                    self._cm_active.remove(cid)
            elif tag in ("ins", "del"):
                old, self._tc = self._tc, tag
                self.runs_of(c, base, link, out)
                self._tc = old
            elif tag in ("smartTag", "fldSimple", "sdt", "sdtContent", "customXml", "moveTo"):
                self.runs_of(c, base, link, out)
        return out

    def paragraph(self, p):
        ppr = p.find(_q("pPr"))
        b = para()
        sid = _val(ppr.find(_q("pStyle"))) if ppr is not None else None
        kind = self.style_kind(sid) if sid else "normal"
        base = {}
        if sid and sid in self.styles:
            # Zeichenformat der Absatzvorlage, nur wenn sie von unseren Standards abweicht (z. B. farbige Vorlagen)
            st_r = self.run_props(self.styles[sid][2])
            for k in ("font", "color"):
                if k in st_r and kind in ("normal",):
                    base[k] = st_r[k]
        if kind.startswith("list:"):
            b["list"] = kind[5:]
        else:
            b["style"] = kind
        numpr = ppr.find(_q("numPr")) if ppr is not None else None
        if numpr is None and sid:
            numpr = self.style_numpr(sid)
        if numpr is not None:
            nid = _val(numpr.find(_q("numId")))
            lvl = _val(numpr.find(_q("ilvl")), "0")
            if nid and nid != "0":
                b["list"] = self.num_fmt.get((nid, lvl), "bullet")
                b["indent"] = int(lvl) if lvl.isdigit() else 0
        if ppr is not None:
            jc = _val(ppr.find(_q("jc")))
            b["align"] = {"center": "center", "right": "right", "end": "right", "both": "justify",
                          "distribute": "justify"}.get(jc, "left")
            ind = ppr.find(_q("ind"))
            if ind is not None and not b["list"]:
                left = ind.get(_q("left")) or ind.get(_q("start"))
                try:
                    b["indent"] = max(0, min(8, round(int(left) / 720)))
                except (TypeError, ValueError):
                    pass
            spc = ppr.find(_q("spacing"))
            if spc is not None and spc.get(_q("line")) and spc.get(_q("lineRule"), "auto") == "auto":
                try:
                    b["spacing"] = round(int(spc.get(_q("line"))) / 240, 2)
                except ValueError:
                    pass
            if ppr.find(_q("pBdr")) is not None and not "".join(p.itertext()).strip() \
                    and p.find(f".//{_q('drawing')}") is None:
                return [{"t": "hr"}]
            pre_pb = _on(ppr.find(_q("pageBreakBefore")))
        else:
            pre_pb = False
        out = [{"t": "pb"}] if pre_pb else []
        cur = b
        for r in self.runs_of(p, base):
            if r == "PB":
                out.append(cur)
                out.append({"t": "pb"})
                cur = {**b, "runs": []}
            elif r == "BR":
                out.append(cur)
                cur = {**b, "runs": [], "list": None}
            else:
                cur["runs"].append(r)
        out.append(cur)
        for x in out:
            if x["t"] == "p":
                x["runs"] = merge_runs(x["runs"])
        # Absatz, der nur einen Seitenumbruch trägt: die leeren Hüllen davor/danach weglassen
        if any(x["t"] == "pb" for x in out):
            out = [x for x in out if x["t"] != "p" or x["runs"]]
        return out

    def table(self, tbl):
        rows, fills, bold, jcs = [], [], [], []
        for tr in tbl.findall(_q("tr")):
            row, rf, rb, rj = [], [], [], []
            for tc in tr.findall(_q("tc")):
                lines = ["".join(t.text or "" for t in p.iter(_q("t"))) for p in tc.iter(_q("p"))]
                row.append("\n".join(lines).strip("\n"))
                shd = tc.find(f"{_q('tcPr')}/{_q('shd')}")
                rf.append((shd.get(_q("fill")) or "").lower() if shd is not None else "")
                rb.append(tc.find(f".//{_q('rPr')}/{_q('b')}") is not None)
                jc = tc.find(f".//{_q('pPr')}/{_q('jc')}")
                rj.append(_val(jc, "left") if jc is not None else "left")
                span = _val(tc.find(f"{_q('tcPr')}/{_q('gridSpan')}"))
                if span and span.isdigit():
                    row.extend([""] * (int(span) - 1))
            if row:
                rows.append(row)
                fills.append(rf)
                bold.append(rb)
                jcs.append(rj)
        out = {"t": "table", "rows": rows or [[""]]}
        try:
            st = dict(TABLE_DEFAULT)
            tr0 = tbl.find(_q("tr"))
            hdr = tr0 is not None and tr0.find(f"{_q('trPr')}/{_q('tblHeader')}") is not None
            st["head"] = bool(hdr or (bold and bold[0] and all(bold[0])))
            f0 = fills[0][0] if fills and fills[0] else ""
            if st["head"] and f0 and f0 not in ("auto", "e8e8e8", "ffffff"):
                st["accent"] = "#" + f0
            body = fills[1:] if st["head"] else fills
            st["stripes"] = len(body) >= 2 and not any(body[0]) and bool(body[1] and all(body[1]))
            bo = tbl.find(f"{_q('tblPr')}/{_q('tblBorders')}")
            if bo is not None:
                on = {s for s in ("top", "left", "bottom", "right", "insideH", "insideV")
                      if bo.find(_q(s)) is not None and _val(bo.find(_q(s))) not in ("nil", "none")}
                st["border"] = next((k for k in TABLE_BORDERS if table_border_sides({"border": k}) == on), "grid")
            if jcs:
                col = [max(set(c), key=c.count) for c in zip(*[r for r in jcs if len(r) == len(jcs[0])])] or []
                st["align"] = ["center" if a == "center" else "right" if a in ("right", "end") else "left"
                               for a in col]
            look = tbl.find(f"{_q('tblPr')}/{_q('tblLook')}")
            if look is not None and look.get(_q("firstColumn")) in ("1", "true", "on"):
                st["first_col"] = True
            mt = tbl.find(f"{_q('tblPr')}/{_q('tblCellMar')}/{_q('top')}")
            if mt is not None and (mt.get(_q("w")) or "").isdigit():
                v = int(mt.get(_q("w")))
                st["pad"] = "compact" if v <= 30 else "wide" if v >= 90 else "normal"
            gw = [int(g.get(_q("w")) or 0) for g in tbl.findall(f"{_q('tblGrid')}/{_q('gridCol')}")]
            if gw and all(gw) and max(gw) > min(gw) * 1.15:
                st["widths"] = [round(w / sum(gw), 3) for w in gw]
            sm = table_style_min(st)
            if sm:
                out["style"] = sm
        except Exception:  # noqa: BLE001 – Design ist Zugabe, Inhalt zählt
            pass
        return out

    def blocks(self, container):
        out = []
        for el in container:
            tag = el.tag.split("}")[-1]
            if tag == "p":
                if len(el) == 0 and out and out[-1]["t"] == "table":
                    continue                 # Pflicht-Leerabsatz nach einer Tabelle
                sid = _val(el.find(f"{_q('pPr')}/{_q('pStyle')}"))
                if sid and self.style_kind(sid) == "toc":     # Inhaltsverzeichnis: als ein Block übernehmen
                    if not out or out[-1]["t"] != "toc":
                        out.append({"t": "toc"})
                    continue
                if out and out[-1]["t"] == "toc" and not "".join(el.itertext()).strip():
                    continue
                out.extend(self.paragraph(el))
            elif tag == "tbl":
                out.append(self.table(el))
            elif tag in ("sdt", "sdtContent", "customXml", "ins"):
                out.extend(self.blocks(el))
        return out


def read_docx(path):
    blocks, title, _page = read_docx_full(path)
    return blocks, title


def read_docx_full(path):
    with zipfile.ZipFile(path) as z:
        rd = _DocxReader(z)
        root = rd._xml("word/document.xml")
        if root is None:
            raise ValueError("Keine gültige DOCX-Datei (word/document.xml fehlt)")
        body = root.find(_q("body"))
        blocks = rd.blocks(body) if body is not None else []
        page = rd.page(body)
        # Leerzeilen am Ende abschneiden
        while len(blocks) > 1 and blocks[-1]["t"] == "p" and not blocks[-1]["runs"]:
            blocks.pop()
        title = ""
        core = rd._xml("docProps/core.xml")
        if core is not None:
            t = core.find("{http://purl.org/dc/elements/1.1/}title")
            title = (t.text or "").strip() if t is not None else ""
    # Schriftgrößen, die nur der Standardgröße des Dokuments entsprechen, nicht extra merken
    for b in blocks:
        if b["t"] == "p":
            std = STYLE_FMT[b["style"]][0]
            for r in b["runs"]:
                if r.get("size") in (std, rd.default_size) and b["style"] == "normal":
                    r.pop("size")
    return blocks or [para()], title, page


# =====================================================================
# DOC (Word 97–2003) lesen – nur Text, ohne Fremdprogramm
# =====================================================================
class _Cfb:
    """Minimaler Leser für OLE-Verbunddateien (Container von .doc)."""

    def __init__(self, data):
        if data[:8] != b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
            raise ValueError("Keine Word-97-Datei")
        self.d = data
        self.ss = 1 << struct.unpack("<H", data[30:32])[0]
        self.mss = 1 << struct.unpack("<H", data[32:34])[0]
        nfat, dir_start = struct.unpack("<I", data[44:48])[0], struct.unpack("<i", data[48:52])[0]
        self.cutoff = struct.unpack("<I", data[56:60])[0]
        mf_start, nmf = struct.unpack("<i", data[60:64])[0], struct.unpack("<I", data[64:68])[0]
        dif_start, ndif = struct.unpack("<i", data[68:72])[0], struct.unpack("<I", data[72:76])[0]
        difat = list(struct.unpack("<109i", data[76:512]))
        s = dif_start
        for _ in range(ndif):
            if s < 0:
                break
            ints = struct.unpack(f"<{self.ss // 4}i", self.sector(s))
            difat.extend(ints[:-1])
            s = ints[-1]
        self.fat = []
        for s in difat[:nfat]:
            if s >= 0:
                self.fat.extend(struct.unpack(f"<{self.ss // 4}i", self.sector(s)))
        dirs = self.chain(dir_start)
        self.entries = {}
        root = None
        for i in range(len(dirs) // 128):
            e = dirs[i * 128:(i + 1) * 128]
            nlen = struct.unpack("<H", e[64:66])[0]
            name = e[:max(0, nlen - 2)].decode("utf-16-le", "ignore")
            typ = e[66]
            start, size = struct.unpack("<iI", e[116:124])
            if typ == 5:
                root = (start, size)
            elif typ == 2:
                self.entries[name] = (start, size)
        self.minifat = []
        if mf_start >= 0:
            mf = self.chain(mf_start)
            self.minifat = list(struct.unpack(f"<{len(mf) // 4}i", mf))
        self.ministream = self.chain(root[0])[:root[1]] if root else b""

    def sector(self, n):
        o = 512 + n * self.ss
        return self.d[o:o + self.ss]

    def chain(self, start):
        out, s, seen = [], start, set()
        while s >= 0 and s not in seen and s < len(self.fat) + 1:
            seen.add(s)
            out.append(self.sector(s))
            s = self.fat[s] if s < len(self.fat) else -2
        return b"".join(out)

    def stream(self, name):
        start, size = self.entries[name]
        if size < self.cutoff:
            out, s, seen = [], start, set()
            while s >= 0 and s not in seen and s < len(self.minifat):
                seen.add(s)
                out.append(self.ministream[s * self.mss:(s + 1) * self.mss])
                s = self.minifat[s]
            return b"".join(out)[:size]
        return self.chain(start)[:size]


def read_doc(path):
    """Text aus .doc über die Stücktabelle (Piece Table). Formatierung geht dabei verloren."""
    cfb = _Cfb(open(path, "rb").read())
    wd = cfb.stream("WordDocument")
    flags = struct.unpack("<H", wd[10:12])[0]
    if flags & 0x0100:
        raise ValueError("Die Datei ist verschlüsselt")
    table = cfb.stream("1Table" if flags & 0x0200 else "0Table")
    ccp_text = struct.unpack("<i", wd[0x4C:0x50])[0]
    fc_clx, lcb_clx = struct.unpack("<II", wd[0x1A2:0x1AA])
    clx = table[fc_clx:fc_clx + lcb_clx]
    i = 0
    while i < len(clx) and clx[i] == 1:        # Prc-Einträge überspringen
        i += 3 + struct.unpack("<H", clx[i + 1:i + 3])[0]
    if i >= len(clx) or clx[i] != 2:
        raise ValueError("Stücktabelle nicht gefunden")
    lcb = struct.unpack("<I", clx[i + 1:i + 5])[0]
    plc = clx[i + 5:i + 5 + lcb]
    n = (lcb - 4) // 12
    cps = struct.unpack(f"<{n + 1}I", plc[:4 * (n + 1)])
    chars = []
    for k in range(n):
        pcd = plc[4 * (n + 1) + 8 * k: 4 * (n + 1) + 8 * (k + 1)]
        fc = struct.unpack("<I", pcd[2:6])[0]
        cnt = cps[k + 1] - cps[k]
        if fc & 0x40000000:
            off = (fc & 0x3FFFFFFF) // 2
            chars.append(wd[off:off + cnt].decode("cp1252", "replace"))
        else:
            chars.append(wd[fc:fc + 2 * cnt].decode("utf-16-le", "replace"))
    text = "".join(chars)[:ccp_text]
    # Feldfunktionen: { Befehl \x14 Ergebnis \x15 } → nur Ergebnis behalten
    out, depth_instr = [], []
    for ch in text:
        if ch == "\x13":
            depth_instr.append(True)
        elif ch == "\x14":
            if depth_instr:
                depth_instr[-1] = False
        elif ch == "\x15":
            if depth_instr:
                depth_instr.pop()
        elif not any(depth_instr):
            out.append(ch)
    text = "".join(out)
    blocks, table_rows, row = [], [], []
    for piece in re.split(r"(\r|\x07|\x0c)", text):
        if piece == "\r" or piece == "":
            continue
        if piece == "\x0c":
            blocks.append({"t": "pb"})
            continue
        if piece == "\x07":
            continue
        clean = re.sub(r"[\x00-\x08\x0e-\x1f]", "", piece.replace("\x0b", " ").replace("\x1e", "-"))
        blocks.append(para(clean))
    # Tabellenzellen (\x07) lassen sich ohne Formatierungsdaten nicht sicher zuordnen – sie werden zu Absätzen
    del table_rows, row
    return blocks or [para()]


# =====================================================================
# TXT / Markdown / HTML
# =====================================================================
def read_text(path):
    raw = open(path, "rb").read()
    for enc in ("utf-8", "cp1252"):
        try:
            txt = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    return [para(line) for line in txt.replace("\r\n", "\n").split("\n")] or [para()]


def _md_inline(s):
    """**fett**, *kursiv*, ~~durch~~, `code`, [text](url) → Läufe."""
    runs, pos = [], 0
    pat = re.compile(r"\*\*(.+?)\*\*|__(.+?)__|\*(.+?)\*|_(.+?)_|~~(.+?)~~|`(.+?)`|\[(.+?)\]\((.+?)\)")
    for m in pat.finditer(s):
        if m.start() > pos:
            runs.append({"text": s[pos:m.start()]})
        if m.group(1) or m.group(2):
            runs.append({"text": m.group(1) or m.group(2), "b": True})
        elif m.group(3) or m.group(4):
            runs.append({"text": m.group(3) or m.group(4), "i": True})
        elif m.group(5):
            runs.append({"text": m.group(5), "s": True})
        elif m.group(6):
            runs.append({"text": m.group(6), "font": MONO_FONT})
        else:
            runs.append({"text": m.group(7), "link": m.group(8)})
        pos = m.end()
    if pos < len(s):
        runs.append({"text": s[pos:]})
    return runs


def read_markdown(path):
    return markdown_blocks(open(path, encoding="utf-8", errors="replace").read())


def _md_tables(lines):
    """Zeilen → Zeilen, wobei Pipe-Tabellen („| a | b |“ + Trennzeile „|---|---|“) zu je einer Zeilenliste werden."""
    def cells(l):
        l = l.strip()
        l = l[1:] if l.startswith("|") else l
        l = l[:-1] if l.endswith("|") and not l.endswith("\\|") else l
        return [c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", l)]
    out, i, fence = [], 0, False
    while i < len(lines):
        l = lines[i]
        if l.startswith("```"):
            fence = not fence
        sep = lines[i + 1] if i + 1 < len(lines) else ""
        if (not fence and "|" in l and re.match(r"^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?\s*$", sep)
                and "|" in sep and len(cells(l)) == len(cells(sep))):
            rows, i = [cells(l)], i + 2
            while i < len(lines) and "|" in lines[i] and lines[i].strip():
                rows.append(cells(lines[i]))
                i += 1
            out.append(rows)
            continue
        out.append(l)
        i += 1
    return out


def markdown_blocks(text):
    """Markdown-Text → Blöcke (auch für Einfügen aus der Zwischenablage)."""
    blocks, code = [], False
    for line in _md_tables(text.replace("\r\n", "\n").split("\n")):
        if isinstance(line, list):                      # Markdown-Tabelle
            blocks.append({"t": "table", "rows": line})
            continue
        if line.startswith("```"):
            code = not code
            continue
        if code:
            blocks.append(para(line, style="code"))
            continue
        m = re.match(r"^(#{1,6})\s+(.*)", line)
        lm = re.match(r"^(\s*)([-*+]|\d+[.)])\s+(.*)", line)
        if m:
            p = para(style={1: "h1", 2: "h2"}.get(len(m.group(1)), "h3"))
            p["runs"] = _md_inline(m.group(2))
        elif re.match(r"^\s*([-*_])\s*\1\s*\1[\s\1]*$", line):
            blocks.append({"t": "hr"})
            continue
        elif line.startswith(">"):
            p = para(style="quote")
            p["runs"] = _md_inline(line.lstrip("> "))
        elif lm:
            p = para(list="number" if lm.group(2)[0].isdigit() else "bullet", indent=len(lm.group(1)) // 2)
            p["runs"] = _md_inline(lm.group(3))
        else:
            p = para()
            p["runs"] = _md_inline(line)
        blocks.append(p)
    return blocks or [para()]


def _slug(text):
    return re.sub(r"[^\w\- ]", "", text.lower()).strip().replace(" ", "-")


def to_markdown(blocks):
    blocks = accept_all(blocks)
    nums = list_numbers(blocks)
    out, kinds, notes = [], [], []
    for i, b in enumerate(blocks):
        if b["t"] == "toc":
            out.append("## " + tr("Inhaltsverzeichnis"))
            kinds.append("p")
            for level, text, _ in headings(blocks):
                out.append("  " * (level - 1) + f"- [{text}](#{_slug(text)})")
                kinds.append("list")
            continue
        if b["t"] == "hr":
            out.append("---")
        elif b["t"] == "pb":
            out.append("")
        elif b["t"] == "table":
            rows = b["rows"]
            ncol = max(len(r) for r in rows)
            for k, r in enumerate(rows):
                cells = [(r[c] if c < len(r) else "").replace("\n", " ").replace("|", "\\|") for c in range(ncol)]
                out.append("| " + " | ".join(cells) + " |")
                kinds.append("table" if k else "table0")
                if k == 0:
                    st = table_style(b)
                    out.append("|" + "".join({"center": ":---:|", "right": "---:|"}.get(table_align(st, c), "---|")
                                             for c in range(ncol)))
                    kinds.append("table")
            continue
        else:
            txt = ""
            for r in b["runs"]:
                if r.get("img"):
                    txt += "![Bild]()"
                    continue
                if r.get("fn") is not None:
                    notes.append(r["fn"])
                    txt += f"[^{len(notes)}]"
                    continue
                t = r["text"]
                core = t.strip()
                lead, trail = t[:len(t) - len(t.lstrip())], t[len(t.rstrip()):]
                if core:                       # Leerzeichen gehören außerhalb von **…**
                    if r.get("b"):
                        core = f"**{core}**"
                    if r.get("i"):
                        core = f"*{core}*"
                    if r.get("s"):
                        core = f"~~{core}~~"
                    if r.get("link"):
                        core = f"[{core}]({r['link']})"
                txt += lead + core + trail
            pre = {"title": "# ", "h1": "# ", "h2": "## ", "h3": "### ", "quote": "> "}.get(b["style"], "")
            if b["style"] == "code":
                txt = f"    {txt}"
            if b.get("list"):
                pre = "  " * b.get("indent", 0) + ("- " if b["list"] == "bullet" else f"{nums.get(i, 1)}. ")
            out.append(pre + txt)
            kinds.append("list" if b.get("list") else "code" if b["style"] == "code" else "p")
            continue
        kinds.append(b["t"])
    # Listen, Tabellenzeilen und Code-Zeilen bleiben zusammen, sonst Leerzeile zwischen Absätzen
    res = ""
    for k, (line, kind) in enumerate(zip(out, kinds)):
        if k:
            same = kind == kinds[k - 1] or (kind == "table" and kinds[k - 1] == "table0")
            res += "\n" if same and kind in ("list", "table", "code") else "\n\n"
        res += line
    if notes:
        res += "\n\n" + "\n".join(f"[^{k}]: {t}" for k, t in enumerate(notes, start=1))
    return res + "\n"


def to_html(blocks, title=""):
    blocks = accept_all(blocks)
    nums = list_numbers(blocks)
    out = [f"<!doctype html><html lang=\"de\"><head><meta charset=\"utf-8\"><title>{esc(title)}</title>"
           f"<style>body{{font-family:'{BASE_FONT}',sans-serif;max-width:46em;margin:3em auto;line-height:1.4}}"
           "table{border-collapse:collapse;width:100%}td{border:1px solid #888;padding:4px 8px;vertical-align:top}"
           "blockquote{margin-left:2em;color:#555;font-style:italic}pre{background:#f2f2f2;padding:2px 6px;margin:0}"
           "</style></head><body>"]
    notes = []
    for i, b in enumerate(blocks):
        if b["t"] == "toc":
            items = "".join(f'<li style="margin-left:{(lv - 1) * 1.5}em"><a href="#h{idx}">{esc(t)}</a></li>'
                            for lv, t, idx in headings(blocks))
            out.append(f'<nav><h2>{esc(tr("Inhaltsverzeichnis"))}</h2><ul style="list-style:none;padding:0">{items}</ul></nav>')
        elif b["t"] == "hr":
            out.append("<hr>")
        elif b["t"] == "pb":
            out.append('<div style="page-break-after:always"></div>')
        elif b["t"] == "table":
            out.append(html_table(b))
        else:
            inner = ""
            for r in b["runs"]:
                if r.get("img"):
                    inner += (f'<img src="data:{r.get("mime", "image/png")};base64,{r["img"]}" '
                              f'width="{r.get("w", "")}" height="{r.get("h", "")}" alt="">')
                    continue
                if r.get("fn") is not None:
                    notes.append(r["fn"])
                    k = len(notes)
                    inner += f'<sup><a href="#fn{k}" id="ref{k}">{k}</a></sup>'
                    continue
                t = esc(r["text"]).replace("\t", "&emsp;")
                css = []
                if r.get("font"):
                    css.append(f"font-family:'{esc(r['font'])}'")
                if r.get("size"):
                    css.append(f"font-size:{r['size']}pt")
                if r.get("color"):
                    css.append(f"color:{r['color']}")
                if r.get("hl"):
                    css.append(f"background:{r['hl']}")
                if css:
                    t = f'<span style="{";".join(css)}">{t}</span>'
                for k, tag in (("b", "b"), ("i", "i"), ("u", "u"), ("s", "s")):
                    if r.get(k):
                        t = f"<{tag}>{t}</{tag}>"
                if r.get("va"):
                    t = f"<{r['va']}>{t}</{r['va']}>"
                if r.get("link"):
                    t = f'<a href="{esc(r["link"])}">{t}</a>'
                inner += t
            tag = {"title": "h1", "h1": "h1", "h2": "h2", "h3": "h3", "quote": "blockquote", "code": "pre"}.get(
                b["style"], "p")
            style = []
            if b["align"] != "left":
                style.append(f"text-align:{b['align']}")
            ind = b.get("indent", 0) + (1 if b.get("list") else 0)
            if ind:
                style.append(f"margin-left:{ind * 2}em")
            if b.get("list"):
                mark = "•" if b["list"] == "bullet" else f"{nums.get(i, 1)}."
                inner = f"{mark}&ensp;{inner}"
            st_attr = f' style="{";".join(style)}"' if style else ""
            if b["style"] in ("h1", "h2", "h3"):
                st_attr += f' id="h{i}"'
            out.append(f"<{tag}{st_attr}>{inner or '&nbsp;'}</{tag}>")
    if notes:
        out.append('<hr style="width:30%;margin-left:0"><ol style="font-size:90%">' +
                   "".join(f'<li id="fn{k}">{esc(t)} <a href="#ref{k}">↩</a></li>' for k, t in enumerate(notes, start=1))
                   + "</ol>")
    out.append("</body></html>")
    return "\n".join(out)


def read_html(path):
    """Einfacher HTML-Import: Absätze, Überschriften, Listen, fett/kursiv. Für Webseiten-Schnipsel."""
    src = open(path, encoding="utf-8", errors="replace").read()
    src = re.sub(r"(?is)<(script|style|head)[^>]*>.*?</\1>", "", src)
    blocks, cur, fmt, lst = [], None, {}, []

    def flush():
        nonlocal cur
        if cur is not None:
            cur["runs"] = merge_runs(cur["runs"])
            blocks.append(cur)
        cur = None
    for m in re.finditer(r"<(/?)([a-zA-Z0-9]+)[^>]*?>|([^<]+)", src):
        if m.group(3) is not None:
            txt = html.unescape(re.sub(r"\s+", " ", m.group(3)))
            if txt.strip() or (cur and cur["runs"]):
                if cur is None:
                    cur = para(list=lst[-1] if lst else None, indent=max(0, len(lst) - 1))
                cur["runs"].append({"text": txt, **fmt})
            continue
        close, tag = m.group(1) == "/", m.group(2).lower()
        if tag in ("p", "div", "li", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "pre", "tr", "br"):
            flush()
            if not close and tag != "br":
                st = {"h1": "h1", "h2": "h2", "h3": "h3", "h4": "h3", "h5": "h3", "h6": "h3",
                      "blockquote": "quote", "pre": "code"}.get(tag, "normal")
                cur = para(style=st, list=lst[-1] if (lst and tag == "li") else None, indent=max(0, len(lst) - 1))
        elif tag in ("ul", "ol"):
            flush()
            if close:
                lst and lst.pop()
            else:
                lst.append("bullet" if tag == "ul" else "number")
        elif tag == "hr":
            flush()
            blocks.append({"t": "hr"})
        elif tag in ("b", "strong"):
            fmt["b"] = True if not close else fmt.pop("b", None) and None
        elif tag in ("i", "em"):
            fmt["i"] = True if not close else fmt.pop("i", None) and None
        elif tag == "u":
            fmt["u"] = True if not close else fmt.pop("u", None) and None
        fmt = {k: v for k, v in fmt.items() if v}
    flush()
    for b in blocks:
        if b["t"] == "p" and b["runs"]:
            b["runs"][0]["text"] = b["runs"][0]["text"].lstrip()
    return [b for b in blocks if b["t"] != "p" or b["runs"]] or [para()]


IMPORT_TYPES = {".docx": read_docx, ".docm": read_docx, ".dotx": read_docx, ".doc": read_doc, ".txt": read_text,
                ".md": read_markdown, ".markdown": read_markdown, ".html": read_html, ".htm": read_html,
                ".odt": None}


def import_file_full(path):
    """Datei → (Blöcke, Titel, Seiteneinstellungen oder None)."""
    import os
    ext = os.path.splitext(path)[1].lower()
    if ext == ".odt":
        import odf
        return odf.read_odt(path)
    if ext in (".docx", ".docm", ".dotx"):
        import_file(path)                  # Prüfungen (Passwort usw.)
        return read_docx_full(path)
    blocks, title = import_file(path)
    return blocks, title, None


def import_file(path):
    """Datei → (Blöcke, Titel). Titel leer heißt: Dateiname nehmen."""
    import os
    ext = os.path.splitext(path)[1].lower()
    if ext == ".doc":
        with open(path, "rb") as f:
            head = f.read(8)
        if head[:4] == b"PK\x03\x04":       # falsch benanntes DOCX
            return read_docx(path)
        if head.startswith(b"{\\rtf"):
            raise ValueError("Das ist eine RTF-Datei, kein Word-Dokument")
    if ext in (".docx", ".docm", ".dotx"):
        with open(path, "rb") as f:
            if f.read(8) == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
                raise ValueError("Das Dokument ist mit einem Passwort geschützt")
    if ext == ".odt":
        import odf
        return odf.read_odt(path)[:2]
    fn = IMPORT_TYPES.get(ext)
    if not fn:
        raise ValueError(f"Dateityp {ext or '?'} wird nicht unterstützt")
    res = fn(path)
    return res if isinstance(res, tuple) else (res, "")


def export_text(blocks):
    blocks = accept_all(blocks)
    nums = list_numbers(blocks)
    out, notes = [], []
    for i, b in enumerate(blocks):
        if b["t"] == "toc":
            out.append(tr("Inhaltsverzeichnis"))
            out.extend("  " * (lv - 1) + t for lv, t, _ in headings(blocks))
            out.append("")
        if b["t"] == "p":
            t = ""
            for r in b["runs"]:
                if r.get("fn") is not None:
                    notes.append(r["fn"])
                    t += f"[{len(notes)}]"
                else:
                    t += r.get("text", "")
            if b.get("list"):
                t = "  " * b.get("indent", 0) + ("• " if b["list"] == "bullet" else f"{nums.get(i, 1)}. ") + t
            out.append(t)
        elif b["t"] == "table":
            out.extend("\t".join(c.replace("\n", " ") for c in r) for r in b["rows"])
        elif b["t"] == "hr":
            out.append("―" * 40)
        elif b["t"] == "pb":
            out.append("\f")
    if notes:
        out += ["", "―" * 20] + [f"[{k}] {t}" for k, t in enumerate(notes, start=1)]
    return "\n".join(out) + "\n"


def html_table(b):
    rows = b["rows"] or [[""]]
    ncol = max(len(r) for r in rows)
    st = table_style(b)
    fr = table_widths(st, ncol)
    sides = table_border_sides(st)
    col = st["accent"] or "#999999"
    pad = {"compact": "2px 6px", "normal": "4px 8px", "wide": "8px 12px"}[st["pad"]]
    outer = ";".join(f"border-{s}:1px solid {col}" for s in ("top", "bottom", "left", "right") if s in sides)
    out = [f'<table style="border-collapse:collapse;width:100%;{outer}">',
           "<colgroup>" + "".join(f'<col style="width:{f * 100:.1f}%">' for f in fr) + "</colgroup>"]
    for r, row in enumerate(rows):
        cells = []
        for c in range(ncol):
            fill, fg, bold = table_cell_look(st, r, c)
            css = [f"padding:{pad}", f"text-align:{table_align(st, c)}", "vertical-align:top"]
            if "insideH" in sides:
                css.append(f"border-bottom:1px solid {col}")
            if "insideV" in sides and c < ncol - 1:
                css.append(f"border-right:1px solid {col}")
            if fill:
                css.append(f"background:#{fill}")
            if fg:
                css.append(f"color:#{fg}")
            if bold:
                css.append("font-weight:bold")
            tag = "th" if st["head"] and r == 0 else "td"
            txt = esc(row[c] if c < len(row) else "").replace("\n", "<br>")
            cells.append(f'<{tag} style="{";".join(css)}">{txt}</{tag}>')
        out.append("<tr>" + "".join(cells) + "</tr>")
    out.append("</table>")
    return "".join(out)
