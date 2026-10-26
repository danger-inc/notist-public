# Einstellungsfenster (Zahnrad oben rechts) und Tastenkürzel-Übersicht (F1).
import os, subprocess, sys

from gi.repository import Gio, GLib, Gtk, Pango

import backup
import chrome as ch
import dialogs
import i18n
import paths

CSS = """
.settings-side { background: none; padding: 4px 6px 10px 14px; }
.settings-side row { border-radius: 4px; padding: 3px 10px; margin: 1px 0; color: alpha(@foreground, 0.8);
    font-weight: bold; font-size: 13px; outline: none; }
.settings-side row:hover { background-color: alpha(@primary, 0.12); color: @foreground; }
.settings-side row:selected { background-color: alpha(@primary, 0.22); color: @foreground; }
.settings-side .key { color: @primary; }
.settings-side row:selected .key { color: @foreground; }
.settings-side .ticon { color: @primary; }
.settings-page { padding: 4px 14px 14px 8px; }
.settings-page .tpbody { padding: 4px 12px 10px 12px; }
.set-h { font-size: 13px; font-weight: bold; }
.set-sub { font-size: 12px; color: @secondary; }
.set-intro { font-size: 12px; color: @secondary; margin: 2px 2px 4px 2px; }
.set-row { padding: 7px 2px; }
.set-row + .set-row { border-top: 1px dashed alpha(@primary, 0.18); }
.set-title { font-weight: bold; font-size: 13px; }
.set-mono { font-family: monospace; font-size: 11px; color: @secondary; }
.kbd { font-family: monospace; font-weight: bold; font-size: 11px; color: @primary;
    border: 1px solid alpha(@primary, 0.45); border-radius: 4px; padding: 0 6px; }
.sc-desc { font-size: 12px; }
button.theme-card { background: none; background-image: none; border: 1px solid alpha(@primary, 0.25);
    border-radius: 6px; padding: 6px; box-shadow: none; }
button.theme-card label { font-size: 12px; font-weight: bold; }
button.theme-card:hover { border-color: alpha(@primary, 0.7); background-color: alpha(@primary, 0.06); }
button.theme-card:checked { border-color: @primary; background-color: alpha(@primary, 0.18); color: @foreground; }
window.settings button.pb, window.dlg button.pb.small { background: none; background-image: none; box-shadow: none;
    border: 1px solid alpha(@primary, 0.55); border-radius: 4px; padding: 1px 8px; min-height: 0; font-size: 12px;
    font-weight: bold; color: @foreground; }
window.settings button.pb:hover, window.dlg button.pb.small:hover { background-color: @primary; color: @on_primary;
    border-color: @primary; }
window.settings textview, window.settings textview text { background: none; color: @foreground; }
.set-words { border: 1px solid alpha(@primary, 0.35); border-radius: 4px; padding: 6px; }
"""

LANGS = [("de", "Deutsch"), ("en", "English")]
START = [("home", "Home (alles auf einen Blick)"), ("last", "Zuletzt benutzter Bereich"), ("notes", "Notizen"), ("docs", "Words"), ("latex", "LaTeX")]
INTERVALS = [(1, "stündlich"), (6, "alle 6 Stunden"), (24, "täglich"), (168, "wöchentlich")]


def row(title, sub, widget):
    r = Gtk.Box(spacing=12)
    r.add_css_class("set-row")
    v = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True, valign=Gtk.Align.CENTER)
    t = Gtk.Label(label=title, xalign=0, wrap=True)
    t.add_css_class("set-title")
    v.append(t)
    if sub:
        s = Gtk.Label(label=sub, xalign=0, wrap=True)
        s.add_css_class("set-sub")
        v.append(s)
    r.append(v)
    if widget:
        widget.set_valign(Gtk.Align.CENTER)
        r.append(widget)
    return r


def switch(prefs, key, default, cb=None):
    sw = Gtk.Switch(active=prefs.get(key, default))

    def changed(w, _):
        prefs[key] = w.get_active()
        cb and cb(w.get_active())
    sw.connect("notify::active", changed)
    return sw


def dropdown(options, current, cb):
    dd = Gtk.DropDown.new_from_strings([label for _, label in options])
    keys = [k for k, _ in options]
    dd.set_selected(keys.index(current) if current in keys else 0)
    dd.connect("notify::selected", lambda d, _: cb(keys[d.get_selected()]))
    return dd


