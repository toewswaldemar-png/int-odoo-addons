from odoo.tests import TransactionCase, tagged
from odoo import Command


@tagged("post_install", "-at_install")
class TestWorksheet(TransactionCase):
    def test_blank_values_stay_blank_and_plan_is_complete(self):
        wizard = self.env["repair.worksheet.test"].create({})
        data = wizard._worksheet_data()
        self.assertEqual(len(data["incoming"]), 10)
        self.assertEqual(len(data["work"]), 17)
        self.assertFalse(data["incoming"][0]["result"])
        self.assertEqual(data["serial"], "")
        self.assertEqual(data["page_count"], 2)

    def test_atc_excludes_br_specific_measure(self):
        wizard = self.env["repair.worksheet.test"].create({"variant": "atc"})
        row = next(r for r in wizard._worksheet_data()["work"] if r["code"] == "p30")
        self.assertEqual(row["result"], "na")
        self.assertFalse(row["performed"])

    def test_results_and_material_continuation(self):
        wizard = self.env["repair.worksheet.test"].create({
            "serial_number": "TEST-123", "rb_reference": "RB-TEST",
            "material_ids": [Command.create({"description": f"Teil {i}"}) for i in range(15)],
        })
        wizard.line_ids.filtered(lambda line: line.code == "p12").result = "fail"
        data = wizard._worksheet_data()
        self.assertEqual(data["incoming"][0]["result"], "fail")
        self.assertEqual(data["serial"], "TEST-123")
        self.assertEqual(data["page_count"], 3)
        self.assertEqual(data["material_pages"][1][0]["description"], "Teil 14")

    def test_qweb_html_render(self):
        wizard = self.env["repair.worksheet.test"].create({"serial_number": "TEST-QWEB"})
        html, _ = self.env["ir.actions.report"]._render_qweb_html(
            "int_repair_worksheet_demo.action_report_worksheet_pdf", wizard.ids)
        self.assertIn(b"TEST-QWEB", html)
        self.assertIn(b"BE 01412", html)
        self.assertNotIn(b"t-foreach", html)
