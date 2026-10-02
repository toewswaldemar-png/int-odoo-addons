# int_filemanager – Entscheidungen und Befunde

Stand 2026-10-02. Hier steht, **warum** etwas so gebaut ist und was bewusst **nicht** gebaut wird. Was der Code tut, steht im
Code und in den Tests; diese Datei wird nur ergänzt, wenn eine Entscheidung fällt, und nicht nachgeführt, wenn sich Code ändert.
Die ausführlichen Vorgänger (Konzept, Werterkennungs-Plan, Oberflächen-Konzept, Übergabe) stehen im Git-Tag
`docs-vor-aufraeumen-2026-10-02` (`git show docs-vor-aufraeumen-2026-10-02:docs/<Datei>`).

## Grundregeln I1–I13

Gelten immer, auch bei Absturz und Last; jede hat Tests. Die Kürzel stehen in den Tests und Entscheidungen, nicht in Code-Kommentaren.

| # | Regel | in einfachen Worten |
|---|---|---|
| I1 | Nur Odoo schreibt in den Dateispeicher. | Keine Hintertür auf die Dateien. |
| I2 | Ein gespeicherter Inhalt wird nie verändert. | Neue Fassung = neue Datei im Speicher, benannt nach ihrer Prüfsumme. |
| I3 | Erst die Datenbank, dann die Wirkung nach außen. | Mails, Umwandlungen usw. erst, wenn der Vorgang sicher gespeichert ist. |
| I4 | Inhalte werden erst gelöscht, wenn nichts mehr auf sie verweist **und** eine Schonfrist abgelaufen ist; im Zweifel bleiben sie. | Kein Datenverlust durch Aufräumen, auch nicht bei gleichzeitigem Upload desselben Inhalts. |
| I5 | Nichts wird gelöscht, nur weil es nicht gesehen wurde. | Kein Watcher, kein Scan, der Dateien entfernt. |
| I6 | Jede gespeicherte Fassung ist wiederherstellbar. | Versionen und Papierkorb. |
| I7 | Rechte prüft nur Odoo, für jede Tabelle und jeden Zugriffsweg. | Auch Versionen und Inhalte sind geschützt; Admin-Rechte im Code erst nach der Prüfung. |
| I8 | Verweise über Nummern (IDs), nie über Pfade. | Umbenennen und Verschieben brechen nichts. |
| I9 | Was Nutzer sehen, ändert sich ganz oder gar nicht; Wiederholungen und gleichzeitige Zugriffe erzeugen keine Doppelungen. | Doppelklick, Abbruch, erneutes Senden, zwei gleichzeitige Uploads sind harmlos. |
| I10 | Odoo selbst wird nicht verändert. | Updates bleiben möglich. |
| I11 | Fremde Dateiformate werden außerhalb von Odoo verarbeitet. | Vorschaubilder und OCR in einem eigenen Container. |
| I12 | Keine ganzen großen Dateien im Arbeitsspeicher. | Hoch- und Herunterladen als Datenstrom. |
| I13 | Odoo öffnet keine fremden Dateibytes, auch nicht die Ergebnisse des Umwandlers. | Vorschaubilder und Text liegen im Dateispeicher und werden nur ausgeliefert. |

## 1. Grundsatz

