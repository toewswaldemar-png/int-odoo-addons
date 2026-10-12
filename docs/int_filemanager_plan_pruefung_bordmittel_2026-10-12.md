# Prüfbericht: Eigenbau im Speicherplan von int_filemanager (Stand 2026-10-12)

Geprüft: `docs/int_filemanager_plan_dateispeicher_2026-10-12.md`. Die Plandatei ist unverändert. Reine Prüfung, kein Code geändert.

## Grundlage und Grenzen

- Quelle: Klon `GitHub\odoo` auf `8d05257` (24.09.). `git fetch` gemacht, `origin/19.0` steht auf `e6ebad8`.
- Der Diff über alle Dateien, auf die sich dieser Bericht stützt, zeigt nur Änderungen an drei Stellen:
  - `ir_attachment.py`: Zugriffsprüfung in `_check_access`/`_search` und `create_unique`.
  - `service/db.py`: nur `restore_db`.
  - `ir_http.py`: Übersetzungen.
  
  Speichern, Streamen, Cron, Upload und Mail sind unverändert.
- Zeilenangaben gelten für den Klon, Pfade sind relativ zum Odoo-Klon. Der Plan nennt seine eigene Kopie `docs/odoo@7a74539`. Dort passen `http.py`, `mail_thread.py` und `ir_attachment.py:475` genau. `ir_binary.py` (Plan 127–137, Klon 115–124) und `_to_http_stream` (Plan 932, Klon 913) weichen ab. Die Aussagen gelten in beiden Ständen.
- **Nicht gemacht:** nichts per `odoo shell` ausprobiert. Alle Urteile stammen aus dem Quelltext. Drei Dinge sind deshalb nur gelesen, nicht gelaufen: die Träger-Variante (Befund 1), die `file_size`-Feldklasse (Befund 2) und das Verhalten beim Deinstallieren.
- Herkunft der Funde: Lesen von `ir_attachment.py`, `ir_binary.py`, `http.py`, `ir_cron.py`, `service/server.py`, `service/db.py`, `web/controllers/binary.py`, `orm/fields_*`; gezielte Greps in `addons/` und `odoo/`; Diff gegen `origin/19.0`; die Memory-Datei zur Speicher-Topologie (nur für A5 und A6, nicht neu gemessen). Weitere Suchen brachten zuletzt keine neuen Funde mehr.

## 1. Kurzfazit

Etwa die Hälfte des Plans ist berechtigter Eigenbau: der Streaming-Schreibweg, die Upload-Route, die Archiv-Kaskade, der Einlese-Lauf, die Namenslogik und die Temp-Aufräumung. Die andere Hälfte lässt sich nativ ersetzen. Das betrifft Stufe 5 (Aufräumer samt Prüfliste und Sperre), den Hook `_record_to_stream`, das Pseudo-Feld `content`, den Handstream und die Typ-Ermittlung samt html→text/plain-Regel.

Die Ursache liegt in der Abweichung „Eigener Speicher statt `ir.attachment`“. Von den drei Begründungen in §1 trägt nur der Speicherbedarf beim Schreiben (`file.read()` lädt die ganze Datei, `ir_attachment.py:908`) voll. Die 2-GiB-Grenze von `file_size` ist nativ umgehbar (Feldklasse). Der Bildverkleinerer ist per Kontext abschaltbar (`ir_attachment.py:429`). Nativ ersetzbar sind also fast alle Folgeteile (Aufräumer, Hook, Pseudo-Feld, Handstream, Typregel), nicht der Streaming-Schreibweg selbst.

Außerhalb des Eigenbaus gibt es einen Befund zum Betrieb: Der Plan geht von `limit_time_real = 1800` aus. Der Default ist 120 s, und ein 15-GB-Upload läuft darüber (A1).

## 2. Tabelle

