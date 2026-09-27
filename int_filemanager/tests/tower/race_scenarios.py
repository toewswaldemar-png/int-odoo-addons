"""Driver for the A3/A4 real-process race tests (Konzept 16, Pruefbericht
A3/A4). See README.md in this directory for prerequisites, the stage-name
contract the write path must implement, and why this cannot be an Odoo
TransactionCase. Runs against a real, running Odoo instance (workers=2) on
the Tower test environment - never against fmv2/fmreal or the live DB.

Standard library only (matches docs/prototypes/fm2/tests_block_a/tlib.py):
this runs in a small helper container that need not have `requests`
installed.
"""

import argparse
import base64
import glob
import json
import logging
import os
import shutil
import threading
import time
import urllib.error
import urllib.request

_logger = logging.getLogger(__name__)


def _b64(data):
    return base64.b64encode(data).decode()


class ScenarioFailed(AssertionError):
    pass


class CallResult:
    def __init__(self, value=None, error=None):
        self.value = value
        self.error = error

    @property
    def ok(self):
        return self.error is None


def json2_call(base_url, api_key, model, method, params, timeout=30):
    """POST /json/2/<model>/<method> with a bearer API key (Konzept 19.16).
    Returns the raw result on success, raises urllib.error.HTTPError (with
    the JSON error body already read into .body) on a non-2xx response."""
    body = json.dumps(params).encode("utf-8")
    req = urllib.request.Request(
        f"{base_url}/json/2/{model}/{method}",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        exc.body = exc.read()
        raise


def set_fault(fault_file, spec):
    with open(fault_file, "w", encoding="utf-8") as f:
        f.write(spec)


def clear_fault(fault_file):
    if os.path.exists(fault_file):
        os.remove(fault_file)


def clear_barrier_dirs(fault_file):
    for path in glob.glob(f"{fault_file}.barrier.*"):
        shutil.rmtree(path, ignore_errors=True)


def run_concurrent(fn_a, fn_b):
    """Fire two calls from two Python threads so both HTTP requests are in
    flight at (almost) the same time - the actual overlap is then forced by
    the barrier the fault file installs server-side, not by this timing."""
    results = [None, None]

    def wrap(i, fn):
        try:
            results[i] = CallResult(value=fn())
        except urllib.error.HTTPError as exc:
            results[i] = CallResult(error=exc)

    t_a = threading.Thread(target=wrap, args=(0, fn_a))
    t_b = threading.Thread(target=wrap, args=(1, fn_b))
    t_a.start()
    t_b.start()
    t_a.join(timeout=60)
    t_b.join(timeout=60)
    if t_a.is_alive() or t_b.is_alive():
        raise ScenarioFailed(
            "a racer did not return within 60s - barrier likely never satisfied"
        )
    return results


# --------------------------------------------------------------------------
# Thin wrappers around the real write-path methods (int_filemanager.node),
# called over JSON-2 with a bearer API key (Konzept 19.16). Content always
# travels as base64 (JSON cannot carry binary data, Konzept 12/19.16) -
# blobstore.decode_content() on the server side accepts that transparently.
# --------------------------------------------------------------------------


def perform_create_node(base_url, api_key, parent_id, name, content=b"race"):
    return json2_call(
        base_url,
        api_key,
        "int_filemanager.node",
        "create_file",
        {
            "parent_id": parent_id,
            "name": name,
            "content": _b64(content),
            "operation_key": f"race-create-{name}-{time.monotonic_ns()}",
        },
    )


def perform_new_revision(base_url, api_key, node_id, base_revision_id, content):
    return json2_call(
        base_url,
        api_key,
        "int_filemanager.node",
        "create_new_revision",
        {
            "node_id": node_id,
            "base_revision_id": base_revision_id,
            "content": _b64(content),
            "operation_key": f"race-revise-{node_id}-{time.monotonic_ns()}",
        },
    )


def perform_rename(base_url, api_key, node_id, new_name, new_parent_id=False):
    return json2_call(
        base_url,
        api_key,
        "int_filemanager.node",
        "rename_or_move",
        {
            "node_id": node_id,
            "new_parent_id": new_parent_id,
            "new_name": new_name,
            "operation_key": f"race-rename-{node_id}-{time.monotonic_ns()}",
        },
    )


def perform_move(base_url, api_key, node_id, new_parent_id, new_name):
    return perform_rename(base_url, api_key, node_id, new_name, new_parent_id)


def perform_trash(base_url, api_key, node_id):
    return json2_call(
        base_url,
        api_key,
        "int_filemanager.node",
        "trash",
        {
            "node_id": node_id,
            "operation_key": f"race-trash-{node_id}-{time.monotonic_ns()}",
        },
    )


# A4's cleanup job is @api.autovacuum, not a public method or an ir.cron
# record of its own - it is only ever invoked by Odoo's own daily vacuum
# sweep (ir.autovacuum._run_vacuum_cleaner, which itself requires admin AND
# a 'cron_id' in context) and is deliberately not exposed for external
# triggering. A live two-process reproduction of A4 would need a dedicated
# admin trigger endpoint this module does not have; the exact invariant
# (a reused blob must survive a concurrent cleanup run) is instead covered
# deterministically in int_filemanager/tests/test_v2_blobstore.py, which can
# force the precise ordering directly instead of hoping an HTTP race lands on
# it. Left as a documented gap rather than adding test-only production code.


def load_fixtures(fixtures_path):
    """Fixture ids come from a separate odoo-shell bootstrap step
    (bootstrap_fixtures.py in this directory, see README "Prerequisites"),
    not from calling the write paths themselves: a scope and its root
    folder are administrative setup (creating a scope needs "manage"
    rights nobody has by default, Konzept 12), not something a normal
    write-path caller ever does. Each scenario gets its OWN node fixture
    (never shared) so running --scenario all does not make a later
    scenario's outcome depend on an earlier one having won its race a
    particular way. That script's JSON output - api_key, parent_id,
    revision_node_id/revision_base_revision_id, rename_node_a_id/
    rename_node_b_id, move_node_id/move_new_parent_id, lock_node_id - is
    passed straight through here."""
    with open(fixtures_path, encoding="utf-8") as f:
        return json.load(f)


# --------------------------------------------------------------------------
# A3 scenarios (Konzept 16 "A3 Wettlaeufe"). Every scenario takes the same
# (base_url, api_key, fault_file, fixtures) signature so main() can dispatch
# uniformly; each pulls the ids it needs out of `fixtures`.
# --------------------------------------------------------------------------


def scenario_same_new_name_twice(base_url, api_key, fault_file, fixtures):
    """Two racers create a node with the SAME new name under the same
    parent. Expectation (A3): exactly one node survives with one revision -
    NOT a second silent row, and NOT a lost update; the loser gets a defined
    error (existing-name / retry), not a crash."""
    parent_id = fixtures["parent_id"]
    set_fault(fault_file, "node_create_before_check:barrier:2")
    try:
        results = run_concurrent(
            lambda: perform_create_node(
                base_url, api_key, parent_id, "race-same-name.txt"
            ),
            lambda: perform_create_node(
                base_url, api_key, parent_id, "race-same-name.txt"
            ),
        )
    finally:
        clear_fault(fault_file)
        clear_barrier_dirs(fault_file)

    oks = [r for r in results if r.ok]
    errs = [r for r in results if not r.ok]
    if len(oks) != 1 or len(errs) != 1:
        raise ScenarioFailed(
            f"expected exactly one success and one defined error, got {results}"
        )


def scenario_same_base_revision_twice(base_url, api_key, fault_file, fixtures):
    """Two racers save a new revision of the same node from the same base
    revision (double-click / two tabs). Expectation (I6/A3): one wins, the
    other gets a base-revision conflict - never a silently dropped edit."""
    node_id = fixtures["revision_node_id"]
    base_revision_id = fixtures["revision_base_revision_id"]
    set_fault(fault_file, "revision_write_before_check:barrier:2")
    try:
        results = run_concurrent(
            lambda: perform_new_revision(
                base_url, api_key, node_id, base_revision_id, b"racer-a-content"
            ),
            lambda: perform_new_revision(
                base_url, api_key, node_id, base_revision_id, b"racer-b-content"
            ),
        )
    finally:
        clear_fault(fault_file)
        clear_barrier_dirs(fault_file)

    oks = [r for r in results if r.ok]
    errs = [r for r in results if not r.ok]
    if len(oks) != 1 or len(errs) != 1:
        raise ScenarioFailed(
            f"expected exactly one success and one conflict error, got {results}"
        )


def scenario_rename_to_same_name(base_url, api_key, fault_file, fixtures):
    """Two different existing nodes are renamed to the SAME target name at
    the same time. Expectation (A3): one rename succeeds, the other is
    rejected with a name-conflict error - never two nodes ending up with the
    same (parent, name)."""
    node_id = fixtures["rename_node_a_id"]
    node_b_id = fixtures["rename_node_b_id"]
    set_fault(fault_file, "node_rename_before_check:barrier:2")
    try:
        results = run_concurrent(
            lambda: perform_rename(base_url, api_key, node_id, "race-target-name.txt"),
            lambda: perform_rename(
                base_url, api_key, node_b_id, "race-target-name.txt"
            ),
        )
    finally:
        clear_fault(fault_file)
        clear_barrier_dirs(fault_file)

    oks = [r for r in results if r.ok]
    errs = [r for r in results if not r.ok]
    if len(oks) != 1 or len(errs) != 1:
        raise ScenarioFailed(f"expected exactly one rename to win, got {results}")


def scenario_move_against_delete(base_url, api_key, fault_file, fixtures):
    """One racer moves a node while the other deletes it. Expectation (A3):
    a defined outcome either way (moved node stays deleted-or-not
    consistently; no orphaned row, no node that is both trashed and present
    under a new parent)."""
    node_id = fixtures["move_node_id"]
    new_parent_id = fixtures["move_new_parent_id"]
    set_fault(fault_file, "node_rename_before_check:barrier:2")
    try:
        results = run_concurrent(
            lambda: perform_move(
                base_url, api_key, node_id, new_parent_id, "moved-away.txt"
            ),
            lambda: perform_trash(base_url, api_key, node_id),
        )
    finally:
        clear_fault(fault_file)
        clear_barrier_dirs(fault_file)

    if all(r.ok for r in results):
        raise ScenarioFailed(
            f"move and delete both reported success on the same node: {results}"
        )


def scenario_lock_timeout_triggers_retry(base_url, api_key, fault_file, fixtures):
    """One racer holds the row lock past `lock_timeout` while the other
    writes it. Expectation (A3): the second racer sees `LockError`
    (`retrying()` retries it, Konzept 6) rather than hanging indefinitely or
    silently overwriting."""
    node_id = fixtures["lock_node_id"]
    set_fault(fault_file, "node_lock_before_wait:barrier:2")
    try:
        started = time.monotonic()
        results = run_concurrent(
            lambda: perform_rename(base_url, api_key, node_id, "held-by-racer-a.txt"),
            lambda: perform_rename(base_url, api_key, node_id, "held-by-racer-b.txt"),
        )
        elapsed = time.monotonic() - started
    finally:
        clear_fault(fault_file)
        clear_barrier_dirs(fault_file)

    if elapsed > 30:
        raise ScenarioFailed(
            f"racer took {elapsed:.1f}s - lock_timeout/retry does not appear wired up"
        )
    oks = [r for r in results if r.ok]
    if len(oks) != 1:
        raise ScenarioFailed(
            f"expected exactly one rename to win after the lock timeout, got {results}"
        )


# A4 (Konzept 16 "A4 Aufraeumjob") has no scenario here: see the comment
# above load_fixtures() for why a live two-process reproduction is not
# feasible without adding test-only production code, and where its
# invariant is instead covered deterministically.


SCENARIOS = {
    "same_new_name_twice": scenario_same_new_name_twice,
    "same_base_revision_twice": scenario_same_base_revision_twice,
    "rename_to_same_name": scenario_rename_to_same_name,
    "move_against_delete": scenario_move_against_delete,
    "lock_timeout_triggers_retry": scenario_lock_timeout_triggers_retry,
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--fault-file", required=True)
    parser.add_argument(
        "--fixtures-json",
        required=False,
        help="path to the JSON fixture file produced by the odoo-shell bootstrap"
        " script (see README 'Prerequisites'); contains api_key and all fixture ids",
    )
    parser.add_argument("--scenario", default="all", choices=["all", *SCENARIOS])
    parser.add_argument(
        "--cleanup", action="store_true", help="remove stale barrier dirs and exit"
    )
    args = parser.parse_args()

    if args.cleanup:
        clear_fault(args.fault_file)
        clear_barrier_dirs(args.fault_file)
        _logger.info("cleaned up")
        return

    if not args.fixtures_json:
        parser.error("--fixtures-json is required unless --cleanup is given")

    fixtures = load_fixtures(args.fixtures_json)
    api_key = fixtures["api_key"]

    names = list(SCENARIOS) if args.scenario == "all" else [args.scenario]
    failures = []
    for name in names:
        _logger.info("--- %s ---", name)
        try:
            SCENARIOS[name](args.base_url, api_key, args.fault_file, fixtures)
        except NotImplementedError as exc:
            _logger.info("PENDING: %s", exc)
        except ScenarioFailed as exc:
            _logger.info("FAILED: %s", exc)
            failures.append(name)
        else:
            _logger.info("OK")

    if failures:
        raise SystemExit(f"failed: {', '.join(failures)}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    main()
