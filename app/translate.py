# Übersetzer-Leiste (GTK). Wörterbuch-Aufbau und -Abfrage stecken seit 5.0 in core/dictdb.py.
import re
import threading

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, GLib, Gtk  # noqa: E402

import i18n  # noqa: E402
import paths  # noqa: E402
from core import dictdb  # noqa: E402
from core.dictdb import *  # noqa: F401,F403,E402
from core.dictdb import (DICT_DIR, DB, URL, LOCAL, ONLINE, DB_VERSION, WIKDICT_URL, WIKDICT_DIR, LANGS, WD_TYPES,  # noqa: F401,E402
                         WORDTYPES, TYPE_OF, ARTICLE, FILLER, NOTE)

dictdb.UI_CALL = lambda fn: GLib.idle_add(lambda: (fn(), False)[1])

# ---------------- Fenster ----------------
CSS = """
.trx { background-color: alpha(@background, 0.97); border: 1px solid @primary; border-radius: 8px;
    padding: 8px 10px 6px 10px; box-shadow: 0 6px 22px alpha(black, 0.35); }
.trx .trx-title { font-weight: 800; color: @primary; }
.trx button.trx-dir { padding: 0 8px; min-height: 22px; font-size: 11px; border-radius: 4px; }
.trx button.trx-dir { background-image: none; box-shadow: none; }
.trx button.trx-dir:checked, .trx button.trx-dir:checked:hover { background-color: @primary; background-image: none;
    color: @on_primary; }
.trx entry { margin: 6px 0 4px 0; }
.trx .trx-sec { font-size: 11px; font-weight: 800; color: @secondary; margin-top: 8px; }
.trx .trx-type { font-size: 11px; font-weight: 800; color: @primary; margin-top: 6px; }
.trx .trx-ctx { font-size: 11px; color: alpha(@foreground, 0.55); }
.trx button.trx-word { padding: 1px 7px; min-height: 0; border-radius: 4px; border: 1px solid alpha(@primary, 0.45);
    background: none; font-weight: 600; }
.trx button.trx-word:hover { background-color: @primary; color: @on_primary; }
.trx .trx-art { font-size: 11px; color: alpha(@foreground, 0.5); }
.trx button.trx-phrase { padding: 2px 6px; min-height: 0; border: none; background: none; border-radius: 4px; }
.trx button.trx-phrase:hover { background-color: alpha(@primary, 0.18); }
.trx .trx-src { font-size: 11px; color: alpha(@foreground, 0.6); }
.trx .trx-foot { font-size: 10px; color: alpha(@foreground, 0.45); margin-top: 4px; }
.trx .trx-ok { color: @primary; font-weight: 800; }
.trx .trx-empty { color: alpha(@foreground, 0.6); margin: 8px 0; }
.trx progressbar trough { min-height: 4px; } .trx progressbar progress { min-height: 4px; background-color: @primary; }
"""


