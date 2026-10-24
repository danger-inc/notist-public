# ODT (LibreOffice / OpenDocument Text) lesen und schreiben – ohne Fremdpakete, nur zip + XML.
# Unterstützt: Überschriften, Absätze (Ausrichtung, Einzug, Zeilenabstand), Zeichenformat, Links, Listen,
# Tabellen, Bilder, Linien, Seitenumbrüche, Fußnoten, Inhaltsverzeichnis, Seitenformat, Kopf-/Fußzeile, Seitenzahl.
import base64, datetime, re, zipfile
import xml.etree.ElementTree as ET
from html import escape as _esc

import docfmt as df

NS = {
    "office": "urn:oasis:names:tc:opendocument:xmlns:office:1.0",
    "style": "urn:oasis:names:tc:opendocument:xmlns:style:1.0",
    "text": "urn:oasis:names:tc:opendocument:xmlns:text:1.0",
    "table": "urn:oasis:names:tc:opendocument:xmlns:table:1.0",
    "draw": "urn:oasis:names:tc:opendocument:xmlns:drawing:1.0",
    "fo": "urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0",
    "xlink": "http://www.w3.org/1999/xlink",
    "svg": "urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0",
    "meta": "urn:oasis:names:tc:opendocument:xmlns:meta:1.0",
    "dc": "http://purl.org/dc/elements/1.1/",
    "manifest": "urn:oasis:names:tc:opendocument:xmlns:manifest:1.0",
}
NSDECL = " ".join(f'xmlns:{k}="{v}"' for k, v in NS.items() if k != "manifest")
MIME = "application/vnd.oasis.opendocument.text"
BOLD_TP = '<style:text-properties fo:font-weight="bold"/>'


def esc(s):
    return _esc(s, quote=True)


def q(tag):
    p, t = tag.split(":")
    return f"{{{NS[p]}}}{t}"


