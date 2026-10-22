from psycopg2 import IntegrityError

from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged
from odoo.tests.common import new_test_user
from odoo.tools import mute_logger


@tagged("post_install", "-at_install")
class TestIntLiedanzeigeState(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.operator = new_test_user(
            cls.env,
            login="lied_operator",
            groups="base.group_user,int_liedanzeige.group_liedanzeige_operator",
        )
        cls.outsider = new_test_user(cls.env, login="lied_outsider", groups="base.group_user")
        cls.State = cls.env["int_liedanzeige.state"].with_user(cls.operator)
        cls.state = cls.env.ref("int_liedanzeige.state_main")

    def act(self, action, target=None, value=None, values=None):
        return self.State.apply_action(action, target, value, values)

    def type_digits(self, digits, target=None):
        for digit in digits:
            result = self.act("input", target, digit)
        return result

    def test_hymn_input_shows_on_both_displays(self):
        result = self.type_digits("123")
        self.assertEqual(result["hymn_state"], "123")
        self.assertEqual(result["choir_state"], "123")
        self.assertEqual(result["control_state"], "123")

    def test_choir_input_leaves_hymn_untouched(self):
        self.type_digits("5")
        self.act("reset", "hymn")
        self.type_digits("5")
        result = self.type_digits("88", "choir")
        self.assertEqual(result["hymn_state"], "5")
        self.assertEqual(result["choir_state"], "588")
        self.assertEqual(result["control_state"], "588")

    def test_fifth_digit_is_ignored(self):
        result = self.type_digits("12345")
        self.assertEqual(result["hymn_state"], "1234")
        self.assertEqual(result["choir_state"], "1234")
        self.assertEqual(result["control_state"], "1234")

    def test_backspace_removes_last_digit(self):
        self.type_digits("123")
        result = self.act("backspace", "hymn")
        self.assertEqual(
            (result["hymn_state"], result["choir_state"], result["control_state"]),
            ("12", "12", "12"),
        )

    def test_backspace_on_choir_keeps_hymn(self):
        self.type_digits("12")
        self.type_digits("3", "choir")
        result = self.act("backspace", "choir")
        self.assertEqual(result["hymn_state"], "12")
        self.assertEqual(result["choir_state"], "12")
        self.assertEqual(result["control_state"], "12")

    def test_backspace_on_empty_state_does_nothing(self):
        self.act("reset", "hymn")
        result = self.act("backspace", "hymn")
        self.assertEqual(result["hymn_state"], "")

    def test_reset_hymn_clears_everything(self):
        self.type_digits("123")
        result = self.act("reset", "hymn")
        self.assertEqual((result["hymn_state"], result["choir_state"], result["control_state"]), ("", "", ""))

    def test_reset_choir_clears_choir_and_control_only(self):
        self.type_digits("123")
        result = self.act("reset", "choir")
        self.assertEqual(result["hymn_state"], "123")
        self.assertEqual(result["choir_state"], "")
        self.assertEqual(result["control_state"], "")

    def test_settings_are_stored(self):
        result = self.act("settings", values={"time_size": 90, "font": "georgia", "reset_delay": 2})
        self.assertEqual(result["settings"]["time_size"], 90)
        self.assertEqual(result["settings"]["font"], "georgia")
        self.state.invalidate_recordset()
        self.assertEqual(self.state.reset_delay, 2)

    def test_operator_state_lists_the_setting_ranges(self):
        ranges = self.act("input", "hymn", "1")["ranges"]
        self.assertEqual(ranges["reset_delay"], [1, 10])
        self.assertEqual(ranges["time_size"], [10, 100])
        self.assertEqual(ranges["gap_time_date"], [0, 100])

    def test_unknown_setting_is_rejected(self):
        with self.assertRaises(UserError):
            self.act("settings", values={"hymn_state": "1"})

    def test_invalid_font_is_rejected(self):
        with self.assertRaises(UserError):
            self.act("settings", values={"font": "comic-sans"})

    def test_invalid_setting_numbers_are_rejected(self):
        for bad in (-1, 9, 101, "50", 50.5, True):
            with self.assertRaises(UserError, msg=repr(bad)):
                self.act("settings", values={"time_size": bad})

    def test_input_must_be_one_digit(self):
        for bad in ("a", "12", "", None, 5, "٣"):
            with self.assertRaises(UserError, msg=repr(bad)):
                self.act("input", "hymn", bad)

    def test_unknown_action_and_target_are_rejected(self):
        with self.assertRaises(UserError):
            self.act("explode")
        with self.assertRaises(UserError):
            self.act("input", "organ", "1")

    def test_user_without_operator_group_is_refused(self):
        with self.assertRaises(AccessError):
            self.env["int_liedanzeige.state"].with_user(self.outsider).apply_action("input", "hymn", "1")

    def test_operator_cannot_create_or_delete_state(self):
        with self.assertRaises(AccessError):
            self.State.create({})
        with self.assertRaises(AccessError):
            self.state.with_user(self.operator).unlink()

    def test_setting_bounds_are_accepted(self):
        result = self.act("settings", values={"time_size": 10, "reset_delay": 10, "gap_time_date": 0})
        self.assertEqual(result["settings"]["time_size"], 10)
        self.assertEqual(result["settings"]["reset_delay"], 10)

    def test_database_rejects_setting_out_of_range(self):
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"), self.env.cr.savepoint():
            self.state.write({"reset_delay": 0})
            self.state.flush_recordset()

    def test_database_rejects_non_digit_state(self):
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"), self.env.cr.savepoint():
            self.state.write({"hymn_state": "12a"})
            self.state.flush_recordset()
