import json
from datetime import timedelta

from odoo import fields
from odoo.tests import TransactionCase, tagged
from odoo.tests.common import new_test_user


def can_part(count=1, read_at="2026-11-14T10:00:00+01:00"):
    modules = [{"number": n, "type": 18, "type_name": "11IO12", "serial": f"A{n}", "mc_sw": "3.10", "sw": "1.0", "hw": "2.0", "can_status": "05"} for n in range(1, count + 1)]
    return {"status": "ok", "count": count, "configured_count": 3, "time": read_at, "stale": False, "modules": modules}


@tagged("post_install", "-at_install")
class TestIntWorkbenchFeedback(TransactionCase):
    """What the user is told: how a request ended, which lists have new data, the line to the controller, new errors."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.technician = new_test_user(cls.env, login="wb_fb_tech", groups="base.group_user,int_workbench.int_workbench_group_technician")
        cls.other = new_test_user(cls.env, login="wb_fb_other", groups="base.group_user,int_workbench.int_workbench_group_technician")
        cls.service = new_test_user(cls.env, login="wb_fb_svc", groups="int_workbench.int_workbench_group_service")
        cls.device = cls.env["int.workbench.device"].create({"name": "Bench", "device_ref": "main", "service_user_id": cls.service.id})
        cls.device.capability_ids = cls.env["int.workbench.capability"]._get_or_create(["clamps", "clock", "console", "can_control"])

    def setUp(self):
        super().setUp()
        self.env.cr.precommit.run()
        self.env["bus.bus"].sudo().search([]).unlink()

    def messages(self):
        """The messages that were put on the bus since the last call: [(channel, type, payload)]."""
        self.env.cr.precommit.run()
        rows = self.env["bus.bus"].sudo().search([], order="id")
        out = [(json.loads(row.channel), json.loads(row.message)["type"], json.loads(row.message)["payload"]) for row in rows]
        rows.unlink()
        return out

    def of_type(self, kind):
        return [(channel, payload) for channel, type_, payload in self.messages() if type_ == kind]

    def report(self, snapshot=None, results=None):
        return self.env["int.workbench.device"].with_user(self.service).service_sync(device_ref="main", snapshot=snapshot, results=results)

    def ask(self, action, payload=None, user=None):
        return self.env["int.workbench.command"].with_user(user or self.technician).create({"device_id": self.device.id, "action": action, "payload": payload})

    def look(self):
        self.device.sudo().viewer_at = fields.Datetime.now()

    def settle(self, command, state="done", message="carried out", output=None):
        self.report()
        self.report(results=[{"id": command.id, "state": state, "message": message, **({"output": output} if output else {})}])

    # === the end of a request, told to the user who asked === #

    def test_the_user_who_asked_is_told_that_it_worked(self):
        command = self.ask("reset")
        self.settle(command)
        notices = [(channel, payload) for channel, payload in self.of_type("simple_notification")]
        self.assertEqual(len(notices), 1)
        channel, payload = notices[0]
        self.assertEqual(channel[-2:], ["res.partner", self.technician.partner_id.id], "it goes to the user who asked, nobody else")
        self.assertEqual((payload["type"], payload["title"]), ("success", "Restart the controller"))
        self.assertIn("Bench", payload["message"])
        self.assertNotIn("sticky", payload, "a success goes away by itself")

    def test_a_problem_stays_until_it_is_read_and_carries_the_text_of_the_service(self):
        for state, kind in (("failed", "danger"), ("unconfirmed", "warning"), ("unknown", "warning")):
            command = self.ask("clock_set", {"local_time": "2026-11-14T09:30:00"})
            self.settle(command, state=state, message="403: the clock is not released")
            _, payload = self.of_type("simple_notification")[-1]
            self.assertEqual((payload["type"], payload["sticky"], payload["title"]), (kind, True, "Set the clock"), state)
            self.assertIn("the clock is not released", payload["message"])

    def test_a_request_that_expired_is_told_too(self):
        command = self.ask("reset")
        self.env.flush_all()
        self.env.cr.execute("UPDATE int_workbench_command SET create_date = %s WHERE id = %s", [fields.Datetime.now() - timedelta(minutes=30), command.id])
        self.env.invalidate_all()
        self.report()
        notices = self.of_type("simple_notification")
        self.assertEqual([payload["type"] for _, payload in notices], ["warning"])

    def test_the_console_says_where_the_answer_is(self):
        command = self.ask("console", {"command": "id all"})
        self.settle(command, output="Kompaktregler")
        _, payload = self.of_type("simple_notification")[-1]
        self.assertEqual(payload["title"], "Console command")
        self.assertIn("answer of the controller", payload["message"])
        self.assertEqual(command.output, "Kompaktregler")

    def test_a_clamp_is_not_told_the_switch_shows_it(self):
        self.env["int.workbench.parameter"].sudo().create({"device_id": self.device.id, "code": "0016", "name": "x", "status": "ok", "can_clamp": True})
        command = self.env["int.workbench.command"].with_user(self.technician).create({"device_id": self.device.id, "code": "0016", "action": "set", "value": 1.0})
        self.settle(command)
        self.assertEqual(self.of_type("simple_notification"), [])

    def test_the_page_of_the_request_is_told_to_load_the_answer(self):
        command = self.ask("console", {"command": "sr"})
        self.settle(command)
        requests = [(channel, payload) for channel, payload in self.of_type("int_workbench/request")]
        self.assertEqual([(c[-1], p) for c, p in requests], [(self.technician.partner_id.id, {"id": command.id, "state": "done"})])

    def test_another_user_is_not_told(self):
        command = self.ask("reset", user=self.technician)
        self.settle(command)
        partners = {channel[-1] for channel, _ in self.of_type("simple_notification")}
        self.assertNotIn(self.other.partner_id.id, partners)

    # === the line to the controller === #

    def test_the_connection_of_the_controller_is_shown(self):
        self.assertEqual(self.device.connection_state, "unknown")
        self.report({"status": {"connected": True}})
        self.assertEqual(self.device.connection_state, "connected")
        self.report({"status": {"connected": False}})
        self.assertEqual(self.device.connection_state, "disconnected")
        self.env.flush_all()
        self.env.cr.execute("UPDATE int_workbench_device SET seen_at = %s WHERE id = %s", [fields.Datetime.now() - timedelta(minutes=5), self.device.id])
        self.env.invalidate_all()
        self.assertEqual(self.device.connection_state, "silent", "the service has not called for a while: what is shown may be old")

    def test_those_who_look_are_told_when_the_line_is_lost_and_when_it_is_back(self):
        self.report({"status": {"connected": True}})
        self.look()
        self.messages()
        self.report({"status": {"connected": False}})
        self.assertEqual([p for _, p in self.of_type("int_workbench/connection")], [{"device": "Bench", "state": "disconnected"}])
        self.report({"status": {"connected": False}})
        self.assertEqual(self.of_type("int_workbench/connection"), [], "nothing new, nothing said")
        self.report({"status": {"connected": True}})
        self.assertEqual([p["state"] for _, p in self.of_type("int_workbench/connection")], ["connected"])

    def test_nobody_is_told_while_nobody_looks(self):
        self.report({"status": {"connected": True}})
        self.messages()
        self.report({"status": {"connected": False}, "can": can_part(1), "errors": {"active": [{"word": "F1", "bit": 1, "text": "Fan"}]}})
        self.assertEqual([t for _, t, _ in self.messages() if t.startswith("int_workbench/")], [])

    # === new data and new errors, told to those who look === #

    def test_the_lists_are_told_which_models_have_new_rows(self):
        self.report({"status": {"connected": True}})
        self.look()
        self.messages()
        self.report({"can": can_part(2)})
        changed = [p for _, p in self.of_type("int_workbench/changed")]
        self.assertEqual(changed, [{"models": ["int.workbench.can.module"]}])
        self.report({"can": can_part(2)})  # the same reading again
        self.assertEqual(self.of_type("int_workbench/changed"), [])
        self.report({"can": can_part(3, read_at="2026-11-14T10:05:00+01:00")})
        self.assertEqual([p["models"] for _, p in self.of_type("int_workbench/changed")], [["int.workbench.can.module"]])

    def test_a_new_error_is_told_but_not_at_the_first_report_and_not_twice(self):
        error = {"word": "F1", "bit": 3, "text": "CAN Stop"}
        self.look()
        self.report({"errors": {"active": [error]}})
        self.assertEqual(self.of_type("int_workbench/error_new"), [], "the first report: everything is new, nothing is told")
        self.report({"errors": {"active": [error, {"word": "F2", "bit": 1, "text": "Fan defect"}]}})
        self.assertEqual([p for _, p in self.of_type("int_workbench/error_new")], [{"device": "Bench", "errors": ["Fan defect"], "more": 0}])
        self.report({"errors": {"active": [error, {"word": "F2", "bit": 1, "text": "Fan defect"}]}})
        self.assertEqual(self.of_type("int_workbench/error_new"), [])

    def test_many_new_errors_are_named_up_to_a_limit(self):
        self.look()
        self.report({"errors": {"active": []}})
        self.report({"errors": {"active": [{"word": "F1", "bit": n, "text": f"E{n}"} for n in range(8)]}})
        (_, payload), = self.of_type("int_workbench/error_new")
        self.assertEqual((len(payload["errors"]), payload["more"]), (5, 3))
