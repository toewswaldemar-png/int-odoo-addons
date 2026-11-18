from odoo import fields, models


class IntWorkbenchComboTemplateLevel(models.Model):
    _name = "int.workbench.combo.template.level"
    _description = "Level of a combination of a device"
    _order = "sequence, id"

    template_id = fields.Many2one("int.workbench.combo.template", string="Combination", required=True, index=True, ondelete="cascade")
    device_id = fields.Many2one(related="template_id.device_id", string="Device")
    sequence = fields.Integer(default=10)
    name = fields.Char(required=True, help="What the list shows when the level is clamped, for example Stage 2 (60 %).")
    step_ids = fields.One2many("int.workbench.combo.template.step", "level_id", string="Rows", copy=True)
