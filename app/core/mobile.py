# notist – Speicher + Abgleich für das Handy (Plan Schritt 20). GTK-frei, läuft im Handy per Chaquopy (und am PC im Test).
#
# Gleiche Daten wie am PC: je Eintrag eine JSON-Datei in data/notes|docs|latex (core/store.py), Anhänge in data/pdfs,
# data/sheets, data/latex-files, Verlauf in data/history. Dazu ein SQLite-Index (data/index.sqlite: Titel, Vorschau,
# Ordner, Schlagwörter, Volltext per FTS5) – nur zum schnellen Auflisten/Suchen, jederzeit aus den Dateien neu baubar.
# Abgleich = core/sync2 + core/peerlink (Client, mehrere Gegenstellen), derselbe Code wie am PC; hier nur ein schlankes
# „App“-Gerüst (_App/_Srv) anstelle des GTK-Fensters. Der Abgleich läuft in einem eigenen Python-Faden und hält die
# Sperre LOCK nur, während er Einträge anfasst; Netzwerk und Anhänge laufen ohne Sperre.
import json, os, re, shutil, sqlite3, threading, time

from core import handylink as hl
from core import paths, peerlink, store, sync2

KINDS = hl.KINDS2
LOCK = threading.RLock()
INDEX_V = 1
_M = None


def _json_file(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


class _App:
    """Das Wenige, was AppBackend/Peers von der App brauchen."""

    def __init__(self):
        self.stores = {"notes": store.Store(paths.NOTES), "docs": store.Store(paths.DOCS),
                       "latex": store.Store(paths.LATEX)}
        self.prefs = _json_file(paths.PREFS, {})
        if not isinstance(self.prefs, dict):
            self.prefs = {}
        self.current = None
        self.message = None

    def save_prefs(self):
        os.makedirs(os.path.dirname(paths.PREFS), exist_ok=True)
        tmp = paths.PREFS + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.prefs, f, indent=1)
        os.replace(tmp, paths.PREFS)

    def folder_prefs(self, kind):
        by = self.prefs.setdefault("folders_by", {})
        return by.setdefault(kind, []), self.prefs.setdefault("folders_closed_by", {}).setdefault(kind, [])

    def notify(self, msg):
        self.message = msg

    def flush(self): pass
    def run_sync_file(self, wait=False): pass
    def reload_if_changed(self, n, kind): return False
    def join_bg(self): pass


class _Backend(hl.AppBackend):
    """AppBackend ohne Fenster: nach jeder Runde den Index nachziehen."""

    def __init__(self, mob):
        super().__init__(mob.app)
        self.mob = mob

    def begin(self):
        self.touched, self.deleted = [], 0

    def finish(self, stats, what="abgleich"):
        if self.touched or self.deleted:
            self.app.save_prefs()
            self.mob.reindex()
        self.touched, self.deleted = [], 0


class _Srv:
    """Gerüst für peerlink.Peers (sonst ist das handylink.Server mit Fenster)."""

    def __init__(self, mob):
        self.mob, self.app = mob, mob.app
        self._rep = None

    @property
    def rep(self):
        if self._rep is None:
            self._rep = sync2.Replica(_Backend(self.mob), path=os.path.join(paths.DATA, "sync2.json"))
        return self._rep

    def run_main(self, fn, timeout=None):
        with LOCK:
            return fn()

    def _notify(self):
        pass


class _Peers(peerlink.Peers):
    """mDNS macht am Handy der NsdManager (Kotlin) und reicht die Funde herein (Mobile.found)."""

    def _mdns(self, wait):
        own = self.own_ips()
        return [(h, p) for h, p in self.srv.mob.found if h not in own]


