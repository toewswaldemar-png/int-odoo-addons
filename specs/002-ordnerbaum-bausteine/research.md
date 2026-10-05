# Research: Aus welchen Teilen ein Ordnerbaum gebaut werden kann

Stand 2026-10-04. Suchraster nach Constitution I: (1) Core-Grep im Image
`odoo:19.0-hm-test` auf Tower, (2) vergleichbare Odoo-Module, (3) vorhandene
Bibliotheken, (4) Odoo-Defaults, (5) Messung. Pfade unter
`/usr/lib/python3/dist-packages/odoo/addons/` gekürzt auf `web/…` usw.

## Vergleichsbeispiele im Core (Community)

| Beispiel                | Fundstelle                                                                                                                                                | Was es zeigt                                                                                                                                                                                  | Als Baustein wiederverwendbar?                                                      |
| ----------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------- |
| Export-Dialog: Feldbaum | `web/static/src/views/view_dialogs/export_data_dialog.js/.xml` (`ExportDataItem`)                                                                         | Echter **Lazy-Baum**: Knoten mit `role="treeitem"`, Chevron `oi-chevron-right/down`, Unterfelder werden beim Aufklappen nachgeladen (`loadFields`) und zwischengespeichert (`expandedFields`) | Nein: die Klasse ist nicht exportiert und an den Dialog gebunden; **als Muster** ja |
| Suchpanel, Kategorie    | `web/static/src/search/search_panel/search_panel.js`, `search_model.js` (`_fetchCategories`), Server `web/models/models.py` (`search_panel_select_range`) | Hierarchische Seitenleiste mit Zählern, native Auswahl über Suchmodell                                                                                                                        | Ja, aber lädt **alles in einem Aufruf** (siehe Messung)                             |
| Hierarchie-Ansicht      | Modul `web_hierarchy` (Community, LGPL-3, hängt nur von `web` ab); `hierarchy_read` in `web_hierarchy/models/models.py`                                   | Ansichtstyp `hierarchy` mit Karten, Aufklappen, Ziehen zum Umhängen (`hierarchy_node_draggable.js`); Organigramm in `hr_org_chart`                                                            | Als Ansicht, nicht als Seitenleiste; Karten-Layout                                  |
| Menü-Editor             | `website/static/src/components/dialog/edit_menu.js`                                                                                                       | `useNestedSortable` mit `nest: true`, `maxLevels: 2`                                                                                                                                          | Als Muster fürs Umsortieren und Einrücken in einer fertig gezeichneten Liste        |
| Discuss-Seitenleiste    | `mail/static/src/core/public_web/discuss_sidebar*.js/.xml`                                                                                                | einklappbare Kategorien, Zähler                                                                                                                                                               | Als Muster für Kopfzeilen mit Auf-/Zuklappen, kein Baum                             |

## Die Teilstücke

Spalten: **Kandidaten** (Fundstelle im Core), **Heute** (`v2/…`), **Urteil**. Urteile:
✔ nativ genutzt · ◐ nativ möglich, nicht genutzt · ◆ Eigenbau begründet · ◇ Eigenbau
offen.

