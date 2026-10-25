# Zusätzliche Ausgabeformate ohne externe Programme: RTF, EPUB, ZIP (LaTeX-Projekt). Eingabe = Blockmodell (docfmt).
import html
import os
import re
import uuid
import zipfile
from xml.sax.saxutils import escape

import docfmt as df

# Alle Formate für „Als Datei speichern“: Schlüssel → (Symbol, Name, Endung, Bereiche)
FORMATS = {
    "pdf": ("󰈦", "PDF", ".pdf", ("notes", "docs", "latex")),
    "txt": ("󰦨", "Text", ".txt", ("notes", "docs", "latex")),
    "docx": ("󰈬", "Word-Dokument", ".docx", ("notes", "docs")),
    "md": ("󰍔", "Markdown", ".md", ("notes", "docs")),
    "html": ("󰖟", "Webseite", ".html", ("notes", "docs")),
    "odt": ("󰈙", "LibreOffice-Dokument", ".odt", ("notes", "docs")),
    "rtf": ("󰈮", "Rich Text", ".rtf", ("notes", "docs")),
    "epub": ("󰂺", "E-Book", ".epub", ("notes", "docs")),
    "tex": ("Σ", "LaTeX-Quelltext", ".tex", ("latex",)),
    "zip": ("󰗄", "Projekt als ZIP", ".zip", ("latex",)),
}
DEFAULT_PINNED = ["pdf", "txt", "docx", "md", "html"]


# ---------------------------------------------------------------- RTF
def _rtf_text(s):
    out = []
    for ch in s:
        o = ord(ch)
        if ch in "\\{}":
            out.append("\\" + ch)
        elif ch == "\n":
            out.append("\\line ")
        elif ch == "\t":
            out.append("\\tab ")
        elif o < 128:
            out.append(ch)
        else:
            if o > 0xFFFF:                       # Ersatzpaar
                o -= 0x10000
                out.append(f"\\u{((o >> 10) + 0xD800) - 65536}?\\u{((o & 0x3FF) + 0xDC00) - 65536}?")
            else:
                out.append(f"\\u{o - 65536 if o > 32767 else o}?")
    return "".join(out)


def to_rtf(blocks, title=""):
    blocks = df.accept_all(blocks)
    fonts = [df.BASE_FONT, df.MONO_FONT]
    colors = []

    def font_id(name):
        if name not in fonts:
            fonts.append(name)
        return fonts.index(name)

    def color_id(hexcol):
        h = hexcol.lstrip("#")
        if len(h) != 6:
            return 0
        if h not in colors:
            colors.append(h)
        return colors.index(h) + 1

    nums = df.list_numbers(blocks)
    body = []
    for i, b in enumerate(blocks):
        if b["t"] == "pb":
            body.append("\\page ")
            continue
        if b["t"] == "hr":
            body.append("\\pard\\brdrb\\brdrs\\brdrw10\\par ")
            continue
        if b["t"] == "table":
            for row in b.get("rows", []):
                body.append("\\trowd" + "".join(f"\\cellx{(c + 1) * 2000}" for c in range(len(row))))
                for cell in row:
                    body.append("\\intbl " + _rtf_text(str(cell)) + "\\cell ")
                body.append("\\row ")
            body.append("\\pard ")
            continue
        if b["t"] != "p":
            continue
        style = b.get("style", "normal")
        size, bold, ital = df.STYLE_FMT.get(style, df.STYLE_FMT["normal"])
        mono = style == "code"
        al = {"left": "\\ql", "center": "\\qc", "right": "\\qr", "justify": "\\qj"}.get(b.get("align"), "\\ql")
        ind = int(b.get("indent", 0) or 0) * 720 + (360 if style == "quote" else 0)
        sp = int((b.get("spacing") or 1.15) * 240)
        p = [f"\\pard{al}\\li{ind}\\sl{sp}\\slmult1\\sa120"]
        if b.get("list"):
            mark = "\\u8226?" if b["list"] == "bullet" else f"{nums.get(i, 1)}."
            p.append(f"\\fi-360 {mark}\\tab ")
        for r in b.get("runs", []):
            if r.get("fn") is not None:
                p.append(f"{{\\super [{_rtf_text(str(r['fn']))}]}}")
                continue
            if r.get("img"):
                continue
            t = r.get("text", "")
            if not t:
                continue
            f = font_id(r["font"]) if r.get("font") else (1 if mono else 0)
            sz = r.get("size") or size
            fl = f"\\f{f}\\fs{int(round(sz * 2))}"
            if r.get("b") or bold:
                fl += "\\b"
            if r.get("i") or ital:
                fl += "\\i"
            if r.get("u"):
                fl += "\\ul"
            if r.get("s"):
                fl += "\\strike"
            if r.get("va") == "sup":
                fl += "\\super"
            elif r.get("va") == "sub":
                fl += "\\sub"
            if r.get("color"):
                fl += f"\\cf{color_id(r['color'])}"
            if r.get("hl"):
                fl += f"\\highlight{color_id(r['hl'])}"
            txt = _rtf_text(t)
            if r.get("link"):
                url = r["link"].replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")
                p.append(f'{{\\field{{\\*\\fldinst HYPERLINK "{url}"}}{{\\fldrslt {{{fl} {txt}}}}}}}')
            else:
                p.append(f"{{{fl} {txt}}}")
        p.append("\\par ")
        body.append("".join(p))
    ft = "".join(f"{{\\f{i} {_rtf_text(n)};}}" for i, n in enumerate(fonts))
    ct = "{\\colortbl ;" + "".join(
        f"\\red{int(c[0:2], 16)}\\green{int(c[2:4], 16)}\\blue{int(c[4:6], 16)};" for c in colors) + "}"
    head = f"{{\\rtf1\\ansi\\deff0\\uc1{{\\fonttbl{ft}}}{ct}{{\\info{{\\title {_rtf_text(title)}}}}}\n"
    return head + "\n".join(body) + "}"


