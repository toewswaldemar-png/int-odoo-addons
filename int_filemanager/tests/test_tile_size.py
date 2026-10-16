from odoo.tests.common import TransactionCase, new_test_user, tagged


@tagged("post_install", "-at_install")
class TestTileSize(TransactionCase):
    """The size of the cards of the kanban is a setting of the user (``res.users.settings``)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.alice = new_test_user(
            cls.env, login="tile_alice", groups="base.group_user,int_filemanager.int_filemanager_group_user"
        )
        cls.bob = new_test_user(
            cls.env, login="tile_bob", groups="base.group_user,int_filemanager.int_filemanager_group_user"
        )

    def _settings(self, user):
        return self.env["res.users.settings"].with_user(user)._find_or_create_for_user(user)

    def test_the_default_is_medium(self):
        self.assertEqual(self._settings(self.alice).int_filemanager_tile_size, "medium")

    def test_the_browser_gets_the_size_with_the_other_settings(self):
        # `user.settings` of the webclient is this (`ir.http.session_info`).
        formatted = self._settings(self.alice)._res_users_settings_format()
        self.assertEqual(formatted["int_filemanager_tile_size"], "medium")

    def test_a_user_sets_the_size_the_way_the_webclient_does(self):
        settings = self._settings(self.alice)
        result = settings.with_user(self.alice).set_res_users_settings(
            {"int_filemanager_tile_size": "large"}
        )
        self.assertEqual(result["int_filemanager_tile_size"], "large")
        self.assertEqual(self._settings(self.alice).int_filemanager_tile_size, "large")

    def test_the_size_belongs_to_the_user(self):
        self._settings(self.alice).with_user(self.alice).set_res_users_settings(
            {"int_filemanager_tile_size": "small"}
        )
        self.assertEqual(self._settings(self.bob).int_filemanager_tile_size, "medium")
