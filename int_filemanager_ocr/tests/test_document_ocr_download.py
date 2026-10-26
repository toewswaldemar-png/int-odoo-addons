import io
import os

from odoo.exceptions import UserError
from odoo.tests.common import HttpCase, TransactionCase, new_test_user, tagged

from odoo.addons.int_filemanager.tests.test_document_download import DownloadCase, remove

RECOGNIZED = b"%PDF-1.4 the recognized copy with a text layer"


class RecognizedCase(DownloadCase):
    """A document and the PDF the text recognition made of it."""

    def _recognized(self, document, content=RECOGNIZED):
        """Give the file of ``document`` a recognized PDF, as the recognition does."""
        Document = self.env["int.filemanager.document"]
        stored = Document._store_stream(io.BytesIO(content), "recognized.pdf", "application/pdf")
        Document._publish_blob(stored["tmp_path"], stored["checksum"])
        self.addCleanup(remove, Document._blob_path(stored["checksum"]))
        self.addCleanup(
            remove, os.path.join(Document._checklist_dir(), stored["checksum"][:2], stored["checksum"])
        )
        row = self.env["int.filemanager.text"].search([("checksum", "=", document.checksum)])
        values = {"ocr_checksum": stored["checksum"], "ocr_size": stored["size"]}
        if row:
            row.write(values)
        else:
            self.env["int.filemanager.text"].create({"checksum": document.checksum, **values})
        document.invalidate_recordset(["ocr_checksum"])
        return stored["checksum"]

    def _ocr_url(self, document):
        return f"/web/content/int.filemanager.document/{document.id}/ocr_content"


