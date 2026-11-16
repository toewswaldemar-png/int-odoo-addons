from odoo import fields, models


class IntUiShowcaseStage(models.Model):
    _name = "int.ui.showcase.stage"
    _description = "UI Showcase Stage"
    _order = "sequence, id"

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    fold = fields.Boolean("Folded in Kanban")
    # Days after which a record in this stage is marked as rotting (0 disables it).
    rotting_threshold_days = fields.Integer("Days to rot", default=0)
