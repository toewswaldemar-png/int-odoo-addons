import errno
from urllib.parse import urlencode

from werkzeug.exceptions import MethodNotAllowed

import odoo.service.common
from odoo import fields, http
from odoo.exceptions import MissingError, UserError
from odoo.fields import Domain
from odoo.http import request
from odoo.tools import hmac
from odoo.tools.image import ImageProcess
from odoo.tools.misc import human_size

from ..models.int_filemanager_share import (
    SHARE_PATH,
    MEBIBYTE,
    UPLOAD_HEAD_SIZE,
    ShareBadRequest,
    ShareForbidden,
    ShareGone,
    ShareNotFound,
)
from ..tools.share_gateway import ShareGateway

# The password and the calls of the gateway are small: the core would read up to 128 MiB of a
# request.
SMALL_REQUEST = 64 * 1024
GATEWAY_REQUEST = 1024 * 1024
# What the browser shows by itself (the guests with the right to see only get these inline), and
# which sizes of a picture they may ask for. A picture is read into memory to be made smaller:
# above this size of the file the guest gets the placeholder.
INLINE_TYPES = {"application/pdf", "text/plain"}
INLINE_PREFIXES = ("image/", "audio/", "video/")
NOT_INLINE = {"image/svg+xml"}
IMAGE_SIZES = (64, 128, 256, 512, 1024)
IMAGE_SOURCE_MAX = 25 * 1024 * 1024
ETAG_SCOPE = "int_filemanager.share_etag"
DOCUMENT = "int.filemanager.document"


def upload_limit(controller):
    """The most that the body of an upload to a share may be (the ``max_content_length`` of the
    route). Odoo calls it before it reads the body, so a body that is too big is turned away with
    a 413 at once, and what the share allows decides, not a limit for all. The address of the
    request names the share (``.../share/<token>/upload``) and may carry the key of its password.
    """
    token = request.httprequest.path.removeprefix(f"{SHARE_PATH}/").split("/", 1)[0]
    return request.env["int.filemanager.share"]._upload_body_limit(token, request.httprequest.args.get("k"))


