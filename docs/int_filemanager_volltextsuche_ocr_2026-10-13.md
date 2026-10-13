# int_filemanager: Volltextsuche und OCR (Entwurf, Stand 2026-10-13)

Status: **Entwurf, nichts gebaut.** Maßgeblich für Code bleibt der Code; dieses Dokument hält Zielbild, Entscheidungen und Belege fest.
Das Modul soll auf jedem Odoo-19-Betrieb laufen (Threaded oder Prefork, mit oder ohne Docker). Messungen auf dem Live-Server (HM-SRV) dienen
nur als Beleg für Verhalten, nicht als Designgrundlage; Werte der Odoo-Konfiguration werden zur Laufzeit gelesen.

Grundlagen: Odoo-19-Quelltext (Klon `GitHub\odoo`, Commit `8d05257`, 10.08.2026), Regeln in `docs/odoo_regeln/`, Messungen im Live-Container
(Odoo 19.0-20260908, Postgres 17.11, `ocrmypdf` 17.12.1, Tesseract 5.3.4), Paperless-ngx v3.3.1 (Quelltext gelesen, GPL-3.0: nur Ideen, kein Code).

Stand der Prüfung (2026-10-13): Das Konzept wurde gegen den Odoo-19-Quelltext (frischer Klon, Commit `0f577f1`; `8d05257` war im Shallow-Klon nicht abrufbar, die
Zeilen stimmen bis auf ±3) und in einer Wegwerf-Umgebung (Odoo 19, Postgres 16.15, `ocrmypdf` 17.13.0, Tesseract 5.3.4) geprüft. Die Korrekturen daraus sind eingearbeitet
(Abschnitte 3, 4, 6, 7a, 9, 10, 11); die Produktentscheidungen vom selben Tag stehen in Abschnitt 12.

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
| Größengrenze im Odoo-Prozess | 50 MB (Einstellung). Eine größere Datei bekommt `skipped` und eine `message`; wer die Grenze anhebt, stellt die Zeile wieder auf `pending`. |
| Suche | Postgres-Volltext (`to_tsvector('german', …)`, GIN), Umlautfaltung ä/ö/ü/ß → ae/oe/ue/ss. |
| Viewer | Treffermarkierung per pdf.js `#page=N&search=…`, als eigener Schritt nach der Suche. Übergeben werden die Wortformen, die im Dokument tatsächlich stehen (aus dem Textauszug der Treffer-Seite, z. B. `ts_headline`), nicht die eingetippte Suche. |
| Treffer-Ansicht | Mit Textauszug und Seite, eigener Schritt nach Stufe A. |
| OCR-Umfang | PDFs und Bilder. Bilder nur in Ordnern mit Schalter „Texterkennung für Bilder“ (erbt vom Elternordner); PDFs immer. Der Schalter löst nur die OCR aus: ist der Text da, sind alle Dokumente mit dieser Prüfsumme darüber auffindbar, auch in Ordnern ohne Schalter (gleicher Inhalt, kein Rechteproblem). |
| OCR-PDF | Dauerhaft als abgeleiteter Blob (nur für Scans). Original unverändert. Viewer zeigt das OCR-PDF, Download liefert das Original. |
| Ausführung | Kein eigener Container, nichts mit Docker. **Der Odoo-Cron (`ir.cron`) arbeitet selbst**; nur `ocrmypdf` läuft als Kindprozess. |
| Große Scans | Abschnittsweise OCR (`--pages`), Standard. *Annahme.* |
| Ausgabetyp | `pdf` als Standard, `pdfa` als Einstellung (Archivzwecke). *Annahme.* |
| Last | Einstellungen in Odoo (siehe 5). |

## 3. Zielbild Stufe A (Volltextsuche)

