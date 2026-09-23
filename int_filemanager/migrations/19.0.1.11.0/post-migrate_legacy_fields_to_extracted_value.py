from odoo import SUPERUSER_ID, api

# Vereinheitlichung (2026-09-19, siehe docs/int_filemanager_ocr_selbstdefinierte_felder.md): die
# drei fest verdrahteten Char-Felder extracted_date/_invoice_number/_amount auf
# int_filemanager.file sind entfallen, jedes Erkennungsmuster erzeugt jetzt gleichermassen einen
# int_filemanager.extracted_value-Datensatz. Bestandsdaten in den drei alten Spalten werden hier
# uebernommen, bevor die inzwischen vom Python-Modell nicht mehr verwalteten Spalten geloescht
# werden - sonst waeren bereits erkannte/bestaetigte Werte nach dem Update kommentarlos weg.
#
# post-migrate (nicht pre-): braucht die bereits geladene int_filemanager.extracted_value-Tabelle
# (neu in dieser Version) UND die drei mitgelieferten extraction_pattern-Datensaetze mit fester
# External ID (data/filemanager_extraction_pattern.xml, unveraendert seit der Erstinstallation).

_PATTERN_XML_IDS = {
    "extracted_date": "int_filemanager.filemanager_extraction_pattern_date",
    "extracted_invoice_number": "int_filemanager.filemanager_extraction_pattern_invoice_number",
    "extracted_amount": "int_filemanager.filemanager_extraction_pattern_amount",
}


def migrate(cr, version):
    cr.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'int_filemanager_file' AND column_name = ANY(%s)",
        (list(_PATTERN_XML_IDS),),
    )
    existing_columns = {row[0] for row in cr.fetchall()}
    if not existing_columns:
        # Frische Installation ohne Vorgeschichte - keine alten Spalten, nichts zu uebernehmen.
        return

    env = api.Environment(cr, SUPERUSER_ID, {})
    Value = env["int_filemanager.extracted_value"]

    for column, xml_id in _PATTERN_XML_IDS.items():
        if column not in existing_columns:
            continue
        pattern = env.ref(xml_id, raise_if_not_found=False)
        if not pattern:
            # Sollte nicht vorkommen (die drei Muster werden nie geloescht, siehe
            # ondelete="restrict" auf extracted_value.pattern_id) - konservativ ueberspringen
            # statt der Migration abzubrechen, falls doch.
            continue
        cr.execute(
            'SELECT id, "%s" FROM int_filemanager_file WHERE "%s" IS NOT NULL AND "%s" != \'\''
            % (column, column, column)
        )
        rows = cr.fetchall()
        for file_id, value in rows:
            Value.create({"file_id": file_id, "pattern_id": pattern.id, "value": value})

    # Die Spalten selbst raeumt Odoos _auto_init nicht automatisch weg (nur um neue Spalten
    # kuemmert es sich, nie um entfernte) - hier explizit, jetzt wo die Werte uebernommen sind.
    for column in existing_columns:
        cr.execute('ALTER TABLE int_filemanager_file DROP COLUMN IF EXISTS "%s"' % column)
