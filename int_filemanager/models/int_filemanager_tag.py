from odoo import fields, models


class IntFilemanagerTag(models.Model):
    _name = "int.filemanager.tag"
    _description = "Filemanager tag"
    _order = "name"

    name = fields.Char(required=True)
    color = fields.Integer(default=0)

    _name_uniq = models.Constraint("UNIQUE(name)", "A tag with this name already exists.")
