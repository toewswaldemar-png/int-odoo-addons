# Implementation Plan: int_filemanager erfüllt die verbindlichen Regeln, und die Prüfautomatik erzwingt sie

**Branch**: `feature/int-filemanager-v2` (Spec-Ordner
`001-filemanager-regelkonformitaet`) | **Date**: 2026-10-04 | **Spec**:
[spec.md](spec.md) **Input**: Feature specification from
`/specs/001-filemanager-regelkonformitaet/spec.md`

## Summary

Die Prüfautomatik wird lückenlos und blockierend, das Regelwerk wird gegen Referenzen
und Core belegt, und der neue Code von `int_filemanager` wird auf die Regeln gebracht.
Vier Bausteine:

1. **Durchsetzung** (FR-001 bis FR-007, FR-019): der LEGACY-Block wird aus dem
   Git-Vergleich zum Tag `int_filemanager-v1` abgeleitet statt von Hand gepflegt; neue
   blockierende Prüfungen kommen aus den vorhandenen Bordmitteln von pre-commit
   (`pygrep`-Hooks, ESLint-Regeln, `commit-msg`-Stufe); ein wiederholbares Probemodul
   belegt, dass jede prüfbare Regel erkannt wird; `PYTHONUTF8` und die Hook-Installation
   werden per Skript auf dem Arbeitsrechner eingerichtet.
2. **Dokumentation** (FR-008 bis FR-010): eine Prüfmatrix
   `docs/pruefmatrix_2026-10-04.md` führt je Regel Prüfweg, Fundstelle in Referenz oder
   Core und Ergebnis; das Prüfautomatik-Dokument wird an die Konfiguration angeglichen;
   überholte Regeln werden korrigiert.
3. **Code** (FR-002, FR-012 bis FR-018): die 12 Altdateien werden bereinigt
   (Formatierung als eigener Schritt), `mail_create_nosubscribe`, SQL-Form,
   `browser`-Objekt, Manifest, Testhilfen, XML-IDs mit Migration.
4. **Browser-Tests** (FR-006, FR-007, FR-011): 75 Node-Testfälle werden Hoot-Tests
   (`@odoo/hoot`), dazu eine Tour; sie laufen über Odoos eigenen Läufer
   `WebSuite.test_unit_desktop` in einem Test-Image mit Chrome.

## Technical Context

**Language/Version**: Python 3.12 (Odoo 19.0 im Image `odoo:19.0-hm-test`, Ubuntu
24.04), JavaScript (Owl 2.8.4, native ES-Module), Bash/PowerShell, YAML (pre-commit)
**Primary Dependencies**: pre-commit 4.6.2 (`pygrep`, `commit-msg`), ruff 0.13.0,
pylint-odoo 10.0.8, `odoo-pre-commit-hooks` 0.1.7, ESLint 9.35.0 +
`eslint-plugin-jsdoc`, Prettier 3.6.2, Odoos `test_lint`, odoo-ls, Hoot (im Core:
`web/static/lib/hoot`), `odoo/upgrade-util` (neu, nicht im Image), Chrome und
`websocket-client` (neu, nicht im Image) **Storage**: PostgreSQL der Testinstanz
(`fmtest_pg` auf Tower, Wegwerf-Datenbanken); keine neuen Tabellen. Die Migration
schreibt `ir_model_data`. **Testing**: Odoo-Tests (645) über `tools/v2check/tests.sh`;
Hoot-Tests und Tour über `WebSuite`/`HttpCase`; `v2check.sh`, `jscheck.sh`,
`owlcheck.sh`; Probemodul (neu) **Target Platform**: Arbeitsrechner Windows 10 (Git
Bash, `py -3.13`) für pre-commit; Tower (Unraid, Docker) für Odoo-gebundene Prüfungen
**Project Type**: Odoo-Addon-Repo mit Prüf-Werkzeugen (`tools/`, `scripts/`)
**Performance Goals**: pre-commit auf allen geänderten Dateien unter 60 s; `v2check`
unverändert (ca. 8 Minuten); Hoot-Lauf des Moduls unter 5 Minuten **Constraints**: nie
`pre-commit run --all-files` im Arbeitsbaum; nur Wegwerf-Container und -Datenbanken auf
Tower, nie die Live-Instanz; Commits nur auf Ansage; Downloads (Chrome, upgrade-util)
brauchen vorher eine ausdrückliche Freigabe **Scale/Scope**: 161 geänderte oder neue
Dateien, 12 Altdateien mit zusammen 51 pylint-Befunden und 4 Zeilenlängen-Befunden (bei
120 Zeichen), 21 XML-IDs, 24 Owl-Templates, 17 Regel-Destillate, 75 Testfälle

