from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase, new_test_user, tagged

from .test_folder_access import AccessCase

READER_GROUPS = "base.group_user,int_filemanager.int_filemanager_group_reader"


@tagged("post_install", "-at_install")
class TestFolderMenu(AccessCase, TransactionCase):
    """What the menu of a folder in the search panel calls on the server.

    The menu leaves out what a reader can never do; these tests are the part that does not hide
    behind the interface: the server decides.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._set_up_access()
        cls.reader = new_test_user(cls.env, login="menu_reader", groups=READER_GROUPS)

    def test_rename_is_the_dialog_of_the_new_folder_for_a_folder_that_exists(self):
        action = self.env.ref("int_filemanager.int_filemanager_folder_action_rename")
        self.assertEqual(action.res_model, "int.filemanager.folder")
        self.assertEqual(action.target, "new")
        self.assertEqual(action.view_mode, "form")
        self.assertEqual(action.view_id, self.env.ref("int_filemanager.int_filemanager_folder_view_form_dialog"))
        # Not bound to the model: it needs the id that the menu passes as `resId`.
        self.assertFalse(action.binding_model_id)

    def test_a_user_renames_a_folder_in_the_dialog(self):
        view = self.env.ref("int_filemanager.int_filemanager_folder_view_form_dialog")
        self.assertIn('name="name"', view.arch_db)
        self.deep.with_user(self.alice).write({"name": "Deeper"})
        self.assertEqual(self.deep.name, "Deeper")

    def test_a_user_archives_the_folder_with_what_is_in_it(self):
        document = self._document(self.deep)
        self.shared.with_user(self.alice).action_archive()
        self.assertFalse(self.shared.active or self.deep.active or document.active)

    def test_a_reader_may_neither_rename_nor_archive_nor_move(self):
        folder = self.shared.with_user(self.reader)
        with self.assertRaises(AccessError):
            folder.write({"name": "Renamed"})
        with self.assertRaises(AccessError):
            folder.action_archive()
        with self.assertRaises(AccessError):
            self.env["int.filemanager.move"].with_user(self.reader).with_context(
                default_folder_ids=self.shared.ids
            ).create({})

    def test_a_reader_downloads_what_the_reader_sees(self):
        action = self.shared.with_user(self.reader).action_download()
        self.assertEqual(action["url"], f"/int_filemanager/folder_zip/{self.shared.id}")
