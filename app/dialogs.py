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
