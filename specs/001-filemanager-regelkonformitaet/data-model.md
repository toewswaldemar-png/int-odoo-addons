# Data Model: Regelkonformität und Prüfautomatik

Es entstehen keine Tabellen und keine Felder. Dieses Dokument beschreibt die Daten der
Prüfung: Matrixzeile, LEGACY-Ableitung, Probekatalog und die XML-ID-Zuordnung der
Migration.

## 1. Regel (Zeile der Prüfmatrix `pruefmatrix_2026-10-04.md`)

| Feld                 | Bedeutung                                                                                                                               |
| -------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| Nr.                  | `<Destillat-Kürzel>-<laufende Nummer>`, z. B. `ORM-014`; stabil, wird nie wiederverwendet                                               |
| Regel                | die Aussage in einem Satz, wie im Destillat (MUSS/NIE/muss)                                                                             |
| Destillat, Abschnitt | Datei und Überschrift der Regel                                                                                                         |
| Prüfweg              | `W:<Werkzeug>` (pre-commit-Hook, `test_lint`-Test, odoo-ls, `jscheck`, `owlcheck`, ESLint, Hoot, Odoo-Test) oder `R:<Checklistenpunkt>` |
| Fundstelle           | Datei und Funktion/Abschnitt in Referenz oder Core, die die Regel belegt                                                                |
| Ergebnis             | `stimmt`, `überholt` (Destillat korrigiert), `ergänzt` (Hinweis aufgenommen)                                                            |
| Probe                | Nr. des Probefalls (Abschnitt 3), falls das Werkzeug die Regel erkennen soll                                                            |

**Regeln**: jede Regel hat genau einen Prüfweg (bei Werkzeug und Review zugleich zählt
das Werkzeug); `Ergebnis` ist nicht leer; jede Zeile mit `W:` hat einen Probefall oder
die Angabe `Probe: Core-Test`.

## 2. LEGACY-Ableitung

Eingabe: `git diff --name-only int_filemanager-v1 -- int_filemanager` und
`git ls-tree -r --name-only int_filemanager-v1`.

| Menge         | Definition                                  | Wirkung                                     |
| ------------- | ------------------------------------------- | ------------------------------------------- |
| Altbestand    | Datei im Tag und unverändert im Arbeitsbaum | im LEGACY-Block, von pre-commit ausgenommen |
| Umgeschrieben | Datei im Tag und geändert oder gelöscht     | nicht im Block, wird vollständig geprüft    |
| Neu           | Datei nicht im Tag                          | nicht im Block, wird vollständig geprüft    |

Ganze Altmodule (`int_generic`, `int_fleet_kanban_width`, `int_legacy_erp_import`,
`int_repair_workshop`, `onlyoffice_odoo`) bleiben als Verzeichnis ausgenommen.
**Zustandsübergang:** eine Altdatei wird geändert → der Hook `legacy-excludes-in-sync`
schlägt fehl → `sync_legacy_excludes.py` nimmt sie aus dem Block → ab dann gilt sie als
umgeschrieben. Die Rückrichtung gibt es nicht.

**Startmenge der 12 Dateien (Stand 2026-10-04):** `controllers/main.py`,
`controllers/portal.py`, `index_utils.py`, `models/filemanager_extraction_pattern.py`,
`models/filemanager_file.py`, `publish_service.py`, `security/security.xml`,
`static/src/int_filemanager/native_ui/document_review_dialog.js`,
`…/document_review_dialog.xml`, `views/filemanager_extracted_value_views.xml`,
`views/filemanager_file_form_view.xml`, `write_service.py`.

## 3. Probekatalog (`tools/v2check/probe/probe_rules/`)

Je Fall eine Datei oder ein Abschnitt mit genau einem Verstoß und dem erwarteten Hook
mit Meldung. `run_probe.py` kopiert das Probemodul mit der Prüfkonfiguration in ein
temporäres Git-Verzeichnis, führt `pre-commit run --files …` aus und vergleicht mit
`expected.json`.

| Nr. | Verstoß                             | Erwartet von                                                       |
| --- | ----------------------------------- | ------------------------------------------------------------------ |
| P01 | `print(...)`                        | pylint-odoo `print-used`                                           |
| P02 | `cr.commit()`                       | `invalid-commit`                                                   |
| P03 | `except …: pass`                    | `except-pass`                                                      |
| P04 | SQL mit `%` im Text                 | `sql-injection`                                                    |
| P05 | `search([])` ohne `limit`           | `no-search-all`                                                    |
| P06 | `eval(...)`                         | `eval-used`                                                        |
| P07 | `string=` gleich Feldname           | `attribute-string-redundant`                                       |
| P08 | statischer Text in `UserError`      | `translation-required`                                             |
| P09 | `_("…" % x)`                        | `translation-not-lazy`                                             |
| P10 | f-String in `env._`                 | `translation-fstring-interpolation`                                |
| P11 | `unlink` mit `raise` ohne `super`   | `no-raise-unlink`, `method-required-super`                         |
| P12 | Schreiben in Compute-Methode        | `no-write-in-compute`                                              |
| P13 | `self._cr`                          | `deprecated-self-cr`                                               |
| P14 | `eval` in JS                        | ESLint `no-eval`                                                   |
| P15 | `var` im globalen Scope in JS       | ESLint `no-implicit-globals`                                       |
| P16 | doppelte XML-ID                     | `oca-checks-odoo-module` `xml-duplicate-record-id`                 |
| P17 | `position="replace"` ohne Priorität | `oca-checks-odoo-module` `xml-view-dangerous-replace-low-priority` |
| P18 | `self._context`                     | neu: `pygrep` `odoo-deprecated-env`                                |
| P19 | `self._uid`                         | neu: `odoo-deprecated-env`                                         |
| P20 | `domain += [...]`                   | neu: `odoo-domain-concat`                                          |
| P21 | `<tree>`                            | neu: `odoo-xml-deprecated`                                         |
| P22 | `attrs=`                            | neu: `odoo-xml-deprecated`                                         |
| P23 | `t-raw`                             | neu: `odoo-xml-deprecated`                                         |
| P24 | `"application": False` im Manifest  | neu: `odoo-manifest-defaults`                                      |
| P25 | `localStorage` direkt im JS         | neu: ESLint `no-restricted-globals`                                |
| P26 | `sessionStorage` direkt im JS       | neu: ESLint `no-restricted-globals`                                |
| P27 | `window.location` im JS             | neu: ESLint `no-restricted-properties`                             |
| P28 | Commit-Kopfzeile ohne Tag           | neu: `commit-subject`                                              |
| P29 | Commit-Kopfzeile mit `[DOC]`        | neu: `commit-subject`                                              |
| P30 | Commit-Kopfzeile über 80 Zeichen    | neu: `commit-subject`                                              |