@tagged("post_install", "-at_install")
class TestRecognizedStream(RecognizedCase, TransactionCase):
    """The hook ``ir.binary._record_to_stream`` also knows the recognized PDF."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.folder = cls.env["int.filemanager.folder"].create({"name": "Scans", "access_mode": "open"})

    def test_the_recognized_pdf_is_streamed_from_its_blob(self):
        document = self._document("scan.pdf", b"%PDF-1.4 the scan")
        checksum = self._recognized(document)
        stream = self.env["ir.binary"]._get_stream_from(document, "ocr_content")
        self.assertEqual(stream.type, "path")
        self.assertEqual(stream.path, document._blob_path(checksum))
        self.assertEqual(stream.mimetype, "application/pdf")
        self.assertEqual(stream.etag, checksum)
        self.assertEqual(stream.size, len(RECOGNIZED))
        self.assertEqual(stream.download_name, "scan.pdf")

    def test_the_original_is_still_the_content(self):
        document = self._document("scan.pdf", b"%PDF-1.4 the scan")
        self._recognized(document)
        stream = self.env["ir.binary"]._get_stream_from(document, "content")
        self.assertEqual(stream.path, document._blob_path(document.checksum))

    def test_a_document_without_a_recognized_pdf_has_none_to_stream(self):
        document = self._document("scan.pdf", b"%PDF-1.4 the scan")
        with self.assertRaisesRegex(UserError, "no PDF"):
            self.env["ir.binary"]._get_stream_from(document, "ocr_content")

    def test_a_missing_recognized_blob_is_a_missing_record(self):
        document = self._document("scan.pdf", b"%PDF-1.4 the scan")
        checksum = self._recognized(document)
        os.unlink(document._blob_path(checksum))
        with self.assertRaisesRegex(UserError, "missing"):
            self.env["ir.binary"]._get_stream_from(document, "ocr_content")

    def test_the_checksum_is_known_to_the_documents_with_the_same_file(self):
        first = self._document("a.pdf", b"%PDF-1.4 same")
        second = self._document("b.pdf", b"%PDF-1.4 same")
        other = self._document("c.pdf", b"%PDF-1.4 other")
        checksum = self._recognized(first)
        self.assertEqual((first + second + other).mapped("ocr_checksum"), [checksum, checksum, False])

    def test_a_row_without_a_recognized_pdf_gives_no_checksum(self):
        document = self._document("a.pdf", b"%PDF-1.4 plain")
        self.env["int.filemanager.text"].create({"checksum": document.checksum})
        self.assertFalse(document.ocr_checksum)

    def test_the_field_holds_nothing_and_cannot_be_written(self):
        document = self._document("a.pdf", b"%PDF-1.4 plain")
        self.assertFalse(document.ocr_content)
        with self.assertRaises(UserError):
            document.write({"ocr_content": "aGVsbG8="})
        description = self.env["int.filemanager.document"].fields_get(["ocr_content", "ocr_checksum"])
        self.assertFalse(description["ocr_content"]["exportable"])
        self.assertFalse(description["ocr_checksum"]["exportable"])


@tagged("post_install", "-at_install")
class TestRecognizedDownload(RecognizedCase, HttpCase):
    """``/web/content/int.filemanager.document/<id>/ocr_content``: the core route, our hook."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.folder = cls.env["int.filemanager.folder"].create({"name": "Scans", "access_mode": "open"})
        cls.user = new_test_user(
            cls.env,
            login="ocr_download_user",
            groups="base.group_user,int_filemanager.int_filemanager_group_user",
        )
        cls.outsider = new_test_user(cls.env, login="ocr_download_outsider", groups="base.group_user")

    def setUp(self):
        super().setUp()
        self.authenticate("ocr_download_user", "ocr_download_user")

    def test_the_route_delivers_the_recognized_pdf(self):
        document = self._document("scan.pdf", b"%PDF-1.4 the scan")
        checksum = self._recognized(document)
        response = self.url_open(self._ocr_url(document))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, RECOGNIZED)
        self.assertTrue(response.headers["Content-Type"].startswith("application/pdf"))
        self.assertEqual(response.headers["ETag"].strip('"'), checksum)

    def test_the_download_is_the_original_file(self):
        document = self._document("scan.pdf", b"%PDF-1.4 the scan")
        self._recognized(document)
        response = self.url_open(self._url(document))
        self.assertEqual(response.content, b"%PDF-1.4 the scan")
        self.assertIn("attachment", response.headers["Content-Disposition"])

    def test_an_unchanged_pdf_is_answered_with_304(self):
        document = self._document("scan.pdf", b"%PDF-1.4 the scan")
        self._recognized(document)
        etag = self.url_open(self._ocr_url(document)).headers["ETag"]
        response = self.url_open(self._ocr_url(document), headers={"If-None-Match": etag})
        self.assertEqual(response.status_code, 304)

    def test_a_range_is_answered_with_206(self):
        document = self._document("scan.pdf", b"%PDF-1.4 the scan")
        self._recognized(document)
        response = self.url_open(self._ocr_url(document), headers={"Range": "bytes=0-3"})
        self.assertEqual((response.status_code, response.content), (206, b"%PDF"))

    def test_a_user_who_may_not_see_the_document_gets_404(self):
        document = self._document("scan.pdf", b"%PDF-1.4 the scan")
        self._recognized(document)
        self.authenticate("ocr_download_outsider", "ocr_download_outsider")
        self.assertEqual(self.url_open(self._ocr_url(document)).status_code, 404)

    def test_the_recognized_pdf_of_a_document_in_a_folder_of_others_gets_404(self):
        secret = self.env["int.filemanager.folder"].create({"name": "Secret", "access_mode": "restricted"})
        document = self._document("scan.pdf", b"%PDF-1.4 the scan", folder=secret)
        self._recognized(document)
        self.assertEqual(self.url_open(self._ocr_url(document)).status_code, 404)

    def test_a_document_without_a_recognized_pdf_gets_404(self):
        document = self._document("scan.pdf", b"%PDF-1.4 the scan")
        self.assertEqual(self.url_open(self._ocr_url(document)).status_code, 404)
