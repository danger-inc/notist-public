#!/usr/bin/env python3
# Datenpfad-Tests (Plan Schritt 4): Hintergrund-Schreiben, Umbenennen, Neu-Einlesen, Sicherung, Erinnerung, Teilen.
# Ohne Fenster: die Methoden von notes.Notes laufen auf einem schlanken Ersatz-Objekt. Alles in einem Temp-Ordner.
#   python tests/datapath.py [-v] [--only t3]
import os, sys, tempfile, time, json, shutil

T = tempfile.mkdtemp(prefix="notist-dp-")
os.environ.update(NOTES_HOME=T, NOTES_DATA_DIR=os.path.join(T, "data"), NOTES_APP_ID="de.test.Notist",
                  NOTES_NO_TIMERS="1", NOTIST_DATIST_HOME=os.path.join(T, "kalender"))
APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, APP)

import notes  # noqa: E402
import paths  # noqa: E402
import linked as lk  # noqa: E402
import store as st  # noqa: E402
import reminders as rem  # noqa: E402
import backup  # noqa: E402
import share  # noqa: E402
from gi.repository import GLib  # noqa: E402

VERBOSE = "-v" in sys.argv
REAL_WRITE = lk.write


def slow_write(kind, note):
    time.sleep(0.3)
    REAL_WRITE(kind, note)


def pump():
    ctx = GLib.MainContext.default()
    while ctx.iteration(False):
        pass


class App:
    """Nur was der Datenpfad braucht; die Logik selbst kommt unverändert aus notes.Notes."""
    for _m in ("write_bg", "join_bg", "sync_file", "reload_if_changed", "file_index", "run_sync_file",
               "later_sync_file", "restore_backup", "fire_reminder", "move_to_folder", "kind_of", "taken_paths", "source_hit"):
        locals()[_m] = getattr(notes.Notes, _m)

    def __init__(self):
        root = tempfile.mkdtemp(dir=T)
        self.docdir = os.path.join(root, "Dokumente", "notist")
        self.prefs = {"files": {"dir": self.docdir, "new_as_files": True},
                      "backup": {"dir": os.path.join(root, "sicherungen")}}
        for p in (paths.NOTES, paths.DOCS, paths.LATEX, paths.HISTORY, os.path.join(paths.DATA, "originals")):
            shutil.rmtree(p, ignore_errors=True)
        self.stores = {"notes": st.Store(paths.NOTES), "docs": st.Store(paths.DOCS), "latex": st.Store(paths.LATEX)}
        self.kind, self.current, self.tex, self.docs, self.mode = "notes", None, False, False, "notes"
        self._fsync_id = self._fsync_note = None
        self.last_sel, self.sent, self.msgs = {}, [], []

    store = property(lambda self: self.stores[self.kind])

    def notify(self, msg, *a, **k):
        self.msgs.append(msg)

    def send_notification(self, nid, note):
        self.sent.append(nid)

    def display_title(self, n, kind):
        return n.get("title") or "?"

    def folder_prefs(self, kind):
        return [], []

    flush = update_meta = refresh_list = refresh_home = fill_more_menu = save_prefs = apply_kind = \
        update_rem_btn = confirm_overwrite = latex_files_along = lambda self, *a, **k: None


def new_note(app, title="Titel", text="eins", kind="notes"):
    n = app.stores[kind].create()
    n.update(title=title, text=text, rich=[], want_file=True)
    app.stores[kind].save(n)
    app.sync_file(n, kind)
    assert n.get("file") and os.path.exists(n["file"]), n
    return n