class IntFilemanagerShareController(http.Controller):
    """What a guest reaches with the address of a share: no account, no cookie.

    Every route carries the token in the path and sets ``save_session=False``: without it Odoo
    would give each guest a session cookie and keep a session file for it. A guest is the
    public user, also if somebody who is logged in opens the address.
    """

    def _guest(self):
        """From here on the environment of the request is the one of the public user."""
        request.update_env(user=request.env.ref("base.public_user"))

    def _resolve(self, token, **kwargs):
        self._guest()
        return request.env["int.filemanager.share"]._resolve(
            token, request.httprequest.remote_addr, **kwargs
        )

    @staticmethod
    def _guest_headers(response):
        """The address is a secret: it is not passed on to other sites (``Referer``), the search
        engines are told to leave it, and the answer is not kept by the browser, so that a share
        that is blocked later does not live on in its cache."""
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Robots-Tag"] = "noindex, nofollow"
        response.headers["Cache-Control"] = "private, no-cache"
        return response

    @http.route(
        f"{SHARE_PATH}/<string:token>/unlock",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
        save_session=False,
        max_content_length=SMALL_REQUEST,
    )
    def unlock(self, token, password=None, **kwargs):
        """The key for the password of a share (see ``int.filemanager.share._unlock``).

        A wrong password is an answer, not an error: an error would roll the transaction back,
        and with it the note of the wrong try that the brake counts.
        """
        share = self._resolve(token, needs_key=False, braked=False)
        key = share._unlock(password, request.httprequest.remote_addr)
        if not key:
            return self._guest_headers(
                request.make_json_response({"error": request.env._("Wrong password.")}, status=403)
            )
        return self._guest_headers(request.make_json_response({"key": key}))

    @http.route(
        f"{SHARE_PATH}/<string:token>/rpc",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
        save_session=False,
        max_content_length=GATEWAY_REQUEST,
    )
    def rpc(self, token, **kwargs):
        """The reading of the views of a folder share (see tools/share_gateway.py).

        The body is JSON: the key of the password as k, and model, method, args
        and kwargs of the call. Not a JSON-RPC route: that kind answers every error with the
        traceback, and with the status 200.
        """
        data = self._json_body()
        share = self._resolve(token, right=("view", "download"), key=data.get("k"))
        if share.document_id:
            raise ShareForbidden(request.env._("This link does not allow that."))
        gateway = ShareGateway(share, lang=request.env.lang)
        result = gateway.call(
            data.get("model"), data.get("method"), data.get("args", []), data.get("kwargs", {})
        )
        return self._guest_headers(request.make_json_response(result))

    # --- the files ----------------------------------------------------------------------------

    @staticmethod
    def _inline(mimetype):
        return mimetype not in NOT_INLINE and (
            mimetype in INLINE_TYPES or bool(mimetype and mimetype.startswith(INLINE_PREFIXES))
        )

    @staticmethod
    def _document(share, document_id):
        """The file, if the share reaches it (the same scope as the lists, not only the id)."""
        document = share.env[DOCUMENT].search(
            Domain("id", "=", document_id) & share._scope_domain(DOCUMENT), limit=1
        )
        if not document:
            raise ShareNotFound(request.env._("This file does not exist."))
        return document

    @staticmethod
    def _guest_etag(share, stream):
        """The checksum of the file is the ETag of the user's download; for a guest it is not:
        it would show which files are the same, in any share. A signed value of the share and the
        checksum changes with the content, is another one per share, and says nothing."""
        if stream.etag:
            stream.etag = hmac(share.env, ETAG_SCOPE, f"{share.id}:{stream.etag}")
        return stream

    def _file_stream(self, share, document):
        try:
            stream = share.env["ir.binary"]._get_stream_from(document, "content")
        except MissingError:
            raise ShareNotFound(request.env._("This file is not there any more.")) from None
        return self._guest_etag(share, stream)

    @http.route(
        f"{SHARE_PATH}/<string:token>/content/<int(max=2147483647):document_id>",
        type="http",
        auth="public",
        methods=["GET"],
        save_session=False,
    )
    def content(self, token, document_id, download=None, k=None, **kwargs):
        """The file: shown in the browser (the right to see, and only what a browser shows), or
        as a download (the right to download; with a limit of downloads only by ``POST``, see
        ``download``)."""
        share = self._resolve(token, right=("view", "download"), key=k)
        document = self._document(share, document_id)
        if download:
            if not share.can_download:
                raise ShareForbidden(request.env._("This link does not allow that."))
            if share.max_downloads:
                raise MethodNotAllowed(valid_methods=["POST"])
        elif not (share.can_view and self._inline(document.mimetype)):
            raise ShareForbidden(request.env._("This link does not allow that."))
        stream = self._file_stream(share, document)
        # A download without a limit is only counted for the statistics: a request with a range
        # asks for a part, and checkers of links ask with HEAD.
        counted = download and request.httprequest.method == "GET" and "Range" not in request.httprequest.headers
        if counted:
            share._count_download()
        return self._guest_headers(stream.get_response(as_attachment=bool(download)))

    @http.route(
        f"{SHARE_PATH}/<string:token>/download/<int(max=2147483647):document_id>",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
        save_session=False,
        max_content_length=SMALL_REQUEST,
    )
    def download(self, token, document_id, k=None, **kwargs):
        """The download that is counted, and ends the share at its limit (the button of the page
        is a form). Only a ``POST``: a link checker that calls an address with ``GET`` would use
        up a limit of one, and a ``Range`` header would get the file without being counted."""
        share = self._resolve(token, right="download", key=k)
        document = self._document(share, document_id)
        stream = self._file_stream(share, document)
        # last, right before the file goes out: what was refused above must not use up a download
        if not share._count_download():
            raise ShareGone(request.env._("This link has reached its limit of downloads."))
        return self._guest_headers(stream.get_response(as_attachment=True))

    @http.route(
        f"{SHARE_PATH}/<string:token>/thumbnail/<int(max=2147483647):document_id>",
        type="http",
        auth="public",
        methods=["GET"],
        save_session=False,
    )
    def thumbnail(self, token, document_id, k=None, **kwargs):
        """The picture of the first page of a PDF (the placeholder where there is none)."""
        share = self._resolve(token, right="view", key=k)
        document = self._document(share, document_id)
        stream = share.env["ir.binary"]._get_image_stream_from(document, "thumbnail")
        return self._guest_headers(self._guest_etag(share, stream).get_response())

    @http.route(
        f"{SHARE_PATH}/<string:token>/image/<int(max=2147483647):document_id>/<int:size>",
        type="http",
        auth="public",
        methods=["GET"],
        save_session=False,
    )
    def image(self, token, document_id, size, k=None, **kwargs):
        """A picture made smaller, of one of the sizes in ``IMAGE_SIZES``.

        The core reads the whole file to make it smaller and does not look at the number of
        pixels: a small file can be a picture of hundreds of megapixels. So the file is looked at
        first (its size, then its resolution by ``ImageProcess`` with ``verify_resolution``);
        what is too much gets the placeholder, like a file that is not a picture.
        """
        share = self._resolve(token, right="view", key=k)
        if size not in IMAGE_SIZES:
            raise ShareNotFound(request.env._("This size does not exist."))
        document = self._document(share, document_id)
        binary = share.env["ir.binary"]
        stream = None
        if document.mimetype and document.mimetype.startswith("image/") and document.size <= IMAGE_SOURCE_MAX:
            try:
                with open(document._blob_path(document.checksum), "rb") as blob:
                    ImageProcess(blob.read(), verify_resolution=True)
                stream = binary._get_image_stream_from(document, "content", width=size, height=size)
            except (OSError, UserError):  # a file that is not there, or not a picture, or too big
                stream = None
        stream = stream or binary._get_placeholder_stream()
        return self._guest_headers(self._guest_etag(share, stream).get_response())

    # --- the pages ----------------------------------------------------------------------------

    @http.route(
        f"{SHARE_PATH}/<string:token>",
        type="http",
        auth="public",
        methods=["GET"],
        save_session=False,
    )
    def page(self, token, **kwargs):
        """The page of a share. For a share with a password only a shell that asks for it, with
        nothing of the share on it (not its name): the page itself comes from ``page_with_key``."""
        share = self._resolve(token, needs_key=False)
        if share.has_password:
            return self._guest_headers(request.render("int_filemanager.share_password_page", {"token": token}))
        return self._render_page(share)

    @http.route(
        f"{SHARE_PATH}/<string:token>/page",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
        save_session=False,
        max_content_length=SMALL_REQUEST,
    )
    def page_with_key(self, token, k=None, **kwargs):
        """The page of a share with a password, for the key that the password gave (it comes
        in the body, never in an address); the shell replaces itself with it."""
        return self._render_page(self._resolve(token, key=k), key=k)

    def _render_page(self, share, key=None):
        if request.httprequest.method != "HEAD":
            share._count_visit()
        if share.document_id:
            template, values = "int_filemanager.share_file_page", self._file_values(share, key)
        else:
            template, values = "int_filemanager.share_folder_page", self._folder_values(share)
        return self._guest_headers(request.render(template, values))

    def _file_values(self, share, key):
        """What the page of a file shows: plain values, no records."""
        document = share.document_id
        base = f"{SHARE_PATH}/{share.token}"
        query = f"?{urlencode({'k': key})}" if key else ""
        picture_url = None
        if share.can_view:
            if document.mimetype and document.mimetype.startswith("image/"):
                picture_url = f"{base}/image/{document.id}/512{query}"
            elif document.thumbnail_state == "done":
                picture_url = f"{base}/thumbnail/{document.id}{query}"
        return {
            "name": document.name,
            "mimetype": document.mimetype or "",
            "size_text": human_size(document.size),
            "picture_url": picture_url,
            "show_url": (
                f"{base}/content/{document.id}{query}"
                if share.can_view and self._inline(document.mimetype)
                else None
            ),
            "download_url": f"{base}/download/{document.id}" if share.can_download else None,
            "downloads_left": share.max_downloads - share.download_count if share.max_downloads else None,
            "key": key,
        }

    def _folder_values(self, share):
        """What the page of a folder needs to start its app: what the webclient puts into the
        session information at the login, minus everything about a user."""
        version_info = odoo.service.common.exp_version()
        session_info = request.env["ir.http"].get_frontend_session_info()
        session_info.update(
            {
                "is_frontend": False,
                "db": request.env.cr.dbname,
                "server_version": version_info.get("server_version"),
                "server_version_info": version_info.get("server_version_info"),
                "user_context": {"lang": request.env.lang, "tz": request.env.context.get("tz") or "UTC"},
                "view_info": request.env["ir.ui.view"].get_view_info(),
                # the size that ``checkFileSize`` of the core tests a file against (0: its own limit)
                "max_file_upload_size": share.upload_max_file_mb * MEBIBYTE if share.can_upload else 0,
                "active_ids_limit": 0,
                "groups": {},
            }
        )
        return {
            "name": share.folder_id.name,
            "token": share.token,
            "session_info": session_info,
            "rights": {
                "can_view": share.can_view,
                "can_download": share.can_download,
                "can_upload": share.can_upload,
                "upload_max_file": share.upload_max_file_mb * MEBIBYTE,
                "upload_extensions": sorted(share._upload_extensions()),
            },
        }

    # --- the uploads --------------------------------------------------------------------------

    @staticmethod
    def _json_body():
        """The body of a call as the dictionary that it has to be."""
        try:
            data = request.get_json_data()
        except ValueError:
            raise ShareBadRequest(request.env._("This is not a call.")) from None
        if not isinstance(data, dict):
            raise ShareBadRequest(request.env._("This is not a call."))
        return data

    def _upload_error(self, status, message):
        """What the ``file_upload`` service of the core shows to the guest: it reads the text from
        ``{"error": {"message": ...}}`` (the uploads of the users answer the same way)."""
        return self._guest_headers(request.make_json_response({"error": {"message": message}}, status=status))

    @http.route(
        f"{SHARE_PATH}/<string:token>/upload",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
        save_session=False,
        max_content_length=upload_limit,
    )
    def upload(self, token, k=None, **kwargs):
        """Keep one file that a guest sends, in the folder for the uploads of the share.

        The key of the password is in the address (``k``), not in the body: the size of the body
        is limited before the body is read (``upload_limit``), and that needs to know whether the
        request may carry a file at all. The answer is the JSON of the file and its receipt, or
        ``{"error": {"message": ...}}`` with a status.
        """
        try:
            return self._upload(token, k)
        except UserError as error:  # also the refusals of the share, which carry their status
            return self._upload_error(getattr(error, "http_status", 400), error.args[0])
        except OSError as error:
            if error.errno != errno.ENOSPC:
                raise
            return self._upload_error(507, request.env._("There is no space left to store the file."))

    def _upload(self, token, key):
        share = self._resolve(token, right="upload", key=key)
        share._check_upload_brake(request.httprequest.remote_addr)
        if not share._upload_folder_usable():
            raise ShareGone(request.env._("This link does not take files."))
        files = request.httprequest.files.getlist("ufile")
        if len(files) != 1:
            raise ShareBadRequest(request.env._("Send exactly one file per request."))
        upload = files[0]
        name = share._upload_name(upload.filename)
        head = upload.stream.read(UPLOAD_HEAD_SIZE)
        upload.stream.seek(0)
        share._check_upload(name, head)
        # The type is not the one the browser says (``None``): it is made from the name and the
        # start of the file, so a guest cannot give his file a harmless one. A savepoint holds
        # what the request writes together: the limits are taken before the file is kept, and a
        # failure later must give them back.
        with request.env.cr.savepoint():
            document = (
                share.env["int.filemanager.document"]
                .with_context(mail_create_nosubscribe=True)
                ._create_from_stream(
                    upload.stream,
                    name,
                    share.upload_folder_id,
                    None,
                    check=lambda stored: share._reserve_upload(stored["size"]),
                    share_id=share.id,
                )
            )
        return self._guest_headers(
            request.make_json_response(
                {
                    "id": document.id,
                    "name": document.name,
                    "size": document.size,
                    "receipt": share._receipt(document),
                }
            )
        )

    @http.route(
        f"{SHARE_PATH}/<string:token>/uploads",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
        save_session=False,
        max_content_length=SMALL_REQUEST,
    )
    def uploads(self, token, **kwargs):
        """The files that the guest uploaded, from the receipts that his browser kept.

        The body is ``{"k": key, "receipts": [{"id": ..., "receipt": ...}, ...]}``. What the
        receipts do not prove is left out without a word.
        """
        data = self._json_body()
        share = self._resolve(token, right="upload", key=data.get("k"))
        entries = data.get("receipts")
        if not isinstance(entries, list):
            raise ShareBadRequest(request.env._("This is not a call."))
        own = share._own_uploads(entries)
        removable = share._removable_uploads(own)
        return self._guest_headers(
            request.make_json_response(
                [
                    {
                        "id": document.id,
                        "name": document.name,
                        "size": document.size,
                        "time": fields.Datetime.to_string(document.create_date),
                        "removable": document in removable,
                    }
                    for document in own
                ]
            )
        )

    @http.route(
        f"{SHARE_PATH}/<string:token>/uploads/delete",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
        save_session=False,
        max_content_length=SMALL_REQUEST,
    )
    def uploads_delete(self, token, **kwargs):
        """Take away a file that the guest uploaded, if the receipt is his and no user has taken
        the file over. The limits of the share get it back.

        The body is ``{"k": key, "id": ..., "receipt": ...}``.
        """
        data = self._json_body()
        share = self._resolve(token, right="upload", key=data.get("k"))
        own = share._own_uploads([{"id": data.get("id"), "receipt": data.get("receipt")}])
        if not own:
            raise ShareNotFound(request.env._("This file does not exist."))
        if not share._removable_uploads(own):
            raise ShareForbidden(request.env._("This file has been taken over. It cannot be removed any more."))
        size = own.size
        own.unlink()
        share._release_upload(size)
        return self._guest_headers(request.make_json_response({"removed": True}))
