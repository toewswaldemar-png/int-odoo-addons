from odoo import fields, models


class IntUiShowcaseCategory(models.Model):
    _name = "int.ui.showcase.category"
    _description = "UI Showcase Category"
    _order = "sequence, id"

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    icon = fields.Char(help="Font Awesome class, e.g. fa-cog.")
    # Records of this category get these properties (see `properties` on int.ui.showcase).
    showcase_properties_definition = fields.PropertiesDefinition("Showcase Properties")