class Mobile:
    def __init__(self):
        os.makedirs(paths.DATA, exist_ok=True)
        self.app = _App()
        self.found = []                         # [(host, port)] vom NsdManager
        self.srv = _Srv(self)
        self.peers = _Peers(self.srv)
        self.status = {"running": False, "peer": None, "err": None, "got": 0, "sent": 0, "conflicts": 0,
                       "deleted": 0, "last": None, "msg": None}
        self.db = None
        self.cjob = {}
        self.cpending = set()
        self._open_index()
        self.reindex()

    # ---------- Index ----------
    def _open_index(self):
        p = os.path.join(paths.DATA, "index.sqlite")
        fresh = not os.path.exists(p)
        db = sqlite3.connect(p, check_same_thread=False)
        if not fresh and db.execute("PRAGMA user_version").fetchone()[0] != INDEX_V:
            db.close()
            os.remove(p)
            db = sqlite3.connect(p, check_same_thread=False)
        db.executescript("""
            CREATE TABLE IF NOT EXISTS e(key TEXT PRIMARY KEY, kind TEXT, id TEXT, title TEXT, preview TEXT,
              updated TEXT, created TEXT, pinned INT, archived INT, trashed INT, trashed_at TEXT, labels TEXT,
              folder TEXT, color TEXT, media INT, sig TEXT);
            CREATE INDEX IF NOT EXISTS e_kind ON e(kind, trashed, archived);""")
        try:
            db.execute("CREATE VIRTUAL TABLE IF NOT EXISTS f USING fts5(key UNINDEXED, title, body, labels)")
            self.fts = True
        except sqlite3.Error:
            self.fts = False
        db.execute(f"PRAGMA user_version={INDEX_V}")
        self.db = db

    @staticmethod
    def _summary(kind, n):
        text = re.sub(r"[￼\s]+", " ", str(n.get("text") or "")).strip()
        if not text and kind == "docs":
            parts = []
            for b in n.get("blocks") or []:
                if isinstance(b, dict):
                    for r in b.get("runs") or []:
                        if isinstance(r, dict) and r.get("text"):
                            parts.append(str(r["text"]))
                    if sum(map(len, parts)) > 400:
                        break
            text = re.sub(r"\s+", " ", " ".join(parts)).strip()
        blocks = n.get("blocks") or []
        media = any(isinstance(b, dict) and b.get("t") in ("img", "image", "pdf", "sheet") for b in blocks)
        return {"kind": kind, "id": n["id"], "title": n.get("title") or "", "preview": text[:240],
                "updated": n.get("updated") or "", "created": n.get("created") or "",
                "pinned": bool(n.get("pinned")), "archived": bool(n.get("archived")), "trashed": bool(n.get("trashed")),
                "trashed_at": n.get("trashed_at"), "labels": list(n.get("labels") or []),
                "folder": n.get("folder") or None, "color": n.get("color") or "default", "media": media, "body": text}

    def _put_index(self, kind, n):
        s = self._summary(kind, n)
        key = f"{kind}:{n['id']}"
        sig = "|".join(map(str, (s["updated"], s["pinned"], s["archived"], s["trashed"], s["folder"], len(s["body"]),
                                 s["title"], ",".join(s["labels"]), s["color"])))
        row = self.db.execute("SELECT sig FROM e WHERE key=?", (key,)).fetchone()
        if row and row[0] == sig:
            return False
        self.db.execute("INSERT OR REPLACE INTO e VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (key, kind, n["id"], s["title"], s["preview"], s["updated"], s["created"], s["pinned"],
                         s["archived"], s["trashed"], s["trashed_at"], json.dumps(s["labels"], ensure_ascii=False),
                         s["folder"], s["color"], s["media"], sig))
        if self.fts:
            self.db.execute("DELETE FROM f WHERE key=?", (key,))
            self.db.execute("INSERT INTO f(key,title,body,labels) VALUES(?,?,?,?)",
                            (key, s["title"], self._fulltext(n, s["body"]), " ".join(s["labels"])))
        return True

    @staticmethod
    def _fulltext(n, body):
        if n.get("text"):
            return str(n["text"])
        parts = []
        for b in n.get("blocks") or []:
            if isinstance(b, dict):
                parts += [str(r.get("text") or "") for r in b.get("runs") or [] if isinstance(r, dict)]
        return " ".join(parts) or body

    def reindex(self):
        """Index an die Dateien angleichen (billig: nur geänderte Einträge werden neu geschrieben)."""
        with LOCK:
            live = set()
            for kind in KINDS:
                st = self.app.stores[kind]
                for nid, n in list(st.notes.items()):
                    if os.path.exists(os.path.join(st.path, nid + ".json")):
                        live.add(f"{kind}:{nid}")
                        self._put_index(kind, n)
            gone = [r[0] for r in self.db.execute("SELECT key FROM e") if r[0] not in live]
            for k in gone:
                self.db.execute("DELETE FROM e WHERE key=?", (k,))
                if self.fts:
                    self.db.execute("DELETE FROM f WHERE key=?", (k,))
            self.db.commit()

    def _one(self, kind, n):
        self._put_index(kind, n)
        self.db.commit()

    # ---------- Einträge ----------
    def _store(self, kind):
        if kind not in KINDS:
            raise ValueError(f"unbekannter Bereich {kind!r}")
        return self.app.stores[kind]

    def _find(self, kind, nid):
        n = self._store(kind).notes.get(nid)
        if n is None:
            raise ValueError("Eintrag nicht gefunden")
        return n

    def list(self, kind, view="aktiv", q="", label=None, folder=None, limit=2000):
        with LOCK:
            self._store(kind)
            where, args = ["kind=?"], [kind]
            where.append({"archiv": "archived=1 AND trashed=0", "papierkorb": "trashed=1"}.get(
                view, "archived=0 AND trashed=0"))
            if folder is not None:
                if folder == "":
                    where.append("folder IS NULL")
                else:
                    where.append("(folder=? OR folder LIKE ?)")
                    args += [folder, folder.replace("%", "") + "/%"]
            q = (q or "").strip()
            keys = None
            if q.startswith("#") and len(q) > 1:
                where.append("EXISTS(SELECT 1 FROM json_each(e.labels) j WHERE lower(j.value) LIKE ?)")
                args.append(q[1:].lower() + "%")
            elif q:
                if self.fts:
                    try:
                        toks = re.findall(r"\w+", q)
                        m = " ".join(f'"{t}"*' for t in toks)
                        keys = {r[0] for r in self.db.execute("SELECT key FROM f WHERE f MATCH ?", (m,))} if m else None
                    except sqlite3.Error:
                        keys = None
                if keys is None:
                    like = f"%{q.lower()}%"
                    where.append("(lower(title) LIKE ? OR lower(preview) LIKE ? OR lower(labels) LIKE ?)")
                    args += [like, like, like]
            if label:
                where.append("EXISTS(SELECT 1 FROM json_each(e.labels) j WHERE j.value=?)")
                args.append(label)
            order = {"archiv": "updated DESC", "papierkorb": "trashed_at DESC"}.get(view, "pinned DESC, updated DESC")
            rows = self.db.execute(f"SELECT key,id,title,preview,updated,created,pinned,archived,trashed,trashed_at,"
                                   f"labels,folder,color,media FROM e WHERE {' AND '.join(where)} ORDER BY {order}",
                                   args).fetchall()
            out = []
            for r in rows:
                if keys is not None and r[0] not in keys:
                    continue
                out.append({"kind": kind, "id": r[1], "title": r[2], "preview": r[3], "updated": r[4], "created": r[5],
                            "pinned": bool(r[6]), "archived": bool(r[7]), "trashed": bool(r[8]), "trashed_at": r[9],
                            "labels": json.loads(r[10] or "[]"), "folder": r[11], "color": r[12], "media": bool(r[13])})
                if len(out) >= limit:
                    break
            return out

    def get(self, kind, nid):
        with LOCK:
            n = self._store(kind).notes.get(nid)
            return hl.content(n) if n is not None and os.path.exists(os.path.join(self.app.stores[kind].path, nid + ".json")) else None

    def exists(self, kind, nid):
        with LOCK:
            return os.path.exists(os.path.join(self._store(kind).path, nid + ".json"))

    def new(self, kind, folder=None):
        """Neuer Eintrag nur im Speicher (steht erst nach save() auf der Platte)."""
        with LOCK:
            n = self._store(kind).create()
            if folder:
                n["folder"] = folder
            return hl.content(n)

    def save(self, kind, entry):
        """Eintrag speichern (zählt als Änderung → Abgleich). Fremde Felder bleiben erhalten."""
        with LOCK:
            st = self._store(kind)
            nid = str(entry.get("id") or "")
            if not nid:
                raise ValueError("Eintrag ohne Id")
            cur = st.notes.get(nid)
            if cur is not None and os.path.exists(os.path.join(st.path, nid + ".json")):
                try:
                    st.snapshot(cur)
                except OSError:
                    pass
            n = {**store.new_note(), **(cur or {}), **{k: v for k, v in entry.items() if k not in hl.LOCAL}}
            n["id"] = nid
            st.save(n)
            self._one(kind, n)
            return hl.content(n)

    def patch(self, kind, nid, fields):
        """Einzelne Felder ändern (angeheftet, Archiv, Ordner, Schlagwörter, Farbe …)."""
        with LOCK:
            n = self._find(kind, nid)
            for k, v in (fields or {}).items():
                if k in hl.LOCAL or k in ("id", "created"):
                    continue
                n[k] = v
            self._store(kind).save(n)
            self._one(kind, n)
            return hl.content(n)

    def trash(self, kind, nid):
        with LOCK:
            n = self._find(kind, nid)
            self._store(kind).trash(n)
            self._one(kind, n)

    def restore(self, kind, nid):
        with LOCK:
            n = self._find(kind, nid)
            self._store(kind).restore(n)
            self._one(kind, n)

    def delete_forever(self, kind, nid):
        with LOCK:
            st = self._store(kind)
            n = st.notes.get(nid)
            if n is None:
                return
            st.delete_forever(n)
            key = f"{kind}:{nid}"
            self.db.execute("DELETE FROM e WHERE key=?", (key,))
            if self.fts:
                self.db.execute("DELETE FROM f WHERE key=?", (key,))
            self.db.commit()

    def labels(self):
        with LOCK:
            seen = {}
            for (js,) in self.db.execute("SELECT labels FROM e WHERE trashed=0"):
                for l in json.loads(js or "[]"):
                    seen.setdefault(l.lower(), l)
            return sorted(seen.values(), key=str.lower)

    def folders(self, kind):
        with LOCK:
            names = set(self.app.folder_prefs(kind)[0])
            names |= {r[0] for r in self.db.execute("SELECT DISTINCT folder FROM e WHERE kind=? AND trashed=0 AND folder IS NOT NULL", (kind,))}
            for n in list(names):
                p = n
                while "/" in p:
                    p = p.rsplit("/", 1)[0]
                    names.add(p)
            return sorted((n for n in names if n.strip()), key=str.lower)

    def add_folder(self, kind, name):
        with LOCK:
            made = self.app.folder_prefs(kind)[0]
            if name.strip() and name not in made:
                made.append(name)
                self.app.save_prefs()

    def rename_folder(self, kind, old, new):
        """Ordner umbenennen/verschieben (samt Unterordnern und Einträgen; new leer = Ordner auflösen). → Zahl Einträge."""
        old, new = old.strip().strip("/"), (new or "").strip().strip("/")
        if not old or new == old or new.startswith(old + "/"):
            raise ValueError("Ordner lässt sich nicht dorthin verschieben")

        def conv(f):
            if f == old or (f or "").startswith(old + "/"):
                rest = f[len(old):]
                return (new + rest) if new else (rest.lstrip("/") or None)
            return f
        with LOCK:
            st = self._store(kind)
            n_changed = 0
            for n in list(st.notes.values()):
                f = n.get("folder")
                if f and conv(f) != f:
                    n["folder"] = conv(f)
                    st.save(n)
                    self._put_index(kind, n)
                    n_changed += 1
            made = self.app.folder_prefs(kind)[0]
            made[:] = [c for c in dict.fromkeys(conv(f) for f in made) if c]
            if new and new not in made:
                made.append(new)
            self.app.save_prefs()
            self.db.commit()
            return n_changed

    def delete_folder(self, kind, name):
        """Leeren Ordner entfernen (Einträge darin → Ordner aufgelöst, nichts wird gelöscht)."""
        return self.rename_folder(kind, name, "")

    def versions(self, kind, nid):
        with LOCK:
            n = self._find(kind, nid)
            return [{"name": os.path.basename(p), "time": t.isoformat()} for t, p in self._store(kind).versions(n)]

    def version(self, kind, nid, name):
        with LOCK:
            n = self._find(kind, nid)
            p = os.path.join(self._store(kind).history_dir(n), os.path.basename(name))
            return hl.content(store.Store.load_version(p))

    def reload(self):
        """Nach dem Einspielen einer Sicherung: Einträge neu lesen, Index neu bauen (Gegenstellen/Einstellungen bleiben)."""
        with LOCK:
            fresh = _App()
            self.app.stores = fresh.stores
            self.app.prefs = fresh.prefs
            self.srv._rep = None
            self.db.execute("DELETE FROM e")
            if self.fts:
                self.db.execute("DELETE FROM f")
            self.db.commit()
        self.reindex()

    # ---------- Erinnerungen ----------
    def reminders(self):
        """Alle Erinnerungen (nicht gelöscht): [{kind, id, title, at, at_ms, done}] nach Zeit sortiert. at_ms = Ortszeit als Millisekunden seit 1970."""
        import datetime
        from core import reminders as rm
        out = []
        with LOCK:
            for kind in KINDS:
                for n in self.app.stores[kind].notes.values():
                    if n.get("reminder") and not n.get("trashed"):
                        dt = rm.parse(n["reminder"])
                        if dt is None:
                            continue
                        out.append({"kind": kind, "id": n["id"], "title": rm.reminder_title(n), "at": n["reminder"],
                                    "at_ms": int(dt.timestamp() * 1000), "done": bool(n.get("reminder_done"))})
        return sorted(out, key=lambda r: r["at_ms"])

    def reminder_done(self, kind, nid):
        with LOCK:
            n = self._find(kind, nid)
            n["reminder_done"] = True
            self._store(kind).save(n)
            self._one(kind, n)

    # ---------- Verlauf: Vergleich ----------
    @staticmethod
    def _plain(c):
        if c.get("blocks") is not None:
            return [("".join(r.get("text", "") for r in b.get("runs", [])) if b.get("t") == "p" else f"[{b.get('t')}]") for b in c["blocks"]]
        return (c.get("text") or "").split("\n")

    def diff(self, kind, nid, name):
        """Version `name` → aktuell: [["+"|"-"|" ", Zeile]] (difflib, Zeile für Zeile)."""
        import difflib
        old = self._plain(self.version(kind, nid, name))
        cur = self._plain(self.get(kind, nid) or {})
        out = []
        for line in difflib.ndiff(old, cur):
            tag = line[:1]
            if tag in "+- ":
                out.append([tag, line[2:]])
        return out

    # ---------- Abgleich ----------
    def peer_list(self):
        with LOCK:
            out = []
            for pid, p in self.peers.peers.items():
                out.append({"id": pid, "name": p.get("name"), "host": p.get("host"), "port": p.get("port"),
                            "fixed": bool(p.get("fixed")), "last": p.get("last"), "err": p.get("err"),
                            "busy": pid in self.peers.busy})
            return out

    def pair(self, addr, code, name=None):
        p = self.peers.pair(addr, code, name or "handy")
        return {"id": p["id"], "name": p.get("name")}

    def unpair(self, pid):
        self.peers.remove(pid)

    def discover(self):
        return self.peers.discover(wait=0, scan=True)

    def set_found(self, hosts):
        self.found = [(str(h), int(p)) for h, p in hosts]

    def interval(self):
        v = self.app.prefs.get("peer_min", peerlink.DEFAULT_MIN)
        return v if isinstance(v, int) and v >= 0 else peerlink.DEFAULT_MIN

    def set_interval(self, minutes):
        with LOCK:
            self.app.prefs["peer_min"] = int(minutes)
            self.app.save_prefs()

    def sync_start(self, pid=None):
        """Abgleich im Hintergrund starten (pid leer = alle Gegenstellen). → False, wenn schon einer läuft."""
        with LOCK:
            if self.status["running"]:
                return False
            ids = [pid] if pid else list(self.peers.peers)
            if not ids:
                raise RuntimeError("noch kein Gerät gekoppelt")
            self.status.update(running=True, peer=ids[0], err=None, got=0, sent=0, conflicts=0, deleted=0, msg=None)
        threading.Thread(target=self._sync_all, args=(ids,), daemon=True, name="notist-sync").start()
        return True

    def _sync_all(self, ids):
        errs, tot = [], {"got": 0, "sent": 0, "conflicts": 0, "deleted": 0}
        for pid in ids:
            p = self.peers.peers.get(pid)
            if p is None:
                continue
            self.status["peer"] = p.get("name") or pid
            try:
                st = self.peers.sync(pid, manual=True)
                for k in tot:
                    tot[k] += int(st.get(k, 0) or 0)
                self.status.update(tot)
            except Exception as e:  # noqa: BLE001
                errs.append(f"{p.get('name') or 'Gerät'}: {self.peers._why(e)}")
        self.reindex()
        self.status.update(running=False, err="; ".join(errs) or None, last=time.time(), peer=None,
                           msg=self.app.message)

    def sync_status(self):
        s = dict(self.status)
        if s["running"]:                                   # Zwischenstand der laufenden Runde
            live = self.srv.rep.stats
            s["got"] = max(s["got"], int(live.get("got", 0)))
            s["conflicts"] = max(s["conflicts"], int(live.get("conflicts", 0)))
        s["peers"] = self.peer_list()
        return s

    # ---------- LaTeX: Kompilieren am gekoppelten Rechner (Schritt 29) ----------
    def _rpc(self, pid, op, **kw):
        """Eine einzelne Anfrage (neue Sitzung) an eine Gegenstelle. Wirft OSError, wenn sie nicht erreichbar ist."""
        peer = self.peers.peers.get(pid)
        if peer is None:
            raise RuntimeError("noch kein Gerät gekoppelt")
        call = hl.client_call(peer)
        r = call({"op": "open"})
        return call({"op": op, "sess": r["sess"], "ctr": 1, **kw})

    def compile_start(self, nid, text, pid=None):
        """Dokument am Rechner bauen lassen (Hintergrund). Stand: compile_status()."""
        with LOCK:
            if self.cjob.get("running"):
                return False
            ids = [pid] if pid else list(self.peers.peers)
            if not ids:
                raise RuntimeError("noch kein Gerät gekoppelt")
            self.cjob = {"running": True, "nid": nid, "ok": None, "problems": [], "log": "", "pdf": None, "synctex": False, "err": None, "pid": ids[0]}
        threading.Thread(target=self._compile, args=(ids[0], nid, text), daemon=True, name="notist-compile").start()
        return True

    def _compile(self, pid, nid, text):
        job = self.cjob
        try:
            r = self._rpc(pid, "compile", key=f"latex:{nid}", text=text)
            pdf = None
            if r.get("pdf"):
                import base64
                os.makedirs(os.path.join(paths.DATA, "pdfs"), exist_ok=True)
                pdf = f"tex-{nid}.pdf"
                with open(os.path.join(paths.DATA, "pdfs", pdf), "wb") as f:
                    f.write(base64.b64decode(r["pdf"]))
            job.update(ok=bool(r.get("ok")), problems=r.get("problems") or [], log=r.get("log") or "", pdf=pdf, synctex=bool(r.get("synctex")))
            self.cpending.discard(nid)
        except sync2.Refused as e:
            job["err"] = str(e)
        except Exception as e:  # noqa: BLE001
            job["err"] = self.peers._why(e) if isinstance(e, OSError) else str(e)
            if isinstance(e, OSError):
                self.cpending.add(nid)
                job["err"] += " – Auftrag gemerkt, nach Verbindung noch einmal kompilieren"
        finally:
            job["running"] = False

    def sync_pdf(self, nid, line, pid=None):
        pid = pid or self.cjob.get("pid") or next(iter(self.peers.peers), None)
        return self._rpc(pid, "sync_pdf", key=f"latex:{nid}", file="main.tex", line=int(line))

    def sync_src(self, nid, page, x, y, pid=None):
        pid = pid or self.cjob.get("pid") or next(iter(self.peers.peers), None)
        return self._rpc(pid, "sync_src", key=f"latex:{nid}", page=int(page), x=float(x), y=float(y))

    def due(self):
        """Ist ein Abgleich fällig (Zeitgeber-Intervall)? Für den WorkManager."""
        if not self.peers.peers or self.interval() == 0:
            return False
        now = time.time()
        return any(now - (p.get("last") or 0) >= self.interval() * 60 for p in self.peers.peers.values())


