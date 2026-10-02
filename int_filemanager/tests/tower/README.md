# A3/A4 real-process tests

Not Odoo tests. `TransactionCase` never commits and runs no post-commit hooks (see the
write-path tests), so it cannot see a real name/lock race or a real cleanup cron running against a
committed row. These scripts drive a REAL, running Odoo instance on the Tower test
environment instead - same idea as the 1.15.0 durchstich tests
and the earlier `fm_proto` prototype tests. Deliberately outside
`int_filemanager/tests/__init__.py`: `pre-commit` and `tools/v2check/v2check.sh` still
lint this code, but `odoo-bin --test-tags` never collects it, and it is only ever run by
hand against `fmtest_pg`.

## Status: all scenarios verified for real on Tower (2026-09-28)

`race_scenarios.py` drives the race and crash scenarios over real
`/json/2/int_filemanager.node/<method>` calls against a live `workers=2` instance.
`tools/v2check/race.sh` builds that instance from scratch, runs everything and tears it
down again (about 1.5 minutes). Result:

- `same_new_name_twice`, `same_base_revision_twice`, `rename_to_same_name` - **pass**,
  forced overlap via the barrier, real HTTP requests. The first real run also caught a
  real production bug (not a race): `create_new_revision`'s dedup check read the blob's
  own field without `.sudo()`, which every TransactionCase test missed because `setUp()`
  had already warmed that transaction's shared field cache - see
  `test_dedup_check_works_without_a_warm_cache` in `test_v2_write_paths.py`.
- `lock_timeout_triggers_retry` - **pass**. Uses the fault-file mode `hold:<seconds>`
  (`fault.py`): the first racer to reach `node_lock_acquired` claims the spec and sits
  on its row lock for 8 s, longer than the 5 s `lock_timeout`. The other racer's
  `SELECT ... FOR UPDATE` then really fails with LockNotAvailable (server log:
  `LOCK_NOT_AVAILABLE, 4 tries left`), `retrying()` runs the request again, and the
  retry sees the winner's revision and gets the base-revision conflict. The scenario
  checks: one winner, one defined 4xx error, and the loser waited at least the lock
  timeout.
- `move_against_delete` - **pass**, and **red before its fix**: moving a file into a
  folder while that folder is trashed was a write skew under REPEATABLE READ (trash
  decided its subtree from a snapshot that cannot see the newcomer, the move decided the
  folder was active from a snapshot that cannot see the trash) and ended with an ACTIVE
  file under a trashed folder. Fix: every operation that puts something under a folder
  (`rename_or_move`, `create_file`, `copy_node`, `finish_upload`, `restore`) first runs
  `_touch_active_parent()` - one `UPDATE ... WHERE id = %s AND active` on the folder
  row - so it conflicts with trash's own write of that row (serialization error -> retry
  -> the retry sees the trash and rejects). Both racers meet at the new stage
  `node_tree_before_write`, which `trash()`, `restore()` and `rename_or_move()` call.
- `blob_gc_against_reuse` (A4) - **pass**, needs `--odoo-shell-cmd`. The cleanup job is
  `@api.autovacuum` (private, no HTTP trigger, and no test-only endpoint is added for
  it), so the driver runs it as what it is: a SECOND real OS process, `odoo shell`
  calling `_gc_blobs()`. A writer that has just found the stale blob's file on disk
  (`blob_write_after_dedup_found`) is parked with `hold` (its claim of the fault file is
  the signal that it is parked), the job runs to completion and removes the stale blob
  row, the writer is released via `<fault file>.release.<stage>`. Checked afterwards,
  again in a separate `odoo shell`: one blob row with one revision and an intact file
  with the right hash - and that the job really removed the row while the writer was
  parked (else the interleaving was never exercised). The writer's retry after the
  deleted row shows up in the log as a serialization failure. The same invariant is also
  covered deterministically in `test_v2_blobstore.py`.

- `crash_create_file`, `crash_new_revision`, `crash_rename_and_trash` - **pass** (Kern
  11, step 3: "I1-I6 and I9 also with an abort in the middle of the operation"). The
  fault file arms `<stage>:exit`: the worker `os._exit(137)`s inside the write path
  (after the rows were written, before the commit), the client sees the connection die,
  and the scenario checks that nothing is visible afterwards (no node, no extra
  revision, name and activity unchanged - one transaction, all or nothing) and that
  repeating the request with the SAME operation key then works exactly once. The dead
  worker's row lock is released with its connection, so the retry does not hang. Not
  covered yet: a crash in the middle of `finish_upload` / the upload cron (no fault
  points there).

