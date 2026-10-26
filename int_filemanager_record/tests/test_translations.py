import glob
import os

from odoo.modules import get_module_path
from odoo.tests.common import TransactionCase, tagged
from odoo.tools.translate import PoFileReader


@tagged("post_install", "-at_install")
class TestTranslationFiles(TransactionCase):
    """The files of the translations are read as Odoo reads them when a language is loaded."""

    def test_every_po_file_is_read_by_the_reader_of_odoo(self):
        folder = os.path.join(get_module_path("int_filemanager_record"), "i18n")
        paths = glob.glob(os.path.join(folder, "*.po"))
        self.assertTrue(paths)
        for path in paths:
            with self.subTest(file=os.path.basename(path)):
                rows = list(PoFileReader(path))
                self.assertTrue(rows)
                self.assertEqual({row["module"] for row in rows}, {"int_filemanager_record"})

    def test_the_term_of_the_script_is_marked_for_the_web_client(self):
        # The web client takes only the entries with a ``code:`` reference (the terms of `_t`).
        folder = os.path.join(get_module_path("int_filemanager_record"), "i18n")
        rows = list(PoFileReader(os.path.join(folder, "de.po")))
        self.assertTrue(
            any(
                row["src"] == "Drop the files to attach them to %(record)s" and row["type"] == "code"
                for row in rows
            )
        )
