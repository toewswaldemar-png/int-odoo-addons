# Odoo 19 Regeln: Views – Records und Architekturen (Destillat)

Quelle: `odoo/documentation`, Branch 19.0, Commit `eee2e56` (2026-10-02),
`content/developer/reference/user_interface/view_records.rst`, `view_architectures.rst` und die eingebundenen
Bausteine `view_architectures/*.rst`
(Web: <https://www.odoo.com/documentation/19.0/developer/reference/user_interface/view_records.html>,
`…/view_architectures.html`). Geprüft: 2026-10-02. Ergänzt `docs/odoo_konventionen_2026-09-26.md` Abschnitt 5 (XML).
Icons und SCSS: `docs/odoo_regeln_ui_icons_scss_2026-10-02.md`. Index: `docs/odoo_regeln_index_2026-10-02.md`.

Legende: **Pflicht** = laut Quelle "Mandatory"; sonst optional. Standardwerte in Klammern. `Enterprise` = nicht in
Community (HM-SRV/Tower betreiben Community → **nicht verfügbar**).

## 1. View-Records (`ir.ui.view`)

- Minimalform: `<record id="ADDON.MODEL_view_TYPE" model="ir.ui.view">` mit `name`, `model`, `arch` (`type="xml"`).
- Felder: `name` (nur Mnemonik; Odoo-Namen beginnen mit Addon und enden auf View-Typ), `model` (**Pflicht**),
  `arch`, `priority` (niedrigste Priorität = Standardview des Typs; steuert auch die Anwendungsreihenfolge der
  Vererbung), `inherit_id` (Elternview, per `ref`; Addon-Präfix nur nötig, wenn aus anderem Modul), `mode`
  (`extension` = Standard, `primary`).
- **`mode`:** `extension` – wird die View angefordert, wird die nächste Primär-View gesucht und alle Erweiterungen
  darauf angewendet. `primary` – die nächste Primär-View wird vollständig aufgelöst, dann werden die Specs dieser View
  angewendet; Ergebnis gilt als deren `arch`. Pflicht-Fall für `primary`: **Delegations-Vererbung** (abgeleitetes
  Modell braucht eigene Basis-View, sonst greift das Matching nicht).
- Kontext und Zugriffsrechte beeinflussen, was eine View kann.
- Typen: form, list (früher `tree`), search, kanban, qweb, graph, pivot, calendar, activity; **Enterprise:** cohort,
  gantt, grid, map. API: `get_views`, `get_view`.

### Vererbung
- **Auflösung:** Hat die View einen Elternteil → erst Elternteil vollständig auflösen, dann eigene Specs anwenden;
  sonst `arch` unverändert. Danach die `extension`-Kinder **tiefenweise** anwenden (Kind, dessen Kinder, dann
  Geschwister); Reihenfolge mehrerer Kinder derselben View nach `priority`.
- **Spec-Locator (3 Arten):** `<xpath expr="…">` (erster Treffer; in QWeb-Views zusätzlich `hasclass(*klassen)`),
  `<field name="…">` (erstes Feld gleichen Namens, **alle anderen Attribute ignoriert**), beliebiges Element
  (erstes mit gleichem Namen und identischen Attributen; `position`/`version` ignoriert).
- **`position`** (Standard `inside`): `inside` (anhängen), `after`, `before`, `replace` (`$0` als einzelner Textknoten
  = Kopie des gefundenen Knotens, zum Umhüllen), `attributes` (`<attribute name="x">Wert</attribute>`; ohne Körper =
  Attribut entfernen; `add`/`remove`/`separator` für Teilwerte, Standardtrenner `,`), `move`
  (`position="move"` auf dem Inhalt; der Locator braucht dann `inside|replace|after|before`).
- Hausregeln aus den Konventionen: `position="replace"` **vermeiden** (Kommentar + hohe `priority`), ein Modul erweitert
  eine View nur einmal; geerbte View-ID = Original-ID, `name` mit `.inherit.<modul>`.

## 2. Python-Ausdrücke in Views

Für Modifier (`invisible`, `readonly`, `required`, `column_invisible`, `decoration-*` …) stehen zur Verfügung:
alle **in der View vorhandenen** Feldnamen (Wert des aktuellen Datensatzes; relationale Felder als ID-Liste; bei
`column_invisible` in Listen nicht), die Datensatz-ID, `parent` (nur in Subviews relationaler Felder), `context`,
`uid`, `today` (`YYYY-MM-DD`), `now` (`YYYY-MM-DD hh:mm:ss`).
**Folgerung:** ein Feld, das nur in einem Ausdruck gebraucht wird, muss trotzdem in der View stehen (`invisible`
genügt).

