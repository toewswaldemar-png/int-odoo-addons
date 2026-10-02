# Odoo 19 Regeln – Index der Destillate

Stand: 2026-10-02. Quelle: `odoo/documentation`, Branch `19.0`, Commit `eee2e56e2998b754e43758f4854137ae073789fb`
(2026-10-02), `.rst`-Dateien (nicht das gerenderte HTML). Aufgabe: die Odoo-19-Dokumentation
- Coding Guidelines: <https://www.odoo.com/documentation/19.0/contributing/development/coding_guidelines.html>
- Developer Reference mit allen Unterseiten: <https://www.odoo.com/documentation/19.0/developer/reference.html>

als **verbindliche Regeln** festhalten (Entscheidung 2026-10-02: Umfang **alles**, Reihenfolge **erst Destillate**,
dann Prüfautomatik).

## Aufbau der Verbindlichkeit (drei Schichten)

1. **`CLAUDE.md`** – kurze Pflichtregel mit Verweis hierher (immer geladen).
2. **Diese Destillate** – pro Themenbereich eine Datei: Regeln der Quelle, Fallstricke, Quellverweis, Prüfdatum.
   Sie sind **keine Kopie** der Dokumentation (zu groß, veraltet schnell), sondern ihre Regeln und Entscheidungspunkte.
3. **Maschinelle Prüfung** (pre-commit nach OCA-Vorlage, Odoos `test_lint`, odoo-ls) – **eingerichtet 2026-10-02**,
   Stand, Aufruf und Befunde im Altbestand: `docs/pruefautomatik_2026-10-02.md`. Erst sie macht Regeln erzwingbar;
   Regeln ohne Werkzeug bleiben Review-Checkliste in den Destillaten.

## Dateien

| Datei | Quelle (`content/…`) | Inhalt |
|---|---|---|
| `odoo_konventionen_2026-09-26.md` (+ Abschnitt 11) | `contributing/development/coding_guidelines.rst`, `git_guidelines.rst` | Coding-/Git-Guidelines, OCA, `test_lint`; Abgleich 2026-10-02 in Abschnitt 11 |
| `odoo_regeln_orm_2026-10-02.md` | `developer/reference/backend/orm.rst`, `orm/changelog.rst` | Modelle, Felder, Recordsets, Domains, Environment, SQL, Vererbung, Changelog 15.2 → 19.0 |
| `odoo_regeln_security_2026-10-02.md` | `backend/security.rst` | ACL, Record Rules, Feldzugriff, Security Pitfalls |
| `odoo_regeln_performance_2026-10-02.md` | `backend/performance.rst` | Batching, Komplexität, Indizes, Profiler |
| `odoo_regeln_testing_2026-10-02.md` | `backend/testing.rst` | Python-Tests, Tags, Tours, Query-Counts |
| `odoo_regeln_data_manifest_2026-10-02.md` | `backend/data.rst`, `backend/module.rst` | XML/CSV-Daten, Manifest |
| `odoo_regeln_actions_cron_http_reports_2026-10-02.md` | `backend/actions.rst`, `backend/http.rst`, `backend/reports.rst` | Aktionen, Cron, Controller, QWeb-Berichte |
| `odoo_regeln_mixins_2026-10-02.md` | `backend/mixins.rst` | `mail.thread`, Alias, Aktivitäten, UTM, Website, Rating |
| `odoo_regeln_js_framework_2026-10-02.md` | `frontend/framework_overview.rst`, `javascript_modules.rst`, `assets.rst`, `registries.rst`, `services.rst`, `hooks.rst`, `patching_code.rst`, `javascript_reference.rst` (ohne Widgets), `owl_components.rst`, `error_handling.rst`, `odoo_editor.rst`, `mobile.rst` | JS-Module, Assets, Registries, Services, Owl, Patchen, Fehler |
| `odoo_regeln_js_fields_2026-10-02.md` | `frontend/javascript_reference.rst` (Widgets, Client-Aktionen) | Feld-Widget-Katalog |
| `odoo_regeln_qweb_2026-10-02.md` | `frontend/qweb.rst` | QWeb-Direktiven, Escaping, Vererbung |
| `odoo_regeln_js_tests_2026-10-02.md` | `frontend/unit_testing.rst`, `unit_testing/hoot.rst`, `web_helpers.rst`, `mock_server.rst` | Hoot, Web-Helfer, Mock-Server |
| `odoo_regeln_views_2026-10-02.md` | `user_interface/view_records.rst`, `view_architectures.rst`, `view_architectures/*.rst` | View-Records, Vererbung, alle View-Typen |
| `odoo_regeln_ui_icons_scss_2026-10-02.md` | `user_interface/icons.rst`, `scss_inheritance.rst` | Icons, SCSS `!default` |
| `odoo_regeln_api_cli_upgrade_2026-10-02.md` | `external_api.rst`, `external_rpc_api.rst`, `extract_api.rst`, `cli.rst`, `upgrades/*.rst`, `standard_modules*` | JSON-2, RPC (veraltet), Extract, CLI, Upgrade-Skripte |

