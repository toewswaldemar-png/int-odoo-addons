from odoo import fields, models


class IntFilemanagerStatus(models.Model):
    _name = "int_filemanager.status"
    _description = "Filemanager-Freigabestatus"
    _order = "sequence, id"

    name = fields.Char(required=True)
    color = fields.Integer(default=0)
    sequence = fields.Integer(default=10)

    _name_uniq = models.Constraint(
        "UNIQUE(name)", "Ein Status mit diesem Namen existiert bereits."
    )
