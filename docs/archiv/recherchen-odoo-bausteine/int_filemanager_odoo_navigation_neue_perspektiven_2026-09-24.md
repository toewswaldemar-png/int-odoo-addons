# int_filemanager: Ordnernavigation — zwei neue, bisher nicht betrachtete native Perspektiven

Stand 2026-09-24. Fünfte Prüfung in der Reihe, diesmal bewusst **weg vom Baum-Widget-Vergleich**
(SearchPanel/`web_hierarchy`/`hr_org_chart` sind in den vorherigen vier Dokumenten erschöpfend
behandelt) — stattdessen zwei komplett andere Fragen gestellt: (1) Gibt es einen generischen
Caching-Baustein, der `FolderTree`s bereits lazy ladende Anfragen zusätzlich beschleunigen könnte,
unabhängig vom Baum-Konzept selbst? (2) Gibt es ein natives Muster für "direkt zu einem tief
verschachtelten Ordner springen", das eine Baumdarstellung gar nicht erst braucht? Beide Fragen
haben echte, bisher unbenutzte native Treffer ergeben. Reine Recherche, nichts umgesetzt.

---

## 1. `RPCCache` — natives, verschlüsseltes IndexedDB-Caching für JEDEN RPC-Aufruf, ungenutzt in `FolderTree`

Beim Verfolgen, wie `SearchPanel`s eigener `_fetchCategories()`-Aufruf technisch funktioniert
(`this.orm.cache({type: "disk", update: "always", callback: ...}).call(...)`, bereits in
`int_filemanager_odoo_suche_navigation_vollstaendig_2026-09-24.md` zitiert, aber nicht bis zur
Cache-Implementierung verfolgt), zeigt sich: das ist keine SearchPanel-Eigenheit, sondern ein
**generischer, für jeden beliebigen RPC-Aufruf nutzbarer Baustein**.

**Fundstelle** (`addons/web/static/src/core/network/rpc_cache.js`, 244 Zeilen, vollständig gelesen;
verdrahtet in `addons/web/static/src/start.js:36`, `rpc.setCache(new RPCCache("rpc",
session.registry_hash, session.browser_cache_secret))` — läuft also bei **jedem** Odoo-Webclient-
Start, nicht optional):

- Zwei Ebenen: **RAM** (Sitzung) und **Disk** (IndexedDB, übersteht Reloads/neue Sitzungen),
  Disk-Werte **AES-GCM-verschlüsselt** mit einem pro Browser generierten Secret (Zeilen 29-74,
  110-125).
- **`update: "always"`-Modus = Stale-while-revalidate**: liefert sofort den zwischengespeicherten
  Wert (falls vorhanden) für eine augenblickliche Anzeige, holt **gleichzeitig** im Hintergrund den
  aktuellen Stand nach und ruft bei Abweichung einen `callback(result, hasChanged)` auf (Zeilen
  147-230) — exakt das Muster, das `SearchPanel` intern nutzt: sofort anzeigen, still korrigieren,
  falls nötig.
- Automatische Größenbegrenzung (2 GB, Zeilen 27, 119-125) mit Selbstlöschung bei Überschreitung.
- Globale wie gezielte Invalidierung per Tabellen-Namen (`invalidate(tables)`, Zeilen 235-243) und
  Bus-Event `"CLEAR-CACHES"` (`rpc.js:85-87`).
- **Funktioniert auf Ebene der einfachen `rpc()`-Funktion selbst**, nicht nur über `orm.call()` —
  jeder eigene Controller-Aufruf (wie `int_filemanager`s `/int_filemanager/tree`) kann das dritte
  Argument `{cache: {...}}` genauso übergeben.

**Direkter, bisher ungenutzter Nutzen für `FolderTree`:** `folder_tree.js:ensureLoaded()` ruft
aktuell **ungecacht** `rpc("/int_filemanager/tree", { path })` auf (`folder_tree.js:77`). Der
gesamte Lade-Fortschritt (`this.nodes`) lebt nur in `useState` — nach jedem Seiten-Reload sind
selbst bereits besuchte, bereits aufgeklappte Ebenen wieder komplett unbekannt, jede erneut
aufgeklappte Ebene braucht wieder einen vollen Round-Trip. Mit
`rpc("/int_filemanager/tree", { path }, { cache: { type: "disk", update: "always", callback: (result, hasChanged) => { if (hasChanged) { /* Knoten aktualisieren */ } } } })`
würde:
1. Erneutes Aufklappen einer bereits besuchten Ebene **innerhalb** einer Sitzung sofort aus dem
   RAM-Cache kommen (heute: erneuter Server-Roundtrip).
2. Der Baum **nach einem Seiten-Reload** sofort mit dem zuletzt bekannten Stand aus IndexedDB
   erscheinen, statt leer zu starten und jede Ebene der aktuellen Pfadkette neu zu laden — und sich
   im Hintergrund still korrigieren, falls sich zwischenzeitlich etwas geändert hat.
