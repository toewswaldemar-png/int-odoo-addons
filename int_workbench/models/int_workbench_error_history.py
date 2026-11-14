from odoo import fields, models

from .service_utils import clean_text, upsert


class IntWorkbenchErrorHistory(models.Model):
    _name = "int.workbench.error.history"
    _description = "Entry of the error history of a controller"
    _order = "device_id, entry desc"

    device_id = fields.Many2one("int.workbench.device", string="Controller", required=True, index=True, ondelete="cascade", readonly=True)
    entry = fields.Integer(string="Entry", required=True, readonly=True, help="The place in the history of the controller, 1 is the oldest.")
    code = fields.Integer(readonly=True, index=True, help="The code of the error; 9997, 9998 and 9999 mark a restart, an initialization and a clearing.")
    text = fields.Char(string="Error", readonly=True)
    count = fields.Integer(readonly=True, help="How often the error had come at that time.")
    controller_time = fields.Char(
        readonly=True,
        help="Date and time of the clock of the controller, as it was set there (no time zone), for example 2026-11-14T09:57:18.",
    )
    event = fields.Selection([("coming", "Coming"), ("going", "Going")], readonly=True, index=True)
    priority = fields.Char(readonly=True, help="The letter of the evaluation view: A for an error that came, C for one that went.")
    raw = fields.Char(string="Bytes", readonly=True, help="The 26 bytes of the entry as the controller holds them, in hexadecimal.")

    _device_entry_unique = models.Constraint("UNIQUE (device_id, entry)", "An entry exists once per controller.")

    def _sync(self, device, snapshot):
        """Bring the history of one controller to what the report says; entries the report no longer has are removed.
        A report whose error memory is not readable (it says so in its status) leaves the entries as they are.
        Returns whether an entry was created, changed or removed."""
        part = snapshot.get("errors_memory") if isinstance(snapshot, dict) else None
        if not isinstance(part, dict) or part.get("status") != "ok" or not isinstance(part.get("history"), list):
            return False
        wanted = {}
        for position, item in enumerate(part["history"], start=1):
            if not isinstance(item, dict) or not isinstance(item.get("code"), int):
                continue
            wanted[position] = {
                "device_id": device.id,
                "code": item["code"],
                "text": clean_text(item.get("text")),
                "count": item["count"] if isinstance(item.get("count"), int) else 0,
                "controller_time": clean_text(item.get("time")),
                "event": "coming" if item.get("z") == "K" else "going",
                "priority": clean_text(item.get("p")),
                "raw": clean_text(item.get("raw")),
            }
        records = self.search([("device_id", "=", device.id)])
        gone = records.filtered(lambda record: record.entry not in wanted)
        changed = bool(gone)
        gone.unlink()
        return bool(upsert(records - gone, "entry", wanted)) or changed
