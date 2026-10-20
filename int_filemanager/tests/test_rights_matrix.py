from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase, tagged

from .test_folder_access import AccessCase


@tagged("post_install", "-at_install")
class TestRightsMatrix(AccessCase, TransactionCase):
    """What the groups may do with what they see: read, change, delete, create.

    A row marked "today" is a gap of the first rights model: seeing is changing. Whoever
    builds the group that only reads turns those rows around.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._set_up_access()
        cls.Tag = cls.env["int.filemanager.tag"]

    def setUp(self):
        super().setUp()
        self.document = self._document(self.shared, "a.txt", b"hello")

    # --- folders ----------------------------------------------------------------------------

    def test_a_folder_user_reads_changes_and_deletes_what_the_user_sees(self):
        # today: no group that only reads
        as_alice = self.shared.with_user(self.alice)
        self.assertEqual(as_alice.name, "Shared")
        as_alice.write({"name": "Renamed"})
        self.assertEqual(self.shared.name, "Renamed")
        mine = self.Folder.create({"name": "Mine", "access_mode": "open"})
        mine.with_user(self.alice).unlink()
        self.assertFalse(mine.exists())

    def test_a_folder_user_makes_a_top_folder(self):
        folder = self.Folder.with_user(self.alice).create({"name": "Mine"})
        self.assertEqual(folder.create_uid, self.alice)

    def test_a_follower_changes_and_deletes_the_folder_too(self):
        self._invite(self.secret, self.alice)
        as_alice = self.secret.with_user(self.alice)
        as_alice.write({"name": "Renamed"})
        self.assertEqual(self.secret.name, "Renamed")
        self.inner.with_user(self.alice).unlink()
        self.assertFalse(self.inner.exists())

    def test_a_user_who_does_not_see_a_folder_has_no_right_on_it(self):
        as_bob = self.secret.with_user(self.bob)
        for operation in ("read", "write", "unlink"):
            with self.assertRaises(AccessError):
                as_bob.check_access(operation)

    def test_a_user_without_the_group_has_no_right_on_the_folders(self):
        for operation in ("read", "write", "create", "unlink"):
            with self.assertRaises(AccessError):
                self.Folder.with_user(self.outsider).check_access(operation)

    def test_the_administrators_do_everything_with_every_folder(self):
        as_boss = self.secret.with_user(self.boss)
        for operation in ("read", "write", "unlink"):
            as_boss.check_access(operation)
        self.Folder.with_user(self.boss).check_access("create")

    # --- the lists of who may see (today: for everyone who sees the folder) -----------------

    def test_a_folder_user_reads_and_changes_who_may_see_the_folder(self):
        # today: the fields are for every user, not for the administrators only
        self.secret.access_user_ids = self.alice
        as_alice = self.secret.with_user(self.alice)
        self.assertEqual(as_alice.access_user_ids, self.alice)
        as_alice.write(
            {
                "access_mode": "open",
                "access_user_ids": [Command.link(self.bob.id)],
                "access_group_ids": [Command.link(self.env.ref("base.group_user").id)],
            }
        )
        self.assertEqual(self.secret.access_mode, "open")
        self.assertIn(self.secret, self._seen_by(self.bob))

    def test_a_follower_invites_others(self):
        self._invite(self.secret, self.alice)
        self.secret.with_user(self.alice).message_subscribe(partner_ids=[self.bob.partner_id.id])
        self.assertIn(self.secret, self._seen_by(self.bob))

    def test_the_fields_of_the_administrators_stay_closed_to_the_users(self):
        as_alice = self.shared.with_user(self.alice)
        for name in ("ocr_images", "model_folder_ids"):
            with self.assertRaises(AccessError):
                as_alice[name]  # noqa: B018
            with self.assertRaises(AccessError):
                as_alice.write({name: False})

    # --- documents --------------------------------------------------------------------------

    def test_a_folder_user_reads_changes_and_deletes_the_documents_of_what_the_user_sees(self):
        # today: no group that only reads
        as_alice = self.document.with_user(self.alice)
        self.assertEqual(as_alice.name, "a.txt")
        as_alice.write({"name": "b.txt"})
        self.assertEqual(self.document.name, "b.txt")
        as_alice.unlink()
        self.assertFalse(self.document.exists())

    def test_a_document_is_made_by_the_upload_not_by_the_orm(self):
        values = {"name": "c.txt", "folder_id": self.shared.id}
        with self.assertRaises(AccessError):
            self.Document.with_user(self.alice).create(values)
        with self.assertRaises(AccessError):
            self.Document.with_user(self.boss).create(values)

    def test_a_user_who_does_not_see_the_folder_has_no_right_on_its_documents(self):
        hidden = self._document(self.inner, "hidden.txt")
        as_bob = hidden.with_user(self.bob)
        for operation in ("read", "write", "unlink"):
            with self.assertRaises(AccessError):
                as_bob.check_access(operation)

    def test_a_user_without_the_group_has_no_right_on_the_documents(self):
        # without a link; the way over a linked record has its own rows, in test_link
        as_outsider = self.document.with_user(self.outsider)
        for operation in ("read", "write", "unlink"):
            with self.assertRaises(AccessError):
                as_outsider.check_access(operation)

    def test_the_administrators_do_everything_with_every_document(self):
        hidden = self._document(self.inner, "hidden.txt")
        as_boss = hidden.with_user(self.boss)
        for operation in ("read", "write", "unlink"):
            as_boss.check_access(operation)

    # --- tags -------------------------------------------------------------------------------

    def test_the_tags_are_for_every_folder_user_to_make_change_and_delete(self):
        # today: global, not tied to a folder
        tag = self.Tag.with_user(self.alice).create({"name": "Invoices"})
        self.assertEqual(self.Tag.with_user(self.bob).search([("name", "=", "Invoices")]), tag)
        tag.with_user(self.bob).write({"name": "Bills"})
        self.assertEqual(tag.name, "Bills")
        tag.with_user(self.bob).unlink()
        self.assertFalse(tag.exists())

    def test_a_user_without_the_group_has_no_right_on_the_tags(self):
        with self.assertRaises(AccessError):
            self.Tag.with_user(self.outsider).search([])

    # --- what only the administrators open --------------------------------------------------

    def test_the_lists_of_the_text_search_the_import_and_the_upload_folders_are_for_the_administrators(self):
        for model in (
            "int.filemanager.import",
            "int.filemanager.import.line",
            "int.filemanager.text",
            "int.filemanager.text.page",
            "int.filemanager.model.folder",
        ):
            self.env[model].with_user(self.boss).check_access("read")
            for user in (self.alice, self.outsider):
                with self.assertRaises(AccessError):
                    self.env[model].with_user(user).check_access("read")
