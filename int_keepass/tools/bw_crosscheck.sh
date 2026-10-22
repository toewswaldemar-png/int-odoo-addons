#!/bin/sh
# Runs in a node container next to the throwaway Vaultwarden: the official Bitwarden CLI reads
# the accounts that vaultwarden_experiment.py made, then adds an item of its own that
# vaultwarden_readback.py reads back. Arguments: BASE_URL TAG.
set -e
BASE="$1"
TAG="$2"
# the newest CLI calls /identity/accounts/prelogin/password, which this Vaultwarden does not know yet
npm install -g "@bitwarden/cli@${BW_VERSION:-2025.8.0}" --silent >/dev/null 2>&1
bw config server "$BASE" >/dev/null
export BW_PASSWORD="pässwörd-€-$TAG"
names='const d=JSON.parse(require("fs").readFileSync(0));console.log(d.map(x=>x.name+(x.login?" ("+x.login.username+", "+((x.login.uris||[])[0]||{}).uri+")":"")).sort().join(" | "))'
for label in pbkdf2 argon2id; do
  session=$(bw login "$label-$TAG@example.test" --passwordenv BW_PASSWORD --raw)
  echo "== official CLI, $label"
  echo "folders: $(bw list folders --session "$session" | node -e "$names")"
  echo "items:   $(bw list items --session "$session" | node -e "$names")"
  echo '{"type":1,"name":"FromBw","folderId":null,"login":{"username":"bwuser","password":"BWSECRET","uris":[{"uri":"https://bw.example"}]}}' \
    | bw encode | bw create item --session "$session" >/dev/null
  bw logout >/dev/null
done
