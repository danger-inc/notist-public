# Einheitlicher Rahmen für Nebenfenster (Einstellungen, Verlauf, Befehle, Quellen, Tabellen-Editor …):
# eigene Kopfzeile mit Titel, Glas-Schalter und Schließen-Knopf, zum Verschieben anfassbar. Esc schließt ebenfalls.
import os

from gi.repository import Gdk, Gtk

import glass
import i18n

CSS = """
window.dlg { background-color: @background; }
window.dlg.glass:not(.glass-ul) { background-color: alpha(@background, 0.6); backdrop-filter: blur(10px); }
.dlg-head { padding: 10px 14px 6px 14px; }
.dlg-brand { background-color: @primary; color: @on_primary; padding: 1px 9px; border-radius: 4px; font-size: 13px;
    font-weight: bold; margin-right: 8px; }
.dlg-title { font-size: 13px; font-weight: bold; color: @foreground; }
.dlg-head button.pb.glass-toggle { background: none; background-image: none; box-shadow: none; min-height: 0; min-width: 0;
    border: 1px solid alpha(@primary, 0.55); border-radius: 4px; padding: 1px 8px; color: @foreground; font-size: 13px; }
.dlg-head button.pb.glass-toggle:checked { background-color: alpha(@primary, 0.22); }
.dlg-head button.pb.glass-toggle:hover { background-color: @primary; color: @on_primary; border-color: @primary; }
.glass .settings-side { background: none; }
"""


def tiling():
    env = os.environ
    if env.get("HYPRLAND_INSTANCE_SIGNATURE") or env.get("SWAYSOCK") or env.get("NIRI_SOCKET"):
        return True
    desk = env.get("XDG_CURRENT_DESKTOP", "").lower()
    return any(d in desk for d in ("hyprland", "sway", "river", "niri", "wayfire", "i3", "bspwm", "qtile"))


def chrome(win, title, content):
    """Inhalt mit Kopfzeile in das Fenster setzen."""
    win.add_css_class("dlg")
    win.add_css_class("pb-window")
    head = Gtk.Box(spacing=6)
    head.add_css_class("dlg-head")
    brand = Gtk.Label(label="notist", valign=Gtk.Align.CENTER)
    brand.add_css_class("dlg-brand")
    head.append(brand)
    title = i18n.tr(title)                     # erst übersetzen, dann klein (Schlüssel sind groß geschrieben)
    t = Gtk.Label(label=title.lower() if len(title) < 40 else title, xalign=0, hexpand=True, ellipsize=3)
    t.add_css_class("dlg-title")
    head.append(t)
    head.append(glass.GlassToggle(win))
    close = Gtk.Button(label="✕", tooltip_text="Schließen (Esc)", valign=Gtk.Align.CENTER, focus_on_click=False)
    close.add_css_class("tclose")
    close.connect("clicked", lambda *_: win.close())
    head.append(close)
    handle = Gtk.WindowHandle()
    handle.set_child(head)
    if tiling():
        win.set_decorated(False)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.append(handle)
        content.set_vexpand(True)
        box.append(content)
        win.set_child(box)
    else:
        win.set_titlebar(handle)
        win.set_child(content)
    k = Gtk.EventControllerKey()
    k.connect("key-pressed", lambda c, kv, *_: kv == Gdk.KEY_Escape and (win.close() or True))
    win.add_controller(k)
    win.title_label = t
    return win


def choice(parent, title, msg, buttons, on_pick, sub=None):
    """Kleiner Suite-Dialog statt Gtk.AlertDialog. buttons = [(beschriftung, wert, gefährlich)], erster = Abbrechen
    (auch Esc/✕). on_pick(wert) nur bei einem der anderen Knöpfe."""
    win = Gtk.Window(title=i18n.tr(title), transient_for=parent, modal=True, resizable=False, default_width=440)
    win.add_css_class("settings")
    col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, margin_start=16, margin_end=16,
                  margin_top=6, margin_bottom=16)
    if msg:
        col.append(Gtk.Label(label=msg, xalign=0, wrap=True, max_width_chars=50))
    if sub:
        s = Gtk.Label(label=sub, xalign=0, wrap=True, max_width_chars=50)
        s.add_css_class("wpdf-sub")
        col.append(s)
    row = Gtk.Box(spacing=8, halign=Gtk.Align.END, margin_top=6)
    first = None
    for i, (label, value, danger) in enumerate(buttons):
        b = Gtk.Button(label=i18n.tr(label).lower(), focus_on_click=False)
        b.add_css_class("pb"); b.add_css_class("small")
        b.set_cursor_from_name("pointer")
        if danger:
            b.add_css_class("danger")
        b.connect("clicked", lambda _b, i=i, v=value: (win.close(), i and on_pick(v)))
        row.append(b)
        first = first or b
    col.append(row)
    chrome(win, title, col)
    win.present()
    first.grab_focus()
    return win
