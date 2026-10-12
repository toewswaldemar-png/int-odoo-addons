# int_filemanager: Plan eigener Dateispeicher im Odoo-Filestore (Stand 2026-10-12)

Stand: Plan, noch nichts umgesetzt. Entscheidungen des Nutzers vom 12.10.2026: SHA-256 statt SHA-1; `mail.thread` bleibt,
Tracking beim Einlesen aus; Einlese-Wurzel ist ganz `/mnt/hm-daten`, alles kommt in Odoo.
Grundlage: Prototyp (gemessen), Regeln in `docs/odoo_regeln/`, Odoo-19-Quelltext in `docs/odoo/` (Commit `7a74539`, 10.10.).
Das Image `odoo:19.0-hm-test` (`19.0.post20260817`) weicht davon leicht ab (z. B. `file_size` in `ir_attachment.py` Zeile 475 statt 476);
die Kopie sollte neu gezogen werden. Fundstellen wie `http.py:670` beziehen sich auf die Kopie, die Aussagen gelten in beiden Ständen.
Gelesen und angewandt: ORM, Sicherheit, Aktionen/Cron/HTTP, Performance, Coding Guidelines. Noch zu lesen vor Stufe 3: Views, JS-Framework, JS-Tests, QWeb.
Der Plan wurde am 12.10. von einer zweiten Instanz gegengelesen und gegen den Quelltext verifiziert; die Korrekturen sind eingearbeitet.

## 1. Ziel und Rahmen

- Modul `int_filemanager` (hängt nur von `base` und `mail` ab). Ordner und Dokumente sind gewöhnliche Datensätze.
- Die Bytes liegen in `<data_dir>/filestore/<db>/int_filemanager/<sha256[:2]>/<sha256>`, nicht in `ir.attachment`. Das gilt für alle Größen bis 15 GB.
  Die Prüfsumme ist SHA-256 (Regex `^[0-9a-f]{64}$`); eine Byte-für-Byte-Kollisionsprüfung wie beim Core-SHA-1 entfällt.
- Bestand: 399.872 Dateien, 29.318 Ordner, 1.901 GB aus `/mnt/hm-daten`. Das Einlesen kopiert; die Originale bleiben unverändert.
- Nach dem Einlesen sehen nur Mitglieder der Gruppe „Filemanager Administrator“ die Dokumente. „Filemanager User“ wird erst nach Durchsicht vergeben
  (der Bestand enthält private Familienunterlagen).
- Nur zwei nötige Abweichungen vom Standard, beide mit Beleg: der eigene Speicher und der Hook `ir.binary._record_to_stream`.
  Beleg zum Speicher:
  - `ir.attachment.file_size` ist ein Integer-Feld (`ir_attachment.py:475`, `int4`, läuft ab 2 GiB über); Odoo hat keinen Bigint-Feldtyp, deshalb ist `size` ein Float.
  - Die ganze Datei liegt beim Schreiben im Arbeitsspeicher (`web/controllers/binary.py:239`, `_set_attachment_data`, `_file_write`, `_same_content`).
    Der Lesepfad ist dagegen schon ein Pfad-Stream (`_to_http_stream`).
  - `_postprocess_contents` verkleinert png, jpeg, bmp und tiff über 1920×1920 und komprimiert jpeg mit Qualität 80 (außer bei `image_no_postprocess`,
    `ir_attachment.py:376-419`). Das trifft schon das Bestandsmodul (`Binary(attachment=True)`); Scans im Bestand würden verändert.
  - Die 128-MiB-Grenze (`http.py:247`) gehört **nicht** dazu: Sie liegt in der HTTP-Schicht, jede Upload-Route braucht die Funktion `max_content_length`
    (nativ geht auch der Systemparameter `web.max_file_upload_size`, `ir_http.py:298`).

## 2. Betrieb vor dem Einlesen (Freigabe durch den Nutzer nötig)

