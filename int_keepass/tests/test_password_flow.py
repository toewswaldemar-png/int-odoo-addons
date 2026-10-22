import base64
import json
import os
import shutil
import tempfile
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests.common import HttpCase, TransactionCase, tagged

from ..cache import MetadataCache, cache_key
from ..kdbx import read_kdbx
from ..models.int_keepass_source import CACHE, PASSWORD_HEADER
from .test_read_database import PASSWORD, create_database, make_database

READ = "odoo.addons.int_keepass.models.int_keepass_source.read_kdbx"


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


@tagged("post_install", "-at_install")
class TestMetadataCache(TransactionCase):
    def test_entries_expire_a_fixed_time_after_they_were_put_in(self):
        clock = FakeClock()
        cache = MetadataCache(clock=clock)
        cache.put("a", {"x": 1}, ttl=10)
        clock.now = 9
        self.assertEqual(cache.get("a"), {"x": 1})  # using it does not extend it
        clock.now = 11
        self.assertIsNone(cache.get("a"))
        self.assertEqual(len(cache), 0)

    def test_the_number_of_entries_is_bounded(self):
        clock = FakeClock()
        cache = MetadataCache(max_items=2, clock=clock)
        for index, key in enumerate("abc"):
            clock.now = index
            cache.put(key, index, ttl=100)
        self.assertIsNone(cache.get("a"))
        self.assertEqual((cache.get("b"), cache.get("c")), (1, 2))

    def test_drop_and_clear(self):
        cache = MetadataCache()
        cache.put("a", 1, ttl=100)
        cache.put("b", 2, ttl=100)
        cache.drop("a")
        self.assertEqual(len(cache), 1)
        cache.clear()
        self.assertEqual(len(cache), 0)


@tagged("post_install", "-at_install")
class TestCacheKey(TransactionCase):
    def setUp(self):
        super().setUp()
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        self.path = os.path.join(folder, "file.kdbx")
        with open(self.path, "wb") as handle:
            handle.write(b"one")

    def test_key_depends_on_password_and_state_of_the_file(self):
        key = cache_key(self.path, "a")
        self.assertEqual(key, cache_key(self.path, "a"))
        self.assertNotEqual(key, cache_key(self.path, "b"))
        with open(self.path, "wb") as handle:
            handle.write(b"changed")
        self.assertNotEqual(key, cache_key(self.path, "a"))

    def test_key_holds_no_password(self):
        self.assertNotIn("secret-word", cache_key(self.path, "secret-word"))

    def test_missing_file(self):
        with self.assertRaises(FileNotFoundError):
            cache_key(self.path + ".missing", "a")


