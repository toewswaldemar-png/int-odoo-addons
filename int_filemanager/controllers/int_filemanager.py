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


class IntFilemanager(http.Controller):
    @http.route(
        "/int_filemanager/upload",
        type="http",
        auth="user",
        methods=["POST"],
        max_content_length=max_upload_size,
    )
    def upload(self, folder_id=None, **kwargs):
        """Store one file as a document of the folder.

        The answer is JSON; an error carries ``{"error": {"message": ...}}`` and a status that
        Odoo's ``file_upload`` service shows to the user.
        """
        files = request.httprequest.files.getlist("ufile")
        if len(files) != 1:
            return self._error(400, request.env._("Send exactly one file per request."))
        try:
            folder = request.env["int.filemanager.folder"].search(
                [("id", "=", int(folder_id))]
            )
        except (TypeError, ValueError):
            folder = None
        except AccessError as error:
            return self._error(403, error.args[0])
        if not folder:
            return self._error(404, request.env._("This folder does not exist."))
        try:
            # The storage runs as superuser: the right to write here is checked first.
            folder.check_access("write")
            upload = files[0]
            document = request.env["int.filemanager.document"]._create_from_stream(
                upload.stream, upload.filename, folder, upload.mimetype
            )
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

    def _error(self, status, message):
        return request.make_json_response({"error": {"message": message}}, status=status)
