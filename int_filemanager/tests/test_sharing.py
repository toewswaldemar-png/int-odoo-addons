import os
import shutil
import tempfile
from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError
from odoo.tests.common import HttpCase, TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestSharingAcl(TransactionCase):
    """Phase 5, 'intern': Portal-Zweig der Read-Regel (shared_partner_ids) -
    komplett getrennt vom internen Schutzordner-Zweig aus Phase 2."""

    def setUp(self):
        super().setUp()
        self.Model = self.env["int_filemanager.file"].sudo()

    def _make_file(self, path):
        return self.Model.create({"name": os.path.basename(path), "path": path, "is_dir": False})

    def _make_portal_user(self, login):
        partner = self.env["res.partner"].sudo().create({"name": login})
        portal_group = self.env.ref("base.group_portal")
        user = (
            self.env["res.users"]
            .sudo()
            .create(
                {
                    "name": login,
                    "login": login,
                    "partner_id": partner.id,
                    "group_ids": [(6, 0, [portal_group.id])],
                }
            )
        )
        return user

    def test_portal_user_sees_only_shared_file(self):
        shared = self._make_file("geteilt.txt")
        other = self._make_file("nicht_geteilt.txt")
        portal_user = self._make_portal_user("portal_share_1")
        shared.shared_partner_ids = [(4, portal_user.partner_id.id)]

        File = self.env["int_filemanager.file"].with_user(portal_user)
        self.assertTrue(File.search([("path", "=", "geteilt.txt")]))
        self.assertFalse(File.search([("path", "=", "nicht_geteilt.txt")]))
        # Sanity: "other" existiert wirklich (kein falsch-positiver Test durch einen Tippfehler).
        self.assertTrue(other.exists())

    def test_portal_user_ignores_internal_protected_folder_groups(self):
        """Portal-Zweig ist EIGENSTAENDIG - eine Schutzordner-Gruppe, die ein
        interner Nutzer haette, darf einem Portal-Nutzer nichts nuetzen (er
        hat nie eine solche Gruppe), und umgekehrt darf shared_partner_ids
        einem internen Nutzer nichts nuetzen (Portal-Zweig wird nur bei
        has_group('base.group_portal') ueberhaupt ausgewertet)."""
        internal_group = self.env["res.groups"].sudo().create({"name": "FM Interne Gruppe Share-Test"})
        self.env["int_filemanager.protected_folder"].sudo().create(
            {"path": "Geschuetzt10", "read_group_ids": [(4, internal_group.id)]}
        )
        protected_file = self._make_file("Geschuetzt10/geheim.txt")
        portal_user = self._make_portal_user("portal_share_2")
        # Portal-Nutzer OHNE shared_partner_ids UND ohne die interne Gruppe -> unsichtbar.
        File = self.env["int_filemanager.file"].with_user(portal_user)
        self.assertFalse(File.search([("path", "=", "Geschuetzt10/geheim.txt")]))

        unshared = self._make_file("nicht_freigegeben.txt")
        internal_user = (
            self.env["res.users"]
            .sudo()
            .create(
                {
                    "name": "InternerNutzer",
                    "login": "internal_share_test",
                    "group_ids": [(6, 0, [self.env.ref("int_filemanager.group_filemanager_user").id])],
                }
            )
        )
        unshared.shared_partner_ids = [(4, portal_user.partner_id.id)]
        # shared_partner_ids nuetzt einem INTERNEN Nutzer nichts - er ist
        # kein Portal-Nutzer, der Portal-Zweig wird fuer ihn nie ausgewertet,
        # nur der normale interne (Schutzordner-)Zweig gilt.
        File_internal = self.env["int_filemanager.file"].with_user(internal_user)
        self.assertTrue(File_internal.search([("path", "=", "nicht_freigegeben.txt")]))

    def test_portal_access_requires_model_access_row(self):
        """Bestätigt, dass die neue ir.model.access-Zeile tatsächlich
        notwendig ist (Odoos ir.model.access ist default-deny pro Modell,
        unabhängig von jeder ir.rule) - ohne sie wäre ein Portal-Nutzer
        trotz shared_partner_ids komplett ausgesperrt."""
        shared = self._make_file("geteilt2.txt")
        portal_user = self._make_portal_user("portal_share_3")
        shared.shared_partner_ids = [(4, portal_user.partner_id.id)]

        access = self.env.ref("int_filemanager.access_int_filemanager_file_portal")
        access.sudo().active = False
        try:
            with self.assertRaises(AccessError):
                self.env["int_filemanager.file"].with_user(portal_user).search(
                    [("path", "=", "geteilt2.txt")]
                )
        finally:
            access.sudo().active = True

    def test_admin_bypass_unaffected_by_portal_branch(self):
        self._make_file("admin_sichtbar.txt")
        admin_user = (
            self.env["res.users"]
            .sudo()
            .create(
                {
                    "name": "AdminShareTest",
                    "login": "admin_share_test",
                    "group_ids": [(6, 0, [self.env.ref("int_filemanager.group_filemanager_admin").id])],
                }
            )
        )
        File = self.env["int_filemanager.file"].with_user(admin_user)
        self.assertTrue(File.search([("path", "=", "admin_sichtbar.txt")]))


