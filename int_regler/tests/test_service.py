from datetime import timedelta
from unittest import mock

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tests.common import new_test_user

SNAPSHOT = {"status": {"connected": True}, "values": {"entries": []}, "clamps": {"rows": []}, "pages": {"pages": []}}
# what is kept of it: the process values, the clamps and the pages are rows
KEPT = {"status": {"connected": True}}


@tagged("post_install", "-at_install")
class TestIntReglerService(TransactionCase):
    """What the controller service does through int.regler.device.service_sync, and what the page does with the clamp requests."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.operator = new_test_user(cls.env, login="regler_operator", groups="base.group_user,int_regler.group_regler_operator")
        cls.reader = new_test_user(cls.env, login="regler_reader", groups="base.group_user,int_regler.group_regler_user")
        cls.service = new_test_user(cls.env, login="regler_svc", groups="int_regler.group_regler_service")
        cls.other_service = new_test_user(cls.env, login="regler_svc2", groups="int_regler.group_regler_service")
        Device = cls.env["int.regler.device"]
        cls.device = Device.create({"name": "Bench", "device_ref": "main", "service_user_id": cls.service.id})
        cls.other_device = Device.create({"name": "Other", "device_ref": "main", "service_user_id": cls.other_service.id})
        cls.Command = cls.env["int.regler.command"]

    def answer(self, **kwargs):
        """The whole answer of service_sync."""
        kwargs.setdefault("device_ref", "main")
        return self.env["int.regler.device"].with_user(self.service).service_sync(**kwargs)

    def sync(self, **kwargs):
        """The requests that the answer of service_sync hands out."""
        return self.answer(**kwargs)["commands"]

    def sql(self, query, params):
        """A change in the database that the ORM did not make: what it has not written yet is written first, and what it knows is forgotten."""
        self.env.flush_all()
        self.env.cr.execute(query, params)
        self.env.invalidate_all()

    def age(self, command, seconds, column="create_date"):
        """Make a request older, as if the time had passed."""
        self.sql(f"UPDATE int_regler_command SET {column} = %s WHERE id = %s", [fields.Datetime.now() - timedelta(seconds=seconds), command.id])

    def look(self, seconds_ago):
        """Make the last look at the controller older."""
        self.sql("UPDATE int_regler_device SET viewer_at = %s WHERE id = %s", [fields.Datetime.now() - timedelta(seconds=seconds_ago), self.device.id])

    def ask(self, code="0016", action="set", value=1.0, user=None, device=None):
        return self.Command.with_user(user or self.operator).create(
            {"device_id": (device or self.device).id, "code": code, "action": action, "value": value}
        )

    # ---- the service reports ----

    def test_the_snapshot_is_kept_with_its_time(self):
        self.assertEqual(self.sync(snapshot=SNAPSHOT), [])
        self.assertEqual(self.device.snapshot, KEPT)
        self.assertTrue(self.device.snapshot_at)

    def test_a_call_without_a_snapshot_keeps_the_old_one(self):
        self.sync(snapshot=SNAPSHOT)
        at = self.device.snapshot_at
        self.sync()
        self.assertEqual(self.device.snapshot, KEPT)
        self.assertEqual(self.device.snapshot_at, at)

    def test_a_snapshot_must_be_an_object_and_not_huge(self):
        with self.assertRaises(ValidationError):
            self.sync(snapshot=["a"])
        with self.assertRaises(ValidationError):
            self.sync(snapshot={"x": "y" * 2_100_000})

    # ---- who may call it ----

    def test_only_the_service_user_calls_it(self):
        Device = self.env["int.regler.device"]
        for user in (self.operator, self.reader, self.env.ref("base.user_admin")):
            with self.subTest(user.login), self.assertRaises(AccessError):
                Device.with_user(user).service_sync(device_ref="main", snapshot=SNAPSHOT)

    def test_a_service_user_reaches_its_own_controllers_only(self):
        """Both controllers have the id "main"; each service gets its own."""
        self.sync(snapshot=SNAPSHOT)
        self.assertTrue(self.device.snapshot)
        self.assertFalse(self.other_device.snapshot)
        with self.assertRaises(UserError):
            self.sync(device_ref="nobody")

    def test_an_archived_controller_is_not_served(self):
        self.device.active = False
        with self.assertRaises(UserError):
            self.sync(snapshot=SNAPSHOT)

    # ---- the clamp requests ----

    def test_a_request_is_handed_out_once(self):
        command = self.ask()
        self.assertEqual(command.state, "pending")
        taken = self.sync()
        self.assertEqual([c["id"] for c in taken], [command.id])
        self.assertEqual({k: v for k, v in taken[0].items() if k != "expires_in_ms"}, {"id": command.id, "code": "0016", "action": "set", "value": 1.0, "user": "regler_operator"})
        self.assertTrue(13000 <= taken[0]["expires_in_ms"] <= 15000, "the service is told how long the request is valid")
        self.assertEqual(command.state, "sent")
        self.assertTrue(command.sent_at)
        self.assertEqual(self.sync(), [], "the next call has nothing new")

    def test_requests_come_in_the_order_they_were_made(self):
        first = self.ask("0013", "set", 0)
        second = self.ask("0014", "release", 0)
        self.assertEqual([c["id"] for c in self.sync()], [first.id, second.id])

    def test_a_request_for_another_controller_stays_there(self):
        other = self.ask(device=self.other_device)
        self.assertEqual(self.sync(), [])
        self.assertEqual(other.state, "pending")

    def test_the_results_settle_the_requests(self):
        a, b, c = self.ask("0013"), self.ask("0014"), self.ask("0015")
        self.sync()
        self.sync(
            results=[
                {"id": a.id, "state": "done", "message": "confirmed by the controller"},
                {"id": b.id, "state": "failed", "message": "no answer"},
                {"id": c.id, "state": "unconfirmed"},
            ]
        )
        self.assertEqual((a.state, b.state, c.state), ("done", "failed", "unconfirmed"))
        self.assertEqual(a.message, "confirmed by the controller")
        self.assertTrue(a.done_at)

    def test_a_result_settles_only_what_was_handed_out_to_this_controller(self):
        pending = self.ask()
        other = self.ask(device=self.other_device)
        self.sync(results=[{"id": pending.id, "state": "done"}, {"id": other.id, "state": "done"}])
        # the call hands the first one out after it has taken the results, so it ends as "sent", and never as "done"
        self.assertEqual(pending.state, "sent", "a result does not settle what was not handed out yet")
        self.assertEqual(other.state, "pending", "not this controller's")

    def test_a_settled_request_stays_settled(self):
        command = self.ask()
        self.sync()
        self.sync(results=[{"id": command.id, "state": "done"}])
        self.sync(results=[{"id": command.id, "state": "failed", "message": "late and wrong"}])
        self.assertEqual(command.state, "done")

    def test_wrong_results_are_ignored(self):
        command = self.ask()
        self.sync()
        self.sync(results=["x", {}, {"id": "7", "state": "done"}, {"id": command.id, "state": "pending"}, {"id": command.id, "state": "sent"}])
        self.assertEqual(command.state, "sent")
        with self.assertRaises(ValidationError):
            self.sync(results="nonsense")

    def test_an_old_request_expires_instead_of_being_carried_out_late(self):
        command = self.ask()
        self.age(command, 120)
        self.assertEqual(self.sync(), [])
        self.assertEqual(command.state, "expired")
        self.assertTrue(command.message)

    def test_a_request_expires_before_the_page_gives_up(self):
        """The page waits 20 s (regler_client.js); a request must not be carried out after that."""
        command = self.ask()
        self.age(command, 16)
        self.assertEqual(self.sync(), [])
        self.assertEqual(command.state, "expired")
        fresh = self.ask("0014")
        self.age(fresh, 10)
        taken = self.sync()
        self.assertEqual([c["id"] for c in taken], [fresh.id])
        self.assertTrue(0 < taken[0]["expires_in_ms"] <= 5500, "what is left is told: %s" % taken[0]["expires_in_ms"])

    def test_a_request_without_a_result_is_unknown_and_not_expired(self):
        command = self.ask()
        self.sync()
        self.age(command, 20)
        self.sync()
        self.assertEqual(command.state, "unknown")
        self.assertIn("may or may not", command.message)

    def test_a_request_is_handed_out_again_when_no_result_came_back(self):
        command = self.ask()
        self.assertEqual([c["id"] for c in self.sync()], [command.id])
        self.assertEqual(self.sync(), [], "not at once")
        self.age(command, 5, "sent_at")
        again = self.sync()
        self.assertEqual([c["id"] for c in again], [command.id], "the answer may have been lost")
        self.assertEqual(command.state, "sent")
        self.sync(results=[{"id": command.id, "state": "done"}])
        self.age(command, 10, "sent_at")
        self.assertEqual(self.sync(), [], "a request with a result is never handed out again")

    def test_the_states_unknown_and_expired_can_be_reported_by_the_service(self):
        a, b = self.ask("0013"), self.ask("0014")
        self.sync()
        self.sync(results=[{"id": a.id, "state": "unknown", "message": "line lost"}, {"id": b.id, "state": "expired", "message": "too late"}])
        self.assertEqual((a.state, b.state), ("unknown", "expired"))

    # ---- somebody looks: how often the service asks and reports ----

    def test_without_somebody_looking_the_service_is_told_to_keep_quiet(self):
        answer = self.answer()
        self.assertEqual((answer["watched"], answer["poll_ms"], answer["report_ms"]), (False, 2000, 60000))

    def test_while_somebody_looks_it_asks_and_reports_often(self):
        self.device.with_user(self.reader).watch()
        answer = self.answer()
        self.assertEqual((answer["watched"], answer["poll_ms"], answer["report_ms"]), (True, 250, 2000))

    def test_after_the_page_closes_the_service_goes_quiet_again(self):
        self.device.with_user(self.reader).watch()
        self.look(31)
        self.assertFalse(self.answer()["watched"])
        self.look(25)
        self.assertTrue(self.answer()["watched"], "still within the 30 s")

    def test_the_look_is_written_down_at_most_every_few_seconds(self):
        self.device.with_user(self.reader).watch()
        first = self.device.viewer_at
        self.assertTrue(first)
        self.look(2)
        recent = self.device.viewer_at
        self.device.with_user(self.reader).watch()
        self.assertEqual(self.device.viewer_at, recent, "not written again so soon")
        self.look(8)
        old = self.device.viewer_at
        self.device.with_user(self.reader).watch()
        self.assertGreater(self.device.viewer_at, old)

    def test_only_somebody_who_may_read_the_controller_can_say_that_he_looks(self):
        outsider = new_test_user(self.env, login="regler_outsider2", groups="base.group_user")
        with self.assertRaises(AccessError):
            self.device.with_user(outsider).watch()
        self.assertFalse(self.device.viewer_at)

    def test_the_rates_come_from_system_parameters_within_limits(self):
        params = self.env["ir.config_parameter"].sudo()
        params.set_param("int_regler.poll_idle_ms", "5000")
        params.set_param("int_regler.report_idle_ms", "nonsense")
        params.set_param("int_regler.poll_fast_ms", "1")
        answer = self.answer()
        self.assertEqual(answer["poll_ms"], 5000)
        self.assertEqual(answer["report_ms"], 60000, "a value that is not a number is the default")
        self.device.with_user(self.reader).watch()
        self.assertEqual(self.answer()["poll_ms"], 100, "too small a value is the smallest allowed one")

    def test_the_call_of_the_service_is_written_down_not_every_time(self):
        self.assertFalse(self.device.seen_at)
        self.answer()
        first = self.device.seen_at
        self.assertTrue(first)
        self.assertGreaterEqual(self.device.seen_age, 0)
        self.answer()
        self.assertEqual(self.device.seen_at, first, "a second call at once does not write again")

    # ---- the pages hear how a request ended ----

    def test_a_result_is_told_to_the_pages_that_look_at_the_controller(self):
        command = self.ask()
        self.sync()
        with mock.patch.object(type(self.env["bus.bus"]), "_sendone") as sendone:
            self.sync(results=[{"id": command.id, "state": "done", "message": "confirmed by the controller"}])
        self.assertEqual(sendone.call_count, 1)
        target, kind, message = sendone.call_args.args
        self.assertEqual((target, kind), (self.device, "int_regler/command"))
        self.assertEqual(message, {"id": command.id, "state": "done", "message": "confirmed by the controller"})

    def test_an_expired_request_is_told_too(self):
        command = self.ask()
        self.age(command, 30)
        with mock.patch.object(type(self.env["bus.bus"]), "_sendone") as sendone:
            self.sync()
        self.assertEqual(sendone.call_count, 1)
        self.assertEqual(sendone.call_args.args[2]["state"], "expired")

    @staticmethod
    def without_the_channels_of_odoo():
        """The parent method adds the channels of the session (the user, the groups); it needs a websocket request, which a test does not
        have. Without it only what this module adds is left to look at."""
        return mock.patch("odoo.addons.bus.models.ir_websocket.IrWebsocket._build_bus_channel_list", lambda self, channels: list(channels))

    def test_a_page_hears_the_controllers_it_may_read_and_no_other(self):
        channel = f"int.regler.device_{self.device.id}"
        websocket = self.env["ir.websocket"]
        with self.without_the_channels_of_odoo():
            listed = websocket.with_user(self.reader)._build_bus_channel_list([channel])
            self.assertIn(self.device, listed)
            self.assertNotIn(channel, listed, "the name is turned into the record")
            outsider = new_test_user(self.env, login="regler_outsider3", groups="base.group_user")
            listed = websocket.with_user(outsider)._build_bus_channel_list([channel])
        self.assertNotIn(self.device, listed)
        self.assertNotIn(channel, listed, "the name of a controller is never kept as a text channel")

    def test_other_channel_names_are_left_alone(self):
        with self.without_the_channels_of_odoo():
            listed = self.env["ir.websocket"].with_user(self.reader)._build_bus_channel_list(["int.regler.device_x", "something"])
        self.assertIn("something", listed)
        self.assertIn("int.regler.device_x", listed)

    # ---- who may ask ----

    def test_an_operator_asks_and_the_server_sets_the_rest(self):
        command = self.Command.with_user(self.operator).create(
            {
                "device_id": self.device.id,
                "code": "0016",
                "action": "set",
                "value": 1,
                "state": "done",
                "message": "made up",
                "user_id": self.reader.id,
                "done_at": fields.Datetime.now(),
            }
        )
        self.assertEqual(command.state, "pending")
        self.assertFalse(command.message)
        self.assertFalse(command.done_at)
        self.assertEqual(command.user_id, self.operator, "the user is the one who asks")

    def test_a_reader_reads_the_log_but_does_not_ask(self):
        command = self.ask()
        self.assertEqual(command.with_user(self.reader).code, "0016")
        with self.assertRaises(AccessError):
            self.ask(user=self.reader)

    def test_nobody_changes_or_deletes_a_request_by_the_orm(self):
        command = self.ask()
        for user in (self.operator, self.reader):
            with self.subTest(user.login), self.assertRaises(AccessError):
                command.with_user(user).write({"state": "done"})
            with self.subTest(user.login), self.assertRaises(AccessError):
                command.with_user(user).unlink()

    def test_the_service_user_has_no_right_on_the_models_itself(self):
        command = self.ask()
        with self.assertRaises(AccessError):
            command.with_user(self.service).read(["state"])
        with self.assertRaises(AccessError):
            self.device.with_user(self.service).read(["snapshot"])

    def test_a_row_code_is_checked(self):
        for bad in ("", "a b", "../x", "x" * 21):
            with self.subTest(bad), self.assertRaises(ValidationError), self.cr.savepoint():
                self.ask(code=bad)

    def test_an_archived_controller_takes_no_requests(self):
        self.device.active = False
        with self.assertRaises(UserError):
            self.ask()

    def test_the_requests_go_with_the_controller(self):
        command = self.ask()
        self.device.unlink()
        self.assertFalse(command.exists())
