import io
import os

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, new_test_user, tagged


def remove(path):
    if os.path.exists(path):
        os.unlink(path)


@tagged("post_install", "-at_install")
class TestFolderArchive(TransactionCase):
    """Archiving or restoring a folder does it on everything below, like a project on its tasks."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Folder = cls.env["int.filemanager.folder"]
        cls.Document = cls.env["int.filemanager.document"]
        # top > mid > leaf, and a sibling that must stay as it is
        cls.top = cls.Folder.create({"name": "Top", "access_mode": "open"})
        cls.mid = cls.Folder.create({"name": "Mid", "parent_id": cls.top.id})
        cls.leaf = cls.Folder.create({"name": "Leaf", "parent_id": cls.mid.id})
        cls.other = cls.Folder.create({"name": "Other", "access_mode": "open"})

    def _document(self, folder, name="a.txt", content=b"x"):
        document = self.Document._create_from_stream(io.BytesIO(content), name, folder)
        self.addCleanup(remove, self.Document._blob_path(document.checksum))
        return document

    def _active(self, *records):
        return [record.active for record in records]

    # --- archiving -----------------------------------------------------------

    def test_archiving_a_folder_archives_what_is_below(self):
        in_top, in_mid, in_leaf = self._document(self.top), self._document(self.mid), self._document(self.leaf)
        elsewhere = self._document(self.other)
        self.top.action_archive()
        self.assertEqual(self._active(self.top, self.mid, self.leaf), [False] * 3)
        self.assertEqual(self._active(in_top, in_mid, in_leaf), [False] * 3)
        self.assertEqual(self._active(self.other, elsewhere), [True, True])

    def test_archiving_a_subfolder_leaves_the_parent_alone(self):
        document = self._document(self.leaf)
        self.mid.action_archive()
        self.assertEqual(self._active(self.top, self.mid, self.leaf, document), [True, False, False, False])

    def test_what_a_user_does_not_see_below_is_archived_too(self):
        user = new_test_user(
            self.env, login="archive_user", groups="base.group_user,int_filemanager.int_filemanager_group_user"
        )
        hidden = self.Folder.create(
            {"name": "Hidden", "parent_id": self.top.id, "access_mode": "restricted"}
        )
        document = self._document(hidden)
        self.assertNotIn(hidden, self.Folder.with_user(user).search([]))
        self.top.with_user(user).action_archive()
        self.assertEqual(self._active(hidden, document), [False, False])

    def test_an_archived_folder_cannot_be_uploaded_into_but_keeps_its_place(self):
        self.leaf.action_archive()
        self.assertNotIn(self.leaf, self.Folder.search([]))
        self.assertIn(self.leaf, self.Folder.with_context(active_test=False).search([]))

    # --- restoring -----------------------------------------------------------

    def test_restoring_a_folder_restores_what_is_below(self):
        in_mid, in_leaf = self._document(self.mid), self._document(self.leaf)
        self.top.action_archive()
        self.top.action_unarchive()
        self.assertEqual(self._active(self.top, self.mid, self.leaf, in_mid, in_leaf), [True] * 5)

    def test_restoring_leaves_other_folders_alone(self):
        elsewhere = self._document(self.other)
        elsewhere.active = False
        self.top.action_archive()
        self.top.action_unarchive()
        self.assertFalse(elsewhere.active)

    def test_a_folder_below_an_archived_folder_cannot_be_restored_alone(self):
        self.top.action_archive()
        with self.assertRaisesRegex(UserError, "Restore the folder Top first"):
            self.mid.action_unarchive()

    def test_a_document_in_an_archived_folder_cannot_be_restored_alone(self):
        document = self._document(self.leaf)
        self.mid.action_archive()
        with self.assertRaisesRegex(UserError, "Restore the folder Leaf first"):
            document.action_unarchive()

    def test_a_document_may_be_restored_when_its_folder_is_active(self):
        document = self._document(self.leaf)
        document.action_archive()
        document.action_unarchive()
        self.assertTrue(document.active)

    def test_a_folder_is_not_restored_when_its_name_is_taken(self):
        self.mid.action_archive()
        self.Folder.create({"name": "mid", "parent_id": self.top.id})
        with self.assertRaisesRegex(UserError, "taken: Mid"):
            self.mid.action_unarchive()
        self.assertFalse(self.mid.active)

    def test_a_top_folder_is_not_restored_when_its_name_is_taken(self):
        self.top.action_archive()
        self.Folder.create({"name": "TOP"})
        with self.assertRaisesRegex(UserError, "(?i)taken: top"):
            self.top.action_unarchive()
        self.assertFalse(self.top.active)

    def test_a_folder_is_not_restored_when_a_name_below_is_taken(self):
        old = self._document(self.leaf, "a.txt", b"old")
        old.active = False
        self._document(self.leaf, "A.TXT", b"new")
        self.top.action_archive()
        with self.assertRaisesRegex(UserError, "taken: "):
            self.top.action_unarchive()
        self.assertEqual(self._active(self.top, self.mid, self.leaf), [False] * 3)

    def test_two_archived_folders_with_one_name_are_not_restored_together(self):
        first = self.Folder.create({"name": "Twin", "parent_id": self.top.id})
        first.action_archive()
        second = self.Folder.create({"name": "Twin", "parent_id": self.top.id})
        second.action_archive()
        with self.assertRaisesRegex(UserError, "taken: Twin"):
            (first + second).action_unarchive()
        first.action_unarchive()
        self.assertTrue(first.active)

    def test_the_message_names_the_first_few_names_only(self):
        for number in range(8):
            self._document(self.leaf, f"name{number}.txt", bytes([number])).active = False
            self._document(self.leaf, f"NAME{number}.TXT", bytes([number, 1]))
        self.top.action_archive()
        with self.assertRaises(UserError) as caught:
            self.top.action_unarchive()
        self.assertEqual(caught.exception.args[0].split("taken: ")[1].count(","), 4)
