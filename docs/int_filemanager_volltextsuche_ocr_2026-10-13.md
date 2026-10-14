# int_filemanager: Volltextsuche und OCR (Entwurf, Stand 2026-10-13)

Status: **Entwurf, nichts gebaut.** Maßgeblich für Code bleibt der Code; dieses Dokument hält Zielbild, Entscheidungen und Belege fest.
Das Modul soll auf jedem Odoo-19-Betrieb laufen (Threaded oder Prefork, mit oder ohne Docker). Messungen auf dem Live-Server (HM-SRV) dienen
nur als Beleg für Verhalten, nicht als Designgrundlage; Werte der Odoo-Konfiguration werden zur Laufzeit gelesen.

Grundlagen: Odoo-19-Quelltext (Klon `GitHub\odoo`, Commit `8d05257`, 10.08.2026), Regeln in `docs/odoo_regeln/`, Messungen im Live-Container
(Odoo 19.0-20260908, Postgres 17.11, `ocrmypdf` 17.12.1, Tesseract 5.3.4), Paperless-ngx v3.3.1 (Quelltext gelesen, GPL-3.0: nur Ideen, kein Code).

Stand der Prüfung (2026-10-13): Das Konzept wurde gegen den Odoo-19-Quelltext (frischer Klon, Commit `0f577f1`; `8d05257` war im Shallow-Klon nicht abrufbar, die
Zeilen stimmen bis auf ±3) und in einer Wegwerf-Umgebung (Odoo 19, Postgres 16.15, `ocrmypdf` 17.13.0, Tesseract 5.3.4) geprüft. Die Korrekturen daraus sind eingearbeitet
(Abschnitte 3, 4, 6, 7a, 9, 10, 11); die Produktentscheidungen vom selben Tag stehen in Abschnitt 12.

Stand 2026-10-14: Messungen in einer Wegwerf-Umgebung (Abschnitt 7b: Cron-Limits in Threaded und Prefork, `pdfminer`, OCR-Durchsatz und Abschnitte, GIN-Index mit 3 Mio. Seiten
unter Postgres 16.15 und 18.1, `attachment_indexation`, Sicherheit der Suche) haben mehrere Annahmen widerlegt. Die Folgen sind eingearbeitet und mit „(14.10.)“ gekennzeichnet.
Drei Produktentscheidungen wurden dadurch neu getroffen (Abschnitt 12, „Entschieden am 2026-10-14“); sie ersetzen die Entscheidung 7 vom 13.10.

## 1. Ziel

Dokumente des Filemanagers (Ordner und Dokumente, Blobs im eigenen Speicher) sollen nach ihrem **Inhalt** durchsuchbar sein:
Text aus PDFs (mit Textebene und gescannt), Office-Dateien, Textdateien und Bildern. Treffer sollen Seite und Textauszug zeigen und im PDF-Viewer
markiert werden. Die Rechte pro Ordner gelten unverändert auch für die Suche.

## 2. Entscheidungen

| Thema | Entscheidung |
|---|---|
| Stufen | Stufe A: Volltextsuche ohne OCR. Stufe B: OCR. |
| Extraktion Office/Text | `attachment_indexation` (Core-Modul) als Abhängigkeit, `ir.attachment._index`. Nebenwirkung akzeptiert: alle künftigen Anhänge der Instanz werden mitindexiert. **(14.10.) Entschieden: nicht als Abhängigkeit.** Gemessen (7b): das Modul rechnet beim Anlegen *jedes* Anhangs synchron im Request, ein 6,9-MB-PDF mit komplexen Seiten 154 s (über `limit_time_real` 120 s). Stattdessen eigene schlanke Extraktion im Cron (docx/xlsx/pptx/odt über `zipfile`/`lxml`, Text selbst dekodiert). |
| Extraktion PDF | Alle PDFs seitenweise mit `pdfminer` über den Cron-Weg (Seitenzahlen, gemischte PDFs), nicht über `_index` des Cores. *Annahme, bei „ja“ zum Paperless-Vergleich gesetzt.* **(14.10.) `pdfminer` läuft in einem zeitbegrenzten Kindprozess, nicht im Odoo-Prozess:** die CPU-Zeit hängt an der Seite, nicht an der Dateigröße (6,9 MB, 28 Seiten: 149 s, eine Seite allein 91 s; 250 MB, 60 Seiten: 6,4 s). Je Seite `TextConverter` wie `attachment_indexation`, nicht `extract_pages` (das liefert den unsichtbaren OCR-Text nicht). |
| Budgets statt Größengrenze | **(14.10.)** Die Grenze „50 MB im Odoo-Prozess“ entfällt als Ausschluss. Stattdessen getrennte Budgets: Zeit je Kindprozess-Aufruf, Arbeitsspeicher (Odoo-Prozess: ganze Datei als `bytes`, etwa 2,2-fach; `ocrmypdf` am Stück: 54-MB-Datei 945 MB), Seitenzahl je Abschnitt, Textobergrenze je Zeile. Eine Datei über einem Budget bekommt `skipped` mit `message` (Grund: Zeit, Speicher oder Seiten); wer das Budget anhebt, stellt die Zeile auf `pending`. 54-MB-Scans werden verarbeitet. |
| Suche | Postgres-Volltext (`to_tsvector('german', …)`, GIN), Umlautfaltung ä/ö/ü/ß → ae/oe/ue/ss. |
| Viewer | Treffermarkierung per pdf.js `#page=N&search=…`, als eigener Schritt nach der Suche. Übergeben werden die Wortformen, die im Dokument tatsächlich stehen (aus dem Textauszug der Treffer-Seite, z. B. `ts_headline`), nicht die eingetippte Suche. |
| Treffer-Ansicht | Mit Textauszug und Seite, eigener Schritt nach Stufe A. |
| OCR-Umfang | PDFs und Bilder. Bilder nur in Ordnern mit Schalter „Texterkennung für Bilder“ (erbt vom Elternordner); PDFs immer. Der Schalter löst nur die OCR aus: ist der Text da, sind alle Dokumente mit dieser Prüfsumme darüber auffindbar, auch in Ordnern ohne Schalter (gleicher Inhalt, kein Rechteproblem). |
| OCR-PDF | Dauerhaft als abgeleiteter Blob (nur für Scans). Original unverändert. Viewer zeigt das OCR-PDF, Download liefert das Original. |
| Ausführung | Kein eigener Container, nichts mit Docker. **Der Odoo-Cron (`ir.cron`) arbeitet selbst**; nur `ocrmypdf` läuft als Kindprozess. |
| Große Scans | Abschnittsweise OCR (`--pages`), Standard. *Annahme.* **(14.10.)** Die Abschnittsgröße folgt aus Zeitbudget und gemessenem Durchsatz; bevorzugt 100 Seiten, keine starre Untergrenze. Der Durchsatz schwankt um den Faktor 10 (hochaufgelöste Einzelseiten etwa 10 CPU-s je Seite, Buchscans 1,5), 100 Seiten dauern also 40 s bis über 5 Minuten. Kleine Abschnitte kosten viel (5 Seiten: +139 %, 100 Seiten: +3 % bei 396 Seiten, +19 % bei 2.596 Seiten). |
| Ausgabetyp | `pdf` als Standard, `pdfa` als Einstellung (Archivzwecke). *Annahme.* |
| Last | Einstellungen in Odoo (siehe 5). |

