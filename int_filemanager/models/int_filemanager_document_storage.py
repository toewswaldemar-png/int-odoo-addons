"""The storage of the files of the documents.

It holds the blobs in the filestore, their garbage collector, the upload and the cleaning of
the trash (the archived documents that nobody takes back)."""

import hashlib
import itertools
import os
import time
import uuid

import psycopg2.errors

from odoo import api, models
from odoo.exceptions import UserError
from odoo.tools import SQL

from ..tools.files import remove_file
from ..tools.filestore import check_contents, filestore, full_path
from .int_filemanager_cron import TRASH_ENABLED_DEFAULT
from .int_filemanager_document import BLOB_FOLDER, CHECKSUM_REGEX, PREVIEW_CRON_XMLID, PREVIEW_EXTENSIONS
from .int_filemanager_named import NAME_MAX_LENGTH


UPLOAD_FOLDER = ".upload"
# The blobs to check: one empty file per checksum, like the checklist of ``ir.attachment`` (its
# garbage collector would delete our blobs, so the lists must stay apart).
CHECKLIST_FOLDER = ".checklist"
# Blobs checked per run of the garbage collector; each run holds the lock of the table (see
# ``_gc_blobs``).
GC_BATCH = 1000
GC_LOCK_TIMEOUT = "10s"
# First key of the advisory lock that publishers of one checksum take (see _publish_blob).
BLOB_LOCK_NAME = "int_filemanager.blob"
CHUNK_SIZE = 1024 * 1024
# The start of a file is enough for ``guess_mimetype`` (it reads no more than this).
HEAD_SIZE = 2048


