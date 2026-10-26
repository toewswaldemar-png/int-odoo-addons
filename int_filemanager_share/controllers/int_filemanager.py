import errno
import unicodedata

from werkzeug.exceptions import MethodNotAllowed

from odoo import fields, http
from odoo.exceptions import MissingError, UserError
from odoo.fields import Domain
from odoo.http import request
from odoo.tools import format_date, hmac
from odoo.tools.image import ImageProcess
from odoo.tools.misc import human_size
from odoo.tools.sql import escape_psql
from odoo.tools.translate import LazyTranslate

from odoo.addons.portal.controllers.portal import pager as portal_pager

from ..models.int_filemanager_share import (
    SHARE_PATH,
    MEBIBYTE,
    UPLOAD_HEAD_SIZE,
    ShareBadRequest,
    ShareBusy,
    ShareForbidden,
    ShareGone,
    ShareNotFound,
)

_lt = LazyTranslate(__name__)

# The password and the receipts are small: the core would read up to 128 MiB of a request.
SMALL_REQUEST = 64 * 1024
# The key of the password lives in a cookie of its own for each share, as the guests of the discuss
# channels keep theirs (``mail.guest``); the addresses carry no secret but the token. Its path is
# ``/``: a page in another language comes with a prefix (``/de/int_filemanager/...``, the pages are
# frontend routes like those of the portal), and the cookie of a narrower path would not go along.
KEY_COOKIE_PREFIX = "int_filemanager_share_key_"


def key_cookie(token):
    """The name of the cookie that holds the key of the share with this token."""
    return f"{KEY_COOKIE_PREFIX}{token}"


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
FOLDER = "int.filemanager.folder"
# The list of a folder, as the lists of the portal: files per page, the sortings (folders come before
# the files in all of them; the size sorts the files only), the longest search text.
PAGE_SIZE = 30
SEARCH_MAX_LENGTH = 100
SORTINGS = {
    "name": {"label": _lt("Name"), "order": "name, id"},
    "date": {"label": _lt("Modified"), "order": "write_date desc, id"},
    "size": {"label": _lt("Size"), "order": "size desc, id"},
}
# The symbol of a file in the list, by the start of its type.
ICONS = (
    ("application/pdf", "fa-file-pdf-o"),
    ("image/", "fa-file-image-o"),
    ("audio/", "fa-file-audio-o"),
    ("video/", "fa-file-video-o"),
    ("text/", "fa-file-text-o"),
    ("application/zip", "fa-file-archive-o"),
    ("application/vnd.openxmlformats-officedocument.wordprocessingml", "fa-file-word-o"),
    ("application/vnd.openxmlformats-officedocument.spreadsheetml", "fa-file-excel-o"),
    ("application/vnd.openxmlformats-officedocument.presentationml", "fa-file-powerpoint-o"),
)


def upload_limit(controller):
    """The most that the body of an upload to a share may be (the ``max_content_length`` of the
    route). Odoo calls it before it reads the body, so a body that is too big is turned away with
    a 413 at once, and what the share allows decides, not a limit for all. The address of the
    request names the share (``.../share/<token>/upload``), the cookie carries the key of its
    password.
    """
    token = request.httprequest.path.removeprefix(f"{SHARE_PATH}/").split("/", 1)[0]
    return request.env["int.filemanager.share"]._upload_body_limit(token, request.httprequest.cookies.get(key_cookie(token)))


