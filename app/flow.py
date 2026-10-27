# Words „fließend“ – die zweite Ansicht neben „Seiten“ (wie Notion statt Word), im selben Editor und Dateiformat:
#   · kein Papier, keine Seitenumbrüche: eine ruhige Textspalte in den Farben der App
#   · statt Menüband eine schlanke Leiste (Datei, Rückgängig, Ansicht wechseln)
#   · „/“ am Zeilenanfang (oder nach einem Leerzeichen) öffnet das Blockmenü; weitertippen filtert,
#     ↑/↓ wählt, Enter/Tab fügt ein, Esc schließt
#   · Text markieren → kleine Formatleiste (F K U S, Überschriften, Zitat, Code, Link)
#   · Maus über einer Zeile → „+“ links davon öffnet das Blockmenü für diese Zeile
#   · leere Zeile mit Cursor zeigt den Hinweis „tippe / für blöcke“
# Export, Drucken und PDF bleiben seitenweise (render.py) – die Ansicht betrifft nur den Bildschirm.
import datetime

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Graphene", "1.0")
from gi.repository import Gdk, GLib, Graphene, Gtk, Pango

COL = 720           # Textspalte bei 100 % (px)
GUTTER = 44         # Platz links für „+“

# (schlüssel, symbol, name, suchwörter)
BLOCKS = (
    ("normal", "󰊄", "text", "text absatz normal paragraph"),
    ("h1", "󰉫", "überschrift 1", "h1 heading titel überschrift"),
    ("h2", "󰉬", "überschrift 2", "h2 heading überschrift"),
    ("h3", "󰉭", "überschrift 3", "h3 heading überschrift"),
    ("bullet", "󰉹", "aufzählung", "liste bullet aufzählung punkt"),
    ("number", "󰉻", "nummerierung", "liste nummer number zahl"),
    ("quote", "󰝗", "zitat", "zitat quote"),
    ("code", "󰅩", "code", "code programm mono"),
    ("hr", "󰇘", "trennlinie", "linie trenner divider hr"),
    ("table", "󰓫", "tabelle", "tabelle table"),
    ("image", "󰋩", "bild …", "bild image foto"),
    ("toc", "󰠶", "inhaltsverzeichnis", "inhalt toc verzeichnis"),
    ("pdf", "󰈦", "pdf", "pdf anhang datei dokument"),
    ("date", "󰃭", "datum von heute", "datum date heute"),
    ("footnote", "󰯃", "fußnote", "fußnote footnote"),
)

CSS = """
textview.page.flow, textview.page.flow text { color: @foreground; }
.desk.flow { background: none; }
.flowbar { margin: 2px 0 6px 0; padding: 2px 4px; border-bottom: 1px solid alpha(@primary, 0.25); }
.flowbar .flow-hint { font-size: 11px; color: @secondary; }
.flowbar .fsep { min-width: 1px; min-height: 16px; background-color: alpha(@primary, 0.3); margin: 4px 5px; }
.flowbar menubutton.wt > button { min-width: 22px; }
popover.slash > contents { padding: 4px; min-width: 240px; }
popover.slash button.sl-item { background: none; background-image: none; border: 1px solid transparent; box-shadow: none;
    border-radius: 4px; padding: 3px 8px; min-height: 0; color: @foreground; }
popover.slash button.sl-item.cur { background-color: @primary; color: @on_primary; }
popover.slash button.sl-item.cur .sl-icon { color: @on_primary; }
popover.slash .sl-icon { color: @primary; min-width: 22px; font-size: 14px; }
popover.slash .sl-name { font-size: 13px; }
popover.slash .sl-empty { color: @secondary; font-size: 12px; padding: 4px 8px; }
popover.bubble > contents { padding: 2px 4px; }
popover.bubble button { background: none; background-image: none; box-shadow: none; border: 1px solid transparent;
    border-radius: 4px; min-height: 0; min-width: 0; padding: 1px 7px; color: @foreground; font-size: 13px; }
popover.bubble button:hover { background-color: @primary; color: @on_primary; }
popover.bubble button.on { background-color: alpha(@primary, 0.25); border-color: @primary; }
popover.bubble .bsep { min-width: 1px; background-color: alpha(@primary, 0.35); margin: 3px 3px; }
"""


