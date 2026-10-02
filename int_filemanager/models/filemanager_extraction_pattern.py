import re

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class IntFilemanagerExtractionPattern(models.Model):
    _name = "int_filemanager.extraction_pattern"
    _description = "Filemanager Erkennungsmuster"
    _order = "target_field, sequence, id"

    name = fields.Char(required=True)
    # Ehemals eine feste 3er-Selection (date/invoice_number/amount) - seit 2026-09-19 freier Text,
    # damit Admins beliebig viele eigene Felder anlegen koennen (siehe
    # docs/int_filemanager_ocr_selbstdefinierte_felder.md, Phase A). Zunaechst befuellten die drei
    # Werte "date"/"invoice_number"/"amount" noch besondere, fest verdrahtete Felder auf
    # int_filemanager.file - seit der Vereinheitlichung am selben Tag ist target_field nur noch
    # ein frei waehlbares Label ohne Sonderbedeutung im Code: JEDES Muster (auch die drei
    # mitgelieferten) erzeugt gleichermassen einen int_filemanager.extracted_value-Datensatz
    # (siehe filemanager_file.py::_apply_extracted_values).
    target_field = fields.Char(
        required=True,
        help="Freier Anzeigename/technischer Name des Feldes, das dieses Muster befüllt (z.B. "
        "\"iban\" oder \"kundennummer\") - dient nur der Sortierung/Gruppierung in dieser Liste, "
        "ohne Sonderbedeutung im Code.",
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

    # Jedes aktive Muster liefert unabhaengig sein eigenes Ergebnis, kein gemeinsamer Slot pro
    # target_field (siehe fulltext.py:_match_patterns; kein Modell-Code dafuer noetig, das ist
    # reine Auswertungslogik dort).
    @api.constrains("pattern")
    def _check_pattern(self):
        for rec in self:
            try:
                re.compile(rec.pattern, re.IGNORECASE if rec.ignore_case else 0)
            except re.error as e:
                raise ValidationError("Ungültiger regulärer Ausdruck: %s" % e)