# =====================================================================
# Schreiben
# =====================================================================
class _Writer:
    def __init__(self, blocks, page, title):
        self.blocks, self.page, self.title = blocks, df.norm_page(page), title
        self.auto = {}        # Stil-Definition → Name
        self.pictures = []    # (pfad, bytes, mime)
        self.fn = 0

    def style(self, family, props, parent=None, kind="text"):
        key = (family, parent, tuple(sorted(props.items())), kind)
        if key in self.auto:
            return self.auto[key]
        name = ("T" if family == "text" else "P") + str(len(self.auto) + 1)
        self.auto[key] = name
        return name

    def auto_xml(self):
        out = []
        for (family, parent, props, kind), name in self.auto.items():
            p = dict(props)
            par = f' style:parent-style-name="{parent}"' if parent else ""
            if family == "text":
                attrs = " ".join(f'{k}="{esc(str(v))}"' for k, v in p.items())
                out.append(f'<style:style style:name="{name}" style:family="text"><style:text-properties {attrs}/></style:style>')
            else:
                para_p = {k: v for k, v in p.items() if not k.startswith("_")}
                attrs = " ".join(f'{k}="{esc(str(v))}"' for k, v in para_p.items())
                out.append(f'<style:style style:name="{name}" style:family="paragraph"{par}>'
                           f'<style:paragraph-properties {attrs}/></style:style>')
        return "".join(out)

    def span(self, r):
        if r.get("img"):
            return self.image(r)
        if r.get("fn") is not None:
            self.fn += 1
            return (f'<text:note text:id="ftn{self.fn}" text:note-class="footnote"><text:note-citation>{self.fn}'
                    f'</text:note-citation><text:note-body><text:p text:style-name="Footnote">{esc(r["fn"])}'
                    f'</text:p></text:note-body></text:note>')
        props = {}
        if r.get("b"):
            props["fo:font-weight"] = "bold"
        if r.get("i"):
            props["fo:font-style"] = "italic"
        if r.get("u") and not r.get("link"):
            props["style:text-underline-style"] = "solid"
            props["style:text-underline-width"] = "auto"
            props["style:text-underline-color"] = "font-color"
        if r.get("s"):
            props["style:text-line-through-style"] = "solid"
        if r.get("font"):
            props["style:font-name"] = r["font"]
            props["fo:font-family"] = r["font"]
        if r.get("size"):
            props["fo:font-size"] = f"{float(r['size']):g}pt"
        if r.get("color"):
            props["fo:color"] = r["color"]
        if r.get("hl"):
            props["fo:background-color"] = r["hl"]
        if r.get("va") == "sup":
            props["style:text-position"] = "super 58%"
        elif r.get("va") == "sub":
            props["style:text-position"] = "sub 58%"
        text = self.text(r.get("text", ""))
        if props:
            text = f'<text:span text:style-name="{self.style("text", props)}">{text}</text:span>'
        if r.get("link"):
            text = f'<text:a xlink:type="simple" xlink:href="{esc(r["link"])}">{text}</text:a>'
        return text

    @staticmethod
    def text(t):
        out = []
        for part in re.split(r"(\t| {2,})", t):
            if part == "\t":
                out.append("<text:tab/>")
            elif part.startswith("  ") and not part.strip():
                out.append(f' <text:s text:c="{len(part) - 1}"/>')
            else:
                out.append(esc(part))
        return "".join(out)

    def image(self, r):
        data = base64.b64decode(r["img"])
        mime = r.get("mime") or df.sniff_mime(data) or "image/png"
        ext = {"image/jpeg": "jpg", "image/gif": "gif", "image/webp": "webp", "image/bmp": "bmp"}.get(mime, "png")
        path = f"Pictures/bild{len(self.pictures) + 1}.{ext}"
        self.pictures.append((path, data, mime))
        w, h = (r.get("w") or df.image_size(data)[0]), (r.get("h") or df.image_size(data)[1])
        cm = 2.54 / 96
        return (f'<draw:frame draw:name="Bild{len(self.pictures)}" text:anchor-type="as-char" svg:width="{w * cm:.2f}cm" '
                f'svg:height="{h * cm:.2f}cm"><draw:image xlink:href="{path}" xlink:type="simple" xlink:show="embed" '
                f'xlink:actuate="onLoad"/></draw:frame>')

    def para_style(self, b, extra=None):
        props = dict(extra or {})
        if b.get("align", "left") != "left":
            props["fo:text-align"] = {"center": "center", "right": "end", "justify": "justify"}[b["align"]]
        if b.get("indent") and not b.get("list"):
            props["fo:margin-left"] = f"{1.25 * b['indent']:g}cm"
        sp = b.get("spacing", 1.15)
        if abs(sp - 1.15) > 0.01:
            props["fo:line-height"] = f"{round(sp / 1.15 * 115)}%"
        parent = {"title": "Title", "h1": "Heading_20_1", "h2": "Heading_20_2", "h3": "Heading_20_3",
                  "quote": "Quotations", "code": "Preformatted_20_Text"}.get(b.get("style"), "Standard")
        if not props:
            return parent
        return self.style("paragraph", props, parent, "p")

    def paragraph(self, b, extra=None):
        st = self.para_style(b, extra)
        inner = "".join(self.span(r) for r in b["runs"])
        if b.get("style") in ("h1", "h2", "h3"):
            return f'<text:h text:style-name="{st}" text:outline-level="{b["style"][1]}">{inner}</text:h>'
        return f'<text:p text:style-name="{st}">{inner}</text:p>'

    def body(self):
        out, i, pending_break = [], 0, False
        blocks = self.blocks
        while i < len(blocks):
            b = blocks[i]
            extra = {"fo:break-before": "page"} if pending_break else None
            pending_break = False
            if b["t"] == "p" and b.get("list"):
                kind = b["list"]
                items = []
                while i < len(blocks) and blocks[i]["t"] == "p" and blocks[i].get("list") == kind:
                    items.append(blocks[i])
                    i += 1
                out.append(self.list_xml(items, kind))
                continue
            if b["t"] == "p":
                out.append(self.paragraph(b, extra))
            elif b["t"] == "table":
                out.append(self.table(b))
            elif b["t"] == "hr":
                st = self.style("paragraph", {"fo:border-bottom": "0.06pt solid #808080", "fo:padding": "0.05cm"},
                                "Standard", "p")
                out.append(f'<text:p text:style-name="{st}"/>')
            elif b["t"] == "pb":
                pending_break = True
            elif b["t"] == "toc":
                out.append(self.toc())
            i += 1
        return "".join(out)

    def list_xml(self, items, kind):
        name = "LBullet" if kind == "bullet" else "LNumber"
        out = [f'<text:list text:style-name="{name}">']
        level = 0
        for b in items:
            want = b.get("indent", 0)
            while level < want:
                out.append("<text:list-item><text:list>")
                level += 1
            while level > want:
                out.append("</text:list></text:list-item>")
                level -= 1
            out.append(f"<text:list-item>{self.paragraph(dict(b, list=None))}</text:list-item>")
        while level > 0:
            out.append("</text:list></text:list-item>")
            level -= 1
        out.append("</text:list>")
        return "".join(out)

    def table(self, b):
        rows = b["rows"] or [[""]]
        ncol = max(len(r) for r in rows)
        out = [f'<table:table table:name="Tabelle{id(b) % 1000}" table:style-name="Tab">'
               f'<table:table-column table:number-columns-repeated="{ncol}"/>']
        for k, row in enumerate(rows):
            out.append("<table:table-row>")
            for c in range(ncol):
                cell = row[c] if c < len(row) else ""
                ps = "".join(f'<text:p text:style-name="{"TabHead" if k == 0 else "Standard"}">{self.text(line)}</text:p>'
                             for line in cell.split("\n"))
                out.append(f'<table:table-cell table:style-name="Cell" office:value-type="string">{ps}</table:table-cell>')
            out.append("</table:table-row>")
        out.append("</table:table>")
        return "".join(out)

    def toc(self):
        try:
            import render
            pages = render.heading_pages(self.blocks, self.page)
        except Exception:  # noqa: BLE001
            pages = {}
        ents = "".join(
            f'<text:p text:style-name="Contents_20_{lv}">{esc(t)}<text:tab/>{pages.get(idx, "")}</text:p>'
            for lv, t, idx in df.headings(self.blocks))
        tmpl = "".join(
            f'<text:table-of-content-entry-template text:outline-level="{lv}" text:style-name="Contents_20_{lv}">'
            f'<text:index-entry-text/><text:index-entry-tab-stop style:type="right" style:leader-char="."/>'
            f'<text:index-entry-page-number/></text:table-of-content-entry-template>' for lv in (1, 2, 3))
        return (f'<text:table-of-content text:name="Inhaltsverzeichnis1"><text:table-of-content-source text:outline-level="3">'
                f'<text:index-title-template text:style-name="Contents_20_Heading">{esc(df.tr("Inhaltsverzeichnis"))}</text:index-title-template>'
                f'{tmpl}</text:table-of-content-source><text:index-body><text:index-title text:name="Inhaltsverzeichnis1_Head">'
                f'<text:p text:style-name="Contents_20_Heading">{esc(df.tr("Inhaltsverzeichnis"))}</text:p></text:index-title>{ents}'
                f'</text:index-body></text:table-of-content>')

    # ---------- Seite, Kopf/Fuß ----------
    def hf(self, text, num):
        parts = []
        if text:
            t = text.replace("{titel}", self.title or "").replace("{datum}", datetime.date.today().strftime("%d.%m.%Y"))
            for chunk in re.split(r"(\{seiten?\})", t):
                if chunk == "{seite}":
                    parts.append('<text:page-number text:select-page="current">1</text:page-number>')
                elif chunk == "{seiten}":
                    parts.append("<text:page-count>1</text:page-count>")
                elif chunk:
                    parts.append(self.text(chunk))
        out = f'<text:p text:style-name="Header">{"".join(parts)}</text:p>' if parts else ""
        if num:
            before, after, align = num
            n = (esc(before) + '<text:page-number text:select-page="current">1</text:page-number>' +
                 (f" {esc(df.tr('von'))} <text:page-count>1</text:page-count>" if after == "of" else esc(after)))
            out += f'<text:p text:style-name="Num{align}">{n}</text:p>'
        return out

    def styles_xml(self):
        w, h, (t, r, b, l) = df.page_mm(self.page)
        cfg = self.page
        pos = cfg["numbers"]
        num = None
        if pos != "none":
            fmt = {"n": ("", ""), "page": (df.tr("Seite") + " ", ""), "page-of": (df.tr("Seite") + " ", "of"),
                   "dash": ("– ", " –")}[cfg["num_fmt"]]
            num = fmt + ({"footer-center": "Center", "footer-left": "Left"}.get(pos, "Right"),)
        head = self.hf(cfg["header"], num if pos == "header-right" else None)
        foot = self.hf(cfg["footer"], num if pos.startswith("footer") else None)
        first_plain = num is not None and int(cfg.get("num_from", 1)) > 1
        head_first = self.hf(cfg["header"], None) if first_plain else ""
        foot_first = self.hf(cfg["footer"], None) if first_plain else ""
        hf_props = '<style:header-style><style:header-footer-properties fo:min-height="0cm" fo:margin-bottom="0.3cm"/></style:header-style>' \
                   '<style:footer-style><style:header-footer-properties fo:min-height="0cm" fo:margin-top="0.3cm"/></style:footer-style>'
        # Kopf/Fuß sitzen im Rand: Seitenrand verkleinern, damit der Textbereich gleich groß bleibt
        mt, mb = (t / 2 if head else t), (b / 2 if foot else b)
        master = (f'<style:master-page style:name="Standard" style:page-layout-name="PL1">'
                  + (f"<style:header>{head}</style:header>" if head else "")
                  + (f"<style:header-first>{head_first}</style:header-first>" if first_plain and head else "")
                  + (f"<style:footer>{foot}</style:footer>" if foot else "")
                  + (f"<style:footer-first>{foot_first}</style:footer-first>" if first_plain and foot else "")
                  + "</style:master-page>")
        base = df.BASE_FONT
        heads = "".join(
            f'<style:style style:name="Heading_20_{n}" style:display-name="Heading {n}" style:family="paragraph" '
            f'style:parent-style-name="Heading" style:next-style-name="Standard" style:default-outline-level="{n}">'
            f'<style:text-properties fo:font-size="{size}pt" fo:font-weight="bold"/></style:style>'
            for n, size in ((1, 20), (2, 16), (3, 13)))
        contents = "".join(
            f'<style:style style:name="Contents_20_{n}" style:display-name="Contents {n}" style:family="paragraph" '
            f'style:parent-style-name="Standard"><style:paragraph-properties fo:margin-left="{(n - 1) * 0.5}cm">'
            f'<style:tab-stops><style:tab-stop style:position="{w - l - r - (n - 1) * 5:.0f}mm" style:type="right" '
            f'style:leader-style="dotted" style:leader-text="."/></style:tab-stops></style:paragraph-properties>'
            f'{BOLD_TP if n == 1 else ""}</style:style>' for n in (1, 2, 3))
        lists = (
            '<text:list-style style:name="LBullet">' + "".join(
                f'<text:list-level-style-bullet text:level="{lv}" text:bullet-char="{"•◦▪"[(lv - 1) % 3]}">'
                f'<style:list-level-properties text:list-level-position-and-space-mode="label-alignment">'
                f'<style:list-level-label-alignment text:label-followed-by="listtab" fo:text-indent="-0.5cm" '
                f'fo:margin-left="{0.75 * lv:.2f}cm"/></style:list-level-properties></text:list-level-style-bullet>'
                for lv in range(1, 10)) + '</text:list-style>'
            '<text:list-style style:name="LNumber">' + "".join(
                f'<text:list-level-style-number text:level="{lv}" style:num-suffix="." style:num-format="1">'
                f'<style:list-level-properties text:list-level-position-and-space-mode="label-alignment">'
                f'<style:list-level-label-alignment text:label-followed-by="listtab" fo:text-indent="-0.5cm" '
                f'fo:margin-left="{0.75 * lv:.2f}cm"/></style:list-level-properties></text:list-level-style-number>'
                for lv in range(1, 10)) + '</text:list-style>')
        return (
            f'<?xml version="1.0" encoding="UTF-8"?><office:document-styles {NSDECL} office:version="1.3">'
            f'<office:font-face-decls><style:font-face style:name="{base}" svg:font-family="\'{base}\'"/></office:font-face-decls>'
            f'<office:styles><style:default-style style:family="paragraph"><style:text-properties style:font-name="{base}" '
            f'fo:font-family="\'{base}\'" fo:font-size="11pt" fo:language="de" fo:country="DE"/></style:default-style>'
            f'<style:style style:name="Standard" style:family="paragraph" style:class="text">'
            f'<style:paragraph-properties fo:margin-bottom="0.28cm" fo:line-height="115%"/></style:style>'
            f'<style:style style:name="Heading" style:family="paragraph" style:parent-style-name="Standard" '
            f'style:next-style-name="Standard"><style:paragraph-properties fo:margin-top="0.42cm" fo:margin-bottom="0.21cm" '
            f'fo:keep-with-next="always"/></style:style>{heads}'
            f'<style:style style:name="Title" style:family="paragraph" style:parent-style-name="Standard">'
            f'<style:text-properties fo:font-size="26pt" fo:font-weight="bold"/></style:style>'
            f'<style:style style:name="Quotations" style:family="paragraph" style:parent-style-name="Standard">'
            f'<style:paragraph-properties fo:margin-left="1cm" fo:margin-right="1cm"/>'
            f'<style:text-properties fo:font-style="italic" fo:color="#595959"/></style:style>'
            f'<style:style style:name="Preformatted_20_Text" style:display-name="Preformatted Text" style:family="paragraph" '
            f'style:parent-style-name="Standard"><style:paragraph-properties fo:margin-bottom="0cm" fo:background-color="#f2f2f2"/>'
            f'<style:text-properties style:font-name="{df.MONO_FONT}" fo:font-family="\'{df.MONO_FONT}\'" fo:font-size="10pt"/></style:style>'
            f'<style:style style:name="Footnote" style:family="paragraph" style:parent-style-name="Standard">'
            f'<style:paragraph-properties fo:margin-bottom="0cm"/><style:text-properties fo:font-size="9pt"/></style:style>'
            f'<style:style style:name="Header" style:family="paragraph" style:parent-style-name="Standard">'
            f'<style:paragraph-properties fo:margin-bottom="0cm"/><style:text-properties fo:font-size="9pt" fo:color="#595959"/></style:style>'
            + "".join(f'<style:style style:name="Num{a}" style:family="paragraph" style:parent-style-name="Header">'
                      f'<style:paragraph-properties fo:text-align="{ {"Left": "start", "Center": "center", "Right": "end"}[a]}"/>'
                      f'</style:style>' for a in ("Left", "Center", "Right"))
            + f'<style:style style:name="TabHead" style:family="paragraph" style:parent-style-name="Standard">'
            f'<style:text-properties fo:font-weight="bold"/></style:style>'
            f'<style:style style:name="Contents_20_Heading" style:display-name="Contents Heading" style:family="paragraph" '
            f'style:parent-style-name="Heading"><style:text-properties fo:font-size="16pt" fo:font-weight="bold"/></style:style>'
            f'{contents}{lists}'
            f'<text:notes-configuration text:note-class="footnote" style:num-format="1" text:start-value="0" '
            f'text:footnotes-position="page" text:start-numbering-at="document"/></office:styles>'
            f'<office:automatic-styles><style:page-layout style:name="PL1"><style:page-layout-properties '
            f'fo:page-width="{w}mm" fo:page-height="{h}mm" style:print-orientation="{cfg["orient"]}" '
            f'fo:margin-top="{mt}mm" fo:margin-bottom="{mb}mm" fo:margin-left="{l}mm" fo:margin-right="{r}mm"/>'
            f'{hf_props}</style:page-layout>'
            f'<style:style style:name="Tab" style:family="table"><style:table-properties style:width="{w - l - r}mm" '
            f'table:align="margins"/></style:style>'
            f'<style:style style:name="Cell" style:family="table-cell"><style:table-cell-properties fo:padding="0.1cm" '
            f'fo:border="0.5pt solid #808080"/></style:style>'
            f'</office:automatic-styles><office:master-styles>{master}</office:master-styles></office:document-styles>')