## 3. Zielbild Stufe A (Volltextsuche)

- **Anlage und Zustände der Textzeilen:** Der Cron legt Zeilen für Dokumente ohne Textzeile an (Bestand und Neues, kein Eingriff in den Upload; ein Index
  auf der Prüfsumme der Zeilen genügt für die Suche „Dokumente ohne Zeile“). Archivierte Dokumente werden nicht verarbeitet. Fehlt der Blob, wird die Zeile
  `failed` (`message`). Neu verarbeitet wird bei geänderter Engine-Version; `empty` wird wieder `pending`, wenn die OCR eingeschaltet wird; `skipped` (Größengrenze)
  wird `pending`, wenn die Grenze angehoben wird. Der Fortschritt der Abschnitts-OCR steht als Feld an der Zeile (nächste Seite) und wird nicht aus „Seiten ohne
  Text“ abgeleitet, weil leere Trennblätter auch nach der OCR ohne Text bleiben.
- **Dateitypen (14.10.):** Der Cron legt Zeilen nur für Dokumente an, deren `mimetype` in einer festen Liste steht (PDF, docx/xlsx/pptx/odt, `text/*`, Bilder nach Ordnerschalter).
  Ohne Liste bliebe jede MP3 für immer ein „Dokument ohne Zeile“ (im Bestand der größte Teil der Dateien). Die Auswahl „ohne Zeile“ läuft über `mimetype` und die Prüfsumme (Anti-Join).
- **Modell `int.filemanager.text`** je Prüfsumme des Blobs (nicht je Dokument; doppelte Dateien teilen sich eine Zeile): `checksum` (eindeutig, Regex wie
  beim Dokument), `state` (`pending`, `done`, `empty`, `skipped`, `failed`), `message`, Seitenzahl, Engine-Version, OCR-Zustand (Abschnitt 4).
- **Modell `int.filemanager.text.page`**: `text_id`, `page`, `content` (Text). PDFs: eine Zeile je Seite. **(14.10.)** Office- und Textdateien werden in Blöcke von höchstens 64 KB zerlegt
  (Pseudo-Seiten 1, 2, …), statt auf eine Zeile mit Kürzung bei etwa 650.000 Bytes: so geht bei einer großen xlsx (13,5 Mio. Zeichen bei 100.000 Zeilen) nichts verloren.
  Textobergrenze je Zeile **in Bytes** (Richtwert 650.000 Bytes UTF-8, Zeichen × 1,5 < 1.048.575; nicht gemessen, siehe 7a), darüber wird gekürzt und `message`
  vermerkt (siehe 9, `tsvector`-Grenze). Eine Grenze in Zeichen schützt nicht (7a). `content` mit `prefetch=False` (Core-Muster `index_content`);
  `_log_access = False` ist bei Millionen Zeilen eine Option (Core: `ir_model.py:1448`).
- **Index**: `models.Index("USING gin (to_tsvector('german', <Faltung>(content)))")`. Die Faltung (`replace`/`lower`-Kette, alles `immutable`) steht an
  genau einer Stelle und wird in Index und Suche gleich benutzt. **Die Faltung muss unabhängig von der Datenbank-Locale sein:** `lower()` und die
  Konfiguration `german` hängen an `LC_CTYPE`; in einer Datenbank mit `LC_CTYPE C` bleibt `Ü` groß und wird nicht gefaltet (7a). Deshalb Großbuchstaben
  ausdrücklich mappen (`Ä`/`Ö`/`Ü` vor `lower`). Ändert sich die Faltung später, baut das Modul-Update den ganzen GIN-Index neu auf (kein `CONCURRENTLY`).
- **Suchfeld `content_search`** am Dokument: berechnet, nicht gespeichert, mit `search='_search_content_search'`. **(14.10.)** Eigenes `string` (nicht „Content“): das Binärfeld `content` des Dokuments
  heißt schon so, Odoo warnt sonst „Two fields … have the same label“ (gemessen).
  **`work_mem` (14.10.):** Bei einem häufigen Wort (616.000 von 3 Mio. Seiten) dauert die Unterabfrage mit dem Standard von 4 MB 281 s (Postgres 16) bzw. 360 s (18), mit 256 MB 5 s: die Trefferliste wird
  „lossy“, Postgres rechnet dann die Faltung für über eine Million Seiten nochmal. Die Suche setzt deshalb `SET LOCAL work_mem` nur für ihre Transaktion (nie global; Gesamtbedarf = Wert × Operationen ×
  parallele Arbeiter). Gemessen (Postgres 18, 3 Mio. Seiten, Wort mit 616.280 Treffern): 4 MB 360 s, 16 MB 115 s (44.000 Blöcke „lossy“), **32 MB 4,1 s** (alles exakt), 64/128/256 MB 3,4/3,5/3,6 s; ohne parallele Arbeiter
  (`SET LOCAL max_parallel_workers_per_gather = 0`) 2,2/1,1/1,1 s bei 64/128/256 MB. Die Schwelle liegt zwischen 16 und 32 MB für 616.000 Treffer, rund 40 Byte je Treffer; für die ganze Tabelle (3 Mio. Treffer)
  also etwa 120 MB. Ein Wort mit 59.470 Treffern braucht schon bei 4 MB keine Hilfe (0,9 s). Empfehlung: `work_mem` 128 MB und keine parallelen Arbeiter für diese Abfrage (das senkt auch den
  Gesamtbedarf: Wert × Operationen, ohne Mehrfaches durch Arbeiter); der Wert wächst mit der Seitenzahl und ist eine Einstellung. Alternative: gespeicherte `tsvector`-Spalte (nicht in voller Größe getestet). Die Methode liefert eine Domain mit der
  Unterabfrage `checksum IN (SELECT … websearch_to_tsquery('german', <Faltung>(%s)))` und bei nicht unterstützten Operatoren `NotImplemented`. Angenommen
  werden `ilike` (Vorgabe der Suchansicht bei Char) und `=`; `not ilike` löst der ORM über die Negation. Bevorzugt `Domain.custom(to_sql=…)` (Muster des Cores,
  z. B. `analytic_mixin.py:112`); `[('checksum', 'in', SQL(…))]` läuft in 19 ebenfalls ohne Warnung (geprüft).
  Die Suche läuft über die Dokumente, deshalb gelten die Ordnerregeln (`ir.rule`) unverändert; eine gleiche Prüfsumme in einem unsichtbaren Ordner verrät
  nichts, weil der Inhalt byte-gleich ist (geprüft, 7a).
