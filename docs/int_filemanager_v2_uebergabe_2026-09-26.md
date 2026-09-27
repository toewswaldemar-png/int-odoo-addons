# Übergabe: int_filemanager 2 – Stand und nächste Schritte

Stand 2026-09-26, ergänzt 2026-09-27 (Code-Prüfung eingearbeitet). Für eine neue Sitzung: zuerst dieses Dokument,
dann Kern und Konzept lesen.

## 1. Worum es geht

`int_filemanager` wird neu aufgebaut: **Dateimanager vollständig als Odoo-Addon, Odoo ist alleiniger Schreiber**,
Dateiinhalte liegen in einem **eigenen, inhaltsadressierten Blob-Speicher**. Odoo-Bausteine werden genutzt, selbst
gebaut wird nur, wo Odoo nachweislich begrenzt ist. Der Bestand wird **kopiert** (kein Hardlink).

**Maßgebliche Dokumente (in dieser Reihenfolge lesen):**
0. `docs/int_filemanager_v2_kern_2026-09-26.md` – **Kurzfassung** (Regeln, Aufbau, Funktionen zum Start,
   Entscheidungen, Reihenfolge mit Abnahmekriterien); das ist das Dokument zur Freigabe.
1. `docs/int_filemanager_v2_konzept_2026-09-26.md` – Konzept: Invarianten I1–I12, Datenmodell, Schreibwege,
   Migration, Testplan, offene Entscheidungen (17), Reihenfolge (18), **Prototyp-Ergebnisse (19, WebDAV: 19.4)**.
2. `docs/int_filemanager_konzept_db_vorrang_2026-09-24.md`, Abschnitte **19 und 20** – Live-Prüfungen auf Tower,
   die zur Entscheidung geführt haben (Fehlerbilder des heutigen Moduls, Odoo-Core-Befunde, SMB-Verhalten).
3. `docs/review/konzept_codepruefung_2026-09-26.md` – Code-Prüfung des Konzepts (194 Behauptungen mit Beleg,
   Befunde A1–A21); seit 2026-09-27 in Konzept und Kern eingearbeitet.
4. `CLAUDE.md` (Repo-Wurzel) – Regeln: vor "kein Bordmittel" den Odoo-Core prüfen; Claims verifizieren;
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
| 2026-09-26 | Test mit echtem Word/Excel **entfällt** |
| 2026-09-26 | Explorer-Zugriff: **Option A, WebDAV-Netzlaufwerk** (Konzept 11, 19.4) |
| 2026-09-26 | Migration: **ganzer Share**; Versionen **unbegrenzt**; Papierkorb **30 Tage** (Konzept 17.1–17.4) |
| 2026-09-26 | WebDAV-Bauform, falls WebDAV: **eigener Odoo-Befehl `odoo fmdav`** (Konzept 11.2, 19.10) |
| 2026-09-26 | **Start ohne Explorer-Zugriff** (Odoo-Oberfläche, ONLYOFFICE im Browser) **plus Eingangsordner**; Netzlaufwerk (WebDAV oder SMB über Odoo-FUSE) später nach Nutzung entscheiden (Konzept 11, 17.1/17.7) |
| 2026-09-26 | Code nach den Odoo-/OCA-Konventionen (`docs/odoo_konventionen_2026-09-26.md`): **Englisch** in Namen, Kommentaren, Docstrings, Log-Meldungen und Commits (`[TAG] modul: …`); Oberflächentexte englisch im Code, deutsche Übersetzung in `i18n/de.po`. Prüfwerkzeuge: **pre-commit** nach OCA-Vorlage (nur für neuen Code), Odoos **`test_lint`** und **odoo-ls** (Parse-Modus) auf der Testinstanz; **keine** GitHub Action; Migrationsskripte mit **`odoo/upgrade-util`** |
| 2026-09-26 | Modellnamen mit Modulpräfix `int_filemanager.*` (Konventionen, `docs/odoo_konventionen_2026-09-26.md`) |
| 2026-09-26 | Rechte-Bereiche **minimal** ("Alle" + heutiger Schutzordner); **HM-SRV bleibt vorerst beim heutigen Modul** (17.5, 17.6) |
| 2026-09-27 | Eingangsordner: Datei gilt nach **2 Minuten** ohne Änderung als fertig; ZIP-Download bis **ca. 500 MB** direkt, darüber Hintergrundjob; Blob-Speicher auf **disk2 + disk3** (Konzept, Entscheidungen 6–8) |
| 2026-09-27 | Kern-Änderungen aus der Code-Prüfung übernommen; Zusatzpunkte aus dem externen Review (Import-Manifest, Outbox-Regel, B-Invarianten, Versionen festnageln) **nicht** aufgenommen |