def body(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


# ---------------------------------------------------------------- Funde
def t1_rename_during_bg_write():
    """Titel ändern, während die Datei im Hintergrund geschrieben wird → alte Datei darf nicht wieder auftauchen."""
    app = App()
    n = new_note(app, "Alt")
    old = n["file"]
    lk.write = slow_write
    try:
        n["text"] = "zwei"
        app.write_bg("notes", n)
        n["title"] = "Neu"
        app.sync_file(n, "notes")
        app.join_bg()
        pump()
    finally:
        lk.write = REAL_WRITE
    assert not os.path.exists(old), f"Geisterdatei {os.path.basename(old)} neben {os.path.basename(n['file'])}"
    assert "zwei" in body(n["file"])


def t1b_folder_move_during_bg_write():
    """In einen Ordner verschieben, während im Hintergrund geschrieben wird."""
    app = App()
    n = new_note(app, "Ordnerfall")
    old = n["file"]
    lk.write = slow_write
    try:
        n["text"] = "zwei"
        app.write_bg("notes", n)
        app.move_to_folder(n, "uni", kind="notes", quiet=True)
        app.join_bg()
        pump()
    finally:
        lk.write = REAL_WRITE
    assert not os.path.exists(old), "Geisterdatei im alten Ordner"
    assert os.sep + "uni" + os.sep in n["file"] and "zwei" in body(n["file"])


def t2_quit_keeps_queued_write():
    """Beenden: join_bg muss auch den nachgereichten neuesten Stand schreiben und die mtime merken."""
    app = App()
    n = new_note(app)
    lk.write = slow_write
    try:
        n["text"] = "zwei"
        app.write_bg("notes", n)
        n["text"] = "drei"
        app.write_bg("notes", n)               # wartet hinter dem ersten
        app.join_bg()                          # kein pump(): beim Beenden läuft die Hauptschleife nicht mehr
    finally:
        lk.write = REAL_WRITE
    assert "drei" in body(n["file"]), "neuester Stand nicht in der Datei"
    assert abs(lk.mtime(n["file"]) - n["file_mtime"]) <= 0.001, "file_mtime veraltet → nächster Start liest neu ein"


def t3_reload_during_own_write():
    """Eigenes Hintergrund-Schreiben ist fertig, aber noch nicht quittiert → darf nicht als „außen geändert“ gelten."""
    app = App()
    n = new_note(app)
    time.sleep(0.05)                           # sonst gleiche mtime wie beim Anlegen
    n["text"] = "zwei"
    app.write_bg("notes", n)
    app._bg_thread.join()                      # Datei geschrieben, finish() noch nicht gelaufen
    n["text"] = "drei"                         # inzwischen weiter getippt (flush)
    again = app.reload_if_changed(n, "notes")
    pump()
    assert not again and n["text"] == "drei", f"eigene Änderung überschrieben: {n['text']!r}"


def t4_reload_keeps_local_version():
    """Datei außen geändert → neu einlesen; der notist-Stand davor muss im Verlauf landen."""
    app = App()
    n = new_note(app, "Fremd", "lokal")
    with open(n["file"], "w", encoding="utf-8") as f:
        f.write("extern\n")
    os.utime(n["file"], (time.time() + 5, time.time() + 5))
    assert app.reload_if_changed(n, "notes")
    texts = [app.stores["notes"].load_version(p).get("text") for _, p in app.stores["notes"].versions(n)]
    assert "lokal" in texts, f"lokaler Stand weg (Verlauf: {texts})"


def t5_restore_with_pending_write():
    """Sicherung zurückspielen, während eine aufgeschobene Datei-Speicherung wartet."""
    app = App()
    n = new_note(app, "Sich", "alt")
    zipf = backup.backup_now(app.prefs["backup"]["dir"], 99)
    n["text"] = "neu"
    app.stores["notes"].save(n)
    app.current, app._fsync_note = n, (n, "notes")
    app.restore_backup(zipf)
    app.run_sync_file()
    app.join_bg()
    pump()
    m = st.Store(paths.NOTES).notes[n["id"]]
    assert m["text"] == "alt", f"Wiederherstellen wieder überschrieben: {m['text']!r}"


def t6_restore_reaches_files():
    """Sicherung zurückspielen gilt auch für Einträge mit Datei (sonst liest select() den neuen Dateistand ein)."""
    app = App()
    n = new_note(app, "Datei", "alt")
    zipf = backup.backup_now(app.prefs["backup"]["dir"], 99)
    time.sleep(0.02)
    n["text"] = "neu"
    app.stores["notes"].save(n)
    app.sync_file(n, "notes")
    os.utime(n["file"], (time.time() + 5, time.time() + 5))
    app.restore_backup(zipf)
    m = app.stores["notes"].notes[n["id"]]
    app.reload_if_changed(m, "notes")
    assert m["text"] == "alt" and "alt" in body(m["file"]), f"Eintrag {m['text']!r}, Datei {body(m['file'])!r}"
    orig = os.path.join(paths.DATA, "originals", n["id"])
    kept = [body(os.path.join(orig, f)) for f in os.listdir(orig)] if os.path.isdir(orig) else []
    assert any("neu" in k for k in kept), "Dateistand vor dem Wiederherstellen nicht gesichert"


def t7_reminder_for_trashed():
    """Erinnerung eines gelöschten Eintrags darf nicht melden (systemd-Timer und laufende App)."""
    app = App()
    n = app.stores["notes"].create()
    n.update(title="Zahnarzt", text="x", reminder="2020-01-01T09:00")
    app.stores["notes"].save(n)
    app.stores["notes"].trash(n)
    assert rem.mark_done(n["id"]) is None, "systemd-Weg meldet gelöschten Eintrag"
    app.fire_reminder(n["id"])
    assert not app.sent, "laufende App meldet gelöschten Eintrag"


def t8_two_entries_one_file():
    """Zwei neue Einträge gleichen Titels, der erste schreibt noch im Hintergrund → nicht dieselbe Datei."""
    app = App()
    a, b = (app.stores["notes"].create() for _ in range(2))
    for x, t in ((a, "A"), (b, "B")):
        x.update(title="", text=t, rich=[], want_file=True)
        app.stores["notes"].save(x)
    lk.write = slow_write
    try:
        app.sync_file(a, "notes", bg=True)
        app.sync_file(b, "notes")
        app.join_bg()
        pump()
    finally:
        lk.write = REAL_WRITE
    assert not lk.same(a["file"], b["file"]), f"beide → {a['file']}"
    assert "A" in body(a["file"]) and "B" in body(b["file"])


def t9_bundle_keeps_attachments():
    """.notes-Datei eines Freundes darf vorhandene Anhänge (data/pdfs) nicht überschreiben."""
    d = os.path.join(paths.DATA, "pdfs")
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, "abc.pdf")
    with open(p, "wb") as f:
        f.write(b"orig")
    share.write_files("x", {os.path.join("pdfs", "abc.pdf"): b"fremd"})
    with open(p, "rb") as f:
        assert f.read() == b"orig", "Anhang überschrieben"