def spin(lo, hi, value, cb, digits=0, step=1):
    sp = Gtk.SpinButton.new_with_range(lo, hi, step)
    sp.set_digits(digits)
    sp.set_value(value)
    sp.connect("value-changed", lambda s: cb(s.get_value()))
    return sp


class PageBox(Gtk.Box):
    """Seite der Einstellungen: alles nach head()/sec() landet im jeweiligen Kasten (Titel im Rahmen)."""

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.add_css_class("settings-page")
        self.panel = None

    def append(self, widget):
        if self.panel is not None:
            self.panel.body.append(widget)
        else:
            Gtk.Box.append(self, widget)

    def new_panel(self, title):
        if self.panel is not None and self.panel.body.get_first_child() is None:
            self.panel.set_title(ch.esc(i18n.tr(title).lower()))       # leerer Kasten: nur umbenennen
            return self.panel
        panel = ch.Panel(ch.esc(i18n.tr(title).lower()))     # gezeichnet → selbst übersetzen
        panel.body.set_vexpand(False)
        panel.body.set_spacing(0)
        Gtk.Box.append(self, panel)
        self.panel = panel
        return panel


class SettingsWindow(Gtk.Window):
    def __init__(self, app, page=None):
        super().__init__(title="Einstellungen", transient_for=app.win, modal=False, default_width=820,
                         default_height=600)
        self.add_css_class("settings")
        self.add_css_class("pb-window")
        self.app, self.prefs = app, app.prefs
        k = Gtk.EventControllerKey()
        k.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        k.connect("key-pressed", self.on_key)
        self.add_controller(k)
        box = Gtk.Box()
        dialogs.chrome(self, self.get_title(), box)
        side = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
        side.add_css_class("settings-side")
        side.set_size_request(200, -1)
        self.stack = Gtk.Stack(hexpand=True, transition_type=Gtk.StackTransitionType.CROSSFADE)
        pages = [("general", "󰒓", "allgemein", self.page_general), ("files", "󰉋", "dateien & datist", self.page_files),
                 ("backup", "󰁯", "sicherung", self.page_backup),
                 ("history", "󰋚", "verlauf", self.page_history), ("words", "󰈬", "words", self.page_words),
                 ("latex", "󰿈", "latex", self.page_latex), ("spell", "󰓆", "rechtschreibung", self.page_spell),
                 ("about", "󰋽", "über & systemcheck", self.page_about)]
        self.side = side
        for i, (key, icon, label, build) in enumerate(pages, 1):
            r = Gtk.ListBoxRow()
            r.key = key
            r.set_child(ch.hbox(ch.label(ch.SUP[i], "key"), ch.label(icon, "ticon"), ch.label(label), spacing=4))
            r.set_tooltip_text(f"{label} ({i})")
            side.append(r)
            sc = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER)
            inner = PageBox()
            build(inner)
            sc.set_child(inner)
            self.stack.add_named(sc, key)
        side.connect("row-selected", lambda lb, r: r and self.stack.set_visible_child_name(r.key))
        box.append(side)
        box.append(self.stack)
        start = page or "general"
        for i, (key, *_r) in enumerate(pages):
            if key == start:
                side.select_row(side.get_row_at_index(i))
        self.connect("close-request", lambda *_: (app.save_prefs(), False)[-1])

    def on_key(self, _c, kv, _code, state):
        if kv == 0xff1b:
            self.close()
            return True
        focus = self.get_focus()
        typing = isinstance(focus, (Gtk.Text, Gtk.TextView, Gtk.Entry))
        if not typing and 0x31 <= kv <= 0x39 and not state & 0x0c:      # 1–9 = Seite (wie die Tabs der Suite)
            row = self.side.get_row_at_index(kv - 0x31)
            if row:
                self.side.select_row(row)
                return True
        return False

    @staticmethod
    def head(box, title, sub=""):
        """Erster Kasten der Seite (Titel im Rahmen), darunter die Erklärung."""
        box.new_panel(title)
        if sub:
            s = Gtk.Label(label=sub, xalign=0, wrap=True)
            s.add_css_class("set-intro")
            box.append(s)

    @staticmethod
    def sec(box, title):
        box.new_panel(title)

    # ---------- Seiten ----------
    def page_general(self, box):
        import themes
        p = self.prefs
        self.head(box, "Allgemein")
        self.sec(box, "Design")
        box.append(themes.picker(on_change=self.app.load_css))
        hint = Gtk.Label(xalign=0, wrap=True, label="„Automatisch“ übernimmt die Farben deines Desktops (matugen), "
                                                     "falls vorhanden – dunkel oder hell nach Wahl. Das Design gilt für alle -ist-Apps. "
                                                     "Der Glas-Effekt oben rechts macht Fenster durchscheinend.")
        hint.add_css_class("set-sub")
        box.append(hint)
        self.sec(box, "Allgemein")
        box.append(row("Beim Start öffnen", "Welcher Bereich nach dem Start zu sehen ist",
                       dropdown(START, p.get("start_kind", "home"), lambda v: p.__setitem__("start_kind", v))))
        lang_note = Gtk.Label(xalign=0, wrap=True)
        lang_note.add_css_class("set-sub")

        def set_lang(v):
            if v != p.get("lang", "de"):
                p["lang"] = v
                self.app.save_prefs()
                lang_note.set_label("Wird nach einem Neustart von notist übernommen. / Applies after restarting notist.")
                self.app.quit_on_close = True      # beim Schließen wirklich beenden, damit es greift
        box.append(row("Sprache / Language", "Sprache der Oberfläche", dropdown(LANGS, p.get("lang", "de"), set_lang)))
        box.append(lang_note)
        box.append(row("Im Hintergrund weiterlaufen", "Schließen blendet notist nur aus – der nächste Start geht sofort",
                       switch(p, "background", True)))
        box.append(row("Markdown verstehen", "**fett**, *kursiv*, # Überschrift, - Liste, [ ] Checkliste beim Tippen "
                       "und Einfügen in Notizen und Words umwandeln",
                       switch(p, "markdown", True, lambda on: p.setdefault("writer", {}).__setitem__("markdown", on))))
        af = p.setdefault("autofmt", {})
        box.append(row("Typografie beim Tippen", "„Anführungszeichen“, -- wird –, ... wird …, -> wird → "
                       "(Notizen und Words)", switch(af, "typo", True)))
        box.append(row("Satzanfang groß", "Ersten Buchstaben eines Satzes automatisch groß schreiben",
                       switch(af, "autocap", False)))
        box.append(row("Smarte Korrekturen", "SChreibstift → Schreibstift, hALLO → Hallo, Tset → Test, teh → the – "
                       "Rücktaste direkt danach macht es rückgängig (mehr unter Rechtschreibung)",
                       switch(af, "smart", True)))
        box.append(row("Listen automatisch fortsetzen", "„- “ wird •, Enter setzt Aufzählungen und Checklisten fort",
                       switch(p, "auto_lists", True)))
        box.append(row("Mitscrollen beim Schreiben", "Die Zeile, in der du schreibst, bleibt etwa auf halber Höhe – "
                       "unten ist immer eine halbe Seite Luft", switch(p, "typewriter", True,
                                                                      lambda _: self.app.apply_typewriter())))
        box.append(row("Stelle beim Wechseln merken", "Zurück aus einem anderen Modus (Home, Notizen, Words, LaTeX) "
                       "landest du wieder dort, wo du warst", switch(p, "keep_pos", True)))
        box.append(row("Knopf „zur letzten Stelle“", "Beim Öffnen eines Eintrags erscheint kurz ein Knopf, der an die "
                       "zuletzt bearbeitete Stelle springt", switch(p, "jump_btn", True,
                                                                    lambda on: on or self.app.hide_jump())))
        box.append(row("Notizen in der Liste zählen", "Zeigt unten die Wortzahl im Notizen-Bereich",
                       switch(p, "show_words", True, lambda _: self.app.update_meta())))

    def page_files(self, box):
        import linked as lk
        import reminders as rem
        f = lk.settings(self.prefs)
        self.head(box, "Dateien", "notist bearbeitet geöffnete Dateien direkt – es entstehen keine Kopien. Home ist "
                                  "eine Sammlung von Verknüpfungen: Jeder Eintrag zeigt unten, in welcher Datei er "
                                  "steht. Neue Einträge werden als normale Dateien abgelegt (Notizen .md, Words .docx, "
                                  "LaTeX als Ordner mit main.tex). Dateien, die du in diesen Ordner legst, erscheinen "
                                  "automatisch in notist.")
        box.append(row("Neue Einträge als Datei speichern", "Aus: neue Einträge liegen nur in notist (wie früher)",
                       switch(f, "new_as_files", True)))
        self.files_label = Gtk.Label(label=f["dir"], xalign=0, ellipsize=Pango.EllipsizeMode.MIDDLE, hexpand=True)
        self.files_label.add_css_class("set-mono")
        dr = Gtk.Box(spacing=6)
        for label, cb in (("Ändern …", self.pick_files_dir), ("Öffnen", lambda *_: self.open_dir(f["dir"]))):
            btn = Gtk.Button(label=label)
            btn.add_css_class("pb"); btn.add_css_class("small")
            btn.connect("clicked", cb)
            dr.append(btn)
        r = row("Ordner für neue Einträge", "mit Unterordnern notizen/, words/, latex/", dr)
        r.get_first_child().append(self.files_label)
        box.append(r)
        internal = sum(1 for st_ in self.app.stores.values() for n in st_.notes.values()
                       if not n.get("file") and not n.get("trashed") and (n["title"].strip() or n["text"].strip()))
        mig = Gtk.Button(label=f"󰉋  {internal} ältere Einträge als Dateien ablegen", halign=Gtk.Align.START,
                         sensitive=internal > 0)
        mig.add_css_class("pb")
        self.mig_state = Gtk.Label(xalign=0, wrap=True)
        self.mig_state.add_css_class("set-sub")

        def migrate(b):
            n = self.app.files_to_disk()
            b.set_sensitive(False)
            self.mig_state.set_label(f"{n} Einträge liegen jetzt in {f['dir']}")
            self.app.save_prefs()
        mig.connect("clicked", migrate)
        h = Gtk.Box(spacing=10)
        h.append(mig)
        h.append(self.mig_state)
        box.append(row("Einträge aus der Zeit vor v4.4", "Liegen bisher nur in notist. Auf Wunsch kommen sie als "
                                                         "Dateien in den Ordner oben (notist behält die Verknüpfung).",
                       None))
        box.append(h)

        self.sec(box, "Erinnerungen in datist")
        d = self.prefs.setdefault("datist", {})
        if not rem.datist_available():
            box.append(row("datist ist nicht installiert", "Erinnerungen erscheinen dann nur als Benachrichtigung.",
                           None))
            return
        box.append(row("Erinnerungen als Termine zeigen", "Jede Erinnerung erscheint in datist als 15-Minuten-Termin "
                                                         "„󰂚 Titel“; „öffnen“ im Termin springt zurück zum Eintrag",
                       switch(d, "on", True, lambda _: self.app.queue_datist())))
        cals = rem.datist_calendars()

        def set_cal(v):
            d["cal"] = v
            self.app.save_prefs()
            self.app.queue_datist()
        box.append(row("Kalender", "Lokal bleibt auf diesem Rechner, ein Google-Kalender ist auch am Handy zu sehen",
                       dropdown(cals, d.get("cal", "local"), set_cal)))

    def pick_files_dir(self, *_):
        import linked as lk
        dlg = Gtk.FileDialog(title="Ordner für neue Einträge")
        f = lk.settings(self.prefs)
        try:
            os.makedirs(os.path.expanduser(f["dir"]), exist_ok=True)
            dlg.set_initial_folder(Gio.File.new_for_path(os.path.expanduser(f["dir"])))
        except OSError:
            pass

        def done(d, res):
            try:
                folder = d.select_folder_finish(res)
            except GLib.Error:
                return
            f["dir"] = folder.get_path().replace(os.path.expanduser("~"), "~", 1)
            self.files_label.set_label(f["dir"])
            self.app.save_prefs()
            self.app.scan_files()
        dlg.select_folder(self, None, done)

    def set_theme(self, key):
        self.prefs["theme"] = key
        self.app.save_prefs()
        self.app.load_css()

    def page_backup(self, box):
        b = backup.defaults(self.prefs)
        self.head(box, "Sicherung", "notist sichert alle Notizen, Dokumente, LaTeX-Projekte und den Verlauf als ZIP-Datei. "
                                    "Tipp: Wähle als Ziel einen Cloud-Ordner (Nextcloud, Syncthing, Dropbox …), "
                                    "dann liegt jede Sicherung automatisch auch dort.")
        sw = Gtk.Switch(active=b["on"])
        sw.connect("notify::active", lambda w, _: b.__setitem__("on", w.get_active()))
        box.append(row("Automatisch sichern", "Beim Start und im laufenden Betrieb, sobald fällig", sw))
        box.append(row("Wie oft", None, dropdown([(str(h), l) for h, l in INTERVALS], str(b["hours"]),
                                                 lambda v: b.__setitem__("hours", int(v)))))
        box.append(row("Wie viele behalten", "Ältere automatische Sicherungen werden gelöscht",
                       spin(1, 365, b["keep"], lambda v: b.__setitem__("keep", int(v)))))
        self.dest_label = Gtk.Label(label=b["dir"], xalign=0, ellipsize=Pango.EllipsizeMode.MIDDLE, hexpand=True)
        self.dest_label.add_css_class("set-mono")
        dr = Gtk.Box(spacing=6)
        for label, cb in (("Ändern …", self.pick_dest), ("Öffnen", lambda *_: self.open_dir(b["dir"]))):
            btn = Gtk.Button(label=label)
            btn.add_css_class("pb"); btn.add_css_class("small")
            btn.connect("clicked", cb)
            dr.append(btn)
        r = row("Ziel-Ordner", None, dr)
        r.get_first_child().append(self.dest_label)
        box.append(r)
        now = Gtk.Button(label="󰁯  Jetzt sichern", halign=Gtk.Align.START)
        now.add_css_class("pb")
        self.backup_state = Gtk.Label(xalign=0, wrap=True)
        self.backup_state.add_css_class("set-sub")
        now.connect("clicked", lambda *_: self.do_backup())
        h = Gtk.Box(spacing=10)
        h.append(now)
        h.append(self.backup_state)
        box.append(h)
        self.sec(box, "Vorhandene Sicherungen")
        self.backup_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.append(self.backup_list)
        self.fill_backups()

    def fill_backups(self):
        b = backup.defaults(self.prefs)
        lst = self.backup_list
        while (c := lst.get_first_child()):
            lst.remove(c)
        items = backup.list_backups(os.path.expanduser(b["dir"]))
        if not items:
            l = Gtk.Label(label="Noch keine Sicherung vorhanden.", xalign=0)
            l.add_css_class("set-sub")
            lst.append(l)
        for path in items[:40]:
            when, info = backup.describe(path)
            btn = Gtk.Button(label="Wiederherstellen")
            btn.add_css_class("pb"); btn.add_css_class("small")
            btn.confirm = False

            def restore(bt, p=path):
                if not bt.confirm:
                    bt.confirm = True
                    bt.set_label("Sicher? Aktueller Stand wird ersetzt")
                    GLib.timeout_add(4000, lambda: (setattr(bt, "confirm", False), bt.set_label("Wiederherstellen"),
                                                    False)[-1])
                    return
                self.app.restore_backup(p)
                self.fill_backups()
            btn.connect("clicked", restore)
            lst.append(row(when, info, btn))

    def do_backup(self):
        self.backup_state.set_label("Sichert …")

        def done(path, err):
            self.backup_state.set_label(f"Fehler: {err}" if err else f"Gespeichert: {os.path.basename(path)}")
            self.app.save_prefs()
            self.fill_backups()
        backup.run_async(self.prefs, done)

    def pick_dest(self, *_):
        dlg = Gtk.FileDialog(title="Ordner für Sicherungen")

        def done(d, res):
            try:
                f = d.select_folder_finish(res)
            except GLib.Error:
                return
            b = backup.defaults(self.prefs)
            b["dir"] = f.get_path()
            self.dest_label.set_label(b["dir"])
            self.app.save_prefs()
            self.fill_backups()
        dlg.select_folder(self, None, done)

    @staticmethod
    def open_dir(path):
        path = os.path.expanduser(path)
        os.makedirs(path, exist_ok=True)
        Gio.AppInfo.launch_default_for_uri(Gio.File.new_for_path(path).get_uri(), None)

    def page_history(self, box):
        h = self.prefs.setdefault("history", {})
        import store
        self.head(box, "Versionsverlauf", "Beim Schreiben merkt sich notist frühere Stände jeder Notiz und jedes Dokuments. "
                                          "Über „Mehr → Verlauf“ unten im Editor holst du sie zurück.")

        def set_min(v):
            h["minutes"] = int(v)
            store.HISTORY_MINUTES = int(v)

        def set_max(v):
            h["max"] = int(v)
            store.HISTORY_MAX = int(v)
        box.append(row("Abstand zwischen Versionen", "Minuten – während du schreibst", spin(1, 120, h.get("minutes", 5), set_min)))
        box.append(row("Versionen je Eintrag", "Ältere werden gelöscht", spin(5, 500, h.get("max", 60), set_max)))

    def page_words(self, box):
        w = self.prefs.setdefault("writer", {})
        self.head(box, "Words", "Grundeinstellungen für die Textverarbeitung.")
        fonts = sorted({f.get_name() for f in self.get_pango_context().list_families()}, key=str.lower)
        cur = w.get("font", "Noto Sans")
        opts = [(f, f) for f in fonts] if cur in fonts else [(cur, cur)] + [(f, f) for f in fonts]
        import writer
        fd = writer.font_dropdown(dropdown(opts, cur, lambda v: w.__setitem__("font", v)))
        box.append(row("Standardschrift", "Schrift der Formatvorlage „Standard“ (auch im Export). Gilt nach Neustart.", fd))
        box.append(row("Standardgröße (pt)", "Gilt nach Neustart", spin(8, 20, w.get("size", 11), lambda v: w.__setitem__("size", v),
                                                                        digits=1, step=0.5)))
        box.append(row("Seitenränder für neue Dokumente (cm)", "Oben, rechts, unten, links – einzeln änderbar im Reiter Layout",
                       spin(0.5, 5, w.get("margin", 2.5), lambda v: w.__setitem__("margin", round(v, 2)), digits=1, step=0.1)))
        box.append(row("Helles Papier", "Weiße Seite statt Theme-Farben",
                       switch(w, "light_paper", False, lambda on: self.app.writer.tools["paper"].set_active(on))))

    def page_latex(self, box):
        L = self.prefs.setdefault("latex", {})
        import latex
        self.head(box, "LaTeX")
        comps = latex.find_compilers()
        opts = [("auto", "Automatisch (" + (comps[0][0] if comps else "keiner gefunden") + ")")] + [(n, n) for n, _ in comps]
        box.append(row("Compiler", "Welches Programm aus dem Quelltext ein PDF macht",
                       dropdown(opts, L.get("compiler", "auto"), lambda v: (L.__setitem__("compiler", v),
                                                                            self.app.latex.refresh_compilers()))))
        box.append(row("Live-Vorschau", "Beim Tippen automatisch neu kompilieren", switch(L, "live", True,
                                                                                          lambda on: self.app.latex.live_btn.set_active(on))))
        for key, title, sub in (("hints", "Vorschläge beim Tippen", "Sonst nur mit Strg+Leertaste"),
                                ("autoclose", "Klammern schließen", "{ ergänzt }"),
                                ("lists", "Listen fortsetzen", "Enter nach \\item beginnt den nächsten Punkt"),
                                ("auto_problems", "Fehlerliste automatisch zeigen", None),
                                ("formula_preview", "Formel-Vorschau", "Zeigt die Formel unter dem Cursor gerendert an"),
                                ("spell", "Rechtschreibung im Quelltext", "Prüft nur den Fließtext, keine Befehle")):
            box.append(row(title, sub, switch(L, key, True, lambda on, k=key: self.app.latex.setting_changed(k))))

    def page_spell(self, box):
        import spell
        sp = spell.speller()
        self.head(box, "Rechtschreibung", f"Wörterbücher: {', '.join(sp.langs)}" if sp.available else
                  f"Keine Wörterbücher gefunden. Installieren mit: {spell.INSTALL_HINT}")
        box.append(row("Rechtschreibprüfung", "In Notizen und Words (LaTeX: siehe dort)",
                       switch(self.prefs, "spell", True, lambda on: self.app.set_spell(on))))
        box.append(row("Standardsprache neuer Dokumente",
                       "Jedes Dokument hat unten in der Leiste seinen DE/EN-Knopf: Rechtschreibung und Anführungszeichen "
                       "(„…“ oder “…”) richten sich danach",
                       dropdown([("de", "Deutsch"), ("en", "English")], self.app.default_lang(),
                                lambda v: (self.prefs.__setitem__("doc_lang", v), self.app.save_prefs(),
                                           self.app.apply_doc_lang()))))
        have = spell.installed_langs()

        def lang_cb(code):
            def cb(on):
                langs = [c for c in spell.VARIANTS if c != code and c in self.prefs.get("spell_langs", spell.DEFAULT_LANGS)]
                if on:
                    langs.append(code)
                self.prefs["spell_langs"] = [c for c in spell.VARIANTS if c in langs]
                self.app.set_spell_langs(self.prefs["spell_langs"])
            return cb
        for code, name in spell.LANG_NAMES.items():
            sw = Gtk.Switch(active=code in self.prefs.get("spell_langs", spell.DEFAULT_LANGS) and code in have)
            sw.set_sensitive(code in have)
            sw.connect("notify::active", lambda w, _, cb=lang_cb(code): cb(w.get_active()))
            box.append(row(name, ", ".join(n for n in spell.VARIANTS[code][:1]) if code in have else
                           f"Kein Wörterbuch gefunden – {spell.INSTALL_HINT}", sw))
        af = self.prefs.setdefault("autofmt", {})
        self.sec(box, "Smarte Korrekturen")
        box.append(row("Beim Tippen korrigieren", "Nach Leerzeichen oder Satzzeichen: SChreibstift → Schreibstift, "
                       "hALLO → Hallo, vertauschte Buchstaben (Tset → Test), Nomen groß (schreibstift → Schreibstift), "
                       "häufige Tippfehler (teh → the, nciht → nicht). Rücktaste direkt danach macht es rückgängig.",
                       switch(af, "smart", True)))
        box.append(Gtk.Label(label="Eigene Ersetzungen – eine pro Zeile: falsch = richtig", xalign=0, css_classes=["set-sub"]))
        ac_tv = Gtk.TextView(monospace=True, wrap_mode=Gtk.WrapMode.NONE)
        ac_tv.get_buffer().set_text("\n".join(f"{k} = {v}" for k, v in (self.prefs.get("autocorrect") or {}).items()))
        ac_sc = Gtk.ScrolledWindow(min_content_height=120)
        ac_sc.add_css_class("set-words")
        ac_sc.set_child(ac_tv)
        box.append(ac_sc)
        ac_save = Gtk.Button(label="Speichern", halign=Gtk.Align.START)
        ac_save.add_css_class("pb"); ac_save.add_css_class("small")

        def save_ac(*_):
            b = ac_tv.get_buffer()
            table = {}
            for line in b.get_text(b.get_start_iter(), b.get_end_iter(), False).split("\n"):
                if "=" in line:
                    k, v = (x.strip() for x in line.split("=", 1))
                    if k and v and k != v:
                        table[k] = v
            self.prefs["autocorrect"] = table
            self.app.save_prefs()
            self.app.notify(f"{len(table)} eigene Ersetzungen gespeichert")
        ac_save.connect("clicked", save_ac)
        box.append(ac_save)
        self.sec(box, "Eigene Wörter (eins pro Zeile)")
        tv = Gtk.TextView(monospace=True, wrap_mode=Gtk.WrapMode.NONE)
        try:
            tv.get_buffer().set_text(open(paths.WORDS).read())
        except OSError:
            pass
        sc = Gtk.ScrolledWindow(min_content_height=220)
        sc.add_css_class("set-words")
        sc.set_child(tv)
        box.append(sc)
        save = Gtk.Button(label="Speichern", halign=Gtk.Align.START)
        save.add_css_class("pb"); save.add_css_class("small")

        def do_save(*_):
            b = tv.get_buffer()
            words = sorted({w.strip() for w in b.get_text(b.get_start_iter(), b.get_end_iter(), False).split("\n") if w.strip()})
            os.makedirs(os.path.dirname(paths.WORDS), exist_ok=True)
            with open(paths.WORDS, "w") as f:
                f.write("\n".join(words) + ("\n" if words else ""))
            spell.reload_words()
            self.app.notify("Eigene Wörter gespeichert")
        save.connect("clicked", do_save)
        box.append(save)

    def page_about(self, box):
        here = self.app.here
        self.head(box, f"notist {self.app.version}", "Notizen · Words · LaTeX")
        r = Gtk.Box(spacing=6)
        for label, path in (("Datenordner öffnen", paths.DATA), ("Programmordner öffnen", here)):
            b = Gtk.Button(label=label)
            b.add_css_class("pb"); b.add_css_class("small")
            b.connect("clicked", lambda *_, p=path: self.open_dir(p))
            r.append(b)
        box.append(r)
        self.sec(box, "Systemcheck")
        out = Gtk.Label(xalign=0, selectable=True, wrap=True)
        out.add_css_class("set-mono")
        box.append(out)
        try:
            res = subprocess.run([sys.executable, os.path.join(here, "notes.py"), "--check", "--plain"],
                                 capture_output=True, text=True, timeout=20)
            out.set_label(res.stdout.strip())
        except (OSError, subprocess.SubprocessError) as e:
            out.set_label(str(e))
        self.sec(box, "Änderungen")
        b = Gtk.Button(label="󰋚  changelog", halign=Gtk.Align.START)
        b.add_css_class("pb"); b.add_css_class("small")
        b.connect("clicked", lambda *_: self.app.show_changelog(self))
        box.append(b)


