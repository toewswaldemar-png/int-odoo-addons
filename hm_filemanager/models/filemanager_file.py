from odoo import fields, models


class HmFilemanagerFile(models.Model):
    _name = "hm_filemanager.file"
    _description = "Filemanager-Dateimetadaten"

    path = fields.Char(
        required=True,
        index=True,
        help="Pfad relativ zum Filemanager-Stammverzeichnis.",
    )
    tag_ids = fields.Many2many("hm_filemanager.tag", string="Tags")

    _path_uniq = models.Constraint("UNIQUE(path)", "Für diesen Pfad existiert bereits ein Metadaten-Eintrag.")
