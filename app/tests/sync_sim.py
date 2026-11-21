#!/usr/bin/env python3
# Abgleich v2 (core/sync2.py) im Simulator – Plan Schritt 9. Ohne GTK, ohne Netz.
# Zwei/drei Geräte, Zufallsfolgen aus Anlegen/Bearbeiten/Löschen/Einstellungen/Anhängen und Abgleichen mit Störungen:
# Anfrage weg, Antwort weg (nach dem Anwenden), doppelte Zustellung, Abbruch mitten im Anhang, verstellte Uhren.
# Invarianten nach einem störungsfreien Schlussabgleich:
#   1. Konvergenz: alle Geräte haben dieselben Einträge, Einstellungen und Anhänge.
#   2. Nie stiller Verlust: jeder Text, den niemand bewusst überschrieben/gelöscht hat, steht noch in einem Eintrag
#      (Konflikt → Kopie). Eigene Wörter gehen nie verloren.
#   python tests/sync_sim.py [--runs 10000] [--seed 1] [-v]
import os, random, shutil, sys, tempfile, time

APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, APP)
sys.modules.setdefault("gi", None)          # beweist nebenbei: der Kern braucht kein GTK
from core import sync2  # noqa: E402

VERBOSE = "-v" in sys.argv


def arg(name, default):
    return type(default)(sys.argv[sys.argv.index(name) + 1]) if name in sys.argv else default


class Lost(Exception):
    pass


class MemBackend(sync2.Backend):
    def __init__(self, files):
        self.d, self.ver, self.files = {}, {}, files
        self.n = 0

    def keys(self):
        return list(self.d)

    def stamp(self, key):
        return None if key.startswith("prefs:") else self.ver.get(key)

    def get(self, key):
        c = self.d.get(key)
        return None if c is None else {k: (list(v) if isinstance(v, list) else v) for k, v in c.items()}

    def put(self, key, content):
        self.d[key] = {k: (list(v) if isinstance(v, list) else v) for k, v in content.items()}
        self.n += 1
        self.ver[key] = self.n

    def delete(self, key):
        self.d.pop(key, None)
        self.ver.pop(key, None)

    def _dir(self, key):
        return os.path.join(self.files, key.replace(":", "_"))

    def refs(self, key, c):
        out = {}
        for name in c.get("att") or []:
            p = os.path.join(self._dir(key), name)
            if os.path.exists(p):
                out[name] = p
        return out

    def ref_path(self, key, name):
        return os.path.join(self._dir(key), name) if "/" not in name and ".." not in name else None

    def merge(self, key, a, b):
        if key.startswith("prefs:"):
            return {"v": sorted(set(a.get("v") or []) | set(b.get("v") or []))}
        return None


class Dev:
    def __init__(self, name, root, rng):
        self.name = name
        self.be = MemBackend(os.path.join(root, name, "files"))
        self.rep = sync2.Replica(self.be, me=name, blob_dir=os.path.join(root, name, "parts"))
        self.skew = rng.randint(-500, 500)            # verstellte Uhr
        self.be.d["prefs:words"] = {"v": []}
        self.be.ver["prefs:words"] = 0


