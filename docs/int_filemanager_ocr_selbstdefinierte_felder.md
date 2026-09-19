# int_filemanager: Selbstdefinierte Extraktionsfelder + Highlighting im PDF

Stand 2026-09-19: alle drei Phasen (A/B/C) auf Branch `feature/ocr-selbstdefinierte-felder`
umgesetzt - siehe "Umsetzung" ganz unten für die dabei getroffenen Entscheidungen zu den unten
offen gelassenen Fragen. Ergänzt
[int_filemanager_paperoffice_recherche.md](int_filemanager_paperoffice_recherche.md) (Baustein 1/3) -
dort wurde `fields.Properties` als möglicher späterer Schritt vorgemerkt, dieses Dokument ersetzt
diese Empfehlung durch ein echtes Datensatz-Modell (Begründung siehe unten).

## Ausgangslage

Baustein 1 (Volltextsuche + Werterkennung, siehe `int_filemanager_native_ui.md` Punkt 22) ist eng
begrenzt:
- Nur drei feste Werte: `extracted_date`, `extracted_invoice_number`, `extracted_amount`
  (`int_filemanager.extraction_pattern.target_field` ist eine feste 3er-Auswahl).
- Nur PDF + reine Textformate (`fulltext.py`), Regex-basiert, kein LLM (bewusste
  Nutzerentscheidung 2026-09-05).
- Kontroll-Dialog (`document_review_dialog.xml`) zeigt nur Textfelder, keine Sicht auf die
  Quelle - man muss den erkannten Werten blind vertrauen.

**Neuer Bedarf (2026-09-19):** selbstdefinierte, beliebig viele Extraktionsfelder statt der drei
festen - und eine visuelle Markierung im PDF, wo ein Wert gefunden wurde.

## Verworfene Wege (nicht versehentlich nochmal aufgreifen)

- **`fields.Properties`**: am echten Odoo-Code geprüft (`project_task.py`:
  `task_properties = fields.Properties(..., definition='project_id.task_properties_definition')`).
  Die Definition liegt als JSON-Blob auf einem gewählten Trägerdatensatz (z.B. `res.company`),
  kein echtes Modell mit eigener Liste/Reporting. Für global geltende, aber trotzdem "echte"
  Datensätze **ungeeignet** - Nutzereinwand 2026-09-19 war berechtigt.
- **Regex → LLM**: laufende Kosten pro Datei + Datenschutz (Dokumente würden extern verschickt,
  heute läuft alles lokal). Bereits am 2026-09-05 abgelehnt, jetzt nochmal bestätigt - eigene
  Felder brauchen kein LLM.
- **Manuell Zonen im PDF einzeichnen ("Vorlagen pro Dokumenttyp")**: technisch einfacher als
  automatisches Highlighting (kein Rückweg von Text-Treffer zu Position nötig), aber nur bei
  wiederkehrend gleichem Layout sinnvoll, bräuchte ein Vorlagen-/Zuordnungskonzept. Nutzer hat
  sich stattdessen für automatisches Highlighting entschieden (2026-09-19).

## Phase A - Datenmodell-Fundament

- `int_filemanager.extraction_pattern.target_field`: feste 3er-Auswahl → freier Text (der
  technische Name des Feldes, das dieses Muster befüllt).
- **Neues Modell `int_filemanager.extracted_value`**, 1:1 nach Vorbild von Odoos eigenem
  `product.attribute.custom.value` (`addons/product/models/product_attribute_custom_value.py`,
  echtes natives EAV-Muster: Definition + freier Wert, jeweils eigene Datensätze):
  - `pattern_id` (Many2one auf `extraction_pattern`, `ondelete='restrict'` - schützt vor
    verwaisten Werten bei gelöschter Definition)
  - `file_id` (Many2one auf `int_filemanager.file`)
  - `value` (Char)
  - `name` (computed, z.B. "Betrag (EUR): 129,90")
  - `page`, `x0`, `y0`, `x1`, `y1` (Position im PDF, **rein technisch, nie als Spalte sichtbar** -
    genau wie `is_dir`/`path`/`folder_path` heute schon in der Dateiliste per
    `column_invisible="1"` mitgeladen werden. Jetzt schon anlegen, obwohl Highlighting erst
    Phase C ist - Kernvorteil eines echten Modells: eine simple Feldergänzung statt eines
    JSON-Umbaus).
