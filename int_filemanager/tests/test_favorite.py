from datetime import datetime

from odoo.exceptions import AccessError, MissingError
from odoo.tests.common import TransactionCase, new_test_user, tagged

from .test_folder_access import AccessCase
from .test_rights_matrix import READER_GROUPS

LONG_AGO = datetime(2020, 1, 1, 12, 0, 0)


@tagged("post_install", "-at_install")
class TestFavorite(AccessCase, TransactionCase):
    """The star of a user on a folder or a document: theirs alone, and the record stays as it was.

    A reader may set it though readers may not write; it is asked whether the user reads the record.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._set_up_access()
        cls.reader = new_test_user(cls.env, login="favorite_reader", groups=READER_GROUPS)

    def setUp(self):
        super().setUp()
        self.document = self._document(self.shared, "open.txt", b"open")
        self.hidden = self._document(self.secret, "hidden.txt", b"hidden")

    def _age(self, record):
        self.env.flush_all()
        self.env.cr.execute(f"UPDATE {record._table} SET write_date = %s WHERE id = %s", [LONG_AGO, record.id])
        self.env.invalidate_all()

    def test_both_sides_of_a_star_are_one_table(self):
        for model, field in (
            ("int.filemanager.document", "int_filemanager_favorite_document_ids"),
            ("int.filemanager.folder", "int_filemanager_favorite_folder_ids"),
        ):
            with self.subTest(model=model):
                record_side = self.env[model]._fields["favorite_user_ids"]
                user_side = self.env["res.users"]._fields[field]
                self.assertEqual(record_side.relation, user_side.relation)
                self.assertEqual(
                    (record_side.column1, record_side.column2), (user_side.column2, user_side.column1)
                )

    def test_a_star_is_the_users_and_leaves_the_record_as_it_was(self):
        for record in (self.document, self.shared):
            with self.subTest(record=record.display_name):
                self._age(record)
                messages = len(record.message_ids)
                record.with_user(self.alice).write({"is_favorite": True})
                self.env.invalidate_all()
                self.assertEqual(record.write_date, LONG_AGO)
                self.assertEqual(len(record.message_ids), messages)
                self.assertEqual(record.favorite_user_ids, self.alice)
                self.assertTrue(record.with_user(self.alice).is_favorite)
                self.assertFalse(record.with_user(self.bob).is_favorite)
                record.with_user(self.alice).write({"is_favorite": False})
                self.assertFalse(record.with_user(self.alice).is_favorite)
                self.assertFalse(record.favorite_user_ids)

    def test_the_answer_is_not_kept_from_one_user_for_another(self):
        # No invalidation in between: the cache is read by user after user.
        self.document.with_user(self.alice).write({"is_favorite": True})
        self.document.with_user(self.bob).write({"is_favorite": True})
        self.document.with_user(self.alice).write({"is_favorite": False})
        self.assertFalse(self.document.with_user(self.alice).is_favorite)
        self.assertTrue(self.document.with_user(self.bob).is_favorite)
        self.assertEqual(self.document.favorite_user_ids, self.bob)

    def test_a_star_with_other_values_writes_the_other_values(self):
        self.document.with_user(self.alice).write({"is_favorite": True, "name": "other.txt"})
        self.assertEqual(self.document.name, "other.txt")
        self.assertTrue(self.document.with_user(self.alice).is_favorite)

    def test_a_reader_sets_a_star_but_changes_nothing_else(self):
        for record in (self.document, self.shared):
            with self.subTest(record=record.display_name):
                as_reader = record.with_user(self.reader)
                as_reader.write({"is_favorite": True})
                self.assertTrue(as_reader.is_favorite)
                with self.assertRaises(AccessError):
                    as_reader.write({"name": "other"})

    def test_nobody_stars_what_they_may_not_read(self):
        # The star is written as superuser, so the right to read is asked first.
        with self.assertRaises(AccessError):
            self.hidden.with_user(self.bob).write({"is_favorite": True})
        with self.assertRaises(AccessError):
            self.document.with_user(self.outsider).write({"is_favorite": True})
        self.assertFalse(self.hidden.favorite_user_ids | self.document.favorite_user_ids)

    def test_an_id_that_is_gone_is_told_from_a_hidden_one_as_by_any_write(self):
        as_bob = self.Document.with_user(self.bob)
        with self.assertRaises(AccessError):
            as_bob.browse(self.hidden.id).write({"name": "x"})
        with self.assertRaises(MissingError):
            as_bob.browse(987654).write({"name": "x"})
        with self.assertRaises(AccessError):
            as_bob.browse(self.hidden.id).write({"is_favorite": True})
        with self.assertRaises(MissingError):
            as_bob.browse(987654).write({"is_favorite": True})

    def test_the_search_finds_the_stars_of_the_user_only(self):
        other = self._document(self.shared, "other.txt", b"other")
        self.document.with_user(self.alice).write({"is_favorite": True})
        domain = [("folder_id", "=", self.shared.id)]
        as_alice = self.Document.with_user(self.alice)
        self.assertEqual(as_alice.search([*domain, ("is_favorite", "=", True)]), self.document)
        self.assertEqual(as_alice.search([*domain, ("is_favorite", "=", False)]), other)
        self.assertEqual(as_alice.search([*domain, ("is_favorite", "!=", True)]), other)
        self.assertFalse(self.Document.with_user(self.bob).search([*domain, ("is_favorite", "=", True)]))

    def test_a_folder_is_created_with_a_star_and_takes_it_away_when_it_goes(self):
        folder = self.Folder.with_user(self.alice).create(
            {"name": "Starred", "parent_id": self.shared.id, "is_favorite": True}
        )
        self.assertTrue(folder.with_user(self.alice).is_favorite)
        self.assertFalse(folder.with_user(self.bob).is_favorite)
        self.assertIn(folder, self.alice.sudo().int_filemanager_favorite_folder_ids)
        folder.unlink()
        self.assertNotIn(folder, self.alice.sudo().int_filemanager_favorite_folder_ids)

    def test_a_star_is_not_copied_with_the_record(self):
        folder = self.Folder.create({"name": "Copied", "parent_id": self.shared.id})
        folder.with_user(self.alice).write({"is_favorite": True})
        self.assertFalse(folder.copy({"name": "Copy"}).favorite_user_ids)

    def test_the_users_keep_their_stars_when_a_record_is_archived(self):
        self.document.with_user(self.alice).write({"is_favorite": True})
        self.document.write({"active": False})
        self.assertEqual(self.document.favorite_user_ids, self.alice)
        self.document.with_user(self.alice).write({"is_favorite": False})
        self.assertFalse(self.document.favorite_user_ids)