- **Rechte**: keine ACL für Nutzer auf den Textmodellen (kein Zugriff), Lesen nur für „Filemanager Administrator“. Textauszüge entstehen erst für
  sichtbare Treffer; die öffentliche Methode dafür ruft `check_access('read')` selbst auf (Sicherheits-Destillat, öffentliche Methoden).
- **Aufräumen**: Textzeilen und abgeleitete OCR-PDFs ohne Dokument (auch archivierte, `active_test=False`) löscht ein `@api.autovacuum`; die Blobs gehen über
  die Checkliste (siehe 9). **(14.10.)** Gleiches gilt für Zwischendateien der Abschnitts-OCR (Abschnitt 4 Schritt 5) einer Zeile, die nicht mehr existiert oder nicht mehr `running` ist.
  Der Aufräumer arbeitet in Stapeln (Rückgabe `(erledigt, übrig)`). Die Zeit des Anti-Joins „Texte ohne Dokument“ und „Dokumente ohne Zeile“ bei 68.000 Texten und 477.000 Dokumenten ist **ungemessen**
  (das Messskript brach vor diesen Abfragen ab).
- **Suchansicht**: `<field name="content_search" string="Content">` neben dem Namen; kombiniert sich mit Suchpanel und Tags.
- **Textdateien** werden selbst dekodiert (UTF-8, dann Latin-1): der Basis-`_index` liefert nur ASCII-Folgen ab 4 Zeichen und zerhackt Umlaute.

## 4. Zielbild Stufe B (OCR im Odoo-Cron)

Ein `ir.cron` (Methode `_cron_ocr`, hohe `priority`-Zahl, damit er im Durchlauf zuletzt kommt) macht beides: erst Zeilen anlegen und Text extrahieren
(Stufe A, Abschnitt 3), dann, wenn die OCR aktiv ist, die OCR. Beide teilen sich ein Zeitbudget. Jeder Aufruf verarbeitet einen Stapel. Ist die OCR aus, läuft nur
die Extraktion.

1. **Einstieg:** aktiv? Zeitfenster offen? Werkzeuge vorhanden? Sonst `_commit_progress(0, remaining=0)` (der Cron ruht bis zum nächsten Intervall).
   **Zeitbudget** nach Betriebsart (geprüft, 7a):
   - Prefork: `limit_time_real_cron` `-1` heißt `limit_time_real` (Standard 120 s), `0` kein Limit (dann eigener Deckel), `n > 0` heißt `n`.
     **(14.10.) Aber das nutzbare Budget ist kleiner:** Der Watchdog zählt ab dem letzten Herzschlag des Workers (`server.py:1349-1358`, vor dem Schlaf), der Worker schläft dann
     `SLEEP_INTERVAL + PID % 10` = 60 bis 69 s (`server.py:1422-1435`), danach läuft erst der Job. Gemessen: Limit 100 s, Job gekillt nach 31 s (nicht 100 s). Budget = Limit − 69 s − Reserve;
     wird der Worker früher durch NOTIFY geweckt, bleibt mehr, das lässt sich nicht erkennen. Ein Limit unter etwa 90 s tötet auch untätige Cron-Worker (alle 24 s gemessen).
     Das Budget ist keine Konstante, sondern wird aus den Konfigurationswerten und dieser Rechnung abgeleitet.
   - Threaded: `n > 0` heißt `n`; **`0` und `-1` heißen beide `limit_time_real`** (`0` ist hier nicht „kein Limit“, der Hilfetext der Option gilt nur für Prefork).
   Davon die Zeitreserve und die schon laufende Zeit abziehen: Threaded `threading.current_thread().start_time` (je Datenbank-Durchlauf gesetzt); **im Prefork
   fehlt das Attribut**, dort zählt ein Eigenzähler (er kennt die Zeit zuvor gelaufener Crons desselben Durchlaufs nicht, die Reserve deckt das ab).
   **(14.10., gemessen) Der Eigenzähler läuft ab Jobstart, nicht ab Methodenaufruf:** Der Core ruft die Methode im selben Durchlauf bis zu 10-mal erneut auf (`ir_cron.py` `_run_job`); ein Zähler ab Aufruf
   beginnt dabei jedes Mal neu, der Job lief dann bis zum Kill weiter. Der Jobstart steht im Kontext: `cron_end_time − MIN_TIME_PER_JOB` (monotone Uhr, `ir_cron.py:481-485`). Ein erneuter Aufruf mit
   verbrauchtem Budget kehrt sofort zurück (`_commit_progress(0, remaining=n)`), er arbeitet und schläft nicht. Prefork-Budget = `limit − 70 s − Reserve − (jetzt − Jobstart)`: gemessen mit
   zwei Worker-Zuständen (25 s und 80 s untätig, per Trigger geweckt): jeweils der erste Pass endete nach 33 bis 34 s mit „partially done“, ohne Kill. Der zweite Pass (Start nach dem regulären Schlaf von
   69 s, Kill nach 31 s) wurde in der ersten Probe in der Wiederholschleife gekillt, weil sie dort pro Aufruf noch 1 s schlief. Mit sofortiger Rückkehr der Wiederholaufrufe (Nachmessung) endeten drei
   Pässe nacheinander (ein per Trigger, zwei nach dem regulären Schlaf) nach 24 bis 25 s mit „partially done“, ohne Kill.
   Der Kill kam immer genau `limit` nach dem letzten Herzschlag (`server.py:1349-1358`), egal ob der Job per Trigger oder Timer startete.
   **Prefork hat zusätzlich ein CPU-Budget:** `limit_time_cpu` (60 s) je Durchlauf gilt für den Odoo-Prozess selbst, also auch für `pdfminer` und `_index_*`; wird
   es überschritten, beendet sich der Cron-Worker. Die Arbeit im Prozess wird deshalb auch nach CPU-Zeit (`time.process_time()`) begrenzt, wo `resource` vorhanden ist.
   **Reicht das Budget nicht mehr, während Zeilen warten** (Core ruft die Methode nach einem langen Aufruf bis zu 10-mal erneut), liefert der Aufruf
   `_commit_progress(0, remaining=<Zahl der wartenden Zeilen>)`: dann gilt der Cron als „teilweise erledigt“ und kommt sofort wieder an die Reihe. `remaining=0`
   würde ihn als „fertig“ werten (`ir_cron.py` `_run_job`, `match`), er ruhte bis zum nächsten Intervall.
