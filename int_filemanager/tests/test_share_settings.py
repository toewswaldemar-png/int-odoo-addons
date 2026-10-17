from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestShareSettings(TransactionCase):
    """The settings of the shares: numbers of at least 1, start values below the highest."""

    def _settings(self, **values):
        return self.env["res.config.settings"].create(
            {f"int_filemanager_share_{name}": value for name, value in values.items()}
        )

    def test_the_settings_start_with_the_values_of_the_code(self):
        settings = self._settings()
        self.assertEqual(settings.int_filemanager_share_creators, "user")
        self.assertEqual(settings.int_filemanager_share_default_file_mb, 25)
        self.assertEqual(settings.int_filemanager_share_max_file_mb, 200)
        self.assertEqual(settings.int_filemanager_share_password_length, 8)

    def test_the_numbers_are_at_least_1(self):
        for name in (
            "default_file_mb",
            "default_total_mb",
            "default_files",
            "max_file_mb",
            "max_total_mb",
            "max_files",
            "password_length",
            "unlock_hours",
            "invalid_tokens",
            "requests_per_minute",
            "uploads_per_minute",
            "password_tries_ip",
            "password_tries_share",
        ):
            for value in (0, -1):
                with self.subTest(name=name, value=value), self.assertRaises(ValidationError):
                    self._settings(**{name: value})

    def test_a_start_value_is_not_above_the_highest(self):
        with self.assertRaises(ValidationError):
            self._settings(default_file_mb=300)
        with self.assertRaises(ValidationError):
            self._settings(max_files=50)
        self._settings(default_file_mb=300, max_file_mb=300)

    def test_what_is_saved_is_what_the_shares_use(self):
        Share = self.env["int.filemanager.share"]
        settings = self._settings(
            creators="admin",
            default_file_mb=30,
            max_file_mb=60,
            default_extensions="pdf, jpg",
            password_length=12,
        )
        settings.set_values()
        self.assertEqual(Share._setting("share_creators"), "admin")
        self.assertEqual(Share._setting("share_default_file_mb"), 30)
        self.assertEqual(Share._setting("share_max_file_mb"), 60)
        self.assertEqual(Share._setting("share_default_extensions"), "pdf, jpg")
        self.assertEqual(Share._setting("share_password_length"), 12)
        self._settings(creators="user").set_values()
        self.assertEqual(Share._setting("share_creators"), "user")