| Nr. | Teilstück                                           | Kandidaten im Core                                                                                                                                                                                                                                                            | Heute im Baum                                                                                                                                                                                             | Urteil                                                                                       |
| --- | --------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------- |
| 1   | **Hierarchie speichern**                            | `_parent_store` + `parent_path`, Operatoren `child_of`/`parent_of` (`orm/models.py`: `_parent_store_create`, `_parent_store_compute`)                                                                                                                                         | `_parent_store = True`, `parent_path` mit Index, `parent_id`                                                                                                                                              | ✔                                                                                           |
| 2   | **Eine Ebene laden**                                | (a) `search_panel_select_range` (alles in einem Aufruf); (b) `hierarchy_read(domain, specification, parent_field)` (liefert Datensatz, Eltern, Kinder mit `__child_ids__`, ohne Vorfahrenkette); (c) `web_read_group` mit Entfalten; (d) allgemeines `search` + `_read_group` | eigene Methode `tree_children`: `search` auf eine Ebene + ein `_read_group` für "hat Unterordner" (nur ORM-Aufrufe, Rechte greifen)                                                                       | ◆ (siehe Messung)                                                                            |
| 3   | **Pfad zum Knoten** (Sprung in die Tiefe)           | `parent_path` (Spalte), `child_of`                                                                                                                                                                                                                                            | `breadcrumb`: Pfad aus `parent_path`, nur lesbare Vorfahren                                                                                                                                               | ◆                                                                                            |
| 4   | **Aufruf und Zwischenspeicher im Browser**          | `orm`-Dienst; `orm.cache({...})` und `RPCCache` (RAM oder IndexedDB, `core/network/rpc_cache.js`, Invalidierung nach Tabelle); `rpcBus CLEAR-CACHES`                                                                                                                          | `orm.call` ohne Cache, eigener Zwischenspeicher `nodes` mit `loaded`/`invalidate`                                                                                                                         | ◐ (bei 6 bis 9 ms je Ebene wenig Gewinn)                                                     |
| 5   | **Zustand halten**                                  | Owl `useState`, `reactive`                                                                                                                                                                                                                                                    | `useState`, rekursive Knoten mit `expanded`/`loaded`/`loading`                                                                                                                                            | ✔                                                                                           |
| 6   | **Zeichnen**                                        | rekursives Template (`t-call`); Muster Export-Baum; `Transition` (`core/transition.js`); **kein** fertiger Baum-Baustein                                                                                                                                                      | rekursives Template `FolderTreeNode`, Einrückung `depth * 16 px`, Kopfzeile mit Klick                                                                                                                     | ◆ (kein Baustein vorhanden)                                                                  |
| 7   | **Lange Ebenen zeichnen**                           | `useVirtualGrid` (`core/virtual_grid_hook.js`; in Community-Addons von keinem anderen Code benutzt)                                                                                                                                                                           | alle Kinder einer Ebene werden gezeichnet                                                                                                                                                                 | ◇ (nicht gemessen bei 5.000 Kindern)                                                         |
| 8   | **Auswahl und aktueller Ordner**                    | Suchmodell (`env.searchModel`), `router`, `action`-Dienst, Brotkrumen                                                                                                                                                                                                         | `activeId` aus `env.searchModel.folderId`, `onSelectFolder` ruft die Aktion                                                                                                                               | ✔                                                                                           |
| 9   | **Tastatur**                                        | `useNavigation` (`core/navigation/navigation.js`: Pfeile, Home/End, Fokus, `virtualFocus`), `useHotkey`; ARIA-Muster im Export-Baum                                                                                                                                           | **fehlt im Baum** (`useNavigation` nur für die Liste); Knoten haben weder `tabindex` noch `aria-expanded` noch `aria-level`; `role="tree"` steht am Behälter, `role="treeitem"` nur am Papierkorb-Eintrag | ◇ (Lücke)                                                                                    |
| 10  | **Breite ziehen**                                   | `ResizablePanel` (`core/resizable_panel`)                                                                                                                                                                                                                                     | `ResizablePanel`, Breite in `browser.localStorage`                                                                                                                                                        | ✔                                                                                           |
| 11  | **Handy**                                           | `bottom_sheet`-Dienst und `usePopover(..., {useBottomSheet})` (`core/bottom_sheet`, setzt `history.pushState` und hört auf `popstate`); `env.isSmall`                                                                                                                         | eigenes Overlay (`mobileTreeState`), `env.isSmall` für die Umschaltung; kein `popstate`                                                                                                                   | ◐                                                                                            |
| 12  | **Ordner verschieben per Ziehen**                   | `useDraggable`/`useSortable` (`core/utils/`), `useNestedSortable` (umsortieren und einrücken in fertiger Liste), Muster `web_hierarchy/hierarchy_node_draggable.js`                                                                                                           | rohes HTML5-Drag-and-drop (`dragover`/`drop` auf `window`), Zielknoten über `data-int-filemanager-tree-id`                                                                                                | ◇ (Eignung der Core-Hooks fürs Ablegen auf einen zugeklappten Lazy-Knoten ist nicht geprüft) |
| 13  | **Dateien aus dem Rechner auf einen Ordner ziehen** | `useDropzone`/`Dropzone` (`core/dropzone`, benutzt von `mail`, `base_import`, `website`)                                                                                                                                                                                      | eigenes Overlay, Handler auf `window` (`controller_uploads.js`)                                                                                                                                           | ◇ (Frühere Notiz: fast wortgleich nachgebaut)                                                |
| 14  | **Kontextmenü, Aktionen**                           | `usePopover`/Popover-Dienst, `Dropdown`, `DropdownItem`, `useNavigation`                                                                                                                                                                                                      | `context_menu.js`: Popover-Dienst, `DropdownItem`, `useNavigation`                                                                                                                                        | ✔                                                                                           |
| 15  | **Zähler, Markierungen**                            | `badge`, `tags_list`, Zähler im Suchpanel (`enable_counters`, langsam bei vielen Werten)                                                                                                                                                                                      | keine Zähler im Baum, nur "hat Unterordner"                                                                                                                                                               | ◆ (bewusst)                                                                                  |
| 16  | **Aktualisieren bei Änderungen**                    | `bus_service`, `useBus`, `rpcBus`                                                                                                                                                                                                                                             | eigener Aufruf `refreshTree`/`invalidate` nach jeder Änderung des Nutzers; Bus für Vorschauen                                                                                                             | ◐ (Änderungen anderer Nutzer erscheinen erst beim nächsten Öffnen)                           |
| 17  | **Rechte**                                          | `ir.rule`, ACL; ORM-Aufrufe wenden sie an                                                                                                                                                                                                                                     | `search` und `_read_group` mit den Regeln des Nutzers, Vorfahren ohne Leserecht fehlen im Pfad                                                                                                            | ✔                                                                                           |

Querschnitt: Tooltips `data-tooltip` (✔ genutzt), Übersetzung `_t` (✔), Icons
FontAwesome (`fa-caret-*`, `fa-folder`; die Regel nennt FontAwesome als Standard und
`oi` für Lücken, der Baum ist konform; der Export-Baum nutzt `oi-chevron-*`),
Doppelbaum: `native_ui/folder_tree.js` (Template `int_filemanager.FolderTree`) wird über
die Glob-Zeile `static/src/int_filemanager/**/*` im Manifest mitgeladen; ob er noch
benutzt wird, ist nicht geprüft (FR-009).

## Messung zu Teilstück 2 (Constitution III)

