# Odoo 19 Regeln: Feld-Widgets und Client-Aktionen im Webclient (Destillat)

Quelle: `odoo/documentation`, Branch 19.0, Commit `eee2e56` (2026-10-02),
`content/developer/reference/frontend/javascript_reference.rst` (Abschnitte Fields, Widgets, Client actions).
Geprüft: 2026-10-02. Framework-Teil derselben Datei: `docs/odoo_regeln/odoo_regeln_js_framework_2026-10-02.md`.
Index: `docs/odoo_regeln/odoo_regeln_index_2026-10-02.md`.

Dies ist ein **Nachschlage-Katalog** (kein Regelwerk); Abschnitt "Eigenes Feld-Widget" am Ende enthält Regeln. Verbindlich ist sonst nur, **für welchen Feldtyp ein Widget
gilt**, und dass Optionen in `options="{…}"` bzw. als Attribut am `<field>` stehen. Vor Verwendung im Core des
Containers prüfen, ob das Widget in 19.0 noch so heißt.

## 1. Allgemein

- `<field name=… widget="…" options="{…}"/>`; Standardwidget je Feldtyp (`integer`, `float`, `boolean`, `char`,
  `date`, `datetime`, `monetary`, `text`, `many2one`, `many2many`, `one2many`, `selection`, `binary`, `image`).
- **Dekorationen** am Feld: `decoration-{bf|it|danger|info|muted|primary|success|warning}="python-ausdruck"` →
  CSS-Klasse `text-*` (Bootstrap; `bf`/`it` von Odoo = fett/kursiv); Ausdruck wird mit dem Datensatz als Kontext
  ausgewertet.
- `title` (Attribut) statt `options.title`, wenn der Text **übersetzt** werden soll (Progressbar).

## 2. Nicht-relationale Widgets (Widget → Feldtyp, wichtige Optionen)

| Widget | Typen | Optionen / Hinweise |
|---|---|---|
| `integer`, `float` | integer / float | `type: 'number'`, `step`, `format` (false = unformatiert); float: `digits="[42,5]"`, `min_display_digits`, `hide_trailing_zeros` |
| `float_time` | float | Stunden als `h:mm` |
| `float_factor` / `float_toggle` | float | Option `factor`; Toggle zusätzlich `range` |
| `boolean`, `boolean_toggle`, `boolean_favorite` | boolean | Toggle-Schalter bzw. Stern (auch im Readonly editierbar) |
| `char`, `text` | char / text | — |
| `date` / `datetime` / `daterange` | date, datetime | `min_date`/`max_date` (SQL-Format oder `"today"`; Standard 1000-01-01…9999-12-31), `warn_future`, `numeric`; datetime: `rounding` (5), `show_seconds`, `show_time`, `show_date`; daterange: `start_date_field` **oder** `end_date_field` (nicht beide); Werte immer in Client-Zeitzone |
| `remaining_days` | date, datetime | Readonly: Tage bis heute |
| `monetary` | monetary, float | `currency_field`, `hide_trailing_zeros`; ohne Angabe Session-Währung |
| `password` | char, text | Eingabe verdeckt, Auge-Schalter; für API-Schlüssel/Token; `placeholder` |
| `handle` | integer | Ziehgriff zum Umsortieren; **muss am Sortierfeld stehen, nur ein Handle je Liste** |
| `email`, `phone`, `url` | char | Anker mit href im Readonly; `url`: `text`-Attribut, `website_path` |
| `domain` | char | nur **statische** Domains; Optionen `model`, `foldable`, `in_dialog`, `count_limit` (10000; Zähl-Requests können teuer sein) |
| `image` | binary | Optionen `preview_image` (z. B. `image_128`), `accepted_file_extensions` |
| `binary` | binary | Attribut `filename` (Dateiname-Feld in der View), `accepted_file_extensions` |
| `priority` | selection | Sterne, auch im Readonly klickbar |
| `attachment_image` | many2one | nur Anzeige |
| `label_selection` | selection | Option `classes` (Wert → CSS-Klasse) |
| `state_selection` | selection | verlangt Felder `stage_id`, `legend_normal/blocked/done` in der View; `hide_label` |
| `statinfo` | integer, float | Stat-Button; `label_field` |
| `percentpie`, `progressbar` | integer, float | Progressbar: `editable`, `current_value`, `max_value`, `edit_max_value` |
| `dashboard_graph` | char | JSON-Daten; Attribut `graph_type` (`line`/`bar`) |
| `ace` | char, text | Code-Editor (XML/Python) |
| `badge` | char, selection, many2one | Farbe über `decoration-*` |

