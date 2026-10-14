import hashlib
import io
import os
import resource
import threading
import time

import psycopg2.errors

from odoo.sql_db import db_connect
from odoo.tests.common import TransactionCase, new_test_user, tagged
from odoo.tools import SQL

from odoo.addons.int_filemanager.models.int_filemanager_document import BLOB_LOCK_NAME

PNG_HEAD = b"\x89PNG\r\n\x1a\n" + b"\0" * 50
ZIP_HEAD = b"PK\x03\x04" + b"\0" * 50
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


class BrokenStream:
    """Delivers one block, then fails."""

    def __init__(self):
        self.delivered = False

    def read(self, size):
        if self.delivered:
            raise OSError("connection lost")
        self.delivered = True
        return b"x" * 10


class ZeroStream:
    """``size`` bytes of zeros, never held in memory as a whole."""

    def __init__(self, size):
        self.left = size

    def read(self, size):
        size = min(size, self.left)
        self.left -= size
        return bytes(size)


def remove(path):
    if os.path.exists(path):
        os.unlink(path)


@tagged("post_install", "-at_install")
class TestDocumentStorage(TransactionCase):
    """The file side of the own storage: temporary file, measuring, blob."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Document = cls.env["int.filemanager.document"]

    def _store(self, content=b"hello", name="a.txt", mimetype=None, env=None):
        Document = (env or self.env)["int.filemanager.document"]
        stored = Document._store_stream(io.BytesIO(content), name, mimetype)
        self.addCleanup(remove, stored["tmp_path"])
        self.addCleanup(remove, Document._blob_path(stored["checksum"]))
        return stored

    def test_a_stream_is_measured_and_written_to_a_temporary_file(self):
        stored = self._store(b"hello", "a.txt")
        self.assertEqual(stored["checksum"], hashlib.sha256(b"hello").hexdigest())
        self.assertEqual(stored["size"], 5)
        self.assertEqual(stored["mimetype"], "text/plain")
        with open(stored["tmp_path"], "rb") as tmp:
            self.assertEqual(tmp.read(), b"hello")
        self.assertFalse(os.path.exists(self.Document._blob_path(stored["checksum"])))

    def test_the_temporary_file_lies_in_the_upload_folder_next_to_the_blobs(self):
        stored = self._store()
        blob = self.Document._blob_path(stored["checksum"])
        root = os.path.dirname(os.path.dirname(blob))
        self.assertEqual(os.path.dirname(stored["tmp_path"]), os.path.join(root, ".upload"))
        self.assertEqual(os.path.basename(root), "int_filemanager")

    def test_publishing_moves_the_temporary_file_to_the_blob(self):
        stored = self._store(b"hello")
        self.Document._publish_blob(stored["tmp_path"], stored["checksum"])
        blob = self.Document._blob_path(stored["checksum"])
        with open(blob, "rb") as published:
            self.assertEqual(published.read(), b"hello")
        self.assertFalse(os.path.exists(stored["tmp_path"]))
        self.assertEqual(
            blob.split(os.sep)[-3:],
            ["int_filemanager", stored["checksum"][:2], stored["checksum"]],
        )

    def test_the_same_content_is_kept_once(self):
        first = self._store(b"same")
        self.Document._publish_blob(first["tmp_path"], first["checksum"])
        blob = self.Document._blob_path(first["checksum"])
        inode = os.stat(blob).st_ino
        second = self._store(b"same", "b.txt")
        self.Document._publish_blob(second["tmp_path"], second["checksum"])
        self.assertEqual(os.stat(blob).st_ino, inode)
        self.assertFalse(os.path.exists(second["tmp_path"]))

    def test_a_second_publisher_waits_for_the_first_and_does_not_replace_its_blob(self):
        stored = self._store(b"same", "a.txt")
        checksum = stored["checksum"]
        blob = self.Document._blob_path(checksum)
        errors = []

        def publish():
            try:
                self.Document._publish_blob(stored["tmp_path"], checksum)
            except Exception as error:  # noqa: BLE001 (reported by the test thread below)
                errors.append(error)

        with db_connect(self.env.cr.dbname).cursor() as first:
            # The first publisher holds the lock of this checksum.
            first.execute(
                SQL(
                    "SELECT pg_advisory_xact_lock(hashtext(%s), hashtext(%s))",
                    BLOB_LOCK_NAME,
                    checksum,
                )
            )
            thread = threading.Thread(target=publish)
            thread.start()
            for _attempt in range(100):
                first.execute("SELECT count(*) FROM pg_locks WHERE locktype = 'advisory' AND NOT granted")
                if first.fetchone()[0]:
                    break
                time.sleep(0.05)
            else:
                self.fail("The second publisher did not wait for the lock.")
            self.assertTrue(thread.is_alive())
            self.assertTrue(os.path.exists(stored["tmp_path"]))
            # The first publisher places the blob and ends its transaction (leaving the block).
            os.makedirs(os.path.dirname(blob), exist_ok=True)
            with open(blob, "wb") as placed:
                placed.write(b"same")
            inode = os.stat(blob).st_ino
        thread.join(timeout=10)
        self.assertFalse(thread.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(os.stat(blob).st_ino, inode)
        self.assertFalse(os.path.exists(stored["tmp_path"]))

    def test_publishing_a_blob_that_exists_takes_no_lock(self):
        second = self._store(b"same", "b.txt")
        blob = self.Document._blob_path(second["checksum"])
        os.makedirs(os.path.dirname(blob), exist_ok=True)
        with open(blob, "wb") as placed:
            placed.write(b"same")
        with db_connect(self.env.cr.dbname).cursor() as other:
            other.execute(
                SQL(
                    "SELECT pg_advisory_xact_lock(hashtext(%s), hashtext(%s))",
                    BLOB_LOCK_NAME,
                    second["checksum"],
                )
            )
            self.env.cr.execute("SET LOCAL lock_timeout TO '100ms'")
            self.Document._publish_blob(second["tmp_path"], second["checksum"])
        self.assertFalse(os.path.exists(second["tmp_path"]))

    def test_a_publisher_that_cannot_get_the_lock_leaves_blob_and_file_alone(self):
        stored = self._store(b"new")
        with db_connect(self.env.cr.dbname).cursor() as other:
            other.execute(
                SQL(
                    "SELECT pg_advisory_xact_lock(hashtext(%s), hashtext(%s))",
                    BLOB_LOCK_NAME,
                    stored["checksum"],
                )
            )
            self.env.cr.execute("SAVEPOINT publish_test")
            self.env.cr.execute("SET LOCAL lock_timeout TO '100ms'")
            with self.assertRaises(psycopg2.errors.LockNotAvailable):
                self.Document._publish_blob(stored["tmp_path"], stored["checksum"])
            self.env.cr.execute("ROLLBACK TO SAVEPOINT publish_test")
        self.assertTrue(os.path.exists(stored["tmp_path"]))
        self.assertFalse(os.path.exists(self.Document._blob_path(stored["checksum"])))

    def test_a_failing_stream_leaves_no_temporary_file(self):
        upload_dir = os.path.dirname(self._store()["tmp_path"])
        before = set(os.listdir(upload_dir))
        with self.assertRaises(OSError):
            self.Document._store_stream(BrokenStream(), "a.txt")
        self.assertEqual(set(os.listdir(upload_dir)), before)

    def test_a_rollback_removes_the_temporary_file(self):
        stored = self._store()
        self.assertTrue(os.path.exists(stored["tmp_path"]))
        self.env.cr.postrollback.run()
        self.assertFalse(os.path.exists(stored["tmp_path"]))

    def test_a_blob_path_needs_a_sha256(self):
        for bad in ("", None, "../../etc/passwd", "a" * 63, "A" * 64, "g" * 64, "a" * 64 + "/"):
            with self.subTest(checksum=bad), self.assertRaises(ValueError):
                self.Document._blob_path(bad)
        self.assertTrue(self.Document._blob_path("a" * 64).endswith(f"/aa/{'a' * 64}"))

    def test_the_type_follows_the_core_rules(self):
        cases = [
            # (name, client type, head, expected type)
            ("a.pdf", None, b"", "application/pdf"),
            ("a.pdf", "application/pdf", b"%PDF", "application/pdf"),
            ("a.docx", None, b"PK", DOCX),
            ("a.docx", DOCX, ZIP_HEAD, DOCX),
            ("noextension", None, PNG_HEAD, "image/png"),
            ("noextension", None, ZIP_HEAD, "application/zip"),
            ("unknown.zzz", None, b"", "application/octet-stream"),
            ("empty.txt", None, b"", "text/plain"),
            ("page.html", "text/html", b"<html>", "text/plain"),
            ("page.htm", None, b"<html>", "text/plain"),
            ("drawing.svg", "image/svg+xml", b"<svg>", "text/plain"),
            ("data.xml", "application/xml", b"<a/>", "text/plain"),
        ]
        for name, client_type, head, expected in cases:
            with self.subTest(name=name, client_type=client_type):
                stored = self._store(head, name, client_type)
                self.assertEqual(stored["mimetype"], expected)

    def test_html_becomes_plain_text_for_an_administrator_too(self):
        admin = new_test_user(self.env, login="storage_admin", groups="base.group_system")
        stored = self._store(b"<html>", "page.html", "text/html", env=self.env(user=admin))
        self.assertEqual(stored["mimetype"], "text/plain")


@tagged("post_install", "-at_install", "-standard", "int_filemanager_big")
class TestDocumentStorageBig(TransactionCase):
    """Run on demand: ``--test-tags int_filemanager_big``. Needs 2.5 GiB of disk space."""

    def test_a_file_above_2_gib_is_streamed_without_holding_it_in_memory(self):
        size = 2560 * 1024 * 1024
        Document = self.env["int.filemanager.document"]
        block = bytes(1024 * 1024)
        digest = hashlib.sha256()
        for _ in range(size // len(block)):
            digest.update(block)
        before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss  # KiB on Linux
        stored = Document._store_stream(ZeroStream(size), "big.bin")
        self.addCleanup(remove, stored["tmp_path"])
        grown_mib = (resource.getrusage(resource.RUSAGE_SELF).ru_maxrss - before) / 1024
        self.assertEqual(stored["size"], size)
        self.assertEqual(stored["checksum"], digest.hexdigest())
        self.assertEqual(os.path.getsize(stored["tmp_path"]), size)
        self.assertLess(grown_mib, 200)
