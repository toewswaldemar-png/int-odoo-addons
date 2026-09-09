from odoo import fields, models


class ProductLegacyManufacturerRef(models.Model):
    _name = "product.legacy.manufacturer.ref"
    _description = "Hersteller-/Ident-Referenz aus dem alten ERP"

    product_tmpl_id = fields.Many2one(
        "product.template", required=True, ondelete="cascade"
    )
    code = fields.Selection(
        [
            ("BT", "BT (Bombardier)"),
            ("LH", "LH (Liebherr)"),
            ("FY", "FY"),
            ("NK", "NK (Noske Käser)"),
            ("KO", "KO"),
            ("VK", "VK"),
            ("BE", "BE"),
            ("TK", "TK"),
            ("DB", "DB"),
            ("HO", "HO"),
            ("WE", "WE"),
            ("SI", "SI"),
        ],
        string="Hersteller",
        required=True,
    )
    value = fields.Char(string="Teilenummer", required=True)