| Entscheidung | Grund |
|---|---|
| **Dateimanager vollständig als Odoo-Addon, Odoo ist alleiniger Schreiber** (2026-09-26) | Fast alle Fehler des Stands auf `master` kamen vom direkten Schreiben anderer (SMB, Explorer) auf dieselben Dateien: Watcher verliert Ereignisse (17 % bei 20.000 Dateien per robocopy), zwei Schreiber überschreiben sich still, Rechte laufen an Odoo vorbei, überschriebene Fassungen sind weg. Ein Schreibweg macht die Invarianten I1–I13 überhaupt erst haltbar. |
| Eigenbau nur, wo Odoo nachweislich nicht reicht | Wiederholt war "gibt es nicht in Odoo" falsch (siehe CLAUDE.md). Vor jeder Eigenbau-Aussage Core-Grep. |
| **Bestand kopieren, kein Hardlink** | Ein später bearbeiteter Hardlink würde den Blob verändern (I2). Rückweg bleibt möglich: alter Share bleibt schreibgeschützt bis zur Abnahme. |
| Ganzer Share, Versionen unbegrenzt, Papierkorb 30 Tage, Rechte minimal ("Alle" + heutiger Schutzordner) (2026-09-26) | Heute 1 interner Nutzer außer Admin, keine Portal-Nutzer; engere Bereiche erst bei Bedarf. |
| **HM-SRV bleibt vorerst auf `master`** | Die Sicherheitslücke N1 (öffentliche Methoden `action_analyze_document`/`action_apply_extracted_values` mit `sudo`) ist dort noch nicht behoben. |
| Modellnamen mit Präfix `int_filemanager.*`; Code englisch, Oberflächentexte englisch + `i18n/de.po` | Odoo-/OCA-Konvention (`odoo_regeln/odoo_regeln_coding_guidelines_2026-10-02.md`). |
| Keine Verweise auf Dokumente in Kommentaren/Docstrings (2026-09-28) | Dokumente veralten, der Code bleibt. |
| Odoo wird nicht verändert (I10), Änderungen am Datenmodell über Migrationsskripte mit `odoo/upgrade-util` | Updates müssen möglich bleiben. |
| **Bewusst viel Eigenbau, aber klein gehalten**: Blob-Speicher, Upload in Stücken, Umwandler; keine Erweiterungen, bevor das Fundament im Alltag trägt | Für einen Server mit heute einem Nutzer ist das ein Risiko, das bewusst eingegangen wurde. Kein Netzlaufwerk zum Start, kein Samba + Watcher, keine Änderung am Odoo-Kern. |

## 2. Speicher und Schreiben

| Entscheidung | Grund |
|---|---|
| **Eigener inhaltsadressierter Blob-Speicher** statt `ir.attachment` (auch für abgeleitete Dateien, 2026-09-28) | `ir.attachment` hat keinen Datenstrom; Odoo öffnet Anhangsinhalt an vielen Stellen selbst (Pillow-Nachbearbeitung in `_postprocess_contents`, pdfminer/openpyxl in `_index`, `fields.Image`, `/web/image`, `pdf_first_page`, `html_editor`). Eine Wache je Stelle wäre nie vollständig, ein später installiertes Modul kann weitere ergänzen (I13). |
| **Upload in 4-MB-Stücken**, Fortsetzen, Idempotenz | Odoo gibt den rohen Request-Strom nicht heraus, jeder Body liegt ganz im RAM (`http.py`). Worker wachsen mit großen Bodies (16-MB-Stücke bis 1,9 GB), 1 MB: 160 MB, 4 MB: 200–600 MB. Odoo recycelt Worker über `limit_memory_soft`. |
| Downloads über nginx per `x_sendfile` | Ohne nginx belegt jeder Download einen Odoo-Prozess für die ganze Dauer. `x_sendfile` funktioniert nur für Dateien unter `data_dir/filestore`, deshalb liegt der Blob-Speicher dort (Unraid-Share, nur disk2 + disk3, ohne Cache). 3 GB Download: Odoo braucht 5 ms. |
| `finish` großer Dateien als Hintergrundjob | 3 GB: 51–56 s im Request (Hash erneut lesen, `fsync`, DB). |
| Dateigröße nicht als `fields.Integer` | Ist `int4` (max. 2,1 GB). |
| Wettläufe regelt der Code ausdrücklich | Odoos `retrying()` wiederholt `UniqueViolation` (gleicher neuer Name) und belegte Sperren (`55P03`) **nicht** von selbst; Serialisierungsfehler `40001` schon. Deshalb Tests zuerst (`race.sh`, echte Prozessabbrüche), dabei zwei echte Fehler gefunden (`sudo` bei kaltem Cache, Verschieben gegen Löschen). |
| Namen ohne Groß/Klein eindeutig, NFC-normalisiert, Windows-Namensregeln | Wie Windows; NFD (macOS) gegen NFC machte Dateien unauffindbar; Index mit `NULLS NOT DISTINCT`, sonst zwei Wurzeln `Daten`/`daten`. |
| **C-Kollation der Datenbank** | Odoo-Commit `9b1872b179` (2026-09-08) vergleicht `parent_path` per Bereich statt `LIKE`; unter `en_US.utf8` fehlen echte Nachfahren und fremde Pfade werden erfasst, Teilbäume würden beim Verschieben beschädigt. HM-SRV (`en_US.utf8`) **vor jedem Image-Update umstellen**. Tower-Live-DB ist `C`. |
| Dateityp aus den ersten Bytes (libmagic), nicht aus der Endung (2026-09-28) | Schließt eine Lücke bei Dateien mit falscher Endung; HTML wird beim Download immer als Text ausgeliefert. |
| Aufräumjob löscht nur ohne Verweis **und** nach Schonfrist, im Zweifel bleibt der Inhalt (I4) | Ein gleichzeitiger Upload desselben Inhalts darf nicht verlieren. |
| Backup: Datenbank und Blob-Speicher zusammen, erst DB, dann Speicher | Inhalte ändern sich nie, inkrementell reicht. |
| ZIP-Download bis ca. 500 MB direkt als Strom, darüber Hintergrundjob mit Benachrichtigung (2026-09-27) | Ein langer Download belegt sonst einen Odoo-Prozess bis zum Zeitlimit. |
| `fsync` je Datei bleibt | ~28–33 ms auf dem Array, Ausreißer bis 7 s nach Spindown; Absturzsicherheit wiegt mehr. |
| Kopierrate bei der Übernahme 27,5 MB/s | Hochrechnung ca. 18 h für 1,8 TB, ca. 7 % Dubletten. |

