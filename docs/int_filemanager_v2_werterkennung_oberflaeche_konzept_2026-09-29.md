# int_filemanager 2: Werterkennung – Oberfläche mit Kasten-Auswahl (Konzept)

Stand 2026-09-29, **Konzept, nichts umgesetzt.** K1–K5 und U1–U9 entschieden; nach der Vollständigkeitsrunde
(Abschnitt 10: Abdeckung, Versuche mit echten Dokumenten, kritische Gegenlese) neue Fragen N1–N9 **entschieden**; es fehlt nur noch die **Freigabe**. Baut auf dem
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
- **Markierung (N6):** alle gefundenen Werte im Dokument dezent umrandet; das gerade gezeigte oder gewählte Feld wird
  kräftig hervorgehoben, das Dokument scrollt dorthin (auch auf eine andere Seite); Hover im Dokument hebt umgekehrt
  die Zeile rechts hervor. Keine feste Farbe je Feld.

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
   Betrag und Verwendungszweck; diese Werte sind **starke Kandidaten** (maschinenlesbar, nicht aus Text erraten),
   geprüft wie jeder Wert (IBAN-Prüfziffer, Betrag) – sie überstimmen gedruckte, beschriftete Werte aber nicht; weichen
   sie ab (z. B. Abschlag statt Gesamtbetrag), zeigt das Prüf-Fenster einen Hinweis (N2, 10.4). Eigene Firmendaten (E10) werden auch hier übersprungen. Neue
   Spec-Version der Wortliste, damit vorhandene Dokumente beim nächsten Durchlauf nachgelesen werden. Vorher an der
   Sammlung zählen, wie viele Dokumente einen GiroCode tragen.

## 6. Lernen je Absender und Automatik

### 6.1 Was gelernt wird

- **Beschriftung → Feld** (gibt es: `extraction_hint`).
- **Kästen** (neu, 5.5) und **welche Felder** bei diesem Absender gebraucht werden (bestimmt die Feldliste 4.4).

### 6.2 Verrutschte Layouts

Kasten nicht an Pixel binden: Anker-Beschriftung plus relative Verschiebung. **Korrigiert (Gegenlese 10.4):** die
frühere Aussage „ein falsch sitzender gemerkter Kasten kostet höchstens den Vorrang, nicht den Wert“ war falsch – weil
Werte im Kasten Vorrang haben, kann ein verrutschter Kasten einen falschen Wert nach vorne holen. Deshalb: ein
**gemerkter** Kasten bekommt nur Vorrang, wenn seine Anker-Beschriftung im neuen Dokument **eindeutig** gefunden wird;
sonst wird er nur gestrichelt angezeigt, ohne Vorrang. Ein vom Nutzer gerade gezogener Kasten behält den Vorrang.

### 6.3 Automatisch übernehmen (K3) – Konflikt mit E7

Der Nutzer wünscht **beides**: Vorschlag *und* automatisch. E7 sagt: nichts ohne Prüfung, frühestens mit dem
Eingangsordner neu entscheiden. Vorschlag:

- **Standard je Absender: vorschlagen.** Gemerkte Kästen erscheinen gestrichelt, Werte vorbelegt, Speichern bestätigt.
- **„Künftig automatisch übernehmen“** als Schalter je Absender (setzt nur ein Verwalter, U3), erst mit dem Eingangsordner (Schritt 7) wirksam,
  nur wenn *alle* Werte aus gemerkten Kästen eindeutig gelesen wurden und die Anker gefunden wurden; sonst fällt die
  Datei in „ungeprüft“. Übernommene Werte tragen die Herkunft „automatisch“ und bleiben filterbar („automatisch
  übernommen, nie angesehen“); Notiz im Verlauf wie heute.
- **Ergänzt nach Gegenlese (10.4):** „eindeutig“ wird messbar – ein Absender kommt für die Automatik erst in Frage, wenn
  seine letzten Dokumente (Zahl beim Bau festlegen) **ohne jede Korrektur** bestätigt wurden; eine Korrektur setzt das
  zurück. Automatisch übernommene Werte werden bei späterem Speichern nie wieder automatisch überschrieben
  (Paperless-Lehre).
- **Entschieden (U1, Nutzer 2026-09-29): genau so** – Standard Vorschlag; automatisch nur per bewusst eingeschaltetem
  Schalter je Absender, erst mit dem Eingangsordner, nur wenn alles eindeutig ist; Vermerk, Filter, Notiz. E7 gilt
  damit weiter für alles andere.

## 7. Umsetzung in Scheiben (Reihenfolge nach U9, noch nicht freigegeben)

