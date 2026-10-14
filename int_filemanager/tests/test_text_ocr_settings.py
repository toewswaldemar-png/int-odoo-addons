from ast import literal_eval
from unittest.mock import patch

from odoo.tests.common import new_test_user, tagged

from .test_text_ocr import OcrCase

SYSTEM_GROUPS = "base.group_user,base.group_system"
ADMIN_GROUPS = "base.group_user,int_filemanager.int_filemanager_group_admin"


@tagged("post_install", "-at_install")
class TestOcrStatus(OcrCase):
    """The numbers and the words of the status of the text recognition."""

    def _row(self, name, **values):
        return self.Text.create({"checksum": name * 64, **values})

    def test_the_rows_are_counted_by_state(self):
        before = self.Text._ocr_status()["counts"]
        self._row("a", ocr_state="wait")
        self._row("b", ocr_state="wait")
        self._row("c", ocr_state="done")
        self._row("d", ocr_state="failed")
        self._row("e")
        counts = self.Text._ocr_status()["counts"]
        self.assertEqual(counts["wait"] - before["wait"], 2)
        self.assertEqual(counts["done"] - before["done"], 1)
        self.assertEqual(counts["failed"] - before["failed"], 1)

    def test_the_pages_still_to_do_and_the_time_for_them(self):
        self.Text.search([("ocr_state", "!=", False)]).write({"ocr_state": False})
        pdf = {"mimetype": "application/pdf"}
        first = self._row("a", ocr_state="wait", page_count=10, ocr_next_page=4, ocr_seconds_per_page=2, **pdf)
        second = self._row("b", ocr_state="running", page_count=5, ocr_next_page=1, **pdf)
        self._row("c", ocr_state="wait")  # a picture: its pages are not counted yet
        self._row("d", ocr_state="done", page_count=50)
        self._row("e", ocr_state="wait", page_count=4, ocr_next_page=2, mimetype="image/tiff")
        # Scans on 2, 5, 6 and 9 of the first (2 is done), on 1 and 3 of the second.
        pages = [(first, number, True) for number in (2, 5, 6, 9)]
        pages += [(second, 1, True), (second, 2, False), (second, 3, True)]
        self.env["int.filemanager.text.page"].create(
            [{"text_id": text.id, "page": number, "scan": scan} for text, number, scan in pages]
        )
        status = self.Text._ocr_status()
        self.assertEqual(status["pages_left"], 3 + 2 + 1 + 3)
        # 3 pages at 2 s, the 6 others at the guess of 5 s.
        self.assertEqual(status["seconds_left"], 3 * 2 + 6 * 5)

    def test_the_size_of_the_recognized_pdfs(self):
        before = self.Text._ocr_status()["pdf_size"]
        self._row("a", ocr_size=1000)
        self._row("b", ocr_size=500)
        self.assertEqual(self.Text._ocr_status()["pdf_size"] - before, 1500)

    def test_it_says_when_it_is_ready_and_why_not(self):
        self.assertTrue(self.Text._ocr_status()["ready"])
        self.env["ir.config_parameter"].set_param("int_filemanager.ocr_enabled", "0")
        status = self.Text._ocr_status()
        self.assertEqual((status["ready"], status["reason"]), (False, "off"))
        self.env["ir.config_parameter"].set_param("int_filemanager.ocr_enabled", "1")
        self.Text._ocr_block("disk_full", "no space left")
        status = self.Text._ocr_status()
        self.assertEqual((status["reason"], status["detail"]), ("disk_full", "no space left"))

    def test_the_character_set_of_the_database_is_given(self):
        self.assertTrue(self.Text._ocr_status()["lc_ctype"])


