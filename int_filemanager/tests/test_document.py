import base64

from psycopg2 import IntegrityError

from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase, new_test_user, tagged
from odoo.tools import mute_logger


@tagged("post_install", "-at_install")
class TestFolderAndDocument(TransactionCase):
    """Folders and documents are ordinary records: no own methods, Odoo's own storage."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Folder = cls.env["int_filemanager.folder"]
        cls.Document = cls.env["int_filemanager.document"]
        cls.user = new_test_user(
            cls.env,
            login="doc_user",
            groups="base.group_user,int_filemanager.group_filemanager_user",
        )
        cls.outsider = new_test_user(cls.env, login="doc_outsider", groups="base.group_user")
        cls.top = cls.Folder.create({"name": "Top"})
        cls.sub = cls.Folder.create({"name": "Sub", "parent_id": cls.top.id})

    def _document(self, name="a.txt", content=b"hello", folder=None):
        return self.Document.create(
            {
                "name": name,
                "folder_id": (folder or self.sub).id,
                "data": base64.b64encode(content),
            }
        )

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

    def test_the_content_lives_in_an_odoo_attachment(self):
        document = self._document("report.pdf", b"%PDF-1.4 content")
        attachment = self.env["ir.attachment"].search(
            [
                ("res_model", "=", "int_filemanager.document"),
                ("res_field", "=", "data"),
                ("res_id", "=", document.id),
            ]
        )
        self.assertEqual(len(attachment), 1)
        self.assertEqual(attachment.raw, b"%PDF-1.4 content")
        self.assertEqual(base64.b64decode(document.data), b"%PDF-1.4 content")

    def test_size_and_mimetype_follow_the_content_and_the_name(self):
        document = self._document("report.pdf", b"x" * 1500)
        self.assertEqual(document.size, 1500)
        self.assertEqual(document.mimetype, "application/pdf")
        document.write({"data": base64.b64encode(b"y" * 10), "name": "notes.txt"})
        self.assertEqual(document.size, 10)
        self.assertEqual(document.mimetype, "text/plain")

    def test_an_unknown_extension_is_a_binary_file(self):
        self.assertEqual(self._document("blob.zzz").mimetype, "application/octet-stream")

    def test_a_document_needs_a_folder(self):
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"):
            self.Document.create({"name": "x", "data": base64.b64encode(b"x")})

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
        document = self.Document.with_user(self.user).create(
            {
                "name": "mine.txt",
                "folder_id": folder.id,
                "data": base64.b64encode(b"mine"),
            }
        )
        document.write({"name": "mine2.txt"})
        document.unlink()
        folder.unlink()

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
        tag = self.env["int_filemanager.tag"].create({"name": "Invoice"})
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

    # --- moving and copying ---------------------------------------------------

    def test_a_copy_keeps_the_content_the_tags_and_gets_a_free_name(self):
        tag = self.env["int_filemanager.tag"].create({"name": "Copied"})
        original = self._document("report.pdf", b"content")
        original.tag_ids = tag
        copy = original.copy()
        self.assertEqual(copy.name, "report (copy).pdf")
        self.assertEqual(copy.folder_id, original.folder_id)
        self.assertEqual(copy.tag_ids, tag)
        self.assertEqual(copy.size, original.size)
        self.assertEqual(base64.b64decode(copy.data), b"content")
        self.assertEqual(copy.mimetype, "application/pdf")

    def test_copying_again_counts_up_and_a_given_name_is_kept(self):
        original = self._document("a.txt")
        first, second = original.copy(), original.copy()
        self.assertEqual((first.name, second.name), ("a (copy).txt", "a (copy 2).txt"))
        self.assertEqual(original.copy({"name": "chosen.txt"}).name, "chosen.txt")

    def test_a_copy_of_several_documents(self):
        both = self._document("a.txt") + self._document("b.txt")
        self.assertEqual(
            sorted(both.copy().mapped("name")), ["a (copy).txt", "b (copy).txt"]
        )

    def test_the_lists_move_by_multi_edit_and_folders_cannot_be_duplicated(self):
        views = self.Document.get_views([(False, "list")])
        self.assertIn('multi_edit="1"', views["views"]["list"]["arch"])
        views = self.Folder.get_views([(False, "list"), (False, "form")])
        for view_type in ("list", "form"):
            self.assertIn('duplicate="0"', views["views"][view_type]["arch"])