class World:
    def __init__(self, rng, root, ndev, att):
        self.rng, self.root, self.att = rng, root, att
        self.devs = [Dev("abc"[i], root, rng) for i in range(ndev)]
        self.t = 0
        self.alive = set()        # Texte, die nie bewusst überschrieben/gelöscht wurden
        self.words = set()
        self.tok = 0
        self.log = []
        self.chunk = None

    def token(self):
        self.tok += 1
        return f"T{self.tok}"

    def now(self, dev):
        self.t += 1
        return f"{self.t * 10 + dev.skew + 100000:09d}"

    def live(self, dev):
        return [k for k in dev.be.d if not k.startswith("prefs:")]

    def step(self):
        rng = self.rng
        dev = rng.choice(self.devs)
        r = rng.random()
        live = self.live(dev)
        if r < 0.18 or not live:
            nid = "%08x" % rng.getrandbits(32)
            key = f"notes:{nid}"
            tok = self.token()
            c = {"id": nid, "title": f"t{nid[:3]}", "text": tok, "updated": self.now(dev)}
            if self.att and rng.random() < 0.4:
                name = f"a{rng.randint(0, 3)}.bin"
                p = dev.be.ref_path(key, name)
                os.makedirs(os.path.dirname(p), exist_ok=True)
                with open(p, "wb") as f:
                    f.write(rng.randbytes(rng.randint(1, 5000)))
                c["att"] = [name]
            dev.be.put(key, c)
            self.alive.add(tok)
            self.log.append(f"{dev.name} neu {key} {tok}")
        elif r < 0.55:
            key = rng.choice(live)
            c = dev.be.get(key)
            old = c["text"]
            tok = self.token()
            c["text"], c["updated"] = tok, self.now(dev)
            dev.be.put(key, c)
            self.alive.discard(old)
            self.alive.add(tok)
            self.log.append(f"{dev.name} bearbeitet {key} {old}→{tok}")
        elif r < 0.65:
            key = rng.choice(live)
            self.alive.discard(dev.be.d[key]["text"])
            dev.be.delete(key)
            self.log.append(f"{dev.name} löscht {key}")
        elif r < 0.72:
            w = f"w{rng.randint(0, 999)}"
            c = dev.be.get("prefs:words")
            if w not in c["v"]:
                c["v"] = sorted(c["v"] + [w])
                dev.be.put("prefs:words", c)
                self.words.add(w)
            self.log.append(f"{dev.name} wort {w}")
        else:
            a, b = rng.sample(self.devs, 2)
            self.sync(a, b, faults=True)

    def sync(self, cli, srv, faults):
        rng = self.rng
        sync2.CHUNK = self.chunk or sync2.CHUNK

        def call(req):
            if faults and rng.random() < 0.06:
                raise Lost("anfrage weg")
            if faults and rng.random() < 0.05:
                srv.rep.handle(cli.name, dict(req))      # doppelt zugestellt – zweite Antwort zählt
            res = srv.rep.handle(cli.name, req)
            if faults and rng.random() < 0.06:
                raise Lost("antwort weg")
            return sync2.json.loads(sync2.json.dumps(res))
        try:
            st = cli.rep.run(call)
            self.log.append(f"sync {cli.name}→{srv.name} ok {st['got']}/{st['sent']}/{st['conflicts']}")
        except Lost as e:
            self.log.append(f"sync {cli.name}→{srv.name} abbruch: {e}")

    def settle(self):
        for _ in range(4):
            for a in self.devs:
                for b in self.devs:
                    if a is not b:
                        self.sync(a, b, faults=False)

    def check(self):
        ref = self.devs[0]
        for d in self.devs[1:]:
            if d.be.d != ref.be.d:
                diff = sorted(k for k in set(d.be.d) | set(ref.be.d) if d.be.d.get(k) != ref.be.d.get(k))
                return f"nicht konvergiert ({ref.name}≠{d.name}): {diff[:4]}"
            for key, c in ref.be.d.items():
                for name in c.get("att") or []:
                    pa, pb = ref.be.ref_path(key, name), d.be.ref_path(key, name)
                    if not os.path.exists(pa) or not os.path.exists(pb):
                        return f"anhang fehlt: {key}/{name}"
                    with open(pa, "rb") as fa, open(pb, "rb") as fb:
                        if fa.read() != fb.read():
                            return f"anhang verschieden: {key}/{name}"
            if d.rep.missing():
                return f"{d.name}: anhänge offen {d.rep.missing()}"
        texts = {c.get("text") for c in ref.be.d.values()}
        lost = self.alive - texts
        if lost:
            return f"still verloren: {sorted(lost)[:5]}"
        if not self.words <= set(ref.be.d["prefs:words"]["v"]):
            return "wörter verloren"
        return None


