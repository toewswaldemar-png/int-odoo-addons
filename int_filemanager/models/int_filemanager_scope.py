from odoo import fields, models


class IntFilemanagerScope(models.Model):
    """Rights scope for a subtree of int_filemanager.node (Konzept 4/12).

    Every node stores the scope of the nearest ancestor folder that has one
    (I7); ir.rule on node/revision/... reads read_group_ids/write_group_ids
    from here rather than from path prefixes, so a rule stays one indexed
    join instead of a generated per-folder domain (A1, A10)."""

    _name = "int_filemanager.scope"
    _description = "Filemanager v2 rights scope"
    _order = "name"

    name = fields.Char(required=True)
    read_group_ids = fields.Many2many(
        "res.groups",
        "int_filemanager_scope_read_group_rel",
        "scope_id",
        "group_id",
        string="Read groups",
    )
    write_group_ids = fields.Many2many(
        "res.groups",
        "int_filemanager_scope_write_group_rel",
        "scope_id",
        "group_id",
        string="Write groups",
    )
    manage_group_ids = fields.Many2many(
        "res.groups",
        "int_filemanager_scope_manage_group_rel",
        "scope_id",
        "group_id",
        string="Manage groups",
    )
    purge_group_ids = fields.Many2many(
        "res.groups",
        "int_filemanager_scope_purge_group_rel",
        "scope_id",
        "group_id",
        string="Purge groups",
    )

    _name_uniq = models.Constraint(
        "UNIQUE(name)", "A scope with this name already exists."
    )
