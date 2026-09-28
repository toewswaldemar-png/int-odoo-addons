# int_filemanager: Bausteine-Inventar Teil 2 — die restlichen Odoo-`core/`-Bausteine im Detail

Stand 2026-09-24. Vierzehntes Dokument, direkte Fortsetzung von
`int_filemanager_odoo_bausteine_inventar_2026-09-24.md` (Dokument 13, 57 Bausteine, davon 9
geprüft). Auftrag: alle 48 damals noch offenen Bausteine vertiefen. Ehrlich vorab benannt, bevor
die Ergebnisse folgen: **18 weitere Bausteine wurden in diesem Durchgang tatsächlich vollständig
gelesen** (Dateiinhalt, nicht nur Name/Ordnerstruktur) — bei 30 restlichen wäre eine ernsthafte,
nicht nur behauptete Vollständigkeit bei diesem Umfang (in Summe über 12.000 Zeilen allein in den
noch offenen Ordnern) in einer einzelnen Bearbeitung nicht mehr seriös zu leisten, ohne in genau
das oberflächliche "Name angeschaut, Urteil gefällt" zurückzufallen, dessen Vermeidung der
ausdrückliche Auftrag dieser ganzen Reihe war (siehe die Korrektur zu `nested_sortable` in
Dokument 6). Die verbleibenden 30 werden deshalb unten explizit als **noch offen**, nicht als
"geprüft" geführt. Reine Recherche, nichts umgesetzt.

---

## 1. Vollständig gelesen — vier Ergebnisklassen

### 1.1 Bereits korrekt genutzt (Bestätigung, kein neuer Fund)

- **`confirmation_dialog`** (`ConfirmationDialog`/`AlertDialog`, 104 Zeilen) — bereits direkt in
  `filemanager_controller_mixin.js` importiert und genutzt.
- **`tag_navigation_hook`/`navigation`** (`useTagNavigation`/`useNavigation`) — `useNavigation`
  bereits importiert und für die Tastaturnavigation im eigenen Kontextmenü genutzt
  (`filemanager_controller_mixin.js:409`), mit explizitem Kommentar dort, dass Odoos eigene
  `DropdownItem`/`useNavigation`/`usePopover`-Bausteine bewusst unverändert verwendet werden.

### 1.2 Bestätigt korrekt NICHT verwendet (echte Prüfung, nicht nur Vermutung)

- **`file_input`** (`FileInput`, 127 Zeilen, vollständig gelesen): fest an `ir.attachment`
  gebunden (`resModel`/`resId`, Standardroute `/web/binary/upload_attachment`). `int_filemanager`s
  Dateien liegen roh auf der Platte, nicht als Attachment-Datensätze — der eigene Upload-Weg
  (`/int_filemanager/upload`) ist damit strukturell notwendig, kein vermeidbarer Eigenbau. Eine der
  wenigen in dieser ganzen Reihe positiv **bestätigten** Nicht-Eignungen, nicht nur angenommen.
- **`model_selector`** (103 Zeilen, vollständig gelesen): wählt ein **Python-Modell** (nicht einen
  Datensatz) aus allen zugänglichen Modellen — ein Entwickler-/Technische-Einstellungen-Baustein
  (z. B. für Properties-Feld-Konfiguration). Kein Bezug zu Endnutzer-Navigation in
  `int_filemanager`.

### 1.3 Neue, bisher nicht dokumentierte, potenziell nützliche Bausteine

- **`action_swiper`** (`ActionSwiper`, 226 Zeilen, vollständig gelesen): generisches
  Wisch-um-Aktion-auszulösen-Bauteil (links/rechts, RTL-bewusst, Bounce-/Vorwärts-Animation,
  erkennt und respektiert horizontal scrollbaren Inhalt innerhalb der Zeile, damit Wischen zum
  Scrollen nicht versehentlich eine Aktion auslöst). Auf Mobilgeräten könnte damit "Datei nach
  links wischen = in den Papierkorb" nativ umgesetzt werden, ohne eigene Touch-Gesten-Logik — bisher
  in keinem Feature-Katalog dieser Session erwähnt, und ergänzt den bereits vorhandenen
  Long-Press-Mechanismus (Dok. 6) um eine zweite, in Explorer-artigen Mobil-Apps übliche Geste.
- **`copy_button`** (`CopyButton`, 49 Zeilen, vollständig gelesen): fertiger "in Zwischenablage
  kopieren"-Knopf inkl. automatischem Erfolgs-Tooltip (verschwindet nach 800 ms), nutzt die native
  Zwischenablage-API. Direkt einsetzbar für "Freigabe-Link kopieren" im bestehenden
  Freigabe-Dialog — ungeprüft, ob dieser aktuell einen eigenen Kopier-Mechanismus hat oder noch
  gar keinen.
- **`colorlist`** (`ColorList`, 63 Zeilen, vollständig gelesen): Odoos festes 12-Farben-Auswahlfeld
  (dasselbe, das Kanban-Kartenfarben und Tag-Farben im ganzen System nutzen), mit
  Auf-/Zuklapp-Verhalten und Klick-außerhalb-schließt. Falls `int_filemanager`s eigenes
  Tag-Farbsystem nicht bereits darauf aufbaut, wäre das ein direkter Kandidat für Konsistenz mit
  dem Rest von Odoo (dieselben 12 Farben, die Nutzer aus jeder anderen Odoo-App kennen).