## 3. Explorer-Zugriff: bewusst nicht zum Start

**Entscheidung 2026-09-26:** Start **ohne Netzlaufwerk**, dafür **Eingangsordner** (Samba, nur zum Hineinlegen; Odoo übernimmt nach
2 Minuten ohne Änderung, verschiebt erst nach dem Commit nach `_übernommen`, 24 h später gelöscht). Ob und wie später ein
Netzlaufwerk kommt, wird nach der Nutzung entschieden. **Test mit echtem Word/Excel entfällt**, ebenso Handtest-Checklisten.

| Weg | Ergebnis |
|---|---|
| **WebDAV als eigener Odoo-Befehl `odoo fmdav`** (Protokoll WsgiDAV, Basic mit API-Schlüssel mit eigenem Bereich `int_filemanager.dav`, `GET` per `X-Accel-Redirect`) | **Bevorzugte Bauform, falls WebDAV.** litmus 100 %, Windows-WebClient, LibreOffice. Identitätsregel für das Word/Excel-Speichermuster (Temp schreiben, Original wegbenennen, Temp umbenennen) hält Knoten und Versionen. Grenzen: HTTPS mit vertrautem Zertifikat und angehobene Download-Grenze (50 MB) je Windows-Client, viele kleine Dateien langsam (8 Requests je Datei, 0,28 s). |
| WebDAV in einer Odoo-Route (`dav_inproc`) | **Verworfen:** offene Transaktion, Zeitlimits, belegte Worker, nur mit Kniffen beherrschbar; `PUT` großer Dateien liegt im RAM. |
| Separater WebDAV-Dienst mit JSON-RPC | **Verworfen:** langsamer, Hash doppelt, zwei Code-Stände. JSON-2 nimmt nur JSON, Binärdaten nur base64 (I12). |
| **Samba + inotify** (Prinzip von `master`) | **Verworfen:** zweiter Schreiber; unlösbar bleiben gleichzeitiges Schreiben (Odoo ersetzt die Datei, der offene SMB-Client schreibt ins Leere), Rechte an Odoo vorbei, Versionen externer Änderungen. |
| **SMB über Samba + Odoo-FUSE-Dateisystem** | **Eleganteste Alternative für die Clients** (normales Netzlaufwerk, nichts einzurichten), aber ohne Prototyp: UID-Zuordnung, Schreibpuffer bis Schließen (große `.pst`/`.accdb` werden bei jedem Schließen komplett neu gespeichert), Metadaten-Tempo, FUSE im Container. |
| SFTP, FTP, S3, NFS, Python-SMB (`impacket`), schreibgeschützter Spiegel, eigener Sync-Client | Verworfen (Windows kann SFTP nicht einbinden, FTP unverschlüsselt, S3 ohne Umbenennen, NFS nur Pro, `impacket` nicht gehärtet, Sync-Client zu groß). rclone + WinFsp bleibt als Notlösung am Client. |
| ONLYOFFICE im Browser statt Desktop-Office vom Server | "Lokal öffnen" (Word/Excel) braucht WebDAV. **ONLYOFFICE-Zertifikat** ist heute nur auf einem Rechner vertraut; ohne Lösung ist der Branch für Word/Excel ein Rückschritt gegenüber `master`. JWT im Callback ist Pflicht, Rechteprüfung mit `check_access` (das heutige `onlyoffice_odoo` verwirft das Ergebnis von `has_access`). |

