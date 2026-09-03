from odoo import _, fields, models


class IntFilemanagerLinkableMixin(models.AbstractModel):
    """Inherit this on any model to get a 'Verknüpfte Dateien' smart button
    counting/opening the int_filemanager.file records whose res_reference
    points back at the record - the reverse direction of the per-file
    "Verknüpfen mit..." action in the filemanager itself."""

    _name = "int_filemanager.linkable.mixin"
    _description = "Filemanager: verknüpfbar mit Dateien/Ordnern"

    int_filemanager_count = fields.Integer(
        string="Verknüpfte Dateien", compute="_compute_int_filemanager_count"
    )

    def _compute_int_filemanager_count(self):
        for record in self:
            record.int_filemanager_count = self.env["int_filemanager.file"].search_count(
                [("res_reference", "=", f"{record._name},{record.id}")]
            )

    def action_view_int_filemanager_files(self):
        self.ensure_one()
        return {
            "type": "ir.actions.client",
            "tag": "int_filemanager_browser",
            "name": _("Verknüpfte Dateien"),
            "params": {"domain": [["res_reference", "=", f"{self._name},{self.id}"]]},
        }
