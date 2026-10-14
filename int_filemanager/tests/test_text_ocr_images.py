import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from unittest.mock import patch

from odoo.tests.common import tagged

from odoo.addons.int_filemanager.models.int_filemanager_text import OCR_PROGRESS, _image_info
from odoo.addons.int_filemanager.tools import ocr_plan

from .test_text_ocr import OcrCase
from .test_text_search import TextCase


# Makes the picture in a child process: the Odoo process cannot write all formats (see
# ``tools/image_info.py``). Gets the settings as JSON on stdin and writes the file to stdout.
MAKER = """
import io, json, sys
from PIL import Image, ImageDraw, ImageFont
settings = json.load(sys.stdin)
width, form, dpi = settings["width"], settings["form"], settings["dpi"]
font = ImageFont.load_default(size=56 * width // 1654)
pages = []
for lines in settings["pages"]:
    image = Image.new("RGB", (width, width * 2339 // 1654), "white")
    draw = ImageDraw.Draw(image)
    for number, line in enumerate(lines):
        draw.text((width // 14, width // 8 + number * width // 14), line, fill="black", font=font)
    pages.append(image)
stream = io.BytesIO()
options = {"dpi": (dpi, dpi)} if dpi else {}
if form == "TIFF" and len(pages) > 1:
    options.update(save_all=True, append_images=pages[1:])
pages[0].save(stream, form, **options)
sys.stdout.buffer.write(stream.getvalue())
"""


def picture(lines_per_page, form="PNG", width=1654, dpi=None):
    """A picture of text (several pages for a TIFF); ``dpi`` is put in the file or left out."""
    settings = {"pages": lines_per_page, "form": form, "width": width, "dpi": dpi}
    done = subprocess.run(
        [sys.executable, "-I", "-c", MAKER],
        input=json.dumps(settings).encode(),
        capture_output=True,
        check=True,
        timeout=120,
    )
    return done.stdout


class PicturesCase:
    """Folders with the recognition of images on or off."""

    def _folder(self, name, mode="inherit", parent=None):
        return self.env["int.filemanager.folder"].create(
            {"name": name, "ocr_images": mode, "parent_id": parent.id if parent else False}
        )

    def _rows(self):
        self.Text._create_rows(1000)
        return self.Text.search([("mimetype", "like", "image/%")])


@tagged("post_install", "-at_install")
class TestPictureRows(PicturesCase, OcrCase):
    """Which pictures get a row: those in a folder with the recognition of images on."""

    def test_a_picture_in_a_folder_that_is_on_gets_a_row_that_waits_for_the_recognition(self):
        on = self._folder("Scans", "on")
        document = self._document("photo.png", picture([["Hello"]], width=400), folder=on)
        [row] = self._rows()
        self.assertEqual(row.checksum, document.checksum)
        self.assertEqual((row.state, row.ocr_state, row.mimetype), ("empty", "wait", "image/png"))
        self.assertEqual(self.Text.search_count([("state", "=", "pending")]), 0)

    def test_a_picture_in_a_folder_that_is_off_gets_none(self):
        self._document("photo.png", picture([["Hello"]], width=400), folder=self._folder("Photos"))
        self.assertFalse(self._rows())

    def test_the_choice_of_the_parent_folder_holds_below_it(self):
        top = self._folder("Top", "on")
        middle = self._folder("Middle", parent=top)
        deep = self._folder("Deep", parent=middle)
        off = self._folder("Off", "off", parent=top)
        self._document("a.png", picture([["Hello"]], width=400), folder=deep)
        self._document("b.png", picture([["World"]], width=400), folder=off)
        [row] = self._rows()
        self.assertEqual(self.Document.search([("checksum", "=", row.checksum)]).name, "a.png")

    def test_the_same_picture_in_two_folders_has_one_row_if_one_of_them_is_on(self):
        content = picture([["Hello again"]], width=400)
        self._document("a.png", content, folder=self._folder("Off"))
        self._document("b.png", content, folder=self._folder("On", "on"))
        self.assertEqual(len(self._rows()), 1)

    def test_nothing_is_made_when_the_recognition_is_off(self):
        self.env["ir.config_parameter"].set_param("int_filemanager.ocr_enabled", "0")
        self._document("a.png", picture([["Hello"]], width=400), folder=self._folder("On", "on"))
        self.assertFalse(self._rows())
        self.assertEqual(self.Text._count_missing(), 0)

    def test_turning_a_folder_on_makes_the_rows_at_the_next_run(self):
        folder = self._folder("Later")
        self._document("a.png", picture([["Hello"]], width=400), folder=folder)
        self.assertFalse(self._rows())
        folder.ocr_images = "on"
        self.assertEqual(self.Text._count_missing(), 1)
        self.assertEqual(len(self._rows()), 1)

    def test_other_files_do_not_depend_on_the_switch(self):
        self._document("a.txt", b"plain text", folder=self._folder("Off"))
        self.Text._create_rows(1000)
        self.assertEqual(self.Text.search_count([("mimetype", "=", "text/plain")]), 1)

    def test_the_row_of_a_picture_that_is_read_again_starts_with_the_recognition(self):
        document = self._document("a.png", picture([["Hello"]], width=400), folder=self._folder("On", "on"))
        [row] = self._rows()
        row.write({"state": "done", "ocr_state": "done", "page_count": 1, "ocr_attempts": 2})
        self.Page.create({"text_id": row.id, "page": 1, "content": "old text"})
        row._reset()
        self.assertEqual((row.state, row.ocr_state, row.page_count, row.ocr_attempts), ("empty", "wait", 0, 0))
        self.assertFalse(self.Page.search([("text_id", "=", row.id)]))
        self.assertTrue(document)


