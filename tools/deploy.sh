#!/usr/bin/env bash
# Deploys the committed state (HEAD) of the int_filemanager* modules to the LIVE Odoo on the Tower:
# backs up the old module folders, copies the new ones, updates them in the database, restarts Odoo.
#
# Usage (from the repo, Git Bash):  DEPLOY_DB=<database> tools/deploy.sh
#
# Settings (environment):
#   DEPLOY_DB        database to update (required; DEPLOY_DB=? lists the databases of the Tower)
#   DEPLOY_HOST      SSH alias of the Tower (default: unraid)
#   DEPLOY_CONTAINER Odoo container (default: odoo)
#   DEPLOY_PG        PostgreSQL container, only used to list databases (default: odoo_db)
#   DEPLOY_ADDONS    extra-addons folder of the live Odoo on the Tower
#                    (default: /mnt/user/appdata/odoo/extra-addons)
#   DEPLOY_MODULES   comma list of modules to copy and update (default: every int_filemanager*)
#   DEPLOY_DRY=1     show what would happen, change nothing
#   DEPLOY_YES=1     do not ask before touching the live instance
#   DEPLOY_DIRTY=1   deploy although the modules have uncommitted changes (HEAD is still what is copied)
#
# Only the Python libraries and programs of the modules are checked, not installed: they belong to
# the image (Dockerfile in the repo root). A missing one is reported, the deploy goes on.
# Rollback: the old folders stay in <DEPLOY_ADDONS>/../extra-addons.bak-<stamp>; the last line of
# the run prints the command that puts them back.
set -euo pipefail

HOST="${DEPLOY_HOST:-unraid}"
CONTAINER="${DEPLOY_CONTAINER:-odoo}"
PG="${DEPLOY_PG:-odoo_db}"
ADDONS="${DEPLOY_ADDONS:-/mnt/user/appdata/odoo/extra-addons}"
DB="${DEPLOY_DB:-}"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="$ADDONS.bak-$STAMP"

cd "$(git rev-parse --show-toplevel)"

if [[ "$DB" == "?" || -z "$DB" ]]; then
  echo "deploy.sh: DEPLOY_DB is not set. Databases in $PG:" >&2
  ssh "$HOST" "docker exec $PG psql -U odoo -d postgres -Atc \"select datname from pg_database where not datistemplate and datname <> 'postgres'\"" >&2 || true
  exit 1
fi

if [[ -n "${DEPLOY_MODULES:-}" ]]; then
  IFS=, read -r -a MODULES <<<"$DEPLOY_MODULES"
else
  mapfile -t MODULES < <(git ls-tree --name-only HEAD | grep '^int_filemanager' | sort)
fi
for m in "${MODULES[@]}"; do
  git cat-file -e "HEAD:$m/__manifest__.py" 2>/dev/null || { echo "deploy.sh: $m is not a module in HEAD" >&2; exit 1; }
done
LIST="$(IFS=,; echo "${MODULES[*]}")"

# What gets copied is HEAD, so uncommitted work would be missing from the Tower: say so.
if [[ -n "$(git status --porcelain -- "${MODULES[@]}")" && "${DEPLOY_DIRTY:-0}" != 1 ]]; then
  echo "deploy.sh: uncommitted changes in the modules; commit them or set DEPLOY_DIRTY=1 (HEAD is deployed)" >&2
  git status --short -- "${MODULES[@]}" >&2
  exit 1
fi
git fetch -q origin master 2>/dev/null || true
if git rev-parse -q --verify origin/master >/dev/null && [[ "$(git rev-parse HEAD)" != "$(git rev-parse origin/master)" ]]; then
  echo "deploy.sh: note: HEAD ($(git rev-parse --short HEAD)) differs from origin/master ($(git rev-parse --short origin/master))" >&2
fi