2. **Aufräumen:** `running`-Zeilen sind zu Beginn eines Aufrufs veraltet (der Core lässt von einem Cron nie zwei Läufe gleichzeitig zu) und gehen
   auf `pending` zurück (Zähler +1). Jobordner früherer Läufe werden gelöscht.
3. **Holen:** bis zu N Dateien mit `try_lock_for_update`, deren geschätzte Dauer ins Restbudget passt.
4. **Prüfen** (**(14.10.)** in einem Kindprozess mit Zeitgrenze, nicht im Cron-Prozess; `pdfminer`): Seitenzahl und Text je Seite, je Seite `TextConverter` mit
   `LAParams(detect_vertical=True, boxes_flow=None)` (wie `attachment_indexation`; `extract_pages` liefert für den unsichtbaren OCR-Text nur Einzelzeichen und keine Textboxen, also leeren Text). Der Kindprozess meldet jede fertige Seite,
   bei Überschreiten der Frist wird er beendet und die bisherigen Seiten bleiben (Wiederaufnahme ab der nächsten Seite). „Hat Text“ gilt bei getaggtem PDF oder mehr als 50 Zeichen. Hat jede Seite
   Text: keine OCR, nur Text und Seiten speichern. Verschlüsselte oder signierte PDFs: vorhandenen Text nehmen. Warum nicht im Prozess: eine Seite kann Minuten brauchen (91 s gemessen), die Prefork-Grenze
   `limit_time_cpu` tötet den Worker, im Threaded-Betrieb hält die Rechnung den GIL und die Webanfragen werden um etwa das Vierfache langsamer (10 → 45 ms).
5. **OCR in Abschnitten:** `ocrmypdf --skip-text --pages a-b` als Kindprozess auf dem Ergebnis des Vorlaufs. Erster Abschnitt klein, misst die Zeit
   je Seite; Abschnittsgröße = Restbudget / gemessene Zeit je Seite. Überschreitet ein Abschnitt die Frist: Prozessbaum beenden (`SIGTERM`, nach 5 s
   `SIGKILL`, mit `psutil`), Abschnitt halbieren, wiederholen. Zwischenergebnis liegt im Modulspeicher (nicht in `/tmp`).
   **Wiederaufnahme nach Absturz (14.10., Regel, ungetestet):** Der Abschnitt schreibt in eine Datei im Modulspeicher (`<abschnitt>.tmp`), die nach `fsync` atomar umbenannt wird. Erst danach werden
   im selben Commit `next_page` und der Pfad der Zwischendatei (mit Größe) an der Zeile gespeichert. Nach einem Absturz gilt: fehlt die Datei oder weicht die Größe ab, wird der Abschnitt aus dem letzten
   gesicherten Stand wiederholt; ein Abschnitt zweimal mit `--skip-text` ändert das Ergebnis nicht. Die Zwischendatei gehört zu den Dingen, die der Aufräumer kennt (Abschnitt 3, „Aufräumen“).
   **OCR-Modus (14.10., gemessen):** Ohne Modus bricht `ocrmypdf` bei einer Seite mit Text mit Exit 6 ab. `--skip-text` lässt bei einer Seite mit digitalem Text *und* eingescanntem Bildteil den Bildtext
   unerkannt (Exit 0). `--redo-ocr` erkennt den Bildteil und behält den digitalen Text (16 KB), `--force-ocr` rastert die Seite und erkennt alles (130 KB). Auf reinen Scanseiten liefern `--skip-text` und
   `--redo-ocr` denselben Text in derselben Zeit. **`--redo-ocr` ist mit `--deskew` (und `--clean-final`) nicht kombinierbar** (Exit 1, Meldung von `ocrmypdf`). Regel je Abschnitt: hat eine Seite Text
   und zugleich ein Bild, `--redo-ocr` ohne Ausrichten; sonst `--skip-text` mit den Einstellungen für Ausrichten und Drehen. `--skip-text --deskew --rotate-pages` kostete 2-fach so lange wie ohne (37,6 s gegen 18,5 s für 11 Seiten).
   **Wiederaufnahme (gemessen):** Ein mit `SIGKILL` beendeter Abschnitt hinterlässt keine Ausgabe- und keine `.tmp`-Datei (`ocrmypdf` schreibt erst am Ende); nach Fortsetzung ab dem gesicherten Stand ist der Text
   aller 15 Seiten identisch mit einem ununterbrochenen Lauf, und ein Abschnitt zweimal auf seinem eigenen Ergebnis ändert den Text nicht.
