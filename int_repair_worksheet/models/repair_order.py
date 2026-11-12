from odoo import models


class RepairOrder(models.Model):
    _inherit = "repair.order"

    def action_open_be01412(self):
        self.ensure_one()
        self.check_access("read")
        worksheet = self.env["repair.worksheet"].search([("repair_id", "=", self.id)], limit=1)
        if not worksheet:
            worksheet = self.env["repair.worksheet"].create({"repair_id": self.id})
        return worksheet.action_open_editor()
