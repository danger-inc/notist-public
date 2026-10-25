# Strg+F: Suchleiste in zwei Teilen – links „in diesem Eintrag“ (Treffer markieren, vor/zurück),
# rechts „in allen“ (Anzahl passender Einträge, Klick übernimmt die Suche in die Liste).
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, GLib, Gtk

import writer as wr

# Gemeinsamer Look aller Suchleisten (Notizen, Words, LaTeX) – wie die Suche in Code-Editoren: eine schmale Karte
# oben rechts im Text, Eingabefeld ohne eigenen Rahmen, flache Knöpfe, Akzentrahmen. Andere -ist-Apps übernehmen ihn,
# indem sie ihre Leiste mit style(bar) versehen und CSS in ihr Stylesheet aufnehmen (nur Farben aus dem Theme).
CSS = """
.ist-find { background-color: alpha(@background, 0.94); border: 1px solid alpha(@primary, 0.55); border-radius: 6px;
    padding: 3px 4px; margin: 4px 4px 8px 4px; box-shadow: 0 4px 14px rgba(0,0,0,0.25); }
.ist-find entry, .ist-find searchentry, .ist-find entry.pb, .ist-find searchentry.pb {
    background-color: alpha(@foreground, 0.07); background-image: none; border: 1px solid transparent; border-radius: 4px;
    box-shadow: none; min-height: 24px; padding: 0 6px; outline: none; color: @foreground; }
.ist-find entry:focus-within, .ist-find searchentry:focus-within { border-color: @primary; }
.ist-find button, .ist-find button.wt, .ist-find button.pb, .ist-find togglebutton.wt {
    background: none; background-image: none; box-shadow: none; border: 1px solid transparent; border-radius: 4px;
    min-height: 22px; min-width: 22px; padding: 0 6px; color: @foreground; }
.ist-find button:hover, .ist-find togglebutton:hover { background-color: alpha(@primary, 0.2); }
.ist-find togglebutton:checked { background-color: alpha(@primary, 0.25); border-color: @primary; }
.ist-find .wstatus, .ist-find .tex-status { color: alpha(@foreground, 0.6); font-size: 12px; padding: 0 4px; }
"""


def style(bar):
    """Suchleiste im gemeinsamen Look: Karte, volle Breite."""
    bar.add_css_class("ist-find")
    bar.set_halign(Gtk.Align.FILL)
    bar.set_hexpand(True)
    return bar


class AllPart(Gtk.Box):
    """Rechter Teil der Suchleiste: „󰍉 alle notizen · 3“. count(q) → Anzahl, go(q) → Listensuche."""

    def __init__(self, what, count, go):
        super().__init__(spacing=6, valign=Gtk.Align.CENTER)
        self.add_css_class("find-all")
        self.what, self.count, self.go, self.q = what, count, go, ""
        line = Gtk.Box()
        line.add_css_class("find-div")
        self.append(line)
        self.btn = Gtk.Button(focus_on_click=False,
                              tooltip_text="Diese Suche in allen Einträgen – Liste filtern (Strg+Umschalt+F)")
        self.btn.add_css_class("pb"); self.btn.add_css_class("small")
        self.lab = Gtk.Label()
        self.btn.set_child(self.lab)
        self.btn.connect("clicked", lambda *_: self.go(self.q))
        self.append(self.btn)
        self._tick = None
        self.update("")

    def update(self, q):
        self.q = q
        if self._tick:
            GLib.source_remove(self._tick)
        self._tick = GLib.timeout_add(120, self._count)     # gebündelt: nicht bei jedem Tastendruck zählen

    def _count(self):
        self._tick = None
        q = self.q.strip()
        if not q:
            self.lab.set_label(f"󰍉 in allen {self.what}")
        else:
            try:
                n = self.count(q)
            except Exception:
                n = 0
            self.lab.set_label(f"󰍉 in allen {self.what} · {n}")
        return False


