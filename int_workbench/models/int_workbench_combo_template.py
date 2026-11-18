from odoo import api, fields, models


class IntWorkbenchComboTemplate(models.Model):
    _name = "int.workbench.combo.template"
    _description = "Combination of a device"
    _order = "device_id, code"

    device_id = fields.Many2one("int.workbench.device", string="Device", required=True, index=True, ondelete="cascade")
    code = fields.Char(string="Row code", required=True, copy=False, help="The code of the combination in the list of the process values of the device, for example K001.")
    name = fields.Char(required=True, help="What the list calls the combination, for example Zuluftventilator.")
    release_all = fields.Boolean(
        string="Release all other clamps",
        help="Choosing a level first releases every clamp of the device, and then clamps only the rows of the level. Off: only the rows that "
        "other levels of the combination have are released, and clamps of other rows stay.",
    )
    level_ids = fields.One2many("int.workbench.combo.template.level", "template_id", string="Levels", copy=True)
    row_ids = fields.One2many("int.workbench.parameter", "template_id", string="Rows of the device")

    _device_code_unique = models.Constraint("UNIQUE (device_id, code)", "The device has a combination with this code already.")

    @api.model_create_multi
    def create(self, vals_list):
        combos = super().create(vals_list)
        for combo in combos:
            # every combination has a level without rows: choosing it releases the rows, and the cell shows it while none is clamped
            if not combo.level_ids.filtered(lambda level: not level.step_ids):
                self.env["int.workbench.combo.template.level"].create({"template_id": combo.id, "sequence": 0, "name": self.env._("Off")})
        combos._sync_row()
        return combos

    def write(self, vals):
        result = super().write(vals)
        self._sync_row()
        return result

    def copy_data(self, default=None):
        """A copy is for another device, which the user chooses afterwards; until then it is for the same device, under a code that is free."""
        default = dict(default or {})
        if "code" not in default:
            for combo in self:
                taken = set(self.search([("device_id", "=", combo.device_id.id)]).mapped("code"))
                number = 2
                while f"{combo.code}-{number}" in taken:
                    number += 1
                default["code"] = f"{combo.code}-{number}"
        return super().copy_data(default)

    # ---- the device has the combination as a row of its process values; the levels are not copied to it, the row looks them up ----

    def _sync_row(self):
        """The device of the combination has its row, and no other device has: it is made where it is missing, taken away where the
        combination is for another device now, and named and coded as the combination says."""
        Parameter = self.env["int.workbench.parameter"].sudo()
        for combo in self:
            rows = Parameter.with_context(active_test=False).search([("template_id", "=", combo.id)])
            stale = rows.filtered(lambda row: row.device_id != combo.device_id)
            have = rows - stale
            stale.unlink()
            if not have:
                Parameter.create(
                    {
                        "device_id": combo.device_id.id,
                        "code": combo.code,
                        "label": combo.name,
                        "is_combo": True,
                        "can_clamp": True,
                        "status": "ok",
                        "sequence": 1,
                        "template_id": combo.id,
                    }
                )
            elif have.label != combo.name or have.code != combo.code:
                have.write({"label": combo.name, "code": combo.code})
