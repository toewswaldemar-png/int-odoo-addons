# int_filemanager: Volltextsuche und OCR (Entwurf, Stand 2026-10-13)

Status: **Entwurf, nichts gebaut.** Maßgeblich für Code bleibt der Code; dieses Dokument hält Zielbild, Entscheidungen und Belege fest.
Das Modul soll auf jedem Odoo-19-Betrieb laufen (Threaded oder Prefork, mit oder ohne Docker). Messungen auf dem Live-Server (HM-SRV) dienen
nur als Beleg für Verhalten, nicht als Designgrundlage; Werte der Odoo-Konfiguration werden zur Laufzeit gelesen.

Grundlagen: Odoo-19-Quelltext (Klon `GitHub\odoo`, Commit `8d05257`, 10.08.2026), Regeln in `docs/odoo_regeln/`, Messungen im Live-Container
(Odoo 19.0-20260908, Postgres 17.11, `ocrmypdf` 17.12.1, Tesseract 5.3.4), Paperless-ngx v3.3.1 (Quelltext gelesen, GPL-3.0: nur Ideen, kein Code).

## 1. Ziel

Dokumente des Filemanagers (Ordner und Dokumente, Blobs im eigenen Speicher) sollen nach ihrem **Inhalt** durchsuchbar sein:
Text aus PDFs (mit Textebene und gescannt), Office-Dateien, Textdateien und Bildern. Treffer sollen Seite und Textauszug zeigen und im PDF-Viewer
markiert werden. Die Rechte pro Ordner gelten unverändert auch für die Suche.

## 2. Entscheidungen

| Thema | Entscheidung |
|---|---|
| Stufen | Stufe A: Volltextsuche ohne OCR. Stufe B: OCR. |
| Extraktion Office/Text | `attachment_indexation` (Core-Modul) als Abhängigkeit, `ir.attachment._index`. Nebenwirkung akzeptiert: alle künftigen Anhänge der Instanz werden mitindexiert. |
| Extraktion PDF | Alle PDFs seitenweise mit `pdfminer` über den Cron-Weg (Seitenzahlen, gemischte PDFs), nicht über `_index` des Cores. *Annahme, bei „ja“ zum Paperless-Vergleich gesetzt.* |
| Größengrenze im Odoo-Prozess | 50 MB, größere Dateien wartet der Cron-Weg ab. |
| Suche | Postgres-Volltext (`to_tsvector('german', …)`, GIN), Umlautfaltung ä/ö/ü/ß → ae/oe/ue/ss. |
| Viewer | Treffermarkierung per pdf.js `#page=N&search=…`, als eigener Schritt nach der Suche. |
| Treffer-Ansicht | Mit Textauszug und Seite, eigener Schritt nach Stufe A. |
| OCR-Umfang | PDFs und Bilder. Bilder nur in Ordnern mit Schalter „Texterkennung für Bilder“ (erbt vom Elternordner); PDFs immer. |
| OCR-PDF | Dauerhaft als abgeleiteter Blob (nur für Scans). Original unverändert. Viewer zeigt das OCR-PDF, Download liefert das Original. |
| Ausführung | Kein eigener Container, nichts mit Docker. **Der Odoo-Cron (`ir.cron`) arbeitet selbst**; nur `ocrmypdf` läuft als Kindprozess. |
| Große Scans | Abschnittsweise OCR (`--pages`), Standard. *Annahme.* |
| Ausgabetyp | `pdf` als Standard, `pdfa` als Einstellung (Archivzwecke). *Annahme.* |
| Last | Einstellungen in Odoo (siehe 5). |

## 3. Zielbild Stufe A (Volltextsuche)

- **Modell `int.filemanager.text`** je Prüfsumme des Blobs (nicht je Dokument; doppelte Dateien teilen sich eine Zeile): `checksum` (eindeutig, Regex wie
  beim Dokument), `state` (`pending`, `done`, `empty`, `skipped`, `failed`), `message`, Seitenzahl, Engine-Version, OCR-Zustand (Abschnitt 4).
- **Modell `int.filemanager.text.page`**: `text_id`, `page`, `content` (Text). Office und Textdateien bekommen eine Zeile (Seite 1).
  Textobergrenze je Zeile **500.000 Zeichen**, darüber wird gekürzt und `message` vermerkt (siehe 9, `tsvector`-Grenze).
- **Index**: `models.Index("USING gin (to_tsvector('german', <Faltung>(content)))")`. Die Faltung (`replace`/`lower`-Kette, alles `immutable`) steht an
  genau einer Stelle und wird in Index und Suche gleich benutzt.
