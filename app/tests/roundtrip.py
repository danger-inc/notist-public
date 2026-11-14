# Format-Rundlauf-Test (ohne GTK): Gold-Modelle + Zufallsmodelle → DOCX/ODT/MD/HTML/RTF/EPUB/.notes → zurück → Vergleich.
# Aufruf: python tests/roundtrip.py [-v] [--n 500] [--seed 7] [--only NAME]
# Bewusste Verluste je Format stehen in MASK (Merkmale, die das Format nicht kennt) und in tests/gold/VERLUSTE.md.
import argparse, base64, hashlib, json, os, random, re, sys, tempfile, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
os.environ.setdefault("NOTES_NO_TIMERS", "1")
import docfmt as df                                    # noqa: E402

GOLD = os.path.join(HERE, "gold")
P_KEYS = ("style", "align", "indent", "list")

# Was ein Format NICHT behält (wird vor dem Vergleich aus Original UND Ergebnis entfernt):
#   run:   Laufschlüssel   para: Absatzschlüssel   block: Blockarten   page: Seitenschlüssel
MASK = {
    "docx": {"run": (), "para": (), "block": ("pdf", "sheet"), "page": ("author", "track", "page_color", "watermark"),
             "table_infer": True},
    "odt":  {"accept": True, "run": ("cm", "tc", "fl"), "para": (), "block": ("pdf", "sheet"),
             "page": ("author", "track", "comments", "lnum", "lnum_step", "page_color", "watermark"),
             "table_keys": ("stripes", "accent", "align", "border", "first_col", "pad", "widths", "head")},
    "md":   {"accept": True, "style_map": {"title": "h1"}, "run": ("u", "va", "font", "size", "color", "hl", "cm", "tc", "fl", "w", "h", "mime"),
             "para": ("align", "spacing", "indent"), "block": ("pb", "toc", "pdf", "sheet"), "page": ("*",),
             "img": True, "table_style": True, "blank": True, "cell_nl": True, "ws": True, "code_plain": True},
    "html": {"accept": True, "style_map": {"title": "h1"}, "run": ("size", "font", "color", "hl", "cm", "tc", "fl"),
             "para": ("spacing",), "block": ("pb", "toc", "pdf", "sheet"), "page": ("*",), "table_style": True,
             "blank": True, "ws": True},
}
# Gold-Modelle, bei denen ein Textformat bewusst nur den Text behält (Grund in tests/gold/VERLUSTE.md)
EXEMPT = {"10_bild": ("md", "html"), "11_bild_schwebend": ("md", "html"), "12_fussnoten": ("md", "html"),
          "13_inhaltsverzeichnis": ("md", "html"), "17_sonderzeichen": ("md",)}


# ---------------------------------------------------------------- Normalisieren
def _img_id(r):
    return hashlib.md5(base64.b64decode(r["img"])).hexdigest()[:8] if r.get("img") else None


def norm_runs(runs, mask, cms=None):
    out = []
    for r in df.merge_runs(runs):
        d = {k: v for k, v in r.items() if k not in ("img", "text") and v not in (None, False, "")}
        if "size" in d:
            d["size"] = float(d["size"])
        if "cm" in d and cms is not None:                      # Kommentar-Ids werden beim Speichern neu vergeben
            d["cm"] = cms.setdefault(d["cm"], len(cms))
        if r.get("img"):
            d["img"] = _img_id(r)
            for k in ("mime", "w", "h"):
                if r.get(k) is not None:
                    d[k] = r[k]
        else:
            d["text"] = r.get("text", "")
            if mask.get("ws"):
                d["text"] = re.sub(r"\s+", " ", d["text"])
        for k in mask.get("run", ()):
            d.pop(k, None)
        if d.get("link"):
            d.pop("u", None)                      # Links erscheinen in Word/LibreOffice ohnehin unterstrichen
        if mask.get("img") and d.get("img"):
            continue                              # Bilder entfallen in Markdown
        out.append(d)
    if mask.get("ws"):                  # Leerraum trägt keine Formatierung (Textformate schieben ihn aus **…** heraus)
        flat = []
        for d in out:
            if "text" in d and not d.get("fn") and "img" not in d:
                for ch in d["text"]:
                    flat.append({"text": ch} if ch.isspace() else dict(d, text=ch))
            else:
                flat.append(d)
        out = flat
    # gleiche Formatierung nach dem Maskieren wieder zusammenlegen
    res = []
    for d in out:
        if res and "text" in d and "text" in res[-1] and {k: v for k, v in d.items() if k != "text"} == \
                {k: v for k, v in res[-1].items() if k != "text"}:
            res[-1]["text"] += d["text"]
        else:
            res.append(d)
    return [d for d in res if d.get("text") != "" or "img" in d or "fn" in d]


