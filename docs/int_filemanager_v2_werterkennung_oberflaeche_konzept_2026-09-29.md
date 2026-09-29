# int_filemanager 2: Werterkennung – Oberfläche mit Kasten-Auswahl (Konzept)

Stand 2026-09-29, **Konzept, nichts umgesetzt** (Nutzer: „noch nichts unternehmen“, erst durchdenken). Baut auf dem
Werterkennungs-Plan (`int_filemanager_v2_werterkennung_plan_2026-09-29.md`, W-1…W-6) auf; der Server liefert heute
schon Vorschläge je Feld mit Fundstelle, bestätigt, lernt je Absender – es fehlt die Oberfläche.

## 1. Anlass und Nutzerentscheidungen

Nach drei Übungsrunden (86 % richtige Vorschläge, 88 % gefunden) der Befund des Nutzers: *„Mir scheint es effektiver,
wenn das stärker mit selbst auswählen, was man braucht, verbunden ist. Aktuell werden viele Werte gelesen, die nicht
immer relevant sind.“* Vorschlag des Nutzers (am Jahresbescheid Wasser): **mit der Maus grob einen Kasten aufziehen,
aus dem Kasten werden alle relevanten Daten über Stichwörter wie bisher gelesen.**

Anders als die 2026-09-19 verworfene Zonen-Vorlage (fester Rahmen, blind gelesen) ist der Kasten nur eine **grobe
Auswahl**; darin arbeitet die bestehende Erkennung (Beschriftung–Wert-Paare, Stichwörter, Wertarten). Er muss nicht
genau sitzen und überlebt verrutschte Layouts.

Entscheidungen des Nutzers (2026-09-29):

| # | Frage | Antwort |
|---|---|---|
| K1 | Nur im Kasten oder Kasten mit Vorrang? | **Außerhalb bleiben alle anderen Werte erhalten** – der Kasten ergänzt und hat Vorrang, er schränkt nicht ein |
| K2 | Mehrere Kästen, auch auf Folgeseiten? | **Auf jeden Fall** |
| K3 | Gemerkte Kästen je Absender: automatisch oder als Vorschlag? | **Beides wäre gut** (→ Abschnitt 6, Konflikt mit E7) |
| K4 | Unlesbare Stelle im Kasten gründlicher nachlesen? | **Ja** |
| K5 | Anspruch | **Rundum vollständig: nimmt vieles ab, lässt dem Nutzer Eingriff.** UI elegant, modern, mit Odoo-eigenen Mechanismen |

Früher schon entschieden und weiter gültig: E6 (ein Wert je Feld), E7 (nichts ohne Prüfung übernehmen, frühestens mit
dem Eingangsordner neu entscheiden), E10 (eigene Firmendaten nie), E12 (Lernen je Absender, KI erst wenn nötig),
„Empfänger“ = Adressat, IBAN nur mit Beschriftung.

## 2. Vorbilder – was sie tun, was wir übernehmen

### PaperOffice (kommerzielles DMS, Hauptvorbild für den Ablauf)

- **Ablagedialog** (PIA): links das Dokument, automatisch gelesene Stellen **blau umrandet**; rechts Reiter (BASIS,
  ERWEITERT, BELEG, BENUTZERDEFINIERT). Halbautomatisch: PIA füllt vor, der Nutzer prüft und korrigiert **im
  Eingabefeld**; Symbol „?“ = unbekanntes Dokument, „✓“ = Vorlage erkannt.
- **Dokumentvorlage einlernen**: Erkennungsmerkmale (optional Bildbereiche wie Logo anklicken; **Pflicht:
  Schlagwörter**, die exakt im Dokument stehen müssen). **Variablen**: Maus über einen **Textcontainer** → gelb,
  Klick → grün, Namen und **Farbe** vergeben, **Positionslogik** wählen: *im ausgewählten Container* (feste Stelle),
  *zwischen dem Container mit dem vorherigen und dem kommenden Wert* (verschiebbar), *irgendwo im Dokument* (z. B.
  Endsummen), oder Regex. „Klicken um zu testen“ gibt sofort Rückmeldung.
- Erkannte Vorlage → Ablagemaske (Ablageort, Verschlagwortung) → **ohne weitere Mitwirkung** archivierbar.
- **Übernehmen:** Anklicken fertiger Textblöcke statt Pixelrahmen; die Positionslogik „zwischen zwei Nachbarn“ ist
  genau unser Anker-Gedanke (6.2); Farbe je Feld; sofortiges Testen. **Nicht übernehmen:** Pflicht-Schlagwörter als
  starre Vorlagenerkennung (wir erkennen den Absender über USt-IdNr./IBAN/Mail/Name, W-4); ein Vorlagen-Assistent als
  eigener Modus – bei uns lernt das System nebenbei beim normalen Prüfen.

### Paperless-ngx (Open Source)

