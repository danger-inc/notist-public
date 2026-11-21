#!/usr/bin/env python3
# Gemeinsames Bearbeiten über die Handy-Schnittstelle (core/api m_collab_*) ohne Emulator: lokaler musicalist-Server,
# „bernd“ = Handy-Kern (wie Kotlin ihn aufruft: push/pull), „anna“ = Live-Client mit Speicher-Editor.
#   python tests/mobile_collab_test.py <server-binary>
import base64, hashlib, json, os, socket, subprocess, sys, tempfile, threading, time, urllib.request

APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T = tempfile.mkdtemp(prefix="notist-mcollab-")
os.makedirs(os.path.join(T, "h"))
os.environ.update(HOME=os.path.join(T, "h"), NOTES_HOME=os.path.join(T, "notist"), NOTES_NO_TIMERS="1")
os.environ.pop("NOTES_DATA_DIR", None)
sys.path.insert(0, APP)
sys.modules.setdefault("gi", None)
RES = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(f"  {'✓' if ok else '✗'} {name}" + (f" – {info}" if info and not ok else ""), flush=True)


with socket.socket() as s_:
    s_.bind(("127.0.0.1", 0))
    PORT = s_.getsockname()[1]
URL = f"http://127.0.0.1:{PORT}"
SD = os.path.join(T, "server")
srv = subprocess.Popen([sys.argv[1], "-addr", f"127.0.0.1:{PORT}", "-data", SD, "-pow-bits", "4"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def http(m, p, b=None, t=None):
    r = urllib.request.Request(URL + p, data=None if b is None else json.dumps(b).encode(), method=m)
    r.add_header("Content-Type", "application/json")
    if t:
        r.add_header("Authorization", "Bearer " + t)
    return json.loads(urllib.request.urlopen(r, timeout=10).read() or b"{}")


def reg(n):
    c = http("GET", "/v1/challenge")
    raw = base64.urlsafe_b64decode(c["challenge"] + "=" * (-len(c["challenge"]) % 4))[:24]
    k = 0
    while int.from_bytes(hashlib.sha256(raw + n.encode() + k.to_bytes(8, "big")).digest()[:4], "big") >> (32 - c["bits"]):
        k += 1
    http("POST", "/v1/account", {"name": n, "password": "ein-gutes-passwort", "challenge": c["challenge"], "nonce": k, "label": "t"})


def until(cond, sec=10):
    end = time.monotonic() + sec
    while time.monotonic() < end:
        v = cond()
        if v:
            return v
        time.sleep(0.05)
    return None


def main():
    for _ in range(100):
        try:
            http("GET", "/v1/health")
            break
        except Exception:  # noqa: BLE001
            time.sleep(0.1)
    reg("anna")
    reg("bernd")
    adm = open(os.path.join(SD, "admin-secret")).read().strip()
    from core import api, collab as C
    api.m_start()
    os.makedirs(os.environ["NOTES_HOME"], exist_ok=True)
    with open(os.path.join(os.environ["NOTES_HOME"], "collab.json"), "w") as f:
        json.dump({"server": URL}, f)
    # anna (Rechner): lädt bernd zu einem Words-Dokument ein
    A = C.Account(None)
    A.st["server"] = URL
    A.login("anna", "ein-gutes-passwort")
    adoc = {"d": C.blocks_to_doc([{"t": "p", "style": "h1", "runs": [{"text": "Plan"}]},
                                  {"t": "p", "runs": [{"text": "erste Zeile"}]}])}
    lock = threading.RLock()
    s = A.invite("docs", "Plan", "docs:anna-1", ["bernd"])
    http("POST", f"/admin/collab/{s['id']}", {"action": "approve"}, adm)
    alive = C.Live(A, s["id"], True, lambda: C.deep(adoc["d"]), lambda d, doc: adoc.__setitem__("d", C.apply(adoc["d"], d)),
                   lambda fn: (lock.acquire(), fn(), lock.release()), key=A.key_for(s))
    alive.start()
    # bernd (Handy-Kern)
    check("anmelden", api.m_collab_login("bernd", "ein-gutes-passwort")["name"] == "bernd")
    ss = api.m_collab_sessions()
    check("einladung sichtbar", len(ss["sessions"]) == 1 and ss["sessions"][0]["key"] is None, str(ss))
    check("falscher code abgelehnt", api.m_collab_accept(s["id"], "kaputt").get("error"))
    acc = api.m_collab_accept(s["id"], A.code_for(s))
    check("annehmen legt eintrag an", acc.get("kind") == "docs" and api.m_get("docs", acc["id"]) is not None, str(acc))
    api.m_collab_sessions()
    # im Hintergrund landet annas Stand schon im gespeicherten Eintrag (oder kommt nach dem Öffnen per pull)
    until(lambda: "Plan" in json.dumps(api.m_get("docs", acc["id"]).get("blocks")), 15)
    entry = api.m_get("docs", acc["id"])
    check("verbinden", api.m_collab_bind("docs", acc["id"], entry)["sid"] == s["id"])
    gen = 0
    r = until(lambda: (lambda x: x if x.get("entry") else None)(api.m_collab_pull(gen)), 2)
    if r:
        entry, gen = r["entry"], r["gen"]
    check("handy bekommt annas stand", "Plan" in json.dumps(entry["blocks"]), str(entry)[:300])
    # bernd tippt (Kotlin: Eintrag ändern + push)
    entry["blocks"][1]["runs"] = [{"text": "erste Zeile vom handy"}]
    api.m_collab_push(entry, gen)
    check("anna sieht handy-änderung", until(lambda: "vom handy" in C.text_of(adoc["d"]), 15), C.text_of(adoc["d"]))
    # gleichzeitig: anna tippt, bernd tippt auf veraltetem Stand (hat annas Änderung noch nicht abgeholt)
    with lock:
        adoc["d"] = C.apply(adoc["d"], [{"insert": "A: "}])
        alive.local_changed()
    until(lambda: api.m_collab_pull(gen, -1, False).get("gen", 0) > gen and False, 1.5)     # Zeit lassen, ohne abzuholen
    stale = json.loads(json.dumps(entry))
    stale["blocks"].append({"t": "p", "style": "normal", "align": "left", "list": None, "indent": 0, "spacing": 1.15,
                            "runs": [{"text": "neue zeile handy"}]})
    api.m_collab_push(stale, gen)
    def both():
        x = api.m_collab_pull(gen)
        if x.get("entry"):
            both.e, both.g = x["entry"], x["gen"]
        e = getattr(both, "e", None)
        t = C.text_of(C.blocks_to_doc(e["blocks"])) if e else ""
        return t if (t == C.text_of(adoc["d"]) and "A: " in t and "neue zeile handy" in t) else None
    got = until(both, 15)
    check("veralteter push wird gehoben, beide gleich", got, f"handy={getattr(both, 'e', None)} anna={C.text_of(adoc['d'])}")
    # Tippen in mehreren Schüben, dazwischen fremde Änderungen, die das Handy erst danach abholt (Emulator-Fund)
    entry = both.e
    for i, word in enumerate(("katze", "hund", "maus")):
        with lock:
            adoc["d"] = C.apply(adoc["d"], [{"retain": C.doc_len(adoc["d"]) - 1}, {"insert": f" [anna{i}]"}])
            alive.local_changed()
        time.sleep(0.6)
        for ch in " " + word:
            entry["blocks"][1]["runs"][0]["text"] += ch
            api.m_collab_push(entry, 0)
            api.m_collab_pull(0, -1, False)                 # tippt gerade: nichts ausliefern
    def merged():
        x = api.m_collab_pull(0, -1, True)
        if x.get("entry"):
            merged.e = x["entry"]
        e = getattr(merged, "e", None)
        t = C.text_of(C.blocks_to_doc(e["blocks"])) if e else ""
        return t if (t == C.text_of(adoc["d"]) and all(w in t for w in (" katze", " hund", " maus", "[anna2]"))) else None
    check("schübe beim tippen gehen nicht verloren", until(merged, 15),
          f"handy={C.text_of(C.blocks_to_doc(merged.e['blocks'])) if getattr(merged, 'e', None) else None} anna={C.text_of(adoc['d'])}")
    both.g = 0
    alive.cursor(2)
    check("anna als anwesend sichtbar", until(lambda: "anna" in api.m_collab_pull(both.g).get("online", []), 10))
    check("lösen", api.m_collab_unbind())
    # Editor zu: Verbindung bleibt, annas Änderungen landen im gespeicherten Eintrag
    with lock:
        adoc["d"] = C.apply(adoc["d"], [{"retain": C.doc_len(adoc["d"]) - 1}, {"insert": " im hintergrund"}])
        alive.local_changed()
    check("im hintergrund: eintrag wird aktualisiert",
          until(lambda: "im hintergrund" in json.dumps(api.m_get("docs", acc["id"]).get("blocks")), 15))
    x = api.m_collab_pull(0)
    check("pull ohne gebundenen editor meldet ended", x.get("ended"))
    api.m_collab_bind("docs", acc["id"], api.m_get("docs", acc["id"]))
    p = api.m_collab_pull(0)
    check("farben + namen für die leiste", len(p.get("people", [])) == 2 and all(q["color"].startswith("#") for q in p["people"]),
          str(p.get("people")))
    check("trennen", api.m_collab_end(s["id"]).get("ok") and not api._CO["conns"])
    alive.close()
    srv.terminate()
    srv.wait(5)
    print(f"{'✓' if all(RES) else '✗'} mobile_collab_test: {sum(RES)}/{len(RES)} grün")
    sys.exit(0 if all(RES) else 1)


if __name__ == "__main__":
    main()
