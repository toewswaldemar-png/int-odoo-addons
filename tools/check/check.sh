#!/usr/bin/env bash
# odoo-ls for int_filemanager and its extension modules on the Tower test instance (must report nothing there).
#
# Usage (from the repo, Git Bash):  tools/check/check.sh
#
# Copies the working trees of int_filemanager* to Tower, runs odoo-ls in a throwaway container from
# the test image (about 30 s) and filters the output with check_filter.py.
# Never touches the live instance.
set -euo pipefail

HOST="${CHECK_HOST:-unraid}"
BASE=/mnt/user/appdata/fmtest
WORK="$BASE/v2check"
IMAGE=odoo:19.0-hm-test

cd "$(git rev-parse --show-toplevel)"
source tools/check/lock.sh
take_lock check

# Nothing stays on Tower but odoo-ls itself; CHECK_KEEP=1 keeps the rest to look at.
cleanup() {
  [[ "${CHECK_KEEP:-0}" == 1 ]] || ssh "$HOST" "rm -rf $BASE/v2src $WORK" || true
  release_lock
}
trap cleanup EXIT

ssh "$HOST" "rm -rf $BASE/v2src && mkdir -p $BASE/v2src $WORK && chmod 777 $WORK"
tar -c --exclude=__pycache__ int_filemanager* | ssh "$HOST" "tar -x -C $BASE/v2src"
scp -q tools/check/check_filter.py "$HOST:$WORK/check_filter.py"

# A missing tool must not look like a clean result: stop loudly.
require() {
  ssh "$HOST" "test $1" || { echo "check.sh: $2" >&2; exit 1; }
}
require "-x $BASE/odoo-ls/odoo_ls_server -a -d $BASE/odoo-ls/typeshed/stdlib" \
  "odoo-ls is missing in $BASE/odoo-ls (odoo_ls_server and typeshed/ from the odoo/odoo-ls release)"

echo "== odoo-ls"
ssh "$HOST" "rm -f $WORK/odoo_ls.json; docker run --rm --user root --network none --entrypoint /ols/odoo_ls_server \
  -v $BASE/odoo-ls:/ols -v $BASE/v2src:/mnt/v2src:ro -v $WORK:/work $IMAGE \
  --parse -c /usr/lib/python3/dist-packages -a /mnt/v2src -t /mnt/v2src --python /usr/bin/python3 \
  --stdlib /ols/typeshed/stdlib -s /ols/typeshed/stubs -o /work/odoo_ls.json --log-level error \
  >/dev/null 2>&1" || { echo "check.sh: odoo-ls failed" >&2; exit 1; }
require "-s $WORK/odoo_ls.json" "odoo-ls wrote no result"

echo "== filter"
ssh "$HOST" "docker run --rm --network none -v $WORK:/work:ro --entrypoint python3 $IMAGE /work/check_filter.py"
