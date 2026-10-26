import unicodedata

from psycopg2 import IntegrityError

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged
from odoo.tools import mute_logger

from .test_folder_access import AccessCase

COMPOSED = "\u00e4.txt"
DECOMPOSED = "a\u0308.txt"


@tagged("post_install", "-at_install")
class TestName(AccessCase, TransactionCase):
    """The name of a folder or a document, whatever way it comes in: the upload cleans it, and so
    does a form, an import or a call of the API."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._set_up_access()

    def test_a_name_is_composed_and_has_no_control_character_or_space_around(self):
        folder = self.Folder.create({"name": "  Ca\u0308fe\x00\t "})
        self.assertEqual(folder.name, unicodedata.normalize("NFC", "Ca\u0308fe"))
        document = self._document(self.deep, "x.txt")
        document.write({"name": f" {DECOMPOSED}\n"})
        self.assertEqual(document.name, COMPOSED)
        folder.with_user(self.boss).write({"name": DECOMPOSED})
        self.assertEqual(folder.name, COMPOSED)

    def test_a_name_that_is_nothing_is_refused(self):
        document = self._document(self.deep, "x.txt")
        for name in (".", "..", "", " \x00 "):
            with self.subTest(name=name), self.assertRaises(ValidationError):
                document.write({"name": name})
            with self.subTest(folder=name), self.assertRaises(ValidationError):
                self.Folder.create({"name": name, "parent_id": self.deep.id})
        # What a form of a folder does: the same refusal when a name is changed.
        with self.assertRaises(ValidationError):
            self.deep.write({"name": ".."})

    def test_a_slash_is_part_of_a_name_that_is_typed(self):
        # The ZIP makes the name of its entry (``export_name``); only an upload cuts a path off.
        folder = self.Folder.create({"name": "Invoices 2025/26", "parent_id": self.deep.id})
        self.assertEqual(folder.name, "Invoices 2025/26")

    def test_a_name_may_have_255_characters_and_not_more(self):
        folder = self.Folder.create({"name": "n" * 255})
        self.assertEqual(len(folder.name), 255)
        with self.assertRaises(ValidationError):
            folder.write({"name": "n" * 256})
        document = self._document(self.deep, "x.txt")
        with self.assertRaises(ValidationError):
            document.write({"name": "n" * 256})

    def test_a_decomposed_name_is_the_same_name_as_the_composed_one(self):
        # Without the cleaning the unique index (by the letters) would let the two live together.
        self._document(self.deep, COMPOSED)
        other = self._document(self.deep, "other.txt")
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"), self.env.cr.savepoint():
            other.write({"name": DECOMPOSED})

    def test_the_upload_still_cuts_a_path_and_a_long_name_instead_of_refusing_it(self):
        document = self._document(self.deep, "C:\\fakepath\\" + "n" * 300 + ".txt")
        self.assertEqual(len(document.name), 255)
        self.assertTrue(document.name.endswith(".txt"))

    def test_a_taken_name_gets_a_number_for_folders_and_documents(self):
        first = self._document(self.deep, "a.txt")
        second = self._document(self.deep, "A.TXT")
        self.assertEqual((first.name, second.name), ("a.txt", "A (2).TXT"))
        folder = self.Folder._create_numbered("Deep", self.shared)
        self.assertEqual(folder.name, "Deep (2)")
        self.assertEqual(self.Folder._create_numbered("deep", self.shared).name, "deep (3)")
