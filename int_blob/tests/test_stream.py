"""``_create_from_stream``: the claims of the README, one test each."""

import base64
import contextlib
import hashlib
import inspect
import io
import os
import threading
import time
from unittest.mock import patch

from odoo import models
from odoo.exceptions import AccessError, UserError
from odoo.tests.common import HttpCase, TransactionCase, new_test_user, tagged

from odoo.addons.base.models.ir_autovacuum import is_autovacuum
from odoo.addons.int_blob.models import ir_attachment as blob

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)
MIB = 1024 * 1024


def remove(path):
    with contextlib.suppress(FileNotFoundError):
        os.unlink(path)


def resident_memory():
    """The resident memory of this process in bytes (Linux)."""
    with open("/proc/self/statm", encoding="utf-8") as statm:
        return int(statm.read().split()[1]) * os.sysconf("SC_PAGE_SIZE")


class ZeroStream:
    """``size`` bytes of zeros, never held in memory as a whole."""

    def __init__(self, size):
        self.left = size
        self.read_bytes = 0

    def read(self, size):
        size = min(size, self.left)
        self.left -= size
        self.read_bytes += size
        return bytes(size)


class MeasuredStream(ZeroStream):
    """Notes the largest growth of the resident memory while it is read.

    The blocks are not zeros: the memory of ``bytes(n)`` is not resident until it is written to,
    so a reader that kept every block would not show.
    """

    def __init__(self, size):
        super().__init__(size)
        self.start = resident_memory()
        self.growth = 0

    def read(self, size):
        self.growth = max(self.growth, resident_memory() - self.start)
        block = super().read(size)
        return b"a" * len(block)


class BrokenStream:
    """Delivers one block, then fails."""

    def __init__(self):
        self.delivered = False

    def read(self, size):
        if self.delivered:
            raise OSError("connection lost")
        self.delivered = True
        return b"x" * 10


class BlobCase:
    def upload(self, data, name="file.bin", owner=None, **kwargs):
        owner = owner or self.partner
        attachment = self.Attachment._create_from_stream(
            io.BytesIO(data) if isinstance(data, bytes) else data,
            name,
            "res.partner",
            owner.id,
            **kwargs,
        )
        return attachment

    def blob_path(self, checksum):
        return self.Attachment._full_path(blob.blob_fname(checksum))

    def upload_files(self):
        folder = blob.upload_dir(self.Attachment)
        return set(os.listdir(folder)) if os.path.isdir(folder) else set()

    def forget(self, data):
        """Remove the blob of ``data`` when the test is over."""
        self.addCleanup(remove, self.blob_path(hashlib.sha1(data).hexdigest()))


