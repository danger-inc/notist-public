# notist – gemeinsames Bearbeiten (GTK-frei: PC, Mac und Handy über Chaquopy).
#
# Dokument = „Delta“ wie bei quill-delta: Liste von {"insert": text|objekt, "attributes": {...}} (nur Einfügungen).
# Änderung = Delta aus retain/insert/delete. Absätze enden mit "\n", dessen Attribute die Absatzformate sind; Bilder,
# Fußnoten und Tabellen sind Objekte (Länge 1, wie das U+FFFC im Editor) → Positionen im Delta = Positionen im Editor.
#
# Zusammenführen (Operational Transformation, Client-seitig): Der Server reiht Änderungen nur (rev 1, 2, …). Jede App
# rechnet für jede Änderung p die „kanonische“ Form aus, indem sie sie über die kanonischen Formen base+1 … p-1
# transformiert (frühere gewinnen bei gleicher Stelle). Eigene, noch unbestätigte Änderungen (inflight/buffer) werden
# über jede fremde Änderung transformiert – wie bei ot.js, nur ohne Rechnen auf dem Server.
import base64, copy, difflib, hashlib, hmac, json, os, secrets, threading, time, urllib.error, urllib.request, uuid

DEFAULT_SERVER = "https://musicserver.tailf63251.ts.net"
OBJ = "￼"
# Farbe je Person: fest aus dem Namen (auf PC, Mac und Handy gleich) – für Cursor, Markierung und Namens-Chip
PALETTE = ("#e5737f", "#5aa9e6", "#7cc46a", "#f0a64b", "#b48ee8", "#3fc5b0", "#e88ac4", "#c9b458")


def color_for(name):
    return PALETTE[int(hashlib.sha256((name or "?").encode()).hexdigest()[:8], 16) % len(PALETTE)]


def colors_for(names):
    """Farben für alle Beteiligten einer Sitzung, ohne Doppelte (Wunschfarbe aus dem Namen, sonst die nächste freie).
    Alle Geräte rechnen mit derselben Namensliste → überall dieselbe Zuordnung."""
    out, used = {}, set()
    for n in sorted(set(names)):
        i = int(hashlib.sha256(n.encode()).hexdigest()[:8], 16) % len(PALETTE)
        while PALETTE[i] in used and len(used) < len(PALETTE):
            i = (i + 1) % len(PALETTE)
        out[n] = PALETTE[i]
        used.add(PALETTE[i])
    return out


# ====================================================================== Delta-Grundlagen
def op_len(op):
    if "delete" in op:
        return op["delete"]
    if "retain" in op:
        return op["retain"]
    return len(op["insert"]) if isinstance(op["insert"], str) else 1


def _attrs(a):
    return a if a else None


def push(ops, op):
    """Anhängen mit Zusammenfassen (wie Delta.push): gleiche Art + gleiche Attribute verschmelzen, delete vor insert."""
    op = {k: v for k, v in op.items() if not (k == "attributes" and not v)}
    if op_len(op) == 0 and "insert" not in op:
        return ops
    if "insert" in op and isinstance(op["insert"], str) and op["insert"] == "":
        return ops
    if ops:
        last = ops[-1]
        if "delete" in op and "delete" in last:
            ops[-1] = {"delete": last["delete"] + op["delete"]}
            return ops
        if "delete" in last and "insert" in op:     # insert vor ein delete ziehen (kanonische Reihenfolge)
            if len(ops) >= 2 and "insert" in ops[-2]:
                prev = ops[-2]
                if (isinstance(prev["insert"], str) and isinstance(op["insert"], str)
                        and prev.get("attributes") == op.get("attributes")):
                    ops[-2] = dict(prev, insert=prev["insert"] + op["insert"])
                    return ops
            ops.insert(len(ops) - 1, op)
            return ops
        if last.get("attributes") == op.get("attributes"):
            if "insert" in op and "insert" in last and isinstance(op["insert"], str) and isinstance(last["insert"], str):
                ops[-1] = dict(last, insert=last["insert"] + op["insert"])
                return ops
            if "retain" in op and "retain" in last:
                ops[-1] = dict(last, retain=last["retain"] + op["retain"])
                return ops
    ops.append(op)
    return ops


def chop(ops):
    """Abschließendes reines retain weglassen."""
    if ops and "retain" in ops[-1] and not ops[-1].get("attributes"):
        ops.pop()
    return ops


