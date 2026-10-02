# PaperOffice Classic: Ideenkatalog für int_filemanager (A1 bis H6)

Stand 2026-10-01. Ergebnis der Recherche in der PaperOffice-Classic-Hilfe (öffentliches Portal) und
des Abgleichs mit dem Odoo-19-Quellcode (`C:\Users\Admin\Documents\GitHub\odoo`, Community).
Der Katalog ist **unabhängig vom Ist-Stand des Moduls** aufgestellt; was schon gebaut ist, steht
in `int_filemanager_stand.md`.

Zeichen: **✔** = Odoo-Baustein im Quellcode gefunden. **–** = in Odoo Community nichts Passendes,
wäre Eigenbau. Nichts davon ist im Browser erprobt, wo nicht ausdrücklich vermerkt.

Die Bilder des PaperOffice-Hilfeportals liegen hinter einer Anmeldung (Antwort 401); gesehen
wurden nur zwei Bilder des Einführungsvideos (drei Spalten: Ordnerliste, Dokumentliste aus Karten,
große Seitenvorschau).

## A. Werte erkennen und prüfen

| # | PaperOffice | Odoo-Weg | Aufwand |
|---|---|---|---|
| A1 | **OCR-Textschicht über der Vorschau**, per Klick auf einen Block übernimmt man den Wert ins Feld („Text aus OCR einfügen“). Der Block wird beim Überfahren gelb, nach dem Klick grün. | „Im Dokument wählen …“ als Eintrag der Feldliste (`AutoComplete`-Option ✔), Ereignis auf `record.model.bus` ✔, Wortflächen aus `viewer_overlay.js`. | mittel |
| A2 | **Blauer Strich** für „automatisch gelesen“, am Feld und im Dokument. | Eigene Klasse am Feld in `$o-action`, ähnlich `o_field_highlight` ✔. Umrandung im Dokument ist vorhanden. | klein |
| A3 | **Zähler pro Reiter** („6 erkannt“). | Stat-Button im Formularkopf (`button_box`, `oe_stat_button`, `stat_info` ✔). | klein |
| A4 | **Vorlagen einlernen:** Pflicht sind Schlagwörter (Kundennummer, E-Mail, USt-IdNr.), optional das Aussehen (Kopf/Fuß per Klick markiert). Nur Seite 1 zählt. Eine **Testtaste** prüft, ob alle Schlagwörter gefunden werden. | Entspricht unserem Lernen je Absender. Neu wäre die Testtaste und das optionale „Aussehen“ (Bildvergleich des Kopfs). | mittel bis groß |
| A5 | **Variablen mit Positionsregel:** „exakt dieselbe Stelle“, „zwischen zwei Begriffen“, „irgendwo im Dokument“, dazu Regex mit Index und „Werte entfernen/hinzufügen“. Name und Farbe je Variable. | Unsere Hinweise je Absender (Beschriftung und Lage) decken das teilweise ab. „Zwischen zwei Begriffen“ und „Regex mit Index“ fehlen. Katalogregeln gibt es als Regex schon. | mittel |
| A6 | **Datumskürzel** am Datumsfeld (heute, +1 Tag, +1 Woche, +1 Jahr). | Odoos Datumsfeld hat nur die Markierung des heutigen Tags (`o_today` ✔), keine Schnellknöpfe. Eigenbau als kleines Menü. | klein |
| A7 | **Wörterbuch (SmartSpell):** OCR-Fehler korrigieren, je Sprache „erkannt → richtig“, Eigennamen, wirkt auf alle künftigen Dokumente. Gilt nicht für digitale PDFs mit eingebettetem Text. | – In Odoo Community nichts gefunden (keine OCR- oder Rechtschreib-Module). Eine einfache Odoo-Liste (`erkannt`, `ersetzt`, `Sprache`) und Anwendung beim Einlesen. | mittel |
| A8 | **Erkannten Text korrigieren und neu erzeugen** („Texterkennung neu erstellen“, „kopieren“, „Texterkennung speichern“, Suche im Text mit grüner Markierung). | Text als Feld am Knoten bearbeiten und neu lesen lassen (Knopf in Aktionsmenü). Markierung der Suche: pdf.js-Hash `#search=…&phrase=true` ✔. | klein bis mittel |
| A9 | **Dublettenwarnung** mit Waage statt Vorschau, plus „Dokument im neuen Fenster öffnen“ und „Abbrechen und Dokument aufrufen“. | Gleicher Inhalt: Hash vorhanden (Blob). Ähnlicher Inhalt: Trigram-Index auf dem Text (`pg_trgm`, ist schon da). Anzeige als `alert alert-warning` wie die Dublettenwarnung an Rechnungen. | mittel |
| A10 | **Bekannt oder unbekannt:** Häkchen oder Fragezeichen am Dokument. Bei unbekannt „Dokument einlernen“. | Zeile im Formular „Bekannter Absender“ oder „Neuer Absender – wird beim Speichern gemerkt“ (`alert alert-info`). | klein |

