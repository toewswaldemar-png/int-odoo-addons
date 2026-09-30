"""The trigram index of the text search needs the pg_trgm extension, which Odoo only
creates in databases it made itself."""

from odoo.tests.common import TransactionCase, tagged

from .. import pg_extensions


@tagged("post_install", "-at_install")
class TestV2PgExtensions(TransactionCase):
    def test_a_missing_extension_is_created_and_the_registry_told(self):
        registry = self.env.registry
        was_there = registry.has_trigram
        self.addCleanup(setattr, registry, "has_trigram", was_there)
        # The rollback at the end of the test brings the extension and the trigram
        # indexes of every table back.
        self.env.cr.execute("DROP EXTENSION IF EXISTS pg_trgm CASCADE")
        registry.has_trigram = False
        self.assertTrue(pg_extensions.ensure_trigram(registry, self.env.cr))
        self.assertTrue(registry.has_trigram)
        self.env.cr.execute("SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm'")
        self.assertTrue(self.env.cr.fetchone())

    def test_nothing_is_done_when_the_extension_is_there(self):
        registry = self.env.registry
        if not registry.has_trigram:
            self.skipTest("pg_trgm is not available in this database")
        self.assertTrue(pg_extensions.ensure_trigram(registry, self.env.cr))

    def test_an_extension_that_cannot_be_created_is_reported_not_raised(self):
        with self.assertLogs(pg_extensions.__name__, "WARNING"):
            self.assertFalse(
                pg_extensions.ensure_extension(self.env.cr, "int_no_such_extension")
            )
        # The transaction is still usable afterwards.
        self.env.cr.execute("SELECT 1")
        self.assertEqual(self.env.cr.fetchone(), (1,))
