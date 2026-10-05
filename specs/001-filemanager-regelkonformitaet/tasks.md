---
description: "Aufgabenliste: int_filemanager Regelkonformität und Prüfautomatik"
---

# Tasks: int_filemanager erfüllt die verbindlichen Regeln, und die Prüfautomatik erzwingt sie

**Input**: Design documents from `/specs/001-filemanager-regelkonformitaet/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md,
contracts/pruefwerkzeuge.md, quickstart.md **Tests**: Von der Spezifikation verlangt
(FR-005 Probemodul, FR-011 Hoot und Tour, FR-012 Follower-Test, FR-018 Migrationstest).
Die Probe und die Tests stehen vor der Umsetzung und müssen zuerst fehlschlagen.
**Organization**: Nach Nutzergeschichten (US1 bis US5) gruppiert. Pfade sind relativ zur
Repo-Wurzel `int-odoo-addons/`.

## Format: `[ID] [P?] [Story] Beschreibung mit Dateipfad`

- **[P]**: parallel möglich (andere Datei, keine offene Abhängigkeit)
- **Commits**: nur auf ausdrückliche Ansage des Nutzers; die Vorschläge in den Aufgaben
  sind Kopfzeilen im Format `[TAG] int_filemanager: …` (Commit-Regel FR-019: ohne
  `[DOC]`)
- **Prüfläufe auf Tower** nur in Wegwerf-Containern; die Live-Instanz bleibt unberührt
- **Downloads** (Chrome, `websocket-client`, `upgrade-util`) erst nach der Freigabe aus
  T003

## Phase 1: Setup

- [ ] T001 Ausgangsstand messen und in
      `specs/001-filemanager-regelkonformitaet/baseline.md` festhalten:
      `tools/v2check/v2check.sh`, `tools/v2check/jscheck.sh`,
      `tools/v2check/owlcheck.sh`,
      `node --test "int_filemanager/static/tests/js/*.test.mjs"`,
      `tools/v2check/tests.sh`; erwartet 0 neue Befunde, 54 Module, 19 Templates, 75
      Node-Tests, 645 Odoo-Tests
- [ ] T002 [P] `scripts/lint/setup_windows.ps1` anlegen: setzt `PYTHONUTF8=1` als
      Benutzervariable, führt `pre-commit install` und
      `pre-commit install --hook-type commit-msg` aus und prüft Python 3.13 und
      pre-commit 4.6.2 (Vertrag `contracts/pruefwerkzeuge.md`); Aufruf macht der Nutzer
- [ ] T003 Freigabe des Nutzers für Downloads einholen und in `research.md` (R5, R7)
      vermerken: Google Chrome `.deb` von `dl.google.com`, `websocket-client` (PyPI),
      `upgrade-util` (`git+https://github.com/odoo/upgrade-util@master`); Dateiname,
      Quelle und Größe nennen. Ohne Freigabe bleiben T047, T052, T069 bis T072 und T083
      offen

---

## Phase 2: Foundational (blockiert alle Nutzergeschichten)

**Zweck**: das Probemodul, an dem jede Durchsetzung gemessen wird. Es muss zuerst rot
laufen.

- [ ] T004 Probe-Gerüst anlegen: `tools/v2check/probe/run_probe.py` (kopiert
      `probe_rules/` und die Prüfkonfiguration in ein temporäres Git-Verzeichnis, führt
      `pre-commit run --files …` und `--hook-stage commit-msg` aus, vergleicht mit
      `expected.json`, Ausgabe `n/30 cases detected`),
      `tools/v2check/probe/expected.json` (30 Fälle P01 bis P30 aus `data-model.md`
      Abschnitt 3 mit Hook und Meldungsmuster),
      `tools/v2check/probe/probe_rules/__init__.py` und `__manifest__.py`
- [ ] T005 [P] Python-Probefälle P01 bis P13 und P18 bis P20 in
      `tools/v2check/probe/probe_rules/models/probe_python.py` (je ein Verstoß, mit
      Kommentar `# probe Pnn`)
- [ ] T006 [P] XML-Probefälle P16, P17, P21, P22, P23 in
      `tools/v2check/probe/probe_rules/views/probe_views.xml` (im Probe-Manifest unter
      `data` eingetragen, sonst meldet der Hook nur `file-not-used`)
- [ ] T007 [P] JS-Probefälle P14, P15, P25, P26, P27 in
      `tools/v2check/probe/probe_rules/static/src/probe.js`
- [ ] T008 [P] Manifest-Probefall P24 (`"application": False`) in
      `tools/v2check/probe/probe_rules/__manifest__.py`
