# Übersetzer Deutsch ⇄ Englisch: kleines Fenster unten rechts (Statusleiste „übersetzer“, Strg+Umschalt+T).
# Wörter schlägt notist offline im Wörterbuch der TU Chemnitz nach („ding“, GPL, ~200 000 Einträge), einmal geladen
# und in eine SQLite-Datei übersetzt (~/.local/share/notes/dict/de-en.sqlite). Ergebnisse sind nach Wortart und
# Bedeutung geordnet; ein Klick auf ein Wort kopiert es. Ganze Sätze gehen nur auf Klick/Enter online (MyMemory).
# Weitere Sprachen (Deutsch ⇄ Französisch, Spanisch …) lassen sich optional laden: WikDict (aus Wiktionary,
# CC BY-SA), je Richtung eine fertige SQLite-Datei unter ~/.local/share/notes/dict/wikdict/.
import json, lzma, os, re, sqlite3, threading, urllib.parse, urllib.request

from core import paths, plat

# Hauptfaden-Übergabe: die GTK-Oberfläche setzt UI_CALL = GLib.idle_add-Hülle; ohne Oberfläche (Handy) wird direkt aufgerufen.
UI_CALL = None


def _ui(fn):
    (UI_CALL or (lambda f: f()))(fn)


def _tr(s, *a):
    try:
        import i18n
        return i18n.tr(s, *a)
    except ImportError:
        return s.format(*a) if a else s

DICT_DIR = os.path.join(paths.HOME, "dict")
DB = os.path.join(DICT_DIR, "de-en.sqlite")
URL = "https://ftp.tu-chemnitz.de/pub/Local/urz/ding/de-en/de-en.txt.xz"
# Paket „trans-de-en“ (Debian/Ubuntu) bzw. ding bringt die Datei schon mit – dann nichts herunterladen
LOCAL = tuple(plat.local_dict_files())
ONLINE = "https://api.mymemory.translated.net/get?{}"
DB_VERSION = 2
WIKDICT_URL = "https://download.wikdict.com/dictionaries/sqlite/2/{}.sqlite3"
WIKDICT_DIR = os.path.join(DICT_DIR, "wikdict")
# Sprachen, die WikDict mit Deutsch anbietet (Englisch kommt aus ding)
LANGS = {"en": "Englisch", "fr": "Französisch", "es": "Spanisch", "it": "Italienisch", "nl": "Niederländisch",
         "pt": "Portugiesisch", "pl": "Polnisch", "sv": "Schwedisch", "da": "Dänisch", "no": "Norwegisch",
         "fi": "Finnisch", "cs": "Tschechisch", "ru": "Russisch", "tr": "Türkisch", "el": "Griechisch",
         "ja": "Japanisch", "zh": "Chinesisch", "la": "Latein", "bg": "Bulgarisch", "ca": "Katalanisch",
         "lt": "Litauisch", "id": "Indonesisch"}
# Wortarten aus WikDict (je nach Sprache benannt) → unsere Gruppen
WD_TYPES = {"substantiv": "Substantiv", "noun": "Substantiv", "nom": "Substantiv", "sustantivo": "Substantiv",
            "sostantivo": "Substantiv", "zelfstandig naamwoord": "Substantiv", "verb": "Verb", "verbe": "Verb",
            "verbo": "Verb", "werkwoord": "Verb", "adjektiv": "Adjektiv", "adjective": "Adjektiv",
            "adjectif": "Adjektiv", "adjetivo": "Adjektiv", "aggettivo": "Adjektiv", "adverb": "Adverb",
            "adverbe": "Adverb", "adverbio": "Adverb", "avverbio": "Adverb", "eigenname": "Eigenname",
            "proper noun": "Eigenname", "redewendung": "Wendung", "präposition": "Präposition",
            "konjunktion": "Konjunktion", "adj": "Adjektiv", "adv": "Adverb",
            "nom propre": "Eigenname", "locution": "Wendung", "pronomen": "Pronomen", "interjektion": "Ausruf", "numerale": "Zahlwort"}

