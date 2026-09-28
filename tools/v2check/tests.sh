#!/usr/bin/env bash
# Odoo test suite of int_filemanager on the Tower test instance (fresh install + tests).
#
# Usage (from the repo, Git Bash):  tools/v2check/tests.sh [--test-tags TAGS]
#   default tags: /int_filemanager (every test of the module)
#
# Copies the working tree of int_filemanager and onlyoffice_odoo to Tower, installs them in a
# fresh throwaway DB (fmv2_tests on fmtest_pg) and runs the tests there; DB and directory are
# removed again (TESTS_KEEP=1 keeps them). Never touches the live instance.
set -euo pipefail

HOST="${V2CHECK_HOST:-unraid}"
BASE=/mnt/user/appdata/fmtest
R="$BASE/v2tests"
IMAGE=odoo:19.0-hm-test
DB=fmv2_tests
TAGS="/int_filemanager"
if [[ "${1:-}" == "--test-tags" ]]; then
  TAGS="$2"
fi

cd "$(git rev-parse --show-toplevel)"

cleanup() {
  [[ "${TESTS_KEEP:-0}" == 1 ]] && return
  ssh "$HOST" "docker exec fmtest_pg dropdb -U odoo --if-exists $DB; rm -rf $R" || true
}
trap cleanup EXIT

ssh "$HOST" "rm -rf $R && mkdir -p $R/addons $R/config $R/data && chmod 777 $R/data"
tar -c --exclude=__pycache__ int_filemanager onlyoffice_odoo | ssh "$HOST" "tar -x -C $R/addons"
ssh "$HOST" "sed -e 's/^db_name = .*/db_name = $DB/' -e 's#^data_dir = .*#data_dir = /var/lib/odoo#' \
  -e 's#^addons_path = .*#addons_path = /mnt/extra-addons,/usr/lib/python3/dist-packages/odoo/addons#' \
  $BASE/config_v2/odoo.conf > $R/config/odoo.conf"

status=0
ssh "$HOST" "docker exec fmtest_pg dropdb -U odoo --if-exists $DB && docker run --rm --network fmtest-net \
  -v $R/config:/etc/odoo:ro -v $R/addons:/mnt/extra-addons:ro -v $R/data:/var/lib/odoo $IMAGE \
  odoo -c /etc/odoo/odoo.conf -d $DB -i int_filemanager --test-tags '$TAGS' --stop-after-init --workers=0 \
  --max-cron-threads=0 --no-http --log-level=test >$R/tests.log 2>&1" || status=$?
ssh "$HOST" "grep -E -A14 'FAIL:|ERROR: Test' $R/tests.log | head -120; grep -E 'tests in|failed, ' $R/tests.log | tail -3"
exit $status
