import base64
import contextlib
import hashlib
import importlib.util
import itertools
import logging
import os
import re
import subprocess
import sys
import time
import unicodedata
import uuid

import psycopg2.errors
from psycopg2 import IntegrityError

from odoo import api, fields, models
from odoo.exceptions import MissingError, UserError
from odoo.fields import Domain
from odoo.http import Stream
from odoo.tools import SQL
from odoo.tools.mimetypes import get_extension

from ..tools.clash import clash_summary, clashing_names
from ..tools.zip_stream import ZipEntry, export_names
from .int_filemanager_text_page import folded

_logger = logging.getLogger(__name__)

BLOB_FOLDER = "int_filemanager"
UPLOAD_FOLDER = ".upload"
# The blobs to look at: one empty file per checksum, like the core's "checklist" for attachments
# (its cleaner would delete our blobs, so the lists must stay apart).
CHECKLIST_FOLDER = ".checklist"
# Blobs looked at per run of the cleaner; each run holds the lock of the table (see _gc_blobs).
GC_BATCH = 1000
GC_LOCK_TIMEOUT = "10s"
# First key of the advisory lock that publishers of one checksum take (see _publish_blob).
BLOB_LOCK_NAME = "int_filemanager.blob"
# The most bytes of the files in one ZIP. The server stops a request after 30 minutes in our setup
# (limit_time_real), and a slow line keeps it that long: see docs/int_filemanager_erkenntnisse.md.
ZIP_MAX_SIZE_PARAMETER = "int_filemanager.zip_max_size"
DEFAULT_ZIP_MAX_SIZE = 10 * 1024**3
# The ids of a ZIP go into the address, and the proxy takes 8 KB of the request line.
ZIP_PATH_MAX_LENGTH = 7000
ZIP_PATH = "/int_filemanager/zip/"
# Names of missing files shown in a message.
MISSING_NAMES_SHOWN = 5
UPLOAD_AGE_PARAMETER = "int_filemanager.upload_max_age_hours"
DEFAULT_UPLOAD_MAX_AGE_HOURS = 24
CHECKSUM_REGEX = re.compile(r"[0-9a-f]{64}")
CHUNK_SIZE = 1024 * 1024
# The head of a file is enough for ``guess_mimetype`` (it reads no more than this).
HEAD_SIZE = 2048
NAME_MAX_LENGTH = 255
# Names tried for one upload ("a.txt", "a (2).txt", ...) before giving up.
NAME_TRIES = 1000
# The context key with the words of the full text search (see ``content_hits``), and how many
# of them, and how long, are looked at.
CONTENT_WORDS_KEY = "int_filemanager_words"
CONTENT_WORDS_MAX = 10
CONTENT_WORD_LENGTH = 200
# The hits that the list loads at a time for one file (``get_content_hits``), and the most a call may ask for.
CONTENT_BLOCK = 20
CONTENT_BLOCK_MAX = 50
# Set by the storage only (see ``write``), like the core does for ``ir.attachment``. The picture
# of a PDF and its state are made by the scheduled action alone; the share a file came in
# through, by the upload of the share.
STORAGE_FIELDS = (
    "checksum",
    "size",
    "mimetype",
    "thumbnail",
    "thumbnail_state",
    "share_id",
    "edit_source_id",
    "edit_state",
)
# The most bytes of the state that the picture editor stores with a picture (the marks, the
# filters, the crop, and the small pictures that were put into the editor).
EDIT_STATE_MAX_SIZE = 8 * 1024**2
# The picture of the first page of a PDF (``_cron_thumbnails``): the longer side in pixels, the
# files drawn per run, the time and the memory one page may take. A child process draws it
# (``tools/pdf_thumbnail.py``): a broken file may crash the PDF library.
PDF = "application/pdf"
THUMBNAIL_CRON_XMLID = "int_filemanager.int_filemanager_thumbnail_cron"
THUMBNAIL_SIZE = 256
THUMBNAIL_BATCH = 100
THUMBNAIL_SECONDS = 60
THUMBNAIL_MEMORY_MIB = 1024
PDF_THUMBNAIL = os.path.join(os.path.dirname(os.path.dirname(__file__)), "tools", "pdf_thumbnail.py")


