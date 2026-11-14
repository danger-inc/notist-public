# notist – Abgleich von Rechner zu Rechner (Plan Schritt 10). GTK-frei bis auf den Zeitgeber (GLib nur in start()).
#
# Jeder Rechner kann Server (zeigt einen Code, wird angesprochen – core/handylink.Server) UND Client sein (tippt den
# Code eines anderen ein, spricht ihn danach selbst an). Der Client hält Gegenstellen in sync-peers.json
# ({id: {name, host, port, id, key, fixed, me, last, err}}), gleicht per sync2.Replica.run ab – alle N Minuten,
# beim Fokus und auf Knopfdruck – und findet eine Gegenstelle nach Adresswechsel wieder (mDNS, sonst /24-Suche;
# feste Adressen/Tailscale-Namen werden nie umgeschrieben).
# Verknüpfte Dateien bleiben je Gerät eigen: handylink.LOCAL wird nie übertragen; neue Einträge bekommen am Ziel ihre
# Datei im notist-Ordner (create_entry setzt want_file).
import json, os, socket, threading, time

from core import handylink as hl
from core import sync2

DEFAULT_MIN = 10                 # Abgleich alle … Minuten (0 = nur auf Knopfdruck/Fokus)
FOCUS_GAP = 60                   # beim Fokus höchstens alle … Sekunden
CHOICES = (0, 5, 10, 30, 60)


def split_addr(text, default=None):
    """„name“, „name:port“, „1.2.3.4“, „[::1]:1“ → (host, port). Leer → (None, None)."""
    t = (text or "").strip()
    for p in ("http://", "https://"):
        if t.startswith(p):
            t = t[len(p):]
    t = t.split("/")[0]
    if not t:
        return None, None
    port = default or hl.PORT
    if t.startswith("["):
        host, _, rest = t[1:].partition("]")
        if rest.startswith(":") and rest[1:].isdigit():
            port = int(rest[1:])
        return host, port
    if t.count(":") == 1:
        host, _, p = t.partition(":")
        if p.isdigit():
            return host, int(p)
        return host, port
    return t, port


def _hello(host, port, timeout=1.2):
    import http.client
    c = http.client.HTTPConnection(host, port, timeout=timeout)
    try:
        c.request("GET", "/hello")
        r = c.getresponse()
        d = json.loads(r.read() or b"{}")
        return d if r.status == 200 and d.get("app") == "notist" else None
    except (OSError, ValueError, http.client.HTTPException):
        return None
    finally:
        c.close()


