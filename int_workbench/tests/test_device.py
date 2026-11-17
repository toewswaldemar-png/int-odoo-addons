from psycopg2 import IntegrityError

from odoo.exceptions import AccessError, ValidationError
from odoo.tests import Form, TransactionCase, tagged
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

    def test_a_device_has_a_type_a_controller_and_serial_numbers_as_text(self):
        device = self.Device.create(
            {
                "name": "Typed",
                "service_user_id": self.service.id,
                "device_kind": "air_conditioner",
                "device_type": " 3EGM064970R0001 ",
                "serial": " 4711 ",
                "controller_type": "11HA35D",
                "controller_serial": "9885-17",
            }
        )
        self.assertEqual((device.device_kind, device.device_type, device.serial), ("air_conditioner", "3EGM064970R0001", "4711"))
        self.assertEqual((device.controller_type, device.controller_serial), ("11HA35D", "9885-17"))
        plain = self.Device.create({"name": "Plain", "service_user_id": self.service.id})
        self.assertFalse(plain.device_kind or plain.device_type or plain.controller_type or plain.serial)

    def test_a_new_device_gets_the_type_number_of_the_last_device_of_its_kind(self):
        self.device.write({"device_kind": "air_conditioner", "device_type": "3EGM064970R0001"})
        with Form(self.Device) as form:
            form.name = "Next"
            form.service_user_id = self.service
            form.device_kind = "panel"
            self.assertFalse(form.device_type, "no device of this kind yet")
            form.device_kind = "air_conditioner"
            self.assertEqual(form.device_type, "3EGM064970R0001")
            form.device_type = "3EGM000000R0002"
            form.device_kind = "air_conditioner"
            self.assertEqual(form.device_type, "3EGM000000R0002", "what was typed stays")

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

    def test_the_buttons_open_the_lists_of_this_device_and_count_their_rows(self):
        other = self.Device.create({"name": "Other bench", "device_ref": "other", "service_user_id": self.service.id})
        for device, codes in ((self.device, ("0001", "0002", "0003")), (other, ("0001",))):
            for code in codes:
                self.env["int.workbench.parameter"].create({"device_id": device.id, "code": code})
        self.env["int.workbench.error"].create({"device_id": self.device.id, "word": "F1", "bit": 3})
        self.env["int.workbench.command"].create({"device_id": self.device.id, "user_id": self.user.id, "code": "0001", "action": "set", "value": 1})
        device = self.device.with_user(self.user)
        self.assertEqual((device.parameter_count, device.error_count, device.command_count), (3, 1, 1))
        self.assertEqual((other.parameter_count, other.error_count, other.command_count), (1, 0, 0))
        for method, model, view_type in (
            ("action_open_parameters", "int.workbench.parameter", "list"),
            ("action_open_errors", "int.workbench.error", "list"),
            ("action_open_commands", "int.workbench.command", "list"),
        ):
            with self.subTest(method):
                action = getattr(device, method)()
                self.assertEqual((action["type"], action["res_model"]), ("ir.actions.act_window", model))
                self.assertEqual(action["domain"], [("device_id", "=", self.device.id)])
                self.assertTrue(action["name"].startswith("Bench: "))
                self.assertIn(view_type, action["view_mode"])
                rows = self.env[model].with_user(self.user).search(action["domain"])
                self.assertTrue(rows and rows.device_id == self.device, "only the rows of this device")

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

    def test_the_menu_is_grouped_by_what_one_does(self):
        ref = lambda name: self.env.ref(f"int_workbench.int_workbench_{name}")  # noqa: E731
        root, memory, intermediate, configuration = ref("menu_root"), ref("error_memory_menu"), ref("intermediate_menu"), ref("menu_configuration")
        for name in ("parameter_menu", "intermediate_menu", "error_memory_menu", "device_menu", "menu_configuration"):
            self.assertEqual(ref(name).parent_id, root, name)
        for name in ("error_menu", "error_history_menu", "error_status_menu", "fs2_file_menu", "fs2_record_menu"):
            self.assertEqual(ref(name).parent_id, memory, name)
        for name in ("parameter_config_menu", "user_menu", "log_menu"):
            self.assertEqual(ref(name).parent_id, configuration, name)
        for menu in (memory, intermediate):
            self.assertGreaterEqual(len(menu.child_id), 2, "a group menu has at least two entries")
        self.assertFalse(self.env["ir.ui.menu"].search([("parent_id", "child_of", root.id), ("parent_id.parent_id.parent_id", "=", root.id)]), "no third level")
