from odoo.tests.common import TransactionCase, tagged

from .test_folder_access import AccessCase


@tagged("post_install", "-at_install")
class TestFolderCounts(AccessCase, TransactionCase):
    """The numbers on the smart buttons of the folder form: what lies right in it, as the user sees it."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._set_up_access()

    def test_a_folder_counts_its_own_documents_and_subfolders_not_those_below(self):
        self._document(self.shared, "a.txt")
        self._document(self.shared, "b.txt")
        self._document(self.deep, "c.txt")
        self.assertEqual((self.shared.document_count, self.shared.child_count), (2, 1))
        self.assertEqual((self.deep.document_count, self.deep.child_count), (1, 0))

    def test_archived_documents_and_subfolders_are_not_counted(self):
        document = self._document(self.shared)
        document.action_archive()
        self.deep.action_archive()
        self.assertEqual((self.shared.document_count, self.shared.child_count), (0, 0))

    def test_the_user_counts_only_what_the_rules_show(self):
        self._document(self.secret)
        hidden = self.Folder.create({"name": "Hidden", "parent_id": self.shared.id, "access_mode": "restricted"})
        self._document(hidden)
        self._document(self.shared)
        shared = self.shared.with_user(self.alice)
        self.assertEqual((shared.document_count, shared.child_count), (1, 1))
        self.assertEqual((self.shared.child_count, self.shared.document_count), (2, 1))

    def test_a_new_folder_has_no_counts(self):
        folder = self.Folder.new({"name": "New"})
        self.assertEqual((folder.document_count, folder.child_count), (0, 0))

    def test_the_buttons_open_the_documents_and_subfolders_of_the_folder(self):
        document = self._document(self.shared)
        action = self.shared.action_open_documents()
        self.assertEqual(self.Document.search(action["domain"]), document)
        action = self.shared.action_open_children()
        self.assertEqual(self.Folder.search(action["domain"]), self.deep)
        self.assertEqual(action["context"], {"default_parent_id": self.shared.id})
