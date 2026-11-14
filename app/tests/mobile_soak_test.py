#!/usr/bin/env python3
# Schritt 33: Abgleich-Dauerlauf – 500 Zufallsänderungen beidseitig (Handy-Kern ↔ echte PC-Instanz), dazwischen immer wieder abgleichen;
# am Ende müssen beide Seiten genau dieselben Einträge haben (inklusive „(konflikt)“-Kopien und Löschungen).
#   python tests/mobile_soak_test.py [N] [-v]
import os, random, subprocess, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, "mobile_test.py"), encoding="utf-8").read().split("def main")[0]
exec(compile(src, "mobile_test_head", "exec"))
N = int(next((a for a in sys.argv[1:] if a.isdigit()), 500))

PC_OP = '''
import random
rnd = random.Random({seed})
k = rnd.choice(["notes", "docs", "latex"]); st = app.stores[k]
exists = lambda n: os.path.exists(os.path.join(st.path, n["id"] + ".json"))
live = [n for n in st.notes.values() if exists(n) and not n.get("trashed")]
dead = [n for n in st.notes.values() if exists(n) and n.get("trashed")]
act = rnd.choice(["new", "edit", "edit", "edit", "trash", "restore", "delete", "label"])
out = act
if act == "new" or not live:
    n = st.create(); n.update(title="pc-{seed}", text="pc {seed}"); st.save(n)
elif act == "edit":
    n = rnd.choice(live); n["text"] = n.get("text", "") + " pc{seed}"; st.save(n)
elif act == "trash":
    st.trash(rnd.choice(live))
elif act == "restore" and dead:
    st.restore(rnd.choice(dead))
elif act == "delete" and dead:
    st.delete_forever(rnd.choice(dead))
elif act == "label":
    n = rnd.choice(live); n["labels"] = sorted(set(n.get("labels", []) + ["l" + str({seed} % 5)])); st.save(n)
'''


def mob_op(api, mobile, seed):
    rnd = random.Random(seed + 10_000)
    k = rnd.choice(["notes", "docs", "latex"])
    live = api.m_list(k, "aktiv"); dead = api.m_list(k, "papierkorb")
    act = rnd.choice(["new", "edit", "edit", "edit", "trash", "restore", "delete", "label"])
    if act == "new" or not live:
        e = api.m_new(k); e.update(title=f"hy-{seed}", text=f"hy {seed}"); api.m_save(k, e)
    elif act == "edit":
        e = api.m_get(k, rnd.choice(live)["id"]); e["text"] = (e.get("text") or "") + f" hy{seed}"; api.m_save(k, e)
    elif act == "trash":
        api.m_trash(k, rnd.choice(live)["id"])
    elif act == "restore" and dead:
        api.m_restore(k, rnd.choice(dead)["id"])
    elif act == "delete" and dead:
        api.m_delete(k, rnd.choice(dead)["id"])
    elif act == "label":
        e = rnd.choice(live); api.m_patch(k, e["id"], {"labels": sorted(set(e["labels"] + [f"l{seed % 5}"]))})


def main4():
    xv = subprocess.Popen(["Xvfb", ":98", "-screen", "0", "1280x800x24", "-nolisten", "tcp"], stderr=subprocess.DEVNULL)
    time.sleep(1)
    os.environ.update(DISPLAY=":98", GDK_BACKEND="x11")
    port = free_port(); PC = None
    t0 = time.time()
    try:
        PC = Inst("pc", port)
        PC.x("app.handy.start()")
        code = PC.x("out = app.handy.start_pairing()[1]")
        from core import api, mobile
        api.m_start(None)
        pid = api.m_pair(f"127.0.0.1:{port}", code)["id"]
        rnd = random.Random(2026)
        errs = []; syncs = 0; nxt = rnd.randint(4, 12)
        for i in range(N):
            if rnd.random() < 0.5:
                PC.x(PC_OP.format(seed=i), 60)
            else:
                mob_op(api, mobile, i)
            if i + 1 >= nxt or i == N - 1:
                nxt = i + 1 + rnd.randint(4, 12)
                e = wait_sync(api, pid, 180); syncs += 1
                if e:
                    errs.append((i, e))
        for _ in range(3):
            e = wait_sync(api, pid, 180); syncs += 1
            if e: errs.append(("final", e))
        sm, sp = mob_snap(api), pc_snap(PC)
        conflicts = sum(1 for v in sm.values() if "(konflikt)" in (v.get("title") or ""))
        check(f"{N} Zufallsänderungen, {syncs} Abgleiche ohne Fehler", not errs, str(errs[:3]))
        only_m = sorted(set(sm) - set(sp)); only_p = sorted(set(sp) - set(sm))
        diff = [k for k in sm if k in sp and sm[k] != sp[k]]
        check(f"am Ende gleiche Einträge ({len(sm)} Handy / {len(sp)} PC, {conflicts} Konfliktkopien)", not only_m and not only_p, f"nur Handy {only_m[:3]} nur PC {only_p[:3]}")
        check("alle gemeinsamen Einträge inhaltsgleich", not diff, f"{len(diff)} verschieden, z. B. {diff[:2]}")
        print(f"  Dauer {time.time() - t0:.0f} s")
    finally:
        if PC:
            PC.stop()
        xv.terminate()
    ok = all(RES)
    print(f"{'✓' if ok else '✗'} mobile_soak_test: {sum(RES)}/{len(RES)} grün" + ("" if ok else f"  (Logs: {T})"))
    sys.exit(0 if ok else 1)


main4()
