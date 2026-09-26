"""Prototyp-Import (Kopie) von der Live-Freigabe (nur lesend) in den Blob-Speicher. Laeuft in `odoo shell`."""
import hashlib, os, time
from odoo.addons.fm_proto import blobstore

SRC = "/mnt/live-ro"
DIRS = ["Gemeinde/08 Tontechnik", "Bilder/06 Verwandtschaft Enns", "Programme/Mac"]
BATCH = 500
CH = 1024 * 1024

Node, Blob, Rev = env["fm.node"], env["fm.blob"], env["fm.revision"]
root_node = Node.search([("name", "=", "import"), ("parent_id", "=", False)], limit=1) or Node.create({"name": "import", "is_dir": True})
env.cr.commit()
tmpd = blobstore.tmp_dir(env)
folders = {"": root_node.id}


def folder_id(rel_dir):
    if rel_dir in folders:
        return folders[rel_dir]
    parent, name = os.path.split(rel_dir)
    pid = folder_id(parent)
    n = Node.create({"name": name, "parent_id": pid, "is_dir": True})
    folders[rel_dir] = n.id
    return n.id


stats = {"files": 0, "bytes": 0, "dedup": 0, "errors": 0}
pending = []  # (parent_id, name, sha, size)
t0 = time.time()


def flush():
    if not pending:
        return
    os.sync()  # Blobs dauerhaft auf der Platte, BEVOR die Zeilen committet werden (I3/I4)
    shas = list({p[2] for p in pending})
    existing = {b.sha256: b for b in Blob.search([("sha256", "in", shas)])}
    new = [{"sha256": s, "size": sz} for s, sz in {p[2]: p[3] for p in pending}.items() if s not in existing]
    for b in Blob.create(new):
        existing[b.sha256] = b
    nodes = Node.create([{"name": p[1], "parent_id": p[0]} for p in pending])
    revs = Rev.create([{"node_id": n.id, "blob_id": existing[p[2]].id, "revision_no": 1, "origin": "import"}
                       for n, p in zip(nodes, pending)])
    for n, r in zip(nodes, revs):
        n.current_revision_id = r
    env.cr.commit()
    pending.clear()


for d in DIRS:
    td = time.time(); b0 = stats["bytes"]; f0 = stats["files"]
    for dirpath, dirnames, filenames in os.walk(os.path.join(SRC, d)):
        rel_dir = os.path.relpath(dirpath, SRC)
        pid = folder_id(rel_dir)
        for fn in filenames:
            src = os.path.join(dirpath, fn)
            tmp = os.path.join(tmpd, "imp_%d" % stats["files"])
            try:
                h = hashlib.sha256(); size = 0
                with open(src, "rb") as fi, open(tmp, "wb") as fo:
                    while chunk := fi.read(CH):
                        h.update(chunk); fo.write(chunk); size += len(chunk)
                sha = h.hexdigest()
                final = blobstore.blob_path(env, sha)
                os.makedirs(os.path.dirname(final), exist_ok=True)
                try:
                    os.link(tmp, final)
                except FileExistsError:
                    stats["dedup"] += 1
                os.unlink(tmp)
                pending.append((pid, fn, sha, size))
                stats["files"] += 1; stats["bytes"] += size
            except OSError:
                stats["errors"] += 1
                if os.path.exists(tmp):
                    os.unlink(tmp)
            if len(pending) >= BATCH:
                flush()
    flush()
    dt = time.time() - td
    print(">> %-32s %6d Dateien %7.1f GB in %6.0f s = %5.1f MB/s, %5.1f Dateien/s" % (
        d, stats["files"] - f0, (stats["bytes"] - b0) / 1e9, dt, (stats["bytes"] - b0) / 1e6 / dt, (stats["files"] - f0) / dt), flush=True)

dt = time.time() - t0
print(">> GESAMT %d Dateien, %.1f GB in %.0f s = %.1f MB/s, %.1f Dateien/s, Duplikate %d, Fehler %d" % (
    stats["files"], stats["bytes"] / 1e9, dt, stats["bytes"] / 1e6 / dt, stats["files"] / dt, stats["dedup"], stats["errors"]), flush=True)
