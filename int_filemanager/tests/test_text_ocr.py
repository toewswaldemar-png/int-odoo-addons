import errno
import io
import json
import os
import shutil
import sys
import tempfile
import time
from unittest.mock import patch

import psutil

from odoo.exceptions import AccessError
from odoo.tests.common import new_test_user, tagged

from odoo.addons.int_filemanager.models.int_filemanager_text import (
    OCR_BLOCK_PARAMETER,
    OCR_IDLE,
    OCR_NO_TIME,
    OCR_PROGRESS,
)
from odoo.addons.int_filemanager.tools import ocr_plan

from . import text_files
from .test_text_search import TextCase

MODULE = "odoo.addons.int_filemanager.models.int_filemanager_text"
ADMIN_GROUPS = "base.group_user,int_filemanager.int_filemanager_group_admin"

# A program that behaves like ``ocrmypdf`` as the test says (``config.json``): it logs its
# arguments, and gives one of the prepared PDFs for the pages it was asked for, or fails.
STUB = """#!@PYTHON@
import json, os, shutil, subprocess, sys, time
config = json.load(open(@CONFIG@))
args = sys.argv[1:]
with open(config["log"], "a") as log:
    log.write(json.dumps(args) + "\\n")
pages = args[args.index("--pages") + 1]
target = args[-1]
mode = config.get("mode", "ok")
if mode == "hang":
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    with open(config["pids"], "w") as handle:
        handle.write("%d %d" % (os.getpid(), child.pid))
    time.sleep(60)
if mode == "exit":
    sys.stderr.write(config["stderr"] + "\\n")
    raise SystemExit(config["code"])
if mode == "needs_dpi" and "--image-dpi" not in args:
    sys.stderr.write("Input file is an image, but has no resolution (DPI) in its metadata.\\n")
    raise SystemExit(2)
if mode == "nofile" or (mode == "force_only" and "--force-ocr" not in args):
    raise SystemExit(0)
shutil.copy(config["outputs"][pages], target)
"""


class OcrCase(TextCase):
    """Scans, and a stub in place of ``ocrmypdf``."""

    def setUp(self):
        super().setUp()
        self.work = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.work, ignore_errors=True)
        self.config_path = os.path.join(self.work, "config.json")
        self.log_path = os.path.join(self.work, "log.txt")
        self.program = os.path.join(self.work, "ocrmypdf")
        with open(self.program, "w", encoding="utf-8") as handle:
            handle.write(
                STUB.replace("@PYTHON@", sys.executable).replace("@CONFIG@", repr(self.config_path))
            )
        os.chmod(self.program, 0o755)
        self.config = {
            "log": self.log_path,
            "pids": os.path.join(self.work, "pids.txt"),
            "outputs": {},
        }
        self._save_config()
        tools = {
            "program": self.program,
            "version": "stub",
            "tesseract": "tesseract",
            "languages": {"deu", "eng", "osd"},
        }
        patcher = patch.object(type(self.Text), "_ocr_tools", lambda *_args: tools)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.env["ir.config_parameter"].set_param("int_filemanager.ocr_enabled", "1")
        self.addCleanup(self._remove_jobs)

    def _remove_jobs(self):
        shutil.rmtree(self.Text._ocr_dir(), ignore_errors=True)

    def _save_config(self, **changes):
        self.config.update(changes)
        with open(self.config_path, "w", encoding="utf-8") as handle:
            json.dump(self.config, handle)

    def _output(self, pages, texts):
        """A PDF for the stub to give when it is asked for ``pages`` ("1-2"); ``texts`` per page."""
        path = os.path.join(self.work, f"out-{pages}.pdf")
        with open(path, "wb") as handle:
            handle.write(text_files.pdf(texts, pictures=range(len(texts))))
        self.config["outputs"][pages] = path
        self._save_config()

    def _calls(self):
        if not os.path.exists(self.log_path):
            return []
        with open(self.log_path, encoding="utf-8") as handle:
            return [json.loads(line) for line in handle]

    def _scan(self, pages=3, name="scan.pdf"):
        """A PDF of pages with a picture and no text, read, and queued for the recognition."""
        document = self._document(name, text_files.pdf([""] * pages, pictures=range(pages)))
        self._read_all()
        self.Text._ocr_queue(100)
        return document, self._text_of(document)

    def _step(self, seconds=100):
        return self.Text._ocr_step(time.monotonic() + seconds)

    def _job(self, row):
        return row._job_dir()


