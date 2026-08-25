from odoo import fields, models


class HmFilemanagerTag(models.Model):
    _name = "hm_filemanager.tag"
    _description = "Filemanager-Tag"
    _order = "name"

    name = fields.Char(required=True)
    color = fields.Integer(default=0)

    _name_uniq = models.Constraint("UNIQUE(name)", "Ein Tag mit diesem Namen existiert bereits.")