Vorgabe des Nutzers für den Umbau: **erst vollständig durchplanen, keine Zeile Modul-Code vor Freigabe des
Konzepts.** Prototypen auf der Testinstanz sind erlaubt.

## 3. Erledigt

| Was | Ergebnis | Ort |
|---|---|---|
| Live-Prüfung der offenen Punkte (DB-Vorrang) | Abschnitte 19/20 des DB-Vorrang-Konzepts | Commits `3b6b522`, `f695f5e` |
| Konzept int_filemanager 2 | Abschnitte 1–18 | Commit `22332b3` |
| Prototyp Blob-Speicher, Upload in Stücken, `x_sendfile`, Kopierrate | Abschnitt 19 des Konzepts; alles bestanden | Commit `81c232f` |
| Prototyp-Code und Testskripte archiviert | `docs/prototypes/fm2/` (siehe 5) | Commit `57ffd83` |
| **WebDAV im Odoo-Prozess** (Nachprüfung 19.6, Prototyp 19.7) | Strom in Odoo-Route lesbar, 25-ms-Grundlast war Konfiguration; WsgiDAV hinter Odoo-Route: litmus 100 %, schneller als der Dienst, eigener Odoo-Prozess für `/dav/` nötig | `fm_proto/dav_inproc.py` |
| **WebDAV-Prototyp (Explorer-Zugriff, Konzept 11 A)** | Abschnitt 19.4 des Konzepts; litmus 100 %, Windows-WebClient, LibreOffice, Identitätsregel für Word/Excel-Speichermuster | `docs/prototypes/fm2/fmdav/`, `fm_proto/dav.py` |
| **Code-Prüfung des Konzepts** (2026-09-26/27) | 194 Behauptungen gegen Odoo 19 geprüft, 21 Befunde; hoch: Regeln für Neben-Modelle (A1), `call_kw` (A2), `retrying()` wiederholt keine Namens-/Sperrkonflikte (A3), Aufräumjob-Wettlauf (A4); in Konzept (u. a. 2, 4–6, 12, 16, 19.17) und Kern eingearbeitet; Plattengrenzen-Test für disk2 + disk3 bestanden | `docs/review/konzept_codepruefung_2026-09-26.md` |

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

**WebDAV-Prototyp (Details: Konzept 19.4):** WebDAV-Dienst neben Odoo (WsgiDAV als Protokollschicht), der nur
übersetzt und mit dem API-Schlüssel des Nutzers (`auth='bearer'`) Odoo aufruft; Odoo bleibt alleiniger Schreiber.
- litmus 100 % (basic, copymove, props, locks, http); Windows-WebClient als Netzlaufwerk funktioniert (Umlaute,
  Ordner, Papierkorb); LibreOffice speichert per `PUT` auf dieselbe Datei.
- **Identitätsregel** für "Temp schreiben → Original wegbenennen/löschen → Temp umbenennen" (Word/Excel) hält Knoten-ID
  und Versionen; Temp-Knoten werden restlos entfernt.
- Tempo: kleine Dateien 0,28 s je Datei (Odoo-Grundlast ~25 ms je Request, WebClient 8 Requests je Datei); große
  Dateien streamen mit konstantem Speicher (3 GB: `PUT` 90 s, davon 46 s Hash-Prüfung; `GET` 11 s).
- Offen: Windows braucht HTTPS mit vertrautem Zertifikat (Basic nur über HTTPS) und eine angehobene Download-Grenze
  (Standard 50 MB); Namen müssen ohne Groß/Klein eindeutig werden; Sperren in Odoo speichern.

## 4. Nächste Schritte

1. ~~Test mit echtem Word/Excel~~ – **entfällt** (Nutzerentscheidung 2026-09-26). Falls später doch: IP des
   Office-Rechners in `FM_DAV_ANON_IPS` (`/mnt/user/appdata/fmtest/fmdav/env`), `fmv2_dav` neu erstellen, dort
   `net use W: http://192.168.188.67:8082/`, `.docx`/`.xlsx` zweimal speichern, Knoten/Revisionen in `fmv2` prüfen.