- **Anlage und Zustände der Textzeilen:** Der Cron legt Zeilen für Dokumente ohne Textzeile an (Bestand und Neues, kein Eingriff in den Upload; ein Index
  auf der Prüfsumme der Zeilen genügt für die Suche „Dokumente ohne Zeile“). Archivierte Dokumente werden nicht verarbeitet. Fehlt der Blob, wird die Zeile
  `failed` (`message`). Neu verarbeitet wird bei geänderter Engine-Version; `empty` wird wieder `pending`, wenn die OCR eingeschaltet wird; `skipped` (Größengrenze)
  wird `pending`, wenn die Grenze angehoben wird. Der Fortschritt der Abschnitts-OCR steht als Feld an der Zeile (nächste Seite) und wird nicht aus „Seiten ohne
  Text“ abgeleitet, weil leere Trennblätter auch nach der OCR ohne Text bleiben.
- **Modell `int.filemanager.text`** je Prüfsumme des Blobs (nicht je Dokument; doppelte Dateien teilen sich eine Zeile): `checksum` (eindeutig, Regex wie
  beim Dokument), `state` (`pending`, `done`, `empty`, `skipped`, `failed`), `message`, Seitenzahl, Engine-Version, OCR-Zustand (Abschnitt 4).
- **Modell `int.filemanager.text.page`**: `text_id`, `page`, `content` (Text). Office und Textdateien bekommen eine Zeile (Seite 1).
  Textobergrenze je Zeile **in Bytes** (Richtwert 650.000 Bytes UTF-8, Zeichen × 1,5 < 1.048.575; nicht gemessen, siehe 7a), darüber wird gekürzt und `message`
  vermerkt (siehe 9, `tsvector`-Grenze). Eine Grenze in Zeichen schützt nicht (7a). `content` mit `prefetch=False` (Core-Muster `index_content`);
  `_log_access = False` ist bei Millionen Zeilen eine Option (Core: `ir_model.py:1448`).
- **Index**: `models.Index("USING gin (to_tsvector('german', <Faltung>(content)))")`. Die Faltung (`replace`/`lower`-Kette, alles `immutable`) steht an
  genau einer Stelle und wird in Index und Suche gleich benutzt. **Die Faltung muss unabhängig von der Datenbank-Locale sein:** `lower()` und die
  Konfiguration `german` hängen an `LC_CTYPE`; in einer Datenbank mit `LC_CTYPE C` bleibt `Ü` groß und wird nicht gefaltet (7a). Deshalb Großbuchstaben
  ausdrücklich mappen (`Ä`/`Ö`/`Ü` vor `lower`). Ändert sich die Faltung später, baut das Modul-Update den ganzen GIN-Index neu auf (kein `CONCURRENTLY`).
- **Suchfeld `content_search`** am Dokument: berechnet, nicht gespeichert, mit `search='_search_content_search'`. Die Methode liefert eine Domain mit der
  Unterabfrage `checksum IN (SELECT … websearch_to_tsquery('german', <Faltung>(%s)))` und bei nicht unterstützten Operatoren `NotImplemented`. Angenommen
  werden `ilike` (Vorgabe der Suchansicht bei Char) und `=`; `not ilike` löst der ORM über die Negation. Bevorzugt `Domain.custom(to_sql=…)` (Muster des Cores,
  z. B. `analytic_mixin.py:112`); `[('checksum', 'in', SQL(…))]` läuft in 19 ebenfalls ohne Warnung (geprüft).
  Die Suche läuft über die Dokumente, deshalb gelten die Ordnerregeln (`ir.rule`) unverändert; eine gleiche Prüfsumme in einem unsichtbaren Ordner verrät
  nichts, weil der Inhalt byte-gleich ist (geprüft, 7a).
- **Rechte**: keine ACL für Nutzer auf den Textmodellen (kein Zugriff), Lesen nur für „Filemanager Administrator“. Textauszüge entstehen erst für
  sichtbare Treffer; die öffentliche Methode dafür ruft `check_access('read')` selbst auf (Sicherheits-Destillat, öffentliche Methoden).
