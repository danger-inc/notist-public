# notist – Abgleich v2 (Plan Schritt 9). Transportfrei und ohne GTK: läuft gleich am PC, am Mac und im Handy (Chaquopy).
#
# Jedes Gerät ist eine Replik mit eigener Kennung `me`. Je Eintrag merkt sie einen Versionsvektor vv = {replik: zähler}
# und eine Prüfsumme des Inhalts (samt Anhang-Liste). Eigene Änderung → eigener Zähler + 1. Zwei Stände a, b:
#   a ≤ b             → b ist neuer, übernehmen (a war Vorfahr – nichts geht verloren)
#   weder a≤b noch b≤a → nebenläufig = Konflikt, erkannt ohne Uhr:
#       gleicher Inhalt          → nur die Vektoren vereinen
#       Grabstein gegen Inhalt   → Inhalt bleibt (Bearbeiten schlägt Löschen)
#       zwei Inhalte             → neuerer `updated` bleibt an Ort und Stelle, der andere wird „(konflikt)“-Kopie;
#                                  deren Id ist uuid5(Schlüssel + Prüfsumme) → beide Seiten erzeugen dieselbe Kopie
#       Einstellungen (prefs:*)  → zusammenführen (Backend.merge)
# Endgültig Gelöschtes bleibt als Grabstein (d = None) mit Vektor.
#
# Protokoll – der Client fragt, der Server antwortet, jede Anfrage ist wiederholbar:
#   open                                   → {sess, me}
#   sync {sess, ctr, me, have, data}       → {me, have, data, more, need}
#   blob {sess, ctr, sha, off}             → {size, b64}          (Anhang holen, in Häppchen)
#   put  {sess, ctr, sha, off, size, b64}  → {off}                (Anhang abgeben, setzt bei `off` fort)
# `have` = {schlüssel: [vv, prüfsumme]} ist die Quittung: Was die Gegenseite hat, steht nur in IHRER Liste. Gesendet
# heißt nie „angekommen“ – geht eine Antwort verloren, schickt die nächste Runde einfach noch einmal.
# Gleiche (sess, ctr) noch einmal → dieselbe Antwort; ältere ctr oder fremde sess → abgelehnt (kein Wiedereinspielen).
#
# Kopplung (pake_*): SPAKE2 in der RFC-3526-Gruppe 14. Der Code geht nie über die Leitung, das Mitschneiden einer
# Kopplung erlaubt kein Durchprobieren; der Server bestätigt erst, nachdem der Client den Code bewiesen hat.
import base64, hashlib, hmac, json, os, secrets, shutil, threading, time, uuid

V = 2
MAX_OUT = 6 * 1024 * 1024        # Daten je Antwort/Anfrage, der Rest in der nächsten Runde
CHUNK = 2 * 1024 * 1024          # Anhang-Häppchen
MAX_BLOB = 200 * 1024 * 1024
TOMB_DAYS = 365                  # Grabsteine, die alle Gegenstellen bestätigt haben, so lange noch aufheben
NS = uuid.UUID("6f1c2a4e-9b7d-4c35-a0e2-5d8f3b7c1e90")


class Refused(Exception):
    """Anfrage abgelehnt (Sitzung abgelaufen, Wiederholung mit anderem Inhalt, veraltet)."""


# ---------- Versionsvektoren ----------
def vv_leq(a, b):
    return all(v <= b.get(k, 0) for k, v in a.items())


def vv_merge(a, b):
    out = dict(a)
    for k, v in b.items():
        if v > out.get(k, 0):
            out[k] = v
    return out