class _It:
    def __init__(self, ops):
        self.ops, self.i, self.off = ops, 0, 0

    def has(self):
        return self.peek_len() < float("inf")

    def peek(self):
        return self.ops[self.i] if self.i < len(self.ops) else None

    def peek_len(self):
        op = self.peek()
        return op_len(op) - self.off if op else float("inf")

    def peek_type(self):
        op = self.peek()
        if not op:
            return "retain"
        return "delete" if "delete" in op else "retain" if "retain" in op else "insert"

    def next(self, n=float("inf")):
        op = self.peek()
        if not op:
            return {"retain": float("inf")}
        off, ln = self.off, op_len(op)
        if n >= ln - off:
            n = ln - off
            self.i += 1
            self.off = 0
        else:
            self.off += n
        if "delete" in op:
            return {"delete": n}
        out = {}
        if op.get("attributes"):
            out["attributes"] = op["attributes"]
        if "retain" in op:
            out["retain"] = n
        elif isinstance(op["insert"], str):
            out["insert"] = op["insert"][off:off + n]
        else:
            out["insert"] = op["insert"]
        return out

    def rest(self):
        if not self.has():
            return []
        if self.off == 0:
            return self.ops[self.i:]
        op = self.next()
        return [op] + self.ops[self.i:]


def _compose_attrs(a, b, keep_null):
    a, b = a or {}, b or {}
    out = dict(a)
    out.update(b)
    if not keep_null:
        out = {k: v for k, v in out.items() if v is not None}
    return out or None


def _transform_attrs(a, b, priority):
    if not a:
        return b or None
    if not b:
        return None
    if not priority:
        return b
    out = {k: v for k, v in b.items() if k not in a}
    return out or None


def compose(a, b):
    """a, dann b → eine Änderung."""
    A, B, out = _It(a), _It(b), []
    while A.has() or B.has():
        if B.peek_type() == "insert":
            push(out, B.next())
        elif A.peek_type() == "delete":
            push(out, A.next())
        else:
            n = min(A.peek_len(), B.peek_len())
            x, y = A.next(n), B.next(n)
            if "retain" in y:
                if "retain" in x:
                    nop = {"retain": n}
                else:
                    nop = {"insert": x["insert"]}
                at = _compose_attrs(x.get("attributes"), y.get("attributes"), "retain" in x)
                if at:
                    nop["attributes"] = at
                if nop.get("retain") == float("inf"):
                    break
                push(out, nop)
            elif "delete" in y and "retain" in x:
                push(out, y)
            # insert + delete heben sich auf
    return chop(out)


def transform(a, b, priority):
    """b so umschreiben, dass es nach a gilt. priority=True: a kam zuerst (seine Einfügungen stehen links)."""
    A, B, out = _It(a), _It(b), []
    while A.has() or B.has():
        if A.peek_type() == "insert" and (priority or B.peek_type() != "insert"):
            push(out, {"retain": op_len(A.next())})
        elif B.peek_type() == "insert":
            push(out, B.next())
        else:
            n = min(A.peek_len(), B.peek_len())
            x, y = A.next(n), B.next(n)
            if "delete" in x:
                continue
            if "delete" in y:
                push(out, y)
            else:
                nop = {"retain": n}
                at = _transform_attrs(x.get("attributes"), y.get("attributes"), priority)
                if at:
                    nop["attributes"] = at
                if n == float("inf"):
                    break
                push(out, nop)
    return chop(out)


def transform_pos(pos, d, priority=False):
    """Cursorposition durch eine Änderung schieben."""
    off, i = 0, 0
    while i < len(d) and off <= pos:
        op = d[i]
        n = op_len(op)
        if "delete" in op:
            pos -= min(n, pos - off)
            i += 1
            continue
        if "insert" in op and (off < pos or not priority):
            pos += n
        off += n
        i += 1
    return pos


def doc_len(doc):
    return sum(op_len(op) for op in doc)


def apply(doc, d):
    return compose(doc, d)


def _items(doc):
    """Dokument → Liste (zeichen, attrs) mit Objekten als eigenem Eintrag."""
    out = []
    for op in doc:
        at = op.get("attributes") or None
        if isinstance(op["insert"], str):
            out.extend((ch, at) for ch in op["insert"])
        else:
            out.append((op["insert"], at))
    return out


def attr_diff(x, y):
    """Nur geänderte Schlüssel (entfernte = None) – sonst überschreibt eine Formatänderung gleichzeitige andere."""
    x, y = x or {}, y or {}
    at = {k: v for k, v in y.items() if x.get(k) != v}
    at.update({k: None for k in x if k not in y})
    return at


