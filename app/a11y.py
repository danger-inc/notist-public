# Barrierefreiheit: Knöpfe, die nur ein Symbol zeigen (Nerd-Font-Zeichen), bekommen ihren Tooltip als Beschriftung für
# Screenreader (Orca). Läuft einmal über den Widget-Baum; neue Fenster/Popover rufen label_tree() für sich auf.
from gi.repository import Gtk

KINDS = (Gtk.Button, Gtk.ToggleButton, Gtk.MenuButton, Gtk.Scale, Gtk.Switch, Gtk.SpinButton, Gtk.DropDown,
         Gtk.CheckButton, Gtk.Entry, Gtk.SearchEntry, Gtk.Scrollbar)


def _icon_only(text):
    return not text or all(0xE000 <= ord(c) <= 0xF8FF or ord(c) >= 0xF0000 or c.isspace() for c in text)


def label_tree(root, depth=0):
    if root is None or depth > 40:
        return 0
    n = 0
    if isinstance(root, KINDS):
        tip = root.get_tooltip_text()
        text = ""
        if isinstance(root, (Gtk.Button, Gtk.CheckButton)):
            text = root.get_label() or ""
        if tip and _icon_only(text):
            root.update_property([Gtk.AccessibleProperty.LABEL], [tip])
            n += 1
    child = root.get_first_child()
    while child is not None:
        n += label_tree(child, depth + 1)
        child = child.get_next_sibling()
    return n
