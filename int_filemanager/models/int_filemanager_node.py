import io
import logging
import os
import re
import unicodedata
import uuid
from collections import defaultdict
from datetime import timedelta

import psycopg2

from odoo import Command, api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Domain
from odoo.tools import SQL, escape_psql
from odoo.tools.mimetypes import guess_mimetype

# fault: test hooks of the write paths (see its docstring); a no-op in production.
from .. import blobstore, fault, params
from .. import derivative_plan as plan
from . import int_filemanager_derivative as derivative

_logger = logging.getLogger(__name__)


# Days a node stays in the trash before it is deleted for good.
DEFAULT_TRASH_RETENTION_DAYS = 30
TRASH_RETENTION_PARAM = "int_filemanager.trash_retention_days"
# Expired trash subtrees one run of the purge job deletes.
TRASH_PURGE_BATCH = 200

# How long a write path waits for a row another request holds before it gives up and
# the request is retried.
LOCK_TIMEOUT = "5s"

# Fields that carry rights, position, content or the trash purge time. The record
# rules only look at where a node is now, so these change through the model methods,
# which check the rights on both ends, never through a plain write().
SERVER_ONLY_FIELDS = frozenset(
    {
        "scope_id",
        "parent_id",
        "current_revision_id",
        "size",
        "mime",
        "review_state",
        "active",
        "removal_reason",
        "trashed_at",
    }
)

# Where the content of a new revision may come from when a client says so; the other
# origins are set by the server paths that really are that origin.
CLIENT_REVISION_ORIGINS = ("upload", "edit")

# A name never carries a path: "/" and "\\" would make it one. The rest is what Windows
# refuses, so that an export or a network drive works for every name in the tree.
_INVALID_NAME_CHARS = re.compile(r'[\x00-\x1f<>:"/\\|?*]')
_WINDOWS_RESERVED_NAME = re.compile(r"(con|prn|aux|nul|(com|lpt)[0-9¹²³])(\..*)?", re.I)

# Words of a content search, and their length.
MAX_SEARCH_TERMS = 10
MAX_SEARCH_TERM_CHARS = 100
# Names one availability check may carry.
MAX_CHECKED_NAMES = 10000

PREVIEW_STATES = [
    ("ready", "Ready"),
    ("pending", "Pending"),
    ("failed", "Failed"),
    ("none", "None"),
]


def _remove_if_exists(path):
    try:
        os.remove(path)
    except OSError:
        _logger.warning(
            "could not remove temp file %s after commit", path, exc_info=True
        )


