"""Tests for fault.py, the fault injection used by the write-path tests.

Threads stand in for a second process, except in TestCrossProcessBarrier.
"""

import os
import subprocess
import sys
import tempfile
import threading
import time
from unittest.mock import patch

from odoo.tests.common import BaseCase, tagged

from odoo.addons.int_filemanager import fault


@tagged("post_install", "-at_install")
class TestFaultPoint(BaseCase):
    def setUp(self):
        super().setUp()
        fault._test_hooks.clear()
        self.addCleanup(fault._test_hooks.clear)
        self.addCleanup(os.environ.pop, fault.FAULT_FILE_ENV, None)

    def _write_fault_file(self, content):
        fd, path = tempfile.mkstemp(prefix="int_filemanager_fault_test_")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        # hold mode deletes the file itself (its claim), so a plain os.remove would fail
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))
        os.environ[fault.FAULT_FILE_ENV] = path
        return path

    def test_hold_sleeps_once_and_consumes_the_spec(self):
        path = self._write_fault_file("stage_a:hold:0.3")
        started = time.monotonic()
        fault.fault_point("stage_a")
        self.assertGreaterEqual(time.monotonic() - started, 0.3)
        self.assertFalse(os.path.exists(path), "the first arrival must claim the spec")

        started = time.monotonic()
        fault.fault_point("stage_a")  # a retry or the second racer: no hold any more
        self.assertLess(time.monotonic() - started, 0.2)

    def test_hold_only_one_of_two_concurrent_arrivals_waits(self):
        self._write_fault_file("stage_a:hold:0.5")
        elapsed = []

        def arrive():
            started = time.monotonic()
            fault.fault_point("stage_a")
            elapsed.append(time.monotonic() - started)

        threads = [threading.Thread(target=arrive) for _i in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        self.assertEqual(len(elapsed), 2)
        self.assertEqual(
            sorted(e >= 0.5 for e in elapsed),
            [False, True],
            "exactly one racer must hold, the other must pass immediately",
        )

    def test_hold_ends_early_when_the_release_file_appears(self):
        path = self._write_fault_file("stage_a:hold:30")
        release = f"{path}.release.stage_a"
        self.addCleanup(lambda: os.path.exists(release) and os.remove(release))
        timer = threading.Timer(0.2, lambda: open(release, "w").close())
        timer.start()
        self.addCleanup(timer.cancel)

        started = time.monotonic()
        fault.fault_point("stage_a")

        self.assertLess(time.monotonic() - started, 5)

    def test_hold_on_stage_mismatch_keeps_the_spec(self):
        path = self._write_fault_file("stage_a:hold:0.3")
        fault.fault_point("stage_b")
        self.assertTrue(os.path.exists(path))

    def test_noop_without_fault_file(self):
        os.environ.pop(fault.FAULT_FILE_ENV, None)
        fault.fault_point("any_stage")  # must not raise

    def test_raises_on_matching_stage(self):
        self._write_fault_file("stage_a")
        with self.assertRaises(fault.FaultInjected):
            fault.fault_point("stage_a")

    def test_noop_on_stage_mismatch(self):
        self._write_fault_file("stage_a")
        fault.fault_point("stage_b")  # must not raise, different stage armed

    def test_exit_calls_os_exit_with_137(self):
        self._write_fault_file("stage_a:exit")
        with patch("os._exit") as mock_exit:
            fault.fault_point("stage_a")
        mock_exit.assert_called_once_with(137)

    def test_unknown_mode_raises_fault_injected(self):
        self._write_fault_file("stage_a:bogus")
        with self.assertRaises(fault.FaultInjected):
            fault.fault_point("stage_a")

    def test_in_process_hook_runs_without_fault_file(self):
        os.environ.pop(fault.FAULT_FILE_ENV, None)
        calls = []
        fault._test_hooks["stage_x"] = lambda: calls.append(1)
        fault.fault_point("stage_x")
        self.assertEqual(calls, [1])

    def test_missing_fault_file_is_ignored(self):
        os.environ[fault.FAULT_FILE_ENV] = "/does/not/exist/anywhere"
        fault.fault_point("any_stage")  # OSError on open() is swallowed


@tagged("post_install", "-at_install")
class TestWaitAtBarrier(BaseCase):
    def setUp(self):
        super().setUp()
        self.barrier_dir = tempfile.mkdtemp(prefix="int_filemanager_barrier_test_")
        self.addCleanup(self._rmtree, self.barrier_dir)

    @staticmethod
    def _rmtree(path):
        for name in os.listdir(path):
            os.remove(os.path.join(path, name))
        os.rmdir(path)

    def test_single_participant_returns_immediately(self):
        started = time.monotonic()
        fault.wait_at_barrier(self.barrier_dir, 1, timeout=5)
        self.assertLess(time.monotonic() - started, 1)

    def test_two_participants_both_proceed_once_both_registered(self):
        results = []

        def second_participant():
            fault.wait_at_barrier(self.barrier_dir, 2, timeout=5)
            results.append("second")

        t = threading.Thread(target=second_participant)
        t.start()
        fault.wait_at_barrier(self.barrier_dir, 2, timeout=5)
        results.append("first")
        t.join(timeout=5)

        self.assertEqual(set(results), {"first", "second"})
        self.assertGreaterEqual(len(os.listdir(self.barrier_dir)), 2)

    def test_timeout_when_not_enough_participants_arrive(self):
        started = time.monotonic()
        with self.assertRaises(fault.FaultBarrierTimeout):
            fault.wait_at_barrier(self.barrier_dir, 2, timeout=0.2, poll=0.02)
        elapsed = time.monotonic() - started
        self.assertGreaterEqual(elapsed, 0.2)
        self.assertLess(elapsed, 2)

    def test_repeated_registration_from_same_process_gets_distinct_markers(self):
        fault.wait_at_barrier(self.barrier_dir, 1, timeout=5)
        fault.wait_at_barrier(self.barrier_dir, 1, timeout=5)
        self.assertEqual(len(os.listdir(self.barrier_dir)), 2)


@tagged("post_install", "-at_install")
class TestFaultPointBarrierMode(BaseCase):
    def setUp(self):
        super().setUp()
        fd, self.fault_file = tempfile.mkstemp(
            prefix="int_filemanager_fault_barrier_test_"
        )
        os.close(fd)
        self.addCleanup(os.remove, self.fault_file)
        os.environ[fault.FAULT_FILE_ENV] = self.fault_file
        self.addCleanup(os.environ.pop, fault.FAULT_FILE_ENV, None)
        self.barrier_dir = f"{self.fault_file}.barrier.stage_a"
        self.addCleanup(self._rmtree_if_exists, self.barrier_dir)

    @staticmethod
    def _rmtree_if_exists(path):
        if not os.path.isdir(path):
            return
        for name in os.listdir(path):
            os.remove(os.path.join(path, name))
        os.rmdir(path)

    def _set_stage(self, spec):
        with open(self.fault_file, "w", encoding="utf-8") as f:
            f.write(spec)

    def test_two_callers_both_pass_the_barrier(self):
        self._set_stage("stage_a:barrier:2")
        results = []

        def caller():
            fault.fault_point("stage_a")
            results.append("done")

        t = threading.Thread(target=caller)
        t.start()
        fault.fault_point("stage_a")
        results.append("done")
        t.join(timeout=5)

        self.assertEqual(results, ["done", "done"])
        self.assertTrue(os.path.isdir(self.barrier_dir))


@tagged("post_install", "-at_install")
class TestCrossProcessBarrier(BaseCase):
    """wait_at_barrier() works across real processes, not only threads."""

    def test_two_real_processes_meet_at_the_barrier(self):
        barrier_dir = tempfile.mkdtemp(prefix="int_filemanager_barrier_proc_test_")
        self.addCleanup(TestWaitAtBarrier._rmtree, barrier_dir)

        child_script = (
            "import importlib.util\n"
            "spec = importlib.util.spec_from_file_location(\n"
            f"    'fault', {fault.__file__!r}\n"
            ")\n"
            "m = importlib.util.module_from_spec(spec)\n"
            "spec.loader.exec_module(m)\n"
            f"m.wait_at_barrier({barrier_dir!r}, 2, timeout=10)\n"
            "print('child done')\n"
        )
        proc = subprocess.Popen(
            [sys.executable, "-c", child_script], stdout=subprocess.PIPE, text=True
        )
        self.addCleanup(proc.wait)

        started = time.monotonic()
        fault.wait_at_barrier(barrier_dir, 2, timeout=10)
        out, _ = proc.communicate(timeout=10)

        self.assertIn("child done", out)
        self.assertLess(time.monotonic() - started, 10)
