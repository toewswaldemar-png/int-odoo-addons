from odoo import fields, models


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
