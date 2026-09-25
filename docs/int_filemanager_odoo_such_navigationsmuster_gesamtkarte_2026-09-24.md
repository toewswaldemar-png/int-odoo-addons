# int_filemanager: Odoos Such- und Navigationsmuster — Gesamtkarte über alle Bereiche

Stand 2026-09-24. Achte und letzte Prüfung dieser Reihe — bewusst nicht mehr auf
"Ordnerbaum-Alternativen" verengt, sondern **alle** Such-/Navigationsmuster im Odoo-Kern
zusammengetragen, unabhängig davon, ob sie mit Hierarchien zu tun haben. Drei bisher nicht
geprüfte, vollständig gelesene Bereiche kommen neu hinzu (Pivot-Drill-down, Kanban-Nachladen,
Befehlspalette im Detail); der Rest fasst die bereits einzeln verifizierten Funde der Dokumente
1–7 zu einer Gesamtkarte zusammen. Reine Recherche, nichts umgesetzt.

---

## 1. Drei neu geprüfte Muster

### 1.1 Pivot-Tabelle: Drill-down als vierte Bestätigung des "gezielt nachladen"-Prinzips

`addons/web/static/src/views/pivot/pivot_model.js` (1604 Zeilen, die Navigations-Methoden
vollständig gelesen: `expandGroup`/`_expandGroup`/`closeGroup`, Zeilen 428-509, 818-843). Klickt
man eine Gruppe (z. B. "2026" in einer Zeitachse, oder eine Produktkategorie) zum Aufklappen an,
ruft `_expandGroup()` **ausschließlich für diese eine Gruppe** `_subdivideGroup()` auf — ein
`read_group`, dessen Domain auf genau den angeklickten Ast beschränkt ist, nicht auf die gesamte
Tabelle. Zuklappen (`closeGroup`) verwirft nur die zwischengespeicherten Werte dieses Astes, ohne
Server-Aufruf. **Vierte unabhängige Bestätigung** (nach `FolderTree`, `hierarchy_read()`,
`hr_org_chart`) desselben Grundsatzes — diesmal für **Datendimensionen** statt Datensätze:
Pivot navigiert man durch Gruppierungsebenen (Jahr → Monat → Tag, oder Ordner → Tag → Datei),
nicht durch Datensatz-Eltern-Kind-Beziehungen. Direkt relevant für eine mögliche
"Speicherplatz-Dashboard"-Drill-down-Ansicht (Ordner → Unterordner → Dateitypen), die dieses
native Muster kostenlos mitbringen würde, sobald `int_filemanager.file` eine Pivot-Ansicht bekäme.

### 1.2 Kanban: "Mehr laden" pro Spalte — drittes Paginierungs-Muster neben Pager und Infinite-Scroll

`kanban_renderer.js:491-493` (gelesen): `loadMore(group)` lädt exakt
`group.list.records.length + group.model.initialLimit` — eine feste Schrittweite mehr, nur für die
angeklickte Spalte/Gruppe, ein simpler Klick-Button ("20 mehr laden"), kein automatisches
Scroll-Nachladen. **Bereits heute automatisch Teil von `int_filemanager`s eigener nativer
Kanban-/Galerieansicht** (dieselbe Vererbungslogik wie beim nativen `ListView`/`ListRenderer`,
siehe `int_filemanager_odoo_listenansicht_vollstaendig_2026-09-24.md`) — keine neue Erkenntnis,
aber jetzt als drittes, eigenständiges Paginierungsmuster neben dem klassischen `Pager` (Abschnitt
2 unten) und Discuss' Endlos-Scroll (`int_filemanager_odoo_navigation_weitere_bausteine_2026-09-24.md`)
eingeordnet.

### 1.3 Befehlspalette im Detail: wichtige Präzisierung des bisherigen "Gehe-zu-Ordner"-Fundes

