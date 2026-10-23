import base64
import io
import os
import subprocess
import sys
import tempfile
from unittest.mock import patch

from PIL import Image

from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.int_filemanager.models.int_filemanager_document import THUMBNAIL_CRON_XMLID
from odoo.addons.int_filemanager.models.int_filemanager_document_rendition import PDF_THUMBNAIL, THUMBNAIL_SIZE

from . import text_files
from .test_folder_access import AccessCase

DOCUMENT_MODULE = "odoo.addons.int_filemanager.models.int_filemanager_document_rendition"


@tagged("post_install", "-at_install")
class TestDocumentThumbnail(AccessCase, TransactionCase):
    """The first page of a PDF as a small picture, drawn by the scheduled action."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._set_up_access()

    def _cron(self):
        """Run the scheduled action as Odoo does, without the commit a test must not make."""
        cron = self.env.ref(THUMBNAIL_CRON_XMLID)
        with patch.object(self.env.cr, "commit"):
            self.Document.with_context(cron_id=cron.id)._cron_thumbnails()

    def _pdf(self, name="a.pdf", pages=("First page", "Second page"), folder=None):
        return self._document(folder or self.shared, name, text_files.pdf(list(pages)))

    def _picture(self, document):
        return Image.open(io.BytesIO(base64.b64decode(document.thumbnail)))

    # --- The drawing -------------------------------------------------------------

    def test_a_pdf_waits_for_its_picture_after_the_upload(self):
        document = self._pdf()
        self.assertFalse(document.thumbnail_state)
        self.assertFalse(document.thumbnail)
        self.assertIn(document, self.Document.search(self.Document._thumbnail_domain()))

    def test_the_scheduled_action_draws_the_first_page(self):
        document = self._pdf()
        self._cron()
        self.assertEqual(document.thumbnail_state, "done")
        picture = self._picture(document)
        self.assertEqual(picture.format, "JPEG")
        # A Letter page, the longer side is the size asked for.
        self.assertEqual(max(picture.size), THUMBNAIL_SIZE)
        self.assertNotIn(document, self.Document.search(self.Document._thumbnail_domain()))

    def test_a_file_of_another_type_gets_no_picture(self):
        document = self._document(self.shared, "a.txt", b"hello")
        self._cron()
        self.assertFalse(document.thumbnail_state)
        self.assertNotIn(document, self.Document.search(self.Document._thumbnail_domain()))

    def test_a_document_that_is_archived_gets_its_picture_too(self):
        # It is shown again when it is restored: the picture is ready then.
        document = self._pdf()
        document.action_archive()
        self._cron()
        self.assertEqual(document.thumbnail_state, "done")

    def test_documents_with_the_same_file_share_one_drawing(self):
        first = self._pdf("one.pdf")
        second = self._pdf("two.pdf", folder=self.deep)
        self.assertEqual(first.checksum, second.checksum)
        with patch(f"{DOCUMENT_MODULE}.subprocess.run", wraps=subprocess.run) as run:
            self._cron()
        self.assertEqual(run.call_count, 1)
        self.assertEqual((first.thumbnail_state, second.thumbnail_state), ("done", "done"))
        self.assertEqual(first.thumbnail, second.thumbnail)

    def test_a_file_that_cannot_be_drawn_fails_and_is_not_tried_again(self):
        document = self._document(self.shared, "broken.pdf", b"%PDF-1.4 and then nothing")
        with patch(f"{DOCUMENT_MODULE}.subprocess.run", wraps=subprocess.run) as run:
            self._cron()
            self._cron()
        self.assertEqual(document.thumbnail_state, "failed")
        self.assertFalse(document.thumbnail)
        self.assertEqual(run.call_count, 1)

    def test_a_missing_blob_fails_the_picture_and_not_the_run(self):
        missing = self._pdf("missing.pdf", pages=("gone",))
        other = self._pdf("other.pdf", pages=("here",))
        os.unlink(self.Document._blob_path(missing.checksum))
        self._cron()
        self.assertEqual(missing.thumbnail_state, "failed")
        self.assertEqual(other.thumbnail_state, "done")

    def test_a_drawing_that_takes_too_long_fails(self):
        document = self._pdf()
        expired = subprocess.TimeoutExpired("pdf_thumbnail", 1)
        with patch(f"{DOCUMENT_MODULE}.subprocess.run", side_effect=expired):
            self._cron()
        self.assertEqual(document.thumbnail_state, "failed")

    def test_without_the_pdf_library_nothing_is_marked(self):
        document = self._pdf()
        with patch(f"{DOCUMENT_MODULE}.importlib.util.find_spec", return_value=None):
            self._cron()
        self.assertFalse(document.thumbnail_state)

    def test_the_scheduled_action_refuses_to_run_by_hand(self):
        with self.assertRaises(AssertionError):
            self.Document._cron_thumbnails()

    # --- The rights --------------------------------------------------------------

    def test_a_user_cannot_set_the_picture_or_its_state(self):
        document = self._pdf()
        picture = base64.b64encode(text_files.pdf(["not a picture"]))
        document.with_user(self.alice).write({"thumbnail": picture, "thumbnail_state": "done", "name": "b.pdf"})
        self.assertEqual(document.name, "b.pdf")
        self.assertFalse(document.thumbnail)
        self.assertFalse(document.thumbnail_state)

    def test_the_picture_follows_the_rights_of_the_document(self):
        document = self._pdf("secret.pdf", folder=self.secret)
        self._invite(self.secret, self.alice)
        self._cron()
        # What ``/web/image`` does first: find the record with the rights of the user.
        Binary = self.env["ir.binary"]
        found = Binary.with_user(self.alice)._find_record(
            res_model=document._name, res_id=document.id, field="thumbnail"
        )
        self.assertEqual(Image.open(io.BytesIO(base64.b64decode(found.thumbnail))).format, "JPEG")
        with self.assertRaises(AccessError):
            Binary.with_user(self.bob)._find_record(
                res_model=document._name, res_id=document.id, field="thumbnail"
            )

    def test_the_picture_is_not_copied_and_not_exported(self):
        document = self._pdf()
        self._cron()
        copied = document.copy_data()[0]
        self.assertNotIn("thumbnail", copied)
        self.assertNotIn("thumbnail_state", copied)
        fields = self.Document.fields_get(["thumbnail"])
        self.assertFalse(fields["thumbnail"]["exportable"])

    def test_the_picture_is_deleted_with_its_document(self):
        document = self._pdf()
        self._cron()
        attachment = self.env["ir.attachment"].search(
            [("res_model", "=", document._name), ("res_id", "=", document.id), ("res_field", "=", "thumbnail")]
        )
        self.assertEqual(len(attachment), 1)
        document.unlink()
        self.assertFalse(attachment.exists())


@tagged("post_install", "-at_install")
class TestPdfThumbnailTool(TransactionCase):
    """The child process: a JPEG on stdout, or a reason on stderr and exit code 1."""

    def _run(self, content, size=128, memory=1024):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "file")
            with open(path, "wb") as handle:
                handle.write(content)
            return subprocess.run(
                [sys.executable, "-I", PDF_THUMBNAIL, path, str(size), str(memory)],
                capture_output=True,
                check=False,
                timeout=120,
            )

    def test_the_first_page_is_drawn_to_fit_the_square(self):
        done = self._run(text_files.pdf(["First page", "Second page"]), size=128)
        self.assertEqual(done.returncode, 0)
        picture = Image.open(io.BytesIO(done.stdout))
        self.assertEqual(picture.format, "JPEG")
        # 612 x 792 points: the height is the longer side.
        self.assertEqual(picture.size[1], 128)
        self.assertLess(picture.size[0], 128)

    def test_a_page_with_text_is_not_blank(self):
        done = self._run(text_files.pdf(["A lot of text " * 20]))
        picture = Image.open(io.BytesIO(done.stdout)).convert("L")
        self.assertLess(picture.getextrema()[0], 200)

    def test_a_file_that_is_no_pdf_says_why(self):
        done = self._run(b"not a pdf at all")
        self.assertEqual(done.returncode, 1)
        self.assertFalse(done.stdout)
        self.assertTrue(done.stderr.strip())

    def test_a_pdf_without_pages_says_why(self):
        done = self._run(text_files.pdf([]))
        self.assertEqual(done.returncode, 1)
        self.assertFalse(done.stdout)
        self.assertTrue(done.stderr.strip())
