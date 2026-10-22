# int_filemanager: Volltextsuche und Texterkennung (OCR)

Kurzfassung dessen, was gebaut ist und warum. Maßgeblich bleibt der Code; Belege zum Odoo-Kern stehen unten. Das Modul läuft auf jedem
Odoo-19-Betrieb (Threaded oder Prefork, mit oder ohne Docker); Werte der Odoo-Konfiguration werden zur Laufzeit gelesen.

## 1. Ziel

Dokumente des Filemanagers (Ordner, Dokumente, Blobs im eigenen Speicher) sind nach ihrem **Inhalt** durchsuchbar: PDFs (mit Textebene und gescannt),
Office-Dateien, Textdateien und Bilder. Treffer zeigen Seite und Textauszug und werden im PDF-Viewer markiert. Die Rechte der Ordner gelten unverändert
auch für die Suche. Die Dateien selbst werden nie verändert.

## 2. Überblick

Ein geplanter Odoo-Cron (`_cron_ocr` an `int.filemanager.text`) macht alles, in dieser Reihenfolge: Zeilen für neue Dateien anlegen, Text lesen, Scans
zählen und einreihen, Texterkennung. Nur die Programme laufen als Kindprozesse (Textleser, `ocrmypdf`, Bildinfo); es gibt keinen eigenen Container und
keinen Dienst. Alles geschieht in Schritten, die einzeln committet werden, und in einem Zeitbudget, das aus der Odoo-Konfiguration folgt.

- **Stufe A (Suche):** Text je Seite lesen, speichern, mit Postgres-Volltext (deutsch, Umlautfaltung) durchsuchen, Treffer anzeigen.
- **Stufe B (OCR):** PDF-Seiten ohne Text (Scans) und Bilder erkennen; der erkannte Text kommt in dieselben Seitenzeilen.

## 3. Daten

- **`int.filemanager.text`:** eine Zeile je Prüfsumme des Blobs (doppelte Dateien teilen sich eine Zeile). Lese-Zustand `state`: `pending`, `running`, `done`,
  `empty`, `skipped`, `failed`; dazu Seitenzahl, `next_page` (Wiederaufnahme), Versuche, `engine_version` (wer das Lesen ändert, erhöht sie: dann wird neu
  gelesen), `memory_limit_mib`. Erkennung getrennt davon: `ocr_state` (`wait`, `running`, `done`, `skipped`, `failed`), `ocr_next_page`, `ocr_file` und
  `ocr_file_size` (letzte ganze Zwischendatei), Versuche, Sekunden je Seite, `ocr_found_pages`, `ocr_checksum`/`ocr_size` des erkannten PDFs,
  `scan_pages` (Scanseiten, -1 = noch nicht gezählt).
- **`int.filemanager.text.page`:** `text_id`, `page`, `content`, `scan` (Bild auf der Seite und kaum Text; Teilindex nur über diese Zeilen). PDFs: eine Zeile je Seite. Office- und Textdateien: Blöcke von höchstens 64 KB als
  Pseudo-Seiten. Obergrenze je Zeile in Bytes (650.000), darüber wird gekürzt und vermerkt (`tsvector` bricht bei 1 MB, schon beim `INSERT`).
- **Rechte:** keine ACL für Nutzer auf den Textmodellen, Lesen nur für Filemanager-Administratoren. Gesucht wird über die Dokumente, deshalb gelten die
  Ordnerregeln; eine gleiche Prüfsumme in einem unsichtbaren Ordner verrät nichts, weil der Inhalt byte-gleich ist. Das Ordnerfeld
  „Texterkennung für Bilder“ (Erben/An/Aus, oberster Ordner ohne Wahl = aus) ist nur für Administratoren les- und schreibbar (`groups` am Feld).
- **Zeilenanlage:** für nicht archivierte Dokumente eines festen Typs (PDF, docx/xlsx/pptx/odt, `text/*`; Bilder nur bei „OCR aktiv“ und Ordnerschalter) ohne
  Zeile. Andere Typen bekommen keine Zeile, sonst blieben sie für immer „ohne Zeile“.

## 4. Lesen (Stufe A)

