# Zusätze für den LaTeX-Modus: SyncTeX (PDF ↔ Quelltext), Literatur (.bib), Tabellen-Editor,
# Befehlsübersicht (alle Befehle mit Erklärung, als PDF speicherbar), Formel-Vorschau, Rechtschreib-Filter.
# Reiner Teil (GTK-frei) – Oberfläche in texextra.py.
import gzip, hashlib, os, re, shutil


from core import latexdata as ld

F = ld.F
SP_PER_BP = 65781.76


# =====================================================================
# SyncTeX
# =====================================================================
class SyncTex:
    """Liest main.synctex.gz. Koordinaten in PDF-Punkten, y von oben (Grundlinie)."""

    REC = re.compile(r"^([\[\(hvxkg$])(\d+),(\d+)(?:,\d+)?:(-?\d+),(-?\d+)(?::(-?\d+)(?:,(-?\d+))?)?")

    def __init__(self, path):
        self.inputs = {}          # tag → dateiname (basename)
        self.records = []         # (seite 0-basiert, tag, zeile, x, y, breite, höhe)
        unit, mag = 1.0, 1000.0
        with gzip.open(path, "rt", encoding="utf-8", errors="replace") as f:
            page = -1
            for line in f:
                if line.startswith("Input:"):
                    _, tag, name = line.rstrip("\n").split(":", 2)
                    self.inputs[int(tag)] = os.path.basename(name) if name else ""
                elif line.startswith("Unit:"):
                    unit = float(line[5:])
                elif line.startswith("Magnification:"):
                    mag = float(line[14:])
                elif line.startswith("{"):
                    page = int(line[1:]) - 1
                else:
                    m = self.REC.match(line)
                    if m and page >= 0:
                        k = unit * mag / 1000 / SP_PER_BP
                        w = int(m.group(6)) * k if m.group(6) else 0
                        h = int(m.group(7)) * k if m.group(7) else 0
                        self.records.append((page, int(m.group(2)), int(m.group(3)), int(m.group(4)) * k,
                                             int(m.group(5)) * k, w, h, m.group(1) not in "[("))

    def to_source(self, page, x, y):
        """PDF-Klick → (datei, zeile)."""
        best, score = None, None
        leaves = any(r[0] == page and r[7] for r in self.records)
        for p, tag, line, rx, ry, rw, rh, leaf in self.records:
            if p != page or line <= 0 or (leaves and not leaf):   # einzelne Textstellen vor umschließenden Kästen
                continue
            dy = abs(ry - y) if ry >= y else abs(ry - y) * 0.6 + (0 if y - ry < max(rh, 12) else 0)
            dx = 0 if rx <= x <= rx + max(rw, 4) else min(abs(x - rx), abs(x - rx - rw))
            s = dy * 3 + dx
            if score is None or s < score:
                best, score = (self.inputs.get(tag, ""), line), s
        return best

    def to_pdf(self, filename, line):
        """Quelltext-Zeile → (seite, x, y, breite) oder None."""
        tags = {t for t, n in self.inputs.items() if n == filename}
        hits = [r for r in self.records if r[1] in tags and r[2] == line]
        if not hits:
            near = [r for r in self.records if r[1] in tags and 0 < r[2] <= line]
            if not near:
                return None
            best = max(r[2] for r in near)
            hits = [r for r in near if r[2] == best]
        p = min(r[0] for r in hits)
        on = [r for r in hits if r[0] == p]
        y = min(r[4] for r in on)
        x = min(r[3] for r in on)
        w = max((r[3] + r[5] for r in on), default=x + 100) - x
        return p, x, y, max(w, 40)


# =====================================================================
# Literatur (.bib)
# =====================================================================
BIB_TYPES = [("book", "Buch"), ("article", "Zeitschriftenartikel"), ("online", "Webseite"),
             ("incollection", "Beitrag in Sammelband"), ("thesis", "Abschlussarbeit"), ("misc", "Sonstiges")]
