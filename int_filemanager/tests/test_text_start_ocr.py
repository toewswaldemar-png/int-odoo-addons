import json
import os
import subprocess
import sys
import tempfile

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.int_filemanager.models.int_filemanager_text import START_OCR

# What the program under test reports about the process it runs in.
PROBE = (
    "import json, os, sys\n"
    "try:\n"
    "    import resource\n"
    "    limit = list(resource.getrlimit(resource.RLIMIT_AS))\n"
    "    nice = os.nice(0)\n"
    "except ImportError:\n"
    "    limit = nice = None\n"
    "print(json.dumps({'env': {k: os.environ.get(k) for k in\n"
    "    ('OMP_THREAD_LIMIT', 'TMPDIR', 'TEMP', 'TMP')},\n"
    "    'limit': limit, 'nice': nice, 'args': sys.argv[1:]}))\n"
)


@tagged("post_install", "-at_install")
class TestStartOcr(TransactionCase):
    """The small script that starts ``ocrmypdf`` with the limits and the environment we want."""

    def _start(self, nice, *command, folder=None):
        with tempfile.TemporaryDirectory() as job:
            done = subprocess.run(
                [sys.executable, "-I", START_OCR, str(nice), folder or job, *command],
                capture_output=True,
                check=False,
                timeout=60,
            )
            return done, job

    def _probe(self, nice=19, *arguments):
        done, job = self._start(nice, sys.executable, "-c", PROBE, *arguments)
        self.assertEqual(done.returncode, 0, done.stderr)
        return json.loads(done.stdout), job

    def test_the_program_gets_one_thread_and_the_job_folder_for_its_temporary_files(self):
        answer, job = self._probe()
        self.assertEqual(answer["env"]["OMP_THREAD_LIMIT"], "1")
        self.assertEqual(answer["env"]["TMPDIR"], job)
        self.assertEqual(answer["env"]["TEMP"], job)
        self.assertEqual(answer["env"]["TMP"], job)

    def test_the_arguments_arrive_as_they_are(self):
        answer, _job = self._probe(19, "--pages", "1-3", "a b", "ü")
        self.assertEqual(answer["args"], ["--pages", "1-3", "a b", "ü"])

    def test_the_exit_code_of_the_program_is_given_back(self):
        done, _job = self._start(19, sys.executable, "-c", "raise SystemExit(6)")
        self.assertEqual(done.returncode, 6)

    def test_a_program_that_is_not_there_gives_127(self):
        done, _job = self._start(19, "int-filemanager-no-such-program")
        self.assertEqual(done.returncode, 127)
        self.assertIn(b"not found", done.stderr)

    def test_too_few_arguments_give_2(self):
        done = subprocess.run([sys.executable, "-I", START_OCR, "19"], capture_output=True, check=False)
        self.assertEqual(done.returncode, 2)

    def test_the_address_space_limit_is_raised_to_the_hard_value(self):
        if os.name == "nt":
            self.skipTest("no resource module on Windows")
        answer, _job = self._probe()
        soft, hard = answer["limit"]
        self.assertEqual(soft, hard)

    def test_the_priority_is_an_absolute_value_whatever_it_was(self):
        if os.name == "nt":
            self.skipTest("no nice on Windows")
        # The test process may have any priority already; the child ends at the value asked for
        # (or at its own, if that is higher: a lower number than ours is not ours to set).
        for wanted in (5, 12, 19):
            with self.subTest(wanted=wanted):
                answer, _job = self._probe(wanted)
                self.assertEqual(answer["nice"], max(wanted, os.nice(0)))
