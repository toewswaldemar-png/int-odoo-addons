from odoo import fields, models

from .service_utils import clean_text, upsert


class IntWorkbenchErrorStatus(models.Model):
    _name = "int.workbench.error.status"
    _description = "Status record of an error of a controller"
    _order = "device_id, rank, element"

    device_id = fields.Many2one("int.workbench.device", string="Device", required=True, index=True, ondelete="cascade", readonly=True)
    element = fields.Integer(
        required=True,
        readonly=True,
        help="The element of the error table of the controller, counted from 1 (the order of the error list of the project).",
    )
    rank = fields.Integer(
        readonly=True,
        help="The place in the controller's list: 0 is the error that came last, then the ones that came before, and the errors that "
        "never came follow in the order of the error list. -1 if the links of the records do not form one list.",
    )
    code = fields.Integer(readonly=True, index=True)
    text = fields.Char(string="Error", readonly=True)
    count = fields.Integer(readonly=True, help="How often the error has come since the error memory was cleared.")
    present = fields.Boolean(readonly=True, index=True, help="The error is there now.")
    newest = fields.Boolean(readonly=True, help="The error that is there now and came last.")
    reported = fields.Boolean(readonly=True, help="The original lists the record in its evaluation: the error is there, or it has been there.")
    level = fields.Integer(readonly=True, help="5 for an error that is there (A), 1 for one that went (C), 0 for one that never came.")
    wprio = fields.Integer(readonly=True, help="2 for the error that is there and came last, 1 for every other one that is there.")
    lmzus = fields.Integer(readonly=True, help="2 for an error that is there.")
    quit = fields.Boolean(readonly=True, help="The controller's flag for an acknowledged error. Never seen set.")
    raw = fields.Char(string="Bytes", readonly=True, help="The 10 bytes of the record as the controller holds them, in hexadecimal.")

    _device_element_unique = models.Constraint("UNIQUE (device_id, element)", "An element exists once per controller.")

    def _sync(self, device, snapshot):
        """Bring the status records of one controller to what the report says. A report whose error memory is not readable
        (it says so in its status) leaves the records as they are. Returns whether a record was created, changed or removed."""
        part = snapshot.get("errors_memory") if isinstance(snapshot, dict) else None
        if not isinstance(part, dict) or part.get("status") != "ok":
            return False
        items = part.get("status_all")
        if not isinstance(items, list):
            items = part.get("status_records")  # a service from before "status_all": only the records the original lists
        if not isinstance(items, list):
            return False
        wanted = {}
        for item in items:
            if not isinstance(item, dict) or not isinstance(item.get("index"), int) or isinstance(item.get("index"), bool):
                continue
            wanted[item["index"] + 1] = {
                "device_id": device.id,
                "rank": item["rank"] if isinstance(item.get("rank"), int) else -1,
                "code": item["code"] if isinstance(item.get("code"), int) else 0,
                "text": clean_text(item.get("text")),
                "count": item["count"] if isinstance(item.get("count"), int) else 0,
                "present": item.get("active") is True,
                "newest": item.get("newest") is True,
                "reported": item.get("reported") is True or item.get("active") is True or bool(item.get("level")),
                "level": item["level"] if isinstance(item.get("level"), int) else 0,
                "wprio": item["wprio"] if isinstance(item.get("wprio"), int) else 0,
                "lmzus": item["lmzus"] if isinstance(item.get("lmzus"), int) else 0,
                "quit": item.get("quit") is True,
                "raw": clean_text(item.get("raw")),
            }
        records = self.search([("device_id", "=", device.id)])
        gone = records.filtered(lambda record: record.element not in wanted)
        changed = bool(gone)
        gone.unlink()
        return bool(upsert(records - gone, "element", wanted)) or changed
