#!/usr/bin/env bash
# odoo-ls in parse mode over our addons, evaluated by odoo_ls_check.py.
#
# odoo-ls (https://github.com/odoo/odoo-ls) knows the Odoo registry and finds unknown models/fields,
# models missing from `depends`, invalid domain fields, wrong call arguments ... (see
# docs/odoo_konventionen_2026-09-26.md section 9). Diagnostics are only raised in the tracked folder
# (= this repository), so the Odoo core does not drown the result.
#
# Two modes (MODE):
#   local   binary on this machine (cloud session, workstation)
#   docker  throw-away container from the odoo image, as on Tower (no network)
#
# Environment:
#   OLS_DIR      directory with odoo_ls_server and typeshed/   (local: required; docker: /tmp/odoo-ls)
#   ODOO_PATH    Odoo community path (the directory that contains odoo/ and addons/)  (local: required)
#   PYTHON       python of the Odoo environment                (local: python3)
#   IMAGE        odoo image                                    (docker: odoo:19.0-hm-test)
#   OLS_OUT      JSON output                                   (/tmp/odoo_ls_out.json)
# Extra arguments are passed to odoo_ls_check.py (e.g. --include-legacy --show-info).
set -euo pipefail

MODE=${MODE:-local}
REPO=$(cd "$(dirname "$0")/../.." && pwd)
OLS_OUT=${OLS_OUT:-/tmp/odoo_ls_out.json}

case "$MODE" in
local)
    : "${OLS_DIR:?set OLS_DIR to the directory with odoo_ls_server and typeshed/}"
    : "${ODOO_PATH:?set ODOO_PATH to the Odoo community checkout}"
    "$OLS_DIR/odoo_ls_server" --parse \
        -c "$ODOO_PATH" -a "$REPO" -t "$REPO" \
        --python "${PYTHON:-python3}" \
        --stdlib "$OLS_DIR/typeshed/stdlib" -s "$OLS_DIR/typeshed/stubs" \
        -o "$OLS_OUT" --log-level error
    ;;
docker)
    OLS_DIR=${OLS_DIR:-/tmp/odoo-ls}
    IMAGE=${IMAGE:-odoo:19.0-hm-test}
    OUT_DIR=$(dirname "$OLS_OUT")
    # Libraries outside the image (e.g. wsgidav) must be visible via PYTHONPATH, otherwise
    # odoo-ls reports false positives; mount them and extend PYLIB_ENV if needed.
    docker run --rm --network none \
        -v "$OLS_DIR":/ols:ro -v "$REPO":/mnt/lint-addons:ro -v "$OUT_DIR":/out \
        ${PYLIB_ENV:+-e PYTHONPATH="$PYLIB_ENV"} \
        --entrypoint /ols/odoo_ls_server "$IMAGE" --parse \
        -c /usr/lib/python3/dist-packages/odoo -a /mnt/lint-addons -t /mnt/lint-addons \
        --python python3 --stdlib /ols/typeshed/stdlib -s /ols/typeshed/stubs \
        -o "/out/$(basename "$OLS_OUT")" --log-level error
    # the tracked folder inside the container is /mnt/lint-addons: map it back for the evaluator
    sed -i "s#file:///mnt/lint-addons#file://$REPO#g" "$OLS_OUT"
    ;;
*)
    echo "unknown MODE: $MODE" >&2
    exit 2
    ;;
esac

python3 "$(dirname "$0")/odoo_ls_check.py" "$OLS_OUT" "$@"
