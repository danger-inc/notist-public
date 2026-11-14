# Tabellen-Anhang (XLSX) in Words: Die Datei liegt in notist/data/sheets/ (Name = Prüfsumme, gleiche Dateien nur einmal),
# im Dokument steht nur eine Karte {"t": "sheet", "file", "name", "sheets", "cur", "nrows", "ncols"}.
# Die Vorschau (Gtk.Grid) entsteht erst auf Knopfdruck. Der XLSX-Leser kommt ohne Fremdpakete aus (zipfile + ElementTree).
# Für Export (DOCX/PDF/HTML/…) wird der Block über docfmt.expand_sheets() zu einer normalen Tabelle des gewählten Blatts.
import datetime
import hashlib
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from xml.etree import ElementTree as ET

from core import paths

SHEETS = os.path.join(paths.DATA, "sheets")
MAX_ROWS = 2000                 # so viele Zeilen/Spalten liest der Leser je Blatt (Rest: nur gezählt)
MAX_COLS = 200
SHOW_ROWS, SHOW_COLS = 100, 26  # sichtbar in der Karte
TABLE_ROWS = 300                # „Als Tabelle einfügen“ / Export
ICON = "\U000f021b"
I_OPEN, I_TABLE, I_REFRESH = "\U000f03cb", "\U000f0e5b", "\U000f0450"


def _de():
    try:
        import i18n
        return i18n.LANG == "de"
    except ImportError:          # Kern ohne App (Handy): Deutsch wie bisher
        return True


# ====================================================================== XLSX-Leser
_M = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
_EPOCH = datetime.datetime(1899, 12, 30)
_DATE_IDS = set(range(14, 18)) | set(range(27, 37)) | set(range(50, 59))
_TIME_IDS = set(range(18, 22)) | {45, 46, 47}
_BUILTIN = {1: "0", 2: "0.00", 3: "#,##0", 4: "#,##0.00", 9: "0%", 10: "0.00%", 11: "0.00E+00",
            37: "#,##0", 38: "#,##0", 39: "#,##0.00", 40: "#,##0.00"}


def col_name(i):
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def _col_index(ref):
    n = 0
    for ch in ref:
        if not ch.isalpha():
            break
        n = n * 26 + ord(ch.upper()) - 64
    return n - 1


def _row_index(ref):
    m = re.search(r"\d+", ref)
    return int(m.group()) - 1 if m else -1


def _text_of(si):
    """Text eines <si>/<is>: <t> direkt oder in <r>-Läufen (Rich Text), Lautschrift (rPh) bleibt draußen."""
    out = []
    for ch in si:
        tag = ch.tag
        if tag == _M + "t":
            out.append(ch.text or "")
        elif tag == _M + "r":
            for t in ch.findall(_M + "t"):
                out.append(t.text or "")
    return "".join(out)


def _clean_code(code):
    code = re.sub(r'"[^"]*"', "", code)
    code = re.sub(r"\[[^\]]*\]", "", code)
    return re.sub(r"\\.", "", code)


def _decimals(code):
    sec = _clean_code(code).split(";")[0]
    m = re.search(r"\.([0#?]+)", sec)
    return len(m.group(1)) if m else 0


def _group(s, sep):
    neg = s.startswith("-")
    ip, _, fp = s.lstrip("-").partition(".")
    ip = f"{int(ip):,}".replace(",", sep) if ip.isdigit() else ip
    return ("-" if neg else "") + ip + ("." + fp if fp else "")


def fmt_number(v, code):
    """Zahl nach (vereinfachtem) Excel-Zahlenformat als Text; Dezimaltrenner nach Oberflächensprache."""
    de = _de()
    sec = _clean_code(code or "").split(";")[0]
    pct = "%" in sec
    if pct:
        v *= 100
    if not code or code.lower() == "general" or code == "@":
        s = str(int(v)) if v == int(v) and abs(v) < 1e15 else f"{v:.10g}"
    elif re.search(r"0\.0+E[+-]0", sec, re.I):
        s = f"{v:.{_decimals(code)}E}"
    else:
        s = f"{v:.{_decimals(code)}f}"
        if "," in re.split(r"\.", sec)[0]:
            s = _group(s, ",")
    if pct:
        s += "%"
    elif "€" in (code or ""):
        s += " €"
    if de:
        s = s.translate(str.maketrans({",": ".", ".": ","}))
    return s