class IntFilemanagerDocument(models.Model):
    _inherit = "int.filemanager.document"

    @api.model
    def _blob_path(self, checksum):
        if not CHECKSUM_REGEX.fullmatch(checksum or ""):
            raise ValueError("A checksum is 64 lowercase hexadecimal characters.")
        return full_path(self.env, f"{BLOB_FOLDER}/{checksum[:2]}/{checksum}")

    @api.model
    def _store_stream(self, stream, name, mimetype=None):
        """Write ``stream`` block by block to a temporary file and measure it.

        The temporary file lies next to the blobs (same file system, so ``_publish_blob`` can
        rename it). It is removed again if this fails or the transaction is rolled back. Nothing
        is held in memory but one block.

        :param stream: file-like object with ``read(size)``
        :param name: file name, to guess the type
        :param mimetype: type given by the client, if any
        :return: ``{"tmp_path", "checksum", "size", "mimetype"}``
        """
        upload_dir = self._upload_dir()
        os.makedirs(upload_dir, exist_ok=True)
        tmp_path = os.path.join(upload_dir, uuid.uuid4().hex)
        self.env.cr.postrollback.add(lambda: remove_file(tmp_path))
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
                remove_file(tmp_path)
        # The rules of Odoo: client type, then file name, then the start of the file; html, svg and
        # xml become text/plain (office formats excepted), for every user. A client that sends
        # "any binary" says nothing: Odoo would skip the file name for it.
        if mimetype == "application/octet-stream":
            mimetype = None
        values = check_contents(self.env, name, mimetype, head)
        return {
            "tmp_path": tmp_path,
            "checksum": digest.hexdigest(),
            "size": size,
            "mimetype": values["mimetype"],
        }

    @api.model
    def _publish_blob(self, tmp_path, checksum):
        """Move the temporary file of ``_store_stream`` to its place among the blobs.

        Call it after the document is created and flushed: the garbage collector of the blobs (it
        waits for this transaction) then sees the document. A blob that exists already has the
        same content and stays: it is never replaced, as a reader that has it open or is about to
        open it must not find a gap (``os.replace`` over a name can fail a reader on a network
        share).

        Two transactions that publish the same checksum at once take turns: the first places the
        blob, the second finds it after the lock and only removes its own temporary file.
        """
        path = self._blob_path(checksum)
        if os.path.exists(path):
            remove_file(tmp_path)
            return
        # One publisher per checksum, until this transaction ends (a blob placed by a transaction
        # that is rolled back stays on the disk, the garbage collector removes it). Look again after
        # the lock: the transaction we waited for may have placed it. The two-key form is a key
        # space of its own, so the one-key locks of Odoo (``mail_thread``) cannot clash.
        self.env.cr.execute(
            SQL("SELECT pg_advisory_xact_lock(hashtext(%s), hashtext(%s))", BLOB_LOCK_NAME, checksum)
        )
        if os.path.exists(path):
            remove_file(tmp_path)
            return
        # Before the blob exists, put it on the checklist: if this transaction is rolled back, the
        # garbage collector finds the blob without a document and deletes it (as ``ir.attachment`` does).
        self._mark_blob_for_gc(checksum)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        os.replace(tmp_path, path)

    @api.model
    def _upload_dir(self):
        return os.path.join(filestore(self.env), BLOB_FOLDER, UPLOAD_FOLDER)

    @api.model
    def _checklist_dir(self):
        return os.path.join(filestore(self.env), BLOB_FOLDER, CHECKLIST_FOLDER)

    @api.model
    def _mark_blob_for_gc(self, checksum):
        self._blob_path(checksum)  # only a checksum goes into a path
        folder = os.path.join(self._checklist_dir(), checksum[:2])
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, checksum), "ab"):
            pass

    @api.model
    def _checklist_entries(self):
        for folder, _subfolders, names in os.walk(self._checklist_dir()):
            for name in names:
                if CHECKSUM_REGEX.fullmatch(name):
                    yield name, os.path.join(folder, name)

    @api.model
    def _gc_lock_tables(self):
        """Return the tables that hold checksums of blobs, in the order the garbage collector locks them.
        """
        return [self._table]

    @api.model
    def _blobs_in_use(self, names):
        """Return those of these checksums that a document uses, as its file or as its preview."""
        # sudo: the garbage collector asks about the documents of all users and companies
        documents = self.sudo().with_context(active_test=False)
        return {
            checksum for [checksum] in documents._read_group([("checksum", "in", names)], ["checksum"])
        } | {
            checksum
            for [checksum] in documents._read_group([("preview_checksum", "in", names)], ["preview_checksum"])
        }

    @api.autovacuum
    def _gc_blobs(self):
        """Delete the blobs on the checklist that no document uses (any more).

        A blob counts as used if a *document* has its checksum or its preview
        (``_blobs_in_use``). Whoever lets another model keep blobs of this storage must add
        that model's checksums there and its table to ``_gc_lock_tables``, or the blobs are
        deleted. The tables are locked in a fixed order (the documents first).
        """
        # Like ``ir.attachment._gc_file_store``, lock the table of the documents against writers
        # while the rows are checked, so a document that is being created (its row is made before
        # its blob) is either seen or waits until the run is done. Unlike Odoo, one run takes a
        # batch only: the lock must not be held for long, and ``(done, remaining)`` makes Odoo
        # call it again.
        cr = self.env.cr
        if not os.path.isdir(self._checklist_dir()):
            return 0, 0
        # Continue in a new transaction: the LOCK must be the first statement of it, otherwise
        # its snapshot (REPEATABLE READ) may not hold what concurrent transactions just wrote.
        cr.commit()
        timeout = self.env.context.get("int_filemanager_lock_timeout", GC_LOCK_TIMEOUT)
        cr.execute(SQL("SET LOCAL lock_timeout TO %s", timeout))
        try:
            for table in self._gc_lock_tables():
                cr.execute(SQL("LOCK %s IN SHARE MODE", SQL.identifier(table)))
        except psycopg2.errors.LockNotAvailable:
            cr.rollback()  # a writer is busy; the next run tries again
            return 0, 0
        entries = list(itertools.islice(self._checklist_entries(), GC_BATCH))
        names = [name for name, _path in entries]
        used = self._blobs_in_use(names)
        for checksum, marker in entries:
            if checksum not in used:
                remove_file(self._blob_path(checksum))
            remove_file(marker)
        cr.commit()  # releases the lock
        remaining = any(True for _entry in itertools.islice(self._checklist_entries(), 1))
        return len(entries), int(remaining)

    @api.autovacuum
    def _gc_blob_uploads(self):
        upload_dir = self._upload_dir()
        if not os.path.isdir(upload_dir):
            return
        hours = self.env["int.filemanager.cron"]._setting("upload_max_age_hours")
        oldest_kept = time.time() - hours * 3600
        for entry in os.scandir(upload_dir):
            if entry.is_file() and entry.stat().st_mtime < oldest_kept:
                remove_file(entry.path)

    @api.autovacuum
    def _gc_trash(self):
        """Delete the archived documents that stayed longer than the settings allow.

        Their files follow by the garbage collectors of the blobs and of the texts. Deleted in
        batches: Odoo calls it again for as long as it reports that documents are left.
        """
        cron = self.env["int.filemanager.cron"]
        if not cron._flag("trash_enabled", TRASH_ENABLED_DEFAULT):
            return 0, 0
        # sudo: the scheduled action has the companies of its user only, and the rules would hide the
        # documents of the others
        found = self.sudo().with_context(active_test=False).search(
            [("active", "=", False), ("archived_date", "<=", f"-{cron._setting('trash_days')}d")],
            limit=GC_BATCH + 1,
        )
        found[:GC_BATCH].unlink()
        return len(found[:GC_BATCH]), int(len(found) > GC_BATCH)

    @api.model
    def _create_from_stream(self, stream, name, folder, mimetype=None, check=None, **values):
        """Store a file and create its document: the one way a document comes to be.

        The right to write into ``folder`` is checked here, once, before a byte is stored:
        the user of ``folder.env`` must be allowed to write into it (``check_access``, which
        a superuser passes). A caller that has checked the right another way passes
        ``folder.sudo()``: an upload at a record, a share, the import.

        :param stream: file-like object with ``read(size)``
        :param name: name of the document, also used to guess the type
        :param folder: ``int.filemanager.folder`` record, in the environment of the one who stores
        :param mimetype: type given by the client, if any
        :param check: called with the result of ``_store_stream`` (size, checksum, type)
            before the document is made; it refuses the file by raising. Only the temporary
            file exists then and is removed (a kept blob cannot be taken back by a rollback).
        :param values: more field values, e.g. ``tag_ids``
        :return: the document, with the environment of the caller
        """
        folder.check_access("write")
        name = self._clean_name(name)
        stored = self._store_stream(stream, name, mimetype)
        try:
            if check:
                check(stored)
            # The document is made as superuser: users cannot create documents, as with a checksum of
            # their choice they could point a document at any blob
            document = self._create_numbered(stored, name, folder, **values)
            self._publish_blob(stored["tmp_path"], stored["checksum"])
        finally:
            # A failed attempt leaves nothing behind.
            remove_file(stored["tmp_path"])
        if stored["mimetype"] in PREVIEW_EXTENSIONS:
            # sudo: ir.cron: the scheduled action belongs to the superuser
            self.env.ref(PREVIEW_CRON_XMLID).sudo()._trigger()
        return document

    @api.model
    def _clean_name(self, name):
        """Return a name as the browser or the disk gives it, made fit for a document.

        Only the last part of a path stays, the characters are cleaned like every name
        (``_normalize_name``), and a name that is too long loses the end of its stem.
        """
        name = self._normalize_name((name or "").replace("\\", "/").rsplit("/", 1)[-1])
        if name in ("", ".", ".."):
            raise UserError(self.env._("A file needs a name."))
        if len(name) > NAME_MAX_LENGTH:
            stem, extension = os.path.splitext(name)
            name = stem[: NAME_MAX_LENGTH - len(extension)] + extension
        return name

    @api.model
    def _create_numbered(self, stored, name, folder, **values):
        """Create the document under ``name``, or under the first free ``stem (2).ext``.

        The rows of an upload are no news: no message of its creation in the chatter, and the user
        does not follow the document (20,000 files of a folder would be 20,000 messages and
        follower rows). What is done to it later is logged as usual.
        """
        # sudo: users cannot create documents (see the class docstring)
        documents = self.sudo().with_context(mail_create_nolog=True, mail_create_nosubscribe=True)

        def create(candidate):
            document = documents.create(
                {
                    **values,
                    "name": candidate,
                    "folder_id": folder.id,
                    "checksum": stored["checksum"],
                    "size": stored["size"],
                    "mimetype": stored["mimetype"],
                }
            )
            # The row must exist before the blob does: the blob garbage collector looks at the rows.
            document.flush_recordset(["checksum"])
            return document.with_env(self.env)

        return self.sudo()._create_numbered_name(
            name, [("folder_id", "=", folder.id)], self._name_per_folder, create
        )

    @api.model
    def _numbered_name(self, name, number):
        stem, extension = os.path.splitext(name)
        return f"{stem} ({number}){extension}"
