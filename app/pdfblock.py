# PDF-Anhang in Words: Die Datei liegt sauber in notist/data/pdfs/ (Name = Prüfsumme, gleiche PDFs nur einmal),
# im Dokument steht nur eine Karte {"t": "pdf", "file", "name", "pages"}. Gerendert wird erst auf Knopfdruck.
import hashlib, os, shutil, subprocess

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, Gio, GLib, Gtk

try:
    gi.require_version("Poppler", "0.18")
    from gi.repository import Poppler
except (ValueError, ImportError):
    Poppler = None
try:
    import cairo
except ImportError:
    cairo = None

import dialogs
import i18n
import paths

PDFS = os.path.join(paths.DATA, "pdfs")

CSS = """
.wpdf { background-color: alpha(@foreground, 0.06); border: 1px solid alpha(@foreground, 0.22); border-radius: 8px;
        padding: 10px; font-family: "Noto Sans", sans-serif; }
.wpdf-name { font-weight: 700; }
.wpdf-sub { opacity: 0.6; font-size: 9pt; }
.wpdf-thumb { border: 1px solid alpha(@foreground, 0.25); border-radius: 2px; }
.wpdf-page { border: 1px solid alpha(@foreground, 0.25); }
.light .wpdf-name { color: #1d1d1d; }
.light .wpdf { background-color: rgba(0,0,0,0.04); border-color: rgba(0,0,0,0.25); }
"""


def path_of(name):
    return os.path.join(PDFS, os.path.basename(name))


def store(src):
    """PDF in den eigenen Ordner kopieren. → {"file", "name", "pages"} oder None."""
    try:
        data = open(src, "rb").read()
    except OSError:
        return None
    if not data.startswith(b"%PDF"):
        return None
    name = hashlib.sha256(data).hexdigest()[:24] + ".pdf"
    os.makedirs(PDFS, exist_ok=True)
    dst = path_of(name)
    if not os.path.exists(dst):
        with open(dst, "wb") as f:
            f.write(data)
    return {"file": name, "name": os.path.basename(src), "pages": page_count(dst)}


def page_count(path):
    if Poppler is None:
        return 0
    try:
        return Poppler.Document.new_from_file(Gio.File.new_for_path(path).get_uri(), None).get_n_pages()
    except GLib.Error:
        return 0


def render(doc, i, width, dpr=1):
    """Seite i auf Breite `width` (logische Pixel) → (Textur, Höhe)."""
    page = doc.get_page(i)
    pw, ph = page.get_size()
    s = width / max(pw, 1)
    W, H = max(1, int(pw * s * dpr)), max(1, int(ph * s * dpr))
    img = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    cr = cairo.Context(img)
    cr.set_source_rgb(1, 1, 1)
    cr.paint()
    cr.scale(s * dpr, s * dpr)
    page.render(cr)
    img.flush()
    tex = Gdk.MemoryTexture.new(W, H, Gdk.MemoryFormat.B8G8R8A8_PREMULTIPLIED,
                                GLib.Bytes.new(bytes(img.get_data())), img.get_stride())
    return tex, ph * s


