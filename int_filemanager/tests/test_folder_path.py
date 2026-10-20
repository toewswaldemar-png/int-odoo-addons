from odoo.tests.common import TransactionCase, tagged

from .test_folder_access import AccessCase

PATH = {"hierarchical_naming": True}


@tagged("post_install", "-at_install")
class TestFolderPath(AccessCase, TransactionCase):
    """The path of a folder in the field that picks one: as far as the user may read it."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._set_up_access()

    def _path(self, folder, user=None):
        folder = folder.with_context(**PATH)
        return (folder.with_user(user) if user else folder).display_name

    def test_the_name_is_the_plain_name_unless_a_view_asks_for_the_path(self):
        self.assertEqual(self.deep.display_name, "Deep")
        self.assertEqual(self.deep.with_user(self.alice).display_name, "Deep")

    def test_the_path_names_every_folder_above(self):
        self.assertEqual(self._path(self.deep), "Shared / Deep")
        self.assertEqual(self._path(self.shared), "Shared")
        below = self.Folder.create({"name": "Below", "parent_id": self.deep.id})
        self.assertEqual(self._path(below, self.alice), "Shared / Deep / Below")

    def test_the_administrators_read_the_whole_path(self):
        self.assertEqual(self._path(self.inner, self.boss), "Secret / Inner")

    def test_a_folder_above_that_the_user_may_not_read_is_not_named(self):
        opened = self.Folder.create(
            {"name": "Opened", "parent_id": self.secret.id, "access_mode": "open"}
        )
        self.assertIn(opened, self._seen_by(self.alice))
        self.assertEqual(self._path(opened, self.alice), "… / Opened")
        self.assertNotIn("Secret", self._path(opened, self.alice))
        # What is above the hidden one is not looked at any more, whatever it is.
        deeper = self.Folder.create({"name": "Deeper", "parent_id": opened.id})
        self.assertEqual(self._path(deeper, self.alice), "… / Opened / Deeper")

    def test_the_path_follows_a_new_name_and_a_move(self):
        self.shared.name = "Renamed"
        self.deep.invalidate_recordset()
        self.assertEqual(self._path(self.deep), "Renamed / Deep")
        other = self.Folder.create({"name": "Other", "access_mode": "open"})
        self.deep.parent_id = other
        self.assertEqual(self._path(self.deep), "Other / Deep")

    def test_the_path_of_a_folder_that_is_not_saved_is_its_name(self):
        self.assertEqual(self._path(self.Folder.new({"name": "Draft"})), "Draft")

    def test_a_folder_stands_right_below_its_parent_in_the_order(self):
        # By the last name alone it would be Hallo, Test, Top.
        top = self.Folder.create({"name": "Top", "access_mode": "open"})
        hallo = self.Folder.create({"name": "Hallo", "parent_id": top.id})
        test = self.Folder.create({"name": "Test", "parent_id": top.id})
        folders = top | hallo | test
        self.assertEqual(self.Folder.search([("id", "in", folders.ids)]).mapped("name"), ["Top", "Hallo", "Test"])
        top.name = "Alpha"
        self.assertEqual(hallo.complete_name, "Alpha / Hallo")
        self.assertEqual(self.Folder.search([("id", "in", folders.ids)]).mapped("name"), ["Alpha", "Hallo", "Test"])
        test.parent_id = False
        self.assertEqual(test.complete_name, "Test")
        self.assertEqual(self.Folder.search([("id", "in", folders.ids)]).mapped("name"), ["Alpha", "Hallo", "Test"])

    def test_the_sort_key_does_not_give_away_a_hidden_folder(self):
        opened = self.Folder.create(
            {"name": "Opened", "parent_id": self.secret.id, "access_mode": "open"}
        )
        self.assertEqual(opened.complete_name, "Secret / Opened")
        values = opened.with_user(self.alice).read(["name", "complete_name"])[0]
        self.assertEqual(values["name"], "Opened")
        self.assertNotIn("complete_name", values)

    def test_the_search_for_a_folder_shows_the_paths(self):
        result = self.Folder.with_user(self.alice).with_context(**PATH).name_search("Deep")
        self.assertEqual([name for __, name in result], ["Shared / Deep"])

    def test_the_fields_that_pick_a_folder_ask_for_the_path(self):
        documents = self.Document.get_views([(False, "list"), (False, "form")])
        folders = self.Folder.get_views([(False, "list"), (False, "form")])
        for views in (documents, folders):
            for view_type in ("list", "form"):
                self.assertIn("hierarchical_naming", views["views"][view_type]["arch"], view_type)

    def test_the_chatter_keeps_the_plain_name_of_a_folder(self):
        document = self._document(self.deep)
        nested = self.Folder.create({"name": "Nested", "parent_id": self.shared.id})
        self.env.cr.precommit.run()
        document.with_context(**PATH).write({"folder_id": nested.id})
        self.env.cr.precommit.run()
        value = self.env["mail.tracking.value"].search(
            [("mail_message_id.model", "=", document._name), ("mail_message_id.res_id", "=", document.id)]
        )
        self.assertEqual((value.old_value_char, value.new_value_char), ("Deep", "Nested"))
        nested.with_context(**PATH).write({"parent_id": self.deep.id})
        self.env.cr.precommit.run()
        value = self.env["mail.tracking.value"].search(
            [("mail_message_id.model", "=", nested._name), ("mail_message_id.res_id", "=", nested.id)]
        )
        self.assertEqual((value.old_value_char, value.new_value_char), ("Shared", "Deep"))
