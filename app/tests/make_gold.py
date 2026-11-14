# Erzeugt die Gold-Modelle (tests/gold/*.json) – handgebaut, keine Nutzerdaten. Aufruf: python tests/make_gold.py
import base64, json, os, struct, zlib

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "gold")


def png(w=8, h=6, rgb=(200, 60, 60)):
    raw = b"".join(b"\x00" + bytes(rgb) * w for _ in range(h))
    def chunk(t, d):
        c = struct.pack(">I", len(d)) + t + d
        return c + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


IMG = base64.b64encode(png()).decode()


def P(*runs, **kw):
    p = {"t": "p", "style": "normal", "align": "left", "indent": 0, "list": None, "spacing": 1.15,
         "runs": [r if isinstance(r, dict) else {"text": r} for r in runs]}
    p.update(kw)
    return p


def T(rows, **style):
    b = {"t": "table", "rows": rows}
    if style:
        b["style"] = style
    return b


docs = {}   # name -> {"kind": "docs"|"notes", "blocks": [...], "page": {...}|None, "note": {...}}


def add(name, blocks, page=None, kind="docs", **note):
    docs[name] = {"kind": kind, "blocks": blocks, "page": page, "note": note}


add("01_absatz_einfach", [P("Hallo Welt."), P("Zweiter Absatz mit zwei Sätzen. Noch einer.")])
for st in ("title", "h1", "h2", "h3", "quote", "code"):
    pass
add("02_formatvorlagen", [P(f"Vorlage {s}", style=s) for s in ("title", "h1", "h2", "h3", "quote", "code", "normal")])
add("03_ausrichtung", [P(f"Zeile {a}", align=a) for a in ("left", "center", "right", "justify")])
add("04_laufschluessel", [P(
    {"text": "fett", "b": True}, " ", {"text": "kursiv", "i": True}, " ", {"text": "unterstrichen", "u": True}, " ",
    {"text": "durch", "s": True}, " x", {"text": "2", "va": "sup"}, " H", {"text": "2", "va": "sub"}, " ",
    {"text": "Schrift", "font": "Noto Serif"}, " ", {"text": "groß", "size": 18}, " ",
    {"text": "rot", "color": "#cc0000"}, " ", {"text": "markiert", "hl": "#ffff00"}, " ",
    {"text": "Link", "link": "https://example.org/a?b=1&c=2"}, " ",
    {"text": "alles", "b": True, "i": True, "u": True, "color": "#0000cc", "size": 14})])
add("05_listen", [P("Punkt A", list="bullet"), P("Unterpunkt", list="bullet", indent=1), P("Punkt B", list="bullet"),
                  P("Eins", list="number"), P("Zwei", list="number"), P("Zwei-a", list="number", indent=1),
                  P("Drei", list="number"), P("Absatz dazwischen"), P("Neu eins", list="number")])
add("06_abstand_einzug", [P("eng", spacing=1.0), P("weit", spacing=2.0), P("eingerückt", indent=2), P("normal")])
add("07_tabelle_einfach", [P("Vor Tabelle"), T([["A", "B", "C"], ["1", "2", "3"], ["x", "y\nzweite Zeile", "z"]]), P("Nach Tabelle")])
add("08_tabelle_design", [T([["Name", "Wert"], ["a", "1"], ["b", "2"], ["c", "3"]], head=True, first_col=True, stripes=True,
                            border="rows", accent="#3b8f94", pad="wide", align=["left", "right"], widths=[200, 100]),
                          P(""), T([["x", "y"], ["1", "2"]], head=False, border="outer", pad="compact"),
                          P(""), T([["n", "o"], ["1", "2"]], border="none")])
add("09_seitenumbruch_linie", [P("Seite eins"), {"t": "hr"}, P("nach Linie"), {"t": "pb"}, P("Seite zwei")])
add("10_bild", [P("Bild: ", {"img": IMG, "mime": "image/png", "w": 80, "h": 60}, " im Text"),
                P({"img": IMG, "mime": "image/png", "w": 120, "h": 90}, align="center")])
add("11_bild_schwebend", [P({"img": IMG, "mime": "image/png", "w": 80, "h": 60, "fl": "front"}, "Text neben schwebendem Bild."),
                          P({"img": IMG, "mime": "image/png", "w": 60, "h": 45, "fl": "back"}, "Dahinter.")])
