# notist – gemeinsames Bearbeiten (PC/Mac). So einfach wie möglich:
#   • Knopf „gemeinsam“ unten: anmelden (musicalist-Konto), Freunde antippen und einladen, Sitzungs-Code kopieren.
#   • Kommt eine Einladung an: Popup „Beitreten“ – in ein neues Dokument oder ins gerade offene.
#   • Verbunden = Leiste über dem Dokument („● Live“ + farbige Namen); fremde Cursor als farbige Linie mit Namen,
#     fremde Markierungen farbig hinterlegt – die Farbe der Person ist überall dieselbe.
#   • Eine freigegebene Verbindung bleibt bestehen (auch wenn das Dokument zu ist: Änderungen landen im Eintrag), bis
#     jemand sie selbst trennt – mit klarer Warnung, was dann passiert.
import os, threading

from gi.repository import Gdk, GLib, Gtk

import dialogs
import i18n
import writer as wr
from core import collab as C, paths
from core import docfmt as df

KIND_NAME = {"notes": "Notiz", "docs": "Words", "latex": "LaTeX"}

CSS = """
.collab-banner { background-color: alpha(@primary, 0.13); border: 1px solid alpha(@primary, 0.45); border-radius: 8px;
    padding: 4px 6px 4px 10px; margin: 6px 0 4px 0; }
.collab-banner.off { background-color: alpha(@foreground, 0.06); border-color: alpha(@foreground, 0.2); }
.collab-dot { color: @primary; font-size: 15px; }
.collab-banner.off .collab-dot { color: alpha(@foreground, 0.4); }
.collab-live { font-weight: bold; color: @primary; }
.collab-banner.off .collab-live { color: alpha(@foreground, 0.6); }
.collab-chip { border-radius: 10px; padding: 1px 9px; color: #15171a; font-weight: bold; font-size: 12px; }
.collab-sub { opacity: 0.65; font-size: 12px; }
.collab-caret { min-width: 2px; border-radius: 1px; }
.collab-tag { border-radius: 4px 4px 4px 0; padding: 0 5px; color: #15171a; font-size: 10px; font-weight: bold; }
.collab-friend { border-radius: 14px; padding: 2px 10px; }
.collab-friend:checked { background-color: alpha(@primary, 0.25); border-color: @primary; }
button.collab-signin { background-color: @primary; color: @on_primary; font-weight: bold; padding: 8px 14px;
    border-radius: 8px; background-image: none; }
button.collab-signin:hover { background-color: shade(@primary, 1.1); }
"""
_COLOR_CSS = set()


def _color_css(hexcol):
    """Klassen je Farbe (Chip-Hintergrund, Cursorlinie) einmalig anlegen."""
    k = hexcol.lstrip("#")
    if k not in _COLOR_CSS:
        _COLOR_CSS.add(k)
        p = Gtk.CssProvider()
        p.load_from_string(f".cc-{k} {{ background-color: {hexcol}; }}")
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), p, Gtk.STYLE_PROVIDER_PRIORITY_USER + 2)
    return f"cc-{k}"


def _bg(fn, done):
    """fn im Hintergrund, done(ergebnis, fehler) im UI-Faden."""
    def run():
        try:
            r, e = fn(), None
        except C.CollabError as x:
            r, e = None, x
        except Exception as x:  # noqa: BLE001
            r, e = None, C.CollabError(str(x))
        GLib.idle_add(lambda: (done(r, e), False)[1])
    threading.Thread(target=run, daemon=True).start()


def replace_text(buf, new):
    """Puffer mit möglichst kleiner Änderung auf `new` bringen (Cursor und Markierungen bleiben, wo sie hingehören)."""
    old = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), True)
    if old == new:
        return
    p = 0
    while p < len(old) and p < len(new) and old[p] == new[p]:
        p += 1
    s = 0
    while s < len(old) - p and s < len(new) - p and old[-1 - s] == new[-1 - s]:
        s += 1
    a, b = buf.get_iter_at_offset(p), buf.get_iter_at_offset(len(old) - s)
    if a.get_offset() != b.get_offset():
        buf.delete(a, b)
    ins = new[p:len(new) - s]
    if ins:
        buf.insert(buf.get_iter_at_offset(p), ins)


def _changed_span(a, b):
    p = 0
    while p < len(a) and p < len(b) and a[p] == b[p]:
        p += 1
    s = 0
    while s < len(a) - p and s < len(b) - p and a[-1 - s] == b[-1 - s]:
        s += 1
    return a[p:len(a) - s] + b[p:len(b) - s]


class Conn:
    """Eine laufende Sitzung auf diesem Gerät (Dokument offen oder nicht)."""

    def __init__(self, s, kind, key):
        self.s, self.kind, self.key = s, kind, key
        self.live = None
        self.state = {}
        self.cursors = []

    @property
    def sid(self):
        return self.s["id"]

    def people(self):
        return [self.s["owner"]] + list(self.s.get("members") or [])