- **Aufräumen**: Textzeilen und abgeleitete OCR-PDFs ohne Dokument (auch archivierte, `active_test=False`) löscht ein `@api.autovacuum`; die Blobs gehen über
  die Checkliste (siehe 9).
- **Suchansicht**: `<field name="content_search" string="Content">` neben dem Namen; kombiniert sich mit Suchpanel und Tags.
- **Textdateien** werden selbst dekodiert (UTF-8, dann Latin-1): der Basis-`_index` liefert nur ASCII-Folgen ab 4 Zeichen und zerhackt Umlaute.

## 4. Zielbild Stufe B (OCR im Odoo-Cron)

Ein `ir.cron` (Methode `_cron_ocr`, hohe `priority`-Zahl, damit er im Durchlauf zuletzt kommt) macht beides: erst Zeilen anlegen und Text extrahieren
(Stufe A, Abschnitt 3), dann, wenn die OCR aktiv ist, die OCR. Beide teilen sich ein Zeitbudget. Jeder Aufruf verarbeitet einen Stapel. Ist die OCR aus, läuft nur
die Extraktion.

1. **Einstieg:** aktiv? Zeitfenster offen? Werkzeuge vorhanden? Sonst `_commit_progress(0, remaining=0)` (der Cron ruht bis zum nächsten Intervall).
   **Zeitbudget** nach Betriebsart (geprüft, 7a):
   - Prefork: `limit_time_real_cron` `-1` heißt `limit_time_real` (Standard 120 s), `0` kein Limit (dann eigener Deckel), `n > 0` heißt `n`.
   - Threaded: `n > 0` heißt `n`; **`0` und `-1` heißen beide `limit_time_real`** (`0` ist hier nicht „kein Limit“, der Hilfetext der Option gilt nur für Prefork).
   Davon die Zeitreserve und die schon laufende Zeit abziehen: Threaded `threading.current_thread().start_time` (je Datenbank-Durchlauf gesetzt); **im Prefork
   fehlt das Attribut**, dort zählt ein Eigenzähler ab Aufruf (er kennt die Zeit zuvor gelaufener Crons desselben Durchlaufs nicht, die Reserve deckt das ab).
   **Prefork hat zusätzlich ein CPU-Budget:** `limit_time_cpu` (60 s) je Durchlauf gilt für den Odoo-Prozess selbst, also auch für `pdfminer` und `_index_*`; wird
   es überschritten, beendet sich der Cron-Worker. Die Arbeit im Prozess wird deshalb auch nach CPU-Zeit (`time.process_time()`) begrenzt, wo `resource` vorhanden ist.
   **Reicht das Budget nicht mehr, während Zeilen warten** (Core ruft die Methode nach einem langen Aufruf bis zu 10-mal erneut), liefert der Aufruf
   `_commit_progress(0, remaining=<Zahl der wartenden Zeilen>)`: dann gilt der Cron als „teilweise erledigt“ und kommt sofort wieder an die Reihe. `remaining=0`
   würde ihn als „fertig“ werten (`ir_cron.py` `_run_job`, `match`), er ruhte bis zum nächsten Intervall.
2. **Aufräumen:** `running`-Zeilen sind zu Beginn eines Aufrufs veraltet (der Core lässt von einem Cron nie zwei Läufe gleichzeitig zu) und gehen
   auf `pending` zurück (Zähler +1). Jobordner früherer Läufe werden gelöscht.
3. **Holen:** bis zu N Dateien mit `try_lock_for_update`, deren geschätzte Dauer ins Restbudget passt.
4. **Prüfen** (im Cron-Prozess, `pdfminer`): Seitenzahl und Text je Seite. „Hat Text“ gilt bei getaggtem PDF oder mehr als 50 Zeichen. Hat jede Seite
   Text: keine OCR, nur Text und Seiten speichern. Verschlüsselte oder signierte PDFs: vorhandenen Text nehmen.
