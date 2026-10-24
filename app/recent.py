# Linke Leiste „zuletzt“: fährt die Maus an den linken Fensterrand, gleitet eine Liste der zuletzt benutzten
# Einträge herein (wie die Apps-Leiste in scourge). Gezeigt wird immer nur der oben gewählte Bereich
# (Notizen, Words oder LaTeX); auf Home alle drei gemischt. Esc, Klick daneben oder Verlassen schließt.
import sys

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, GLib, Gtk

import i18n

EDGE = 6
WIDTH = 270
ROWS = 14
KEEP = 40            # so viele IDs je Bereich merken

CSS = """
.rdrawer { background-color: @background; border: 1px solid alpha(@primary, 0.55); border-left: none;
    border-radius: 0 6px 6px 0; padding: 10px 8px; box-shadow: 6px 0 22px rgba(0,0,0,0.28); }
.glass .rdrawer { background-color: alpha(@background, 0.97); }
.rdrawer .rd-title { font-size: 13px; font-weight: bold; color: @primary; margin: 2px 6px 8px 6px; }
.rdrawer .rd-sub { font-size: 11px; color: @secondary; font-weight: normal; margin: 8px 6px 0 6px; }
.rdrawer .rd-empty { font-size: 12px; color: @secondary; margin: 6px; }
button.rd-item { background: none; background-image: none; border: 1px solid transparent; box-shadow: none;
    border-radius: 6px; padding: 5px 8px; min-height: 0; color: @foreground; outline: none; }
button.rd-item:hover, button.rd-item:focus-visible { border-color: alpha(@primary, 0.55); background-color: alpha(@primary, 0.10); }
button.rd-item.current { background-color: alpha(@primary, 0.22); border-color: alpha(@primary, 0.55); }
button.rd-item .rd-icon { color: @primary; font-size: 15px; min-width: 22px; }
button.rd-item .rd-name { font-size: 13px; font-weight: bold; }
button.rd-item .rd-when { font-size: 11px; color: @secondary; font-weight: normal; }
.rd-edge { background: none; }
.rd-acts { margin: 0 4px 8px 4px; }
.rd-acts flowboxchild { padding: 0; }
button.rd-act { background: none; background-image: none; box-shadow: none; border: 1px solid alpha(@primary, 0.55);
    border-radius: 4px; padding: 1px 8px; min-height: 0; font-size: 12px; font-weight: bold; color: @foreground; }
button.rd-act:hover { background-color: @primary; color: @on_primary; border-color: @primary; }
.rdrawer.pinned { border: 1px solid alpha(@primary, 0.55); border-radius: 6px; box-shadow: none; margin: 0 10px 0 8px; }
"""


def remember(prefs, kind, nid):
    """nid an den Anfang der Zuletzt-Liste des Bereichs setzen. True, wenn sich etwas geändert hat."""
    rec = prefs.setdefault("recent", {}).setdefault(kind, [])
    if rec and rec[0] == nid:
        return False
    if nid in rec:
        rec.remove(nid)
    rec.insert(0, nid)
    del rec[KEEP:]
    return True


