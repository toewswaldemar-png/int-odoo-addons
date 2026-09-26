# Übergabe: int_filemanager 2 – Stand und nächste Schritte

Stand 2026-09-26. Für eine neue Sitzung: zuerst dieses Dokument, dann das Konzept lesen.

## 1. Worum es geht

`int_filemanager` wird neu aufgebaut: **Dateimanager vollständig als Odoo-Addon, Odoo ist alleiniger Schreiber**,
Dateiinhalte liegen in einem **eigenen, inhaltsadressierten Blob-Speicher**. Odoo-Bausteine werden genutzt, selbst
gebaut wird nur, wo Odoo nachweislich begrenzt ist. Der Bestand wird **kopiert** (kein Hardlink).

**Maßgebliche Dokumente (in dieser Reihenfolge lesen):**
1. `docs/int_filemanager_v2_konzept_2026-09-26.md` – Konzept: Invarianten I1–I12, Datenmodell, Schreibwege,
   Migration, Testplan, offene Entscheidungen (17), Reihenfolge (18), **Prototyp-Ergebnisse (19)**.
2. `docs/int_filemanager_konzept_db_vorrang_2026-09-24.md`, Abschnitte **19 und 20** – Live-Prüfungen auf Tower,
   die zur Entscheidung geführt haben (Fehlerbilder des heutigen Moduls, Odoo-Core-Befunde, SMB-Verhalten).
3. `CLAUDE.md` (Repo-Wurzel) – Regeln: vor "kein Bordmittel" den Odoo-Core prüfen; Claims verifizieren;
   Produktentscheidungen beim Nutzer.

**Nicht verfolgte Alternative:** Verbindung von `web-filemanager` mit Odoo, geprüft und dokumentiert in
`web-filemanager/docs/plans/odoo-integration.md` (als "nicht verfolgt" markiert).

## 2. Entscheidungen des Nutzers

| Datum | Entscheidung |
|---|---|
| 2026-09-26 | Dateimanager vollständig als Odoo-Addon; Eigenbau nur, wo Odoo begrenzt ist |
| 2026-09-26 | Odoo ist alleiniger Schreiber (kein SMB-Schreibzugriff auf die Dateien) |
| 2026-09-26 | Migration per **Kopie**, kein Hardlink |
| 2026-09-25 | Testumgebung auf Tower **behalten** (nicht löschen ohne Rückfrage) |

Vorgabe des Nutzers für den Umbau: **erst vollständig durchplanen, keine Zeile Modul-Code vor Freigabe des
Konzepts.** Prototypen auf der Testinstanz sind erlaubt.

## 3. Erledigt

| Was | Ergebnis | Ort |
|---|---|---|
| Live-Prüfung der offenen Punkte (DB-Vorrang) | Abschnitte 19/20 des DB-Vorrang-Konzepts | Commits `3b6b522`, `f695f5e` |
| Konzept int_filemanager 2 | Abschnitte 1–18 | Commit `22332b3` |
| Prototyp Blob-Speicher, Upload in Stücken, `x_sendfile`, Kopierrate | Abschnitt 19 des Konzepts; alles bestanden | Commit `81c232f` |
| Prototyp-Code und Testskripte archiviert | `docs/prototypes/fm2/` (siehe 5) | dieser Commit |

**Wichtigste Prototyp-Befunde (Details: Konzept 19):**
- Blob-Speicher, Upload in 4-MB-Stücken, Fortsetzen, Idempotenz, Deduplizierung, Absturzsicherheit und Aufräumjob
  funktionieren; Auslieferung über nginx per `x_sendfile` mit Range und ETag.
- **Odoo gibt den rohen Request-Strom nicht heraus** (`http.py:1480-1510`): jeder Body liegt ganz im RAM →
  Upload in Stücken zwingend; **WebDAV-`PUT` großer Dateien ist im Odoo-Prozess nicht sauber machbar**.
- Worker-Speicher wächst bei großen Bodies (Allokator, kein Python-Leck); Odoo recycelt Worker über
  `limit_memory_soft`.
- `finish` großer Dateien dauert lange (3 GB: ~51 s) → Hintergrundjob vorsehen.
- `fields.Integer` ist `int4` → Dateigrößen nicht als Integer speichern.
- Kopierrate 27,5 MB/s (55 GB, 62.886 Dateien, 0 Fehler, Stichprobe 300/300 korrekt) → ca. 18 h für 1,8 TB.

## 4. Nächste Schritte

1. **WebDAV-Prototyp (Explorer-Zugriff, Konzept 11 A)** – der größte offene Punkt.
   - Wegen des Befunds zum Request-Strom als **kleiner WebDAV-Dienst neben Odoo** testen: streamt große `PUT`s in
     den Blob-Speicher, lässt Odoo per API/Route den Commit machen (Rechte, Revision, Sperren in Odoo).
   - Zu prüfen: Windows-Explorer als Netzlaufwerk (HTTPS nötig, Größenlimit des WebClient-Dienstes), Speicherabläufe
     von Word/Excel/LibreOffice (Temp-Datei + Umbenennen → Identität der Datei erhalten), Sperren (`LOCK`),
     Geschwindigkeit, Verhalten bei großen Dateien.
   - **Braucht den Nutzer:** Test mit echtem MS Office an einem Rechner mit Office (auf dem Arbeitsrechner gibt es nur
     LibreOffice). Explorer und LibreOffice kann die Sitzung selbst testen.
   - Danach Entscheidung A/B/C (Konzept 11) durch den Nutzer.
