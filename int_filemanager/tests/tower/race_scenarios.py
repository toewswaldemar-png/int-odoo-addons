"""Race and crash tests with real processes against a running Odoo.

See README.md in this directory for prerequisites, the stage names the write
paths implement, and why this cannot be an Odoo TransactionCase. Never run it
against a live database.

Standard library only (Pillow for the JPEG test files): it runs in a helper
container without `requests`.
"""

import argparse
import base64
import glob
import hashlib
import http.client
import http.cookiejar
import json
import logging
import os
import re
import shutil
import subprocess
import threading
import time
import urllib.error
import urllib.parse
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
    """POST /json/2/<model>/<method> with a bearer API key.
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
# called over JSON-2 with a bearer API key. Content travels as base64, because
# JSON cannot carry binary data.
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


# The blob cleanup job is @api.autovacuum, with no HTTP trigger; the driver runs it
# in a second real process through `odoo shell` (see scenario_blob_gc_against_reuse).


def load_fixtures(fixtures_path):
    """Load the fixture ids written by bootstrap_fixtures.py.

    Every scenario has its own nodes, so the outcome of one race does not
    depend on how an earlier one ended.
    """
    with open(fixtures_path, encoding="utf-8") as f:
        return json.load(f)


# --------------------------------------------------------------------------
# Race scenarios. Every scenario takes the same
# (base_url, api_key, fault_file, fixtures) signature so main() can dispatch
# uniformly; each pulls the ids it needs out of `fixtures`.
# --------------------------------------------------------------------------


def scenario_same_new_name_twice(base_url, api_key, fault_file, fixtures):
    """Two racers create a node with the SAME new name under the same
    parent. Expectation: exactly one node survives with one revision -
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
    """Two racers save a new revision from the same base revision.

    Expectation: one wins, the other gets a base-revision conflict. The
    barrier sits before the row lock: after it, the lock already serializes
    the racers and both could never reach the barrier.
    """
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
    the same time. Expectation: one rename succeeds, the other is
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
    """One racer moves a file into a folder while the other trashes that folder.

    Expectation: whatever the order, no active node ends up below a trashed
    folder. Both racers meet after their checks and before their writes.
    """
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
    """One racer holds the row lock past the lock timeout; the other waits.

    Expectation: the waiting request times out, is retried, then sees the
    winner's revision and gets the base-revision conflict. The loser must have
    waited at least the timeout, otherwise the lock was never contended.
    """
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
    """The worker dies right after the node and revision rows were
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
    """The worker dies after the new revision row exists, before the
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
    """A crash in the middle of a rename and of a trash changes nothing
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


# --------------------------------------------------------------------------
# Big upload with an abort and a resume, in the browser's protocol: init_upload /
# finish_upload / upload_status over JSON-2, the chunks as raw bodies over a real login
# session with its CSRF token.
# --------------------------------------------------------------------------

_BLOCK = 1024 * 1024
CHUNK_BYTES = 4 * 1024 * 1024


def _pattern(seed, start, length):
    """Deterministic pseudo-random bytes [start, start+length) of an endless stream, so
    the expected hash of gigabytes needs no gigabytes of memory or disk on the
    client."""
    out = bytearray()
    index = start // _BLOCK
    skip = start % _BLOCK
    while len(out) < length:
        block = hashlib.shake_256(f"{seed}:{index}".encode()).digest(_BLOCK)
        out += block[skip:]
        skip = 0
        index += 1
    return bytes(out[:length])


def _pattern_sha256(seed, total):
    hasher = hashlib.sha256()
    for start in range(0, total, _BLOCK):
        hasher.update(_pattern(seed, start, min(_BLOCK, total - start)))
    return hasher.hexdigest()


def http_login(base_url, login, password):
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    html = opener.open(f"{base_url}/web/login", timeout=30).read().decode()
    csrf = re.search(r'name="csrf_token" value="(\w+)"', html).group(1)
    form = urllib.parse.urlencode(
        {"login": login, "password": password, "csrf_token": csrf, "redirect": ""}
    ).encode()
    opener.open(f"{base_url}/web/login", form, timeout=30)
    page = opener.open(f"{base_url}/odoo", timeout=30).read().decode()
    token = re.search(r'csrf_token: "(\w+)"', page)
    if not token:
        raise ScenarioFailed("login did not give a web client page with a CSRF token")
    return opener, jar, token.group(1)


def post_chunk(base_url, opener, csrf, upload_id, offset, data):
    query = urllib.parse.urlencode({"offset": offset, "csrf_token": csrf})
    req = urllib.request.Request(
        f"{base_url}/int_filemanager/v2/upload/{upload_id}/chunk?{query}",
        data=data,
        headers={"Content-Type": "application/octet-stream"},
        method="POST",
    )
    with opener.open(req, timeout=120) as resp:
        return json.loads(resp.read())


def send_cut_off_chunk(base_url, jar, csrf, upload_id, offset):
    """A client that dies in the middle of a chunk: the headers promise 4 MiB, one
    MiB arrives, the connection drops."""
    parsed = urllib.parse.urlparse(base_url)
    conn = http.client.HTTPConnection(parsed.hostname, parsed.port, timeout=30)
    query = urllib.parse.urlencode({"offset": offset, "csrf_token": csrf})
    conn.putrequest("POST", f"/int_filemanager/v2/upload/{upload_id}/chunk?{query}")
    conn.putheader("Content-Type", "application/octet-stream")
    conn.putheader("Content-Length", str(CHUNK_BYTES))
    conn.putheader("Cookie", "; ".join(f"{c.name}={c.value}" for c in jar))
    conn.endheaders()
    conn.send(b"\xff" * _BLOCK)
    conn.close()


def _upload_call(base_url, api_key, method, params):
    return json2_call(
        base_url, api_key, "int_filemanager.upload", method, params, timeout=120
    )


def scenario_upload_large_resume(base_url, api_key, fault_file, fixtures):
    """init -> ~40 % of the chunks -> one chunk cut off in the middle -> the client
    "restarts" (new login, init again with the SAME operation key, ask the server how
    much it really has) -> a chunk sent twice -> the rest -> finish. Above the
    threshold (256 MB) finish is asynchronous, so the job that finishes it runs in a
    second real process (`odoo shell`), like the cron would. Finally the bytes come
    back through the download route and must hash to what was sent."""
    shell_cmd = fixtures.get("_odoo_shell_cmd")
    if not shell_cmd:
        raise NotImplementedError("needs --odoo-shell-cmd (finishing job runs there)")
    total = int(fixtures.get("_upload_mb") or 300) * 1024 * 1024
    seed = f"race-upload-{time.monotonic_ns()}"
    key = f"race-upload-large-{seed}"
    name = f"{seed}.bin"
    expected_sha = _pattern_sha256(seed, total)
    _logger.info("uploading %d MiB, expected sha256 %s", total >> 20, expected_sha)

    init_params = {
        "target_parent_id": fixtures["parent_id"],
        "target_name": name,
        "target_node_id": False,
        "base_revision_id": False,
        "expected_size": total,
        "operation_key": key,
    }
    upload_id = _upload_call(base_url, api_key, "init_upload", init_params)["upload_id"]

    opener, jar, csrf = http_login(base_url, fixtures["login"], fixtures["password"])
    stop_at = (total * 4 // 10) // CHUNK_BYTES * CHUNK_BYTES
    offset = 0
    while offset < stop_at:
        data = _pattern(seed, offset, min(CHUNK_BYTES, total - offset))
        post_chunk(base_url, opener, csrf, upload_id, offset, data)
        offset += len(data)

    send_cut_off_chunk(base_url, jar, csrf, upload_id, offset)
    time.sleep(1)

    # The client is gone. A new one only knows the operation key and the file.
    opener, jar, csrf = http_login(base_url, fixtures["login"], fixtures["password"])
    again = _upload_call(base_url, api_key, "init_upload", init_params)
    if again["upload_id"] != upload_id:
        raise ScenarioFailed(f"init with the same key gave another upload: {again}")
    status = _upload_call(base_url, api_key, "upload_status", {"upload_id": upload_id})
    received = int(status["received_size"])
    _logger.info(
        "server has %d of %d bytes after the abort (cut-off chunk %s)",
        received,
        total,
        "kept its prefix" if received > stop_at else "dropped",
    )
    if received < stop_at or received > stop_at + _BLOCK:
        raise ScenarioFailed(f"unexpected received_size after the abort: {status}")

    # A chunk the server already has, sent again: harmless.
    if received > 0:
        redo_from = max(0, received - CHUNK_BYTES)
        redo = post_chunk(
            base_url,
            opener,
            csrf,
            upload_id,
            redo_from,
            _pattern(seed, redo_from, min(CHUNK_BYTES, received - redo_from)),
        )
        if int(redo["received_size"]) != received:
            raise ScenarioFailed(f"a repeated chunk changed the size: {redo}")

    offset = received
    while offset < total:
        data = _pattern(seed, offset, min(CHUNK_BYTES, total - offset))
        post_chunk(base_url, opener, csrf, upload_id, offset, data)
        offset += len(data)

    finish = _upload_call(
        base_url,
        api_key,
        "finish_upload",
        {"upload_id": upload_id, "operation_key": f"{key}-finish"},
    )
    if finish.get("state") == "processing":
        _run_odoo_shell(shell_cmd, _FINISH_SCRIPT.format(upload_id=upload_id))
    status = _upload_call(base_url, api_key, "upload_status", {"upload_id": upload_id})
    if status["state"] != "done":
        raise ScenarioFailed(f"the upload did not finish: {status}")
    result = status["result"]
    if result["sha256"] != expected_sha:
        raise ScenarioFailed(f"stored hash differs from what was sent: {result}")

    hasher = hashlib.sha256()
    length = 0
    with opener.open(
        f"{base_url}/int_filemanager/v2/download/{result['node_id']}", timeout=600
    ) as resp:
        while chunk := resp.read(_BLOCK):
            hasher.update(chunk)
            length += len(chunk)
    if length != total or hasher.hexdigest() != expected_sha:
        raise ScenarioFailed(f"the download is not what was uploaded: {length} bytes")
    _logger.info("uploaded and downloaded %d bytes, hashes match", length)


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


_FINISH_SCRIPT = """
import json
upload = env["int_filemanager.upload"].sudo().browse({upload_id})
env["int_filemanager.upload"].sudo()._finish_pending_one(upload)
env.cr.commit()
print("RESULT " + json.dumps({{"state": upload.state}}))
"""


def _run_odoo_shell(shell_cmd, script, extra_env=None, expect_death=False):
    """Run *script* in `odoo shell` (a real second process) and return the JSON
    it prints after its RESULT marker - odoo shell writes plenty of other noise.

    With ``expect_death`` the process is meant to be killed by a fault point: its
    exit code is returned instead of a result."""
    proc = subprocess.run(
        shell_cmd,
        input=script,
        capture_output=True,
        text=True,
        shell=True,
        check=False,
        timeout=180,
        env={**os.environ, **(extra_env or {})},
    )
    if expect_death:
        return proc.returncode
    for line in proc.stdout.splitlines():
        if line.startswith("RESULT "):
            return json.loads(line[len("RESULT ") :])
    raise ScenarioFailed(
        f"odoo shell printed no RESULT line (exit {proc.returncode}): "
        f"{proc.stdout[-500:]} {proc.stderr[-2500:]}"
    )


def scenario_blob_gc_against_reuse(base_url, api_key, fault_file, fixtures):
    """The cleanup job deletes a stale blob while a writer reuses its content.

    The writer is held right after finding the file on disk, the job runs to
    completion in its own process, then the writer continues. Expectation:
    the writer ends with a revision on an existing blob and an intact file.
    """
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


# --------------------------------------------------------------------------
# Derived files (thumbnails): the real queue in real processes against the real
# converter service (tools/fmconverter), with real JPEG files.
# --------------------------------------------------------------------------

_DERIVATIVE_FAULT = "/var/lib/odoo/fault_derivative.txt"
_CONVERT_LOG = "/var/lib/odoo/convert_log.txt"

_SET_URL_SCRIPT = """
env["ir.config_parameter"].sudo().set_param("int_filemanager.converter_url", {url!r})
env.cr.commit()
print("RESULT {{}}")
"""

_RUN_QUEUE_SCRIPT = """
import contextlib, json, os
from odoo.addons.int_filemanager import converter_client

