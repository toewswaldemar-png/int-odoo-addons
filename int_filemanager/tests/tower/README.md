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

## Status: harness ready, scenarios blocked on the write path

`race_scenarios.py` implements the harness (HTTP session handling, writing the
fault-file, firing two requests so they overlap, tearing the barrier back down) and
every scenario from Konzept 16 as a function - but each one's `perform_*()` call raises
`NotImplementedError` until Schritt 3b (Datenmodell, Schreibwege) defines the actual
JSON-2 method names for creating a node, uploading a revision, renaming/moving, and
running the blob cleanup job. Fill those in where marked `# TODO(schreibwege):` once
they exist; the barrier mechanics themselves are already covered for real (not
simulated) processes by
`int_filemanager/tests/test_v2_fault.py::TestCrossProcessBarrier`.

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
- An admin API key (`res.users.apikeys._generate`, scope `rpc`) for the test user
  driving the scenario, and network access to the instance from wherever this script
  runs (matches the existing Tower helper-container setup used for 20.2 and `runv2.sh`).

## Running

```
python race_scenarios.py --base-url http://<host>:<port> --api-key <key> \
    --fault-file /mnt/user/appdata/fmtest/v2race/fault --scenario all
```

Each scenario resets the fault file to empty before returning, so a crash mid-scenario
can leave a stale barrier directory behind - `--cleanup` removes
`<fault-file>.barrier.*` without running anything.