## B. Formular und Vorschau

| # | PaperOffice | Odoo-Weg | Aufwand |
|---|---|---|---|
| B1 | **Seitenminiaturen** rechts neben der großen Vorschau. | pdf.js-Hash `#pagemode=thumbs` ✔. | klein |
| B2 | **Hover-Lupe:** beim Überfahren erscheint der Bereich vergrößert in der Ecke. | Tooltip-Dienst mit `data-tooltip-template="web.ImageZoomTooltip"` ✔ (nur für `<img>`, nicht im pdf.js-Rahmen, und wir haben ein Seitenbild nur für Seite 1). | klein |
| B3 | **Seite drehen** (180°), **Drucken**, **als PDF öffnen**, **mit Outlook senden**. | Drehen und Drucken sind Knöpfe in pdf.js (Rotation lässt sich per `hidePDFJSButtons` ein- oder ausblenden ✔). Senden: Odoo-Mail-Assistent mit Anhang. | klein |
| B4 | **Symbole mit Zähler neben der Vorschau:** Kontakte, Notizen, Aufgaben, Versionen. Klick öffnet die Liste oder legt neu an. | Stat-Buttons (siehe A3). | klein |
| B5 | **Eigenes Fenster** für Seite oder Vorschau. | Haben wir (`mail.popout` ✔ und `FileViewer`). | – |
| B6 | **Dokumenteigenschaften als Reiter:** Allgemein, Basis, Verschlagwortung, Beleg, Benutzerdefiniert, Sicherheit, mit „Änderung speichern“ unten. Vergrößerbar per Pfeil. | Odoo-`notebook` mit Seiten ✔. Bei uns reichen Gruppen im Formular. Die Vergrößerung entspricht dem Symbol „Erweitern“ im `FormViewDialog`. | klein |
| B7 | **Gelber Zettel** (Post-it) mit der Bemerkung neben dem Dokument. | Notizfeld am Knoten und in der Kachel als Zettel (`bg-warning-subtle`). | klein |
| B8 | **Priorität als Sterne** und **Wichtigkeit**. | `priority`-Widget ✔ (Odoo-Sterne). | klein |
| B9 | **Originalablageort** („Schrank Buchhaltung“) als Auswahlliste mit Verwaltung. | Many2one auf eine kleine Liste. Besonders für Papierdokumente (Ihr Privatordner-Ziel) hilfreich. | klein |
| B10 | **Dokument-ID (POD-Nummer)** und QR-Code in den Eigenschaften. | Fortlaufende Nummer über `ir.sequence`. QR: `/report/barcode/QR/<wert>` ✔. | klein |

## C. Liste, Ansichten, Suche

