import logging

from odoo import fields, models
from odoo.exceptions import AccessError

from ..path_utils import to_relative

_logger = logging.getLogger(__name__)


class IrAttachment(models.Model):
    _inherit = "ir.attachment"

    hm_filemanager_path = fields.Char(
        string="Filemanager-Pfad",
        index=True,
        copy=False,
        help="Absoluter Pfad auf der Festplatte, den dieses Attachment spiegelt. "
        "Nur intern von hm_filemanager gesetzt, niemals über normale Requests.",
    )

    def _check_filemanager_path_write_allowed(self, vals):
        # hm_filemanager_path darf ausschließlich von unserem eigenen (sudo-)
        # Controller-Code gesetzt werden - nie durch einen regulären Nutzer-Request,
        # sonst ließe sich darüber beliebiger Dateiinhalt auf der Platte überschreiben.
        if "hm_filemanager_path" in vals and not self.env.su:
            raise AccessError("hm_filemanager_path darf nicht direkt gesetzt werden.")
        if vals.get("hm_filemanager_path"):
            # Defense in depth: auch im sudo-Fall muss der Pfad innerhalb des
            # konfigurierten Filemanager-Stammverzeichnisses liegen.
            to_relative(self.env, vals["hm_filemanager_path"])

    def create(self, vals_list):
        for vals in vals_list if isinstance(vals_list, list) else [vals_list]:
            self._check_filemanager_path_write_allowed(vals)
        return super().create(vals_list)

    def write(self, vals):
        self._check_filemanager_path_write_allowed(vals)
        res = super().write(vals)
        if "raw" in vals or "datas" in vals:
            for attachment in self:
                if attachment.hm_filemanager_path:
                    self._hm_filemanager_sync_to_disk(attachment)
        return res

    def _hm_filemanager_sync_to_disk(self, attachment):
        path = attachment.hm_filemanager_path
        try:
            to_relative(self.env, path)
        except Exception:
            _logger.exception(
                "hm_filemanager: attachment %s hat einen ungültigen hm_filemanager_path, "
                "überspringe Sync auf Platte: %s",
                attachment.id,
                path,
            )
            return
        try:
            with open(path, "wb") as f:
                f.write(attachment.raw or b"")
            _logger.info("hm_filemanager: Attachment %s zurück nach %s geschrieben", attachment.id, path)
        except OSError:
            _logger.exception("hm_filemanager: Sync von Attachment %s nach %s fehlgeschlagen", attachment.id, path)
