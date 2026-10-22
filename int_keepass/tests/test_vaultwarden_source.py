import base64
import json
import os
from unittest.mock import patch

import requests

from odoo.exceptions import UserError
from odoo.tests.common import HttpCase, TransactionCase, tagged

from .. import vaultwarden
from ..models.int_keepass_source import CACHE, EMAIL_HEADER, PASSWORD_HEADER

READ = "odoo.addons.int_keepass.vaultwarden.read_vaultwarden"
PINNED = "odoo.addons.int_keepass.vaultwarden.pinned_session"
URL = "https://vault.example.test:6443"
FIRST, SECOND = "00000000-0000-0000-0000-000000000001", "00000000-0000-0000-0000-000000000002"
RAW = {
    "groups": [{"uuid": FIRST, "name": "Server", "parent": None}],
    "entries": [
        {"uuid": SECOND, "title": "Firewall", "username": "admin", "url": "https://fw.example", "group": FIRST},
    ],
    "skipped": {"organization": 0, "trash": 0},
}


class VaultwardenCase(TransactionCase):
    def setUp(self):
        super().setUp()
        params = self.env["ir.config_parameter"].sudo()
        params.set_param("int_keepass.source", "vaultwarden")
        params.set_param("int_keepass.vaultwarden_url", URL)
        CACHE.clear()
        self.addCleanup(CACHE.clear)
        self.Entry = self.env["int.keepass.entry"].with_context(int_keepass_password="master", int_keepass_email="me@example.test")

    def _fresh_transaction(self):
        self.env.cr.cache.clear()


@tagged("post_install", "-at_install")
class TestVaultwardenSource(VaultwardenCase):
    def test_records_come_from_the_account(self):
        with patch(READ, return_value=RAW) as reader:
            entries = self.Entry.search([])
            self.assertEqual(entries.mapped("title"), ["Firewall"])
            self.assertEqual(entries.group_id.name, "Server")
            reader.assert_called_once_with(URL, "me@example.test", "master", session=None)

    def test_the_email_address_defaults_to_the_one_of_the_user(self):
        self.env.user.email = "Own@Example.Test"
        with patch(READ, return_value=RAW) as reader:
            self.env["int.keepass.entry"].with_context(int_keepass_password="master").search([])
            self.assertEqual(reader.call_args.args[1], "Own@Example.Test")

    def test_second_request_is_served_by_the_worker(self):
        with patch(READ, return_value=RAW) as reader:
            self.Entry.search([])
            self._fresh_transaction()
            self.Entry.search([])
            self.assertEqual(reader.call_count, 1)
            self._fresh_transaction()
            self.Entry.with_context(int_keepass_email="other@example.test").search([])
            self.assertEqual(reader.call_count, 2)  # another account is another entry of the cache

    def test_lock_makes_the_worker_forget(self):
        with patch(READ, return_value=RAW) as reader:
            self.Entry.search([])
            self.Entry.action_lock()
            self._fresh_transaction()
            self.Entry.search([])
            self.assertEqual(reader.call_count, 2)

    def test_a_change_in_vaultwarden_shows_after_unlock_or_refresh(self):
        changed = {**RAW, "groups": RAW["groups"] + [{"uuid": "00000000-0000-0000-0000-000000000003", "name": "New folder", "parent": None}]}
        with patch(READ, side_effect=[RAW, changed, RAW]) as reader:
            self.assertEqual(self.env["int.keepass.group"].with_context(**self.Entry.env.context).search([]).mapped("name"), ["Server"])
            self._fresh_transaction()
            self.Entry.action_unlock()  # reads afresh
            self._fresh_transaction()
            self.assertEqual(self.env["int.keepass.group"].with_context(**self.Entry.env.context).search([]).mapped("name"), ["New folder", "Server"])
            self.assertEqual(reader.call_count, 2)
            self.Entry.action_refresh()
            self._fresh_transaction()
            self.assertEqual(self.env["int.keepass.group"].with_context(**self.Entry.env.context).search([]).mapped("name"), ["Server"])
            self.assertEqual(reader.call_count, 3)

    def test_a_pinned_certificate_is_used(self):
        self.env["ir.config_parameter"].sudo().set_param("int_keepass.vaultwarden_cert_sha256", "ab" * 32)
        with patch(READ, return_value=RAW) as reader, patch(PINNED, return_value="session") as pinned:
            self.Entry.search([])
            pinned.assert_called_once_with("ab" * 32)
            self.assertEqual(reader.call_args.kwargs["session"], "session")

    def test_what_the_user_is_told(self):
        failures = {
            "wrong": (vaultwarden.BadCredentials("x"), "e-mail address or the master password"),
            "second step": (vaultwarden.TwoFactorRequired("x"), "second step"),
            "certificate": (requests.exceptions.SSLError("x"), "certificate"),
            "unreachable": (requests.exceptions.ConnectionError("x"), "cannot be reached"),
            "slowing": (requests.exceptions.HTTPError(response=type("R", (), {"status_code": 429})()), "slowing down"),
            "other": (requests.exceptions.HTTPError(response=type("R", (), {"status_code": 500})()), "HTTP 500"),
        }
        for label, (error, text) in failures.items():
            with self.subTest(label), patch(READ, side_effect=error):
                self._fresh_transaction()
                CACHE.clear()
                with self.assertRaisesRegex(UserError, text):
                    self.Entry.search([])

    def test_no_secret_in_a_message(self):
        with patch(READ, side_effect=requests.exceptions.ConnectionError("master me@example.test")):
            with self.assertRaises(UserError) as caught:
                self.Entry.search([])
        self.assertNotIn("master", str(caught.exception.args[0]))

    def test_locked_without_password(self):
        with self.assertRaisesRegex(UserError, "locked"):
            self.env["int.keepass.entry"].with_context(int_keepass_password=False).search([])

    def test_configuration_is_checked(self):
        params = self.env["ir.config_parameter"].sudo()
        params.set_param("int_keepass.vaultwarden_url", "")
        with self.assertRaisesRegex(UserError, "vaultwarden_url"):
            self.Entry.search([])
        params.set_param("int_keepass.source", "nonsense")
        with self.assertRaisesRegex(UserError, "must be one of"):
            self.Entry.search([])

    def test_source_info_for_the_unlock_screen(self):
        self.env.user.email = "own@example.test"
        info = self.env["int.keepass.entry"].get_source_info()
        self.assertEqual(info, {"source": "vaultwarden", "email": "own@example.test"})
        self.env["ir.config_parameter"].sudo().set_param("int_keepass.source", "kdbx")
        self.assertEqual(self.env["int.keepass.entry"].get_source_info()["source"], "kdbx")


