from odoo import fields, models
from odoo.exceptions import UserError

from ..models.int_workbench_command import CAN_ACTIONS
from ..models.service_utils import notification


class IntWorkbenchCanWizard(models.TransientModel):
    _name = "int.workbench.can.wizard"
    _description = "Stop, start or baptize the CAN bus of a controller"

    device_id = fields.Many2one("int.workbench.device", string="Controller", required=True, ondelete="cascade")
    action = fields.Selection(
        [("stop", "Stop the bus"), ("start", "Start the bus"), ("baptize", "Baptize the modules")],
        required=True,
        default="stop",
        help="Stopping the bus takes the modules off it until it is started again; baptizing gives every module its number.",
    )

    def action_send(self):
        """Ask the service to do what the dialog says. The result shows in the log of the requests."""
        self.ensure_one()
        if self.action not in CAN_ACTIONS:
            raise UserError(self.env._("Choose what to do with the CAN bus."))
        self.env["int.workbench.command"].create({"device_id": self.device_id.id, "action": "can_control", "payload": {"action": self.action}})
        return notification(self.env._("Requested"), self.env._("The CAN bus of %s is being controlled.", self.device_id.name))