def fmt_date(v, code, kind):
    try:
        dt = _EPOCH + datetime.timedelta(days=v)
    except (OverflowError, ValueError):
        return str(v)
    if kind == "time":
        return dt.strftime("%H:%M:%S" if "s" in (code or "").lower() else "%H:%M")
    if kind == "datetime" or (kind == "date" and (dt.hour or dt.minute) and "h" in (code or "").lower()):
        return dt.strftime("%d.%m.%Y %H:%M")
    return dt.strftime("%d.%m.%Y") if _de() else dt.strftime("%Y-%m-%d")


def _date_kind(xid, code):
    if xid in _DATE_IDS:
        return "date"
    if xid in _TIME_IDS:
        return "time"
    if xid == 22:
        return "datetime"
    if not code or xid < 164:
        return None
    c = _clean_code(code).lower()
    d = bool(re.search(r"[yd]", c)) or ("m" in c and "h" not in c and "s" not in c)
    t = bool(re.search(r"[hs]", c))
    if d and t:
        return "datetime"
    return "date" if d else ("time" if t else None)


class Workbook:
    """Liest eine XLSX-Datei; Blätter werden erst bei Bedarf geparst (sheet(i))."""

    def __init__(self, path):
        self.path = path
        self.z = zipfile.ZipFile(path)
        wb = ET.fromstring(self.z.read("xl/workbook.xml"))
        rels = {}
        try:
            for r in ET.fromstring(self.z.read("xl/_rels/workbook.xml.rels")):
                rels[r.get("Id")] = r.get("Target")
        except KeyError:
            pass
        self.names, self.targets = [], []
        for s in wb.iter(_M + "sheet"):
            if s.get("state") in ("hidden", "veryHidden"):
                continue
            t = rels.get(s.get(_R + "id"), "")
            t = t.lstrip("/") if t.startswith("/") else "xl/" + t
            self.names.append(s.get("name") or f"Sheet{len(self.names) + 1}")
            self.targets.append(t)
        if not self.names:
            raise ValueError("keine Blätter")
        self._sst = None
        self._xfs = None
        self._fmts = {}
        self._cache = {}

    def close(self):
        try:
            self.z.close()
        except Exception:  # noqa: BLE001
            pass

    # ---- gemeinsame Tabellen
    def sst(self):
        if self._sst is None:
            self._sst = []
            try:
                root = ET.fromstring(self.z.read("xl/sharedStrings.xml"))
                self._sst = [_text_of(si) for si in root.iter(_M + "si")]
            except KeyError:
                pass
        return self._sst

    def xfs(self):
        if self._xfs is None:
            self._xfs = []
            try:
                root = ET.fromstring(self.z.read("xl/styles.xml"))
            except KeyError:
                return self._xfs
            for nf in root.iter(_M + "numFmt"):
                self._fmts[int(nf.get("numFmtId"))] = nf.get("formatCode") or ""
            cx = root.find(_M + "cellXfs")
            for xf in (cx if cx is not None else []):
                self._xfs.append(int(xf.get("numFmtId") or 0))
        return self._xfs

    def style_fmt(self, s):
        xfs = self.xfs()
        xid = xfs[s] if 0 <= s < len(xfs) else 0
        return xid, self._fmts.get(xid) or _BUILTIN.get(xid, "")

    # ---- Blatt
    def cell(self, el, sst):
        t = el.get("t") or "n"
        v = el.find(_M + "v")
        txt = v.text if v is not None and v.text is not None else None
        if t == "inlineStr":
            is_ = el.find(_M + "is")
            return (_text_of(is_) if is_ is not None else ""), False
        if txt is None:
            return "", False
        if t == "s":
            try:
                return sst[int(txt)], False
            except (ValueError, IndexError):
                return "", False
        if t == "b":
            return (("WAHR" if txt == "1" else "FALSCH") if _de() else ("TRUE" if txt == "1" else "FALSE")), False
        if t in ("str", "e"):
            return txt, False
        try:
            x = float(txt)
        except ValueError:
            return txt, False
        xid, code = self.style_fmt(int(el.get("s") or 0))
        kind = _date_kind(xid, code)
        if kind:
            return fmt_date(x, code, kind), True
        return fmt_number(x, code), True

    def sheet(self, i):
        """→ {"name", "rows": [[(text, is_number)]], "nrows", "ncols"}; Randleere Zeilen/Spalten gekappt."""
        if i in self._cache:
            return self._cache[i]
        i = max(0, min(i, len(self.names) - 1))
        sst = self.sst()
        self.xfs()
        cells, maxr, maxc = {}, -1, -1
        dim = None
        try:
            with self.z.open(self.targets[i]) as f:
                r_auto = -1
                for ev, el in ET.iterparse(f, events=("end",)):
                    if el.tag == _M + "dimension":
                        dim = el.get("ref")
                    elif el.tag == _M + "c":
                        ref = el.get("r") or ""
                        ri = _row_index(ref) if ref else r_auto
                        ci = _col_index(ref) if ref else 0
                        if ri < MAX_ROWS and ci < MAX_COLS:
                            txt, num = self.cell(el, sst)
                            if txt != "":
                                cells[(ri, ci)] = (txt, num)
                                maxr, maxc = max(maxr, ri), max(maxc, ci)
                        el.clear()
                    elif el.tag == _M + "row":
                        r_auto = int(el.get("r") or r_auto + 2) - 1
                        el.clear()
                        if r_auto >= MAX_ROWS:
                            break
        except (KeyError, ET.ParseError):
            pass
        nrows, ncols = maxr + 1, maxc + 1
        if dim and ":" in dim and (maxr >= MAX_ROWS - 1 or maxc >= MAX_COLS - 1):   # gekappt → Gesamtgröße laut Datei
            a, b = dim.split(":")
            nrows = max(nrows, _row_index(b) + 1)
            ncols = max(ncols, _col_index(b) + 1)
            nrows = min(nrows, 1048576)
        rows = [[cells.get((r, c), ("", False)) for c in range(maxc + 1)] for r in range(maxr + 1)]
        res = {"name": self.names[i], "rows": rows, "nrows": nrows, "ncols": ncols}
        self._cache[i] = res
        return res


