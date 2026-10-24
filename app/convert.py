# Umwandeln zwischen Words (Blöcke aus docfmt) und LaTeX-Quelltext.
# Words → LaTeX ist vollständig (inkl. Seiteneinstellungen, Kopf-/Fußzeile, Bilder, Fußnoten, Tabellen).
# LaTeX → Words versteht die üblichen Befehle; Unbekanntes bleibt als lesbarer Text erhalten.
import base64, os, re

import docfmt as df

SPECIAL = {"\\": "\\textbackslash{}", "{": "\\{", "}": "\\}", "$": "\\$", "&": "\\&", "%": "\\%", "#": "\\#",
           "_": "\\_", "^": "\\textasciicircum{}", "~": "\\textasciitilde{}", "„": "\\glqq{}", "“": "\\grqq{}",
           "\u00a0": "~"}


def esc(t):
    return "".join(SPECIAL.get(c, c) for c in t)


# =====================================================================
# Words → LaTeX
# =====================================================================
def run_tex(r, pkgs):
    if r.get("fn") is not None:
        return f"\\footnote{{{esc(r['fn'])}}}"
    t = esc(r.get("text", "")).replace("\t", "\\quad ")
    if not t:
        return ""
    if r.get("b"):
        t = f"\\textbf{{{t}}}"
    if r.get("i"):
        t = f"\\textit{{{t}}}"
    if r.get("u") and not r.get("link"):
        t = f"\\underline{{{t}}}"
    if r.get("s"):
        pkgs.add("ulem")
        t = f"\\sout{{{t}}}"
    if r.get("va") == "sup":
        t = f"\\textsuperscript{{{t}}}"
    elif r.get("va") == "sub":
        t = f"\\textsubscript{{{t}}}"
    if r.get("color"):
        pkgs.add("xcolor")
        t = f"\\textcolor[HTML]{{{r['color'].lstrip('#').upper()}}}{{{t}}}"
    if r.get("hl"):
        pkgs.add("xcolor")
        pkgs.add("soul")
        t = f"{{\\sethlcolor[HTML]{{{r['hl'].lstrip('#').upper()}}}\\hl{{{t}}}}}"
    if r.get("link"):
        pkgs.add("hyperref")
        t = f"\\href{{{r['link']}}}{{{t}}}"
    return t


