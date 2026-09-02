import os
from datetime import timedelta

from odoo import fields, models

STUCK_TIMEOUT_MINUTES = 30


class IntFilemanagerWriteJournal(models.Model):
    _name = "int_filemanager.write_journal"
    _description = "Filemanager Schreibvorgang-Journal (Recovery)"
    _order = "id desc"

    file_id = fields.Many2one("int_filemanager.file", ondelete="set null", index=True)
    operation = fields.Selection(
        [
            ("sync_write", "ONLYOFFICE-Sync"),
            ("upload_overwrite", "Upload-Überschreiben"),
            ("restore", "Version-Restore"),
        ],
        required=True,
    )
    stage = fields.Selection(
        [
            ("created", "Angelegt"),
            ("snapshot_committed", "Snapshot gesichert"),
            ("temp_synced", "Temporärdatei geschrieben"),
            ("replaced", "Ersetzt"),
            ("done", "Abgeschlossen"),
            ("failed", "Fehlgeschlagen"),
        ],
        required=True,
        default="created",
        index=True,
        help="Erlaubt einem Recovery-Cron, den tatsächlichen Plattenzustand gegen den "
        "Journalzustand abzugleichen, statt nur zu erkennen, dass 'irgendetwas offen blieb'.",
    )
    version_id = fields.Many2one("int_filemanager.version", ondelete="set null")
    old_sha256 = fields.Char()
    new_sha256 = fields.Char()
    temp_path = fields.Char()
    started_at = fields.Datetime(required=True)
    finished_at = fields.Datetime()
    error = fields.Text()

    def _cron_recover_stuck_entries(self):
        """Findet Journal-Einträge, die länger als STUCK_TIMEOUT_MINUTES in
        einem nicht-terminalen Stage feststecken (z.B. Prozessabsturz
        zwischen zwei Stufen) - markiert sie zur manuellen Prüfung statt
        automatisch zu erraten, was zu tun ist, und räumt eine noch
        vorhandene Temporärdatei auf (zweite Verteidigungslinie neben dem
        finally-Block in write_service.py, der den Normalfall abdeckt)."""
        cutoff = fields.Datetime.now() - timedelta(minutes=STUCK_TIMEOUT_MINUTES)
        stuck = self.sudo().search([("stage", "not in", ["done", "failed"]), ("started_at", "<", cutoff)])
        for entry in stuck:
            if entry.temp_path and os.path.exists(entry.temp_path):
                try:
                    os.remove(entry.temp_path)
                except OSError:
                    pass
            entry.write(
                {
                    "stage": "failed",
                    "error": ((entry.error or "") + "\nAls hängengeblieben erkannt (Recovery-Cron).").strip(),
                    "finished_at": fields.Datetime.now(),
                }
            )
