from unittest.mock import patch

from odoo.tests.common import TransactionCase, tagged

GIB = 1024**3


@tagged("post_install", "-at_install")
class TestSettingsLimits(TransactionCase):
    """The limits of the uploads and the ZIPs are fields of the settings page (in GB and hours),
    with their defaults and least values."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Document = cls.env["int.filemanager.document"]
        cls.params = cls.env["ir.config_parameter"].sudo()

    def test_the_page_shows_the_defaults(self):
        settings = self.env["res.config.settings"].create({})
        self.assertEqual(settings.int_filemanager_upload_max_gb, 20)
        self.assertEqual(settings.int_filemanager_upload_max_age_hours, 24)
        self.assertEqual(settings.int_filemanager_zip_max_gb, 10)
        self.assertEqual(settings.int_filemanager_trash_enabled, "1")
        self.assertEqual(settings.int_filemanager_trash_days, 30)
        self.assertEqual(self.Document._upload_max_size(), 20 * GIB)
        self.assertEqual(self.Document._zip_max_size(), 10 * GIB)

    def test_the_page_saves_the_limits(self):
        self.env["res.config.settings"].create(
            {
                "int_filemanager_upload_max_gb": 50,
                "int_filemanager_upload_max_age_hours": 6,
                "int_filemanager_zip_max_gb": 3,
                "int_filemanager_trash_enabled": "0",
                "int_filemanager_trash_days": 7,
            }
        ).execute()
        self.assertEqual(self.params.get_param("int_filemanager.upload_max_gb"), "50")
        self.assertEqual(self.params.get_param("int_filemanager.upload_max_age_hours"), "6")
        self.assertEqual(self.params.get_param("int_filemanager.zip_max_gb"), "3")
        self.assertEqual(self.params.get_param("int_filemanager.trash_enabled"), "0")
        self.assertEqual(self.params.get_param("int_filemanager.trash_days"), "7")
        self.assertEqual(self.Document._upload_max_size(), 50 * GIB)
        self.assertEqual(self.Document._zip_max_size(), 3 * GIB)

    def test_the_page_raises_a_number_below_the_least(self):
        names = [
            "int_filemanager_upload_max_gb",
            "int_filemanager_upload_max_age_hours",
            "int_filemanager_zip_max_gb",
            "int_filemanager_preview_seconds",
            "int_filemanager_preview_max_size_mib",
            "int_filemanager_trash_days",
        ]
        result = self.env["res.config.settings"].onchange(
            dict.fromkeys(names, -4), names, {name: {} for name in names}
        )
        self.assertEqual(
            result["value"],
            {
                "int_filemanager_upload_max_gb": 1,
                "int_filemanager_upload_max_age_hours": 1,
                "int_filemanager_zip_max_gb": 1,
                "int_filemanager_preview_seconds": 5,
                "int_filemanager_preview_max_size_mib": 1,
                "int_filemanager_trash_days": 1,
            },
        )

    def test_the_status_says_when_pypdfium2_is_missing(self):
        with patch("importlib.util.find_spec", return_value=None):
            settings = self.env["res.config.settings"].create({})
            self.assertIn("pypdfium2", settings.int_filemanager_thumbnail_state)
        with patch("importlib.util.find_spec", return_value=object()):
            settings = self.env["res.config.settings"].create({})
            self.assertEqual(settings.int_filemanager_thumbnail_state, "Ready.")