def diff(a, b, cursor=None):
    """Änderung von Dokument a zu Dokument b (Text per difflib, gleiche Strecken: nur Attributänderungen).
    cursor = Cursor in b nach der Eingabe: bei mehrdeutigen Stellen („k1“ → „k14 k1“) muss die Änderung dort enden –
    sonst landet eine gleichzeitige fremde Einfügung mitten im gerade getippten Wort."""
    ia, ib = _items(a), _items(b)
    tail = None
    if ia and ib and ia[-1][0] == "\n" and ib[-1][0] == "\n":    # Schluss-\n bleibt immer dasselbe Zeichen
        tail = (ia[-1][1], ib[-1][1])
        ia, ib = ia[:-1], ib[:-1]
    p = 0
    while p < len(ia) and p < len(ib) and ia[p] == ib[p]:
        p += 1
    hint = cursor is not None and 0 <= cursor <= len(ib)
    if hint:
        p = max(0, min(p, cursor - max(0, len(ib) - len(ia))))
    s = 0
    while s < len(ia) - p and s < len(ib) - p and ia[len(ia) - 1 - s] == ib[len(ib) - 1 - s]:
        s += 1
    if hint:
        s = max(0, min(s, len(ib) - cursor))
    out = []
    if p:
        push(out, {"retain": p})
    ma, mb = ia[p:len(ia) - s], ib[p:len(ib) - s]
    keys = {}

    def code(it):
        ch = it[0]
        if isinstance(ch, str):
            return ch
        k = json.dumps(ch, sort_keys=True)
        return keys.setdefault(k, chr(0xF0000 + len(keys)))
    sa, sb = "".join(code(x) for x in ma), "".join(code(x) for x in mb)
    sm = difflib.SequenceMatcher(None, sa, sb, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                x, y = ma[i1 + k], mb[j1 + k]
                if x[1] == y[1]:
                    push(out, {"retain": 1})
                else:
                    push(out, {"retain": 1, "attributes": attr_diff(x[1], y[1])})
            continue
        if i2 > i1:
            push(out, {"delete": i2 - i1})
        for it in mb[j1:j2]:
            push(out, {"insert": it[0], **({"attributes": it[1]} if it[1] else {})})
    if tail and tail[0] != tail[1]:
        if s:
            push(out, {"retain": s})
        push(out, {"retain": 1, "attributes": attr_diff(tail[0], tail[1])})
    return chop(out)


def text_of(doc):
    return "".join(op["insert"] if isinstance(op["insert"], str) else OBJ for op in doc)


# ====================================================================== Einträge ↔ Delta
CHAR_KEYS = ("b", "i", "u", "s", "va", "font", "size", "color", "hl", "link", "cm", "tc")
PARA_SKIP = ("t", "runs")


def table_attrs(rows):
    """Tabelle zellweise als Attribute am Objekt: gleichzeitige Änderungen in verschiedenen Zellen fließen zusammen."""
    at = {"_r": len(rows or [])}
    for i, r in enumerate(rows or []):
        for j, c in enumerate(r):
            at[f"c:{i}:{j}"] = c if isinstance(c, str) else str(c)
    return at


def table_rows(at):
    rows = []
    for i in range(int(at.get("_r") or 0)):
        row, j = [], 0
        while f"c:{i}:{j}" in at:
            row.append(at[f"c:{i}:{j}"])
            j += 1
        rows.append(row)
    return rows


def _plain_attrs(at):
    return {k: v for k, v in (at or {}).items() if not k.startswith(("c:", "_"))}


def blocks_to_doc(blocks):
    out = []
    for b in blocks or [{"t": "p", "runs": []}]:
        if b.get("t") == "table":
            push(out, {"insert": {"block": {k: v for k, v in b.items() if k != "rows"}}, "attributes": table_attrs(b.get("rows"))})
            push(out, {"insert": "\n"})
            continue
        if b.get("t") != "p":
            push(out, {"insert": {"block": b}})
            push(out, {"insert": "\n"})
            continue
        for r in b.get("runs") or []:
            if r.get("img") or r.get("fn") is not None:
                push(out, {"insert": {"run": r}})
            elif r.get("text"):
                at = {k: r[k] for k in CHAR_KEYS if r.get(k) not in (None, False, "")}
                push(out, {"insert": r["text"], **({"attributes": at} if at else {})})
        pa = {k: v for k, v in b.items() if k not in PARA_SKIP and v is not None}
        push(out, {"insert": "\n", **({"attributes": pa} if pa else {})})
    return out


def doc_to_blocks(doc):
    blocks, runs, objs = [], [], []
    for op in doc:
        ins, at = op["insert"], op.get("attributes") or {}
        if isinstance(ins, dict):
            if "block" in ins:
                blk = dict(ins["block"])
                if blk.get("t") == "table":
                    blk["rows"] = table_rows(at)
                objs.append(blk)
            elif "run" in ins:
                runs.append(dict(ins["run"]))
            continue
        parts = ins.split("\n")
        for k, chunk in enumerate(parts):
            if chunk:
                runs.append({**at, "text": chunk})
            if k < len(parts) - 1:                       # Absatzende
                if objs and not runs:
                    blocks.extend(objs)
                else:
                    blocks.extend(objs)
                    p = {"t": "p", "style": "normal", "align": "left", "list": None, "indent": 0, "spacing": 1.15}
                    p.update(at)
                    p["runs"] = _merge(runs)
                    blocks.append(p)
                runs, objs = [], []
    if runs or objs:
        blocks.extend(objs)
        if runs:
            blocks.append({"t": "p", "style": "normal", "align": "left", "list": None, "indent": 0, "spacing": 1.15,
                           "runs": _merge(runs)})
    return blocks or [{"t": "p", "style": "normal", "align": "left", "list": None, "indent": 0, "spacing": 1.15,
                       "runs": []}]


def _merge(runs):
    out = []
    for r in runs:
        if out and "text" in r and "text" in out[-1] and not r.get("img") and not out[-1].get("img") \
                and r.get("fn") is None and out[-1].get("fn") is None \
                and {k: v for k, v in r.items() if k != "text"} == {k: v for k, v in out[-1].items() if k != "text"}:
            out[-1] = dict(out[-1], text=out[-1]["text"] + r["text"])
        else:
            out.append(r)
    return out


def note_to_doc(n):
    """Notiz: Text + rich [[s, e, stil]] + images (je U+FFFC in Reihenfolge)."""
    text = n.get("text") or ""
    marks = [[] for _ in text]
    for s, e, st in n.get("rich") or []:
        for k in range(max(0, s), min(len(text), e)):
            marks[k].append(st)
    imgs = list(n.get("images") or [])
    out, k = [], 0
    for i, ch in enumerate(text):
        at = {m: True for m in sorted(set(marks[i]))} or None
        if ch == OBJ:
            img = imgs[k] if k < len(imgs) else None
            if isinstance(img, dict) and isinstance(img.get("table"), dict):
                t = img["table"]
                push(out, {"insert": {"img": {"table": {kk: v for kk, v in t.items() if kk != "rows"}}},
                           "attributes": {**(at or {}), **table_attrs(t.get("rows"))}})
            else:
                push(out, {"insert": {"img": img}, **({"attributes": at} if at else {})})
            k += 1
        else:
            push(out, {"insert": ch, **({"attributes": at} if at else {})})
    push(out, {"insert": "\n"})
    return out


def doc_to_note(doc):
    text, rich, imgs, pos, open_ = [], [], [], 0, {}
    items = _items(doc)
    if items and items[-1][0] == "\n":
        items = items[:-1]
    for ch, at in items:
        styles = set(_plain_attrs(at).keys())
        for st in list(open_):
            if st not in styles:
                rich.append([open_.pop(st), pos, st])
        for st in styles:
            open_.setdefault(st, pos)
        if isinstance(ch, dict):
            img = ch.get("img")
            if isinstance(img, dict) and isinstance(img.get("table"), dict):
                img = {"table": {**img["table"], "rows": table_rows(at or {})}}
            imgs.append(img)
            text.append(OBJ)
        else:
            text.append(ch)
        pos += 1
    for st, s in open_.items():
        rich.append([s, pos, st])
    rich.sort()
    return {"text": "".join(text), "rich": rich, "images": [i for i in imgs if i is not None]}


def entry_to_doc(kind, n):
    if kind == "docs":
        return blocks_to_doc(n.get("blocks"))
    if kind == "notes":
        return note_to_doc(n)
    return [{"insert": (n.get("text") or "") + "\n"}]


def doc_into_entry(kind, doc, n):
    """Delta zurück in den Eintrag schreiben (n wird verändert und zurückgegeben)."""
    if kind == "docs":
        n["blocks"] = doc_to_blocks(doc)
    elif kind == "notes":
        n.update(doc_to_note(doc))
    else:
        t = text_of(doc)
        n["text"] = t[:-1] if t.endswith("\n") else t
    return n


# ====================================================================== Ende-zu-Ende-Verschlüsselung
# Nur Standardbibliothek (läuft so auch im Handy): Schlüsselstrom SHAKE-256(k_enc ‖ nonce), danach HMAC-SHA256
# über nonce ‖ geheimtext ‖ sitzung (encrypt-then-MAC). Der Server sieht Stand, Änderungen und Cursor nur verschlüsselt.
# Schlüssel je Sitzung aus dem Sitzungs-Code: die Einladende leitet ihn aus ihrem Kontoschlüssel ab (alle ihre Geräte
# kennen ihn), Eingeladene tippen ihn einmal ein (Weitergabe außerhalb von notist, z. B. per WhatsApp).
CODE_ABC = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"          # Crockford: ohne I, L, O, U


def norm_code(code):
    c = "".join(ch for ch in (code or "").upper() if ch.isalnum()).replace("O", "0").replace("I", "1").replace("L", "1")
    return c if len(c) == 20 and all(ch in CODE_ABC for ch in c) else None


def fmt_code(c):
    return "-".join(c[i:i + 4] for i in range(0, len(c), 4))


def session_key(sid, code):
    c = norm_code(code)
    if not c:
        raise CollabError("Sitzungs-Code ungültig (20 Zeichen)")
    return hashlib.sha256(f"notist-collab-key|{sid}|{c}".encode()).digest()


def seal(key, obj, aad):
    pt = json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode()
    ek, mk = hashlib.sha256(b"enc|" + key).digest(), hashlib.sha256(b"mac|" + key).digest()
    nonce = os.urandom(16)
    ks = hashlib.shake_256(ek + nonce).digest(len(pt))
    ct = (int.from_bytes(pt, "big") ^ int.from_bytes(ks, "big")).to_bytes(len(pt), "big")
    tag = hmac.new(mk, nonce + ct + aad.encode(), hashlib.sha256).digest()[:16]
    return {"e": base64.b64encode(nonce + ct + tag).decode()}


def unseal(key, box, aad):
    try:
        raw = base64.b64decode(box["e"])
    except (KeyError, TypeError, ValueError):
        raise CollabError("unverschlüsselte Daten – Sitzung neu einladen", 422) from None
    nonce, ct, tag = raw[:16], raw[16:-16], raw[-16:]
    ek, mk = hashlib.sha256(b"enc|" + key).digest(), hashlib.sha256(b"mac|" + key).digest()
    if len(raw) < 32 or not hmac.compare_digest(tag, hmac.new(mk, nonce + ct + aad.encode(), hashlib.sha256).digest()[:16]):
        raise CollabError("Sitzungs-Code passt nicht", 422)
    ks = hashlib.shake_256(ek + nonce).digest(len(ct))
    return json.loads((int.from_bytes(ct, "big") ^ int.from_bytes(ks, "big")).to_bytes(len(ct), "big"))


# ====================================================================== Konto + Server
class CollabError(Exception):
    def __init__(self, msg, code=0):
        super().__init__(msg)
        self.code = code


class Account:
    """Anmeldung mit dem musicalist-Konto (gleicher Name, gleiches Passwort). Nur für gemeinsames Bearbeiten nötig."""

    def __init__(self, path):
        self.path = path
        self.st = {}
        try:
            if path:
                with open(path, encoding="utf-8") as f:
                    self.st = json.load(f)
        except (OSError, ValueError):
            self.st = {}
        self.st.setdefault("server", DEFAULT_SERVER)
        self.st.setdefault("dev", secrets.token_hex(6))
        self.st.setdefault("links", {})            # sitzung → lokaler Schlüssel (kind:id)
        self._save()

    @property
    def name(self):
        return self.st.get("name")

    @property
    def token(self):
        return self.st.get("token")

    @property
    def dev(self):
        return self.st["dev"]

    def _save(self):
        if not self.path:
            return
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        tmp = self.path + ".tmp"
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)   # Token: nur für den Nutzer lesbar
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(self.st, f, ensure_ascii=False)
        os.replace(tmp, self.path)

    def req(self, method, path, body=None, timeout=30, auth=True):
        url = self.st["server"].rstrip("/") + path
        data = None if body is None else json.dumps(body, separators=(",", ":")).encode()
        r = urllib.request.Request(url, data=data, method=method)
        r.add_header("Content-Type", "application/json")
        r.add_header("User-Agent", "notist-collab")
        if auth:
            if not self.token:
                raise CollabError("nicht angemeldet", 401)
            r.add_header("Authorization", "Bearer " + self.token)
        try:
            with urllib.request.urlopen(r, timeout=timeout) as resp:
                raw = resp.read()
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            try:
                msg = json.loads(e.read()).get("error") or str(e)
            except Exception:  # noqa: BLE001
                msg = str(e)
            if e.code == 401 and auth:
                self.st.pop("token", None)
                self._save()
            raise CollabError(msg, e.code) from None
        except (urllib.error.URLError, OSError, ValueError) as e:
            raise CollabError(f"server nicht erreichbar ({getattr(e, 'reason', e)})", 0) from None

    def login(self, name, password, label="notist"):
        o = self.req("POST", "/v1/login", {"name": name.strip().lower(), "password": password, "label": label}, auth=False)
        # Kontoschlüssel (verlässt das Gerät nie): gleiches Passwort → gleicher Schlüssel auf PC, Mac und Handy
        ak = hashlib.scrypt(password.encode(), salt=f"notist-collab|{o['name']}".encode(), n=2 ** 14, r=8, p=1, dklen=32)
        self.st.update(name=o["name"], token=o["token"], ak=base64.b64encode(ak).decode())
        self._save()
        return o["name"]

    @property
    def has_key(self):
        return bool(self.st.get("ak"))

    def code_for(self, s):
        """Sitzungs-Code: eigene Sitzung → aus dem Kontoschlüssel; fremde → eingetippt (st["codes"])."""
        if s["owner"] == self.name:
            if not self.st.get("ak"):
                raise CollabError("Bitte einmal neu anmelden (für die Verschlüsselung)", 401)
            h = hmac.new(base64.b64decode(self.st["ak"]), f"code|{s['id']}".encode(), hashlib.sha256).digest()
            n = int.from_bytes(h[:13], "big") >> 4
            return "".join(CODE_ABC[(n >> (5 * i)) & 31] for i in range(20))
        c = (self.st.get("codes") or {}).get(s["id"])
        if not c:
            raise CollabError("Sitzungs-Code fehlt", 428)
        return c

    def set_code(self, sid, code):
        c = norm_code(code)
        if not c:
            raise CollabError("Sitzungs-Code ungültig (20 Zeichen)")
        self.st.setdefault("codes", {})[sid] = c
        self._save()

    def key_for(self, s):
        return session_key(s["id"], self.code_for(s))

    def logout(self):
        try:
            self.req("POST", "/v1/logout", {}, timeout=10)
        except CollabError:
            pass
        for k in ("token", "name", "ak"):
            self.st.pop(k, None)
        self._save()

    def sessions(self):
        return self.req("GET", "/v1/collab").get("sessions") or []

    def friends(self):
        """musicalist-Freunde als [{name (Konto), display}] – leer, wenn der Server das (noch) nicht kann."""
        try:
            return self.req("GET", "/v1/friends", timeout=15).get("friends") or []
        except CollabError:
            return []

    def invite(self, kind, title, doc_key, members):
        return self.req("POST", "/v1/collab", {"kind": kind, "title": title, "doc_key": doc_key, "members": members})

    def end(self, sid):
        return self.req("POST", f"/v1/collab/{sid}/end", {})

    def link(self, sid, key=None):
        if key is None:
            return self.st["links"].get(sid)
        self.st["links"][sid] = key
        self._save()
        return key

    def unlink(self, sid):
        if self.st["links"].pop(sid, None) is not None:
            self._save()


