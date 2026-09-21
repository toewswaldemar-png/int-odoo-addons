from odoo import _, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    int_filemanager_root_path = fields.Char(
        string="Stammverzeichnis",
        config_parameter="int_filemanager.root_path",
        help="Absoluter Pfad auf dem Server, den der Dateimanager anzeigt (path_utils.py, "
        "get_root()). Aendern setzt nur den Parameter - der bestehende Index/Watcher laeuft "
        "bis zum naechsten manuellen Scan bzw. Odoo-Neustart weiter auf dem alten Pfad, siehe "
        "Warnhinweis in der Ansicht.",
    )

    int_filemanager_trash_retention_days = fields.Integer(
        string="Papierkorb: Aufbewahrung (Tage)",
        config_parameter="int_filemanager.trash_retention_days",
        default=30,
        help="Papierkorb-Einträge werden nach dieser Anzahl Tage automatisch endgültig "
        "gelöscht (ir_cron_purge_trash_filemanager, siehe data/ir_cron.xml).",
    )

    def action_scan_now(self):
        """Manueller Ersatz fuer Einstellungen > Technisch > Geplante Aktionen > "Jetzt
        ausfuehren" auf ir_cron_scan_filemanager (data/ir_cron.xml) - ruft denselben Cron-
        Einstiegspunkt auf, ohne dass Filemanager-Admins (die nicht zwingend volle Odoo-
        Systemadmins/base.group_system sind) dafuer den Entwicklermodus brauchen.

        self.execute() zuerst: persistiert ein evtl. gerade im Formular geaendertes, noch
        nicht gespeichertes Stammverzeichnis, bevor gescannt wird - sonst wuerde der Scan
        (liest int_filemanager.root_path per get_root() direkt aus ir.config_parameter)
        unbemerkt noch auf dem alten Pfad laufen."""
        self.execute()
        self.env["int_filemanager.file"]._cron_scan_filemanager()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Scan abgeschlossen"),
                "message": _("Der Index wurde mit dem Dateisystem abgeglichen."),
                "type": "success",
            },
        }
