from copy import deepcopy
from uuid import uuid4

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from .plan import PLAN
from .form_data import parse_form, FormError


class RepairWorksheet(models.Model):
    _name = "repair.worksheet"
    _description = "BE01412 Reparatur-Arbeitsblatt"
    _order = "write_date desc, id desc"
    _check_company_auto = True

    name = fields.Char(compute="_compute_name", store=True)
    repair_id = fields.Many2one("repair.order", string="Reparaturauftrag", required=True,
                               ondelete="cascade", check_company=True, index=True)
    company_id = fields.Many2one(related="repair_id.company_id", store=True, index=True)
    variant = fields.Selection([("br185", "BR185.2"), ("atc", "ATC")], required=True, default="br185", string="Gerätetyp")
    serial_number = fields.Char(string="Seriennummer")
    rb_reference = fields.Char(string="RB / Referenz")
    inspection_date = fields.Date(string="Eingangsprüfung am")
    inspector = fields.Char(string="Name Prüfer")
    document_revision = fields.Char(default="Interaktiv 01", readonly=True)
    notes = fields.Text(string="Bemerkungen")
    plan_data = fields.Json(default=lambda self: deepcopy(PLAN), readonly=True, copy=False)
    entry_data = fields.Json(default=dict, copy=False)
    material_data = fields.Json(default=list, copy=False)
    edit_token = fields.Char(default=lambda self: uuid4().hex, readonly=True, copy=False)

    _one_per_repair = models.Constraint("UNIQUE(repair_id)", "Für diesen Reparaturauftrag existiert bereits ein Arbeitsblatt.")

    @api.depends("repair_id.name")
    def _compute_name(self):
        for record in self:
            record.name = "BE01412 · " + (record.repair_id.name or "")

    @api.model_create_multi
    def create(self, vals_list):
        prepared = []
        for original in vals_list:
            vals = dict(original)
            repair = self.env["repair.order"].browse(vals.get("repair_id")).exists()
            if not repair:
                raise ValidationError("Bitte einen Reparaturauftrag auswählen.")
            repair.check_access("read")
            vals.update(plan_data=deepcopy(PLAN), edit_token=uuid4().hex)
            vals.setdefault("serial_number", repair.lot_id.name or "")
            vals.setdefault("rb_reference", repair.name)
            prepared.append(vals)
        return super().create(prepared)

    def write(self, vals):
        if "plan_data" in vals:
            raise UserError("Die Prüfplan-Momentaufnahme kann nicht überschrieben werden.")
        if "repair_id" in vals and any(r.repair_id.id != vals["repair_id"] for r in self):
            raise UserError("Der zugeordnete Reparaturauftrag kann nicht geändert werden.")
        for record in self:
            record.repair_id.check_access("read")
        return super().write(dict(vals, edit_token=uuid4().hex))

    def action_open_editor(self):
        self.ensure_one()
        self.check_access("read")
        self.repair_id.check_access("read")
        return {"type": "ir.actions.act_url", "url": f"/be01412/{self.id}", "target": "new"}

    def _apply_editor_form(self, form):
        self.ensure_one()
        self.check_access("write")
        self.repair_id.check_access("read")
        try:
            values = parse_form(form, self.plan_data)
        except FormError as exc:
            raise ValidationError(str(exc)) from exc
        # Serialize writes and reject stale browser tabs before changing any value.
        self.flush_recordset(["edit_token"])
        self.env.cr.execute("SELECT edit_token FROM repair_worksheet WHERE id = %s FOR UPDATE", [self.id])
        token = self.env.cr.fetchone()
        if not token or token[0] != form.get("edit_token"):
            raise UserError("Das Arbeitsblatt wurde zwischenzeitlich geändert. Bitte den aktuellen Stand neu laden und die Eingaben abgleichen.")
        self.write(values)

    def _editor_values(self):
        self.ensure_one()
        form = {
            "variant": self.variant, "serial_number": self.serial_number or "",
            "rb_reference": self.rb_reference or "", "inspector": self.inspector or "",
            "inspection_date": str(self.inspection_date) if self.inspection_date else "",
            "notes": self.notes or "", "edit_token": self.edit_token,
        }
        for item in self.plan_data:
            value = (self.entry_data or {}).get(item["code"], {})
            form["result_" + item["code"]] = value.get("result", "")
            form["performed_" + item["code"]] = "1" if value.get("performed") else ""
            form["operator_" + item["code"]] = value.get("operator", "")
            form["hm_" + item["code"]] = value.get("hm", item["hm"])
        materials = self.material_data or []
        form["material_count"] = str(max(14, len(materials)))
        for i, value in enumerate(materials):
            for key in ("description", "old", "new"):
                form[f"material_{key}_{i}"] = value.get(key, "")
        return form

    def _worksheet_data(self):
        self.ensure_one()
        self.check_access("read")
        self.repair_id.check_access("read")
        rows = []
        for item in self.plan_data:
            row = dict(item)
            row.update((self.entry_data or {}).get(item["code"], {}))
            row.setdefault("result", "")
            row.setdefault("performed", False)
            row.setdefault("operator", "")
            if item["br_only"] and self.variant == "atc":
                row.update(result="na", performed=False)
            rows.append(row)
        materials = self.material_data or []
        pages = [materials[i:i+14] for i in range(0, len(materials), 14)] or [[]]
        pages = [p + [{"description": "", "old": "", "new": ""}] * (14-len(p)) for p in pages]
        return {"variant": self.variant, "serial": self.serial_number or "", "rb": self.rb_reference or "",
                "revision": self.document_revision, "date": self.inspection_date.strftime("%d.%m.%Y") if self.inspection_date else "",
                "inspector": self.inspector or "", "notes": self.notes or "",
                "incoming": [r for r in rows if r["section"] == "incoming"],
                "work": [r for r in rows if r["section"] == "work"],
                "material_pages": pages, "page_count": len(pages)+1}
