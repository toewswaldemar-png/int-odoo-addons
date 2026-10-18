from psycopg2 import IntegrityError

from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase, tagged
from odoo.tools import mute_logger

from .test_folder_access import AccessCase


@tagged("post_install", "-at_install")
class TestMoveTarget(AccessCase, TransactionCase):
    """Where a document or a folder may be put, and what holds for the tree whoever moves it.

    ``self.env`` is the superuser: the rules of the tree (the folder is in use, the names, the
    company) must hold for it too. The rights of the user are tried with ``with_user``.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._set_up_access()
        cls.other = cls.Folder.create({"name": "Other", "access_mode": "open"})

    def _message(self, exception):
        return exception.exception.args[0]

    # --- rights: the user may write into the target --------------------------

    def test_a_document_cannot_be_put_into_a_hidden_folder(self):
        document = self._document(self.deep)
        with self.assertRaises(AccessError):
            document.with_user(self.alice).write({"folder_id": self.inner.id})
        self.assertEqual(document.folder_id, self.deep)

    def test_a_document_is_put_into_a_folder_the_user_may_write(self):
        document = self._document(self.deep)
        document.with_user(self.alice).write({"folder_id": self.other.id})
        self.assertEqual(document.folder_id, self.other)

    def test_a_folder_cannot_be_put_below_a_hidden_folder(self):
        with self.assertRaises(AccessError):
            self.deep.with_user(self.alice).write({"parent_id": self.inner.id})
        self.assertEqual(self.deep.parent_id, self.shared)

    def test_a_folder_is_put_below_a_folder_the_user_may_write(self):
        self.deep.with_user(self.alice).write({"parent_id": self.other.id})
        self.assertEqual(self.deep.parent_id, self.other)

    def test_a_folder_goes_to_the_top_level_without_a_target_to_check(self):
        self.deep.with_user(self.alice).write({"parent_id": False})
        self.assertFalse(self.deep.parent_id)

    def test_nothing_is_asked_of_the_superuser_but_the_rules_of_the_tree(self):
        document = self._document(self.deep)
        document.write({"folder_id": self.inner.id})
        self.assertEqual(document.folder_id, self.inner)

    # --- the rules of the tree, also for the superuser ------------------------

    def test_an_archived_folder_takes_nothing(self):
        archived = self.Folder.create({"name": "Archived", "active": False})
        document = self._document(self.deep)
        with self.assertRaises(UserError) as error:
            document.write({"folder_id": archived.id})
        self.assertIn("Archived", self._message(error))
        with self.assertRaises(UserError):
            self.deep.write({"parent_id": archived.id})
        with self.assertRaises(UserError):
            self.Folder.create({"name": "Below", "parent_id": archived.id})

    def test_the_names_that_are_taken_are_named(self):
        self._document(self.other, "Report.pdf")
        moving = self._document(self.deep, "report.PDF")
        with self.assertRaises(UserError) as error:
            moving.with_user(self.alice).write({"folder_id": self.other.id})
        self.assertIn("report.PDF", self._message(error))
        self.assertIn("Other", self._message(error))
        self.assertEqual(moving.folder_id, self.deep)

    def test_documents_that_come_together_with_one_name_are_named(self):
        first = self._document(self.deep, "twin.txt")
        second = self._document(self.shared, "TWIN.txt", b"other")
        with self.assertRaises(UserError) as error:
            (first + second).write({"folder_id": self.other.id})
        self.assertIn("twin.txt", self._message(error).lower())

    def test_only_the_first_names_are_shown_and_the_rest_is_counted(self):
        names = [f"file{number}.txt" for number in range(7)]
        for name in names:
            self._document(self.other, name, name.encode())
        moving = self.Document
        for name in names:
            moving |= self._document(self.deep, name, b"moving " + name.encode())
        with self.assertRaises(UserError) as error:
            moving.write({"folder_id": self.other.id})
        self.assertIn("(+2)", self._message(error))

    def test_a_document_that_stays_where_it_is_is_not_a_clash(self):
        document = self._document(self.deep, "stay.txt")
        document.with_user(self.alice).write({"folder_id": self.deep.id})
        self.assertEqual(document.folder_id, self.deep)

    def test_an_archived_document_does_not_clash(self):
        self._document(self.other, "old.txt").action_archive()
        moving = self._document(self.deep, "old.txt", b"newer")
        moving.write({"folder_id": self.other.id})
        self.assertEqual(moving.folder_id, self.other)

    def test_the_folders_that_are_taken_are_named(self):
        self.Folder.create({"name": "Same", "parent_id": self.other.id})
        moving = self.Folder.create({"name": "SAME", "parent_id": self.shared.id})
        with self.assertRaises(UserError) as error:
            moving.with_user(self.alice).write({"parent_id": self.other.id})
        self.assertIn("SAME", self._message(error))

    def test_two_moves_at_once_still_meet_the_unique_index(self):
        # The check looks first; what slips through is caught by the index of the database.
        self.Folder.create({"name": "Late", "parent_id": self.other.id})
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"):
            self.Folder.create({"name": "late", "parent_id": self.other.id})

    def test_a_folder_cannot_be_put_below_itself(self):
        with self.assertRaises(UserError):
            self.shared.write({"parent_id": self.deep.id})

    # --- the company of the tree ---------------------------------------------

    def _company(self):
        return self.env["res.company"].create({"name": "Move target company"})

    def test_a_subfolder_has_the_company_of_its_parent(self):
        company = self._company()
        top = self.Folder.create({"name": "Their top", "company_id": company.id})
        child = self.Folder.create(
            {"name": "Child", "parent_id": top.id, "company_id": self.env.company.id}
        )
        self.assertEqual(child.company_id, company)
        document = self._document(child)
        self.assertEqual(document.company_id, company)

    def test_a_tree_that_is_moved_takes_the_company_of_its_target(self):
        company = self._company()
        target = self.Folder.create({"name": "Their top", "company_id": company.id})
        top = self.Folder.create({"name": "My top", "company_id": self.env.company.id})
        child = self.Folder.create({"name": "My child", "parent_id": top.id})
        archived = self.Folder.create({"name": "My old", "parent_id": child.id, "active": False})
        document = self._document(child)
        top.write({"parent_id": target.id})
        for folder in (top, child, archived):
            self.assertEqual(folder.company_id, company, folder.name)
        self.assertEqual(document.company_id, company)

    def test_a_tree_that_is_moved_takes_the_company_for_a_user_too(self):
        # The superuser carries the company over the folders the user does not see.
        company = self._company()
        top = self.Folder.create({"name": "My top", "access_mode": "open"})
        target = self.Folder.create({"name": "Their top", "access_mode": "open", "company_id": company.id})
        self.alice.write({"company_ids": [(4, company.id)]})
        child = self.Folder.create({"name": "My child", "parent_id": top.id})
        top.with_user(self.alice).with_context(allowed_company_ids=[self.alice.company_id.id, company.id]).write(
            {"parent_id": target.id}
        )
        self.assertEqual(child.company_id, company)

    def test_the_company_of_a_top_folder_comes_down_to_what_is_below(self):
        company = self._company()
        top = self.Folder.create({"name": "My top", "company_id": self.env.company.id})
        child = self.Folder.create({"name": "My child", "parent_id": top.id})
        document = self._document(child)
        top.write({"company_id": company.id})
        self.assertEqual(child.company_id, company)
        self.assertEqual(document.company_id, company)

    def test_the_company_of_a_subfolder_is_not_changed_on_its_own(self):
        company = self._company()
        with self.assertRaises(UserError):
            self.deep.write({"company_id": company.id})
        self.assertEqual(self.deep.company_id, self.shared.company_id)

    def test_writing_the_company_a_subfolder_has_is_no_change(self):
        self.deep.write({"company_id": self.deep.company_id.id})
        self.assertEqual(self.deep.company_id, self.shared.company_id)

    def test_the_default_parent_of_the_context_gives_the_company_too(self):
        company = self._company()
        top = self.Folder.create({"name": "Their top", "company_id": company.id})
        child = self.Folder.with_context(default_parent_id=top.id).create({"name": "Child"})
        self.assertEqual((child.parent_id, child.company_id), (top, company))

    def test_a_folder_that_goes_to_the_top_level_keeps_its_company(self):
        company = self._company()
        top = self.Folder.create({"name": "Their top", "company_id": company.id})
        child = self.Folder.create({"name": "Child", "parent_id": top.id})
        child.write({"parent_id": False})
        self.assertEqual(child.company_id, company)