## Constitution Check

_GATE: Must pass before Phase 0 research. Re-check after Phase 1 design._

| Grundsatz                       | Prüfung                                                                                                                                                                                                                                                                                                                  | Stand     |
| ------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | --------- |
| I. Odoo-Core vor Eigenbau       | Für jeden Baustein steht in `research.md` die Fundstelle: Hoot-Läufer (`web/tests/test_js.py`), Chrome-Suche (`tests/common.py::_find_executable`), `pygrep`/`commit-msg` (pre-commit selbst), `mail_create_nosubscribe` (`mail/models/mail_thread.py`), `test_manifests`. Kein Eigenbau eines Testläufers oder Linters. | bestanden |
| II. Odoo-19-Regeln              | Neuer Code folgt den Regeln; Abweichungen stehen unter Complexity Tracking                                                                                                                                                                                                                                               | bestanden |
| III. Owl 2.8.4                  | Hoot-Tests und Tour nutzen nur Owl-2-API; `owlcheck` wird auf alle Templates erweitert                                                                                                                                                                                                                                   | bestanden |
| IV. Prüfautomatik erzwingt      | Kern dieses Plans; neue Regeln gehen in die Konfiguration; Regeln ohne Werkzeug stehen in der Prüfmatrix                                                                                                                                                                                                                 | bestanden |
| V. Verifizieren                 | Offene Annahmen (Chrome, upgrade-util, Hook-Verhalten) sind in `research.md` geprüft oder als Freigabe-Schritt in den Aufgaben markiert                                                                                                                                                                                  | bestanden |
| VI. Produktentscheidungen vorab | Fünf Entscheidungen am 2026-10-04 getroffen (Clarifications)                                                                                                                                                                                                                                                             | bestanden |
| VII. Ursachen beheben           | Jede Behebung mit Test, der ohne sie fehlschlägt (Follower, XML-ID-Migration); keine Handeingriffe in Datenbanken                                                                                                                                                                                                        | bestanden |

**Post-Design-Check (nach Phase 1):** unverändert bestanden; eine begründete Abweichung
(Cron-Commit im Blob-GC, siehe unten).

## Project Structure

### Documentation (this feature)