2. ~~Entscheidung Explorer-Zugriff~~ – **erledigt:** Start ohne Netzlaufwerk plus Eingangsordner; WebDAV-Bauform
   `odoo fmdav` vorbereitet, SMB über Odoo-FUSE als Alternative (ohne Prototyp); Entscheidung später (Konzept 11, 17.7).
3. ~~Offene Entscheidungen des Nutzers~~ (Konzept 17) – **alle erledigt** (2026-09-26). Folgeaufgabe aus 17.6:
   Sicherheitslücke N1 im heutigen Modul beheben (HM-SRV läuft damit weiter).
4. ~~Konzept festschreiben~~ – **erledigt** (2026-09-26): Befunde aus 19 und Entscheidungen aus 17 in die Abschnitte
   3–7, 10–14, 16–18 eingearbeitet.
5. ~~Code-Prüfung einarbeiten~~ – **erledigt** (2026-09-27): Befunde A1–A21 in Konzept und Kern.
   **Nächster Schritt: Freigabe durch den Nutzer.**
6. Erst danach Umsetzung nach Konzept 18. Schritt 3 (Fundament) beginnt mit: Test-Image aktualisieren
   (`docker build --pull`, Konzept 13), pre-commit/`test_lint`/odoo-ls einrichten, **zuerst die Tests für A1–A4**
   (erzwungene Überlappung, echter Prozessabbruch, Konzept 16). Update der Live-Instanz ist eine eigene Entscheidung.

## 5. Testumgebung auf Tower (lokaler Unraid, `ssh unraid`)

**Alles gestoppt bzw. temporär; vor dem Löschen den Nutzer fragen.** Live-Instanz (`odoo`, `odoo_db`) wurde nur
gelesen.

