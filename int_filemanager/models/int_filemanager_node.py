import io
import logging
import os
import re
import unicodedata
import uuid
from datetime import timedelta

import psycopg2

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools import SQL
from odoo.tools.mimetypes import guess_mimetype

from .. import blobstore, fault

_logger = logging.getLogger(__name__)


# Days a node stays in the trash before it is deleted for good.
DEFAULT_TRASH_RETENTION_DAYS = 30
TRASH_RETENTION_PARAM = "int_filemanager.trash_retention_days"

# A name never carries a path: "/" and "\\" would make it one. The rest is what Windows
# refuses, so that an export or a network drive works for every name in the tree.
_INVALID_NAME_CHARS = re.compile(r'[\x00-\x1f<>:"/\\|?*]')
_WINDOWS_RESERVED_NAME = re.compile(r"(con|prn|aux|nul|(com|lpt)[0-9¹²³])(\..*)?", re.I)


def _remove_if_exists(path):
    try:
        os.remove(path)
    except OSError:
        _logger.warning(
            "could not remove temp file %s after commit", path, exc_info=True
        )


class IntFilemanagerNode(models.Model):
    """A folder or a file. The content lives in its revisions and their
    blobs; the node carries identity, position in the tree and rights."""

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
    # Float, not Integer: an int4 column overflows for files above 2 GiB.
    size = fields.Float()
    mime = fields.Char()
    tag_ids = fields.Many2many(
        "int_filemanager.tag",
        "int_filemanager_node_tag_rel",
        "node_id",
        "tag_id",
        string="Tags",
    )
    status_id = fields.Many2one("int_filemanager.status", ondelete="set null")
    status_color = fields.Integer(related="status_id.color")
    partner_id = fields.Many2one("res.partner", ondelete="set null", index=True)
    revision_ids = fields.One2many("int_filemanager.revision", "node_id")
    # Portal contacts who may download this file from /my/files, independent of any
    # link. The portal routes check membership explicitly; portal users have no rights
    # on the node model itself.
    shared_partner_ids = fields.Many2many(
        "res.partner",
        "int_filemanager_node_shared_partner_rel",
        "node_id",
        "partner_id",
        string="Shared with",
    )
    # Set by trash() for the whole subtree; the trash purge counts from it.
    trashed_at = fields.Datetime(index=True)

    # Names are unique per folder regardless of case, like on Windows. NULLS NOT
    # DISTINCT: otherwise two roots (parent_id IS NULL) would never collide.
    _unique_name_per_parent = models.UniqueIndex(
        '(parent_id, lower(name COLLATE "und-x-icu")) NULLS NOT DISTINCT WHERE active',
        "A file or folder with this name already exists here.",
    )

    # When the content last changed (the current revision's creation), what the file
    # list shows as "modified"; write_date would also move on a tag or status edit.
    mtime = fields.Datetime(related="current_revision_id.create_date", store=True)
    # Active links only; created and revoked through int_filemanager.share methods.
    share_ids = fields.One2many(
        "int_filemanager.share", "node_id", domain=[("revoked_at", "=", False)]
    )

    # A root, or a folder whose rights scope differs from its parent's: the places where
    # a user's access can begin. Kept as a stored flag so that "what is the top of this
    # user's tree" only has to look at these few rows, not at every node.
    is_scope_root = fields.Boolean(
        compute="_compute_is_scope_root", store=True, index=True
    )
    # True for what the caller sees at the top of the tree: a real root, or a scope root
    # whose parent the caller cannot read (a scope that starts below the real root).
    # Searchable, so the explorer's "nothing selected" view is one plain domain.
    is_visible_top = fields.Boolean(
        compute="_compute_is_visible_top", search="_search_is_visible_top"
    )

    @api.depends("parent_id", "scope_id", "parent_id.scope_id")
    def _compute_is_scope_root(self):
        for node in self:
            node.is_scope_root = (
                not node.parent_id or node.parent_id.scope_id != node.scope_id
            )

    @api.model
    def _readable_scope_ids(self):
        Scope = self.env["int_filemanager.scope"].sudo()
        groups = self.env.user.all_group_ids.ids
        return Scope.search([("read_group_ids", "in", groups)]).ids

    @api.depends_context("uid")
    def _compute_is_visible_top(self):
        readable = set(self._readable_scope_ids())
        for node in self:
            node.is_visible_top = (
                not node.parent_id or node.parent_id.sudo().scope_id.id not in readable
            )

    def _search_is_visible_top(self, operator, value):
        if operator not in ("=", "!=") or not isinstance(value, bool):
            raise UserError(self.env._("Unsupported search on the top of the tree."))
        # Raw SQL below: what the ORM still holds back must reach the database first.
        self.flush_model()
        cr = self.env.cr
        cr.execute(
            SQL(
                """
                SELECT n.id FROM int_filemanager_node n
                LEFT JOIN int_filemanager_node p ON p.id = n.parent_id
                WHERE n.is_scope_root
                  AND (n.parent_id IS NULL OR p.scope_id <> ALL(%s))
                """,
                self._readable_scope_ids() or [0],
            )
        )
        top_ids = [row[0] for row in cr.fetchall()]
        # search() applies the caller's rights on top of this list of candidates.
        return [("id", "in" if (operator == "=") == value else "not in", top_ids)]

    @api.model
    def tree_children(self, parent_id):
        """Return the visible sub-folders of ``parent_id`` for the sidebar tree.

        Without ``parent_id``, return the top of what the caller can see. One level
        per call, so the cost depends on the opened level, not on the whole tree.
        """
        level = (
            [("parent_id", "=", parent_id)]
            if parent_id
            else [("is_visible_top", "=", True)]
        )
        folders = self.search([*level, ("is_dir", "=", True)])
        with_children = set()
        if folders:
            grouped = self._read_group(
                [("parent_id", "in", folders.ids), ("is_dir", "=", True)],
                ["parent_id"],
                ["__count"],
            )
            with_children = {parent.id for parent, _count in grouped}
        return [
            {"id": f.id, "name": f.name, "has_children": f.id in with_children}
            for f in sorted(folders, key=lambda f: f.name.casefold())
        ]

    @api.model
    def breadcrumb(self, node_id):
        """Return ``[{id, name}]`` from the topmost visible folder down to the node.

        Ancestors the caller cannot read are left out, not revealed.
        """
        node = self.browse(node_id).exists()
        if not node:
            return []
        node.check_access("read")
        ids = [int(i) for i in node.parent_path.split("/") if i]
        visible = self.with_context(active_test=False).search([("id", "in", ids)])
        names = {n.id: n.name for n in visible}
        return [{"id": i, "name": names[i]} for i in ids if i in names]

    @api.model
    def existing_names(self, parent_id, names):
        """Return which of ``names`` are already taken below ``parent_id``.

        Compared like the unique index (case-insensitive, NFC). The SQL query only
        finds candidates; search() then applies the caller's rights.
        """
        names = [unicodedata.normalize("NFC", n) for n in names or []]
        if not names:
            return []
        if parent_id:
            self.browse(parent_id).check_access("read")
        self.flush_model()
        cr = self.env.cr
        cr.execute(
            SQL(
                """
                SELECT id FROM int_filemanager_node
                WHERE parent_id IS NOT DISTINCT FROM %s AND active
                  AND lower(name COLLATE "und-x-icu") IN (
                      SELECT lower(x COLLATE "und-x-icu") FROM unnest(%s::text[]) AS x
                  )
                """,
                parent_id or None,
                names,
            )
        )
        found = self.search([("id", "in", [row[0] for row in cr.fetchall()])])
        return [
            {
                "id": n.id,
                "name": n.name,
                "is_dir": n.is_dir,
                "current_revision_id": n.current_revision_id.id or False,
            }
            for n in found
        ]

    def action_restore(self):
        """Restore the selected nodes from the trash."""
        for node in self:
            self.restore(node.id, f"ui-restore-{uuid.uuid4().hex}")
        return True

    def action_delete_permanently(self):
        """Delete the selected nodes for good; needs the purge right."""
        for node in self:
            self.delete_permanently(node.id, f"ui-delete-{uuid.uuid4().hex}")
        return True

    def action_create_share_link(self):
        """Create a share link for this file."""
        self.ensure_one()
        self.env["int_filemanager.share"].create_link(self.id)
        return True

    def _display_path(self):
        """Return the node's path, e.g. ``/root/sub/file.txt``, for logs and messages.

        Ancestors are read with sudo: the caller may not be allowed to read them.
        """
        self.ensure_one()
        ids = [int(i) for i in (self.parent_path or "").split("/") if i]
        return "/" + "/".join(self.sudo().browse(ids).mapped("name"))

    @api.model
    def _clean_name(self, name):
        """Normalize and validate a file or folder name.

        NFC, so that "e" + combining accent and the precomposed letter cannot exist
        side by side as two different names.
        """
        name = unicodedata.normalize("NFC", name or "").strip()
        if not name or name in (".", ".."):
            raise UserError(self.env._("This is not a valid file or folder name."))
        if (
            _INVALID_NAME_CHARS.search(name)
            or name.endswith(".")
            or _WINDOWS_RESERVED_NAME.fullmatch(name)
        ):
            raise UserError(
                self.env._(
                    'A name must not contain / \\ : * ? " < > | or control characters, '
                    "end with a dot, or be a reserved Windows name such as CON, NUL "
                    "or COM1 (with or without an extension)."
                )
            )
        return name

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if "name" in vals:
                vals["name"] = self._clean_name(vals["name"])
        return super().create(vals_list)

    def write(self, vals):
        if "name" in vals:
            vals = dict(vals, name=self._clean_name(vals["name"]))
        return super().write(vals)

    @api.model
    def create_file(self, parent_id, name, content, operation_key):
        """Create a file from content small enough for one request.

        The node is created first, as the calling user, so the record rules
        reject a denied request before anything reaches the blob store. A name
        collision raises instead of replacing the existing file.
        """
        operation, is_new = self.env["int_filemanager.operation"]._get_or_create(
            operation_key
        )
        if not is_new:
            return operation.result

        content = blobstore.decode_content(content)
        parent = self.browse(parent_id)
        scope_id = parent.scope_id.id

        fault.fault_point("node_create_before_check")
        try:
            with self.env.cr.savepoint():
                # No "created" chatter message per file: too many of them, and it
                # can fail on a reply-to lookup the user has no rights for.
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
        self._touch_active_parent(parent)

        tmp_path = blobstore.write_stream_to_temp(
            self.env, io.BytesIO(content), f"create_{operation.id}"
        )
        sha256, size = blobstore.hash_file(tmp_path)
        blobstore.adopt_hashed(self.env, tmp_path, sha256, keep_tmp=True)

        # Blobs have no user rights at all; sudo() is safe here because the node
        # create() above already checked the caller against the scope.
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
        # The blob is already linked under its hash; the temp file goes only once
        # the transaction has committed (postcommit does not run on rollback).
        self.env.cr.postcommit.add(lambda: _remove_if_exists(tmp_path))
        return result

    def _touch_active_parent(self, parent):
        """Write the target folder's row before putting something below it.

        Trashing the folder writes the same row, so the two operations conflict
        and the later one is retried, instead of both committing under
        REPEATABLE READ and leaving an active node below a trashed folder.
        Bypasses record rules: call it only after the rights were checked.
        """
        if not parent:
            return
        if not parent.is_dir:
            raise UserError(self.env._("The target is not a folder."))
        cr = self.env.cr
        cr.execute("SET LOCAL lock_timeout TO '5s'")
        cr.execute(
            SQL(
                "UPDATE int_filemanager_node"
                " SET write_date = (now() AT TIME ZONE 'utc')"
                " WHERE id = %s AND active RETURNING id",
                parent.id,
            )
        )
        if not cr.fetchone():
            raise UserError(
                self.env._("The target folder is in the trash; restore it first.")
            )

    @api.model
    def create_folder(self, parent_id, name, operation_key):
        """Create a folder below ``parent_id``."""
        operation, is_new = self.env["int_filemanager.operation"]._get_or_create(
            operation_key
        )
        if not is_new:
            return operation.result

        parent = self.browse(parent_id)
        try:
            with self.env.cr.savepoint():
                node = self.with_context(mail_create_nolog=True).create(
                    {
                        "name": name,
                        "parent_id": parent_id,
                        "scope_id": parent.scope_id.id,
                        "is_dir": True,
                    }
                )
        except psycopg2.errors.UniqueViolation:
            raise UserError(
                self.env._(
                    "A file or folder named %(name)s already exists here.", name=name
                )
            ) from None
        self._touch_active_parent(parent)

        result = {"node_id": node.id}
        operation.write({"result": result})
        return result

    def _lock_and_check_base_revision(self, node, base_revision_id):
        """Lock the node and check it did not change since ``base_revision_id``.

        Waits for the lock: lock_for_update() skips locked rows and fails at
        once. A lock timeout propagates so that the request is retried.
        Returns the current revision as seen under the lock.
        """
        fault.fault_point("node_lock_before_wait")
        cr = self.env.cr
        cr.execute("SET LOCAL lock_timeout TO '5s'")
        cr.execute(
            SQL("SELECT id FROM int_filemanager_node WHERE id = %s FOR UPDATE", node.id)
        )
        fault.fault_point("node_lock_acquired")
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
        """Add a revision on ``blob_id`` and make it current.

        Does nothing if ``blob_id`` is already the current content. ``current``
        is None for a new node.
        """
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
        """Store new content for a file as a new revision.

        ``base_revision_id`` is the revision the caller started from; if the file
        changed since, this raises instead of silently overwriting. The same
        content as the current revision adds nothing.
        """
        operation, is_new = self.env["int_filemanager.operation"]._get_or_create(
            operation_key
        )
        if not is_new:
            return operation.result

        content = blobstore.decode_content(content)
        node = self.browse(node_id)
        node.check_access("write")

        current = self._lock_and_check_base_revision(node, base_revision_id)
        fault.fault_point("revision_write_before_check")

        tmp_path = blobstore.write_stream_to_temp(
            self.env, io.BytesIO(content), f"revise_{operation.id}"
        )
        sha256, size = blobstore.hash_file(tmp_path)

        # sudo() only to read the blob's hash; the node's rights were checked above.
        if current and current.sudo().blob_id.sha256 == sha256:
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
        """Make an old revision current again, as a new revision on its blob."""
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
        """Copy a file or folder to ``target_parent_id`` as ``new_name``.

        The copies point to the same blobs, no bytes are copied. A folder is
        copied with everything below it that the caller can see.
        """
        operation, is_new = self.env["int_filemanager.operation"]._get_or_create(
            operation_key
        )
        if not is_new:
            return operation.result

        source = self.browse(node_id)
        source.check_access("read")
        if not source.is_dir and not source.current_revision_id:
            raise UserError(
                self.env._("This file has no content yet; nothing to copy.")
            )

        target_parent = self.browse(target_parent_id)
        if source.is_dir and target_parent.parent_path.startswith(source.parent_path):
            raise UserError(self.env._("A folder cannot be copied into itself."))
        scope_id = target_parent.scope_id.id

        try:
            with self.env.cr.savepoint():
                new_node = self.with_context(mail_create_nolog=True).create(
                    self._copy_vals(source, new_name, target_parent_id, scope_id)
                )
        except psycopg2.errors.UniqueViolation:
            raise UserError(
                self.env._(
                    "A file or folder named %(name)s already exists here.",
                    name=new_name,
                )
            ) from None
        self._touch_active_parent(target_parent)

        result = self._attach_copy_content(source, new_node, operation)
        if source.is_dir:
            copied = self._copy_children(source, new_node, scope_id, operation)
            result = {"node_id": new_node.id, "copied": copied + 1}
        operation.write({"result": result})
        return result

    @api.model
    def _copy_vals(self, source, name, parent_id, scope_id):
        return {
            "name": name,
            "parent_id": parent_id,
            "scope_id": scope_id,
            "is_dir": source.is_dir,
            "mime": source.mime,
            "tag_ids": [(6, 0, source.tag_ids.ids)],
            "status_id": source.status_id.id,
            "partner_id": source.partner_id.id,
        }

    def _attach_copy_content(self, source, new_node, operation):
        if source.is_dir or not source.current_revision_id:
            return {"node_id": new_node.id}
        return self._attach_revision(
            new_node,
            None,
            source.current_revision_id.blob_id.id,
            source.current_revision_id.size,
            "restore",
            operation,
        )

    def _copy_children(self, source, new_top, scope_id, operation):
        """Copy what the caller can see below ``source`` into ``new_top``.

        Parents come before their children, so every new parent exists in time.
        """
        mapping = {source.id: new_top.id}
        copied = 0
        descendants = self.search(
            [("id", "child_of", source.id), ("id", "!=", source.id)],
            order="parent_path",
        )
        for old in descendants:
            new_parent_id = mapping.get(old.parent_id.id)
            if not new_parent_id:
                continue  # parent was not visible to the caller, so neither is this
            new = self.with_context(mail_create_nolog=True).create(
                self._copy_vals(old, old.name, new_parent_id, scope_id)
            )
            mapping[old.id] = new.id
            self._attach_copy_content(old, new, operation)
            copied += 1
        return copied

    @api.model
    def rename_or_move(self, node_id, new_parent_id, new_name, operation_key):
        """Rename a node and/or move it below ``new_parent_id``.

        Only rows change, no file is touched. Moving into another scope moves
        the whole subtree along. The write right on the destination is checked
        explicitly: record rules only check the node's current scope.
        """
        operation, is_new = self.env["int_filemanager.operation"]._get_or_create(
            operation_key
        )
        if not is_new:
            return operation.result

        node = self.browse(node_id)
        node.check_access("write")

        vals = {"name": new_name}
        new_scope_id = None
        new_parent = self.browse()
        if new_parent_id and new_parent_id != node.parent_id.id:
            new_parent = self.browse(new_parent_id)
            new_parent.check_access("write")
            if new_parent.parent_path.startswith(node.parent_path):
                raise UserError(self.env._("A folder cannot be moved into itself."))
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
        fault.fault_point("node_lock_acquired")
        if not node.active:
            raise UserError(
                self.env._("This item is in the trash; restore it before moving it.")
            )

        fault.fault_point("node_rename_before_check")
        fault.fault_point("node_tree_before_write")
        self._touch_active_parent(new_parent)
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
            # The whole subtree, the node included, changes scope in this transaction.
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
        """Move a node and everything visible below it to the trash."""
        operation, is_new = self.env["int_filemanager.operation"]._get_or_create(
            operation_key
        )
        if not is_new:
            return operation.result

        node = self.browse(node_id)
        node.check_access("write")

        subtree = self.search([("id", "child_of", node_id)])
        fault.fault_point("node_tree_before_write")
        subtree.write(
            {
                "active": False,
                "removal_reason": "trash",
                "trashed_at": fields.Datetime.now(),
            }
        )

        result = {"node_id": node.id}
        operation.write({"result": result})
        return result

    @api.model
    def restore(self, node_id, operation_key):
        """Restore a node and its subtree from the trash.

        A name collision raises instead of renaming automatically.
        """
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
        fault.fault_point("node_tree_before_write")
        # Restoring under a folder that is still in the trash would leave an active
        # node below an inactive one - same rule (and same row conflict) as moving
        # into it.
        self._touch_active_parent(node.parent_id)
        try:
            with self.env.cr.savepoint():
                subtree.write(
                    {"active": True, "removal_reason": False, "trashed_at": False}
                )
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
        """Delete a node and its subtree for good.

        Only rows are deleted; the blob cleanup job removes the content later,
        once nothing refers to it any more.
        """
        operation, is_new = self.env["int_filemanager.operation"]._get_or_create(
            operation_key
        )
        if not is_new:
            return operation.result

        node = self.browse(node_id)
        node.check_access("unlink")

        self._unlink_subtree(node)

        result = {"node_id": node_id}
        operation.write({"result": result})
        return result

    @api.model
    def _unlink_subtree(self, root):
        subtree = self.with_context(active_test=False).search(
            [("id", "child_of", root.id)]
        )
        # current_revision_id is ondelete=restrict: clear it before the delete.
        subtree.write({"current_revision_id": False})
        subtree.unlink()
        return len(subtree)

    @api.model
    def _trash_retention_days(self):
        return int(
            self.env["ir.config_parameter"]
            .sudo()
            .get_param(TRASH_RETENTION_PARAM, DEFAULT_TRASH_RETENTION_DAYS)
        )

    @api.model
    def _expired_trash_roots(self):
        """Return the top nodes of trashed subtrees older than the retention."""
        cutoff = fields.Datetime.now() - timedelta(days=self._trash_retention_days())
        expired = self.with_context(active_test=False).search(
            [("removal_reason", "=", "trash"), ("trashed_at", "<", cutoff)]
        )
        return expired.filtered(lambda n: n.parent_id not in expired)

    @api.model
    def _purge_expired_trash(self, limit=200):
        """Delete trashed subtrees older than the retention; return how many.

        One savepoint per subtree, so one that fails does not block the others.
        """
        purged = 0
        for root in self._expired_trash_roots()[:limit]:
            try:
                with self.env.cr.savepoint():
                    self._unlink_subtree(root)
                purged += 1
            except Exception:
                _logger.exception("could not purge trashed node %s", root.id)
        return purged

    @api.model
    def _cron_purge_trash(self):
        self._purge_expired_trash()
