import io
import os
import zipfile
from unittest.mock import patch

from odoo import Command, fields
from odoo.exceptions import UserError
from odoo.tests.common import HttpCase, new_test_user, tagged

from .test_folder_access import USER_GROUPS, remove

ROUTE = "/int_filemanager/folder_zip/"


@tagged("post_install", "-at_install")
class TestFolderZip(HttpCase):
    """A folder as one ZIP: the action that points to it, the route that sends it, who sees what."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Folder = cls.env["int.filemanager.folder"]
        cls.Document = cls.env["int.filemanager.document"]
        cls.user = new_test_user(cls.env, login="folder_zip_user", groups=USER_GROUPS)
        # club (open) > 2026 (like the parent) > invoices (like the parent)
        #            > empty
        cls.club = cls.Folder.create({"name": "Club", "access_mode": "open"})
        cls.year = cls.Folder.create({"name": "2026", "parent_id": cls.club.id})
        cls.invoices = cls.Folder.create({"name": "Invoices", "parent_id": cls.year.id})
        cls.empty = cls.Folder.create({"name": "Empty", "parent_id": cls.club.id})

    def setUp(self):
        super().setUp()
        self.authenticate("folder_zip_user", "folder_zip_user")

    def _document(self, folder, name="a.txt", content=b"hello"):
        document = self.Document._create_from_stream(io.BytesIO(content), name, folder)
        self.addCleanup(remove, self.Document._blob_path(document.checksum))
        return document

    def _zip(self, folder=None):
        response = self.url_open(f"{ROUTE}{(folder or self.club).id}")
        self.assertEqual(response.status_code, 200, response.text[:200])
        return response, zipfile.ZipFile(io.BytesIO(response.content))

    def _cookie(self, *company_ids):
        self.opener.cookies.set("cids", "-".join(str(i) for i in company_ids), domain="127.0.0.1", path="/")

    # --- the action ------------------------------------------------------------------------

    def test_the_action_points_to_the_route(self):
        action = self.club.with_user(self.user).action_download()
        self.assertEqual(
            (action["type"], action["target"], action["url"]),
            ("ir.actions.act_url", "download", f"{ROUTE}{self.club.id}"),
        )

    def test_the_action_works_for_one_folder_only(self):
        with self.assertRaises(ValueError):
            (self.club + self.year).with_user(self.user).action_download()

    def test_an_archived_folder_is_refused_with_its_name(self):
        self.year.action_archive()
        with self.assertRaisesRegex(UserError, "2026"):
            self.year.with_user(self.user).action_download()

    def test_more_bytes_than_the_parameter_allows_are_refused_before_the_tab_opens(self):
        self._document(self.invoices, "a.txt", b"x" * 100)
        self._document(self.year, "b.txt", b"y" * 100)
        # The setting counts in GB; the method gives the bytes, so the test makes them small.
        with patch.object(type(self.Document), "_zip_max_size", return_value=150):
            with self.assertRaisesRegex(UserError, "in parts"):
                self.club.with_user(self.user).action_download()
        # what the user does not see does not count
        with patch.object(type(self.Document), "_zip_max_size", return_value=250):
            self.club.with_user(self.user).action_download()

    def test_the_form_and_the_menu_have_the_button(self):
        view = self.env.ref("int_filemanager.int_filemanager_folder_view_form")
        self.assertIn('name="action_download"', view.arch_db)

    # --- the structure ---------------------------------------------------------------------

    def test_the_folder_is_the_top_and_the_structure_stays(self):
        self._document(self.club, "top.txt", b"top")
        self._document(self.invoices, "bill.pdf", b"%PDF")
        __, archive = self._zip()
        self.assertIsNone(archive.testzip())
        self.assertEqual(
            archive.namelist(),
            ["Club/2026/Invoices/bill.pdf", "Club/Empty/", "Club/top.txt"],
        )
        self.assertEqual(archive.read("Club/top.txt"), b"top")
        self.assertEqual(archive.read("Club/2026/Invoices/bill.pdf"), b"%PDF")

    def test_an_empty_folder_is_an_entry_of_its_own_and_only_an_empty_one(self):
        self._document(self.invoices, "bill.pdf")
        __, archive = self._zip()
        names = archive.namelist()
        self.assertIn("Club/Empty/", names)
        self.assertNotIn("Club/", names)
        self.assertNotIn("Club/2026/", names)
        info = archive.getinfo("Club/Empty/")
        self.assertEqual((info.file_size, info.external_attr >> 16), (0, 0o40755))

    def test_an_empty_top_folder_is_a_folder_in_the_archive(self):
        __, archive = self._zip(self.empty)
        self.assertEqual(archive.namelist(), ["Empty/"])

    def test_a_subfolder_alone_is_a_zip_of_itself(self):
        self._document(self.invoices, "bill.pdf")
        self._document(self.club, "top.txt")
        __, archive = self._zip(self.year)
        self.assertEqual(archive.namelist(), ["2026/Invoices/bill.pdf"])

    def test_a_file_with_the_name_of_a_folder_is_numbered_the_folder_keeps_its_name(self):
        self._document(self.club, "empty", b"file")
        self._document(self.club, "Year", b"other")
        self.Folder.create({"name": "year", "parent_id": self.club.id})
        __, archive = self._zip()
        names = archive.namelist()
        self.assertIn("Club/Empty/", names)
        self.assertIn("Club/empty (2)", names)
        self.assertIn("Club/year/", names)
        self.assertIn("Club/Year (2)", names)
        self.assertEqual(archive.read("Club/empty (2)"), b"file")

    def test_equal_files_of_a_folder_are_numbered_and_the_stored_names_stay(self):
        first = self._document(self.club, 're:port?.txt', b"one")
        second = self._document(self.club, "re_port_.txt", b"two")
        __, archive = self._zip()
        names = archive.namelist()
        self.assertIn("Club/re_port_.txt", names)
        self.assertIn("Club/re_port_ (2).txt", names)
        self.assertEqual((first.name, second.name), ("re:port?.txt", "re_port_.txt"))

    def test_the_names_of_folders_open_on_windows(self):
        weird = self.Folder.create({"name": 'a:b?', "parent_id": self.club.id})
        self._document(weird, "x.txt")
        __, archive = self._zip()
        self.assertIn("Club/a_b_/x.txt", archive.namelist())
        self.assertEqual(weird.name, "a:b?")

    def test_the_answer_tells_its_length_and_its_name(self):
        self._document(self.invoices)
        response, __ = self._zip()
        self.assertEqual(response.headers["Content-Type"], "application/zip")
        self.assertEqual(int(response.headers["Content-Length"]), len(response.content))
        today = fields.Date.context_today(self.Document)
        self.assertIn(f"Club-{today}.zip", response.headers["Content-Disposition"])
        self.assertIn("attachment", response.headers["Content-Disposition"])

    def test_archived_folders_and_documents_are_not_in_it(self):
        old = self.Folder.create({"name": "Old", "parent_id": self.club.id})
        self._document(old, "old.txt")
        gone = self._document(self.club, "gone.txt")
        self._document(self.club, "kept.txt")
        old.action_archive()
        gone.action_archive()
        __, archive = self._zip()
        names = archive.namelist()
        self.assertIn("Club/kept.txt", names)
        self.assertFalse([name for name in names if "Old" in name or "gone" in name])

    # --- the rights ------------------------------------------------------------------------

    def _hide_below(self):
        """secret (restricted) below the club; below it a folder that is open, and a document."""
        secret = self.Folder.create({"name": "Secret", "parent_id": self.club.id, "access_mode": "restricted"})
        opened = self.Folder.create({"name": "OpenBelow", "parent_id": secret.id, "access_mode": "open"})
        return secret, opened

    def test_a_hidden_folder_and_everything_below_it_is_left_out_and_never_named(self):
        secret, opened = self._hide_below()
        self._document(secret, "secret.txt", b"classified")
        self._document(opened, "below.txt", b"classified-too")
        self._document(self.club, "plain.txt", b"plain")
        response, archive = self._zip()
        # The user sees the folder below the hidden one, but not the way down to it.
        self.assertIn(opened, self.Folder.with_user(self.user).search([]))
        self.assertEqual(archive.namelist(), ["Club/2026/Invoices/", "Club/Empty/", "Club/plain.txt"])
        for hidden in (b"Secret", b"OpenBelow", b"secret.txt", b"below.txt", b"classified"):
            self.assertNotIn(hidden, response.content)

    def test_an_invitation_shows_the_hidden_folder(self):
        secret, __ = self._hide_below()
        self._document(secret, "secret.txt", b"classified")
        secret.access_user_ids = self.user
        __, archive = self._zip()
        self.assertIn("Club/Secret/secret.txt", archive.namelist())

    def test_a_folder_the_user_may_not_see_is_refused(self):
        secret, __ = self._hide_below()
        self.assertEqual(self.url_open(f"{ROUTE}{secret.id}").status_code, 403)

    def test_a_folder_that_does_not_exist_is_not_found(self):
        self.assertEqual(self.url_open(f"{ROUTE}{self.club.id + 100000}").status_code, 404)

    def test_an_address_that_is_no_id_is_not_found(self):
        self.assertEqual(self.url_open(f"{ROUTE}abc").status_code, 404)

    def test_an_archived_folder_answers_with_the_reason_and_no_zip(self):
        self.year.action_archive()
        response = self.url_open(f"{ROUTE}{self.year.id}")
        self.assertEqual(response.status_code, 409)
        self.assertIn("2026", response.text)

    def test_a_broken_cookie_is_a_bad_request(self):
        self.opener.cookies.set("cids", "x-y", domain="127.0.0.1", path="/")
        self.assertEqual(self.url_open(f"{ROUTE}{self.club.id}").status_code, 400)

    def test_a_company_the_user_may_not_use_is_refused(self):
        other = self.env["res.company"].create({"name": "Not mine"})
        self._cookie(other.id)
        self.assertEqual(self.url_open(f"{ROUTE}{self.club.id}").status_code, 403)

    def test_the_company_of_the_list_decides_what_is_read(self):
        other = self.env["res.company"].create({"name": "Second"})
        self.user.write({"company_ids": [Command.link(other.id)]})
        theirs = self.Folder.create({"name": "Theirs", "access_mode": "open", "company_id": other.id})
        self._document(theirs, "theirs.txt")
        self._cookie(self.user.company_id.id)
        self.assertEqual(self.url_open(f"{ROUTE}{theirs.id}").status_code, 403)
        self._cookie(self.user.company_id.id, other.id)
        self.assertEqual(self.url_open(f"{ROUTE}{theirs.id}").status_code, 200)

    def test_without_the_right_to_the_filemanager_nothing_is_delivered(self):
        new_test_user(self.env, login="folder_zip_outsider", groups="base.group_user")
        self.authenticate("folder_zip_outsider", "folder_zip_outsider")
        self.assertEqual(self.url_open(f"{ROUTE}{self.club.id}").status_code, 403)

    def test_a_visitor_who_is_not_logged_in_is_sent_to_the_login(self):
        self.opener.cookies.clear()
        response = self.url_open(f"{ROUTE}{self.club.id}", allow_redirects=False)
        self.assertIn(response.status_code, (302, 303))
        self.assertIn("login", response.headers["Location"])

    # --- what goes wrong -------------------------------------------------------------------

    def test_a_file_that_is_missing_answers_with_its_name_and_no_zip(self):
        document = self._document(self.invoices, "gone.txt", b"other")
        os.unlink(document._blob_path(document.checksum))
        response = self.url_open(f"{ROUTE}{self.club.id}")
        self.assertEqual(response.status_code, 409)
        self.assertIn("gone.txt", response.text)

    def test_more_bytes_than_the_parameter_allows_answer_without_a_zip(self):
        self._document(self.invoices, "a.txt", b"x" * 100)
        self._document(self.club, "b.txt", b"y" * 100)
        with patch.object(type(self.Document), "_zip_max_size", return_value=150):
            response = self.url_open(f"{ROUTE}{self.club.id}")
        self.assertEqual(response.status_code, 409)
        self.assertIn("in parts", response.text)

    def test_a_document_without_a_stored_size_is_measured_on_the_file(self):
        document = self._document(self.invoices, "old.txt", b"twelve bytes")
        document.write({"size": 0})
        response, archive = self._zip()
        self.assertEqual(archive.read("Club/2026/Invoices/old.txt"), b"twelve bytes")
        self.assertEqual(int(response.headers["Content-Length"]), len(response.content))

    def test_a_deep_tree_comes_whole(self):
        folder = self.club
        for level in range(30):
            folder = self.Folder.create({"name": f"level {level}", "parent_id": folder.id})
        self._document(folder, "bottom.txt", b"deep")
        __, archive = self._zip()
        path = "/".join(["Club", *(f"level {level}" for level in range(30)), "bottom.txt"])
        self.assertEqual(archive.read(path), b"deep")
