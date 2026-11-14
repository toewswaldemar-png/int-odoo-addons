from odoo import fields, models

from ..models.int_workbench_command import TRAIN_LIMIT, WAGON_LIMIT
from ..models.service_utils import notification


class IntWorkbenchFs2Wizard(models.TransientModel):
    _name = "int.workbench.fs2.wizard"
    _description = "Save the error memory of a controller as error files"

    device_id = fields.Many2one("int.workbench.device", string="Controller", required=True, ondelete="cascade")
    wagon = fields.Char(string="Wagon number", required=True, default="000", size=WAGON_LIMIT, help="The number the files are saved under (the original asks for it too).")
    train = fields.Char(string="Train", size=TRAIN_LIMIT)
    complete = fields.Boolean(string="Complete", default=True, help="Save the history and the status records; without it only the history.")

    def action_save(self):
        """Ask the service to read the error memory of the controller and save it as error files in its project folder."""
        self.ensure_one()
        self.env["int.workbench.command"].create(
            {
                "device_id": self.device_id.id,
                "action": "fs2_save",
                "payload": {"wagon": self.wagon, "train": self.train or "", "complete": self.complete},
            }
        )
        return notification(self.env._("Requested"), self.env._("The error memory of %s is being saved.", self.device_id.name))
