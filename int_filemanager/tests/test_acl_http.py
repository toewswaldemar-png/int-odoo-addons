import os
import shutil
import tempfile

from odoo.tests.common import HttpCase, tagged


@tagged("post_install", "-at_install")
class TestAclHttp(HttpCase):
    """Phase 2: echte HTTP-Requests gegen download/tree - TransactionCase
    allein prüft nur die ORM-Ebene, nicht die tatsächliche Controller-Route
    (z.B. ob tree_dir wirklich über die ORM statt os.scandir läuft)."""

    def setUp(self):
        super().setUp()
        self.root = os.path.realpath(tempfile.mkdtemp(prefix="int_filemanager_http_test_"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.env["ir.config_parameter"].sudo().set_param("int_filemanager.root_path", self.root)
        self.env.cr.commit = lambda: None

        self.read_group = self.env["res.groups"].sudo().create({"name": "FM HTTP Leser"})
        self.env["int_filemanager.protected_folder"].sudo().create(
            {"path": "Geheim", "read_group_ids": [(4, self.read_group.id)]}
        )

        base_group = self.env.ref("int_filemanager.group_filemanager_user")
        self.outsider = self.env["res.users"].sudo().create(
            {
                "name": "HttpOutsider",
                "login": "acl_http_outsider",
                "group_ids": [(6, 0, [base_group.id])],
            }
        )
        self.reader = self.env["res.users"].sudo().create(
            {
                "name": "HttpReader",
                "login": "acl_http_reader",
                "group_ids": [(6, 0, [base_group.id, self.read_group.id])],
            }
        )

        os.makedirs(os.path.join(self.root, "Geheim"))
        with open(os.path.join(self.root, "Geheim", "geheim.txt"), "wb") as f:
            f.write(b"top secret")
        os.makedirs(os.path.join(self.root, "Offen"))
        with open(os.path.join(self.root, "Offen", "hallo.txt"), "wb") as f:
            f.write(b"hallo welt")

        self.env["int_filemanager.file"].sudo()._scan_and_reconcile()

    def _rpc(self, route, params):
        return self.url_open(
            route,
            data=None,
            json={"jsonrpc": "2.0", "method": "call", "params": params, "id": 1},
        )

    def test_download_denied_without_group(self):
        self.authenticate("acl_http_outsider", "irrelevant")
        resp = self.url_open("/int_filemanager/download?path=Geheim/geheim.txt")
        self.assertNotEqual(resp.status_code, 200)

    def test_download_allowed_with_group(self):
        self.authenticate("acl_http_reader", "irrelevant")
        resp = self.url_open("/int_filemanager/download?path=Geheim/geheim.txt")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content, b"top secret")

    def test_download_unprotected_open_to_outsider(self):
        self.authenticate("acl_http_outsider", "irrelevant")
        resp = self.url_open("/int_filemanager/download?path=Offen/hallo.txt")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content, b"hallo welt")

    def test_tree_hides_protected_folder_name(self):
        self.authenticate("acl_http_outsider", "irrelevant")
        resp = self._rpc("/int_filemanager/tree", {"path": ""})
        payload = resp.json()
        names = [c["name"] for c in payload["result"]["children"]]
        self.assertIn("Offen", names)
        self.assertNotIn("Geheim", names)

    def test_tree_shows_protected_folder_name_with_group(self):
        self.authenticate("acl_http_reader", "irrelevant")
        resp = self._rpc("/int_filemanager/tree", {"path": ""})
        payload = resp.json()
        names = [c["name"] for c in payload["result"]["children"]]
        self.assertIn("Geheim", names)
