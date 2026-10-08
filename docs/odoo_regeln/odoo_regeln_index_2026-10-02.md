# Odoo 19 Regeln – Index der Destillate

Die Destillate fassen die Regeln der offiziellen Odoo-19-Dokumentation zusammen und ergänzen sie, wo der Odoo-Quelltext mehr oder anderes festlegt:

- Coding Guidelines: <https://www.odoo.com/documentation/19.0/contributing/development/coding_guidelines.html>
- Developer Reference mit allen Unterseiten: <https://www.odoo.com/documentation/19.0/developer/reference.html>
- Odoo-19-Quelltext (lokale Kopie `docs/odoo/`, Branch 19.0; nicht Teil des Repos, muss mit dem Odoo-Image übereinstimmen)

**Quellen und Rangfolge:** Nur Odoo-Quelltext und offizielle Odoo-Dokumentation. Bei Widerspruch gilt der Quelltext vor der Doku. Aussagen, die nur im Quelltext stehen, sind in den Dateien mit **[Code]** gekennzeichnet.
Es gibt keine Regeln aus anderen Quellen (OCA, eigene Hausregeln). Stand der Überarbeitung: 2026-10-08.
Die lokale Doku-Kopie unter `docs/odoo19_reference/` ist an einigen Stellen veraltet; die Destillate folgen dort dem Quelltext.

## Dateien

| Datei | Quelle (`content/…`) | Inhalt |
|---|---|---|
| `odoo_regeln_coding_guidelines_2026-10-02.md` | `contributing/development/coding_guidelines.rst`, `test_lint`, `ruff.toml`, `web/tooling` | Modul, Manifest, Python, XML, JS/SCSS |
| `odoo_regeln_git_guidelines_2026-10-02.md` | `contributing/development/git_guidelines.rst` | Commit-Nachrichten |
| `odoo_regeln_orm_2026-10-02.md` | `developer/reference/backend/orm.rst`, `orm/changelog.rst` | Modelle, Felder, Recordsets, Domains, Environment, SQL, Vererbung, Changelog 15.2 → 19.0 |
| `odoo_regeln_security_2026-10-02.md` | `backend/security.rst` | ACL, Record Rules, Feldzugriff, Security Pitfalls |
| `odoo_regeln_performance_2026-10-02.md` | `backend/performance.rst` | Batching, Komplexität, Indizes, Profiler |
| `odoo_regeln_testing_2026-10-02.md` | `backend/testing.rst` | Python-Tests, Tags, Tours, Query-Counts |
| `odoo_regeln_data_manifest_2026-10-02.md` | `backend/data.rst`, `backend/module.rst` | XML/CSV-Daten, Manifest |
| `odoo_regeln_actions_cron_http_reports_2026-10-02.md` | `backend/actions.rst`, `backend/http.rst`, `backend/reports.rst` | Aktionen, Cron, Controller, QWeb-Berichte |
| `odoo_regeln_mixins_2026-10-02.md` | `backend/mixins.rst` | `mail.thread`, Alias, Aktivitäten, UTM, Website, Rating |
| `odoo_regeln_js_framework_2026-10-02.md` | `frontend/framework_overview.rst`, `javascript_modules.rst`, `assets.rst`, `registries.rst`, `services.rst`, `hooks.rst`, `patching_code.rst`, `javascript_reference.rst` (ohne Widgets), `owl_components.rst`, `error_handling.rst`, `odoo_editor.rst`, `mobile.rst` | JS-Module, Assets, Registries, Services, Owl, Patchen, Fehler |
| `odoo_regeln_js_fields_2026-10-02.md` | `frontend/javascript_reference.rst` (Widgets, Client-Aktionen) | Feld-Widget-Katalog, eigene Felder |
| `odoo_regeln_qweb_2026-10-02.md` | `frontend/qweb.rst` | QWeb-Direktiven, Escaping, Vererbung |
| `odoo_regeln_js_tests_2026-10-02.md` | `frontend/unit_testing.rst`, `unit_testing/hoot.rst`, `web_helpers.rst`, `mock_server.rst` | Hoot, Web-Helfer, Mock-Server |
| `odoo_regeln_views_2026-10-02.md` | `user_interface/view_records.rst`, `view_architectures.rst`, `view_architectures/*.rst` | View-Records, Vererbung, alle View-Typen |
| `odoo_regeln_ui_icons_scss_2026-10-02.md` | `user_interface/icons.rst`, `scss_inheritance.rst` | Icons, SCSS `!default` |
| `odoo_regeln_api_cli_upgrade_2026-10-02.md` | `external_api.rst`, `external_rpc_api.rst`, `extract_api.rst`, `cli.rst`, `upgrades/*.rst`, `standard_modules*` | JSON-2, RPC (veraltet), Extract, CLI, Upgrade-Skripte |

## Verwendung

- **Vor Code in einem Bereich** die zugehörige Datei lesen (Tabelle). Bei Zweifel über API-Details (Signaturen, Feldparameter, View-Attribute) im Quelltext nachsehen; wo die Doku autodoc ist, steht in den Destillaten nur, was in der `.rst` selbst steht.
- **Grenzen der Quelle:** Parameter und Signaturen (`create`, `write`, `search`, `Field`-Parameter, `@api.*`, `Request`, `IrCron` …) stehen nur im Docstring des Quellcodes. Der Core liegt im Container unter `/usr/lib/python3/dist-packages/odoo/`.
- **Nicht auf Odoo 19 aktualisierte Quellabschnitte:** `qweb.rst` Abschnitt JavaScript (altes System) und `mobile.rst`.
- **Enterprise-only** (Cohort, Gantt, Grid, Map, Mobile-App): in Community nicht verfügbar, nur nachschlagen.

## Pflege

- Quelle neu holen: `git clone --depth 1 --branch 19.0 https://github.com/odoo/documentation`. Geänderte Dateien: `git diff --stat <alter-hash>..HEAD -- content/developer/reference content/contributing/development` (braucht tieferen Klon).
- Bei Änderung: betroffene Destillate anpassen, Prüfdatum oben aktualisieren.
