# Übergabe: int_filemanager 2 – Stand und nächste Schritte

Stand 2026-09-26, ergänzt 2026-09-27 (Code-Prüfung eingearbeitet, Konzept freigegeben), **2026-09-28: Schritt 3
und 4a fertig, 4b (Oberfläche) gebaut** und **2026-09-29: Schritt 5 (Vorschau, Text, Metadaten, OCR mit
Wortpositionen) im Server/Datenmodell fertig, noch ohne Oberfläche** – **für eine neue Sitzung: Abschnitt 4.0 zuerst
lesen, das ist der aktuelle Stand und die nächste Aufgabe.** Der Rest von Abschnitt 4 ist Verlauf (Schritt-4-Themen,
schon erledigt). Für eine neue Sitzung sonst: zuerst dieses Dokument, dann Kern und Konzept lesen. **Gearbeitet wird
auf dem Branch `feature/int-filemanager-v2`** (master = Stand `int_filemanager-v1` plus Dokumente).

## 1. Worum es geht

`int_filemanager` wird neu aufgebaut: **Dateimanager vollständig als Odoo-Addon, Odoo ist alleiniger Schreiber**,
Dateiinhalte liegen in einem **eigenen, inhaltsadressierten Blob-Speicher**. Odoo-Bausteine werden genutzt, selbst
gebaut wird nur, wo Odoo nachweislich begrenzt ist. Der Bestand wird **kopiert** (kein Hardlink).

**Maßgebliche Dokumente (in dieser Reihenfolge lesen):**
0. `docs/int_filemanager_v2_kern_2026-09-26.md` – **Kurzfassung** (Regeln, Aufbau, Funktionen zum Start,
   Entscheidungen, Reihenfolge mit Abnahmekriterien); **am 2026-09-27 freigegeben**.
1. `docs/int_filemanager_v2_konzept_2026-09-26.md` – Konzept: Invarianten I1–I12, Datenmodell, Schreibwege,
   Migration, Testplan, offene Entscheidungen (17), Reihenfolge (18), **Prototyp-Ergebnisse (19, WebDAV: 19.4)**.
2. `docs/int_filemanager_konzept_db_vorrang_2026-09-24.md`, Abschnitte **19 und 20** – Live-Prüfungen auf Tower,
   die zur Entscheidung geführt haben (Fehlerbilder des heutigen Moduls, Odoo-Core-Befunde, SMB-Verhalten).
3. `docs/review/konzept_codepruefung_2026-09-26.md` – Code-Prüfung des Konzepts (194 Behauptungen mit Beleg,
   Befunde A1–A21); seit 2026-09-27 in Konzept und Kern eingearbeitet.
4. `CLAUDE.md` (Repo-Wurzel) – Regeln: vor "kein Bordmittel" den Odoo-Core prüfen; Claims verifizieren;
   Produktentscheidungen beim Nutzer.

**Nicht verfolgte Alternative:** Verbindung von `web-filemanager` mit Odoo, geprüft und dokumentiert in
`web-filemanager/docs/plans/odoo-integration.md` (als "nicht verfolgt" markiert).

## 2. Entscheidungen des Nutzers