2. **Offene Entscheidungen des Nutzers einholen** (Konzept 17): Umfang (ganzer Share oder ohne Fotos/Musik),
   Versionsaufbewahrung, Papierkorb-Frist, anfängliche Rechte-Bereiche/Gruppen, HM-SRV (gleicher Weg? wann?).
3. **Konzept festschreiben:** Prototyp-Befunde in die Abschnitte 5–7 und 11 einarbeiten (4-MB-Stücke, `finish` als
   Hintergrundjob, Größen als Float/bigint, WebDAV-Dienst), Entscheidungen aus 17 eintragen, **Freigabe durch den
   Nutzer**.
4. Erst danach Umsetzung nach Konzept 18 (Fundament → Oberfläche → Vorschau/OCR → Office → Explorer → Migration).

## 5. Testumgebung auf Tower (lokaler Unraid, `ssh unraid`)

**Alles gestoppt bzw. temporär; vor dem Löschen den Nutzer fragen.** Live-Instanz (`odoo`, `odoo_db`) wurde nur
gelesen.

| Element | Details |
|---|---|
| `fmtest_pg` | PostgreSQL 16 der Testumgebung (läuft). DBs: `fmtest` (Modul 1.15.0, Testwurzel), `fmreal` (neutralisierte Kopie der Tower-Live-DB, 427.914 Zeilen), `fmv2` (Prototyp int_filemanager 2). Passwort in `/mnt/user/appdata/fmtest/.pgpw` |
| `fmtest_odoo` | Test-Odoo für `fmtest` (Port 8070, erstellt, gestoppt) |
| `fmreal_odoo` | Odoo für `fmreal` (gestoppt; für Lasttests) |
| `fmv2_odoo`, `fmv2_nginx` | Prototyp int_filemanager 2: Odoo Prefork (`workers=2`, `x_sendfile`) + nginx (Port **8081**), gestoppt. Start: `docker start fmtest_pg fmv2_odoo fmv2_nginx` |
| Modul `fm_proto` | `/mnt/user/appdata/fmtest/addons_v2/fm_proto` (Kopie im Repo: `docs/prototypes/fm2/fm_proto`) |
| Konfiguration | `/mnt/user/appdata/fmtest/config_v2/odoo.conf` und `nginx.conf` (Kopie ohne Passwort: `docs/prototypes/fm2/tower/config_v2_odoo_und_nginx.txt`) |
| Blob-Speicher | temporärer Unraid-Share **`fmv2blobs`** (nur `disk3`, kein Cache, keine SMB-Freigabe), Config `/boot/config/shares/fmv2blobs.cfg`, ca. **53 GB** (Import-Teilbestand + Testdateien) |
| Testdateien | `/mnt/user/test/v2src` (3,3 GB) |
| Skripte | `/mnt/user/appdata/fmtest/runv2.sh <schritt>` (Prototyp-Tests `t_v2.py`), `runt.sh` (Block-A-Tests), `fmshell.sh <db>` (odoo shell mit Watcher-Schalter), `snap.sh`; Tests unter `/mnt/user/appdata/fmtest/tests/` (Kopie: `docs/prototypes/fm2/tests*`) |
| Testnutzer | in `fmtest`: `admin`/`admin`, `fmuser`/`fmtest-pw-1`; in `fmreal`: `fmuser_real`/`fmreal-pw-1`; in `fmv2`: `admin`/`admin` (nur Testdatenbanken) |

**Aufräumen, wenn nicht mehr gebraucht (nur nach Rückfrage):** Container `fmv2_*`, `fmtest_*`, `fmreal_odoo`;
Share `fmv2blobs` (Verzeichnis `/mnt/disk3/fmv2blobs` + `.cfg`); `/mnt/user/test/v2src`, `/mnt/user/test/fmroot`;
`/mnt/user/appdata/fmtest`; Netzwerk `fmtest-net`.

## 6. Sonstiges

- **HM-SRV** ist von hier nicht erreichbar; DB dort laut Doku `en_US.utf8` → vor jedem Odoo-Image-Update auf
  C-Kollation umstellen (neuerer Core zerstört sonst Teilbäume, DB-Vorrang-Konzept 19.2).
- **Sicherheitslücke N1** im heutigen Modul (öffentliche Methoden `action_analyze_document`/
  `action_apply_extracted_values` per RPC mit `sudo`) ist **nicht gefixt**; im Konzept 9 für int_filemanager 2
  berücksichtigt. Falls das heutige Modul noch länger produktiv läuft, vorab separat beheben.
- In `web-filemanager` liegen nicht committete Code-Änderungen des Nutzers (unberührt lassen). Dort steht außerdem
  ein Vorschlag als Aufgabe bereit: `frame-ancestors`-Header (Clickjacking-Schutz).
