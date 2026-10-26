# int_filemanager_ocr: Volltextsuche und Texterkennung (OCR)

Kurzfassung dessen, was gebaut ist und warum. Maßgeblich bleibt der Code. Das Modul `int_filemanager_ocr` erweitert `int_filemanager`
(Felder, Aufräumen, Settings über Erweiterungspunkte des Kerns, siehe `docs/int_filemanager/modulaufteilung.md`). Es läuft auf jedem
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

- **`int.filemanager.text`:** eine Zeile je Prüfsumme des Blobs (doppelte Dateien teilen sich eine Zeile). Der Lese-Zustand `state` (`pending`, `running`, `done`, `empty`, `skipped`, `failed`) und der Erkennungs-Zustand `ocr_state` (`wait`, `running`, `done`, `skipped`, `failed`) sind getrennt; `engine_version` erzwingt neues Lesen, wenn das Lesen sich ändert. Die Felder im Einzelnen: Code.
- **`int.filemanager.text.page`:** eine Zeile je Seite (PDF) oder je Block von höchstens 64 KB als Pseudo-Seite (Office, Text); `scan` markiert Seiten mit Bild und kaum Text (Teilindex nur darüber). Obergrenze je Zeile 650.000 Byte, darüber wird gekürzt (`tsvector` bricht bei 1 MB, schon beim `INSERT`).
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
- **Viewer:** PDFs mit erkanntem PDF zeigen dieses (Route `viewer_pdf_content`, gleiche Zugriffsprüfung wie `content`, ETag = Prüfsumme des erkannten PDFs);
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
(digitaler Text plus eingescanntes Bild) bleiben unberührt (`--skip-text`).

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

**Größe des Abschnitts:** aus der Restzeit und der geglätteten Zeit je Seite (mindestens 1, höchstens 100 Seiten; ohne Messung höchstens 10).

**Wiederaufnahme nach Absturz:** Zeile zeigt immer auf die letzte ganze Zwischendatei. Fehlt sie oder hat sie eine andere Größe, beginnt die Erkennung bei
Seite 1 mit dem Original und verbraucht keinen Versuch (die Scanseiten werden aus den Seitenzeilen neu bestimmt). Ein Abschnitt zweimal mit `--skip-text` ändert das Ergebnis nicht. Zeilen, die beim Start eines Laufs
noch `running` sind, gehen auf `wait` zurück (+1 Versuch).

**Fehlerzuordnung:** `tools/ocr_plan.py`, `classify` (reine Funktion über die Exit-Codes von `ocrmypdf`). Grundsatz: Liegt der Fehler an der Datei (kaputt, Passwort), wird sie `failed`; liegt er an der Einstellung oder am Programm (falsche Option, Programm fehlt), hält die Erkennung an und meldet es in den Einstellungen; bei Zeit, Speicher oder Abstürzen gibt es Wiederholungen bis `max_attempts`; bei vollem Datenträger pausiert sie. Einzelne Fälle (fehlende DPI, Seite mit Text, zu großes Bild) werden einmal mit angepasster Option wiederholt.

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

Namen und Standardwerte stehen in `models/res_config_settings.py` (Zeitreserve, Speicher je Datei, Blockgröße, Versuche, `ocr_enabled` standardmäßig aus, Sprachen `deu+eng`, Kerne, `nice`, Ausrichten, Ausgabeformat).

Zahlenfelder speichern in den Odoo-Einstellungen keine 0, Häkchen kein „aus“ bei Standard „an“: deshalb Auswahlfelder. Die Programme (`ocrmypdf`, `tesseract`,
Sprachen) werden zur Laufzeit gesucht und fünf Minuten gemerkt; `external_dependencies` im Manifest bleibt leer. Der Status zeigt Zustand mit Grund,
Programme mit Version und Sprachen, Zahlen je Zustand, offene Seiten mit grober Restdauer, Gesamtgröße der erkannten PDFs und Hinweise (Zeichensatz `C`
der Datenbank, `limit_time_real_cron`). Die Liste „Texte der Dateien“ (Administratoren) hat Spalten, Filter und Knöpfe „Erneut lesen“ und „Erneut erkennen“.

## 9. Stolpersteine

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

## 10. Abgrenzung und Offenes

- **Nicht gemacht:** `attachment_indexation` als Abhängigkeit (synchron, ohne Grenze); Wortpositionen in der Datenbank (stehen in der Textebene des
  erkannten PDFs); OCR für gemischte Seiten (`--redo-ocr` ist mit Ausrichten nicht kombinierbar, im Bestand sehr selten); ein eigener Dienst oder Container.