def blocks_to_latex(blocks, title="", page=None, image_dir=None):
    """→ LaTeX-Quelltext. Bilder werden nach image_dir geschrieben (falls angegeben)."""
    pkgs = {"amsmath", "graphicx"}
    body, nums = [], 0
    cfg = df.norm_page(page)
    img_n = 0
    stack = []                                # offene Listen: [(art, ebene)]

    def close_lists(to_level=-1):
        while stack and stack[-1][1] > to_level:
            kind, _ = stack.pop()
            body.append("  " * len(stack) + ("\\end{itemize}" if kind == "bullet" else "\\end{enumerate}"))

    title_done = False
    for b in blocks:
        if b["t"] != "p" or not b.get("list"):
            close_lists()
        if b["t"] == "toc":
            body.append("\\tableofcontents\n")
            continue
        if b["t"] == "pb":
            body.append("\\newpage\n")
            continue
        if b["t"] == "hr":
            body.append("\\noindent\\rule{\\textwidth}{0.4pt}\n")
            continue
        if b["t"] == "table":
            rows = b["rows"] or [[""]]
            n = max(len(r) for r in rows)
            spec = "|" + "|".join(["p{%.2f\\textwidth}" % (0.9 / n)] * n) + "|"
            lines = ["\\begin{table}[htbp]", "  \\centering", f"  \\begin{{tabular}}{{{spec}}}", "    \\hline"]
            for k, r in enumerate(rows):
                cells = [esc(c).replace("\n", " \\newline ") for c in (r + [""] * n)[:n]]
                if k == 0:
                    cells = [f"\\textbf{{{c}}}" if c else c for c in cells]
                lines.append("    " + " & ".join(cells) + " \\\\ \\hline")
            lines += ["  \\end{tabular}", "\\end{table}\n"]
            body.append("\n".join(lines))
            continue
        # Absatz
        parts = []
        for r in b["runs"]:
            if r.get("img"):
                img_n += 1
                data = base64.b64decode(r["img"])
                ext = {"image/jpeg": "jpg", "image/gif": "gif", "image/webp": "png"}.get(r.get("mime"), "png")
                name = f"bild{img_n}.{ext}"
                if image_dir:
                    os.makedirs(image_dir, exist_ok=True)
                    with open(os.path.join(image_dir, name), "wb") as f:
                        f.write(data)
                frac = min(1.0, (r.get("w") or 400) / df.CONTENT_W_PX)
                parts.append(f"\\includegraphics[width={frac:.2f}\\textwidth]{{{name}}}")
            else:
                parts.append(run_tex(r, pkgs))
        text = "".join(parts).strip()
        style = b.get("style", "normal")
        if style == "title" and not title_done:
            title = "".join(r.get("text", "") for r in b["runs"]).strip() or title
            body.append("\\maketitle\n")
            title_done = True
            continue
        if style in ("h1", "h2", "h3", "title"):
            cmd = {"h1": "section", "h2": "subsection", "h3": "subsubsection", "title": "section*"}[style]
            body.append(f"\\{cmd}{{{text}}}\n")
            continue
        if b.get("list"):
            lvl = b.get("indent", 0)
            while not stack or stack[-1][1] < lvl:
                body.append("  " * len(stack) + ("\\begin{itemize}" if b["list"] == "bullet" else "\\begin{enumerate}"))
                stack.append((b["list"], stack[-1][1] + 1 if stack else 0))
            close_lists(lvl)
            if stack and stack[-1][0] != b["list"]:
                close_lists(lvl - 1)
                body.append("  " * len(stack) + ("\\begin{itemize}" if b["list"] == "bullet" else "\\begin{enumerate}"))
                stack.append((b["list"], lvl))
            body.append("  " * len(stack) + f"\\item {text}")
            continue
        if style == "code":
            body.append("\\begin{verbatim}\n" + "".join(r.get("text", "") for r in b["runs"]) + "\n\\end{verbatim}\n")
            continue
        if not text:
            body.append("")
            continue
        align = b.get("align", "left")
        if style == "quote":
            text = f"\\begin{{quote}}\n\\textit{{{text}}}\n\\end{{quote}}"
        elif align == "center":
            text = f"\\begin{{center}}\n{text}\n\\end{{center}}"
        elif align == "right":
            text = f"\\begin{{flushright}}\n{text}\n\\end{{flushright}}"
        if b.get("indent") and style == "normal" and align == "left":
            text = f"\\begin{{quote}}\n{text}\n\\end{{quote}}"
        body.append(text + "\n")
    close_lists()
    w, h, (t, r, bt, l) = df.page_mm(cfg)
    geo = f"a4paper" if cfg["size"] == "A4" else ("a5paper" if cfg["size"] == "A5" else "letterpaper")
    if cfg["orient"] == "landscape":
        geo += ",landscape"
    pre = ["\\documentclass[11pt]{article}", f"\\usepackage[{df.tr('ngerman')}]{{babel}}",
           f"\\usepackage[{geo},top={t / 10:g}cm,bottom={bt / 10:g}cm,left={l / 10:g}cm,right={r / 10:g}cm]{{geometry}}"]
    for p in sorted(pkgs):
        pre.append(f"\\usepackage{{{p}}}")
    if any(b.get("spacing", 1.15) >= 1.4 for b in blocks if b["t"] == "p"):
        pre += ["\\usepackage{setspace}", "\\onehalfspacing"]
    if cfg["header"] or cfg["footer"] or cfg["numbers"] != "none":
        pre += ["\\usepackage{fancyhdr}", "\\usepackage{lastpage}", "\\pagestyle{fancy}", "\\fancyhf{}",
                "\\renewcommand{\\headrulewidth}{0pt}"]

        def hf(s):
            import datetime
            s = s.replace("{titel}", title or "").replace("{datum}", datetime.date.today().strftime("%d.%m.%Y"))
            out = ""
            for part in re.split(r"(\{seiten?\})", s):
                out += {"{seite}": "\\thepage{}", "{seiten}": "\\pageref{LastPage}"}.get(part) or esc(part)
            return out
        if cfg["header"]:
            pre.append(f"\\fancyhead[L]{{{hf(cfg['header'])}}}")
        if cfg["footer"]:
            pre.append(f"\\fancyfoot[L]{{{hf(cfg['footer'])}}}")
        if cfg["numbers"] != "none":
            S, V = df.tr("Seite"), df.tr("von")
            num = {"n": "\\thepage", "page": f"{S} \\thepage", "page-of": f"{S} \\thepage{{}} {V} \\pageref{{LastPage}}",
                   "dash": "-- \\thepage{} --"}[cfg["num_fmt"]]
            where = {"footer-center": "\\fancyfoot[C]", "footer-right": "\\fancyfoot[R]", "footer-left": "\\fancyfoot[L]",
                     "header-right": "\\fancyhead[R]"}[cfg["numbers"]]
            pre.append(f"{where}{{{num}}}")
    if title:
        pre += [f"\\title{{{esc(title)}}}", "\\date{}"]
        pre.append("\\author{}")
    first = "\\thispagestyle{empty}\n" if cfg["numbers"] != "none" and int(cfg.get("num_from", 1)) > 1 else ""
    doc = "\n".join(pre) + "\n\n\\begin{document}\n" + first + "\n" + "\n".join(body).strip() + "\n\n\\end{document}\n"
    return re.sub(r"\n{3,}", "\n\n", doc)


