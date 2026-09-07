import re

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class IntFilemanagerExtractionPattern(models.Model):
    _name = "int_filemanager.extraction_pattern"
    _description = "Filemanager Erkennungsmuster"
    _order = "target_field, sequence, id"

    name = fields.Char(required=True)
    target_field = fields.Selection(
        [
            ("date", "Datum"),
            ("invoice_number", "Rechnungsnummer"),
            ("amount", "Betrag"),
        ],
        required=True,
        help="Welchen Vorschlags-Slot im \"Werte erkennen\"-Dialog dieses Muster befüllt.",
    )
    pattern = fields.Char(
        required=True,
        help="Regulärer Ausdruck (Python re-Syntax), gegen den der extrahierte Dokumenttext "
        "geprüft wird.",
    )
    ignore_case = fields.Boolean(
        string="Groß-/Kleinschreibung ignorieren", default=False
    )
    group_index = fields.Integer(
        string="Erfassungsgruppe",
        default=0,
        help="Welche Erfassungsgruppe des Musters den vorgeschlagenen Wert liefert - 0 für "
        "den gesamten Treffer.",
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    # Pro target_field wird in sequence-Reihenfolge geprueft, der erste Treffer gewinnt -
    # fulltext.py:suggest_from_text() haelt sich strikt daran (kein Modell-Code dafuer noetig,
    # das ist reine Auswertungslogik dort).
    @api.constrains("pattern")
    def _check_pattern(self):
        for rec in self:
            try:
                re.compile(rec.pattern, re.IGNORECASE if rec.ignore_case else 0)
            except re.error as e:
                raise ValidationError("Ungültiger regulärer Ausdruck: %s" % e)