Wegwerf-Datenbank auf Tower, Kopie von `fmv2_ui` plus 70.440 erzeugte Ordner (4 Ebenen:
40 × 40 × 43), insgesamt **70.446 Ordner**. Aufruf als normaler Nutzer `tester`
(Dateimanager-Gruppe, Rechteregeln aktiv), Odoo-Registry im Wegwerf-Container, kalter
Cache je Lauf (`invalidate_all`), gemessen ist die Serverseite.

| Aufruf                                                                            | Zeit                   | Zeilen | Datenmenge   |
| --------------------------------------------------------------------------------- | ---------------------- | ------ | ------------ |
| `tree_children`, oberste Ebene                                                    | 9 bis 11 ms            | 1      | unter 1 KB   |
| `tree_children`, Ebene mit 43 Unterordnern                                        | 6 bis 8 ms             | 43     | 2 KB         |
| `tree_children`, Ebene mit 40 Unterordnern                                        | 7 bis 8 ms             | 40     | 2 KB         |
| `breadcrumb`, Ordner in Ebene 4                                                   | 6 bis 7 ms             | 4      | unter 1 KB   |
| `search_panel_select_range(parent_id, expand=True, hierarchize=True)`, nur Ordner | **1.750 bis 1.782 ms** | 70.446 | **3.851 KB** |
| dasselbe mit Zählern                                                              | 1.926 bis 1.927 ms     | 70.446 | 4.816 KB     |
| Standard (`expand=False`)                                                         | 221 bis 227 ms         | 1.645  | 85 KB        |

Lesart: Das Suchpanel liefert mit `expand=False` nur Ordner, in denen schon etwas liegt
(1.645 von 70.446), leere Ordner fehlen; damit ist es als Ordnerbaum nicht gleichwertig.
Mit `expand=True` sind es alle, dafür fast 2 Sekunden und knapp 4 MB. Das passt zur
Begründung im Code ("mehrere Sekunden"). Nicht gemessen: Übertragung und Aufbau im
Browser; eine einzelne Ebene mit tausenden Unterordnern; `hierarchy_read` (nicht
getestet, liefert aber nur die Nachbarschaft eines Datensatzes und bräuchte je Ebene
einen Aufruf mit zusätzlichen Vorfahren).

## Auswertung

- **Nativ und genutzt (6):** Teilstücke 1, 5, 8, 10, 14, 17.
- **Eigenbau begründet (4):** 2, 3, 6, 15.
- **Nativ möglich, nicht genutzt (3):** 4 (Cache, wenig Nutzen), 11 (Handy), 16 (Bus).
- **Eigenbau offen oder Lücke (4):** 7 (breite Ebenen), 9 (Tastatur, ARIA), 12 (Ziehen),
  13 (Hochladen per Ziehen).
- Es gibt **keinen fertigen Baum-Baustein** im Community-Core; der nächste ist der
  Lazy-Baum im Export-Dialog (als Muster) und die Suchpanel-Kategorie (als Baustein,
  aber nicht Lazy).

## Decisions (für den Plan)

- Teilstücke 2, 3 und 6 bleiben Eigenbau, Begründung und Messung stehen hier; im Code
  genügt ein Verweis auf diese Datei.
- Teilstück 9 (Tastatur, ARIA) ist eine Lücke mit Core-Bausteinen (`useNavigation`,
  ARIA-Muster des Export-Baums): Entscheidung des Nutzers nötig, welcher Weg gewählt
  wird (FR-003).
- Teilstück 11 (Handy): Core-Baustein `bottom_sheet` ist vorhanden; Entscheidung nötig
  (FR-007).
- Teilstücke 12 und 13: Eignung der Core-Hooks fürs Ablegen auf Baumknoten und
  `useDropzone` erst nach einem Versuch beurteilbar; Entscheidung nötig (FR-008).
- Teilstück 7: Messung bei 5.000 Unterordnern vor jeder Entscheidung.
- Alter Ordnerbaum: Aufräumen oder Beleg der Nutzung (FR-009).

**Nicht belegt in dieser Prüfung:** `hr_org_chart` und `web_hierarchy` im Betrieb (nur
Quelltext gelesen, nicht gestartet); Ersetzung von `tree_children` durch
`hierarchy_read` (nicht erprobt); Verhalten am Handy und mit Hilfsprogrammen (kein
Gerätetest).

---

# Messreihe 2: alle nativen Varianten (2026-10-04)

Aufbau wie oben: Wegwerf-Datenbank (Kopie `fmv2_ui` plus 70.440 Ordner, **70.446
Ordner**, 4 Ebenen: 1 × 40 × 40 × 43), Nutzer `tester` mit Regeln, kalter Cache je Lauf,
kleinster und größter von 2 bis 3 Läufen. Zusätzlich im Wegwerf-Bestand installiert:
`web_hierarchy` und ein Messmodul mit gespeichertem rekursivem `complete_name` (Muster
`product.category`). Alles nach der Messung gelöscht. **Gemessen ist die Serverseite
plus ein Nachbau des Client-Aufbaus in Node; die Darstellung im Browser ist nicht
gemessen** (Browser-Tests macht der Nutzer selbst).

Hinweis zu den Ebenen: Der Ordner `a1` hat 40 Unterordner (Teilbaum 1.761), `b9` hat 43.

