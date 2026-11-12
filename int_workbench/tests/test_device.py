from psycopg2 import IntegrityError

from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tests.common import new_test_user
from odoo.tools import mute_logger


@tagged("post_install", "-at_install")
class TestIntWorkbenchDevice(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = new_test_user(cls.env, login="regler_user", groups="base.group_user,int_workbench.int_workbench_group_user")
        cls.manager = new_test_user(
            cls.env, login="regler_manager", groups="base.group_user,int_workbench.int_workbench_group_manager"
        )
        cls.outsider = new_test_user(cls.env, login="regler_outsider", groups="base.group_user")
        cls.service = new_test_user(cls.env, login="regler_service", groups="int_workbench.int_workbench_group_service")
        cls.Device = cls.env["int.workbench.device"]
        cls.device = cls.Device.create({"name": "Bench", "device_ref": "main", "service_user_id": cls.service.id})

    def test_the_defaults(self):
        device = self.Device.create({"name": "Defaults", "service_user_id": self.service.id})
        self.assertEqual(device.device_ref, "main")
        self.assertTrue(device.active)
        self.assertFalse(device.snapshot)
        self.assertFalse(device.snapshot_at)

    def test_the_controller_id_is_what_the_service_accepts(self):
        for good in ("main", "A-1", "tisch_2"):
            self.Device.create({"name": f"id {good}", "device_ref": good, "service_user_id": self.service.id})
        for bad in ("", "a b", "a/b", "ä", "../x"):
            with self.subTest(bad), self.assertRaises(ValidationError), self.cr.savepoint():
                self.Device.create({"name": f"badid {bad}", "device_ref": bad, "service_user_id": self.service.id})

    def test_the_controller_id_loses_spaces(self):
        device = self.Device.create({"name": "Spaces", "device_ref": " main ", "service_user_id": self.service.id})
        self.assertEqual(device.device_ref, "main")

    def test_a_change_is_checked_too(self):
        with self.assertRaises(ValidationError):
            self.device.write({"device_ref": "a b"})
        with self.assertRaises(ValidationError):
            self.device.write({"service_user_id": self.user.id})

    def test_only_a_service_user_can_serve_a_controller(self):
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.Device.create({"name": "Wrong", "service_user_id": self.manager.id})

    def test_a_name_is_used_once(self):
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"), self.cr.savepoint():
            self.Device.create({"name": "Bench", "service_user_id": self.service.id})

    def test_a_user_reads_but_does_not_write(self):
        device = self.device.with_user(self.user)
        self.assertEqual(device.device_ref, "main")
        with self.assertRaises(AccessError):
            device.write({"name": "Other"})
        with self.assertRaises(AccessError):
            self.Device.with_user(self.user).create({"name": "New", "service_user_id": self.service.id})
        with self.assertRaises(AccessError):
            device.unlink()

    def test_a_manager_writes(self):
        created = self.Device.with_user(self.manager).create({"name": "Made by the manager", "service_user_id": self.service.id})
        created.write({"note": "ok"})
        created.unlink()

    def test_somebody_without_the_group_reads_nothing(self):
        with self.assertRaises(AccessError):
            self.device.with_user(self.outsider).read(["name"])

    def test_the_groups(self):
        operator = self.env.ref("int_workbench.int_workbench_group_operator")
        manager = self.env.ref("int_workbench.int_workbench_group_manager")
        user = self.env.ref("int_workbench.int_workbench_group_user")
        service = self.env.ref("int_workbench.int_workbench_group_service")
        self.assertIn(user, manager.all_implied_ids)
        self.assertIn(user, operator.all_implied_ids)
        self.assertNotIn(operator, manager.all_implied_ids, "clamping is not part of managing the list of controllers")
        self.assertFalse(service.all_implied_ids & (user | operator | manager), "the service user has nothing else")

    def test_the_menu_is_for_the_users_and_the_configuration_for_the_managers(self):
        menu = self.env.ref("int_workbench.int_workbench_menu_root")
        self.assertIn(self.env.ref("int_workbench.int_workbench_group_user"), menu.group_ids)
        configuration = self.env.ref("int_workbench.int_workbench_menu_configuration")
        self.assertIn(self.env.ref("int_workbench.int_workbench_group_manager"), configuration.group_ids)
