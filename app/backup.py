# Sicherungen: der ganze Datenordner als ZIP, automatisch (Standard: täglich) oder per Knopf.
# Ziel ist frei wählbar – z. B. ein Nextcloud-/Syncthing-/Dropbox-Ordner, dann landet die Sicherung
# automatisch auch in der Cloud. Wiederherstellen legt vorher selbst noch eine Sicherung an.
import datetime, glob, os, shutil, tempfile, threading, zipfile

from gi.repository import GLib

import paths

PREFIX = "notes-sicherung-"


def defaults(prefs):
    b = prefs.setdefault("backup", {})
    b.setdefault("on", True)
    b.setdefault("dir", paths.BACKUPS)
    b.setdefault("hours", 24)
    b.setdefault("keep", 14)
    return b


def backup_now(dest, keep=14, tag=""):
    """Schreibt die Sicherung und gibt den Pfad zurück (blockierend)."""
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


def restore(path, dest):
    """Ersetzt den Datenordner durch die Sicherung. Vorher wird der aktuelle Stand gesichert."""
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        if not any(n.split("/")[0] in ("notes", "docs", "latex") for n in names):
            raise ValueError("Das ist keine notist-Sicherung")
        if any(n.startswith("/") or ".." in n.split("/") for n in names):
            raise ValueError("Ungültige Pfade in der Sicherung")
        safety = backup_now(dest, keep=10 ** 6, tag="vor-wiederherstellung")
        tmp = tempfile.mkdtemp(dir=os.path.dirname(paths.DATA))
        z.extractall(tmp)
    for sub in ("notes", "docs", "latex", "latex-files", "history"):
        target = os.path.join(paths.DATA, sub)
        shutil.rmtree(target, ignore_errors=True)
        if os.path.isdir(os.path.join(tmp, sub)):
            shutil.move(os.path.join(tmp, sub), target)
    for f in ("words.txt",):
        if os.path.isfile(os.path.join(tmp, f)):
            shutil.copy2(os.path.join(tmp, f), os.path.join(paths.DATA, f))
    shutil.rmtree(tmp, ignore_errors=True)
    return safety


def due(prefs):
    b = defaults(prefs)
    if not b["on"]:
        return False
    last = b.get("last")
    if not last:
        return True
    try:
        age = datetime.datetime.now() - datetime.datetime.fromisoformat(last)
    except ValueError:
        return True
    return age.total_seconds() >= b["hours"] * 3600


def run_async(prefs, done, tag=""):
    """Sicherung im Hintergrund; done(pfad, fehler) läuft wieder im GTK-Thread."""
    b = defaults(prefs)
    dest, keep = os.path.expanduser(b["dir"]), b["keep"]

    def work():
        try:
            p = backup_now(dest, keep, tag)
            GLib.idle_add(lambda: (b.__setitem__("last", datetime.datetime.now().isoformat(timespec="seconds")),
                                   done(p, None), False)[-1])
        except Exception as e:  # noqa: BLE001 – Fehler (voller Datenträger, kein Zugriff) dem Nutzer zeigen
            GLib.idle_add(lambda: (done(None, str(e)), False)[-1])
    threading.Thread(target=work, daemon=True).start()
