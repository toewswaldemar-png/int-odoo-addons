from unittest.mock import patch

from odoo.tests.common import TransactionCase, tagged

SOURCE = "odoo.addons.int_keepass.models.int_keepass_source.IntKeepassSource._read_database"

UUIDS = [f"00000000-0000-0000-0000-{n:012d}" for n in range(1, 10)]
SERVER, ROUTER, WEB = UUIDS[0:3]

RAW = {
    "groups": [
        {"uuid": SERVER, "name": "Server", "parent": None},
        {"uuid": ROUTER, "name": "Router", "parent": SERVER},
        {"uuid": WEB, "name": "Web", "parent": None},
    ],
    "entries": [
        {"uuid": UUIDS[3], "title": "Firewall", "username": "admin", "url": "https://fw.example", "group": ROUTER},
        {"uuid": UUIDS[4], "title": "Backup", "username": "root", "url": False, "group": SERVER},
        {"uuid": UUIDS[5], "title": "Shop", "username": "shop", "url": "https://shop.example", "group": WEB},
        {"uuid": UUIDS[6], "title": "Loose entry", "username": False, "url": False, "group": None},
    ],
}


@tagged("post_install", "-at_install")
class TestVirtualRecords(TransactionCase):
    """Groups and entries are ordinary records that never touch the database."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Entry = cls.env["int.keepass.entry"]
        cls.Group = cls.env["int.keepass.group"]
        patcher = patch(SOURCE, return_value=RAW)
        patcher.start()
        cls.addClassCleanup(patcher.stop)

    def _id(self, uuid_text):
        return self.env["int.keepass.source"]._id_of(uuid_text)

    def test_search_returns_all_entries_by_title(self):
        self.assertEqual(self.Entry.search([]).mapped("title"), ["Backup", "Firewall", "Loose entry", "Shop"])
        self.assertEqual(self.Entry.search_count([]), 4)

    def test_search_filters_on_computed_fields(self):
        self.assertEqual(self.Entry.search([("title", "ilike", "fire")]).mapped("title"), ["Firewall"])
        self.assertEqual(self.Entry.search([("username", "=", "root")]).mapped("title"), ["Backup"])

    def test_offset_and_limit(self):
        self.assertEqual(self.Entry.search([], offset=1, limit=2).mapped("title"), ["Firewall", "Loose entry"])

    def test_order_by_a_column_and_by_a_relation(self):
        self.assertEqual(self.Entry.search([], order="title desc").mapped("title"), ["Shop", "Loose entry", "Firewall", "Backup"])
        self.assertEqual(self.Entry.search([("group_id", "!=", False)], order="group_id, title").mapped("title"), ["Firewall", "Backup", "Shop"])

    def test_group_child_of_includes_subgroups(self):
        server = self.Group.browse(self._id(SERVER))
        titles = self.Entry.search([("group_id", "child_of", server.id)]).mapped("title")
        self.assertEqual(titles, ["Backup", "Firewall"])

    def test_group_equals_excludes_subgroups(self):
        server = self.Group.browse(self._id(SERVER))
        self.assertEqual(self.Entry.search([("group_id", "=", server.id)]).mapped("title"), ["Backup"])

    def test_web_search_read_as_the_list_view_calls_it(self):
        result = self.Entry.web_search_read([], {"title": {}, "group_id": {"fields": {"display_name": {}}}}, limit=2)
        self.assertEqual(result["length"], 4)
        self.assertEqual([record["title"] for record in result["records"]], ["Backup", "Firewall"])
        self.assertEqual(result["records"][1]["group_id"]["display_name"], "Router")

    def test_web_read_as_the_form_view_calls_it(self):
        entry = self.Entry.browse(self._id(UUIDS[3]))
        record = entry.web_read({"title": {}, "username": {}, "url": {}})[0]
        self.assertEqual((record["title"], record["username"], record["url"]), ("Firewall", "admin", "https://fw.example"))

    def test_group_names_and_parent(self):
        router = self.Group.browse(self._id(ROUTER))
        self.assertEqual(router.name, "Router")
        self.assertEqual(router.parent_id.name, "Server")
        self.assertFalse(self.Group.browse(self._id(SERVER)).parent_id)

    def test_search_panel_range_is_a_tree(self):
        result = self.Entry.search_panel_select_range("group_id", expand=True)
        self.assertEqual(result["parent_field"], "parent_id")
        parents = {value["display_name"]: value["parent_id"] for value in result["values"]}
        self.assertEqual(set(parents), {"Server", "Router", "Web"})
        self.assertEqual(parents["Router"], self._id(SERVER))
        self.assertFalse(parents["Server"])

    def test_nothing_is_stored(self):
        self.Entry.search([])
        self.env.cr.execute("SELECT to_regclass('int_keepass_entry'), to_regclass('int_keepass_group')")
        self.assertEqual(self.env.cr.fetchone(), (None, None))
