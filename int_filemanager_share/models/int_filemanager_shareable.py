from odoo import api, fields, models


class IntFilemanagerShareable(models.AbstractModel):
    """Mixin for what can be shared: folders and documents.

    It gives the button "Share" (the dialog of a new share with the target filled in) and the
    number of shares of the target with the action that lists them, as the mixin of the links does
    for the records that have documents. The model says which field of the share names it in
    ``_share_target``.
    """

    _name = "int.filemanager.shareable"
    _description = "Folder or document that can be shared"

    _share_target = None  # the field of int.filemanager.share that points to this model
    share_count = fields.Integer(string="Shares", compute="_compute_share_count")

    @api.depends_context("uid")
    def _compute_share_count(self):
        # The shares the user sees (the rule of the share: the own ones, all for the
        # administrators), the active ones: a blocked share is not counted.
        Share = self.env["int.filemanager.share"]
        counts = {}
        if Share.has_access("read"):
            counts = dict(
                Share._read_group(
                    [(self._share_target, "in", self.ids)], [self._share_target], ["__count"]
                )
            )
        for record in self:
            record.share_count = counts.get(record, 0)

    def action_share(self):
        """The dialog of a new share for this folder or file: it starts with what most shares are
        (see and download, no end, no password); "Create the link" saves it and shows the
        address."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Share"),
            "res_model": "int.filemanager.share",
            "views": [(self.env.ref("int_filemanager_share.int_filemanager_share_view_form_dialog").id, "form")],
            "target": "new",
            "context": {f"default_{self._share_target}": self.id},
        }

    def action_open_shares(self):
        """The shares of this folder or file."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Shares"),
            "res_model": "int.filemanager.share",
            "view_mode": "list,form",
            "domain": [(self._share_target, "=", self.id)],
            "context": {f"default_{self._share_target}": self.id},
        }
