# int_filemanager: UI-Modernisierung auf native Odoo-Komponenten — Status

Stand 2026-09-03. Getrenntes Thema von [int_filemanager_ausbau.md](int_filemanager_ausbau.md)
(dort: Backend-Phasen Scan-Identität/ACL/Versionierung/Vorschau/Freigaben). Hier: UI/UX
so nativ wie möglich an echten Odoo-Bausteinen statt eigenem Code.

## Zielbild

Explizite Vorgabe: so nah wie möglich an nativem Odoo-Verhalten/-Look, verifiziert am
echten Odoo-19-Quellcode (nicht angenommen), live gegen die Unraid-Instanz getestet.
Übergeordnetes Ziel (siehe auch `docs/int_filemanager_ausbau.md`): Mitarbeiter sollen
vom Windows Explorer auf die WebUI umsteigen — Parität zu Explorer/Directory Opus als
Messlatte für Tempo und Bedienbarkeit.

## Stand auf `master` (bereits umgesetzt, deployed)

Schrittweise wurden eigene UI-Bausteine durch echte Odoo-Web-Komponenten ersetzt:

- Checkboxen (`CheckBox`), Zeilen-Highlight, Pager (`Pager`) — native Widgets statt Eigenbau
- Sortierbare Spalten (Name/Größe/Geändert) mit nativer Sortier-Iconografie
- Komplette Toolbar über echtes `Layout`/`ControlPanel` (`static/src/int_filemanager/filemanager_action.xml`) —
  Breadcrumbs führen automatisch zurück zum aufrufenden Datensatz (z.B.
  `Kontakte / Administrator / Ausgangsrechnungen`-Muster), weil `env.config.breadcrumbs`
  genutzt wird statt eigener Navigation
- "+Neu"-Dropdown, Aktionen-Dropdown für Mehrfachauswahl, per-Zeile Kebab-Menü (`Dropdown`/`DropdownItem`)
- PDF-/Bildvorschau vollständig auf natives `FileViewer`/`useFileViewer` umgestellt
  (`preview_action.js`/`.xml` dafür komplett entfernt)
- Tags-Zelle: readonly bis Klick, dann editierbar — Verhalten nativer Listenzeilen nachgebildet
  (`inline_tags.js`, inkl. Fix für einen Race mit `useOwnedDialogs()`, siehe unten)
- Optionale Spalte "Verknüpft mit" über den nativen Gear-Icon-Spalten-Umschalter (`oi-settings-adjust`-Muster
  aus `list_renderer.js`), Zustand in `browser.localStorage`

**Datensatz-Verknüpfung (neues Feature, end-to-end umgesetzt):**
- `res_reference = fields.Reference(...)` auf `int_filemanager.file` (beliebiger Zieldatensatz)
- `IntFilemanagerLinkableMixin` (`models/filemanager_linkable_mixin.py`) — wiederverwendbarer
  Smart-Button-Baustein (`int_filemanager_count` + `action_view_int_filemanager_files`)
- Bisher nur auf `res.partner` verdrahtet (`models/res_partner.py`, `views/res_partner_views.xml`) —
  Mixin ist bewusst modellagnostisch gehalten, weitere Modelle sind ein reiner Vererbungs-Einzeiler
- `IntLinkRecordDialog` (`link_record_dialog.js`/`.xml`) — isolierter `Record` + `Field type="reference"`
- Rückverweis-Navigation filtert `int_filemanager.file` nach `res_reference` (inkl. `recursive`-Kontext
  für "auch Unterordner durchsuchen")

**Bekannte Bugs, die dabei gefunden und gefixt wurden** (Details siehe Commit-Historie auf `master`):
- Stichwörter-Dropdown flackerte kurz zu — Ursache: `useOwnedDialogs()` koppelt die Lebensdauer eines
  `SelectCreateDialog` an die Komponente, die ihn geöffnet hat; unser Fokus-getriebener
  readonly-Wechsel zerstörte diese Komponente mitten im Vorgang. Fix: readonly-Wechsel wird
  übersprungen, solange `document.body.classList.contains("modal-open")`.
- PDF-Vorschau: ESC funktionierte nach Klick ins iframe nicht mehr (Cross-Frame-Fokus) — Fix: eigener
  `keydown`-Listener direkt auf `iframe.contentWindow` (same-origin).
- Vollbild-Vorschau-Dialog: Lücken zum Rand / Drag verschob das Layout kaputt — Fix:
  `position:fixed!important; inset:0!important` scoped auf `.modal-fullscreen`, Pointer-Events auf dem
  Header deaktiviert (außer den Buttons), damit `useDialogDraggable` gar nicht erst greift.

## Experiment-Branch `experiment/native-listview`

Ausgangsfrage: würde ein **echtes** Odoo-`ListView`, direkt an `int_filemanager.file` gebunden,
als Dateibrowser funktionieren, statt weiter eigene Tabellen-UI zu pflegen? Bewusst auf einem
separaten, additiven, jederzeit verwerfbaren Branch geprüft — Produktiv-Menü/Action bleiben unberührt.

**Ergebnis: funktioniert, mit minimalem Override.** Einziger nötiger Eingriff:
`ListController.openRecord()` überschreiben, damit ein Klick auf eine Ordnerzeile die Liste mit neuer
Domain neu lädt statt eine (nicht existierende) Formularansicht zu öffnen — alles andere
(Sortierung, optionale Spalten inkl. `fields.Properties`-Aufsplittung, Mehrfachauswahl, `ActionMenus`,
Pager, Breadcrumbs) ist unverändertes natives `ListView`-Verhalten.

```
int_filemanager/views/filemanager_file_list_view.xml   -- neue Test-Action/Menü "Dateimanager (nativ, Test)"
int_filemanager/static/src/int_filemanager/native_list_view.js
```

`IntFilemanagerListController` (Kern, siehe Datei für vollständigen Code):
- `openRecord(record)`: bei `is_dir` → `goToFolder(path)`, sonst Download
- `goToFolder(path)`: `this.model.load({ domain: [["folder_path", "=", path || false]] })`
- `updateBreadcrumbs(path)`: baut `env.config.breadcrumbs` aus dem Pfad nach — **kein** eigener
  "Eine Ebene höher"-Button mehr (erste Fassung wurde vom Nutzer als "nicht elegant" abgelehnt,
  richtige Lösung war die native Breadcrumb-Array-Manipulation statt eines Zusatz-Buttons)

**Aktueller Arbeitsstand auf dem Branch:** unversioniert im Working Tree, wird mit diesem Commit
gesichert (Breadcrumb-Rework, gelöschte Zwischenfassung `native_list_view.xml`, Manifest-Eintrag).

**Entscheidung (2026-09-03, nach Architektur-Review): vollständig weiterportieren, alten Pfad danach
löschen.** Begründung: die produktive `IntFileManagerAction` baut Selection/`Dropdown`-Aktionsmenü/
`Pager`/Breadcrumbs von Hand nach, mit der (zum damaligen Zeitpunkt richtigen) Begründung, `ActionMenus`/
`SelectionBox` seien "fest an `RelationalModel`-Record-Objekte gekoppelt und für eine dateisystembasierte
Liste nicht sinnvoll nachbaubar" (siehe Memory `project_hm_odoo_filemanager.md`, Eintrag 2026-09-03).
Das stimmt nur, **weil** `/int_filemanager/list` rohe Dicts statt echter ORM-Records liefert. Dieser
Branch widerlegt genau diese Prämisse: bindet man direkt an `int_filemanager.file`, bekommt man echte
`RelationalModel`-Records — `ActionMenus`, `Pager`, Mehrfachauswahl, Sortierung, optionale Spalten sind
dann **kostenlos nativ**, ohne Nachbau. Der einzige nötige Eingriff bleibt `openRecord()`. Die aktuelle
Handarbeit an CheckBox/Dropdown/Pager/Breadcrumb-Markup ist also kein Zufall, sondern eine Folge des
Custom-Endpoints — und genau die Pflege, die mit echtem `ListView` entfällt. Zwei UI-Pfade dauerhaft
parallel zu pflegen wäre die doppelte Pflege, die vermieden werden soll — Ziel ist **Ablösung**, nicht
Koexistenz.

**Sicherheitsrelevanter Stolperstein beim Weiterportieren von Mutationen** (Upload/Mkdir/Umbenennen/
Löschen): `authz.py` (Kopfkommentar) hält fest, dass diese Routen die eigentlichen Dateisystem-Operationen
direkt über `os`/`shutil` ausführen, nicht über die ORM — `ir.rule` sichert das **nicht** automatisch ab.
`authz.require()`/`require_subtree_deletable()`/`require_rename_or_move_allowed()` werden bisher explizit
im Controller (`controllers/main.py`) aufgerufen. Lesen/Browsen ist unkritisch (beide Pfade laufen
nicht-sudo über dieselben generierten `ir.rule`-Regeln aus `acl_rules.py`, kein Unterschied zwischen
Custom-Endpoint und nativem `ListView`). Werden Mutationen aber naiv als objektgebundene Buttons
(`type="object"` auf `int_filemanager.file`-Methoden) nachgebaut, **muss jede dieser Methoden dieselben
`authz.*`-Aufrufe explizit wiederholen** — das passiert nicht automatisch nur weil es "nativ" aussieht.
Sonst umgeht ein scheinbar natives Button vor allem den Schutzordner-Mechanismus (Zugriffsschranken pro
geschütztem Ordner). Pflichtpunkt für jede Portierungs-PR, kein Nebensatz.

**Performance-Frage vermutlich unkritisch:** der aktuelle Controller macht pro Listing bereits
`search_count` + `search` (`main.py`) — praktisch dieselbe Arbeit, die `web_search_read` hinter
`model.load({domain})` macht. `folder_path` ist bereits indiziert. Kein struktureller Grund, warum
natives `ListView` langsamer sein sollte; eher im Gegenteil (eine Query-Runde statt Controller-Roundtrip +
manuelles Dict-Bauen). Kurze Bestätigung mit echten Ordnergrößen vor dem finalen Cutover trotzdem sinnvoll
(Ziel ist explizit Explorer-Tempo), aber kein Blocker mit unklarem Ausgang.

**Empfohlene Reihenfolge:**
1. SearchPanel-`domain`→`comodel_domain`-Mapping live verifizieren (siehe unten — kleinster Aufwand,
   entscheidet ob das Ordnerbaum-Konzept überhaupt trägt).
2. `native_list_view.js` schrittweise ausbauen: Preview (`FileViewer`-Hook im Controller, gleiches Muster
   wie `openRecord`), Upload/Mkdir/Umbenennen/Löschen/Verknüpfungs-Dialog als Buttons/Widgets — bei jeder
   Mutation den passenden `authz.*`-Aufruf aus `main.py` mit übernehmen.
3. Erst bei erreichter Funktionsparität: `filemanager_action.js`/`.xml`, `folder_tree.js`/`.xml` und den
   `/int_filemanager/list`-Endpoint löschen.
4. `parent_id`/`_parent_store` + Scan-BFS-Umbau danach, als eigener Schritt.

## Ordnerbaum als natives `SearchPanel` — Architektur-Entscheidung (Recherche abgeschlossen, Umsetzung offen)

Auslöser: `IntFolderTree` (eigene OWL-Komponente) durch etwas Natives ersetzen. Live am
Odoo-19-Quellcode auf dem Server verifiziert (`search_panel_select_range` in
`web/models/models.py:1643`), nicht nur angenommen.

**Live-Beispiel in der Instanz:** Lager → Berichtswesen → Bestand (`action_product_stock_view`,
Search-View `product_search_form_view_stock_report`) — zeigt eine "KATEGORIE"-Baumleiste links,
Klick filtert die Liste rechts.

### Kernentscheidung: kein zweites Modell

Odoos übliches Muster trennt Hierarchie- und Leaf-Modell (`product.category` ↔ `product.template`,
`hr.department` ↔ `hr.employee`). Hier **bewusst nicht** übernehmen: Ordner sind in
`int_filemanager.file` bereits volle Peer-Datensätze (`is_dir=True`, tragen Tags/`res_reference`,
laufen durch dieselbe Scan-/Merge-Logik). Eine Modelltrennung wäre ein Rückbau dieser bereits
getroffenen Entscheidung. Sauber heißt hier: **ein Modell, self-referencing.**

### Das Feld

```python
parent_id = fields.Many2one(
    "int_filemanager.file", string="Übergeordneter Ordner",
    index=True, ondelete="cascade",
)
_parent_name = "parent_id"
_parent_store = True
```

`_parent_store=True` ist der entscheidende Unterschied zu einem nackten Many2one: Odoo pflegt dann
selbst `parent_path` (Char, Präfix-Format), macht `child_of`/`parent_of` zu indizierten
Präfix-Queries, und kaskadiert bei einem Move automatisch über den ganzen verschobenen Teilbaum —
exakt der Mechanismus, den `product.category` intern nutzt.

`folder_path` (bestehendes Char-Feld) **bleibt unverändert** — es ist der literale Dateisystempfad,
den die Syscalls brauchen (open/rename/mkdir), das kann eine ID nicht ersetzen. `parent_id`/
`parent_path` sind die relationale Repräsentation für Baum/SearchPanel. Zwei Repräsentationen
derselben Hierarchie, jede die native Lösung für ihren eigenen Konsumenten (analog dazu, dass
`product.category` selbst zusätzlich `complete_name` neben `parent_path` pflegt) — keine
Dopplung im schlechten Sinne.

### Die SearchPanel-Arch

```xml
<searchpanel>
    <field name="parent_id" string="Ordner" icon="fa-folder"
           enable_counters="1" expand="1"/>
</searchpanel>
```

Kein `domain`-Attribut mehr am `<field>` — siehe Smoke-Test unten, das Attribut wird für
Category-Felder von Odoo schlicht ignoriert. Stattdessen filtert
`search_panel_select_range` serverseitig (Override, siehe unten). Die verbleibenden zwei
Attribute sind **Pflicht**:

- **`expand="1"` zwingend**, sonst zeigt der Baum nur Ordner, die aktuell mindestens einen
  bestätigten Nachfahren mit Daten haben (`domain_image`-Logik in `search_panel_select_range`).
  Ein frisch angelegter, leerer Ordner würde sonst im Baum **gar nicht erscheinen**.
- **`enable_counters="1"`** — Bonus passend zum DMS-Ziel: zeigt pro Ordner die Trefferzahl der
  aktuell gefilterten/gesuchten Datensätze.

#### Smoke-Test durchgeführt (2026-09-03) — Ergebnis: `domain`-Attribut bestätigt tot, Server-Override bestätigt nötig UND ausreichend

Reiner Server-Test über `docker exec odoo odoo shell` gegen die echte Unraid-DB, ohne Browser
(kein UI-Rendering geprüft, nur der ORM-Aufruf selbst) — `parent_id`/`parent_path` testweise als
reine Feld-Definition angelegt (keine Scan-Logik), zwei echte Datensätze per Hand verknüpft,
danach Feld + DB-Spalten wieder vollständig entfernt (kein Rückstand, siehe Commit):

- **Ohne `comodel_domain`** (= exakt das, was `search_model.js` für ein Category-Feld tatsächlich
  schickt — nur `category_domain`, kein `comodel_domain`, siehe oben): `search_panel_select_range`
  liefert bei realer Datenmenge **keinen falschen Baum, sondern einen harten Fehler**
  (`{'error_msg': 'Too many items to display.'}`), weil ausnahmslos alle ~hunderttausend Dateien
  *und* Ordner ungefiltert in die Zählung eingehen. Kein kosmetisches Problem, sondern ein Blocker.
