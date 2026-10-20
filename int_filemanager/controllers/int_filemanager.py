import errno
import json
import logging
import time

from werkzeug.exceptions import BadRequest

from odoo import fields, http
from odoo.exceptions import AccessError, UserError
from odoo.http import Response, request

from ..models.int_filemanager_document import EDIT_STATE_MAX_SIZE
from ..tools.zip_stream import export_name, zip_chunks, zip_length

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
    def upload(
        self,
        folder_id=None,
        link_model=None,
        link_id=None,
        edit_state=None,
        edit_source_id=None,
        **kwargs,
    ):
        """Store one file as a document of the folder, or of the record it is uploaded at.

        With ``link_model`` and ``link_id`` the file goes to the folder that the settings name
        for the model of the record and is linked to the record; whoever may change the record
        may do that, the folders are not looked at. Without them the file goes to ``folder_id``.

        The picture editor sends ``edit_state`` (its state as JSON) and ``edit_source_id`` (the
        picture it started from) with the picture it stored: they are kept with the document so
        that the next edit finds the marks again. A source that the user may not read is
        dropped, the picture is then stored flat.

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
            values = {} if record else self._edit_values(edit_state, edit_source_id)
            document = request.env["int.filemanager.document"]._create_from_stream(
                upload.stream, upload.filename, folder, upload.mimetype, **values
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

    def _edit_values(self, edit_state, edit_source_id):
        """The field values for the state of the picture editor, none if there is nothing to keep."""
        if not edit_state:
            return {}
        if len(edit_state.encode()) > EDIT_STATE_MAX_SIZE:
            raise UserError(request.env._("The state of the editor is too large to be kept."))
        try:
            state = json.loads(edit_state)
            source_id = int(edit_source_id)
        except (TypeError, ValueError):
            raise UserError(request.env._("The state of the editor is not valid.")) from None
        if not isinstance(state, dict):
            raise UserError(request.env._("The state of the editor is not valid."))
        # The rules of the user decide: the marks are kept only with a picture they could start from.
        source = request.env["int.filemanager.document"].search([("id", "=", source_id)])
        if not source:
            return {}
        return {"edit_state": state, "edit_source_id": source.id}

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
        except ValueError:
            raise BadRequest() from None
        companies = self._list_companies()
        documents = request.env["int.filemanager.document"].with_context(allowed_company_ids=companies)
        documents = documents.browse(sorted(document_ids))
        if len(documents.exists()) != len(document_ids):
            raise request.not_found()
        documents.check_access("read")
        try:
            entries = documents._zip_entries()
        except UserError as error:
            return self._zip_refused(error)
        return self._zip_response(entries, f"documents-{fields.Date.context_today(documents)}.zip")

    @http.route("/int_filemanager/folder_zip/<int:folder_id>", type="http", auth="user", methods=["GET"])
    def folder_zip(self, folder_id):
        """A folder with everything below it that the user sees, as one ZIP.

        The checks are those of ``zip``: the companies of the list from the cookie, the folder read
        as the user, now. What lies below is what the user sees on the way down from this folder
        (``_zip_tree``): the name of a folder that is hidden is nowhere in the archive.
        """
        companies = self._list_companies()
        folder = request.env["int.filemanager.folder"].with_context(allowed_company_ids=companies).browse(folder_id)
        if not folder.exists():
            raise request.not_found()
        folder.check_access("read")
        try:
            entries = folder._zip_entries()
        except UserError as error:
            return self._zip_refused(error)
        return self._zip_response(entries, f"{export_name(folder.name)}-{fields.Date.context_today(folder)}.zip")

    def _list_companies(self):
        """The companies that the list of the web client shows (its cookie), as ids; 400 if broken."""
        try:
            return [
                int(company_id)
                for company_id in request.cookies.get("cids", str(request.env.user.company_id.id)).split("-")
            ]
        except ValueError:
            raise BadRequest() from None

    def _zip_refused(self, error):
        """The answer to what cannot be a ZIP: 409 with the reason, which the user reads in the tab."""
        return request.make_response(error.args[0], headers=[("Content-Type", "text/plain; charset=utf-8")], status=409)

    def _zip_response(self, entries, name):
        # The request lives as long as the stream does. The records of a big folder (hundreds of
        # thousands of documents) have done their work, the entries are all that the stream needs.
        request.env.invalidate_all()
        headers = [
            ("Content-Type", "application/zip"),
            ("Content-Length", str(zip_length(entries))),
            ("Content-Disposition", http.content_disposition(name)),
            ("X-Content-Type-Options", "nosniff"),
        ]
        tag = f"{name} of {len(entries)} files for user {request.env.uid}"
        return Response(logged_chunks(entries, tag), headers=headers, direct_passthrough=True)