| Scheibe | Inhalt | Fertig, wenn |
|---|---|---|
| U-1 | **Volltextsuche** im gelesenen Text (`derivative.text`) in der Dateisuche wieder anbinden, dazu **Formularfeld-Werte** in Wortliste und Text (N1) – die v2-Suche findet heute nur Name, Tags, Status, Kontakt (v1 konnte den Inhalt durchsuchen) | ein Wort, das nur im Dokument steht, findet die Datei; Suche bleibt bei großen Ordnern schnell |
| U-2 | Server: Kästen beim Vorschlagen, Paare je Kasten mit Lage, Wert aus Markierung | Tests je Richtung wie W-4; Jahresbescheid-Beispiel liefert Infoblock-Paare |
| U-3 | Prüf-Fenster Grundgerüst: Client-Aktion, Pager, geteilte Ansicht, Viewer mit Wortflächen, Feldliste mit `Record`, Speichern, **Prüfstatus** je Dokument (N4); **unsichere Werte zuerst**, Plausibilitäts-/Dubletten-Hinweise, **abweichende IBAN** (Abschnitt 9) | eine Datei prüfen und speichern ohne Kasten |
| U-4 | Kasten-Werkzeug, weitere Werte, „als neues Feld“ (Verwalter) / „Feld vorschlagen“ (Nutzer, U2), Hervorheben aktive Stelle ↔ Feld (N6) | Kästen auf mehreren Seiten, Katalog wächst aus dem Fenster |
| U-5 | „daraus nicht lernen“ und Verwalter-Übersicht des Gelernten (N5); Kästen merken je Absender für alle (U3: Modell, Anker, Vorschlag beim nächsten Dokument; N3: Vorrang nur mit eindeutigem Anker, „gemerkte Kästen verwerfen“), Feldliste je Absender | zweites Dokument desselben Absenders kommt vorbelegt |
| U-6 | Nachlesen (Umwandler), QR automatisch je Dokument (U5, 5.6), „Text erkennen“ für Bilder auf Wunsch (U6) | schlechter Scan liefert nach Nachlesen Werte; GiroCode wird ohne Zutun gelesen und vorgeschlagen |
| U-7 | **Neue Feldarten und Feldeigenschaften** (N8, Abgleich 10.6) **und echte Spalte je Katalogfeld** (N9: Spaltenart, Kopplung Katalogfeld ↔ Spalte, „neu aufbauen“): Verknüpfung zu Odoo-Datensätzen (Zielmodell je Feld, Suche über `name_search`, nur lesbare Datensätze), Ankreuzfeld, Auswahl (Möglichkeiten mit Stichwörtern), Telefon, Prozentsatz, Monat; Eigenschaften Hilfetext, Platzhalter, Standardwert, Sichtbarkeit nur für Gruppen, bei Daten Zukunfts-Warnung und früheste/späteste Grenze | jede neue Art wird an echten Dokumenten erkannt und mit Odoos Eingabefeld angezeigt; ein Fahrzeug-Feld findet das Fahrzeug über das Kennzeichen |
| U-8 | **Kontakt aus Dokument** (vorbelegtes Odoo-Kontaktformular, nur mit Odoos Recht „Kontakte: Anlegen“, U8), Namensvarianten je Kontakt | neuer Absender wird mit zwei Klicks Kontakt, Varianten finden ihn wieder |
| U-9 | **Werte nutzen**, sobald durch das Prüfen echte Werte entstehen (U9): Spalten in der Dateiliste, Filter, Gruppieren, Pivot/Diagramm mit Summen und Export über die echten Spalten (N9), Kalender über Datumswerte, „Zum selben Vorgang“ | „Gesamtbetrag > 500 €“ und „Nebenkosten je Jahr“ funktionieren mit Odoo-Bordmitteln |
| U-10 | Messung: **Prüfteil** (16 unbekannte Absender, bisher unverbraucht) ohne und mit Lernen, dazu Zeit je Dokument | Zahlen gegen die 86 % des Übungsteils |
| (später) | Automatisch übernehmen (6.3, U1) und **Ablageregeln** (N7) mit dem Eingangsordner; Bilder automatisch je Ordner (U6); E-Rechnung; Dokumentarten (U4); Verknüpfung mit Odoo-Bestellungen/-Rechnungen; semantische Suche/Sprachmodell (E12) | eigene Entscheidungen bzw. Schritte |

