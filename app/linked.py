# Einträge als echte Dateien: notist bearbeitet geöffnete Dateien direkt (keine Kopie) und legt neue Einträge
# als normale Dateien in einem Ordner ab (Standard ~/Dokumente/notist/{notizen,words,latex}). Die JSON-Datei in
# data/ bleibt als Verknüpfung + Zwischenstand (Titel, Etiketten, Erinnerung, Verlauf); der Inhalt steht in der Datei.
#
# Felder je Eintrag:
#   file        Pfad der Datei (None = nur intern, wie früher)
#   file_auto   True: Datei hat notist selbst angelegt (darf sie umbenennen und beim endgültigen Löschen wegräumen)
#   file_mtime  Änderungszeit nach dem letzten Lesen/Schreiben – weicht sie ab, wurde die Datei außerhalb geändert
#   file_ok     True: Rückfrage „Original überschreiben?“ für verlustbehaftete Formate ist beantwortet
#   want_file   neuer Eintrag, bekommt beim ersten Speichern eine Datei
import os, re, shutil

import paths

SUB = {"notes": "notizen", "docs": "words", "latex": "latex"}
NEW_EXT = {"notes": ".md", "docs": ".docx", "latex": ".tex"}
# was sich in welchem Bereich zurückschreiben lässt
WRITABLE = {"notes": (".md", ".markdown", ".txt"),
            "docs": (".docx", ".odt", ".html", ".htm", ".md", ".markdown", ".txt"),
            "latex": (".tex",)}
# notist versteht diese Formate nicht vollständig → vor dem ersten Überschreiben einmal fragen
LOSSY = (".docx", ".odt", ".html", ".htm")
ORIGINALS = os.path.join(paths.DATA, "originals")     # Sicherung des Originals vor dem ersten Überschreiben


def documents_dir():
    try:
        from gi.repository import GLib
        d = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_DOCUMENTS)
    except Exception:  # noqa: BLE001
        d = None
    return d or os.path.expanduser("~/Dokumente")


def settings(prefs):
    f = prefs.setdefault("files", {})
    f.setdefault("dir", os.path.join(documents_dir(), "notist"))
    f.setdefault("new_as_files", True)
    return f


def base_dir(prefs):
    return os.path.expanduser(settings(prefs)["dir"])


def kind_dir(prefs, kind):
    return os.path.join(base_dir(prefs), SUB[kind])


def safe_stem(title, fallback="unbenannt"):
    s = re.sub(r'[/\\:*?"<>|\x00-\x1f]', "", title or "").strip().strip(".")
    s = re.sub(r"\s+", " ", s)[:80].strip()
    return s or fallback


def unique(path, own=None):
    """path, oder „name (2).ext“ … falls schon belegt (own = der eigene, darf überschrieben werden)."""
    if not os.path.exists(path) or (own and same(path, own)):
        return path
    root, ext = os.path.splitext(path)
    if os.path.isdir(path) and not ext:
        root, ext = path, ""
    i = 2
    while True:
        p = f"{root} ({i}){ext}"
        if not os.path.exists(p) or (own and same(p, own)):
            return p
        i += 1


def same(a, b):
    try:
        return os.path.realpath(a) == os.path.realpath(b)
    except OSError:
        return a == b


def norm(path):
    return os.path.realpath(os.path.expanduser(path))


def mtime(path):
    try:
        return os.stat(path).st_mtime
    except OSError:
        return None


def is_project(note):
    """LaTeX-Eintrag, dessen Datei ein eigener Projektordner von notist ist (…/latex/<titel>/main.tex)."""
    f = note.get("file")
    return bool(f and note.get("file_auto") and os.path.basename(f) == "main.tex")


def clean_folder(folder):
    """„uni / mathe“ → „uni/mathe“ (Ordnerpfad in notist, „/“ trennt Unterordner)."""
    parts = [safe_stem(p, "") for p in (folder or "").replace("\\", "/").split("/")]
    return "/".join(p for p in parts if p)


def folder_dir(prefs, kind, folder):
    return os.path.join(kind_dir(prefs, kind), *clean_folder(folder).split("/")) if clean_folder(folder) \
        else kind_dir(prefs, kind)


def in_tree(prefs, kind, note):
    """Selbst angelegte Datei, die im notist-Ordner des Bereichs liegt (nur die zieht mit in Unterordner um)."""
    f = note.get("file")
    if not f or not note.get("file_auto"):
        return False
    top = norm(kind_dir(prefs, kind))
    return norm(f).startswith(top + os.sep)