def canon(o):
    return json.dumps(o, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def digest(content, blobs=None):
    c = dict(content)
    if blobs:
        c["\u0000blobs"] = blobs
    return hashlib.sha256(canon(c).encode()).hexdigest()[:24]


def file_sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _norm(stamp):
    return None if stamp is None else json.loads(json.dumps(stamp))


class Backend:
    """Schnittstelle zum Speicher eines Geräts (Vorlage – PC: handylink.AppBackend, Test: sync_sim.MemBackend).
    Schlüssel = "art:id"; Inhalt = dict ohne gerätelokale Felder."""

    def keys(self):                 # alle gespeicherten Schlüssel
        raise NotImplementedError

    def stamp(self, key):           # billiges Änderungsmerkmal (z. B. mtime+Größe) oder None = immer Prüfsumme rechnen
        return None

    def get(self, key):             # Inhalt oder None
        raise NotImplementedError

    def put(self, key, content):    # anlegen oder ersetzen (vorherigen Stand in den Verlauf)
        raise NotImplementedError

    def delete(self, key):
        raise NotImplementedError

    def refs(self, key, content):   # Anhänge: {name: lokaler pfad} (nur vorhandene zählen)
        return {}

    def ref_path(self, key, name):  # wohin ein empfangener Anhang gehört (None = verwerfen)
        return None

    def merge(self, key, a, b):     # nebenläufige Stände zusammenführen (None = Konflikt-Kopie)
        return None

    def updated(self, content):
        return str(content.get("updated") or "")


class Replica:
    def __init__(self, backend, path=None, me=None, blob_dir=None):
        self.b = backend
        self.path = path
        self.lock = threading.RLock()
        self.st = self._load()
        if me:
            self.st["me"] = me
        self.st.setdefault("me", secrets.token_hex(6))
        for k in ("e", "need", "shas", "peers", "ack"):
            self.st.setdefault(k, {})
        self.blob_dir = blob_dir or (os.path.join(os.path.dirname(path), "sync2-teile") if path else None)
        self.sess = {}            # peer → {sess, ctr, h, resp} (nur im Speicher: Neustart = neue Sitzung)
        self.ext = {}             # zusätzliche Anfragen (op → fn(req)), z. B. compile (Schritt 29); laufen im Anfrage-Faden
        self.stats = {"got": 0, "conflicts": 0, "deleted": 0, "keys": set()}

    @property
    def me(self):
        return self.st["me"]

    # ----- Zustand -----
    def _load(self):
        if not self.path:
            return {}
        try:
            with open(self.path, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return {}

    def save(self):
        if not self.path:
            return
        with self.lock:
            raw = json.dumps(self.st, ensure_ascii=False, separators=(",", ":"))
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(raw)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, self.path)

    def _bump(self, vv):
        vv = dict(vv)
        vv[self.me] = vv.get(self.me, 0) + 1
        return vv

    # ----- Anhänge: Prüfsummen mit Zwischenspeicher -----
    def _sha(self, path):
        try:
            s = os.stat(path)
        except OSError:
            return None
        c = self.st["shas"].get(path)
        if c and c[0] == s.st_mtime_ns and c[1] == s.st_size:
            return c[2]
        if s.st_size > MAX_BLOB:
            return None
        sha = file_sha(path)
        self.st["shas"][path] = [s.st_mtime_ns, s.st_size, sha]
        return sha

    def _blobmap(self, key, content):
        out = {}
        for name, p in (self.b.refs(key, content) or {}).items():
            sha = self._sha(p)
            if sha:
                out[name] = sha
        e = self.st["e"].get(key)
        for name, sha in ((e or {}).get("b") or {}).items():      # unterwegs: zählt schon als da
            if name not in out and sha in self.st["need"]:
                out[name] = sha
        return out

    def _local_blob(self, sha):
        for p, c in list(self.st["shas"].items()):
            if c[2] == sha and os.path.exists(p) and self._sha(p) == sha:
                return p
        return None

    # ----- eigene Änderungen erkennen -----
    def scan(self):
        with self.lock:
            E, seen = self.st["e"], set()
            for key in list(self.b.keys()):
                e = E.get(key)
                s = _norm(self.b.stamp(key))
                if e is not None and e["d"] is not None and s is not None and e.get("s") == s:
                    seen.add(key)
                    continue
                c = self.b.get(key)
                if c is None:
                    continue
                seen.add(key)
                bm = self._blobmap(key, c)
                d = digest(c, bm)
                if e is None:
                    E[key] = {"vv": {self.me: 1}, "d": d, "s": s, "b": bm}
                elif e["d"] != d:
                    E[key] = {"vv": self._bump(e["vv"]), "d": d, "s": s, "b": bm}
                else:
                    e["s"] = s
            for key, e in E.items():
                if e["d"] is not None and key not in seen:         # hier endgültig gelöscht → Grabstein
                    E[key] = {"vv": self._bump(e["vv"]), "d": None, "t": time.time()}
            self._gc()

    def summary(self):
        with self.lock:
            return {k: [e["vv"], e["d"]] for k, e in self.st["e"].items()}

    # ----- was die Gegenseite braucht -----
    def outgoing(self, theirs, limit=MAX_OUT):
        with self.lock:
            want = []
            for key, e in self.st["e"].items():
                t = theirs.get(key)
                if t is not None and vv_leq(e["vv"], t[0]):
                    continue
                want.append(key)
            items, size, more = [], 0, False

            def order(k):
                e = self.st["e"][k]
                return (0 if k.startswith("prefs:") else 1, -len(e["vv"]), k)
            for key in sorted(want, key=order):
                e = self.st["e"][key]
                it = {"k": key, "vv": e["vv"], "d": e["d"]}
                t = theirs.get(key)
                if e["d"] is not None and not (t is not None and t[1] == e["d"]):
                    c = self.b.get(key)
                    if c is None:
                        continue                     # zwischen scan und jetzt verschwunden – nächste Runde
                    it["n"] = c
                    if e.get("b"):
                        it["b"] = e["b"]
                est = len(canon(it))
                if items and size + est > limit:
                    more = True
                    break
                items.append(it)
                size += est
            return items, more

    # ----- empfangen -----
    def take(self, peer, items, theirs=None):
        with self.lock:
            for it in items or []:
                try:
                    self._take(it)
                except (KeyError, TypeError, ValueError) as e:
                    raise Refused(f"ungültiger eintrag: {e}") from None
            if theirs is not None and peer:
                self._note_peer(peer, theirs)

    def _take(self, it):
        key, vv, d = it["k"], dict(it["vv"]), it.get("d")
        if not isinstance(key, str) or ":" not in key or not isinstance(vv, dict):
            raise ValueError(key)
        n, bm = it.get("n"), dict(it.get("b") or {})
        E = self.st["e"]
        e = E.get(key)
        if d is not None and n is None and (e is None or e["d"] != d):
            return                                   # Inhalt fehlt (Gegenseite dachte, wir hätten ihn) – nächste Runde
        if e is None:
            if d is None:
                E[key] = {"vv": vv, "d": None, "t": time.time()}
            else:
                self._put(key, n, bm, vv, d)
                self.stats["got"] += 1
            return
        if vv_leq(vv, e["vv"]):
            return                                   # kennen wir schon (oder Neueres)
        if vv_leq(e["vv"], vv):                      # dort neuer – unser Stand ist Vorfahr
            if d is None:
                if e["d"] is not None:
                    self.b.delete(key)
                    self.stats["deleted"] += 1
                    self.stats["keys"].add(key)
                E[key] = {"vv": vv, "d": None, "t": time.time()}
            elif d != e["d"]:
                self._put(key, n, bm, vv, d)
                self.stats["got"] += 1
            else:
                e["vv"] = vv
            return
        # nebenläufig
        m = vv_merge(e["vv"], vv)
        if d == e["d"]:
            e["vv"] = m
            return
        if d is None:                                # dort gelöscht, hier bearbeitet → bleibt, Löschung verworfen
            e["vv"] = self._bump(m)
            return
        if e["d"] is None:                           # hier gelöscht, dort bearbeitet → zurückholen
            self._put(key, n, bm, self._bump(m), d)
            self.stats["got"] += 1
            return
        cur = self.b.get(key)
        if cur is None:                              # (sollte nicht vorkommen) wie hier gelöscht behandeln
            self._put(key, n, bm, self._bump(m), d)
            return
        mrg = self.b.merge(key, cur, n)
        if mrg is not None:
            self._put(key, mrg, {**e.get("b", {}), **bm}, self._bump(m), None)
            return
        self.stats["conflicts"] += 1
        mine = (self.b.updated(cur), e["d"])
        theirs = (self.b.updated(n), d)
        if theirs > mine:
            self._copy(key, cur, e.get("b") or {}, e["d"])
            self._put(key, n, bm, self._bump(m), d)
        else:
            self._copy(key, n, bm, d)
            e["vv"] = self._bump(m)

    def _copy(self, key, content, bm, d):
        kind = key.split(":", 1)[0]
        nid = str(uuid.uuid5(NS, key + "/" + str(d)))
        ckey = f"{kind}:{nid}"
        if ckey in self.st["e"]:
            return
        c = dict(content)
        c["id"] = nid
        c["title"] = (c.get("title") or "") + " (konflikt)"
        self._put(ckey, c, bm, {"_": 1}, None)
        self.stats["keys"].add(ckey)

    def _put(self, key, content, bm, vv, d):
        """Inhalt schreiben, Anhänge einsortieren (vorhanden / lokal kopierbar / zu holen), Zustand merken."""
        self.b.put(key, content)
        self.stats["keys"].add(key)
        for name, sha in bm.items():
            p = self.b.ref_path(key, name)
            if not p or self._sha(p) == sha:
                continue
            src = self._local_blob(sha)
            if src:
                os.makedirs(os.path.dirname(p), exist_ok=True)
                shutil.copyfile(src, p + ".sync2")
                os.replace(p + ".sync2", p)
                self._sha(p)
            else:
                need = self.st["need"].setdefault(sha, {"to": []})
                if [key, name] not in need["to"]:
                    need["to"].append([key, name])
        self.st["e"][key] = {"vv": vv, "d": None, "b": bm}
        got = self.b.get(key)
        real = digest(got, self._blobmap(key, got)) if got is not None else None
        if d is not None and real != d:              # Speicher hat den Inhalt angepasst → das ist unser neuer Stand
            vv = self._bump(vv)
        self.st["e"][key] = {"vv": vv, "d": real, "s": _norm(self.b.stamp(key)), "b": bm}

    def _note_peer(self, peer, theirs):
        """Quittungen für Grabsteine: die Gegenseite meldet ihn selbst (gleich oder neuer)."""
        self.st["peers"][peer] = time.time()
        for key, e in self.st["e"].items():
            if e["d"] is None:
                t = theirs.get(key)
                if t is not None and t[1] is None and vv_leq(e["vv"], t[0]):
                    acks = self.st["ack"].setdefault(key, [])
                    if peer not in acks:
                        acks.append(peer)

    def _gc(self):
        peers = set(self.st["peers"])
        if not peers:
            return
        old = time.time() - TOMB_DAYS * 86400
        for key in [k for k, e in self.st["e"].items() if e["d"] is None and e.get("t", 0) < old]:
            if peers <= set(self.st["ack"].get(key, [])):
                del self.st["e"][key]
                self.st["ack"].pop(key, None)

    # ----- Anhänge übertragen -----
    def missing(self):
        with self.lock:
            return sorted(self.st["need"])

    def has_blob(self, sha):
        with self.lock:
            return self._local_blob(sha) is not None

    def blob_read(self, sha, off, n=None):
        n = n or CHUNK
        with self.lock:
            p = self._local_blob(sha)
        if p is None:
            raise Refused("anhang unbekannt")
        size = os.path.getsize(p)
        with open(p, "rb") as f:
            f.seek(off)
            data = f.read(n)
        return size, data

    def _part(self, sha):
        if not self.blob_dir:
            raise Refused("kein ordner für anhänge")
        os.makedirs(self.blob_dir, exist_ok=True)
        if not all(c in "0123456789abcdef" for c in sha) or len(sha) != 64:
            raise Refused("prüfsumme ungültig")
        return os.path.join(self.blob_dir, sha + ".part")

    def blob_offset(self, sha):
        p = self._part(sha)
        return os.path.getsize(p) if os.path.exists(p) else 0

    def blob_write(self, sha, off, data, size):
        """Häppchen anhängen; gibt den nächsten erwarteten Versatz zurück (Fortsetzen nach Abbruch)."""
        with self.lock:
            if sha not in self.st["need"]:
                return size                      # brauchen wir nicht (mehr)
            if size > MAX_BLOB:
                raise Refused("anhang zu groß")
            p = self._part(sha)
            have = os.path.getsize(p) if os.path.exists(p) else 0
            if off != have:
                return have
            with open(p, "ab") as f:
                f.write(data)
            have += len(data)
            if have < size:
                return have
            if have > size or file_sha(p) != sha:
                os.remove(p)
                return 0
            for key, name in self.st["need"].pop(sha)["to"]:
                dest = self.b.ref_path(key, name)
                if dest:
                    os.makedirs(os.path.dirname(dest), exist_ok=True)
                    shutil.copyfile(p, dest + ".sync2")
                    os.replace(dest + ".sync2", dest)
                    self._sha(dest)
                    e = self.st["e"].get(key)
                    if e is not None:
                        e["s"] = _norm(self.b.stamp(key))
            os.remove(p)
            return size

    # ----- Server -----
    def handle(self, peer, req):
        """Eine Anfrage einer gekoppelten Gegenstelle `peer` (Geräte-Id aus der Kopplung). Bei sync läuft das
        im Hauptfaden des Programms (Backend fasst die Einträge an), blob/put dürfen in jedem Faden laufen."""
        op = req.get("op")
        if op == "open":
            sess = secrets.token_hex(8)
            with self.lock:
                self.sess[peer] = {"sess": sess, "ctr": 0, "h": None, "resp": None}
            return {"sess": sess, "me": self.me, "v": V}
        with self.lock:
            s = self.sess.get(peer)
            if not s or req.get("sess") != s["sess"]:
                raise Refused("sitzung abgelaufen")
            ctr = int(req.get("ctr") or 0)
            h = hashlib.sha256(canon(req).encode()).hexdigest()
            if ctr == s["ctr"] and s["resp"] is not None:
                if h == s["h"]:
                    return s["resp"]             # Wiederholung (Antwort ging verloren) → dieselbe Antwort
                raise Refused("wiederholte nummer mit anderem inhalt")
            if ctr <= s["ctr"]:
                raise Refused("veraltete anfrage")
            s["ctr"], s["h"], s["resp"] = ctr, h, None
        resp = self._dispatch(op, req)
        with self.lock:
            if self.sess.get(peer) is s and s["ctr"] == ctr:
                s["h"], s["resp"] = h, resp
        return resp

    def _dispatch(self, op, req):
        if op == "sync":
            self.scan()
            theirs = req.get("have") or {}
            self.take(str(req.get("me") or ""), req.get("data") or [], theirs)
            items, more = self.outgoing(theirs)
            out = {"me": self.me, "have": self.summary(), "data": items, "more": more, "need": self.missing()}
            self.save()
            return out
        if op == "blob":
            size, data = self.blob_read(str(req.get("sha")), int(req.get("off") or 0))
            return {"size": size, "b64": base64.b64encode(data).decode()}
        if op == "put":
            off = self.blob_write(str(req.get("sha")), int(req.get("off") or 0),
                                  base64.b64decode(req.get("b64") or ""), int(req.get("size") or 0))
            self.save()
            return {"off": off}
        if op in self.ext:
            return self.ext[op](req)
        raise Refused(f"unbekannte anfrage {op!r}")

    # ----- Client -----
    def run(self, call, on_main=None, rounds=200):
        """Abgleich gegen eine Gegenstelle. call(req) → antwort (Transport, darf werfen). on_main(fn) führt fn im
        Hauptfaden aus (Backend-Zugriffe). Gibt eine Statistik zurück. Abbruch an jeder Stelle ist harmlos."""
        on_main = on_main or (lambda fn: fn())
        self.stats = {"got": 0, "conflicts": 0, "deleted": 0, "keys": set()}
        r = call({"op": "open"})
        sess, peer = r["sess"], r["me"]
        ctr = 0

        def ask(o):
            nonlocal ctr
            ctr += 1
            o.update(sess=sess, ctr=ctr)
            return call(o)

        theirs, last_in, need = None, True, []
        sent = 0
        for _ in range(rounds):
            def prep():
                self.scan()
                if theirs is None:
                    return self.summary(), [], False
                return (self.summary(),) + self.outgoing(theirs)
            have, data, _more = on_main(prep)
            if theirs is not None and not data and not last_in:
                break
            res = ask({"op": "sync", "me": self.me, "have": have, "data": data})
            sent += len(data)
            on_main(lambda: self.take(peer, res.get("data") or [], res.get("have") or {}))
            theirs = res.get("have") or {}
            last_in = bool(res.get("data")) or bool(res.get("more"))
            need = res.get("need") or []
        else:
            raise RuntimeError("abgleich endet nicht")
        on_main(self.save)
        # Anhänge holen (setzt bei Abbruch beim gespeicherten Teil fort)
        for sha in self.missing():
            off, stuck = self.blob_offset(sha), 0
            while stuck < 3:
                try:
                    r = ask({"op": "blob", "sha": sha, "off": off})
                except Refused:
                    break                        # Gegenstelle hat ihn (noch) nicht – bleibt offen
                size = int(r["size"])
                nxt = self.blob_write(sha, off, base64.b64decode(r["b64"]), size)
                if nxt >= size or not r["b64"]:
                    break
                stuck = stuck + 1 if nxt <= off else 0
                off = nxt
        # Anhänge abgeben
        for sha in need:
            if not self.has_blob(sha):
                continue
            off = 0
            while True:
                size, data = self.blob_read(sha, off)
                nxt = int(ask({"op": "put", "sha": sha, "off": off, "size": size,
                               "b64": base64.b64encode(data).decode()})["off"])
                if nxt >= size:
                    break
                off = nxt
        on_main(self.save)
        st = dict(self.stats)
        st["sent"] = sent
        st["peer"] = peer
        return st


# ---------- Kopplung: SPAKE2 (RFC-3526-Gruppe 14, Untergruppe der Ordnung q) ----------
P = int("FFFFFFFFFFFFFFFFC90FDAA22168C234C4C6628B80DC1CD129024E088A67CC74020BBEA63B139B22514A08798E3404DD"
        "EF9519B3CD3A431B302B0A6DF25F14374FE1356D6D51C245E485B576625E7EC6F44C42E9A637ED6B0BFF5CB6F406B7ED"
        "EE386BFB5A899FA5AE9F24117C4B1FE649286651ECE45B3DC2007CB8A163BF0598DA48361C55D39A69163FA8FD24CF5F"
        "83655D23DCA3AD961C62F356208552BB9ED529077096966D670C354E4ABC9804F1746C08CA18217C32905E462E36CE3B"
        "E39E772C180E86039B2783A2EC07A28FB5C55DF06F4C52C9DE2BCBF6955817183995497CEA956AE515D2261898FA0510"
        "15728E5A8AACAA68FFFFFFFFFFFFFFFF", 16)
Q = (P - 1) // 2
G = 2                                    # p ≡ 7 (mod 8) → 2 ist quadratischer Rest, erzeugt die Untergruppe


def _h2g(label):
    """Element der Untergruppe ohne bekannten Logarithmus (Hash → Quadrat)."""
    raw = b"".join(hashlib.sha512(label + bytes([i])).digest() for i in range(5))
    return pow(int.from_bytes(raw, "big") % P, 2, P)


PM, PN = _h2g(b"notist-spake2-M"), _h2g(b"notist-spake2-N")


def _w(code):
    code = "".join(ch for ch in str(code).upper() if ch.isalnum())
    return int.from_bytes(hashlib.sha256(b"notist-pake-v2:" + code.encode()).digest(), "big") % Q


def _ok_elem(x):
    return 1 < x < P - 1 and pow(x, Q, P) == 1


def _keys(X, Y, K, w):
    t = b"".join(v.to_bytes(256, "big") for v in (X, Y, K)) + w.to_bytes(32, "big")
    k = hashlib.sha256(b"notist-pake-key" + t).digest()
    return (k, hmac.new(k, b"cli", hashlib.sha256).hexdigest(), hmac.new(k, b"srv", hashlib.sha256).hexdigest())


def pake_client_start(code):
    """→ (zustand, X als Hex) – X an den Server."""
    x = secrets.randbelow(Q - 2) + 1
    X = pow(G, x, P) * pow(PM, _w(code), P) % P
    return {"x": x, "X": X, "w": _w(code)}, format(X, "x")


def pake_server(code, X_hex):
    """Server: → (zustand, Y als Hex). Y verrät nichts über den Code."""
    X = int(X_hex, 16)
    if not _ok_elem(X):
        raise ValueError("ungültig")
    w = _w(code)
    y = secrets.randbelow(Q - 2) + 1
    Y = pow(G, y, P) * pow(PN, w, P) % P
    K = pow(X * pow(pow(PM, w, P), P - 2, P) % P, y, P)
    key, cli, srv = _keys(X, Y, K, w)
    return {"key": key, "cli": cli, "srv": srv}, format(Y, "x")


def pake_client_finish(state, Y_hex):
    """Client: → (schlüssel, eigener Beweis, erwarteter Server-Beweis)."""
    Y = int(Y_hex, 16)
    if not _ok_elem(Y):
        raise ValueError("ungültige antwort")
    K = pow(Y * pow(pow(PN, state["w"], P), P - 2, P) % P, state["x"], P)
    return _keys(state["X"], Y, K, state["w"])


def pake_check(expected, got):
    return hmac.compare_digest(str(expected), str(got))
