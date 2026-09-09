from unittest.mock import patch

from odoo.tests.common import TransactionCase, tagged

from ..watcher import _resolve_dbname, _watcher_enabled, config


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


@tagged("post_install", "-at_install")
class TestResolveDbname(TransactionCase):
    """Produktiv laeuft ohne -d/db_name (Odoos eigene Multi-DB-Erkennung waehlt die
    Datenbank), was config["db_name"][0] frueher mit IndexError abstuerzen liess -
    jeder einzelne Prozessstart, seit dieser Code im watcher existiert."""

    def setUp(self):
        super().setUp()
        original = config["db_name"]
        self.addCleanup(lambda: config.__setitem__("db_name", original))

    def test_uses_explicit_db_name_when_configured(self):
        config["db_name"] = ["explicit_db"]
        self.assertEqual(_resolve_dbname(), "explicit_db")

    def test_falls_back_to_sole_database_when_unset(self):
        config["db_name"] = []
        with patch("odoo.addons.int_filemanager.watcher.list_dbs", return_value=["only_one"]):
            self.assertEqual(_resolve_dbname(), "only_one")

    def test_none_when_ambiguous(self):
        config["db_name"] = []
        with patch("odoo.addons.int_filemanager.watcher.list_dbs", return_value=["a", "b"]):
            self.assertIsNone(_resolve_dbname())

    def test_none_when_no_database_found(self):
        config["db_name"] = []
        with patch("odoo.addons.int_filemanager.watcher.list_dbs", return_value=[]):
            self.assertIsNone(_resolve_dbname())
