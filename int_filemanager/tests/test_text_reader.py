import json
import os
import subprocess
import sys
import tempfile

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.int_filemanager.models.int_filemanager_text import READER
from odoo.addons.int_filemanager.tools import extract_text

from . import text_files

PDF = "application/pdf"


@tagged("post_install", "-at_install")
class TestTextReader(TransactionCase):
    """The child process that reads the text of a file, as the scheduled action starts it."""

    def _read(self, content, mimetype, first=1, block=64 * 1024, cut=650000, memory=1024, pages=None):
        """Run the reader on ``content``: the lines of its answer, as objects."""
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "file")
            with open(path, "wb") as handle:
                handle.write(content)
            command = [sys.executable, "-I", READER, path, mimetype, str(first), str(block), str(cut), str(memory)]
            if pages:
                command.append(",".join(str(number) for number in pages))
            done = subprocess.run(command, capture_output=True, check=True, timeout=120)
        return [json.loads(line) for line in done.stdout.decode().splitlines()]

    def _pages(self, answer):
        return {entry["page"]: entry["text"] for entry in answer if "page" in entry}

    # --- PDF ---------------------------------------------------------------------

    def test_a_pdf_gives_the_text_of_each_page_and_the_number_of_pages(self):
        answer = self._read(text_files.pdf(["First page", "Müller and Straße"]), PDF)
        self.assertEqual(answer[0], {"pages": 2})
        pages = self._pages(answer)
        self.assertEqual(pages[1].strip(), "First page")
        self.assertEqual(pages[2].strip(), "Müller and Straße")
        self.assertEqual(answer[-1], {"done": True})

    def test_a_pdf_can_be_read_from_a_later_page(self):
        answer = self._read(text_files.pdf(["one", "two", "three"]), PDF, first=3)
        self.assertEqual(list(self._pages(answer)), [3])

    def test_a_pdf_can_be_read_for_a_list_of_pages(self):
        answer = self._read(text_files.pdf(["one", "two", "three", "four", "five"]), PDF, pages=[2, 4])
        self.assertEqual(list(self._pages(answer)), [2, 4])
        self.assertEqual(answer[0], {"pages": 5})
        self.assertEqual(answer[-1], {"done": True})

    def test_a_pdf_page_says_whether_it_has_a_picture(self):
        answer = self._read(text_files.pdf(["one", "", "three"], pictures=[1, 2]), PDF)
        self.assertEqual([entry["image"] for entry in answer if "page" in entry], [False, True, True])

    def test_a_page_above_the_limit_is_cut_and_says_so(self):
        answer = self._read(text_files.pdf(["x" * 300]), PDF, cut=100)
        page = next(entry for entry in answer if "page" in entry)
        self.assertEqual(len(page["text"].encode()), 100)
        self.assertTrue(page["cut"])

    def test_a_file_that_is_no_pdf_is_corrupt(self):
        answer = self._read(b"not a pdf at all", PDF)
        self.assertEqual(answer[-1]["error"], "corrupt")

    # --- Office and text ---------------------------------------------------------

    def test_word_gives_its_paragraphs_and_footers(self):
        answer = self._read(text_files.docx(["Hello world", "Second"], footer="Footer text"), text_files.DOCX)
        self.assertEqual(self._pages(answer), {1: "Hello world\nSecond\nFooter text"})

    def test_excel_gives_the_cells_with_shared_and_inline_strings(self):
        for shared in (True, False):
            with self.subTest(shared=shared):
                content = text_files.xlsx([["Name", "Amount"], ["Müller", 12.5]], shared=shared)
                self.assertEqual(
                    self._pages(self._read(content, text_files.XLSX)), {1: "Name Amount\nMüller 12.5"}
                )

    def test_powerpoint_gives_the_slides_in_order(self):
        content = text_files.pptx([["Title"], ["Second slide"], ["Third"]])
        self.assertEqual(
            self._pages(self._read(content, text_files.PPTX)), {1: "Title\nSecond slide\nThird"}
        )

    def test_opendocument_gives_its_paragraphs(self):
        self.assertEqual(
            self._pages(self._read(text_files.odt(["One", "Two"]), text_files.ODT)), {1: "One\nTwo"}
        )

    def test_plain_text_is_utf8_and_else_latin1(self):
        text = "Grüße aus Köln"
        self.assertEqual(self._pages(self._read(text.encode(), "text/plain")), {1: text})
        self.assertEqual(self._pages(self._read(text.encode("latin-1"), "text/plain")), {1: text})
        self.assertEqual(self._pages(self._read(b"\xef\xbb\xbfwith bom\r\nline", "text/plain")), {1: "with bom\nline"})

    def test_text_without_pages_comes_in_blocks_and_nothing_is_lost(self):
        lines = [f"line {number} " + "ü" * 20 for number in range(300)]
        content = "\n".join(lines).encode()
        pages = self._pages(self._read(content, "text/plain", block=1000))
        self.assertGreater(len(pages), 5)
        self.assertTrue(all(len(text.encode()) <= 1000 for text in pages.values()))
        self.assertEqual("\n".join(pages[number] for number in sorted(pages)), "\n".join(lines))

    def test_a_large_spreadsheet_is_split_and_complete(self):
        rows = [[f"word{number}", number] for number in range(20000)]
        pages = self._pages(self._read(text_files.xlsx(rows), text_files.XLSX, block=64 * 1024))
        self.assertGreater(len(pages), 3)
        text = "\n".join(pages[number] for number in sorted(pages))
        self.assertEqual(text.count("\n") + 1, 20000)
        self.assertTrue(text.endswith("word19999 19999"))

    def test_a_block_can_be_read_from_a_later_one(self):
        content = "\n".join(f"line {number}" for number in range(100)).encode()
        everything = self._pages(self._read(content, "text/plain", block=100))
        later = self._pages(self._read(content, "text/plain", first=4, block=100))
        self.assertEqual(later, {number: everything[number] for number in everything if number >= 4})

    def test_a_broken_archive_is_corrupt(self):
        for mimetype in (text_files.DOCX, text_files.XLSX, text_files.ODT):
            with self.subTest(mimetype=mimetype):
                self.assertEqual(self._read(b"PK\x03\x04 broken", mimetype)[-1]["error"], "corrupt")

    def test_an_unknown_type_has_no_reader(self):
        self.assertEqual(self._read(b"x", "application/zip")[-1]["error"], "corrupt")

    def test_a_file_that_needs_too_much_memory_says_so(self):
        # Eight megabytes of one line in a budget of 64 MiB is fine; the budget is lowered by
        # the reader itself, so a big XML tree does not take the machine with it.
        rows = [[f"w{number}" * 5, number] for number in range(300000)]
        answer = self._read(text_files.xlsx(rows, shared=False), text_files.XLSX, memory=1)
        self.assertEqual(answer[-1].get("error"), "memory")

    # --- Pieces ------------------------------------------------------------------

    def test_blocks_keep_paragraphs_together_and_cut_long_ones(self):
        blocks = list(extract_text.blocks(["aaaa", "bbbb", "cccc", "d" * 50], 20))
        self.assertEqual(blocks, ["aaaa\nbbbb\ncccc", "d" * 20, "d" * 20, "d" * 10])

    def test_blocks_never_cut_a_character(self):
        blocks = list(extract_text.blocks(["ü" * 50], 17))
        self.assertTrue(all(len(block.encode()) <= 17 for block in blocks))
        self.assertEqual("".join(blocks), "ü" * 50)

    def test_text_is_cleaned_for_the_database(self):
        self.assertEqual(extract_text.clean("a\x00b\ud800c"), "abc")