# ---------- Übernahme der Daten aus Version 0.1.0 ----------
def migrate_legacy(old_dir):
    """Alte App-Daten (files/data/{notes,docs}/*.json + sync.json) übernehmen. Nichts geht verloren: die alten Dateien
    bleiben in data-0.1.0 liegen. → {"notes": n, "docs": n, "folders": n} oder None (nichts zu tun)."""
    if not old_dir or not os.path.isdir(old_dir):
        return None
    marker = os.path.join(paths.DATA, ".migrated-0.1.0")
    if os.path.exists(marker):
        return None
    out = {"notes": 0, "docs": 0, "folders": 0, "skipped": 0}
    for kind, dest in (("notes", paths.NOTES), ("docs", paths.DOCS)):
        src = os.path.join(old_dir, kind)
        os.makedirs(dest, exist_ok=True)
        for f in sorted(os.listdir(src)) if os.path.isdir(src) else []:
            if not f.endswith(".json"):
                continue
            target = os.path.join(dest, f)
            try:
                with open(os.path.join(src, f), encoding="utf-8") as fh:
                    n = json.load(fh)
                if not isinstance(n, dict) or not n.get("id"):
                    raise ValueError("kein Eintrag")
            except (OSError, ValueError):
                out["skipped"] += 1
                continue
            if not os.path.exists(target):
                shutil.copy2(os.path.join(src, f), target)
                out[kind] += 1
    meta = _json_file(os.path.join(old_dir, "sync.json"), {})
    folders = meta.get("folders") if isinstance(meta, dict) else None
    if isinstance(folders, dict):
        prefs = _json_file(paths.PREFS, {})
        by = prefs.setdefault("folders_by", {})
        for kind, names in folders.items():
            if kind in KINDS and isinstance(names, list):
                cur = by.setdefault(kind, [])
                for nm in names:
                    if isinstance(nm, str) and nm not in cur:
                        cur.append(nm)
                        out["folders"] += 1
        os.makedirs(os.path.dirname(paths.PREFS), exist_ok=True)
        with open(paths.PREFS, "w", encoding="utf-8") as f:
            json.dump(prefs, f, indent=1)
    with open(marker, "w", encoding="utf-8") as f:
        json.dump(out, f)
    try:
        os.replace(old_dir, old_dir.rstrip("/") + "-0.1.0")
    except OSError:
        pass
    return out