real = converter_client.convert

@contextlib.contextmanager
def logged(url, sha256, kind, spec, timeout):
    with open({log!r}, "a") as f:
        f.write(str(os.getpid()) + " " + sha256 + "\\n")
    with real(url, sha256, kind, spec, timeout) as result:
        yield result

converter_client.convert = logged
env["int_filemanager.derivative"].sudo()._cron_run()
print("RESULT {{}}")
"""

_STATE_SCRIPT = """
import json, os
from odoo.addons.int_filemanager import blobstore
shas = {shas!r}
out = {{}}
for sha in shas:
    blob = env["int_filemanager.blob"].sudo().search([("sha256", "=", sha)])
    jobs = env["int_filemanager.derivative"].sudo().search(
        [("source_blob_id", "in", blob.ids)])
    entry = {{"jobs": len(jobs), "state": jobs.state if len(jobs) == 1 else None}}
    if len(jobs) == 1 and jobs.derived_blob_id:
        derived = jobs.derived_blob_id
        path = blobstore.blob_path(env, derived.sha256)
        with open(path, "rb") as f:
            head = f.read(3)
        entry["file_ok"] = (
            blobstore.hash_file(path)[0] == derived.sha256
            and head == b"\\xff\\xd8\\xff"
            and derived.size < 60000
        )
        entry["derived_rows"] = env["int_filemanager.blob"].sudo().search_count(
            [("sha256", "=", derived.sha256)])
    out[sha] = entry
