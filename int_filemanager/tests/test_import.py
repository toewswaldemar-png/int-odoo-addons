import hashlib
import os
import shutil
import tempfile
from unittest.mock import patch

from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase, new_test_user, tagged

ROOT_PARAMETER = "int_filemanager.import_root"


def remove(path):
    if os.path.exists(path):
        os.unlink(path)


@tagged("post_install", "-at_install")
class TestImport(TransactionCase):
    """Reading a folder of the disk into the filemanager: check, copy, stop, again."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Import = cls.env["int.filemanager.import"]
        cls.Line = cls.env["int.filemanager.import.line"]
        cls.Document = cls.env["int.filemanager.document"]
        cls.Folder = cls.env["int.filemanager.folder"]
        cls.target = cls.Folder.create({"name": "Target"})

    def setUp(self):
        super().setUp()
        self.root = os.path.realpath(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.addCleanup(self._forget_blobs)
        self.env["ir.config_parameter"].set_param(ROOT_PARAMETER, self.root)

    def _forget_blobs(self):
        for document in self.Document.with_context(active_test=False).search([]):
            remove(self.Document._blob_path(document.checksum))

    def _write(self, relative, content=b"hello"):
        path = os.path.join(self.root, relative)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as handle:
            handle.write(content)
        return path

    def _order(self, source_path="", **values):
        return self.Import.create(
            {"name": "Test", "source_path": source_path, "target_folder_id": self.target.id, **values}
        )

    def _cron(self):
        """Run the scheduled action as Odoo does, without the commit a test must not make."""
        with patch.object(self.env.cr, "commit"):
            self.Import._cron_run()
        self.env.invalidate_all()

    def _check(self, order):
        with patch.object(type(self.env["ir.cron"]), "_trigger", return_value=None):
            order.action_scan()
        self._cron()

    def _read_in(self, order):
        with patch.object(type(self.env["ir.cron"]), "_trigger", return_value=None):
            order.action_start()
        self._cron()

    def _lines(self, order, **domain):
        return self.Line.search(
            [("import_id", "=", order.id), ("path", "!=", "")]
            + [(key, "=", value) for key, value in domain.items()]
        )

    # ---- Check -------------------------------------------------------------------------

    def test_the_check_lists_everything_and_copies_nothing(self):
        self._write("a.txt", b"12345")
        self._write("sub/b.pdf", b"%PDF-1.4")
        self._write("sub/Thumbs.db", b"x")
        os.makedirs(os.path.join(self.root, "empty"))
        order = self._order()
        self._check(order)
        self.assertEqual(order.state, "scanned")
        self.assertEqual((order.folder_count, order.file_count), (2, 3))
        self.assertEqual(order.excluded_count, 1)
        self.assertEqual(order.total_size, 5 + 8)
        self.assertFalse(self.Document.search([]))
        self.assertFalse(self.target.child_ids)

    def test_links_and_odd_names_are_reported_not_read(self):
        self._write("a.txt")
        os.symlink(os.path.join(self.root, "a.txt"), os.path.join(self.root, "link.txt"))
        os.mkfifo(os.path.join(self.root, "fifo"))
        order = self._order()
        self._check(order)
        skipped = self._lines(order, state="skipped")
        self.assertEqual(sorted(skipped.mapped("path")), ["fifo", "link.txt"])
        self._read_in(order)
        self.assertEqual(self.target.document_ids.mapped("name"), ["a.txt"])

    def test_names_that_are_the_same_for_the_filemanager_are_marked(self):
        self._write("Report.txt", b"1")
        self._write("report.txt", b"2")
        self._write(" report.txt", b"3")
        self._write("Dokumente/x.txt", b"4")
        self._write("dokumente/y.txt", b"5")
        order = self._order()
        self._check(order)
        self.assertEqual(order.clash_count, 3)

    def test_a_path_outside_the_root_is_refused(self):
        outside = os.path.realpath(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, outside, ignore_errors=True)
        os.symlink(outside, os.path.join(self.root, "way_out"))
        for source_path in ("..", "../etc", "/etc", "way_out", "missing"):
            with self.subTest(source_path=source_path), self.assertRaises(UserError):
                self._order(source_path).action_scan()

    def test_without_a_root_folder_nothing_starts(self):
        self.env["ir.config_parameter"].set_param(ROOT_PARAMETER, "")
        with self.assertRaises(UserError):
            self._order().action_scan()

    def test_a_folder_below_the_root_is_read_in_alone(self):
        self._write("one/a.txt")
        self._write("two/b.txt")
        order = self._order("one")
        self._check(order)
        self._read_in(order)
        self.assertEqual(self.target.document_ids.mapped("name"), ["a.txt"])
        self.assertEqual(self.target.document_ids.sudo().origin_path, "one/a.txt")

    def test_the_check_cannot_start_while_it_runs(self):
        order = self._order()
        order.state = "running"
        with self.assertRaises(UserError):
            order.action_scan()
        with self.assertRaises(UserError):
            order.unlink()

    def test_reading_in_needs_the_check_first(self):
        with self.assertRaises(UserError):
            self._order().action_start()

    # ---- Reading in --------------------------------------------------------------------

    def test_reading_in_copies_folders_and_files(self):
        path = self._write("a/b/c.txt", b"hello world")
        self._write("a/d.bin", bytes(range(256)))
        order = self._order()
        self._check(order)
        self._read_in(order)
        self.assertEqual(order.state, "done")
        self.assertEqual((order.pending_count, order.error_count, order.progress), (0, 0, 100.0))
        folder_a = self.target.child_ids
        self.assertEqual(folder_a.mapped("name"), ["a"])
        self.assertEqual(folder_a.child_ids.mapped("name"), ["b"])
        document = folder_a.child_ids.document_ids
        self.assertEqual((document.name, document.size), ("c.txt", 11))
        self.assertEqual(document.checksum, hashlib.sha256(b"hello world").hexdigest())
        self.assertEqual(document.sudo().origin_path, "a/b/c.txt")
        self.assertEqual(document.mimetype, "text/plain")
        self.assertEqual(folder_a.document_ids.mapped("name"), ["d.bin"])
        with open(path, "rb") as handle:  # the original is still there, unchanged
            self.assertEqual(handle.read(), b"hello world")

    def test_a_folder_of_the_same_name_is_used_a_new_one_is_not_made(self):
        self._write("a/x.txt")
        existing = self.Folder.create({"name": "A", "parent_id": self.target.id})
        order = self._order()
        self._check(order)
        self._read_in(order)
        self.assertEqual(self.target.child_ids, existing)
        self.assertEqual(existing.document_ids.mapped("name"), ["x.txt"])

    def test_names_that_clash_get_a_number(self):
        self._write("Report.txt", b"1")
        self._write("report.txt", b"2")
        self._write("Dokumente/x.txt", b"3")
        self._write("dokumente/y.txt", b"4")
        order = self._order()
        self._check(order)
        self._read_in(order)
        self.assertEqual(
            sorted(self.target.document_ids.mapped("name")), ["Report.txt", "report (2).txt"]
        )
        self.assertEqual(
            sorted(self.target.child_ids.mapped("name")), ["Dokumente", "dokumente (2)"]
        )
        self.assertEqual(len(self.target.child_ids.document_ids), 2)
        self.assertFalse(self._lines(order, state="error"))

    def test_reading_in_twice_makes_no_duplicates(self):
        self._write("a/x.txt")
        first = self._order()
        self._check(first)
        self._read_in(first)
        second = self._order()
        self._check(second)
        self._read_in(second)
        self.assertEqual(len(self.target.child_ids.document_ids), 1)
        self.assertEqual(len(self.target.child_ids), 1)
        self.assertEqual(second.skipped_count, 1)

    def test_a_failing_file_does_not_stop_the_others(self):
        self._write("a.txt")
        bad = self._write("b.txt")
        self._write("c.txt")
        order = self._order()
        self._check(order)
        real_open = open

        def refuse(path, *args, **kwargs):
            if path == bad:
                raise PermissionError(13, "Permission denied")
            return real_open(path, *args, **kwargs)

        with patch("odoo.addons.int_filemanager.models.int_filemanager_import_line.open", refuse, create=True):
            self._read_in(order)
        self.assertEqual(sorted(self.target.document_ids.mapped("name")), ["a.txt", "c.txt"])
        failed = self._lines(order, state="error")
        self.assertEqual(failed.mapped("path"), ["b.txt"])
        self.assertEqual(failed.message, "Permission denied")
        self.assertEqual((order.state, order.error_count), ("done", 1))
        # The file is readable again: retrying reads it in.
        with patch.object(type(self.env["ir.cron"]), "_trigger", return_value=None):
            order.action_retry_errors()
        self._cron()
        self.assertEqual(sorted(self.target.document_ids.mapped("name")), ["a.txt", "b.txt", "c.txt"])
        self.assertEqual((order.state, order.error_count), ("done", 0))

    def test_a_file_that_vanished_is_a_failed_line(self):
        gone = self._write("a.txt")
        self._write("b.txt")
        order = self._order()
        self._check(order)
        os.unlink(gone)
        self._read_in(order)
        self.assertEqual(self._lines(order, state="error").mapped("path"), ["a.txt"])
        self.assertEqual(self.target.document_ids.mapped("name"), ["b.txt"])

    def test_a_link_that_replaced_a_file_after_the_check_is_not_followed(self):
        path = self._write("a.txt")
        secret = os.path.join(tempfile.mkdtemp(), "secret.txt")
        self.addCleanup(shutil.rmtree, os.path.dirname(secret), ignore_errors=True)
        with open(secret, "w", encoding="utf-8") as handle:
            handle.write("secret")
        order = self._order()
        self._check(order)
        os.unlink(path)
        os.symlink(secret, path)
        self._read_in(order)
        self.assertFalse(self.target.document_ids)
        self.assertEqual(self._lines(order, state="error").mapped("path"), ["a.txt"])

    def test_nothing_is_written_to_the_chatter(self):
        self._write("a/x.txt")
        order = self._order()
        self._check(order)
        self._read_in(order)
        folder = self.target.child_ids
        document = folder.document_ids
        self.assertFalse(folder.message_ids | document.message_ids)
        self.assertFalse(folder.message_follower_ids | document.message_follower_ids)

    def test_the_company_of_the_order_is_the_company_of_the_folders(self):
        company = self.env["res.company"].create({"name": "Other company"})
        target = self.Folder.create({"name": "Other", "company_id": company.id})
        self._write("a/x.txt")
        order = self.Import.create(
            {"name": "Test", "target_folder_id": target.id, "company_id": company.id}
        )
        self._check(order)
        self._read_in(order)
        self.assertEqual(target.child_ids.company_id, company)

    # ---- Stop and go on ---------------------------------------------------------------

    def test_a_stopped_order_goes_on_where_it_stopped(self):
        for number in range(4):
            self._write(f"f{number}.txt", str(number).encode())
        order = self._order()
        self._check(order)
        with patch.object(type(self.env["ir.cron"]), "_trigger", return_value=None):
            order.action_start()
        # The time of the run is up after two steps.
        calls = []

        def commit_progress(_cron, processed=0, *, remaining=None, deactivate=False):
            calls.append(processed)
            return 0 if len(calls) == 2 else 1

        with patch.object(type(self.env["ir.cron"]), "_commit_progress", commit_progress):
            self.Import._cron_run()
        self.env.invalidate_all()
        self.assertEqual(order.state, "running")
        self.assertEqual(len(self.target.document_ids), 2)
        self._cron()
        self.assertEqual((order.state, len(self.target.document_ids)), ("done", 4))

    def test_stop_returns_to_the_last_calm_state(self):
        order = self._order()
        order.state = "running"
        order.action_stop()
        self.assertEqual(order.state, "scanned")
        order.state = "scanning"
        order.action_stop()
        self.assertEqual(order.state, "draft")

    def test_an_order_whose_root_vanished_stops_and_says_why(self):
        self._write("a.txt")
        order = self._order()
        self._check(order)
        with patch.object(type(self.env["ir.cron"]), "_trigger", return_value=None):
            order.action_start()
        self.env["ir.config_parameter"].set_param(ROOT_PARAMETER, "")
        self._cron()
        self.assertEqual(order.state, "scanned")
        self.assertIn("root folder", order.message)

    # ---- Rights ------------------------------------------------------------------------

    def test_the_users_of_the_filemanager_do_not_see_the_orders(self):
        user = new_test_user(
            self.env, login="import_user", groups="base.group_user,int_filemanager.int_filemanager_group_user"
        )
        with self.assertRaises(AccessError):
            self.Import.with_user(user).search([])
        admin = new_test_user(
            self.env, login="import_admin", groups="base.group_user,int_filemanager.int_filemanager_group_admin"
        )
        order = self._order()
        self.assertEqual(self.Import.with_user(admin).search([]), order)