## 3. Gemeinsame Attribute (alle Views)

| Attribut | Typ | Regel |
|---|---|---|
| `string` (Wurzel) | str | Titel, nur sichtbar bei Aktion ohne Namen mit `target=new` |
| `create`, `edit`, `delete` | bool (True) | Anlegen/Bearbeiten/Löschen an der View abschalten |
| `default_group_by` | str | Standardgruppierung, wenn Aktion/Suche keine vorgibt |
| `default_order` | str | überschreibt `_order` des Modells; `"sequence,name desc"` |
| `sample` | bool (False) | Beispieldatensätze, wenn das Modell leer ist (nicht bedienbar, verworfen bei erster Aktion) |
| `invisible` | Python-Ausdruck | unsichtbar; Technisch: Feld muss für Ausdrücke vorhanden sein |
| `column_invisible` | Python-Ausdruck | ganze Spalte (ohne Subtree-Werte ausgewertet); nur Listen |
| `groups` | str | kommagetrennte XML-IDs, `!` schließt aus: `groups="base.group_no_one,!base.group_multi_company"` |
| `readonly`, `required` | Python-Ausdruck | `required` mit unterschiedlichen Werten bei **mehrfach vorkommendem** Feld: Verhalten nicht garantiert |
| `class` | str | Bootstrap + Odoo-Klassen: `oe_inline`, `oe_left`, `oe_right`, `oe_read_only`, `oe_edit_only`, `oe_avatar` (max. 90×90), `oe_stat_button` |
| `widget` am Feld | str | Owl-Komponente aus Registry `fields` |
| `help` | str | Tooltip |

**Button** (Formular, Liste, Kanban): `type` **Pflicht**, außer `special` gesetzt: `object` (Methode `name` am Modell,
mit Datensatz-ID und `context`) oder `action` (XML-ID der Aktion, roh oder `%(XMLID)d`; Kontext erhält
`active_model`, `active_id`); `string` (Text bzw. `alt` bei Icon), `icon` (`fa-…` oder `oi-…`), `help`, `context`,
`groups`, `invisible`, `class`; Formular: `special` (`save`, `cancel` im Dialog), `confirm` (Bestätigungstext),
`data-hotkey` (Alt+Zeichen, `shift+k`); Liste: `column_invisible`.

## 4. Formular (`<form>`)

- Wurzelattribute: `string`, `create`, `edit`, `duplicate` (True), `delete`, `js_class`, `disable_autofocus`.
- **Semantische Komponenten:** `field`, `label`, `button`, `chatter` (nur bei `mail.thread`-Modellen),
  `<div class="o_attachment_preview"/>` (leer, Anhangsvorschau).
- **`field`**: `name` **Pflicht**, `id` (bei Mehrfachvorkommen), `string`, `help`, `options` (Python-Dict; bei
  Relationen `no_create`, `no_quick_create`, `no_open`, `no_create_edit`), `readonly`, `required`, `invisible`,
  `groups`, `domain` (Python-Ausdruck, relationale Felder, darf `parent.x` nutzen), `context` (u. a.
  `TYPE_view_ref`, `group_by`, `default_*`, `search_default_*`), `nolabel` (nur direktes Kind von `group`),
  `placeholder` (**kein Beispieldatum** – Nutzer halten es sonst für einen Wert), `mode` (`list|form|kanban|graph`),
  `class`, `filename` (Binary), `password` (Char), `kanban_view_ref`, `default_focus` (nur ein Feld je View).
  Dasselbe Feld mehrfach: erlaubt, `invisible`/`readonly` dürfen abweichen; relationale Felder können Subviews
  (`<list>`, `<form>`) enthalten.
- **`label`**: `for` **Pflicht** (Feldname oder `id`; bei mehreren Vorkommen eindeutige `id`s), `string`, `class`, `invisible`.
- **Struktur:** `group` (Standard 2 Spalten; `col`, `colspan`, `string`, `invisible`; Felder darin zeigen Label),
  `sheet` (schmales, responsives Layout), `notebook`/`page` (**`notebook` nicht in `group`**; `page string`),
  `newline`, `separator`, `header` (Workflow-Buttons + Statusfeld, z. B.
  `<field name="state" widget="statusbar" statusbar_visible="draft,posted" options="{'clickable': 1}"/>`),
  `footer` (Dialog-Buttons; Standardbuttons entfallen, außer `replace="0"`), Buttons-Container
  `<div name="button_box">`, Titel-Container `<div class="oe_title">`.

