import io
import os

from odoo import http
from odoo.tests.common import HttpCase, new_test_user, tagged

UPLOAD = "/int_filemanager/upload"


def remove(path):
    if os.path.exists(path):
        os.unlink(path)


@tagged("post_install", "-at_install")
class TestDocumentUpload(HttpCase):
    """``POST /int_filemanager/upload``: one file per request, as the ``file_upload`` service sends."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Document = cls.env["int.filemanager.document"]
        cls.folder = cls.env["int.filemanager.folder"].create(
            {"name": "Uploads", "access_mode": "open"}
        )
        cls.user = new_test_user(
            cls.env,
            login="upload_user",
            groups="base.group_user,int_filemanager.int_filemanager_group_user",
        )
        cls.outsider = new_test_user(cls.env, login="upload_outsider", groups="base.group_user")

    def setUp(self):
        super().setUp()
        self.authenticate("upload_user", "upload_user")

    def _upload(self, content=b"hello", name="a.txt", mimetype="text/plain", folder=None, **extra):
        data = {"csrf_token": http.Request.csrf_token(self), **extra}
        if folder is not False:
            data.setdefault("folder_id", (folder or self.folder).id)
        response = self.url_open(
            UPLOAD, data=data, files={"ufile": (name, io.BytesIO(content), mimetype)}
        )
        if response.status_code == 200:
            document = self.Document.browse(response.json()["id"])
            self.addCleanup(remove, self.Document._blob_path(document.checksum))
        return response

    def _leftovers(self):
        """The temporary files in the upload folder; there must be none after a request."""
        folder = os.path.join(self.env["ir.attachment"]._filestore(), "int_filemanager", ".upload")
        return os.listdir(folder) if os.path.isdir(folder) else []

    def test_an_upload_creates_a_document_with_the_file(self):
        response = self._upload(b"hello world", "notes.txt")
        self.assertEqual(response.status_code, 200)
        answer = response.json()
        document = self.Document.browse(answer["id"])
        self.assertEqual(answer["name"], "notes.txt")
        self.assertEqual((document.name, document.folder_id), ("notes.txt", self.folder))
        self.assertEqual((document.size, document.mimetype), (11, "text/plain"))
        self.assertEqual(document.create_uid, self.user)
        with open(self.Document._blob_path(document.checksum), "rb") as blob:
            self.assertEqual(blob.read(), b"hello world")

    def test_nothing_is_left_in_the_upload_folder(self):
        self._upload()
        self.assertFalse(self._leftovers())

    def test_a_taken_name_is_numbered(self):
        names = [self._upload(bytes([n]), "a.txt").json()["name"] for n in range(3)]
        self.assertEqual(names, ["a.txt", "a (2).txt", "a (3).txt"])

    def test_the_same_content_twice_is_two_documents_and_one_blob(self):
        first = self.Document.browse(self._upload(b"same", "a.txt").json()["id"])
        second = self.Document.browse(self._upload(b"same", "b.txt").json()["id"])
        self.assertNotEqual(first, second)
        self.assertEqual(first.checksum, second.checksum)

    def test_a_path_in_the_file_name_is_cut_off(self):
        response = self._upload(name="C:\\fakepath\\evil.txt")
        self.assertEqual(response.json()["name"], "evil.txt")

    def test_an_office_file_keeps_its_type_even_when_the_browser_says_binary(self):
        response = self._upload(b"PK", "a.docx", "application/octet-stream")
        self.assertTrue(response.json()["mimetype"].startswith("application/vnd.openxmlformats"))

    def test_html_is_stored_as_plain_text(self):
        response = self._upload(b"<script>alert(1)</script>", "page.html", "text/html")
        self.assertEqual(response.json()["mimetype"], "text/plain")

    def test_the_limit_of_the_core_does_not_apply(self):
        # 130 MiB: more than the 128 MiB that stop every route without its own limit.
        response = self._upload(bytes(130 * 1024 * 1024), "big.bin")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["size"], 130 * 1024 * 1024)

    def test_the_large_limit_is_for_those_who_may_upload(self):
        # The body is read before the controller runs: whoever may not upload keeps the core's
        # limit (a reader, a portal user), so that nothing large is spooled to the disk for them.
        reader = new_test_user(
            self.env,
            login="upload_reader",
            groups="base.group_user,int_filemanager.int_filemanager_group_reader",
        )
        new_test_user(self.env, login="upload_portal", groups="base.group_portal")
        before = self.Document.search_count([])
        for login in (reader.login, "upload_portal", self.outsider.login):
            with self.subTest(login=login):
                self.authenticate(login, login)
                response = self._upload(bytes(130 * 1024 * 1024), "big.bin")
                self.assertEqual(response.status_code, 413)
        self.assertEqual(self.Document.search_count([]), before)
        self.assertFalse(self._leftovers())

    def test_the_limit_is_a_system_parameter(self):
        self.env["ir.config_parameter"].set_param("int_filemanager.max_upload_size", "1000")
        before = self.Document.search_count([])
        response = self._upload(bytes(5000), "too-big.bin")
        self.assertEqual(response.status_code, 413)
        self.assertEqual(self.Document.search_count([]), before)
        self.assertFalse(self._leftovers())

    def test_a_missing_or_unknown_folder_is_404(self):
        self.assertEqual(self._upload(folder=False).status_code, 404)
        self.assertEqual(self._upload(folder_id="x").status_code, 404)
        self.assertEqual(self._upload(folder_id=999999).status_code, 404)

    def test_an_archived_folder_is_404(self):
        self.folder.active = False
        self.assertEqual(self._upload().status_code, 404)

    def test_a_folder_of_another_company_is_404(self):
        other = self.env["res.company"].create({"name": "Other company"})
        foreign = self.env["int.filemanager.folder"].create(
            {"name": "Foreign", "company_id": other.id}
        )
        self.assertEqual(self._upload(folder=foreign).status_code, 404)

    def test_a_user_without_the_group_is_refused_and_nothing_is_stored(self):
        self.authenticate("upload_outsider", "upload_outsider")
        before = self.Document.search_count([])
        response = self._upload()
        self.assertEqual(response.status_code, 403)
        self.assertIn("message", response.json()["error"])
        self.assertEqual(self.Document.search_count([]), before)
        self.assertFalse(self._leftovers())

    def test_exactly_one_file_per_request(self):
        data = {"csrf_token": http.Request.csrf_token(self), "folder_id": self.folder.id}
        none = self.url_open(UPLOAD, data=data)
        self.assertEqual(none.status_code, 400)
        two = self.url_open(
            UPLOAD,
            data=data,
            files=[("ufile", ("a.txt", io.BytesIO(b"a"))), ("ufile", ("b.txt", io.BytesIO(b"b")))],
        )
        self.assertEqual(two.status_code, 400)

    def test_a_name_without_content_is_400(self):
        response = self._upload(name="..")
        self.assertEqual(response.status_code, 400)

    def test_a_request_without_csrf_token_is_refused(self):
        response = self.url_open(
            UPLOAD,
            data={"folder_id": self.folder.id},
            files={"ufile": ("a.txt", io.BytesIO(b"a"))},
        )
        self.assertNotEqual(response.status_code, 200)

    def test_get_is_not_allowed(self):
        self.assertEqual(self.url_open(UPLOAD).status_code, 405)

    def test_an_uploaded_file_can_be_downloaded(self):
        document = self.Document.browse(self._upload(b"round trip", "trip.txt").json()["id"])
        response = self.url_open(
            f"/web/content/int.filemanager.document/{document.id}/content?download=true"
        )
        self.assertEqual(response.content, b"round trip")
