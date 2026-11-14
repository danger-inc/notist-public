#!/usr/bin/env python3
# Schritt 31 (Handy-Kern, ohne Gerät): Sicherung PC↔Handy in beide Richtungen, Verlauf-Vergleich, Erinnerungen, Willkommensnotiz.
import datetime, os, shutil, sys, tempfile, zipfile
T = tempfile.mkdtemp(prefix="notist-extra-")
os.environ.update(HOME=os.path.join(T, "h"), NOTES_HOME=os.path.join(T, "n"), NOTES_NO_TIMERS="1")
os.environ.pop("NOTES_DATA_DIR", None)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import api, backupcore, mobile  # noqa: E402
RES = []
def check(name, ok, info=""):
    RES.append(bool(ok)); print(f"  {'✓' if ok else '✗'} {name}" + (f" – {info}" if info and not ok else ""))
r = api.m_start(None)
wid = api.m_welcome("de")
check("Willkommensnotiz beim ersten Start (einmalig)", wid and api.m_welcome("de") is None and api.m_get("notes", wid)["title"] == "Willkommen bei notist")
n = api.m_new("notes"); n.update(title="Verlauf", text="Zeile A\nZeile B"); n = api.m_save("notes", n)
st = mobile.get().app.stores["notes"]
st.snapshot(st.notes[n["id"]], force=True)
n["text"] = "Zeile A\nZeile B geändert\nZeile C"; api.m_save("notes", n)
st.snapshot(st.notes[n["id"]], force=True)
v = api.m_versions("notes", n["id"])
d = api.m_diff("notes", n["id"], v[-1]["name"])
check("Verlauf: Vergleich zeigt + und −", any(t == "+" and "Zeile C" in x for t, x in d) and any(t == "-" and x == "Zeile B" for t, x in d), str(d))
n2 = api.m_version("notes", n["id"], v[-1]["name"])
api.m_save("notes", n2)
check("Verlauf: Wiederherstellen", api.m_get("notes", n["id"])["text"] == "Zeile A\nZeile B")
soon = (datetime.datetime.now() + datetime.timedelta(hours=2)).replace(microsecond=0).isoformat()
api.m_patch("notes", n["id"], {"reminder": soon, "reminder_done": False})
rm = api.m_reminders()
check("Erinnerungen: Eintrag mit Zeit in ms", len(rm) == 1 and rm[0]["id"] == n["id"] and rm[0]["at_ms"] > datetime.datetime.now().timestamp() * 1000)
api.m_reminder_done("notes", n["id"])
check("Erinnerung erledigt", api.m_reminders()[0]["done"] is True)
# Sicherung: Handy → ZIP → am PC (backup.py-Format) lesen
bk = os.path.join(T, "bk")
z = api.m_backup(bk)
names = zipfile.ZipFile(z).namelist()
check("Sicherung enthält notes/ + history/ im PC-Format", any(x.startswith("notes/") for x in names) and any(x.startswith("history/") for x in names), str(names[:5]))
# PC-Format → Handy einspielen: Daten ändern, dann zurückspielen
api.m_trash("notes", n["id"]); api.m_delete("notes", n["id"])
check("Eintrag weg", api.m_get("notes", n["id"]) is None)
safety = api.m_restore_backup(z, os.path.join(T, "safety"))
check("Wiederherstellen: Eintrag + Vorsicherung da", api.m_get("notes", n["id"]) and os.path.exists(safety), str(safety))
check("Index nach Wiederherstellen aktuell", n["id"] in [x["id"] for x in api.m_list("notes", q="Verlauf")])
try:
    open(os.path.join(T, "kaputt.zip"), "wb").write(b"kein zip"); api.m_restore_backup(os.path.join(T, "kaputt.zip"), os.path.join(T, "safety")); ok = False
except Exception:  # noqa: BLE001
    ok = True
check("Fremde/kaputte Datei wird abgelehnt", ok)
# Goldkorpus: PC-Datei → Handy-Speicher (speichern, lesen) → unverändert (Blöcke, Seite, Notizfelder)
import glob, json
n_gold = 0
for f in sorted(glob.glob(os.path.join(os.path.dirname(__file__), "gold", "*.json"))):
    d = json.load(open(f, encoding="utf-8"))
    e = api.m_new("docs"); e.update(title=os.path.basename(f), blocks=d["blocks"], page=d.get("page")); e = api.m_save("docs", e)
    back = api.m_get("docs", e["id"])
    if back["blocks"] != d["blocks"] or back.get("page") != d.get("page"):
        check(f"Gold {os.path.basename(f)} unverändert", False, "")
        break
    nt = d.get("note")
    if nt:
        x = api.m_new("notes"); x.update(**{k: v for k, v in nt.items() if k not in ("id",)}); x = api.m_save("notes", x)
        bx = api.m_get("notes", x["id"])
        if any(bx.get(k) != v for k, v in nt.items() if k not in ("id", "created", "updated", "sync")):
            check(f"Gold-Notiz {os.path.basename(f)} unverändert", False, "")
            break
    n_gold += 1
else:
    check(f"Goldkorpus ({n_gold} Dateien) PC → Handy-Speicher → zurück: Blöcke/Seite/Notizfelder gleich", True)
ok = all(RES); print(f"{'✓' if ok else '✗'} mobile_extra_test: {sum(RES)}/{len(RES)} grün")
if ok: shutil.rmtree(T, ignore_errors=True)
sys.exit(0 if ok else 1)
