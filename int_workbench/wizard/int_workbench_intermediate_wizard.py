from odoo import api, fields, models
from odoo.exceptions import UserError


class IntWorkbenchIntermediateWizard(models.TransientModel):
    _name = "int.workbench.intermediate.wizard"
    _description = "Write an intermediate value into a controller"

    intermediate_id = fields.Many2one("int.workbench.intermediate", string="Value", required=True, ondelete="cascade")
    device_id = fields.Many2one(related="intermediate_id.device_id", string="Device")
    name = fields.Char(related="intermediate_id.name")
    address = fields.Char(related="intermediate_id.address")
    format = fields.Selection(related="intermediate_id.format")
    current = fields.Char(compute="_compute_current", string="Now")
    text = fields.Char(
        string="New value",
        help="In the format of the row: bits (blanks and points may be typed), a number ($ before hex digits), a percent value or hex "
        "digits. Nothing at all is a zero. What does not fit is cut to the low byte or word.",
    )

    @api.depends("intermediate_id.text", "intermediate_id.answered")
    def _compute_current(self):
        for wizard in self:
            row = wizard.intermediate_id
            wizard.current = row.text if row.answered else ""

    def action_send(self):
        """Ask the service to write the value, in the way the editing of the original does. How it ended is in the log of the requests."""
        self.ensure_one()
        row = self.intermediate_id
        if not row.device_id.cap_intermediate_write:
            raise UserError(self.env._("The controller %s may not be written to in this way.", row.device_id.name))
        self.env["int.workbench.command"].create(
            {
                "device_id": row.device_id.id,
                "action": "intermediate_write",
                "payload": {"name": row.name, "operand": row.address, "byte": row.is_byte, "format": row.format, "text": self.text or ""},
            }
        )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": self.env._("Requested"),
                "message": self.env._("%(name)s of %(device)s is being written.", name=row.name, device=row.device_id.name),
                "type": "success",
                "sticky": False,
            },
        }