```text
specs/001-filemanager-regelkonformitaet/
├── plan.md              # Dieser Plan
├── research.md          # Phase 0: belegte Entscheidungen
├── data-model.md        # Phase 1: Regelmatrix, LEGACY-Ableitung, XML-ID-Zuordnung
├── quickstart.md        # Phase 1: Ablauf zur Überprüfung
├── contracts/
│   └── pruefwerkzeuge.md  # Phase 1: Aufruf, Ausgabe und Exit-Codes der Werkzeuge
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
.pre-commit-config.yaml                  # neue pygrep- und commit-msg-Hooks, Ableitung des LEGACY-Blocks
eslint.config.cjs                        # no-restricted-globals/-properties, definedTags, Regeln aufräumen
scripts/lint/
├── sync_legacy_excludes.py              # Block aus `git diff` zum Tag ableiten; --check strenger
└── setup_windows.ps1                    # NEU: PYTHONUTF8, pre-commit- und commit-msg-Hook installieren
tools/v2check/
├── owlcheck/merge_templates.py          # Glob auf **/*.xml
├── probe/                               # NEU: Probemodul `probe_rules/` und run_probe.py
├── hoot.sh                              # NEU: Hoot-Lauf auf Tower
├── tests.sh                             # tests/tower hierher
└── tower/                               # NEU: verlegt aus int_filemanager/tests/tower/
tools/docker/Dockerfile.test             # NEU: odoo:19.0-hm-test + Chrome + websocket-client + upgrade-util
Dockerfile                               # upgrade-util ergänzen
docs/
├── pruefautomatik_2026-10-02.md         # angleichen (Werkzeuge, Aufruf, Zahlen, Windows)
├── pruefmatrix_2026-10-04.md            # NEU: Regel → Prüfweg → Fundstelle → Ergebnis (bewusst außerhalb von odoo_regeln/,
│                                        #      damit die Pflicht-Lektüre jeder Sitzung nicht wächst)
└── odoo_regeln/odoo_regeln_*.md         # korrigierte Destillate, neues Prüfdatum
int_filemanager/
├── __manifest__.py                      # installable raus, external_dependencies, Version 19.0.1.24.0, web.assets_unit_tests/tests
├── migrations/19.0.1.24.0/pre-migrate.py   # XML-ID-Umbenennung
├── models/int_filemanager_node.py       # mail_create_nosubscribe, tracking
├── models/int_filemanager_blob.py, int_filemanager_derivative.py, int_filemanager_upload.py   # SQL-Form, flush_model
├── models/filemanager_file.py, controllers/main.py, controllers/portal.py, index_utils.py,
│   publish_service.py, write_service.py, models/filemanager_extraction_pattern.py            # 12 Altdateien bereinigt
├── views/ und security/ (Dateien der 21 umbenannten XML-IDs)
├── static/src/int_filemanager/v2/       # browser-Objekt statt Globals
├── static/tests/                        # *.test.js (Hoot) statt js/*.test.mjs
├── static/tests/tours/                  # Tour
├── tests/test_v2_followers.py, test_v2_migration_xmlids.py, test_v2_hoot.py   # NEU
└── tests/*.py                           # new_test_user statt _make_user
```

**Structure Decision**: Die Änderungen liegen im Modul `int_filemanager`, in den
Prüf-Konfigurationsdateien der Repo-Wurzel, in `scripts/lint/` und `tools/v2check/`
sowie in `docs/odoo_regeln/`. Es gibt kein neues Modul. Hilfsskripte verlassen das
Modulverzeichnis (`tests/tower` nach `tools/v2check/tower/`). Das Test-Image ist eine
Datei unter `tools/docker/`, damit das Produktions-`Dockerfile` unverändert klein
bleibt.

## Complexity Tracking

> Nur Abweichungen von den Regeln, die begründet bleiben.

| Abweichung                                                                                   | Warum nötig                                                                                                                                      | Einfachere Alternative abgelehnt, weil                                                                                                                             |
| -------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `cr.commit()` auf dem Cron-Cursor in `_gc_blobs` (zwei Stellen, `pylint: disable`)           | Die Tabellensperre muss in einer frischen Transaktion beginnen und mit dem Commit enden; Odoo macht es in `ir_attachment._gc_file_store` genauso | `_commit_progress` committet nach Stapeln, nicht um eine Sperre zu halten und zu lösen; der Plan trägt die Ausnahme in `odoo_regeln_actions_cron_http_reports` ein |
| Zwei `except Exception` in Crons (`int_filemanager_upload.py`, `int_filemanager_zip_job.py`) | Ein fehlerhafter Auftrag darf den Cron nicht beenden; beide loggen mit `_logger.exception` und markieren den Auftrag als fehlgeschlagen          | konkrete Typen können nicht alle Fehler einer Fremdbibliothek benennen; Begründung am Code und in der Matrix                                                       |
| Eigenes Test-Image mit Chrome statt Chrome im Produktionsimage                               | Chrome gehört nicht in das Produktions-Image von HM-SRV                                                                                          | alles in ein Image: größeres Produktionsimage ohne Nutzen                                                                                                          |
