#!/usr/bin/env bash
# Runs the int_keepass tests in a throwaway Odoo on HM-SRV.
#
# Usage (Git Bash, from the repo):
#   tools/int_keepass/odoo_real_check.sh                   all tests, the real-database tests are skipped
#   tools/int_keepass/odoo_real_check.sh PATH_TO_KDBX      and the real-database tests against that file
#
# With a file, the master password is typed here and travels to the server on stdin only: it is
# never part of a command line, the chat or a stored Odoo setting. The encrypted file is copied
# to /tmp/kptest, the database lives in RAM; everything is removed again.
set -euo pipefail

HOST="${CHECK_HOST:-unraid-odoo}"
IMAGE=int-filemanager-odoo:19.0-ocr
R=/tmp/kptest
KDBX="${1:-}"

cd "$(git rev-parse --show-toplevel)"
PW=""
if [[ -n "$KDBX" ]]; then
  read -r -s -p "Master password: " PW
  echo
fi

cleanup() {
  ssh "$HOST" "docker rm -f kp_pg >/dev/null 2>&1; docker network rm kp_net >/dev/null 2>&1; rm -rf $R" || true
}
trap cleanup EXIT

ssh "$HOST" "set -e; rm -rf $R; mkdir -p $R/addons $R/data $R/pylib $R/real; chmod 777 $R/data $R/pylib
  docker rm -f kp_pg >/dev/null 2>&1 || true; docker network rm kp_net >/dev/null 2>&1 || true
  docker network create kp_net >/dev/null
  docker run -d --name kp_pg --network kp_net -e POSTGRES_USER=odoo -e POSTGRES_PASSWORD=odoo -e POSTGRES_DB=postgres --tmpfs /var/lib/postgresql/data postgres:17 >/dev/null
  docker run --rm --user root --entrypoint python3 -v $R/pylib:/pylib $IMAGE -m pip install --quiet --target /pylib --break-system-packages pykeepass >/dev/null 2>&1
  for i in \$(seq 1 30); do docker exec kp_pg pg_isready -U odoo >/dev/null 2>&1 && break; sleep 1; done"
tar -c --exclude=__pycache__ int_keepass | ssh "$HOST" "tar -x -C $R/addons"
if [[ -n "$KDBX" ]]; then
  scp -q "$KDBX" "$HOST:$R/real/real.kdbx"
  REAL_ENV='-e INT_KEEPASS_TEST_PASSWORD -e INT_KEEPASS_TEST_PATH=/real/real.kdbx'
else
  REAL_ENV=''
fi

# the password is read from stdin on the server and handed to docker by name, not by value
printf '%s\n' "$PW" | ssh "$HOST" "read -r INT_KEEPASS_TEST_PASSWORD; export INT_KEEPASS_TEST_PASSWORD
  chmod 644 $R/real/real.kdbx 2>/dev/null || true
  docker run --rm --name kp_odoo --entrypoint /entrypoint.sh --network kp_net \
    -e HOST=kp_pg -e USER=odoo -e PASSWORD=odoo -e PYTHONPATH=/pylib $REAL_ENV \
    -v $R/pylib:/pylib:ro -v $R/real:/real:ro -v $R/addons:/mnt/extra-addons:ro -v $R/data:/var/lib/odoo \
    $IMAGE odoo --addons-path=/mnt/extra-addons,/usr/lib/python3/dist-packages/odoo/addons \
    -d kp_test -i int_keepass --test-tags /int_keepass --stop-after-init --workers=0 --max-cron-threads=0 \
    --log-level=test > $R/tests.log 2>&1 || true
  grep -nE 'ERROR|FAIL|post-tests|Traceback' $R/tests.log | cut -c1-220 | head -60"
