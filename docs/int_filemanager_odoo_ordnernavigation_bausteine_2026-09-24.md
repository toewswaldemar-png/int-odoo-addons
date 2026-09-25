# int_filemanager: Weitere native Odoo-Bausteine für hierarchische Navigation — breite Suche über den gesamten Kern

Stand 2026-09-24. Vierte, bewusst sehr breit gefächerte Prüfung (nach Bildverarbeitung,
Listenansicht, Suche/Breadcrumbs) — nicht auf `<searchpanel>` beschränkt, sondern gezielt nach
JEDEM Odoo-Baustein gesucht, der irgendwo im Kern hierarchische/rekursive Datensatz-Navigation
löst. Durchsucht: alle registrierten View-Typen (`registry.category("views")`, ~140 Einträge),
Volltextsuche nach "hierarchy"/`loadChildren`/`fetchChildren`/`expandNode` über den gesamten
Frontend-Code, alle Module mit "chart"/"tree" im Namen. Reine Recherche, nichts umgesetzt.

---

## 1. Haupt-Fund: `hierarchy_read()` — ein generischer, nativer, korrekt skalierender Baustein, bisher unbekannt

Die Registry-Suche fand einen bisher in keiner Session-Recherche aufgetauchten View-Typ:
**`web_hierarchy`** (eigenständiges Modul, `addons/web_hierarchy/`, 1876 Zeilen Code + Übersetzungen
in 49 Sprachen — kein kleines Nebenprojekt). Registriert als View-Typen `hierarchy` und
`hr_employee_hierarchy`. Laut eigenem Manifest: *"Odoo Web Hierarchy view — adds a new view [...]
to display an organization such as an Organization Chart for employees."*

**Die eigentlich wichtige Entdeckung liegt nicht in der View selbst, sondern in ihrer
Server-Methode**, die generisch auf `base` definiert ist — also auf **jedem** Odoo-Modell verfügbar,
nicht nur `hr.employee` (`addons/web_hierarchy/models/models.py:10-41`, vollständig gelesen):

```python
@api.model
def hierarchy_read(self, domain, specification, parent_field, child_field=None, order=None):
    records = self.search(domain, order=order)
    if not records:
        return []
    elif len(records) == 1:
        # genau EIN Treffer (z.B. ein einzelner Ordner): lade ihn + seinen Elternteil +
        # dessen weitere direkte Kinder (Geschwister) - EIN gezielter search()
        ...
    else:
        fetch_child_ids_for_all_records = True
        # MEHRERE Treffer (z.B. Wurzelebene): Kinder fuer GENAU DIESE Treffermenge holen
    children_ids_per_record_id = {
        record.id: child_ids
        for record, child_ids in self._read_group(
            [(parent_field, 'in', <nur die betroffenen IDs>)],
            (parent_field,), ('id:array_agg',), order=order
        )
    }
    ...
```

**Das ist strukturell etwas anderes als das native SearchPanel** (`search_panel_select_range()`,
siehe `int_filemanager_odoo_suche_navigation_vollstaendig_2026-09-24.md`): dort wird immer über
`search_domain` (typischerweise leer/global) aggregiert — hier läuft die Kinder-Ermittlung
IMMER als `_read_group([(parent_field, 'in', <konkrete, bereits bekannte ID-Menge>)], ...)`,
also grundsätzlich begrenzt auf genau die Datensätze, die die aufrufende Seite bereits kennt
(ein einzelner Knoten oder eine bereits geladene Menge) — kein Full-Table-`GROUP BY`, unabhängig
von der Gesamtgröße der Tabelle.

**Auf der Client-Seite genauso lazy wie `int_filemanager`s eigenes `FolderTree`:**
`hierarchy_model.js:showChildNodes()` (Zeile 257-273, gelesen) löst nur dann einen neuen RPC aus
(`this.model.fetchSubordinates(this)`), wenn die Kinder eines Knotens noch nicht geladen sind
(`this._nodes.length === 0`); sind sie es bereits, wird nur der Sichtbarkeits-Status umgeschaltet,
kein erneuter Request. Exakt dasselbe Prinzip wie `folder_tree.js:ensureLoaded()`.