def norm_table_style(b, mask):
    st = df.table_style(b)
    st["widths"] = [round(x, 2) for x in df.table_widths(st, max(len(r) for r in b["rows"]))] if st.get("widths") else []
    if mask.get("table_infer"):               # Word kennt keine „Streifen“/„Akzent“ als Merkmal: sie werden aus der Optik erschlossen
        nrow, ncol = len(b["rows"]), max(len(r) for r in b["rows"])
        if st["stripes"] and nrow - (1 if st["head"] else 0) < 2:
            st["stripes"] = False                 # bei einer Zeile Inhalt unsichtbar
        if not st["head"]:
            st["accent"] = None                   # Akzentfarbe sieht man nur an der Kopfzeile
        if ncol == 1 and st["first_col"]:
            st.update(head=True, first_col=False, accent=None)          # alles fett = „Kopfzeile“
    st = df.table_style_min(st)
    for k in mask.get("table_keys", ()):
        st.pop(k, None)
    return st


PLACEHOLDER = ("[Gold.pdf]", "[Gold.xlsx]")


def norm_blocks(blocks, mask, cms=None):
    out = []
    if mask.get("accept"):
        blocks = df.accept_all(blocks)                         # Textformate kennen keine Änderungsverfolgung
    cms = {} if cms is None else cms
    for b in blocks:
        t = b["t"]
        if t in mask.get("block", ()):
            continue
        if t == "p" and "".join(r.get("text", "") for r in b["runs"]) in PLACEHOLDER:
            continue
        if t == "table" and b["rows"] == [[PLACEHOLDER[1]]]:
            continue
        if t == "p":
            d = {"t": "p", "runs": norm_runs(b["runs"], mask, cms)}
            for k in P_KEYS + ("spacing",):
                if k in mask.get("para", ()):
                    continue
                v = b.get(k)
                if k == "spacing":
                    v = round(v or 1.15, 2)
                if k == "style":
                    v = mask.get("style_map", {}).get(v, v)
                d[k] = v
            if mask.get("blank") and not d["runs"]:
                continue
            if mask.get("code_plain") and d.get("style") == "code":     # Code-Absätze behalten in Markdown keine Auszeichnung
                d["runs"] = norm_runs([{"text": "".join(r.get("text", "") for r in b["runs"] if not r.get("img"))}], mask, cms)
            out.append(d)
        elif t == "table":
            d = {"t": "table", "rows": [[str(c).replace("\n", " ") if mask.get("cell_nl") else str(c) for c in row]
                                         for row in b["rows"]]}
            if not mask.get("table_style"):
                d["style"] = norm_table_style(b, mask)
            out.append(d)
        elif t in ("pdf", "sheet"):
            out.append({"t": t, "name": b.get("name")})
        else:
            out.append({"t": t})
    # Leerabsätze am Ende ignorieren; Leerabsatz zwischen zwei Blöcken bleibt
    while out and out[-1]["t"] == "p" and not out[-1]["runs"]:
        out.pop()
    return out


def norm_comments(page, blocks):
    """Kommentare in Reihenfolge ihres Vorkommens → [(Text, Autor)] (Ids und Zeitstempel sind nicht vergleichbar)."""
    cm = (df.norm_page(page).get("comments") or {})
    order = []
    for b in blocks:
        for r in b.get("runs", []) if b["t"] == "p" else []:
            if r.get("cm") and r["cm"] not in order:
                order.append(r["cm"])
    return [(cm.get(k, {}).get("text"), cm.get(k, {}).get("author")) for k in order]


def norm_page(page, mask):
    if "*" in mask.get("page", ()):
        return {}
    p = df.norm_page(page)
    base = df.norm_page(None)
    d = {k: v for k, v in p.items() if v != base[k] and k not in mask.get("page", ()) and k != "comments"}
    return d


