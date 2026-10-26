#!/usr/bin/env bash
# Exports every translatable term of a module (Python, XML views, JS, QWeb; default int_filemanager,
# I18N_MODULE=int_filemanager_share for another one) from a
# fresh install on the Tower test instance into a .pot next to this script's output dir:
#   tools/check/i18n_export.sh  ->  prints the path of the fetched file (tmp)
# With I18N_LANG=de_DE it installs the module with its translation of that language (i18n/de.po)
# and exports that language instead: Odoo writes the file in its own layout (line breaks, order),
# the way to bring a hand-merged .po back into the form Odoo would export.
#   I18N_LANG=de_DE tools/check/i18n_export.sh /tmp/de.po
# Odoo's own exporter finds the terms in static/src (JS _t(), QWeb text) too.
set -euo pipefail

HOST="${CHECK_HOST:-unraid}"
BASE=/mnt/user/appdata/fmtest
R="$BASE/v2i18n"
IMAGE=odoo:19.0-hm-test
DB=fmv2_i18n
MODULE="${I18N_MODULE:-int_filemanager}"
OUT="${1:-/tmp/$MODULE.pot}"
LANGUAGE="${I18N_LANG:-pot}"
LOAD=""
EXTENSION=pot
if [[ "$LANGUAGE" != pot ]]; then
  LOAD="--load-language=$LANGUAGE"
  EXTENSION=po
fi

cd "$(git rev-parse --show-toplevel)"
source tools/check/lock.sh
take_lock i18n
cleanup() {
  [[ "${I18N_KEEP:-0}" == 1 ]] && return
  ssh "$HOST" "docker exec fmtest_pg dropdb -U odoo --if-exists $DB; rm -rf $R" || true
}
trap 'cleanup; release_lock' EXIT

ssh "$HOST" "rm -rf $R && mkdir -p $R/addons $R/config $R/data $R/out && chmod 777 $R/data $R/out"
tar -c --exclude=__pycache__ int_filemanager* | ssh "$HOST" "tar -x -C $R/addons"
ssh "$HOST" "sed -e 's/^db_name = .*/db_name = $DB/' -e 's#^data_dir = .*#data_dir = /var/lib/odoo#' \
  -e 's#^addons_path = .*#addons_path = /mnt/extra-addons,/usr/lib/python3/dist-packages/odoo/addons#' \
  $BASE/config_v2/odoo.conf > $R/config/odoo.conf"
ssh "$HOST" "docker exec fmtest_pg dropdb -U odoo --if-exists $DB && docker run --rm --network fmtest-net \
  -v $R/config:/etc/odoo:ro -v $R/addons:/mnt/extra-addons:ro -v $R/data:/var/lib/odoo -v $R/out:/out $IMAGE \
  odoo -c /etc/odoo/odoo.conf -d $DB -i $MODULE $LOAD --stop-after-init --workers=0 --no-http --log-level=warn \
  >$R/install.log 2>&1 && docker run --rm --network fmtest-net \
  -v $R/config:/etc/odoo:ro -v $R/addons:/mnt/extra-addons:ro -v $R/data:/var/lib/odoo -v $R/out:/out $IMAGE \
  odoo i18n export -c /etc/odoo/odoo.conf -d $DB -l $LANGUAGE -o /out/$MODULE.$EXTENSION $MODULE \
  >$R/export.log 2>&1"
scp -q "$HOST:$R/out/$MODULE.$EXTENSION" "$OUT"
echo "$OUT"
