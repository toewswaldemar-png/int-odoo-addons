from unittest.mock import patch

from odoo.exceptions import AccessError
from odoo.tests.common import new_test_user, tagged
from odoo.tools import config

from . import text_files
from .test_text_search import TextCase

ADMIN_GROUPS = "base.group_user,int_filemanager.int_filemanager_group_admin"
USER_GROUPS = "base.group_user,int_filemanager.int_filemanager_group_user"
SYSTEM_GROUPS = "base.group_user,base.group_system"


@tagged("post_install", "-at_install")
class TestTextAdmin(TextCase):
    """The list of the texts for the administrator, and the status in the settings."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.boss = new_test_user(cls.env, login="text_admin", groups=ADMIN_GROUPS)
        cls.alice = new_test_user(cls.env, login="text_alice2", groups=USER_GROUPS)

    # --- the list ----------------------------------------------------------------

    def test_the_views_of_the_list_are_there_for_the_administrator(self):
        views = self.Text.with_user(self.boss).get_views([(False, "list"), (False, "form"), (False, "search")])
        self.assertEqual(set(views["views"]), {"list", "form", "search"})

    def test_a_row_shows_a_file_that_has_the_text_and_how_many_have_it(self):
        first = self._document("a.txt", b"same text")
        second = self._document("b.txt", b"same text")
        second.active = False
        self.Text._create_rows(1000)
        row = self._text_of(first)
        self.assertEqual((row.document_id, row.document_count), (first, 2))

    def test_the_administrator_can_read_the_list_and_a_user_cannot(self):
        self._document("a.txt", b"text")
        self.Text._create_rows(1000)
        self.assertTrue(self.Text.with_user(self.boss).web_search_read([], {"document_id": {}, "state": {}}))
        with self.assertRaises(AccessError):
            self.Text.with_user(self.alice).search([])

    def test_read_again_throws_the_text_away_and_asks_for_a_new_run(self):
        document = self._document("a.txt", b"some words")
        self._read_all()
        row = self._text_of(document)
        row.write({"state": "failed", "attempts": 3, "message": "was broken"})
        with patch.object(type(self.env["ir.cron"]), "_trigger") as trigger:
            row.with_user(self.boss).action_read_again()
        self.assertEqual((row.state, row.attempts, row.next_page), ("pending", 0, 1))
        self.assertFalse(row.message)
        self.assertFalse(self.Page.search([("text_id", "=", row.id)]))
        trigger.assert_called_once()

    def test_read_again_leaves_the_rows_alone_that_are_waiting_or_running(self):
        first, second = self._document("a.txt", b"one"), self._document("b.txt", b"two")
        self.Text._create_rows(1000)
        waiting, running = self._text_of(first), self._text_of(second)
        running.state = "running"
        (waiting + running).with_user(self.boss).action_read_again()
        self.assertEqual((waiting.state, running.state), ("pending", "running"))

    def test_a_user_cannot_make_the_reader_start_again(self):
        document = self._document("a.txt", b"text")
        self._read_all()
        row = self._text_of(document)
        with self.assertRaises(AccessError):
            row.with_user(self.alice).action_read_again()
        self.assertEqual(row.state, "done")

    # --- the numbers -------------------------------------------------------------

    def test_the_status_counts_the_rows_per_state_and_the_files_without_a_row(self):
        before = self.Text._status()
        self._document("a.txt", b"fresh one")
        self._document("b.pdf", text_files.pdf(["fresh two"]))
        self._document("c.mp3", b"ID3" + b"\0" * 20)  # no text, no row, not counted
        self.assertEqual(self.Text._status()["missing"], before["missing"] + 2)
        self._read_all()
        after = self.Text._status()
        self.assertEqual(after["missing"], before["missing"])
        self.assertEqual(after["done"], before["done"] + 2)
        self.assertEqual(after["failed"], before["failed"])

    def test_the_time_of_a_run_per_kind_of_server(self):
        def limits(workers, real, cron):
            return patch.dict(
                config._runtime_options,
                {"workers": workers, "limit_time_real": real, "limit_time_real_cron": cron},
            )

        with limits(0, 120, -1):
            self.assertEqual(self.Text._budget(), ("threaded", 120, 105, True))
        with limits(2, 120, -1):
            # 70 seconds are gone before the job starts in a worker.
            self.assertEqual(self.Text._budget(), ("prefork", 120, 35, True))
        with limits(2, 120, 0):
            self.assertEqual(self.Text._budget(), ("prefork", 300, 285, False))
        with limits(2, 60, -1):
            self.assertEqual(self.Text._budget()[2], 0)

    # --- the settings ------------------------------------------------------------

    def _settings(self):
        return self.env["res.config.settings"].with_user(
            new_test_user(self.env, login="text_system", groups=SYSTEM_GROUPS)
        ).create({})

    def test_the_settings_show_the_numbers_and_the_tools(self):
        self._document("a.txt", b"setting words")
        self._read_all()
        self._document("b.txt", b"not yet")
        settings = self._settings()
        status = self.Text._status()
        self.assertEqual(settings.int_filemanager_text_done, status["done"])
        self.assertEqual(settings.int_filemanager_text_missing, status["missing"])
        self.assertGreaterEqual(settings.int_filemanager_text_done, 1)
        self.assertGreaterEqual(settings.int_filemanager_text_missing, 1)
        self.assertIn("pdfminer", settings.int_filemanager_text_reader)
        self.assertIn("s (", settings.int_filemanager_text_budget)

    def test_the_settings_warn_when_the_time_of_a_run_is_too_short(self):
        with patch.dict(
            config._runtime_options, {"workers": 2, "limit_time_real": 60, "limit_time_real_cron": -1}
        ):
            budget = self._settings().int_filemanager_text_budget
        self.assertIn("Too short", budget)

    def test_the_settings_say_when_the_reader_is_missing(self):
        with patch.object(type(self.Text), "_tools", return_value=False):
            self.assertIn("not installed", self._settings().int_filemanager_text_reader)

    def test_the_settings_show_when_the_action_ran_last(self):
        cron = self.env.ref("int_filemanager.int_filemanager_text_cron")
        cron.sudo().lastcall = "2026-10-14 08:00:00"
        self.assertEqual(str(self._settings().int_filemanager_text_lastcall), "2026-10-14 08:00:00")