_WB = {}


def workbook(path):
    """Gemerkte Arbeitsmappe (neu geladen, wenn sich die Datei geändert hat)."""
    try:
        st = os.stat(path)
    except OSError:
        return None
    key = (st.st_mtime_ns, st.st_size)
    hit = _WB.get(path)
    if hit and hit[0] == key:
        return hit[1]
    try:
        wb = Workbook(path)
    except (OSError, KeyError, ValueError, zipfile.BadZipFile, ET.ParseError):
        return None
    if hit:
        hit[1].close()
    if len(_WB) > 6:
        _WB.pop(next(iter(_WB)))[1].close()
    _WB[path] = (key, wb)
    return wb


def path_of(name):
    return os.path.join(SHEETS, os.path.basename(name))


def table_rows(info, limit=TABLE_ROWS):
    """Aktuelles Blatt als Zeilenliste reiner Texte (für Words-Tabelle und Export); leer → [[""]]."""
    wb = workbook(path_of(info.get("file", "")))
    if wb is None:
        return [[f"[{info.get('name', 'XLSX')}]"]]
    sh = wb.sheet(int(info.get("cur") or 0))
    rows = [[t for t, _n in r] for r in sh["rows"][:limit]]
    n = max((len(r) for r in rows), default=0)
    rows = [r + [""] * (n - len(r)) for r in rows]
    return rows or [[""]]


