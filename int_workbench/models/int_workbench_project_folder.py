from odoo import api, fields, models


class IntWorkbenchProjectFolder(models.Model):
    _name = "int.workbench.project.folder"
    _description = "Project of a vehicle"
    _order = "vehicle, name"

    name = fields.Char(string="Project", required=True, help="The name of the project folder, for example Pro_2.")
    vehicle = fields.Char(required=True, index=True, help="The folders above the project, for example BR145/Br145020/BR145020.")
    version_ids = fields.One2many("int.workbench.project.version", "folder_id", string="Versions", readonly=True)
    version_count = fields.Integer(compute="_compute_version_count")
    note = fields.Text()

    _vehicle_name_unique = models.Constraint("UNIQUE (vehicle, name)", "A project exists once for a vehicle.")

    @api.depends("version_ids")
    def _compute_version_count(self):
        counts = {
            folder.id: count
            for folder, count in self.env["int.workbench.project.version"]._read_group([("folder_id", "in", self.ids)], ["folder_id"], ["__count"])
        }
        for folder in self:
            folder.version_count = counts.get(folder.id, 0)

    @api.depends("vehicle", "name")
    def _compute_display_name(self):
        for folder in self:
            folder.display_name = f"{folder.vehicle} / {folder.name}" if folder.vehicle else folder.name or ""

    def action_open_versions(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Versions"),
            "res_model": "int.workbench.project.version",
            "view_mode": "list,form",
            "domain": [("folder_id", "=", self.id)],
        }
