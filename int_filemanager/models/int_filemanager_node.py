import io
import logging
import os

import psycopg2

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools import SQL
from odoo.tools.mimetypes import guess_mimetype

from .. import blobstore, fault

_logger = logging.getLogger(__name__)


def _remove_if_exists(path):
    try:
        os.remove(path)
    except OSError:
        _logger.warning(
            "could not remove temp file %s after commit", path, exc_info=True
        )


class IntFilemanagerNode(models.Model):
    """A folder or file entry (Konzept 4). Content lives in
    int_filemanager.revision/.blob; a node only carries identity, position
    and rights (I1: Odoo is the sole writer of the tree this describes)."""

    _name = "int_filemanager.node"
    _description = "Filemanager v2 node (folder or file)"
    _inherit = ["mail.thread"]
    _parent_store = True
    _order = "parent_path"

    name = fields.Char(required=True)
    parent_id = fields.Many2one("int_filemanager.node", index=True, ondelete="restrict")
    parent_path = fields.Char(index=True)
    is_dir = fields.Boolean(default=False)
    active = fields.Boolean(default=True)
    removal_reason = fields.Selection([("trash", "Trash")])
    scope_id = fields.Many2one("int_filemanager.scope", required=True, index=True)
    current_revision_id = fields.Many2one(
        "int_filemanager.revision", index=True, ondelete="restrict"
    )
    # Float, not Integer (int4 overflows above ~2 GiB, Pruefbericht Nr. 33-35/19.2).
    size = fields.Float()
    mime = fields.Char()

    # Same (parent_id, lower(name)) uniqueness Windows Explorer enforces
    # (case-insensitive, NTFS-like: "Groesse.txt" next to "GROESSE.txt" is
    # rejected, "GRÖSSE.txt" is not),
    # over the trashed subtree too (active=False keeps its own namespace). NULLS NOT
    # DISTINCT because two root nodes (parent_id IS NULL) would otherwise both pass as
    # "distinct nulls" and bypass the uniqueness entirely (A6, Konzept 4/19.17).
    _unique_name_per_parent = models.UniqueIndex(
        '(parent_id, lower(name COLLATE "und-x-icu")) NULLS NOT DISTINCT WHERE active',
        "A file or folder with this name already exists here.",
    )

    @api.model
    def create_file(self, parent_id, name, content, operation_key):
        """Konzept 6 "Hochladen (neu)" for small files (Konzept 7: content that
        fits in a single request/commit) - runs as the calling user, not sudo
        (I7): ir.rule on create already enforces the parent's scope, and the
        node create() below runs BEFORE any filesystem write so a denied
        request never touches the blob store (Konzept 6 "Rechte pruefen"
        first in the generic flow). A name collision raises instead of
        silently replacing anything (I1); an empty file still gets a
        revision, on the 0-byte blob (A7) - nothing special-cased for that
        here, hashing b"" already lands on it."""
        operation, is_new = self.env["int_filemanager.operation"]._get_or_create(
            operation_key
        )
        if not is_new:
            return operation.result

        parent = self.browse(parent_id)
        scope_id = parent.scope_id.id

        fault.fault_point("node_create_before_check")
        try:
            with self.env.cr.savepoint():
                node = self.create(
                    {
                        "name": name,
                        "parent_id": parent_id,
                        "scope_id": scope_id,
                        "is_dir": False,
                        "mime": guess_mimetype(content) if content else False,
                    }
                )
        except psycopg2.errors.UniqueViolation:
            raise UserError(
                self.env._(
                    "A file or folder named %(name)s already exists here.", name=name
                )
            ) from None

        tmp_path = blobstore.write_stream_to_temp(
            self.env, io.BytesIO(content), f"create_{operation.id}"
        )
        sha256, size = blobstore.hash_file(tmp_path)
        blobstore.adopt_hashed(self.env, tmp_path, sha256, keep_tmp=True)

        # Blob has no user-facing ACL at all (Konzept 12/A1) - sudo() only reaches
        # it after the node create() above already checked this user's identity
        # against the scope (I7 "sudo() nur nach abgeschlossener Pruefung").
        blob = self.env["int_filemanager.blob"].sudo()._get_or_create(sha256, size)
        blobstore.ensure_on_disk(self.env, sha256, tmp_path)
        revision = self.env["int_filemanager.revision"].create(
            {
                "node_id": node.id,
                "blob_id": blob.id,
                "revision_no": 1,
                "origin": "upload",
                "operation_id": operation.id,
                "size": size,
            }
        )
        node.write({"current_revision_id": revision.id, "size": size})
        fault.fault_point("node_create_after_insert")

        result = {"node_id": node.id, "revision_id": revision.id, "sha256": sha256}
        operation.write({"result": result})
        # Only after the surrounding request commits (cr.postcommit never runs on
        # rollback, sql_db.py) - the content is already durable via the hardlink
        # onto its hash, this is just the working copy cleanup (Konzept 5).
        self.env.cr.postcommit.add(lambda: _remove_if_exists(tmp_path))
        return result

    @api.model
    def create_new_revision(
        self, node_id, base_revision_id, content, operation_key, origin="edit"
    ):
        """Konzept 6 "Neue Fassung": the base revision travels with every
        write (WebDAV: lock/ETag) so a stale write becomes a conflict
        instead of a silent overwrite (I6) - the old version is never
        touched, only a new row is added. Same content as the current
        revision -> no new revision at all. check_access() runs before the
        row lock and before any filesystem write (Konzept 6 "Rechte
        pruefen" first) - the raw SQL lock below does not go through
        ir.rule on its own."""
        operation, is_new = self.env["int_filemanager.operation"]._get_or_create(
            operation_key
        )
        if not is_new:
            return operation.result

        node = self.browse(node_id)
        node.check_access("write")

        fault.fault_point("node_lock_before_wait")
        cr = self.env.cr
        cr.execute("SET LOCAL lock_timeout TO '5s'")
        # LockNotAvailable propagates uncaught: retrying() retries the whole
        # request on it (Konzept 6/19.17), this method must not swallow it.
        cr.execute(
            SQL("SELECT id FROM int_filemanager_node WHERE id = %s FOR UPDATE", node_id)
        )
        node.invalidate_recordset(["current_revision_id"])

        current = node.current_revision_id
        if base_revision_id != (current.id or False):
            raise UserError(
                self.env._(
                    "This file changed since you loaded it; reload and try again."
                )
            )

        fault.fault_point("revision_write_before_check")

        tmp_path = blobstore.write_stream_to_temp(
            self.env, io.BytesIO(content), f"revise_{operation.id}"
        )
        sha256, size = blobstore.hash_file(tmp_path)

        if current and current.blob_id.sha256 == sha256:
            os.remove(tmp_path)
            result = {
                "node_id": node.id,
                "revision_id": current.id,
                "sha256": sha256,
                "unchanged": True,
            }
            operation.write({"result": result})
            return result

        blobstore.adopt_hashed(self.env, tmp_path, sha256, keep_tmp=True)
        blob = self.env["int_filemanager.blob"].sudo()._get_or_create(sha256, size)
        blobstore.ensure_on_disk(self.env, sha256, tmp_path)

        next_no = (current.revision_no if current else 0) + 1
        revision = self.env["int_filemanager.revision"].create(
            {
                "node_id": node.id,
                "blob_id": blob.id,
                "revision_no": next_no,
                "origin": origin,
                "operation_id": operation.id,
                "size": size,
            }
        )
        node.write({"current_revision_id": revision.id, "size": size})
        fault.fault_point("revision_write_after_insert")

        result = {"node_id": node.id, "revision_id": revision.id, "sha256": sha256}
        operation.write({"result": result})
        self.env.cr.postcommit.add(lambda: _remove_if_exists(tmp_path))
        return result
