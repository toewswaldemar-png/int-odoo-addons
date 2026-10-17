"""Tests for the URI handling of odoo_ls_check.py.

Run:  python scripts/lint/test_odoo_ls_check.py
"""

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from odoo_ls_check import uri_to_path  # noqa: E402


class UriToPathTest(unittest.TestCase):
    def test_windows_uri_loses_the_leading_slash(self):
        path = uri_to_path("file:///C:/Users/Admin/repo/modell.py")
        self.assertEqual(path.as_posix(), "C:/Users/Admin/repo/modell.py")
        if sys.platform == "win32":
            self.assertEqual(str(path), "C:\\Users\\Admin\\repo\\modell.py")
            self.assertTrue(path.is_absolute())

    def test_windows_uri_with_escaped_characters(self):
        path = uri_to_path("file:///c%3A/My%20Repo/modell.py")
        self.assertEqual(path.as_posix(), "c:/My Repo/modell.py")

    def test_posix_uri_is_unchanged(self):
        path = uri_to_path("file:///mnt/v2src/int_filemanager/a.py")
        self.assertEqual(path.as_posix(), "/mnt/v2src/int_filemanager/a.py")


if __name__ == "__main__":
    unittest.main()
