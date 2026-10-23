# int_filemanager: Größe der Modelle Dokument und Text (Prüfung und Vorschlag, 23.10.2026)

Stand: nur geprüft, nichts geändert, keine Tests gelaufen. Entscheidung offen (siehe unten).

## 1. Frage

Sind `models/int_filemanager_document.py` (1209 Zeilen) und `models/int_filemanager_text.py` (1560 Zeilen) zu groß, und wie würde Odoo sie aufteilen?

## 2. Befund im Odoo-19-Quelltext

- Größe allein ist kein Verstoß. Der Core hält große Modelle in einer Datei: `account/models/account_move.py` 7503 Zeilen, `mail/models/mail_thread.py` 5141, `stock/models/stock_move.py` 2837.
- Die Richtlinie (`docs/odoo19_reference/contributing/coding_guidelines.md:58`) sagt nur: eine Datei je Hauptmodell, benannt nach dem Hauptmodell.
- Ein Addon, das sein eigenes Modell in einer zweiten Datei per `_inherit` erweitert, kommt im Core in 9 Fällen vor, zum Beispiel `account_journal_dashboard.py` (1200 Zeilen), `account_move_line_tax_details.py`, `website_form.py`. Muster des Dateinamens: `<modell>_<thema>.py`. Dasselbe Muster hat das Modul schon bei `int_filemanager_document_link.py`.
- Wiederverwendbare Teile zieht der Core als eigene abstrakte Modelle heraus (`mail.thread.cc`, `mail.thread.blacklist`), nicht per `_inherit` desselben Modells.
- Eine frühere Aussage, der Core würde große Modelle nach Thema auf mehrere Dateien verteilen, war zu stark und gilt nicht. Die Aufteilung ist erlaubt und belegt, aber nicht vorgeschrieben.

## 3. Was in den Dateien steckt

### `int_filemanager_text.py` (1560 Zeilen)

Zwei getrennte Abläufe mit eigenen Feldern.

| Teil | Zeilen | Felder |
|---|---|---|
| Text lesen, Status, Cron | ca. 870 | ca. 10 |
| Texterkennung (OCR) | ca. 600 | 13 mit Vorsilbe `ocr_` |

Nahtstelle: 10 Verweise zwischen den Teilen.

- Lesen ruft OCR: `_missing_where` → `_ocr_options`, `_ocr_queue` → `_ocr_options`, `_requeue_stale` → `_ocr_after_failure`, `_reset` → `_ocr_drop_job` und `_ocr_restart_values`, `_text_source` → `_ocr_section_path`.
- OCR ruft Lesen: `_ocr_accept` → `_run_reader` und `_store_pages`, `_ocr_finish` → `_count_scan_pages` und `_has_text`.
- Zusätzlich greifen `_work_left` und `_ocr_status` (Status und Cron) auf OCR zu.
- Bei einer Aufteilung per `_inherit` laufen diese Aufrufe über `self` unverändert weiter. Die Hauptdatei kennt die Texterkennung aber weiterhin.

Nur von der Texterkennung benutzt: 15 Konstanten und die Hilfen `_probe`, `_image_info`, `_remove_path`, `_last_line`.

### `int_filemanager_document.py` (1209 Zeilen)

| Teil | Zeilen |
|---|---|
| Felder, Inhaltssuche, `write`/`unlink`, Download, ZIP, Streams | ca. 600 |
| Blob-Speicher (`_blob_path`, `_store_stream`, `_publish_blob`, `_mark_blob_for_gc`, `_gc_blobs`, `_create_from_stream`, `_create_numbered`) | ca. 280 |
| Vorschaubild und Office-Vorschau (zwei Crons) | ca. 230 |
| Konstanten | ca. 120 |

- Der Blob-Speicher hat keine eigenen Felder, nur Methoden mit `@api.model`.
- Er wird als Methode am Dokument aufgerufen: von über 20 Testdateien, von beiden Controllern, vom Import (`int_filemanager_import_line.py`), vom Text-Modell und von der Freigabe.
- Er darf deshalb nicht in ein anderes Modell wandern (alle Aufrufstellen änderten sich).
- Ein Mixin ist riskant: `ir.autovacuum` ruft jede `@api.autovacuum`-Methode für jedes Modell der Registry auf, auch für abstrakte; `_gc_blobs` liefe doppelt (einmal für das Mixin, einmal für das Dokument).
- Gleichmodell-Dateien mit `_inherit` lassen alle Aufrufe unberührt.

## 4. Weitere Befunde, unabhängig von der Aufteilung

