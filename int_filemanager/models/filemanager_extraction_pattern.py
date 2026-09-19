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
    # docs/int_filemanager_ocr_selbstdefinierte_felder.md, Phase A). Die drei alten Werte
    # "date"/"invoice_number"/"amount" bleiben als besondere, fest verdrahtete Werte bestehen
    # (siehe fulltext._LEGACY_TARGET_FIELDS) - ein Muster mit einem dieser drei Werte befuellt
    # weiterhin ausschliesslich die alten Felder extracted_date/_invoice_number/_amount auf
    # int_filemanager.file (kein Migrationsrisiko fuer Bestandsdaten/-ansichten). JEDES ANDERE
    # target_field erzeugt stattdessen einen dynamischen int_filemanager.extracted_value-Datensatz
    # - siehe filemanager_file.py:action_apply_extracted_values.
    target_field = fields.Char(
        required=True,
        help="Technischer Name des Feldes, das dieses Muster befüllt (frei wählbar, z.B. "
        "\"iban\" oder \"kundennummer\"). Die drei besonderen Werte \"date\", \"invoice_number\" "
        "und \"amount\" befüllen weiterhin die eingebauten Felder Datum/Rechnungsnummer/Betrag - "
        "jeder andere Wert erzeugt ein eigenes, frei benanntes Feld im \"Werte erkennen\"-Dialog.",
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

    # Nur fuer die drei Legacy-target_field-Werte (date/invoice_number/amount) gilt "erster
    # Treffer in sequence-Reihenfolge gewinnt pro target_field" - jedes selbstdefinierte Muster
    # (jedes andere target_field) liefert dagegen unabhaengig sein eigenes Ergebnis, da es dafuer
    # keinen gemeinsamen Slot gibt (siehe fulltext.py:_match_extraction_patterns vs.
    # _match_custom_patterns; kein Modell-Code dafuer noetig, das ist reine Auswertungslogik dort).
    @api.constrains("pattern")
    def _check_pattern(self):
        for rec in self:
            try:
                re.compile(rec.pattern, re.IGNORECASE if rec.ignore_case else 0)
            except re.error as e:
                raise ValidationError("Ungültiger regulärer Ausdruck: %s" % e)
