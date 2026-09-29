# int_filemanager 2 – Werterkennung (Schritt 5, Punkt 1 der Übergabe 4.0)

Stand 2026-09-29. Grundlage: Konzept 9 (Entscheidung 14 „Werterkennung bleibt in Odoo“), Übergabe 4.0 Punkt 1,
v1-Umsetzung (`docs/int_filemanager_ocr_selbstdefinierte_felder.md`). **Nur Server und Datenmodell, keine
Oberfläche** (Nutzerentscheidung 2026-09-29). **Fertig, wenn:** Muster, Felder und erkannte Werte hängen am Knoten,
Vorschlagen und Übernehmen sind rechtegeprüft (N1 ist in v2 zu, belegt durch einen RPC-Test als Nicht-Admin), eine
Sammlung echter Dokumente mit bekannten Sollwerten wird mit gemessener Trefferquote erkannt, und pre-commit,
`test_lint`, odoo-ls, `i18n/de.po` sind ohne Befund.

Dieses Dokument trennt **Befund** (Abschnitte 2–3, alles im Code nachgesehen oder live geprüft) von **Vorschlag**
(4–6). Die offenen Entscheidungen stehen gesammelt in Abschnitt 7.

## 1. Ausgangslage

- **v1** (`int_filemanager.extraction_pattern` / `.extracted_value`, `fulltext.py`): Admin-Muster als Python-Regex
  mit Erfassungsgruppe, `target_field` als freier Text, je Muster **nur der erste Treffer**, Wert als `Char`,
  Position `page/x0/y0/x1/y1` (tatsächlich `top`/`bottom` von pdfplumber). Vorschläge werden bei Bedarf berechnet
  und nicht gespeichert; gespeichert wird erst, was der Nutzer im Prüf-Dialog bestätigt (Liste wird ganz ersetzt).
  Partner-Vorschlag: Namen der ersten 2000 Kontakte als Teilzeichenkette im Text; Tag-Vorschlag: Tag-Name im Text.
- **N1:** Die beiden v1-Methoden sind öffentlich, arbeiten mit `sudo()` und vertrauen der Prüfung im Controller;
  über `/web/dataset/call_kw` umgeht man den Controller (DB-Vorrang-Konzept, Befund N1).
- **v2 heute:** Der Umwandler liefert für PDFs und Office-Vorschau-PDFs die Art `words`: eine JSON-Datei
  `{"pages", "text", "words": [{text, page, x0, top, x1, bottom}]}` im Blob-Speicher (`derived_blob_id`).
  Textdateien liefern die Art `text` in die Spalte `derivative.text`. **Der Text von PDFs steht damit nicht in der
  Datenbank** – die Volltextsuche aus Konzept 9 ist noch nicht gebaut und hätte für PDFs heute nichts zu durchsuchen.
- Der Knoten hat schon `tag_ids`, `status_id`, `partner_id` und `mail.thread`.
- Die v1-Modelle liegen im selben Modul; v1-Code (`int_filemanager.file`) bleibt bis Schritt 8 lauffähig (Schritt-4-Plan,
  Entscheidung 1).

## 2. Befund Odoo 19 (Community-Checkout `2e2acfd6` und Test-Image `odoo:19.0-hm-test`)

Suchraster nach CLAUDE.md: Core-Grep, vergleichbare Module, Bibliotheken im Image, Feld-/Modell-Defaults, Live-Probe.

### 2.1 Regeln „Muster → Wert“ gibt es mehrfach – immer gleich gebaut

| Stelle | Was es tut | Übernehmen |
|---|---|---|
| `barcodes_gs1_nomenclature/models/barcode_rule.py`, `barcode_nomenclature.py` (`parse_gs1_rule_pattern`) | Regel mit `sequence`, `pattern` (Regex mit Gruppen), `type` (Ziel) und **`gs1_content_type`** (`date`/`measure`/`identifier`/`alpha`): der Treffer wird **nach Typ umgewandelt** (Datum, Zahl mit Dezimalstelle); `@api.constrains` prüft `re.compile` und die Gruppenzahl | **Nächstes Vorbild:** Regel → Typ → Umwandlung; Prüfung beim Speichern |
| `account/models/account_reconcile_model.py` | `match_label = 'match_regex'`, `amount_type = 'regex'` (Betrag aus der Erfassungsgruppe), Prüfung per `re.compile` | Erfassungsgruppe liefert den Wert; die Anwendung selbst liegt in Enterprise (`account_accountant`), im Community-Code nur die Definition |
| `hr_recruitment/models/hr_job_platform.py` + `hr_applicant.py` | Admin-Regex auf Betreff/Text, erster Treffer von `re.findall` | Admin-Regex **ohne Zeitgrenze** ist in Odoo übliche Praxis (auch oben) |
| `hr_expense/models/hr_expense.py` `_parse_price` | Betrag mit Währung aus Freitext: Symbole und ISO-Codes aus `res.currency`, längster Treffer gewinnt, `,`→`.` | Währungserkennung aus `res.currency` statt fester Liste |

### 2.2 Umwandeln und Prüfen der Werte – alles schon da

| Baustein | Befund (live im Test-Image geprüft, wo angegeben) | Einsatz |
|---|---|---|
| `python-stdnum` 1.19 (Odoo-Pflichtabhängigkeit, genutzt von `base_vat`) | `stdnum.iban.is_valid('DE89 3704 0044 0532 0130 00')` → True, letzte Ziffer verändert → False; `stdnum.eu.vat.is_valid('DE136695976')` → True/False entsprechend; außerdem `stdnum.bic`, `stdnum.iso11649` (RF-Referenz), `stdnum.de.handelsregisternummer` vorhanden (live) | **Prüfziffern** gegen OCR-Fehler und Fehltreffer: ein IBAN-Kandidat ohne gültige Prüfsumme wird verworfen |
| `babel` 2.10.3 (Pflichtabhängigkeit), `odoo.tools.misc.parse_date` | `babel.dates.parse_date('01.02.24', locale='de')` → 2024-02-01; `get_month_names('wide', locale='de')` → Januar, Februar, März …; `babel.numbers.parse_decimal('1.234,56', locale='de')` → 1234.56, mit `strict=True` wird `1,234.56` abgelehnt (live) | Datum in Zahlenform und mit Monatsnamen (Monatsnamen aus babel statt eigener Liste), Beträge |
| `base_import/models/base_import.py` `_infer_separators`, `DATE_PATTERNS` | Tausender-/Dezimaltrenner aus der Zahl selbst erschließen (zwei verschiedene Trennzeichen, das letzte kommt einmal vor → Dezimaltrenner); Datumsformate TT/MM/JJ in allen Trennzeichen-Varianten | Logik übernehmen (etwa 15 Zeilen, Quelle im Kommentar nennen); `base_import` ist keine Abhängigkeit des Moduls |
| `odoo/tools/mail.py` `email_re`, `email_normalize` | Mail-Adressen finden und vereinheitlichen | Typ „E-Mail“ |
| `odoo/addons/base/models/res_bank.py` | `sanitize_account_number`, gespeichertes `res.partner.bank.sanitized_acc_number` (in `base`) | IBAN → Kontakt |
| `base_iban` `validate_iban` | Prüfung mit Fehlermeldung | **nicht** nötig, `stdnum` reicht und ist ohne Zusatzmodul da |