| # | PaperOffice | Odoo-Weg | Aufwand |
|---|---|---|---|
| C1 | **Fünf Anzeigetypen:** nach Ordner, Status, Schlüsselwörter, Dokumenttyp, Kontakt. Ein Dokument erscheint bei jedem seiner Werte. | `groupby` in Liste und Kanban ✔ und das **Suchpanel** (`<searchpanel>`, mit Zählern `enable_counters`, `expand`, `hierarchize` ✔) links. Das entspricht den Filtergruppen der erweiterten Suche. | mittel |
| C2 | **Schnelle Ansichten:** Zuletzt hinzugefügt, Favoriten, Merkliste, Alle verfügbaren, „Von mir in Bearbeitung“. | Gespeicherte Filter (`ir.filters`) und `boolean_favorite` ✔. Favoriten und Merkliste als Kopie-Ordner sind bei uns besser als Markierung. | klein |
| C3 | **Karten in der Liste:** Seite 1 als Miniatur, Dateityp links unten, Seitenzahl rechts unten, Datum oben, Statusbalken links, der bei Hover ausfährt. | Kanban mit Badges (`badge`, `color_field` ✔). Seitenzahl braucht ein Metadatenfeld. | klein |
| C4 | **Symbole in der Karte mit Zähler** (Notizen, Aufgaben, Kontakte, Versionen). | Wie A3, als Badges in der Kachel. | klein |
| C5 | **Untere Leiste „Dokumente: N, davon angezeigt M“.** | Odoo-Pager (`1-80 / 321`) ✔ vorhanden. | – |
| C6 | **Live-Suche ohne Enter**, bei Klick ins Feld die letzten Dokumente. | Odoos Suche braucht Enter. Eine Live-Trefferliste gibt es als **Befehlspalette** (Strg+K, `command_provider` ✔), in der Dokumente als Quelle eingehängt werden können. | mittel |
| C7 | **Suchleiste mit QR-Symbol:** Dokument per Kamera finden. | `barcode_dialog` mit ZXing-Fallback ✔ (Odoos Kamerascanner). Gefundene Nummer → Dokument öffnen. | klein bis mittel |
| C8 | **Erweiterte Suche:** Datum (heute, Jahr, frei), Benutzer, Status, Schlüsselwörter, Typ, Ablage, Kontakte, Datum auf Dokument, Posteingang, mit Grenze „Gesamte Datenbank / Ordner / Ordner und Unterordner“. | Suchpanel plus Filter (`search view`) ✔. Die Ordnergrenze entspricht der Suche mit `child_of`. | mittel |
| C9 | **Excel-Export** aus der Ergebnisliste, mit Belegdaten und benutzerdefinierten Feldern (Steuerberater). | Odoos Export (`export`-Dialog) ✔ auf den Feldern des Knotens. | klein |
| C10 | **Kontextmenü** mit allen Dokumentaktionen, auch per Knopf an der Karte. | Haben wir (Rechtsklick und Kontextmenü). Die Einträge von PaperOffice sind eine gute Checkliste, siehe E. | – |

## D. Notizen, Aufgaben, Termine

