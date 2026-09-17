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

## Verbleibende, noch nicht getestete Spur

**Kandidat:** Heute Morgen (im Rahmen der Wrapper/Restart-Policy-Arbeit) wurde `Odoo19` von
`odoo:latest` (Image-Alter: 18.08., aeltere Odoo-Version) auf das eigene
`int-filemanager-odoo:19.0-ocr`-Image (basiert auf `odoo:19.0`, Build 10.09., "Odoo version
19.0-20260908" laut Log) umgestellt - das ist die einzige noch nicht getestete, konkret datierte
Aenderung von heute. `watcher.py` ist zwar reiner, image-unabhängiger Python-Code (sollte sich
unter jeder Odoo-Version identisch verhalten), aber die BASIS-OS-Schicht/Python-Umgebung
zwischen beiden Images wurde nicht verglichen.

**Nutzer konnte den Zeitpunkt "hat zuletzt funktioniert" nicht eingrenzen** - das Regressionsfenster
ist daher nicht bekannt (koennte heute, koennte aber auch schon laenger her sein und nur jetzt zum
ersten Mal aufgefallen sein).

**Vorschlag fuer die naechste Session:**
1. Zuerst den `hard`/`soft`-Nebenschaden beheben (siehe oben).
2. Testweise `Odoo19` kurzzeitig auf `odoo:latest` zurückstellen (identische Mounts/ExtraParams,
   nur `--mount ...` durch das alte Image ersetzen), denselben externen-Aenderungs-Test wiederholen.
   Bei Erfolg: Odoo-Kernversion oder eine OS-Paket-Differenz zwischen den Images ist die Ursache.
   Bei Fehlschlag: Ursache liegt vermutlich ausserhalb von Odoo/Docker/Unraid ganz (z.B. SMB-Server-
   seitige Aenderung auf HM-FL01 selbst, ein Windows-Update dort, das Change-Notify betrifft) -
   dann lohnt ein Blick direkt auf HM-FL01 (Windows-Server/-Freigabe), nicht mehr auf dieser Seite.
3. Falls beides nichts bringt: `watcher.py`s tatsächliche Inotify-Maskeneinstellungen am Quellcode
   gegenlesen, und/oder einen periodischen Reconciliation-Fallback-Scan zusätzlich zu reinem
   Inotify in Erwägung ziehen (robuster gegen genau diese Art von Cross-Session-Blindheit,
   unabhängig davon, woran es letztlich liegt).

## Was NICHT angefasst werden sollte, bevor das hier gelöst ist

- `bind-propagation=rslave` auf dem Odoo19-Docker-Mount ist der korrekte, bestätigte Fix für den
  Mount-Leak (siehe rshared-Memo) - nicht zurück auf `rshared` stellen, das ist nachweislich nicht
  die Ursache dieses Watcher-Problems.
- `lib.php` MUSS auf `soft` stehen (Produktivzustand, Hang-Schutz) - siehe Nebenschaden-Abschnitt
  oben, aktuell noch nicht garantiert wirksam.
