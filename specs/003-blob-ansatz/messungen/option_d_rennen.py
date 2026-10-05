#!/usr/bin/env python3
"""Throwaway race test for "option D": the content hash sits on the revision row,
files are named after the hash, cleanup follows Odoo's ir.attachment._gc_file_store
(checklist + LOCK ... IN SHARE MODE + whitelist query), real processes, REPEATABLE READ.
"""

import hashlib
import multiprocessing as mp
import os
import shutil
import sys
import time

import psycopg2
from psycopg2 import extensions as ext

DSN = os.environ["DSN"]
ROOT = os.environ["ROOT"]
ctx = mp.get_context("fork")
RESULTS = []


def conn():
    c = psycopg2.connect(DSN)
    # same isolation level as odoo.sql_db.Cursor
    c.set_isolation_level(ext.ISOLATION_LEVEL_REPEATABLE_READ)
    return c


def sha_of(data):
    return hashlib.sha256(data).hexdigest()


def p_blob(sha):
    return f"{ROOT}/blobs/{sha[:2]}/{sha}"


def p_mark(sha):
    return f"{ROOT}/checklist/{sha[:2]}/{sha}"


def quiet_unlink(path):
    try:
        os.unlink(path)
    except OSError:
        pass


def mark(sha):
    """ir.attachment._mark_for_gc, plus a touch so the age restarts."""
    p = p_mark(sha)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "ab"):
        pass
    os.utime(p)


