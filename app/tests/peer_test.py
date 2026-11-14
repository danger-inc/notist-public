#!/usr/bin/env python3
# Rechner↔Rechner-Abgleich mit zwei ECHTEN notist-Instanzen (Plan Schritt 10): Xvfb, getrennte Zuhause/Datenordner/Ports.
#   python tests/peer_test.py [-v]      (startet selbst Xvfb, ~1 Min.)
# Prüft: Kopplung per Code (und falscher Code), Abgleich Notiz/Words mit PDF-Block/LaTeX-Projekt in beide Richtungen,
# Konflikt → Kopie, Abbruch mitten im Anhang → Fortsetzen, verknüpfte Dateien bleiben je Gerät eigen, Entfernen,
# feste Adresse (localhost/Name), Wiederfinden nach Adresswechsel (/hello-Suche), Timer-Funktion sync_due.
import json, os, secrets, shutil, socket, subprocess, sys, tempfile, threading, time

HERE = os.path.dirname(os.path.abspath(__file__))
VERBOSE = "-v" in sys.argv
T = tempfile.mkdtemp(prefix="notist-peer-")
RES = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(f"  {'✓' if ok else '✗'} {name}" + (f" – {info}" if info and (VERBOSE or not ok) else ""))


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


class Inst:
    def __init__(self, tag, port):
        self.root = os.path.join(T, tag)
        os.makedirs(self.root)
        self.port, self.n, self.buf = port, 0, {}
        self.p = subprocess.Popen([sys.executable, "-X", "utf8", os.path.join(HERE, "peer_inst.py"), self.root, str(port)],
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=open(os.path.join(T, tag + ".err"), "w"),
                                  text=True, bufsize=1)
        self.lines = []
        threading.Thread(target=self._rd, daemon=True).start()
        self.wait(0, 60)

    def _rd(self):
        for line in self.p.stdout:
            if line.startswith("R "):
                d = json.loads(line[2:])
                self.buf[d["id"]] = d

    def wait(self, i, t=120):
        end = time.time() + t
        while time.time() < end:
            if i in self.buf:
                return self.buf.pop(i)
            time.sleep(0.05)
        raise TimeoutError(f"keine Antwort {i}")

    def x(self, code, t=120):
        self.n += 1
        self.p.stdin.write(json.dumps({"id": self.n, "code": code}) + "\n")
        self.p.stdin.flush()
        r = self.wait(self.n, t)
        if not r["ok"]:
            raise RuntimeError(r["err"])
        return r["out"]

    def stop(self):
        try:
            self.p.stdin.write(json.dumps({"id": 0, "code": "quit"}) + "\n")
            self.p.stdin.flush()
            self.p.wait(10)
        except Exception:  # noqa: BLE001
            self.p.kill()


def snap(i):
    return i.x('''
import json as _j
out = {}
for k, s in app.stores.items():
    for nid, n in s.notes.items():
        if os.path.exists(os.path.join(s.path, nid + ".json")):
            from core import handylink as hl
            out[k + ":" + nid] = hl.content(n)
''')


def mk(i, kind, title, text="", extra=None):
    return i.x(f'''
n = app.stores[{kind!r}].create()
n.update(title={title!r}, text={text!r}, **({extra!r} or {{}}))
n["want_file"] = True
app.stores[{kind!r}].save(n)
app.sync_file(n, {kind!r}, force=True)
out = n["id"]
''')


def sync(i, pid, manual=False):
    """Abgleich im Arbeitsfaden der Instanz, auf das Ende warten; → Fehlertext oder None."""
    i.x(f'''
import threading
app._res = None
def _d(r):
    app._res = ("ERR " + str(r)) if isinstance(r, Exception) else "OK"
app.handy.peers.sync_bg({pid!r}, manual={manual}, done=_d)
''')
    for _ in range(600):
        r = i.x("out = getattr(app, '_res', None)")
        if r:
            return None if r == "OK" else r
        time.sleep(0.2)
    return "Zeitüberschreitung"


