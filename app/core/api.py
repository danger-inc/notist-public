"""Schmale JSON-Schnittstelle des Kerns – für die Handy-App (Chaquopy) und für Skripte.

Alles hier nimmt/gibt nur JSON-taugliche Werte (dict, list, str, int, bool, None; Bytes als Base64-Text), wirft bei
Fehlern ValueError/OSError mit lesbarer Meldung und importiert nie „gi“.

Modelle:
  Words-Dokument = {"blocks": [...], "title": str, "page": dict|None}      (Blöcke wie in docfmt)
  Notiz          = {"text": str, "rich": [[von, bis, "stil"], ...], "title": str}
"""
import base64
import json
import os

from core import autofix, dictdb, docfmt, exports, handylink, mdnotes, notesconvert, share, xlsx
from core import odf as _odf

EXPORT_FORMATS = ("docx", "odt", "md", "html", "txt", "rtf", "epub", "tex")


def _default(o):
    if isinstance(o, (bytes, bytearray)):
        return base64.b64encode(bytes(o)).decode("ascii")
    if isinstance(o, (set, frozenset, tuple)):
        return list(o)
    return str(o)


def jsonable(x):
    """Beliebige Kernwerte → reines JSON (Tupel werden Listen, Bytes Base64)."""
    return json.loads(json.dumps(x, ensure_ascii=False, default=_default))


# ---------------- Words-Dokumente ----------------
def import_file(path):
    """.docx/.odt/.md/.html/.txt … → {"blocks", "title", "page"}."""
    blocks, title, page = docfmt.import_file_full(path)
    return jsonable({"blocks": blocks, "title": title or os.path.splitext(os.path.basename(path))[0], "page": page})


def export(model, fmt, path):
    """Dokument-Modell → Datei im Format fmt (siehe EXPORT_FORMATS). Gibt den Pfad zurück."""
    blocks, title, page = model.get("blocks") or [], model.get("title") or "", model.get("page")
    fmt = fmt.lower().lstrip(".")
    if fmt == "docx":
        docfmt.write_docx(blocks, path, title, page)
    elif fmt == "odt":
        _odf.write_odt(blocks, path, title, page)
    elif fmt == "rtf":
        exports.write_rtf(blocks, path, title)
    elif fmt == "epub":
        exports.write_epub(blocks, path, title)
    elif fmt in ("md", "html", "txt", "tex"):
        text = {"md": lambda: docfmt.to_markdown(blocks), "html": lambda: docfmt.to_html(blocks, title),
                "txt": lambda: docfmt.export_text(blocks),
                "tex": lambda: notesconvert.blocks_to_latex(blocks, title, page)}[fmt]()
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
    else:
        raise ValueError(f"Format {fmt!r} wird nicht unterstützt")
    return path


def to_latex(model, image_dir=None):
    return notesconvert.blocks_to_latex(model.get("blocks") or [], model.get("title") or "", model.get("page"), image_dir)


def from_latex(src, image_dir=None):
    blocks, title = notesconvert.latex_to_blocks(src, image_dir)
    return jsonable({"blocks": blocks, "title": title, "page": None})


# ---------------- Notizen ↔ Markdown ----------------
def md_to_note(md):
    title, rest = mdnotes.split_title(md)
    text, rich = mdnotes.to_note(rest)
    return jsonable({"title": title, "text": text, "rich": rich})


def note_to_md(note, images=None):
    return mdnotes.from_note(note.get("text") or "", [tuple(r) for r in note.get("rich") or []],
                             note.get("title") or "", images)


# ---------------- Abgleich ----------------
def digest(entry):
    """Inhaltsprüfsumme eines Eintrags (ohne Felder, die nur am PC gelten) – gleiche Zahl auf jedem Gerät."""
    return handylink.digest(entry)


def bundle_write(note, kind, path):
    """Eintrag als .notes-Datei schreiben (kind: notes | docs | latex)."""
    with open(path, "w", encoding="utf-8") as f:
        f.write(share.bundle(note, kind))
    return path


def bundle_read(path):
    """.notes-Datei → {"kind", "note", "files": {pfad: base64}}."""
    kind, note, files = share.read_bundle(path)
    return jsonable({"kind": kind, "note": note, "files": files})


