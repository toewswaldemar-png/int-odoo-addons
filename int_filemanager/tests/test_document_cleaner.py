import io
import os
import time
from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.sql_db import db_connect
from odoo.tests.common import TransactionCase, tagged

MODULE = "odoo.addons.int_filemanager.models.int_filemanager_document_storage"


def remove(path):
    if os.path.exists(path):
        os.unlink(path)


class BlobCase(TransactionCase):
    """Documents with blobs, and the cleaner run as it runs."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Document = cls.env["int.filemanager.document"]
        cls.folder = cls.env["int.filemanager.folder"].create({"name": "Cleaning"})

    def _document(self, name="a.txt", content=b"hello"):
        document = self.Document._create_from_stream(io.BytesIO(content), name, self.folder)
        self.addCleanup(self._forget, document.checksum)
        return document

    def _gc(self, **context):
        """Run the cleaner as it runs, but with a savepoint for the commit and the rollback
        that a test is not allowed to make."""
        cr = self.env.cr
        cr.execute("SAVEPOINT cleaner_test")

        def rollback():
            cr.execute("ROLLBACK TO SAVEPOINT cleaner_test")

        with patch.object(cr, "commit"), patch.object(cr, "rollback", rollback):
            return self.Document.with_context(**context)._gc_blobs()

    def _forget(self, checksum):
        remove(self.Document._blob_path(checksum))
        remove(self._marker(checksum))

    def _marker(self, checksum):
        return os.path.join(self.Document._checklist_dir(), checksum[:2], checksum)

    def _blob(self, document_or_checksum):
        checksum = getattr(document_or_checksum, "checksum", document_or_checksum)
        return self.Document._blob_path(checksum)


@tagged("post_install", "-at_install")
class TestBlobCleaner(BlobCase):
    """The cleaner deletes the blobs that no document uses, and only those."""

    # --- what goes on the checklist ------------------------------------------

    def test_a_new_blob_is_on_the_checklist_until_the_cleaner_has_looked(self):
        document = self._document()
        self.assertTrue(os.path.exists(self._marker(document.checksum)))

    def test_deleting_a_document_marks_its_blob(self):
        document = self._document()
        self._gc()
        self.assertFalse(os.path.exists(self._marker(document.checksum)))
        checksum = document.checksum
        document.unlink()
        self.assertTrue(os.path.exists(self._marker(checksum)))

    def test_changing_the_checksum_marks_the_old_blob(self):
        document = self._document()
        old = document.checksum
        self._gc()
        document.sudo().write({"checksum": "b" * 64})
        self.assertTrue(os.path.exists(self._marker(old)))
        self.assertFalse(os.path.exists(self._marker("b" * 64)))

    def test_only_a_checksum_goes_on_the_checklist(self):
        with self.assertRaises(ValueError):
            self.Document._mark_blob_for_gc("../../etc/passwd")

    # --- what the cleaner deletes --------------------------------------------

    def test_the_blob_of_a_deleted_document_is_deleted(self):
        document = self._document()
        checksum = document.checksum
        document.unlink()
        done, remaining = self._gc()
        self.assertEqual((done, remaining), (1, 0))
        self.assertFalse(os.path.exists(self._blob(checksum)))
        self.assertFalse(os.path.exists(self._marker(checksum)))

    def test_a_blob_that_another_document_uses_stays(self):
        first, second = self._document("a.txt"), self._document("b.txt")
        checksum = first.checksum
        first.unlink()
        self._gc()
        self.assertTrue(os.path.exists(self._blob(checksum)))
        self.assertFalse(os.path.exists(self._marker(checksum)))
        second.unlink()
        self._gc()
        self.assertFalse(os.path.exists(self._blob(checksum)))

    def test_the_blob_of_an_archived_document_stays(self):
        document = self._document()
        document.active = False
        self.Document._mark_blob_for_gc(document.checksum)
        self._gc()
        self.assertTrue(os.path.exists(self._blob(document)))

    def test_a_blob_without_any_document_is_deleted(self):
        # What a rolled back upload leaves: the blob and its entry, but no row.
        stored = self.Document._store_stream(io.BytesIO(b"orphan"), "orphan.txt")
        self.Document._publish_blob(stored["tmp_path"], stored["checksum"])
        self.addCleanup(self._forget, stored["checksum"])
        self.assertTrue(os.path.exists(self._blob(stored["checksum"])))
        self._gc()
        self.assertFalse(os.path.exists(self._blob(stored["checksum"])))

    def test_an_entry_without_a_blob_does_not_stop_the_cleaner(self):
        self.Document._mark_blob_for_gc("c" * 64)
        self.addCleanup(self._forget, "c" * 64)
        self.assertEqual(self._gc(), (1, 0))
        self.assertFalse(os.path.exists(self._marker("c" * 64)))

    def test_an_empty_checklist_is_nothing_to_do(self):
        self._gc()
        self.assertEqual(self._gc(), (0, 0))

    def test_the_cleaner_works_in_batches_and_says_what_is_left(self):
        for number in range(5):
            self.Document._mark_blob_for_gc(f"{number}" * 64)
            self.addCleanup(self._forget, f"{number}" * 64)
        with patch(f"{MODULE}.GC_BATCH", 2):
            results = [self._gc() for _ in range(3)]
        self.assertEqual(results, [(2, 1), (2, 1), (1, 0)])

    def test_a_busy_writer_makes_the_cleaner_give_up_and_keep_everything(self):
        document = self._document()
        checksum = document.checksum
        document.unlink()
        with db_connect(self.env.cr.dbname).cursor() as other:
            # A transaction that writes to the documents (the cleaner must wait for it).
            other.execute("LOCK TABLE int_filemanager_document IN ROW EXCLUSIVE MODE")
            result = self._gc(int_filemanager_lock_timeout="100ms")
        self.assertEqual(result, (0, 0))
        self.assertTrue(os.path.exists(self._blob(checksum)))
        self.assertTrue(os.path.exists(self._marker(checksum)))
        # Free again: the next run does the work.
        self.assertEqual(self._gc(), (1, 0))
        self.assertFalse(os.path.exists(self._blob(checksum)))

    def test_the_cleaner_of_the_core_leaves_the_blobs_alone(self):
        # It deletes what is on ITS checklist and has no attachment: our blobs must never be
        # on it, and it must not look at ours.
        document = self._document()
        checksum = document.checksum
        document.unlink()
        self.env["ir.attachment"]._gc_file_store_unsafe()
        self.assertTrue(os.path.exists(self._blob(checksum)))
        self.assertTrue(os.path.exists(self._marker(checksum)))
        self._gc()
        self.assertFalse(os.path.exists(self._blob(checksum)))

    # --- the temporary files of uploads --------------------------------------

    def _upload_file(self, name, age_hours):
        os.makedirs(self.Document._upload_dir(), exist_ok=True)
        path = os.path.join(self.Document._upload_dir(), name)
        with open(path, "wb") as handle:
            handle.write(b"half")
        stamp = time.time() - age_hours * 3600
        os.utime(path, (stamp, stamp))
        self.addCleanup(remove, path)
        return path

    def test_old_temporary_files_are_deleted_and_young_ones_stay(self):
        old, young = self._upload_file("old", 30), self._upload_file("young", 2)
        self.Document._gc_blob_uploads()
        self.assertFalse(os.path.exists(old))
        self.assertTrue(os.path.exists(young))

    def test_the_age_is_a_system_parameter(self):
        young = self._upload_file("young", 2)
        self.env["ir.config_parameter"].set_param("int_filemanager.upload_max_age_hours", "1")
        self.Document._gc_blob_uploads()
        self.assertFalse(os.path.exists(young))


@tagged("post_install", "-at_install")
class TestTrash(BlobCase):
    """An archived document is deleted when it has been in the trash for the time of the settings."""

    def _trashed(self, name="a.txt", days=40, **kwargs):
        """An archived document that has been archived ``days`` days ago."""
        document = self._document(name, **kwargs)
        document.action_archive()
        document.write({"archived_date": fields.Datetime.now() - timedelta(days=days)})
        return document

    def test_archiving_starts_the_time_and_restoring_ends_it(self):
        document = self._document()
        self.assertFalse(document.archived_date)
        document.action_archive()
        self.assertTrue(document.archived_date)
        document.action_unarchive()
        self.assertFalse(document.archived_date)

    def test_writing_to_an_archived_document_does_not_start_the_time_again(self):
        document = self._trashed(days=40)
        before = document.archived_date
        document.sudo().write({"preview_state": "failed"})
        self.assertEqual(document.archived_date, before)

    def test_a_document_in_the_trash_longer_than_the_time_is_deleted(self):
        old, young = self._trashed("old.txt", days=31), self._trashed("young.txt", days=29)
        active = self._document("active.txt")
        self.assertEqual(self.Document._gc_trash(), (1, 0))
        self.assertFalse(old.exists())
        self.assertTrue(young.exists())
        self.assertTrue(active.exists())

    def test_the_file_goes_with_the_document(self):
        document = self._trashed()
        checksum = document.checksum
        self.Document._gc_trash()
        self._gc()
        self.assertFalse(os.path.exists(self._blob(checksum)))

    def test_the_time_is_a_setting(self):
        document = self._trashed(days=10)
        self.Document._gc_trash()
        self.assertTrue(document.exists())
        self.env["ir.config_parameter"].set_param("int_filemanager.trash_days", "7")
        self.Document._gc_trash()
        self.assertFalse(document.exists())

    def test_nothing_is_deleted_when_the_setting_says_never(self):
        document = self._trashed(days=400)
        self.env["ir.config_parameter"].set_param("int_filemanager.trash_enabled", "0")
        self.assertEqual(self.Document._gc_trash(), (0, 0))
        self.assertTrue(document.exists())

    def test_the_documents_of_other_companies_are_deleted_too(self):
        # The scheduled action has the companies of its user; the rules would hide the rest.
        company = self.env["res.company"].create({"name": "Other company"})
        folder = self.env["int.filemanager.folder"].create({"name": "Elsewhere", "company_id": company.id})
        document = self.Document._create_from_stream(io.BytesIO(b"other"), "other.txt", folder)
        self.addCleanup(self._forget, document.checksum)
        document.action_archive()
        document.write({"archived_date": fields.Datetime.now() - timedelta(days=40)})
        bot = self.env.ref("base.user_root")
        self.Document.with_user(bot).with_context(allowed_company_ids=[self.env.company.id])._gc_trash()
        self.assertFalse(document.exists())

    def test_it_works_in_batches_and_says_what_is_left(self):
        documents = [self._trashed(f"{number}.txt", content=bytes([number])) for number in range(5)]
        with patch(f"{MODULE}.GC_BATCH", 2):
            results = [self.Document._gc_trash() for _ in range(3)]
        self.assertEqual(results, [(2, 1), (2, 1), (1, 0)])
        self.assertFalse(any(document.exists() for document in documents))
