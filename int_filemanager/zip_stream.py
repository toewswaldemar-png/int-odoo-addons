"""ZIP download of a selection of nodes (Konzept 8): the entries are collected with the
CALLER's rights (only nodes the caller can read appear), and the archive is written as a
stream - never held in memory (I12) and never needing a seekable output, so the same
generator serves the direct download and the background job that writes it to a file.

Entries are stored, not compressed: the file manager runs on a LAN, and compressing
would hold a worker for the whole download (Konzept 8: "belegt einen Worker").
"""

import os
import unicodedata
import zipfile
from collections import namedtuple
from datetime import timezone

from odoo.exceptions import UserError
from odoo.tools import config

from . import blobstore

PIECE_BYTES = 1024 * 1024
DEFAULT_DIRECT_MAX_MB = 500
DIRECT_MAX_PARAM = "int_filemanager.zip_direct_max_mb"

# path is None for a folder entry (kept so empty folders survive the round trip).
ZipEntry = namedtuple("ZipEntry", "arcname is_dir path size mtime")


def direct_max_bytes(env):
    mb = int(
        env["ir.config_parameter"].sudo().get_param(DIRECT_MAX_PARAM)
        or DEFAULT_DIRECT_MAX_MB
    )
    return mb * 1024 * 1024


def _mtime(dt):
    """ZIP dates start in 1980 and carry no time zone."""
    stamp = dt.replace(tzinfo=timezone.utc)
    return max(stamp.timetuple()[:6], (1980, 1, 1, 0, 0, 0))


def _unique_name(name, used):
    """Two selected items can share a name; the archive must not hold two entries with
    one name (extractors overwrite silently). Compared without case, like the tree."""
    candidate, n = name, 1
    while unicodedata.normalize("NFC", candidate).casefold() in used:
        n += 1
        stem, dot, ext = name.rpartition(".")
        candidate = f"{stem} ({n}).{ext}" if dot and stem else f"{name} ({n})"
    used.add(unicodedata.normalize("NFC", candidate).casefold())
    return candidate


def collect_entries(env, node_ids):
    """(entries, total_bytes, archive_name). Raises AccessError for a selected node the
    caller may not read; below a selected folder only what the caller can read is
    included (plain search under the caller's rights, no sudo - I7). Trashed nodes are
    skipped (search() is active-only)."""
    Node = env["int_filemanager.node"]
    tops = Node.browse(node_ids).exists()
    if not tops:
        raise UserError(env._("Nothing to download."))
    tops.check_access("read")

    entries, total, used_top = [], 0, set()
    for top in tops:
        base = _unique_name(top.name, used_top)
        if not top.is_dir:
            revision = top.current_revision_id
            if revision:
                entries.append(_file_entry(env, base, revision))
                total += int(revision.size)
            continue
        entries.append(ZipEntry(base + "/", True, None, 0, _mtime(top.write_date)))
        arcnames = {top.id: base}
        subtree = Node.search(
            [("id", "child_of", top.id), ("id", "!=", top.id)], order="parent_path"
        )
        # One sudo'd read for all blob hashes instead of one query per file - only
        # reached after the search above already applied the caller's rights.
        shas = {
            rev.id: rev.blob_id.sha256
            for rev in subtree.current_revision_id.sudo()  # rights checked above
        }
        for node in subtree:
            parent_arc = arcnames.get(node.parent_id.id)
            if parent_arc is None:
                continue  # its folder is not visible to the caller, so neither is it
            arcname = f"{parent_arc}/{node.name}"
            arcnames[node.id] = arcname
            if node.is_dir:
                entries.append(
                    ZipEntry(arcname + "/", True, None, 0, _mtime(node.write_date))
                )
            elif node.current_revision_id:
                revision = node.current_revision_id
                entries.append(
                    ZipEntry(
                        arcname,
                        False,
                        blobstore.blob_path(env, shas[revision.id]),
                        int(revision.size),
                        _mtime(revision.create_date),
                    )
                )
                total += int(revision.size)
    name = f"{tops[0].name}.zip" if len(tops) == 1 else "files.zip"
    return entries, total, name


def _file_entry(env, arcname, revision):
    sha256 = (
        revision.sudo().blob_id.sha256
    )  # revision was reached under the caller's rights
    return ZipEntry(
        arcname,
        False,
        blobstore.blob_path(env, sha256),
        int(revision.size),
        _mtime(revision.create_date),
    )


class _Sink:
    """Write-only, unseekable target: ZipFile then streams (data descriptors) instead
    of seeking back to patch headers. drain() hands over what was written so far."""

    def __init__(self):
        self._parts = []

    # A plain class, not a model: nothing to call super() on.
    # pylint: disable-next=unknown-option-value,method-required-super
    def write(self, data):
        self._parts.append(bytes(data))
        return len(data)

    def flush(self):
        pass

    def drain(self):
        parts, self._parts = self._parts, []
        return parts


def stream_zip(entries):
    """Generator of the archive's bytes. Touches only the filesystem, never the ORM, so
    it can run after the request's cursor is gone (a streamed response body)."""
    sink = _Sink()
    with zipfile.ZipFile(sink, "w", zipfile.ZIP_STORED, allowZip64=True) as archive:
        for entry in entries:
            info = zipfile.ZipInfo(entry.arcname, date_time=entry.mtime)
            if entry.is_dir:
                # mkdir() fills these in only when given a name, not a ZipInfo.
                info.compress_size = 0
                info.file_size = 0
                info.CRC = 0
                info.external_attr = (((0o40000 | 0o755) & 0xFFFF) << 16) | 0x10
                archive.mkdir(info)
            else:
                info.compress_type = zipfile.ZIP_STORED
                with (
                    archive.open(info, "w", force_zip64=True) as target,
                    open(entry.path, "rb") as source,
                ):
                    while piece := source.read(PIECE_BYTES):
                        target.write(piece)
                        yield from sink.drain()
            yield from sink.drain()
    yield from sink.drain()


def write_zip(entries, path):
    """The same archive into a file (background job), fsynced before it is renamed
    into place by the caller."""
    with open(path, "wb") as out:
        for piece in stream_zip(entries):
            out.write(piece)
        out.flush()
        os.fsync(out.fileno())


def zips_dir(env):
    """Below data_dir/filestore on purpose: only there does x_sendfile hand the file to
    nginx (Konzept 8, 19.2)."""
    path = os.path.join(config.filestore(env.cr.dbname), "zips")
    os.makedirs(path, exist_ok=True)
    return path
