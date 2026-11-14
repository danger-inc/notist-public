#!/usr/bin/env python3
# Handy-Speicher + Abgleich (Plan Schritt 20): core/mobile.py (wie im Handy) gegen EINE echte PC-Instanz unter Xvfb.
#   python tests/mobile_test.py [-v]      (~1 Min.)
# Prüft: Migration aus 0.1.0 ohne Verlust, Speichern/Suchen/Papierkorb/Archiv/Ordner/Verlauf, Kopplung (falscher/richtiger
# Code), 3 Bereiche + PDF-Anhang hin und zurück, Abbruch mitten im Anhang → Fortsetzen, Konflikt → Kopie, Gerät entfernen.
import json, os, secrets, shutil, socket, subprocess, sys, tempfile, threading, time

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.dirname(HERE)
VERBOSE = "-v" in sys.argv
T = tempfile.mkdtemp(prefix="notist-mobile-")
RES = []
# das „Handy“ = dieser Prozess, mit eigenem Zuhause
MH = os.path.join(T, "handy")
os.makedirs(os.path.join(MH, "h"))
os.environ.update(HOME=os.path.join(MH, "h"), NOTES_HOME=os.path.join(MH, "notist"), NOTES_NO_TIMERS="1")
os.environ.pop("NOTES_DATA_DIR", None)
sys.path.insert(0, APP)
OLD = os.path.join(MH, "files-data")           # 0.1.0: files/data


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


def pc_snap(pc):
    return pc.x('''
from core import handylink as hl
out = {}
for k, s in app.stores.items():
    for nid, n in s.notes.items():
        if os.path.exists(os.path.join(s.path, nid + ".json")):
            out[k + ":" + nid] = hl.content(n)
''')


def pc_mk(pc, kind, title, text="", extra=None):
    return pc.x(f'''
n = app.stores[{kind!r}].create()
n.update(title={title!r}, text={text!r}, **({extra!r} or {{}}))
n["want_file"] = True
app.stores[{kind!r}].save(n)
app.sync_file(n, {kind!r}, force=True)
out = n["id"]
''')


def wait_sync(api, pid=None, t=120):
    """Abgleich anstoßen und auf das Ende warten → Fehlertext oder None."""
    api.m_sync_start(pid)
    end = time.time() + t
    while time.time() < end:
        s = api.m_sync_status()
        if not s["running"]:
            return s["err"]
        time.sleep(0.1)
    return "Zeitüberschreitung"


def mob_snap(api):
    from core import handylink as hl, mobile
    m = mobile.get()
    out = {}
    for k in mobile.KINDS:
        for nid, n in m.app.stores[k].notes.items():
            if os.path.exists(os.path.join(m.app.stores[k].path, nid + ".json")):
                out[f"{k}:{nid}"] = hl.content(n)
    return out