- **Kindprozess `tools/extract_text.py`** mit Zeitgrenze und Speicherbudget, nicht im Odoo-Prozess: die Rechenzeit hängt an der Seite, nicht an der
  Dateigröße (eine Seite kann Minuten brauchen), und im Odoo-Prozess würde sie im Threaded-Betrieb die Webanfragen verlangsamen und im Prefork den Worker
  töten (`limit_time_cpu`). Je Seite `pdfminer` mit `TextConverter` (wie `attachment_indexation`; `extract_pages` liefert den unsichtbaren OCR-Text nicht).
  Der Prozess meldet jede fertige Seite; bei Fristablauf wird er beendet, die fertigen Seiten bleiben, das Lesen geht bei der nächsten Seite weiter.
- **Office/Text** werden selbst dekodiert (`zipfile`/`lxml`, UTF-8 dann Latin-1), nicht über `attachment_indexation`: dessen Indexierung läuft synchron im
  Request jedes Anhangs der Instanz, ohne Größengrenze.
- **Fehler:** kaputt/verschlüsselt → `failed` mit Meldung; zu wenig Speicher → `skipped` (wird bei höherem Budget neu versucht); Abstürze zählen als Versuch,
  nach `max_attempts` ist die Datei `failed`. „Neu lesen“ (Administrator) wirft den Text weg und liest erneut.
- **Neu lesen liest das beste vorhandene Ergebnis:** die letzte ganze Zwischendatei einer laufenden Erkennung, sonst das erkannte PDF, sonst das Original.
  Sonst ginge der erkannte Text verloren und die Scans würden noch einmal erkannt.

## 5. Suche und Treffer

- **Index:** GIN auf `to_tsvector('german', <Faltung>(content))`. Die Faltung (Umlaute → ae/oe/ue/ss, Großbuchstaben ausdrücklich gemappt, nur
  `replace`/`lower`) steht an einer einzigen Stelle und ist unabhängig von der Datenbank-Locale (bei `LC_CTYPE C` würde `lower` ein `Ü` stehen lassen).
  `Müller` findet `Mueller` und umgekehrt, `Rechnung` findet `Rechnungen`; `Haus` findet `Häuser` nicht (Faltung vor Stamm). Nach einem Major-Upgrade von
  Postgres den Index neu aufbauen (andere Wortstämme).
- **Suchfeld `content_search`** am Dokument (eigenes Label, `websearch`-Syntax), Operatoren `ilike`, `=`, `in`; `work_mem` wird nur für diese Suche
  gesetzt (häufige Wörter brauchen sonst Minuten: Trefferliste „lossy“), ohne parallele Arbeiter.
- **Treffer-Spalte:** `content_hits` liefert je Datei bis zu drei Seiten mit Textauszug (Wörter aus dem Seitentext, mit Umlauten und Schreibweise der
  Datei), ein Klick öffnet den Viewer auf der Seite und markiert die Wörter (ganze Wörter, zentriert). Bei Bildern ohne Seitenlabel.
- **Viewer:** PDFs mit erkanntem PDF zeigen dieses (Route `ocr_content`, gleiche Zugriffsprüfung wie `content`, ETag = Prüfsumme des erkannten PDFs);
  der Download der Zeile liefert das Original.

## 6. Zeitbudget des Crons

Der Cron arbeitet in Schritten und meldet nach jedem Schritt Fortschritt; ist die Zeit um und Arbeit übrig, meldet er `remaining > 0`, Odoo ruft ihn sofort
wieder auf.

- **Frist** = Odoo-Limit für Cron-Läufe minus Reserve (Einstellung, 15 s) minus bereits verbrauchte Zeit. Threaded: `limit_time_real_cron` (0 und -1 heißen
  `limit_time_real`); die verbrauchte Zeit zählt ab `thread.start_time`. Prefork: der Watchdog zählt ab dem letzten Herzschlag des Workers, vor dem 60 bis 69 s
  langen Schlaf, deshalb werden 70 s abgezogen; die verbrauchte Zeit zählt ab dem Jobstart (`cron_end_time − MIN_TIME_PER_JOB`), jeder Wiederholaufruf im
  selben Durchlauf bekommt dieselbe Frist.
- **Ein Job darf nie Fortschritt melden und trotzdem die Frist reißen** (Neustart jede Minute, Endlosschleife). Darum gibt es eine eigene Frist statt der
  Rückgabe von `_commit_progress` (die zählt nur bis Jobstart + 10 s).
