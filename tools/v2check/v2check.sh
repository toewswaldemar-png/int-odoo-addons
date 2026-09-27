#!/usr/bin/env bash
# Odoo test_lint and odoo-ls for int_filemanager on the Tower test instance
# (Konzept 16, Kern 11: both must report nothing in new code).
#
# Usage (from the repo, Git Bash):  tools/v2check/v2check.sh [--quick]
#   --quick  odoo-ls only (~30 s); without it test_lint also runs (~8 min, pylint over the core)
#
# Copies the working tree of int_filemanager and onlyoffice_odoo (dependency) to Tower,
# runs both tools in throwaway containers from the test image and filters the output with
# v2check_filter.py. Never touches the live instance: own DB fmv2_lint on fmtest_pg.
set -euo pipefail

HOST="${V2CHECK_HOST:-unraid}"
BASE_REF="${V2CHECK_BASE_REF:-int_filemanager-v1}"
BASE=/mnt/user/appdata/fmtest
WORK="$BASE/v2check"
IMAGE=odoo:19.0-hm-test
DB=fmv2_lint

quick=0
[[ "${1:-}" == "--quick" ]] && quick=1

cd "$(git rev-parse --show-toplevel)"
changed="$(mktemp)"
trap 'rm -f "$changed"' EXIT
# "New" code = changed since the base tag, plus untracked files.
{
  git diff --name-only "$BASE_REF" -- int_filemanager
  git ls-files --others --exclude-standard -- int_filemanager
} | sort -u >"$changed"

ssh "$HOST" "rm -rf $BASE/v2src && mkdir -p $BASE/v2src $WORK/data && chmod 777 $WORK/data"
tar -c --exclude=__pycache__ int_filemanager onlyoffice_odoo | ssh "$HOST" "tar -x -C $BASE/v2src"
scp -q "$changed" "$HOST:$WORK/changed.txt"
scp -q tools/v2check/v2check_filter.py "$HOST:$WORK/v2check_filter.py"

echo "== odoo-ls"
ssh "$HOST" "docker run --rm --user root --network none --entrypoint /ols/odoo_ls_server \
  -v $BASE/odoo-ls:/ols -v $BASE/v2src:/mnt/v2src:ro -v $WORK:/work $IMAGE \
  --parse -c /usr/lib/python3/dist-packages -a /mnt/v2src -t /mnt/v2src --python /usr/bin/python3 \
  --stdlib /ols/typeshed/stdlib -s /ols/typeshed/stubs -o /work/odoo_ls.json --log-level error \
  >/dev/null 2>&1"

filter_args=""
if [[ $quick == 1 ]]; then
  filter_args="--no-test-lint"
else
  echo "== test_lint (takes about 8 minutes)"
  # Fresh DB each run: -i on an already installed test_lint would not run the tests again.
  ssh "$HOST" "docker exec fmtest_pg dropdb -U odoo --if-exists $DB && \
    docker run --rm --network fmtest-net \
      -v $BASE/config_v2:/etc/odoo:ro -v $BASE/v2src:/mnt/v2src:ro \
      -v $BASE/lintlib:/mnt/lintlib:ro -v $WORK/data:/var/lib/odoo \
      -e PYTHONPATH=/mnt/lintlib \
      -e PATH=/mnt/lintlib/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
      $IMAGE odoo -c /etc/odoo/odoo.conf -d $DB --db-filter=^$DB\$ \
      --addons-path=/mnt/v2src,/usr/lib/python3/dist-packages/odoo/addons --data-dir=/var/lib/odoo \
      -i test_lint --test-tags /test_lint --stop-after-init --workers=0 --max-cron-threads=0 --no-http \
      >$WORK/test_lint.log 2>&1 || true"
fi

echo "== filter"
ssh "$HOST" "docker run --rm --network none -v $WORK:/work:ro --entrypoint python3 $IMAGE \
  /work/v2check_filter.py $filter_args"