@tagged("post_install", "-at_install")
class TestShareToken(TransactionCase):
    """Phase 5, 'extern': anonymer Freigabe-Link (share_token/share_expires_at)."""

    def setUp(self):
        super().setUp()
        self.Model = self.env["int_filemanager.file"].sudo()
        self.file = self.Model.create({"name": "extern.txt", "path": "extern.txt", "is_dir": False})

    def test_generate_sets_token_and_expiry_and_logs(self):
        self.file.action_generate_share_token()
        self.assertTrue(self.file.share_token)
        self.assertTrue(self.file.share_expires_at)
        self.assertTrue(self.file.share_expires_at > fields.Datetime.now())
        log = self.env["int_filemanager.share_log"].sudo().search([("file_id", "=", self.file.id)])
        self.assertEqual(log.event_type, "created")

    def test_generate_rejects_folders(self):
        folder = self.Model.create({"name": "Ordner", "path": "Ordner", "is_dir": True})
        with self.assertRaises(Exception):
            folder.action_generate_share_token()

    def test_regenerate_rotates_token(self):
        self.file.action_generate_share_token()
        first_token = self.file.share_token
        self.file.action_generate_share_token()
        self.assertNotEqual(self.file.share_token, first_token)

    def test_revoke_clears_token_and_expiry_and_logs(self):
        self.file.action_generate_share_token()
        self.file.action_revoke_share_token()
        self.assertFalse(self.file.share_token)
        self.assertFalse(self.file.share_expires_at)
        events = self.env["int_filemanager.share_log"].sudo().search([("file_id", "=", self.file.id)]).mapped(
            "event_type"
        )
        self.assertEqual(events, ["revoked", "created"])

    def test_revoke_without_active_token_does_not_log(self):
        self.file.action_revoke_share_token()
        self.assertFalse(
            self.env["int_filemanager.share_log"].sudo().search_count([("file_id", "=", self.file.id)])
        )

    def test_share_log_survives_file_deletion(self):
        self.file.action_generate_share_token()
        path_snapshot, filename_snapshot = self.file.path, self.file.name
        self.file.unlink()
        log = self.env["int_filemanager.share_log"].sudo().search([("path", "=", path_snapshot)])
        self.assertTrue(log)
        self.assertFalse(log.file_id)
        self.assertEqual(log.path, path_snapshot)
        self.assertEqual(log.filename, filename_snapshot)

    def test_share_url_computed_from_base_url(self):
        self.env["ir.config_parameter"].sudo().set_param("web.base.url", "https://hm-srv.example")
        self.file.action_generate_share_token()
        self.assertEqual(self.file.share_url, "https://hm-srv.example/int_filemanager/share/%s" % self.file.share_token)
        self.file.action_revoke_share_token()
        self.assertFalse(self.file.share_url)