def move_to_folder(prefs, kind, note):
    """Datei (bzw. LaTeX-Projektordner) in den Unterordner zu note["folder"] verschieben. True bei Erfolg."""
    if not in_tree(prefs, kind, note) or not os.path.exists(note["file"]):
        return False
    d = folder_dir(prefs, kind, note.get("folder"))
    if is_project(note):
        cur = os.path.dirname(note["file"])
        if same(os.path.dirname(cur), d):
            return False
        new = os.path.join(unique(os.path.join(d, os.path.basename(cur))), "main.tex")
    else:
        if same(os.path.dirname(note["file"]), d):
            return False
        new = unique(os.path.join(d, os.path.basename(note["file"])))
    try:
        os.makedirs(d, exist_ok=True)
    except OSError:
        return False
    return move(note, new)


def rename_dir(prefs, kind, old, new):
    """Ordner auf der Platte umbenennen (falls vorhanden). Gibt (alter, neuer) Pfad zurück oder None."""
    a, b = folder_dir(prefs, kind, old), folder_dir(prefs, kind, new)
    if not os.path.isdir(a) or os.path.exists(b):
        return None
    try:
        os.makedirs(os.path.dirname(b), exist_ok=True)
        os.rename(a, b)
    except OSError:
        return None
    return a, b


def remove_empty_dirs(prefs, kind, folder):
    """Leere Ordner (von innen nach außen) wegräumen – nie welche mit Inhalt."""
    folder = clean_folder(folder)
    while folder:
        try:
            os.rmdir(folder_dir(prefs, kind, folder))
        except OSError:
            return
        folder = folder.rpartition("/")[0]


def disk_folders(prefs, kind):
    """Unterordner im notist-Ordner des Bereichs → Ordnerpfade (LaTeX-Projektordner zählen nicht)."""
    top = kind_dir(prefs, kind)
    out = []
    for root, dirs, files in os.walk(top):
        dirs[:] = sorted(d for d in dirs if not d.startswith("."))
        if root == top:
            continue
        if kind == "latex" and "main.tex" in files:
            dirs[:] = []
            continue
        out.append(os.path.relpath(root, top).replace(os.sep, "/"))
    return out


def new_path(prefs, kind, title, folder=None):
    stem = safe_stem(title)
    d = folder_dir(prefs, kind, folder)
    if kind == "latex":
        return os.path.join(unique(os.path.join(d, stem)), "main.tex")
    return unique(os.path.join(d, stem + NEW_EXT[kind]))


def wanted_path(prefs, kind, note):
    """Wohin eine selbst angelegte Datei nach Titeländerung umziehen soll (None = bleibt)."""
    f = note.get("file")
    if not f or not note.get("file_auto"):
        return None
    stem = safe_stem(note.get("title"))
    if kind == "latex" and is_project(note):
        folder = os.path.dirname(f)
        cur = os.path.basename(folder)
        if re.sub(r" \(\d+\)$", "", cur) == stem:
            return None
        return os.path.join(unique(os.path.join(os.path.dirname(folder), stem), own=folder), "main.tex")
    root, ext = os.path.splitext(os.path.basename(f))
    if re.sub(r" \(\d+\)$", "", root) == stem:
        return None
    return unique(os.path.join(os.path.dirname(f), stem + ext), own=f)


def move(note, new):
    """Datei bzw. Projektordner umbenennen. True bei Erfolg."""
    old = note["file"]
    try:
        if is_project(note):
            os.rename(os.path.dirname(old), os.path.dirname(new))
        else:
            os.rename(old, new)
    except OSError:
        return False
    note["file"] = new
    return True


