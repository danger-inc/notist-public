#!/usr/bin/env python3
# Schritt 27: Export am Handy (Emulator) → Dateien holen → am PC öffnen.  Voraussetzung: Emulator läuft, App + Test-APK installiert
# (cd ~/Projects/notist-android; ./gradlew :app:assembleDebug :app:assembleDebugAndroidTest; adb install -r … )
import io, json, os, subprocess, sys, tarfile, tempfile, zipfile
import pwd
REAL = pwd.getpwuid(os.getuid()).pw_dir          # echtes Zuhause (HOME wird in den Tests umgebogen)
APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, APP)
ENV = "source " + REAL + "/.local/share/android-dev/env.sh; "
def sh(c, **k): return subprocess.run(["bash", "-c", ENV + c], capture_output=True, **k)
r = sh("adb shell am instrument -w -e class de.invincible.notist.ExportTest de.invincible.notist.test/androidx.test.runner.AndroidJUnitRunner", text=True)
ok = "OK (1 test)" in r.stdout
print(("✓" if ok else "✗"), "Handy-Test ExportTest", "" if ok else r.stdout[-1200:])
tar = sh("adb exec-out run-as de.invincible.notist tar c -C files export-test").stdout
T = tempfile.mkdtemp(prefix="notist-exp-")
tarfile.open(fileobj=io.BytesIO(tar)).extractall(T)
D = os.path.join(T, "export-test")
os.environ.update(NOTES_HOME=os.path.join(T, "n"), HOME=T, NOTES_NO_TIMERS="1")
from core import docfmt, share, exports  # noqa: E402
res = []
def chk(name, good, info=""):
    res.append(bool(good)); print(f"  {'✓' if good else '✗'} {name}" + (f" – {info}" if info and not good else ""))
need = {"notes": "Zweite Zeile", "docs": "Fließtext mit Umlauten", "latex": "Hallo Tex"}
for key, (_s, name, ext, kinds) in exports.FORMATS.items():
    if key == "pdf": continue
    for kind in kinds:
        p = os.path.join(D, f"{kind}-{key}{ext}")
        if not os.path.exists(p): chk(f"{kind} → {key}: Datei da", False, p); continue
        good = os.path.getsize(p) > 0; info = ""
        try:
            if key in ("txt", "md", "html", "tex"): t = open(p, encoding="utf-8").read(); good = good and need[kind] in t
            elif key in ("docx", "odt"):
                b, title, page = docfmt.import_file_full(p); t = "\n".join("".join(r["text"] for r in x.get("runs", [])) for x in b if x["t"] == "p"); good = good and need[kind] in t; info = t[:60]
            elif key == "rtf": good = good and need[kind].split()[-1].encode() in open(p, "rb").read()
            elif key in ("epub", "zip"): z = zipfile.ZipFile(p); good = good and z.testzip() is None and (key != "zip" or "main.tex" in z.namelist())
        except Exception as e:  # noqa: BLE001
            good, info = False, repr(e)
        chk(f"{kind} → {key} (am PC geöffnet)", good, info)
for kind in ("notes", "docs", "latex"):
    p = os.path.join(D, f"{kind}-notes.notes")
    try: k, n, files = share.read_bundle(p); chk(f"{kind} → .notes (PC liest Bündel)", k == kind and n.get("title"))
    except Exception as e: chk(f"{kind} → .notes", False, repr(e))
print(("✓" if all(res) and ok else "✗"), f"mobile_export_check: {sum(res)}/{len(res)} Dateien am PC in Ordnung")
sys.exit(0 if all(res) and ok else 1)
