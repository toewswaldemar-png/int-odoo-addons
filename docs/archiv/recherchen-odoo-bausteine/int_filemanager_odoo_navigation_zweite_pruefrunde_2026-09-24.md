# int_filemanager: Ordnernavigation — unabhängige zweite Prüfrunde

Stand 2026-09-24. Auf ausdrücklichen Wunsch **unabhängig von den bisherigen acht/neun Dokumenten**
noch einmal neu gesucht, mit bewusst anderen Einstiegspunkten als zuvor (nicht Registry-Listen oder
bekannte Widget-Namen, sondern: Gegenprobe der Grundgesamtheits-Technik, sowie die alltäglichsten,
aber bisher nie tatsächlich gelesenen Bausteine — das `Many2one`-Feld selbst und der modale
Datensatz-Auswahldialog). Ergebnis: **kein Widerspruch zu den bisherigen neun Dokumenten, aber vier
echte, bisher nicht dokumentierte Ergänzungen.** Reine Recherche, nichts umgesetzt.

---

## 1. Gegenprobe der Grundgesamtheits-Technik aus Dokument 7 — bestätigt, mit einer wichtigen Präzisierung

Andere Suchrichtung: statt `_parent_store = True` diesmal nach `_parent_name = ` gesucht (auch
ohne die Speicher-Optimierung). Ergebnis: nur 6 Treffer statt der 12 aus Dokument 7 — auf den
ersten Blick ein Widerspruch. Aufgelöst durch Nachschlagen im ORM-Kern
(`odoo/orm/models.py:435`): **`_parent_name` hat den Klassenstandard `'parent_id'`** — Modelle, die
einfach das konventionelle Feld `parent_id` nutzen (z. B. `hr.department`, `website.menu`), müssen
`_parent_name` gar nicht explizit setzen und tauchen deshalb in einer reinen `_parent_name`-Suche
nicht auf. `_parent_store` dagegen hat **keinen** Automatik-Standard (muss immer explizit `True`
gesetzt werden) — die Technik aus Dokument 7 bleibt damit die korrekte, vollständige Methode,
jetzt zusätzlich durch die Gegenprobe abgesichert statt nur einmalig angewendet.

---

## 2. Vier neue Funde aus dem `Many2one`-Feld und dem Datensatz-Auswahldialog

Beide Bausteine gehören zu den am häufigsten genutzten UI-Elementen in ganz Odoo (jedes
"Übergeordneter Kontakt"/"Verantwortlicher"-Feld), wurden in der bisherigen Reihe aber nie selbst
gelesen, nur über die serverseitige `name_search()` referenziert.

### 2.1 Barcode-Scan als Navigationsmodalität — bisher komplett unberücksichtigte Kategorie

`addons/web/static/src/views/fields/many2one/many2one.js:237-306` (`openBarcodeScanner()`,
`processScannedBarcode()`, vollständig gelesen): auf Mobilgeräten kann ein `Many2one`-Feld einen
gescannten Barcode/QR-Code direkt als `name_search(name=barcode, operator="ilike")` verwenden —
bei **genau einem** Treffer wird der Datensatz sofort ausgewählt, ohne weitere Nutzerinteraktion;
bei mehreren/keinem Treffer fällt es auf die normale Texteingabe zurück. **Eine bisher in der
gesamten Reihe nicht betrachtete Navigationskategorie:** von der physischen Welt (ein Aufkleber,
ein aufgedrucktes Etikett) direkt zu einem Datensatz springen. Für `int_filemanager` denkbar, falls
je Papierdokumente mit aufgedrucktem QR-Code auf ihre digitale Entsprechung verweisen sollen — bisher
in keinem der Feature-Kataloge dieser Session erwähnt.

### 2.2 Präzise Suchsteuerung in `Many2XAutocomplete` — konkrete Verfeinerung der bisherigen "Direkt-Sprung"-Idee

