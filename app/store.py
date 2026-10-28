# Speicher für notist: eine JSON-Datei pro Notiz in ~/.local/share/notes/data/notes/.
# Die Felder entsprechen denen von Google Keep, damit ein späterer Abgleich (siehe sync.py)
# nur noch übersetzen muss. Gelöschtes bleibt als "trashed" liegen, damit der Abgleich es mitbekommt.
import datetime, glob, json, os, re, shutil, uuid

import paths

DATA = paths.NOTES
HISTORY = paths.HISTORY   # history/<id>/<zeit>.json
PURGE_DAYS = 30  # so lange bleiben gelöschte Notizen im Papierkorb
HISTORY_MINUTES = 5   # höchstens alle 5 Minuten eine Version
HISTORY_MAX = 60      # so viele Versionen je Notiz


_BIG = 50_000          # Zeichenketten ab dieser Länge (Bilder als base64) werden nur einmal kodiert
_enc_cache = {}        # (Länge, Hash) → fertig kodierte JSON-Zeichenkette
_PLACE = re.compile(r'"\\u0000IMG(\d+)\\u0000"')


def _lift(o, big):
    """Kopie von o, in der große Zeichenketten durch Platzhalter ersetzt sind (Original bleibt unberührt)."""
    if isinstance(o, str):
        if len(o) < _BIG:
            return o
        key = (len(o), hash(o))
        if key not in _enc_cache:
            _enc_cache[key] = json.dumps(o, ensure_ascii=False)
        big.append(key)
        return f"\0IMG{len(big) - 1}\0"
    if isinstance(o, dict):
        return {k: _lift(v, big) for k, v in o.items()}
    if isinstance(o, list):
        return [_lift(v, big) for v in o]
    return o


def dumps(note):
    """Wie json.dumps(note, ensure_ascii=False), aber schnell: der C-Encoder sieht keine Bilder, bereits kodierte
    Bilddaten kommen aus dem Zwischenspeicher (ein 16-MB-Dokument brauchte sonst bei jedem Speichern ~140 ms)."""
    big = []
    out = json.dumps(_lift(note, big), ensure_ascii=False)
    if big:
        out = _PLACE.sub(lambda m: _enc_cache[big[int(m.group(1))]], out)
        for k in list(_enc_cache)[:-24]:          # nur die zuletzt benutzten Bilder merken (Arbeitsspeicher)
            if k not in big:
                del _enc_cache[k]
    return out


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def new_note(title="", text=""):
    t = now()
    return {
        "id": str(uuid.uuid4()),
        "type": "text",          # Keep kennt auch "list" (Checklisten), für später
        "title": title,
        "text": text,
        "pinned": False,
        "archived": False,
        "trashed": False,
        "color": "default",      # Keep-Farbnamen: default, red, orange, yellow, green, teal, blue, ...
        "labels": [],
        "rich": [],              # Formatierung: [[start, ende, "bold"|"italic"|"underline"|"font:Familie"], ...]
                                 # "text" bleibt reiner Text, damit Suche und Keep-Abgleich einfach bleiben
        "created": t,
        "updated": t,
        "trashed_at": None,
        "sync": {"keep_id": None, "keep_updated": None, "dirty": True},
    }


