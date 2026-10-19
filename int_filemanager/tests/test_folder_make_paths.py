from unittest.mock import patch

from odoo.exceptions import AccessError, ConcurrencyError, UserError
from odoo.tests.common import TransactionCase, tagged

from .test_folder_access import AccessCase


@tagged("post_install", "-at_install")
class TestFolderMakePaths(AccessCase, TransactionCase):
    """The folders of an upload: made below the chosen folder, an existing one is used."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._set_up_access()

    def _make(self, paths, folder=None, user=None):
        return (folder or self.shared).with_user(user or self.alice).action_make_paths(paths)

    def _below(self, folder=None):
        return self.Folder.with_context(active_test=False).search([("id", "child_of", (folder or self.shared).id)])

    # --- making --------------------------------------------------------------------------

    def test_the_folders_of_a_path_are_made_one_below_the_other(self):
        result = self._make(["Photos/2025/June", "Photos/2025/July", "Photos/empty"])
        june, july, empty = (self.Folder.browse(result[path]) for path in ("Photos/2025/June", "Photos/2025/July", "Photos/empty"))
        self.assertEqual((june.name, july.name, empty.name), ("June", "July", "empty"))
        self.assertEqual(june.parent_id, july.parent_id)
        self.assertEqual(june.parent_id.name, "2025")
        self.assertEqual(june.parent_id.parent_id.name, "Photos")
        self.assertEqual(june.parent_id.parent_id.parent_id, self.shared)
        self.assertEqual(empty.parent_id, june.parent_id.parent_id)
        self.assertEqual(len(self._below()), 1 + 1 + 1 + 1 + 1 + 1 + 1)  # shared, deep, Photos, 2025, June, July, empty

    def test_a_second_call_makes_nothing_and_gives_the_same_folders(self):
        first = self._make(["Photos/2025", "Photos/2026"])
        count = len(self._below())
        self.assertEqual(self._make(["Photos/2025", "Photos/2026"]), first)
        self.assertEqual(len(self._below()), count)

    def test_a_folder_that_is_there_is_used_whatever_the_case(self):
        result = self._make(["DEEP/Sub", "deep/Sub2"])
        self.assertEqual(self.Folder.browse(result["DEEP/Sub"]).parent_id, self.deep)
        self.assertEqual(self.Folder.browse(result["deep/Sub2"]).parent_id, self.deep)
        self.assertEqual(self.deep.name, "Deep")

    def test_paths_that_differ_in_case_are_one_folder(self):
        result = self._make(["Photos/a", "photos/A"])
        self.assertEqual(result["Photos/a"], result["photos/A"])
        self.assertEqual(len(self._below()), 4)

    def test_the_subfolder_has_the_company_of_its_parent_and_the_rights_of_it(self):
        other = self.env["res.company"].create({"name": "Other"})
        top = self.Folder.create({"name": "Elsewhere", "access_mode": "open", "company_id": other.id})
        self.alice.write({"company_ids": [(4, other.id)]})
        folder = self.Folder.browse(self._make(["Sub"], top)["Sub"])
        self.assertEqual(folder.company_id, other)
        self.assertEqual(folder.access_folder_id, top)

    def test_the_names_are_composed_and_cleaned(self):
        result = self._make(["Café \t/x\x00y "])
        folder = self.Folder.browse(result["Café \t/x\x00y "])
        self.assertEqual((folder.parent_id.name, folder.name), ("Café", "xy"))

    def test_no_message_is_written_for_each_folder(self):
        folder = self.Folder.browse(self._make(["Quiet"])["Quiet"])
        self.assertFalse(folder.message_ids)

    def test_no_paths_make_nothing(self):
        self.assertEqual(self._make([]), {})

    # --- what is refused -----------------------------------------------------------------

    def test_a_path_that_is_none_is_refused(self):
        long_name = "x" * 256
        deep_path = "/".join(["d"] * 51)
        for path in ("", "/abs", "a//b", "a/./b", "a/..", "../a", "a\\b", " ", "a/ /b", long_name, deep_path, None, 5):
            with self.subTest(path=path), self.assertRaisesRegex(UserError, "valid folder path"):
                self._make([path])
        self.assertEqual(len(self._below()), 2)

    def test_the_longest_name_and_the_deepest_path_are_fine(self):
        self.assertEqual(len(self._make(["x" * 255, "/".join(["d"] * 50)])), 2)

    def test_a_refused_path_makes_none_of_the_others(self):
        with self.assertRaises(UserError), self.env.cr.savepoint():
            self._make(["Good/one", "bad/../two"])
        self.assertEqual(len(self._below()), 2)

    def test_too_many_paths_at_once_are_refused(self):
        with self.assertRaisesRegex(UserError, "Too many"):
            self._make([f"f{number}" for number in range(501)])

    def test_the_folder_must_be_one_the_user_may_write_into(self):
        with self.assertRaises(AccessError):
            self._make(["x"], self.secret)
        with self.assertRaises(AccessError):
            self._make(["x"], user=self.outsider)
        self._invite(self.secret, self.alice)
        self._make(["x"], self.secret)

    def test_an_archived_folder_takes_nothing(self):
        self.deep.action_archive()
        with self.assertRaisesRegex(UserError, "archived"):
            self._make(["x"], self.deep)

    def test_a_folder_that_is_archived_does_not_count(self):
        old = self.Folder.create({"name": "Old", "parent_id": self.shared.id})
        old.action_archive()
        made = self.Folder.browse(self._make(["Old"])["Old"])
        self.assertNotEqual(made, old)
        self.assertTrue(made.active)

    def test_a_folder_the_user_does_not_see_is_not_used_and_not_named(self):
        hidden = self.Folder.create({"name": "Hush", "parent_id": self.shared.id, "access_mode": "restricted"})
        self.assertNotIn(hidden, self._seen_by(self.alice))
        with self.assertRaises(UserError) as caught:
            self._make(["hush/below"])
        self.assertIn("not available", caught.exception.args[0])
        self.assertNotIn("restricted", caught.exception.args[0])
        self.assertFalse(hidden.child_ids)

    # --- two uploads at once -------------------------------------------------------------

    def test_a_folder_that_another_transaction_has_just_made_is_a_case_for_a_new_try(self):
        # Odoo's transaction does not see what committed after its start: the search finds
        # nothing, the unique index says the folder is there, and a new search would not see it
        # either. ``ConcurrencyError`` makes Odoo take a new view and call again.
        self.Folder.create({"name": "Race", "parent_id": self.shared.id})
        shared = self.shared.with_user(self.alice)
        with (
            patch.object(type(self.Folder), "search", return_value=self.Folder.browse()),
            patch.object(type(self.Folder), "search_count", return_value=0),
            self.assertRaises(ConcurrencyError),
        ):
            shared._find_or_make(shared, "Race")
        # Whatever it ended with, the transaction is usable and a new try finds the folder.
        self.assertEqual(self._make(["race"])["race"], self.Folder.search([("name", "=", "Race")]).id)