- `int_filemanager.file.extracted_value_ids` (One2many).
- Bestehende drei Felder (`extracted_date`/`_invoice_number`/`_amount`) bleiben unverändert -
  kein Migrationsrisiko für Bestandsdaten, neue selbstdefinierte Felder kommen zusätzlich dazu.
- Werte bleiben bei der Datei selbst (eigenes Formular), fließen NICHT automatisch in andere
  Odoo-Module (z.B. `account.move`) - offene Frage, nur bei explizitem Wunsch später angehen.

**Wie der Kontroll-Dialog weiß, welche Felder er zeigen soll:** genau wie heute schon (alle drei
festen Felder werden IMMER zurückgegeben, gefüllt oder leer) - künftig holt
`action_analyze_document()` sich alle aktiven `extraction_pattern`-Datensätze, prüft jeden gegen
den Dokumenttext und gibt für jeden einen (ggf. leeren) Wert zurück. Der Dialog rendert eine Zeile
pro zurückgegebenem Muster - keine feste Liste im Dialog-Code, sondern das Ergebnis einer frischen
Abfrage pro Analyse-Lauf. Neue Admin-Muster tauchen automatisch ab dem nächsten Lauf auf.

**Was echte Datensätze (statt Properties/JSON) konkret ermöglichen:**
- Suchen/Filtern über `extracted_value_ids` (z.B. "alle Dateien mit Rechnungsnummer X").
- Eigene Listen-/Pivot-Auswertung direkt auf `extracted_value` (z.B. Beträge nach Monat).
- Normale Odoo-Exporte (Excel/CSV) über die Standard-Listenansicht.
- Automatisierte Aktionen auf Basis der Werte (z.B. "Betrag > 1000€ → Benachrichtigung").
- Leichter an andere Module anzubinden, falls später gewünscht (normaler Lesezugriff auf echte
  Felder statt JSON-Parsing).

## Phase B - Extraktionspfad vereinheitlichen

Aktuell zwei getrennte Wege ohne Positionsdaten: `PyPDF2` (Textlayer) und `pytesseract`/
`pdf2image` (OCR-Fallback, nur Fließtext via `image_to_string()`).

Recherche-Ergebnis (Paperless-ngx als reales Vorbild geprüft, `src/paperless/parsers/tesseract.py`):
nutzt **OCRmyPDF** statt rohem `pytesseract` - baut eine korrekt positionierte, unsichtbare
Textebene direkt in die PDF ein (Zweck des Tools: durchsuchbare/markierbare PDF erzeugen). Eigene
Sidecar-Textdatei nur für deren Volltextsuche, kein Highlighting bei denen.

**Daraus abgeleiteter, vereinfachter eigener Plan:**
- `PyPDF2` → `pdfplumber` (statt PyMuPDF: gleiche freizügige Lizenzfamilie wie bisher, PyMuPDF ist
  AGPL).
- `pytesseract`/`pdf2image` roh → **OCRmyPDF**. Tesseract läuft weiterhin intern, aber wir rufen es
  nicht mehr direkt auf - OCRmyPDF übernimmt Positionierung.