BIB_FIELDS = {
    "book": [("author", "Autor(en)", "Nachname, Vorname and Nachname, Vorname"), ("title", "Titel", ""),
             ("year", "Jahr", "2024"), ("publisher", "Verlag", ""), ("address", "Ort", "")],
    "article": [("author", "Autor(en)", "Nachname, Vorname"), ("title", "Titel", ""), ("journal", "Zeitschrift", ""),
                ("year", "Jahr", ""), ("volume", "Band", ""), ("pages", "Seiten", "12--34")],
    "online": [("author", "Autor/Organisation", ""), ("title", "Titel", ""), ("url", "Adresse (URL)", "https://"),
               ("year", "Jahr", ""), ("urldate", "Abgerufen am", "2026-10-18")],
    "incollection": [("author", "Autor(en)", ""), ("title", "Titel des Beitrags", ""), ("booktitle", "Titel des Buchs", ""),
                     ("editor", "Herausgeber", ""), ("year", "Jahr", ""), ("publisher", "Verlag", ""), ("pages", "Seiten", "")],
    "thesis": [("author", "Autor(in)", ""), ("title", "Titel", ""), ("school", "Hochschule", ""), ("year", "Jahr", ""),
               ("type", "Art", "Bachelorarbeit")],
    "misc": [("author", "Autor(en)", ""), ("title", "Titel", ""), ("year", "Jahr", ""), ("note", "Hinweis", "")],
}


def parse_bib(text):
    """→ [{"type", "key", Felder…}] (einfacher Leser, reicht für eigene Literaturlisten)."""
    out = []
    for m in re.finditer(r"@(\w+)\s*\{\s*([^,\s]+)\s*,", text):
        start, depth, i = m.end(), 1, m.end()
        while i < len(text) and depth:
            depth += {"{": 1, "}": -1}.get(text[i], 0)
            i += 1
        body = text[start:i - 1]
        e = {"type": m.group(1).lower(), "key": m.group(2)}
        for f in re.finditer(r"(\w+)\s*=\s*(\{((?:[^{}]|\{[^{}]*\})*)\}|\"([^\"]*)\"|(\d+))", body):
            e[f.group(1).lower()] = (f.group(3) or f.group(4) or f.group(5) or "").strip()
        out.append(e)
    return out


def bib_key(entry, existing):
    a = (entry.get("author") or entry.get("title") or "quelle").split(" and ")[0]
    last = a.split(",")[0].strip().split()[-1] if "," in a or a.strip() else "quelle"
    last = re.sub(r"[^a-z0-9]", "", last.lower().translate(str.maketrans("äöüß", "aous"))) or "quelle"
    key = f"{last}{entry.get('year', '')}"
    base, n = key, 1
    while key in existing:
        key = base + "abcdefghijklmnopqrstuvwxyz"[n % 26]
        n += 1
    return key


def bib_entry(entry):
    fields = [(k, v) for k, v in entry.items() if k not in ("type", "key") and v]
    typ = entry["type"]
    if typ == "online":                    # funktioniert auch mit klassischem BibTeX
        typ = "misc"
        fields = [(k if k != "urldate" else "note", v if k != "urldate" else f"Abgerufen am {v}") for k, v in fields]
        if not any(k == "howpublished" for k, _ in fields) and entry.get("url"):
            fields.append(("howpublished", f"\\url{{{entry['url']}}}"))
    if typ == "thesis":
        typ = "phdthesis" if "diss" in entry.get("type", "").lower() else "mastersthesis"
    w = max((len(k) for k, _ in fields), default=4)
    body = ",\n".join(f"  {k.ljust(w)} = {{{v}}}" for k, v in fields)
    return f"@{typ}{{{entry['key']},\n{body}\n}}\n"