WORDTYPES = (  # (Bezeichnung, ding-Kürzel)
    ("Substantiv", ("m", "f", "n", "pl", "m,f", "m,n", "n,m", "f,n", "n,f", "f,m", "n,pl", "m,f,n")),
    ("Verb", ("vt", "vi", "vr", "v")),
    ("Adjektiv", ("adj",)),
    ("Adverb", ("adv",)),
    ("Präposition", ("prp",)),
    ("Konjunktion", ("conj",)),
    ("Pronomen", ("pron", "ppron", "relativ.pron", "pron interrog")),
    ("Ausruf", ("interj",)),
    ("Zahlwort", ("num",)),
    ("Artikel", ("art",)),
)
TYPE_OF = {k: name for name, ks in WORDTYPES for k in ks}
ARTICLE = {"m": "der", "f": "die", "n": "das", "pl": "die"}
FILLER = re.compile(r"^(jd[nmsr]?|etw|sich|sb|sth|sb's|one's|oneself|so|sth's)\.?(/\S+)?$", re.I)
NOTE = re.compile(r"\{[^}]*\}|\[[^\]]*\]|\([^)]*\)|<[^>]*>")


# ---------------- Wörterbuch ----------------
def split_syn(s):
    """„a; b (x; y); c“ → [a, b (x; y), c] – Semikolon in Klammern trennt nicht."""
    out, depth, cur = [], 0, ""
    for ch in s:
        if ch in "([{":
            depth += 1
        elif ch in ")]}" and depth:
            depth -= 1
        if ch == ";" and depth == 0:
            out.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if cur.strip():
        out.append(cur.strip())
    return out


def clean(s):
    """Suchschlüssel: ohne {Wortart} [Gebiet] (Hinweis), klein, Leerraum zusammengefasst."""
    return re.sub(r"\s+", " ", NOTE.sub(" ", s)).strip().lower()


def keys_for(s, en):
    """Schlüssel einer Fundstelle: der Text selbst, bei Verben auch ohne „to“, ohne jdn./etw./sich."""
    k = clean(s)
    if not k:
        return []
    out = [k]
    words = k.split()
    if en and words[0] == "to" and len(words) > 1:
        words = words[1:]
        out.append(" ".join(words))
    core = [w for w in words if not FILLER.match(w)]
    if core and len(core) < len(words):
        out.append(" ".join(core))
    return list(dict.fromkeys(out))


def tags(s):
    """Wortart-Kürzel einer Fundstelle: „Haus {n}“ → ["n"]."""
    return [t.split(";")[0].strip() for t in re.findall(r"\{([^}]*)\}", s)]


def word_type(de, en):
    for t in tags(de):
        if t in TYPE_OF:
            return TYPE_OF[t]
    if clean(en).startswith("to "):
        return "Verb"
    return "Sonstiges"


def pretty(s):
    """Fundstelle lesbar: „Haus {n}; Zuhause {n}“ → „das Haus · das Zuhause“, Wortart-Kürzel weg."""
    out = []
    for syn in split_syn(s):
        t = tags(syn)
        art = ARTICLE.get(t[0]) if t else None
        syn = re.sub(r"\s*\{[^}]*\}", "", syn).strip()
        if art == "die" and t[0] == "pl":
            syn += " (Plural)"
        out.append(f"{art} {syn}" if art else syn)
    return " · ".join(x for x in out if x)


def available():
    return os.path.exists(DB)


def local_source():
    return next((p for p in LOCAL if os.path.exists(p)), None)


