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
class TestEditStateUpload(HttpCase):
    """The state of the picture editor that comes with a picture it stored (``POST /int_filemanager/upload``)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Document = cls.env["int.filemanager.document"]
        cls.folder = cls.env["int.filemanager.folder"].create(
            {"name": "Uploads", "access_mode": "open"}
        )
        cls.user = new_test_user(
            cls.env,
            login="edit_user",
            groups="base.group_user,int_filemanager.int_filemanager_group_user",
        )

    def setUp(self):
        super().setUp()
        self.authenticate("edit_user", "edit_user")

    def _upload(self, content=b"hello", name="a.txt", mimetype="text/plain", **extra):
        data = {"csrf_token": http.Request.csrf_token(self), "folder_id": self.folder.id, **extra}
        response = self.url_open(
            UPLOAD, data=data, files={"ufile": (name, io.BytesIO(content), mimetype)}
        )
        if response.status_code == 200:
            document = self.Document.browse(response.json()["id"])
            self.addCleanup(remove, self.Document._blob_path(document.checksum))
        return response

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
        with patch("odoo.addons.int_filemanager_image_editor.controllers.int_filemanager.EDIT_STATE_MAX_SIZE", 20):
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