class CollabUI:
    def __init__(self, app):
        self.app = app
        self.acct = C.Account(os.path.join(paths.HOME, "collab.json"))
        self.sessions = []
        self.friends = []
        self.conns = {}              # sid → Conn (alle verbundenen Sitzungen, offen oder im Hintergrund)
        self.problem = {}            # sid → Hinweis (Code fehlt/falsch, neu anmelden)
        self._edit_id = self._cur_id = self._paint_id = None
        self._carets = {}            # (view, name/gerät) → Schild des fremden Cursors (wird nur verschoben)
        self._sel_tags = {}          # (buf, farbe) → Tag
        self._popup = None
        p = Gtk.CssProvider()
        p.load_from_string(CSS)
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), p, Gtk.STYLE_PROVIDER_PRIORITY_USER + 1)
        self.btn = self.make_button()
        self.banner = self.make_banner()
        for buf in (app.writer.buf, app.latex.main_buf, app.text.get_buffer()):
            buf.connect("mark-set", lambda b, it, m: m.get_name() == "insert" and self.cursor_moved(b))
            buf.connect_after("changed", lambda *_: self.repaint_soon())
        GLib.timeout_add_seconds(2, lambda: (self.refresh(), False)[1])
        GLib.timeout_add_seconds(45, lambda: (self.refresh(), True)[1])

    # ================================================================ Server-Liste
    def refresh(self, then=None):
        if not self.acct.token:
            self.sessions = []
            self.stop_all()
            self.update_ui()
            return

        def done(r, e):
            if e is None:
                self.sessions = r or []
                self.connect_all()
                self.ask_invites()
            self.update_ui()
            if then:
                then(e)
        _bg(self.acct.sessions, done)
        if not self.friends:
            _bg(self.acct.friends, lambda r, e: setattr(self, "friends", r or []))

    def entry(self, key):
        kind, _, nid = (key or "").partition(":")
        st = self.app.stores.get(kind)
        n = st.notes.get(nid) if st else None
        return n if n and not n.get("trashed") else None

    def local_key(self, s):
        k = self.acct.link(s["id"])
        if k and self.entry(k):
            return k
        if s["owner"] == self.acct.name and self.entry(s["doc_key"]):     # eigenes Dokument auf einem anderen Gerät
            return s["doc_key"]
        return None

    def cur_key(self):
        n = self.app.current
        return f"{self.app.kind}:{n['id']}" if n and self.app.view != "home" else None

    def session_for(self, key):
        return next((s for s in self.sessions if s["status"] in ("pending", "active") and key and self.local_key(s) == key), None)

    def invites(self):
        """Einladungen an mich, die hier noch keinem Eintrag zugeordnet sind."""
        return [s for s in self.sessions if s["owner"] != self.acct.name and s["status"] in ("pending", "active")
                and not self.local_key(s)]

    # ================================================================ Verbindungen
    def connect_all(self):
        """Jede freigegebene Sitzung mit lokalem Eintrag läuft – auch im Hintergrund, bis jemand trennt."""
        alive = set()
        for s in self.sessions:
            key = self.local_key(s)
            if s["status"] != "active" or not key:
                continue
            alive.add(s["id"])
            c = self.conns.get(s["id"])
            if c is not None:
                c.s = s
                continue
            try:
                ckey = self.acct.key_for(s)
            except C.CollabError as e:
                self.problem[s["id"]] = str(e)
                continue
            self.problem.pop(s["id"], None)
            kind = key.split(":", 1)[0]
            c = Conn(s, kind, key)
            if key == self.cur_key():
                self.snapshot_once(c)
            # „Einladende“ (lädt den ersten Stand hoch) ist nur das Gerät, auf dem eingeladen wurde – andere eigene
            # Geräte übernehmen den gemeinsamen Stand, statt ihn mit einer älteren Fassung zu überschreiben
            origin = s["owner"] == self.acct.name and self.acct.link(s["id"]) == key
            c.live = C.Live(self.acct, s["id"], origin,
                            lambda c=c: self.get_doc(c), lambda d, doc, c=c: self.apply_remote(c, d, doc),
                            lambda fn: GLib.idle_add(lambda: (fn(), False)[1]),
                            lambda st, c=c: self.on_state(c, st), lambda cur, c=c: self.on_cursors(c, cur), key=ckey,
                            get_cursor=lambda c=c: self.cursor_of(c))
            self.conns[s["id"]] = c
            c.live.start()
        for sid in [x for x in self.conns if x not in alive]:            # beendet (von wem auch immer)
            self.drop(sid)
        self.update_ui()

    def drop(self, sid):
        c = self.conns.pop(sid, None)
        if c and c.live:
            if c.live.ready:
                c.live.local_changed()
            c.live.close()
        self.repaint()

    def stop_all(self):
        for sid in list(self.conns):
            self.drop(sid)

    def bound(self):
        """Verbindung des gerade offenen Dokuments (oder None)."""
        key = self.cur_key()
        return next((c for c in self.conns.values() if c.key == key), None)

    def is_open(self, c):
        return c.key == self.cur_key()

    def snapshot_once(self, c):
        """Vor der ersten gemeinsamen Bearbeitung eine Version sichern (Verlauf → zurückholbar)."""
        done = self.acct.st.setdefault("snapped", [])
        tag = f"{c.sid}:{c.key}"
        n = self.entry(c.key)
        if tag in done or n is None:
            return
        try:
            self.app.stores[c.kind].snapshot(n, force=True)
            done.append(tag)
            del done[:-300]
            self.acct._save()
        except Exception as e:  # noqa: BLE001
            print("collab: sicherung vor der sitzung:", e)

    # ================================================================ Hooks aus notes.py
    def selected(self):
        """Anderes Dokument geöffnet/geschlossen: alle Verbindungen holen ihren Stand jetzt aus Editor bzw. Speicher."""
        for c in self.conns.values():
            if c.live and c.live.ready:
                c.live.local_changed()
            if self.is_open(c):
                self.snapshot_once(c)
        self.app.writer.collab_author = self.acct.name if self.bound() else None
        self.update_ui()
        self.repaint()

    def edited(self):
        if self.bound() and not self._edit_id:
            self._edit_id = GLib.timeout_add(150, self._push)

    def _push(self):
        self._edit_id = None
        c = self.bound()
        if c and c.live.ready:
            c.live.local_changed(self.cursor_of(c))
        self.repaint_soon()
        return False

    def cursor_moved(self, buf):
        if self.bound() and not self._cur_id:
            self._cur_id = GLib.timeout_add(250, self._send_cursor)

    def _send_cursor(self):
        self._cur_id = None
        c = self.bound()
        if c:
            buf = self.buf(c.kind)
            b = buf.get_selection_bounds()
            i, j = (b[0].get_offset(), b[1].get_offset()) if b else (buf.get_iter_at_mark(buf.get_insert()).get_offset(),) * 2
            c.live.cursor(i, j)
        return False

    def cursor_of(self, c):
        if not self.is_open(c):
            return None
        buf = self.buf(c.kind)
        return buf.get_iter_at_mark(buf.get_insert()).get_offset()

    # ================================================================ Editor bzw. Speicher
    def buf(self, kind):
        app = self.app
        return app.writer.buf if kind == "docs" else app.latex.main_buf if kind == "latex" else app.text.get_buffer()

    def view(self, kind):
        app = self.app
        if kind == "docs":
            return app.writer.view
        if kind == "latex":
            return app.latex.view if app.latex.buf is app.latex.main_buf else None
        return app.text

    def get_doc(self, c):
        if not self.is_open(c):                                   # Dokument zu: Stand aus dem Speicher
            n = self.entry(c.key)
            return C.entry_to_doc(c.kind, n) if n else [{"insert": "\n"}]
        app = self.app
        if c.kind == "docs":
            return C.blocks_to_doc(app.writer.to_model())
        if c.kind == "latex":
            return [{"insert": app.latex.text() + "\n"}]
        b = app.text.get_buffer()
        return C.note_to_doc({"text": b.get_slice(b.get_start_iter(), b.get_end_iter(), True),
                              "rich": app.serialize_rich(), "images": app.collect_note_images()})

    def apply_remote(self, c, d, doc):
        if not self.is_open(c):                                   # im Hintergrund: direkt in den Eintrag
            n = self.entry(c.key)
            if n is not None:
                C.doc_into_entry(c.kind, doc, n)
                if c.kind == "docs":
                    n["text"] = df.plain_text(n["blocks"])
                self.app.stores[c.kind].save(n)
                if self.app.view == "home" or self.app.kind == c.kind:
                    GLib.idle_add(lambda: (self.app.refresh_home() if self.app.view == "home" else self.app.refresh_list(), False)[1])
            return
        app = self.app
        buf = self.buf(c.kind)
        mark = buf.get_insert()
        cur = buf.get_iter_at_mark(mark).get_offset()
        if c.kind == "docs":
            self.apply_words(d, doc)
        elif c.kind == "latex":
            replace_text(buf, C.text_of(doc)[:-1])
        else:
            self.apply_note(doc)
        new = min(C.transform_pos(cur, d), buf.get_char_count())
        if new != buf.get_iter_at_mark(mark).get_offset() and not buf.get_has_selection():
            buf.place_cursor(buf.get_iter_at_offset(new))
        app.on_edit()

    def apply_note(self, doc):
        app = self.app
        n = C.doc_to_note(doc)
        b = app.text.get_buffer()
        old = b.get_slice(b.get_start_iter(), b.get_end_iter(), True)
        if old.count(C.OBJ) == n["text"].count(C.OBJ) and C.OBJ not in _changed_span(old, n["text"]):
            replace_text(b, n["text"])
            for tag in app.our_tags():
                b.remove_tag(tag, b.get_start_iter(), b.get_end_iter())
            for s, e, name in n["rich"]:
                tag = app.font_tag(name[5:]) if name.startswith("font:") else b.get_tag_table().lookup(name)
                if tag:
                    b.apply_tag(tag, b.get_iter_at_offset(s), b.get_iter_at_offset(e))
        else:                                   # Bild/Tabelle betroffen: ganz neu laden (Rückgängig bleibt)
            app._n_restoring = True
            try:
                app.load_rich({**(app.current or {}), **n})
            finally:
                app._n_restoring = False
        app.style_checks()

    def apply_words(self, d, doc):
        """Nur die betroffenen Zeilen neu aufbauen (eine Zeile im Puffer = ein Block)."""
        w = self.app.writer
        buf = w.buf
        off, first, last_old, dl = 0, None, None, 0
        for op in d:
            n = C.op_len(op)
            if "retain" in op and not op.get("attributes"):
                off += n
                continue
            first = off if first is None else first
            if "insert" in op:
                if isinstance(op["insert"], str):
                    dl += op["insert"].count("\n")
                last_old = max(last_old or off, off)
            else:
                if "delete" in op:
                    t = buf.get_text(buf.get_iter_at_offset(off), buf.get_iter_at_offset(off + n), True)
                    dl -= t.count("\n")
                last_old = max(last_old or off, off + n)
                off += n
        if first is None:
            return
        total = buf.get_char_count()
        l0 = buf.get_iter_at_offset(min(first, total)).get_line()
        l1 = buf.get_iter_at_offset(min(max(last_old, first), total)).get_line()
        w.replace_lines(l0, l1, C.doc_to_blocks(doc)[l0:l1 + dl + 1])

    # ================================================================ Status
    def on_state(self, c, st):
        c.state = st
        if st.get("ended"):
            if st.get("badkey") or st.get("relogin"):
                self.problem[c.sid] = st.get("error")
                self.app.notify(i18n.tr("Gemeinsam bearbeiten: {} – unten auf „gemeinsam“", st.get("error") or ""))
            else:
                who = c.s["owner"] if c.s["owner"] != self.acct.name else ""
                self.app.notify(i18n.tr("{} hat die gemeinsame Bearbeitung beendet – deine Fassung bleibt", who) if who
                                else i18n.tr("Gemeinsame Bearbeitung beendet – deine Fassung bleibt"))
            self.drop(c.sid)
            self.refresh()
        self.update_ui()

    def on_cursors(self, c, curs):
        c.cursors = curs
        if self.is_open(c):
            self.repaint()
            self.update_banner()

    # ================================================================ fremde Cursor + Markierungen
    def repaint_soon(self):
        if self.conns and not self._paint_id:
            self._paint_id = GLib.timeout_add(60, lambda: (setattr(self, "_paint_id", None), self.repaint(), False)[-1])

    def repaint(self):
        """Fremde Cursor: je Person+Gerät GENAU ein Schild, das nur verschoben wird (TextView.remove entfernt Overlays
        nicht wirklich – neu anlegen würde sie anhäufen). Wer nicht mehr da ist, wird ausgeblendet."""
        for (buf, _), tag in self._sel_tags.items():
            buf.remove_tag(tag, buf.get_start_iter(), buf.get_end_iter())
        c = self.bound()
        view = self.view(c.kind) if c else None
        shown = set()
        if c is not None and view is not None:
            buf = self.buf(c.kind)
            colors = C.colors_for(c.people())
            total = buf.get_char_count()
            for cur in c.cursors:
                name = cur.get("by") or "?"
                col = colors.get(name, C.color_for(name))
                i, j = sorted((max(0, min(cur["i"], total)), max(0, min(cur["j"], total))))
                if i < j:                                        # Markierung farbig hinterlegen
                    tag = self._sel_tags.get((buf, col))
                    if tag is None:
                        tag = self._sel_tags[(buf, col)] = buf.create_tag(None, background=col + "55")
                    buf.apply_tag(tag, buf.get_iter_at_offset(i), buf.get_iter_at_offset(j))
                key = (view, f"{name}/{cur.get('dev') or ''}")
                r = view.get_iter_location(buf.get_iter_at_offset(j))
                ent = self._carets.get(key)
                if ent is None:
                    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, can_target=False)
                    lab = Gtk.Label(xalign=0)
                    lab.add_css_class("collab-tag")
                    bar = Gtk.Box(halign=Gtk.Align.START)
                    bar.add_css_class("collab-caret")
                    box.append(lab)
                    box.append(bar)
                    view.add_overlay(box, r.x, max(0, r.y - 15))
                    ent = self._carets[key] = {"box": box, "lab": lab, "bar": bar, "col": None}
                if ent["col"] != col:
                    for w in (ent["lab"], ent["bar"]):
                        if ent["col"]:
                            w.remove_css_class(_color_css(ent["col"]))
                        w.add_css_class(_color_css(col))
                    ent["col"] = col
                ent["lab"].set_label(i18n.tr("du (anderes Gerät)") if name == self.acct.name else name)
                ent["bar"].set_size_request(2, max(12, r.height))
                view.move_overlay(ent["box"], r.x, max(0, r.y - 15))
                ent["box"].set_visible(True)
                shown.add(key)
        for key, ent in self._carets.items():
            if key not in shown:
                ent["box"].set_visible(False)

    # ================================================================ Leiste über dem Dokument
    def make_banner(self):
        rev = Gtk.Revealer(transition_type=Gtk.RevealerTransitionType.SLIDE_DOWN, transition_duration=180)
        box = Gtk.Box(spacing=8)
        box.add_css_class("collab-banner")
        self.b_dot = Gtk.Label(label="●")
        self.b_dot.add_css_class("collab-dot")
        self.b_live = Gtk.Label(label="Live")
        self.b_live.add_css_class("collab-live")
        self.b_chips = Gtk.Box(spacing=5)
        self.b_sub = Gtk.Label(xalign=0, hexpand=True, ellipsize=3)
        self.b_sub.add_css_class("collab-sub")
        self.b_leave = Gtk.Button(label=i18n.tr("trennen"), focus_on_click=False, valign=Gtk.Align.CENTER)
        self.b_leave.add_css_class("pb"); self.b_leave.add_css_class("small")
        self.b_leave.connect("clicked", lambda *_: self.ask_leave(self.bound()))
        for w in (self.b_dot, self.b_live, self.b_chips, self.b_sub, self.b_leave):
            box.append(w)
        self.b_box = box
        rev.set_child(box)
        return rev

    def place_banner(self):
        app = self.app
        row = {"notes": app.note_title_row, "docs": app.writer.title_row, "latex": app.latex.title_row}.get(app.kind)
        if row is None:
            return
        parent = row.get_parent()
        if self.banner.get_parent() is not parent:
            if self.banner.get_parent() is not None:
                self.banner.get_parent().remove(self.banner)
            parent.insert_child_after(self.banner, None)

    def update_banner(self):
        c = self.bound()
        s = None if c else self.session_for(self.cur_key())
        if c is None and (s is None or s["status"] != "pending"):
            self.banner.set_reveal_child(False)
            return
        self.place_banner()
        child = self.b_chips.get_first_child()
        while child:
            self.b_chips.remove(child)
            child = self.b_chips.get_first_child()
        if c is None:                                            # wartet noch auf Freigabe
            self.b_box.add_css_class("off")
            self.b_live.set_label(i18n.tr("Wartet auf Freigabe"))
            self.b_sub.set_label(", ".join(s["members"]) or i18n.tr("nur deine Geräte"))
            self.b_leave.set_label(i18n.tr("zurückziehen"))
            self.banner.set_reveal_child(True)
            return
        ok = c.live.ready and not c.state.get("error")
        (self.b_box.remove_css_class if ok else self.b_box.add_css_class)("off")
        self.b_live.set_label(i18n.tr("Live") if ok else i18n.tr("Verbinde …"))
        colors = C.colors_for(c.people())
        here = {x.get("by") for x in c.cursors}
        for name in c.people():
            chip = Gtk.Label(label=(i18n.tr("du") if name == self.acct.name else name))
            chip.add_css_class("collab-chip")
            chip.add_css_class(_color_css(colors.get(name, C.color_for(name))))
            chip.set_tooltip_text(i18n.tr("gerade da") if name in here or name == self.acct.name else i18n.tr("gerade nicht da"))
            if name not in here and name != self.acct.name:
                chip.set_opacity(0.45)
            self.b_chips.append(chip)
        self.b_sub.set_label(c.state.get("error") or i18n.tr("Änderungen erscheinen sofort bei allen · verschlüsselt"))
        self.b_leave.set_label(i18n.tr("trennen"))
        self.banner.set_reveal_child(True)

    def update_ui(self):
        self.app.writer.collab_author = self.acct.name if self.bound() else None     # „Änderungen verfolgen“: wer
        self.update_button()
        self.update_banner()

    # ================================================================ Knopf unten + Menü
    def make_button(self):
        mb = Gtk.MenuButton(tooltip_text=i18n.tr("Gemeinsam bearbeiten: mit Freunden oder den eigenen Geräten live"))
        self.btn_label = Gtk.Label(label="󰡉 gemeinsam")
        mb.set_child(self.btn_label)
        mb.full_label = "󰡉 gemeinsam"
        mb.add_css_class("tbtn")
        mb.set_valign(Gtk.Align.CENTER)
        mb.set_margin_start(6)
        self.pop = Gtk.Popover(has_arrow=False)
        self.pop.add_css_class("file-menu")
        mb.set_popover(self.pop)
        wr.keep_focus(mb, self.pop)
        self.pop.connect("show", lambda *_: (self.fill(), self.refresh(lambda e: self.pop.get_visible() and self.fill())))
        return mb

    def update_button(self):
        n = len([s for s in self.invites() if s["status"] == "active"])
        live = self.bound() is not None
        if not self.acct.token:
            lab = "󰡉 gemeinsam"
        else:
            lab = "󰡉 gemeinsam" + (f" · {n}" if n else "") + (" ●" if live else "")
        self.btn_label.set_label(lab)
        self.btn.full_label = lab
        (self.btn.add_css_class if (n or live) else self.btn.remove_css_class)("news")

    def _head(self, box, text):
        h = Gtk.Label(label=i18n.tr(text).upper(), xalign=0)
        h.add_css_class("wpop-head")
        box.append(h)

    def _row(self, box, text, btn=None, cb=None, danger=False, dim=False):
        r = Gtk.Box(spacing=10)
        lab = Gtk.Label(label=text, xalign=0, hexpand=True, wrap=True, max_width_chars=44)
        if dim:
            lab.add_css_class("dim-label")
        r.append(lab)
        if btn:
            b = Gtk.Button(label=i18n.tr(btn).lower(), focus_on_click=False, valign=Gtk.Align.CENTER)
            b.add_css_class("pb"); b.add_css_class("small")
            if danger:
                b.add_css_class("danger")
            b.connect("clicked", lambda *_: cb())
            r.append(b)
        box.append(r)
        return r

    def fill(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, margin_start=12, margin_end=12,
                      margin_top=10, margin_bottom=12)
        box.set_size_request(400, -1)
        self.pop.set_child(box)
        if not self.acct.token:
            return self.fill_login(box)
        self._row(box, i18n.tr("Angemeldet als {}", self.acct.name), "abmelden", self.logout, dim=True)
        if not self.acct.has_key:
            self._row(box, "⚠ " + i18n.tr("Für die Verschlüsselung einmal ab- und wieder anmelden."), dim=True)
        app = self.app
        key = self.cur_key()
        n = app.current if key else None
        inv = self.invites()
        if inv:
            self._head(box, "Einladungen")
            for s in inv:
                t = f"{s['owner']}: „{s['title'] or '…'}“ ({KIND_NAME.get(s['kind'], s['kind'])})"
                if s["status"] == "active":
                    self._row(box, t, "beitreten", lambda s=s: (self.pop.popdown(), self.show_invite(s, force=True)))
                else:
                    self._row(box, t + " · " + i18n.tr("wartet auf Freigabe"), dim=True)
        if n is not None:
            self._head(box, "Dieses Dokument")
            s = self.session_for(key)
            if s is None:
                self.fill_invite(box)
            else:
                c = self.conns.get(s["id"])
                who = ", ".join(c.people() if c else [s["owner"]] + s["members"])
                if s["status"] == "pending":
                    self._row(box, i18n.tr("Wartet auf Freigabe · {}", who), dim=True)
                else:
                    self._row(box, i18n.tr("Live mit {}", who))
                if self.problem.get(s["id"]):
                    self._row(box, "⚠ " + self.problem[s["id"]], dim=True)
                    if s["owner"] != self.acct.name:
                        self.code_entry(box, s, then=lambda: (self.connect_all(), self.fill()))
                if s["owner"] == self.acct.name and s["members"]:
                    try:
                        code = C.fmt_code(self.acct.code_for(s))
                        self._row(box, i18n.tr("Sitzungs-Code für die Eingeladenen: {}", code), "kopieren",
                                  lambda c=code: (self.btn.get_clipboard().set(c), self.app.notify(i18n.tr("Code kopiert"))))
                    except C.CollabError as e:
                        self._row(box, "⚠ " + str(e), dim=True)
                self._row(box, "", "trennen …", lambda s=s: (self.pop.popdown(), self.ask_leave(self.conns.get(s["id"]), s)),
                          danger=True)
        others = [c for c in self.conns.values() if not self.is_open(c)]
        if others:
            self._head(box, "Auch verbunden")
            for c in others:
                self._row(box, f"„{c.s['title'] or '…'}“ · {', '.join(x for x in c.people() if x != self.acct.name)}",
                          "öffnen", lambda c=c: self.open_key(c.key))

    def fill_invite(self, box):
        """Freunde antippen (musicalist) oder Namen eintippen – leer = nur die eigenen Geräte."""
        picked = set()
        if self.friends:
            flow = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, max_children_per_line=4, column_spacing=6,
                               row_spacing=6, homogeneous=False)
            for f in self.friends:
                tb = Gtk.ToggleButton(label=f.get("display") or f["name"], focus_on_click=False)
                tb.add_css_class("pb"); tb.add_css_class("small"); tb.add_css_class("collab-friend")
                tb.set_tooltip_text(f["name"])
                tb.connect("toggled", lambda b, nm=f["name"]: picked.add(nm) if b.get_active() else picked.discard(nm))
                flow.append(tb)
            box.append(Gtk.Label(label=i18n.tr("Deine musicalist-Freunde – antippen zum Einladen:"), xalign=0))
            box.append(flow)
        ent = Gtk.Entry(placeholder_text=i18n.tr("weitere Namen, mit Komma"), hexpand=True)
        box.append(ent)
        self.err = Gtk.Label(xalign=0, wrap=True)
        self.err.add_css_class("error")
        go = Gtk.Button(label=i18n.tr("Einladen"), focus_on_click=False, hexpand=True)
        go.add_css_class("collab-signin")
        go.connect("clicked", lambda *_: self.invite(sorted(picked) + [x.strip().lower() for x in ent.get_text().replace(";", ",").split(",") if x.strip()]))
        ent.connect("activate", lambda *_: go.emit("clicked"))
        box.append(go)
        box.append(Gtk.Label(label=i18n.tr("Niemanden auswählen = zwischen deinen eigenen Geräten (PC, Mac, Handy)."),
                             xalign=0, wrap=True, max_width_chars=48, css_classes=["dim-label"]))
        box.append(self.err)

    def code_entry(self, box, s, then, label="übernehmen"):
        """Sitzungs-Code eintippen (bekommt man von der Einladenden, z. B. per WhatsApp)."""
        r = Gtk.Box(spacing=8)
        ent = Gtk.Entry(placeholder_text=i18n.tr("Sitzungs-Code (z. B. 7KQ2-…)"), hexpand=True)
        b = Gtk.Button(label=i18n.tr(label).lower(), focus_on_click=False)
        b.add_css_class("pb"); b.add_css_class("small")

        def go(*_):
            try:
                self.acct.set_code(s["id"], ent.get_text())
            except C.CollabError as e:
                ent.add_css_class("error")
                ent.set_tooltip_text(str(e))
                return
            self.problem.pop(s["id"], None)
            then()
        ent.connect("activate", go)
        b.connect("clicked", go)
        r.append(ent)
        r.append(b)
        box.append(r)
        return ent

    def fill_login(self, box):
        t = Gtk.Label(label=i18n.tr("Gemeinsam bearbeiten"), xalign=0)
        t.add_css_class("title-4")
        box.append(t)
        box.append(Gtk.Label(label=i18n.tr("Mit deinem musicalist-Konto (gleicher Name, gleiches Passwort) bearbeitest du "
                                           "Dokumente live zusammen mit Freunden oder zwischen PC, Mac und Handy. "
                                           "Für alles andere in notist brauchst du kein Konto."),
                             xalign=0, wrap=True, max_width_chars=48))
        name = Gtk.Entry(placeholder_text=i18n.tr("Nutzername"))
        pw = Gtk.PasswordEntry(placeholder_text=i18n.tr("Passwort"), show_peek_icon=True)
        err = Gtk.Label(xalign=0, wrap=True)
        err.add_css_class("error")
        btn = Gtk.Button(label=i18n.tr("Mit musicalist-Konto anmelden"), hexpand=True)
        btn.add_css_class("collab-signin")

        def go(*_):
            btn.set_sensitive(False)
            btn.set_label(i18n.tr("Melde an …"))
            err.set_label("")

            def done(r, e):
                btn.set_sensitive(True)
                btn.set_label(i18n.tr("Mit musicalist-Konto anmelden"))
                if e is not None:
                    err.set_label(str(e))
                    return
                self.app.notify(i18n.tr("Angemeldet als {}", r))
                self.refresh(lambda _e: self.pop.get_visible() and self.fill())
            _bg(lambda: self.acct.login(name.get_text(), pw.get_text(), "notist"), done)
        for w in (name, pw):
            w.connect("activate", go)
        btn.connect("clicked", go)
        for w in (name, pw, btn, err):
            box.append(w)
        GLib.idle_add(lambda: (name.grab_focus(), False)[1])

    # ================================================================ Aktionen
    def logout(self):
        self.stop_all()
        _bg(self.acct.logout, lambda r, e: (self.refresh(), self.fill()))

    def invite(self, names):
        app = self.app
        n = app.current
        if not n:
            return
        app.flush(force=True)
        kind, key = app.kind, f"{app.kind}:{n['id']}"
        title = app.display_title(n, kind)

        def done(r, e):
            if e is not None:
                self.err.set_label(str(e))
                return
            self.acct.link(r["id"], key)
            self.pop.popdown()
            if r.get("members"):
                try:
                    code = C.fmt_code(self.acct.code_for(r))
                    self.btn.get_clipboard().set(code)
                    msg = i18n.tr("Sitzungs-Code {} ist kopiert – gib ihn den Eingeladenen (z. B. per WhatsApp)", code)
                except C.CollabError as e2:
                    msg = str(e2)
            else:
                msg = ""
            self.app.notify((i18n.tr("Eingeladen.") + " " + msg + " " + (
                i18n.tr("Los geht's, sobald die Einladung freigegeben ist.") if r["status"] != "active" else "")).strip(), ms=15000)
            self.refresh()
        _bg(lambda: self.acct.invite(kind, title, key, names), done)

    def ask_leave(self, c, s=None):
        """Trennen nur mit klarer Warnung."""
        s = s or (c.s if c else None)
        if s is None:
            return
        mine = s["owner"] == self.acct.name
        others = [x for x in [s["owner"]] + s["members"] if x != self.acct.name]
        if s["status"] == "pending":
            title, msg, ok = "Einladung zurückziehen?", i18n.tr("Die Einladung wird zurückgezogen, bevor sie freigegeben ist."), "Zurückziehen"
        elif mine:
            title = "Gemeinsame Bearbeitung beenden?"
            msg = i18n.tr("Damit endet sie für alle ({}). Jede·r behält die eigene Fassung, aber Änderungen werden nicht mehr "
                          "abgeglichen. Wieder verbinden geht nur mit einer neuen Einladung.", ", ".join(others) or i18n.tr("deine Geräte"))
            ok = "Für alle beenden"
        else:
            title = "Verbindung trennen?"
            msg = i18n.tr("Du verlässt die gemeinsame Bearbeitung mit {}. Deine Fassung bleibt bei dir, aber Änderungen der "
                          "anderen kommen nicht mehr an – und deine nicht mehr bei ihnen. Zurück geht es nur mit einer neuen "
                          "Einladung.", ", ".join(others))
            ok = "Trennen"
        dialogs.choice(self.app.win, title, msg, [("Abbrechen", None, False), (ok, True, True)],
                       lambda _v: self.end(s))

    def end(self, s):
        self.drop(s["id"])

        def done(r, e):
            self.acct.unlink(s["id"])
            self.app.notify(i18n.tr("Getrennt – deine Fassung bleibt") if e is None else str(e))
            self.refresh()
        _bg(lambda: self.acct.end(s["id"]), done)

    def ask_invites(self):
        """Neue Einladung → Popup (einmal je Einladung; danach im Menü unter „Einladungen“)."""
        asked = self.acct.st.setdefault("asked", [])
        for s in self.invites():
            if s["status"] == "active" and s["id"] not in asked and self._popup is None:
                asked.append(s["id"])
                del asked[:-200]
                self.acct._save()
                self.show_invite(s)
                return

    def show_invite(self, s, force=False):
        """„anna lädt dich ein“ – Code eintippen, beitreten (neues Dokument oder das offene)."""
        if self._popup is not None and not force:
            return
        win = Gtk.Window(title=i18n.tr("Einladung"), transient_for=self.app.win, modal=True, resizable=False, default_width=460)
        win.add_css_class("settings")
        col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, margin_start=16, margin_end=16, margin_top=6, margin_bottom=16)
        head = Gtk.Box(spacing=8)
        col_ = C.color_for(s["owner"])
        chip = Gtk.Label(label=s["owner"])
        chip.add_css_class("collab-chip")
        chip.add_css_class(_color_css(col_))
        head.append(chip)
        head.append(Gtk.Label(label=i18n.tr("lädt dich ein, gemeinsam zu bearbeiten:"), xalign=0))
        col.append(head)
        t = Gtk.Label(label=f"„{s['title'] or '…'}“ · {KIND_NAME.get(s['kind'], s['kind'])}", xalign=0)
        t.add_css_class("title-4")
        col.append(t)
        has_code = bool((self.acct.st.get("codes") or {}).get(s["id"]))
        ent = None
        if not has_code:
            col.append(Gtk.Label(label=i18n.tr("Den Sitzungs-Code bekommst du von {} (z. B. per WhatsApp).", s["owner"]),
                                 xalign=0, wrap=True, max_width_chars=50, css_classes=["dim-label"]))
            ent = Gtk.Entry(placeholder_text=i18n.tr("Sitzungs-Code (z. B. 7KQ2-…)"))
            col.append(ent)
        err = Gtk.Label(xalign=0, wrap=True)
        err.add_css_class("error")
        col.append(err)
        row = Gtk.Box(spacing=8, halign=Gtk.Align.END, margin_top=4)

        def join(into_current):
            if ent is not None:
                try:
                    self.acct.set_code(s["id"], ent.get_text())
                except C.CollabError as e:
                    err.set_label(str(e))
                    return
            win.close()
            if into_current:
                self.join_current(s)
            else:
                self.open_invite(s)

        later = Gtk.Button(label=i18n.tr("später"))
        later.connect("clicked", lambda *_: win.close())
        row.append(later)
        if self.app.current is not None and self.app.view != "home" and self.app.kind == s["kind"]:
            cur = Gtk.Button(label=i18n.tr("ins offene Dokument"))
            cur.set_tooltip_text(i18n.tr("Das offene Dokument wird durch den gemeinsamen Stand ersetzt – eine Version davor "
                                         "bleibt im Verlauf."))
            cur.connect("clicked", lambda *_: join(True))
            row.append(cur)
        go = Gtk.Button(label=i18n.tr("Beitreten"))
        go.add_css_class("collab-signin")
        go.connect("clicked", lambda *_: join(False))
        row.append(go)
        for b in row:
            if b is not go:
                b.add_css_class("pb"); b.add_css_class("small")
        col.append(row)
        dialogs.chrome(win, "Einladung", col)
        win.connect("close-request", lambda *_: (setattr(self, "_popup", None), False)[1])
        self._popup = win
        win.present()
        (ent or go).grab_focus()

    def open_invite(self, s):
        """Einladung annehmen: neuer Eintrag, der sich gleich mit dem gemeinsamen Stand füllt."""
        app = self.app
        st = app.stores[s["kind"]]
        n = st.create()
        n["title"] = s["title"] or i18n.tr("Gemeinsam mit {}", s["owner"])
        if s["kind"] == "docs":
            n["blocks"] = [df.para()]
        st.save(n)
        self.acct.link(s["id"], f"{s['kind']}:{n['id']}")
        self.open_key(f"{s['kind']}:{n['id']}")
        self.connect_all()

    def join_current(self, s):
        """Ins gerade offene Dokument beitreten (Version davor bleibt im Verlauf)."""
        app = self.app
        n = app.current
        if n is None:
            return
        app.flush(force=True)
        app.stores[app.kind].snapshot(n, force=True)
        self.acct.link(s["id"], f"{app.kind}:{n['id']}")
        self.connect_all()
        self.selected()

    def open_key(self, key):
        kind, _, nid = key.partition(":")
        self.pop.popdown()
        self.app.home_open(kind, nid)