| # | Maßnahme | Stand / Grund |
|---|---|---|
| B1 | Eigener Share mit Cache „no“ für die Blobs. Der Pfad `int_filemanager` muss unter `<data_dir>/filestore/<db>` liegen, sonst greift x_sendfile nicht (`http.py:670-674`, sonst `ValueError` und kein Header). **Als Symlink** `…/<db>/int_filemanager` → Share einbinden, nicht als verschachtelter Mount: `exp_drop` löscht `filestore/<db>` mit `shutil.rmtree` (`odoo/service/db.py:253-255`); ein Symlink im Ordner wird nur entfernt (im Image geprüft), bei einem Mount würde der Inhalt des Shares gelöscht (abgeleitet, nicht gemessen). Der Proxy muss das Ziel am selben Pfad sehen (B4). | Cache hat 86 GB frei, der Bestand ist 1,9 TB |
| B2 | `TMPDIR` des Odoo-Containers auf ein Volume; Größe mindestens wie der größte gleichzeitige Upload. | `/tmp` liegt auf dem Docker-Datenträger mit 16 GB frei |
| B3 | Proxy (NPM): `client_max_body_size 0`, Lese-/Sendezeiten 3600 s, `client_body_temp_path` auf ein Volume (Größe wie B2). | sonst 413 und 504 |
| B4 | Odoo mit `--x-sendfile` starten. **Pflicht, nicht nur nützlich:** ohne x-sendfile hält der HTTP-Thread für die ganze Downloaddauer, HTTP-Threads fallen ins Limit (`server.py:300, 520-530`), über 1800 s startet der Server neu. Filestore und Share-Ziel **lesend in den Proxy-Container einhängen** (jeden Mount einzeln, ein Eltern-Mount reicht für verschachtelte Mounts nicht); `location /web/filestore { internal; alias <Einhang>; }` (`web/controllers/binary.py:40-44`). | Proxy hat den Filestore bisher nicht (nur `/data`, `/etc/letsencrypt`, `/var/log`); ohne Einhang 404 |
| B5 | `/mnt/hm-daten` im Odoo-Container auf `:ro` umstellen. | ist bisher `rw=true` |
| B6 | Sicherung des Filestores auf Dateiebene. Datenbank-Verwaltung: `list_db = False` sperrt nur die Weboberfläche; die CLI (`odoo db drop`, `dump`, `duplicate`) setzt `list_db = True` selbst (`odoo/cli/db.py:198`) und kopiert/löscht den ganzen Filestore (`service/db.py:211, 254, 294`). Deshalb Symlink (B1), `dump` nur mit `--no-filestore` und die CLI im Betrieb nicht auf diese Datenbank anwenden. | |
| B7 | Zeitlimit prüfen. Live: Thread-Modus, `limit_time_real = 1800`; eine Überschreitung startet den ganzen Server neu (`server.py:740-753`), dreimal in Folge ergibt Cron „fehlgeschlagen“ (`ir_cron.py:35, 430`). Für den Import lässt sich das Limit mit `--limit-time-real-cron` allein für Cron-Threads anheben (`server.py:523-526`). `limit_time_cpu` greift bei `workers=0` nicht (`RLIMIT_CPU` nur in den Prefork-Workern, `server.py:1297`). In Stufe 7 Durchsatz von `hm-daten` messen; nötig sind etwa 10 MB/s für 15 GB. | |
| B8 | Platz nach dem Einlesen: frei sinkt von 3,6 TB auf etwa 1,7 TB; das Sicherungsziel ist darin nicht enthalten. | |

## 3. Datenmodell

- `int.filemanager.folder`: wie bisher, dazu `_check_company_auto` (Sub-Ordner und Firma) und Archiv-Kaskade
  (Ordner archivieren → Inhalt mit; Wiederherstellen prüft vorher Namenskonflikte). ORM §1, §6–§7.
  Archivieren eines Ordners mit sehr vielen Dokumenten läuft nicht in einer Anfrage (Zeitlimit, Speicher): in Stapeln (Cron), dazu ein Mengentest mit mindestens 100.000 Dokumenten.
