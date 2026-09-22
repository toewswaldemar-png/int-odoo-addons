import base64
import os
import shutil
import tempfile

from odoo.tests.common import HttpCase, tagged


@tagged("post_install", "-at_install")
class TestVersioningHttp(HttpCase):
    """write_service.snapshot_and_write() committet über eigene, von Odoos
    Test-Transaktion unabhängige DB-Verbindungen (Journal + Session-Lock).
    self.env.cr selbst darf innerhalb eines Tests NICHT committen (TransactionCase
    verbietet das - "Cannot commit or rollback a cursor from inside a test"),
    das gilt auch für HttpCase. _scan_and_reconcile() committet intern
    batchweise - wie in test_scan_identity.py wird das für die Testdauer
    neutralisiert. Für die separat (über write_service) committeten Daten
    reicht danach ein reines Cache-Invalidieren (env.cr.clear()): dieselbe
    Transaktion sieht unter PostgreSQLs Standard-Isolationsstufe READ COMMITTED
    zwischenzeitlich commitete Daten anderer Verbindungen automatisch bei der
    nächsten Abfrage, ganz ohne einen eigenen (verbotenen) Commit."""

    def setUp(self):
        super().setUp()
        self.root = os.path.realpath(tempfile.mkdtemp(prefix="int_filemanager_ver_http_"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.env["ir.config_parameter"].sudo().set_param("int_filemanager.root_path", self.root)
        self.env.cr.commit = lambda: None

        base_group = self.env.ref("int_filemanager.group_filemanager_user")
        self.env["res.users"].sudo().create(
            {
                "name": "VersionTester",
                "login": "ver_test_user",
                "group_ids": [(6, 0, [base_group.id])],
            }
        )

        with open(os.path.join(self.root, "doc.txt"), "wb") as f:
            f.write(b"version1")
        self.env["int_filemanager.file"].sudo()._scan_and_reconcile()

    def _authenticate(self):
        self.authenticate("ver_test_user", "irrelevant")

    def _rpc(self, route, params):
        return self.url_open(
            route, data=None, json={"jsonrpc": "2.0", "method": "call", "params": params, "id": 1}
        )

    def _upload_overwrite(self, filename, content):
        return self.url_open("/int_filemanager/upload", data={"path": ""}, files={"ufile": (filename, content)})

    def test_upload_overwrite_creates_version_and_writes_atomically(self):
        self._authenticate()
        resp = self._upload_overwrite("doc.txt", b"version2")
        self.assertEqual(resp.status_code, 200)

        self.env.cr.clear()
        file_record = self.env["int_filemanager.file"].sudo().search([("path", "=", "doc.txt")])
        self.assertTrue(file_record)
        versions = self.env["int_filemanager.version"].sudo().search([("file_id", "=", file_record.id)])
        self.assertEqual(len(versions), 1)
        self.assertEqual(base64.b64decode(versions.content), b"version1")
        with open(os.path.join(self.root, "doc.txt"), "rb") as f:
            self.assertEqual(f.read(), b"version2")

    def test_upload_overwrite_identical_content_skips_version(self):
        """Byteidentischer Inhalt (z.B. ONLYOFFICE-Editor nur geoeffnet, nichts
        bearbeitet) darf keine neue Version anlegen - siehe
        docs/int_filemanager_onlyoffice_ladezeit_untersuchung_2026-09-22.md."""
        self._authenticate()
        resp = self._upload_overwrite("doc.txt", b"version1")
        self.assertEqual(resp.status_code, 200)

        self.env.cr.clear()
        file_record = self.env["int_filemanager.file"].sudo().search([("path", "=", "doc.txt")])
        versions = self.env["int_filemanager.version"].sudo().search([("file_id", "=", file_record.id)])
        self.assertEqual(len(versions), 0)
        with open(os.path.join(self.root, "doc.txt"), "rb") as f:
            self.assertEqual(f.read(), b"version1")

    def test_restore_creates_new_version_and_restores_content(self):
        self._authenticate()
        self._upload_overwrite("doc.txt", b"version2")
        self.env.cr.clear()

        file_record = self.env["int_filemanager.file"].sudo().search([("path", "=", "doc.txt")])
        v1 = self.env["int_filemanager.version"].sudo().search([("file_id", "=", file_record.id)], limit=1)
        self.assertTrue(v1)

        resp = self._rpc("/int_filemanager/version_restore", {"version_id": v1.id})
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertTrue(payload["result"]["ok"])

        self.env.cr.clear()
        with open(os.path.join(self.root, "doc.txt"), "rb") as f:
            self.assertEqual(f.read(), b"version1")
        versions_after = self.env["int_filemanager.version"].sudo().search([("file_id", "=", file_record.id)])
        # v1 (Snapshot von "version1") + neuer Snapshot des Stands direkt vor
        # dem Restore ("version2") - Restore ist selbst wieder undo-sicher.
        self.assertEqual(len(versions_after), 2)
        self.assertIn(b"version2", [base64.b64decode(v.content) for v in versions_after])

    def test_restore_rejects_unauthorized_version(self):
        read_group = self.env["res.groups"].sudo().create({"name": "FM Version Leser"})
        self.env["int_filemanager.protected_folder"].sudo().create(
            {"path": "Geheim", "read_group_ids": [(4, read_group.id)]}
        )
        os.makedirs(os.path.join(self.root, "Geheim"))
        with open(os.path.join(self.root, "Geheim", "s.txt"), "wb") as f:
            f.write(b"secret-v1")
        self.env["int_filemanager.file"].sudo()._scan_and_reconcile()

        admin_group = self.env.ref("int_filemanager.group_filemanager_admin")
        self.env["res.users"].sudo().create(
            {
                "name": "VersionAdmin",
                "login": "ver_test_admin",
                "group_ids": [(6, 0, [admin_group.id])],
            }
        )
        self.env.cr.clear()

        self.authenticate("ver_test_admin", "irrelevant")
        resp = self.url_open(
            "/int_filemanager/upload", data={"path": "Geheim"}, files={"ufile": ("s.txt", b"secret-v2")}
        )
        self.assertEqual(resp.status_code, 200)
        self.env.cr.clear()

        file_record = self.env["int_filemanager.file"].sudo().search([("path", "=", "Geheim/s.txt")])
        version = self.env["int_filemanager.version"].sudo().search([("file_id", "=", file_record.id)], limit=1)
        self.assertTrue(version)

        # Outsider ohne die Leser-Gruppe versucht, dieselbe version_id zu restaurieren.
        self.authenticate("ver_test_user", "irrelevant")
        resp = self._rpc("/int_filemanager/version_restore", {"version_id": version.id})
        payload = resp.json()
        self.assertIn("error", payload)

    # Eine echte end-to-end-Nebenläufigkeitsprüfung über zwei parallele
    # url_open()-Aufrufe wurde versucht und wieder verworfen: Odoos eigenes
    # HttpCase serialisiert Test-Requests intern über einen
    # allow_requests()-Kontextmanager - ein zweiter, während des ersten noch
    # laufender Request blockiert dort dauerhaft, unabhängig vom eigentlich zu
    # testenden Code. Der eigentliche Sperrmechanismus (_file_write_lock) wird
    # deshalb isoliert direkt getestet, siehe
    # TestFileWriteLock.test_serializes_concurrent_holders in test_versioning.py.