class Store:
    def __init__(self, path=DATA):
        self.path = path
        os.makedirs(path, exist_ok=True)
        self.notes = {}
        self.load()

    def load(self):
        self.notes = {}
        os.makedirs(self.path, exist_ok=True)
        for f in os.listdir(self.path):
            if f.endswith(".json"):
                try:
                    with open(os.path.join(self.path, f)) as fh:
                        n = json.load(fh)
                    self.notes[n["id"]] = {**new_note(), **n}
                except (OSError, ValueError, KeyError):
                    pass
        self.purge()

    def save(self, note, touch=True):
        if touch:
            note["updated"] = now()
            note["sync"]["dirty"] = True
        self.notes[note["id"]] = note
        dest = os.path.join(self.path, note["id"] + ".json")
        tmp = dest + ".tmp"
        with open(tmp, "w") as fh:
            fh.write(dumps(note))
        os.replace(tmp, dest)  # nie halb geschriebene Notizen

    def create(self):
        """Neue Notiz nur im Speicher; auf die Platte kommt sie erst, wenn etwas drinsteht."""
        n = new_note()
        self.notes[n["id"]] = n
        return n

    def trash(self, note):
        note["trashed"], note["trashed_at"] = True, now()
        self.save(note)

    def restore(self, note):
        note["trashed"], note["trashed_at"] = False, None
        if note.get("file_trashed"):            # Datei war mit in den System-Papierkorb gewandert
            import linked
            linked.untrash(note)
        self.save(note)

    def delete_forever(self, note):
        """Endgültig löschen. Schon mit Keep abgeglichene Notizen bleiben als Löschauftrag liegen."""
        if note["sync"]["keep_id"]:
            note["sync"]["delete_remote"] = True
            self.save(note)
            return
        try:
            os.remove(os.path.join(self.path, note["id"] + ".json"))
        except OSError:
            pass
        import linked
        linked.discard(note)            # selbst angelegte Datei in den System-Papierkorb, fremde bleiben
        self.drop_history(note)
        self.notes.pop(note["id"], None)

    @staticmethod
    def matches(n, q, label=None):
        if label and label not in n.get("labels", []):
            return False
        if not q:
            return True
        if q.startswith("#") and len(q) > 1:      # „#uni“ sucht nur in den Schlagwörtern
            return any(l.lower().startswith(q[1:]) for l in n.get("labels", []))
        return q in n["title"].lower() or q in n["text"].lower() or any(q in l.lower() for l in n.get("labels", []))

    def trashed(self, query=""):
        q = query.lower().strip()
        out = [n for n in self.notes.values() if n["trashed"] and not n["sync"].get("delete_remote")
               and self.matches(n, q)]
        return sorted(out, key=lambda n: n["trashed_at"] or "", reverse=True)

    def visible(self, query="", label=None):
        q = query.lower().strip()
        out = [n for n in self.notes.values() if not n["trashed"] and not n["archived"] and self.matches(n, q, label)]
        # Angeheftete zuerst, dann zuletzt geänderte
        return sorted(out, key=lambda n: (n["pinned"], n["updated"]), reverse=True)

    def archived(self, query="", label=None):
        q = query.lower().strip()
        out = [n for n in self.notes.values() if n["archived"] and not n["trashed"] and self.matches(n, q, label)]
        return sorted(out, key=lambda n: n["updated"], reverse=True)

    def labels(self):
        return sorted({l for n in self.notes.values() if not n["trashed"] for l in n.get("labels", [])}, key=str.lower)

    # ---------- Versionsverlauf ----------
    def history_dir(self, note):
        return os.path.join(HISTORY, note["id"])

    def snapshot(self, note, force=False):
        """Version sichern – höchstens alle HISTORY_MINUTES und nur, wenn sich etwas geändert hat."""
        d = self.history_dir(note)
        files = sorted(glob.glob(os.path.join(d, "*.json")))
        if files and not force:
            try:
                last = datetime.datetime.fromisoformat(os.path.basename(files[-1])[:-5].replace("_", ":"))
                age = datetime.datetime.now(datetime.timezone.utc) - last
                if age.total_seconds() < HISTORY_MINUTES * 60:
                    return None
                with open(files[-1]) as fh:
                    old = json.load(fh)
                if old.get("text") == note.get("text") and old.get("title") == note.get("title") and \
                        old.get("blocks") == note.get("blocks"):
                    return None
            except (OSError, ValueError):
                pass
        os.makedirs(d, exist_ok=True)
        stamp = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="milliseconds")
        dest = os.path.join(d, stamp.replace(":", "_") + ".json")
        if os.path.exists(dest):
            return None
        data = dumps(note)
        with open(dest, "w") as fh:
            fh.write(data)
        keep = HISTORY_MAX if len(data) < 2_000_000 else max(8, HISTORY_MAX * 2_000_000 // len(data))   # Bilder-Riesen: weniger Versionen
        for old in files[:max(0, len(files) + 1 - keep)]:
            try:
                os.remove(old)
            except OSError:
                pass
        return dest

    def versions(self, note):
        """[(zeit, pfad)] neueste zuerst."""
        out = []
        for f in sorted(glob.glob(os.path.join(self.history_dir(note), "*.json")), reverse=True):
            try:
                out.append((datetime.datetime.fromisoformat(os.path.basename(f)[:-5].replace("_", ":")), f))
            except ValueError:
                pass
        return out

    @staticmethod
    def load_version(path):
        with open(path) as fh:
            return json.load(fh)

    def drop_history(self, note):
        shutil.rmtree(self.history_dir(note), ignore_errors=True)

    def purge(self):
        """Löscht Papierkorb-Notizen endgültig, aber nur wenn sie schon abgeglichen sind (oder nie synchronisiert)."""
        limit = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=PURGE_DAYS)
        for n in list(self.notes.values()):
            if n["trashed"] and n["trashed_at"] and datetime.datetime.fromisoformat(n["trashed_at"]) < limit \
                    and (not n["sync"]["dirty"] or not n["sync"]["keep_id"]):
                try:
                    os.remove(os.path.join(self.path, n["id"] + ".json"))
                except OSError:
                    pass
                import linked
                linked.discard(n)
                del self.notes[n["id"]]
