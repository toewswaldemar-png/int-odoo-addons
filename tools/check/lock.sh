#!/usr/bin/env bash
# Sourced by the scripts of tools/check, which share one test setup on the Tower: two runs of the
# same kind (from two workstations) would overwrite each other's directories and database.
#
#   take_lock <kind>   lets one run of this kind in; another stops and names the holder, or waits
#                      for LOCK_WAIT seconds (default 0)
#   release_lock       gives it back; the scripts call it from their exit trap
#
# Different kinds do not wait for each other (they use different directories and databases). A
# lock older than LOCK_TTL seconds (default 2 hours) is taken over: a run that was cut off cannot
# release it. Needs HOST and BASE.

LOCK_KIND=""
LOCK_TOKEN=""

take_lock() {
  LOCK_KIND="$1"
  LOCK_TOKEN="$(hostname)-$$-$(date +%s)"
  local waited=0 answer
  while true; do
    answer="$(ssh "$HOST" bash -s -- "$BASE/locks" "$LOCK_KIND" "$LOCK_TOKEN" "${LOCK_TTL:-7200}" \
      "$(git rev-parse --short HEAD)" <<'REMOTE'
dir="$1/$2"; token=$3; ttl=$4; commit=$5
mkdir -p "$1"
now=$(date +%s)
if ! mkdir "$dir" 2>/dev/null; then
  age=$((now - $(stat -c %Y "$dir")))
  if [ "$age" -le "$ttl" ]; then
    echo "BUSY $(cut -d' ' -f2- "$dir/owner" 2>/dev/null), since $((age / 60)) min"
    exit 0
  fi
fi
echo "$now $token $commit" > "$dir/owner"
echo TAKEN
REMOTE
    )"
    [[ "$answer" == TAKEN ]] && return 0
    if ((waited >= ${LOCK_WAIT:-0})); then
      echo "$(basename "$0"): the test machine is in use for '$LOCK_KIND': ${answer#BUSY }" >&2
      echo "  wait with LOCK_WAIT=<seconds>, or try again later" >&2
      LOCK_TOKEN=""
      exit 1
    fi
    sleep 20
    waited=$((waited + 20))
  done
}

release_lock() {
  [[ -n "$LOCK_TOKEN" ]] || return 0
  ssh "$HOST" "grep -q ' $LOCK_TOKEN ' $BASE/locks/$LOCK_KIND/owner 2>/dev/null && rm -rf $BASE/locks/$LOCK_KIND" || true
}