@tagged("post_install", "-at_install")
class TestShareHttp(HttpCase):
    """Öffentliche Link-Route - bewusst ohne Login (auth='public')."""

    def setUp(self):
        super().setUp()
        self.root = os.path.realpath(tempfile.mkdtemp(prefix="int_filemanager_share_http_"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.env["ir.config_parameter"].sudo().set_param("int_filemanager.root_path", self.root)
        self.env.cr.commit = lambda: None

        with open(os.path.join(self.root, "share_me.txt"), "wb") as f:
            f.write(b"share content")
        self.env["int_filemanager.file"].sudo()._scan_and_reconcile()
        self.file = self.env["int_filemanager.file"].sudo().search([("path", "=", "share_me.txt")])

    def test_unknown_token_returns_404(self):
        resp = self.url_open("/int_filemanager/share/does-not-exist")
        self.assertEqual(resp.status_code, 404)

    def test_valid_token_downloads_with_attachment_disposition(self):
        self.file.action_generate_share_token()
        resp = self.url_open("/int_filemanager/share/%s" % self.file.share_token)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content, b"share content")
        self.assertIn("attachment", resp.headers.get("Content-Disposition", ""))
        self.assertIn("no-store", resp.headers.get("Cache-Control", ""))
        log = self.env["int_filemanager.share_log"].sudo().search(
            [("file_id", "=", self.file.id), ("event_type", "=", "downloaded")]
        )
        self.assertTrue(log)

    def test_expired_token_returns_404(self):
        self.file.action_generate_share_token()
        self.file.sudo().share_expires_at = fields.Datetime.now() - timedelta(days=1)
        resp = self.url_open("/int_filemanager/share/%s" % self.file.share_token)
        self.assertEqual(resp.status_code, 404)

    def test_revoked_token_returns_404(self):
        self.file.action_generate_share_token()
        token = self.file.share_token
        self.file.action_revoke_share_token()
        resp = self.url_open("/int_filemanager/share/%s" % token)
        self.assertEqual(resp.status_code, 404)


@tagged("post_install", "-at_install")
class TestPortalHttp(HttpCase):
    """Portal-Route /my/shared_files/<id>/download - echter eingeloggter
    Portal-Nutzer, nicht nur ORM-Ebene."""

    def setUp(self):
        super().setUp()
        self.root = os.path.realpath(tempfile.mkdtemp(prefix="int_filemanager_portal_http_"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.env["ir.config_parameter"].sudo().set_param("int_filemanager.root_path", self.root)
        self.env.cr.commit = lambda: None

        with open(os.path.join(self.root, "portal_a.txt"), "wb") as f:
            f.write(b"portal content a")
        with open(os.path.join(self.root, "portal_b.txt"), "wb") as f:
            f.write(b"portal content b")
        self.env["int_filemanager.file"].sudo()._scan_and_reconcile()
        self.file_a = self.env["int_filemanager.file"].sudo().search([("path", "=", "portal_a.txt")])
        self.file_b = self.env["int_filemanager.file"].sudo().search([("path", "=", "portal_b.txt")])

        partner = self.env["res.partner"].sudo().create({"name": "portal_http_user"})
        self.portal_user = self.env["res.users"].sudo().create(
            {
                "name": "portal_http_user",
                "login": "portal_http_user",
                "password": "portal_http_pw",
                "partner_id": partner.id,
                "group_ids": [(6, 0, [self.env.ref("base.group_portal").id])],
            }
        )
        self.file_a.sudo().shared_partner_ids = [(4, self.portal_user.partner_id.id)]

    def test_download_shared_file_succeeds(self):
        self.authenticate("portal_http_user", "portal_http_pw")
        resp = self.url_open("/my/shared_files/%d/download" % self.file_a.id)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content, b"portal content a")

    def test_download_unshared_file_denied(self):
        self.authenticate("portal_http_user", "portal_http_pw")
        resp = self.url_open("/my/shared_files/%d/download" % self.file_b.id)
        self.assertNotEqual(resp.status_code, 200)

    def test_shared_files_page_lists_only_shared(self):
        self.authenticate("portal_http_user", "portal_http_pw")
        resp = self.url_open("/my/shared_files")
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode("utf-8")
        self.assertIn("portal_a.txt", body)
        self.assertNotIn("portal_b.txt", body)