- `int.filemanager.document` (erbt weiter `mail.thread`): `name`, `folder_id`, `checksum` (Char, Pflicht, indiziert), `size` (Float), `mimetype`, `active`,
  `tag_ids`, `company_id` (von der Ordner-Firma abgeleitet), `origin_path`.
  - Schreibschutz wie `ir.attachment` (`ir_attachment.py:476-478`, `741`, `780`): `size`, `mimetype`, `checksum` mit `readonly=True` (wirkt nur in der Oberfläche,
    `odoo19_reference/backend/orm/02_fields.md:22`); `write` wirft diese Schlüssel aus den Werten, außer bei `self.env.su`; `create` ist durch das fehlende `perm_create` geschlossen (ein Wächter wäre toter Code) (Prüfung nicht über den Kontext, den setzt der RPC-Client selbst).
    Der Speicherweg läuft über eine private Methode mit `sudo()`. Die Felder bleiben lesbar, sortierbar und filterbar, es gibt keine Anzeigefelder.
    `origin_path`: `groups="base.group_system"` (Serverpfad, Nutzer sehen und sortieren ihn nicht; `sudo()` umgeht `groups`, Security §1).
  - Keine Berechtigung `perm_create` für die Nutzergruppe an `int.filemanager.document` (default-deny, Security §1): Dokumente entstehen nur über Upload und Einlesen mit `sudo()`.
    `sudo()` umgeht auch Ordner-Rechte und Datensatzregeln (`ir.rule`): die öffentliche Upload-Methode prüft zuerst selbst das Schreibrecht auf den Ordner, erst dann die private Methode mit `sudo()` (Security §2).
  - Mehrfirmen: `_check_company_auto = True` und `check_company=True` an `folder_id` (Dokument) und `parent_id` (Ordner); das Dokument-`company_id` ist von der Ordner-Firma abgeleitet (`models.py:4522`, `4749`).
    `tag_ids` bleibt ohne `check_company`: Tags sind firmenübergreifend (kein `company_id` am Tag-Modell).
  - `content`: Pseudo-Binary, ein echtes Binary-Feld ohne Speicherung (compute immer `False`, `store=False`, `copy=False`, `exportable=False`, `inverse` wirft `UserError`).
    Nötig, weil `_get_stream_from` vor `_record_to_stream` prüft, dass das Feld in `_fields` steht und vom Typ `binary` ist (`ir_binary.py:127-137`).
    **Nicht im Formular**: das Binary-Widget zeigt bei leerem Wert keinen Download (`binary_field.js`, `fields_binary.py`). Download über Knopf oder URL
    `/web/content/int.filemanager.document/<id>/content?download=true`.
  - `origin_path`: Hash-Index `models.Index("USING hash (origin_path)")` nur zum Nachschlagen (ein normaler Index scheitert bei Pfaden über etwa 2,7 KB).
    Ein Hash-Index kann nicht unique sein (in PostgreSQL 16 geprüft: „access method hash does not support unique indexes“). Die Idempotenz des Einlesens läuft
    über die Import-Zeilen (Unique je Auftrag und Pfad) oder über einen Unique-Index auf `md5(origin_path)`.
  - Namen werden beim Einlesen auf NFC normalisiert (der Unique-Index vergleicht byteweise, zusammengesetztes und zerlegtes „ä“ wären zwei Namen).
  - Ein Firmenwechsel an einem Ordner mit Inhalt wird abgelehnt (das gespeicherte Related-Feld würde sonst alle Dokumente darin schreiben).
  - Liste und Formular mit `import="0"`, `create="0"` und `duplicate="0"` (Kopieren entfällt), damit der Odoo-Import keine leeren Dokumente anlegt.
- `int.filemanager.import` (Auftrag) und `int.filemanager.import.line` (eine Zeile je Datei: Pfad, Größe, mtime, Status, Meldung).
- Einstellungen über `res.config.settings` (nur `base.group_system`): Einlese-Wurzelpfad, Alter für Temp-Dateien in `.upload/` (Standard 1 Tag), Upload-Obergrenze.
- Dateinamen nach Modellname, `models/ir_binary.py` für den Hook, `controllers/int_filemanager.py`. Coding Guidelines §1.

## 4. Umsetzung in Stufen

Vor jeder Stufe die zugehörigen Regeln lesen. Jede Stufe mit Tests.