- Doppelte Konstanten: `PDF` in `int_filemanager_document.py`, `int_filemanager_text.py` und `tools/extract_text.py`; `NAME_TRIES` in Dokument, Ordner und Importzeile.
- Alias statt eigener Wert: `CRON_XMLID = TEXT_CRON_XMLID` in der Text-Datei.
- Private Hilfen werden dateiübergreifend importiert: `res_config_settings.py` holt `_probe` aus der Text-Datei, die Text-Datei holt `_remove_file` aus der Dokument-Datei; die Dokument-Datei holt `folded` aus `int_filemanager_text_page.py`.
- Rund 50 Zeilen reine Hilfsfunktionen ohne ORM hängen an den Modellen (`_probe`, `_image_info`, `_remove_path`, `_last_line`, `_is_scan_text`, `_remove_file`, `_files_in`). Das Modul hat dafür schon `tools/`.
- Sechs Stellen starten Programme mit `subprocess` (`_draw_first_page`, `_preview_run`, `_probe`, `_image_info`, `_run_reader`, `_ocr_run`). `nice -n … timeout --kill-after=…` steht fast wortgleich in `_preview_run` und `_ocr_run`.

## 5. Vorschlag

Jede Stufe ist ein eigener Commit, der nur verschiebt und kein Verhalten ändert (Regel „kleiner Diff, bei großem Umbau erst ein reiner Verschiebe-Commit“).

### Stufe 1: aufräumen (klein, sicher), umgesetzt am 23.10.2026

- `tools/files.py`: `remove_file`, `remove_path` (vorher `_remove_file` in der Dokument-Datei, `_remove_path` in der Text-Datei).
- `tools/programs.py`: `probe`, `image_info`, `last_line` (vorher private Funktionen der Text-Datei; `res_config_settings.py` importierte `_probe` aus ihr) und `limited(command, seconds, nice, kill_after)`, der gemeinsame Vorsatz `nice -n … timeout --kill-after=…` von `_preview_run` und `_ocr_run`. Die Zeiten und die Priorität übergeben die Modelle beim Aufruf, weil die Tests `KILL_GRACE_SECONDS` im Modul patchen.
- `NAME_TRIES` steht einmal in `tools/clash.py` (vorher Dokument, Ordner, Importzeile).
- `PDF` und `TEXT_CRON_XMLID` kommen in der Text-Datei aus der Dokument-Datei; der Alias `CRON_XMLID` entfällt.
- Tests: `test_text_ocr_images.py` importiert `image_info` aus `tools`; neu `tests/test_tools_programs.py`.
- Nicht verschoben: `GC_BATCH` (zwei verschiedene Einstellungen mit gleichem Wert: Blobs je Lauf im Dokument, Texte je Lauf im Text; die Tests patchen es je Modul), `_files_in` (nur vom ZIP des Dokuments benutzt), `_is_scan_text` (nur vom Lesen benutzt), `PDF` in `tools/extract_text.py` (läuft als eigenes Programm mit `-I` und kann nichts importieren).

### Stufe 2: Dateien nach Thema trennen

Modelle und Namen bleiben gleich. Muster `<modell>_<thema>.py`, Reihenfolge in `models/__init__.py`: Hauptdatei zuerst, Erweiterungen danach.

| Neue Datei | Inhalt | Größe |
|---|---|---|
| `int_filemanager_text_ocr.py` | `ocr_*`-Felder, OCR-Ablauf, `action_recognize_again`, `_gc_ocr_jobs` | ca. 620 |
| `int_filemanager_document_storage.py` | Blob-Speicher, Anlegen aus Stream, Aufräumen der Blobs | ca. 330 |
| `int_filemanager_document_rendition.py` | Vorschaubild und Office-Vorschau, beide Crons | ca. 290 |

Danach: Text-Hauptdatei ca. 830 Zeilen, Dokument-Hauptdatei ca. 600. ZIP und Download bleiben im Dokument.

### Prüfung je Commit

- Syntaxbaum-Vergleich: vorher und nachher jede Methode und jedes Feld identisch, nur an anderer Stelle.
- Hook „Odoo guidelines check“ ohne offene MUST-FIX-Meldung.
- Python-Tests des Moduls auf dem Tower (`tools/check/tests.sh`).

### Nutzen und Grenzen

- Gewinn: schnellere Orientierung, Änderungen an Texterkennung, Speicher und Vorschau berühren getrennte Dateien.
- Nicht gelöst: die Abhängigkeiten zwischen den Teilen bleiben bestehen, nur auf mehrere Dateien verteilt.
- Pflicht ist die Aufteilung nicht: der Core käme mit den jetzigen Größen genauso aus.