**Direkt relevant für `int_filemanager`:** `models/filemanager_file.py:100-102` zeigt, dass das
Modell bereits `_parent_store = True`/`parent_id`/`parent_path` nutzt — also genau die
Voraussetzung erfüllt, die `hierarchy_read()` als Parameter (`parent_field`) erwartet. Die
Methode ist nicht an `hr.employee` gebunden, sondern generisch auf `base` — technisch auch für
`int_filemanager.file` aufrufbar.

---

## 2. Warum das trotzdem kein direkter Ersatz für `FolderTree` ist

Zwei unabhängige, jeweils für sich ausreichende Gründe, geprüft:

1. **Die zugehörige Ansicht ist visuell ein Organigramm, keine Baumliste.** `hierarchy_renderer.xml`
   (vollständig gelesen) rendert Knoten als 250px breite Karten in umbrechenden Zeilen
   (`row-cols-lg-5`, `hierarchy_card.scss:11: width: 250px`) mit Verbindungslinien
   (`o_hierarchy_line_left/right`) — gebaut für "Vorgesetzter oben, Team darunter", nicht für eine
   kompakte, tief verschachtelte Explorer-Seitenleiste mit potenziell hunderten Geschwistern pro
   Ebene. Die fertige View-Komponente (`HierarchyRenderer`/`HierarchyCard`) ist damit für den
   Anwendungsfall ungeeignet, unabhängig von der Datenladung dahinter.
2. **Navigationsmodell passt nicht 1:1.** `hierarchy_read()` arbeitet mit Datensatz-IDs
   (`parent_field`, `records.ids`), `int_filemanager`s gesamte Navigation (URL-Persistenz,
   Breadcrumbs, `_getIntFilemanagerFolderDomain()`) läuft bewusst über literale Pfad-Strings, nicht
   ID-Ketten (siehe `int_filemanager_odoo_suche_navigation_vollstaendig_2026-09-24.md`, Abschnitt 2).
   Eine Umstellung wäre ein eigenständiger Umbau, keine Ein-Zeilen-Anpassung.

**Praktischer Wert des Fundes trotzdem:** `hierarchy_read()` ist der **dritte unabhängige Beleg**
(nach `FolderTree`s eigener Begründung und dem separat gefundenen `hr_org_chart`-Muster unten),
dass Odoo für "große, self-referentielle Hierarchie, nicht per SearchPanel lösbar" durchgängig
denselben Grundsatz verfolgt: **pro Knoten/Knotenmenge gezielt nachladen, nie global aggregieren.**
`int_filemanager`s `FolderTree` entspricht damit exakt dem nativen Muster, nur mit eigener
Pfad-String-Logik statt ID-Logik und eigenem, schlankerem Rendering statt der schweren
Organigramm-Karten.

---

## 3. Zweiter, unabhängig gefundener Beleg: `hr_org_chart` löst dasselbe Problem exakt wie `FolderTree`

`addons/hr_org_chart/` (separates Modul, nicht `web_hierarchy`) — der bekannte
"Vorgesetzter/Team"-Kartenausschnitt auf der Mitarbeiterkarte. Server-Controller
(`controllers/hr_org_chart.py:44-78`, vollständig gelesen):

```python
@http.route('/hr/get_org_chart', type='jsonrpc', auth='user')
def get_org_chart(self, employee_id, new_parent_id=None, **kw):
    ...
    children=[self._prepare_employee_data(child) for child in employee.child_ids if child != employee],
```

