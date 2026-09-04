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
12. **Sicherheitsrelevant, nicht vergessen:** für die Live-Tests in dieser Session wurde ein
    temporäres Admin-Passwort (`TempDebug2026!`) auf der Unraid-Instanz gesetzt — bewusst noch nicht
    zurückgesetzt (Stand 2026-09-04, auf Wunsch offen gelassen).
