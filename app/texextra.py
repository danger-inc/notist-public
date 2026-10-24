# Zusätze für den LaTeX-Modus: SyncTeX (PDF ↔ Quelltext), Literatur (.bib), Tabellen-Editor,
# Befehlsübersicht (alle Befehle mit Erklärung, als PDF speicherbar), Formel-Vorschau, Rechtschreib-Filter.
import gzip, hashlib, os, re, shutil

from gi.repository import Gdk, Gio, GLib, Gtk, Pango

import latexdata as ld

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
        with gzip.open(path, "rt", errors="replace") as f:
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


class TableEditor(Gtk.Window):
    """Tabelle wie in einer Tabellenkalkulation ausfüllen – notist schreibt den LaTeX-Code."""

    def __init__(self, parent, on_apply, aligns=None, rows=None, existing=False):
        super().__init__(title="Tabellen-Editor", transient_for=parent, default_width=760, default_height=520)
        self.add_css_class("settings")
        self.add_css_class("pb-window")
        self.on_apply = on_apply
        self.aligns = aligns or ["l", "l", "l"]
        self.rows = rows or [["", "", ""] for _ in range(3)]
        k = Gtk.EventControllerKey()
        k.connect("key-pressed", lambda c, kv, *_: kv == Gdk.KEY_Escape and (self.close() or True))
        self.add_controller(k)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.add_css_class("settings-page")
        import dialogs
        dialogs.chrome(self, self.get_title(), box)
        h = Gtk.Label(label="Tabelle bearbeiten" if existing else "Neue Tabelle", xalign=0)
        h.add_css_class("set-h")
        box.append(h)
        sub = Gtk.Label(xalign=0, wrap=True, label="Einfach in die Zellen tippen. Tab springt weiter. Die erste Zeile ist "
                                                   "die Kopfzeile. notist erzeugt daraus den LaTeX-Code (& trennt Zellen, \\\\ beendet Zeilen).")
        sub.add_css_class("set-sub")
        box.append(sub)
        bar = Gtk.Box(spacing=6)
        for label, cb in (("+ Zeile", self.add_row), ("− Zeile", self.del_row), ("+ Spalte", self.add_col), ("− Spalte", self.del_col)):
            b = Gtk.Button(label=label)
            b.add_css_class("pb"); b.add_css_class("small")
            b.connect("clicked", lambda *_, c=cb: c())
            bar.append(b)
        box.append(bar)
        sc = Gtk.ScrolledWindow(vexpand=True)
        self.grid = Gtk.Grid(column_spacing=4, row_spacing=4)
        sc.set_child(self.grid)
        box.append(sc)
        opts = Gtk.Box(spacing=10)
        self.lines = Gtk.DropDown.new_from_strings(["Alle Linien", "Schön (booktabs)", "Keine Linien"])
        self.header = Gtk.CheckButton(label="Kopfzeile fett", active=True)
        self.float_ = Gtk.CheckButton(label="Mit Beschriftung (table)", active=True)
        opts.append(self.lines)
        opts.append(self.header)
        opts.append(self.float_)
        box.append(opts)
        cap = Gtk.Box(spacing=6)
        self.caption = Gtk.Entry(placeholder_text="Beschriftung, z. B. Ergebnisse der Umfrage", hexpand=True)
        self.label = Gtk.Entry(placeholder_text="Label (für \\ref), z. B. umfrage")
        for e in (self.caption, self.label):
            e.add_css_class("pb")
            cap.append(e)
        box.append(cap)
        ok = Gtk.Button(label="󰄬  Übernehmen" if existing else "󰐕  Einfügen", halign=Gtk.Align.END)
        ok.add_css_class("pb")
        ok.connect("clicked", lambda *_: self.apply())
        box.append(ok)
        self.build_grid()

    def read(self):
        self.rows = [[e.get_text() for e in row] for row in self.entries]
        self.aligns = ["lcr"[d.get_selected()] for d in self.align_drops]

    def build_grid(self):
        while (c := self.grid.get_first_child()):
            self.grid.remove(c)
        n = len(self.aligns)
        self.align_drops, self.entries = [], []
        for c in range(n):
            d = Gtk.DropDown.new_from_strings(["links", "mittig", "rechts"])
            d.set_selected("lcr".index(self.aligns[c]))
            d.set_tooltip_text(f"Ausrichtung Spalte {c + 1}")
            self.grid.attach(d, c, 0, 1, 1)
            self.align_drops.append(d)
        for r, row in enumerate(self.rows):
            line = []
            for c in range(n):
                e = Gtk.Entry(text=row[c] if c < len(row) else "", width_chars=12, hexpand=True)
                e.add_css_class("pb")
                if r == 0:
                    e.set_placeholder_text(f"Kopf {c + 1}")
                self.grid.attach(e, c, r + 1, 1, 1)
                line.append(e)
            self.entries.append(line)

    def add_row(self):
        self.read()
        self.rows.append([""] * len(self.aligns))
        self.build_grid()

    def del_row(self):
        self.read()
        if len(self.rows) > 1:
            self.rows.pop()
        self.build_grid()

    def add_col(self):
        self.read()
        self.aligns.append("l")
        self.rows = [r + [""] for r in self.rows]
        self.build_grid()

    def del_col(self):
        self.read()
        if len(self.aligns) > 1:
            self.aligns.pop()
            self.rows = [r[:-1] for r in self.rows]
        self.build_grid()

    def apply(self):
        self.read()
        lines = ("all", "booktabs", "none")[self.lines.get_selected()]
        label = re.sub(r"[^A-Za-z0-9:_-]", "", self.label.get_text())
        code = build_table(self.aligns, self.rows, lines, self.header.get_active(), self.caption.get_text().strip(),
                           label, self.float_.get_active())
        self.on_apply(code, "booktabs" if lines == "booktabs" else None)
        self.close()