# ---------------- Tabellen, Wörterbuch, Autokorrektur ----------------
def xlsx_preview(path, sheet=0, limit=xlsx.TABLE_ROWS):
    """XLSX → {"sheets": [namen], "cur": n, "name", "nrows", "ncols", "rows": [[text]]} (nur Texte, wie angezeigt)."""
    wb = xlsx.workbook(path)
    if wb is None:
        raise ValueError("Die Tabelle lässt sich nicht lesen")
    sh = wb.sheet(int(sheet))
    return {"sheets": list(wb.names), "cur": max(0, min(int(sheet), len(wb.names) - 1)), "name": sh.get("name", ""),
            "nrows": sh["nrows"], "ncols": sh["ncols"], "rows": [[t for t, _n in r] for r in sh["rows"][:limit]]}


_DICT = None


def dict_lookup(query, direction="auto"):
    """Wörterbuch de ⇄ en (Datei dict/de-en.sqlite muss vorhanden sein; sonst leer)."""
    global _DICT
    if _DICT is None:
        _DICT = dictdb.Dictionary()
    return jsonable(_DICT.lookup(query, direction))


def autofix_word(word, prefs=None):
    """Smarte Korrektur für ein fertig getipptes Wort → Ersatz oder None."""
    return autofix.correction(word, prefs or {})


# ---------------- Handy: Speicher + Abgleich (core/mobile.py, Plan Schritt 20) ----------------
def _mob():
    from core import mobile
    return mobile.get()


def m_start(legacy_dir=None):
    """Speicher öffnen: alte 0.1.0-Daten übernehmen, Index bauen. → {"migrated": …|None, "counts": {bereich: n}}."""
    from core import mobile
    mig = mobile.migrate_legacy(legacy_dir)
    m = mobile.get()
    return jsonable({"migrated": mig, "counts": {k: len(m.list(k, "aktiv")) for k in mobile.KINDS}, "me": m.srv.rep.me,
                     "fts5": m.fts})


def m_list(kind, view="aktiv", q="", label=None, folder=None):
    return jsonable(_mob().list(kind, view, q, label or None, folder))


def m_get(kind, nid):
    return jsonable(_mob().get(kind, nid))


def m_exists(kind, nid):
    return _mob().exists(kind, nid)


def m_new(kind, folder=None):
    return jsonable(_mob().new(kind, folder or None))


def m_save(kind, entry):
    return jsonable(_mob().save(kind, entry))


def m_patch(kind, nid, fields):
    return jsonable(_mob().patch(kind, nid, fields))


def m_trash(kind, nid):
    _mob().trash(kind, nid)


def m_restore(kind, nid):
    _mob().restore(kind, nid)


def m_delete(kind, nid):
    _mob().delete_forever(kind, nid)


def m_labels():
    return _mob().labels()


def m_folders(kind):
    return _mob().folders(kind)


def m_add_folder(kind, name):
    _mob().add_folder(kind, name)


def m_rename_folder(kind, old, new):
    return _mob().rename_folder(kind, old, new)


def m_delete_folder(kind, name):
    return _mob().delete_folder(kind, name)


def m_versions(kind, nid):
    return _mob().versions(kind, nid)


def m_version(kind, nid, name):
    return jsonable(_mob().version(kind, nid, name))


def m_peers():
    return _mob().peer_list()


def m_pair(addr, code, name=None):
    """Mit PC/Mac koppeln (Code von dort). addr leer → im Netz suchen."""
    return _mob().pair(addr, code, name)


def m_unpair(pid):
    _mob().unpair(pid)


def m_set_found(hosts):
    """Vom Handy (NsdManager) gefundene notist-Geräte: [[host, port], …]."""
    _mob().set_found(hosts)


def m_discover():
    return jsonable(_mob().discover())


def m_sync_start(pid=None):
    return _mob().sync_start(pid or None)


def m_sync_status():
    return jsonable(_mob().sync_status())


def m_due():
    return _mob().due()


def m_interval(minutes=None):
    m = _mob()
    if minutes is not None:
        m.set_interval(minutes)
    return m.interval()


# ---------------- Handy: Öffnen/Importieren und Exportieren (Schritt 27) ----------------
IMPORT_NOTES = (".md", ".markdown", ".txt")
IMPORT_DOCS = (".docx", ".docm", ".dotx", ".odt", ".html", ".htm", ".rtf")


def _new_entry(kind, title, **fields):
    from core import store as _st
    n = _st.new_note(title=title)
    n.update(fields)
    if kind == "docs":
        n.setdefault("blocks", [])
    return n