3. Die bereits vorhandene, an `int_filemanager.change`-Bus-Events gebundene `reload()`/`refresh()`-
   Logik (`filemanager_controller_mixin.js`) ließe sich direkt an `invalidate("/int_filemanager/tree")`
   koppeln statt nur an `folderTreeApi.invalidate(path)` — echte Push-Invalidierung statt reinem
   Verwerfen des In-Memory-Zustands.

Kein Architekturwechsel, keine Server-Änderung nötig — eine bestehende, bereits im Kern aktive
Infrastruktur wird schlicht noch nicht in Anspruch genommen.

---

## 2. `complete_name`/`hierarchical_naming`-Muster + `name_search` — natives "Direkt-Springen" statt Baum-Browsen

Ausgangsfrage: gibt es ein natives Muster, um in einer riesigen Hierarchie **direkt** zu einem
Knoten zu springen, ohne sich durchzuklicken? Gefunden über den `hierarchical_naming`-Kontext-
Flag, der bereits in `search_panel_select_range()` auftauchte (`Comodel = ...with_context(
hierarchical_naming=False)`, siehe vorheriges Dokument) — Grep über den ganzen Kern zeigt: genau
zwei Modelle implementieren das wirklich, `hr.department` und `product.category`
(`addons/product/models/product_category.py:8-35`, vollständig gelesen):

```python
_rec_name = 'complete_name'
complete_name = fields.Char(compute='_compute_complete_name', recursive=True, store=True, ...)

@api.depends('name', 'parent_id.complete_name')
def _compute_complete_name(self):
    for category in self:
        category.complete_name = f'{category.parent_id.complete_name} / {category.name}' if category.parent_id else category.name
```

**Kein magischer Automatismus, sondern ein klar kopierbares Muster:** ein rekursiv berechnetes,
**gespeichertes** Feld mit dem vollen "Pfad"-Namen, als `_rec_name` gesetzt. Der native
`name_search()`/`_search_display_name()`-Mechanismus (`odoo/orm/models.py:1454-1464`, vollständig
gelesen) durchsucht automatisch genau dieses Feld — jede `Many2one`-Autocomplete-Eingabe auf ein
Modell mit diesem Muster durchsucht damit **den vollen Pfad**, nicht nur den letzten Namensteil,
und liefert indexbasierte, kleine Treffermengen (kein Tree-Walk, kein `GROUP BY`).

**Für `int_filemanager` bereits fast fertig vorhanden:** `int_filemanager.file` hat bereits ein
gespeichertes, vollständiges Pfadfeld (`path`) — strukturell exakt das, was `complete_name` bei
`product.category` leistet, nur mit `/` statt selbst gewähltem Trenner. Es fehlt kein neues Feld,
nur eine **Sucheingabe**, die `name_search`/eine eigene, leichte RPC gegen `path ilike '%Eingabe%'`
(begrenzt auf `is_dir=True`) nutzt und bei Auswahl `env.searchModel.setIntFilemanagerFolderPath()`
aufruft — dieselbe Funktion, die `FolderTree`/Breadcrumbs bereits als einzigen Schreiber nutzen
(siehe `int_filemanager_odoo_suche_navigation_vollstaendig_2026-09-24.md`, Abschnitt 2).

**Zusätzliche, native UI-Oberfläche dafür bereits vorhanden, nicht nur als Konzept:** Odoos globale
Befehlspalette (Strg+K) hat einen offenen, generischen Erweiterungspunkt
(`registry.category("command_provider")`, `addons/web/static/src/core/commands/default_providers.js:35-38`,
Muster `provide: (env, options) => [...Befehle]`, vollständig gelesen). Ein eigener Provider
("Gehe zu Ordner: …") könnte dieselbe pfadbasierte Suche direkt in die native, bereits jedem
Nutzer bekannte Tastatur-Palette einhängen — keine eigene Such-UI nötig, nur ein Registry-Eintrag.

**Einordnung:** kein Ersatz für `FolderTree` (Browsen/Struktur-Überblick bleibt dessen Aufgabe),
sondern eine **komplementäre**, bisher komplett fehlende zweite Navigationsart ("ich weiß, wonach
ich suche" vs. "ich will mich durchklicken") — beide zusammen decken sich mit dem in
`../../int_filemanager_feature_ideen_2026-09-21.md` (Abschnitt C) skizzierten Wunsch nach einer
"Adressleiste"/Schnellzugriff, jetzt mit einem konkreten, nativen Umsetzungsweg statt einer
offenen Idee.

---

## 3. Warum diese zwei und nicht mehr

Bewusst nicht weiterverfolgt, mit Begründung: Service-Worker/Offline-PWA-Fähigkeiten (kein
erkennbarer Bezug zu Ordnernavigation); ein drittes Muster über `command_provider` hinaus wurde
nicht gesondert behandelt, da es dieselbe zugrunde liegende Fähigkeit (Pfad-Suche) nur über eine
andere UI-Oberfläche anbietet, keine eigenständige dritte Idee. Beide hier behandelten Funde sind
bewusst **orthogonal** zur bisherigen Baum-Widget-Diskussion, nicht eine Variation davon — das war
der Auftrag ("nicht auf bekannte Muster versteifen").
