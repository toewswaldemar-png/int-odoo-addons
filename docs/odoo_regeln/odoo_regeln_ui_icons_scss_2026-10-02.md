# Odoo 19 Regeln: UI-Icons und SCSS-Vererbung (Destillat)

Quellen (Rangfolge: Odoo-19-Code vor Doku): Odoo-19-Core (`addons/web/static/lib/odoo_ui_icons/style.css`,
`addons/web/static/src/libs/fontawesome`, `addons/web/static/src/views/view_button/view_button.js`,
`addons/web/__manifest__.py`, `addons/spreadsheet/static/src/o_spreadsheet/`, `odoo/addons/base/models/ir_ui_view.py`)
und Odoo-19-Entwicklerdoku (`odoo/documentation`, Branch 19.0, `content/developer/reference/user_interface/icons.rst`
und `scss_inheritance.rst`). Wo Core und Doku abweichen, gilt der Core.
(Web: <https://www.odoo.com/documentation/19.0/developer/reference/user_interface/icons.html>,
`…/scss_inheritance.html`). Geprüft: 2026-10-02, Core-Abgleich 2026-10-08. SCSS-Format/Namensregeln (Coding Guidelines):
`odoo_regeln_coding_guidelines_2026-10-02.md` Abschnitt 6. Index: `docs/odoo_regeln/odoo_regeln_index_2026-10-02.md`.

## 1. Icons

- Standard: **FontAwesome 4** (Core: Font Awesome 4.7.0; `fa fa-…`; im Button-Attribut `icon="fa-trash"`). Das
  Button-Attribut `icon` akzeptiert `fa-…`, `oi-…` oder einen Bildpfad (`iconFromString` in `view_button.js`).
- Für Lücken zusätzlich **Odoo-UI-Icons**: Hauptklasse `oi` + Icon-Klasse: `<i class="oi oi-odoo"/>`.
  Verfügbar (Doku; deckungsgleich mit den 69 `.oi-*`-Klassen in `odoo_ui_icons/style.css`): `oi-odoo`, `oi-view`, `oi-view-kanban`, `oi-view-list`, `oi-view-cohort`,
  `oi-view-pivot`, `oi-text-break`, `oi-text-inline`, `oi-text-wrap`, `oi-text-effect`, `oi-search`, `oi-group`,
  `oi-settings-adjust`, `oi-panel-right`, `oi-launch`, `oi-apps`, `oi-studio`, `oi-voip`, `oi-gif-picker`, `oi-close`,
  `oi-chevron-{down,left,right,up}`, `oi-arrows-{h,v}`, `oi-arrow-{down,left,right,up}` (+ `-down-left`,
  `-down-right`, `-up-left`, `-up-right`), `oi-draggable`, `oi-archive`, `oi-unarchive`, `oi-smile-add`,
  `oi-food-delivery`, `oi-activity`, `oi-activity-plus`, `oi-schedule-{today,tomorrow,later}`, `oi-backspace-o`,
  `oi-numpad`, `oi-record`, `oi-merge`, `oi-transfer`, `oi-suitcase`, `oi-suitcase-plus`, `oi-user`, `oi-user-plus`,
  `oi-users`, `oi-ellipsis-{v,h}`, `oi-plus`, `oi-minus`, `oi-star-plus`, `oi-subtitle`; Marken: `oi-bluesky`,
  `oi-tiktok`, `oi-discord`, `oi-google-play`, `oi-kickstarter`, `oi-strava`, `oi-threads`, `oi-x`, `oi-x-square`.
- **Spreadsheet-Icons** (`SEE_RECORDS`, `GLOBAL_FILTERS`, `BOLD` …, 139 Namen) sind `<svg>`-Elemente in
  QWeb-Templates `o-spreadsheet-Icon.NAME` (z. B. `<svg width="20" height="20" viewbox="0 0 20 20"><path
  fill="currentColor" d="…"/></svg>`; Core: `spreadsheet/static/src/o_spreadsheet/icons.xml` und
  `o_spreadsheet.xml`) – nur relevant, wenn `spreadsheet` verwendet wird. Namensliste bei Bedarf in der Quelle.
- **Regel:** vor der Verwendung eines `oi-*`-Icons gegen die Liste prüfen (die Liste ist vollständig für 19.0, Abgleich
  mit `style.css`).
- **Barrierefreiheit (Core-Validierung `_validate_fa_class_accessibility` in `ir_ui_view.py`):** ein `fa-*`-Icon in
  einer View-Arch (Klasse oder Button-`icon`) braucht daneben Text, `title`/`aria-label` (auch am Vorfahren) oder
  `string`, sonst Warnung.

## 2. SCSS-Vererbung

- Ziele des Systems: Bootstrap anpassen, Community- und Enterprise-Design, Backend-/Frontend-Bundles getrennt,
  Assets kontextabhängig laden, mehrere Farbschemata (Dark Mode).
- **NIE Variablen direkt überschreiben** (`$foo: blue;` in einer Anpassungsschicht) – das führt bei
  bundleübergreifender Kompilierung zu unvorhersehbaren Ergebnissen.
- **Immer `!default`:** `$foo: red !default;` setzt den Wert **nur**, wenn die Variable noch nicht definiert ist;
  die Priorität folgt so der **Ladereihenfolge** der Assets (früher geladene Datei gewinnt). Eine spätere
  Bibliotheksdatei mit `$foo: blue !default` wird dann ignoriert.
- Kompilierreihenfolge (konzeptionell, laut Quelle unvollständig): `web.dark_mode_variables` →
  `web._assets_primary_variables` (Enterprise vor Community; Primär- vor Komponenten-Variablen; im Core besteht das Bundle aus
  `primary_variables.scss` und `web/static/src/**/*.variables.scss`) →
  `web._assets_bootstrap` → `web.assets_backend` (CSS-Variablen-Definition und kontextuelle Anpassungen). Hinweis: `web.dark_mode_variables` ist
  in `web/__manifest__.py` nicht definiert, Community-Module erweitern es nur (z. B. `onboarding/__manifest__.py`);
  die Dark-Mode-Stile (`*.dark.scss`) liefert dort `web.assets_web_dark`.
- **Folgerung für eigene Module:** Variablen mit `!default` definieren und im richtigen Bundle laden (siehe
  Assets-Operationen `prepend`/`before`/`after` im JS-Framework-Destillat); Stilnamen und Format nach den Coding Guidelines
  Abschnitt 6 (`$o-[root]-[element]-[property]-[modifier]`, lokale `$-name`, CSS-Variablen BEM).