class IntFilemanagerNode(models.Model):
    """A folder or a file: its place in the tree and its rights.

    The content lives in the revisions and their blobs.
    """

    _name = "int_filemanager.node"
    _description = "Filemanager node (folder or file)"
    _inherit = ["mail.thread", "int_filemanager.value_recognition"]
    _parent_store = True
    _order = "parent_path"

    name = fields.Char(required=True)
    parent_id = fields.Many2one("int_filemanager.node", index=True, ondelete="restrict")
    parent_path = fields.Char(index=True)
    is_dir = fields.Boolean()
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
    # Values read from the document and confirmed by a user, one per field.
    field_value_ids = fields.One2many("int_filemanager.field_value", "node_id")
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
    # Whether someone looked at the values found in the file; set by apply_field_values.
    review_state = fields.Selection(
        [
            ("unreviewed", "Not reviewed"),
            ("reviewed", "Reviewed"),
            ("automatic", "Applied automatically"),
        ],
        default="unreviewed",
        copy=False,
        index=True,
    )
    # Thumbnail and large preview image. Only the states: the explorer builds the
    # picture URLs from the revision itself.
    preview_state = fields.Selection(PREVIEW_STATES, compute="_compute_preview_states")
    full_preview_state = fields.Selection(
        PREVIEW_STATES, compute="_compute_preview_states"
    )
    # The values found in the file, for the properties form: reading gives the answer of
    # suggest_field_values, writing {"revision_id", "edits"} confirms values through
    # apply_field_values. Never stored, so the form saves it like any other field.
    values_json = fields.Json(
        string="Values",
        compute="_compute_values_json",
        inverse="_inverse_values_json",
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
    # Searchable only: the text read from the document (see the derivative's ``text``).
    # It is never handed out, not even to someone who found the file by it.
    content = fields.Char(compute="_compute_content", search="_search_content")

    # Names are unique per folder regardless of case, like on Windows. NULLS NOT
    # DISTINCT: otherwise two roots (parent_id IS NULL) would never collide.
    _unique_name_per_parent = models.UniqueIndex(
        '(parent_id, lower(name COLLATE "und-x-icu")) NULLS NOT DISTINCT WHERE active',
        "A file or folder with this name already exists here.",
    )

    # The state of a job is no dependency: the converter changes it without the node.
    @api.depends("is_dir", "name", "current_revision_id.blob_id")
    def _compute_preview_states(self):
        # sudo(): revisions, blobs and jobs have no user rights; the node was readable.
        blobs = self.sudo().current_revision_id.blob_id
        # Only the columns that are needed: a job row can carry a long text.
        jobs = (
            self.env["int_filemanager.derivative"]
            .sudo()
            .search_fetch(
                [("source_blob_id", "in", blobs.ids)],
                ["source_blob_id", "kind", "state"],
            )
        )
        states = {(job.source_blob_id.id, job.kind): job.state for job in jobs}
        for node in self:
            blob = node.sudo().current_revision_id.blob_id
            file_like = not node.is_dir and blob
            for field_name, kind in (
                ("preview_state", "tile" if plan.has_tile(node.name) else None),
                ("full_preview_state", plan.full_preview_kind(node.name)),
            ):
                state = states.get((blob.id, kind))
                if not file_like or kind is None or state == "not_applicable":
                    node[field_name] = "none"
                elif state == "done":
                    node[field_name] = "ready"
                elif state == "failed":
                    node[field_name] = "failed"
                else:
                    # No row yet: the cron has not queued it, but it will.
                    node[field_name] = "pending"

    # Not the contact or the stored values: the form keeps the edits that are not saved
    # yet in this field, and an answer read again would wipe them.
    @api.depends("is_dir", "current_revision_id")
    def _compute_values_json(self):
        # A field is also computed for the nodes read along with the asked one (the
        # prefetch), and those may be nodes the caller cannot read.
        readable = self.filtered(lambda n: isinstance(n.id, int))._filtered_access(
            "read"
        )
        shared = self._recognition_shared()
        for node in self:
            answer = False
            if node in readable and not node.is_dir:
                try:
                    answer = self._suggest_values(node, [], shared)
                except (re.error, ValueError, OSError):
                    # A broken rule or word list: the form is still worth opening.
                    _logger.exception("could not read the values of node %s", node.id)
            node.values_json = answer

    def _inverse_values_json(self):
        for node in self:
            payload = node.values_json or {}
            if payload.get("edits"):
                self.apply_field_values(
                    node.id, payload.get("revision_id"), payload["edits"]
                )

    @api.depends("parent_id", "scope_id", "parent_id.scope_id")
    def _compute_is_scope_root(self):
        for node in self:
            node.is_scope_root = (
                not node.parent_id or node.parent_id.scope_id != node.scope_id
            )

    @api.depends("parent_id.scope_id")
    @api.depends_context("uid")
    def _compute_is_visible_top(self):
        readable = set(self._readable_scope_ids())
        for node in self:
            # sudo(): the parent's scope is compared with the readable ones, not shown.
            node.is_visible_top = (
                not node.parent_id or node.parent_id.sudo().scope_id.id not in readable
            )

    def _search_is_visible_top(self, operator, value):
        if operator not in ("=", "!=") or not isinstance(value, bool):
            raise UserError(self.env._("Unsupported search on the top of the tree."))
        top_ids = [
            row[0]
            for row in self.env.execute_query(
                SQL(
                    """
                    SELECT n.id FROM int_filemanager_node n
                    LEFT JOIN int_filemanager_node p ON p.id = n.parent_id
                    WHERE n.is_scope_root
                      AND (n.parent_id IS NULL OR p.scope_id <> ALL(%s))
                    """,
                    self._readable_scope_ids() or [0],
                    to_flush=[
                        self._fields["parent_id"],
                        self._fields["scope_id"],
                        self._fields["is_scope_root"],
                    ],
                )
            )
        ]
        # search() applies the caller's rights on top of this list of candidates.
        return Domain("id", "in" if (operator == "=") == value else "not in", top_ids)

    @api.depends()
    def _compute_content(self):
        self.content = False

    def _search_content(self, operator, value):
        """Return the domain of the files whose read text has every word of ``value``.

        Only the current revision counts. The text is read as the superuser, but the
        caller's rights on the node narrow the hits down like for any other field.
        """
        if operator not in ("ilike", "not ilike"):
            raise UserError(self.env._("The content can only be searched for words."))
        terms = str(value or "").split()
        if len(terms) > MAX_SEARCH_TERMS or any(
            len(term) > MAX_SEARCH_TERM_CHARS for term in terms
        ):
            raise UserError(
                self.env._("The content search has too many or too long words.")
            )
        if not terms:
            return Domain.TRUE if operator == "ilike" else Domain.FALSE
        # sudo(): the read texts have no user rights; only a list of hits leaves here.
        texts = (
            self.env["int_filemanager.derivative"]
            .sudo()
            ._search(
                [
                    ("kind", "in", ("text", "words")),
                    ("state", "=", "done"),
                    *(("text", "ilike", escape_psql(term)) for term in terms),
                ]
            )
        )
        found = Domain(
            "current_revision_id.blob_id", "in", texts.subselect("source_blob_id")
        )
        return found if operator == "ilike" else ~found

    def _has_field_access(self, field, operation):
        """Allow writing the server-only fields to the server alone."""
        if (
            operation == "write"
            and field.name in SERVER_ONLY_FIELDS
            and not self.env.su
        ):
            return False
        return super()._has_field_access(field, operation)

    @api.model_create_multi
    def create(self, vals_list):
        return super().create(
            [
                dict(vals, name=self._clean_name(vals["name"]))
                if "name" in vals
                else vals
                for vals in vals_list
            ]
        )

    def write(self, vals):
        if "name" in vals:
            vals = dict(vals, name=self._clean_name(vals["name"]))
        return super().write(vals)

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

    @api.model
    def request_previews(self, node_ids):
        """Move the thumbnails of the nodes on screen to the front of the queue.

        Does not wait for them: the explorer shows an icon until they exist.
        """
        if not isinstance(node_ids, list | tuple):
            return 0
        ids = [i for i in node_ids if type(i) is int][: derivative.MAX_REQUESTED_NODES]
        # search() applies the caller's rights; the queue itself needs sudo.
        nodes = self.search([("id", "in", ids), ("is_dir", "=", False)])
        blobs = nodes.sudo().current_revision_id.blob_id
        jobs = (
            self.env["int_filemanager.derivative"]
            .sudo()
            .search([("source_blob_id", "in", blobs.ids), ("state", "=", "pending")])
        )
        jobs.write({"priority": derivative.VISIBLE_PRIORITY})
        return len(jobs)

    @api.model
    def _readable_scope_ids(self):
        """Return the ids of the scopes the caller may read."""
        # sudo(): the caller has no right on the scope list, only the ids come back.
        Scope = self.env["int_filemanager.scope"].sudo()
        groups = self.env.user.all_group_ids.ids
        return Scope.search([("read_group_ids", "in", groups)]).ids

    @api.model
    @api.readonly
    def tree_children(self, parent_id):
        """Return the visible sub-folders of ``parent_id`` for the sidebar tree.

        Without ``parent_id``, return the top of what the caller can see. One level
        per call, so the cost depends on the opened level, not on the whole tree.
        """
        parent_id = params.optional_id(self.env, parent_id, "parent_id")
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
            for f in folders.sorted(lambda f: f.name.casefold())
        ]

    @api.model
    @api.readonly
    def breadcrumb(self, node_id):
        """Return ``[{id, name}]`` from the topmost visible folder down to the node.

        Ancestors the caller cannot read are left out, not revealed.
        """
        node = self.browse(params.require_id(self.env, node_id, "node_id")).exists()
        if not node:
            return []
        node.check_access("read")
        ids = [int(i) for i in node.parent_path.split("/") if i]
        visible = self.with_context(active_test=False).search([("id", "in", ids)])
        names = {n.id: n.name for n in visible}
        return [{"id": i, "name": names[i]} for i in ids if i in names]

    @api.model
    @api.readonly
    def existing_names(self, parent_id, names):
        """Return which of ``names`` are already taken below ``parent_id``.

        Compared like the unique index (case-insensitive, NFC). The SQL query only
        finds candidates; search() then applies the caller's rights.
        """
        parent_id = params.optional_id(self.env, parent_id, "parent_id")
        if (
            not isinstance(names, list | tuple)
            or len(names) > MAX_CHECKED_NAMES
            or not all(isinstance(n, str) for n in names)
        ):
            raise UserError(self.env._("%(argument)s is not valid.", argument="names"))
        names = [unicodedata.normalize("NFC", n) for n in names]
        if not names:
            return []
        if parent_id:
            self.browse(parent_id).check_access("read")
        rows = self.env.execute_query(
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
                to_flush=[
                    self._fields["parent_id"],
                    self._fields["active"],
                    self._fields["name"],
                ],
            )
        )
        found = self.search([("id", "in", [row[0] for row in rows])])
        return [
            {
                "id": n.id,
                "name": n.name,
                "is_dir": n.is_dir,
                "current_revision_id": n.current_revision_id.id or False,
            }
            for n in found
        ]

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
        name = unicodedata.normalize("NFC", name if isinstance(name, str) else "")
        name = name.strip()
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

    @api.model
    def _require_node(self, node_id, argument):
        """Return the node with the id the client sent, which must be an id at all."""
        return self.browse(params.require_id(self.env, node_id, argument))

    @api.model
    def _create_below(self, parent, vals):
        """Create a node below ``parent`` in its scope, once the caller may write there.

        Users have no create right on nodes: the position and the scope are not
        theirs to choose, they follow from the parent.
        """
        parent.check_access("write")
        return self._create_nodes([(parent, vals)])

    @api.model
    def _create_nodes(self, placed):
        """Create the nodes of ``[(parent, vals)]`` without checking rights.

        The caller did. Each node takes the scope of its parent.
        """
        # sudo(): users have no create right on nodes; the callers checked the write
        # right on the parent. No "created" chatter message per node: too many of them.
        return (
            self.sudo()
            .with_context(mail_create_nolog=True)
            .create(
                [
                    dict(vals, parent_id=parent.id, scope_id=parent.scope_id.id)
                    for parent, vals in placed
                ]
            )
        )

    @api.model
    def _create_checked(self, parent, vals):
        """Create a node below ``parent`` and tell the user if the name is taken."""
        try:
            with self.env.cr.savepoint():
                node = self._create_below(parent, vals)
        except psycopg2.errors.UniqueViolation:
            raise UserError(
                self.env._(
                    "A file or folder named %(name)s already exists here.",
                    name=vals["name"],
                )
            ) from None
        self._touch_active_parent(parent)
        return node

    @api.model
    def _content_bytes(self, content):
        """Return the content a client sent (base64 text or bytes) as bytes."""
        if not isinstance(content, str | bytes):
            raise UserError(
                self.env._("%(argument)s is not valid.", argument="content")
            )
        try:
            return blobstore.decode_content(content)
        except ValueError:  # binascii.Error is one
            raise UserError(
                self.env._("%(argument)s is not valid.", argument="content")
            ) from None

    def _stage_content(self, content, key):
        """Write ``content`` to a temp file; return ``(path, sha256, size)``."""
        tmp_path = blobstore.write_stream_to_temp(self.env, io.BytesIO(content), key)
        sha256, size = blobstore.hash_file(tmp_path)
        return tmp_path, sha256, size

    def _blob_of_staged(self, tmp_path, sha256, size, content):
        """Link the staged file into the blob store; return its blob row.

        The temp file stays: the caller removes it once the transaction has committed.
        """
        blobstore.adopt_hashed(self.env, tmp_path, sha256, keep_tmp=True)
        # sudo(): blobs have no user rights; the caller checked the rights on the node.
        blob = self.env["int_filemanager.blob"].sudo()._get_or_create(sha256, size)
        blobstore.ensure_on_disk(self.env, sha256, tmp_path)
        if content and not blob.mime:
            # The bytes are in hand: no need to read the file again.
            blob.mime = guess_mimetype(content) or False
        return blob

    @api.model
    def create_file(self, parent_id, name, content, operation_key):
        """Create a file from content small enough for one request.

        A denied request stops before anything reaches the blob store. A name
        collision raises instead of replacing the existing file.
        """
        operation, is_new = self.env["int_filemanager.operation"]._get_or_create(
            operation_key
        )
        if not is_new:
            return operation.result

        parent = self._require_node(parent_id, "parent_id")
        content = self._content_bytes(content)

        fault.fault_point("node_create_before_check")
        node = self._create_checked(parent, {"name": name, "is_dir": False})

        tmp_path, sha256, size = self._stage_content(content, f"create_{operation.id}")
        blob = self._blob_of_staged(tmp_path, sha256, size, content)
        result = self._attach_revision(node, None, blob.id, size, "upload", operation)
        fault.fault_point("node_create_after_insert")

        result["sha256"] = sha256
        operation.write({"result": result})
        # The blob is already linked under its hash; the temp file goes only once
        # the transaction has committed (postcommit does not run on rollback).
        self.env.cr.postcommit.add(lambda: _remove_if_exists(tmp_path))
        return result

    def _set_lock_timeout(self):
        """Bound how long this transaction waits for a row lock."""
        self.env.cr.execute(SQL("SET LOCAL lock_timeout TO %s", LOCK_TIMEOUT))

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
        self._set_lock_timeout()
        rows = self.env.execute_query(
            SQL(
                "UPDATE int_filemanager_node"
                " SET write_date = (now() AT TIME ZONE 'utc')"
                " WHERE id = %s AND active RETURNING id",
                parent.id,
                to_flush=self._fields["active"],
            )
        )
        if not rows:
            raise UserError(
                self.env._("The target folder is in the trash; restore it first.")
            )
        parent.invalidate_recordset(["write_date"])

    @api.model
    def create_folder(self, parent_id, name, operation_key):
        """Create a folder below ``parent_id``."""
        operation, is_new = self.env["int_filemanager.operation"]._get_or_create(
            operation_key
        )
        if not is_new:
            return operation.result

        parent = self._require_node(parent_id, "parent_id")
        node = self._create_checked(parent, {"name": name, "is_dir": True})

        result = {"node_id": node.id}
        operation.write({"result": result})
        return result

    def _lock_node(self, node):
        """Wait for the row lock of ``node``; a lock timeout propagates for a retry."""
        # Not lock_for_update(): that skips locked rows and fails at once, while a
        # second request should wait a moment and then see the first one's result.
        # FOR NO KEY UPDATE like the core's allow_referencing lock: revisions, values
        # and uploads that point at the node can still be inserted meanwhile; what is
        # written under the lock (name, place, scope, revision) is no identifier.
        fault.fault_point("node_lock_before_wait")
        self._set_lock_timeout()
        self.env.execute_query(
            SQL(
                "SELECT id FROM int_filemanager_node WHERE id = %s FOR NO KEY UPDATE",
                node.id,
            )
        )
        fault.fault_point("node_lock_acquired")

    def _lock_and_check_base_revision(self, node, base_revision_id):
        """Lock the node, check it did not change since ``base_revision_id``.

        Return the current revision as seen under the lock.
        """
        self._lock_node(node)
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

        # sudo(): users cannot create revisions or point a node at one; every caller
        # checked the rights on the node and took the blob from content it may use.
        next_no = (current.revision_no if current else 0) + 1
        revision = (
            self.env["int_filemanager.revision"]
            .sudo()
            .create(
                {
                    "node_id": node.id,
                    "blob_id": blob_id,
                    "revision_no": next_no,
                    "origin": origin,
                    "operation_id": operation.id,
                    "size": size,
                }
            )
        )
        # What the content is decides the node's type, not its name; a new revision
        # can be another kind of file than the one before.
        blob = self.env["int_filemanager.blob"].sudo().browse(blob_id)
        blob._ensure_mime()
        node.sudo().write(
            {
                "current_revision_id": revision.id,
                "size": size,
                "mime": blob.mime or False,
            }
        )
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

        origin = params.require_choice(
            self.env, origin, "origin", CLIENT_REVISION_ORIGINS
        )
        node = self._require_node(node_id, "node_id")
        node.check_access("write")
        base_revision_id = params.optional_id(
            self.env, base_revision_id, "base_revision_id"
        )
        content = self._content_bytes(content)

        current = self._lock_and_check_base_revision(node, base_revision_id)
        fault.fault_point("revision_write_before_check")

        tmp_path, sha256, size = self._stage_content(content, f"revise_{operation.id}")

        # sudo() only to read the blob's hash; the node's rights were checked above.
        if current and current.sudo().blob_id.sha256 == sha256:
            _remove_if_exists(tmp_path)
            result = {
                "node_id": node.id,
                "revision_id": current.id,
                "sha256": sha256,
                "unchanged": True,
            }
            operation.write({"result": result})
            return result

        blob = self._blob_of_staged(tmp_path, sha256, size, content)
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

        node = self._require_node(node_id, "node_id")
        base_revision_id = params.optional_id(
            self.env, base_revision_id, "base_revision_id"
        )
        node.check_access("write")

        old_revision = self.env["int_filemanager.revision"].browse(
            params.require_id(self.env, revision_id, "revision_id")
        )
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

        source = self._require_node(node_id, "node_id")
        source.check_access("read")
        if not source.is_dir and not source.current_revision_id:
            raise UserError(
                self.env._("This file has no content yet; nothing to copy.")
            )

        target_parent = self._require_node(target_parent_id, "target_parent_id")
        if source.is_dir and target_parent.parent_path.startswith(source.parent_path):
            raise UserError(self.env._("A folder cannot be copied into itself."))

        new_node = self._create_checked(
            target_parent, self._copy_vals(source, new_name)
        )
        if source.is_dir:
            copied = self._copy_children(source, new_node, operation)
            result = {"node_id": new_node.id, "copied": copied + 1}
        else:
            [revision] = self._attach_copied_revisions([(source, new_node)], operation)
            result = {"node_id": new_node.id, "revision_id": revision.id}
        operation.write({"result": result})
        return result

    @api.model
    def _copy_vals(self, source, name):
        return {
            "name": name,
            "is_dir": source.is_dir,
            "mime": source.mime,
            "tag_ids": [Command.set(source.tag_ids.ids)],
            "status_id": source.status_id.id,
            "partner_id": source.partner_id.id,
        }

    def _attach_copied_revisions(self, copies, operation):
        """Give each copied file a first revision on the content of its original.

        ``copies`` is a list of ``(original, copy)``; return the new revisions in
        the same order. All revisions are created in one call.
        """
        # sudo(): users cannot create revisions or point a node at one; the callers
        # checked the rights on the folder the copies lie in, and the originals
        # were found by a search of the caller.
        revisions = (
            self.env["int_filemanager.revision"]
            .sudo()
            .create(
                [
                    {
                        "node_id": new.id,
                        "blob_id": old.current_revision_id.blob_id.id,
                        "revision_no": 1,
                        "origin": "copy",
                        "operation_id": operation.id,
                        "size": old.current_revision_id.size,
                    }
                    for old, new in copies
                ]
            )
        )
        for (old, new), revision in zip(copies, revisions, strict=True):
            new.sudo().write(
                {
                    "current_revision_id": revision.id,
                    "size": revision.size,
                    "mime": old.mime,
                }
            )
        return revisions

    def _copy_children(self, source, new_top, operation):
        """Copy what the caller can see below ``source`` into ``new_top``.

        Return how many nodes were created. The caller checked the write right on
        the folder ``new_top`` lies in, and every copy takes its scope. The nodes
        are created one tree level at a time, so every new parent exists in time and
        a big folder costs a few calls, not one per node.
        """
        by_depth = defaultdict(list)
        for old in self.search(
            [("id", "child_of", source.id), ("id", "!=", source.id)]
        ):
            by_depth[old.parent_path.count("/")].append(old)

        new_of = {source.id: new_top}
        files = []
        for depth in sorted(by_depth):
            # A parent the caller could not see is not copied, so neither is this.
            level = [old for old in by_depth[depth] if old.parent_id.id in new_of]
            created = self._create_nodes(
                [
                    (new_of[old.parent_id.id], self._copy_vals(old, old.name))
                    for old in level
                ]
            )
            for old, new in zip(level, created, strict=True):
                new_of[old.id] = new
                if not old.is_dir and old.current_revision_id:
                    files.append((old, new))
        if files:
            self._attach_copied_revisions(files, operation)
        return len(new_of) - 1

    @api.model
    def _check_move_target(self, node, new_parent_id):
        """Return the folder to move ``node`` into, once the caller may write there.

        The record rules only check the node's current scope, not the destination.
        """
        new_parent = self.browse(new_parent_id)
        new_parent.check_access("write")
        if new_parent.parent_path.startswith(node.parent_path):
            raise UserError(self.env._("A folder cannot be moved into itself."))
        return new_parent

    @api.model
    def _move_vals(self, node, new_parent_id, new_name):
        """Return ``(vals, new_parent)`` for renaming ``node`` and moving it if asked.

        ``new_parent`` is empty when the node stays where it is.
        """
        vals = {"name": new_name}
        new_parent = self.browse()
        if new_parent_id and new_parent_id != node.parent_id.id:
            new_parent = self._check_move_target(node, new_parent_id)
            vals["parent_id"] = new_parent.id
            if new_parent.scope_id != node.scope_id:
                vals["scope_id"] = new_parent.scope_id.id
        return vals, new_parent

    @api.model
    def rename_or_move(self, node_id, new_parent_id, new_name, operation_key):
        """Rename a node and/or move it below ``new_parent_id``.

        Only rows change, no file is touched. Moving into another scope moves
        what shares the node's scope along; a folder below it with a scope of
        its own keeps it.
        """
        operation, is_new = self.env["int_filemanager.operation"]._get_or_create(
            operation_key
        )
        if not is_new:
            return operation.result

        node = self._require_node(node_id, "node_id")
        node.check_access("write")
        new_parent_id = params.optional_id(self.env, new_parent_id, "new_parent_id")

        vals, new_parent = self._move_vals(node, new_parent_id, new_name)

        # A LockNotAvailable propagates, same reasoning as in create_new_revision.
        self._lock_node(node)
        if not node.active:
            raise UserError(
                self.env._("This item is in the trash; restore it before moving it.")
            )

        fault.fault_point("node_rename_before_check")
        fault.fault_point("node_tree_before_write")
        self._touch_active_parent(new_parent)
        # What shares the old scope is read before the node changes it.
        inheriting = self._inheriting_descendants(node) if "scope_id" in vals else None
        try:
            with self.env.cr.savepoint():
                # sudo(): the position and scope fields are not writable by users;
                # the rights on the node and on the destination were checked above.
                node.sudo().write(vals)
        except psycopg2.errors.UniqueViolation:
            raise UserError(
                self.env._(
                    "A file or folder named %(name)s already exists here.",
                    name=new_name,
                )
            ) from None

        if inheriting:
            self._set_scope(inheriting, vals["scope_id"])

        result = {"node_id": node.id}
        operation.write({"result": result})
        return result

    def _inheriting_descendants(self, node):
        """Return the descendants of ``node`` that take their scope from it.

        A folder with a scope of its own is left out, with everything below it:
        the caller may not even see it, and its rights are not the node's to give.
        """
        # sudo(): this follows the scope of rows the caller may not read.
        scope_id = node.sudo().scope_id.id
        descendants = (
            self.sudo()
            .with_context(active_test=False)
            .search_fetch(
                [("id", "child_of", node.id), ("id", "!=", node.id)],
                ["parent_id", "scope_id"],
                order="parent_path",
            )
        )
        # Parents come before their children, so one pass is enough.
        inheriting_ids = {node.id}
        for child in descendants:
            if child.parent_id.id in inheriting_ids and child.scope_id.id == scope_id:
                inheriting_ids.add(child.id)
        inheriting_ids.discard(node.id)
        return descendants.browse(inheriting_ids)

    def _set_scope(self, nodes, scope_id):
        """Set the scope of ``nodes`` in one statement.

        A subtree can have hundreds of thousands of rows, too many to write
        through the ORM; the stored fields that depend on the scope are
        recomputed from ``modified()``.
        """
        self.flush_model(["scope_id"])
        self.env.execute_query(
            SQL(
                "UPDATE int_filemanager_node SET scope_id = %s WHERE id = ANY(%s)",
                scope_id,
                nodes.ids,
            )
        )
        nodes.invalidate_recordset(["scope_id"])
        nodes.modified(["scope_id"])

    @api.model
    def trash(self, node_id, operation_key):
        """Move a node and everything visible below it to the trash."""
        operation, is_new = self.env["int_filemanager.operation"]._get_or_create(
            operation_key
        )
        if not is_new:
            return operation.result

        node = self._require_node(node_id, "node_id")
        node.check_access("write")

        subtree = self.search([("id", "child_of", node.id)])
        # The write below is sudo(), which skips the record rules of every row.
        subtree.check_access("write")
        fault.fault_point("node_tree_before_write")
        subtree.sudo().write(
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

        node = self._require_node(node_id, "node_id")
        node.check_access("write")

        subtree = self.with_context(active_test=False).search(
            [("id", "child_of", node.id)]
        )
        # The write below is sudo(), which skips the record rules of every row.
        subtree.check_access("write")
        fault.fault_point("node_tree_before_write")
        # Restoring under a folder that is still in the trash would leave an active
        # node below an inactive one - same rule (and same row conflict) as moving
        # into it.
        self._touch_active_parent(node.parent_id)
        try:
            with self.env.cr.savepoint():
                subtree.sudo().write(
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

        node = self._require_node(node_id, "node_id")
        node.check_access("unlink")

        self._unlink_subtree(node)

        result = {"node_id": node.id}
        operation.write({"result": result})
        return result

    @api.model
    def _unlink_subtree(self, root):
        """Delete ``root`` with everything below it; return how many nodes went."""
        subtree = self.with_context(active_test=False).search(
            [("id", "child_of", root.id)]
        )
        # The write below is sudo(); unlink() checks the purge right per row, the
        # write right is what clearing the revision used to need.
        subtree.check_access("write")
        # current_revision_id is ondelete=restrict: clear it before the delete.
        subtree.sudo().write({"current_revision_id": False})
        subtree.unlink()
        return len(subtree)

    @api.model
    def _trash_retention_days(self):
        # sudo(): a setting of the module, not data of the caller.
        return int(
            self.env["ir.config_parameter"]
            .sudo()
            .get_param(TRASH_RETENTION_PARAM, DEFAULT_TRASH_RETENTION_DAYS)
        )

    @api.model
    def _expired_trash_domain(self):
        """Return the domain of the tops of trash subtrees older than the retention."""
        cutoff = fields.Datetime.now() - timedelta(days=self._trash_retention_days())
        expired = Domain("removal_reason", "=", "trash") & Domain(
            "trashed_at", "<", cutoff
        )
        # Spelled out: NOT (parent_id IN ...) is no answer for a node without parent.
        return expired & (
            Domain("parent_id", "=", False) | ~Domain("parent_id", "any", expired)
        )

    @api.model
    def _expired_trash_roots(self, limit=None):
        """Return up to ``limit`` tops of trashed subtrees older than the retention."""
        return self.with_context(active_test=False).search(
            self._expired_trash_domain(), limit=limit
        )

    @api.model
    def _purge_root(self, root):
        """Delete one expired subtree; return whether it went.

        A savepoint per subtree, so that one that cannot go (a right, a row still in
        use) does not block the others.
        """
        try:
            with self.env.cr.savepoint():
                self._unlink_subtree(root)
        except (UserError, psycopg2.Error):
            _logger.exception("could not purge trashed node %s", root.id)
            return False
        return True

    @api.model
    def _purge_expired_trash(self, limit=TRASH_PURGE_BATCH):
        """Delete up to ``limit`` expired trash subtrees; return how many went."""
        return sum(self._purge_root(root) for root in self._expired_trash_roots(limit))

    @api.model
    def _cron_purge_trash(self, limit=TRASH_PURGE_BATCH):
        """Delete the expired trash subtrees, committing after each one."""
        roots = self._expired_trash_roots(limit)
        remaining = (
            len(roots)
            if len(roots) < limit
            else self.with_context(active_test=False).search_count(
                self._expired_trash_domain()
            )
        )
        cron = self.env["ir.cron"]
        cron._commit_progress(remaining=remaining)
        for root in roots:
            self._purge_root(root)
            if not cron._commit_progress(1):
                return