def _remove_file(path):
    with contextlib.suppress(FileNotFoundError):
        os.unlink(path)


def _files_in(directory):
    """The names of the files in a directory, none if it is not there."""
    try:
        with os.scandir(directory) as listing:
            return {entry.name for entry in listing}
    except FileNotFoundError:
        return set()


class IntFilemanagerDocument(models.Model):
    """A file: an ordinary record that points to a blob in the filestore.

    The bytes lie in ``<filestore>/int_filemanager/<sha256[:2]>/<sha256>``, not in
    ``ir.attachment`` (its size field is an int4, and it holds a whole file in memory).
    Documents are only created by the storage (``_create_from_stream``), which runs as
    superuser: the users have no right to create them.
    """

    _name = "int.filemanager.document"
    _description = "Filemanager document"
    _inherit = ["mail.thread", "mail.activity.mixin", "int.filemanager.shareable"]
    _order = "name"
    _share_target = "document_id"

    name = fields.Char(required=True, tracking=True)
    folder_id = fields.Many2one(
        "int.filemanager.folder",
        required=True,
        index=True,
        ondelete="restrict",
        tracking=True,
    )
    checksum = fields.Char(readonly=True, required=True, index=True)
    # Float, not Integer: an int4 column overflows above 2 GiB.
    size = fields.Float(readonly=True)
    mimetype = fields.Char(readonly=True)
    active = fields.Boolean(default=True, tracking=True)
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
    # The share (link for guests) that a guest uploaded the file through; empty for all others.
    share_id = fields.Many2one(
        "int.filemanager.share",
        string="Uploaded through",
        readonly=True,
        copy=False,
        index="btree_not_null",
        ondelete="set null",
    )
    # What the picture editor leaves with a picture it stored: the picture it started from and the
    # state of the editor (marks, filters, crop) on that picture, so that the next edit finds the
    # marks as objects again. Both are set by the storage only; the editor reads them through
    # ``get_edit_session``, which hands out the source only to someone who may read it.
    edit_source_id = fields.Many2one(
        "int.filemanager.document",
        string="Edited from",
        readonly=True,
        copy=False,
        index="btree_not_null",
        ondelete="set null",
        groups="base.group_system",
    )
    edit_state = fields.Json(
        string="Editor state",
        readonly=True,
        copy=False,
        exportable=False,
        groups="base.group_system",
    )
    # A binary field that holds nothing: ``ir.binary`` only streams a record's *binary field*
    # (``/web/content/<model>/<id>/content``). The bytes come from the blob, see
    # ``_to_http_stream``; reading the field yields False, it is not in the views.
    content = fields.Binary(
        compute="_compute_content",
        inverse="_inverse_content",
        copy=False,
        exportable=False,
    )
    # The same for the PDF that the text recognition made of a scan (it has a text layer, the
    # viewer searches in it). Served by ``_to_ocr_http_stream`` for the viewer only: the
    # download is the original.
    ocr_content = fields.Binary(
        string="Recognized PDF (file)",
        compute="_compute_ocr_content",
        inverse="_inverse_content",
        copy=False,
        exportable=False,
    )
    # The checksum of that PDF, empty if there is none; the viewer asks for it to choose the
    # address, and it changes the address of the file when the PDF changes.
    ocr_checksum = fields.Char(
        string="Recognized PDF",
        compute="_compute_ocr_checksum",
        copy=False,
        exportable=False,
    )
    # The first page of a PDF as a small picture for the list and the kanban. Made by the
    # scheduled action ``_cron_thumbnails`` on the server: the core's ``thumbnail`` of the
    # attachments of a message is made by the browser and only when somebody looks at the file.
    thumbnail = fields.Image(
        max_width=THUMBNAIL_SIZE,
        max_height=THUMBNAIL_SIZE,
        readonly=True,
        copy=False,
        exportable=False,
    )
    # Empty while a PDF waits for its picture, and for every other type. A PDF that cannot be
    # drawn is "failed" and is not tried again.
    thumbnail_state = fields.Selection(
        [("done", "Done"), ("failed", "Failed")],
        string="Picture state",
        readonly=True,
        copy=False,
    )
    # The text inside the file, for the search only (the pages are in ``int.filemanager.text``).
    # Not "Content": that is the label of the binary field above, Odoo warns of two alike.
    content_search = fields.Char(
        string="Full text",
        compute="_compute_content_search",
        search="_search_content_search",
        exportable=False,
    )
    # Where the words of the full text search are, for the column of the list: set only while
    # the list is searched by them (the search puts them in the context, see the search view).
    content_hits = fields.Json(
        string="Found in the text",
        compute="_compute_content_hits",
        exportable=False,
    )
    # How many pages of the file have the words (the badge of the list).
    content_hit_count = fields.Integer(
        string="Hits",
        compute="_compute_content_hits",
        exportable=False,
    )
    # "mp3" for "song.MP3": the kind of file as the user knows it; the mimetype says "audio/mpeg".
    extension = fields.Char(compute="_compute_extension", exportable=False)

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
    # The PDFs that wait for their picture: the scheduled action looks only at these.
    _thumbnail_work_index = models.Index(
        "(id) WHERE thumbnail_state IS NULL AND mimetype = 'application/pdf'"
    )

    def _compute_content(self):
        self.content = False

    def _inverse_content(self):
        raise UserError(self.env._("The file of a document is set by the upload only."))

    def _compute_ocr_content(self):
        self.ocr_content = False

    @api.depends("checksum")
    def _compute_ocr_checksum(self):
        # The text rows are for the administrators; the checksum of the PDF is no secret to
        # whoever may read the document it belongs to.
        Text = self.env["int.filemanager.text"].sudo()
        found = {
            row.checksum: row.ocr_checksum
            for row in Text.search_fetch(
                [("checksum", "in", self.mapped("checksum")), ("ocr_checksum", "!=", False)],
                ["checksum", "ocr_checksum"],
            )
        }
        for document in self:
            document.ocr_checksum = found.get(document.checksum, False)

    def _compute_content_search(self):
        self.content_search = False

    @api.model
    def _content_words(self, words):
        """The words of a search as the search takes them: texts only, cut in length and in number."""
        if isinstance(words, str):
            words = [words]
        elif not isinstance(words, (list, tuple)):
            words = []
        words = [word[:CONTENT_WORD_LENGTH] for word in words if isinstance(word, str) and word.strip()]
        return words[:CONTENT_WORDS_MAX]

    @api.depends_context(CONTENT_WORDS_KEY)
    def _compute_content_hits(self):
        """The first page of the files that have the words of the search, with an excerpt, and the count.

        The words come from the context: the search view sets them from what was typed in the
        field "Full text". Whoever sets them by hand only gets excerpts of files they can read
        anyway (the field is read for readable documents), and no more than they could search.
        The words go with the hits: the list asks for the other hits with them.
        """
        words = self._content_words(self.env.context.get(CONTENT_WORDS_KEY) or [])
        found = self.env["int.filemanager.text.page"]._content_hits(self.mapped("checksum"), words)
        for document in self:
            entry = found.get(document.checksum)
            document.content_hits = {**entry, "words": words} if entry else False
            document.content_hit_count = entry["total"] if entry else 0

    def get_content_hits(self, words, offset=0, limit=CONTENT_BLOCK):
        """A block of the pages of this file that have the words, for the list that shows all of them.

        Public (the list calls it), so it checks the right itself: only a file that the user may
        read gives hits, and no more than the search would find.

        :param words: the words of the search (see ``_content_words``)
        :param offset: how many of the pages with a hit (by page number) are skipped
        :param limit: how many are given, at most ``CONTENT_BLOCK_MAX``
        :return: ``{"hits": [{"page", "parts", "terms"}], "total": n}``
        """
        self.ensure_one()
        self.check_access("read")
        offset = offset if isinstance(offset, int) and offset > 0 else 0
        limit = min(limit, CONTENT_BLOCK_MAX) if isinstance(limit, int) and limit > 0 else CONTENT_BLOCK
        found = self.env["int.filemanager.text.page"]._content_hits(
            [self.checksum], self._content_words(words), offset, limit
        )
        return found.get(self.checksum, {"hits": [], "total": 0})

    @api.depends("name")
    def _compute_extension(self):
        for document in self:
            document.extension = get_extension(document.name or "").lstrip(".")

    def _search_content_search(self, operator, value):
        """Documents whose file has these words in it (``websearch`` syntax: quotes, ``-``, ``or``).

        Words, not letters: ``Mueller`` finds ``Müller`` and the other way round, ``Rechnung`` finds
        ``Rechnungen``, ``Rechn`` finds nothing. A plural with an umlaut is another word: ``Haus``
        does not find ``Häuser`` (the folding makes ``haeuser``, the stemmer cuts ``haeus``). A text belongs to a blob, so every document with the
        checksum is found; the rules of the folders still decide which of them the user sees,
        as the search runs over the documents. Equal checksum means equal content, nothing
        is given away by a hit in a folder the user cannot see.
        """
        if operator == "ilike" and isinstance(value, str):
            values = [value]
        elif operator == "in" and value and all(isinstance(item, str) for item in value):
            values = list(value)  # the ORM turns ``=`` into ``in``
        else:
            return NotImplemented
        domains = [Domain.custom(to_sql=self._content_sql(item)) for item in values if item.strip()]
        return Domain.OR(domains) if domains else Domain.TRUE

    @api.model
    def _content_sql(self, words):
        def to_sql(model, alias, query):
            model.env["int.filemanager.text"]._use_search_memory()
            return SQL(
                """
                %(checksum)s IN (
                    SELECT text.checksum
                      FROM int_filemanager_text_page page
                      JOIN int_filemanager_text text ON text.id = page.text_id
                     WHERE to_tsvector('german', %(content)s)
                           @@ websearch_to_tsquery('german', %(words)s))
                """,
                checksum=model._field_to_sql(alias, "checksum", query),
                content=SQL(folded("page.content")),
                words=SQL(folded("%s::text"), words),
            )

        return to_sql

    def write(self, vals):
        # ``readonly`` holds in the interface only: through RPC a user could point a document
        # at another blob or give it another type. Like ``ir.attachment``, drop such values;
        # the storage runs as superuser. Creating is closed by the missing access right.
        if not self.env.su:
            vals = {key: value for key, value in vals.items() if key not in STORAGE_FIELDS}
        if "folder_id" in vals:
            self._check_move(vals["folder_id"])
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
        # The name that the tracking keeps of a folder is the plain one, whatever the context.
        plain = self.with_context(hierarchical_naming=False)
        result = super(IntFilemanagerDocument, plain).write(vals)
        if old_checksums:
            # Another file: the blob it had may be free now (the cleaner looks).
            for checksum in old_checksums - {vals["checksum"]}:
                self._mark_blob_for_gc(checksum)
        return result

    def _check_move(self, folder_id):
        """Check the folder that the documents are put into.

        The rights of the user (not asked of the superuser, whose acts the storage and the
        cascades are): the folder is one the user may write into, as for an upload. And the rules
        of the tree, which hold for the superuser too: the folder is in use and no name is taken
        twice there, naming the names. The unique index remains for two moves at once.
        """
        folder = self.env["int.filemanager.folder"].browse(folder_id).exists()
        moved = self.filtered(lambda document: document.folder_id != folder)
        if not (folder and moved):
            return
        if not self.env.su:
            folder.check_access("write")
        folder.sudo()._check_active_target()
        active = moved.filtered("active")
        clash = clashing_names(
            self.env, self._table, "folder_id", folder.id, active.mapped("name"), active.ids
        )
        if clash:
            raise UserError(
                self.env._(
                    "These names are taken in %(folder)s: %(names)s",
                    folder=folder.name,
                    names=clash_summary(clash),
                )
            )

    def unlink(self):
        # First delete the rows, then mark the blobs, like ir.attachment.unlink. A blob that
        # another document uses (or an archived one) is kept by the cleaner.
        checksums = set(self.mapped("checksum"))
        result = super().unlink()
        for checksum in checksums:
            self._mark_blob_for_gc(checksum)
        return result

    def action_download(self):
        """Let the browser download the file (the route is the core's, see ``_to_http_stream``).

        Several documents come as one ZIP from the route of the filemanager (``_zip_url``).
        """
        if not self:
            raise UserError(self.env._("Select at least one document."))
        if len(self) > 1:
            return {"type": "ir.actions.act_url", "url": self._zip_url(), "target": "download"}
        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/{self._name}/{self.id}/content?download=true",
            "target": "download",
        }

    def _zip_url(self):
        """The address of the ZIP of these documents, after the checks that tell the user why not.

        The route checks everything again when the browser asks: the rights and the companies
        count at that moment, not at this one. Here the user gets a message at once instead of
        an error page in a new tab.
        """
        path = ZIP_PATH + ",".join(str(document_id) for document_id in self.ids)
        if len(path) > ZIP_PATH_MAX_LENGTH:
            raise UserError(
                self.env._("Too many documents are selected for one download. Select fewer and download in parts.")
            )
        self._zip_entries()
        return path

    def _zip_entries(self):
        """The entries of the ZIP of these documents, flat, in the order of their ids.

        Refuses what cannot be a ZIP: a file whose blob is missing (the message names them, a ZIP
        without them would look complete), or more bytes than the system parameter allows.
        """
        names = export_names((document.id, document.name) for document in self)
        entries = self._zip_files(names)
        self._check_zip_size(sum(entry.size for entry in entries))
        return entries

    def _zip_files(self, names):
        """The entries of these documents, each under its name in the archive (``{id: name}``).

        Which blobs are there is read from their directories, one listing for each (the filestore
        is a network file system on our server: a ``stat`` for each of 300,000 files took 90
        seconds, the proxy gives up after that). The size is the one that was measured when the
        file was stored; the blob is named by its checksum, so it does not change. A file that is
        not as big as that breaks the stream (see ``zip_chunks``), it cannot look complete.
        """
        entries, missing = [], []
        listings = {}
        for document in self.sorted("id"):
            checksum = document.checksum
            if not CHECKSUM_REGEX.fullmatch(checksum or ""):
                raise ValueError("A checksum is 64 lowercase hexadecimal characters.")
            if checksum[:2] not in listings:
                directory = os.path.dirname(self._blob_path(checksum))
                listings[checksum[:2]] = (directory, _files_in(directory))
            directory, present = listings[checksum[:2]]
            if checksum not in present:
                missing.append(document.name)
                continue
            path = os.path.join(directory, checksum)
            size = int(document.size) or os.stat(path).st_size
            entries.append(ZipEntry(names[document.id], path, size, document.write_date))
        if missing:
            raise UserError(
                self.env._(
                    "The file of these documents is missing: %(names)s",
                    names=", ".join(missing[:MISSING_NAMES_SHOWN]) + (" …" if len(missing) > MISSING_NAMES_SHOWN else ""),
                )
            )
        return entries

    @api.model
    def _check_zip_size(self, total):
        """Refuse more bytes than one ZIP may hold (the system parameter)."""
        limit = self._zip_max_size()
        if total > limit:
            raise UserError(
                self.env._(
                    "The files are %(size).1f GB together, more than the %(limit).1f GB that one ZIP may hold. "
                    "Download them in parts.",
                    size=total / 1024**3,
                    limit=limit / 1024**3,
                )
            )

    @api.model
    def _zip_max_size(self):
        value = self.env["ir.config_parameter"].sudo().get_param(ZIP_MAX_SIZE_PARAMETER, DEFAULT_ZIP_MAX_SIZE)
        try:
            return int(value)
        except ValueError:
            return DEFAULT_ZIP_MAX_SIZE

    def action_share(self):
        """The share dialog of one file: the list has the button for the ticked rows too."""
        self._check_one_selected()
        return super().action_share()

    def get_edit_session(self):
        """What the picture editor needs to go on with a picture that it stored before.

        The state of the editor and the picture that it was made on. The picture is handed out
        only if the user may read it (their rules, and not archived): the one who may read the
        edited picture need not see where it came from. The editor then starts with the flat
        picture.

        :return: ``{"state": dict, "source": {"id", "name", "mimetype", "checksum", "size"}}``,
            or ``{}`` if there is nothing to go on with
        """
        self.ensure_one()
        self.check_access("read")
        stored = self.sudo()
        if not stored.edit_state or not stored.edit_source_id:
            return {}
        source = self.search([("id", "=", stored.edit_source_id.id)])
        if not source:
            return {}
        return {
            "state": stored.edit_state,
            "source": {
                "id": source.id,
                "name": source.name,
                "mimetype": source.mimetype,
                "checksum": source.checksum,
                "size": source.size,
            },
        }

    def _check_one_selected(self):
        # The buttons in the head of the list act on every ticked row; these act on one.
        if len(self) != 1:
            raise UserError(self.env._("Select exactly one document."))

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
        the same content and stays: it is never replaced, a reader that has it open or is about
        to open it must not find a gap (``os.replace`` over a name can fail a reader on a
        network share).

        Two transactions that publish the same checksum at once take turns: the first places the
        blob, the second finds it after the lock and only removes its own temporary file.
        """
        path = self._blob_path(checksum)
        if os.path.exists(path):
            _remove_file(tmp_path)
            return
        # One publisher per checksum, until this transaction ends (a blob placed by a
        # transaction that is rolled back stays on the disk, the cleaner sees to it). Look again
        # after the lock: the transaction we waited for may have placed it. The two-key form is
        # a key space of its own, the core's one-key locks (``mail_thread``) cannot clash.
        self.env.cr.execute(
            SQL("SELECT pg_advisory_xact_lock(hashtext(%s), hashtext(%s))", BLOB_LOCK_NAME, checksum)
        )
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

        A blob counts as used if a *document* has its checksum, or a text row has it as its
        recognized PDF (``used`` below). Whoever lets another model keep blobs of this storage
        must add that model's checksums there and lock its table with the others, or the
        cleaner deletes them. The tables are locked in a fixed order (documents, then texts).
        """
        cr = self.env.cr
        if not os.path.isdir(self._checklist_dir()):
            return 0, 0
        # Continue in a new transaction: the LOCK must be the first statement of it, otherwise
        # its snapshot (REPEATABLE READ) may not hold what concurrent transactions just wrote.
        cr.commit()
        timeout = self.env.context.get("int_filemanager_lock_timeout", GC_LOCK_TIMEOUT)
        cr.execute(SQL("SET LOCAL lock_timeout TO %s", timeout))
        Text = self.env["int.filemanager.text"]
        try:
            for table in (self._table, Text._table):
                cr.execute(SQL("LOCK %s IN SHARE MODE", SQL.identifier(table)))
        except psycopg2.errors.LockNotAvailable:
            cr.rollback()  # a writer is busy; the next run tries again
            return 0, 0
        entries = list(itertools.islice(self._checklist_entries(), GC_BATCH))
        names = [name for name, _path in entries]
        used = {
            checksum
            for [checksum] in self.sudo()
            .with_context(active_test=False)
            ._read_group([("checksum", "in", names)], ["checksum"])
        } | Text._used_ocr_checksums(names)
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
    def _create_from_stream(self, stream, name, folder, mimetype=None, check=None, **values):
        """Store a file and create its document: the one way a document comes to be.

        Runs as superuser (the users cannot create documents), so the caller has to check
        first that the user may write into ``folder``.

        :param stream: file-like object with ``read(size)``
        :param name: name of the document, also used to guess the type
        :param folder: ``int.filemanager.folder`` record
        :param mimetype: type given by the client, if any
        :param check: called with the result of ``_store_stream`` (the size, the checksum, the
            type) after the file is measured and before the document is made and the blob is
            kept. It refuses the file by raising. Then only the temporary file is there, and it is
            removed: a blob that was kept cannot be taken back by a rollback.
        :param values: more field values, e.g. ``tag_ids``
        :return: the document, with the environment of the caller
        """
        name = self._clean_name(name)
        stored = self._store_stream(stream, name, mimetype)
        try:
            if check:
                check(stored)
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

    @api.model
    def _thumbnail_domain(self):
        """The PDFs that wait for their picture (one that failed is not tried again)."""
        return Domain([("mimetype", "=", PDF), ("thumbnail_state", "=", False)])

    @api.model
    def _cron_thumbnails(self, limit=THUMBNAIL_BATCH):
        """Draw the first page of the PDFs that have no picture yet, one blob at a time.

        Documents with the same checksum share one drawing. Every blob is committed
        (``_commit_progress``), so a stop loses no more than the file that was being drawn; when
        the time is up with PDFs left, the report of what remains makes Odoo call it again.

        :param limit: the documents looked at in one call
        """
        assert self.env.context.get("cron_id") == self.env.ref(THUMBNAIL_CRON_XMLID).id, (
            "Meant for cron usage only"
        )
        if not importlib.util.find_spec("pypdfium2"):
            _logger.warning("pypdfium2 is not installed: the pictures of PDFs are not made.")
            return
        cron = self.env["ir.cron"]
        domain = self._thumbnail_domain()
        documents = self.with_context(active_test=False).search(domain, limit=limit)
        for checksum, same in documents.grouped("checksum").items():
            # Another transaction holds a row (the cleaner, a rename): the next call gets it.
            same = same.try_lock_for_update(allow_referencing=True).filtered_domain(domain)
            if same:
                same._make_thumbnail(checksum)
            if not cron._commit_progress(len(same)):
                break
        cron._commit_progress(0, remaining=self.with_context(active_test=False).search_count(domain))

    def _make_thumbnail(self, checksum):
        """Draw the blob ``checksum`` and give the picture to these documents, or mark them failed."""
        picture = self._draw_first_page(checksum)
        values = {"thumbnail_state": "failed"}
        if picture:
            values = {"thumbnail": base64.b64encode(picture), "thumbnail_state": "done"}
        # The users cannot write these fields (see ``write``); the job runs as superuser anyway.
        self.sudo().with_context(tracking_disable=True).write(values)

    @api.model
    def _draw_first_page(self, checksum):
        """The first page of the PDF blob as a JPEG, or ``None`` if it cannot be drawn.

        The program that cannot be started is no fault of the file: that error goes up (Odoo stops
        a scheduled action that fails again and again and tells the administrator).
        """
        command = [
            sys.executable,
            "-I",
            PDF_THUMBNAIL,
            self._blob_path(checksum),
            str(THUMBNAIL_SIZE),
            str(THUMBNAIL_MEMORY_MIB),
        ]
        try:
            done = subprocess.run(  # noqa: S603 (own script, own interpreter, no shell)
                command, capture_output=True, check=False, timeout=THUMBNAIL_SECONDS
            )
        except subprocess.TimeoutExpired:
            _logger.warning("No picture of %s: the first page took more than %s s.", checksum, THUMBNAIL_SECONDS)
            return None
        if done.returncode or not done.stdout:
            reason = done.stderr.decode(errors="replace").strip().splitlines()[-1:] or ["no answer"]
            _logger.warning("No picture of %s: %s", checksum, reason[0][:200])
            return None
        return done.stdout

    def _to_ocr_http_stream(self):
        """The recognized PDF of the file as a stream, for the viewer.

        ``ir.binary._record_to_stream`` calls it for the field ``ocr_content``: the way in is the
        document, so the rights and rules of the document decide, as for ``content``. The
        checksum of the PDF is the ETag.
        """
        self.ensure_one()
        checksum = self.ocr_checksum
        if not checksum:
            raise MissingError(self.env._("The text recognition made no PDF of this document."))
        path = self._blob_path(checksum)
        try:
            stat = os.stat(path)
        except FileNotFoundError:
            raise MissingError(self.env._("The recognized PDF of this document is missing.")) from None
        return Stream(
            type="path",
            path=path,
            mimetype="application/pdf",
            download_name=self.name,
            etag=checksum,
            last_modified=stat.st_mtime,
            size=stat.st_size,
        )

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
