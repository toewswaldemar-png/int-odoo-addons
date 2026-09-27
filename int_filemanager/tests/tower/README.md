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

## Status: 3 of 5 A3 scenarios verified for real on Tower

`race_scenarios.py` drives Konzept 16's scenarios over real
`/json/2/int_filemanager.node/<method>` calls against a live `workers=2` instance -
already run for real on Tower (2026-09-27), not just wired up. Result:

- `same_new_name_twice`, `same_base_revision_twice`, `rename_to_same_name` - **pass**,
  forced overlap via the barrier, real HTTP requests. This actual run is also what
  caught a real production bug (not a race): `create_new_revision`'s dedup check read
  the blob's own field without `.sudo()`, which every TransactionCase test missed
  because `setUp()` had already warmed that transaction's shared field cache - see
  `test_dedup_check_works_without_a_warm_cache` in `test_v2_write_paths.py` and the
  commit that fixed it for the full story.
- `lock_timeout_triggers_retry` - runs, but both racers won (no lock_timeout was ever
  triggered): an Odoo request normally finishes in milliseconds, well under the 5s
  `lock_timeout`, so nothing currently forces one racer to actually HOLD the row lock
  long enough for the other to time out. `fault.py` only has exception/exit/barrier
  modes, not a "hold for N seconds" one - needed before this scenario gives a real
  pass/fail signal, not just "didn't crash".
- `move_against_delete` - **not runnable as designed**: the barrier needs both racers to
  call `fault.fault_point()` with the SAME stage name (the barrier directory is keyed by
  stage, see `fault.py`), but `trash()` has no `fault_point()` call at all, unlike every
  other write path - the move racer would hang forever waiting for an arrival that can't
  happen. Needs a deliberate instrumentation decision (which stage name; whether
  `restore()`/`delete_permanently()` need the same one for symmetry) - a production-code
  change left for a follow-up rather than rushed in. See the comment where this scenario
  used to be in `race_scenarios.py` (removed from `SCENARIOS`, kept as a code comment).
- A4 ("Aufraeumjob") has no scenario at all: the cleanup cron is `@api.autovacuum`, a
  private method with no public/`ir.cron` trigger, so a live two-process reproduction
  would need a dedicated admin trigger endpoint this module does not otherwise have.
  That invariant (a reused blob must survive a concurrent cleanup run) is instead
  covered deterministically in `int_filemanager/tests/test_v2_blobstore.py`, which can
  force the exact ordering directly rather than hoping an HTTP race lands on it - see
  the comment above `load_fixtures()` in `race_scenarios.py` for the full reasoning.

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

Verified 2026-09-27 against a throwaway `fmv2_race` DB on `fmtest_pg`,
config/addons/data under `/mnt/user/appdata/fmtest/v2race/` on Tower (odoo.conf:
`workers=2`, `INT_FILEMANAGER_FAULT_FILE=/var/lib/odoo/fault.txt`), server container
`fmv2_race_odoo` on `fmtest-net`. Fresh install first
(`odoo -i int_filemanager --stop-after-init --workers=0`), then start the real server,
then:

```
# bootstrap: a throwaway odoo-shell container against the SAME db + addons + data mounts
cat bootstrap_fixtures.py | docker run --rm -i --network fmtest-net \
    -v .../v2race/config:/etc/odoo:ro -v .../v2race/addons:/mnt/extra-addons:ro \
    -v .../v2race/data:/var/lib/odoo \
    odoo:19.0-hm-test odoo shell -c /etc/odoo/odoo.conf -d fmv2_race --no-http \
    > fixtures.json   # last stdout line is the JSON; earlier lines are onlyoffice_odoo's
                       # own harmless SyntaxWarning noise, same as fmshell.sh already filters

# driver: another throwaway container, same data mount (for --fault-file) + reachable by
# container name over the SAME network (for --base-url)
docker run --rm -i --network fmtest-net \
    -v .../v2race:/work -v .../v2race/data:/var/lib/odoo \
    odoo:19.0-hm-test python3 -u /work/race_scenarios.py \
    --base-url http://fmv2_race_odoo:8069 --fixtures-json /work/fixtures.json \
    --fault-file /var/lib/odoo/fault.txt --scenario all
```

`bootstrap_fixtures.py` creates the scope, write group, writer user + API key, and one
dedicated node per scenario via real `create_file()` calls, then prints their ids as
JSON. Re-running scenarios against an already-used DB without a fresh bootstrap first
will spuriously fail on `same_new_name_twice` (the target name from the previous run
already exists) - use a fresh DB + fresh bootstrap for a clean pass, not just a fresh
fault file.

Each scenario resets the fault file to empty before returning, so a crash mid-scenario
can leave a stale barrier directory behind - `--cleanup` removes
`<fault-file>.barrier.*` without running anything.