## Verwendung

- **Vor Code in einem Bereich** die zugehörige Datei lesen (Tabelle). Bei Konflikt gilt: **Odoo-Quelle vor
  Destillat vor Bauchgefühl** – und die `CLAUDE.md`-Regel "vor jeder Eigenbau-Aussage Odoo-Core prüfen" bleibt
  unverändert. Die Destillate ersetzen nicht den Core-Grep.
- **Grenzen der Quelle** (jede Datei nennt sie oben): Teile der Reference sind *autodoc* – Parameter und Signaturen
  (`create`, `write`, `search`, `Field`-Parameter, `@api.*`, `Request`, `IrCron` …) stehen nur im Docstring des
  Odoo-Quellcodes. Das Destillat enthält dort nur, was in der `.rst` selbst steht. Der Core liegt im Container unter
  `/usr/lib/python3/dist-packages/odoo/` (nicht in diesem Repo, nicht in der Cloud-Sitzung).
- **Teilweise veraltete Quelle** (nicht nur Tippfehler): `mixins.rst` (Beispielcode), `framework_overview.rst`
  (`env._t`), `qweb.rst` Abschnitt JavaScript (altes System), `mobile.rst`, Cron-Beispiel (Syntaxfehler),
  Client-Aktions-Beispiel. Die Destillate markieren das.
- **Enterprise-only** (Cohort, Gantt, Grid, Map, Mobile-App): in Community nicht verfügbar, nur nachschlagen.

## Pflege

- Quelle neu holen: `git clone --depth 1 --branch 19.0 https://github.com/odoo/documentation`, Commit-Hash vergleichen.
  Geänderte Dateien: `git diff --stat <alter-hash>..HEAD -- content/developer/reference content/contributing/development`
  (braucht tieferen Klon; Hash steht in jeder Datei).
- Bei Änderung: betroffene Destillate anpassen, **Prüfdatum und Hash oben aktualisieren**, Dateiname-Datum erst bei
  grundlegendem Neuaufbau ändern (CLAUDE.md verweist nur auf diesen Index).
- Neue Regel, die maschinell prüfbar ist → in die Prüfkonfiguration (Schicht 3), nicht nur in Prosa.

## Offene Folgepunkte

1. Prüfautomatik: Läufe auf Tower und Arbeitsrechner, Altbefunde und offene Entscheidungen siehe
   `docs/pruefautomatik_2026-10-02.md` (Abschnitte 3–5).
2. Stichprobe, ob bestehende Module gegen die Destillate verstoßen (z. B. rohes SQL ohne `SQL`, `_cr`/`_context`,
   Listen-Domains, fehlendes `flush_model`/`invalidate_*`); Ergebnis in die Übergabe-Dokumente von `int_filemanager`.
3. Destillate durch Review gegen die Quelle prüfen lassen, bevor sie als abgenommen gelten (sie wurden in einem
   Durchgang erstellt, nicht gegenvalidiert).