def main():
    xv = subprocess.Popen(["Xvfb", ":93", "-screen", "0", "1280x800x24", "-nolisten", "tcp"], stderr=subprocess.DEVNULL)
    time.sleep(1)
    os.environ["DISPLAY"] = ":93"
    os.environ["GDK_BACKEND"] = "x11"
    pa, pb = free_port(), free_port()
    A = B = None
    try:
        A, B = Inst("a", pa), Inst("b", pb)
        # Inhalte auf A: Notiz, Words mit PDF-Block, LaTeX-Projekt mit Bild; auf B eine eigene Notiz
        pdf = secrets.token_bytes(6000)
        A.x(f'''
d = os.path.join(app.stores["docs"].path, "..", "pdfs"); os.makedirs(d, exist_ok=True)
open(os.path.join(d, "abc.pdf"), "wb").write({pdf!r})''')
        na = mk(A, "notes", "von-A", "hallo")
        da = mk(A, "docs", "words-A", "", {"blocks": [{"t": "p", "runs": []}, {"t": "pdf", "file": "abc.pdf"}]})
        la = mk(A, "latex", "tex-A", "\\documentclass{article}\\begin{document}x\\end{document}")
        img = secrets.token_bytes(4000)
        A.x(f'''
from core import handylink as hl
d = hl.AppBackend(app)._projdir("latex:{la}")
os.makedirs(os.path.join(d, "bilder"), exist_ok=True)
open(os.path.join(d, "bilder", "fig.png"), "wb").write({img!r})''')
        nb = mk(B, "notes", "von-B", "zweite")
        A.x("app.handy.start()")
        # Kopplung: falscher Code, danach richtiger (der erste beendet die Kopplung)
        code = A.x("out = app.handy.start_pairing()[1]")
        bad = "".join("A" if c != "A" else "B" for c in code.replace("-", ""))
        e = B.x(f'''
try:
    app.handy.peers.pair("127.0.0.1:{pa}", {bad!r}); out = None
except Exception as e:
    out = str(e)''')
        check("Kopplung: falscher Code abgelehnt", e == "code falsch", e)
        code = A.x("out = app.handy.start_pairing()[1]")
        peer = B.x(f'out = app.handy.peers.pair("127.0.0.1:{pa}", {code.lower()!r})')
        pid = peer["id"]
        dev = A.x("out = list(app.handy.devices.values())")
        check("Kopplung mit Code (andere Schreibweise, mit Bindestrich)", len(dev) == 1 and dev[0].get("kind") == "pc",
              str(dev))
        # erster Abgleich
        err = sync(B, pid, manual=True)
        sa, sb = snap(A), snap(B)
        check("erster Abgleich ohne Fehler", err is None, err)
        check("gleiche Einträge auf beiden (Notiz, Words, LaTeX)", sa == sb and len(sa) >= 4, f"{len(sa)} / {len(sb)}")
        have_pdf = B.x('out = os.path.exists(os.path.join(app.stores["docs"].path, "..", "pdfs", "abc.pdf"))')
        b_pdf = B.x('out = open(os.path.join(app.stores["docs"].path, "..", "pdfs", "abc.pdf"), "rb").read().hex()')
        check("PDF-Block-Datei angekommen", have_pdf and bytes.fromhex(b_pdf) == pdf)
        b_img = B.x(f'''
from core import handylink as hl
p = os.path.join(hl.AppBackend(app)._projdir("latex:{la}"), "bilder", "fig.png")
out = open(p, "rb").read().hex() if os.path.exists(p) else None''')
        check("LaTeX-Projektdatei angekommen", b_img is not None and bytes.fromhex(b_img) == img)
        # verknüpfte Dateien: je Gerät eigene Pfade
        fa = A.x(f'out = app.stores["notes"].notes[{na!r}].get("file")')
        fb = B.x(f'out = app.stores["notes"].notes[{na!r}].get("file")')
        check("verknüpfte Datei: jedes Gerät hat seine eigene im eigenen Ordner",
              bool(fa) and bool(fb) and fa != fb and fa.startswith(A.root) and fb.startswith(B.root) and os.path.exists(fb),
              f"{fa} | {fb}")
        # Rückrichtung: Änderung auf A kommt per Abgleich (B ist Client) an, Änderung auf B geht zu A
        A.x(f'n = app.stores["notes"].notes[{na!r}]; n["text"] = "A-neu"; app.stores["notes"].save(n)')
        B.x(f'n = app.stores["notes"].notes[{nb!r}]; n["text"] = "B-neu"; app.stores["notes"].save(n)')
        err = sync(B, pid)
        ta = A.x(f'out = app.stores["notes"].notes[{nb!r}]["text"]')
        tb = B.x(f'out = app.stores["notes"].notes[{na!r}]["text"]')
        check("Änderungen in beide Richtungen", err is None and ta == "B-neu" and tb == "A-neu", f"{err} {ta} {tb}")
        fbt = B.x(f'out = open(app.stores["notes"].notes[{na!r}]["file"], encoding="utf-8").read()')
        check("verknüpfte Datei am Ziel mit neuem Text neu geschrieben", "A-neu" in fbt, fbt[:80])
        # Konflikt
        A.x(f'n = app.stores["notes"].notes[{na!r}]; n["text"] = "konfl-A"; app.stores["notes"].save(n)')
        B.x(f'n = app.stores["notes"].notes[{na!r}]; n["text"] = "konfl-B"; app.stores["notes"].save(n)')
        err = sync(B, pid)
        sa, sb = snap(A), snap(B)
        cop = [k for k, v in sa.items() if "(konflikt)" in (v.get("title") or "")]
        txt = {v.get("text") for v in sa.values()}
        check("Konflikt → Kopie, beide Texte bleiben, beide gleich",
              err is None and len(cop) == 1 and {"konfl-A", "konfl-B"} <= txt and sa == sb, f"{err} {cop}")
        # Abbruch mitten im Anhang → Fortsetzen
        big = secrets.token_bytes(30000)
        A.x(f'''
from core import handylink as hl, sync2
sync2.CHUNK = 4000
d = hl.AppBackend(app)._projdir("latex:{la}")
open(os.path.join(d, "daten.csv"), "wb").write({big!r})''')
        B.x('''
from core import sync2, handylink as hl
sync2.CHUNK = 4000
app._calls = 0
_orig = hl.client_call
def _cut(peer):
    c = _orig(peer)
    def call(req):
        if req.get("op") == "blob":
            app._calls += 1
            if app._calls == 3:
                raise OSError("Netz weg (Test)")
        return c(req)
    return call
hl.client_call = _cut
app._orig_cc = _orig''')
        err1 = sync(B, pid)
        part = B.x('''
from core import paths
d = os.path.join(paths.DATA, "sync2-teile")
out = sorted((f, os.path.getsize(os.path.join(d, f))) for f in os.listdir(d)) if os.path.isdir(d) else []''')
        B.x("from core import handylink as hl; hl.client_call = app._orig_cc")
        err2 = sync(B, pid)
        got = B.x(f'''
from core import handylink as hl
p = os.path.join(hl.AppBackend(app)._projdir("latex:{la}"), "daten.csv")
out = open(p, "rb").read().hex() if os.path.exists(p) else None''')
        check("Abbruch im Anhang: 1. Lauf scheitert, Teil bleibt liegen", err1 is not None and any(s > 0 for _, s in part),
              f"{err1} {part}")
        check("Fortsetzen: 2. Lauf vollständig", err2 is None and got is not None and bytes.fromhex(got) == big, str(err2))
        # Abgleich von der anderen Seite (A als Client von B) – symmetrisch
        code = B.x("out = app.handy.start_pairing()[1]")
        pidA = A.x(f'out = app.handy.peers.pair("127.0.0.1:{pb}", {code!r})["id"]')
        mk(B, "notes", "nur-B", "x")
        err = sync(A, pidA)
        check("symmetrisch: A als Client von B", err is None and snap(A) == snap(B), str(err))
        # feste Adresse als Name, Wiederfinden nach Adresswechsel
        pr = B.x(f'out = app.handy.peers.peers[{pid!r}]')
        check("feste Adresse bleibt stehen (fixed)", pr["fixed"] is True and pr["host"] == "127.0.0.1")
        B.x(f'p = app.handy.peers.peers[{pid!r}]; p["host"] = "127.0.0.2"; p["fixed"] = False')
        # 127.0.0.2 ist auf Linux Loopback, aber nichts lauscht dort auf diesem Port? (Server bindet 0.0.0.0 → erreichbar)
        B.x(f'p = app.handy.peers.peers[{pid!r}]; p["host"] = "10.255.255.1"; p["port"] = {pa}')   # tot
        B.x("""
from core import peerlink
pl = app.handy.peers
pl.discover = lambda wait=2.0, scan=True: [{"host": "127.0.0.1", "port": %d, "id": app.handy.peers.peers[%r]["me"], "name": "A", "pairing": False}]
pl.interval = lambda: 5
""" % (pa, pid))
        B.x(f'import socket; socket.setdefaulttimeout(3)')
        err = sync(B, pid)
        host = B.x(f'out = app.handy.peers.peers[{pid!r}]["host"]')
        check("Adresswechsel: Gegenstelle über ihre Kennung wiedergefunden", err is None and host == "127.0.0.1", f"{err} {host}")
        # Timer-Funktion: fällig → Abgleich läuft los
        B.x(f'app.handy.peers.last_try[{pid!r}] = 0; app._res = None; app.handy.peers.sync_due(0)')
        time.sleep(3)
        last = B.x(f'out = app.handy.peers.peers[{pid!r}]["last"]')
        check("sync_due stößt Abgleich an", last and time.time() - last < 10)
        # Entfernen + Entkoppeln
        B.x(f'app.handy.peers.remove({pid!r})')
        left = B.x("out = len(app.handy.peers.peers)")
        A.x("app.handy.remove(list(app.handy.devices)[0])")
        check("Entfernen/Entkoppeln", left == 0 and A.x("out = len(app.handy.devices)") == 0)
        gone = sync(B, pid)
        check("entfernte Gegenstelle: kein Abgleich mehr", gone is not None)
        # Einstellungsseite baut sich auf
        ui = B.x("""
import settings
app.open_settings("handy")
w = app._settings_win
w._settings_pump = True
out = type(w).__name__
""")
        check("Einstellungsseite „Geräte“ öffnet ohne Fehler", ui)
    finally:
        for i in (A, B):
            if i:
                i.stop()
        xv.terminate()
    errs = []
    for tag in ("a", "b"):
        try:
            txt = open(os.path.join(T, tag + ".err"), encoding="utf-8").read()
        except OSError:
            continue
        bad = [l for l in txt.splitlines() if ("Traceback" in l or "CRITICAL" in l) ]
        errs += [f"{tag}: {l}" for l in bad]
    check("keine Tracebacks/CRITICALs in den Instanzen", not errs, "; ".join(errs[:5]))
    ok = all(RES)
    print(f"{'✓' if ok else '✗'} peer_test: {sum(RES)}/{len(RES)} grün" + ("" if ok else f"  (Logs: {T})"))
    if ok:
        shutil.rmtree(T, ignore_errors=True)
    sys.exit(0 if ok else 1)


main()
