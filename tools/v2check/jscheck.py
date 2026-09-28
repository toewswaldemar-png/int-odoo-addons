"""Static checks of int_filemanager's browser code, run inside the Odoo image (it has the
real transpiler and Node): what a browser would only report at runtime.

1. every JS file under static/src goes through Odoo's own transpiler (imports/exports ->
   odoo.define) and the result must pass `node --check`;
2. every import of an int_filemanager module resolves to a file that exists and, for named
   imports, to a name that file exports;
3. QWeb templates: XML is well-formed, t-name is unique across the module, every t-call
   points to a template that exists (in the module, or in Odoo's own web/mail assets), and
   every t-inherit base exists.

Usage inside the container:  python3 jscheck.py <path to int_filemanager>
"""

import os
import re
import subprocess
import sys
import tempfile
from xml.etree import ElementTree

from odoo.tools.js_transpiler import transpile_javascript

ODOO_ADDONS = "/usr/lib/python3/dist-packages/odoo/addons"


def walk(root, suffix):
    for base, _dirs, files in os.walk(root):
        for name in files:
            if name.endswith(suffix):
                yield os.path.join(base, name)


def module_url(module_dir, path):
    rel = os.path.relpath(path, module_dir).replace(os.sep, "/")
    return f"/{os.path.basename(module_dir)}/{rel}"


IMPORT_RE = re.compile(
    r"import\s+(?:(?P<names>[\w${},\s*]+?)\s+from\s+)?[\"'](?P<path>[^\"']+)[\"']"
)
EXPORT_RE = re.compile(
    r"export\s+(?:async\s+)?(?:function\*?|class|const|let|var)\s+(?P<name>[\w$]+)"
)


def check_js(module_dir, problems):
    src = os.path.join(module_dir, "static", "src")
    files = list(walk(src, ".js"))
    exports = {}
    for path in files:
        with open(path, encoding="utf-8") as f:
            exports[path] = set(EXPORT_RE.findall(f.read()))
    checked = 0
    for path in files:
        with open(path, encoding="utf-8") as f:
            content = f.read()
        if "@odoo-module" not in content[:400]:
            continue  # not an ES module for Odoo
        checked += 1
        url = module_url(module_dir, path)
        try:
            transpiled = transpile_javascript(url, content)
        except Exception as exc:  # noqa: BLE001
            problems.append(f"{url}: transpile failed: {exc}")
            continue
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as tmp:
            tmp.write(transpiled)
        result = subprocess.run(
            ["node", "--check", tmp.name], capture_output=True, text=True, check=False
        )
        os.unlink(tmp.name)
        if result.returncode:
            problems.append(f"{url}: {result.stderr.strip().splitlines()[0:4]}")
        for match in IMPORT_RE.finditer(content):
            target = match.group("path")
            if not target.startswith("."):
                continue
            resolved = os.path.normpath(os.path.join(os.path.dirname(path), target))
            if not os.path.exists(resolved) and os.path.exists(resolved + ".js"):
                resolved += ".js"
            if not os.path.exists(resolved):
                problems.append(f"{url}: import {target!r} does not exist")
                continue
            names = match.group("names") or ""
            named = re.search(r"\{([^}]*)\}", names)
            if named and resolved in exports:
                for item in named.group(1).split(","):
                    wanted = item.split(" as ")[0].strip()
                    if wanted and wanted not in exports[resolved]:
                        problems.append(
                            f"{url}: {resolved.rsplit('/', 1)[-1]} does not export {wanted}"
                        )


    print(f"{checked} JS module(s) transpiled and syntax-checked")


def template_names_of(root_dir):
    names = {}
    for path in walk(root_dir, ".xml"):
        if "/static/src/" not in path.replace(os.sep, "/"):
            continue
        try:
            tree = ElementTree.parse(path)
        except ElementTree.ParseError:
            continue
        for element in tree.iter():
            name = element.get("t-name")
            if name:
                names.setdefault(name, []).append(path)
    return names


def check_templates(module_dir, problems):
    src = os.path.join(module_dir, "static", "src")
    own = {}
    for path in walk(src, ".xml"):
        try:
            tree = ElementTree.parse(path)
        except ElementTree.ParseError as exc:
            problems.append(f"{module_url(module_dir, path)}: not well-formed XML: {exc}")
            continue
        for element in tree.iter():
            name = element.get("t-name")
            if name:
                own.setdefault(name, []).append(path)
    for name, paths in own.items():
        if len(paths) > 1:
            problems.append(f"template {name} is defined {len(paths)} times")
    print(f"{len(own)} template(s), {sum(len(v) for v in own.values())} definition(s)")
    known = set(own)
    for addon in ("web", "mail", "bus", "portal", "onlyoffice_odoo"):
        known.update(template_names_of(os.path.join(ODOO_ADDONS, addon)))
    for path in walk(src, ".xml"):
        try:
            tree = ElementTree.parse(path)
        except ElementTree.ParseError:
            continue
        for element in tree.iter():
            for attr in ("t-call", "t-inherit"):
                target = element.get(attr)
                if target and "{" not in target and target not in known:
                    problems.append(
                        f"{module_url(module_dir, path)}: {attr}={target!r} does not exist"
                    )


def main():
    module_dir = os.path.abspath(sys.argv[1])
    problems = []
    check_js(module_dir, problems)
    check_templates(module_dir, problems)
    for problem in problems:
        print("PROBLEM:", problem)
    print(f"{len(problems)} problem(s)")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