| # | Plan-Abschnitt | Eigenbau-Punkt | Urteil | Odoo-Mittel | Konsequenz für den Plan |
|---|---|---|---|---|---|
| 1 | §1, §7, Stufe 1 | Eigener Blob-Speicher `int_filemanager/<sha256[:2]>/…` | **NATIV TEILWEISE** | `ir_attachment.py:125` `_full_path`, `:177` `_mark_for_gc`, `:287` `_set_attachment_data` (Muster `super(IrAttachment, attach.sudo()).write(vals)`), `:913` `_to_http_stream`. Aber `:908` `'raw': file.read()  # load the entire file in memory :(` und `:158` `_file_write` brauchen alles im RAM. | Ein `ir.attachment` je Dokument als Träger (`res_model`/`res_id`/`res_field='data'`), `data = Binary(attachment=True)`. Der Streaming-Schreibweg bleibt Eigenbau. `store_fname`, `checksum` und `file_size` setzt man per Basis-`write` am Core-`write` vorbei, wie `_set_attachment_data` es tut. Die Core-`create`/`write` verwerfen diese Felder (`ir_attachment.py:723`, `:762`). |
| 2 | §1, §3 | `size` als Float wegen `file_size` int4 | **NATIV TEILWEISE** | `orm/fields_numeric.py:20` (`_column_type=('int4','int4')`); `orm/model_classes.py:414` (`Field = type(fields_[-1])`, die zuletzt definierte Klasse gewinnt); Präzedenz für eine Feldsubklasse mit eigenem Spaltentyp: `addons/base_sparse_field/models/fields.py:77-81`; `fields_numeric.py:44-48` `convert_to_read` behandelt Werte > MAXINT schon. | Kein mitgelieferter Bigint-Typ (Plan stimmt). Eine Subklasse `BigInteger(Integer)` mit `_column_type=('int8','int8')` genügt, im Träger-Fall auch als Redefinition von `ir.attachment.file_size`. Risiko: Beim Deinstallieren konvertiert Odoo die Spalte zurück auf int4, das schlägt mit Werten > 2^31 fehl. Alternative ohne Kerneingriff: `file_size` bleibt 0, die Wahrheit liegt im eigenen Feld. Beides nicht ausprobiert. |
| 3 | §1, Stufe 1 | Eigene Typ-Reihenfolge Client → Name → Kopf | **NATIV MÖGLICH** | `ir_attachment.py:353` `_compute_mimetype` (genau diese Reihenfolge); `:418` `_check_contents`; Kontexte `attachments_mime_plainxml` (`:424`) und `image_no_postprocess` (`:429`). Externe Aufrufer: `addons/project/controllers/portal.py:573` (`_check_contents`), `addons/mail/models/mail_thread.py:1344` (Kontext). | `ir.attachment.with_context(attachments_mime_plainxml=True, image_no_postprocess=True)._check_contents({'name', 'mimetype', 'raw': kopf})` liefert `values['mimetype']`. Die Regel „html/xml/svg → text/plain, OOXML ausgenommen“ ist dort wortgleich (`:419-428`). Die eigene Regel entfällt. |
| 4 | §3, Stufe 1 | Hook `ir.binary._record_to_stream`, Pseudo-Feld `content`, Handstream, ETag, 404-Logik | **NATIV MÖGLICH** (bei Träger-Attachment) | `ir_binary.py:57-82`: Bei `field.attachment` sucht der Standard das Attachment `res_field=data` und ruft `_to_http_stream()`. `:115-124` verlangt ein echtes Binary-Feld. `http.py:670-678` liefert x-sendfile für Pfad-Streams. `tools/_vendor/send_file.py:151` (Content-Disposition `filename*`), `:209-212` (Range/416/304). | Das Pseudo-Feld ist nur wegen Punkt 1 nötig. Mit Träger entfallen Hook, Feld `content` und Handstream. Bleiben muss ein kleiner Override von `ir.attachment._to_http_stream` für „Datei fehlt → 404“: `os.stat` wirft `FileNotFoundError` (kein `UserError`), und `content_common` fängt nur `UserError` (`web/controllers/binary.py:76`). |
| 5 | Stufe 5, §5 | Aufräumer: Prüfliste, `LOCK … IN SHARE MODE`, `@api.autovacuum`, Dedup-Wettlauf | **NATIV MÖGLICH** (bei Träger-Attachment) | `ir_attachment.py:177` `_mark_for_gc`, `:191-245` `_gc_file_store` (Prüfliste, `LOCK ir_attachment IN SHARE MODE`, Whitelist über `store_fname`); `orm/models.py:4231`, `:4333` entfernen beim Löschen alle Attachments zu `res_model`/`res_id` und rufen `_file_delete`. | Der Plan baut diesen Mechanismus für die eigene Tabelle nach. Mit Träger-Attachments löscht der Core die Blobs selbst, auch bei Referenz durch mehrere Dokumente. Es bleibt nur die Altersgrenze für `.upload/` (Zeile 12). |
| 6 | §1, Stufe 1 | SHA-256 statt SHA-1, eigenes Regex | **EIGENBAU BERECHTIGT** (Nutzerentscheidung) | `ir_attachment.py:476` `checksum = Char(size=40)`, `:327` SHA-1 | Bei Träger-Attachment passt SHA-256 (64 Zeichen) nicht in `checksum`. Der Blob-Pfad `store_fname` darf trotzdem SHA-256 sein, das Core-GC liest nur `store_fname`. `checksum` hält parallel SHA-1 (ETag), beim Streamen zwei Hashes. Das Regex lässt sich als `models.Constraint("CHECK (… ~ …)")` ausdrücken (`orm/table_objects.py:79`). |
| 7 | Stufe 1 | Blockweises Schreiben in Temp, Hash beim Schreiben, `os.replace` | **EIGENBAU BERECHTIGT** | Gesucht: `ir_attachment.py` (alle Schreibwege laden RAM), `web/controllers/binary.py:~235`, `_from_request_file` `:908`; `addons/cloud_storage` (nur signierte URLs zu Azure/Google, `models/ir_attachment.py:17-45`, kein lokales Ziel). | Bleibt. Die Reihenfolge flush → `os.replace` entspricht dem Core-Muster (`ir_attachment.py:293-301`) und wird durch Punkt 1 noch genauer an den Core gebunden. |
| 8 | Stufe 3 | Route `POST /int_filemanager/upload`, `max_content_length` als Funktion | **EIGENBAU BERECHTIGT** (Mechanismus nativ) | `http.py:2377-2378` (`_authenticate` vor `_pre_dispatch`), `:2435-2439` (callable), `:247` (128 MiB); `ir_http.py:306` (`web.max_file_upload_size`, gilt global) | Route-Callable ist der native Weg. Ein eigener Parameter statt des globalen ist richtig, sonst fiele die Grenze für alle Routen. |
| 9 | Stufe 3 | Upload-Client | **NATIV TEILWEISE** | `web/static/src/core/file_upload/file_upload_service.js:35-52` (FormData, `ufile`, CSRF, Fortschritt); `web/static/src/views/fields/file_handler.js` nutzt `getDataURLFromFile`, also Base64 (Plan stimmt); `account/static/src/views/file_upload_list/` | Dienst wird genutzt, `FileUploader` korrekt vermieden. Die Listen-Unterklasse mit Upload-Knopf bleibt Eigenbau, im Core gibt es das nur in `account`. |
| 10 | Stufe 3 | Nummerierung bei Namenskonflikt | **EIGENBAU BERECHTIGT** | `utm/models/utm_mixin.py:106` `_get_unique_names` sucht global per `ilike` auf `name` (UTM-spezifisch, kein Ordnerbezug, nur „[n]“) | Die Savepoint-Schleife bleibt (Retry greift bei `IntegrityError` nie, `service/model.py:192-214` bestätigt). |
| 11 | §3, Stufe 2 | Schreibschutz für `checksum`/`size`/`mimetype`/`origin_path` per `env.su` | **NATIV TEILWEISE** | `ir_attachment.py:723` (`write` verwirft `file_size`/`checksum`/`store_fname`); Feld-`groups=` sperrt auch das Lesen; `readonly` wirkt nur in der UI. | Im Träger-Fall liegen diese Werte am Attachment, wo der Core sie schon schützt. Der Schutz bleibt nur für `origin_path` und den Typ. Der `env.su`-Override schrumpft auf zwei Felder. |
| 12 | Stufe 2 | Archiv-Kaskade in Stapeln | **EIGENBAU BERECHTIGT** | Gesucht in `orm/*.py`, `base/models`, `addons/*/models`: kein deklarativer Archiv-Kaskadenmechanismus gefunden | Bleibt. |
| 13 | Stufe 2, §5 | Vorabprüfung beim Wiederherstellen | **NATIV TEILWEISE** | `orm/table_objects.py:185-205` (`UniqueIndex` mit Meldung); `service/model.py:~195-205` übersetzt `IntegrityError` in `ValidationError` mit `_sql_error_to_message`. Der Index ist `WHERE active`, trifft also beim Reaktivieren. | Die Konfliktmeldung kommt nativ. Nur der Hinweis „mit Namen“ wäre Zusatz. Die Vorprüfung kann klein bleiben. |
| 14 | Stufe 6 | Einlese-Cron mit `_commit_progress`, `tracking_disable`, Savepoint je Datei | Native Nutzung | `ir_cron.py:846` `_commit_progress` (liefert Restzeit), `:485` `MIN_TIME_PER_JOB = 10`; `mail_thread.py:324`, `:385` (`tracking_disable`); `sql_db.py:217` `savepoint` | Berechtigte Nutzung. |
| 15 | Stufe 6 | `try_lock_for_update` je Zeile gegen zweiten Cron-Lauf | **NATIV TEILWEISE** (weitgehend entbehrlich) | `ir_cron.py:308-365` (`FOR NO KEY UPDATE SKIP LOCKED` auf der Job-Zeile), `:156-166` (`method_direct_trigger`: „Job already executing“) | Derselbe Cron läuft nie parallel. Die Zeilensperre braucht es nur bei einem zweiten Einstiegspunkt. Das offene Thema „mehrere Cron-Threads“ (§9) entfällt in dieser Form. |
| 16 | §3, Stufe 6 | `int.filemanager.import(.line)`, `os.walk` | **EIGENBAU BERECHTIGT** | `grep os.walk/scandir` über `addons`/`odoo`: kein Dateisystem-Import im Core außer `base_import_module` (Modul-ZIPs); `base_import` liest CSV/XLSX | Bleibt. Die Line-Tabelle (400k Zeilen) ist eine Abwägung, kein Bordmittel-Thema. |
| 17 | §3 | NFC-Normalisierung der Namen | **EIGENBAU BERECHTIGT** | `unicodedata.normalize` nur in `ir_http.py:156-162` (Slug), `tools/misc.py:719` (Entakzentuierung), `web/controllers/binary.py:234` (Safari-NFD) | Kein Helfer für Dateinamen. |
| 18 | §3, Stufe 1 | `neuter_mimetype` verworfen | Plan stimmt | `tools/mimetypes.py:235-239` (`'xml' in mimetype`, trifft OOXML) | Entfällt mit Zeile 3 ohnehin. |
| 19 | Stufe 4 | `size_field.js` und Template | **NATIV TEILWEISE** | `web/static/src/core/utils/binary.js:24` `humanSize` (exportiert, Format „2.00 Kb“); Python `tools/misc.py:519` `human_size` | Das Widget ist kosmetisch. Es darf `humanSize` importieren, das Format wäre dann ein anderes. |
| 20 | §3, Stufe 2 | Gruppen, `ir.rule`, `res.config.settings`, `_check_company_auto`, `models.Index`, `@api.ondelete` | Native Nutzung | `orm/models.py:451`, `:4522`; `orm/table_objects.py:125` | Berechtigte Nutzung. |