## 6. Offene Entscheidung

Stufe 1 allein oder Stufe 1 und 2? Empfehlung: beide. Stufe 1 macht die Trennung in Stufe 2 erst sauber, weil die Hilfsfunktionen sonst im Weg sind. Stufe 2 kann auch später kommen, ohne dass Stufe 1 umsonst war.

## 7. Stufe 2 in drei kleinen Schritten (Plan vom 23.10.2026, noch nichts umgesetzt)

Jeder Schritt ist eine eigene Sitzung und ein eigener Commit `[REF] int_filemanager: move … to …`. Reihenfolge nach Größe des Risikos: 2a, 2b, 2c. Alle Schritte verschieben nur; keine Zeile ändert ihr Verhalten.

**Regeln für alle drei Schritte (Fallen, die sich beim Planen gezeigt haben):**

1. Die Erweiterungsdatei steht in `models/__init__.py` **nach** der Hauptdatei und importiert nur **aus** der Hauptdatei, nie umgekehrt. Sonst wird die Klasse der Erweiterung vor dem Basismodell angelegt und das Laden schlägt fehl. Was beide Dateien brauchen, bleibt in der Hauptdatei oder geht nach `tools/`.
2. Die Tests patchen Konstanten und Module über den Pfad der Datei (`patch(f"{MODULE}.NAME", …)`, `{MODULE}.subprocess.run`, `{MODULE}.importlib.util.find_spec`, `{MODULE}.shutil.which`). Wandert der Code, wandert der Pfad: `MODULE` in diesen Tests auf die neue Datei umstellen, sonst wirkt der Patch ins Leere und der Test läuft grün oder rot aus dem falschen Grund.
3. Prüfung je Schritt: Syntaxbaum-Vergleich vorher/nachher (jede Methode und jedes Feld unverändert, nur an anderer Stelle; Skript wie in der Sitzung vom 23.10., Vergleich pro Klassenmitglied), Ruff über `pre_commit`, Tests der betroffenen Dateien mit `tools/check/tests.sh --test-tags "/int_filemanager:<Klasse>"`, am Ende von 2c einmal die ganze Suite (`tools/check/tests.sh`, ca. 4,5 Minuten, 994 Tests am 23.10.).
4. Danach prüfen, dass `grep` auf die Methodennamen keine Aufrufstelle außerhalb der Dateien übersieht (Controller, Import, Freigabe, Text, Tests).

### 2a: `int_filemanager_text_ocr.py` (aus `int_filemanager_text.py`, ca. 620 Zeilen)

- Felder: `ocr_state`, `ocr_message`, `ocr_next_page`, `ocr_file`, `ocr_file_size`, `ocr_attempts`, `ocr_found_pages`, `ocr_seconds_per_page`, `ocr_checksum`, `ocr_size`; dazu `_ocr_checksum_is_sha256`, `_ocr_work_index`, `_unqueued_index`.
- Methoden: alles ab `_flag` (`_ocr_options`, `_ocr_tools`, `_ocr_blocked`, `_ocr_block`, `_ocr_ready`, `_ocr_step`, `_ocr_dir`, `_job_dir`, `_ocr_section_path`, `_ocr_pages_left`, `_ocr_pages`, `_ocr_section`, `_ocr_io_failed`, `_ocr_run`, `_ocr_timed_out`, `_ocr_conclude`, `_ocr_accept`, `_ocr_finish`, `_ocr_after_failure`, `_ocr_fail`, `_ocr_clean_job`, `_ocr_drop_job`, `_ocr_forget`, `_ocr_restart_values`, `action_recognize_again`, `_gc_ocr_jobs`), dazu `_ocr_status` und `_ocr_queue`, `_scan_page_counts`, `_count_scan_pages` prüfen (Lesen und OCR rufen sie beide).
- Nur-OCR-Konstanten (wandern mit): `DEFAULT_LANGUAGES`, `OCR_BLOCK_PARAMETER`, `OCR_BLOCK_SECONDS`, `OCR_FOLDER`, `OCR_LANGUAGES`, `OCR_OUTPUT_TYPES`, `STDERR_BYTES`, `TOOLS_CACHE_SECONDS`, `KILL_GRACE_SECONDS`, `MIN_TEACH_SECONDS`, `MIN_READ_SECONDS`, `JOB_MIN_AGE_SECONDS`, `_tools_cache`.
- Bleiben in der Hauptdatei, weil Lesen und `_cron_ocr` sie brauchen: `OCR_PROGRESS`, `OCR_IDLE`, `OCR_NO_TIME`, `IMAGE_TYPES`, `MESSAGE_LENGTH`, `PDF`-Import, `TEXT_CRON_XMLID`-Import.
- Nahtstelle (10 Verweise, laufen über `self` unverändert): Lesen → OCR in `_missing_where`, `_ocr_queue`, `_requeue_stale`, `_reset`, `_text_source`; OCR → Lesen in `_ocr_accept` (`_run_reader`, `_store_pages`) und `_ocr_finish` (`_count_scan_pages`, `_has_text`); `_work_left` und `_ocr_status` greifen auf OCR zu.
- Tests, deren `MODULE`-Pfad sich ändert: `test_text_ocr.py` (`MIN_READ_SECONDS`, `MIN_TEACH_SECONDS`, `JOB_MIN_AGE_SECONDS`), `test_text_ocr_plan.py` (`KILL_GRACE_SECONDS`), `test_text_ocr_settings.py`, `test_text_ocr_images.py`. `test_text_search.py` patcht `GC_BATCH` und `MIN_ATTEMPT_SECONDS` der Hauptdatei: unverändert.
- `res_config_settings.py` prüfen auf Importe aus der Text-Datei (`SETTINGS` bleibt in der Hauptdatei).

