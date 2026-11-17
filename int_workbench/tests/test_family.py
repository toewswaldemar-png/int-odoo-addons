from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tests.common import new_test_user

# What the service sends: the example of the registration (go/workbench/odoosync/register.go).
PAYLOAD = {
    "device_ref": "main",
    "family": "micserv",
    "capabilities": ["clamps", "clock", "console", "can_control", "flash", "error_memory", "error_files", "intermediate", "project_files"],
    "families": [
        {
            "name": "micserv",
            "label": "Micserv",
            "transports": ["com", "tcp"],
            "capabilities": ["clamps", "clock", "console", "can_control", "flash", "line_switch", "error_memory", "error_files", "intermediate", "project_files"],
        }
    ],
}


@tagged("post_install", "-at_install")
class TestIntWorkbenchFamily(TransactionCase):
    """What the service tells when it signs on: the controller gets the name of its original and its capabilities."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.service = new_test_user(cls.env, login="wb_family_svc", groups="int_workbench.int_workbench_group_service")
        cls.other_service = new_test_user(cls.env, login="wb_family_svc2", groups="int_workbench.int_workbench_group_service")
        cls.reader = new_test_user(cls.env, login="wb_family_reader", groups="base.group_user,int_workbench.int_workbench_group_user")
        cls.device = cls.env["int.workbench.device"].create({"name": "Bench", "device_ref": "main", "service_user_id": cls.service.id})
        cls.Family = cls.env["int.workbench.family"]

    def register(self, **kwargs):
        payload = {**PAYLOAD, **kwargs}
        return self.Family.with_user(self.service).service_register(**payload)

    def test_the_example_payload_sets_the_original_and_the_capabilities_of_the_controller(self):
        answer = self.register()
        self.assertEqual(self.device.family, "Micserv")
        self.assertEqual(set(self.device.capability_ids.mapped("code")), set(PAYLOAD["capabilities"]))
        self.assertEqual(answer["family"], "micserv")
        self.assertEqual(set(answer["capabilities"]), set(PAYLOAD["capabilities"]))
        self.assertEqual(answer["families"], ["micserv"])

    def test_the_controller_has_only_what_it_reports(self):
        self.register()
        self.assertNotIn("line_switch", self.device.capability_ids.mapped("code"))
        self.assertFalse(self.device.cap_line_switch)
        self.assertTrue(self.device.cap_clamps)
        self.assertTrue(self.device.cap_project_files)

    def test_the_same_call_again_changes_nothing(self):
        self.register()
        count = self.env["int.workbench.capability"].search_count([])
        self.device.flush_recordset()
        written = self.device.write_date
        self.register()
        self.device.invalidate_recordset(["write_date"])
        self.assertEqual(self.env["int.workbench.capability"].search_count([]), count)
        self.assertEqual(self.device.write_date, written)

    def test_a_new_original_needs_no_change_of_the_module(self):
        self.register()
        new_family = {"name": "mona", "label": "MonA", "transports": ["com"], "capabilities": ["clamps", "operating_mode"]}
        self.register(family="mona", capabilities=["clamps", "operating_mode"], families=[PAYLOAD["families"][0], new_family])
        self.assertEqual(self.device.family, "MonA")
        # a capability that the module has no record for is kept, with its code as name
        capability = self.env["int.workbench.capability"].search([("code", "=", "operating_mode")])
        self.assertEqual(capability.name, "Operating mode")
        self.assertEqual(set(self.device.capability_ids.mapped("code")), {"clamps", "operating_mode"})

    def test_a_controller_that_has_not_signed_on_can_still_clamp(self):
        """A service that has not signed on (an older one) keeps what the module did before the original was told: clamping."""
        self.assertFalse(self.device.family)
        self.assertTrue(self.device.cap_clamps)
        self.assertFalse(self.device.cap_project_files)

    def test_a_controller_without_the_capability_hides_it(self):
        self.register(capabilities=["clock"])
        self.assertFalse(self.device.cap_clamps)
        operator = new_test_user(self.env, login="wb_family_operator", groups="base.group_user,int_workbench.int_workbench_group_operator")
        with self.assertRaises(UserError):
            self.env["int.workbench.command"].with_user(operator).create({"device_id": self.device.id, "code": "0016", "action": "release"})

    def test_only_the_service_user_of_the_controller_calls_it(self):
        with self.assertRaises(AccessError):
            self.Family.with_user(self.reader).service_register(**PAYLOAD)
        with self.assertRaises(UserError):
            self.Family.with_user(self.other_service).service_register(**PAYLOAD)
        self.assertFalse(self.device.family)

    def test_what_is_not_shaped_as_expected_is_refused_and_nothing_is_kept(self):
        for bad in (
            {"families": "micserv"},
            {"families": [{"label": "No name"}]},
            {"families": [{"name": "bad name!", "label": "x"}]},
            {"families": [{"name": "x", "transports": "com"}]},
            {"capabilities": "clamps"},
            {"capabilities": ["Not A Code"]},
            {"family": "unknown_family"},
        ):
            with self.subTest(bad=bad), self.assertRaises(ValidationError):
                self.register(**bad)
        self.assertFalse(self.device.family)

    def test_capabilities_are_read_only_for_everybody_but_the_service(self):
        self.register()
        with self.assertRaises(AccessError):
            self.env["int.workbench.capability"].with_user(self.reader).create({"code": "x", "name": "x"})