echo "== deploy $(git rev-parse --short HEAD) $(git log -1 --format=%s)"
echo "   host $HOST, container $CONTAINER, database $DB"
echo "   addons $ADDONS (backup $BACKUP)"
echo "   modules $LIST"

if [[ "${DEPLOY_DRY:-0}" == 1 ]]; then
  echo "== dry run, nothing changed"
  exit 0
fi
if [[ "${DEPLOY_YES:-0}" != 1 ]]; then
  read -r -p "Touch the LIVE instance? [y/N] " answer
  [[ "$answer" == [yYjJ] ]] || { echo "deploy.sh: cancelled" >&2; exit 1; }
fi

# The Tower must be reachable and the container must exist before anything is copied.
ssh "$HOST" "test -d '$ADDONS' && docker inspect -f '{{.State.Status}}' $CONTAINER" >/dev/null \
  || { echo "deploy.sh: $ADDONS or container $CONTAINER not found on $HOST" >&2; exit 1; }

echo "== libraries in the image"
ssh "$HOST" "docker exec $CONTAINER sh -c '
  for lib in mutagen pdfplumber ocrmypdf pypdfium2 jwt; do
    python3 -c \"import \$lib\" 2>/dev/null || echo \"   missing Python library: \$lib\"
  done
  for bin in tesseract soffice qpdf gs; do
    command -v \$bin >/dev/null || echo \"   missing program: \$bin\"
  done'" || true
echo "   (a missing one means: rebuild the image from the Dockerfile in the repo root)"

echo "== copy"
STAGE="$ADDONS.stage-$STAMP"
ssh "$HOST" "rm -rf '$STAGE' && mkdir -p '$STAGE'"
git archive HEAD -- "${MODULES[@]}" | ssh "$HOST" "tar -x --no-same-owner -C '$STAGE'"

echo "== swap (old folders go to the backup)"
ssh "$HOST" bash -s -- "$ADDONS" "$STAGE" "$BACKUP" "${MODULES[@]}" <<'REMOTE'
set -euo pipefail
addons=$1; stage=$2; backup=$3; shift 3
mkdir -p "$backup"
for m in "$@"; do
  [ -d "$addons/$m" ] && mv "$addons/$m" "$backup/$m"
  mv "$stage/$m" "$addons/$m"
done
rmdir "$stage"
REMOTE

# Same database settings as the official image's entrypoint passes; --no-http keeps the throwaway run
# from fighting the running server for the port.
echo "== update modules in $DB"
if ! ssh "$HOST" "docker exec $CONTAINER sh -c 'odoo -d \"\$1\" -u \"\$2\" --stop-after-init --no-http \
    --db_host \"\${HOST:-db}\" --db_user \"\${USER:-odoo}\" --db_password \"\${PASSWORD:-odoo}\"' sh '$DB' '$LIST'"; then
  echo "deploy.sh: the module update failed; the old folders are in $BACKUP" >&2
  echo "  put them back:  ssh $HOST 'cd $ADDONS && rm -rf ${MODULES[*]} && cp -a $BACKUP/* .'" >&2
  exit 1
fi

echo "== restart"
ssh "$HOST" "docker restart $CONTAINER" >/dev/null
for _ in $(seq 1 30); do
  if ssh "$HOST" "docker exec $CONTAINER curl -fsS -o /dev/null http://localhost:8069/web/login" 2>/dev/null; then
    echo "== Odoo answers again"
    echo "   rollback:  ssh $HOST 'cd $ADDONS && rm -rf ${MODULES[*]} && cp -a $BACKUP/* . && docker restart $CONTAINER'"
    exit 0
  fi
  sleep 5
done
echo "deploy.sh: Odoo does not answer after 150 s; look at: ssh $HOST docker logs --tail 80 $CONTAINER" >&2
echo "  rollback:  ssh $HOST 'cd $ADDONS && rm -rf ${MODULES[*]} && cp -a $BACKUP/* . && docker restart $CONTAINER'" >&2
exit 1
