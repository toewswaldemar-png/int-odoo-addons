import os
import sys
import tempfile

from odoo.tests.common import BaseCase, tagged

from ..tools.files import remove_file, remove_path
from ..tools.programs import last_line, limited, probe


@tagged("post_install", "-at_install")
class TestToolsPrograms(BaseCase):
    """The helpers of ``tools/`` that the models call to start programs and to clean up."""

    def test_limited_puts_nice_and_timeout_in_front(self):
        command = limited(["soffice", "--headless"], 12.5, 19, 5)
        self.assertEqual(command[:2], ["nice", "-n"])
        self.assertEqual(command[3:], ["timeout", "--kill-after=5", "12.500", "soffice", "--headless"])

    def test_limited_never_asks_for_a_higher_priority(self):
        # A lower number than the one of this process needs a right the server does not have.
        command = limited(["true"], 1, -20, 5)
        self.assertEqual(command[2], "0")
        self.assertEqual(limited(["true"], 1, os.nice(0) + 3, 5)[2], "3")

    def test_probe_gives_what_the_program_wrote(self):
        self.assertEqual(probe([sys.executable, "-c", "print('1.2')"]).strip(), "1.2")

    def test_probe_of_a_missing_program_is_empty(self):
        self.assertEqual(probe(["/nonexistent/program"]), "")

    def test_last_line_skips_blank_lines_and_is_short(self):
        self.assertEqual(last_line("first\n  second  \n\n"), "second")
        self.assertEqual(last_line("x" * 300), "x" * 200)
        self.assertEqual(last_line(None), "")

    def test_remove_file_and_path(self):
        with tempfile.TemporaryDirectory() as folder:
            file = os.path.join(folder, "file")
            tree = os.path.join(folder, "tree", "deeper")
            os.makedirs(tree)
            for path in (file, os.path.join(tree, "file")):
                with open(path, "wb"):
                    pass
            remove_file(file)
            remove_file(file)  # already gone: no error
            remove_path(os.path.join(folder, "tree"))
            remove_path(os.path.join(folder, "tree"))
            self.assertEqual(os.listdir(folder), [])
