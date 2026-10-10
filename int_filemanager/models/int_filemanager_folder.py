from odoo import api, fields, models
from odoo.exceptions import UserError


class IntFilemanagerFolder(models.Model):
    """A folder: an ordinary record with a parent, nothing else."""

    _name = "int_filemanager.folder"
    _description = "Filemanager folder"
    _parent_store = True
    _order = "name"

    name = fields.Char(required=True)
    parent_id = fields.Many2one("int_filemanager.folder", index=True, ondelete="restrict")
    parent_path = fields.Char(index=True)
    child_ids = fields.One2many("int_filemanager.folder", "parent_id")
    document_ids = fields.One2many("int_filemanager.document", "folder_id")
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company", default=lambda self: self.env.company, index=True
    )

    # Names are unique per folder regardless of case, like on Windows. NULLS NOT
    # DISTINCT: otherwise two top folders (parent_id IS NULL) would never collide.
    _name_per_parent = models.UniqueIndex(
        '(parent_id, lower(name COLLATE "und-x-icu")) NULLS NOT DISTINCT WHERE active',
        "A folder with this name already exists here.",
    )

    @api.ondelete(at_uninstall=False)
    def _unlink_except_not_empty(self):
        # active_test=False: an archived folder or document still keeps its place.
        Document = self.env["int_filemanager.document"].with_context(active_test=False)
        for folder in self.with_context(active_test=False):
            if folder.child_ids or Document.search_count([("folder_id", "=", folder.id)]):
                raise UserError(
                    self.env._(
                        "The folder %(name)s is not empty. Move or delete what is in it first.",
                        name=folder.name,
                    )
                )
