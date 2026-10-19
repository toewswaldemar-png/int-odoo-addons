import io
import os
import zipfile
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests.common import HttpCase, new_test_user, tagged

from ..models.int_filemanager_document import ZIP_MAX_SIZE_PARAMETER
from .test_document_download import DownloadCase

ROUTE = "/int_filemanager/zip/"


@tagged("post_install", "-at_install")
class TestDocumentZip(DownloadCase, HttpCase):
    """Several documents as one ZIP: the action that points to it, the route that sends it."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Folder = cls.env["int.filemanager.folder"]
        cls.Document = cls.env["int.filemanager.document"]
        cls.folder = Folder.create({"name": "Zips", "access_mode": "open"})
        cls.beside = Folder.create({"name": "Beside", "access_mode": "open"})
        cls.secret = Folder.create({"name": "Secret", "access_mode": "restricted"})
        cls.user = new_test_user(
            cls.env,
            login="zip_user",
            groups="base.group_user,int_filemanager.int_filemanager_group_user",
        )

    def setUp(self):
        super().setUp()
        self.authenticate("zip_user", "zip_user")

    def _url_of(self, *documents):
        return ROUTE + ",".join(str(document.id) for document in documents)

    def _zip(self, *documents):
        response = self.url_open(self._url_of(*documents))
        self.assertEqual(response.status_code, 200, response.text[:200])
        return response, zipfile.ZipFile(io.BytesIO(response.content))

    # --- the action ------------------------------------------------------------------------

    def test_one_document_is_still_the_download_of_the_core(self):
        document = self._document()
        action = document.with_user(self.user).action_download()
        self.assertEqual(action["url"], f"/web/content/int.filemanager.document/{document.id}/content?download=true")

    def test_several_documents_point_to_the_zip_route(self):
        first, second = self._document("a.txt"), self._document("b.txt", b"other")
        action = (first + second).with_user(self.user).action_download()
        self.assertEqual(
            (action["type"], action["target"], action["url"]),
            ("ir.actions.act_url", "download", f"{ROUTE}{first.id},{second.id}"),
        )

    def test_no_document_is_an_error(self):
        with self.assertRaises(UserError):
            self.Document.browse().action_download()

    def test_too_many_documents_for_the_address_are_refused_with_a_hint(self):
        documents = self._document("a.txt") + self._document("b.txt", b"other")
        with patch("odoo.addons.int_filemanager.models.int_filemanager_document.ZIP_PATH_MAX_LENGTH", 10):
            with self.assertRaisesRegex(UserError, "Select fewer"):
                documents.action_download()

    def test_a_missing_file_is_refused_with_its_name_before_the_tab_opens(self):
        first, second = self._document("a.txt"), self._document("gone.txt", b"other")
        os.unlink(second._blob_path(second.checksum))
        with self.assertRaisesRegex(UserError, "gone.txt"):
            (first + second).action_download()

    def test_more_bytes_than_the_parameter_allows_are_refused(self):
        documents = self._document("a.txt", b"x" * 100) + self._document("b.txt", b"y" * 100)
        self.env["ir.config_parameter"].set_param(ZIP_MAX_SIZE_PARAMETER, "150")
        with self.assertRaisesRegex(UserError, "in parts"):
            documents.action_download()
        self.env["ir.config_parameter"].set_param(ZIP_MAX_SIZE_PARAMETER, "200")
        documents.action_download()

    # --- the route -------------------------------------------------------------------------

    def test_the_zip_holds_the_files_flat_and_whole(self):
        first = self._document("a.txt", b"first")
        second = self._document("b.bin", bytes(range(200)), self.beside)
        __, archive = self._zip(first, second)
        self.assertIsNone(archive.testzip())
        self.assertEqual(archive.namelist(), ["a.txt", "b.bin"])
        self.assertEqual(archive.read("a.txt"), b"first")
        self.assertEqual(archive.read("b.bin"), bytes(range(200)))

    def test_the_answer_tells_its_length_and_its_name(self):
        response, __ = self._zip(self._document("a.txt"), self._document("b.txt", b"other"))
        self.assertEqual(response.headers["Content-Type"], "application/zip")
        self.assertEqual(int(response.headers["Content-Length"]), len(response.content))
        today = fields.Date.context_today(self.Document)
        self.assertIn(f"documents-{today}.zip", response.headers["Content-Disposition"])
        self.assertIn("attachment", response.headers["Content-Disposition"])
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")

    def test_equal_names_from_different_folders_are_numbered(self):
        first = self._document("same.txt", b"one")
        second = self._document("same.txt", b"two", self.beside)
        __, archive = self._zip(second, first)
        self.assertEqual(archive.namelist(), ["same.txt", "same (2).txt"])
        self.assertEqual(archive.read("same.txt"), b"one")
        self.assertEqual(archive.read("same (2).txt"), b"two")

    def test_the_names_in_the_zip_open_on_windows_the_stored_names_stay(self):
        document = self._document('re:port?.txt', b"x")
        other = self._document("con.txt", b"y")
        __, archive = self._zip(document, other)
        self.assertEqual(archive.namelist(), ["re_port_.txt", "_con.txt"])
        self.assertEqual(document.name, "re:port?.txt")

    def test_a_document_the_user_may_not_read_refuses_the_whole_request(self):
        mine = self._document("mine.txt")
        hidden = self._document("hidden.txt", b"secret", self.secret)
        response = self.url_open(self._url_of(mine, hidden))
        self.assertEqual(response.status_code, 403)
        self.assertNotIn(b"PK", response.content[:2])

    def test_a_document_that_does_not_exist_is_not_found(self):
        mine = self._document("mine.txt")
        response = self.url_open(f"{ROUTE}{mine.id},{mine.id + 100000}")
        self.assertEqual(response.status_code, 404)

    def test_an_address_that_is_no_list_of_ids_is_a_bad_request(self):
        self.assertEqual(self.url_open(ROUTE + "1,abc").status_code, 400)

    def test_a_file_that_is_missing_answers_with_its_name_and_no_zip(self):
        first, second = self._document("a.txt"), self._document("gone.txt", b"other")
        os.unlink(second._blob_path(second.checksum))
        response = self.url_open(self._url_of(first, second))
        self.assertEqual(response.status_code, 409)
        self.assertIn("gone.txt", response.text)

    def test_more_bytes_than_the_parameter_allows_answer_without_a_zip(self):
        documents = (self._document("a.txt", b"x" * 100), self._document("b.txt", b"y" * 100))
        self.env["ir.config_parameter"].set_param(ZIP_MAX_SIZE_PARAMETER, "150")
        response = self.url_open(self._url_of(*documents))
        self.assertEqual(response.status_code, 409)
        self.assertIn("in parts", response.text)

    def test_a_company_the_user_may_not_use_is_refused(self):
        document = self._document()
        other = self.env["res.company"].create({"name": "Not mine"})
        self.opener.cookies.set("cids", str(other.id), domain="127.0.0.1", path="/")
        self.assertEqual(self.url_open(self._url_of(document)).status_code, 403)

    def test_the_company_of_the_list_decides_what_is_read(self):
        # The folder lies in another company that the user is allowed to use, but the list
        # shows only the first: what the list does not show is not delivered.
        other = self.env["res.company"].create({"name": "Second"})
        self.user.write({"company_ids": [(4, other.id)]})
        theirs = self.env["int.filemanager.folder"].create(
            {"name": "Theirs", "access_mode": "open", "company_id": other.id}
        )
        document = self._document("theirs.txt", b"z", theirs)
        self.opener.cookies.set("cids", str(self.user.company_id.id), domain="127.0.0.1", path="/")
        self.assertEqual(self.url_open(self._url_of(document)).status_code, 403)
        self.opener.cookies.set("cids", f"{self.user.company_id.id}-{other.id}", domain="127.0.0.1", path="/")
        self.assertEqual(self.url_open(self._url_of(document)).status_code, 200)

    def test_without_the_right_to_the_filemanager_nothing_is_delivered(self):
        document = self._document()
        new_test_user(self.env, login="zip_outsider", groups="base.group_user")
        self.authenticate("zip_outsider", "zip_outsider")
        self.assertEqual(self.url_open(self._url_of(document)).status_code, 403)

    def test_a_visitor_who_is_not_logged_in_is_sent_to_the_login(self):
        document = self._document()
        self.opener.cookies.clear()
        response = self.url_open(self._url_of(document), allow_redirects=False)
        self.assertIn(response.status_code, (302, 303))
        self.assertIn("login", response.headers["Location"])
