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

## Eingegrenzt, aber NICHT verifiziert (nächster Schritt für die nächste Session)

**Führende Hypothese:** Die heutige SMB-Watchdog-Korrektur (siehe [[project_hm_odoo_filemanager]] im
Memory) hat die Unassigned-Devices-Mount-Option von `hard` auf `soft` umgestellt
(`lib.php:1827`, absichtlich so gefixt wegen wedged-CIFS-Hangs - siehe
`scripts/int_filemanager_smb_watchdog.sh`). Das ist die **einzige** Mount-Options-Änderung, die
heute an den produktiven SMB-Freigaben vorgenommen wurde, bevor das Symptom auffiel. Möglich, dass
`soft` das SMB3-Change-Notify-Verhalten des CIFS-Kernel-Clients anders behandelt als `hard` (z.B.
weil oplock-/lease-Renewal unter `soft` anders auf Verzögerungen reagiert).

**Test angefangen, aber nicht abgeschlossen:** `lib.php` testweise zurück auf `hard` gepatcht -
Mount hat den neuen Wert aber NICHT übernommen, weil `emhttpd` dauerhaft läuft und `lib.php` schon
lange vorher eingelesen/im Speicher hat (reines Datei-Edit reicht nicht, ohne dass `emhttpd`
neu startet). `lib.php` wurde wieder auf `soft` zurückgesetzt (Produktivzustand, nicht
verändert lassen!).

**Sauberster nächster Test:** `lib.php` auf `hard` patchen, **Host neu booten** (frischer
`emhttpd`-Prozess liest die Datei garantiert neu, kein Cache-Risiko mehr), dann denselben
Testablauf wiederholen:
1. Ordner über eine externe SMB-Sitzung (Laptop **oder** ersatzweise die Host-eigene
   `/mnt/remotes/...`-Mount-Sitzung, beide haben sich bisher identisch verhalten) anlegen.
2. Nach ~30s in der DB prüfen: `docker exec odoo_db psql -U odoouser -d odoodb -t -c "select path, name, write_date from int_filemanager_file where write_date > now() - interval '2 minutes';"`
3. Wenn es mit `hard` funktioniert: Ursache bestätigt, dann eine Lösung suchen, die BEIDES kann
   (kein endloses Haengen bei totem Server UND funktionierende Change-Notifies) - z.B. andere
   Timeout-Kombination statt reinem `hard`/`soft`-Umschalten, oder den SMB-Watchdog so anpassen,
   dass er nur bei einem BESTÄTIGTEN Hang eingreift statt die Grundoption dauerhaft zu ändern.
4. Wenn es AUCH mit `hard` nicht funktioniert: Hypothese verworfen, weitersuchen - z.B. Odoo-19-
   Versionswechsel (`19.0-20260817` → `19.0-20260908`, siehe Log-Zeile
   "Odoo version 19.0-20260908" von heute vs. frühere Sessions) als möglicher Auslöser prüfen,
   oder `watcher.py`s tatsächliche Inotify-Maskeneinstellungen am Quellcode gegenlesen (evtl. ist
   die inotify-Kette selbst unverändert, aber CIFS liefert das zugrunde liegende Kernel-Event für
   fremde Sessions grundsätzlich nicht - dann bräuchte es einen periodischen Reconciliation-
   Fallback-Scan zusätzlich zu reinem Inotify, nicht nur eine Mount-Options-Korrektur).

## Was NICHT angefasst werden sollte, bevor das hier gelöst ist

- `lib.php` steht aktuell korrekt auf `soft` (Produktivzustand) - **nicht** wieder auf `hard`
  lassen, ohne den SMB-Watchdog-Grund dafür (wedged-CIFS-Hang-Schutz) zu berücksichtigen.
- `bind-propagation=rslave` auf dem Odoo19-Docker-Mount ist der korrekte, bestätigte Fix für den
  Mount-Leak (siehe rshared-Memo) - nicht zurück auf `rshared` stellen, das ist nachweislich nicht
  die Ursache dieses Watcher-Problems.
