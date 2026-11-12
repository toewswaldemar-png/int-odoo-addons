from odoo.tests import TransactionCase, tagged
from odoo.exceptions import UserError, ValidationError


@tagged("post_install", "-at_install")
class TestInteractiveWorksheet(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        product = cls.env["product.product"].create({"name": "BE01412 Testgerät"})
        cls.repair = cls.env["repair.order"].create({"product_id": product.id})
        cls.worksheet = cls.env["repair.worksheet"].create({"repair_id": cls.repair.id})

    def test_save_and_clear_checkbox(self):
        form = self.worksheet._editor_values()
        form.update(result_p26="pass", performed_p26="1", serial_number="TEST-SAVED")
        self.worksheet._apply_editor_form(form)
        self.assertEqual(self.worksheet.serial_number, "TEST-SAVED")
        self.assertTrue(self.worksheet.entry_data["p26"]["performed"])
        form = self.worksheet._editor_values()
        form.pop("performed_p26")
        self.worksheet._apply_editor_form(form)
        self.assertFalse(self.worksheet.entry_data["p26"]["performed"])

    def test_stale_tab_cannot_overwrite_newer_data(self):
        first = self.worksheet._editor_values()
        second = dict(first, serial_number="NEWER")
        self.worksheet._apply_editor_form(second)
        first["serial_number"] = "OLDER"
        with self.assertRaises(UserError):
            self.worksheet._apply_editor_form(first)
        self.assertEqual(self.worksheet.serial_number, "NEWER")

    def test_invalid_material_preserves_saved_data(self):
        form = self.worksheet._editor_values()
        form.update(serial_number="MUST-NOT-SAVE", material_old_0="ALT-OHNE-BESCHREIBUNG")
        with self.assertRaises(ValidationError):
            self.worksheet._apply_editor_form(form)
        self.assertNotEqual(self.worksheet.serial_number, "MUST-NOT-SAVE")

    def test_atc_and_qweb_report(self):
        form = self.worksheet._editor_values()
        form.update(variant="atc", result_p30="pass", performed_p30="1", serial_number="QWEB-ATC")
        self.worksheet._apply_editor_form(form)
        self.assertEqual(self.worksheet.entry_data["p30"]["result"], "na")
        self.assertFalse(self.worksheet.entry_data["p30"]["performed"])
        html, _ = self.env["ir.actions.report"]._render_qweb_html(
            "int_repair_worksheet.action_report_worksheet_pdf", self.worksheet.ids)
        self.assertIn(b"QWEB-ATC", html)
        self.assertIn(b"nicht anwendbar", html)
