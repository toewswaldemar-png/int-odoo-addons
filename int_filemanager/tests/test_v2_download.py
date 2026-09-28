"""Download route of the v2 file manager (Schritt 4a-2): rights per node and revision,
old revisions, Range, and the x_sendfile hand-over below data_dir/filestore."""

from unittest.mock import patch

from odoo import http
from odoo.tests.common import HttpCase, tagged
from odoo.tools import config

CONTENT = b"0123456789" * 100


@tagged("post_install", "-at_install")
class TestV2Download(HttpCase):
    def setUp(self):
        super().setUp()
        # The test instance's odoo.conf turns x_sendfile on (bodyless responses that
        # only nginx completes); the content tests need the real body.
        self.enterContext(patch.dict(config.options, {"x_sendfile": False}))
        base_group = self.env.ref("int_filemanager.group_filemanager_user")
        group = self.env["res.groups"].sudo().create({"name": "Download group"})
        scope = (
            self.env["int_filemanager.scope"]
            .sudo()
            .create(
                {
                    "name": "Download scope",
                    "read_group_ids": [(4, group.id)],
                    "write_group_ids": [(4, group.id)],
                }
            )
        )
        folder = (
            self.env["int_filemanager.node"]
            .sudo()
            .create({"name": "dl", "scope_id": scope.id, "is_dir": True})
        )
        Users = self.env["res.users"].sudo()
        self.reader = Users.create(
            {
                "name": "DL reader",
                "login": "dl_reader",
                "password": "dl_reader_pw_1",
                "group_ids": [(6, 0, [base_group.id, group.id])],
            }
        )
        self.outsider = Users.create(
            {
                "name": "DL outsider",
                "login": "dl_outsider",
                "password": "dl_outsider_pw_1",
                "group_ids": [(6, 0, [base_group.id])],
            }
        )
        Node = self.env["int_filemanager.node"].with_user(self.reader)
        first = Node.create_file(folder.id, "data.bin", CONTENT, "op-dl-1")
        self.node_id = first["node_id"]
        self.first_revision_id = first["revision_id"]
        second = Node.create_new_revision(
            self.node_id, self.first_revision_id, b"second version", "op-dl-2"
        )
        self.second_revision_id = second["revision_id"]
        self.folder = folder
        other = Node.create_file(folder.id, "other.bin", b"other", "op-dl-3")
        self.other_revision_id = other["revision_id"]

    def _get(self, path, login="dl_reader", headers=None):
        self.authenticate(login, f"{login}_pw_1")
        return self.url_open(path, headers=headers)

    def test_current_revision_is_served_as_attachment(self):
        res = self._get(f"/int_filemanager/v2/download/{self.node_id}")

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.content, b"second version")
        self.assertIn("attachment", res.headers["Content-Disposition"])
        self.assertIn("data.bin", res.headers["Content-Disposition"])

    def test_old_revision_can_be_downloaded(self):
        res = self._get(
            f"/int_filemanager/v2/download/{self.node_id}"
            f"?revision_id={self.first_revision_id}"
        )

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.content, CONTENT)

    def test_revision_of_another_node_is_404(self):
        res = self._get(
            f"/int_filemanager/v2/download/{self.node_id}"
            f"?revision_id={self.other_revision_id}"
        )
        self.assertEqual(res.status_code, 404)

    def test_bad_revision_id_is_400(self):
        res = self._get(f"/int_filemanager/v2/download/{self.node_id}?revision_id=abc")
        self.assertEqual(res.status_code, 400)

    def test_inline_disposition(self):
        url = f"/int_filemanager/v2/download/{self.node_id}?disposition=inline"
        res = self._get(url)
        self.assertNotIn("attachment", res.headers.get("Content-Disposition", ""))

    def test_range_request_gets_partial_content(self):
        res = self._get(
            f"/int_filemanager/v2/download/{self.node_id}"
            f"?revision_id={self.first_revision_id}",
            headers={"Range": "bytes=10-19"},
        )

        self.assertEqual(res.status_code, 206)
        self.assertEqual(res.content, CONTENT[10:20])

    def test_user_without_read_right_gets_403(self):
        res = self._get(
            f"/int_filemanager/v2/download/{self.node_id}", login="dl_outsider"
        )
        self.assertEqual(res.status_code, 403)

    def test_old_revision_is_also_protected(self):
        res = self._get(
            f"/int_filemanager/v2/download/{self.node_id}"
            f"?revision_id={self.first_revision_id}",
            login="dl_outsider",
        )
        self.assertEqual(res.status_code, 403)

    def test_folder_is_400_and_missing_node_404(self):
        folder_url = f"/int_filemanager/v2/download/{self.folder.id}"
        self.assertEqual(self._get(folder_url).status_code, 400)
        self.assertEqual(
            self._get("/int_filemanager/v2/download/99999999").status_code, 404
        )

    def test_anonymous_is_not_served(self):
        self.authenticate(None, None)
        res = self.url_open(
            f"/int_filemanager/v2/download/{self.node_id}", allow_redirects=False
        )
        self.assertIn(res.status_code, (303, 401, 403))

    def test_x_sendfile_hands_over_a_path_inside_the_filestore(self):
        with patch.dict(config.options, {"x_sendfile": True}):
            res = self._get(f"/int_filemanager/v2/download/{self.node_id}")

        redirect = res.headers.get("X-Accel-Redirect", "")
        self.assertTrue(
            redirect.startswith(f"/web/filestore/{self.env.cr.dbname}/blobs/"),
            redirect,
        )
        self.assertEqual(res.content, b"")


