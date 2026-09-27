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
                # mail.thread's own creation-logging chatter message is not wanted for
                # every single file (volume, and it runs un-sudo'd - mail_thread.py
                # _message_log_batch/_notify_get_reply_to_batch - so it can fail on a
                # company/reply-to lookup this user has no reason to need for this).
                node = self.with_context(mail_create_nolog=True).create(
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

    def _lock_and_check_base_revision(self, node, base_revision_id):
        """Konzept 6 "Zeilen wartend sperren ... und Basisrevision pruefen"
        (shared by create_new_revision and restore_version): SET LOCAL
        lock_timeout + SELECT ... FOR UPDATE instead of lock_for_update()
        (A3: the latter is SKIP LOCKED and raises LockError immediately);
        LockNotAvailable propagates uncaught so retrying() retries the
        whole request (Konzept 6/19.17). Returns the node's current
        revision (possibly empty) as it stands AFTER the lock is held."""
        fault.fault_point("node_lock_before_wait")
        cr = self.env.cr
        cr.execute("SET LOCAL lock_timeout TO '5s'")
        cr.execute(
            SQL("SELECT id FROM int_filemanager_node WHERE id = %s FOR UPDATE", node.id)
        )
        node.invalidate_recordset(["current_revision_id"])

        current = node.current_revision_id
        if base_revision_id != (current.id or False):
            raise UserError(
                self.env._(
                    "This file changed since you loaded it; reload and try again."
                )
            )
        return current

    def _attach_revision(self, node, current, blob_id, size, origin, operation):
        """Creates the new revision and re-points current_revision_id,
        unless blob_id already matches the current one (no new revision at
        all then, Konzept 6). Shared by create_new_revision, restore_version
        and copy_node (which passes current=None: revision_no always starts
        at 1 for a brand-new node, nothing to compare against)."""
        if current and current.blob_id.id == blob_id:
            return {"node_id": node.id, "revision_id": current.id, "unchanged": True}

        next_no = (current.revision_no if current else 0) + 1
        revision = self.env["int_filemanager.revision"].create(
            {
                "node_id": node.id,
                "blob_id": blob_id,
                "revision_no": next_no,
                "origin": origin,
                "operation_id": operation.id,
                "size": size,
            }
        )
        node.write({"current_revision_id": revision.id, "size": size})
        return {"node_id": node.id, "revision_id": revision.id}

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

        current = self._lock_and_check_base_revision(node, base_revision_id)
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

        result = self._attach_revision(node, current, blob.id, size, origin, operation)
        result["sha256"] = sha256
        fault.fault_point("revision_write_after_insert")

        operation.write({"result": result})
        self.env.cr.postcommit.add(lambda: _remove_if_exists(tmp_path))
        return result

    @api.model
    def restore_version(self, node_id, revision_id, base_revision_id, operation_key):
        """Konzept 6 "Version wiederherstellen": a new revision on the OLD
        blob - no bytes copied, the blob is content-addressed and already
        on disk. Restoring the revision that is already current is the same
        no-op _attach_revision already gives create_new_revision."""
        operation, is_new = self.env["int_filemanager.operation"]._get_or_create(
            operation_key
        )
        if not is_new:
            return operation.result

        node = self.browse(node_id)
        node.check_access("write")

        old_revision = self.env["int_filemanager.revision"].browse(revision_id)
        old_revision.check_access("read")
        if old_revision.node_id.id != node.id:
            raise UserError(self.env._("This revision does not belong to this file."))

        current = self._lock_and_check_base_revision(node, base_revision_id)
        fault.fault_point("revision_write_before_check")

        result = self._attach_revision(
            node,
            current,
            old_revision.blob_id.id,
            old_revision.size,
            "restore",
            operation,
        )
        fault.fault_point("revision_write_after_insert")

        operation.write({"result": result})
        return result

    @api.model
    def copy_node(self, node_id, target_parent_id, new_name, operation_key):
        """Konzept 6 "Kopieren": a new node with a new revision on the SAME
        blob - no bytes copied. Runs the node create() (rights-checked,
        Konzept 6 "Rechte pruefen" first) before anything else, same
        ordering fix as create_file. revision_no always starts at 1 on the
        new node, so no lock/base-revision check is needed here (nobody
        else can know about a node that does not exist yet)."""
        operation, is_new = self.env["int_filemanager.operation"]._get_or_create(
            operation_key
        )
        if not is_new:
            return operation.result

        source = self.browse(node_id)
        source.check_access("read")
        if not source.current_revision_id:
            raise UserError(
                self.env._("This file has no content yet; nothing to copy.")
            )

        target_parent = self.browse(target_parent_id)
        scope_id = target_parent.scope_id.id

        try:
            with self.env.cr.savepoint():
                new_node = self.with_context(mail_create_nolog=True).create(
                    {
                        "name": new_name,
                        "parent_id": target_parent_id,
                        "scope_id": scope_id,
                        "is_dir": False,
                        "mime": source.mime,
                    }
                )
        except psycopg2.errors.UniqueViolation:
            raise UserError(
                self.env._(
                    "A file or folder named %(name)s already exists here.",
                    name=new_name,
                )
            ) from None

        result = self._attach_revision(
            new_node,
            None,
            source.current_revision_id.blob_id.id,
            source.current_revision_id.size,
            "restore",
            operation,
        )
        operation.write({"result": result})
        return result

    @api.model
    def rename_or_move(self, node_id, new_parent_id, new_name, operation_key):
        """Konzept 6 "Umbenennen, Verschieben": a pure node write, no disk
        operation at all (no blob touched, so none of the B2/B7 failure
        modes from the old module apply here). Moving into a different
        scope updates the whole subtree's scope_id in the same commit;
        moving into a scope this user cannot write to is checked against
        the DESTINATION parent explicitly (ir.rule only re-validates a
        write against the record's own scope, not a value being assigned
        to a related field)."""
        operation, is_new = self.env["int_filemanager.operation"]._get_or_create(
            operation_key
        )
        if not is_new:
            return operation.result

        node = self.browse(node_id)
        node.check_access("write")

        vals = {"name": new_name}
        new_scope_id = None
        if new_parent_id and new_parent_id != node.parent_id.id:
            new_parent = self.browse(new_parent_id)
            new_parent.check_access("write")
            vals["parent_id"] = new_parent_id
            if new_parent.scope_id != node.scope_id:
                new_scope_id = new_parent.scope_id.id
                vals["scope_id"] = new_scope_id

        fault.fault_point("node_lock_before_wait")
        cr = self.env.cr
        cr.execute("SET LOCAL lock_timeout TO '5s'")
        # LockNotAvailable propagates uncaught, same reasoning as create_new_revision.
        cr.execute(
            SQL("SELECT id FROM int_filemanager_node WHERE id = %s FOR UPDATE", node_id)
        )

        fault.fault_point("node_rename_before_check")
        try:
            with self.env.cr.savepoint():
                node.write(vals)
        except psycopg2.errors.UniqueViolation:
            raise UserError(
                self.env._(
                    "A file or folder named %(name)s already exists here.",
                    name=new_name,
                )
            ) from None

        if new_scope_id is not None:
            # write() above recomputed parent_path (its own _parent_store logic)
            # but this recordset's cached value predates that - refetch it.
            node.invalidate_recordset(["parent_path"])
            # Whole subtree moves scope together, in this same commit (Konzept 6);
            # node's own row is included (harmless no-op re-write of what write()
            # above already set) since parent_path always starts with itself.
            cr.execute(
                SQL(
                    "UPDATE int_filemanager_node SET scope_id = %s"
                    " WHERE parent_path LIKE %s",
                    new_scope_id,
                    f"{node.parent_path}%",
                )
            )
            self.invalidate_model(["scope_id"])

        result = {"node_id": node.id}
        operation.write({"result": result})
        return result

    @api.model
    def trash(self, node_id, operation_key):
        """Konzept 6 "Loeschen": active=False + removal_reason='trash' over
        the WHOLE subtree - never just the node itself, or its children
        would keep showing up active under a parent that no longer does.
        Only descendants this user can already see are included (plain
        search(), no sudo - I7); child_of also matches node_id itself."""
        operation, is_new = self.env["int_filemanager.operation"]._get_or_create(
            operation_key
        )
        if not is_new:
            return operation.result

        node = self.browse(node_id)
        node.check_access("write")

        subtree = self.search([("id", "child_of", node_id)])
        subtree.write({"active": False, "removal_reason": "trash"})

        result = {"node_id": node.id}
        operation.write({"result": result})
        return result

    @api.model
    def restore(self, node_id, operation_key):
        """Konzept 6 "Wiederherstellen": active=True over the trashed
        subtree; a name collision in the target folder is a UserError, not
        an automatic rename."""
        operation, is_new = self.env["int_filemanager.operation"]._get_or_create(
            operation_key
        )
        if not is_new:
            return operation.result

        node = self.browse(node_id)
        node.check_access("write")

        subtree = self.with_context(active_test=False).search(
            [("id", "child_of", node_id)]
        )
        try:
            with self.env.cr.savepoint():
                subtree.write({"active": True, "removal_reason": False})
        except psycopg2.errors.UniqueViolation:
            raise UserError(
                self.env._(
                    "Restoring would collide with an existing file or folder"
                    " of the same name."
                )
            ) from None

        result = {"node_id": node.id}
        operation.write({"result": result})
        return result

    @api.model
    def delete_permanently(self, node_id, operation_key):
        """Konzept 6 "Endgueltig loeschen": rows only - the blob a deleted
        revision pointed to is swept later by the cleanup job once nothing
        references it any more (I4), never deleted here directly. Clearing
        current_revision_id first breaks its own ondelete=restrict link to
        revision before the cascade delete, rather than relying on unlink()
        ordering its own cascade simulation the same way."""
        operation, is_new = self.env["int_filemanager.operation"]._get_or_create(
            operation_key
        )
        if not is_new:
            return operation.result

        node = self.browse(node_id)
        node.check_access("unlink")

        subtree = self.with_context(active_test=False).search(
            [("id", "child_of", node_id)]
        )
        subtree.write({"current_revision_id": False})
        subtree.unlink()

        result = {"node_id": node_id}
        operation.write({"result": result})
        return result
