"""Tests for the odoo-ls evaluation in check_filter.py (synthetic output, no Odoo needed).

Run:  python tools/check/test_check_filter.py
"""

import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import check_filter  # noqa: E402


def event(uri, *diagnostics):
    return {"type": "diagnostic", "uri": uri, "diagnostics": list(diagnostics)}


def diag(code, severity, line=4):
    return {
        "code": code,
        "severity": severity,
        "message": "message",
        "range": {"start": {"line": line, "character": 0}},
    }


class OdooLsEvaluationTest(unittest.TestCase):
    def evaluate(self, *events):
        with tempfile.TemporaryDirectory() as tmp:
            work = pathlib.Path(tmp)
            (work / "odoo_ls.json").write_text(json.dumps({"events": list(events)}), encoding="utf-8")
            old = check_filter.WORK
            check_filter.WORK = work
            try:
                return list(check_filter.odoo_ls_findings())
            finally:
                check_filter.WORK = old

    def test_clean_run(self):
        self.assertEqual(self.evaluate(), [])

    def test_error_in_our_module_fails(self):
        findings = self.evaluate(event("file:///mnt/v2src/int_filemanager/models/a.py", diag("OLS03002", 1)))
        self.assertEqual(findings, [("int_filemanager/models/a.py", 5, "odoo-ls", "OLS03002 message")])

    def test_warning_in_our_module_fails(self):
        findings = self.evaluate(event("/mnt/v2src/int_filemanager/models/a.py", diag("OLS03011", 2)))
        self.assertEqual(len(findings), 1)

    def test_information_is_not_a_finding(self):
        self.assertEqual(self.evaluate(event("/mnt/v2src/int_filemanager/models/a.py", diag("OLS03024", 3))), [])

    def test_findings_in_the_core_are_ignored(self):
        uri = "file:///usr/lib/python3/dist-packages/odoo/models.py"
        self.assertEqual(self.evaluate(event(uri, diag("OLS03002", 1))), [])

    def test_other_event_types_are_ignored(self):
        self.assertEqual(self.evaluate({"type": "log", "uri": "/mnt/v2src/int_filemanager/a.py"}), [])


if __name__ == "__main__":
    unittest.main()