Prototyp-Code (`fm_proto`, `fmdav`, Testskripte) nur noch im Git-Tag `docs-vor-aufraeumen-2026-10-02`, Pfad `docs/prototypes/fm2/`.

## 4. Umwandler, Vorschau, OCR

| Entscheidung | Grund |
|---|---|
| **Eigener Umwandler-Container** (`tools/fmconverter`: ffmpeg, Ghostscript, LibreOffice, ExifTool, Tesseract, OCRmyPDF, Pillow+RAW+HEIC) (I11) | Fremde Formate gehören nicht in den Odoo-Prozess, der auch Buchhaltung und Rechte trägt. Cloudreve/FileRun/Nextcloud brauchen keinen, weil dort nichts davon im selben Prozess liegt. |
| Abgeleitete Daten (`int_filemanager.derivative`) im Blob-Speicher; Odoo liest sie nie, liefert nur aus | I13. Dauerhafte Warteschlange, gedrosselt, Sichtbares zuerst; zwei Bildgrößen (Kachel, Vorschau). |
| **Kein Zerstückeln langer OCR-Dokumente.** Der Umwandler antwortet bei über 15 s mit Auftragsnummer (`202`, `GET /convert/<id>`), Odoo fragt per Cron nach, gibt nach 40 min auf; Obergrenze 2000 Seiten | Alle geprüften Systeme (Cloudreve, FileRun, Nextcloud, Amazon/Google) trennen langsame Texterkennung per Abschicken und Abfragen, keines zerlegt. |
| OCR nur, wenn Text fehlt (< 20 Zeichen je Seite) oder ein Scanner-Text unsauber ist (`--redo-ocr`, ersetzt nur unsichtbaren Scanner-Text) | Sauberer Anteil bei Scans mit Scanner-Text 0,71 → 0,80. |
| Wortliste mit Positionen (Spec-Version; neue Spec löscht alte Ergebnisse und liest im Hintergrund neu) | Grundlage für Hervorhebung, Wortklick, Volltext. Neue Spec nur mit Eintrag in `server.py` `WORDS_SPECS`. Weißer Text auf weißem Papier (Maschinenmarken) wird nicht gelesen; Formularfelder werden gelesen (Text/Auswahl, nicht Ankreuzfelder; XFA nicht). |
| **Volltextsuche mit GIN-Trigram** auf `derivative.text` (kein tsvector, kein Elasticsearch) | tsvector findet `154989` nicht in `0154989`. Trigram: seltenes Wort 2 ms, Wort in 3 % der Dokumente 0,3–0,6 s, in 30 % 4,7 s (100.000 Texte). Wörter < 3 Zeichen nutzen den Index nicht. Zweiter Index für häufige Wörter nicht gebaut (offen). |
| `pg_trgm` per `pre_init_hook` + Migration | Odoo legt die Erweiterung nur in selbst erzeugten Datenbanken an; sonst fällt der Index still weg (Suche 13 s statt 6 ms). |

