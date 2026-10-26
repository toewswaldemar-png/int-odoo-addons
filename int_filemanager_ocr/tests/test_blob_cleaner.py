import io
import os

from odoo.sql_db import db_connect
from odoo.tests.common import tagged

from odoo.addons.int_filemanager.tests.test_document_cleaner import BlobCase


@tagged("post_install", "-at_install")
class TestBlobCleanerTexts(BlobCase):
    """The cleaner keeps the recognized PDFs that a text row has, and deletes them with the last row."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Text = cls.env["int.filemanager.text"]

    def _recognized_pdf(self, content=b"recognized"):
        """A blob that only a text row will keep: its checksum, as the recognition makes it."""
        stored = self.Document._store_stream(io.BytesIO(content), "scan.pdf")
        self.Document._publish_blob(stored["tmp_path"], stored["checksum"])
        self.addCleanup(self._forget, stored["checksum"])
        return stored["checksum"]

    def _text_row(self, ocr_checksum):
        return self.Text.create({"checksum": "d" * 64, "ocr_checksum": ocr_checksum})

    def test_the_recognized_pdf_of_a_text_row_stays(self):
        checksum = self._recognized_pdf()
        self._text_row(checksum)
        self._gc()
        self.assertTrue(os.path.exists(self._blob(checksum)))
        self.assertFalse(os.path.exists(self._marker(checksum)))

    def test_the_recognized_pdf_goes_with_the_last_text_row(self):
        checksum = self._recognized_pdf()
        row = self._text_row(checksum)
        self._gc()
        row.unlink()
        self.assertTrue(os.path.exists(self._marker(checksum)))
        self._gc()
        self.assertFalse(os.path.exists(self._blob(checksum)))

    def test_another_recognized_pdf_marks_the_old_one(self):
        old, new = self._recognized_pdf(b"old"), self._recognized_pdf(b"new")
        row = self._text_row(old)
        row.ocr_checksum = new
        self.assertTrue(os.path.exists(self._marker(old)))
        self._gc()
        self.assertFalse(os.path.exists(self._blob(old)))
        self.assertTrue(os.path.exists(self._blob(new)))

    def test_a_document_with_the_same_checksum_keeps_it_too(self):
        document = self._document("a.txt", b"same")
        checksum = document.checksum
        self._text_row(checksum)
        document.unlink()
        self._gc()
        self.assertTrue(os.path.exists(self._blob(checksum)))

    def test_a_busy_writer_of_the_texts_makes_the_cleaner_give_up(self):
        checksum = self._recognized_pdf()
        with db_connect(self.env.cr.dbname).cursor() as other:
            other.execute("LOCK TABLE int_filemanager_text IN ROW EXCLUSIVE MODE")
            result = self._gc(int_filemanager_lock_timeout="100ms")
        self.assertEqual(result, (0, 0))
        self.assertTrue(os.path.exists(self._blob(checksum)))
        self.assertTrue(os.path.exists(self._marker(checksum)))