@tagged("post_install", "-at_install")
class TestScans(OcrCase):
    """Which files need the recognition."""

    def test_the_pages_without_text_are_counted_when_a_pdf_is_read(self):
        document = self._document(
            "a.pdf", text_files.pdf(["A page with plenty of words", "", "x"], pictures=range(3))
        )
        self._read_all()
        row = self._text_of(document)
        self.assertEqual((row.state, row.page_count, row.scan_pages), ("done", 3, 2))

    def test_a_page_without_a_picture_is_no_scan(self):
        document = self._document("a.pdf", text_files.pdf(["Plenty of words on this page", "", "x"], pictures=[2]))
        self._read_all()
        row = self._text_of(document)
        self.assertEqual((row.state, row.scan_pages), ("done", 1))
        scans = self.env["int.filemanager.text.page"].search([("text_id", "=", row.id), ("scan", "=", True)])
        self.assertEqual(scans.mapped("page"), [3])
        self.Text._ocr_queue(100)
        self.assertEqual(row.ocr_state, "wait")

    def test_a_file_of_empty_sheets_is_not_queued(self):
        document = self._document("a.pdf", text_files.pdf(["", "", ""]))
        self._read_all()
        self.Text._ocr_queue(100)
        row = self._text_of(document)
        self.assertEqual((row.state, row.scan_pages, row.ocr_state), ("empty", 0, False))

    def test_a_file_without_pages_has_no_scans(self):
        document = self._document("a.txt", b"some text")
        self._read_all()
        self.assertEqual(self._text_of(document).scan_pages, 0)

    def test_a_scan_is_queued_when_the_recognition_is_on(self):
        _document, row = self._scan()
        self.assertEqual((row.state, row.scan_pages, row.ocr_state), ("empty", 3, "wait"))

    def test_nothing_is_queued_when_the_recognition_is_off(self):
        self.env["ir.config_parameter"].set_param("int_filemanager.ocr_enabled", "0")
        _document, row = self._scan()
        self.assertFalse(row.ocr_state)

    def test_a_row_read_before_the_recognition_existed_is_counted_and_queued(self):
        document = self._document(
            "a.pdf", text_files.pdf(["", "words enough for a page of text"], pictures=range(2))
        )
        self._read_all()
        row = self._text_of(document)
        row.write({"scan_pages": -1, "ocr_state": False})
        self.assertEqual(self.Text._ocr_queue(100), 2)
        self.assertEqual((row.scan_pages, row.ocr_state), (1, "wait"))
        self.assertEqual(self.Text._ocr_queue(100), 0)

    def test_a_file_that_is_all_text_is_not_queued(self):
        document = self._document("a.pdf", text_files.pdf(["Plenty of words on page number one", "and plenty of words on page number two"]))
        self._read_all()
        self.Text._ocr_queue(100)
        self.assertFalse(self._text_of(document).ocr_state)

    def test_what_the_settings_say(self):
        Params = self.env["ir.config_parameter"]
        options = self.Text._ocr_options()
        self.assertEqual(
            (options["languages"], options["jobs"], options["nice"], options["deskew"], options["output_type"]),
            ("deu+eng", 1, 19, True, "pdf"),
        )
        Params.set_param("int_filemanager.ocr_languages", "deu; rm -rf /")
        Params.set_param("int_filemanager.ocr_output_type", "tiff")
        Params.set_param("int_filemanager.ocr_deskew", "0")
        Params.set_param("int_filemanager.ocr_nice", "50")
        options = self.Text._ocr_options()
        self.assertEqual(
            (options["languages"], options["deskew"], options["output_type"], options["nice"]),
            ("deu+eng", False, "pdf", 19),
        )
        Params.set_param("int_filemanager.ocr_languages", "deu")
        Params.set_param("int_filemanager.ocr_output_type", "pdfa")
        self.assertEqual(self.Text._ocr_options()["languages"], "deu")
        self.assertEqual(self.Text._ocr_options()["output_type"], "pdfa")

    def test_why_the_recognition_cannot_run(self):
        Params = self.env["ir.config_parameter"]
        self.assertEqual(self.Text._ocr_ready(), (True, None))
        Params.set_param("int_filemanager.ocr_enabled", "0")
        self.assertEqual(self.Text._ocr_ready(), (False, "off"))
        Params.set_param("int_filemanager.ocr_enabled", "1")
        Params.set_param("int_filemanager.ocr_languages", "deu+fra")
        self.assertEqual(self.Text._ocr_ready(), (False, "missing_language"))
        Params.set_param("int_filemanager.ocr_languages", "deu")
        with patch.object(type(self.Text), "_ocr_tools", lambda *_args: {"program": False, "tesseract": "t", "languages": {"deu"}}):
            self.assertEqual(self.Text._ocr_ready(), (False, "missing_dependency"))
        self.Text._ocr_block("disk_full", "no space")
        self.assertEqual(self.Text._ocr_ready(), (False, "disk_full"))