def build(lines, progress=None):
    """ding-Zeilen → SQLite (erst in eine Zwischendatei, dann umbenennen)."""
    os.makedirs(DICT_DIR, exist_ok=True)
    tmp = DB + ".tmp"
    if os.path.exists(tmp):
        os.remove(tmp)
    con = sqlite3.connect(tmp)
    con.execute("PRAGMA journal_mode=OFF")
    con.execute("PRAGMA synchronous=OFF")
    con.execute("CREATE TABLE e(id INTEGER PRIMARY KEY, de TEXT, en TEXT)")
    con.execute("CREATE TABLE k(w TEXT, side INTEGER, id INTEGER, sub INTEGER, syn INTEGER, "
                "PRIMARY KEY(w, side, id, sub)) WITHOUT ROWID")
    con.execute("CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT)")
    fts = True
    try:
        con.execute("CREATE VIRTUAL TABLE f USING fts5(de, en, content='e', content_rowid='id', detail='column')")
    except sqlite3.OperationalError:
        fts = False
    entries, keys = [], []
    n = 0
    for line in lines:
        if not line or line.startswith("#") or " :: " not in line:
            continue
        de, en = line.rstrip("\n").split(" :: ", 1)
        n += 1
        entries.append((n, de, en))
        for side, text in ((0, de), (1, en)):
            for sub, part in enumerate(text.split(" | ")):
                syns = split_syn(part)
                if sub and len(clean(part).split()) > 3:     # lange Wendung: findet die Volltextsuche
                    continue
                for j, syn in enumerate(syns):
                    for k in keys_for(syn, side == 1):
                        keys.append((k, side, n, sub, j))
        if len(entries) >= 5000:
            con.executemany("INSERT INTO e VALUES (?,?,?)", entries)
            con.executemany("INSERT OR IGNORE INTO k VALUES (?,?,?,?,?)", keys)
            entries, keys = [], []
            if progress:
                progress(n)
    con.executemany("INSERT INTO e VALUES (?,?,?)", entries)
    con.executemany("INSERT OR IGNORE INTO k VALUES (?,?,?,?,?)", keys)
    if fts:
        con.execute("INSERT INTO f(f) VALUES ('rebuild')")
    con.execute("INSERT INTO meta VALUES ('version', ?)", (str(DB_VERSION),))
    con.execute("INSERT INTO meta VALUES ('entries', ?)", (str(n),))
    con.commit()
    con.execute("VACUUM")
    con.close()
    os.replace(tmp, DB)
    return n


def install(progress, done):
    """Im Hintergrund: Wörterbuch laden (oder vorhandene Datei nehmen) und einrichten.
    progress(text, anteil 0..1 oder None), done(fehler oder None) – beides im GTK-Hauptthread."""
    def ui(fn, *a):
        _ui(lambda: fn(*a))

    def work():
        try:
            src = local_source()
            if src:
                with open(src, encoding="utf-8", errors="replace") as f:
                    lines = f.read().splitlines()
            else:
                req = urllib.request.Request(URL, headers={"User-Agent": "notist"})
                with urllib.request.urlopen(req, timeout=30) as r:
                    total = int(r.headers.get("Content-Length") or 0)
                    data, got = bytearray(), 0
                    while True:
                        chunk = r.read(65536)
                        if not chunk:
                            break
                        data += chunk
                        got += len(chunk)
                        ui(progress, _tr("lade wörterbuch … {} MB", f"{got / 1e6:.1f}"),
                           got / total * 0.5 if total else None)
                lines = lzma.decompress(bytes(data)).decode("utf-8", "replace").splitlines()
            total = len(lines) or 1
            build(lines, lambda n: ui(progress, _tr("richte wörterbuch ein …"), 0.5 + 0.5 * n / total))
            ui(done, None)
        except Exception as e:  # noqa: BLE001 – Netz weg, Platte voll …
            ui(done, str(e))
    threading.Thread(target=work, daemon=True).start()


def wd_path(pair):
    return os.path.join(WIKDICT_DIR, pair + ".sqlite3")


def wd_installed():
    """Geladene Zusatzsprachen (beide Richtungen vorhanden)."""
    return [k for k in LANGS if k != "en" and os.path.exists(wd_path(f"de-{k}")) and os.path.exists(wd_path(f"{k}-de"))]


