# LaTeX-Pakete verwalten: suchen, vorab laden (offline nutzbar), Speicherordner öffnen, Befehle daraus übernehmen.
import os
import threading

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, Gio, GLib, Gtk, Pango

import dialogs
import pkgcmds as pc


class PackageManager(Gtk.Window):
    """find_tectonic() → Pfad oder None · doc_text() → Quelltext des offenen Dokuments · on_changed() nach neuen Befehlen."""
    SHOWN = 250

    def __init__(self, parent, find_tectonic, doc_text, on_changed):
        super().__init__(title="LaTeX-Pakete", transient_for=parent, default_width=780, default_height=660)
        self.add_css_class("settings")
        self.add_css_class("pb-window")
        self.find_tectonic, self.doc_text, self.on_changed = find_tectonic, doc_text, on_changed
        self.busy = {}                                   # Paket → Statustext während es lädt
        k = Gtk.EventControllerKey()
        k.connect("key-pressed", lambda c, kv, *_: kv == Gdk.KEY_Escape and (self.close() or True))
        self.add_controller(k)
        col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, hexpand=True)
        col.add_css_class("settings-page")
        dialogs.chrome(self, self.get_title(), col)

        top = Gtk.Box(spacing=8)
        self.search = Gtk.SearchEntry(placeholder_text="Paket suchen (z. B. lineno, tikz, biblatex)", hexpand=True)
        self.search.add_css_class("pb")
        self.search.connect("search-changed", lambda *_: self.fill())
        top.append(self.search)
        self.filters = {}
        first = None
        for key, label in (("all", "alle"), ("cached", "geladen"), ("doc", "im dokument")):
            b = Gtk.ToggleButton(label=label, focus_on_click=False)
            b.add_css_class("pb"); b.add_css_class("small")
            if first:
                b.set_group(first)
            else:
                first = b
                b.set_active(True)
            b.connect("toggled", lambda w, k=key: w.get_active() and self.set_filter(k))
            self.filters[key] = b
            top.append(b)
        self.mode = "all"
        col.append(top)

        bar = Gtk.Box(spacing=8)
        self.info = Gtk.Label(xalign=0, hexpand=True)
        self.info.add_css_class("set-sub")
        bar.append(self.info)
        for icon, text, tip, cb in (
                ("󰉋", "speicherordner öffnen", "Hier legt Tectonic geladene Pakete ab", self.open_folder),
                ("󰍉", "nach befehlen suchen", "Befehle aller geladenen und im Dokument benutzten Pakete einlesen",
                 self.scan_all)):
            b = Gtk.Button(label=f"{icon}  {text}", tooltip_text=tip, focus_on_click=False)
            b.add_css_class("pb"); b.add_css_class("small")
            b.connect("clicked", lambda *_, f=cb: f())
            bar.append(b)
        col.append(bar)

        sc = Gtk.ScrolledWindow(vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER)
        self.list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        self.list.add_css_class("cmd-list")
        sc.set_child(self.list)
        col.append(sc)
        self.hint = Gtk.Label(xalign=0, wrap=True)
        self.hint.add_css_class("set-sub")
        col.append(self.hint)
        self.refresh()
        GLib.idle_add(lambda: self.search.grab_focus() and False)

    # ---------------------------------------------------------------- Daten
    def refresh(self):
        self.avail = pc.available()
        self.have = pc.cached()
        self.scanned = pc.scanned()
        self.used = set(pc.used_packages(self.doc_text() or ""))
        n = sum(1 for f in self.have if f.endswith((".sty", ".cls")))
        self.info.set_label(f"{n} Dateien offline · {pc.human(pc.cache_size())} · {len(self.scanned)} Pakete mit Befehlen")
        if not self.avail:
            self.hint.set_label("Noch keine Paketliste: sie erscheint nach dem ersten Kompilieren (Tectonic lädt sie "
                                "beim ersten Mal herunter).")
        else:
            self.hint.set_label("„laden“ holt das Paket samt Abhängigkeiten, danach funktioniert es auch ohne Internet. "
                                "Die Befehle des Pakets erscheinen automatisch in den Vorschlägen.")
        self.fill()

    def set_filter(self, key):
        self.mode = key
        self.fill()

    def names(self):
        """{paketname: größe} – ohne Klassen-Doppelungen."""
        out = {}
        for f, size in self.avail.items():
            out.setdefault(os.path.splitext(f)[0], size)
        for f in self.have:
            if f.endswith((".sty", ".cls")):
                out.setdefault(os.path.splitext(f)[0], 0)
        for p in self.used:
            out.setdefault(p, 0)
        return out

    def fill(self):
        lst = self.list
        while (c := lst.get_first_child()):
            lst.remove(c)
        q = self.search.get_text().strip().lower()
        names = self.names()
        rows = []
        for name in sorted(names, key=lambda n: (n not in self.used, n.lower())):
            cached = name + ".sty" in self.have or name + ".cls" in self.have
            if self.mode == "cached" and not cached:
                continue
            if self.mode == "doc" and name not in self.used:
                continue
            if q and q not in name.lower():
                continue
            rows.append((name, cached, names[name]))
        for name, cached, size in rows[:self.SHOWN]:
            lst.append(self.row(name, cached, size))
        if len(rows) > self.SHOWN:
            l = Gtk.Label(label=f"… und {len(rows) - self.SHOWN} weitere – oben weiter eingrenzen.", xalign=0)
            l.add_css_class("set-sub")
            lst.append(l)
        if not rows:
            l = Gtk.Label(label="Kein Paket gefunden.", xalign=0)
            l.add_css_class("set-sub")
            lst.append(l)

    def row(self, name, cached, size):
        r = Gtk.ListBoxRow(activatable=False)
        r.pkg = name
        g = Gtk.Box(spacing=12)
        n = Gtk.Label(label=name, xalign=0)
        n.add_css_class("cmd-name")
        n.set_size_request(200, -1)
        n.set_ellipsize(Pango.EllipsizeMode.END)
        g.append(n)
        state = self.busy.get(name)
        if state:
            txt = state
        else:
            bits = []
            if name in self.used:
                bits.append("im dokument")
            bits.append("offline ✓" if cached else "online")
            if name in self.scanned:
                bits.append("befehle ✓")
            if size:
                bits.append(pc.human(size))
            txt = " · ".join(bits)
        d = Gtk.Label(label=txt, xalign=0, hexpand=True, ellipsize=Pango.EllipsizeMode.END)
        d.add_css_class("cmd-desc")
        g.append(d)
        if not state:
            if not cached:
                b = Gtk.Button(label="󰇚 laden", focus_on_click=False, tooltip_text="Paket herunterladen")
                b.connect("clicked", lambda *_, p=name: self.load(p))
            elif name not in self.scanned:
                b = Gtk.Button(label="󰍉 befehle", focus_on_click=False, tooltip_text="Befehle dieses Pakets einlesen")
                b.connect("clicked", lambda *_, p=name: self.scan([p]))
            else:
                b = None
            if b:
                b.add_css_class("pb"); b.add_css_class("small")
                g.append(b)
        r.set_child(g)
        return r

    # ---------------------------------------------------------------- Aktionen
    def tectonic(self):
        exe = self.find_tectonic()
        if not exe:
            self.hint.set_label("Tectonic ist nicht eingerichtet – das geht im LaTeX-Bereich unter „Einrichtung“.")
        return exe

    def set_busy(self, pkg, text):
        if text is None:
            self.busy.pop(pkg, None)
        else:
            self.busy[pkg] = text
        self.fill()

    def load(self, pkg):
        exe = self.tectonic()
        if not exe or pkg in self.busy:
            return
        self.set_busy(pkg, "lädt … (kann bei der ersten Nutzung einige Minuten dauern)")

        def run():
            ok, msg = pc.preload(exe, pkg)
            n = pc.scan_package(exe, pkg) if ok else None
            GLib.idle_add(self.loaded, pkg, ok, msg, n)
        threading.Thread(target=run, daemon=True).start()

    def loaded(self, pkg, ok, msg, n):
        self.busy.pop(pkg, None)
        if ok:
            self.hint.set_label(f"{pkg}: geladen" + (f" · {n} Befehle übernommen" if n else ""))
            self.on_changed()
        else:
            self.hint.set_label(f"{pkg}: {msg}")
        self.refresh()
        return False

    def scan(self, pkgs):
        exe = self.tectonic()
        if not exe or not pkgs:
            return
        for p in pkgs:
            self.busy[p] = "liest Befehle …"
        self.fill()

        def done(pk, cm):
            GLib.idle_add(self.scanned_done, pkgs, pk, cm)
        pc.scan_async(exe, pkgs, done)

    def scanned_done(self, pkgs, pk, cm):
        for p in pkgs:
            self.busy.pop(p, None)
        self.hint.set_label(f"{cm} Befehle aus {pk} Paketen übernommen" if pk else
                            "Konnte die Pakete nicht lesen – erst laden (Internet nötig).")
        self.on_changed()
        self.refresh()
        return False

    def scan_all(self):
        have = {os.path.splitext(f)[0] for f in self.have if f.endswith(".sty")}
        todo = sorted((have | self.used) - self.scanned)
        if not todo:
            self.hint.set_label("Alle bekannten Pakete sind schon eingelesen.")
            return
        self.scan(todo)

    def open_folder(self):
        d = pc.cache_dir()
        os.makedirs(d, exist_ok=True)
        Gio.AppInfo.launch_default_for_uri(Gio.File.new_for_path(d).get_uri(), None)