6. **Start des Kindprozesses** nur mit Standardbibliothek: ein Inline-Start (`sys.executable -c …`) hebt `RLIMIT_AS` auf den Hard-Wert (Odoo setzt es in **beiden**
   Betriebsarten und der Kindprozess erbt es), setzt `os.nice` und ersetzt sich per `execvp` durch `ocrmypdf`. `RLIMIT_CPU` braucht keine Anhebung: im Prefork
   ist `SIGXCPU` im Cron-Thread blockiert und die Signalmaske erbt der Kindprozess (das CPU-Limit tötet ihn nicht, geprüft), im Threaded-Betrieb gibt es keines.
   `nice` ist relativ (`os.nice(n)`), der Prefork-Cron-Worker startet schon mit 10: die Einstellung als absoluten Wert setzen (`os.nice(wert - os.nice(0))`).
   Umgebung: `OMP_THREAD_LIMIT=1`, `TMPDIR` = Jobordner (Windows: `TEMP`/`TMP`). Keine GNU-Präfixprogramme. Auf Systemen ohne `resource` (Windows) startet er ohne diesen Schritt.
   **(14.10.)** `OMP_THREAD_LIMIT=1` bringt gegenüber `ocrmypdf` 17.12.1 nichts Messbares: `ocrmypdf` setzt den Wert selbst (`clamp(jobs // Seiten, 1, 3)`,
   `tesseract_ocr.py`, Funktion `validate`); Wall und CPU waren bei `-j1/2/4/8` mit und ohne identisch. Erzwungen 4 oder 8 kostet +55 % CPU. Die Zeile bleibt, damit das Verhalten
   nicht von der `ocrmypdf`-Version abhängt. **Windows:** `execvp` ersetzt den Prozess dort nicht (gemessen: der Wrapper kehrt nach 0,04 s mit Code 0 zurück, das Kind läuft weiter), `os.nice`,
   `resource` und `SIGKILL` fehlen. Dort startet der Prozess direkt per `subprocess`, beendet wird er mit `psutil` (`terminate()`/`kill()`); Prefork gibt es dort nicht (`PosixOnlyOption`).
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
| 7, 4, 10 | bis zur Einstellung „Wiederholungen“ erneut. **(14.10.)** Exit 7 ist auch ein fester Fehler (gemessen: „Image too large: (41437, 5315)“ in Tesseract): `stderr` auswerten; bei Bildgröße einmal mit `--tesseract-downsample-large-images`, sonst endgültig `failed` |
| 3 fehlende Abhängigkeit, 9 Konfiguration | OCR stoppt, Meldung in den Einstellungen |
| Frist trotz kleinstem Abschnitt | `failed: zu langsam` |
| Platte voll | pausieren |

**Warum nicht anders:** Läuft eine Cron-Pass länger als das Odoo-Limit, lädt der Threaded-Server neu (`server.py:735-755`; die Prüfung läuft nur alle 60 s, gemessen
wurden 65 s bis zur Meldung) oder der Prefork-Watchdog beendet den Worker (`server.py:1018-1027`). Dieselbe Datei käme wieder dran; nach 3 Zeitüberschreitungen führt
der Core den Cron nicht mehr aus (`CONSECUTIVE_TIMEOUT_FOR_FAILURE`). Deshalb eigene Frist und Abschnitte statt „ganze Datei und hoffen“.
**(14.10.) Genauer:** Der Core überspringt den Lauf nur, wenn kein Fortschritt gemeldet wurde (`timed_out_counter >= 3 and not done`, `ir_cron.py` um Zeile 431; gemessen: nach dem dritten Kill
„timed out“, der vierte Lauf entfällt). Meldet der Job vor dem Kill Fortschritt (`_commit_progress`), gibt es nie „timed out“: der Server lädt dann in jeder Minute neu, eine Endlosschleife (gemessen).
Ein Job darf deshalb nie Fortschritt melden und trotzdem die Frist reißen.

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
| Extraktion | Zeitgrenze des Extraktions-Kindprozesses je Aufruf (14.10., ersetzt die Größengrenze 50 MB) | aus dem Cron-Budget |
| | Speicherbudget je Datei (14.10.) | 1 GiB (Vorschlag, nicht gemessen) |
| | Textblock je Seitenzeile für Office/Text (14.10.) | 64 KB (Vorschlag) |
| | `work_mem` der Suche (14.10.) | 256 MB (gemessen: 5 s statt 281 s; Zwischenwerte fehlen) |
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

Nicht geprüft (Stand 13.10.; Stand 14.10. siehe 7b): `LC_CTYPE` der Live-Datenbank, Windows, das Verhalten von pdf.js bei geändertem Hash im Browser, GIN-Leistung bei Millionen Seiten, Postgres 17.

## 7b. Belege: Messungen vom 2026-10-14 (Wegwerf-Umgebung auf dem Tower, Image `odoo:19.0-hm-test` 19.0-20260817, `ocrmypdf` 17.12.1, Postgres 16.15 und 18.1)

Das Image weicht vom Klon (`7a74539`) kaum ab (`ir_cron.py` identisch). Die Werte sind Belege für Verhalten, keine Designgrundlage.

