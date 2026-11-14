# Automatisches Formatieren beim Tippen (Notizen und Words) – alles einzeln abschaltbar (Mehr-Menü, Einstellungen):
#   typo     „Anführungszeichen“, -- → –, ... → …, -> → →, <- → ←, => → ⇒
#   autocap  erster Buchstabe eines Satzes groß
#   smart    Wort nach Leerzeichen/Satzzeichen korrigieren: SChreibstift → Schreibstift, hALLO → Hallo,
#            Tippfehler-Liste (teh → the, nciht → nicht, eigene in prefs["autocorrect"]), mit Wörterbuch:
#            vertauschte Buchstaben (Tset → Test), Nomen groß (schreibstift → Schreibstift).
#            Rücktaste direkt danach macht die Korrektur rückgängig (und das Wort bleibt dann in Ruhe).
# Dazu tidy(): Notiz einmal aufräumen (Leerzeichen am Zeilenende, doppelte Leerzeichen, zu viele Leerzeilen).
# Ersetzt wird im Leerlauf nach dem Einfügen (während des insert-text-Signals darf der Puffer nicht verändert werden).
import re

from gi.repository import GLib
from core.autofix import *  # noqa: F401,F403
from core.autofix import (_swapped, _case_like, _fix_quote, _reverted)  # noqa: F401

_last = {}            # Puffer → letzte Korrektur (für Rücktaste = rückgängig)
_hooked = set()


def _hook(buf):
    if hash(buf) in _hooked:
        return
    _hooked.add(hash(buf))
    buf.connect("insert-text", lambda b, *_: _last.pop(hash(b), None) if not getattr(b, "_af_busy", False) else None)
    buf.connect("delete-range", _on_delete)


def _on_delete(buf, start, end):
    last = _last.pop(hash(buf), None)
    if not last or getattr(buf, "_af_busy", False):
        return
    st, mark, word, fix = last
    after = buf.get_iter_at_mark(mark)
    if end.get_offset() - start.get_offset() != 1 or not end.equal(after):
        buf.delete_mark(st)
        buf.delete_mark(mark)
        return

    def revert():                                # Grenzzeichen ist jetzt weg: Wort zurücksetzen
        a, b = buf.get_iter_at_mark(st), buf.get_iter_at_mark(mark)
        if buf.get_text(a, b, False) == fix:
            tags = a.get_tags()
            buf._af_busy = True
            buf.begin_user_action()
            buf.delete(a, b)
            buf.insert(a, word)
            b = buf.get_iter_at_mark(mark)
            a = b.copy()
            a.backward_chars(len(word))
            for t in tags:
                buf.apply_tag(t, a, b)
            buf.end_user_action()
            buf._af_busy = False
            _reverted.add(word)
            try:
                import spell
                spell.speller().ignore(word)
            except Exception:
                pass
        buf.delete_mark(st)
        buf.delete_mark(mark)
        return False
    GLib.idle_add(revert)


# Satzanfang groß: löscht man den gerade groß gemachten Buchstaben, bleibt die Stelle danach klein
_capped = {}          # Puffer → Marke vor dem zuletzt groß gemachten Buchstaben
_declined = {}        # Puffer → Marke einer Stelle, an der man die Großschreibung wieder gelöscht hat
_cap_hooked = set()


def _drop(store, buf):
    m = store.pop(hash(buf), None)
    if m is not None and not m.get_deleted():
        buf.delete_mark(m)


def _hook_cap(buf):
    if hash(buf) in _cap_hooked:
        return
    _cap_hooked.add(hash(buf))
    buf.connect("delete-range", _on_cap_delete)


def _on_cap_delete(buf, start, end):
    m = _capped.get(hash(buf))
    if m is None or getattr(buf, "_af_busy", False) or m.get_deleted():
        return
    off = buf.get_iter_at_mark(m).get_offset()
    if start.get_offset() <= off < end.get_offset():
        _drop(_declined, buf)
        _declined[hash(buf)] = _capped.pop(hash(buf))      # Marke bleibt an der Löschstelle stehen


def smart_after(buf, loc, text, prefs, skip=None):
    """Grenzzeichen getippt: Wort davor prüfen und ggf. im Leerlauf ersetzen."""
    if text not in BOUNDARY or not opt(prefs, "smart"):
        return False
    line_start = loc.copy()
    line_start.set_line_offset(0)
    before = buf.get_text(line_start, loc, False)[:-1]
    m = WORD_END.search(before)
    if not m:
        return False
    word = m.group(1)
    sp = None
    try:
        import spell
        sp = spell.speller()
    except Exception:
        pass
    fix = correction(word, prefs, sp)
    if not fix or fix == word or (skip and skip(loc)):
        return False
    _hook(buf)
    mark = buf.create_mark(None, loc, True)

    def run():
        end = buf.get_iter_at_mark(mark)
        end.backward_char()
        start = end.copy()
        start.backward_chars(len(word))
        if buf.get_text(start, end, False) != word:
            buf.delete_mark(mark)
            return False
        tags = [t for t in start.get_tags() if t.props.name != "spell-err"]
        buf._af_busy = True
        buf.begin_user_action()
        buf.delete(start, end)
        buf.insert(start, fix)
        end = buf.get_iter_at_mark(mark)
        end.backward_char()
        start = end.copy()
        start.backward_chars(len(fix))
        for t in tags:
            buf.apply_tag(t, start, end)
        buf.end_user_action()
        buf._af_busy = False
        old = _last.pop(hash(buf), None)
        if old:
            buf.delete_mark(old[0])
            buf.delete_mark(old[1])
        _last[hash(buf)] = (buf.create_mark(None, start, True), mark, word, fix)
        return False
    GLib.idle_add(run)
    return True


