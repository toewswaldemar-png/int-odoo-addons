from odoo import api, fields, models
from odoo.exceptions import UserError


class IntFilemanagerFolder(models.Model):
    """A folder: an ordinary record with a parent.

    Who sees a folder (and its documents) is decided by record rules: a folder is open to all
    filemanager users, or only to the users and groups listed on it. Followers
    (``mail.thread``, the creator is one) see it too, the pattern of ``project.project``.
    A subfolder takes over what its parent says, unless it says otherwise itself.
    Filemanager administrators see everything.
    """

    _name = "int.filemanager.folder"
    _description = "Filemanager folder"
    _inherit = ["mail.thread"]
    _parent_store = True
    _order = "name"

    name = fields.Char(required=True)
    parent_id = fields.Many2one("int.filemanager.folder", index=True, ondelete="restrict")
    parent_path = fields.Char(index=True)
    child_ids = fields.One2many("int.filemanager.folder", "parent_id")
    document_ids = fields.One2many("int.filemanager.document", "folder_id")
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company", default=lambda self: self.env.company, index=True
    )
    access_mode = fields.Selection(
        [
            ("inherit", "Like the parent folder"),
            ("restricted", "Only the users and groups allowed"),
            ("open", "All filemanager users"),
        ],
        required=True,
        default="inherit",
        help="Who sees this folder and its documents. A top folder that is not open to all is "
        "seen by the users and groups listed on it and by its followers (and by the "
        "administrators).",
    )
    access_user_ids = fields.Many2many(
        "res.users",
        "int_filemanager_folder_access_user_rel",
        "folder_id",
        "user_id",
        string="Allowed users",
    )
    access_group_ids = fields.Many2many(
        "res.groups",
        "int_filemanager_folder_access_group_rel",
        "folder_id",
        "group_id",
        string="Allowed groups",
    )
    # The folder whose ``access_mode`` and followers decide for this one: itself, or the
    # nearest parent that does not say "like the parent". The record rules look at it.
    access_folder_id = fields.Many2one(
        "int.filemanager.folder",
        compute="_compute_access_folder_id",
        store=True,
        recursive=True,
        index=True,
    )

    # Names are unique per folder regardless of case, like on Windows. NULLS NOT
    # DISTINCT: otherwise two top folders (parent_id IS NULL) would never collide.
    _name_per_parent = models.UniqueIndex(
        '(parent_id, lower(name COLLATE "und-x-icu")) NULLS NOT DISTINCT WHERE active',
        "A folder with this name already exists here.",
    )

    @api.depends("access_mode", "parent_id.access_folder_id")
    def _compute_access_folder_id(self):
        for folder in self:
            inherits = folder.access_mode == "inherit" and folder.parent_id
            folder.access_folder_id = folder.parent_id.access_folder_id if inherits else folder

    @api.ondelete(at_uninstall=False)
    def _unlink_except_not_empty(self):
        # active_test=False: an archived folder or document still keeps its place.
        Document = self.env["int.filemanager.document"].with_context(active_test=False)
        for folder in self.with_context(active_test=False):
            if folder.child_ids or Document.search_count([("folder_id", "=", folder.id)]):
                raise UserError(
                    self.env._(
                        "The folder %(name)s is not empty. Move or delete what is in it first.",
                        name=folder.name,
                    )
                )
