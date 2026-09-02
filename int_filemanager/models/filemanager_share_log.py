from odoo import fields, models


class IntFilemanagerShareLog(models.Model):
    _name = "int_filemanager.share_log"
    _description = "Filemanager Freigabe-Protokoll"
    _order = "create_date desc, id desc"

    file_id = fields.Many2one(
        "int_filemanager.file",
        ondelete="set null",
        index=True,
        help="Kein cascade: das Protokoll soll eine gelöschte/umbenannte Datei überleben, "
        "path/filename unten sind dafür ein reiner Text-Snapshot zum Ereigniszeitpunkt.",
    )
    path = fields.Char(required=True, help="Pfad-Snapshot zum Zeitpunkt des Ereignisses.")
    filename = fields.Char(required=True, help="Namens-Snapshot zum Zeitpunkt des Ereignisses.")
    event_type = fields.Selection(
        [
            ("created", "Link erzeugt"),
            ("revoked", "Link widerrufen"),
            ("downloaded", "Über Link/Portal heruntergeladen"),
        ],
        required=True,
        index=True,
    )
    partner_id = fields.Many2one(
        "res.partner", help="Nur bei 'downloaded' über die Portal-Freigabe gesetzt - ein anonymer "
        "Link-Download hat keinen bekannten Partner."
    )