- **Suchfeld `content_search`** am Dokument: berechnet, nicht gespeichert, mit `search='_search_content_search'`. Die Methode liefert
  `[('checksum', 'in', SQL(…))]` (Unterabfrage mit `websearch_to_tsquery('german', <Faltung>(%s))`) und bei anderen Operatoren `NotImplemented`.
  Die Suche läuft über die Dokumente, deshalb gelten die Ordnerregeln (`ir.rule`) unverändert.
- **Rechte**: keine ACL für Nutzer auf den Textmodellen (kein Zugriff), Lesen nur für „Filemanager Administrator“. Textauszüge entstehen erst für
  sichtbare Treffer.
- **Suchansicht**: `<field name="content_search" string="Content">` neben dem Namen; kombiniert sich mit Suchpanel und Tags.
- **Textdateien** werden selbst dekodiert (UTF-8, dann Latin-1): der Basis-`_index` liefert nur ASCII-Folgen ab 4 Zeichen und zerhackt Umlaute.

## 4. Zielbild Stufe B (OCR im Odoo-Cron)

Ein `ir.cron` (Methode `_cron_ocr`, hohe `priority`-Zahl, damit er im Durchlauf zuletzt kommt). Jeder Aufruf verarbeitet einen Stapel.

1. **Einstieg:** aktiv? Zeitfenster offen? Werkzeuge vorhanden? Zeitbudget aus der Odoo-Konfiguration: `limit_time_real_cron`; `-1` heißt
   `limit_time_real` (Standard 120 s), `0` heißt kein Limit (dann eigener Deckel). Davon die Zeitreserve und die schon laufende Zeit des Durchlaufs
   abziehen (`threading.current_thread().start_time`, intern; fehlt es, eigener Zähler). Sonst `_commit_progress(0, remaining=0)`.
2. **Aufräumen:** `running`-Zeilen sind zu Beginn eines Aufrufs veraltet (der Core lässt von einem Cron nie zwei Läufe gleichzeitig zu) und gehen
   auf `pending` zurück (Zähler +1). Jobordner früherer Läufe werden gelöscht.
3. **Holen:** bis zu N Dateien mit `try_lock_for_update`, deren geschätzte Dauer ins Restbudget passt.
4. **Prüfen** (im Cron-Prozess, `pdfminer`): Seitenzahl und Text je Seite. „Hat Text“ gilt bei getaggtem PDF oder mehr als 50 Zeichen. Hat jede Seite
   Text: keine OCR, nur Text und Seiten speichern. Verschlüsselte oder signierte PDFs: vorhandenen Text nehmen.
5. **OCR in Abschnitten:** `ocrmypdf --skip-text --pages a-b` als Kindprozess auf dem Ergebnis des Vorlaufs. Erster Abschnitt klein, misst die Zeit
   je Seite; Abschnittsgröße = Restbudget / gemessene Zeit je Seite. Überschreitet ein Abschnitt die Frist: Prozessbaum beenden (`SIGTERM`, nach 5 s
   `SIGKILL`, mit `psutil`), Abschnitt halbieren, wiederholen. Zwischenergebnis liegt im Modulspeicher (nicht in `/tmp`).
6. **Start des Kindprozesses** nur mit Standardbibliothek: ein Inline-Start (`sys.executable -c …`) hebt `RLIMIT_AS` und `RLIMIT_CPU` auf den Hard-Wert,
   setzt `os.nice` und ersetzt sich per `execvp` durch `ocrmypdf`. Umgebung: `OMP_THREAD_LIMIT=1`, `TMPDIR` = Jobordner. Keine GNU-Präfixprogramme.
   Auf Systemen ohne `resource` (Windows) startet er ohne diesen Schritt.
7. **Bilder:** DPI aus Metadaten, sonst Einstellung, sonst Schätzung `Breite / (21/2.54)` (A4), Warnung unter 70 dpi; Alphakanal entfernen.
8. **Fertig:** Text je Seite aus dem endgültigen PDF lesen (nicht aus der Sidecar-Datei, siehe 9). Bei OCR das PDF als abgeleiteten Blob über
   `_store_stream` und `_publish_blob` ablegen, Seiten und Status schreiben, `_commit_progress(n, remaining=…)`, Jobordner löschen.

**Fehlerzuordnung** (Exit-Codes des installierten `ocrmypdf`, `ExitCode`; gemessen sind 0, 2, 6):

