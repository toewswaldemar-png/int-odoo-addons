# int_filemanager: externe Änderungen werden nicht mehr indexiert (Regression, ungelöst)

Stand 2026-09-17, direkte Fortsetzung des rshared-Mount-Leak-Vorfalls vom selben Tag (siehe
[[project_hm_odoo_filemanager_rshared_leak]] im Claude-Memory bzw. Session-Historie). Festgehalten,
damit eine andere Session/ein anderer Tag hier nahtlos weitermachen kann, ohne die Diagnose von
vorne zu beginnen.

## Symptom

Nutzer legt einen Ordner über einen **externen SMB-Client** an (getestet: Windows-Laptop, Freigabe
`EDV-Datenbank` → Ordner `Test`, sowie separat ein Ordner `0001`) - der neue Eintrag erscheint
**nicht** in Odoo/int_filemanager, auch nach mehreren Minuten Wartezeit nicht. Laut Nutzer **hat
das vorher funktioniert** (deckt sich mit der ursprünglichen Watcher-Doku vom 2026-08-26: "Änderungen
von außerhalb Odoos landen jetzt in Sekunden im Index") - das ist also eine echte Regression, keine
grundsätzliche Einschränkung.

## Live bestätigt (empirisch, nicht vermutet)

1. **Ordner existiert wirklich auf der Freigabe** - per SSH direkt auf `/mnt/remotes/HM-FL01.HERRMANN_Datenbank/HM-Datenbank/EDV-Datenbank/Test` verifiziert (`stat` zeigt echte Birth-Zeit).
2. **DB-Query bestätigt: kein Eintrag** - `select ... from int_filemanager_file where path like '%EDV-Datenbank/Test%'` liefert nichts, weder für "Test" noch für "0001" noch für einen künstlichen Testordner, der über die eigene, separate Host-CIFS-Mount-Sitzung angelegt wurde.
3. **Der Watcher selbst funktioniert** - Testordner **von innerhalb des laufenden Odoo19-Containers** angelegt (`docker exec Odoo19 mkdir /mnt/hm-daten/Daten/_watcher_selftest_...`) wurde **innerhalb weniger Sekunden** indexiert. Der Inotify-Mechanismus im Container ist also grundsätzlich aktiv und funktionsfähig.
4. **Nicht durch den rshared→rslave-Wechsel verursacht** - sauberer A/B-Test (identische Testdatei einmal mit `bind-propagation=rshared`, einmal mit `rslave` auf dem Docker-Mount) zeigte in **beiden** Fällen identisches Fehlverhalten (keine Indexierung). Die heutige Propagation-Änderung ist also nicht die Ursache.
5. **Nicht durch die ~822 verwaisten Mount-Duplikate von den heutigen Tests verursacht** - nach einem sauberen Reboot (Mount-Zahl zurück auf 0, dann normal neu gemountet) wurde derselbe externe-Änderung-Test **erneut wiederholt und schlug wieder fehl** - sowohl über die Host-eigene CIFS-Sitzung als auch über den echten Laptop-Client.
6. **Nicht durch `hard` vs. `soft` verursacht** (ursprünglich fuehrende Hypothese, jetzt widerlegt) -
   sauberer Test nach Reboot (siehe unten, damit `emhttpd`'s In-Memory-Cache von `lib.php` garantiert
   umgangen wird): Mount lief nachweislich mit `hard` (`findmnt` zeigte es live), Odoo19 wurde neu
   gestartet, danach exakt derselbe externe-Aenderung-Test wiederholt - **auch mit `hard` keine
   Indexierung**. Die heutige SMB-Watchdog-Mount-Options-Korrektur ist damit ebenfalls ausgeschlossen.
7. **Kein Code-Commit hat `watcher.py`/`models/` kürzlich angefasst** (`git log --since` heute Abend
   geprüft, keine Treffer) - keine versehentliche Regression durch die vielen UI-Fixes von heute.

## Bekannter Nebenschaden aus dem hard/soft-Test (WICHTIG, zuerst beheben)

Der `hard`-Test hat einen Seiteneffekt hinterlassen: **der `Daten`-Mount lief zuletzt live auf
`hard`** statt dem korrekten `soft` (siehe "Sicherheits-Notiz" unten warum das wichtig ist).
`lib.php` selbst steht bereits wieder korrekt auf `soft` (Datei-Inhalt verifiziert), aber
`emhttpd`s In-Memory-Cache hat das nicht übernommen (dasselbe Cache-Problem wie beim Testen selbst,
siehe unten) - ein Datei-Edit ohne Reboot reicht nicht. **Vor jeder weiteren Arbeit**: entweder
per Reboot sauber auf `soft` zurückstellen (garantiert wirksam), oder zumindest verifizieren, dass
der Live-Mount `soft` zeigt (`findmnt /mnt/remotes/HM-FL01.HERRMANN_Daten`) bevor man sich auf die
Watchdog-Hang-Schutzfunktion verlässt.

## `emhttpd`-Cache-Falle (fuer jeden weiteren Mount-Options-Test wichtig)

`emhttpd` läuft dauerhaft und liest `lib.php` offenbar beim ERSTEN tatsächlichen Mount-Vorgang nach
dem Boot ein, haelt den Inhalt danach im Speicher - ein reines `sed`-Edit auf der Datei plus
`rc.unassigned mount` reicht NICHT, um eine geänderte Mount-Option live wirksam zu machen, auch
nicht direkt nach einem Reboot, sobald bereits EIN Mount-Vorgang stattgefunden hat. Einzig
zuverlässiger Weg, eine `lib.php`-Änderung sauber zu testen: Datei VOR jedem weiteren Mount-Versuch
nach einem frischen Reboot ändern (vor dem allerersten `rc.unassigned mount`-Aufruf dieser Boot-
Session) - genau in dieser Reihenfolge wurde der `hard`-Test oben erfolgreich durchgeführt.

## Image-Spur getestet und ausgeschlossen (2026-09-17, Folgesession)

`Odoo19` testweise auf `odoo:latest` (bereits lokal vorhandenes Image, "Odoo version 19.0-20260817",
Image-Alter 18.08., aelter als das Custom-Image) zurueckgestellt - identische Mounts/Env/Ports/
RestartPolicy, nur `--entrypoint /entrypoint.sh` statt des `wait_for_smb_mounts.sh`-Wrappers (der
existiert im Standard-Image nicht, unproblematisch weil die Mounts zum Testzeitpunkt schon laufend
liefen, kein Boot-Race). Alter Container per `docker rename` als Instant-Rollback gesichert, nicht
geloescht.

**Ergebnis: Regression reproduziert sich identisch unter `odoo:latest`.** Ein von einem echten
Windows-Client angelegter Ordner (`EDV-Datenbank/Ordner2`, per `stat` auf der Freigabe verifiziert)
wurde nach >20s **nicht** indexiert (`select ... from int_filemanager_file where path ilike
'%Ordner2%'` liefert nichts). Watcher lief nachweislich aktiv und korrekt ("watcher active for
/mnt/hm-daten (69188 directories)" im Log) - ein Selbsttest von innerhalb des Containers
(`docker exec Odoo19 mkdir ...`) wurde im selben Zeitraum in 6s indexiert, exakt dasselbe
Failure-Pattern wie mit dem Custom-Image. Danach sauber zurueckgestellt auf
`int-filemanager-odoo:19.0-ocr` (HTTP 200 verifiziert).

**Damit: Odoo-Kernversion/OS-Paket-Differenz zwischen den beiden Images ist ausgeschlossen.** Die
Ursache liegt nicht in Odoo/Docker/Unraid auf dieser Seite - naechster Schritt ist ein Blick direkt
auf HM-FL01 (Windows-Server/-Freigabe selbst, z.B. ein Windows-Update dort, das Change-Notify
betrifft), oder `watcher.py`s Inotify-Maskeneinstellungen am Quellcode gegenlesen und/oder einen
periodischen Reconciliation-Fallback-Scan zusaetzlich zu reinem Inotify in Erwaegung ziehen.

**Nutzer konnte den Zeitpunkt "hat zuletzt funktioniert" nicht eingrenzen** - das Regressionsfenster
ist daher nicht bekannt (koennte am 2026-09-17 selbst, koennte aber auch schon laenger her sein und
nur jetzt zum ersten Mal aufgefallen sein).

## Eingrenzung: nur die drei CIFS-Remote-Mounts betroffen, nicht die lokale Array-Freigabe (2026-09-17, selbe Folgesession)

Ordner direkt auf `/mnt/user/HM-Daten` angelegt (SSH `mkdir`, **ausserhalb** der drei Unterordner
`Daten`/`Produktiv-HM-Datenbank`/`Transfer`, die die externen CIFS-Remotes ueberlagern) - das ist die
lokale Unraid-Array-Freigabe selbst, per einfachem `rslave`-Bind in den Container gemountet, keine
verschachtelte Mount-Kette. **Ergebnis: sofort live indexiert** (Anlegen und Loeschen jeweils
innerhalb derselben Sekunde in der DB nachvollzogen - `write_date` deckt sich exakt mit dem
`stat`-Zeitstempel). Ein erster Testlauf direkt nach Container-Neustart war noch durch den laufenden
Watcher-Startup-Scan verfaelscht (Treffer exakt zum "watcher active"-Log-Zeitpunkt, nicht beweiskraeftig
fuer Live-Inotify) - der zweite, sauber nach bestaetigtem Live-Modus wiederholte Test war eindeutig.

**Damit ist die Ursache eng eingegrenzt:** der Inotify-Mechanismus selbst, der `rslave`-Bind-Mount und
Odoo/Docker/Watcher-Code funktionieren nachweislich einwandfrei. Das Problem betrifft **spezifisch**
die drei extern gemounteten CIFS-Remote-Freigaben (`Daten`+`Produktiv-HM-Datenbank`←HM-FL01,
`Transfer`←192.100.0.102) - vermutlich propagieren Inotify-Events aus der verschachtelten Mount-Kette
(Unraid mountet die externe SMB-Freigabe selbst als CIFS-Client via Unassigned Devices, Docker
bind-mountet diesen CIFS-Mountpoint zusaetzlich in den Container) grundsaetzlich nicht durch, unabhaengig
von Docker-Propagation (das war schon vorher per A/B-Test `rshared`/`rslave` ausgeschlossen) oder
Odoo-Version (s.o.). Das verschiebt den Fokus weg von "irgendwo in Odoo/Docker" hin zu **"CIFS-Client-
Mount von Unraid auf HM-FL01/192.100.0.102 liefert grundsaetzlich keine Inotify-Events durch, egal was
darueber gebindet wird"** - ein bekanntes generelles Linux/CIFS-Verhalten (CIFS-Client-Mounts
unterstuetzen `inotify` fuer Fremdaenderungen oft gar nicht nativ, unabhaengig von Unraid/Docker) waere
damit die naheliegendste Erklaerung, noch nicht abschliessend verifiziert.

## Praezisierung + Korrektur einer aelteren Notiz: lokale Aenderungen auf dem CIFS-Mount funktionieren, nur fremde Server-Aenderungen nicht (2026-09-17, direkt danach)

Ordner direkt auf dem Host **auf demselben Pfad**, den der `Daten`-Sub-Bind ins Image spiegelt
(`/mnt/remotes/HM-FL01.HERRMANN_Daten`, per SSH `mkdir`, **ausserhalb** des Containers) angelegt -
**wurde ebenfalls sofort live indexiert** (Anlegen+Loeschen jeweils in derselben Sekunde). Das
widerspricht einer aelteren Notiz aus dem rshared-Mount-Leak-Vorfall vom Vortag, die exakt diese
Testmethode ("Testdatei direkt auf der Host-eigenen `/mnt/remotes/...`-CIFS-Mount-Sitzung angelegt")
als grundsaetzlich nicht Inotify-ausloesend beschrieben hatte - diese aeltere Aussage war offenbar
falsch oder bezog sich auf einen anderen/fehlerhaften Zustand zum damaligen Zeitpunkt; **die Memory-
Notiz [[project_hm_odoo_filemanager_rshared_leak]] sollte bei Gelegenheit entsprechend korrigiert
werden.**

**Damit ist das Bild jetzt vollstaendig klar:** JEDE Aenderung, die ueber Unraids eigenen CIFS-
Client-Mount laeuft - egal ob von innerhalb des Containers (`docker exec`), direkt auf dem Host-Pfad,
oder auf der lokalen Array-Freigabe - wird sofort live indexiert. **Ausschliesslich Aenderungen, die
ein ECHTER, unabhaengiger SMB-Client (ein Windows-Geraet, das sich direkt und eigenstaendig mit
HM-FL01 verbindet, unabhaengig von Unraids eigener Client-Session) auf dem Server vornimmt, werden
nicht indexiert.** Das ist exakt das erwartbare, dokumentierte Verhalten von Linux' CIFS-Client
(`cifs.ko`): lokale VFS-Operationen ueber den eigenen Mount loesen normale `fsnotify`/Inotify-Events
aus, aber Aenderungen, die ein ANDERER Client auf demselben SMB-Server vornimmt, erreichen den lokalen
VFS-Layer nur ueber SMB-Server-Push-Benachrichtigungen (Change-Notify/Directory-Leases) - und `cifs.ko`
uebersetzt diese in der Praxis nicht zuverlaessig in lokale Inotify-Events (bekannte, seit Jahren
dokumentierte Einschraenkung, keine unraid-/odoo-spezifische Macke).

**Konsequenz:** das ist strukturell **nicht per Mount-Option/Docker-Konfiguration loesbar** - eine rein
inotify-basierte Loesung kann echte externe SMB-Client-Aenderungen auf diesen drei Freigaben prinzipiell
nicht zuverlaessig erfassen. Der einzig robuste Fix ist ein **periodischer Reconciliation-Fallback-Scan
speziell fuer die drei CIFS-Remote-Mounts** (`Daten`, `Produktiv-HM-Datenbank`, `Transfer`) zusaetzlich
zu reinem Inotify - die lokale `HM-Daten`-Array-Freigabe braucht das laut den obigen Tests nicht, dort
reicht Inotify allein.

**Offener `hard`/`soft`-Nebenschaden von vorher weiterhin ungeklaert** (siehe Abschnitt oben) - noch
nicht separat verifiziert in dieser Folgesession.

**Vorschlag fuer die naechste Session:**
1. `hard`/`soft`-Nebenschaden beheben/verifizieren (siehe oben, weiterhin offen).
2. Periodischen Reconciliation-Scan fuer die drei CIFS-Remote-Mounts implementieren (Intervall
   abwaegen: haeufig genug fuer brauchbare Aktualitaet, aber nicht so haeufig wie der bisherige
   15-Min-Cron-Vollscan alle 1,38 Mio. Zeilen unnoetig belastet - ggf. nur die drei betroffenen
   Teilbaeume scannen, nicht den ganzen Baum).

## Finale Klärung (2026-09-17, dritte Folgesession): Server sendet grundsaetzlich kein CHANGE_NOTIFY

Nutzer bestand darauf, dass externe SMB-Aenderungen frueher sichtbar wurden - zu Recht angezweifelt,
weiteres Nachgraben ergab einen deutlich praeziseren Befund als die bisherige "cifs.ko liefert das
strukturell nicht"-Einordnung:

1. **`inotifywait` DIREKT am Host** (nicht im Container, nicht ueber Odoo) auf `EDV-Datenbank`
   angesetzt, waehrend Nutzer live ueber echten Windows-Client mehrere Testordner anlegte
   (`Ordner999`, `Watcher111`) - **0 Kernel-Inotify-Events**, obwohl die Ordner nachweislich real
   entstanden sind. Bestaetigt den App-seitigen Befund nochmal auf Kernel-Ebene.
2. **`/proc/fs/cifs/DebugData` geprueft:** SMB-Leasing IST mit HM-FL01 verhandelt (Dialect 3.1.1,
   Server-Capability-Bit 0x2 gesetzt) - keine "falsches SMB-Protokoll"-Erklaerung.
3. **Entscheidender Test: rohes SMB2 CHANGE_NOTIFY direkt gegen den Server**, per
   `smbclient //HM-FL01.HERRMANN.LOCAL/Datenbank -c "notify HM-Datenbank\EDV-Datenbank"` -
   komplett am Linux-Kernel-CIFS-Client vorbei. Kontrolltest: waehrend `notify` lief, wurde per
   einer ZWEITEN, unabhaengigen `smbclient`-Sitzung (`mkdir ...`) ein Ordner angelegt - nachweislich
   real entstanden (per `stat` auf der Freigabe verifiziert), aber **auch dabei kam beim `notify`-
   Aufruf nichts an**.

**Schlussfolgerung, jetzt praezise statt vermutet:** Nicht der Linux-CIFS-Client (`cifs.ko`) ist die
Ursache, sondern **der Server `HM-FL01` selbst sendet fuer diese Freigabe grundsaetzlich keine
CHANGE_NOTIFY-Antworten** - unabhaengig vom anfragenden Client (Windows Explorer, Linux-CIFS-Mount,
oder eine rohe SMB2-Verbindung wie im Test). Damit ist auch eine "elegantere" SMB-Notify-basierte
Alternativimplementierung (eigener SMB2-Client, z.B. `smbprotocol`) **ausgeschlossen** - sie wuerde am
selben Punkt scheitern, weil der Server nichts pusht. Polling (siehe `_shallow_reconcile()` unten) ist
damit nicht die zweitbeste, sondern die einzig moegliche Loesung.

**Vermutete Erklaerung fuer "hat frueher funktioniert":** der urspruengliche Watcher-Test vom
2026-08-26 lief wahrscheinlich gegen lokale/Container-eigene Aenderungen, nicht gegen echte externe
Windows-Client-Schreibvorgaenge auf HM-FL01 - dieser Server hat vermutlich nie CHANGE_NOTIFY fuer diese
Freigabe unterstuetzt. Nicht abschliessend verifizierbar ohne Zugriff auf die Windows-Server-Konfiguration
selbst (Freigabe-Typ/-Einstellungen auf HM-FL01, ausserhalb der Reichweite dieser Session).

**Umgesetzt, siehe [[project_int_filemanager_watcher_regression]] fuer Details:** periodischer
Fallback-Scan `_shallow_reconcile()` (`ir_cron_shallow_reconcile_filemanager`, alle 5 Minuten) -
prueft nur Verzeichnis-mtimes statt jeder Datei einzeln. Bekannte, noch zu behebende Ineffizienz: die
Laufzeit (~289s) ist praktisch unabhaengig davon, wie viel sich tatsaechlich geaendert hat (nur 1
Verzeichnis wirklich veraendert, trotzdem voller Aufwand) - Optimierung folgt.

## Was NICHT angefasst werden sollte, bevor das hier gelöst ist

- `bind-propagation=rslave` auf dem Odoo19-Docker-Mount ist der korrekte, bestätigte Fix für den
  Mount-Leak (siehe rshared-Memo) - nicht zurück auf `rshared` stellen, das ist nachweislich nicht
  die Ursache dieses Watcher-Problems.
- `lib.php` MUSS auf `soft` stehen (Produktivzustand, Hang-Schutz) - siehe Nebenschaden-Abschnitt
  oben, aktuell noch nicht garantiert wirksam.
