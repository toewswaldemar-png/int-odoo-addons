import email.utils
import logging
import mimetypes
import os

from odoo import http
from odoo.exceptions import AccessError, UserError
from odoo.http import request

from .. import webdav_tokens
from ..path_utils import resolve_path

_logger = logging.getLogger(__name__)

_DAV_METHODS = ["OPTIONS", "GET", "HEAD", "PUT", "LOCK", "UNLOCK", "PROPFIND", "PROPPATCH"]


def _etag(abs_path):
    return '"%d"' % int(os.path.getmtime(abs_path))


def _formatdate(abs_path):
    return email.utils.formatdate(os.path.getmtime(abs_path), usegmt=True)


def _drain_body():
    # Every handler must consume the request body even if unused - an
    # unread body left on a keep-alive connection corrupts the *next*
    # request on that connection. Verified empirically against real
    # Excel 365 (surfaced as intermittent "Bad request syntax" errors).
    request.httprequest.get_data()


class IntFilemanagerWebdavController(http.Controller):

    @http.route("/int_filemanager/webdav_token", type="jsonrpc", auth="user", methods=["POST"])
    def webdav_token(self, path=""):
        if not request.env.user.has_group("int_filemanager.group_filemanager_user"):
            raise AccessError("Kein Zugriff auf den Dateimanager.")
        abs_path = resolve_path(request.env, path)
        if not os.path.isfile(abs_path):
            raise UserError("Datei nicht gefunden.")
        rel_path = path
        token = webdav_tokens.issue(rel_path)
        filename = os.path.basename(abs_path)
        url = "%sint_filemanager/webdav/%s/%s" % (request.httprequest.host_url, token, filename)
        return {"token": token, "url": url}

    @http.route(
        "/int_filemanager/webdav/<string:token>/<string:filename>",
        type="http", auth="public", methods=_DAV_METHODS, csrf=False,
    )
    def webdav(self, token, filename):
        method = request.httprequest.method
        rel_path = webdav_tokens.resolve(token)

        if method == "OPTIONS":
            _drain_body()
            return self._dav_response(200, headers=[
                ("Allow", "OPTIONS, GET, HEAD, PUT, PROPFIND, PROPPATCH, LOCK, UNLOCK"),
            ])

        if rel_path is None:
            _drain_body()
            return self._dav_response(403)

        abs_path = resolve_path(request.env, rel_path)

        if method in ("GET", "HEAD"):
            return self._get(abs_path, head_only=method == "HEAD")
        if method == "PUT":
            return self._put(abs_path)
        if method == "LOCK":
            return self._lock(rel_path)
        if method == "UNLOCK":
            return self._unlock(rel_path)
        if method == "PROPFIND":
            return self._propfind(abs_path, rel_path)
        if method == "PROPPATCH":
            _drain_body()
            return self._dav_response(207)

        _drain_body()
        return self._dav_response(405)

    # -----------------------------------------------------------------
    # verb handlers
    # -----------------------------------------------------------------

    def _get(self, abs_path, head_only):
        if not os.path.isfile(abs_path):
            return self._dav_response(404)
        etag = _etag(abs_path)
        if request.httprequest.headers.get("If-None-Match") == etag:
            return self._dav_response(304, headers=[("ETag", etag)])
        headers = [
            ("Content-Type", mimetypes.guess_type(abs_path)[0] or "application/octet-stream"),
            ("Last-Modified", _formatdate(abs_path)),
            ("ETag", etag),
        ]
        if head_only:
            headers.append(("Content-Length", str(os.path.getsize(abs_path))))
            return self._dav_response(200, headers=headers)
        with open(abs_path, "rb") as f:
            data = f.read()
        return self._dav_response(200, headers=headers, body=data)

    def _put(self, abs_path):
        data = request.httprequest.get_data()
        with open(abs_path, "wb") as f:
            f.write(data)
        # No index_upsert here on purpose - same lesson as the ONLYOFFICE
        # sync fix: the filesystem watcher picks up this write and updates
        # the index itself, avoiding two concurrent transactions racing on
        # the same row (previously "could not serialize access").
        _logger.info("int_filemanager webdav: wrote %d bytes to %s", len(data), abs_path)
        return self._dav_response(204)

    def _lock(self, rel_path):
        _drain_body()
        token = webdav_tokens.lock(rel_path)
        body = (
            '<?xml version="1.0" encoding="utf-8"?>'
            '<D:prop xmlns:D="DAV:"><D:lockdiscovery><D:activelock>'
            "<D:locktype><D:write/></D:locktype>"
            "<D:lockscope><D:exclusive/></D:lockscope>"
            "<D:depth>0</D:depth>"
            "<D:timeout>Second-600</D:timeout>"
            "<D:locktoken><D:href>%s</D:href></D:locktoken>"
            "</D:activelock></D:lockdiscovery></D:prop>" % token
        ).encode("utf-8")
        return self._dav_response(200, headers=[
            ("Lock-Token", "<%s>" % token),
            ("Content-Type", "application/xml; charset=utf-8"),
        ], body=body)

    def _unlock(self, rel_path):
        _drain_body()
        lock_token = request.httprequest.headers.get("Lock-Token", "").strip("<>")
        webdav_tokens.unlock(rel_path, lock_token)
        return self._dav_response(204)

    def _propfind(self, abs_path, rel_path):
        _drain_body()
        exists = os.path.isfile(abs_path)
        size = os.path.getsize(abs_path) if exists else 0
        last_modified = _formatdate(abs_path) if exists else ""
        etag = _etag(abs_path) if exists else '"0"'
        content_type = mimetypes.guess_type(abs_path)[0] or "application/octet-stream"
        body = (
            '<?xml version="1.0" encoding="utf-8"?>'
            '<D:multistatus xmlns:D="DAV:" xmlns:Office="urn:schemas-microsoft-com:office:office">'
            "<D:response><D:href>%s</D:href><D:propstat><D:prop>"
            "<D:displayname>%s</D:displayname>"
            "<D:getcontentlength>%d</D:getcontentlength>"
            "<D:getlastmodified>%s</D:getlastmodified>"
            "<D:creationdate>%s</D:creationdate>"
            "<D:resourcetype/>"
            "<D:getetag>%s</D:getetag>"
            "<D:getcontenttype>%s</D:getcontenttype>"
            "<Office:modifiedby></Office:modifiedby>"
            "</D:prop><D:status>HTTP/1.1 200 OK</D:status></D:propstat>"
            "</D:response></D:multistatus>"
            % (request.httprequest.path, os.path.basename(abs_path), size, last_modified, last_modified, etag, content_type)
        ).encode("utf-8")
        return self._dav_response(207, headers=[("Content-Type", "application/xml; charset=utf-8")], body=body)

    # -----------------------------------------------------------------
    # helpers
    # -----------------------------------------------------------------

    def _dav_response(self, status, headers=None, body=b""):
        all_headers = [
            ("DAV", "1,2"),
            ("MS-Author-Via", "DAV"),
            ("Cache-Control", "no-cache, no-store, must-revalidate"),
        ] + (headers or [])
        if not any(h[0] == "Content-Length" for h in all_headers):
            all_headers.append(("Content-Length", str(len(body))))
        return request.make_response(body, headers=all_headers, status=status)