| Datum | Entscheidung |
|---|---|
| 2026-09-26 | Dateimanager vollständig als Odoo-Addon; Eigenbau nur, wo Odoo begrenzt ist |
| 2026-09-26 | Odoo ist alleiniger Schreiber (kein SMB-Schreibzugriff auf die Dateien) |
| 2026-09-26 | Migration per **Kopie**, kein Hardlink |
| 2026-09-25 | Testumgebung auf Tower **behalten** (nicht löschen ohne Rückfrage) |
| 2026-09-26 | Test mit echtem Word/Excel **entfällt** |
| 2026-09-26 | Explorer-Zugriff: **Option A, WebDAV-Netzlaufwerk** (Konzept 11, 19.4) |
| 2026-09-26 | Migration: **ganzer Share**; Versionen **unbegrenzt**; Papierkorb **30 Tage** (Konzept 17.1–17.4) |
| 2026-09-26 | WebDAV-Bauform, falls WebDAV: **eigener Odoo-Befehl `odoo fmdav`** (Konzept 11.2, 19.10) |
| 2026-09-26 | **Start ohne Explorer-Zugriff** (Odoo-Oberfläche, ONLYOFFICE im Browser) **plus Eingangsordner**; Netzlaufwerk (WebDAV oder SMB über Odoo-FUSE) später nach Nutzung entscheiden (Konzept 11, 17.1/17.7) |
| 2026-09-26 | Code nach den Odoo-/OCA-Konventionen (`docs/odoo_konventionen_2026-09-26.md`): **Englisch** in Namen, Kommentaren, Docstrings, Log-Meldungen und Commits (`[TAG] modul: …`); Oberflächentexte englisch im Code, deutsche Übersetzung in `i18n/de.po`. Prüfwerkzeuge: **pre-commit** nach OCA-Vorlage (nur für neuen Code), Odoos **`test_lint`** und **odoo-ls** (Parse-Modus) auf der Testinstanz; **keine** GitHub Action; Migrationsskripte mit **`odoo/upgrade-util`** |
| 2026-09-26 | Modellnamen mit Modulpräfix `int_filemanager.*` (Konventionen, `docs/odoo_konventionen_2026-09-26.md`) |
| 2026-09-26 | Rechte-Bereiche **minimal** ("Alle" + heutiger Schutzordner); **HM-SRV bleibt vorerst beim heutigen Modul** (17.5, 17.6) |
| 2026-09-27 | Eingangsordner: Datei gilt nach **2 Minuten** ohne Änderung als fertig; ZIP-Download bis **ca. 500 MB** direkt, darüber Hintergrundjob; Blob-Speicher auf **disk2 + disk3** (Konzept, Entscheidungen 6–8) |
| 2026-09-27 | Kern-Änderungen aus der Code-Prüfung übernommen; Zusatzpunkte aus dem externen Review (Import-Manifest, Outbox-Regel, B-Invarianten, Versionen festnageln) **nicht** aufgenommen |
| 2026-09-27 | **Konzept und Kern freigegeben.** Umsetzung **im Modul `int_filemanager`** (19.0.2.0.0) auf Branch `feature/int-filemanager-v2`, heutiger Stand als Tag `int_filemanager-v1`; Test-Image `odoo:19.0-hm-test` (Live-Tag unberührt); pre-commit auf dem Arbeitsrechner (Konzept, Entscheidungen 9–10) |
| 2026-09-28 | **Schritt 5 festgelegt** (Konzept 8, 9, Entscheidungen 11–15): abgeleitete Dateien im eigenen Blob-Speicher statt `ir.attachment` (Prüfung des Odoo-Cores: Odoo dekodiert Anhänge an vielen Stellen selbst), Mischform bei der Erzeugung, zwei Bildgrößen, Werterkennung in Odoo, Umfang = Kern, Erweiterungen später |
| 2026-09-28 | Kommentare und Docstrings **ohne Verweise auf Dokumente** (keine Kürzel `I…`/`A…`, keine Konzept-Abschnitte), Docstrings kurz wie im Odoo-Kern; ersetzt die Hausregel "Grundregeln benennen" (Konventionen Abschnitt 3); Zuordnung Grundregel → Test nur noch im Konzept 16.1 |
| 2026-09-28 | Dateityp (`node.mime`) wird beim Anhängen jeder Fassung (Upload, neue Fassung, Wiederherstellen) aus den ersten Bytes erkannt statt aus der Endung – schließt eine Lücke aus Konzept 8.3; Option A von drei geprüften Wegen |
| 2026-09-29 | **OCR/Werterkennung volle Ausbaustufe** (Wortpositionen für spätere Hervorhebung, wie v1s Phase A–C), aber **erst Server/Datenmodell, ohne Oberfläche** – modularer Baustein, Anbindung an den Explorer folgt als eigener, späterer Schritt. Gilt auch für Vorschau-PDFs aus Office-Dateien, nicht nur echte PDFs (Erweiterung gegenüber v1) |
| 2026-09-29 | **Kein Zerstückeln langer OCR-Dokumente in Seiten-Häppchen.** Nach Prüfung von Cloudreve (Quellcode), FileRun, Nextcloud und Amazons/Googles eigenen Umwandler-Diensten: alle trennen langsame Texterkennung vom schnellen Pfad durch **asynchrones Abschicken und Abfragen**, keines zerlegt ein Dokument. Der Umwandler antwortet bei einer Umwandlung über 15 Sekunden sofort mit einer Auftragsnummer statt zu blockieren; Odoo fragt bei späteren Cron-Durchläufen nach. Ein Dokument ist eine Arbeitseinheit, egal wie lange es dauert (Obergrenze 2000 Seiten als Notbremse) |
| 2026-09-29 | **Umwandler bleibt eigener Container**, aber nicht weil das der verbreitete Standard wäre (Cloudreve/FileRun/Nextcloud brauchen dafür keinen eigenen Container) – sondern weil Odoo, anders als diese Systeme, im selben Prozess auch Buchhaltung und Rechte verwaltet |

Vorgabe des Nutzers für den Umbau: **erst vollständig durchplanen, keine Zeile Modul-Code vor Freigabe des
Konzepts.** Prototypen auf der Testinstanz sind erlaubt. **Freigabe von Konzept und Kern erteilt am 2026-09-27.**

## 3. Erledigt