- **Mit `comodel_domain=[('is_dir','=',True)]`** manuell übergeben (simuliert den geplanten
  `search_panel_select_range`-Override): liefert sauber alle **29.120** Ordner, kein Fehler,
  0,4s Serverzeit.
- Damit ist der Server-seitige Override (siehe "Sicherheitsrelevanter Stolperstein"-Abschnitt-Nachbar
  oben, jetzt als Pflichtteil des Plans) nicht nur die sauberere, sondern die **einzige
  funktionierende** Lösung — nicht nur "schöner als die Arch-Variante".

**Neuer Fund, der über die ursprüngliche Frage hinausgeht — Skalierung:** `expand=True` +
`hierarchize=True` ignoriert `search_domain`/den aktuell gebrowsten Pfad komplett für die
Knotenauswahl (das steckt im Odoo-Kern-Code selbst: der `if not expand:`-Zweig, der
`comodel_domain` auf die per `category_domain`/Vorfahren eingegrenzten IDs beschränkt, wird bei
`expand=True` schlicht übersprungen). Der Baum holt in **einem** Aufruf **alle** Datensätze, die
`comodel_domain` erfüllen — bei 29.120 Ordnern in dieser Instanz sind das mit dem Odoo-Standard
`limit="200"` sofort wieder "Too many items". Für den produktiven Einsatz ist ein deutlich
höheres `limit`-Attribut am `<field>` nötig (bei 29k Ordnern getestet: `limit="50000"` liefert in
~0,4s ein ca. 2,3 MB großes JSON — unkritisch für den Server, aber ein Punkt, den es vor dem
eigentlichen Umbau bewusst zu entscheiden gilt, nicht implizit über den 200er-Default
mitzuschleppen). Gehört mit in Schritt 1 der Ordnerbaum-Umsetzung unten.

**Umgesetzt (2026-09-03/04):** Arch nutzt `limit="0"` (kein Cap) statt einer konkreten Zahl —
seit `comodel_domain` per Override immer korrekt auf `is_dir=True` eingeschränkt ist, gibt es
keinen Grund mehr für eine künstliche Obergrenze; ein evaluiert falsy `limit` überspringt die
Limit-Prüfung im Odoo-Kern-Code komplett (siehe `search_panel_select_range`).

### Eigentlicher Aufwand: Pflege von `parent_id`, nicht das Feld selbst — umgesetzt (2026-09-03/04)

- **`_scan_and_reconcile`**: `to_create` wird jetzt nach Pfadtiefe gruppiert und pro Ebene erstellt
  (BFS, `os.walk` liefert Eltern zwar meist vor Kindern, aber Batch-/Merge-Reihenfolge garantieren
  das nicht zuverlässig genug für eine einzige `create()`-Liste), mit `path_to_id_cache` als
  wachsendem Zwischenspeicher über den ganzen Lauf.
- **Merge-Pfad bei Rename/Move während Odoo nicht lief**: beide Merge-Zweige (Datei- und
  Ordner-Identität) setzen `parent_id` jetzt über denselben Cache mit Lazy-Fallback (`Model.search`
  bei Cache-Miss) — funktioniert dank desselben Cursors auch für bereits in diesem Lauf
  umbenannte/neu angelegte Elternordner. Bekannter, dokumentierter Grenzfall (ein Datensatz wird
  in genau diesem Lauf in einen brandneuen, noch nicht erstellten Ordner verschoben): heilt sich
  beim nächsten Scan von selbst, kein Blocker.
- **Watcher/`mkdir`-Controller**: `index_upsert`/`index_move_tree` (`index_utils.py`) lösen
  `parent_id` jetzt über eine einzelne Query auf den unmittelbaren Elternordner auf — der
  Controller/Watcher selbst musste nicht angefasst werden, beide rufen nur diese Helper auf.
- **Migration Bestandsdaten — anders gelöst als ursprünglich geplant:** kein `post_init_hook`
  (der läuft laut Odoo-Kern-Code ohnehin nur bei Erstinstallation, nicht bei einem Upgrade einer
  laufenden Instanz). Stattdessen zunächst versucht, den periodischen `_cron_scan_filemanager`
  (ohnehin einmal täglich, re-visitiert jeden Bestandsdatensatz über `flush()`) den Backfill
  naturlich erledigen zu lassen — **das ist beim Live-Test krachend gescheitert:**

  **Wichtige operative Lehre:** `parent_id` record-für-record per `write()` auf den kompletten
  Bestand (427.767 Zeilen) zu setzen, hat Odoos `_parent_store`-Mechanismus in eine massiv
  redundante Kaskade laufen lassen — jeder einzelne Ordner-Write löst eine rekursive
  `UPDATE ... SET parent_path = concat(...)`-Query über alle **eigenen** Nachfahren aus (live an
  `pg_stat_activity` beobachtet), obwohl die meisten dieser Nachfahren Sekunden später ohnehin
  ihren eigenen direkten Write bekommen hätten. Nach 20+ Minuten ohne einen einzigen fertig
  befüllten Nicht-Wurzel-Ordner abgebrochen (keine Datenkorruption - bereits gelaufene 2000er-
  Batches waren sauber committed, der Rest einfach nicht erledigt).

  **Tatsächliche Lösung:** ein einmaliges rohes SQL-`UPDATE` direkt auf `int_filemanager_file`
  (Self-Join `child.folder_path = parent.path`, komplett am ORM vorbei, keine Kaskade) —
  427.767 Zeilen in **einem Statement**, danach `env["int_filemanager.file"]._parent_store_compute()`
  (Odoos eigene rekursive Bulk-CTE-Methode, dieselbe die auch beim Schema-Deploy für `parent_path`
  lief) zur `parent_path`-Neuberechnung für die komplette Tabelle in ~2 Minuten. Ergebnis
  verifiziert: 29.063 von 29.120 Ordnern (alle außer den 57 Wurzelordnern) korrekt mit `parent_id`,
  `search_panel_select_range("parent_id", ...)` liefert alle 29.120 Knoten fehlerfrei in ~3,5s.
  **Für zukünftige Bestandsdaten-Migrationen dieser Art (Self-Referencing-Feld auf großem Bestand
  nachträglich befüllen) merken: nie über ORM-`write()` pro Datensatz, sondern SQL-Backfill +
  `_parent_store_compute()`.** Der reguläre Scan-Pfad selbst (`flush()`/Merges/`to_create`) bleibt
  wie oben beschrieben - im Normalbetrieb ändert sich `parent_id` für die allermeisten Datensätze
  ohnehin nicht mehr (Odoo überspringt unveränderte Feldwerte beim `write()`), das Kaskadenproblem
  betraf ausschließlich den einmaligen Bestands-Backfill.

### Geprüfte Alternative: natives `hierarchy`-View (`web_hierarchy`) — verworfen

Odoo bringt seit einigen Versionen einen echten eigenen View-Typ für selbstreferenzierende
Baumstrukturen mit: `web_hierarchy` (`type="hierarchy"`, Arch-Tag `<hierarchy parent_field="..."
child_field="..." draggable="1">`). Live am Odoo-19-Quellcode auf der Unraid-Instanz verifiziert
(nicht nur angenommen):

- Modul liegt unter `odoo/addons/web_hierarchy`, `category: "Hidden"`, hängt nur von `web` ab —
  **Community-verfügbar**, kein Enterprise-Gate.
- `hierarchy_arch_parser.js`: verlangt zwingend ein Many2one-`parent_field` (Default exakt
  `parent_id`) auf **demselben** Modell — passt eins-zu-eins zum oben festgelegten
  `parent_id`/`_parent_store`-Design (kein zweites Modell). Optional ein `child_field`
  (One2many-Gegenstück) und `draggable="1"` für Reparenting per Drag&Drop.
- `hierarchy_renderer.xml`: rendert **keinen** eingerückten Listenbaum, sondern Kartenreihen pro
  Generation (`o_hierarchy_row`, `row-cols-2`…`row-cols-lg-5`), horizontal zentriert und mit
  Verbindungslinien zwischen den Ebenen verbunden — klassische Org-Chart-/Stücklisten-Optik
  (gebaut u.a. für `hr.employee`-Organigramme, BOM-Strukturen).

