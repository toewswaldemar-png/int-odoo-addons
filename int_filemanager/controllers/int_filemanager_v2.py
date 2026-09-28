"""Browser-facing HTTP routes of the v2 file manager (Konzept 7/8). Everything here
runs as the logged-in user: rights come from the ORM (ir.rule on node/revision),
never from a path, and `sudo()` only reaches the blob AFTER that check (I7)."""

import mimetypes
import os
import re
from datetime import timezone

from werkzeug.exceptions import BadRequest, Conflict, NotFound

from odoo import http
from odoo.http import request

from .. import blobstore, zip_stream

# Konzept 7: chunks are 4 MiB (bigger ones let the workers grow up to 1.9 GB, 19.2); the
# route accepts a little more than that and nothing beyond.
CHUNK_MAX_BYTES = 5 * 1024 * 1024


class IntFilemanagerV2Controller(http.Controller):
    def _node_for_read(self, node_id):
        """The node, or 404. check_access raises AccessError (-> 403) for a node this
        user may not read; a node that does not exist at all is a plain 404."""
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
        """One file, current or a given older revision. Range requests work through
        Odoo's own Stream; with `x_sendfile` on, nginx delivers the bytes (the blob
        store lives below data_dir/filestore for exactly that, Konzept 5)."""
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

        # The rights check above is what authorises the blob; the blob itself has no
        # ACL of its own (Konzept 12/A1).
        blob = revision.sudo().blob_id
        path = blobstore.blob_path(request.env, blob.sha256)
        stream = http.Stream(
            type="path",
            path=path,
            mimetype=node.mime
            or mimetypes.guess_type(node.name)[0]
            or "application/octet-stream",
            size=int(blob.size),
            download_name=node.name,
            last_modified=revision.create_date.replace(tzinfo=timezone.utc).timestamp(),
            # Content is immutable and named by its hash, so the hash is the ETag.
            etag=blob.sha256,
            public=False,
        )
        return stream.get_response(as_attachment=disposition != "inline")

    @http.route(
        "/int_filemanager/v2/upload/<int:upload_id>/chunk",
        type="http",
        auth="user",
        methods=["POST"],
        max_content_length=CHUNK_MAX_BYTES,
    )
    def upload_chunk(self, upload_id, offset, **_kwargs):
        """One piece of an upload as the raw request body (Content-Type
        application/octet-stream, no base64 inflation): `offset` is where it starts.
        Repeating a piece already received is harmless; a gap is refused
        (int_filemanager.upload.upload_chunk, Konzept 7). The csrf_token travels in
        the query string because the body is the data."""
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
        """A selection as one ZIP, streamed while it is packed. Only up to the direct
        limit (500 MB by default, Konzept 8): a stream holds a worker for its whole
        duration; bigger selections go through int_filemanager.zip_job.request_zip."""
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
