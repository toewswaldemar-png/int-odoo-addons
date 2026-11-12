from odoo import fields, models

from .service_utils import as_text, parse_time, upsert

# How many of the newest entries of the write log one fetch asks for (the service gives at most 1000).
LOG_LIMIT = 1000


class IntWorkbenchLog(models.Model):
    _name = "int.workbench.log"
    _description = "Entry of the write log of the service"
    _order = "device_id, entry_id desc"

    device_id = fields.Many2one("int.workbench.device", string="Controller", required=True, index=True, ondelete="cascade", readonly=True)
    entry_id = fields.Integer(string="Entry", required=True, readonly=True, help="The number of the entry in the log of the service.")
    started_at = fields.Datetime(readonly=True)
    finished_at = fields.Datetime(readonly=True)
    user = fields.Char(readonly=True, help="Empty if nobody was signed in; in brackets for the shared token or the local page.")
    roles = fields.Char(readonly=True)
    remote = fields.Char(readonly=True)
    device_ref = fields.Char(string="Controller id", readonly=True)
    route = fields.Char(readonly=True)
    kind = fields.Char(readonly=True, index=True)
    input = fields.Text(readonly=True, help="What was asked for. The service keeps no password and no file content in it.")
    outcome = fields.Char(readonly=True, index=True, help="running, done, not_confirmed, failed, rejected, denied or unknown.")
    status = fields.Integer(string="HTTP status", readonly=True)
    detail = fields.Char(readonly=True)

    _device_entry_unique = models.Constraint("UNIQUE (device_id, entry_id)", "An entry exists once per service.")

    def _fetch(self, device):
        """Bring the newest entries of the write log of one controller's service into the records; an entry that ended since is updated."""
        answer = device._service_request("GET", "/api/v1/audit", params={"limit": LOG_LIMIT})
        wanted = {}
        for entry in answer.get("entries") or []:
            if isinstance(entry, dict) and isinstance(entry.get("id"), int):
                wanted[entry["id"]] = {
                    "device_id": device.id,
                    "started_at": parse_time(entry.get("started_at")),
                    "finished_at": parse_time(entry.get("finished_at")),
                    "user": as_text(entry.get("user")),
                    "roles": as_text(entry.get("roles")),
                    "remote": as_text(entry.get("remote")),
                    "device_ref": as_text(entry.get("device")),
                    "route": as_text(entry.get("route")),
                    "kind": as_text(entry.get("kind")),
                    "input": as_text(entry.get("input")),
                    "outcome": as_text(entry.get("outcome")),
                    "status": entry.get("status") if isinstance(entry.get("status"), int) else 0,
                    "detail": as_text(entry.get("detail")),
                }
        # sudo: int.workbench.log: the mirror is written by the button of a manager, the records themselves are read-only
        known = self.sudo().search([("device_id", "=", device.id), ("entry_id", "in", list(wanted))])
        upsert(known, "entry_id", wanted)