## 8. Entscheidungen (U1–U9 getroffen; N1–N8 in 10.5 und N9 in 10.7, ebenfalls entschieden)

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
- ~~**U6**~~ **entschieden (Nutzer 2026-09-29): Bilder auf Wunsch jetzt, automatisch später je Ordner.** Im
  Prüf-Fenster zeigt ein Bild ohne Wortliste den Knopf „Text erkennen“ (Umwandler-Auftrag, danach wie PDF); mit dem
  Eingangsordner zusätzlich automatisch für Bilder aus bestimmten Ordnern (Eingang, Scans). Nie für alle Bilder
  (rund 209.000 Fotos). Geraderücken von Handyfotos wäre ein eigener späterer Schritt.

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
| **Human-in-the-loop** – „Jedes Feld trägt Konfidenz und Fundstelle, damit die Kontrolle schnell geht“; unsichere Felder zur Prüfung, „Bild und Text nebeneinander“; Plausibilität (Summen, Steuer, IBAN, Dubletten) | – | Genau unser Prüf-Fenster (Abschnitt 4). Ergänzen: **unsichere Werte zuerst** (Stufe „enthält“, „ähnlich“, „ohne Beschriftung“ farblich markiert, sichere gedämpft); **Plausibilität** als Hinweise: Netto + Steuer = Brutto, Fälligkeit nach Rechnungsdatum, gleiche Rechnungsnummer beim selben Absender schon vorhanden (**Dublette?**), abweichende IBAN | mittel, gehört in U-3 |

**Was daraus für die Scheiben folgt:** eingearbeitet in Abschnitt 7 (U-1 Volltextsuche, U-3 unsichere Werte zuerst,
Plausibilität, abweichende IBAN, U-8 Kontakt aus Dokument, U-9 Werte nutzen).

Entscheidungen dazu:

- ~~**U7** Fristen als Odoo-Aktivitäten~~ – **entfällt** (Nutzer 2026-09-29: „U7 weglassen“); keine Erinnerungen aus
  erkannten Daten.
- ~~**U8**~~ **entschieden (Nutzer 2026-09-29): Odoos eigenes Recht gilt** – „Kontakt aus Dokument anlegen“ sieht nur,
  wer in Odoo Kontakte anlegen darf (`base.group_partner_manager`, „Kontakte: Anlegen“; normale interne Benutzer dürfen
  `res.partner` laut `base/security/ir.model.access.csv` nur lesen). Keine eigene Regel, kein Vorschlagsknopf.
- ~~**U9**~~ **entschieden (Nutzer 2026-09-29): aufgeteilt** – zuerst die **Volltextsuche** (unabhängig, der gelesene
  Text liegt für jede Datei schon vor), dann das Prüf-Fenster, danach „Werte nutzen“ (Filter, Kalender, Auswertung,
  Vorgang): diese brauchen gespeicherte Werte, und die entstehen erst durch das Prüfen – heute gibt es außer in
  Testdatenbanken praktisch keine.

## 10. Vollständigkeitsrunde (2026-09-29): Abdeckung, Versuche, Gegenlese

Anlass: Nutzer-Sorge „zu schnell, Stichproben statt vollständig lesen, nicht alle Möglichkeiten gezeigt“. Die erste
Fassung (Abschnitte 2–9) beruhte zum Teil auf Zusammenfassungen und Stichproben, ohne das zu sagen. Dieser Abschnitt legt
offen, was wie gründlich geprüft ist, und korrigiert, was sich dabei als falsch herausstellte.

### 10.1 Abdeckung

| Quelle | Vollständig gelesen | Nur teilweise | Nicht gelesen (Grund) |
|---|---|---|---|
| Paperless-ngx PR #13043 „OCR Templates“ | Kern `zone_ocr.py` (757 Z.), Modell, Schnittstelle `views.py`, Auslöser, Editor (HTML 414 + TS 997 Z.), Dokumentansicht, Übersicht, Datentypen | Tests (903 Z.) nur Namen und Prüfinhalte; Serialisierer per Suche | Migration (gleich dem Modell) |
| Paperless-ngx Doku | `docs/usage.md`: Custom Fields, Workflows, Vorschläge, KI, Dokumentansicht | – | übrige Kapitel (Installation, Suche-Syntax, API) |
| PaperOffice Classic Handbuch | Inhaltsverzeichnis (277 Artikel) nach Titel gefiltert; **21 relevante Artikel im Originaltext** (Vorlagen, Ablagemasken, Ablagedialog, Ablagemodi, Felder, Texterkennung, SmartSpell, Suche, Kontakte, QR, Stapel) | – | 256 Artikel zu Installation, NAS, Lizenz, Fehlerbehebung, Workflows im Detail, Videos |
| PaperOffice AI (Cloud) | 8 Produktseiten (Graph, Entitäten, Kontakte, Suche, Zeitleiste, Dokumenttypen, Rechnung, Preise) | **nur als Zusammenfassung** eines Hilfsmodells (WebFetch), nicht im Originaltext | Entwickler-Doku, Blog |
| Odoo 19 Community (Image `odoo:19.0-hm-test`) | **Suche über alle 692 Module / 3.700 JS-Dateien** nach: pdf.js-Nutzung, Textebene, Rahmen ziehen, Barcode-Lesen, `Record`-Nutzung, Vorschau-neben-Formular, Beleg-Hochladen, Server-Texterkennung; gelesen: `utils/pdfjs.js`, `pdf_thumbnail.js`, `crop_overlay.js`, `analytic_distribution` (Record+Field), `multi_create_popover`, `document_file_uploader`, Formular-Compiler/-Renderer der Anhang-Vorschau, `properties_field.onPropertyCreate`, Rechte `res.partner` | `image_crop.js` nur Anfang | Odoo Enterprise (nicht im Image: Documents, Extract, Sign) – nur Doku |
| Odoo Doku | Digitalisierung, Extract API (Kandidaten-Format im Originaltext), AI-Felder | – | – |

