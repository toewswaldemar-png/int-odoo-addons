import os
import re

from odoo import api, fields, models
from odoo.exceptions import MissingError, UserError
from odoo.http import Stream
from odoo.tools.mimetypes import get_extension

from ..tools.zip_stream import ZipEntry, export_names
from .int_filemanager_folder import CASCADE_KEY

BLOB_FOLDER = "int_filemanager"
# The ids of a ZIP go into the address, and the proxy takes 8 KB of the request line.
ZIP_PATH_MAX_LENGTH = 7000
DOCUMENTS_ZIP_PATH = "/int_filemanager/zip/"
# Names of missing files shown in a message.
MISSING_NAMES_SHOWN = 5
CHECKSUM_REGEX = re.compile(r"[0-9a-f]{64}")
# Set by the storage only (see ``write``), like the core does for ``ir.attachment``. The picture
# of a PDF and its state are made by the scheduled action alone.
STORAGE_FIELDS = (
    "checksum",
    "size",
    "mimetype",
    "thumbnail",
    "thumbnail_state",
    "preview_checksum",
    "preview_state",
)
PDF = "application/pdf"
THUMBNAIL_CRON_XMLID = "int_filemanager.int_filemanager_thumbnail_cron"
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
    _inherit = ["mail.thread", "mail.activity.mixin", "int.filemanager.named"]
    _order = "name"

    name = fields.Char(tracking=True)
    folder_id = fields.Many2one(
        "int.filemanager.folder",
        required=True,
        index=True,
        ondelete="restrict",
        tracking=True,
    )
    checksum = fields.Char(readonly=True, required=True, index=True)
    # Float, not Integer: an int4 column overflows above 2 GiB. A float8 holds every whole number
    # up to 2**53 (8 PiB) exactly, so sums of sizes are exact as well.
    size = fields.Float(readonly=True)
    mimetype = fields.Char(readonly=True)
    active = fields.Boolean(default=True, tracking=True)
    tag_ids = fields.Many2many(
        "int.filemanager.tag",
        "int_filemanager_document_tag_rel",
        "document_id",
        "tag_id",
        string="Tags",
        tracking=True,
    )
    company_id = fields.Many2one(
        related="folder_id.company_id", store=True, index=True
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
    # The same for the PDF that the viewer shows instead of the file: the preview of an office
    # file, or a PDF that another module made of it (``int_filemanager_ocr``: a scan with a text
    # layer). Served by ``_to_viewer_pdf_http_stream`` for the viewer only: the download is the
    # original.
    viewer_pdf_content = fields.Binary(
        string="PDF for the viewer (file)",
        compute="_compute_viewer_pdf_content",
        inverse="_inverse_content",
        copy=False,
        exportable=False,
    )
    # The checksum of that PDF, empty if there is none; the viewer asks for it to choose the
    # address, and it changes the address of the file when the PDF changes.
    viewer_pdf_checksum = fields.Char(
        string="PDF for the viewer",
        compute="_compute_viewer_pdf_checksum",
        copy=False,
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

    def _compute_content(self):
        self.content = False

    def _inverse_content(self):
        raise UserError(self.env._("The file of a document is set by the upload only."))

    def _compute_viewer_pdf_content(self):
        self.viewer_pdf_content = False

    @api.depends("preview_checksum")
    def _compute_viewer_pdf_checksum(self):
        # The PDF that the viewer shows instead of the file: the preview of an office file. A
        # module that recognizes the text of scans (``int_filemanager_ocr``) adds the PDF it made.
        for document in self:
            document.viewer_pdf_checksum = document.preview_checksum

    @api.depends("name")
    def _compute_extension(self):
        for document in self:
            document.extension = get_extension(document.name or "").lstrip(".")

    def write(self, vals):
        # ``readonly`` holds in the interface only: through RPC a user could point a document
        # at another blob or give it another type. Like ``ir.attachment``, drop such values;
        # the storage runs as superuser. Creating is closed by the missing access right.
        if not self.env.su:
            vals = {key: value for key, value in vals.items() if key not in STORAGE_FIELDS}
        if "folder_id" in vals:
            self._check_move(vals["folder_id"])
        if vals.get("active") and not (self.env.su and self.env.context.get(CASCADE_KEY)):
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

    def _filtered_folder_access(self, operation="read"):
        """The documents whose folder the user may ``operation``.

        A document is seen by the rules of its folder, so this is ``_filtered_access`` as far as
        the folders go. A module that shows a document by another way (a record it is linked to)
        does not change the answer: it is what the folders show, for whoever may not pass on a
        document that they see only by that other way. As ``ir.attachment`` asks the record it
        belongs to, here the folder is asked.
        """
        # The ids as superuser (the user may not read the document), the check as the user.
        folders = self.env["int.filemanager.folder"].browse(self.sudo().folder_id.ids)
        allowed = set(folders._filtered_access(operation).ids)
        return self.filtered(lambda document: document.sudo().folder_id.id in allowed)

    def _documents_referenced(self):
        """Of these documents, those that something else points to; none in the core.

        A module that keeps a reference to a document (a link to a record, say) returns them with
        ``super()``, so that whoever may take a file away (a guest of a share, for its own
        uploads) leaves them alone.
        """
        return self.browse()

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
        taken = moved._names_taken("folder_id", folder)
        if taken:
            raise UserError(
                self.env._("These names are taken in %(folder)s: %(names)s", folder=folder.name, names=taken)
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
        path = DOCUMENTS_ZIP_PATH + ",".join(str(document_id) for document_id in self.ids)
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
        """The most bytes of the files in one ZIP (the setting ``zip_max_gb``).

        The server stops a request after 30 minutes in our setup (``limit_time_real``), and a slow
        line keeps it that long: see docs/int_filemanager/erkenntnisse.md.
        """
        return self.env["int.filemanager.cron"]._setting("zip_max_gb") * 1024**3

    @api.model
    def _upload_max_size(self):
        """The most bytes of one upload request (the setting ``upload_max_gb``)."""
        return self.env["int.filemanager.cron"]._setting("upload_max_gb") * 1024**3

    def _check_one_selected(self):
        # The buttons in the head of the list act on every ticked row; these act on one.
        if len(self) != 1:
            raise UserError(self.env._("Select exactly one document."))

    def _to_viewer_pdf_http_stream(self):
        """The PDF of the file that is not the file as a stream, for the viewer.

        That is the preview of an office file, or the PDF that another module made of the file.
        ``ir.binary._record_to_stream`` calls it for the field ``viewer_pdf_content``: the way in
        is the document, so the rights and rules of the document decide, as for ``content``. The
        checksum of the PDF is the ETag.
        """
        self.ensure_one()
        checksum = self.viewer_pdf_checksum
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