### Risiken der Träger-Variante

- Die Dateien liegen dann in `ir.attachment` und unterliegen dessen Admin-Funktionen. `force_storage` und `_migrate` (`ir_attachment.py:~96-110`) lesen per `attach.raw` komplett ins RAM. Ein Admin, der `ir_attachment.location` auf `db` stellt, würde 15-GB-Dateien laden. Das müsste per Betriebsregel ausgeschlossen werden. Der eigene Speicher wäre dagegen immun.
- `ir.attachment` bekommt 400k Zeilen mehr. Das Bestandsmodul tut das schon (Prototyp, laut Memory gemessen).
- Der Core bleibt auf SHA-1 im Feld `checksum` (Punkt 6).

## 3. Falsche oder ungeprüfte Annahmen im Plan

**A1 – Zeitlimit (B7, B4): Plan nennt 1800 s, Default ist 120 s.**
- Beleg: `tools/config.py:487` hat `my_default=120`. Die Memory-Messung vom 12.10. (SSH) bestätigt: auf HM-SRV ist `limit_time_real` nicht gesetzt, 1800 gilt nur für `limit_time_real_cron`.
- Folge: HTTP-Threads bekommen `start_time` beim Annehmen der Verbindung (`service/server.py:299-300`). `process_limit` prüft sie gegen `limit_time_real` (`:520-529`), danach folgt `reload()` (`:740-753`). Der Plan behandelt nur Cron und Download. Ein 15-GB-Upload, schon bei 110 MB/s über 130 s, überschreitet die 120 s und löst einen Server-Neustart aus. Dafür fehlt im Plan jede Maßnahme (global `limit_time_real` anheben oder Prefork). `--limit-time-real-cron` hilft hier nicht.