## 5. Einstellungen (`<form>` für res.config.settings)

- `app` (Pflicht `string`, `name` = Modulname; `logo` Standard `/{name}/static/description/icon.png`),
  `block` (`title`, `help`; beide durchsuchbar), `setting` (`type="header"` für Bereichsbanner, `string`, `title`,
  `help`, `company_dependent="1"`, `documentation`-Pfad). Das **erste Feld** im `setting` ist das Hauptfeld
  (Boolean links, sonst oben rechts) und liefert das Label, wenn `string` fehlt.

## 6. Liste (`<list>`, früher `<tree>`)

- Wurzel: `string`, `create`, `edit`, `delete`, `import` (True), `export_xlsx` (True), `editable` (`top`/`bottom`;
  Inline-Formular wird aus der Liste abgeleitet; wirkungslos bei `edit="false"`), `multi_edit="1"`,
  `open_form_view` (nur editierbar), `default_group_by`, `default_order`, `decoration-<stil>` (`bf`, `it`, `info`,
  `warning`, `danger`, `muted`, `primary`, `success`), `limit` (80; X2many 40), `groups_limit`, `expand` (langsam bei
  vielen Gruppen), `sample`.
- **`field`**: wie Formular, zusätzlich `optional` (`show|hide`), `column_invisible`, `decoration-<stil>`,
  `sum`/`avg` (Aggregat unten; **muss zum `aggregator` des Feldes passen**; nur angezeigte Datensätze), `width`
  (immer Pixel, `width="40px"`), `nolabel="1"` (leerer Kopf, nicht sortierbar). **Dasselbe Feld nur einmal.**
  Schlechter Stil: numerisches Feld in der **letzten** Spalte einer gruppierbaren Liste (Pager/Aggregate überlappen).
- **`button`**: wie Formular + `column_invisible`; `type="edit"` öffnet das Formular.
- **`groupby name="<many2one>"`**: Buttons/Felder im Gruppenkopf (Felder nur zum Laden, nie angezeigt).
- **`header`**: Buttons im Control-Panel; `display="always"` = ohne Auswahl sichtbar.
- **`control`** (**nur in One2many-/Many2many-Listen**): `create string=… context=…` (ersetzt "Add a line"),
  `button`, `delete invisible=…` (zeilenweise).

## 7. Suche (`<search>`)

- Keine Anzeige, filtert andere Views; Wurzel ohne Attribute. Kinder: `field`, `filter`, `separator`, `group`,
  `searchpanel`.
- **`field`:** `name` Pflicht; `operator` (Standard je Typ: `=` float, `ilike` char, `child_of` many2one),
  `filter_domain` (nutzt `self` für den Nutzerwert; **hat Vorrang vor `operator`**), `context`, `domain`
  (Autovervollständigung), `string`, `groups`, `invisible`. Felder und Filter werden mit **AND** verknüpft.
- **`filter`:** `name` und `string` **Pflicht**; `domain`, `help`, `context` (`{'group_by': 'feld'}` bzw.
  `'create_date:week'` für Gruppieren), `date` (Datumsfilter-Untermenü; `start_month` −2, `end_month` 0,
  `start_year` −2, `end_year` 0, `default_period`, eigene Unterfilter mit `name`/`string`/`domain`), `invisible`,
  `groups`.
  **ACHTUNG:** direkt aufeinanderfolgende Filter ohne `<separator/>` werden mit **OR** verknüpft.
- **`searchpanel`:** nur `field`-Kinder: `select` (`one`|`multi`), `icon`, `color`, `groups`; `one`: `hierarchize`,
  `depth`; `multi`: `enable_counters` (Performance!), `expand`, `limit` (200), `domain`, `groupby`.
  Performance-Alternative: `search_panel_select_range`/`_multi_range` überschreiben.
- **Standardwerte** über Aktions-Kontext `search_default_<name>`: Feld = Wert; Filter = Boolean/Zahl; Gruppier-Filter
  mit Zahl 1–99 bestimmen die Reihenfolge.

## 8. Kanban (`<kanban>`)

- Wurzel: `string`, `create/edit/delete`, `default_group_by`, `default_order`, `class`, `examples` (Registry-Schlüssel),
  `group_create`, `group_delete`, `group_edit`, `groups_draggable`, `records_draggable`, `archivable`, `quick_create`
  (Standard True bei Gruppierung nach many2one/selection/char/boolean), `quick_create_view`, `on_create`, `can_open`,
  `highlight_color` (Integer-Feld → Kartenrand), `sample`. Maximal 10 Spalten werden geladen.