- **Zusatzfelder je Dokument nur bei Bedarf**: auf der Detailseite über das Menü „Custom Fields“ ein Feld auswählen,
  erst dann erscheint es. Workflows können Felder je Absender/Dokumenttyp automatisch **hinzufügen** (mit oder ohne
  Wert). → Genau der Gedanke „nur was man braucht“: **Feldliste je Dokument statt Katalog für alle.**
- **Vorschläge** (Tags, Korrespondent, Dokumenttyp) über ein lokales Lernmodell; werden auf der Detailseite angeboten,
  angenommen oder verworfen. Werte aus dem Text liest Paperless selbst nicht.
- **„OCR Templates“** (PR #13043, Juni 2026, nur in den Branch `feature/ocr-templates` gemergt, kein Release,
  Maintainer: „nach v3“): feste Zonen je **Dokumenttyp** auf einem Musterdokument, je Zone Zielfeld, Sprache,
  Umformung (Zahl, Datum, **QR/Barcode lesen** mit zxing-cpp), Prüf-Regex, **„Zone testen“** mit Rohtext und
  Ergebnis. → Übernehmen: *Testen mit sofortiger Anzeige*, *QR lesen* (bei uns automatisch für jedes Dokument, U5), *Prüfen gegen die Wertart*. Nicht
  übernehmen: starre Zonen je Dokumenttyp (unser verworfener Weg).

### Odoo selbst

- **Rechnungs-Digitalisierung** (Enterprise, IAP „Extract“): Dokumentvorschau rechts neben dem Formular, erkannte
  Werte werden in der Vorschau hervorgehoben, Felder im Formular korrigiert; beim Kontakt-Feld wird der erkannte Name in
  der Vorschau markiert. Einstellung automatisch / auf Knopfdruck / aus. Die **Extract API** liefert je Feld
  `selected_value` plus `candidates` (nach Sicherheit sortiert), jeder Kandidat mit `content`, `page` und `coords`
  **relativ zur Seite (0…1)**. → Unser `suggest_field_values` hat bereits diese Form (bester Wert + Alternativen mit
  Kasten); für gemerkte Kästen übernehmen wir die **relative** Lage (unabhängig von Seitengröße und Scan-Auflösung).
- **AI-Felder** (Odoo 19, Studio bzw. „Eigenschaften bearbeiten“): Feld mit Prompt, Wert auf Klick oder täglich per
  Cron. Lizenzpflichtig, sendet Inhalte an einen KI-Dienst – für uns **kein Weg** (E12: lokal, KI erst wenn nötig),
  aber Bestätigung, dass „Feld + Anweisung + Wert auf Knopfdruck“ Odoos eigenes Muster ist.
- **Properties-Felder**: „Eigenschaft hinzufügen“ direkt im Formular über ein Popover (`properties_field.js`,
  `onPropertyCreate`). → Vorbild für „als neues Feld anlegen“ im Prüf-Fenster (Speicherung bleibt in unseren eigenen
  Modellen; Properties wurden 2026-09-19 als Speicherort verworfen).

## 3. Odoo-Bausteine (im Odoo-19-Quellcode geprüft, Image `odoo:19.0-hm-test`)

| Bedarf | Odoo-Baustein | Befund |
|---|---|---|
| Ganzseitiges Prüf-Fenster mit Brotkrumen, Knöpfen, Blättern | `ir.actions.client` + `Layout`/ControlPanel, `usePager` (`web/static/src/search/pager_hook.js`) | vorhanden; Blättern durch die Auswahl wie Datensatz-Pager (Alt+N/P) |
| Dokument neben den Feldern, Breite ziehbar | `ResizablePanel` (`web/static/src/core/resizable_panel/`) | vorhanden, u. a. in Discuss und Website-Builder genutzt |
| Vorbild Layout „Vorschau neben Formular“ | `mail` `AttachmentView` + `o_attachment_preview` (Eingangsrechnungen) | nur für `ir.attachment` des Datensatzes und als fertiger iframe-Viewer ohne eigene Überlagerung → **nur Vorbild**, nicht nutzbar (unsere Dateien liegen im eigenen Blob-Speicher) |
| PDF zeichnen, Kästen darüber | pdf.js **4.8.69** (`web/static/lib/pdfjs/build/pdf.js`, inkl. `TextLayer`) | vorhanden; v1-Baustein `IntPdfHighlightViewer` (Canvas + Kästen, Zoom mit Mausrad) ist die Grundlage |
| Odoo-Eingabefelder für unsere frei definierten Felder | `Record` (`web/static/src/model/record.js`) mit `fields`-Definition ohne echtes Modell | vorhanden (genutzt z. B. in `analytic_distribution`, `multi_create_popover`); Datum, Betrag+Währung, Kontakt (many2one), Tags wie überall in Odoo |
| „Neues Feld anlegen“ direkt im Fenster | Popover-Muster der Properties (`usePopover`, `property_definition`) | vorhanden, als Vorbild |
| Dokument in zweitem Fenster (zwei Bildschirme) | `mail_popout_service.js` (`documentPictureInPicture` bzw. `window.open`) | vorhanden |
| QR-Code (Überweisung/GiroCode) im Kasten lesen | `zxing-library` (`web/static/lib/zxing-library`, `HTMLCanvasElementLuminanceSource`) | vorhanden; Odoos eigener Detektor liest nur Video, die Bibliothek kann Canvas → im Browser machbar, noch nicht erprobt. **Nicht gewählt (U5):** gelesen wird auf dem Server im Umwandler |
| Kasten aufziehen | `CropOverlay` (`web/static/src/core/barcode/crop_overlay.js`) | nur für den Kamera-Scanner (zur Mitte symmetrisch), **nicht wiederverwendbar**; eigener kleiner Zieh-Code (Pointer-Events) wie in v1s Viewer |
| Ausschnitt gründlich nachlesen | Umwandler `fmconverter`: `pdftoppm`, `tesseract`, OCRmyPDF 17.12, Pillow | vorhanden |
| E-Rechnung in der PDF | `odoo.tools.pdf.OdooPdfFileReader.getAttachments()`, Modul `account_edi_ubl_cii` | vorhanden (Community) – eigener späterer Schritt, hier nur als Hinweis |

