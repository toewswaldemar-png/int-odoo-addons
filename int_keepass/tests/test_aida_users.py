import json
from unittest.mock import patch

from psycopg2 import IntegrityError

from odoo.exceptions import AccessError
from odoo.tests.common import HttpCase, TransactionCase, new_test_user, tagged
from odoo.tools import mute_logger

SOURCE = "odoo.addons.int_keepass.models.int_keepass_source.IntKeepassSource._read_database"
AIDA = "http://aida.example.test:40080/00.00.00.00000/de.aidaorga.aida.ewas.central/#/x?InstanceID=0"


def uuid_of(number):
    return f"00000000-0000-0000-0000-{number:012d}"


def entry(number, username, url=AIDA):
    return {"uuid": uuid_of(number), "title": username, "username": username, "url": url, "group": None}


RAW = {
    "groups": [],
    "entries": [
        entry(1, "Epp, Nikolai"),
        entry(2, "Keller, Max"),
        entry(3, "Keller, Max"),  # the same name twice is one name
        entry(4, "  Pauli, David  "),  # blanks around it are not part of the name
        entry(5, "router-admin", url="https://router.example"),  # not an AIDA address
        entry(6, "nobody", url=None),
        entry(7, None),
        entry(8, "UPPER, Case", url=AIDA.upper()),  # the address is compared without regard to case
    ],
}


class AidaCase(TransactionCase):
    def setUp(self):
        super().setUp()
        self.Entry = self.env["int.keepass.entry"]
        self.Users = self.env["int.keepass.aida.user"].with_context(active_test=False)

    def sync(self, raw=RAW):
        self.env.cr.cache.clear()
        with patch(SOURCE, return_value=raw):
            return self.Entry.action_sync_aida_users()

    def names(self, active=True):
        return sorted(self.Users.search([("active", "=", active)]).mapped("name"))


@tagged("post_install", "-at_install")
class TestSyncAidaUsers(AidaCase):
    def test_only_the_names_of_aida_entries_are_taken_over(self):
        result = self.sync()
        self.assertEqual(self.names(), ["Epp, Nikolai", "Keller, Max", "Pauli, David", "UPPER, Case"])
        self.assertEqual(result, {"added": 4, "removed": 0, "total": 4})

    def test_a_second_run_changes_nothing(self):
        self.sync()
        self.assertEqual(self.sync(), {"added": 0, "removed": 0, "total": 4})

    def test_a_name_that_is_gone_is_archived_and_comes_back(self):
        self.sync()
        fewer = {**RAW, "entries": [e for e in RAW["entries"] if e["username"] != "Epp, Nikolai"]}
        self.assertEqual(self.sync(fewer), {"added": 0, "removed": 1, "total": 3})
        self.assertEqual(self.names(active=False), ["Epp, Nikolai"])
        self.assertEqual(self.sync(), {"added": 1, "removed": 0, "total": 4})
        self.assertEqual(self.names(active=False), [])
        self.assertEqual(self.Users.search_count([("name", "=", "Epp, Nikolai")]), 1)  # the same record, not a second one

    def test_the_text_that_marks_an_address_can_be_set(self):
        self.env["ir.config_parameter"].sudo().set_param("int_keepass.aida_url_match", "router.example")
        self.assertEqual(self.sync(), {"added": 1, "removed": 0, "total": 1})
        self.assertEqual(self.names(), ["router-admin"])

    def test_nothing_but_the_name_is_kept(self):
        self.sync()
        self.assertEqual(set(self.Users._fields) - set(self.env["base"]._fields) - {"create_uid", "create_date", "write_uid", "write_date", "display_name"}, {"name", "active"})

    def test_only_administrators_can_take_names_over(self):
        user = new_test_user(self.env, login="plain-user", groups="base.group_user")
        with self.assertRaises(AccessError):
            self.Entry.with_user(user).action_sync_aida_users()

    def test_a_name_exists_once(self):
        self.Users.create({"name": "Epp, Nikolai"})
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"), self.cr.savepoint():
            self.Users.create({"name": "Epp, Nikolai"})


@tagged("post_install", "-at_install")
class TestAidaUsersEndpoint(HttpCase):
    def setUp(self):
        super().setUp()
        self.env["int.keepass.aida.user"].create([{"name": "Pauli, David"}, {"name": "Epp, Nikolai"}, {"name": "Old, One", "active": False}])
        self.env["ir.config_parameter"].sudo().set_param("int_keepass.aida_token", "tök3n-€")

    def test_the_names_behind_the_token(self):
        response = self.url_open("/int_keepass/aida_users", params={"token": "tök3n-€"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content), {"users": ["Epp, Nikolai", "Pauli, David"]})
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertEqual(response.headers["Access-Control-Allow-Origin"], "*")

    def test_a_missing_or_wrong_token_is_a_404(self):
        for params in ({}, {"token": ""}, {"token": "wrong"}, {"token": "tök3n-€x"}):
            with self.subTest(params=params):
                self.assertEqual(self.url_open("/int_keepass/aida_users", params=params).status_code, 404)

    def test_without_a_token_in_the_settings_the_page_does_not_exist(self):
        self.env["ir.config_parameter"].sudo().set_param("int_keepass.aida_token", "")
        for params in ({}, {"token": ""}):
            self.assertEqual(self.url_open("/int_keepass/aida_users", params=params).status_code, 404)