The barrier mechanics themselves are covered for real (not simulated) processes by
`int_filemanager/tests/test_v2_fault.py::TestCrossProcessBarrier`.

Fixture ids (a scope, a write group, a writer + API key, and one dedicated node per
scenario) come from `bootstrap_fixtures.py` in this same directory, run once via
`odoo shell` against the throwaway instance before `race_scenarios.py` - see "Running"
below. Each scenario gets its OWN node fixture, never shared, so running
`--scenario all` does not make a later scenario's outcome depend on how an earlier one's
race happened to resolve.

## The stage-name contract

The write path (and the cleanup cron) must call
`odoo.addons.int_filemanager.fault.fault_point("<stage>")` at exactly these points -
this is the single source of truth `race_scenarios.py` assumes:

| Stage                                | Where                                                                                                                  |
| ------------------------------------ | ---------------------------------------------------------------------------------------------------------------------- |
| `node_create_before_check`           | after the uniqueness/lock check, before `create` (write path, "create")                                     |
| `node_create_after_insert`           | after `create`, before commit                                                                                          |
| `revision_write_before_check`        | after the base-revision check, before writing a new revision                                                           |
| `revision_write_after_insert`        | after the new revision row exists, before commit                                                                       |
| `node_rename_before_check`           | after the target-name check, before `write` (rename/move)                                                              |
| `node_lock_before_wait`              | immediately before `SELECT ... FOR UPDATE` with `lock_timeout` set                                                     |
| `node_lock_acquired`                 | immediately after that `SELECT ... FOR UPDATE` returned - the row lock is held                                         |
| `node_tree_before_write`             | `trash`/`restore`/`rename_or_move`: checks done, before the write that changes where a node is or whether it is active |
| `blob_gc_after_dedup_check`          | cleanup cron: after it decides a blob is unreferenced, before it deletes the file                                      |
| `blob_gc_after_delete_before_commit` | cleanup cron: after the file is gone, before its transaction commits                                                   |
| `blob_write_after_dedup_found`       | writer: after it finds an existing blob to reuse, before it renews the mark / commits                                  |

## Prerequisites

- `fmtest_pg` running, a disposable database (never `fmv2`/`fmreal`/the live DB), module
  `int_filemanager` installed with `workers=2` (two real worker processes, per Konzept
  13/19 - a race needs two real OS processes, not one worker serving both requests in
  turn).
- Both workers see the same `INT_FILEMANAGER_FAULT_FILE` path on a filesystem they share
  (bind mount), so the barrier directory (`<fault file>.barrier.<stage>`) is visible to
  both.
- `int_filemanager.watcher_enabled` set to `false` before running `odoo shell` against
  this database (a shell session against the watcher DB starts a
  second watcher otherwise), matching the existing `fmshell.sh` Tower helper.
- Network access to the instance from wherever this script runs (matches the existing
  Tower helper-container setup used for 20.2 and `runv2.sh`).

## Running

```
tools/v2check/race.sh                            # everything
tools/v2check/race.sh --scenario move_against_delete
RACE_KEEP=1 tools/v2check/race.sh                # keep container/DB/directory for inspection
```

The script does by hand what is described here (Git Bash, from the repo): copy the
working tree to `/mnt/user/appdata/fmtest/v2race/` on Tower, install into a throwaway DB
`fmv2_race` on `fmtest_pg`, set `int_filemanager.watcher_enabled=false`, pipe
`bootstrap_fixtures.py` into `odoo shell` (its last stdout line is the fixture JSON),
start the server container `fmv2_race_odoo` (`workers=2`, `INT_FILEMANAGER_FAULT_FILE`
on the shared data mount) and run the driver in a helper container with the same mounts,
so the driver can also start `odoo shell` for A4 (`--odoo-shell-cmd`).

`bootstrap_fixtures.py` creates the scope, write group, writer user + API key, one
dedicated node per scenario via real `create_file()` calls and one stale blob for A4,
then prints their ids as JSON. Re-running scenarios against an already-used DB without a
fresh bootstrap first will spuriously fail on `same_new_name_twice` (the target name
from the previous run already exists) - use a fresh DB + fresh bootstrap for a clean
pass, not just a fresh fault file.

Each scenario resets the fault file to empty before returning, so a crash mid-scenario
can leave a stale barrier directory behind - `--cleanup` removes
`<fault-file>.barrier.*` without running anything.
