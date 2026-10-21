from odoo.tests.common import TransactionCase, new_test_user, tagged

PARAMETER = "int_filemanager.default_open_mode"


@tagged("post_install", "-at_install")
class TestOpenMode(TransactionCase):
    """What opens a document (one click or two): a default of the filemanager that the user can
    override in their preferences; the browser gets the result (``res.users.settings``)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        groups = "base.group_user,int_filemanager.int_filemanager_group_user"
        cls.alice = new_test_user(cls.env, login="open_alice", groups=groups)
        cls.bob = new_test_user(cls.env, login="open_bob", groups=groups)

    def _settings(self, user):
        return self.env["res.users.settings"].with_user(user)._find_or_create_for_user(user)

    def _resolved(self, user):
        self.env.invalidate_all()
        return self._settings(user)._res_users_settings_format()["int_filemanager_open_mode_resolved"]

    def test_without_any_choice_one_click_opens(self):
        self.assertEqual(self._settings(self.alice).int_filemanager_open_mode, "default")
        self.assertEqual(self._resolved(self.alice), "single")

    def test_the_default_of_the_filemanager_reaches_the_browser(self):
        self.env["ir.config_parameter"].sudo().set_param(PARAMETER, "double")
        self.assertEqual(self._resolved(self.alice), "double")
        self.assertEqual(self._resolved(self.bob), "double")

    def test_the_default_is_a_setting_of_the_settings_page(self):
        settings = self.env["res.config.settings"].create({"int_filemanager_default_open_mode": "double"})
        settings.execute()
        self.assertEqual(self.env["ir.config_parameter"].sudo().get_param(PARAMETER), "double")

    def test_the_choice_of_a_user_beats_the_default(self):
        self.env["ir.config_parameter"].sudo().set_param(PARAMETER, "double")
        self.alice.with_user(self.alice).write({"int_filemanager_open_mode": "single"})
        self.assertEqual(self._resolved(self.alice), "single")
        self.assertEqual(self._resolved(self.bob), "double")

    def test_a_user_changes_the_choice_in_the_preferences(self):
        self.assertEqual(self.alice.with_user(self.alice).int_filemanager_open_mode, "default")
        self.alice.with_user(self.alice).write({"int_filemanager_open_mode": "double"})
        self.assertEqual(self._settings(self.alice).int_filemanager_open_mode, "double")
        self.assertEqual(self._settings(self.bob).int_filemanager_open_mode, "default")

    def test_the_webclient_sets_the_choice_the_way_it_sets_any_setting(self):
        result = self._settings(self.alice).with_user(self.alice).set_res_users_settings(
            {"int_filemanager_open_mode": "double"}
        )
        self.assertEqual(result["int_filemanager_open_mode"], "double")
        self.assertEqual(self._resolved(self.alice), "double")