| Ergebnis | Reaktion |
|---|---|
| 0 | fertig |
| 2 (kaputte Datei) | endgültig `failed` |
| 2 mit „DpiError“ | mit DPI-Schätzung wiederholen |
| 2 „Input“, 6, oder leeres Ergebnis | einmal `force_ocr` versuchen |
| 8 verschlüsselt | endgültig `failed`; vorhandenen Text nehmen, falls es einen gibt |
| 7, 4, 10 | bis zur Einstellung „Wiederholungen“ erneut |
| 3 fehlende Abhängigkeit, 9 Konfiguration | OCR stoppt, Meldung in den Einstellungen |
| Frist trotz kleinstem Abschnitt | `failed: zu langsam` |
| Platte voll | pausieren |

**Warum nicht anders:** Läuft eine Cron-Pass länger als das Odoo-Limit, lädt der Threaded-Server neu (`server.py:735-755`) oder der Prefork-Watchdog
beendet den Worker (`server.py:1018-1027`). Dieselbe Datei käme wieder dran; nach 3 Zeitüberschreitungen führt der Core den Cron nicht mehr aus
(`CONSECUTIVE_TIMEOUT_FOR_FAILURE`). Deshalb eigene Frist und Abschnitte statt „ganze Datei und hoffen“.

## 5. Einstellungen (Odoo-Einstellungen, nur Systemadministratoren)

| Gruppe | Einstellung | Standard |
|---|---|---|
| Betrieb | OCR aktiv | aus |
| | Zeitfenster (Start- und Endstunde, Zeitzone, am Wochenende ganztägig) | leer = immer |
| | Parallele Jobs | 1 |
| | Kerne je Job (`-j`) | 1 |
| | CPU-Priorität (`nice`) | 19 |
| | Zeitreserve unter dem Odoo-Limit | 15 s |
| | Wiederholungen je Datei | 3 |
| OCR | Sprachen | `deu+eng` |
| | Ausgabetyp | `pdf` (Alternative `pdfa`) |
| | Seitenlimit der OCR (0 = alle) | 0 |
| | Bild-DPI, falls unbekannt (0 = schätzen) | 0 |
| | Maximale Bildpixel | `ocrmypdf`-Standard |
| | Ausrichten, Drehen, Bereinigen | an, an, aus |
| Extraktion | Größengrenze im Odoo-Prozess | 50 MB |
| | Textobergrenze je Zeile | 500.000 Zeichen |

Am Ordner: Schalter „Texterkennung für Bilder“. Die Einstellungen zeigen einen Status: effektives Zeitlimit aus der Konfiguration; ob `ocrmypdf`,
`tesseract`, `unpaper` gefunden wurden (Version, Sprachpakete); Zahl wartender, fehlgeschlagener und „zu langsamer“ Dateien; letzter Lauf.
`external_dependencies` im Manifest bleibt leer: fehlende Programme werden zur Laufzeit gemeldet und blockieren nicht die Installation.

## 6. Belege: Odoo-Core

| Aussage | Fundstelle |
|---|---|
| `ir.attachment.index_content`, `_index` (Basis: nur `text/*`, ASCII ab 4 Zeichen) | `ir_attachment.py:434-441, 478` |
| Extraktoren docx/pptx/xlsx/odt/pdf (`pdfminer`, ohne OCR) | `attachment_indexation/models/ir_attachment.py` |
| Muster `search=` mit `[('id', 'in', SQL(…))]` | `mail_thread.py:247`, `hr_applicant.py:412`; `domains.py:96, 1073` |
| `models.Index` nimmt Definition oder Funktion der Registry | `orm/table_objects.py:125` |
| Cron ruft die Methode ≥ 10-mal und ≥ 10 s lang; Teilfortschritt plant sofort neu | `ir_cron.py:481-495`, `_reschedule_asap` 660 |
| `timed_out_counter`, 3 Zeitüberschreitungen | `ir_cron.py:803-821, 35, ~430` |
| `thread.start_time` je Durchlauf über alle fälligen Crons; Limit löst Neustart aus | `server.py:~600, 508-531, 735-755` |
| Prefork-Worker: `RLIMIT_CPU` = bisherige CPU + `limit_time_cpu` (60 s), `RLIMIT_AS` = `limit_memory_hard` (2560 MiB), von Kindprozessen geerbt | `server.py:78, 1294-1304`; `config.py:474, 484` |
| Defaults: `limit_time_real` 120, `limit_time_real_cron` -1 (= `limit_time_real`), `max_cron_threads` 2 | `config.py:443, 487-493` |
| Watchdog beendet Prefork-Cron-Worker per `SIGKILL` | `server.py:1018-1027` |
| pdf.js 4.8.69: `#search=…&phrase=true`, `#page=N`; Core baut `viewer.html?file=…#pagemode=none` | `viewer.js:1109`; `file_model.js:33` |
| `set_param` signalisiert Cache-Änderung | `ir_config_parameter.py:107` |
| Der Core nutzt `tsvector` nirgends | Suche in `odoo/` und `addons/` ohne Treffer |

