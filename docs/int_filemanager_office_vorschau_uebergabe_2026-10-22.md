# int_filemanager: Office-Vorschau, Übergabe vom 22.10.2026

Ziel: Word, ODT, Excel, PowerPoint und Verwandte (docx, doc, odt, rtf, xlsx, xls, ods, pptx, ppt, odp, auch sxw/sxc/sxi/fodt) im Viewer wie ein PDF anzeigen. Ein Cron wandelt sie im Hintergrund mit LibreOffice in ein abgeleitetes PDF um. Der Download bleibt das Original. Nichts davon ist gebaut, der Plan ist vom Nutzer freigegeben.

## Entscheidungen des Nutzers

- **Variante A zuerst** (LibreOffice nach PDF). ONLYOFFICE (Variante C) nur später und nur, wenn Bearbeiten im Browser gewollt ist; dann über WOPI, nicht über den alten Connector.
- **Erste Runde nur die Vorschau** (Schritte 1 und 2 unten). Die Suche über `.doc`/`.rtf` ist ein eigener späterer Auftrag.
- **Odoo-nah, ohne Hilfsskripte:** direkter `subprocess.run` wie Odoo bei `wkhtmltopdf` und Nextcloud bei `Office.php`. Kein Starter-Skript, kein gemeinsamer Wrapper.
- **Bei der OCR ohne `prlimit`** (Speichergrenze des Workers gilt für das Programm). Bei der Office-Vorschau ebenso.
- Standardwerte, die ich vorgeschlagen habe und die nicht widersprochen wurden: Schalter „Office-Vorschau“ an, Größengrenze 500 MB, Zeit je Datei 120 s.

## Fertig und gepusht (master)

- `7974cc5` [FIX] OCR blieb bei kleinem Zeitlimit stehen: die faire Zeit einer Einzelseite kommt jetzt aus dem Fenster des Laufs (`ocr_plan.fair_seconds`).
- `8eb38bc` [REF] `_ocr_run` nutzt `subprocess.run` mit `nice`, `timeout --kill-after=5` und `env=`. Weg: `tools/start_ocr.py`, `_kill_tree`, psutil-Import, Windows-Zweig.

## Messungen (Tower, Wegwerf-Container, echte Dateien)

- **LibreOffice 24.2.7** (Ubuntu 24.04): doc, rtf, docx, xls, xlsx, pptx, odt, ods wandeln in 1 bis 4 s, auch unter 1,5 GiB Adressraumgrenze. Größte Dateien: .doc 474 MB in 48 bis 54 s (PDF 24 MB), .pptx 126 MB in 25 s (PDF 101 MB). Abbruch hinterlässt keine Prozesse.
- **Image:** +116 MB Download, +396 MB installiert (89 Pakete plus 3 Schriftpakete). Pakete: `libreoffice-writer-nogui`, `libreoffice-calc-nogui`, `libreoffice-impress-nogui`, `fonts-liberation`, `fonts-crosextra-carlito`, `fonts-crosextra-caladea`, jeweils mit `--no-install-recommends`. Im Image fehlen Liberation und Carlito sonst.
- **Bestand** (`/mnt/user/Daten`, Zählung evtl. unvollständig): 1.219 Büro-Dateien, 2,3 GB, davon 496 `.doc` und 528 `.rtf` (84 % alte Formate, die die Suche heute nicht liest).
- **OCR mit plain `subprocess.run`:** 20 echte Dateien, 10 größte PDFs, größte Bilder (110 Mpx) und A0-Seiten laufen unter 2,5 GiB identisch zum Starter-Skript. Ab etwa 450 bis 500 Mpx scheitert Tesseract still (Exit 0, kein Text); das ist die bewusste Folge der Entscheidung gegen `prlimit`.
- **Prefork-Cron-Worker mit Standard-Limit (120 s):** Budget 35 s, Fenster 25 s; das war der Anlass für den Fix `7974cc5`.
- **Tower-Konfiguration:** `limit_time_real_cron = 1800`, Einzelprozess-Betrieb (`workers = 0`).

## Bauplan Schritt 1 (Vorschau)

