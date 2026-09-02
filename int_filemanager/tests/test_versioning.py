import base64
import os
import shutil
import tempfile
import threading
import time

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestFileWriteLock(TransactionCase):
    """Testet _file_write_lock isoliert von HTTP/ORM: ein willkürlicher,
    garantiert unbenutzter Integer-Key statt eines echten file_id - braucht
    dadurch keine über die Testtransaktion hinaus committeten Daten (siehe
    Kommentar in test_versioning_http.py, warum ein End-to-End-Test über
    zwei parallele HTTP-Requests an Odoos eigener Test-Request-Serialisierung
    scheitert). Das ist genau der Nebenläufigkeitsfehler aus Runde 4: eine
    transaktionsgebundene Sperre gäbe die Sperre schon beim Commit des
    Snapshot-Schritts frei, lange bevor der eigentliche Schreibvorgang fertig
    ist - dieser Test beweist, dass die Session-Sperre das nicht tut."""

    def test_serializes_concurrent_holders(self):
        from odoo.addons.int_filemanager import write_service

        dbname = self.env.cr.dbname
        lock_key = 999999001
        events = []

        def _holder(label, hold_seconds):
            with write_service._file_write_lock(dbname, lock_key):
                events.append(("acquired", label))
                time.sleep(hold_seconds)
                events.append(("released", label))

        t1 = threading.Thread(target=_holder, args=("a", 0.5))
        t2 = threading.Thread(target=_holder, args=("b", 0.0))
        t1.start()
        time.sleep(0.1)  # sicherstellen, dass t1 den Lock zuerst haelt
        t2.start()
        t1.join(timeout=10)
        t2.join(timeout=10)

        self.assertEqual(
            events,
            [("acquired", "a"), ("released", "a"), ("acquired", "b"), ("released", "b")],
            "t2 durfte den Lock erst NACH t1s Freigabe bekommen - beide gleichzeitig "
            "haltend wäre exakt die in Runde 4 gefundene Race Condition.",
        )


@tagged("post_install", "-at_install")
class TestVersioningModel(TransactionCase):
    """Phase 3: reine Modell-/Größengrenzen-Logik, die keine über
    write_service.py's eigene DB-Verbindungen laufenden Schritte berührt
    (diese brauchen bereits committete Daten - siehe test_versioning_http.py
    für den vollständigen, HTTP-getriebenen Ablauf)."""

    def test_identical_content_shares_filestore_blob(self):
        file_rec = self.env["int_filemanager.file"].sudo().create(
            {"name": "d.txt", "path": "d.txt", "is_dir": False}
        )
        content = base64.b64encode(b"identical content")
        v1 = self.env["int_filemanager.version"].sudo().create(
            {"file_id": file_rec.id, "version_no": 1, "content": content, "size": 18}
        )
        v2 = self.env["int_filemanager.version"].sudo().create(
            {"file_id": file_rec.id, "version_no": 2, "content": content, "size": 18}
        )
        Attachment = self.env["ir.attachment"].sudo()
        att1 = Attachment.search(
            [("res_model", "=", "int_filemanager.version"), ("res_id", "=", v1.id), ("res_field", "=", "content")],
            limit=1,
        )
        att2 = Attachment.search(
            [("res_model", "=", "int_filemanager.version"), ("res_id", "=", v2.id), ("res_field", "=", "content")],
            limit=1,
        )
        self.assertTrue(att1 and att2)
        self.assertEqual(att1.store_fname, att2.store_fname)

    def test_version_no_unique_per_file(self):
        file_rec = self.env["int_filemanager.file"].sudo().create(
            {"name": "e.txt", "path": "e.txt", "is_dir": False}
        )
        self.env["int_filemanager.version"].sudo().create(
            {"file_id": file_rec.id, "version_no": 1, "content": base64.b64encode(b"a"), "size": 1}
        )
        with self.assertRaises(Exception):
            self.env["int_filemanager.version"].sudo().create(
                {"file_id": file_rec.id, "version_no": 1, "content": base64.b64encode(b"b"), "size": 1}
            )

    def test_new_content_over_limit_rejected(self):
        from odoo.addons.int_filemanager import write_service

        self.env["ir.config_parameter"].sudo().set_param("int_filemanager.version_max_size_mb", "1")
        file_rec = self.env["int_filemanager.file"].sudo().create(
            {"name": "big.txt", "path": "big.txt", "is_dir": False}
        )
        with self.assertRaises(UserError):
            write_service.snapshot_and_write(
                self.env, file_rec, b"x" * (2 * 1024 * 1024), operation="upload_overwrite"
            )

    def test_existing_file_over_limit_rejected(self):
        from odoo.addons.int_filemanager import write_service

        root = os.path.realpath(tempfile.mkdtemp(prefix="int_filemanager_size_test_"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        self.env["ir.config_parameter"].sudo().set_param("int_filemanager.root_path", root)
        self.env["ir.config_parameter"].sudo().set_param("int_filemanager.version_max_size_mb", "1")
        with open(os.path.join(root, "big.txt"), "wb") as f:
            f.write(b"x" * (2 * 1024 * 1024))
        file_rec = self.env["int_filemanager.file"].sudo().create(
            {"name": "big.txt", "path": "big.txt", "is_dir": False}
        )
        with self.assertRaises(UserError):
            write_service.snapshot_and_write(self.env, file_rec, b"small", operation="upload_overwrite")

    def test_prune_keeps_only_configured_count(self):
        file_rec = self.env["int_filemanager.file"].sudo().create(
            {"name": "f.txt", "path": "f.txt", "is_dir": False}
        )
        Version = self.env["int_filemanager.version"].sudo()
        for i in range(1, 6):
            Version.create(
                {"file_id": file_rec.id, "version_no": i, "content": base64.b64encode(b"x" * i), "size": i}
            )
        self.env["ir.config_parameter"].sudo().set_param("int_filemanager.version_keep_count", "2")
        Version._cron_prune_old_versions()
        remaining = Version.search([("file_id", "=", file_rec.id)], order="version_no")
        self.assertEqual(remaining.mapped("version_no"), [4, 5])

    def test_prune_default_unbounded(self):
        file_rec = self.env["int_filemanager.file"].sudo().create(
            {"name": "g.txt", "path": "g.txt", "is_dir": False}
        )
        Version = self.env["int_filemanager.version"].sudo()
        for i in range(1, 4):
            Version.create(
                {"file_id": file_rec.id, "version_no": i, "content": base64.b64encode(b"x" * i), "size": i}
            )
        # kein version_keep_count gesetzt -> Default 0 = unbegrenzt, kein Löschen
        Version._cron_prune_old_versions()
        remaining = Version.search([("file_id", "=", file_rec.id)])
        self.assertEqual(len(remaining), 3)
