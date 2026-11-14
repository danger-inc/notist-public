#!/usr/bin/env python3
# Öffnen/Exportieren am Handy (Plan Schritt 27): core.api.m_import / m_export / m_export_bundle / m_html mit Ersatz-Zuhause.
#   python tests/mobile_io_test.py [-v]
# Jede Formatzeile aus exports.FORMATS (außer PDF = Druckdienst am Handy) wird für jeden erlaubten Bereich geschrieben und
# am PC wieder geöffnet; Texte müssen drinstecken. Danach der Weg zurück: m_import.
import json, os, shutil, sys, tempfile, zipfile
T = tempfile.mkdtemp(prefix="notist-io-")
os.environ.update(HOME=os.path.join(T, "h"), NOTES_HOME=os.path.join(T, "n"), NOTES_NO_TIMERS="1")
os.environ.pop("NOTES_DATA_DIR", None)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import api, docfmt, exports, share  # noqa: E402
RES = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(f"  {'✓' if ok else '✗'} {name}" + (f" – {info}" if info and (not ok or "-v" in sys.argv) else ""))


api.m_start(None)
note = api.m_new("notes"); note.update(title="Notiztitel", text="Erste Zeile mit fett\nZweite Zeile ⚑", rich=[[16, 20, "bold"]], labels=["x"])
note = api.m_save("notes", note)
doc = api.m_new("docs"); doc.update(title="Dokumenttitel", blocks=[
    docfmt.para("Überschrift Eins", style="h1"), docfmt.para("Fließtext mit Umlauten äöü."),
    {"t": "table", "rows": [["A", "B"], ["1", "2"]]}], page={"size": "A4"})
doc = api.m_save("docs", doc)
tex = api.m_new("latex"); tex.update(title="Texprojekt", text="\\documentclass{article}\\begin{document}Hallo Tex\\end{document}")
tex = api.m_save("latex", tex)
os.makedirs(os.path.join(T, "n", "data", "latex-files", tex["id"], "bilder"), exist_ok=True)
open(os.path.join(T, "n", "data", "latex-files", tex["id"], "bilder", "a.txt"), "w").write("anhang")
ents = {"notes": note, "docs": doc, "latex": tex}
needle = {"notes": "Zweite Zeile", "docs": "Fließtext mit Umlauten", "latex": "Hallo Tex"}
out = os.path.join(T, "out"); os.makedirs(out)
for key, (_sym, name, ext, kinds) in exports.FORMATS.items():
    if key == "pdf":
        continue
    for kind in kinds:
        p = os.path.join(out, f"{kind}-{key}{ext}")
        try:
            api.m_export(kind, ents[kind]["id"], key, p)
        except Exception as e:  # noqa: BLE001
            check(f"{kind} → {key}", False, repr(e)); continue
        ok = os.path.getsize(p) > 0
        info = ""
        if key in ("txt", "md", "html", "tex"):
            txt = open(p, encoding="utf-8").read(); ok = ok and needle[kind] in txt; info = txt[:80]
        elif key in ("docx", "odt"):
            blocks, title, page = docfmt.import_file_full(p)
            allt = "\n".join("".join(r["text"] for r in b.get("runs", [])) for b in blocks if b["t"] == "p")
            ok = ok and needle[kind] in allt; info = allt[:80]
        elif key in ("rtf",):
            ok = ok and needle[kind].split()[-1].encode() in open(p, "rb").read()
        elif key in ("epub", "zip"):
            z = zipfile.ZipFile(p); ok = ok and z.testzip() is None
            if key == "zip": ok = ok and "main.tex" in z.namelist() and "bilder/a.txt" in z.namelist(); info = str(z.namelist())
        check(f"{kind} → {key}", ok, info)
# .notes-Bündel + Rückweg
for kind in ents:
    p = os.path.join(out, f"{kind}.notes")
    api.m_export_bundle(kind, ents[kind]["id"], p)
    r = api.m_import(p, os.path.basename(p))
    back = api.m_get(r["kind"], r["id"])
    check(f"{kind} → .notes → importiert (neue Id)", r["id"] != ents[kind]["id"] and r["kind"] == kind and back["title"] == ents[kind]["title"], str(r))
for src, name, kind, tt in (("docs-docx.docx", "d.docx", "docs", "Fließtext"), ("docs-odt.odt", "d.odt", "docs", "Fließtext"), ("docs-html.html", "d.html", "docs", "Fließtext"),
                            ("notes-md.md", "n.md", "notes", "Zweite Zeile"), ("notes-txt.txt", "n.txt", "notes", "Zweite Zeile"), ("latex-tex.tex", "t.tex", "latex", "Hallo Tex")):
    r = api.m_import(os.path.join(out, src), name)
    back = api.m_get(r["kind"], r["id"])
    body = back.get("text") or json.dumps(back.get("blocks"), ensure_ascii=False)
    check(f"{src} → importiert als {kind}", r["kind"] == kind and tt in body, body[:80])
for bad, msg in (("x.rtf", "RTF"), ("x.xyz", "nicht unterstützt")):
    open(os.path.join(out, bad), "w").write("x")
    try:
        api.m_import(os.path.join(out, bad), bad); ok = False
    except ValueError as e:
        ok = msg in str(e)
    check(f"{bad}: verständliche Meldung", ok)
h = api.m_html("docs", doc["id"])
check("Seitenansicht-HTML enthält Text + Tabelle", "Fließtext" in h and "<table" in h, h[:120])
ok = all(RES)
print(f"{'✓' if ok else '✗'} mobile_io_test: {sum(RES)}/{len(RES)} grün")
if ok:
    shutil.rmtree(T, ignore_errors=True)
sys.exit(0 if ok else 1)
