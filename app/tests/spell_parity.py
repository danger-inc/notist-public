#!/usr/bin/env python3
# Schritt 28: gleiche Eingaben → gleiche Rechtschreib-/Autokorrektur-Ergebnisse am PC (libhunspell via spell.py) und am Handy
# (core/spellmob.py mit spylls). Tabelle aus ~200 Fällen: richtige Wörter, Tippfehler, vertauschte Buchstaben, Großschreibung.
#   python tests/spell_parity.py [-v]   (braucht spylls: pip install spylls oder Pfad in SPYLLS_PATH)
import glob, os, random, sys, tempfile
T = tempfile.mkdtemp(prefix="notist-spell-")
os.environ.update(NOTES_HOME=T, HOME=T, NOTES_NO_TIMERS="1", NOTES_DICT_DIR="/usr/share/hunspell")
for p in os.environ.get("SPYLLS_PATH", "").split(os.pathsep) + glob.glob("/tmp/claude-1000/*/*/scratchpad/sp/lib/python*/site-packages"):
    if p and os.path.isdir(p): sys.path.append(p)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import spell  # noqa: E402
from core import autofix, spellmob  # noqa: E402
pc = spell.speller(); mob = spellmob.get(); mob.set_langs(["de", "en"])
good = "Haus Baum Straße Schreibstift Wörterbuch Computer house tree keyboard Mittwoch Fahrrad Zeitung Übung Käse Mädchen quick brown jumps".split()
base = good + list(autofix.TYPOS)
rnd = random.Random(7)
cases = list(base)
for w in good:
    if len(w) > 4:
        i = rnd.randrange(1, len(w) - 2); cases.append(w[:i + 1][:-1] + w[i + 1] + w[i] + w[i + 2:])     # vertauscht
        cases.append(w.lower()); cases.append(w[0] + w[1:].upper()[:2] + w[3:])
        cases.append(w[:2] + w[3:])                                                                   # Buchstabe fehlt
cases = list(dict.fromkeys(cases))[:220]
diff_known, diff_fix = [], []
for w in cases:
    a, b = bool(pc.known(w)), bool(mob.known(w))
    if a != b: diff_known.append((w, a, b))
    fa = autofix.correction(w, {}, pc); autofix._reverted.clear()
    fb = autofix.correction(w, {}, mob); autofix._reverted.clear()
    if fa != fb: diff_fix.append((w, fa, fb))
n = len(cases)
print(f"{n} Fälle · gleiche Prüfung: {n - len(diff_known)}/{n} · gleiche Autokorrektur: {n - len(diff_fix)}/{n}")
for d in diff_known[:12]: print("  Prüfung ≠", d)
for d in diff_fix[:12]: print("  Korrektur ≠", d)
ok = len(diff_known) <= n * 0.03 and len(diff_fix) <= n * 0.03
print("✓ spell_parity" if ok else "✗ spell_parity")
sys.exit(0 if ok else 1)
