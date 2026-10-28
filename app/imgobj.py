# Bilder in Words: Größe an den Ecken ziehen und schwebende Bilder (vor/hinter dem Text).
# Ein schwebendes Bild ist im Text ein 1 px großer, unsichtbarer Platzhalter (Anker); das Bild selbst wird in den
# Schichten des Textfelds gezeichnet (hinter bzw. vor dem Text). Im Dokument steht es als Bild-Lauf mit
# "fl": "front"|"back", "dx"/"dy" (Versatz zum Anker in Pixeln bei 100 %).
import base64

import gi

gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gdk, GdkPixbuf, GLib, Graphene, Gtk  # noqa: E402

MIN_PX = 16
HANDLE = 5
CURSORS = {"nw": "nwse-resize", "se": "nwse-resize", "ne": "nesw-resize", "sw": "nesw-resize"}


def fl_of(info):
    """Schwebe-Angaben (fl, dx, dy) eines Bild-Laufs oder None."""
    if info and info.get("fl") in ("front", "back"):
        return {"fl": info["fl"], "dx": info.get("dx", 0), "dy": info.get("dy", 0)}
    return None


def placeholder():
    pb = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, True, 8, 1, 1)
    pb.fill(0)
    return Gdk.Texture.new_for_pixbuf(pb)


