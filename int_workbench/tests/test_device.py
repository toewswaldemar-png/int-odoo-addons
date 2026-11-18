from psycopg2 import IntegrityError

from odoo.exceptions import AccessError, UserError, ValidationError
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

    # === the line and the connection === #

    def test_the_line_is_checked_and_named_in_one_word(self):
        device = self.Device.create({"name": "Line", "service_user_id": self.service.id, "line_kind": "tcp", "line_address": " 192.100.0.50:100 "})
        self.assertEqual((device.line_address, device.line), ("192.100.0.50:100", "tcp:192.100.0.50:100"))
        device.write({"line_kind": "com", "line_address": "com3"})
        self.assertEqual(device.line, "COM3")
        for kind, address in (("com", "LPT1"), ("tcp", "nohost"), ("tcp", "host:99999"), ("tcp", "host:0"), ("com", "")):
            with self.subTest(address), self.assertRaises(ValidationError), self.cr.savepoint():
                device.write({"line_kind": kind, "line_address": address})

    def test_a_device_without_a_line_cannot_be_connected(self):
        with self.assertRaises(ValidationError):
            self.Device.create({"name": "No line", "service_user_id": self.service.id, "line_enabled": True})

    def test_an_operator_connects_and_disconnects_and_takes_the_line_from_another_device(self):
        operator = new_test_user(self.env, login="wb_connect_op", groups="base.group_user,int_workbench.int_workbench_group_operator")
        line = {"line_kind": "tcp", "line_address": "192.100.0.50:100"}
        first = self.Device.create({"name": "First", "service_user_id": self.service.id, **line})
        second = self.Device.create({"name": "Second", "device_ref": "second", "service_user_id": self.service.id, **line})
        first.with_user(operator).action_connect()
        self.assertTrue(first.line_enabled)
        # the line serves one controller: connecting the second lets go of the first
        second.with_user(operator).action_connect()
        self.assertEqual((first.line_enabled, second.line_enabled), (False, True))
        second.with_user(operator).action_disconnect()
        self.assertFalse(second.line_enabled)
        # not an operator: no connection, and nothing to connect without a line
        for user in (self.user, self.outsider):
            with self.subTest(user.login), self.assertRaises(AccessError):
                first.with_user(user).action_connect()
        with self.assertRaises(UserError):
            self.device.with_user(operator).action_connect()

    def test_the_database_keeps_one_connection_per_line(self):
        line = {"line_kind": "com", "line_address": "COM1", "line_enabled": True}
        self.Device.create({"name": "A", "service_user_id": self.service.id, **line})
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"), self.cr.savepoint():
            self.Device.create({"name": "B", "device_ref": "b", "service_user_id": self.service.id, **line})
        # a device that is not connected, or another line, is free
        self.Device.create({"name": "C", "device_ref": "c", "service_user_id": self.service.id, **dict(line, line_enabled=False)})
        self.Device.create({"name": "D", "device_ref": "d", "service_user_id": self.service.id, **dict(line, line_address="COM2")})

    def test_a_technician_sets_the_line_and_the_speed_but_not_the_rest(self):
        technician = new_test_user(self.env, login="wb_line_tech", groups="base.group_user,int_workbench.int_workbench_group_technician")
        self.device.with_user(technician).write({"line_kind": "tcp", "line_address": "10.0.0.5:100", "baud": "38400"})
        self.assertEqual((self.device.line, self.device.baud), ("tcp:10.0.0.5:100", "38400"))
        for vals in ({"name": "Other"}, {"line_enabled": True}, {"service_url": "http://x"}):
            with self.subTest(vals), self.assertRaises(AccessError):
                self.device.with_user(technician).write(vals)
        # an operator does not set the line
        operator = new_test_user(self.env, login="wb_line_op", groups="base.group_user,int_workbench.int_workbench_group_operator")
        with self.assertRaises(AccessError):
            self.device.with_user(operator).write({"baud": "9600"})

    def test_the_service_gets_its_devices_with_line_and_wish(self):
        other_service = new_test_user(self.env, login="regler_service2", groups="int_workbench.int_workbench_group_service")
        self.Device.create({"name": "Not mine", "device_ref": "other", "service_user_id": other_service.id})
        self.device.write({"line_kind": "tcp", "line_address": "192.100.0.50:100", "baud": "38400", "line_enabled": True})
        rows = self.Device.with_user(self.service).service_devices()
        self.assertEqual(rows, [{"device_ref": "main", "name": "Bench", "line": "tcp:192.100.0.50:100", "baud": 38400, "connect": True}])
        for user in (self.user, self.manager):
            with self.subTest(user.login), self.assertRaises(AccessError):
                self.Device.with_user(user).service_devices()

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

    def test_the_buttons_of_the_device_open_its_lists_for_its_rows_only(self):
        other = self.Device.create({"name": "Other", "service_user_id": self.service.id})
        for method in ("action_open_parameters", "action_open_favorites", "action_open_errors"):
            action = getattr(self.device, method)()
            self.assertEqual(action["domain"], [("device_id", "=", self.device.id)], method)
        self.assertNotEqual(other.action_open_parameters()["domain"], self.device.action_open_parameters()["domain"])
        # the star button opens the list of the process values with the filter of the stars
        self.assertEqual(self.device.action_open_favorites()["context"].get("search_default_favorites"), 1)

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
        root, configuration = ref("menu_root"), ref("menu_configuration")
        # the lists of a device (process values, errors, history, log, project) are opened from the device, so the menu has the devices
        # and the configuration; the error memory and the process values are not menus of their own
        for name in ("device_menu", "menu_configuration"):
            self.assertEqual(ref(name).parent_id, root, name)
        for name in ("parameter_config_menu", "combo_template_menu", "error_status_menu", "fs2_file_menu", "user_menu", "log_menu"):
            self.assertEqual(ref(name).parent_id, configuration, name)
        self.assertGreaterEqual(len(configuration.child_id), 2, "a group menu has at least two entries")
        self.assertFalse(self.env["ir.ui.menu"].search([("parent_id", "child_of", root.id), ("parent_id.parent_id.parent_id", "=", root.id)]), "no third level")
