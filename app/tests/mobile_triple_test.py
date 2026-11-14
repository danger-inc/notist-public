#!/usr/bin/env python3
# Schritt 34: Dreier-Test – zwei echte PC-Instanzen (A = „PC“, B = „Mac“, gleiche Python-Anwendung) und das Handy (Kern):
# gleichzeitig bearbeiten, Konflikte, Löschen, Anhang – nach dem Abgleich in beliebiger Reihenfolge haben alle drei dasselbe.
import os, secrets, subprocess, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, "mobile_test.py"), encoding="utf-8").read().split("def main")[0]
exec(compile(src, "mobile_test_head", "exec"))


def b_sync(B, pid):
    B.x(f'''
import threading
app._res = None
def _d(r): app._res = ("ERR " + str(r)) if isinstance(r, Exception) else "OK"
app.handy.peers.sync_bg({pid!r}, manual=False, done=_d)''')
    for _ in range(600):
        r = B.x("out = getattr(app, '_res', None)")
        if r:
            return None if r == "OK" else r
        time.sleep(0.2)
    return "Zeitüberschreitung"


def main5():
    xv = subprocess.Popen(["Xvfb", ":99", "-screen", "0", "1280x800x24", "-nolisten", "tcp"], stderr=subprocess.DEVNULL)
    time.sleep(1); os.environ.update(DISPLAY=":99", GDK_BACKEND="x11")
    pa, pb = free_port(), free_port(); A = B = None
    try:
        A, B = Inst("a", pa), Inst("b", pb)
        for i in (A, B): i.x("app.handy.start()")
        from core import api
        api.m_start(None)
        # Kopplungen: Handy→A, Handy→B, B→A
        ca = A.x("out = app.handy.start_pairing()[1]"); pidA = api.m_pair(f"127.0.0.1:{pa}", ca)["id"]
        cb = B.x("out = app.handy.start_pairing()[1]"); pidB = api.m_pair(f"127.0.0.1:{pb}", cb)["id"]
        ca = A.x("out = app.handy.start_pairing()[1]"); pidBA = B.x(f'out = app.handy.peers.pair("127.0.0.1:{pa}", {ca!r})["id"]')
        def all_sync():
            e1 = wait_sync(api, pidA); e2 = wait_sync(api, pidB); e3 = b_sync(B, pidBA)
            return e1 or e2 or e3
        # Ausgang: ein gemeinsamer Eintrag + PDF-Anhang am PC
        pdf = secrets.token_bytes(8000)
        A.x(f'''
d = os.path.join(app.stores["docs"].path, "..", "pdfs"); os.makedirs(d, exist_ok=True)
open(os.path.join(d, "t.pdf"), "wb").write({pdf!r})''')
        na = pc_mk(A, "notes", "gemeinsam", "start")
        da = pc_mk(A, "docs", "mit-pdf", "", {"blocks": [{"t": "p", "style": "normal", "align": "left", "indent": 0, "list": None, "spacing": 1.15, "runs": []}, {"t": "pdf", "file": "t.pdf"}]})
        err = all_sync() or all_sync()
        check("Erstabgleich über alle drei", err is None, str(err))
        sa, sb, sm = pc_snap(A), pc_snap(B), mob_snap(api)
        check("A = B = Handy nach dem Erstabgleich", sa == sb == sm and len(sa) >= 3, f"{len(sa)} {len(sb)} {len(sm)}")
        pdf_m = os.path.join(mobile_paths(), "pdfs", "t.pdf")
        check("PDF-Anhang liegt auf B und am Handy", os.path.exists(pdf_m) and open(pdf_m, "rb").read() == pdf and
              B.x('out = os.path.exists(os.path.join(app.stores["docs"].path, "..", "pdfs", "t.pdf"))'))
        # gleichzeitig verschieden bearbeiten (derselbe Eintrag) + Neues + Löschen
        A.x(f'n = app.stores["notes"].notes[{na!r}]; n["text"] = "von A"; app.stores["notes"].save(n)')
        B.x(f'n = app.stores["notes"].notes[{na!r}]; n["text"] = "von B"; app.stores["notes"].save(n)')
        e = api.m_get("notes", na); e["text"] = "vom Handy"; api.m_save("notes", e)
        pc_mk(A, "notes", "nur-A", "a"); pc_mk(B, "notes", "nur-B", "b")
        x = api.m_new("notes"); x.update(title="nur-Handy", text="h"); api.m_save("notes", x)
        B.x(f'app.stores["docs"].trash(app.stores["docs"].notes[{da!r}])')
        err = None
        for _ in range(4): err = all_sync() or err
        sa, sb, sm = pc_snap(A), pc_snap(B), mob_snap(api)
        check("nach Konflikten/Löschen: alle drei gleich", sa == sb == sm, f"A {len(sa)} B {len(sb)} H {len(sm)} {err}")
        texts = {v.get("text") for v in sm.values()}
        check("keine der drei gleichzeitigen Fassungen ging verloren", {"von A", "von B", "vom Handy"} <= texts, str(sorted(t for t in texts if t)[:8]))
        check("Eintrag im Papierkorb bei allen", all(s[f"docs:{da}"].get("trashed") for s in (sa, sb, sm)))
        check("Neues von jedem Gerät bei allen", all({"nur-A", "nur-B", "nur-Handy"} <= {v.get("title") for v in s.values()} for s in (sa, sb, sm)))
    finally:
        for i in (A, B):
            if i: i.stop()
        xv.terminate()
    ok = all(RES)
    print(f"{'✓' if ok else '✗'} mobile_triple_test: {sum(RES)}/{len(RES)} grün" + ("" if ok else f"  (Logs: {T})"))
    sys.exit(0 if ok else 1)


def mobile_paths():
    from core import paths
    return paths.DATA


main5()
