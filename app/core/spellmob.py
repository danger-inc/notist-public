# Rechtschreibung für das Handy (Plan Schritt 28): dieselben hunspell-Wörterbücher (.aff/.dic) wie am PC, gelesen von „spylls“
# (reine Python-Umsetzung von Hunspell – keine native Bibliothek nötig, läuft in Chaquopy). Schnittstelle wie spell.Speller
# (available, known, suggest, codes), damit core.autofix dieselben Regeln anwendet. Eigene Wörter: data/words.txt (wird abgeglichen).
import os, re, threading

from core import paths

WORD = re.compile(r"[^\W\d_]+(?:['’\-][^\W\d_]+)*")
SKIP = re.compile(r"\S*(?:://|www\.|@)\S*|\S+\.(?:de|com|org|net|io|py|txt)\b")
VARIANTS = {"de": ("de_DE", "de_DE_frami", "de_AT", "de_CH", "de"), "en": ("en_US", "en_GB", "en_CA", "en_AU", "en")}
DIR_ENV = "NOTES_DICT_DIR"


def _dirs():
    out = [d for d in os.environ.get(DIR_ENV, "").split(os.pathsep) if d]
    return [d for d in out + [os.path.join(paths.HOME, "hunspell")] if os.path.isdir(d)]


class Speller:
    def __init__(self):
        self.lock = threading.RLock()
        self.dicts = {}                 # Sprache → spylls-Wörterbuch
        self.words = set()
        self.words_mtime = None
        self.ignored = set()
        self.langs = ["de", "en"]

    # ----- Wörterbücher -----
    def _load(self, lang):
        if lang in self.dicts:
            return self.dicts[lang]
        d = None
        for name in VARIANTS.get(lang, (lang,)):
            for base in _dirs():
                p = os.path.join(base, name)
                if os.path.exists(p + ".aff") and os.path.exists(p + ".dic"):
                    try:
                        from spylls.hunspell import Dictionary
                        d = Dictionary.from_files(p)
                    except Exception:  # noqa: BLE001
                        d = None
                    break
            if d is not None:
                break
        self.dicts[lang] = d
        return d

    def set_langs(self, langs):
        self.langs = [l for l in langs if l in VARIANTS] or []

    @property
    def available(self):
        return any(self._load(l) is not None for l in self.langs)

    @property
    def codes(self):
        return tuple(l for l in self.langs if self._load(l) is not None)

    def installed(self):
        return {l: self._load(l) is not None for l in VARIANTS}

    # ----- eigene Wörter -----
    def _personal(self):
        try:
            m = os.path.getmtime(paths.WORDS)
        except OSError:
            self.words, self.words_mtime = set(), None
            return self.words
        if m != self.words_mtime:
            with open(paths.WORDS, encoding="utf-8") as f:
                self.words = {w.strip() for w in f if w.strip()}
            self.words_mtime = m
        return self.words

    def add_word(self, word):
        word = word.strip()
        if not word:
            return
        with self.lock:
            ws = set(self._personal()); ws.add(word)
            os.makedirs(os.path.dirname(paths.WORDS), exist_ok=True)
            tmp = paths.WORDS + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                f.write("".join(w + "\n" for w in sorted(ws)))
            os.replace(tmp, paths.WORDS)
            self.words_mtime = None

    # ----- Prüfen -----
    def known(self, word):
        if word in self.ignored or word in self._personal() or word.lower() in self._personal():
            return True
        for l in self.langs:
            d = self._load(l)
            if d is not None and d.lookup(word):
                return True
        return False

    def suggest(self, word, n=8):
        out = []
        for l in self.langs:
            d = self._load(l)
            if d is None:
                continue
            for s in d.suggest(word):
                s = str(s)
                if s not in out:
                    out.append(s)
                if len(out) >= n * 2:
                    break
        # nach Ähnlichkeit zum Wort sortieren (mehrere Sprachen)
        import difflib
        out.sort(key=lambda s: -difflib.SequenceMatcher(None, word.lower(), s.lower()).ratio())
        return out[:n]

    def check(self, text):
        """→ [(start, ende, wort)] falsch geschriebener Wörter (Indizes in UTF-16-Einheiten wie Kotlin-Strings)."""
        out = []
        skip = [(m.start(), m.end()) for m in SKIP.finditer(text)]
        for m in WORD.finditer(text):
            w = m.group(0)
            if len(w) < 2 or any(a <= m.start() < b for a, b in skip):
                continue
            if w.isupper() and len(w) <= 5:
                continue
            if not self.known(w):
                out.append((_u16(text, m.start()), _u16(text, m.end()), w))
        return out


def _u16(text, i):
    return len(text[:i].encode("utf-16-le")) // 2


_S = None


def get():
    global _S
    if _S is None:
        _S = Speller()
    return _S