**Bewertung:** Für das eigentliche Ziel hier — eine kompakte Ordner-Sidebar im
Explorer/Directory-Opus-Stil (siehe Grundidee-Notiz) — ist das die falsche Visualisierung. Ein
Ordner mit 30+ Unterordnern würde als umbrechendes Karten-Grid dargestellt statt als eingerückte
Liste; der View ist zudem als vollflächige Content-Ansicht konzipiert, nicht als schmales
Sidebar-Widget neben einer Liste. Bestätigt aber indirekt die Modellentscheidung: sowohl
`SearchPanel`-Kategorie als auch `hierarchy`-View erwarten dasselbe native Muster
(selbstreferenzierendes Many2one mit `_parent_store`) — das oben geplante `parent_id`-Feld ist
also nicht nur für die SearchPanel-Lösung die native Wahl, sondern universell wiederverwendbar,
falls später doch mal eine Org-Chart-artige Strukturansicht (z.B. "diesen Ast als Baum
anzeigen") gewünscht wird. Für die Sidebar-Navigation bleibt es bei `SearchPanel` +
überschriebenem `search_panel_select_range` (siehe oben).

## Offene Punkte / nächste Schritte

1. ~~SearchPanel-`domain`-Attribut live smoke-testen~~ — erledigt (2026-09-03).
2. ~~`parent_id`/`_parent_store` + Scan-Anpassung (BFS) + `search_panel_select_range`-Override +
   SearchPanel-Arch + Bestands-Backfill~~ — erledigt (2026-09-03/04), auf `experiment/native-listview`
   deployed und live verifiziert (siehe oben). `int_filemanager_file_search` (Such-View, vorher
   ungenutzt) trägt jetzt das `<searchpanel>` und ist über `search_view_id` an die Test-Action
   `action_filemanager_file_list_native` gehängt.
3. **SearchPanel-Ordnerbaum-Klick <-> Zeilennavigation — Root Cause gefunden (2026-09-04), am
   Odoo-19-Quellcode verifiziert, live gegen die Unraid-Instanz getestet und bestätigt:**

   Ursache exakt lokalisiert (per `docker exec Odoo19` direkt im laufenden Container gelesen, nicht
   angenommen): `useModel()` (`web/static/src/model/model.js:117`) registriert unbedingt
   `onWillUpdateProps((nextProps) => model.load(getSearchParams(nextProps)))` auf der Komponente,
   die `useModel` aufruft — bei `ListController` also auf sich selbst, **bevor** irgendein
   Subklassen-Code läuft. Das lässt sich aus einer Subklasse nicht abschalten. `props.domain` kommt
   aus `WithSearch` (`with_search.xml`: `t-slot domain="searchModel.domain"`), das per
   `useBus(searchModel, "update", this.render)` bei jedem `searchModel`-Update neu rendert.
   `toggleCategoryValue()` (`search_model.js:808`) setzt nur `activeValueId` und ruft `_notify()` —
   das reicht, um die komplette Kette auszulösen. Ergebnis: zwei unabhängige Schreiber auf dasselbe
   `model` (der eigene `folder_path`-Reload und der native, nicht abschaltbare `parent_id`-Reload) —
   kein Timing-Bug, sondern zwei Wahrheiten für dieselbe Domain, wer zuletzt schreibt gewinnt.

   Zusätzlicher, unabhängiger Fund: `_getCategoryDomain()` (`search_model.js:1531`) nutzt für ein
   selbstreferenzierendes Many2one automatisch den Operator `child_of` (rekursiv: alle Nachfahren) statt
   `=` (nur direkte Kinder) — richtig für Produktkategorien, falsch für einen Ein-Ebenen-Datei-Browser.
   Und: `activeValueId === false` (Odoos "Alle") wird in `_getCategoryDomain` komplett übersprungen —
   nativ heißt das "kein Filter", nicht "nur Wurzelebene". Erklärt den beobachteten Endzustand
   (ungefilterte ~400k-Zeilen-Liste nach Klick auf "Alle") vollständig.

   **Fix (kein Core-Patch-gegen-das-Race, sondern Autoritäts-Wechsel — searchModel wird einziger
   Schreiber):**
   - `search_model_patch.js` (neu): ein `patch(SearchModel.prototype, { _getCategoryDomain ... })`,
     gescopet auf `this.resModel === "int_filemanager.file"` (gleiches Scoping-Muster wie
     `int_web_tweaks/list_column_reorder.js` über `resModel`) — übernimmt für unsere `parent_id`-
     Section komplett selbst den Domain-Aufbau: Operator immer `=` (nicht `child_of`) UND
     `activeValueId === false` wird zu `[('parent_id','=',false)]` statt "überspringen". Kein
     Core-Datei-Eingriff, jede andere View/Kategorie in der Instanz bleibt beim
     Odoo-Standardverhalten unberührt.
   - **Erster Anlauf über `hierarchize="0"` als Arch-Attribut verworfen, live als Fehler entdeckt:**
     schaltet zwar den Operator um, aber `search_panel_select_range` (`web/models/models.py:1711-1715`)
     lässt dann `parent_id` bei JEDEM Baumwert komplett weg (`if hierarchize and parent_name in
     Comodel._fields: field_names.append(parent_name)`) — der Baum fiel dadurch optisch flach
     zusammen (keine Einrückung mehr, jeder Ordner erschien als Wurzel) UND die
     Breadcrumb-Vorfahrenkette brach nach einem Glied ab, weil `value.parentId` für jeden Ordner
     `false` war. Live im Browser beobachtet (Klick auf "1" → "default" zeigte nur "default" in der
     Breadcrumb, "1" fehlte). Behoben durch Rückbau auf Odoos Default (`hierarchize` unverändert,
     `parent_id` wird wieder mitgeschickt) und stattdessen den kompletten Domain-Aufbau im Patch
     selbst nachgebaut, unabhängig von `hierarchize`.
   - `native_list_view.js` umgebaut: `this.currentPath`-getriebenes `reload()` entfernt.
     `openRecord()` ruft bei Ordnern `env.searchModel.toggleCategoryValue(sectionId, record.resId)`
     statt `model.load()` — es gibt jetzt nur noch einen Schreibkanal für die Domain, ein Race ist
     strukturell unmöglich, nicht nur seltener. Breadcrumbs werden aus der `parentId`-Kette der
     bereits geladenen Kategorie-Werte rekonstruiert (`updateBreadcrumbs()`, an
     `searchModel`-"update" gehängt — das schreibt aber nur das kosmetische
     `env.config.breadcrumbs`-Array, nie `model`/Domain, daher kein Rückfall in dasselbe
     Race-Muster). `this.currentPath` existiert weiterhin, aber nur noch als aus der Breadcrumb-Kette
     abgeleiteter String für die `path`-Parameter der bestehenden `mkdir`/`upload`-Routen — nicht
     mehr als Domain-Quelle.
   - `reload()` nach Mutationen ruft `this.model.load()` ohne Domain-Argument — `_getNextConfig`
     (`relational_model.js:193`) merged nur fehlende Parameter, die aktuelle Domain bleibt erhalten.

   **Live verifiziert (2026-09-04, echte Unraid-Instanz nach Vollsync auf 1.5.0 + Restart):**
   Baum zeigt echte Einrückung mit Aufklapp-Pfeilen (1/Dokumente/HM-Test als Wurzeln, Dokumente
   mit 6 direkten Kindern trotz "590" Nachfahren-Zähler - bestätigt `=` statt `child_of`).
   Vollständiger Zyklus Wurzel → "1" → "default" → zurück zu "1" → zurück zu "Alle" durchgespielt:
   Breadcrumb-Kette korrekt auf allen Stufen (`.o_breadcrumb`-DOM direkt inspiziert, nicht nur
   Screenshot), "Alle" zeigt weiterhin nur die 3 echten Wurzelordner statt aller 601 Zeilen, keine
   Konsolenfehler. Nebenbei aufgefallen und dokumentiert: die Instanz stand vor diesem Test bei
   Modulversion 1.3.0 (Repo war bei 1.5.0) - Phase 4/5 + der komplette parent_id-Spike waren nie
   tatsächlich deployed, nur im Repo committet. Vollsync aller 22 abweichenden Dateien + Modul-
   Upgrade + Backfill (598 von 601 Zeilen per SQL-Self-Join, `_parent_store_compute()`) nachgeholt.

   **Nachtrag, im Live-Test gefunden (2026-09-04): Klick auf die Wurzel-Breadcrumb tat nichts.**
   Aus mehreren Ebenen Tiefe (z.B. "Dateimanager (nativ, Test) / Dokumente / Artikel-PRÜFDOKUMENTE")
   auf den allerersten Breadcrumb-Eintrag geklickt → weder Liste noch die eigenen Unterordner-Krumen
   änderten sich. Ursache: dieser erste Eintrag ist NICHT einer unserer selbstgebauten
   Breadcrumb-Objekte (die reagieren korrekt über `toggleCategoryValue`), sondern der native
   Action-Breadcrumb, den Odoo selbst beim Pushen dieses Controllers auf den Stack anlegt - sein
   `onSelected` ruft nur `restore(controller.jsId)` auf denselben, bereits aktiven Controller auf
   (`action_service.js`), was am ORM-/searchModel-Zustand nichts ändert. Fix: in `setup()` wird
   `env.config.breadcrumbs[rootBreadcrumbCount - 1]` (der letzte bereits vorhandene Root-Eintrag -
   alles davor gehört ggf. einer aufrufenden Action/einem Datensatz und muss ihr natives Verhalten
   behalten) einmalig um einen zusätzlichen `toggleCategoryValue(section.id, false)` ergänzt, nach
   dem nativen Handler. Live erneut bis in "Artikel-PRÜFDOKUMENTE" navigiert, auf die Wurzel-Krume
   geklickt: Liste und Baum springen jetzt korrekt zurück auf die 3 Root-Ordner, `"Alle"` trägt die
   `active`-Klasse im DOM.

   **Zweiter Nachtrag, ebenfalls im Live-Test gefunden (2026-09-04): "Neuer Ordner"/"Hochladen"
   erscheinen ab einer bestimmten Fensterbreite riesig, sobald ein Breadcrumb zu "..." einklappt.**
   Reproduzierbar bei 1000px Fensterbreite (bei 800px nicht) - `resize_window` mit fester Breite
   genutzt, um den schwankenden Effekt greifbar zu machen, ein Nutzerhinweis auf ein
   deplaziertes Suchfeld als Begleitsymptom hat auf die richtige Spur gebracht. Per
   `getBoundingClientRect()` verifiziert: `font-size`/`padding` blieben die ganze Zeit unverändert
   (14px/5px 10px) - die Buttons wurden nicht größer gestylt, sondern der Text "Neuer Ordner" brach
   bei dieser Breite in zwei Zeilen um (Höhe 53,6px statt 32,6px, Breite nur 68px statt 113px).
   Ursache: unsere Buttons in `native_list_view.xml` hatten nur `class="btn btn-primary"` bzw.
   `btn-secondary` - Odoos eigener nativer "Neu"-Button trägt zusätzlich `o_list_button_add`
   (`list_controller.xml`), das genau diesen Umbruch verhindert. Fix: `text-nowrap` auf beide
   Buttons ergänzt. Bei 1000px erneut bis "1-SIEMENS-Revision..." navigiert: Buttons bleiben
   einzeilig (`getBoundingClientRect()` wieder 32,6px hoch, 113px breit).
4. ~~Entscheiden, ob/wie weit der native-ListView-Spike weiter ausgebaut wird~~ — entschieden
   (2026-09-04): weiter ausbauen, SearchPanel-Ordnerbaum ist jetzt verdrahtet (siehe Punkt 3).
5. **Skalierung des `<searchpanel>`-Ordnerbaums — geprüft, bewusst vorerst nativ belassen
   (2026-09-04):** `search_panel_select_range` hat kein Lazy-Loading pro Ebene, ist architektonisch
   nicht dafür vorgesehen (kein "nur Kinder von Knoten X"-Parameter, live am Quellcode geprüft,
   `web/models/models.py:1643-1780`) - jeder Seitenaufruf lädt immer den kompletten `is_dir=True`-
   Baum in einem Rutsch. Mit synthetischen 31.069 Testordnern gemessen (direkt per SQL angelegt,
   danach rückstandsfrei wieder gelöscht): Serverzeit unkritisch (0,76s kalt/0,37s warm, 2,08MB
   JSON), aber der Browser brauchte danach spürbar lange (grob niedriger zweistelliger
   Sekundenbereich) bis zur Interaktionsfähigkeit - vermutlich Owl-Reaktivität über die große
   `Map`, nicht DOM-Rendering (Baum blieb kollabiert, nur 55 sichtbare Knoten). Eine "native-Optik,
   nur Logik lazy nachladen"-Variante wurde geprüft und verworfen: `SearchPanel.toggleCategory()`
   (`search_panel.js:296`) ist reiner lokaler UI-State-Toggle ohne jeden Nachlade-Hook - ein
   Lazy-Patch müsste sowohl `SearchModel`-Fetch-Logik als auch private State-Interna der
   `SearchPanel`-Komponente anfassen (`this.state.expanded`, direktes Mutieren von
   `category.values`), deutlich invasiver und versionsabhängiger als der heutige
   `_getCategoryDomain`-Patch. Aktuelle reale Datenmenge (601 Zeilen/18 Ordner) macht das
   akademisch - Entscheidung: nativ belassen, erst bei echtem Wachstum Richtung mehrerer tausend
   Ordner neu bewerten (Alternative dann: `<searchpanel>` entfernen, Baum als kleine eigene
   Komponente mit gezielten `parent_id`-Queries pro Klick, analog der alten `/int_filemanager/tree`-
   Route aber ohne deren String-Pfad-Vergleich).
6. **Stichwörter-Spalte funktioniert nicht (2026-09-04) — gelöst über Formular-Dialog statt
   Inline-Editing:** Ursache war keine Regression, sondern eine seit Branch-Beginn fehlende
   Übernahme von `inline_tags.js` (der alten UI eigens gebaute Lösung für "Zelle klickbar
   editierbar, Rest der Zeile bleibt Navigation") - unsere `<list>` hat kein `editable`, und
   `editable` ist ohnehin Alles-oder-Nichts (`list_renderer.js: isInlineEditable()` gilt pro
   Definition für die ganze Liste, nicht pro Spalte; mit `editable` gesetzt hätte auch ein Klick
   auf "Name" nicht mehr navigiert, sondern die Zeile in Bearbeitung geschaltet - live am
   Quellcode nachvollzogen, nicht vermutet).

   Stattdessen umgesetzt: ein `<button type="object" icon="fa-arrow-right">` vor dem Namen
   (`filemanager_file_list_view.xml`), der `action_open_form()` (neu, `filemanager_file.py`)
   aufruft und ein Formular (`filemanager_file_form_view.xml`, neu: Name/Path/Größe/Geändert
   readonly, `tag_ids` + `res_reference` editierbar) als Dialog öffnet. Kein JS-Klick-Abfang
   nötig: ein `<button>` in einer Listenzeile löst nach `list_renderer.js` (`onButtonCellClicked`
   prüft `ev.target.closest("button")`) nie `openRecord()`/Zeilennavigation aus - reine
   Arch-Deklaration reicht. Icon `fa-arrow-right` gewählt in Anlehnung an das native
   "Datensatz öffnen"-Pfeilsymbol bei Many2one-Feldern (`oi-arrow-right`/`oi-launch` in
   `many2one.xml`) - inhaltlich dasselbe Symbol, nur im `fa`-Iconset, weil Listen-Buttons laut
   `list_renderer.xml` ausschließlich `fa fa-fw {{button.icon}}` rendern (kein `oi`-Iconset).
   `action_open_form()` setzt zusätzlich `"name": self.display_name`, damit der Dialogtitel den
   Datei-/Ordnernamen statt generisch "Odoo" zeigt.

   Live getestet: Pfeil-Klick bei Ordner ("Dokumente") und Datei (`Reparaturen.xlsx`) öffnet
   jeweils das Formular, Tag hinzugefügt + gespeichert, per SQL verifiziert
   (`int_filemanager_file_int_filemanager_tag_rel`) - Tag landet korrekt in der DB und erscheint
   danach in der Listenspalte. Namensklick auf beide Zeilen weiterhin unverändert (Ordner
   navigiert, Datei würde downloaden/previewen) - keine Überschneidung der beiden Klickziele.
7. **Video-Vorschau angeschlossen (2026-09-04):** `FileViewer` (`file_viewer.js`/`.xml`) unterstützt
   `isVideo` bereits nativ (echtes `<video controls>`) - bislang nur nicht angeschlossen. `mp4`/
   `webm`/`ogv` zu `PREVIEWABLE_EXTENSIONS` ergänzt (bewusst nur diese drei - von Browsern ohne
   Zusatz-Codec nativ abgespielt, anders als z.B. `.mov`), `toViewerFile()` setzt jetzt `isVideo`
   und `mimetype` statt Videos fälschlich als `isImage` zu behandeln. **Audio bewusst nicht
   mitgemacht:** im `FileViewer` gibt es kein `<audio>`-Element und keine `isAudio`-Eigenschaft -
   ein Audio-Icon/Vorschau-Versuch würde nur einen leeren Player zeigen, bräuchte einen eigenen
   kleinen Zusatzbaustein (separates Thema, nicht Teil dieser Änderung).

   **Bekannte Einschränkung - inzwischen behoben, siehe Punkt 11:** `/int_filemanager/download`
   (`controllers/main.py`) las die Datei komplett in den Speicher und lieferte sie als einen Block
   ohne HTTP-Range-Unterstützung. Vorspulen/Suchen in Videos funktionierte dadurch nicht.

   **Nachtrag, doch noch verifiziert (2026-09-04):** beim Testen der Text-Editor-Funktion (Punkt 9)
   tauchte zufällig eine echte `.mp4` im Testbestand auf (`odoo/VID_20260904_130327.mp4`) - Klick
   öffnet den `FileViewer` mit echtem `<video controls>`, Play abgespielt bis `0:03 / 0:03`
   (komplette Laufzeit), keine Konsolenfehler. Video-Vorschau damit vollständig bestätigt, nicht
   nur per Regressionstest angenommen.
9. **Text-Editor umgesetzt (2026-09-04) - CodeEditor ersetzt die readonly-Vorschau für Textformate:**
   `txt`/`csv`/`log`/`md`/`json` lösen jetzt `onEditText()` statt `onPreview()`/Download aus (bewusst
   aus `PREVIEWABLE_EXTENSIONS` entfernt, sonst würde `onPreview()` weiterhin zuerst greifen).

   - **Neue Route** `/int_filemanager/write_text` (`controllers/main.py`), bewusst 1:1 nach dem
     Muster von `mkdir`/`rename`/`delete` gebaut: `type="jsonrpc"`, `_check_access()` →
     `resolve_path` → `to_relative` → `authz.require(..., "write")` (nicht `"unlink"`, nicht
     `require_rename_or_move_allowed" - Pfad ändert sich nicht, nur Inhalt), Datei schreiben,
     `index_upsert()` (Größe/`mtime`/`hash_state` sofort nachziehen, wie bei `mkdir`), `{"ok": True}`.
     Lesen des Inhalts braucht keine neue Route - `fetch(downloadUrl).then(r => r.text())` gegen
     die bestehende `/int_filemanager/download?disposition=inline` reicht.
   - **Neuer Dialog** `IntTextEditorDialog` (`native_ui/text_editor_dialog.js/.xml`, nicht `shared/`
     - nur die aktiv weiterentwickelte native UI bekommt das, die alte UI wird nicht mehr angefasst):
     nativer `CodeEditor` (`@web/core/code_editor/code_editor`, derselbe ACE-Wrapper, den Odoo für
     die View-XML-Bearbeitung im Entwicklermodus nutzt) in einem `Dialog`, Speichern ruft die neue
     Route, `onSaved` löst `reload()` der Liste aus.

   **Live komplett Ende-zu-Ende verifiziert** (`odoo/Notizen.txt`): Dialog zeigt echten Inhalt mit
   Zeilennummern, Zeile ergänzt, gespeichert - Listengröße sofort von 45 auf 68 Bytes aktualisiert,
   `cat` auf der echten Datei via SSH bestätigt den neuen Inhalt tatsächlich auf der Platte. Keine
   Konsolenfehler.
10. **`size` Float → Integer, plus `invisible="is_dir"` (2026-09-04):** Nutzer bemerkte, dass die
    Größe-Spalte (im Gegensatz zu allen anderen) rechtsbündig ist - Odoo-nativ bestätigt
    (`list_renderer.js:75-77`: `float`/`integer`/`monetary` bekommen automatisch die Klasse
    `o_list_number`, kein eigenes Zutun). Daraus zwei echte Mängel abgeleitet: Bytes sind nie
    fraktional (Feld war trotzdem `Float`, zeigte "0,00"/"68,00" - `hash_size`/`meta_source_size`
    auf demselben Modell waren schon immer `Integer`, `size` war die Ausnahme), und für Ordner ist
    "Größe" konzeptionell gar keine sinnvolle Eigenschaft, nicht nur zufällig 0.

    `size` auf `Integer` umgestellt, `invisible="is_dir"` auf dem Feld in
    `filemanager_file_list_view.xml` ergänzt (blendet die Zelle für Ordner-Zeilen komplett aus,
    Odoos übliche bedingte Sichtbarkeits-Syntax, funktioniert pro Zeile auch innerhalb einer
    Liste). Alle Python-Schreibstellen (`index_utils.py`, Scan/Merge in `filemanager_file.py`,
    `write_service.py`) liefern ohnehin schon `os.path.getsize`/`st.st_size`/`len(...)` - echte
    Integers, keine Anpassung nötig.

    **Migration lief automatisch:** Modul-Upgrade hat die Spalte selbst von `double precision` auf
    `integer` migriert (`information_schema.columns` vorher/nachher geprüft), keine manuelle
    SQL-Migration wie beim `parent_id`-Backfill nötig - Werte blieben korrekt (68, 5204338, ...).
    Live verifiziert: Wurzelordner zeigen jetzt eine leere Zelle statt "0,00", Dateien zeigen "68"
    statt "68,00", Tausendertrennzeichen bei großen Werten weiterhin korrekt. Formular-Dialog
    (`filemanager_file_form_view.xml`) bewusst nicht mit angefasst - dort wurde nur nach der
    Listenspalte gefragt.
11. **Video-Spulen behoben (2026-09-04) - `http.Stream` statt manuellem `open()+read()`:** Nutzer
    meldete, dass Vorspringen in der Timeline im Player nicht geht - genau die in Punkt 7
    dokumentierte, damals bewusst offen gelassene Einschränkung. `/int_filemanager/download`
    (`controllers/main.py`) las die Datei bisher komplett in den Speicher und lieferte sie als
    einen Block, keine `Accept-Ranges`/206-Unterstützung, ohne die der Browser im `<video>`-Element
    nicht gezielt springen kann.

    Odoo hat dafür bereits eine fertige Klasse: `odoo.http.Stream` (`http.py:514`). Deren
    `get_response()` ruft intern Werkzeugs eigenes `send_file(conditional=True)` auf, das
    206 Partial Content/Range-Requests automatisch beherrscht - dieselbe Mechanik, die Odoo selbst
    für Attachment-Downloads/Video-Streaming nutzt, hier also wiederverwendet statt selbst
    Range-Header-Parsing zu bauen. `Stream.from_path()` (der übliche Konstruktor) scheidet aus:
    intern ruft er `file_path()` auf, das einen Pfad unterhalb eines bekannten `addons_path`
    verlangt - unser konfigurierbares, beliebiges Filemanager-Stammverzeichnis liegt außerhalb
    davon. Stattdessen `Stream(type="path", path=..., ...)` direkt konstruiert - die eigene
    `authz.require(..., "read")`-Prüfung, die vorher schon lief, übernimmt die
    Zugriffskontrolle, die `from_path()` sonst generisch mitgebracht hätte.

    **Live verifiziert, nicht nur angenommen:** `fetch()` mit `Range: bytes=1000-2000` gegen die
    Route direkt getestet - Antwort `status: 206`, `Content-Range: bytes 1000-2000/5204338`,
    `Accept-Ranges: bytes`, `Content-Length: 1001` (exakt die angeforderten Bytes, nicht die ganze
    5,2-MB-Datei). Danach im echten Player auf `odoo/VID_20260904_130327.mp4` in die Timeline
    geklickt: Sprung direkt zu `0:02 / 0:03` mit sichtbar anderem Frame, kein sequentielles
    Abspielen bis dorthin. Keine Konsolenfehler.
12. **`size`-Spalte linksbündig statt nativ rechtsbündig (2026-09-04):** Odoo ordnet `float`/
    `integer`/`monetary`-Feldern automatisch die Klasse `o_list_number` zu (`list_renderer.js:75-77`),
    die per `list_renderer.scss` rechtsbündig ausrichtet - Nutzerwunsch war, `size` wie alle anderen
    Spalten linksbündig zu zeigen. Bewusst **nicht** global überschrieben (würde jede Zahlenspalte
    in jeder anderen Odoo-View im System mit verändern) - stattdessen eine eigene Scoping-Klasse:
    `IntFilemanagerListController.get className()` hängt `o_int_filemanager_list` an
    (`native_list_view.js`), neue `native_list_view.scss` überschreibt `.o_list_number`/
    `.o_list_number_th` nur innerhalb dieser Klasse.

    **Erster Versuch ohne `!important` scheiterte, live nachgewiesen** (`getComputedStyle` zeigte
    weiterhin `text-align: right`, sowohl in dieser Session als auch vom Nutzer im eigenen Browser
    bestätigt): die native Regel liegt verschachtelt unter `.o_list_renderer { ... }`, dadurch höhere
    Spezifität als der eigene Zwei-Klassen-Selektor angenommen. Mit `!important` behoben - das ist
    hier der akzeptierte Weg, eine Drittanbieter-Core-Regel gezielt von außen zu überschreiben, nicht
    Bequemlichkeit. Live erneut per `getComputedStyle` bestätigt: `text-align: left` für Zelle und
    Header, keine Konsolenfehler.
13. **Sicherheitsrelevant, nicht vergessen:** für die Live-Tests in dieser Session wurde ein
    temporäres Admin-Passwort (`TempDebug2026!`) auf der Unraid-Instanz gesetzt — bewusst noch nicht
    zurückgesetzt (Stand 2026-09-04, auf Wunsch offen gelassen).
14. **Deploy-Blocker gefunden und gefixt (2026-09-04): `size` als `Integer` überlebt reale Dateien
    nicht.** Beim Ausrollen des kompletten Branch-Stands auf die Unraid-Instanz (Modul-Upgrade gegen
    die echte `odoo`-DB mit 427.913 Zeilen) schlug die Spalten-Migration aus Punkt 10 mit
    `psycopg2.errors.NumericValueOutOfRange: integer out of range` fehl. Ursache: Odoos `Integer`-Feld
    ist ein 32-Bit `int4` (Max. ~2,1 GB) - `max(size)` im echten Bestand liegt bei **15.022.675.968
    Bytes (~14 GB)**. Der frühere Test dieser Migration (Punkt 10) lief nur gegen kleine
    Testdateien, nicht gegen den realen Bestand. Fix: `size` zurück auf `fields.Float`, aber mit
    `digits=(0, 0)`, um weiterhin ohne Nachkommastellen anzuzeigen (der eigentliche Punkt-10-Wunsch)
    - kein Integer-Overflow mehr möglich, da `numeric`/`double precision` in Postgres. `hash_size`/
    `meta_source_size` bleiben `Integer` (bestehendes, nicht Teil dieser Änderung) - tragen
    theoretisch dasselbe Risiko, aber das ist vorbestehend und nicht Gegenstand dieses Fixes.

15. **SearchPanel-Skalierung erneut gemessen (2026-09-04) - diesmal gegen echte Daten UND mit dem
    tatsächlich deployten `search_panel_select_range`-Override (nicht nur ein isoliertes Feld wie
    beim Test in Punkt 5):** Server-seitig per `odoo shell` gemessen (kein Browser/Login nötig),
    exakt derselbe Aufruf, den `native_list_view.js`/`search_model_patch.js` beim Laden auslösen.

    | Ordner (`is_dir=True`) | Gesamtzeilen | ohne `enable_counters` | mit `enable_counters` |
    |---|---|---|---|
    | 29.120 (aktueller Realbestand) | 427.913 | 0,44s | 1,93s |
    | 129.121 (+100.000 synthetisch) | 527.914 | 4,75s | 8,32s |

    Synthetische Ordner per SQL-Bulk-Insert unter eigenem isolierten Wurzelpfad
    `/synthetic-scale-test` angelegt (nicht per ORM-`write()`, siehe Kaskaden-Falle in Punkt
    "Eigentlicher Aufwand"), `_parent_store_compute()` danach für die Neuberechnung, nach dem Test
    rückstandsfrei gelöscht + erneut `_parent_store_compute()` - Endstand wieder exakt 427.913/29.120
    verifiziert.

    **Zwei unabhängige, klare Befunde:**
    - **`enable_counters=True` ist teuer und skaliert mit der Gesamtzeilenzahl, nicht der
      Ordnerzahl** - schon bei 29.120 realen Ordnern kostet es +1,49s (0,44s→1,93s), weil dabei
      alle 427.913 Zeilen (nicht nur Ordner) pro Baumknoten gezählt werden müssen. Der in Punkt
      "Die SearchPanel-Arch" genannte Vorteil ("Bonus passend zum DMS-Ziel") hat also einen realen
      Preis, der beim ursprünglichen Smoke-Test (kleiner, dateiloser Testbestand) nicht sichtbar war.
    - **Die Skalierung selbst ist deutlich schlechter als linear:** 4,4x mehr Ordner (29k→129k)
      kosten 10,8x mehr Zeit ohne Counter (0,44s→4,75s), nicht ~4,4x. Vermutlich `expand=True` +
      `hierarchize` (Baumaufbau in `search_panel_select_range`, `web/models/models.py`) - nicht
      weiter root-caused, da für die Entscheidung hier nicht nötig.

    **Einordnung gegenüber der bisherigen Entscheidung in Punkt 5** ("nativ belassen, erst bei
    echtem Wachstum neu bewerten"): der reale Bestand *heute* liefert mit `enable_counters` bereits
    1,93s Serverzeit für einen Aufruf, der bei jedem Seitenaufruf/Navigationsschritt in der
    Dateimanager-Liste feuert (`useModel`/`SearchModel`-Reload) - das ist schon jetzt spürbar, nicht
    erst bei künftigem Wachstum. Keine Änderung an Code/Verhalten in dieser Session vorgenommen
    (reine Messung) - **offene Entscheidung für die nächste Session:** `enable_counters` default
    abschalten (oder nur bei Bedarf einblenden) und/oder das in Punkt "Skalierung des
    `<searchpanel>`" bereits skizzierte Lazy-Loading-Alternative jetzt angehen, statt wie bisher auf
    "spürbares künftiges Wachstum" zu warten - die Zahlen zeigen, dass der Schwellenwert real schon
    erreicht ist.

16. **SearchPanel-Counter-Performance behoben, Navigations-Latenz produktionsnah gemessen, echte
    Lazy-Alternative gefunden (2026-09-04) - Fortsetzung von Punkt 15:**

    **Testumgebung, weil kein Zugriff auf HM-SRV bestand:** komplett separate Odoo-19-Instanz auf
    einem *zweiten* Unraid-Server ("Tower", 192.168.178.73, nicht HM-SRV) aufgesetzt - eigenes
    Docker-Image (Repo-`Dockerfile`), eigene Postgres-17-Instanz, `onlyoffice_odoo` vom offiziellen
    `19.0`-Branch nachinstalliert (harte Manifest-Abhängigkeit, im Repo nicht enthalten). Echte
    Datenbasis über `/mnt/user/Daten` (ein bestehender, aktiver persönlicher Datenbestand auf
    diesem Server) **read-only** gemounted - explizit read-only, weil dort auch sensible Daten
    liegen (u.a. ein `Keepass`-Ordner); erster Scan ergab 87.036 Zeilen/7.788 Ordner. Für
    produktionsnahe Messungen zusätzlich synthetisch auf **427.914 Zeilen/29.121 Ordner** hochskaliert
    (rohes SQL-Bulk-Insert unter isoliertem `synthetic-scale-test`-Pfad, `_parent_store_compute()`
    danach, exakt die in Punkt "Eigentlicher Aufwand" dokumentierte Methode) - trifft den echten
    HM-SRV-Bestand (427.913/29.120) fast exakt. Nach den Messungen rückstandsfrei wieder entfernt
    (`DELETE ... WHERE path LIKE 'synthetic-scale-test%'` + erneutes `_parent_store_compute()`),
    Endstand 87.040/7.788 verifiziert (die 4 zusätzlichen Zeilen ggü. dem ersten Scan sind keine
    Testreste, sondern echte neue Dateien, die während der Session auf `/mnt/user/Daten` entstanden
    sind - per Pfad/Zeitstempel verifiziert, nicht angenommen).

    **Root Cause der Counter-Kosten, per `EXPLAIN ANALYZE` gefunden (kein N+1, wie zunächst
    vermutet):** `search_panel_select_range` → `_search_panel_field_image` →
    `_search_panel_domain_image` baut über `formatted_read_group` eine einzelne, aber schlecht
    geplante Query - `GROUP BY`/`ORDER BY` teilen sich dieselben Spalten (Eltern-`is_dir`,
    Eltern-`name`, `parent_id`), wodurch Postgres einen `GroupAggregate` wählt, der **alle** Roh-Kind-
    Zeilen vorsortiert statt nur die Ergebnisgruppen danach. Bei 87.036 Zeilen: 125ms inkl.
    Platten-Spill (`Sort Method: external merge`), mit `work_mem=64MB` (kein Spill mehr) immer noch
    95ms - der Sort selbst ist die Kosten, nicht die I/O. Odoos eigenes, tieferliegendes `_read_group`
    (statt `formatted_read_group`) liefert dieselben lokalen Zählungen ohne den Join/Sort in **10,8ms**
    (kein N+1, eine einzelne indizierte `GROUP BY parent_id`-Query).

    **Patch (chirurgisch, am bestehenden, bereits genutzten Erweiterungspunkt, kein Core-Patch):**
    [filemanager_file.py](../int_filemanager/models/filemanager_file.py) - der bestehende
    `search_panel_select_range`-Override wird um `_search_panel_parent_id_counters()` ergänzt: Baum
    weiterhin unverändert nativ per `super()` mit `enable_counters=False` holen (bereits schnell),
    lokale Zählung selbst per `self._read_group(...)` nachladen, danach Odoos **eigene**
    `_search_panel_global_counters()` für den lokal→global-Rollup wiederverwenden (keine
    Neuimplementierung - dieselbe Methode, die die rekursiven Nachfahren-Summen erzeugt, siehe das
    "590"-Beispiel weiter oben). `count_domain` wird identisch zu Odoos eigener Formel
    (`search_domain & category_domain & filter_domain`) über `Domain.AND([...])` nachgebaut, damit
    aktive Filter/Suchen die Zählung weiterhin korrekt einschränken.

    **Korrektheit verifiziert (nicht nur behauptet):** echte `BaseModel`-Implementierung per
    MRO-Walk direkt aufgerufen (umgeht den eigenen Override) und mit dem gepatchten Ergebnis
    verglichen - bitgenau identische `__count`-Werte in 4 Domain-Szenarien (kein Filter, nur Dateien,
    nur Ordner, `name ilike 'a'`), sowohl bei 87k- als auch bei 427k-Zeilen-Skala (29.121 Knoten,
    0 Abweichungen). Zusätzlich die komplette Addon-Testsuite (66 Tests) in einer **frischen,
    isolierten** Datenbank (`odoo19test_ci`, ohne echte Daten, `-e HOST/USER/PASSWORD` statt
    `--db_host`-CLI-Flags - der offizielle Odoo-Entrypoint prüft die DB-Verbindung selbst anhand
    dieser Env-Variablen, bevor er eigene CLI-Argumente überhaupt sieht) laufen lassen: **0 failed,
    0 error(s) of 66 tests.** (Ein erster Versuch, die Suite direkt gegen die echte, befüllte
    `odoo19test`-DB laufen zu lassen, wurde abgebrochen - ein Media-Metadaten-Test verarbeitete dabei
    versehentlich den kompletten realen `pending`-Medienbestand mit und lief absehbar sehr lange;
    kein Datenverlust, da Odoo-Tests standardmäßig per Savepoint zurückgerollt werden, aber
    methodisch falsch aufgesetzt - Lehre: Testsuiten dieses Addons nur gegen eine separate DB laufen
    lassen, nie gegen eine mit echtem Datenbestand.)

    **Navigations-Latenz im echten Browser gemessen (nicht nur Server-Funktion isoliert):** bei
    427.914/29.121 Zeilen, per `performance.getEntriesByType('resource')` auf denselben Klick, direkt
    nacheinander unter gleichem Cache-Zustand gemessen:

    | | Server (`odoo shell`) | Browser (echter Klick) |
    |---|---|---|
    | Nativ | 3,48s | 1.744ms |
    | Gepatcht | 0,46s | 572ms |

    Browser-Verhältnis (≈3x) kleiner als das reine Server-Verhältnis (≈7,5x), weil im Browser fixe
    Kosten (Rendering, Netzwerk, restliche Seite) mit reinspielen, die der Patch nicht verändert -
    trotzdem ~1,2s realer Latenzgewinn pro Ordnerklick bei Produktionsgröße.

    **Neuer, wichtiger Fund über die ursprüngliche Frage hinaus - echte Lazy-Navigation ist bereits
    in Odoo eingebaut, keine SearchPanel-Interna-Patch nötig:** live im echten `search_model.js`
    dieser Odoo-19-Version nachgelesen (`_reloadSections()`):
    ```js
    const toFetch = (section) =>
        section.enableCounters || (searchDomainChanged && !section.expand);
    ```
    Mit `expand="1"` (wie in unserer Arch) reduziert sich das zu **`toFetch = enableCounters`** - der
    komplette Baum wird bei *jedem* `toggleCategoryValue()`-Klick neu vom Server geholt, einzig und
    allein *weil* `enable_counters="1"` gesetzt ist, unabhängig davon, ob sich die eigentliche
    Such-/Filter-Domain überhaupt geändert hat. Live verifiziert: mit `enable_counters="0"`
    (temporär testweise umgeschaltet, siehe unten) löst ein Ordnerklick **keinen** neuen
    `search_panel_select_range`-Request mehr aus (per `performance`-Einträge nachgezählt: vorher/
    nachher exakt ein Eintrag, nicht zwei) - nur die Hauptliste lädt neu (`web_search_read`, günstig,
    indizierte `folder_path`/`parent_id`-Gleichheitsabfrage, vergleichbar mit der alten
    `/int_filemanager/tree`-Route, dort 33ms für einen realen Ordner mit 31 Kindern, skaliert mit der
    Kindanzahl, nicht mit der Gesamtgröße des Baums).

    Damit ist die frühere Verwerfung einer Lazy-Variante in Punkt "Skalierung des `<searchpanel>`"
    weiterhin richtig für den dort geprüften Ansatz (`SearchPanel.toggleCategory()`/
    `SearchModel`-Interna patchen), aber nicht die einzige Lazy-Option: **`enable_counters`
    abschalten liefert dieselbe Lazy-Charakteristik kostenlos**, weil Odoos eigene
    Reload-Entscheidung ausschließlich daran hängt - kein Custom-Code, keine Versionsabhängigkeit.

    **Entscheidung (2026-09-04): Counter bleiben vorerst an,** trotz der bekannten Mehrkosten -
    Trefferzahlen im Baum wiegen aktuell stärker als die zusätzliche Latenz. Patch aus diesem Punkt
    bleibt als Absicherung aktiv (reduziert die Kosten der Counter-Variante um ~3x im Browser,
    ~7,5x serverseitig, ohne Verhaltensänderung). **Festgehalten für eine spätere Entscheidung:**
    sollten die Trefferzahlen im Baum doch verzichtbar werden, ist `enable_counters="0"` (ein
    Ein-Zeilen-Arch-Wechsel in `filemanager_file_search.xml`, kein weiterer Code nötig) die
    strukturell bessere Lösung, weil sie das *ganze* "kompletter Baum bei jedem Klick"-Problem
    eliminiert, nicht nur die Zählkosten darin.

    **Stand des Patches:** committet auf `experiment/native-listview` (`1624412`), nicht gepusht.
    Testinstanz auf Tower (`odoo19-test`-Container + `odoo19-test-db`, eigenes Docker-Netzwerk
    `odoo19-test-net`) läuft weiter für künftige Verifikationen; SSH-Key `claude-code-unraid` liegt in
    `authorized_keys` auf Tower. Admin-Login der Testinstanz: `admin`/`admin_test_2026` - wie beim
    `TempDebug2026!`-Passwort auf HM-SRV (Punkt 13) ein Test-Zugang, der bewusst nicht besonders
    abgesichert ist. **Port 8169 ist inzwischen auf Tower fürs LAN freigegeben** (nicht mehr nur
    127.0.0.1/SSH-Tunnel) - erreichbar unter `http://192.168.178.73:8169`, auf ausdrücklichen
    Nutzerwunsch.

17. **Bug gefunden und behoben: Tag-/Text-Suche in der Suchleiste fand nichts, sobald man nicht
    exakt im Ordner der Datei stand (2026-09-04):** live reproduziert - Datei `ColorThemes`
    (Tag `dfgdfg`) liegt unter `Audio/Projekte/REAPER/REAPER`. Suche nach dem Tag direkt in diesem
    Ordner: korrekt 1 Treffer. Dieselbe Suche eine Ebene höher (`Audio/Projekte/REAPER`): 0 Treffer,
    obwohl der SearchPanel-Zähler dort weiterhin "1" zeigt - der Treffer existierte also, war aber
    unsichtbar.

    **Ursache:** `search_model_patch.js` (Punkt "Fix" weiter oben) erzwingt für die
    Ordner-Navigation immer den Operator `=` auf `parent_id` (nur direkte Kinder) - richtig für
    reines Klicken/Browsen, aber kombiniert mit einer Suchleisten-Facette (Tag, Name, Filter)
    verlangt Odoo dann zwangsläufig "matcht die Suche UND ist direktes Kind hier". Eine Datei zwei
    Ebenen tiefer wird nie gefunden, unabhängig vom Suchbegriff. Odoos **eigener** Default für ein
    selbstreferenzierendes Many2one-Kategoriefeld ist eigentlich `child_of` (rekursiv, über den
    indizierten `parent_path`-Präfix) - wir hatten ihn für die Navigation bewusst auf `=`
    heruntergestuft, aber das galt uneingeschränkt auch für den Suchfall.

    Zum Vergleich: die alte UI (`master`) hatte dafür einen expliziten "auch Unterordner
    durchsuchen"-Umschalter (`state.recursive`, Default `false`, `filemanager_action.js`) - kein
    automatisches Verhalten beim Tippen.

    **Fix, im selben bestehenden Override, kein neuer Code-Pfad:** `_getCategoryDomain()` in
    `search_model_patch.js` prüft jetzt `this.query.length` (aktive Suchleisten-Facetten, komplett
    unabhängig vom Ordner-Navigationsstatus `category.activeValueId`) - ist eine Suche aktiv, wird
    `child_of` statt `=` verwendet; ist zusätzlich kein Ordner ausgewählt (`activeValueId` falsy,
    "Alle" + Suche), wird gar keine `parent_id`-Klausel gesetzt (durchsucht den ganzen Baum, wie
    Odoos ursprünglicher Default für eine leere Kategorie-Auswahl). Reine Navigation ohne aktive
    Suche bleibt exakt beim bisherigen `=`-Verhalten.

    **Bewusste Entscheidung gegen das alte Umschalter-Modell:** automatisch rekursiv sobald eine
    Suche aktiv ist, kein zusätzliches UI-Element, kein Opt-in nötig - deckt sich mit modernen
    Explorer-Suchfeldern und behebt den gemeldeten Bug ohne dass Nutzer erst einen Schalter kennen
    müssen. Live im Browser gegen die Testinstanz nachgestellt und vom Nutzer selbst bestätigt.

18. **Direkter Folgefund vom Nutzer, noch am selben Tag (2026-09-04): Klick auf einen
    Ordner in der Liste navigierte in der Breadcrumb korrekt rein, die Listenansicht zeigte aber
    weiterhin den alten Ordnerinhalt - bis der Tag-Filter entfernt wurde.** Live reproduziert:
    Ordner `ColorThemes` trägt selbst den gesuchten Tag `dfgdfg`, hat aber (zu dem Zeitpunkt)
    keine getaggten Kinder. Bei aktivem Tag-Filter eine Ebene höher hineingeklickt - Breadcrumb
    zeigte `.../REAPER/ColorThemes`, die Liste zeigte weiterhin **`ColorThemes` selbst** als
    einzige Zeile, nicht dessen (leeren) Inhalt.

    **Root Cause, per Runtime-Patch auf `SearchModel.prototype._getCategoryDomain` live
    nachgewiesen** (Odoo-Loader-Modul `@web/search/search_model` direkt im Browser gepatcht, um
    jeden Aufruf mit `activeValueId`/Ergebnis zu loggen - kein Rätselraten): die Domain wurde
    korrekt zu `[["parent_id","child_of",<ColorThemes-ID>]]` berechnet, `activeValueId` stimmte.
    Der eigentliche Fehler lag tiefer: **`child_of` auf `parent_id` ist selbst-inklusiv, wenn das
    Feld das eigene `_parent_name` des Modells ist** - die Query matcht den Ordner **selbst plus**
    alle Nachfahren, nicht nur die Nachfahren. Da `ColorThemes` selbst der einzige Treffer war,
    lieferte die (technisch korrekte) Query genau ihn zurück - sah aber aus wie "Navigation
    passiert nicht", weil dieselbe Zeile schon eine Ebene höher sichtbar war.

    **Fix (`search_model_patch.js`):** beim `parent_id`/`child_of`-Zweig zusätzlich
    `["id", "!=", <activeValueId>]` gesetzt, damit der gerade betretene Ordner nie mehr als Zeile
    seiner selbst erscheint, nur seine tatsächlichen Nachfahren. Verifiziert mit einem zweiten
    Testfall (Tag zusätzlich auf eine Datei *innerhalb* von `ColorThemes` gesetzt, testweise, nach
    Verifikation wieder entfernt): Suche von "Alle" aus findet weiterhin beide Treffer
    (`ColorThemes` + die Datei), Klick auf `ColorThemes` zeigt jetzt korrekt nur noch die Datei
    darin, nicht mehr `ColorThemes` selbst.

19. **Funktionsparität zur alten UI hergestellt (2026-09-04): Freigeben, ONLYOFFICE-Bearbeitung,
    "Lokal öffnen" nach `native_list_view.js` portiert.** Abgleich der `on*`-Methoden zwischen
    `legacy_ui/filemanager_action.js` und `native_ui/native_list_view.js` (per `grep`, nicht nur
    Erinnerung) hatte drei fehlende Features aufgedeckt - alle drei riefen im Original bereits
    fertigen, getesteten Backend-Code auf, es fehlte nur die Verdrahtung in der neuen UI:

    - **Freigeben** (`onShare`): nicht als eigener Dialog nachgebaut, sondern als neuer Eintrag
      `int_share` im bestehenden `getStaticActionMenuItems()` (demselben nativen `ActionMenus`-
      Erweiterungspunkt, den `Verknüpfen`/`Umbenennen`/`Löschen` schon nutzen) - ruft exakt
      dieselbe `action_filemanager_file_share` (`ir.actions.act_window`, `target="new"`) über
      `this.actionService.doAction()` auf wie die alte UI. Kein neuer Python-Code:
      `action_generate_share_token()`/`action_revoke_share_token()` (`filemanager_file.py`)
      existierten bereits vollständig inkl. Tests. `is_dir` blendet den Menüpunkt zusätzlich aus
      (Server lehnt Ordner ohnehin ab, `test_generate_rejects_folders`), damit er gar nicht erst
      zum Fehlschlagen einlädt.
    - **ONLYOFFICE-Bearbeitung** (`onEdit`): 1:1 aus `legacy_ui` übernommen - war dort bereits
      vollständig nativ (`this.actionService.doAction()` mit `type: "ir.actions.client"`, derselbe
      Mechanismus, unter dem `onlyoffice_odoo` seine Editor-Komponente registriert). Die einzige
      RPC vorweg (`/int_filemanager/open_editor`) ist unvermeidbares Bindeglied: ONLYOFFICE
      editiert `ir.attachment`-Datensätze, unsere Dateien liegen roh auf der Platte. In die
      bestehende `openRecord()`-Dispatch-Kette eingehängt (`OFFICE_EDIT_EXTENSIONS`, bewusst ohne
      `txt`/`csv` - die öffnen hier bereits im nativen `CodeEditor`, eine Verbesserung ggü. der
      alten UI, die beim Portieren erhalten bleibt statt zurückgebaut zu werden).
    - **"Lokal öffnen"** (`onOpenLocal`, WebDAV-Protokoll-Handoff an Word/Excel/PowerPoint
      Desktop): 1:1 übernommen, **kein natives Odoo-Äquivalent möglich** - das ist ein
      Windows/Office-eigener URL-Protocol-Handler (`ms-word:ofe|u|...`), keine Odoo-UI-Mechanik.
      Ebenfalls als `int_open_local`-Eintrag im `ActionMenus`, gated auf Dateitypen mit
      Protokoll-Handler (`doc(x)`/`xls(x)`/`ppt(x)`).

    **Live gegen die Testinstanz verifiziert, nicht nur angenommen:**
    - Freigeben: Dialog öffnet, "Link erzeugen" liefert echten Freigabe-Link + Ablaufdatum
      (`action_generate_share_token()` bestätigt durchgelaufen), "Link widerrufen" danach
      erfolgreich getestet.
    - Lokal öffnen: `/int_filemanager/webdav_token` liefert `200 OK` mit echtem Token/URL - der
      `ms-excel:`-Protokoll-Handoff selbst lässt sich im Testkontext nicht prüfen (kein Excel auf
      dem Testrechner installiert), das ist unabhängig vom Code.
    - Bearbeiten: `/int_filemanager/open_editor` liefert `200 OK`, `ir.actions.client` wird
      korrekt ausgelöst und zeigt ONLYOFFICEs **eigene** native Fehlermeldung ("ONLYOFFICE cannot
      be reached") - bestätigt, dass die Weiterleitung bis zum Editor korrekt ankommt; es fehlt
      nur die Document-Server-Anbindung auf der Testinstanz (Infrastruktur, nicht Teil dieser
      Änderung).

    **Damit ist die in Punkt "aktueller Stand" (siehe Konversation) festgestellte Funktionslücke
    zur alten UI geschlossen** - offen bleibt weiterhin ein realer End-to-End-Test gegen HM-SRV
    selbst (bisher ausschließlich gegen die isolierte Tower-Testinstanz verifiziert) und ein
    Abgleich des Deploy-Stands dort, bevor `legacy_ui`/`folder_tree.js`/`.xml` und der
    `/int_filemanager/list`-Endpunkt tatsächlich gelöscht werden (siehe "Empfohlene Reihenfolge",
    Schritt 3).

20. **`legacy_ui` gelöscht (2026-09-04) - native ListView/SearchPanel ist jetzt die einzige UI.**
    Nutzerentscheidung nach Abwägen der verbliebenen Restrisiken (Datenbestand auf Tower als
    strukturell vergleichbar mit HM-SRV eingeordnet, Versions-Sync-Check bewusst verworfen; ACL-
    Interaktion und ONLYOFFICE-Document-Server-Anbindung bleiben als reine
    Infrastruktur/Konfigurations-Restrisiken, kein Code mehr).

    **Gelöscht:** `static/src/int_filemanager/legacy_ui/` komplett (`filemanager_action.js/.xml`,
    `folder_tree.js/.xml`, `inline_tags.js/.xml`, `filemanager.scss`) sowie die dadurch verwaiste
    `/int_filemanager/list`-Route + `_breadcrumbs()`-Helper (`controllers/main.py`) - keine Tests
    hingen daran (per `grep` bestätigt, nicht angenommen). `/int_filemanager/tree` bleibt dagegen
    bewusst stehen: eigene ACL-Sicherheitstests (`test_acl_http.py`,
    `test_tree_hides_protected_folder_name`/`test_tree_shows_protected_folder_name_with_group`)
    belegen die Record-Rule-Durchsetzung auf diesem Pfad, unabhängig davon, ob ihn noch eine UI
    aufruft - Sicherheitstestabdeckung wird hier nicht kommentarlos geopfert, nur weil der
    UI-Konsument weg ist.

    **Zwei echte Abhängigkeiten mussten mitwandern, nicht nur Dateien gelöscht werden:**
    - **Hauptmenü "Dateimanager"** zeigte über den `ir.actions.client`-Tag `int_filemanager_browser`
      (registriert in `filemanager_action.js`) auf die alte UI. `menu.xml` zeigt jetzt direkt auf
      `action_filemanager_file_list_native` (umbenannt von "Dateimanager (nativ, Test)" zu
      schlicht "Dateimanager") - Manifest-`data`-Reihenfolge musste dafür angepasst werden
      (`filemanager_file_list_view.xml` vor `menu.xml`, sonst existiert die referenzierte Action
      beim Parsen des Menüeintrags noch nicht).
    - **"Verknüpfte Dateien"-Smart-Button** auf `res.partner` (`IntFilemanagerLinkableMixin`,
      `filemanager_linkable_mixin.py`) nutzte denselben Tag mit einem `params.domain`, das die
      alte UI automatisch in einen "immer rekursiv"-Modus schaltete
      (`int_filemanager_recursive`-Context-Flag, `filemanager_action.js`). `action_view_int_filemanager_files()`
      öffnet jetzt dieselbe native Action per `ir.actions.act_window._for_xml_id()`
      (live gegen den echten Odoo-19-Quellcode verifiziert, nicht angenommen) mit eigener
      `domain`/`context`. **Ohne Anpassung an `search_model_patch.js` wäre das leer erschienen:**
      die dritte Fallunterscheidung dort (Punkt 3 oben, "rekursiv sobald `this.query.length > 0`")
      greift nur bei einer getippten Suchleisten-Facette, nicht bei einer permanenten
      Action-Domain - `this.query` bliebe hier leer, die Liste würde beim Öffnen nur
      Wurzel-Datensätze zeigen (`parent_id = False`), was bei einem domain-gefilterten
      Smart-Button praktisch immer leer wäre (ein verknüpftes Element liegt so gut wie nie im
      Wurzelverzeichnis). Fix: `_getCategoryDomain()` prüft jetzt zusätzlich
      `this.globalContext.int_filemanager_recursive` - derselbe Context-Key, den die alte UI
      schon für exakt denselben Zweck nutzte, bewusst wiederverwendet statt neu erfunden.

    **Live gegen die Testinstanz verifiziert (nicht nur angenommen):**
    - Modul-Upgrade lief fehlerfrei durch, alte `ir.ui.menu`/`ir.actions.client`-Datensätze
      (`menu_filemanager_native_test`, `action_int_filemanager`) wurden beim Upgrade automatisch
      als verwaist erkannt und entfernt.
    - Hauptmenü "Dateimanager" öffnet direkt die native Liste, kein separater "(nativ, Test)"-
      Eintrag mehr.
    - Smart-Button-Test: Datei testweise mit "My Company" (`res.partner`, id 1) verknüpft (über
      den native `Verknüpfen`-Aktionsmenüpunkt), auf der Kontaktkarte den Button "Verknüpfte
      Dateien" (Zähler korrekt "1") angeklickt - Breadcrumb "My Company / Dateimanager", Liste
      zeigt sofort exakt die eine verknüpfte Datei trotz tiefer Verschachtelung
      (`Programme/SQ-MIDI-Generator.xlsx`), ohne manuell dorthin navigieren zu müssen - bestätigt
      den `int_filemanager_recursive`-Fix. Test-Verknüpfung danach wieder entfernt.
    - Komplette Testsuite erneut in einer frischen, isolierten Datenbank: **0 failed, 0 error(s)
      of 66 tests** - keine Regression durch Routen-Entfernung oder Mixin-Änderung.

    **Damit ist Schritt 3 der "Empfohlenen Reihenfolge" (weiter oben in diesem Dokument)
    abgeschlossen.** Verbleibend laut Nutzerentscheidung: ein realer Durchlauf gegen HM-SRV selbst
    vor dem tatsächlichen Produktiv-Rollout, insbesondere die ACL-/ONLYOFFICE-Interaktion dort -
    das ist aber bewusst außerhalb des Codes/dieses Branches angesiedelt, kein offener
    Implementierungspunkt mehr.

21. **Drag&Drop-Upload umgesetzt (2026-09-05) - Baustein 0 aus
    [int_filemanager_paperoffice_recherche.md](int_filemanager_paperoffice_recherche.md).**
    Auslöser: aktuelle Erfassungs-Praxis (PDF per Drag&Drop aus dem Dateisystem, Anhang aus
    Outlook ziehen, direkt scannen) soll beim Umstieg von PaperOffice nicht verloren gehen.

    **Umsetzung** (`native_list_view.js`/`.xml`/`.scss`): `window`-weite `dragenter`/`dragleave`/
    `dragover`/`drop`-Listener (`useExternalListener` aus `@odoo/owl` - nicht `@web/core/utils/
    hooks`, live gegen den Odoo-19-Quellcode verifiziert, wo die Funktion tatsächlich lebt) statt
    einer einzelnen Drop-Zone - robust gegenüber der genauen DOM-Struktur des von `web.ListView`
    geerbten Templates. Tiefenzähler statt Boolean gegen das erwartete Flackern beim Überqueren
    von Kindelementen (dragenter/dragleave feuern pro Element). `dataTransfer.types.includes
    ("Files")` filtert echte Datei-Drags von anderen Drag-Interaktionen heraus. Rein visuelles
    Overlay (`position: fixed`, `pointer-events: none`) - das eigentliche Hochladen läuft über
    denselben, bereits vorhandenen `this.fileUpload.upload(...)`-Pfad wie der bestehende
    "Hochladen"-Button (gemeinsame `_uploadFiles()`-Methode, kein zweiter Code-Pfad).

    **Dabei ein echter, vorbestehender Bug gefunden und behoben** (unabhängig von Drag&Drop -
    betraf auch den bestehenden "Hochladen"-Button, live an einem 500er nachgewiesen, nicht nur
    vermutet): `controllers/main.py`, `upload()`-Handler, Zeile `f.save(target)` übergab einen
    Pfad-String an `werkzeug.FileStorage.save()`. Dieser Odoo-Build monkeypatcht `.save()`
    (`odoo/_monkeypatches/werkzeug.py`: `FileStorage.save = lambda self, dst, ...:
    copyfileobj(self.stream, dst, ...)`) und verlangt dadurch zwingend ein bereits offenes
    Dateiobjekt statt eines Pfad-Strings, anders als Werkzeugs eigene Komfortvariante. Fix:
    `with open(target, "wb") as dst: f.save(dst)` - exakt das Muster, das Odoos eigener Code
    an der einzigen vergleichbaren Stelle im Kern selbst verwendet (`web/controllers/
    database.py`: `with tempfile.NamedTemporaryFile(...) as data_file: backup_file.save
    (data_file)`).

    **Live verifiziert:** Overlay erscheint/verschwindet korrekt bei einem synthetischen
    `dragenter`/`drop`-Event mit echter `File`-Payload (echter OS-Drag aus Explorer/Outlook lässt
    sich aus einer Remote-Browser-Session heraus nicht auslösen - das bleibt ein Test, den nur ein
    Nutzer im echten Browser machen kann). Vor dem Fix: `AttributeError: 'str' object has no
    attribute 'write'`. Nach dem Fix: derselbe Testupload schlägt nur noch am bewusst
    read-only gemounteten `/mnt/hm-daten` der Testinstanz fehl (`OSError: [Errno 30] Read-only
    file system`) - der eigentliche Bug ist damit nachweislich behoben, der verbleibende Fehler
    ist die eigene, gewollte Schreibschutz-Einstellung dieser Testinstanz, kein Defekt.

    **Offener Punkt, bewusst nicht in dieser Session geklärt:** ob ein Drag aus der konkret
    eingesetzten Outlook-Version tatsächlich als echtes Datei-Drag beim Browser ankommt
    (versionsabhängig - klassisches Desktop-Outlook vs. neues Outlook/WebView2 vs. OWA), lässt
    sich nur mit einem echten Nutzer-Test klären.

22. **Baustein 1 umgesetzt (2026-09-05): Volltextsuche (OCR/Textlayer) + interaktiver
    Kontroll-Dialog** ([int_filemanager_paperoffice_recherche.md](int_filemanager_paperoffice_recherche.md)).
    Auslöser: bei PaperOffice wird eine reingezogene Datei direkt per OCR erkannt, die erkannten
    Werte lassen sich vor der Übernahme kontrollieren - reines Hintergrund-Volltextindizieren
    (der ursprüngliche Baustein-1-Entwurf) hätte das nicht abgebildet.

    **Architektur - Muster von `mediameta.py`/`_cron_extract_media_meta` 1:1 gespiegelt:** neue
    Datei `fulltext.py` (`fulltext_type_of()`-Dispatch, `extract_fulltext()` mit derselben
    Stable-Read-Garantie wie `mediameta.extract_metadata()`), eigener `ocr_state` (nicht
    `meta_state` wiederverwendet - anderer Kostenrahmen), neuer Cron `_cron_extract_fulltext()`.
    Bewusste Abgrenzungen ggü. dem ursprünglichen Recherche-Entwurf: **nur PDF + reine
    Textformate** in v1 (Office-Dokumente/Bilder wären Baustein 1b - Bilder bewusst nie
    automatisch, sonst OCR über private Fotos statt Scans); **zweistufige PDF-Behandlung**
    (Textlayer zuerst per `PdfReader`, OCR via `pytesseract`/`pdf2image` nur wenn <20 Zeichen/Seite
    - digital erzeugte PDFs sparen sich damit den teuren Schritt komplett); **kein Backfill** für
    bereits bestehende Dateien (Nutzerentscheidung) - nur ab jetzt neu ankommende/geänderte Dateien
    (`index_utils.py`) bzw. manuell ausgewählte (siehe unten).

    **Zwei Erfassungswege, unterschiedlich behandelt** (deckt sich mit den zwei in Baustein 0
    beschriebenen Gewohnheiten):
    - **Pfad A (Drag&Drop/Upload in die App):** nach dem Upload synchron `POST
      /int_filemanager/analyze_document` pro Datei (neue Route + `action_analyze_document()`,
      `@api.model`) - OCR blockierend fürs UI ist hier bewusst in Ordnung, es geht um eine Datei in
      einer Nutzerinteraktion, nicht um einen Massenlauf. Ergebnis geht in einen neuen Dialog
      (`IntDocumentReviewDialog`, `native_ui/document_review_dialog.js/.xml`) - eine Datei nach der
      anderen bei Mehrfach-Upload (Nutzerentscheidung), `dialog.add(..., {onClose: resolve})` als
      Wartepunkt zwischen den Dateien. "Übernehmen" schreibt per normalem `this.orm.write()` -
      bewusst kein `sudo()`/Custom-Endpoint dafür, das sind reine Feldänderungen
      (`tag_ids`/`res_reference`/`extracted_*`), keine Dateisystem-Operation, laufen also korrekt
      über dieselben `ir.rule`-Regeln wie jede andere Bearbeitung am Datensatz.
    - **Pfad B (Scan-Eingangsordner):** der Hintergrund-Cron, niemand da zum Bestätigen. Dient
      gleichzeitig als Sicherheitsnetz für Pfad A, falls der Dialog übersprungen wird (`ocr_state`
      bleibt dann `pending`, Cron holt es nach). Beide Pfade rufen denselben Kern
      (`_extract_fulltext_for_record()`) auf, nur zu unterschiedlichen Zeitpunkten ausgelöst.
    - **Zusätzlich: manueller Auslöser für Bestandsdateien** ("Werte erkennen", neuer
      `ActionMenus`-Eintrag, gleiches Muster wie "Freigeben"/"Lokal öffnen") - da kein Backfill
      läuft, sonst gäbe es für alte Dateien keinen Weg zur interaktiven Erkennung.

    **Werterkennung per einfacher Regex/Bestandsabgleich** (Nutzerentscheidung 2026-09-05, keine
    LLM-Anbindung): Tags nur aus bereits existierenden `int_filemanager.tag`-Namen (kein Erfinden
    neuer Tags), Kontakt aus Abgleich gegen existierende `res.partner`-Namen im Text (Treffer
    schlägt vor, `res_reference` zu setzen - nutzt die Verknüpfungs-Logik einfach in die andere
    Richtung), Datum/Rechnungsnr./Betrag per Regex. Nichts davon wird automatisch geschrieben -
    erst "Übernehmen" im Dialog schreibt tatsächlich.

    **Echter Bug im eigenen neuen Code gefunden und sofort behoben, live nachgewiesen:**
    `_extract_fulltext_for_record(self, rec, root=None)` hatte `rec` fälschlich als eigenen
    Parameter UND wurde als Instanzmethode aufgerufen (`rec._extract_fulltext_for_record()`) - der
    Analyse-Endpunkt schlug mit `TypeError: missing 1 required positional argument: 'rec'` fehl.
    Fix: `rec`-Parameter entfernt, `self` ist bereits der Datensatz (Methodenkörper nutzte intern
    ohnehin schon durchgehend `self`, nur die Signatur war falsch).

    **Neue Abhängigkeiten, System- nicht nur Python-Pakete (Dockerfile erweitert):**
    `tesseract-ocr`/`tesseract-ocr-deu`/`poppler-utils` (apt) + `pytesseract`/`pdf2image` (pip) -
    laufen alle in-process in derselben Odoo-Instanz, kein separater Dienst/Container nötig
    (`pytesseract` ruft `tesseract` einfach per `subprocess` auf, wie `mutagen`/`Pillow` auch
    lokal arbeiten). Image neu gebaut, `tesseract --version` im Container bestätigt (5.3.4).

    **Live komplett Ende-zu-Ende verifiziert** (Testinstanz auf Tower, temporär auf einen
    beschreibbaren Testordner umgeschaltet, da `/mnt/hm-daten` bewusst read-only ist - danach
    wieder zurückgesetzt): Testdatei mit Inhalt, der alle Muster gleichzeitig trifft (bestehender
    Tag "dfgdfg", bestehender Kontakt "My Company", Datum, Rechnungsnr., Betrag) per synthetischem
    Drop hochgeladen - Dialog zeigte alle fünf Vorschläge korrekt. "Übernehmen" geklickt, per SQL
    verifiziert: `tag_ids`, `res_reference=res.partner,1`, `extracted_date`,
    `extracted_invoice_number`, `extracted_amount`, `content_text` alle korrekt gespeichert.
    Zusätzlich über den manuellen "Werte erkennen"-Button denselben Dialog für eine
    Bestandsdatei ausgelöst - identisches Ergebnis. Volltextsuche nach "Gesamtbetrag" (Wort kommt
    nur im Dateiinhalt vor, nicht in Name/Tags) fand die Datei korrekt - bestätigt die
    Sucheinbindung ohne jede JS-Änderung. Komplette Testsuite in isolierter DB weiterhin **0
    failed, 0 error(s) of 66 tests** - keine Regression durch die neuen Felder/Route/Cron.

23. **Baustein 2 umgesetzt (2026-09-06): `mail.thread`/`mail.activity.mixin`-Vererbung**
    ([int_filemanager_paperoffice_recherche.md](int_filemanager_paperoffice_recherche.md)).
    Günstigster Baustein im ganzen Vorschlag - drei PaperOffice-Features (Aufgabenverwaltung mit
    Fristen, Notizen, Audit-Trail) auf einmal, rein durch Odoo-Bordmittel: `_inherit =
    ["mail.thread", "mail.activity.mixin"]` auf `int_filemanager.file` (`filemanager_file.py`),
    `"mail"` als neue Modul-Abhängigkeit (`__manifest__.py` - war bisher nur transitiv über
    `bus`/`portal` vorhanden, jetzt explizit), `<chatter/>` nach `</sheet>` in
    `filemanager_file_form_view.xml` (Platzierung 1:1 aus Odoos eigenem `mail_blacklist_views.xml`
    übernommen, nicht geraten). Kein neues Modell, kein neuer Controller, keine eigene
    UI-Komponente.

    **Live verifiziert (Tower-Testinstanz):** Modul-Upgrade sauber ohne Fehler durchgelaufen,
    Chatter erscheint auf der vollen Formularseite (`/odoo/int_filemanager.file/<id>`) unterhalb
    des Formulars mit "Send message"/"Log note"/"Activity". Funktional getestet: eine interne
    Notiz geloggt (im Chatter-Verlauf sichtbar, Audit-Trail funktioniert), eine To-Do-Aktivität
    geplant und wieder storniert (Fristverwaltung funktioniert).

    **Zwischenzeitliche Verwirrung, aufgeklärt statt als Bug behandelt:** über den Pfeil-Button
    in der nativen Liste (öffnet den Datensatz im `FormViewDialog`-Modal, `native_list_view.js`)
    erscheint **kein** Chatter - das ist kein Fehler in dieser Erweiterung, sondern
    Odoo-Kernverhalten für jedes Modell mit `mail.thread`: `mail/static/src/chatter/web/
    form_compiler.js` setzt hart `"t-if": "!__comp__.env.inDialog"` auf den Chatter-Container,
    d.h. der Chatter wird in jedem Odoo-Formular-Dialog systemweit unterdrückt, nicht nur hier.
    Am echten Odoo-19-Quellcode verifiziert statt vermutet, bevor es fälschlich als eigener Bug
    behandelt worden wäre.

    **Folgearbeit (2026-09-06): einklappbares Chatter-Seitenpanel für die Listenansicht**, da der
    Pfeil-Button/Dialog wegen genau dieser `env.inDialog`-Sperre keinen Chatter zeigen kann und es
    sonst keinen UI-Weg zu Notizen/Aktivitäten gab (nur die direkte URL zur vollen Formularseite).
    Nutzerwunsch: standardmäßig zu, Toggle in der Toolbar, keine feste Platzverdrängung der
    bestehenden Spalten. Umsetzung in `native_list_view.js/.xml/.scss`:
    - Toolbar-Icon-Button (`oi-panel-right`, dasselbe Icon wie der native Ordnerbaum-Ein-/
      Ausklapp-Button links - Wiedererkennbarkeit statt Neuerfindung) schaltet `chatterState.open`.
    - Bewusst ein überlagerndes `position: fixed`-Panel statt eines echten, Platz verdrängenden
      Flex-Layouts neben der Liste: Letzteres hätte einen Patch auf Odoos geteiltem
      `web.Layout`-Template gebraucht (`main.o_content` liegt innerhalb von Layouts eigenem
      Template, nicht im hier geerbten `web.ListView`) - global auf jede Listen-/Kanban-Ansicht im
      System wirksam, für ein Panel das nur dieser eine Dateimanager braucht unverhältnismäßig
      riskant. Stattdessen wird `top` per `getBoundingClientRect()` auf `.o_content` vermessen
      (bei jedem Öffnen und bei `resize`), damit das Panel exakt unterhalb der eigenen
      Toolbar/Breadcrumb-Zeile beginnt statt Suche/Pager/Buttons zu verdecken - kein geratener
      Navbar-Höhen-Wert.
    - Angezeigter Datensatz = erste markierte Zeile (`this.model.root.selection[0]`, dieselbe
      Auswahl wie die bestehenden Mehrfachaktionen/`getStaticActionMenuItems()`) - reaktiv, kein
      eigener Auswahlmechanismus. Leerzustand mit Hinweistext, wenn nichts markiert ist.
    - `Chatter` (`@mail/chatter/web_portal/chatter`, dieselbe Komponente, die Odoo intern in jedem
      Formular verwendet) direkt eingebunden (`static components = {...ListController.components,
      Chatter}`, `threadModel="int_filemanager.file"`, `threadId=<resId>`), nicht über ein
      Formular-Arch - dafür ist kein `<chatter/>`-Tag nötig, die Komponente funktioniert auch
      freistehend.

    **Live verifiziert (Tower):** Panel öffnet/schließt über den Toolbar-Toggle, positioniert
    korrekt unterhalb der Toolbar (Suche/Pager bleiben bedienbar, keine Überdeckung). Notiz direkt
    im Panel geloggt und im Chatter-Verlauf sichtbar. Auswahlwechsel (anderes Kontrollkästchen)
    aktualisiert den angezeigten Thread live, ohne das Panel neu zu öffnen. Leerzustand bei
    aufgehobener Auswahl korrekt. Funktioniert identisch für Ordner- und Dateizeilen (beide sind
    `int_filemanager.file`-Datensätze mit demselben Mixin). Keine Konsolen-/Server-Fehler während
    des gesamten Tests.

    **Nutzerfeedback nach dem ersten Test (2026-09-06):** Toggle-Button links bei den
    Erfassungs-Buttons (Neuer Ordner/Hochladen) schlecht platziert. Verschoben in
    `control-panel-navigation-additional` - denselben nativen Slot, in dem Odoo selbst den
    Filter/Gruppieren-Toggle direkt neben dem Pager rendert (`control_panel.xml`,
    `.o_control_panel_navigation`). Erneut live verifiziert (Tower) - Funktion unverändert, nur
    Position rechts außen neben "1-38/38".

    **Nebenbefund beim Log-Check nach der Verifikation, nicht Teil dieses Bausteins:** der
    bestehende Hash-Cron (`_cron_compute_hashes`) schlägt für eine reale Datei >2 GB mit
    `psycopg2.errors.NumericValueOutOfRange` fehl, weil `hash_size` als `fields.Integer` (int4,
    Cap ~2,1 GB) deklariert ist - derselbe Fallstrick, den `size` (im selben Model) mit `Float`
    bereits bewusst umgeht. Als separater Task geflaggt (nicht in dieser Session mit erledigt, da
    unabhängig von Baustein 2 und eigenständige Product-/Migrationsentscheidung: DB-Spaltentyp-
    Änderung an einer Tabelle mit ~87k Zeilen).

24. **Baustein 4 umgesetzt (2026-09-06): Ampel-Freigabe über `state_selection`**
    ([int_filemanager_paperoffice_recherche.md](int_filemanager_paperoffice_recherche.md)). Neues
    Feld `state` auf `int_filemanager.file` (`fields.Selection`, Werte `normal`/`blocked`/`done` -
    bewusst Odoos eigene `kanban_state`-Konvention übernommen, nicht frei erfunden: das native
    `state_selection`-Widget (`web/static/src/views/fields/state_selection/
    state_selection_field.js`) färbt **nur genau diese beiden Sonderwerte** ein (`blocked`=rot,
    `done`=grün), jeder andere technische Wert bliebe grau - am Quellcode geprüft, bevor eigene
    Werte gewählt wurden, sonst wäre die Ampel unbemerkt farblos geblieben). `tracking=True` dazu -
    jede Statusänderung landet automatisch im Chatter (Baustein 2), ganz ohne Zusatzcode; reine
    Synergie zwischen beiden Bausteinen.

    **Zwischenzeitlicher Irrtum, aufgeklärt statt übernommen:** ein vom Nutzer gezeigter
    Screenshot (Pill-Badge + individuelle Icons pro Status inkl. Gelb, aus einer Odoo-Projekt-Task-
    Formularseite) sah nach einem reicheren nativen Widget aus, das man einfach wiederverwenden
    könnte - am Quellcode geprüft (`project/static/src/components/project_task_state_selection/`):
    ist tatsächlich natives Odoo, aber ein **eigenes Widget des `project`-Moduls**, dessen Icon-/
    Farbzuordnung hart auf `project.task`s eigene Statuswerte kodiert ist (`01_in_progress` usw.) -
    nicht generisch wiederverwendbar auf ein fremdes Modell. Wäre als eigene Widget-Klasse nach
    diesem Vorbild machbar gewesen, aber echter Zusatzaufwand statt reiner Wiederverwendung -
    Nutzerentscheidung 2026-09-06: stattdessen das generische, sofort einsetzbare
    `state_selection` (Punkt statt Pill-Badge, kein individuelles Icon pro Status).

    UI-Platzierung: Listenspalte direkt nach dem Öffnen-Pfeil (`nolabel="1"`, kein eigener
    Button/eigene Komponente nötig - der Punkt selbst ist per Klick änderbar), zusätzlich im
    Formular. Suchleiste um zwei Filter (`Rückfrage`/`Freigegeben`) und eine Gruppierung
    (`Freigabestatus`) ergänzt, rein deklarativ, kein JS.

    **Live verifiziert (Tower):** Modul-Upgrade sauber durchgelaufen, alle ~87.053 Bestandszeilen
    per SQL bestätigt auf `state='normal'` befüllt (Odoos `_auto_init` backfillt den Python-Default
    für neue Spalten bei bestehenden Zeilen automatisch - am echten Verhalten geprüft, nicht
    angenommen). Punkt-Farbe/Dropdown funktionieren wie erwartet (grau/rot/grün), Klick auf
    "Freigegeben" färbt den Punkt sofort grün um. Tracking bestätigt: die Änderung erscheint als
    eigener Eintrag im Chatter-Panel ("Offen → Freigegeben (Freigabestatus)"). Keine neuen
    Server-/Konsolen-Fehler (die einzigen geloggten Fehler während des Tests waren dieselben
    bereits bekannten, unabhängigen `mail_presence`-Serialisierungskonflikte beim
    Container-Neustart).

25. **Baustein 4 umgebaut (2026-09-06): `state`-Selection → frei konfigurierbares
    `int_filemanager.status`-Modell.** Nutzerwunsch: Freigabestatus-Werte sollen sich über einen
    Menüpunkt anlegen/umbenennen/farblich anpassen lassen, ohne Code-Änderung - mit dem hart
    kodierten Selection-Feld aus Punkt 24 nicht möglich (Werte stehen im Python-Code, und
    `state_selection` färbt ohnehin nur die zwei Sonderwerte `blocked`/`done` ein, siehe dort).

    **Architektur - Muster von `int_filemanager.tag` uebernommen** (`name` + `color`, dieselbe
    Odoo-Farbpalette): neues Modell `int_filemanager.status` (+ `sequence` fürs Umsortieren,
    `widget="handle"`), eigene Konfigurationsseite "Dateimanager > Freigabestatus-Werte"
    (`filemanager_status_views.xml`, admin-only wie "Geschützte Ordner" - normale Nutzer haben nur
    Lesezugriff, siehe `ir.model.access.csv`). Auf `int_filemanager.file`: `state` (Selection)
    ersetzt durch `status_id` (Many2one) + `status_color` (related Integer, reines Hilfsfeld).
    Anzeige über das native `badge`-Widget (`web/static/src/views/fields/badge/badge_field.js`,
    `options="{'color_field': 'status_color'}"`) - unterstützt beliebige Farben aus der vollen
    12-Farben-Palette (`ColorList.COLORS`, am Quellcode geprüft), nicht nur Rot/Grün.

    **Bewusst in Kauf genommener Nachteil, vorher mit dem Nutzer geklärt statt stillschweigend
    verbaut:** `badge` ist rein lesend (`badge_field.xml`: nur `<span t-esc>`, keine
    Klick-/Editier-Logik) - anders als `state_selection` lässt sich der Status jetzt **nicht**
    mehr direkt in der Liste per Klick ändern, nur noch über das Formular (Pfeil-Button-Dialog
    oder volle Seite). Alternative (eigene Klickbarkeit nach `inline_tags.js`-Vorbild) wurde
    besprochen und explizit zugunsten der einfacheren Lösung verworfen.

    **Datenmigration, nicht nur Backfill:** `migrations/19.0.1.6.0/
    post-migrate_state_to_status.py` mappt die ~87k Bestandszeilen von den alten Textwerten
    (`normal`/`blocked`/`done`) auf die IDs der drei per `data/filemanager_status.xml`
    mitgelieferten Standard-Status (dieselben External IDs, damit `env.ref()` im Feld-Default
    funktioniert). `post-migrate` (nicht `pre-`): läuft erst nachdem die Status-Datensätze aus
    `data/` schon geladen sind. Modul-Version deshalb auf `19.0.1.6.0` angehoben, sonst hätte Odoo
    das Skript beim Upgrade nicht ausgeführt.

    **Live verifiziert (Tower):** erster Upgrade-Versuch schlug mit `could not serialize access`
    fehl, weil der Hauptcontainer parallel weiterlief (derselbe bekannte Konflikttyp wie beim
    `mail_presence`-Nebeneffekt) - sauber zurückgerollt (per SQL bestätigt: kein Teilzustand),
    Hauptcontainer gestoppt, Upgrade danach fehlerfrei. Per SQL bestätigt: 87.053 Zeilen →
    "Offen", 1 Zeile (aus einem früheren Test) → "Rückfrage", 0 NULL-Werte. Im Browser:
    Konfigurationsseite zeigt alle drei Status mit korrekter Farb-Vorschau; neuer eigener Status
    "In Prüfung" (Orange) angelegt, taucht sofort im Dropdown auf der Datei auf, Badge in der
    Liste zeigt die korrekte Farbe - kompletter Kreis von "Wert anlegen" bis "sichtbar in der
    Liste" ohne jede Code-Änderung bestätigt. Admin-Menüpunkte ("Geschützte Ordner",
    "Freigabestatus-Werte") waren anfangs nicht sichtbar, weil der Test-Login nie in
    `group_filemanager_admin` war (nicht durch diese Änderung verursacht) - nach Gruppenzuweisung
    und Neustart (ORM-Gruppen-Cache reagiert nicht auf rohe SQL-Writes) sichtbar; die
    Zweitzeilen-Menüleiste selbst rendert erst nach Direktaufruf der jeweiligen Action-URL, nicht
    beim Wechsel per Klick innerhalb derselben Session - rein clientseitige Owl-Eigenheit, keine
    Server-/Datenkorrektheitsfrage (per `load_menus`/`has_group`-RPC direkt verifiziert).

    **Nachbesserung (2026-09-06), Nutzerwunsch:** Feld/Spalte von "Freigabestatus" auf schlicht
    "Status" umbenannt (`status_id`-`string`) - die Werte sind seit obigem Umbau frei
    konfigurierbar, das Feld ist nicht mehr zwingend an einen Freigabe-Workflow gebunden. Dabei
    auch nachgefragt, ob eine reine DB-Umbenennung über Odoo Technical Settings reichen würde -
    am Code verifiziert (`ir_model.py`, `_reflect_fields`), dass Odoo `field_description` bei
    jedem Modul-Upgrade unbedingt aus dem Python-`string` neu synchronisiert (`upsert_en` bei
    jeder Abweichung) - eine manuelle Umbenennung dort wäre beim nächsten Upgrade kommentarlos
    verloren gegangen. Deshalb im Code umbenannt, nicht nur in der DB. Zusätzlich die beiden
    Admin-Bildschirme ("Geschützte Ordner", "Status") unter einem neuen "Konfiguration"-Menüpunkt
    gebündelt statt zwei flacher Einträge direkt unter "Dateimanager" (`menu.xml`, neuer
    `menu_int_filemanager_configuration`).

26. **Umbenennen direkt im Formular (2026-09-06), Nutzerwunsch.** `name` war bisher `readonly="1"`
    im Formular (Pfeil-Button-Dialog) - Grund: das Feld ist nur ein Spiegel des echten
    Dateisystem-Zustands, eine reine `write()` auf die Spalte hätte den DB-Datensatz von der
    echten Datei entkoppelt (Downloads/Vorschau/ONLYOFFICE wären ins Leere gelaufen) und dabei die
    sicherheitsrelevanten Authz-Prüfungen umgangen, die bisher nur in der `/int_filemanager/rename`-
    Route lagen (`authz.require`/`authz.require_rename_or_move_allowed` - verhindert u.a.
    Umbenennen über Schutzordner-Grenzen hinweg).

    **Umbau statt Feld-Attribut-Flip:** die eigentliche Rename-Logik (Pfad auflösen, beide
    Authz-Checks, `os.rename`, `index_move_tree`) aus der Route in eine neue gemeinsame Funktion
    `rename_entry(env, old_rel, new_name)` (`index_utils.py`) gezogen. Sowohl die Route
    (`controllers/main.py`, jetzt nur noch ein Aufruf) als auch ein neues `write()`-Override auf
    `int_filemanager.file` (`models/filemanager_file.py`) rufen ausschließlich diese eine Funktion
    auf - keine zweite, driftgefährdete Kopie der Sicherheitsprüfungen. "Umbenennen" in der Toolbar
    bleibt zusätzlich bestehen (Nutzerwunsch), ruft jetzt intern dieselbe Funktion.

    **Der eigentliche Frickel-Punkt, sauber gelöst statt ignoriert:** `rename_entry()` schreibt am
    Ende selbst wieder `name` zurück (über `index_move_tree()`, um Pfad/Elternordner im Index
    nachzuziehen) - ohne Gegenmaßnahme hätte `write()` das als weiteren Rename-Auftrag
    missverstanden (Endlosschleife/falscher-alter-Pfad-Fehler). Gelöst über einen expliziten
    Kontext-Guard (`int_filemanager_syncing_index`), den jede reine Index-Nachpflege setzen muss,
    die `name` mitschreibt, ohne eine echte Rename-Absicht zu haben. Betraf am Ende **vier**
    Stellen, nicht nur eine - alle beim Review gefunden und abgesichert, nicht erst live entdeckt:
    `rename_entry()` selbst, `index_upsert()` (Watcher-CREATE/MODIFY auf unverändertem Pfad),
    und zwei Stellen in der Scan-Identitätserkennung/Vollscan-Reconciliation
    (`_scan_and_reconcile`), die `name` beim Wiederfinden einer bereits bekannten Datei ebenfalls
    zurückschreiben. Ohne den Guard hätte z.B. jede Watcher-Inhaltsänderung oder jeder tägliche
    Scan-Lauf unnötig `rename_entry()` samt Authz-Checks ausgelöst - im schlimmsten Fall mit einem
    `AccessError` für Dateien in einem Schutzordner, obwohl nur der Inhalt geändert wurde.

    **Formular-Gruppe:** `readonly="1"` beim `name`-Feld entfernt - dank der bereits
    zusammengelegten Gruppe (Punkt davor) bleibt die Zeile bündig mit den anderen.

    **Live verifiziert (Tower), inkl. Regressionstest:** komplette Testsuite in isolierter CI-DB
    weiterhin **0 failed, 0 error(s) von 88 Tests** (inkl. der bestehenden ACL- und
    Scan-Identitäts-Tests, die genau die geänderten Codepfade abdecken). Danach live gegen einen
    temporär umgeschalteten, beschreibbaren Testordner (nie gegen `/mnt/hm-daten`, das ist
    read-only): Name im Formular geändert und gespeichert - echte Datei auf der Platte tatsächlich
    umbenannt (per `ls` bestätigt, nicht nur die DB-Spalte). Bestehendes "Umbenennen" in der
    Toolbar funktioniert unverändert (derselbe gemeinsame Funktionsaufruf).

    **Nebenbefund, kein Bug in dieser Änderung:** beim Testen beobachtet, dass der Datei-Watcher
    gelegentlich mit einer interaktiven Umbenennung um denselben Datensatz konkurriert
    (`could not serialize access due to concurrent update`, watcher-seitig geloggt und verworfen,
    DB-Endzustand korrekt) - ein bereits bestehendes, self-healing Verhalten (Watcher-Ereignis
    schlägt fehl, das tägliche Sicherheitsnetz gleicht es notfalls ab), unabhängig davon ob die
    Umbenennung über die Route oder `write()` ausgelöst wurde.

    **Eigener Fehler bei der Live-Verifikation, vollständig behoben:** beim Aufsetzen des
    beschreibbaren Testordners wurde versehentlich der tägliche Sicherheitsnetz-Scan manuell
    ausgelöst, während `root_path` noch auf den Testordner zeigte - dessen Stale-Erkennung
    (`_scan_and_reconcile`) hat daraufhin alle ~87.000 echten Indexeinträge als "nicht mehr
    vorhanden" gewertet und gelöscht. Die echten Dateien selbst waren nie betroffen (nur lesend
    gemountet, per `find` bestätigt unversehrt) - nach Zurückschalten von `root_path` und einem
    erneuten, korrekten Scan war der Index mit ~87.054 Zeilen wiederhergestellt. Nicht
    wiederherstellbar: jegliche zuvor gesetzten `tag_ids`/`status_id`/Chatter-Notizen/Freigabe-Links
    auf einzelnen Dateien (alle Zeilen sind fachlich neu angelegt, nicht die alten mit ID-Erhalt).
    Siehe [[reference_tower_odoo_test_instance]] für die daraus gezogene, dauerhafte
    Arbeitsanweisung (nie den Scan manuell auslösen, während `root_path` versetzt ist).

27. **Ordner-/Datei-Typ-Icon in der Name-Spalte (2026-09-07), Nutzerwunsch.** Vorher reiner Text,
    kein Icon weder für Ordner noch für Dateien. Recherche vor der Umsetzung: Odoo hat kein
    fertiges Feld-Widget dafür, aber zwei wiederverwendbare native Bausteine.

    **Baustein 1 - Odoos eigenes Mimetype-Icon-Set** (`web/static/img/mimetypes/*.svg`: pdf,
    document, spreadsheet, presentation, image, video, audio, archive, text, web_code, unknown,
    ...), angesprochen rein über CSS-Attribut-Selektoren auf `data-mimetype`
    (`web/static/src/scss/mimetypes.scss`, z.B. `&[data-mimetype*='spreadsheet']` - ein
    Teilstring reicht, kein echter MIME-Type nötig). Geprüft: **kein Ordner-Icon** in diesem Set
    (nur für Anhänge/Dateien gedacht) - dafür stattdessen dasselbe `fa-folder` wie im Ordnerbaum
    links (`filemanager_file_search.xml`, `searchpanel icon="fa-folder"`), für Konsistenz.

    **Baustein 2 - Odoos Muster für "Icon + Feldwert in einer Zelle"**: eigenes kleines
    Feld-Widget in der `fields`-Registry, nach Vorbild von `many2one_avatar` (`web/static/src/
    views/fields/many2one_avatar/`) - dort Avatar-Bild + Wert nebeneinander in einem
    `d-flex`-Container, hier analog Icon + Dateiname. Neue Dateien `name_icon_field.js`/`.xml`,
    registriert als Widget `int_filemanager_name`, `<field name="name"
    widget="int_filemanager_name"/>` in `filemanager_file_list_view.xml`.

    **Bewusst clientseitig, kein neues Backend-Feld:** Endung→Icon-Kategorie-Zuordnung
    (`EXT_TO_PSEUDO_MIMETYPE` in `name_icon_field.js`) läuft rein in JS aus dem bereits geladenen
    `name`-Wert - keine neue Spalte, keine Migration, keine zusätzliche Query (Performance vorher
    explizit durchdacht: `mimetypes.guess_type()` wäre serverseitig ebenfalls trivial billig
    gewesen, aber clientseitig noch günstiger, da komplett ohne Backend-Änderung). Unbekannte
    Endungen (z.B. `.exe`, `.asd`) fallen bewusst auf Odoos generisches `unknown.svg` zurück,
    kein Fehlerfall.

    **CSS-Größenanpassung:** Odoos `.o_image` ist mit 38×38px für eigenständige
    Anhang-Vorschaukacheln gedacht, hier nur als kleines Präfix-Icon vor dem Namen - auf 20×20px
    verkleinert, gescopet auf `.o_int_filemanager_name_cell` (`native_list_view.scss`), keine
    globale Änderung an Odoos eigener Klasse.

    **Live verifiziert (Tower):** Ordner zeigen das gelbe `fa-folder`-Icon, Bilder (`.jpg`) das
    Bild-Icon, `.pdf` das rote PDF-Icon, `.mp3` das Audio-Icon, `.html` das Web-Code-Icon -
    unbekannte Endungen (`.exe`, `.asd`, `.paw3`, `.dnt`) korrekt auf das generische Fallback-Icon.
    Keine Konsolen-/Server-Fehler.

28. **Menschlich lesbare Größenanzeige in der Liste (2026-09-07), Nutzerwunsch.** Vorher rohe
    Byte-Zahl (z.B. "816965"). Recherchiert, bevor umgesetzt: Odoo hat dafür bereits eine
    fertige interne Formatierung - `humanSize()` (`web/static/src/views/fields/formatters.js`),
    die jede `Binary`-Feld-Größe im ganzen System genauso zeigt ("12.34Mb"/"700Mb"/"512 Bytes",
    via `humanNumber()` mit `decimals: 2` - überflüssige Nachkommastellen fallen automatisch weg,
    kein eigenes Rundungsverhalten erfunden). Direkt wiederverwendbar war sie aber nicht:
    `formatBinary()`/`humanSize()` erwarten Base64-Daten oder Odoos eigenen `bin_size`-Platzhalter-
    String, keine rohe Zahl - unser `size` ist bewusst `fields.Float` (int4-2GB-Limit, siehe
    Kommentar dort), keine Binary-Spalte.

    **Lösung:** neues kleines Feld-Widget `size_human_field.js`/`.xml` (Widget-Key
    `int_filemanager_size`), das dieselbe Logik mit dem oeffentlich exportierten Kern-Baustein
    `humanNumber()` (`web/core/utils/numbers.js`) 1:1 nachbildet, nur fuer eine rohe Zahl statt
    eines Binary-Werts. Nur die Liste betroffen (`widget="int_filemanager_size"
    string="Größe"` in `filemanager_file_list_view.xml`) - das Formular zeigt bewusst weiterhin
    die exakte Byte-Zahl unter "Größe (Bytes)", unveraendert, fuer Faelle wo der genaue Wert
    gebraucht wird.

    **Live verifiziert (Tower):** Liste zeigt z.B. "816.97kb"/"5.30Mb"/"6.95Mb" statt roher
    Zahlen, Formular zur selben Datei zeigt weiterhin "816.965" exakt - beide konsistent
    zueinander. Keine neuen Fehler (der einzige geloggte Fehler war der bereits bekannte,
    unabhaengige `hash_size`-int4-Overflow-Bug, siehe Punkt 23).

29. **"Neuer Ordner"/"Hochladen" unter einem "Neu"-Dropdown gebündelt (2026-09-07),
    Nutzerwunsch.** Vorher zwei einzelne nebeneinanderstehende Buttons. Umgesetzt mit Odoos
    generischem `Dropdown`/`DropdownItem`-Paar (`web/core/dropdown/`) - demselben Baukasten,
    den Odoo selbst fuer dieses Toggle-plus-Menue-Muster nutzt (z.B. `control_panel.xml`,
    `SearchBarMenu`/`embeddedActionsDropdown`). Toggle-Button jetzt "Neu" mit
    `o-dropdown-caret` (natives Karet-Icon), Inhalt zwei `DropdownItem`s ("Neuer Ordner"/
    "Hochladen") mit `onSelected="..."` - schliesst das Dropdown nach Auswahl automatisch
    (Default-`closingMode` von `DropdownItem`), kein eigener Zusatzcode dafuer noetig. Die
    beiden Handler-Methoden (`onNewFolder`/`triggerUpload`) unveraendert wiederverwendet, nur
    die Toolbar-Struktur geaendert (`native_list_view.xml`), `Dropdown`/`DropdownItem` dafuer
    in `static components` registriert (`native_list_view.js`).

    **Live verifiziert (Tower):** "Neu"-Button mit Karet erscheint, Dropdown zeigt beide
    Optionen, "Neuer Ordner" schliesst das Dropdown und oeffnet den bestehenden Anlegen-Dialog
    korrekt, "Hochladen" schliesst das Dropdown und loest den bestehenden Datei-Auswahl-Dialog
    aus - keine Konsolen-/Server-Fehler.

30. **`status_id` ohne Default (2026-09-07), Nutzerwunsch.** Vorher `default=lambda self:
    self.env.ref(".../filemanager_status_normal", ...)` - jede neue Datei/jeder neue Ordner
    bekam automatisch "Offen". Beobachtung des Nutzers: das Feld liess sich im Formular schon
    vorher leeren (kein `required=True`) - "leer" war also ein erreichbarer Zustand, nur nicht
    der Startzustand. Reine Standard-Feldkonfiguration, keine besondere Odoo-Funktion noetig:
    `default` einfach entfernt, `fields.Many2one` ohne `default` ist bei jeder Neuanlage
    automatisch leer.

    **Betrifft alle Neuanlage-Wege**, nicht nur die UI-Buttons: auch vom Watcher/Scan neu
    entdeckte Dateien (`index_upsert`/`_scan_and_reconcile`, die keinen `status_id` in ihren
    `vals` setzen) starten jetzt ohne Status-Badge statt automatisch "Offen" zu zeigen -
    bewusst in Kauf genommen, entspricht dem Nutzerwunsch fuer *jede* Neuanlage, nicht nur die
    manuelle.

    **Migrations-Skript-Kommentar korrigiert:** `post-migrate_state_to_status.py` erwaehnte den
    jetzt nicht mehr existierenden Default fuer den Frisch-Installations-Fall - richtiggestellt,
    Verhalten der Migration selbst (Mapping alter `state`-Werte bei einem Upgrade) unveraendert.

    **Live verifiziert (Tower):** neuer Datensatz per RPC angelegt, `status_id` per SQL bestaetigt
    leer (`NULL`) statt automatisch "Offen". Keine neuen Fehler (nur erwartete "Read-only file
    system"-Meldungen von eigenen Testversuchen gegen das absichtlich schreibgeschuetzte
    `/mnt/hm-daten`).