@tagged("post_install", "-at_install")
class TestRecognition(OcrCase):
    """One scan, recognized in steps with a stub as the program."""

    def test_a_scan_is_recognized_published_and_found(self):
        document, row = self._scan(3)
        self._output("1-3", ["first recognized words", "second recognized words", "third recognized words"])
        self.assertEqual(self._step(), OCR_PROGRESS)
        self.assertEqual((row.ocr_state, row.state, row.scan_pages), ("done", "done", 0))
        self.assertTrue(row.ocr_checksum)
        self.assertTrue(os.path.isfile(self.Document._blob_path(row.ocr_checksum)))
        self.assertTrue(os.path.isfile(self.Document._blob_path(document.checksum)))
        self.assertEqual(self._found("second recognized"), document)
        self.assertFalse(row.ocr_file)
        self.assertEqual(self._step(), OCR_IDLE)

    def test_the_program_gets_the_original_the_pages_and_the_settings(self):
        document, _row = self._scan(3)
        self._output("1-3", ["a", "b", "c"])
        self._step()
        [call] = self._calls()
        self.assertEqual(call[:7], ["--skip-text", "--pages", "1-3", "-l", "deu+eng", "-j", "1"])
        self.assertIn("--deskew", call)
        self.assertEqual(call[-2], self.Document._blob_path(document.checksum))
        self.assertTrue(call[-1].endswith("upto-3.pdf.tmp"))

    def test_the_job_folder_is_removed_when_the_transaction_is_committed(self):
        _document, row = self._scan(3)
        self._output("1-3", ["words one", "words two", "words three"])
        self._step()
        job = self._job(row)
        self.assertTrue(os.path.isdir(job))
        self.env.cr.postcommit.run()
        self.assertFalse(os.path.exists(job))

    def test_a_long_file_is_recognized_in_sections_that_build_on_each_other(self):
        document, row = self._scan(5)
        texts = ["alpha one", "alpha two", "alpha three", "alpha four", "alpha five"]
        for first, last in ((1, 2), (3, 4), (5, 5)):
            done = texts[:last] + [""] * (5 - last)
            self._output(f"{first}-{last}" if first != last else str(first), done)
        with patch.object(ocr_plan, "FIRST_SECTION_PAGES", 2), patch.object(ocr_plan, "MAX_SECTION_PAGES", 2):
            self._step()
            self.assertEqual((row.ocr_state, row.ocr_next_page, row.ocr_file), ("wait", 3, "upto-2.pdf"))
            self.assertEqual(self._found("alpha two"), document)
            self.assertFalse(self._found("alpha three"))
            self._step()
            self.assertEqual((row.ocr_next_page, row.ocr_file), (5, "upto-4.pdf"))
            self._step()
        self.assertEqual((row.ocr_state, row.state), ("done", "done"))
        calls = self._calls()
        self.assertEqual([call[call.index("--pages") + 1] for call in calls], ["1-2", "3-4", "5"])
        job = self._job(row)
        self.assertEqual(calls[1][-2], os.path.join(job, "upto-2.pdf"))
        self.assertEqual(calls[2][-2], os.path.join(job, "upto-4.pdf"))
        self.assertEqual(self._found("alpha five"), document)

    def _mixed(self):
        """Seven pages: scans on 2, 3, 5 and 7; text on 1 and 4; an empty sheet on 6."""
        words = "A page with plenty of words"
        texts = [words, "", "", words, "", "", ""]
        document = self._document("mixed.pdf", text_files.pdf(texts, pictures=[1, 2, 4, 6]))
        self._read_all()
        self.Text._ocr_queue(100)
        return document, self._text_of(document)

    def _mixed_output(self, pages):
        texts = ["x", "recognized 2", "recognized 3", "x", "recognized 5", "x", "recognized 7"]
        self._output(pages, texts)

    def test_only_the_scans_of_a_file_are_asked_for(self):
        document, row = self._mixed()
        self.assertEqual((row.scan_pages, row.ocr_state), (4, "wait"))
        self._mixed_output("2-3,5,7")
        self._step()
        [call] = self._calls()
        self.assertEqual(call[call.index("--pages") + 1], "2-3,5,7")
        self.assertEqual((row.ocr_state, row.ocr_found_pages), ("done", 4))
        self.assertEqual(self._found("recognized 5"), document)
        self.assertEqual(self._found("plenty of words"), document)

    def test_sections_are_cut_from_the_list_of_scans(self):
        _document, row = self._mixed()
        self._mixed_output("2-3")
        self._mixed_output("5,7")
        with patch.object(ocr_plan, "FIRST_SECTION_PAGES", 2), patch.object(ocr_plan, "MAX_SECTION_PAGES", 2):
            self._step()
            self.assertEqual((row.ocr_state, row.ocr_next_page, row.ocr_file), ("wait", 4, "upto-3.pdf"))
            self._step()
        self.assertEqual([call[call.index("--pages") + 1] for call in self._calls()], ["2-3", "5,7"])
        self.assertEqual((row.ocr_state, row.ocr_found_pages), ("done", 4))

    def test_a_file_whose_last_scan_is_done_is_finished_before_its_last_page(self):
        _document, row = self._mixed()
        self._mixed_output("2-3,5")
        with patch.object(ocr_plan, "FIRST_SECTION_PAGES", 3), patch.object(ocr_plan, "MAX_SECTION_PAGES", 3):
            self._step()
            self.assertEqual(row.ocr_state, "wait")
            self._mixed_output("7")
            self._step()
        self.assertEqual(row.ocr_state, "done")
        self.assertEqual(self._step(), OCR_IDLE)

    def test_the_row_points_to_the_new_file_and_the_old_one_goes_when_committed(self):
        _document, row = self._scan(4)
        self._output("1-2", ["a b c d e f", "g h i j k l", "", ""])
        self._output("3-4", ["a b c d e f", "g h i j k l", "m n o p q r", "s t u v w x"])
        with patch.object(ocr_plan, "FIRST_SECTION_PAGES", 2), patch.object(ocr_plan, "MAX_SECTION_PAGES", 2):
            self._step()
            first = os.path.join(self._job(row), "upto-2.pdf")
            self.assertEqual(row.ocr_file_size, os.path.getsize(first))
            self._step()
        self.assertTrue(os.path.isfile(first))  # until the commit
        self.env.cr.postcommit.run()
        self.assertFalse(os.path.exists(first))

    def test_after_a_crash_the_recognition_goes_on_with_the_last_finished_section(self):
        _document, row = self._scan(4)
        self._output("1-2", ["a b c d e f", "g h i j k l", "", ""])
        self._output("3-4", ["a b c d e f", "g h i j k l", "m n o p q r", "s t u v w x"])
        with patch.object(ocr_plan, "FIRST_SECTION_PAGES", 2), patch.object(ocr_plan, "MAX_SECTION_PAGES", 2):
            self._step()
            row.ocr_state = "running"  # the server died while the next one ran
            self.Text._requeue_stale()
            self.assertEqual((row.ocr_state, row.ocr_attempts), ("wait", 1))
            self._step()
        calls = self._calls()
        self.assertEqual(calls[1][calls[1].index("--pages") + 1], "3-4")
        self.assertEqual(calls[1][-2], os.path.join(self._job(row), "upto-2.pdf"))
        self.assertEqual((row.ocr_state, row.ocr_attempts), ("done", 0))

    def test_a_section_file_that_is_gone_means_starting_again_without_a_lost_try(self):
        _document, row = self._scan(4)
        self._output("1-2", ["a b c d e f", "g h i j k l", "", ""])
        with patch.object(ocr_plan, "FIRST_SECTION_PAGES", 2), patch.object(ocr_plan, "MAX_SECTION_PAGES", 2):
            self._step()
            os.unlink(os.path.join(self._job(row), "upto-2.pdf"))
            self._step()
        calls = self._calls()
        self.assertEqual(calls[1][calls[1].index("--pages") + 1], "1-2")
        self.assertEqual(calls[1][-2], self.Document._blob_path(row.checksum))
        self.assertEqual((row.ocr_next_page, row.ocr_attempts), (3, 0))

    def test_a_section_file_of_another_size_is_not_trusted(self):
        _document, row = self._scan(4)
        self._output("1-2", ["a b c d e f", "g h i j k l", "", ""])
        with patch.object(ocr_plan, "FIRST_SECTION_PAGES", 2), patch.object(ocr_plan, "MAX_SECTION_PAGES", 2):
            self._step()
            with open(os.path.join(self._job(row), "upto-2.pdf"), "ab") as handle:
                handle.write(b"x")
            self.assertFalse(row._ocr_section_path())

    def test_the_time_per_page_is_measured_and_used_for_the_next_section(self):
        _document, row = self._scan(4)
        self._output("1-2", ["a b c d e f", "g h i j k l", "", ""])
        with patch.object(ocr_plan, "FIRST_SECTION_PAGES", 2):
            self._step()
        self.assertGreater(row.ocr_seconds_per_page, 0)
        self.assertLess(row.ocr_seconds_per_page, 10)

    def test_a_scan_in_which_nothing_is_found_keeps_no_second_copy(self):
        _document, row = self._scan(2)
        self._output("1-2", ["", ""])
        self._step()
        self.assertEqual((row.ocr_state, row.state), ("done", "empty"))
        self.assertFalse(row.ocr_checksum)
        self.assertIn("no text", row.ocr_message)

    def test_a_short_text_is_still_text_worth_the_pdf(self):
        _document, row = self._scan(2)
        self._output("1-2", ["Invoice", ""])
        self._step()
        self.assertEqual((row.ocr_found_pages, bool(row.ocr_checksum)), (1, True))

    def test_the_recognized_pdf_is_kept_when_only_a_later_section_found_text(self):
        _document, row = self._scan(4)
        self._output("1-2", ["", "", "", ""])
        self._output("3-4", ["", "", "Found late", ""])
        with patch.object(ocr_plan, "FIRST_SECTION_PAGES", 2), patch.object(ocr_plan, "MAX_SECTION_PAGES", 2):
            self._step()
            self._step()
        self.assertEqual((row.ocr_state, row.ocr_found_pages, bool(row.ocr_checksum)), ("done", 1, True))

    def test_a_call_without_time_for_a_page_reports_it(self):
        self._scan(2)
        self.assertEqual(self.Text._ocr_step(time.monotonic() + 3), OCR_NO_TIME)
        self.assertEqual(self._calls(), [])

    def test_a_stopped_recognition_does_not_start(self):
        _document, row = self._scan(2)
        self.env["ir.config_parameter"].set_param("int_filemanager.ocr_enabled", "0")
        self.assertEqual(self._step(), OCR_IDLE)
        self.assertEqual(row.ocr_state, "wait")

    # --- the recognized text is the text -----------------------------------------

    def test_reading_again_reads_the_recognized_pdf_and_keeps_the_text(self):
        document, row = self._scan(2)
        self._output("1-2", ["first recognized page of the scan", "second recognized page of the scan"])
        self._step()
        row._reset()
        self.assertEqual(row.state, "pending")
        self.assertTrue(row._text_source().endswith(row.ocr_checksum))
        self._read_all()
        self.assertEqual((row.state, row.ocr_state, row.scan_pages), ("done", "done", 0))
        self.assertEqual(self._found("second recognized"), document)
        self.Text._ocr_queue(100)
        self.assertEqual(row.ocr_state, "done")

    def test_reading_again_in_the_middle_of_a_recognition_reads_the_finished_section(self):
        document, row = self._scan(4)
        self._output("1-2", ["first recognized page of the scan", "second recognized page of the scan", "", ""])
        with patch.object(ocr_plan, "FIRST_SECTION_PAGES", 2):
            self._step()
        row._reset()
        self.assertEqual(row._text_source(), os.path.join(self._job(row), "upto-2.pdf"))
        self._read_all()
        self.assertEqual(self._found("second recognized"), document)
        self.assertEqual((row.ocr_state, row.ocr_next_page), ("wait", 3))

    def test_recognizing_again_begins_from_the_original(self):
        boss = new_test_user(self.env, login="ocr_boss", groups=ADMIN_GROUPS)
        document, row = self._scan(2)
        self._output("1-2", ["first recognized page of the scan", "second recognized page of the scan"])
        self._step()
        old = row.ocr_checksum
        with patch.object(type(self.env["ir.cron"]), "_trigger"):
            row.with_user(boss).action_recognize_again()
        self.assertEqual((row.state, row.ocr_state, row.ocr_checksum, row.ocr_next_page), ("pending", False, False, 1))
        self.assertTrue(os.path.exists(os.path.join(self.Document._checklist_dir(), old[:2], old)))
        self._read_all()
        self.assertFalse(self._found("second recognized"))
        self.Text._ocr_queue(100)
        self.assertEqual(row.ocr_state, "wait")
        self.assertTrue(document)

    def test_recognizing_again_is_for_the_administrators(self):
        alice = new_test_user(self.env, login="ocr_alice", groups="base.group_user,int_filemanager.int_filemanager_group_user")
        _document, row = self._scan(2)
        with self.assertRaises(AccessError):
            row.with_user(alice).action_recognize_again()

    # --- failures ----------------------------------------------------------------

    def _fail_with(self, code, stderr=""):
        self._save_config(mode="exit", code=code, stderr=stderr)
        _document, row = self._scan(2)
        self._step()
        return row

    def test_a_broken_file_is_given_up_at_once(self):
        row = self._fail_with(2, "InputFileError: broken")
        self.assertEqual(row.ocr_state, "failed")
        self.assertIn("cannot be read", row.ocr_message)
        self.assertIn("broken", row.ocr_message)

    def test_a_file_with_a_password_is_given_up(self):
        row = self._fail_with(8, "EncryptedPdfError")
        self.assertEqual(row.ocr_state, "failed")
        self.assertIn("password", row.ocr_message)

    def test_other_faults_are_tried_again_and_then_given_up(self):
        row = self._fail_with(7, "tesseract crashed")
        self.assertEqual((row.ocr_state, row.ocr_attempts), ("wait", 1))
        self._step()
        self.assertEqual((row.ocr_state, row.ocr_attempts), ("wait", 2))
        self._step()
        self.assertEqual((row.ocr_state, row.ocr_attempts), ("failed", 3))
        self.assertIn("several times", row.ocr_message)

    def test_a_failed_file_keeps_its_text_and_the_original(self):
        row = self._fail_with(2)
        self.assertEqual(row.state, "empty")
        self.assertTrue(os.path.isfile(self.Document._blob_path(row.checksum)))
        self.assertFalse(row.ocr_checksum)

    def test_a_wrong_setup_stops_the_recognition_and_the_file_waits(self):
        row = self._fail_with(3, "missing dependency: tesseract")
        self.assertEqual((row.ocr_state, row.ocr_attempts), ("wait", 0))
        self.assertEqual(self.Text._ocr_blocked()[0], "missing_dependency")
        self.assertEqual(self._step(), OCR_IDLE)

    def test_a_full_disk_pauses_the_recognition_without_a_lost_try(self):
        row = self._fail_with(7, "OSError: [Errno 28] No space left on device")
        self.assertEqual((row.ocr_state, row.ocr_attempts), ("wait", 0))
        self.assertEqual(self.Text._ocr_blocked()[0], "disk_full")

    def test_the_pause_ends_after_a_while(self):
        self._fail_with(7, "No space left on device")
        stamp = str(time.time() - 4000)
        self.env["ir.config_parameter"].set_param(OCR_BLOCK_PARAMETER, f"{stamp}|disk_full|x")
        self.assertFalse(self.Text._ocr_blocked())
        self.assertEqual(self.Text._ocr_ready(), (True, None))

    def test_a_program_that_gives_no_file_is_tried_once_more_with_force(self):
        document, row = self._scan(2)
        self._output("1-2", ["recognized by force", "also by force"])
        self._save_config(mode="force_only")
        self._step()
        calls = self._calls()
        self.assertEqual(len(calls), 2)
        self.assertNotIn("--force-ocr", calls[0])
        self.assertIn("--force-ocr", calls[1])
        self.assertEqual((row.ocr_state, self._found("also by force")), ("done", document))

    def test_a_program_that_never_gives_a_file_fails_the_file(self):
        self._save_config(mode="nofile")
        _document, row = self._scan(2)
        self._step()
        self.assertEqual((row.ocr_state, len(self._calls())), ("failed", 2))
        self.assertIn("gave no file", row.ocr_message)

    # --- time --------------------------------------------------------------------

    def _slow(self, seconds=2.5):
        """Run one step in which the stub hangs; the section gets ``seconds``."""
        self._save_config(mode="hang")
        with (
            patch.object(ocr_plan, "FIXED_SECONDS", 1),
            patch.object(ocr_plan, "DEFAULT_SECONDS_PER_PAGE", 1),
            patch(f"{MODULE}.MIN_TEACH_SECONDS", 1),
            patch(f"{MODULE}.MIN_READ_SECONDS", 0),
        ):
            return self._step(seconds)

    def _pids(self):
        with open(self.config["pids"], encoding="utf-8") as handle:
            return [int(pid) for pid in handle.read().split()]

    def test_a_section_that_runs_out_of_time_is_stopped_with_everything_it_started(self):
        _document, row = self._scan(2)
        started = time.monotonic()
        self.assertEqual(self._slow(), OCR_PROGRESS)
        self.assertLess(time.monotonic() - started, 20)
        program, child = self._pids()
        self.assertFalse(psutil.pid_exists(program))  # the program is gone, not even waiting for its parent
        # What the program started has no parent we could wait for: it may stay as a zombie until
        # the first process of the container takes it over (a container with an init does).
        self.assertFalse(psutil.pid_exists(child) and psutil.Process(child).status() != psutil.STATUS_ZOMBIE)
        self.assertEqual(row.ocr_state, "wait")
        self.assertFalse([name for name in os.listdir(self._job(row)) if name.endswith(".tmp")])

    def test_a_timeout_makes_the_next_section_smaller(self):
        _document, row = self._scan(2)
        self._slow()
        self.assertEqual(row.ocr_seconds_per_page, 2)  # twice the guess of 1 second
        self.assertEqual(row.ocr_attempts, 0)  # not a fair time for a page

    def test_a_page_that_takes_too_long_even_with_a_fair_time_fails_the_file(self):
        _document, row = self._scan(1)
        with patch.object(ocr_plan, "MIN_COUNTING_SECONDS", 1):
            for _ in range(3):
                self._slow()
        self.assertEqual(row.ocr_state, "failed")
        self.assertIn("longer", row.ocr_message)

    def test_a_section_that_got_no_time_to_speak_of_teaches_nothing(self):
        _document, row = self._scan(2)
        self._save_config(mode="hang")
        with (
            patch.object(ocr_plan, "FIXED_SECONDS", 1),
            patch.object(ocr_plan, "DEFAULT_SECONDS_PER_PAGE", 1),
            patch(f"{MODULE}.MIN_TEACH_SECONDS", 100),
            patch(f"{MODULE}.MIN_READ_SECONDS", 0),
        ):
            self._step(2.5)
        self.assertEqual((row.ocr_state, row.ocr_seconds_per_page, row.ocr_attempts), ("wait", 0, 0))

    def test_the_program_does_not_get_the_time_that_the_reading_of_its_pages_needs(self):
        self._scan(2)
        # 12 seconds left, 10 of them are for the reading: nothing is started.
        self.assertEqual(self.Text._ocr_step(time.monotonic() + 12), OCR_NO_TIME)
        self.assertEqual(self._calls(), [])

    # --- faults of the disk -----------------------------------------------------

    def _publish_fails(self, error):
        def fail(*_args, **_kwargs):
            raise error

        return patch.object(type(self.Document), "_publish_blob", fail)

    def test_a_full_disk_when_the_pdf_is_placed_pauses_and_does_not_count_a_crash(self):
        _document, row = self._scan(2)
        self._output("1-2", ["first recognized page of the scan", "second recognized page of the scan"])
        with self._publish_fails(OSError(errno.ENOSPC, "No space left on device")):
            self.assertEqual(self._step(), OCR_PROGRESS)
        self.assertEqual((row.ocr_state, row.ocr_attempts), ("wait", 0))
        self.assertEqual(self.Text._ocr_blocked()[0], "disk_full")
        # Nothing of the step is in the database: no text, no new file, no PDF.
        self.assertEqual((row.ocr_next_page, row.ocr_file, row.ocr_checksum), (1, False, False))
        self.assertFalse(self._found("recognized"))

    def test_another_fault_of_the_disk_counts_as_a_failed_try(self):
        _document, row = self._scan(2)
        self._output("1-2", ["first recognized page of the scan", "second recognized page of the scan"])
        with self._publish_fails(OSError(errno.EIO, "Input/output error")):
            self._step()
        self.assertEqual((row.ocr_state, row.ocr_attempts), ("wait", 1))
        self.assertFalse(self.Text._ocr_blocked())
        self.assertFalse(self._found("recognized"))

    def test_the_old_section_file_stays_when_the_end_of_the_step_fails(self):
        _document, row = self._scan(4)
        self._output("1-2", ["a b c d e f", "g h i j k l", "", ""])
        self._output("3-4", ["a b c d e f", "g h i j k l", "m n o p q r", "s t u v w x"])
        with patch.object(ocr_plan, "FIRST_SECTION_PAGES", 2), patch.object(ocr_plan, "MAX_SECTION_PAGES", 2):
            self._step()
            first = os.path.join(self._job(row), "upto-2.pdf")
            with self._publish_fails(OSError(errno.ENOSPC, "No space left on device")):
                self._step()
            self.env.cr.postcommit.run()
        self.assertTrue(os.path.isfile(first))
        self.assertEqual((row.ocr_next_page, row.ocr_file), (3, "upto-2.pdf"))

    # --- the scheduled action ----------------------------------------------------

    def test_the_scheduled_action_reads_queues_and_recognizes(self):
        document = self._document("scan.pdf", text_files.pdf(["", ""], pictures=range(2)))
        self._output("1-2", ["from the action one", "from the action two"])
        self._run()
        row = self._text_of(document)
        self.assertEqual((row.state, row.ocr_state), ("done", "done"))
        self.assertEqual(self._found("action two"), document)

    def test_counting_the_work_left_does_not_look_at_the_programs(self):
        self._scan(2)
        with patch.object(type(self.Text), "_ocr_tools", side_effect=AssertionError("looked at the programs")):
            self.assertEqual(self.Text._work_left(), 1)

    def test_the_work_left_leaves_out_the_scans_while_the_recognition_cannot_run(self):
        self._scan(2)
        self.Text._ocr_block("disk_full")
        self.assertEqual(self.Text._work_left(), 0)

    def test_the_action_reports_the_scans_that_wait_when_there_is_no_time(self):
        self._scan(2)
        reported = []
        cron_model = type(self.env["ir.cron"])
        with (
            patch.object(cron_model, "_commit_progress", lambda _self, *args, **kw: reported.append((args, kw)) or 0),
            patch.object(type(self.Text), "_pass_deadline", lambda *_args: time.monotonic() + 3),
        ):
            self.Text.with_context(cron_id=self._cron().id)._cron_ocr()
        self.assertEqual(reported[-1], ((0,), {"remaining": 1}))
        self.assertEqual(self._calls(), [])

    def _cron(self):
        return self.env.ref("int_filemanager.int_filemanager_text_cron")

    def _run(self):
        self.Text.with_context(cron_id=self._cron().id)._cron_ocr()
        self.env.invalidate_all()

    # --- cleaning up -------------------------------------------------------------

    def test_the_cleaner_removes_job_folders_of_rows_that_are_gone_or_done(self):
        _document, row = self._scan(2)
        gone = os.path.join(self.Text._ocr_dir(), "999999")
        done = self._job(row)
        for path in (gone, done):
            os.makedirs(path, exist_ok=True)
            with open(os.path.join(path, "left.tmp"), "wb") as handle:
                handle.write(b"x")
        row.ocr_state = "done"
        with patch(f"{MODULE}.JOB_MIN_AGE_SECONDS", -1):
            self.Text._gc_ocr_jobs()
        self.assertFalse(os.path.exists(gone))
        self.assertFalse(os.path.exists(done))

    def test_the_cleaner_leaves_a_running_row_and_young_files_and_the_file_in_use(self):
        _document, row = self._scan(2)
        job = self._job(row)
        os.makedirs(job, exist_ok=True)
        for name in ("upto-1.pdf", "stale.tmp"):
            with open(os.path.join(job, name), "wb") as handle:
                handle.write(b"x")
        row.write({"ocr_state": "running"})
        with patch(f"{MODULE}.JOB_MIN_AGE_SECONDS", -1):
            self.Text._gc_ocr_jobs()
        self.assertEqual(sorted(os.listdir(job)), ["stale.tmp", "upto-1.pdf"])
        row.write({"ocr_state": "wait", "ocr_file": "upto-1.pdf"})
        with patch(f"{MODULE}.JOB_MIN_AGE_SECONDS", -1):
            self.Text._gc_ocr_jobs()
        self.assertEqual(os.listdir(job), ["upto-1.pdf"])
        row.ocr_file = False
        self.Text._gc_ocr_jobs()  # young: stays
        self.assertEqual(os.listdir(job), ["upto-1.pdf"])

    def test_a_row_that_is_running_at_the_start_of_a_run_counts_a_try_and_gives_up(self):
        _document, row = self._scan(2)
        row.ocr_state = "running"
        self.Text._requeue_stale()
        self.assertEqual((row.ocr_state, row.ocr_attempts), ("wait", 1))
        row.write({"ocr_state": "running", "ocr_attempts": 2})
        self.Text._requeue_stale()
        self.assertEqual(row.ocr_state, "failed")


