import glob
import os

from odoo.modules import get_module_path
from odoo.tests.common import TransactionCase, tagged
from odoo.tools.translate import PoFileReader


@tagged("post_install", "-at_install")
class TestTranslationFiles(TransactionCase):
    """The files of the translations are read as Odoo reads them when a language is loaded.

    A test database has English only, so the files are never read in a test run, and an entry that
    the reader cannot take stops the update of every database that has the language (the registry
    does not load). The reader needs the comment ``module: ...`` at the start of each entry.
    """

    def test_every_po_file_is_read_by_the_reader_of_odoo(self):
        folder = os.path.join(get_module_path("int_filemanager"), "i18n")
        paths = glob.glob(os.path.join(folder, "*.po"))
        self.assertTrue(paths)
        for path in paths:
            with self.subTest(file=os.path.basename(path)):
                rows = list(PoFileReader(path))
                self.assertTrue(rows)
                self.assertEqual({row["module"] for row in rows}, {"int_filemanager"})
