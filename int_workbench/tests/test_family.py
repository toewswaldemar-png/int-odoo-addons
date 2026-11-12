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
    """What the service tells when it signs on: the families become records, the controller gets its family and its capabilities."""

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

    def test_the_example_payload_creates_the_family_and_sets_the_controller(self):
        answer = self.register()
        family = self.Family.search([("name", "=", "micserv")])
        self.assertEqual(family.label, "Micserv")
        self.assertEqual(family.transports, "com, tcp")
        self.assertEqual(set(family.capability_ids.mapped("code")), set(PAYLOAD["families"][0]["capabilities"]))
        self.assertEqual(self.device.family_id, family)
        self.assertEqual(set(self.device.capability_ids.mapped("code")), set(PAYLOAD["capabilities"]))
        self.assertEqual(answer["family"], "micserv")
        self.assertEqual(set(answer["capabilities"]), set(PAYLOAD["capabilities"]))
        self.assertEqual(answer["families"], ["micserv"])

    def test_the_controller_has_less_than_its_family(self):
        self.register()
        self.assertIn("line_switch", self.device.family_id.capability_ids.mapped("code"))
        self.assertNotIn("line_switch", self.device.capability_ids.mapped("code"))
        self.assertFalse(self.device.cap_line_switch)
        self.assertTrue(self.device.cap_clamps)
        self.assertTrue(self.device.cap_project_files)

    def test_the_same_call_again_changes_nothing(self):
        self.register()
        family = self.Family.search([("name", "=", "micserv")])
        count = self.env["int.workbench.capability"].search_count([])
        written = family.write_date
        self.register()
        family.invalidate_recordset(["write_date"])
        self.assertEqual(self.Family.search_count([("name", "=", "micserv")]), 1)
        self.assertEqual(self.env["int.workbench.capability"].search_count([]), count)
        self.assertEqual(family.write_date, written)

    def test_a_family_is_brought_up_to_date_and_a_new_one_needs_no_change_of_the_module(self):
        self.register()
        new_family = {"name": "mona", "label": "MonA", "transports": ["com"], "capabilities": ["clamps", "operating_mode"]}
        micserv = {**PAYLOAD["families"][0], "label": "Micserv 2", "capabilities": ["clamps"]}
        self.register(family="mona", capabilities=["clamps", "operating_mode"], families=[micserv, new_family])
        self.assertEqual(self.Family.search([("name", "=", "micserv")]).label, "Micserv 2")
        self.assertEqual(self.Family.search([("name", "=", "micserv")]).capability_ids.mapped("code"), ["clamps"])
        mona = self.Family.search([("name", "=", "mona")])
        self.assertEqual(self.device.family_id, mona)
        # a capability that the module has no record for is kept, with its code as name
        capability = self.env["int.workbench.capability"].search([("code", "=", "operating_mode")])
        self.assertEqual(capability.name, "Operating mode")
        self.assertEqual(set(self.device.capability_ids.mapped("code")), {"clamps", "operating_mode"})

    def test_a_controller_without_a_family_can_still_clamp(self):
        """A service that has not signed on (an older one) keeps what the module did before families existed."""
        self.assertFalse(self.device.family_id)
        self.assertTrue(self.device.cap_clamps)
        self.assertFalse(self.device.cap_project_files)

    def test_a_family_without_the_capability_hides_it(self):
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
        self.assertFalse(self.Family.search([("name", "=", "micserv")]))

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
        self.assertFalse(self.device.family_id)

    def test_families_and_capabilities_are_read_only_for_everybody_but_the_service(self):
        self.register()
        family = self.Family.with_user(self.reader).search([("name", "=", "micserv")])
        self.assertEqual(family.label, "Micserv")
        with self.assertRaises(AccessError):
            family.write({"label": "x"})
        with self.assertRaises(AccessError):
            self.env["int.workbench.capability"].with_user(self.reader).create({"code": "x", "name": "x"})
        with self.assertRaises(AccessError):
            self.Family.with_user(self.reader).create({"name": "x", "label": "x"})