- Die Zeit der OCR-Abschnitte wird so geplant, dass für das Lesen der neuen Seiten noch Zeit bleibt; das Zählen der offenen Arbeit startet keine Programme.
- Ein langes `limit_time_real_cron` (einige hundert Sekunden) gibt der Erkennung mehr Arbeit je Lauf.

## 7. Texterkennung (Stufe B)

**Wann:** „OCR aktiv“ an, Zeile gelesen und `scan_pages > 0`. Eine Seite zählt als Scan, wenn sie ein Bild oder eine Form in ihren Ressourcen hat
(`XObject`, vom Reader gemeldet) und weniger als 20 Zeichen ohne Leerraum Text; das Ergebnis steht beim Lesen als `scan` in der Seitenzeile. Leere
Trennblätter ohne Bild zählen nicht. Grenze: ein Bild, das als Inline-Bild im Inhaltsstrom steht (kein `XObject`), wird nicht erkannt. Gemischte Seiten
(digitaler Text plus eingescanntes Bild) bleiben unberührt (`--skip-text`). Messung (14.10., 500 zufällige PDFs = 480 Zeilen, 4 Kerne, `-j2`, alter und neuer
Code nacheinander): Warteschlange 75 Dateien mit 9.007 Seiten, jetzt 52 Dateien mit 1.583 Seiten; Erkennungszeit 3.767 s, jetzt 3.164 s (−16 %). Die
Zeit an Dateien, die nichts fanden, sank von 587 s auf 95 s; der Rest ist echte Erkennung (rund 1.450 Seiten mit neuem Text, 2,1 s je Seite) und bleibt.
Text danach gleich bis auf eine Seite (1.452 gegen 1.451 Seiten mit neuem Text): sie hatte kein `XObject`, die Erkennung fand dort Text.

**Ablauf je Schritt (ein Abschnitt):**
1. Zeile auf `running`, Commit (ein Absturz wird beim nächsten Lauf als Versuch gezählt).
2. Die Abschnittsseiten sind die nächsten Scanseiten ab `ocr_next_page` (Zeilen mit `scan`, bei Bildern die Seiten des Bildes). `subprocess.run`
   startet `nice -n <Differenz> timeout --kill-after=5 <Sekunden> ocrmypdf --skip-text --pages 3,7,12-14` (nur diese Seiten, die übrigen übernimmt `ocrmypdf` unverändert) im Jobordner `<Filestore>/int_filemanager/.ocr/<Zeilen-ID>/`: absolute Priorität (`nice`, soweit die
   eigene Priorität es zulässt), `OMP_THREAD_LIMIT=1` und `TMPDIR` im Jobordner über `env=`; die Speichergrenze des Workers gilt für das Programm wie bei
   `wkhtmltopdf` im Core. Ausgabe `upto-<letzte Seite>.pdf.tmp`, `fsync`, atomar umbenannt. Nur Linux (`nice`, `timeout`).
3. Frist gerissen: `timeout` beendet die ganze Prozessgruppe (`SIGTERM`, nach 5 s `SIGKILL`), die Zeit je Seite verdoppelt sich (der nächste Abschnitt wird
   kleiner). Ein Versuch gegen die Datei zählt nur, wenn eine einzelne Seite eine faire Zeit hatte (60 s, in kurzen Läufen 80 % des Fensters, das der Lauf dem Programm gibt: Budget minus 10 s Lesezeit) und trotzdem nicht fertig wurde. Ist
   die Zeit je Seite so groß geworden, dass keine Seite mehr passt, wird trotzdem eine einzelne Seite versucht, wenn die Restzeit fair ist (sonst käme
   die Datei nie mehr dran).
4. Erfolg: der Text genau der Abschnittsseiten wird aus der neuen Datei gelesen (der Reader bekommt die Seitenliste) und ersetzt die Seitenzeilen, im selben Commit wie `ocr_next_page` (letzte Abschnittsseite + 1), `ocr_file`
   und `ocr_file_size`. Die alte Zwischendatei wird erst nach dem Commit gelöscht (`postcommit`, ganz am Ende des Schritts). Neue Treffer sind sofort suchbar.