def joined_pdf(*contents):
    """The pages of the PDFs ``contents`` one after the other, as one PDF."""
    import pikepdf  # noqa: PLC0415

    joined = pikepdf.Pdf.new()
    for content in contents:
        with pikepdf.Pdf.open(io.BytesIO(content)) as part:
            joined.pages.extend(part.pages)
    stream = io.BytesIO()
    joined.save(stream)
    return stream.getvalue()


def scan_pdf(lines_per_page):
    """A PDF made of pictures of text, as a scanner makes it (no text in it)."""
    from PIL import Image, ImageDraw, ImageFont  # noqa: PLC0415

    font = ImageFont.load_default(size=56)
    pages = []
    for lines in lines_per_page:
        picture = Image.new("RGB", (1654, 2339), "white")  # A4 at 200 dpi
        draw = ImageDraw.Draw(picture)
        for number, line in enumerate(lines):
            draw.text((120, 200 + number * 120), line, fill="black", font=font)
        pages.append(picture)
    stream = io.BytesIO()
    pages[0].save(stream, "PDF", resolution=200, save_all=True, append_images=pages[1:])
    return stream.getvalue()


@tagged("post_install", "-at_install")
class TestRealRecognition(TextCase):
    """The whole way with the real ``ocrmypdf`` and Tesseract (skipped where they are not)."""

    def setUp(self):
        super().setUp()
        if not (shutil.which("ocrmypdf") and shutil.which("tesseract")):
            self.skipTest("ocrmypdf and tesseract are not installed")
        tools = self.Text._ocr_tools()
        if "eng" not in tools["languages"]:
            self.skipTest("Tesseract has no English")
        Params = self.env["ir.config_parameter"]
        Params.set_param("int_filemanager.ocr_enabled", "1")
        Params.set_param("int_filemanager.ocr_languages", "eng")
        self.addCleanup(shutil.rmtree, self.Text._ocr_dir(), ignore_errors=True)

    def test_a_picture_of_text_is_recognized_and_found(self):
        document = self._document(
            "scan.pdf", scan_pdf([["The plumber sent invoice 4711"], ["Second page about gardening"]])
        )
        self._read_all()
        row = self._text_of(document)
        self.assertEqual((row.state, row.scan_pages), ("empty", 2))
        self.assertFalse(self._found("plumber"))
        self.Text._ocr_queue(100)
        while row.ocr_state == "wait":
            self.assertEqual(self.Text._ocr_step(time.monotonic() + 300), OCR_PROGRESS)
        self.assertEqual((row.ocr_state, row.state, row.scan_pages), ("done", "done", 0), row.ocr_message)
        self.assertEqual(self._found("plumber"), document)
        self.assertEqual(self._found("gardening"), document)
        self.assertTrue(os.path.isfile(self.Document._blob_path(row.ocr_checksum)))
        # The recognized PDF is a PDF with text: read again, the text is the same.
        row._reset()
        self._read_all()
        self.assertEqual(self._found("gardening"), document)

    def test_a_mixed_file_gets_the_text_of_its_scans_and_keeps_the_rest(self):
        document = self._document(
            "mixed.pdf",
            joined_pdf(
                text_files.pdf(["A page that is text and has plenty of words in it"]),
                scan_pdf([["Second page about gardening"]]),
                text_files.pdf([""]),
                scan_pdf([["Fourth page about pears"]]),
            ),
        )
        self._read_all()
        row = self._text_of(document)
        self.assertEqual((row.page_count, row.scan_pages), (4, 2))
        self.Text._ocr_queue(100)
        while row.ocr_state == "wait":
            self.assertEqual(self.Text._ocr_step(time.monotonic() + 300), OCR_PROGRESS)
        self.assertEqual((row.ocr_state, row.scan_pages, row.ocr_found_pages), ("done", 0, 2), row.ocr_message)
        self.assertEqual(self._found("gardening"), document)
        self.assertEqual(self._found("pears"), document)
        self.assertEqual(self._found("plenty of words"), document)
        # Read again, the recognized PDF has the same four pages.
        row._reset()
        self._read_all()
        self.assertEqual((row.page_count, row.scan_pages), (4, 0))

    def test_sections_of_one_page_give_the_same_result(self):
        document = self._document(
            "scan.pdf", scan_pdf([["First page about apples"], ["Second page about oranges"], ["Third page about pears"]])
        )
        self._read_all()
        self.Text._ocr_queue(100)
        row = self._text_of(document)
        with patch.object(ocr_plan, "FIRST_SECTION_PAGES", 1), patch.object(ocr_plan, "MAX_SECTION_PAGES", 1):
            steps = 0
            while row.ocr_state == "wait":
                self.Text._ocr_step(time.monotonic() + 300)
                steps += 1
        self.assertEqual((row.ocr_state, steps), ("done", 3), row.ocr_message)
        for word in ("apples", "oranges", "pears"):
            self.assertEqual(self._found(word), document)
