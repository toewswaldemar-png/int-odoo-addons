from random import randint

from odoo import fields, models


class IntWorkbenchParameterTag(models.Model):
    _name = "int.workbench.parameter.tag"
    _description = "Tag of a process value"
    _order = "name"

    name = fields.Char(required=True)
    color = fields.Integer(default=lambda self: randint(1, 11))

    _name_unique = models.Constraint("UNIQUE (name)", "A tag exists once.")