### 2.3 Kontakt aus dem Dokument finden

`account/models/partner.py` `_import_retrieve_customer` mit **Suchplan**: Umsatzsteuer-ID (auch ohne Länderpräfix,
per SQL-Regex) → Bankkonto → Domain → E-Mail → Telefon → Name (`=ilike`); erster Treffer gewinnt, sortiert nach
`is_company DESC, supplier_rank DESC …`; wird von der E-Rechnungs-Einlese (`account_edi_ubl_cii`) genutzt.
`account` ist **keine** Abhängigkeit von `int_filemanager` → dasselbe Muster als kleiner eigener Suchplan auf
`res.partner` (Felder `vat`, `bank_ids.sanitized_acc_number`, `email` liegen in `base`/`mail`), nicht aufrufen.

### 2.4 Typisierte Werte speichern

| Stelle | Aufbau |
|---|---|
| `survey/models/survey_user_input.py` (`survey.user_input.line`) | `answer_type` + je Typ eine Spalte: `value_char_box`, `value_numerical_box`, `value_date`, `value_datetime`, `value_text_box`, `suggested_answer_id`; `display_name` je Typ berechnet |
| `mail/models/mail_tracking_value.py` | `field_id` + `old/new_value_integer/_float/_char/_text/_datetime` + `currency_id` |
| `product.attribute.custom.value` (v1-Vorbild) | nur `Char` |
| `fields.Properties` | wie in v1 verworfen: Definition als JSON an einem Trägerdatensatz, keine eigenen Datensätze zum Filtern/Auswerten |

→ **Typ an der Definition, je Typ eine Spalte am Wert** ist in Odoo selbst das Muster (und identisch mit Paperless, 3.3).
Zusammengesetzte Indizes gibt es als `models.Index` (`odoo/orm/table_objects.py`).

### 2.5 Später nützlich, nicht für Punkt 1

- **E-Rechnungen:** `account/models/account_document_import_mixin.py` (Decoder mit Priorität, `_unwrap_attachments`
  für eingebettete Dateien) und `account_edi_ubl_cii` (Factur-X/ZUGFeRD, UBL, XRechnung, `_import_retrieve_partner_vals`).
  Deutsche Eingangsrechnungen tragen zunehmend eingebettetes XML mit **exakten** Werten. Nach I11/I13 würde der
  **Umwandler** das XML auslesen und als JSON liefern; Odoo übernimmt es wie einen Mustertreffer (Quelle „E-Rechnung“).
- `base_automation`: Folgeaktionen auf neu übernommene Werte („Betrag > 1000 € → Aktivität“) ohne eigenen Code.

### 2.6 Was es im Community-Code nicht gibt

- **Keine** OCR- oder Wortbox-Auswertung: Suche nach `word_box`, `extract_word`, `box_layer`, `selected_status`,
  `ocr_word` ergibt 0 Treffer; `iap_extract`/`account_invoice_extract` (Rechnungserkennung mit Boxen) sind Enterprise
  und fehlen im Checkout.
- **Keine Zeitgrenze für Regex:** `regex`, `rapidfuzz`, `dateparser` sind im Image **nicht** installiert (live).
- **PostgreSQL-Regex ist kein Ersatz:** `regexp_instr` liefert zwar Positionen samt Erfassungsgruppe (live: 14/24),
  aber `\b` bedeutet dort Rückschritt statt Wortgrenze (`'a 12 b' ~ '\b12\b'` → false, mit `\y` → true, live).
  Bestehende Python-Muster würden still nichts mehr finden.

## 3. Befund Paperless-ngx (`paperless-ngx/paperless-ngx`, Stand `61f36eb` vom 2026-09-28, Version 3.2.1)

### 3.1 Zuordnen von Tags, Korrespondenten, Dokumenttypen (`src/documents/matching.py`)

- Jedes dieser Objekte trägt `match`, `matching_algorithm`, `is_insensitive`. Verfahren: keins, irgendein Wort, alle
  Wörter, exakte Wortfolge (immer mit Wortgrenzen `\b…\b`), Regex, unscharf (`rapidfuzz.partial_ratio` ≥ 90 nach
  Entfernen der Satzzeichen), automatisch (siehe 3.4). Dieselben Verfahren nutzen die Workflow-Auslöser.
- Beim Einlesen werden Treffer **ohne Rückfrage** gesetzt (`signals/handlers.py`, bei mehreren der erste);
  in der Oberfläche gibt es zusätzlich Vorschläge.

### 3.2 Regex sicher ausführen (`src/documents/regex.py`)

`safe_regex_search` nutzt die Bibliothek `regex` mit **0,1 s Zeitgrenze**; Syntaxfehler und Zeitüberschreitung
zählen als „kein Treffer“ und werden geprotokolliert. Muster werden beim Speichern mit `regex.compile` geprüft.

### 3.3 Eigene Felder (`CustomField`/`CustomFieldInstance` in `models.py`)

`CustomField`: eindeutiger `name`, `data_type` (Text, URL, Datum, Ja/Nein, Ganzzahl, Kommazahl, Geldbetrag,
Dokumentverweis, Auswahl, Langtext), `extra_data` (z. B. Auswahloptionen). `CustomFieldInstance`: `document`,
`field` und **eine Spalte je Typ** (`value_text`, `value_date`, `value_int`, `value_float`, `value_monetary` als
Text „EUR12.50“ plus berechnete Dezimalspalte, …), Indizes `(field, value_date)`, `(field, value_int)`,
`(field, value_float)` usw.

**Wichtig:** Paperless **liest keine Feldwerte aus dem Dokumenttext**. Eigene Felder werden nur von Hand oder per
Workflow mit festen Werten gesetzt; der optionale KI-Teil (`src/paperless_ai`, auch mit lokalem Modell) schlägt nur
Titel, Tags, Korrespondent, Dokumenttyp, Ablagepfad und Datum vor. Unsere Muster → typisierter Wert gehen also
über Paperless hinaus; das **Speichermodell** übernehmen wir.

### 3.4 Datum, Vorschläge, Lernen

