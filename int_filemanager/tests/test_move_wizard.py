from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase, tagged

from .test_folder_access import AccessCase


@tagged("post_install", "-at_install")
class TestMoveWizard(AccessCase, TransactionCase):
    """The dialog "Move to...": what a click on "Move" does to the ticked documents or folders."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._set_up_access()
        cls.Move = cls.env["int.filemanager.move"]
        cls.other = cls.Folder.create({"name": "Other", "access_mode": "open"})

    def _wizard(self, documents=None, folders=None, target=None, user=None):
        """The wizard as the action makes it: the ticked records come in through the context."""
        context = {}
        if documents:
            context["default_document_ids"] = documents.ids
        if folders:
            context["default_folder_ids"] = folders.ids
        return self.Move.with_user(user or self.alice).with_context(**context).create(
            {"target_folder_id": target.id if target else False}
        )

    # --- documents -----------------------------------------------------------------------

    def test_the_documents_go_into_the_folder(self):
        first, second = self._document(self.shared, "a.txt"), self._document(self.deep, "b.txt", b"other")
        result = self._wizard(first + second, target=self.other).action_move()
        self.assertEqual((first.folder_id, second.folder_id), (self.other, self.other))
        self.assertEqual(result, {"type": "ir.actions.client", "tag": "soft_reload"})

    def test_a_document_that_is_there_already_stays(self):
        document = self._document(self.other)
        self._wizard(document, target=self.other).action_move()
        self.assertEqual(document.folder_id, self.other)

    def test_documents_need_a_target(self):
        document = self._document(self.shared)
        with self.assertRaisesRegex(UserError, "Choose the folder"):
            self._wizard(document).action_move()
        self.assertEqual(document.folder_id, self.shared)

    def test_nothing_ticked_is_nothing_to_move(self):
        with self.assertRaisesRegex(UserError, "Select at least one"):
            self._wizard(target=self.other).action_move()

    def test_taken_names_are_named_and_nothing_moves(self):
        self._document(self.other, "same.txt", b"there")
        first = self._document(self.shared, "same.txt", b"mine")
        second = self._document(self.shared, "free.txt", b"free")
        with self.assertRaisesRegex(UserError, "same.txt"):
            self._wizard(first + second, target=self.other).action_move()
        self.assertEqual((first.folder_id, second.folder_id), (self.shared, self.shared))

    def test_a_folder_the_user_does_not_see_is_no_target(self):
        document = self._document(self.shared)
        with self.assertRaises(AccessError):
            self._wizard(document, target=self.secret).action_move()
        self.assertEqual(document.folder_id, self.shared)

    def test_an_invitation_makes_the_folder_a_target(self):
        document = self._document(self.shared)
        self._invite(self.secret, self.alice)
        self._wizard(document, target=self.secret).action_move()
        self.assertEqual(document.folder_id, self.secret)

    def test_an_archived_folder_is_no_target(self):
        document = self._document(self.shared)
        self.other.action_archive()
        with self.assertRaisesRegex(UserError, "archived"):
            self._wizard(document, target=self.other).action_move()

    def test_a_document_the_user_does_not_see_is_not_moved(self):
        hidden = self._document(self.inner, "hidden.txt")
        with self.assertRaises(AccessError):
            self._wizard(hidden, target=self.other).action_move()
        self.assertEqual(hidden.folder_id, self.inner)

    # --- folders -------------------------------------------------------------------------

    def test_the_folders_go_below_the_folder_with_what_is_in_them(self):
        document = self._document(self.deep)
        self._wizard(folders=self.deep, target=self.other).action_move()
        self.assertEqual(self.deep.parent_id, self.other)
        self.assertEqual(document.folder_id, self.deep)

    def test_a_folder_goes_to_the_top_without_a_target(self):
        self._wizard(folders=self.deep).action_move()
        self.assertFalse(self.deep.parent_id)

    def test_a_folder_does_not_go_below_itself(self):
        child = self.Folder.create({"name": "Child", "parent_id": self.deep.id})
        with self.assertRaises(UserError):
            self._wizard(folders=self.deep, target=child).action_move()
        self.assertEqual(self.deep.parent_id, self.shared)

    def test_the_tree_takes_the_company_of_the_new_parent(self):
        company = self.env["res.company"].create({"name": "Second"})
        self.alice.write({"company_ids": [(4, company.id)]})
        elsewhere = self.Folder.create({"name": "Elsewhere", "access_mode": "open", "company_id": company.id})
        child = self.Folder.create({"name": "Child", "parent_id": self.deep.id})
        self._wizard(folders=self.deep, target=elsewhere).action_move()
        self.assertEqual((self.deep.company_id, child.company_id), (company, company))

    def test_taken_folder_names_are_named(self):
        self.Folder.create({"name": "Deep", "parent_id": self.other.id})
        with self.assertRaisesRegex(UserError, "Deep"):
            self._wizard(folders=self.deep, target=self.other).action_move()
        self.assertEqual(self.deep.parent_id, self.shared)

    # --- the dialog ----------------------------------------------------------------------

    def test_the_summary_names_what_moves(self):
        documents = self._document(self.shared, "b.txt") + self._document(self.deep, "a.txt", b"other")
        self.assertEqual(self._wizard(documents).summary, "Documents (2): a.txt, b.txt")
        self.assertEqual(self._wizard(folders=self.deep).summary, "Folders (1): Deep")

    def test_a_user_without_the_group_cannot_open_it(self):
        with self.assertRaises(AccessError):
            self._wizard(user=self.outsider)

    def test_the_documents_list_has_the_dialog_as_an_item_of_its_menu_not_as_a_button(self):
        # The controller of the list adds the item (it has an icon there): no button in the head
        # of the list and no binding that would show it a second time in the "Actions" menu.
        action = self.env.ref("int_filemanager.int_filemanager_move_document_action")
        self.assertFalse(action.binding_model_id)
        arch = self.env.ref("int_filemanager.int_filemanager_document_view_list").arch_db
        self.assertNotIn(f'name="{action.id}"', arch)

    def test_the_item_of_the_menu_shows_for_those_who_may_open_the_dialog(self):
        # The controller asks for the right to create the dialog, the same right as the model.
        Access = self.env["ir.model.access"]
        self.assertTrue(Access.with_user(self.alice).check("int.filemanager.move", "create", False))
        self.assertFalse(Access.with_user(self.outsider).check("int.filemanager.move", "create", False))

    def test_the_folders_list_has_the_button_for_the_dialog(self):
        arch = self.env.ref("int_filemanager.int_filemanager_folder_view_list").arch_db
        action = self.env.ref("int_filemanager.int_filemanager_move_folder_action")
        self.assertIn(f'name="{action.id}"', arch)

    def test_the_actions_get_the_ticked_records_from_the_active_ids(self):
        self.assertIn("default_document_ids", self.env.ref("int_filemanager.int_filemanager_move_document_action").context)
        self.assertIn("default_folder_ids", self.env.ref("int_filemanager.int_filemanager_move_folder_action").context)