print("RESULT " + json.dumps(out))
"""

_EXPIRE_LEASES_SCRIPT = """
env.cr.execute(
    "UPDATE int_filemanager_derivative d SET lease_until = '2000-01-01'"
    " FROM int_filemanager_blob b WHERE b.id = d.source_blob_id"
    " AND d.state = 'running' AND b.sha256 IN %s", [tuple({shas!r})]
)
n = env.cr.rowcount
env.cr.commit()
print("RESULT " + str(n))
"""


def _jpeg(seed):
    import io

    from PIL import Image

    # Distinct bytes per seed: size and colour both depend on it (a JPEG side < 65536).
    image = Image.new(
        "RGB", (900 + seed % 500, 700), (seed * 37 % 256, seed // 7 % 256, 160)
    )
    buf = io.BytesIO()
    image.save(buf, "JPEG")
    return buf.getvalue()


def _make_photos(base_url, api_key, fixtures, tag, count):
    """Create ``count`` distinct JPEG files; return their blob hashes."""
    shas = []
    salt = int(time.monotonic() * 1000) % 100000
    for i in range(count):
        content = _jpeg(i + 1 + salt)
        perform_create_node(
            base_url,
            api_key,
            fixtures["parent_id"],
            f"race-{tag}-{i}-{time.monotonic_ns()}.jpg",
            content,
        )
        shas.append(hashlib.sha256(content).hexdigest())
    return shas


def _deriv_setup(fixtures, url=None):
    shell_cmd = fixtures.get("_odoo_shell_cmd")
    converter_url = url or fixtures.get("_converter_url")
    if not shell_cmd or not fixtures.get("_converter_url"):
        raise NotImplementedError("needs --odoo-shell-cmd and --converter-url")
    if os.path.exists(_CONVERT_LOG):
        os.remove(_CONVERT_LOG)
    _run_odoo_shell(shell_cmd, _SET_URL_SCRIPT.format(url=converter_url))
    return shell_cmd


def _convert_log():
    if not os.path.exists(_CONVERT_LOG):
        return []
    with open(_CONVERT_LOG, encoding="utf-8") as f:
        return [line.split() for line in f if line.strip()]


def scenario_derivative_end_to_end(base_url, api_key, fault_file, fixtures):
    """Photos are queued, converted by the real service and stored as intact blobs."""
    shell_cmd = _deriv_setup(fixtures)
    shas = _make_photos(base_url, api_key, fixtures, "e2e", 2)
    _run_odoo_shell(shell_cmd, _RUN_QUEUE_SCRIPT.format(log=_CONVERT_LOG))
    state = _run_odoo_shell(shell_cmd, _STATE_SCRIPT.format(shas=shas))
    for sha in shas:
        got = state[sha]
        if got != {"jobs": 1, "state": "done", "file_ok": True, "derived_rows": 1}:
            raise ScenarioFailed(f"{sha[:8]} not converted correctly: {got}")


_TRANSACTION_PROBE_SCRIPT = """
import contextlib, json
from odoo import sql_db
from odoo.addons.int_filemanager import converter_client

