from odoo import fields, models


class IntKeepassGroup(models.Model):
    _name = "int.keepass.group"
    _description = "KeePass Group"
    _inherit = ["int.keepass.virtual"]
    _auto = False
    _table_query = "0"
    _order = "name, id"
    _data_key = "groups"

    name = fields.Char(compute="_compute_values")
    parent_id = fields.Many2one("int.keepass.group", string="Parent Group", compute="_compute_values")

    def _compute_values(self):
        for record in self:
            row = record._row()
            record.name = row.get("name", False)
            record.parent_id = row.get("parent_id", False)