def open_in_scourge(path):
    exe = shutil.which("scourge-pdf")
    try:
        if exe:
            subprocess.Popen([exe, path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        else:
            Gio.AppInfo.launch_default_for_uri(Gio.File.new_for_path(path).get_uri(), None)
        return True
    except (OSError, GLib.Error):
        return False


def _btn(label, tip, cb):
    b = Gtk.Button(label=label, tooltip_text=tip, focus_on_click=False)
    b.add_css_class("pb"); b.add_css_class("small")
    b.set_cursor_from_name("pointer")
    b.connect("clicked", lambda *_: cb())
    return b


class PdfBlock(Gtk.Box):
    def __init__(self, writer, info):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.writer = writer
        self.info = {"file": info.get("file", ""), "name": info.get("name", "PDF"), "pages": int(info.get("pages") or 0)}
        self.doc = None
        self.width = 600
        self.add_css_class("wpdf")
        top = Gtk.Box(spacing=12)
        self.thumb = Gtk.Picture(content_fit=Gtk.ContentFit.CONTAIN, can_shrink=True, valign=Gtk.Align.START)
        self.thumb.add_css_class("wpdf-thumb")
        self.thumb.set_size_request(54, 72)
        top.append(self.thumb)
        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, hexpand=True, valign=Gtk.Align.CENTER)
        self.title = Gtk.Label(label="󰈦 " + self.info["name"], xalign=0, ellipsize=3)
        self.title.add_css_class("wpdf-name")
        self.sub = Gtk.Label(xalign=0)
        self.sub.add_css_class("wpdf-sub")
        text.append(self.title)
        text.append(self.sub)
        btns = Gtk.Box(spacing=6, margin_top=6)
        self.view_btn = _btn("󰈈 hier ansehen", "Die Seiten hier in notist anzeigen", self.toggle)
        btns.append(self.view_btn)
        btns.append(_btn("󰏌 scourge-pdf", "In scourge-pdf öffnen und bearbeiten", self.open_scourge))
        btns.append(_btn("󰆓 speichern unter", "Eine Kopie der PDF speichern", self.save_as))
        btns.append(_btn("󰆴", "PDF aus dem Dokument entfernen", lambda: writer.remove_block(self)))
        text.append(btns)
        top.append(text)
        self.append(top)
        self.pages = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, visible=False)
        self.append(self.pages)
        self.refresh_sub()
        GLib.idle_add(self.load_thumb)

    # --- Modell ---
    def model(self):
        return {"t": "pdf", **self.info}

    def path(self):
        return path_of(self.info["file"])

    def refresh_sub(self):
        n = self.info["pages"]
        ok = os.path.exists(self.path())
        s = (f"{n} Seite" + ("n" if n != 1 else "") if n else "PDF")
        try:
            sz = os.path.getsize(self.path())
            s += f" · {sz / 1048576:.1f} MB" if sz >= 1048576 else f" · {max(1, sz // 1024)} KB"
        except OSError:
            pass
        self.sub.set_label(s if ok else "Datei fehlt im Ordner notist/data/pdfs")

    def open_doc(self):
        if self.doc is None and Poppler is not None and cairo is not None:
            try:
                self.doc = Poppler.Document.new_from_file(Gio.File.new_for_path(self.path()).get_uri(), None)
            except GLib.Error:
                self.doc = None
        return self.doc

    def load_thumb(self):
        doc = self.open_doc()
        if doc is not None and doc.get_n_pages():
            if not self.info["pages"]:
                self.info["pages"] = doc.get_n_pages()
                self.refresh_sub()
            tex, h = render(doc, 0, 108, 2)
            self.thumb.set_paintable(tex)
            self.thumb.set_size_request(54, max(40, round(h / 2)))
        return False

    # --- Aktionen ---
    def toggle(self):
        show = not self.pages.get_visible()
        if show and not self.pages.get_first_child():
            doc = self.open_doc()
            if doc is None:
                self.writer.win.notify("Die PDF lässt sich hier nicht anzeigen (poppler fehlt oder Datei fehlt)")
                return
            w = max(200, min(self.width - 40, 900))
            dpr = self.get_scale_factor() or 1
            for i in range(doc.get_n_pages()):
                tex, h = render(doc, i, w, dpr)
                pic = Gtk.Picture.new_for_paintable(tex)
                pic.set_size_request(w, round(h))
                pic.set_halign(Gtk.Align.CENTER)
                pic.add_css_class("wpdf-page")
                self.pages.append(pic)
        self.pages.set_visible(show)
        self.view_btn.set_label("󰈉 ausblenden" if show else "󰈈 hier ansehen")
        GLib.timeout_add(60, lambda: (self.writer.invalidate(), False)[1])

    def open_scourge(self):
        if not open_in_scourge(self.path()):
            self.writer.win.notify("scourge-pdf lässt sich nicht starten")

    def save_as(self):
        dlg = Gtk.FileDialog(title="PDF speichern", initial_name=self.info["name"])

        def done(d, res):
            try:
                gf = d.save_finish(res)
                shutil.copyfile(self.path(), gf.get_path())
                self.writer.win.notify(f"Gespeichert: {gf.get_basename()}")
            except (GLib.Error, OSError):
                pass
        dlg.save(self.writer.win, None, done)

    def set_width(self, w):
        self.width = int(w)
        self.set_size_request(max(240, int(w)), -1)


def ask_trash_original(parent, src, on_trash):
    """Suite-Dialog nach dem Einfügen: Original in den Papierkorb? Wegklicken, Esc, ✕ oder Fokusverlust = behalten."""
    win = Gtk.Window(title="Original löschen?", transient_for=parent, modal=True, resizable=False,
                     default_width=460)
    win.add_css_class("settings")
    col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, margin_start=16, margin_end=16,
                  margin_top=6, margin_bottom=16)
    short = src.replace(os.path.expanduser("~"), "~", 1)
    msg = Gtk.Label(label=i18n.tr("Die PDF liegt jetzt im notist-Ordner. Die Datei im ursprünglichen Ordner in den "
                                  "Papierkorb legen, damit sie nicht doppelt vorhanden ist?"),
                    xalign=0, wrap=True, max_width_chars=48)
    path = Gtk.Label(label=short, xalign=0, ellipsize=1)
    path.add_css_class("wpdf-sub")
    col.append(msg)
    col.append(path)
    row = Gtk.Box(spacing=8, halign=Gtk.Align.END, margin_top=6)
    keep = Gtk.Button(label=i18n.tr("Original behalten"), focus_on_click=False)
    trash = Gtk.Button(label=i18n.tr("Original in den Papierkorb"), focus_on_click=False)
    for b in (keep, trash):
        b.add_css_class("pb"); b.add_css_class("small")
        b.set_cursor_from_name("pointer")
    trash.add_css_class("danger")
    keep.connect("clicked", lambda *_: win.close())
    state = {"seen": False}

    def do_trash(*_):
        state["seen"] = False
        win.close()
        on_trash()
    trash.connect("clicked", do_trash)
    row.append(keep)
    row.append(trash)
    col.append(row)
    dialogs.chrome(win, "Original löschen?", col)

    def active(w, _p):                    # Wegklicken (anderes Fenster/Außenbereich) = behalten
        if w.is_active():
            state["seen"] = True
        elif state["seen"]:
            w.close()
    win.connect("notify::is-active", active)
    win.present()
    keep.grab_focus()
