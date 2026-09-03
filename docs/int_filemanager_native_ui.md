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
           enable_counters="1" expand="1"
           domain="[('is_dir', '=', True)]"/>
</searchpanel>
```

Alle drei Attribute sind **Pflicht**, nicht optional — belegt am Python-Quellcode:

- **`domain="[('is_dir','=',True)]"` zwingend**, sonst listet der Baum jedes
  `int_filemanager.file`-Record als Knoten, auch einzelne Dateien.
- **`expand="1"` zwingend**, sonst zeigt der Baum nur Ordner, die aktuell mindestens einen
  bestätigten Nachfahren mit Daten haben (`domain_image`-Logik in `search_panel_select_range`).
  Ein frisch angelegter, leerer Ordner würde sonst im Baum **gar nicht erscheinen**.
- **`enable_counters="1"`** — Bonus passend zum DMS-Ziel: zeigt pro Ordner die Trefferzahl der
  aktuell gefilterten/gesuchten Datensätze.

Offen/noch nicht smoke-getestet: dass das `domain`-Attribut am `<field>` tatsächlich auf
`comodel_domain` gemappt wird (Standardmuster, aber die JS-Quelldatei dafür wurde in diesem Build
nicht am erwarteten Pfad gefunden) — vor der Umsetzung als Erstes live prüfen.

### Eigentlicher Aufwand: Pflege von `parent_id`, nicht das Feld selbst

- **`_scan_and_reconcile`** (`models/filemanager_file.py:120`): baut aktuell `to_create` als eine
  einzige `Model.create(...)`-Liste am Ende. Für `parent_id` braucht ein Kind die bereits vergebene
  DB-ID seines Elternordners — bei einem kompletten Erst-Scan existiert die noch nicht. Lösung:
  Erstellung in Ebenen (BFS nach Tiefe, `os.walk` liefert Eltern ohnehin vor Kindern), mit
  `path → id`-Cache pro Ebene.
- **Merge-Pfad bei Rename/Move während Odoo nicht lief** (Zeile 301–346): muss zusätzlich
  `parent_id` auf den neuen Elternordner umschreiben (`_parent_store` kaskadiert dann automatisch).
- **Watcher/`mkdir`-Controller**: unkritisch, unmittelbarer Elternordner ist immer bekannt.
- **Migration Bestandsdaten**: einmaliger Backfill (`post_init_hook`), der `parent_id` aus
  `folder_path` top-down auflöst.

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

1. Ordnerbaum-Design oben umsetzen (auf `experiment/native-listview` oder eigenem Sub-Branch) —
   zuerst SearchPanel-`domain`-Attribut live smoke-testen, dann `parent_id`/`_parent_store` +
   Scan-Anpassung.
2. Entscheiden, ob/wie weit der native-ListView-Spike weiter ausgebaut wird (siehe oben) oder ob
   der jetzige Stand als Erkenntnis reicht und verworfen wird.
3. **Sicherheitsrelevant, nicht vergessen:** für die Live-Tests in dieser Session wurde ein
   temporäres Admin-Passwort (`TempDebug2026!`) auf der Unraid-Instanz gesetzt — zurücksetzen,
   sobald nicht mehr gebraucht.
