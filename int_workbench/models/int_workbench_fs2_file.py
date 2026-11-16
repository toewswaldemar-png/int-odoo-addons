from odoo import fields, models
from odoo.exceptions import AccessError, UserError

from .service_utils import clean_text, upsert

TECHNICIAN_GROUP = "int_workbench.int_workbench_group_technician"


class IntWorkbenchFs2File(models.Model):
    _name = "int.workbench.fs2.file"
    _description = "Saved error file of a controller"
    _order = "device_id, name"

    device_id = fields.Many2one("int.workbench.device", string="Device", required=True, index=True, ondelete="cascade", readonly=True)
    name = fields.Char(string="File", required=True, readonly=True, help="The name of the file in the project folder of the service.")
    date = fields.Char(string="Date", readonly=True, help="The date the error memory was read, as the file holds it.")
    time = fields.Char(string="Time", readonly=True)
    wagon = fields.Char(readonly=True)
    train = fields.Char(readonly=True)
    count = fields.Integer(string="Records", readonly=True)
    kind = fields.Char(readonly=True, help="history or status.")
    mode = fields.Integer(readonly=True)
    controller_type = fields.Char(readonly=True, help="The type of the controller the file was read from.")
    loaded_signature = fields.Char(readonly=True, copy=False, help="What the file was like when its records were fetched. If it differs, the service is asked for them again.")
    record_ids = fields.One2many("int.workbench.fs2.record", "file_id", string="Records in the file")

    _device_name_unique = models.Constraint("UNIQUE (device_id, name)", "A file exists once per controller.")

    def _signature(self):
        """Return what tells that the file is still the one whose records were fetched."""
        self.ensure_one()
        return f"{self.count}|{self.date}|{self.time}|{self.wagon}|{self.train}|{self.kind}"

    def action_delete(self):
        """The button of the list: ask the service to move the files shown as selected to its folder of deleted files. One request
        per controller; the files go away from the list when the service has done it and has reported."""
        if not self.env.user.has_group(TECHNICIAN_GROUP):
            raise AccessError(self.env._("Only a technician may delete error files."))
        if not self:
            raise UserError(self.env._("Select the files to delete."))
        for device, files in self.grouped("device_id").items():
            self.env["int.workbench.command"].create({"device_id": device.id, "action": "fs2_delete", "payload": {"names": files.mapped("name")}})
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": self.env._("Requested"),
                "message": self.env._("%s file(s) are being moved to the folder of deleted files.", len(self)),
                "type": "info",
                "sticky": False,
            },
        }

    def _sync(self, device, snapshot):
        """Bring the list of saved error files of one controller to what the report says (the records come separately). A report whose
        list is not readable leaves the files as they are. Returns whether a file was created, changed or removed."""
        part = snapshot.get("fs2_files") if isinstance(snapshot, dict) else None
        if not isinstance(part, dict) or not isinstance(part.get("files"), list):
            return False
        wanted = {}
        for item in part["files"]:
            if not isinstance(item, dict) or not isinstance(item.get("name"), str) or not item["name"]:
                continue
            wanted[clean_text(item["name"])] = {
                "device_id": device.id,
                "date": clean_text(item.get("date")),
                "time": clean_text(item.get("time")),
                "wagon": clean_text(item.get("wagon")),
                "train": clean_text(item.get("train")),
                "count": item["count"] if isinstance(item.get("count"), int) else 0,
                "kind": clean_text(item.get("kind")),
                "mode": item["mode"] if isinstance(item.get("mode"), int) else 0,
                "controller_type": clean_text(item.get("device")),
            }
        records = self.search([("device_id", "=", device.id)])
        gone = records.filtered(lambda record: record.name not in wanted)
        changed = bool(gone)
        gone.unlink()
        return bool(upsert(records - gone, "name", wanted)) or changed