- [ ] T009 [P] Commit-Probefälle P28 bis P30 als Dateien
      `tools/v2check/probe/probe_rules/commit_messages/p28_no_tag.txt`,
      `p29_doc_tag.txt`, `p30_too_long.txt` plus je ein gültiger Gegenfall `ok_fix.txt`,
      `ok_merge.txt`
- [ ] T010 Probe ausführen (`py -3.13 tools/v2check/probe/run_probe.py`), Ergebnis
      **muss rot sein** (erwartet 18 von 30 erkannt, die Fälle P18 bis P30 fehlen) und
      in `baseline.md` eintragen

**Checkpoint**: Probe läuft und zeigt die heutigen Lücken.

---

## Phase 3: User Story 1 - Ein Regelverstoß fällt vor dem Commit auf (Priority: P1) 🎯 MVP

**Goal**: Jede prüfbare Regel blockiert den Commit, für jede neue oder geänderte Datei,
lesbar auf Windows (FR-001 bis FR-004, FR-007, FR-014, FR-016, FR-019, FR-005).

**Independent Test**: `run_probe.py` meldet `30/30 cases detected`;
`pre-commit run --files` auf allen seit dem Tag geänderten Dateien in einer Kopie endet
mit Exit 0, und `sync_legacy_excludes.py --check` meldet keine geänderte Datei im Block.

### Code, den die neuen Prüfungen sonst blockieren würden

- [ ] T011 [US1] `int_filemanager/__manifest__.py`: `external_dependencies` für
      `pdfplumber`, `ocrmypdf`, `mutagen` eintragen (im Image `odoo:19.0-hm-test`
      vorhanden, geprüft) (FR-016); Version erst in T052 ändern