SHORTCUTS = [
    ("Überall", [("Strg+N", "Neu"), ("Strg+O", "Datei öffnen"), ("Strg+F", "Im Eintrag suchen"), ("Strg+Umschalt+F", "In allen suchen"), ("Strg+Umschalt+T", "Übersetzer Deutsch ⇄ Englisch"), ("Strg+T", "Liste aufklappen (schmales Fenster)"),
                 ("Alt+1 / 2 / 3", "Notizen / Words / LaTeX"), ("Strg+P", "Anheften"),
                 ("Strg+Umschalt+A", "Archivieren"), ("Rechtsklick auf Ordner", "Neu, Unterordner, umbenennen, auflösen"), ("Strg+,", "Einstellungen"), ("F1", "Diese Übersicht"),
                 ("Strg+W / Strg+Q", "Schließen")]),
    ("Notizen", [("Strg+B / I / U", "Fett / Kursiv / Unterstrichen"), ("Strg+Umschalt+L", "Checkliste"),
                 ("Strg+V", "Bild aus der Zwischenablage einfügen"), ("Tab im Titel", "In den Text springen")]),
    ("Words", [("Strg+B / I / U / D", "Fett / Kursiv / Unterstrichen / Durchgestrichen"),
               ("Strg+Umschalt++ / Strg+#", "Hoch- / Tiefgestellt"), ("Strg+L / E / R / J", "Links / Zentriert / Rechts / Blocksatz"),
               ("Strg+0 / 1 / 2 / 3", "Standard / Überschrift 1–3"), ("Strg+Umschalt+L / N", "Aufzählung / Nummerierung"),
               ("Tab / Umschalt+Tab", "Einzug in Listen"), ("Strg+Enter", "Seitenumbruch"), ("Strg+K", "Link"),
               ("Strg+H", "Suchen & Ersetzen"), ("Strg+Leertaste", "Formatierung löschen"),
               ("Strg+Umschalt+> / <", "Schrift größer / kleiner"), ("Strg++ / Strg+−", "Zoom"),
               ("Strg+Z / Strg+Umschalt+Z", "Rückgängig / Wiederholen"), ("Strg+F1", "Menüband ein-/ausklappen"),
               ("/ (Ansicht „fließend“)", "Blockmenü: Überschrift, Liste, Tabelle …")]),
    ("LaTeX", [("Strg+S / Strg+Enter", "Kompilieren"), ("Strg+Leertaste", "Vorschläge zeigen"),
               ("Tab", "Vorschlag übernehmen / nächstes Feld"), ("Esc", "Vorschläge schließen"),
               ("Strg+B / I / U", "\\textbf / \\textit / \\underline um die Markierung"), ("Strg+M", "Formel $…$"),
               ("Strg+7", "Zeilen aus-/einkommentieren"), ("Strg+Klick ins PDF", "Zur Stelle im Quelltext springen"),
               ("Strg+J", "Aktuelle Zeile im PDF zeigen"), ("Strg+F", "Im Quelltext suchen"), ("F1 im Editor", "Befehlsübersicht")]),
]