- **Datum** (`plugins/date_parsing/`): ein Regex für Zahlen- und Monatsnamenformen, dann `dateparser` mit
  `DATE_ORDER=DMY`; verworfen wird, was vor 1900 oder in der Zukunft liegt oder auf der Ignorierliste steht;
  vorgeschlagen werden die ersten 3 verschiedenen Daten.
- **Vorschläge** (`views.py`, `/suggestions/`): bei Bedarf berechnet, im Cache gehalten, bei jeder Änderung des
  Dokuments verworfen; nur Objekte, die der Nutzer sehen darf; Text über 1,2 Mio. Zeichen wird auf Anfang (80 %) und
  Ende (20 %) gekürzt; Grundlage ist der Text der **neuesten Fassung**.
- **Automatisch** (`classifier.py`): neuronales Netz (scikit-learn `MLPClassifier`) auf Wortzählungen, trainiert
  auf den vom Nutzer gesetzten Zuordnungen. Braucht scikit-learn und ein Trainingsjob – nicht für Punkt 1.

## 4. Vorschlag Datenmodell

> **Geändert 2026-09-29 (bei der Vorbereitung von W-2, verbindlich statt 4.2/4.3 unten):** v2 bekommt **eigene,
> neue Modelle**; die v1-Modelle `extraction_pattern`/`extracted_value` bleiben bis Schritt 8 unverändert und werden
> dort übernommen (Muster → Regel im Regex-Modus, `target_field` → Feld, Werte → `field_value`) und gelöscht.
> Gründe, im Code nachgesehen: (1) die generierten v1-Schutzordner-Regeln auf `extracted_value` filtern über
> `file_id.path` (`acl_rules.py`, `MODELS`) – v2-Zeilen ohne `file_id` wären für Nicht-Admins unsichtbar;
> (2) v1s `_match_patterns` (`fulltext.py`) liest **alle** aktiven Muster und würde v2-Regeln im v1-Dialog verwenden;
> (3) der Stichwort-Modus (E8) und die Wertarten aus den Proben (8) passen nicht in v1s „ein Regex je Muster“.
> Neue Modelle (Namen vorläufig, beim Bau festlegen):
> - `int_filemanager.extraction_field` wie 4.1, Wertarten nach den Proben: Nummer (auch in Leerzeichen-Gruppen),
>   Wort, Datum, Zeitraum oder Dauer, Geldbetrag, Menge mit Einheit (ct/kWh, kWh, €/Monat), IBAN, USt-IdNr., E-Mail;
>   dazu Einheit/Währung als Einstellung des Felds.
> - `int_filemanager.extraction_rule`: `field_id`, `sequence`, `active`, `mode` (`keyword` | `regex`), `keywords`
>   (eine Zeile je Stichwort), `pattern`/`group_index`/`ignore_case` für den Regex-Modus.
> - `int_filemanager.field_value`: wie 4.3, aber `rule_id` statt `pattern_id`, ohne `file_id`; typisierte Spalten
>   `value_text` (immer, normalisiert), `value_date`, `value_date_to`, `value_number` + `currency_id`/`unit`.
> - Knoten: `field_value_ids`. Rechte wie 5.3 (Lesen entlang des Knotens, Schreiben nur über die Methode).
>
> Ursprünglicher Text (überholt): Die Modellnamen aus v1 bleiben (Konzept 4: „werden auf den Knoten umgehängt“);
> Änderungen sind additiv, damit v1 bis Schritt 8 läuft.

### 4.1 `int_filemanager.extraction_field` (neu) – „Was wird gesucht“

| Feld | Bedeutung |
|---|---|
| `name` | Anzeigename, z. B. „Rechnungsnummer“; eindeutig |
| `value_type` | `char`, `date`, `amount`, `iban`, `vat`, `email` (Umwandlung und Prüfung je Typ, 5.2) |
| `sequence`, `active` | Reihenfolge im späteren Prüf-Dialog, Abschalten statt Löschen |
| `pattern_ids` | mehrere Muster je Feld (z. B. „Rechnungsnr.“, „Invoice No.“, „Beleg-Nr.“) |

Grund für die Trennung: v1 kennt je Muster einen Wert, dadurch stehen bei drei Mustern für die Rechnungsnummer drei
Zeilen im Dialog. Mit Feld und Muster gibt es eine Zeile je Feld, die Muster sind Suchwege dorthin (wie `barcode.rule`
→ Typ, Paperless `CustomField`).

### 4.2 `int_filemanager.extraction_pattern` (erweitert) – „Wie wird gesucht“

Neu `field_id` (für v2 Pflicht, v1-Muster ohne Feld werden von v2 ignoriert); bleibt: `pattern`, `ignore_case`,
`group_index`, `sequence`, `active`, Prüfung beim Speichern. `target_field` bleibt bis Schritt 8 für v1.
Startbelegung: die drei v1-Muster plus IBAN, USt-IdNr., E-Mail (Typen mit Prüfziffer brauchen nur ein grobes Muster,
die Prüfung filtert).

### 4.3 `int_filemanager.extracted_value` (erweitert) – „Was bestätigt wurde“

| Feld | Bedeutung |
|---|---|
| `node_id` | Knoten (Kaskade); `file_id` bleibt für v1, **genau eins** von beiden gesetzt |
| `revision_id` | Fassung, aus deren Text der Wert bestätigt wurde → später Hinweis „Werte stammen aus Fassung 3, aktuell ist 5“ |
| `field_id` | Feld; **eindeutig je Knoten** (`node_id, field_id`), ein Wert je Feld |
| `pattern_id` | Muster, das den Wert fand; leer = von Hand eingegeben |
| `source` | `pattern`, `manual` (später `einvoice`) |
| `value` | Text wie im Dokument gefunden (bleibt, v1 nutzt es) |
| `value_char`, `value_date`, `value_amount` + `currency_id` | typisierter Wert, genau die Spalte zum Typ; Indizes `(field_id, value_date)`, `(field_id, value_amount)`, Trigram auf `value_char` |
| `page`, `x0`, `top`, `x1`, `bottom` | Position in PDF-Punkten, oben links (pdfplumber); leer bei Textdateien |

Am Knoten: `extracted_value_ids` (One2many), damit „alle Dateien mit Rechnungsnummer X“ eine normale Domain ist.

## 5. Vorschlag Ablauf

### 5.1 Vorschlagen (nur lesend, bei Bedarf berechnet, nichts gespeichert)

Wie v1 und Paperless: Vorschläge werden nicht gespeichert, weil sich Muster jederzeit ändern und gespeicherte
Vorschläge dann veralten.