**A2 – Interner Widerspruch.** §1 sagt „Nur zwei nötige Abweichungen“, §7 listet sieben. Der Plan beweist selbst, dass nicht alle Folgeteile nötig sind.

**A3 – „Kein Bigint-Feldtyp, deshalb Eigenspeicher“.** Der erste Teil stimmt (`fields_numeric.py:20`). Der Schluss nicht: Eine Feldsubklasse mit eigenem `_column_type` ist im Core vorgesehen (`base_sparse_field/models/fields.py:77-81`), und `model_classes.py:414` übernimmt die zuletzt definierte Klasse. Der int4-Beleg begründet den Eigenspeicher also nicht allein.

**A4 – Bildverkleinerer als Begründung für die Abweichung.** `_postprocess_contents` ist per `image_no_postprocess` abschaltbar (`ir_attachment.py:429`). Das Argument trägt nicht.

**A5 – B1/B4/B6 (Symlink) widersprechen der Entscheidung vom 12.10.** Laut Memory liegt der ganze Filestore auf dem Share ohne Symlink. Memory belegt außerdem veraltete Werte im Plan (nicht neu geprüft):
- B8: frei 3,6 TB, tatsächlich 2,3 TB (nach dem Import bleiben rund 0,4 TB).
- B1: Cache 86 GB frei, gemessen 117 GB.