def rgba(s, a=1.0):
    c = Gdk.RGBA()
    c.parse(s)
    c.alpha = a
    return c


class FlowMode:
    def __init__(self, w):
        self.w = w
        self.slash_mark = None          # Position des „/“ (Blockmenü offen)
        self.slash_line = None          # Blockmenü über das „+“ (ohne „/“)
        self.items, self.cur = [], 0
        self.hover_line = None
        self._bubble_id = None
        self.build_slash()
        self.build_bubble()
        m = Gtk.EventControllerMotion()
        m.connect("motion", self.on_motion)
        m.connect("leave", lambda *_: (self.set_hover(None), self.set_pointer(False)))
        w.view.add_controller(m)
        click = Gtk.GestureClick()
        click.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        click.connect("pressed", self.on_press)
        w.view.add_controller(click)
        w.buf.connect_after("changed", lambda *_: self.on_changed())
        w.buf.connect_after("mark-set", self.on_mark)
        w.scroll.get_vadjustment().connect("value-changed", self.on_scroll)
        self._scroll_id = None

    # ================= Geometrie / Zeichnen =================
    def geometry(self, width):
        z = self.w.zoom
        col = max(200, min(width - 2 * 24 - GUTTER, COL * z))
        side = max(GUTTER + 8, (width - col) / 2)
        return dict(side=side, page_w=col, page_h=0, scale=1.0, k=z, mt=0, mr=0, mb=0, ml=0, m=0, text_w=col,
                    gap=0, flow=True)

    def draw(self, snap):
        """Hinweis in der leeren Cursor-Zeile + „+“ neben der Zeile unter der Maus."""
        w = self.w
        view, buf = w.view, w.buf
        fg = w.fg_hex if hasattr(w, "fg_hex") else "#e0e0e0"
        if view.has_focus() and not buf.get_has_selection() and w.editable and self.slash_mark is None:
            it = buf.get_iter_at_mark(buf.get_insert())
            if it.starts_line() and it.ends_line():
                a = w.para_at(it.get_line())
                hint = {"h1": "überschrift 1", "h2": "überschrift 2", "h3": "überschrift 3", "quote": "zitat",
                        "code": "code"}.get(a["style"]) or ("listenpunkt" if a["list"] else
                                                            "tippe „/“ für blöcke – oder einfach schreiben")
                r = view.get_iter_location(it)
                lay = view.create_pango_layout(hint)
                size = {"h1": 20, "h2": 16, "h3": 13, "code": 10}.get(a["style"], 11)
                lay.set_font_description(Pango.FontDescription.from_string(f"Noto Sans {size * w.zoom:.1f}"))
                snap.save()
                snap.translate(Graphene.Point().init(r.x + 1, r.y))
                snap.append_layout(lay, rgba(fg, 0.35))
                snap.restore()
        ln = self.hover_line
        if ln is not None and w.editable and ln < buf.get_line_count():
            ok, it = buf.get_iter_at_line(ln)
            r = view.get_iter_location(it)          # erste Bildschirmzeile des Absatzes (ohne Abstand darüber)
            x = w.geo["side"] - GUTTER + 10         # „+“ als Vektor: unabhängig von Schriften (Windows ohne Icon-Font)
            half, th = 5.5 * w.zoom, max(1.4, 1.5 * w.zoom)
            cx, cy = x + 7 * w.zoom, r.y + r.height / 2
            col = rgba(fg, 0.55)
            snap.append_color(col, Graphene.Rect().init(cx - half, cy - th / 2, 2 * half, th))
            snap.append_color(col, Graphene.Rect().init(cx - th / 2, cy - half, th, 2 * half))

    # ================= Maus =================
    def line_at(self, x, y):
        bx, by = self.w.view.window_to_buffer_coords(Gtk.TextWindowType.WIDGET, int(x), int(y))
        it, _ = self.w.view.get_line_at_y(by)
        return it.get_line(), bx

    def on_motion(self, ctrl, x, y):
        if not self.w.flow:
            return
        ln, bx = self.line_at(x, y)
        self.set_hover(ln if bx > self.w.geo["side"] - GUTTER - 4 else None)
        side = self.w.geo["side"]
        self.set_pointer(self.w.editable and side - GUTTER <= bx < side - 8)

    def set_pointer(self, on):
        """Über dem „+“ normaler Zeiger statt Text-Cursor."""
        if on != getattr(self, "_pointer", False):
            self._pointer = on
            self.w.view.set_cursor_from_name("pointer" if on else "text")

    def set_hover(self, ln):
        if ln != self.hover_line:
            self.hover_line = ln
            self.w.view.queue_draw()

    def on_press(self, g, n, x, y):
        if not self.w.flow or not self.w.editable:
            return
        ln, bx = self.line_at(x, y)
        side = self.w.geo["side"]
        if side - GUTTER <= bx < side - 8:            # Klick auf „+“
            g.set_state(Gtk.EventSequenceState.CLAIMED)
            GLib.idle_add(lambda: (self.plus(ln), False)[1])

    def plus(self, ln):
        """„+“: leere Zeile → dort das Blockmenü; sonst darunter eine neue Zeile anlegen."""
        w = self.w
        ok, it = w.buf.get_iter_at_line(ln)
        end = it.copy()
        if not end.ends_line():
            end.forward_to_line_end()
        if w.buf.get_text(it, end, True).strip():
            w.buf.place_cursor(end)
            w.view.grab_focus()
            w.buf.insert_at_cursor("\n")
            ln += 1
        else:
            w.buf.place_cursor(it)
            w.view.grab_focus()
        self.slash_line = ln
        self.open_slash()

    # ================= Blockmenü („/“) =================
    def build_slash(self):
        pop = Gtk.Popover(has_arrow=False, autohide=False, can_focus=False)
        pop.add_css_class("wpop")
        pop.add_css_class("slash")
        pop.set_position(Gtk.PositionType.BOTTOM)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        head = Gtk.Label(label="blöcke", xalign=0)
        head.add_css_class("wpop-head")
        box.append(head)
        self.slash_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        sc = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER, propagate_natural_height=True,
                                max_content_height=320, child=self.slash_list)
        box.append(sc)
        self.slash_scroll = sc
        pop.set_child(box)
        pop.set_parent(self.w.view)
        self.slash = pop

    def query(self):
        if self.slash_mark is None:
            return ""
        buf = self.w.buf
        a = buf.get_iter_at_mark(self.slash_mark)
        b = buf.get_iter_at_mark(buf.get_insert())
        return buf.get_text(a, b, False)[1:] if b.compare(a) > 0 else None

    def start(self, it_after_slash):
        """Nach getipptem „/“ (aus writer.after_insert)."""
        if not self.w.flow:
            return
        it = it_after_slash.copy()
        it.backward_char()
        prev = it.copy()
        if not (it.starts_line() or (prev.backward_char() and prev.get_char() in " \t")):
            return
        self.slash_mark = self.w.buf.create_mark(None, it, True)
        self.slash_line = None
        GLib.idle_add(lambda: (self.open_slash(), False)[1])

    def open_slash(self):
        self.cur = 0
        self.fill()
        self.place(self.slash)
        self.slash.popup()

    def place(self, pop, sel=False):
        w = self.w
        buf = w.buf
        if sel:
            s, e = buf.get_selection_bounds()
            r1, r2 = w.view.get_iter_location(s), w.view.get_iter_location(e)
            x0, y0 = min(r1.x, r2.x), min(r1.y, r2.y)
            r = Gdk.Rectangle()
            x, y = w.view.buffer_to_window_coords(Gtk.TextWindowType.WIDGET, x0, y0)
            r.x, r.y, r.width, r.height = int(x), int(y), max(1, abs(r2.x - r1.x)), 1
        else:
            rr = w.view.get_iter_location(buf.get_iter_at_mark(buf.get_insert()))
            x, y = w.view.buffer_to_window_coords(Gtk.TextWindowType.WIDGET, rr.x, rr.y)
            r = Gdk.Rectangle()
            r.x, r.y, r.width, r.height = int(x), int(y), 1, rr.height
        pop.set_pointing_to(r)

    def fill(self):
        q = (self.query() or "").lower().strip()
        box = self.slash_list
        while (c := box.get_first_child()):
            box.remove(c)
        self.items = [b for b in BLOCKS if not q or q in b[2] or any(t.startswith(q) for t in b[3].split())]
        self.cur = min(self.cur, max(0, len(self.items) - 1))
        self.btns = []
        for i, (key, icon, name, _) in enumerate(self.items):
            b = Gtk.Button(focus_on_click=False, can_focus=False)
            b.add_css_class("sl-item")
            if i == self.cur:
                b.add_css_class("cur")
            mo = Gtk.EventControllerMotion()          # Maus zeigt auf einen Eintrag → der ist vorgewählt
            mo.connect("enter", lambda *_a, i=i: self.set_cur(i))
            b.add_controller(mo)
            self.btns.append(b)
            row = Gtk.Box(spacing=8)
            ic = Gtk.Label(label=icon)
            ic.add_css_class("sl-icon")
            nm = Gtk.Label(label=name, xalign=0, hexpand=True)
            nm.add_css_class("sl-name")
            row.append(ic)
            row.append(nm)
            b.set_child(row)
            b.connect("clicked", lambda _b, k=key: self.choose(k))
            box.append(b)
        if not self.items:
            e = Gtk.Label(label="nichts passt – esc schließt", xalign=0)
            e.add_css_class("sl-empty")
            box.append(e)

    def move(self, d):
        if self.items:
            self.set_cur((self.cur + d) % len(self.items), scroll=True)

    def set_cur(self, i, scroll=False):
        """Vorauswahl markieren, ohne die Liste neu zu bauen (sonst springt das Hover-Ziel weg)."""
        self.cur = i
        for k, b in enumerate(getattr(self, "btns", [])):
            (b.add_css_class if k == i else b.remove_css_class)("cur")
        if scroll and 0 <= i < len(self.btns):
            b = self.btns[i]
            ok, r = b.compute_bounds(self.slash_list)
            adj = self.slash_scroll.get_vadjustment()
            if ok:
                top, bot = r.get_y(), r.get_y() + r.get_height()
                if top < adj.get_value():
                    adj.set_value(top)
                elif bot > adj.get_value() + adj.get_page_size():
                    adj.set_value(bot - adj.get_page_size())

    def close_slash(self, remove_text=False):
        buf = self.w.buf
        mark, self.slash_mark = self.slash_mark, None     # zuerst lösen: das Löschen unten meldet mark-set
        self.slash_line = None
        if mark is not None:
            if remove_text:
                a = buf.get_iter_at_mark(mark)
                b = buf.get_iter_at_mark(buf.get_insert())
                if b.compare(a) > 0:
                    self.w._quiet += 1
                    buf.delete(a, b)
                    self.w._quiet -= 1
            buf.delete_mark(mark)
        if self.slash.get_visible():
            self.slash.popdown()
        self.w.view.queue_draw()

    def is_open(self):
        return self.slash.get_visible()

    def choose(self, key):
        self.close_slash(remove_text=True)
        self.insert(key)

    def insert(self, key):
        """Block an der Cursorstelle (aus dem „/“-Menü, dem „+“ oder „einfügen“ in der Leiste)."""
        w = self.w
        w.view.grab_focus()
        if key in ("normal", "h1", "h2", "h3", "quote", "code"):
            w.edit_paras(lambda a: a.update(style=key, list=None if key != "normal" else a["list"]))
        elif key in ("bullet", "number"):
            if w.para_at(w.buf.get_iter_at_mark(w.buf.get_insert()).get_line())["list"] != key:
                w.toggle_list(key)
        elif key == "hr":
            w.insert_block("hr")
        elif key == "table":
            self.ask_table()
            return
        elif key == "image":
            w.pick_image(own_line=True)
        elif key == "toc":
            w.insert_block("toc")
        elif key == "pdf":
            w.pick_pdf()
        elif key == "date":
            w.insert_date()
        elif key == "footnote":
            w.insert_footnote()
        w.changed()

    def ask_table(self):
        """Größe wählen (Raster) an der Cursorstelle, dann einfügen."""
        if getattr(self, "tsize", None) is None:
            from writer import TableSizePicker, ist_pop, close_outside
            pop = close_outside(ist_pop(Gtk.Popover(autohide=False, position=Gtk.PositionType.BOTTOM)))
            pop.set_child(TableSizePicker(self._table_picked))
            pop.set_parent(self.w.view)
            self.tsize = pop
        self.tsize.get_child().reset()
        self.place(self.tsize)
        ok, r = self.tsize.get_pointing_to()
        if ok:                                    # linksbündig am Cursor statt zentriert (ragte sonst links raus)
            pw = self.tsize.get_child().measure(Gtk.Orientation.HORIZONTAL, -1)[1] + 24   # + Rahmen/Innenabstand
            r.width = max(1, min(pw, self.w.view.get_width() - r.x))
            self.tsize.set_pointing_to(r)
        self.tsize.popup()

    def _table_picked(self, rows, cols):
        self.tsize.popdown()
        self.w.view.grab_focus()
        self.w.insert_table(rows, cols)
        self.w.changed()

    # ================= Formatleiste bei Markierung =================
    def build_bubble(self):
        pop = Gtk.Popover(has_arrow=False, autohide=False, can_focus=False)
        pop.add_css_class("wpop")
        pop.add_css_class("bubble")
        pop.set_position(Gtk.PositionType.TOP)
        box = Gtk.Box(spacing=1)
        self.bubble_btns = {}

        def btn(label, tip, cb, key=None, markup=False):
            b = Gtk.Button(focus_on_click=False, can_focus=False, tooltip_text=tip)
            lab = Gtk.Label()
            lab.set_markup(label) if markup else lab.set_label(label)
            b.set_child(lab)
            b.connect("clicked", lambda *_: (cb(), GLib.idle_add(self.sync_bubble)))
            box.append(b)
            if key:
                self.bubble_btns[key] = b

        def sep():
            s = Gtk.Box()
            s.add_css_class("bsep")
            box.append(s)
        w = self.w
        btn("<b>F</b>", "Fett (Strg+B)", lambda: w.toggle_char("b"), "b", True)
        btn("<i>K</i>", "Kursiv (Strg+I)", lambda: w.toggle_char("i"), "i", True)
        btn("<u>U</u>", "Unterstrichen (Strg+U)", lambda: w.toggle_char("u"), "u", True)
        btn("<s>S</s>", "Durchgestrichen (Strg+D)", lambda: w.toggle_char("s"), "s", True)
        sep()
        for st, lab in (("h1", "H1"), ("h2", "H2"), ("h3", "H3")):
            btn(lab, f"Überschrift {lab[1]}", lambda st=st: w.edit_paras(
                lambda a: a.update(style="normal" if a["style"] == st else st, list=None)), "ps:" + st)
        btn("󰝗", "Zitat", lambda: w.edit_paras(lambda a: a.update(style="normal" if a["style"] == "quote" else "quote")),
            "ps:quote")
        btn("󰅩", "Code", lambda: w.edit_paras(lambda a: a.update(style="normal" if a["style"] == "code" else "code")),
            "ps:code")
        sep()
        btn("󰌷", "Link (Strg+K)", lambda: w.open_link())
        btn("󰉹", "Aufzählung", lambda: w.toggle_list("bullet"))
        pop.set_child(box)
        pop.set_parent(w.view)
        self.bubble = pop

    def sync_bubble(self):
        w = self.w
        if not self.bubble.get_visible():
            return False
        ch = w.char_at_cursor() if hasattr(w, "char_at_cursor") else {}
        a = w.para_at(w.buf.get_iter_at_mark(w.buf.get_insert()).get_line())
        for key, b in self.bubble_btns.items():
            on = (a["style"] == key[3:]) if key.startswith("ps:") else bool(ch.get(key))
            (b.add_css_class if on else b.remove_css_class)("on")
        return False

    def on_mark(self, buf, it, mark):
        if not self.w.flow or mark is not buf.get_insert() and mark is not buf.get_selection_bound():
            return
        if self._bubble_id is None:
            self._bubble_id = GLib.timeout_add(180, self.update_bubble)
        if self.slash_mark is not None:
            # Cursor hat die „/“-Zeile verlassen oder steht vor dem „/“ → Menü zu
            a = buf.get_iter_at_mark(self.slash_mark)
            c = buf.get_iter_at_mark(buf.get_insert())
            if c.get_line() != a.get_line() or c.compare(a) <= 0:
                self.close_slash()
        elif self.slash_line is not None and buf.get_iter_at_mark(buf.get_insert()).get_line() != self.slash_line:
            self.close_slash()
        self.w.view.queue_draw()

    def on_scroll(self, adj):
        """Markierungs-Leiste und Blockmenü bleiben beim Scrollen am Text hängen (statt am Bildschirm)."""
        if self._scroll_id is None and (self.bubble.get_visible() or self.slash.get_visible() or
                                        (self.w.flow and self.w.buf.get_has_selection())):
            self._scroll_id = GLib.idle_add(self._follow_scroll)

    def _follow_scroll(self):
        self._scroll_id = None
        if self.bubble.get_visible() or self.w.buf.get_has_selection():
            self.update_bubble()
        if self.slash.get_visible() and (self.slash_mark is not None or self.slash_line is not None):
            self.place(self.slash)
        return False

    def update_bubble(self):
        self._bubble_id = None
        w = self.w
        show = w.flow and w.editable and w.buf.get_has_selection() and w.view.has_focus()
        if show:                                  # Markierungsanfang muss sichtbar sein, sonst keine Leiste
            s, _e = w.buf.get_selection_bounds()
            r = w.view.get_iter_location(s)
            _, y = w.view.buffer_to_window_coords(Gtk.TextWindowType.WIDGET, r.x, r.y)
            show = 0 <= y <= w.view.get_height() - 10
        if show:
            self.place(self.bubble, sel=True)
            if not self.bubble.get_visible():
                self.bubble.popup()
            self.sync_bubble()
        elif self.bubble.get_visible():
            self.bubble.popdown()
        return False

    def on_changed(self):
        # Markierung gelöscht/überschrieben: GTK meldet dabei kein mark-set → Leiste hier schließen
        if getattr(self, "bubble", None) is not None and self.bubble.get_visible() and not self.w.buf.get_has_selection():
            self.bubble.popdown()
        if self.slash_mark is None:
            return
        q = self.query()
        if q is None or "\n" in q or len(q) > 24 or (q.endswith(" ") and not self.items):
            self.close_slash()
            return
        self.cur = 0
        self.fill()
        self.place(self.slash)

    # ================= Tasten =================
    def on_key(self, keyval, state):
        if not self.is_open():
            if keyval == Gdk.KEY_Escape and self.bubble.get_visible():
                self.bubble.popdown()
                return True
            return False
        if keyval in (Gdk.KEY_Down, Gdk.KEY_KP_Down):
            self.move(1)
            return True
        if keyval in (Gdk.KEY_Up, Gdk.KEY_KP_Up):
            self.move(-1)
            return True
        if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter, Gdk.KEY_Tab):
            if self.items:
                self.choose(self.items[self.cur][0])
            else:
                self.close_slash()
            return True
        if keyval == Gdk.KEY_Escape:
            self.close_slash()
            return True
        return False

    def leave(self):
        """Ansicht gewechselt oder anderes Dokument: alles Schwebende zu."""
        self.close_slash()
        if self.bubble.get_visible():
            self.bubble.popdown()
        self.hover_line = None


def today():
    return datetime.date.today()
