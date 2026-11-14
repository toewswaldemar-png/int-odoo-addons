from odoo import fields, models

from .service_utils import clean_text, upsert


class IntWorkbenchIntermediate(models.Model):
    _name = "int.workbench.intermediate"
    _description = "Intermediate value of a controller"
    _order = "device_id, sequence"

    device_id = fields.Many2one("int.workbench.device", string="Controller", required=True, index=True, ondelete="cascade", readonly=True)
    sequence = fields.Integer(required=True, readonly=True, help="The place in the list of intermediate values that the service reads, counted from 1.")
    name = fields.Char(readonly=True)
    address = fields.Char(readonly=True)
    kind = fields.Char(readonly=True)
    format = fields.Char(readonly=True, help="How the value is shown: B bits, H the text of the answer, P process value, and so on.")
    raw = fields.Char(string="Answer", readonly=True, help="What the controller answered, as it came.")
    text = fields.Char(readonly=True)
    value = fields.Float(readonly=True, digits=(16, 3))
    has_value = fields.Boolean(readonly=True, help="The service could turn the answer into a number.")
    unit = fields.Char(readonly=True)
    answered = fields.Boolean(readonly=True)
    locked = fields.Boolean(readonly=True)
    error = fields.Char(readonly=True)

    _device_sequence_unique = models.Constraint("UNIQUE (device_id, sequence)", "A place exists once per controller.")

    def _sync(self, device, snapshot):
        """Bring the intermediate values of one controller to what the report says. A report whose part is not readable leaves them as
        they are. Returns whether a row was created, changed or removed."""
        part = snapshot.get("intermediate") if isinstance(snapshot, dict) else None
        if not isinstance(part, dict) or part.get("status") != "ok" or not isinstance(part.get("items"), list):
            return False
        wanted = {}
        for position, item in enumerate(part["items"], start=1):
            if not isinstance(item, dict):
                continue
            value = item.get("value")
            has_value = isinstance(value, (int, float)) and not isinstance(value, bool)
            wanted[position] = {
                "device_id": device.id,
                "name": clean_text(item.get("name")),
                "address": clean_text(item.get("address")),
                "kind": clean_text(item.get("kind")),
                "format": clean_text(item.get("format")),
                "raw": clean_text(item.get("raw")),
                "text": clean_text(item.get("text")),
                "value": float(value) if has_value else 0.0,
                "has_value": has_value,
                "unit": clean_text(item.get("unit")),
                "answered": item.get("answered") is True,
                "locked": item.get("locked") is True,
                "error": clean_text(item.get("error")),
            }
        records = self.search([("device_id", "=", device.id)])
        gone = records.filtered(lambda record: record.sequence not in wanted)
        changed = bool(gone)
        gone.unlink()
        return bool(upsert(records - gone, "sequence", wanted)) or changed