| Element | Details |
|---|---|
| `fmtest_pg` | PostgreSQL 16 der Testumgebung (läuft). DBs: `fmtest` (Modul 1.15.0, Testwurzel), `fmreal` (neutralisierte Kopie der Tower-Live-DB, 427.914 Zeilen), `fmv2` (Prototyp int_filemanager 2). Passwort in `/mnt/user/appdata/fmtest/.pgpw` |
| `fmtest_odoo` | Test-Odoo für `fmtest` (Port 8070, erstellt, gestoppt) |
| `fmreal_odoo` | Odoo für `fmreal` (gestoppt; für Lasttests) |
| `fmv2_odoo`, `fmv2_nginx` | Prototyp int_filemanager 2: Odoo Prefork (`workers=2`, `x_sendfile`) + nginx (Port **8081**), gestoppt. Start: `docker start fmtest_pg fmv2_odoo fmv2_fmdav fmv2_nginx` (Variante 19.10; `fmv2_nginx` erst starten, wenn `fmv2_fmdav` läuft, sonst findet nginx den Host nicht) bzw. `… fmv2_dav` (Dienst, 19.4). `fmv2_odoo` wurde am 2026-09-26 für den WebDAV-Test neu erstellt (Umgebung `FM_DAV_SWAP_WINDOW=600`, **ohne** `FM_PROTO_GC_GRACE=0` – für den Aufräumjob-Test aus 19.1 wieder setzen) |
| Modul `fm_proto` | `/mnt/user/appdata/fmtest/addons_v2/fm_proto` (Kopie im Repo: `docs/prototypes/fm2/fm_proto`, inkl. `dav.py`) |
| `fmv2_odoo` (Stand 19.12) | zuletzt für den Test "fmdav ohne eigenen Container" neu erstellt: `odoo --workers=2 --load=base,rpc,web,fm_proto` mit `FM_DAV_EMBED=1`, `FM_DAV_EMBED_PORT=8080`, `FM_DAV_ROOT_ID`, `FM_DAV_ACCEL`, `FM_DAV_ANON_*` (startet `odoo fmdav` als Kindprozess); nginx `/dav` → `fmv2_odoo:8080`. Für den Thread-Modus `--workers=0` statt `--workers=2`. Ohne `FM_DAV_EMBED=1` verhält sich das Modul wie vorher |
| `fmv2_fmdav` | **`odoo fmdav`** (19.10): `odoo --addons-path=/mnt/extra-addons,/usr/lib/python3/dist-packages/odoo/addons fmdav -c /etc/odoo/odoo.conf -d fmv2 --dav-root=68624 --dav-accel=/web/filestore --dav-anon-ips=192.168.188.188 --dav-anon-login=davuser`, Port 8080 im Netz `fmtest-net`; nginx leitet `/dav` **jetzt hierhin** (nicht mehr zu `fmv2_odoo_dav`). Code: `fm_proto/cli/fmdav.py`, `fm_proto/dav_server.py` |
| `fmv2_odoo_dav` | **WebDAV im Odoo-Prozess** (19.7): zweiter Odoo-Prozess derselben DB nur für `/dav/` (`--workers=4 --max-cron-threads=0`, `PYTHONPATH=/mnt/pylib` → `/mnt/user/appdata/fmtest/pylib_v2` mit `wsgidav` 4.3.5 und `json5`). nginx (`fmv2_nginx`, Port **8081**) leitet `/dav` dorthin; Netzlaufwerk `http://192.168.188.67:8081/dav/`. `fmv2_odoo` hat dieselben Umgebungsvariablen (`FM_DAV_ROOT_ID`, `FM_DAV_ANON_IPS`, `FM_DAV_ANON_LOGIN=davuser`). Konfiguration seit 19.6/19.7 geändert: `odoo.conf` ohne `dbfilter` (Sicherung `odoo.conf.bak-dbfilter`), `nginx.conf` mit `/dav`-Location, `client_max_body_size 0`, `Host $http_host`, ETag-Weitergabe (Sicherungen `nginx.conf.bak-dav`, `.bak-davsplit`); Kopie: `docs/prototypes/fm2/tower/config_v2_odoo_und_nginx.txt` |
| `fmv2_dav` | WebDAV-Dienst (Image `fmdav:proto`, Port **8082**), Konfiguration `/mnt/user/appdata/fmtest/fmdav/env` (nur root lesbar, enthält den API-Schlüssel von `davuser`); Wurzelordner in `fmv2`: Knoten `davtest` (ID 68624). Anonymer Testzugang nur für `192.168.188.188` (Arbeitsrechner). Kopie des Codes: `docs/prototypes/fm2/fmdav/` |
| odoo-ls | `/tmp/odoo-ls` auf dem Tower-Host (Release 1.6.0: `odoo_ls_server`, `typeshed/`, Auswerteskripte `sum.py`/`det.py`); läuft im Wegwerf-Container `docker run --rm --network none --entrypoint /ols/odoo_ls_server … odoo:19.0-hm --parse …` (Aufruf: Konventionen Abschnitt 9). Liegt in `/tmp`, also nach einem Neustart weg |
| Konfiguration | `/mnt/user/appdata/fmtest/config_v2/odoo.conf` und `nginx.conf` (Kopie ohne Passwort: `docs/prototypes/fm2/tower/config_v2_odoo_und_nginx.txt`) |
| Blob-Speicher | temporärer Unraid-Share **`fmv2blobs`** (nur `disk3`, kein Cache, keine SMB-Freigabe), Config `/boot/config/shares/fmv2blobs.cfg`, ca. **53 GB** (Import-Teilbestand + Testdateien) |
| Testdateien | `/mnt/user/test/v2src` (3,3 GB) |
| Skripte | `/mnt/user/appdata/fmtest/runv2.sh <schritt>` (Prototyp-Tests `t_v2.py`), `runt.sh` (Block-A-Tests), `fmshell.sh <db>` (odoo shell mit Watcher-Schalter), `snap.sh`; Tests unter `/mnt/user/appdata/fmtest/tests/` (Kopie: `docs/prototypes/fm2/tests*`) |
| Testnutzer | in `fmtest`: `admin`/`admin`, `fmuser`/`fmtest-pw-1`; in `fmreal`: `fmuser_real`/`fmreal-pw-1`; in `fmv2`: `admin`/`admin`, `davuser`/`davuser-pw-1` plus API-Schlüssel "fmdav-proto" für `davuser` und `admin` (nur Testdatenbanken) |

**Aufräumen, wenn nicht mehr gebraucht (nur nach Rückfrage):** Container `fmv2_*` (inkl. `fmv2_dav`, `fmv2_odoo_dav`, `fmv2_fmdav`), `/mnt/user/appdata/fmtest/pylib_v2`, `/tmp/odoo-ls`, `fmtest_*`, `fmreal_odoo`;
Images `fmdav:proto`, `python:3.12-slim`, `debian:bookworm-slim`, `curlimages/curl`;
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
