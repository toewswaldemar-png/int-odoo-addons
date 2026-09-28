"""Preview route and the rights on derived files, over HTTP and both RPC routes.

The derived file has no rights of its own (users cannot read that model): the
preview route decides by the rights on the revision, and nothing else reaches it.
"""

import datetime
from unittest.mock import patch

from odoo.tests.common import HttpCase, tagged
from odoo.tools import config

from .. import converter_client
from ..models import int_filemanager_derivative as derivative_module
from .test_v2_derivative import JPEG, PDF, TILE, FakeConverter


@tagged("post_install", "-at_install")
class TestV2PreviewHttp(HttpCase):
    def setUp(self):
        super().setUp()
        # The test instance turns x_sendfile on (bodyless responses that only nginx
        # completes); these tests need the real body.
        self.enterContext(patch.dict(config.options, {"x_sendfile": False}))
        self.enterContext(
            patch.object(
                self.env.registry["ir.cron"], "_commit_progress", return_value=1.0
            )
        )
        base_group = self.env.ref("int_filemanager.group_filemanager_user")
        admin_group = self.env.ref("int_filemanager.group_filemanager_admin")
        group = self.env["res.groups"].sudo().create({"name": "Preview HTTP group"})
        scope = (
            self.env["int_filemanager.scope"]
            .sudo()
            .create(
                {
                    "name": "Preview HTTP scope",
                    "read_group_ids": [(4, group.id)],
                    "write_group_ids": [(4, group.id)],
                }
            )
        )
        folder = (
            self.env["int_filemanager.node"]
            .sudo()
            .create({"name": "previews", "scope_id": scope.id, "is_dir": True})
        )
        Users = self.env["res.users"].sudo()
        self.reader = Users.create(
            {
                "name": "Preview reader",
                "login": "preview_reader",
                "group_ids": [(6, 0, [base_group.id, group.id])],
            }
        )
        self.outsider = Users.create(
            {
                "name": "Preview outsider",
                "login": "preview_outsider",
                "group_ids": [(6, 0, [base_group.id])],
            }
        )
        self.manager = Users.create(
            {
                "name": "Preview manager",
                "login": "preview_manager",
                "group_ids": [(6, 0, [admin_group.id])],
            }
        )
        made = (
            self.env["int_filemanager.node"]
            .with_user(self.reader)
            .create_file(folder.id, "photo.jpg", JPEG, "op-preview-1")
        )
        self.revision_id = made["revision_id"]
        self.node = self.env["int_filemanager.node"].sudo().browse(made["node_id"])
        self.Derivative = self.env["int_filemanager.derivative"].sudo()
        self.env["ir.config_parameter"].sudo().set_param(
            derivative_module.CONVERTER_URL_PARAM, "http://converter.invalid"
        )

    def _convert(self):
        with patch.object(converter_client, "convert", FakeConverter()):
            self.Derivative._cron_run()
        self.job = self.Derivative.search(
            [
                ("source_blob_id", "=", self.node.current_revision_id.blob_id.id),
                ("kind", "=", "tile"),
            ]
        )

    def _url(self, revision_id=None, kind="tile"):
        return f"/int_filemanager/v2/preview/{revision_id or self.revision_id}/{kind}"

    def _api_key(self, user):
        return (
            self.env["res.users.apikeys"]
            .with_user(user)
            ._generate(
                scope="rpc",
                name="preview test",
                expiration_date=datetime.datetime.now() + datetime.timedelta(hours=1),
            )
        )

    def _call_kw(self, model, method, args=None, kwargs=None):
        return self.url_open(
            "/web/dataset/call_kw",
            json={
                "jsonrpc": "2.0",
                "method": "call",
                "params": {
                    "model": model,
                    "method": method,
                    "args": args or [],
                    "kwargs": kwargs or {},
                },
                "id": 1,
            },
        )

    # -- the route ---------------------------------------------------------

    def test_reader_gets_the_tile(self):
        self._convert()
        self.authenticate("preview_reader", "irrelevant")
        response = self.url_open(self._url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, TILE)
        self.assertEqual(response.headers["Content-Type"], "image/jpeg")
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
        self.assertIn("private", response.headers["Cache-Control"])
        self.assertEqual(
            response.headers["ETag"].strip('"'), self.job.derived_blob_id.sha256
        )
        self.assertNotIn("attachment", response.headers.get("Content-Disposition", ""))

    def test_a_browser_image_is_served_as_its_own_large_preview(self):
        self._convert()
        self.authenticate("preview_reader", "irrelevant")
        response = self.url_open(self._url(kind="preview"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, JPEG)
        self.assertEqual(response.headers["Content-Type"], "image/jpeg")
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")

    def test_the_large_preview_is_protected_like_the_tile(self):
        self._convert()
        self.authenticate("preview_outsider", "irrelevant")
        response = self.url_open(self._url(kind="preview"))
        self.assertEqual(response.status_code, 403)
        self.assertNotIn(JPEG, response.content)

    def test_an_office_document_is_served_as_its_pdf_and_thumbnail(self):
        folder = self.node.parent_id
        made = (
            self.env["int_filemanager.node"]
            .with_user(self.reader)
            .create_file(folder.id, "letter.docx", b"docx bytes", "op-preview-docx")
        )
        self._convert()
        self.authenticate("preview_reader", "irrelevant")
        pdf = self.url_open(self._url(made["revision_id"], "preview_pdf"))
        self.assertEqual(pdf.status_code, 200)
        self.assertEqual(pdf.content, PDF)
        self.assertEqual(pdf.headers["Content-Type"], "application/pdf")
        self.assertEqual(pdf.headers["X-Content-Type-Options"], "nosniff")
        tile = self.url_open(self._url(made["revision_id"], "tile"))
        self.assertEqual((tile.status_code, tile.content), (200, TILE))
        self.authenticate("preview_outsider", "irrelevant")
        self.assertEqual(
            self.url_open(self._url(made["revision_id"], "preview_pdf")).status_code,
            403,
        )

    def test_text_and_facts_have_no_route(self):
        self._convert()
        self.authenticate("preview_reader", "irrelevant")
        for kind in ("text", "meta"):
            with self.subTest(kind=kind):
                self.assertEqual(self.url_open(self._url(kind=kind)).status_code, 404)

    def test_range_and_conditional_requests_work(self):
        self._convert()
        self.authenticate("preview_reader", "irrelevant")
        part = self.url_open(self._url(), headers={"Range": "bytes=0-3"})
        self.assertEqual((part.status_code, part.content), (206, TILE[:4]))
        etag = self.url_open(self._url()).headers["ETag"]
        again = self.url_open(self._url(), headers={"If-None-Match": etag})
        self.assertEqual(again.status_code, 304)

    def test_outsider_gets_nothing(self):
        self._convert()
        self.authenticate("preview_outsider", "irrelevant")
        response = self.url_open(self._url())
        self.assertEqual(response.status_code, 403)
        self.assertNotIn(TILE, response.content)

    def test_anonymous_gets_nothing(self):
        self._convert()
        self.authenticate(None, None)
        response = self.url_open(self._url(), allow_redirects=False)
        self.assertNotEqual(response.status_code, 200)
        self.assertNotIn(TILE, response.content)

    def test_without_a_result_it_is_404(self):
        self.authenticate("preview_reader", "irrelevant")
        self.assertEqual(self.url_open(self._url()).status_code, 404)

    def test_unknown_revision_and_kind_are_404(self):
        self._convert()
        self.authenticate("preview_reader", "irrelevant")
        self.assertEqual(self.url_open(self._url(revision_id=999999)).status_code, 404)
        for kind in ("text", "TILE", "../tile", "meta"):
            with self.subTest(kind=kind):
                self.assertEqual(self.url_open(self._url(kind=kind)).status_code, 404)

    def test_an_old_revision_keeps_its_own_tile(self):
        self._convert()
        old_revision = self.revision_id
        new_content = JPEG + b"changed"
        self.env["int_filemanager.node"].with_user(self.reader).create_new_revision(
            self.node.id, old_revision, new_content, "op-preview-2"
        )
        self.authenticate("preview_reader", "irrelevant")
        self.assertEqual(self.url_open(self._url(old_revision)).content, TILE)
        newest = self.node.revision_ids.sorted("revision_no")[-1].id
        self.assertEqual(
            self.url_open(self._url(newest)).status_code, 404, "not converted yet"
        )

    # -- the derived file itself is not reachable --------------------------

    def test_call_kw_on_the_derivative_model_is_denied_for_users(self):
        self._convert()
        self.authenticate("preview_reader", "irrelevant")
        for method, kwargs in (
            ("search_read", {"domain": [], "fields": ["error", "mime"]}),
            ("read", {}),
            ("search_count", {}),
        ):
            with self.subTest(method=method):
                args = [[self.job.id]] if method == "read" else [[]]
                response = self._call_kw(
                    "int_filemanager.derivative", method, args, kwargs
                )
                self.assertIn("error", response.json())

    def test_json2_on_the_derivative_model_is_denied_for_users(self):
        self._convert()
        key = self._api_key(self.reader)
        response = self.url_open(
            "/json/2/int_filemanager.derivative/search_read",
            json={"domain": [], "fields": ["error"]},
            headers={"Authorization": f"Bearer {key}"},
        )
        self.assertEqual(response.status_code, 403)

    def test_a_manager_may_read_it_and_only_read(self):
        self._convert()
        Derivative = self.env["int_filemanager.derivative"].with_user(self.manager)
        self.assertEqual(Derivative.browse(self.job.id).state, "done")
        from odoo.exceptions import AccessError

        with self.assertRaises(AccessError):
            Derivative.browse(self.job.id).write({"state": "failed"})
        with self.assertRaises(AccessError):
            Derivative.create(
                {
                    "source_blob_id": self.job.source_blob_id.id,
                    "kind": "tile",
                    "spec": "1x1",
                }
            )

    def test_web_image_and_web_content_do_not_serve_it(self):
        self._convert()
        self.authenticate("preview_reader", "irrelevant")
        for path in (
            f"/web/image/int_filemanager.derivative/{self.job.id}/mime",
            f"/web/content/int_filemanager.derivative/{self.job.id}/mime",
            f"/web/image/int_filemanager.derivative/{self.job.id}/derived_blob_id",
            f"/web/image/int_filemanager.blob/{self.job.derived_blob_id.id}/sha256",
        ):
            with self.subTest(path=path):
                response = self.url_open(path)
                # /web/image answers 200 with a placeholder picture when access is
                # denied; what matters is that the tile is not what comes back.
                self.assertNotIn(TILE, response.content)
                self.assertNotEqual(response.headers.get("Content-Type"), "image/jpeg")

    # -- what the explorer may call ----------------------------------------

    def test_users_can_read_the_state_and_request_previews(self):
        self.authenticate("preview_reader", "irrelevant")
        state = self._call_kw(
            "int_filemanager.node",
            "read",
            [[self.node.id], ["preview_state"]],
        ).json()["result"]
        self.assertEqual(state[0]["preview_state"], "pending")
        asked = self._call_kw(
            "int_filemanager.node", "request_previews", [[self.node.id]]
        ).json()
        self.assertEqual(asked["result"], 0, "not queued yet: nothing to move")

    def test_request_previews_for_unreadable_nodes_reveals_nothing(self):
        self.Derivative._enqueue_missing()
        self.authenticate("preview_outsider", "irrelevant")
        asked = self._call_kw(
            "int_filemanager.node", "request_previews", [[self.node.id]]
        ).json()
        self.assertEqual(asked["result"], 0)
        priorities = self.Derivative.search([("state", "=", "pending")]).mapped(
            "priority"
        )
        self.assertNotIn(derivative_module.VISIBLE_PRIORITY, priorities)