| Was | Ergebnis | Ort |
|---|---|---|
| Live-Prüfung der offenen Punkte (DB-Vorrang) | Abschnitte 19/20 des DB-Vorrang-Konzepts | Commits `3b6b522`, `f695f5e` |
| Konzept int_filemanager 2 | Abschnitte 1–18 | Commit `22332b3` |
| Prototyp Blob-Speicher, Upload in Stücken, `x_sendfile`, Kopierrate | Abschnitt 19 des Konzepts; alles bestanden | Commit `81c232f` |
| Prototyp-Code und Testskripte archiviert | `docs/prototypes/fm2/` (siehe 5) | Commit `57ffd83` |
| **WebDAV im Odoo-Prozess** (Nachprüfung 19.6, Prototyp 19.7) | Strom in Odoo-Route lesbar, 25-ms-Grundlast war Konfiguration; WsgiDAV hinter Odoo-Route: litmus 100 %, schneller als der Dienst, eigener Odoo-Prozess für `/dav/` nötig | `fm_proto/dav_inproc.py` |
| **WebDAV-Prototyp (Explorer-Zugriff, Konzept 11 A)** | Abschnitt 19.4 des Konzepts; litmus 100 %, Windows-WebClient, LibreOffice, Identitätsregel für Word/Excel-Speichermuster | `docs/prototypes/fm2/fmdav/`, `fm_proto/dav.py` |
| **Code-Prüfung des Konzepts** (2026-09-26/27) | 194 Behauptungen gegen Odoo 19 geprüft, 21 Befunde; hoch: Regeln für Neben-Modelle (A1), `call_kw` (A2), `retrying()` wiederholt keine Namens-/Sperrkonflikte (A3), Aufräumjob-Wettlauf (A4); in Konzept (u. a. 2, 4–6, 12, 16, 19.17) und Kern eingearbeitet; Plattengrenzen-Test für disk2 + disk3 bestanden | `docs/review/konzept_codepruefung_2026-09-26.md` |
| **Schritt 3 Fundament** (2026-09-27) | Datenmodell (Knoten, Revision, Blob, Bereich, Upload, Vorgang), Blob-Speicher, alle Schreibwege, Rechte; Tests für A1–A4 zuerst; Wettlauf- und Absturzszenarien mit echten Prozessen auf Tower grün (`tools/v2check/race.sh`), dabei zwei echte Fehler gefunden und behoben (`sudo` bei kaltem Cache, Verschieben gegen Löschen) | Commits `c0cf442` … `7f06431` |
| **Schritt 4a Server** (2026-09-28) | Ordnerbaum, Download (Rechte, Range, `x_sendfile`), Upload in Stücken mit Fortsetzen, ZIP direkt/als Job, Papierkorb-Frist, Freigabe-Links und Kundenportal; Abnahme **3 GB mit Abbruch und Fortsetzen** auf Tower bestanden | Commits `af0c9fc` … `55549be` |
| **Schritt 4b Oberfläche gebaut** (2026-09-28) | Explorer auf `int_filemanager.node` (Liste, Kacheln, Baum, Breadcrumb, Uploads, Kontextmenü, Tastatur, Verschieben/Kopieren/Drag & Drop, Versionen, Freigabe-Dialog, Details-Dialog), Upload-Logik mit 45 Node-Tests, `de.po` vollständig; **Handtest und Abnahme offen** | Commits `78f8e99`, `8279772`, `27b2a11`, `01e5793` |
| **Kommentare bereinigt** (2026-09-28) | Verweise auf Dokumente entfernt, Docstrings gekürzt; nur Kommentare geändert (AST-Vergleich), 305 Odoo-Tests + 45 Node-Tests grün auf HM-SRV | Commit `d0d5c94` |
| **Schritt 4 Nacharbeiten** (2026-09-28) | Drei Fehler aus dem ersten Handtest behoben: Basis-Fassung beim Herunterladen merken, abgelehnte Uploads zählen nicht als unterbrochen (Verwerfen-Knopf), Windows-verbotene Dateinamen | Commits `fc84ff5`, `0515672`, `735abc4` |
| **Dateityp aus dem Inhalt** (2026-09-28) | `node.mime` und `blob.mime` werden aus den ersten 2048 Bytes erkannt (libmagic), bei jeder neuen Fassung neu; HTML wird beim Download immer als Text ausgeliefert (Absicherung); 10 neue Tests | Commit `6daf929` |
| **Schritt 5 Umwandler: alle Formate außer OCR** (2026-09-28) | Eigener Container `tools/fmconverter` mit allen Werkzeugen (ffmpeg, Ghostscript, LibreOffice, ExifTool, Tesseract, Pillow+RAW+HEIC); Kacheln/Vorschauen für alle Bildformate des Bestands (inkl. MPO, HEIC, TIFF, RAW), Video-Standbild, PDF-Seite+Text+Metadaten, Office über eigenes Vorschau-PDF, Audio-Cover, Textdateien, Metadaten (EXIF/ffprobe/pdfinfo); Auftragskette mit Abhängigkeiten (`depends_on_id`); Kacheln in Liste/Kacheln-Ansicht des Explorers; 279 Umwandlungen an den 95 echten Testdateien, 0 unerwartet | Commits `5c4d090` … `f177660` |
| **Schritt 5 OCR mit Wortpositionen, asynchron** (2026-09-29) | Neue Auftragsart `words` ersetzt `text` für PDFs (echt und aus Office): liest zuerst die eingebettete Textebene (`pdfplumber`), bei Scan-Verdacht läuft `OCRmyPDF` über das ganze Dokument, dann wieder `pdfplumber` für Text und Wortpositionen zusammen; Ergebnis liegt wie eine Vorschau im Blob-Speicher. Umwandler antwortet bei über 15 Sekunden Dauer mit einer Auftragsnummer statt zu blockieren (`202` + `GET /convert/<id>`), Odoo fragt bei späteren Cron-Durchläufen nach (`_poll_running_jobs`), gibt nach 40 Minuten als gewöhnlichen, wiederholbaren Fehlschlag auf. Echter Test auf Tower: ein 300-Seiten-Scan mit echtem Bildrauschen läuft korrekt durch `running` → `done`, nur einmal abgeschickt. Noch **ohne** `extraction_pattern`/`extracted_value` (Werterkennung) und ohne Oberfläche | Commits `3e01332`, `09c8ca7`, `3f42304` |

**Wichtigste Prototyp-Befunde (Details: Konzept 19):**
- Blob-Speicher, Upload in 4-MB-Stücken, Fortsetzen, Idempotenz, Deduplizierung, Absturzsicherheit und Aufräumjob
  funktionieren; Auslieferung über nginx per `x_sendfile` mit Range und ETag.
- **Odoo gibt den rohen Request-Strom nicht heraus** (`http.py:1480-1510`): jeder Body liegt ganz im RAM →
  Upload in Stücken zwingend; **WebDAV-`PUT` großer Dateien ist im Odoo-Prozess nicht sauber machbar**.
- Worker-Speicher wächst bei großen Bodies (Allokator, kein Python-Leck); Odoo recycelt Worker über
  `limit_memory_soft`.