class Peers:
    def __init__(self, server):
        self.srv = server
        self.lock = threading.Lock()
        self.peers = self._load()
        self.busy = set()
        self.last_try = {}
        self.timer = 0
        self.last_focus = 0

    # ----- Gegenstellen -----
    def _load(self):
        try:
            with open(hl.PEERS, encoding="utf-8") as f:
                d = json.load(f)
            return d if isinstance(d, dict) else {}
        except (OSError, ValueError):
            return {}

    def _save(self):
        tmp = hl.PEERS + ".tmp"
        with open(os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w", encoding="utf-8") as f:
            json.dump(self.peers, f)
        os.replace(tmp, hl.PEERS)

    def remove(self, pid):
        with self.lock:
            self.peers.pop(pid, None)
            self._save()
        self.srv._notify()

    def interval(self):
        v = (self.srv.app.prefs.get("handy") or {}).get("peer_min", DEFAULT_MIN)
        return v if isinstance(v, int) and v >= 0 else DEFAULT_MIN

    # ----- Suchen -----
    def own_ips(self):
        return set(hl.local_ips()) | {"127.0.0.1"}

    def discover(self, wait=2.0, scan=True):
        """Notist-Rechner im Netz: mDNS (wenn zeroconf da), sonst /24-Suche. → [{host, port, id, name, pairing}]"""
        found = {}

        def add(host, port):
            if (host, port) in found:
                return
            h = _hello(host, port)
            if h and h.get("id") != self.srv.rep.me:
                found[(host, port)] = {"host": host, "port": port, "id": h.get("id"), "name": h.get("name") or host,
                                       "pairing": bool(h.get("pairing"))}
        for host, port in self._mdns(wait):
            add(host, port)
        if not found and scan:
            ips = [i for i in hl.local_ips() if i.count(".") == 3]
            for host, port in self._scan(ips):
                add(host, port)
        return list(found.values())

    def _mdns(self, wait):
        try:
            from zeroconf import IPVersion, ServiceBrowser, Zeroconf
        except ImportError:
            return []
        out = []

        class L:
            def __init__(self, zc):
                self.zc = zc

            def add_service(self, zc, typ, name):
                try:
                    info = zc.get_service_info(typ, name, timeout=1000)
                    for a in (info.parsed_addresses() if info else []):
                        out.append((a, info.port))
                except Exception:  # noqa: BLE001
                    pass

            def update_service(self, *a):
                pass

            def remove_service(self, *a):
                pass
        zc = None
        try:
            zc = Zeroconf(ip_version=IPVersion.V4Only)
            ServiceBrowser(zc, "_notist._tcp.local.", L(zc))
            time.sleep(wait)
        except Exception as e:  # noqa: BLE001
            hl.log(f"mdns-suche: {e}")
        finally:
            if zc is not None:
                try:
                    zc.close()
                except Exception:  # noqa: BLE001
                    pass
        own = self.own_ips()
        return [(h, p) for h, p in dict.fromkeys(out) if h not in own]

    def _scan(self, ips):
        from concurrent.futures import ThreadPoolExecutor
        own = self.own_ips()
        cands = []
        for ip in ips:
            pre = ip.rsplit(".", 1)[0]
            cands += [f"{pre}.{i}" for i in range(1, 255) if f"{pre}.{i}" not in own]

        def probe(host):
            s = socket.socket()
            s.settimeout(0.4)
            try:
                return host if s.connect_ex((host, hl.PORT)) == 0 else None
            except OSError:
                return None
            finally:
                s.close()
        with ThreadPoolExecutor(64) as ex:
            return [(h, hl.PORT) for h in ex.map(probe, cands) if h]

    # ----- Koppeln -----
    def pair(self, addr, code, name=None):
        """Code des anderen Rechners eintippen. addr leer → im Netz suchen und den nehmen, der „koppeln“ zeigt."""
        code = (code or "").replace("-", "").replace(" ", "").upper()
        if len(code) != 8:
            raise RuntimeError("der code hat 8 zeichen (z. B. ABCD-2345)")
        host, port = split_addr(addr)
        fixed = bool(host)
        if host:
            cands = [{"host": host, "port": port}]
        else:
            cands = [c for c in self.discover() if c["pairing"]]
            if not cands:
                raise RuntimeError("kein rechner gefunden, der gerade „koppeln“ zeigt – adresse eintippen?")
        err = None
        for c in cands:
            try:
                p = hl.client_pair(c["host"], code, c["port"], name=name)
            except (OSError, RuntimeError) as e:
                err = e
                continue
            p.update(fixed=fixed, last=None, err=None, me=None, added=time.time())
            h = _hello(p["host"], p["port"])
            if h:
                p["me"] = h.get("id")
            with self.lock:
                self.peers[p["id"]] = p
                self._save()
            self.srv._notify()
            return p
        if isinstance(err, OSError):
            raise RuntimeError(f"{cands[0]['host']} antwortet nicht ({err.strerror or err})")
        raise err or RuntimeError("koppeln fehlgeschlagen")

    # ----- Abgleich -----
    def _relocate(self, p):
        """Adresse einer nicht festen Gegenstelle neu finden (über ihre Kennung)."""
        if p.get("fixed") or not p.get("me"):
            return False
        for c in self.discover():
            if c["id"] == p["me"] and (c["host"], c["port"]) != (p["host"], p["port"]):
                with self.lock:
                    p["host"], p["port"] = c["host"], c["port"]
                    self._save()
                return True
        return False

    def sync(self, pid, manual=False):
        """Ein Abgleich mit einer Gegenstelle (blockiert – im Arbeitsfaden aufrufen). → Statistik; wirft bei Fehler."""
        p = self.peers.get(pid)
        if p is None:
            raise RuntimeError("gegenstelle unbekannt")
        with self.lock:
            if pid in self.busy:
                raise RuntimeError("läuft schon")
            self.busy.add(pid)
        self.last_try[pid] = time.time()
        srv, rep = self.srv, self.srv.rep
        be = rep.b
        try:
            try:
                st = self._run(p, rep, be, srv)
            except OSError as e:
                if not self._relocate(p):
                    raise
                st = self._run(p, rep, be, srv)
            with self.lock:
                p["last"], p["err"] = time.time(), None
                p["me"] = st.get("peer") or p.get("me")
                self._save()
            if manual and not (st["got"] or st["conflicts"] or st["deleted"]):
                srv.run_main(lambda: srv.app.notify(f"abgleich mit {p.get('name') or 'rechner'}: alles aktuell"))
            hl.log(f"peer {p.get('name')}: {st['got']} übernommen, {st['conflicts']} konflikte, {st['deleted']} gelöscht")
            return st
        except Exception as e:  # noqa: BLE001
            msg = self._why(e)
            with self.lock:
                p["err"] = msg
                self._save()
            hl.log(f"peer {p.get('name')}: {msg} ({e!r})")
            raise
        finally:
            with self.lock:
                self.busy.discard(pid)
            srv._notify()

    @staticmethod
    def _why(e):
        if isinstance(e, ConnectionRefusedError):
            return "nicht erreichbar (notist dort aus?)"
        if isinstance(e, (socket.timeout, TimeoutError)):
            return "keine antwort"
        if isinstance(e, socket.gaierror):
            return "adresse unbekannt"
        if isinstance(e, OSError):
            return "nicht erreichbar"
        return str(e) or e.__class__.__name__

    def _run(self, p, rep, be, srv):
        on_main = srv.run_main
        on_main(be.begin)
        try:
            st = rep.run(hl.client_call(p), on_main=on_main)
        finally:
            on_main(lambda: be.finish(rep.stats, "abgleich"))
        return st

    def sync_bg(self, pid, manual=False, done=None):
        def work():
            try:
                res = self.sync(pid, manual)
            except Exception as e:  # noqa: BLE001
                res = e
            if done:
                done(res)
        threading.Thread(target=work, daemon=True, name="peer-sync").start()

    def sync_due(self, gap=None):
        """Alle Gegenstellen, deren letzter Versuch länger her ist als das Intervall (gap Sekunden)."""
        now = time.time()
        gap = self.interval() * 60 if gap is None else gap
        for pid in list(self.peers):
            if pid not in self.busy and now - self.last_try.get(pid, 0) >= gap:
                self.sync_bg(pid)

    # ----- Zeitgeber -----
    def start(self):
        """Alle 30 s nachsehen, ob ein Abgleich fällig ist (erste Runde kurz nach dem Start)."""
        if self.timer:
            return
        from gi.repository import GLib

        def tick():
            if self.interval() > 0:
                self.sync_due()
            return True
        self.timer = GLib.timeout_add_seconds(30, tick)
        GLib.timeout_add_seconds(8, lambda: (self.interval() > 0 and self.sync_due(), False)[1])

    def on_focus(self):
        now = time.time()
        if self.peers and now - self.last_focus > 5:
            self.last_focus = now
            self.sync_due(FOCUS_GAP)
