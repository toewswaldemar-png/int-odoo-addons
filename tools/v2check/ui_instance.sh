#!/usr/bin/env bash
# A long-lived Odoo on Tower with the CURRENT working tree of int_filemanager, for testing the
# v2 explorer by hand in a browser (DB fmv2_ui on fmtest_pg, container fmv2_ui, port 8085).
# Run again to update it to the latest working tree (the database is kept; the module is
# upgraded). `ui_instance.sh reset` drops the database and starts from scratch.
# Also starts the converter container fmv2_ui_conv for thumbnails (blob store mounted read-only).
# Never touches the live Odoo. The test login is written to $R/LOGIN.txt on Tower.
set -euo pipefail

HOST="${V2CHECK_HOST:-unraid}"
BASE=/mnt/user/appdata/fmtest
R="$BASE/v2ui"
IMAGE=odoo:19.0-hm-test
DB=fmv2_ui
NAME=fmv2_ui
PORT=8085

cd "$(git rev-parse --show-toplevel)"
if [[ "${1:-}" == reset ]]; then
  ssh "$HOST" "docker rm -f $NAME >/dev/null 2>&1; docker exec fmtest_pg dropdb -U odoo --if-exists $DB; rm -rf $R"
fi

ssh "$HOST" "docker rm -f $NAME >/dev/null 2>&1 || true; mkdir -p $R/addons $R/config $R/data && chmod 777 $R $R/data; rm -rf $R/addons/*"
tar -c --exclude=__pycache__ --exclude=node_modules int_filemanager onlyoffice_odoo | ssh "$HOST" "tar -x -C $R/addons"
ssh "$HOST" "sed -e 's/^db_name = .*/db_name = $DB/' -e 's#^data_dir = .*#data_dir = /var/lib/odoo#' \
  -e 's#^addons_path = .*#addons_path = /mnt/extra-addons,/usr/lib/python3/dist-packages/odoo/addons#' \
  -e 's/^workers = .*/workers = 0/' -e 's/^max_cron_threads = .*/max_cron_threads = 1/' -e 's/^x_sendfile = .*/x_sendfile = False/' \
  -e 's/^proxy_mode = .*/proxy_mode = False/' $BASE/config_v2/odoo.conf > $R/config/odoo.conf"
MOUNTS="-v $R/config:/etc/odoo:ro -v $R/addons:/mnt/extra-addons:ro -v $R/data:/var/lib/odoo"

exists="$(ssh "$HOST" "docker exec fmtest_pg psql -U odoo -lqt | cut -d'|' -f1 | tr -d ' ' | grep -x $DB || true")"
if [[ -z "$exists" ]]; then
  echo "== install"
  ssh "$HOST" "docker run --rm --network fmtest-net $MOUNTS $IMAGE odoo -c /etc/odoo/odoo.conf -d $DB -i int_filemanager \
    --stop-after-init --workers=0 --no-http --log-level=warn --load-language=de_DE >$R/install.log 2>&1"
  ssh "$HOST" "docker exec fmtest_pg psql -U odoo -d $DB -qAtc \"insert into ir_config_parameter(key,value,create_date,write_date) values('int_filemanager.watcher_enabled','false',now(),now()) on conflict (key) do update set value='false'\""
  echo "== seed"
  ssh "$HOST" "docker run --rm -i --network fmtest-net $MOUNTS -v $R:/out $IMAGE odoo shell -c /etc/odoo/odoo.conf -d $DB --no-http --log-level=warn" <<'PY' 2>&1 | grep -E '^(LOGIN|SEED)' || true
import secrets
env = env  # noqa: F821 - injected by odoo shell
group_user = env.ref("int_filemanager.group_filemanager_user")
group_admin = env.ref("int_filemanager.group_filemanager_admin")
everyone = env["res.groups"].sudo().create({"name": "Files test: everyone"})
scope = env["int_filemanager.scope"].sudo().create({
    "name": "All",
    "read_group_ids": [(4, everyone.id)],
    "write_group_ids": [(4, everyone.id)],
    "purge_group_ids": [(4, everyone.id)],
})
root = env["int_filemanager.node"].sudo().create({"name": "Test", "scope_id": scope.id, "is_dir": True})
password = secrets.token_urlsafe(9)
user = env["res.users"].sudo().create({
    "name": "Files tester",
    "login": "tester",
    "password": password,
    "group_ids": [(6, 0, [env.ref("base.group_user").id, group_user.id, group_admin.id, everyone.id])],
})
env["res.users"].browse(2).sudo().write({"group_ids": [(4, everyone.id)]})
env.cr.commit()
open("/out/LOGIN.txt", "w").write(f"login: tester\npassword: {password}\n")
print("LOGIN written; root folder id", root.id)
PY
fi

echo "== upgrade + start"
ssh "$HOST" "docker run --rm --network fmtest-net $MOUNTS $IMAGE odoo -c /etc/odoo/odoo.conf -d $DB -u int_filemanager \
  --stop-after-init --workers=0 --no-http --log-level=warn >$R/upgrade.log 2>&1"
ssh "$HOST" "docker run -d --name $NAME --network fmtest-net -p $PORT:8069 $MOUNTS $IMAGE odoo -c /etc/odoo/odoo.conf -d $DB --log-level=info >/dev/null"

echo "== converter (thumbnails): read-only blob store, same code as tools/fmconverter"
CONV=fmv2_ui_conv
ssh "$HOST" "mkdir -p $R/tools $R/data/filestore/$DB/blobs && chmod 777 $R/data/filestore $R/data/filestore/$DB 2>/dev/null; rm -rf $R/tools/fmconverter"
tar -c tools/fmconverter | ssh "$HOST" "tar -x -C $R"
ssh "$HOST" "docker rm -f $CONV >/dev/null 2>&1 || true; docker run -d --name $CONV --network fmtest-net --user 10001 \
  -v $R/data/filestore/$DB/blobs:/blobs:ro -v $R/tools/fmconverter:/app:ro --entrypoint python3 $IMAGE /app/server.py >/dev/null"
ssh "$HOST" "docker exec fmtest_pg psql -U odoo -d $DB -qAtc \"insert into ir_config_parameter(key,value,create_date,write_date) values('int_filemanager.converter_url','http://$CONV:8090',now(),now()) on conflict (key) do update set value='http://$CONV:8090'\""
ip="$(ssh "$HOST" "hostname -I | awk '{print \$1}'")"
echo "http://$ip:$PORT/odoo/action-int_filemanager.action_int_filemanager_node   (login: cat $R/LOGIN.txt on Tower)"
