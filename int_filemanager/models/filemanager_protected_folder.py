from odoo import api, fields, models
from odoo.exceptions import ValidationError


class IntFilemanagerProtectedFolder(models.Model):
    _name = "int_filemanager.protected_folder"
    _description = "Filemanager geschützter Ordner"
    _order = "path"

    path = fields.Char(
        required=True,
        index=True,
        help="Pfad relativ zum Filemanager-Stammverzeichnis (z.B. 'Buchhaltung' oder "
        "'Buchhaltung/Gehaltsdaten'). Die Wurzel selbst kann nicht geschützt werden.",
    )
    read_group_ids = fields.Many2many(
        "res.groups",
        "int_filemanager_pf_read_rel",
        "folder_id",
        "group_id",
        string="Lesen erlaubt für",
    )
    write_group_ids = fields.Many2many(
        "res.groups",
        "int_filemanager_pf_write_rel",
        "folder_id",
        "group_id",
        string="Schreiben erlaubt für",
    )
    unlink_group_ids = fields.Many2many(
        "res.groups",
        "int_filemanager_pf_unlink_rel",
        "folder_id",
        "group_id",
        string="Löschen erlaubt für",
    )

    _path_uniq = models.Constraint("UNIQUE(path)", "Für diesen Pfad existiert bereits ein Schutz-Eintrag.")

    @api.constrains("path")
    def _check_path(self):
        for rec in self:
            path = (rec.path or "").strip()
            if not path:
                raise ValidationError("Die Wurzel kann nicht als geschützter Ordner registriert werden.")
            if path.startswith("/") or path.endswith("/"):
                raise ValidationError("Der Pfad darf nicht mit '/' beginnen oder enden.")

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        self._rebuild_acl_rules()
        return records

    def write(self, vals):
        res = super().write(vals)
        self._rebuild_acl_rules()
        return res

    def unlink(self):
        res = super().unlink()
        self.env["int_filemanager.protected_folder"]._rebuild_acl_rules()
        return res

    def _rebuild_acl_rules(self):
        from ..acl_rules import rebuild_rules

        rebuild_rules(self.env)
