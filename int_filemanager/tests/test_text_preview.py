import io
import os
from unittest.mock import patch

from odoo.tests.common import tagged

from . import text_files
from .test_text_search import MODULE, TextCase, remove


@tagged("post_install", "-at_install")
class TestTextOfOldFormats(TextCase):
    """Word, Excel and PowerPoint of before 2007 and RTF: the text comes from the preview PDF."""

    def _preview(self, document, pages=("First page of the sheet", "Second page")):
        """Give the document the preview that the scheduled action of LibreOffice would make."""
        stored = self.Document._store_stream(io.BytesIO(text_files.pdf(list(pages))), "preview")
        self.Document._publish_blob(stored["tmp_path"], stored["checksum"])
        self.addCleanup(remove, self.Document._blob_path(stored["checksum"]))
        document.sudo().write({"preview_checksum": stored["checksum"], "preview_state": "done"})
        return stored["checksum"]

    def test_a_file_of_an_old_format_has_no_row_before_its_preview(self):
        document = self._document("old.xls", b"binary sheet")
        self.assertEqual(self.Text._create_rows(1000), 0)
        self.assertFalse(self._text_of(document))
        self.assertEqual(self.Text._count_missing(), 0)

    def test_a_file_whose_preview_failed_never_gets_one(self):
        document = self._document("old.doc", b"binary text")
        document.sudo().write({"preview_state": "failed"})
        self.assertEqual(self.Text._create_rows(1000), 0)

    def test_the_text_is_read_from_the_preview_and_found(self):
        document = self._document("old.xls", b"binary sheet")
        self._preview(document)
        self._read_all()
        row = self._text_of(document)
        self.assertEqual((row.state, row.mimetype, row.page_count), ("done", "application/vnd.ms-excel", 2))
        self.assertEqual(self._found("sheet"), document)
        # The pages are the pages of the PDF that the viewer shows.
        hits = document.with_context(int_filemanager_words=["second"]).content_hits
        self.assertEqual([hit["page"] for hit in hits["hits"]], [2])

    def test_every_old_type_is_read(self):
        words = {"a.doc": "harvest", "a.rtf": "orchard", "a.xls": "granary", "a.ppt": "meadow"}
        documents = {name: self._document(name, name.encode()) for name in words}
        for name, document in documents.items():
            self._preview(document, (f"all about the {words[name]}",))
        self._read_all()
        for name, document in documents.items():
            with self.subTest(name=name):
                self.assertEqual(self._found(words[name]), document)

    def test_documents_with_the_same_file_share_the_row(self):
        first = self._document("one.doc", b"same bytes")
        second = self._document("two.doc", b"same bytes", self.env["int.filemanager.folder"].create({"name": "Other"}))
        self._preview(first)
        self.assertEqual(self.Text._create_rows(1000), 1)
        self._read_all()
        self.assertEqual(self._found("sheet"), first + second)

    def test_an_archived_document_gets_no_row(self):
        document = self._document("old.doc", b"binary text")
        self._preview(document)
        document.action_archive()
        self.assertEqual(self.Text._create_rows(1000), 0)

    def test_the_old_formats_are_never_sent_to_the_text_recognition(self):
        document = self._document("old.xls", b"binary sheet")
        self._preview(document)
        self._read_all()
        self.assertEqual(self._text_of(document).scan_pages, 0)

    def test_a_row_whose_preview_is_gone_fails(self):
        document = self._document("old.xls", b"binary sheet")
        checksum = self._preview(document)
        self.Text._create_rows(1000)
        os.unlink(self.Document._blob_path(checksum))
        self._read_all()
        self.assertEqual(self._text_of(document).state, "failed")

    def test_without_the_pdf_reader_the_old_formats_wait(self):
        document = self._document("old.xls", b"binary sheet")
        self._preview(document)
        with patch(f"{MODULE}.importlib.util.find_spec", return_value=None):
            self.assertEqual(self.Text._create_rows(1000), 0)
        self.assertFalse(self._text_of(document))

    def test_the_new_formats_are_still_read_from_the_file_itself(self):
        document = self._document("new.docx", text_files.docx(["words of the new format"]))
        self._read_all()
        self.assertEqual(self._found("format"), document)
        self.assertFalse(document.preview_checksum)

    def test_the_scheduled_action_reads_a_file_when_its_preview_is_there(self):
        document = self._document("old.ppt", b"binary slides")
        self._preview(document, ("slide about the harvest",))
        cron = self.env.ref("int_filemanager.int_filemanager_text_cron")
        self.Text.with_context(cron_id=cron.id)._cron_ocr()
        self.env.invalidate_all()
        self.assertEqual(self._found("harvest"), document)
