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
import subprocess
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
    def __init__(self, value=None, error=None, elapsed=0.0):
        self.value = value
        self.error = error
        self.elapsed = elapsed

    def __repr__(self):
        detail = self.error if self.error is not None else self.value
        return f"CallResult({detail!r}, {self.elapsed:.1f}s)"

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
        started = time.monotonic()
        try:
            results[i] = CallResult(value=fn())
        except urllib.error.HTTPError as exc:
            results[i] = CallResult(error=exc)
        except OSError as exc:
            # A genuine network/read timeout (json2_call's own 30s), not an HTTP
            # error response - e.g. a barrier that never got satisfied because of
            # a scenario design bug (found this way: see
            # scenario_same_base_revision_twice's docstring). Surfaced as a result
            # instead of silently leaving results[i] None, which used to turn into
            # a confusing AttributeError in the scenario's own assertions.
            results[i] = CallResult(error=exc)
        results[i].elapsed = time.monotonic() - started

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


def perform_create_node(
    base_url,
    api_key,
    parent_id,
    name,
    content=b"race",
    timeout=30,
    operation_key=None,
):
    return json2_call(
        base_url,
        api_key,
        "int_filemanager.node",
        "create_file",
        {
            "parent_id": parent_id,
            "name": name,
            "content": _b64(content),
            "operation_key": operation_key
            or f"race-create-{name}-{time.monotonic_ns()}",
        },
        timeout=timeout,
    )


def perform_new_revision(
    base_url, api_key, node_id, base_revision_id, content, operation_key=None
):
    return json2_call(
        base_url,
        api_key,
        "int_filemanager.node",
        "create_new_revision",
        {
            "node_id": node_id,
            "base_revision_id": base_revision_id,
            "content": _b64(content),
            "operation_key": operation_key
            or f"race-revise-{node_id}-{time.monotonic_ns()}",
        },
    )


def perform_rename(
    base_url, api_key, node_id, new_name, new_parent_id=False, operation_key=None
):
    return json2_call(
        base_url,
        api_key,
        "int_filemanager.node",
        "rename_or_move",
        {
            "node_id": node_id,
            "new_parent_id": new_parent_id,
            "new_name": new_name,
            "operation_key": operation_key
            or f"race-rename-{node_id}-{time.monotonic_ns()}",
        },
    )


def perform_move(base_url, api_key, node_id, new_parent_id, new_name):
    return perform_rename(base_url, api_key, node_id, new_name, new_parent_id)


def perform_trash(base_url, api_key, node_id, operation_key=None):
    return json2_call(
        base_url,
        api_key,
        "int_filemanager.node",
        "trash",
        {
            "node_id": node_id,
            "operation_key": operation_key
            or f"race-trash-{node_id}-{time.monotonic_ns()}",
        },
    )


