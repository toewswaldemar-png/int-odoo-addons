from psycopg2 import IntegrityError

from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tests.common import new_test_user
from odoo.tools import mute_logger


@tagged("post_install", "-at_install")
class TestIntWorkbenchType(TransactionCase):
    """Device, device type and controller: the technician chooses the device, the types are one list for both kinds."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Type = cls.env["int.workbench.type"]
        cls.Device = cls.env["int.workbench.device"]
        cls.service = new_test_user(cls.env, login="wb_type_svc", groups="int_workbench.int_workbench_group_service")
        cls.reader = new_test_user(cls.env, login="wb_type_read", groups="base.group_user,int_workbench.int_workbench_group_user")
        cls.manager = new_test_user(cls.env, login="wb_type_mgr", groups="base.group_user,int_workbench.int_workbench_group_manager")
        cls.ac3 = cls.Type.create({"name": "AC3", "ident": "3EGM064970R0001", "kind": "device"})
        cls.controller = cls.Type.create({"name": "11HA35D", "ident": "3EGM009885R0001", "kind": "controller"})
        cls.version = cls.env["int.workbench.project.version"].create({"project": "TRAXX3002/Pro_1", "checksum": "type-test-version"})

    def device(self, name="AC3 bench", **vals):
        return self.Device.create({"name": name, "service_user_id": self.service.id, **vals})

    # === the list of types === #

    def test_the_type_number_is_written_in_capitals_without_spaces(self):
        record = self.Type.create({"name": "Lower", "ident": " 3egm000001r0001 ", "kind": "device"})
        self.assertEqual(record.ident, "3EGM000001R0001")
        record.write({"ident": "3egm000002r0001"})
        self.assertEqual(record.ident, "3EGM000002R0001")

    def test_an_empty_type_number_is_no_number_and_can_be_given_to_many_types(self):
        first = self.Type.create({"name": "No number 1", "ident": "  ", "kind": "device"})
        second = self.Type.create({"name": "No number 2", "kind": "device"})
        self.assertFalse(first.ident)
        self.assertFalse(second.ident)

    def test_a_type_number_and_a_name_are_used_once_for_a_kind(self):
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"), self.cr.savepoint():
            self.Type.create({"name": "Other name", "ident": "3egm064970r0001", "kind": "device"})
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"), self.cr.savepoint():
            self.Type.create({"name": "AC3", "kind": "device"})
        # the same number may be a controller and a device (the kinds are two lists in one)
        self.Type.create({"name": "AC3 controller", "ident": "3EGM064970R0001", "kind": "controller"})

    def test_a_type_is_found_by_its_number(self):
        self.assertEqual(self.Type.name_search("3EGM009885")[0][0], self.controller.id)
        self.assertEqual(self.Type.name_search("AC3")[0][0], self.ac3.id)

    def test_only_a_device_type_has_a_default_project(self):
        self.ac3.write({"project_version_id": self.version.id})
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.controller.write({"project_version_id": self.version.id})

    def test_a_type_that_devices_use_keeps_its_kind(self):
        self.device(device_type_id=self.ac3.id, controller_type_id=self.controller.id)
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.ac3.write({"kind": "controller"})
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.controller.write({"kind": "device"})

    def test_the_rights(self):
        self.assertEqual(self.ac3.with_user(self.reader).ident, "3EGM064970R0001")
        with self.assertRaises(AccessError):
            self.ac3.with_user(self.reader).write({"name": "Other"})
        with self.assertRaises(AccessError):
            self.Type.with_user(self.reader).create({"name": "New"})
        created = self.Type.with_user(self.manager).create({"name": "By the manager"})
        created.write({"note": "ok"})
        created.unlink()

    # === the device === #

    def test_a_device_has_a_type_a_controller_and_serial_numbers(self):
        device = self.device(
            device_type_id=self.ac3.id, serial=" 4711 ", controller_type_id=self.controller.id, controller_serial="9885-17"
        )
        self.assertEqual((device.device_type_id, device.serial), (self.ac3, "4711"))
        self.assertEqual((device.controller_type_id, device.controller_serial), (self.controller, "9885-17"))
        self.assertEqual(self.ac3.device_ids, device)
        self.assertEqual(self.controller.controller_device_ids, device)

    def test_all_fields_are_optional_so_a_device_without_types_still_works(self):
        device = self.device("Only a name")
        self.assertFalse(device.device_type_id | device.controller_type_id)
        self.assertFalse(device.serial or device.controller_serial)

    def test_the_kinds_are_checked(self):
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.device("Wrong 1", device_type_id=self.controller.id)
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.device("Wrong 2", controller_type_id=self.ac3.id)

    def test_replacing_the_controller_changes_the_serial_number_and_nothing_else(self):
        device = self.device(device_type_id=self.ac3.id, controller_type_id=self.controller.id, controller_serial="old")
        device.write({"controller_serial": "new"})
        self.assertEqual((device.device_type_id, device.controller_type_id, device.controller_serial), (self.ac3, self.controller, "new"))

    def test_a_type_that_devices_use_is_not_deleted(self):
        self.device(device_type_id=self.ac3.id)
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"), self.cr.savepoint():
            self.ac3.unlink()

    # === the default project === #

    def test_a_device_gets_the_default_project_of_its_type_once(self):
        self.ac3.write({"project_version_id": self.version.id})
        device = self.device(device_type_id=self.ac3.id)
        self.assertEqual(device.project_version_id, self.version)
        self.assertIn("Assigned to the controller AC3 bench", self.version.message_ids[0].body)

    def test_a_device_with_a_project_keeps_it_and_a_later_default_changes_nothing(self):
        other = self.env["int.workbench.project.version"].create(
            {"project": self.version.project, "checksum": "type-test-other"}
        )
        own = self.device("Own", project_version_id=other.id, device_type_id=self.ac3.id)
        self.assertEqual(own.project_version_id, other, "a project that is assigned is a deviation and stays")
        free = self.device("Free", device_type_id=self.ac3.id)
        self.assertFalse(free.project_version_id, "the type has no default yet")
        self.ac3.write({"project_version_id": self.version.id})
        self.assertFalse(free.project_version_id, "changing the default does not touch the devices")
        free.write({"device_type_id": self.ac3.id})
        self.assertEqual(free.project_version_id, self.version, "a device that is given the type gets it")