@tagged("post_install", "-at_install")
class TestV2UploadChunkRoute(HttpCase):
    """The chunk route (Schritt 4a-3): raw body, CSRF token in the query string, size
    limit, and a complete init -> chunks -> finish -> download round trip."""

    def setUp(self):
        super().setUp()
        self.enterContext(patch.dict(config.options, {"x_sendfile": False}))
        base_group = self.env.ref("int_filemanager.group_filemanager_user")
        group = self.env["res.groups"].sudo().create({"name": "Chunk group"})
        scope = (
            self.env["int_filemanager.scope"]
            .sudo()
            .create(
                {
                    "name": "Chunk scope",
                    "read_group_ids": [(4, group.id)],
                    "write_group_ids": [(4, group.id)],
                }
            )
        )
        self.folder = (
            self.env["int_filemanager.node"]
            .sudo()
            .create({"name": "chunks", "scope_id": scope.id, "is_dir": True})
        )
        Users = self.env["res.users"].sudo()
        self.writer = Users.create(
            {
                "name": "Chunk writer",
                "login": "chunk_writer",
                "password": "chunk_writer_pw_1",
                "group_ids": [(6, 0, [base_group.id, group.id])],
            }
        )
        self.other = Users.create(
            {
                "name": "Chunk other",
                "login": "chunk_other",
                "password": "chunk_other_pw_1",
                "group_ids": [(6, 0, [base_group.id, group.id])],
            }
        )

    def _post_chunk(self, upload_id, offset, data, csrf=True, login="chunk_writer"):
        self.authenticate(login, f"{login}_pw_1")
        params = {"offset": offset}
        if csrf:
            params["csrf_token"] = http.Request.csrf_token(self)
        return self.url_open(
            f"/int_filemanager/v2/upload/{upload_id}/chunk",
            data=data,
            params=params,
            headers={"Content-Type": "application/octet-stream"},
        )

    def _init(self, name="round.bin", size=None):
        return (
            self.env["int_filemanager.upload"]
            .with_user(self.writer)
            .init_upload(self.folder.id, name, False, False, size, f"op-init-{name}")
        )["upload_id"]

    def test_chunks_arrive_in_order_and_the_file_downloads_back(self):
        upload_id = self._init(size=12)

        first = self._post_chunk(upload_id, 0, b"hello ")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json()["received_size"], 6)
        again = self._post_chunk(upload_id, 0, b"hello ")  # a retried piece
        self.assertEqual(again.json()["received_size"], 6)
        second = self._post_chunk(upload_id, 6, b"world!")
        self.assertEqual(second.json()["received_size"], 12)

        finish = (
            self.env["int_filemanager.upload"]
            .with_user(self.writer)
            .finish_upload(upload_id, "op-finish-round")
        )
        res = self.url_open(f"/int_filemanager/v2/download/{finish['node_id']}")
        self.assertEqual(res.content, b"hello world!")

    def test_a_gap_is_refused(self):
        upload_id = self._init()
        res = self._post_chunk(upload_id, 100, b"gap")
        self.assertNotEqual(res.status_code, 200)

    def test_without_csrf_token_nothing_is_written(self):
        upload_id = self._init()
        res = self._post_chunk(upload_id, 0, b"data", csrf=False)
        self.assertEqual(res.status_code, 400)
        upload = self.env["int_filemanager.upload"].sudo().browse(upload_id)
        self.assertEqual(upload.received_size, 0)

    def test_oversized_chunk_is_rejected(self):
        upload_id = self._init()
        res = self._post_chunk(upload_id, 0, b"x" * (5 * 1024 * 1024 + 1))
        self.assertEqual(res.status_code, 413)

    def test_a_chunk_at_the_limit_is_accepted(self):
        upload_id = self._init()
        res = self._post_chunk(upload_id, 0, b"x" * (4 * 1024 * 1024))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["received_size"], 4 * 1024 * 1024)

    def test_someone_elses_upload_cannot_be_written_to(self):
        upload_id = self._init()
        res = self._post_chunk(upload_id, 0, b"data", login="chunk_other")
        self.assertIn(res.status_code, (403, 404))
        upload = self.env["int_filemanager.upload"].sudo().browse(upload_id)
        self.assertEqual(upload.received_size, 0)

    def test_non_numeric_offset_is_400(self):
        upload_id = self._init()
        res = self._post_chunk(upload_id, "abc", b"data")
        self.assertEqual(res.status_code, 400)
