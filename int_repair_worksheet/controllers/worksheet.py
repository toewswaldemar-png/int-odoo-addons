from odoo import http
from odoo.http import request
from odoo.exceptions import AccessError, UserError, ValidationError
from werkzeug.exceptions import Forbidden, NotFound


class WorksheetController(http.Controller):
    def _worksheet(self, worksheet_id, operation="read"):
        record = request.env["repair.worksheet"].browse(worksheet_id).exists()
        if not record:
            raise NotFound()
        try:
            record.check_access(operation)
            record.repair_id.check_access("read")
        except AccessError as exc:
            raise Forbidden() from exc
        return record

    def _render(self, record, *, form=None, error="", saved=False, status=200):
        form = record._editor_values() if form is None else form
        try:
            count = max(14, min(200, int(form.get("material_count", "14"))))
        except (ValueError, TypeError):
            count = 14
        response = request.render("int_repair_worksheet.worksheet_editor", {
            "record": record, "sheet": record._worksheet_data(), "form": form,
            "material_indices": range(count), "error": error, "saved": saved, "local_preview": False,
        }, status=status)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        return response

    @http.route("/be01412/<int:worksheet_id>", type="http", auth="user", methods=["GET"])
    def editor(self, worksheet_id, saved=None, **kwargs):
        return self._render(self._worksheet(worksheet_id), saved=saved == "1")

    @http.route("/be01412/<int:worksheet_id>/save", type="http", auth="user", methods=["POST"], csrf=True)
    def save(self, worksheet_id, **post):
        record = self._worksheet(worksheet_id, "write")
        try:
            with request.env.cr.savepoint():
                record._apply_editor_form(post)
        except (ValidationError, UserError) as exc:
            return self._render(record, form=post, error=str(exc), status=422)
        if post.get("intent") == "pdf":
            return request.redirect(f"/report/pdf/int_repair_worksheet.report_worksheet/{record.id}", code=303)
        return request.redirect(f"/be01412/{record.id}?saved=1", code=303)
