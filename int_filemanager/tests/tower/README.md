# A3/A4 real-process tests (Konzept 16, Pruefbericht A3/A4)

Not Odoo tests. `TransactionCase` never commits and runs no post-commit hooks (Konzept
16), so it cannot see a real name/lock race or a real cleanup cron running against a
committed row. These scripts drive a REAL, running Odoo instance on the Tower test
environment instead - same idea as the 1.15.0 durchstich tests
(`docs/int_filemanager_konzept_db_vorrang_2026-09-24.md`, 20.2) and the `fm_proto`
prototype tests (`docs/prototypes/fm2/tests/t_exit.py`). Deliberately outside
`int_filemanager/tests/__init__.py`: `pre-commit` and `tools/v2check/v2check.sh` still
lint this code, but `odoo-bin --test-tags` never collects it, and it is only ever run by
hand against `fmtest_pg`.

## Status: harness and scenarios wired to the real write paths

`race_scenarios.py` drives the 5 A3 scenarios from Konzept 16 over real
`/json/2/int_filemanager.node/<method>` calls (Kern 11 Schritt 3's write paths all exist
now). A4 ("Aufraeumjob") has no scenario here: the cleanup cron is `@api.autovacuum`, a
private method with no public/`ir.cron` trigger, so a live two-process reproduction
would need a dedicated admin trigger endpoint this module does not otherwise have. That
invariant (a reused blob must survive a concurrent cleanup run) is instead covered
deterministically in `int_filemanager/tests/test_v2_blobstore.py`, which can force the
exact ordering directly rather than hoping an HTTP race lands on it - see the comment
above `load_fixtures()` in `race_scenarios.py` for the full reasoning. The barrier
mechanics themselves are covered for real (not simulated) processes by
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

| Stage                                | Where                                                                                 |
| ------------------------------------ | ------------------------------------------------------------------------------------- |
| `node_create_before_check`           | after the uniqueness/lock check, before `create` (write path, Konzept 6 "Anlegen")    |
| `node_create_after_insert`           | after `create`, before commit                                                         |
| `revision_write_before_check`        | after the base-revision check, before writing a new revision                          |
| `revision_write_after_insert`        | after the new revision row exists, before commit                                      |
| `node_rename_before_check`           | after the target-name check, before `write` (rename/move)                             |
| `node_lock_before_wait`              | immediately before `SELECT ... FOR UPDATE` with `lock_timeout` set                    |
| `blob_gc_after_dedup_check`          | cleanup cron: after it decides a blob is unreferenced, before it deletes the file     |
| `blob_gc_after_delete_before_commit` | cleanup cron: after the file is gone, before its transaction commits                  |
| `blob_write_after_dedup_found`       | writer: after it finds an existing blob to reuse, before it renews the mark / commits |

## Prerequisites

- `fmtest_pg` running, a disposable database (never `fmv2`/`fmreal`/the live DB), module
  `int_filemanager` installed with `workers=2` (two real worker processes, per Konzept
  13/19 - a race needs two real OS processes, not one worker serving both requests in
  turn).
- Both workers see the same `INT_FILEMANAGER_FAULT_FILE` path on a filesystem they share
  (bind mount), so the barrier directory (`<fault file>.barrier.<stage>`) is visible to
  both.
- `int_filemanager.watcher_enabled` set to `false` before running `odoo shell` against
  this database (Konzept 19.5, N5 - a shell session against the watcher DB starts a
  second watcher otherwise), matching the existing `fmshell.sh` Tower helper.
- Network access to the instance from wherever this script runs (matches the existing
  Tower helper-container setup used for 20.2 and `runv2.sh`).

## Running

```
cat bootstrap_fixtures.py | odoo shell -d fmtest_pg --no-http > fixtures.json

python race_scenarios.py --base-url http://<host>:<port> \
    --fixtures-json fixtures.json \
    --fault-file /mnt/user/appdata/fmtest/v2race/fault --scenario all
```

`bootstrap_fixtures.py` creates the scope, write group, writer user + API key, and one
dedicated node per scenario, then prints their ids as JSON - `fixtures.json` is passed
straight through to `race_scenarios.py` via `--fixtures-json`.

Each scenario resets the fault file to empty before returning, so a crash mid-scenario
can leave a stale barrier directory behind - `--cleanup` removes
`<fault-file>.barrier.*` without running anything.
