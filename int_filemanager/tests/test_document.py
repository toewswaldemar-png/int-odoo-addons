import io
import os

from psycopg2 import IntegrityError

from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase, new_test_user, tagged
from odoo.tools import mute_logger


@tagged("post_install", "-at_install")
class TestFolderAndDocument(TransactionCase):
    """Folders and documents are ordinary records; a document's file lies in a blob."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Folder = cls.env["int.filemanager.folder"]
        cls.Document = cls.env["int.filemanager.document"]
        cls.user = new_test_user(
            cls.env,
            login="doc_user",
            groups="base.group_user,int_filemanager.int_filemanager_group_user",
        )
        cls.outsider = new_test_user(cls.env, login="doc_outsider", groups="base.group_user")
        cls.top = cls.Folder.create({"name": "Top"})
        cls.sub = cls.Folder.create({"name": "Sub", "parent_id": cls.top.id})

    def _document(self, name="a.txt", content=b"hello", folder=None):
        document = self.Document._create_from_stream(
            io.BytesIO(content), name, folder or self.sub
        )
        self.addCleanup(self._remove_blob, document.checksum)
        return document

    def _remove_blob(self, checksum):
        path = self.Document._blob_path(checksum)
        if os.path.exists(path):
            os.unlink(path)

    # --- folders --------------------------------------------------------------

    def test_a_folder_below_a_folder_is_found_with_child_of(self):
        deep = self.Folder.create({"name": "Deep", "parent_id": self.sub.id})
        found = self.Folder.search([("id", "child_of", self.top.id)])
        self.assertEqual(found, self.top + self.sub + deep)
        self.assertEqual(deep.parent_path.split("/")[:-1], [str(i) for i in (self.top.id, self.sub.id, deep.id)])

    def test_a_name_is_unique_per_folder_without_regard_to_case(self):
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"):
            self.Folder.create({"name": "SUB", "parent_id": self.top.id})

    def test_two_top_folders_cannot_share_a_name(self):
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"):
            self.Folder.create({"name": "top"})

    def test_the_same_name_may_exist_in_different_folders(self):
        other = self.Folder.create({"name": "Other"})
        self.assertTrue(self.Folder.create({"name": "Sub", "parent_id": other.id}))

    def test_an_archived_folder_gives_its_name_back(self):
        self.sub.active = False
        self.env.flush_all()
        self.assertTrue(self.Folder.create({"name": "Sub", "parent_id": self.top.id}))

    def test_a_folder_cannot_be_moved_below_itself(self):
        # Odoo's own check of a stored parent ("Recursion Detected.").
        with self.assertRaises(UserError):
            self.top.parent_id = self.sub

    def test_a_folder_with_content_cannot_be_deleted(self):
        with self.assertRaises(UserError):
            self.top.unlink()
        self._document()
        with self.assertRaises(UserError):
            self.sub.unlink()

    def test_an_archived_document_still_keeps_its_folder(self):
        self._document().active = False
        with self.assertRaises(UserError):
            self.sub.unlink()

    def test_an_empty_folder_can_be_deleted(self):
        empty = self.Folder.create({"name": "Empty", "parent_id": self.top.id})
        empty.unlink()
        self.assertFalse(empty.exists())

    # --- documents ------------------------------------------------------------

    def test_the_content_lies_in_a_blob_and_not_in_an_attachment(self):
        document = self._document("report.pdf", b"%PDF-1.4 content")
        with open(self.Document._blob_path(document.checksum), "rb") as blob:
            self.assertEqual(blob.read(), b"%PDF-1.4 content")
        self.assertFalse(
            self.env["ir.attachment"].search(
                [("res_model", "=", "int.filemanager.document"), ("res_id", "=", document.id)]
            )
        )

    def test_size_and_type_are_set_by_the_storage_and_stay_when_the_name_changes(self):
        document = self._document("report.pdf", b"x" * 1500)
        self.assertEqual(document.size, 1500)
        self.assertEqual(document.mimetype, "application/pdf")
        document.name = "notes.txt"
        self.assertEqual(document.mimetype, "application/pdf")

    def test_an_unknown_extension_is_judged_by_the_content(self):
        self.assertEqual(self._document("blob.zzz", b"\x00\x01\x02").mimetype, "application/octet-stream")
        self.assertEqual(self._document("notes.zzz", b"plain words").mimetype, "text/plain")

    def test_a_document_needs_a_folder(self):
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"):
            self.Document.create({"name": "x", "checksum": "a" * 64})

    def test_a_checksum_is_a_sha256(self):
        for bad in ("abc", "A" * 64, "g" * 64, "a" * 63):
            with self.subTest(checksum=bad), self.assertRaises(IntegrityError), mute_logger(
                "odoo.sql_db"
            ):
                self.Document.create(
                    {"name": "x", "folder_id": self.sub.id, "checksum": bad}
                )

    def test_a_document_name_is_unique_per_folder_without_regard_to_case(self):
        self._document("a.txt")
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"):
            self._document("A.TXT")
        self.assertTrue(self._document("a.txt", folder=self.top))

    def test_moving_a_document_is_a_write(self):
        document = self._document()
        document.folder_id = self.top
        self.assertEqual(document.folder_id, self.top)
        self.assertEqual(document.company_id, self.top.company_id)

    # --- rights ---------------------------------------------------------------

    def test_a_filemanager_user_works_with_folders_and_documents(self):
        folder = self.Folder.with_user(self.user).create({"name": "Mine"})
        document = self.Document.with_user(self.user)._create_from_stream(
            io.BytesIO(b"mine"), "mine.txt", folder
        )
        self.addCleanup(self._remove_blob, document.checksum)
        document.write({"name": "mine2.txt"})
        document.unlink()
        folder.unlink()

    def test_a_user_cannot_create_a_document_directly(self):
        with self.assertRaises(AccessError):
            self.Document.with_user(self.user).create(
                {"name": "x", "folder_id": self.sub.id, "checksum": "a" * 64}
            )

    def test_a_user_cannot_change_checksum_size_or_type(self):
        document = self._document("a.txt", b"hello")
        before = (document.checksum, document.size, document.mimetype)
        document.with_user(self.user).write(
            {"name": "b.txt", "checksum": "b" * 64, "size": 99, "mimetype": "evil/type"}
        )
        self.assertEqual(document.name, "b.txt")
        self.assertEqual((document.checksum, document.size, document.mimetype), before)

    def test_the_storage_may_change_checksum_size_and_type(self):
        document = self._document("a.txt", b"hello")
        document.sudo().write({"size": 99, "mimetype": "text/x"})
        self.assertEqual((document.size, document.mimetype), (99, "text/x"))

    def test_the_origin_path_is_for_administrators_only(self):
        document = self._document()
        document.sudo().origin_path = "/mnt/data/a.txt"
        as_user = document.with_user(self.user)
        with self.assertRaises(AccessError):
            as_user.origin_path  # noqa: B018
        self.assertNotIn("origin_path", self.Document.with_user(self.user).fields_get())
        self.assertEqual(document.sudo().origin_path, "/mnt/data/a.txt")

    def test_a_user_sorts_and_filters_by_size(self):
        small, large = self._document("s.txt", b"x"), self._document("l.txt", b"x" * 10)
        found = self.Document.with_user(self.user).search(
            [("size", ">", 0)], order="size desc"
        )
        self.assertEqual(found[:2], large + small)

    def test_without_the_group_nothing_is_readable(self):
        with self.assertRaises(AccessError):
            self.Folder.with_user(self.outsider).search([])
        with self.assertRaises(AccessError):
            self.Document.with_user(self.outsider).search([])

    def test_a_folder_of_another_company_is_not_visible(self):
        other = self.env["res.company"].create({"name": "Other company"})
        foreign = self.Folder.create({"name": "Foreign", "company_id": other.id})
        document = self._document("foreign.txt", folder=foreign)
        self.assertNotIn(foreign, self.Folder.with_user(self.user).search([]))
        self.assertNotIn(document, self.Document.with_user(self.user).search([]))
        self.assertIn(foreign, self.Folder.search([]))

    # --- search panel ---------------------------------------------------------

    def test_the_search_panel_offers_the_folder_tree(self):
        result = self.Document.with_user(self.user).search_panel_select_range(
            "folder_id", expand=True, limit=0
        )
        self.assertEqual(result["parent_field"], "parent_id")
        parents = {v["display_name"]: v["parent_id"] for v in result["values"]}
        self.assertEqual(parents["Sub"], self.top.id)
        self.assertFalse(parents["Top"])

    def test_the_search_panel_offers_the_tags(self):
        tag = self.env["int.filemanager.tag"].create({"name": "Invoice"})
        self._document().tag_ids = tag
        result = self.Document.with_user(self.user).search_panel_select_multi_range(
            "tag_ids", expand=True
        )
        self.assertIn("Invoice", [v["display_name"] for v in result["values"]])

    def test_choosing_a_folder_in_the_panel_finds_its_documents_and_those_below(self):
        deep = self.Folder.create({"name": "Deep", "parent_id": self.sub.id})
        here, below, elsewhere = (
            self._document("a.txt", folder=self.sub),
            self._document("b.txt", folder=deep),
            self._document("c.txt", folder=self.top),
        )
        found = self.Document.search([("folder_id", "child_of", self.sub.id)])
        self.assertEqual(found, here + below)
        self.assertNotIn(elsewhere, found)

    # --- moving and listing --------------------------------------------------

    def test_the_lists_move_by_multi_edit_and_nothing_is_duplicated_or_created_by_hand(self):
        views = self.Document.get_views([(False, "list"), (False, "form")])
        self.assertIn('multi_edit="1"', views["views"]["list"]["arch"])
        for view_type in ("list", "form"):
            arch = views["views"][view_type]["arch"]
            self.assertIn('duplicate="0"', arch)
            self.assertIn('create="0"', arch)
        self.assertIn('import="0"', views["views"]["list"]["arch"])
        views = self.Folder.get_views([(False, "list"), (False, "form")])
        for view_type in ("list", "form"):
            self.assertIn('duplicate="0"', views["views"][view_type]["arch"])
