import contextlib
import hashlib
import itertools
import os
import re
import time
import unicodedata
import uuid

import psycopg2.errors
from psycopg2 import IntegrityError

from odoo import api, fields, models
from odoo.exceptions import MissingError, UserError
from odoo.http import Stream
from odoo.tools import SQL

BLOB_FOLDER = "int_filemanager"
UPLOAD_FOLDER = ".upload"
# The blobs to look at: one empty file per checksum, like the core's "checklist" for attachments
# (its cleaner would delete our blobs, so the lists must stay apart).
CHECKLIST_FOLDER = ".checklist"
# Blobs looked at per run of the cleaner; each run holds the lock of the table (see _gc_blobs).
GC_BATCH = 1000
GC_LOCK_TIMEOUT = "10s"
UPLOAD_AGE_PARAMETER = "int_filemanager.upload_max_age_hours"
DEFAULT_UPLOAD_MAX_AGE_HOURS = 24
CHECKSUM_REGEX = re.compile(r"[0-9a-f]{64}")
CHUNK_SIZE = 1024 * 1024
# The head of a file is enough for ``guess_mimetype`` (it reads no more than this).
HEAD_SIZE = 2048
NAME_MAX_LENGTH = 255
# Names tried for one upload ("a.txt", "a (2).txt", ...) before giving up.
NAME_TRIES = 1000
# Set by the storage only (see ``write``), like the core does for ``ir.attachment``.
STORAGE_FIELDS = ("checksum", "size", "mimetype")


def _remove_file(path):
    with contextlib.suppress(FileNotFoundError):
        os.unlink(path)


