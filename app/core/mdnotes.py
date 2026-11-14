# Markdown ↔ Notizen (Text + Formatierungs-Spannen wie in note["rich"]).
# Notizen kennen fett/kursiv/unterstrichen/durchgestrichen, Schriften, • Listen, 1. Listen und ☐/☑-Checklisten.
# Überschriften werden fett, Code bekommt die Monospace-Schrift, Links werden „Text (URL)“.
import re

BULLET = "•"
BOX_OPEN, BOX_DONE = "☐", "☑"
MONO = "Noto Sans Mono"
MONO_FONTS = ("mono", "code", "courier", "consol")

_INLINE = re.compile(r"\*\*(?=\S)(.+?)(?<=\S)\*\*|__(?=\S)(.+?)(?<=\S)__|(?<![*\w])\*(?=\S)(.+?)(?<=\S)\*(?!\*)"
                     r"|(?<![_\w])_(?=\S)(.+?)(?<=\S)_(?![_\w])|~~(?=\S)(.+?)(?<=\S)~~|`([^`]+)`"
                     r"|!\[([^\]]*)\]\(([^)]*)\)|\[([^\]]+)\]\(([^)]+)\)|<u>(.+?)</u>")


def looks_like_markdown(text):
    """Grobe Erkennung beim Einfügen: nur umwandeln, wenn klar Markdown drinsteckt."""
    if len(text) > 400_000:
        return False
    marks = 0
    marks += len(re.findall(r"^#{1,6} \S", text, re.M)) * 2
    marks += len(re.findall(r"^\s*[-*+] \[[ xX]\] ", text, re.M)) * 2
    marks += len(re.findall(r"\*\*\S.*?\S\*\*|__\S.*?\S__|~~\S.*?\S~~", text))
    marks += len(re.findall(r"\[[^\]]+\]\([^)\s]+\)", text))
    marks += len(re.findall(r"^```", text, re.M)) * 2
    marks += len(re.findall(r"`[^`\n]+`", text))
    lists = len(re.findall(r"^\s*[-*+] \S", text, re.M))
    return marks >= 2 or (marks >= 1 and lists >= 1)


def _inline(s, out, spans, base=()):
    """Inline-Markdown in out (Liste von Textstücken) schreiben, Spannen mit absoluten Offsets."""
    s = re.sub(r"\*\*\*(?=\S)(.+?)(?<=\S)\*\*\*", r"**_\1_**", s)     # ***fett+kursiv***
    pos = 0
    off = lambda: sum(len(x) for x in out)         # noqa: E731

    def emit(text, styles):
        start = off()
        out.append(text)
        for st in styles:
            spans.append([start, start + len(text), st])

    for m in _INLINE.finditer(s):
        if m.start() > pos:
            emit(s[pos:m.start()], base)
        g = m.groups()
        if g[0] or g[1] or g[2] or g[3]:
            style = "bold" if (g[0] or g[1]) else "italic"
            sub, sub_spans = [], []
            _inline(g[0] or g[1] or g[2] or g[3], sub, sub_spans, ())
            start = off()
            out.extend(sub)
            for a, b, n in sub_spans:
                spans.append([a + start, b + start, n])
            for st in tuple(base) + (style,):
                spans.append([start, start + len("".join(sub)), st])
        elif g[4]:
            emit(g[4], tuple(base) + ("strike",))
        elif g[5]:
            emit(g[5], tuple(base) + ("font:" + MONO,))
        elif g[6] is not None or g[7] is not None:
            emit(g[6] or "Bild", base)                 # Bilder aus Markdown: nur der Alternativtext
        elif g[8]:
            emit(g[8], base)
            if g[9] and g[9] != g[8]:
                emit(f" ({g[9]})", base)
        elif g[10]:
            emit(g[10], tuple(base) + ("underline",))
        pos = m.end()
    if pos < len(s):
        emit(s[pos:], base)


def split_title(md):
    """Beginnt das Dokument mit „# Titel“, wird das der Notiztitel → (titel, rest)."""
    m = re.match(r"^\s*# +(.+?)\s*#*\s*(?:\n|$)", md)
    if not m:
        return "", md
    return m.group(1).strip(), md[m.end():].lstrip("\n")


