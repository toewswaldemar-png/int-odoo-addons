from odoo import api, fields, models


class IntWorkbenchParameterClamp(models.TransientModel):
    _name = "int.workbench.parameter.clamp"
    _description = "Clamp a process value of a controller"

    parameter_id = fields.Many2one("int.workbench.parameter", string="Process value", required=True, ondelete="cascade", readonly=True)
    device_id = fields.Many2one(related="parameter_id.device_id")
    analog = fields.Boolean(related="parameter_id.analog")
    value = fields.Float(
        digits=(16, 3),
        help="The value to clamp the row to. A digital row takes 0 or 1.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        """Start with the value the row is clamped to now, or else the value it has."""
        records = super().create(vals_list)
        for wizard in records:
            row = wizard.parameter_id
            wizard.value = row.clamp_value if row.clamped else row.value
        return records

    def action_clamp(self):
        """Ask the service to clamp the row to the value; the answer shows in the list and in the clamp log."""
        self.ensure_one()
        self.env["int.workbench.command"].create(
            {
                "device_id": self.parameter_id.device_id.id,
                "code": self.parameter_id.code,
                "action": "set",
                "value": self.value,
            }
        )
        return {"type": "ir.actions.act_window_close"}