class ImageObjects:
    def imgobj_init(self):
        self.float_tex = {}              # Platzhalter-Textur → {"mark": TextMark am Anker, "tex": Textur in Anzeigegröße}
        self._sel = None                 # ("f", Platzhalter) | ("i", Offset) – Bild mit Ziehgriffen
        self._idrag = None
        self._img_cur = None
        drag = Gtk.GestureDrag(button=1)
        drag.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        drag.connect("drag-begin", self.img_drag_begin)
        drag.connect("drag-update", self.img_drag_update)
        drag.connect("drag-end", self.img_drag_end)
        self.view.add_controller(drag)
        mo = Gtk.EventControllerMotion()
        mo.connect("motion", self.img_motion)
        self.view.add_controller(mo)
        self.buf.connect_after("notify::cursor-position", self._img_cursor_moved)

    # ---------- Geometrie ----------
    def pxk(self):
        return self.zoom * self.geo["scale"]

    def float_rect(self, ph):
        d, info = self.float_tex.get(ph), self.images.get(ph)
        if not d or not info:
            return None
        it = self.buf.get_iter_at_mark(d["mark"])
        if it.get_paintable() is not ph:
            return None
        r = self.view.get_iter_location(it)
        ly, _lh = self.view.get_line_yrange(it)
        k = self.pxk()
        return (r.x + info.get("dx", 0) * k, ly + info.get("dy", 0) * k, info["w"] * k, info["h"] * k)

    def sel_rect(self):
        s = self._sel
        if not s:
            return None
        if s[0] == "f":
            return self.float_rect(s[1])
        it = self.buf.get_iter_at_offset(s[1])
        if it.get_paintable() not in self.images:
            return None
        r = self.view.get_iter_location(it)
        return (r.x, r.y, r.width, r.height)

    @staticmethod
    def corner_at(bx, by, rect):
        x, y, w, h = rect
        for c, (cx, cy) in {"nw": (x, y), "ne": (x + w, y), "sw": (x, y + h), "se": (x + w, y + h)}.items():
            if abs(bx - cx) <= HANDLE + 3 and abs(by - cy) <= HANDLE + 3:
                return c
        return None

    def text_at(self, bx, by):
        """Liegt an der Stelle ein sichtbares Zeichen? (Hinter dem Text liegende Bilder lassen sich nur daneben anfassen.)"""
        ok, it, _tr = self.view.get_iter_at_position(bx, by)
        if not ok:
            return False
        r = self.view.get_iter_location(it)
        ch = it.get_char()
        return bool(ch.strip()) and ch != "￼" and r.x <= bx <= r.x + r.width and r.y <= by <= r.y + r.height

    def float_at(self, bx, by):
        phs = list(self.float_tex)
        order = [p for p in reversed(phs) if self.images.get(p, {}).get("fl") == "front"] + \
                [p for p in reversed(phs) if self.images.get(p, {}).get("fl") == "back"]
        for ph in order:
            r = self.float_rect(ph)
            if r and r[0] <= bx <= r[0] + r[2] and r[1] <= by <= r[1] + r[3]:
                if self.images[ph]["fl"] == "back" and self.text_at(bx, by):
                    continue
                return ph
        return None

    # ---------- Zeichnen ----------
    def draw_floats(self, snap, z):
        if not self.float_tex:
            return
        dead = []
        for ph, d in list(self.float_tex.items()):
            info = self.images.get(ph)
            if info is None:
                dead.append(ph)
                continue
            if info.get("fl") != z:
                continue
            r = self.float_rect(ph)
            if r is None:
                dead.append(ph)
                continue
            snap.append_texture(d["tex"], Graphene.Rect().init(*r))
        if dead:
            GLib.idle_add(lambda: ([self.drop_float(p) for p in dead], False)[1])

    def draw_img_sel(self, snap):
        rect = self.sel_rect()
        if not rect:
            return
        x, y, w, h = rect
        d = self._idrag
        if d and d["kind"] == "resize" and d.get("pw") and self._sel[0] == "i":
            w, h = d["pw"] * self.pxk(), d["ph"] * self.pxk()
        col = self.link_rgba
        t = 1.5
        for rx, ry, rw, rh in ((x, y, w, t), (x, y + h - t, w, t), (x, y, t, h), (x + w - t, y, t, h)):
            snap.append_color(col, Graphene.Rect().init(rx, ry, rw, rh))
        for cx, cy in ((x, y), (x + w, y), (x, y + h), (x + w, y + h)):
            snap.append_color(Gdk.RGBA(red=1, green=1, blue=1, alpha=1),
                              Graphene.Rect().init(cx - HANDLE - 1, cy - HANDLE - 1, 2 * HANDLE + 2, 2 * HANDLE + 2))
            snap.append_color(col, Graphene.Rect().init(cx - HANDLE, cy - HANDLE, 2 * HANDLE, 2 * HANDLE))

    # ---------- Schwebende Bilder verwalten ----------
    def add_float(self, ph, tex, off):
        mark = self.buf.create_mark(None, self.buf.get_iter_at_offset(off), False)   # rechte Schwerkraft: bleibt am Anker
        self.float_tex[ph] = {"mark": mark, "tex": tex}

    def drop_float(self, ph):
        d = self.float_tex.pop(ph, None)
        if d:
            try:
                self.buf.delete_mark(d["mark"])
            except Exception:  # noqa: BLE001
                pass
        if self._sel and self._sel[0] == "f" and self._sel[1] is ph:
            self._sel = None
        self.view.queue_draw()

    def clear_floats(self):
        for ph in list(self.float_tex):
            self.drop_float(ph)
        self._sel = None

    def float_refresh(self, ph):
        """Textur in der Größe nachziehen, die das Bild jetzt hat (nach dem Ändern der Größe)."""
        import writer as wr
        info = self.images[ph]
        k = self.pxk()
        self.float_tex[ph]["tex"] = wr.pixel_texture(base64.b64decode(info["img"]), info["w"] * k, info["h"] * k)

    # ---------- Auswahl ----------
    def img_deselect(self):
        if self._sel:
            self._sel = None
            self.view.queue_draw()
        pop = getattr(self, "img_pop", None)
        if pop:
            pop.popdown()

    def _img_scrolled(self, *_):
        """Beim Scrollen bliebe das Menü an der alten Stelle hängen: ausblenden (die Griffe wandern mit dem Bild)."""
        pop = getattr(self, "img_pop", None)
        if pop and pop.get_visible() and not self._idrag:
            pop.popdown()

    def _img_cursor_moved(self, *_):
        s = self._sel
        if s and s[0] == "i":
            pos = self.cursor_offset()
            if not (s[1] <= pos <= s[1] + 1) and not (self._idrag and self._idrag["kind"] == "resize"):
                self.img_deselect()

    # ---------- Maus ----------
    def img_motion(self, ctrl, x, y):
        name = None
        if self.editable and (self._sel or self.float_tex):
            bx, by = self.view.window_to_buffer_coords(Gtk.TextWindowType.WIDGET, int(x), int(y))
            rect = self.sel_rect()
            c = self.corner_at(bx, by, rect) if rect else None
            if c:
                name = CURSORS[c]
            elif self.float_at(bx, by) is not None:
                name = "move"
        if name != self._img_cur:
            self._img_cur = name
            self.view.set_cursor_from_name(name)

    def img_drag_begin(self, g, x, y):
        ev = g.get_last_event(None)
        native = self.view.get_native()
        if ev is not None and native is not None and ev.get_surface() is not native.get_surface():
            g.set_state(Gtk.EventSequenceState.DENIED)        # Klick im Bild-Menü (eigenes Fenster), nicht im Text
            return
        if not self.editable or self._idrag:
            g.set_state(Gtk.EventSequenceState.DENIED)
            return
        bx, by = self.view.window_to_buffer_coords(Gtk.TextWindowType.WIDGET, int(x), int(y))
        rect = self.sel_rect()
        c = self.corner_at(bx, by, rect) if rect else None
        if c:
            info = self.images.get(self._sel[1]) if self._sel[0] == "f" else \
                self.images.get(self.buf.get_iter_at_offset(self._sel[1]).get_paintable())
            if info:
                self._idrag = dict(kind="resize", corner=c, w0=info["w"], h0=info["h"], dx0=info.get("dx", 0),
                                   dy0=info.get("dy", 0), moved=False, sel=self._sel)
                g.set_state(Gtk.EventSequenceState.CLAIMED)
                return
        ph = self.float_at(bx, by)
        if ph is not None:
            info = self.images[ph]
            self._sel = ("f", ph)
            self._idrag = dict(kind="move", ph=ph, dx0=info.get("dx", 0), dy0=info.get("dy", 0), moved=False,
                               sel=self._sel)
            self.buf.place_cursor(self.buf.get_iter_at_mark(self.float_tex[ph]["mark"]))
            self._sel = ("f", ph)
            self.view.queue_draw()
            g.set_state(Gtk.EventSequenceState.CLAIMED)
            return
        pop = getattr(self, "img_pop", None)
        if self._sel or (pop and pop.get_visible()):          # Klick daneben: Menü und Griffe weg
            self.img_deselect()                               # (ein Klick auf ein Inline-Bild öffnet es danach neu)
        g.set_state(Gtk.EventSequenceState.DENIED)

    def _drag_info(self, d):
        s = d["sel"]
        if s[0] == "f":
            return self.images.get(s[1])
        return self.images.get(self.buf.get_iter_at_offset(s[1]).get_paintable())

    def img_drag_update(self, g, ox, oy):
        d = self._idrag
        if not d:
            return
        if not d["moved"]:
            if abs(ox) + abs(oy) < 4:
                return
            d["moved"] = True
            pop = getattr(self, "img_pop", None)
            if pop:
                pop.popdown()
            if d["sel"][0] == "f":
                self.checkpoint()
        info = self._drag_info(d)
        if not info:
            return
        k = self.pxk()
        if d["kind"] == "move":
            info["dx"], info["dy"] = d["dx0"] + ox / k, d["dy0"] + oy / k
        else:
            c, w0, h0 = d["corner"], d["w0"], d["h0"]
            sx, sy = (1 if "e" in c else -1), (1 if "s" in c else -1)
            s = 1 + (sx * ox / k / w0 + sy * oy / k / h0) / 2
            nw = min(4000, max(MIN_PX, w0 * s))
            nh = h0 * nw / w0
            if d["sel"][0] == "f":
                info["w"], info["h"] = nw, nh
                info["dx"] = d["dx0"] + (w0 - nw if "w" in c else 0)
                info["dy"] = d["dy0"] + (h0 - nh if "n" in c else 0)
            else:
                d["pw"], d["ph"] = nw, nh
        self.view.queue_draw()

    def img_drag_end(self, g, ox, oy):
        d, self._idrag = self._idrag, None
        if not d:
            return
        if d["sel"][0] == "f":
            ph = d["sel"][1]
            if ph not in self.float_tex:
                return
            if d["moved"]:
                info = self.images[ph]
                info["w"], info["h"] = round(info["w"]), round(info["h"])
                self.float_refresh(ph)
                self.changed()
            self.show_image_pop(self.buf.get_iter_at_mark(self.float_tex[ph]["mark"]))
        elif d["moved"] and d.get("pw"):
            off = d["sel"][1]
            if self.reinsert_image(off, round(d["pw"]), round(d["ph"])):
                self._sel = ("i", off)
                self.show_image_pop(self.buf.get_iter_at_offset(off))
        self.view.queue_draw()

    # ---------- Bild ändern ----------
    def reinsert_image(self, off, w=None, h=None, fl="keep"):
        """Das Bild-Zeichen an Offset off durch eines mit anderer Größe/Schwebe-Art ersetzen (ein Rückgängig-Schritt)."""
        it = self.buf.get_iter_at_offset(off)
        tex = it.get_paintable()
        info = self.images.get(tex)
        if not info:
            return False
        self.checkpoint()
        self._quiet += 1
        names = self.names(it)
        e = it.copy()
        e.forward_char()
        self.images.pop(tex)
        self.drop_float(tex)
        self.buf.delete(it, e)
        pos = self.buf.get_iter_at_offset(off)
        self._loading = True
        self.insert_image_data(base64.b64decode(info["img"]), info["mime"], w or info["w"], h or info["h"], pos,
                               b64=info["img"], fl=fl_of(info) if fl == "keep" else fl)
        s, e = self.buf.get_iter_at_offset(off), self.buf.get_iter_at_offset(off + 1)
        for n in names:
            self.buf.apply_tag(self.tag(n) if not n.startswith(("zoom",)) else self.zoom_tag, s, e)
        self._loading = False
        self._quiet -= 1
        self.changed()
        return True

    def float_align(self, ph, where):
        """Schwebendes Bild links/mittig/rechts im Textbereich ausrichten."""
        r, g, k = self.float_rect(ph), self.geo, self.pxk()
        if not r:
            return
        info = self.images[ph]
        left = g["side"] + g["ml"]
        target = {"left": left, "center": left + (g["text_w"] - r[2]) / 2, "right": left + g["text_w"] - r[2]}[where]
        self.checkpoint()
        info["dx"] = info.get("dx", 0) + (target - r[0]) / k
        self.changed()
        self.view.queue_draw()

    def float_resize(self, ph, w, h):
        self.checkpoint()
        info = self.images[ph]
        info["w"], info["h"] = round(w), round(h)
        self.float_refresh(ph)
        self.changed()
        self.view.queue_draw()