## 5. Werterkennung

| Entscheidung | Grund |
|---|---|
| **Werterkennung bleibt in Odoo** (Muster arbeiten nur auf dem fertigen Text), eigene Modelle (`extraction_field`, `extraction_rule`, `field_value`, `extraction_hint`) statt Erweiterung der bisherigen Modelle von `master` | Rechte, Herkunft, Fundstelle, Fassung und Lernen brauchen eigene Zeilen. |
| **Eigene Modelle als Grundlage plus echte Spalte je Katalogfeld** (N9) | Eigenschaftsfelder verworfen: keine Summen, keine Herkunft, Wertarten zu grob, Löschen einer Eigenschaft löscht alle Werte. Reine `x_`-Felder verworfen: ohne Herkunft/Lernen. Spiegel in Eigenschaften verworfen: doppelte Speicherung. Spalten nur vom System befüllt (Sperre in `write`/`create`), Archivieren blendet nur aus; die Spalte zeigt den Wert der aktuellen Fassung. Messung: Spalte an 1,4 Mio. Zeilen 2–3 ms. |
| **Vorschläge nur bei Bedarf berechnen**, nichts gespeichert (E2); ein Wert je Feld (E6) | Speichern erst, wenn eine Liste "ungeprüfte Eingänge" gebraucht wird (Eingangsordner). Linear: 100 Seiten ≈ 0,8 s, 1.000 ≈ 9 s. |
| **Erkennung allgemein** (E12): Beschriftung-Wert-Paare nach Layout aus allen Richtungen, unscharfe Zuordnung wie `base_import`, **Lernen pro Absender**; lokales KI-Modell erst, wenn die Quote nicht reicht | Stichwort für Stichwort skaliert nicht. Tower: i7-4770K, 16 GB, keine GPU, ein kleines Modell bräuchte 0,5–3 min je Dokument. Einstellungen **nur als allgemeine Regeln**, nie für ein einzelnes Dokument. |
| Stichwort-Modus für eigene Felder, Regex nur für Sonderfälle (E8) | Ein Nicht-Programmierer muss Felder anlegen können. |
| Eigene Firmendaten (IBAN, USt-IdNr., Mail einer eigenen Firma) werden übersprungen (E10); getrennte Felder je Belegart im Startkatalog (E11); IBAN ohne Beschriftung nicht vorschlagen, USt-IdNr. ja | Probeergebnisse am echten Bestand. |
| **Keine automatische Übernahme ohne Prüfung** (E7). Später per Schalter je Absender, nur mit dem Eingangsordner, nur wenn jeder gemerkte Kasten gefunden und jeder Wert eindeutig gelesen ist; Vermerk "automatisch übernommen" + Filter "automatisch, nie angesehen" | Prüfung bleibt Standard. |
| Messung am echten Bestand: **Übungsteil (Einstellen) und Prüfteil (erst am Ende messen) nach Absendern getrennt**; Ergebnis Übungsteil 86 % richtig / 88 % gefunden; Prüfteil bewusst unverbraucht | Quote des Prüfteils gilt als Erwartung für neue Dokumente. Private Daten nur auf Tower, nie ins Repo. |
| Prüfziffern/Lesefehler-Reparatur (O→0, I→1 …) nur bei IBAN/USt-IdNr.; IBAN-Prüfung über Modulo 97 | `stdnum.iban` ist in Odoo wegen Odoos eigenem Import-Haken nicht ladbar. |
| Katalogfelder anlegen: nur Verwalter; "Feld vorschlagen" für alle (U2); gelernte Beschriftungen für alle Nutzer (U3) | Wertart wählt jemand, der die Folgen kennt. |
| Dokumentarten **später** entscheiden, nach einigen Wochen Nutzung (U4) | Zuerst Feldliste aus Funden, Absender-Gedächtnis und angehefteten Feldern. |
| QR (Überweisung) jetzt bauen, überstimmt Gedrucktes nicht (N2) | Nur 2 von 513 privaten Dokumenten tragen einen. |
| Bilder: "Text erkennen" auf Wunsch, automatisch später je Ordner, nie für alle Bilder (U6) | ~209.000 Fotos. |
| Prüfstatus (ungeprüft/geprüft/automatisch) getrennt vom Freigabestatus; Pflichtfelder erst mit Dokumentarten (N4) | – |
| Häkchen "daraus nicht lernen"; Verwalter-Übersicht des Gelernten; **kein** verzögertes Umlernen (N5) | Nachvollziehbarkeit. |
| Ablageregeln je Absender mit Platzhaltern erst mit dem Eingangsordner (N7); Feldtypen Verknüpfung, Ankreuz, Auswahl, Telefon, Prozent, Monat, Hilfetext/Standardwert (N8) | Vorher kaum anwendbar, weil vorhandene Dateien schon richtig liegen. |
| **Nicht**: Priorität, Datei, Bild, Signatur, formatierter Text, Stichwörter je Feld; Tabellen außerhalb (E6); Einzeichnen von Feldern auf dem PDF | – |