class IntFilemanagerDocument(models.Model):
    """A file: an ordinary record that points to a blob in the filestore.

    The bytes lie in ``<filestore>/int_filemanager/<sha256[:2]>/<sha256>``, not in
    ``ir.attachment`` (its size field is an int4, and it holds a whole file in memory).
    Documents are only created by the storage (``_create_from_stream``), which runs as
    superuser: the users have no right to create them.
    """

    _name = "int.filemanager.document"
    _description = "Filemanager document"
    _inherit = ["mail.thread"]
    _order = "name"

    name = fields.Char(required=True)
    folder_id = fields.Many2one(
        "int.filemanager.folder", required=True, index=True, ondelete="restrict"
    )
    checksum = fields.Char(readonly=True, required=True, index=True)
    # Float, not Integer: an int4 column overflows above 2 GiB.
    size = fields.Float(readonly=True)
    mimetype = fields.Char(readonly=True)
    active = fields.Boolean(default=True)
    tag_ids = fields.Many2many(
        "int.filemanager.tag",
        "int_filemanager_document_tag_rel",
        "document_id",
        "tag_id",
        string="Tags",
    )
    company_id = fields.Many2one(
        related="folder_id.company_id", store=True, index=True
    )
    origin_path = fields.Char(groups="base.group_system", copy=False)
    # A binary field that holds nothing: ``ir.binary`` only streams a record's *binary field*
    # (``/web/content/<model>/<id>/content``). The bytes come from the blob, see
    # ``_to_http_stream``; reading the field yields False, it is not in the views.
    content = fields.Binary(
        compute="_compute_content",
        inverse="_inverse_content",
        copy=False,
        exportable=False,
    )

    _name_per_folder = models.UniqueIndex(
        '(folder_id, lower(name COLLATE "und-x-icu")) WHERE active',
        "A document with this name already exists in this folder.",
    )
    _checksum_is_sha256 = models.Constraint(
        "CHECK (checksum ~ '^[0-9a-f]{64}$')",
        "The checksum must be a SHA-256 in lowercase hexadecimal.",
    )
    # A hash index only finds an equal path (a btree index fails above about 2.7 KB).
    _origin_path_index = models.Index("USING hash (origin_path)")

    def _compute_content(self):
        self.content = False

    def _inverse_content(self):
        raise UserError(self.env._("The file of a document is set by the upload only."))

    def write(self, vals):
        # ``readonly`` holds in the interface only: through RPC a user could point a document
        # at another blob or give it another type. Like ``ir.attachment``, drop such values;
        # the storage runs as superuser. Creating is closed by the missing access right.
        if not self.env.su:
            vals = {key: value for key, value in vals.items() if key not in STORAGE_FIELDS}
        if vals.get("active") and not self.env.context.get("int_filemanager_cascade"):
            for document in self.filtered(lambda document: not document.active):
                if not document.folder_id.active:
                    raise UserError(
                        self.env._(
                            "Restore the folder %(folder)s first, it contains %(name)s.",
                            folder=document.folder_id.display_name,
                            name=document.name,
                        )
                    )
        old_checksums = set(self.mapped("checksum")) if "checksum" in vals else set()
        result = super().write(vals)
        if old_checksums:
            # Another file: the blob it had may be free now (the cleaner looks).
            for checksum in old_checksums - {vals["checksum"]}:
                self._mark_blob_for_gc(checksum)
        return result

    def unlink(self):
        # First delete the rows, then mark the blobs, like ir.attachment.unlink. A blob that
        # another document uses (or an archived one) is kept by the cleaner.
        checksums = set(self.mapped("checksum"))
        result = super().unlink()
        for checksum in checksums:
            self._mark_blob_for_gc(checksum)
        return result

    def action_download(self):
        """Let the browser download the file (the route is the core's, see ``_to_http_stream``)."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/{self._name}/{self.id}/content?download=true",
            "target": "download",
        }

    @api.model
    def _blob_path(self, checksum):
        """The absolute path of the blob with this SHA-256 checksum."""
        if not CHECKSUM_REGEX.fullmatch(checksum or ""):
            raise ValueError("A checksum is 64 lowercase hexadecimal characters.")
        return self.env["ir.attachment"]._full_path(
            f"{BLOB_FOLDER}/{checksum[:2]}/{checksum}"
        )

    @api.model
    def _store_stream(self, stream, name, mimetype=None):
        """Write ``stream`` block by block to a temporary file and measure it.

        The temporary file lies next to the blobs (same file system, so ``_publish_blob`` can
        rename it). It is removed again if this fails or the transaction is rolled back.
        Nothing is held in memory but one block.

        :param stream: file-like object with ``read(size)``
        :param name: file name, to guess the type
        :param mimetype: type given by the client, if any
        :return: ``{"tmp_path", "checksum", "size", "mimetype"}``
        """
        upload_dir = self._upload_dir()
        os.makedirs(upload_dir, exist_ok=True)
        tmp_path = os.path.join(upload_dir, uuid.uuid4().hex)
        self.env.cr.postrollback.add(lambda: _remove_file(tmp_path))
        digest = hashlib.sha256()
        size = 0
        head = b""
        written = False
        try:
            with open(tmp_path, "xb") as out:
                while chunk := stream.read(CHUNK_SIZE):
                    head += chunk[: HEAD_SIZE - len(head)]
                    digest.update(chunk)
                    out.write(chunk)
                    size += len(chunk)
            written = True
        finally:
            if not written:
                _remove_file(tmp_path)
        # The core's rules: client type, then file name, then the head; html, svg and xml
        # become text/plain (office formats excepted), for every user. A client that sends
        # "any binary" says nothing: the core would skip the file name for it.
        if mimetype == "application/octet-stream":
            mimetype = None
        values = (
            self.env["ir.attachment"]
            .with_context(image_no_postprocess=True, attachments_mime_plainxml=True)
            ._check_contents({"name": name, "mimetype": mimetype, "raw": head})
        )
        return {
            "tmp_path": tmp_path,
            "checksum": digest.hexdigest(),
            "size": size,
            "mimetype": values["mimetype"],
        }

    @api.model
    def _publish_blob(self, tmp_path, checksum):
        """Move the temporary file of ``_store_stream`` to its place among the blobs.

        Call it after the document is created and flushed: the cleaner of the blobs
        (it waits for this transaction) then sees the document. A blob that exists already has
        the same content and stays.
        """
        path = self._blob_path(checksum)
        if os.path.exists(path):
            _remove_file(tmp_path)
            return
        # Before the blob exists, put it on the checklist: if this transaction is rolled back,
        # the cleaner finds the blob without a document and deletes it (like the core does).
        self._mark_blob_for_gc(checksum)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        os.replace(tmp_path, path)

    @api.model
    def _upload_dir(self):
        return os.path.join(self.env["ir.attachment"]._filestore(), BLOB_FOLDER, UPLOAD_FOLDER)

    @api.model
    def _checklist_dir(self):
        return os.path.join(self.env["ir.attachment"]._filestore(), BLOB_FOLDER, CHECKLIST_FOLDER)

    @api.model
    def _mark_blob_for_gc(self, checksum):
        """Put the blob on the checklist: the cleaner deletes it if no document uses it."""
        self._blob_path(checksum)  # only a checksum goes into a path
        folder = os.path.join(self._checklist_dir(), checksum[:2])
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, checksum), "ab"):
            pass

    @api.model
    def _checklist_entries(self):
        """The checksums on the checklist (a generator, the list may be long)."""
        for folder, _subfolders, names in os.walk(self._checklist_dir()):
            for name in names:
                if CHECKSUM_REGEX.fullmatch(name):
                    yield name, os.path.join(folder, name)

    @api.autovacuum
    def _gc_blobs(self):
        """Delete the blobs on the checklist that no document uses (any more).

        Like ``ir.attachment._gc_file_store``: the table of the documents is locked against
        writers while the rows are looked at, so a document that is being created (its row
        is made before its blob) is either seen or waits until the cleaner is done. Unlike the
        core, one run takes a batch only: the lock must not be held for a long time, and
        ``(done, remaining)`` makes Odoo call it again.
        """
        cr = self.env.cr
        if not os.path.isdir(self._checklist_dir()):
            return 0, 0
        # Continue in a new transaction: the LOCK must be the first statement of it, otherwise
        # its snapshot (REPEATABLE READ) may not hold what concurrent transactions just wrote.
        cr.commit()
        timeout = self.env.context.get("int_filemanager_lock_timeout", GC_LOCK_TIMEOUT)
        cr.execute(SQL("SET LOCAL lock_timeout TO %s", timeout))
        try:
            cr.execute(SQL("LOCK %s IN SHARE MODE", SQL.identifier(self._table)))
        except psycopg2.errors.LockNotAvailable:
            cr.rollback()  # a writer is busy; the next run tries again
            return 0, 0
        entries = list(itertools.islice(self._checklist_entries(), GC_BATCH))
        used = {
            checksum
            for [checksum] in self.sudo()
            .with_context(active_test=False)
            ._read_group([("checksum", "in", [name for name, _path in entries])], ["checksum"])
        }
        for checksum, marker in entries:
            if checksum not in used:
                _remove_file(self._blob_path(checksum))
            _remove_file(marker)
        cr.commit()  # releases the lock
        remaining = any(True for _entry in itertools.islice(self._checklist_entries(), 1))
        return len(entries), int(remaining)

    @api.autovacuum
    def _gc_blob_uploads(self):
        """Delete the temporary files of uploads that never ended (a crash leaves them)."""
        upload_dir = self._upload_dir()
        if not os.path.isdir(upload_dir):
            return
        value = self.env["ir.config_parameter"].sudo().get_param(UPLOAD_AGE_PARAMETER)
        try:
            hours = int(value) if value else DEFAULT_UPLOAD_MAX_AGE_HOURS
        except ValueError:
            hours = DEFAULT_UPLOAD_MAX_AGE_HOURS
        oldest_kept = time.time() - hours * 3600
        for entry in os.scandir(upload_dir):
            if entry.is_file() and entry.stat().st_mtime < oldest_kept:
                _remove_file(entry.path)

    @api.model
    def _create_from_stream(self, stream, name, folder, mimetype=None, **values):
        """Store a file and create its document: the one way a document comes to be.

        Runs as superuser (the users cannot create documents), so the caller has to check
        first that the user may write into ``folder``.

        :param stream: file-like object with ``read(size)``
        :param name: name of the document, also used to guess the type
        :param folder: ``int.filemanager.folder`` record
        :param mimetype: type given by the client, if any
        :param values: more field values, e.g. ``tag_ids``
        :return: the document, with the environment of the caller
        """
        name = self._clean_name(name)
        stored = self._store_stream(stream, name, mimetype)
        try:
            document = self._create_numbered(stored, name, folder, **values)
            self._publish_blob(stored["tmp_path"], stored["checksum"])
        finally:
            # Nothing is left of a failed attempt.
            _remove_file(stored["tmp_path"])
        return document

    @api.model
    def _clean_name(self, name):
        """A name as the browser or the disk gives it, made fit for a document.

        Only the last part of a path stays, the characters are composed (NFC: an "ä" typed
        as one character and as "a" plus a mark are one name), control characters go.
        """
        name = (name or "").replace("\\", "/").rsplit("/", 1)[-1]
        name = unicodedata.normalize("NFC", name)
        name = "".join(char for char in name if unicodedata.category(char) != "Cc").strip()
        if name in ("", ".", ".."):
            raise UserError(self.env._("A file needs a name."))
        if len(name) > NAME_MAX_LENGTH:
            stem, extension = os.path.splitext(name)
            name = stem[: NAME_MAX_LENGTH - len(extension)] + extension
        return name

    @api.model
    def _create_numbered(self, stored, name, folder, **values):
        """Create the document under ``name``, or under the first free ``stem (2).ext``.

        Two documents of a folder cannot share a name (case aside). The names that are taken
        are looked up in one go; one that slips through (another case, a parallel upload) is
        caught by the unique index of the database. Odoo does not retry on that error.
        """
        stem, extension = os.path.splitext(name)

        def numbered(number):
            return name if number == 1 else f"{stem} ({number}){extension}"

        taken = {
            document.name.lower()
            for document in self.sudo().search_fetch(
                [
                    ("folder_id", "=", folder.id),
                    ("name", "in", [numbered(number) for number in range(1, 101)]),
                ],
                ["name"],
            )
        }
        constraint = self._name_per_folder.full_name(self)
        for number in range(1, NAME_TRIES + 1):
            candidate = numbered(number)
            if candidate.lower() in taken:
                continue
            try:
                with self.env.cr.savepoint():
                    document = (
                        self.sudo()
                        .create(
                            {
                                **values,
                                "name": candidate,
                                "folder_id": folder.id,
                                "checksum": stored["checksum"],
                                "size": stored["size"],
                                "mimetype": stored["mimetype"],
                            }
                        )
                        .with_env(self.env)
                    )
                    # The row must exist before the blob does: the cleaner looks at the rows.
                    document.sudo().flush_recordset(["checksum"])
            except IntegrityError as error:
                if error.diag.constraint_name != constraint:
                    raise
                taken.add(candidate.lower())
            else:
                return document
        raise UserError(self.env._("No free name for %(name)s in this folder.", name=name))

    def _to_http_stream(self):
        """The blob as a stream for the download.

        ``ir.binary._record_to_stream`` calls it. The stream is a path, so with
        ``--x-sendfile`` the proxy delivers the file and Odoo's thread is free. The checksum is
        the ETag (the blob never changes), the request is cached and answered with 304 or a range
        by the core.
        """
        self.ensure_one()
        path = self._blob_path(self.checksum)
        try:
            size = os.stat(path).st_size
        except FileNotFoundError:
            raise MissingError(self.env._("The file of this document is missing.")) from None
        return Stream(
            type="path",
            path=path,
            mimetype=self.mimetype,
            download_name=self.name,
            etag=self.checksum,
            last_modified=self.write_date,
            size=size,
        )