5. **OCR in Abschnitten:** `ocrmypdf --skip-text --pages a-b` als Kindprozess auf dem Ergebnis des Vorlaufs. Erster Abschnitt klein, misst die Zeit
   je Seite; Abschnittsgröße = Restbudget / gemessene Zeit je Seite. Überschreitet ein Abschnitt die Frist: Prozessbaum beenden (`SIGTERM`, nach 5 s
   `SIGKILL`, mit `psutil`), Abschnitt halbieren, wiederholen. Zwischenergebnis liegt im Modulspeicher (nicht in `/tmp`).
6. **Start des Kindprozesses** nur mit Standardbibliothek: ein Inline-Start (`sys.executable -c …`) hebt `RLIMIT_AS` auf den Hard-Wert (Odoo setzt es in **beiden**
   Betriebsarten und der Kindprozess erbt es), setzt `os.nice` und ersetzt sich per `execvp` durch `ocrmypdf`. `RLIMIT_CPU` braucht keine Anhebung: im Prefork
   ist `SIGXCPU` im Cron-Thread blockiert und die Signalmaske erbt der Kindprozess (das CPU-Limit tötet ihn nicht, geprüft), im Threaded-Betrieb gibt es keines.
   `nice` ist relativ (`os.nice(n)`), der Prefork-Cron-Worker startet schon mit 10: die Einstellung als absoluten Wert setzen (`os.nice(wert - os.nice(0))`).
   Umgebung: `OMP_THREAD_LIMIT=1`, `TMPDIR` = Jobordner (Windows: `TEMP`/`TMP`). Keine GNU-Präfixprogramme. Auf Systemen ohne `resource` (Windows) startet er ohne diesen Schritt.
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

**Warum nicht anders:** Läuft eine Cron-Pass länger als das Odoo-Limit, lädt der Threaded-Server neu (`server.py:735-755`; die Prüfung läuft nur alle 60 s, gemessen
wurden 65 s bis zur Meldung) oder der Prefork-Watchdog beendet den Worker (`server.py:1018-1027`). Dieselbe Datei käme wieder dran; nach 3 Zeitüberschreitungen führt
der Core den Cron nicht mehr aus (`CONSECUTIVE_TIMEOUT_FOR_FAILURE`). Deshalb eigene Frist und Abschnitte statt „ganze Datei und hoffen“.

**Takt:** Bleibt der Cron „teilweise erledigt“, legt der Core den neuen Trigger ohne `NOTIFY` an (nur mit der Umgebungsvariablen `ODOO_NOTIFY_CRON_CHANGES`). Der
Cron-Thread oder -Worker schläft dann bis zu 60 s (`SLEEP_INTERVAL`) bis zum nächsten Durchlauf; der Durchsatz rechnet mit Arbeit plus dieser Pause.

## 5. Einstellungen (Odoo-Einstellungen, nur Systemadministratoren)

