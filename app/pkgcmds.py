# LaTeX-Pakete: was Tectonic anbietet, was schon geladen ist – und welche Befehle ein Paket mitbringt.
# Befehle werden aus den .sty-Dateien gelesen (\def, \newcommand …) und kommen als Rubrik „Pakete“ in Vorschläge
# und Befehlsübersicht. Alles läuft über das lokale Tectonic (`tectonic -X bundle …`) – ohne eigenen Netzzugriff.
import glob
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time

import paths

STORE = os.path.join(paths.HOME, "latex-cmds.json")
CATEGORY = "Pakete"
DEF = re.compile(
    r"^\s*(?:\\(?:newcommand|renewcommand|providecommand|DeclareRobustCommand|newrobustcmd|NewDocumentCommand|"
    r"DeclareDocumentCommand|NewExpandableDocumentCommand|ProvideDocumentCommand)\*?\s*\{?\s*\\|\\(?:long\s*)?"
    r"(?:def|gdef|edef)\s*\\|\\let\s*\\)([A-Za-z]{3,})\b")
_lock = threading.Lock()
_names = None


def cache_roots():
    out = []
    for base in (os.environ.get("XDG_CACHE_HOME"), os.path.expanduser("~/.cache"), os.environ.get("LOCALAPPDATA")):
        for n in ("tectonic", "Tectonic"):
            if base and os.path.isdir(os.path.join(base, n)):
                out.append(os.path.join(base, n))
    return list(dict.fromkeys(out))


def cache_dir():
    """Ordner, in dem Tectonic heruntergeladene Pakete ablegt (fehlt noch, wenn nie etwas geladen wurde)."""
    roots = cache_roots()
    return roots[0] if roots else os.path.join(os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache"),
                                               "tectonic")


def _index_file():
    for r in cache_roots():
        hits = glob.glob(os.path.join(r, "bundles", "data", "*.index"))
        if hits:
            return hits[0]
    return None


def available():
    """{dateiname: größe} aller .sty/.cls im Bundle (aus dem lokalen Index; leer, solange noch nichts geladen wurde)."""
    global _names
    if _names is None:
        out = {}
        p = _index_file()
        if p:
            try:
                with open(p, encoding="utf-8", errors="replace") as f:
                    for line in f:
                        parts = line.rstrip("\n").rsplit(" ", 2)
                        if len(parts) == 3 and parts[0].endswith((".sty", ".cls")):
                            out[parts[0]] = int(parts[2]) if parts[2].isdigit() else 0
            except OSError:
                pass
        _names = out
    return _names


def cached():
    """Dateinamen, die schon lokal liegen (offline nutzbar)."""
    out = set()
    for r in cache_roots():
        for d in glob.glob(os.path.join(r, "bundles", "data", "*")):
            if os.path.isdir(d):
                try:
                    out.update(os.listdir(d))
                except OSError:
                    pass
    return out


def is_cached(pkg):
    names = cached()
    return pkg + ".sty" in names or pkg + ".cls" in names


def cache_size():
    total = 0
    for r in cache_roots():
        for root, _d, files in os.walk(r):
            for f in files:
                try:
                    total += os.path.getsize(os.path.join(root, f))
                except OSError:
                    pass
    return total


