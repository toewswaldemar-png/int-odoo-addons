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
- legacy files (see sync_legacy_excludes.py) are skipped unless ``--include-legacy``;
- severities up to ``--fail-level`` (default 2: errors and warnings) fail the run; level 3
  (e.g. OLS03024) is information, not an error.

Usage: odoo_ls_check.py out.json [--include-legacy] [--fail-level 2] [--show-info]
"""

import argparse
import collections
import json
import pathlib
import sys
from urllib.parse import unquote, urlparse

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import sync_legacy_excludes as legacy  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parents[2]
SEVERITY = {1: "error", 2: "warning", 3: "info", 4: "hint"}


def uri_to_path(uri):
    return pathlib.Path(unquote(urlparse(uri).path))


def is_module_file(rel, root):
    """Only files inside an Odoo module count (docs/prototypes, scripts etc. are not module code)."""
    return len(rel.parts) > 1 and (root / rel.parts[0] / "__manifest__.py").is_file()


def is_legacy(rel, legacy_files):
    parts = rel.parts
    if parts[0] in legacy.LEGACY_MODULES:
        return True
    return rel.as_posix() in legacy_files


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("json_file")
    parser.add_argument("--root", default=str(REPO), help="only report files below this directory")
    parser.add_argument("--include-legacy", action="store_true")
    parser.add_argument("--fail-level", type=int, default=2, choices=(1, 2, 3, 4))
    parser.add_argument("--show-info", action="store_true", help="also print findings above the fail level")
    args = parser.parse_args()

    root = pathlib.Path(args.root).resolve()
    legacy_files = set()
    if not args.include_legacy:
        legacy_files = {
            path
            for path in legacy.baseline_files()
            if path.split("/", 1)[0] in legacy.PARTIAL_MODULES and path not in legacy.REWRITTEN_FILES
        }

    data = json.loads(pathlib.Path(args.json_file).read_text())
    failures, others, by_code = [], [], collections.Counter()
    skipped_legacy = 0
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
        if not args.include_legacy and is_legacy(rel, legacy_files):
            skipped_legacy += len(event.get("diagnostics", []))
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
        f"{len(others)} above, {skipped_legacy} in legacy files skipped",
        file=sys.stderr,
    )
    if by_code:
        print("by code: " + ", ".join(f"{code} x{n}" for code, n in by_code.most_common()), file=sys.stderr)
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