Liefert **ausschließlich**: den aktuellen Mitarbeiter, seine Vorgesetzten-Kette bis zu einer festen
Tiefe (`_managers_level = 5`), und seine **direkten** `child_ids` (keine Enkel-Ebene). Client-seitig
(`hr_org_chart.js:65-97`, vollständig gelesen) ruft `fetchEmployeeData()` bei jedem Klick auf einen
Mitarbeiter einen **neuen** RPC mit dessen ID auf — die Ansicht "rezentriert" sich, statt eine
wachsende Baumstruktur im Speicher zu halten.

**Das ist praktisch identisch zum Aufbau von `int_filemanager`s `/int_filemanager/tree`-Route**: ein
eigener, schmaler Controller statt eines generischen Odoo-Bausteins, weil weder SearchPanel noch
(hier zusätzlich bestätigt) `web_hierarchy`s fertige Kartenansicht für den jeweiligen
Anwendungsfall passt. Odoo selbst baut in diesem Fall also lieber einen 35-zeiligen eigenen
Controller, statt einen der beiden generischen Hierarchie-Bausteine zweckzuentfremden — dieselbe
Entscheidung, die `int_filemanager` am 2026-09-16 getroffen hat.

---

## 4. Sonst nichts Vergleichbares gefunden — Suchabdeckung

Zusätzlich geprüft, ohne weitere relevante Treffer:
- Alle ~140 registrierten View-Typen im Kern (`registry.category("views")`) durchsucht — außer
  `hierarchy`/`hr_employee_hierarchy` kein weiterer Typ mit erkennbarem Hierarchie-/Baum-Bezug.
- Volltextsuche nach `loadChildren`/`fetchChildren`/`expandNode`/`loadSubTree` über den gesamten
  Frontend-Code (`addons/web/static/src`, `addons/hr/static/src`) — keine weiteren Treffer außer
  den beiden oben behandelten.
- `nested_sortable.js` (`addons/web/static/src/core/utils/`) — **Korrektur (siehe
  `int_filemanager_odoo_navigation_weitere_bausteine_2026-09-24.md`, Abschnitt 1): diese Einordnung
  war falsch**, weil die Datei damals nur dem Namen nach eingeordnet, nicht gelesen wurde.
  `useNestedSortable()` unterstützt echte Verschachtelung (`nest: true`, `maxLevels`) und wird
  genau dafür in Websites Menü-Editor eingesetzt — ein generischer, potenziell für künftiges
  Drag&Drop direkt in `FolderTree` wiederverwendbarer Baustein, keine reine Flachlisten-Hilfe.
- Keine "Documents"-App im Community-Kern (bereits in früherer Session bestätigt, hier nicht erneut
  geprüft) — der einzige Ort, an dem eine echte Ordnerbaum-Navigation außerhalb von `hr_org_chart`/
  `web_hierarchy` zu erwarten gewesen wäre.

---

## 5. Fazit

Keine der beiden gefundenen nativen Hierarchie-Lösungen ist ohne größeren Umbau direkt einsetzbar
— `web_hierarchy`s Datenladung (`hierarchy_read()`) ist zwar genau richtig dimensioniert und sogar
strukturell einsatzbereit (Modell erfüllt bereits `_parent_store`/`parent_id`), scheitert aber am
Organigramm-Rendering und am ID- statt Pfad-Modell; `hr_org_chart` ist zu eng an `hr.employee`
gebunden, um wiederverwendet zu werden, bestätigt aber als zweites unabhängiges Beispiel dasselbe
Muster. **Der eigentliche Ertrag dieser Suche ist eine dritte, unabhängige Bestätigung, dass
`FolderTree`s Grundprinzip (gezieltes Nachladen pro Knoten statt globaler Aggregation) exakt dem
entspricht, was Odoo selbst tut, sobald ein Hierarchie-Problem die Größenordnung erreicht, für die
SearchPanel nicht gebaut ist** — kein Ersatzbaustein gefunden, aber die bestehende Entscheidung
ein drittes Mal bestätigt.
