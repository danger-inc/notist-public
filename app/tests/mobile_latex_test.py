#!/usr/bin/env python3
# Schritt 29: LaTeX am Handy – der gekoppelte Rechner baut. core/mobile.py (Handy) gegen EINE echte PC-Instanz unter Xvfb.
#   python tests/mobile_latex_test.py [-v]        (braucht Tectonic am PC: ~/.local/share/notes/tools/tectonic + Paket-Zwischenspeicher)
import os, sys, time, subprocess, base64
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, "mobile_test.py"), encoding="utf-8").read().split("def main")[0]
exec(compile(src, "mobile_test_head", "exec"))


def wait_job(api, t=300):
    end = time.time() + t
    while time.time() < end:
        s = api.m_compile_status()
        if not s.get("running"):
            return s
        time.sleep(0.3)
    return {"err": "Zeitüberschreitung"}


def main3():
    xv = subprocess.Popen(["Xvfb", ":96", "-screen", "0", "1280x800x24", "-nolisten", "tcp"], stderr=subprocess.DEVNULL)
    time.sleep(1)
    os.environ.update(DISPLAY=":96", GDK_BACKEND="x11")
    port = free_port()
    PC = None
    try:
        PC = Inst("pc", port)
        os.makedirs(os.path.join(PC.root, "cache"), exist_ok=True)
        for link, target in (("cache/Tectonic", os.path.expanduser("~/.cache/Tectonic")), ("tools", os.path.expanduser("~/.local/share/notes/tools"))):
            if os.path.exists(target) and not os.path.exists(os.path.join(PC.root, link)):
                os.symlink(target, os.path.join(PC.root, link))
        PC.x("app.handy.start()")
        code = PC.x("out = app.handy.start_pairing()[1]")
        from core import api
        api.m_start(None)
        pid = api.m_pair(f"127.0.0.1:{port}", code)["id"]
        # Projekt mit Bild-Datei am Rechner und am Handy anlegen und abgleichen
        e = api.m_new("latex"); e.update(title="Texprojekt", text="\\documentclass{article}\\begin{document}Hallo\\end{document}"); e = api.m_save("latex", e)
        api.m_tex_add_file(e["id"], "daten/kap1.tex", base64.b64encode(b"Kapitel eins aus Datei.").decode())
        err = wait_sync(api, pid)
        check("Projekt (mit Unterordner-Datei) am Rechner angekommen", err is None and any(f["name"] == "daten/kap1.tex" for f in api.m_tex_files(e["id"])), str(err))
        # 1) gutes Dokument inkl. \input aus der Projektdatei
        good = "\\documentclass{article}\n\\begin{document}\nHallo Welt\\\\\n\\input{daten/kap1}\n\\end{document}\n"
        api.m_compile(e["id"], good)
        s = wait_job(api)
        pdf = os.path.join(mobile.paths.DATA, "pdfs", f"tex-{e['id']}.pdf") if False else None
        from core import mobile as _m
        pdf = os.path.join(_m.paths.DATA, "pdfs", f"tex-{e['id']}.pdf")
        check("Kompilieren: ok, PDF am Handy", s.get("ok") and os.path.exists(pdf) and open(pdf, "rb").read(5) == b"%PDF-", str(s)[:300])
        check("SyncTeX-Daten gemeldet", s.get("synctex") is True, str(s)[:200])
        r = api.m_tex_sync_pdf(e["id"], 4)
        check("Quelle → PDF (Zeile 4)", "page" in r and r["page"] == 0, str(r))
        r2 = api.m_tex_sync_src(e["id"], 0, r.get("x", 100), r.get("y", 100))
        check("PDF → Quelle", r2.get("file") and r2.get("line"), str(r2))
        # 2) Fehler: unbekannter Befehl → deutsche Erklärung + Zeile
        bad = "\\documentclass{article}\n\\begin{document}\nText\n\\gibtesnicht\n\\end{document}\n"
        api.m_compile(e["id"], bad)
        s = wait_job(api)
        probs = [p for p in s.get("problems", []) if p["kind"] == "error"]
        check("Fehler: Unbekannter Befehl, Zeile 4", not s.get("ok") and probs and probs[0]["title"] == "Unbekannter Befehl" and probs[0]["line"] == 4, str(s)[:400])
        # 3) Rechner nicht erreichbar → Auftrag gemerkt
        PC.stop(); PC = None
        api.m_compile(e["id"], good)
        s = wait_job(api)
        check("Ohne Verbindung: Meldung + Auftrag gemerkt", s.get("err") and e["id"] in api.m_compile_status().get("pending", []), str(s)[:300])
        # Helfer: Befehlsvorschläge, Vorlagen
        check("Befehlsvorschläge (\\sec…) + Vorlagen", any(c["name"] == "\\section" for c in api.m_tex_complete("\\sec")) and len(api.m_tex_templates()) >= 5)
    finally:
        if PC:
            PC.stop()
        xv.terminate()
    ok = all(RES)
    print(f"{'✓' if ok else '✗'} mobile_latex_test: {sum(RES)}/{len(RES)} grün" + ("" if ok else f"  (Logs: {T})"))
    sys.exit(0 if ok else 1)


main3()
