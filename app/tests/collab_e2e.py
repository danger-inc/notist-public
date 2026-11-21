#!/usr/bin/env python3
# Gemeinsames Bearbeiten Ende-zu-Ende: lokaler musicalist-Server (Testinstanz), echte notist-Oberfläche (Testdaten)
# als „anna“ und ein zweites Gerät „bernd“ (core.collab.Live mit einem Speicher-Editor) – für Words, Notiz, LaTeX.
#   python tests/collab_e2e.py <pfad zum server-binary>
# Fasst den Live-Server und die echten Daten nicht an.
import base64, hashlib, json, os, socket, subprocess, sys, tempfile, threading, time, urllib.request

APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T = tempfile.mkdtemp(prefix="notist-collab-")
os.environ.update(NOTES_HOME=T, NOTES_DATA_DIR=os.path.join(T, "data"), NOTES_APP_ID="de.test.NotistCollab",
                  NOTES_NO_TIMERS="1", XDG_CACHE_HOME=os.path.join(T, "c"), XDG_CONFIG_HOME=os.path.join(T, "cf"),
                  NOTES_DOCS_DIR=os.path.join(T, "Dok"))
os.makedirs(os.path.join(T, "data"), exist_ok=True)
with open(os.path.join(T, "data", "prefs.json"), "w") as f:
    f.write("{}")
sys.path.insert(0, APP)

BIN = sys.argv[1]
with socket.socket() as s_:
    s_.bind(("127.0.0.1", 0))
    PORT = s_.getsockname()[1]
