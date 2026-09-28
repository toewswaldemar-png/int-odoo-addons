#!/usr/bin/env bash
# Real-process race tests (A3/A4) for int_filemanager on the Tower test instance.
#
# Usage (from the repo, Git Bash):  tools/v2check/race.sh [--scenario NAME]
#
# Copies the working tree of int_filemanager and onlyoffice_odoo to Tower, installs them in a
# fresh throwaway DB (fmv2_race on fmtest_pg), starts a REAL two-worker Odoo, bootstraps the
# fixtures and runs int_filemanager/tests/tower/race_scenarios.py against it. Everything
# (container, DB, directory) is removed again at the end, also on failure; RACE_KEEP=1 keeps
# it for inspection. Never touches the live instance. Details: int_filemanager/tests/tower/README.md.
set -euo pipefail

HOST="${V2CHECK_HOST:-unraid}"
BASE=/mnt/user/appdata/fmtest
R="$BASE/v2race"
IMAGE=odoo:19.0-hm-test
DB=fmv2_race
SERVER=fmv2_race_odoo
NET=fmtest-net

cd "$(git rev-parse --show-toplevel)"

cleanup() {
  [[ "${RACE_KEEP:-0}" == 1 ]] && return
  ssh "$HOST" "docker rm -f $SERVER >/dev/null 2>&1; docker exec fmtest_pg dropdb -U odoo --if-exists $DB; rm -rf $R" || true
}
trap cleanup EXIT

echo "== sync"
ssh "$HOST" "docker rm -f $SERVER >/dev/null 2>&1 || true; rm -rf $R && mkdir -p $R/addons $R/config $R/data $R/work && chmod 777 $R/data"
tar -c --exclude=__pycache__ int_filemanager onlyoffice_odoo | ssh "$HOST" "tar -x -C $R/addons"
scp -q int_filemanager/tests/tower/race_scenarios.py int_filemanager/tests/tower/bootstrap_fixtures.py "$HOST:$R/work/"
ssh "$HOST" "sed -e 's/^db_name = .*/db_name = $DB/' -e 's#^addons_path = .*#addons_path = /mnt/extra-addons,/usr/lib/python3/dist-packages/odoo/addons#' \
  -e 's#^data_dir = .*#data_dir = /var/lib/odoo#' -e 's/^max_cron_threads = .*/max_cron_threads = 0/' -e 's/^workers = .*/workers = 2/' \
  $BASE/config_v2/odoo.conf > $R/config/odoo.conf"

MOUNTS="-v $R/config:/etc/odoo:ro -v $R/addons:/mnt/extra-addons:ro -v $R/data:/var/lib/odoo"

echo "== install"
ssh "$HOST" "docker exec fmtest_pg dropdb -U odoo --if-exists $DB && docker run --rm --network $NET $MOUNTS $IMAGE \
  odoo -c /etc/odoo/odoo.conf -d $DB -i int_filemanager --stop-after-init --workers=0 --no-http --log-level=warn >$R/install.log 2>&1" \
  || { ssh "$HOST" "tail -30 $R/install.log"; exit 1; }
# A shell/server session against a DB with the watcher on would start a second watcher (Konzept 19.5, N5).
ssh "$HOST" "docker exec fmtest_pg psql -U odoo -d $DB -qAtc \"insert into ir_config_parameter(key,value,create_date,write_date) values('int_filemanager.watcher_enabled','false',now(),now()) on conflict (key) do update set value='false'\""

echo "== bootstrap"
ssh "$HOST" "docker run --rm -i --network $NET $MOUNTS $IMAGE odoo shell -c /etc/odoo/odoo.conf -d $DB --no-http --log-level=warn \
  < $R/work/bootstrap_fixtures.py 2>$R/bootstrap.err | grep '^{' > $R/work/fixtures.json" \
  || { ssh "$HOST" "tail -30 $R/bootstrap.err"; exit 1; }

echo "== start server (workers=2)"
ssh "$HOST" "docker run -d --name $SERVER --network $NET -e INT_FILEMANAGER_FAULT_FILE=/var/lib/odoo/fault.txt $MOUNTS $IMAGE \
  odoo -c /etc/odoo/odoo.conf -d $DB --log-level=info >/dev/null"
for _ in $(seq 1 60); do
  if ssh "$HOST" "docker run --rm --network $NET $IMAGE python3 -c \"import urllib.request as u; u.urlopen('http://$SERVER:8069/web/health', timeout=3)\"" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

echo "== scenarios"
status=0
ssh "$HOST" "docker run --rm --network $NET $MOUNTS -v $R/work:/work $IMAGE python3 -u /work/race_scenarios.py \
  --base-url http://$SERVER:8069 --fixtures-json /work/fixtures.json --fault-file /var/lib/odoo/fault.txt \
  --odoo-shell-cmd 'odoo shell -c /etc/odoo/odoo.conf -d $DB --no-http --log-level=warn' $*" || status=$?
if [[ $status != 0 ]]; then
  echo "== server log (tail)"
  ssh "$HOST" "docker logs --tail 40 $SERVER 2>&1" || true
fi
exit $status