## 3. Relationale Widgets

| Widget | Typen | Optionen / Hinweise |
|---|---|---|
| `selection` | selection | Attribut `placeholder` |
| `radio` | selection, many2one | `horizontal`; bei many2one zusätzliche RPCs |
| `selection_badge` | selection, many2one | — |
| `many2one` | many2one | Attribute `can_create` (hat Vorrang vor `no_create`), `can_write`; Optionen `quick_create`, `no_create`, `no_quick_create`, `no_create_edit`, `create_name_field`, `always_reload` (nur wenn `name_get` überschrieben – "bitte nicht tun"), `no_open` |
| `many2one_barcode` | many2one | Kamera-Scan (nur Mobile-App; sonst Fallback auf `many2one`) |
| `many2one_avatar`, `_user`, `_employee` | many2one | Ziel erbt `image.mixin`; `_user` → `res.users`, `_employee` → `hr.employee` |
| `many2many` | many2many | Attribute `mode`, `domain`; Optionen `create_text`, `link`, `unlink` |
| `many2many_binary` | many2many | nur `ir.attachment`; `accepted_file_extensions` |
| `many2many_tags` (+`form.`, `kanban.`) | many2many | `create`, `color_field` (numerisches Feld in der View), `no_edit_color`, `edit_tags` |
| `many2many_checkboxes` | many2many | **max. 100** Einträge, nicht anpassbar (bei großen Modellen Listenansicht nutzen) |
| `one2many` | one2many | `create`, `delete` (Domains), `create_text` |
| `statusbar` | selection, many2one | nur Formulare |
| `reference` | char, reference | `model_field` blendet die Modellauswahl aus |

## 4. Widgets (`<widget name="…">`)

- `web_ribbon` (Attribute `title`, `tooltip`, `bg_color`/`bg-class`; z. B. "Archived"), `week_days`.

## 5. Client-Aktionen

- Eine Client-Aktion ist serverseitig ein `ir.actions.client`-Datensatz mit `tag`, im Webclient eine **Owl-Komponente
  in `registry.category("actions")` unter demselben Schlüssel** (alternativ eine Funktion, deren Rückgabewert als
  Folgeaktion ausgeführt wird). Sie belegt den Bereich unter der Navbar (Vorbild: Discuss).

## Eigenes Feld-Widget (Regeln)

- **Unterklasse eines vorhandenen Felds:** die Komponente erbt die Feldkomponente und bekommt ein eigenes `static template = "<addon>.<Name>"`; das Template
  steht in einer `.xml`-Datei und erbt das Template des Elternfelds (`t-inherit="web.<Elternfeld>"` mit `<xpath …>`).
- **Neues Feld:** Owl-Komponente mit benanntem Template (`.xml`, kein Inline-Template mit dem Helfer `xml`) und `static props = {...standardFieldProps}`. Die
  Standard-Props sind `id`, `name`, `readonly` und `record`; es gibt kein `value`, `update` oder `type`. **Lesen** aus `props.record.data[props.name]`
  (reaktiv mit `useRecordObserver`), **schreiben** mit `props.record.update({[props.name]: wert})`.
- **Registrierung als Objekt** in `registry.category("fields")`: `{component, displayName: _t("…"), supportedTypes: [...]}`, optional `extractProps`
  (Optionen aus dem Attribut `options` in Props übersetzen) und `isEmpty`. `supportedTypes` steht im Objekt, nicht als statische Eigenschaft der
  Komponente. Das Objekt wird als eigene exportierte Konstante (`export const <name>Field = {…}`) definiert und dann registriert.
- **Widgetname** mit Modulpräfix (`<modul>_<name>`), damit er keinen Namen des Cores überlagert.
- **Einbinden:** `widget="<name>"` am `<field>` der View; Optionen über `options="{…}"`, ausgewertet von `extractProps`.
