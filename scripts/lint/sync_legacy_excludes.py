#!/usr/bin/env python3
"""Keep the LEGACY exclude block of .pre-commit-config.yaml in sync.

Odoo rule (docs/odoo_konventionen_2026-09-26.md): existing code is not reformatted. pre-commit
therefore only checks files that did not exist at the baseline tag. Whole legacy modules are
excluded by directory, the baseline files of modules that are being rewritten
(``int_filemanager``) one by one. Rewritten files are removed from the list by hand-editing
LEGACY_FILES_KEEP below or by raising the baseline; run this script afterwards.

Usage:
    scripts/lint/sync_legacy_excludes.py            # rewrite the block
    scripts/lint/sync_legacy_excludes.py --check    # exit 1 if the block is outdated
"""

import argparse
import pathlib
import re
import subprocess
import sys

BASELINE = "int_filemanager-v1"
# Modules that stay untouched as a whole (third-party or not rewritten).
LEGACY_MODULES = (
    "int_fleet_kanban_width",
    "int_generic",
    "int_legacy_erp_import",
    "int_repair_workshop",
    "onlyoffice_odoo",
)
# Modules that are rewritten: only their baseline files are legacy.
PARTIAL_MODULES = ("int_filemanager",)
# Baseline files of PARTIAL_MODULES that were rewritten and now have to pass the checks.
# Add the path here as soon as a legacy file is rewritten (or removed from the module).
REWRITTEN_FILES = frozenset()

START = "  # LEGACY (existing code is not reformatted, see scripts/lint/sync_legacy_excludes.py)"
END = "  # END LEGACY"
CONFIG = pathlib.Path(__file__).resolve().parents[2] / ".pre-commit-config.yaml"


def baseline_files():
    out = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", BASELINE],
        check=True,
        capture_output=True,
        text=True,
        cwd=CONFIG.parent,
    ).stdout
    return sorted(out.splitlines())


def build_block():
    lines = [START]
    for module in LEGACY_MODULES:
        lines.append(f"  ^{re.escape(module)}/|")
    for path in baseline_files():
        module = path.split("/", 1)[0]
        if module in PARTIAL_MODULES and path not in REWRITTEN_FILES:
            lines.append(f"  ^{re.escape(path)}$|")
    lines.append(END)
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    text = CONFIG.read_text()
    pattern = re.compile(re.escape(START) + r".*?" + re.escape(END), re.S)
    if not pattern.search(text):
        sys.exit(f"markers not found in {CONFIG.name}")
    new = pattern.sub(lambda _m: build_block(), text)
    if args.check:
        if new != text:
            sys.exit("LEGACY block is outdated; run scripts/lint/sync_legacy_excludes.py")
        return
    CONFIG.write_text(new)


if __name__ == "__main__":
    main()