def m_import(path, name=None):
    """Datei → neuer Eintrag. → {"kind", "id", "title"}. Wirft ValueError mit lesbarer Meldung bei unbekannten/kaputten Dateien.
    .notes → wie gesendet (neue Id, Anhänge werden abgelegt) · .md/.txt → Notiz · .docx/.odt/.html/.rtf → Words · .tex → LaTeX."""
    from core import mobile, share
    m = mobile.get()
    base = os.path.basename(name or path)
    stem, ext = os.path.splitext(base)
    ext = ext.lower()
    if ext == ".notes":
        kind, n, files = share.read_bundle(path)
        share.write_files(n["id"], files)
        entry = n
    elif ext in IMPORT_NOTES:
        with open(path, "rb") as f:
            raw = f.read()
        try:
            txt = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            txt = raw.decode("cp1252", "replace")
        if ext == ".txt":
            kind, entry = "notes", _new_entry("notes", stem, text=txt.replace("\r\n", "\n"))
        else:
            d = md_to_note(txt)
            kind, entry = "notes", _new_entry("notes", d.get("title") or stem, text=d["text"], rich=d["rich"])
    elif ext in IMPORT_DOCS:
        if ext == ".rtf":
            raise ValueError("RTF kann das Handy nur schreiben, nicht lesen – am PC öffnen oder als DOCX/ODT senden")
        blocks, title, page = docfmt.import_file_full(path)
        kind = "docs"
        entry = _new_entry("docs", title or stem, blocks=blocks)
        if page:
            entry["page"] = page
    elif ext == ".tex":
        with open(path, "rb") as f:
            txt = f.read().decode("utf-8", "replace")
        kind, entry = "latex", _new_entry("latex", stem, text=txt)
    else:
        raise ValueError(f"Der Dateityp {ext or '(ohne Endung)'} wird nicht unterstützt")
    out = m.save(kind, entry)
    return jsonable({"kind": kind, "id": out["id"], "title": out.get("title") or stem})


def _blocks_of(kind, n):
    if kind == "docs":
        return n.get("blocks") or [], n.get("title") or "", n.get("page")
    md = mdnotes.from_note(n.get("text") or "", [tuple(r) for r in n.get("rich") or []], n.get("title") or "", n.get("images"))
    return docfmt.markdown_blocks(md) or [docfmt.para("")], n.get("title") or "", None


def m_export(kind, nid, fmt, path):
    """Eintrag → Datei im Format fmt (docx, odt, md, html, txt, rtf, epub; LaTeX zusätzlich tex, zip). Gibt den Pfad zurück.
    PDF entsteht am Handy über den Druckdienst (HTML → WebView), nicht hier."""
    import zipfile
    from core import mobile
    m = mobile.get()
    n = m.get(kind, nid)
    if n is None:
        raise ValueError("Eintrag nicht gefunden")
    fmt = fmt.lower().lstrip(".")
    if kind == "latex":
        if fmt in ("tex", "txt"):
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(n.get("text") or "")
        elif fmt == "zip":
            d = os.path.join(paths_data(), "latex-files", nid)
            with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
                z.writestr("main.tex", n.get("text") or "")
                if os.path.isdir(d):
                    for root, _dirs, files in os.walk(d):
                        for fn in files:
                            full = os.path.join(root, fn)
                            rel = os.path.relpath(full, d)
                            if rel != "main.tex":
                                z.write(full, rel)
        else:
            raise ValueError(f"LaTeX lässt sich nicht als {fmt} speichern")
        return path
    if kind == "notes" and fmt == "txt":
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(share.plain(n, "notes"))
        return path
    if kind == "notes" and fmt == "md":
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(mdnotes.from_note(n.get("text") or "", [tuple(r) for r in n.get("rich") or []], n.get("title") or "", n.get("images")))
        return path
    blocks, title, page = _blocks_of(kind, n)
    return export({"blocks": blocks, "title": title, "page": page}, fmt, path)


def paths_data():
    from core import paths
    return paths.DATA


def m_export_bundle(kind, nid, path):
    """Eintrag als .notes-Datei (verlustfrei, mit Anhängen)."""
    from core import mobile
    m = mobile.get()
    n = m._find(kind, nid)
    return bundle_write(n, kind, path)


