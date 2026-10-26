"""The upload of the browser: one file per request, as the ``file_upload`` service of the web client sends it."""

import errno
import unicodedata

from odoo import http
from odoo.exceptions import AccessError, UserError
from odoo.http import request

MAX_UPLOAD_SIZE_PARAMETER = "int_blob.max_upload_size"
DEFAULT_MAX_UPLOAD_SIZE = 20 * 1024**3
NAME_MAX_LENGTH = 255


def max_upload_size(controller):
    """The limit of one upload request in bytes, from the system parameter.

    The core's own limit (128 MiB) stops every upload route that does not set its own. Odoo calls
    this after the sign-in, so the database is at hand.
    """
    value = request.env["ir.config_parameter"].sudo().get_param(MAX_UPLOAD_SIZE_PARAMETER, DEFAULT_MAX_UPLOAD_SIZE)
    try:
        return int(value)
    except ValueError:
        return DEFAULT_MAX_UPLOAD_SIZE


def clean_name(name):
    """The name as the browser gives it, made fit for an attachment: the last part, composed, no control characters."""
    name = (name or "").replace("\\", "/").rsplit("/", 1)[-1]
    name = unicodedata.normalize("NFC", name)
    name = "".join(char for char in name if unicodedata.category(char) != "Cc").strip()
    if name in ("", ".", ".."):
        raise UserError(request.env._("A file needs a name."))
    return name[:NAME_MAX_LENGTH]


class IntBlob(http.Controller):
    @http.route("/int_blob/upload", type="http", auth="user", methods=["POST"], max_content_length=max_upload_size)
    def upload(self, model=None, field=None, **kwargs):
        """Store one file as an attachment of the record ``model`` and ``id``, or as the value of its binary ``field``.

        The names ``model``, ``id`` and ``ufile`` are those that the file input of the web client
        sends. Whoever may write the record may do this. The answer is JSON; an error carries
        ``{"error": {"message": ...}}`` and a status that the ``file_upload`` service shows to the user.
        """
        files = request.httprequest.files.getlist("ufile")
        if len(files) != 1:
            return self._error(400, request.env._("Send exactly one file per request."))
        try:
            res_id = int(kwargs.get("id"))
        except (TypeError, ValueError):
            return self._error(400, request.env._("The record of the file is missing."))
        upload = files[0]
        try:
            attachment = request.env["ir.attachment"]._create_from_stream(
                upload.stream, clean_name(upload.filename), model, res_id, field or False, upload.mimetype
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
                "id": attachment.id,
                "name": attachment.name,
                "size": attachment.int_blob_size,
                "mimetype": attachment.mimetype,
            }
        )

    def _error(self, status, message):
        return request.make_json_response({"error": {"message": message}}, status=status)
