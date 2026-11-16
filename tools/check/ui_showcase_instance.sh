#!/usr/bin/env bash
# A long-lived Odoo on Tower with the CURRENT working tree of int_ui_showcase, for testing by hand
# in a browser (DB ui_showcase on fmtest_pg, container ui_showcase, port 8086, login admin / admin).
# Run again to update it to the latest working tree (the database is kept; the module is
# upgraded). `ui_showcase_instance.sh reset` drops the database and starts from scratch.
# Never touches the live Odoo or the int_filemanager test instance (ui_instance.sh).
set -euo pipefail

HOST="${CHECK_HOST:-unraid}"
BASE=/mnt/user/appdata/fmtest
R="$BASE/uishowcase"
IMAGE=odoo:19.0-hm-test
DB=ui_showcase
NAME=ui_showcase
PORT=8086
MODULE=int_ui_showcase

cd "$(git rev-parse --show-toplevel)"
if [[ "${1:-}" == reset ]]; then
  ssh "$HOST" "docker rm -f $NAME >/dev/null 2>&1; docker exec fmtest_pg dropdb -U odoo --if-exists $DB; rm -rf $R"
fi

ssh "$HOST" "docker rm -f $NAME >/dev/null 2>&1 || true; mkdir -p $R/addons $R/config $R/data && chmod 777 $R $R/data; rm -rf $R/addons/*"
tar -c --exclude=__pycache__ $MODULE | ssh "$HOST" "tar -x -C $R/addons"
ssh "$HOST" "sed -e 's/^db_name = .*/db_name = $DB/' -e 's#^data_dir = .*#data_dir = /var/lib/odoo#' \
  -e 's#^addons_path = .*#addons_path = /mnt/extra-addons,/usr/lib/python3/dist-packages/odoo/addons#' \
  -e 's/^workers = .*/workers = 0/' -e 's/^max_cron_threads = .*/max_cron_threads = 1/' -e 's/^x_sendfile = .*/x_sendfile = False/' \
  -e 's/^proxy_mode = .*/proxy_mode = False/' $BASE/config_v2/odoo.conf > $R/config/odoo.conf"
MOUNTS="-v $R/config:/etc/odoo:ro -v $R/addons:/mnt/extra-addons:ro -v $R/data:/var/lib/odoo"

exists="$(ssh "$HOST" "docker exec fmtest_pg psql -U odoo -lqt | cut -d'|' -f1 | tr -d ' ' | grep -x $DB || true")"
if [[ -z "$exists" ]]; then
  echo "== install"
  ssh "$HOST" "docker run --rm --network fmtest-net $MOUNTS $IMAGE odoo -c /etc/odoo/odoo.conf -d $DB -i $MODULE \
    --stop-after-init --workers=0 --no-http --log-level=warn --without-demo=all >$R/install.log 2>&1" || {
    ssh "$HOST" "tail -60 $R/install.log"; exit 1; }
else
  echo "== upgrade"
  ssh "$HOST" "docker run --rm --network fmtest-net $MOUNTS $IMAGE odoo -c /etc/odoo/odoo.conf -d $DB -u $MODULE \
    --stop-after-init --workers=0 --no-http --log-level=warn >$R/upgrade.log 2>&1" || {
    ssh "$HOST" "tail -60 $R/upgrade.log"; exit 1; }
fi

echo "== start"
ssh "$HOST" "docker run -d --name $NAME --network fmtest-net -p $PORT:8069 $MOUNTS $IMAGE odoo -c /etc/odoo/odoo.conf -d $DB --log-level=info >/dev/null"

ip="$(ssh "$HOST" "hostname -I | awk '{print \$1}'")"
echo "http://$ip:$PORT/odoo   (login: admin / admin)"
