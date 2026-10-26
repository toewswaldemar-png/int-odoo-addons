from odoo import models


class ResPartner(models.Model):
    _inherit = ["res.partner", "int.filemanager.linkable"]