| # | PaperOffice | Odoo-Weg | Aufwand |
|---|---|---|---|
| D1 | **Notiz auf einem Dokumentbereich** (mit gedrückter Maus aufgezogen), beliebig viele pro Seite, verändert das Dokument nicht. Links öffnet sich ein Notizfenster. | Eigenes Modell mit Seite und Rahmen (in Prozent der Seite). Die Kommentare dazu über `mail.thread` ✔ (Odoo-Verlauf mit Antworten). Aufziehen: eigener Zeichner, bei Bildern evtl. Cropper.js. | groß |
| D2 | **Kommentare pro Notiz** als Chat-Verlauf, Antworten, löschen, Zeitstempel. | Odoo-Chatter (`mail.thread`) ✔. | klein |
| D3 | **Aufgaben nur zusammen mit Notizen**, nach „Was, Wer, Wann“, mit Vorlagen für wiederkehrende Aufgaben. | `mail.activity` ✔ (Aufgabe mit Frist und Verantwortlichem, mit Typen als Vorlagen). | klein |
| D4 | **Briefing beim Start:** was heute und in den nächsten 14 Tagen fällig ist (Wiedervorlage, Fälligkeit, erledigt). | Odoos Aktivitätsmenü in der Kopfleiste und die **Aktivitätsansicht** (`views/activity` ✔) plus „Meine Aktivitäten“. Wiedervorlage und Fälligkeit als Aktivitäten. | klein |
| D5 | **Kalenderansicht** mit Filtern (Dokumente, E-Mails, mit Notizen/Aufgaben/Kontakten, Benutzer, relevantes Datum). | Odoos Kalenderansicht (`views/calendar` ✔) auf Datumsfeldern des Knotens. | klein bis mittel |
| D6 | **Notizverwaltung:** alle Notizen listen, filtern (Dokument, Benutzer, Inhalt, Zeitraum), durchsuchen. | Listenansicht auf dem Notiz-Modell mit Suchfiltern. | klein |
| D7 | **Erledigt-Haken** nimmt das Dokument aus dem Briefing. | `mail.activity` „als erledigt markieren“ ✔. | klein |

## E. Ablage, Eingang, Automatik

| # | PaperOffice | Odoo-Weg | Aufwand |
|---|---|---|---|
| E1 | **Ablagemodi:** immer Dialog zeigen, nur wenn unbekannt, nie zeigen (Hintergrund), manuell, immer fragen. | Einstellung je Eingangsordner. „Nur wenn unbekannt“: Aktivität „prüfen“ nur für unbekannte Absender. | mittel |
| E2 | **Ablagemasken:** Name, Datum, Bemerkung, Ordner, **automatische Unterordner nach Jahr/Monat**, Status, Typ, Schlüsselwort, Workflow, Belegdaten, benutzerdefinierte Felder. Wird durch eine erkannte Vorlage ausgelöst oder von Hand gewählt. | Eine „Ablageregel“ als Modell, angewandt beim Eingang. Platzhalter über `mail.render.mixin` ✔ (Odoo-Vorlagen mit `{{ … }}`). | mittel bis groß |
| E3 | **Variablen in Masken:** `[%DOCUMENT_FILENAME%]`, `[%TODAY%]`, `[%TODAY+7days%]`, eigene Variablen aus der Vorlage. | Odoo-Platzhalter und Datumsrechnung (`relativedelta`, `format_date`) in `mail.render.mixin` ✔. | klein bis mittel |
| E4 | **Ordnerüberwachung (ExplorerConnect):** Verzeichnis beobachten, nach dem Import in Unterordner verschieben oder löschen, mit Modus. | Haben wir (Eingangsordner mit Ruhezeit, `_übernommen`). | – |
| E5 | **Mail-Import:** Anhänge aus Outlook in die Ablage, Outlook-Überwachung. | Odoo-**E-Mail-Alias** (`mail.alias.mixin` ✔): Eine Adresse je Ordner, Anhänge landen automatisch dort. Kein Outlook-Zusatz nötig. | mittel |
| E6 | **Stapelscan mit Trennseiten:** gedruckte Trennseite zwischen Dokumenten, danach automatisch aufgetrennt. | – Nichts in Odoo. Im Umwandler (Trennseite per QR erkennen, PDF teilen, Odoos `extract_page` und `merge_pdf` helfen ✔). Passt zu Ihren Papierdokumenten. | mittel bis groß |
| E7 | **QR-Aufkleber** (Dokument-ID) auf Papier, beim Scannen erkennt PaperOffice das Dokument und legt eine neue Version an. | QR erzeugen (`/report/barcode/QR` ✔), im Umwandler lesen (zxing steht im Konzept für GiroCode). | mittel |
| E8 | **Massenimport** ohne Prüfung (bewusst „nicht für geprüfte Datenablage“). | Eingangsordner mit Modus „ohne Analyse“. | klein |
| E9 | **Scanner (TWAIN), virtueller Drucker, WebCapture, Bildschirmfoto.** | Browser kann nicht scannen. Vorschlag: Hochladen vom Handy und Eingangsordner des Scanners (Samba). Virtueller Drucker und WebCapture: später. | – |