### 2b: `int_filemanager_document_storage.py` (aus `int_filemanager_document.py`, ca. 330 Zeilen)

- Methoden: `_blob_path`, `_store_stream`, `_publish_blob`, `_upload_dir`, `_checklist_dir`, `_mark_blob_for_gc`, `_checklist_entries`, `_gc_blobs`, `_gc_blob_uploads`, `_create_from_stream`, `_clean_name`, `_create_numbered`. Keine Felder.
- Konstanten: `BLOB_LOCK_NAME`, `CHECKLIST_FOLDER`, `CHUNK_SIZE`, `DEFAULT_UPLOAD_MAX_AGE_HOURS`, `GC_BATCH`, `GC_LOCK_TIMEOUT`, `HEAD_SIZE`, `NAME_MAX_LENGTH`, `UPLOAD_AGE_PARAMETER`, `UPLOAD_FOLDER`. `BLOB_FOLDER` und `CHECKSUM_REGEX` bleiben in der Hauptdatei (Text-Datei und ZIP brauchen sie).
- Alles bleibt als Methode am Dokument aufrufbar; Controller, Import, Freigabe und Text ändern sich nicht. Kein Mixin und kein eigenes Modell (sonst liefen die `@api.autovacuum`-Methoden doppelt).
- Tests: `test_document_cleaner.py` (`GC_BATCH`-Pfad), `test_document_storage.py`, `BLOB_LOCK_NAME`-Import (`test_document_upload.py` o. ä., per `grep` finden).

### 2c: `int_filemanager_document_rendition.py` (aus `int_filemanager_document.py`, ca. 290 Zeilen)

- Felder: `thumbnail`, `thumbnail_state`, `preview_checksum`, `preview_state`; Indizes `_thumbnail_work_index`, `_preview_work_index`, `_preview_thumbnail_work_index`, `_preview_checksum_is_sha256`.
- Methoden: `_thumbnail_domain`, `_cron_thumbnails`, `_make_thumbnail`, `_draw_first_page`, `_preview_domain`, `_preview_counts`, `_cron_previews`, `_make_preview`, `_convert_to_pdf`, `_preview_run`.
- Konstanten: `PDF_THUMBNAIL`, `THUMBNAIL_*`, `PREVIEW_*`, `THUMBNAIL_CRON_XMLID`, `PREVIEW_CRON_XMLID`, `PREVIEW_EXTENSIONS`; `PDF` und `TEXT_CRON_XMLID` bleiben in der Hauptdatei (die Text-Datei importiert sie), `_logger` je Datei.
- Achtung: `PREVIEW_EXTENSIONS` und `PDF` braucht auch die Hauptdatei (`STORAGE_FIELDS`, Text-Modell) und `_preview_*_index` benutzt `PREVIEW_EXTENSIONS` schon bei der Klassendefinition. Daher `PREVIEW_EXTENSIONS` in der Hauptdatei lassen und in der Erweiterung importieren.
- Tests mit Pfad `…int_filemanager_document` für `subprocess.run`, `shutil.which`, `importlib.util.find_spec`: `test_document_office_preview.py`, `test_document_thumbnail.py` auf die neue Datei umstellen; `THUMBNAIL_CRON_XMLID`-Importe in `test_document_thumbnail.py`, `test_document_office_preview.py`, `test_share_upload.py`.