| Stufe | Inhalt | Fundstellen |
|---|---|---|
| 1 Speicher | `_store_stream`: blockweise in Temp-Datei im `.upload/`-Ordner des Filestores (gleiches Dateisystem wie die Blobs), SHA-256 beim Schreiben. Reihenfolge: Temp → Dokument anlegen und flushen → prüfen, ob der Blob schon da ist → `os.replace` auf den Blob-Pfad (wie der Core, `ir_attachment.py:307`: Flush vor dem Schreiben, damit der Aufräumer bis Transaktionsende wartet). Wegen dieser Reihenfolge braucht ein Treffer auf einen vorhandenen Blob nichts weiter (Zeile ist geflusht, die Sperre hält den Aufräumer fern); kein `os.utime`. Stream von Hand bauen wie `ir.attachment._to_http_stream` (`ir_attachment.py:932`) mit `safe_join` auf den Filestore; **nicht** `Stream.from_path` (`file_path` kennt nur Addon-Pfade, `tools/misc.py:196`). ETag = Prüfsumme, `last_modified` vom Datensatz. Temp-Datei über `cr.postrollback` und `finally` löschen. **Typ** nicht selbst bauen, Odoo-Bausteine aufrufen: `self.env['ir.attachment'].with_context(image_no_postprocess=True, attachments_mime_plainxml=True)._check_contents({'name': …, 'mimetype': Client-Typ, 'raw': erste 2048 Byte})` (`ir_attachment.py:379-390`). Das ruft `_compute_mimetype` (Reihenfolge Client-Typ, Dateiname, erst zuletzt Dateikopf mit `guess_mimetype`) und erzwingt `text/plain` für html/xml/svg-ähnliche Typen mit der Ausnahme `application/vnd.openxmlformats…`; der Kontext `attachments_mime_plainxml` gilt dabei für jeden Nutzer (sonst hängt es vom Schreibrecht auf Ansichten ab), `image_no_postprocess` schaltet die Bildverkleinerung ab. Der Kopf (2048 Byte) erkennt docx/xlsx/pptx nicht, die OOXML-Typen kommen über den Dateinamen; ohne passende Endung bleibt es `application/zip`. `neuter_mimetype` (`mimetypes.py:235`) ist ungeeignet (`'xml' in mimetype` trifft OOXML). **Ablageort** über `ir.attachment._filestore()` (`ir_attachment.py:93`) und `_full_path` (`:126`, bereinigt den Pfad) statt selbst gebauter Pfade; `_get_path`/`_file_write` passen nicht (SHA-1, ganze Datei im Speicher). Hook `ir.binary._record_to_stream`. | ORM §7; Security §2; Perf §1; Coding §3 |
| 2 Rechte/Ordner | `_check_company_auto`, Archiv-Kaskade in Stapeln, `@api.ondelete`, Gruppen `int_filemanager_group_*` (Datei `int_filemanager_groups.xml`, beim Anfassen von `security.xml` umbenennen), Feldschutz wie `ir.attachment` (siehe Dokument-Modell). | ORM §1, §6–§7; Security §1; Coding §3 |
| 3 Upload | Route `POST /int_filemanager/upload`, `max_content_length` als Funktion (läuft nach der Anmeldung: `_authenticate` vor `_pre_dispatch`, `http.py:2377-2378`, Aufruf `2435-2439`; Route-Wert hat Vorrang vor `web.max_file_upload_size`). Client: Dienst `file_upload` (Vorbild `mail/…/attachment_upload_service.js`), **nicht** `FileUploader` (liest die Datei als Base64-Data-URL im Browser, `file_handler.js`). Eine Datei je Anfrage. Nummerierung bei Namenskonflikt in einer Savepoint-Schleife (die einzige Absicherung, Odoo wiederholt bei Unique-Fehlern nicht). Listenansicht als Unterklasse mit Upload-Knopf, kein Patch (Vorbild `account/static/src/views/file_upload_list/`). | ACH §3; JSF; Views |
| 4 Oberfläche | Liste, Formular, Suchpanel (`limit="0"`, `expand="1"`), Download-Knopf, „Neu“ entfällt, Übersetzungen. | Views; Coding §5 |
| 5 Aufräumer | Prüfliste nach Core-Muster (`ir_attachment.py:178-253`): eingetragen wird beim Löschen eines Dokuments, beim Ändern der Prüfsumme und beim Speichern. `@api.autovacuum`, Rückgabe `(erledigt, Rest)` ergibt Stapel (`ir_autovacuum.py:41-50`). `cr.commit()` und `LOCK … IN SHARE MODE` auf der Dokument-Tabelle vor dem Löschen (mit `lock_timeout`, bei Misserfolg später wiederholen), Gegenprüfung in der Datenbank. **Blobs ohne Schonfrist:** der Core kennt keine, die Sperre genügt für die Konsistenz. Eigenbau (und nötig) ist nur eine Altersgrenze für Temp-Dateien in `.upload/`, weil diese keine Datenbankzeile haben. Kein Vollscan des Filestores. | Perf; Coding §3 |
| 6 Einlesen | Scan legt Zeilen an. Lauf als Cron: Stapel kurz, `_commit_progress`, Savepoint je Datei, Zeilenstatus und Dokument im selben Commit, Kontext `tracking_disable=True` (überspringt Abonnieren, Log und Tracking, `mail_thread.py:324, 385`). Je Zeile `try_lock_for_update`, damit ein zweiter Cron-Lauf sie nicht doppelt nimmt. `os.walk(followlinks=False)`, `realpath` muss innerhalb der Wurzel bleiben, Symlinks überspringen und melden. Keine öffentliche Methode mit Pfadparameter. Vorab-Bericht für Namenskonflikte und Sonderfälle, Idempotenz (siehe Abschnitt 3), Wiederaufnahme. | ACH §2; Security §2; Coding §3 |
| 7 Betrieb/Messung | Aufräumer einstellen, Betriebsdoku, Prüfliste B1–B8 abnehmen. Stichprobe von einigen GB vom Bestand: Zeit, Platz, Durchsatz. Nutzer testet im Browser. | Perf |
| 8 Bestandslauf | Einlesen des Bestands, Zählung gegen die Freigabe, Stichproben-Prüfsummen. | |