def human(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


# ---------------------------------------------------------------- Befehle lesen
def _load():
    try:
        with open(STORE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"pkgs": {}}


def _save(data):
    try:
        os.makedirs(os.path.dirname(STORE), exist_ok=True)
        tmp = STORE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        os.replace(tmp, STORE)
    except OSError:
        pass


def cat(tectonic, name, timeout=90):
    try:
        r = subprocess.run([tectonic, "-X", "bundle", "cat", name], capture_output=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout.decode("utf-8", "replace") if r.returncode == 0 and r.stdout else None


def scan_text(text, pkg):
    """[(befehl, beschreibung)] – öffentliche Befehle (nur Buchstaben), ohne interne und End-Marken."""
    lines = text.splitlines()
    seen, out = set(), []
    for i, line in enumerate(lines):
        if line.lstrip().startswith("%"):
            continue
        m = DEF.match(line)
        if not m:
            continue
        name = m.group(1)
        if name in seen or name.startswith("end") or name.lower().startswith(("tmp", "my")) or name[0].isupper() \
                and name.isupper():
            continue
        seen.add(name)
        desc = ""
        if i and lines[i - 1].lstrip().startswith("%"):
            desc = lines[i - 1].lstrip("% \t").strip()
            if len(desc) < 8 or desc.startswith(("\\", "-", "=", "*")):
                desc = ""
        out.append(("\\" + name, desc[:90] or f"Befehl aus dem Paket {pkg}"))
        if len(out) >= 120:
            break
    return out


def scanned():
    return set(_load().get("pkgs", {}))


def scan_package(tectonic, pkg):
    """Paket lesen und im Verzeichnis ablegen → Anzahl neuer Befehle oder None (nicht lesbar/offline)."""
    text = cat(tectonic, pkg + ".sty") or cat(tectonic, pkg + ".cls")
    if text is None:
        return None
    cmds = scan_text(text, pkg)
    with _lock:
        data = _load()
        data.setdefault("pkgs", {})[pkg] = {"cmds": cmds, "t": int(time.time())}
        _save(data)
    return len(cmds)


def scan_async(tectonic, pkgs, done=None):
    """Mehrere Pakete im Hintergrund lesen; done(anzahl_pakete, anzahl_befehle) im Thread-Ende."""
    def run():
        pk = cm = 0
        for p in pkgs:
            n = scan_package(tectonic, p)
            if n is not None:
                pk += 1
                cm += n
        if done:
            done(pk, cm)
    threading.Thread(target=run, daemon=True).start()


def merge_into(ld):
    """Gelesene Befehle in latexdata.COMMANDS aufnehmen (Rubrik „Pakete“); schon Bekanntes bleibt unberührt."""
    if CATEGORY not in ld.CATEGORIES:
        ld.CATEGORIES.append(CATEGORY)
    known = {c[0] for c in ld.COMMANDS}
    added = 0
    for pkg, info in _load().get("pkgs", {}).items():
        for name, desc in info.get("cmds", []):
            if name in known:
                continue
            known.add(name)
            ld.COMMANDS.append((name, name + " ", desc, CATEGORY, pkg))
            added += 1
    return added


def used_packages(text):
    """Pakete aus den \\usepackage-Zeilen eines Dokuments."""
    out = []
    for m in re.finditer(r"\\usepackage(?:\[[^\]]*\])?\{([^}]*)\}", text):
        out += [p.strip() for p in m.group(1).split(",") if p.strip()]
    return list(dict.fromkeys(out))


# ---------------------------------------------------------------- Paket vorab laden
def preload(tectonic, pkg, timeout=900):
    """Paket samt Abhängigkeiten in den Cache holen (Mini-Dokument kompilieren) → (ok, meldung)."""
    d = tempfile.mkdtemp(prefix="notist-pkg-")
    try:
        with open(os.path.join(d, "main.tex"), "w", encoding="utf-8") as f:
            f.write("\\documentclass{article}\n\\usepackage{%s}\n\\begin{document}\nx\n\\end{document}\n" % pkg)
        try:
            r = subprocess.run([tectonic, "--chatter", "minimal", "--outdir", d, os.path.join(d, "main.tex")],
                               capture_output=True, timeout=timeout, cwd=d)
        except subprocess.TimeoutExpired:
            return False, "Zeitüberschreitung – Internetverbindung prüfen"
        except OSError as e:
            return False, str(e)
        if r.returncode == 0:
            return True, "geladen"
        err = (r.stderr or b"").decode("utf-8", "replace").strip().splitlines()
        msg = next((l for l in err if "error" in l.lower() or "not found" in l.lower()), err[-1] if err else "Fehler")
        return False, msg[:160]
    finally:
        shutil.rmtree(d, ignore_errors=True)