def kind_for(path, text=None):
    """Bereich, der zu einer Datei passt: "notes" | "docs" | "latex" | None (unklar → nachfragen)."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".tex":
        return "latex"
    if ext in (".docx", ".docm", ".dotx", ".doc", ".odt", ".html", ".htm", ".rtf"):
        return "docs"
    if ext not in (".md", ".markdown", ".txt", ""):
        return None
    if text is None:
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                text = f.read(200_000)
        except OSError:
            return "notes"
    if re.search(r"\\documentclass|\\begin\{document\}", text):
        return "latex"
    if ext in (".md", ".markdown"):
        heads = len(re.findall(r"^#{1,6} ", text, re.M))
        return "docs" if len(text) > 20_000 or heads >= 6 else "notes"
    if len(text) <= 6_000:
        return "notes"
    return None                                     # langer Fließtext: Notiz oder Words? → fragen


def needs_confirm(note):
    f = note.get("file")
    return bool(f and not note.get("file_auto") and not note.get("file_ok")
                and os.path.splitext(f)[1].lower() in LOSSY)


def writable(kind, path):
    return os.path.splitext(path)[1].lower() in WRITABLE[kind]


def backup_original(note, again=False):
    """Vor dem ersten Überschreiben einer fremden Datei eine Sicherung ablegen (einmal je Eintrag).
    again=True: die Datei wurde außerhalb geändert → diesen Stand zusätzlich mit Zeitstempel sichern."""
    f = note.get("file")
    if not f or not os.path.exists(f) or (not again and (note.get("file_auto") or note.get("file_backup"))):
        return
    d = os.path.join(ORIGINALS, note["id"])
    try:
        os.makedirs(d, exist_ok=True)
        dest = os.path.join(d, os.path.basename(f))
        if again:
            import time
            root, ext = os.path.splitext(dest)
            dest = f"{root} {time.strftime('%Y-%m-%d %H-%M-%S')}{ext}"
        shutil.copy2(f, dest)
        if not again:
            note["file_backup"] = dest
    except OSError:
        pass


# ---------------- lesen ----------------
def read(kind, path):
    """Datei → Felder für den Eintrag (title, text, rich | blocks, page)."""
    import docfmt as df
    stem = os.path.splitext(os.path.basename(path))[0]
    if kind == "latex":
        with open(path, encoding="utf-8", errors="replace") as f:
            text = f.read()
        import latexdata as ld
        title = ld.doc_title(text)
        if not title:
            title = os.path.basename(os.path.dirname(path)) if os.path.basename(path) == "main.tex" else stem
        return {"text": text, "title": title}
    if kind == "notes":
        import mdnotes as md
        with open(path, encoding="utf-8", errors="replace") as f:
            text = f.read()
        if path.lower().endswith((".md", ".markdown")):
            head, body = md.split_title(text)
            t, rich = md.to_note(body)
            return {"title": head or stem, "text": t, "rich": rich}
        return {"title": stem, "text": text, "rich": []}
    blocks, title, page = df.import_file_full(path)
    out = {"title": title or stem, "blocks": blocks, "text": df.plain_text(blocks), "media": df.has_content(blocks)}
    if page:
        out["page"] = page
    return out


def load_into(kind, note, path):
    data = read(kind, path)
    note.update(data)
    note["file_mtime"] = mtime(path)
    return note


# ---------------- schreiben ----------------
def render(kind, note, path):
    """Inhalt des Eintrags im Format der Datei → bytes oder str; None für Formate mit eigenem Schreiber."""
    import docfmt as df
    ext = os.path.splitext(path)[1].lower()
    title = (note.get("title") or "").strip()
    stem = os.path.splitext(os.path.basename(path))[0]
    if kind == "latex":
        return note.get("text", "")
    if kind == "notes":
        if ext in (".md", ".markdown"):
            import mdnotes as md
            body = md.from_note(note.get("text", ""), note.get("rich"))
            # Titel als Überschrift nur, wenn er sich nicht schon aus dem Dateinamen ergibt
            if title and title != re.sub(r" \(\d+\)$", "", stem):
                return f"# {title}\n\n{body}"
            return body
        return note.get("text", "").replace("￼", "")
    blocks = note.get("blocks") or [df.para()]
    if ext in (".md", ".markdown"):
        return df.to_markdown(blocks)
    if ext == ".txt":
        return df.export_text(blocks)
    if ext in (".html", ".htm"):
        return df.to_html(blocks, title)
    return None


def write(kind, note):
    """Eintrag in seine Datei schreiben (atomar: Hilfsdatei + Umbenennen). Wirft OSError/ValueError."""
    import docfmt as df
    path = note["file"]
    d = os.path.dirname(path)
    os.makedirs(d, exist_ok=True)
    tmp = os.path.join(d, f".{os.path.basename(path)}.notist-tmp")
    ext = os.path.splitext(path)[1].lower()
    try:
        content = render(kind, note, path)
        if content is not None:
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(content)
        elif ext == ".odt":
            import odf
            odf.write_odt(note.get("blocks") or [df.para()], tmp, note.get("title", ""), note.get("page"))
        elif ext == ".docx":
            df.write_docx(note.get("blocks") or [df.para()], tmp, note.get("title", ""), note.get("page"))
        else:
            raise ValueError(f"{ext} kann notist nicht schreiben")
        if os.path.exists(path):
            try:
                shutil.copymode(path, tmp)
            except OSError:
                pass
        os.replace(tmp, path)
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise
    note["file_mtime"] = mtime(path)


def discard(note):
    """Endgültig gelöscht: selbst angelegte Datei (bzw. Projektordner) in den System-Papierkorb."""
    f = note.get("file")
    if not f or not note.get("file_auto"):
        return
    target = os.path.dirname(f) if is_project(note) else f
    if not os.path.exists(target):
        return
    try:
        from gi.repository import Gio
        Gio.File.new_for_path(target).trash(None)
    except Exception:  # noqa: BLE001 – kein Papierkorb (z. B. anderes Dateisystem): dann bleibt die Datei
        pass


# ---------------- Ordner einlesen ----------------
def scan(prefs, known):
    """Dateien im notist-Ordner (auch in Unterordnern), die noch keinen Eintrag haben → [(kind, pfad, ordner)].
    known = Menge normierter Pfade."""
    out = []
    for kind in ("notes", "docs", "latex"):
        top = kind_dir(prefs, kind)
        for root, dirs, files in os.walk(top):
            dirs[:] = sorted(d for d in dirs if not d.startswith("."))
            if kind == "latex" and root != top and "main.tex" in files:
                dirs[:] = []                          # Projektordner: nicht tiefer
                p = os.path.join(root, "main.tex")
                if norm(p) not in known:
                    rel = os.path.relpath(os.path.dirname(root), top)
                    out.append((kind, p, "" if rel == "." else rel.replace(os.sep, "/")))
                continue
            if kind == "latex":
                continue
            rel = os.path.relpath(root, top)
            for name in sorted(files):
                p = os.path.join(root, name)
                if name.startswith(".") or not writable(kind, p) or norm(p) in known:
                    continue
                out.append((kind, p, "" if rel == "." else rel.replace(os.sep, "/")))
    return out


# ---------------- Dateien außerhalb von notist ----------------
def outside(prefs, note):
    """Pfad der Datei, wenn sie NICHT in notists Ordner liegt (z. B. ~/Downloads) und existiert – sonst None.
    Solche Dateien gehören dem Nutzer: Löschen fragt vorher nach."""
    f = note.get("file")
    if not f or note.get("file_auto") or not os.path.exists(f):
        return None
    base = norm(base_dir(prefs))
    p = norm(f)
    return None if p == base or p.startswith(base + os.sep) else f


def trash_file(note):
    """Datei des Eintrags in den System-Papierkorb (wiederherstellbar). True bei Erfolg."""
    f = note.get("file")
    if not f or not os.path.exists(f):
        return False
    try:
        from gi.repository import Gio
        Gio.File.new_for_path(f).trash(None)
    except Exception:  # noqa: BLE001 – kein Papierkorb auf diesem Dateisystem: dann bleibt sie
        return False
    note["file_trashed"] = True
    return True


def untrash(note):
    """Mit trash_file() weggeworfene Datei aus dem System-Papierkorb zurückholen (jüngster Treffer)."""
    f = note.get("file")
    if not note.pop("file_trashed", None) or not f or os.path.exists(f):
        return bool(f and os.path.exists(f))
    try:
        from gi.repository import Gio
        trash = Gio.File.new_for_uri("trash:///")
        it = trash.enumerate_children("standard::name,trash::orig-path,trash::deletion-date",
                                      Gio.FileQueryInfoFlags.NONE, None)
        best = None
        for info in it:
            if info.get_attribute_byte_string("trash::orig-path") == f or \
                    info.get_attribute_as_string("trash::orig-path") == f:
                when = info.get_attribute_as_string("trash::deletion-date") or ""
                if best is None or when > best[0]:
                    best = (when, info.get_name())
        if best is None:
            return False
        trash.get_child(best[1]).move(Gio.File.new_for_path(f), Gio.FileCopyFlags.NONE, None, None, None)
        note.pop("file_missing", None)
        return True
    except Exception:  # noqa: BLE001
        return False
