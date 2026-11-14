# notist – Abgleich mit der Handy-App im WLAN (Notizen und Words in beide Richtungen).
#
# Gleiches Verfahren wie musicalist (handy_sync.py): In den Einstellungen „handy koppeln“ → Code (8 Zeichen) +
# Adresse für 3 Minuten. Koppeln = Diffie-Hellman (RFC-3526-Gruppe 14) + Code-Bestätigung in beide Richtungen →
# eigener Schlüssel je Gerät. Danach ist jede Anfrage verschlüsselt und signiert (HMAC-SHA256 als Stromchiffre +
# HMAC-Prüfsumme, nur stdlib). Port 37527/tcp, mDNS _notist._tcp (nur wenn zeroconf da ist – sonst sucht das Handy
# im eigenen Netz nach dem Port).
#
# Abgleich: Das Handy schickt die Liste seiner Einträge, alles, was es seit dem letzten Abgleich geändert hat, und
# was es endgültig gelöscht hat. Der PC merkt sich je Gerät, welchen Stand (Prüfsumme) jedes Eintrags das Handy
# zuletzt bekommen hat – daran erkennt er, wer etwas geändert hat. Beide geändert → der neuere Stand bleibt, der
# andere wird als Kopie „(konflikt)“ behalten. Nichts geht still verloren.
#
# v2 (Plan Schritt 9, Kern in core/sync2.py): POST /v2 (verschlüsselt wie oben, Kopf X-Dev), Kopplung über
# /v2/pair1 + /v2/pair2 (SPAKE2 statt Code-HMAC). Versionsvektoren statt Wanduhr, Quittung über die eigene Liste der
# Gegenseite, Grabsteine, Anhänge (PDF/Sheets/LaTeX-Projektdateien), LaTeX und Einstellungen. v1 (/pair, /sync) ist seit
# Schritt 20 entfernt (Handy 1.0 spricht nur v2).
import hashlib, hmac, json, os, secrets, socket, threading, time, uuid

from core import paths, sync2

PORT = int(os.environ.get("NOTES_HANDY_PORT") or 37527)     # Tests: eigener Port je Instanz
KINDS = ("notes", "docs")                     # v1: LaTeX bleibt am PC
KINDS2 = ("notes", "docs", "latex")           # v2
DEVICES = os.path.join(paths.DATA, "handy.json")
PEERS = os.path.join(paths.DATA, "sync-peers.json")   # Gegenstellen, bei denen dieses Gerät Client ist (Schritt 10)
SMALL = 64 * 1024                             # Kopplungs-Anfragen
BIG = 96 * 1024 * 1024                        # Abgleich (erst nach der Geräteprüfung gelesen)
# Felder, die nur am PC Sinn haben (Datei-Verknüpfung) – gehen nicht ans Handy und werden nie überschrieben
LOCAL = {"file", "file_auto", "file_mtime", "file_size", "file_hash", "file_backup", "file_error", "file_missing", "want_file", "file_ok",
         "file_trashed", "source", "sync"}
MAX_OUT = 6 * 1024 * 1024                     # so viel je Antwort, der Rest in der nächsten Runde
P = int("FFFFFFFFFFFFFFFFC90FDAA22168C234C4C6628B80DC1CD129024E088A67CC74020BBEA63B139B22514A08798E3404DD"
        "EF9519B3CD3A431B302B0A6DF25F14374FE1356D6D51C245E485B576625E7EC6F44C42E9A637ED6B0BFF5CB6F406B7ED"
        "EE386BFB5A899FA5AE9F24117C4B1FE649286651ECE45B3DC2007CB8A163BF0598DA48361C55D39A69163FA8FD24CF5F"
        "83655D23DCA3AD961C62F356208552BB9ED529077096966D670C354E4ABC9804F1746C08CA18217C32905E462E36CE3B"
        "E39E772C180E86039B2783A2EC07A28FB5C55DF06F4C52C9DE2BCBF6955817183995497CEA956AE515D2261898FA0510"
        "15728E5A8AACAA68FFFFFFFFFFFFFFFF", 16)
G = 2
ALPHA = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"      # ohne 0/O/1/I


