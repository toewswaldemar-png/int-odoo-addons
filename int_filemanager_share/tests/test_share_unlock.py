import base64
from datetime import timedelta

from odoo import fields
from odoo.tests.common import HttpCase, freeze_time, tagged

from odoo.addons.int_filemanager.tests.test_folder_access import AccessCase

from ..controllers.int_filemanager import key_cookie
from .common import NoSessionMixin
from ..models.int_filemanager_share import ShareBusy, ShareForbidden, ShareGone, ShareNotFound

PASSWORD = "a long password"
IP = "9.9.9.9"


@tagged("post_install", "-at_install")
class TestShareUnlock(NoSessionMixin, AccessCase, HttpCase):
    """The password of a share: the key for it, the tries that are counted, the order of the checks."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._set_up_access()
        cls.Share = cls.env["int.filemanager.share"]
        cls.Attempt = cls.env["int.filemanager.share.attempt"]
        cls.Config = cls.env["ir.config_parameter"]

    def setUp(self):
        super().setUp()
        self.share = self.Share.create({"folder_id": self.shared.id, "password": PASSWORD})

    def _unlock(self, share=None, password=PASSWORD, **kwargs):
        share = share or self.share
        return self.url_open(
            f"/int_filemanager/share/{share.token}/unlock", data={"password": password}, **kwargs
        )

    # --- the route ----------------------------------------------------------------------------

    def test_the_right_password_sets_the_cookie_of_the_share_and_leads_to_it(self):
        response = self._unlock(allow_redirects=False)
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers["Location"], f"/int_filemanager/share/{self.share.token}")
        cookie = response.cookies[key_cookie(self.share.token)]
        self.assertTrue(self.share._key_is_valid(cookie))
        header = response.headers["Set-Cookie"]
        self.assertIn("Path=/", header)
        self.assertIn("HttpOnly", header)
        self.assertIn("SameSite=Lax", header)
        self.assertIn(f"Max-Age={12 * 3600}", header)
        self.assertNotIn("session_id", response.cookies)
        self.assertEqual(response.headers["Referrer-Policy"], "no-referrer")
        self.assertEqual(response.headers["X-Robots-Tag"], "noindex, nofollow")
        self.assertEqual(response.headers["Cache-Control"], "private, no-cache")

    def test_the_browser_that_followed_it_opens_the_share(self):
        self.assertIn("password", self.url_open(f"/int_filemanager/share/{self.share.token}").text)
        response = self._unlock()
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("This link needs a password", response.text)

    def test_a_wrong_password_is_403_with_the_page_again_and_the_try_is_kept(self):
        response = self._unlock(password="another password")
        self.assertEqual(response.status_code, 403)
        self.assertIn("The password is wrong.", response.text)
        self.assertIn("This link needs a password", response.text)
        self.assertNoSession(response)
        self.assertEqual(self.Attempt.search_count([("share_id", "=", self.share.id)]), 1)
        self.assertEqual(self._unlock(password=None).status_code, 403)
        url = f"/int_filemanager/share/{self.share.token}/unlock"
        self.assertEqual(self.url_open(url, data={"x": "y"}).status_code, 403)

    def test_the_answers_to_what_is_not_a_share_that_works(self):
        self.assertEqual(self.url_open("/int_filemanager/share/unknown/unlock", data={"x": "y"}).status_code, 404)
        unknown = "00000000-0000-4000-8000-000000000000"
        self.assertEqual(self.url_open(f"/int_filemanager/share/{unknown}/unlock", data={"x": "y"}).status_code, 404)
        self.share.action_archive()
        self.assertEqual(self._unlock().status_code, 410)
        self.share.action_unarchive()
        self.assertEqual(self._unlock().status_code, 200)
        self.share.expiration_date = fields.Datetime.now() + timedelta(days=1)
        with freeze_time(fields.Datetime.now() + timedelta(days=2)):
            self.assertEqual(self._unlock().status_code, 410)

    def test_a_share_without_a_password_has_nothing_to_unlock(self):
        share = self.Share.create({"folder_id": self.shared.id})
        response = self._unlock(share, allow_redirects=False)
        self.assertEqual(response.status_code, 303)  # on to the share
        self.assertNoSession(response)
        self.assertFalse(self.Attempt.search_count([("share_id", "=", share.id)]))

    def test_a_big_request_is_turned_away_before_it_is_read(self):
        self.assertEqual(self._unlock(password="x" * 70_000).status_code, 413)

    def test_after_the_wrong_passwords_of_an_address_it_is_turned_away_for_ten_minutes(self):
        for __ in range(5):
            self.assertEqual(self._unlock(password="wrong").status_code, 403)
        self.assertEqual(self._unlock().status_code, 429)  # also with the right one
        with freeze_time(fields.Datetime.now() + timedelta(minutes=11)):
            self.assertEqual(self._unlock().status_code, 200)

    def test_a_right_password_clears_the_wrong_ones_of_its_address(self):
        for __ in range(4):
            self._unlock(password="wrong")
        self.assertEqual(self._unlock().status_code, 200)
        self.assertFalse(self.Attempt.search_count([("share_id", "=", self.share.id)]))

    def test_the_brake_on_passwords_has_no_switch(self):
        self.Config.set_param("int_filemanager.share_brake", "0")
        for __ in range(5):
            self._unlock(password="wrong")
        self.assertEqual(self._unlock().status_code, 429)

    def test_the_wrong_passwords_of_all_addresses_together_are_limited_too(self):
        self.Attempt.create([{"share_id": self.share.id, "ip": f"10.0.0.{n}"} for n in range(30)])
        with self.assertRaises(ShareBusy):
            self.share._unlock(PASSWORD, "10.0.1.1")
        self.Config.set_param("int_filemanager.share_password_tries_share", "31")
        self.assertTrue(self.share._unlock(PASSWORD, "10.0.1.1"))

    # --- the key ------------------------------------------------------------------------------

    def test_a_key_is_for_one_share_and_ends_with_its_password_and_its_time(self):
        key = self.share._unlock_key()
        self.assertTrue(self.share._key_is_valid(key))
        other = self.Share.create({"folder_id": self.shared.id, "password": PASSWORD})
        self.assertFalse(other._key_is_valid(key))
        with freeze_time(fields.Datetime.now() + timedelta(hours=11)):
            self.assertTrue(self.share._key_is_valid(key))
        with freeze_time(fields.Datetime.now() + timedelta(hours=13)):
            self.assertFalse(self.share._key_is_valid(key))
        self.Config.set_param("int_filemanager.share_unlock_hours", "1")
        short = self.share._unlock_key()
        with freeze_time(fields.Datetime.now() + timedelta(hours=2)):
            self.assertFalse(self.share._key_is_valid(short))
        self.share.write({"password": "a new long password"})
        self.assertFalse(self.share._key_is_valid(key))

    def test_what_is_not_a_key_is_not_a_key_and_raises_nothing(self):
        key = self.share._unlock_key()
        header = b"\x01" + b"\x00" * 8 + b"\x00" * 32
        broken = (
            None,
            5,
            ["a"],
            {},
            b"bytes",
            "",
            "x",
            "!!!",
            key[:-3],
            key + "A",
            key.upper(),
            "x" * 513,
            base64.urlsafe_b64encode(header + b"not json").decode(),
            base64.urlsafe_b64encode(b"\x02" + b"\x00" * 60).decode(),
            base64.urlsafe_b64encode(b"\xff" * 60).decode(),
        )
        for value in broken:
            with self.subTest(value=value):
                self.assertFalse(self.share._key_is_valid(value))
        self.assertFalse(self.Share.create({"folder_id": self.shared.id})._key_is_valid(key))

    # --- the order of the checks --------------------------------------------------------------

    def test_a_share_that_is_over_says_so_before_it_asks_for_the_password(self):
        self.share.write({"can_download": False})
        self.share.action_archive()
        with self.assertRaises(ShareGone):
            self.Share._resolve(self.share.token, IP, right="download")

    def test_the_password_is_asked_for_before_the_right_is_looked_at(self):
        self.share.write({"can_download": False})
        with self.assertRaisesRegex(ShareForbidden, "password"):
            self.Share._resolve(self.share.token, IP, right="download")
        key = self.share._unlock_key()
        with self.assertRaisesRegex(ShareForbidden, "does not allow"):
            self.Share._resolve(self.share.token, IP, right="download", key=key)
        self.assertEqual(self.Share._resolve(self.share.token, IP, right="view", key=key), self.share)
        resolved = self.Share._resolve(self.share.token, IP, right=("download", "view"), key=key)
        self.assertEqual(resolved, self.share)
        self.assertEqual(self.Share._resolve(self.share.token, IP, key=key), self.share)

    def test_the_calls_before_the_password_do_not_need_a_key(self):
        self.assertEqual(self.Share._resolve(self.share.token, IP, needs_key=False), self.share)
        with self.assertRaises(ShareForbidden):
            self.Share._resolve(self.share.token, IP)

    def test_a_share_without_a_password_needs_no_key_only_the_right(self):
        share = self.Share.create({"folder_id": self.shared.id, "can_download": False})
        with self.assertRaisesRegex(ShareForbidden, "does not allow"):
            self.Share._resolve(share.token, IP, right="download")
        self.assertEqual(self.Share._resolve(share.token, IP, right="view"), share)

    def test_a_token_that_leads_nowhere_is_not_found(self):
        with self.assertRaises(ShareNotFound):
            self.Share._resolve(self.share.token[:-1] + "x", IP)

    def test_a_share_is_found_as_the_superuser(self):
        share = self.Share._resolve(self.share.token, IP, needs_key=False)
        self.assertTrue(share.env.su)