URL = f"http://127.0.0.1:{PORT}"
SDATA = os.path.join(T, "server")
srv = subprocess.Popen([BIN, "-addr", f"127.0.0.1:{PORT}", "-data", SDATA, "-pow-bits", "4"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
OK, BAD = [], []


def ok(cond, what):
    (OK if cond else BAD).append(what)
    print(("  ✓ " if cond else "  ✗ ") + what, flush=True)


def http(method, path, body=None, tok=None):
    r = urllib.request.Request(URL + path, data=None if body is None else json.dumps(body).encode(), method=method)
    r.add_header("Content-Type", "application/json")
    if tok:
        r.add_header("Authorization", "Bearer " + tok)
    with urllib.request.urlopen(r, timeout=10) as resp:
        return json.loads(resp.read() or b"{}")


def register(name):
    c = http("GET", "/v1/challenge")
    raw = base64.urlsafe_b64decode(c["challenge"] + "=" * (-len(c["challenge"]) % 4))[:24]
    n = 0
    while True:
        h = hashlib.sha256(raw + name.encode() + n.to_bytes(8, "big")).digest()
        if int.from_bytes(h[:4], "big") >> (32 - c["bits"]) == 0:
            break
        n += 1
    return http("POST", "/v1/account", {"name": name, "password": "ein-gutes-passwort", "challenge": c["challenge"],
                                        "nonce": n, "label": "test"})["token"]


for _ in range(100):
    try:
        http("GET", "/v1/health")
        break
    except Exception:  # noqa: BLE001
        time.sleep(0.1)
register("anna")
register("bernd")
with open(os.path.join(SDATA, "admin-secret")) as _f:
    ADMIN = _f.read().strip()
with open(os.path.join(T, "collab.json"), "w") as f:
    json.dump({"server": URL}, f)

import gi  # noqa: E402
gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk  # noqa: E402
import notes  # noqa: E402
from core import collab as C  # noqa: E402


def pump(sec=0.3):
    end = time.monotonic() + sec
    while time.monotonic() < end:
        GLib.MainContext.default().iteration(False)
        time.sleep(0.005)


def until(cond, sec=10):
    end = time.monotonic() + sec
    while time.monotonic() < end:
        if cond():
            return True
        pump(0.05)
    return False


class Bernd:
    """Zweites Gerät ohne Oberfläche: Editor = Delta im Speicher."""
    def __init__(self, sid, code):
        self.acct = C.Account(None)
        self.acct.st["server"] = URL
        self.acct.login("bernd", "ein-gutes-passwort")
        self.acct.set_code(sid, code)
        self.doc = [{"insert": "\n"}]
        self.lock = threading.RLock()
        self.live = C.Live(self.acct, sid, False, lambda: C.deep(self.doc), self._apply, self._post,
                           key=self.acct.key_for({"id": sid, "owner": "anna"}))
        self.live.start()

    def _post(self, fn):
        with self.lock:
            fn()

    def _apply(self, d, doc):
        self.doc = C.apply(self.doc, d)

    def edit(self, d):
        with self.lock:
            self.doc = C.apply(self.doc, d)
            self.live.local_changed()


def run(app):
    cu = app.collab
    cu.acct.login("anna", "ein-gutes-passwort")
    ok(cu.acct.name == "anna", "anmelden mit musicalist-konto")
    for kind in (os.environ.get("KINDS") or "docs,notes,latex").split(","):
        print(f"— {kind}", flush=True)
        app.set_kind(kind)
        app.new_note()
        pump(0.3)
        n = app.current
        n["title"] = f"Gemeinsam {kind}"
        if kind == "docs":
            w = app.writer
            w.buf.insert(w.buf.get_end_iter(), "Erste Zeile\nZweite Zeile")
        elif kind == "latex":
            app.latex.main_buf.set_text("\\documentclass{article}\n\\begin{document}\nHallo\n\\end{document}\n")
        else:
            app.text.get_buffer().set_text("☐ Milch\n☐ Brot")
        app.on_edit()
        app.flush(force=True)
        cu.invite(["bernd"])
        ok(until(lambda: any(s["status"] == "pending" and s["kind"] == kind for s in cu.sessions)), "einladung wartet auf freigabe")
        sid = next(s["id"] for s in cu.sessions if s["kind"] == kind and s["status"] == "pending")
        ok(cu.bound() is None, "vor der freigabe keine live-verbindung")
        http("POST", f"/admin/collab/{sid}", {"action": "approve"}, ADMIN)
        cu.refresh()
        ok(until(lambda: cu.bound() is not None and cu.bound().live.ready), "nach freigabe live, stand hochgeladen")
        ok(until(lambda: cu.banner.get_reveal_child() and "Live" in cu.b_live.get_label()), "live-leiste sichtbar")
        import glob as _g
        ok(len(_g.glob(os.path.join(app.store.history_dir(n), "*.json"))) >= 1, "vor der sitzung eine version gesichert")
        ok(app.writer.author_name() == "anna", "änderungen verfolgen: autor = kontoname")
        code = cu.acct.code_for({"id": sid, "owner": "anna"})
        raw = json.dumps(http("GET", f"/v1/collab/{sid}/doc", tok=cu.acct.token))
        probe = {"docs": "Zweite Zeile", "notes": "Milch", "latex": "documentclass"}[kind]
        ok(probe not in raw and '"e"' in raw, "server sieht nur verschlüsselte daten")
        b = Bernd(sid, code)
        mine = lambda: C.text_of(cu.get_doc(cu.bound()))
        ok(until(lambda: b.live.ready and C.text_of(b.doc) == mine()), "bernd bekommt den stand")
        # gleichzeitig: anna tippt am Anfang, bernd hängt hinten an
        buf = cu.buf(kind)
        buf.insert(buf.get_start_iter(), "A-")
        app.on_edit()
        L = C.doc_len(b.doc)
        b.edit([{"retain": L - 1}, {"insert": " (bernd)"}])
        ok(until(lambda: mine() == C.text_of(b.doc) and "A-" in mine() and "(bernd)" in mine(), 25),
           "gleichzeitige änderungen kommen bei beiden an")
        if os.environ.get("DBG"):
            print("   anna:", repr(mine()), "\n   bernd:", repr(C.text_of(b.doc)), "\n   live.doc:", repr(C.text_of(cu.bound().live.doc)), flush=True)
        if kind == "docs":
            b.edit([{"retain": 2}, {"retain": 5, "attributes": {"b": True}}])
            ok(until(lambda: any(r.get("b") for bl in app.writer.to_model() for r in bl.get("runs", []))),
               "fett von bernd erscheint im writer")
            b.edit([{"retain": C.doc_len(b.doc) - 1}, {"insert": "\n"}, {"insert": {"block": {"t": "hr"}}}, {"insert": "\n"}])
            ok(until(lambda: any(bl.get("t") == "hr" for bl in app.writer.to_model())), "linie (objekt) von bernd")
            ok(until(lambda: C.text_of(cu.get_doc(cu.bound())) == C.text_of(b.doc)), "danach wieder gleich")
            # Tabelle: anna und bernd ändern gleichzeitig verschiedene Zellen
            w = app.writer
            w.buf.place_cursor(w.buf.get_end_iter())
            w.insert_table(2, 2)
            app.on_edit()
            tbl = lambda bl: next((x for x in bl if x.get("t") == "table"), None)
            ok(until(lambda: tbl(C.doc_to_blocks(b.doc)) is not None, 15), "tabelle kommt bei bernd an")
            tb = next(x for x in w.blocks.values() if x.kind == "table")
            tb.cells[0][0].tv.get_buffer().set_text("anna-zelle")
            pos = next(i for i, ch in enumerate(C._items(b.doc)) if isinstance(ch[0], dict) and ch[0].get("block", {}).get("t") == "table")
            b.edit([{"retain": pos}, {"retain": 1, "attributes": {"c:1:1": "bernd-zelle"}}])
            both = lambda: (lambda t1, t2: t1 and t2 and t1["rows"] == t2["rows"] and t1["rows"][0][0] == "anna-zelle"
                            and t1["rows"][1][1] == "bernd-zelle")(tbl(w.to_model()), tbl(C.doc_to_blocks(b.doc)))
            ok(until(both, 20), "zellen von beiden bleiben erhalten")
        # Cursor von bernd wird angezeigt
        b.live.cursor(1)
        def tags_shown():
            view = cu.view(kind)
            out, stack = [], [view.get_first_child()] if view else []
            while stack:
                w = stack.pop()
                while w is not None:
                    if isinstance(w, Gtk.Label) and w.get_label() == "bernd" and w.get_mapped():
                        out.append(w)
                    stack.append(w.get_first_child())
                    w = w.get_next_sibling()
            return out
        ok(until(lambda: [x.get("by") for x in cu.bound().cursors] == ["bernd"] and len(tags_shown()) == 1), "cursor von bernd als farbige linie sichtbar")
        y0 = tags_shown()[0].compute_bounds(cu.view(kind))[1].get_x() if tags_shown() else None
        for pos in (2, 5, 4):                    # mehrmals bewegen: immer genau EIN Schild, das mitwandert
            b.live.cursor(pos)
            pump(0.8)
        ok(until(lambda: len(tags_shown()) == 1 and any(c.get("i") == 4 for c in cu.bound().cursors)), "nach mehreren bewegungen genau ein schild")
        x1 = tags_shown()[0].compute_bounds(cu.view(kind))[1].get_x() if tags_shown() else None
        ok(x1 is not None and x1 != y0, f"schild wandert mit ({y0} → {x1})")
        chips = []
        ch_ = cu.b_chips.get_first_child()
        while ch_:
            chips.append(ch_.get_label()); ch_ = ch_.get_next_sibling()
        ok(chips == ["du", "bernd"], f"namen in der leiste {chips}")
        # Hintergrund: anderes Dokument offen, bernd schreibt weiter → landet im gespeicherten Eintrag
        if kind == "notes":
            app.new_note(); pump(0.5)
            b.edit([{"retain": C.doc_len(b.doc) - 1}, {"insert": " hintergrund"}])
            ok(until(lambda: "hintergrund" in (app.store.notes[n["id"]].get("text") or ""), 15), "änderung kommt auch bei geschlossenem dokument an")
            app.home_open(kind, n["id"]); pump(0.5)
        app.flush(force=True)
        saved = app.store.notes[n["id"]]
        ok("(bernd)" in (saved.get("text") or ""), "gemeinsamer stand wird gespeichert")
        b.live.close()
        cu.end(next(s for s in cu.sessions if s["id"] == sid))
        ok(until(lambda: cu.bound() is None and not cu.banner.get_reveal_child()), "beenden löst die verbindung")


def main():
    app = notes.Notes()

    def go(a):
        def tick():
            try:
                a.win.set_size_request(1200, 800)
                run(a)
            except Exception:  # noqa: BLE001
                import traceback
                traceback.print_exc()
                BAD.append("ausnahme")
            finally:
                a.quit()
            return False
        GLib.timeout_add(500, tick)
    app.connect("activate", go)
    try:
        app.run([sys.argv[0]])
    finally:
        srv.terminate()
        srv.wait(5)
    print(f"{'✓' if not BAD else '✗'} collab_e2e: {len(OK)}/{len(OK) + len(BAD)} grün")
    sys.exit(1 if BAD else 0)


if __name__ == "__main__":
    main()