| Nr. | Variante                                                                 | Zeit                                                           | Zeilen                                          | Daten        |
| --- | ------------------------------------------------------------------------ | -------------------------------------------------------------- | ----------------------------------------------- | ------------ |
| A1  | **Eigener Baum**, `tree_children(a1)`                                    | 8 bis 10 ms                                                    | 40                                              | 2 KB         |
| A2  | Eigener Baum, `breadcrumb(tief)`                                         | 7 bis 9 ms                                                     | 4                                               | unter 1 KB   |
| B1  | Suchpanel-Kategorie, alle Ordner (`expand=True`)                         | **1.751 bis 1.769 ms**                                         | 70.446                                          | **3.851 KB** |
| B2  | Suchpanel, Standard (`expand=False`): nur Ordner mit Inhalt              | 217 bis 232 ms                                                 | 1.645                                           | 85 KB        |
| B3  | Suchpanel, Teilbaum `child_of a1` **ohne** Vorfahren                     | 54 ms                                                          | **0**                                           | 0 KB         |
| B3b | Suchpanel, Teilbaum `child_of a1` **mit** Vorfahren (`parent_of`)        | 46 ms                                                          | 1.762                                           | 97 KB        |
| B4  | Suchpanel, nur Ebene 0 und 1                                             | 42 bis 44 ms                                                   | 44                                              | 85 KB        |
| B5  | Suchpanel mit `limit=5000`                                               | 107 bis 255 ms                                                 | Fehlermeldung "Zu viele Elemente zum Anzeigen." | 0 KB         |
| B6  | Suchpanel flach (`hierarchize=False`)                                    | 824 bis 847 ms                                                 | 70.446                                          | 2.589 KB     |
| C1  | `hierarchy_read`, ein Datensatz (`a1`): Datensatz, Eltern, Kinder        | 14 bis 17 ms                                                   | 89                                              | 29 KB        |
| C2  | `hierarchy_read`, Ebene (`parent_id = a1`)                               | 8 bis 9 ms                                                     | 40                                              | 16 KB        |
| C3  | `hierarchy_read`, Ebene 1 unter der Wurzel                               | 9 ms                                                           | 48                                              | 14 KB        |
| C4  | `hierarchy_read`, alle Ordner (Gegenprobe)                               | 1.009 ms                                                       | 70.446                                          | 7.020 KB     |
| D1  | `web_read_group` nach `parent_id`, limit 80                              | 96 bis 100 ms                                                  | 80                                              | 7 KB         |
| D2  | `_read_group` nach `parent_id`, alle                                     | 21 ms                                                          | 1.643 Gruppen                                   | 18 KB        |
| D3  | `web_search_read`, eine Ebene                                            | 7 bis 8 ms                                                     | 40                                              | 4 KB         |
| D4  | `search_read`, eine Ebene, nur Name                                      | 2 ms                                                           | 40                                              | 1 KB         |
| E1  | `web_name_search('c7')`, limit 8                                         | 3 bis 4 ms                                                     | 8                                               | 1 KB         |
| E2  | Suche in gespeichertem `complete_name` (`ilike`, limit 8)                | 54 bis 55 ms                                                   | 1                                               | unter 1 KB   |
| E3  | Suche `name = 'c7'` (1.600 Treffer)                                      | 13 ms                                                          | 1.600                                           | 11 KB        |
| F1  | `search_count` `child_of` (Teilbaum 1.761)                               | 12 bis 13 ms                                                   | –                                               | –            |
| F2  | `search_count` `child_of` Wurzel (70.446)                                | 15 bis 16 ms                                                   | –                                               | –            |
| F3  | `search_count` `parent_path =like 'Pfad%'`                               | 11 bis 12 ms                                                   | –                                               | –            |
| F4  | Zähler je Unterordner, **eine** Abfrage (`split_part`), `a1`             | 9 bis 10 ms                                                    | 40 Gruppen                                      | 1 KB         |
| F5  | dasselbe für die Wurzel (70.446 Zeilen)                                  | 32 bis 33 ms                                                   | 40 Gruppen                                      | 1 KB         |
| G1  | `complete_name` neu berechnen: **Umbenennen `a1`** (1.761 Knoten)        | 317 ms                                                         | –                                               | –            |
| G2  | `complete_name` neu berechnen: **Umbenennen der Wurzel** (70.446 Knoten) | **11.584 ms**                                                  | –                                               | –            |
| H   | Client-Nachbau in Node (Kopie von `_createCategoryTree`), B1-Daten       | Lesen 5 ms, `JSON.parse` 25 ms, Baum aufbauen **49 bis 90 ms** | 70.446                                          | 3.851 KB     |

Weitere Befunde aus dem Quelltext (Core, Odoo 19):

- Das Suchpanel holt die Kategorien mit `orm.cache({type: "disk", update: "always"})`
  (`search_model.js`, `_fetchCategories`): beim zweiten Öffnen zeigt der Browser die
  Werte sofort aus dem Speicher und aktualisiert im Hintergrund. Die Serverarbeit von B1
  fällt dabei **bei jedem Seitenaufruf** erneut an.
- Das Panel zeichnet Unterknoten nur, wenn der Elternknoten aufgeklappt ist
  (`search_panel.xml`); die Darstellungskosten hängen an den offenen Zweigen.
- `SearchPanel` hat **keine** Tastaturbedienung und keine ARIA-Rollen (kein `role`,
  `aria-`, `tabindex`, kein `useNavigation`, kein `useHotkey`).
