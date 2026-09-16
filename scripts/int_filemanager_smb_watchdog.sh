#!/bin/bash
# int_filemanager SMB-Watchdog (2026-09-16) - prueft periodisch, ob die drei Remote-SMB-
# Freigaben unter /mnt/remotes (HM-FL01 Daten/Datenbank, 192.100.0.102 Transfer) noch
# antworten, und haengt eine haengende Freigabe gezielt neu ein, BEVOR sie den ganzen Unraid-
# Host mitreisst (zweimal am 2026-09-16 live beobachtet: eine wedged CIFS-Sitzung blockiert
# im Kernel unbegrenzt, jeder Prozess, der den Pfad beruehrt - auch Docker/shfs fuer ANDERE,
# unbeteiligte Container - haengt sich dadurch mit auf, bis nur noch ein harter Reboot hilft).
#
# Sicherheits-Design (wichtig, kein normales Skript): ein "stat"-Check auf einer bereits toten
# CIFS-Freigabe haengt selbst unbegrenzt im D-Zustand fest und ist NICHT per SIGTERM/timeout(1)
# abbrechbar (Kernel liefert das Signal an einen unterbrechbaren Wartezustand erst nach
# Abschluss der IO aus). Deshalb laeuft jeder Check im HINTERGRUND (&), das Hauptskript wartet
# NICHT per "wait" darauf, sondern pollt nur bis zu CHECK_TIMEOUT Sekunden auf eine Marker-
# Datei - laeuft die Zeit ab, gilt die Freigabe als haengend, unabhaengig davon, ob der
# Hintergrund-Check jemals zurueckkehrt (der haengt dann harmlos fuer sich alleine weiter, bis
# sich das Problem von selbst loest oder der naechste Reboot aufraeumt).
#
# umount -l (lazy unmount) statt normalem umount: trennt den Mountpoint sofort aus dem
# Namespace, OHNE auf die haengende zugrunde liegende IO zu warten - das ist die in der
# Unraid-Community dokumentierte Standardloesung fuer genau dieses Symptom (siehe Recherche
# 2026-09-16). rc.unassigned mount danach baut eine FRISCHE Verbindung auf, beruehrt also
# nicht mehr die alte, verklemmte - deshalb dort ein normaler timeout(1)-Wrapper als
# zusaetzliche Absicherung ausreichend (ein echter Netzwerk-Connect-Timeout ist unterbrechbar,
# anders als der urspruengliche D-Zustand-Hang).
#
# ensure_soft_mount_patch() (siehe unten) haertet zusaetzlich die Unassigned-Devices-eigene
# Mount-Option selbst (hard -> soft,timeo=30,retrans=2, siehe lib.php:1826) - bei JEDEM Lauf
# dieses Watchdogs neu, nicht nur einmalig oder beim Boot. Ein reiner Boot-Zeit-Patch (z.B. in
# /boot/config/go) haette hier tagelang eine Luecke offen gelassen, bis der naechste Reboot
# faellig ist - ein Plugin-Update koennte in der Zwischenzeit unbemerkt auf "hard" zurueckfallen.

LOG_DIR="/boot/config/plugins/user.scripts/scripts/int_filemanager_smb_watchdog"
LOG="$LOG_DIR/watchdog.log"
CHECK_TIMEOUT=5
REMOUNT_TIMEOUT=20
UD_LIB="/usr/local/emhttp/plugins/unassigned.devices/include/lib.php"

mkdir -p "$LOG_DIR"

log() {
    echo "$(date '+%F %T') $1" >> "$LOG"
    # Log-Datei nicht unbegrenzt wachsen lassen - letzte 2000 Zeilen reichen fuer die
    # Fehlersuche, mehr braucht kein Watchdog-Log dieser Groessenordnung (bei jedem Lauf
    # hoechstens ein bis zwei Zeilen).
    tail -n 2000 "$LOG" > "$LOG.tmp" 2>/dev/null && mv "$LOG.tmp" "$LOG"
}

# Haertet die Unassigned-Devices-Mount-Option (hard -> soft,timeo=30,retrans=2) bei JEDEM
# Lauf dieses Watchdogs neu, nicht nur einmalig oder nur beim Boot (Nutzereinwand 2026-09-16:
# "ein erneuter Boot kann aber erst in mehreren Tagen erfolgen" - ein Plugin-Update koennte die
# Datei also tagelang unbemerkt zurueck auf "hard" setzen, bevor der naechste Boot das wieder
# reparieren wuerde). sed matcht nur, wenn die alte Zeichenkette noch da ist - bereits gepatcht
# heisst automatisch kein Treffer, also ein reines No-op ohne Fehler und ohne Log-Eintrag.
# Damit ist der Patch von Natur aus idempotent, ohne eine eigene "schon gepatcht"-Markierung
# fuehren zu muessen. "hard" wird bewusst NUR im SMB-spezifischen Kontext ersetzt (die direkt
# danach folgende Zeichenkette ",relatime,noserverino,nounix" kommt in lib.php ausschliesslich
# in der SMB-Mount-Zeile vor, nicht in der separaten NFS-Zeile - siehe Recherche 2026-09-16),
# damit kein anderer "hard"-Treffer in der Datei versehentlich mitgeaendert wird.
ensure_soft_mount_patch() {
    if [ ! -f "$UD_LIB" ]; then
        return
    fi
    if grep -q ',hard,relatime,noserverino,nounix,' "$UD_LIB"; then
        sed -i 's/,hard,relatime,noserverino,nounix,/,soft,timeo=30,retrans=2,relatime,noserverino,nounix,/' "$UD_LIB"
        log "PATCH ANGEWENDET: $UD_LIB auf soft,timeo=30,retrans=2 gehaertet (Plugin-Update hatte auf hard zurueckgesetzt, oder Erstlauf)"
    fi
}

check_and_fix() {
    local mountpoint="$1"
    local share_key="$2"
    local marker
    marker=$(mktemp -u "/tmp/int_filemanager_smb_check.XXXXXX")

    ( stat "$mountpoint" >/dev/null 2>&1 && touch "$marker.done" ) &

    local waited=0
    while [ ! -f "$marker.done" ] && [ "$waited" -lt "$CHECK_TIMEOUT" ]; do
        sleep 1
        waited=$((waited + 1))
    done

    if [ -f "$marker.done" ]; then
        rm -f "$marker.done"
        return 0
    fi

    log "HAENGT: $mountpoint antwortet nicht innerhalb ${CHECK_TIMEOUT}s - haenge neu ein ($share_key)"
    umount -l "$mountpoint" 2>>"$LOG"
    if timeout "$REMOUNT_TIMEOUT" /usr/local/sbin/rc.unassigned mount "$share_key" >>"$LOG" 2>&1; then
        log "OK: $share_key neu eingehaengt"
    else
        log "FEHLGESCHLAGEN: $share_key konnte nicht neu eingehaengt werden - manuelle Pruefung noetig"
    fi
}

ensure_soft_mount_patch

check_and_fix "/mnt/remotes/HM-FL01.HERRMANN_Daten" "//HM-FL01.HERRMANN/Daten"
check_and_fix "/mnt/remotes/HM-FL01.HERRMANN_Datenbank/HM-Datenbank" "//HM-FL01.HERRMANN/Datenbank"
check_and_fix "/mnt/remotes/192.100.0.102_Transfer" "//192.100.0.102/Transfer"
