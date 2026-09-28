#!/usr/bin/env bash
# Static checks of int_filemanager's browser code in the Odoo test image on Tower: Odoo's
# own JS transpiler + node --check, import/export resolution, QWeb template references.
# See jscheck.py. Node unit tests of the pure logic run locally instead:
#   node --test "int_filemanager/static/tests/js/*.test.mjs"
set -euo pipefail

HOST="${V2CHECK_HOST:-unraid}"
BASE=/mnt/user/appdata/fmtest
WORK="$BASE/v2jscheck"
IMAGE=odoo:19.0-hm-test

cd "$(git rev-parse --show-toplevel)"
ssh "$HOST" "rm -rf $WORK && mkdir -p $WORK"
tar -c --exclude=__pycache__ int_filemanager/static | ssh "$HOST" "tar -x -C $WORK"
scp -q tools/v2check/jscheck.py "$HOST:$WORK/jscheck.py"
ssh "$HOST" "docker run --rm -v $WORK:/w --entrypoint python3 $IMAGE /w/jscheck.py /w/int_filemanager" || status=$?
ssh "$HOST" "rm -rf $WORK"
exit "${status:-0}"