| Messung | Ergebnis |
|---|---|
| Cron Threaded, `limit_time_real=20` | `-1` und `0` beide wie `limit_time_real`; Kill erst beim 60-s-Takt (59 s gemeldet); `1000`: Job läuft 100 s durch. Nach 3 Kills ohne Fortschritt „timed out“, vierter Lauf entfällt; mit `_commit_progress` nie „timed out“, Neustart jede Minute |
| Zeitbudget-Schleife Threaded (`limit − Reserve − Zeit seit thread.start_time`) | Pass nach 23 s beendet, „partially done“, nächster Lauf genau 60 s später (`SLEEP_INTERVAL`); `_commit_progress` liefert 9,0 → 0 (Jobstart + 10 s) |
| Cron Prefork | Watchdog zählt ab letztem Herzschlag: Limit 100 s, Job gekillt nach 31 s; Limit 20 s: untätiger Cron-Worker alle 24 s getötet; `limit_time_cpu=10`: „CPU time limit reached“, Worker beendet, Job startet nach 64 s neu |
| Webzugriff (Login-Seite, 10/s, auf einen Kern festgelegt) | Threaded + CPU-Last im Odoo-Prozess (Rechnung oder `pdfminer`): Antwort 10 → 45 ms (p95 52); Prefork: unverändert; `ocrmypdf` als Kindprozess: unverändert, auch ohne `nice` |
| `pdfminer`, Odoo-Einstellungen | normal 0,03 bis 0,11 s je Seite (1.036 Seiten 35 s; 581 Seiten 62 s; 1.458 Seiten 66 s); Ausreißer 6,9 MB / 28 Seiten 149 s (eine Seite 91 s); 250 MB / 60 Seiten 6,4 s, 544 MB RAM; `pdfminer` 20221105 (offizielles Image) gleich |
| `attachment_indexation` | ohne Modul 0,0 s; mit Modul 0,7-MB-PDF 3,3 s, 14 MB 12,8 s, 25 MB 33 s, 40 MB 37 s, 6,9 MB komplex 154 s; xlsx 100.000 Zeilen 11,9 s, 13,5 Mio. Zeichen; kein Index auf `index_content` |
| OCR Abschnitte, 396 Seiten / 9 MB, `-j4` | am Stück 161 s; Abschnitte zu 100/50/25/10/5 Seiten: +3/+9/+21/+62/+139 % Zeit, CPU +0/+0/+0/+7/+17 % |
| OCR Abschnitte, 2.596 Seiten / 54 MB | am Stück 1.100 s, 945 MB RAM; 26 Abschnitte zu 100: 1.308 s (+19 %), 392 MB RAM; fester Aufwand je Aufruf 5,5 s |
| OCR Durchsatz, 50 PDFs aus dem Bestand (39 reine Scans mit 170 Seiten, 10 gemischte mit 417 Seiten) | Scans 7,5 CPU-s je Seite, 17,5 Seiten/min bei `-j4` (zwei Läufe: 536 s, 584 s); gemischte 0,27 CPU-s je Seite; eine Datei Exit 7 „Image too large“ |
| OCR Qualität | 112 Seiten Text-PDF als Bild gerendert, mit der Textebene verglichen: 300 dpi 99,2 % der Wörter, Umlautwörter 97,2 %; 150 dpi 97,8 % und 94,9 %. Echte Scans nur Näherung: 73 % der Wörter im Vokabular aus 70 deutschen Büchern (Umlautwörter 69 %) |
| Platz je Seite | Text 1,9 bis 2,2 KB; GIN 467 B (Postgres 16) / 432 B (18); Tabelle samt Auslagerung 2,6 KB; OCR-PDF bei Scans 899 KB je Seite (0,84-fach, eine volle zweite Kopie) |
| `OMP_THREAD_LIMIT` | 28 Seiten, `-j1/2/4/8`: mit und ohne gleich; erzwungen 4/8: +55 % CPU, −7 % Zeit |
| GIN, 3.000.002 Seiten, 68.543 Texte, 477.086 Dokumente | Aufbau 28 min (16, 64 MB `maintenance_work_mem`), 24 min (1 GB), 13 min (18); Einfügen von 100.000 Seiten mit Index 9 min (184 Seiten/s) |
| Suche auf 3 Mio. Seiten | seltenes Wort (996 Seiten) 0,2 s; mittleres Wort 0,8 s (16) / 2,7 s (18); häufiges Wort (616.280 Seiten) bei `work_mem` 4 MB 281 s (16) / 360 s (18), bei 256 MB 5 s; Rechte-Filter ohne messbaren Zusatz (7,6 s ohne, 7,0 s mit Regel beim häufigen Wort) |
| `work_mem`-Reihe (Postgres 18, 616.280 Treffer) | 16 MB 115 s; 32/64/128/256 MB 4,1/3,4/3,5/3,6 s; ohne parallele Arbeiter 64 MB 2,2 s, 128/256 MB 1,1 s; Wort mit 59.470 Treffern bei 4/16/64 MB 0,87/0,94/0,94 s |
| Anti-Join der Cron-Auswahl (Postgres 18, 408.543 Dokumente, 68.543 Texte, gemessen nach 5.000 neuen PDFs und 3.000 gelöschten) | Dokumente ohne Zeile (PDF, 0 Treffer, `LIMIT 100`) 346 ms; mit 5.000 Treffern 141 ms; Zählung aller 79 ms; beliebiger Typ 4 ms; Texte ohne Dokument (0 Treffer) 91 ms, mit 3.000 Treffern 95 ms, Zählung 88 ms |
| Prefork-Budget mit Jobuhr (`cron_end_time − 10`) | Limit 100 s, Worker 25 s und 80 s untätig, per Trigger geweckt: Pass endet nach 33 bis 34 s „partially done“, kein Kill; drei Pässe nacheinander mit sofort zurückkehrenden Wiederholaufrufen: je 24 bis 25 s, kein Kill. Ein Zähler ab Methodenaufruf (Wiederholaufrufe mit neuem Zähler) lief bis zum Kill |
| OCR-Modi, gemischte Seite (digital oben, Bild unten) | ohne Modus Exit 6; `--skip-text` Bildtext nicht erkannt; `--redo-ocr` und `--force-ocr` erkennen ihn (16 KB gegen 130 KB); `--redo-ocr` mit `--deskew` Exit 1; reine Scanseiten mit `--skip-text` und `--redo-ocr` gleicher Text, gleiche Zeit |
| Wiederaufnahme-Regel, 15 Seiten in 3 Abschnitten | Kill im 2. Abschnitt hinterlässt weder Ausgabe noch `.tmp`; nach Fortsetzung Text aller Seiten identisch mit dem ununterbrochenen Lauf; Abschnitt zweimal auf eigenem Ergebnis: Text unverändert |
| Wortpositionen im OCR-PDF | `pdfplumber` (im Image) liest 154 Wörter mit Koordinaten von Seite 1; `pdfminer` `extract_pages`: 1.050 Zeichen, 0 Textboxen |
| Wortstämme | Postgres 18 stemmt anders als 16 (`Übung` → `ubung` statt `uebung`; `kön` 59.470 statt 42.669 Seiten): nach einem Major-Upgrade Index neu aufbauen |
| `LC_CTYPE` | Live-DB auf dem Tower: `LC_COLLATE C`, `LC_CTYPE en_US.utf8` (Odoo legt mit `LC_COLLATE 'C'` an, `service/db.py:143-148`). Faltung `Übung` = `uebung` in `C`, `en_US`, `de_DE`, `C.UTF-8`, builtin; nur bei `LC_CTYPE C` bleiben `CAFÉ` und `ПРИВЕТ` groß und werden nicht gefunden |
| Sicherheit der Suche, 2 Benutzer | gleiche Prüfsumme in fremdem Ordner verrät nichts (Treffer, Zählung, Gruppierung, Ordnersuche, `not ilike`); Textauszug mit fremder ID `AccessError`; Textmodelle ohne ACL unlesbar; `sudo()` sieht alles; eine Methode mit Text-IDs ohne Dokumentprüfung leckt (Negativkontrolle) |
| Blob ersetzen (`os.replace` über vorhandenen Namen) | Unraid-Share: 0,6 % der Lesezugriffe ENOENT (Härtetest: 3 Leser gegen Dauer-Ersetzen); direkt auf dem Cache-Laufwerk 0 |
| Bestand auf dem Tower (`/mnt/user/Daten`) | 4.967 PDFs, 8,47 GiB, 175.355 Seiten; Textebene 93,9 %, reine Scans 3,4 % (4,8 % der Seiten), gemischt 2,5 % (8,0 %); mindestens 1.107 Kopien; die 79.411 sind hier nicht reproduzierbar (vermutlich HM-SRV) |
| Windows (auf einem Windows-Rechner) | `os.nice`, `resource`, `SIGKILL` fehlen; der `execvp`-Wrapper kehrt nach 0,04 s mit Code 0 zurück statt nach 3 s mit Exit 7; `psutil` garantiert (`setup.py:49`, `requirements.txt:57-59`, `debian/control:51`, `server.py:23`), `pdfminer` nicht |

