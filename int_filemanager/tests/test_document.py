import io
import os

from psycopg2 import IntegrityError

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import Form
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
        cls.top = cls.Folder.create({"name": "Top", "access_mode": "open"})
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

    def test_the_dialog_of_new_folder_has_the_name_and_the_parent(self):
        action = self.env.ref("int_filemanager.int_filemanager_folder_action_new")
        self.assertEqual((action.res_model, action.target, action.view_mode), (self.Folder._name, "new", "form"))
        arch = self.Folder.with_user(self.user).get_view(action.view_id.id, "form")["arch"]
        for name in ("name", "parent_id"):
            self.assertIn(f'name="{name}"', arch)

    def test_the_dialog_of_new_folder_puts_the_folder_of_the_panel_in_the_parent(self):
        # The list passes the folder of its panel as `default_parent_id` (`additionalContext`).
        view = self.env.ref("int_filemanager.int_filemanager_folder_view_form_dialog")
        folders = self.Folder.with_user(self.user)
        form = Form(folders.with_context(default_parent_id=self.top.id), view=view)
        self.assertEqual(form.parent_id, self.top)
        form.name = "From the dialog"
        self.assertEqual(form.save().parent_id, self.top)
        # No folder chosen in the panel: a folder of the top level, which every user may make.
        form = Form(folders, view=view)
        self.assertFalse(form.parent_id)
        form.name = "At the top"
        self.assertFalse(form.save().parent_id)
        # The name that is taken in that folder is refused (the unique index).
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"):
            form = Form(folders.with_context(default_parent_id=self.top.id), view=view)
            form.name = "FROM THE DIALOG"
            form.save()

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
        values = {"folder_id": self.sub.id, "checksum": "a" * 64}
        self.Document.create({**values, "name": "a.txt"})
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"):
            self.Document.create({**values, "name": "A.TXT"})
        self.assertTrue(self._document("a.txt", folder=self.top))

    # --- names ----------------------------------------------------------------

    def test_a_taken_name_gets_a_number(self):
        names = [self._document("a.txt", content=bytes([n])).name for n in range(3)]
        self.assertEqual(names, ["a.txt", "a (2).txt", "a (3).txt"])

    def test_the_number_comes_before_the_extension_and_case_does_not_matter(self):
        self._document("a.txt")
        self.assertEqual(self._document("A.TXT").name, "A (2).TXT")

    def test_a_number_that_is_taken_is_skipped(self):
        self._document("a (2).txt")
        self.assertEqual(
            [self._document("a.txt").name, self._document("a.txt").name],
            ["a.txt", "a (3).txt"],
        )

    def test_an_archived_document_gives_its_name_back(self):
        self._document("a.txt").active = False
        self.assertEqual(self._document("a.txt").name, "a.txt")

    def test_the_same_name_in_two_folders_stays(self):
        self._document("a.txt")
        self.assertEqual(self._document("a.txt", folder=self.top).name, "a.txt")

    def test_two_documents_with_the_same_content_share_one_blob(self):
        first, second = self._document("a.txt"), self._document("b.txt")
        self.assertEqual(first.checksum, second.checksum)
        blob_folder = os.path.dirname(self.Document._blob_path(first.checksum))
        self.assertEqual(os.listdir(blob_folder).count(first.checksum), 1)

    def test_a_name_is_cleaned(self):
        cases = {
            "C:\\fakepath\\x.txt": "x.txt",
            "dir/sub/y.txt": "y.txt",
            "a\u0308.txt": "\u00e4.txt",  # "a" plus a combining mark becomes one character
            "li\nne.txt": "line.txt",
            "  padded.txt  ": "padded.txt",
        }
        for given, expected in cases.items():
            with self.subTest(given=given):
                self.assertEqual(self.Document._clean_name(given), expected)

    def test_a_name_without_content_is_refused(self):
        for bad in ("", "  ", ".", "..", "dir/", None):
            with self.subTest(name=bad), self.assertRaises(UserError):
                self.Document._clean_name(bad)

    def test_a_long_name_keeps_its_extension(self):
        name = self.Document._clean_name("x" * 400 + ".pdf")
        self.assertEqual(len(name), 255)
        self.assertTrue(name.endswith("x.pdf"))

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

    def test_a_user_cannot_change_the_company_or_the_archive_date(self):
        document = self._document("a.txt", b"hello")
        other = self.env["res.company"].create({"name": "Other company"})
        before = (document.company_id, document.archived_date)
        document.with_user(self.user).write(
            {"company_id": other.id, "archived_date": fields.Datetime.now()}
        )
        self.assertEqual((document.company_id, document.archived_date), before)

    def test_the_storage_may_change_checksum_size_and_type(self):
        document = self._document("a.txt", b"hello")
        document.sudo().write({"size": 99, "mimetype": "text/x"})
        self.assertEqual((document.size, document.mimetype), (99, "text/x"))

    def test_a_user_sorts_and_filters_by_size(self):
        small, large = self._document("s.txt", b"x"), self._document("l.txt", b"x" * 10)
        found = self.Document.with_user(self.user).search(
            [("size", ">", 0)], order="size desc"
        )
        self.assertEqual(found[:2], large + small)

    def test_without_the_group_nothing_is_readable(self):
        with self.assertRaises(AccessError):
            self.Folder.with_user(self.outsider).search([])
        # The way over a linked record is a setting, off at first (test_link.py switches it on).
        self._document("hidden.txt")
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

    def test_the_download_action_points_to_the_route_of_the_content(self):
        document = self._document()
        action = document.with_user(self.user).action_download()
        self.assertEqual(action["type"], "ir.actions.act_url")
        self.assertEqual(action["target"], "download")
        self.assertEqual(
            action["url"],
            f"/web/content/int.filemanager.document/{document.id}/content?download=true",
        )
        # Several documents come as one ZIP (see test_document_zip), none is an error.
        both = document + self._document("b.txt")
        self.assertEqual(both.action_download()["url"], f"/int_filemanager/zip/{document.id},{both[1].id}")
        with self.assertRaises(UserError):
            self.Document.browse().action_download()

    def test_the_list_has_the_upload_and_the_buttons_for_the_ticked_rows(self):
        views = self.Document.with_user(self.user).get_views([(False, "list"), (False, "form")])
        arch = views["views"]["list"]["arch"]
        self.assertIn('js_class="int_filemanager_document_list"', arch)
        # The buttons are in the head of the list, none is in a row.
        head = arch[arch.index("<header>") : arch.index("</header>")]
        self.assertIn('name="action_download"', head)
        self.assertEqual(arch.count('name="action_download"'), 1)
        self.assertIn('widget="int_filemanager_document_name"', arch)
        self.assertIn('name="action_download"', views["views"]["form"]["arch"])

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