- `finish` großer Dateien dauert lange (3 GB: ~51 s) → Hintergrundjob vorsehen.
- `fields.Integer` ist `int4` → Dateigrößen nicht als Integer speichern.
- Kopierrate 27,5 MB/s (55 GB, 62.886 Dateien, 0 Fehler, Stichprobe 300/300 korrekt) → ca. 18 h für 1,8 TB.

**WebDAV-Prototyp (Details: Konzept 19.4):** WebDAV-Dienst neben Odoo (WsgiDAV als Protokollschicht), der nur
übersetzt und mit dem API-Schlüssel des Nutzers (`auth='bearer'`) Odoo aufruft; Odoo bleibt alleiniger Schreiber.
- litmus 100 % (basic, copymove, props, locks, http); Windows-WebClient als Netzlaufwerk funktioniert (Umlaute,
  Ordner, Papierkorb); LibreOffice speichert per `PUT` auf dieselbe Datei.
- **Identitätsregel** für "Temp schreiben → Original wegbenennen/löschen → Temp umbenennen" (Word/Excel) hält Knoten-ID
  und Versionen; Temp-Knoten werden restlos entfernt.
- Tempo: kleine Dateien 0,28 s je Datei (Odoo-Grundlast ~25 ms je Request, WebClient 8 Requests je Datei); große
  Dateien streamen mit konstantem Speicher (3 GB: `PUT` 90 s, davon 46 s Hash-Prüfung; `GET` 11 s).
- Offen: Windows braucht HTTPS mit vertrautem Zertifikat (Basic nur über HTTPS) und eine angehobene Download-Grenze
  (Standard 50 MB); Namen müssen ohne Groß/Klein eindeutig werden; Sperren in Odoo speichern.

## 4. Nächste Schritte

### 4.0 Aktueller Stand (2026-09-29) – hier weitermachen

Schritt 5 (Konzept Abschnitt 8/9, Kern Reihenfolge Punkt 5) ist **im Server/Datenmodell fertig, ohne Oberfläche**:
Kacheln/Vorschauen für alle Formate, Text und Metadaten, dazu OCR mit Wortpositionen für später geplante
Hervorhebung – siehe die beiden neuesten Zeilen in Abschnitt 3. Getestet (Stand W-1): 400 Odoo-Tests, 16 echte
Prozess-Szenarien auf Tower (`tools/v2check/race.sh`, nach W-1 nicht erneut gelaufen), 55 Umwandler-Tests, alle grün.
Nichts davon ist an eine Explorer-Ansicht angebunden außer den fertigen Kacheln (Liste/Kacheln-Ansicht) und dem
Öffnen der großen Vorschau für TIFF/HEIC/RAW/Office im Viewer.

**Offen, in dieser Reihenfolge:**