@tagged("post_install", "-at_install")
class TestVaultwardenHeaders(HttpCase):
    """The browser's two headers reach the reader as the text that was typed."""

    def setUp(self):
        super().setUp()
        params = self.env["ir.config_parameter"].sudo()
        params.set_param("int_keepass.source", "vaultwarden")
        params.set_param("int_keepass.vaultwarden_url", URL)
        CACHE.clear()
        self.addCleanup(CACHE.clear)
        self.authenticate("admin", "admin")

    def _call(self, method, **headers):
        headers = {"Content-Type": "application/json", **{k: base64.b64encode(v.encode()).decode() for k, v in headers.items()}}
        body = {"jsonrpc": "2.0", "method": "call", "params": {"model": "int.keepass.entry", "method": method, "args": [], "kwargs": {}}}
        return self.url_open(f"/web/dataset/call_kw/int.keepass.entry/{method}", data=json.dumps(body), headers=headers).json()

    def test_password_and_email_header(self):
        with patch(READ, return_value=RAW) as reader:
            self.assertTrue(self._call("action_unlock", **{PASSWORD_HEADER: "pässwörd-€", EMAIL_HEADER: "wäldi@example.test"})["result"])
        self.assertEqual(reader.call_args.args[1:3], ("wäldi@example.test", "pässwörd-€"))

    def test_source_info_needs_no_password(self):
        result = self._call("get_source_info")["result"]
        self.assertEqual(result["source"], "vaultwarden")


# not "standard": the core blocks every request to another host in the tests of that tag
@tagged("post_install", "-at_install", "-standard", "external")
class TestRealVaultwarden(TransactionCase):
    """Runs against a real Vaultwarden when INT_VW_URL, INT_VW_EMAIL and INT_VW_PASSWORD are set (INT_VW_PIN is the fingerprint).
    Selected on its own: --test-tags /int_keepass:TestRealVaultwarden

    Asserts only on counts and links, so a failure message never contains an entry.
    """

    def setUp(self):
        super().setUp()
        self.url, self.email, self.password = (os.environ.get(name) for name in ("INT_VW_URL", "INT_VW_EMAIL", "INT_VW_PASSWORD"))
        if not (self.url and self.email and self.password):
            self.skipTest("INT_VW_URL / INT_VW_EMAIL / INT_VW_PASSWORD not set")
        params = self.env["ir.config_parameter"].sudo()
        params.set_param("int_keepass.source", "vaultwarden")
        params.set_param("int_keepass.vaultwarden_url", self.url)
        params.set_param("int_keepass.vaultwarden_cert_sha256", os.environ.get("INT_VW_PIN", ""))
        CACHE.clear()
        self.addCleanup(CACHE.clear)
        self.Entry = self.env["int.keepass.entry"].with_context(int_keepass_password=self.password, int_keepass_email=self.email)
        self.Group = self.env["int.keepass.group"].with_context(int_keepass_password=self.password, int_keepass_email=self.email)

    def test_the_records_match_the_account(self):
        pin = os.environ.get("INT_VW_PIN")
        raw = vaultwarden.read_vaultwarden(self.url, self.email, self.password, session=vaultwarden.pinned_session(pin) if pin else None)
        entries, groups = self.Entry.search([]), self.Group.search([])
        self.assertEqual((len(groups), len(entries)), (len(raw["groups"]), len(raw["entries"])))
        self.assertTrue(all(entry.group_id in groups for entry in entries if entry.group_id))

    def test_list_form_and_search_panel_calls(self):
        total = self.Entry.search_count([])
        result = self.Entry.web_search_read([], {"title": {}, "group_id": {"fields": {"display_name": {}}}}, limit=5)
        self.assertEqual(result["length"], total)
        if total:
            self.assertEqual(len(self.Entry.search([], limit=1).web_read({"title": {}, "username": {}, "url": {}})), 1)
        panel = self.Entry.search_panel_select_range("group_id", expand=True)
        self.assertEqual(len(panel["values"]), self.Group.search_count([]))

    def test_wrong_password(self):
        with self.assertRaisesRegex(UserError, "wrong"):
            self.Entry.with_context(int_keepass_password=self.password + "x").search([])
