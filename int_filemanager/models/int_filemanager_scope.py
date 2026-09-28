from odoo import fields, models


class IntFilemanagerScope(models.Model):
    """Who may read, write, manage and purge a subtree of nodes.

    Every node stores its scope, so the record rules are a plain join on the
    scope's groups instead of a generated domain per folder.
    """

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