def wd_install(lang, progress, done):
    """Beide Richtungen de-xx und xx-de laden, Index anlegen. progress(text, anteil), done(fehler) im Hauptthread."""
    def ui(fn, *a):
        _ui(lambda: fn(*a))

    def work():
        try:
            os.makedirs(WIKDICT_DIR, exist_ok=True)
            pairs = (f"de-{lang}", f"{lang}-de")
            for i, pair in enumerate(pairs):
                tmp = wd_path(pair) + ".tmp"
                req = urllib.request.Request(WIKDICT_URL.format(pair), headers={"User-Agent": "notist"})
                with urllib.request.urlopen(req, timeout=30) as r, open(tmp, "wb") as f:
                    total, got = int(r.headers.get("Content-Length") or 0), 0
                    while True:
                        chunk = r.read(262144)
                        if not chunk:
                            break
                        f.write(chunk)
                        got += len(chunk)
                        ui(progress, _tr("lade {} … {} MB", pair, f"{got / 1e6:.0f}"),
                           (i + (got / total if total else 0)) / 2)
                con = sqlite3.connect(tmp)
                con.execute("CREATE INDEX IF NOT EXISTS ix_rep ON translation(written_rep COLLATE NOCASE)")
                con.commit()
                con.close()
                os.replace(tmp, wd_path(pair))
            ui(done, None)
        except Exception as e:  # noqa: BLE001
            for pair in (f"de-{lang}", f"{lang}-de"):
                for f in (wd_path(pair) + ".tmp",):
                    if os.path.exists(f):
                        os.remove(f)
            ui(done, str(e))
    threading.Thread(target=work, daemon=True).start()


def wd_remove(lang):
    for pair in (f"de-{lang}", f"{lang}-de"):
        try:
            os.remove(wd_path(pair))
        except OSError:
            pass


class WikDict:
    """Deutsch ⇄ andere Sprache aus WikDict – liefert dasselbe Format wie Dictionary.lookup."""

    def __init__(self, lang):
        self.lang = lang
        self.cons = {}

    def con(self, pair):
        if pair not in self.cons:
            self.cons[pair] = sqlite3.connect(wd_path(pair), check_same_thread=False)
        return self.cons[pair]

    def guess(self, q):
        w = q.strip().split()[0] if q.strip() else ""
        hit = lambda pair: self.con(pair).execute(
            "SELECT 1 FROM translation WHERE written_rep=? COLLATE NOCASE LIMIT 1", (w,)).fetchone()
        if re.search(r"[äöüß]", q.lower()) or hit(f"de-{self.lang}"):
            return "de"
        return self.lang if hit(f"{self.lang}-de") else "de"

    def lookup(self, q, direction="auto"):
        q = re.sub(r"\s+", " ", q).strip()
        if not q:
            return []
        sides = {"auto": ("de", self.lang), "de": ("de",)}.get(direction, (self.lang,))
        out = []
        for src in sides:
            res = self._side(q, src)
            if res["groups"]:
                out.append(res)
        if direction == "auto" and any(r["exact"] for r in out):
            out = [r for r in out if r["exact"]]
        out.sort(key=lambda r: -r["score"])
        return out

    def _side(self, q, src):
        pair = f"{src}-{self.lang}" if src == "de" else f"{self.lang}-de"
        con = self.con(pair)
        sql = ("SELECT lexentry, written_rep, sense, trans_list, score FROM translation WHERE {} "
               "ORDER BY importance DESC, score DESC LIMIT 60")
        rows = con.execute(sql.format("written_rep=? COLLATE NOCASE"), (q,)).fetchall()
        exact = len(rows)
        if not rows and len(q) >= 3:            # Wortanfang
            rows = con.execute(sql.format("written_rep>=? COLLATE NOCASE AND written_rep<? COLLATE NOCASE"),
                               (q, q + "￿")).fetchall()[:30]
        groups, order, seen = {}, [], set()
        for lex, rep_, sense, trans, _score in rows:
            words = [w.strip() for w in (trans or "").split(" | ") if w.strip() and "#" not in w]
            key = (rep_, tuple(words))
            if not words or key in seen:
                continue
            seen.add(key)
            parts = (lex or "").split("/", 1)[-1].split("__")
            wt = WD_TYPES.get(parts[1].lower(), parts[1]) if len(parts) > 2 else "Sonstiges"
            ctx = (sense or "").replace("\n", " ").strip()
            if len(ctx) > 140:
                ctx = ctx[:139] + "…"
            if not exact and rep_.lower() != q.lower():
                ctx = f"{rep_}: {ctx}" if ctx else rep_
            if wt not in groups:
                groups[wt] = []
                order.append(wt)
            if len(groups[wt]) < 8:
                groups[wt].append({"words": [(w, None, "") for w in words], "context": ctx, "rank": 0})
        return {"dir": src, "groups": [(g, groups[g]) for g in order], "phrases": [],
                "score": exact * 10 + len(rows), "exact": exact}


