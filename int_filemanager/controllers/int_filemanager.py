import errno

from odoo import http
from odoo.exceptions import AccessError, UserError
from odoo.http import request

MAX_UPLOAD_SIZE_PARAMETER = "int_filemanager.max_upload_size"
DEFAULT_MAX_UPLOAD_SIZE = 20 * 1024**3


def max_upload_size(controller):
    """The limit of one upload request in bytes, from the system parameter.

    The core's own limit (128 MiB) stops every upload route that does not set its own.
    Odoo calls this after the sign-in, so the database is at hand.
    """
    value = (
        request.env["ir.config_parameter"]
        .sudo()
        .get_param(MAX_UPLOAD_SIZE_PARAMETER, DEFAULT_MAX_UPLOAD_SIZE)
    )
    try:
        return int(value)
    except ValueError:
        return DEFAULT_MAX_UPLOAD_SIZE


class _NotFound(UserError):
    """The folder or the record of an upload is not there (answered with 404)."""


class IntFilemanager(http.Controller):
    @http.route(
        "/int_filemanager/upload",
        type="http",
        auth="user",
        methods=["POST"],
        max_content_length=max_upload_size,
    )
    def upload(self, folder_id=None, link_model=None, link_id=None, **kwargs):
        """Store one file as a document of the folder, or of the record it is uploaded at.

        With ``link_model`` and ``link_id`` the file goes to the folder that the settings name
        for the model of the record and is linked to the record; whoever may change the record
        may do that, the folders are not looked at. Without them the file goes to ``folder_id``.

        The answer is JSON; an error carries ``{"error": {"message": ...}}`` and a status that
        Odoo's ``file_upload`` service shows to the user.
        """
        files = request.httprequest.files.getlist("ufile")
        if len(files) != 1:
            return self._error(400, request.env._("Send exactly one file per request."))
        try:
            if link_model:
                record = self._record_to_link(link_model, link_id)
                folder = self._record_folder(record)
            else:
                record = None
                folder = self._folder_to_write(folder_id)
            upload = files[0]
            document = request.env["int.filemanager.document"]._create_from_stream(
                upload.stream, upload.filename, folder, upload.mimetype
            )
            if record:
                # The storage and the link run as superuser: the right to change the record was
                # checked, the uploader need not see the folder.
                request.env["int.filemanager.link"].sudo().create(
                    {
                        "document_id": document.id,
                        "res_model_id": request.env["ir.model"]._get_id(record._name),
                        "res_id": record.id,
                    }
                )
        except _NotFound as error:
            return self._error(404, error.args[0])
        except AccessError as error:
            return self._error(403, error.args[0])
        except UserError as error:
            return self._error(400, error.args[0])
        except OSError as error:
            if error.errno != errno.ENOSPC:
                raise
            return self._error(507, request.env._("There is no space left to store the file."))
        return request.make_json_response(
            {
                "id": document.id,
                "name": document.name,
                "size": document.size,
                "mimetype": document.mimetype,
            }
        )

    def _folder_to_write(self, folder_id):
        """The folder, if the user may write into it (the storage runs as superuser)."""
        try:
            folder = request.env["int.filemanager.folder"].search([("id", "=", int(folder_id))])
        except (TypeError, ValueError):
            folder = None
        if not folder:
            raise _NotFound(request.env._("This folder does not exist."))
        folder.check_access("write")
        return folder

    def _record_to_link(self, link_model, link_id):
        """The record that the file is uploaded at, if the user may change it."""
        env = request.env
        if link_model not in env["int.filemanager.link"]._linkable_models():
            raise UserError(env._("Documents cannot be linked to this kind of record."))
        try:
            record = env[link_model].browse(int(link_id)).exists()
        except (TypeError, ValueError):
            record = None
        if not record:
            raise _NotFound(env._("This record does not exist."))
        record.check_access("write")
        return record

    def _record_folder(self, record):
        folder = request.env["int.filemanager.model.folder"]._folder_for_record(record)
        if not folder:
            raise UserError(
                request.env._(
                    "No folder is set for the files of this kind of record. Ask the administrator "
                    "of the filemanager (menu Upload folders)."
                )
            )
        return folder

    def _error(self, status, message):
        return request.make_json_response({"error": {"message": message}}, status=status)
