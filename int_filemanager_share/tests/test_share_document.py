from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase, new_test_user, tagged

from odoo.addons.int_filemanager.tests.test_folder_access import AccessCase


@tagged("post_install", "-at_install")
class TestShareOfTheDocument(AccessCase, TransactionCase):
    """The buttons and the rights that the share links add to the documents and folders."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._set_up_access()
        cls.reader = new_test_user(
            cls.env,
            login="share_reader",
            groups="base.group_user,int_filemanager.int_filemanager_group_reader",
        )

    def test_the_share_button_of_the_list_is_for_the_group_that_may_share(self):
        # The same arch makes the buttons of the ticked rows and the menu of the right click.
        # The user without the group loads the list through the way over a linked record.
        self.env["int.filemanager.link"]._toggle_access_via_record(True)
        for user, has_button in ((self.alice, True), (self.outsider, False)):
            with self.subTest(user=user.login):
                views = self.Document.with_user(user).get_views([(False, "list")])
                self.assertEqual('name="action_share"' in views["views"]["list"]["arch"], has_button)

    def test_the_share_action_of_the_list_wants_one_document(self):
        document = self._document(self.shared, "a.txt", b"a")
        action = document.with_user(self.alice).action_share()
        self.assertEqual(action["context"], {"default_document_id": document.id})
        with self.assertRaises(UserError):
            (document + self._document(self.shared, "b.txt", b"b")).action_share()

    def test_a_reader_makes_no_share(self):
        with self.assertRaises(AccessError):
            self.env["int.filemanager.share"].with_user(self.reader).check_access("create")
        self.env["int.filemanager.share"].with_user(self.alice).check_access("create")

    def test_the_screens_of_a_reader_have_no_share_button(self):
        for model, view_type in (
            ("int.filemanager.document", "list"),
            ("int.filemanager.document", "form"),
            ("int.filemanager.folder", "list"),
            ("int.filemanager.folder", "form"),
        ):
            with self.subTest(model=model, view_type=view_type):
                arch = self.env[model].with_user(self.reader).get_views([(False, view_type)])["views"][view_type]["arch"]
                self.assertNotIn("action_share", arch)
