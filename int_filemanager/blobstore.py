"""Content-addressed blob storage.

Each content is stored once, named by its SHA-256, below
``<data_dir>/filestore/<db>/blobs`` - only below the filestore does
``http.Stream`` hand a file to nginx via x_sendfile. ir.attachment is not
used: it holds the content in memory, uses SHA-1 and ties rights to a record.

Cleanup uses the same checklist as ``ir.attachment._gc_file_store``, plus a
grace period, so a blob a writer has linked but not yet committed is not
deleted under it.
"""

import base64
import contextlib
import hashlib
import os

from odoo.tools import config

from . import fault

CHUNK_SIZE = 1024 * 1024
EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()
BLOBS_DIRNAME = "blobs"


def decode_content(content):
    """Return ``content`` as bytes; RPC callers send it as base64 text."""
    if isinstance(content, str):
        return base64.b64decode(content)
    return content


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
    """Put ``sha256`` on the cleanup checklist, or renew its mark.

    Called for new and for reused blobs, so the cleanup job does not delete a
    blob a writer is about to use. os.utime() renews the mark: opening an
    existing file in append mode does not reliably update its mtime.
    """
    path = os.path.join(checklist_dir(env), sha256)
    open(path, "ab").close()
    os.utime(path, None)


def remove_if_exists(path):
    """Delete a temp file; a file that is already gone is the goal, not an error."""
    with contextlib.suppress(FileNotFoundError):
        os.unlink(path)


def read_head(env, sha256, size=2048):
    """The first bytes of a blob, enough to tell what kind of content it is."""
    with open(blob_path(env, sha256), "rb") as f:
        return f.read(size)


def hash_file(path):
    hasher = hashlib.sha256()
    size = 0
    with open(path, "rb") as f:
        while chunk := f.read(CHUNK_SIZE):
            hasher.update(chunk)
            size += len(chunk)
    return hasher.hexdigest(), size


def write_stream_to_temp(env, fileobj, name):
    """Write ``fileobj`` to a temp file next to the blobs and return its path.

    Same filesystem as the blobs, so adopt_hashed() can hardlink it.
    """
    tmp_path = os.path.join(tmp_dir(env), name)
    with open(tmp_path, "wb") as out:
        while chunk := fileobj.read(CHUNK_SIZE):
            out.write(chunk)
        out.flush()
        os.fsync(out.fileno())
    return tmp_path


def adopt_hashed(env, tmp_path, sha256, keep_tmp=False):
    """Hardlink a hashed temp file under its hash; return True if it existed.

    An existing blob is never overwritten. Callers pass ``keep_tmp=True`` to
    keep the temp file until their transaction has committed.
    """
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
    """Link the blob again from the temp file if the cleanup job removed it."""
    final_path = blob_path(env, sha256)
    if os.path.exists(final_path):
        return
    os.makedirs(os.path.dirname(final_path), exist_ok=True)
    os.link(tmp_path, final_path)
    _fsync_dir(os.path.dirname(final_path))


def ensure_empty_blob(env):
    """Make sure the empty blob exists; empty files have a revision on it."""
    final_path = blob_path(env, EMPTY_SHA256)
    if os.path.exists(final_path):
        return
    tmp_path = os.path.join(tmp_dir(env), f"empty_{os.getpid()}")
    open(tmp_path, "wb").close()
    adopt_hashed(env, tmp_path, EMPTY_SHA256)
