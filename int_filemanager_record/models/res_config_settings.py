from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    int_filemanager_access_via_record = fields.Boolean(
        string="Access through linked records",
        help="Whoever may read a record (a contact, say) may also read the documents linked to "
        "it, without a right on their folder. Off: only the folders decide, and a file uploaded "
        "to a record is seen by those who see its upload folder.",
    )

    @api.model
    def get_values(self):
        res = super().get_values()
        rule = self.env.ref("int_filemanager_record.int_filemanager_document_rule_record")
        res["int_filemanager_access_via_record"] = rule.sudo().active
        return res

    def set_values(self):
        super().set_values()
        self.env["int.filemanager.link"]._toggle_access_via_record(
            self.int_filemanager_access_via_record
        )