# =====================================================================
# Befehlsübersicht
# =====================================================================
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


class CommandOverview(Gtk.Window):
    """Alle Befehle mit Erklärung, Beispiel und Paket – durchsuchbar, Klick fügt ein."""

    def __init__(self, parent, on_insert, on_pdf=None):
        super().__init__(title="LaTeX-Befehle", transient_for=parent, default_width=860, default_height=680)
        self.add_css_class("settings")
        self.add_css_class("pb-window")
        self.on_insert = on_insert
        k = Gtk.EventControllerKey()
        k.connect("key-pressed", lambda c, kv, *_: kv in (Gdk.KEY_Escape, Gdk.KEY_F1) and (self.close() or True))
        self.add_controller(k)
        outer = Gtk.Box()
        import dialogs
        dialogs.chrome(self, self.get_title(), outer)
        side = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
        side.add_css_class("settings-side")
        side.set_size_request(190, -1)
        self.items = overview_items()
        cats = ["Alle"] + [c for c in ld.CATEGORIES + ["Umgebungen"] if any(i[0] == c for i in self.items)]
        for c in cats:
            r = Gtk.ListBoxRow()
            r.cat = c
            n = len(self.items) if c == "Alle" else sum(1 for i in self.items if i[0] == c)
            r.set_child(Gtk.Label(label=f"{c}  ({n})", xalign=0))
            side.append(r)
        side.connect("row-selected", lambda lb, r: r and self.set_cat(r.cat))
        outer.append(side)
        right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, hexpand=True)
        right.add_css_class("settings-page")
        top = Gtk.Box(spacing=8)
        self.search = Gtk.SearchEntry(placeholder_text="Suchen: Befehl oder was er tun soll (z. B. Bruch, fett, Pfeil)",
                                      hexpand=True)
        self.search.add_css_class("pb")
        self.search.connect("search-changed", lambda *_: self.fill())
        top.append(self.search)
        if on_pdf:
            b = Gtk.Button(label="󰈦  Als PDF speichern", tooltip_text="Spickzettel mit allen Befehlen zum Ausdrucken")
            b.add_css_class("pb"); b.add_css_class("small")
            b.connect("clicked", lambda *_: on_pdf())
            top.append(b)
        right.append(top)
        hint = Gtk.Label(xalign=0, label="Klick auf eine Zeile fügt den Befehl an der Cursorstelle ein.")
        hint.add_css_class("set-sub")
        right.append(hint)
        sc = Gtk.ScrolledWindow(vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER)
        self.list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        self.list.add_css_class("cmd-list")
        self.list.connect("row-activated", lambda lb, r: (self.on_insert(r.snip, r.pkg), self.present()))
        sc.set_child(self.list)
        right.append(sc)
        outer.append(right)
        self.cat = "Alle"
        side.select_row(side.get_row_at_index(0))
        GLib.idle_add(lambda: self.search.grab_focus() and False)

    def set_cat(self, cat):
        self.cat = cat
        self.fill()

    def fill(self):
        lst = self.list
        while (c := lst.get_first_child()):
            lst.remove(c)
        q = self.search.get_text().strip().lower()
        shown = 0
        for cat, name, snip, desc, ex, pkg in self.items:
            if self.cat != "Alle" and cat != self.cat:
                continue
            if q and q not in name.lower() and q not in desc.lower() and q not in cat.lower():
                continue
            row = Gtk.ListBoxRow()
            row.snip, row.pkg = snip, pkg
            g = Gtk.Grid(column_spacing=14, row_spacing=1)
            n = Gtk.Label(label=name, xalign=0, selectable=False)
            n.add_css_class("cmd-name")
            n.set_size_request(230, -1)
            n.set_ellipsize(Pango.EllipsizeMode.END)
            g.attach(n, 0, 0, 1, 1)
            d = Gtk.Label(label=desc, xalign=0, wrap=True, hexpand=True)
            d.add_css_class("cmd-desc")
            g.attach(d, 1, 0, 1, 1)
            if pkg:
                p = Gtk.Label(label=pkg, xalign=1)
                p.add_css_class("cmp-pkg")
                g.attach(p, 2, 0, 1, 1)
            if ex:
                e = Gtk.Label(label="z. B.  " + ex, xalign=0, wrap=True)
                e.add_css_class("cmd-ex")
                g.attach(e, 1, 1, 2, 1)
            row.set_child(g)
            lst.append(row)
            shown += 1
            if shown >= 400:
                break
        if not shown:
            l = Gtk.Label(label="Nichts gefunden – probier ein anderes Wort.", xalign=0)
            l.add_css_class("set-sub")
            lst.append(l)