Offene Fragen aus dem Entwurf (Rechte/Leistung): Was zählt als "ungeprüft"; Dauern in Wochen und Mengen mit abweichender Einheit nicht
in die Spalten spiegeln; Einheit eines Mengenfelds sperren, sobald Werte da sind (Empfehlung jeweils: ja, nur ausdrücklich Geprüftes, ja).
Befund: Nutzer haben Schreibrecht auf den ganzen Knoten, deshalb brauchen die "nur vom System befüllt"-Spalten eine Sperre in `write`.

## 6. Oberfläche

| Entscheidung | Grund |
|---|---|
| **Neue Oberfläche parallel** (`static/src/int_filemanager/v2/`) auf `int_filemanager.node`; die bisherige Oberfläche (`native_ui/`) bleibt bis zur Übernahme und wird dann **gelöscht** | Modul bleibt nach jedem Schritt installierbar. |
| **Nichts Neues im Frontend, was Odoo kann**: native list/kanban/form/search; Eigenbau nur für Ordnerbaum (Odoo hat keine Baum-Seitenleiste), Chunk-Upload, Kontextmenü | – |
| Alles Schreibende über Modellmethoden (`create_file`, `rename_or_move` …) mit Vorgangsnummer, nie `write()` aus dem Browser | I9. |
| Frontend **nicht per Browser-Automatik testen** (Nutzerregel); Server mit Odoo-Tests und Echtprozess-Skripten, Frontend per eslint/prettier und **freiem Nutzertest** | – |
| **Prüf-Fenster entfällt** (2026-10-01). Stattdessen Rechtsklick → **Eigenschaften**: natives Odoo-Formular am Knoten, links Name/Status/Tags/Kontakt und erkannte Werte, rechts Vorschau; Werte als Feld `values_json` (Compute = `suggest_field_values`, Inverse = `apply_field_values`), damit der normale Speichern-Knopf geht | Der Nutzer sah das Prüf-Fenster: "sieht nicht nach Odoo aus". Formular bringt Pager, Speichern-Kürzel, Chatter, Handy-Verhalten mit. Frühere Entscheidung (eigene Client-Aktion, 2026-09-30) ist damit überholt. |
| **Odoos pdf.js-Viewer mit Überlagerung** statt eigener Leinwand; Umrandung per `MutationObserver` neu einhängen | pdf.js entfernt fremde Kinder einer Seite beim Neuzeichnen; Zoom auf den Wert per pdf.js-Ziel `FitR`. Odoo 19 Community hat keine `--bs-*`-Farbvariablen zur Laufzeit: Farben über Klassen `text-action`/`text-muted`. |
| Wortklick: Eintrag "Im Dokument wählen …" in der Feldliste, Wortmodus mit Hinweisband, Esc; nicht ein Kasten aufziehen | PaperOffice wählt Werte per Klick aus einer Textschicht. |
| Feldnamen über den Umrandungen per Schalter (N10); nur die aktive Stelle kräftig (N6); Brotkrumen Odoo-Art "Dateien › Name" (N11); Alt-Kürzel Alt+N/P/S/J (N12) | Odoo-Abgleich am Quellcode. |
| Volltextsuche (U-1) ohne zweiten Index für häufige Wörter; alte Wortlisten bleiben bis zum Ersatz | – |
| Offen: Mindestlänge Suchwörter; Dublette-/Plausibilitätshinweise (Katalogfelder brauchen feste Bedeutung) | – |