# ---------------------------------------------------------------- Rundläufe
def rt_docx(blocks, page, tmp):
    f = os.path.join(tmp, "x.docx")
    df.write_docx(blocks, f, title="T", page=page)
    b, _t, p = df.read_docx_full(f)
    return b, p


def rt_odt(blocks, page, tmp):
    import odf
    f = os.path.join(tmp, "x.odt")
    odf.write_odt(blocks, f, title="T", page=page)
    b, _t, p = odf.read_odt(f)
    return b, p


def rt_md(blocks, page, tmp):
    return df.markdown_blocks(df.to_markdown(blocks), loose=True), None


def rt_html(blocks, page, tmp):
    f = os.path.join(tmp, "x.html")
    with open(f, "w", encoding="utf-8") as fh:
        fh.write(df.to_html(blocks, "T"))
    r = df.read_html(f)
    return (r[0] if isinstance(r, tuple) else r), None


ROUNDTRIPS = {"docx": rt_docx, "odt": rt_odt, "md": rt_md, "html": rt_html}


def text_only(a, b):
    """Für bewusst verlustbehaftete Textformate: alle Wörter des Originals müssen im Ergebnis vorkommen."""
    ta = df.plain_text(df.accept_all(a))
    tb = df.plain_text(df.accept_all(b)) + " " + " ".join(r.get("fn", "") or "" for x in b if x["t"] == "p" for r in x["runs"])
    miss = [w for w in ta.split() if w.isalpha() and w not in tb]
    return [f"Wörter fehlen: {miss[:5]}"] if miss else []


def only_write(blocks, page, tmp):
    """RTF/EPUB: nur schreiben (kein Leser) – Text muss im Ergebnis stecken."""
    import exports
    fails = []
    text = " ".join(r.get("text", "") for b in df.accept_all(blocks) if b["t"] == "p" for r in b["runs"]
                    if not r.get("va") and not r.get("img"))
    words = [w for w in text.split() if w.isalnum() and w.isascii()][:5]
    f = os.path.join(tmp, "x.rtf")
    exports.write_rtf(blocks, f, "T")
    with open(f, "rb") as fh:
        rtf = fh.read().decode("latin-1")
    for w in words:
        if w not in rtf:
            fails.append(f"rtf: Wort {w!r} fehlt")
    f = os.path.join(tmp, "x.epub")
    exports.write_epub(blocks, f, "T")
    with zipfile.ZipFile(f) as z:
        if z.testzip() is not None:
            fails.append("epub: kaputtes Zip")
        body = "".join(z.read(n).decode("utf-8", "replace") for n in z.namelist() if n.endswith((".xhtml", ".html")))
    for w in words:
        if w not in body:
            fails.append(f"epub: Wort {w!r} fehlt")
    return fails


# ---------------------------------------------------------------- Vergleich
def diff(a, b, path=""):
    if type(a) is not type(b):
        return [f"{path}: {a!r} ≠ {b!r}"]
    if isinstance(a, dict):
        out = []
        for k in sorted(set(a) | set(b)):
            if k not in a:
                out.append(f"{path}.{k}: fehlt im Original, Ergebnis {b[k]!r}")
            elif k not in b:
                out.append(f"{path}.{k}: Original {a[k]!r}, fehlt im Ergebnis")
            else:
                out += diff(a[k], b[k], f"{path}.{k}")
        return out
    if isinstance(a, list):
        if len(a) != len(b):
            return [f"{path}: Länge {len(a)} ≠ {len(b)}  ({_short(a)} ≠ {_short(b)})"]
        out = []
        for i, (x, y) in enumerate(zip(a, b)):
            out += diff(x, y, f"{path}[{i}]")
        return out
    return [] if a == b else [f"{path}: {a!r} ≠ {b!r}"]


def _short(x):
    s = json.dumps(x, ensure_ascii=False)
    return s if len(s) < 160 else s[:157] + "…"


