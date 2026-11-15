#!/usr/bin/env python3
"""Bring the stock of the original (C:\\INBETRIE) into the project management of int_workbench, as drafts.

What it does (see micserv/PLAN.md, Teil J, Schritt 3):
  * every project folder (with a DEF.BIN) becomes a version: the files that belong to it, read by their content, named after the
    checksum (the rule of the project library of the service), the same files from several folders are one version with several origins;
  * every program (S-Record image, program text) found anywhere in the stock becomes a record of the software, once for each content.
Everything comes in as a *draft*: a manager looks at it in Odoo and approves what is wanted. Nothing is deleted or changed in Odoo, and
bringing the same files in again changes nothing. The stock itself is only read.

Usage:
  python workbench_import.py --stock C:\\INBETRIE                       dry run: what would come in (no Odoo needed)
  python workbench_import.py --stock C:\\INBETRIE --url http://host:8069 --db NAME --key-file KEYFILE --run

The key is the API key of a user with the manager role of Workbench; it is read from a file, never from the command line.
"""

import argparse
import base64
import collections
import json
import os
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
MODELS = os.path.normpath(os.path.join(HERE, "..", "..", "int_workbench", "models"))
sys.path.insert(0, MODELS)
import project_check  # noqa: E402  (the rules are the module's own: the same code that Odoo runs)
import software_check  # noqa: E402

MAX_PROGRAM_BYTES = software_check.MAX_FILE_SIZE


def walk_projects(stock):
    """Every folder with a DEF.BIN: ``(vehicle, project, [(name, bytes)])``, the vehicle being the path above the project."""
    for folder, _dirs, files in os.walk(stock):
        if "def.bin" not in {name.lower() for name in files}:
            continue
        relative = os.path.relpath(folder, stock).replace("\\", "/")
        vehicle, _slash, project = relative.rpartition("/")
        content = []
        for name in files:
            path = os.path.join(folder, name)
            if os.path.isfile(path) and not project_check.is_excluded(name):
                with open(path, "rb") as handle:
                    content.append((name, handle.read()))
        yield vehicle or "-", project, relative, content


def walk_programs(stock):
    """Every file anywhere in the stock that is a program: ``(path, name, bytes, Checked)``."""
    for folder, _dirs, files in os.walk(stock):
        for name in files:
            path = os.path.join(folder, name)
            try:
                size = os.path.getsize(path)
                if size == 0 or size > MAX_PROGRAM_BYTES:
                    continue
                with open(path, "rb") as handle:
                    head = handle.read(4000)
                    # cheap test before the whole file is read: an image starts with S0..S9, a program text has its header line
                    if not (head[:1] in (b"S", b"s") or software_check.TEXT_HEADER.search(head.decode("latin1", "replace"))):
                        continue
                    content = head + handle.read()
            except OSError:
                continue
            try:
                checked = software_check.check_file(name, content)
            except software_check.ImageError:
                continue
            yield path, name, content, checked


def plan(stock, include_unknown=False):
    """Read the stock and say what would come in. Files that no known controller takes (other makers) are left out and listed."""
    versions = {}
    problems = collections.Counter()
    for vehicle, project, relative, files in walk_projects(stock):
        try:
            info = project_check.build(files)
        except project_check.VersionError as error:
            problems[error.code] += 1
            continue
        entry = versions.setdefault(info.checksum, {"info": info, "vehicle": vehicle, "project": project, "origins": []})
        entry["origins"].append(relative)
    programs = {}
    for path, name, content, checked in walk_programs(stock):
        if checked.kind == software_check.KIND_UNKNOWN and not include_unknown:
            problems["left out, no known memory: " + os.path.relpath(path, stock).replace("\\", "/")] += 1
            continue
        entry = programs.setdefault(checked.sha256, {"checked": checked, "name": name, "content": content, "origins": []})
        entry["origins"].append(os.path.relpath(path, stock).replace("\\", "/"))
    return versions, programs, problems


