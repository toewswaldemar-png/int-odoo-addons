"""Tests for the test_lint evaluation in check_filter.py (synthetic logs, no Odoo needed).

Run:  python tools/check/test_check_filter.py
"""

import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import check_filter  # noqa: E402

CORE_PYLINT_FAILURE = """\
2026-10-16 21:57:29,895 1 ERROR fmv2_lint odoo.addons.test_lint.tests.test_pylint: FAIL: TestPyLint.test_pylint
Traceback (most recent call last):
AssertionError: pylint test failed:

************* Module addons.purchase.migrations.9.0.1.2.pre-create-properties
Possible SQL injection risk . (E8501) at /usr/lib/python3/dist-packages/odoo/addons/purchase/migrations/9.0.1.2/pre-create-properties.py:31
"""

OWN_PYLINT_FAILURE = CORE_PYLINT_FAILURE + (
    "Possible SQL injection risk . (E8501) at /mnt/v2src/int_filemanager/models/a.py:12\n"
)

# As logged by Odoo 19 (measured on Tower, 2026-10-17): a subtest, and the message names no file.
MANIFEST_FAILURE = """\
2026-10-17 11:31:40,577 1 ERROR fmv2_lint odoo.addons.test_lint.tests.test_manifests: FAIL: Subtest ManifestLinter.test_manifests (module='int_filemanager')
AssertionError: Items in the first set but not the second:
'kontrollfall_unbekannt' : Unknown manifest keys in module 'int_filemanager'. Either there are typos or they must be white listed.
"""


def summary(failed, errors=0):
    return (
        f"2026-10-16 21:57:37,251 1 ERROR fmv2_lint odoo.tests.result: "
        f"{failed} failed, {errors} error(s) of 30 tests when loading database 'fmv2_lint'\n"
    )


class TestLintEvaluationTest(unittest.TestCase):
    def evaluate(self, log, exit_code="1"):
        with tempfile.TemporaryDirectory() as tmp:
            work = pathlib.Path(tmp)
            (work / "test_lint.log").write_text(log, encoding="utf-8")
            if exit_code is not None:
                (work / "test_lint.exit").write_text(exit_code + "\n")
            old = check_filter.WORK
            check_filter.WORK = work
            try:
                return list(check_filter.test_lint_findings())
            finally:
                check_filter.WORK = old

    def test_clean_run(self):
        self.assertEqual(self.evaluate(summary(0), exit_code="0"), [])

    def test_known_core_finding_is_accepted(self):
        self.assertEqual(self.evaluate(CORE_PYLINT_FAILURE + summary(1)), [])

    def test_pylint_finding_in_our_module_fails(self):
        findings = self.evaluate(OWN_PYLINT_FAILURE + summary(1))
        self.assertEqual([f[0] for f in findings], ["int_filemanager/models/a.py"])

    def test_failure_without_path_in_the_message_is_not_swallowed(self):
        # The case that made the old filter report OK: a failed test whose message names no file.
        findings = self.evaluate(MANIFEST_FAILURE + summary(1))
        self.assertEqual(len(findings), 1, findings)
        self.assertIn("ManifestLinter.test_manifests", findings[0][3])

    def test_manifest_failure_next_to_the_known_core_finding(self):
        findings = self.evaluate(MANIFEST_FAILURE + CORE_PYLINT_FAILURE + summary(2))
        self.assertEqual(len(findings), 1, findings)
        self.assertIn("ManifestLinter.test_manifests", findings[0][3])

    def test_unrecognised_failure_count_fails(self):
        findings = self.evaluate(CORE_PYLINT_FAILURE + summary(2))
        self.assertTrue(any("summary reports" in f[3] for f in findings), findings)

    def test_pylint_crash_without_findings_fails(self):
        log = (
            "2026-10-16 21:57:29,895 1 ERROR fmv2_lint odoo.addons.test_lint.tests.test_pylint: "
            "FAIL: TestPyLint.test_pylint\nAssertionError: pylint crashed\n"
        )
        findings = self.evaluate(log + summary(1))
        self.assertTrue(any("without any pylint finding" in f[3] for f in findings), findings)

    def test_nonzero_exit_without_failure_fails(self):
        findings = self.evaluate(summary(0), exit_code="1")
        self.assertTrue(any("exited with 1" in f[3] for f in findings), findings)

    def test_missing_exit_file_with_clean_summary_fails(self):
        findings = self.evaluate(summary(0), exit_code=None)
        self.assertTrue(any("exited with missing" in f[3] for f in findings), findings)

    def test_unfinished_run_stops(self):
        with self.assertRaises(SystemExit):
            self.evaluate("2026-10-16 21:49:28,369 1 INFO started\n")


if __name__ == "__main__":
    unittest.main()