**A6 – Sicherheitsrisiko nicht erwähnt (Memory, nicht Quelltext).** Auf HM-SRV ist `list_db` Default True und `admin_passwd = admin`. `exp_drop` löscht den Filestore mit `shutil.rmtree` (`service/db.py:253-255`), nach dem Wegfall des Symlinks heißt das: 1,9 TB. B6 sagt nur „CLI nicht anwenden“. Vor dem Einlesen müssen `admin_passwd` und `list_db` gesetzt werden.

**A7 – `try_lock_for_update` gegen zweiten Cron-Lauf und „Mehrere Cron-Threads“ (§9).** Siehe Tabelle Zeile 15: Der Core sperrt die Job-Zeile selbst.

**A8 – x-sendfile-Pfad.** `http.py:670-673` testet `Path(self.path).relative_to(opj(config['data_dir'], 'filestore'))` mit dem nicht normalisierten `data_dir`. Der Core baut seinen Stream-Pfad aus `os.path.abspath(config.filestore(db))` (`ir_attachment.py:~928`). Der Plan nennt `safe_join` auf den Filestore, aber nicht `abspath`. Bei relativem `data_dir` fällt x-sendfile still aus (`ValueError` wird unterdrückt), und der Python-Thread liefert die ganze Datei. Gering, aber prüfenswert.

