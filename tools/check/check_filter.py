"""Filter odoo-ls and test_lint output down to int_filemanager.

Runs inside the Odoo test image on Tower. Both tools check far more than our module:
odoo-ls reports ~1,800 diagnostics in the Odoo core, and test_lint runs pylint over the
whole core (which has findings of its own), so their exit status alone says nothing about
our code. Findings under int_filemanager always fail the check. Beyond that, test_lint only
counts as clean when Odoo's summary line reports every failed test and each of them is either
explained by a finding in our module or on the allowlist below (known core findings of
TestPyLint.test_pylint). Anything unrecognised fails: a check must not turn green because its
output was not understood.
"""

import json
import re
import sys
from pathlib import Path

WORK = Path("/work")
PREFIX = "/mnt/v2src/"
MODULE = "int_filemanager/"
# odoo-ls severities: 1 error, 2 warning, 3 information, 4 hint. Information covers
# known limitations such as OLS03024 (classes declared in test functions).
MAX_SEVERITY = 2


# Failed tests that are known to be caused by the Odoo core and are accepted when none of their
# pylint findings lies in our module (and there is at least one finding, so a pylint crash fails).
KNOWN_CORE_FAILURES = {"TestPyLint.test_pylint"}

SUMMARY_RE = re.compile(r"(\d+) failed, (\d+) error\(s\) of (\d+) tests when loading database")
# Odoo logs "FAIL: Class.test" or, for a subtest, "FAIL: Subtest Class.test (module='x')". The whole text is
# the identity of the failure, so every subtest counts on its own.
FAILED_TEST_RE = re.compile(r": (?:FAIL|ERROR): (?P<test>\S.*?)\s*$")


def _rel(path):
    path = path.removeprefix("file://")
    return path[len(PREFIX):] if path.startswith(PREFIX) else None


def odoo_ls_findings():
    data = json.loads((WORK / "odoo_ls.json").read_text(encoding="utf-8"))
    for event in data.get("events", []):
        if event.get("type") != "diagnostic":
            continue
        value = event.get("value") or event.get("params") or event
        rel = _rel(value.get("uri", ""))
        if not rel or not rel.startswith(MODULE):
            continue
        for diag in value.get("diagnostics", []):
            if diag.get("severity", 1) > MAX_SEVERITY:
                continue
            line = diag["range"]["start"]["line"] + 1
            yield rel, line, "odoo-ls", f"{diag.get('code')} {diag['message']}"


PYLINT_RE = re.compile(r"^\s*(?P<msg>.+?) at (?P<path>/\S+?):(?P<line>\d+)\s*$")
PATH_RE = re.compile(re.escape(PREFIX) + r"(?P<rel>" + re.escape(MODULE) + r"[^\s\"”:]+)")


def test_lint_findings():
    log = WORK / "test_lint.log"
    text = log.read_text(encoding="utf-8", errors="replace")
    summaries = SUMMARY_RE.findall(text)
    if not summaries:
        raise SystemExit("test_lint did not finish, see test_lint.log")
    failed, errors, _total = (int(n) for n in summaries[-1])
    failed_tests = set()
    for raw in text.splitlines():
        match = FAILED_TEST_RE.search(raw)
        if match:
            failed_tests.add(match["test"])
    seen = set()
    pylint_lines = 0
    for raw in text.splitlines():
        match = PYLINT_RE.match(raw)
        if match:
            pylint_lines += 1
            rel = _rel(match["path"])
            if rel and rel.startswith(MODULE):
                key = (rel, int(match["line"]), match["msg"])
                if key not in seen:
                    seen.add(key)
                    yield rel, int(match["line"]), "test_lint/pylint", match["msg"]
            continue
        if ("ERROR" in raw or "AssertionError" in raw) and PREFIX + MODULE in raw:
            found = PATH_RE.search(raw)
            message = raw.split(": ", 1)[-1].strip()
            key = (found["rel"], 0, message)
            if key not in seen:
                seen.add(key)
                yield found["rel"], 0, "test_lint", message

    # Everything below guards against output we did not recognise.
    for test in sorted(failed_tests - KNOWN_CORE_FAILURES):
        yield "(test_lint)", 0, "test_lint", f"{test} failed"
    if "TestPyLint.test_pylint" in failed_tests and pylint_lines == 0:
        yield "(test_lint)", 0, "test_lint", "TestPyLint.test_pylint failed without any pylint finding"
    if failed + errors != len(failed_tests):
        yield "(test_lint)", 0, "test_lint", (
            f"summary reports {failed} failed + {errors} error(s), "
            f"but {len(failed_tests)} failed test(s) were recognised in the log"
        )
    exit_file = WORK / "test_lint.exit"
    exit_code = exit_file.read_text().strip() if exit_file.is_file() else "missing"
    if exit_code != "0" and failed + errors == 0:
        yield "(test_lint)", 0, "test_lint", f"odoo exited with {exit_code} but the summary shows no failure"


def main():
    findings = list(odoo_ls_findings())
    if "--no-test-lint" not in sys.argv:
        findings += list(test_lint_findings())
    print(f"== findings: {len(findings)}")
    for rel, line, tool, message in sorted(findings):
        print(f"  {rel}:{line} [{tool}] {message[:200]}")
    print(f"== result: {'FAIL' if findings else 'OK'}")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
