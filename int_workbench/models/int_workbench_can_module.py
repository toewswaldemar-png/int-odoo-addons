from odoo import fields, models

from .service_utils import clean_text, upsert


class IntWorkbenchCanModule(models.Model):
    _name = "int.workbench.can.module"
    _description = "CAN module of a controller"
    _order = "device_id, number"

    device_id = fields.Many2one("int.workbench.device", string="Controller", required=True, index=True, ondelete="cascade", readonly=True)
    number = fields.Integer(required=True, readonly=True, help="The place of the module in the list of the controller.")
    type_name = fields.Char(string="Type", readonly=True)
    type_code = fields.Integer(string="Type code", readonly=True)
    serial = fields.Char(string="Serial number", readonly=True)
    mc_sw = fields.Char(string="Controller software", readonly=True, help="The software of the controller the module reports.")
    sw = fields.Char(string="Software", readonly=True)
    hw = fields.Char(string="Hardware", readonly=True)
    can_status = fields.Char(string="CAN status", readonly=True, help="The status byte of the module as two hexadecimal digits.")

    _device_number_unique = models.Constraint("UNIQUE (device_id, number)", "A module exists once per controller.")

    def _sync(self, device, snapshot):
        """Bring the CAN modules of one controller to what the report says. A report whose CAN part is not readable (it says so in its
        status) leaves the modules as they are. Returns whether a module was created, changed or removed."""
        part = snapshot.get("can") if isinstance(snapshot, dict) else None
        if not isinstance(part, dict) or part.get("status") != "ok" or not isinstance(part.get("modules"), list):
            return False
        wanted = {}
        for item in part["modules"]:
            if not isinstance(item, dict) or not isinstance(item.get("number"), int) or isinstance(item.get("number"), bool):
                continue
            wanted[item["number"]] = {
                "device_id": device.id,
                "type_name": clean_text(item.get("type_name")),
                "type_code": item["type"] if isinstance(item.get("type"), int) else 0,
                "serial": clean_text(item.get("serial")),
                "mc_sw": clean_text(item.get("mc_sw")),
                "sw": clean_text(item.get("sw")),
                "hw": clean_text(item.get("hw")),
                "can_status": clean_text(item.get("can_status")),
            }
        records = self.search([("device_id", "=", device.id)])
        gone = records.filtered(lambda record: record.number not in wanted)
        changed = bool(gone)
        gone.unlink()
        return bool(upsert(records - gone, "number", wanted)) or changed
