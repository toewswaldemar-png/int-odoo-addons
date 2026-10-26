import inspect
import os

from odoo.addons.base.models import ir_cron
from odoo.addons.base.models.ir_attachment import IrAttachment
from odoo.service import server
from odoo.tests.common import TransactionCase, tagged
from odoo.tools import config

from ..tools.filestore import check_contents, filestore, full_path


def parameters(function):
    return list(inspect.signature(function).parameters)


@tagged("post_install", "-at_install")
class TestCoreContract(TransactionCase):
    """What the module takes from the core without a promise that it stays.

    Odoo may change a private method or a number of the server in an update: these tests then fail
    here, at the place that is named, and not as a wrong file or a run that is killed.
    """

    # --- ir.attachment: the filestore and the types of the files (``tools/filestore.py``) ----

    def test_the_attachment_has_the_methods_of_the_filestore(self):
        self.assertEqual(parameters(IrAttachment._filestore), ["self"])
        self.assertEqual(parameters(IrAttachment._full_path), ["self", "path"])
        self.assertEqual(parameters(IrAttachment._check_contents), ["self", "values"])

    def test_the_filestore_is_the_one_of_the_database(self):
        self.assertEqual(filestore(self.env), config.filestore(self.env.cr.dbname))
        self.assertEqual(full_path(self.env, "ab/abc"), os.path.join(filestore(self.env), "ab", "abc"))

    def test_the_types_follow_the_core_rules(self):
        # The client type, then the file name, then the head; html, svg and xml are text for every user.
        self.assertEqual(check_contents(self.env, "a.html", None, b"<html></html>")["mimetype"], "text/plain")
        self.assertEqual(check_contents(self.env, "a.svg", "image/svg+xml", b"<svg/>")["mimetype"], "text/plain")
        self.assertEqual(check_contents(self.env, "a.pdf", None, b"%PDF-1.4")["mimetype"], "application/pdf")
        # The office formats are zip files that must keep their type.
        docx = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        self.assertEqual(check_contents(self.env, "a.docx", docx, b"PK\x03\x04")["mimetype"], docx)

    # --- ir.cron: the time of a run (``models/int_filemanager_cron.py``) ----------------------

    def test_the_cron_has_the_window_and_the_progress_the_budget_works_from(self):
        self.assertIsInstance(ir_cron.MIN_TIME_PER_JOB, int)
        self.assertIsInstance(server.SLEEP_INTERVAL, int)
        self.assertIn("remaining", parameters(type(self.env["ir.cron"])._commit_progress))
        for option in ("workers", "limit_time_real", "limit_time_real_cron"):
            self.assertIsInstance(config[option], int, option)
