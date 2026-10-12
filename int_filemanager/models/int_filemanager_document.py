import contextlib
import hashlib
import os
import re
import uuid

from odoo import api, fields, models
from odoo.exceptions import MissingError, UserError
from odoo.http import Stream

BLOB_FOLDER = "int_filemanager"
UPLOAD_FOLDER = ".upload"
CHECKSUM_REGEX = re.compile(r"[0-9a-f]{64}")
CHUNK_SIZE = 1024 * 1024
# The head of a file is enough for ``guess_mimetype`` (it reads no more than this).
HEAD_SIZE = 2048
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
        return super().write(vals)

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
        upload_dir = os.path.join(
            self.env["ir.attachment"]._filestore(), BLOB_FOLDER, UPLOAD_FOLDER
        )
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
        # become text/plain (office formats excepted), for every user.
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
        os.makedirs(os.path.dirname(path), exist_ok=True)
        os.replace(tmp_path, path)

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
        stored = self._store_stream(stream, name, mimetype)
        try:
            document = (
                self.sudo()
                .create(
                    {
                        **values,
                        "name": name,
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
            self._publish_blob(stored["tmp_path"], stored["checksum"])
        finally:
            # Nothing is left of a failed attempt (e.g. a name that is taken).
            _remove_file(stored["tmp_path"])
        return document

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
