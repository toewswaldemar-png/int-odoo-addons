"""The attachments, extended by the upload from a stream: a file is written block by block.

The core takes the whole content of a file in memory (``create`` with ``raw``). Here the file is
read from a stream, measured while it is written to a temporary file next to the filestore and
then placed where the core keeps it (``<sha1[:2]>/<sha1>``), so the core reads, serves, shares
and cleans it like any other attachment.

The model gets one field and three methods; the steps are plain functions of this module.
"""

import contextlib
import hashlib
import os
import re
import time
import uuid

from odoo import api, fields, models
from odoo.exceptions import UserError

CHUNK_SIZE = 1024 * 1024
# The head of a file is enough for ``_check_contents`` (it reads no more than this).
HEAD_SIZE = 2048
# ``ir_attachment.file_size`` is a 32-bit column (the core): it takes this much and no more.
# A larger file is recorded here as this, and by its real size in ``int_blob_size``.
FILE_SIZE_MAX = 2**31 - 1
# Next to the ``checklist`` folder of the core, which its cleaner walks; this one it leaves alone.
UPLOAD_FOLDER = "int_blob_upload"
UPLOAD_AGE_PARAMETER = "int_blob.upload_max_age_hours"
# The folder that a file may be read in from (an absolute path); without it nothing is read in.
IMPORT_ROOT_PARAMETER = "int_blob.import_root"
DEFAULT_UPLOAD_MAX_AGE_HOURS = 24
CHECKSUM_REGEX = re.compile(r"[0-9a-f]{40}")
STORED_FIELDS = ["store_fname", "checksum", "file_size"]


class Bigint(fields.Integer):
    """An integer in a 64-bit column.

    The column is the module's own: Odoo drops it when the module is uninstalled. A change to
    the type of a column of the core is not safe: the core converts it back as soon as the
    module is not loaded, and that fails for a stored value over 2 GiB.
    """

    _column_type = ("int8", "int8")


def remove_file(path):
    with contextlib.suppress(FileNotFoundError):
        os.unlink(path)


def same_content(first, second):
    """Whether two files hold the same bytes (read block by block)."""
    if os.path.getsize(first) != os.path.getsize(second):
        return False
    with open(first, "rb") as one, open(second, "rb") as other:
        while chunk := one.read(CHUNK_SIZE):
            if chunk != other.read(len(chunk)):
                return False
    return True


def blob_fname(checksum):
    """The name in the filestore of the file with this SHA-1: the core's ``<sha[:2]>/<sha>``."""
    if not CHECKSUM_REGEX.fullmatch(checksum or ""):
        raise ValueError("A checksum is 40 lowercase hexadecimal characters.")
    return f"{checksum[:2]}/{checksum}"


def import_file_path(attachments, path):
    """The real path of a file below the root folder for reading in, or an error.

    The root is a system parameter, written by the administrators only. A path may be absolute or
    relative to the root; a link that leads out of the root is found by comparing real paths.
    """
    value = attachments.env["ir.config_parameter"].sudo().get_param(IMPORT_ROOT_PARAMETER)
    if not value or not os.path.isabs(value):
        raise UserError(attachments.env._("Set the root folder for reading in files first."))
    root = os.path.realpath(value)
    if not os.path.isdir(root):
        raise UserError(attachments.env._("The root folder %(root)s does not exist.", root=root))
    candidate = path if os.path.isabs(path) else os.path.join(root, path)
    real = os.path.realpath(candidate)
    if not real.startswith(root + os.sep) or not os.path.isfile(real):
        raise UserError(attachments.env._("%(path)s is not a file below the root folder.", path=path))
    return real


def upload_dir(attachments):
    return attachments._full_path(UPLOAD_FOLDER)


def store_stream(attachments, stream, name, mimetype=None):
    """Write ``stream`` block by block to a temporary file and measure it.

    Nothing is held in memory but one block. The temporary file is removed if this fails or the
    transaction is rolled back.

    :return: ``{"tmp_path", "checksum", "size", "mimetype"}``
    """
    folder = upload_dir(attachments)
    os.makedirs(folder, exist_ok=True)
    tmp_path = os.path.join(folder, uuid.uuid4().hex)
    attachments.env.cr.postrollback.add(lambda: remove_file(tmp_path))
    digest = hashlib.sha1()  # noqa: S324 (the name the core gives its files)
    size = 0
    head = b""
    written = False
    try:
        with open(tmp_path, "xb") as out:
            while chunk := stream.read(CHUNK_SIZE):
                size += len(chunk)
                head += chunk[: HEAD_SIZE - len(head)]
                digest.update(chunk)
                out.write(chunk)
        written = True
    finally:
        if not written:
            remove_file(tmp_path)
    # The core's rules for the type: the client's, then the file name, then the head. Only the
    # head is at hand, so a picture is not processed (``image_no_postprocess``).
    if mimetype == "application/octet-stream":
        mimetype = None
    values = attachments.with_context(image_no_postprocess=True)._check_contents(
        {"name": name, "mimetype": mimetype, "raw": head}
    )
    return {"tmp_path": tmp_path, "checksum": digest.hexdigest(), "size": size, "mimetype": values["mimetype"]}