def write_odt(blocks, path, title="", page=None):
    w = _Writer(blocks, page, title)
    body = w.body()
    content = (f'<?xml version="1.0" encoding="UTF-8"?><office:document-content {NSDECL} office:version="1.3">'
               f'<office:automatic-styles>{w.auto_xml()}</office:automatic-styles>'
               f'<office:body><office:text>{body}</office:text></office:body></office:document-content>')
    meta = (f'<?xml version="1.0" encoding="UTF-8"?><office:document-meta {NSDECL} office:version="1.3"><office:meta>'
            f'<dc:title>{esc(title)}</dc:title><meta:generator>notist</meta:generator></office:meta></office:document-meta>')
    files = [("content.xml", "text/xml"), ("styles.xml", "text/xml"), ("meta.xml", "text/xml")]
    manifest = (f'<?xml version="1.0" encoding="UTF-8"?><manifest:manifest xmlns:manifest="{NS["manifest"]}" '
                f'manifest:version="1.3"><manifest:file-entry manifest:full-path="/" manifest:version="1.3" '
                f'manifest:media-type="{MIME}"/>'
                + "".join(f'<manifest:file-entry manifest:full-path="{p}" manifest:media-type="{m}"/>' for p, m in files)
                + "".join(f'<manifest:file-entry manifest:full-path="{p}" manifest:media-type="{m}"/>'
                          for p, _d, m in w.pictures)
                + "</manifest:manifest>")
    with zipfile.ZipFile(path, "w") as z:
        z.writestr(zipfile.ZipInfo("mimetype"), MIME, compress_type=zipfile.ZIP_STORED)   # muss zuerst, unkomprimiert
        z.writestr("content.xml", content, compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("styles.xml", w.styles_xml(), compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("meta.xml", meta, compress_type=zipfile.ZIP_DEFLATED)
        for p, data, _m in w.pictures:
            z.writestr(p, data, compress_type=zipfile.ZIP_STORED)
        z.writestr("META-INF/manifest.xml", manifest, compress_type=zipfile.ZIP_DEFLATED)


# =====================================================================
# Lesen
# =====================================================================
def _length_mm(v, default=None):
    m = re.match(r"([\d.]+)\s*(mm|cm|in|pt|px)?", v or "")
    if not m:
        return default
    x = float(m.group(1))
    return x * {"mm": 1, "cm": 10, "in": 25.4, "pt": 25.4 / 72, "px": 25.4 / 96, None: 1}[m.group(2)]


class _Reader:
    def __init__(self, z):
        self.z = z
        self.styles = {}       # name → {"b","i",..., "parent", "align", "heading", "break", "list"}
        self.list_kind = {}    # Listenstil → bullet/number
        for part in ("styles.xml", "content.xml"):
            root = self.xml(part)
            if root is None:
                continue
            for st in root.iter(q("style:style")):
                self.read_style(st)
            for ls in root.iter(q("text:list-style")):
                first = next(iter(ls), None)
                self.list_kind[ls.get(q("style:name"))] = "number" if first is not None and \
                    first.tag == q("text:list-level-style-number") else "bullet"

    def xml(self, name):
        try:
            return ET.fromstring(self.z.read(name))
        except (KeyError, ET.ParseError):
            return None

    def read_style(self, st):
        name = st.get(q("style:name"))
        d = {"parent": st.get(q("style:parent-style-name")), "display": (st.get(q("style:display-name")) or name or "")}
        tp = st.find(q("style:text-properties"))
        if tp is not None:
            if tp.get(q("fo:font-weight")) in ("bold", "700", "800", "900"):
                d["b"] = True
            if tp.get(q("fo:font-style")) == "italic":
                d["i"] = True
            if tp.get(q("style:text-underline-style")) not in (None, "none"):
                d["u"] = True
            if tp.get(q("style:text-line-through-style")) not in (None, "none"):
                d["s"] = True
            pos = tp.get(q("style:text-position")) or ""
            if pos.startswith("super") or pos.startswith("33%"):
                d["va"] = "sup"
            elif pos.startswith("sub") or pos.startswith("-33%"):
                d["va"] = "sub"
            c = tp.get(q("fo:color"))
            if c and re.fullmatch(r"#[0-9a-fA-F]{6}", c) and c.lower() not in ("#000000",):
                d["color"] = c.lower()
            bg = tp.get(q("fo:background-color"))
            if bg and re.fullmatch(r"#[0-9a-fA-F]{6}", bg):
                d["hl"] = bg.lower()
            fs = tp.get(q("fo:font-size"))
            if fs and fs.endswith("pt"):
                try:
                    d["size"] = float(fs[:-2])
                except ValueError:
                    pass
            fam = tp.get(q("style:font-name")) or tp.get(q("fo:font-family"))
            if fam:
                d["font"] = fam.strip("'")
        pp = st.find(q("style:paragraph-properties"))
        if pp is not None:
            al = pp.get(q("fo:text-align"))
            if al:
                d["align"] = {"center": "center", "end": "right", "right": "right", "justify": "justify"}.get(al, "left")
            if pp.get(q("fo:break-before")) == "page":
                d["break"] = True
            ml = _length_mm(pp.get(q("fo:margin-left")))
            if ml:
                d["indent"] = max(0, min(8, round(ml / 12.5)))
            lh = pp.get(q("fo:line-height"))
            if lh and lh.endswith("%"):
                try:
                    d["spacing"] = round(float(lh[:-1]) / 100 * 1.15, 2)
                except ValueError:
                    pass
            if pp.get(q("fo:border-bottom")) not in (None, "none"):
                d["border"] = True
        self.styles[name] = d

    def chain(self, name):
        seen, out = set(), []
        while name and name not in seen and name in self.styles:
            seen.add(name)
            out.append(self.styles[name])
            name = self.styles[name]["parent"]
        return out

    def get(self, name, key):
        for d in self.chain(name):
            if key in d:
                return d[key]
        return None

    def kind(self, name):
        for d in self.chain(name):
            n = d["display"].lower().replace("_20_", " ")
            if n in ("title", "titel"):
                return "title"
            m = re.match(r"(heading|überschrift)\s*(\d)", n)
            if m:
                return {"1": "h1", "2": "h2"}.get(m.group(2), "h3")
            if "quotation" in n or "zitat" in n:
                return "quote"
            if "preformatted" in n or "code" in n:
                return "code"
        return "normal"

    def run_props(self, sname, base):
        r = dict(base)
        for d in reversed(self.chain(sname)):
            for k in ("b", "i", "u", "s", "va", "color", "hl", "font", "size"):
                if k in d:
                    r[k] = d[k]
        return r

    def runs(self, el, props, out, notes):
        if el.text:
            out.append({**props, "text": el.text})
        for c in el:
            tag = c.tag
            if tag == q("text:span"):
                self.runs(c, self.run_props(c.get(q("text:style-name")), props), out, notes)
            elif tag == q("text:a"):
                self.runs(c, {**props, "link": c.get(q("xlink:href"))}, out, notes)
            elif tag == q("text:s"):
                out.append({**props, "text": " " * int(c.get(q("text:c"), "1"))})
            elif tag == q("text:tab"):
                out.append({**props, "text": "\t"})
            elif tag == q("text:line-break"):
                out.append({**props, "text": " "})
            elif tag == q("text:note"):
                body = c.find(q("text:note-body"))
                txt = " ".join("".join(p.itertext()).strip() for p in body) if body is not None else ""
                out.append({"fn": txt.strip(), "text": ""})
            elif tag == q("draw:frame"):
                img = c.find(q("draw:image"))
                if img is not None:
                    href = img.get(q("xlink:href"))
                    try:
                        data = self.z.read(href)
                        mime = df.sniff_mime(data)
                        if mime:
                            w = _length_mm(c.get(q("svg:width")))
                            h = _length_mm(c.get(q("svg:height")))
                            px = 96 / 25.4
                            out.append({"img": base64.b64encode(data).decode(), "mime": mime,
                                        "w": round(w * px) if w else df.image_size(data)[0],
                                        "h": round(h * px) if h else df.image_size(data)[1]})
                    except KeyError:
                        pass
            elif tag in (q("text:page-number"), q("text:page-count"), q("text:date"), q("text:title")):
                out.append({**props, "text": "".join(c.itertext())})
            elif tag in (q("text:bookmark"), q("text:bookmark-start"), q("text:bookmark-end"), q("text:soft-page-break")):
                pass
            else:
                self.runs(c, props, out, notes)
            if c.tail:
                out.append({**props, "text": c.tail})
        return out

    def para(self, el, list_kind=None, level=0):
        sname = el.get(q("text:style-name"))
        b = df.para()
        if el.tag == q("text:h"):
            lv = int(el.get(q("text:outline-level"), "1"))
            b["style"] = {1: "h1", 2: "h2"}.get(lv, "h3")
        else:
            b["style"] = self.kind(sname)
        b["align"] = self.get(sname, "align") or "left"
        b["spacing"] = self.get(sname, "spacing") or 1.15
        if list_kind:
            b["list"], b["indent"] = list_kind, level
            if b["style"] in ("title", "h1", "h2", "h3"):
                b["style"] = "normal"
        elif self.get(sname, "indent"):
            b["indent"] = self.get(sname, "indent")
        base = {}
        if b["style"] == "normal":
            for k in ("b", "i", "color", "font"):
                v = self.get(sname, k)
                if v:
                    base[k] = v
        b["runs"] = df.merge_runs(self.runs(el, base, [], []))
        out = []
        if self.get(sname, "break"):
            out.append({"t": "pb"})
        if self.get(sname, "border") and not b["runs"]:
            out.append({"t": "hr"})
        else:
            out.append(b)
        return out

    def list_items(self, lst, kind, level, out):
        kind = self.list_kind.get(lst.get(q("text:style-name")), kind)
        for item in lst:
            if item.tag not in (q("text:list-item"), q("text:list-header")):
                continue
            for c in item:
                if c.tag in (q("text:p"), q("text:h")):
                    out.extend(self.para(c, kind, level))
                elif c.tag == q("text:list"):
                    self.list_items(c, kind, level + 1, out)

    def blocks(self, container, out):
        for el in container:
            tag = el.tag
            if tag in (q("text:p"), q("text:h")):
                out.extend(self.para(el))
            elif tag == q("text:list"):
                self.list_items(el, "bullet", 0, out)
            elif tag == q("table:table"):
                rows = []
                for tr in el.iter(q("table:table-row")):
                    row = []
                    for tc in tr:
                        if tc.tag == q("table:table-cell"):
                            row.append("\n".join("".join(p.itertext()) for p in tc if p.tag == q("text:p")))
                            rep = int(tc.get(q("table:number-columns-repeated"), "1"))
                            row.extend([""] * min(rep - 1, 20))
                    rows.append(row)
                out.append({"t": "table", "rows": rows or [[""]]})
            elif tag == q("text:table-of-content"):
                out.append({"t": "toc"})
            elif tag in (q("text:section"), q("office:text")):
                self.blocks(el, out)
        return out

    def page(self):
        pg = df.page_defaults()
        root = self.xml("styles.xml")
        if root is None:
            return pg
        master = root.find(f".//{q('style:master-page')}")
        layout_name = master.get(q("style:page-layout-name")) if master is not None else None
        for pl in root.iter(q("style:page-layout")):
            if layout_name and pl.get(q("style:name")) != layout_name:
                continue
            p = pl.find(q("style:page-layout-properties"))
            if p is None:
                continue
            w, h = _length_mm(p.get(q("fo:page-width"))), _length_mm(p.get(q("fo:page-height")))
            if w and h:
                pg["orient"] = "landscape" if w > h else "portrait"
                a, b = min(w, h), max(w, h)
                pg["size"] = min(df.PAGE_SIZES, key=lambda k: abs(df.PAGE_SIZES[k][0] - a) + abs(df.PAGE_SIZES[k][1] - b))
            m = [_length_mm(p.get(q(f"fo:margin-{s}")), 20) for s in ("top", "right", "bottom", "left")]
            pg["margins"] = [round(x, 1) for x in m]
            break
        if master is not None:
            for tag, key in (("style:header", "header"), ("style:footer", "footer")):
                el = master.find(q(tag))
                if el is None:
                    continue
                # beim Schreiben liegt Kopf/Fuß im halben Rand – hier den vollen Rand zurückrechnen
                idx = 0 if key == "header" else 2
                pg["margins"][idx] = round(pg["margins"][idx] * 2, 1)
                texts, has_num = [], False
                for p in el.iter(q("text:p")):
                    if p.find(f".//{q('text:page-number')}") is not None:
                        has_num = True
                        al = self.get(p.get(q("text:style-name")), "align") or "left"
                        pg["numbers"] = "header-right" if key == "header" else \
                            {"center": "footer-center", "right": "footer-right"}.get(al, "footer-left")
                        pg["num_fmt"] = "page-of" if p.find(f".//{q('text:page-count')}") is not None else "n"
                        continue
                    t = "".join(p.itertext()).strip()
                    if t:
                        texts.append(t)
                pg[key] = " · ".join(texts)
                if has_num and master.find(q(tag + "-first")) is not None:
                    pg["num_from"] = 2
        return pg


def read_odt(path):
    with zipfile.ZipFile(path) as z:
        rd = _Reader(z)
        root = rd.xml("content.xml")
        if root is None:
            raise ValueError("Keine gültige ODT-Datei (content.xml fehlt)")
        text = root.find(f"{q('office:body')}/{q('office:text')}")
        blocks = rd.blocks(text, []) if text is not None else []
        page = rd.page()
        title = ""
        meta = rd.xml("meta.xml")
        if meta is not None:
            t = meta.find(f".//{q('dc:title')}")
            title = (t.text or "").strip() if t is not None else ""
    while len(blocks) > 1 and blocks[-1]["t"] == "p" and not blocks[-1]["runs"]:
        blocks.pop()
    return blocks or [df.para()], title, page