## F. Versionen, Sicherheit, Rechte

| # | PaperOffice | Odoo-Weg | Aufwand |
|---|---|---|---|
| F1 | **Revisionssichere Versionen:** Original bleibt als Version 1.0, jede Änderung eine Schattenkopie mit Fingerabdruck, „Zeitmaschine“, Zähler am Symbol. | Haben wir (Revisionen, Blob mit Hash). Fehlt: Zähler als Stat-Button (A3) und Notiz zur Version. | klein |
| F2 | **Aus- und Einchecken** („Quelldatei bearbeiten“, nach Bearbeitung wieder einchecken). | Sperre der Datei (`dav_lock` gibt es schon) und ein Knopf „Auschecken“. | mittel |
| F3 | **Manuell als neue Version hinzufügen** (Dokument auf ein vorhandenes ziehen). | Haben wir (Menü „Neue Version hochladen“). | – |
| F4 | **Freigabestufen mit Sternen** je Dokument (1 bis x). Benutzer unterhalb sehen das Dokument nicht, auch nicht in Suchen. | Eine Zahl am Knoten und eine Aufnahmestufe beim Benutzer, geprüft mit einer Regel (`ir.rule`, Auswertung mit Benutzer ✔). Odoo-übliche Alternative: Gruppen und Schutzordner (haben wir). | mittel |
| F5 | **Benutzergruppen mit Rechten je Datenbankbereich.** | Odoo-Gruppen und unsere Bereiche (`scope`). | – |

## G. Bearbeiten und Veredeln

| # | PaperOffice | Odoo-Weg | Aufwand |
|---|---|---|---|
| G1 | **Stempel** auf dem Dokument („Bezahlt“, „Abgelehnt“, „Eilt sehr“) mit Rahmen, Farbe, Bild, **Variablen** (Benutzer, Datum, Uhrzeit), Animation, Anzeigemodus (immer, halbtransparent, nur beim Überfahren), automatische Aktionen (Status setzen, Workflow starten). | – Nichts in Community. Ein Stempel wäre ein Modell mit Seite, Lage und Aussehen, als Überlagerung wie die Kästen, ohne das PDF zu ändern. Die Aktion beim Stempeln (Status setzen) passt zu `ir.actions.server`. Odoos `add_banner` ✔ zeigt, dass PDF-Banner serverseitig geht. | mittel bis groß |
| G2 | **WorkBench:** Seiten umordnen, Dokumente verbinden, aus Einzelseiten neue Dokumente, Inhalte radieren oder **schwärzen**, als neues Dokument speichern. | – Odoo hat serverseitig `merge_pdf`, `rotate_pdf`, `extract_page` ✔, aber keine Oberfläche. Eigenbau im Umwandler plus eine Seitenübersicht. | groß |
| G3 | **Dokumentkopie zu WorkBench**, **PDF/A-Umwandlung** für Langzeitarchiv, **Quelldatei exportieren**, **in DOCX umwandeln**. | Export haben wir. PDF/A und DOCX als Jobs im Umwandler (ocrmypdf bzw. LibreOffice). | mittel |
| G4 | **160 Sprachen für OCR** mit fester oder automatischer Spracherkennung. | Einstellung im Umwandler (Tesseract-Sprachpakete). | klein |

## H. Verwaltung und Kontakte

