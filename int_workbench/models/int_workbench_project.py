from odoo import api, fields, models

from .service_utils import as_text, parse_time, upsert


class IntWorkbenchProject(models.Model):
    _name = "int.workbench.project"
    _description = "Version in the project library of the service"
    _order = "vehicle, project, added_at desc"

    device_id = fields.Many2one("int.workbench.device", string="Controller", required=True, index=True, ondelete="cascade", readonly=True)
    checksum = fields.Char(required=True, readonly=True, help="The checksum of the definition files; it names the version in the library of the service.")
    short_id = fields.Char(compute="_compute_short_id", string="Id")
    vehicle = fields.Char(readonly=True, index=True, help="The folders above the project, from the place the version was first brought in from.")
    project = fields.Char(readonly=True, index=True)
    added_at = fields.Datetime(string="Added in the service", readonly=True)
    size = fields.Integer(string="Size (bytes)", readonly=True)
    file_count = fields.Integer(string="Files", readonly=True)
    rows = fields.Integer(string="Entries", readonly=True, help="The monitor entries of the project; 0 if it does not load.")
    loadable = fields.Boolean(readonly=True, help="The service can load the version.")
    load_error = fields.Char(string="Why not", readonly=True, help="Why the version does not load.")
    origins = fields.Text(string="Origin", readonly=True, help="The folders the version was brought in from, below the root folder of the service.")

    _device_checksum_unique = models.Constraint("UNIQUE (device_id, checksum)", "A version exists once per service.")

    @api.depends("checksum")
    def _compute_short_id(self):
        for project in self:
            project.short_id = (project.checksum or "")[:8]

    @api.depends("short_id", "project")
    def _compute_display_name(self):
        for project in self:
            project.display_name = f"{project.project or ''} {project.short_id or ''}".strip()

    def _fetch(self, device):
        """Bring the versions of the project library of one controller's service into the records.

        A version that the service no longer lists is removed; the service does not delete versions, so this is only a repair.
        """
        answer = device._service_request("GET", "/api/v1/projects")
        wanted = {}
        for entry in answer.get("projects") or []:
            if not isinstance(entry, dict) or not isinstance(entry.get("id"), str):
                continue
            origins = [origin for origin in entry.get("origins") or [] if isinstance(origin, dict) and isinstance(origin.get("path"), str)]
            vehicle, _slash, project = (origins[0]["path"].rpartition("/") if origins else ("", "", ""))
            wanted[entry["id"]] = {
                "device_id": device.id,
                "vehicle": vehicle,
                "project": project,
                "added_at": parse_time(entry.get("added_at")),
                "size": entry.get("size") if isinstance(entry.get("size"), int) else 0,
                "file_count": entry.get("file_count") if isinstance(entry.get("file_count"), int) else 0,
                "rows": entry.get("rows") if isinstance(entry.get("rows"), int) else 0,
                "loadable": bool(entry.get("loadable")),
                "load_error": as_text(entry.get("load_error") or entry.get("problem")),
                "origins": "\n".join(origin["path"] for origin in origins),
            }
        # sudo: int.workbench.project: the mirror is written by the button of a manager, the records themselves are read-only
        projects = self.sudo().search([("device_id", "=", device.id)])
        upsert(projects, "checksum", wanted)
        projects.filtered(lambda version: version.checksum not in wanted).unlink()