1. Rechte: Knoten lesen (`check_access('read')` unter der Nutzeridentität, kein `sudo` davor).
2. Text der **aktuellen Fassung**: `derivative.text` der Art `text` bzw. `words` (siehe 5.4). Fehlt er noch (OCR läuft),
   Rückgabe „noch nicht bereit“ statt leerer Vorschläge.
3. Je Feld (Reihenfolge `sequence`) alle Muster (Reihenfolge `sequence`), **alle** Treffer per `finditer`, bis
   5 gültige Kandidaten je Feld.
4. Umwandeln und prüfen je Typ: `date` (Zahlenformen nach `DATE_PATTERNS`-Art mit Tag vor Monat, Monatsnamen aus
   babel; verwerfen vor 1900 und mehr als ein Jahr in der Zukunft), `amount` (Trenner erschließen wie
   `_infer_separators`, Währung aus `res.currency` wie `_parse_price`, Standard EUR), `iban`/`vat` (`stdnum`,
   gespeichert in kompakter Form), `email` (`email_normalize`), `char` (Leerraum zusammenfassen).
   Ungültige Kandidaten fallen heraus – daran scheitern die meisten OCR-Fehltreffer.
5. Position je Kandidat über die Wortliste (Zeichenbereich → Wörter → umschließende Box, nur auf einer Seite).
6. Kontakt-Vorschlag nach dem Suchplan aus 2.3: gefundene USt-IdNr. → IBAN → E-Mail → Name (Namen ab 5 Zeichen als
   Wort im Text, Firmen zuerst, per SQL statt 2000 Kontakte in Python). Tag-Vorschlag wie v1, aber mit Wortgrenzen
   (Paperless „exakte Wortfolge“).
7. Ergebnis je Feld: Standardvorschlag (erster gültiger Kandidat), Alternativen, bereits bestätigter Wert, dazu
   `revision_id` der ausgewerteten Fassung.

### 5.2 Übernehmen

1. Rechte: Knoten schreiben (`check_access('write')`), erst danach `sudo` nur für die Wert-Zeilen.
2. Der Client schickt `revision_id` mit; ist das nicht mehr die aktuelle Fassung → `UserError` (wie die
   Basisfassungs-Prüfung I6), damit kein Wert aus einer alten Fassung als aktuell gilt.
3. Werte werden **auf dem Server** erneut umgewandelt und geprüft (der Client liefert nur Feld, Text, Position);
   Ersetzen **je Feld**, nicht die ganze Liste; leerer Wert löscht das Feld.
4. Kontakt und Tags werden als der Nutzer über das normale ORM gesetzt (Rechte greifen von selbst).
5. Eine Chatter-Notiz am Knoten („Werte übernommen: …“) als Nachweis.

### 5.3 Rechte und N1

- Beide Methoden arbeiten auf dem Knoten-Datensatz und prüfen selbst; sie sind damit über JSON-2 **und** `call_kw`
  sicher (Befund A2). Kein Pfad-Parameter, kein `sudo` vor der Prüfung.
- `extracted_value`: Lesen über `ir.rule` entlang des Knotens (wie Revision, Befund A1), **kein** Schreibrecht für
  Nutzer (nur über die Methode). Feld und Muster: lesen alle Nutzer, schreiben nur Verwalter.
- Die v1-Methoden bleiben bis Schritt 8 im Code und damit **offen**; für die laufende v1-Instanz auf HM-SRV bleibt
  die separate Behebung von N1 nötig (Übergabe 6).

### 5.4 Nebenbei im Umwandler: Wortliste Version 2

Vorschlag, **jetzt** zu ändern, weil die neue Version alle `words`-Aufträge neu anstößt (heute nur Testdaten auf
Tower, nach Schritt 8 tausende OCR-Läufe):

- **Zeichenbereich je Wort** (`start`, `end`) ausdrücklich in der JSON statt stillschweigend aus der
  Zusammensetzung des Texts nachgerechnet; bei gekürztem Text oder mehr als 500.000 Wörtern bricht die Zuordnung
  sonst unbemerkt.
- **Zeilenumbrüche** zwischen Textzeilen (heute nur zwischen Seiten): Muster wie „Rechnungsnr.: (…) am Zeilenende“
  werden möglich, Treffer laufen nicht mehr über Spalten hinweg.
- **Seitenmaße und Drehung** je Seite: braucht der Hervorhebungs-Viewer; ob pdfplumber-Koordinaten bei gedrehten
  Seiten und abweichender CropBox zu pdf.js passen, ist im Viewer-Schritt zu prüfen – mit den Maßen in der Datei ist
  das ohne neuen OCR-Lauf nachholbar.
- **Text zusätzlich in `derivative.text`**: dann haben die Volltextsuche (Konzept 9) und die Werterkennung den Text
  in der Datenbank; die JSON-Datei wird nur für Positionen gelesen.

### 5.5 Sicherheit der Muster

Ein ungünstiges Muster (verschachtelte Wiederholungen) kann an einem passenden Text minutenlang rechnen und einen
Worker blockieren. Odoo selbst nimmt das bei Admin-Regex hin (2.1). Vorschlag: Muster nur für Verwalter, Text auf
2 Mio. Zeichen begrenzt (wie im Umwandler), Rechenzeit je Muster messen und über 1 s im Log melden, beim Speichern
gegen einen Beispieltext testen. Die Grenze des Workers (`limit_time_real`) bleibt das Netz. Alternativen stehen in
Entscheidung E3.

## 6. Scheiben und Abnahme

| # | Inhalt | Abnahme |
|---|---|---|
| W-1 | Umwandler: Wortliste v2 (5.4), Text in `derivative.text` | Umwandler-Tests; `run_formats.py` über die 95 Testdateien ohne Unerwartetes; Zeichenbereiche stimmen mit dem Text überein (Test über alle Wörter) |
| W-2 | Datenmodell 4 (geänderte Fassung), Rechte, Startbelegung, `de.po` | Frischinstallation + Update von 19.0.1.15.0; A1-Test (Nicht-Admin sieht Werte fremder Bereiche nicht) |
| W-3 | Umwandeln/Prüfen je Typ als reine Funktionen | Tabellentests mit Grenzfällen (OCR-Fehler, `1.234,56`/`1,234.56`/`1234,5`, Monatsnamen, IBAN mit Leerzeichen, USt-IdNr. ohne Präfix) |
| W-4 | Vorschlagen (5.1) inkl. Kontakt/Tags | Odoo-Tests; kalter Cache (`invalidate_all`, Lehre aus dem `sudo`-Fehler in Schritt 3) |
| W-5 | Übernehmen (5.2), N1 | HttpCase: Nicht-Admin per `call_kw` und JSON-2 auf fremden Knoten → Zugriff verweigert; alte `revision_id` → Fehler |
| W-6 | **Messung an echten Dokumenten**: 20–30 echte Rechnungen/Briefe mit Sollwerten in einer TSV-Datei (Ablage nur auf Tower, nicht im Repo – Kundendaten) | Trefferquote je Feld dokumentiert; Zielwert legt der Nutzer nach der ersten Messung fest |

