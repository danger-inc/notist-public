# Kleiner Monatskalender im datist-Look (für Erinnerungen): Kasten mit Monat im Rahmen, KW-Spalte mit
# gerader/ungerader Woche (g/u wie in datist), Wochenende gedämpft, heute gefüllt, gewählter Tag umrandet.
# Tage außerhalb des Monats blass; ‹ › blättern, Mausrad auch.
import calendar
import datetime as dt

from gi.repository import Gtk

import chrome as ch
import i18n

MONTHS = ("januar", "februar", "märz", "april", "mai", "juni", "juli", "august", "september", "oktober",
          "november", "dezember")
DAYS = ("mo", "di", "mi", "do", "fr", "sa", "so")

CSS = """
.mc .tpbody { padding: 2px 6px 6px 6px; }
.mc-nav { margin: 0 0 2px 0; }
.mc-nav button.tflat { font-size: 14px; padding: 0 8px; }
.mc-month { font-size: 12px; font-weight: bold; color: @foreground; }
.mc-head { font-size: 11px; font-weight: bold; color: alpha(@foreground, 0.85); }
.mc-head.we { color: alpha(@foreground, 0.5); }
.mc-kw { font-size: 11px; font-weight: bold; color: @primary; padding: 0 4px 0 0; }
.mc-kw.odd { color: @tertiary; }
.mc-kw.even { background-color: alpha(@primary, 0.06); border-radius: 3px; }
button.mc-day { background: none; background-image: none; box-shadow: none; border: 1px solid transparent;
    border-radius: 4px; min-height: 0; min-width: 0; padding: 2px 0; font-size: 12px; font-weight: bold;
    color: @foreground; outline: none; }
button.mc-day:hover { border-color: alpha(@primary, 0.6); background-color: alpha(@primary, 0.1); }
button.mc-day.we { color: alpha(@foreground, 0.6); }
button.mc-day.other { color: alpha(@foreground, 0.32); }
button.mc-day.past { color: alpha(@foreground, 0.32); }
button.mc-day.sel { background-color: alpha(@primary, 0.18); border-color: @primary; }
button.mc-day.today { background-color: @primary; color: @on_primary; }
button.mc-day.today.sel { box-shadow: inset 0 0 0 1px @on_primary; }
"""


class MiniCal(Gtk.Box):
    def __init__(self, on_select=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.add_css_class("mc")
        self.on_select = on_select
        self.sel = dt.date.today()
        self.month = self.sel.replace(day=1)
        self.panel = ch.Panel()
        self.append(self.panel)
        nav = Gtk.Box(spacing=2)
        nav.add_css_class("mc-nav")
        prev = Gtk.Button(label="‹", focus_on_click=False, tooltip_text="Voriger Monat")
        prev.add_css_class("tflat")
        prev.connect("clicked", lambda *_: self.flip(-1))
        nxt = Gtk.Button(label="›", focus_on_click=False, tooltip_text="Nächster Monat")
        nxt.add_css_class("tflat")
        nxt.connect("clicked", lambda *_: self.flip(1))
        self.month_lbl = ch.label("", "mc-month", xalign=0.5, hexpand=True)
        today = Gtk.Button(label="heute", focus_on_click=False, tooltip_text="Zum heutigen Tag")
        today.add_css_class("tflat")
        today.connect("clicked", lambda *_: self.select(dt.date.today(), notify=True))
        nav.append(prev)
        nav.append(self.month_lbl)
        nav.append(today)
        nav.append(nxt)
        self.panel.body.append(nav)
        self.grid = Gtk.Grid(column_spacing=2, row_spacing=2, column_homogeneous=False)
        self.panel.body.append(self.grid)
        scroll = Gtk.EventControllerScroll(flags=Gtk.EventControllerScrollFlags.VERTICAL |
                                           Gtk.EventControllerScrollFlags.DISCRETE)
        scroll.connect("scroll", lambda c, dx, dy: (self.flip(1 if dy > 0 else -1), True)[1])
        self.add_controller(scroll)
        self.render()

    def get_date(self):
        return self.sel

    def select(self, day, notify=False):
        self.sel = day
        self.month = day.replace(day=1)
        self.render()
        if notify and self.on_select:
            self.on_select(day)

    def flip(self, d):
        m = self.month.month - 1 + d
        self.month = dt.date(self.month.year + m // 12, m % 12 + 1, 1)
        self.render()

    def render(self):
        g = self.grid
        while (c := g.get_first_child()):
            g.remove(c)
        first = self.month
        start = first - dt.timedelta(days=first.weekday())
        last_day = first.replace(day=calendar.monthrange(first.year, first.month)[1])
        weeks = ((last_day - start).days // 7) + 1
        end_kw = (start + dt.timedelta(days=7 * weeks - 1)).isocalendar()[1]
        self.panel.set_title(f"{ch.esc(i18n.tr(MONTHS[first.month - 1]))} {first.year}"
                             f"<span alpha='55%'> · kw {start.isocalendar()[1]}–{end_kw}</span>")
        g.attach(ch.label("kw", "mc-head", xalign=0), 0, 0, 1, 1)
        for i, d in enumerate(DAYS):
            lab = ch.label(i18n.tr(d), "mc-head", xalign=0.5, hexpand=True)
            if i >= 5:
                lab.add_css_class("we")
            g.attach(lab, i + 1, 0, 1, 1)
        today = dt.date.today()
        for w in range(weeks):
            d0 = start + dt.timedelta(days=7 * w)
            kw = d0.isocalendar()[1]
            even = kw % 2 == 0
            kl = ch.label(f"{kw:>2}{'g' if even else 'u'}", "mc-kw", "even" if even else "odd", xalign=0)
            kl.set_tooltip_text(f"KW {kw} – {'gerade' if even else 'ungerade'} Woche")
            g.attach(kl, 0, w + 1, 1, 1)
            for i in range(7):
                d = d0 + dt.timedelta(days=i)
                b = Gtk.Button(label=str(d.day), focus_on_click=False, hexpand=True)
                b.add_css_class("mc-day")
                if d.month != first.month:
                    b.add_css_class("other")
                elif d < today:
                    b.add_css_class("past")
                elif i >= 5:
                    b.add_css_class("we")
                if d == today:
                    b.add_css_class("today")
                if d == self.sel:
                    b.add_css_class("sel")
                b.connect("clicked", lambda _b, d=d: self.select(d, notify=True))
                g.attach(b, i + 1, w + 1, 1, 1)