## 7. Belege: Messungen (Live-Container, nur als Verhalten)

| Messung | Ergebnis |
|---|---|
| Sidecar bei gemischtem PDF (Seite 1 Text, Seite 2 Scan, `--skip-text`) | Seite 1: nur der Platzhalter `[OCR skipped on page(s) 1]`; Seitentrenner `\f` |
| Text aus dem fertigen PDF mit `pdfminer` je Seite | beide Seiten korrekt, 0,01 s |
| Rein digitales PDF mit `--skip-text` | Exit 0, trotzdem eine Kopie als Ausgabe; ohne `--skip-text` Exit 6 |
| Kaputte Datei | Exit 2 (`UnsupportedImageFormatError`) |
| Bild ohne DPI | Exit 2 (`DpiError`); mit `--image-dpi` Exit 0 |
| PDF, PNG, JPEG, TIFF ohne Dateiendung | alle Exit 0 |
| 100 Scanseiten (300 dpi, einfacher Text), `-j 1` | 106 s, größter Einzelprozess 146 MB, Ausgabe +2 % |
| `pdfminer` je Seite, 300 dichte Textseiten | 15,3 s, 36 MB |
| Abschnitts-OCR 40 Seiten (`--pages 1-10`, dann `11-20` auf dem Ergebnis) | alle 40 Seiten bleiben, Text auf 1–20; je 10 Seiten 12,4 s und 11,9 s |
| Abbruch nach 4 s | Baum `ocrmypdf` + `tesseract`; `SIGTERM` beendete einen, `SIGKILL` den anderen; Rest: Ordner `ocrmypdf.io.*` im `TMPDIR`; keine Ausgabedatei |
| Vererbte Grenzen (Emulation Prefork: AS 2,5 GiB, CPU 60 s) | Inline-Start setzt AS und CPU auf unbegrenzt, `nice` 19 |
| Speicherlimit bei 600-dpi-A4-Seite | kein Unterschied mit und ohne Limit (Problem nicht reproduziert; Anhebung bleibt Vorsicht) |
| Postgres: `tsvector`-Grenze | Fehler ab 1.048.575 Bytes (60.000 verschiedene Wörter ≈ 2,2 MB) |
| Postgres: `german` ohne Faltung | `Müller` → `mull`, `Mueller` → `muell` (verschieden); mit Faltung beide `muell`, `Straße`/`Strasse` → `strass` |
| `replace`, `translate`, `lower`, `to_tsvector(config, text)` | `immutable`, damit indexierbar; `websearch_to_tsquery` verträgt kaputte Eingaben |

## 8. Paperless-ngx im Vergleich

Gleich: Sidecar-Platzhalter (Text dann aus dem PDF, `extract_text` in `parsers/tesseract.py`), Original unverändert mit getrenntem Archiv-PDF nur für Scans
(`ARCHIVE_FILE_GENERATION=auto`), ein Prozess pro Dokument (`CELERY_WORKER_MAX_TASKS_PER_CHILD = 1`), Text im Dokument plus Suchindex, `skip_text`.

Anders: Celery-Worker mit Redis statt Cron; Zeitlimit 1800 s (`PAPERLESS_WORKER_TIMEOUT`), bei Überschreitung Fehlschlag ohne Abschnitte; Suche mit
Tantivy-Index (Snowball-Stemmer, `ascii_fold` ü→u), Rechte in den Index kopiert; Standardausgabe PDF/A.
Wir machen bewusst anders: Rechte zur Abfragezeit über Odoo-Regeln, Faltung ü→ue, Postgres-Volltext, Abschnitts-OCR.

Übernommen: `OMP_THREAD_LIMIT=1` im OCR-Kind; DPI-Reihenfolge und -Schätzung; Fallback `force_ocr`; Regel „getaggt oder > 50 Zeichen“; Ausgabetyp als
Einstellung; Seitenlimit, Bildpixel, Ausrichten, Drehen, Bereinigen.

