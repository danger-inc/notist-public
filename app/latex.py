# LaTeX-Modus von notist: Editor mit Hervorhebung, Zeilennummern und Vorschlägen beim Tippen,
# Live-PDF-Vorschau (Poppler), verständlichen Fehlermeldungen, Vorlagen und eingebauter Anleitung.
# Kompiliert wird mit dem ersten gefundenen Programm aus COMPILERS. Fehlt alles, kann die App Tectonic
# (ein einzelnes Programm, lädt LaTeX-Pakete selbst nach) ohne Admin-Rechte nach ~/.local/share/notes/tools holen.
import json, os, platform, re, shutil, tarfile, threading, time, urllib.request

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Graphene", "1.0")
from gi.repository import Gdk, Gio, GLib, Graphene, Gtk, Pango

try:
    gi.require_version("Poppler", "0.18")
    from gi.repository import Poppler
    import cairo
except (ValueError, ImportError):
    Poppler = None

import latexdata as ld
import texextra as tx
from writer import WrapLayout, file_menu, popover_button, rgba, tool

F = ld.F
import i18n  # noqa: E402
import paths
FILES = paths.LATEX_FILES      # Projektordner je Dokument (Bilder usw.)
TOOLS = paths.TOOLS
BUILD = os.path.join(GLib.get_user_cache_dir(), "notes", "latex")
TECTONIC_API = "https://api.github.com/repos/tectonic-typesetting/tectonic/releases/latest"
LIST_ENVS = ("itemize", "enumerate", "description")
PACKAGES = [
    ("amsmath", "Bessere Formeln: align, \\text, Matrizen"), ("amssymb", "Mathe-Symbole wie ℝ (\\mathbb)"),
    ("graphicx", "Bilder mit \\includegraphics"), ("geometry", "Seitenränder: \\usepackage[margin=2cm]{geometry}"),
    ("hyperref", "Klickbare Links und Verweise"), ("xcolor", "Farben"), ("booktabs", "Schöne Tabellenlinien"),
    ("csquotes", "Anführungszeichen mit \\enquote"), ("babel", "Sprache: \\usepackage[ngerman]{babel}"),
    ("setspace", "Zeilenabstand (\\onehalfspacing)"), ("enumitem", "Listen anpassen"),
    ("tikz", "Zeichnungen und Diagramme"), ("listings", "Programmcode mit Hervorhebung"),
    ("siunitx", "Zahlen und Einheiten: \\SI{3}{\\meter}"), ("float", "Bilder genau hier: [H]"),
    ("caption", "Bildunterschriften gestalten"), ("subcaption", "Mehrere Bilder nebeneinander"),
    ("fancyhdr", "Kopf- und Fußzeilen"), ("multicol", "Mehrspaltiger Text"), ("eurosym", "Euro-Zeichen €"),
    ("biblatex", "Literaturverzeichnis (für Fortgeschrittene)"), ("microtype", "Feinere Typografie"),
]

CSS = """
.latex-editor textview.tex, .latex-editor textview.tex text { background: none; color: @foreground; }
textview.tex { font-family: "JetBrainsMono Nerd Font", "JetBrains Mono", "DejaVu Sans Mono", monospace;
    font-size: 10.5pt; caret-color: @color9; }
.tex-pane { background-color: alpha(@background, 0.55); border-radius: 11px; }
.glass .tex-pane { background-color: alpha(@background, 0.25); }
.tex-gutter { font-family: "JetBrainsMono Nerd Font", monospace; }
.pdf-pane { background-color: alpha(@background, 0.55); border-radius: 11px; }
.glass .pdf-pane { background-color: alpha(@background, 0.25); }
.pdf-page { box-shadow: 0 2px 10px rgba(0,0,0,0.35); }
paned.tex-split > separator { min-width: 8px; min-height: 8px; background: none; }
.tex-tabs button { background: none; box-shadow: none; border: none; border-radius: 9px; padding: 2px 10px;
    min-height: 24px; color: alpha(@foreground, 0.6); font-weight: 800; font-size: 12px; }
.tex-tabs button:hover { color: @foreground; background-color: alpha(@color9, 0.12); }
.tex-tabs button:checked { color: @background; background-color: @color9; }
button.compile { background-color: @color9; background-image: none; color: @background; border: none;
    border-radius: 9px; font-weight: 800; padding: 0 12px; min-height: 26px; box-shadow: none; text-shadow: none; }
button.compile:hover { background-color: alpha(@color9, 0.85); }
button.compile:disabled { background-color: alpha(@color9, 0.25); color: alpha(@foreground, 0.5); }
.latex-editor textview.tex border, .latex-editor textview.tex .tex-gutter { background: none; }
.tpl { background-image: none; }
.cheat button, .tex-tabs button { background-image: none; }
.tex-status { font-size: 11px; color: alpha(@foreground, 0.6); }
.tex-state { font-size: 11px; font-weight: 800; border-radius: 8px; padding: 1px 8px; }
.tex-state.ok { color: @background; background-color: @color9; }
.tex-state.busy { color: @foreground; background-color: alpha(@color9, 0.18); }
.tex-state.err { color: #1d1d1d; background-color: #f28b82; }
.tex-state.idle { color: alpha(@foreground, 0.6); background-color: alpha(@foreground, 0.08); }
.tex-ctx { font-size: 11px; color: alpha(@foreground, 0.75); }
.tex-ctx-cmd { font-family: "JetBrainsMono Nerd Font", monospace; font-weight: 800; color: @color9; }
.problems { background-color: alpha(@background, 0.7); border-radius: 11px; border: 2px solid alpha(#f28b82, 0.5);
    margin-top: 6px; padding: 6px; }
.problems list { background: none; }
.problems row { border-radius: 8px; padding: 4px 6px; }
.problems row:hover { background-color: alpha(@color9, 0.1); }
.prob-title { font-weight: 800; font-size: 12px; }
.prob-text { font-size: 11px; color: alpha(@foreground, 0.75); }
.prob-raw { font-size: 10px; color: alpha(@foreground, 0.45); font-family: monospace; }
.prob-icon-err { color: #f28b82; font-size: 15px; }
.prob-icon-warn { color: #fdd663; font-size: 15px; }
.prob-head { font-size: 11px; font-weight: 800; letter-spacing: 1px; color: alpha(@foreground, 0.6); }
popover.complete > contents { background-color: @background; border: 2px solid @color9; border-radius: 11px; padding: 4px; }
popover.complete list { background: none; }
popover.complete row { border-radius: 7px; padding: 2px 6px; }
popover.complete row:selected { background-color: alpha(@color9, 0.25); color: @foreground; }
.cmp-name { font-family: "JetBrainsMono Nerd Font", monospace; font-weight: 800; font-size: 12px; }
.cmp-desc { font-size: 11px; color: alpha(@foreground, 0.65); }
.cmp-pkg { font-size: 10px; color: @color9; font-weight: 800; }
.cmp-hint { font-size: 10px; color: alpha(@foreground, 0.45); margin: 4px 4px 0 4px; }
.help { padding: 10px 14px; }
.help-h { font-size: 11px; font-weight: 800; letter-spacing: 1px; color: @color9; margin-top: 10px; }
.help expander title { font-weight: 800; font-size: 13px; }
.help-body { font-size: 12px; }
.cheat button { background-color: alpha(@foreground, 0.05); border: 2px solid alpha(@color9, 0.2); border-radius: 9px;
    padding: 2px 8px; min-height: 24px; font-size: 12px; box-shadow: none; }
.cheat button:hover { border-color: @color9; background-color: alpha(@color9, 0.12); }
.tpl { background-color: @surface_container; border: 2px solid alpha(@color9, 0.3); border-radius: 13px; padding: 12px; }
.tpl:hover { border-color: @color9; }
.tpl-icon { font-size: 26px; color: @color9; }
.tpl-title { font-weight: 800; font-size: 13px; }
.tpl-sub { font-size: 11px; color: alpha(@foreground, 0.6); }
.tpl-head { font-size: 18px; font-weight: 800; }
.setup { padding: 20px; }
.setup-title { font-size: 16px; font-weight: 800; }
.setup-code { font-family: monospace; font-size: 12px; background-color: alpha(@foreground, 0.07); border-radius: 7px; padding: 4px 8px; }
.compact .tex-tabs button { padding: 2px 6px; }
"""


# =====================================================================
# Compiler
# =====================================================================
TECTONIC_EXE = "tectonic.exe" if os.name == "nt" else "tectonic"


def which_tectonic():
    own = os.path.join(TOOLS, TECTONIC_EXE)
    return own if os.access(own, os.X_OK) else shutil.which("tectonic")


COMPILERS = [  # (Name, Finder) – Reihenfolge = Vorzug
    ("tectonic", which_tectonic),
    ("latexmk", lambda: shutil.which("latexmk") if shutil.which("pdflatex") else None),
    ("pdflatex", lambda: shutil.which("pdflatex")),
    ("xelatex", lambda: shutil.which("xelatex")),
    ("lualatex", lambda: shutil.which("lualatex")),
]


def find_compilers():
    return [(name, path) for name, find in COMPILERS if (path := find())]


def compile_cmd(name, exe, outdir, search=None, main="main.tex", bib=False):
    if name == "tectonic":
        cmd = [exe, "--keep-logs", "--synctex", "--chatter", "minimal", "--outdir", outdir]
        if search:
            cmd += ["-Z", f"search-path={search}"]
        return cmd + [main]
    if name == "latexmk":
        return [exe, "-pdf", "-synctex=1", "-interaction=nonstopmode", "-file-line-error", f"-outdir={outdir}", main]
    one = [exe, "-synctex=1", "-interaction=nonstopmode", "-file-line-error", f"-output-directory={outdir}", main]
    if bib and shutil.which("bibtex"):      # pdflatex & Co.: Literatur braucht bibtex und zwei weitere Läufe
        import shlex
        stem = os.path.join(outdir, os.path.splitext(main)[0])
        line = " ".join(shlex.quote(x) for x in one)
        return ["sh", "-c", f"{line}; BIBINPUTS=.: bibtex {shlex.quote(stem)}; {line}; {line}"]
    return one


def install_tectonic(progress, done):
    """Lädt die neueste Tectonic-Version von GitHub (Hintergrund-Thread). progress(text, anteil), done(fehler)."""
    def run():
        try:
            if os.name == "nt":
                arch = {"AMD64": "x86_64-pc-windows-msvc", "x86_64": "x86_64-pc-windows-msvc"}.get(platform.machine())
                ext = ".zip"
            else:
                arch = {"x86_64": "x86_64-unknown-linux-musl", "aarch64": "aarch64-unknown-linux-musl",
                        "armv7l": "arm-unknown-linux-musleabihf"}.get(platform.machine())
                ext = ".tar.gz"
            if not arch:
                raise RuntimeError(f"Prozessor {platform.machine()} wird nicht unterstützt")
            GLib.idle_add(progress, "Suche neueste Version …", 0.02)
            req = urllib.request.Request(TECTONIC_API, headers={"User-Agent": "notes-app"})
            with urllib.request.urlopen(req, timeout=20) as r:
                rel = json.load(r)
            asset = next(a for a in rel["assets"] if a["name"].endswith(arch + ext))
            os.makedirs(TOOLS, exist_ok=True)
            tmp = os.path.join(TOOLS, "tectonic" + ext + ".part")
            with urllib.request.urlopen(asset["browser_download_url"], timeout=30) as r, open(tmp, "wb") as f:
                total, got = asset["size"] or 1, 0
                while chunk := r.read(65536):
                    f.write(chunk)
                    got += len(chunk)
                    GLib.idle_add(progress, f"Lade Tectonic … {got / 1e6:.1f} / {total / 1e6:.1f} MB", got / total)
            dest = os.path.join(TOOLS, TECTONIC_EXE)
            if ext == ".zip":
                import zipfile
                with zipfile.ZipFile(tmp) as z:
                    name = next(n for n in z.namelist() if os.path.basename(n) == TECTONIC_EXE)
                    with z.open(name) as src, open(dest + ".new", "wb") as out:
                        shutil.copyfileobj(src, out)
            else:
                with tarfile.open(tmp) as tar:
                    member = next(m for m in tar.getmembers() if os.path.basename(m.name) == "tectonic" and m.isfile())
                    src = tar.extractfile(member)
                    with open(dest + ".new", "wb") as out:
                        shutil.copyfileobj(src, out)
            os.chmod(dest + ".new", 0o755)
            os.replace(dest + ".new", dest)
            os.remove(tmp)
            GLib.idle_add(done, None)
        except Exception as e:  # noqa: BLE001 – Netzwerk/Dateifehler dem Nutzer zeigen
            GLib.idle_add(done, str(e) or e.__class__.__name__)
    threading.Thread(target=run, daemon=True).start()


def parse_log(log, out=""):
    """→ Liste von dict(line, file, kind 'error'|'warning', msg, title, text)."""
    probs, seen = [], set()
    cur = ["main.tex"]

    def add(line, kind, msg, file=None):
        msg = msg.strip().rstrip(".")
        key = (line, kind, msg[:60])
        if key in seen or not msg:
            return
        seen.add(key)
        ex = ld.explain(msg, kind == "warning")
        if kind == "warning" and not ex:
            return
        probs.append(dict(line=line, file=file or "main.tex", kind=kind, msg=msg, title=ex[0] if ex else "Fehler",
                          text=ex[1] if ex else ""))

    def track(l):
        """Welche Datei liest TeX gerade? „(./kapitel.tex“ öffnet, „)“ schließt."""
        for m in re.finditer(r"\((?:\./)?([^\s()]+\.(?:tex|bib))|\)", l):
            if m.group(1):
                cur.append(os.path.basename(m.group(1)))
            elif len(cur) > 1:
                cur.pop()

    lines = log.splitlines()
    for i, l in enumerate(lines):
        m = re.match(r"^(?:\./)?([^\s:]+\.tex):(\d+): (.*)", l)
        if m:
            add(int(m.group(2)), "error", m.group(3), os.path.basename(m.group(1)))
            continue
        if l.startswith("! "):
            msg, line = l[2:], None
            for nxt in lines[i + 1:i + 30]:
                lm = re.match(r"^l\.(\d+)", nxt)
                if lm:
                    line = int(lm.group(1))
                    break
            add(line, "error", msg, cur[-1] if cur[-1].endswith(".tex") else "main.tex")
            continue
        track(l)
        m = re.search(r"(LaTeX|Package \w+) Warning: (.*)", l)
        if m:
            msg = m.group(2)
            for nxt in lines[i + 1:i + 4]:          # Warnungen gehen oft über mehrere Zeilen
                if nxt.startswith("(") and not nxt.startswith("(./"):
                    msg += " " + nxt.strip("() ")
                else:
                    break
            lm = re.search(r"on input line (\d+)", msg)
            add(int(lm.group(1)) if lm else None, "warning", msg, cur[-1])
            continue
        m = re.match(r"^Overfull \\hbox .* at lines? (\d+)", l)
        if m:
            add(int(m.group(1)), "warning", l, cur[-1])
    for l in out.splitlines():                       # Tectonic: "error: main.tex:12: …"
        m = re.match(r"^error: (?:\./)?([^\s:]+\.tex):(\d+): (.*)", l)
        if m:
            add(int(m.group(2)), "error", m.group(3), os.path.basename(m.group(1)))
        elif l.startswith("error:") and not any(p["kind"] == "error" for p in probs) and "halted" not in l:
            add(None, "error", l[6:])
    probs.sort(key=lambda p: (p["kind"] != "error", p["line"] or 0))
    return probs


