from odoo import api, fields, models
from odoo.exceptions import UserError

from ..tools.clash import clash_summary


class IntFilemanagerMove(models.TransientModel):
    """The dialog "Move to...": the documents or folders ticked in a list, and the folder they go to.

    Built like ``crm.lead.lost``: the records come in through the context of the action
    (``default_document_ids`` / ``default_folder_ids``) and the button acts on them. Nothing is
    checked here: ``write`` of the document and of the folder checks the target (the rights of the
    user, the target in use, the names, the company, the cycle), all or nothing.
    """

    _name = "int.filemanager.move"
    _description = "Filemanager: move to a folder"

    document_ids = fields.Many2many("int.filemanager.document", string="Documents")
    folder_ids = fields.Many2many("int.filemanager.folder", string="Folders")
    target_folder_id = fields.Many2one(
        "int.filemanager.folder",
        string="Move to",
        help="The folder that takes them. For folders, none is the top level.",
    )
    summary = fields.Char(compute="_compute_summary")

    @api.depends("document_ids", "folder_ids")
    def _compute_summary(self):
        for move in self:
            records = move.document_ids or move.folder_ids
            names = clash_summary(sorted(records.mapped("name"), key=str.lower))
            if move.document_ids:
                move.summary = self.env._("Documents (%(count)s): %(names)s", count=len(records), names=names)
            elif move.folder_ids:
                move.summary = self.env._("Folders (%(count)s): %(names)s", count=len(records), names=names)
            else:
                move.summary = False

    def action_move(self):
        """Put the documents (or the folders) into the target folder, then reload the view."""
        self.ensure_one()
        if not (self.document_ids or self.folder_ids):
            raise UserError(self.env._("Select at least one document or folder."))
        if self.document_ids:
            if not self.target_folder_id:
                raise UserError(self.env._("Choose the folder to move the documents to."))
            self.document_ids.write({"folder_id": self.target_folder_id.id})
        if self.folder_ids:
            self.folder_ids.write({"parent_id": self.target_folder_id.id})
        # The search panel shows the tree and the counts of the folders: only a reload of the
        # whole view brings them up to date.
        return {"type": "ir.actions.client", "tag": "soft_reload"}
