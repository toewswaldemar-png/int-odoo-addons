import importlib.util

from odoo.modules import Manifest
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestMigrationEarlierLayers(TransactionCase):
    """The script that drops what the removed models left in an existing database."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        path = Manifest.for_addon("int_filemanager").path
        spec = importlib.util.spec_from_file_location(
            "earlier_layers", f"{path}/migrations/19.0.1.0.1/pre-earlier_layers.py"
        )
        cls.script = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.script)

    def _exists(self, table):
        self.env.cr.execute("SELECT to_regclass(%s)", [table])
        return bool(self.env.cr.fetchone()[0])

    def _leave_earlier_layers(self):
        """The state of a database from before the restart: old tables, old columns, old rows."""
        cr = self.env.cr
        cr.execute("CREATE TABLE int_filemanager_node (id serial PRIMARY KEY)")
        cr.execute("CREATE TABLE int_filemanager_file (id serial PRIMARY KEY, name varchar)")
        # The table of the shares belongs to ``int_filemanager_share``: the core makes no claim on it.
        cr.execute("CREATE TABLE IF NOT EXISTS int_filemanager_share (id serial PRIMARY KEY)")
        cr.execute("""
            ALTER TABLE int_filemanager_share
                ADD COLUMN node_id integer REFERENCES int_filemanager_node (id),
                ADD COLUMN expires_at timestamp,
                ADD COLUMN revoked_at timestamp
        """)
        cr.execute("""
            INSERT INTO ir_config_parameter (key, value, create_date, write_date)
            VALUES ('int_filemanager.watcher_enabled', 'true', now(), now())
        """)

    def test_the_tables_columns_and_parameters_of_the_removed_models_are_gone(self):
        self._leave_earlier_layers()
        self.script.migrate(self.env.cr, "19.0.1.0.0")
        for table in self.script.EARLIER_TABLES:
            self.assertFalse(self._exists(table), table)
        self.env.cr.execute("""
            SELECT column_name FROM information_schema.columns
             WHERE table_name = 'int_filemanager_share'
               AND column_name IN ('node_id', 'expires_at', 'revoked_at')
        """)
        self.assertFalse(self.env.cr.fetchall())
        self.assertFalse(self.env["ir.config_parameter"].get_param("int_filemanager.watcher_enabled"))

    def test_the_tables_of_the_models_in_use_stay(self):
        self.script.migrate(self.env.cr, "19.0.1.0.0")
        models = self.env["ir.model"].search([("model", "=like", "int.filemanager.%")])
        for model in models.filtered(lambda m: not self.env[m.model]._abstract):
            self.assertTrue(self._exists(self.env[model.model]._table), model.model)

    def test_the_script_runs_twice_without_an_error(self):
        self._leave_earlier_layers()
        self.script.migrate(self.env.cr, "19.0.1.0.0")
        self.script.migrate(self.env.cr, "19.0.1.0.0")
