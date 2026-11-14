# Tabellen-Anhang (XLSX) in Words: Oberfläche (Karte + Vorschau). Der XLSX-Leser steckt seit 5.0 in core/xlsx.py.
import os
import re
import subprocess
import tempfile
import shutil

from core import plat
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gio, GLib, Gtk

import i18n
import pdfblock as pb
from core import paths, xlsx
from core.xlsx import *  # noqa: F401,F403
from core.xlsx import (SHEETS, MAX_ROWS, MAX_COLS, SHOW_ROWS, SHOW_COLS, TABLE_ROWS, ICON, I_OPEN, I_TABLE, I_REFRESH,  # noqa: F401
                       _WB, _M, _R)

CSS = """
.wsheet { background-color: alpha(@foreground, 0.06); border: 1px solid alpha(@foreground, 0.22); border-radius: 8px;
          padding: 10px; font-family: "Noto Sans", sans-serif; }
.wsheet-icon { font-size: 26px; color: @primary; min-width: 54px; }
.wsheet-tabs button { padding: 1px 10px; min-height: 22px; font-size: 9pt; border-radius: 6px; }
.wsheet .wsheet-tabs button { background-image: none; }
.wsheet .wsheet-tabs button:checked { background-color: @primary; color: @on_primary; }
.wsheet-view { border: 1px solid alpha(@foreground, 0.22); border-radius: 4px; }
.wsh-c, .wsh-h { font-size: 9pt; padding: 2px 7px; border-right: 1px solid alpha(@foreground, 0.14);
                 border-bottom: 1px solid alpha(@foreground, 0.14); }
.wsh-h { background-color: alpha(@foreground, 0.1); font-weight: 700; color: alpha(@foreground, 0.7); }
.wsh-c.first { background-color: alpha(@primary, 0.1); font-weight: 700; }
.wsheet-note { opacity: 0.6; font-size: 9pt; }
.light .wsheet { background-color: rgba(0,0,0,0.04); border-color: rgba(0,0,0,0.25); }
.light .wsheet .wpdf-name { color: #1d1d1d; }
"""

def block_of(widget):
    while widget is not None and not isinstance(widget, SheetBlock):
        widget = widget.get_parent()
    return widget


