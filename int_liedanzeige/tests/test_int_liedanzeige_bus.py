import json

from odoo.addons.bus.models.bus import channel_with_db, json_dump
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged
from odoo.tests.common import new_test_user


@tagged("post_install", "-at_install")
class TestIntLiedanzeigeBus(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.operator = new_test_user(
            cls.env,
            login="lied_bus_operator",
            groups="base.group_user,int_liedanzeige.group_liedanzeige_operator",
        )
        cls.State = cls.env["int_liedanzeige.state"].with_user(cls.operator)
        cls.operator_group = cls.env.ref("int_liedanzeige.group_liedanzeige_operator")
        cls.conductor_group = cls.env.ref("int_liedanzeige.group_liedanzeige_conductor")

    def notifications(self):
        """Return the bus messages created since the last call as (channel, type, payload)."""
        self.env.cr.precommit.run()
        Bus = self.env["bus.bus"].sudo()
        rows = Bus.search([])
        result = [
            (
                json.loads(row.channel),
                json.loads(row.message)["type"],
                json.loads(row.message)["payload"],
            )
            for row in rows
        ]
        rows.unlink()
        return result

    def channel(self, name_or_record):
        return json.loads(json_dump(channel_with_db(self.env.cr.dbname, name_or_record)))

    def setUp(self):
        super().setUp()
        self.notifications()

    def by_channel(self, notifications):
        return {json.dumps(channel): payload for channel, _type, payload in notifications}

    def test_hymn_input_reaches_both_displays_and_the_operators(self):
        self.State.apply_action("input", "hymn", "1")
        by_channel = self.by_channel(self.notifications())
        hymn = by_channel[json.dumps(self.channel("int_liedanzeige_hymn"))]
        choir = by_channel[json.dumps(self.channel("int_liedanzeige_choir"))]
        control = by_channel[json.dumps(self.channel(self.operator_group))]
        self.assertEqual((hymn["target"], hymn["number"]), ("hymn", "1"))
        self.assertEqual((choir["target"], choir["number"]), ("choir", "1"))
        self.assertEqual(control["target"], "control")
        self.assertEqual(control["control_state"], "1")

    def test_choir_input_changes_only_the_choir_number(self):
        self.State.apply_action("input", "choir", "8")
        by_channel = self.by_channel(self.notifications())
        self.assertEqual(by_channel[json.dumps(self.channel("int_liedanzeige_hymn"))]["number"], "")
        self.assertEqual(by_channel[json.dumps(self.channel("int_liedanzeige_choir"))]["number"], "8")

    def test_public_channels_never_carry_the_control_number(self):
        self.State.apply_action("input", "hymn", "7")
        for channel, _type, payload in self.notifications():
            if channel in (self.channel(self.operator_group), self.channel(self.conductor_group)):
                continue
            self.assertNotIn("control_state", payload)
            self.assertEqual(set(payload), {"target", "number", "settings"})

    def test_operator_messages_use_a_group_channel_not_a_string(self):
        self.State.apply_action("input", "hymn", "7")
        control_channels = [
            channel for channel, _type, payload in self.notifications() if payload["target"] == "control"
        ]
        self.assertEqual(control_channels, [self.channel(self.operator_group)])
        self.assertIsInstance(control_channels[0], list)
        self.assertEqual(control_channels[0][1], "res.groups")

    def test_settings_reach_every_channel(self):
        self.State.apply_action("settings", values={"time_size": 40})
        notifications = self.notifications()
        self.assertEqual(len(notifications), 4)
        for _channel, _type, payload in notifications:
            if payload["target"] != "conductor":
                self.assertEqual(payload["settings"]["time_size"], 40)

    def test_kiosk_command_goes_to_the_kiosk_channel_with_a_send_time(self):
        self.State.send_kiosk_command("fullscreen")
        notifications = self.notifications()
        self.assertEqual(len(notifications), 1)
        channel, _type, payload = notifications[0]
        self.assertEqual(channel, self.channel("int_liedanzeige_kiosk"))
        self.assertEqual(payload["command"], "fullscreen")
        self.assertGreater(payload["sent_at"], 0)

    def test_unknown_kiosk_command_is_rejected(self):
        with self.assertRaises(UserError):
            self.State.send_kiosk_command("format_disk")

    def test_kiosk_commands_need_the_operator_group(self):
        outsider = new_test_user(self.env, login="lied_bus_outsider", groups="base.group_user")
        with self.assertRaises(AccessError):
            self.env["int_liedanzeige.state"].with_user(outsider).send_kiosk_command("quit")
        with self.assertRaises(AccessError):
            self.env["int_liedanzeige.state"].with_user(outsider).report_kiosk_state(False)

    def test_kiosk_state_is_stored_and_sent_to_the_operators_only(self):
        self.State.report_kiosk_state(False)
        notifications = self.notifications()
        self.assertEqual([channel for channel, _t, _p in notifications], [self.channel(self.operator_group)])
        self.assertIs(notifications[0][2]["kiosk_fullscreen"], False)
        self.assertIs(self.State.get_state()["kiosk_fullscreen"], False)

    def test_kiosk_state_must_be_a_boolean(self):
        for bad in ("yes", 1, None):
            with self.assertRaises(UserError, msg=repr(bad)):
                self.State.report_kiosk_state(bad)

    def conductor_payloads(self):
        return [
            payload
            for channel, _type, payload in self.notifications()
            if channel == self.channel(self.conductor_group)
        ]

    def test_conductor_gets_the_song_text_of_the_choir_number(self):
        self.env["int_liedanzeige.song"].create({"number": "88", "name": "Praise", "text": "Line one\nLine two"})
        self.State.apply_action("input", "choir", "8")
        self.State.apply_action("input", "choir", "8")
        payload = self.conductor_payloads()[-1]
        self.assertEqual(payload["target"], "conductor")
        self.assertEqual(payload["choir_number"], "88")
        self.assertEqual(payload["song_name"], "Praise")
        self.assertEqual(payload["song_text"], "Line one\nLine two")

    def test_conductor_gets_only_the_number_without_a_song(self):
        self.State.apply_action("input", "choir", "9")
        payload = self.conductor_payloads()[-1]
        self.assertEqual((payload["choir_number"], payload["song_name"], payload["song_text"]), ("9", "", ""))

    def test_conductor_gets_the_hymn_number_too(self):
        self.State.apply_action("input", "hymn", "4")
        self.assertEqual(self.conductor_payloads()[-1]["hymn_number"], "4")

    def test_song_text_never_travels_on_a_public_or_string_channel(self):
        self.env["int_liedanzeige.song"].create({"number": "5", "name": "Secret", "text": "Words"})
        self.State.apply_action("input", "hymn", "5")
        for channel, _type, payload in self.notifications():
            if payload["target"] == "conductor":
                self.assertEqual(channel, self.channel(self.conductor_group))
            else:
                self.assertNotIn("Words", json.dumps(payload))
                self.assertNotIn("Secret", json.dumps(payload))

    def test_conductor_channel_is_a_group_record_not_a_string(self):
        channel = self.channel(self.conductor_group)
        self.assertIsInstance(channel, list)
        self.assertEqual(channel[1], "res.groups")