def write_rtf(blocks, path, title=""):
    with open(path, "w", encoding="ascii", errors="replace") as f:
        f.write(to_rtf(blocks, title))


# ---------------------------------------------------------------- EPUB
def write_epub(blocks, path, title=""):
    blocks = df.accept_all(blocks)
    """EPUB 3: ein Kapitel (die ganze Seite als XHTML), Inhaltsverzeichnis aus den Überschriften."""
    page = df.to_html(blocks, title or "Dokument")
    body = re.search(r"<body>(.*)</body>", page, re.S)
    body = body.group(1) if body else page
    body = re.sub(r"&([A-Za-z][A-Za-z0-9]*);",
                  lambda m: m.group(0) if m.group(1) in ("amp", "lt", "gt", "quot", "apos") else
                  (f"&#{ord(html.unescape(m.group(0)))};" if len(html.unescape(m.group(0))) == 1 else m.group(0)), body)
    body = re.sub(r"<(br|hr|col|img|input|wbr)\b([^>]*?)(?<!/)>", r"<\1\2/>", body)       # leere Elemente für XHTML
    name = escape(title or "Dokument")
    uid = "urn:uuid:" + str(uuid.uuid4())
    chapter = ('<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE html>\n'
               '<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" lang="de">'
               f"<head><meta charset=\"utf-8\"/><title>{name}</title></head><body>{body}</body></html>")
    nav = ('<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE html>\n'
           '<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" lang="de">'
           f'<head><meta charset="utf-8"/><title>{name}</title></head><body><nav epub:type="toc"><ol>'
           f'<li><a href="chapter.xhtml">{name}</a></li></ol></nav></body></html>')
    opf = ('<?xml version="1.0" encoding="utf-8"?>\n'
           '<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="id">'
           '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
           f'<dc:identifier id="id">{uid}</dc:identifier><dc:title>{name}</dc:title><dc:language>de</dc:language>'
           '<meta property="dcterms:modified">2026-01-01T00:00:00Z</meta></metadata>'
           '<manifest><item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>'
           '<item id="c1" href="chapter.xhtml" media-type="application/xhtml+xml"/></manifest>'
           '<spine><itemref idref="c1"/></spine></package>')
    container = ('<?xml version="1.0"?><container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
                 '<rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>'
                 '</rootfiles></container>')
    with zipfile.ZipFile(path, "w") as z:
        z.writestr(zipfile.ZipInfo("mimetype"), "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        z.writestr("META-INF/container.xml", container, compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("OEBPS/content.opf", opf, compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("OEBPS/nav.xhtml", nav, compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("OEBPS/chapter.xhtml", chapter, compress_type=zipfile.ZIP_DEFLATED)


# ---------------------------------------------------------------- ZIP (LaTeX-Projektordner)
def zip_dir(src, path, skip=(".aux", ".log", ".out", ".synctex.gz", ".toc", ".fls", ".fdb_latexmk", ".bbl", ".blg")):
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for root, _dirs, files in os.walk(src):
            for f in files:
                if f.endswith(skip) or f.endswith(".notist-tmp"):
                    continue
                p = os.path.join(root, f)
                z.write(p, os.path.relpath(p, src))
