from odoo import Command, api, fields, models
from .plan import PLAN


class RepairWorksheetTest(models.TransientModel):
    _name = "repair.worksheet.test"
    _description = "BE01412 Arbeitsblatt-Layouttest"

    repair_id = fields.Many2one("repair.order", string="Reparaturauftrag", check_company=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    variant = fields.Selection([("br185", "BR185.2"), ("atc", "ATC")], required=True, default="br185", string="Gerätetyp")
    serial_number = fields.Char(string="Seriennummer")
    rb_reference = fields.Char(string="RB / Referenz")
    inspection_date = fields.Date(string="Eingangsprüfung am")
    inspector = fields.Char(string="Name Prüfer")
    document_revision = fields.Char(string="Änderungsstand", default="Layouttest 01")
    notes = fields.Text(string="Bemerkungen")
    line_ids = fields.One2many("repair.worksheet.test.line", "wizard_id", string="Prüfpunkte", default=lambda self: self._default_lines())
    material_ids = fields.One2many("repair.worksheet.test.material", "wizard_id", string="Material Alt / Neu")

    @api.model
    def _default_lines(self):
        return [Command.create({"code": p["code"], "sequence": p["sequence"], "section": p["section"], "name": p["name"], "hm_number": p["hm"], "br_only": p["br_only"]}) for p in PLAN]

    @api.model
    def default_get(self, field_names):
        vals = super().default_get(field_names)
        if self.env.context.get("active_model") == "repair.order" and self.env.context.get("active_id"):
            repair = self.env["repair.order"].browse(self.env.context["active_id"]).exists()
            if repair:
                repair.check_access("read")
                vals.update(repair_id=repair.id, company_id=repair.company_id.id,
                            serial_number=repair.lot_id.name or "", rb_reference=repair.name)
        return vals

    @api.onchange("repair_id")
    def _onchange_repair_id(self):
        if self.repair_id:
            self.company_id = self.repair_id.company_id
            self.serial_number = self.repair_id.lot_id.name
            self.rb_reference = self.repair_id.name

    def action_print_pdf(self):
        self.ensure_one()
        return self.env.ref("int_repair_worksheet_demo.action_report_worksheet_pdf").report_action(self)

    def action_preview_html(self):
        self.ensure_one()
        return self.env.ref("int_repair_worksheet_demo.action_report_worksheet_html").report_action(self)

    def _worksheet_data(self):
        self.ensure_one()
        values = {line.code: line for line in self.line_ids}
        rows = []
        for item in PLAN:
            row = dict(item)
            line = values.get(item["code"])
            row.update(result=line.result if line else False,
                       performed=line.performed if line else False,
                       operator=line.operator or "" if line else "",
                       hm=line.hm_number or "" if line else item["hm"])
            if item["br_only"] and self.variant != "br185":
                row.update(result="na", performed=False)
            rows.append(row)
        materials = [{"description": m.description or "", "old": m.old_reference or "", "new": m.new_reference or ""} for m in self.material_ids]
        # Keep the original second sheet, and add continuation sheets if needed.
        material_pages = [materials[i:i + 14] for i in range(0, len(materials), 14)] or [[]]
        material_pages = [page + [{"description": "", "old": "", "new": ""}] * (14 - len(page)) for page in material_pages]
        return {
            "variant": self.variant, "serial": self.serial_number or "",
            "rb": self.rb_reference or "", "revision": self.document_revision or "",
            "date": self.inspection_date.strftime("%d.%m.%Y") if self.inspection_date else "",
            "inspector": self.inspector or "", "notes": self.notes or "",
            "incoming": [r for r in rows if r["section"] == "incoming"],
            "work": [r for r in rows if r["section"] == "work"],
            "material_pages": material_pages,
            "page_count": 1 + len(material_pages),
        }


class RepairWorksheetTestLine(models.TransientModel):
    _name = "repair.worksheet.test.line"
    _description = "BE01412 Test-Prüfergebnis"
    _order = "sequence, id"

    wizard_id = fields.Many2one("repair.worksheet.test", required=True, ondelete="cascade")
    sequence = fields.Integer()
    code = fields.Char(required=True)
    section = fields.Selection([("incoming", "Eingangsprüfung"), ("work", "Reparatur")], required=True)
    name = fields.Char(string="Prüfpunkt", required=True)
    hm_number = fields.Char(string="HM-Nr.")
    br_only = fields.Boolean()
    result = fields.Selection([("pass", "OK"), ("fail", "Nicht OK"), ("na", "Nicht anwendbar")], string="Ergebnis")
    performed = fields.Boolean(string="Maßnahme durchgeführt")
    operator = fields.Char(string="Name")


class RepairWorksheetTestMaterial(models.TransientModel):
    _name = "repair.worksheet.test.material"
    _description = "BE01412 Test-Materialangabe"
    _order = "id"

    wizard_id = fields.Many2one("repair.worksheet.test", required=True, ondelete="cascade")
    description = fields.Char(string="Bemerkung / erneuertes Material", required=True)
    old_reference = fields.Char(string="Alt")
    new_reference = fields.Char(string="Neu")
