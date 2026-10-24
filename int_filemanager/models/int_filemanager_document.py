import os
import re

from odoo import api, fields, models
from odoo.exceptions import MissingError, UserError
from odoo.fields import Domain
from odoo.http import Stream
from odoo.tools import SQL
from odoo.tools.mimetypes import get_extension

from ..tools.clash import clash_summary, clashing_names
from ..tools.zip_stream import ZipEntry, export_names
from .int_filemanager_text_page import folded

BLOB_FOLDER = "int_filemanager"
# The most bytes of the files in one ZIP. The server stops a request after 30 minutes in our setup
# (limit_time_real), and a slow line keeps it that long: see docs/int_filemanager/erkenntnisse.md.
ZIP_MAX_SIZE_PARAMETER = "int_filemanager.zip_max_size"
DEFAULT_ZIP_MAX_SIZE = 10 * 1024**3
# The ids of a ZIP go into the address, and the proxy takes 8 KB of the request line.
ZIP_PATH_MAX_LENGTH = 7000
ZIP_PATH = "/int_filemanager/zip/"
# Names of missing files shown in a message.
MISSING_NAMES_SHOWN = 5
CHECKSUM_REGEX = re.compile(r"[0-9a-f]{64}")
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
    "preview_checksum",
    "preview_state",
    "share_id",
    "edit_source_id",
    "edit_state",
)
# The most bytes of the state that the picture editor stores with a picture (the marks, the
# filters, the crop, and the small pictures that were put into the editor).
EDIT_STATE_MAX_SIZE = 8 * 1024**2
PDF = "application/pdf"
THUMBNAIL_CRON_XMLID = "int_filemanager.int_filemanager_thumbnail_cron"
TEXT_CRON_XMLID = "int_filemanager.int_filemanager_text_cron"
# The office files that LibreOffice turns into a PDF for the viewer (``_cron_previews``), with the
# ending it needs to know the format (a blob has none).
PREVIEW_CRON_XMLID = "int_filemanager.int_filemanager_preview_cron"
PREVIEW_EXTENSIONS = {
    "application/msword": "doc",
    "application/rtf": "rtf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/vnd.oasis.opendocument.text": "odt",
    "application/vnd.ms-excel": "xls",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
    "application/vnd.oasis.opendocument.spreadsheet": "ods",
    "application/vnd.ms-powerpoint": "ppt",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": "pptx",
    "application/vnd.oasis.opendocument.presentation": "odp",
}


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

    def _compute_content(self):
        self.content = False

    def _inverse_content(self):
        raise UserError(self.env._("The file of a document is set by the upload only."))

    def _compute_ocr_content(self):
        self.ocr_content = False

    @api.depends("checksum", "preview_checksum")
    def _compute_ocr_checksum(self):
        # The text rows are for the administrators; the checksum of the PDF is no secret to
        # whoever may read the document it belongs to. An office file has the preview instead.
        Text = self.env["int.filemanager.text"].sudo()
        found = {
            row.checksum: row.ocr_checksum
            for row in Text.search_fetch(
                [("checksum", "in", self.mapped("checksum")), ("ocr_checksum", "!=", False)],
                ["checksum", "ocr_checksum"],
            )
        }
        for document in self:
            document.ocr_checksum = found.get(document.checksum) or document.preview_checksum

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
        old_previews = set()
        if old_checksums - {vals.get("checksum")}:
            # Another file: its preview is not the preview of the new one.
            old_previews = set(self.mapped("preview_checksum"))
            vals = {
                **vals,
                "preview_checksum": False,
                "preview_state": False,
                "thumbnail": False,
                "thumbnail_state": False,
            }
        # The name that the tracking keeps of a folder is the plain one, whatever the context.
        plain = self.with_context(hierarchical_naming=False)
        result = super(IntFilemanagerDocument, plain).write(vals)
        if old_checksums:
            # Another file: the blob it had may be free now (the cleaner looks).
            for checksum in old_checksums - {vals["checksum"]} | old_previews - {False}:
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
        checksums = set(self.mapped("checksum")) | set(self.mapped("preview_checksum")) - {False}
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

    def _to_ocr_http_stream(self):
        """The PDF of the file that is not the file as a stream, for the viewer.

        That is the recognized PDF of a scan, or the preview of an office file.
        ``ir.binary._record_to_stream`` calls it for the field ``ocr_content``: the way in is the
        document, so the rights and rules of the document decide, as for ``content``. The
        checksum of the PDF is the ETag.
        """
        self.ensure_one()
        checksum = self.ocr_checksum
        if not checksum:
            raise MissingError(self.env._("There is no PDF version of this document."))
        path = self._blob_path(checksum)
        try:
            stat = os.stat(path)
        except FileNotFoundError:
            raise MissingError(self.env._("The PDF version of this document is missing.")) from None
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
