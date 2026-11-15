#!/usr/bin/env python3
"""Write the file of the examples that the Python checker and the Go checker must read the same way.

    python tools/int_workbench/software_golden.py           writes int_workbench/tests/data/software_golden.json
    python tools/int_workbench/software_golden.py OUT.json  writes OUT.json (copy it to micserv/go/workbench/softwarelib/testdata/golden.json)

The test of the module compares the file with what the checker says today, so it cannot go stale unnoticed.
"""

import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MODULE = os.path.normpath(os.path.join(HERE, "..", "..", "int_workbench"))


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def main():
    check = load("software_check", os.path.join(MODULE, "models", "software_check.py"))
    images = load("images", os.path.join(MODULE, "tests", "images.py"))
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(MODULE, "tests", "data", "software_golden.json")
    with open(out, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(images.golden(check), handle, indent=1, sort_keys=True)
        handle.write("\n")
    print("written:", out)


if __name__ == "__main__":
    main()