**Stand W-1 (2026-09-29):** gebaut und getestet.
- Umwandler (`tools/fmconverter/worker.py`): Wortliste **v2** = `{"version": 2, "ocr": "none"|"redo-ocr"|"force-ocr",
  "pages": [{width, height, rotation}], "text", "words": [[page, x0, top, x1, bottom, start, end]]}`,
  `text[start:end]` ist das Wort; Zeilen `\n`, Spaltenlücke (> 1,5 × Texthöhe) `\t`, Seiten `\f`. Scans (≥ 50 % der
  Seiten zu ≥ 50 % von einem Bild bedeckt) werden **auch mit Scanner-Text** neu erkannt (`--redo-ocr`, bei Fehler
  `--force-ocr`); unter 20 Zeichen je Seite wie bisher `--force-ocr`. 55 Umwandler-Tests grün (neu: Zeilen/Spalten/
  Zeichenbereiche, Seitenumbruch, Scan mit falscher Scanner-Ebene, Rückfall redo → force).
- Messung vorab an der Sammlung (513 PDFs): 343 digital, 94 Scans ohne Text, **76 Scans mit Scanner-Text**
  (v. a. Canon „IJ Scan Utility“, PDF24). Stichprobe 12: `--redo-ocr` nie schlechter als der Scanner-Text, bei
  Canon-Scans saubere Wörter 10 → 47 %, 33 → 62 %, 53 → 79 %; kein doppelter Text; 1 × Abbruch (PDF24) → Rückfall.
- Odoo: `WORDS_SPEC = "v2"`; **Fehler behoben:** `_enqueue_missing` zählte alle Zeilen eines Blobs, eine neue Spec
  (Wortliste, Kachelgröße) wäre nie nachgeholt worden – zählt jetzt nur Zeilen aus `derivative_plan.CURRENT_JOBS`;
  neu `_drop_outdated_jobs` (löscht Zeilen alter Specs, laufende erst nach Antwort); Text der Wortliste zusätzlich
  in `derivative.text` (`_words_text`, Grenze `MAX_WORDS_BYTES`). Neue Odoo-Tests in `test_v2_derivative_kinds.py`.
- Tests: 55 Umwandler-Tests, 400 Odoo-Tests grün, pre-commit grün. `race.sh` nach W-1 nicht erneut gelaufen.
- **Lauf über die ganze Sammlung (2026-09-29, Container `wk_runall`, danach entfernt):** 513 PDFs in 27 min,
  **0 Fehler, 0 kaputte Zeichenbereiche**. Art: 343 digital (`none`), 97 neu erkannt (`force-ocr`, davon 3 als
  Rückfall nach gescheitertem `--redo-ocr`), 73 Scans mit Scanner-Text neu erkannt (`redo-ocr`). Anteil sauberer
  Wörter bei diesen 73: **0,71 → 0,80**, 57 besser, **8 schlechter**; bei den 3 Rückfällen 0,86 → 0,84. Langsamste
  Datei 43 s (21 Seiten). Die 8 schlechteren sind bei W-6 anzusehen (Maß „sauber“ ist grob: Wörter aus Buchstaben
  und Ziffern ohne Sonderzeichen; ob der Wert dort trotzdem gefunden wird, zeigt erst die Messung mit Sollwerten).

**Stand W-2 (2026-09-29):** gebaut, Modulversion 19.0.1.16.0.
- Neue Modelle (Dateien `models/int_filemanager_extraction_field.py`, `…_extraction_rule.py`, `…_field_value.py`):
  - `int_filemanager.extraction_field`: `name` (übersetzbar, eindeutig ohne Groß-/Kleinschreibung, Prüfung in
    Python, weil übersetzte Namen als JSON gespeichert sind), `sequence`, `active`, `value_type` (`number`, `word`,
    `date`, `period` = Zeitraum oder Dauer, `amount`, `quantity`, `iban`, `vat`, `email`), `unit` (Pflicht bei
    `quantity`), `currency_id` (Währung, falls der Betrag keine trägt). Die Art lässt sich nicht mehr ändern, sobald
    Werte existieren (sonst passen die gespeicherten Spalten nicht mehr) – dann archivieren und neu anlegen.
  - `int_filemanager.extraction_rule`: `field_id` (Kaskade), `sequence`, `active`, `mode` (`keyword`/`regex`),
    `keywords` (eine Zeile je Stichwort, nicht übersetzt – es sind Wörter im Dokument), `pattern`, `group_index`,
    `ignore_case`; beim Speichern geprüft: mindestens ein Stichwort bzw. gültiger Regex mit vorhandener Gruppe.
  - `int_filemanager.field_value`: `node_id` (Kaskade), `field_id` (**restrict** – ein Feld mit Werten wird
    archiviert, nicht gelöscht), `revision_id`, `rule_id`, `source` (`rule`/`manual`), `source_text` (wie gedruckt),
    `value_text` (normalisiert, immer gesetzt, Trigramm-Index), `value_date`, `value_date_to`, `value_number`,
    `currency_id`, `unit`, Position `page/x0/top/x1/bottom`; eindeutig `(node_id, field_id)`; Indizes
    `(field_id, value_date)`, `(field_id, value_number)`; Prüfung, dass **genau** die Spalten der Art gesetzt sind
    (Datum; Zeitraum = zwei Daten in richtiger Reihenfolge **oder** Zahl mit Einheit; Betrag mit Währung; Menge mit
    Einheit; Textarten nur `value_text`), und dass `revision_id` zum selben Knoten und `rule_id` zum selben Feld
    gehören (beides nach Gegenlesen durch Codex verschärft bzw. ergänzt). Ein Betrag von 0 ist nicht von „fehlt“ zu
    unterscheiden (Odoo speichert eine fehlende Kommazahl als 0) – W-5 setzt Beträge immer aus dem Umwandeln.
  - Bewusst hingenommen (Codex, niedrig): die Namens-Eindeutigkeit ist eine Python-Prüfung; legen zwei Verwalter
    im selben Augenblick gleichnamige Felder an, kommen beide durch. Ein Datenbank-Index auf den englischen Namen
    würde nach einer Umbenennung in der deutschen Oberfläche falsche Konflikte melden.
  - Knoten: `field_value_ids`.
