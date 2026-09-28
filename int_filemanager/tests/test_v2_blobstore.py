"""Tests for the blob store: writes, deduplication and the cleanup job."""

import io
import os
import time

from odoo import fields
from odoo.tests.common import TransactionCase, tagged

from .. import blobstore


@tagged("post_install", "-at_install")
class TestBlobstorePrimitives(TransactionCase):
    def _write_temp(self, content):
        return blobstore.write_stream_to_temp(
            self.env, io.BytesIO(content), f"t{id(content)}"
        )

    def test_hash_file_matches_sha256_and_size(self):
        tmp_path = self._write_temp(b"hello world")
        sha256, size = blobstore.hash_file(tmp_path)
        self.assertEqual(size, 11)
        self.assertEqual(
            sha256, "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"
        )
        os.remove(tmp_path)

    def test_adopt_hashed_first_write_then_dedup(self):
        content = b"same content twice"
        tmp1 = self._write_temp(content)
        sha256, _size = blobstore.hash_file(tmp1)

        deduped_first = blobstore.adopt_hashed(self.env, tmp1, sha256)
        self.assertFalse(deduped_first)

        tmp2 = self._write_temp(content)
        deduped_second = blobstore.adopt_hashed(self.env, tmp2, sha256)
        self.assertTrue(deduped_second)

        final_path = blobstore.blob_path(self.env, sha256)
        with open(final_path, "rb") as f:
            self.assertEqual(f.read(), content)

    def test_adopt_hashed_creates_checklist_marker(self):
        tmp_path = self._write_temp(b"marked for gc")
        sha256, _size = blobstore.hash_file(tmp_path)
        blobstore.adopt_hashed(self.env, tmp_path, sha256)
        marker = os.path.join(blobstore.checklist_dir(self.env), sha256)
        self.assertTrue(os.path.isfile(marker))

    def test_mark_for_gc_renews_mtime_on_existing_marker(self):
        """Opening an existing marker in append mode alone does not renew its mtime."""
        sha256 = "c" * 64
        blobstore.mark_for_gc(self.env, sha256)
        marker = os.path.join(blobstore.checklist_dir(self.env), sha256)
        old_time = time.time() - 3600
        os.utime(marker, (old_time, old_time))
        self.assertAlmostEqual(os.path.getmtime(marker), old_time, delta=1)

        blobstore.mark_for_gc(self.env, sha256)

        self.assertGreater(os.path.getmtime(marker), old_time + 1000)

    def test_ensure_on_disk_relinks_from_kept_temp_file(self):
        content = b"vanished by an unlucky gc run"
        tmp_path = self._write_temp(content)
        sha256, _size = blobstore.hash_file(tmp_path)
        blobstore.adopt_hashed(self.env, tmp_path, sha256, keep_tmp=True)
        final_path = blobstore.blob_path(self.env, sha256)
        os.remove(final_path)
        self.assertFalse(os.path.exists(final_path))

        blobstore.ensure_on_disk(self.env, sha256, tmp_path)

        with open(final_path, "rb") as f:
            self.assertEqual(f.read(), content)
        os.remove(tmp_path)

    def test_ensure_on_disk_is_a_noop_when_file_already_present(self):
        tmp_path = self._write_temp(b"already there")
        sha256, _size = blobstore.hash_file(tmp_path)
        blobstore.adopt_hashed(self.env, tmp_path, sha256, keep_tmp=True)

        blobstore.ensure_on_disk(self.env, sha256, tmp_path)  # must not raise

        os.remove(tmp_path)

    def test_ensure_empty_blob_creates_zero_byte_blob(self):
        blobstore.ensure_empty_blob(self.env)
        final_path = blobstore.blob_path(self.env, blobstore.EMPTY_SHA256)
        self.assertEqual(os.path.getsize(final_path), 0)