# =====================================================================
# LaTeX → Words
# =====================================================================
UNESC = [("\\textbackslash{}", "\\"), ("\\{", "{"), ("\\}", "}"), ("\\$", "$"), ("\\&", "&"), ("\\%", "%"),
         ("\\#", "#"), ("\\_", "_"), ("\\glqq{}", "„"), ("\\grqq{}", "“"), ("\\glqq", "„"), ("\\grqq", "“"),
         ("---", "—"), ("--", "–"), ("``", "„"), ("''", "“"), ("\\ldots{}", "…"), ("\\ldots", "…"), ("\\dots", "…"),
         ("\\LaTeX{}", "LaTeX"), ("\\LaTeX", "LaTeX"), ("\\TeX", "TeX"), ("\\today", ""), ("\\,", " "), ("\\ ", " "),
         ("\\quad", " "), ("\\qquad", "  "), ("~", "\u00a0"), ("\\\\", "\n"), ("\\newline", "\n")]
INLINE = {"textbf": {"b": True}, "textit": {"i": True}, "emph": {"i": True}, "underline": {"u": True},
          "sout": {"s": True}, "textsuperscript": {"va": "sup"}, "textsubscript": {"va": "sub"},
          "texttt": {"font": df.MONO_FONT}, "textsc": {}, "textsf": {}, "textrm": {}, "enquote": {}, "mbox": {}}


def _arg(s, i):
    """Ab s[i] == '{' das Argument bis zur passenden '}' → (inhalt, index danach)."""
    depth, j = 0, i
    while j < len(s):
        c = s[j]
        if c == "\\":
            j += 2
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return s[i + 1:j], j + 1
        j += 1
    return s[i + 1:], len(s)


def _skip_opt(s, i):
    while i < len(s) and s[i] == "[":
        j = s.find("]", i)
        if j < 0:
            break
        i = j + 1
    return i


