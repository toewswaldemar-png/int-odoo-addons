import json

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tests.common import new_test_user
from odoo.tools import mute_logger

SIGNALS = [
    {"name": "P0005", "operand": "I0002", "byte": False},
    {"name": "P1000", "operand": "M0534", "byte": True},
    {"name": "P1011", "operand": "M0448", "byte": False},
    {"name": "P0001", "operand": "I0000.0", "byte": True},
]


@tagged("post_install", "-at_install")
class TestIntWorkbenchIntermediate(TransactionCase):
    """The intermediate values: the catalog (variable list of the project), the selection that Odoo keeps and tells the service by a
    version, the readings that the service reports for the rows, and the writing of a value as a request."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.technician = new_test_user(cls.env, login="wb_int_tech", groups="base.group_user,int_workbench.int_workbench_group_technician")
        cls.operator = new_test_user(cls.env, login="wb_int_op", groups="base.group_user,int_workbench.int_workbench_group_operator")
        cls.service = new_test_user(cls.env, login="wb_int_svc", groups="int_workbench.int_workbench_group_service")
        cls.device = cls.env["int.workbench.device"].create({"name": "Bench", "device_ref": "main", "service_user_id": cls.service.id})
        cls.device.capability_ids = cls.env["int.workbench.capability"]._get_or_create(["clamps", "intermediate", "intermediate_write"])
        cls.Row = cls.env["int.workbench.intermediate"]
        cls.Signal = cls.env["int.workbench.signal"]

    def add(self, name="P1011", address="M0448", is_byte=False, fmt="Z", user=None):
        return self.Row.with_user(user or self.technician).create({"device_id": self.device.id, "name": name, "address": address, "is_byte": is_byte, "format": fmt})

    def sync(self, **kwargs):
        return self.env["int.workbench.device"].with_user(self.service).service_sync(device_ref="main", **kwargs)

    def report(self, items, read_at="2026-11-16T10:00:00+01:00"):
        return self.sync(snapshot={"intermediate": {"status": "ok", "items": items, "read_at": read_at, "stale": False}})

    @staticmethod
    def item(name="P1011", address="M0448", fmt="Z", text="2", raw="0002", value=2, answered=True):
        return {"name": name, "address": address, "format": fmt, "text": text, "raw": raw, "value": value, "unit": "", "answered": answered}

    # === the button of the device === #

    def test_the_button_of_the_device_counts_and_opens_its_values(self):
        self.add("P1011")
        self.add("P1000", "M0534", True, "H")
        self.assertEqual(self.device.intermediate_count, 2)
        opened = self.device.action_open_intermediate()
        self.assertEqual((opened["res_model"], opened["domain"]), ("int.workbench.intermediate", [("device_id", "=", self.device.id)]))

    # === the own name === #

    def test_an_own_name_is_only_shown_and_does_not_make_a_new_selection(self):
        row = self.add("P1011")
        version = self.device.intermediate_version
        row.write({"label": "Zulufttemperatur"})
        self.assertEqual(self.device.intermediate_version, version, "the service reads the signal and the address, not the name")
        self.report([self.item("P1011")])
        self.assertEqual((row.label, row.name), ("Zulufttemperatur", "P1011"), "a report of the readings keeps it")

    # === the selection and its version === #

    def test_a_new_row_goes_to_the_end_and_counts_as_a_new_selection(self):
        version = self.device.intermediate_version
        first, second = self.add("P1011"), self.add("P1000", "M0534", True, "H")
        self.assertEqual((first.sequence, second.sequence), (1, 2))
        self.assertEqual(self.device.intermediate_version, version + 2)

    def test_a_change_of_what_is_read_counts_but_a_reading_does_not(self):
        row = self.add()
        version = self.device.intermediate_version
        row.format = "H"
        self.assertEqual(self.device.intermediate_version, version + 1)
        self.report([self.item(fmt="H", text="0002")])
        self.assertEqual((row.text, self.device.intermediate_version), ("0002", version + 1), "the readings of the service are no change of the selection")
        row.unlink()
        self.assertEqual(self.device.intermediate_version, version + 2)

    def test_a_row_is_checked(self):
        for name, address in (("", "M0448"), ("x" * 21, "M0448"), ("P1", "M04 48"), ("P1", "m0448"), ("P1", "M0448=1"), ("P1", "M0448.8"), ("P1", "M123456"), ("P1", "ABCDEFGHI")):
            with self.subTest(name=name, address=address), self.assertRaises(ValidationError), self.cr.savepoint():
                self.add(name, address)

    def test_a_value_is_there_once_per_format(self):
        self.add("P1011", fmt="Z")
        self.add("P1011", fmt="H")
        with self.assertRaises(Exception), mute_logger("odoo.sql_db"), self.cr.savepoint():
            self.add("P1011", fmt="Z")

    def test_only_a_technician_changes_the_selection(self):
        row = self.add()
        with self.assertRaises(AccessError):
            self.add("P1000", "M0534", user=self.operator)
        with self.assertRaises(AccessError):
            row.with_user(self.operator).write({"format": "H"})
        with self.assertRaises(AccessError):
            row.with_user(self.operator).unlink()
        self.assertEqual(self.Row.with_user(self.operator).search([("device_id", "=", self.device.id)]), row, "an operator looks")

    def test_the_service_gets_the_selection_when_its_version_is_not_the_current_one(self):
        self.add("P1011", "M0448", False, "Z")
        self.add("P1000", "M0534", True, "H")
        version = self.device.intermediate_version
        answer = self.sync(intermediate_version=-1)
        self.assertEqual(
            answer["intermediate"],
            {
                "version": version,
                "rows": [
                    {"name": "P1011", "operand": "M0448", "byte": False, "format": "Z"},
                    {"name": "P1000", "operand": "M0534", "byte": True, "format": "H"},
                ],
            },
        )
        self.assertNotIn("intermediate", self.sync(intermediate_version=version), "a service that has this version gets nothing")
        self.assertNotIn("intermediate", self.sync(), "a service that says nothing about it (an older one) gets nothing")
        self.add("P0005", "I0002", False, "P")
        self.assertEqual(len(self.sync(intermediate_version=version)["intermediate"]["rows"]), 3)

    def test_the_rows_are_handed_out_in_the_order_of_the_list(self):
        a, b = self.add("A1", "M0001"), self.add("B1", "M0002")
        a.sequence, b.sequence = 5, 1
        self.assertEqual([r["name"] for r in self.sync(intermediate_version=-1)["intermediate"]["rows"]], ["B1", "A1"])

    def test_an_empty_selection_is_handed_out_too(self):
        self.assertEqual(self.sync(intermediate_version=-1)["intermediate"]["rows"], [])

    # === the readings === #

    def test_a_report_fills_the_readings_of_the_rows_by_name_address_and_format(self):
        row, other = self.add("P1011", "M0448", False, "Z"), self.add("P1011", "M0448", False, "H")
        self.report([self.item(fmt="Z", text="2", raw="0002", value=2), self.item(fmt="H", text="0002", raw="0002", value=0)])
        self.assertEqual((row.text, row.raw, row.value, row.has_value, row.answered), ("2", "0002", 2.0, True, True))
        self.assertEqual((other.text, other.has_value), ("0002", True))

    def test_a_report_creates_and_removes_no_row(self):
        row = self.add()
        self.report([self.item(), self.item("Fremd", "M9999")])
        self.assertEqual(self.device.intermediate_ids, row, "a reading for a row that is not selected is left out")
        self.report([])
        self.assertEqual(self.device.intermediate_ids, row, "a report without the row does not remove it")
        self.assertEqual(row.text, "2", "and leaves its reading")

    def test_an_unreadable_part_leaves_the_readings(self):
        row = self.add()
        self.report([self.item()])
        self.sync(snapshot={"intermediate": {"status": "error", "error": "no answer", "read_at": "2026-11-16T10:00:05+01:00"}})
        self.assertEqual(row.text, "2")

    # === the variable list of the project === #

    def test_the_variable_list_of_the_service_becomes_rows_and_stays_when_it_is_the_same(self):
        self.assertEqual(self.env["int.workbench.device"].with_user(self.service).service_signals_report(device_ref="main", signals=SIGNALS), {"ok": True})
        rows = self.device.signal_ids.sorted("sequence")
        self.assertEqual([(r.sequence, r.name, r.operand, r.is_byte) for r in rows], [(1, "P0005", "I0002", False), (2, "P1000", "M0534", True), (3, "P1011", "M0448", False), (4, "P0001", "I0000.0", True)])
        ids = rows.ids
        self.env["int.workbench.device"].with_user(self.service).service_signals_report(device_ref="main", signals=SIGNALS)
        self.assertEqual(self.device.signal_ids.sorted("sequence").ids, ids, "the same list is not written again")
        self.env["int.workbench.device"].with_user(self.service).service_signals_report(device_ref="main", signals=SIGNALS[:2])
        self.assertEqual(self.device.signal_ids.mapped("name"), ["P0005", "P1000"])

    def test_a_variable_that_is_not_valid_is_left_out(self):
        bad = [{"name": "", "operand": "M0001"}, {"name": "X", "operand": "m 1"}, "text", {"name": "Y", "operand": "M0002", "byte": "yes"}, {"name": "Z" * 30, "operand": "M0003"}]
        self.env["int.workbench.device"].with_user(self.service).service_signals_report(device_ref="main", signals=bad)
        self.assertEqual(sorted(self.device.signal_ids.mapped("name")), ["Y", "Z" * 20])
        self.assertFalse(self.device.signal_ids.filtered(lambda s: s.name == "Y").is_byte, "only a real true makes it a byte")

    def test_only_the_service_of_the_controller_reports_the_list(self):
        other = new_test_user(self.env, login="wb_int_svc2", groups="int_workbench.int_workbench_group_service")
        with self.assertRaises(UserError):
            self.env["int.workbench.device"].with_user(other).service_signals_report(device_ref="main", signals=SIGNALS)
        with self.assertRaises(AccessError):
            self.env["int.workbench.device"].with_user(self.technician).service_signals_report(device_ref="main", signals=SIGNALS)

    def test_choosing_variables_adds_rows_once(self):
        self.env["int.workbench.device"].with_user(self.service).service_signals_report(device_ref="main", signals=SIGNALS)
        signals = self.device.signal_ids.filtered(lambda s: s.name in ("P1011", "P1000"))
        signals.with_user(self.technician).action_choose()
        rows = self.device.intermediate_ids
        self.assertEqual(sorted((r.name, r.address, r.is_byte, r.format) for r in rows), [("P1000", "M0534", True, "Z"), ("P1011", "M0448", False, "Z")])
        self.assertTrue(all(signals.mapped("chosen")))
        again = signals.with_user(self.technician).action_choose()
        self.assertEqual(len(self.device.intermediate_ids), 2, "a variable that is chosen is not added again")
        self.assertIn("0 added", again["params"]["message"])
        with self.assertRaises(UserError):
            self.Signal.browse().with_user(self.technician).action_choose()
        with self.assertRaises(AccessError):
            signals.with_user(self.operator).action_choose()

    def test_sorting_puts_the_rows_in_the_order_of_the_variable_list(self):
        self.env["int.workbench.device"].with_user(self.service).service_signals_report(device_ref="main", signals=SIGNALS)
        own_first = self.add("Mein", "M7777")
        late = self.add("P0001", "I0000.0", True)
        early = self.add("P0005", "I0002")
        self.Row.with_user(self.technician).browse(early.id).action_sort()
        ordered = self.device.intermediate_ids.sorted("sequence")
        self.assertEqual(ordered.mapped("name"), ["P0005", "P0001", "Mein"], "the rows of the list first, in its order; the own rows after them")
        self.assertEqual(ordered.mapped("sequence"), [1, 2, 3])
        self.assertEqual((own_first, late, early), (ordered[2], ordered[1], ordered[0]))

    # === writing a value === #

    def write_wizard(self, row, text, user=None):
        wizard = self.env["int.workbench.intermediate.wizard"].with_user(user or self.technician).create({"intermediate_id": row.id, "text": text})
        return wizard.action_send()

    def test_writing_a_value_makes_a_request_for_the_service(self):
        row = self.add("P1011", "M0448", False, "Z")
        self.write_wizard(row, "2")
        command = self.device.command_ids
        self.assertEqual((command.action, command.state, command.code), ("intermediate_write", "pending", "errors"))
        self.assertEqual(json.loads(command.payload), {"name": "P1011", "operand": "M0448", "byte": False, "format": "Z", "text": "2"})
        self.assertEqual(command.detail, "P1011 = 2")
        handed = self.sync()["commands"]
        self.assertEqual([(c["action"], c["payload"]) for c in handed], [("intermediate_write", {"name": "P1011", "operand": "M0448", "byte": False, "format": "Z", "text": "2"})])

    def test_nothing_typed_is_a_zero_for_the_service_to_make(self):
        self.write_wizard(self.add(), "")
        self.assertEqual(json.loads(self.device.command_ids.payload)["text"], "")

    def test_a_controller_that_cannot_write_refuses_the_request(self):
        row = self.add()
        self.device.capability_ids = self.env["int.workbench.capability"]._get_or_create(["clamps", "intermediate"])
        with self.assertRaises(UserError):
            self.write_wizard(row, "2")
        self.assertFalse(self.device.command_ids)

    def test_only_a_technician_writes_a_value(self):
        row = self.add()
        with self.assertRaises(AccessError):
            self.write_wizard(row, "2", user=self.operator)
        with self.assertRaises(AccessError):
            self.env["int.workbench.command"].with_user(self.operator).create(
                {"device_id": self.device.id, "action": "intermediate_write", "payload": {"name": "P1", "operand": "M0448", "byte": False, "format": "Z", "text": "2"}}
            )

    def test_the_payload_of_a_write_is_checked(self):
        good = {"name": "P1011", "operand": "M0448", "byte": False, "format": "Z", "text": "2"}
        for label, change in (
            ("no name", {"name": ""}),
            ("name too long", {"name": "x" * 21}),
            ("address with a blank", {"operand": "M04 48"}),
            ("address that is a command", {"operand": "M0448=1"}),
            ("lower case address", {"operand": "m0448"}),
            ("byte is no boolean", {"byte": "yes"}),
            ("unknown format", {"format": "X"}),
            ("text with a line end", {"text": "1\rplc off"}),
            ("text too long", {"text": "1" * 41}),
            ("text is no string", {"text": 5}),
        ):
            with self.subTest(label), self.assertRaises(ValidationError), self.cr.savepoint():
                self.env["int.workbench.command"].with_user(self.technician).create({"device_id": self.device.id, "action": "intermediate_write", "payload": {**good, **change}})

    def test_a_payload_carries_only_what_the_service_takes(self):
        self.env["int.workbench.command"].with_user(self.technician).create(
            {"device_id": self.device.id, "action": "intermediate_write", "payload": {"name": "P1011", "operand": "M0448", "byte": False, "format": "H", "text": "ff", "command": "plc off"}}
        )
        self.assertEqual(sorted(json.loads(self.device.command_ids.payload)), ["byte", "format", "name", "operand", "text"])

    def test_the_capability_to_write_is_a_flag_of_the_controller(self):
        self.assertTrue(self.device.cap_intermediate_write)
        self.device.capability_ids = self.env["int.workbench.capability"]._get_or_create(["intermediate"])
        self.assertFalse(self.device.cap_intermediate_write)
        self.assertTrue(self.add().can_write_value is False)