# ====================================================================== Karte
class SheetBlock(Gtk.Box):
    def __init__(self, writer, info):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.writer = writer
        self.info = {"file": info.get("file", ""), "name": info.get("name", "Tabelle.xlsx"),
                     "sheets": int(info.get("sheets") or 1), "cur": int(info.get("cur") or 0),
                     "nrows": int(info.get("nrows") or 0), "ncols": int(info.get("ncols") or 0)}
        self.width = 600
        self.add_css_class("wsheet")
        top = Gtk.Box(spacing=12)
        ic = Gtk.Label(label=ICON, valign=Gtk.Align.START)
        ic.add_css_class("wsheet-icon")
        top.append(ic)
        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, hexpand=True, valign=Gtk.Align.CENTER)
        self.title = Gtk.Label(label=self.info["name"], xalign=0, ellipsize=3)
        self.title.add_css_class("wpdf-name")
        self.sub = Gtk.Label(xalign=0)
        self.sub.add_css_class("wpdf-sub")
        text.append(self.title)
        text.append(self.sub)
        btns = Gtk.Box(spacing=2, margin_top=4)
        btns.add_css_class("wpdf-hdr")
        self.view_btn = pb._tool(pb.I_EYE, "Die Tabelle hier in notist anzeigen", self.toggle)
        btns.append(self.view_btn)
        btns.append(pb._sep())
        btns.append(pb._tool(I_OPEN, "In Gnumeric öffnen und bearbeiten", self.open_ext))
        btns.append(pb._tool(I_TABLE, "Das Blatt als Tabelle ins Dokument einfügen", self.insert_table))
        btns.append(pb._tool(pb.I_SAVE, "Eine Kopie der Tabelle speichern", self.save_as))
        btns.append(pb._tool(pb.I_EDIT, "Tabelle umbenennen", self.rename))
        btns.append(pb._tool(pb.I_TRASH, "Tabelle aus dem Dokument entfernen", self.ask_remove))
        text.append(btns)
        top.append(text)
        self.append(top)

        self.view_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, visible=False)
        self.tabs = Gtk.Box(spacing=4)
        self.tabs.add_css_class("wsheet-tabs")
        self.tab_scroll = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
                                             vscrollbar_policy=Gtk.PolicyType.NEVER, child=self.tabs)
        self.view_col.append(self.tab_scroll)
        self.grid = Gtk.Grid()
        self.scroll = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
                                         vscrollbar_policy=Gtk.PolicyType.AUTOMATIC, propagate_natural_height=True,
                                         max_content_height=340, min_content_height=60, hexpand=True)
        self.scroll.add_css_class("wsheet-view")
        vp = Gtk.Viewport(scroll_to_focus=False)
        vp.set_child(self.grid)
        self.scroll.set_child(vp)
        self.view_col.append(self.scroll)
        self.note = Gtk.Label(xalign=0, wrap=True)
        self.note.add_css_class("wsheet-note")
        self.view_col.append(self.note)
        self.append(self.view_col)
        self._built = None
        fc = Gtk.EventControllerFocus()
        fc.connect("notify::contains-focus", self._focus_changed)
        self.add_controller(fc)
        self.refresh_sub()

    def _focus_changed(self, ctrl, _p):
        view = getattr(self.writer, "view", None)
        if view is None:
            return
        pb._nocaret_css()
        (view.add_css_class if ctrl.get_property("contains-focus") else view.remove_css_class)("wpdf-nocaret")

    def toast(self, msg):
        app = self.writer.win.get_application()
        if app is not None and hasattr(app, "notify"):
            app.notify(msg)

    # --- Modell ---
    def model(self):
        return {"t": "sheet", **self.info}

    def path(self):
        return path_of(self.info["file"])

    def refresh_sub(self):
        n = self.info["sheets"]
        parts = [i18n.tr("%d Blätter") % n if n != 1 else i18n.tr("1 Blatt")]
        if self.info["nrows"]:
            parts.append(i18n.tr("%d Zeilen × %d Spalten") % (self.info["nrows"], self.info["ncols"]))
        try:
            sz = os.path.getsize(self.path())
            parts.append(f"{sz / 1048576:.1f} MB" if sz >= 1048576 else f"{max(1, sz // 1024)} KB")
        except OSError:
            self.sub.set_label(i18n.tr("Datei fehlt im Ordner notist/data/sheets"))
            return
        self.sub.set_label(" · ".join(parts))

    # --- Vorschau ---
    def is_open(self):
        return self.view_col.get_visible()

    def toggle(self):
        show = not self.view_col.get_visible()
        if show:
            self.build(force=True)
        self.view_col.set_visible(show)
        self.view_btn.get_child().set_label(pb.I_EYE_OFF if show else pb.I_EYE)
        self.relayout()

    def relayout(self):
        """Der Text-Editor misst eingebettete Blöcke erst neu, wenn man es ihm sagt (sonst bleibt die Karte zu niedrig)."""
        GLib.timeout_add(60, lambda: (self.writer.invalidate(), False)[1])

    def build(self, force=False):
        wb = workbook(self.path())
        if wb is None:
            self.note.set_label(i18n.tr("Datei fehlt im Ordner notist/data/sheets"))
            return
        cur = max(0, min(self.info["cur"], len(wb.names) - 1))
        key = (id(wb), cur)
        if not force and self._built == key:
            return
        self._built = key
        self.info["sheets"] = len(wb.names)
        # Blatt-Umschalter
        while (c := self.tabs.get_first_child()):
            self.tabs.remove(c)
        first = None
        for i, nm in enumerate(wb.names):
            b = Gtk.ToggleButton(label=nm, focus_on_click=False, can_focus=False)
            b.set_cursor_from_name("pointer")
            if first is None:
                first = b
            else:
                b.set_group(first)
            b.set_active(i == cur)
            b.connect("toggled", lambda w, i=i: w.get_active() and self.switch_sheet(i))
            self.tabs.append(b)
        self.tab_scroll.set_visible(len(wb.names) > 1)
        # Raster
        while (c := self.grid.get_first_child()):
            self.grid.remove(c)
        sh = wb.sheet(cur)
        self.info["nrows"], self.info["ncols"] = sh["nrows"], sh["ncols"]
        rows = sh["rows"][:SHOW_ROWS]
        ncol = min(max([len(r) for r in rows] + [1]), SHOW_COLS)
        corner = Gtk.Label(label="")
        corner.add_css_class("wsh-h")
        self.grid.attach(corner, 0, 0, 1, 1)
        for c in range(ncol):
            h = Gtk.Label(label=col_name(c), xalign=0.5)
            h.add_css_class("wsh-h")
            self.grid.attach(h, c + 1, 0, 1, 1)
        wch = [min(24, max([len(row[c][0]) for row in rows if c < len(row)] + [2]) + 1) for c in range(ncol)]
        for r, row in enumerate(rows):
            h = Gtk.Label(label=str(r + 1), xalign=1)
            h.add_css_class("wsh-h")
            self.grid.attach(h, 0, r + 1, 1, 1)
            for c in range(ncol):
                txt, num = row[c] if c < len(row) else ("", False)
                lab = Gtk.Label(label=txt, xalign=1 if num else 0, ellipsize=3, max_width_chars=24, width_chars=wch[c])
                lab.add_css_class("wsh-c")
                if r == 0:
                    lab.add_css_class("first")
                self.grid.attach(lab, c + 1, r + 1, 1, 1)
        # GtkTextView gibt eingebetteten Widgets nur ihre MINDEST-Höhe → Mindesthöhe = tatsächliche Höhe (bis 340)
        nat = self.grid.measure(Gtk.Orientation.VERTICAL, -1)[1]
        self.scroll.set_min_content_height(min(340, nat + 14))
        more = []
        if sh["nrows"] > SHOW_ROWS:
            more.append(i18n.tr("%d von %d Zeilen") % (SHOW_ROWS, sh["nrows"]))
        if sh["ncols"] > SHOW_COLS:
            more.append(i18n.tr("%d von %d Spalten") % (SHOW_COLS, sh["ncols"]))
        self.note.set_label((i18n.tr("Angezeigt: ") + ", ".join(more) + i18n.tr(" – der Rest ist in Gnumeric sichtbar.")) if more else "")
        self.note.set_visible(bool(more))
        self.refresh_sub()

    def switch_sheet(self, i):
        if i != self.info["cur"]:
            self.writer.checkpoint()
            self.info["cur"] = i
            self.build(force=True)
            self.relayout()
            self.writer.changed()

    # --- Aktionen ---
    def open_ext(self):
        apps = plat.spreadsheet_apps()
        if not plat.open_external(self.path(), app=apps[0] if apps else None):
            self.toast(i18n.tr("Konnte nicht geöffnet werden: ") + os.path.basename(self.path()))

    def insert_table(self):
        rows = table_rows(self.info)
        wb = workbook(self.path())
        if wb is None or not any(any(r) for r in rows):
            self.toast(i18n.tr("Das Blatt ist leer"))
            return
        for anchor, w in self.writer.blocks.items():          # Schreibmarke hinter die Karte
            if w is self:
                it = self.writer.anchor_iter(anchor)
                it.forward_char()
                self.writer.buf.place_cursor(it)
                break
        total = wb.sheet(self.info["cur"])["nrows"]
        self.writer.insert_block("table", rows)
        if total > TABLE_ROWS:
            self.toast(i18n.tr("Eingefügt: die ersten %d von %d Zeilen") % (TABLE_ROWS, total))

    def save_as(self):
        dlg = Gtk.FileDialog(title=i18n.tr("Tabelle speichern"), initial_name=self.info["name"])

        def done(d, res):
            try:
                gf = d.save_finish(res)
                shutil.copyfile(self.path(), gf.get_path())
                self.toast(i18n.tr("Gespeichert: ") + gf.get_basename())
            except (GLib.Error, OSError):
                pass
        dlg.save(self.writer.win, None, done)

    def ask_remove(self):
        pb.ask_dialog(self.writer.win, "Tabelle entfernen?",
                      i18n.tr("Die Tabelle „%s“ wird aus dem Dokument entfernt. Du kannst das mit Strg+Z rückgängig machen.")
                      % self.info["name"], "Entfernen", lambda: self.writer.remove_block(self), danger=True)

    def rename(self):
        def ok(name):
            name = name.strip().replace("/", "_")
            if not name:
                return
            if not name.lower().endswith(".xlsx"):
                name += ".xlsx"
            if name != self.info["name"]:
                self.writer.checkpoint()
                self.info["name"] = name
                self.title.set_label(name)
                self.writer.changed()
        pb.ask_dialog(self.writer.win, "Tabelle umbenennen", "", "Umbenennen", ok, entry=self.info["name"])

    def set_width(self, w):
        self.width = int(w)
        self.set_size_request(max(240, self.width - 8), -1)
