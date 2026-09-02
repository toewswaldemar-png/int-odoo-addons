import logging

from odoo import fields, models
from odoo.exceptions import AccessError

from ..path_utils import to_relative

_logger = logging.getLogger(__name__)


class IrAttachment(models.Model):
    _inherit = "ir.attachment"

    int_filemanager_path = fields.Char(
        string="Filemanager-Pfad",
        index=True,
        copy=False,
        help="Absoluter Pfad auf der Festplatte, den dieses Attachment spiegelt. "
        "Nur intern von int_filemanager gesetzt, niemals über normale Requests.",
    )

    def _check_filemanager_path_write_allowed(self, vals):
        # int_filemanager_path darf ausschließlich von unserem eigenen (sudo-)
        # Controller-Code gesetzt werden - nie durch einen regulären Nutzer-Request,
        # sonst ließe sich darüber beliebiger Dateiinhalt auf der Platte überschreiben.
        if "int_filemanager_path" in vals and not self.env.su:
            raise AccessError("int_filemanager_path darf nicht direkt gesetzt werden.")
        if vals.get("int_filemanager_path"):
            # Defense in depth: auch im sudo-Fall muss der Pfad innerhalb des
            # konfigurierten Filemanager-Stammverzeichnisses liegen.
            to_relative(self.env, vals["int_filemanager_path"])

    def create(self, vals_list):
        for vals in vals_list if isinstance(vals_list, list) else [vals_list]:
            self._check_filemanager_path_write_allowed(vals)
        return super().create(vals_list)

    def write(self, vals):
        self._check_filemanager_path_write_allowed(vals)
        res = super().write(vals)
        if "raw" in vals or "datas" in vals:
            for attachment in self:
                if attachment.int_filemanager_path:
                    self._int_filemanager_sync_to_disk(attachment)
        return res

    def _int_filemanager_sync_to_disk(self, attachment):
        path = attachment.int_filemanager_path
        try:
            rel = to_relative(self.env, path)
        except Exception:
            _logger.exception(
                "int_filemanager: attachment %s hat einen ungültigen int_filemanager_path, "
                "überspringe Sync auf Platte: %s",
                attachment.id,
                path,
            )
            return

        file_record = self.env["int_filemanager.file"].sudo().search([("path", "=", rel)], limit=1)
        if not file_record:
            # Datei noch nicht indexiert (z.B. gerade erst angelegt, Watcher
            # noch nicht durchgelaufen) - kein Versionierungsziel vorhanden,
            # einfacher Direktschreibvorgang wie bisher.
            try:
                with open(path, "wb") as f:
                    f.write(attachment.raw or b"")
                _logger.info("int_filemanager: Attachment %s zurück nach %s geschrieben (unindexiert)", attachment.id, path)
            except OSError:
                _logger.exception(
                    "int_filemanager: Sync von Attachment %s nach %s fehlgeschlagen", attachment.id, path
                )
            return

        # Über den zentralen Snapshot-/Schreibdienst: sichert den vorherigen
        # Inhalt als Version, schreibt atomar (Temp-Datei + os.replace). Ruft
        # bewusst KEIN index_upsert() auf - der Watcher beobachtet diesen
        # Schreibvorgang selbst per inotify und aktualisiert den Index; ein
        # zusätzlicher direkter Aufruf hier würde dasselbe Race auslösen, das
        # das ursprüngliche Direktschreiben hier vermeiden sollte (überlappende
        # Transaktionen auf dieselbe int_filemanager.file-Zeile, von Postgres
        # mit "could not serialize access due to concurrent update" abgelehnt).
        from .. import write_service

        write_service.snapshot_and_write(self.env, file_record, attachment.raw or b"", operation="sync_write")
        _logger.info("int_filemanager: Attachment %s zurück nach %s geschrieben (versioniert)", attachment.id, path)