def describe_bib(e):
    who = e.get("author", "").replace(" and ", "; ")
    return f"{who} ({e.get('year', 'o. J.')}): {e.get('title', '')}".strip()


# =====================================================================
# Rechtschreibung: was in LaTeX nicht geprüft wird
# =====================================================================
ARG_CMDS = ("label", "ref", "eqref", "autoref", "pageref", "cite", "citep", "citet", "nocite", "usepackage",
            "documentclass", "includegraphics", "input", "include", "begin", "end", "bibliography", "bibliographystyle",
            "addbibresource", "url", "href", "hypersetup", "setlength", "newcommand", "renewcommand", "pagestyle",
            "thispagestyle", "pagenumbering", "usetheme", "color", "textcolor", "setkomavar", "lstinline", "verb")
_SKIP = re.compile(r"\$\$.*?\$\$|\$(?:\\.|[^$\\])*\$|\\\[.*?\\\]|\\\(.*?\\\)"
                   r"|\\begin\{(equation|align|gather|multline|tikzpicture|lstlisting|verbatim)\*?\}.*?\\end\{\1\*?\}"
                   r"|\\(?:" + "|".join(ARG_CMDS) + r")\*?(?:\[[^\]]*\])*(?:\{[^{}]*\})?(?:\{[^{}]*\})?"
                   r"|\\[A-Za-z@]+\*?|\[[^\]\n]*=[^\]\n]*\]", re.S)


def spell_skip(text):
    return [(m.start(), m.end()) for m in _SKIP.finditer(text)]


# =====================================================================
# Formeln
# =====================================================================
MATH_ENVS = ("equation", "equation*", "align", "align*", "gather", "gather*", "multline", "multline*")


def math_at(text, off):
    """Formel um die Cursorposition: (anfang, ende, quelltext) oder None."""
    for m in re.finditer(r"\$\$(.+?)\$\$|(?<!\\)\$((?:\\.|[^$\\])+?)\$|\\\[(.+?)\\\]|\\\((.+?)\\\)"
                         r"|\\begin\{(" + "|".join(re.escape(e) for e in MATH_ENVS) + r")\}(.+?)\\end\{\5\}", text, re.S):
        if m.start() <= off <= m.end():
            return m.start(), m.end(), m.group(0)
        if m.start() > off:
            break
    return None


def formula_source(preamble_src, formula):
    pkgs = "\n".join(l for l in preamble_src.split("\n")
                     if re.match(r"\s*\\(usepackage|newcommand|renewcommand|DeclareMathOperator)", l)
                     and not re.search(r"\{(hyperref|geometry|fancyhdr|biblatex|csquotes|babel)\}", l))
    return ("\\documentclass[border=3pt,varwidth=20cm]{standalone}\n\\usepackage{amsmath,amssymb}\n" + pkgs +
            "\n\\begin{document}\n" + formula + "\n\\end{document}\n")


def formula_hash(src):
    return hashlib.sha1(src.encode()).hexdigest()[:16]


# =====================================================================
# Tabellen-Editor
# =====================================================================
def parse_tabular(src):
    """\\begin{tabular}{…} … \\end{tabular} → (spalten-ausrichtung, zeilen)."""
    m = re.search(r"\\begin\{tabular\}\{([^}]*)\}(.*?)\\end\{tabular\}", src, re.S)
    if not m:
        return None
    aligns = [c for c in m.group(1) if c in "lcr"] or ["l"]
    body = re.sub(r"\\(hline|toprule|midrule|bottomrule|cline\{[^}]*\})", "", m.group(2))
    rows = []
    for r in re.split(r"\\\\", body):
        if not r.strip():
            continue
        rows.append([c.strip() for c in re.split(r"(?<!\\)&", r)])
    n = max([len(aligns)] + [len(r) for r in rows])
    aligns += ["l"] * (n - len(aligns))
    rows = [r + [""] * (n - len(r)) for r in rows] or [[""] * n]
    return aligns, rows


