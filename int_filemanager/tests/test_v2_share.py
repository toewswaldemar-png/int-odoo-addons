"""Sharing (Schritt 4a-6): anonymous links with expiry and revocation, the download log,
and the customer portal's per-partner shares."""

from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests.common import HttpCase, tagged
from odoo.tools import config


@tagged("post_install", "-at_install")
class TestV2Share(HttpCase):
    def setUp(self):
        super().setUp()
        self.enterContext(patch.dict(config.options, {"x_sendfile": False}))
        base_group = self.env.ref("int_filemanager.group_filemanager_user")
        group = self.env["res.groups"].sudo().create({"name": "Share group"})
        scope = (
            self.env["int_filemanager.scope"]
            .sudo()
            .create(
                {
                    "name": "Share scope",
                    "read_group_ids": [(4, group.id)],
                    "write_group_ids": [(4, group.id)],
                }
            )
        )
        self.folder = (
            self.env["int_filemanager.node"]
            .sudo()
            .create({"name": "shared", "scope_id": scope.id, "is_dir": True})
        )
        Users = self.env["res.users"].sudo()
        self.writer = Users.create(
            {
                "name": "Share writer",
                "login": "share_writer",
                "password": "share_writer_pw_1",
                "group_ids": [(6, 0, [base_group.id, group.id])],
            }
        )
        self.outsider = Users.create(
            {
                "name": "Share outsider",
                "login": "share_outsider",
                "password": "share_outsider_pw_1",
                "group_ids": [(6, 0, [base_group.id])],
            }
        )
        self.portal_user = Users.create(
            {
                "name": "Share portal",
                "login": "share_portal",
                "password": "share_portal_pw_1",
                "group_ids": [(6, 0, [self.env.ref("base.group_portal").id])],
            }
        )
        created = (
            self.env["int_filemanager.node"]
            .with_user(self.writer)
            .create_file(self.folder.id, "report.txt", b"the report", "op-share-1")
        )
        self.node = self.env["int_filemanager.node"].sudo().browse(created["node_id"])
        self.Share = self.env["int_filemanager.share"]

    def _link(self, days=None):
        return self.Share.with_user(self.writer).create_link(self.node.id, days)

    def _token(self, link):
        return link["url"].rsplit("/", 1)[1]

    def _anonymous_get(self, token):
        self.authenticate(None, None)
        return self.url_open(f"/int_filemanager/v2/share/{token}")

    # --- links -----------------------------------------------------------------

    def test_link_downloads_without_login_and_is_logged(self):
        link = self._link()

        res = self._anonymous_get(self._token(link))

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.content, b"the report")
        self.assertIn("report.txt", res.headers["Content-Disposition"])
        self.assertIn("no-store", res.headers["Cache-Control"])
        logs = (
            self.env["int_filemanager.share_log"]
            .sudo()
            .search([("node_id", "=", self.node.id)], order="id")
        )
        self.assertEqual(logs.mapped("event_type"), ["created", "downloaded"])
        self.assertEqual(logs[0].path, "/shared/report.txt")
        share = self.Share.sudo().browse(link["share_id"])
        self.assertEqual(share.download_count, 1)

    def test_default_expiry_is_30_days_and_days_are_clamped(self):
        share = self.Share.sudo().browse(self._link()["share_id"])
        delta = share.expires_at - fields.Datetime.now()
        self.assertAlmostEqual(delta.days, 29, delta=1)

        huge = self.Share.sudo().browse(self._link(days=100000)["share_id"])
        self.assertLessEqual((huge.expires_at - fields.Datetime.now()).days, 365)

    def test_expired_link_is_404(self):
        link = self._link()
        self.Share.sudo().browse(link["share_id"]).write(
            {"expires_at": fields.Datetime.now() - timedelta(seconds=1)}
        )
        self.assertEqual(self._anonymous_get(self._token(link)).status_code, 404)

    def test_revoked_link_is_404_and_logged(self):
        link = self._link()
        self.Share.with_user(self.writer).revoke_link(link["share_id"])

        self.assertEqual(self._anonymous_get(self._token(link)).status_code, 404)
        events = (
            self.env["int_filemanager.share_log"]
            .sudo()
            .search([("node_id", "=", self.node.id)])
            .mapped("event_type")
        )
        self.assertIn("revoked", events)

    def test_unknown_token_is_404(self):
        self.assertEqual(self._anonymous_get("nope").status_code, 404)

    def test_trashed_file_link_is_404_and_works_again_after_restore(self):
        link = self._link()
        Node = self.env["int_filemanager.node"].with_user(self.writer)
        Node.trash(self.node.id, "op-share-trash")
        self.assertEqual(self._anonymous_get(self._token(link)).status_code, 404)

        Node.restore(self.node.id, "op-share-restore")
        self.assertEqual(self._anonymous_get(self._token(link)).status_code, 200)

    def test_link_serves_the_current_revision(self):
        link = self._link()
        Node = self.env["int_filemanager.node"].with_user(self.writer)
        Node.create_new_revision(
            self.node.id, self.node.current_revision_id.id, b"newer", "op-share-rev"
        )
        self.assertEqual(self._anonymous_get(self._token(link)).content, b"newer")

    def test_only_writers_can_create_or_revoke_links(self):
        with self.assertRaises(AccessError):
            self.Share.with_user(self.outsider).create_link(self.node.id)
        link = self._link()
        with self.assertRaises(AccessError):
            self.Share.with_user(self.outsider).revoke_link(link["share_id"])

    def test_folders_cannot_be_shared_by_link(self):
        with self.assertRaises(UserError):
            self.Share.with_user(self.writer).create_link(self.folder.id)

    def test_users_cannot_write_or_create_share_rows_themselves(self):
        link = self._link()
        Share = self.Share.with_user(self.writer)
        with self.assertRaises(AccessError):
            Share.browse(link["share_id"]).write({"expires_at": "2999-01-01 00:00:00"})
        with self.assertRaises(AccessError):
            Share.create(
                {
                    "node_id": self.node.id,
                    "token": "chosen-by-me",
                    "expires_at": "2999-01-01 00:00:00",
                }
            )

    def test_outsiders_do_not_see_the_links_of_a_file(self):
        self._link()
        self.assertFalse(self.Share.with_user(self.outsider).search([]))
        self.assertTrue(self.Share.with_user(self.writer).search([]))

    # --- customer portal -----------------------------------------------------------

    def _portal_get(self, path, login="share_portal"):
        self.authenticate(login, f"{login}_pw_1")
        return self.url_open(path)

    def test_portal_partner_sees_and_downloads_only_what_is_shared_with_them(self):
        other = (
            self.env["int_filemanager.node"]
            .with_user(self.writer)
            .create_file(self.folder.id, "private.txt", b"private", "op-share-2")
        )
        self.node.write({"shared_partner_ids": [(4, self.portal_user.partner_id.id)]})

        page = self._portal_get("/my/files")
        self.assertEqual(page.status_code, 200)
        self.assertIn("report.txt", page.text)
        self.assertNotIn("private.txt", page.text)

        res = self._portal_get(f"/my/files/{self.node.id}/download")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.content, b"the report")
        log = (
            self.env["int_filemanager.share_log"]
            .sudo()
            .search([("node_id", "=", self.node.id), ("event_type", "=", "downloaded")])
        )
        self.assertEqual(log.partner_id, self.portal_user.partner_id)

        denied = self._portal_get(f"/my/files/{other['node_id']}/download")
        self.assertEqual(denied.status_code, 404)

    def test_portal_download_stops_when_the_file_is_trashed(self):
        self.node.write({"shared_partner_ids": [(4, self.portal_user.partner_id.id)]})
        self.env["int_filemanager.node"].with_user(self.writer).trash(
            self.node.id, "op-share-portal-trash"
        )
        res = self._portal_get(f"/my/files/{self.node.id}/download")
        self.assertEqual(res.status_code, 404)

    def test_portal_user_has_no_direct_access_to_nodes(self):
        self.node.write({"shared_partner_ids": [(4, self.portal_user.partner_id.id)]})
        with self.assertRaises(AccessError):
            self.env["int_filemanager.node"].with_user(self.portal_user).search([])