@tagged("post_install", "-at_install")
class TestImageInfo(PicturesCase, TextCase):
    """The child process that says how many pictures a file has and how wide it is."""

    def _info(self, content):
        with tempfile.NamedTemporaryFile(suffix=".img") as handle:
            handle.write(content)
            handle.flush()
            return _image_info(handle.name)

    def test_the_formats_the_odoo_process_does_not_know_are_read_too(self):
        tiff = picture([["one"], ["two"], ["three"]], form="TIFF", width=400)
        self.assertEqual(self._info(tiff), (3, 400))
        self.assertEqual(self._info(picture([["one"]], form="WEBP", width=500)), (1, 500))
        self.assertEqual(self._info(picture([["one"]], form="PNG", width=600)), (1, 600))

    def test_a_file_that_is_no_picture_gives_nothing(self):
        self.assertIsNone(self._info(b"this is no picture"))
        self.assertIsNone(_image_info("/nonexistent/path/to/nothing"))


@tagged("post_install", "-at_install")
class TestPictureRecognition(PicturesCase, OcrCase):
    """A picture recognized in steps, with a stub as the program."""

    def _picture_row(self, content, name="photo.png"):
        document = self._document(name, content, folder=self._folder("On", "on"))
        [row] = self._rows()
        return document, row

    def test_a_picture_is_recognized_found_and_keeps_no_pdf(self):
        document, row = self._picture_row(picture([["The plumber"]], width=400))
        self._output("1-1", ["The plumber sent an invoice"])
        self.assertEqual(self._step(), OCR_PROGRESS)
        self.assertEqual((row.ocr_state, row.state, row.page_count), ("done", "done", 1))
        self.assertFalse(row.ocr_checksum)
        self.assertEqual(self._found("plumber"), document)
        self.assertTrue(os.path.isfile(self.Document._blob_path(document.checksum)))
        [call] = self._calls()
        self.assertEqual(call[call.index("--pages") + 1], "1-1")
        self.assertEqual(call[-2], self.Document._blob_path(document.checksum))

    def test_a_picture_without_a_resolution_is_tried_again_with_an_estimate(self):
        _document, row = self._picture_row(picture([["Hello"]], width=400))
        self._output("1-1", ["The estimate worked"])
        self._save_config(mode="needs_dpi")
        self._step()
        first, second = self._calls()
        self.assertNotIn("--image-dpi", first)
        self.assertEqual(second[second.index("--image-dpi") + 1], str(ocr_plan.estimate_dpi(400)))
        self.assertEqual(row.ocr_state, "done")
        self.assertIn("dpi was assumed", row.ocr_message)

    def test_a_good_estimate_needs_no_warning(self):
        _document, row = self._picture_row(picture([["Hello"]], width=1654))
        self._output("1-1", ["The estimate worked"])
        self._save_config(mode="needs_dpi")
        self._step()
        self.assertEqual(row.ocr_state, "done")
        self.assertFalse(row.ocr_message)

    def test_a_file_that_is_no_picture_fails(self):
        document = self._document("fake.png", b"this is no picture", folder=self._folder("On", "on"))
        [row] = self._rows()
        self.assertTrue(document)
        self._step()
        self.assertEqual(row.ocr_state, "failed")
        self.assertIn("cannot be read", row.ocr_message)
        self.assertEqual(self._calls(), [])

    def test_a_picture_with_several_pages_is_recognized_in_sections(self):
        content = picture([["page one"], ["page two"], ["page three"]], form="TIFF", width=400, dpi=200)
        document, row = self._picture_row(content, "scan.tiff")
        self._output("1-2", ["first page text", "second page text", ""])
        self._output("3-3", ["first page text", "second page text", "third page text"])
        with patch.object(ocr_plan, "FIRST_SECTION_PAGES", 2), patch.object(ocr_plan, "MAX_SECTION_PAGES", 2):
            while row.ocr_state == "wait":
                self._step()
        self.assertEqual((row.ocr_state, row.page_count), ("done", 3))
        first, second = self._calls()
        self.assertEqual(first[-2], self.Document._blob_path(document.checksum))
        self.assertEqual(second[-2], os.path.join(self._job(row), "upto-2.pdf"))
        self.assertEqual(self._found("third"), document)
        self.assertFalse(row.ocr_checksum)


