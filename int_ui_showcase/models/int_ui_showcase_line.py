from odoo import api, fields, models


class IntUiShowcaseLine(models.Model):
    _name = "int.ui.showcase.line"
    _description = "UI Showcase Line"
    _order = "sequence, id"

    showcase_id = fields.Many2one("int.ui.showcase", required=True, ondelete="cascade", index=True)
    sequence = fields.Integer(default=10)
    name = fields.Char(required=True)
    quantity = fields.Float(default=1.0)
    currency_id = fields.Many2one(related="showcase_id.currency_id")
    price_unit = fields.Monetary()
    subtotal = fields.Monetary(compute="_compute_subtotal", store=True)

    @api.depends("quantity", "price_unit")
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line.quantity * line.price_unit