@tagged("post_install", "-at_install")
class TestOcrSettings(OcrCase):
    """The settings page: the status in words, and what saving does."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.system = new_test_user(cls.env, login="ocr_system", groups=SYSTEM_GROUPS)

    def _settings(self, **values):
        return self.env["res.config.settings"].with_user(self.system).create(values)

    def test_the_status_in_words(self):
        settings = self._settings()
        self.assertEqual(settings.int_filemanager_ocr_state, "Ready.")
        self.assertIn("ocrmypdf stub", settings.int_filemanager_ocr_tools)
        self.assertIn("deu, eng, osd", settings.int_filemanager_ocr_tools)
        self.assertIn("limit_time_real_cron", settings.int_filemanager_ocr_notes)

    def test_the_reasons_it_does_not_run_are_told(self):
        self.env["ir.config_parameter"].set_param("int_filemanager.ocr_enabled", "0")
        self.assertEqual(self._settings().int_filemanager_ocr_state, "Off.")
        self.env["ir.config_parameter"].set_param("int_filemanager.ocr_enabled", "1")
        self.env["ir.config_parameter"].set_param("int_filemanager.ocr_languages", "deu+fra")
        self.assertIn("lacks a language", self._settings().int_filemanager_ocr_state)
        self.env["ir.config_parameter"].set_param("int_filemanager.ocr_languages", "deu")
        self.Text._ocr_block("disk_full", "no space")
        state = self._settings().int_filemanager_ocr_state
        self.assertIn("disk is full", state)
        self.assertIn("no space", state)

    def test_missing_programs_are_told(self):
        tools = {"program": False, "version": False, "tesseract": False, "languages": set()}
        with patch.object(type(self.Text), "_ocr_tools", lambda *_args: tools):
            settings = self._settings()
            self.assertEqual(settings.int_filemanager_ocr_tools, "not installed")
            self.assertIn("not installed on the server", settings.int_filemanager_ocr_state)

    def test_the_pages_to_do_are_shown_with_the_time(self):
        self.Text.search([("ocr_state", "!=", False)]).write({"ocr_state": False})
        self.Text.create(
            {
                "checksum": "a" * 64,
                "mimetype": "image/tiff",
                "ocr_state": "wait",
                "page_count": 720,
                "ocr_seconds_per_page": 5,
            }
        )
        left = self._settings().int_filemanager_ocr_left
        self.assertIn("720 pages", left)
        self.assertIn("01:00", left)  # 3600 s

    def test_the_numbers_are_the_ones_of_the_status(self):
        self.Text.create({"checksum": "b" * 64, "ocr_state": "failed", "ocr_size": 2048})
        settings = self._settings()
        status = self.Text._ocr_status()
        self.assertEqual(settings.int_filemanager_ocr_failed, status["counts"]["failed"])
        self.assertEqual(settings.int_filemanager_ocr_wait, status["counts"]["wait"])
        self.assertIn("kb", settings.int_filemanager_ocr_pdf_size.lower())

    def test_saving_changes_what_the_recognition_does(self):
        Params = self.env["ir.config_parameter"]
        Params.set_param("int_filemanager.ocr_enabled", "0")
        settings = self._settings(
            int_filemanager_ocr_enabled=True,
            int_filemanager_ocr_languages="eng",
            int_filemanager_ocr_jobs=3,
            int_filemanager_ocr_nice="5",
            int_filemanager_ocr_deskew="0",
            int_filemanager_ocr_output_type="pdfa",
        )
        settings.execute()
        self.assertEqual(
            self.Text._ocr_options(),
            {
                "enabled": True,
                "languages": "eng",
                "jobs": 3,
                "nice": 5,
                "deskew": False,
                "output_type": "pdfa",
            },
        )

    def test_switching_the_recognition_off_again_works(self):
        self._settings(int_filemanager_ocr_enabled=True).execute()
        self.assertTrue(self.Text._ocr_options()["enabled"])
        self._settings(int_filemanager_ocr_enabled=False).execute()
        self.assertFalse(self.Text._ocr_options()["enabled"])

    def test_the_priority_zero_is_a_priority(self):
        self._settings(int_filemanager_ocr_nice="0").execute()
        self.assertEqual(self.Text._ocr_options()["nice"], 0)

    def test_the_defaults_are_the_ones_of_the_recognition(self):
        Params = self.env["ir.config_parameter"].sudo()
        for name in ("languages", "jobs", "nice", "deskew", "output_type", "enabled"):
            Params.search([("key", "=", f"int_filemanager.ocr_{name}")]).unlink()
        settings = self._settings()
        self.assertEqual(
            (
                settings.int_filemanager_ocr_enabled,
                settings.int_filemanager_ocr_languages,
                settings.int_filemanager_ocr_jobs,
                settings.int_filemanager_ocr_nice,
                settings.int_filemanager_ocr_deskew,
                settings.int_filemanager_ocr_output_type,
            ),
            (False, "deu+eng", 1, "19", "1", "pdf"),
        )


@tagged("post_install", "-at_install")
class TestOcrViews(OcrCase):
    """The list of the administrator shows the recognition."""

    def test_the_views_load_with_the_new_fields(self):
        boss = new_test_user(self.env, login="ocr_view_boss", groups=ADMIN_GROUPS)
        views = self.Text.with_user(boss).get_views([(False, "list"), (False, "form"), (False, "search")])
        self.assertIn("ocr_state", views["models"]["int.filemanager.text"]["fields"])

    def test_the_settings_page_has_the_fields_of_the_recognition(self):
        system = new_test_user(self.env, login="ocr_view_system", groups=SYSTEM_GROUPS)
        views = self.env["res.config.settings"].with_user(system).get_views([(False, "form")])
        arch = views["views"]["form"]["arch"]
        for name in ("ocr_enabled", "ocr_languages", "ocr_jobs", "ocr_nice", "ocr_state", "ocr_left"):
            self.assertIn(f"int_filemanager_{name}", arch)

    def test_the_action_of_the_scans_lists_the_rows_with_a_recognition(self):
        self.Text.search([]).write({"ocr_state": False})
        row = self.Text.create({"checksum": "a" * 64, "ocr_state": "done"})
        self.Text.create({"checksum": "b" * 64})
        action = self.env.ref("int_filemanager.int_filemanager_text_ocr_action")
        self.assertEqual(self.Text.search(literal_eval(action.domain)), row)
