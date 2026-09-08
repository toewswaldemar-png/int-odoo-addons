from odoo.tests.common import TransactionCase, tagged

from ..watcher import _watcher_enabled


@tagged("post_install", "-at_install")
class TestWatcherEnabled(TransactionCase):
    """Kill-Switch fuer den Watcher: int_filemanager.watcher_enabled wird nur
    beim Prozessstart gelesen (siehe _run_watcher), aber die reine
    Entscheidungsfunktion laesst sich ohne echten Prozess-Neustart testen."""

    def _set(self, value):
        if value is None:
            self.env["ir.config_parameter"].sudo().search(
                [("key", "=", "int_filemanager.watcher_enabled")]
            ).unlink()
        else:
            self.env["ir.config_parameter"].sudo().set_param("int_filemanager.watcher_enabled", value)

    def test_enabled_by_default_when_unset(self):
        self._set(None)
        self.assertTrue(_watcher_enabled(self.env))

    def test_disabled_by_explicit_false(self):
        for value in ("false", "False", "0", "no", "off"):
            self._set(value)
            self.assertFalse(_watcher_enabled(self.env), "expected disabled for %r" % value)

    def test_enabled_by_explicit_true_variants(self):
        for value in ("true", "True", "1", "yes"):
            self._set(value)
            self.assertTrue(_watcher_enabled(self.env), "expected enabled for %r" % value)