- [x] T012 [P] [US1] ENTFALLEN (Regel geändert: Zeitgeber, `fetch` und DOM sind frei,
      Speicher läuft schon über `browser`):
      `int_filemanager/static/src/int_filemanager/v2/uploads_service.js`: `setTimeout`
      (Zeile 97
- [x] T013 [P] [US1] ENTFALLEN (Regel geändert: Zeitgeber, `fetch` und DOM sind frei,
      Speicher läuft schon über `browser`):
      `int_filemanager/static/src/int_filemanager/v2/controller_mutations.js`:
      `window.open` (Ze
- [x] T014 [P] [US1] ENTFALLEN (Regel geändert: Zeitgeber, `fetch` und DOM sind frei,
      Speicher läuft schon über `browser`):
      `int_filemanager/static/src/int_filemanager/v2/list_renderer.js`:
      `setTimeout`/`clearTimeo
- [x] T015 [P] [US1] ENTFALLEN (Regel geändert: Zeitgeber, `fetch` und DOM sind frei,
      Speicher läuft schon über `browser`):
      `int_filemanager/static/src/int_filemanager/v2/controller_interaction.js` und
      `controller\_
- [x] T016 [P] [US1] ENTFALLEN (Regel geändert: Zeitgeber, `fetch` und DOM sind frei,
      Speicher läuft schon über `browser`):
      `int_filemanager/static/src/int_filemanager/v2/properties/values_field.js` und
      `properties
- [x] T017 [P] [US1] ENTFALLEN (Regel geändert: Zeitgeber, `fetch` und DOM sind frei,
      Speicher läuft schon über `browser`):
      `int_filemanager/static/src/int_filemanager/v2/name_field.js`: `window.innerWidth`
      (Zeile

### Neue Prüfungen

- [ ] T018 [US1] `.pre-commit-config.yaml`: vier lokale `pygrep`-Hooks
      `odoo-deprecated-env` (`\b(self|rec|record|records)\._(cr|context|uid)\b`,
      Python), `odoo-domain-concat` (`\bdomain\s*\+=|\bdomain\s*\+\s*\[`, Python),
      `odoo-xml-deprecated` (`<tree\b|\battrs=|\bstates=|\bt-raw\b`, XML außer
      `/static/`), `odoo-manifest-defaults`
      (`"application":\s*False|"auto_install":\s*False|"demo":\s*\[\]` in
      `__manifest__.py`); Regexe an der Probe prüfen
- [ ] T019 [US1] `eslint.config.cjs`: `no-restricted-globals` (`localStorage`,
      `sessionStorage`) und `no-restricted-properties` (`window.location`,
      `window.history`, `window.navigator`) für `int_filemanager/static/src/**` als
      Fehler; `jsdoc/check-tag-names` mit `definedTags: ["odoo-module"]`; `sort-imports`
      und `no-inline-comments` abschalten; `complexity` auf 20 (R11, FR-007)
- [ ] T020 [US1] `.pre-commit-config.yaml`: Hook `commit-subject` in der Stufe
      `commit-msg` (`pygrep`, `--multiline`): erlaubt `[TAG] modul: Satz` mit Tags FIX
      REF ADD REM REV MOV REL IMP MERGE CLA I18N PERF CLN LINT MIG, ganze Zeile
      höchstens 80 Zeichen, Zeilen `Merge ` bleiben erlaubt (FR-019, R2); mit den
      Dateien aus T009 testen
- [ ] T021 [US1] Probe ausführen; erwartet `30/30 cases detected` (FR-005); Treffer der
      neuen Hooks im bestehenden Code (T011 bis T017 müssen sie auf 0 gebracht haben)
      prüfen: `py -3.13 -m pre_commit run --files <geänderte Dateien>` in einer Kopie
      des Arbeitsbaums

### Die 12 geänderten Altdateien (ganze Datei prüfen, FR-002)

- [ ] T022 [US1] Nur-Format-Schritt (Zeilenlänge 120 für Python): `ruff format` und
      Prettier ausschließlich auf die 12 Dateien aus `data-model.md` Abschnitt 2 in
      einer Kopie ausführen, mit `git diff -w` belegen, dass sich nur Umbrüche und
      Leerraum ändern, dann im Arbeitsbaum übernehmen; Commit-Vorschlag
      `[REF] int_filemanager: format the twelve rewritten legacy files` (eigener Schritt
      vor den inhaltlichen)
- [ ] T023 [P] [US1] `int_filemanager/controllers/main.py`: 19 ×
      `prefer-env-translation` (`request.env._`), Zeilenlängen
- [ ] T024 [P] [US1] `int_filemanager/controllers/portal.py` und
      `int_filemanager/models/filemanager_extraction_pattern.py` (1 ×
      `translation-required`): `prefer-env-translation`, Zeilenlängen
- [ ] T025 [P] [US1] `int_filemanager/index_utils.py`: 5 × `prefer-env-translation`,
      Zeilenlängen
- [ ] T026 [P] [US1] `int_filemanager/publish_service.py`: 6 × `prefer-env-translation`,
      3 × `except-pass` (konkreter Typ oder Logging), 2 × `translation-not-lazy`,
      Zeilenlängen
- [ ] T027 [P] [US1] `int_filemanager/models/filemanager_file.py`: 3 ×
      `prefer-env-translation`, 3 × `invalid-commit` (Kommentar mit Grund und
      `# pylint: disable=invalid-commit` an den Stellen im selbst geöffneten Cursor,
      sonst entfernen), 2 × `except-pass`, 1 × `translation-not-lazy`, 1 ×
      `attribute-string-redundant`, Zeilenlängen, den deutschen Docstring aus der
      Änderung ins Englische (Hausregel)
- [ ] T028 [P] [US1] `int_filemanager/write_service.py`: 2 × `prefer-env-translation`, 2
      × `translation-not-lazy`, 1 × `invalid-commit` (der Aufruf `cr.commit()` steht im
      eigenen Cursor und hat einen Kommentar; Disable ergänzen), Zeilenlängen
- [ ] T029 [P] [US1] Die fünf XML- und JS-Dateien ohne Python-Befunde bereinigen:
      `int_filemanager/security/security.xml`,
      `int_filemanager/static/src/int_filemanager/native_ui/document_review_dialog.js`,
      `…/document_review_dialog.xml`,
      `int_filemanager/views/filemanager_extracted_value_views.xml`,
      `int_filemanager/views/filemanager_file_form_view.xml` (Prettier, ESLint)
- [ ] T030 [US1] Nach T023 bis T029: Odoo-Tests der betroffenen Bereiche
      (`tools/v2check/tests.sh`, volle Suite) und `tools/v2check/race.sh`; erwartet 645
      Tests grün, 16 von 16 Rennszenarien; Commit-Vorschlag
      `[REF] int_filemanager: clear the findings of the twelve rewritten legacy files`

### LEGACY-Ableitung

- [ ] T031 [US1] `scripts/lint/sync_legacy_excludes.py`: Altbestand aus
      `git diff --name-only int_filemanager-v1` ableiten (`data-model.md` Abschnitt 2),
      `REWRITTEN_FILES` entfernen (außer gelöschte Dateien), `--check` listet auf stdout
      jede geänderte Datei im Block; Hook `legacy-excludes-in-sync` in
      `.pre-commit-config.yaml` auf
      `^(\.pre-commit-config\.yaml|scripts/lint/sync_legacy_excludes\.py|int_filemanager/.*)$`
      erweitern; Skript ausführen, der Block verliert die 12 Dateien (und weitere, falls
      inzwischen geändert)
- [ ] T032 [US1] Abnahme US1 in einer Kopie des Arbeitsbaums: `pre-commit run --files`
      auf allen geänderten und neuen Dateien (Exit 0), `sync_legacy_excludes.py --check`
      (Exit 0), `run_probe.py` (`30/30`); Ergebnisse in `baseline.md` neben den
      Ausgangswerten festhalten (SC-001, SC-002)

**Checkpoint**: Commit-Prüfung ist lückenlos und blockierend.

---

## Phase 4: User Story 2 - Wer prüft was, ist nachlesbar (Priority: P1)

**Goal**: Prüfmatrix mit Prüfweg je Regel und ein stimmiges Prüfautomatik-Dokument
(FR-008, FR-009).

**Independent Test**: Jede Regel der 17 Destillate hat in
`docs/pruefmatrix_2026-10-04.md` Nummer, Prüfweg und, bei Werkzeug, einen Probefall;
Dokument, Konfiguration und `CLAUDE.md` widersprechen sich nicht.

- [ ] T033 [US2] `docs/pruefmatrix_2026-10-04.md` mit Kopf anlegen (Spaltenbeschreibung
      nach `data-model.md` Abschnitt 1, Legende der Prüfwege, Zählweise) und je Gruppe
      einen leeren Abschnitt
- [ ] T034 [US2] Abschnitt Coding Guidelines und Git: Regeln aus
      `docs/odoo_regeln/odoo_regeln_coding_guidelines_2026-10-02.md` und
      `…_git_guidelines_2026-10-02.md` nummerieren (`CG-001` …, `GIT-001` …) und je
      einen Prüfweg (`W:<Hook oder Test>` mit Probefall oder `R:<Punkt>`) eintragen
- [ ] T035 [US2] Abschnitt ORM und Mixins: `…_orm_…` und `…_mixins_…`
- [ ] T036 [US2] Abschnitt Sicherheit, Performance, Testen: `…_security_…`,
      `…_performance_…`, `…_testing_…`
- [ ] T037 [US2] Abschnitt Daten, Manifest, Aktionen, Cron, HTTP, Berichte:
      `…_data_manifest_…`, `…_actions_cron_http_reports_…`
- [ ] T038 [US2] Abschnitt Views, QWeb, Icons, SCSS: `…_views_…`, `…_qweb_…`,
      `…_ui_icons_scss_…`
- [ ] T039 [US2] Abschnitt JS: `…_js_framework_…`, `…_js_fields_…`, `…_js_tests_…`
- [ ] T040 [US2] Abschnitt API, CLI, Upgrade: `…_api_cli_upgrade_…`; danach Zählung
      (Anzahl Regeln je Prüfweg) an den Kopf der Matrix und in `baseline.md` (Wert für
      SC-003)
- [ ] T041 [US2] Review-Checkliste aus den `R:`-Zeilen der Matrix als eigener Abschnitt
      am Ende von `docs/pruefmatrix_2026-10-04.md` (Punkt, Regel-Nummern, wie man sucht)
- [ ] T042 [US2] `docs/pruefautomatik_2026-10-02.md` angleichen (FR-008): Abschnitt 1
      und 2 um `jscheck`, `owlcheck`, `hoot`, `tests`, `race`, Probe,
      `setup_windows.ps1`, `commit-msg`-Hook und die vier `pygrep`-Hooks erweitern;
      Aufruf `--files` statt `--all-files`; Abschnitt 6 mit den aus `git` abgeleiteten
      Zahlen und der LEGACY-Ableitung; Verifikationsstand für Windows (läuft,
      `PYTHONUTF8`); pylint-Namen an die Konfiguration angleichen
      (`xml-duplicate-record-id`, `xml-view-dangerous-replace-low-priority` statt der
      alten Namen); Altbefunde auf die 12 bereinigten Dateien aktualisieren
- [ ] T043 [US2] `CLAUDE.md` an Constitution und Dokument angleichen: Verweise auf
      `.specify/memory/constitution.md`, `docs/pruefmatrix_2026-10-04.md` und das
      Probemodul, Aufruf der Prüfungen; **vorher den ungesicherten Diff des Nutzers
      lesen** (`git diff CLAUDE.md`) und nur die betroffenen Absätze ändern
- [ ] T044 [US2] Abgleich Dokument gegen Konfiguration und `CLAUDE.md` Satz für Satz
      (Hook-Namen, Aufrufe, Zahlen) und das Ergebnis in `baseline.md` festhalten
      (SC-004)

**Checkpoint**: Wer reviewt, findet Prüfweg und Checkliste an einer Stelle.

---

## Phase 5: User Story 3 - Der neue Code hält die Hausregeln ein (Priority: P2)

**Goal**: Follower, SQL-Form, begründete Ausnahmen, Testhilfen und XML-IDs im Zustand
der Regeln (FR-012, FR-013, FR-015, FR-017, FR-018; FR-014 und FR-016 sind in US1
erledigt, werden hier nur abgenommen).

**Independent Test**: Follower-Test und Migrationstest grün; Probe und v2check ohne
Befund; `grep` auf `cr.execute(` mit Rohtext im neuen Code liefert 0 Treffer.

### Tests zuerst (müssen fehlschlagen)

- [ ] T045 [P] [US3] `int_filemanager/tests/test_v2_followers.py` (`TestV2Followers`,
      `@tagged("post_install", "-at_install")`, Nutzer über `new_test_user`): nach
      `create_folder`, `create_file` und `copy_node` steht kein Satz für
      `int_filemanager.node` in `mail.followers`; muss vor T049 fehlschlagen (SC-007)
- [ ] T046 [P] [US3] `int_filemanager/tests/test_v2_migration_xmlids.py`
      (`TestV2MigrationXmlids`): legt in einer Wegwerf-Datenbank die 21 alten XML-IDs in
      `ir_model_data` an (Stand `19.0.1.23.0`), führt
      `migrations/19.0.1.24.0/pre-migrate.py` aus und prüft neue IDs vorhanden, alte
      weg, Datensatzzahlen von `ir.ui.view`, `ir.rule`, `ir.actions.act_window`
      unverändert; zweiter Lauf auf frischer Datenbank bricht nicht ab; Teilstand (11
      neu, 10 alt) bricht nicht ab (SC-009)

### Umsetzung

- [ ] T047 [US3] Abhängigkeit prüfen: `upgrade-util` im Test-Image vorhanden (nach T069
      und T070); ohne sie bleibt T052 offen
- [ ] T048 [P] [US3] `int_filemanager/models/int_filemanager_blob.py`: 6 rohe
      `cr.execute` auf `SQL`/`env.execute_query(SQL(...))`, `flush_all()` auf
      `flush_model([...])`; Kommentar zur Cron-Cursor-Ausnahme an den beiden
      `cr.commit()` (FR-013, FR-015)
- [ ] T049 [US3] `int_filemanager/models/int_filemanager_node.py`: `_create_nodes` setzt
      `mail_create_nosubscribe=True` und `mail_notrack=True` zusätzlich zu
      `mail_create_nolog` (Zeile 557) (FR-012, R8); T045 muss jetzt grün sein
- [ ] T050 [P] [US3] `int_filemanager/models/int_filemanager_derivative.py`: 4 rohe
      `cr.execute` auf `SQL`, den f-String in `_enqueue_missing` (Zeile 218) als `SQL`
      mit Konstantenteil, `flush_all` und `invalidate_all` (Zeilen 159, 168, 205, 338,
      359, 364, 376, 381) auf `flush_model`/`invalidate_model`
- [ ] T051 [P] [US3] `int_filemanager/models/int_filemanager_upload.py`:
      `cr.execute("SET LOCAL lock_timeout …")` (Zeile 160) auf `SQL`; die zwei breiten
      `except Exception` hier und in
      `int_filemanager/models/int_filemanager_zip_job.py:133` mit Begründungskommentar
      versehen (FR-015)
- [ ] T052 [US3] XML-IDs umbenennen laut `data-model.md` Abschnitt 4:
      `int_filemanager/views/int_filemanager_node_views.xml` (11 IDs),
      `int_filemanager/security/int_filemanager_{node,revision,upload,zip_job,share,operation,scope,field_value}_security.xml`
      (10 IDs); Verweise in
      `int_filemanager/static/src/int_filemanager/v2/controller_mutations.js`,
      `…/folder_tree.js`, `tools/v2check/po_tool.py`, `tools/v2check/ui_instance.sh`;
      `int_filemanager/migrations/19.0.1.24.0/pre-migrate.py` mit
      `odoo.upgrade.util.rename_xmlid` (je Eintrag nur, wenn der alte vorhanden ist);
      Version in `int_filemanager/__manifest__.py` auf `19.0.1.24.0`; T046 muss grün
      sein
- [ ] T053 [US3] `int_filemanager/i18n/de.po` neu erzeugen mit
      `tools/v2check/i18n_export.sh` (neue Fundstellen der umbenannten IDs),
      `test_v2_i18n` grün
- [ ] T054 [P] [US3] Testnutzer vereinheitlichen: `_make_user` aus den 5 Testdateien
      (per `grep -n "def _make_user" int_filemanager/tests/*.py` bestimmen) durch
      `odoo.tests.common.new_test_user` ersetzen, Verhalten und Rechte der Nutzer
      unverändert (FR-017)
- [ ] T055 [P] [US3] `int_filemanager/tests/tower/` (`bootstrap_fixtures.py`,
      `race_scenarios.py`, `README.md`) nach `tools/v2check/tower/` verlegen mit
      `git mv` (reiner Verschiebe-Schritt, Commit-Vorschlag
      `[MOV] int_filemanager: move the Tower helper scripts out of the module`);
      Verweise in `tools/v2check/race.sh` und `tools/v2check/tests.sh` anpassen
- [ ] T056 [P] [US3] `int_filemanager/tests/test_fulltext_word_index.py`: `@tagged`
      ergänzen (Altdatei, aber bereits in T032 durch den Hook erfasst, falls geändert)
- [ ] T057 [US3] Odoo-Tests auf Tower (`tools/v2check/tests.sh`) und
      `tools/v2check/race.sh`: erwartet mindestens 645 Tests plus T045 und T046, 0
      Fehler, 16 von 16 Rennszenarien (SC-008); Commit-Vorschläge
      `[FIX] int_filemanager: stop creating a follower row per node`,
      `[REF] int_filemanager: use SQL objects for the raw queries`,
      `[REF] int_filemanager: rename the XML IDs of the views, actions and rules` (mit
      Migration)
- [ ] T058 [US3] Abnahme: `grep -rn "cr.execute(" int_filemanager/models` ohne Rohtext
      (außer `SQL(`), Probe `30/30`, `tools/v2check/v2check.sh` 0 neu

**Checkpoint**: Der neue Code folgt den Hausregeln, die Migration ist belegt.

---

## Phase 6: User Story 4 - Das Regelwerk stimmt mit den Referenzen überein (Priority: P2)

**Goal**: Jede Regel gegen Referenz oder Core belegt, überholte Regeln korrigiert
(FR-010).

**Independent Test**: Jede Matrixzeile hat Fundstelle und Ergebnis; kein Ergebnis
`überholt` ohne korrigiertes Destillat.

- [ ] T059 [US4] Quellen für die Gegenprüfung bereit: Referenzen in
      `docs/odoo19_reference/` und `docs/owl2_reference/` gelesen (jeweils `INDEX.md`,
      dann die Datei der Gruppe), Core im Image per
      `ssh unraid "docker run --rm --entrypoint sh odoo:19.0-hm-test -c '…'"` abfragbar;
      Arbeitsweise und Zählung in `docs/pruefmatrix_2026-10-04.md` Kopf vermerken
- [ ] T060 [US4] Matrix Coding Guidelines und Git: Fundstelle (Referenzdatei und
      Abschnitt, bei autodoc Core-Datei und Funktion) und Ergebnis je Regel; bekannte
      Prüfpunkte: Importreihenfolge, Manifest-Schlüssel (`_DEFAULT_MANIFEST` in
      `odoo/modules/module.py`), `test_manifests`
- [ ] T061 [US4] Matrix ORM und Mixins: Fundstelle und Ergebnis (Core: `odoo/models.py`,
      `mail/models/mail_thread.py`)
- [ ] T062 [US4] Matrix Sicherheit, Performance, Testen: Fundstelle und Ergebnis (Core:
      `odoo/addons/test_lint/tests/`, `odoo/tests/common.py`)
- [ ] T063 [US4] Matrix Daten, Manifest, Aktionen, Cron, HTTP, Berichte: Fundstelle und
      Ergebnis (Core: `odoo/addons/base/models/ir_cron.py`, `odoo/http.py`)
- [ ] T064 [US4] Matrix Views, QWeb, Icons, SCSS: Fundstelle und Ergebnis; die Aussage
      `t-out` vor `t-esc` mit Owl-Referenz
      (`docs/owl2_reference/reference/templates.md`) und Core-Zählung (337 × `t-esc`, 92
      × `t-out`) als `ergänzen` für Owl-Templates führen
- [ ] T065 [US4] Matrix JS: Fundstelle und Ergebnis; die Regel "ES2019" als `überholt`
      führen (Beleg: Core nutzt `?.` in 150 Dateien)
- [ ] T066 [US4] Matrix API, CLI, Upgrade: Fundstelle und Ergebnis
- [ ] T067 [US4] Destillate korrigieren, wo die Matrix `überholt` oder `ergänzen` nennt:
      `docs/odoo_regeln/odoo_regeln_js_framework_2026-10-02.md` (ES2019), `…_qweb_…`
      (Owl-Hinweis zu `t-esc`), `…_actions_cron_http_reports_…` und
      `…_coding_guidelines_…` (Ausnahme Cron-Cursor-Commit aus dem Plan), weitere nach
      Matrix; Prüfdatum je geänderter Datei auf 2026-10-04 und Zeile "gegengelesen" im
      Index `docs/odoo_regeln/odoo_regeln_index_2026-10-02.md` ergänzen, Folgepunkt 3
      schließen
- [ ] T068 [US4] Abnahme: Zählung der Matrixzeilen ohne Fundstelle oder Ergebnis (muss 0
      sein), Ergebnisse `stimmt`/`überholt`/`ergänzt` in `baseline.md` (SC-005)

**Checkpoint**: Das Regelwerk ist belegt und korrigiert.

---

## Phase 7: User Story 5 - Die Oberfläche wird nach Odoo-Regel getestet (Priority: P3)

**Goal**: Hoot-Tests und Tour laufen automatisch; die Template-Prüfung erfasst alle
Templates (FR-006, FR-007, FR-011).

**Independent Test**: `tools/v2check/hoot.sh` meldet `Test suite succeeded`;
`owlcheck.sh` nennt 24 von 24 Templates; jeder der 75 Testfälle ist als Hoot-Test
vorhanden.

- [ ] T069 [US5] `tools/docker/Dockerfile.test` anlegen: `FROM odoo:19.0-hm-test`,
      `USER root`, Google Chrome stable (`.deb`) installieren,
      `pip3 install --break-system-packages websocket-client` und `upgrade-util`,
      `USER odoo`; Image auf Tower bauen als `odoo:19.0-hm-test-chrome` (**erst nach
      Freigabe T003**)
- [ ] T070 [US5] Produktions-`Dockerfile` (Repo-Wurzel): `upgrade-util` in die
      vorhandene `pip3 install`-Zeile (**nach Freigabe T003**; das Image wird nicht
      gebaut, nur die Datei geändert)
- [ ] T071 [US5] `tools/v2check/hoot.sh` anlegen (nach dem Muster von
      `tools/v2check/tests.sh`): Wegwerf-Datenbank, Container aus
      `odoo:19.0-hm-test-chrome`, Lauf von `WebSuite.test_unit_desktop` gefiltert auf
      `@int_filemanager` und der Tour `int_filemanager_explorer`, Ausgabe der
      Hoot-Fehler; Aufräumen wie in `tests.sh`
- [ ] T072 [US5] Beweis, dass der Läufer fehlschlägt, wenn ein Hoot-Test fehlschlägt:
      Probetest mit `expect(1).toBe(2)` in einer Kopie, Exit ≠ 0, danach entfernen
- [ ] T073 [P] [US5] Hoot-Test `int_filemanager/static/tests/chunk_upload.test.js` aus
      `static/tests/js/chunk_upload.test.mjs` (alle Testfälle,
      `expect.step`/`verifySteps`, `mockFetch` statt `fake_server.mjs`)
- [ ] T074 [P] [US5] `int_filemanager/static/tests/upload_manager.test.js` aus
      `upload_manager.test.mjs`
- [ ] T075 [P] [US5] `int_filemanager/static/tests/upload_plan.test.js` aus
      `upload_plan.test.mjs`
- [ ] T076 [P] [US5] `int_filemanager/static/tests/download_bases.test.js` aus
      `download_bases.test.mjs`
- [ ] T077 [P] [US5] `int_filemanager/static/tests/folder_walk.test.js` aus
      `folder_walk.test.mjs`
- [ ] T078 [P] [US5] `int_filemanager/static/tests/utils.test.js` und `helpers.test.js`
      aus `utils.test.mjs` und `helpers.test.mjs`
- [ ] T079 [P] [US5] `int_filemanager/static/tests/value_edits.test.js` und
      `value_geometry.test.js` aus `value_edits.test.mjs` und `value_geometry.test.mjs`
- [ ] T080 [US5] Äquivalenzliste in
      `specs/001-filemanager-regelkonformitaet/hoot-equivalence.md`: jede der 75
      Testfall-Überschriften der `.mjs`-Dateien (`node --test` Ausgabe) neben dem
      Hoot-Test gleichen Namens; Zählung muss 75 von 75 ergeben
- [ ] T081 [US5] Tour `int_filemanager/static/tests/tours/int_filemanager_explorer.js`
      (Ordner anlegen, Datei hochladen, umbenennen, in den Papierkorb legen; letzte
      Schritte bringen den Client in einen stabilen Zustand) und
      `int_filemanager/tests/test_v2_tour.py` (`HttpCase`, `start_tour`, `post_install`)
- [ ] T082 [US5] `int_filemanager/__manifest__.py`: `assets` um `web.assets_unit_tests`
      (`int_filemanager/static/tests/**/*` ohne `tours/`) und `web.assets_tests`
      (`int_filemanager/static/tests/tours/**/*`) erweitern
- [ ] T083 [US5] `tools/v2check/hoot.sh` ausführen; erwartet `Test suite succeeded`, 75
      Testfälle plus Tour; Ergebnis in `baseline.md`
- [ ] T084 [US5] Nach grünem T083: `int_filemanager/static/tests/js/` (alle `.mjs`,
      `fake_server.mjs`) löschen, den `.mjs`-Block in `eslint.config.cjs` entfernen, den
      Hinweis auf `node --test` aus `tools/v2check/jscheck.sh` streichen;
      Commit-Vorschlag `[REF] int_filemanager: port the browser tests to Hoot`
- [ ] T085 [P] [US5] `tools/v2check/owlcheck/merge_templates.py`: Glob auf `**/*.xml`
      (rekursiv), Ausgabe nennt die Zahl; `tools/v2check/owlcheck.sh` ausführen,
      erwartet `24 template(s) compiled, 0 problem(s)` (SC-006)
- [ ] T086 [US5] ESLint-Lauf auf `int_filemanager/static`
      (`pre-commit run eslint --files …`): 0 Fehler, keine Dauerwarnungen (SC-006)

**Checkpoint**: Die Oberfläche hat Hoot-Tests und eine Tour im Prüflauf.

---

## Phase 8: Polish & Querschnitt

- [ ] T087 Gesamtlauf nach Abschluss: `tools/v2check/v2check.sh`, `jscheck.sh`,
      `owlcheck.sh`, `hoot.sh`, `tests.sh`, `race.sh`, `run_probe.py`, pre-commit in
      einer Kopie auf allen geänderten Dateien; Ergebnisse gegen `baseline.md` und
      SC-001 bis SC-009 in `specs/001-filemanager-regelkonformitaet/baseline.md`
      (Abschnitt "Abschluss")
- [ ] T088 `quickstart.md` Schritt für Schritt auf dem Arbeitsrechner und auf Tower
      nachvollziehen und Abweichungen in `quickstart.md` korrigieren
- [ ] T089 Hinweis an den Nutzer, `scripts/lint/setup_windows.ps1` selbst auszuführen
      und eine neue Shell zu öffnen (T002); danach `git commit` mit einer absichtlich
      falschen Kopfzeile in einem Wegwerf-Klon belegen, dass `commit-subject` blockiert
- [ ] T090 Memory-Eintrag und `CLAUDE.md`-Verweis auf den Stand bringen (`MEMORY.md`,
      `project_speckit_regelpruefung_filemanager.md`); `/speckit-analyze` und
      `/speckit-checklist` erneut laufen lassen

---

## Dependencies & Execution Order

- **Phase 1** vor allem anderen; **T003** (Freigabe) blockiert T069 bis T072, T047, T052
  (Migration) und T083.
- **Phase 2** (Probe) vor Phase 3: ohne rote Probe gibt es keinen Beleg.
- **US1** (T011 bis T032): T011 bis T017 vor T018 bis T021 (die neuen Prüfungen würden
  sonst den bestehenden Code blockieren); T022 vor T023 bis T029; T031 erst nach T030
  (sonst blockiert der Hook die noch nicht bereinigten Dateien).
- **US2** nach US1 (Dokument beschreibt den Endstand); T033 bis T041 können neben US1
  laufen, T042 und T044 erst nach US1 und US5.
- **US3**: T045 und T046 vor T049 und T052; T052 braucht `upgrade-util` im Image
  (T069/T070, Freigabe).
- **US4** unabhängig von US3 und US5; T067 vor T044.
- **US5**: T069 → T071 → T072; T073 bis T079 parallel; T080 nach T073 bis T079; T084
  nach T083.
- **Polish** zuletzt.

### Parallele Beispiele

```text
US1 (Browser-Objekt):  T012, T013, T014, T015, T016, T017
US1 (12 Altdateien):   T023, T024, T025, T026, T027, T028, T029
US3 (Tests und Code):  T045, T046, T048, T050, T051, T054, T055, T056
US5 (Hoot-Portierung): T073, T074, T075, T076, T077, T078, T079
```

## Implementation Strategy

### MVP zuerst (nur US1)

1. Phase 1 und 2 (Probe rot).
2. US1: Code anpassen, Hooks einschalten, 12 Dateien bereinigen, LEGACY ableiten.
3. **Prüfen**: Probe 30/30, pre-commit Exit 0 auf allen geänderten Dateien.
4. Danach US2 (Dokumentation), US3, US4, US5 in Prioritätsreihenfolge; jede Geschichte
   endet mit ihrer Abnahme.

### Inkrementelle Lieferung

Jede Phase endet mit einem Prüfstand (Checkpoint) und, auf Ansage des Nutzers, mit
Commits in der Reihenfolge: Format (`[REF]`), Bereinigung (`[REF]`), Prüfautomatik
(`[IMP]`), Verschiebung (`[MOV]`), Korrekturen (`[FIX]`), Umbenennung mit Migration
(`[REF]`), Tests (`[ADD]`).

## Notes

- Jede Aufgabe ändert nur die genannte Datei; Aufgaben mit [P] haben verschiedene
  Dateien.
- Keine Handeingriffe in Datenbanken oder Container; alle Prüfungen mit
  Wegwerf-Datenbanken.
- Der Nutzer führt `setup_windows.ps1` und alle Commits selbst aus oder gibt sie
  ausdrücklich frei.
