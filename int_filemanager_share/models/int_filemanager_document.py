from odoo import fields, models

# Set by the upload of the share only, never through RPC (see ``write``).
SHARE_FIELDS = ("share_id",)


class IntFilemanagerDocument(models.Model):
    _name = "int.filemanager.document"
    _inherit = ["int.filemanager.document", "int.filemanager.shareable"]
    _share_target = "document_id"

    # The share (link for guests) that a guest uploaded the file through; empty for all others.
    share_id = fields.Many2one(
        "int.filemanager.share",
        string="Uploaded through",
        readonly=True,
        copy=False,
        index="btree_not_null",
        ondelete="set null",
    )

    def write(self, vals):
        # ``readonly`` holds in the interface only: through RPC a user could say that a file came
        # in through a share. As in the core, drop such values; the upload runs as superuser.
        if not self.env.su:
            vals = {key: value for key, value in vals.items() if key not in SHARE_FIELDS}
        return super().write(vals)

    def action_share(self):
        """The share dialog of one file: the list has the button for the ticked rows too."""
        self._check_one_selected()
        return super().action_share()
