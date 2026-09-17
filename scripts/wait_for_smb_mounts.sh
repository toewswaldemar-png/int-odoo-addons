#!/bin/bash
# int_filemanager: Container-Entrypoint-Wrapper, der beim Start wartet, bis alle drei SMB-
# Freigaben unter /mnt/hm-daten wirklich als CIFS gemountet sind - nicht nur Unraids leerer
# tmpfs-Platzhalter fuer eine Unassigned-Devices-Freigabe, die noch nicht fertig eingehaengt ist.
#
# Grund: Docker baut Bind-Mounts bei JEDEM Container-Start neu auf (live am 2026-09-17 bestaetigt
# - derselbe Mechanismus, der beim Absturz einen Tag zuvor griff). Startet Odoo19 zu frueh im
# Boot-Race gegen Unraids Unassigned-Devices-Autostart (eigenstaendiges Plugin, NICHT an den
# Array-Start-/Docker-Start-Zeitpunkt gekoppelt), bindet er dauerhaft den leeren Platzhalter statt
# der echten Freigabe ein - ein spaeteres echtes Mounten auf dem Host zieht wegen des statischen
# Bind-Mount-Snapshots NICHT mehr nach, ohne Container-Neustart.
#
# Bricht dieses Skript mit exit 1 ab, uebernimmt RestartPolicy=unless-stopped (siehe Docker-
# Template) den Rest: Docker startet automatisch mit eingebautem Backoff neu, und jeder neue
# Start baut die Bind-Mounts frisch auf - sieht also einen inzwischen ggf. echten Host-Mount.
set -eu

MOUNTS=(
    /mnt/hm-daten/Daten
    /mnt/hm-daten/Produktiv-HM-Datenbank
    /mnt/hm-daten/Transfer
)
TIMEOUT=60
INTERVAL=5

all_ready() {
    local m fstype
    for m in "${MOUNTS[@]}"; do
        # Bei gestapelten Mounts auf demselben Zielpfad (bekannter, separater Watchdog-Bug -
        # false-positive-Remounts stapeln gelegentlich einen zweiten Mount obendrauf) liefert
        # findmnt mehrere Zeilen zurueck. Die LETZTE Zeile ist die zuletzt gemountete, also die
        # tatsaechlich wirksame/sichtbare - nur die zaehlt, nicht ob irgendeine Zeile "cifs" ist.
        fstype=$(findmnt -no FSTYPE "$m" 2>/dev/null | tail -n1)
        [ "$fstype" = "cifs" ] || return 1
    done
    return 0
}

waited=0
while ! all_ready; do
    if [ "$waited" -ge "$TIMEOUT" ]; then
        echo "wait_for_smb_mounts: SMB-Freigaben nach ${TIMEOUT}s immer noch nicht echt gemountet - breche ab, RestartPolicy uebernimmt" >&2
        exit 1
    fi
    echo "wait_for_smb_mounts: warte auf echte SMB-Mounts (${waited}/${TIMEOUT}s)..." >&2
    sleep "$INTERVAL"
    waited=$((waited + INTERVAL))
done

exec /entrypoint.sh "$@"