real = converter_client.convert
seen = []
own_pid = env.cr._cnx.get_backend_pid()

@contextlib.contextmanager
def probing(url, sha256, kind, spec, timeout):
    # From a second connection: what does the worker's own connection do right now?
    with sql_db.db_connect(env.cr.dbname).cursor() as cr:
        cr.execute("SELECT state FROM pg_stat_activity WHERE pid = %s", [own_pid])
        seen.append(cr.fetchone()[0])
    with real(url, sha256, kind, spec, timeout) as result:
        yield result

converter_client.convert = probing
env["int_filemanager.derivative"].sudo()._cron_run()
print("RESULT " + json.dumps(seen))
"""


def scenario_derivative_idle_while_converting(base_url, api_key, fault_file, fixtures):
    """While the converter works, the worker holds no open database transaction.

    An open transaction would keep its snapshot (and so old row versions) alive for
    as long as a conversion takes.
    """
    shell_cmd = _deriv_setup(fixtures)
    _make_photos(base_url, api_key, fixtures, "notx", 2)
    seen = _run_odoo_shell(shell_cmd, _TRANSACTION_PROBE_SCRIPT)
    if not seen or set(seen) != {"idle"}:
        raise ScenarioFailed(f"the connection was not idle during the calls: {seen}")


def scenario_derivative_converter_down_then_up(base_url, api_key, fault_file, fixtures):
    """With the converter unreachable the jobs stay open without an attempt; when it
    is back they are done."""
    shell_cmd = _deriv_setup(fixtures, url="http://127.0.0.1:9")
    shas = _make_photos(base_url, api_key, fixtures, "down", 2)
    _run_odoo_shell(shell_cmd, _RUN_QUEUE_SCRIPT.format(log=_CONVERT_LOG))
    state = _run_odoo_shell(shell_cmd, _STATE_SCRIPT.format(shas=shas))
    if any(state[sha] != {"jobs": 1, "state": "pending"} for sha in shas):
        raise ScenarioFailed(f"jobs did not stay open: {state}")
    _run_odoo_shell(shell_cmd, _SET_URL_SCRIPT.format(url=fixtures["_converter_url"]))
    _run_odoo_shell(shell_cmd, _RUN_QUEUE_SCRIPT.format(log=_CONVERT_LOG))
    state = _run_odoo_shell(shell_cmd, _STATE_SCRIPT.format(shas=shas))
    if any(state[sha].get("state") != "done" for sha in shas):
        raise ScenarioFailed(f"jobs were not done once the converter was back: {state}")


def scenario_crash_derivative_after_link(base_url, api_key, fault_file, fixtures):
    """The worker dies after linking the result file, before the row is committed.

    Nothing is lost and nothing is half done: the job is still marked as running,
    becomes free again when its lease has run out, and then ends with exactly one
    intact result.
    """
    shell_cmd = _deriv_setup(fixtures)
    shas = _make_photos(base_url, api_key, fixtures, "crash", 1)
    set_fault(_DERIVATIVE_FAULT, "derivative_after_link:exit")
    try:
        code = _run_odoo_shell(
            shell_cmd,
            _RUN_QUEUE_SCRIPT.format(log=_CONVERT_LOG),
            extra_env={"INT_FILEMANAGER_FAULT_FILE": _DERIVATIVE_FAULT},
            expect_death=True,
        )
    finally:
        clear_fault(_DERIVATIVE_FAULT)
    if code != 137:
        raise ScenarioFailed(f"the worker was expected to die (137), exit code {code}")
    state = _run_odoo_shell(shell_cmd, _STATE_SCRIPT.format(shas=shas))
    if state[shas[0]] != {"jobs": 1, "state": "running"}:
        raise ScenarioFailed(f"a dead worker must leave a running job: {state}")
    if _run_odoo_shell(shell_cmd, _EXPIRE_LEASES_SCRIPT.format(shas=shas)) != 1:
        raise ScenarioFailed("expected exactly one running job to expire")
    _run_odoo_shell(shell_cmd, _RUN_QUEUE_SCRIPT.format(log=_CONVERT_LOG))
    state = _run_odoo_shell(shell_cmd, _STATE_SCRIPT.format(shas=shas))
    if state[shas[0]] != {
        "jobs": 1,
        "state": "done",
        "file_ok": True,
        "derived_rows": 1,
    }:
        raise ScenarioFailed(f"the job did not end intact after the crash: {state}")


def scenario_two_workers_take_different_jobs(base_url, api_key, fault_file, fixtures):
    """Two queue runs overlap (held at the barrier right after taking their jobs).

    Expectation: no job is converted twice, both runs did some of the work, and
    every job ends done.
    """
    shell_cmd = _deriv_setup(fixtures)
    shas = _make_photos(base_url, api_key, fixtures, "two", 6)
    set_fault(_DERIVATIVE_FAULT, "derivative_after_claim:barrier:2:150")
    env = {"INT_FILEMANAGER_FAULT_FILE": _DERIVATIVE_FAULT}
    try:

        def queue_run(delay=0):
            # Two `odoo shell` processes starting at the very same moment collide in the
            # old module's rule rebuild at registry load; the barrier does the overlap.
            time.sleep(delay)
            try:
                return _run_odoo_shell(
                    shell_cmd, _RUN_QUEUE_SCRIPT.format(log=_CONVERT_LOG), env
                )
            except ScenarioFailed as exc:
                # run_concurrent reports OSError as a result of the racer.
                raise OSError(str(exc)) from exc

        results = run_concurrent(queue_run, lambda: queue_run(delay=15))
    finally:
        clear_fault(_DERIVATIVE_FAULT)
        clear_barrier_dirs(_DERIVATIVE_FAULT)
    if not all(r.ok for r in results):
        raise ScenarioFailed(f"a queue run failed: {[r.error for r in results]}")
    log = [entry for entry in _convert_log() if entry[1] in shas]
    per_job = {}
    for _pid, sha in log:
        per_job[sha] = per_job.get(sha, 0) + 1
    if sorted(per_job) != sorted(shas) or set(per_job.values()) != {1}:
        raise ScenarioFailed(f"jobs must be converted exactly once: {per_job}")
    if len({pid for pid, _sha in log}) != 2:
        raise ScenarioFailed(f"both runs should have worked: {log}")
    state = _run_odoo_shell(shell_cmd, _STATE_SCRIPT.format(shas=shas))
    if any(state[sha].get("state") != "done" for sha in shas):
        raise ScenarioFailed(f"not every job is done: {state}")


SCENARIOS = {
    "same_new_name_twice": scenario_same_new_name_twice,
    "same_base_revision_twice": scenario_same_base_revision_twice,
    "rename_to_same_name": scenario_rename_to_same_name,
    "move_against_delete": scenario_move_against_delete,
    "lock_timeout_triggers_retry": scenario_lock_timeout_triggers_retry,
    "blob_gc_against_reuse": scenario_blob_gc_against_reuse,
    "upload_large_resume": scenario_upload_large_resume,
    "crash_create_file": scenario_crash_create_file,
    "crash_new_revision": scenario_crash_new_revision,
    "crash_rename_and_trash": scenario_crash_rename_and_trash,
    "derivative_end_to_end": scenario_derivative_end_to_end,
    "derivative_idle_while_converting": scenario_derivative_idle_while_converting,
    "derivative_converter_down_then_up": scenario_derivative_converter_down_then_up,
    "crash_derivative_after_link": scenario_crash_derivative_after_link,
    "two_workers_take_different_jobs": scenario_two_workers_take_different_jobs,
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
    parser.add_argument(
        "--converter-url",
        help="base URL of the converter service (tools/fmconverter); the derivative"
        " scenarios stay PENDING without it.",
    )
    parser.add_argument(
        "--upload-mb",
        type=int,
        default=300,
        help="size of the file upload_large_resume sends; above 256 the finish is"
        " asynchronous (300 by default, 3072 for the step 4 acceptance run)",
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
    fixtures["_upload_mb"] = args.upload_mb
    fixtures["_converter_url"] = args.converter_url

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