- `SearchPanel` hat einen eigenen Handy-Modus (`web.SearchPanel.Small`, Auswahl über
  `Dropdown`) und merkt, ob die Seitenleiste eingeklappt ist (`localStorage`).
- `SearchPanel` kennt kein Ziehen zum Verschieben.
- `web_hierarchy` lädt Ebene für Ebene (`hierarchy_read`, Kinder-IDs über
  `formattedReadGroup`), kann Karten per Ziehen umhängen (`draggable="1"`), ist am Handy
  ohne Ziehen.
- Reihenfolge der Panel-Werte: die des Modells (`_order = parent_path`, also nach
  Anlage), nicht alphabetisch.

## Was die Zahlen sagen

1. **Das Laden einer Ebene braucht keinen Eigenbau.** `hierarchy_read` (C2, 8 bis 9 ms),
   `web_search_read` (D3, 7 bis 8 ms) und `search_read` (D4, 2 ms) sind so schnell wie
   `tree_children`. `tree_children` bleibt eine dünne Hülle (ein `search` und ein
   `_read_group`, 8 ms, 2 KB); der Umstieg brächte keine Zeitersparnis, bei
   `hierarchy_read` wären die Daten 8-mal größer (16 KB gegen 2 KB). Ersetzbar, aber
   nicht besser.
2. **Der ganze Baum in einem Aufruf (Suchpanel) skaliert mit der Ordnerzahl** und kostet
   bei 70.446 Ordnern **1,75 s Serverzeit und 3,9 MB bei jedem Seitenaufruf**, dazu 50
   bis 90 ms Aufbau im Browser. Auf einen Ordner umgerechnet sind das ca. 0,025 ms
   (Hochrechnung, nicht gemessen: bei 10.000 Ordnern ca. 250 ms, bei 2.000 ca. 50 ms).
   Der Browser-Zwischenspeicher macht nur die Anzeige schneller, nicht die Serverlast.
3. **Das Suchpanel ist als Baum brauchbar, wenn man es begrenzt:** Teilbaum mit
   Vorfahren (B3b, 46 ms, 1.762 Werte) oder nur die oberen Ebenen (B4, 43 ms). Das
   Nachladen beim Aufklappen kann das Panel nicht.
4. **Zähler:** im Panel +10 % Zeit (B1 mit Zählern: 1.926 ms); selbst gebaut als
   **eine** Abfrage 9 bis 33 ms für alle Unterordner einer Ebene (F4, F5) statt 40
   Einzelzählungen mit `child_of` (je 12 ms, zusammen ca. 480 ms).
5. **Direktsprung ist nativ fertig:** `web_name_search` in 3 bis 4 ms.
6. **Ein gespeicherter Pfadname (`complete_name`) macht das Umbenennen teuer:** große
   Teilbäume 11,6 s (G2). Der Pfad lässt sich auch ohne Speicherung liefern
   (`breadcrumb` aus `parent_path`, 7 bis 9 ms).

## Die Frage: Ist Eigenbau nötig?

- **Baum als Seitenleiste mit beliebig großer Ordnerzahl (Ziel 70.000+, Nachladen beim
  Aufklappen):** **Ja, Eigenbau bleibt nötig.** Kein nativer Baustein lädt ebenenweise;
  das Suchpanel braucht 1,75 s und 3,9 MB je Seitenaufruf, die Hierarchie-Ansicht ist
  ein Kartenlayout, keine Seitenleiste.
- **Baum bei kleiner Ablage (unter ca. 5.000 Ordnern) oder auf einen Teilbaum
  begrenzt:** **Nein.** Das native Suchpanel genügt (hochgerechnet unter 130 ms Server),
  mit Handy-Modus und Auswahl über das Suchmodell.
- **Server-Teil (`tree_children`, `breadcrumb`):** nicht zwingend Eigenbau, aber auch
  nicht schlechter als die nativen Aufrufe; kein Grund zum Umbau.
- **Teilstücke ohne Baum-Baustein (Tastatur, ARIA, Ziehen, Hochladen per Ziehen):**
  weder das Suchpanel noch `web_hierarchy` liefern Tastatur oder ARIA; hier kommt man
  mit Core-Hooks (`useNavigation`, `useDraggable`, `useDropzone`) weiter, nicht mit
  einem fertigen Baum.

## Einschränkungen nativer Lösungen und wie man sie mit Odoo-Mitteln löst

