import io
import json
import logging
import os
import re
import unicodedata
import uuid
from datetime import timedelta

import psycopg2
from markupsafe import Markup

from odoo import Command, api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Domain
from odoo.tools import SQL, escape_psql
from odoo.tools.mimetypes import guess_mimetype

from .. import blobstore, fault, value_suggest, value_types
from .. import derivative_plan as plan
from . import int_filemanager_derivative as derivative

_logger = logging.getLogger(__name__)


# Days a node stays in the trash before it is deleted for good.
DEFAULT_TRASH_RETENTION_DAYS = 30
TRASH_RETENTION_PARAM = "int_filemanager.trash_retention_days"

# A name never carries a path: "/" and "\\" would make it one. The rest is what Windows
# refuses, so that an export or a network drive works for every name in the tree.
_INVALID_NAME_CHARS = re.compile(r'[\x00-\x1f<>:"/\\|?*]')
_WINDOWS_RESERVED_NAME = re.compile(r"(con|prn|aux|nul|(com|lpt)[0-9¹²³])(\..*)?", re.I)

# Company names are looked for in the letterhead, the start of the first page.
NAME_SEARCH_CHARS = 20000
MAX_SUGGESTED_TAGS = 10
# Boxes one request may carry, and the longest text a marking may cover.
MAX_AREAS = 50
MAX_SELECTION_CHARS = 200
# Words of one page sent to the review window to click on.
MAX_PAGE_WORDS = 5000
# Words of a content search, and their length.
MAX_SEARCH_TERMS = 10
MAX_SEARCH_TERM_CHARS = 100


def _website_host(website):
    """ "https://www.example.com/x" -> "example.com"."""
    host = re.sub(r"^[a-z]+://", "", (website or "").strip().lower())
    return host.split("/")[0].removeprefix("www.")


def _area(field):
    return None if field.page_area == "anywhere" else field.page_area


