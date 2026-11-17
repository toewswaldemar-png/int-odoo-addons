import base64

from odoo import fields, models
from odoo.exceptions import UserError


class IntWorkbenchSoftwareUpload(models.TransientModel):
    _name = "int.workbench.software.upload"
    _description = "Import programs of the controllers"

    attachment_ids = fields.Many2many("ir.attachment", string="Files", help="Images (S-Record, whatever the name and the extension) and program texts.")
    state = fields.Selection([("upload", "Upload"), ("done", "Done")], default="upload")
    software_ids = fields.Many2many("int.workbench.software", string="Programs", help="The programs the files are (new or already there).")
    result = fields.Text(readonly=True)

    def action_upload(self):
        """Read every file and make a record of each program that is not there yet. Files that are not programs are named, not hidden."""
        self.ensure_one()
        if not self.attachment_ids:
            raise UserError(self.env._("Choose at least one file."))
        Software = self.env["int.workbench.software"]
        lines, found = [], Software
        for attachment in self.attachment_ids:
            try:
                record, created = Software._from_file(attachment.name, base64.b64decode(attachment.datas or b""))
            except UserError as error:
                lines.append("× " + str(error.args[0]))
                continue
            found |= record
            if created:
                lines.append("+ " + self.env._("%(file)s: new program %(name)s", file=attachment.name, name=record.name))
            else:
                lines.append("= " + self.env._("%(file)s: is already there as %(name)s", file=attachment.name, name=record.name))
        # the uploads are only what the user brought in: they are not kept as files of their own
        self.attachment_ids.unlink()
        self.write({"state": "done", "software_ids": [(6, 0, found.ids)], "result": "\n".join(lines)})
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_show(self):
        """Open the list of the programs that the files are."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Software"),
            "res_model": "int.workbench.software",
            "view_mode": "list,form",
            "domain": [("id", "in", self.software_ids.ids)],
        }