def report(versions, programs, problems):
    kinds = collections.Counter(entry["checked"].kind for entry in programs.values())
    print("Staende (verschiedene Pruefsummen):", len(versions), "aus", sum(len(v["origins"]) for v in versions.values()), "Projektordnern")
    print("  Dateien je Art:", dict(collections.Counter(f.kind for v in versions.values() for f in v["info"].files)))
    print("  Summe MB:", round(sum(v["info"].size for v in versions.values()) / 1e6, 1))
    print("  mit erwarteter Dokumentnummer:", sum(1 for v in versions.values() if v["info"].expected_document))
    print("Programme (verschiedene Inhalte):", len(programs), "aus", sum(len(p["origins"]) for p in programs.values()), "Dateien")
    print("  nach Art:", dict(kinds), " Summe MB:", round(sum(len(p["content"]) for p in programs.values()) / 1e6, 1))
    print("  mit Warnung:", sum(1 for p in programs.values() if p["checked"].warnings))
    if problems:
        print("Abgelehnt oder ausgelassen:", dict(problems))


class Odoo:
    """The JSON-2 API of Odoo: one call is one POST with the arguments as JSON."""

    def __init__(self, url, database, key):
        self.url, self.database, self.key = url.rstrip("/"), database, key

    def call(self, model, method, **arguments):
        request = urllib.request.Request(
            f"{self.url}/json/2/{model}/{method}",
            data=json.dumps(arguments).encode(),
            headers={
                "Authorization": f"bearer {self.key}",
                "X-Odoo-Database": self.database,
                "Content-Type": "application/json; charset=utf-8",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=300) as response:
                return json.loads(response.read())
        except urllib.error.HTTPError as error:
            body = error.read().decode("utf-8", "replace")
            try:
                message = json.loads(body).get("message") or body
            except ValueError:
                message = body
            raise RuntimeError(f"{model}.{method}: {error.code} {message[:300]}") from None


def run(stock, odoo, only, include_unknown=False):
    versions, programs, problems = plan(stock, include_unknown)
    report(versions, programs, problems)
    created = collections.Counter()
    failed = []
    if only in ("all", "programs"):
        for sha, entry in programs.items():
            try:
                answer = odoo.call(
                    "int.workbench.software", "import_file", filename=entry["name"], data=base64.b64encode(entry["content"]).decode()
                )
            except RuntimeError as error:
                failed.append(str(error))
                continue
            created["programs new" if answer["created"] else "programs there"] += 1
    if only in ("all", "projects"):
        for checksum, entry in versions.items():
            files = [{"name": f.name, "data": base64.b64encode(f.content).decode()} for f in entry["info"].files]
            try:
                answer = odoo.call(
                    "int.workbench.project.version",
                    "import_version",
                    vehicle=entry["vehicle"],
                    project=entry["project"],
                    files=files,
                    origin=entry["origins"][0] if len(entry["origins"]) == 1 else "\n".join(entry["origins"]),
                )
            except RuntimeError as error:
                failed.append(str(error))
                continue
            created["versions new" if answer["created"] else "versions there"] += 1
    print("Ergebnis:", dict(created), " Fehler:", len(failed))
    for line in failed[:20]:
        print("  FEHLER", line)
    return 1 if failed else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--stock", required=True, help="the folder of the stock (the original's C:\\INBETRIE)")
    parser.add_argument("--run", action="store_true", help="bring it in (without this: only say what would come in)")
    parser.add_argument("--url", help="address of Odoo, for example http://192.168.188.67:8089")
    parser.add_argument("--db", help="name of the database")
    parser.add_argument("--key-file", help="file with the API key of a manager of Workbench")
    parser.add_argument("--only", choices=("all", "programs", "projects"), default="all")
    parser.add_argument("--with-unknown", action="store_true", help="also bring in files whose memory ranges are no known controller's")
    arguments = parser.parse_args()
    if not os.path.isdir(arguments.stock):
        parser.error("the stock is not a folder")
    if not arguments.run:
        report(*plan(arguments.stock, arguments.with_unknown))
        return 0
    if not (arguments.url and arguments.db and arguments.key_file):
        parser.error("--run needs --url, --db and --key-file")
    with open(arguments.key_file, encoding="utf-8") as handle:
        key = handle.read().strip()
    return run(arguments.stock, Odoo(arguments.url, arguments.db, key), arguments.only, arguments.with_unknown)


if __name__ == "__main__":
    sys.exit(main())