Nicht in pre-commit (laufen in `v2check.sh`): Parameter `ids`/`context` (`test_naming`),
Standardschlüssel `application`/`auto_install` (`test_manifests`), Import aus `odoo.orm`
(`test_orm_import`).

**Heute erkannt: 18 von den ersten 24 des früheren Probemoduls**; Ziel dieses Plans:
alle 30 Fälle.

## 4. XML-ID-Zuordnung der Migration `19.0.1.24.0`

Schema (CG 5): View `<model>_view_<typ>[_<zusatz>]`, Aktion `<model>_action[_<detail>]`,
Menü `<model>_menu[_<zweck>]`, Regel `<model>_rule_<zweck>`. Neu, alt jeweils mit
Modulpräfix `int_filemanager.` bei der Umbenennung.

| Alt                                   | Neu                                           |
| ------------------------------------- | --------------------------------------------- |
| `int_filemanager_node_search`         | `int_filemanager_node_view_search`            |
| `int_filemanager_node_list`           | `int_filemanager_node_view_list`              |
| `int_filemanager_node_kanban`         | `int_filemanager_node_view_kanban`            |
| `int_filemanager_node_trash_list`     | `int_filemanager_node_view_list_trash`        |
| `int_filemanager_node_share_form`     | `int_filemanager_node_view_form_share`        |
| `int_filemanager_node_details_form`   | `int_filemanager_node_view_form_details`      |
| `action_int_filemanager_node`         | `int_filemanager_node_action`                 |
| `action_int_filemanager_node_details` | `int_filemanager_node_action_details`         |
| `action_int_filemanager_node_trash`   | `int_filemanager_node_action_trash`           |
| `action_int_filemanager_node_share`   | `int_filemanager_node_action_share`           |
| `menu_int_filemanager_v2_root`        | `int_filemanager_node_menu_root`              |
| `rule_node_scope_read`                | `int_filemanager_node_rule_scope_read`        |
| `rule_node_scope_write`               | `int_filemanager_node_rule_scope_write`       |
| `rule_node_scope_purge`               | `int_filemanager_node_rule_scope_purge`       |
| `rule_revision_scope_read`            | `int_filemanager_revision_rule_scope_read`    |
| `rule_scope_manage_write`             | `int_filemanager_scope_rule_manage_write`     |
| `rule_share_node_writers`             | `int_filemanager_share_rule_node_writers`     |
| `rule_upload_own_records`             | `int_filemanager_upload_rule_own_records`     |
| `rule_operation_own_records`          | `int_filemanager_operation_rule_own_records`  |
| `rule_zip_job_own_records`            | `int_filemanager_zip_job_rule_own_records`    |
| `rule_field_value_scope_read`         | `int_filemanager_field_value_rule_scope_read` |

Unverändert, weil sie dem Schema folgen oder keine Regel dafür gilt:
`int_filemanager_node_view_form_page`, `_view_list_page`, `_view_list_contents`,
`_view_search_contents`, `int_filemanager_node_action_page`,
`…_action_page_view_list`/`_form`, `int_filemanager_node_menu_page`, die Cron-IDs
`ir_cron_int_filemanager_*` (Odoo-Kernstil), die Datensätze
`extraction_field_*`/`extraction_rule_*`, alle `access_int_filemanager_*` der CSV. Die
Altdateien (`menu.xml`, `security.xml` usw.) behalten ihre IDs.

**Zustände der Datenbank:** frisch (kein alter Eintrag) → Migration ändert nichts; Stand
`19.0.1.23.0` (alte IDs) → alle 21 werden umbenannt, bestehende Verweise
(`ir.model.data`, Übersetzungen) bleiben gültig; Teilstand (einige schon neu) → nur die
vorhandenen alten werden umbenannt, kein Abbruch. Verweise im Code:
`controller_mutations.js` (Aktionen Details und Share), `folder_tree.js` (Papierkorb),
`tools/v2check/po_tool.py`, `tools/v2check/ui_instance.sh`, `i18n/de.po`.

## 5. Optionale Bereinigung (Entscheidung offen)

Bestehende Follower-Zeilen für `int_filemanager.node` (`mail.followers`) aus der Zeit
vor der Behebung: entweder lassen oder in einer Migration löschen. Betrifft nur
Datenbanken mit dem Branch-Stand; Entscheidung des Nutzers vor einer Bestandsübernahme.