### 10.2 Versuche mit deinen echten Dokumenten (Tower, Wegwerf-Container, alle 513 PDFs)

- **Seitengeometrie** (alle 1.512 Seiten): 4 gedrehte Seiten (3 Dokumente), keine mit Beschnitt oder verschobenem
  Ursprung.
- **Wortlage passt:** Wortkästen aus der Wortliste auf die gerenderte Seite gezeichnet (poppler, wie pdf.js mit
  Seitenbox und Drehung) – deckungsgleich bei allen 4 gedrehten Seiten, bei digitalen PDFs, bei Scans mit neuer und mit
  erzwungener Texterkennung und bei einer Seite mit 1860 × 2630 Punkten. **Nicht geprüft:** pdf.js selbst im Browser.
- **Neue Lücke gefunden – Formularfelder:** ausgefüllte PDF-Formulare (z. B. Elterngeld-Antrag) – die eingetragenen
  Werte fehlen in der v2-Wortliste. Der Umwandler hat dafür keinen Code; v1 hatte eine Lösung (19.09.,
  `fulltext._pdf_form_field_words`). **Mindestens 30 von 513 PDFs** mit ausgefüllten Textfeldern, **999 Werte**
  (10 Dateien konnte der Schnelltest nicht lesen). Betrifft Werterkennung **und** Volltextsuche.
- **QR-Codes** (zxing-cpp, alle Seiten): Überweisungs-QR nur in **2 von 513** Dokumenten; andere QR 34, DataMatrix 86
  (vermutlich Post-Frankierung), ITF 33, Code 128 12. In der privaten Sammlung also selten – bei Geschäftsrechnungen
  vermutlich häufiger, nicht gemessen.
- **Felder ohne echtes Modell (`Record` + `Field`):** kein Versuch nötig – Odoo nutzt genau das im Kern
  (`analytic_distribution`: Kontakt, Betrag mit Währung, Prozent). Restrisiko: keine offizielle Schnittstelle, kann sich
  zwischen Odoo-Versionen ändern.
- **Nicht geprüft** (braucht Browser, Nutzer testet selbst): Ziehen/Anfassen der Kästen, zweites Fenster, Pager in der
  Client-Aktion – erst mit U-3/U-4.

### 10.3 Neue Befunde aus der vollständigen Lektüre

- **PaperOffice:** Ablagemasken sind **Ablageregeln** (Dokumentname mit Platzhaltern, Zielordner mit Jahr/Monat,
  Status, Typ, Schlüsselwörter, Notiz) – Vorbild für „Dateiname und Ablageort aus erkannten Werten“; Automatik ist dort
  **global** (4 Ablagemodi), unsere je Absender (U1) ist feiner; **Dublettenwarnung schon beim Hinzufügen**; „Text aus
  OCR einfügen“ = unser Anklicken; Feldarten auch **Auswahlliste** und **Ankreuzfeld**; Felder je Dokumenttyp
  sichtbar; **Korrekturwörterbuch** für Lesefehler; erkannter Text je Seite ansehbar, im Dokument durchsuchbar, von Hand
  korrigierbar; Suchergebnis mit Trefferzahl und Textstelle; Export PDF + Excel mit Links; Speichern „als neue Version
  des markierten Dokuments“.
- **Paperless:** mehrere Zonen zu **einem Feld zusammensetzen** (`{Zone A} - {Zone B}`); Seite „−1 = letzte Seite“;
  Werte werden **nicht bei jedem Speichern neu geschrieben**, weil das Korrekturen des Nutzers überschreiben würde (nur
  beim Einlesen und bei Typwechsel) – gilt auch für unsere Automatik; Schnellanlage eines Felds nutzt ein gleichnamiges
  vorhandenes; „Zone testen“ ohne zu speichern; Editor-Details (Ziehen auf freier Fläche, Umschalt+Ziehen über
  vorhandener Zone, 8 Anfasser, Mindestgröße gegen Fehlklicks). Sicherheitslücke dort: Seitenbild-Endpunkt ohne
  Rechteprüfung am Dokument – bei uns jede Seitenausgabe über die Knotenrechte.
