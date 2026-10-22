"""Check the reader against a real .kdbx file, without Odoo.

    python tools/int_keepass/read_check.py PATH [--keyfile FILE]

The master password is asked for on the terminal. Only counts and group names
are printed, no entry titles, user names, URLs or passwords.
"""

import argparse
import getpass
import importlib.util
import pathlib
from collections import Counter

spec = importlib.util.spec_from_file_location("kdbx", pathlib.Path(__file__).resolve().parents[2] / "int_keepass" / "kdbx.py")
kdbx = importlib.util.module_from_spec(spec)
spec.loader.exec_module(kdbx)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("path")
    parser.add_argument("--keyfile")
    args = parser.parse_args()
    password = getpass.getpass("Master password: ") or None
    result = kdbx.read_kdbx(args.path, password, args.keyfile)
    groups, entries = result["groups"], result["entries"]
    names = {group["uuid"]: group["name"] for group in groups}
    children = {}
    for group in groups:
        children.setdefault(group["parent"], []).append(group)
    per_group = Counter(entry["group"] for entry in entries)
    print(f"{len(groups)} groups, {len(entries)} entries")

    def show(parent, depth):
        for group in sorted(children.get(parent, []), key=lambda g: g["name"].lower()):
            print(f"{'  ' * depth}{group['name']} ({per_group[group['uuid']]})")
            show(group["uuid"], depth + 1)

    show(None, 0)
    if per_group[None]:
        print(f"(top level: {per_group[None]} entries)")
    assert all(entry["group"] in names or entry["group"] is None for entry in entries)
    if len({entry["uuid"] for entry in entries}) != len(entries):
        print("WARNING: duplicate entry uuids")


if __name__ == "__main__":
    main()
