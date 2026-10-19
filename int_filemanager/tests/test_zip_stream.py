import datetime
import io
import os
import tempfile
import zipfile

from odoo.tests.common import BaseCase, tagged

from ..tools.zip_stream import ZipEntry, date_time, export_name, export_names, zip_chunks, zip_length

LONG_FILE = 2 * 1024**3 + 200 * 1024**2


@tagged("post_install", "-at_install")
class TestZipStream(BaseCase):
    """The ZIP that is written as a stream: the names in it, its length before the first byte."""

    def setUp(self):
        super().setUp()
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)

    def _file(self, content=b"", name=None):
        path = os.path.join(self.folder.name, name or f"file{len(os.listdir(self.folder.name))}")
        with open(path, "wb") as handle:
            handle.write(content)
        return path

    def _entry(self, name, content=b"x", date=datetime.datetime(2026, 1, 2, 3, 4, 6)):
        return ZipEntry(name, self._file(content), len(content), date)

    def _written(self, entries):
        return b"".join(zip_chunks(entries))

    # --- names ----------------------------------------------------------------------------

    def test_a_name_that_is_fine_stays(self):
        for name in ("report.pdf", "Müller & Söhne (2).docx", "日本語.txt", ".hidden", "a b.tar.gz"):
            self.assertEqual(export_name(name), name)

    def test_the_characters_of_windows_are_replaced(self):
        self.assertEqual(export_name('a:b?c*d"e<f>g|h.txt'), "a_b_c_d_e_f_g_h.txt")

    def test_slashes_and_control_characters_are_dropped(self):
        self.assertEqual(export_name("a/b\\c\x00d\te\n.txt"), "abcde.txt")

    def test_the_name_is_in_the_composed_form(self):
        self.assertEqual(export_name("é.txt"), "é.txt")

    def test_a_space_or_a_dot_at_the_end_goes(self):
        self.assertEqual(export_name("name. . "), "name")
        self.assertEqual(export_name("  name.txt  "), "name.txt")

    def test_a_name_that_is_nothing_is_a_file(self):
        for name in ("", "...", " ", "///", "\x01"):
            self.assertEqual(export_name(name), "file")

    def test_the_names_of_devices_are_made_harmless(self):
        for name, expected in (
            ("con.txt", "_con.txt"),
            ("NUL", "_NUL"),
            ("Com1.tar.gz", "_Com1.tar.gz"),
            ("lpt9.pdf", "_lpt9.pdf"),
            ("console.txt", "console.txt"),
            ("com10.txt", "com10.txt"),
        ):
            self.assertEqual(export_name(name), expected)

    def test_a_long_name_keeps_its_extension(self):
        name = export_name("x" * 400 + ".pdf")
        self.assertEqual(len(name), 255)
        self.assertTrue(name.endswith("x.pdf"))
        self.assertEqual(len(export_name("y" * 400)), 255)

    def test_equal_names_are_numbered_in_the_order_of_the_keys(self):
        names = export_names([(7, "a.txt"), (3, "a.txt"), (5, "A.TXT"), (9, "b.txt"), (1, "a (2).txt")])
        # "a (2).txt" was there first (key 1), so the others skip the number 2.
        self.assertEqual(names, {1: "a (2).txt", 3: "a.txt", 5: "A (3).TXT", 7: "a (4).txt", 9: "b.txt"})

    def test_names_that_are_equal_only_after_the_cleaning_are_numbered(self):
        names = export_names([(1, "a?.txt"), (2, "a_.txt"), (3, "A_.TXT")])
        self.assertEqual(names, {1: "a_.txt", 2: "a_ (2).txt", 3: "A_ (3).TXT"})

    def test_the_same_files_always_give_the_same_names(self):
        items = [(index, "same.txt") for index in range(1, 30)]
        self.assertEqual(export_names(items), export_names(list(reversed(items))))

    def test_a_number_does_not_make_the_name_too_long(self):
        long_name = "z" * 300 + ".txt"
        names = export_names([(1, long_name), (2, long_name)])
        self.assertTrue(all(len(name) <= 255 for name in names.values()))
        self.assertNotEqual(names[1], names[2])

    def test_a_date_before_1980_is_the_earliest_a_zip_knows(self):
        self.assertEqual(date_time(datetime.datetime(1970, 5, 5)), (1980, 1, 1, 0, 0, 0))
        self.assertEqual(date_time(datetime.date(2026, 3, 4)), (2026, 3, 4, 0, 0, 0))

    # --- the archive ----------------------------------------------------------------------

    def test_the_archive_holds_the_files_as_they_are(self):
        entries = [self._entry("a.txt", b"hello"), self._entry("ü/ö.bin", bytes(range(256)) * 10), self._entry("empty", b"")]
        archive = zipfile.ZipFile(io.BytesIO(self._written(entries)))
        self.assertIsNone(archive.testzip())
        self.assertEqual(archive.namelist(), ["a.txt", "ü/ö.bin", "empty"])
        self.assertEqual(archive.read("a.txt"), b"hello")
        self.assertEqual(archive.read("ü/ö.bin"), bytes(range(256)) * 10)
        self.assertEqual(archive.read("empty"), b"")
        self.assertTrue(all(info.compress_type == zipfile.ZIP_STORED for info in archive.infolist()))
        self.assertEqual(archive.getinfo("a.txt").date_time, (2026, 1, 2, 3, 4, 6))

    def test_a_file_of_more_than_one_chunk_is_whole(self):
        content = os.urandom(3 * 1024 * 1024 + 17)
        archive = zipfile.ZipFile(io.BytesIO(self._written([self._entry("big", content)])))
        self.assertEqual(archive.read("big"), content)

    def test_the_length_is_the_length_of_the_archive(self):
        cases = {
            "none": [],
            "one": [self._entry("a.txt", b"hello")],
            "empty": [self._entry("e", b"")],
            "names": [self._entry(name, b"x" * size) for name, size in (("ä.txt", 3), ("日本語.pdf", 70000), ("c" * 255, 1))],
        }
        for label, entries in cases.items():
            self.assertEqual(zip_length(entries), len(self._written(entries)), label)

    def test_the_length_holds_for_more_than_65535_entries(self):
        empty = self._file(b"")
        entries = [ZipEntry(f"f{index}", empty, 0, datetime.datetime(2026, 1, 1)) for index in range(70000)]
        self.assertEqual(zip_length(entries), len(self._written(entries)))

    def test_the_length_holds_for_a_file_above_2_gib(self):
        # A sparse file: it costs no disk. It has to be read once, the writer counts its bytes.
        path = os.path.join(self.folder.name, "sparse")
        with open(path, "wb") as handle:
            handle.truncate(LONG_FILE)
        small = self._entry("small", b"abc")
        entries = [small, ZipEntry("long", path, LONG_FILE, datetime.datetime(2026, 1, 1)), small._replace(name="last")]
        length = 0
        for chunk in zip_chunks(entries):
            length += len(chunk)
        self.assertEqual(zip_length(entries), length)

    def test_a_file_that_is_shorter_than_its_entry_breaks_the_stream(self):
        entry = self._entry("a.txt", b"hello")._replace(size=50)
        with self.assertRaisesRegex(OSError, "a.txt"):
            self._written([entry])

    def test_a_file_that_grew_breaks_the_stream(self):
        entry = self._entry("a.txt", b"hello world")._replace(size=5)
        with self.assertRaisesRegex(OSError, "a.txt"):
            self._written([entry])

    def test_a_file_that_is_gone_breaks_the_stream(self):
        entry = self._entry("a.txt", b"hello")
        os.unlink(entry.path)
        with self.assertRaises(FileNotFoundError):
            self._written([entry])
