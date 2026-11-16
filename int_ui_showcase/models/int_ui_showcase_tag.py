from random import randint

from odoo import fields, models


class IntUiShowcaseTag(models.Model):
    _name = "int.ui.showcase.tag"
    _description = "UI Showcase Tag"
    _order = "name"

    def _default_color(self):
        return randint(1, 11)

    name = fields.Char(required=True, translate=True)
    color = fields.Integer(default=_default_color)
