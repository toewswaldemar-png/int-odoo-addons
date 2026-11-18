from odoo import api, fields, models

from .int_workbench_parameter import VALUE_DIGITS


class IntWorkbenchComboTemplateStep(models.Model):
    _name = "int.workbench.combo.template.step"
    _description = "Row of a level of a combination of a device"
    _order = "sequence, id"

    level_id = fields.Many2one("int.workbench.combo.template.level", string="Level", required=True, index=True, ondelete="cascade")
    sequence = fields.Integer(default=10)
    # Only to choose the row from the rows of the device. What is kept is the code of the row, so that a copy of the combination for another
    # device finds the row of that device by its code (a device that has no such row leaves the row out of the level).
    parameter_id = fields.Many2one(
        "int.workbench.parameter",
        string="Process value",
        ondelete="set null",
        help="Choose the row from the rows of the device. Only its code is kept.",
    )
    code = fields.Char(string="Row code", compute="_compute_code", store=True, readonly=False, required=True, precompute=True)
    value = fields.Float(digits=(16, VALUE_DIGITS), help="The value the row is clamped to when the level is chosen.")

    _level_code_unique = models.Constraint("UNIQUE (level_id, code)", "A level clamps a row once.")

    @api.depends("parameter_id")
    def _compute_code(self):
        for step in self:
            step.code = step.parameter_id.code or step.code
