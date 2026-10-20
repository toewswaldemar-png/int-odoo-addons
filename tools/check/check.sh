#!/usr/bin/env bash
# Odoo test_lint and odoo-ls for int_filemanager on the Tower test instance
# (both must report nothing in int_filemanager; test_lint also fails on any failed test that is
# neither explained by a finding in int_filemanager nor a known core finding, see check_filter.py).
#
# Usage (from the repo, Git Bash):  tools/check/check.sh [--quick]
#   --quick  odoo-ls only (~30 s); without it test_lint also runs (~8 min, pylint over the core)
#
# Copies the working tree of int_filemanager to Tower,
# runs both tools in throwaway containers from the test image and filters the output with
# check_filter.py. Never touches the live instance: own DB fmv2_lint on fmtest_pg.
set -euo pipefail

HOST="${CHECK_HOST:-unraid}"
BASE=/mnt/user/appdata/fmtest
WORK="$BASE/v2check"
IMAGE=odoo:19.0-hm-test
DB=fmv2_lint

quick=0
[[ "${1:-}" == "--quick" ]] && quick=1

cd "$(git rev-parse --show-toplevel)"
source tools/check/lock.sh
take_lock check

# Nothing stays on Tower but the tools (odoo-ls, lintlib); CHECK_KEEP=1 keeps the rest to look at.
cleanup() {
  [[ "${CHECK_KEEP:-0}" == 1 ]] || ssh "$HOST" "docker exec fmtest_pg dropdb -U odoo --if-exists $DB; rm -rf $BASE/v2src $WORK" || true
  release_lock
}
trap cleanup EXIT

ssh "$HOST" "rm -rf $BASE/v2src && mkdir -p $BASE/v2src $WORK/data && chmod 777 $WORK/data"
tar -c --exclude=__pycache__ int_filemanager | ssh "$HOST" "tar -x -C $BASE/v2src"
scp -q tools/check/check_filter.py "$HOST:$WORK/check_filter.py"

# A missing tool must not look like a clean result: stop loudly.
require() {
  ssh "$HOST" "test $1" || { echo "check.sh: $2" >&2; exit 1; }
}
require "-x $BASE/odoo-ls/odoo_ls_server -a -d $BASE/odoo-ls/typeshed/stdlib" \
  "odoo-ls is missing in $BASE/odoo-ls (odoo_ls_server and typeshed/ from the odoo/odoo-ls release)"
[[ $quick == 1 ]] || require "-d $BASE/lintlib/pylint" \
  "pylint is missing in $BASE/lintlib (pip install --target, see docs/pruefautomatik_2026-10-02.md)"

echo "== odoo-ls"
ssh "$HOST" "rm -f $WORK/odoo_ls.json; docker run --rm --user root --network none --entrypoint /ols/odoo_ls_server \
  -v $BASE/odoo-ls:/ols -v $BASE/v2src:/mnt/v2src:ro -v $WORK:/work $IMAGE \
  --parse -c /usr/lib/python3/dist-packages -a /mnt/v2src -t /mnt/v2src --python /usr/bin/python3 \
  --stdlib /ols/typeshed/stdlib -s /ols/typeshed/stubs -o /work/odoo_ls.json --log-level error \
  >/dev/null 2>&1" || { echo "check.sh: odoo-ls failed" >&2; exit 1; }
require "-s $WORK/odoo_ls.json" "odoo-ls wrote no result"

filter_args=""
if [[ $quick == 1 ]]; then
  filter_args="--no-test-lint"
else
  echo "== test_lint (takes about 8 minutes)"
  # Fresh DB each run: -i on an already installed test_lint would not run the tests again.
  # Remove old results first, so a stale log can never be mistaken for this run. Odoo's exit status
  # is kept in test_lint.exit (it is non-zero for the known core findings too, so the filter
  # judges the summary line and the failed tests, not the status alone).
  ssh "$HOST" "rm -f $WORK/test_lint.log $WORK/test_lint.exit; docker exec fmtest_pg dropdb -U odoo --if-exists $DB && \
    docker run --rm --network fmtest-net \
      -v $BASE/config_v2:/etc/odoo:ro -v $BASE/v2src:/mnt/v2src:ro \
      -v $BASE/lintlib:/mnt/lintlib:ro -v $WORK/data:/var/lib/odoo \
      -e PYTHONPATH=/mnt/lintlib \
      -e PATH=/mnt/lintlib/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
      $IMAGE odoo -c /etc/odoo/odoo.conf -d $DB --db-filter=^$DB\$ \
      --addons-path=/mnt/v2src,/usr/lib/python3/dist-packages/odoo/addons --data-dir=/var/lib/odoo \
      -i test_lint --test-tags /test_lint --stop-after-init --workers=0 --max-cron-threads=0 --no-http \
      >$WORK/test_lint.log 2>&1; echo \$? >$WORK/test_lint.exit"
fi

echo "== filter"
ssh "$HOST" "docker run --rm --network none -v $WORK:/work:ro --entrypoint python3 $IMAGE \
  /work/check_filter.py $filter_args"
