import io
import json
import os
from unittest.mock import patch

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

    # The state of the picture editor that comes with a picture it stored.
    PICTURE = b"\x89PNG\r\n\x1a\n" + b"0" * 32

    def _store_edited(self, source, state=None, **extra):
        state = {"version": 1, "objects": []} if state is None else state
        return self._upload(
            self.PICTURE,
            "edited.png",
            "image/png",
            edit_state=json.dumps(state),
            edit_source_id=source.id,
            **extra,
        )

    def test_the_state_and_the_source_are_kept_with_the_picture(self):
        source = self.Document.browse(self._upload(self.PICTURE, "p.png", "image/png").json()["id"])
        response = self._store_edited(source, {"version": 1, "objects": [{"type": "Rect"}]})
        self.assertEqual(response.status_code, 200)
        document = self.Document.browse(response.json()["id"])
        self.assertEqual(document.sudo().edit_source_id, source)
        self.assertEqual(document.sudo().edit_state["objects"], [{"type": "Rect"}])
        session = document.get_edit_session()
        self.assertEqual(session["source"]["id"], source.id)
        self.assertEqual(session["state"]["objects"], [{"type": "Rect"}])

    def test_a_picture_without_state_has_no_session(self):
        document = self.Document.browse(self._upload(self.PICTURE, "p.png", "image/png").json()["id"])
        self.assertEqual(document.get_edit_session(), {})

    def test_a_source_that_the_user_cannot_read_is_dropped(self):
        secret = self.env["int.filemanager.folder"].create({"name": "Secret", "access_mode": "restricted"})
        hidden = self.Document._create_from_stream(io.BytesIO(self.PICTURE), "h.png", secret, "image/png")
        self.addCleanup(remove, self.Document._blob_path(hidden.checksum))
        response = self._store_edited(hidden)
        self.assertEqual(response.status_code, 200)
        document = self.Document.browse(response.json()["id"])
        self.assertFalse(document.sudo().edit_state)
        self.assertFalse(document.sudo().edit_source_id)

    def test_the_session_hides_a_source_that_the_user_cannot_read(self):
        secret = self.env["int.filemanager.folder"].create({"name": "Secret", "access_mode": "restricted"})
        hidden = self.Document._create_from_stream(io.BytesIO(self.PICTURE), "h.png", secret, "image/png")
        self.addCleanup(remove, self.Document._blob_path(hidden.checksum))
        document = self.Document._create_from_stream(
            io.BytesIO(self.PICTURE + b"1"),
            "e.png",
            self.folder,
            "image/png",
            edit_state={"version": 1},
            edit_source_id=hidden.id,
        )
        self.addCleanup(remove, self.Document._blob_path(document.checksum))
        self.assertEqual(document.with_user(self.user).get_edit_session(), {})
        self.assertTrue(document.get_edit_session())

    def test_a_state_that_is_no_json_object_is_400(self):
        source = self.Document.browse(self._upload(self.PICTURE, "p.png", "image/png").json()["id"])
        for broken in ("{not json", "[1, 2]", '"text"'):
            response = self._upload(
                self.PICTURE, "e.png", "image/png", edit_state=broken, edit_source_id=source.id
            )
            self.assertEqual(response.status_code, 400, broken)

    def test_a_state_that_is_too_large_is_400(self):
        source = self.Document.browse(self._upload(self.PICTURE, "p.png", "image/png").json()["id"])
        with patch("odoo.addons.int_filemanager.controllers.int_filemanager.EDIT_STATE_MAX_SIZE", 20):
            response = self._store_edited(source, {"version": 1, "objects": ["x" * 50]})
        self.assertEqual(response.status_code, 400)

    def test_a_user_cannot_write_the_state_by_hand(self):
        source = self.Document.browse(self._upload(self.PICTURE, "p.png", "image/png").json()["id"])
        source.with_user(self.user).write({"edit_state": {"x": 1}, "edit_source_id": source.id})
        self.assertFalse(source.sudo().edit_state)
        self.assertFalse(source.sudo().edit_source_id)

    def test_the_source_going_away_leaves_a_flat_picture(self):
        source = self.Document.browse(self._upload(self.PICTURE, "p.png", "image/png").json()["id"])
        document = self.Document.browse(self._store_edited(source).json()["id"])
        source.sudo().unlink()
        self.assertFalse(document.sudo().edit_source_id)
        self.assertEqual(document.get_edit_session(), {})