def after_type(buf, loc, text, prefs, skip=None):
    """Nach einem getippten Zeichen aufrufen (connect_after von insert-text). skip(iter) → True = hier nichts tun
    (z. B. Code, Formel). Gibt True zurück, wenn eine Ersetzung geplant ist."""
    if len(text) != 1:
        return False
    smart = smart_after(buf, loc, text, prefs, skip)
    typo, cap = opt(prefs, "typo"), opt(prefs, "autocap")
    if not (typo or cap):
        return smart
    line_start = loc.copy()
    line_start.set_line_offset(0)
    before = buf.get_text(line_start, loc, False)          # Zeile bis einschließlich des neuen Zeichens
    job = None
    if typo and text == '"':
        prev = before[-2] if len(before) >= 2 else " "
        opening = prev.isspace() or prev in "([{–—/„“￼"
        if getattr(buf, "lang", "de") == "en":
            job = (1, "“" if opening else "”")
        else:
            job = (1, "„" if opening else "“")
    elif typo:
        for a, b in PAIRS:
            if before.endswith(a) and not before.endswith(a + a[-1]):
                if a == "--" and before.endswith("---"):
                    break
                job = (len(a), b)
                break
    if job is None and cap and text.isalpha() and text.islower():
        head = before[:-1]
        rest = head[LIST_HEAD.match(head).end():]
        words = rest.split()
        last = words[-1] if words else ""
        new_sentence = not rest or (re.search(r"[.!?]\s+$", rest) and not ABBR.search(rest)
                                    and not re.search(r"\d\.\s+$", rest))
        if new_sentence and "://" not in last and "@" not in last:
            dm = _declined.get(hash(buf))
            if dm is not None and not dm.get_deleted() and buf.get_iter_at_mark(dm).get_offset() == loc.get_offset() - 1:
                _drop(_declined, buf)          # hier wurde das Groß gerade gelöscht → klein lassen
            else:
                job = (1, text.upper())
    if job is None:
        return smart
    if skip and skip(loc):
        return smart
    mark = buf.create_mark(None, loc, True)    # bleibt direkt hinter dem Zeichen, auch wenn danach weitergetippt wird

    def run():
        it = buf.get_iter_at_mark(mark)
        start = it.copy()
        n, repl = job
        ok = start.backward_chars(n)
        if ok and buf.get_text(start, it, False)[-1:] == text:
            at = start.get_offset()
            busy = getattr(buf, "_af_busy", False)
            buf._af_busy = True
            buf.begin_user_action()
            buf.delete(start, it)
            buf.insert(start, repl)
            buf.end_user_action()
            buf._af_busy = busy
            if repl.isupper() and len(repl) == 1 and n == 1:     # Satzanfang: Stelle merken (für Rücktaste)
                _hook_cap(buf)
                _drop(_capped, buf)
                _capped[hash(buf)] = buf.create_mark(None, buf.get_iter_at_offset(at), True)
        buf.delete_mark(mark)
        return False
    GLib.idle_add(run)
    return True


def tidy(buf):
    """Notiz aufräumen, Formatierung bleibt: Leerzeichen am Zeilenende, doppelte Leerzeichen im Text und mehr als
    eine Leerzeile hintereinander. Gibt die Zahl der Änderungen zurück."""
    text = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), True)
    cuts = []                                   # (start, ende) als Zeichen-Offsets, von hinten nach vorn löschen
    off = 0
    blank = 0
    for line in text.split("\n"):
        n = len(line)
        stripped = line.rstrip(" \t")
        if stripped != line:
            cuts.append((off + len(stripped), off + n))
        if not stripped.strip():
            blank += 1
            if blank > 1:                           # zweite Leerzeile in Folge: samt Zeilenumbruch weg
                cuts.append((off - 1, off + n))
        else:
            blank = 0
            lead = len(stripped) - len(stripped.lstrip(" \t"))
            for m in re.finditer(r"(?<=\S) {2,}(?=\S)", stripped[lead:]):
                cuts.append((off + lead + m.start() + 1, off + lead + m.end()))
        off += n + 1
    # überlappende zusammenfassen
    cuts.sort()
    merged = []
    for a, b in cuts:
        if merged and a <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(b, merged[-1][1]))
        else:
            merged.append((a, b))
    if not merged:
        return 0
    buf.begin_user_action()
    for a, b in reversed(merged):
        buf.delete(buf.get_iter_at_offset(a), buf.get_iter_at_offset(b))
    buf.end_user_action()
    return len(merged)
