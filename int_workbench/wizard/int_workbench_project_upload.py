import base64

from odoo import fields, models
from odoo.exceptions import UserError

from odoo.addons.int_workbench.models import project_check as check


class IntWorkbenchProjectUpload(models.TransientModel):
    _name = "int.workbench.project.upload"
    _description = "Bring a project version in"

    vehicle = fields.Char(required=True, help="The folders above the project, for example BR145/Br145020/BR145020.")
    project = fields.Char(required=True, help="The name of the project folder, for example Pro_2.")
    attachment_ids = fields.Many2many(
        "ir.attachment", string="Files", help="The files of the project folder, or one ZIP archive of the folder. Files that the original makes itself (error data, reports) are left out."
    )
    state = fields.Selection([("upload", "Upload"), ("done", "Done")], default="upload")
    version_id = fields.Many2one("int.workbench.project.version", readonly=True)
    result = fields.Text(readonly=True)

    def action_upload(self):
        """Make a draft of the version that the files are (or find the one that is already there)."""
        self.ensure_one()
        if not self.attachment_ids:
            raise UserError(self.env._("Choose the files of the project, or a ZIP archive of the folder."))
        files = []
        archives = [attachment for attachment in self.attachment_ids if (attachment.name or "").lower().endswith(".zip")]
        if len(archives) > 1 or (archives and len(self.attachment_ids) > 1):
            raise UserError(self.env._("Bring in one ZIP archive alone, or the files of one project. A version at a time."))
        try:
            if archives:
                files = check.read_archive(base64.b64decode(archives[0].datas or b""))
            else:
                files = [(attachment.name, base64.b64decode(attachment.datas or b"")) for attachment in self.attachment_ids]
        except check.VersionError as error:
            raise UserError(self.env["int.workbench.project.version"]._error_text(error)) from error
        Version = self.env["int.workbench.project.version"]
        version, created = Version._from_files(self.vehicle, self.project, files, origin=self.env._("Upload by %s", self.env.user.name))
        # the uploads are only what the user brought in: the content now lives in the version
        self.attachment_ids.unlink()
        if created:
            result = self.env._("New draft %(name)s with %(count)d files.", name=version.display_name, count=version.file_count)
        else:
            result = self.env._("This version is already there as %s. The folder was added to its origins.", version.display_name)
        self.write({"state": "done", "version_id": version.id, "result": result})
        return {"type": "ir.actions.act_window", "res_model": self._name, "res_id": self.id, "view_mode": "form", "target": "new"}

    def action_show(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "int.workbench.project.version",
            "res_id": self.version_id.id,
            "view_mode": "form",
        }