def run(seed, steps=None):
    rng = random.Random(seed)
    root = tempfile.mkdtemp(prefix="notist-sim-")
    try:
        w = World(rng, root, rng.choice((2, 2, 3)), att=rng.random() < 0.3)
        w.chunk = rng.choice((7, 300, 2 * 1024 * 1024))
        for _ in range(steps or rng.randint(5, 40)):
            w.step()
        w.settle()
        err = w.check()
        return err, w.log
    finally:
        shutil.rmtree(root, ignore_errors=True)


class NormBackend(MemBackend):
    """Speichert Empfangenes leicht anders ab (wie der DOCX-Rundweg am PC oder ein anderes docfmt am Handy)."""
    def __init__(self, files, tag):
        super().__init__(files)
        self.tag = tag

    def put(self, key, content):
        super().put(key, {**content, "norm": self.tag} if not key.startswith("prefs:") else content)


def check_normalize():
    """2026-11-18: Normalisierung zählte als eigene Änderung → Zähler in die Tausende, Konflikt-Kopien von Kopien.
    Jetzt: ohne Bearbeitung bleibt alles ruhig; echte Änderungen kommen weiter an; kaputter Zustand → .bak, Kennung bleibt."""
    root = tempfile.mkdtemp(prefix="notist-norm-")
    try:
        devs = []
        for name in "ab":
            os.makedirs(os.path.join(root, name))
            be = NormBackend(os.path.join(root, name, "files"), name)
            devs.append((be, sync2.Replica(be, path=os.path.join(root, name, "sync2.json"))))
        (ba, ra), (bb, rb) = devs
        for i in range(5):
            ba.d[f"docs:{i}"] = {"id": str(i), "title": f"t{i}", "text": f"x{i}", "updated": "1"}
            ba.ver[f"docs:{i}"] = 100 + i

        def sync(src, dst):
            src.scan(); dst.scan()
            items, _ = src.outgoing(dst.summary())
            dst.take(src.me, items, src.summary())
        for _ in range(10):
            sync(ra, rb); sync(rb, ra)
        top = max(sum(e["vv"].values()) for r in (ra, rb) for e in r.st["e"].values())
        assert top <= 2, f"zähler schaukeln hoch: {top}"
        assert not any("konflikt" in str(c.get("title")) for be in (ba, bb) for c in be.d.values()), "konflikt-kopie"
        bb.put("docs:1", {**bb.d["docs:1"], "text": "neu von b", "updated": "2"})      # echte Änderung an b
        for _ in range(3):
            sync(ra, rb); sync(rb, ra)
        assert ba.d["docs:1"]["text"] == "neu von b", "echte änderung kam nicht an"
        ra.save(); ra.save()
        me = ra.me
        with open(ra.path, "w") as f:
            f.write("{kaputt")
        r2 = sync2.Replica(ba, path=ra.path)
        assert r2.me == me and r2.st["e"], "kaputter zustand: .bak nicht genommen"
        os.remove(ra.path); os.remove(ra.path + ".bak")
        assert sync2.Replica(ba, path=ra.path).me == me, "kennung verloren"
    finally:
        shutil.rmtree(root, ignore_errors=True)


def main():
    check_normalize()
    print("✓ normalisierung/zustand")
    runs, seed = arg("--runs", 10000), arg("--seed", 1)
    t0 = time.time()
    bad = 0
    for i in range(runs):
        err, log = run(seed * 1_000_003 + i)
        if err:
            bad += 1
            print(f"✗ lauf {i} (seed {seed * 1_000_003 + i}): {err}")
            if VERBOSE or bad == 1:
                print("   " + "\n   ".join(log[-40:]))
            if bad >= 5:
                break
        elif VERBOSE and i % 1000 == 0:
            print(f"  {i} …")
    print(f"{'✓' if not bad else '✗'} sync_sim: {runs if not bad else i + 1} läufe, {bad} fehler, {time.time() - t0:.1f} s")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
