#!/usr/bin/env python3
# Schritt 29: LaTeX-Editor im Emulator gegen eine echte PC-Instanz (Kompilieren am Rechner). Voraussetzung: Emulator läuft,
# App + Test-APK installiert (siehe mobile_export_check.py), Tectonic am PC.   python tests/mobile_latex_emu.py
import os, subprocess, sys, time
import pwd
REAL = pwd.getpwuid(os.getuid()).pw_dir          # echtes Zuhause (HOME wird in den Tests umgebogen)
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, "mobile_test.py"), encoding="utf-8").read().split("def main")[0]
exec(compile(src, "mobile_test_head", "exec"))
ENV = "source " + REAL + "/.local/share/android-dev/env.sh; "
def sh(c, **k): return subprocess.run(["bash", "-c", ENV + c], capture_output=True, text=True, **k)
xv = subprocess.Popen(["Xvfb", ":97", "-screen", "0", "1280x800x24", "-nolisten", "tcp"], stderr=subprocess.DEVNULL)
time.sleep(1); os.environ.update(DISPLAY=":97", GDK_BACKEND="x11")
PC = None
try:
    port = free_port(); PC = Inst("pc", port)
    os.makedirs(os.path.join(PC.root, "cache"), exist_ok=True)
    for link, target in (("cache/Tectonic", os.path.expanduser("~/.cache/Tectonic")), ("tools", os.path.expanduser("~/.local/share/notes/tools"))):
        if os.path.exists(target) and not os.path.exists(os.path.join(PC.root, link)): os.symlink(target, os.path.join(PC.root, link))
    PC.x("app.handy.start()"); code = PC.x("out = app.handy.start_pairing()[1]")
    sh("adb shell pm grant de.invincible.notist android.permission.ACCESS_LOCAL_NETWORK")
    r = sh(f"adb shell am instrument -w -e class de.invincible.notist.LatexUiTest -e addr 10.0.2.2:{port} -e code {code} de.invincible.notist.test/androidx.test.runner.AndroidJUnitRunner")
    ok = "OK (1 test)" in r.stdout
    print(("✓" if ok else "✗"), "LatexUiTest (Emulator ↔ PC-Instanz, Tectonic/pdfLaTeX am PC)", "" if ok else r.stdout[-1500:])
    sys.exit(0 if ok else 1)
finally:
    if PC: PC.stop()
    xv.terminate()