def inline_runs(s, props=None, image_dir=None):
    props = props or {}
    runs, buf, i = [], "", 0

    def flush():
        nonlocal buf
        if buf:
            t = buf
            for a, b in UNESC:
                t = t.replace(a, b)
            runs.append({**props, "text": t})
            buf = ""
    while i < len(s):
        c = s[i]
        if c == "%" and (i == 0 or s[i - 1] != "\\"):
            j = s.find("\n", i)
            i = len(s) if j < 0 else j
            continue
        if c == "$" and (i == 0 or s[i - 1] != "\\"):
            j = s.find("$", i + 1)
            if j > i:
                flush()
                runs.append({**props, "text": s[i + 1:j], "i": True})
                i = j + 1
                continue
        if c == "\\":
            m = re.match(r"\\([A-Za-z]+)\*?", s[i:])
            if m:
                name = m.group(1)
                j = _skip_opt(s, i + m.end())
                if name in INLINE and j < len(s) and s[j] == "{":
                    flush()
                    inner, j = _arg(s, j)
                    runs += inline_runs(inner, {**props, **INLINE[name]}, image_dir)
                    i = j
                    continue
                if name == "footnote" and j < len(s) and s[j] == "{":
                    flush()
                    inner, j = _arg(s, j)
                    runs.append({"fn": "".join(r.get("text", "") for r in inline_runs(inner)), "text": ""})
                    i = j
                    continue
                if name == "href" and j < len(s) and s[j] == "{":
                    flush()
                    url, j = _arg(s, j)
                    text, j = _arg(s, j) if j < len(s) and s[j] == "{" else (url, j)
                    runs += inline_runs(text, {**props, "link": url})
                    i = j
                    continue
                if name == "url" and j < len(s) and s[j] == "{":
                    flush()
                    url, j = _arg(s, j)
                    runs.append({**props, "text": url, "link": url})
                    i = j
                    continue
                if name == "textcolor" and j < len(s) and s[j] == "{":
                    flush()
                    col, j = _arg(s, j)
                    inner, j = _arg(s, j) if j < len(s) and s[j] == "{" else ("", j)
                    color = "#" + col.upper() if re.fullmatch(r"[0-9A-Fa-f]{6}", col) else \
                        {"red": "#c00000", "blue": "#0b5394", "green": "#38761d", "orange": "#ff9900",
                         "gray": "#666666"}.get(col)
                    runs += inline_runs(inner, {**props, **({"color": color} if color else {})})
                    i = j
                    continue
                if name == "includegraphics" and j < len(s) and s[j] == "{":
                    flush()
                    fn, j = _arg(s, j)
                    path = os.path.join(image_dir, fn) if image_dir else fn
                    for cand in (path, path + ".png", path + ".jpg"):
                        if os.path.isfile(cand):
                            data = open(cand, "rb").read()
                            mime = df.sniff_mime(data)
                            if mime:
                                w, h = df.image_size(data)
                                if w > df.CONTENT_W_PX:
                                    w, h = df.CONTENT_W_PX, round(h * df.CONTENT_W_PX / w)
                                runs.append({"img": base64.b64encode(data).decode(), "mime": mime, "w": w, "h": h})
                            break
                    i = j
                    continue
                if name in ("label", "ref", "cite", "eqref", "pageref", "index", "hspace", "vspace", "phantom"):
                    k = j
                    if k < len(s) and s[k] == "{":
                        arg, k = _arg(s, k)
                        if name in ("ref", "eqref", "pageref"):
                            buf += "?"
                        elif name == "cite":
                            buf += f"[{arg}]"
                    i = k
                    continue
                # unbekannter Befehl: Symbol-Ersatz oder Argument behalten
                full = "\\" + name
                rep = next((b for a, b in UNESC if a == full), None)
                if rep is not None:
                    buf += rep
                    i += m.end()
                    continue
                if j < len(s) and s[j] == "{":
                    inner, j = _arg(s, j)
                    flush()
                    runs += inline_runs(inner, props, image_dir)
                    i = j
                    continue
                i = j
                continue
            buf += s[i:i + 2]
            i += 2
            continue
        if c in "{}":
            i += 1
            continue
        buf += c
        i += 1
    flush()
    out = []
    for r in runs:                            # Leerraum wie LaTeX zusammenfassen
        if "text" in r and not r.get("fn") and "img" not in r:
            r = dict(r, text=re.sub(r"[ \t\n]+", " ", r["text"]))
        out.append(r)
    return df.merge_runs(out)