def main():
    xv = subprocess.Popen(["Xvfb", ":94", "-screen", "0", "1280x800x24", "-nolisten", "tcp"], stderr=subprocess.DEVNULL)
    time.sleep(1)
    env0 = dict(os.environ)
    os.environ["DISPLAY"] = ":94"
    os.environ["GDK_BACKEND"] = "x11"
    pa = free_port()
    PC = None
    try:
        # ---- Migration aus 0.1.0 ----
        for k in ("notes", "docs"):
            os.makedirs(os.path.join(OLD, k))
        old = {"notes": [], "docs": []}
        for i in range(3):
            nid = f"old-note-{i}"
            n = {"id": nid, "type": "text", "title": f"alt {i}", "text": f"Text ä ö ü {i}", "pinned": i == 0, "labels": ["uni"],
                 "created": "2026-01-01T10:00:00+00:00", "updated": "2026-01-0%dT10:00:00+00:00" % (i + 1),
                 "trashed": i == 2, "archived": False, "color": "default", "rich": []}
            json.dump(n, open(os.path.join(OLD, "notes", nid + ".json"), "w", encoding="utf-8"), ensure_ascii=False)
            old["notes"].append(nid)
        d = {"id": "old-doc-0", "title": "altes Words", "blocks": [{"t": "p", "runs": [{"text": "Hallo Welt"}]}],
             "created": "2026-01-01T10:00:00+00:00", "updated": "2026-01-05T10:00:00+00:00", "labels": [], "folder": "Uni/Mathe"}
        json.dump(d, open(os.path.join(OLD, "docs", "old-doc-0.json"), "w", encoding="utf-8"))
        open(os.path.join(OLD, "notes", "kaputt.json"), "w").write("{nicht json")
        json.dump({"revs": {}, "gone": [], "folders": {"notes": ["Leer"]}}, open(os.path.join(OLD, "sync.json"), "w"))
        from core import api
        r = api.m_start(OLD)
        check("Migration: alle Einträge übernommen, Kaputtes gezählt",
              r["migrated"] and r["migrated"]["notes"] == 3 and r["migrated"]["docs"] == 1 and r["migrated"]["skipped"] == 1,
              str(r))
        check("Migration: alte Dateien bleiben (data-0.1.0)", os.path.isdir(OLD + "-0.1.0") and not os.path.exists(OLD))
        check("Migration: zweiter Start tut nichts", api.m_start(OLD + "-0.1.0")["migrated"] is None)
        lst = api.m_list("notes")
        check("Liste: angeheftete zuerst, Papierkorb getrennt",
              [e["id"] for e in lst] == ["old-note-0", "old-note-1"] and len(api.m_list("notes", "papierkorb")) == 1, str(lst))
        check("Ordnerliste aus 0.1.0 + Ordner eines Eintrags", "Leer" in api.m_folders("notes") and
              {"Uni", "Uni/Mathe"} <= set(api.m_folders("docs")), str(api.m_folders("docs")))
        n_ = api.m_rename_folder("docs", "Uni", "Studium")
        check("Ordner umbenennen: Unterordner + Einträge folgen", n_ == 1 and api.m_get("docs", "old-doc-0")["folder"] == "Studium/Mathe"
              and "Studium/Mathe" in api.m_folders("docs") and "Uni" not in api.m_folders("docs"), str(api.m_folders("docs")))
        api.m_rename_folder("docs", "Studium", "Uni")
        check("Ordner auflösen: Einträge ohne Ordner", api.m_delete_folder("docs", "Uni") == 1 and api.m_get("docs", "old-doc-0")["folder"] == "Mathe")
        api.m_rename_folder("docs", "Mathe", "Uni/Mathe")
        # ---- Speichern, Suchen, Verlauf ----
        e = api.m_new("notes")
        e.update(title="Einkauf", text="Milch und Brot", labels=["haushalt"])
        e = api.m_save("notes", e)
        check("Speichern + Volltextsuche (Teilwort)", [x["id"] for x in api.m_list("notes", q="brot")] == [e["id"]])
        check("Suche mit Umlaut (ohne Akzent-Unterschied)", {"old-note-0", "old-note-1"} <= {x["id"] for x in api.m_list("notes", q="ü")}, str([x["id"] for x in api.m_list("notes", q="ü")]))
        check("Suche nach Wortanfang", e["id"] in [x["id"] for x in api.m_list("notes", q="mil")])
        check("Schlagwort-Suche #", [x["id"] for x in api.m_list("notes", q="#haus")] == [e["id"]])
        e["text"] = "Milch, Brot und Käse"
        api.m_save("notes", e)
        check("Volltext nach Änderung aktuell", [x["id"] for x in api.m_list("notes", q="käse")] == [e["id"]])
        api.m_patch("notes", e["id"], {"archived": True})
        check("Archiv", e["id"] not in [x["id"] for x in api.m_list("notes")] and
              e["id"] in [x["id"] for x in api.m_list("notes", "archiv")])
        api.m_patch("notes", e["id"], {"archived": False})
        api.m_trash("notes", e["id"])
        check("Papierkorb", e["id"] in [x["id"] for x in api.m_list("notes", "papierkorb")])
        api.m_restore("notes", e["id"])
        check("Wiederherstellen", e["id"] in [x["id"] for x in api.m_list("notes")])
        from core import mobile
        st = mobile.get().app.stores["notes"]
        st.snapshot(st.notes[e["id"]], force=True)
        check("Verlauf: Versionen lesbar", len(api.m_versions("notes", e["id"])) >= 1 and
              api.m_version("notes", e["id"], api.m_versions("notes", e["id"])[0]["name"])["id"] == e["id"])
        # ---- PC-Instanz ----
        PC = Inst("pc", pa)
        pdf = secrets.token_bytes(6000)
        PC.x(f'''
d = os.path.join(app.stores["docs"].path, "..", "pdfs"); os.makedirs(d, exist_ok=True)
open(os.path.join(d, "abc.pdf"), "wb").write({pdf!r})''')
        pn = pc_mk(PC, "notes", "vom-PC", "hallo")
        pd = pc_mk(PC, "docs", "words-PC", "", {"blocks": [{"t": "p", "runs": []}, {"t": "pdf", "file": "abc.pdf"}]})
        pl = pc_mk(PC, "latex", "tex-PC", "\\documentclass{article}\\begin{document}x\\end{document}")
        PC.x("app.handy.start()")
        code = PC.x("out = app.handy.start_pairing()[1]")
        bad = "".join("A" if c != "A" else "B" for c in code.replace("-", ""))
        try:
            api.m_pair(f"127.0.0.1:{pa}", bad)
            err = None
        except Exception as ex:  # noqa: BLE001
            err = str(ex)
        check("Kopplung: falscher Code abgelehnt", err == "code falsch", err)
        code = PC.x("out = app.handy.start_pairing()[1]")
        peer = api.m_pair(f"127.0.0.1:{pa}", code.lower())
        pid = peer["id"]
        check("Kopplung mit Code, Gerät steht in der Liste", [p["id"] for p in api.m_peers()] == [pid], str(api.m_peers()))
        # ---- erster Abgleich ----
        err = wait_sync(api, pid)
        sm, sp = mob_snap(api), pc_snap(PC)
        check("erster Abgleich ohne Fehler", err is None, err)
        check("gleiche Einträge auf beiden (3 Bereiche + Migriertes)", sm == sp and len(sm) >= 8, f"{len(sm)} / {len(sp)}")
        pdf_m = os.path.join(mobile.paths.DATA, "pdfs", "abc.pdf")
        check("PDF-Anhang am Handy angekommen", os.path.exists(pdf_m) and open(pdf_m, "rb").read() == pdf)
        check("Liste/Index zeigt PC-Einträge", {"vom-PC", "words-PC", "tex-PC"} <=
              {x["title"] for k in mobile.KINDS for x in api.m_list(k)})
        check("PC bekommt die Handy-Einträge (Notiz mit Umlauten + migriertes Words)",
              any(v.get("title") == "Einkauf" for v in sp.values()) and any(v.get("title") == "altes Words" for v in sp.values()))
        # ---- Handy → PC mit PDF-Anhang ----
        os.makedirs(os.path.join(mobile.paths.DATA, "pdfs"), exist_ok=True)
        pdf2 = secrets.token_bytes(9000)
        open(os.path.join(mobile.paths.DATA, "pdfs", "vomhandy.pdf"), "wb").write(pdf2)
        dd = api.m_new("docs")
        dd.update(title="Handy-Words", blocks=[{"t": "p", "runs": [{"text": "x"}]}, {"t": "pdf", "file": "vomhandy.pdf"}])
        api.m_save("docs", dd)
        err = wait_sync(api, pid)
        got = PC.x('out = open(os.path.join(app.stores["docs"].path, "..", "pdfs", "vomhandy.pdf"), "rb").read().hex() '
                   'if os.path.exists(os.path.join(app.stores["docs"].path, "..", "pdfs", "vomhandy.pdf")) else None')
        check("Anhang Handy → PC", err is None and got is not None and bytes.fromhex(got) == pdf2, str(err))
        # ---- Änderung in beide Richtungen ----
        e = api.m_get("notes", pn) or {}
        e["text"] = "Handy-neu"
        api.m_save("notes", e)
        PC.x(f'n = app.stores["notes"].notes[{api.m_list("notes", q="Einkauf")[0]["id"]!r}]; n["text"] = "PC-neu"; app.stores["notes"].save(n)')
        err = wait_sync(api, pid)
        check("Änderungen in beide Richtungen", err is None and
              PC.x(f'out = app.stores["notes"].notes[{pn!r}]["text"]') == "Handy-neu" and
              api.m_get("notes", api.m_list("notes", q="Einkauf")[0]["id"])["text"] == "PC-neu")
        # ---- Konflikt ----
        e = api.m_get("notes", pn)
        e["text"] = "konfl-handy"
        api.m_save("notes", e)
        PC.x(f'n = app.stores["notes"].notes[{pn!r}]; n["text"] = "konfl-pc"; app.stores["notes"].save(n)')
        err = wait_sync(api, pid)
        sm, sp = mob_snap(api), pc_snap(PC)
        cop = [k for k, v in sm.items() if "(konflikt)" in (v.get("title") or "")]
        texts = {v.get("text") for v in sm.values()}
        check("Konflikt → Kopie, beide Texte bleiben, beide gleich",
              err is None and len(cop) == 1 and {"konfl-handy", "konfl-pc"} <= texts and sm == sp, f"{err} {cop}")
        # ---- Abbruch mitten im Anhang → Fortsetzen ----
        big = secrets.token_bytes(30000)
        PC.x(f'''
from core import handylink as hl, sync2
sync2.CHUNK = 4000
d = hl.AppBackend(app)._projdir("latex:{pl}")
open(os.path.join(d, "daten.csv"), "wb").write({big!r})''')
        from core import sync2
        sync2.CHUNK = 4000
        orig = hl_cc = mobile.hl.client_call
        cnt = {"n": 0}

        def cut(peer):
            c = orig(peer)

            def call(req):
                if req.get("op") == "blob":
                    cnt["n"] += 1
                    if cnt["n"] == 3:
                        raise OSError("Netz weg (Test)")
                return c(req)
            return call
        mobile.hl.client_call = cut
        err1 = wait_sync(api, pid)
        d = os.path.join(mobile.paths.DATA, "sync2-teile")
        part = sorted((f, os.path.getsize(os.path.join(d, f))) for f in os.listdir(d)) if os.path.isdir(d) else []
        mobile.hl.client_call = orig
        err2 = wait_sync(api, pid)
        dest = os.path.join(mobile.paths.DATA, "latex-files", pl, "daten.csv")
        check("Abbruch im Anhang: 1. Lauf scheitert, Teil bleibt liegen", err1 is not None and any(s > 0 for _, s in part), f"{err1} {part}")
        check("Fortsetzen: 2. Lauf vollständig", err2 is None and os.path.exists(dest) and open(dest, "rb").read() == big, str(err2))
        # ---- Löschen am PC kommt an; Entkoppeln ----
        PC.x(f'app.stores["notes"].delete_forever(app.stores["notes"].notes[{pn!r}])')
        err = wait_sync(api, pid)
        check("Endgültiges Löschen am PC → Handy", err is None and api.m_get("notes", pn) is None and
              pn not in [x["id"] for x in api.m_list("notes")], str(err))
        api.m_unpair(pid)
        check("Gerät entfernen", api.m_peers() == [])
        try:
            api.m_sync_start()
            e2 = None
        except RuntimeError as ex:
            e2 = str(ex)
        check("ohne Gerät kein Abgleich", e2 is not None)
    finally:
        if PC:
            PC.stop()
        xv.terminate()
    errs = []
    try:
        txt = open(os.path.join(T, "pc.err"), encoding="utf-8").read()
        errs = [l for l in txt.splitlines() if "Traceback" in l or "CRITICAL" in l]
    except OSError:
        pass
    check("keine Tracebacks/CRITICALs in der PC-Instanz", not errs, "; ".join(errs[:5]))
    ok = all(RES)
    print(f"{'✓' if ok else '✗'} mobile_test: {sum(RES)}/{len(RES)} grün" + ("" if ok else f"  (Logs: {T})"))
    if ok:
        shutil.rmtree(T, ignore_errors=True)
    sys.exit(0 if ok else 1)


main()