| Gruppe | Einstellung | Standard |
|---|---|---|
| Betrieb | OCR aktiv | aus |
| | Zeitfenster (Start- und Endstunde, Zeitzone, am Wochenende ganztägig) | leer = immer |
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
| Prefork-Worker: `RLIMIT_CPU` = bisherige CPU + `limit_time_cpu` (60 s) je Durchlauf; Überschreitung beendet den Worker (`signal_time_expired_handler`). `RLIMIT_AS` = `limit_memory_hard` (2560 MiB), auch im Threaded-Betrieb gesetzt (`server.py:645`) und vom Kindprozess geerbt. Das CPU-Limit erbt das Kind zwar, aber `SIGXCPU` ist im Cron-Thread blockiert (`Worker._runloop`) und die Maske wird mitvererbt | `server.py:78, 645, 1294-1304`; `config.py:474, 484` |
| Defaults: `limit_time_real` 120, `limit_time_real_cron` -1 (= `limit_time_real`), `max_cron_threads` 2. `0` heißt nur im Prefork „kein Limit“ (`server.py:899-901`); im Threaded-Betrieb gilt dann `limit_time_real` (`server.py:520-526`) | `config.py:443, 487-493` |
| `_commit_progress(processed=0, *, remaining=None, deactivate=False) -> float`: committet, liefert die Sekunden bis Jobstart + 10 s (`MIN_TIME_PER_JOB`), nicht bis zum Odoo-Limit; außerhalb eines Crons `inf` | `ir_cron.py:846-890`, `_run_job` |
| `remaining=0` wertet der Core als „fertig“ (`FULLY_DONE`), `remaining>0` ohne Fortschritt als „teilweise“; Reihenfolge der Crons `ORDER BY failure_count, priority, id`; `numbercall`/`doall` gibt es nicht mehr | `ir_cron.py` `_run_job`, `_get_all_ready_jobs`, Felder 93-110 |
| Der Core lässt von einem Cron nie zwei Läufe gleichzeitig zu: Zeilensperre `FOR NO KEY UPDATE SKIP LOCKED` auf `ir_cron`, gehalten über den ganzen Job, auch bei `method_direct_trigger` | `ir_cron.py:317-345`, `method_direct_trigger` |
| Watchdog beendet Prefork-Cron-Worker per `SIGKILL` | `server.py:1018-1027` |
| pdf.js 4.8.69: `#search=…&phrase=true`, `#page=N`; Core baut `viewer.html?file=…#pagemode=none` | `viewer.js:1109`; `file_model.js:33` |
| `create`, `write`, `unlink` des Parameters leeren den Cache `stable` (`set_param` selbst signalisiert nichts); der Cron prüft das Signal bei jedem Aufruf (`_callback`) | `ir_config_parameter.py:107, 115, 119`; `ir_cron.py` `_callback` |
| Der Core nutzt `tsvector` nirgends | Suche in `odoo/` und `addons/` ohne Treffer |
| Suchmethode: `NotImplemented` für nicht unterstützte Operatoren; der ORM versucht dann verwandte Operatoren | `fields.py:152-157` |
| `pdfminer` steht nicht in Odoos `requirements.txt` und nicht in den Debian-Paketen (nur `setup/package.dfwine`); `psutil` und `openpyxl` sind Requirements | `requirements.txt`, `server.py:23` |

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

## 7a. Belege: Prüfung vom 2026-10-13 (Wegwerf-Umgebung, Postgres 16.15, `ocrmypdf` 17.13.0)