def m_html(kind, nid):
    """Eintrag als HTML-Text (für Seitenansicht/Drucken am Handy)."""
    from core import mobile
    n = mobile.get().get(kind, nid)
    if n is None:
        raise ValueError("Eintrag nicht gefunden")
    if kind == "latex":
        import html as _h
        return "<html><body><pre>" + _h.escape(n.get("text") or "") + "</pre></body></html>"
    blocks, title, _page = _blocks_of(kind, n)
    return docfmt.to_html(blocks, title)


# ---------------- Handy: Rechtschreibung, Autokorrektur, Übersetzer (Schritt 28) ----------------
def m_spell_langs(langs=None):
    """Aktive Sprachen setzen (z. B. ["de","en"]) → {"de": installiert?, "en": …}."""
    from core import spellmob
    sp = spellmob.get()
    if langs is not None:
        sp.set_langs(list(langs))
    return sp.installed()


def m_spell_check(text):
    """Falsch geschriebene Wörter: [[start, ende, wort], …] (UTF-16-Indizes)."""
    from core import spellmob
    return [list(x) for x in spellmob.get().check(text)]


def m_spell_suggest(word, n=8):
    from core import spellmob
    return spellmob.get().suggest(word, int(n))


def m_spell_add(word):
    from core import spellmob
    spellmob.get().add_word(word)


def m_spell_ignore(word):
    from core import spellmob
    spellmob.get().ignored.add(word)


def m_autofix(word, prefs=None):
    """Korrektur für ein fertig getipptes Wort (core.autofix mit Wörterbuch-Regeln) oder None."""
    from core import spellmob
    sp = spellmob.get()
    sp.set_langs(sp.langs)
    return autofix.correction(word, prefs or {}, sp)


def m_autofix_revert(word):
    """Nach der Rücktaste: dieses Wort nicht wieder anfassen."""
    autofix._reverted.add(word)


def m_dict_status():
    from core import dictdb
    d = dictdb.Dictionary()
    wd = dictdb.wd_installed() if hasattr(dictdb, "wd_installed") else []
    return {"installed": dictdb.available(), "size": os.path.getsize(dictdb.DB) if dictdb.available() else 0,
            "langs": dictdb.LANGS, "extra": list(wd)}


_DICT_JOB = {"running": False, "text": "", "frac": None, "err": None, "done": False}


def m_dict_install(lang=None):
    """Wörterbuch laden/einrichten (Hintergrund). Stand: m_dict_progress()."""
    from core import dictdb
    if _DICT_JOB["running"]:
        return False
    _DICT_JOB.update(running=True, text="…", frac=None, err=None, done=False)

    def progress(text, frac):
        _DICT_JOB.update(text=text, frac=frac)

    def done(err):
        _DICT_JOB.update(running=False, err=err, done=True)
    if lang and lang != "en":
        dictdb.wd_install(lang, progress, done)
    else:
        dictdb.install(progress, done)
    return True


def m_dict_progress():
    return dict(_DICT_JOB)


def m_translate(q, direction="auto", lang="en"):
    """Wort/Wendung nachschlagen (offline). lang = Fremdsprache des Paars (en = ding, sonst WikDict). → Treffergruppen."""
    from core import dictdb
    global _DICT
    if lang and lang != "en":
        return jsonable(dictdb.WikDict(lang).lookup(q, direction))
    if _DICT is None:
        _DICT = dictdb.Dictionary()
    return jsonable(_DICT.lookup(q, direction))


def m_translate_online(q, src="de", lang="en"):
    """Ganzen Satz online übersetzen (MyMemory) – blockiert bis zur Antwort. → [text, alternativen…]"""
    import threading
    from core import dictdb
    box = {}
    ev = threading.Event()

    def done(res, err):
        box["res"], box["err"] = res, err
        ev.set()
    dictdb.online(q, src, done, lang)
    ev.wait(20)
    if box.get("err"):
        raise ValueError(box["err"])
    return box.get("res") or []


# ---------------- Handy: LaTeX (Schritt 29) ----------------
def m_compile(nid, text, pid=None):
    """Am gekoppelten Rechner bauen lassen (Hintergrund); Stand: m_compile_status()."""
    return _mob().compile_start(nid, text, pid or None)


def m_compile_status():
    m = _mob()
    return jsonable({**m.cjob, "pending": sorted(m.cpending)})


