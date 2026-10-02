import mimetypes
import os

from odoo import http
from odoo.exceptions import ValidationError
from odoo.http import request


class IntFilemanagerPortal(http.Controller):
    """Portal-seitige Ansicht der 'intern' freigegebenen Dateien
    (shared_partner_ids) - getrennt von der internen Filemanager-UI in
    controllers/main.py, die für Portal-Nutzer weiterhin unerreichbar bleibt
    (dort gilt _check_access(), das group_filemanager_user verlangt).
    Die Sichtbarkeit selbst kommt vollständig aus dem generierten
    Portal-Zweig der Read-Regel in acl_rules.py - hier wird bewusst NICHT
    zusätzlich gefiltert, sondern der normalen (nicht-sudo) ORM-Suche
    vertraut, dieselbe Regel gilt für jeden weiteren künftigen Lesezugriff
    auf int_filemanager.file gleichermaßen."""

    @http.route("/my/shared_files", type="http", auth="user", website=True)
    def portal_shared_files(self, **kwargs):
        # ("shared_partner_ids", "!=", False) zusätzlich zur Regel: die Seite
        # soll ausschließlich Dateien mit AKTIVER Freigabe zeigen, auch falls
        # sie (z.B. als Admin) von jemandem ohne Portal-Kontext geöffnet wird.
        records = request.env["int_filemanager.file"].search(
            [("is_dir", "=", False), ("shared_partner_ids", "!=", False)], order="name"
        )
        return request.render(
            "int_filemanager.portal_shared_files",
            {"page_name": "shared_files", "files": records},
        )

    @http.route("/my/shared_files/<int:file_id>/download", type="http", auth="user")
    def portal_shared_file_download(self, file_id, **kwargs):
        record = request.env["int_filemanager.file"].browse(file_id).exists()
        if not record:
            return request.not_found()
        # exists() prüft keine ir.rule (nur eine rohe id-IN-Abfrage) - die
        # eigentliche Freigabeprüfung (ir.model.access UND die generierte
        # Portal-Leseregel) läuft erst hier, explizit.
        record.check_access("read")
        if record.is_dir:
            return request.not_found()

        try:
            abs_path = record.sudo()._absolute_path()
        except ValidationError:
            return request.not_found()
        if not os.path.isfile(abs_path):
            return request.not_found()

        with open(abs_path, "rb") as f:
            data = f.read()
        request.env["int_filemanager.share_log"].sudo().create(
            {
                "file_id": record.id,
                "path": record.path,
                "filename": record.name,
                "event_type": "downloaded",
                "partner_id": request.env.user.partner_id.id,
            }
        )
        mimetype = mimetypes.guess_type(record.name)[0] or "application/octet-stream"
        headers = [
            ("Content-Type", mimetype),
            ("Content-Length", str(len(data))),
            ("Content-Disposition", http.content_disposition(record.name, "attachment")),
            ("Cache-Control", "private, no-store"),
        ]
        return request.make_response(data, headers=headers)
