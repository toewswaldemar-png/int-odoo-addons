from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    x_alt_artnr = fields.Char(string="Artikelnummer")
    x_alt_kurzbezeichnung = fields.Char(string="Kurzbezeichnung")
    x_alt_hersteller_ref_ids = fields.One2many(
        "product.legacy.manufacturer.ref", "product_tmpl_id",
        string="Hersteller-/Ident-Referenzen",
    )
    x_alt_bestellnr = fields.Char(string="Bestellnummer")
    x_alt_hauptlieferant_id = fields.Many2one(
        "res.partner", string="Hauptlieferant",
        help="ARTIKEL.HAUPTLIEFERANT im Altsystem ist ein echter Fremdschlüssel auf "
        "ADRESSEN.OID, kein Freitext.",
    )
    x_alt_gruppe_id = fields.Many2one(
        "product.category", string="Gruppe",
        help="ARTIKEL.GRUPPE im Altsystem ist ein echter Fremdschlüssel auf "
        "ARTIKELGRUPPEN.GID, kein Freitext.",
    )
    x_alt_einheit = fields.Char(string="Einheit")