def build_table(aligns, rows, lines="all", header=True, caption="", label="", float_=True):
    n = len(aligns)
    if lines == "all":
        spec = "|" + "|".join(aligns) + "|"
    else:
        spec = "".join(aligns)
    out = []
    if float_:
        out += ["\\begin{table}[htbp]", "  \\centering"]
        if caption:
            out.append(f"  \\caption{{{caption}}}")
        if label:
            out.append(f"  \\label{{tab:{label}}}")
    ind = "  " if float_ else ""
    out.append(f"{ind}\\begin{{tabular}}{{{spec}}}")
    top = {"all": "\\hline", "booktabs": "\\toprule", "none": None}[lines]
    mid = {"all": "\\hline", "booktabs": "\\midrule", "none": None}[lines]
    bot = {"all": "\\hline", "booktabs": "\\bottomrule", "none": None}[lines]
    if top:
        out.append(f"{ind}  {top}")
    for k, r in enumerate(rows):
        cells = [(f"\\textbf{{{c}}}" if header and k == 0 and c else c) for c in (r + [""] * n)[:n]]
        out.append(f"{ind}  " + " & ".join(cells) + " \\\\")
        if k == 0 and header and mid:
            out.append(f"{ind}  {mid}")
        elif lines == "all" and k < len(rows) - 1:
            out.append(f"{ind}  \\hline")
    if bot:
        out.append(f"{ind}  {bot}")
    out.append(f"{ind}\\end{{tabular}}")
    if float_:
        out.append("\\end{table}")
    return "\n".join(out) + "\n"


def tex_escape(s):
    rep = {"\\": "\\textbackslash{}", "{": "\\{", "}": "\\}", "$": "\\$", "&": "\\&", "%": "\\%", "#": "\\#",
           "_": "\\_", "^": "\\^{}", "~": "\\~{}"}
    return "".join(rep.get(c, c) for c in s)


def overview_items():
    """[(rubrik, befehl, schnipsel, erklärung, beispiel, paket)] – alles, was notist kennt."""
    out = []
    for name, snip, desc, cat, pkg in ld.COMMANDS:
        out.append((cat, name, snip, desc, ld.EXAMPLES.get(name, ""), pkg))
    for name, body, desc, pkg in ld.ENVIRONMENTS:
        out.append(("Umgebungen", f"\\begin{{{name}}} … \\end{{{name}}}", ld.env_snippet(name), desc, "", pkg))
    return out


def cheatsheet_source():
    cats = {}
    for cat, name, snip, desc, ex, pkg in overview_items():
        cats.setdefault(cat, []).append((name, desc, pkg))
    parts = ["\\documentclass[9pt,a4paper]{extarticle}", "\\usepackage[ngerman]{babel}",
             "\\usepackage[a4paper,margin=1.4cm]{geometry}", "\\usepackage{multicol}", "\\usepackage{xcolor}",
             "\\setlength{\\parindent}{0pt}", "\\pagestyle{empty}",
             "\\newcommand{\\cmd}[1]{\\textcolor{blue!60!black}{\\texttt{#1}}}", "\\begin{document}",
             "{\\Large\\bfseries LaTeX-Befehle auf einen Blick}\\\\[2pt]{\\small aus notist · Befehl – was er tut – "
             "(nötiges Paket)}\\medskip", "\\begin{multicols}{2}"]
    for cat in ld.CATEGORIES + ["Umgebungen"]:
        items = cats.get(cat)
        if not items:
            continue
        parts.append(f"\\subsection*{{{tex_escape(cat)}}}")
        for name, desc, pkg in items:
            p = f" \\textit{{({tex_escape(pkg)})}}" if pkg else ""
            parts.append(f"\\cmd{{{tex_escape(name)}}} – {tex_escape(desc)}{p}\\par")
    parts += ["\\end{multicols}", "\\end{document}"]
    return "\n".join(parts) + "\n"