def fsync_dir(d):
    fd = os.open(d, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def put(sha, tmp):
    p = p_blob(sha)
    d = os.path.dirname(p)
    os.makedirs(d, exist_ok=True)
    if os.environ.get("PUT") == "link":
        try:
            os.link(tmp, p)
        except FileExistsError:
            pass
        os.unlink(tmp)
    else:
        os.replace(tmp, p)
    fsync_dir(d)


def make_tmp(name, data):
    p = f"{ROOT}/tmp/{name}"
    with open(p, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    return p


def reset():
    shutil.rmtree(ROOT, ignore_errors=True)
    for d in ("blobs", "checklist", "tmp"):
        os.makedirs(f"{ROOT}/{d}")
    c = conn()
    cur = c.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS rev (id serial PRIMARY KEY, node_id int, sha varchar(64) NOT NULL)")
    cur.execute("CREATE INDEX IF NOT EXISTS rev_sha_idx ON rev (sha)")
    cur.execute("TRUNCATE rev RESTART IDENTITY")
    c.commit()
    c.close()


def rows_with(sha):
    c = conn()
    cur = c.cursor()
    cur.execute("SELECT count(*) FROM rev WHERE sha = %s", (sha,))
    n = cur.fetchone()[0]
    c.close()
    return n


def blob_ok(sha, data):
    try:
        with open(p_blob(sha), "rb") as f:
            return f.read() == data
    except OSError:
        return False


# ---------------------------------------------------------------- the operations


def upload(sha, data, name, hook=None, die_at=None):
    """Plan D, finishing an upload: row first, then mark, then os.replace, then commit."""
    tmp = make_tmp(name, data)
    c = conn()
    cur = c.cursor()

    def at(point):
        if hook:
            hook(point)
        if die_at == point:
            os._exit(9)

    at("start")
    cur.execute("INSERT INTO rev (node_id, sha) VALUES (1, %s)", (sha,))
    at("inserted")
    mark(sha)
    at("marked")
    put(sha, tmp)
    at("placed")
    c.commit()
    at("committed")
    ok = blob_ok(sha, data)
    if not ok:
        time.sleep(0.2)
        ok = "transient" if blob_ok(sha, data) else False
    c.close()
    return ok


def gc(grace=0, hook=None):
    """ir.attachment._gc_file_store with a grace period on the checklist mark."""
    c = conn()
    cur = c.cursor()
    cur.execute("SET LOCAL lock_timeout TO '10s'")
    t0 = time.time()
    if not os.environ.get("NOLOCK"):
        cur.execute("LOCK rev IN SHARE MODE")
    waited = time.time() - t0
    if hook:
        hook("locked")
    names = []
    for _dp, _dn, fns in os.walk(f"{ROOT}/checklist"):
        names.extend(fns)
    removed = []
    for i in range(0, len(names), 1000):
        batch = names[i : i + 1000]
        cur.execute("SELECT sha FROM rev WHERE sha IN %s", (tuple(batch),))
        white = {r[0] for r in cur.fetchall()}
        for sha in batch:
            if sha in white:
                quiet_unlink(p_mark(sha))
                continue
            try:
                age = time.time() - os.stat(p_mark(sha)).st_mtime
            except OSError:
                continue
            if age < grace:
                continue
            quiet_unlink(p_blob(sha))
            quiet_unlink(p_mark(sha))
            removed.append(sha)
    c.commit()
    c.close()
    return waited, removed


def delete_rev(rev_id, sha):
    """Revision unlink: delete the row, then mark the file (Odoo's order)."""
    c = conn()
    cur = c.cursor()
    cur.execute("DELETE FROM rev WHERE id = %s", (rev_id,))
    mark(sha)
    c.commit()
    c.close()


def copy_rev(src_id, hook):
    """Copy a revision: read the source, insert a row with the same hash."""
    c = conn()
    cur = c.cursor()
    cur.execute("SELECT sha FROM rev WHERE id = %s", (src_id,))
    sha = cur.fetchone()[0]
    hook("read")
    cur.execute("INSERT INTO rev (node_id, sha) VALUES (2, %s)", (sha,))
    c.commit()
    c.close()
    return sha


# ---------------------------------------------------------------- process helpers


def run(label, fn, q, *a, **kw):
    try:
        q.put((label, "ok", fn(*a, **kw)))
    except BaseException as e:  # noqa: BLE001
        q.put((label, "err", repr(e)))


def spawn(label, q, fn, *a, **kw):
    p = ctx.Process(target=run, args=(label, fn, q) + a, kwargs=kw)
    p.start()
    return p


def hooker(spec, evs):
    def hook(point):
        if point in spec:
            s, w = spec[point]
            if s:
                evs[s].set()
            if w:
                evs[w].wait(30)

    return hook


def drain(q):
    out = {}
    while not q.empty():
        label, st, val = q.get()
        out[label] = (st, val)
    return out


def report(name, ok, detail):
    RESULTS.append((name, ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}", flush=True)


# ---------------------------------------------------------------- scenarios


def s1(prestale):
    """GC starts while an upload has inserted its row but not committed."""
    reset()
    data = os.urandom(200_000)
    sha = sha_of(data)
    if prestale:  # earlier orphan: file + checklist mark, no row
        os.makedirs(os.path.dirname(p_blob(sha)), exist_ok=True)
        with open(p_blob(sha), "wb") as f:
            f.write(data)
        mark(sha)
    q = ctx.Queue()
    evs = {"ins": ctx.Event(), "go": ctx.Event()}
    u = spawn("U", q, upload, sha, data, "u1", hook=hooker({"inserted": ("ins", "go")}, evs))
    evs["ins"].wait(10)
    g = spawn("GC", q, gc, 0)
    time.sleep(1.5)
    gc_alive = g.is_alive()
    evs["go"].set()
    u.join()
    g.join()
    res = drain(q)
    waited = res["GC"][1][0] if res["GC"][0] == "ok" else -1
    ok = gc_alive and waited >= 1.0 and blob_ok(sha, data) and rows_with(sha) == 1
    report(
        f"S1 gc waits for open upload (prestale={prestale})",
        ok,
        f"gc blocked={gc_alive}, waited={waited:.1f}s, blob_ok={blob_ok(sha, data)}, rows={rows_with(sha)}",
    )


def s2():
    """Upload starts while GC holds its lock and deletes the orphan of the same content."""
    reset()
    data = os.urandom(200_000)
    sha = sha_of(data)
    os.makedirs(os.path.dirname(p_blob(sha)), exist_ok=True)
    with open(p_blob(sha), "wb") as f:
        f.write(data)
    mark(sha)
    q = ctx.Queue()
    evs = {"locked": ctx.Event(), "go": ctx.Event()}
    g = spawn("GC", q, gc, 0, hook=hooker({"locked": ("locked", "go")}, evs))
    evs["locked"].wait(10)
    u = spawn("U", q, upload, sha, data, "u2")
    time.sleep(1.5)
    u_alive = u.is_alive()
    evs["go"].set()
    g.join()
    u.join()
    res = drain(q)
    ok = u_alive and res["U"] == ("ok", True) and blob_ok(sha, data) and rows_with(sha) == 1 and sha in res["GC"][1][1]
    report(
        "S2 upload waits for running gc, file is recreated",
        ok,
        f"upload blocked={u_alive}, gc removed orphan={sha in res['GC'][1][1]}, "
        f"blob_ok={blob_ok(sha, data)}, rows={rows_with(sha)}",
    )


def s3(grace):
    """Copy of a revision races with the deletion of the source and a gc run."""
    reset()
    data = os.urandom(200_000)
    sha = sha_of(data)
    os.makedirs(os.path.dirname(p_blob(sha)), exist_ok=True)
    with open(p_blob(sha), "wb") as f:
        f.write(data)
    c = conn()
    cur = c.cursor()
    cur.execute("INSERT INTO rev (node_id, sha) VALUES (1, %s)", (sha,))
    c.commit()
    c.close()
    q = ctx.Queue()
    evs = {"read": ctx.Event(), "go": ctx.Event()}
    k = spawn("K", q, copy_rev, 1, hooker({"read": ("read", "go")}, evs))
    evs["read"].wait(10)
    delete_rev(1, sha)
    gc(grace)
    evs["go"].set()
    k.join()
    drain(q)
    ok = blob_ok(sha, data) and rows_with(sha) == 1
    report(
        f"S3 copy vs delete vs gc (grace={grace}s)",
        ok,
        f"blob_ok={blob_ok(sha, data)}, rows={rows_with(sha)}",
    )
    return ok


def s4(rounds=12, writers=10):
    """Ten parallel uploads of the same new content while gc runs in a loop."""
    q = ctx.Queue()
    stop = ctx.Event()

    def gc_loop(q, stop):
        n = 0
        while not stop.is_set():
            gc(0)
            n += 1
        q.put(("GCLOOP", "ok", n))

    bad = 0
    transient = 0
    gc_runs = 0
    for r in range(rounds):
        reset()
        stop.clear()
        data = os.urandom(2_000_000)
        sha = sha_of(data)
        if r % 2:  # stale mark of an earlier orphan with the same content
            mark(sha)
        gp = ctx.Process(target=gc_loop, args=(q, stop))
        gp.start()
        procs = [spawn(f"U{i}", q, upload, sha, data, f"u{i}") for i in range(writers)]
        for p in procs:
            p.join()
        stop.set()
        gp.join()
        res = drain(q)
        gc_runs += res.get("GCLOOP", ("", 0))[1]
        errs = [v for k, v in res.items() if k.startswith("U") and v != ("ok", True)]
        transient += sum(1 for v in errs if v == ("ok", "transient"))
        errs = [v for v in errs if v != ("ok", "transient")]
        files = [f for _d, _n, fs in os.walk(f"{ROOT}/blobs") for f in fs]
        if errs or rows_with(sha) != writers or not blob_ok(sha, data) or files != [sha]:
            bad += 1
            print("  round", r, "errs", errs, "rows", rows_with(sha), "files", files, flush=True)
    report(
        f"S4 {writers} parallel uploads x {rounds} rounds against a gc loop (grace=0)",
        bad == 0,
        f"bad rounds={bad}, transient misses={transient}, gc runs={gc_runs}",
    )


def s5():
    """Deduplicated content: file stays while any row references it."""
    reset()
    data = os.urandom(100_000)
    sha = sha_of(data)
    q = ctx.Queue()
    for i in range(2):
        spawn(f"U{i}", q, upload, sha, data, f"u{i}").join()
    gc(0)
    both = blob_ok(sha, data) and rows_with(sha) == 2
    delete_rev(1, sha)
    gc(0)
    after_one = blob_ok(sha, data) and rows_with(sha) == 1
    delete_rev(2, sha)
    gc(0)
    gone = not os.path.exists(p_blob(sha)) and rows_with(sha) == 0
    report(
        "S5 dedup: kept while referenced, removed after last delete",
        both and after_one and gone,
        f"two rows ok={both}, after 1 delete kept={after_one}, after 2 deleted removed={gone}",
    )


def s6():
    """Crash (os._exit) at each step of finishing an upload."""
    all_ok = True
    notes = []
    for point in ("start", "inserted", "marked", "placed", "committed"):
        reset()
        data = os.urandom(100_000)
        sha = sha_of(data)
        q = ctx.Queue()
        p = spawn("U", q, upload, sha, data, "uc", die_at=point)
        p.join()
        rows = rows_with(sha)
        exists = os.path.exists(p_blob(sha))
        invariant = (rows == 0) or exists  # committed row => file there
        gc(0)
        clean = (rows == 0 and not os.path.exists(p_blob(sha))) or (rows == 1 and blob_ok(sha, data))
        ok = invariant and clean
        all_ok &= ok
        notes.append(f"{point}: rows={rows} file={exists} -> {'ok' if ok else 'BAD'}")
    report("S6 crash at every step: no committed row without file, leftovers collected", all_ok, "; ".join(notes))


if __name__ == "__main__":
    if os.environ.get("ONLY") == "control":
        s1(True)
        s4(rounds=12)
        sys.exit(0)
    if os.environ.get("ONLY") == "long":
        s4(rounds=60)
        sys.exit(0)
    s1(False)
    s1(True)
    s2()
    s3(0)  # expected to fail: shows why the grace period is needed
    s3(3600)
    s4()
    s5()
    s6()
    print("SUMMARY", [(n, ok) for n, ok in RESULTS])
