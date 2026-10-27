# Teilen: Notiz/Dokument als Text kopieren, per E-Mail verschicken, als Datei speichern – oder als
# .notes-Datei für Freunde mit notist (enthält alles: Formatierung, Bilder, LaTeX-Projektdateien).
import base64, datetime, json, os, re, shutil, subprocess, tempfile, uuid

import paths

MAGIC = "notes-share"
VERSION = 1


def safe_name(title, fallback="Notiz"):
    name = "".join(c for c in (title or fallback) if c not in '/\\:*?"<>|').strip()[:80]
    return name or fallback


PRIVATE = ("file", "file_auto", "file_mtime", "file_ok", "file_backup", "file_error", "file_missing", "want_file",
           "source", "reminder", "reminder_done", "reminder_systemd")     # eigene Pfade bleiben auf diesem Rechner


def bundle(note, kind):
    """Eintrag → .notes-Inhalt (JSON-Text)."""
    import linked
    data = {"magic": MAGIC, "version": VERSION, "kind": kind,
            "exported": datetime.datetime.now().isoformat(timespec="seconds"),
            "note": {k: v for k, v in note.items() if k not in PRIVATE}, "files": {}}
    if kind == "latex":
        d = os.path.dirname(note["file"]) if linked.is_project(note) else os.path.join(paths.LATEX_FILES, note["id"])
        if os.path.isdir(d):
            for root, _dirs, files in os.walk(d):
                for f in files:
                    full = os.path.join(root, f)
                    rel = os.path.relpath(full, d)
                    if f == "main.tex" or os.path.getsize(full) > 25 * 1024 * 1024:
                        continue
                    with open(full, "rb") as fh:
                        data["files"][rel] = base64.b64encode(fh.read()).decode()
    if kind == "docs":                   # PDF-Anhänge aus notist/data/pdfs gehören mit in die Datei
        import pdfblock
        for blk in note.get("blocks") or []:
            f = blk.get("file") if blk.get("t") == "pdf" else None
            if f and os.path.exists(pdfblock.path_of(f)):
                with open(pdfblock.path_of(f), "rb") as fh:
                    data["files"]["pdfs/" + os.path.basename(f)] = base64.b64encode(fh.read()).decode()
    return json.dumps(data, ensure_ascii=False)


def read_bundle(path):
    """.notes-Datei → (art, notiz, dateien). Neue ID, damit nichts Vorhandenes überschrieben wird."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if data.get("magic") != MAGIC or data.get("kind") not in ("notes", "docs", "latex"):
        raise ValueError("Das ist keine notist-Datei")
    n = data["note"]
    n["id"] = str(uuid.uuid4())
    n["trashed"], n["trashed_at"], n["archived"] = False, None, False
    n["sync"] = {"keep_id": None, "keep_updated": None, "dirty": True}
    for k in PRIVATE:
        n.pop(k, None)
    files = {}
    for rel, b64 in (data.get("files") or {}).items():
        rel = os.path.normpath(rel)
        if rel.startswith("..") or os.path.isabs(rel):
            continue                     # keine Pfade außerhalb des Projektordners
        files[rel] = base64.b64decode(b64)
    return data["kind"], n, files


def write_files(nid, files):
    d = os.path.join(paths.LATEX_FILES, nid)
    for rel, blob in files.items():
        if rel.startswith("pdfs" + os.sep):
            os.makedirs(os.path.join(paths.DATA, "pdfs"), exist_ok=True)
            with open(os.path.join(paths.DATA, "pdfs", os.path.basename(rel)), "wb") as f:
                f.write(blob)
            continue
        p = os.path.join(d, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as f:
            f.write(blob)


def temp_dir():
    d = os.path.join(tempfile.gettempdir(), "notes-teilen")
    os.makedirs(d, exist_ok=True)
    return d


def email(path, subject):
    """Mailprogramm mit Anhang öffnen. → True, wenn ein Programm gestartet wurde."""
    for cmd in (["xdg-email", "--subject", subject, "--attach", path],
                ["thunderbird", "-compose", f"subject='{subject}',attachment='file://{path}'"]):
        if shutil.which(cmd[0]):
            try:
                subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
                return True
            except OSError:
                continue
    return False


def plain(note, kind):
    if kind == "latex":
        return note["text"]
    text = note["text"].replace("￼", "")
    title = note["title"].strip()
    return (title + "\n\n" if title else "") + text