add("12_fussnoten", [P("Text", {"text": "", "fn": "Erste Fußnote."}, " weiter", {"text": "", "fn": "Zweite, mit ä ö ü."}, ".")])
add("13_inhaltsverzeichnis", [{"t": "toc"}, P("Kapitel 1", style="h1"), P("Text"), P("Abschnitt 1.1", style="h2"),
                              P("Text"), P("Kapitel 2", style="h1"), P("Text")])
add("14_kommentare", [P("Vorher ", {"text": "kommentiert", "cm": "c1"}, " nachher.")],
    page={"comments": {"c1": {"author": "Tester", "text": "Ein Kommentar", "time": "2026-01-02T03:04:05"}}, "author": "Tester"})
add("15_aenderungen", [P("Alt ", {"text": "eingefügt", "tc": "ins"}, {"text": " gelöscht", "tc": "del"}, " Ende.")],
    page={"track": True, "author": "Tester"})
add("16_seite", [P("Quer, andere Ränder"), P("Zweiter Absatz")],
    page={"size": "Letter", "orient": "landscape", "margins": [20, 30, 20, 30], "numbers": "footer-right", "num_fmt": "page-of",
          "header": "Kopf", "footer": "Fuß", "lnum": "continuous", "lnum_step": 5, "watermark": "ENTWURF", "page_color": "#fff8e0"})
add("17_sonderzeichen", [P("Umlaute äöüÄÖÜß, Akzente éèê, ñ, ç, Œ"), P("Symbole: ☐ ☑ → ≤ ≥ ∑ √ € © ™"),
                         P("Außerhalb BMP: 😀 🚀 𝔸 𠀀"), P("XML: <a href=\"x\">&amp;</a> ]]> ' \""),
                         P("Markdown: * _ # [ ] ( ) ` | \\ > - + ~"), P("Tab\tund  zwei  Leerzeichen")])
add("18_pdf_block", [P("Vor PDF"), {"t": "pdf", "file": "gold-0000.pdf", "name": "Gold.pdf", "pages": 3}, P("Nach PDF")])
add("19_sheet_block", [P("Vor Tabelle"), {"t": "sheet", "file": "gold-0000.xlsx", "name": "Gold.xlsx", "sheets": ["Blatt1"],
                                          "cur": 0, "nrows": 2, "ncols": 2}, P("Nach Tabelle")])
add("20_leer", [P("")])
add("21_gemischt", [P("Titel", style="title", align="center"), P("Einleitung mit ", {"text": "fett", "b": True}, " und Link ",
                                                                  {"text": "hier", "link": "https://example.org"}, "."),
                    P("Liste", list="bullet"), T([["a", "b"], ["c", "d"]]), P("Schluss", style="quote"),
                    P("code()", style="code")])
add("22_lange_zeile", [P("Wort " * 400)])
# Notizen (kind=notes): Text + rich-Spans + Häkchen + Tabellen + Bilder
add("23_notiz_text", [], kind="notes", title="Einkauf", text="Einkauf\n☐ Milch\n☑ Brot\n☐ Äpfel 😀\nEnde", rich=[])
add("24_notiz_rich", [], kind="notes", title="Rich", text="Fett kursiv unterstrichen durchgestrichen Mono Ende",
    rich=[[0, 4, "bold"], [5, 11, "italic"], [12, 26, "underline"], [27, 41, "strike"], [42, 46, "font:Noto Sans Mono"],
          [0, 4, "italic"]])
add("25_notiz_tabelle_bild", [], kind="notes", title="Tab+Bild", text="Vor\ufffc\nMitte\ufffc\nEnde",
    rich=[], images=[{"table": {"rows": [["a", "b"], ["c", "d"]], "style": {"head": True}}},
                     {"img": IMG, "mime": "image/png", "w": 80}])
add("26_notiz_liste_sonder", [], kind="notes", title="Sonder", text="• Punkt 😀\n1. Eins\n2. Zwei 𝔸\n☐ ä ö ü ß ☑",
    rich=[[2, 9, "bold"]])


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for name, d in docs.items():
        with open(os.path.join(OUT, name + ".json"), "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=1)
    print(len(docs), "Gold-Modelle in", OUT)
