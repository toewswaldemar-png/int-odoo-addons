from odoo import fields, models


class IntWorkbenchError(models.Model):
    _name = "int.workbench.error"
    _description = "Active error of a controller"
    _order = "device_id, word, bit"

    device_id = fields.Many2one("int.workbench.device", string="Controller", required=True, index=True, ondelete="cascade", readonly=True)
    word = fields.Char(string="Error word", required=True, readonly=True)
    bit = fields.Integer(required=True, readonly=True)
    text = fields.Char(string="Error", readonly=True)

    _device_word_bit_unique = models.Constraint("UNIQUE (device_id, word, bit)", "An error exists once per controller.")

    def _sync(self, device, snapshot):
        """Bring the errors of one controller to what the report says: the active errors are the rows, the others are removed."""
        wanted = {}
        if isinstance(snapshot, dict) and isinstance(snapshot.get("errors"), dict):
            for entry in snapshot["errors"].get("active") or []:
                if isinstance(entry, dict) and isinstance(entry.get("word"), str) and isinstance(entry.get("bit"), int):
                    wanted[entry["word"], entry["bit"]] = str(entry.get("text") or "")
        known = {(row.word, row.bit): row for row in self.search_fetch([("device_id", "=", device.id)], ["word", "bit", "text"])}
        for key, row in known.items():
            if key not in wanted:
                row.unlink()
            elif (row.text or "") != wanted[key]:
                row.write({"text": wanted[key]})
        self.create(
            [{"device_id": device.id, "word": word, "bit": bit, "text": text} for (word, bit), text in wanted.items() if (word, bit) not in known]
        )