## 4. Bedienkonzept

### 4.1 Einstieg

- Kontextmenü, Listen-Aktion und Vorschau: **„Werte prüfen“** (eine oder mehrere Dateien). Später Eingangsordner:
  Filter „ungeprüft“ → dasselbe Fenster.
- Öffnet ein **ganzseitiges Prüf-Fenster** (Client-Aktion, kein Dialog – Platz für das Dokument), Brotkrumen zurück
  zum Ordner, Blättern durch die Auswahl („3 / 17“), Knöpfe **Speichern**, **Speichern und weiter**, **Verwerfen**.

### 4.2 Aufbau

```
┌─ Dateien / Rechnungen 2025 / Jahresbescheid Wasser.pdf ─────────── ‹ 3/17 › ─ [Speichern und weiter] ─┐
│ [Zeiger] [Kasten] [Nachlesen]  − 100 % +        ⧉ eigenes Fenster  │ Absender  [Verbandsgemeinde…  ▾]  │
│ ┌───────────────────────────────────────────┐                      │ Tags      [Wasser] [2024] +       │
│ │  Seite 1                                  │                      │───────────────────────────────────│
│ │   ┌ ─ Kasten 1 (6 Werte) ─ ─ ─ ─ ┐        │                      │ Rechnungsnummer 300/0154989/5/25 ✓│
│ │   │ Auskunft erteilt: Iris Stephan│       │                      │   aus Kasten 1 · „Rechnungsnummer“│
│ │   │ Rechnungsnummer: 300/0154…  ◀─┼───────┼── Hover verbindet ──▶│ Kundennummer    173918          ✓ │
│ │   └ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─┘        │                      │ Gesamtbetrag    784,12 €   ▾ (2)  │
│ │   [Kundennummer: 173918]                  │                      │ Ansprechpartner Iris Stephan      │
│ │   …                     [Gesamtbetrag 784,12 €]                  │ + Feld                            │
│ └───────────────────────────────────────────┘                      │───────────────────────────────────│
│  Seiten: [1] [2]                                                   │ Weitere Werte in Kästen           │
│                                                                    │  Objektnummer 069-000008 0001     │
│                                                                    │    [→ Feld …] [Als neues Feld]    │
│                                                                    │ ☐ Für diesen Absender merken      │
└────────────────────────────────────────────────────────────────────┴───────────────────────────────────┘
```

- **Links das Dokument** (alle Seiten untereinander, Zoom, Seitenleiste), **rechts die Felder**; Trennlinie ziehbar
  (`ResizablePanel`); auf schmalen Bildschirmen Reiter „Dokument / Werte“; Knopf „eigenes Fenster“ legt das
  Dokument auf einen zweiten Bildschirm.
- **Farben:** jedes Feld hat eine Farbe (wie PaperOffice); sein Wert ist im Dokument in derselben Farbe umrandet,
  Alternativen gestrichelt. Hover über eine Zeile rechts hebt die Stelle links hervor und umgekehrt.

### 4.3 Die drei Werkzeuge im Dokument

1. **Zeiger (Standard): anklicken und markieren.** Jedes gelesene Wort ist eine unsichtbare Fläche (aus der
   Wortliste, gilt für digitale PDFs und Scans gleich). Feld rechts anklicken, dann im Dokument ein Wort anklicken
   oder über mehrere Wörter ziehen → der Text wird nach der Wertart des Felds gelesen und eingetragen (9 von 10
   fehlenden Werten aus Runde 1 wären so erreichbar gewesen). Ohne gewähltes Feld: Klick auf einen Wert öffnet
   „Zu Feld …“.