def log(msg):
    try:
        os.makedirs(os.path.expanduser("~/.cache/notes"), exist_ok=True)
        with open(os.path.expanduser("~/.cache/notes/handy.log"), "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + msg + "\n")
    except OSError:
        pass


# ---------- Krypto (identisch mit musicalist/handy_sync.py) ----------
def _hm(key, *parts):
    h = hmac.new(key, digestmod=hashlib.sha256)
    for p in parts:
        h.update(p if isinstance(p, bytes) else str(p).encode())
    return h.digest()


def _stream(key, nonce, n):
    out = bytearray()
    i = 0
    while len(out) < n:
        out += _hm(key, nonce, i.to_bytes(4, "big"))
        i += 1
    return bytes(out[:n])


def _xor(a, b):
    return (int.from_bytes(a, "big") ^ int.from_bytes(b, "big")).to_bytes(len(a), "big") if a else b""


def box(key, data):
    """Verschlüsseln + signieren: nonce(16) | daten ^ strom | hmac(32)."""
    ke, km = _hm(key, b"enc"), _hm(key, b"mac")
    nonce = secrets.token_bytes(16)
    ct = _xor(data, _stream(ke, nonce, len(data)))
    return nonce + ct + _hm(km, nonce, ct)


def unbox(key, blob):
    ke, km = _hm(key, b"enc"), _hm(key, b"mac")
    if len(blob) < 48:
        raise ValueError("zu kurz")
    nonce, ct, tag = blob[:16], blob[16:-32], blob[-32:]
    if not hmac.compare_digest(tag, _hm(km, nonce, ct)):
        raise ValueError("falsche signatur")
    return _xor(ct, _stream(ke, nonce, len(ct)))


def _int_bytes(x):
    return x.to_bytes(256, "big")


def local_ips():
    ips = []
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("192.0.2.1", 9))          # kein Paket – nur die Ausgangsadresse ermitteln
        ips.append(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    return ips


# ---------- Einträge ----------
def content(n):
    return {k: v for k, v in n.items() if k not in LOCAL}


def digest(n):
    raw = json.dumps(content(n), sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


class Server:
    """Läuft im notist-Prozess. Alles, was Einträge anfasst, passiert im GTK-Hauptfaden (app.* ist nicht threadsicher)."""

    def __init__(self, app):
        self.app = app
        self.httpd = None
        self.zc = None
        self.pairing = None        # {"code", "until", "pending": {A: (B, key, name)}}
        self.lock = threading.Lock()
        self.listeners = []        # fn() nach Koppeln/Abgleich (Einstellungen aktualisieren)
        self.error = None
        self.devices = self._load()
        self.main = None           # Tests: fn → fn() statt GTK-Hauptfaden
        self._rep = None
        self._peers = None

    @property
    def peers(self):
        """Gegenstellen, bei denen dieses Gerät Client ist (core/peerlink.py)."""
        if self._peers is None:
            from core import peerlink
            self._peers = peerlink.Peers(self)
        return self._peers

    @property
    def rep(self):
        if self._rep is None:
            self._rep = sync2.Replica(AppBackend(self.app), path=os.path.join(paths.DATA, "sync2.json"))
            self._rep.ext.update(compile=self._op_compile, sync_pdf=self._op_sync_pdf, sync_src=self._op_sync_src)
        return self._rep

    # ----- Geräte -----
    def _load(self):
        try:
            with open(DEVICES, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return {}

    def _save(self):
        tmp = DEVICES + ".tmp"
        with open(os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w", encoding="utf-8") as f:
            json.dump(self.devices, f)
        os.replace(tmp, DEVICES)

    def remove(self, dev_id):
        with self.lock:
            self.devices.pop(dev_id, None)
            self._save()
        self._notify()

    def _notify(self):
        from gi.repository import GLib
        for fn in list(self.listeners):
            GLib.idle_add(lambda f=fn: f() and False)

    # ----- Server -----
    @property
    def running(self):
        return self.httpd is not None

    def start(self):
        if self.httpd is not None:
            return True
        from http.server import ThreadingHTTPServer
        try:
            self.httpd = ThreadingHTTPServer(("0.0.0.0", PORT), self._handler())
        except OSError as e:
            self.error = f"port {PORT} belegt ({e.strerror})"
            log(self.error)
            return False
        self.httpd.daemon_threads = True
        threading.Thread(target=self.httpd.serve_forever, daemon=True, name="handy-link").start()
        threading.Thread(target=self._announce, daemon=True).start()
        self.error = None
        return True

    def stop(self):
        if self.httpd is not None:
            self.httpd.shutdown()
            self.httpd.server_close()
            self.httpd = None
        if self.zc is not None:
            try:
                self.zc.close()
            except Exception:  # noqa: BLE001
                pass
            self.zc = None

    def _announce(self):
        try:
            from zeroconf import IPVersion, ServiceInfo, Zeroconf
        except ImportError:
            return
        try:
            ips = local_ips()
            name = socket.gethostname().split(".")[0] or "pc"
            info = ServiceInfo("_notist._tcp.local.", f"notist {name}._notist._tcp.local.", port=PORT,
                               addresses=[socket.inet_aton(i) for i in ips], properties={"v": "2"},
                               server=f"{name}-notist.local.")
            zc = Zeroconf(ip_version=IPVersion.V4Only)
            zc.register_service(info)
            self.zc = zc
        except Exception as e:  # noqa: BLE001
            log(f"mdns: {e}")

    def start_pairing(self):
        """Neuen Code für 3 Minuten. Der Server läuft ab dann bei jedem Start (prefs handy.on)."""
        self.app.prefs.setdefault("handy", {})["on"] = True
        self.app.save_prefs()
        ok = self.start()
        code = "".join(secrets.choice(ALPHA) for _ in range(8))
        with self.lock:
            self.pairing = {"code": code, "until": time.time() + 180, "pending": {}}
        if os.environ.get("NOTES_HANDY_CODE_FILE"):            # nur für Tests
            with open(os.environ["NOTES_HANDY_CODE_FILE"], "w", encoding="utf-8") as f:
                f.write(code)
        return ok, code[:4] + "-" + code[4:], local_ips()

    def stop_pairing(self):
        with self.lock:
            self.pairing = None

    # ----- Anfragen -----
    def _handler(self):
        srv = self
        from http.server import BaseHTTPRequestHandler

        class H(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *a):
                pass

            def _send(self, code, body, ctype="application/json"):
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _json(self, code, obj):
                self._send(code, json.dumps(obj).encode())

            def do_GET(self):
                if self.path == "/hello":
                    self._json(200, {"app": "notist", "v": 2, "proto": [1, 2], "id": srv.rep.me,
                                     "name": socket.gethostname().split(".")[0],
                                     "pairing": srv.pairing is not None and srv.pairing["until"] > time.time()})
                else:
                    self._json(404, {"error": "?"})

            def do_POST(self):
                try:
                    n = int(self.headers.get("Content-Length") or 0)
                except ValueError:
                    n = -1
                dev_id = self.headers.get("X-Dev", "")
                dev = srv.devices.get(dev_id) if self.path == "/v2" else None
                limit = BIG if dev is not None else SMALL      # A8: großer Körper erst nach der Geräteprüfung
                if n < 0 or n > limit:
                    self.close_connection = True
                    return self._json(413 if dev is not None or self.path != "/v2" else 401,
                                      {"error": "zu groß" if dev is not None else "unbekanntes gerät – neu koppeln"})
                body = self.rfile.read(n)
                try:
                    if self.path == "/v2/pair1":
                        return self._json(*srv.v2_pair1(json.loads(body)))
                    if self.path == "/v2/pair2":
                        return self._json(*srv.v2_pair2(json.loads(body)))
                    if self.path == "/v2":
                        if dev is None:
                            return self._json(401, {"error": "unbekanntes gerät – neu koppeln"})
                        key = bytes.fromhex(dev["key"])
                        try:
                            req = json.loads(unbox(key, body))
                        except ValueError:
                            return self._json(401, {"error": "schlüssel passt nicht – neu koppeln"})
                        try:
                            res = srv.v2(dev_id, req)
                        except sync2.Refused as e:
                            return self._json(409, {"error": str(e)})
                        return self._send(200, box(key, json.dumps(res, ensure_ascii=False).encode()),
                                          "application/octet-stream")
                except Exception as e:  # noqa: BLE001
                    import traceback
                    log("fehler: " + traceback.format_exc())
                    return self._json(500, {"error": str(e)[:200]})
                self._json(404, {"error": "?"})

        return H

    # ----- LaTeX für das Handy (Schritt 29): der Rechner baut, das Handy zeigt PDF + Fehlerliste -----
    _tex = {}                                # Schlüssel → {"work": Ordner, "synctex": Pfad oder None}

    def _op_compile(self, req):
        """{key: "latex:<id>", text: main.tex} → {ok, problems, log, pdf (base64) | None, synctex: bool}. Projektdateien kommen aus dem
        abgeglichenen Projektordner des Rechners; der Text der Anfrage ersetzt main.tex (auch ungesicherte Änderungen zählen)."""
        import base64, shutil, subprocess, tempfile
        import latex
        key = str(req.get("key") or "")
        text = str(req.get("text") or "")
        kind, _, nid = key.partition(":")
        if kind != "latex" or not nid or "/" in nid or ".." in nid:
            raise sync2.Refused("kein latex-eintrag")
        found = latex.find_compilers()
        if not found:
            return {"ok": False, "problems": [{"line": None, "file": "main.tex", "kind": "error", "msg": "Kein LaTeX-Programm am Rechner",
                                              "title": "Kein LaTeX am Rechner", "text": "Am Rechner ist weder Tectonic noch pdflatex eingerichtet (notist → LaTeX → Einrichten)."}],
                    "log": "", "pdf": None, "synctex": False}
        name, exe = found[0]
        src = self.rep.b._projdir(key)
        old = self._tex.pop(key, None)
        if old:
            shutil.rmtree(old["work"], ignore_errors=True)
        work = tempfile.mkdtemp(prefix="notist-tex-")
        if os.path.isdir(src):
            shutil.copytree(src, work, dirs_exist_ok=True, ignore=shutil.ignore_patterns(".*"))
        with open(os.path.join(work, "main.tex"), "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        cmd = latex.compile_cmd(name, exe, work, main="main.tex", bib="\\bibliography{" in text)
        try:
            r = subprocess.run(cmd, cwd=work, capture_output=True, text=True, timeout=240, stdin=subprocess.DEVNULL)
            out = (r.stdout or "") + (r.stderr or "")
        except subprocess.TimeoutExpired:
            out = "error: Zeitüberschreitung beim Kompilieren"
        pdf = os.path.join(work, "main.pdf")
        logp = os.path.join(work, "main.log")
        logtxt = open(logp, encoding="utf-8", errors="replace").read() if os.path.exists(logp) else ""
        probs = latex.parse_log(logtxt, out)
        ok = os.path.exists(pdf) and not any(p["kind"] == "error" for p in probs)
        data = None
        if os.path.exists(pdf) and os.path.getsize(pdf) <= 24 * 1024 * 1024:
            with open(pdf, "rb") as f:
                data = base64.b64encode(f.read()).decode()
        st = os.path.join(work, "main.synctex.gz")
        self._tex[key] = {"work": work, "synctex": st if os.path.exists(st) else None}
        return {"ok": ok, "problems": probs, "log": (out + "\n" + logtxt)[-6000:], "pdf": data, "synctex": os.path.exists(st), "compiler": name}

    def _synctex(self, key):
        from core import texcore
        t = self._tex.get(str(key))
        if not t or not t["synctex"]:
            raise sync2.Refused("noch nicht kompiliert (oder keine synctex-daten)")
        return texcore.SyncTex(t["synctex"])

    def _op_sync_pdf(self, req):
        """Quelltext-Zeile → {page, x, y} (Seite 0-basiert, PDF-Punkte, y von oben) oder {}."""
        r = self._synctex(req.get("key")).to_pdf(str(req.get("file") or "main.tex"), int(req.get("line") or 1))
        return {"page": r[0], "x": r[1], "y": r[2], "w": r[3]} if r else {}

    def _op_sync_src(self, req):
        """PDF-Stelle → {file, line} oder {}."""
        r = self._synctex(req.get("key")).to_source(int(req.get("page") or 0), float(req.get("x") or 0), float(req.get("y") or 0))
        return {"file": r[0], "line": r[1]} if r else {}

    def run_main(self, fn, timeout=120):
        """fn im GTK-Hauptfaden ausführen und auf das Ergebnis warten. A3: Hat fn nach `timeout` noch nicht
        angefangen, wird es abgesagt (läuft nie mehr); hat es angefangen, wird zu Ende gewartet – sonst wäre der
        Abgleich angewendet, aber die Antwort weg."""
        if self.main is not None:
            return self.main(fn)
        from gi.repository import GLib
        box_ = {}
        done = threading.Event()
        gate = threading.Lock()
        state = {"started": False, "cancelled": False}

        def run():
            with gate:
                if state["cancelled"]:
                    return False
                state["started"] = True
            try:
                box_["res"] = fn()
            except Exception as e:  # noqa: BLE001
                if not isinstance(e, sync2.Refused):
                    import traceback
                    log("abgleich: " + traceback.format_exc())
                box_["err"] = e
            done.set()
            return False
        GLib.idle_add(run)
        if not done.wait(timeout):
            with gate:
                if not state["started"]:
                    state["cancelled"] = True
                    raise RuntimeError("pc beschäftigt")
            done.wait()
        if "err" in box_:
            raise box_["err"]
        return box_["res"]

    def v2_pair1(self, req):
        with self.lock:
            pr = self.pairing
            if pr is None or pr["until"] < time.time():
                return 403, {"error": "am anderen gerät zuerst „koppeln“ drücken (notist → einstellungen)"}
            if len(pr["pending"]) > 20:
                return 429, {"error": "zu viele versuche"}
            try:
                st, Y = sync2.pake_server(pr["code"], str(req["X"]))
            except (KeyError, ValueError):
                return 400, {"error": "ungültig"}
            pr["pending"][str(req["X"])] = (st, str(req.get("name") or "gerät")[:40], "pc" if req.get("kind") == "pc" else "handy")
        return 200, {"Y": Y, "name": socket.gethostname().split(".")[0], "v": 2}

    def v2_pair2(self, req):
        with self.lock:
            pr = self.pairing
            if pr is None or str(req.get("X")) not in pr["pending"]:
                return 403, {"error": "kopplung abgelaufen"}
            st, name, kind = pr["pending"][str(req["X"])]
            if not sync2.pake_check(st["cli"], req.get("c")):
                self.pairing = None              # falscher Code: Kopplung beenden (ein Versuch je Code)
                return 403, {"error": "code falsch"}
            dev_id = secrets.token_hex(8)
            self.devices[dev_id] = {"name": name, "key": st["key"].hex(), "paired": time.time(), "last": None,
                                    "v": 2, "kind": kind}
            self._save()
            self.pairing = None
        self._notify()
        return 200, {"id": dev_id, "s": st["srv"]}

    def v2(self, dev_id, req):
        if req.get("op") in ("blob", "put", "open", "compile", "sync_pdf", "sync_src"):
            return self.rep.handle(dev_id, req)       # nur Dateien/Sitzung/Kompilieren – kein Hauptfaden nötig
        return self.run_main(lambda: self._v2_main(dev_id, req))

    def _v2_main(self, dev_id, req):
        app = self.app
        be = self.rep.b
        be.begin()
        self.rep.stats = {"got": 0, "conflicts": 0, "deleted": 0, "keys": set()}
        res = self.rep.handle(dev_id, req)
        be.finish(self.rep.stats, "abgleich")
        with self.lock:
            dev = self.devices.get(dev_id)
            if dev is not None:
                dev["last"] = time.time()
                self._save()
        self._notify()
        return res


def apply_entry(app, kind, n, incoming):
    """Fremden Stand in den vorhandenen Eintrag (gleiches Objekt – der Editor hält eine Referenz darauf)."""
    store = app.stores[kind]
    try:
        store.snapshot(n, force=True)                   # vorheriger Stand bleibt im Verlauf
    except Exception:  # noqa: BLE001
        pass
    old_folder = n.get("folder")
    for k in [k for k in n if k not in LOCAL and k not in incoming]:
        del n[k]
    n.update({k: v for k, v in incoming.items() if k not in LOCAL})
    if n.get("folder") != old_folder and n.get("file_auto"):
        try:
            from core import linked
            app.join_bg()                  # kein Hintergrund-Schreiben an den alten Ort
            linked.move_to_folder(app.prefs, kind, n)
        except Exception as e:  # noqa: BLE001
            log(f"ordner: {e}")
    store.save(n, touch=False)


def create_entry(app, kind, data, conflict=False):
    store = app.stores[kind]
    n = store.create()
    nid = n["id"]
    n.update({k: v for k, v in data.items() if k not in LOCAL})
    if conflict:
        n["id"] = str(uuid.uuid4())
        store.notes.pop(nid, None)
        store.notes[n["id"]] = n
        n["title"] = (n.get("title") or "") + " (konflikt)"
    elif n["id"] != nid:                                 # fremder Eintrag behält seine Id
        store.notes.pop(nid, None)
        store.notes[n["id"]] = n
    n["want_file"] = True
    store.save(n, touch=conflict)
    return n


# ---------- v2: Speicher der App für core/sync2 ----------
TEX_SKIP = (".aux", ".log", ".out", ".toc", ".fls", ".fdb_latexmk", ".synctex.gz", ".synctex", ".bbl", ".blg",
            ".lof", ".lot", ".nav", ".snm", ".xdv", ".sync2", ".part")
PREF_KEYS = ("prefs:folders.notes", "prefs:folders.docs", "prefs:folders.latex", "prefs:words", "prefs:autocorrect")


class AppBackend(sync2.Backend):
    """Einträge, Anhänge und geteilte Einstellungen der laufenden App. Nur im Hauptfaden benutzen (außer
    ref_path/stamp beim Anhang-Empfang: lesen nur)."""

    def __init__(self, app, data=None):
        self.app = app
        self.data = data or paths.DATA
        self.touched, self.deleted = [], 0

    # ----- Hilfen -----
    def _store(self, kind):
        return self.app.stores.get(kind) if kind in KINDS2 else None

    def _entry(self, key):
        kind, _, nid = key.partition(":")
        store = self._store(kind)
        n = store.notes.get(nid) if store is not None else None
        if n is None or not os.path.exists(os.path.join(store.path, nid + ".json")):
            return None
        return n

    def _projdir(self, key, n=None):
        n = n if n is not None else self._entry(key)
        from core import linked
        if n is not None and linked.is_project(n):
            return os.path.dirname(n["file"])
        return os.path.join(self.data, "latex-files", key.partition(":")[2])

    # ----- Abgleich-Rahmen -----
    def begin(self):
        """Vor jeder Runde: offenes Dokument speichern, außen geänderte Dateien einlesen (zählt als eigener Stand)."""
        app = self.app
        app.flush()
        try:
            app.run_sync_file(wait=True)
        except Exception:  # noqa: BLE001
            pass
        for kind in KINDS2:
            store = self._store(kind)
            for n in list(store.notes.values()) if store is not None else []:
                if n.get("file") and not n.get("trashed"):
                    try:
                        if app.reload_if_changed(n, kind):
                            self.touched.append((kind, n, False))
                    except Exception:  # noqa: BLE001
                        pass

    def finish(self, stats, what="abgleich"):
        app = self.app
        reload_current = False
        for kind, n, write in self.touched:
            if n is app.current:
                reload_current = True
            if not write:
                continue
            try:
                from core import linked
                if not n.get("trashed") and not linked.needs_confirm(n):
                    app.sync_file(n, kind, force=True)
            except Exception as e:  # noqa: BLE001
                log(f"datei {n.get('title')!r}: {e}")
        if self.touched or self.deleted:
            app.save_prefs()
            if reload_current and app.current is not None and app.kind_of(app.current) == app.kind:
                try:
                    app.select(app.current["id"], from_list=True)
                except Exception as e:  # noqa: BLE001
                    log(f"neu laden: {e}")
            try:
                app.refresh_home() if app.view == "home" else app.refresh_list()
            except Exception:  # noqa: BLE001
                pass
        got, conf, gone = stats.get("got", 0), stats.get("conflicts", 0), stats.get("deleted", 0)
        if got or conf or gone:
            app.notify(f"{what}: {got} übernommen" + (f", {conf} konflikt" + ("e" if conf != 1 else "") if conf else "")
                       + (f", {gone} gelöscht" if gone else ""))
        self.touched, self.deleted = [], 0

    # ----- Backend -----
    def keys(self):
        out = list(PREF_KEYS)
        for kind in KINDS2:
            store = self._store(kind)
            if store is None:
                continue
            for nid in list(store.notes):
                if os.path.exists(os.path.join(store.path, nid + ".json")):
                    out.append(f"{kind}:{nid}")
        return out

    def stamp(self, key):
        if key.startswith("prefs:"):
            return None
        kind, _, nid = key.partition(":")
        store = self._store(kind)
        try:
            s = os.stat(os.path.join(store.path, nid + ".json"))
        except (OSError, AttributeError):
            return None
        out = [s.st_mtime_ns, s.st_size]
        if kind == "latex":
            files = self.refs(key, self._entry(key) or {})
            for p in sorted(files.values()):
                try:
                    f = os.stat(p)
                    out += [f.st_mtime_ns, f.st_size]
                except OSError:
                    pass
            out.append(len(files))
        return out

    def get(self, key):
        if key.startswith("prefs:"):
            return self._pref_get(key)
        n = self._entry(key)
        return content(n) if n is not None else None

    def put(self, key, c):
        if key.startswith("prefs:"):
            return self._pref_put(key, c)
        kind = key.partition(":")[0]
        cur = self._entry(key)
        if cur is not None:
            apply_entry(self.app, kind, cur, c)
        else:
            stale = self._store(kind).notes.get(key.partition(":")[2])
            if stale is not None:                            # nur im Speicher, nie gespeichert → ersetzen
                self._store(kind).notes.pop(stale["id"], None)
            cur = create_entry(self.app, kind, c)
        self.touched.append((kind, cur, True))

    def delete(self, key):
        n = self._entry(key)
        if n is None:
            return
        app = self.app
        was = n is app.current
        app.stores[key.partition(":")[0]].delete_forever(n)
        if was:
            app.current = None
        self.deleted += 1

    def refs(self, key, c):
        kind = key.partition(":")[0]
        out = {}
        if kind == "docs":
            for blk in c.get("blocks") or []:
                t = blk.get("t") if isinstance(blk, dict) else None
                if t in ("pdf", "sheet") and blk.get("file"):
                    folder = "pdfs" if t == "pdf" else "sheets"
                    name = os.path.basename(str(blk["file"]))
                    p = os.path.join(self.data, folder, name)
                    if os.path.isfile(p):
                        out[f"{folder}/{name}"] = p
        elif kind == "latex":
            n = self._entry(key)
            d = self._projdir(key, n)
            main = os.path.basename(n["file"]) if n is not None and n.get("file") else "main.tex"
            if os.path.isdir(d):
                for root, dirs, files in os.walk(d):
                    dirs[:] = [x for x in dirs if not x.startswith(".")]
                    for f in files:
                        full = os.path.join(root, f)
                        rel = os.path.relpath(full, d).replace(os.sep, "/")
                        stem = os.path.splitext(main)[0]
                        if rel in (main, stem + ".pdf") or f.startswith(".") or f.endswith(TEX_SKIP):
                            continue
                        out["tex/" + rel] = full
                        if len(out) >= 500:
                            return out
        return out

    def ref_path(self, key, name):
        kind = key.partition(":")[0]
        name = str(name)
        parts = name.split("/")
        if any(p in ("", ".", "..") for p in parts) or "\\" in name or os.path.isabs(name):
            return None
        if kind == "docs" and len(parts) == 2 and parts[0] in ("pdfs", "sheets"):
            return os.path.join(self.data, parts[0], parts[1])
        if kind == "latex" and parts[0] == "tex" and len(parts) > 1:
            return os.path.join(self._projdir(key), *parts[1:])
        return None

    # ----- geteilte Einstellungen -----
    def _words_path(self):
        return os.path.join(self.data, "words.txt")

    def _pref_get(self, key):
        name = key.partition(":")[2]
        if name.startswith("folders."):
            made, _ = self.app.folder_prefs(name.partition(".")[2])
            return {"v": sorted(set(made))}
        if name == "words":
            try:
                with open(self._words_path(), encoding="utf-8") as f:
                    return {"v": sorted({w.strip() for w in f if w.strip()})}
            except OSError:
                return {"v": []}
        if name == "autocorrect":
            return {"v": dict(self.app.prefs.get("autocorrect") or {})}
        return None

    def _pref_put(self, key, c):
        name = key.partition(":")[2]
        v = c.get("v")
        if name.startswith("folders.") and isinstance(v, list):
            made, _ = self.app.folder_prefs(name.partition(".")[2])
            made[:] = [f for f in v if isinstance(f, str) and f.strip()]
            self.app.save_prefs()
        elif name == "words" and isinstance(v, list):
            tmp = self._words_path() + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                f.write("".join(str(w).strip() + "\n" for w in v if str(w).strip()))
            os.replace(tmp, self._words_path())
            import sys
            sp = sys.modules.get("spell")
            if sp is not None and hasattr(sp, "reload_words"):
                try:
                    sp.reload_words()
                except Exception:  # noqa: BLE001
                    pass
        elif name == "autocorrect" and isinstance(v, dict):
            self.app.prefs["autocorrect"] = {str(k): str(x) for k, x in v.items()}
            self.app.save_prefs()

    def merge(self, key, a, b):
        if not key.startswith("prefs:"):
            return None
        va, vb = a.get("v"), b.get("v")
        if isinstance(va, list) and isinstance(vb, list):
            return {"v": sorted(set(map(str, va)) | set(map(str, vb)))}
        if isinstance(va, dict) and isinstance(vb, dict):
            out = dict(va)
            for k, x in vb.items():
                out[k] = max(out[k], x, key=sync2.canon) if k in out else x
            return {"v": out}
        return None


# ---------- v2: Client (Rechner↔Rechner ab Schritt 10; Tests) ----------
def _post(host, port, path, body, headers=None, timeout=120):
    import http.client
    c = http.client.HTTPConnection(host, port, timeout=timeout)
    try:
        c.request("POST", path, body=body, headers={"Content-Type": "application/octet-stream", **(headers or {})})
        r = c.getresponse()
        return r.status, r.read()
    finally:
        c.close()


def _post_json(host, port, path, obj):
    code, raw = _post(host, port, path, json.dumps(obj).encode(), {"Content-Type": "application/json"}, timeout=30)
    try:
        res = json.loads(raw or b"{}")
    except ValueError:
        res = {}
    if code != 200:
        raise RuntimeError(res.get("error") or f"gegenstelle antwortet {code}")
    return res


def client_pair(host, code, port=PORT, name=None):
    """Mit einem anderen notist koppeln (Code von dort). → Eintrag {host, port, id, key, name} für PEERS."""
    st, X = sync2.pake_client_start(code)
    r1 = _post_json(host, port, "/v2/pair1", {"X": X, "kind": "pc", "name": name or socket.gethostname().split(".")[0]})
    key, cli, srv = sync2.pake_client_finish(st, r1["Y"])
    r2 = _post_json(host, port, "/v2/pair2", {"X": X, "c": cli})
    if not sync2.pake_check(srv, r2.get("s")):
        raise RuntimeError("gegenstelle konnte den code nicht beweisen")
    return {"host": host, "port": port, "id": r2["id"], "key": key.hex(), "name": r1.get("name") or "pc"}


def client_call(peer):
    """Transport für Replica.run: verschlüsselte Anfrage an /v2."""
    key = bytes.fromhex(peer["key"])

    def call(req):
        code, raw = _post(peer["host"], peer.get("port", PORT), "/v2",
                          box(key, json.dumps(req, ensure_ascii=False).encode()), {"X-Dev": peer["id"]})
        if code != 200:
            try:
                msg = json.loads(raw).get("error")
            except ValueError:
                msg = None
            if code == 409:
                raise sync2.Refused(msg or "abgelehnt")
            raise RuntimeError(msg or f"gegenstelle antwortet {code}")
        return json.loads(unbox(key, raw))
    return call
