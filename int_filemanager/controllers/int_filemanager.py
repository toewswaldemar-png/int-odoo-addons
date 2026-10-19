import errno
import logging
import time

from werkzeug.exceptions import BadRequest

from odoo import fields, http
from odoo.exceptions import AccessError, UserError
from odoo.http import Response, request

from ..tools.zip_stream import zip_chunks, zip_length

_logger = logging.getLogger(__name__)

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


def logged_chunks(entries, tag):
    """The bytes of the ZIP, with a line in the log of how the stream ended.

    The answer is sent after Odoo has closed its cursor: nothing here may touch the database or
    the request, only the plain entries.
    """
    started = time.monotonic()
    try:
        yield from zip_chunks(entries)
    except GeneratorExit:
        _logger.warning("ZIP %s: the client went away after %.1f s", tag, time.monotonic() - started)
        raise
    except Exception:
        _logger.exception("ZIP %s: the stream broke after %.1f s", tag, time.monotonic() - started)
        raise
    _logger.info("ZIP %s: sent in %.1f s", tag, time.monotonic() - started)


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
                    "of the filemanager to choose an upload folder."
                )
            )
        return folder

    def _error(self, status, message):
        return request.make_json_response({"error": {"message": message}}, status=status)

    @http.route("/int_filemanager/zip/<string:ids>", type="http", auth="user", methods=["GET"])
    def zip(self, ids):
        """The files of these documents as one ZIP, flat, sent as it is written.

        The address comes from ``action_download``, but nothing there counts: the companies of the
        list (the cookie of the web client) are checked against the user, and every document is
        read as the user, now. A document that is missing or that the user may not read refuses
        the whole request, no ZIP without it is made. The ZIP is stored, so its length is known:
        a stream that breaks off is an error to the browser, not a file that looks complete.
        """
        try:
            document_ids = {int(document_id) for document_id in ids.split(",")}
            companies = [
                int(company_id)
                for company_id in request.cookies.get("cids", str(request.env.user.company_id.id)).split("-")
            ]
        except ValueError:
            raise BadRequest() from None
        documents = request.env["int.filemanager.document"].with_context(allowed_company_ids=companies)
        documents = documents.browse(sorted(document_ids))
        if len(documents.exists()) != len(document_ids):
            raise request.not_found()
        documents.check_access("read")
        try:
            entries = documents._zip_entries()
        except UserError as error:
            return request.make_response(
                error.args[0], headers=[("Content-Type", "text/plain; charset=utf-8")], status=409
            )
        name = f"documents-{fields.Date.context_today(documents)}.zip"
        headers = [
            ("Content-Type", "application/zip"),
            ("Content-Length", str(zip_length(entries))),
            ("Content-Disposition", http.content_disposition(name)),
            ("X-Content-Type-Options", "nosniff"),
        ]
        tag = f"{name} of {len(entries)} files for user {request.env.uid}"
        return Response(logged_chunks(entries, tag), headers=headers, direct_passthrough=True)
