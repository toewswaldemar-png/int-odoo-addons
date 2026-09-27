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
# Pending on Schritt 3b (Datenmodell, Schreibwege): fill in the JSON-2 method
# names below once they exist, then delete the NotImplementedError. Keep the
# barrier/assertion structure - that part is already correct per Konzept 6/16.
# --------------------------------------------------------------------------


def perform_create_node(base_url, api_key, parent_id, name):
    # TODO(schreibwege): call the future "create a node under a name" JSON-2
    # method (Konzept 6 "Hochladen (neu)"). Must reach node_create_before_check
    # / node_create_after_insert internally.
    raise NotImplementedError(
        "write path for node creation does not exist yet (Schritt 3b)"
    )


def perform_new_revision(base_url, api_key, node_id, base_revision_id, content_sha256):
    # TODO(schreibwege): call the future "new revision" JSON-2 method
    # (Konzept 6 "Neue Fassung"). Must reach revision_write_before_check /
    # revision_write_after_insert internally.
    raise NotImplementedError(
        "write path for new revisions does not exist yet (Schritt 3b)"
    )


def perform_rename(base_url, api_key, node_id, new_name):
    # TODO(schreibwege): call the future rename/move JSON-2 method (Konzept 6
    # "Umbenennen, Verschieben"). Must reach node_rename_before_check internally.
    raise NotImplementedError(
        "write path for rename/move does not exist yet (Schritt 3b)"
    )


def perform_move(base_url, api_key, node_id, new_parent_id):
    raise NotImplementedError("write path for move does not exist yet (Schritt 3b)")


def perform_delete(base_url, api_key, node_id):
    raise NotImplementedError("write path for delete does not exist yet (Schritt 3b)")


def trigger_cleanup_cron(base_url, api_key):
    # TODO(schreibwege): trigger the future blob-cleanup cron directly
    # (e.g. env.ref("int_filemanager.cron_blob_gc").method_direct_trigger()
    # via call_kw/JSON-2 as an admin key). Must reach blob_gc_after_dedup_check
    # / blob_gc_after_delete_before_commit internally.
    raise NotImplementedError("blob cleanup cron does not exist yet (Schritt 3b)")


def setup_fixtures(base_url, api_key):
    """Create the parent folder, an existing node with a revision, and a
    second existing node that every scenario below needs, and return their
    ids. Pending on the same write path as the perform_*() helpers above -
    kept as ONE place so main() can report "nothing to run yet" once instead
    of every scenario failing with a confusing TypeError over missing ids."""
    # TODO(schreibwege): create real fixtures via perform_create_node() /
    # perform_new_revision() once they work, then return e.g.:
    # {"parent_id": ..., "node_id": ..., "base_revision_id": ...,
    #  "node_b_id": ..., "new_parent_id": ..., "stale_blob_node_id": ...}
    raise NotImplementedError("scenario fixtures need the write path from Schritt 3b")


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
    node_id = fixtures["node_id"]
    base_revision_id = fixtures["base_revision_id"]
    set_fault(fault_file, "revision_write_before_check:barrier:2")
    try:
        results = run_concurrent(
            lambda: perform_new_revision(
                base_url, api_key, node_id, base_revision_id, "a" * 64
            ),
            lambda: perform_new_revision(
                base_url, api_key, node_id, base_revision_id, "b" * 64
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
    node_id = fixtures["node_id"]
    node_b_id = fixtures["node_b_id"]
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
    node_id = fixtures["node_id"]
    new_parent_id = fixtures["new_parent_id"]
    set_fault(fault_file, "node_rename_before_check:barrier:2")
    try:
        results = run_concurrent(
            lambda: perform_move(base_url, api_key, node_id, new_parent_id),
            lambda: perform_delete(base_url, api_key, node_id),
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
    node_id = fixtures["node_id"]
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


# --------------------------------------------------------------------------
# A4 scenario (Konzept 16 "A4 Aufraeumjob")
# --------------------------------------------------------------------------


def scenario_cleanup_races_blob_reuse(base_url, api_key, fault_file, fixtures):
    """The cleanup cron runs between a writer finding an old blob to reuse
    (deduplication) and that writer's commit. Expectation (A4): the writer's
    new revision always references a blob that still exists on disk - the
    mark gets renewed on reuse, or the writer re-links after the cron won the
    race, per Konzept 5 "Schreiben". A regression here reproduces exactly the
    dangling reference the review found in `fm_proto/blobstore.py`."""
    stale_blob_node_id = fixtures["stale_blob_node_id"]
    set_fault(fault_file, "blob_write_after_dedup_found:barrier:2")
    try:
        results = run_concurrent(
            lambda: perform_new_revision(
                base_url, api_key, stale_blob_node_id, None, "c" * 64
            ),
            lambda: trigger_cleanup_cron(base_url, api_key),
        )
    finally:
        clear_fault(fault_file)
        clear_barrier_dirs(fault_file)

    writer_result = results[0]
    if not writer_result.ok:
        raise ScenarioFailed(
            f"writer must not fail because the cleanup job ran concurrently: "
            f"{writer_result.error}"
        )
    # TODO(schreibwege): once the revision is created, fetch its blob and
    # assert the underlying file exists on disk (the actual regression test
    # for A4 - the cleanup job must never delete a blob a concurrent writer
    # is about to reference).


SCENARIOS = {
    "same_new_name_twice": scenario_same_new_name_twice,
    "same_base_revision_twice": scenario_same_base_revision_twice,
    "rename_to_same_name": scenario_rename_to_same_name,
    "move_against_delete": scenario_move_against_delete,
    "lock_timeout_triggers_retry": scenario_lock_timeout_triggers_retry,
    "cleanup_races_blob_reuse": scenario_cleanup_races_blob_reuse,
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--api-key", required=True)
    parser.add_argument("--fault-file", required=True)
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

    try:
        fixtures = setup_fixtures(args.base_url, args.api_key)
    except NotImplementedError as exc:
        _logger.info("PENDING: %s", exc)
        return

    names = list(SCENARIOS) if args.scenario == "all" else [args.scenario]
    failures = []
    for name in names:
        _logger.info("--- %s ---", name)
        try:
            SCENARIOS[name](args.base_url, args.api_key, args.fault_file, fixtures)
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