@tagged("post_install", "-at_install")
class TestBlobGetOrCreate(TransactionCase):
    def test_returns_new_row_and_sets_last_used(self):
        blob = self.env["int_filemanager.blob"].sudo()._get_or_create("d" * 64, 42.0)
        self.assertEqual(blob.sha256, "d" * 64)
        self.assertTrue(blob.last_used)

    def test_returns_same_row_and_bumps_last_used_on_reuse(self):
        Blob = self.env["int_filemanager.blob"].sudo()
        first = Blob._get_or_create("e" * 64, 1.0)
        first.write({"last_used": "2020-01-01 00:00:00"})

        second = Blob._get_or_create("e" * 64, 1.0)

        self.assertEqual(first.id, second.id)
        self.assertNotEqual(second.last_used, "2020-01-01 00:00:00")

    def test_recovers_from_concurrent_unique_violation(self):
        """Odoo does not retry a unique violation, so _get_or_create handles it.

        Simulated race: search() finds nothing, then create() collides with a
        row a concurrent writer committed in between.
        """
        Blob = self.env["int_filemanager.blob"].sudo()
        sha256 = "f" * 64
        existing = Blob.create(
            {"sha256": sha256, "size": 1.0, "last_used": fields.Datetime.now()}
        )

        model_cls = type(Blob)
        real_search = model_cls.search
        state = {"calls": 0}

        def fake_search(self, domain, **kwargs):
            state["calls"] += 1
            if state["calls"] == 1:
                return self.browse()
            return real_search(self, domain, **kwargs)

        model_cls.search = fake_search
        try:
            result = Blob._get_or_create(sha256, 2.0)
        finally:
            model_cls.search = real_search

        self.assertEqual(result.id, existing.id)


@tagged("post_install", "-at_install")
class TestBlobGc(TransactionCase):
    def _adopt(self, content):
        tmp_path = blobstore.write_stream_to_temp(
            self.env, io.BytesIO(content), f"gc{id(content)}"
        )
        sha256, size = blobstore.hash_file(tmp_path)
        blobstore.adopt_hashed(self.env, tmp_path, sha256)
        return sha256, size

    def _make_node_with_revision(self, name, sha256, size):
        scope = (
            self.env["int_filemanager.scope"]
            .sudo()
            .create({"name": f"GC scope {name}"})
        )
        node = (
            self.env["int_filemanager.node"]
            .sudo()
            .create({"name": name, "scope_id": scope.id})
        )
        blob = self.env["int_filemanager.blob"].sudo()._get_or_create(sha256, size)
        return (
            self.env["int_filemanager.revision"]
            .sudo()
            .create(
                {
                    "node_id": node.id,
                    "blob_id": blob.id,
                    "revision_no": 1,
                    "origin": "upload",
                }
            )
        )

    def test_blob_with_revision_survives_gc(self):
        Blob = self.env["int_filemanager.blob"].sudo()
        sha256, size = self._adopt(b"referenced content")
        self._make_node_with_revision("kept.txt", sha256, size)
        Blob.search([("sha256", "=", sha256)]).write(
            {"last_used": "2000-01-01 00:00:00"}
        )

        stale_count, _removed, _kept = Blob._gc_blobs_unsafe()

        self.assertEqual(stale_count, 0)
        self.assertTrue(Blob.search([("sha256", "=", sha256)]))
        self.assertTrue(os.path.exists(blobstore.blob_path(self.env, sha256)))

    def test_blob_without_revision_past_grace_is_removed(self):
        """The first run removes the row and renews the marker; the file goes only
        in a later run, once the marker has aged past the grace period too."""
        Blob = self.env["int_filemanager.blob"].sudo()
        sha256, size = self._adopt(b"never referenced, old")
        Blob._get_or_create(sha256, size).write({"last_used": "2000-01-01 00:00:00"})
        marker = os.path.join(blobstore.checklist_dir(self.env), sha256)

        stale_count_1, removed_1, _kept_1 = Blob._gc_blobs_unsafe()
        self.assertEqual(stale_count_1, 1)
        self.assertEqual(removed_1, 0)
        self.assertFalse(Blob.search([("sha256", "=", sha256)]))
        self.assertTrue(os.path.exists(blobstore.blob_path(self.env, sha256)))

        old_time = time.time() - 1000000
        os.utime(marker, (old_time, old_time))
        stale_count_2, removed_2, _kept_2 = Blob._gc_blobs_unsafe()

        self.assertEqual(stale_count_2, 0)
        self.assertEqual(removed_2, 1)
        self.assertFalse(os.path.exists(blobstore.blob_path(self.env, sha256)))

    def test_blob_without_revision_within_grace_survives(self):
        """A blob a writer just linked is kept until it could commit its revision."""
        Blob = self.env["int_filemanager.blob"].sudo()
        sha256, size = self._adopt(b"just written")
        Blob._get_or_create(sha256, size)  # row created, no revision yet - like
        # a writer between "blob row committed" and "revision about to be created"

        stale_count, removed, _kept = Blob._gc_blobs_unsafe()

        self.assertEqual(stale_count, 0)
        self.assertEqual(removed, 0)
        self.assertTrue(os.path.exists(blobstore.blob_path(self.env, sha256)))