`command_palette.js` (388 Zeilen, vollständig gelesen). Bisher (siehe
`int_filemanager_odoo_navigation_neue_perspektiven_2026-09-24.md`, Fund 2) nur der
Registrierungs-Mechanismus (`command_provider`) geprüft — jetzt die tatsächliche Filterlogik:
**Für den Standard-Namensraum (`FUZZY_NAMESPACES = ["default"]`) filtert die Palette das, was ein
Provider zurückgibt, zusätzlich noch einmal selbst per `fuzzyLookup()` — rein client-seitig**
(Zeilen 206-207). Ein Provider, der naiv "alle 69k Ordner" zurückgibt, würde also genauso am
Full-Table-Problem scheitern wie das native SearchPanel. **Wichtige Präzisierung für eine künftige
Umsetzung:** der eigene Provider muss `options.searchValue` (wird ihm bei jedem Tastendruck
übergeben, Zeile 201/313-317) selbst nutzen, um serverseitig (z. B. über `name_search`/eine
`path ilike`-Abfrage) vorzufiltern, und nur die bereits kleine Treffermenge zurückgeben — dann
bleibt die anschließende client-seitige `fuzzyLookup()`-Nachfilterung unproblematisch, weil sie nur
noch auf einer schon kleinen Menge läuft. Ohne dieses Detail wäre der in Fund 2 skizzierte Ansatz
in der Praxis genauso am Umfang gescheitert wie SearchPanel.

---

## 2. Gesamtkarte: alle in dieser Recherchereihe (2026-09-24, 8 Dokumente) gefundenen Muster

| Muster | Fundstelle | Zweck | Skaliert für `int_filemanager`s Größenordnung? |
|---|---|---|---|
| `<searchpanel type="category">` | `search_panel.js`/`search_model.js` | Kategoriebaum als Filter | **Nein** (Full-Table-`GROUP BY`, verifiziert) |
| `_getDomain()`-Override | `native_search_model.js` | Eigene Domain-Klausel einhängen | native Erweiterung, bereits genutzt |
| Freitextsuche/Filter/`group_by` | `<search>`-Arch | Klassische Facettensuche | Ja, bereits vollständig genutzt |
| `env.config.breadcrumbs` | `breadcrumbs.js`/`action_service.js` | Aktions-Stack-Pfad | Ja, bereits vollständig genutzt (Desktop) |
| Native Mobil-Kollabierung | `breadcrumbs.xml` | Krumen ab 4. Ebene ins Dropdown | feste Heuristik, für `int_filemanager` durch eigene Breitenmessung ersetzt |
| `hierarchy_read()` | `web_hierarchy`-Modul | Organigramm-Datenladung | Ja (Datenladung), Nein (Rendering: Karten statt Liste) |
| `/hr/get_org_chart` | `hr_org_chart`-Modul | Vorgesetzter+Team, pro Klick neu | Ja (Muster), an `hr.employee` gebunden |
| `RPCCache` (IndexedDB) | `rpc_cache.js` | Persistentes Caching jeder RPC | Ja, in `FolderTree` bisher ungenutzt |
| `complete_name`+`name_search` | `product.category`/`stock.location`/`stock.package`/`analytic.plan` | Volltext über Gesamtpfad | **Ja** — 4 reale Vorbilder, `int_filemanager.file.path` erfüllt die Voraussetzung bereits |
| `command_provider` + `fuzzyLookup` | `command_palette.js` | Globale Tastatur-Schnellsuche | Ja, aber nur mit serverseitiger Vorfilterung im eigenen Provider (Abschnitt 1.3) |
| `useNestedSortable` | `nested_sortable.js` | Drag&Drop-Umsortierung/-Verschachtelung | Ja (Baustein), für kleine Bäume gebaut (Website-Menü) |
| Pivot-Drill-down | `pivot_model.js` | Gruppierungsebenen aufklappen | Ja — gezielt pro Ast, wie `FolderTree` |
| Kanban "Mehr laden" | `kanban_renderer.js` | Feste Schrittweite pro Spalte | Ja, bereits automatisch genutzt |
| Discuss Endlos-Scroll | `mail`s `hooks.js` | Alternative zu Paging | Ja (Baustein), bisher ungenutzt |
| Nativer `Pager` | `pager.js` | Seiten-/Bereichsnavigation | Ja, bereits automatisch genutzt |
| `router.js`/`addLockedKey`/`hideKeyFromUrl` | `router.js` | URL-Zustand über Reload hinweg | Ja, teilweise genutzt |