Ungemessen bleiben: Postgres 17, HM-SRV, das Verhalten von pdf.js im Browser, die gespeicherte `tsvector`-Spalte in voller Größe, eine echte (nicht künstliche) gemischte Seite für `--redo-ocr`.

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
- `pdfminer` ist keine Odoo-Requirement: das Image oder die Umgebung muss es mitbringen; `attachment_indexation` warnt nur im Log, wenn es fehlt. (14.10.) Im offiziellen Image `odoo:19.0`
  ist `pdfminer.six` 20221105 schon enthalten; `pdfplumber`, `mutagen` und `pyjwt` braucht das Modul nicht (`pyjwt` nur `onlyoffice_odoo`).
- (14.10.) `attachment_indexation` rechnet synchron beim Anlegen jedes Anhangs, ohne Größengrenze: ein 6,9-MB-PDF 154 s, eine xlsx mit 100.000 Zeilen 11,9 s und 413 MB Spitze. Die
  Beschreibung im Manifest („Attachments list“) ist veraltet, das Modul bringt keine Oberfläche mit.
- (14.10.) `pdfminer`: `extract_pages` bildet für den unsichtbaren OCR-Text keine Textboxen (1.050 Zeichen, 0 Textboxen; Textauszug leer), `TextConverter` je Seite liest ihn. Die Kosten hängen an der Seite: ein einzelnes Blatt 91 s.
- (14.10.) GIN auf einem Ausdruck: Bei zu kleinem `work_mem` wird die Trefferliste „lossy“ und Postgres rechnet die Faltung für alle Zeilen der Blöcke nochmal (281 s gegen 5 s). Die Schreibleistung mit
  Index (184 Seiten/s) reicht für `pdfminer` und OCR, nicht für einen schnellen Massenimport.
- (14.10.) Postgres 16 und 18 liefern für dieselbe Faltung verschiedene Wortstämme: nach einem Major-Upgrade Index neu aufbauen; ein bestehender Index findet sonst neue Anfragen nicht.
- (14.10.) Prefork: ein Cron-Limit unter etwa 90 s tötet untätige Cron-Worker; das Zeitbudget beginnt vor dem 60-bis-69-s-Schlaf (Abschnitt 4 Schritt 1).
- (14.10.) `_publish_blob`: `exists` und `os.replace` ohne Sperre. Zwei gleichzeitige Uploads derselben Datei ersetzen einander; auf dem Unraid-Share sehen Leser dabei kurz ENOENT (0,6 %, Härtetest). Absicherung
  im Code vorgesehen (Abschnitt 10), unabhängig von der Volltextsuche.
- Die Markierung im Viewer ist wörtlich (`pdf.js` `search=`), die Suche nicht (Stemming, Faltung): `Mueller` findet `Müller`, markiert wird nichts.

## 10. Änderungen am Bestand (Realitätscheck)

- Neu: Textmodelle, Index, Suchfeld, Cron, Einstellungen, Status, Ordner-Schalter, Treffer-Ansicht, Viewer-Anbindung.
- Zu ändern: `_gc_blobs` (benutzte Prüfsummen und Sperre der Texttabelle), `DocumentFile.defaultSource` (PDF-Adresse mit `#page=…&search=…`, Quelle: OCR-PDF oder Original).
  **Serverseite der Auslieferung:** `/web/content/int.filemanager.document/<id>/content` liefert über `ir.binary._record_to_stream` und `_to_http_stream` heute
  nur das Original. Für das OCR-PDF braucht es eine Variante (Parameter oder zweites Binärfeld), die dieselbe Zugriffsprüfung über das Dokument macht und die
  Prüfsumme des OCR-PDFs als ETag nimmt; Download liefert weiter das Original.
- Neu zusätzlich: Aufräumer für Textzeilen und OCR-PDFs ohne Dokument (Abschnitt 3); Anlage der Textzeilen (Abschnitt 12, offen).
- Manifest: `depends` um `attachment_indexation` erweitern; Aufteilung der Datei `int_filemanager_text.py` nach Coding Guidelines (Datei je Modell).
  **(14.10.)** Entschieden: nein, `depends` bleibt `base`, `mail`.
- (14.10.) `_publish_blob` absichern (eigener Fix, vor einem großen Import): `os.replace` nur, wenn der Zielname fehlt (Prüfung nach der Sperre), gleichzeitige Veröffentlichung derselben Prüfsumme per
  `pg_advisory_xact_lock` auf dem Hash (Core-Muster: `pg_try_advisory_xact_lock(hashtext(…))` in `mail_thread.py:1488`); Test mit zwei Cursoren. `_gc_blobs` kennt außerdem die Zwischendateien der Abschnitts-OCR (Abschnitt 3) und die Prüfsummen der OCR-PDFs.
- (14.10.) Das Dokument hat kein Quota; abgeleitete OCR-PDFs (bei Scans eine volle zweite Kopie) zählen nicht in die Größenauswertung (Pivot „Wohin der Platz geht“): entscheiden, ob sie dort erscheinen.
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
- (14.10.) Cron: Prefork-Budget = Limit − Schlafzeit − Reserve, Eigenzähler fehlt `start_time`; kein Fortschritt melden, wenn danach die Frist gerissen wird; `pdfminer`-Kindprozess wird bei Fristablauf
  beendet und liefert die bisherigen Seiten; Seite mit sehr langer Rechenzeit (simuliert) blockiert den Stapel nicht; Zwischendatei fehlt nach „Absturz“ → Abschnitt wird wiederholt.
