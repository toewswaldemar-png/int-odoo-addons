from odoo import fields, models

from .service_utils import as_text, parse_time, upsert


class IntWorkbenchUser(models.Model):
    _name = "int.workbench.user"
    _description = "Account of the service"
    _order = "device_id, name"

    device_id = fields.Many2one("int.workbench.device", string="Controller", required=True, index=True, ondelete="cascade", readonly=True)
    name = fields.Char(string="Account", required=True, readonly=True)
    roles = fields.Char(readonly=True, help="The roles of the account in the service, for example read, clamp.")
    disabled = fields.Boolean(readonly=True, help="The account is locked in the service.")
    created_at = fields.Datetime(string="Created in the service", readonly=True)
    changed_at = fields.Datetime(string="Changed in the service", readonly=True)

    _device_name_unique = models.Constraint("UNIQUE (device_id, name)", "An account exists once per service.")

    def _fetch(self, device):
        """Bring the accounts of one controller's service to what the service says; the accounts are kept and changed there only."""
        answer = device._service_request("GET", "/api/v1/users")
        wanted = {}
        for entry in answer.get("users") or []:
            if isinstance(entry, dict) and isinstance(entry.get("name"), str):
                wanted[entry["name"]] = {
                    "device_id": device.id,
                    "roles": as_text(entry.get("roles")),
                    "disabled": bool(entry.get("disabled")),
                    "created_at": parse_time(entry.get("created_at")),
                    "changed_at": parse_time(entry.get("changed_at")),
                }
        # sudo: int.workbench.user: the mirror is written by the button of a manager, the records themselves are read-only
        users = self.sudo().search([("device_id", "=", device.id)])
        upsert(users, "name", wanted)
        users.filtered(lambda user: user.name not in wanted).unlink()