class Dictionary:
    def __init__(self):
        self.con = None

    def open(self):
        if self.con is None and available():
            try:
                self.con = sqlite3.connect(DB, check_same_thread=False)
                self.has_fts = bool(self.con.execute(
                    "SELECT 1 FROM sqlite_master WHERE name='f'").fetchone())
            except sqlite3.Error:
                self.con = None
        return self.con

    def entry(self, eid):
        return self.con.execute("SELECT de, en FROM e WHERE id=?", (eid,)).fetchone()

    def guess(self, q):
        """Sprache der Eingabe raten: Wie viele Wörter kennt das deutsche bzw. englische Wörterbuch?"""
        words = re.findall(r"[\wäöüß'-]+", q.lower())
        if re.search(r"[äöüß]", q.lower()):
            return "de"
        score = [0, 0]
        for w in words[:12]:
            for side in (0, 1):
                if self.con.execute("SELECT 1 FROM k WHERE w=? AND side=? LIMIT 1", (w, side)).fetchone():
                    score[side] += 1
        return "en" if score[1] > score[0] else "de"

    def lookup(self, q, direction="auto"):
        """→ [{"dir": "de"/"en", "groups": [(wortart, [bedeutung, …])], "phrases": [(quelle, ziel), …]}]
        bedeutung = {"words": [(wort, artikel, hinweis)], "context": str}"""
        if not self.open():
            return []
        qk = clean(q)
        if not qk:
            return []
        out = []
        for side in {"auto": (0, 1), "de": (0,), "en": (1,)}[direction]:
            res = self._side(qk, side)
            if res["groups"] or res["phrases"]:
                out.append(res)
        if direction == "auto" and any(r["exact"] for r in out):      # nur Wortanfang-Treffer: Rauschen
            out = [r for r in out if r["exact"]]
        # „auto“: die Richtung mit dem besseren Treffer zuerst
        out.sort(key=lambda r: -r["score"])
        return out

    def _side(self, qk, side):
        rows = self.con.execute("SELECT id, sub, syn FROM k WHERE w=? AND side=? LIMIT 300", (qk, side)).fetchall()
        exact = len(rows)
        if not rows and len(qk) >= 3:           # nichts Genaues: Wortanfang („hau“ → Haus, hauen …)
            rows += self.con.execute("SELECT id, sub, syn FROM k WHERE w>? AND w<? AND side=? AND sub=0 LIMIT 40",
                                     (qk, qk + "￿", side)).fetchall()
        seen, items = set(), []
        for eid, sub, syn in rows:
            if (eid, sub) in seen:
                continue
            seen.add((eid, sub))
            de, en = self.entry(eid)
            src_all, tgt_all = (de, en) if side == 0 else (en, de)
            srcs, tgts = src_all.split(" | "), tgt_all.split(" | ")
            if sub >= len(tgts):
                continue
            hit = qk in keys_for(split_syn(srcs[sub])[syn] if syn < len(split_syn(srcs[sub])) else "", side == 1)
            # genauer Treffer zuerst, dann Hauptwort vor Wendung, dann eindeutige (wenige Synonyme) vor allgemeinen
            items.append(((0 if hit else 2) + (1 if sub else 0), syn, len(split_syn(srcs[sub])), -len(srcs), eid,
                          sub, srcs, tgts, de.split(" | "), en.split(" | ")))
        items.sort(key=lambda t: t[:5])
        groups, order = {}, []
        for rank, syn, _ns, _n, eid, sub, srcs, tgts, des, ens in items[:40]:
            wt = word_type(des[sub] if sub < len(des) else des[0], ens[sub] if sub < len(ens) else ens[0])
            words = []
            for w in split_syn(tgts[sub]):
                hint = " ".join(re.findall(r"\[[^\]]*\]|\([^)]*\)", w))
                t = tags(w)
                art = ARTICLE.get(t[0]) if (side == 1 and t) else None
                plain = re.sub(r"\s+", " ", NOTE.sub(" ", w)).strip()
                if plain:
                    words.append((plain, art, hint))
            if not words:
                continue
            m = {"words": words, "context": srcs[sub].strip(), "rank": rank}
            if wt not in groups:
                groups[wt] = []
                order.append(wt)
            groups[wt].append(m)
        phrases = self._phrases(qk, side)
        best = min((m["rank"] for g in groups.values() for m in g), default=9)
        return {"dir": "de" if side == 0 else "en", "groups": [(g, groups[g][:8]) for g in order],
                "phrases": phrases, "score": (10 - best) * 10 + min(len(items), 9), "exact": exact}

    def _phrases(self, qk, side):
        """Wendungen und Beispiele, in denen das Wort vorkommt (kurze zuerst)."""
        words = re.findall(r"[\wäöüß'-]+", qk)
        if not words or not getattr(self, "has_fts", False):
            return []
        col = "de" if side == 0 else "en"
        match = " AND ".join(f'{col}:"{w}"' for w in words if w.replace("'", "").replace("-", "").isalnum())
        if not match:
            return []
        try:
            ids = [r[0] for r in self.con.execute("SELECT rowid FROM f WHERE f MATCH ? LIMIT 400", (match,))]
        except sqlite3.Error:
            return []
        pat = re.compile(r"(?<![\wäöüß])" + re.escape(qk) + r"(?![\wäöüß])", re.I)
        out, seen = [], set()
        for eid in ids:
            de, en = self.entry(eid)
            srcs, tgts = (de, en) if side == 0 else (en, de)
            srcs, tgts = srcs.split(" | "), tgts.split(" | ")
            for i, s in enumerate(srcs):
                if i >= len(tgts) or not pat.search(s):
                    continue
                c = clean(s)
                if c == qk or c in seen or len(c.split()) < 2:
                    continue
                seen.add(c)
                out.append((s.strip(), tgts[i].strip()))
        out.sort(key=lambda p: (len(p[0]), p[0].lower()))
        return out[:30]


def online(q, src, done, lang="en"):
    """Satz übersetzen über MyMemory (kostenlos, ohne Konto). done(text oder None, fehler) im Hauptthread.
    lang = die Fremdsprache des Paars (de ⇄ lang)."""
    tgt = lang if src == "de" else "de"

    def work():
        try:
            url = ONLINE.format(urllib.parse.urlencode({"q": q[:500], "langpair": f"{src}|{tgt}"}))
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "notist"}),
                                        timeout=12) as r:
                data = json.loads(r.read().decode("utf-8"))
            text = (data.get("responseData") or {}).get("translatedText")
            alts = []
            for m in data.get("matches") or []:
                t = (m.get("translation") or "").strip()
                if t and t != text and t not in alts and len(alts) < 3:
                    alts.append(t)
            _ui(lambda: done([text] + alts if text else None, None))
        except Exception as e:  # noqa: BLE001
            msg = str(e)
            _ui(lambda: done(None, msg))
    threading.Thread(target=work, daemon=True).start()