- (14.10.) Textblöcke: große xlsx (über 650.000 Bytes) wird in Blöcke zerlegt, nichts geht verloren; Dateityp außerhalb der Liste bekommt keine Zeile und bleibt kein „Dokument ohne Zeile“.
- (14.10.) Suchfeld: Label ungleich `content` (keine Odoo-Warnung); `SET LOCAL work_mem` gilt nur in der Suche (nach der Transaktion wieder Standard); `Übung`/`uebung` auch bei `LC_CTYPE C`.
- (14.10.) `_publish_blob`: zwei gleichzeitige Veröffentlichungen derselben Prüfsumme (zwei Cursoren) ersetzen den Blob nicht doppelt; `_gc_blobs` behält OCR-PDF und Zwischendatei, solange die Zeile existiert.
- Archivieren und Wiederherstellen eines Dokuments; Zeile ohne Blob (Datei weg) → `failed`; Cron legt Zeilen für Dokumente ohne Zeile an (nicht für archivierte);
  `skipped` → `pending` nach Anheben der Grenze; Bilder-Schalter: Text einer Prüfsumme ist auch über das Dokument im Ordner ohne Schalter auffindbar; Markierungsterme
  kommen aus dem Textauszug, nicht aus der Eingabe.

## 12. Offen / ungemessen

Gemessen am 14.10. (Abschnitt 7b): Overhead der Abschnitte, OCR-Durchsatz und Platzbedarf, Verhalten unter Last, `OMP_THREAD_LIMIT`, `pdfminer` bei großen Dateien, GIN bei 3 Mio. Seiten,
Windows, `LC_CTYPE`, Sicherheit der Suche, Zählung des Bestands auf dem Tower (4.967 PDFs; die 79.411 sind dort nicht reproduzierbar).

Nachgemessen am 14.10. (zweiter Lauf, Abschnitt 7b): `work_mem`-Reihe, Anti-Join der Cron-Auswahl, Prefork-Budget mit Jobuhr, OCR-Modi, Wiederaufnahme-Regel, Wortpositionen.

Weiter offen:
- pdf.js im Browser bei geändertem Hash im bestehenden Frame (Quelltext sagt: wird verarbeitet, `viewer.js:14625-14634`; Browser-Test steht aus, macht der Nutzer). Dazu `matchDiacritics: true`:
  `Mueller` markiert kein `Müller`.
- HM-SRV (von hier nicht erreichbar): `LC_CTYPE` und Bestand dort. Postgres 17 bleibt ungeprüft (Entscheidung: 16.15 und 18.1 reichen).
- Die gespeicherte `tsvector`-Spalte in voller Größe (nur nötig, wenn `work_mem` nicht reicht).
- Die `--redo-ocr`-Regel (Abschnitt 4 Schritt 5) für Seiten mit Text und Bild ist an einer künstlichen Seite gemessen; eine echte gemischte Seite aus dem Bestand fehlt.
- Qualität echter Scans ist nur über ein Vokabular geschätzt (73 % Treffer), nicht gegen eine Wahrheit gemessen; dafür bräuchte es einige Seiten mit abgetipptem Text.

**Entschieden am 2026-10-14:**
1. **`attachment_indexation` als Abhängigkeit (ersetzt Entscheidung 7 vom 13.10.):** nein; eigene schlanke Extraktion im Cron (Abschnitt 2). `depends` bleibt `base`, `mail`.
2. **Prefork:** Threaded und Prefork gleichzeitig in Stufe A (Abschnitt 4 Schritt 1 und 5, Tests in Abschnitt 11).
3. **Häufige Wörter:** `SET LOCAL work_mem` nur in der Suche, ohne parallele Arbeiter (Abschnitt 3); gespeicherte `tsvector`-Spalte nur, wenn das nicht reicht.
4. **Postgres 17:** nicht laden; 16.15 und 18.1 gelten als Eckpunkte.
5. **Wortpositionen:** nicht in der Datenbank speichern. Sie stehen in der Textebene des OCR-PDFs und werden bei Bedarf daraus gelesen (`pdfplumber` liest 154 Wörter mit Koordinaten von einer Seite). Neu bewerten nur, wenn das Anklicken oft vorkommt und das Lesen je Seite zu langsam ist.

**Entschieden am 2026-10-13** (Produktentscheidungen aus der Prüfung):
1. **Datei über der Größengrenze:** `skipped` mit `message`; die Grenze ist eine Einstellung (Abschnitte 2, 5).
2. **Cron:** ein `ir.cron` `_cron_ocr` für Extraktion und OCR (Abschnitt 4).
3. **„Parallele Jobs“:** gestrichen; ein Kindprozess zugleich, mehr Durchsatz über „Kerne je Job“ (Abschnitt 5).
4. **Ordnerschalter für Bilder:** löst nur die OCR aus, die Suche folgt ihm nicht (Abschnitt 2).
5. **Markierung im Viewer:** Wortformen des Treffers aus dem Textauszug (Abschnitt 2).
6. **Textzeilen:** der Cron legt sie für Dokumente ohne Zeile an; Regeln für Neu-Verarbeitung, Archiv und fehlenden Blob in Abschnitt 3.
7. **`attachment_indexation`:** Nebenwirkung bleibt akzeptiert, die Messwerte stehen in Abschnitt 9 und 7a. *(Am 14.10. durch neue Messungen ersetzt: nicht als Abhängigkeit, siehe „Entschieden am 2026-10-14“ oben.)*

## 13. Reihenfolge

0. (14.10.) Vorab, unabhängig von der Suche: `_publish_blob` gegen gleichzeitige Veröffentlichung derselben Prüfsumme absichern (Abschnitt 10).
1. Stufe A: Textmodelle (mit Dateitypliste und Textblöcken), Index, Suchfeld mit eigenem Label, Rechte, `work_mem` in der Suche, Cron mit Extraktion in einem zeitbegrenzten Kindprozess
   (Threaded und Prefork, Zeitbudget je Betriebsart, Wiederholaufrufe kehren sofort zurück), Aufräumer, Tests (inklusive Sicherheit und `LC_CTYPE C`). Die Entscheidungen in Abschnitt 12 sind gefallen;
   offen sind nur Dinge, die Stufe A nicht blockieren.
2. Viewer-Anbindung (vorher JS-Regeln `js_framework`, `js_fields` lesen; Browser-Test des Hash-Wechsels), Treffer-Ansicht.
3. Stufe B erst, wenn Wiederaufnahme, OCR-Modi, Prefork-Budget und Verwaltung der abgeleiteten PDFs widerspruchsfrei spezifiziert und getestet sind: OCR-Cron mit Abschnitten nach Zeitbudget,
   Einstellungen, Status, Ordner-Schalter.
