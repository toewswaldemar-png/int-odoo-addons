from odoo import fields, models

from .service_utils import clean_text, upsert


class IntWorkbenchFs2Record(models.Model):
    _name = "int.workbench.fs2.record"
    _description = "Record of a saved error file"
    _order = "file_id, entry"

    file_id = fields.Many2one("int.workbench.fs2.file", string="File", required=True, index=True, ondelete="cascade", readonly=True)
    device_id = fields.Many2one(related="file_id.device_id", store=True, index=True, string="Controller")
    entry = fields.Integer(required=True, readonly=True, help="The place of the record in the file, counted from 0.")
    kind = fields.Char(readonly=True, help="history or status.")
    wagon = fields.Char(readonly=True)
    train = fields.Char(readonly=True)
    date = fields.Char(readonly=True)
    time = fields.Char(readonly=True)
    iso = fields.Char(string="Date and time", readonly=True, index=True, help="Date and time of the record as the controller held them (no time zone), for example 2026-11-14T09:57:18.")
    code = fields.Integer(readonly=True, index=True)
    text = fields.Char(string="Error", readonly=True)
    priority = fields.Char(readonly=True, help="The letter of the evaluation view: A for an error that came, C for one that went.")
    count = fields.Integer(readonly=True)
    event = fields.Selection([("coming", "Coming"), ("going", "Going")], readonly=True, index=True)
    error_class = fields.Integer(string="Class", readonly=True)

    _file_entry_unique = models.Constraint("UNIQUE (file_id, entry)", "A record exists once per file.")

    def _sync(self, device, snapshot):
        """Bring the records of the files named in the report to what it says (the service sends the records of a few files at a time,
        the ones Odoo asked for). The file remembers what it was like then. Returns whether a record was created, changed or removed."""
        part = snapshot.get("fs2_records") if isinstance(snapshot, dict) else None
        if not isinstance(part, dict) or not isinstance(part.get("files"), dict):
            return False
        changed = False
        files = self.env["int.workbench.fs2.file"].search([("device_id", "=", device.id), ("name", "in", list(part["files"]))])
        for file in files:
            body = part["files"].get(file.name)
            if not isinstance(body, dict) or not isinstance(body.get("rows"), list):
                continue
            wanted = {}
            for item in body["rows"]:
                if not isinstance(item, dict) or not isinstance(item.get("index"), int) or isinstance(item.get("index"), bool):
                    continue
                wanted[item["index"]] = {
                    "file_id": file.id,
                    "kind": clean_text(item.get("kind")),
                    "wagon": clean_text(item.get("wagon")),
                    "train": clean_text(item.get("train")),
                    "date": clean_text(item.get("date")),
                    "time": clean_text(item.get("time")),
                    "iso": clean_text(item.get("iso")),
                    "code": item["code"] if isinstance(item.get("code"), int) else 0,
                    "text": clean_text(item.get("text")),
                    "priority": clean_text(item.get("p")),
                    "count": item["count"] if isinstance(item.get("count"), int) else 0,
                    "event": "coming" if item.get("z") == "K" else "going",
                    "error_class": item["class"] if isinstance(item.get("class"), int) else 0,
                }
            records = file.record_ids
            gone = records.filtered(lambda record: record.entry not in wanted)
            changed = bool(gone) or changed
            gone.unlink()
            changed = bool(upsert(records - gone, "entry", wanted)) or changed
            file.loaded_signature = file._signature()
        return changed
