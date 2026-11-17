from datetime import timedelta
from unittest import mock

import psycopg2.errors

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tests.common import new_test_user


def can_part(modules, read_at="2026-11-14T10:00:00+01:00"):
    return {"status": "ok", "count": len(modules), "configured_count": 3, "time": read_at, "stale": False, "modules": modules}


def can_item(number, type_name="11IO12", serial="A0001", sw="1.04", hw="2.0", can_status="05"):
    return {"number": number, "type_raw": "x", "type": 18, "type_hex": 18, "type_name": type_name, "serial": serial, "serial_hex": "00", "mc_sw": "3.10", "sw": sw, "hw": hw, "can_status": can_status}


@tagged("post_install", "-at_install")
class TestIntWorkbenchControl(TransactionCase):
    """The requests a technician makes (clock, CAN bus, restart, console) and what the report says about the CAN modules and the intermediate values."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.technician = new_test_user(cls.env, login="wb_ctl_tech", groups="base.group_user,int_workbench.int_workbench_group_technician")
        cls.operator = new_test_user(cls.env, login="wb_ctl_op", groups="base.group_user,int_workbench.int_workbench_group_operator")
        cls.reader = new_test_user(cls.env, login="wb_ctl_reader", groups="base.group_user,int_workbench.int_workbench_group_user")
        cls.service = new_test_user(cls.env, login="wb_ctl_svc", groups="int_workbench.int_workbench_group_service")
        cls.device = cls.env["int.workbench.device"].create({"name": "Bench", "device_ref": "main", "service_user_id": cls.service.id})
        cls.device.capability_ids = cls.env["int.workbench.capability"]._get_or_create(["clamps", "clock", "console", "can_control"])
        cls.Command = cls.env["int.workbench.command"]

    def ask(self, action, payload=None, user=None, device=None):
        return self.Command.with_user(user or self.technician).create({"device_id": (device or self.device).id, "action": action, "payload": payload})

    def report(self, snapshot=None, results=None):
        return self.env["int.workbench.device"].with_user(self.service).service_sync(device_ref="main", snapshot=snapshot, results=results)

    # === who may ask for what === #

    def test_a_technician_asks_for_the_clock_the_can_bus_a_restart_and_a_console_command(self):
        clock = self.ask("clock_set", {"local_time": "2026-11-14T09:30:00"})
        can = self.ask("can_control", {"action": "stop"})
        reset = self.ask("reset")
        console = self.ask("console", {"command": "  id   all "})
        self.assertEqual([c.code for c in (clock, can, reset, console)], ["errors"] * 4, "they are about the controller, not about a row")
        self.assertEqual(clock.detail, "2026-11-14T09:30:00")
        self.assertEqual(can.detail, "stop")
        self.assertEqual(console._payload_dict(), {"command": "id   all"})
        self.assertEqual(reset.detail, "")

    def test_an_operator_and_a_reader_may_not(self):
        for user in (self.operator, self.reader):
            for action, payload in (("clock_set", {"local_time": "2026-11-14T09:30:00"}), ("can_control", {"action": "stop"}), ("reset", None), ("console", {"command": "id all"})):
                with self.assertRaises(AccessError, msg=f"{user.login} {action}"):
                    self.ask(action, payload, user=user)

    def test_an_operator_still_clamps_and_clears(self):
        with self.assertRaisesRegex(UserError, "cannot do this"):
            self.ask("clear_errors", user=self.operator)  # needs the capability of the error memory
        self.device.capability_ids |= self.env["int.workbench.capability"]._get_or_create(["error_memory"])
        self.assertEqual(self.ask("clear_errors", user=self.operator).action, "clear_errors")

    def test_a_controller_that_cannot_do_it_refuses_the_request(self):
        bare = self.env["int.workbench.device"].create({"name": "Bare", "device_ref": "bare", "service_user_id": self.service.id})
        bare.capability_ids = self.env["int.workbench.capability"]._get_or_create(["clamps"])
        with self.assertRaisesRegex(UserError, "cannot do this"):
            self.ask("reset", device=bare)
        with self.assertRaisesRegex(UserError, "cannot do this"):
            self.ask("clock_set", {"local_time": "2026-11-14T09:30:00"}, device=bare)

    # === what a request may carry === #

    def test_the_payload_is_checked_for_the_action(self):
        for action, payload in (
            ("clock_set", {"local_time": "14.11.2026 09:30"}),
            ("clock_set", {"local_time": "2026-13-14T09:30:00"}),
            ("clock_set", {}),
            ("can_control", {"action": "format"}),
            ("console", {"command": ""}),
            ("console", {"command": "id all\rsr"}),
            ("console", {"command": "x" * 121}),
            ("console", ["id all"]),
        ):
            with self.assertRaises(ValidationError, msg=f"{action} {payload}"):
                self.ask(action, payload)

    def test_only_what_the_action_needs_goes_to_the_service(self):
        command = self.ask("can_control", {"action": "start", "extra": "rm -rf"})
        self.assertEqual(command._payload_dict(), {"action": "start"})

    # === the way to the service === #

    def test_the_service_gets_the_payload_and_gives_back_the_answer(self):
        command = self.ask("console", {"command": "id all"})
        taken = self.report()["commands"]
        self.assertEqual([(c["id"], c["action"], c["payload"], c["user"]) for c in taken], [(command.id, "console", {"command": "id all"}, "wb_ctl_tech")])
        self.report(results=[{"id": command.id, "state": "done", "message": "carried out", "output": "Kompaktregler 1 1 H A 3 X"}])
        self.assertEqual((command.state, command.output), ("done", "Kompaktregler 1 1 H A 3 X"))

    def test_a_slow_request_is_valid_for_longer_than_a_clamp(self):
        reset = self.ask("reset")
        self.env.flush_all()
        self.env.cr.execute("UPDATE int_workbench_command SET create_date = %s WHERE id = %s", [fields.Datetime.now() - timedelta(seconds=60), reset.id])
        self.env.invalidate_all()
        taken = self.report()["commands"]
        self.assertEqual([c["id"] for c in taken], [reset.id], "a restart is not given up after the 15 seconds of a clamp")
        self.assertTrue(0 < taken[0]["expires_in_ms"] <= 120_000)

    def test_a_restart_that_nobody_carried_out_expires_in_the_end(self):
        reset = self.ask("reset")
        self.env.flush_all()
        self.env.cr.execute("UPDATE int_workbench_command SET create_date = %s WHERE id = %s", [fields.Datetime.now() - timedelta(minutes=10), reset.id])
        self.env.invalidate_all()
        self.assertEqual(self.report()["commands"], [])
        self.assertEqual(reset.state, "expired")

    # === the clock and the CAN modules in the report === #

    def test_the_clock_shows_on_the_controller(self):
        self.report(snapshot={"clock": {"available": True, "write_enabled": True, "connected": True, "local_time": "2026-11-14T09:30:00", "read_at": "2026-11-14T09:30:01Z"}, "can": can_part([can_item(1)])})
        self.assertEqual((self.device.clock_local_time, self.device.clock_write_enabled), ("2026-11-14T09:30:00", True))

    def test_the_can_modules_of_a_report_become_rows(self):
        self.report(snapshot={"can": can_part([can_item(1), can_item(2, "11WR15", "B0002")])})
        rows = self.device.can_module_ids.sorted("number")
        self.assertEqual([(r.number, r.type_name, r.serial, r.sw, r.can_status) for r in rows], [(1, "11IO12", "A0001", "1.04", "05"), (2, "11WR15", "B0002", "1.04", "05")])
        self.assertEqual(self.device.snapshot["can"]["count"], 2)
        self.assertNotIn("modules", self.device.snapshot["can"], "the modules are rows, not a part of the Json")
        self.report(snapshot={"can": can_part([can_item(1, sw="1.05")], read_at="2026-11-14T10:05:00+01:00")})
        self.assertEqual(self.device.can_module_ids.mapped("sw"), ["1.05"])
        self.assertEqual(self.device.can_module_ids.mapped("number"), [1], "a module the controller no longer has is removed")

    def test_the_can_modules_stay_when_the_service_could_not_read_them(self):
        self.report(snapshot={"can": can_part([can_item(1)])})
        self.report(snapshot={"can": {"status": "error", "error": "no answer", "time": "2026-11-14T10:10:00+01:00"}})
        self.assertEqual(self.device.can_module_ids.mapped("number"), [1])

    # === the intermediate values === #

    def test_the_intermediate_values_of_a_report_fill_the_rows_of_the_selection(self):
        items = [
            {"name": "Zuluft", "address": "I0004", "kind": "P", "format": "P", "raw": "0123", "text": "21,5", "value": 21.5, "unit": "°C", "answered": True},
            {"name": "Bits", "address": "I0000", "kind": "B", "format": "B", "raw": "", "text": "", "value": None, "unit": "", "answered": False, "error": "no answer"},
        ]
        Row = self.env["int.workbench.intermediate"]
        # the rows are the selection of Odoo; the service reports the readings of them
        Row.create([{"device_id": self.device.id, "name": "Zuluft", "address": "I0004", "format": "P"}, {"device_id": self.device.id, "name": "Bits", "address": "I0000", "is_byte": True, "format": "B"}])
        self.report(snapshot={"intermediate": {"status": "ok", "items": items, "read_at": "2026-11-14T10:00:00+01:00", "stale": False}})
        rows = self.device.intermediate_ids.sorted("sequence")
        self.assertEqual(
            [(r.sequence, r.name, r.has_value, r.value, r.unit or "", r.answered, r.error or "") for r in rows],
            [(1, "Zuluft", True, 21.5, "°C", True, ""), (2, "Bits", False, 0.0, "", False, "no answer")],
        )
        self.assertEqual(self.device.snapshot["intermediate"], {"status": "ok", "read_at": "2026-11-14T10:00:00+01:00", "stale": False})
        self.report(snapshot={"intermediate": {"status": "ok", "items": items[:1], "read_at": "2026-11-14T10:00:05+01:00", "stale": False}})
        self.assertEqual(self.device.intermediate_ids.mapped("name"), ["Zuluft", "Bits"], "a report does not remove a row of the selection")

    def test_a_reader_looks_at_the_lists_but_changes_nothing(self):
        self.report(snapshot={"can": can_part([can_item(1)])})
        modules = self.env["int.workbench.can.module"].with_user(self.reader)
        self.assertEqual(modules.search([]).mapped("number"), [1])
        with self.assertRaises(AccessError):
            modules.search([]).write({"sw": "x"})

    # === what the real controller sends === #

    def test_a_serial_number_that_starts_with_a_nul_byte_is_stored(self):
        self.report(snapshot={"can": can_part([can_item(1, serial="\x00\x01ab"), can_item(2, type_name="Typ\x00B")])})
        rows = self.device.can_module_ids.sorted("number")
        self.assertEqual((rows[0].serial, rows[1].type_name), ("ab", "TypB"), "control characters are dropped, the rest stays")

    def test_a_part_that_cannot_be_stored_does_not_take_the_report_down(self):
        command = self.ask("reset")
        with mock.patch.object(type(self.env["int.workbench.can.module"]), "_sync", side_effect=ValueError("A string literal cannot contain NUL")):
            answer = self.report(snapshot={"status": {"connected": True}, "can": can_part([can_item(1)])})
        self.assertEqual(self.device.snapshot["status"], {"connected": True}, "the rest of the report is kept")
        self.assertEqual([c["id"] for c in answer["commands"]], [command.id], "and the request still goes out")

    def test_a_clash_with_another_transaction_is_left_to_the_server_to_run_again(self):
        # Another transaction wrote the same rows (the page that tells "somebody looks"): the server runs the whole call again,
        # which it cannot do if the part is only logged and the report goes on in an aborted transaction.
        for error in (psycopg2.errors.SerializationFailure, psycopg2.errors.DeadlockDetected, psycopg2.errors.LockNotAvailable):
            with self.subTest(error.__name__), mock.patch.object(type(self.env["int.workbench.can.module"]), "_sync", side_effect=error("clash")):
                with self.assertRaises(error):
                    self.report(snapshot={"status": {"connected": True}, "can": can_part([can_item(1)])})
