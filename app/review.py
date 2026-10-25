# Words → Reiter „Überprüfen“: Kommentare und Änderungen nachverfolgen.
# Text-Tags im Puffer: cm:<id> (Kommentar-Bereich), tc:ins / tc:del (nachverfolgte Einfügung/Löschung). Sie wandern als
# Laufschlüssel "cm"/"tc" durchs Blockmodell (docfmt.RUN_KEYS) und nach DOCX (w:comment…, w:ins/w:del). Kommentartexte
# liegen in page["comments"] = {id: {text, author, time}}, das Nachverfolgen-Flag in page["track"].
import datetime
import uuid

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, GLib, Gtk, Pango


class ReviewMixin:
    """In Writer eingemischt (self.buf, self.view, self.page, self.checkpoint(), self.changed() …)."""

    # ---------------------------------------------------------------- Tags
    def make_review_tags(self):
        from writer import rgba
        b = self.buf
        self.tc_ins = b.create_tag("tc:ins", foreground_rgba=rgba("#2e9d5c"), underline=Pango.Underline.SINGLE)
        self.tc_del = b.create_tag("tc:del", foreground_rgba=rgba("#e5534b"), strikethrough=True)
        self._tc_busy = False
        self.cm_pop = None

    def comment_tag(self, cid):
        from writer import rgba
        name = "cm:" + cid
        t = self.buf.get_tag_table().lookup(name)
        return t or self.buf.create_tag(name, background_rgba=rgba("#ffb300", 0.28))

    # ---------------------------------------------------------------- UI
    def build_review(self, pg, group):
        from writer import big_tool, popover_button, big_label, tool
        self.tools["track"] = big_tool("󰏫", "Verfolgen", "Änderungen nachverfolgen (Strg+Umschalt+E)", toggle=True)
        self.tools["track"].connect("toggled", lambda b: self._sync or self.set_track(b.get_active()))
        self.cm_list_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, width_request=340)
        cm_btn, self.cm_list_pop = popover_button(big_label("󰍩", "Alle"), "Alle Kommentare des Dokuments",
                                                   self.cm_list_box, big=True)
        self.cm_list_pop.connect("show", lambda *_: self.fill_comment_list())
        group(pg, "Kommentare", [big_tool("󰍪", "Neu", "Kommentar zur Markierung hinzufügen (Strg+Alt+M)",
                                           lambda *_: self.new_comment()), cm_btn,
                                 big_tool("󰒮", "Zurück", "Vorheriger Kommentar", lambda *_: self.goto_comment(-1)),
                                 big_tool("󰒭", "Weiter", "Nächster Kommentar", lambda *_: self.goto_comment(1))])
        group(pg, "Änderungen", [self.tools["track"],
                                 big_tool("󰄬", "Annehmen", "Änderung an der Schreibmarke annehmen",
                                          lambda *_: self.resolve_change(True)),
                                 big_tool("󰜺", "Ablehnen", "Änderung an der Schreibmarke ablehnen",
                                          lambda *_: self.resolve_change(False)),
                                 big_tool("󰒮", "Zurück", "Vorherige Änderung", lambda *_: self.goto_change(-1)),
                                 big_tool("󰒭", "Weiter", "Nächste Änderung", lambda *_: self.goto_change(1))],
              [tool("󰄬 Alle annehmen", "Alle nachverfolgten Änderungen übernehmen", lambda *_: self.resolve_all(True)),
               tool("󰜺 Alle ablehnen", "Alle nachverfolgten Änderungen verwerfen", lambda *_: self.resolve_all(False))])
        lang = []
        for code, text in (("de", "Deutsch"), ("en", "English")):
            b = big_tool("󰗊", text, f"Dokumentsprache {text}: Rechtschreibung und Anführungszeichen", toggle=True)
            b.connect("toggled", lambda btn, c=code: self._sync or not btn.get_active() or self.set_language(c))
            self.tools["lang:" + code] = b
            lang.append(b)
        group(pg, "Sprache", lang)
        group(pg, "Prüfen", [big_tool("󰄨", "Wörter", "Wörter, Zeichen, Absätze zählen", lambda *_: self.show_stats())],
              last=True)

    def set_language(self, code):
        app = self.win.get_application()
        if app is not None and hasattr(app, "set_doc_lang"):
            app.set_doc_lang(code)
        self.sync_review()

    def sync_review(self):
        self._sync = True
        try:
            if "track" in self.tools:
                self.tools["track"].set_active(bool(self.page.get("track")))
            app = self.win.get_application()
            cur = app.doc_lang() if app is not None and hasattr(app, "doc_lang") else "de"
            for code in ("de", "en"):
                if "lang:" + code in self.tools:
                    self.tools["lang:" + code].set_active(code == cur)
        finally:
            self._sync = False

    # ---------------------------------------------------------------- Kommentare
    def author_name(self):
        real = GLib.get_real_name()
        return self.page.get("author") or (real if real and real != "Unknown" else "") or GLib.get_user_name() or "notist"

    def comment_at(self, it):
        for t in it.get_tags():
            n = t.props.name or ""
            if n.startswith("cm:") and n[3:] in self.page["comments"]:
                return n[3:]
        return None

    def comment_range(self, cid):
        tag = self.buf.get_tag_table().lookup("cm:" + cid)
        if tag is None:
            return None
        it = self.buf.get_start_iter()
        if not it.has_tag(tag) and not it.forward_to_tag_toggle(tag):
            return None
        end = it.copy()
        end.forward_to_tag_toggle(tag)
        return it, end

    def new_comment(self):
        if not self.editable:
            return
        b = self.buf.get_selection_bounds()
        if not b:                                            # ohne Markierung: Wort am Cursor
            it = self.buf.get_iter_at_mark(self.buf.get_insert())
            s, e = it.copy(), it.copy()
            if not s.starts_word():
                s.backward_word_start()
            if not e.ends_word():
                e.forward_word_end()
            if s.equal(e):
                return
            b = (s, e)
        s, e = b
        self.checkpoint()
        cid = uuid.uuid4().hex[:12]
        self.page["comments"][cid] = {"text": "", "author": self.author_name(),
                                      "time": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")}
        self.buf.apply_tag(self.comment_tag(cid), s, e)
        self.changed()
        self.on_change()
        self.open_comment(cid, new=True)

    def open_comment(self, cid, new=False):
        """Kleines Fenster am Kommentar: Text bearbeiten, löschen, schließen."""
        c = self.page["comments"].get(cid)
        rng = self.comment_range(cid)
        if not c or not rng:
            return
        self.close_comment()
        pop = Gtk.Popover(has_arrow=False, autohide=False, can_focus=True)
        pop.add_css_class("wpop")
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, width_request=300)
        head = Gtk.Label(label=f"{c.get('author', '')} · {self.nice_time(c.get('time'))}".strip(" ·"), xalign=0)
        head.add_css_class("wpop-head")
        box.append(head)
        tv = Gtk.TextView(wrap_mode=Gtk.WrapMode.WORD_CHAR, top_margin=4, bottom_margin=4, left_margin=6, right_margin=6)
        tv.add_css_class("cm-text")
        tv.get_buffer().set_text(c.get("text", ""))
        sc = Gtk.ScrolledWindow(min_content_height=70, max_content_height=200, propagate_natural_height=True)
        sc.set_child(tv)
        box.append(sc)
        row = Gtk.Box(spacing=6)
        save = Gtk.Button(label="Fertig", focus_on_click=False)
        save.add_css_class("pb")
        rm = Gtk.Button(label="Löschen", focus_on_click=False)
        rm.add_css_class("pb")
        row.append(save)
        row.append(rm)
        box.append(row)
        pop.set_child(box)

        def commit(*_):
            txt = tv.get_buffer().get_text(*tv.get_buffer().get_bounds(), False).strip()
            if self.page["comments"].get(cid) is not None:
                if not txt and new:                           # leerer neuer Kommentar: nichts anlegen
                    self.delete_comment(cid)
                else:
                    self.page["comments"][cid]["text"] = txt
                    self.on_change()
            self.close_comment()
            self.focus_text()
        save.connect("clicked", commit)
        rm.connect("clicked", lambda *_: (self.delete_comment(cid), self.close_comment(), self.focus_text()))
        k = Gtk.EventControllerKey()
        k.connect("key-pressed", lambda _c, kv, _code, st: (kv == Gdk.KEY_Return and not st & Gdk.ModifierType.SHIFT_MASK
                                                            and (commit(), True)[1]) or
                  (kv == Gdk.KEY_Escape and (commit(), True)[1]))
        tv.add_controller(k)
        pop.set_parent(self.view)
        r = self.view.get_iter_location(rng[0])
        x, y = self.view.buffer_to_window_coords(Gtk.TextWindowType.WIDGET, r.x, r.y)
        rect = Gdk.Rectangle()
        rect.x, rect.y, rect.width, rect.height = int(x), int(y), 2, max(1, r.height)
        pop.set_pointing_to(rect)
        pop.set_position(Gtk.PositionType.BOTTOM)
        from writer import close_outside
        close_outside(pop)
        pop.connect("closed", lambda p: GLib.idle_add(lambda: (p.unparent(), False)[1]))
        self.cm_pop = pop
        pop.popup()
        GLib.idle_add(lambda: (tv.grab_focus(), False)[1])

    def close_comment(self):
        p = self.cm_pop
        self.cm_pop = None
        if p is not None and p.get_visible():
            p.popdown()

    def delete_comment(self, cid):
        self.checkpoint()
        rng = self.comment_range(cid)
        tag = self.buf.get_tag_table().lookup("cm:" + cid)
        if rng and tag:
            self.buf.remove_tag(tag, self.buf.get_start_iter(), self.buf.get_end_iter())
        self.page["comments"].pop(cid, None)
        self.changed()
        self.on_change()

    @staticmethod
    def nice_time(t):
        try:
            d = datetime.datetime.fromisoformat((t or "")[:19])
            return d.strftime("%d.%m.%Y %H:%M")
        except ValueError:
            return t or ""

    def comments_in_order(self):
        """[(offset, id)] nach Stelle im Text."""
        out = []
        for cid in self.page["comments"]:
            rng = self.comment_range(cid)
            if rng:
                out.append((rng[0].get_offset(), cid))
        return sorted(out)

    def fill_comment_list(self):
        box = self.cm_list_box
        while (c := box.get_first_child()):
            box.remove(c)
        items = self.comments_in_order()
        if not items:
            l = Gtk.Label(label="Noch keine Kommentare – Text markieren und „Neu“ wählen.", xalign=0, wrap=True,
                          max_width_chars=36)
            l.add_css_class("hf-help")
            box.append(l)
            return
        for off, cid in items:
            c = self.page["comments"][cid]
            rng = self.comment_range(cid)
            quote = self.buf.get_text(*rng, False).strip().replace("\n", " ")[:50] if rng else ""
            b = Gtk.Button(focus_on_click=False)
            b.add_css_class("wt")
            v = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
            t = Gtk.Label(label=f"„{quote}“", xalign=0, ellipsize=3)
            t.add_css_class("wpop-head")
            body = Gtk.Label(label=(c.get("text") or "(leer)"), xalign=0, wrap=True, max_width_chars=40)
            who = Gtk.Label(label=f"{c.get('author', '')} · {self.nice_time(c.get('time'))}", xalign=0)
            who.add_css_class("hf-help")
            for w in (t, body, who):
                v.append(w)
            b.set_child(v)
            b.connect("clicked", lambda _b, i=cid: (self.cm_list_pop.popdown(), self.goto_comment_id(i)))
            box.append(b)

    def goto_comment_id(self, cid):
        rng = self.comment_range(cid)
        if not rng:
            return
        self.buf.place_cursor(rng[0])
        self.view.scroll_to_iter(rng[0], 0.15, True, 0, 0.3)
        GLib.timeout_add(120, lambda: (self.open_comment(cid), False)[1])

    def goto_comment(self, d):
        items = self.comments_in_order()
        if not items:
            return
        cur = self.buf.get_iter_at_mark(self.buf.get_insert()).get_offset()
        if d > 0:
            pick = next((i for o, i in items if o > cur), items[0][1])
        else:
            pick = next((i for o, i in reversed(items) if o < cur), items[-1][1])
        self.goto_comment_id(pick)

    # ---------------------------------------------------------------- Änderungen verfolgen
    def set_track(self, on):
        self.page["track"] = bool(on)
        self.on_change()
        self.sync_review()
        self.focus_text()

    def tracking(self):
        return bool(self.page.get("track")) and not self._loading and not self._quiet and not self._tc_busy and self.editable

    def track_inserted(self, loc, text):
        """Nach dem Tippen: neu eingefügten Text als Einfügung markieren."""
        if not self.tracking() or not text:
            return
        end = loc.copy()
        start = loc.copy()
        start.backward_chars(len(text))
        self._tc_busy = True
        try:
            self.buf.remove_tag(self.tc_del, start, end)
            self.buf.apply_tag(self.tc_ins, start, end)
        finally:
            self._tc_busy = False

    def track_delete(self, buf, start, end):
        """Vor dem Löschen: eigene (noch nicht angenommene) Einfügungen wirklich entfernen, alles andere nur
        als gelöscht markieren – und das Löschen selbst verhindern."""
        if not self.tracking() or start.equal(end):
            return
        txt = buf.get_text(start, end, True)
        if "￼" in txt:                                    # Bilder/Tabellen: normal löschen
            return
        cursor_at_end = buf.get_iter_at_mark(buf.get_insert()).equal(end)
        a, z = start.get_offset(), end.get_offset()
        segs, it, cur_ins, seg_start = [], buf.get_iter_at_offset(a), None, a
        for i in range(a, z):
            ch = buf.get_iter_at_offset(i)
            ins = ch.has_tag(self.tc_ins)
            if cur_ins is None:
                cur_ins, seg_start = ins, i
            elif ins != cur_ins:
                segs.append((seg_start, i, cur_ins))
                cur_ins, seg_start = ins, i
        segs.append((seg_start, z, cur_ins))
        if all(s[2] for s in segs):                           # nur eigene Einfügungen → ganz normal löschen
            return
        buf.stop_emission_by_name("delete-range")
        self._tc_busy = True
        try:
            for s0, s1, own in segs:
                if not own:
                    buf.apply_tag(self.tc_del, buf.get_iter_at_offset(s0), buf.get_iter_at_offset(s1))
        finally:
            self._tc_busy = False
        dels = [(s0, s1) for s0, s1, own in segs if own]

        def finish():
            self._tc_busy = True
            try:
                for s0, s1 in sorted(dels, reverse=True):
                    buf.delete(buf.get_iter_at_offset(s0), buf.get_iter_at_offset(s1))
                removed = sum(s1 - s0 for s0, s1 in dels)
                pos = a if cursor_at_end else z - removed          # Rücktaste: davor · Entf: dahinter
                buf.place_cursor(buf.get_iter_at_offset(max(0, pos)))
            finally:
                self._tc_busy = False
            self.changed()
            return False
        GLib.idle_add(finish)

    def change_at(self, it):
        for t in it.get_tags():
            if t is self.tc_ins or t is self.tc_del:
                return t
        return None

    def change_bounds(self, it, tag):
        s = it.copy()
        if not s.starts_tag(tag):
            s.backward_to_tag_toggle(tag)
        e = it.copy()
        e.forward_to_tag_toggle(tag)
        return s, e

    def resolve_change(self, accept):
        it = self.buf.get_iter_at_mark(self.buf.get_insert())
        tag = self.change_at(it)
        if tag is None:
            prev = it.copy()
            if prev.backward_char():
                tag = self.change_at(prev)
                it = prev
        if tag is None:
            return
        s, e = self.change_bounds(it, tag)
        self.checkpoint()
        self._tc_busy = True
        try:
            keep = (tag is self.tc_ins) == accept                 # Einfügung annehmen / Löschung ablehnen = Text bleibt
            if keep:
                self.buf.remove_tag(tag, s, e)
            else:
                self.buf.delete(s, e)
        finally:
            self._tc_busy = False
        self.changed()

    def resolve_all(self, accept):
        self.checkpoint()
        self._tc_busy = True
        try:
            for tag, keep in ((self.tc_del, not accept), (self.tc_ins, accept)):
                while True:
                    it = self.buf.get_start_iter()
                    if not it.has_tag(tag) and not it.forward_to_tag_toggle(tag):
                        break
                    if not it.has_tag(tag):
                        break
                    s, e = self.change_bounds(it, tag)
                    if keep:
                        self.buf.remove_tag(tag, s, e)
                    else:
                        self.buf.delete(s, e)
        finally:
            self._tc_busy = False
        self.changed()

    def goto_change(self, d):
        it = self.buf.get_iter_at_mark(self.buf.get_insert())
        starts = []
        for tag in (self.tc_ins, self.tc_del):
            p = self.buf.get_start_iter()
            while True:
                if not p.has_tag(tag) and not p.forward_to_tag_toggle(tag):
                    break
                if not p.has_tag(tag):
                    break
                s, e = self.change_bounds(p, tag)
                starts.append(s.get_offset())
                p = e
                if p.is_end():
                    break
        starts = sorted(set(starts))
        if not starts:
            return
        cur = it.get_offset()
        pick = next((o for o in starts if o > cur), starts[0]) if d > 0 else \
            next((o for o in reversed(starts) if o < cur), starts[-1])
        target = self.buf.get_iter_at_offset(pick)
        self.buf.place_cursor(target)
        self.view.scroll_to_iter(target, 0.15, True, 0, 0.3)