def _whole_words(text, start, end):
    """Widen ``[start:end]`` where it cuts a word, up to a blank, tab or line break.

    Looks no further than a marking may be long, so a text without blanks costs no more.
    """
    if 0 < start < len(text) and not text[start - 1].isspace():
        if not text[start].isspace():
            head = text[max(0, start - MAX_SELECTION_CHARS) : start]
            start -= len(re.search(r"\S*$", head)[0])
    if 0 < end < len(text) and not text[end - 1].isspace():
        if not text[end].isspace():
            end += len(re.match(r"\S*", text[end : end + MAX_SELECTION_CHARS])[0])
    return start, end


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
    # Only the states: the explorer builds the picture URLs from the revision itself.
    # Thumbnail and large preview image.
    preview_state = fields.Selection(PREVIEW_STATES, compute="_compute_preview_states")
    full_preview_state = fields.Selection(
        PREVIEW_STATES, compute="_compute_preview_states"
    )

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
    # Searchable only: the text read from the document (see the derivative's ``text``).
    # It is never handed out, not even to someone who found the file by it.
    content = fields.Char(compute="_compute_content", search="_search_content")

    @api.depends("parent_id", "scope_id", "parent_id.scope_id")
    def _compute_is_scope_root(self):
        for node in self:
            node.is_scope_root = (
                not node.parent_id or node.parent_id.scope_id != node.scope_id
            )

    def _compute_preview_states(self):
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

    def _compute_content(self):
        self.content = False

    def _search_content(self, operator, value):
        """Files whose read text contains every word of ``value``, in any order.

        Only the current revision counts. The text is read as the superuser, but the
        answer is a list of hits, which the caller's rights on the node then narrow
        down like for any other field: nothing is revealed about files the caller
        cannot see.
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
        if content and not blob.mime:
            # The bytes are in hand: no need to read the file again.
            blob.mime = guess_mimetype(content) or False
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
        # What the content is decides the node's type, not its name; a new revision
        # can be another kind of file than the one before.
        blob = self.env["int_filemanager.blob"].sudo().browse(blob_id)
        blob._ensure_mime()
        node.write(
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

    # ------------------------------------------------------------------
    # value recognition
    # ------------------------------------------------------------------

    @api.model
    def suggest_field_values(self, node_id, areas=None):
        """Suggest values for the extraction fields from the file's current text.

        Nothing is stored: rules change at any time, and stored suggestions would go
        stale. ``state`` is "ready", "pending" (the text is still being read) or
        "none" (no text to read, e.g. a picture); ``revision_id`` is the revision the
        suggestions come from, to be sent back when they are confirmed.

        :param areas: boxes the user drew, ``[{"page", "x0", "top", "x1", "bottom"}]``
            with the place as shares (0 to 1) of the page. A value printed in a box
            goes before the same kind of value outside; everything outside is still
            found. ``areas`` in the answer has one entry per box: how many values
            lie in it and the label-value pairs no field took.
        """
        node = self.browse(node_id)
        node.check_access("read")
        boxes = self._parse_areas(areas)
        revision = node.current_revision_id
        if node.is_dir or not revision:
            return {"state": "none", "revision_id": False}
        state, page = self._recognition_page(node, revision)
        if state != "ready":
            return {"state": state, "revision_id": revision.id}
        own = self._own_company_values()
        options = self._recognition_options()

        def slow(rule_id, seconds):
            _logger.warning(
                "extraction rule %s took %.1f s on node %s", rule_id, seconds, node.id
            )

        partner = self._suggest_partner(page.text, own, options)
        suggestions, unassigned = value_suggest.suggest(
            page,
            self._extraction_specs(self._sender(node, partner)),
            skip=lambda value_type, value: self._is_own_value(own, value_type, value),
            slow=slow,
            areas=boxes,
            **options,
        )
        codes = {
            c.name: c.id
            for c in self.env["res.currency"].sudo().search([("active", "=", True)])
        }
        confirmed = {v.field_id.id: v for v in node.field_value_ids}
        return {
            "state": "ready",
            "revision_id": revision.id,
            "review_state": node.review_state,
            # Width and height of the pages in the unit of the value boxes; a page
            # not listed is taken as A4.
            "page_sizes": {str(n): list(size) for n, size in page.sizes.items()},
            "fields": [
                {
                    "field_id": f.id,
                    "name": f.name,
                    "value_type": f.value_type,
                    "suggestions": [
                        self._json_suggestion(s.as_dict(), codes)
                        for s in suggestions.get(f.id, [])
                    ],
                    "confirmed": confirmed[f.id].value_text
                    if f.id in confirmed
                    else False,
                }
                for f in self.env["int_filemanager.extraction_field"].search(
                    [("active", "=", True)]
                )
            ],
            "unassigned": [
                self._json_value(u, codes) for u in unassigned if u["area"] is None
            ],
            "areas": [
                {
                    "index": index,
                    "values": sum(
                        1
                        for found in suggestions.values()
                        if page.in_box(found[0].start, found[0].end, box)
                    )
                    + sum(1 for u in unassigned if u["area"] == index),
                    "unassigned": [
                        self._json_value(u, codes)
                        for u in unassigned
                        if u["area"] == index
                    ],
                }
                for index, box in enumerate(boxes)
            ],
            "partner": partner,
            "tags": self._suggest_tags(page.text),
            "warnings": self._suggest_warnings(partner, suggestions),
        }

    def _suggest_warnings(self, partner, suggestions):
        """Hints for the reviewer about values that look wrong; nothing is stored.

        An IBAN that none of the bank accounts of the sender has: the protection
        against a forged invoice with a new account. Without a known sender or
        accounts there is nothing to compare with.
        """
        if not partner:
            return []
        accounts = (
            self.env["res.partner.bank"]
            .sudo()
            .search([("partner_id", "child_of", partner["id"])])
        )
        known = {a.sanitized_acc_number for a in accounts if a.sanitized_acc_number}
        if not known:
            return []
        warnings = []
        for field in self.env["int_filemanager.extraction_field"].search(
            [("active", "=", True), ("value_type", "=", "iban")]
        ):
            best = (suggestions.get(field.id) or [None])[0]
            if best and best.value["value_text"] not in known:
                warnings.append(
                    {
                        "type": "iban_differs",
                        "field_id": field.id,
                        "message": self.env._(
                            "%(field)s: this IBAN is not one of the bank accounts "
                            "of %(partner)s.",
                            field=field.name,
                            partner=partner["name"],
                        ),
                    }
                )
        return warnings

    @api.model
    def page_words(self, node_id, revision_id, page_number):
        """The words of one page of a file with their places, to click on.

        :returns: ``{"state", "revision_id", "words"}``; each word is ``[x0, top,
            x1, bottom, start, end]`` in the unit of the value boxes, ``start`` and
            ``end`` the offsets in the text of the file. "changed" when the file has a
            newer revision than ``revision_id``.
        """
        node = self.browse(node_id)
        node.check_access("read")
        if not isinstance(page_number, int) or isinstance(page_number, bool):
            raise UserError(self.env._("The page is not valid."))
        revision = node.current_revision_id
        if node.is_dir or not revision:
            return {"state": "none", "revision_id": False, "words": []}
        if revision.id != revision_id:
            return {"state": "changed", "revision_id": revision.id, "words": []}
        state, page = self._recognition_page(node, revision)
        if state != "ready":
            return {"state": state, "revision_id": revision.id, "words": []}
        words = [
            [w[1], w[2], w[3], w[4], w[5], w[6]]
            for w in page.words
            if w[0] == page_number
        ]
        return {
            "state": "ready",
            "revision_id": revision.id,
            "words": words[:MAX_PAGE_WORDS],
        }

    def _parse_areas(self, areas):
        """The boxes of a request as tuples ``(page, x0, top, x1, bottom)``."""
        areas = areas or []
        if len(areas) > MAX_AREAS:
            raise UserError(self.env._("There are too many boxes."))
        boxes = []
        for area in areas:
            try:
                page = area["page"]
                x0, top, x1, bottom = (
                    float(area[k]) for k in ("x0", "top", "x1", "bottom")
                )
                valid = (
                    isinstance(page, int)
                    and not isinstance(page, bool)
                    and page >= 1
                    and 0.0 <= x0 < x1 <= 1.0
                    and 0.0 <= top < bottom <= 1.0
                )
            except (KeyError, TypeError, ValueError):
                valid = False
            if not valid:
                raise UserError(self.env._("A box is not valid."))
            boxes.append((page, x0, top, x1, bottom))
        return boxes

    def _recognition_options(self):
        """Currencies as printed (symbol or code) and the defaults of the company."""
        # Settings, not data of the user: read whatever the user's own rights are.
        company = self.env.company.sudo()
        currencies = {}
        for currency in (
            self.env["res.currency"].sudo().search([("active", "=", True)])
            + company.currency_id
        ):
            currencies[currency.symbol] = currency.name
            currencies[currency.name] = currency.name
        if "EUR" in currencies:
            currencies["Euro"] = "EUR"
        return {
            "currencies": currencies,
            "default_currency": company.currency_id.name,
            "default_country": (company.country_id.code or "DE").upper(),
        }

    def _recognition_page(self, node, revision):
        """("ready", Page) of the revision's text and words, or (state, None)."""
        jobs = (
            self.env["int_filemanager.derivative"]
            .sudo()
            .search(
                [
                    ("source_blob_id", "=", revision.blob_id.id),
                    "|",
                    "&",
                    ("kind", "=", "words"),
                    ("spec", "=", plan.WORDS_SPEC),
                    "&",
                    ("kind", "=", "text"),
                    ("spec", "=", plan.TEXT_SPEC),
                ]
            )
        )
        done = jobs.filtered(lambda j: j.state == "done")
        words_job = done.filtered(lambda j: j.kind == "words" and j.derived_blob_id)[:1]
        if words_job:
            words = self._read_word_list(words_job.derived_blob_id)
            if words is not None:
                return "ready", value_suggest.Page(
                    words["text"], words["words"], words.get("pages")
                )
        text_job = done.filtered(lambda j: j.kind == "text" and j.text)[:1]
        if text_job:
            return "ready", value_suggest.Page(text_job.text)
        if jobs.filtered(lambda j: j.state in ("pending", "running")):
            return "pending", None
        # Not queued yet (the queue runs by cron), but planned for this kind of file.
        planned = {item.kind for item in plan.job_plan(node.name)}
        if not jobs and planned & {"words", "text"}:
            return "pending", None
        return "none", None

    def _read_word_list(self, blob):
        path = blobstore.blob_path(self.env, blob.sha256)
        try:
            if os.path.getsize(path) > derivative.MAX_WORDS_BYTES:
                return None
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            _logger.warning(
                "word list %s could not be read", blob.sha256, exc_info=True
            )
            return None
        if not isinstance(data, dict) or data.get("version") != 2:
            return None
        text, words = data.get("text"), data.get("words")
        if not isinstance(text, str) or not isinstance(words, list):
            return None
        # Only well-formed words that point into the text; a broken entry is left
        # out rather than breaking the whole suggestion.
        data["words"] = [
            w
            for w in words
            if isinstance(w, list)
            and len(w) == 7
            and all(isinstance(x, int | float) for x in w)
            and 0 <= w[5] <= w[6] <= len(text)
        ]
        return data

    def _sender(self, node, suggested):
        """The sender whose learned labels apply: the file's contact, else the one
        suggested; only a contact the user may read."""
        partner = node.partner_id.commercial_partner_id
        if not partner and suggested:
            partner = self.env["res.partner"].browse(suggested["id"])
        return partner._filtered_access("read")

    def _extraction_specs(self, sender=None):
        """The active fields and rules as the recognition needs them, with the labels
        learned for the sender."""
        specs = []
        # Users have no access to the learned labels themselves: the list would show
        # which senders there are documents from, also in scopes they cannot read.
        hints = (
            self.env["int_filemanager.extraction_hint"]
            .sudo()
            .search(
                [("partner_id", "=", sender.id), ("field_id.active", "=", True)]
                if sender
                else [("id", "=", False)]
            )
        )
        for field in hints.field_id:
            specs.append(
                value_suggest.FieldSpec(
                    field.id,
                    field.value_type,
                    unit=field.unit or None,
                    hints={h.label: h.id for h in hints if h.field_id == field},
                    area=_area(field),
                )
            )
        rules = self.env["int_filemanager.extraction_rule"].search(
            [("field_id.active", "=", True)]
        )
        for rule in rules:
            f = rule.field_id
            spec = value_suggest.FieldSpec(
                f.id, f.value_type, unit=f.unit or None, rule_id=rule.id, area=_area(f)
            )
            if rule.mode == "keyword":
                spec.keywords = rule._keyword_list()
            else:
                flags = re.IGNORECASE if rule.ignore_case else 0
                pattern = re.compile(rule.pattern, flags)
                spec.patterns = [(rule.id, pattern, rule.group_index)]
            specs.append(spec)
        return specs

    def _own_company_values(self):
        """VAT numbers, bank accounts and mail domains of the own companies."""
        partners = (
            self.env["res.company"]
            .sudo()
            .search([("partner_id", "!=", False)])
            .partner_id
        )
        accounts = (
            self.env["res.partner.bank"]
            .sudo()
            .search([("partner_id", "in", partners.ids)])
        )
        domains = set()
        for partner in partners:
            if partner.email and "@" in partner.email:
                domains.add(partner.email.rsplit("@", 1)[1].strip().lower())
            if partner.website:
                domains.add(_website_host(partner.website))
        return {
            "partner_ids": set(partners.commercial_partner_id.ids),
            "vat": {re.sub(r"[^A-Z0-9]", "", p.vat.upper()) for p in partners if p.vat},
            "iban": {
                a.sanitized_acc_number for a in accounts if a.sanitized_acc_number
            },
            "domains": domains - {""},
        }

    @api.model
    def _is_own_value(self, own, value_type, value):
        text = value.get("value_text") or ""
        if value_type in ("iban", "vat"):
            return text in own[value_type]
        if value_type == "email":
            return text.rsplit("@", 1)[-1] in own["domains"]
        return False

    def _suggest_partner(self, text, own, options):
        """The sender, found like account's _import_retrieve_customer does: VAT
        number, bank account, mail address or its domain, then the name; never an
        own company, and only a contact the user may read."""
        partners = self.env["res.partner"].sudo()

        def found(records, via):
            # Access is checked on the company that is returned, not on the contact
            # that led to it.
            commercial = records.commercial_partner_id.filtered(
                lambda p: p.id not in own["partner_ids"]
            )
            readable = commercial.with_env(self.env)._filtered_access("read")
            if not readable:
                return None
            partner = readable[0]
            return {"id": partner.id, "name": partner.display_name, "via": via}

        def values(value_type):
            return sorted(
                {
                    c.value["value_text"]
                    for c in value_types.find(value_type, text, **options)
                    if not self._is_own_value(own, value_type, c.value)
                }
            )

        for vat in values("vat"):
            # Stored with or without the country prefix.
            domain = ["|", ("vat", "=ilike", vat), ("vat", "=ilike", vat[2:])]
            if hit := found(partners.search(domain, limit=5), "vat"):
                return hit
        if ibans := values("iban"):
            accounts = (
                self.env["res.partner.bank"]
                .sudo()
                .search([("sanitized_acc_number", "in", ibans)], limit=5)
            )
            if hit := found(accounts.partner_id, "iban"):
                return hit
        addresses = values("email")
        for address in addresses:
            records = partners.search([("email", "=ilike", address)], limit=5)
            if hit := found(records, "email"):
                return hit
        # Another address of the same company: its domain is the company's website.
        # A mail provider's domain is nobody's website, so it never matches.
        for domain in sorted({a.rsplit("@", 1)[1] for a in addresses}):
            records = partners.search([("website", "ilike", domain)], limit=20)
            records = records.filtered(
                lambda p, d=domain: _website_host(p.website) == d
            )
            if hit := found(records, "email"):
                return hit
        # Names last: companies whose whole name stands in the letterhead (the
        # first page), compared in the database rather than name by name.
        first_page = text.split("\f", 1)[0][:NAME_SEARCH_CHARS]
        tokens = [t.strip(",;:()").lower() for t in first_page.split()]
        phrases = {
            " ".join(tokens[i : i + n])
            for n in range(1, 7)
            for i in range(len(tokens) - n + 1)
        }
        phrases = [p for p in phrases if len(p) >= 5]
        if phrases:
            self.env.cr.execute(
                """
                SELECT id FROM res_partner
                WHERE active AND is_company AND length(name) >= 5
                  AND lower(regexp_replace(name, '[[:space:]]+', ' ', 'g')) = ANY(%s)
                ORDER BY length(name) DESC
                LIMIT 20
                """,
                [phrases],
            )
            ids = [row[0] for row in self.env.cr.fetchall()]
            if hit := found(partners.browse(ids), "name"):
                return hit
        return False

    def _suggest_tags(self, text):
        """Tags whose name stands in the text as a whole word or phrase."""
        words = re.findall(r"\w+", text.lower())
        single, joined = set(words), f" {' '.join(words)} "
        result = []
        for tag in self.env["int_filemanager.tag"].search([("name", "!=", False)]):
            parts = re.findall(r"\w+", tag.name.lower())
            if not parts:
                continue
            if (
                parts[0] in single
                if len(parts) == 1
                else f" {' '.join(parts)} " in joined
            ):
                result.append({"id": tag.id, "name": tag.name})
                if len(result) == MAX_SUGGESTED_TAGS:
                    break
        return result

    @api.model
    def _json_value(self, value, codes):
        """A value of value_types as JSON, with the currency as a record id."""
        result = {}
        for key, item in value.items():
            if key == "currency_code":
                result["currency_id"] = codes.get(item, False)
            elif hasattr(item, "isoformat"):
                result[key] = item.isoformat()
            else:
                result[key] = item
        return result

    @api.model
    def _json_suggestion(self, suggestion, codes):
        return {**suggestion, "value": self._json_value(suggestion["value"], codes)}

    @api.model
    def read_selection(self, node_id, revision_id, field_id, start, end):
        """Read the marked text of a file as a value of a field.

        :param revision_id: the revision the marking was made on; if the file has
            a newer one by now, ``state`` is "changed" and nothing is read
        :param start: offset in the text of the file where the marking begins
        :param end: offset where it ends; a marking that cuts a word takes the
            whole word
        :returns: ``{"state", "revision_id", "suggestion", "message"}``. ``suggestion``
            is the value in the form of :meth:`suggest_field_values` (direction
            "selection"), or False when the text is no value of the field; then
            ``message`` says so. Nothing is stored: confirming goes through
            :meth:`apply_field_values`, which reads the text again.
        """
        node = self.browse(node_id)
        node.check_access("read")
        field = self.env["int_filemanager.extraction_field"].browse(field_id)
        if not field.exists():
            raise UserError(self.env._("This field does not exist any more."))
        revision = node.current_revision_id
        if node.is_dir or not revision:
            return {"state": "none", "revision_id": False}
        if revision.id != revision_id:
            return {"state": "changed", "revision_id": revision.id}
        state, page = self._recognition_page(node, revision)
        if state != "ready":
            return {"state": state, "revision_id": revision.id}
        if not (
            isinstance(start, int)
            and isinstance(end, int)
            and 0 <= start < end <= len(page.text)
            # Blanks are squeezed below, so the range may be longer than the text.
            and end - start <= 4 * MAX_SELECTION_CHARS
        ):
            raise UserError(self.env._("The marking is not valid."))
        start, end = _whole_words(page.text, start, end)
        marked = page.text[start:end]
        text = " ".join(marked.split())
        # Not over a page break: the place of the value would belong to no page.
        if not text or len(text) > MAX_SELECTION_CHARS or "\f" in marked:
            raise UserError(self.env._("The marking is not valid."))
        result = {"state": "ready", "revision_id": revision.id}
        try:
            parsed = self._parse_confirmed(field, text, self._recognition_options())
        except UserError:
            labels = dict(field._fields["value_type"]._description_selection(self.env))
            message = self.env._(
                "%(text)s cannot be read as: %(type)s.",
                text=text,
                type=labels[field.value_type],
            )
            return {**result, "suggestion": False, "message": message}
        codes = {
            c.name: c.id
            for c in self.env["res.currency"].sudo().search([("active", "=", True)])
        }
        box = dict(
            zip(
                ("page", "x0", "top", "x1", "bottom"),
                page.box(start, end) or (0, 0.0, 0.0, 0.0, 0.0),
                strict=True,
            )
        )
        suggestion = {
            "value": parsed,
            "source_text": text,
            "start": start,
            "end": end,
            **box,
            "label": "",
            "direction": "selection",
            "tier": None,
            "rule_id": None,
            "hint_id": None,
            "in_area": False,
        }
        return {**result, "suggestion": self._json_suggestion(suggestion, codes)}

    @api.model
    def apply_field_values(
        self, node_id, revision_id, values, partner_id=False, tag_ids=None
    ):
        """Store the confirmed values of the extraction fields on a file.

        :param revision_id: the revision the values were read from; if the file has
            a newer one by now, nothing is stored
        :param values: ``[{"field_id", "text", "source", "rule_id", "start"}]`` -
            ``text`` as printed or typed, an empty one removes the field's value;
            ``source`` "rule" for an accepted suggestion (``rule_id`` the rule that
            found it, ``start`` its place in the text), "manual" for a typed value.
            Every text is read again here with the field's type: nothing parsed by
            the client is taken over.
        :param partner_id: the confirmed sender, False to leave it as it is
        :param tag_ids: tags to add to the file
        :returns: ``{field_id: value_text}`` of the file's values after the change
        """
        node = self.browse(node_id)
        node.check_access("write")
        # Under the node's lock, like a new revision: a revision stored meanwhile by
        # another request makes these values stale.
        self._lock_and_check_base_revision(node, revision_id)
        if partner_id:
            self.env["res.partner"].browse(partner_id).check_access("read")
        tags = self.env["int_filemanager.tag"].browse(tag_ids or [])
        tags.check_access("read")

        options = self._recognition_options()
        _state, page = self._recognition_page(node, node.current_revision_id)
        Value = self.env["int_filemanager.field_value"].sudo()
        existing = {v.field_id.id: v for v in node.sudo().field_value_ids}
        stored, removed, learn = [], [], []
        for item in values:
            field = self.env["int_filemanager.extraction_field"].browse(
                item["field_id"]
            )
            if not field.exists():
                raise UserError(self.env._("This field does not exist any more."))
            text = (item.get("text") or "").strip()
            if not text:
                if field.id in existing:
                    existing.pop(field.id).unlink()
                    removed.append(field)
                continue
            parsed = self._parse_confirmed(field, text, options)
            from_rule = item.get("source") == "rule"
            vals = {
                "node_id": node.id,
                "field_id": field.id,
                "revision_id": revision_id,
                "source": "rule" if from_rule else "manual",
                "rule_id": (from_rule and item.get("rule_id")) or False,
                "source_text": text,
                "value_text": parsed["value_text"],
                "value_date": parsed.get("value_date") or False,
                "value_date_to": parsed.get("value_date_to") or False,
                "value_number": parsed.get("value_number") or 0.0,
                "currency_id": self._currency_id(parsed.get("currency_code")),
                "unit": parsed.get("unit") or False,
                "page": 0,
                "x0": 0.0,
                "top": 0.0,
                "x1": 0.0,
                "bottom": 0.0,
            }
            label = None
            if page:
                label, printed = value_suggest.label_of_value(
                    page,
                    field.value_type,
                    parsed["value_text"],
                    near=item.get("start"),
                    unit=field.unit or None,
                    **options,
                )
                box = printed and page.box(printed.start, printed.end)
                if box:
                    vals.update(
                        zip(("page", "x0", "top", "x1", "bottom"), box, strict=False)
                    )
            if field.id in existing:
                existing[field.id].write(vals)
            else:
                existing[field.id] = Value.create(vals)
            stored.append((field, parsed["value_text"]))
            if label:
                learn.append((field, label, page.box(label.start, label.end)))

        if partner_id and node.partner_id.id != partner_id:
            node.partner_id = partner_id
        if tags:
            node.tag_ids = [Command.link(tag.id) for tag in tags]
        self._learn_labels(node.partner_id, learn)
        node.review_state = "reviewed"
        if stored or removed:
            self._post_confirmed_values(node, stored, removed)
        return {v.field_id.id: v.value_text for v in existing.values()}

    def _parse_confirmed(self, field, text, options):
        """The value of a confirmed text, read with the field's type; UserError if none.

        A number typed without its unit or currency is read with the field's.
        """
        unit = field.unit or None
        if field.value_type == "amount" and field.currency_id:
            options = {**options, "default_currency": field.currency_id.name}
        attempts = [text]
        if field.value_type == "quantity":
            attempts.append(f"{text} {field.unit}")
        elif field.value_type == "amount":
            code = field.currency_id.name or options["default_currency"]
            attempts.append(f"{text} {code}")
        for attempt in attempts:
            parsed = value_types.parse(field.value_type, attempt, unit=unit, **options)
            if parsed:
                return parsed
        raise UserError(
            self.env._(
                "%(field)s: %(text)s cannot be read as a value of this field.",
                field=field.name,
                text=text,
            )
        )

    def _currency_id(self, code):
        if not code:
            return False
        return (
            self.env["res.currency"]
            .sudo()
            .with_context(active_test=False)
            .search([("name", "=", code)], limit=1)
            .id
        )

    def _learn_labels(self, partner, learned):
        """Remember for the sender which label named which field; the last one wins."""
        own = self._own_company_values()["partner_ids"]
        partner = partner.commercial_partner_id
        if not partner or partner.id in own:
            return
        Hint = self.env["int_filemanager.extraction_hint"].sudo()
        for field, label, box in learned:
            norm = value_suggest.normalize(label.text)
            if not norm:
                continue
            vals = {
                "field_id": field.id,
                "direction": label.direction,
                "page": box[0] if box else 0,
                "x0": box[1] if box else 0.0,
                "top": box[2] if box else 0.0,
                "last_date": fields.Datetime.now(),
            }
            hint = Hint.search(
                [("partner_id", "=", partner.id), ("label", "=", norm)], limit=1
            )
            if hint:
                vals["hit_count"] = hint.hit_count + 1 if hint.field_id == field else 1
                hint.write(vals)
            else:
                Hint.create({**vals, "partner_id": partner.id, "label": norm})

    def _post_confirmed_values(self, node, stored, removed):
        """A note on the file: who confirmed which values, for later questions."""
        lines = [Markup("<li>%s: %s</li>") % (f.name, text) for f, text in stored]
        lines += [
            Markup("<li>%s: %s</li>") % (f.name, self.env._("removed")) for f in removed
        ]
        node.message_post(
            body=Markup("<p>%s</p><ul>%s</ul>")
            % (self.env._("Values confirmed"), Markup("").join(lines)),
            subtype_xmlid="mail.mt_note",
        )