1. **Werterkennung** (Konzept 9, Entscheidung 14 "Werterkennung bleibt in Odoo"), noch **ohne** Oberfläche.
   **Maßgeblich ist der Plan `docs/int_filemanager_v2_werterkennung_plan_2026-09-29.md`** (Recherche Odoo 19 und
   Paperless-ngx, 4 Proben an echten Dokumenten, Scheiben W-1…W-6). **Entscheidungen E1–E9 vom Nutzer freigegeben
   (2026-09-29, „dann leg los“)**; Plan-Abschnitt 4 geändert: **eigene neue v2-Modelle** statt Erweiterung der
   v1-Modelle (Gründe dort).

   **Stand 2026-09-29 abends – hier weitermachen:**
   - **W-1 fertig** (Wortliste v2, neue Texterkennung für Scans mit Scanner-Text, Spec-Wechsel-Fehler in
     `_enqueue_missing` behoben, Text in `derivative.text`): 55 Umwandler-Tests, **400 Odoo-Tests** grün, pre-commit
     grün; Einzelheiten Plan Abschnitt 6 „Stand W-1“. Image `fmconverter:dev` auf Tower ist neu gebaut (enthält v2);
     der laufende Container `fmv2_ui_conv` (UI-Testinstanz) nutzt noch das **alte** Image – bei Bedarf neu erstellen.
   - **Lauf der Wortliste über die ganze Sammlung ausgewertet** (Plan 6 „Stand W-1“): 513 PDFs, 0 Fehler, 0 kaputte
     Zeichenbereiche; bei den 73 neu erkannten Scans mit Scanner-Text sauberer Anteil 0,71 → 0,80 (57 besser,
     8 schlechter – bei W-6 ansehen). Container `wk_runall` entfernt; Wortlisten liegen weiter in
     `/mnt/user/test/werterkennung_words/` (`chmod 700`, persönliche Texte – nie ins Repo).
   - **W-2 fertig** (Datenmodell, Plan 6 „Stand W-2“): `int_filemanager.extraction_field`, `.extraction_rule`
     (Stichwort- und Regex-Modus), `.field_value` mit typisierten Spalten, Rechte (Werte nur lesen entlang des
     Knoten-Bereichs, niemand schreibt sie über das ORM), Startbelegung (21 Felder, `noupdate`), `de.po`;
     Modulversion 19.0.1.16.0.
   - **W-3 fertig** (Plan 6 „Stand W-3“): `int_filemanager/value_types.py` findet und prüft Werte je Art ohne
     Datenbank (`find`/`parse`), mit Reparatur von Lesefehlern nur bei Prüfziffer-Arten. Befund: `stdnum.iban` ist in
     Odoo wegen Odoos eigenem Import-Haken nicht ladbar – IBAN-Prüfung deshalb über `numdb.read` + Modulo 97.
   - **W-4 fertig** (Plan 5a und 6 „Stand W-4“, Nutzerentscheidungen E10–E12): allgemeine Erkennung über
     Beschriftung-Wert-Paare aus allen Richtungen und unscharfe Zuordnung wie `base_import`
     (`int_filemanager/value_suggest.py`, `node.suggest_field_values`), eigene Firma übersprungen, Absender und Tags;
     Startkatalog 27 Felder (Geschäftsbelege); Umwandler liest Fettdruck einmal (Spec `v3`). Neue Wortlisten der
     Sammlung: `/mnt/user/test/werterkennung_words_v3/` (Aufruf siehe `docs/prototypes/werterkennung/README.md`).
   - **W-5 fertig** (Plan 6 „Stand W-5“): `node.apply_field_values` (Schreibrecht, aktuelle Fassung, jeder Wert neu
     gelesen, je Feld ersetzen, Kontakt/Tags, Notiz), Lernen pro Absender (`int_filemanager.extraction_hint`, Beschriftung
     vom Server aus der Wortliste abgeleitet), **N1 in v2 zu** (Test über `call_kw` und JSON-2). Version 19.0.1.17.0.
   - **W-6 läuft – Runde 1 von 4 fertig** (Plan 6 „Stand W-6“): Übungsteil 10 Dokumente, 84 % der bewerteten Vorschläge
     richtig, ≈ 81 % der vorhandenen Werte gefunden; vier allgemeine Befunde notiert, noch nicht umgesetzt.
   - **Vor Runde 2 erledigt (2026-09-29, Plan 6 „Stand W-6 vor Runde 2“):** Befund 1 (Stichwort nur am Wortende, ≥ 30 %,
     ≤ 3 Wörter danach, Beschriftung vor dem Wert nach der letzten Zahl, keine einstelligen Nummern) und Befund 3
     (USt-IdNr. ohne Beschriftung; **IBAN nicht**, Nutzerentscheidung) umgesetzt, 491 Tests grün; **Befund 2
     (Anschriftenfeld) auf Nutzerwunsch zurückgestellt**. Runde 1 automatisch nachgeprüft (`w6_recheck.py 1`):
     84 % → 90 %, nichts Richtiges falsch geworden. Vorschläge neu berechnet, Seite Runde 2 gebaut
     (`%TEMP%\w6r2\werterkennung_runde2.html` auf dem Arbeitsrechner, Übungsdokumente 11–20).
   - **Einstieg neue Sitzung – Runde 2 auswerten:** sobald der Nutzer gespeichert hat, `werterkennung_runde2.json` aus
     Downloads als `runde2.json` nach Tower (`/mnt/user/test/werterkennung_w6/`), lokale Kopien (Downloads,
     `%TEMP%\w6r2`) löschen; Zahlen wie Runde 1, Befunde notieren, als allgemeine Regeln umsetzen, dann
     `w6_recheck.py 1 2`. Runde 3 = Übungsdokumente 21–24 + ggf. Nachschärfen, **Runde 4 = Prüfteil (16 Dokumente,
     `check`) erst ganz am Ende, ohne danach etwas einzustellen** – deren Quote ist die ehrliche Erwartung für neue
     Absender (ohne und mit Lernen messen).
   - Im Downloads-Ordner des Nutzers liegen noch `werterkennung_runde1*.json` (10 Zwischenstände, private Werte) – der
     Nutzer löscht sie selbst; die maßgebliche Fassung liegt auf Tower.
   - Prototyp-Skripte (ohne persönliche Daten): `docs/prototypes/werterkennung/` mit README.
2. **Testdateien je Format sammeln** (Konzept 18, Schritt 5a) ist durch `/mnt/user/test/formats` auf Tower und
   `tools/fmconverter/run_formats.py` bereits erledigt (95 echte Dateien, `MANIFEST.tsv`). **Für die Werterkennung**
   liegt seit 2026-09-29 eine eigene Sammlung echter privater Dokumente des Nutzers unter
   `/mnt/user/test/werterkennung/` auf Tower (528 Dateien, 531 MB, davon 513 PDFs: Immobilie/Rechnungen und Finanzen
   mit Versicherungen, Hausnebenkosten, Gehalt, Steuer, Bank, Rente/Krankenkasse; Quelle `G:\Meine Ablage\Privat`,
   ohne `.pfx`-Zertifikate und `.gsheet`-Verknüpfungen). Nur root (`chmod 700`), keine Freigabe; **niemals ins Repo,
   nicht in Berichte mit persönlichen Daten**. Sollwerte je Dokument (W-6) fehlen noch. Abgeleitete Wortlisten:
   `/mnt/user/test/werterkennung_words/` (ebenfalls `chmod 700`, Skripte in `_tools/`).