# ---------------------------------------------------------------- Notizen
def check_note(n):
    """Notiz → MD → Notiz und → .notes-Bündel → Notiz."""
    import mdnotes
    fails = []
    text, rich = n["text"], n.get("rich") or []
    if "￼" not in text:
        md = mdnotes.from_note(text, rich, "", n.get("images"))
        t2, r2 = mdnotes.to_note(md)
        plain = lambda s: "".join(ch for ch in s if ch.isalnum())          # noqa: E731
        if plain(t2).replace("•", "") != plain(text).replace("•", ""):
            fails.append(f"md: Text {plain(text)!r} → {plain(t2)!r}")
        names = lambda r, s: sorted({(s[a:b].strip(), nm) for a, b, nm in r if s[a:b].strip()})   # noqa: E731
        want = {(w, nm) for w, nm in names(rich, text) if nm in ("bold", "italic", "strike")}
        got = {(w, nm) for w, nm in names(r2, t2) if nm in ("bold", "italic", "strike")}
        if want - got:
            fails.append(f"md: Formatierung verloren {sorted(want - got)}")
    import share
    note = {"id": "x", "type": "text", "title": n.get("title", ""), "text": text, "rich": rich,
            "images": n.get("images") or [], "labels": [], "color": "default"}
    with tempfile.TemporaryDirectory() as d:
        f = os.path.join(d, "x.notes")
        with open(f, "w", encoding="utf-8") as fh:
            fh.write(share.bundle(note, "notes"))
        kind, back, _files = share.read_bundle(f)
    for k in ("title", "text", "rich", "images"):
        if json.loads(json.dumps(back.get(k))) != json.loads(json.dumps(note[k])):
            fails.append(f".notes: Feld {k} geändert")
    return fails


def check_docs_bundle(blocks, page):
    import share
    note = {"id": "x", "type": "docs", "title": "T", "text": "", "blocks": blocks, "page": page, "labels": [], "color": "default"}
    with tempfile.TemporaryDirectory() as d:
        f = os.path.join(d, "x.notes")
        with open(f, "w", encoding="utf-8") as fh:
            fh.write(share.bundle(note, "docs"))
        _k, back, _f = share.read_bundle(f)
    return [] if json.loads(json.dumps(back["blocks"])) == json.loads(json.dumps(blocks)) else [".notes: Blöcke geändert"]


# ---------------------------------------------------------------- Zufallsmodelle
WORDS = ["Haus", "Baum", "ä", "ö", "Straße", "😀", "x²", "α", "Ende."]
SPECIAL = ["a&b", "<t>", "**", "_", "#", "[l]", "1.", "-", "|", "\\", "*", "`", ">"]          # Markdown kennt kein Maskieren
SPECIAL_ON = [False]
COLORS = ["#cc0000", "#00aa00", "#0000cc"]


def rnd_text(rng):
    return " ".join(rng.choice(WORDS + (SPECIAL if SPECIAL_ON[0] else [])) for _ in range(rng.randint(1, 5)))


def rnd_runs(rng, img):
    runs = []
    for _ in range(rng.randint(1, 4)):
        r = {"text": rnd_text(rng) + " "}
        for k in rng.sample(["b", "i", "u", "s"], rng.randint(0, 2)):
            r[k] = True
        if rng.random() < 0.15:
            r["va"] = rng.choice(["sup", "sub"])
        if rng.random() < 0.15:
            r["color"] = rng.choice(COLORS)
        if rng.random() < 0.1:
            r["size"] = rng.choice([9, 14, 18])
        if rng.random() < 0.1:
            r["hl"] = "#ffff00"
        if rng.random() < 0.1:
            r["link"] = "https://example.org/" + str(rng.randint(1, 99))
        runs.append(r)
    if rng.random() < 0.1:
        runs.append({"img": img, "mime": "image/png", "w": rng.choice([40, 80]), "h": rng.choice([30, 60])})
    return df.merge_runs(runs)


def rnd_doc(rng, img):
    blocks = []
    for _ in range(rng.randint(1, 8)):
        c = rng.random()
        if c < 0.7:
            b = df.para(style=rng.choice(df.STYLES), align=rng.choice(["left", "center", "right", "justify"]),
                        list=rng.choice([None, None, "bullet", "number"]), indent=rng.choice([0, 0, 1, 2]),
                        spacing=rng.choice([1.0, 1.15, 1.5]))
            b["runs"] = rnd_runs(rng, img)
            if b["style"] != "normal":
                b["list"] = None
            blocks.append(b)
        elif c < 0.85:
            nc = rng.randint(1, 3)
            tb = {"t": "table", "rows": [[rnd_text(rng) for _ in range(nc)] for _ in range(rng.randint(1, 3))]}
            if rng.random() < 0.5:
                tb["style"] = {"head": rng.random() < 0.7, "first_col": rng.random() < 0.3, "border": rng.choice(df.TABLE_BORDERS),
                               "pad": rng.choice(list(df.TABLE_PADS)), "accent": rng.choice([None, *df.TABLE_ACCENTS])}
            blocks.append(tb)
            blocks.append(df.para(rnd_text(rng)))              # zwei Tabellen hintereinander verschmelzen sonst
        elif c < 0.92:
            blocks.append({"t": "hr"})
        else:
            blocks.append({"t": "pb"})
    return blocks


