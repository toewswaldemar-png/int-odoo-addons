#!/usr/bin/env bash
# A long-lived Odoo on Tower with the CURRENT working tree of int_filemanager, for testing by
# hand in a browser (DB fmv2_ui on fmtest_pg, container fmv2_ui, port 8085).
# Run again to update it to the latest working tree (the database is kept; the module is
# upgraded). `ui_instance.sh reset` drops the database and starts from scratch.
# Never touches the live Odoo. The test login is written to $R/LOGIN.txt on Tower.
set -euo pipefail

HOST="${CHECK_HOST:-unraid}"
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
tar -c --exclude=__pycache__ --exclude=node_modules int_filemanager | ssh "$HOST" "tar -x -C $R/addons"
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
  echo "== seed"
  ssh "$HOST" "docker run --rm -i --network fmtest-net $MOUNTS -v $R:/out $IMAGE odoo shell -c /etc/odoo/odoo.conf -d $DB --no-http --log-level=warn" <<'PY' 2>&1 | grep -E '^(LOGIN|SEED)' || true
import secrets
env = env  # noqa: F821 - injected by odoo shell
group_user = env.ref("int_filemanager.group_filemanager_user")
group_admin = env.ref("int_filemanager.group_filemanager_admin")
folder = env["int_filemanager.folder"].sudo().create({"name": "Test"})
password = secrets.token_urlsafe(9)
env["res.users"].sudo().create({
    "name": "Files tester",
    "login": "tester",
    "password": password,
    "group_ids": [(6, 0, [env.ref("base.group_user").id, group_user.id, group_admin.id])],
})
env.cr.commit()
open("/out/LOGIN.txt", "w").write(f"login: tester\npassword: {password}\n")
print("LOGIN written; root folder id", folder.id)
PY
fi

echo "== upgrade + start"
ssh "$HOST" "docker run --rm --network fmtest-net $MOUNTS $IMAGE odoo -c /etc/odoo/odoo.conf -d $DB -u int_filemanager --i18n-overwrite \
  --stop-after-init --workers=0 --no-http --log-level=warn >$R/upgrade.log 2>&1"
ssh "$HOST" "docker run -d --name $NAME --network fmtest-net -p $PORT:8069 $MOUNTS $IMAGE odoo -c /etc/odoo/odoo.conf -d $DB --log-level=info >/dev/null"

ip="$(ssh "$HOST" "hostname -I | awk '{print \$1}'")"
echo "http://$ip:$PORT/odoo/action-int_filemanager.int_filemanager_document_action   (login: cat $R/LOGIN.txt on Tower)"