@tagged("post_install", "-at_install")
class TestRealPictureRecognition(PicturesCase, TextCase):
    """Pictures of text, read by the real ``ocrmypdf`` and Tesseract (skipped where they are not)."""

    def setUp(self):
        super().setUp()
        if not (shutil.which("ocrmypdf") and shutil.which("tesseract")):
            self.skipTest("ocrmypdf and tesseract are not installed")
        if "eng" not in self.Text._ocr_tools()["languages"]:
            self.skipTest("Tesseract has no English")
        Params = self.env["ir.config_parameter"]
        Params.set_param("int_filemanager.ocr_enabled", "1")
        Params.set_param("int_filemanager.ocr_languages", "eng")
        self.folder = self._folder("Pictures", "on")
        self.addCleanup(shutil.rmtree, self.Text._ocr_dir(), ignore_errors=True)

    def _recognize(self, content, name):
        document = self._document(name, content, folder=self.folder)
        self.Text._create_rows(1000)
        row = self._text_of(document)
        for _ in range(5):
            if row.ocr_state != "wait":
                break
            self.assertEqual(self.Text._ocr_step(time.monotonic() + 300), OCR_PROGRESS)
        return document, row

    def test_each_kind_of_picture_is_recognized(self):
        for form, name in (("PNG", "a.png"), ("JPEG", "a.jpg"), ("BMP", "a.bmp"), ("GIF", "a.gif"), ("WEBP", "a.webp")):
            with self.subTest(form=form):
                content = picture([[f"The plumber of {form} sent a bill"]], form=form)
                document, row = self._recognize(content, name)
                self.assertEqual(row.ocr_state, "done", row.ocr_message)
                self.assertEqual(self._found(f"plumber of {form}"), document)

    def test_a_picture_with_a_resolution_in_it_needs_no_estimate(self):
        document, row = self._recognize(picture([["Garden roses in autumn"]], dpi=200), "dpi.png")
        self.assertEqual((row.ocr_state, row.ocr_message), ("done", False))
        self.assertEqual(self._found("roses"), document)

    def test_a_tiff_with_two_pages_is_recognized_whole(self):
        content = picture([["Apples on page one"], ["Oranges on page two"]], form="TIFF", dpi=200)
        document, row = self._recognize(content, "two.tiff")
        self.assertEqual((row.ocr_state, row.page_count), ("done", 2), row.ocr_message)
        self.assertEqual(self._found("oranges"), document)
        self.assertEqual(self._found("apples"), document)

    def test_a_tiff_is_recognized_in_sections_of_one_page(self):
        content = picture([["Pears on page one"], ["Plums on page two"]], form="TIFF", dpi=200)
        with patch.object(ocr_plan, "FIRST_SECTION_PAGES", 1), patch.object(ocr_plan, "MAX_SECTION_PAGES", 1):
            document, row = self._recognize(content, "sections.tiff")
        self.assertEqual(row.ocr_state, "done", row.ocr_message)
        self.assertEqual(self._found("pears"), document)
        self.assertEqual(self._found("plums"), document)
