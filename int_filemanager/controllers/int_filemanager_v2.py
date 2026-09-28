"""HTTP routes of the v2 file manager.

Everything runs as the logged-in user; sudo() only reaches the blob after the
node's rights were checked.
"""

import mimetypes
import os
import re
from datetime import timezone

from werkzeug.exceptions import BadRequest, Conflict, NotFound

from odoo import http
from odoo.http import request

from .. import blobstore, zip_stream

# The client sends 4 MiB chunks (bigger ones make the workers grow too much); the
# route accepts a little more than that and nothing beyond.
CHUNK_MAX_BYTES = 5 * 1024 * 1024


class IntFilemanagerV2Controller(http.Controller):
    def _node_for_read(self, node_id):
        """Return the node if the user may read it (else 404 or 403)."""
        node = request.env["int_filemanager.node"].browse(node_id).exists()
        if not node:
            raise NotFound
        node.check_access("read")
        return node

    @http.route(
        "/int_filemanager/v2/download/<int:node_id>",
        type="http",
        auth="user",
        methods=["GET"],
    )
    def download(self, node_id, revision_id=None, disposition="attachment"):
        """Download a file, or one of its older revisions.

        Range requests and x_sendfile are handled by ``http.Stream``.
        """
        node = self._node_for_read(node_id)
        if node.is_dir:
            raise BadRequest
        if revision_id:
            try:
                revision = request.env["int_filemanager.revision"].browse(
                    int(revision_id)
                )
            except ValueError:
                raise BadRequest from None
            revision = revision.exists()
            if not revision or revision.node_id != node:
                raise NotFound
            revision.check_access("read")
        else:
            revision = node.current_revision_id
            if not revision:
                raise NotFound

        # The checks above authorise the blob; blobs have no rights of their own.
        stream = self._blob_stream(node, revision)
        return stream.get_response(as_attachment=disposition != "inline")

    @http.route(
        "/int_filemanager/v2/upload/<int:upload_id>/chunk",
        type="http",
        auth="user",
        methods=["POST"],
        max_content_length=CHUNK_MAX_BYTES,
    )
    def upload_chunk(self, upload_id, offset, **_kwargs):
        """Receive one chunk of an upload as the raw request body.

        The CSRF token is in the query string because the body is the data.
        """
        try:
            offset = int(offset)
        except ValueError:
            raise BadRequest from None
        data = request.httprequest.get_data()
        result = request.env["int_filemanager.upload"].upload_chunk(
            upload_id, offset, data
        )
        return request.make_json_response(result)

    @http.route("/int_filemanager/v2/zip", type="http", auth="user", methods=["GET"])
    def zip_direct(self, ids=""):
        """Stream the selected nodes as one ZIP.

        Only up to the direct limit, because the stream holds a worker for its
        whole duration; bigger selections go through int_filemanager.zip_job.
        """
        try:
            node_ids = [int(i) for i in ids.split(",") if i]
        except ValueError:
            raise BadRequest from None
        if not node_ids:
            raise BadRequest
        entries, total, name = zip_stream.collect_entries(request.env, node_ids)
        if total > zip_stream.direct_max_bytes(request.env):
            raise Conflict("Too big for a direct download; request it as a job.")
        return request.make_response(
            zip_stream.stream_zip(entries),
            headers=[
                ("Content-Type", "application/zip"),
                ("Content-Disposition", http.content_disposition(name)),
                ("X-Content-Type-Options", "nosniff"),
            ],
        )

    @http.route(
        "/int_filemanager/v2/zip/job/<int:job_id>",
        type="http",
        auth="user",
        methods=["GET"],
    )
    def zip_job_download(self, job_id):
        job = request.env["int_filemanager.zip_job"].browse(job_id).exists()
        if not job:
            raise NotFound
        job.check_access("read")
        if job.state != "done" or not re.fullmatch(
            r"\d+-[0-9a-f]{32}\.zip", job.file_name
        ):
            raise NotFound
        path = job._path()
        if not os.path.exists(path):
            raise NotFound
        stream = http.Stream(
            type="path",
            path=path,
            mimetype="application/zip",
            size=os.path.getsize(path),
            download_name=job.name,
            last_modified=os.path.getmtime(path),
            etag=job.file_name,
            public=False,
        )
        return stream.get_response(as_attachment=True)

    # ------------------------------------------------------------------
    # sharing: anonymous links and the customer portal
    # ------------------------------------------------------------------

    def _blob_stream(self, node, revision):
        """Return the content of ``revision`` as a Stream; the caller checked access."""
        blob = revision.sudo().blob_id
        return http.Stream(
            type="path",
            path=blobstore.blob_path(request.env, blob.sha256),
            mimetype=node.mime
            or mimetypes.guess_type(node.name)[0]
            or "application/octet-stream",
            size=int(blob.size),
            download_name=node.name,
            last_modified=revision.create_date.replace(tzinfo=timezone.utc).timestamp(),
            etag=blob.sha256,
            public=False,
        )

    @http.route("/int_filemanager/v2/share/<string:token>", type="http", auth="public")
    def share_download(self, token):
        """Download a file through a share link, without login.

        Unknown, expired, revoked and trashed links all answer the same 404.
        """
        share = request.env["int_filemanager.share"]._find_active(token)
        if not share:
            raise NotFound
        node = share.node_id
        share._log("downloaded")
        share.download_count += 1
        response = self._blob_stream(node, node.current_revision_id).get_response(
            as_attachment=True
        )
        response.headers["Cache-Control"] = "private, no-store"
        return response

    def _portal_node(self, node_id):
        node = request.env["int_filemanager.node"].sudo().browse(node_id).exists()
        partner = request.env.user.partner_id
        if (
            not node
            or not node.active
            or node.is_dir
            or not node.current_revision_id
            or partner not in node.shared_partner_ids
        ):
            raise NotFound
        return node

    @http.route("/my/files", type="http", auth="user", website=True)
    def portal_files(self, **_kwargs):
        partner = request.env.user.partner_id
        nodes = (
            request.env["int_filemanager.node"]
            .sudo()
            .search(
                [("shared_partner_ids", "in", [partner.id]), ("is_dir", "=", False)],
                order="name",
            )
        )
        return request.render(
            "int_filemanager.portal_files", {"page_name": "files", "files": nodes}
        )

    @http.route("/my/files/<int:node_id>/download", type="http", auth="user")
    def portal_file_download(self, node_id, **_kwargs):
        node = self._portal_node(node_id)
        request.env["int_filemanager.share_log"].sudo().create(
            {
                "node_id": node.id,
                "path": node._display_path(),
                "filename": node.name,
                "event_type": "downloaded",
                "partner_id": request.env.user.partner_id.id,
            }
        )
        response = self._blob_stream(node, node.current_revision_id).get_response(
            as_attachment=True
        )
        response.headers["Cache-Control"] = "private, no-store"
        return response
