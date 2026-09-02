from datetime import timedelta

from odoo import fields, models

SCAN_LOG_RETENTION_DAYS = 90


class IntFilemanagerScanLog(models.Model):
    _name = "int_filemanager.scan_log"
    _description = "Filemanager Scan-Ereignis (Identitaets-Abgleich)"
    _order = "scan_started desc, id desc"

    scan_started = fields.Datetime(required=True, index=True)
    event_type = fields.Selection(
        [
            ("merged", "Zusammengeführt"),
            ("ambiguous", "Mehrdeutig verworfen"),
        ],
        required=True,
        index=True,
    )
    old_path = fields.Char()
    new_path = fields.Char()
    detail = fields.Text()

    def _cron_prune_old_entries(self):
        cutoff = fields.Datetime.now() - timedelta(days=SCAN_LOG_RETENTION_DAYS)
        self.sudo().search([("scan_started", "<", cutoff)]).unlink()
