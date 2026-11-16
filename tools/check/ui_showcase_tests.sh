#!/usr/bin/env bash
# Odoo tests of int_ui_showcase on the Tower test instance, including the browser tours (headless
# Chrome). Needs the image odoo:19.0-hm-test-chrome (odoo:19.0-hm-test plus Google Chrome; built
# from /mnt/user/appdata/fmtest/chromebuild/Dockerfile on Tower).
#
# Usage (from the repo, Git Bash):  tools/check/ui_showcase_tests.sh [--test-tags TAGS]
#   default tags: /int_ui_showcase (every test of the module)
#
# Installs the module in a fresh throwaway DB (ui_showcase_tests on fmtest_pg); DB and directory
# are removed again (TESTS_KEEP=1 keeps them, with the log and the screenshots of failed tours in $R). Never touches the other instances.
set -euo pipefail

HOST="${CHECK_HOST:-unraid}"
BASE=/mnt/user/appdata/fmtest
R="$BASE/uishowcasetests"
IMAGE=odoo:19.0-hm-test-chrome
DB=ui_showcase_tests
MODULE=int_ui_showcase
TAGS="/$MODULE"
if [[ "${1:-}" == "--test-tags" ]]; then
  TAGS="$2"
fi

cd "$(git rev-parse --show-toplevel)"

cleanup() {
  [[ "${TESTS_KEEP:-0}" == 1 ]] && return
  ssh "$HOST" "docker exec fmtest_pg dropdb -U odoo --if-exists $DB; rm -rf $R" || true
}
trap cleanup EXIT

ssh "$HOST" "rm -rf $R && mkdir -p $R/addons $R/config $R/data $R/out && chmod 777 $R/data $R/out"
tar -c --exclude=__pycache__ $MODULE | ssh "$HOST" "tar -x -C $R/addons"
ssh "$HOST" "sed -e 's/^db_name = .*/db_name = $DB/' -e 's#^data_dir = .*#data_dir = /var/lib/odoo#' \
  -e 's#^addons_path = .*#addons_path = /mnt/extra-addons,/usr/lib/python3/dist-packages/odoo/addons#' \
  -e 's/^workers = .*/workers = 0/' -e 's/^proxy_mode = .*/proxy_mode = False/' \
  $BASE/config_v2/odoo.conf > $R/config/odoo.conf"

status=0
ssh "$HOST" "docker exec fmtest_pg dropdb -U odoo --if-exists $DB && docker run --rm --network fmtest-net \
  -v $R/config:/etc/odoo:ro -v $R/addons:/mnt/extra-addons:ro -v $R/data:/var/lib/odoo -v $R/out:/tmp/odoo_tests $IMAGE \
  odoo -c /etc/odoo/odoo.conf -d $DB -i $MODULE --test-tags '$TAGS' --stop-after-init --workers=0 \
  --max-cron-threads=0 --http-port=8070 --log-level=test >$R/tests.log 2>&1" || status=$?
ssh "$HOST" "grep -E -A25 'FAIL:|ERROR:|Traceback|console\.(error|warn)|ERROR \\$DB' $R/tests.log | head -150; grep -E 'tests in|failed, ' $R/tests.log | tail -3"
exit $status
