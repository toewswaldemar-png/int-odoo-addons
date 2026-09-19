from odoo import api, fields, models


class IntFilemanagerExtractedValue(models.Model):
    _name = "int_filemanager.extracted_value"
    _description = "Filemanager erkannter Wert"
    _order = "file_id, pattern_id"

    # 1:1 nach Vorbild von Odoos eigenem product.attribute.custom.value - ein echtes
    # Datensatz-Modell statt eines JSON-Blobs (fields.Properties), siehe
    # docs/int_filemanager_ocr_selbstdefinierte_felder.md fuer die Begruendung. ondelete=restrict
    # auf pattern_id: ein Admin, der ein Muster loescht, das bereits Werte erzeugt hat, muss das
    # explizit ueber "Aktiv" abschalten (soft-delete) statt bestehende Werte zu verwaisen - active
    # auf extraction_pattern deckt diesen Fall bereits ab.
    pattern_id = fields.Many2one(
        "int_filemanager.extraction_pattern", required=True, ondelete="restrict", index=True
    )
    file_id = fields.Many2one("int_filemanager.file", required=True, ondelete="cascade", index=True)
    value = fields.Char(required=True)
    name = fields.Char(compute="_compute_name", store=True)

    # Position im PDF - rein technisch, nie als eigene Spalte in einer Listenansicht sichtbar
    # (genau wie is_dir/path/folder_path auf int_filemanager.file per column_invisible="1" in der
    # Dateiliste mitgeladen werden). page ist 1-basiert; alle vier Koordinaten liegen in
    # PDF-Punkten mit Ursprung oben-links (pdfplumber-Konvention, siehe fulltext.py) - dieselbe
    # Konvention wie ein <canvas>, der Highlight-Viewer (Phase C) skaliert sie ohne
    # Achsen-Umrechnung. False/0, wenn keine Position ermittelt werden konnte (z.B. reine
    # Textdatei ohne Seitenkonzept, oder ein Scan-PDF, dessen OCR-Textlayer nur in einer
    # verworfenen Temp-Datei existierte - siehe fulltext.pdf_word_index).
    page = fields.Integer(help="1-basierte Seitenzahl im PDF, leer bei Klartextdateien.")
    x0 = fields.Float(string="X0")
    y0 = fields.Float(string="Y0")
    x1 = fields.Float(string="X1")
    y1 = fields.Float(string="Y1")

    @api.depends("pattern_id.name", "value")
    def _compute_name(self):
        for rec in self:
            rec.name = "%s: %s" % (rec.pattern_id.name, rec.value) if rec.pattern_id else rec.value