class Translator(Gtk.Revealer):
    """Kleines Übersetzer-Fenster für die rechte untere Ecke (als Overlay). show_for(text) öffnet es mit Text."""

    def __init__(self, prefs, save_prefs):
        super().__init__(transition_type=Gtk.RevealerTransitionType.SLIDE_UP, transition_duration=160,
                         halign=Gtk.Align.END, valign=Gtk.Align.END, margin_end=10, margin_bottom=8,
                         reveal_child=False, can_target=False)
        self.prefs, self.save_prefs = prefs, save_prefs
        self.dict = Dictionary()
        self.wd = {}                     # Sprache → WikDict
        self.lang_mode = False           # Sprachliste statt Ergebnissen
        self.online_btn = None
        self._fresh = False              # nach einer Suche: nächster Klick ins Feld markiert alles
        self.on_toggled = None
        self._timer = 0
        self._installing = False
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0, width_request=380)
        box.add_css_class("trx")
        head = Gtk.Box(spacing=4)
        t = Gtk.Label(label="übersetzer", xalign=0, hexpand=True)
        t.add_css_class("trx-title")
        head.append(t)
        self.dir_btns = {}
        group = None
        self.lang_btn = Gtk.Button(focus_on_click=False, tooltip_text="Sprache wählen / weitere laden")
        self.lang_btn.add_css_class("trx-dir")
        self.lang_btn.connect("clicked", lambda *_: self.show_langs(not self.lang_mode))
        head.append(self.lang_btn)
        for key, text, tip in (("auto", "auto", "Sprache selbst erkennen"),
                               ("de", "de → en", "Deutsch nach …"), ("en", "en → de", "… nach Deutsch")):
            b = Gtk.ToggleButton(label=text, tooltip_text=tip, focus_on_click=False)
            b.add_css_class("trx-dir")
            if group:
                b.set_group(group)
            group = group or b
            b.connect("toggled", lambda btn, k=key: btn.get_active() and self.set_dir(k))
            self.dir_btns[key] = b
            head.append(b)
        x = Gtk.Button(label="󰅖", tooltip_text="Schließen (Esc oder Strg+Umschalt+T)", focus_on_click=False)
        x.add_css_class("trx-dir")
        x.connect("clicked", lambda *_: self.toggle(False))
        head.append(x)
        box.append(head)
        self.entry = Gtk.SearchEntry(placeholder_text="Wort oder Satz – Deutsch oder Englisch")
        self.entry.connect("search-changed", self.on_changed)
        self.entry.connect("activate", lambda *_: self.on_enter())
        # 1. Klick ins Feld nach einer Suche markiert alles (gleich lostippen), Doppelklick ebenso
        click = Gtk.GestureClick(propagation_phase=Gtk.PropagationPhase.CAPTURE)
        click.connect("pressed", self.on_entry_press)
        self.entry.add_controller(click)
        fc = Gtk.EventControllerFocus()
        fc.connect("leave", lambda *_: setattr(self, "_fresh", bool(self.entry.get_text())))
        self.entry.add_controller(fc)
        self.entry.connect("stop-search", lambda *_: self.toggle(False))
        box.append(self.entry)
        self.results = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.scroll = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER, propagate_natural_height=True,
                                         max_content_height=380)
        self.scroll.set_child(self.results)
        box.append(self.scroll)
        foot = Gtk.Box(spacing=6)
        self.status = Gtk.Label(label="", xalign=0, hexpand=True, ellipsize=3)
        self.status.add_css_class("trx-foot")
        foot.append(self.status)
        src = Gtk.Label(label="wörterbuch: tu chemnitz (ding)", xalign=1)
        src.add_css_class("trx-foot")
        foot.append(src)
        self.src_lbl = src
        box.append(foot)
        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self.on_key)
        box.add_controller(keys)
        self.set_child(box)
        d = self.settings().get("dir", "auto")
        self.dir_btns.get(d, self.dir_btns["auto"]).set_active(True)
        self.first = None
        self.update_lang_ui()

    def settings(self):
        return self.prefs.setdefault("translator", {})

    # ---------- Sprache ----------
    def lang(self):
        lg = self.settings().get("lang", "en")
        return lg if lg == "en" or lg in wd_installed() else "en"

    def source(self):
        lg = self.lang()
        if lg == "en":
            return self.dict
        if lg not in self.wd:
            self.wd[lg] = WikDict(lg)
        return self.wd[lg]

    def update_lang_ui(self):
        lg = self.lang()
        self.lang_btn.set_label(f"󰗊 {lg} ▾" if not self.lang_mode else f"󰗊 {lg} ▴")
        self.dir_btns["de"].set_label(f"de → {lg}")
        self.dir_btns["en"].set_label(f"{lg} → de")
        name = i18n.tr(LANGS.get(lg, lg))
        self.dir_btns["de"].set_tooltip_text(i18n.tr("Deutsch nach {}", name))
        self.dir_btns["en"].set_tooltip_text(i18n.tr("{} nach Deutsch", name))
        self.src_lbl.set_label("wörterbuch: tu chemnitz (ding)" if lg == "en" else "wörterbuch: wikdict (wiktionary)")

    def set_lang(self, lg):
        self.settings()["lang"] = lg
        self.save_prefs()
        self.lang_mode = False
        self.update_lang_ui()
        self.queue(0)
        self.entry.grab_focus()

    def show_langs(self, on=True):
        self.lang_mode = on
        self.update_lang_ui()
        self.queue(0)

    def render_langs(self):
        self.label("sprache", "trx-sec")
        have = wd_installed()
        cur = self.lang()
        busy = getattr(self, "_wd_busy", None)
        for k, name in LANGS.items():
            ok = k == "en" or k in have
            row = Gtk.Box(spacing=6)
            b = Gtk.Button(focus_on_click=False, hexpand=True, sensitive=ok)
            b.add_css_class("trx-phrase")
            lab = Gtk.Label(label=f"{'●' if k == cur else ' '} {k}  {i18n.tr(name)}", xalign=0)
            b.set_child(lab)
            b.connect("clicked", lambda _b, kk=k: self.set_lang(kk))
            row.append(b)
            if k == "en":
                row.append(self.small("eingebaut", "trx-ctx"))
            elif ok:
                x = Gtk.Button(label="󰆴", focus_on_click=False, tooltip_text=i18n.tr("{} wieder löschen", name))
                x.add_css_class("trx-dir")
                x.connect("clicked", lambda _b, kk=k: self.remove_lang(kk))
                row.append(x)
            else:
                d = Gtk.Button(label="⟳ lädt …" if busy == k else "󰇚 laden (~35 MB)", focus_on_click=False,
                               sensitive=busy is None)
                d.add_css_class("trx-dir")
                d.connect("clicked", lambda _b, kk=k: self.install_lang(kk))
                row.append(d)
            self.results.append(row)
        self.label("Wörterbücher aus Wiktionary (wikdict.com, CC BY-SA) – einmal laden, danach offline. "
                   "Sätze übersetzt „online“ in jeder Sprache.", "trx-ctx")

    def small(self, text, cls):
        lab = Gtk.Label(label=text)
        lab.add_css_class(cls)
        return lab

    def install_lang(self, lg):
        self._wd_busy = lg
        self.queue(0)

        def progress(text, frac):
            self.status.set_label(text)

        def done(err):
            self._wd_busy = None
            if err:
                self.status.set_label(i18n.tr("Fehler: {}", err))
                self.queue(0)
            else:
                self.status.set_label(i18n.tr("{} bereit", i18n.tr(LANGS.get(lg, lg)).lower()))
                self.set_lang(lg)
        wd_install(lg, progress, done)

    def remove_lang(self, lg):
        w = self.wd.pop(lg, None)
        if w:
            for c in w.cons.values():
                c.close()
        wd_remove(lg)
        if self.settings().get("lang") == lg:
            self.settings()["lang"] = "en"
            self.save_prefs()
        self.update_lang_ui()
        self.queue(0)

    # ---------- Eingabe ----------
    def on_changed(self, *_):
        if not self.entry.get_text() and self.is_open() and not self.entry_focused():
            self.entry.grab_focus()            # ✕ gedrückt → gleich weiterschreiben
        self._fresh = False
        self.queue()

    def entry_focused(self):
        root = self.entry.get_root()
        f = root.get_focus() if root else None
        return f is not None and (f is self.entry or f.is_ancestor(self.entry))

    def on_entry_press(self, gesture, n, x, y):
        if not self.entry.get_text():
            return
        if n >= 2 or self._fresh:
            self._fresh = False
            if n >= 2:
                gesture.set_state(Gtk.EventSequenceState.CLAIMED)
            if not self.entry_focused():
                self.entry.grab_focus()
            GLib.idle_add(lambda: (self.entry.select_region(0, -1), False)[1])

    def on_enter(self):
        """Enter: steht „online übersetzen“ als Hauptweg da (kein Treffer oder ganzer Satz), los – sonst kopieren."""
        b = self.online_btn
        if b is not None and b.get_parent() is not None and b.get_visible() and b.get_sensitive() and \
                (self.first is None or getattr(b, "primary", False)):
            b.emit("clicked")
        else:
            self.copy_first()
    def set_dir(self, key):
        if self.settings().get("dir") != key:
            self.settings()["dir"] = key
            self.save_prefs()
        self.queue(0)

    def is_open(self):
        return self.get_reveal_child()

    def toggle(self, on=None, text=None):
        on = (not self.is_open()) if on is None else on
        self.set_reveal_child(on)
        self.set_can_target(on)
        if on:
            if text:
                self.entry.set_text(text.strip()[:500])
            self.entry.grab_focus()
            self.entry.select_region(0, -1)
            self._fresh = False
            self.queue(0)
        if self.on_toggled:
            self.on_toggled(on)

    def on_key(self, ctrl, keyval, code, state):
        if keyval == Gdk.KEY_Escape:
            self.toggle(False)
            return True
        return False

    def queue(self, delay=160):
        if self._timer:
            GLib.source_remove(self._timer)
        self._timer = GLib.timeout_add(max(delay, 1), self._run)

    # ---------- Anzeige ----------
    def clear(self):
        while (c := self.results.get_first_child()):
            self.results.remove(c)
        self.first = None
        self.online_btn = None

    def label(self, text, cls, **kw):
        lab = Gtk.Label(label=text, xalign=0, wrap=True, **kw)
        lab.add_css_class(cls)
        self.results.append(lab)
        return lab

    def _run(self):
        self._timer = 0
        self.clear()
        if self.lang_mode:
            self.render_langs()
            return False
        q = self.entry.get_text().strip()
        if self.lang() != "en":
            return self._run_with(q, self.source())
        if not available():
            self.show_install()
            if q:
                self.online_button(q)
            return False
        return self._run_with(q, self.dict)

    def _run_with(self, q, source):
        lg = self.lang()
        name = i18n.tr(LANGS.get(lg, lg)).lower()
        if not q:
            self.label(i18n.tr("Tippe ein Wort – deutsch oder {}. Ein Klick auf eine Übersetzung kopiert sie, "
                               "Enter kopiert die erste (oder übersetzt online).", name), "trx-empty")
            return False
        direction = self.settings().get("dir", "auto")
        direction = {"en": lg}.get(direction, direction)
        try:
            res = source.lookup(q, direction)
        except sqlite3.Error as e:
            self.label(i18n.tr("Wörterbuch nicht lesbar: {}", str(e)), "trx-empty")
            return False
        both = len(res) > 1
        for r in res:
            if both or direction == "auto":
                self.label(i18n.tr("deutsch → {}", name) if r["dir"] == "de" else i18n.tr("{} → deutsch", name),
                           "trx-sec")
            for wt, means in r["groups"]:
                self.label(i18n.tr(wt), "trx-type")
                for m in means:
                    self.meaning(m)
            if r["phrases"]:
                self.label("wendungen & beispiele", "trx-sec")
                for src, tgt in r["phrases"][:12 if both else 20]:
                    self.phrase(src, tgt)
        if not res:
            self.label(i18n.tr("„{}“ steht nicht im Wörterbuch.", q), "trx-empty")
        if not res or len(q.split()) >= 3:
            self.online_button(q, primary=True)
        self.scroll.get_vadjustment().set_value(0)
        self._fresh = True                     # nächster Klick ins Feld markiert alles
        return False

    def meaning(self, m):
        row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        flow = Gtk.Box()
        import writer
        flow.set_layout_manager(writer.WrapLayout(spacing=4, row_spacing=3))
        for word, art, hint in m["words"]:
            b = Gtk.Button(focus_on_click=False, tooltip_text=i18n.tr("„{}“ kopieren", word))
            b.add_css_class("trx-word")
            inner = Gtk.Box(spacing=4)
            if art:
                a = Gtk.Label(label=art)
                a.add_css_class("trx-art")
                inner.append(a)
            inner.append(Gtk.Label(label=word))
            if hint:
                h = Gtk.Label(label=hint)
                h.add_css_class("trx-art")
                inner.append(h)
            b.set_child(inner)
            b.connect("clicked", lambda _b, w=word: self.copy(w))
            b.set_cursor_from_name("pointer")
            flow.append(b)
            if self.first is None:
                self.first = word
        row.append(flow)
        ctx = Gtk.Label(label=pretty(m["context"]), xalign=0, wrap=True, max_width_chars=48)
        ctx.add_css_class("trx-ctx")
        row.append(ctx)
        row.set_margin_bottom(3)
        self.results.append(row)

    def phrase(self, src, tgt):
        b = Gtk.Button(focus_on_click=False, tooltip_text="Übersetzung kopieren")
        b.add_css_class("trx-phrase")
        inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        s = Gtk.Label(label=src, xalign=0, wrap=True, max_width_chars=48)
        s.add_css_class("trx-src")
        t = Gtk.Label(label=re.sub(r"\s*\{[^}]*\}", "", tgt), xalign=0, wrap=True, max_width_chars=48)
        inner.append(s)
        inner.append(t)
        b.set_child(inner)
        plain = re.sub(r"\s+", " ", NOTE.sub(" ", tgt)).strip()
        b.connect("clicked", lambda *_: self.copy(plain))
        b.set_cursor_from_name("pointer")
        self.results.append(b)

    def online_button(self, q, primary=False):
        b = Gtk.Button(label="󰖟 online übersetzen (MyMemory) ⏎" if primary else "󰖟 online übersetzen (MyMemory)",
                       focus_on_click=False, halign=Gtk.Align.START,
                       tooltip_text="Schickt den Text an api.mymemory.translated.net – nur auf Klick oder Enter")
        b.primary = primary
        self.online_btn = b
        b.add_css_class("trx-dir")
        b.set_margin_top(6)

        def go(*_):
            b.set_sensitive(False)
            b.set_label(i18n.tr("übersetze …"))
            d = self.settings().get("dir", "auto")
            lg = self.lang()
            if d == "de":
                src = "de"
            elif d == "en":
                src = lg
            elif lg != "en":
                src = self.source().guess(q)
            else:
                src = self.dict.guess(q) if self.dict.open() else \
                    ("de" if re.search(r"[äöüß]", q.lower()) else "en")
            online(q, src, lambda texts, err: self.show_online(b, texts, err), lang=lg)
        b.connect("clicked", go)
        self.results.append(b)

    def show_online(self, btn, texts, err):
        if btn.get_parent() is None:            # inzwischen neu gesucht
            return
        btn.set_visible(False)
        if not texts:
            self.label(i18n.tr("Online-Übersetzung ging nicht ({})", err or "keine Antwort"), "trx-empty")
            return
        self.label("online (mymemory)", "trx-sec")
        for t in texts:
            self.phrase(t, t)
        self.first = texts[0]                   # Enter kopiert jetzt die Online-Übersetzung
        self.online_btn = None

    def show_install(self):
        self.label("Für die Wörter braucht notist einmalig das freie Wörterbuch der TU Chemnitz "
                   "(etwa 6 MB, danach offline).", "trx-empty")
        if local_source():
            self.label(i18n.tr("Gefunden: {} – wird nur eingelesen.", local_source()), "trx-ctx")
        self.prog = Gtk.ProgressBar(visible=self._installing)
        self.results.append(self.prog)
        b = Gtk.Button(label="󰇚 wörterbuch einrichten", focus_on_click=False, halign=Gtk.Align.START,
                       sensitive=not self._installing)
        b.add_css_class("trx-dir")
        b.connect("clicked", lambda *_: self.start_install(b))
        self.results.append(b)

    def start_install(self, btn):
        self._installing = True
        btn.set_sensitive(False)
        self.prog.set_visible(True)

        def progress(text, frac):
            self.status.set_label(text)
            if getattr(self, "prog", None) is not None:
                self.prog.set_fraction(frac) if frac is not None else self.prog.pulse()

        def done(err):
            self._installing = False
            self.status.set_label(i18n.tr("Fehler: {}", err) if err else i18n.tr("wörterbuch bereit"))
            self.queue(0)
        install(progress, done)

    def copy(self, text):
        self.get_clipboard().set(text)
        self.status.set_label(i18n.tr("kopiert: {}", text))
        self.status.add_css_class("trx-ok")
        GLib.timeout_add(1600, lambda: (self.status.remove_css_class("trx-ok"), False)[1])

    def copy_first(self):
        if self.first:
            self.copy(self.first)