| # | PaperOffice | Odoo-Weg | Aufwand |
|---|---|---|---|
| H1 | **Verwaltungsmasken** für Status (mit Farbe), Schlüsselwörter, Dokumenttypen (Farbe), Originalablageorte, Workflows, Stempel, Benutzerfelder. Je mit Bezeichnung, Bemerkung, Live-Suche. | Odoo-Listen mit Farbe (`color_picker` ✔), Standard-Konfigurationsmenüs. | klein |
| H2 | **Benutzerdefinierte Felder** mit Typ (Text einzeilig/mehrzeilig, Datum, Zahl, Dezimal, E-Mail, Web, Auswahlliste, Checkbox), Vorgabewert, **Anzeige je Dokumenttyp**, Filter in der Suche (max. 1 Feld). | Unser Katalog kann das (Typen). Neu: „je Dokumenttyp“. Odoo-Properties kennen Typen ähnlich. | mittel |
| H3 | **Kontakte mit Dokumenten verbinden** (mehrere, per Rechtsklick), netzwerkfähig, Kontakt-Import (Outlook, PST, CSV), Ansicht „alle Dokumente dieses Kontakts“. | `res.partner` ✔ (Kontakt am Knoten haben wir, mehrere wären ein Many2many). Dokumente je Kontakt als Stat-Button am Kontakt. Import: Odoo-Importassistent ✔. | klein |
| H4 | **Systembenachrichtigungen:** Dokumente in Bearbeitung, in Verarbeitung, verpasste Meldungen (OCR und Vorschau erledigt?). | Haben wir teilweise (Upload-Panel und Bus-Meldungen). Odoos Benachrichtigungen (`notification`) ✔. | klein |
| H5 | **Virtuelle Ordnerverknüpfung:** dasselbe Dokument in mehreren Ordnern, ohne Kopie. | Bei uns eine Seitenverknüpfung (Many2many auf Ordner) oder Tags als virtuelle Ordner. Entscheidung nötig. | mittel |
| H6 | **Hybridmodus** (Datenbank oder echte Windows-Ordner) und **Netz** mit Freigabestufen je Ordner. | Das ist unser WebDAV-/Netzlaufwerk-Pfad (später). | – |

## Einordnung (nach Wert für das Ziel, nicht nach Aufwand)

**Sehr hoch:** A1 (Wortklick vom Feld), A7 (Wörterbuch), A9 (Dublette), A4/A5 (Vorlagen und Positionsregeln), E2/E3 (Ablageregeln mit Platzhaltern), E5 (E-Mail-Alias je Ordner), E6/E7 (Trennseiten und QR für Papier), B9 (Originalablageort), D3/D4/D7 (Aufgaben und Briefing über Aktivitäten).

**Hoch:** C1 (Suchpanel), C6/C7 (Live-Suche, QR-Scan), D1/D2 (Notizen auf Bereichen), G1 (Stempel), A8 (Text korrigieren), B1/B2/A8 (Seitenminiaturen, Lupe, Treffer im Dokument), F2 (Auschecken), G3 (PDF/A).

**Mittel:** F4 (Sterne-Stufen), H5 (virtuelle Ordner), G2 (WorkBench), D5 (Kalender), H2 (Felder je Typ).

**Bewusst klein halten:** A6 (Datumsknöpfe), B6 (Reiter), B8 (Sterne), B7 (Zettel).

## Offene Entscheidungen

1. Was ist bei uns der „Dokumenttyp“: ein Tag, ein Status oder ein neues Feld? (H2, C1, A10)
2. Sollen Dokumente in mehreren Ordnern erscheinen können (H5)?
3. Notizen auf Dokumentbereichen und Stempel: gewünscht, oder reicht die Werteerkennung?
4. Soll der Katalog später Papier-Workflows (Trennseite, QR, Originalablageort) tragen? Das gehört zum Ziel mit den Privatdateien.

## Was PaperOffice grundsätzlich anders macht

Es zieht nie einen Kasten für Werte auf. Werte werden aus einer Textschicht per Klick gewählt
oder durch Regeln (Position, zwischen zwei Begriffen, irgendwo, Regex) gefunden. Nur Notizen
werden mit einem aufgezogenen Bereich gesetzt. Das stützt die Linie: Wortklick vom Feld aus
(A1) zuerst, Kasten später.
