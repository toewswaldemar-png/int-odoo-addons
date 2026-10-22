from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestIntLiedanzeigeKioskUser(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.kiosk = cls.env.ref("int_liedanzeige.user_kiosk")

    def test_kiosk_user_is_a_portal_user_with_the_operator_group_only(self):
        self.assertTrue(self.kiosk.share, "a portal user, not an internal one")
        groups = self.kiosk.group_ids
        self.assertIn(self.env.ref("int_liedanzeige.group_liedanzeige_operator"), groups)
        self.assertNotIn(self.env.ref("base.group_user"), groups)
        self.assertFalse(self.kiosk.has_group("base.group_system"))

    def test_kiosk_user_runs_the_display_calls(self):
        State = self.env["int_liedanzeige.state"].with_user(self.kiosk)
        self.assertEqual(State.apply_action("input", "choir", "5")["choir_state"], "5")
        State.send_kiosk_command("reload")
        State.report_kiosk_state(True)

    def test_kiosk_user_cannot_read_system_or_other_people_data(self):
        with self.assertRaises(AccessError):
            self.env["ir.config_parameter"].with_user(self.kiosk).search([])
        other = self.env["res.partner"].create({"name": "Somebody else"})
        self.assertNotIn(other, self.env["res.partner"].with_user(self.kiosk).search([]))

    def test_kiosk_user_has_no_password_login(self):
        self.assertFalse(self.kiosk.password)
