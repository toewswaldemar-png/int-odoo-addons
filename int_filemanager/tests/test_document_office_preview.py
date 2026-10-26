import io
import os
import shutil
import subprocess
import time
from unittest import skipUnless
from unittest.mock import patch

from pdfminer.high_level import extract_text

from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.int_filemanager.models.int_filemanager_document import (
    PREVIEW_CRON_XMLID,
    THUMBNAIL_CRON_XMLID,
    PREVIEW_EXTENSIONS,
)

from . import text_files
from .test_folder_access import AccessCase, remove

MODULE = "odoo.addons.int_filemanager.models.int_filemanager_document_rendition"
PREVIEW = b"%PDF-1.4 the preview of an office file"
SOFFICE = "/usr/bin/soffice"


class FakeLibreOffice:
    """Stands in for ``subprocess.run``: writes the PDF where LibreOffice would, or fails."""

    def __init__(self, content=PREVIEW, code=0, error=b"", make=True):
        self.content, self.code, self.error, self.make = content, code, error, make
        self.calls = []
        self.sources = []

    def __call__(self, command, **kwargs):
        self.calls.append(command)
        source = command[-1]
        # The job folder is gone when the test looks: note where the link points now.
        self.sources.append((os.path.basename(source), os.path.realpath(source)))
        if self.make:
            stem = os.path.splitext(os.path.basename(source))[0]
            with open(os.path.join(command[command.index("--outdir") + 1], f"{stem}.pdf"), "wb") as handle:
                handle.write(self.content)
        return subprocess.CompletedProcess(command, self.code, b"", self.error)


class OfficeCase(AccessCase):
    def setUp(self):
        super().setUp()
        # Less than the budget of a test run, so that more than one file is started.
        self.env["ir.config_parameter"].sudo().set_param("int_filemanager.preview_seconds", "10")

    def _forget(self, checksum):
        remove(self.Document._blob_path(checksum))
        remove(os.path.join(self.Document._checklist_dir(), checksum[:2], checksum))

    def _office(self, name="a.docx", content=None, folder=None):
        return self._document(folder or self.shared, name, content or text_files.docx(["Hello"]))

    def _cron(self, run=None, found=SOFFICE):
        """Run the scheduled action as Odoo does, without the commit a test must not make."""
        run = run or FakeLibreOffice()
        cron = self.env.ref(PREVIEW_CRON_XMLID)
        with (
            patch.object(self.env.cr, "commit"),
            patch(f"{MODULE}.subprocess.run", run),
            patch(f"{MODULE}.shutil.which", return_value=found),
        ):
            self.Document.with_context(cron_id=cron.id)._cron_previews()
        for checksum in self.Document.with_context(active_test=False).search([]).mapped("preview_checksum"):
            if checksum:
                self.addCleanup(self._forget, checksum)
        return run


