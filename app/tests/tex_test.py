#!/usr/bin/env python3
# LaTeX-/PDF-/Tabellen-/Wörterbuch-Kette (Plan Schritt 16), läuft auf Linux und am Mac (CI):
#   Compiler gefunden → Vorlage „LaTeX lernen“ + ein Haus-Dokument kompilieren → SyncTeX (Zeile↔PDF) → Poppler-Suche
#   CSV → XLSX-Vorschau ohne ssconvert · Wörterbuch findet „Haus“ · Rechtschreibung · SQLite-FTS5 · Tectonic-Archivname
#   python tests/tex_test.py [--no-compile]
import os, shutil, subprocess, sys, tempfile
T = tempfile.mkdtemp(prefix="notist-tex-")
os.environ.update(NOTES_HOME=T, NOTES_DATA_DIR=os.path.join(T, "data"), NOTES_APP_ID="de.test.NotistTex", NOTES_NO_TIMERS="1",
                  XDG_CACHE_HOME=os.path.join(T, "cache"), XDG_CONFIG_HOME=os.path.join(T, "config"))
APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, APP)
FAIL, SKIP = [], []


def check(ok, msg):
    print(("ok   " if ok else "FAIL ") + msg)
    if not ok:
        FAIL.append(msg)


import gi  # noqa: E402
gi.require_version("Gtk", "4.0")
gi.require_version("Poppler", "0.18")
from gi.repository import Poppler, GLib  # noqa: E402
import notes  # noqa: E402,F401 – legt den Suchpfad für glass/vendor an
import latex, latexdata as ld  # noqa: E402
from core import plat, texcore, xlsx, pkgcmds, dictdb  # noqa: E402

# ---- Compiler, Vorlage, SyncTeX, PDF-Suche
comps = latex.find_compilers()
print("Compiler:", [c[0] for c in comps] or "keiner")
if "--no-compile" in sys.argv or not comps:
    SKIP.append("kein Compiler – Kompilieren übersprungen")
else:
    name, exe = comps[0]
    docs = {"haus": "\\documentclass{article}\n\\begin{document}\nEin Haus am See.\n\n\\newpage\nZweite Seite mit Garten.\n\\end{document}\n"}
    tpl = next((t for t in ld.TEMPLATES if t[0] == "lernen"), None)
    if tpl and name != "tectonic":                    # Vorlage braucht babel/Pakete – mit großem TeX meist da, sonst überspringen
        docs["vorlage"] = tpl[4]
    for key, src in docs.items():
        d = os.path.join(T, "b-" + key); os.makedirs(d)
        open(os.path.join(d, "main.tex"), "w", encoding="utf-8").write(src)
        cmd = latex.compile_cmd(name, exe, d, main="main.tex")
        r = subprocess.run(cmd, cwd=d, capture_output=True, timeout=600)
        pdf = os.path.join(d, "main.pdf")
        if key != "haus" and not os.path.exists(pdf):
            SKIP.append(f"Vorlage {key}: Pakete fehlen bei diesem TeX – übersprungen")
            continue
        check(os.path.exists(pdf), f"{name}: {key} kompiliert")
        if key != "haus" or not os.path.exists(pdf):
            continue
        doc = Poppler.Document.new_from_file(GLib.filename_to_uri(pdf), None)
        check(doc.get_n_pages() == 2, "PDF hat 2 Seiten")
        hits = doc.get_page(0).find_text("Haus")
        check(len(hits) == 1, "Poppler findet „Haus“ auf Seite 1")
        check(not doc.get_page(0).find_text("Garten") and doc.get_page(1).find_text("Garten"), "„Garten“ nur auf Seite 2")
        st = os.path.join(d, "main.synctex.gz")
        check(os.path.exists(st), "main.synctex.gz entsteht")
        if os.path.exists(st):
            sx = texcore.SyncTex(st)
            to = sx.to_pdf("main.tex", 3)                      # Zeile 3 = „Ein Haus am See.“
            check(to is not None and to[0] == 0, f"SyncTeX Zeile→PDF: Seite 1 ({to})")
            to2 = sx.to_pdf("main.tex", 6)
            check(to2 is not None and to2[0] == 1, f"SyncTeX Zeile→PDF: Seite 2 ({to2})")
            h = hits[0]
            back = sx.to_source(0, (h.x1 + h.x2) / 2, doc.get_page(0).get_size()[1] - (h.y1 + h.y2) / 2)
            check(back is not None and back[0] == "main.tex" and back[1] == 3, f"SyncTeX PDF→Zeile ({back})")

# ---- Tectonic: Archivname je System/Prozessor
for fake_m, want in (("arm64", "aarch64-apple-darwin"), ("x86_64", "x86_64-apple-darwin")):
    if plat.SYSTEM == "mac" or plat.FAKE:
        check(plat.tectonic_asset(fake_m)[0] == want, f"Tectonic-Archiv {fake_m} → {want}")

# ---- CSV → Tabelle ohne ssconvert
shutil.which = (lambda orig: lambda n, *a, **k: None if n == "ssconvert" else orig(n, *a, **k))(shutil.which)
f = os.path.join(T, "t.csv")
open(f, "w", encoding="utf-8-sig").write('Name;Preis\nÄpfel;1,50\n"Birnen; rot";2.25\n')
info, err = xlsx.store(f)
check(err is None and info and info["nrows"] == 2 + 1 and info["ncols"] == 2, f"CSV-Vorschau ohne ssconvert ({info}, {err})")
rows = xlsx.table_rows(info) if info else []
check(rows[:3] == [["Name", "Preis"], ["Äpfel", "1,5"], ["Birnen; rot", "2,25"]], f"CSV-Zellen richtig ({rows})")
f2 = os.path.join(T, "t2.csv")
open(f2, "wb").write("a,b\nü,2\n".encode("cp1252"))
i2, e2 = xlsx.store(f2)
check(i2 and xlsx.table_rows(i2)[1][0] == "ü", "CSV in cp1252 (Excel) wird gelesen")

# ---- Rechtschreibung, Wörterbuch, FTS5
import spell  # noqa: E402
sp = spell.speller()
if sp.available:
    check(sp.check("Haus"), "Rechtschreibung: „Haus“ richtig")
    check(not sp.check("Hauss"), "Rechtschreibung: „Hauss“ unterstrichen")
else:
    SKIP.append("kein Hunspell-Wörterbuch – Rechtschreibung übersprungen")
import sqlite3  # noqa: E402
try:
    sqlite3.connect(":memory:").execute("CREATE VIRTUAL TABLE t USING fts5(a)")
    check(True, "SQLite FTS5 vorhanden")
except sqlite3.OperationalError:
    check(False, "SQLite FTS5 fehlt (Wörterbuch fällt auf langsame Suche zurück)")
n = dictdb.build(["Haus {n} :: house", "Haustür {f} :: front door", "Garten {m} :: garden"])
from core import api  # noqa: E402
res = api.dict_lookup("Haus")
check(n == 3 and bool(res) and "house" in str(res).lower(), f"Wörterbuch findet „Haus“ ({str(res)[:80]})")
check("garden" in str(api.dict_lookup("garden", "en")).lower(), "Wörterbuch Rückrichtung en→de")

# ---- Cache-Ordner von Tectonic
cd = pkgcmds.cache_dir()
check(isinstance(cd, str) and cd, f"pkgcmds.cache_dir() = {cd}")

for s in SKIP:
    print("skip " + s)
print("\nalle grün" if not FAIL else f"\n{len(FAIL)} Fehler")
sys.exit(1 if FAIL else 0)