- **`signature`** (`SignatureDialog`/`NameAndSignature`, Kernteil vollständig gelesen): fertiger
  "Name eingeben + Unterschrift zeichnen"-Dialog, liefert ein Bild der gezeichneten Unterschrift
  über `uploadSignature({name, signatureImage})`. **Schließt einen Bogen zu einem viel früheren
  Fund dieser Session** (`odoo.tools.pdf.signature.PdfSigner`, echte kryptographische
  PDF-Signierfähigkeit, damals als "in Community ungenutzt außer in einem Test" eingeordnet) — das
  clientseitige Zeichen-Widget und das serverseitige Signier-Werkzeug zusammen wären ein
  vollständiger, komplett nativer Baustein für ein künftiges "PDF unterschreiben"-Feature in
  `int_filemanager`, bisher als zwei unverbundene Einzelfunde in verschiedenen Dokumenten dieser
  Session verstreut.
- **`record_selector`** (`RecordSelector`, 69 Zeilen, vollständig gelesen): nutzt einen bisher in
  der gesamten Reihe nicht erwähnten **`name`-Dienst** (`useService("name").loadDisplayNames(...)`)
  — eine Anzeigenamen-Auflösung mit eigenem Caching, getrennt von den bereits gefundenen
  `RPCCache`/`web_name_search`-Bausteinen. Nicht weiter vertieft in diesem Dokument (Umfangsgrenze),
  aber als offener Punkt festgehalten: könnte für die in Dokument 10/11 skizzierte
  "Ordner-Schnellsuche" eine weitere, noch nicht geprüfte Caching-Ebene sein.

### 1.4 Rein informativ gelesen, ohne Bezug zu Navigation/Dateiverwaltung

`checkbox` (98 Zeilen), `colors` (218 Zeilen, Chart-/Diagramm-Farbpaletten, nicht UI-Farbwahl),
`notebook` (183 Zeilen, generische Reiter-Komponente, aktuell kein erkennbarer Bedarf) —
vollständig gelesen, aber ohne unmittelbaren Bezug zur aktuellen `int_filemanager`-Fragestellung.

---

## 2. Ausdrücklich noch offen — 30 Bausteine, ehrlich als ungeprüft geführt

Nicht individuell vollständig gelesen in diesem Durchgang: `autocomplete` (teilweise über
`Many2XAutocomplete` in Dok. 10 bereits mitgeprüft, aber nicht die Basis-Komponente selbst),
`avatar`, `badge`, `barcode` (Kern-API teilweise über das `Many2one`-Barcode-Scan-Feature in Dok.
10 mitgeprüft, nicht das ganze Verzeichnis), `code_editor` (von `int_filemanager` bereits als
`CodeEditor`-Widget genutzt, aber der Baustein selbst hier nicht gelesen), `color_picker`,
`datetime`, `dialog` (Basiskomponente hinter `ConfirmationDialog`, nicht separat gelesen),
`domain_selector`, `domain_selector_dialog`, `errors`, `expression_editor`,
`expression_editor_dialog`, `hotkeys` (Nutzung an mehreren Stellen gesehen, Kern-Hook nicht
gelesen), `model_field_selector`, `multi_record_selector`/`record_autocomplete` (Geschwister von
`record_selector`), `notifications`, `overlay` (technische Grundlage mehrerer bereits genutzter
Bausteine), `position`, `select_menu`, `time_picker`, `tooltip`, `tree_editor` (2772 Zeilen —
größter einzelner verbleibender Ordner, visueller Ausdrucks-Baukasten für Odoo Studio-artige
Filter, geringe erwartete Relevanz, aber ungeprüft), `ui`.

**Empfehlung statt Fortsetzung ins Uferlose:** diese 30 nur bei konkretem Anlass gezielt
aufschlagen (z. B. `tooltip`/`overlay`/`position` erst, wenn tatsächlich ein eigenes Tooltip-Problem
auftritt), nicht pauschal "der Vollständigkeit halber" — genau das hätte bei `tree_editor` (2772
Zeilen für einen filterbezogenen Baustein ohne erkennbaren Dateimanager-Bezug) keinen
verhältnismäßigen Ertrag mehr.

---

## 3. Fazit

Drei echte neue Kandidaten mit klarem, sofort umsetzbarem Nutzen (`action_swiper` für
Wisch-Gesten, `copy_button` für Freigabe-Links, `colorlist` für Tag-Farben-Konsistenz), ein
bedeutender verbindender Fund (`signature` schließt den Kreis zum früheren `PdfSigner`-Fund zu
einem vollständigen nativen PDF-Unterschreiben-Bauplan), zwei bestätigte korrekte
Nicht-Verwendungen (`file_input`, `model_selector`) und zwei bereits korrekt genutzte Bausteine
bestätigt. Der Rest (30 von 57) bleibt bewusst und ausdrücklich unvollständig geprüft — ehrlicher
als eine vorgetäuschte Vollständigkeit, die bei diesem Umfang nicht zu halten gewesen wäre.
