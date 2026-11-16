from odoo import api, fields, models

from ..models.int_workbench_command import CONSOLE_LIMIT


class IntWorkbenchConsoleWizard(models.TransientModel):
    _name = "int.workbench.console.wizard"
    _description = "Send a console command to a controller"

    device_id = fields.Many2one("int.workbench.device", string="Device", required=True, ondelete="cascade")
    command = fields.Char(required=True, size=CONSOLE_LIMIT, help="One line of the monitor of the controller, for example id all or sr.")
    changes = fields.Boolean(
        string="The command changes or clears something",
        help="Commands that only look (id, sr, db, dw, md ...) go the short way; every other command has to be marked.",
    )

    @api.onchange("command")
    def _onchange_command(self):
        """Take the line as it is typed: one line, no line ends."""
        if self.command:
            self.command = " ".join(self.command.split())

    def action_send(self):
        """Ask the service to send the command to the monitor of the controller and open the request, which holds the answer when it comes."""
        self.ensure_one()
        action = "console_write" if self.changes else "console"
        command = self.env["int.workbench.command"].create({"device_id": self.device_id.id, "action": action, "payload": {"command": self.command}})
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Console"),
            "res_model": "int.workbench.command",
            "res_id": command.id,
            "view_mode": "form",
            "target": "current",
        }
