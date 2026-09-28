"""Browser-facing HTTP routes of the v2 file manager (Konzept 7/8). Everything here
runs as the logged-in user: rights come from the ORM (ir.rule on node/revision),
never from a path, and `sudo()` only reaches the blob AFTER that check (I7)."""

import mimetypes
from datetime import timezone

from werkzeug.exceptions import BadRequest, NotFound

from odoo import http
from odoo.http import request

from .. import blobstore


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
