#!/usr/bin/env bash
# Compiles every OWL template of the v2 explorer with the real OWL (the copy Odoo ships) in
# jsdom, after applying the t-inherit xpaths to the core templates - what the browser would
# only report at render time. See tools/v2check/owlcheck/. Needs Node and npm locally
# (jsdom is installed on first use) and the Tower test image for OWL and the core templates.
set -euo pipefail

HOST="${V2CHECK_HOST:-unraid}"
IMAGE=odoo:19.0-hm-test
CORE=/usr/lib/python3/dist-packages/odoo/addons/web/static
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/owlcheck"
ROOT="$(git rev-parse --show-toplevel)"

mkdir -p "$HERE/core_templates"
if [[ ! -f "$HERE/owl.js" ]]; then
  ssh "$HOST" "docker run --rm --entrypoint cat $IMAGE $CORE/lib/owl/owl.js" >"$HERE/owl.js"
fi
for name in list kanban; do
  ssh "$HOST" "docker run --rm --entrypoint cat $IMAGE $CORE/src/views/$name/${name}_controller.xml" \
    >"$HERE/core_templates/${name}_controller.xml"
done
[[ -d "$HERE/node_modules" ]] || (cd "$HERE" && npm install --no-audit --no-fund >/dev/null)

merged="$(mktemp)"
trap 'rm -f "$merged" "$merged.own"' EXIT
PYTHON="$(command -v python3 || echo "py -3.13")"
$PYTHON "$HERE/merge_templates.py" "$ROOT/int_filemanager" "$merged"
node "$HERE/compile.mjs" "$merged"
node "$HERE/render_check.mjs"