# A4's cleanup job is @api.autovacuum: private, and no ir.cron record of its own, so
# there is no HTTP trigger for it (and adding one only for tests would be
# test-only production code). The driver runs it as what it really is - a SECOND
# real OS process, `odoo shell` calling the method (see scenario_blob_gc_against_reuse).


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
    other gets a base-revision conflict - never a silently dropped edit.

    Barrier on node_lock_before_wait, not revision_write_before_check: the
    latter fires AFTER `SELECT ... FOR UPDATE` succeeds, which Postgres
    itself already serializes on this node's row - a barrier there can
    never be satisfied by both racers at once (found empirically on Tower:
    both threads hung for the full 30s and then both timed out, since
    racer B's own lock attempt blocks on racer A, who in turn is parked at
    a barrier waiting for an arrival that structurally cannot happen).
    node_lock_before_wait fires BEFORE either racer attempts the row lock,
    so both reach it freely; only afterwards does Postgres serialize them,
    which is the real thing being tested."""
    node_id = fixtures["revision_node_id"]
    base_revision_id = fixtures["revision_base_revision_id"]
    set_fault(fault_file, "node_lock_before_wait:barrier:2")
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


def _is_defined_error(result):
    """A racer that lost must lose with a domain error the client can act on
    (UserError -> 4xx), never a server crash (5xx) or a network timeout."""
    return (
        isinstance(result.error, urllib.error.HTTPError)
        and 400 <= result.error.code < 500
    )


def scenario_move_against_delete(base_url, api_key, fault_file, fixtures):
    """One racer moves a file INTO a folder while the other trashes that folder.
    Odoo runs REPEATABLE READ, so without an explicit shared write the two are a
    write skew: trash() decided its subtree from a snapshot that cannot see the
    newcomer, the move decided the folder was active from one that cannot see
    the trash. Expectation: whatever the order, no ACTIVE node ends up under a
    trashed folder.

    Both racers meet at node_tree_before_write (after their own checks, before
    their writes), so the interleaving is forced instead of hoped for."""
    file_id = fixtures["move_node_id"]
    folder_id = fixtures["move_new_parent_id"]
    set_fault(fault_file, "node_tree_before_write:barrier:2")
    try:
        results = run_concurrent(
            lambda: perform_move(base_url, api_key, file_id, folder_id, "moved.txt"),
            lambda: perform_trash(base_url, api_key, folder_id),
        )
    finally:
        clear_fault(fault_file)
        clear_barrier_dirs(fault_file)

    for result in results:
        if not result.ok and not _is_defined_error(result):
            raise ScenarioFailed(
                f"racer crashed instead of a defined outcome: {results}"
            )

    state = {
        row["id"]: row
        for row in json2_call(
            base_url,
            api_key,
            "int_filemanager.node",
            "search_read",
            {
                "domain": [["id", "in", [file_id, folder_id]]],
                "fields": ["active", "parent_id"],
                "context": {"active_test": False},
            },
        )
    }
    file_row, folder_row = state[file_id], state[folder_id]
    file_in_folder = (
        bool(file_row["parent_id"]) and file_row["parent_id"][0] == folder_id
    )
    if folder_row["active"]:
        raise ScenarioFailed(f"the trash did not take effect: {state} / {results}")
    if file_row["active"] and file_in_folder:
        raise ScenarioFailed(
            f"active file under a trashed folder (write skew): {state} / {results}"
        )


def scenario_lock_timeout_triggers_retry(base_url, api_key, fault_file, fixtures):
    """One racer HOLDS the row lock past `lock_timeout` (5 s) while the other
    saves a new revision from the same base. Expectation (A3, Konzept 6): the
    waiting racer is not left hanging and does not overwrite anything - its lock
    wait ends in LockNotAvailable after the 5 s timeout, retrying() runs the
    request again, and by then it sees the winner's revision and gets the
    base-revision conflict. So: exactly one success, one defined error, and the
    loser waited for at least the lock timeout (otherwise the lock was never
    contended and this proves nothing)."""
    node_id = fixtures["lock_node_id"]
    base_revision_id = fixtures["lock_base_revision_id"]
    lock_timeout_s = 5
    set_fault(fault_file, f"node_lock_acquired:hold:{lock_timeout_s + 3}")
    try:
        results = run_concurrent(
            lambda: perform_new_revision(
                base_url, api_key, node_id, base_revision_id, b"lock-racer-a"
            ),
            lambda: perform_new_revision(
                base_url, api_key, node_id, base_revision_id, b"lock-racer-b"
            ),
        )
    finally:
        clear_fault(fault_file)
        clear_barrier_dirs(fault_file)

    oks = [r for r in results if r.ok]
    errs = [r for r in results if not r.ok]
    if len(oks) != 1 or len(errs) != 1:
        raise ScenarioFailed(f"expected one winner and one loser, got {results}")
    if not _is_defined_error(errs[0]):
        raise ScenarioFailed(f"the loser did not get a defined conflict: {results}")
    if errs[0].elapsed < lock_timeout_s - 0.5:
        raise ScenarioFailed(
            f"the loser returned after {errs[0].elapsed:.1f}s, before the"
            f" {lock_timeout_s}s lock timeout - the lock was never contended: {results}"
        )
    if max(r.elapsed for r in results) > 30:
        raise ScenarioFailed(f"a racer needed more than 30s: {results}")


def _search_read(base_url, api_key, model, domain, fields):
    return json2_call(
        base_url,
        api_key,
        model,
        "search_read",
        {
            "domain": domain,
            "fields": fields,
            "context": {"active_test": False},
        },
    )


def _crash_then_retry(fault_file, stage, call):
    """Arm `<stage>:exit` (os._exit(137) in the worker, no cleanup - the real
    thing, not an exception), run *call* with a fixed operation key, and
    return once the client saw the connection die. Then disarm the fault."""
    set_fault(fault_file, f"{stage}:exit")
    try:
        try:
            call()
        except OSError:
            return  # URLError/RemoteDisconnected/timeout: the worker really died
        raise ScenarioFailed(f"the request survived a crash at {stage}")
    finally:
        clear_fault(fault_file)


def scenario_crash_create_file(base_url, api_key, fault_file, fixtures):
    """I3/I9: the worker dies right after the node and revision rows were
    written but before the commit. Nothing may be visible afterwards (one
    transaction, all or nothing), and repeating the request with the SAME
    operation key must give exactly one node - also when repeated a third time."""
    parent_id = fixtures["parent_id"]
    name = "race-crash-create.txt"
    key = "race-crash-create-op"

    _crash_then_retry(
        fault_file,
        "node_create_after_insert",
        lambda: perform_create_node(
            base_url, api_key, parent_id, name, operation_key=key
        ),
    )
    found = _search_read(
        base_url, api_key, "int_filemanager.node", [["name", "=", name]], ["id"]
    )
    if found:
        raise ScenarioFailed(f"a crashed create left a node behind: {found}")

    first = perform_create_node(base_url, api_key, parent_id, name, operation_key=key)
    again = perform_create_node(base_url, api_key, parent_id, name, operation_key=key)
    found = _search_read(
        base_url, api_key, "int_filemanager.node", [["name", "=", name]], ["id"]
    )
    if len(found) != 1 or first != again:
        raise ScenarioFailed(f"retry after a crash is not exactly-once: {found}")


def scenario_crash_new_revision(base_url, api_key, fault_file, fixtures):
    """I3/I6/I9: the worker dies after the new revision row exists, before the
    commit. The node must still point at its old revision with no new one
    added; the retry with the same key then adds exactly one."""
    parent_id = fixtures["parent_id"]
    seed = perform_create_node(base_url, api_key, parent_id, "race-crash-rev.txt")
    node_id, base_revision_id = seed["node_id"], seed["revision_id"]
    key = "race-crash-revision-op"

    _crash_then_retry(
        fault_file,
        "revision_write_after_insert",
        lambda: perform_new_revision(
            base_url, api_key, node_id, base_revision_id, b"new content", key
        ),
    )
    node = _search_read(
        base_url,
        api_key,
        "int_filemanager.node",
        [["id", "=", node_id]],
        ["current_revision_id"],
    )[0]
    revisions = _search_read(
        base_url,
        api_key,
        "int_filemanager.revision",
        [["node_id", "=", node_id]],
        ["id"],
    )
    if node["current_revision_id"][0] != base_revision_id or len(revisions) != 1:
        raise ScenarioFailed(f"a crashed revision left traces: {node} / {revisions}")

    perform_new_revision(
        base_url, api_key, node_id, base_revision_id, b"new content", key
    )
    revisions = _search_read(
        base_url,
        api_key,
        "int_filemanager.revision",
        [["node_id", "=", node_id]],
        ["id"],
    )
    if len(revisions) != 2:
        raise ScenarioFailed(f"expected exactly two revisions after retry: {revisions}")


def scenario_crash_rename_and_trash(base_url, api_key, fault_file, fixtures):
    """I9: a crash in the middle of a rename and of a trash changes nothing
    (the row lock the dead worker held is released with its connection, so
    the retry does not hang), and the retries then go through."""
    parent_id = fixtures["parent_id"]
    seed = perform_create_node(base_url, api_key, parent_id, "race-crash-tree.txt")
    node_id = seed["node_id"]

    _crash_then_retry(
        fault_file,
        "node_rename_before_check",
        lambda: perform_rename(
            base_url,
            api_key,
            node_id,
            "race-crash-tree-renamed.txt",
            operation_key="k1",
        ),
    )
    row = _search_read(
        base_url, api_key, "int_filemanager.node", [["id", "=", node_id]], ["name"]
    )[0]
    if row["name"] != "race-crash-tree.txt":
        raise ScenarioFailed(f"a crashed rename changed the name: {row}")
    perform_rename(
        base_url, api_key, node_id, "race-crash-tree-renamed.txt", operation_key="k1"
    )

    _crash_then_retry(
        fault_file,
        "node_tree_before_write",
        lambda: perform_trash(base_url, api_key, node_id, operation_key="k2"),
    )
    row = _search_read(
        base_url, api_key, "int_filemanager.node", [["id", "=", node_id]], ["active"]
    )[0]
    if not row["active"]:
        raise ScenarioFailed(f"a crashed trash deactivated the node: {row}")
    perform_trash(base_url, api_key, node_id, operation_key="k2")
    row = _search_read(
        base_url, api_key, "int_filemanager.node", [["id", "=", node_id]], ["active"]
    )[0]
    if row["active"]:
        raise ScenarioFailed(f"the retried trash did not take effect: {row}")


_GC_SCRIPT = """
import json
sha256 = {sha256!r}
Blob = env["int_filemanager.blob"].sudo()
before = Blob.search_count([("sha256", "=", sha256)])
Blob._gc_blobs()
env.cr.commit()
env.invalidate_all()
after = Blob.search_count([("sha256", "=", sha256)])
print("RESULT " + json.dumps({{"row_before": before, "row_after": after}}))
"""

_VERIFY_SCRIPT = """
import json, os
from odoo.addons.int_filemanager import blobstore
sha256 = {sha256!r}
blob = env["int_filemanager.blob"].sudo().search([("sha256", "=", sha256)])
path = blobstore.blob_path(env, sha256)
file_ok = os.path.exists(path) and blobstore.hash_file(path)[0] == sha256
print("RESULT " + json.dumps({{
    "blob_rows": len(blob),
    "revisions": len(blob.revision_ids),
    "file_ok": file_ok,
}}))
"""


def _run_odoo_shell(shell_cmd, script):
    """Run *script* in `odoo shell` (a real second process) and return the JSON
    it prints after its RESULT marker - odoo shell writes plenty of other noise."""
    proc = subprocess.run(
        shell_cmd,
        input=script,
        capture_output=True,
        text=True,
        shell=True,
        check=False,
        timeout=180,
    )
    for line in proc.stdout.splitlines():
        if line.startswith("RESULT "):
            return json.loads(line[len("RESULT ") :])
    raise ScenarioFailed(
        f"odoo shell printed no RESULT line (exit {proc.returncode}): "
        f"{proc.stdout[-500:]} {proc.stderr[-500:]}"
    )


def scenario_blob_gc_against_reuse(base_url, api_key, fault_file, fixtures):
    """A4: the cleanup job deletes a stale blob row while a writer has just
    decided to REUSE that very content. Expectation: the writer still ends with a
    live revision on a live blob row and an intact file - nothing the writer
    committed points at a blob the job took away.

    The writer is parked right after it found the file already on disk
    (blob_write_after_dedup_found, hold mode) - the claim of the fault file is the
    signal that it is parked. Only then does the job run, in its own process, to
    completion. Only then is the writer released."""
    shell_cmd = fixtures.get("_odoo_shell_cmd")
    if not shell_cmd:
        raise NotImplementedError("needs --odoo-shell-cmd (second real process)")
    sha256 = fixtures["a4_sha256"]
    content = base64.b64decode(fixtures["a4_content_b64"])
    release = f"{fault_file}.release.blob_write_after_dedup_found"
    if os.path.exists(release):
        os.remove(release)
    set_fault(fault_file, "blob_write_after_dedup_found:hold:120")

    outcome = {}

    def writer():
        try:
            outcome["value"] = perform_create_node(
                base_url,
                api_key,
                fixtures["parent_id"],
                "race-a4-writer.txt",
                content,
                timeout=180,
            )
        except (urllib.error.HTTPError, OSError) as exc:
            outcome["error"] = exc

    thread = threading.Thread(target=writer)
    thread.start()
    try:
        deadline = time.monotonic() + 60
        while os.path.exists(fault_file):
            if time.monotonic() > deadline:
                raise ScenarioFailed("the writer never reached the dedup stage")
            time.sleep(0.1)
        gc = _run_odoo_shell(shell_cmd, _GC_SCRIPT.format(sha256=sha256))
    finally:
        open(release, "w", encoding="utf-8").close()
        thread.join(timeout=180)
        clear_fault(fault_file)
        if os.path.exists(release):
            os.remove(release)

    if gc["row_before"] != 1 or gc["row_after"] != 0:
        raise ScenarioFailed(
            f"the job did not remove the stale row while the writer was parked - the"
            f" interleaving was not exercised: {gc}"
        )
    if "value" not in outcome:
        raise ScenarioFailed(f"the writer failed: {outcome}")
    verify = _run_odoo_shell(shell_cmd, _VERIFY_SCRIPT.format(sha256=sha256))
    if verify != {"blob_rows": 1, "revisions": 1, "file_ok": True}:
        raise ScenarioFailed(f"the reused blob did not survive intact: {verify}")


SCENARIOS = {
    "same_new_name_twice": scenario_same_new_name_twice,
    "same_base_revision_twice": scenario_same_base_revision_twice,
    "rename_to_same_name": scenario_rename_to_same_name,
    "move_against_delete": scenario_move_against_delete,
    "lock_timeout_triggers_retry": scenario_lock_timeout_triggers_retry,
    "blob_gc_against_reuse": scenario_blob_gc_against_reuse,
    "crash_create_file": scenario_crash_create_file,
    "crash_new_revision": scenario_crash_new_revision,
    "crash_rename_and_trash": scenario_crash_rename_and_trash,
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
    parser.add_argument(
        "--odoo-shell-cmd",
        help="shell command that starts `odoo shell` against the SAME database (script"
        " on stdin); needed for blob_gc_against_reuse, which runs the cleanup job in"
        " its own process. The scenario stays PENDING without it.",
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
    fixtures["_odoo_shell_cmd"] = args.odoo_shell_cmd

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
