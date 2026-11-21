#!/usr/bin/env python3
# Gemeinsames Bearbeiten (core/collab.py) ohne Netz: Delta-Grundlagen, Umwandlung Eintrag ↔ Delta (Gold-Korpus) und
# ein Simulator mit 2–4 Geräten, die gleichzeitig zufällig tippen, löschen, formatieren und Absätze/Objekte einfügen;
# der Server reiht in zufälliger Folge, Zustellung verzögert. Am Ende müssen alle Geräte dasselbe Dokument haben und
# es muss dem kanonischen Server-Stand entsprechen.
#   python tests/collab_test.py [--runs 3000]
import glob, json, os, random, sys, time

APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, APP)
sys.modules.setdefault("gi", None)
from core import collab as C  # noqa: E402


def check(cond, what):
    if not cond:
        raise AssertionError(what)


def basics():
    a = [{"insert": "Hallo Welt\n"}]
    check(C.apply(a, [{"retain": 5}, {"insert": ","}]) == [{"insert": "Hallo, Welt\n"}], "insert")
    check(C.apply(a, [{"retain": 6}, {"delete": 4}]) == [{"insert": "Hallo \n"}], "delete")
    check(C.apply(a, [{"retain": 5, "attributes": {"b": True}}]) ==
          [{"insert": "Hallo", "attributes": {"b": True}}, {"insert": " Welt\n"}], "format")
    x, y = [{"retain": 2}, {"insert": "A"}], [{"retain": 2}, {"insert": "B"}]
    d1 = C.apply(C.apply(a, x), C.transform(x, y, True))
    d2 = C.apply(C.apply(a, y), C.transform(y, x, False))
    check(d1 == d2 and C.text_of(d1).startswith("HaAB"), f"tie: {d1} {d2}")
    check(C.transform_pos(3, [{"retain": 1}, {"insert": "xx"}]) == 5, "pos")
    check(C.diff(a, C.apply(a, [{"retain": 5, "attributes": {"b": True}}])) == [{"retain": 5, "attributes": {"b": True}}],
          "diff attrs")
    n = {"text": "☐ kaufen " + C.OBJ + " fertig", "rich": [[2, 8, "bold"]], "images": [{"table": {"rows": [["a"]]}}]}
    m = C.doc_into_entry("notes", C.entry_to_doc("notes", n), {})
    check(m["text"] == n["text"] and m["rich"] == n["rich"] and m["images"] == n["images"], f"notiz rundweg {m}")
    print("✓ grundlagen")


def gold():
    """Jedes Words-Modell aus dem Gold-Korpus übersteht blocks → Delta → blocks (nach docfmt-Normalisierung)."""
    from core import docfmt as df
    files = glob.glob(os.path.join(APP, "tests", "gold", "**", "*.json"), recursive=True)
    n = 0
    for f in files:
        try:
            with open(f, encoding="utf-8") as fh:
                d = json.load(fh)
        except (OSError, ValueError):
            continue
        blocks = d.get("blocks") if isinstance(d, dict) else d if isinstance(d, list) else None
        if not blocks or not isinstance(blocks, list) or not all(isinstance(b, dict) and "t" in b for b in blocks):
            continue
        back = C.doc_to_blocks(C.blocks_to_doc(blocks))
        norm = lambda bl: [dict(b, runs=df.merge_runs(b["runs"])) if b.get("t") == "p" else b for b in bl]
        check(norm(back) == norm(blocks), f"gold {f}")
        n += 1
    print(f"✓ gold-korpus: {n} modelle")


# ---------------------------------------------------------------- Simulator
class FakeAcct:
    def __init__(self, name, dev):
        self.name, self.dev = name, dev