# ---------------------------------------------------------------- Lauf
def run_model(name, blocks, page, only=None, verbose=False, skip=()):
    fails = {}
    with tempfile.TemporaryDirectory() as tmp:
        for fmt, fn in ROUNDTRIPS.items():
            if fmt in skip:
                continue
            mask = MASK[fmt]
            try:
                b2, p2 = fn(blocks, page, tmp)
            except Exception as e:                                           # noqa: BLE001
                fails[fmt] = [f"Ausnahme {type(e).__name__}: {e}"]
                continue
            if fmt in EXEMPT.get(name.replace(".json", ""), ()):
                d = text_only(blocks, b2)
            else:
                d = diff(norm_blocks(blocks, mask), norm_blocks(b2, mask))
                if page is not None or p2:
                    d += diff(norm_page(page, mask), norm_page(p2, mask), "page")
                if "comments" not in mask.get("page", ()) and "*" not in mask.get("page", ()):
                    d += diff(norm_comments(page, blocks), norm_comments(p2, b2), "kommentare")
            if d:
                fails[fmt] = d
        try:
            w = only_write(blocks, page, tmp)
            if w:
                fails["rtf/epub"] = w
        except Exception as e:                                               # noqa: BLE001
            fails["rtf/epub"] = [f"Ausnahme {type(e).__name__}: {e}"]
    try:
        d = check_docs_bundle(blocks, page)
        if d:
            fails["bundle"] = d
    except Exception as e:                                                   # noqa: BLE001
        fails["bundle"] = [f"Ausnahme {type(e).__name__}: {e}"]
    return fails


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-v", "--verbose", action="store_true")
    ap.add_argument("--n", type=int, default=500)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--only")
    ap.add_argument("--limit", type=int, default=12, help="höchstens so viele Abweichungen je Modell zeigen")
    a = ap.parse_args()
    bad = 0
    total = 0
    for f in sorted(os.listdir(GOLD)):
        if not f.endswith(".json") or (a.only and a.only not in f):
            continue
        with open(os.path.join(GOLD, f), encoding="utf-8") as fh:
            m = json.load(fh)
        total += 1
        if m["kind"] == "notes":
            fails = {"note": check_note(dict(m["note"]))}
            fails = {k: v for k, v in fails.items() if v}
        else:
            fails = run_model(f, m["blocks"], m.get("page"), a.only, a.verbose)
        if fails:
            bad += 1
            print(f"✗ {f}")
            for fmt, d in fails.items():
                for line in d[:a.limit]:
                    print(f"    [{fmt}] {line}")
        elif a.verbose:
            print(f"✓ {f}")
    if not a.only:
        rng = random.Random(a.seed)
        img = base64.b64encode(open(os.path.join(GOLD, "_rnd.png"), "rb").read()).decode() if os.path.exists(
            os.path.join(GOLD, "_rnd.png")) else __import__("make_gold").IMG
        nbad = 0
        for i in range(a.n):
            SPECIAL_ON[0] = bool(i % 2)
            blocks = rnd_doc(rng, img)
            fails = run_model(f"zufall{i}", blocks, None, skip=("md",) if SPECIAL_ON[0] else ())
            total += 1
            if fails:
                nbad += 1
                bad += 1
                if nbad <= 5:
                    print(f"✗ zufall{i}  (seed {a.seed})")
                    for fmt, d in fails.items():
                        for line in d[:3]:
                            print(f"    [{fmt}] {line}")
        if nbad > 5:
            print(f"  … {nbad - 5} weitere Zufallsmodelle mit Abweichungen")
    print(f"\n{total - bad}/{total} Modelle ohne Abweichung")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.path.insert(0, HERE)
    sys.exit(main())
