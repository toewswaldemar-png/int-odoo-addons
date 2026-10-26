from odoo.tests.common import tagged

from odoo.addons.int_filemanager.tests.test_document_cleaner import BlobCase
from odoo.addons.int_filemanager_ocr.models.int_filemanager_text import TEXT_CRON_XMLID


@tagged("post_install", "-at_install")
class TestHooksOfTheCore(BlobCase):
    """What this module adds to the extension points of the filemanager."""

    def test_a_made_preview_wakes_the_action_of_the_picture_and_of_the_text(self):
        crons = self.Document._crons_after_preview()
        self.assertIn("int_filemanager.int_filemanager_thumbnail_cron", crons)
        self.assertIn(TEXT_CRON_XMLID, crons)

    def test_the_cleaner_locks_the_documents_first_and_then_the_texts(self):
        tables = self.Document._gc_lock_tables()
        self.assertEqual(tables, [self.Document._table, self.env["int.filemanager.text"]._table])

    def test_a_recognized_pdf_of_a_text_row_is_in_use(self):
        checksum = "e" * 64
        self.addCleanup(self._forget, checksum)
        self.env["int.filemanager.text"].create({"checksum": "f" * 64, "ocr_checksum": checksum})
        self.assertEqual(self.Document._blobs_in_use([checksum, "0" * 64]), {checksum})

    def test_the_viewer_gets_the_recognized_pdf_before_the_preview(self):
        document = self.Document.create(
            {"name": "a.pdf", "folder_id": self.folder.id, "checksum": "a" * 64, "preview_checksum": "b" * 64}
        )
        self.assertEqual(document.ocr_checksum, "b" * 64)
        self.addCleanup(self._forget, "c" * 64)
        self.env["int.filemanager.text"].create({"checksum": "a" * 64, "ocr_checksum": "c" * 64})
        document.invalidate_recordset(["ocr_checksum"])
        self.assertEqual(document.ocr_checksum, "c" * 64)
