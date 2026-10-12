import io
import os

from odoo.exceptions import UserError
from odoo.tests.common import HttpCase, TransactionCase, new_test_user, tagged
from odoo.tools import config


def remove(path):
    if os.path.exists(path):
        os.unlink(path)


class DownloadCase:
    """Documents with a real blob, and the cleanup of it."""

    def _document(self, name="a.txt", content=b"0123456789", folder=None):
        document = self.env["int.filemanager.document"]._create_from_stream(
            io.BytesIO(content), name, folder or self.folder
        )
        self.addCleanup(remove, document._blob_path(document.checksum))
        return document

    def _url(self, document, download=True):
        return f"/web/content/int.filemanager.document/{document.id}/content" + (
            "?download=true" if download else ""
        )


@tagged("post_install", "-at_install")
class TestDocumentStream(DownloadCase, TransactionCase):
    """The hook ``ir.binary._record_to_stream`` turns a document into a stream of its blob."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.folder = cls.env["int.filemanager.folder"].create({"name": "Downloads"})

    def test_a_document_is_streamed_from_its_blob(self):
        document = self._document("report.pdf", b"%PDF-1.4 content")
        stream = self.env["ir.binary"]._get_stream_from(document, "content")
        self.assertEqual(stream.type, "path")
        self.assertEqual(stream.path, document._blob_path(document.checksum))
        self.assertEqual(stream.mimetype, "application/pdf")
        self.assertEqual(stream.etag, document.checksum)
        self.assertEqual(stream.download_name, "report.pdf")
        self.assertEqual(stream.size, len(b"%PDF-1.4 content"))
        self.assertEqual(stream.last_modified, document.write_date)

    def test_the_path_lies_below_the_filestore_for_x_sendfile(self):
        document = self._document()
        stream = self.env["ir.binary"]._get_stream_from(document, "content")
        filestore = os.path.join(config["data_dir"], "filestore")
        self.assertEqual(os.path.commonpath([stream.path, filestore]), filestore)

    def test_a_missing_blob_is_a_missing_record_and_not_an_error(self):
        document = self._document()
        os.unlink(document._blob_path(document.checksum))
        with self.assertRaisesRegex(UserError, "missing"):
            self.env["ir.binary"]._get_stream_from(document, "content")

    def test_the_content_field_holds_nothing(self):
        document = self._document()
        self.assertFalse(document.content)
        self.assertFalse(document.read(["content"])[0]["content"])
        self.assertNotIn("content", document.copy_data()[0])
        description = self.env["int.filemanager.document"].fields_get(["content"])["content"]
        self.assertFalse(description["exportable"])
        self.assertFalse(description["store"])

    def test_the_content_field_cannot_be_written(self):
        document = self._document()
        with self.assertRaises(UserError):
            document.write({"content": "aGVsbG8="})


@tagged("post_install", "-at_install")
class TestDocumentDownload(DownloadCase, HttpCase):
    """``/web/content/int.filemanager.document/<id>/content``: the core route, our hook."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.folder = cls.env["int.filemanager.folder"].create({"name": "Downloads"})
        cls.user = new_test_user(
            cls.env,
            login="download_user",
            groups="base.group_user,int_filemanager.int_filemanager_group_user",
        )
        cls.outsider = new_test_user(cls.env, login="download_outsider", groups="base.group_user")

    def setUp(self):
        super().setUp()
        self.authenticate("download_user", "download_user")

    def test_the_download_delivers_the_file(self):
        document = self._document("a.txt", b"0123456789")
        response = self.url_open(self._url(document))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"0123456789")
        self.assertTrue(response.headers["Content-Type"].startswith("text/plain"))
        self.assertIn("attachment", response.headers["Content-Disposition"])
        self.assertIn("a.txt", response.headers["Content-Disposition"])
        self.assertEqual(response.headers["ETag"].strip('"'), document.checksum)
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response.headers["Content-Security-Policy"], "default-src 'none'")

    def test_a_range_is_answered_with_206(self):
        document = self._document()
        response = self.url_open(self._url(document), headers={"Range": "bytes=2-4"})
        self.assertEqual(response.status_code, 206)
        self.assertEqual(response.content, b"234")
        self.assertEqual(response.headers["Content-Range"], "bytes 2-4/10")

    def test_a_range_beyond_the_end_is_answered_with_416(self):
        document = self._document()
        response = self.url_open(self._url(document), headers={"Range": "bytes=50-60"})
        self.assertEqual(response.status_code, 416)

    def test_an_unchanged_file_is_answered_with_304(self):
        document = self._document()
        etag = self.url_open(self._url(document)).headers["ETag"]
        response = self.url_open(self._url(document), headers={"If-None-Match": etag})
        self.assertEqual(response.status_code, 304)
        self.assertFalse(response.content)

    def test_html_is_delivered_as_plain_text(self):
        document = self._document("page.html", b"<script>alert(1)</script>")
        response = self.url_open(self._url(document, download=False))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers["Content-Type"].startswith("text/plain"))

    def test_with_x_sendfile_the_proxy_delivers_the_file(self):
        document = self._document()
        previous = config["x_sendfile"]
        config.options["x_sendfile"] = True
        self.addCleanup(config.options.__setitem__, "x_sendfile", previous)
        response = self.url_open(self._url(document))
        checksum = document.checksum
        self.assertEqual(
            response.headers["X-Accel-Redirect"],
            f"/web/filestore/{self.env.cr.dbname}/int_filemanager/{checksum[:2]}/{checksum}",
        )
        self.assertFalse(response.content)

    def test_a_user_without_the_right_gets_404(self):
        document = self._document()
        self.authenticate("download_outsider", "download_outsider")
        self.assertEqual(self.url_open(self._url(document)).status_code, 404)

    def test_a_document_of_another_company_gets_404(self):
        other = self.env["res.company"].create({"name": "Other company"})
        foreign = self.env["int.filemanager.folder"].create(
            {"name": "Foreign", "company_id": other.id}
        )
        document = self._document("foreign.txt", folder=foreign)
        self.assertEqual(self.url_open(self._url(document)).status_code, 404)

    def test_a_missing_file_gets_404_and_not_500(self):
        document = self._document()
        os.unlink(document._blob_path(document.checksum))
        self.assertEqual(self.url_open(self._url(document)).status_code, 404)

    def test_a_document_that_does_not_exist_gets_404(self):
        response = self.url_open("/web/content/int.filemanager.document/999999/content")
        self.assertEqual(response.status_code, 404)

    def test_other_models_keep_the_core_behaviour(self):
        attachment = self.env["ir.attachment"].create(
            {"name": "x.txt", "raw": b"core", "public": True}
        )
        response = self.url_open(f"/web/content/{attachment.id}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"core")
