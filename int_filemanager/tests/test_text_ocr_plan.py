import os
import shutil
import subprocess
import sys
import tempfile
import unittest

from odoo.tests.common import BaseCase, tagged

from odoo.addons.int_filemanager.models.int_filemanager_text import START_OCR
from odoo.addons.int_filemanager.tools import ocr_plan as plan

from . import text_files


@tagged("post_install", "-at_install")
class TestOcrPlanner(BaseCase):
    """How long the next section is, and what a section that ran out of time teaches."""

    def test_the_pages_follow_the_time_left_the_time_per_page_and_the_safety(self):
        # (100 - 6) * 0.7 / 2 = 32.9
        self.assertEqual(plan.section_pages(100, 2, 500), 32)

    def test_a_file_with_nothing_measured_starts_short(self):
        self.assertEqual(plan.section_pages(1000, 0, 500), plan.FIRST_SECTION_PAGES)

    def test_a_measured_file_may_take_big_sections_but_not_more_than_100(self):
        self.assertEqual(plan.section_pages(100000, 1, 500), plan.MAX_SECTION_PAGES)

    def test_a_section_never_has_more_pages_than_are_left(self):
        self.assertEqual(plan.section_pages(1000, 1, 3), 3)
        self.assertEqual(plan.section_pages(1000, 0, 4), 4)

    def test_no_time_for_one_page_gives_zero(self):
        self.assertEqual(plan.section_pages(8, 10, 50), 0)
        self.assertEqual(plan.section_pages(3, 1, 50), 0)  # less than the fixed time
        self.assertEqual(plan.section_pages(-5, 1, 50), 0)

    def test_an_unmeasured_file_is_judged_by_the_guessed_time_per_page(self):
        self.assertEqual(plan.section_pages(6 + 4, 0, 50), 0)  # 4 * 0.7 / 5 < 1
        self.assertEqual(plan.section_pages(6 + 8, 0, 50), 1)  # 8 * 0.7 / 5 = 1.12

    def test_a_page_is_tried_all_the_same_when_the_time_is_fair_for_one_page(self):
        # The time per page grew so big that not even one page fits by the rule ...
        self.assertEqual(plan.section_pages(100, 500, 50), 1)
        # ... but a run too short for a fair try does not start one.
        self.assertEqual(plan.section_pages(plan.MIN_COUNTING_SECONDS - 1, 500, 50), 0)
        self.assertEqual(plan.section_pages(plan.MIN_COUNTING_SECONDS, 500, 50), 1)
        self.assertEqual(plan.section_pages(30, 500, 50, fair=20), 1)
        self.assertEqual(plan.section_pages(100, 500, 0), 0)

    def test_a_short_run_still_tries_a_slow_page_and_in_the_end_gives_it_up(self):
        # A run of 25 seconds (the fair time is 80 % of it): the page must be tried, and a page
        # that does not end in that time counts, or it would wait for ever.
        fair = 25 * 0.8
        self.assertEqual(plan.section_pages(25, 20, 50, fair), 1)
        self.assertTrue(plan.after_timeout(1, 20, 25, fair).counts)

    def test_the_fair_time_is_a_part_of_what_a_run_gives_the_program(self):
        self.assertEqual(plan.fair_seconds(1000), plan.MIN_COUNTING_SECONDS)
        self.assertEqual(plan.fair_seconds(25), 20)
        self.assertEqual(plan.fair_seconds(-5), 0)
        # Whatever the length of a run, the first page of it is tried: the fair time never
        # asks for more than the run has (a run of 35 seconds had a window of 25, asked 28).
        for window in (5, 25, 49, 100, 1000):
            with self.subTest(window=window):
                self.assertEqual(plan.section_pages(window, 500, 1, plan.fair_seconds(window)), 1)

    def test_a_short_run_lowers_the_time_a_page_needs_to_count(self):
        self.assertTrue(plan.after_timeout(1, 3.0, 20, fair=20).counts)
        self.assertFalse(plan.after_timeout(1, 3.0, 19, fair=20).counts)

    def test_the_time_per_page_is_the_section_without_the_fixed_time(self):
        self.assertEqual(plan.measured_seconds_per_page(10, 36), 3.0)

    def test_a_very_quick_section_does_not_read_as_not_measured(self):
        self.assertEqual(plan.measured_seconds_per_page(10, 2), plan.MIN_SECONDS_PER_PAGE)

    def test_the_average_starts_with_the_first_measurement_and_then_smooths(self):
        self.assertEqual(plan.smoothed(0, 4.0), 4.0)
        self.assertEqual(plan.smoothed(4.0, 8.0), 6.0)

    def test_a_timeout_halves_the_section_and_doubles_the_time_per_page(self):
        result = plan.after_timeout(10, 3.0, 40)
        self.assertEqual((result.pages, result.seconds_per_page, result.counts), (5, 6.0, False))

    def test_a_section_of_one_page_stays_at_one(self):
        self.assertEqual(plan.after_timeout(1, 3.0, 40).pages, 1)
        self.assertEqual(plan.after_timeout(3, 3.0, 40).pages, 1)

    def test_a_timeout_with_nothing_measured_doubles_the_guess(self):
        result = plan.after_timeout(10, 0, 40)
        self.assertEqual(result.seconds_per_page, 2 * plan.DEFAULT_SECONDS_PER_PAGE)

    def test_only_one_page_with_a_fair_time_counts_against_the_file(self):
        self.assertTrue(plan.after_timeout(1, 3.0, 60).counts)
        self.assertFalse(plan.after_timeout(1, 3.0, 59).counts)
        self.assertFalse(plan.after_timeout(2, 3.0, 600).counts)

    def test_the_resolution_of_an_image_comes_from_its_width_as_an_a4_page(self):
        self.assertEqual(plan.estimate_dpi(2480), 300)
        self.assertEqual(plan.estimate_dpi(1240), 150)
        self.assertEqual(plan.estimate_dpi(1), 1)