# ====================================================================== Einfügen / Speichern
def _csv_rows(src):
    """CSV/TSV lesen: Trennzeichen erkennen (, ; Tab), Kodierung UTF-8 (mit/ohne BOM) sonst cp1252."""
    import csv
    raw = open(src, "rb").read()
    for enc in ("utf-8-sig", "cp1252"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = raw.decode("latin-1")
    sample = text[:8192]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel_tab if src.lower().endswith(".tsv") else csv.excel
    return [r for r in csv.reader(text.splitlines(), dialect)]


def csv_to_xlsx(src, dst):
    """Eigener Mini-Umwandler (ohne Gnumeric): CSV/TSV → XLSX mit einem Blatt. Zahlen bleiben Zahlen, Rest ist Text."""
    from xml.sax.saxutils import escape
    rows = _csv_rows(src)
    out = []
    for ri, row in enumerate(rows, 1):
        cells = []
        for ci, val in enumerate(row):
            if val == "":
                continue
            ref = f"{col_name(ci)}{ri}"
            v = val.strip()
            if re.fullmatch(r"-?\d+([.,]\d+)?", v):
                cells.append(f'<c r="{ref}"><v>{v.replace(",", ".")}</v></c>')
            else:
                cells.append(f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">{escape(val)}</t></is></c>')
        out.append(f'<row r="{ri}">{"".join(cells)}</row>')
    ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    rel = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                   '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                   '<Default Extension="xml" ContentType="application/xml"/>'
                   '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
                   '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>')
        z.writestr("_rels/.rels", '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        z.writestr("xl/workbook.xml", f'<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="{ns}" xmlns:r="{rel}"><sheets>'
                   '<sheet name="Tabelle1" sheetId="1" r:id="rId1"/></sheets></workbook>')
        z.writestr("xl/_rels/workbook.xml.rels", '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>')
        z.writestr("xl/worksheets/sheet1.xml", f'<?xml version="1.0" encoding="UTF-8"?><worksheet xmlns="{ns}"><sheetData>{"".join(out)}</sheetData></worksheet>')


def convert(src):
    """Andere Formate in eine temporäre XLSX umwandeln → Pfad oder None. xls/ods/… per ssconvert (Gnumeric), CSV/TSV auch
    ohne (eigener Umwandler – am Mac gibt es kein Gnumeric)."""
    exe = shutil.which("ssconvert")
    is_csv = src.lower().endswith((".csv", ".tsv", ".txt"))
    if not exe and not is_csv:
        return None
    d = tempfile.mkdtemp(prefix="notist-sheet-")
    dst = os.path.join(d, "x.xlsx")
    try:
        if is_csv and not exe:
            csv_to_xlsx(src, dst)
        else:
            subprocess.run([exe, src, dst], check=True, capture_output=True, timeout=60)
    except (OSError, subprocess.SubprocessError, ValueError, zipfile.BadZipFile):
        shutil.rmtree(d, ignore_errors=True)
        return None
    return dst if os.path.exists(dst) else None


def store(src):
    """Datei in den eigenen Ordner kopieren. → (info, fehlertext). info = {"file","name","sheets","cur","nrows","ncols"}."""
    name = os.path.basename(src)
    tmp = None
    try:
        is_xlsx = zipfile.is_zipfile(src) and "xl/workbook.xml" in zipfile.ZipFile(src).namelist()
    except (OSError, zipfile.BadZipFile):
        return None, "Die Datei lässt sich nicht lesen"
    if not is_xlsx:
        tmp = convert(src)
        if tmp is None:
            return None, ("Das ist keine XLSX-Datei – xls/ods lassen sich nur mit ssconvert (Gnumeric) umwandeln, CSV und XLSX gehen immer"
                          if not shutil.which("ssconvert") else "Diese Tabelle lässt sich nicht umwandeln")
        name = os.path.splitext(name)[0] + ".xlsx"
        src = tmp
    try:
        data = paths.read_file(src, True)
    finally:
        if tmp:
            shutil.rmtree(os.path.dirname(tmp), ignore_errors=True)
    fname = hashlib.sha256(data).hexdigest()[:24] + ".xlsx"
    os.makedirs(SHEETS, exist_ok=True)
    dst = path_of(fname)
    if not os.path.exists(dst):
        with open(dst, "wb") as f:
            f.write(data)
    wb = workbook(dst)
    if wb is None:
        try:
            os.remove(dst)
        except OSError:
            pass
        return None, "Die Tabelle lässt sich nicht lesen"
    sh = wb.sheet(0)
    return {"file": fname, "name": name, "sheets": len(wb.names), "cur": 0,
            "nrows": sh["nrows"], "ncols": sh["ncols"]}, None

