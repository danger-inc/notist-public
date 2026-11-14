# GTK-freie Sicherung (Auszug aus backup.py für das Handy – gleiche Formate/Regeln, Schritt 31). Änderungen in backup.py hierher übernehmen.
# Sicherungen: der ganze Datenordner als ZIP, automatisch (Standard: täglich) oder per Knopf.
# Ziel ist frei wählbar – z. B. ein Nextcloud-/Syncthing-/Dropbox-Ordner, dann landet die Sicherung
# automatisch auch in der Cloud. Wiederherstellen legt vorher selbst noch eine Sicherung an.
import datetime, glob, os, shutil, tempfile, threading, zipfile

from core import paths

PREFIX = "notes-sicherung-"


def defaults(prefs):
    b = prefs.setdefault("backup", {})
    b.setdefault("on", True)
    b.setdefault("dir", paths.BACKUPS)
    b.setdefault("hours", 24)
    b.setdefault("keep", 14)
    return b


FILES = "dateien"          # in der ZIP: der notist-Dateiordner (~/Dokumente/notist) – Inhalt steht seit v4.4 dort
BIG = 100 * 1024 * 1024    # einzelne Riesendateien im Dateiordner nicht mitsichern
SUBS = ("notes", "docs", "latex", "latex-files", "history")


def files_dir_of(prefs):
    import linked
    return linked.base_dir(prefs)


def backup_now(dest, keep=14, tag="", files_dir=None):
    """Schreibt die Sicherung und gibt den Pfad zurück (blockierend). files_dir = notist-Dateiordner (kommt
    unter dateien/ mit hinein)."""
    os.makedirs(dest, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    path = os.path.join(dest, f"{PREFIX}{stamp}{'-' + tag if tag else ''}.zip")
    tmp = path + ".part"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        for root, dirs, files in os.walk(paths.DATA):
            for f in files:
                if f.endswith((".tmp", ".part")):
                    continue
                full = os.path.join(root, f)
                z.write(full, os.path.relpath(full, paths.DATA))
        if files_dir and os.path.isdir(files_dir):
            for root, dirs, files in os.walk(files_dir):
                dirs[:] = [d for d in dirs if not d.startswith(".")]
                for f in files:
                    full = os.path.join(root, f)
                    if f.startswith(".") or f.endswith((".tmp", ".part", ".notist-tmp")):
                        continue
                    try:
                        if os.path.getsize(full) > BIG:
                            continue
                        z.write(full, FILES + "/" + os.path.relpath(full, files_dir).replace(os.sep, "/"))
                    except OSError:
                        continue
    os.replace(tmp, path)
    prune(dest, keep)
    return path


def prune(dest, keep):
    auto = [p for p in list_backups(dest) if "-vor-" not in os.path.basename(p)]
    for old in auto[keep:]:
        try:
            os.remove(old)
        except OSError:
            pass


def list_backups(dest):
    """Neueste zuerst."""
    return sorted(glob.glob(os.path.join(dest, PREFIX + "*.zip")), reverse=True)


def describe(path):
    name = os.path.basename(path)[len(PREFIX):-4]
    try:
        d = datetime.datetime.strptime(name[:19], "%Y-%m-%d_%H-%M-%S")
        when = d.strftime("%d.%m.%Y %H:%M")
    except ValueError:
        when = name
    extra = " (vor Wiederherstellung)" if "-vor-" in name else ""
    try:
        with zipfile.ZipFile(path) as z:
            n = sum(1 for i in z.namelist() if i.endswith(".json") and i.split("/")[0] in ("notes", "docs", "latex"))
    except (OSError, zipfile.BadZipFile):
        n = 0
    size = os.path.getsize(path) / 1e6
    return f"{when}{extra}", f"{n} Einträge · {size:.1f} MB".replace(".", ",")


def restore(path, dest, files_dir=None):
    """Ersetzt den Datenordner durch die Sicherung. Vorher wird der aktuelle Stand gesichert.
    Ordnerweise per Umbenennen mit Rückweg: scheitert etwas, kommt der alte Stand zurück. Aus dateien/ werden nur
    fehlende Dateien zurückgeholt (vorhandene schreibt notist danach selbst mit dem zurückgespielten Stand)."""
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        if not any(n.split("/")[0] in ("notes", "docs", "latex") for n in names):
            raise ValueError("Das ist keine notist-Sicherung")
        if any(n.startswith("/") or ".." in n.split("/") for n in names):
            raise ValueError("Ungültige Pfade in der Sicherung")
        safety = backup_now(dest, keep=10 ** 6, tag="vor-wiederherstellung", files_dir=files_dir)
        tmp = tempfile.mkdtemp(dir=os.path.dirname(paths.DATA))
        try:
            z.extractall(tmp)
        except BaseException:
            shutil.rmtree(tmp, ignore_errors=True)
            raise
    old = tempfile.mkdtemp(dir=os.path.dirname(paths.DATA), prefix=".notist-alt-")
    try:
        for sub in SUBS:
            target = os.path.join(paths.DATA, sub)
            if os.path.exists(target):
                os.rename(target, os.path.join(old, sub))
            if os.path.isdir(os.path.join(tmp, sub)):
                os.rename(os.path.join(tmp, sub), target)
    except BaseException:
        for sub in SUBS:                            # Rückweg: alten Stand wieder hinstellen
            back = os.path.join(old, sub)
            if os.path.exists(back):
                target = os.path.join(paths.DATA, sub)
                shutil.rmtree(target, ignore_errors=True)
                os.rename(back, target)
        shutil.rmtree(tmp, ignore_errors=True)
        shutil.rmtree(old, ignore_errors=True)
        raise
    shutil.rmtree(old, ignore_errors=True)
    src = os.path.join(tmp, FILES)
    if files_dir and os.path.isdir(src):
        for root, _dirs, files in os.walk(src):
            for f in files:
                rel = os.path.relpath(os.path.join(root, f), src)
                target = os.path.join(files_dir, rel)
                if not os.path.exists(target):
                    try:
                        os.makedirs(os.path.dirname(target), exist_ok=True)
                        shutil.copy2(os.path.join(root, f), target)
                    except OSError:
                        pass
    for sub in ("pdfs", "sheets"):                 # PDF-/Tabellen-Anhänge: nur fehlende Dateien zurückholen
        src = os.path.join(tmp, sub)
        if os.path.isdir(src):
            os.makedirs(os.path.join(paths.DATA, sub), exist_ok=True)
            for f in os.listdir(src):
                if not os.path.exists(os.path.join(paths.DATA, sub, f)):
                    shutil.copy2(os.path.join(src, f), os.path.join(paths.DATA, sub, f))
    for f in ("words.txt",):
        if os.path.isfile(os.path.join(tmp, f)):
            shutil.copy2(os.path.join(tmp, f), os.path.join(paths.DATA, f))
    shutil.rmtree(tmp, ignore_errors=True)
    return safety