@tagged("post_install", "-at_install")
class TestOcrOutcome(BaseCase):
    """What is done after the program ended, from its exit code and its error text."""

    def _classify(self, code, text="", **kwargs):
        return plan.classify(code, text, **kwargs)

    def test_success_is_done(self):
        self.assertEqual(self._classify(0).action, plan.DONE)

    def test_success_without_a_result_is_tried_once_more_with_force(self):
        first = self._classify(0, empty_result=True)
        self.assertEqual((first.action, first.add), (plan.AGAIN, plan.FORCE))
        second = self._classify(0, empty_result=True, tried={plan.FORCE})
        self.assertEqual((second.action, second.reason), (plan.FAIL, "empty_result"))

    def test_a_broken_file_is_given_up_at_once(self):
        outcome = self._classify(2, "InputFileError: not a PDF")
        self.assertEqual((outcome.action, outcome.reason), (plan.FAIL, "bad_file"))

    def test_an_image_without_resolution_is_tried_once_with_an_estimate(self):
        text = "Input file is an image, but has no resolution (DPI) in its metadata."
        first = self._classify(2, text)
        self.assertEqual((first.action, first.add), (plan.AGAIN, plan.DPI))
        self.assertEqual(self._classify(2, text, tried={plan.DPI}).action, plan.FAIL)

    def test_a_refused_option_is_our_fault_and_not_a_resolution_problem(self):
        # argparse of the program: code 2, and the usage text names ``--image-dpi``.
        text = "usage: ocrmypdf [-h] [--image-dpi DPI] input output\nocrmypdf: error: unrecognized arguments"
        outcome = self._classify(2, text)
        self.assertEqual((outcome.action, outcome.reason, outcome.add), (plan.BLOCK, "bad_setup", None))

    def test_the_name_of_the_option_alone_is_no_resolution_problem(self):
        self.assertEqual(self._classify(2, "mentions --image-dpi somewhere").action, plan.FAIL)

    def test_a_page_that_has_text_already_is_tried_once_with_force(self):
        first = self._classify(6)
        self.assertEqual((first.action, first.add), (plan.AGAIN, plan.FORCE))
        self.assertEqual(self._classify(6, tried={plan.FORCE}).action, plan.FAIL)

    def test_a_file_with_a_password_is_given_up(self):
        outcome = self._classify(8)
        self.assertEqual((outcome.action, outcome.reason), (plan.FAIL, "encrypted"))

    def test_a_missing_program_or_a_wrong_setup_stops_the_recognition(self):
        self.assertEqual(self._classify(3).action, plan.BLOCK)
        self.assertEqual(self._classify(9).action, plan.BLOCK)
        self.assertEqual(self._classify(1).action, plan.BLOCK)

    def test_a_full_disk_pauses_whatever_the_code(self):
        for code in (0, 5, 7, 15):
            outcome = self._classify(code, "OSError: No space left on device")
            self.assertEqual(outcome.action, plan.PAUSE)

    def test_an_image_too_large_is_tried_once_with_a_smaller_copy(self):
        text = "Image too large: (41437, 5315)"
        first = self._classify(7, text)
        self.assertEqual((first.action, first.add, first.attempts), (plan.AGAIN, plan.DOWNSAMPLE, 0))
        self.assertEqual(self._classify(7, text, tried={plan.DOWNSAMPLE}).reason, "image_too_large")

    def test_other_faults_are_tried_again_until_the_tries_are_used_up(self):
        for code in (7, 4, 5, 10, 15, -9):
            with self.subTest(code=code):
                first = self._classify(code, attempts=0, max_attempts=3)
                self.assertEqual((first.action, first.attempts), (plan.AGAIN, 1))
                last = self._classify(code, attempts=2, max_attempts=3)
                self.assertEqual((last.action, last.reason, last.attempts), (plan.FAIL, "gave_up", 3))

    def test_one_try_only_gives_up_at_the_first_fault(self):
        self.assertEqual(self._classify(7, max_attempts=1).action, plan.FAIL)

    def test_no_error_text_is_no_problem(self):
        self.assertEqual(plan.classify(2, None).reason, "bad_file")