- **Odoo:** fertiger Lader `loadPDFJSAssets()` statt eigener Pfade (v1-Viewer umgeht ihn); das Beleg-Hochladen der
  Buchhaltung (`FileUploader` → `create_document_from_attachment` → Liste öffnet sich, Meldung je Datei) ist das
  Vorbild für den Eingangsordner; **exakte Dubletten** erkennt v2 ohnehin (inhaltsadressierter Blob-Speicher, gleicher
  Hash).

### 10.4 Kritische Gegenlese (Codex) – und meine Bewertung

| Einwand (Codex) | Bewertung nach Prüfung | Folge |
|---|---|---|
| Verrutschter gemerkter Kasten kann einen falschen Wert nach vorne holen – Aussage in 6.2 falsch | **stimmt** | 6.2 korrigiert: Vorrang nur bei eindeutig gefundenem Anker |
| Herkunft geht verloren: `source` kennt nur „rule/manual“, Fundstelle wird beim Speichern neu gesucht | **stimmt** (geprüft: `field_value.source`; Neusuche nahe der angeklickten Stelle mildert es) | Herkunft erweitern (Stichwort, gelernt, Kasten, Formularfeld, QR, Hand, automatisch); gewählte Fundstelle mitschicken und auf dem Server gegen die Wortliste prüfen statt neu suchen |
| Tabellen/mehrere Werte je Feld fehlen | stimmt, bewusst (E6) | ausdrücklich **außerhalb** dieses Konzepts |
| Prüfstatus je Dokument/Feld, Pflichtfelder, „fertig“-Definition fehlen | stimmt – ohne Status kein Filter „ungeprüft“ bzw. „automatisch, nie angesehen“ (U1 setzt ihn voraus) | Frage N4 |
| Lernen ohne Gegensteuer („letzte Bestätigung gewinnt“, für alle) | stimmt (geprüft: `_learn_labels`); U3 bleibt, braucht aber Gegensteuer | Frage N5 |
| Automatik erst nach gemessener Fehlübernahme-Quote | stimmt – die 86 % sind aus dem Übungsteil, nicht entscheidungsreif | U1 ergänzt: Automatik je Absender erst nach mehreren Bestätigungen **ohne Korrektur**; Prüfteil messen |
| QR ist nicht automatisch der „sicherste“ Geschäftswert | stimmt teilweise (Abschlag ≠ Gesamtbetrag) | QR-Werte als starke Kandidaten, bei Abweichung zum Gedruckten Hinweis statt Vorrang; Frage N2 |
| QR und Nachlesen brauchen Grenzen | stimmt | Seiten-, Zeit- und Parallelitätsgrenzen wie beim Umwandler bereits üblich |
| Kasten wird zum Produkt statt Ausnahme-Werkzeug | teilweise – der Nutzer will den Kasten ausdrücklich; die Reihenfolge (erst Anklicken/Vorschläge in U-3, Kasten in U-4) passt bereits | gemerkte Kästen: Frage N3 |
| Frei definierte Felder über `Record` sind fragil, lieber echtes (transientes) Modell | teilweise – ein echtes Modell kann keine vom Nutzer definierten Spalten; Odoo nutzt `Record` so im Kern | bleibt; Rückfallplan: eigene einfache Eingabefelder |
| Farbe je Feld wird unruhig | plausibel | Frage N6 |
| Feldanlage gehört nicht ins Prüf-Fenster | abweichend von U2 (Nutzerentscheidung) | U2 bleibt |
| Absender allein zu grob (ein Absender, mehrere Belegarten) | stimmt als Risiko | Anker-Pflicht (6.2) mildert; Dokumentarten nach Nutzung (U4) |
| Mit Odoo-Geschäftsdatensätzen verknüpfen statt eigener Auswertung | Richtung stimmt | bereits „später“ (Abschnitt 9) |
| Entwurf/Rückgängig, Warteschlange mit Zuständigkeit, zwei gleichzeitige Prüfer | teilweise: Knotensperre und Fassungsprüfung schützen die Datei; „letzte Speicherung gewinnt“ je Feld bleibt | Warnung bei ungespeicherten Änderungen in U-3; Zuständigkeit später mit dem Eingangsordner |

### 10.5 Neue Fragen an den Nutzer

- ~~**N1**~~ **entschieden (Nutzer 2026-09-29): ja, Teil von U-1.** Der Umwandler liest ausgefüllte Formularfelder
  (Text- und Auswahlfelder, wie v1 `fulltext._pdf_form_field_words`) mit ihrer Lage auf der Seite und hängt sie an die
  Wortliste; Ankreuzfelder vorerst nicht (Wert ist kein Text, Zuordnung zur Beschriftung unsicher). Neue Spec-Version der
  Wortliste, damit vorhandene Dokumente im Hintergrund neu gelesen werden.
