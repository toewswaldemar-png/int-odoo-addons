from unittest.mock import patch

from odoo.tests.common import TransactionCase, tagged

from ..models.int_filemanager_share import ShareBusy, ShareDenied, ShareNotFound
from ..tools.request_brake import RequestBrake
from .test_folder_access import AccessCase


class Clock:
    """A clock that goes only when the test says."""

    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


@tagged("post_install", "-at_install")
class TestRequestBrake(TransactionCase):
    """The counters in memory: events per key in a window that slides."""

    def setUp(self):
        super().setUp()
        self.clock = Clock()
        self.brake = RequestBrake(clock=self.clock)

    def test_it_counts_the_events_of_a_key_within_the_window(self):
        self.assertEqual([self.brake.hit("a", 10) for __ in range(3)], [1, 2, 3])
        self.assertEqual(self.brake.count("a", 10), 3)
        self.assertEqual(self.brake.count("b", 10), 0)

    def test_the_window_slides(self):
        self.brake.hit("a", 10)
        self.clock.now += 6
        self.brake.hit("a", 10)
        self.assertEqual(self.brake.count("a", 10), 2)
        self.clock.now += 5  # the first is 11 seconds old
        self.assertEqual(self.brake.count("a", 10), 1)
        self.clock.now += 6
        self.assertEqual(self.brake.count("a", 10), 0)
        self.assertEqual(self.brake.hit("a", 10), 1)

    def test_counting_does_not_count_and_clearing_forgets(self):
        self.brake.hit("a", 10)
        self.brake.count("a", 10)
        self.assertEqual(self.brake.count("a", 10), 1)
        self.brake.clear("a")
        self.assertEqual(self.brake.count("a", 10), 0)
        self.brake.clear("never seen")

    def test_the_number_of_keys_is_bounded_and_the_unused_go_first(self):
        brake = RequestBrake(max_keys=3, clock=self.clock)
        for key in "abc":
            brake.hit(key, 10)
        brake.hit("a", 10)  # a is in use again: b is the one that has been idle longest
        brake.hit("d", 10)
        self.assertEqual([brake.count(key, 10) for key in "abcd"], [2, 0, 1, 1])

    def test_the_events_of_a_key_are_bounded(self):
        brake = RequestBrake(max_events=5, clock=self.clock)
        counts = [brake.hit("a", 10) for __ in range(20)]
        self.assertEqual(max(counts), 5)


@tagged("post_install", "-at_install")
class TestShareBrake(AccessCase, TransactionCase):
    """The brakes of the guests: made-up addresses, and requests to a share."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._set_up_access()
        cls.Share = cls.env["int.filemanager.share"]
        cls.Config = cls.env["ir.config_parameter"]

    def setUp(self):
        super().setUp()
        self.clock = Clock()
        patcher = patch.object(
            self.env.registry, "_int_filemanager_share_brake", RequestBrake(clock=self.clock), create=True
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        self.share = self.Share.create({"folder_id": self.shared.id})

    def test_a_made_up_token_is_not_found_until_the_address_has_tried_too_often(self):
        self.Config.set_param("int_filemanager.share_invalid_tokens", "3")
        for __ in range(3):
            with self.assertRaises(ShareNotFound):
                self.Share._resolve("x" * 36, "1.1.1.1")
        with self.assertRaises(ShareBusy):
            self.Share._resolve("x" * 36, "1.1.1.1")
        with self.assertRaises(ShareNotFound):  # another address
            self.Share._resolve("x" * 36, "2.2.2.2")

    def test_the_ban_ends_ten_minutes_after_the_last_try(self):
        self.Config.set_param("int_filemanager.share_invalid_tokens", "1")
        for expected in (ShareNotFound, ShareBusy):
            with self.assertRaises(expected):
                self.Share._resolve("x" * 36, "1.1.1.1")
        self.clock.now += 599
        with self.assertRaises(ShareBusy):  # this try counts too
            self.Share._resolve("x" * 36, "1.1.1.1")
        self.clock.now += 601
        with self.assertRaises(ShareNotFound):
            self.Share._resolve("x" * 36, "1.1.1.1")

    def test_a_right_token_goes_through_while_the_address_is_banned(self):
        self.Config.set_param("int_filemanager.share_invalid_tokens", "1")
        for __ in range(3):
            with self.assertRaises(ShareDenied):
                self.Share._resolve("x" * 36, "1.1.1.1")
        self.assertEqual(self.Share._resolve(self.share.token, "1.1.1.1"), self.share)

    def test_every_shape_of_a_wrong_token_counts(self):
        self.Config.set_param("int_filemanager.share_invalid_tokens", "3")
        for token in (None, 5, "short", "x" * 37):
            with self.assertRaises(ShareDenied):
                self.Share._resolve(token, "1.1.1.1")
        self.assertEqual(self.Share._brake().count(("tokens", "1.1.1.1"), 600), 4)

    def test_requests_to_a_share_are_limited_per_address_and_minute(self):
        self.Config.set_param("int_filemanager.share_requests_per_minute", "3")
        for __ in range(3):
            self.Share._resolve(self.share.token, "1.1.1.1")
        with self.assertRaises(ShareBusy):
            self.Share._resolve(self.share.token, "1.1.1.1")
        self.Share._resolve(self.share.token, "2.2.2.2")
        other = self.Share.create({"folder_id": self.shared.id})
        self.Share._resolve(other.token, "1.1.1.1")
        self.clock.now += 61
        self.Share._resolve(self.share.token, "1.1.1.1")

    def test_the_call_that_checks_the_password_is_not_counted_among_the_requests(self):
        self.Config.set_param("int_filemanager.share_requests_per_minute", "1")
        for __ in range(3):
            self.Share._resolve(self.share.token, "1.1.1.1", braked=False)

    def test_the_brakes_on_requests_can_be_switched_off(self):
        self.Config.set_param("int_filemanager.share_brake", "0")
        self.Config.set_param("int_filemanager.share_invalid_tokens", "1")
        self.Config.set_param("int_filemanager.share_requests_per_minute", "1")
        for __ in range(5):
            with self.assertRaises(ShareNotFound):
                self.Share._resolve("x" * 36, "1.1.1.1")
            self.Share._resolve(self.share.token, "1.1.1.1")