5. Letzter Abschnitt (keine Scanseite mehr ab `ocr_next_page`): das erkannte PDF geht durch `_store_stream` und `_publish_blob` in den Speicher und wird nur behalten, wenn die Erkennung mindestens
   einer Seite Text gab (sonst wäre es eine zweite Kopie für nichts). Der Jobordner wird gelöscht, `state` neu bestimmt (`empty` → `done`).
   Dateisystemfehler im Schritt laufen in einem Savepoint und werden der Zeile zugeordnet (Platte voll → Pause, sonst ein Versuch).

**Größe des Abschnitts (Seitenzahl):** `(Restzeit − 6 s) × 0,7 / Sekunden je Seite`, mindestens 1, höchstens 100, ohne Messung höchstens 10 Seiten bei angenommenen 5 s je
Seite; die Zeit je Seite wird nach jedem Abschnitt geglättet (Hälfte alt, Hälfte neu, ohne den festen Aufwand von 6 s).

**Wiederaufnahme nach Absturz:** Zeile zeigt immer auf die letzte ganze Zwischendatei. Fehlt sie oder hat sie eine andere Größe, beginnt die Erkennung bei
Seite 1 mit dem Original und verbraucht keinen Versuch (die Scanseiten werden aus den Seitenzeilen neu bestimmt). Ein Abschnitt zweimal mit `--skip-text` ändert das Ergebnis nicht. Zeilen, die beim Start eines Laufs
noch `running` sind, gehen auf `wait` zurück (+1 Versuch).

**Fehlerzuordnung** (`tools/ocr_plan.py`, `classify`, reine Funktion; Exit-Codes von `ocrmypdf`):

| Ergebnis | Reaktion |
|---|---|
| 0 | fertig; 0 ohne Ausgabedatei: einmal mit `--force-ocr` |
| 2, Text „resolution (DPI)“ | Bild: einmal mit geschätzter DPI (Breite / A4-Breite), unter 70 dpi mit Warnung |
| 2, Usage-Text von `ocrmypdf` | falsche Einstellung/Option: OCR hält an (nicht die Schuld der Datei) |
| 2 sonst | Datei kaputt/falsch: `failed` |
| 6 | Seite hat Text: einmal `--force-ocr`, dann `failed` |
| 8 | Passwort zum Öffnen: `failed` |
| 3, 127 (Programm fehlt), 1, 9 | OCR hält an, Meldung in den Einstellungen |
| 7 „Image too large“ | einmal mit `--tesseract-downsample-large-images`, dann `failed` |
| 7, 4, 5, 10, 15, Signal | erneut bis `max_attempts`, dann `failed` |
| „No space left“ | Pause; die Datei wartet unverändert |

„Hält an“ und „Pause“ sperren das Starten für eine Stunde (Systemparameter `int_filemanager.ocr_blocked`); die Datei bleibt `wait`. Beim Aufgeben bleibt
der bis dahin erkannte Text stehen, das Original wird nie angefasst.

**Bilder:** JPEG, PNG, TIFF, BMP, GIF, WebP. Die Zeile entsteht schon als `empty`/`wait` (die Erkennung ist das Lesen), es bleibt kein PDF. Seitenzahl und
Breite liefert das Kindprogramm `tools/image_info.py`: der Odoo-Prozess kennt nur PNG/JPEG/GIF/BMP (`odoo/tools/image.py` lädt keine weiteren Plug-ins von
Pillow). Mehrseitige TIFF laufen in Abschnitten: der erste liest das TIFF (die Ausgabe behält alle Seiten), die folgenden das Zwischen-PDF. „Neu lesen“
eines Bildes startet die Erkennung neu.

**Aufräumen:** `_gc_blobs` zählt die erkannten PDFs der Zeilen als benutzt und sperrt Dokument- und Texttabelle in fester Reihenfolge (sonst wäre ein frisch
veröffentlichtes PDF bis zum Commit „unbenutzt“); die Zeile markiert ihr PDF, wenn sie es ersetzt oder gelöscht wird. `_gc_texts` löscht Zeilen ohne Dokument
(auch archivierte zählen). `_gc_ocr_jobs` räumt Jobordner von Zeilen, die weg oder fertig sind (laufende nicht, nichts Jüngeres als 10 Minuten).
„Erkennung wiederholen“ (Administrator) wirft die Erkennung weg und beginnt mit dem Original.

## 8. Einstellungen und Status

Systemparameter `int_filemanager.*`, auf der Einstellungsseite (Block „Text in scans“) nur für Systemadministratoren:

| Parameter | Standard |
|---|---|
| `time_reserve` (s unter dem Odoo-Limit) | 15 |
| `memory_mib` (Lesen einer Datei) | 1024 |
| `text_block_kib`, `text_cut_bytes` | 64, 650000 |
| `work_mem_mib` (nur Suche) | 128 |
| `max_attempts` | 3 |
| `ocr_enabled` | aus |
| `ocr_languages` | `deu+eng` |
| `ocr_jobs` (Kerne je Erkennung) | 1 |
| `ocr_nice` (19 niedrigste, 0 normal; als Auswahl) | 19 |
| `ocr_deskew` (Ausrichten und Drehen; als Auswahl „1“/„0“) | 1 |
| `ocr_output_type` (`pdf`, `pdfa`) | `pdf` |

Zahlenfelder speichern in den Odoo-Einstellungen keine 0, Häkchen kein „aus“ bei Standard „an“: deshalb Auswahlfelder. Die Programme (`ocrmypdf`, `tesseract`,
Sprachen) werden zur Laufzeit gesucht und fünf Minuten gemerkt; `external_dependencies` im Manifest bleibt leer. Der Status zeigt Zustand mit Grund,
Programme mit Version und Sprachen, Zahlen je Zustand, offene Seiten mit grober Restdauer, Gesamtgröße der erkannten PDFs und Hinweise (Zeichensatz `C`
der Datenbank, `limit_time_real_cron`). Die Liste „Texte der Dateien“ (Administratoren) hat Spalten, Filter und Knöpfe „Erneut lesen“ und „Erneut erkennen“.

## 9. Messwerte (zur Einordnung, hängen von Hardware und Bestand ab)

- **Lesen:** normal 0,03 bis 0,11 s je Seite; Ausreißer einzelne Seiten bis 91 s. 250-MB-PDF mit 60 Seiten 6 s.
- **Erkennung:** Scans etwa 7,5 CPU-s je Seite, mit vier Kernen rund 17 Seiten/min. Abschnitte kosten: 5 Seiten +139 %, 25 Seiten +21 %, 100 Seiten +3 bis
  +19 %; fester Aufwand je Aufruf etwa 5,5 s. Eine 54-MB-Datei am Stück braucht 945 MB RAM, in Abschnitten zu 100 Seiten 392 MB.
- **Qualität:** gegen die Textebene als Bild gerenderter Seiten 99 % der Wörter bei 300 dpi (97 % bei 150 dpi); echte Buchscans 98 bis 100 %, Handyscans von
  Formularen 77 bis 91 %.
- **Platz:** Text 1,9 bis 2,2 KB je Seite, GIN etwa 450 Byte; das erkannte PDF eines Scans ist eine volle zweite Kopie (etwa 0,84-fach).
- **Index und Suche (3 Mio. Seiten):** Aufbau 13 bis 28 min, Einfügen mit Index etwa 180 Seiten/s; seltenes Wort 0,2 s, häufiges Wort (616.000 Seiten) 5 s mit
  `work_mem` ab 32 MB und ohne parallele Arbeiter ab 1 s, mit 4 MB über 280 s. Die Rechteprüfung kostet nichts Messbares.
- **Bestand (Stichprobe):** reine Scans 3 % der Seiten, gemischte Seiten 0,3 % (meist Titelseiten), keine signierten PDFs, verschlüsselte nur mit
  Besitzerpasswort.
- **Webzugriff:** CPU-Last im Odoo-Prozess verlangsamt im Threaded-Betrieb die Seiten (10 → 45 ms), ein Kindprozess nicht.

## 10. Stolpersteine

- Der Core hält Prefork-Worker per Watchdog an (`SIGKILL`) und lädt im Threaded-Betrieb den Server neu, wenn ein Lauf das Limit reißt; nach drei Läufen ohne
  Fortschritt führt er den Cron nicht mehr aus. Darum eigene Frist und Abschnitte.
- `RLIMIT_AS` setzt Odoo in beiden Betriebsarten und der Kindprozess erbt es. Eine einzelne Seite von mehr als etwa 450 Megapixel scheitert dann still in Tesseract (Meldung „found no text“); Abhilfe wie bei `wkhtmltopdf`: `limit_memory_hard` erhöhen; `RLIMIT_CPU` erbt er zwar, `SIGXCPU` ist aber im
  Cron-Thread blockiert.