### Bestätigt (stimmen genau so)

- `content` muss ein echtes Binary-Feld sein (`ir_binary.py:115-124`).
- x-sendfile braucht einen Pfad unter `<data_dir>/filestore` (`http.py:670-678`).
- 128 MiB liegt in der HTTP-Schicht (`http.py:247`), die Reihenfolge `_authenticate` → `_pre_dispatch` stimmt (`:2377-2378`).
- `IntegrityError` wird zu `ValidationError` (`service/model.py`).
- `tracking_disable` (`mail_thread.py:324`, `:385`).
- OOXML-Erkennung braucht die ganze Zip-Datei (`tools/mimetypes.py:213-228`).
- `file_path` kennt nur Addon-Pfade (`tools/misc.py:196-236`).
- Die CLI setzt `list_db=True` selbst (`cli/db.py:198`).
- `duplicate` und `dump` kopieren den Filestore (`service/db.py:210-212`, `dump_db`).
- Test-HTTP-Daemon startet auch mit `--no-http` (`server.py:659`, `config.py:716-720`).
- `CONSECUTIVE_TIMEOUT_FOR_FAILURE = 3` (`ir_cron.py:35`).
- Autovacuum `(erledigt, Rest)` bildet Stapel (`ir_autovacuum.py` um Zeile 50).

## 4. Änderungsvorschläge in der Reihenfolge ihrer Wirkung

1. **Träger-Attachment statt eigenem Speicher entscheiden (Punkte 1, 4, 5):** Das streicht Hook, Pseudo-Feld, Handstream, den kompletten Aufräumer samt Prüfliste, LOCK und Wettlauftest. Es bleibt nur der Streaming-Schreibweg, der `.upload/`-Cleanup und der 404-Override.
2. **A1 klären:** `limit_time_real` und den 120-s-Default gegen den 15-GB-Upload planen (Uploadzeit messen, global anheben oder Prefork), sonst scheitert Stufe 7.
3. **`file_size` als Bigint-Subklasse lösen oder bewusst auf 0 lassen (Punkt 2):** Das Deinstallationsrisiko vorher mit `odoo shell` bestätigen.
4. **Typ-Ermittlung über `ir.attachment._check_contents` mit den zwei Kontexten ersetzen (Punkt 3):** Das entfernt die eigene Reihenfolge, die eigene Plain-Text-Regel und deren Test.
5. **Wenn Träger: SHA-256 nur im Pfad `store_fname`, SHA-1 in `checksum` (Punkt 6):** Das entscheidet der Nutzer, nicht der Quelltext.
6. **Betriebsabschnitte B1, B4, B6, B8 auf die Entscheidung vom 12.10. umschreiben (A5),** und `admin_passwd`/`list_db` als eigenen Punkt vor dem Einlesen aufnehmen (A6).
7. **§1 und §7 angleichen (A2):** Nach der Änderung bleiben nur wenige echte Abweichungen: Streaming-Schreibweg, Upload-Route, `.upload/`-Altersgrenze.
8. **Zeilensperre je Import-Zeile streichen (Punkt 15) und den Punkt „Mehrere Cron-Threads“ aus §9 entfernen.**

## Offen

Die Plandatei ist von diesen Funden in großen Teilen betroffen (§1, §2 B1/B4/B6/B7/B8, §3, Stufen 1, 3 und 5, §5, §7, §9). Eingearbeitet ist noch nichts. Vorher ist die Entscheidung zu Vorschlag 1 nötig (Träger-Variante ja/nein), weil davon abhängt, was in der Datei bleibt.