2. **Kasten: grob aufziehen** (Werkzeug oder Umschalt+Ziehen). Sofort danach liest der Server alle
   Beschriftung–Wert-Paare darin; die Kastenecke zeigt „6 Werte“. Zugeordnete Werte füllen ihre Felder (Vorrang vor
   Funden außerhalb, K1); nicht zugeordnete Paare erscheinen rechts unter **„Weitere Werte in Kästen“**. Kästen lassen
   sich verschieben, in der Größe ändern und löschen; beliebig viele, auf jeder Seite (K2).
3. **Nachlesen** (am Kasten, K4): wurde im Kasten wenig oder Unsinn gelesen (schlechter Scan), liest der Umwandler
   genau diesen Ausschnitt mit höherer Auflösung neu; Ladeanzeige am Kasten, danach neue Paare. Den **Überweisungs-QR**
   (GiroCode) braucht man nicht anzuklicken: er wird für jedes Dokument automatisch gelesen (U5, Abschnitt 5.6); seine
   Werte (Empfänger, IBAN, Betrag, Verwendungszweck) stehen als sicherste Vorschläge in der Feldliste, im Dokument ist
   der QR-Code markiert.

### 4.4 Die Feldliste rechts – „nur was man braucht“

- Angezeigt werden: Felder **mit Vorschlag**, Felder, die **bei diesem Absender schon einmal bestätigt** wurden, und
  **angeheftete** Felder. Alle übrigen Felder des Katalogs erscheinen nicht – erreichbar über **„+ Feld“** (Suche im
  Katalog wie Paperless' „Custom Fields“-Menü).
- Jede Zeile nutzt das **Odoo-Eingabefeld der Wertart** (über `Record`): Datumswähler, Betrag mit Währung, Text.
  Daneben: Herkunft (aus Kasten / gelernt / Stichwort / von Hand), Alternativen (Aufklappliste, „▾ (2)“), bestätigen,
  entfernen. Der **gelesene Wert** steht im Feld, der **gedruckte** darunter klein (Runde 2: eine E-Mail war richtig
  gelesen, aber mit Leerzeichen gedruckt und wurde deshalb als falsch markiert).
- **„Als neues Feld anlegen“** aus einem weiteren Wert: Popover mit vorbelegtem Namen (die Beschriftung, z. B.
  „Objektnummer“) und vorbelegter Wertart; legt Feld plus Stichwort-Regel an – der Katalog wächst nach Bedarf.
- **Speichern** ruft das vorhandene `apply_field_values` (Schreibrecht, aktuelle Fassung, Notiz im Verlauf, Lernen).

### 4.5 Tastatur

Tab/Umschalt+Tab durch die Felder, Enter bestätigt den Vorschlag, Alt+N / Alt+P nächstes / voriges Dokument
(Odoo-Pager), K = Kasten-Werkzeug, Esc = Zeiger. Speichern und weiter = Strg+Enter.

## 5. Server: was dazukommt

Bestehend bleibt: `suggest_field_values`, `apply_field_values`, `value_suggest.suggest`, Lernen der Beschriftung
(`extraction_hint`), Adressfenster (`page_area`, bereits ein fest eingebauter Kasten).

1. **Kästen beim Vorschlagen:** `suggest_field_values(node_id, areas=[{page, x0, top, x1, bottom}])` mit Lage
   **relativ zur Seite (0…1)** wie Odoos Extract API. Paare, deren Wert im Kasten liegt, bekommen eine eigene, höchste
   Stufe nach „gelernt“; Rückgabe zusätzlich je Kasten die **nicht zugeordneten Paare** (heute schon berechnet,
   `_unassigned`, bisher auf 30 und ohne Lage begrenzt).
2. **Wert aus Markierung:** `read_selection(node_id, revision_id, field_id, start, end)` – liest den markierten Text mit
   der Wertart des Felds (`value_types.parse`, sonst Fehlermeldung „kein Datum“ usw.). Der Server leitet die Stelle
   selbst ab wie beim Speichern.
3. **Nachlesen eines Ausschnitts:** neue Umwandler-Aufgabe „Ausschnitt lesen“ (`pdftoppm` Ausschnitt mit hoher
   Auflösung → `tesseract` → Wörter mit Lage, zurückgerechnet auf die Seite). Ergebnis als eigenes Derivat je Fassung
   und Kasten (wie Kacheln/Wortliste), fließt beim nächsten Vorschlag in die Seite ein. Oberfläche wartet mit
   Ladeanzeige; Benachrichtigung über den Odoo-Bus, wenn fertig.
4. **Neues Feld aus Paar:** `create_field_from_pair(label, value_type)` → `extraction_field` + Stichwort-Regel, **nur
   Verwalter** (U2). Normale Nutzer: **„Feld vorschlagen“** → Nachricht an die Verwalter mit Beschriftung, Beispielwert,
   Wertart und Link zum Dokument (Odoo-Bordmittel, genaue Form bei der Umsetzung); der Verwalter legt mit einem Klick an
   oder lehnt ab.
5. **Kästen merken** (neues Modell, Vorschlag `int_filemanager.extraction_area`): Absender (Pflicht), Seite (auch
   „letzte Seite“ für Summen), Lage relativ, **Anker** = die Beschriftung im Kasten, die beim Speichern Werte lieferte
   (wie PaperOffice' Positionslogik „zwischen zwei Containern“), bestätigte Felder, Zähler, zuletzt benutzt, Modus
   (vorschlagen / automatisch, 6.3). Beim nächsten Dokument desselben Absenders: Anker in der Wortliste suchen und den
   Kasten um die Verschiebung mitnehmen; ohne Anker die gemerkte Lage.

6. **Überweisungs-QR (GiroCode) automatisch** (U5): der Umwandler sucht beim Erzeugen der Wortliste auf jeder Seite
   nach QR-Codes (Bibliothek `zxing-cpp` im Umwandler-Image nachinstallieren, wie Paperless' OCR-Templates) und
   liefert gefundene Inhalte mit Lage mit. Ein GiroCode (EPC-Format, beginnt mit „BCD“) ergibt Empfänger, IBAN, BIC,
   Betrag und Verwendungszweck; diese Werte sind die **höchste Stufe** (maschinenlesbar, nicht aus Text erraten),
   geprüft wie jeder Wert (IBAN-Prüfziffer, Betrag). Eigene Firmendaten (E10) werden auch hier übersprungen. Neue
   Spec-Version der Wortliste, damit vorhandene Dokumente beim nächsten Durchlauf nachgelesen werden. Vorher an der
   Sammlung zählen, wie viele Dokumente einen GiroCode tragen.

## 6. Lernen je Absender und Automatik

### 6.1 Was gelernt wird

- **Beschriftung → Feld** (gibt es: `extraction_hint`).
- **Kästen** (neu, 5.5) und **welche Felder** bei diesem Absender gebraucht werden (bestimmt die Feldliste 4.4).

### 6.2 Verrutschte Layouts

Kasten nicht an Pixel binden: Anker-Beschriftung plus relative Verschiebung; zusätzlich ist ein Kasten nur Vorrang,
nie Pflicht (K1) – ein falsch sitzender gemerkter Kasten kostet höchstens den Vorrang, nicht den Wert.

### 6.3 Automatisch übernehmen (K3) – Konflikt mit E7

Der Nutzer wünscht **beides**: Vorschlag *und* automatisch. E7 sagt: nichts ohne Prüfung, frühestens mit dem
Eingangsordner neu entscheiden. Vorschlag:

- **Standard je Absender: vorschlagen.** Gemerkte Kästen erscheinen gestrichelt, Werte vorbelegt, Speichern bestätigt.
- **„Künftig automatisch übernehmen“** als Schalter je Absender (setzt nur ein Verwalter, U3), erst mit dem Eingangsordner (Schritt 7) wirksam,
  nur wenn *alle* Werte aus gemerkten Kästen eindeutig gelesen wurden und die Anker gefunden wurden; sonst fällt die
  Datei in „ungeprüft“. Übernommene Werte tragen die Herkunft „automatisch“ und bleiben filterbar („automatisch
  übernommen, nie angesehen“); Notiz im Verlauf wie heute.
- **Entschieden (U1, Nutzer 2026-09-29): genau so** – Standard Vorschlag; automatisch nur per bewusst eingeschaltetem
  Schalter je Absender, erst mit dem Eingangsordner, nur wenn alles eindeutig ist; Vermerk, Filter, Notiz. E7 gilt
  damit weiter für alles andere.

## 7. Umsetzung in Scheiben (Vorschlag, noch nicht freigegeben)

| Scheibe | Inhalt | Fertig, wenn |
|---|---|---|
| U-1 | Server: Kästen beim Vorschlagen, Paare je Kasten mit Lage, Wert aus Markierung | Tests je Richtung wie W-4; Jahresbescheid-Beispiel liefert Infoblock-Paare |
| U-2 | Prüf-Fenster Grundgerüst: Client-Aktion, Pager, geteilte Ansicht, Viewer mit Wortflächen, Feldliste mit `Record`, Speichern | eine Datei prüfen und speichern ohne Kasten |
| U-3 | Kasten-Werkzeug, weitere Werte, „als neues Feld“, Farben/Hover | Kästen auf mehreren Seiten, Katalog wächst aus dem Fenster |
| U-4 | Kästen merken je Absender (Modell, Anker, Vorschlag beim nächsten Dokument), Feldliste je Absender | zweites Dokument desselben Absenders kommt vorbelegt |
| U-5 | Nachlesen (Umwandler) und QR automatisch je Dokument (Umwandler, 5.6) | schlechter Scan liefert nach Nachlesen Werte; GiroCode wird ohne Zutun gelesen und vorgeschlagen |
| U-6 | Messung: **Prüfteil** (16 unbekannte Absender, bisher unverbraucht) ohne und mit Lernen, dazu Zeit je Dokument | Zahlen gegen die 86 % des Übungsteils |
| (später) | Automatisch übernehmen (6.3) mit dem Eingangsordner; E-Rechnung; Dokumentart | eigene Entscheidungen |

## 8. Offene Entscheidungen

- ~~**U1**~~ **entschieden:** automatisch übernehmen wie in 6.3 (Schalter je Absender, erst mit Eingangsordner, nur
  eindeutig, Vermerk „automatisch übernommen“ + Filter „automatisch, nie angesehen“ + Notiz).
- ~~**U2**~~ **entschieden (Nutzer 2026-09-29): nur Verwalter** legen Felder direkt an; normale Nutzer „Feld
  vorschlagen“ (5.4). Katalog bleibt sauber, Wertart wird von jemandem gewählt, der die Folgen kennt.
- ~~**U3**~~ **entschieden (Nutzer 2026-09-29): für alle Nutzer** (wie die gelernten Beschriftungen seit W-5) – es
  sind nur Vorschläge, eine falsche Vorbelegung korrigiert die nächste Bestätigung. **Ausnahme:** den Schalter
  „automatisch übernehmen“ (U1) setzt nur ein Verwalter.
- ~~**U4**~~ **entschieden (Nutzer 2026-09-29): später entscheiden** – zuerst ohne Dokumentarten (Feldliste aus Funden,
  Absender-Gedächtnis und angehefteten Feldern, 4.4); nach einigen Wochen Nutzung prüfen, ob bei neuen Absendern oft
  Felder fehlen. Dokumentarten lassen sich ohne Umbau ergänzen.
- ~~**U5**~~ **entschieden (Nutzer 2026-09-29): auf dem Server im Umwandler, automatisch für jedes Dokument** (5.6),
  ohne Kasten; funktioniert damit auch für den Eingangsordner und die Automatik aus U1.
- **U6** Nur PDF im Prüf-Fenster, oder auch Bilder (JPG/TIFF-Scans haben heute keine Wortliste, Lücke aus dem
  Werterkennungs-Plan)?

## 9. Nachtrag: PaperOffice AI (Cloud-Plattform) – Wissensgraph, Entitäten, Kontakte, Suche

Recherche 2026-09-29 auf Nutzerwunsch. **Wichtig zur Einordnung:** die Seiten beschreiben **PaperOffice AI**
(paperoffice.ai), eine Cloud-Plattform mit Sprachmodellen, Vision und Embeddings in eigenen EU-Rechenzentren,
abgerechnet **je verarbeiteter Seite** (0,02–0,30 € je Seite, dazu Tarife 39 € bis 14.999 € im Monat; Wissensgraph ab
„Premium“, LLM-Verknüpfung und Logo-Erkennung erst „Ultra“). Das Vorlagen-Einlernen aus Abschnitt 2 gehört zu
**PaperOffice Classic** (Windows, lokal). Für uns gilt weiter: lokal, keine Kosten je Seite, KI erst wenn nötig (E12) –
übernommen werden deshalb die **Ideen**, umgesetzt mit Odoo-Bordmitteln und der vorhandenen Erkennung.

| PaperOffice AI | Wie es dort funktioniert | Übertragung auf int_filemanager 2 (Odoo-nativ) | Einschätzung |
|---|---|---|---|
| **Wissensgraph / Vorgänge** – Bestellung → Lieferschein → Rechnung → Vertrag als „ein Vorgang statt vier Dateien“; Ansichten Universum, Partner, Vorgang; jede Verbindung zeigt ihre Quelle | Kanten aus Metafeldern (Referenznummern, Parteien), Embedding-Ähnlichkeit, LLM-Schlüsse (Ultra) | (a) **Gleiche Nummer = gleicher Vorgang:** unsere Felder Bestell-, Auftrags-, Lieferschein-, Rechnungs-, Vertragsnummer liegen typisiert in `field_value` (`value_text` mit Trigram-Index) → im Prüf-Fenster und im Details-Dialog eine Liste **„Zum selben Vorgang“** (andere Dateien mit derselben Nummer), Quelle der Verbindung sichtbar („gleiche Bestellnummer“). (b) **Odoos eigener Vorgang:** `purchase`, `sale`, `stock`, `account` sind installierbar (Community); eine erkannte „Ihre Bestellung P00012“ lässt sich per `name_search` der Bestellung zuordnen – Odoo verknüpft Bestellung, Lieferung und Rechnung dann **selbst**, der Graph kommt aus dem ERP statt aus eigener Technik. (c) Absender: Kontakt-Smartbutton „Dokumente“. Eine Netz-Grafik baut Odoo nicht (`web_hierarchy` zeigt nur Bäume) – Listen reichen | (a) klein, gleich mit dem Prüf-Fenster; (b) sobald Odoo als ERP genutzt wird (Schritt 8 hängt Verknüpfungen um); Grafik nicht |
| **Zeitleiste** – bis zu 7 Datumsfelder (Rechnung, Fälligkeit, Lieferung, Gültigkeit …) plus alle Ereignisse; **„Attention Queue“** je Partei mit Fristen nach Fälligkeit | Datumsfelder aus der Extraktion, Ereignisse aus dem Protokoll | **Kalender- und Listenansicht über `field_value`** (`value_date`, `value_date_to` sind echte Datumsspalten) – reine Odoo-Ansichten ohne eigenes JS, gruppierbar nach Absender, Feld, Monat. ~~Fristen als Odoo-Aktivitäten~~ – **weggelassen (Nutzer 2026-09-29, U7)** | Kalender/Liste: klein |
| **Auswertung** (Analytics-Dashboard) | Kennzahlen aus extrahierten Werten | **Pivot- und Diagrammansicht über `field_value`** (Beträge je Absender und Monat, z. B. Nebenkosten je Jahr) – Odoo-Bordmittel | klein |
| **Entitäten (NER)** – Personen, Firmen (mit Logo), Beträge, Daten, Orte, Bankdaten, Referenznummern; kanonische Namen mit Aliasen; Fundstelle, Konfidenz und Modellversion je Fund; Korrekturen fließen zurück | Sprachmodell „liest im Kontext“, Vision, Musterprüfung | Haben wir in anderer Form: **Wertarten** (W-3) statt freier Entitäten, **Fundstelle + Stufe** je Wert (Stufe ≈ Konfidenz), Lernen aus Bestätigungen (W-5). Neu übernehmen: (1) **abweichende Bankverbindung** – IBAN im Dokument ≠ bekannte Konten des Kontakts (`res.partner.bank`) → deutlicher Hinweis im Prüf-Fenster (Schutz vor gefälschten Rechnungen); (2) **Aliase** – gedruckter Firmenname, unter dem ein Kontakt bestätigt wurde, als gelernter Name des Absenders merken (wie `extraction_hint`), damit „Nordlicht Energie“ und „NE GmbH“ beim nächsten Mal denselben Kontakt finden | (1) klein, sehr nützlich; (2) klein |
| **Kontakt-Extraktion** – Firma, Person, Adresse, USt-IdNr., E-Mail, Telefon, Bankdaten, Rollen (Absender, Unterzeichner, Empfänger); Dubletten über Name/E-Mail/USt-IdNr./Logo; Partei-Register mit allen Dokumenten | IDP + Vision, automatisch ohne Bestätigung | Wir finden **vorhandene** Kontakte (W-4: USt-IdNr. → IBAN → Mail → Domain → Name). Neu: **„Kontakt aus Dokument anlegen“** – Odoos Kontaktformular öffnen, vorbelegt über `default_*`-Kontext mit Name, Anschrift (aus Absenderzeile/Briefkopf bzw. einem Kasten), USt-IdNr. (geprüft durch Odoos `base_vat`, auf Wunsch gegen VIES), E-Mail, Telefon, IBAN als Bankkonto. Nutzer bestätigt im gewohnten Formular. Rollen: Absender = Kontakt der Datei, Adressat/Ansprechpartner = unsere Felder. `partner_autocomplete` (Odoo-IAP, Cloud) nicht | mittel, gut abgegrenzt |
| **Intelligente Suche** – semantisch (Embeddings je Zusammenfassung/Seite/Absatz), hybrid mit Volltext, exakt für Nummern, Filter nach Partei/Typ/Zeitraum/Entitäten, sprachübergreifend, Antwort mit Quellen (Graph-RAG) | Embeddings + Vektorsuche + LLM | **Zuerst die Lücke schließen:** die v2-Suche findet heute **nur Namen, Tags, Status, Kontakt** – der gelesene Text (`derivative.text`) ist nicht durchsuchbar (v1 konnte das). Dann **Suche nach erkannten Werten** mit Odoo-Bordmitteln: Suchfelder/Filter über `field_value_ids` („Gesamtbetrag > 500“, „Absender = …“, „Rechnungsdatum im 3. Quartal“), Gruppieren, gespeicherte Favoriten. **Semantische Suche** braucht Vektoren: Odoo 19 Community hat keinen Vektor-Feldtyp, der Test-Postgres keine `vector`-Erweiterung (nur `pg_trgm`, `unaccent`) → eigener späterer KI-Schritt mit lokalem Modell (E12) | Volltext + Wertefilter: klein, wichtig; semantisch: später |
| **Human-in-the-loop** – „Jedes Feld trägt Konfidenz und Fundstelle, damit die Kontrolle schnell geht“; unsichere Felder zur Prüfung, „Bild und Text nebeneinander“; Plausibilität (Summen, Steuer, IBAN, Dubletten) | – | Genau unser Prüf-Fenster (Abschnitt 4). Ergänzen: **unsichere Werte zuerst** (Stufe „enthält“, „ähnlich“, „ohne Beschriftung“ farblich markiert, sichere gedämpft); **Plausibilität** als Hinweise: Netto + Steuer = Brutto, Fälligkeit nach Rechnungsdatum, gleiche Rechnungsnummer beim selben Absender schon vorhanden (**Dublette?**), abweichende IBAN | mittel, gehört in U-2/U-3 |

**Was daraus für die Scheiben folgt** (Ergänzung zu Abschnitt 7, noch nicht freigegeben):

- **U-2 erweitern:** unsichere Werte zuerst, Plausibilitäts- und Dubletten-Hinweise, abweichende IBAN.
- **Neue kleine Scheibe U-7 „Werte nutzen“:** Volltextsuche im gelesenen Text wieder anbinden, Suchfilter über erkannte
  Werte, Kalender-/Listen-/Pivot-Ansicht über `field_value`, „Zum selben Vorgang“.
- **Neue Scheibe U-8 „Kontakt aus Dokument“:** vorbelegtes Kontaktformular, Aliase je Kontakt.
- **Später/eigene Entscheidung:** Verknüpfung mit Odoo-Bestellungen/-Rechnungen (mit Schritt 8), semantische Suche und
  Sprachmodell (E12).

Weitere offene Entscheidungen dazu:

- ~~**U7** Fristen als Odoo-Aktivitäten~~ – **entfällt** (Nutzer 2026-09-29: „U7 weglassen“); keine Erinnerungen aus
  erkannten Daten.
- **U8** Kontakte aus Dokumenten: darf jeder Nutzer neue Kontakte anlegen, oder nur Vorschlag an einen Verwalter?
- **U9** Reihenfolge: U-7 (Werte nutzen – Suche, Kalender, Auswertung) **vor** dem Prüf-Fenster, weil es sofort mit den
  bereits gespeicherten Werten nutzt, oder danach?

## Quellen

- PaperOffice: [Dokumentvorlagen einlernen](https://portal.paperoffice.ai/paperoffice/de/kb/paperoffice-classic-dms/wie_lerne_ich_die_dokumentvorlagen_in_paperoffice_ein),
  [PIA Ablagedialog](https://portal.paperoffice.ai/paperoffice/de/kb/paperoffice-classic-dms/pia_ablagedialog_detailliert_erklaert);
  frühere allgemeine Recherche: `docs/int_filemanager_paperoffice_recherche.md`
- PaperOffice AI (Cloud): [Wissensgraph](https://paperoffice.ai/de/ki-knowledge-graph-wissensgraph/),
  [Entitäten/NER](https://paperoffice.ai/de/ki-entities-named-entity-recognition-ner-extraktion/),
  [Kontakt-Extraktion](https://paperoffice.ai/de/ki-kontakt-extraktion-beziehungsmanagement/),
  [Intelligente Suche](https://paperoffice.ai/de/ki-smart-search-intelligente-suche-semantische-dokumentensuche/),
  [Zeitleiste](https://paperoffice.ai/de/ki-timeline-dokument-zeitleiste-chronologische-ansicht/),
  [Dokumenttypen](https://paperoffice.ai/de/loesungen/dokumenttypen/), [Rechnungsverarbeitung](https://paperoffice.ai/de/idp/rechnung/),
  [Preise](https://paperoffice.ai/de/preise/)
- Paperless-ngx: `docs/usage.md` im Repository (Custom Fields, Workflows, Suggestions);
  [PR #13043 „OCR Templates“](https://github.com/paperless-ngx/paperless-ngx/pull/13043) (Branch
  `feature/ocr-templates`, `src/documents/zone_ocr.py`, `src-ui/src/app/data/ocr-template.ts`)
- Odoo: [Rechnungs-Digitalisierung](https://www.odoo.com/documentation/19.0/applications/finance/accounting/vendor_bills/invoice_digitization.html),
  [Extract API](https://www.odoo.com/documentation/19.0/developer/reference/extract_api.html),
  [AI-Felder](https://www.odoo.com/documentation/19.0/applications/productivity/ai/fields.html); Odoo-19-Quellcode im
  Image `odoo:19.0-hm-test` (Pfade in Abschnitt 3)