class NoteFind:
    """Suchleiste für den Notiz-Editor (Gtk.TextView), Aufbau wie in Words."""

    def __init__(self, view, what, count, go):
        self.view = view
        buf = view.get_buffer()
        self.tag = buf.create_tag("find-hit", background_rgba=wr.rgba("#ffb300", 0.45))
        self.hits = []
        bar = Gtk.Box()
        bar.set_layout_manager(wr.WrapLayout(spacing=6, row_spacing=4))
        bar.add_css_class("findbar")
        bar.add_css_class("note-find")
        style(bar)
        self.entry = Gtk.SearchEntry(placeholder_text="In dieser Notiz suchen", width_chars=20)
        self.entry.add_css_class("pb")
        self.entry.connect("search-changed", lambda *_: self.run())
        self.entry.connect("activate", lambda *_: self.step(1))
        self.entry.connect("stop-search", lambda *_: self.hide())
        bar.append(self.entry)
        bar.append(wr.tool("󰅃", "Vorheriger Treffer (Umschalt+Enter)", lambda *_: self.step(-1)))
        bar.append(wr.tool("󰅀", "Nächster Treffer (Enter)", lambda *_: self.step(1)))
        self.case = Gtk.ToggleButton(label="Aa", tooltip_text="Groß-/Kleinschreibung beachten", focus_on_click=False)
        self.case.add_css_class("wt")
        self.case.connect("toggled", lambda *_: self.run())
        bar.append(self.case)
        self.info = Gtk.Label(label="")
        self.info.add_css_class("wstatus")
        bar.append(self.info)
        self.all = AllPart(what, count, go)
        bar.append(self.all)
        bar.append(wr.tool("󰅖", "Schließen (Esc oder Strg+F)", lambda *_: self.hide()))
        k = Gtk.EventControllerKey()
        k.connect("key-pressed", self.on_key)
        bar.add_controller(k)
        self.rev = Gtk.Revealer(transition_type=Gtk.RevealerTransitionType.SLIDE_DOWN, reveal_child=False)
        self.rev.set_child(bar)
        buf.connect("changed", lambda *_: self.rev.get_reveal_child() and self.queue_run())
        self._run_id = None

    @property
    def widget(self):
        return self.rev

    def is_open(self):
        return self.rev.get_reveal_child()

    def show(self):
        self.rev.set_reveal_child(True)
        buf = self.view.get_buffer()
        b = buf.get_selection_bounds()
        if b and b[0].get_line() == b[1].get_line():
            self.entry.set_text(buf.get_text(*b, False))
        self.entry.grab_focus()
        self.entry.select_region(0, -1)
        self.run()

    def hide(self, focus=True):
        if not self.rev.get_reveal_child():
            return
        self.rev.set_reveal_child(False)
        self.clear()
        if focus:
            self.view.grab_focus()

    def clear(self):
        buf = self.view.get_buffer()
        buf.remove_tag(self.tag, buf.get_start_iter(), buf.get_end_iter())
        self.hits = []

    def queue_run(self):
        if self._run_id:
            GLib.source_remove(self._run_id)
        self._run_id = GLib.timeout_add(200, lambda: (setattr(self, "_run_id", None), self.run(keep=True), False)[-1])

    def run(self, keep=False):
        self.clear()
        q = self.entry.get_text()
        self.all.update(q)
        if not q:
            self.info.set_label("")
            return
        buf = self.view.get_buffer()
        flags = Gtk.TextSearchFlags.TEXT_ONLY | Gtk.TextSearchFlags.VISIBLE_ONLY
        if not self.case.get_active():
            flags |= Gtk.TextSearchFlags.CASE_INSENSITIVE
        it = buf.get_start_iter()
        while len(self.hits) < 5000:
            m = it.forward_search(q, flags, None)
            if not m:
                break
            s, e = m
            buf.apply_tag(self.tag, s, e)
            self.hits.append((s.get_offset(), e.get_offset()))
            it = e
        self.info.set_label(f"{len(self.hits)} Treffer" if self.hits else "keine Treffer")
        if self.hits and not keep:          # gleich zum ersten Treffer ab dem Cursor springen
            self.step(1, select=False)

    def step(self, d, select=True):
        if not self.hits:
            self.run(keep=True)
        if not self.hits:
            return
        buf = self.view.get_buffer()
        b = buf.get_selection_bounds()
        cur = buf.get_iter_at_mark(buf.get_insert()).get_offset()
        if d > 0:
            pos = b[1].get_offset() if b else cur
            if not select:
                pos = b[0].get_offset() if b else cur
            hit = next((h for h in self.hits if h[0] >= pos), self.hits[0])
        else:
            pos = b[0].get_offset() if b else cur
            hit = next((h for h in reversed(self.hits) if h[1] <= pos), self.hits[-1])
        s, e = buf.get_iter_at_offset(hit[0]), buf.get_iter_at_offset(hit[1])
        if select:
            buf.select_range(s, e)
        self.view.scroll_to_iter(s, 0.2, False, 0, 0)
        self.info.set_label(f"{self.hits.index(hit) + 1} von {len(self.hits)}")

    def on_key(self, ctrl, keyval, code, state):
        if keyval == Gdk.KEY_Escape:
            self.hide()
            return True
        if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter) and state & Gdk.ModifierType.SHIFT_MASK:
            self.step(-1)
            return True
        return False


def attach_all(bar, entry, what, count, go):
    """Words/LaTeX: den „in allen“-Teil an eine vorhandene Suchleiste hängen (vor dem Schließen-Knopf)."""
    part = AllPart(what, count, go)
    last = bar.get_last_child()
    part.insert_before(bar, last)
    entry.connect("search-changed", lambda e: part.update(e.get_text()))
    return part
