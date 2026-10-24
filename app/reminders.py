# Erinnerungen: Zeitpunkt je Notiz (note["reminder"], ISO, Ortszeit). Damit sie auch kommen, wenn notist
# geschlossen ist, legt notist – falls vorhanden – einen systemd-Benutzer-Timer an, der zur Zeit
# "notes --remind <id>" startet. Ohne systemd prüft die laufende App selbst alle 30 Sekunden.
import datetime, json, os, shutil, subprocess, sys

import paths

UNIT = "notes-erinnerung-{}"


def parse(iso):
    try:
        return datetime.datetime.fromisoformat(iso) if iso else None
    except ValueError:
        return None


def nice(dt):
    now = datetime.datetime.now()
    days = (dt.date() - now.date()).days
    day = {0: "heute", 1: "morgen", -1: "gestern"}.get(days)
    if day is None:
        day = ("Mo", "Di", "Mi", "Do", "Fr", "Sa", "So")[dt.weekday()] + f" {dt:%d.%m.}"
    return f"{day} {dt:%H:%M}"


def has_systemd():
    if os.environ.get("NOTES_NO_TIMERS"):
        return False
    return bool(shutil.which("systemd-run") and shutil.which("systemctl")) and \
        os.path.isdir(f"/run/user/{os.getuid()}/systemd")


def schedule(note, script):
    """Timer setzen (oder entfernen, wenn keine Erinnerung). True, wenn systemd übernimmt."""
    unit = UNIT.format(note["id"][:12])
    if not has_systemd():
        return False
    subprocess.run(["systemctl", "--user", "stop", unit + ".timer"], capture_output=True, timeout=10)
    subprocess.run(["systemctl", "--user", "reset-failed", unit + ".service"], capture_output=True, timeout=10)
    dt = parse(note.get("reminder"))
    if not dt or note.get("reminder_done") or dt <= datetime.datetime.now():
        return False
    cmd = ["systemd-run", "--user", f"--unit={unit}", f"--on-calendar={dt:%Y-%m-%d %H:%M:%S}",
           "--timer-property=AccuracySec=1s", "--collect", sys.executable, script, "--remind", note["id"]]
    try:
        return subprocess.run(cmd, capture_output=True, timeout=10).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def find_note(nid):
    for sub in (paths.NOTES, paths.DOCS, paths.LATEX):
        p = os.path.join(sub, nid + ".json")
        if os.path.exists(p):
            return p
    return None


def mark_done(nid):
    """Im Speicher auf der Platte als erledigt markieren. Gibt die Notiz zurück (oder None)."""
    p = find_note(nid)
    if not p:
        return None
    with open(p) as f:
        n = json.load(f)
    if n.get("reminder_done"):
        return None
    n["reminder_done"] = True
    tmp = p + ".tmp"
    with open(tmp, "w") as f:
        json.dump(n, f, ensure_ascii=False, indent=1)
    os.replace(tmp, p)
    return n


def quick_choices():
    now = datetime.datetime.now().replace(second=0, microsecond=0)
    tomorrow9 = (now + datetime.timedelta(days=1)).replace(hour=9, minute=0)
    evening = now.replace(hour=18, minute=0)
    nxt_monday = (now + datetime.timedelta(days=(7 - now.weekday()) or 7)).replace(hour=9, minute=0)
    out = [("In 1 Stunde", now + datetime.timedelta(hours=1))]
    if evening > now + datetime.timedelta(minutes=10):
        out.append(("Heute 18:00", evening))
    out += [("Morgen 9:00", tomorrow9), ("Nächsten Montag 9:00", nxt_monday)]
    return out


# ---------------- datist ----------------
# notist schreibt alle Erinnerungen in eine eigene Datei bei datist. datist übernimmt sie selbst als Termine
# (in den gewählten Kalender, auch Google) – so kommt sich nichts mit datists eigenem Speicher in die Quere.
DATIST_HOME = os.environ.get("NOTIST_DATIST_HOME") or os.path.expanduser("~/.local/share/kalender")
DATIST_FILE = os.path.join(DATIST_HOME, "data", "notist.json")


def datist_available():
    return os.path.isdir(DATIST_HOME) or bool(shutil.which("datist"))


def datist_calendars():
    """[(id, name)] der Kalender, in die datist schreiben darf."""
    out = [("local", "Lokal (nur dieser Rechner)")]
    try:
        with open(os.path.join(DATIST_HOME, "data", "cache.json")) as f:
            cals = json.load(f).get("calendars", [])
    except (OSError, ValueError):
        cals = []
    for c in cals:
        if c.get("role") in ("owner", "writer"):
            out.append((c["id"], c.get("name") or c["id"]))
    return out


def reminder_title(n):
    t = (n.get("title") or "").strip()
    if not t:
        t = next((l.strip() for l in n.get("text", "").replace("￼", "").splitlines() if l.strip()), "")
    return t[:80] or "Erinnerung"


def export_datist(prefs, stores):
    """Erinnerungen → datist/notist.json (nur schreiben, wenn sich etwas geändert hat)."""
    if not datist_available():
        return
    cfg = prefs.get("datist", {})
    items = {}
    if cfg.get("on", True):
        for kind, store in stores.items():
            for n in store.notes.values():
                if n.get("reminder") and not n.get("trashed") and parse(n["reminder"]):
                    items[n["id"]] = {"title": reminder_title(n), "start": n["reminder"], "kind": kind,
                                      "done": bool(n.get("reminder_done"))}
    data = {"version": 1, "cal": cfg.get("cal", "local"), "items": items}
    try:
        with open(DATIST_FILE) as f:
            if json.load(f) == data:
                return
    except (OSError, ValueError):
        pass
    try:
        os.makedirs(os.path.dirname(DATIST_FILE), exist_ok=True)
        tmp = DATIST_FILE + ".tmp"
        with open(tmp, "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        os.replace(tmp, DATIST_FILE)
    except OSError:
        pass
