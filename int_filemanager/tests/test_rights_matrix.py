import io
import os

from odoo import Command, http
from odoo.exceptions import AccessError
from odoo.tests.common import HttpCase, TransactionCase, new_test_user, tagged

from .test_folder_access import AccessCase, remove

READER_GROUPS = "base.group_user,int_filemanager.int_filemanager_group_reader"


@tagged("post_install", "-at_install")
class TestRightsMatrix(AccessCase, TransactionCase):
    """What the groups may do with what they see: read, change, delete, create.

    The reader sees what the user sees and only reads; the user changes it; the administrator
    also says who sees a folder.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._set_up_access()
        cls.Tag = cls.env["int.filemanager.tag"]
        cls.reader = new_test_user(cls.env, login="access_reader", groups=READER_GROUPS)

    def setUp(self):
        super().setUp()
        self.document = self._document(self.shared, "a.txt", b"hello")

    # --- folders ----------------------------------------------------------------------------

    def test_a_folder_user_reads_changes_and_deletes_what_the_user_sees(self):
        as_alice = self.shared.with_user(self.alice)
        self.assertEqual(as_alice.name, "Shared")
        as_alice.write({"name": "Renamed"})
        self.assertEqual(self.shared.name, "Renamed")
        mine = self.Folder.create({"name": "Mine", "access_mode": "open"})
        mine.with_user(self.alice).unlink()
        self.assertFalse(mine.exists())

    def test_a_reader_sees_what_a_user_sees_and_only_reads(self):
        self.assertEqual(self._seen_by(self.reader), self._seen_by(self.alice))
        self._invite(self.secret, self.reader)
        self.assertEqual(self._seen_by(self.reader), self._seen_by(self.alice) + self.secret + self.inner)
        as_reader = self.shared.with_user(self.reader)
        self.assertEqual(as_reader.name, "Shared")
        for operation in ("write", "unlink", "create"):
            with self.assertRaises(AccessError):
                as_reader.check_access(operation)
        with self.assertRaises(AccessError):
            as_reader.write({"name": "Renamed"})
        with self.assertRaises(AccessError):
            self.Folder.with_user(self.reader).create({"name": "Mine", "parent_id": self.shared.id})

    def test_the_groups_imply_each_other_from_the_administrator_down_to_the_reader(self):
        reader = self.env.ref("int_filemanager.int_filemanager_group_reader")
        user = self.env.ref("int_filemanager.int_filemanager_group_user")
        admin = self.env.ref("int_filemanager.int_filemanager_group_admin")
        self.assertEqual(user.implied_ids, reader)
        self.assertEqual(admin.implied_ids, user)
        self.assertLessEqual(reader + user, self.alice.all_group_ids)
        self.assertLessEqual(reader + user + admin, self.boss.all_group_ids)
        self.assertNotIn(user, self.reader.all_group_ids)

    def test_a_folder_user_makes_a_top_folder(self):
        folder = self.Folder.with_user(self.alice).create({"name": "Mine"})
        self.assertEqual(folder.create_uid, self.alice)

    def test_a_listed_user_changes_and_deletes_the_folder_too(self):
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

    # --- the lists of who may see: for the administrators -----------------------------------

    def test_a_folder_user_neither_reads_nor_changes_who_may_see_the_folder(self):
        self.secret.access_user_ids = self.alice
        as_alice = self.secret.with_user(self.alice)
        for name in ("access_mode", "access_user_ids", "access_group_ids"):
            with self.assertRaises(AccessError):
                as_alice[name]  # noqa: B018
            with self.assertRaises(AccessError):
                as_alice.write({name: False})
        self.assertNotIn(self.secret, self._seen_by(self.bob))

    def test_the_administrators_read_and_change_who_may_see_the_folder(self):
        as_boss = self.secret.with_user(self.boss)
        as_boss.write(
            {
                "access_mode": "restricted",
                "access_user_ids": [Command.link(self.bob.id)],
                "access_group_ids": [Command.link(self.env.ref("base.group_user").id)],
            }
        )
        self.assertEqual(as_boss.access_user_ids, self.bob)
        self.assertIn(self.secret, self._seen_by(self.bob))

    def test_a_folder_made_by_a_user_has_the_default_access(self):
        folder = self.Folder.with_user(self.alice).create({"name": "Mine"})
        self.assertEqual(folder.sudo().access_mode, "inherit")
        sub = self.Folder.with_user(self.alice).create({"name": "Sub", "parent_id": folder.id})
        self.assertEqual(sub.access_folder_id, folder)

    def test_a_reader_may_not_invite_others(self):
        self._invite(self.secret, self.reader)
        with self.assertRaises(AccessError):
            self.secret.with_user(self.reader).message_subscribe(partner_ids=[self.bob.partner_id.id])
        self.assertNotIn(self.secret, self._seen_by(self.bob))

    def test_a_listed_user_does_not_invite_others(self):
        self._invite(self.secret, self.alice)
        self.secret.with_user(self.alice).message_subscribe(partner_ids=[self.bob.partner_id.id])
        self.assertNotIn(self.secret, self._seen_by(self.bob))

    # --- documents --------------------------------------------------------------------------

    def test_a_folder_user_reads_changes_and_deletes_the_documents_of_what_the_user_sees(self):
        as_alice = self.document.with_user(self.alice)
        self.assertEqual(as_alice.name, "a.txt")
        as_alice.write({"name": "b.txt"})
        self.assertEqual(self.document.name, "b.txt")
        as_alice.unlink()
        self.assertFalse(self.document.exists())

    def test_a_reader_reads_the_documents_and_changes_nothing(self):
        as_reader = self.document.with_user(self.reader)
        self.assertEqual(as_reader.name, "a.txt")
        for operation in ("write", "unlink", "create"):
            with self.assertRaises(AccessError):
                as_reader.check_access(operation)
        with self.assertRaises(AccessError):
            as_reader.write({"name": "b.txt"})
        hidden = self._document(self.inner, "hidden.txt")
        with self.assertRaises(AccessError):
            hidden.with_user(self.reader).check_access("read")

    def test_a_document_is_made_by_the_upload_not_by_the_orm(self):
        values = {"name": "c.txt", "folder_id": self.shared.id}
        with self.assertRaises(AccessError):
            self.Document.with_user(self.alice).create(values)
        with self.assertRaises(AccessError):
            self.Document.with_user(self.boss).create(values)

    def test_the_storage_refuses_a_user_who_may_not_write_into_the_folder_before_it_stores(self):
        before = self.Document.search_count([])
        upload_dir = self.Document._upload_dir()
        stored = set(os.listdir(upload_dir)) if os.path.isdir(upload_dir) else set()
        # a reader, a user who does not see the folder, and one without the group
        for user, folder in ((self.reader, self.shared), (self.alice, self.inner), (self.outsider, self.shared)):
            with self.subTest(user=user.login, folder=folder.name), self.assertRaises(AccessError):
                self.Document.with_user(user)._create_from_stream(
                    io.BytesIO(b"x"), "x.txt", folder.with_user(user)
                )
        self.assertEqual(self.Document.search_count([]), before)
        self.assertEqual(set(os.listdir(upload_dir)) if os.path.isdir(upload_dir) else set(), stored)

    def test_the_storage_takes_the_user_who_may_write_and_the_folder_handed_over_as_superuser(self):
        mine = self.Document.with_user(self.alice)._create_from_stream(
            io.BytesIO(b"mine"), "mine.txt", self.shared.with_user(self.alice)
        )
        # an upload at a record, a share and the import check another right and hand the folder over
        handed = self.Document.with_user(self.alice)._create_from_stream(
            io.BytesIO(b"handed"), "handed.txt", self.inner.sudo()
        )
        for document in (mine, handed):
            self.addCleanup(remove, self.Document._blob_path(document.checksum))
        self.assertEqual((mine.folder_id, handed.folder_id), (self.shared, self.inner))

    def test_a_user_who_does_not_see_the_folder_has_no_right_on_its_documents(self):
        hidden = self._document(self.inner, "hidden.txt")
        as_bob = hidden.with_user(self.bob)
        for operation in ("read", "write", "unlink"):
            with self.assertRaises(AccessError):
                as_bob.check_access(operation)

    def test_a_user_without_the_group_has_no_right_on_the_documents(self):
        as_outsider = self.document.with_user(self.outsider)
        for operation in ("read", "write", "unlink"):
            with self.assertRaises(AccessError):
                as_outsider.check_access(operation)

    def test_the_administrators_do_everything_with_every_document(self):
        hidden = self._document(self.inner, "hidden.txt")
        as_boss = hidden.with_user(self.boss)
        for operation in ("read", "write", "unlink"):
            as_boss.check_access(operation)

    def test_the_documents_that_the_folders_show_are_those_that_the_rules_show(self):
        hidden = self._document(self.inner, "hidden.txt")
        both = (self.document + hidden).with_user(self.alice)
        self.assertEqual(both._filtered_folder_access("read"), self.document.with_user(self.alice))
        self.assertEqual(both._filtered_folder_access("read"), both._filtered_access("read"))
        self._invite(self.secret, self.alice)
        self.assertEqual(both._filtered_folder_access("read"), both)

    def test_nothing_refers_to_a_document_in_the_core(self):
        self.assertFalse(self.document._documents_referenced())

    # --- tags -------------------------------------------------------------------------------

    def test_a_reader_reads_the_tags_and_changes_none(self):
        tag = self.Tag.create({"name": "Invoices"})
        self.assertEqual(self.Tag.with_user(self.reader).search([("name", "=", "Invoices")]), tag)
        with self.assertRaises(AccessError):
            tag.with_user(self.reader).write({"name": "Bills"})
        with self.assertRaises(AccessError):
            self.Tag.with_user(self.reader).create({"name": "New"})

    def test_the_tags_are_for_every_folder_user_to_make_change_and_delete(self):
        # global, not tied to a folder
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

    def test_the_list_of_the_upload_folders_is_for_the_administrators(self):
        for model in (
            "int.filemanager.model.folder",
        ):
            self.env[model].with_user(self.boss).check_access("read")
            for user in (self.reader, self.alice, self.outsider):
                with self.assertRaises(AccessError):
                    self.env[model].with_user(user).check_access("read")

    # --- moves are the user's ---------------------------------------------------------------

    def test_a_reader_moves_nothing(self):
        with self.assertRaises(AccessError):
            self.env["int.filemanager.move"].with_user(self.reader).check_access("create")
        self.env["int.filemanager.move"].with_user(self.alice).check_access("create")

    # --- what the screens offer -------------------------------------------------------------

    def test_the_screens_of_a_reader_are_for_reading(self):
        for model, view_type in (
            ("int.filemanager.document", "list"),
            ("int.filemanager.document", "form"),
            ("int.filemanager.folder", "list"),
            ("int.filemanager.folder", "form"),
        ):
            with self.subTest(model=model, view_type=view_type):
                as_reader = self.env[model].with_user(self.reader)
                arch = as_reader.get_views([(False, view_type)])["views"][view_type]["arch"]
                self.assertIn('edit="False"', arch)
                self.assertNotIn("Move to", arch)
                as_alice = self.env[model].with_user(self.alice)
                arch = as_alice.get_views([(False, view_type)])["views"][view_type]["arch"]
                self.assertNotIn('edit="False"', arch)

    def test_the_fields_of_who_sees_are_on_the_screens_of_the_administrators_only(self):
        for user, shown in ((self.alice, False), (self.boss, True)):
            views = self.Folder.with_user(user).get_views([(False, "list"), (False, "form")])["views"]
            for view_type in ("list", "form"):
                self.assertEqual('name="access_mode"' in views[view_type]["arch"], shown)

    def test_the_menu_is_for_the_readers_and_up(self):
        menu = self.env.ref("int_filemanager.menu_int_filemanager_root")
        self.assertEqual(menu.group_ids, self.env.ref("int_filemanager.int_filemanager_group_reader"))


@tagged("post_install", "-at_install")
class TestRightsMatrixOverHttp(AccessCase, HttpCase):
    """The reader downloads and does not upload."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._set_up_access()
        cls.reader = new_test_user(cls.env, login="access_reader", groups=READER_GROUPS)

    def test_a_reader_downloads_and_cannot_upload(self):
        document = self._document(self.deep, "shown.txt")
        self.authenticate("access_reader", "access_reader")
        response = self.url_open(f"/web/content/int.filemanager.document/{document.id}/content?download=true")
        self.assertEqual(response.status_code, 200)
        data = {"csrf_token": http.Request.csrf_token(self), "folder_id": self.deep.id}
        files = {"ufile": ("a.txt", io.BytesIO(b"x"))}
        self.assertEqual(self.url_open("/int_filemanager/upload", data=data, files=files).status_code, 403)