WELCOME = {
    "de": ("Willkommen bei notist", ["Drei Bereiche: Notizen, Words und LaTeX – alles speichert sich von selbst.",
        "• Tippe „/“ am Absatzanfang in Words: Überschrift, Liste, Tabelle, Bild, Fußnote …",
        "• Unter „Abgleich mit PC/Mac“ koppelst du das Handy mit notist am Rechner (Code von dort).",
        "• Schreibhilfen (Rechtschreibung, Autokorrektur) und Übersetzer findest du im ⋮-Menü.",
        "• Verlauf, Teilen/Export und Erinnerungen stehen ebenfalls im ⋮-Menü bzw. in den Eigenschaften.",
        "Diesen Eintrag kannst du jederzeit löschen."]),
    "en": ("Welcome to notist", ["Three areas: notes, words and latex – everything saves itself.",
        "• Type “/” at the start of a paragraph in Words: heading, list, table, image, footnote …",
        "• “Sync with PC/Mac” pairs the phone with notist on your computer (code from there).",
        "• Writing aids (spell check, autocorrect) and the translator are in the ⋮ menu.",
        "• History, share/export and reminders are in the ⋮ menu and in the properties.",
        "You can delete this entry at any time."])}


def welcome(lang="de"):
    """Beim allerersten Start (leerer Speicher) eine Willkommensnotiz anlegen. → ID oder None."""
    m = get()
    marker = os.path.join(paths.DATA, ".welcomed")
    if os.path.exists(marker):
        return None
    open(marker, "w").close()
    if any(m.list(k, "aktiv") for k in KINDS):
        return None
    title, lines = WELCOME.get(lang, WELCOME["de"])
    n = m.save("notes", {**m.new("notes"), "title": title, "text": "\n".join(lines)})
    return n["id"]


def get():
    global _M
    if _M is None:
        _M = Mobile()
    return _M