1. **Dockerfile:** die Pakete oben ergänzen. Image `odoo:19.0-hm` und `odoo:19.0-hm-test` auf dem Tower neu bauen, **erst nach Rückfrage**.
2. **Felder am Dokument** (`models/int_filemanager_document.py`): `preview_checksum` (Char, `readonly`, `copy=False`, `exportable=False`) und `preview_state` (Selection `done|failed`), Muster `thumbnail_state` (Zeile 216). **Beide in `STORAGE_FIELDS` (Zeile 70) aufnehmen**, sonst kann ein Nutzer per RPC eine fremde Prüfsumme eintragen und über die Route `ocr_content` lesen. Teilindex wie `_thumbnail_work_index` (Zeile 257).
3. **`_compute_ocr_checksum`** (Zeile 270): Rückfall auf die eigene `preview_checksum`, `@api.depends` ergänzen. Dann ändern sich Controller, Ansichten und `_to_ocr_http_stream` nicht. Meldung in `_to_ocr_http_stream` neutral formulieren.
4. **Cron `_cron_previews`** nach dem Vorbild von `_cron_thumbnails` (Zeile 865), eigener `ir.cron` in `data/int_filemanager_document_data.xml` (5 Minuten, Priorität unter den Vorschaubildern), `_trigger()` beim Upload. Gruppiert nach Prüfsumme; vorher bei Geschwistern mit fertiger Vorschau übernehmen.
5. **Umwandlung:** Blob ohne Endung, darum Symlink oder Kopie mit Endung aus fester Zuordnung Typ nach Endung in den Jobordner. Aufruf: `subprocess.run(["nice", "-n", …, "timeout", "--kill-after=5", "120", "soffice", "-env:UserInstallation=file://<Jobordner>/profile", "--headless", "--nologo", "--nofirststartwizard", "--invisible", "--norestore", "--convert-to", "pdf", "--outdir", <Jobordner>, <Datei>])`, Profilordner je Lauf (LibreOffice läuft nur einmal je Profil). Ergebnis mit `_store_stream` und `_publish_blob` ablegen (Muster `_ocr_finish`, `int_filemanager_text.py` um Zeile 1340). Zeitgrenze aus `Text._budget()`; Größengrenze und Zeit als Einstellung.
6. **Aufräumer `_gc_blobs`** (Zeile 699): `used` um Dokumente mit `preview_checksum` erweitern; Prüfsumme beim Löschen oder Ersetzen auf die Liste setzen. Ohne LibreOffice: Cron warnt einmal und tut nichts (wie `pypdfium2` bei den Vorschaubildern).
7. **Viewer** (`static/src/int_filemanager/document_file.js`): `isPdf` für Büro-Dateien mit Vorschau wahr machen, daneben eine Eigenschaft „ist selbst ein PDF“ (nach Typ) für die Trefferbeschriftung (`document_content_hits_field.js:12`) und den Seitensprung (`document_file.js:71`). Grund: Die Textseiten der Suche sind bei Büro-Dateien 64-KB-Blöcke, keine Seiten.
8. **Einstellungen:** Schalter, Größengrenze, Zeit, Statuszeile (LibreOffice gefunden und Version, Zähler fertig/offen/fehlgeschlagen) nach dem Muster der OCR (`models/res_config_settings.py`, `views/res_config_settings_views.xml`).
9. **Übersetzungen** (`i18n/de.po`; `tests/test_translations.py` prüft sie).
10. **Tests** nach Muster `test_document_thumbnail.py` und `test_document_ocr_download.py`: Cron mit Stub-Programm, Zustand je Fehlerfall, Schreibschutz der neuen Felder (Nutzer ohne `su`), Aufräumer behält und löscht die Vorschau, Route liefert das PDF, Download bleibt das Original, Rechte eines Lesers, Geschwister übernehmen statt neu wandeln, Trennung „zeigt PDF“ / „ist PDF“.

## Bauplan Schritt 2 (Vorschaubilder)

Derselbe Cron zeichnet nach der Umwandlung die erste Seite des Vorschau-PDFs (`_draw_first_page(preview_checksum)`); `thumbnailUrl` in `document_file.js:119` greift dann über `isPdf` von selbst. Der Vorschaubild-Cron für PDFs bleibt unverändert.

## Fehlerfälle

LibreOffice fehlt: Datei bleibt Download. Defekt, passwortgeschützt, zu groß oder zu langsam: `preview_state = failed`, nicht wiederholt, Download geht. Datei ersetzt oder gelöscht: alter Blob auf die Aufräum-Liste. Gäste einer Freigabe: unverändert, kein Vorschau-PDF. Rechte: wie das Original, über das Dokument.

## Stolpersteine

- **Standard-Zeitlimit:** Cron-Limit 120 s gibt der OCR nur 35 s Budget; Rechenlast in der Weboberfläche beachten.
- Im Odoo-Image fehlt `ps`; Tests lesen `/proc`.
- Bash-Heredocs mit Backslashes sind auf dem Windows-Arbeitsrechner unzuverlässig; Skripte mit dem Write-Werkzeug anlegen.
- `tools/check/tests.sh --test-tags "/int_filemanager:Klasse,…"` für gezielte Tests (rund 2 Minuten), Testinstanz `fmv2_ui` auf Port 8085 gehört dem Nutzer und bleibt unberührt.
- Der 22.10.: ein Privatschlüssel des ONLYOFFICE-Servers (WOPI, `local.json`) war versehentlich in einer Ausgabe sichtbar; bei Weitergabe des Verlaufs erneuern.

## ONLYOFFICE als spätere Ergänzung (Stand der Prüfung)

Auf dem Tower läuft `OnlyOfficeDocumentServer` (Version 9.2.1, WOPI aktiv, Ports 8888/4430, öffentlich `http://192.168.188.67:8888/`), `onlyoffice_odoo` ist in der Datenbank `odoo` installiert. Der Connector hängt an `ir.attachment`; für den Filemanager wären eigene WOPI-Routen nötig (Token je Datei mit Ablaufzeit, Prüfung über die Ordner-Rechte). Hürden: zweiter Hostname mit vertrauenswürdigem Zertifikat auf allen Geräten (Befund vom 23.09.), HTTP/HTTPS-Mischinhalt.

## Offene Entscheidungen

1. Unabhängige Gegenlese des Entwurfs vor dem Bau (Hilfsagent oder Codex), empfohlen wegen Dateispeicher und fremden Dateien.
2. Neubau des Images auf dem Tower (Zeitpunkt).
3. Ob Variante C später kommt.

## Erster Schritt der nächsten Sitzung

Skill `feature` Phase 4 (Umsetzung, Plan ist freigegeben) mit dem Skill `odoo-quellcode-schreiben`: zuerst das Dockerfile und ein Test-Image, damit `soffice` im Container laufen kann, dann Schritt 1 in der Reihenfolge der Liste. Vor dem ersten Code kurz die Gegenlese klären.
