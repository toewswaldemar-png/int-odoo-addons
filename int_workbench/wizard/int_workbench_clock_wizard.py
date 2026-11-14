from odoo import fields, models

from ..models.service_utils import notification


class IntWorkbenchClockWizard(models.TransientModel):
    _name = "int.workbench.clock.wizard"
    _description = "Set the clock of a controller"

    device_id = fields.Many2one("int.workbench.device", string="Controller", required=True, ondelete="cascade")
    time = fields.Datetime(string="New time", required=True, default=fields.Datetime.now, help="The time the controller is set to, in your time zone.")
    current = fields.Char(related="device_id.clock_local_time", string="The clock shows now")

    def action_set(self):
        """Ask the service to set the clock of the controller to the time in the dialog. The result shows in the log of the requests."""
        self.ensure_one()
        local = fields.Datetime.context_timestamp(self, self.time).strftime("%Y-%m-%dT%H:%M:%S")
        self.env["int.workbench.command"].create({"device_id": self.device_id.id, "action": "clock_set", "payload": {"local_time": local}})
        return notification(self.env._("Requested"), self.env._("The clock of %(name)s is being set to %(time)s.", name=self.device_id.name, time=local))