# =====================================================================
# Bausteine
# =====================================================================
LATEX_FILE_MENU = (
    (None, (("󰝰", ".tex-Datei öffnen …", "strg+o", "win.doc-import"),)),
    ("Exportieren", (("󰈦", "PDF speichern unter …", ".pdf", "win.latex-export::pdf"),
                     ("󰗀", ".tex-Datei speichern unter …", ".tex", "win.latex-export::tex"))),
    ("Weiteres", (("󰈬", "In ein Words-Dokument umwandeln", "", "win.latex-to-words"),
                  ("󰉋", "Projektordner öffnen (Bilder usw.)", "", "win.latex-folder"))),
)


class Gutter(Gtk.Widget):
    """Zeilennummern links neben dem Text (über TextView.set_gutter)."""

    def __init__(self, ed):
        super().__init__()
        self.ed = ed
        self.add_css_class("tex-gutter")

    def do_measure(self, orientation, for_size):
        if orientation == Gtk.Orientation.HORIZONTAL:
            digits = max(2, len(str(self.ed.buf.get_line_count())))
            lay = self.create_pango_layout("8" * digits)
            w = lay.get_pixel_size()[0] + 18
            return w, w, -1, -1
        return 0, 0, -1, -1

    def do_snapshot(self, snap):
        view, buf = self.ed.view, self.ed.buf
        vis = view.get_visible_rect()
        it, _ = view.get_line_at_y(vis.y)
        cur = buf.get_iter_at_mark(buf.get_insert()).get_line()
        fg, accent, err = self.ed.colors["dim"], self.ed.colors["cmd"], rgba("#f28b82")
        w = self.get_width()
        while True:
            y, h = view.get_line_yrange(it)
            if y > vis.y + vis.height:
                break
            ln = it.get_line()
            _, wy = view.buffer_to_window_coords(Gtk.TextWindowType.LEFT, 0, y)
            lay = self.create_pango_layout(str(ln + 1))
            lw, lh = lay.get_pixel_size()
            snap.save()
            snap.translate(Graphene.Point().init(w - lw - 8, wy))
            snap.append_layout(lay, accent if ln == cur else (err if ln + 1 in self.ed.err_lines else fg))
            snap.restore()
            if ln + 1 in self.ed.err_lines:
                snap.append_color(err, Graphene.Rect().init(1, wy + 2, 3, max(4, lh - 4)))
            if not it.forward_line():
                break


class TexView(Gtk.TextView):
    """TextView, die eigene Popover (Vorschläge, Formel-Vorschau) mit positioniert – GTK macht das nur für seine."""

    def __init__(self, **kw):
        super().__init__(**kw)
        self.popovers = []

    def do_size_allocate(self, width, height, baseline):
        Gtk.TextView.do_size_allocate(self, width, height, baseline)
        for p in self.popovers:
            if p.get_visible():
                p.present()


class PageWidget(Gtk.Widget):
    """Eine PDF-Seite: zeigt eine Textur in fester (logischer) Größe."""

    def __init__(self):
        super().__init__(halign=Gtk.Align.CENTER)
        self.tex, self.w, self.h = None, 100, 141
        self.scale, self.flash = 1.0, None
        self.add_css_class("pdf-page")

    def set_page(self, tex, w, h):
        self.tex = tex
        if (int(w), int(h)) != (self.w, self.h):
            self.w, self.h = int(w), int(h)
            self.queue_resize()
        self.queue_draw()

    def do_measure(self, orientation, for_size):
        v = self.w if orientation == Gtk.Orientation.HORIZONTAL else self.h
        return v, v, -1, -1

    def do_snapshot(self, snap):
        r = Graphene.Rect().init(0, 0, self.get_width(), self.get_height())
        if self.tex:
            snap.append_texture(self.tex, r)
        else:
            snap.append_color(rgba("#ffffff"), r)
        if self.flash:
            x, y, w, h = self.flash
            snap.append_color(rgba("#fdd663", 0.45), Graphene.Rect().init(x - 4, y - 2, w + 8, h + 4))


class PdfPreview(Gtk.Box):
    def __init__(self, settings):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.settings = settings
        self.doc, self.path, self.pages = None, None, []
        self.zoom = settings.get("pdf_zoom", 0)          # 0 = an Breite anpassen
        self._render_id = None
        self.scroll = Gtk.ScrolledWindow(vexpand=True, hexpand=True)
        self.scroll.add_css_class("pdf-pane")
        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14, margin_top=14, margin_bottom=14,
                           margin_start=14, margin_end=14)
        self.scroll.set_child(self.box)
        self.scroll.get_hadjustment().connect("notify::page-size", lambda *_: self.zoom == 0 and self.queue_render(120))
        self.stack = Gtk.Stack(vexpand=True, transition_type=Gtk.StackTransitionType.CROSSFADE)
        self.stack.add_named(self.scroll, "pdf")
        self.empty = Gtk.Label(wrap=True, justify=Gtk.Justification.CENTER, valign=Gtk.Align.CENTER)
        self.empty.add_css_class("empty-hint")
        e = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        e.add_css_class("pdf-pane")
        e.append(self.empty)
        self.empty.set_vexpand(True)
        self.stack.add_named(e, "empty")
        self.append(self.stack)
        bar = Gtk.Box(spacing=4, margin_top=6)
        bar.add_css_class("tex-status")
        self.page_label = Gtk.Label(xalign=0, hexpand=True)
        bar.append(self.page_label)
        bar.append(tool("−", "Kleiner", lambda *_: self.step(-1)))
        self.zoom_btn = Gtk.Button(tooltip_text="An Breite anpassen", focus_on_click=False)
        self.zoom_btn.add_css_class("wt")
        self.zoom_btn.connect("clicked", lambda *_: self.set_zoom(0))
        bar.append(self.zoom_btn)
        bar.append(tool("+", "Größer", lambda *_: self.step(1)))
        bar.append(tool("󰏌", "Im PDF-Programm öffnen", lambda *_: self.open_external()))
        self.append(bar)
        self.scroll.get_vadjustment().connect("value-changed", lambda *_: self.update_page_label())
        self.on_inverse = None
        click = Gtk.GestureClick()
        click.connect("pressed", self.on_click)
        self.box.add_controller(click)
        self.show_message("Noch keine Vorschau.\nStrg+S kompiliert das Dokument.")
        self.update_zoom_label()

    def show_message(self, text):
        self.empty.set_label(text)
        self.stack.set_visible_child_name("empty")
        self.page_label.set_label("")

    def clear(self, text="Noch keine Vorschau.\nStrg+S kompiliert das Dokument."):
        self.doc, self.path = None, None
        while (c := self.box.get_first_child()):
            self.box.remove(c)
        self.pages = []
        self.show_message(text)

    def load(self, path):
        if Poppler is None:
            self.show_message("Für die Vorschau fehlt poppler-glib.\nDas PDF lässt sich trotzdem extern öffnen.")
            self.path = path
            return
        try:
            with open(path, "rb") as f:
                data = f.read()
            doc = Poppler.Document.new_from_bytes(GLib.Bytes.new(data), None)
        except (OSError, GLib.Error):
            return
        self.doc, self.path = doc, path
        self.stack.set_visible_child_name("pdf")
        self.queue_render(0)

    def queue_render(self, delay):
        if self._render_id:
            GLib.source_remove(self._render_id)
        self._render_id = GLib.timeout_add(delay, self.render)

    def scale_for(self, page_w):
        if self.zoom:
            return self.zoom
        avail = self.scroll.get_hadjustment().get_page_size() or self.scroll.get_width() or 500
        return max(0.2, (avail - 30) / page_w)

    def render(self):
        self._render_id = None
        if not self.doc:
            return False
        n = self.doc.get_n_pages()
        while len(self.pages) < n:
            p = PageWidget()
            self.pages.append(p)
            self.box.append(p)
        while len(self.pages) > n:
            self.box.remove(self.pages.pop())
        native = self.get_native()
        surf = native.get_surface() if native else None
        dpr = surf.get_scale() if surf and hasattr(surf, "get_scale") else self.get_scale_factor()
        todo = list(range(n))

        def step():
            if not todo or not self.doc:
                return False
            i = todo.pop(0)
            if i >= len(self.pages):
                return False
            page = self.doc.get_page(i)
            pw, ph = page.get_size()
            s = self.scale_for(pw)
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
            self.pages[i].set_page(tex, pw * s, ph * s)
            self.pages[i].scale = s
            return bool(todo)
        step()                    # erste Seite sofort, Rest im Leerlauf
        if todo:
            GLib.idle_add(step)
        self.update_page_label()
        return False

    def on_click(self, gesture, n, x, y):
        """Doppelklick oder Strg+Klick ins PDF: zur Stelle im Quelltext (SyncTeX)."""
        ctrl = gesture.get_current_event_state() & Gdk.ModifierType.CONTROL_MASK
        if not (n == 2 or ctrl) or not self.on_inverse:
            return
        for i, p in enumerate(self.pages):
            ok, pt = self.box.compute_point(p, Graphene.Point().init(x, y))
            if ok and 0 <= pt.x <= p.get_width() and 0 <= pt.y <= p.get_height():
                self.on_inverse(i, pt.x / p.scale, pt.y / p.scale)
                return

    def show_location(self, page, x, y, w):
        """Stelle im PDF zeigen und kurz gelb markieren."""
        if page >= len(self.pages):
            return
        p = self.pages[page]
        ok, pt = p.compute_point(self.box, Graphene.Point().init(0, 0))
        if ok:
            adj = self.scroll.get_vadjustment()
            adj.set_value(max(0, pt.y + y * p.scale - adj.get_page_size() * 0.3))
        for q in self.pages:
            q.flash = None
        p.flash = (x * p.scale, (y - 10) * p.scale, w * p.scale, 13 * p.scale)
        p.queue_draw()

        def clear():
            p.flash = None
            p.queue_draw()
            return False
        GLib.timeout_add(1600, clear)

    def update_page_label(self):
        if not self.doc:
            return
        n = self.doc.get_n_pages()
        v = self.scroll.get_vadjustment()
        cur = 1
        for i, p in enumerate(self.pages):
            ok, pt = p.compute_point(self.box, Graphene.Point().init(0, 0))
            if ok and pt.y <= v.get_value() + v.get_page_size() / 3:
                cur = i + 1
        self.page_label.set_label(f"Seite {cur} von {n}")

    def set_zoom(self, z):
        self.zoom = z
        self.settings["pdf_zoom"] = z
        self.update_zoom_label()
        self.queue_render(0)

    def step(self, d):
        cur = self.zoom or (self.scale_for(self.doc.get_page(0).get_size()[0]) if self.doc else 1.0)
        self.set_zoom(round(min(4.0, max(0.3, cur * (1.2 if d > 0 else 1 / 1.2))), 2))

    def update_zoom_label(self):
        self.zoom_btn.set_label("Breite" if not self.zoom else f"{round(self.zoom * 100)} %")

    def open_external(self):
        if self.path and os.path.exists(self.path):
            Gio.AppInfo.launch_default_for_uri(Gio.File.new_for_path(self.path).get_uri(), None)