def t10_coarse_fs_same_second():
    """FAT/SMB: Fremdänderung gleicher Größe in derselben (ganzen) Sekunde → trotzdem erkannt (Prüfsumme)."""
    app = App()
    n = new_note(app, "Grob", "aaaa")
    sec = int(time.time()) - 10
    os.utime(n["file"], ns=(sec * 10**9, sec * 10**9))
    lk.stamp(n)
    assert n.get("file_hash"), "kein Hash auf grobem Dateisystem"
    data = body(n["file"]).replace("aaaa", "bbbb")
    with open(n["file"], "w", encoding="utf-8") as f:
        f.write(data)
    os.utime(n["file"], ns=(sec * 10**9, sec * 10**9))
    assert app.reload_if_changed(n, "notes") and "bbbb" in n["text"], "Fremdänderung übersehen"


def t10b_size_change_same_mtime():
    app = App()
    n = new_note(app, "Groesse", "aaaa")
    ns = os.stat(n["file"]).st_mtime_ns
    with open(n["file"], "a", encoding="utf-8") as f:
        f.write("mehr\n")
    os.utime(n["file"], ns=(ns, ns))
    assert lk.differs(n) is True, "Größenänderung bei gleicher mtime übersehen"
    os.utime(n["file"], ns=(ns + 7, ns + 7))
    lk.stamp(n)
    assert lk.differs(n) is False


def t11_rename_while_bg_no_wait():
    """Umbenennen aus dem Hintergrund-Pfad wartet nicht auf den Faden, holt es danach nach."""
    app = App()
    n = new_note(app, "Alt2")
    old = n["file"]
    lk.write = slow_write
    try:
        n["text"] = "zwei"
        app.write_bg("notes", n)
        n["title"], n["text"] = "Neu2", "drei"
        t0 = time.time()
        app.sync_file(n, "notes", bg=True)
        waited = time.time() - t0
        app.join_bg()
        pump()
    finally:
        lk.write = REAL_WRITE
    assert waited < 0.15, f"Oberfläche stand {waited:.2f} s"
    assert not os.path.exists(old) and n["file"].endswith("Neu2.md") and "drei" in body(n["file"])


