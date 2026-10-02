# Odoo 19 Regeln: UI-Icons und SCSS-Vererbung (Destillat)

Quelle: `odoo/documentation`, Branch 19.0, Commit `eee2e56` (2026-10-02),
`content/developer/reference/user_interface/icons.rst` und `scss_inheritance.rst`
(Web: <https://www.odoo.com/documentation/19.0/developer/reference/user_interface/icons.html>,
`…/scss_inheritance.html`). Geprüft: 2026-10-02. SCSS-Format/Namensregeln (Coding Guidelines):
`docs/odoo_konventionen_2026-09-26.md` Abschnitt 6. Index: `docs/odoo_regeln/odoo_regeln_index_2026-10-02.md`.

## 1. Icons

- Standard: **FontAwesome 4** (`fa fa-…`; im Button-Attribut `icon="fa-trash"`).
- Für Lücken zusätzlich **Odoo-UI-Icons**: Hauptklasse `oi` + Icon-Klasse: `<i class="oi oi-odoo"/>`.
  Verfügbar (aus der Referenz): `oi-odoo`, `oi-view`, `oi-view-kanban`, `oi-view-list`, `oi-view-cohort`,
  `oi-view-pivot`, `oi-text-break`, `oi-text-inline`, `oi-text-wrap`, `oi-text-effect`, `oi-search`, `oi-group`,
  `oi-settings-adjust`, `oi-panel-right`, `oi-launch`, `oi-apps`, `oi-studio`, `oi-voip`, `oi-gif-picker`, `oi-close`,
  `oi-chevron-{down,left,right,up}`, `oi-arrows-{h,v}`, `oi-arrow-{down,left,right,up}` (+ `-down-left`,
  `-down-right`, `-up-left`, `-up-right`), `oi-draggable`, `oi-archive`, `oi-unarchive`, `oi-smile-add`,
  `oi-food-delivery`, `oi-activity`, `oi-activity-plus`, `oi-schedule-{today,tomorrow,later}`, `oi-backspace-o`,
  `oi-numpad`, `oi-record`, `oi-merge`, `oi-transfer`, `oi-suitcase`, `oi-suitcase-plus`, `oi-user`, `oi-user-plus`,
  `oi-users`, `oi-ellipsis-{v,h}`, `oi-plus`, `oi-minus`, `oi-star-plus`, `oi-subtitle`; Marken: `oi-bluesky`,
  `oi-tiktok`, `oi-discord`, `oi-google-play`, `oi-kickstarter`, `oi-strava`, `oi-threads`, `oi-x`, `oi-x-square`.
- **Spreadsheet-Icons** (`SEE_RECORDS`, `GLOBAL_FILTERS`, `BOLD` …, rund 160 Namen) sind `<svg>`-Elemente
  (`<svg class="os-icon"><use href="#name"/></svg>`), per QWeb-Template `o-spreadsheet-Icon.NAME` gerendert –
  nur relevant, wenn `spreadsheet` verwendet wird (nicht in diesem Repo). Namensliste bei Bedarf in der Quelle.
- **Regel:** vor der Verwendung eines `oi-*`-Icons gegen die Liste prüfen (Referenz ist die vollständige Liste für 19.0).

## 2. SCSS-Vererbung

- Ziele des Systems: Bootstrap anpassen, Community- und Enterprise-Design, Backend-/Frontend-Bundles getrennt,
  Assets kontextabhängig laden, mehrere Farbschemata (Dark Mode).
- **NIE Variablen direkt überschreiben** (`$foo: blue;` in einer Anpassungsschicht) – das führt bei
  bundleübergreifender Kompilierung zu unvorhersehbaren Ergebnissen.
- **Immer `!default`:** `$foo: red !default;` setzt den Wert **nur**, wenn die Variable noch nicht definiert ist;
  die Priorität folgt so der **Ladereihenfolge** der Assets (früher geladene Datei gewinnt). Eine spätere
  Bibliotheksdatei mit `$foo: blue !default` wird dann ignoriert.
- Kompilierreihenfolge (konzeptionell, laut Quelle unvollständig): `web.dark_mode_variables` →
  `web._assets_primary_variables` (Enterprise vor Community; Primär- vor Komponenten-Variablen) →
  `web._assets_bootstrap` → `web.assets_backend` (CSS-Variablen-Definition und kontextuelle Anpassungen).
- **Folgerung für eigene Module:** Variablen mit `!default` definieren und im richtigen Bundle laden (siehe
  Assets-Operationen `prepend`/`before`/`after` im JS-Framework-Destillat); Stilnamen und Format nach Konventionen
  Abschnitt 6 (`$o-<modul>-…`, lokale `$-name`, CSS-Variablen BEM).
