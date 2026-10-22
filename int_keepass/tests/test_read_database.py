import os
import shutil
import tempfile

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged

from ..models.int_keepass_source import CACHE

try:
    from pykeepass import create_database
except ImportError:
    create_database = None

PASSWORD = "test-only-password"


def make_database(folder, password=PASSWORD):
    """A small database with a group in a group, an entry at the top and one in the recycle bin."""
    path = os.path.join(folder, "test.kdbx")
    database = create_database(path, password=password)
    server = database.add_group(database.root_group, "Server")
    router = database.add_group(server, "Router")
    database.add_entry(router, "Firewall", "admin", "SECRET-PASSWORD", url="https://fw.example", notes="SECRET-NOTE")
    database.add_entry(database.root_group, "Loose", "x", "SECRET-PASSWORD")
    database.add_entry(server, "Deleted", "gone", "SECRET-PASSWORD")
    database.trash_entry(database.find_entries(title="Deleted", first=True))
    database.save()
    return path


@tagged("post_install", "-at_install")
class TestReadDatabase(TransactionCase):
    """The records come from a real .kdbx file, without passwords or notes."""

    def setUp(self):
        super().setUp()
        if create_database is None:
            self.skipTest("pykeepass is not installed")
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        self.path = make_database(folder)
        self.env["ir.config_parameter"].sudo().set_param("int_keepass.kdbx_path", self.path)
        CACHE.clear()
        self.addCleanup(CACHE.clear)
        self.Entry = self.env["int.keepass.entry"].with_context(int_keepass_password=PASSWORD)
        self.Group = self.env["int.keepass.group"].with_context(int_keepass_password=PASSWORD)

    def test_entries_and_groups_come_from_the_file(self):
        entries = self.Entry.search([])
        self.assertEqual(entries.mapped("title"), ["Firewall", "Loose"])
        firewall = entries[0]
        self.assertEqual((firewall.username, firewall.url), ("admin", "https://fw.example"))
        self.assertEqual(firewall.group_id.name, "Router")
        self.assertEqual(firewall.group_id.parent_id.name, "Server")
        self.assertFalse(entries[1].group_id)
        self.assertEqual(self.Group.search([]).mapped("name"), ["Router", "Server"])

    def test_no_secret_reaches_odoo(self):
        entries = self.Entry.search([])
        shown = str(entries.web_read({name: {} for name in entries._fields if name != "id"}))
        self.assertNotIn("SECRET", shown)

    def test_wrong_password(self):
        with self.assertRaisesRegex(UserError, "password is wrong"):
            self.Entry.with_context(int_keepass_password="wrong").search([])

    def test_missing_file(self):
        self.env["ir.config_parameter"].sudo().set_param("int_keepass.kdbx_path", self.path + ".missing")
        with self.assertRaisesRegex(UserError, "was not found"):
            self.Entry.search([])