## 9. Stolpersteine

- Sidecar-Datei nicht indexieren (Platzhalter für Textseiten); Text immer aus dem fertigen PDF je Seite lesen.
- `tsvector` bricht ab 1 MB: der Fehler träte schon beim `INSERT` auf; deshalb Obergrenze je Zeile und Seitenmodell.
- Aufräumer `_gc_blobs` kennt abgeleitete Blobs nicht (Docstring warnt): Prüfsummen der OCR-PDFs als „benutzt“ ergänzen.
- `_publish_blob` setzt gleiches Dateisystem voraus (`os.replace`): OCR-PDFs über `_store_stream` ablegen.
- Odoo-Prefork vererbt `RLIMIT_CPU` und `RLIMIT_AS` an Kindprozesse; ohne Anhebung bräche eine lange OCR ab.
- Core-`_index` für PDF trennt keine Seiten und erkennt keine gemischten PDFs; für Textdateien liefert die Basis nur ASCII.
- Der Cron belegt einen von standardmäßig zwei Cron-Threads (`max_cron_threads`).
- Zombies: nach einem Servercrash bleiben verwaiste OCR-Prozesse bis zum Containerende; Frist und Jobordner-Aufräumen begrenzen den Schaden.
- `attachment_indexation` schaltet die Indexierung für alle Anhänge der Instanz ein.

## 10. Änderungen am Bestand (Realitätscheck)

- Neu: Textmodelle, Index, Suchfeld, Cron, Einstellungen, Status, Ordner-Schalter, Treffer-Ansicht, Viewer-Anbindung.
- Zu ändern: `_gc_blobs` (benutzte Prüfsummen), `DocumentFile.defaultSource` (PDF-Adresse mit `#page=…&search=…`, Quelle: OCR-PDF oder Original).
- Manifest: `depends` um `attachment_indexation` erweitern; Aufteilung der Datei `int_filemanager_text.py` nach Coding Guidelines (Datei je Modell).
- Das Live-Image `int-filemanager-odoo:19.0-ocr` hat `ocrmypdf`, Tesseract (`deu`, `eng`, `osd`), Ghostscript, qpdf, `img2pdf`; es fehlen `unpaper`,
  `pngquant`, `jbig2`, `pdftotext`. Das Test-Image `odoo:19.0-hm-test` ist nicht geprüft; Tests, die `ocrmypdf` brauchen, überspringen sich ohne das Programm.

## 11. Tests

`TransactionCase`, jede Testdatei in `tests/__init__.py`: Extraktion je Typ mit kleinen Fixtures; `Müller`/`Mueller`; Treffer nur in sichtbaren Ordnern;
doppelte Datei teilt eine Textzeile; Kürzung bei Überlänge; Größengrenze → `skipped`; Cron-Aufräumen (`running` → `pending`); Zeitbudget (-1, 0, Zahl);
Abschnittsplanung und Halbierung (mit simuliertem Kindprozess); Fehlerzuordnung je Exit-Code; Jobordner wird gelöscht; Einstellungen wirken ohne Neustart.
Tests mit echtem `ocrmypdf` nur, wenn das Programm vorhanden ist.

## 12. Offen / ungemessen

- Overhead der Abschnitte bei sehr großen Dateien (jeder Abschnitt schreibt das PDF neu).
- OCR-Durchsatz und Qualität auf echten Scans; Platzbedarf von Texten, Index und OCR-PDFs.
- Verhalten unter Last auf einem geteilten Host.
- Ob `threading.current_thread().start_time` in allen Betriebsarten gesetzt ist (Prefork: eigener Zähler nötig).
- `OMP_THREAD_LIMIT=1` und dessen Wirkung auf Durchsatz nicht selbst gemessen (aus Paperless übernommen).
- Bestand für spätere Läufe: mindestens 79.411 PDFs (Zählung brach nach 100 s ab = Untergrenze).

## 13. Reihenfolge

1. Stufe A: Textmodelle, Index, Suchfeld, Rechte, Cron (Extraktion Office/Text und PDF-Text), Tests.
2. Viewer-Anbindung (vorher JS-Regeln `js_framework`, `js_fields` lesen), Treffer-Ansicht.
3. Messung an einer Stichprobe (~50 PDFs) in einer Wegwerf-Umgebung.
4. Stufe B: OCR-Cron mit Abschnitten, Einstellungen, Status, Ordner-Schalter.
