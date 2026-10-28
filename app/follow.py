# Mitscrollen beim Schreiben (Notizen, Words, LaTeX): Sobald sich der Text ändert – auch direkt nach Enter, nicht
# erst beim nächsten Zeichen –, rückt die Ansicht so nach, dass der Cursor höchstens bei ~60 % der Höhe steht.
# Damit das auch am Textende geht, bekommt die Ansicht unten eine halbe Seite Luft (set_extra).
import time

from gi.repository import GLib, Gtk

LINE = 0.6          # Cursor nicht tiefer als 60 % der sichtbaren Höhe


class Follow:
    def __init__(self, view, enabled, set_extra):
        """view: Gtk.TextView (scrollbar über seinen ScrolledWindow), enabled(): an/aus,
        set_extra(px): zusätzlichen Platz unter dem Text setzen."""
        self.view, self.enabled, self.set_extra = view, enabled, set_extra
        self._id = None
        self._extra = None
        self._buf_ids = []
        view.connect("notify::buffer", lambda *_: self._watch())
        self._watch()
        view.connect("map", lambda *_: self.update_extra())

    def _watch(self):
        buf = self.view.get_buffer()
        if getattr(self, "_buf", None) is buf:
            return
        self._buf = buf
        buf.connect_after("changed", lambda *_: self.queue())

    def queue(self):
        if time.monotonic() < getattr(self.view, "_no_follow_until", 0):     # Rückgängig & Co. setzen die Ansicht selbst
            return
        if self._id is None and self.enabled() and self.view.has_focus():
            self._id = GLib.idle_add(self._run)

    def update_extra(self):
        """Platz unter dem Text: halbe sichtbare Höhe (aus: keiner)."""
        h = self._height()
        px = int(h * 0.5) if (self.enabled() and h > 0) else 0
        if px != self._extra:
            self._extra = px
            self.set_extra(px)

    def _height(self):
        sc = self.view.get_ancestor(Gtk.ScrolledWindow)
        return sc.get_height() if sc is not None else self.view.get_height()

    def _run(self):
        self._id = None
        self.update_extra()
        sc = self.view.get_ancestor(Gtk.ScrolledWindow)
        if sc is None:
            return False
        adj = sc.get_vadjustment()
        buf = self.view.get_buffer()
        rect = self.view.get_iter_location(buf.get_iter_at_mark(buf.get_insert()))
        # Puffer- → Fensterkoordinaten (Fenster = sichtbarer Ausschnitt)
        _, wy = self.view.buffer_to_window_coords(Gtk.TextWindowType.WIDGET, rect.x, rect.y)
        h = sc.get_height()
        if h <= 0:
            return False
        limit = h * LINE
        bottom = wy + rect.height
        if bottom > limit:
            adj.set_value(min(adj.get_value() + bottom - limit, adj.get_upper() - adj.get_page_size()))
        elif wy < 0:
            adj.set_value(max(0, adj.get_value() + wy - 8))
        return False