Ausführung über `tools/check/tests.sh` (Wegwerf-Datenbank) und `tools/check/ui_instance.sh` (Browser-Probe). Committet wird nur auf Ansage.

## 5. Fehlerfälle

| Fall | Verhalten |
|---|---|
| Upload abgebrochen | Temp-Datei wird sofort gelöscht, bei Absturz vom Aufräumer nach der Altersgrenze. |
| Fehler nach der Ablage, vor dem Commit | Verwaiste Blob-Datei: der Aufräumer löscht sie über die Prüfliste (ohne Frist, die Sperre genügt). |
| Unique-Konflikt beim Upload | Odoo wiederholt hier **nicht**: `retrying` macht aus einem `IntegrityError` sofort einen `ValidationError` (`service/model.py:192-214`); wiederholt werden nur Sperr-, Serialisierungs- und Deadlock-Fehler. Die Savepoint-Schleife nummeriert neu; bei Dauerkonflikt lesbare Meldung. Der Fehler tritt außerhalb des Controllers auf, die Temp-Datei räumt `cr.postrollback` weg. |
| Server-Neustart mitten im Einlesen oder durch Zeitlimit | Zeilenstatus und Dokument im selben Commit, der Lauf setzt fort. Eine Datei, die wiederholt das Limit reißt, bekommt den Status „zu langsam“ statt Endlosschleife. |
| Download länger als das Zeitlimit | Ohne x-sendfile Server-Neustart (B4); mit x-sendfile liefert der Proxy. |
| Datei ändert sich beim Kopieren | Größe/mtime vor und nach vergleichen, bis zu 3 Wiederholungen, dann „instabil“. |
| Name nicht UTF-8, mit NUL, zu lang | Zeile `error`, Lauf geht weiter (Savepoint). |
| Symlink oder Pfad außerhalb der Wurzel | Zeile `error`, Lauf geht weiter. |
| Namenskonflikt (Groß/Klein, Leerzeichen, NFC/NFD) | Vorab-Bericht, Suffix „(2)“, Originalpfad bleibt in `origin_path`. |
| Datei fehlt im Filestore | Download gibt 404 mit Meldung, nie 500. |
| Manipulierte Prüfsumme | Regex `^[0-9a-f]{64}$` vor dem Pfadbau, 404. |
| Gleichzeitiger Upload derselben Datei | Eine Datei auf der Platte, ein Dokument je Name; Konflikt über Savepoint-Schleife. |
| Dedup-Treffer, Blob wird parallel aufgeräumt | Kein Verlust, weil die Zeile vor der Prüfung auf den Blob geflusht ist und der Aufräumer die Tabelle sperrt. Wettlauf-Test Pflicht. |
| Nutzer ohne Recht oder falsche Firma | 404 (`AccessError`/`MissingError` werden im Content-Controller zu 404). |
| Platte voll | `OSError`, Temp wird gelöscht, Meldung; Obergrenze per Parameter, weil `statvfs` auf Unraid-Shares lügt. |
| Cron-Zeitlimit | Callback prüft `_commit_progress` und kehrt nach etwa 10 s zurück. |
| Wiederherstellen eines Ordners, Name inzwischen vergeben | Hinweis mit Namen, Wiederherstellen abgebrochen. |
| html/svg/xml | Typ `text/plain` für Dateien aus Upload und Einlesen (über `ir.attachment._check_contents` mit Kontext `attachments_mime_plainxml`, unabhängig vom Nutzer; OOXML ausgenommen). Odoo sendet zusätzlich CSP `default-src 'none'` und `nosniff` (`Stream.get_response`, `http.py`). |

## 6. Tests (Python `TransactionCase`/`HttpCase`)

