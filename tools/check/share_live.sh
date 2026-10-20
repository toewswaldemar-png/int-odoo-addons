#!/usr/bin/env bash
# The checks of the share links that the test suite cannot do: a throw-away Odoo with several
# worker processes on the Tower test instance, seeded with folders, files and shares, against
# which two scripts run from a container beside it:
#   share_attacks.py   the attacks of the spike against the routes that were built (any leak of a
#                      name that starts with SECRET-, of a checksum, any 5xx or traceback fails)
#   share_parallel.py  real parallel uploads, downloads, visits and wrong passwords at the limits,
#                      timings on a tree of 300 folders and 21000 files, and the size of the bundle
# Then it prints the counters from the database and the errors of the log.
#
# Usage (from the repo, Git Bash):  tools/check/share_live.sh
# Never touches the live instance: own DB fmv2_live on fmtest_pg, container fmv2_live, removed at
# the end (SHARE_LIVE_KEEP=1 keeps them).
set -euo pipefail

HOST="${CHECK_HOST:-unraid}"
BASE=/mnt/user/appdata/fmtest
R="$BASE/v2live"
IMAGE=odoo:19.0-hm-test
DB=fmv2_live
NAME=fmv2_live
WORKERS="${SHARE_LIVE_WORKERS:-4}"

cd "$(git rev-parse --show-toplevel)"
source tools/check/lock.sh
take_lock sharelive
cleanup() {
  [[ "${SHARE_LIVE_KEEP:-0}" == 1 ]] && return
  ssh "$HOST" "docker rm -f $NAME >/dev/null 2>&1; docker exec fmtest_pg dropdb -U odoo --if-exists $DB; rm -rf $R" || true
}
trap 'cleanup; release_lock' EXIT

ssh "$HOST" "docker rm -f $NAME >/dev/null 2>&1 || true; docker exec fmtest_pg dropdb -U odoo --if-exists $DB; rm -rf $R; \
  mkdir -p $R/addons $R/config $R/data $R/scripts $R/out && chmod 777 $R/data $R/out"
tar -c --exclude=__pycache__ int_filemanager | ssh "$HOST" "tar -x -C $R/addons"
scp -q tools/check/share_live_seed.py tools/check/share_attacks.py tools/check/share_parallel.py "$HOST:$R/scripts/"
ssh "$HOST" "sed -e 's/^db_name = .*/db_name = $DB/' -e 's#^data_dir = .*#data_dir = /var/lib/odoo#' \
  -e 's#^addons_path = .*#addons_path = /mnt/extra-addons,/usr/lib/python3/dist-packages/odoo/addons#' \
  -e 's/^workers = .*/workers = $WORKERS/' -e 's/^max_cron_threads = .*/max_cron_threads = 0/' \
  -e 's/^x_sendfile = .*/x_sendfile = False/' -e 's/^proxy_mode = .*/proxy_mode = False/' \
  $BASE/config_v2/odoo.conf > $R/config/odoo.conf"
MOUNTS="-v $R/config:/etc/odoo:ro -v $R/addons:/mnt/extra-addons:ro -v $R/data:/var/lib/odoo"

echo "== install + seed"
ssh "$HOST" "docker run --rm --network fmtest-net $MOUNTS $IMAGE odoo -c /etc/odoo/odoo.conf -d $DB -i int_filemanager \
  --stop-after-init --workers=0 --no-http --log-level=warn >$R/install.log 2>&1"
ssh "$HOST" "docker run --rm -i --network fmtest-net $MOUNTS -v $R/out:/out $IMAGE odoo shell -c /etc/odoo/odoo.conf -d $DB \
  --no-http --log-level=warn --workers=0 < $R/scripts/share_live_seed.py" | grep -E '^(SEED|Traceback|.*Error)' || true
ssh "$HOST" "test -s $R/out/seed.json" || { echo "share_live.sh: the seed did not finish" >&2; exit 1; }

echo "== start with $WORKERS workers"
ssh "$HOST" "docker run -d --name $NAME --network fmtest-net $MOUNTS $IMAGE odoo -c /etc/odoo/odoo.conf -d $DB \
  --log-level=info >/dev/null"
for _ in $(seq 1 60); do
  ssh "$HOST" "docker exec $NAME python3 -c \"import urllib.request; urllib.request.urlopen('http://localhost:8069/web/login', timeout=5)\"" \
    >/dev/null 2>&1 && break
  sleep 2
done

client() {
  ssh "$HOST" "docker run --rm --network fmtest-net -v $R/scripts:/s:ro -v $R/out:/out:ro --entrypoint python3 $IMAGE /s/$1 http://$NAME:8069 /out/seed.json"
}
status=0
echo "== attacks"
client share_attacks.py || status=$?
echo "== parallel runs and timings"
client share_parallel.py || status=$?

echo "== the counters in the database"
psql() { ssh "$HOST" "docker exec fmtest_pg psql -U odoo -d $DB -At -F ' | ' -c \"$1\""; }
psql "SELECT name, 'uploads=' || upload_count || ' bytes=' || upload_size || ' downloads=' || download_count || ' visits=' || view_count FROM int_filemanager_share ORDER BY id"
psql "SELECT 'documents uploaded through a share: ' || count(*) FROM int_filemanager_document WHERE share_id IS NOT NULL"
psql "SELECT 'rows of wrong passwords: ' || count(*) FROM int_filemanager_share_attempt"
echo "== the log of the instance"
ssh "$HOST" "docker logs $NAME 2>&1 | grep -ciE 'traceback|ERROR '" || true
ssh "$HOST" "docker logs $NAME 2>&1 | grep -iE 'traceback|ERROR |could not serialize|concurrent update' | cut -c1-220 | sort | uniq -c | sort -rn | head -12" || true
exit $status