| Messung | Ergebnis |
|---|---|
| Threaded, `limit_time_real=10`, `limit_time_real_cron=0`, Cron 100 s | `virtual real time limit (65/10s) reached`, „Initiating server reload“: `0` ist hier nicht „kein Limit“; die Prüfung läuft nur alle 60 s |
| `_commit_progress` im Cron | Rückgabe zählt von 9,0 s auf 0 (Jobstart + 10 s); die Methode lief 10-mal, dann „partially done (#loop 10 … duration 10.39s)" |
| Prefork: Cron-Methode | `start_time` fehlt (Thread „Worker WorkerCron … workthread“), `RLIMIT_CPU` (60, -1), `RLIMIT_AS` (2.684.354.560, -1), `nice` 10, Signalmaske `SIGINT/QUIT/USR1/USR2/XCPU` blockiert, vom Kindprozess geerbt |
| Prefork: Kindprozess mit CPU-Limit 4 s, 12 s CPU-Last | läuft durch (`SIGXCPU` blockiert), Exit 0 |
| Threaded: Cron-Methode | `start_time` gesetzt, `RLIMIT_CPU` (-1, -1), `RLIMIT_AS` 2.684.354.560 (auch vom Kindprozess geerbt), `nice` 0 |
| Prefork: 80 s CPU-Last im Cron-Prozess | nach 60 s: „Worker CPU time limit (60) reached … Exception occurred, exiting“, Worker neu gestartet |
| `tsvector`-Grenze: 494.999 kyrillische Zeichen (934.999 Bytes, 55.000 verschiedene Wörter) | `INSERT` mit Index scheitert: „string is too long for tsvector (1100000 bytes, max 1048575 bytes)“. Lateinisch: 469k Zeichen (80.000 Zahlen) und 480k Zeichen (80.000 Codes zu 5 Zeichen) gehen noch |
| Faltung in Datenbank mit `LC_CTYPE C` | `lower('ÜBER')` bleibt `ÜBER`; `Übung` wird Lexem `Übung`, nicht `uebung`. Mit `C.UTF-8` korrekt (`ueb`, `uebung`) |
| GIN-Index über `to_tsvector('german', <Faltung>(content))` per `models.Index("USING gin (…)")` | wird angelegt; Suche mit derselben Faltung nutzt den Bitmap-Index |
| Suchfeld: Nutzer ohne Zugriff auf den Ordner | findet das Dokument im gesperrten Ordner nicht; ein sichtbares Dokument mit gleicher Prüfsumme wird gefunden (Inhalt byte-gleich, kein Leck); archivierte Dokumente fallen heraus; `!=` und `like` ergeben `UserError` |
| `attachment_indexation` installiert: `ir.attachment.create` mit 300-Seiten-PDF (1 MB) | 20,2 s, 1.695.086 Zeichen `index_content`; 50 Seiten 3,0 s |
| dasselbe mit xlsx, 200.000 Zeilen (4,1 MB) | 5,5 s, 6.703.704 Zeichen, Speicherspitze 381 MB; läuft synchron im HTTP-Request |
| `ocrmypdf`-Stichprobe: Sidecar-Platzhalter, `--skip-text` (Exit 0), ohne (Exit 6), kaputte Datei (2), `DpiError`, ohne Dateiendung, Abschnitts-OCR 1-2 dann 3-4, Abbruch | wie in Abschnitt 7 beschrieben bestätigt (Abbruch: `ocrmypdf.io.*` bleibt im `TMPDIR`, keine Ausgabedatei) |

Nicht geprüft: `LC_CTYPE` der Live-Datenbank, Windows, das Verhalten von pdf.js bei geändertem Hash im Browser, GIN-Leistung bei Millionen Seiten, Postgres 17.

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
- `tsvector` bricht ab 1 MB (Bytes, nicht Zeichen): der Fehler tritt schon beim `INSERT` auf und bricht den ganzen Cron-Stapel ab. Deshalb Obergrenze in Bytes je
  Zeile, Seitenmodell und der `INSERT` je Zeile in einem Savepoint (Fehler → `failed` mit `message`).
- Aufräumer `_gc_blobs` kennt abgeleitete Blobs nicht (Docstring warnt): Prüfsummen der OCR-PDFs als „benutzt“ ergänzen **und die Texttabelle wie die
  Dokumenttabelle sperren** (`LOCK … IN SHARE MODE`, feste Reihenfolge). Sonst ist ein frisch veröffentlichtes OCR-PDF bis zum Commit der Textzeile für den
  Aufräumer unbenutzt (aus dem Code gelesen, nicht getestet).
- Textzeilen und OCR-PDFs haben keinen Fremdschlüssel zu den Dokumenten: ohne Aufräumer (Abschnitt 3) bleiben sie nach dem Löschen der Datei liegen.
- `_publish_blob` setzt gleiches Dateisystem voraus (`os.replace`): OCR-PDFs über `_store_stream` ablegen.
- Odoo setzt `RLIMIT_AS` in beiden Betriebsarten und der Kindprozess erbt es; das erbte CPU-Limit wirkt im Prefork nicht (`SIGXCPU` blockiert), dafür begrenzt
  `limit_time_cpu` den Odoo-Prozess selbst (Abschnitt 4 Schritt 1).
- Core-`_index` für PDF trennt keine Seiten und erkennt keine gemischten PDFs; für Textdateien liefert die Basis nur ASCII. Textdateien: Latin-1 dekodiert alles, bei
  Windows-Dateien ist cp1252 genauer; UTF-16 mit BOM wird nicht erkannt.
- Der Cron belegt einen von standardmäßig zwei Cron-Threads (`max_cron_threads`).
- Zombies: nach einem Servercrash bleiben verwaiste OCR-Prozesse bis zum Containerende; Frist und Jobordner-Aufräumen begrenzen den Schaden.
- `attachment_indexation` schaltet die Indexierung für alle Anhänge der Instanz ein, synchron im Request und ohne Größengrenze (7a: 300-Seiten-PDF 20 s, xlsx mit
  200.000 Zeilen 5,5 s und 381 MB). Zusätzlich liegen die Texte in `ir_attachment.index_content`.
- `pdfminer` ist keine Odoo-Requirement: das Image oder die Umgebung muss es mitbringen; `attachment_indexation` warnt nur im Log, wenn es fehlt.
- Die Markierung im Viewer ist wörtlich (`pdf.js` `search=`), die Suche nicht (Stemming, Faltung): `Mueller` findet `Müller`, markiert wird nichts.

## 10. Änderungen am Bestand (Realitätscheck)

- Neu: Textmodelle, Index, Suchfeld, Cron, Einstellungen, Status, Ordner-Schalter, Treffer-Ansicht, Viewer-Anbindung.
- Zu ändern: `_gc_blobs` (benutzte Prüfsummen und Sperre der Texttabelle), `DocumentFile.defaultSource` (PDF-Adresse mit `#page=…&search=…`, Quelle: OCR-PDF oder Original).
  **Serverseite der Auslieferung:** `/web/content/int.filemanager.document/<id>/content` liefert über `ir.binary._record_to_stream` und `_to_http_stream` heute
  nur das Original. Für das OCR-PDF braucht es eine Variante (Parameter oder zweites Binärfeld), die dieselbe Zugriffsprüfung über das Dokument macht und die
  Prüfsumme des OCR-PDFs als ETag nimmt; Download liefert weiter das Original.
- Neu zusätzlich: Aufräumer für Textzeilen und OCR-PDFs ohne Dokument (Abschnitt 3); Anlage der Textzeilen (Abschnitt 12, offen).
- Manifest: `depends` um `attachment_indexation` erweitern; Aufteilung der Datei `int_filemanager_text.py` nach Coding Guidelines (Datei je Modell).
- Das Live-Image `int-filemanager-odoo:19.0-ocr` hat `ocrmypdf`, Tesseract (`deu`, `eng`, `osd`), Ghostscript, qpdf, `img2pdf`; es fehlen `unpaper`,
  `pngquant`, `jbig2`, `pdftotext`. Das Test-Image `odoo:19.0-hm-test` ist nicht geprüft; Tests, die `ocrmypdf` brauchen, überspringen sich ohne das Programm.

## 11. Tests

`TransactionCase`, jede Testdatei in `tests/__init__.py`: Extraktion je Typ mit kleinen Fixtures; `Müller`/`Mueller`; Treffer nur in sichtbaren Ordnern;
doppelte Datei teilt eine Textzeile; Kürzung bei Überlänge; Größengrenze → `skipped`; Cron-Aufräumen (`running` → `pending`); Zeitbudget (-1, 0, Zahl);
Abschnittsplanung und Halbierung (mit simuliertem Kindprozess); Fehlerzuordnung je Exit-Code; Jobordner wird gelöscht; Einstellungen wirken ohne Neustart.
Tests mit echtem `ocrmypdf` nur, wenn das Programm vorhanden ist.

Dazu aus der Prüfung (2026-10-13):
- Sicherheit: gleiche Prüfsumme in einem Ordner, den der Nutzer nicht sieht (Treffer nur über die sichtbare Kopie); Zugriff auf die Methode des Textauszugs mit
  fremden IDs (`AccessError`); `not ilike`; archivierte Dokumente.
- `tsvector`: Text unter der Obergrenze in Zeichen, aber über 1 MB in Bytes (kyrillisch) wird gekürzt oder `failed`, der Stapel bricht nicht ab.
- Faltung: `Übung`/`uebung` auch in einer Datenbank mit `LC_CTYPE C` (Testdatenbank mit `LC_CTYPE C` anlegen).
- Cron: Budget erschöpft bei wartenden Zeilen → `_commit_progress(0, remaining=n)` (Status „teilweise“); `0` und `-1` für `limit_time_real_cron` je Betriebsart.
- Aufräumer: OCR-PDF einer Textzeile bleibt erhalten, solange die Zeile existiert; Textzeile und OCR-PDF verschwinden mit dem letzten Dokument.
- Archivieren und Wiederherstellen eines Dokuments; Zeile ohne Blob (Datei weg) → `failed`; Cron legt Zeilen für Dokumente ohne Zeile an (nicht für archivierte);
  `skipped` → `pending` nach Anheben der Grenze; Bilder-Schalter: Text einer Prüfsumme ist auch über das Dokument im Ordner ohne Schalter auffindbar; Markierungsterme
  kommen aus dem Textauszug, nicht aus der Eingabe.

## 12. Offen / ungemessen

- Overhead der Abschnitte bei sehr großen Dateien (jeder Abschnitt schreibt das PDF neu).
- OCR-Durchsatz und Qualität auf echten Scans; Platzbedarf von Texten, Index und OCR-PDFs.
- Verhalten unter Last auf einem geteilten Host.
- `OMP_THREAD_LIMIT=1` und dessen Wirkung auf Durchsatz nicht selbst gemessen (aus Paperless übernommen).
- Bestand für spätere Läufe: mindestens 79.411 PDFs (Zählung brach nach 100 s ab = Untergrenze).
- `LC_CTYPE` der Live-Datenbank; Windows; pdf.js im Browser bei geändertem Hash im bestehenden Frame; GIN-Index und Unterabfrage bei Millionen Seiten (Zeit des
  Neuaufbaus bei geänderter Faltung); Postgres 17 (geprüft wurde 16.15).
- Wie viel CPU-Zeit `pdfminer` für große Dateien im Odoo-Prozess braucht (gemessen: 300 dichte Seiten 15,3 s; 50-MB-Dateien nicht).

**Entschieden am 2026-10-13** (Produktentscheidungen aus der Prüfung):
1. **Datei über der Größengrenze:** `skipped` mit `message`; die Grenze ist eine Einstellung (Abschnitte 2, 5).
2. **Cron:** ein `ir.cron` `_cron_ocr` für Extraktion und OCR (Abschnitt 4).
3. **„Parallele Jobs“:** gestrichen; ein Kindprozess zugleich, mehr Durchsatz über „Kerne je Job“ (Abschnitt 5).
4. **Ordnerschalter für Bilder:** löst nur die OCR aus, die Suche folgt ihm nicht (Abschnitt 2).
5. **Markierung im Viewer:** Wortformen des Treffers aus dem Textauszug (Abschnitt 2).
6. **Textzeilen:** der Cron legt sie für Dokumente ohne Zeile an; Regeln für Neu-Verarbeitung, Archiv und fehlenden Blob in Abschnitt 3.
7. **`attachment_indexation`:** Nebenwirkung bleibt akzeptiert, die Messwerte stehen in Abschnitt 9 und 7a.

## 13. Reihenfolge

1. Stufe A: Textmodelle, Index, Suchfeld, Rechte, Cron (Extraktion Office/Text und PDF-Text), Aufräumer, Tests.
2. Viewer-Anbindung (vorher JS-Regeln `js_framework`, `js_fields` lesen), Treffer-Ansicht.
3. Messung an einer Stichprobe (~50 PDFs) in einer Wegwerf-Umgebung.
4. Stufe B: OCR-Cron mit Abschnitten, Einstellungen, Status, Ordner-Schalter.