@tagged("post_install", "-at_install")
class TestOfficePreview(OfficeCase, TransactionCase):
    """The PDF that LibreOffice makes of a Word, Excel or PowerPoint file, for the viewer."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._set_up_access()

    # --- The conversion ----------------------------------------------------------

    def test_an_office_file_waits_for_its_preview_after_the_upload(self):
        document = self._office()
        self.assertEqual(document.mimetype, next(t for t, e in PREVIEW_EXTENSIONS.items() if e == "docx"))
        self.assertFalse(document.preview_state)
        self.assertIn(document, self.Document.search(self.Document._preview_domain()))

    def test_the_upload_wakes_the_scheduled_action_for_an_office_file_only(self):
        cron = self.env.ref(PREVIEW_CRON_XMLID)
        triggers = self.env["ir.cron.trigger"].search_count([("cron_id", "=", cron.id)])
        self._document(self.shared, "a.txt", b"hello")
        self.assertEqual(self.env["ir.cron.trigger"].search_count([("cron_id", "=", cron.id)]), triggers)
        self._office()
        self.assertEqual(self.env["ir.cron.trigger"].search_count([("cron_id", "=", cron.id)]), triggers + 1)

    def test_a_made_preview_wakes_the_action_of_the_picture(self):
        triggers = self.env["ir.cron.trigger"]
        crons = self.env.ref("int_filemanager.int_filemanager_thumbnail_cron")
        before = triggers.search_count([("cron_id", "in", crons.ids)])
        self._office()
        self._cron()
        self.assertEqual(triggers.search_count([("cron_id", "in", crons.ids)]), before + 1)

    def test_a_run_starts_no_further_file_when_its_time_is_short(self):
        # The core's window (``cron_end_time``) is 10 s and says nothing of the limit that kills
        # the worker: ``int.filemanager.cron._pass_deadline`` does, see its docstring.
        documents = self._office("a.docx", text_files.docx(["one"])) + self._office("b.docx", text_files.docx(["two"]))
        reported = []
        cron_model = type(self.env["ir.cron"])
        with (
            # 3 s are left, one file may take 10: the first one is always started, the second is not
            patch.object(
                type(self.env["int.filemanager.cron"]), "_pass_deadline", lambda *_args: time.monotonic() + 3
            ),
            patch.object(
                cron_model, "_commit_progress", lambda _self, *args, **kw: reported.append((args, kw)) or float("inf")
            ),
        ):
            run = self._cron()
        self.assertEqual(len(run.calls), 1)
        self.assertEqual(len(documents.filtered("preview_state")), 1)
        self.assertEqual(reported[-1], ((0,), {"remaining": 1}))
        # the next run, with its own time, gets the other one
        self._cron()
        self.assertEqual(documents.mapped("preview_state"), ["done", "done"])

    def test_the_scheduled_action_makes_the_preview_from_a_link_that_has_the_ending(self):
        document = self._office("report.docx")
        run = self._cron()
        self.assertEqual(document.preview_state, "done")
        self.assertTrue(document.preview_checksum)
        with open(self.Document._blob_path(document.preview_checksum), "rb") as handle:
            self.assertEqual(handle.read(), PREVIEW)
        # LibreOffice is told the format by the ending, and reads the blob through the link.
        self.assertEqual(run.sources, [("file.docx", self.Document._blob_path(document.checksum))])
        command = run.calls[0]
        self.assertEqual(command[:3], ["nice", "-n", command[2]])
        self.assertIn("timeout", command)
        self.assertIn("--convert-to", command)
        self.assertNotIn(document, self.Document.search(self.Document._preview_domain()))

    def test_every_type_gets_the_ending_of_its_format(self):
        names = {
            "a.doc": "doc",
            "a.docx": "docx",
            "a.rtf": "rtf",
            "a.odt": "odt",
            "a.xls": "xls",
            "a.xlsx": "xlsx",
            "a.ods": "ods",
            "a.ppt": "ppt",
            "a.pptx": "pptx",
            "a.odp": "odp",
        }
        for name, extension in names.items():
            with self.subTest(name=name):
                document = self._office(name, name.encode())
                self.assertIn(document.mimetype, PREVIEW_EXTENSIONS)
                run = self._cron()
                self.assertEqual(run.sources[0][0], f"file.{extension}")

    def test_a_file_of_another_type_gets_no_preview(self):
        pdf = self._document(self.shared, "a.pdf", text_files.pdf(["x"]))
        text = self._document(self.shared, "a.txt", b"hello")
        run = self._cron()
        self.assertFalse(run.calls)
        self.assertFalse(pdf.preview_state or text.preview_state)

    def test_documents_with_the_same_file_share_one_conversion(self):
        first = self._office("one.docx")
        second = self._office("two.docx", folder=self.deep)
        self.assertEqual(first.checksum, second.checksum)
        run = self._cron()
        self.assertEqual(len(run.calls), 1)
        self.assertEqual((first.preview_state, second.preview_state), ("done", "done"))
        self.assertEqual(first.preview_checksum, second.preview_checksum)

    def test_a_copy_that_comes_later_takes_the_preview_of_the_first(self):
        first = self._office("one.docx")
        self._cron()
        second = self._office("two.docx", folder=self.deep)
        run = self._cron()
        self.assertFalse(run.calls)
        self.assertEqual((second.preview_state, second.preview_checksum), ("done", first.preview_checksum))

    def test_an_archived_document_gets_its_preview_too(self):
        document = self._office()
        document.action_archive()
        self._cron()
        self.assertEqual(document.preview_state, "done")

    # --- The picture -------------------------------------------------------------

    def _thumbnails(self):
        cron = self.env.ref(THUMBNAIL_CRON_XMLID)
        with patch.object(self.env.cr, "commit"):
            self.Document.with_context(cron_id=cron.id)._cron_thumbnails()

    def test_an_office_file_waits_for_its_picture_only_when_it_has_a_preview(self):
        document = self._office()
        self.assertNotIn(document, self.Document.search(self.Document._thumbnail_domain()))
        self._cron()
        self.assertIn(document, self.Document.search(self.Document._thumbnail_domain()))

    def test_the_picture_is_the_first_page_of_the_preview(self):
        document = self._office()
        other = self._office("two.docx", text_files.docx(["Two"]), folder=self.deep)
        self._cron(FakeLibreOffice(content=text_files.pdf(["First page", "Second page"])))
        self._thumbnails()
        for each in document + other:
            self.assertEqual(each.thumbnail_state, "done")
            self.assertTrue(each.thumbnail)
        self.assertNotIn(document, self.Document.search(self.Document._thumbnail_domain()))

    def test_a_preview_that_cannot_be_drawn_fails_the_picture_only(self):
        document = self._office()
        self._cron()
        self._thumbnails()
        self.assertEqual((document.preview_state, document.thumbnail_state), ("done", "failed"))

    def test_another_file_for_the_document_drops_the_old_picture(self):
        document = self._office()
        self._cron(FakeLibreOffice(content=text_files.pdf(["First page"])))
        self._thumbnails()
        self.assertTrue(document.thumbnail)
        stored = self.Document._store_stream(io.BytesIO(text_files.docx(["New"])), "n.docx")
        self.Document._publish_blob(stored["tmp_path"], stored["checksum"])
        self.addCleanup(self._forget, stored["checksum"])
        document.sudo().write({"checksum": stored["checksum"]})
        self.assertFalse(document.thumbnail)
        self.assertFalse(document.thumbnail_state)

    # --- What goes wrong ---------------------------------------------------------

    def test_a_file_that_cannot_be_converted_fails_and_is_not_tried_again(self):
        document = self._office()
        run = FakeLibreOffice(code=1, error=b"Error: source file could not be loaded", make=False)
        self._cron(run)
        self._cron(run)
        self.assertEqual(document.preview_state, "failed")
        self.assertFalse(document.preview_checksum)
        self.assertEqual(len(run.calls), 1)

    def test_a_conversion_that_takes_too_long_fails(self):
        document = self._office()
        self._cron(FakeLibreOffice(code=124, make=False))
        self.assertEqual(document.preview_state, "failed")

    def test_a_run_that_gives_no_file_fails(self):
        document = self._office()
        self._cron(FakeLibreOffice(make=False))
        self.assertEqual(document.preview_state, "failed")

    def test_a_result_that_is_no_pdf_fails(self):
        document = self._office()
        self._cron(FakeLibreOffice(content=b"just some words"))
        self.assertEqual(document.preview_state, "failed")
        self.assertFalse(document.preview_checksum)

    def test_a_file_above_the_size_limit_fails_without_a_conversion(self):
        self.env["ir.config_parameter"].sudo().set_param("int_filemanager.preview_max_size_mib", "1")
        document = self._office(content=text_files.docx(["Hello"]) + b"\0" * (1024**2 + 1))
        run = self._cron()
        self.assertFalse(run.calls)
        self.assertEqual(document.preview_state, "failed")

    def test_the_size_limit_is_a_setting(self):
        self.env["ir.config_parameter"].sudo().set_param("int_filemanager.preview_max_size_mib", "5")
        document = self._office(content=text_files.docx(["Hello"]) + b"\0" * (1024**2 + 1))
        self._cron()
        self.assertEqual(document.preview_state, "done")

    def test_a_missing_blob_fails_the_preview_and_not_the_run(self):
        missing = self._office("missing.docx", text_files.docx(["gone"]))
        other = self._office("other.docx", text_files.docx(["here"]))
        os.unlink(self.Document._blob_path(missing.checksum))
        self._cron()
        self.assertEqual(missing.preview_state, "failed")
        self.assertEqual(other.preview_state, "done")

    def test_without_libreoffice_nothing_is_marked(self):
        document = self._office()
        run = self._cron(found=None)
        self.assertFalse(run.calls)
        self.assertFalse(document.preview_state)

    def test_the_switch_in_the_settings_stops_the_conversion(self):
        self.env["ir.config_parameter"].sudo().set_param("int_filemanager.preview_enabled", "0")
        document = self._office()
        run = self._cron()
        self.assertFalse(run.calls)
        self.assertFalse(document.preview_state)

    def test_the_scheduled_action_refuses_to_run_by_hand(self):
        with self.assertRaises(AssertionError):
            self.Document._cron_previews()

    # --- The rights --------------------------------------------------------------

    def test_a_user_cannot_set_the_preview_or_its_state(self):
        document = self._office()
        document.with_user(self.alice).write(
            {"preview_checksum": "a" * 64, "preview_state": "done", "name": "b.docx"}
        )
        self.assertEqual(document.name, "b.docx")
        self.assertFalse(document.preview_checksum)
        self.assertFalse(document.preview_state)

    def test_the_preview_follows_the_rights_of_the_document(self):
        document = self._office("secret.docx", folder=self.secret)
        self._invite(self.secret, self.alice)
        self._cron()
        Binary = self.env["ir.binary"]
        found = Binary.with_user(self.alice)._find_record(
            res_model=document._name, res_id=document.id, field="viewer_pdf_content"
        )
        self.assertEqual(Binary._get_stream_from(found, "viewer_pdf_content").mimetype, "application/pdf")
        with self.assertRaises(AccessError):
            Binary.with_user(self.bob)._find_record(
                res_model=document._name, res_id=document.id, field="viewer_pdf_content"
            )

    def test_the_viewer_gets_the_preview_and_the_download_stays_the_original(self):
        document = self._office()
        self._cron()
        Binary = self.env["ir.binary"]
        preview = Binary._get_stream_from(document, "viewer_pdf_content")
        original = Binary._get_stream_from(document, "content")
        self.assertEqual(preview.path, self.Document._blob_path(document.preview_checksum))
        self.assertEqual((preview.mimetype, preview.etag), ("application/pdf", document.preview_checksum))
        self.assertEqual(original.path, self.Document._blob_path(document.checksum))
        self.assertEqual(original.mimetype, document.mimetype)
        self.assertEqual(document.viewer_pdf_checksum, document.preview_checksum)

    def test_a_file_without_a_preview_has_none_to_stream(self):
        document = self._office()
        self.assertFalse(document.viewer_pdf_checksum)
        with self.assertRaisesRegex(UserError, "no PDF"):
            self.env["ir.binary"]._get_stream_from(document, "viewer_pdf_content")

    def test_the_preview_is_not_copied_and_not_exported(self):
        document = self._office()
        self._cron()
        copied = document.copy_data()[0]
        self.assertNotIn("preview_checksum", copied)
        self.assertNotIn("preview_state", copied)
        self.assertFalse(self.Document.fields_get(["preview_checksum"])["preview_checksum"]["exportable"])

    # --- The blobs ---------------------------------------------------------------

    def _marker(self, checksum):
        return os.path.join(self.Document._checklist_dir(), checksum[:2], checksum)

    def test_the_preview_of_a_deleted_document_goes_on_the_checklist(self):
        document = self._office()
        self._cron()
        checksum = document.preview_checksum
        remove(self._marker(checksum))
        document.unlink()
        self.assertTrue(os.path.exists(self._marker(checksum)))

    def test_another_file_for_the_document_drops_the_old_preview(self):
        document = self._office()
        self._cron()
        old = document.preview_checksum
        remove(self._marker(old))
        stored = self.Document._store_stream(io.BytesIO(text_files.docx(["New"])), "n.docx")
        self.Document._publish_blob(stored["tmp_path"], stored["checksum"])
        self.addCleanup(self._forget, stored["checksum"])
        document.sudo().write({"checksum": stored["checksum"]})
        self.assertFalse(document.preview_checksum)
        self.assertFalse(document.preview_state)
        self.assertTrue(os.path.exists(self._marker(old)))

    def test_the_cleaner_keeps_the_preview_of_a_document_and_deletes_it_after(self):
        document = self._office()
        self._cron()
        checksum = document.preview_checksum
        cr = self.env.cr
        cr.execute("SAVEPOINT preview_cleaner")

        def rollback():
            cr.execute("ROLLBACK TO SAVEPOINT preview_cleaner")

        with patch.object(cr, "commit"), patch.object(cr, "rollback", rollback):
            self.Document._gc_blobs()
            self.assertTrue(os.path.exists(self.Document._blob_path(checksum)))
            document.unlink()
            self.Document._gc_blobs()
        self.assertFalse(os.path.exists(self.Document._blob_path(checksum)))

    # --- The settings ------------------------------------------------------------

    def test_the_settings_count_the_files_by_state(self):
        self._office("one.docx", text_files.docx(["1"]))
        self._office("two.docx", text_files.docx(["2"]))
        self._cron(FakeLibreOffice(code=1, make=False))
        self._office("three.docx", text_files.docx(["3"]))
        counts = self.Document._preview_counts()
        self.assertEqual((counts["failed"], counts[False], counts["done"]), (2, 1, 0))
        settings = self.env["res.config.settings"].create({})
        with patch("odoo.addons.int_filemanager.models.res_config_settings.shutil.which", return_value=None):
            settings.invalidate_recordset()
            self.assertIn("not installed", settings.int_filemanager_preview_state)
        self.assertEqual(settings.int_filemanager_preview_failed, 2)
        self.assertEqual(settings.int_filemanager_preview_waiting, 1)


@tagged("post_install", "-at_install")
class TestLibreOffice(OfficeCase, TransactionCase):
    """The real program, where it is installed (the image of the server has it)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._set_up_access()

    @skipUnless(shutil.which("soffice"), "LibreOffice is not installed")
    def test_libreoffice_turns_a_rich_text_file_into_a_pdf_with_its_words(self):
        document = self._office("letter.rtf", rb"{\rtf1\ansi\deff0 Hello preview of the office file\par}")
        with patch.object(self.env.cr, "commit"):
            self.Document.with_context(cron_id=self.env.ref(PREVIEW_CRON_XMLID).id)._cron_previews()
        self.assertEqual(document.preview_state, "done")
        self.addCleanup(self._forget, document.preview_checksum)
        path = self.Document._blob_path(document.preview_checksum)
        with open(path, "rb") as handle:
            self.assertEqual(handle.read(5), b"%PDF-")
        self.assertIn("Hello preview of the office file", extract_text(path))
