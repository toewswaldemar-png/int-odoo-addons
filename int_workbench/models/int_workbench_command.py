import re

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

# The code of a row in the service: "0016", "4200", "9000".
ROW_CODE_PATTERN = re.compile(r"[A-Za-z0-9_-]{1,20}")
# What the page may fill in; everything else (state, user, times) is set by the server.
CLIENT_FIELDS = ("device_id", "code", "action", "value")
# A request that is about the controller and not about a row has this as its row: the clamp log shows it, the service ignores it.
CONTROLLER_CODE = "errors"


class IntWorkbenchCommand(models.Model):
    _name = "int.workbench.command"
    _description = "Clamp request for a controller"
    _order = "id desc"

    device_id = fields.Many2one("int.workbench.device", string="Controller", required=True, index=True, ondelete="cascade")
    user_id = fields.Many2one("res.users", string="Requested by", required=True, readonly=True, index=True, ondelete="restrict")
    code = fields.Char(string="Row", required=True)
    parameter_id = fields.Many2one(
        "int.workbench.parameter",
        string="Process value",
        readonly=True,
        index=True,
        ondelete="set null",
        help="The row of the controller this request is about, if the service has reported it. The service works with the code.",
    )
    action = fields.Selection([("set", "Clamp"), ("release", "Release"), ("clear_errors", "Clear error memory")], required=True)
    value = fields.Float(help="The value to clamp the row to (only for Clamp).")
    state = fields.Selection(
        [
            ("pending", "Waiting for the service"),
            ("sent", "Handed to the service"),
            ("done", "Done"),
            ("failed", "Failed"),
            ("unconfirmed", "Not confirmed"),
            ("unknown", "Result not reported"),
            ("expired", "Expired"),
        ],
        default="pending",
        required=True,
        readonly=True,
        index=True,
    )
    message = fields.Char(readonly=True)
    sent_at = fields.Datetime(readonly=True)
    done_at = fields.Datetime(readonly=True)

    @api.constrains("code")
    def _check_code(self):
        for command in self:
            if not ROW_CODE_PATTERN.fullmatch(command.code or ""):
                raise ValidationError(self.env._("The row %s is not a row code.", command.code))

    @api.model_create_multi
    def create(self, vals_list):
        """A request is made by the page (or by a program in the name of a user): who asked, and how it stands, is not up to them."""
        cleaned = []
        for vals in vals_list:
            vals = {key: value for key, value in vals.items() if key in CLIENT_FIELDS}
            vals["user_id"] = self.env.uid
            if vals.get("action") == "clear_errors":
                vals["code"] = CONTROLLER_CODE  # it is about the controller, not about a row
            cleaned.append(vals)
        # sudo: int.workbench.parameter: the row is looked up by its code, whoever asks may not read every row
        Parameter = self.env["int.workbench.parameter"].sudo()
        for vals in cleaned:
            if vals.get("device_id") and vals.get("code") and vals.get("action") != "clear_errors":
                vals["parameter_id"] = Parameter.search([("device_id", "=", vals["device_id"]), ("code", "=", vals["code"])], limit=1).id
        commands = super().create(cleaned)
        for command in commands:
            if not command.device_id.active:
                raise UserError(self.env._("The controller %s is archived.", command.device_id.name))
            # a controller whose service has not signed on has no family yet and is not refused (for clamping; clearing the error
            # memory is something a family has to say it can, as a service has to be started for it)
            device = command.device_id
            if command.action == "clear_errors":
                if not device.cap_error_memory:
                    raise UserError(self.env._("The controller %s cannot clear its error memory.", device.name))
            elif device.family_id and not device.cap_clamps:
                raise UserError(self.env._("The controller %s cannot be clamped.", device.name))
        return commands