@tagged("post_install", "-at_install")
class TestWorkerCache(TransactionCase):
    """The file is read once per password while the worker keeps the groups and entries."""

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

    def _fresh_transaction(self):
        """What the next request sees: nothing of the cursor cache, only the worker's cache."""
        self.env.cr.cache.clear()

    def test_second_request_does_not_read_the_file(self):
        with patch(READ, wraps=read_kdbx) as reader:
            self.Entry.search([])
            self._fresh_transaction()
            self.Entry.search([])
            self.assertEqual(reader.call_count, 1)

    def test_a_changed_file_is_read_again(self):
        with patch(READ, wraps=read_kdbx) as reader:
            self.assertEqual(self.Entry.search([]).mapped("title"), ["Firewall", "Loose"])
            from pykeepass import PyKeePass

            database = PyKeePass(self.path, password=PASSWORD)
            database.add_entry(database.root_group, "Added", "u", "p")
            database.save()
            self._fresh_transaction()
            self.assertEqual(self.Entry.search([]).mapped("title"), ["Added", "Firewall", "Loose"])
            self.assertEqual(reader.call_count, 2)

    def test_lock_makes_the_worker_forget(self):
        with patch(READ, wraps=read_kdbx) as reader:
            self.Entry.search([])
            self.Entry.action_lock()
            self._fresh_transaction()
            self.Entry.search([])
            self.assertEqual(reader.call_count, 2)

    def test_unlock_reads_afresh_and_refresh_makes_the_next_read_afresh(self):
        with patch(READ, wraps=read_kdbx) as reader:
            self.Entry.search([])
            self._fresh_transaction()
            self.Entry.action_unlock()  # the screen of the password: never a copy of a few minutes ago
            self.assertEqual(reader.call_count, 2)
            self._fresh_transaction()
            self.Entry.search([])
            self.assertEqual(reader.call_count, 2)
            self.Entry.action_refresh()
            self._fresh_transaction()
            self.Entry.search([])
            self.assertEqual(reader.call_count, 3)

    def test_cache_can_be_switched_off(self):
        self.env["ir.config_parameter"].sudo().set_param("int_keepass.cache_seconds", "0")
        with patch(READ, wraps=read_kdbx) as reader:
            self.Entry.search([])
            self._fresh_transaction()
            self.Entry.search([])
            self.assertEqual(reader.call_count, 2)
            self.assertEqual(len(CACHE), 0)

    def test_wrong_password_is_not_cached_and_no_password_is_locked(self):
        with self.assertRaisesRegex(UserError, "password is wrong"):
            self.Entry.with_context(int_keepass_password="wrong").search([])
        self.assertEqual(len(CACHE), 0)
        self._fresh_transaction()
        with self.assertRaisesRegex(UserError, "locked"):
            self.env["int.keepass.entry"].with_context(int_keepass_password=False).search([])


@tagged("post_install", "-at_install")
class TestPasswordHeader(HttpCase):
    """The browser sends the password as a header; nothing of it reaches the context or the database."""

    def setUp(self):
        super().setUp()
        if create_database is None:
            self.skipTest("pykeepass is not installed")
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        self.password = "pässwörd-€"  # not Latin-1: the header carries base64 of the UTF-8 bytes
        self.path = make_database(folder, password=self.password)
        self.env["ir.config_parameter"].sudo().set_param("int_keepass.kdbx_path", self.path)
        CACHE.clear()
        self.addCleanup(CACHE.clear)
        self.authenticate("admin", "admin")

    def _call(self, method, password=None, **kwargs):
        headers = {"Content-Type": "application/json"}
        if password is not None:
            headers[PASSWORD_HEADER] = base64.b64encode(password.encode()).decode()
        body = {"jsonrpc": "2.0", "method": "call", "params": {"model": "int.keepass.entry", "method": method, "args": [], "kwargs": kwargs}}
        response = self.url_open(f"/web/dataset/call_kw/int.keepass.entry/{method}", data=json.dumps(body), headers=headers)
        return response.json()

    def test_unlock_with_the_header(self):
        self.assertEqual(self._call("action_unlock", self.password).get("result"), True)

    def test_list_call_with_the_header(self):
        result = self._call("web_search_read", self.password, domain=[], specification={"title": {}}, limit=80)
        self.assertEqual([r["title"] for r in result["result"]["records"]], ["Firewall", "Loose"])

    def test_without_the_header_it_is_locked(self):
        self.assertIn("locked", self._call("action_unlock")["error"]["data"]["message"])

    def test_wrong_password(self):
        self.assertIn("password is wrong", self._call("action_unlock", "wrong")["error"]["data"]["message"])

    def test_malformed_header(self):
        headers = {"Content-Type": "application/json", PASSWORD_HEADER: "***not base64***"}
        body = {"jsonrpc": "2.0", "method": "call", "params": {"model": "int.keepass.entry", "method": "action_unlock", "args": [], "kwargs": {}}}
        response = self.url_open("/web/dataset/call_kw/int.keepass.entry/action_unlock", data=json.dumps(body), headers=headers)
        self.assertIn("wrong form", response.json()["error"]["data"]["message"])

    def test_no_secret_in_a_response(self):
        result = self._call("web_search_read", self.password, domain=[], specification={"title": {}, "username": {}, "url": {}}, limit=80)
        self.assertNotIn("SECRET", json.dumps(result))
        self.assertNotIn(self.password, json.dumps(result))