@tagged("post_install", "-at_install")
class TestCreateFromStream(BlobCase, TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Attachment = cls.env["ir.attachment"]
        cls.partner = cls.env["res.partner"].create({"name": "Blob owner"})
        cls.manager = new_test_user(cls.env, login="blob_manager", groups="base.group_user,base.group_partner_manager")
        cls.employee = new_test_user(cls.env, login="blob_employee", groups="base.group_user")

    # The result is what the core makes.
    def test_the_row_is_the_one_the_core_makes(self):
        data = os.urandom(3 * MIB + 17)
        self.forget(data)
        streamed = self.upload(data, "song.mp3")
        made_by_core = self.Attachment.create({"name": "song.mp3", "raw": data})
        for field in ("store_fname", "checksum", "file_size", "mimetype"):
            self.assertEqual(streamed[field], made_by_core[field], field)
        self.assertEqual(streamed.raw, data)
        self.assertEqual(streamed.int_blob_size, len(data))
        self.assertEqual((streamed.res_model, streamed.res_id), ("res.partner", self.partner.id))
        self.assertEqual(streamed.checksum, hashlib.sha1(data).hexdigest())
        self.assertEqual(self.upload_files(), set())

    def test_a_binary_field_reads_the_file(self):
        self.forget(PNG)
        self.upload(PNG, "pic.png", res_field="image_1920")
        self.partner.invalidate_recordset(["image_1920"])
        self.assertEqual(base64.b64decode(self.partner.image_1920), PNG)

    def test_the_type_comes_from_the_name_and_the_head(self):
        data = b"ID3" + os.urandom(300)
        self.forget(data)
        self.assertEqual(self.upload(data, "song.mp3").mimetype, "audio/mpeg")

    def test_html_gets_the_type_that_the_core_gives_it(self):
        """The core makes html plain text for a user who cannot write views; a designer keeps it."""
        data = b"<html><script>alert(1)</script></html>"
        self.forget(data)
        types = {}
        for user in (self.env.ref("base.user_admin"), self.manager):
            streamed = self.Attachment.with_user(user)._create_from_stream(
                io.BytesIO(data), "page.html", "res.partner", self.partner.id, mimetype="text/html"
            )
            by_core = self.Attachment.with_user(user).create({"name": "page.html", "raw": data, "mimetype": "text/html"})
            self.assertEqual(streamed.mimetype, by_core.mimetype, user.login)
            types[user.login] = streamed.mimetype
        self.assertEqual(types[self.manager.login], "text/plain")

    # Memory and size.
    def test_a_large_file_does_not_grow_the_memory(self):
        stream = MeasuredStream(400 * MIB)
        attachment = self.upload(stream, "big.bin")
        self.addCleanup(remove, self.blob_path(attachment.checksum))
        self.assertEqual(attachment.file_size, 400 * MIB)
        self.assertLess(stream.growth / MIB, 64)

    def test_a_file_over_the_column_is_stored_with_its_real_size(self):
        """``file_size`` takes what its 32-bit column takes; the real size is in ``int_blob_size``."""
        size = 10 * MIB
        checksum = hashlib.sha1(bytes(size)).hexdigest()
        self.addCleanup(remove, self.blob_path(checksum))
        with patch.object(blob, "FILE_SIZE_MAX", 3 * MIB):
            attachment = self.upload(ZeroStream(size), "long.bin")
        self.assertEqual((attachment.file_size, attachment.int_blob_size), (3 * MIB, size))
        self.assertEqual(attachment.checksum, checksum)
        self.assertEqual(os.path.getsize(self.blob_path(checksum)), size)
        self.assertEqual(self.upload_files(), set())

    def test_the_size_is_recorded_in_the_column_of_the_module(self):
        """The core's column keeps 32 bits; the module's own column takes any size and is dropped with the module."""
        self.assertEqual(blob.FILE_SIZE_MAX, 2**31 - 1)
        self.assertEqual(self.Attachment._fields["file_size"].column_type[0], "int4")
        self.assertEqual(self.Attachment._fields["int_blob_size"].column_type[0], "int8")
        self.env.cr.execute(
            "SELECT data_type FROM information_schema.columns "
            "WHERE table_name = 'ir_attachment' AND column_name = 'int_blob_size'"
        )
        self.assertEqual(self.env.cr.fetchone()[0], "bigint")
        data = os.urandom(40)
        self.forget(data)
        attachment = self.upload(data)
        self.assertEqual(attachment.int_blob_size, len(data))
        models.Model.write(attachment.sudo(), {"int_blob_size": 5 * 1000**3})
        attachment.invalidate_recordset(["int_blob_size"])
        self.assertEqual(attachment.int_blob_size, 5 * 1000**3)

    # Failure leaves nothing.
    def test_a_stream_that_breaks_leaves_nothing(self):
        before = self.upload_files()
        with self.assertRaises(OSError):
            self.upload(BrokenStream())
        self.assertEqual(self.upload_files(), before)
        self.assertFalse(self.Attachment.search([("res_model", "=", "res.partner"), ("res_id", "=", self.partner.id)]))

    def test_a_refused_file_leaves_nothing(self):
        def refuse(_stored):
            raise UserError("no")

        before = self.upload_files()
        with self.assertRaises(UserError):
            self.upload(b"refused", check=refuse)
        self.assertEqual(self.upload_files(), before)
        self.assertFalse(os.path.exists(self.blob_path(hashlib.sha1(b"refused").hexdigest())))

    def test_a_rollback_after_the_upload_leaves_a_blob_that_the_cleaner_removes(self):
        data = os.urandom(64)
        path = self.blob_path(hashlib.sha1(data).hexdigest())
        self.addCleanup(remove, path)
        with contextlib.closing(self.cr.savepoint()):
            self.upload(data)
            self.assertTrue(os.path.exists(path))
        self.Attachment._gc_file_store_unsafe()
        self.assertFalse(os.path.exists(path))

    # Where it may go.
    def test_only_the_filestore_takes_a_stream(self):
        self.env["ir.config_parameter"].sudo().set_param("ir_attachment.location", "db")
        before = self.upload_files()
        with self.assertRaises(UserError):
            self.upload(b"in the database")
        self.assertEqual(self.upload_files(), before)
        self.assertFalse(self.Attachment.search([("res_model", "=", "res.partner"), ("res_id", "=", self.partner.id)]))

    def test_the_owner_must_exist(self):
        for res_model, res_id in (("res.partner", 0), ("res.partner", 99999999), ("no.such.model", 1), (False, False)):
            with self.subTest(res_model=res_model, res_id=res_id), self.assertRaises(UserError):
                self.Attachment._create_from_stream(io.BytesIO(b"x"), "x", res_model, res_id)

    def test_the_caller_must_be_allowed_to_write_the_owner(self):
        data = os.urandom(32)
        self.forget(data)
        stream = ZeroStream(5 * MIB)
        with self.assertRaises(AccessError):
            self.Attachment.with_user(self.employee)._create_from_stream(
                stream, "x.bin", "res.partner", self.partner.id
            )
        self.assertEqual(stream.read_bytes, 0, "refused before a byte is read")
        attachment = self.Attachment.with_user(self.manager)._create_from_stream(
            io.BytesIO(data), "x.bin", "res.partner", self.partner.id
        )
        self.assertEqual(attachment.with_user(self.manager).raw, data)
        self.assertEqual(self.upload_files(), set())

    # Sharing and replacing.
    def test_the_same_file_twice_is_one_blob_until_both_rows_are_gone(self):
        data = os.urandom(128)
        path = self.blob_path(hashlib.sha1(data).hexdigest())
        self.addCleanup(remove, path)
        first = self.upload(data, "a.bin")
        second = self.upload(data, "b.bin")
        self.assertEqual(first.store_fname, second.store_fname)
        inode = os.stat(path).st_ino
        first.unlink()
        self.Attachment._gc_file_store_unsafe()
        self.assertTrue(os.path.exists(path))
        self.assertEqual(os.stat(path).st_ino, inode)
        second.unlink()
        self.Attachment._gc_file_store_unsafe()
        self.assertFalse(os.path.exists(path))

    def test_a_file_at_the_place_with_other_content_is_refused(self):
        data = os.urandom(64)
        path = self.blob_path(hashlib.sha1(data).hexdigest())
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as taken:
            taken.write(b"other content")
        self.addCleanup(remove, path)
        before = self.upload_files()
        with self.assertRaises(UserError):
            self.upload(data)
        with open(path, "rb") as taken:
            self.assertEqual(taken.read(), b"other content")
        self.assertEqual(self.upload_files(), before)

    def test_a_new_file_in_the_same_field_replaces_the_old_one(self):
        old, new = os.urandom(50), os.urandom(60)
        old_path = self.blob_path(hashlib.sha1(old).hexdigest())
        self.addCleanup(remove, old_path)
        self.forget(new)
        first = self.upload(old, "one.bin", res_field="image_1920")
        second = self.upload(new, "two.bin", res_field="image_1920")
        self.assertEqual(first, second)
        self.assertEqual((second.name, second.raw, second.int_blob_size), ("two.bin", new, 60))
        self.Attachment._gc_file_store_unsafe()
        self.assertFalse(os.path.exists(old_path))

    # Critical review: what a failure or a stranger can do.
    def catch(self, error, function, *args, **kwargs):
        """Call ``function`` and swallow ``error`` like a caller that goes on with the next file.

        ``assertRaises`` of the test case rolls back to a savepoint and so hides what stays behind.
        """
        try:
            function(*args, **kwargs)
        except error:
            return
        self.fail(f"{error.__name__} was not raised")

    def test_a_failed_placement_leaves_no_row(self):
        """A caller that catches the error and goes on (an import of many files) must not keep a row without a file."""
        data = os.urandom(64)
        path = self.blob_path(hashlib.sha1(data).hexdigest())
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as taken:
            taken.write(b"other content")
        self.addCleanup(remove, path)
        self.catch(UserError, self.upload, data)
        domain = [("res_model", "=", "res.partner"), ("res_id", "=", self.partner.id)]
        self.assertFalse(self.Attachment.search(domain))

    def test_a_failed_replacement_keeps_the_old_file(self):
        old = os.urandom(50)
        self.forget(old)
        first = self.upload(old, "one.bin", res_field="image_1920")
        new = os.urandom(60)
        path = self.blob_path(hashlib.sha1(new).hexdigest())
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as taken:
            taken.write(b"other content")
        self.addCleanup(remove, path)
        self.catch(UserError, self.upload, new, "two.bin", res_field="image_1920")
        first.invalidate_recordset()
        self.assertEqual((first.name, first.raw), ("one.bin", old))

    def test_the_field_must_be_a_binary_field_of_the_owner(self):
        for res_field in ("no_such_field", "name", "parent_id"):
            with self.subTest(res_field=res_field), self.assertRaises(UserError):
                self.upload(b"x", res_field=res_field)

    def test_an_empty_file_is_what_the_core_makes_of_it(self):
        streamed = self.upload(b"", "empty.txt")
        by_core = self.Attachment.create({"name": "empty.txt", "raw": b""})
        for field in ("store_fname", "checksum", "file_size", "mimetype"):
            self.assertEqual(streamed[field], by_core[field], field)
        self.assertFalse(os.path.exists(self.blob_path(hashlib.sha1(b"").hexdigest())))
        self.assertEqual(self.upload_files(), set())

    # The path is made from a checksum only.
    def test_a_name_in_the_filestore_needs_a_sha1(self):
        for bad in ("", None, "../../etc/passwd", "a" * 39, "A" * 40, "g" * 40, "a" * 40 + "/", "a" * 64):
            with self.subTest(checksum=bad), self.assertRaises(ValueError):
                blob.blob_fname(bad)
        self.assertEqual(blob.blob_fname("ab" + "c" * 38), "ab/" + "ab" + "c" * 38)

    # Temporary files.
    def test_the_cleaner_removes_old_temporary_files_only(self):
        folder = blob.upload_dir(self.Attachment)
        os.makedirs(folder, exist_ok=True)
        old, fresh = os.path.join(folder, "old"), os.path.join(folder, "fresh")
        for path in (old, fresh):
            with open(path, "wb") as out:
                out.write(b"x")
            self.addCleanup(remove, path)
        long_ago = time.time() - 48 * 3600
        os.utime(old, (long_ago, long_ago))
        self.Attachment._gc_int_blob_uploads()
        self.assertFalse(os.path.exists(old))
        self.assertTrue(os.path.exists(fresh))

    def test_the_vacuum_of_odoo_collects_the_cleaner_of_the_temporary_files(self):
        """The daily cron finds the methods marked ``@api.autovacuum`` of every model, ours among them."""
        names = [name for name, _function in inspect.getmembers(type(self.Attachment), is_autovacuum)]
        self.assertIn("_gc_int_blob_uploads", names)
        self.assertIn("_gc_file_store", names)

    # Two uploads of the same file at once.
    def test_publishers_of_the_same_file_need_no_lock(self):
        """Eight at once: each succeeds, the file is whole at every moment, one blob stays."""
        data = os.urandom(5 * MIB)
        checksum = hashlib.sha1(data).hexdigest()
        fname = blob.blob_fname(checksum)
        path = self.Attachment._full_path(fname)
        self.addCleanup(remove, path)
        folder = blob.upload_dir(self.Attachment)
        os.makedirs(folder, exist_ok=True)
        tmp_paths = []
        for index in range(8):
            tmp = os.path.join(folder, f"race{index}")
            with open(tmp, "wb") as out:
                out.write(data)
            tmp_paths.append(tmp)
        barrier = threading.Barrier(len(tmp_paths) + 1)
        errors, partial = [], []
        done = threading.Event()

        def publish(tmp):
            try:
                barrier.wait()
                blob.publish(self.Attachment, tmp, fname)
            except Exception as error:  # noqa: BLE001 (reported by the test thread below)
                errors.append(error)

        def watch():
            barrier.wait()
            while not done.is_set():
                with contextlib.suppress(FileNotFoundError):
                    size = os.path.getsize(path)
                    if size != len(data):
                        partial.append(size)

        threads = [threading.Thread(target=publish, args=(tmp,)) for tmp in tmp_paths]
        watcher = threading.Thread(target=watch)
        for thread in (*threads, watcher):
            thread.start()
        for thread in threads:
            thread.join(timeout=30)
        done.set()
        watcher.join(timeout=5)
        self.assertEqual(errors, [])
        self.assertEqual(partial, [], "a reader saw a part of the file")
        with open(path, "rb") as placed:
            self.assertEqual(hashlib.sha1(placed.read()).hexdigest(), checksum)
        self.assertEqual([tmp for tmp in tmp_paths if os.path.exists(tmp)], [])


@tagged("post_install", "-at_install")
class TestStreamedDownload(BlobCase, HttpCase):
    """The core route serves the file; the size comes from the file, not from the column."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Attachment = cls.env["ir.attachment"]
        cls.partner = cls.env["res.partner"].create({"name": "Download owner"})

    def setUp(self):
        super().setUp()
        self.authenticate("admin", "admin")

    def test_the_download_delivers_the_bytes_and_a_range(self):
        data = os.urandom(3 * MIB)
        self.forget(data)
        attachment = self.upload(data, "d.bin")
        url = f"/web/content/{attachment.id}?download=true"
        response = self.url_open(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, data)
        partial = self.url_open(url, headers={"Range": "bytes=10-19"})
        self.assertEqual(partial.status_code, 206)
        self.assertEqual(partial.content, data[10:20])

    def test_a_file_above_2_gib_is_served_with_its_real_size(self):
        """A sparse file of 3 GiB under a row that holds the highest size the column takes."""
        size = 3 * 1024 * MIB
        checksum = hashlib.sha1(b"sparse").hexdigest()
        fname = blob.blob_fname(checksum)
        path = self.Attachment._full_path(fname)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as sparse:
            sparse.truncate(size)
        self.addCleanup(remove, path)
        attachment = self.Attachment.create(
            {"name": "huge.bin", "res_model": "res.partner", "res_id": self.partner.id, "mimetype": "application/octet-stream"}
        )
        models.Model.write(
            attachment.sudo(), {"store_fname": fname, "checksum": checksum, "file_size": blob.FILE_SIZE_MAX, "int_blob_size": size}
        )
        attachment.flush_recordset(blob.STORED_FIELDS)
        response = self.url_open(f"/web/content/{attachment.id}?download=true", headers={"Range": "bytes=0-9"})
        self.assertEqual(response.status_code, 206)
        self.assertEqual(response.headers["Content-Range"], f"bytes 0-9/{size}")
        self.assertEqual(response.content, bytes(10))


@tagged("post_install", "-at_install", "-standard", "int_blob_big")
class TestStreamBig(BlobCase, TransactionCase):
    """Run on demand: ``--test-tags int_blob_big``. Needs 2.1 GiB of disk space."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Attachment = cls.env["ir.attachment"]
        cls.partner = cls.env["res.partner"].create({"name": "Big owner"})

    def test_a_file_above_2_gib_is_streamed_and_recorded_with_its_real_size(self):
        size = 2 * 1024 * MIB + 5 * MIB
        block = b"a" * MIB
        digest = hashlib.sha1()
        for _ in range(size // MIB):
            digest.update(block)
        stream = MeasuredStream(size)
        attachment = self.upload(stream, "big.bin")
        path = self.blob_path(attachment.checksum)
        self.addCleanup(remove, path)
        self.assertEqual(attachment.checksum, digest.hexdigest())
        self.assertEqual((attachment.file_size, attachment.int_blob_size), (blob.FILE_SIZE_MAX, size))
        self.assertEqual(os.path.getsize(path), size)
        self.assertLess(stream.growth / MIB, 64)
        self.assertEqual(self.upload_files(), set())
