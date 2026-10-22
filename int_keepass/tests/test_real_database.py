import os

from odoo.tests.common import TransactionCase, tagged

from ..kdbx import read_kdbx
from ..models.int_keepass_source import CACHE

PATH = os.environ.get("INT_KEEPASS_TEST_PATH")
PASSWORD = os.environ.get("INT_KEEPASS_TEST_PASSWORD")


@tagged("post_install", "-at_install")
class TestRealDatabase(TransactionCase):
    """Runs against a real .kdbx file when INT_KEEPASS_TEST_PATH and INT_KEEPASS_TEST_PASSWORD are set.

    Asserts only on counts and links, so a failure message never contains an entry.
    """

    def setUp(self):
        super().setUp()
        if not (PATH and PASSWORD):
            self.skipTest("INT_KEEPASS_TEST_PATH / INT_KEEPASS_TEST_PASSWORD not set")
        self.env["ir.config_parameter"].sudo().set_param("int_keepass.kdbx_path", PATH)
        CACHE.clear()
        self.addCleanup(CACHE.clear)
        self.Entry = self.env["int.keepass.entry"].with_context(int_keepass_password=PASSWORD)
        self.Group = self.env["int.keepass.group"].with_context(int_keepass_password=PASSWORD)

    def test_counts_match_the_file(self):
        raw = read_kdbx(PATH, PASSWORD)
        entries = self.Entry.search([])
        groups = self.Group.search([])
        self.assertEqual((len(groups), len(entries)), (len(raw["groups"]), len(raw["entries"])))
        self.assertEqual(self.Entry.search_count([]), len(entries))

    def test_every_link_leads_to_a_group(self):
        entries = self.Entry.search([])
        groups = self.Group.search([])
        self.assertTrue(all(entry.group_id in groups for entry in entries if entry.group_id))
        self.assertTrue(all(group.parent_id in groups for group in groups if group.parent_id))
        self.assertTrue(all(entry.title is not None for entry in entries))

    def test_list_form_and_search_panel_calls(self):
        total = self.Entry.search_count([])
        result = self.Entry.web_search_read([], {"title": {}, "group_id": {"fields": {"display_name": {}}}}, limit=5)
        self.assertEqual(result["length"], total)
        self.assertEqual(len(result["records"]), min(5, total))
        first = self.Entry.search([], limit=1)
        self.assertEqual(len(first.web_read({"title": {}, "username": {}, "url": {}})), 1)
        panel = self.Entry.search_panel_select_range("group_id", expand=True)
        self.assertEqual(len(panel["values"]), self.Group.search_count([]))
        for group in self.Group.search([], limit=3):
            by_group = self.Entry.search([("group_id", "child_of", group.id)])
            self.assertTrue(all(entry.group_id for entry in by_group))
