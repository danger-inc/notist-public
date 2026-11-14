#!/usr/bin/env python3
# Handy-App im Emulator gegen eine echte PC-Instanz (Plan Schritt 20). Voraussetzung: Emulator läuft (adb devices),
# Gradle-Projekt ~/Projects/notist-android. Ablauf: Hin/Zurück mit PDF-Anhang, 20-MB-Anhang mit Flugmodus mittendrin
# (Fortsetzen), Entkoppeln.   python tests/mobile_emu.py
import hashlib, os, re, secrets, subprocess, sys, time
import pwd
REAL = pwd.getpwuid(os.getuid()).pw_dir          # echtes Zuhause (HOME wird in den Tests umgebogen)
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, "mobile_test.py"), encoding="utf-8").read().split("def main")[0]
exec(compile(src, "mobile_test_head", "exec"))
ENV = ["bash", "-c"]
PRJ = REAL + "/Projects/notist-android"
PKG = "de.invincible.notist.core.test"


def sh(cmd, **k):
    return subprocess.run(["bash", "-c", "source " + REAL + "/.local/share/android-dev/env.sh; " + cmd], capture_output=True, text=True, **k)


def instr(test, **args):
    a = " ".join(f"-e {k} {v}" for k, v in args.items())
    return sh(f"adb shell am instrument -w -e class de.invincible.notist.core.SyncTest#{test} {a} {PKG}/androidx.test.runner.AndroidJUnitRunner")


def ok(r):
    return "OK (1 test)" in r.stdout


def main2():
    xv = subprocess.Popen(["Xvfb", ":95", "-screen", "0", "1280x800x24", "-nolisten", "tcp"], stderr=subprocess.DEVNULL)
    time.sleep(1)
    os.environ.update(DISPLAY=":95", GDK_BACKEND="x11")
    port = free_port()
    PC = None
    try:
        apk = ["core-debug-androidTest.apk"]      # vorher: ./gradlew :core:assembleDebugAndroidTest
        sh("adb uninstall " + PKG)
        r = sh(f"adb install -r {PRJ}/core/build/outputs/apk/androidTest/debug/{apk[0]}")
        sh(f"adb shell pm grant {PKG} android.permission.ACCESS_LOCAL_NETWORK")
        check("Test-App installiert", "Success" in r.stdout, r.stdout + r.stderr)
        PC = Inst("pc", port)
        pdf = secrets.token_bytes(6000)
        PC.x(f'''
d = os.path.join(app.stores["docs"].path, "..", "pdfs"); os.makedirs(d, exist_ok=True)
open(os.path.join(d, "abc.pdf"), "wb").write({pdf!r})''')
        pc_mk(PC, "notes", "vom-PC", "hallo")
        pc_mk(PC, "docs", "vom-PC-words", "", {"blocks": [{"t": "p", "runs": []}, {"t": "pdf", "file": "abc.pdf"}]})
        pl = pc_mk(PC, "latex", "vom-PC-tex", "\\documentclass{article}\\begin{document}x\\end{document}")
        PC.x("app.handy.start()")
        code = PC.x("out = app.handy.start_pairing()[1]")
        r = instr("pairAndSync", addr=f"10.0.2.2:{port}", code=code, pdfsize=len(pdf))
        check("Handy: koppeln + abgleichen + Einträge/PDF da", ok(r), r.stdout[-1500:])
        sp = pc_snap(PC)
        check("PC hat Notiz mit Umlauten + Words vom Handy", any(v.get("text") == "Grüße ä ö ü" for v in sp.values()) and
              any(v.get("title") == "Handy-Words" for v in sp.values()))
        got = PC.x('p = os.path.join(app.stores["docs"].path, "..", "pdfs", "vomhandy.pdf"); out = os.path.getsize(p) if os.path.exists(p) else None')
        check("PDF-Anhang Handy → PC", got == 9000, str(got))
        # großer Anhang, Flugmodus mittendrin
        big = secrets.token_bytes(24 * 1024 * 1024)
        PC.x(f'''
from core import handylink as hl, sync2
sync2.CHUNK = 65536
d = hl.AppBackend(app)._projdir("latex:{pl}")
open(os.path.join(d, "gross.bin"), "wb").write(bytes.fromhex({big.hex()!r}))''', 300)
        p = subprocess.Popen(["bash", "-c", "source " + REAL + "/.local/share/android-dev/env.sh; adb shell am instrument -w -e class "
                              f"de.invincible.notist.core.SyncTest#bigStart {PKG}/androidx.test.runner.AndroidJUnitRunner"],
                             stdout=subprocess.PIPE, text=True)
        part = 0
        for _ in range(200):
            r = sh(f"adb shell run-as {PKG} ls -l files/notist/data/sync2-teile")
            m = re.findall(r"\s(\d+)\s\d{4}-\d\d-\d\d", r.stdout)
            part = max([int(x) for x in m] or [0])
            if part > 300000:
                break
            time.sleep(0.15)
        sh("adb shell cmd connectivity airplane-mode enable")
        out, _ = p.communicate(timeout=300)
        sh("adb shell cmd connectivity airplane-mode disable")
        time.sleep(6)
        check("Flugmodus mitten im Anhang: Teil bleibt liegen", 300000 < part < len(big), f"part={part}")
        r = instr("bigFinish", addr="x", size=len(big), sha=hashlib.sha256(big).hexdigest())
        check("danach: Fortsetzen, Datei vollständig und identisch", ok(r), r.stdout[-1500:])
        r = instr("unpair")
        check("Entkoppeln", ok(r), r.stdout[-800:])
    finally:
        sh("adb shell cmd connectivity airplane-mode disable")
        if PC:
            PC.stop()
        xv.terminate()
    allok = all(RES)
    print(f"{'✓' if allok else '✗'} mobile_emu: {sum(RES)}/{len(RES)} grün" + ("" if allok else f"  (Logs: {T})"))
    sys.exit(0 if allok else 1)


main2()
