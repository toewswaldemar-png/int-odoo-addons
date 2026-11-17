from odoo import fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    int_workbench_device_id = fields.Many2one(
        "int.workbench.device",
        string="Last device of the Workbench",
        copy=False,
        ondelete="set null",
        help="The device whose list the user opened last from its form. The menu of the process values opens this device.",
    )
