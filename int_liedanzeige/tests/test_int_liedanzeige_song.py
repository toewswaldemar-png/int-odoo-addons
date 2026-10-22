from psycopg2 import IntegrityError

from odoo.exceptions import AccessError, UserError
from odoo.addons.int_liedanzeige.models.int_liedanzeige_song import _number_taken_message
from odoo.tests import TransactionCase, tagged
from odoo.tests.common import new_test_user
from odoo.tools import mute_logger


@tagged("post_install", "-at_install")
class TestIntLiedanzeigeSong(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.operator = new_test_user(
            cls.env,
            login="lied_song_operator",
            groups="base.group_user,int_liedanzeige.group_liedanzeige_operator",
        )
        cls.conductor = new_test_user(
            cls.env,
            login="lied_song_conductor",
            groups="base.group_user,int_liedanzeige.group_liedanzeige_conductor",
        )
        cls.outsider = new_test_user(cls.env, login="lied_song_outsider", groups="base.group_user")
        cls.song = cls.env["int_liedanzeige.song"].create({"number": "123", "name": "Title", "text": "Words"})

    def test_the_message_of_a_clash_names_the_number(self):
        class Diagnostics:
            message_detail = "Key (number)=(123) already exists."

        message = _number_taken_message(self.env, Diagnostics())
        self.assertIn("123", message)
        Diagnostics.message_detail = None
        self.assertNotIn("123", _number_taken_message(self.env, Diagnostics()))

    def test_the_database_keeps_numbers_unique(self):
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"), self.cr.savepoint():
            self.cr.execute("INSERT INTO int_liedanzeige_song (number, number_value) VALUES ('123', 123)")

    def test_only_numbers_of_one_to_four_digits_are_accepted(self):
        for bad in ("", "12a", "12345", " 7", "²", "-1"):
            with self.assertRaises(UserError, msg=repr(bad)), self.cr.savepoint():
                self.env["int_liedanzeige.song"].create({"number": bad})
        self.env["int_liedanzeige.song"].create({"number": "0007"})

    def test_songs_sort_by_number_not_by_text(self):
        Song = self.env["int_liedanzeige.song"]
        for number in ("9", "10", "100"):
            Song.create({"number": number})
        numbers = Song.search([("number", "in", ["9", "10", "100"])]).mapped("number")
        self.assertEqual(numbers, ["9", "10", "100"])

    def test_display_name_shows_number_and_title(self):
        self.assertEqual(self.song.display_name, "123 Title")
        self.assertEqual(self.env["int_liedanzeige.song"].create({"number": "5"}).display_name, "5")

    def test_operator_maintains_songs(self):
        Song = self.env["int_liedanzeige.song"].with_user(self.operator)
        song = Song.create({"number": "321", "text": "More"})
        song.write({"name": "Named"})
        self.assertEqual(Song.browse(song.id).name, "Named")
        song.unlink()
        self.assertFalse(song.exists())

    def test_conductor_reads_but_does_not_change_songs(self):
        Song = self.env["int_liedanzeige.song"].with_user(self.conductor)
        self.assertEqual(Song.browse(self.song.id).text, "Words")
        with self.assertRaises(AccessError):
            Song.create({"number": "555"})
        with self.assertRaises(AccessError):
            Song.browse(self.song.id).write({"text": "Changed"})
        with self.assertRaises(AccessError):
            Song.browse(self.song.id).unlink()

    def test_others_do_not_see_songs(self):
        with self.assertRaises(AccessError):
            self.env["int_liedanzeige.song"].with_user(self.outsider).search([])

    def test_conductor_state_is_for_conductors_only(self):
        State = self.env["int_liedanzeige.state"]
        self.assertIn("choir_number", State.with_user(self.conductor).get_conductor_state())
        for user in (self.operator, self.outsider):
            with self.assertRaises(AccessError):
                State.with_user(user).get_conductor_state()

    def test_conductor_state_carries_the_song_of_the_choir_number(self):
        state = self.env.ref("int_liedanzeige.state_main")
        state.choir_state = "123"
        State = self.env["int_liedanzeige.state"].with_user(self.conductor)
        values = State.get_conductor_state()
        self.assertEqual((values["song_name"], values["song_text"]), ("Title", "Words"))
        state.choir_state = "999"
        values = State.get_conductor_state()
        self.assertEqual((values["choir_number"], values["song_name"], values["song_text"]), ("999", "", ""))