# ====================================================================== Live-Sitzung
class Live:
    """Eine laufende Sitzung. Netz läuft in Fäden; alles, was das Dokument betrifft, über post() im UI-Faden.

    get_doc()            → aktuelles Dokument aus dem Editor (UI-Faden)
    apply_remote(d, doc) → fremde Änderung d in den Editor bringen; doc = Stand danach (UI-Faden)
    on_state(dict)       → Status für die Oberfläche (verbunden, wer ist da, Fehler)
    on_cursors(list)     → [{by, dev, pos}] fremde Cursor, schon auf den lokalen Stand umgerechnet
    """
    KEEP = 400                       # kanonische Änderungen im Speicher (für Nachzügler-Transformation)
    SNAP_EVERY = 100                 # nach so vielen Änderungen einen neuen Stand hochladen

    def __init__(self, acct, sid, owner, get_doc, apply_remote, post, on_state=None, on_cursors=None, key=None,
                 get_cursor=None):
        self.a, self.sid, self.owner = acct, sid, owner
        self.get_cursor = get_cursor or (lambda: None)
        self.key = key                   # None nur in Tests ohne Server (Simulator)
        self.get_doc, self.apply_remote, self.post = get_doc, apply_remote, post
        self.on_state = on_state or (lambda s: None)
        self.on_cursors = on_cursors or (lambda c: None)
        self.rev = 0
        self.canon = None            # Stand bei rev (ohne eigene offene Änderungen)
        self.doc = None              # lokaler Stand (canon + inflight + buffer)
        self.hist = {}               # rev → kanonische Änderung
        self.inflight, self.buffer = None, None
        self.seq = int(time.time() * 1000) % 10**12      # je Start neu, aber steigend (Server erkennt Wiederholungen)
        self.cseen = 0
        self.cursors = []
        self.stop = threading.Event()
        self.outq = []
        self.cv = threading.Condition()
        self.ready = False
        self.err = None

    # ----- Fäden -----
    def start(self):
        threading.Thread(target=self._recv_loop, daemon=True, name=f"collab-recv-{self.sid}").start()
        threading.Thread(target=self._send_loop, daemon=True, name=f"collab-send-{self.sid}").start()

    def close(self):
        self.stop.set()
        with self.cv:
            self.cv.notify_all()

    def _state(self, **kw):
        st = {"ready": self.ready, "rev": self.rev, "error": self.err, "pending": self.inflight is not None, **kw}
        self.post(lambda: self.on_state(st))

    def _seal(self, obj):
        return obj if self.key is None else seal(self.key, obj, self.sid)

    def _unseal(self, box):
        return box if self.key is None else unseal(self.key, box, self.sid)

    def _call_ui(self, fn, *a):
        """fn im UI-Faden ausführen und auf das Ergebnis warten."""
        box, ev = {}, threading.Event()

        def run():
            try:
                box["v"] = fn(*a)
            except Exception as e:  # noqa: BLE001
                box["e"] = e
            ev.set()
        self.post(run)
        while not ev.wait(0.5):
            if self.stop.is_set():
                raise CollabError("beendet")
        if "e" in box:
            raise box["e"]
        return box.get("v")

    def _load(self):
        """Stand holen; ist noch keiner da und wir laden ein, unseren hochladen."""
        try:
            o = self.a.req("GET", f"/v1/collab/{self.sid}/doc")
        except CollabError as e:
            if e.code != 404:
                raise
            if not self.owner:
                return False                             # warten, bis die Einladende den Stand hochlädt
            doc = self._call_ui(self.get_doc)
            o = self.a.req("PUT", f"/v1/collab/{self.sid}/doc", {"rev": 0, "doc": self._seal(doc)}, timeout=60)
            if not o.get("ok"):
                return False
            o = self.a.req("GET", f"/v1/collab/{self.sid}/doc")
        self._call_ui(self._reset, o["rev"], self._unseal(o["doc"]))
        return True

    def _reset(self, rev, doc):
        """(Neu-)Start auf einem Server-Stand: eigene Änderungen seit dem letzten bekannten Stand bleiben erhalten."""
        mine = self.get_doc()
        local = []
        if mine != doc:
            if self.canon is not None:                   # Wiederaufnahme: eigenes Ungesendetes auf den neuen Stand heben
                local = transform(diff(self.canon, doc), diff(self.canon, mine), True)
            elif self.owner:                             # Einladende haben seit dem Hochladen weitergeschrieben
                local = diff(doc, mine)
        with self.cv:
            self.outq = [x for x in self.outq if "pos" in x]
        self.rev, self.canon, self.hist = rev, doc, {}
        self.inflight, self.buffer = None, None
        self.doc = apply(doc, local) if local else doc
        if self.doc != mine:
            self.apply_remote(diff(mine, self.doc), self.doc)
        if local:
            self._queue(local)
        self.ready = True
        self._state()

    def _recv_loop(self):
        delay = 1
        while not self.stop.is_set():
            try:
                if not self.ready:
                    if not self._load():
                        self._state(waiting=True)
                        self.stop.wait(3)
                        continue
                o = self.a.req("GET", f"/v1/collab/{self.sid}/ops?after={self.rev}&wait=25&dev={self.a.dev}"
                               f"&cseen={self.cseen}", timeout=40)
                delay = 1
                if self.err:
                    self.err = None
                    self._state()
                self.cseen = o.get("cseen") or self.cseen
                ops, curs = o.get("ops") or [], o.get("cursors") or []
                if ops or curs:
                    self._call_ui(self._incoming, ops, curs)
            except CollabError as e:
                if self.stop.is_set():
                    break
                if e.code == 410:                         # Stand verdichtet / Server neu gestartet → neu laden
                    self.ready = False
                    continue
                if e.code in (404, 409, 403, 422, 428, 401):
                    self.err = str(e)
                    self._state(ended=True, badkey=e.code in (422, 428), relogin=e.code == 401)
                    break
                self.err = str(e)
                self._state()
                self.stop.wait(delay)
                delay = min(30, delay * 2)

    # ----- UI-Faden: Empfang -----
    def _incoming(self, ops, curs):
        if ops and self.ready and self.doc is not None:
            self.local_changed(self.get_cursor())    # noch nicht gesendetes Tippen zuerst übernehmen – sonst überschreibt es
        for o in ops:
            if o["rev"] <= self.rev:
                continue
            if o["rev"] != self.rev + 1:                   # Lücke (sollte nicht vorkommen) → neu laden
                self.ready = False
                return
            mine = o["by"] == self.a.name and o["dev"] == self.a.dev and self.inflight is not None \
                and o["seq"] == self.inflight[0]
            if mine:
                c = self.inflight[1]                      # schon über alles Fremde transformiert = kanonisch
                self.inflight = None
                self.hist[o["rev"]] = c
                self.canon = apply(self.canon, c)
                self.rev = o["rev"]
                if self.buffer is not None:
                    self._send_now(self.buffer)
                    self.buffer = None
            else:
                c = self._unseal(o["op"])
                for k in range(o["base"] + 1, o["rev"]):
                    h = self.hist.get(k)
                    if h is None:                         # zu alt für den Speicher → neu laden
                        self.ready = False
                        return
                    c = transform(h, c, True)
                self.hist[o["rev"]] = c
                self.canon = apply(self.canon, c)
                self.rev = o["rev"]
                cc = c
                if self.inflight is not None:
                    cc = transform(self.inflight[1], cc, False)
                    self.inflight = (self.inflight[0], transform(c, self.inflight[1], True))
                if self.buffer is not None:
                    c2 = transform(self.buffer, cc, False)
                    self.buffer = transform(cc, self.buffer, True)
                    cc = c2
                self.doc = apply(self.doc, cc)
                self.apply_remote(cc, self.doc)
            for k in [k for k in self.hist if k <= self.rev - self.KEEP]:
                del self.hist[k]
        if curs is not None:
            self.cursors = []
            for c in curs:
                try:
                    self.cursors.append(dict(c, pos=self._unseal(c.get("pos") or {})))
                except CollabError:
                    pass
        self.on_cursors(self.local_cursors())
        # Stand regelmäßig sichern: Einladende alle 100 Änderungen, alle anderen alle 300 (falls sie offline ist)
        if self.rev and self.rev % (self.SNAP_EVERY if self.owner else 3 * self.SNAP_EVERY) == 0:
            self._snapshot()
        self._state()

    def local_cursors(self):
        out = []
        for c in self.cursors:
            pos = c.get("pos") or {}
            i, j = pos.get("i", 0), pos.get("j", pos.get("i", 0))
            for k in range(int(c.get("rev") or 0) + 1, self.rev + 1):
                h = self.hist.get(k)
                if h is not None:
                    i, j = transform_pos(i, h), transform_pos(j, h)
            for d in (self.inflight[1] if self.inflight else None, self.buffer):
                if d:
                    i, j = transform_pos(i, d), transform_pos(j, d)
            out.append({"by": c.get("by"), "dev": c.get("dev"), "i": i, "j": j})
        return out

    def _snapshot(self):
        rev, doc = self.rev, self.canon
        box = self._seal(doc)
        threading.Thread(target=lambda: self._try(lambda: self.a.req(
            "PUT", f"/v1/collab/{self.sid}/doc", {"rev": rev, "doc": box}, timeout=60)), daemon=True).start()

    @staticmethod
    def _try(fn):
        try:
            fn()
        except CollabError:
            pass

    # ----- UI-Faden: eigene Änderungen -----
    def local_changed(self, cursor=None):
        """Nach einer Eingabe (entprellt) aufrufen: Unterschied zum letzten Stand ermitteln und senden.
        cursor (Position im Dokument) macht mehrdeutige Einfügungen eindeutig (siehe diff)."""
        if not self.ready or self.doc is None:
            return
        cur = self.get_doc()
        d = diff(self.doc, cur, cursor)
        if not d:
            return
        self.doc = cur
        self._queue(d)

    def _queue(self, d):
        if self.inflight is None:
            self._send_now(d)
        else:
            self.buffer = d if self.buffer is None else compose(self.buffer, d)
        self._state()

    def _send_now(self, d):
        self.seq += 1
        self.inflight = (self.seq, d)
        with self.cv:
            self.outq.append({"dev": self.a.dev, "seq": self.seq, "base": self.rev, "op": self._seal(d)})
            self.cv.notify_all()

    def cursor(self, i, j=None):
        with self.cv:
            self.outq = [x for x in self.outq if "pos" not in x]
            self.outq.append({"dev": self.a.dev, "rev": self.rev, "pos": self._seal({"i": i, "j": i if j is None else j})})
            self.cv.notify_all()

    def _send_loop(self):
        delay = 1
        while not self.stop.is_set():
            with self.cv:
                while not self.outq and not self.stop.is_set():
                    self.cv.wait(5)
                if self.stop.is_set():
                    return
                item = self.outq[0]
            try:
                if "pos" in item:
                    self.a.req("POST", f"/v1/collab/{self.sid}/cursor", item, timeout=15)
                else:
                    self.a.req("POST", f"/v1/collab/{self.sid}/ops", item, timeout=30)
                with self.cv:
                    if self.outq and self.outq[0] is item:
                        self.outq.pop(0)
                delay = 1
            except CollabError as e:
                if e.code == 410:                     # Basis zu alt → nach dem Neuladen wird neu gesendet
                    with self.cv:
                        self.outq = [x for x in self.outq if "pos" in x]
                    self.ready = False
                    continue
                if e.code in (400, 404, 409, 413):
                    with self.cv:
                        if self.outq and self.outq[0] is item:
                            self.outq.pop(0)
                    continue
                self.stop.wait(delay)
                delay = min(30, delay * 2)


def new_local_id():
    return str(uuid.uuid4())


def deep(x):
    return copy.deepcopy(x)