- Speicher: 1 und 2,5 GiB, Duplikate, Rollback, Aufräumer inklusive Wettlauf, Prüfsummen-Regex. Die großen Dateien unter eigenem Tag, nicht im Standardlauf.
- Typ: docx/xlsx/pptx bleiben OOXML-Typ, html/svg/xml werden `text/plain` (auch für Admins und im Einlese-Cron), über `_check_contents` mit den beiden Kontexten.
- Hook: Download, Range, ETag, 304/416, Rechte, Mehrfirmen, x_sendfile-Header (Konfiguration im Test setzen).
- Pseudo-Feld: read, copy, Export, write → Fehler. Feldschutz: `checksum`, `size`, `mimetype` per RPC-`write` ohne `su` verworfen (Wert bleibt unverändert), mit `su` gesetzt; `origin_path` für Nutzer nicht lesbar; `create` per RPC ohne `perm_create` → Fehler.
- Upload: 413 ohne die Funktion, Konflikt-Nummerierung (inklusive gleichzeitiger Uploads), Ordner Pflicht.
- Einlesen: Neustart-Simulation, Fehlerzeile, Idempotenz, zweiter Cron-Lauf, Sonderfälle, Namenskonflikte, Symlinks, NFC-Namen, `tracking_disable`.
- Archiv-Kaskade (Mengentest, Stapel) und Wiederherstellen-Konflikt.
- **Testumgebung:** `tools/check/tests.sh` startet zwar mit `--no-http`, aber bei `test_enable` startet der Server den HTTP-Daemon trotzdem (`server.py:659`; `--test-tags` setzt `test_enable`, `config.py:716-720`).
  Ein zweiter Aufruf ist deshalb nicht nötig. Aus dem Quelltext belegt, noch nicht ausprobiert: ein `HttpCase` mit `url_open('/web/login')` im bestehenden Lauf bestätigt es.
  Das Test-Image hat kein Chromium: Hoot und Tours laufen dort nicht. Den Upload-Knopf prüft der Nutzer im Browser (`ui_instance.sh`).

## 7. Abweichungen vom Standard, offengelegt

- Eigener Dateispeicher statt `ir.attachment` (Beleg: Abschnitt 1).
- `ir.binary._record_to_stream`-Override (dokumentierter Hook, `ir_binary.py`).
- Pseudo-Feld `content`, nur für `_get_stream_from`.
- Eigene Upload-Route und Upload-Knopf (der Kerndienst `file_upload` bleibt in Benutzung).
- Eigener Aufräumer; der Core-GC kennt den Ordner `int_filemanager/` nicht und fasst ihn nicht an (er arbeitet nur mit seiner Prüfliste).
- Eigene Altersgrenze für Temp-Dateien in `.upload/` (Eigenbau, der Core hat dafür nichts).
- SHA-256 statt SHA-1 (keine Bindung an `ir.attachment`).
- Einlesen mit Auftrags- und Zeilentabelle (`int.filemanager.import`/`.line`): kein Odoo-Baustein vorhanden; die Zeilen tragen Vorab-Bericht (Namenskonflikte) und Fehlerliste, Entscheidung des Nutzers 12.10.: beide Tabellen behalten.

## 8. Offene Annahmen (Standardwerte)

- Altersgrenze für Temp-Dateien 1 Tag, Archiv-Kaskade ja.
- Upload-Konflikt: automatisch nummerieren; „Neu“-Knopf entfällt.
- Wer darf Einlesen: Gruppe „Filemanager Administrator“. Wurzelpfad nur durch `base.group_system` änderbar.
- Ausschlussliste: `Thumbs.db`, `desktop.ini`, `.DS_Store`, `~$*`, `*.tmp`, `.part`, `.crdownload`. Leere Dateien werden importiert.
- Upload-Obergrenze 20 GiB als Parameter.

## 9. Noch nicht gesichert

- Echter Browser-Upload über den Proxy mit mehreren GB.
- nginx und `X-Accel-Redirect`: ob Typ, Dateiname und CSP von Odoo durchkommen.
- Verhalten von `rmtree` bei einem verschachtelten Docker-Mount (abgeleitet, nicht gemessen) und das Mount-Verhalten des Proxys.
- `HttpCase` im bestehenden Lauf mit `--no-http`.
- Aufräumer bei Millionen Einträgen.
- Platte voll auf Unraid.
- Mehrere Cron-Threads gleichzeitig.
- Regeln zu Views, JS-Framework, JS-Tests, QWeb noch nicht gelesen.

Das sind die ersten Punkte der Stufen 3, 6 und 7.