## 7. Prozess

| Entscheidung | Grund |
|---|---|
| Zuerst vollständig durchplanen, **keine Zeile Modul-Code vor Freigabe** (erteilt 2026-09-27); Prototypen auf der Testinstanz erlaubt | – |
| Je Schritt: pre-commit, `test_lint`, odoo-ls ohne Befund im eigenen Code, `de.po` vollständig, Gegenlese per zweitem Modell, Abnahme je Schritt | – |
| **Commit erst auf Ansage**; Test-Instanz ohne Rückfrage aktualisieren | Arbeitsweise des Nutzers. |
| Ursachen im Code mit Test beheben, keine Handeingriffe in DB oder Container | – |
| Zusatzpunkte aus dem externen Review (Import-Manifest, Outbox-Regel, B-Invarianten, Versionen festnageln) **nicht** aufgenommen (2026-09-27) | – |
| Prüfautomatik: pre-commit nur für neuen Code (OCA-Vorlage), `test_lint` und odoo-ls auf Tower; keine GitHub Action | Details `pruefautomatik_2026-10-02.md`. |

## 8. Odoo-19-Fallen (gemessen oder im Quellcode belegt)

- **JSON-2:** Jede öffentliche Methode (kein `_`, nicht `@api.private`) ist für jeden angemeldeten Nutzer per API-Schlüssel aufrufbar. Öffentlich ist nur, was mit beliebigen Argumenten sicher ist; lesende Methoden mit `@api.readonly`. `/xmlrpc` und `/jsonrpc` sind veraltet (Entfernung Odoo 22).
- **Rechte:** Jede Tabelle braucht eigene Regeln; Odoo überträgt Ordnerrechte nicht auf Versionen und Inhalte. `call_kw` erreicht jede öffentliche Methode.
- **API-Schlüssel:** Prüfung `scope IS NULL OR scope = angefragt`; Nicht-Admins brauchen ein Ablaufdatum bis `api_key_duration` ihrer Gruppe (Standard 1 Tag).
- **`retrying()`** wiederholt keine Namenskonflikte und keine belegten Sperren (siehe 2).
- **Datenbank:** `pg_trgm` nur in selbst erzeugten DBs; C-Kollation (siehe 2).
- **Odoo-Image:** Das Test-Image `odoo:19.0-hm-test` (19.0-20260908) enthält den Sicherheits-Fix `97e3d6152d`; das Live-Tag `odoo:19.0-hm` (20260817) nicht.
- **Verknüpfung mit Geschäftsobjekten** überschreibt `_check_access` und `_search` (wie Odoos `mail.activity`); die Ordnerrechte selbst laufen über normale Regeln. Odoo-Updates nur nach grünem Testlauf auf der Testinstanz.
- **Zwei Knotenfelder** tragen dieselbe Bezeichnung "Created on" (`create_date`, `mtime`).
- `odoo shell`/`odoo -u` gegen die Watcher-DB startet einen zweiten Watcher; Workaround: `int_filemanager.watcher_enabled` vorher auf `false`.