def publish(attachments, tmp_path, fname):
    """Move the temporary file to its place in the filestore.

    Call it after the row is made and flushed: the cleaner of the core (it locks the table and so
    waits for this transaction) then sees the row. A file that is there already has the same
    name, so it is the same file unless the SHA-1 collides: that is checked, and it is never
    replaced, a reader that has it open must not find a gap.

    The file goes on the checklist first: if this transaction is rolled back, the cleaner finds
    a file without a row and deletes it, like the core does for its own files.
    """
    path = attachments._full_path(fname)
    if os.path.exists(path):
        if not same_content(tmp_path, path):
            raise UserError(attachments.env._("The attachment collides with an existing file."))
        remove_file(tmp_path)
        return
    attachments._mark_for_gc(fname)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    os.replace(tmp_path, path)


def set_row(attachment, stored, name, fname):
    """Point the row at the file: the core drops these fields from ``create`` and ``write``.

    The base model's ``write`` is what the core itself calls (``_set_attachment_data``). Access to
    the owner was checked where the row was made. ``file_size`` takes what the 32-bit column
    takes; the real size is in ``int_blob_size``.
    """
    models.Model.write(
        attachment.sudo(),
        {
            "name": name,
            "mimetype": stored["mimetype"],
            "store_fname": fname,
            "checksum": stored["checksum"] if stored["size"] else False,
            "file_size": min(stored["size"], FILE_SIZE_MAX),
            "int_blob_size": stored["size"],
            "index_content": False,
        },
    )
    attachment.flush_recordset([*STORED_FIELDS, "int_blob_size", "mimetype", "name"])


class IrAttachment(models.Model):
    _inherit = "ir.attachment"

    int_blob_size = Bigint(
        "Size in bytes",
        readonly=True,
        copy=False,
        help="The size of a file stored by int_blob, whatever it is; 0 for any other attachment "
        "(its size is in File Size). File Size takes 2 GiB at most.",
    )

    @api.model
    def _create_from_stream(self, stream, name, res_model, res_id, res_field=False, mimetype=None, check=None):
        """Store the content of ``stream`` as an attachment of the record ``(res_model, res_id)``.

        The owner must exist and the caller must be allowed to write it (the same rule as
        ``create``), else the attachment would be seen by its creator only. With ``res_field``
        the file is the value of that binary field of the owner: a file that is there already
        is replaced.

        :param stream: file-like object with ``read(size)``
        :param check: called with the result of ``store_stream`` (the size, the checksum, the
            type) after the file is measured and before anything is kept. It refuses the file
            by raising.
        :return: the attachment, with the environment of the caller
        """
        if self._storage() != "file":
            raise UserError(self.env._("Streaming needs the attachments to be stored in the filestore."))
        owner_model = self.env.get(res_model) if res_model else None
        if owner_model is None or not res_id or not owner_model.sudo().browse(res_id).exists():
            raise UserError(self.env._("A file needs the record that it belongs to."))
        if res_field:
            field = owner_model._fields.get(res_field)
            if not (isinstance(field, fields.Binary) and field.attachment and field.store):
                raise UserError(
                    self.env._(
                        "%(field)s is not a binary field of %(model)s that keeps its file as an attachment.",
                        field=res_field,
                        model=res_model,
                    )
                )
        owner_model.browse(res_id).check_access("write")
        stored = store_stream(self, stream, name, mimetype)
        try:
            if check:
                check(stored)
            # Like the core: a file without content has no file in the store.
            fname = blob_fname(stored["checksum"]) if stored["size"] else False
            existing = self.browse()
            if res_field:
                existing = (
                    self.sudo()
                    .with_context(skip_res_field_check=True)
                    .search(
                        [("res_model", "=", res_model), ("res_id", "=", res_id), ("res_field", "=", res_field)],
                        limit=1,
                    )
                )
            # A caller that catches the error and goes on must not keep a row without a file.
            with self.env.cr.savepoint():
                if existing:
                    attachment = existing.with_env(self.env)
                    attachment.check_access("write")
                    old_fname = attachment.store_fname
                else:
                    attachment = self.create(
                        {"name": name, "res_model": res_model, "res_id": res_id, "res_field": res_field or False}
                    )
                    old_fname = False
                set_row(attachment, stored, name, fname)
                if fname:
                    publish(self, stored["tmp_path"], fname)
                if old_fname and old_fname != fname:
                    self._file_delete(old_fname)
        finally:
            remove_file(stored["tmp_path"])
        return attachment

    @api.model
    def _create_from_path(self, path, res_model, res_id, res_field=False, name=None, mimetype=None, check=None):
        """Store a file of the server as an attachment of the record ``(res_model, res_id)``.

        The file must lie below the root folder (system parameter ``int_blob.import_root``); it is
        read, never changed. The rest is ``_create_from_stream``.

        :param path: absolute, or relative to the root folder
        :param name: the name of the attachment, the file name if empty
        """
        real = import_file_path(self, path)
        with open(real, "rb") as source:
            return self._create_from_stream(
                source, name or os.path.basename(real), res_model, res_id, res_field, mimetype, check
            )

    @api.autovacuum
    def _gc_int_blob_uploads(self):
        """Delete the temporary files of uploads that never ended (a crash leaves them)."""
        folder = upload_dir(self)
        if not os.path.isdir(folder):
            return
        value = self.env["ir.config_parameter"].sudo().get_param(UPLOAD_AGE_PARAMETER)
        try:
            hours = int(value) if value else DEFAULT_UPLOAD_MAX_AGE_HOURS
        except ValueError:
            hours = DEFAULT_UPLOAD_MAX_AGE_HOURS
        oldest_kept = time.time() - hours * 3600
        for entry in os.scandir(folder):
            if entry.is_file() and entry.stat().st_mtime < oldest_kept:
                remove_file(entry.path)