class IntFilemanagerShareController(http.Controller):
    """What a guest reaches with the address of a share: no account, no session.

    The pages are made on the server and shown in the layout of the portal, as ``project`` and
    ``sale`` show a record to whoever has its ``access_token`` (``portal.mixin``,
    ``CustomerPortal._document_check_access``): the token of the share is checked, then the
    records are read as superuser, but only those that ``share._scope_domain`` names, and only the
    fields that go into the template as plain values. Nothing of the ORM is open to the guest.

    Every route carries the token in the path and sets ``save_session=False``: without it Odoo
    would give each guest a session cookie and keep a session file for it. A guest is the
    public user, also if somebody who is logged in opens the address.
    """

    def _guest(self):
        """From here on the environment of the request is the one of the public user."""
        request.update_env(user=request.env.ref("base.public_user"))

    @staticmethod
    def _key(token):
        """The key that the password gave, from the cookie of the share (``None``: there is none)."""
        return request.httprequest.cookies.get(key_cookie(token))

    def _resolve(self, token, **kwargs):
        self._guest()
        kwargs.setdefault("key", self._key(token))
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

    # --- the password -------------------------------------------------------------------------

    def _password_page(self, token, error=None, status=200):
        """The page that asks for the password: nothing of the share is on it, not even its name."""
        return self._guest_headers(
            request.render(
                "int_filemanager_share.share_password_page",
                {"token": token, "unlock_url": f"{SHARE_PATH}/{token}/unlock", "error": error},
                status=status,
            )
        )

    @http.route(
        f"{SHARE_PATH}/<string:token>/unlock",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
        save_session=False,
        website=True,
        max_content_length=SMALL_REQUEST,
    )
    def unlock(self, token, password=None, **kwargs):
        """The form of the password page: a right password sets the cookie with the key of the share
        (see ``int.filemanager.share._unlock``) and leads on to the share.

        A wrong password is an answer, not an error: an error would roll the transaction back, and
        the page would have nothing to say but a status. The tries are counted in a transaction of
        their own, so the brake holds either way. No token for the CSRF: the route only sets the
        cookie for this share, to whoever knows its password, and counts every try.
        """
        share = self._resolve(token, needs_key=False, braked=False)
        page = f"{SHARE_PATH}/{share.token}"
        if not share.has_password:
            return self._guest_headers(request.redirect(page))
        try:
            key = share._unlock(password, request.httprequest.remote_addr)
        except ShareBusy as error:
            return self._password_page(token, error.args[0], status=error.http_status)
        if not key:
            return self._password_page(token, request.env._("The password is wrong."), status=403)
        response = self._guest_headers(request.redirect(page))
        response.set_cookie(
            key_cookie(share.token),
            key,
            max_age=share._setting("share_unlock_hours") * 3600,
            path="/",
            secure=request.httprequest.is_secure,
            httponly=True,
            samesite="Lax",
        )
        return response

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
    def content(self, token, document_id, download=None, **kwargs):
        """The file: shown in the browser (the right to see, and only what a browser shows), or
        as a download (the right to download; with a limit of downloads only by ``POST``, see
        ``download``)."""
        share = self._resolve(token, right=("view", "download"))
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
    def download(self, token, document_id, **kwargs):
        """The download that is counted, and ends the share at its limit (the button of the page
        is a form). Only a ``POST``: a link checker that calls an address with ``GET`` would use
        up a limit of one, and a ``Range`` header would get the file without being counted."""
        share = self._resolve(token, right="download")
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
    def thumbnail(self, token, document_id, **kwargs):
        """The picture of the first page of a PDF (the placeholder where there is none)."""
        share = self._resolve(token, right="view")
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
    def image(self, token, document_id, size, **kwargs):
        """A picture made smaller, of one of the sizes in ``IMAGE_SIZES``.

        The core reads the whole file to make it smaller and does not look at the number of
        pixels: a small file can be a picture of hundreds of megapixels. So the file is looked at
        first (its size, then its resolution by ``ImageProcess`` with ``verify_resolution``);
        what is too much gets the placeholder, like a file that is not a picture.
        """
        share = self._resolve(token, right="view")
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
        [
            f"{SHARE_PATH}/<string:token>",
            f"{SHARE_PATH}/<string:token>/folder/<int(max=2147483647):folder_id>",
            f"{SHARE_PATH}/<string:token>/folder/<int(max=2147483647):folder_id>/page/<int(max=2147483647):page>",
        ],
        type="http",
        auth="public",
        methods=["GET"],
        save_session=False,
        website=True,
    )
    def page(self, token, folder_id=None, page=1, sortby=None, search=None, **kwargs):
        """The page of a share: the file, or a folder with what lies in it.

        For a share with a password and no key only a page that asks for it, with nothing of the
        share on it (not its name).
        """
        share = self._resolve(token, needs_key=False)
        if share.has_password and not share._key_is_valid(self._key(token)):
            return self._password_page(token)
        if request.httprequest.method != "HEAD":
            share._count_visit()
        if share.document_id:
            if folder_id:
                raise ShareNotFound(request.env._("This folder does not exist."))
            template, values = "int_filemanager_share.share_file_page", self._file_values(share)
        else:
            template, values = "int_filemanager_share.share_folder_page", self._folder_values(
                share, folder_id, page, sortby, search
            )
        return self._guest_headers(request.render(template, values))

    def _file_values(self, share):
        """What the page of a file shows: plain values, no records."""
        document = share.document_id
        base = f"{SHARE_PATH}/{share.token}"
        picture_url = None
        if share.can_view:
            if document.mimetype and document.mimetype.startswith("image/"):
                picture_url = f"{base}/image/{document.id}/512"
            elif document.thumbnail_state == "done":
                picture_url = f"{base}/thumbnail/{document.id}"
        return {
            "name": document.name,
            "mimetype": document.mimetype or "",
            "size_text": human_size(document.size),
            "picture_url": picture_url,
            "show_url": (
                f"{base}/content/{document.id}" if share.can_view and self._inline(document.mimetype) else None
            ),
            "download_url": f"{base}/download/{document.id}" if share.can_download else None,
            "downloads_left": share.max_downloads - share.download_count if share.max_downloads else None,
        }

    @staticmethod
    def _upload_hint(share):
        """The line under the button: how large a file may be, and which endings are taken."""
        hints = [request.env._("Up to %(size)s per file.", size=human_size(share.upload_max_file_mb * MEBIBYTE))]
        extensions = ", ".join(sorted(share._upload_extensions()))
        if extensions:
            hints.append(request.env._("Allowed: %(kinds)s.", kinds=extensions))
        return " ".join(hints)

    @staticmethod
    def _icon(mimetype):
        return next((icon for start, icon in ICONS if (mimetype or "").startswith(start)), "fa-file-o")

    def _folder_values(self, share, folder_id, page, sortby, search):
        """What the page of a folder shows: the way down from the shared folder, the folders and the
        files in it (or, for a search, the ones below it), a page of them, and the rights.

        Everything that is read is asked together with the scope of the share, and the folder of
        the address must be in it too: one that is hidden, or lies outside, does not exist.
        """
        env, base = share.env, f"{SHARE_PATH}/{share.token}"
        can_upload = share.can_upload and share._upload_folder_usable()
        rights = {"can_view": share.can_view, "can_download": share.can_download, "can_upload": can_upload}
        values = {
            "name": share.folder_id.name,
            "rights": rights,
            "listing": share.can_view or share.can_download,
            "token": share.token,
            "upload_closed": share.can_upload and not can_upload,
            "upload_max_file": share.upload_max_file_mb * MEBIBYTE,
            "upload_hint": self._upload_hint(share),
            "is_portal": True,
        }
        if not values["listing"]:
            return {**values, "title": values["name"], "breadcrumbs": [], "rows": []}
        Folder, Document = env[FOLDER], env[DOCUMENT]
        folder_scope, document_scope = share._scope_domain(FOLDER), share._scope_domain(DOCUMENT)
        current = Folder.search(Domain("id", "=", share.folder_id.id if folder_id is None else folder_id) & folder_scope, limit=1)
        if not current:
            raise ShareNotFound(request.env._("This folder does not exist."))
        sortby = sortby if sortby in SORTINGS else "name"
        # No control characters: the database does not take a NUL in a text, and nothing else of them
        # belongs in a name that is looked for.
        search = "".join(c for c in (search if isinstance(search, str) else "") if unicodedata.category(c) != "Cc")
        search = search.strip()[:SEARCH_MAX_LENGTH]
        order = SORTINGS[sortby]["order"]
        folder_order = SORTINGS["name"]["order"] if sortby == "size" else order
        if search:
            # ``ilike`` takes % and _ as they are; the text of the guest is text, not a pattern
            pattern = escape_psql(search)
            folder_domain = (
                Domain("id", "child_of", current.id)
                & Domain("id", "!=", current.id)
                & Domain("name", "ilike", pattern)
                & folder_scope
            )
            document_domain = (
                Domain("folder_id", "child_of", current.id) & Domain("name", "ilike", pattern) & document_scope
            )
        else:
            folder_domain = Domain("parent_id", "=", current.id) & folder_scope
            document_domain = Domain("folder_id", "=", current.id) & document_scope
        folder_total, document_total = Folder.search_count(folder_domain), Document.search_count(document_domain)
        url = f"{base}/folder/{current.id}"
        url_args = {"sortby": sortby if sortby != "name" else None, "search": search or None}
        pager = portal_pager(
            url,
            folder_total + document_total,
            page,
            PAGE_SIZE,
            url_args={key: value for key, value in url_args.items() if value},
        )
        offset = pager["offset"]
        folders = Folder.browse()
        if offset < folder_total:
            folders = Folder.search_fetch(
                folder_domain, ["name", "write_date", "parent_id"], order=folder_order, offset=offset, limit=PAGE_SIZE
            )
        documents = Document.browse()
        if PAGE_SIZE - len(folders) > 0:
            documents = Document.search_fetch(
                document_domain,
                ["name", "size", "mimetype", "write_date", "folder_id"],
                order=order,
                offset=max(offset - folder_total, 0),
                limit=PAGE_SIZE - len(folders),
            )
        rows = [
            {
                "kind": "folder",
                "name": folder.name,
                "icon": "fa-folder",
                "url": f"{base}/folder/{folder.id}",
                "size_text": "",
                "date": format_date(env, folder.write_date),
                "where": folder.parent_id.name if search else "",
            }
            for folder in folders
        ]
        for document in documents:
            rows.append(
                {
                    "kind": "file",
                    "name": document.name,
                    "icon": self._icon(document.mimetype),
                    "show_url": (
                        f"{base}/content/{document.id}"
                        if share.can_view and self._inline(document.mimetype)
                        else None
                    ),
                    "download_url": f"{base}/content/{document.id}?download=1" if share.can_download else None,
                    "size_text": human_size(document.size),
                    "date": format_date(env, document.write_date),
                    "where": document.folder_id.name if search else "",
                }
            )
        return {
            **values,
            "title": current.name,
            "current": current.name,
            "breadcrumbs": self._breadcrumbs(share, current, base),
            "rows": rows,
            "search_results": bool(search),
            "pager": pager if pager["page_count"] > 1 else None,
            "searchbar_sortings": SORTINGS,
            "sortby": sortby,
            "searchbar_inputs": {"name": {"input": "name", "label": request.env._("Name")}},
            "search_in": "name",
            "search": search,
            "default_url": url,
        }

    @staticmethod
    def _breadcrumbs(share, current, base):
        """The way from the shared folder down to this one, ``[{"name", "url"}]``; the last has no
        address. The folders above the shared one are not on it: the guest does not learn them."""
        chain = [int(folder_id) for folder_id in current.parent_path.split("/") if folder_id]
        chain = chain[chain.index(share.folder_id.id) :]
        names = {
            folder.id: folder.name for folder in share.env[FOLDER].search_fetch([("id", "in", chain)], ["name"])
        }
        crumbs = [
            {"name": names[folder_id], "url": f"{base}/folder/{folder_id}"} for folder_id in chain if folder_id in names
        ]
        crumbs[-1]["url"] = None
        return crumbs

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
        """What the page of the guests shows: the text of ``{"error": {"message": ...}}`` (the uploads
        of the users answer the same way)."""
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
    def upload(self, token, **kwargs):
        """Keep one file that a guest sends, in the folder for the uploads of the share.

        The key of the password is in the cookie, which Odoo has before it reads the body: the size
        of the body is limited first (``upload_limit``), and that needs to know whether the request
        may carry a file at all. The answer is the JSON of the file and its receipt, or
        ``{"error": {"message": ...}}`` with a status.
        """
        try:
            return self._upload(token)
        except UserError as error:  # also the refusals of the share, which carry their status
            return self._upload_error(getattr(error, "http_status", 400), error.args[0])
        except OSError as error:
            if error.errno != errno.ENOSPC:
                raise
            return self._upload_error(507, request.env._("There is no space left to store the file."))

    def _upload(self, token):
        share = self._resolve(token, right="upload")
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

        The body is ``{"receipts": [{"id": ..., "receipt": ...}, ...]}``. What the receipts do not
        prove is left out without a word.
        """
        data = self._json_body()
        share = self._resolve(token, right="upload")
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

        The body is ``{"id": ..., "receipt": ...}``.
        """
        data = self._json_body()
        share = self._resolve(token, right="upload")
        own = share._own_uploads([{"id": data.get("id"), "receipt": data.get("receipt")}])
        if not own:
            raise ShareNotFound(request.env._("This file does not exist."))
        if not share._removable_uploads(own):
            raise ShareForbidden(request.env._("This file has been taken over. It cannot be removed any more."))
        size = own.size
        own.unlink()
        share._release_upload(size)
        return self._guest_headers(request.make_json_response({"removed": True}))
