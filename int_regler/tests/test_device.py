from psycopg2 import IntegrityError

from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tests.common import new_test_user
from odoo.tools import mute_logger


@tagged("post_install", "-at_install")
class TestIntReglerDevice(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = new_test_user(cls.env, login="regler_user", groups="base.group_user,int_regler.group_regler_user")
        cls.manager = new_test_user(
            cls.env, login="regler_manager", groups="base.group_user,int_regler.group_regler_manager"
        )
        cls.outsider = new_test_user(cls.env, login="regler_outsider", groups="base.group_user")
        cls.Device = cls.env["int.regler.device"]
        cls.device = cls.Device.create({"name": "Bench", "core_url": "http://127.0.0.1:8085", "device_ref": "main"})

    def test_the_defaults_point_at_the_local_service(self):
        device = self.Device.create({"name": "Defaults"})
        self.assertEqual(device.core_url, "http://127.0.0.1:8085")
        self.assertEqual(device.device_ref, "main")
        self.assertTrue(device.active)

    def test_the_address_loses_spaces_and_closing_slashes(self):
        device = self.Device.create({"name": "Slash", "core_url": " https://host.example/regler// "})
        self.assertEqual(device.core_url, "https://host.example/regler")
        device.write({"core_url": "http://10.0.0.5:8085/"})
        self.assertEqual(device.core_url, "http://10.0.0.5:8085")

    def test_an_address_is_a_url_or_a_path(self):
        for good in ("http://127.0.0.1:8085", "https://regler.example.com", "https://h/regler/x", "/regler"):
            self.Device.create({"name": f"ok {good}", "core_url": good})
        for bad in ("127.0.0.1:8085", "ftp://host", "http://", "has space", "http://host?x=1", "javascript:alert(1)", "/", ""):
            with self.subTest(bad), self.assertRaises(ValidationError), self.cr.savepoint():
                self.Device.create({"name": f"bad {bad}", "core_url": bad})

    def test_the_controller_id_is_what_the_service_accepts(self):
        for good in ("main", "A-1", "tisch_2"):
            self.Device.create({"name": f"id {good}", "device_ref": good})
        for bad in ("", "a b", "a/b", "ä", "../x"):
            with self.subTest(bad), self.assertRaises(ValidationError), self.cr.savepoint():
                self.Device.create({"name": f"badid {bad}", "device_ref": bad})

    def test_a_change_is_checked_too(self):
        with self.assertRaises(ValidationError):
            self.device.write({"core_url": "nonsense"})
        with self.assertRaises(ValidationError):
            self.device.write({"device_ref": "a b"})

    def test_a_name_is_used_once(self):
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"), self.cr.savepoint():
            self.Device.create({"name": "Bench"})

    def test_a_user_reads_but_does_not_write(self):
        device = self.device.with_user(self.user)
        self.assertEqual(device.core_url, "http://127.0.0.1:8085")
        with self.assertRaises(AccessError):
            device.write({"name": "Other"})
        with self.assertRaises(AccessError):
            self.Device.with_user(self.user).create({"name": "New"})
        with self.assertRaises(AccessError):
            device.unlink()

    def test_a_manager_writes(self):
        created = self.Device.with_user(self.manager).create({"name": "Made by the manager"})
        created.write({"note": "ok"})
        created.unlink()

    def test_somebody_without_the_group_reads_nothing(self):
        with self.assertRaises(AccessError):
            self.device.with_user(self.outsider).read(["name"])

    def test_the_manager_group_includes_the_user_group(self):
        manager_group = self.env.ref("int_regler.group_regler_manager")
        self.assertIn(self.env.ref("int_regler.group_regler_user"), manager_group.all_implied_ids)

    def test_the_page_is_in_the_menu_of_the_users_only(self):
        menu = self.env.ref("int_regler.int_regler_menu_root")
        self.assertIn(self.env.ref("int_regler.group_regler_user"), menu.group_ids)
        action = self.env.ref("int_regler.int_regler_app_action")
        self.assertEqual(action.tag, "int_regler.app")
