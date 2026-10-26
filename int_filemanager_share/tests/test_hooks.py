from odoo.tests.common import TransactionCase, tagged

from odoo.addons.int_filemanager_share.hooks import EARLIER_COLUMNS, pre_init_hook


@tagged("post_install", "-at_install")
class TestPreInitHook(TransactionCase):
    """The hook that drops what the earlier layers left in the table of the shares."""

    def _columns(self):
        self.env.cr.execute(
            """
            SELECT column_name FROM information_schema.columns
             WHERE table_name = 'int_filemanager_share' AND column_name IN %s
            """,
            [EARLIER_COLUMNS],
        )
        return {name for [name] in self.env.cr.fetchall()}

    def test_the_columns_of_the_earlier_layers_are_dropped(self):
        self.env.cr.execute(
            """
            ALTER TABLE int_filemanager_share
                ADD COLUMN node_id integer,
                ADD COLUMN expires_at timestamp,
                ADD COLUMN revoked_at timestamp
            """
        )
        self.assertEqual(self._columns(), set(EARLIER_COLUMNS))
        pre_init_hook(self.env)
        self.assertFalse(self._columns())

    def test_the_hook_runs_twice_without_an_error(self):
        pre_init_hook(self.env)
        pre_init_hook(self.env)
        self.assertFalse(self._columns())