- Rechte: Felder und Regeln lesen alle Dateimanager-Nutzer, ändern nur Verwalter; Werte nur lesen, per `ir.rule`
  entlang des Knoten-Bereichs (`int_filemanager_field_value_security.xml`), **kein Schreibrecht für irgendwen** über
  das ORM – geschrieben wird in W-5 über die geprüfte Knoten-Methode.
- Startbelegung `data/int_filemanager_extraction_field.xml` (`noupdate`, damit gelernte Synonyme ein Update
  überleben): die 18 Felder des Stichwort-Katalogs aus `keyword_search.py` (Zeitraum/Dauer/„Zeitraum oder Dauer“
  zusammengefasst als `period`, ct/kWh und kWh als `quantity` mit Einheit), dazu IBAN und USt-IdNr. (Stichwörter)
  und E-Mail (grobes Regex-Muster); Namen englisch, deutsch über `de.po`.
- `po_tool.py` kennt die neuen Modelle und die Namen der Startbelegung; `de.po` neu erzeugt (dabei auch zwei in
  W-1 vergessene Begriffe des Umwandlers übersetzt: „Converter Job“, „Text and word positions“).
- Tests `tests/test_v2_field_value.py` (13): A1 für Werte (fremder Bereich unsichtbar, auch über die Knoten-Suche),
  niemand schreibt Werte über das ORM (auch Verwalter nicht), Rechte an Feldern/Regeln, Eindeutigkeit je Feld und
  Knoten, Kaskade beim Löschen des Knotens, Feld mit Werten nur archivierbar, Art-Wechsel gesperrt, Einheit bei
  Menge, Spalte passt zur Art, Fassung und Regel gehören zum Wert, Regelprüfung, Startbelegung vollständig.
- Abnahme: Frischinstallation mit allen Tests (413 grün), Update von 19.0.1.15.0 (Stand `HEAD`, mit Deutsch) auf
  19.0.1.16.0 ohne Fehler – 21 Felder, 21 Regeln, deutsche Namen, alle Indizes da; pre-commit und
  `v2check.sh` ohne neuen Befund; gegengelesen mit Codex (`-m gpt-5.6-sol`, das in `~/.codex/config.toml`
  eingestellte `gpt-6-sol` ist für das ChatGPT-Konto nicht freigegeben).
- Aus 5.5 offen für W-4: Rechenzeit je Muster messen und über 1 s melden (gehört zur Ausführung, nicht zum
  Speichern).

**Stand W-3 (2026-09-29):** gebaut, ohne Datenbankzugriff in `int_filemanager/value_types.py`.
- `find(value_type, text, pos, endpos, unit=, currencies=, default_currency=, default_country=, today=)` liefert
  alle gültigen Kandidaten einer Art von links nach rechts (Anfang, Ende, gedruckter Text, Spalten für
  `field_value` mit Währung als ISO-Code); `parse(value_type, text)` nimmt nur einen Text, der ganz ein Wert ist
  (für das erneute Prüfen auf dem Server in W-5). Ein Wert überschreitet nie Tabulator, Zeilen- oder Seitenumbruch.
- Je Art: **Nummer** (Gruppen mit Leerzeichen „836 585 797 780“ vor Einzelwort, gespeichert ohne Leerzeichen,
  mindestens eine Ziffer), **Wort** (bis 5 Wörter einer Zeile/Spalte, beginnt mit Buchstaben), **Datum** (T.M.J mit
  `.`/`/`/`-`, ISO, Monatsnamen deutsch und englisch aus babel; zweistellige Jahre bis heute + 10 im 21.
  Jahrhundert), **Zeitraum** (zwei Daten mit „-“, „–“, „bis (zum)“; das erste Datum darf ohne Jahr sein und nimmt
  es vom zweiten, über den Jahreswechsel eins zurück) **oder Dauer** („12 Monate“ → 12 months), **Betrag**
  (Trennzeichen nach `base_import._infer_separators`, Tausendergruppen müssen dreistellig sein; Währung vor oder
  hinter der Zahl, auch „EUR/Monat 10,90“ und „13,40 €/Monat“; Minus vorn oder hinten; ohne Währung nur mit genau
  zwei Nachkommastellen, dann Standardwährung; normales Leerzeichen trennt nie Tausender, damit „Pos. 3 250,00“ nicht
  verschmilzt), **Menge** (Einheit des Felds vor oder hinter der Zahl, Schreibweisen wie „Cent / kWh“ für ct/kWh),
  **IBAN** und **USt-IdNr.** (Prüfziffer; ein folgendes Wort wie „BIC …“ wird abgeschnitten; USt-IdNr. ohne
  Länderkürzel bekommt `default_country`), **E-Mail** (Leerzeichen um „@“ entfernt, `email_normalize`).
- **Reparatur von Lesefehlern** (O→0, I/l/|→1, S→5, B→8, Z→2, G→6, D/Q→0) nur bei IBAN und USt-IdNr., nur an
  Stellen, an denen das Länderformat eine Ziffer verlangt, und nur übernommen, wenn die Prüfziffer danach stimmt.
