"""Filter the odoo-ls output down to int_filemanager and its extension modules (int_filemanager*).

Runs inside the Odoo test image on Tower. odoo-ls checks far more than our module (~1,800
diagnostics in the Odoo core), and it exits normally whatever it finds, so its exit status says
nothing about our code. Every finding under int_filemanager* of severity error or warning fails
the check.
"""

import json
import sys
from pathlib import Path

WORK = Path("/work")
PREFIX = "/mnt/v2src/"
MODULE = "int_filemanager"
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


def main():
    findings = list(odoo_ls_findings())
    print(f"== findings: {len(findings)}")
    for rel, line, tool, message in sorted(findings):
        print(f"  {rel}:{line} [{tool}] {message[:200]}")
    print(f"== result: {'FAIL' if findings else 'OK'}")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
