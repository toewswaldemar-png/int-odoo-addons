import threading
import time
from unittest.mock import patch

from odoo.tests.common import TransactionCase, tagged
from odoo.tools import config


@tagged("post_install", "-at_install")
class TestCronBudget(TransactionCase):
    """The time that a run of a scheduled action of the filemanager may take."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Cron = cls.env["int.filemanager.cron"]

    def _limits(self, workers, real, cron):
        return patch.dict(
            config._runtime_options,
            {"workers": workers, "limit_time_real": real, "limit_time_real_cron": cron},
        )

    def test_the_limit_of_a_threaded_server(self):
        for real, cron, expected in ((120, -1, (120, True)), (120, 0, (120, True)), (120, 50, (50, True)), (0, 0, (300, False))):
            with self.subTest(real=real, cron=cron), self._limits(0, real, cron):
                self.assertEqual(self.Cron._limit_seconds(), expected)

    def test_the_limit_of_a_prefork_server(self):
        for real, cron, expected in ((120, -1, (120, True)), (120, 0, (300, False)), (120, 50, (50, True)), (0, -1, (300, False))):
            with self.subTest(real=real, cron=cron), self._limits(2, real, cron):
                self.assertEqual(self.Cron._limit_seconds(), expected)

    def test_the_deadline_of_a_threaded_server_counts_from_the_start_of_the_thread(self):
        thread = threading.current_thread()
        with self._limits(0, 120, -1), patch.object(thread, "start_time", time.time() - 30, create=True):
            left = self.Cron._pass_deadline() - time.monotonic()
        self.assertAlmostEqual(left, 120 - 15 - 30, delta=2)

    def test_the_deadline_of_a_prefork_server_counts_from_the_job_and_the_sleep(self):
        started = time.monotonic() - 12
        Cron = self.Cron.with_context(cron_end_time=started + 10)
        with self._limits(2, 120, 200):
            left = Cron._pass_deadline() - time.monotonic()
        # 200 s limit, 70 s sleep of the worker before the job, 15 s reserve, 12 s used.
        self.assertAlmostEqual(left, 200 - 70 - 15 - 12, delta=2)

    def test_every_call_of_one_run_gets_the_same_deadline(self):
        started = time.monotonic() - 5
        Cron = self.Cron.with_context(cron_end_time=started + 10)
        with self._limits(2, 200, 200):
            first = Cron._pass_deadline()
            time.sleep(0.2)
            self.assertAlmostEqual(Cron._pass_deadline(), first, delta=0.01)

    def test_the_reserve_is_a_setting(self):
        self.env["ir.config_parameter"].set_param("int_filemanager.time_reserve", "40")
        Cron = self.Cron.with_context(cron_end_time=time.monotonic() + 10)
        with self._limits(2, 200, 200):
            left = Cron._pass_deadline() - time.monotonic()
        self.assertAlmostEqual(left, 200 - 70 - 40, delta=2)

    def test_the_time_of_a_run_per_kind_of_server(self):
        def limits(workers, real, cron):
            return patch.dict(
                config._runtime_options,
                {"workers": workers, "limit_time_real": real, "limit_time_real_cron": cron},
            )

        with limits(0, 120, -1):
            self.assertEqual(self.Cron._budget(), ("threaded", 120, 105, True))
        with limits(2, 120, -1):
            # 70 seconds are gone before the job starts in a worker.
            self.assertEqual(self.Cron._budget(), ("prefork", 120, 35, True))
        with limits(2, 120, 0):
            self.assertEqual(self.Cron._budget(), ("prefork", 300, 285, False))
        with limits(2, 60, -1):
            self.assertEqual(self.Cron._budget()[2], 0)