- **Befund Odoo (live geprüft):** `stdnum.iban` lässt sich **innerhalb von Odoo nicht importieren**. Odoos
  Import-Haken für `stdnum` (`odoo/_monkeypatches/__init__.py`, `PatchImportHook`) ersetzt den Lader des Pakets,
  danach kann `importlib.resources` die Datei `iban.dat` nicht öffnen („Can't open orphan path“); Odoo selbst
  nutzt `stdnum.iban` nirgends. Deshalb liest `value_types` dieselbe Datei über ihren Pfad mit dem öffentlichen
  `stdnum.numdb.read` und prüft wie `stdnum.iban.is_valid` (Länderformat + Modulo 97). `stdnum.eu.vat` ist nicht
  betroffen.
- **Abweichung von 5.1:** Daten werden erst verworfen, wenn sie vor 1900 oder **mehr als 30 Jahre** in der Zukunft
  liegen (nicht schon nach einem Jahr) – Verträge in der Sammlung nennen Laufzeit- und Preisgarantie-Enden Jahre
  voraus; die Grenze fängt Lesefehler wie „2924“.
- **Gegengelesen mit Codex, 8 Befunde, alle behoben:** Suchfenster schnitt Werte ab (jetzt: Kandidaten, die im
  Fenster **beginnen**, dürfen darüber hinausgehen); `parse` machte aus Tabulator/Zeilenumbruch ein Leerzeichen
  (jetzt nur Leerzeichen aufgeräumt); Datum in Kennungen wie „INV-01-02-2024-A“; Absturz bei ungewöhnlichen
  Großbuchstaben im Monatsnamen; „12 kWh/Tag“ als kWh; 29.02. ohne Jahr im Zeitraum; formal ungültige E-Mail-Adressen;
  400-stellige Zahl als „unendlich“ (jetzt höchstens 15 Ziffern). Die erste Fassung der Datumsgrenze war zu streng:
  an der Sammlung gemessen fielen 730 Daten weg, davon 441 echte, an die PDF-Text das nächste Wort ohne Leerzeichen
  hängt („01.02.2024Seite“), und 156 mit Uhrzeit („2024-01-01T12:00“); jetzt sind Buchstaben direkt daneben erlaubt,
  abgelehnt wird nur die Verkettung mit Bindestrich – danach fallen 101 weg, fast alle Kennungen.
- Tests `tests/test_v2_value_types.py` (22, Tabellen mit Grenzfällen aus den Proben: Zahlenschreibweisen, OCR-Fehler,
  Monatsnamen, Zeitraum über den Jahreswechsel, IBAN mit „O“/„l“, maskierte IBAN, Gläubiger-ID, USt-IdNr. ohne
  Präfix und mit „l“, Offsets).
- **Lauf über die Sammlung** (alle Suchen über die 513 Wortlisten, 3,7 Mio. Zeichen, im Container ohne Netz):
  0 Fehler, langsamste Suche 26 ms je Dokument. Für W-4: Suchen über den **ganzen** Text liefern bei USt-IdNr.
  ohne Präfix Fehltreffer (etwa jede zehnte 9-stellige Zahl hat eine gültige deutsche Prüfziffer) – USt-IdNr. und
  Nummern nur in der Nähe eines Stichworts suchen.

## 7. Entscheidungen

**Alle Empfehlungen E1–E9 vom Nutzer übernommen (2026-09-29, „dann leg los“).** Ergänzend aus den Proben (8):
Stichwort-Modus sucht im Text und nach Seitenlage; „Wert anklicken und Stichwort lernen“ für die Oberfläche
vorgemerkt; kein Einzeichnen von Feldern auf dem PDF.

| # | Frage | Empfehlung (übernommen) |
|---|---|---|
| E1 | Feld-Definition als eigenes Modell (4.1) oder bei v1s „ein Muster = ein Wert“ bleiben? | eigenes Modell |
| E2 | Vorschläge nur bei Bedarf berechnen oder gespeichert (z. B. für eine spätere Liste „ungeprüfte Eingänge“)? | bei Bedarf; Speichern erst, wenn die Liste gebraucht wird (Schritt 7, Eingangsordner) |
| E3 | Schutz vor langsamen Mustern: (a) wie 5.5, (b) Bibliothek `regex` mit Zeitgrenze ins Odoo-Image, (c) Muster im Umwandler ausführen (weicht von Entscheidung 14 ab) | (a); (b) nur, wenn ein eigenes Image ohnehin gebaut wird |
| E4 | Wortliste v2 jetzt (5.4)? | ja, jetzt |
| E5 | Kontakt- und Tag-Vorschlag gehören zu Punkt 1? | ja (v1 hatte sie; Suchplan statt 2000-Kontakte-Schleife) |
| E6 | Ein Wert je Feld und Knoten? | ja; mehrere Werte je Feld später bei Bedarf |
| E7 | Automatisch übernehmen ohne Prüfung (wie Paperless beim Einlesen)? | nein, Prüfung wie v1; frühestens mit dem Eingangsordner neu entscheiden |

| E8 | Einfacher **Stichwort-Modus** für eigene Felder (Stichwörter + Art eintragen, das System baut das Suchmuster), Regex nur für Sonderfälle | ja – ohne ihn kann ein Nicht-Programmierer keine eigenen Felder anlegen |
| E9 | Vorhandene Textebenen gescannter PDFs neu erkennen (OCRmyPDF `--redo-ocr`, ersetzt nur unsichtbaren Scanner-Text, echter Text bleibt) statt ihnen zu vertrauen | ja (siehe 8) |

**Bewusst nicht in Punkt 1:** Oberfläche und Hervorhebungs-Viewer; E-Rechnungs-XML (2.5); Zuordnungsregeln an Tags
nach Paperless-Art; Lernen/KI; OCR für Bilddateien (JPG/TIFF-Scans bekommen heute keine `words` und damit keine
Werte – Lücke für den Eingangsordner vormerken); Muster nur für bestimmte Ordner/Bereiche.

## 8. Probe an einem echten Dokument (2026-09-29)

Ein vom Nutzer bereitgestellter Gebührenbescheid (2 Seiten, Scan mit eingebetteter Textebene des Scanners) lief durch
den Umwandler (`fmconverter:dev`, Wegwerf-Container ohne Netz) und durch die geplanten Felder mit Prüfung. Die Kopie
wurde danach auf Tower gelöscht; hier stehen bewusst keine persönlichen Daten.

- **Die Textebene des Scanners war schlecht**, der Umwandler hat ihr trotzdem vertraut (genug Zeichen je Seite → keine
  eigene Texterkennung): Datum als „27.0'1 .2025“, Beträge als „152/0 €“ und „231 60 €“, ein Zeichen der
  Rechnungsnummer falsch, USt-IdNr. mit „l“ statt „I“, Fußzeile als Buchstabensalat. **Erzwungene neue Erkennung**
  (OCRmyPDF, 8 s für 2 Seiten) las fast alles richtig; die Rechnungsnummer am Bild nachgeprüft. → E9; zu prüfen, wie
  der Umwandler Scans mit Textebene von echten digitalen PDFs unterscheidet (`--redo-ocr` erkennt das selbst).
- **„Erstes Datum“/„erster Betrag“ taugen nicht:** der erste Betrag war eine Einzelposition, nicht der Gesamtbetrag.
  Mit Stichwort („Gesamtbetrag“) kam der richtige Wert. → Standardfelder an Stichwörter binden (Rechnungsdatum,
  Gesamtbetrag, Fälligkeitsdatum), E8.
- **Prüfziffern wirken:** USt-IdNr. und zwei Bank-IBANs gültig erkannt; die Gläubiger-ID (sieht aus wie eine IBAN)
  richtig verworfen (`stdnum.eu.at_02` erkennt sie als Gläubiger-ID); eine IBAN mit „O“ statt „0“ verworfen – nach
  Tausch ist sie gültig. → **Reparatur typischer Verwechslungen** (O/0, I/l/1, S/5, B/8) nur an Stellen, an denen
  Ziffern stehen müssen, und nur übernehmen, wenn die Prüfziffer danach stimmt.
- **Stichwörter brauchen eine Grenze:** „Kundennummer an.“ im Fließtext lieferte „an.“ als Wert. → Im Stichwort-Modus
  muss ein Nummernfeld mindestens eine Ziffer enthalten, und direkt nach dem Stichwort darf nur „:“ oder Leerraum
  stehen.
- Eine E-Mail-Adresse wurde durch ein eingeschobenes Leerzeichen („name @domain“) nicht erkannt → Leerzeichen um
  „@“ vor der Suche entfernen.
- Das Dokument trägt einen **QR-Code**; ob er strukturierte Daten enthält (z. B. Überweisungsdaten), ist offen –
  Auslesen wäre ein späterer Baustein im Umwandler.

**Zweite Probe: digital erzeugte Telefonrechnung** (3 Seiten, ohne eingebettete E-Rechnung; Kopie danach gelöscht):
fehlerfreie Textebene, 0,2 s. Ein nachgebauter **Stichwort-Modus** (Stichwörter + Art Nummer/Datum/Betrag, Nummer muss
eine Ziffer enthalten) fand alle sieben Probefelder richtig: Rechnungs-, Kunden-, Vertragsnummer, Mandatsreferenz,
Rechnungsdatum, Abbuchungsdatum, Gesamtbetrag. Prüfziffern: Firmen-IBAN und USt-IdNr. gültig, Gläubiger-ID erkannt,
die **gekürzt gedruckte Kunden-IBAN** („DE** 5625 ****…“) richtig verworfen. Die alten v1-Muster lagen hier zufällig
richtig (erstes Datum = Rechnungsdatum, erster Betrag = Gesamtbetrag) – beim Gebührenbescheid nicht. **Grenze des
Stichwort-Modus:** Werte in Tabellen (Kopfzeile „Netto Steuer Brutto“, Zahlen darunter) findet er nicht; dafür
bräuchte es eine Option „n-ter Betrag nach dem Stichwort“ oder ein Regex-Muster.

**Dritte Probe: digital erzeugte Vertragsbestätigung Strom, zweispaltig gesetzt** (2 Seiten; Kopie danach gelöscht).
Im Text stehen Beschriftungen paarweise vor ihren Werten („Grundpreis Geschätzter Jahresverbrauch 13,40 €/Monat
3000 kWh“), weil die Wortliste Zeile für Zeile über beide Spalten läuft. 15 Probefelder mit zwei Suchweisen:
**A** Wert innerhalb der nächsten 6 Wörter im Text, **B** Wert rechts daneben oder direkt darunter in derselben
Spalte (über die Wortpositionen). A fand 13, B fand 10, **beide zusammen (B vor A) 15 von 15 richtig**: Kundennummer,
Dokumentdatum, Lieferbeginn (im Fließtext), Zählernummer, Tarifname, Abschlag, Fälligkeit erster Abschlag, Grundpreis,
Arbeitspreis, Jahresverbrauch, Preisgarantie-Zeitraum, Mindestlaufzeit, Kündigungsfrist, USt-IdNr. (Prüfziffer ok),
Handelsregisternummer. A allein liefert beim Tarifnamen die Nachbarbeschriftung („Fälligkeitstag“), B allein verpasst
Werte im Fließtext. Folgerungen für den Entwurf:
- Stichwort-Modus sucht **in beiden Richtungen** (Text dahinter und Seitenlage rechts/darunter); das macht auch die
  Tabellenwerte der zweiten Probe (Netto/Steuer unter ihrer Kopfzeile) erreichbar.
- Die **Art** des Werts filtert entscheidend (ohne sie würde „Grundpreis“ den Jahresverbrauch greifen). Zusätzlich zu
  Nummer/Datum/Betrag nötig: **Zeitraum** (von–bis), **Dauer** (12 Monate, 30 Tage), **Wert mit Einheit**
  (ct/kWh, kWh, €/Monat), **Wort** (Tarifname).
- Die Suche nach Seitenlage braucht die Wortpositionen in Odoo – ein weiterer Grund, die Wortliste v2 (5.4) jetzt zu
  bauen; die Abstände (gleiche Zeile, Spaltenbreite) sind an den Proben einzustellen.

**Vierte Probe: gescannte Vertragsbestätigung eines anderen Stromversorgers**, diesmal mit einem **vorher
festgelegten** Stichwort-Katalog (18 Felder, Synonyme aus den drei ersten Proben), um die Übertragbarkeit auf einen
unbekannten Absender zu messen (Kopie danach gelöscht). Wieder eine schlechte Scanner-Textebene („04.05.201 7“,
IBAN mit falsch gesetzter Lücke); neue Erkennung 7 s für 2 Seiten.
- **Erster Lauf:** nur 5 der 13 im Dokument vorhandenen Werte richtig, dazu zwei **abgeschnittene** Nummern, die wie
  echte Werte aussehen („836“ statt „836 585 797 780“). Ursachen, alle allgemein: fehlende Synonyme
  („Geschäftspartnernummer“ = Kundennummer, „Mandats-ID“ = Mandatsreferenz), **Nummern in Leerzeichen-Gruppen**,
  **Einheit vor der Zahl** („Grundpreis EUR/Monat 10,90“, „Cent/kWh“ statt „ct/kWh“), Preisgarantie als Dauer
  („12 Monate ab Lieferbeginn“) statt Zeitraum, und zwei gruppierte Nummern nebeneinander, die zu einer verschmolzen.
- **Nach allgemeinen Korrekturen** (Synonyme, gruppierte Nummern, Einheit davor oder dahinter, Art „Zeitraum oder
  Dauer“, großer Wortabstand = Spaltengrenze, die ein Wert nicht überspringt): **13 von 13 richtig** auf dem neu
  erkannten Text, nur 7 von 13 auf der Scanner-Textebene (E9 erneut bestätigt). Nicht vorhandene Felder
  (Rechnungsnummer, Gesamtbetrag …) blieben leer, **kein Fehltreffer**. Die Gläubiger-ID ist auf dem Papier von Hand
  überschrieben; die Prüfziffer schlug fehl, der Wert wurde zu Recht nicht übernommen. Die USt-IdNr. in der kleinen
  Seitenspalte ging bei der neuen Erkennung verloren (in der Scanner-Ebene vorhanden).
- **Folgerungen:** (1) Der mitgelieferte Katalog braucht Synonymlisten und wird mit jedem neuen Absender besser – das
  spricht für „Anklicken und Stichwort lernen“ in der Oberfläche. (2) Die Wortliste v2 (5.4) soll große Abstände
  innerhalb einer Zeile markieren (z. B. als Tabulator), damit auch die Textsuche Spaltengrenzen kennt. (3) Die
  Korrekturen entstanden nach Ansicht dieses Dokuments; die ersten drei Proben sind gelöscht und konnten nicht erneut
  geprüft werden → für W-6 eine **feste Testsammlung auf Tower** anlegen, gegen die jede Regeländerung läuft.