- ~~**N2**~~ **entschieden (Nutzer 2026-09-29): trotzdem jetzt bauen (U5 bleibt), damit die Werterkennung vollständig
  ist** – obwohl nur 2 von 513 privaten Dokumenten einen Überweisungs-QR tragen (Geschäftsrechnungen vermutlich öfter,
  nicht gemessen). Mit den Einschränkungen aus 10.4: QR-Werte sind starke Kandidaten, überstimmen Gedrucktes aber nicht –
  bei Abweichung Hinweis im Prüf-Fenster; Seiten-/Zeitgrenzen wie im Umwandler üblich.
- ~~**N3**~~ **entschieden (Nutzer 2026-09-29): sofort (U-5)**, mit der Anker-Sicherung aus 6.2 und einem Knopf
  „gemerkte Kästen dieses Absenders verwerfen“ (z. B. bei neuem Briefpapier).
- ~~**N4**~~ **entschieden (Nutzer 2026-09-29): Prüfstatus jetzt, Pflichtfelder später.** Eigenes, vom System gesetztes
  Merkmal am Knoten: ungeprüft / geprüft (von, am) / automatisch übernommen – getrennt vom Freigabestatus (`status_id`).
  Grundlage für den Filter „automatisch, nie angesehen“ (U1), die Abarbeitungsliste und „Speichern und weiter“ zum
  nächsten ungeprüften Dokument. Pflichtfelder erst mit Dokumentarten (U4), sonst gälten sie für jedes Dokument.
- ~~**N5**~~ **entschieden (Nutzer 2026-09-29):** (1) Häkchen **„daraus nicht lernen“** beim Speichern (Werte speichern,
  nichts merken); (2) **Verwalter-Übersicht des Gelernten** je Absender (Beschriftungen und Kästen, Datum, Anzahl
  Bestätigungen, zuletzt von wem) als normale Odoo-Liste, Einträge einzeln löschbar. **Nicht:** verzögertes Umlernen erst
  nach zweimaliger Abweichung (schwer nachvollziehbar; mit 1 und 2 lassen sich Fehler beheben).
- ~~**N6**~~ **entschieden (Nutzer 2026-09-29): nur die aktive Stelle kräftig**, alle übrigen Funde dezent umrandet,
  gegenseitiges Hervorheben Feld ↔ Stelle mit Mitscrollen. Umschalter „alle farbig anzeigen“ nur, falls er beim
  Ausprobieren fehlt.
- ~~**N7**~~ **entschieden (Nutzer 2026-09-29): mit dem Eingangsordner (Schritt 7)**, dort fester Baustein.
  Ablageregel je Absender (Vorbild PaperOffice-Ablagemasken): Dateiname aus Platzhaltern (z. B. `{Dokumentdatum}
  Jahresbescheid Wasser.pdf`), Zielordner (auch Jahr/Monat), Tags; das Prüf-Fenster schlägt „umbenennen in … /
  verschieben nach …“ mit Häkchen vor; die Regel kann aus dem bisherigen Ablageort der Dokumente eines Absenders
  vorgeschlagen werden. Vorher kaum anwendbar, weil vorhandene Dateien schon richtig liegen und heißen.
- ~~**N8**~~ **entschieden (Nutzer 2026-09-29), neue Scheibe U-7:** jetzt Verknüpfung zu Odoo-Datensätzen, Ankreuzfeld,
  Auswahl, Telefon, Prozentsatz, Monat sowie die Feldeigenschaften Hilfetext, Platzhalter, Standardwert,
  Gruppen-Sichtbarkeit, Datums-Warnung/-Grenzen. **Bei Bedarf:** Datum mit Uhrzeit, mehrzeiliger Text, URL. **Nicht:**
  Priorität, Datei, Bild, Signatur, formatierter Text, Stichwörter je Feld; Tabellen bleiben außerhalb (E6).

### 10.6 Abgleich mit Odoos Feldtypen (zu N8)