class ShortcutsWindow(Gtk.Window):
    def __init__(self, parent):
        super().__init__(title="Tastenkürzel", transient_for=parent, default_width=760, default_height=640)
        self.add_css_class("shortcuts")
        self.add_css_class("pb-window")
        k = Gtk.EventControllerKey()
        k.connect("key-pressed", lambda c, kv, *_: kv in (0xff1b, 0xffbe) and (self.close() or True))
        self.add_controller(k)
        sc = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER)
        flow = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, max_children_per_line=2, min_children_per_line=1,
                           column_spacing=24, row_spacing=12, homogeneous=False, valign=Gtk.Align.START)
        flow.add_css_class("settings-page")
        for title, items in SHORTCUTS:
            v = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            h = Gtk.Label(label=title.upper(), xalign=0)
            h.add_css_class("set-sec")
            v.append(h)
            grid = Gtk.Grid(column_spacing=12, row_spacing=6)
            for i, (keys, desc) in enumerate(items):
                kl = Gtk.Label(label=keys, xalign=0)
                kl.add_css_class("kbd")
                kl.set_halign(Gtk.Align.START)
                grid.attach(kl, 0, i, 1, 1)
                d = Gtk.Label(label=desc, xalign=0, wrap=True, max_width_chars=34)
                d.add_css_class("sc-desc")
                grid.attach(d, 1, i, 1, 1)
            v.append(grid)
            flow.append(v)
        sc.set_child(flow)
        dialogs.chrome(self, self.get_title(), sc)