@tagged("post_install", "-at_install")
class TestOcrCommand(BaseCase):
    """The command line of a section."""

    def _command(self, **kwargs):
        values = {"languages": "deu+eng", "jobs": 2, "output_type": "pdf"}
        return plan.section_command("ocrmypdf", "in.pdf", "out.pdf", [3, 4, 5, 6, 7], **{**values, **kwargs})

    def test_the_command_for_a_plain_section(self):
        self.assertEqual(
            self._command(),
            [
                "ocrmypdf", "--skip-text", "--pages", "3-7", "-l", "deu+eng", "-j", "2",
                "--output-type", "pdf", "--quiet", "--deskew", "--rotate-pages", "in.pdf", "out.pdf",
            ],
        )  # fmt: skip

    def test_the_pages_are_given_as_a_list_of_ranges(self):
        for numbers, expected in (
            ([3, 7, 12, 13, 14], "3,7,12-14"),
            ([5], "5"),
            ([1, 2], "1-2"),
            ([9, 2, 3, 3], "2-3,9"),
            ([], ""),
        ):
            with self.subTest(numbers=numbers):
                self.assertEqual(plan.page_ranges(numbers), expected)
        command = plan.section_command(
            "ocrmypdf", "in.pdf", "out.pdf", [2, 4, 5], languages="eng", jobs=1, output_type="pdf"
        )
        self.assertEqual(command[command.index("--pages") + 1], "2,4-5")

    def test_deskew_and_rotation_can_be_left_out(self):
        command = self._command(deskew_and_rotate=False)
        self.assertNotIn("--deskew", command)
        self.assertNotIn("--rotate-pages", command)

    def test_force_replaces_skip_text(self):
        command = self._command(add={plan.FORCE})
        self.assertIn("--force-ocr", command)
        self.assertNotIn("--skip-text", command)

    def test_the_additions_of_the_failed_tries(self):
        command = self._command(add={plan.DPI, plan.DOWNSAMPLE}, image_dpi=300)
        self.assertIn("--tesseract-downsample-large-images", command)
        self.assertEqual(command[command.index("--image-dpi") + 1], "300")

    def test_the_resolution_is_only_given_when_it_is_asked_for(self):
        self.assertNotIn("--image-dpi", self._command(image_dpi=300))
        self.assertNotIn("--image-dpi", self._command(add={plan.DPI}))


# A program that ends with the code and the error text it is given.
STUB = "import sys\nsys.stderr.write(sys.argv[2] + '\\n')\nraise SystemExit(int(sys.argv[1]))\n"