- `nice` ist relativ; der Prefork-Cron-Worker startet mit 10: die Einstellung wird absolut gesetzt.
- `Zombies`: Enkelprozesse (Tesseract, Ghostscript) übernimmt der erste Prozess des Containers; reapt er nicht, bleiben sie als Zombies. Container mit `--init`.
- `tsvector` bricht bei 1 MB; ein Fehler im `INSERT` bricht den ganzen Stapel: der Seitenzeilen-`INSERT` läuft im Savepoint, zu lange Seiten werden gekürzt.
- Zwei gleichzeitige Veröffentlichungen derselben Prüfsumme: Advisory-Lock auf den Hash, der Blob wird nie ersetzt (ein Ersetzen über einen vorhandenen Namen lässt
  Leser auf Netzwerkfreigaben kurz ENOENT sehen).
- `pdfminer` ist keine Odoo-Requirement (das offizielle Image bringt es mit).
- Dateinamen und Aufruf von `ocrmypdf`: nur Listenargumente, keine Shell; die Sprachen werden gegen ein festes Muster geprüft.
- Der Exit-Code 2 von `ocrmypdf` heißt auch „falsche Option“, und dessen Hilfetext nennt `--image-dpi`: die Zuordnung darf nicht am Wort allein hängen.

## 11. Belege im Odoo-Kern (Datei, Funktion)

| Aussage | Fundstelle |
|---|---|
| Cron ruft die Methode mindestens zehnmal und zehn Sekunden lang; Teilfortschritt plant sofort neu; `remaining=0` heißt fertig | `ir_cron.py`: `_run_job`, `_reschedule_asap` |
| `_commit_progress` liefert die Sekunden bis Jobstart + `MIN_TIME_PER_JOB` | `ir_cron.py`: `_commit_progress` |
| Drei Zeitüberschreitungen ohne Fortschritt: Lauf entfällt | `ir_cron.py`: `CONSECUTIVE_TIMEOUT_FOR_FAILURE` |
| Prefork-Watchdog, Schlaf `SLEEP_INTERVAL + PID % 10`, `RLIMIT_AS`/`RLIMIT_CPU` | `service/server.py`: `PreforkServer`, `Worker`, `WorkerCron` |
| `0` heißt „kein Limit“ nur im Prefork | `service/server.py`, `tools/config.py` |
| Pillow lädt nur Basisformate | `tools/image.py`: `Image.preinit()`, `Image._initialized = 2` |
| Binäres Feld ausliefern über `ir.binary._record_to_stream` (Haken), Zugriffsprüfung über das Dokument | `ir_binary.py` |
| Suchmethode mit `Domain.custom(to_sql=…)`, `NotImplemented` für unbekannte Operatoren | `orm/domains.py`, `orm/fields.py` |
| Einstellungen: Zahl 0 und `False` werden nicht gespeichert | `res_config.py`: `set_values` |
| `models.Index`/`Constraint` als Attribute | `orm/table_objects.py` |
| Dateisystem-Aufräumen mit Checkliste und Tabellensperre | `ir_attachment.py`: `_gc_file_store_unsafe` |

## 12. Abgrenzung und Offenes

- **Nicht gemacht:** `attachment_indexation` als Abhängigkeit (synchron, ohne Grenze); Wortpositionen in der Datenbank (stehen in der Textebene des
  erkannten PDFs); OCR für gemischte Seiten (`--redo-ocr` ist mit Ausrichten nicht kombinierbar, im Bestand sehr selten); ein eigener Dienst oder Container.
- **Paperless-ngx als Vergleich:** gleich sind Original unverändert plus Archiv-PDF nur für Scans, ein Prozess je Dokument, `skip_text`, Sidecar nicht
  indexieren. Anders: Cron statt Celery/Redis, Rechte zur Abfragezeit über Odoo-Regeln, Postgres-Volltext statt Tantivy, Abschnitts-OCR mit eigener Frist.
- **Ungemessen:** Gesamtlauf am ganzen Bestand (4.967 PDFs; die Stichprobe mal etwa 10 gerechnet: rund 2,4 h Lesen und 8,8 h Erkennen), Anteil der Trennblätter, Windows im Betrieb, Postgres 17, eine echte gemischte Seite für
  `--redo-ocr`, die gespeicherte `tsvector`-Spalte in voller Größe.
