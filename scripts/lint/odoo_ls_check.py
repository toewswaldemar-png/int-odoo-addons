#!/usr/bin/env python3
"""Evaluate the JSON written by ``odoo_ls_server --parse`` and fail on findings in our code.

odoo-ls (parse mode) knows the Odoo registry, so it finds what pylint cannot: unknown models and
fields, models missing from ``depends``, invalid domain fields, wrong call arguments, compute
methods that do not set their field (docs/pruefautomatik_2026-10-02.md, section 4).

Output format (odoo-ls 1.6.0, ``server/src/cli_backend.rs``): ``{"events": [{"type": "diagnostic",
"uri": "file://...", "diagnostics": [<LSP Diagnostic>]}, {"type": "log", ...}]}`` with LSP
severities 1 = error, 2 = warning, 3 = information, 4 = hint.

Rules:
- only files inside Odoo modules of this repository count (``--root``; not docs/, scripts/);
- severities up to ``--fail-level`` (default 2: errors and warnings) fail the run; level 3
  (e.g. OLS03024) is information, not an error.

Usage: odoo_ls_check.py out.json [--fail-level 2] [--show-info]
"""

import argparse
import collections
import json
import pathlib
import re
import sys
from urllib.parse import unquote, urlparse

REPO = pathlib.Path(__file__).resolve().parents[2]
SEVERITY = {1: "error", 2: "warning", 3: "info", 4: "hint"}


def uri_to_path(uri):
    path = unquote(urlparse(uri).path)
    # Windows: file:///C:/Users/x.py has the path /C:/Users/x.py. Without dropping the slash the path
    # has no drive and every finding looks like it lies outside the repository.
    if re.match(r"/[A-Za-z]:/", path):
        path = path[1:]
    return pathlib.Path(path)


def is_module_file(rel, root):
    """Only files inside an Odoo module count (docs/prototypes, scripts etc. are not module code)."""
    return len(rel.parts) > 1 and (root / rel.parts[0] / "__manifest__.py").is_file()


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("json_file")
    parser.add_argument("--root", default=str(REPO), help="only report files below this directory")
    parser.add_argument("--fail-level", type=int, default=2, choices=(1, 2, 3, 4))
    parser.add_argument("--show-info", action="store_true", help="also print findings above the fail level")
    args = parser.parse_args()

    root = pathlib.Path(args.root).resolve()

    data = json.loads(pathlib.Path(args.json_file).read_text())
    failures, others, by_code = [], [], collections.Counter()
    for event in data.get("events", []):
        if event.get("type") != "diagnostic":
            continue
        path = uri_to_path(event["uri"])
        try:
            rel = path.resolve().relative_to(root)
        except ValueError:
            continue
        if not is_module_file(rel, root):
            continue
        for diag in event.get("diagnostics", []):
            severity = diag.get("severity", 1)
            code = diag.get("code", "?")
            line = diag.get("range", {}).get("start", {}).get("line", 0) + 1
            entry = f"{rel}:{line}: {SEVERITY.get(severity, severity)} {code}: {diag.get('message', '')}"
            if severity <= args.fail_level:
                failures.append(entry)
                by_code[code] += 1
            else:
                others.append(entry)

    for entry in failures:
        print(entry)
    if args.show_info:
        for entry in others:
            print(entry)
    print(
        f"odoo-ls: {len(failures)} finding(s) up to level {args.fail_level}, "
        f"{len(others)} above",
        file=sys.stderr,
    )
    if by_code:
        print("by code: " + ", ".join(f"{code} x{n}" for code, n in by_code.most_common()), file=sys.stderr)
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
