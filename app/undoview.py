# Rückgängig/Wiederholen ohne Springen: der Eintrag wird beim Wiederherstellen komplett neu aufgebaut, die Zeilenhöhen
# stehen aber erst nach und nach fest (Seitenumbrüche, Bilder). Deshalb merken wir uns, wo der Cursor im Fenster stand,
# und rücken die Ansicht danach nach, bis das Layout ruhig ist (oder der Nutzer selbst scrollt/tippt).
import time

from gi.repository import GLib


class ScrollAnchor:
    TICK = 60            # ms zwischen den Korrekturen
    CALM = 8             # so viele ruhige Bilder hintereinander = fertig
    MAX = 50             # spätestens nach 3 s aufhören

    def __init__(self, view, scroll):
        self.view, self.scroll = view, scroll
        self._id = 0

    def _cursor_y(self, buf, off=None):
        it = buf.get_iter_at_mark(buf.get_insert()) if off is None else \
            buf.get_iter_at_offset(min(off, buf.get_char_count()))
        return self.view.get_iter_location(it).y

    def capture(self):
        """Cursorhöhe relativ zum Sichtfenster vor dem Wiederherstellen."""
        adj = self.scroll.get_vadjustment()
        return self._cursor_y(self.view.get_buffer()) - adj.get_value(), adj.get_page_size()

    def restore(self, buf, offset, state, done=None):
        """Nach dem Wiederherstellen: Cursor an dieselbe Fensterstelle. War er außerhalb, wird er mit möglichst wenig
        Bewegung ins Bild geholt (nicht in die Mitte gesprungen)."""
        if self._id:
            self.view.remove_tick_callback(self._id)
            self._id = 0
        self.view._no_follow_until = time.monotonic() + 0.6       # Mitscrollen (follow.py) hält still, solange wir zurechtrücken
        rel, page = state
        adj = self.scroll.get_vadjustment()
        margin = 40
        if not 0 <= rel <= page - margin:
            y = self._cursor_y(buf, offset)
            v = adj.get_value()
            rel = y - v if v <= y <= v + page - margin else margin if y < v else page - 2 * margin
        st = [0, 0, None]                   # Bilder, ruhige Bilder in Folge, letzte (Höhe, y)
        t_end = time.monotonic() + 3.0

        def step(widget=None, clock=None):
            st[0] += 1
            y = self._cursor_y(buf, offset)
            key = (round(adj.get_upper()), round(y))
            target = max(0, min(y - rel, adj.get_upper() - adj.get_page_size()))
            if st[1] > 0 and abs(adj.get_value() - target) > 1:
                adj.set_value(target)
            st[1] = st[1] + 1 if key == st[2] else 0
            st[2] = key
            if st[1] == 0:
                return GLib.SOURCE_CONTINUE         # Layout noch geschätzt (y springt): nichts verschieben, erst wenn es zwei Bilder gleich bleibt
            if st[1] == 2 and done:
                done()                              # Layout steht: Standbild weg
            if st[1] >= self.CALM or time.monotonic() > t_end:
                if done:
                    done()
                self._id = 0
                return GLib.SOURCE_REMOVE
            return GLib.SOURCE_CONTINUE
        self._id = self.view.add_tick_callback(step)        # jedes Bild vor dem Zeichnen, nicht erst alle 60 ms