class Dev:
    def __init__(self, i, doc, rng):
        self.rng = rng
        self.text = C.deep(doc)                        # „Editor“
        self.live = C.Live(FakeAcct(f"u{i % 2}", f"d{i}"), "s", i == 0, lambda: C.deep(self.text),
                           self._apply, lambda fn: fn())
        self.live.rev, self.live.canon, self.live.doc, self.live.ready = 0, C.deep(doc), C.deep(doc), True

    def _apply(self, d, doc):
        self.text = C.apply(self.text, d)
        check(self.text == doc, "editor ≠ live.doc nach fremder änderung")

    def edit(self):
        rng, L = self.rng, C.doc_len(self.text)
        r = rng.random()
        pos = rng.randrange(0, L)                       # nie hinter das letzte "\n"
        if r < 0.45:
            ins = rng.choice(["a", "bc", " ", "xyz", "\n", "Ü", {"block": {"t": "hr"}}, {"run": {"img": "Zg==", "w": 1}}])
            at = rng.choice([None, None, {"b": True}, {"i": True}])
            d = [{"retain": pos}, {"insert": ins, **({"attributes": at} if at else {})}] if pos else \
                [{"insert": ins, **({"attributes": at} if at else {})}]
        elif r < 0.75 and L > 2:
            n = rng.randint(1, min(4, L - 1 - pos)) if L - 1 - pos >= 1 else 0
            if not n:
                return
            d = [{"retain": pos}, {"delete": n}] if pos else [{"delete": n}]
        else:
            n = rng.randint(1, max(1, min(5, L - pos)))
            at = rng.choice([{"b": True}, {"b": None}, {"u": True}, {"style": "h1"}, {"color": "#f00"}])
            d = [{"retain": pos}, {"retain": n, "attributes": at}] if pos else [{"retain": n, "attributes": at}]
        self.text = C.apply(self.text, C.chop([o for o in d if C.op_len(o) or "insert" in o]))
        if rng.random() < 0.7:                            # sonst: noch nicht gesendet (Entprellung) – Live muss es selbst holen
            self.live.local_changed()


def sim(seed):
    rng = random.Random(seed)
    start = [{"insert": "Hallo Welt"}, {"insert": "\n", "attributes": {"style": "h1"}}, {"insert": "zwei\n"}]
    devs = [Dev(i, start, rng) for i in range(rng.choice((2, 2, 3, 4)))]
    log, canon = [], C.deep(start)                      # Server: Folge der Änderungen (wie geschickt)
    seen = {}
    got = [0] * len(devs)                               # bis wohin jedes Gerät den Log kennt
    for _ in range(rng.randint(10, 80)):
        k = rng.randrange(len(devs))
        r = rng.random()
        if r < 0.5:
            devs[k].edit()
        elif r < 0.8:                                    # Server nimmt die nächste Sendung eines Geräts an
            q = devs[k].live.outq
            if q:
                it = q.pop(0)
                if "op" in it:
                    key = (devs[k].live.a.dev, it["seq"])
                    if key not in seen:
                        seen[key] = True
                        log.append({"rev": len(log) + 1, "by": devs[k].live.a.name, "dev": it["dev"], "seq": it["seq"],
                                    "base": it["base"], "op": it["op"]})
        else:                                            # Zustellung eines Teils des Logs
            upto = rng.randint(got[k], len(log))
            if upto > got[k]:
                devs[k].live._incoming(C.deep(log[got[k]:upto]), [])
                got[k] = upto
    for dv in devs:
        dv.live.local_changed()
    for _ in range(50):                                  # ausklingen lassen
        busy = False
        for k, dv in enumerate(devs):
            q = dv.live.outq
            while q:
                it = q.pop(0)
                if "op" in it:
                    log.append({"rev": len(log) + 1, "by": dv.live.a.name, "dev": it["dev"], "seq": it["seq"],
                                "base": it["base"], "op": it["op"]})
                    busy = True
            if got[k] < len(log):
                dv.live._incoming(C.deep(log[got[k]:]), [])
                got[k] = len(log)
                busy = True
        if not busy:
            break
    ref = devs[0].text
    for dv in devs:
        check(dv.live.inflight is None and dv.live.buffer is None, "offen geblieben")
        check(dv.text == ref, f"nicht gleich:\n{ref}\n{dv.text}")
        check(dv.live.canon == ref, "kanonischer stand ≠ editor")
        check(C.doc_len(dv.text) >= 1 and C.text_of(dv.text).endswith("\n"), "schluss-\\n fehlt")


def main():
    runs = int(sys.argv[sys.argv.index("--runs") + 1]) if "--runs" in sys.argv else 3000
    basics()
    gold()
    t0, bad = time.time(), 0
    for i in range(runs):
        try:
            sim(i)
        except AssertionError as e:
            bad += 1
            print(f"✗ lauf {i}: {str(e)[:400]}")
            if bad >= 3:
                break
    print(f"{'✓' if not bad else '✗'} collab-simulator: {runs if not bad else i + 1} läufe, {bad} fehler, {time.time() - t0:.1f} s")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