| Einschränkung                                | Native Lösung                                                                                                                                                                                    | Beleg / Messung                                                                                                                                  |
| -------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------ | ------------ |
| Panel lädt alles auf einmal                  | Teilbaum begrenzen mit `comodel_domain`; `limit` als Schutz                                                                                                                                      | B3b 46 ms, B4 43 ms, B5 liefert Fehlermeldung statt Daten                                                                                        |
| Teilbaum-Filter liefert **0 Werte**          | Vorfahren mitnehmen: `["                                                                                                                                                                         | ", ("id","child_of",X), ("id","parent_of",X)]`(das Panel verwirft sonst Knoten, deren Eltern fehlen,`\_search_panel_sanitized_parent_hierarchy`) | B3 gegen B3b |
| Leere Ordner fehlen im Standard              | `expand=True` mit `comodel_domain` nur Ordner                                                                                                                                                    | B2 gegen B1 (Preis: Zeit und Daten)                                                                                                              |
| Reihenfolge nach Anlage statt alphabetisch   | Sortierung im Client oder `search_panel_select_range` im eigenen Modell überschreiben (`@api.model`, Odoo-Erweiterungspunkt)                                                                     | `_order = parent_path`                                                                                                                           |
| Serverarbeit bei jedem Seitenaufruf          | Ergebnis kurz auf dem Server zwischenspeichern (`@tools.ormcache` mit Schlüssel Nutzer und Ordnerstand) oder Panel nur für begrenzten Teilbaum                                                   | ungemessen                                                                                                                                       |
| Kein Nachladen beim Aufklappen               | `search_panel_select_range` überschreiben (eine Ebene) **plus** Client-Patch am Aufklappen (`patch`, im Regelwerk erlaubt, wenn kein Registry-Punkt reicht); das ist dann praktisch der Eigenbau | Quelltext                                                                                                                                        |
| Tastatur, ARIA fehlen                        | `useNavigation` und das ARIA-Muster des Export-Baums auf das Panel-Template anwenden (Patch am Template)                                                                                         | Panel hat keine Treffer                                                                                                                          |
| Handy                                        | nativer `Small`-Modus des Panels, sonst `bottom_sheet`                                                                                                                                           | `search_panel.xml`                                                                                                                               |
| Gespeicherter Pfadname teuer beim Umbenennen | `complete_name` nicht speichern; Pfad aus `parent_path` und Namen zusammensetzen (`breadcrumb`)                                                                                                  | G2 11,6 s gegen A2 7 bis 9 ms                                                                                                                    |
| Zähler je Unterordner                        | eine gruppierte Abfrage mit `odoo.tools.SQL` und `split_part(parent_path, '/', n)`                                                                                                               | F4 9 bis 10 ms, F5 32 bis 33 ms                                                                                                                  |
| Rechte                                       | in allen Varianten über das ORM (`search`, `search_read`, `web_read` wenden `ir.rule` an; das Panel nutzt `Comodel.search_read`); nichts zu bauen                                                | Quelltext `models.py`                                                                                                                            |
| Verschieben per Ziehen                       | `useDraggable`; Muster `hierarchy_node_draggable.js` (setzt den Elternknoten per `write`); Rechte über das ORM                                                                                   | Quelltext                                                                                                                                        |

**Nicht gemessen oder nicht erprobt:** Darstellung im Browser (Zeichnen vieler Knoten,
Ruckeln, Speicher); die Hierarchie-Ansicht im Betrieb; `ir.embedded.actions`,
Befehlspalette und `ir.filters` als Navigationsbausteine (nur im Quelltext gesehen); der
Server-Zwischenspeicher mit `@tools.ormcache`; die Hochrechnung auf 10.000 und 5.000
Ordner.

---

# Messreihe 3: Navigation über die Suche (2026-10-04)

Aufbau: Wegwerf-Datenbank wie oben, dazu **206.410 Dateien** in den untersten Ordnern
(insgesamt 276.856 Knoten, `Rechnung_<8 Hex>.pdf`, zufällige Zeitstempel über 3 Jahre),
Nutzer `tester` mit Regeln. Zwei Läufe: ohne und mit Odoos eigenem Trigram-Index
(`name = fields.Char(index="trigram")`) und einem nicht gespeicherten Pfad-Anzeigenamen
(`_compute_display_name`, Vorfahren mit den Rechten des Nutzers gelesen). Messmodul und
Datenbank nach der Messung gelöscht. Nur Serverseite; Suchleiste und Listen im Browser
sind nicht gemessen.

## Was die Odoo-Suche bietet (Core, Quelltext `web/static/src/search/`)

| Baustein           | Was er kann                                                                                                                                                                                            | Fundstelle                                                              |
| ------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------- |
| **Feld-Suche**     | Eingabe wird zu einem Vorschlag je Feld; Many2one holt Vorschläge mit `name_search`, lässt sich aufklappen (Pfeil) und mit "mehr" nachladen; `operator`, `filter_domain`, `context` im Suchansicht-XML | `search_bar.js`, `search_arch_parser.js`                                |
| **Filter**         | feste Bedingung (`domain`), mehrere Filter in einer Gruppe verbinden sich mit ODER, Gruppen mit UND (`<separator/>`)                                                                                   | `search_model.js`                                                       |
| **Datums-Filter**  | Auswahl von Zeitraum (Monat, Quartal, Jahr) mit Vergleich                                                                                                                                              | `search_arch_parser.js` (`date`, `start_year`, `default_period`)        |
| **Gruppieren**     | nach Feld und nach Datums-Intervall (Tag bis Jahr), mehrstufig, benutzerdefiniert, auch nach Eigenschaften                                                                                             | `custom_group_by_item`, `properties_group_by_item`, `utils/group_by.js` |
| **Facetten**       | jede Auswahl erscheint als Chip; Löschen, Umschalten, Kombinieren                                                                                                                                      | `search_model.js`                                                       |
| **Favoriten**      | gespeicherte Suche (`ir.filters`: Bedingung, Gruppierung, Sortierung), für alle oder bestimmte Nutzer, Standard-Favorit, je Aktion, an eingebettete Aktionen bindbar                                   | `ir_filters.py`                                                         |
| **Eigener Filter** | Bedingungseditor (Domain-Editor) für Nutzer                                                                                                                                                            | `domain_selector`                                                       |
| **Suchpanel**      | Kategorie (Baum) und Filter-Liste mit Zählern                                                                                                                                                          | `search_panel`                                                          |
| **Vorbelegung**    | `search_default_<name>` und `searchpanel_default_<feld>` im Kontext, damit auch Links                                                                                                                  | `search_model.js`                                                       |
| **Seitenzählung**  | Liste zählt nur bis 10.001, danach "10000+"                                                                                                                                                            | `count_limit`                                                           |
| **Operatoren**     | `child_of`, `parent_of`, `any`, `=like`, `ilike`, Datumsteile                                                                                                                                          | ORM                                                                     |

