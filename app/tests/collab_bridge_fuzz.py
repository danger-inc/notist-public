#!/usr/bin/env python3
# Handy-Brücke (api.m_collab_push/pull) im Zufallstest ohne Netz: fremde Änderungen (wie von Live), Eingaben im Editor
# (Kotlin) und Abholen mit/ohne Tipp-Pause beliebig gemischt. Am Ende: Editor == gemeinsamer Stand, kein Wort verloren.
#   python tests/collab_bridge_fuzz.py [--runs 2000]
import os, random, sys, tempfile
APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T = tempfile.mkdtemp(prefix="notist-bridge-")
os.makedirs(os.path.join(T, "h"))
os.environ.update(HOME=os.path.join(T, "h"), NOTES_HOME=os.path.join(T, "notist"), NOTES_NO_TIMERS="1")
os.environ.pop("NOTES_DATA_DIR", None)
sys.path.insert(0, APP)
sys.modules.setdefault("gi", None)
from core import api, collab as C  # noqa: E402


class FakeLive:
    def __init__(self, a, sid, owner, get_doc, apply_remote, post, on_state=None, on_cursors=None, key=None, **kw):
        self.doc = None
        self.get_doc, self.apply_remote, self.ready = get_doc, apply_remote, True
        FakeLive.cur = self
    def start(self): pass
    def close(self): pass
    def cursor(self, i, j=None): pass
    def local_changed(self, cursor=None):
        FakeLive.cur.sent = getattr(FakeLive.cur, "sent", 0) + 1


C.Live = FakeLive


def run(seed):
    rng = random.Random(seed)
    words = []
    def tok(p):
        words.append(f"{p}{len(words)}")
        return " " + words[-1]
    api._CO["sessions"] = [{"id": "s", "key": "notes:x", "status": "active", "owner": "o", "doc_key": "notes:x"}]
    api._CO["live"] = None
    api._CO["conns"] = {}
    kd = {"text": "start", "rich": [], "images": []}            # Editor (Kotlin)
    api._co_acct().set_code("s", "0123-4567-89AB-CDEF-GHJK")
    api.m_collab_bind("notes", "x", dict(kd))
    lv = FakeLive.cur
    rejected = False
    cur = -1                                                     # Cursor wie Kotlin (cursorOffset) – macht den Diff eindeutig
    for _ in range(rng.randint(5, 40)):
        r = 0.99 if rejected else rng.random()                   # Kotlin: nach einer Ablehnung sofort die nächste Runde
        if r < 0.35:                                             # fremde Änderung (Live wendet sie auf local an)
            st = api._CO["live"]
            t = C.text_of(st["local"])[:-1]
            pos = rng.choice([0] + [i for i in range(1, len(t) + 1) if i == len(t) or t[i] == " "])
            d = [{"retain": pos}, {"insert": tok("r")}] if pos else [{"insert": tok("r")}]
            lv.apply_remote(d, C.apply(st["local"], d))
        elif r < 0.75:                                           # Eingabe im Editor + push
            t = kd["text"]
            pos = rng.choice([0] + [i for i in range(1, len(t) + 1) if i == len(t) or t[i] == " "])
            w = tok("k")
            kd["text"] = t[:pos] + w + t[pos:]
            cur = pos + len(w)
            if not rejected:                                     # wie Kotlin: nach Ablehnung zuerst die sync-Runde
                api.m_collab_push(dict(kd), 0, pos + len(w))
        else:                                                    # Runde wie Kotlin: senden + abholen in einem Aufruf
            x = api.m_collab_sync(dict(kd), cur, rng.random() < 0.6, rejected)
            rejected = False
            if x.get("entry"):
                if rng.random() < 0.3:                           # dazwischen getippt → Auslieferung ablehnen
                    t = kd["text"]
                    pos = rng.choice([0] + [i for i in range(1, len(t) + 1) if i == len(t) or t[i] == " "])
                    w = tok("z")
                    kd["text"] = t[:pos] + w + t[pos:]
                    cur = pos + len(w)
                    rejected = True
                else:
                    kd = {"text": x["entry"]["text"], "rich": x["entry"].get("rich") or [], "images": x["entry"].get("images") or []}
    x = api.m_collab_sync(dict(kd), cur, True, rejected)
    if x.get("entry"):
        kd = {"text": x["entry"]["text"]}
    local = C.text_of(api._CO["live"]["local"])[:-1]
    assert kd["text"] == local, f"editor ≠ gemeinsam:\n{kd['text']}\n{local}"
    lost = [w for w in words if w not in local]
    assert not lost, f"verloren: {lost}"


def main():
    runs = int(sys.argv[sys.argv.index("--runs") + 1]) if "--runs" in sys.argv else 2000
    bad = 0
    for i in range(runs):
        try:
            run(i)
        except AssertionError as e:
            bad += 1
            print(f"✗ lauf {i}: {str(e)[:300]}")
            if bad >= 3:
                break
    print(f"{'✓' if not bad else '✗'} collab_bridge_fuzz: {runs if not bad else i + 1} läufe, {bad} fehler")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