def to_note(md):
    """Markdown → (text, rich-Spannen)."""
    out, spans = [], []
    lines = md.replace("\r\n", "\n").split("\n")
    code = False
    for i, line in enumerate(lines):
        if i:
            out.append("\n")
        if line.lstrip().startswith("```"):
            code = not code
            if out and out[-1] == "\n":
                out.pop()                              # Zaunzeile selbst nicht übernehmen
            continue
        if code:
            start = sum(len(x) for x in out)
            out.append(line)
            spans.append([start, start + len(line), "font:" + MONO])
            continue
        m = re.match(r"^(#{1,6})\s+(.*?)\s*#*\s*$", line)
        if m:
            _inline(m.group(2), out, spans, ("bold",))
            continue
        if re.match(r"^\s*([-*_])\s*\1\s*\1[\s\1]*$", line):
            out.append("─" * 24)
            continue
        m = re.match(r"^(\s*)[-*+] \[([ xX])\] (.*)$", line)
        if m:
            out.append(m.group(1) + (BOX_OPEN if m.group(2) == " " else BOX_DONE) + " ")
            _inline(m.group(3), out, spans)
            continue
        m = re.match(r"^(\s*)[-*+] (.*)$", line)
        if m:
            out.append(m.group(1) + BULLET + " ")
            _inline(m.group(2), out, spans)
            continue
        m = re.match(r"^(\s*)(\d+)[.)] (.*)$", line)
        if m:
            out.append(f"{m.group(1)}{m.group(2)}. ")
            _inline(m.group(3), out, spans)
            continue
        m = re.match(r"^>\s?(.*)$", line)
        if m:
            _inline(m.group(1), out, spans, ("italic",))
            continue
        _inline(line, out, spans)
    return "".join(out), merge(spans)


def merge(spans):
    """Aneinanderstoßende Spannen gleichen Namens zusammenfassen."""
    by = {}
    for a, b, n in spans:
        if b > a:
            by.setdefault(n, []).append([a, b])
    out = []
    for n, lst in by.items():
        lst.sort()
        cur = lst[0]
        for a, b in lst[1:]:
            if a <= cur[1]:
                cur[1] = max(cur[1], b)
            else:
                out.append([cur[0], cur[1], n])
                cur = [a, b]
        out.append([cur[0], cur[1], n])
    return sorted(out)


def _wrap(text, styles):
    core = text.strip()
    if not core or not styles:
        return text
    lead, trail = text[:len(text) - len(text.lstrip())], text[len(text.rstrip()):]
    if "code" in styles:
        return f"{lead}`{core}`{trail}"
    for st, mk in (("strike", "~~"), ("italic", "*"), ("bold", "**")):
        if st in styles:
            core = f"{mk}{core}{mk}"
    if "underline" in styles:
        core = f"<u>{core}</u>"
    return lead + core + trail


def table_md(rows):
    """Tabelle einer Notiz → Markdown-Tabelle (erste Zeile = Kopf)."""
    rows = [list(r) for r in rows if r] or [[""]]
    ncol = max(len(r) for r in rows)
    line = lambda r: "| " + " | ".join((r[c] if c < len(r) else "").replace("\n", " ").replace("|", "\\|")
                                       for c in range(ncol)) + " |"
    return "\n".join([line(rows[0]), "|" + "---|" * ncol] + [line(r) for r in rows[1:]])


def from_note(text, rich, title="", images=None):
    """(text, rich) → Markdown. Platzhalter (U+FFFC) = Bilder (entfallen) oder Tabellen (images[k]["table"])."""
    slots = iter(images or [])
    styles = [set() for _ in range(len(text) + 1)]
    for a, b, n in rich or []:
        st = n
        if n.startswith("font:"):
            if not any(k in n.lower() for k in MONO_FONTS):
                continue
            st = "code"
        for i in range(max(0, a), min(b, len(text))):
            styles[i].add(st)
    lines_out, pos = [], 0
    for line in text.split("\n"):
        # Zeilenanfang (Liste/Checkbox) ohne Formatierung übernehmen
        prefix = ""
        m = re.match(r"^(\s*)(☐|☑) ?", line)
        if m:
            prefix = m.group(1) + ("- [ ] " if m.group(2) == BOX_OPEN else "- [x] ")
        else:
            m = re.match(r"^(\s*)• ", line)
            if m:
                prefix = m.group(1) + "- "
            else:
                m = re.match(r"^(\s*)(\d+)\. ", line)
                if m:
                    prefix = m.group(0)
        body_start = len(m.group(0)) if m else 0
        body = line[body_start:]
        chunks, cur, cur_st = [], "", None
        for k, ch in enumerate(body):
            s = frozenset(styles[pos + body_start + k])
            if s != cur_st and cur:
                chunks.append((cur, cur_st))
                cur = ""
            cur_st = s
            cur += ch
        if cur:
            chunks.append((cur, cur_st))
        md = "".join(_wrap(t, set(s or ())) for t, s in chunks)
        if not prefix and re.match(r"^(#{1,6} |[-*+] |\d+\. |> )", md):
            md = "\\" + md                       # sonst würde es beim Wiedereinlesen zur Liste/Überschrift
        if "￼" in md:
            parts = md.split("￼")
            md = parts[0]
            for rest in parts[1:]:
                info = next(slots, None) or {}
                md += ("\n\n" + table_md(info["table"]["rows"]) + "\n\n" if info.get("table") else "") + rest
        lines_out.append(prefix + md)
        pos += len(line) + 1
    body = "\n".join(lines_out)
    title = (title or "").strip()
    return (f"# {title}\n\n" if title else "") + body