def latex_to_blocks(src, image_dir=None):
    """→ (blöcke, titel)."""
    src = re.sub(r"(?<!\\)%[^\n]*", "", src)
    title = ""
    m = re.search(r"\\title\{", src)
    if m:
        title = re.sub(r"\\\\|\s+", " ", _arg(src, m.end() - 1)[0]).strip()
        title = "".join(r.get("text", "") for r in inline_runs(title)).strip()
    m = re.search(r"\\begin\{document\}(.*?)(\\end\{document\}|$)", src, re.S)
    body = m.group(1) if m else src
    body = re.sub(r"(?<!\\)%[^\n]*", "", body)
    blocks = []
    tokens = re.split(r"(\\begin\{[^}]+\}(?:\[[^\]]*\])?|\\end\{[^}]+\}|\\(?:sub)*section\*?\{|\\chapter\*?\{|"
                      r"\\paragraph\*?\{|\\maketitle|\\tableofcontents|\\newpage|\\clearpage|\\item(?:\[[^\]]*\])?|"
                      r"\\noindent\\rule\{[^}]*\}\{[^}]*\}|\n\s*\n)", body)
    lists = []                                 # [(art, ebene)]
    env = []
    pending = ""
    pending_style = "normal"
    align = "left"

    def emit(text, style="normal", lst=None, level=0, al="left"):
        runs = inline_runs(text, image_dir=image_dir)
        if not runs and style == "normal" and not lst:
            return
        p = df.para(style=style, align=al)
        p["runs"] = runs
        if lst:
            p["list"], p["indent"] = lst, level
        blocks.append(p)

    def flush():
        nonlocal pending
        if pending.strip():
            if lists:
                emit(pending.strip(), lst=lists[-1][0], level=lists[-1][1])
            else:
                emit(pending.strip(), "quote" if "quote" in env else pending_style, al=align)
        pending = ""
    i = 0
    while i < len(tokens):
        tk = tokens[i]
        i += 1
        if not tk:
            continue
        sec = re.match(r"\\((?:sub)*section|chapter|paragraph)\*?\{", tk)
        if sec:
            flush()
            rest = "{" + (tokens[i] if i < len(tokens) else "")
            arg, j = _arg(rest, 0)
            style = {"chapter": "h1", "section": "h1", "subsection": "h2", "subsubsection": "h3", "paragraph": "h3"}.get(sec.group(1), "h3")
            emit(arg, style)
            if i < len(tokens):
                tokens[i] = rest[j:]
            continue
        if tk == "\\maketitle":
            flush()
            if title:
                blocks.append(df.para(title, style="title"))
            continue
        if tk == "\\tableofcontents":
            flush()
            blocks.append({"t": "toc"})
            continue
        if tk in ("\\newpage", "\\clearpage"):
            flush()
            blocks.append({"t": "pb"})
            continue
        if tk.startswith("\\noindent\\rule"):
            flush()
            blocks.append({"t": "hr"})
            continue
        if tk.startswith("\\item"):
            flush()
            label = re.match(r"\\item\[([^\]]*)\]", tk)
            if label:
                pending = f"\\textbf{{{label.group(1)}}} "
            continue
        b = re.match(r"\\begin\{([^}]+)\}", tk)
        if b:
            name = b.group(1)
            flush()
            if name in ("itemize", "enumerate", "description"):
                lists.append(("number" if name == "enumerate" else "bullet", len(lists)))
            elif name in ("verbatim", "lstlisting"):
                end = "\\end{" + name + "}"
                code = ""
                while i < len(tokens) and tokens[i] != end:
                    code += tokens[i]
                    i += 1
                i += 1
                for line in code.strip("\n").split("\n"):
                    p = df.para(style="code")
                    p["runs"] = [{"text": line}] if line else []
                    blocks.append(p)
            elif name in ("tabular", "tabularx", "longtable"):
                end = "\\end{" + name + "}"
                if i < len(tokens) and tokens[i].lstrip().startswith("{"):     # Spaltendefinition überspringen
                    rest = tokens[i].lstrip()
                    if name == "tabularx":
                        rest = rest[_arg(rest, 0)[1]:].lstrip()
                    tokens[i] = rest[_arg(rest, 0)[1]:] if rest.startswith("{") else rest
                content = ""
                while i < len(tokens) and tokens[i] != end:
                    content += tokens[i]
                    i += 1
                i += 1
                content = re.sub(r"\\(hline|toprule|midrule|bottomrule|cline\{[^}]*\})", "", content)
                rows = []
                for r in re.split(r"\\\\", content):
                    if r.strip():
                        rows.append(["".join(x.get("text", "") for x in inline_runs(c.strip())) for c in re.split(r"(?<!\\)&", r)])
                if rows:
                    blocks.append({"t": "table", "rows": rows})
            elif name in ("center",):
                align = "center"
            elif name in ("flushright",):
                align = "right"
            elif name in ("equation", "equation*", "align", "align*", "gather", "gather*"):
                end = "\\end{" + name + "}"
                math = ""
                while i < len(tokens) and tokens[i] != end:
                    math += tokens[i]
                    i += 1
                i += 1
                p = df.para(style="normal", align="center")
                p["runs"] = [{"text": " ".join(math.split()), "i": True}]
                blocks.append(p)
            env.append(name)
            continue
        e = re.match(r"\\end\{([^}]+)\}", tk)
        if e:
            name = e.group(1)
            flush()
            if name in ("itemize", "enumerate", "description") and lists:
                lists.pop()
            if name in ("center", "flushright"):
                align = "left"
            if env and env[-1] == name:
                env.pop()
            continue
        if re.fullmatch(r"\n\s*\n", tk):
            flush()
            continue
        if "figure" in env or "table" in env:
            tk = re.sub(r"\\(caption|label)\{[^}]*\}", "", tk)
            tk = tk.replace("\\centering", "")
        pending += tk
    flush()
    return blocks or [df.para()], title
