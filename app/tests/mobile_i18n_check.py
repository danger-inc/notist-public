#!/usr/bin/env python3
# Schritt 32: Suchlauf – jeder tr("…")-Schlüssel der Handy-App muss in lang/en.json (PC) oder lang/en-mobile.json (Handy) stehen.
#   python tests/mobile_i18n_check.py     (Quelle: ~/Projects/notist-android/app/src/main/java)
import glob, json, os, re, sys
APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRJ = os.path.expanduser("~/Projects/notist-android")
en = json.load(open(os.path.join(APP, "lang", "en.json"), encoding="utf-8"))
en.update(json.load(open(os.path.join(PRJ, "app/src/main/assets/lang/en-mobile.json"), encoding="utf-8")))
keys = set()
for f in glob.glob(PRJ + "/app/src/main/java/**/*.kt", recursive=True):
    s = open(f, encoding="utf-8").read()
    for m in re.finditer(r'\btr\(\s*"((?:[^"\\]|\\.)*)"', s):
        keys.add(m.group(1).replace('\\"', '"').replace("\\n", "\n").replace("\\\\", "\\"))
for m in re.finditer(r'" to "([^"]+)"', open(PRJ + "/app/src/main/java/de/invincible/notist/A11y.kt", encoding="utf-8").read()):
    keys.add(m.group(1))
# Plan-Anzeigenamen der Formate/Texte, die nicht über tr("…") laufen, werden von Hand gelistet
missing = sorted(k for k in keys if k not in en)
print(f"{len(keys)} Schlüssel, {len(missing)} ohne Englisch")
for k in missing: print("  fehlt:", repr(k))
sys.exit(1 if missing else 0)
