"""Content-addressed blob storage (Konzept 5): each file's bytes live once,
named by their SHA-256, under a share mounted below <data_dir>/filestore/<db>/
so Odoo's own x_sendfile path check (`http.Stream.get_response`, "unterhalb
von data_dir/filestore") accepts it later when reading (I11/A19).

`ir.attachment` cannot do this job (Pruefbericht Nr. 33-35): content only via
`_set_attachment_data` (fully in memory), `store_fname` not settable (create/
write strip it), checksum is SHA-1, no `fsync` on write, rights tied to the
parent record.

Same checklist/spooldir pattern as Odoo's own `ir.attachment._mark_for_gc`/
`_gc_file_store` (base/models/ir_attachment.py:158-252), adapted with a grace
period: a bare "does anything still reference this file" check would race a
writer that already linked the file but has not committed its DB row yet
(A4). Matches the fm_proto prototype (`docs/prototypes/fm2/fm_proto/
blobstore.py`), with its one confirmed bug fixed: `mark_for_gc` renewing an
existing marker via `open(path, "ab")` alone does not reliably bump its mtime
(A4), so an explicit `os.utime` follows it.
"""

import hashlib
import os

from odoo.tools import config

from . import fault

CHUNK_SIZE = 1024 * 1024
EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()
BLOBS_DIRNAME = "blobs"
CHECKLIST_DIRNAME = "checklist"
TMP_DIRNAME = "tmp"


def root(env):
    return os.path.join(config.filestore(env.cr.dbname), BLOBS_DIRNAME)


def blob_path(env, sha256):
    return os.path.join(root(env), sha256[0:2], sha256[2:4], sha256)


def tmp_dir(env):
    path = os.path.join(root(env), TMP_DIRNAME)
    os.makedirs(path, exist_ok=True)
    return path


def checklist_dir(env):
    path = os.path.join(root(env), CHECKLIST_DIRNAME)
    os.makedirs(path, exist_ok=True)
    return path


def _fsync_dir(path):
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def mark_for_gc(env, sha256):
    """Add sha256 to the cleanup job's checklist (Konzept 5 "Aufraeum-
    Markierung"). Called both when a blob is newly linked (in case the
    surrounding transaction never commits) and whenever an existing one is
    reused (A4: the cleanup job must not delete a blob a concurrent writer is
    about to reference) - `os.utime` after the open is the actual renewal:
    "ab" on an already-existing, zero-byte-appended file does not reliably
    bump its mtime on its own."""
    path = os.path.join(checklist_dir(env), sha256)
    open(path, "ab").close()
    os.utime(path, None)


def hash_file(path):
    hasher = hashlib.sha256()
    size = 0
    with open(path, "rb") as f:
        while chunk := f.read(CHUNK_SIZE):
            hasher.update(chunk)
            size += len(chunk)
    return hasher.hexdigest(), size


def write_stream_to_temp(env, fileobj, name):
    """Read a file-like object into a temp file on the SAME filesystem as
    the blob store (so the later `os.link` is a same-filesystem hardlink,
    never a copy). Caller hashes separately (`hash_file`) or already knows
    the hash from streaming it (`adopt_hashed`)."""
    tmp_path = os.path.join(tmp_dir(env), name)
    with open(tmp_path, "wb") as out:
        while chunk := fileobj.read(CHUNK_SIZE):
            out.write(chunk)
        out.flush()
        os.fsync(out.fileno())
    return tmp_path


def adopt_hashed(env, tmp_path, sha256, keep_tmp=False):
    """Link an already-fsynced, already-hashed temp file onto its content
    address. Returns True if this hash was already present (deduplication) -
    the temp file's bytes are identical either way, so no overwrite is ever
    needed (I2). The temp file is only removed here if `keep_tmp` is False;
    Konzept 5 keeps it until after the DB commit that follows, so a crash in
    between leaves at most an orphan the cleanup job removes, never a lost
    upload (I3/I4)."""
    final_path = blob_path(env, sha256)
    os.makedirs(os.path.dirname(final_path), exist_ok=True)
    mark_for_gc(env, sha256)
    try:
        os.link(tmp_path, final_path)
        deduped = False
    except FileExistsError:
        deduped = True
        fault.fault_point("blob_write_after_dedup_found")
    if not keep_tmp:
        os.unlink(tmp_path)
    _fsync_dir(os.path.dirname(final_path))
    return deduped


def ensure_on_disk(env, sha256, tmp_path):
    """Re-link the blob file from a still-kept temp file if the cleanup job
    won the race and removed it between this writer linking it and its DB
    row committing (A4). No-op if the file is already there."""
    final_path = blob_path(env, sha256)
    if os.path.exists(final_path):
        return
    os.makedirs(os.path.dirname(final_path), exist_ok=True)
    os.link(tmp_path, final_path)
    _fsync_dir(os.path.dirname(final_path))


def ensure_empty_blob(env):
    """A node without content still has a revision, on the 0-byte blob
    (A7) - never a node with no revision at all."""
    final_path = blob_path(env, EMPTY_SHA256)
    if os.path.exists(final_path):
        return
    tmp_path = os.path.join(tmp_dir(env), f"empty_{os.getpid()}")
    open(tmp_path, "wb").close()
    adopt_hashed(env, tmp_path, EMPTY_SHA256)