CSS = """
.cmd-list { background: none; }
.cmd-list row { border-radius: 9px; padding: 6px 10px; }
.cmd-list row:hover { background-color: alpha(@color9, 0.12); }
.cmd-name { font-family: "JetBrainsMono Nerd Font", monospace; font-weight: 800; color: @color9; font-size: 12px; }
.cmd-desc { font-size: 12px; }
.cmd-ex { font-family: "JetBrainsMono Nerd Font", monospace; font-size: 11px; color: alpha(@foreground, 0.55); }
popover.formula > contents { background-color: #ffffff; border: 2px solid @color9; border-radius: 11px; padding: 6px; }
.formula-hint { font-size: 10px; color: #555555; }
.file-tabs button { background: none; background-image: none; box-shadow: none; border: none; border-radius: 8px;
    padding: 0 10px; min-height: 24px; font-size: 12px; font-weight: 700; color: alpha(@foreground, 0.6); }
.file-tabs button:checked { color: @foreground; box-shadow: inset 0 -3px @color9; }
.file-tabs button:hover { background-color: alpha(@color9, 0.1); }
.file-tabs { margin-bottom: 4px; }
.bib-row { background-color: alpha(@foreground, 0.05); border-radius: 9px; padding: 6px 10px; }
.bib-key { font-family: monospace; font-weight: 800; color: @color9; font-size: 11px; }
.pdf-flash { background-color: alpha(#fdd663, 0.45); }
"""
