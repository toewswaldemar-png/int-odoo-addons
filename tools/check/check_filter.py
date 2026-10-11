"""Filter odoo-ls and test_lint output down to int_filemanager.

Runs inside the Odoo test image on Tower. Both tools check far more than our module:
odoo-ls reports ~1,800 diagnostics in the Odoo core, and test_lint runs pylint over the
whole core (which has findings of its own with pylint 3.3), so their exit status says
nothing about our code. We keep only findings under int_filemanager; every one of them
fails the check.
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
    if "tests when loading database" not in text:
        raise SystemExit("test_lint did not finish, see test_lint.log")
    seen = set()
    for raw in text.splitlines():
        match = PYLINT_RE.match(raw)
        if match:
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
