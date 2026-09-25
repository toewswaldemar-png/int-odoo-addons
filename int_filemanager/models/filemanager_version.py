from odoo import fields, models


class IntFilemanagerVersion(models.Model):
    _name = "int_filemanager.version"
    _description = "Filemanager Dateiversion"
    _order = "file_id, version_no desc"

    file_id = fields.Many2one("int_filemanager.file", required=True, ondelete="cascade", index=True)
    version_no = fields.Integer(required=True)
    content = fields.Binary(
        attachment=True,
        required=True,
        help="Base64-kodierter Inhalt, über ir.attachment gespeichert - identische Inhalte "
        "über mehrere Versionen/Dateien hinweg werden dabei automatisch dedupliziert.",
    )
    size = fields.Integer(
        required=True,
        help="Größe des gesicherten Inhalts in Bytes, explizit gesetzt - fields.Binary liefert "
        "anders als fields.Image kein automatisch abgeleitetes Größenfeld.",
    )
    content_sha256 = fields.Char(index=True, help="SHA-256 des gesicherten Inhalts (Diagnose/Dedup-Tests).")
    origin = fields.Selection(
        [("app", "App"), ("extern", "Extern geändert")],
        default="app",
        help="extern: Der Plattenstand wich beim Sichern vom zuletzt bekannten Indexstand ab (z.B. im "
        "Explorer geändert) und wurde vor dem Überschreiben als Version gesichert.",
    )

    _version_no_uniq = models.Constraint(
        "UNIQUE(file_id, version_no)",
        "Diese Versionsnummer existiert bereits für diese Datei.",
    )

    def _cron_prune_old_versions(self):
        """Optionales Aufräumen: behält je Datei nur die neuesten
        version_keep_count Versionen (0 = unbegrenzt, Default - kein
        stilles Löschen von Firmenhistorie ohne bewusste Admin-Entscheidung)."""
        keep = int(self.env["ir.config_parameter"].sudo().get_param("int_filemanager.version_keep_count", "0"))
        if not keep:
            return
        self.env.cr.execute(
            """
            SELECT id FROM (
                SELECT id, ROW_NUMBER() OVER (PARTITION BY file_id ORDER BY version_no DESC) AS rn
                FROM int_filemanager_version
            ) ranked WHERE rn > %s
            """,
            (keep,),
        )
        ids = [row[0] for row in self.env.cr.fetchall()]
        if ids:
            self.sudo().browse(ids).unlink()