- **`templates`:** mindestens Wurzeltemplate **`card`**, optional **`menu`** (Dropdown am ⋮). **Das ist JS-QWeb,
  kein Owl** – Direktiven wie `t-on-click` gibt es nicht. Felder: `<field name=… widget=…>` (`handle`,
  `kanban_color_picker`, …); Feld nur zum Laden: `<field>` **außerhalb** von `templates`.
- Renderkontext: `record` (je Feld `value` = formatiert, `raw_value` = roh; für Anzeige `<field>` bevorzugen),
  `widget` (`editable`, `deletable`), `context`, `read_only_mode`, `selection_mode`, `luxon`, `JSON`.
- Buttons/Links mit `type`: `action`, `object`, `open`, `delete`, `archive`, `unarchive`, `set_cover`.
- Layout: Karte ist Flexbox (Spalte); `<footer>` klebt unten; `aside`/`main` + Klasse `flex-row`;
  `o_kanban_aside_full` entfernt Padding. `<widget name=…>` für Owl-Komponenten aus `view_widgets`.
- `header` (nur Buttons mit `display="always"` – Auswahl in Kanban nicht möglich), `progressbar`
  (`field` Pflicht, `colors` Pflicht als JSON, `sum_field`), `control` wie bei Listen.

## 9. QWeb-View, Graph, Pivot, Calendar, Activity

- **QWeb-View:** kein festes Wurzelelement → `type` muss **explizit** angegeben werden. Frontend-Templates über
  `<template>`; echte QWeb-Views als `ir.ui.view` mit `type` und `model`. Besonderheit: `<nav class="o_qweb_cp_buttons">`
  wandert in die Control-Panel-Buttons. Kontext: `model`, `domain`, `context`, `records` (lazy `search(domain)`);
  Hooks `_qweb_prepare_context(view_id, domain)`, `qweb_render_view(view_id, domain)`.
- **Graph:** `type` (`bar`|`pie`|`line`), `stacked`, `disable_linking`, `order`, `string`, `sample`; `field` mit
  `name` Pflicht, `invisible`, `type="measure"`, `interval` (`day|week|month|quarter|year`, Standard `month`),
  `string`, `widget` (z. B. `float_time`, `monetary`). **Nur gespeicherte Felder** (Aggregation in der DB; nicht
  gespeicherte Compute-Felder gehen nicht).
- **Pivot:** `disable_linking`, `display_quantity`, `default_order` (`"foo asc"`), `sample`; `field` mit `type`
  (`row` Standard, `col`, `measure`, `interval`), `interval`, `string`, `invisible`, `widget`. Auch hier nur
  gespeicherte Felder.
- **Calendar:** `date_start` **Pflicht**; `date_stop` oder `date_delay` (Stunden), `scales`, `mode` (`week`), `color`,
  `all_day`, `aggregate`, `event_limit` (5), `show_unusual_days`, `hide_date/time`, `month_overflow`,
  `show_date_picker`, `event_open_popup`, `form_view_id`, `quick_create` (True), `create_name_field`,
  `quick_create_view_id`, `multi_create_view`, `create/edit/delete`, `string`. Kinder: `field` (Popover, readonly;
  `options` mit `icon`/`string`; Filter-Seitenleiste über `filters`, `avatar_field`, `color`, `write_model`,
  `write_field`, `filter_field`). Initialdatum über Kontext `initial_date`.
- **Activity:** nur mit Modul `mail` und Modellen mit `mail.activity.mixin`; Wurzel `<activity string=…>` (Pflicht);
  `templates` mit Pflicht-Template **`activity-box`**; Kontext `widget`, `record`.

## 10. Enterprise-Views (nicht in Community)

- **Cohort** (`string`, `date_start`, `date_stop` Pflicht; `mode` churn/retention, `timeline`, `interval`, `measure`),
  **Grid** (`string` Pflicht, Spalten `col`/`range`, `row`, `measure`; Arbeit-in-Arbeit, Server-Hooks
  `_grid_*`, `read_grid`), **Gantt** (`date_start`, `date_stop` Pflicht; viele Attribute: `dependency_field`,
  `default_scale`, `precision`, `thumbnails`, …), **Map** (`res_partner`, `routing` braucht MapBox-Token; OpenStreetMap
  ohne Token). Nur nachschlagen, nicht verwenden – für Community-Betrieb nicht verfügbar. Details bei Bedarf in
  `content/developer/reference/user_interface/view_architectures.rst` (Zeilen ab "Cohort").