Was das Modul schon nutzt: Suchansicht mit Name, Tags, Status, Kontakt und Inhalt,
Filter (nur Ordner, nur Dateien, "mit Unterordnern", Tags, Prüfstatus), Gruppieren nach
Status. Der Ordner ist **keine Facette**, sondern ein Zustand im eigenen Suchmodell
(`folderId`, in der URL), der als Bedingung an jede Suche gehängt wird; "mit
Unterordnern" ist ein Marker-Filter.

## Messungen

| Nr. | Abfrage (276.856 Knoten)                                                     | ohne Trigram   | mit Trigram    |
| --- | ---------------------------------------------------------------------------- | -------------- | -------------- |
| S1  | Namenssuche, seltenes Stück (3 bis 10 Treffer), Liste mit Zählung bis 10.001 | 69 bis 81 ms   | **5 bis 6 ms** |
| S2  | Namenssuche häufiges Stück (alle Dateien), 80 Zeilen                         | 16 bis 18 ms   | 16 bis 18 ms   |
| S3  | seltenes Stück nur im Teilbaum `a1` (`child_of`)                             | 69 bis 97 ms   | **5 bis 6 ms** |
| S4  | seltenes Stück im Teilbaum per `parent_path =like`                           | 70 bis 74 ms   | 7 bis 8 ms     |
| S5  | `search_count`, seltenes Stück, ohne Grenze                                  | 67 bis 78 ms   | **2 ms**       |
| S6  | Vorschläge in der Suchleiste (`web_name_search`, 8)                          | 67 bis 80 ms   | **3 ms**       |
| S7  | dasselbe mit Pfad als Anzeigename ("Test / a1 / b1 / c7")                    | 68 bis 79 ms   | **4 bis 5 ms** |
| S8  | Gruppieren nach Ordner im Teilbaum `a1`, nur Dateien, 80 Gruppen             | 67 bis 82 ms   | 73 bis 82 ms   |
| S9  | Gruppieren nach Ordner, ganze Ablage, 80 Gruppen                             | 415 bis 479 ms | 425 bis 476 ms |
| S10 | Gruppieren nach Jahr (`mtime:year`), ganze Ablage                            | 110 bis 128 ms | 113 bis 125 ms |
| S11 | Gruppieren nach Monat, ganze Ablage                                          | 122 bis 130 ms | 116 bis 119 ms |
| S12 | Jahr, dann Monat im Teilbaum `a1`                                            | 27 bis 33 ms   | 27 bis 34 ms   |
| S13 | Gruppieren nach Kontakt, ganze Ablage                                        | 37 bis 48 ms   | 37 bis 52 ms   |
| S14 | "Zuletzt geändert": 80 neueste, sortiert nach `mtime`, ganze Ablage          | 45 bis 61 ms   | 45 bis 61 ms   |
| S15 | 80 Zeilen in Standardreihenfolge (`parent_path`), ganze Ablage               | 10 bis 11 ms   | 9 bis 11 ms    |

Der Trigram-Index entstand beim Installieren des Messmoduls in rund 11 Sekunden auf
276.856 Zeilen (Indexgröße nicht erhoben).

## Lesart

1. **Die Namenssuche ist mit einer einzigen Feldeinstellung schnell:** `index="trigram"`
   (Odoo-eigene Option) senkt Teilwortsuche, Zählung und Vorschläge von rund 70 ms auf 2
   bis 6 ms; ohne Index ist sie bei 277.000 Knoten noch brauchbar, wird aber mit der
   Ablage linear langsamer.
2. **Suche im Ordner (Teilbaum) kostet nichts extra:** `child_of` und
   `parent_path =like` sind gleich schnell (5 bis 8 ms mit Index). "In diesem Ordner und
   darunter suchen" ist damit ein Filter, kein eigener Mechanismus.