# =====================================================================
# Editor
# =====================================================================
class LatexEditor(Gtk.Box):
    """on_change(): Text/Titel geändert. notify(text): kurze Meldung oben in notist."""

    def __init__(self, win, on_change, settings, notify):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, vexpand=True)
        self.add_css_class("latex-editor")
        self.win, self.on_change, self.settings, self.notify = win, on_change, settings, notify
        self.settings.setdefault("live", True)
        self.settings.setdefault("hints", True)
        self.settings.setdefault("autoclose", True)
        self.nid, self.source = None, None
        self._loading = False
        self._hl_id = self._compile_id = self._ctx_id = None
        self.proc, self._gen, self._pending = None, 0, False
        self.err_lines = set()
        self.fields = []                # Schnipsel-Felder (TextMarks) für Tab
        self.cands, self._navigated = [], False
        self.colors = {}
        self.last_written = None
        self.build()

    # ================= Aufbau =================
    def build(self):
        self.title = Gtk.Entry(placeholder_text="Name des Dokuments")
        self.title.add_css_class("doc-title")
        self.title.connect("changed", lambda *_: self._loading or self.on_change())
        self.title.connect("activate", lambda *_: self.focus_text())
        # Titelzeile: rechts daneben setzt notist „anheften“ / „löschen“ ein (title_row)
        self.title.set_hexpand(True)
        self.title_row = Gtk.Box(spacing=6)
        self.title_row.append(self.title)
        self.append(self.title_row)
        self.append(self.build_tools())
        self.banner = Gtk.Revealer(transition_type=Gtk.RevealerTransitionType.SLIDE_DOWN)
        self.append(self.banner)

        self.view = TexView(wrap_mode=Gtk.WrapMode.WORD_CHAR, top_margin=10, bottom_margin=40,
                                 left_margin=8, right_margin=10, pixels_inside_wrap=1, monospace=True)
        self.view.add_css_class("tex")
        __import__("writer").calm_handles(self.view)
        self.bufs = []                      # alle Puffer (Haupt + Zusatzdateien), für Farben & Tags
        self.spell = None
        self.main_buf = self.new_buffer()
        self.view.set_buffer(self.main_buf)
        self.buf = self.main_buf
        self.cur_file = "main.tex"
        self.file_bufs = {"main.tex": self.main_buf}
        self._dirty_files, self._save_files_id = set(), None
        self.synctex = None
        self.gutter = Gutter(self)
        self.view.set_gutter(Gtk.TextWindowType.LEFT, self.gutter)
        k = Gtk.EventControllerKey()
        k.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        k.connect("key-pressed", self.on_key)
        self.view.add_controller(k)
        focus = Gtk.EventControllerFocus()
        focus.connect("leave", lambda *_: (self.hide_complete(), self.hide_formula()))
        self.view.add_controller(focus)
        self.tscroll = Gtk.ScrolledWindow(vexpand=True, hexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER)
        self.tscroll.set_child(self.view)
        self.tscroll.add_css_class("tex-pane")
        self.tscroll.get_vadjustment().connect("value-changed", lambda *_: (self.gutter.queue_draw(),
                                                                            self.hide_complete()))
        self.overlay = Gtk.Overlay(vexpand=True)
        self.overlay.set_child(self.tscroll)
        self.templates = self.build_templates()
        self.overlay.add_overlay(self.templates)

        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        left.append(self.build_findbar())
        left.append(self.build_file_tabs())
        left.append(self.overlay)
        left.append(self.build_problems())

        right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        tabs = Gtk.Box(spacing=2, margin_bottom=6)
        tabs.add_css_class("tex-tabs")
        self.side_btns = {}
        group = None
        for key, label in (("preview", "󰈙  Vorschau"), ("help", "󰋖  Hilfe & Spickzettel")):
            b = Gtk.ToggleButton(focus_on_click=False)
            b.set_child(Gtk.Label(label=label, ellipsize=Pango.EllipsizeMode.END))
            if group:
                b.set_group(group)
            group = group or b
            b.connect("toggled", lambda btn, k=key: btn.get_active() and self.side.set_visible_child_name(k))
            tabs.append(b)
            self.side_btns[key] = b
        tabs.append(Gtk.Box(hexpand=True))
        tabs.append(self.live_btn)
        tabs.append(self.compile_btn)
        right.append(tabs)
        self.side = Gtk.Stack(vexpand=True, transition_type=Gtk.StackTransitionType.CROSSFADE, vhomogeneous=False)
        self.preview = PdfPreview(self.settings)
        self.preview.on_inverse = self.inverse_search
        self.side.add_named(self.preview, "preview")
        self.side.add_named(self.build_setup(), "setup")
        self.side.add_named(self.build_help(), "help")
        right.append(self.side)

        self.paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL, vexpand=True, wide_handle=True,
                               shrink_start_child=False, shrink_end_child=False, resize_start_child=True)
        self.paned.add_css_class("tex-split")
        self.paned.set_start_child(left)
        self.paned.set_end_child(right)
        left.set_size_request(260, 70)        # niedrig halten: passt auch in kleine Kachelfenster
        right.set_size_request(240, 70)
        self.paned.connect("notify::position", self.on_paned_moved)
        self._paned_init = False
        self.append(self.paned)
        self.append(self.build_status())

        self.build_complete()
        self.side_btns["preview"].set_active(True)
        self.compilers = self.pick_compilers()
        self.update_compiler_ui()
        import spell as _spell
        self.spell = _spell.SpellCheck(self.view, lambda: self.settings.get("spell", True) and self.spell_global(),
                                       skip=tx.spell_skip)
        for b in self.bufs:
            self.spell.attach(b)

    def build_tools(self):
        bar = Gtk.Box()
        bar.set_layout_manager(WrapLayout(spacing=0, row_spacing=4))
        bar.add_css_class("writer-tools")
        groups = []

        def group(*ws):
            g = Gtk.Box(spacing=2, valign=Gtk.Align.CENTER)
            g.add_css_class("wgroup")
            for w in ws:
                g.append(w)
            groups.append(g)
            return g

        self.compile_btn = Gtk.Button(tooltip_text="PDF erzeugen (Strg+S oder Strg+Enter)",
                                      focus_on_click=False, can_focus=False)
        self.compile_btn.set_child(Gtk.Label(label="󰐊  Kompilieren", ellipsize=Pango.EllipsizeMode.END))
        self.compile_btn.add_css_class("compile")
        self.compile_btn.connect("clicked", lambda *_: self.compile(manual=True))
        self.live_btn = tool("󰑐 Live", "Beim Tippen automatisch neu kompilieren", toggle=True)
        self.live_btn.set_active(self.settings["live"])
        self.live_btn.connect("toggled", lambda b: (self.settings.__setitem__("live", b.get_active()),
                                                    b.get_active() and self.schedule_compile()))
        filebtn = Gtk.MenuButton(tooltip_text="Datei: öffnen, exportieren, umwandeln", can_focus=False)
        filebtn.set_popover(file_menu(LATEX_FILE_MENU, "Quelltext wird automatisch gespeichert"))
        filebtn.set_child(Gtk.Label(label="󰈙"))
        filebtn.add_css_class("wt")
        group(filebtn, tool("󰕌", "Rückgängig (Strg+Z)", lambda *_: self.buf.get_can_undo() and self.buf.undo()),
              tool("󰑎", "Wiederholen (Strg+Umschalt+Z)", lambda *_: self.buf.get_can_redo() and self.buf.redo()))

        group(tool("<b>F</b>", "Fett: \\textbf{…} (Strg+B)", lambda *_: self.wrap("textbf"), markup=True),
              tool("<i>K</i>", "Kursiv: \\textit{…} (Strg+I)", lambda *_: self.wrap("textit"), markup=True),
              tool("<u>U</u>", "Unterstrichen: \\underline{…} (Strg+U)", lambda *_: self.wrap("underline"), markup=True),
              tool("$x$", "Formel im Text: $…$ (Strg+M)", lambda *_: self.insert_snippet("$" + F + "$")))

        cats = dict(ld.CHEATS)
        menus = [("󰉫 Struktur", "Überschriften, Inhaltsverzeichnis, Fußnoten", cats["Grundgerüst"]),
                 ("󰊄 Text", "Schrift und Hervorhebungen", cats["Text"]),
                 ("󰉹 Listen", "Aufzählungen", cats["Listen"]),
                 ("󰿈 Mathe", "Formeln", cats["Mathe"]),
                 ("Ω Symbole", "Sonderzeichen und griechische Buchstaben", cats["Symbole"] + cats["Griechisch"])]
        ws = [self.snippet_menu(label, tip, items) for label, tip, items in menus] + [self.insert_menu()]
        group(*ws[:3])
        group(*ws[3:])

        self.outline_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        ob, self.outline_pop = popover_button("󰠶", "Gliederung: zu einer Überschrift springen", self.outline_box)
        self.outline_pop.connect("show", lambda *_: self.fill_outline())
        self.find_btn = tool("󰍉", "Suchen (Strg+F)", lambda *_: self.show_find())

        # Hilfen: alles abschaltbar, damit sie später nicht beim flüssigen Schreiben stören
        opts = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        head = Gtk.Label(label="SCHREIBHILFEN", xalign=0)
        head.add_css_class("wpop-head")
        opts.append(head)
        for key, title, sub in (
                ("hints", "Vorschläge beim Tippen", "Nach \\ + 2 Buchstaben. Aus: nur mit Strg+Leertaste"),
                ("autoclose", "Klammern schließen", "{ ergänzt die passende }"),
                ("lists", "Listen fortsetzen", "Enter nach \\item beginnt den nächsten Punkt"),
                ("auto_problems", "Fehlerliste automatisch zeigen", "Sonst nur per Klick unten links")):
            self.settings.setdefault(key, True)
            row = Gtk.Box(spacing=12)
            v = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True)
            t = Gtk.Label(label=title, xalign=0)
            t.add_css_class("tpl-title")
            d = Gtk.Label(label=sub, xalign=0)
            d.add_css_class("tpl-sub")
            v.append(t)
            v.append(d)
            row.append(v)
            sw = Gtk.Switch(active=self.settings[key], valign=Gtk.Align.CENTER)
            sw.connect("notify::active", lambda w, _p, k=key: self.settings.__setitem__(k, w.get_active()))
            row.append(sw)
            opts.append(row)
        hb, _ = popover_button("󰌵", "Schreibhilfen ein-/ausschalten", opts)
        g = group(ob, self.find_btn, tool("󰈈", "Cursorzeile im PDF zeigen (Strg+J)\nUmgekehrt: Doppelklick ins PDF",
                                         lambda *_: self.forward_search()))
        g = group(tool("󰘦 Befehle", "Alle LaTeX-Befehle mit Erklärung (F1)", lambda *_: self.open_overview()),
                  tool("󰂺", "Quellen: Literatur verwalten und zitieren", lambda *_: self.open_bib()), hb)
        g.add_css_class("last")
        for g in groups:
            bar.append(g)
        return bar

    def snippet_menu(self, label, tip, items):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        head = Gtk.Label(label=tip, xalign=0)
        head.add_css_class("wpop-head")
        box.append(head)
        flow = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, max_children_per_line=6, min_children_per_line=3,
                           column_spacing=4, row_spacing=4, homogeneous=False)
        flow.add_css_class("cheat")
        holder = {}
        for text, snip, desc, pkg in items:
            b = Gtk.Button(label=text, focus_on_click=False)
            code = snip.replace(F, "…").strip()
            b.set_tooltip_text(code + (f"\n{desc}" if desc else "") + (f"\nbraucht \\usepackage{{{pkg}}}" if pkg else ""))
            b.connect("clicked", lambda _b, s=snip, p=pkg: (holder["pop"].popdown(), self.insert_snippet(s, p)))
            flow.append(b)
        sc = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER, propagate_natural_height=True,
                                max_content_height=360, min_content_width=360)
        sc.set_child(flow)
        box.append(sc)
        mb, pop = popover_button(label, tip, box)
        holder["pop"] = pop
        return mb

    def insert_menu(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        holder = {}

        def head(t):
            h = Gtk.Label(label=t, xalign=0)
            h.add_css_class("wpop-head")
            box.append(h)

        def item(label, cb):
            b = Gtk.Button(label=label)
            b.add_css_class("wt")
            b.get_child().set_xalign(0)
            b.connect("clicked", lambda *_: (holder["pop"].popdown(), cb()))
            box.append(b)
        head("BILD")
        item("󰋩  Bild aus Datei …", self.pick_image)
        head("TABELLE")
        grid = Gtk.Box(spacing=8)
        rows = Gtk.SpinButton.new_with_range(1, 40, 1)
        rows.set_value(3)
        cols = Gtk.SpinButton.new_with_range(1, 12, 1)
        cols.set_value(3)
        for lab, sp in (("Zeilen", rows), ("Spalten", cols)):
            grid.append(Gtk.Label(label=lab))
            sp.add_css_class("wt")
            grid.append(sp)
        box.append(grid)
        item("󰓫  Tabelle einfügen", lambda: self.insert_table(int(rows.get_value()), int(cols.get_value())))
        item("󰓫  Tabellen-Editor … (auch zum Bearbeiten)", self.open_table_editor)
        head("WEITERES")
        for label, snip, pkg in (("󰌷  Link", "\\href{https://" + F + "}{" + F + "Linktext}", "hyperref"),
                                 ("󰆈  Fußnote", "\\footnote{" + F + "}", None),
                                 ("󰌹  Verweis auf Label", "\\ref{" + F + "}", None),
                                 ("󰂺  Quelle zitieren", "\\cite{" + F + "}", None),
                                 ("󰈚  Literaturverzeichnis", "\\bibliographystyle{plain}\n\\bibliography{literatur}\n", None),
                                 ("󰈚  Inhaltsverzeichnis", "\\tableofcontents\n", None),
                                 ("󰛗  Neue Seite", "\\newpage\n", None),
                                 ("󰅩  Code-Block", ld.env_snippet("verbatim"), None)):
            item(label, lambda s=snip, p=pkg: self.insert_snippet(s, p))
        mb, pop = popover_button("󰐕 Einfügen", "Bild, Tabelle, Link, Fußnote …", box)
        holder["pop"] = pop
        return mb

    def build_findbar(self):
        bar = Gtk.Box(spacing=6, margin_bottom=6)
        self.find_entry = Gtk.SearchEntry(placeholder_text="Im Quelltext suchen", hexpand=True)
        self.find_entry.add_css_class("pb")
        self.find_entry.connect("search-changed", lambda *_: self.run_search())
        self.find_entry.connect("activate", lambda *_: self.find_step(1))
        self.find_entry.connect("stop-search", lambda *_: self.hide_find())
        bar.append(self.find_entry)
        bar.append(tool("󰅃", "Vorheriger (Umschalt+Enter)", lambda *_: self.find_step(-1)))
        bar.append(tool("󰅀", "Nächster (Enter)", lambda *_: self.find_step(1)))
        self.find_info = Gtk.Label()
        self.find_info.add_css_class("tex-status")
        bar.append(self.find_info)
        bar.append(tool("󰅖", "Schließen (Esc oder Strg+F)", lambda *_: self.hide_find()))
        k = Gtk.EventControllerKey()
        k.connect("key-pressed", lambda c, kv, code, st: kv == Gdk.KEY_Return and st & Gdk.ModifierType.SHIFT_MASK
                  and (self.find_step(-1) or True))
        self.find_entry.add_controller(k)
        self.findrev = Gtk.Revealer(transition_type=Gtk.RevealerTransitionType.SLIDE_DOWN)
        self.findrev.set_child(bar)
        return self.findrev

    def build_problems(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.add_css_class("problems")
        head = Gtk.Box(spacing=6)
        self.prob_head = Gtk.Label(xalign=0, hexpand=True)
        self.prob_head.add_css_class("prob-head")
        head.append(self.prob_head)
        logbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.log_view = Gtk.TextView(editable=False, monospace=True, wrap_mode=Gtk.WrapMode.CHAR)
        sc = Gtk.ScrolledWindow(min_content_width=560, min_content_height=320)
        sc.set_child(self.log_view)
        logbox.append(sc)
        lb, _ = popover_button("Protokoll", "Vollständige Ausgabe des Compilers", logbox)
        head.append(lb)
        head.append(tool("󰅖", "Ausblenden", lambda *_: self.probrev.set_reveal_child(False)))
        box.append(head)
        self.prob_list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        self.prob_list.connect("row-activated", lambda lb, row: row.line and self.goto_line(row.line, row.file))
        sc = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER, propagate_natural_height=True,
                                max_content_height=170)
        sc.set_child(self.prob_list)
        box.append(sc)
        self.probrev = Gtk.Revealer(transition_type=Gtk.RevealerTransitionType.SLIDE_UP)
        self.probrev.set_child(box)
        return self.probrev

    def build_status(self):
        bar = Gtk.Box(spacing=8, margin_top=6)
        bar.add_css_class("tex-status")
        self.state = Gtk.Label(label="Bereit")
        self.state.add_css_class("tex-state")
        self.state.add_css_class("idle")
        self.state_click = Gtk.GestureClick()
        self.state_click.connect("released", lambda *_: self.probs and self.probrev.set_reveal_child(
            not self.probrev.get_reveal_child()))
        self.state.add_controller(self.state_click)
        bar.append(self.state)
        self.ctx = Gtk.Box(spacing=6, hexpand=True)
        self.ctx_cmd = Gtk.Label()
        self.ctx_cmd.add_css_class("tex-ctx-cmd")
        self.ctx_text = Gtk.Label(xalign=0, ellipsize=Pango.EllipsizeMode.END, hexpand=True)
        self.ctx_text.add_css_class("tex-ctx")
        self.ctx.append(self.ctx_cmd)
        self.ctx.append(self.ctx_text)
        bar.append(self.ctx)
        self.pos_label = Gtk.Label()
        bar.append(self.pos_label)
        self.comp_label = Gtk.Label()
        bar.append(self.comp_label)
        self.probs = []
        return bar

    def build_setup(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, valign=Gtk.Align.CENTER)
        box.add_css_class("setup")
        t = Gtk.Label(label="󰗀  Noch kein LaTeX-Compiler da", xalign=0, wrap=True)
        t.add_css_class("setup-title")
        box.append(t)
        msg = Gtk.Label(wrap=True, xalign=0, label=(
            "Um aus dem Quelltext ein PDF zu machen, braucht notist einen Compiler. Am einfachsten ist Tectonic: "
            "ein einzelnes Programm (≈ 10 MB), das fehlende LaTeX-Pakete beim ersten Kompilieren selbst "
            "aus dem Internet lädt. Keine Admin-Rechte nötig."))
        box.append(msg)
        self.setup_btn = Gtk.Button(label="󰇚  Tectonic einrichten", halign=Gtk.Align.START)
        self.setup_btn.add_css_class("compile")
        self.setup_btn.connect("clicked", lambda *_: self.setup_tectonic())
        box.append(self.setup_btn)
        self.setup_bar = Gtk.ProgressBar(visible=False)
        box.append(self.setup_bar)
        self.setup_info = Gtk.Label(wrap=True, xalign=0)
        self.setup_info.add_css_class("tex-status")
        box.append(self.setup_info)
        alt = Gtk.Label(wrap=True, xalign=0, margin_top=8,
                        label="Oder über die Paketverwaltung (danach notist neu starten):")
        alt.add_css_class("tex-status")
        box.append(alt)
        for cmd in ("sudo pacman -S tectonic            # Arch", "sudo apt install texlive-latex-extra latexmk   # Debian/Ubuntu",
                    "sudo dnf install texlive-scheme-medium latexmk   # Fedora"):
            l = Gtk.Label(label=cmd, xalign=0, selectable=True, wrap=True, wrap_mode=Pango.WrapMode.WORD_CHAR)
            l.add_css_class("setup-code")
            box.append(l)
        sc = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER)
        sc.add_css_class("pdf-pane")
        sc.set_child(box)
        return sc

    def build_help(self):
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.help_search = Gtk.SearchEntry(placeholder_text="Befehl suchen: z. B. Bruch, fett, Pfeil, Bild …")
        self.help_search.add_css_class("pb")
        self.help_search.set_margin_bottom(6)
        self.help_search.connect("search-changed", lambda *_: self.fill_help())
        outer.append(self.help_search)
        sc = Gtk.ScrolledWindow(vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER)
        sc.add_css_class("pdf-pane")
        self.help_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.help_box.add_css_class("help")
        sc.set_child(self.help_box)
        outer.append(sc)
        self.fill_help()
        return outer

    def fill_help(self):
        box = self.help_box
        while (c := box.get_first_child()):
            box.remove(c)
        q = self.help_search.get_text().strip().lower()

        def head(t):
            h = Gtk.Label(label=t, xalign=0)
            h.add_css_class("help-h")
            box.append(h)
        if q:
            hits = [c for c in ld.COMMANDS if q in c[0].lower() or q in c[2].lower() or q in c[3].lower()]
            hits += [("\\begin{" + e[0] + "}", ld.env_snippet(e[0]), e[2], "Umgebung", e[3]) for e in ld.ENVIRONMENTS
                     if q in e[0].lower() or q in e[2].lower()]
            for cat, items in ld.CHEATS:
                hits += [(i[0], i[1], i[2] or i[1].replace(F, "…").strip(), cat, i[3]) for i in items
                         if q in i[0].lower() and not any(h[1] == i[1] for h in hits)]
            head(f"{len(hits)} TREFFER – KLICK FÜGT EIN")
            for name, snip, desc, cat, pkg in hits[:60]:
                b = Gtk.Button(focus_on_click=False)
                b.add_css_class("wt")
                v = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
                n = Gtk.Label(label=name, xalign=0)
                n.add_css_class("cmp-name")
                d = Gtk.Label(label=desc + (f"  ·  braucht {pkg}" if pkg else ""), xalign=0, wrap=True)
                d.add_css_class("cmp-desc")
                v.append(n)
                v.append(d)
                b.set_child(v)
                b.connect("clicked", lambda _b, s=snip, p=pkg: self.insert_snippet(s, p))
                box.append(b)
            if not hits:
                box.append(Gtk.Label(label="Nichts gefunden. Probier ein anderes Wort.", xalign=0))
            return
        head("ANLEITUNG FÜR EINSTEIGER")
        for i, (title, text) in enumerate(ld.GUIDE):
            ex = Gtk.Expander(label=title, expanded=(i == 0 and not self.settings.get("guide_seen")))
            ex.set_child(self.guide_body(text))
            box.append(ex)
        self.settings["guide_seen"] = True
        for cat, items in ld.CHEATS:
            head(f"SPICKZETTEL · {cat.upper()}")
            flow = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, max_children_per_line=8, min_children_per_line=1,
                               column_spacing=4, row_spacing=4)
            flow.add_css_class("cheat")
            for text, snip, desc, pkg in items:
                b = Gtk.Button(label=text, focus_on_click=False)
                b.set_tooltip_text(snip.replace(F, "…").strip() + (f"\n{desc}" if desc else ""))
                b.connect("clicked", lambda _b, s=snip, p=pkg: self.insert_snippet(s, p))
                flow.append(b)
            box.append(flow)

    @staticmethod
    def guide_body(text):
        v = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, margin_start=8, margin_top=4, margin_bottom=6)
        para = []

        def flush():
            if para:
                l = Gtk.Label(label="\n".join(para), xalign=0, wrap=True)
                l.add_css_class("help-body")
                v.append(l)
                para.clear()
        for line in text.split("\n"):
            if line.startswith("  "):
                flush()
                l = Gtk.Label(label=line.strip(), xalign=0, selectable=True, wrap=True, wrap_mode=Pango.WrapMode.WORD_CHAR)
                l.add_css_class("setup-code")
                v.append(l)
            else:
                para.append(line)
        flush()
        return v

    def build_templates(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, valign=Gtk.Align.CENTER,
                      halign=Gtk.Align.CENTER, margin_start=20, margin_end=20)
        h = Gtk.Label(label="Womit möchtest du anfangen?")
        h.add_css_class("tpl-head")
        box.append(h)
        sub = Gtk.Label(label="Wähle eine Vorlage – oder tipp einfach los.", wrap=True)
        sub.add_css_class("tpl-sub")
        box.append(sub)
        flow = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, max_children_per_line=3, min_children_per_line=1,
                           column_spacing=10, row_spacing=10, homogeneous=True)
        for key, icon, title, desc, text in ld.TEMPLATES:
            b = Gtk.Button(focus_on_click=False)
            b.add_css_class("tpl")
            v = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            i = Gtk.Label(label=icon, xalign=0)
            i.add_css_class("tpl-icon")
            t = Gtk.Label(label=title, xalign=0)
            t.add_css_class("tpl-title")
            d = Gtk.Label(label=desc, xalign=0, wrap=True, max_width_chars=26, lines=2)
            d.add_css_class("tpl-sub")
            for w in (i, t, d):
                v.append(w)
            b.set_child(v)
            b.connect("clicked", lambda _b, tx=text, ti=title, k=key: self.use_template(tx, ti, k))
            flow.append(b)
        box.append(flow)
        sc = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER)
        sc.set_child(box)
        sc.set_visible(False)
        return sc

    def build_complete(self):
        self.cpop = Gtk.Popover(autohide=False, has_arrow=False, position=Gtk.PositionType.BOTTOM, can_focus=False)
        self.cpop.add_css_class("complete")
        self.cpop.set_parent(self.view)
        self.view.popovers.append(self.cpop)
        self.fpop = Gtk.Popover(autohide=False, has_arrow=True, position=Gtk.PositionType.TOP, can_focus=False)
        self.fpop.add_css_class("formula")
        fbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.fpic = Gtk.Picture(can_shrink=True)
        self.fhint = Gtk.Label(label="Formel-Vorschau", xalign=0)
        self.fhint.add_css_class("formula-hint")
        fbox.append(self.fpic)
        fbox.append(self.fhint)
        self.fpop.set_child(fbox)
        self.fpop.set_parent(self.view)
        self.view.popovers.append(self.fpop)
        self._formula_id, self._formula_key, self._formula_cache, self._formula_proc = None, None, {}, None
        v = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, can_focus=False)
        self.clist = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE, can_focus=False)
        self.clist.connect("row-activated", lambda lb, row: self.accept_complete(row.get_index()))
        self.csc = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER, propagate_natural_height=True,
                                      max_content_height=230, min_content_width=380, can_focus=False)
        self.csc.set_child(self.clist)
        v.append(self.csc)
        hint = Gtk.Label(label="Tab übernehmen · ↑↓ auswählen · Esc schließen", xalign=0)
        hint.add_css_class("cmp-hint")
        v.append(hint)
        self.cpop.set_child(v)

    # ================= Farben & Hervorhebung =================
    def new_buffer(self):
        """Ein Puffer je Datei – mit eigenen Tags, eigenem Rückgängig und denselben Hilfen."""
        b = Gtk.TextBuffer()
        self.bufs.append(b)
        self.make_tags(b)
        b.connect("changed", self.on_buffer_changed)
        b.connect("mark-set", self.on_mark_set)
        b.connect_after("insert-text", self.after_insert)
        b.connect_after("delete-range", lambda *_: self.cpop.get_visible() and
                        GLib.idle_add(lambda: self.show_complete() and False))
        if self.spell:
            self.spell.attach(b)
        return b

    def make_tags(self, b=None):
        b = b or self.buf
        for name in ("hl-cmd", "hl-env", "hl-math", "hl-comment", "hl-brace", "hl-arg"):
            b.create_tag(name)
        t = b.get_tag_table().lookup
        t("hl-env").props.weight = Pango.Weight.BOLD
        t("hl-comment").props.style = Pango.Style.ITALIC
        b.create_tag("hl-match", weight=Pango.Weight.BOLD)
        b.create_tag("hl-search")
        b.create_tag("hl-errline")
        if hasattr(self, "view"):
            self.refresh_colors()

    def refresh_colors(self):
        ctx = self.view.get_style_context()

        def col(names, fallback, alpha=1.0):
            for n in names:
                ok, c = ctx.lookup_color(n)
                if ok:
                    c.alpha = alpha
                    return c
            return rgba(fallback, alpha)
        self.colors = {"cmd": col(["color9", "primary"], "#8fcef3"),
                       "env": col(["tertiary", "color11"], "#cac1ea"),
                       "math": col(["secondary", "color10"], "#b5c9d7"),
                       "fg": col(["foreground"], "#dfe3e7"),
                       "dim": col(["foreground"], "#dfe3e7", 0.38)}
        for b in self.bufs:
            t = b.get_tag_table().lookup
            t("hl-cmd").props.foreground_rgba = self.colors["cmd"]
            t("hl-env").props.foreground_rgba = self.colors["env"]
            t("hl-math").props.foreground_rgba = self.colors["math"]
            t("hl-comment").props.foreground_rgba = col(["foreground"], "#dfe3e7", 0.42)
            t("hl-brace").props.foreground_rgba = col(["color9", "primary"], "#8fcef3", 0.6)
            t("hl-match").props.background_rgba = col(["color9", "primary"], "#8fcef3", 0.28)
            t("hl-search").props.background_rgba = rgba("#fdd663", 0.35)
            t("hl-errline").props.paragraph_background_rgba = rgba("#f28b82", 0.14)
        self.gutter.queue_draw() if hasattr(self, "gutter") else None

    TOKENS = re.compile(r"(?P<comment>(?<!\\)%[^\n]*)"
                        r"|(?P<env>\\(?:begin|end)\{[^}\n]*\})"
                        r"|(?P<dmath>\$\$.*?\$\$|\\\[.*?\\\]|\\\(.*?\\\))"
                        r"|(?P<math>(?<!\\)\$(?:\\.|[^$\\])+?\$)"
                        r"|(?P<cmd>\\(?:[A-Za-z@]+\*?|.))"
                        r"|(?P<brace>[{}\[\]])", re.S)

    def highlight(self):
        self._hl_id = None
        b = self.buf
        s, e = b.get_bounds()
        for name in ("hl-cmd", "hl-env", "hl-math", "hl-comment", "hl-brace"):
            b.remove_tag_by_name(name, s, e)
        text = b.get_text(s, e, False)

        def tag(name, a, z):
            b.apply_tag_by_name(name, b.get_iter_at_offset(a), b.get_iter_at_offset(z))
        for m in self.TOKENS.finditer(text):
            kind = m.lastgroup
            a, z = m.span()
            if kind == "comment":
                tag("hl-comment", a, z)
            elif kind == "env":
                k = text.index("{", a)
                tag("hl-cmd", a, k)
                tag("hl-env", k + 1, z - 1)
                tag("hl-brace", k, k + 1)
                tag("hl-brace", z - 1, z)
            elif kind in ("math", "dmath"):
                tag("hl-math", a, z)
                for c in re.finditer(r"\\[A-Za-z]+", m.group()):
                    tag("hl-cmd", a + c.start(), a + c.end())
            elif kind == "cmd":
                tag("hl-cmd", a, z)
            else:
                tag("hl-brace", a, z)
        self.match_braces()
        return False

    def match_braces(self):
        b = self.buf
        s, e = b.get_bounds()
        b.remove_tag_by_name("hl-match", s, e)
        it = b.get_iter_at_mark(b.get_insert())
        text = None
        for off in (it.get_offset(), it.get_offset() - 1):
            if off < 0:
                continue
            ch = b.get_iter_at_offset(off).get_char()
            if not ch or ch not in "{}[]":
                continue
            text = text or b.get_text(s, e, False)
            pair = {"{": "}", "[": "]", "}": "{", "]": "["}[ch]
            d = 1 if ch in "{[" else -1
            depth, i = 0, off
            while 0 <= i < len(text):
                c = text[i]
                if c in (ch, pair) and (i == 0 or text[i - 1] != "\\"):
                    depth += 1 if c == ch else -1
                    if depth == 0:
                        for x in (off, i):
                            b.apply_tag_by_name("hl-match", b.get_iter_at_offset(x), b.get_iter_at_offset(x + 1))
                        return
                i += d
            return

    # ================= Laden / Speichern =================
    def load(self, nid, text, title, source=None, proj=None):
        self.kill()
        self.save_files()
        self._loading = True
        self.nid, self.source, self.proj = nid, source, proj
        self.hide_complete()
        self.hide_formula()
        self.clear_fields()
        for name in [n for n in self.file_bufs if n != "main.tex"]:      # Zusatzdateien des alten Projekts
            b = self.file_bufs.pop(name)
            if b in self.bufs:
                self.bufs.remove(b)
        self.switch_file("main.tex", quiet=True)
        self.synctex = None
        self.main_buf.set_enable_undo(False)          # Laden soll nicht rückgängig zu machen sein
        self.main_buf.set_text(text)
        self.main_buf.set_enable_undo(True)
        self.main_buf.place_cursor(self.main_buf.get_start_iter())
        self.title.set_text(title)
        self._loading = False
        self.err_lines = set()
        self.set_problems([], "")
        self.highlight()
        self.update_templates()
        self.last_written = None
        self.set_state("idle", "Bereit")
        pdf = os.path.join(BUILD, nid, "main.pdf")
        if os.path.exists(pdf):
            self.preview.load(pdf)
        else:
            self.preview.clear()
        self.fill_file_tabs()
        if text.strip() and self.compilers and self.settings["live"]:
            self.schedule_compile(300)
        GLib.idle_add(lambda: self.view.scroll_to_iter(self.buf.get_start_iter(), 0, False, 0, 0) and False)

    def text(self):
        """Inhalt von main.tex (das, was notist speichert)."""
        s, e = self.main_buf.get_bounds()
        return self.main_buf.get_text(s, e, False)

    def cur_text(self):
        s, e = self.buf.get_bounds()
        return self.buf.get_text(s, e, False)

    def update_templates(self):
        self.templates.set_visible(not self.text().strip() and self.view.get_editable() and self.cur_file == "main.tex")

    # ================= Mehrere Dateien =================
    def build_file_tabs(self):
        self.tabs_box = Gtk.Box(spacing=2)
        self.tabs_box.add_css_class("file-tabs")
        self.tabs_rev = Gtk.Revealer(transition_type=Gtk.RevealerTransitionType.SLIDE_DOWN)
        self.tabs_rev.set_child(self.tabs_box)
        return self.tabs_rev

    def project_files(self):
        """Weitere .tex/.bib-Dateien im Projektordner."""
        if not self.nid:
            return []
        d = getattr(self, "proj", None) or os.path.join(FILES, self.nid)
        try:
            names = sorted(f for f in os.listdir(d) if f.endswith((".tex", ".bib")) and f != "main.tex")
        except OSError:
            names = []
        return names

    def fill_file_tabs(self):
        box = self.tabs_box
        while (c := box.get_first_child()):
            box.remove(c)
        files = ["main.tex"] + self.project_files()
        group = None
        for name in files:
            b = Gtk.ToggleButton(label=("󰙩 " if name.endswith(".bib") else "󰈙 ") + name, focus_on_click=False,
                                 active=name == self.cur_file)
            if group:
                b.set_group(group)
            group = group or b
            b.connect("toggled", lambda btn, n=name: btn.get_active() and n != self.cur_file and self.switch_file(n))
            for g in (Gtk.GestureClick(button=3), Gtk.GestureLongPress(touch_only=True)):
                g.connect("pressed", lambda g, *a, btn=b, n=name: self.file_tab_menu(btn, n, a[-2], a[-1]))
                b.add_controller(g)
            box.append(b)
        add_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        h = Gtk.Label(label="NEUE DATEI IM PROJEKT", xalign=0)
        h.add_css_class("wpop-head")
        add_box.append(h)
        entry = Gtk.Entry(placeholder_text="z. B. kapitel1", width_chars=22)
        entry.add_css_class("pb")
        add_box.append(entry)
        hint = Gtk.Label(xalign=0, wrap=True, max_width_chars=30,
                         label="Wird als .tex angelegt und in main.tex mit \\input{…} eingebunden. "
                               "Für Literatur: Name mit .bib")
        hint.add_css_class("tpl-sub")
        add_box.append(hint)
        mb, pop = popover_button("󰐕", "Weitere Datei anlegen (Kapitel, Literatur)", add_box)
        entry.connect("activate", lambda e: (pop.popdown(), self.new_file(e.get_text()), e.set_text("")))
        box.append(mb)
        if self.cur_file != "main.tex":
            rm = tool("󰆴", f"{self.cur_file} löschen", lambda *_: self.delete_file())
            box.append(Gtk.Box(hexpand=True))
            box.append(rm)
        self.tabs_rev.set_reveal_child(len(files) > 1 or bool(self.nid))

    def new_file(self, name):
        name = re.sub(r"[^A-Za-z0-9._-]", "", name.strip().replace(" ", "_"))
        if not name or not self.nid:
            return
        if not name.endswith((".tex", ".bib")):
            name += ".tex"
        path = os.path.join(self.project_dir(), name)
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as f:
                f.write(f"% {name} – wird in main.tex eingebunden\n\n" if name.endswith(".tex") else "")
        if name.endswith(".tex"):
            stem = name[:-4]
            main = self.text()
            if f"\\input{{{stem}}}" not in main and f"\\include{{{stem}}}" not in main:
                m = re.search(r"\\end\{document\}", main)
                if m:
                    it = self.main_buf.get_iter_at_offset(m.start())
                    self.main_buf.insert(it, f"\\input{{{stem}}}\n")
                    self.notify(f"\\input{{{stem}}} in main.tex ergänzt")
        self.switch_file(name)

    def file_tab_menu(self, btn, name, x, y):
        """Rechtsklick auf eine Projektdatei: öffnen, im Dateimanager zeigen, Pfad kopieren, löschen."""
        path = os.path.join(self.project_dir(), name)
        entries = [("󰏌  öffnen", lambda: self.switch_file(name) if name != self.cur_file else None)]
        if os.path.exists(path):
            entries += [None, ("󰉋  im dateimanager zeigen", lambda: self._show_in_files(path)),
                        ("󰅍  pfad kopieren", lambda: (btn.get_clipboard().set(path), self.notify("Pfad kopiert")))]
        if name != "main.tex":
            entries += [None, ("󰆴  löschen …", lambda: self.delete_file(name))]
        pop = Gtk.Popover(has_arrow=False)
        pop.add_css_class("home-menu")
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        for e in entries:
            if e is None:
                sep = Gtk.Box()
                sep.add_css_class("fm-line")
                box.append(sep)
                continue
            b = Gtk.Button(label=e[0], focus_on_click=False)
            b.add_css_class("hm-item")
            b.get_child().set_xalign(0)
            b.connect("clicked", lambda _b, cb=e[1]: (pop.popdown(), GLib.idle_add(lambda: (cb(), False)[1])))
            box.append(b)
        pop.set_child(box)
        # am Latex-Bereich aufhängen, nicht am Reiter: die Reiter werden beim Dateiwechsel neu gebaut
        ok, p = btn.compute_point(self, Graphene.Point().init(x, y))
        pop.set_parent(self)
        r = Gdk.Rectangle()
        r.x, r.y, r.width, r.height = (int(p.x), int(p.y), 1, 1) if ok else (0, 0, 1, 1)
        pop.set_pointing_to(r)
        pop.connect("closed", lambda q: GLib.idle_add(lambda: (q.get_parent() and q.unparent(), False)[1]))
        pop.popup()

    @staticmethod
    def _show_in_files(path):
        uri = Gio.File.new_for_path(path).get_uri()
        try:
            Gio.bus_get_sync(Gio.BusType.SESSION, None).call_sync(
                "org.freedesktop.FileManager1", "/org/freedesktop/FileManager1", "org.freedesktop.FileManager1",
                "ShowItems", GLib.Variant("(ass)", ([uri], "")), None, Gio.DBusCallFlags.NONE, 3000, None)
        except Exception:  # noqa: BLE001
            Gio.AppInfo.launch_default_for_uri(Gio.File.new_for_path(os.path.dirname(path)).get_uri(), None)

    def delete_file(self, name=None):
        """Projektdatei löschen – nach Rückfrage, und nur in den Papierkorb (lässt sich zurückholen)."""
        name = name or self.cur_file
        if name == "main.tex":
            return
        dlg = Gtk.AlertDialog(message=i18n.tr("{} löschen?", name),
                              detail=i18n.tr("Die Datei wandert in den Papierkorb des Systems. Denk an das "
                                             "\\input in main.tex."),
                              buttons=[i18n.tr("Abbrechen"), i18n.tr("In den Papierkorb")],
                              cancel_button=0, default_button=0)

        def done(d, res):
            try:
                if d.choose_finish(res) == 1:
                    self._delete_file(name)
            except GLib.Error:
                pass
        dlg.choose(self.get_root(), None, done)

    def _delete_file(self, name):
        path = os.path.join(self.project_dir(), name)
        try:
            Gio.File.new_for_path(path).trash(None)
        except Exception:  # noqa: BLE001 – kein Papierkorb auf diesem Dateisystem
            try:
                os.remove(path)
            except OSError:
                pass
        b = self.file_bufs.pop(name, None)
        if b in self.bufs:
            self.bufs.remove(b)
        self._dirty_files.discard(name)
        if name == self.cur_file:
            self.switch_file("main.tex")
        else:
            self.fill_file_tabs()
        self.notify(f"{name} im Papierkorb – denk an das \\input in main.tex")

    def switch_file(self, name, quiet=False):
        if name not in self.file_bufs:
            b = self.new_buffer()
            try:
                with open(os.path.join(self.project_dir(), name), encoding="utf-8", errors="replace") as f:
                    content = f.read()
            except OSError:
                content = ""
            self._loading = True
            b.set_enable_undo(False)
            b.set_text(content)
            b.set_enable_undo(True)
            b.place_cursor(b.get_start_iter())
            self._loading = False
            self.file_bufs[name] = b
        self.hide_complete()
        self.hide_formula()
        self.clear_fields()
        self.cur_file = name
        self.buf = self.file_bufs[name]
        self.view.set_buffer(self.buf)
        self.highlight()
        self.apply_err_lines()
        self.update_templates()
        self.gutter.queue_resize()
        if not quiet:
            self.fill_file_tabs()
            self.view.grab_focus()
        if self.spell:
            self.spell.queue(0)

    def save_files(self):
        """Geänderte Zusatzdateien auf die Platte schreiben (main.tex speichert notist selbst)."""
        if self._save_files_id:
            GLib.source_remove(self._save_files_id)
            self._save_files_id = None
        for name in list(self._dirty_files):
            b = self.file_bufs.get(name)
            if b is not None and self.nid:
                s, e = b.get_bounds()
                try:
                    with open(os.path.join(self.project_dir(), name), "w", encoding="utf-8") as f:
                        f.write(b.get_text(s, e, False))
                except OSError:
                    pass
        self._dirty_files.clear()
        return False

    def use_template(self, text, title, key=None):
        self.buf.begin_user_action()
        self.buf.set_text("")
        self.buf.end_user_action()
        self.insert_snippet(text)
        if not self.title.get_text().strip() and key != "artikel" and title != "Einfaches Dokument":
            self.title.set_text(title)
        self.view.grab_focus()
        self.compile()

    def set_editable(self, on):
        self.view.set_editable(on)
        self.view.set_cursor_visible(on)
        self.title.set_editable(on)
        self.update_templates()

    def focus_text(self):
        self.view.grab_focus()

    def on_buffer_changed(self, buf):
        if buf is not self.buf:
            return
        if self._hl_id:
            GLib.source_remove(self._hl_id)
        self._hl_id = GLib.timeout_add(120, self.highlight)
        self.gutter.queue_resize()
        self.gutter.queue_draw()
        if self._loading:
            return
        self.update_templates()
        if buf is self.main_buf:
            self.on_change()
        else:
            self._dirty_files.add(self.cur_file)
            if self._save_files_id:
                GLib.source_remove(self._save_files_id)
            self._save_files_id = GLib.timeout_add(600, self.save_files)
        if self.settings["live"]:
            self.schedule_compile()

    def on_mark_set(self, buf, it, mark):
        if mark.get_name() != "insert":
            return
        self.gutter.queue_draw()
        if self._ctx_id:
            GLib.source_remove(self._ctx_id)
        self._ctx_id = GLib.timeout_add(60, self.update_context)

    def update_context(self):
        """Statuszeile: Zeile/Spalte und eine kurze Erklärung zum Befehl unter dem Cursor."""
        self._ctx_id = None
        self.match_braces()
        if self.cpop.get_visible() and not self.context_prefix():
            self.hide_complete()
        self.update_formula()
        it = self.buf.get_iter_at_mark(self.buf.get_insert())
        self.pos_label.set_label(f"Z. {it.get_line() + 1}, Sp. {it.get_line_offset() + 1}")
        ls = it.copy()
        ls.set_line_offset(0)
        le = it.copy()
        if not le.ends_line():
            le.forward_to_line_end()
        line, col = self.buf.get_text(ls, le, False), it.get_line_offset()
        name = desc = None
        for m in re.finditer(r"\\(begin|end)\{([^}]*)\}?|\\[A-Za-z@]+\*?|\\\[|\\\(", line):
            if m.start() <= col <= m.end():
                if m.group(1):
                    env = ld.ENV_INFO.get(m.group(2))
                    name, desc = f"{m.group(2)}", env[2] if env else "Umgebung"
                else:
                    c = ld.CMD_INFO.get(m.group()) or ld.CMD_INFO.get(m.group().rstrip("*"))
                    if c:
                        name, desc = c[0], c[2] + (f"  ·  Paket {c[4]}" if c[4] else "")
                    elif m.group() in ("\\[", "\\("):
                        name, desc = m.group(), "Beginn einer Formel"
                break
        if not name:
            env = self.enclosing_env(it)
            if env:
                info = ld.ENV_INFO.get(env)
                name, desc = f"in {env}", info[2] if info else ""
        self.ctx_cmd.set_label(name or "")
        self.ctx_text.set_label(desc or "")
        return False

    def enclosing_env(self, it):
        before = self.buf.get_text(self.buf.get_start_iter(), it, False)
        stack = []
        for m in re.finditer(r"(?<!\\)%[^\n]*|\\(begin|end)\{([^}]*)\}", before):
            if m.group(1) == "begin":
                stack.append(m.group(2))
            elif m.group(1) == "end" and stack and stack[-1] == m.group(2):
                stack.pop()
        while stack and stack[-1] == "document":
            stack.pop()
        return stack[-1] if stack else None

    # ================= Tastatur =================
    def on_key(self, ctrl, keyval, code, state):
        ctrl_on = state & Gdk.ModifierType.CONTROL_MASK
        shift = state & Gdk.ModifierType.SHIFT_MASK
        popup = self.cpop.get_visible()
        if keyval == Gdk.KEY_F1 and not ctrl_on:
            self.open_overview()
            return True
        if ctrl_on:
            if keyval in (Gdk.KEY_s, Gdk.KEY_Return, Gdk.KEY_KP_Enter):
                self.compile(manual=True)
                return True
            if keyval == Gdk.KEY_space:
                self.show_complete(manual=True)
                return True
            if keyval in (Gdk.KEY_m, Gdk.KEY_M):
                self.insert_snippet("$" + F + "$")
                return True
            if keyval in (Gdk.KEY_7, Gdk.KEY_slash, Gdk.KEY_numbersign):
                self.toggle_comment()
                return True
            if keyval in (Gdk.KEY_j, Gdk.KEY_J):
                self.forward_search()
                return True
            return False
        if popup:
            if keyval in (Gdk.KEY_Down, Gdk.KEY_Up):
                self.move_complete(1 if keyval == Gdk.KEY_Down else -1)
                return True
            if keyval in (Gdk.KEY_Page_Down, Gdk.KEY_Page_Up):
                self.move_complete(6 if keyval == Gdk.KEY_Page_Down else -6)
                return True
            if keyval in (Gdk.KEY_Tab, Gdk.KEY_ISO_Left_Tab) or \
                    (keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter) and self._navigated):
                row = self.clist.get_selected_row()
                self.accept_complete(row.get_index() if row else 0)
                return True
            if keyval == Gdk.KEY_Escape:
                self.hide_complete()
                return True
        if keyval == Gdk.KEY_Escape and self.fields:
            self.clear_fields()
            return True
        if keyval == Gdk.KEY_Tab and not shift:
            if self.buf.get_has_selection():
                self.indent_lines(1)
            elif not self.next_field():
                self.buf.insert_at_cursor("  ")
            return True
        if keyval == Gdk.KEY_ISO_Left_Tab:
            self.indent_lines(-1)
            return True
        if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter) and not shift:
            return self.on_enter()
        if self.settings["autoclose"] and not self.buf.get_has_selection():
            nxt = self.buf.get_iter_at_mark(self.buf.get_insert()).get_char()
            if keyval == Gdk.KEY_braceright and nxt == "}":
                it = self.buf.get_iter_at_mark(self.buf.get_insert())
                it.forward_char()
                self.buf.place_cursor(it)
                return True
            if keyval == Gdk.KEY_BackSpace:
                it = self.buf.get_iter_at_mark(self.buf.get_insert())
                prev = it.copy()
                if prev.backward_char() and prev.get_char() == "{" and nxt == "}":
                    end = it.copy()
                    end.forward_char()
                    self.buf.delete(prev, end)
                    return True
        if keyval == Gdk.KEY_braceleft and self.settings["autoclose"]:
            b = self.buf.get_selection_bounds()
            if b:
                sel = self.buf.get_text(b[0], b[1], False)
                self.buf.begin_user_action()
                self.buf.delete(b[0], b[1])
                self.buf.insert_at_cursor("{" + sel + "}")
                self.buf.end_user_action()
                return True
            nxt = self.buf.get_iter_at_mark(self.buf.get_insert()).get_char()
            if nxt in ("", " ", "\n", "}", ")", "]", "$", "\t") or nxt == "\0":
                self.buf.begin_user_action()
                self.buf.insert_at_cursor("{}")
                it = self.buf.get_iter_at_mark(self.buf.get_insert())
                it.backward_char()
                self.buf.place_cursor(it)
                self.buf.end_user_action()
                GLib.idle_add(lambda: self.maybe_complete() and False)
                return True
        return False

    def on_enter(self):
        self.hide_complete()
        it = self.buf.get_iter_at_mark(self.buf.get_insert())
        ls = it.copy()
        ls.set_line_offset(0)
        le = it.copy()
        if not le.ends_line():
            le.forward_to_line_end()
        before, after = self.buf.get_text(ls, it, False), self.buf.get_text(it, le, False)
        indent = re.match(r"\s*", before).group()
        m = re.match(r"^(\s*)\\begin\{([^}]+)\}(\[[^\]]*\]|\{[^}]*\})*\s*$", before)
        if m and not after.strip() and self.needs_end(m.group(2), it):
            name = m.group(2)
            inner = indent + "  " + ("\\item " if name in LIST_ENVS else "")
            self.buf.begin_user_action()
            self.buf.insert_at_cursor("\n" + inner)
            mark = self.buf.create_mark(None, self.buf.get_iter_at_mark(self.buf.get_insert()), True)
            self.buf.insert_at_cursor(f"\n{indent}\\end{{{name}}}")
            self.buf.place_cursor(self.buf.get_iter_at_mark(mark))
            self.buf.delete_mark(mark)
            self.buf.end_user_action()
            self.view.scroll_mark_onscreen(self.buf.get_insert())
            return True
        if self.settings["lists"]:
            m = re.match(r"^(\s*)\\item(\[[^\]]*\])?\s*(.*)$", before)
            if m and self.enclosing_env(it) in LIST_ENVS:
                if not m.group(3).strip() and not after.strip():      # leerer Punkt: Liste verlassen
                    self.buf.begin_user_action()
                    self.buf.delete(ls, le)
                    self.buf.end_user_action()
                    return True
                self.buf.insert_at_cursor("\n" + m.group(1) + "\\item ")
                self.view.scroll_mark_onscreen(self.buf.get_insert())
                return True
        if indent:
            self.buf.insert_at_cursor("\n" + indent)
            self.view.scroll_mark_onscreen(self.buf.get_insert())
            return True
        return False

    def needs_end(self, name, it):
        rest = self.buf.get_text(it, self.buf.get_end_iter(), False)
        esc = re.escape(name)
        opens = len(re.findall(r"\\begin\{" + esc + r"\}", rest))
        closes = len(re.findall(r"\\end\{" + esc + r"\}", rest))
        return closes <= opens

    def indent_lines(self, d):
        b = self.buf.get_selection_bounds()
        if b:
            first, last = b[0].get_line(), b[1].get_line()
            if b[1].starts_line() and last > first:
                last -= 1
        else:
            first = last = self.buf.get_iter_at_mark(self.buf.get_insert()).get_line()
        self.buf.begin_user_action()
        for ln in range(first, last + 1):
            ok, it = self.buf.get_iter_at_line(ln)
            if d > 0:
                self.buf.insert(it, "  ")
            else:
                e = it.copy()
                n = 0
                while n < 2 and e.get_char() == " ":
                    e.forward_char()
                    n += 1
                self.buf.delete(it, e)
        self.buf.end_user_action()

    def toggle_comment(self):
        b = self.buf.get_selection_bounds()
        if b:
            first, last = b[0].get_line(), b[1].get_line()
            if b[1].starts_line() and last > first:
                last -= 1
        else:
            first = last = self.buf.get_iter_at_mark(self.buf.get_insert()).get_line()
        lines = []
        for ln in range(first, last + 1):
            ok, s = self.buf.get_iter_at_line(ln)
            e = s.copy()
            if not e.ends_line():
                e.forward_to_line_end()
            lines.append(self.buf.get_text(s, e, False))
        uncomment = all(l.lstrip().startswith("%") or not l.strip() for l in lines)
        self.buf.begin_user_action()
        for ln, l in zip(range(first, last + 1), lines):
            ok, s = self.buf.get_iter_at_line(ln)
            if uncomment:
                m = re.match(r"(\s*)% ?", l)
                if m:
                    a = s.copy()
                    a.forward_chars(len(m.group(1)))
                    z = s.copy()
                    z.forward_chars(m.end())
                    self.buf.delete(a, z)
            elif l.strip():
                self.buf.insert(s, "% ")
        self.buf.end_user_action()

    # ================= Schnipsel =================
    def insert_snippet(self, snippet, pkg=None):
        if not self.view.get_editable():
            return
        b = self.buf
        self.hide_complete()
        b.begin_user_action()
        sel = ""
        bounds = b.get_selection_bounds()
        if bounds:
            sel = b.get_text(bounds[0], bounds[1], False)
            b.delete(bounds[0], bounds[1])
        it = b.get_iter_at_mark(b.get_insert())
        ls = it.copy()
        ls.set_line_offset(0)
        indent = re.match(r"\s*", b.get_text(ls, it, False)).group()
        snippet = snippet.replace("\n", "\n" + indent) if indent else snippet
        if snippet.endswith("\n" + indent) and indent:
            snippet = snippet[:-len(indent)]
        parts = snippet.split(F)
        start = it.get_offset()
        text, offs = "", []
        for i, p in enumerate(parts):
            if i:
                offs.append(start + len(text))
                if i == 1 and sel:
                    text += sel
            text += p
        b.insert(it, text)
        self.clear_fields()
        if offs:
            first = offs[0] + (len(sel) if sel else 0)
            self.fields = [b.create_mark(None, b.get_iter_at_offset(o), True) for o in offs[1:]]
            b.place_cursor(b.get_iter_at_offset(first))
        b.end_user_action()
        if pkg:
            self.ensure_package(pkg)
        self.view.grab_focus()
        self.view.scroll_mark_onscreen(b.get_insert())

    def next_field(self):
        while self.fields:
            m = self.fields.pop(0)
            if m.get_deleted():
                continue
            self.buf.place_cursor(self.buf.get_iter_at_mark(m))
            self.buf.delete_mark(m)
            self.view.scroll_mark_onscreen(self.buf.get_insert())
            return True
        return False

    def clear_fields(self):
        for m in self.fields:
            if not m.get_deleted():
                self.buf.delete_mark(m)
        self.fields = []

    def wrap(self, cmd):
        self.insert_snippet("\\" + cmd + "{" + F + "}" + F)

    def ensure_package(self, pkg):
        text = self.text()
        if re.search(r"\\usepackage(\[[^\]]*\])?\{[^}]*\b" + re.escape(pkg) + r"\b[^}]*\}", text):
            return
        if "\\documentclass" not in text or re.search(r"\\documentclass(\[[^\]]*\])?\{beamer\}", text) and pkg == "hyperref":
            return
        m = list(re.finditer(r"^\\usepackage.*$", text, re.M))
        if m:
            pos = m[-1].end()
        else:
            dc = re.search(r"^\\documentclass.*$", text, re.M)
            pos = dc.end() if dc else 0
        it = self.main_buf.get_iter_at_offset(pos)
        self.main_buf.begin_user_action()
        self.main_buf.insert(it, f"\n\\usepackage{{{pkg}}}")
        self.main_buf.end_user_action()
        self.notify(f"\\usepackage{{{pkg}}} in main.tex ergänzt – wird für diesen Befehl gebraucht")

    def insert_table(self, rows, cols):
        head = " & ".join(F + f"Spalte {c + 1}" if c == 0 else f"Spalte {c + 1}" for c in range(cols))
        body = "\n".join("    " + " & ".join(" " for _ in range(cols)).strip() + " \\\\" for _ in range(max(0, rows - 1)))
        snip = ("\\begin{table}[htbp]\n  \\centering\n  \\begin{tabular}{" + "l" * cols + "}\n    \\hline\n    " + head +
                " \\\\\n    \\hline\n" + (body + "\n" if body else "") + "    \\hline\n  \\end{tabular}\n  \\caption{" + F +
                "Beschriftung}\n\\end{table}\n")
        self.insert_snippet(snip)

    def pick_image(self):
        if not self.nid:
            return
        dlg = Gtk.FileDialog(title="Bild einfügen")
        f = Gtk.FileFilter()
        f.set_name("Bilder (PNG, JPG, PDF)")
        for p in ("*.png", "*.jpg", "*.jpeg", "*.pdf", "*.PNG", "*.JPG", "*.JPEG"):
            f.add_pattern(p)
        store = Gio.ListStore.new(Gtk.FileFilter)
        store.append(f)
        dlg.set_filters(store)

        def done(d, res):
            try:
                path = d.open_finish(res).get_path()
            except GLib.Error:
                return
            self.add_image(path)
        dlg.open(self.win, None, done)

    def add_image(self, path):
        folder = self.project_dir()
        name = re.sub(r"[^A-Za-z0-9._-]", "_", os.path.basename(path))
        base, ext = os.path.splitext(name)
        dest, i = os.path.join(folder, name), 1
        while os.path.exists(dest) and not os.path.samefile(dest, path):
            name = f"{base}-{i}{ext}"
            dest = os.path.join(folder, name)
            i += 1
        if not os.path.exists(dest):
            shutil.copy2(path, dest)
        snip = ("\\begin{figure}[htbp]\n  \\centering\n  \\includegraphics[width=0.8\\textwidth]{" + name + "}\n"
                "  \\caption{" + F + "Bildunterschrift}\n  \\label{fig:" + re.sub(r"\W", "", base) + "}\n\\end{figure}\n")
        self.insert_snippet(snip, "graphicx")

    def project_dir(self):
        """Projektordner: bei Dateien aus notists Ordner deren eigener Ordner, sonst intern je Dokument."""
        d = getattr(self, "proj", None) or os.path.join(FILES, self.nid)
        os.makedirs(d, exist_ok=True)
        return d

    def set_project(self, proj, source):
        """Projektordner wurde umbenannt (Titel geändert)."""
        self.proj, self.source = proj, source

    # ================= Vorschläge =================
    def after_insert(self, buf, loc, text, length):
        if self._loading or length != 1:
            return
        if text.isalpha() or text in "\\{":
            GLib.idle_add(lambda: self.maybe_complete() and False)
        elif self.cpop.get_visible():
            self.hide_complete()

    def context_prefix(self):
        it = self.buf.get_iter_at_mark(self.buf.get_insert())
        ls = it.copy()
        ls.set_line_offset(0)
        before = self.buf.get_text(ls, it, False)
        m = re.search(r"\\(begin|end)\{([A-Za-z*]*)$", before)
        if m:
            return ("env-" + m.group(1), m.group(2), len(m.group(0)))
        m = re.search(r"\\usepackage(\[[^\]]*\])?\{([A-Za-z,]*)$", before)
        if m:
            word = m.group(2).split(",")[-1]
            return ("pkg", word, len(word))
        m = re.search(r"\\(?:cite|citep|citet|nocite|autocite|parencite|textcite)(?:\[[^\]]*\])*\{([^{}]*)$", before)
        if m:
            word = m.group(1).split(",")[-1].strip()
            return ("cite", word, len(word))
        m = re.search(r"\\(?:ref|eqref|autoref|pageref|nameref|cref)\{([^{}]*)$", before)
        if m:
            return ("ref", m.group(1), len(m.group(1)))
        m = re.search(r"\\[A-Za-z]*$", before)
        if m:
            return ("cmd", m.group(), len(m.group()))
        return None

    def maybe_complete(self):
        if self.settings["hints"]:
            self.show_complete()
        elif self.cpop.get_visible():
            self.show_complete(manual=True)

    def show_complete(self, manual=False):
        ctx = self.context_prefix()
        if not ctx or not self.view.get_editable():
            self.hide_complete()
            return
        kind, word, _ = ctx
        lw = word.lower()
        if kind == "cmd":
            if not manual and len(word) < 2:     # nur "\" getippt: noch nichts zeigen
                self.hide_complete()
                return
            names = [c for c in ld.COMMANDS if c[0].startswith(word)]
            names += [c for c in ld.COMMANDS if c not in names and c[0].lower().startswith(lw)]
            names += [c for c in ld.COMMANDS if c not in names and len(lw) > 2 and lw[1:] in c[0].lower()]
            if word.startswith("\\b") and "\\begin".startswith(word):
                names.insert(0, ("\\begin", "\\begin{" + F + "}", "Umgebung beginnen – Name eingeben, dann Enter", "", None))
            cands = [(c[0], c[1], c[2], c[4]) for c in names]
            if len(cands) == 1 and cands[0][0] == word and not manual:
                cands = []
        elif kind == "pkg":
            cands = [(p, p, d, None) for p, d in PACKAGES if p.startswith(lw)]
        elif kind == "cite":
            cands = [(e["key"], e["key"], tx.describe_bib(e) or "Quelle", None) for e in self.bib_entries()
                     if lw in e["key"].lower() or lw in tx.describe_bib(e).lower()]
            if not cands and manual:
                cands = [("(keine Quellen)", "", "Über „Quellen“ in der Werkzeugleiste anlegen", None)]
        elif kind == "ref":
            cands = [(k, k, d, None) for k, d in self.labels() if lw in k.lower()]
        else:
            envs = [e for e in ld.ENVIRONMENTS if e[0].startswith(word)] + \
                   [e for e in ld.ENVIRONMENTS if not e[0].startswith(word) and lw in e[0]]
            cands = [(e[0], e[0], e[2], e[3]) for e in envs]
        if not cands:
            self.hide_complete()
            return
        self.cands = cands[:40]
        self._navigated = False
        while (r := self.clist.get_first_child()):
            self.clist.remove(r)
        for name, snip, desc, pkg in self.cands:
            row = Gtk.ListBoxRow(can_focus=False)
            v = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            top = Gtk.Box(spacing=8)
            n = Gtk.Label(label=name, xalign=0)
            n.add_css_class("cmp-name")
            top.append(n)
            if pkg:
                p = Gtk.Label(label=pkg, xalign=1, hexpand=True)
                p.add_css_class("cmp-pkg")
                top.append(p)
            v.append(top)
            d = Gtk.Label(label=desc, xalign=0, ellipsize=Pango.EllipsizeMode.END, max_width_chars=50)
            d.add_css_class("cmp-desc")
            v.append(d)
            row.set_child(v)
            self.clist.append(row)
        self.clist.select_row(self.clist.get_row_at_index(0))
        it = self.buf.get_iter_at_mark(self.buf.get_insert())
        r = self.view.get_iter_location(it)
        x, y = self.view.buffer_to_window_coords(Gtk.TextWindowType.WIDGET, r.x, r.y)
        rect = Gdk.Rectangle()
        rect.x, rect.y, rect.width, rect.height = x, y, 1, r.height
        self.cpop.set_pointing_to(rect)
        if not self.cpop.get_visible():
            self.cpop.popup()
            self.view.grab_focus()
        self.cpop.present()

    def hide_complete(self):
        if self.cpop.get_visible():
            self.cpop.popdown()

    def move_complete(self, d):
        row = self.clist.get_selected_row()
        i = (row.get_index() if row else 0) + d
        i = max(0, min(len(self.cands) - 1, i))
        r = self.clist.get_row_at_index(i)
        self.clist.select_row(r)
        self._navigated = True
        adj = self.csc.get_vadjustment()
        ok, rect = r.compute_bounds(self.clist)
        if ok:
            y, h = rect.get_y(), rect.get_height()
            if y < adj.get_value():
                adj.set_value(y)
            elif y + h > adj.get_value() + adj.get_page_size():
                adj.set_value(y + h - adj.get_page_size())

    def accept_complete(self, i):
        ctx = self.context_prefix()
        if not ctx or i >= len(self.cands):
            self.hide_complete()
            return
        kind, word, n = ctx
        name, snip, desc, pkg = self.cands[i]
        it = self.buf.get_iter_at_mark(self.buf.get_insert())
        start = it.copy()
        start.backward_chars(n if kind not in ("pkg", "cite") else len(word))
        # bereits automatisch geschlossene "}" hinter dem Cursor mit ersetzen
        end = it.copy()
        if kind in ("env-begin", "env-end", "pkg", "cite", "ref") and end.get_char() == "}":
            end.forward_char()
        if kind in ("cite", "ref") and not snip:
            self.hide_complete()
            return
        self.buf.begin_user_action()
        self.buf.delete(start, end)
        self.buf.place_cursor(start)
        self.buf.end_user_action()
        if kind == "env-begin":
            self.insert_snippet(ld.env_snippet(name).rstrip("\n"), pkg)
        elif kind == "env-end":
            self.insert_snippet(f"\\end{{{name}}}")
        elif kind in ("pkg", "cite", "ref"):
            self.insert_snippet(name + "}")
        else:
            self.insert_snippet(snip, pkg)
        self.hide_complete()

    def labels(self):
        """[(label, zeile mit dem Label)] aus allen Dateien des Projekts."""
        out = []
        texts = [self.text()] + [self.file_text(n) for n in self.project_files() if n.endswith(".tex")]
        for t in texts:
            for line in t.split("\n"):
                for m in re.finditer(r"\\label\{([^}]*)\}", line):
                    out.append((m.group(1), line.strip()[:70]))
        return out

    def file_text(self, name):
        b = self.file_bufs.get(name)
        if b is not None:
            s, e = b.get_bounds()
            return b.get_text(s, e, False)
        try:
            with open(os.path.join(self.project_dir(), name), encoding="utf-8", errors="replace") as f:
                return f.read()
        except OSError:
            return ""

    def bib_entries(self):
        out = []
        for n in self.project_files():
            if n.endswith(".bib"):
                out += tx.parse_bib(self.file_text(n))
        for m in re.finditer(r"\\bibitem(?:\[[^\]]*\])?\{([^}]*)\}\s*([^\n]*)", self.text()):
            out.append({"key": m.group(1), "title": m.group(2)[:60], "type": "bibitem"})
        return out

    # ================= Formel-Vorschau =================
    def update_formula(self):
        if not self.settings.get("formula_preview", True) or not self.compilers or not self.view.has_focus():
            self.hide_formula()
            return
        it = self.buf.get_iter_at_mark(self.buf.get_insert())
        hit = tx.math_at(self.cur_text(), it.get_offset())
        if not hit:
            self.hide_formula()
            return
        start, end, formula = hit
        src = tx.formula_source(self.text(), formula)
        key = tx.formula_hash(src)
        self._formula_start = start
        if key == self._formula_key and self.fpop.get_visible():
            return
        self._formula_key = key
        if key in self._formula_cache:
            self.show_formula(*self._formula_cache[key])
            return
        if self._formula_id:
            GLib.source_remove(self._formula_id)
        self._formula_id = GLib.timeout_add(450, lambda: self.render_formula(key, src))

    def render_formula(self, key, src):
        self._formula_id = None
        if self._formula_proc:                    # immer nur eine Formel gleichzeitig
            self._formula_id = GLib.timeout_add(300, lambda: self.render_formula(key, src))
            return False
        d = os.path.join(BUILD, "formel", key)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "f.tex"), "w", encoding="utf-8") as f:
            f.write(src)

        def done(pdf, log):
            self._formula_proc = None
            tex = None
            if pdf and Poppler is not None:
                try:
                    doc = Poppler.Document.new_from_file(Gio.File.new_for_path(pdf).get_uri(), None)
                    page = doc.get_page(0)
                    pw, ph = page.get_size()
                    s = min(3.0, 520 / max(pw, 1)) * 2
                    W, H = max(1, int(pw * s)), max(1, int(ph * s))
                    img = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
                    cr = cairo.Context(img)
                    cr.set_source_rgb(1, 1, 1)
                    cr.paint()
                    cr.scale(s, s)
                    page.render(cr)
                    img.flush()
                    tex = (Gdk.MemoryTexture.new(W, H, Gdk.MemoryFormat.B8G8R8A8_PREMULTIPLIED,
                                                 GLib.Bytes.new(bytes(img.get_data())), img.get_stride()), W / 2, H / 2)
                except GLib.Error:
                    tex = None
            self._formula_cache[key] = tex or (None, 0, 0)
            if key == self._formula_key:
                self.show_formula(*self._formula_cache[key])
        self._formula_proc = True
        self.run_tex(d, "f.tex", done)
        return False

    def show_formula(self, tex, w, h):
        if tex is None:
            self.fpic.set_paintable(None)
            self.fpic.set_size_request(-1, -1)
            self.fhint.set_label("Formel noch unvollständig – oder ein Befehl fehlt")
        else:
            self.fpic.set_paintable(tex)
            self.fpic.set_size_request(int(w), int(h))
            self.fhint.set_label("Formel-Vorschau")
        it = self.buf.get_iter_at_offset(getattr(self, "_formula_start", 0))
        r = self.view.get_iter_location(it)
        x, y = self.view.buffer_to_window_coords(Gtk.TextWindowType.WIDGET, r.x, r.y)
        rect = Gdk.Rectangle()
        rect.x, rect.y, rect.width, rect.height = x, y, max(1, r.width), r.height
        self.fpop.set_pointing_to(rect)
        if not self.fpop.get_visible():
            self.fpop.popup()
            self.view.grab_focus()
        self.fpop.present()

    def hide_formula(self):
        if getattr(self, "_formula_id", None):
            GLib.source_remove(self._formula_id)
            self._formula_id = None
        if getattr(self, "fpop", None) and self.fpop.get_visible():
            self.fpop.popdown()
        self._formula_key = None

    def run_tex(self, workdir, texname, done):
        """Kleine Nebenaufgabe kompilieren (Formel, Spickzettel). done(pdf-pfad oder None, protokoll)."""
        if not self.compilers:
            done(None, "")
            return
        name, exe = self.compilers[0]
        if name == "latexmk":
            exe = shutil.which("pdflatex") or exe
            name = "pdflatex"
        cmd = compile_cmd(name, exe, workdir, main=texname)
        launcher = Gio.SubprocessLauncher.new(Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_MERGE |
                                              Gio.SubprocessFlags.STDIN_PIPE)
        launcher.set_cwd(workdir)
        try:
            proc = launcher.spawnv(cmd)
        except GLib.Error:
            done(None, "")
            return
        pdf = os.path.join(workdir, os.path.splitext(texname)[0] + ".pdf")
        t0 = time.time()

        def fin(p, res):
            try:
                _ok, out, _ = p.communicate_utf8_finish(res)
            except GLib.Error:
                out = ""
            okp = p.get_if_exited() and p.get_exit_status() == 0 and os.path.exists(pdf) and os.path.getmtime(pdf) >= t0 - 1
            done(pdf if okp else None, out or "")
        proc.communicate_utf8_async(None, None, fin)

    # ================= Befehlsübersicht =================
    def open_overview(self):
        w = getattr(self, "_overview", None)
        if w and w.get_visible():
            w.present()
            return
        self._overview = tx.CommandOverview(self.win, lambda s, p: self.insert_snippet(s, p), self.save_cheatsheet)
        self._overview.present()

    def save_cheatsheet(self):
        d = os.path.join(BUILD, "spickzettel")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "spickzettel.tex"), "w", encoding="utf-8") as f:
            f.write(tx.cheatsheet_source())
        self.notify("Spickzettel wird erstellt …")

        def done(pdf, log):
            if not pdf:
                self.notify("Spickzettel konnte nicht erstellt werden (Compiler-Protokoll prüfen)")
                return
            dlg = Gtk.FileDialog(title="Spickzettel speichern", initial_name="LaTeX-Spickzettel.pdf")

            def saved(dl, res):
                try:
                    shutil.copyfile(pdf, dl.save_finish(res).get_path())
                    self.notify("Spickzettel gespeichert")
                except (GLib.Error, OSError):
                    pass
            dlg.save(self.win, None, saved)
        self.run_tex(d, "spickzettel.tex", done)

    # ================= Tabellen-Editor =================
    def open_table_editor(self):
        text = self.cur_text()
        off = self.buf.get_iter_at_mark(self.buf.get_insert()).get_offset()
        rng = None
        for env in ("table", "tabular"):
            for m in re.finditer(r"\\begin\{" + env + r"\}.*?\\end\{" + env + r"\}\n?", text, re.S):
                if m.start() <= off <= m.end():
                    rng = (m.start(), m.end(), m.group(0))
                    break
            if rng:
                break
        parsed = tx.parse_tabular(rng[2]) if rng else None

        def apply(code, pkg):
            if rng:
                self.buf.begin_user_action()
                self.buf.delete(self.buf.get_iter_at_offset(rng[0]), self.buf.get_iter_at_offset(rng[1]))
                self.buf.place_cursor(self.buf.get_iter_at_offset(rng[0]))
                self.buf.insert_at_cursor(code)
                self.buf.end_user_action()
                if pkg:
                    self.ensure_package(pkg)
            else:
                self.insert_snippet(code, pkg)
        win = tx.TableEditor(self.win, apply, *(parsed or (None, None)), existing=bool(parsed))
        self._table_win = win
        if rng:
            cap = re.search(r"\\caption\{([^}]*)\}", rng[2])
            lab = re.search(r"\\label\{tab:([^}]*)\}", rng[2])
            win.caption.set_text(cap.group(1) if cap else "")
            win.label.set_text(lab.group(1) if lab else "")
            win.float_.set_active(rng[2].lstrip().startswith("\\begin{table}"))
            if "\\toprule" in rng[2]:
                win.lines.set_selected(1)
            elif "\\hline" not in rng[2]:
                win.lines.set_selected(2)
        win.present()

    # ================= Literatur =================
    def open_bib(self):
        if not self.nid:
            return
        win = Gtk.Window(title="Quellen & Literatur", transient_for=self.win, default_width=820, default_height=600)
        win.add_css_class("settings")
        win.add_css_class("pb-window")
        k = Gtk.EventControllerKey()
        k.connect("key-pressed", lambda c, kv, *_: kv == Gdk.KEY_Escape and (win.close() or True))
        win.add_controller(k)
        outer = Gtk.Box()
        import dialogs
        dialogs.chrome(win, win.get_title(), outer)
        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, hexpand=True)
        left.add_css_class("settings-page")
        h = Gtk.Label(label="Deine Quellen", xalign=0)
        h.add_css_class("set-h")
        left.append(h)
        sub = Gtk.Label(xalign=0, wrap=True, label="Gespeichert in literatur.bib im Projekt. „Zitieren“ setzt \\cite{…} "
                        "an die Cursorstelle – das Literaturverzeichnis baut LaTeX dann selbst.")
        sub.add_css_class("set-sub")
        left.append(sub)
        lst = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        sc = Gtk.ScrolledWindow(vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER)
        sc.set_child(lst)
        left.append(sc)
        outer.append(left)
        right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        right.add_css_class("settings-page")
        right.set_size_request(320, -1)
        h = Gtk.Label(label="Neue Quelle", xalign=0)
        h.add_css_class("set-h")
        right.append(h)
        typ = Gtk.DropDown.new_from_strings([l for _, l in tx.BIB_TYPES])
        right.append(typ)
        form = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        right.append(form)
        add = Gtk.Button(label="󰐕  Hinzufügen")
        add.add_css_class("pb")
        right.append(add)
        outer.append(right)
        entries = {}

        def build_form(*_):
            while (c := form.get_first_child()):
                form.remove(c)
            entries.clear()
            for key, label, ph in tx.BIB_FIELDS[tx.BIB_TYPES[typ.get_selected()][0]]:
                l = Gtk.Label(label=label, xalign=0)
                l.add_css_class("set-sub")
                e = Gtk.Entry(placeholder_text=ph)
                e.add_css_class("pb")
                form.append(l)
                form.append(e)
                entries[key] = e
        typ.connect("notify::selected", build_form)
        build_form()

        def fill():
            while (c := lst.get_first_child()):
                lst.remove(c)
            items = [e for e in self.bib_entries() if e.get("type") != "bibitem"]
            if not items:
                l = Gtk.Label(label="Noch keine Quellen – rechts die erste anlegen.", xalign=0)
                l.add_css_class("set-sub")
                lst.append(l)
            for e in items:
                row = Gtk.Box(spacing=8)
                row.add_css_class("bib-row")
                v = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True)
                kl = Gtk.Label(label=e["key"], xalign=0)
                kl.add_css_class("bib-key")
                dl = Gtk.Label(label=tx.describe_bib(e), xalign=0, wrap=True)
                v.append(kl)
                v.append(dl)
                row.append(v)
                b = Gtk.Button(label="Zitieren", valign=Gtk.Align.CENTER)
                b.add_css_class("pb"); b.add_css_class("small")
                b.connect("clicked", lambda *_, k=e["key"]: (self.insert_snippet(f"\\cite{{{k}}}"), win.close()))
                row.append(b)
                lst.append(row)

        def do_add(*_):
            data = {k: e.get_text().strip() for k, e in entries.items()}
            if not data.get("title") and not data.get("author"):
                return
            data["type"] = tx.BIB_TYPES[typ.get_selected()][0]
            data["key"] = tx.bib_key(data, {e["key"] for e in self.bib_entries()})
            name = next((n for n in self.project_files() if n.endswith(".bib")), "literatur.bib")
            old = self.file_text(name)
            new = (old.rstrip() + "\n\n" if old.strip() else "") + tx.bib_entry(data)
            with open(os.path.join(self.project_dir(), name), "w", encoding="utf-8") as f:
                f.write(new)
            b = self.file_bufs.get(name)
            if b is not None:
                self._loading = True
                b.set_text(new)
                self._loading = False
            self.ensure_bibliography(name[:-4])
            for e in entries.values():
                e.set_text("")
            fill()
            self.fill_file_tabs()
            self.notify(f"Quelle „{data['key']}“ angelegt")
        add.connect("clicked", do_add)
        fill()
        win.present()

    def ensure_bibliography(self, stem):
        text = self.text()
        if "\\bibliography{" in text or "\\printbibliography" in text or "\\addbibresource" in text:
            return
        m = re.search(r"\\end\{document\}", text)
        if not m:
            return
        it = self.main_buf.get_iter_at_offset(m.start())
        self.main_buf.insert(it, f"\\bibliographystyle{{plain}}\n\\bibliography{{{stem}}}\n\n")
        self.notify("Literaturverzeichnis am Ende von main.tex ergänzt")

    # ================= Suchen / Springen =================
    def show_find(self):
        self.findrev.set_reveal_child(True)
        b = self.buf.get_selection_bounds()
        if b:
            self.find_entry.set_text(self.buf.get_text(b[0], b[1], False))
        self.find_entry.grab_focus()
        self.run_search()

    def hide_find(self):
        self.findrev.set_reveal_child(False)
        s, e = self.buf.get_bounds()
        self.buf.remove_tag_by_name("hl-search", s, e)
        self.view.grab_focus()

    def run_search(self):
        s, e = self.buf.get_bounds()
        self.buf.remove_tag_by_name("hl-search", s, e)
        q = self.find_entry.get_text()
        self.hits = []
        if q:
            text = self.text().lower()
            i = text.find(q.lower())
            while i >= 0 and len(self.hits) < 2000:
                self.hits.append(i)
                self.buf.apply_tag_by_name("hl-search", self.buf.get_iter_at_offset(i),
                                           self.buf.get_iter_at_offset(i + len(q)))
                i = text.find(q.lower(), i + 1)
        self.find_info.set_label(f"{len(self.hits)} Treffer" if q else "")
        if self.hits:
            self.find_step(0)

    def find_step(self, d):
        hits = getattr(self, "hits", None)
        if not hits:
            return
        b = self.buf.get_selection_bounds()
        pos = b[0].get_offset() if b else self.buf.get_iter_at_mark(self.buf.get_insert()).get_offset()
        if d > 0:
            nxt = next((h for h in hits if h > pos), hits[0])
        elif d < 0:
            nxt = next((h for h in reversed(hits) if h < pos), hits[-1])
        else:
            nxt = next((h for h in hits if h >= pos), hits[0])
        n = len(self.find_entry.get_text())
        a, z = self.buf.get_iter_at_offset(nxt), self.buf.get_iter_at_offset(nxt + n)
        self.buf.select_range(a, z)
        self.view.scroll_to_iter(a, 0.2, False, 0, 0)
        self.find_info.set_label(f"{hits.index(nxt) + 1} / {len(hits)}")

    def goto_line(self, line, file=None):
        if file and file != self.cur_file and (file == "main.tex" or file in self.project_files()):
            self.switch_file(file)
        ok, it = self.buf.get_iter_at_line(max(0, line - 1))
        self.buf.place_cursor(it)
        self.view.scroll_to_iter(it, 0.25, True, 0, 0.3)
        self.view.grab_focus()

    def fill_outline(self):
        box = self.outline_box
        while (c := box.get_first_child()):
            box.remove(c)
        head = Gtk.Label(label="GLIEDERUNG", xalign=0)
        head.add_css_class("wpop-head")
        box.append(head)
        levels = {"part": 0, "chapter": 0, "section": 1, "subsection": 2, "subsubsection": 3, "frametitle": 2}
        n = 0
        for i, line in enumerate(self.text().split("\n")):
            m = re.match(r"\s*\\(part|chapter|section|subsection|subsubsection)\*?\{(.*)\}", line) or \
                re.match(r"\s*\\begin\{frame\}\{(.*)\}()", line)
            if not m:
                continue
            kind, title = (m.group(1), m.group(2)) if m.lastindex == 2 and m.group(1) in levels else ("frametitle", m.group(1))
            b = Gtk.Button(focus_on_click=False)
            b.add_css_class("wt")
            l = Gtk.Label(label=title or "(ohne Titel)", xalign=0, ellipsize=Pango.EllipsizeMode.END, max_width_chars=40,
                          margin_start=14 * levels.get(kind, 1))
            b.set_child(l)
            b.connect("clicked", lambda _b, ln=i + 1: (self.outline_pop.popdown(), self.goto_line(ln)))
            box.append(b)
            n += 1
        if not n:
            box.append(Gtk.Label(label="Noch keine Überschriften.\n\\section{…} legt eine an.", xalign=0))

    # ================= Kompilieren =================
    # ================= SyncTeX =================
    def get_synctex(self):
        path = os.path.join(BUILD, self.nid or "-", "main.synctex.gz")
        if not os.path.exists(path):
            return None
        mt = os.path.getmtime(path)
        if not self.synctex or self.synctex[0] != mt:
            try:
                self.synctex = (mt, tx.SyncTex(path))
            except (OSError, EOFError, ValueError):
                return None
        return self.synctex[1]

    def inverse_search(self, page, x, y):
        st = self.get_synctex()
        hit = st.to_source(page, x, y) if st else None
        if not hit:
            self.notify("Für diese Stelle kenne ich die Quelltext-Zeile nicht – einmal neu kompilieren hilft oft")
            return
        name, line = hit
        self.goto_line(line, name if name else "main.tex")

    def forward_search(self):
        st = self.get_synctex()
        line = self.buf.get_iter_at_mark(self.buf.get_insert()).get_line() + 1
        hit = st.to_pdf(self.cur_file, line) if st else None
        if not hit:
            self.notify("Diese Zeile steht (noch) nicht im PDF – erst kompilieren")
            return
        self.side_btns["preview"].set_active(True)
        self.preview.show_location(*hit)

    def pick_compilers(self):
        comps = find_compilers()
        pref = self.settings.get("compiler", "auto")
        comps.sort(key=lambda c: c[0] != pref)
        return comps

    def refresh_compilers(self):
        self.compilers = self.pick_compilers()
        self.update_compiler_ui()

    def spell_global(self):
        return True

    def setting_changed(self, key):
        if key == "live":
            self.live_btn.set_active(self.settings.get("live", True))
        elif key == "spell" and self.spell:
            self.spell.queue(0)
        elif key == "formula_preview" and not self.settings.get("formula_preview", True):
            self.hide_formula()

    def update_compiler_ui(self):
        if self.compilers:
            name, path = self.compilers[0]
            self.comp_label.set_label(f"󰘦 {name}")
            self.comp_label.set_tooltip_text(path)
            if self.side.get_visible_child_name() == "setup":
                self.side.set_visible_child_name("preview")
                self.side_btns["preview"].set_active(True)
        else:
            self.comp_label.set_label("󰘦 kein Compiler")
            self.side.set_visible_child_name("setup")
        self.compile_btn.set_sensitive(bool(self.compilers))

    def setup_tectonic(self):
        self.setup_btn.set_sensitive(False)
        self.setup_bar.set_visible(True)

        def progress(text, frac):
            self.setup_info.set_label(text)
            self.setup_bar.set_fraction(min(1, frac))
            return False

        def done(err):
            self.setup_btn.set_sensitive(True)
            self.setup_bar.set_visible(False)
            if err:
                self.setup_info.set_label(f"Hat nicht geklappt: {err}\nBesteht eine Internetverbindung?")
                return False
            self.compilers = self.pick_compilers()
            self.setup_info.set_label("Fertig! Tectonic ist eingerichtet.")
            self.update_compiler_ui()
            self.notify("Tectonic eingerichtet – das erste Kompilieren lädt noch Pakete nach")
            self.compile(manual=True)
            return False
        install_tectonic(progress, done)

    def schedule_compile(self, delay=1300):
        if self._compile_id:
            GLib.source_remove(self._compile_id)
        self._compile_id = GLib.timeout_add(delay, lambda: (setattr(self, "_compile_id", None), self.compile())[-1])

    def compile(self, manual=False):
        if self._compile_id:
            GLib.source_remove(self._compile_id)
            self._compile_id = None
        if not self.nid or not self.compilers:
            if manual and not self.compilers:
                self.side.set_visible_child_name("setup")
            return False
        text = self.text()
        if not text.strip():
            return False
        if self.proc:
            self._pending = True
            return False
        dirty = bool(self._dirty_files)
        self.save_files()
        if not manual and text == self.last_written and not dirty:
            return False
        proj = self.project_dir()
        outdir = os.path.join(BUILD, self.nid)
        os.makedirs(outdir, exist_ok=True)
        with open(os.path.join(proj, "main.tex"), "w", encoding="utf-8") as f:
            f.write(text)
        self.last_written = text
        name, exe = self.compilers[0]
        search = os.path.dirname(self.source) if self.source and os.path.isdir(os.path.dirname(self.source)) else None
        cmd = compile_cmd(name, exe, outdir, search, bib="\\bibliography{" in text)
        launcher = Gio.SubprocessLauncher.new(Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_MERGE |
                                              Gio.SubprocessFlags.STDIN_PIPE)
        launcher.set_cwd(proj)
        if search and name != "tectonic":
            launcher.setenv("TEXINPUTS", f"{search}:", True)
        try:
            proc = launcher.spawnv(cmd)
        except GLib.Error as e:
            self.set_state("err", "Compiler startet nicht")
            self.notify(f"Compiler startet nicht: {e.message}")
            return False
        self.proc = proc
        self._gen += 1
        gen, t0 = self._gen, time.monotonic()
        first = name == "tectonic" and not any(os.path.isdir(os.path.join(GLib.get_user_cache_dir(), d)) for d in ("tectonic", "Tectonic"))
        self.set_state("busy", "Lädt LaTeX-Pakete (nur beim ersten Mal) …" if first else "Kompiliert …")
        timeout = GLib.timeout_add_seconds(600 if first else 120, lambda: (proc.force_exit(), False)[-1])
        nid = self.nid

        def finished(p, res):
            GLib.source_remove(timeout) if timeout else None
            try:
                ok, out, _ = p.communicate_utf8_finish(res)
            except GLib.Error:
                out = ""
            if self.proc is p:
                self.proc = None
            if gen != self._gen or nid != self.nid:
                return
            self.synctex = None
            self.after_compile(p, out or "", outdir, time.monotonic() - t0)
            if self._pending:
                self._pending = False
                self.compile()
        proc.communicate_utf8_async(None, None, finished)
        return False

    def after_compile(self, proc, out, outdir, secs):
        try:
            with open(os.path.join(outdir, "main.log"), encoding="utf-8", errors="replace") as f:
                log = f.read()
        except OSError:
            log = ""
        probs = parse_log(log, out)
        status = proc.get_exit_status() if proc.get_if_exited() else -1
        pdf = os.path.join(outdir, "main.pdf")
        errors = [p for p in probs if p["kind"] == "error"]
        if status != 0 and not errors:
            last = [l for l in out.strip().splitlines() if l.strip()][-3:]
            msg = " ".join(last) or "Der Compiler ist ohne PDF abgebrochen"
            if "network" in out.lower() or "resolve" in out.lower() or "connect" in out.lower():
                msg = "Keine Internetverbindung: Tectonic muss beim ersten Mal Pakete laden"
            errors = [dict(line=None, kind="error", msg=msg, title="Kompilieren fehlgeschlagen",
                           text="Details stehen im Protokoll.")]
            probs = errors + probs
        self.set_problems(probs, (out + "\n\n" + log).strip())
        fresh = os.path.exists(pdf) and os.path.getmtime(pdf) >= time.time() - secs - 2
        if fresh:
            self.preview.load(pdf)
        if errors:
            first = errors[0]
            where = (f" in Zeile {first['line']}" if first["line"] else "") + \
                (f" ({first['file']})" if first.get("file", "main.tex") != "main.tex" else "")
            self.set_state("err", f"✗ {len(errors)} Fehler{where}")
            if self.settings.get("auto_problems", True):
                self.probrev.set_reveal_child(True)
        else:
            pages = self.preview.doc.get_n_pages() if self.preview.doc else 0
            warn = len(probs)
            self.set_state("ok", f"✓ {pages} Seite{'n' if pages != 1 else ''} · {secs:.1f} s".replace(".", ",")
                           + (f" · {warn} Hinweis{'e' if warn != 1 else ''}" if warn else ""))
            if not warn:
                self.probrev.set_reveal_child(False)

    def set_state(self, kind, text):
        for k in ("ok", "busy", "err", "idle"):
            self.state.remove_css_class(k)
        self.state.add_css_class(kind)
        self.state.set_label(text)
        self.state.set_tooltip_text("Klick zeigt die Fehlerliste" if kind == "err" else None)

    def set_problems(self, probs, log):
        self.probs = probs
        self.log_view.get_buffer().set_text(log)
        while (r := self.prob_list.get_first_child()):
            self.prob_list.remove(r)
        self.err_all = {(p.get("file", "main.tex"), p["line"]) for p in probs if p["kind"] == "error" and p["line"]}
        self.apply_err_lines()
        ne = sum(p["kind"] == "error" for p in probs)
        nw = len(probs) - ne
        parts = ([f"{ne} FEHLER"] if ne else []) + ([f"{nw} HINWEIS{'E' if nw != 1 else ''}"] if nw else [])
        self.prob_head.set_label(" · ".join(parts) + ("  –  KLICK SPRINGT ZUR ZEILE" if probs else ""))
        for p in probs[:50]:
            row = Gtk.ListBoxRow()
            row.line = p["line"]
            row.file = p.get("file", "main.tex")
            h = Gtk.Box(spacing=8)
            icon = Gtk.Label(label="󰅚" if p["kind"] == "error" else "󰀦", valign=Gtk.Align.START)
            icon.add_css_class("prob-icon-err" if p["kind"] == "error" else "prob-icon-warn")
            h.append(icon)
            v = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True)
            where = (f"{p['file']} · " if p.get("file", "main.tex") != "main.tex" else "") + \
                (f"Zeile {p['line']} · " if p["line"] else "")
            t = Gtk.Label(xalign=0, wrap=True, label=where + p["title"])
            t.add_css_class("prob-title")
            v.append(t)
            if p["text"]:
                x = Gtk.Label(label=p["text"], xalign=0, wrap=True)
                x.add_css_class("prob-text")
                v.append(x)
            raw = Gtk.Label(label=p["msg"][:200], xalign=0, wrap=True, selectable=False)
            raw.add_css_class("prob-raw")
            v.append(raw)
            h.append(v)
            row.set_child(h)
            self.prob_list.append(row)

    def apply_err_lines(self):
        """Fehlerzeilen der gerade offenen Datei rot hinterlegen."""
        for b in self.bufs:
            s, e = b.get_bounds()
            b.remove_tag_by_name("hl-errline", s, e)
        self.err_lines = {ln for f, ln in getattr(self, "err_all", set()) if f == self.cur_file}
        for ln in self.err_lines:
            ok, a = self.buf.get_iter_at_line(ln - 1)
            if ok:
                z = a.copy()
                z.forward_line()
                self.buf.apply_tag_by_name("hl-errline", a, z)
        self.gutter.queue_draw()

    def kill(self):
        if self._compile_id:
            GLib.source_remove(self._compile_id)
            self._compile_id = None
        if self.proc:
            self._gen += 1
            try:
                self.proc.force_exit()
            except GLib.Error:
                pass
            self.proc = None
        self._pending = False

    def shutdown(self):
        self.kill()

    def pdf_path(self):
        p = os.path.join(BUILD, self.nid or "-", "main.pdf")
        return p if os.path.exists(p) else None

    # ================= Layout =================
    def on_paned_moved(self, *_):
        w = self.paned.get_width()
        if not self._paned_init:
            if w > 0:
                self._paned_init = True
                frac = self.settings.get("split", 0.5)
                total = w if self.paned.get_orientation() == Gtk.Orientation.HORIZONTAL else self.paned.get_height()
                GLib.idle_add(lambda: self.paned.set_position(int(total * frac)) and False)
            return
        total = w if self.paned.get_orientation() == Gtk.Orientation.HORIZONTAL else self.paned.get_height()
        if total > 0:
            self.settings["split"] = round(self.paned.get_position() / total, 3)

    def set_compact(self, on):
        orient = Gtk.Orientation.VERTICAL if on else Gtk.Orientation.HORIZONTAL
        if self.paned.get_orientation() != orient:
            self.paned.set_orientation(orient)
            self._paned_init = False
            GLib.idle_add(lambda: self.on_paned_moved() and False)
        for b, (full, short) in ((self.side_btns["preview"], ("󰈙  Vorschau", "󰈙")),
                                 (self.side_btns["help"], ("󰋖  Hilfe & Spickzettel", "󰋖 Hilfe"))):
            b.get_child().set_label(short if on else full)