def t12_backup_has_files():
    """Sicherung enthält den Dateiordner; Wiederherstellen holt gelöschte Dateien (z. B. Projektbilder) zurück."""
    app = App()
    new_note(app, "Mit Bild", "x")
    img = os.path.join(app.docdir, "latex", "Projekt", "bild.png")
    os.makedirs(os.path.dirname(img))
    with open(img, "wb") as f:
        f.write(b"PNG")
    zipf = backup.backup_now(app.prefs["backup"]["dir"], 99, files_dir=app.docdir)
    os.remove(img)
    app.restore_backup(zipf)
    assert os.path.exists(img), "Datei aus dem notist-Ordner nicht zurückgeholt"


def t13_restore_rolls_back():
    """Scheitert das Ersetzen mittendrin, bleibt der alte Datenstand vollständig."""
    app = App()
    n = new_note(app, "Bleibt", "jetzt")
    zipf = backup.backup_now(app.prefs["backup"]["dir"], 99)
    before = set(os.listdir(os.path.dirname(paths.DATA)))
    real, calls = os.rename, [0]

    def flaky(a, b):
        calls[0] += 1
        if calls[0] == 3:
            raise OSError(28, "Kein Platz")
        return real(a, b)
    backup.os.rename = flaky
    try:
        backup.restore(zipf, app.prefs["backup"]["dir"])
        raise AssertionError("Fehler nicht weitergegeben")
    except OSError:
        pass
    finally:
        backup.os.rename = real
    m = st.Store(paths.NOTES).notes.get(n["id"])
    assert m and m["text"] == "jetzt", "Datenstand nach gescheitertem Wiederherstellen beschädigt"
    left = sorted(set(os.listdir(os.path.dirname(paths.DATA))) - before)
    assert not left, f"Reste: {left}"


def t14_doc_reopen_finds_entry():
    """.doc geöffnet (Änderungen → .docx daneben) und erneut geöffnet → derselbe Eintrag."""
    app = App()
    n = app.stores["docs"].create()
    src = os.path.join(T, "alt.doc")
    n.update(title="alt", text="x", source=src, file=os.path.join(T, "alt.docx"))
    app.stores["docs"].save(n)
    hit = app.source_hit(src)
    assert hit and hit[1] is n, "Eintrag über die Quelle nicht gefunden"


def t15_trash_stops_reminder_timer():
    app = App()
    app.view = "kind"
    app._undo = None
    app.notes_for_mode = lambda: []
    n = app.stores["notes"].create()
    n.update(title="Termin", text="x", reminder="2099-01-01T09:00", reminder_systemd=True)
    app.stores["notes"].save(n)
    notes.Notes.trash_entry(app, "notes", n)
    m = st.Store(paths.NOTES).notes[n["id"]]
    assert m["trashed"] and not m.get("reminder_systemd"), "Timer-Merker nicht zurückgesetzt"


def t16_bundle_private_fields():
    n = st.new_note("T", "x")
    n.update(file="/x/y.md", file_trashed=True, file_size=3, file_hash="ab")
    data = json.loads(share.bundle(n, "notes"))["note"]
    assert not {"file", "file_trashed", "file_size", "file_hash"} & set(data), set(data)


def t17_tmp_of_other_instance():
    """Frische *.json.tmp (zweite Instanz schreibt gerade) bleibt; alte Absturzreste werden weggeräumt."""
    os.makedirs(paths.NOTES, exist_ok=True)
    fresh, old = (os.path.join(paths.NOTES, f"{x}.json.tmp") for x in ("frisch", "alt"))
    for p in (fresh, old):
        with open(p, "w", encoding="utf-8") as f:
            f.write("{")
    os.utime(old, (time.time() - 3600, time.time() - 3600))
    st.Store(paths.NOTES)
    assert os.path.exists(fresh), "fremde, frische .json.tmp gelöscht"
    assert not os.path.exists(old), "Absturzrest bleibt liegen"
    os.remove(fresh)


TESTS = [v for k, v in sorted(globals().items()) if k.startswith("t") and k[1:2].isdigit() and callable(v)]

if __name__ == "__main__":
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else ""
    bad = 0
    for t in TESTS:
        if only and not t.__name__.startswith(only):
            continue
        try:
            t()
            print(f"ok    {t.__name__}")
        except Exception as e:  # noqa: BLE001
            bad += 1
            print(f"FEHL  {t.__name__}: {type(e).__name__}: {e}")
            if VERBOSE:
                import traceback
                traceback.print_exc()
    shutil.rmtree(T, ignore_errors=True)
    print(f"{bad} von {len(TESTS)} fehlgeschlagen" if bad else "alle grün")
    sys.exit(1 if bad else 0)
