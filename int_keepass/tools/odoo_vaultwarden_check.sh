#!/usr/bin/env bash
# Runs the int_keepass tests on HM-SRV against a throwaway Vaultwarden with TLS and a test account,
# so that Odoo reads a real server: certificate pinned by its fingerprint, PBKDF2 account.
#
# Usage (Git Bash, from the repo):  int_keepass/tools/odoo_vaultwarden_check.sh
#
# Nothing of the live instances is touched; containers, network and files are removed again.
set -euo pipefail

HOST="${CHECK_HOST:-unraid-odoo}"
IMAGE=int-filemanager-odoo:19.0-ocr
R=/tmp/kpvwodoo
TAG=e2e$RANDOM

cd "$(git rev-parse --show-toplevel)"
cleanup() {
  ssh "$HOST" "docker rm -f kp_pg kp_vw >/dev/null 2>&1; docker network rm kp_net >/dev/null 2>&1; rm -rf $R" || true
}
trap cleanup EXIT

ssh "$HOST" "set -e; rm -rf $R; mkdir -p $R/addons $R/data $R/pylib $R/ssl; chmod 777 $R/data $R/pylib
  docker rm -f kp_pg kp_vw >/dev/null 2>&1 || true; docker network rm kp_net >/dev/null 2>&1 || true
  docker network create kp_net >/dev/null
  docker run -d --name kp_pg --network kp_net -e POSTGRES_USER=odoo -e POSTGRES_PASSWORD=odoo -e POSTGRES_DB=postgres --tmpfs /var/lib/postgresql/data postgres:17 >/dev/null
  openssl req -x509 -nodes -newkey rsa:2048 -days 2 -subj /CN=kp_vw -addext subjectAltName=DNS:kp_vw -keyout $R/ssl/key.pem -out $R/ssl/cert.pem >/dev/null 2>&1
  chmod 644 $R/ssl/*.pem
  docker run -d --name kp_vw --network kp_net -v $R/ssl:/ssl:ro -e SIGNUPS_ALLOWED=true -e I_REALLY_WANT_VOLATILE_STORAGE=true \
    -e DOMAIN=https://kp_vw -e ROCKET_PORT=443 -e 'ROCKET_TLS={certs=\"/ssl/cert.pem\",key=\"/ssl/key.pem\"}' \
    -e LOGIN_RATELIMIT_MAX_BURST=1000 -e LOGIN_RATELIMIT_SECONDS=1 vaultwarden/server:latest >/dev/null
  docker run --rm --user root --entrypoint python3 -v $R/pylib:/pylib $IMAGE -m pip install --quiet --target /pylib --break-system-packages pykeepass >/dev/null 2>&1
  for i in \$(seq 1 30); do docker logs kp_vw 2>&1 | grep -q 'Rocket has launched' && break; sleep 1; done"
tar -c --exclude=__pycache__ int_keepass | ssh "$HOST" "tar -x -C $R/addons"

# the account: made like a Bitwarden client does, with the script of the experiment
ssh "$HOST" "docker run --rm --network kp_net -e REQUESTS_CA_BUNDLE=/ssl/cert.pem -v $R/ssl:/ssl:ro -v $R/addons/int_keepass:/m:ro \
  --entrypoint python3 $IMAGE /m/tools/vaultwarden_experiment.py https://kp_vw /m $TAG 2>&1 | grep -E 'checks passed|FAIL'"
PIN=$(ssh "$HOST" "openssl x509 -in $R/ssl/cert.pem -noout -fingerprint -sha256" | sed 's/.*=//; s/://g')

ssh "$HOST" "docker run --rm --name kp_odoo --entrypoint /entrypoint.sh --network kp_net \
    -e HOST=kp_pg -e USER=odoo -e PASSWORD=odoo -e PYTHONPATH=/pylib \
    -e INT_VW_URL=https://kp_vw -e INT_VW_EMAIL=pbkdf2-$TAG@example.test -e 'INT_VW_PASSWORD=pässwörd-€-$TAG' -e INT_VW_PIN=$PIN \
    -v $R/pylib:/pylib:ro -v $R/addons:/mnt/extra-addons:ro -v $R/data:/var/lib/odoo \
    $IMAGE odoo --addons-path=/mnt/extra-addons,/usr/lib/python3/dist-packages/odoo/addons \
    -d kp_test -i int_keepass --test-tags /int_keepass,external/int_keepass --stop-after-init --workers=0 --max-cron-threads=0 \
    --log-level=test > $R/tests.log 2>&1 || true
  grep -nE 'ERROR|FAIL|post-tests' $R/tests.log | cut -c1-220 | head -20; grep -E '^[A-Za-z_.]*(Error|Exception|UserError)[:(]|AssertionError' $R/tests.log | cut -c1-260 | sort | uniq -c | head -12; grep -E 'Vaultwarden request failed' $R/tests.log | cut -c1-400 | sort | uniq -c | head -4"