@tagged("post_install", "-at_install")
class TestOcrWithPrograms(BaseCase):
    """The pieces together: the starter, a program that ends as told (a stub), the real one."""

    def _run(self, folder, command):
        done = subprocess.run(
            [sys.executable, "-I", START_OCR, "19", folder, *command],
            capture_output=True,
            check=False,
            timeout=300,
        )
        return done.returncode, done.stderr.decode(errors="replace")

    def test_the_code_and_the_error_text_of_a_program_reach_the_rules(self):
        cases = [
            (2, "Input file is an image, but has no resolution (DPI)", plan.AGAIN, plan.DPI),
            (7, "Image too large: (41437, 5315)", plan.AGAIN, plan.DOWNSAMPLE),
            (8, "EncryptedPdfError", plan.FAIL, None),
            (7, "OSError: [Errno 28] No space left on device", plan.PAUSE, None),
        ]
        with tempfile.TemporaryDirectory() as folder:
            for code, text, action, add in cases:
                with self.subTest(code=code):
                    ended, stderr = self._run(folder, [sys.executable, "-c", STUB, str(code), text])
                    outcome = plan.classify(ended, stderr)
                    self.assertEqual((outcome.action, outcome.add), (action, add))

    def test_a_program_that_is_not_there_stops_the_recognition(self):
        with tempfile.TemporaryDirectory() as folder:
            ended, stderr = self._run(folder, ["int-filemanager-no-such-program"])
        self.assertEqual(ended, 127)
        self.assertEqual(plan.classify(ended, stderr).action, plan.BLOCK)

    @unittest.skipUnless(shutil.which("ocrmypdf"), "ocrmypdf is not installed")
    def test_the_real_program_takes_the_command_and_makes_the_pdf(self):
        with tempfile.TemporaryDirectory() as folder:
            source = os.path.join(folder, "in.pdf")
            with open(source, "wb") as handle:
                handle.write(text_files.pdf(["one", "two", "three"]))
            for index, add in enumerate(({}, {plan.FORCE}, {plan.DOWNSAMPLE})):
                with self.subTest(add=add):
                    target = os.path.join(folder, f"out{index}.pdf")
                    command = plan.section_command(
                        "ocrmypdf", source, target, [1, 2],
                        languages="eng", jobs=1, output_type="pdf", add=add,
                    )  # fmt: skip
                    ended, stderr = self._run(folder, command)
                    self.assertEqual(plan.classify(ended, stderr).action, plan.DONE, stderr)
                    self.assertTrue(os.path.getsize(target))

    @unittest.skipUnless(shutil.which("ocrmypdf"), "ocrmypdf is not installed")
    def test_the_real_program_says_what_the_rules_expect_for_the_faults_we_know(self):
        with tempfile.TemporaryDirectory() as folder:
            plain = os.path.join(folder, "plain.pdf")
            with open(plain, "wb") as handle:
                handle.write(text_files.pdf(["a page with plenty of text on it"]))
            encrypted = os.path.join(folder, "encrypted.pdf")
            if shutil.which("qpdf"):
                subprocess.run(
                    ["qpdf", "--encrypt", "user", "owner", "256", "--", plain, encrypted],
                    check=True,
                    capture_output=True,
                    timeout=60,
                )
            else:
                encrypted = None
            out = os.path.join(folder, "out.pdf")
            cases = [
                # Text on the page and no ``--skip-text``: refused, then tried with force.
                ("text", ["ocrmypdf", "-l", "eng", "--quiet", plain, out], plan.AGAIN, plan.FORCE),
                # A language that Tesseract does not have.
                ("language", ["ocrmypdf", "-l", "zzz", "--skip-text", "--quiet", plain, out], plan.BLOCK, None),
                # A bad option.
                ("option", ["ocrmypdf", "--no-such-option", plain, out], plan.BLOCK, None),
            ]
            if encrypted:
                # A password to open: not ours to give.
                cases.append(("password", ["ocrmypdf", "--skip-text", "--quiet", encrypted, out], plan.FAIL, None))
            for name, command, action, add in cases:
                with self.subTest(name=name):
                    ended, stderr = self._run(folder, command)
                    outcome = plan.classify(ended, stderr)
                    self.assertEqual((outcome.action, outcome.add), (action, add), (ended, stderr))

    @unittest.skipUnless(shutil.which("ocrmypdf"), "ocrmypdf is not installed")
    def test_the_real_program_gives_up_on_a_file_that_is_no_pdf(self):
        with tempfile.TemporaryDirectory() as folder:
            source = os.path.join(folder, "in.pdf")
            with open(source, "wb") as handle:
                handle.write(b"this is not a pdf")
            command = plan.section_command(
                "ocrmypdf", source, os.path.join(folder, "out.pdf"), [1],
                languages="eng", jobs=1, output_type="pdf",
            )  # fmt: skip
            ended, stderr = self._run(folder, command)
        outcome = plan.classify(ended, stderr)
        self.assertEqual((outcome.action, outcome.reason), (plan.FAIL, "bad_file"))