`addons/web/static/src/views/fields/relational_utils.js:357-420`, vollständig gelesen. Drei bisher
nicht dokumentierte, für eine künftige Schnellsuche direkt wichtige Bausteine:
- **`searchThreshold`** (Prop, Standard 0): erzwingt eine Mindestanzahl Zeichen, bevor überhaupt
  gesucht wird ("Start typing N characters"-Hinweis, Zeile 544-545) — verhindert genau das
  Kurzschluss-Risiko, das eine naive "gib alle 69k Ordner zurück"-Implementierung hätte.
- **`lastEmptySearch`-Gedächtnis** (Zeilen 360-368): wurde für einen bestimmten Text bereits ein
  leeres Ergebnis geliefert, wird eine Verfeinerung dieses Texts (tippt der Nutzer weiter) **ohne
  erneute Serveranfrage** sofort als leer beantwortet — spart Round-Trips beim "erfolglos
  weitertippen".
- **`web_name_search`** statt des einfacheren `name_search`: nimmt zusätzlich eine `specification`
  entgegen (kombiniert Namenssuche direkt mit einem `web_read`-artigen Feldabruf in einem
  Round-Trip) — die modernere, in Odoo 19 tatsächlich verwendete Variante, nicht die in den
  vorherigen Dokumenten zitierte einfachere `name_search`.
- Zusätzlich `KeepLast` (Racebedingungs-Schutz, `loadOptionsSource()`): verworfene/veraltete
  Zwischenergebnisse bei schnellem Weitertippen werden verworfen, nur die letzte Anfrage zählt.

**Einordnung:** ergänzt Fund 2 aus `int_filemanager_odoo_navigation_neue_perspektiven_2026-09-24.md`
um die konkreten Bausteine, die eine eigene Umsetzung tatsächlich robust machen würden — vorher war
dort nur die Grundidee (`complete_name`+`name_search`) skizziert, jetzt liegt die vollständige,
produktionsreife Referenzimplementierung vor.

### 2.3 `SelectCreateDialog` — ein dritter, bisher unbetrachteter UI-Ansatz ganz ohne neue Suchlogik

`addons/web/static/src/views/view_dialogs/select_create_dialog.js` (131 Zeilen, Kernteil
vollständig gelesen). Ein generischer, wiederverwendbarer Dialog, der eine **komplette native
Liste/Kanban-Ansicht** (`<View>`-Komponente, mit eigener Suchleiste, Filtern, Sortierung, Pager)
in ein Auswahl-Modal einbettet, mit `onSelected(resIds)`-Rückruf und `multiSelect`-Option.

**Bisher unbetrachteter dritter Weg für "Ordner auswählen"**, neben der Baum-Seitenleiste
(`FolderTree`) und einer eigenen Schnellsuche (Abschnitt 2.2): ein Dialog, der einfach
`int_filemanager`s **bereits vorhandene** `int_filemanager_list`/`int_filemanager_kanban`-Ansicht
in diesem nativen Rahmen wiederverwendet — **keine einzige Zeile neuer Suchlogik**, nur eine neue
Verwendungsart der ohnehin schon vorhandenen, bereits vollständig geprüften nativen Listenansicht
(siehe `int_filemanager_odoo_listenansicht_vollstaendig_2026-09-24.md`). Realistischer
Anwendungsfall: "Datei/Ordner in einen anderen Bereich verschieben" oder "Ziel für einen Link/eine
Verknüpfung wählen" über einen Dialog statt Drag & Drop.

---

## 3. Fazit dieser Prüfrunde

Die unabhängige Gegenprobe bestätigt die bisherige Kernaussage (kein natives Baum-Widget für diese
Größenordnung) vollständig, liefert aber vier konkrete, bisher fehlende Ergänzungen: eine ganz neue
Navigationskategorie (Barcode-Scan), drei entscheidende technische Feinheiten für eine robuste
Schnellsuche (`searchThreshold`, `lastEmptySearch`, `web_name_search`), und einen dritten,
aufwandsärmsten UI-Ansatz für "Ordner auswählen" (`SelectCreateDialog`, reine
Wiederverwendung der bereits vorhandenen Listenansicht). Die Gesamtkarte aus
`int_filemanager_odoo_such_navigationsmuster_gesamtkarte_2026-09-24.md` gilt um diese vier Punkte
ergänzt, nicht widerlegt.