Gelesen: [Studio – Felder und Widgets](https://www.odoo.com/documentation/19.0/de/applications/studio/fields.html)
vollständig im Originaltext. **Studio ist Enterprise** (`web_studio` nicht im Image); die Feldtypen dahinter sind
Odoo-Grundgerüst. **Korrigiert (10.7):** Odoo unterscheidet reguläre Felder (echte Spalten; in Community ohne Studio
auch über Einstellungen → Technisch → Felder als `x_`-Felder anlegbar) und **Eigenschaftsfelder** (Properties,
keine Spalten, an einen übergeordneten Datensatz gebunden oder global). Typen der Eigenschaften im Quellcode
(`odoo/orm/fields_properties.py`, `ALLOWED_TYPES`): `boolean, integer, float, text, char, html, date, datetime,
monetary, many2one, many2many, selection, tags, separator`.

| Odoo-Typ (Studio / Properties) | Unsere Wertart | Befund |
|---|---|---|
| Text (`char`), Widgets E-Mail / Telefon / URL | Nummer, Wort, IBAN, USt-IdNr., E-Mail | wir sind feiner (Prüfziffern, Formate); **Telefon und URL fehlen** – Telefonnummern stehen oft unter den nicht zugeordneten Paaren und wären für „Kontakt aus Dokument“ (U-8) nützlich |
| Mehrzeiliger Text (`text`) | – | fehlt (Betreff, Verwendungszweck); „Wort“ fasst höchstens 5 Wörter |
| Ganzzahl (`integer`) | – (Nummer ist bewusst Text) | nicht nötig |
| Dezimal (`float`), Widget Prozentsatz | Menge mit Einheit | **Prozentsatz fehlt** (Zinssatz, Umsatzsteuersatz, Anpassung in %) |
| Monetär (`monetary`) | Betrag | vorhanden |
| Datum (`date`), Eigenschaften „Minimale Genauigkeit Monat/Jahr“, „Warnung für zukünftige Daten“, „frühestes/spätestes Datum“ | Datum | vorhanden; **Monatsangaben fehlen** („Leistungsmonat 03/2025“, „März 2025“ – unser Datum braucht einen Tag); Zukunfts-Warnung und Grenzen wären gute Plausibilitätsprüfungen |
| Datum/Zeit (`datetime`) | – | fehlt (Termine mit Uhrzeit) |
| Datumsbereich (Widget) | Zeitraum/Dauer | vorhanden, bei uns zusätzlich Dauer („24 Monate“) |
| Kontrollkästchen (`boolean`) | – | fehlt (N8 „Ankreuzfeld“) |
| Auswahl (`selection`) | – | fehlt (N8 „Auswahlliste“) |
| Many2One (`many2one`) | nur Kontakt (fest eingebaut) | **allgemeine Verknüpfung zu Odoo-Datensätzen fehlt** – z. B. Fahrzeug über Kennzeichen, Mitarbeiter, Projekt, Bestellung; erkannt über die Suche des Zielmodells (`name_search`), wie heute der Absender |
| Many2Many / Stichwörter (`tags`) | Tags am Dokument | je Feld nicht nötig |
| Zeilen (`one2many`) | – | Tabellen bewusst außerhalb (E6) |
| Priorität, Datei, Bild, Signatur, Html, Zugehöriges Feld | – | für Erkennung nicht sinnvoll |

Feldeigenschaften aus Studio, die auch für unsere Felder passen: **Hilfe-Tooltipp**, **Platzhalter**, **Standardwert**,
**Sichtbarkeit nur für bestimmte Gruppen** (z. B. Gehaltsfelder), **Pflicht** (N4: später), bei Daten **Warnung für
Zukunft** und **früheste/späteste Grenze**.

### 10.7 Speicherform der Werte: eigene Modelle, Eigenschaftsfelder oder reguläre Felder?

Anlass: Hinweis des Nutzers auf [Eigenschaftsfelder](https://www.odoo.com/documentation/19.0/de/applications/essentials/property_fields.html)
(vollständig im Originaltext gelesen). Geprüft im Odoo-19-Quellcode:

- Eigenschaften sind **keine Datenbankspalten** (JSON am Datensatz), die Definition hängt an einem **übergeordneten
  Datensatz** (Projekt → Aufgaben). **Neu in Odoo 19:** `properties.base.definition.mixin` für **globale**
  Eigenschaften ohne übergeordneten Datensatz – genutzt von `res.partner` und `mailing.contact`; Definition anlegen oder
  löschen dürfen nur Odoo-Administratoren (`base.group_system`).
- Definition erlaubt nur feste Angaben (`ALLOWED_KEYS`: Name, Typ, Standardwert, Suffix, Auswahl, Stichwörter, Domain,
  „In Karten anzeigen“, Einklappen, Währung); Erweiterung nur über einen Haken, der für **alle** Eigenschaften in Odoo
  gilt (`_additional_allowed_keys_properties_definition`).
- **Suchen und Gruppieren** nach Eigenschaften: vorhanden (Suchmodell, `_read_group_groupby_properties`).
  **Summieren/Aggregieren: nicht möglich** (`_read_group_select`: „this dot notation is not supported“).
- Eine Eigenschaft löschen entfernt ihre Werte bei **allen** Datensätzen.
- Reguläre Zusatzfelder (`x_`) über `ir.model.fields` gibt es auch in Community (so arbeitet Studio).

| Weg | Vorteile | Nachteile | Bewertung |
|---|---|---|---|
| **A – eigene Modelle** (heute: `extraction_field` + `field_value` mit typisierten Spalten) | volle Kontrolle über Wertarten (IBAN, USt-IdNr., Zeitraum, Menge, neue Arten aus U-7), **Herkunft und Fundstelle je Wert**, Lernen, eigene Rechte (U2), **Summen und Pivot** über typisierte Spalten | Werte erscheinen nicht von selbst als Spalte oder Filter an der Datei; dafür eigene Oberfläche (Prüf-Fenster, U-9 „Werte nutzen“) | **bleibt Grundlage** |
| **B – globale Eigenschaften** an der Datei (wie `res.partner`) | Odoo-eigene Anzeige im Formular, „In Karten anzeigen“, Filter und Gruppieren je Eigenschaft ohne Eigenbau | **keine Summen**; keine Herkunft/Fundstelle je Wert; Wertarten zu grob (keine Prüfziffern, kein Zeitraum/Menge/Telefon/Prozent/Monat); Erkennungseinstellungen passen nicht in die Definition; Löschen einer Eigenschaft löscht alle Werte; Lernen und Regeln bräuchten trotzdem eigene Modelle → zwei Wahrheiten | als alleinige Speicherform **verworfen** |
| **C – reguläre `x_`-Felder** je Katalogfeld (wie Studio) | alles nativ: Listenspalten, Filter, Gruppieren, **Summen**, Export, echte Typen | jedes neue Feld ändert zur Laufzeit das Datenbankschema der großen Dateitabelle und lädt die Odoo-Registry in allen Prozessen neu; Typwechsel und Löschen schwierig (Spalte fällt weg); Herkunft/Lernen bräuchten trotzdem eigene Modelle | als **alleinige** Form verworfen (Herkunft/Lernen fehlen); das Risiko ist nach Messung aber klein (siehe unten) → als **Ergänzung zu A gewählt (N9)** |
| **D – A plus Spiegel in globale Eigenschaften** (bestätigte Werte zusätzlich als Eigenschaft an der Datei) | native Anzeige in Karten und Filter je Feld | doppelte Speicherung, Abgleich in beide Richtungen nötig (Bearbeiten im Formular würde am Prüfweg vorbeischreiben), Löschrisiko | **nicht empfohlen**; die Vorteile holt U-9 mit Odoo-Bordmitteln über `field_value` (Filter, Gruppieren, Pivot mit Summen) |

**Messung zu C** (Tower, Wegwerf-Datenbanken): Spalte an eine Tabelle mit 1,4 Mio. Zeilen anhängen 2–3 ms, entfernen
~5 ms (PostgreSQL 16, Spalte ohne Standardwert); echtes `x_`-Feld (`ir.model.fields`, `state='manual'`) an
`int_filemanager.node` anlegen einschließlich Neuaufbau der Registry ≈ 0,1 s je Feld, löschen 0,2 s. Weitere Odoo-Prozesse
laden beim nächsten Aufruf neu (wie bei Studio). Nebenbefund: zwei Felder des Knotens tragen dieselbe Bezeichnung
„Created on“ (`create_date`, `mtime`) – kleine Korrektur für später.

**Der eigentliche Unterschied** (praktisches Beispiel mit dem Nutzer durchgespielt: alle Wasserbescheide, Betrag je Jahr,
Excel für Steuer/Wohngeld): in A steht jeder Wert als eigene Zeile – Filtern geht, aber **Auswertungen über mehrere Felder**
(Betrag je Jahr des Rechnungsdatums), **Spalten in der Dateiliste** und **Export „eine Zeile je Datei“** gehen nicht mit
Odoo-Bordmitteln. Mit echten Spalten geht all das über Odoos normale Spalten, „Gruppieren nach“, Summen, Pivot und Export.

- ~~**N9**~~ **entschieden (Nutzer 2026-09-29): A plus echte Spalten.** A (`extraction_field` + `field_value`) bleibt die
  Grundlage für Herkunft, Fundstelle, Fassung und Lernen. Zusätzlich bekommt jedes aktive Katalogfeld eine echte Spalte
  (`x_`-Feld) an `int_filemanager.node` mit der passenden Art (Betrag + Währung, Zeitraum als zwei Datumsspalten,
  Verknüpfung als echtes many2one, Auswahl als selection …). Regeln: Spalten werden **nur vom System** befüllt (Speichern im
  Prüf-Fenster, Automatik), für Nutzer schreibgeschützt; Verwalter-Knopf **„Spalten aus den Werten neu aufbauen“**;
  Archivieren eines Felds **blendet die Spalte nur aus** (Daten bleiben), Löschen nur als ausdrückliche Verwalter-Aktion
  mit Rückfrage; die Spalte zeigt den Wert der **aktuellen Fassung**. Umsetzung in U-7 (Spaltenarten, Kopplung
  Katalogfeld ↔ Spalte) und U-9 (Spalten einblenden, Filter, Gruppieren, Pivot, Export).

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