3. **Mehrdeutige Namen löst ein Pfad als Anzeigename:** In einer
   Suchleisten-Vorschlagsliste wären "c7" 1.600-mal gleich; als Pfad ("Test / a1 / b1 /
   c7") sind sie eindeutig, und das geht ohne gespeicherten Pfadnamen in 4 bis 5 ms,
   weil nur die 8 Vorschläge ihre Vorfahren lesen (Rechte des Nutzers, wie bei
   `breadcrumb`).
4. **Gruppieren ist als Navigation brauchbar, aber begrenzen:** Ordner-Gruppen über die
   ganze Ablage 0,4 bis 0,5 s (bei 68.800 Ordnern mit Dateien), im Teilbaum rund 70 ms;
   Zeit-Gruppen 30 bis 130 ms; Kontakt-Gruppen unter 55 ms.
5. **Die Standardsortierung (`parent_path`) ist die schnellste (10 ms), Sortieren nach
   Zeit kostet 45 bis 61 ms** ohne Index auf `mtime`.

## Wie Navigation über die Suche laufen kann

| Muster                                                                                                                                                                              | Aus welchen Odoo-Teilen                                                                                        | Status                                                |
| ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------- |
| **Ordner als Facette:** "Ordner: Verträge / 2023" als Chip in der Suchleiste, Klick auf eine Ordnerzeile setzt ihn, Löschen geht eine Ebene hoch; Brotkrumen und Chip sind dasselbe | Facette (`search_model`), Feld-Suche auf `parent_id` mit Operator `child_of`, URL-Schlüssel (schon da)         | Idee; heute Zustand am Suchmodell, keine Facette      |
| **Suchleiste als Adresszeile:** tippen, Vorschläge mit Pfad, Auswahl springt in den Ordner                                                                                          | `web_name_search` (3 bis 5 ms), Pfad als Anzeigename, Vorschläge der Suchleiste (Pfeil zum Aufklappen, "mehr") | belegt (S6, S7); Zusammenspiel im Browser ungeprüft   |
| **Gruppieren als Baum:** Ordner → Jahr → Monat als aufklappbare Gruppen                                                                                                             | Gruppieren nach `parent_id` und `mtime:year/month`                                                             | belegt (S8 bis S12), Darstellung im Browser ungeprüft |
| **Intelligente Ordner = Favoriten:** gespeicherte Suchen mit Bedingung, Gruppierung, Sortierung; für alle Nutzer teilbar                                                            | `ir.filters` (`user_ids`, `is_default`, `action_id`, `embedded_action_id`)                                     | belegt (Modell), Eignung ungeprüft                    |
| **Zeit statt Ort:** Datumsfilter und Gruppieren nach Zeitraum                                                                                                                       | Datums-Filter, `mtime:year`                                                                                    | belegt (S10 bis S12)                                  |
| **Eigenschaften als zweite Achse:** Tags, Status, Kontakt mit Zählern                                                                                                               | Suchpanel-Filter (`select="multi"`, `enable_counters`) oder Facetten; Gruppieren nach Kontakt 37 bis 52 ms     | belegt (S13)                                          |
| **Zuletzt geändert:** vorbelegte Sortierung                                                                                                                                         | Favorit mit `sort`, `order`                                                                                    | belegt (S14)                                          |
| **Strg+K Direktsprung:** eigener Provider in der Befehlspalette                                                                                                                     | `commandProviderRegistry` + `web_name_search`                                                                  | belegt (Quelltext, S6)                                |
| **Links teilen:** Suchzustand per Kontext und URL                                                                                                                                   | `search_default_<name>`, `router`                                                                              | belegt (Quelltext)                                    |
| **Inhaltssuche:** Wörter im Dokument                                                                                                                                                | Feld `content` (im Modul), Trigram-Text der abgeleiteten Daten                                                 | im Modul vorhanden                                    |

## Einschränkungen und wie man sie mit Odoo-Mitteln löst

| Einschränkung                                  | Lösung mit Odoo-Mitteln                                                                                                                                | Beleg            |
| ---------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------------- |
| Vorschläge zeigen nur den Namen, viele gleiche | Pfad als Anzeigename über `_compute_display_name` (nicht gespeichert, Vorfahren mit Nutzerrechten per `search_fetch`)                                  | S7 4 bis 5 ms    |
| Teilwortsuche langsam bei vielen Knoten        | `index="trigram"` am Feld `name`                                                                                                                       | S1 bis S6        |
| Zählung beim Blättern                          | Listenzählung nur bis 10.001 (Odoo-Standard)                                                                                                           | S1, S2           |
| Gruppieren über die ganze Ablage ist langsam   | Gruppen begrenzen (80) und mit dem Ordner-Teilbaum filtern; Gruppierung "nach Ordner" nur im Teilbaum anbieten                                         | S8 gegen S9      |
| Suche liefert flache Trefferliste ohne Ort     | Spalte "Pfad" mit demselben Pfad-Anzeigenamen in der Ergebnisliste                                                                                     | S7               |
| Ordner ist keine Facette, sondern Zustand      | Facette über eine Many2one-Feld-Suche mit `child_of` und einer Anpassung des Suchmodells (`patch` oder Unterklasse, wie schon in `v2/search_model.js`) | Quelltext        |
| Rechte                                         | ORM wendet `ir.rule` bei Suchen, Gruppieren und Vorschlägen an; Vorfahren in Pfaden nur lesbare zeigen                                                 | S7, `breadcrumb` |
| Sortieren nach Zeit ohne Index                 | Index auf `mtime` (`index=True`) oder Sortierung begrenzen                                                                                             | S14 gegen S15    |

**Nicht gemessen oder nicht erprobt:** die Suchleiste und die Gruppen-Listen im Browser
(Zeichnen, Aufklapp-Verhalten, Zählung der Gruppen), `ir.filters` als intelligente
Ordner und eingebettete Aktionen, Indexgröße und Schreibkosten des Trigram-Index bei
Upload und Umbenennen, Wirkung bei 1,8 TB (die gemessenen 277.000 Knoten entsprechen
nicht dem Zielbestand mit 209.000 Bildern plus allen weiteren Dateien).
