#!/usr/bin/env bash
# Run Odoo's own lint tests (odoo/addons/test_lint) over all addon paths, including our modules.
#
# Why: test_lint is what Odoo's CI checks mechanically (pylint with custom checkers, manifest,
# __init__, docstring, ESLint, JS translations, ...); see docs/odoo_konventionen_2026-09-26.md
# section 9. pylint is not part of the odoo image, so it is mounted via PYTHONPATH.
#
# Runs on the Tower host (needs docker, the PostgreSQL test container and a pylint directory).
# NOT yet run on Tower; the same Odoo command was verified in a cloud session with a venv
# (docs/odoo_regeln_index_2026-10-02.md, "Prüfautomatik").
#
# Usage (from the repo root):  scripts/lint/run_test_lint.sh
# Environment (defaults for the fmtest setup, see docs/int_filemanager_v2_uebergabe_2026-09-26.md):
#   IMAGE      odoo image                       (odoo:19.0-hm-test)
#   PG_HOST    PostgreSQL container name        (fmtest_pg)
#   PG_NET     docker network of PG_HOST        (fmtest-net)
#   PG_USER    database role                    (odoo)
#   PG_PWFILE  file holding the role password   (/mnt/user/appdata/fmtest/.pgpw)
#   PYLIB      host dir with pylint (pip install --target)  (/mnt/user/appdata/fmtest/pylib_lint)
set -euo pipefail

IMAGE=${IMAGE:-odoo:19.0-hm-test}
PG_HOST=${PG_HOST:-fmtest_pg}
PG_NET=${PG_NET:-fmtest-net}
PG_USER=${PG_USER:-odoo}
PG_PWFILE=${PG_PWFILE:-/mnt/user/appdata/fmtest/.pgpw}
PYLIB=${PYLIB:-/mnt/user/appdata/fmtest/pylib_lint}
REPO=$(cd "$(dirname "$0")/../.." && pwd)
DB="lint_$(date +%s)"

if [ ! -d "$PYLIB/pylint" ]; then
    echo "pylint missing in $PYLIB; install once with:" >&2
    echo "  docker run --rm -v $PYLIB:/out --entrypoint pip $IMAGE install --target /out --break-system-packages pylint" >&2
    exit 2
fi
PGPW=$(cat "$PG_PWFILE")

cleanup() {
    docker exec -e PGPASSWORD="$PGPW" "$PG_HOST" dropdb -U "$PG_USER" --if-exists "$DB" >/dev/null 2>&1 || true
}
trap cleanup EXIT

# --test-tags /test_lint implies --test-enable; -i test_lint creates the module in a throw-away DB.
docker run --rm --network "$PG_NET" \
    -v "$REPO":/mnt/lint-addons:ro \
    -v "$PYLIB":/mnt/pylib:ro \
    -e PYTHONPATH=/mnt/pylib \
    --entrypoint odoo "$IMAGE" \
    -d "$DB" --db_host "$PG_HOST" --db_user "$PG_USER" --db_password "$PGPW" \
    --addons-path /usr/lib/python3/dist-packages/odoo/addons,/mnt/lint-addons \
    -i test_lint --test-tags /test_lint --stop-after-init --without-demo --http-port 8199 \
    "$@"