def m_tex_sync_pdf(nid, line):
    return jsonable(_mob().sync_pdf(nid, line))


def m_tex_sync_src(nid, page, x, y):
    return jsonable(_mob().sync_src(nid, page, x, y))


def m_tex_complete(prefix, limit=12):
    """Befehle, die mit prefix (z. B. "\\sec") beginnen: [{name, snippet, info, cat}] (snippet mit \u0001 = Cursor)."""
    from core import latexdata as ld
    pre = prefix.lower()
    out = [{"name": c[0], "snippet": c[1], "info": c[2], "cat": c[3]} for c in ld.COMMANDS if c[0].lower().startswith(pre)]
    out.sort(key=lambda c: (len(c["name"]), c["name"]))
    return out[:int(limit)]


def m_tex_envs():
    from core import latexdata as ld
    return [{"name": e[0], "snippet": ld.env_snippet(e[0]), "info": e[2]} for e in ld.ENVIRONMENTS]


def m_tex_templates(lang="de"):
    from core import latexdata as ld
    t = ld.TEMPLATES_EN if lang == "en" else ld.TEMPLATES
    return [{"id": x[0], "title": x[2], "info": x[3], "source": x[4]} for x in t]


def m_tex_explain(msg, warning=False):
    """Fehlermeldung des Setzers → (Titel, Erklärung) auf Deutsch oder None."""
    from core import latexdata as ld
    r = ld.explain(msg, bool(warning))
    return list(r) if r else None


def m_tex_files(nid):
    """Projektdateien (Anhänge) des LaTeX-Eintrags: [{name, size}] relativ zum Projektordner (ohne main.tex/Zwischendateien)."""
    from core import handylink as hl2, mobile
    m = mobile.get()
    be = hl2.AppBackend(m.app)
    return [{"name": k[4:], "size": os.path.getsize(p)} for k, p in sorted(be.refs(f"latex:{nid}", {}).items())]


def m_tex_add_file(nid, name, b64):
    """Datei (Bild, .bib, weitere .tex) in den Projektordner legen."""
    import base64 as b
    from core import handylink as hl2, mobile
    be = hl2.AppBackend(mobile.get().app)
    name = name.strip().replace("\\", "/")
    if not name or name.startswith("/") or ".." in name.split("/") or name == "main.tex":
        raise ValueError("Ungültiger Dateiname")
    path = os.path.join(be._projdir(f"latex:{nid}"), *name.split("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(b.b64decode(b64))
    return name


def m_tex_remove_file(nid, name):
    from core import handylink as hl2, mobile
    be = hl2.AppBackend(mobile.get().app)
    if ".." in name.split("/") or name.startswith("/"):
        raise ValueError("Ungültiger Dateiname")
    p = os.path.join(be._projdir(f"latex:{nid}"), *name.split("/"))
    if os.path.isfile(p):
        os.remove(p)


# ---------------- Handy: Erinnerungen, Verlauf, Sicherung (Schritt 31) ----------------
def _backup():
    from core import backupcore
    return backupcore


def m_reminders():
    return jsonable(_mob().reminders())


def m_reminder_done(kind, nid):
    _mob().reminder_done(kind, nid)


def m_diff(kind, nid, name):
    return jsonable(_mob().diff(kind, nid, name))


def m_welcome(lang="de"):
    from core import mobile
    mobile.get()
    return mobile.welcome(lang)


def m_backup(dest, tag="handy"):
    """ZIP-Sicherung in den Ordner dest (gleiches Format wie am PC – dort wiederherstellbar). → Pfad."""
    backup = _backup()
    from core import mobile
    mobile.get()
    return backup.backup_now(dest, keep=5, tag=tag)


def m_restore_backup(path, safety_dir):
    """Sicherung (vom Handy oder vom PC) einspielen; der bisherige Stand wird vorher in safety_dir gesichert. → Pfad der Vorsicherung."""
    backup = _backup()
    from core import mobile
    m = mobile.get()
    with mobile.LOCK:
        safety = backup.restore(path, safety_dir)
    m.reload()
    return safety


def m_snapshot(kind, nid):
    """Aktuellen Stand sofort in den Verlauf legen („Jetzt Version speichern“)."""
    from core import mobile
    m = mobile.get()
    with mobile.LOCK:
        st = m._store(kind)
        n = m._find(kind, nid)
        return st.snapshot(n, force=True) is not None
