from odoo import fields, models
from odoo.exceptions import UserError

# How many folders one call of the service takes (the service allows 100; the import of a folder takes about a second).
IMPORT_PACKAGE = 25


class IntWorkbenchProjectImport(models.TransientModel):
    _name = "int.workbench.project.import"
    _description = "Bring the new project folders of the service into its library"

    device_id = fields.Many2one("int.workbench.device", string="Controller", required=True, ondelete="cascade")
    state = fields.Selection([("draft", "Ready"), ("done", "Done")], default="draft", readonly=True)
    result = fields.Text(readonly=True)

    def _reopen(self):
        """Return the action that shows this dialog again, with the result in it."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Take over new folders"),
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_import(self):
        """Ask the service for its project folders and bring the new ones into the library, in packages.

        The service checks every folder with its project loader; a folder that does not load is brought in as well, marked with
        the reason. The list of versions is fetched afresh afterwards.
        """
        self.ensure_one()
        device = self.device_id
        # the call carries the token of the service: only those who may change the controller may use it
        device.check_access("write")
        inventory = device._service_request("GET", "/api/v1/projects/inventory")
        new_paths = [
            item["path"]
            for item in inventory.get("items") or []
            if isinstance(item, dict) and item.get("state") == "new" and isinstance(item.get("path"), str)
        ]
        if not new_paths:
            raise UserError(self.env._("There are no new folders."))
        created = failed = 0
        lines = []
        for start in range(0, len(new_paths), IMPORT_PACKAGE):
            answer = device._service_request(
                "POST", "/api/v1/projects/import", payload={"paths": new_paths[start : start + IMPORT_PACKAGE]}
            )
            for item in answer.get("results") or []:
                if not isinstance(item, dict):
                    continue
                if item.get("ok"):
                    created += bool(item.get("created"))
                    if not item.get("loadable"):
                        lines.append(f"{item.get('path')}: {self.env._('brought in, does not load')}: {item.get('error') or ''}")
                else:
                    failed += 1
                    lines.append(f"{item.get('path')}: {self.env._('turned away')}: {item.get('error') or ''}")
        self.env["int.workbench.project"]._fetch(device)
        summary = self.env._("%(total)s folders, %(created)s new versions, %(failed)s turned away.", total=len(new_paths), created=created, failed=failed)
        self.write({"state": "done", "result": "\n".join([summary, *lines])})
        return self._reopen()