- Nach OCRmyPDF (falls nötig) läuft `pdfplumber` **einheitlich** auf jeder PDF (egal ob
  ursprünglich digital oder frisch OCR'd) - liefert Wort-Boxen direkt in PDF-Punkt-Koordinaten,
  keine eigene Pixel→Punkt-Umrechnung über die Render-DPI mehr nötig (das wäre bei rohem
  `image_to_data()` erforderlich gewesen).
- `content_text` (Volltextsuche) bleibt unverändert befüllt, nur aus anderer Quelle:
  `pdfplumber.extract_text()` - kein Sidecar-Mechanismus nötig, ein Durchlauf liefert Text UND
  Positionen zugleich.
- Regex-Treffer müssen auf die zugrundeliegenden Wort-Boxen zurückgeführt werden (kombinierte Box
  bei mehrwortigen Treffern) - das gibt es heute noch gar nicht, neu zu bauen.
- Docker-Auswirkung (erst bei Umsetzung): `ocrmypdf` neu in `Dockerfile`, `pytesseract`/
  `pdf2image` können raus.

## Phase C - Eigener PDF-Viewer mit Highlighting

- Weg vom fertigen `pdfjs`-iframe-Viewer (`web/static/lib/pdfjs/web/viewer.html`, heute genutzt in
  `onPreview()`), stattdessen Odoos bereits mitgelieferte Kern-Bibliothek
  (`web/static/lib/pdfjs/build/pdf.js` + `pdf.worker.js` - **exakt dieselben Dateien**, die das
  npm-Paket `pdfjs-dist` von Mozilla auch nur verpackt, keine neue Abhängigkeit nötig) direkt über
  die JS-API ansteuern (`pdfjsLib.getDocument(...)`, `page.render(...)`).
- Seiten selbst auf `<canvas>` rendern, Overlay-Boxen an den aus `extracted_value`
  (`page`/`x0..y1`) berechneten, skalierten Positionen einzeichnen.
- Kontroll-Dialog: PDF-Vorschau (eigener Renderer) links, dynamische `extracted_value`-Liste
  rechts, Klick/Hover auf einen Wert hebt die zugehörige Zone im PDF hervor.
- Für reine Textdateien (kein PDF): statt Highlighting einfach `content_text` danebenstellen
  (kein Positionskonzept bei Klartext nötig/möglich).

## Reihenfolge / nächster Schritt

Phase A ist unabhängig von B/C nutzbar (echtes Datenmodell + dynamischer Dialog funktionieren auch
ganz ohne Positionsdaten). B baut auf A auf (befüllt die neuen Positionsfelder). C baut auf B auf
(braucht die Positionsdaten zum Zeichnen). Empfehlung: mit Phase A beginnen.

**Offene, nicht entschiedene Fragen:**
- Sollen erkannte Werte later automatisch andere Odoo-Dokumente befüllen (z.B. `account.move`)?
  Nicht entschieden, nur bei explizitem Wunsch angehen.
- Migration der Bestandsdaten (aktuell befüllte `extracted_date`/`_invoice_number`/`_amount`) in
  `extracted_value`? Nicht besprochen - vermutlich unnötig, da beide Systeme parallel existieren
  können.

## Umsetzung (2026-09-19, Branch `feature/ocr-selbstdefinierte-felder`)

Alle drei Phasen wurden in einem Durchgang umgesetzt, ohne Rückfrage bei offenen Fragen (Auftrag:
"bei offenen Fragen selbst entscheiden"). Konkrete Entscheidungen, die beim Schreiben des Codes
nötig wurden und über das oben Geplante hinausgehen:

**target_field bleibt für die drei Legacy-Felder fest verdrahtet, statt komplett frei zu werden.**
`target_field` ist jetzt `fields.Char` (frei), aber die drei Strings `"date"`/`"invoice_number"`/
`"amount"` bleiben als Sonderwerte im Code (`fulltext._LEGACY_TARGET_FIELDS`): nur sie befüllen
weiterhin `extracted_date`/`_invoice_number`/`_amount`. Jeder andere Wert erzeugt einen
`extracted_value`-Datensatz. Grund: die drei Legacy-Felder sind aktiv in Listen-/Kanban-Spalten
verdrahtet (`filemanager_file_list_view.xml`, `filemanager_file_kanban_view.xml`) - eine
Migration auf ausschließlich `extracted_value` hätte diese Ansichten mitändern müssen und wäre
ein unnötiges Migrationsrisiko für eine Funktion gewesen, die schon funktioniert. Die
Konsequenz: der "Werte erkennen"-Dialog hat zwei Bereiche - die alten drei festen Felder
(unverändert) plus eine neue dynamische Liste darunter, ausschließlich für selbstdefinierte
Muster. Das erfüllt "keine feste Liste im Dialog-Code" für alles NEUE, ohne das Bestehende
anzufassen.

**`int_filemanager.extracted_value` hat bewusst KEINE eigene Schreib-ACL für Nutzer**
(`ir.model.access.csv`: nur `perm_read`). Erzeugt/gelöscht wird ausschließlich sudo() über
`filemanager_file.py::action_apply_extracted_values`, aufgerufen über einen neuen Controller
(`/int_filemanager/apply_extracted_values`), der vorher `authz.require(..., "write")` prüft -
genau das Muster, das `int_filemanager.version` schon für versionierte Dateiinhalte verwendet.
Grund: ohne diese Einschränkung hätte ein Nutzer mit `group_filemanager_user` per direktem
`orm.create()` einen `extracted_value`-Datensatz mit beliebiger `file_id` anlegen können,
einschließlich Dateien unter einem Schutzordner, auf den er keinen Schreibzugriff hat - Odoos
Record-Rules greifen bei `create()` nicht automatisch auf die neuen Feldwerte. Zusätzlich wurde
`int_filemanager.extracted_value` in `acl_rules.py` MODELS-Dict registriert (wie
`int_filemanager.version`) - die drei domain_force-Regeln folgen automatisch dem
Schutzordner-Status der zugehörigen Datei, sonst könnte ein Nutzer erkannte Werte einer
geschützten Datei über die neue Listen-/Pivot-Ansicht lesen, obwohl er die Datei selbst nicht
lesen darf.

**OCRmyPDF schreibt nie in die Originaldatei zurück**, sondern immer in eine Temp-Datei, die nach
der Extraktion sofort wieder gelöscht wird. Grund: ein automatischer Analyse-/Cron-Schritt soll
nie unbemerkt mtime/Hash einer vom Nutzer verwalteten Datei verändern (würde Versionierung/Dedup
verwirren). Konsequenz: der bestehende Kurzschluss-Pfad ("Datei seit letzter Extraktion
unverändert → content_text aus Cache") liefert für einen erneuten "Werte erkennen"-Klick auf
einen SCAN (kein echter Textlayer) keine PDF-Positionen mehr, nur noch beim allerersten Lauf nach
einer Änderung - der erkannte Wert selbst bleibt aber immer korrekt, nur ohne Markierung im PDF.
Für digitale PDFs (der Regelfall, z.B. E-Rechnungen) gilt diese Einschränkung nicht, da dort ein
günstiger pdfplumber-Pass ohne OCR jederzeit wiederholbar ist.

**content_text hat sich strukturell geändert**: statt `pdfminer`/`PyPDF2`-Fließtext mit
Zeilenumbrüchen ist es jetzt eine Wort-für-Wort-Aneinanderreihung mit einfachen Leerzeichen
(Zeilenumbruch nur zwischen Seiten) - notwendig, damit ein Regex-Treffer sich verlustfrei auf
seine Wort-Boxen zurückführen lässt (siehe `fulltext._build_indexed_text`). Die Volltextsuche
selbst bleibt funktional (einfache Teilstring-Suche ist von der Zeilenumbruch-Kosmetik nicht
betroffen), nur die Rohtext-Vorschau sieht etwas anders/kompakter aus als vorher.

**Der neue PDF-Highlight-Viewer (Phase C) ersetzt den `pdfjs`-iframe-Viewer NUR im
"Werte erkennen"-Dialog**, nicht in der normalen Dateivorschau (`onPreview()` in
`filemanager_controller_mixin.js` nutzt weiterhin unverändert
`web/static/lib/pdfjs/web/viewer.html`). Der Plan spricht zwar allgemein von "weg vom fertigen
pdfjs-iframe-Viewer", meint im Kontext aber erkennbar nur die Highlighting-Anforderung im
Kontroll-Dialog - die normale Vorschau hat keinen Bezug zu erkannten Werten und für sie einen
kompletten eigenen Renderer zu bauen wäre eine unbegründete Ausweitung gewesen.

**Nicht automatisiert verifiziert**: dieses Modul braucht eine laufende Odoo+PostgreSQL-Instanz
(Docker) zum Testen, die in dieser Umgebung nicht verfügbar war - alle Python-Dateien wurden per
`py_compile` auf Syntaxfehler geprüft, alle XML-Views auf Wohlgeformtheit, die neue
Offset-Bookkeeping-Logik (`_build_indexed_text`/`_locate_span`) zusätzlich per eigenständigem
Unittest (`tests/test_fulltext_word_index.py`, läuft ohne Odoo-Umgebung) und per manueller
Durchrechnung bestätigt.

## Produktiv-Deploy (2026-09-19, HM-SRV)

Direkt im Anschluss auf HM-SRV deployt (DB-Backup + Watcher-Kill-Switch + Docker-Rebuild +
`-u int_filemanager` nach dem dokumentierten Rollout-Vorgehen). Dabei drei vorher nicht bekannte
Probleme gefunden und behoben, alle im selben bzw. einem Folge-Commit:

- **pip/apt-Konflikt**: `ocrmypdf`/`pikepdf` ziehen ein neueres `cryptography` als das per apt
  vorinstallierte `pyOpenSSL` (23.2.0) vertraegt - Odoos `web`-Modul (importiert `OpenSSL` fuer
  `ir_mail_server`) scheiterte danach komplett (`AttributeError: module 'lib' has no attribute
  'GEN_EMAIL'`), die gesamte Oberflaeche war down. Fix: `pyopenssl>=24` explizit mit installieren.
- **CRLF-Zeilenenden**: `core.autocrlf=true` im Repo wandelt `scripts/*.sh` beim Windows-Checkout
  in CRLF um - ein `exec`-Aufruf eines so ausgecheckten Skripts scheitert mit "no such file or
  directory" (der Kernel versteht die Shebang-Zeile mit `\r` nicht). Fix: `.gitattributes` mit
  `*.sh text eol=lf` (die Git-Blobs selbst waren bereits LF, betraf nur Checkouts unter Windows).
- **`wait_for_smb_mounts.sh` passt nicht zur echten Server-Topologie**: das Skript (Repo-Commit
  `04904d6`, nie zuvor live deployt) erwartet drei separate CIFS-Mounts unter
  `/mnt/hm-daten/{Daten,Produktiv-HM-Datenbank,Transfer}` - real ist `/mnt/hm-daten` ein einziger
  flacher Bind-Mount von `/mnt/user/Daten`. Fuehrte zu einer Neustart-Schleife. Fuer dieses Deploy
  ausgelassen (separates, unabhaengiges Problem, nicht Teil dieser Aufgabe) - auf dem Server liegt
  aktuell eine abweichende Dockerfile-Variante ohne diesen ENTRYPOINT-Wrapper.

## Vereinheitlichung (2026-09-19, noch am selben Tag)

Nutzerwunsch nach dem ersten Test: die drei mitgelieferten Legacy-Felder
(`extracted_date`/`_invoice_number`/`_amount`, bis dahin ein Sonderpfad neben
`extracted_value`) entfernen, alles einheitlich über `extracted_value` laufen lassen. Umgesetzt:

- Die drei Char-Felder auf `int_filemanager.file` sind komplett entfernt.
- `fulltext.py`: `_match_extraction_patterns`/`_match_custom_patterns` zu einer einzigen
  `_match_patterns()` zusammengeführt, `_LEGACY_TARGET_FIELDS` entfernt. `target_field` ist jetzt
  nur noch ein freies Anzeige-/Sortier-Label ohne jede Sonderbedeutung im Code.
- Dialog: die drei festen Eingabefelder sind raus, alle Muster (auch die drei mitgelieferten)
  erscheinen einheitlich in der dynamischen Liste "Erkannte Felder".
- **Migration** (`19.0.1.11.0`): bereits bestätigte Alt-Werte werden vor dem Löschen der Spalten
  in `extracted_value`-Datensätze übernommen (kein Datenverlust) - am echten Produktivbestand
  bestätigt (1 Datum + 1 Betrag korrekt übernommen).
- Redeploy erfolgreich, keine neuen Probleme (kein Docker-Rebuild nötig, reiner Code+Migrations-
  Durchlauf).

## AcroForm-Formularfelder (2026-09-19, direkt im Anschluss an den ersten echten Test)

Erster Test mit einer echten Datei (`04 Anlage Kind Clemens.pdf`, Suche nach einer bekannten
Kindergeldnummer) fand: **nichts erkannt**, obwohl die Nummer im PDF sichtbar ist. Ursache am
echten Dokument verifiziert: es ist ein ausfüllbares AcroForm-PDF - die eingetragenen Werte
(Name, Geburtsdatum, Kindergeldnummer) stecken als Formularfeld-Werte in einer separaten
Annotationsstruktur, NICHT im normalen Seiteninhalt. `pdfplumber.extract_words()` liest nur den
gerenderten Seiteninhalt und sieht solche Werte grundsätzlich nie - unabhängig von der Regex.
Nutzerentscheidung: beheben, da vermutlich ein relevanter Teil der Behörden-/
Versicherungsdokumente im Bestand genauso aufgebaut ist.

**Umsetzung**: `fulltext._pdf_form_field_words()` liest pro Seite die AcroForm-Annotationen
(`page.annots`), nimmt Textfelder (`Tx`) und Dropdowns (`Ch`) - Checkboxen/Radiobuttons (`Btn`)
bewusst ausgeschlossen, deren Wert ist ein PDF-Name (z.B. der gewählte Options-Wert), kein freier
Text, und mehrere Buttons einer Radiogruppe teilen sich denselben Feldnamen. Jeder Feldwert wird
als EIN zusammenhängendes Token (nicht in Einzelwörter zerlegt) an die normale Wortliste der
Seite angehängt - dieselbe `_build_indexed_text`-Pipeline verarbeitet beides identisch, kein
zweiter Auswertungsweg nötig. `_decode_form_field_value()` deckt beide in freier Wildbahn
beobachteten Kodierungen ab (UTF-16BE mit BOM für Nicht-ASCII, PDFDocEncoding/Latin-1 ohne BOM).

**Bewusste Einschränkung**: ein Formularfeld-Token hat keine Nachbarschaft zum gedruckten Label
im Text (Label und Feldwert sind zwei unabhängige, räumlich getrennte Tokens) - ein Muster für
einen Formularwert sollte daher das **Wertformat selbst** matchen (z.B. `\b\d{3}[A-Z]{2}\d{6}\b`
für eine Kindergeldnummer), keine Label-Nähe voraussetzen wie bei echtem Fließtext. Am echten
Dokument bestätigt: mit einem wertformat-basierten Muster wurde `006FK405328` korrekt samt
Position erkannt: die eingebaute Datums-Regel fand zusätzlich `04.02.2025` aus einem Datumsfeld,
das vorher ebenfalls nicht auffindbar war.

Getestet direkt gegen die Produktivdatei per `odoo shell` (Testmuster angelegt, Analyse
ausgeführt, Ergebnis verifiziert, Testmuster wieder gelöscht) - kein automatisierter Unittest für
den PDF-Lesepfad selbst (braucht eine echte AcroForm-PDF-Datei), aber `_decode_form_field_value()`
zusätzlich per Unittest abgedeckt (`tests/test_fulltext_word_index.py`). Kein Schema-/
Migrationsbedarf, reine Erweiterung der Textextraktion - Version `19.0.1.12.0`.
