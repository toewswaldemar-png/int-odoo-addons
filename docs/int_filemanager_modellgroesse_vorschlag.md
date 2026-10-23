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

- Doppelte Konstanten: `PDF` in `int_filemanager_document.py`, `int_filemanager_text.py` und `tools/extract_text.py`; `GC_BATCH` in Dokument und Text; `NAME_TRIES` in Dokument, Ordner und Importzeile.
- Alias statt eigener Wert: `CRON_XMLID = TEXT_CRON_XMLID` in der Text-Datei.
- Private Hilfen werden dateiübergreifend importiert: `res_config_settings.py` holt `_probe` aus der Text-Datei, die Text-Datei holt `_remove_file` aus der Dokument-Datei; die Dokument-Datei holt `folded` aus `int_filemanager_text_page.py`.
- Rund 50 Zeilen reine Hilfsfunktionen ohne ORM hängen an den Modellen (`_probe`, `_image_info`, `_remove_path`, `_last_line`, `_is_scan_text`, `_remove_file`, `_files_in`). Das Modul hat dafür schon `tools/`.
- Sechs Stellen starten Programme mit `subprocess` (`_draw_first_page`, `_preview_run`, `_probe`, `_image_info`, `_run_reader`, `_ocr_run`). `nice -n … timeout --kill-after=…` steht fast wortgleich in `_preview_run` und `_ocr_run`.

## 5. Vorschlag

Jede Stufe ist ein eigener Commit, der nur verschiebt und kein Verhalten ändert (Regel „kleiner Diff, bei großem Umbau erst ein reiner Verschiebe-Commit“).

### Stufe 1: aufräumen (klein, sicher)

- Hilfsfunktionen nach `tools/` (zum Beispiel `tools/subprocess_run.py`, `tools/blob_files.py`).
- Doppelte Konstanten zusammenführen.
- Den Aufruf `nice … timeout` in einer gemeinsamen Funktion bündeln.
- Imports in den Tests anpassen, die diese Namen einführen: `_image_info`, `READER`, `ENGINE_VERSION`, `SETTINGS`, `OCR_PROGRESS`, `BLOB_LOCK_NAME`, `THUMBNAIL_CRON_XMLID`, `ZIP_MAX_SIZE_PARAMETER`.

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