---

## 2a. Nachtrag (gleicher Tag): die im Prompt selbst verlangte Einzelprüfung aller View-Typen abgeschlossen

Die Gesamtkarte in Abschnitt 2 deckte bis hierhin List/Kanban/Pivot/Hierarchy ab. Calendar und
Graph fehlten noch, Gantt/Map waren ungeprüft. Jetzt nachgeholt, ganze Dateien gelesen:

**Calendar-Ansicht** (`calendar_controller.js:412-439`, vollständig gelesen): `setDate(move)`
verschiebt einen Anker-Zeitpunkt um genau eine Skalen-Einheit (Tag/Woche/Monat/Jahr,
`this.model.date.plus/minus({[scale+'s']: 1})`) und ruft `this.model.load({ date })` — dieselbe
Grund-Idee wie überall sonst gefunden: **nur das für das aktuell sichtbare Zeitfenster nötige
nachladen**, kein globaler Reload. Fünfte unabhängige Bestätigung desselben Prinzips (nach
`FolderTree`, `hierarchy_read`, `hr_org_chart`, Pivot-Drill-down), diesmal für ein Zeitfenster
statt eine Baum-/Gruppierungsebene. Direkt relevant, falls `int_filemanager` je eine
"Dateien nach Änderungsdatum durchblättern"-Kalenderansicht bekäme — bräuchte keinen eigenen
Fensterungsmechanismus, die native Calendar-View brächte ihn mit.

**Graph-Ansicht** (`graph_controller.js`, vollständig gelesen, 68 Zeilen): **hat keinerlei eigene
Navigations-/Drill-down-Logik.** Ausschließlich Diagrammtyp/Messgröße/Gruppierung als Konfiguration
(`getContext()` liefert nur `graph_measure`/`graph_mode`/`graph_groupbys` etc.) — kein
Klick-zum-Aufklappen, kein Sprung zu Datensätzen. Bestätigte Fehlanzeige, keine Lücke übersehen.

**Gantt- und Map-Ansicht: in dieser Community-Instanz nicht vorhanden.** `addons/web_gantt` und
`addons/web_map` existieren nicht im geklonten Repository (geprüft, beide Verzeichnisse fehlen) —
beide sind reine Odoo-Enterprise-Module, hier grundsätzlich nicht prüfbar. Festgehalten als
bestätigte Lücke in der Prüfbarkeit, nicht als "nichts gefunden".

**Ergebnis:** keine der vier nachgeprüften Ansichten liefert einen bisher unbekannten Baustein —
Calendar bestätigt das bereits mehrfach gefundene Fenster-/Ast-Prinzip ein weiteres Mal, Graph hat
nachweislich nichts beizutragen, Gantt/Map sind schlicht nicht Teil der Community-Codebasis. Die
Prüfung aller View-Typen aus der Arbeitsregel ist damit vollständig abgeschlossen.

---

## 3. Fazit der gesamten Reihe

Drei Muster sind **bereits vollständig und korrekt genutzt** (Freitextsuche/Filter, Breadcrumbs
Desktop, Pager/Kanban-Nachladen). Zwei sind **bewusst und richtig nicht genutzt**, weil sie an der
Größenordnung scheitern (SearchPanel-Kategorie, `web_hierarchy`-Rendering). Drei sind
**identifizierte, aber ungenutzte Verbesserungsmöglichkeiten** mit jeweils konkretem, durch
mehrere native Vorbilder abgesichertem Ansatz: `RPCCache` für `FolderTree`-Persistenz,
`complete_name`/`name_search` für eine Direkt-Sprung-Suche (jetzt vierfach statt zweifach
bestätigt), `useNestedSortable` für ein mögliches künftiges Drag&Drop im Baum. Ein Muster
(Befehlspalette) ist jetzt so weit präzisiert, dass eine spätere Umsetzung nicht in dieselbe
Skalierungsfalle wie SearchPanel laufen würde. Damit ist die Landschaft der Such-/
Navigationsmuster im Odoo-Kern, soweit mit vertretbarem Aufwand erschöpfend prüfbar, vollständig
kartiert.