3. **Erst danach, als eigener Schritt:** der Hervorhebungs-Viewer (v1s Phase C – eigener `pdf.js`-Renderer mit
   Markierungs-Kästen) und alles, was Schritt 5 in den Explorer einhängt (Kontroll-Dialog, „Werte erkennen"-Knopf).
   Bewusst zurückgestellt, damit Server/Datenmodell zuerst geprüft feststehen (Nutzerentscheidung 2026-09-29).
4. Danach wie im Kern (Abschnitt 11) vorgesehen: Schritt 6 (Office/ONLYOFFICE), Schritt 7 (Eingangsordner),
   Schritt 8 (Übernahme des Bestands) – siehe Punkt 10 unten für schon gesammelte Vorüberlegungen dazu.

**Offene Kleinigkeiten aus Schritt 5, nicht blockierend:**
- Verwalter-Werkzeuge (Diagnose je Datei, Liste fehlgeschlagener Umwandlungen, „neu erzeugen", Konfiguration der
  Bausteine, Konzept 8.6) sind noch nicht gebaut.
- Das Nachholen des ganzen Bestands (Kacheln für 209k vorhandene Bilder usw.) ist nur gedrosselt über die
  Warteschlange vorgesehen, noch nicht mit echtem Bestand durchgemessen – nur Hochrechnungen aus Stichproben.
- Das Umwandler-Docker-Image ist nur auf Tower gebaut (`fmconverter:dev`), noch nicht Teil eines Deployment-Wegs.

**Alter Verlauf ab hier** (Schritt-4-Abnahme, WebDAV, Migrationsvorbereitung – zum großen Teil erledigt):

1. ~~Test mit echtem Word/Excel~~ – **entfällt** (Nutzerentscheidung 2026-09-26). Falls später doch: IP des
   Office-Rechners in `FM_DAV_ANON_IPS` (`/mnt/user/appdata/fmtest/fmdav/env`), `fmv2_dav` neu erstellen, dort
   `net use W: http://192.168.188.67:8082/`, `.docx`/`.xlsx` zweimal speichern, Knoten/Revisionen in `fmv2` prüfen.
2. ~~Entscheidung Explorer-Zugriff~~ – **erledigt:** Start ohne Netzlaufwerk plus Eingangsordner; WebDAV-Bauform
   `odoo fmdav` vorbereitet, SMB über Odoo-FUSE als Alternative (ohne Prototyp); Entscheidung später (Konzept 11, 17.7).
3. ~~Offene Entscheidungen des Nutzers~~ (Konzept 17) – **alle erledigt** (2026-09-26). Folgeaufgabe aus 17.6:
   Sicherheitslücke N1 im heutigen Modul beheben (HM-SRV läuft damit weiter).
4. ~~Konzept festschreiben~~ – **erledigt** (2026-09-26): Befunde aus 19 und Entscheidungen aus 17 in die Abschnitte
   3–7, 10–14, 16–18 eingearbeitet.
5. ~~Code-Prüfung einarbeiten~~ – **erledigt** (2026-09-27): Befunde A1–A21 in Konzept und Kern.
6. ~~Freigabe durch den Nutzer~~ – **erteilt** (2026-09-27).
7. **Schritt 3 (Fundament), erster Teil – erledigt** (2026-09-27, Branch `feature/int-filemanager-v2`):
   - Tag `int_filemanager-v1` (Stand für HM-SRV und Tower-Live), Branch angelegt.
   - Test-Image `odoo:19.0-hm-test` (19.0-20260908, mit Sicherheits-Fix); Live-Tag unberührt.
   - pre-commit nach OCA-Vorlage, nur für `int_filemanager` (`py -3.13 -m pre_commit run --files …`; der Git-Hook
     läuft bei jedem Commit), `.gitattributes` mit LF für `int_filemanager`, Manifest mit Autor, `README.rst`.
   - Prüfskript `tools/v2check/v2check.sh [--quick]` für odoo-ls und Odoos `test_lint` (Konventionen 9): scheitert
     nur an Befunden in seit `int_filemanager-v1` geänderten/neuen Dateien; der v1-Code hat 12 Altbefunde.
8. ~~Schritt 3 und 4a~~ – **erledigt** (2026-09-27/28, siehe Abschnitt 3). Nach jedem Teil weiterhin: pre-commit
   grün, `tools/v2check/v2check.sh` grün, `i18n/de.po` gepflegt, Gegenlesen mit `codex -p review`; Commit nur nach
   Rückfrage. Update der Live-Instanz ist eine eigene Entscheidung.
9. **Nächster Schritt: Abnahme von Schritt 4** (Plan `docs/int_filemanager_v2_schritt4_plan_2026-09-28.md`).
   Offene Punkte aus dem ersten Handtest am 2026-09-28 (Test-Instanz auf HM-SRV, Abschnitt 5a):
   - **`rememberBase` wird nie aufgerufen** (`static/src/int_filemanager/v2/uploads_service.js`): beim Download wird
     die Ausgangsfassung nicht gemerkt, "Neue Fassung" nimmt deshalb die beim Seitenladen aktuelle Fassung als Basis –
     eine Änderung eines anderen zwischen Download und Upload wird nach einem Neuladen der Seite ohne Hinweis
     überschrieben (bleibt in den Versionen). Verdrahten und in Node testen.
   - **Meldung "frühere Uploads wurden unterbrochen" veraltet:** `upload_manager.js` vergisst einen Upload nur bei
     Fertig oder Abbruch; endgültig gescheiterte (Namenskonflikt, Rechte) bleiben in `localStorage` und zählen nach
     dem Neuladen als unterbrochen, obwohl der Server nichts Offenes kennt; die Meldung hat keinen Verwerfen-Knopf.
     Vorschlag: Gescheiterte vergessen, beim Laden gegen den Server abgleichen, Knopf "Verwerfen".
   - **Namensprüfung ohne Windows-Regeln:** `_clean_name` verbietet nur `/ \ NUL` und `.`/`..`. Zusätzlich
     `: * ? " < > |`, Punkt/Leerzeichen am Ende und reservierte Namen (`CON`, `NUL`, `COM1` …) ablehnen, damit Export
     und späteres Netzlaufwerk unter Windows immer möglich bleiben.
   - ~~Checkliste für den Handtest~~ entfällt (Entscheidung 2026-09-28): der Nutzer testet die Oberfläche frei und
     meldet, was auffällt.
   - pylint-odoo, `test_lint` und odoo-ls für den Stand `d0d5c94` auf Tower laufen lassen (nur dort eingerichtet).
10. **Vor Schritt 8 (Übernahme) festlegen** – Ergebnisse vom 2026-09-28:
   - **Notfall-Export ohne Odoo** ist möglich: rekursive SQL-Abfrage über `parent_id` + Kopie aus
     `blobs/ab/cd/<sha256>` ergab auf der HM-SRV-Instanz 33 Ordner, 219 Dateien, 0 Prüfsummenfehler. Als festes
     Werkzeug ins Repo (kopieren statt Hardlink – ein bearbeiteter Hardlink würde den Blob verändern; Änderungsdatum
     übernehmen; Prüfsumme je Datei) und Probelauf gegen das Backup in die Abnahme von Schritt 8 aufnehmen.
   - **Blob-Prüflauf:** `adopt_hashed` vertraut beim Zusammenlegen einer vorhandenen Datei unter dem Hash, ohne sie
     nachzurechnen – ein beschädigter Blob (Bitfäule, XFS erkennt das nicht) würde eine frisch hochgeladene gute Kopie
     verdrängen. Regelmäßiger Cron, der Blobs nachrechnet und meldet (Kern 9 "Prüfsummenfehler"), plus Ersetzen eines
     als beschädigt bekannten Blobs durch eine gute neue Kopie.
   - **ONLYOFFICE-Zertifikat** vor Schritt 6 lösen (heute nur auf einem Rechner vertraut); ohne ONLYOFFICE auf allen
     Rechnern oder Netzlaufwerk ist V2 für Word/Excel ein Rückschritt gegenüber V1.

## 5. Testumgebung auf Tower (lokaler Unraid, `ssh unraid`)

**Alles gestoppt bzw. temporär; vor dem Löschen den Nutzer fragen.** Live-Instanz (`odoo`, `odoo_db`) wurde nur
gelesen.

| Element | Details |
|---|---|
| `fmtest_pg` | PostgreSQL 16 der Testumgebung (läuft). DBs: `fmtest` (Modul 1.15.0, Testwurzel), `fmreal` (neutralisierte Kopie der Tower-Live-DB, 427.914 Zeilen), `fmv2` (Prototyp int_filemanager 2). Passwort in `/mnt/user/appdata/fmtest/.pgpw` |
| `fmtest_odoo` | Test-Odoo für `fmtest` (Port 8070, erstellt, gestoppt) |
| `fmreal_odoo` | Odoo für `fmreal` (gestoppt; für Lasttests) |
| `fmv2_odoo`, `fmv2_nginx` | Prototyp int_filemanager 2: Odoo Prefork (`workers=2`, `x_sendfile`) + nginx (Port **8081**), gestoppt. Start: `docker start fmtest_pg fmv2_odoo fmv2_fmdav fmv2_nginx` (Variante 19.10; `fmv2_nginx` erst starten, wenn `fmv2_fmdav` läuft, sonst findet nginx den Host nicht) bzw. `… fmv2_dav` (Dienst, 19.4). `fmv2_odoo` wurde am 2026-09-26 für den WebDAV-Test neu erstellt (Umgebung `FM_DAV_SWAP_WINDOW=600`, **ohne** `FM_PROTO_GC_GRACE=0` – für den Aufräumjob-Test aus 19.1 wieder setzen) |
| Modul `fm_proto` | `/mnt/user/appdata/fmtest/addons_v2/fm_proto` (Kopie im Repo: `docs/prototypes/fm2/fm_proto`, inkl. `dav.py`) |
| `fmv2_odoo` (Stand 19.12) | zuletzt für den Test "fmdav ohne eigenen Container" neu erstellt: `odoo --workers=2 --load=base,rpc,web,fm_proto` mit `FM_DAV_EMBED=1`, `FM_DAV_EMBED_PORT=8080`, `FM_DAV_ROOT_ID`, `FM_DAV_ACCEL`, `FM_DAV_ANON_*` (startet `odoo fmdav` als Kindprozess); nginx `/dav` → `fmv2_odoo:8080`. Für den Thread-Modus `--workers=0` statt `--workers=2`. Ohne `FM_DAV_EMBED=1` verhält sich das Modul wie vorher |
| `fmv2_fmdav` | **`odoo fmdav`** (19.10): `odoo --addons-path=/mnt/extra-addons,/usr/lib/python3/dist-packages/odoo/addons fmdav -c /etc/odoo/odoo.conf -d fmv2 --dav-root=68624 --dav-accel=/web/filestore --dav-anon-ips=192.168.188.188 --dav-anon-login=davuser`, Port 8080 im Netz `fmtest-net`; nginx leitet `/dav` **jetzt hierhin** (nicht mehr zu `fmv2_odoo_dav`). Code: `fm_proto/cli/fmdav.py`, `fm_proto/dav_server.py` |
| `fmv2_odoo_dav` | **WebDAV im Odoo-Prozess** (19.7): zweiter Odoo-Prozess derselben DB nur für `/dav/` (`--workers=4 --max-cron-threads=0`, `PYTHONPATH=/mnt/pylib` → `/mnt/user/appdata/fmtest/pylib_v2` mit `wsgidav` 4.3.5 und `json5`). nginx (`fmv2_nginx`, Port **8081**) leitet `/dav` dorthin; Netzlaufwerk `http://192.168.188.67:8081/dav/`. `fmv2_odoo` hat dieselben Umgebungsvariablen (`FM_DAV_ROOT_ID`, `FM_DAV_ANON_IPS`, `FM_DAV_ANON_LOGIN=davuser`). Konfiguration seit 19.6/19.7 geändert: `odoo.conf` ohne `dbfilter` (Sicherung `odoo.conf.bak-dbfilter`), `nginx.conf` mit `/dav`-Location, `client_max_body_size 0`, `Host $http_host`, ETag-Weitergabe (Sicherungen `nginx.conf.bak-dav`, `.bak-davsplit`); Kopie: `docs/prototypes/fm2/tower/config_v2_odoo_und_nginx.txt` |
| `fmv2_dav` | WebDAV-Dienst (Image `fmdav:proto`, Port **8082**), Konfiguration `/mnt/user/appdata/fmtest/fmdav/env` (nur root lesbar, enthält den API-Schlüssel von `davuser`); Wurzelordner in `fmv2`: Knoten `davtest` (ID 68624). Anonymer Testzugang nur für `192.168.188.188` (Arbeitsrechner). Kopie des Codes: `docs/prototypes/fm2/fmdav/` |
| Test-Image | `odoo:19.0-hm-test` (19.0-20260908, gebaut 2026-09-27 aus einer Kopie von `/mnt/user/appdata/odoo/Dockerfile` in `/tmp/odoo-test-build`); das Live-Tag `odoo:19.0-hm` (20260817) ist unverändert |
| pre-commit (Arbeitsrechner) | 4.6.2 für Windows-Python 3.13 (`py -3.13 -m pre_commit`), Programme unter `%APPDATA%\Python\Python313\Scripts` (nicht im `PATH`) |
| Prüfskript | `tools/v2check/v2check.sh [--quick]` (Repo): odoo-ls + Odoos `test_lint`, gefiltert auf `int_filemanager` (Konventionen Abschnitt 9). Auf Tower: `/mnt/user/appdata/fmtest/odoo-ls` (Release 1.6.0 mit `typeshed/`), `/mnt/user/appdata/fmtest/lintlib` (pylint 3.3.9), `/mnt/user/appdata/fmtest/v2src` (vom Skript kopierter Arbeitsstand), `/mnt/user/appdata/fmtest/v2check` (Ergebnisse, Daten-Ordner), DB `fmv2_lint` auf `fmtest_pg` (bei jedem Lauf neu) |
| Konfiguration | `/mnt/user/appdata/fmtest/config_v2/odoo.conf` und `nginx.conf` (Kopie ohne Passwort: `docs/prototypes/fm2/tower/config_v2_odoo_und_nginx.txt`) |
| Blob-Speicher | temporärer Unraid-Share **`fmv2blobs`** (nur `disk3`, kein Cache, keine SMB-Freigabe), Config `/boot/config/shares/fmv2blobs.cfg`, ca. **53 GB** (Import-Teilbestand + Testdateien) |
| Testdateien | `/mnt/user/test/v2src` (3,3 GB) |
| Skripte | `/mnt/user/appdata/fmtest/runv2.sh <schritt>` (Prototyp-Tests `t_v2.py`), `runt.sh` (Block-A-Tests), `fmshell.sh <db>` (odoo shell mit Watcher-Schalter), `snap.sh`; Tests unter `/mnt/user/appdata/fmtest/tests/` (Kopie: `docs/prototypes/fm2/tests*`) |
| Testnutzer | in `fmtest`: `admin`/`admin`, `fmuser`/`fmtest-pw-1`; in `fmreal`: `fmuser_real`/`fmreal-pw-1`; in `fmv2`: `admin`/`admin`, `davuser`/`davuser-pw-1` plus API-Schlüssel "fmdav-proto" für `davuser` und `admin` (nur Testdatenbanken) |

**Aufräumen, wenn nicht mehr gebraucht (nur nach Rückfrage):** Container `fmv2_*` (inkl. `fmv2_dav`, `fmv2_odoo_dav`, `fmv2_fmdav`), `/mnt/user/appdata/fmtest/pylib_v2`, `lintlib`, `odoo-ls`, `v2src`, `v2check`, DB `fmv2_lint`, Image `odoo:19.0-hm-test`, `fmtest_*`, `fmreal_odoo`;
Images `fmdav:proto`, `python:3.12-slim`, `debian:bookworm-slim`, `curlimages/curl`;
Share `fmv2blobs` (Verzeichnis `/mnt/disk3/fmv2blobs` + `.cfg`); `/mnt/user/test/v2src`, `/mnt/user/test/fmroot`;
`/mnt/user/appdata/fmtest`; Netzwerk `fmtest-net`.

## 6. Sonstiges

- **HM-SRV** ist von hier nicht erreichbar; DB dort laut Doku `en_US.utf8` → vor jedem Odoo-Image-Update auf
  C-Kollation umstellen (neuerer Core zerstört sonst Teilbäume, DB-Vorrang-Konzept 19.2).
- **Sicherheitslücke N1** im heutigen Modul (öffentliche Methoden `action_analyze_document`/
  `action_apply_extracted_values` per RPC mit `sudo`) ist **nicht gefixt**; im Konzept 9 für int_filemanager 2
  berücksichtigt. Falls das heutige Modul noch länger produktiv läuft, vorab separat beheben.
- In `web-filemanager` liegen nicht committete Code-Änderungen des Nutzers (unberührt lassen). Dort steht außerdem
  ein Vorschlag als Aufgabe bereit: `frame-ancestors`-Header (Clickjacking-Schutz).