class RecentDrawer:
    """Zwei Zustände wie die Apps-Leiste in scourge: schwebend (Maus an den linken Rand, liegt über dem Inhalt)
    und angeheftet (Klick auf den „notist“-Chip: eigene Spalte links, schiebt den Inhalt – nichts wird verdeckt).
    self.widget ersetzt das übergebene Overlay im Fenster."""

    def __init__(self, app, overlay):
        self.app = app
        self._close_id = None
        self.narrow = False
        self.widget = Gtk.Box(vexpand=True)
        self.pin_rev = Gtk.Revealer(transition_type=Gtk.RevealerTransitionType.SLIDE_RIGHT, transition_duration=160,
                                    reveal_child=False, margin_top=4, margin_bottom=10)
        self.pin_panel, self.pin_title, self.pin_list = self._panel(pinned=True)
        self.panels = [self.pin_panel]
        self.pin_rev.set_child(self.pin_panel)
        self.widget.append(self.pin_rev)
        overlay.set_hexpand(True)
        self.widget.append(overlay)

        self.edge = Gtk.Box(halign=Gtk.Align.START, valign=Gtk.Align.FILL, width_request=EDGE)
        self.edge.add_css_class("rd-edge")
        m = Gtk.EventControllerMotion()
        m.connect("enter", lambda *_: self.open())
        # Maus fährt über die Kante gleich aus dem Fenster hinaus (ohne die Leiste zu berühren) → wieder schließen
        m.connect("leave", lambda *_: self.is_open() and self._leave())
        self.edge.add_controller(m)
        overlay.add_overlay(self.edge)

        self.rev = Gtk.Revealer(transition_type=Gtk.RevealerTransitionType.SLIDE_RIGHT, transition_duration=160,
                                halign=Gtk.Align.START, valign=Gtk.Align.FILL, reveal_child=False,
                                margin_top=4, margin_bottom=10)
        self.rev.set_can_target(False)
        self.panel, self.title, self.list = self._panel(pinned=False)
        self.panels.append(self.panel)
        pm = Gtk.EventControllerMotion()
        pm.connect("leave", lambda *_: self._leave())
        pm.connect("enter", lambda *_: self._cancel_close())
        self.panel.add_controller(pm)
        self.rev.set_child(self.panel)
        overlay.add_overlay(self.rev)

        click = Gtk.GestureClick(button=0)
        click.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        click.connect("pressed", self._outside_click)
        overlay.add_controller(click)
        keys = Gtk.EventControllerKey()
        keys.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        keys.connect("key-pressed", self._key)
        overlay.add_controller(keys)
        if app.prefs.get("recent_pinned"):
            self.pin(True, animate=False, save=False)

    def _panel(self, pinned):
        panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, width_request=WIDTH, hexpand=False)
        panel.add_css_class("rdrawer")
        if pinned:
            panel.add_css_class("pinned")
        title = Gtk.Label(xalign=0)
        title.add_css_class("rd-title")
        panel.append(title)
        # Neu anlegen / Datei öffnen – auch im schmalen Fenster, wo diese Knöpfe oben fehlen
        acts = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, max_children_per_line=3, min_children_per_line=1,
                           column_spacing=4, row_spacing=4, homogeneous=False)
        acts.add_css_class("rd-acts")
        panel.append(acts)
        panel.acts = acts
        lst = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        sc = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER, vexpand=True, child=lst)
        panel.append(sc)
        text = i18n.tr("klick auf „notist“ blendet die leiste aus") if pinned else \
            i18n.tr("klick auf „notist“ heftet die leiste an · esc schließt")
        hint = Gtk.Label(label=text, xalign=0, wrap=True, max_width_chars=30)
        hint.add_css_class("rd-sub")
        panel.append(hint)
        return panel, title, lst

    # ---------- angeheftet ----------
    @property
    def pinned(self):
        return bool(self.app.prefs.get("recent_pinned"))

    def pin(self, on, animate=True, save=True):
        self.close()
        if save:
            self.app.prefs["recent_pinned"] = on
            self.app.save_prefs()
        self.pin_rev.set_transition_duration(160 if animate else 0)
        self._apply()

    def toggle(self):
        self.pin(not self.pinned)

    def set_narrow(self, on):
        """Halber Bildschirm: angeheftete Spalte vorübergehend ausblenden (bleibt gemerkt)."""
        if on != self.narrow:
            self.narrow = on
            self._apply()

    def _apply(self):
        show = self.pinned and not self.narrow
        if show:
            self.refresh()
        self.pin_rev.set_reveal_child(show)
        self.edge.set_visible(not show)

    def refresh(self):
        """Angeheftete Liste aktualisieren (nach Speichern, Bereichswechsel usw.)."""
        if self.pin_rev.get_reveal_child() or (self.pinned and not self.narrow):
            self._fill(self.pin_title, self.pin_list)

    # ---------- Inhalt ----------
    def items(self):
        """[(art, notiz)] – zuerst die zuletzt geöffneten, dann nach Änderungsdatum aufgefüllt."""
        app = self.app
        kinds = list(app.stores) if app.view == "home" else [app.kind]
        rec = app.prefs.get("recent", {})
        out, seen = [], set()
        if len(kinds) == 1:
            store = app.stores[kinds[0]]
            for nid in rec.get(kinds[0], []):
                n = store.notes.get(nid)
                if n and not n.get("trashed") and not n.get("archived"):
                    out.append((kinds[0], n))
                    seen.add(nid)
        else:                          # Home: die Listen der drei Bereiche nach letzter Öffnung mischen
            order = app.prefs.get("recent_all", [])
            for key in order:
                kind, _, nid = key.partition(":")
                n = app.stores[kind].notes.get(nid) if kind in app.stores else None
                if n and not n.get("trashed") and not n.get("archived"):
                    out.append((kind, n))
                    seen.add(nid)
        rest = [(k, n) for k in kinds for n in app.stores[k].visible() if n["id"] not in seen]
        rest.sort(key=lambda kn: kn[1].get("updated") or "", reverse=True)
        return (out + rest)[:ROWS]

    def fill(self):
        self._fill(self.title, self.list)

    def _fill(self, title, lst):
        app = self.app
        home = app.view == "home"
        m = sys.modules[type(app).__module__]          # notes.py läuft als __main__
        KINDS, TAB_NAMES, nice_date = m.KINDS, m.TAB_NAMES, m.nice_date
        name = i18n.tr("alle bereiche") if home else i18n.tr(TAB_NAMES[app.kind])
        title.set_label(f"󰋚  {i18n.tr('zuletzt')} · {name}")
        panel = next(p for p in self.panels if p.get_first_child() is title)
        acts = panel.acts
        c = acts.get_first_child()
        while c:
            acts.remove(c)
            c = acts.get_first_child()
        news = [("notes", "󰐕 notiz"), ("docs", "󰐕 words"), ("latex", "󰐕 latex")] if home else \
            [(app.kind, "󰐕 " + {"notes": "neue notiz", "docs": "neues dokument", "latex": "neues latex"}[app.kind])]
        for kind, text in news:
            b = Gtk.Button(label=text, focus_on_click=False, tooltip_text=app.new_label_for(kind) + " (Strg+N)")
            b.add_css_class("rd-act")
            b.connect("clicked", lambda _b, k=kind: self._new(k))
            acts.append(b)
        o = Gtk.Button(label="󰝰 öffnen", focus_on_click=False, tooltip_text="Datei öffnen (Strg+O)")
        o.add_css_class("rd-act")
        o.connect("clicked", lambda *_: (self.close(), app.import_dialog()))
        acts.append(o)
        c = lst.get_first_child()
        while c:
            lst.remove(c)
            c = lst.get_first_child()
        cur = app.current["id"] if (app.current and not home) else None
        items = self.items()
        for kind, n in items:
            b = Gtk.Button(focus_on_click=False)
            b.add_css_class("rd-item")
            if n["id"] == cur:
                b.add_css_class("current")
            row = Gtk.Box(spacing=8)
            ic = Gtk.Label(label="󰐃" if n.get("pinned") and not home else KINDS[kind][1], xalign=0.5)
            ic.add_css_class("rd-icon")
            txt = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            t = Gtk.Label(label=app.display_title(n, kind), xalign=0, ellipsize=3, max_width_chars=26)
            t.add_css_class("rd-name")
            w = Gtk.Label(label=nice_date(n["updated"]), xalign=0)
            w.add_css_class("rd-when")
            txt.append(t)
            txt.append(w)
            row.append(ic)
            row.append(txt)
            b.set_child(row)
            b.set_tooltip_text(app.display_title(n, kind))
            b.connect("clicked", lambda _b, k=kind, i=n["id"]: self._open(k, i))
            self._row_menu(b, kind, n["id"])
            lst.append(b)
        if not items:
            e = Gtk.Label(label=i18n.tr("noch nichts geöffnet"), xalign=0)
            e.add_css_class("rd-empty")
            lst.append(e)

    def _row_menu(self, b, kind, nid):
        """Rechtsklick / langes Drücken: dasselbe Menü wie in allen Listen; die Leiste bleibt solange offen."""
        def show(g, x, y):
            g.set_state(Gtk.EventSequenceState.CLAIMED)
            pop = self.app.entry_menu(b, kind, nid, x, y)
            if pop is not None:
                self._menu = pop
                self._cancel_close()
                pop.connect("closed", lambda *_: (setattr(self, "_menu", None), self._leave()))
        right = Gtk.GestureClick(button=3)
        right.connect("pressed", lambda g, _n, x, y: show(g, x, y))
        b.add_controller(right)
        hold = Gtk.GestureLongPress(touch_only=True)
        hold.connect("pressed", show)
        b.add_controller(hold)

    def _new(self, kind):
        self.close()
        GLib.idle_add(lambda: (self.app.home_new(kind), False)[1])

    def _open(self, kind, nid):
        self.close()
        GLib.idle_add(lambda: (self.app.home_open(kind, nid), False)[1])

    # ---------- auf/zu ----------
    def is_open(self):
        return self.rev.get_reveal_child()

    def open(self):
        self._cancel_close()
        if self.pin_rev.get_reveal_child():
            return
        if not self.is_open():
            self.fill()
            self.rev.set_can_target(True)
            self.rev.set_reveal_child(True)

    def close(self):
        self._cancel_close()
        if self.is_open():
            self.rev.set_reveal_child(False)
            self.rev.set_can_target(False)

    def _leave(self):
        self._cancel_close()
        self._close_id = GLib.timeout_add(220, self._delayed_close)

    def _delayed_close(self):
        self._close_id = None
        if getattr(self, "_menu", None) is None:        # Rechtsklick-Menü offen: Leiste stehen lassen
            self.close()
        return False

    def _cancel_close(self):
        if self._close_id:
            GLib.source_remove(self._close_id)
            self._close_id = None

    def _outside_click(self, g, n, x, y):
        if getattr(self, "_menu", None) is not None:      # Klick ins Menü (läuft auch hier durch)
            return
        if self.is_open() and x > self.panel.get_width():
            self.close()

    def _key(self, ctrl, keyval, code, mods):
        if keyval == Gdk.KEY_Escape and self.is_open():
            self.close()
            return True
        return False
