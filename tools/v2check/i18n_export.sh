#!/usr/bin/env bash
# Exports every translatable term of int_filemanager (Python, XML views, JS, QWeb) from a
# fresh install on the Tower test instance into a .pot next to this script's output dir:
#   tools/v2check/i18n_export.sh  ->  prints the path of the fetched file (tmp)
# Odoo's own exporter finds the terms in static/src (JS _t(), QWeb text) too.
set -euo pipefail

HOST="${V2CHECK_HOST:-unraid}"
BASE=/mnt/user/appdata/fmtest
R="$BASE/v2i18n"
IMAGE=odoo:19.0-hm-test
DB=fmv2_i18n
OUT="${1:-/tmp/int_filemanager.pot}"

cd "$(git rev-parse --show-toplevel)"
cleanup() {
  [[ "${I18N_KEEP:-0}" == 1 ]] && return
  ssh "$HOST" "docker exec fmtest_pg dropdb -U odoo --if-exists $DB; rm -rf $R" || true
}
trap cleanup EXIT

ssh "$HOST" "rm -rf $R && mkdir -p $R/addons $R/config $R/data $R/out && chmod 777 $R/data $R/out"
tar -c --exclude=__pycache__ int_filemanager onlyoffice_odoo | ssh "$HOST" "tar -x -C $R/addons"
ssh "$HOST" "sed -e 's/^db_name = .*/db_name = $DB/' -e 's#^data_dir = .*#data_dir = /var/lib/odoo#' \
  -e 's#^addons_path = .*#addons_path = /mnt/extra-addons,/usr/lib/python3/dist-packages/odoo/addons#' \
  $BASE/config_v2/odoo.conf > $R/config/odoo.conf"
ssh "$HOST" "docker exec fmtest_pg dropdb -U odoo --if-exists $DB && docker run --rm --network fmtest-net \
  -v $R/config:/etc/odoo:ro -v $R/addons:/mnt/extra-addons:ro -v $R/data:/var/lib/odoo -v $R/out:/out $IMAGE \
  odoo -c /etc/odoo/odoo.conf -d $DB -i int_filemanager --stop-after-init --workers=0 --no-http --log-level=warn \
  >$R/install.log 2>&1 && docker run --rm --network fmtest-net \
  -v $R/config:/etc/odoo:ro -v $R/addons:/mnt/extra-addons:ro -v $R/data:/var/lib/odoo -v $R/out:/out $IMAGE \
  odoo i18n export -c /etc/odoo/odoo.conf -d $DB -o /out/int_filemanager.pot int_filemanager \
  >$R/export.log 2>&1"
scp -q "$HOST:$R/out/int_filemanager.pot" "$OUT"
echo "$OUT"
