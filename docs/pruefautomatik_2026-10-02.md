# Prüfautomatik (pre-commit, test_lint, odoo-ls) – Stand 2026-10-02

Umsetzung des Beschlusses vom 2026-09-26 (`docs/odoo_konventionen_2026-09-26.md`, Abschnitte 9 und 10):
**pre-commit nach OCA-Vorlage (nur neuer Code), Odoos `test_lint`, odoo-ls im Parse-Modus; keine GitHub Action.**
Regeln selbst: `docs/odoo_regeln_index_2026-10-02.md`.

## 1. Bestandteile

| Werkzeug | Dateien | Wo läuft es | Was es prüft |
|---|---|---|---|
| **pre-commit** | `.pre-commit-config.yaml`, `.pylintrc-mandatory` (blockierend), `.pylintrc` (alles, nicht blockierend), `.ruff.toml`, `eslint.config.cjs`, `prettier.config.cjs`, `.editorconfig` | Arbeitsrechner, bei `git commit` | Ruff (Lint + Format), pylint-odoo, `oca-checks-odoo-module`/`-po`, ESLint, Prettier (XML/JS/…), Standard-Hooks (Whitespace, XML, Merge-Marker …) |
| **`test_lint`** | `scripts/lint/run_test_lint.sh` | Tower, Wegwerf-Container aus `odoo:19.0-hm-test` | Odoos eigene Lint-Tests über **alle** Addon-Pfade (pylint-Sonderprüfungen, Manifest, `__init__`, Docstring, i18n, Routen …) |
| **odoo-ls** | `scripts/lint/run_odoo_ls.sh`, `scripts/lint/odoo_ls_check.py` | Tower (Docker) oder lokal | Registry-Wissen: unbekannte Modelle/Felder, fehlendes `depends`, falsche Aufrufargumente, doppelte Template-IDs |

**Nur neuer Code:** `.pre-commit-config.yaml` schließt bestehende Dateien über einen generierten Block `LEGACY` aus
(Basis: Tag `int_filemanager-v1`). Ganze Altmodule per Verzeichnis, `int_filemanager` Datei für Datei. Wird eine Altdatei
neu geschrieben: Pfad in `REWRITTEN_FILES` in `scripts/lint/sync_legacy_excludes.py` eintragen und das Skript
ausführen (`--check` prüft, ob der Block aktuell ist; ein pre-commit-Hook tut das bei Änderung der Konfiguration).
`docs/`, `scripts/`, `CLAUDE.md`, `Dockerfile` und `/vendor/` werden nicht geprüft. `odoo_ls_check.py` wendet dieselbe
Legacy-Liste an (`--include-legacy` zeigt alles).

## 2. Aufruf

```bash
# einmalig auf dem Arbeitsrechner (Windows: py -3.13 -m pre_commit, Programme unter %APPDATA%\Python\Python313\Scripts)
pip install pre-commit==4.6.2 && pre-commit install
git fetch origin tag int_filemanager-v1          # Basis für scripts/lint/sync_legacy_excludes.py
pre-commit run --all-files                       # oder nur geänderte Dateien bei jedem Commit

# Tower (ssh unraid), im Repo-Checkout
scripts/lint/run_test_lint.sh                    # braucht pylint in $PYLIB (Hinweis im Skript beim ersten Lauf)
MODE=docker scripts/lint/run_odoo_ls.sh          # braucht /tmp/odoo-ls (odoo_ls_server + typeshed/)
```

Rückgabe: Exit-Code ≠ 0 bei Befunden. odoo-ls: Fehler und Warnungen (Stufe 1–2) zählen, Stufe 3 (Information, z. B.
`OLS03024`) nicht.

## 3. Was verifiziert ist – und was nicht

Verifiziert in einer **Cloud-Sitzung** (Odoo 19.0 Git-Stand 2026-10-02, Python 3.11, pylint 4.1.1, PostgreSQL 16, Node 22,
odoo-ls 1.6.0 aus dem Quellcode gebaut):

- **pre-commit:** alle Hooks laufen; ein Probemodul mit Absicht eingebauten Fehlern wurde erkannt (SQL-Injection,
  `cr.commit()`, `print`, `eval`, `except: pass`, übersetzte Zeichenkette mit `%`, `debugger`, bare `except`). ESLint verarbeitet native ES-Module (`import`, `static`), Prettier formatiert XML. Auf Altdateien und
  `docs/` laufen keine Hooks.
- **`test_lint`:** voller Lauf über Odoo-Kern + unsere Module (Befunde Abschnitt 4).
- **odoo-ls:** Parse-Lauf, JSON-Format bestätigt, Auswertung läuft.

**Nicht verifiziert:**
- Die Docker-Läufe auf **Tower** (`run_test_lint.sh`, `MODE=docker`): in der Cloud gibt es keinen Docker-Daemon. Dieselben
  Odoo-/odoo-ls-Aufrufe wurden aber ohne Docker ausgeführt.
- pre-commit auf dem **Windows-Arbeitsrechner** (Node-Pin `22.9.0` wird dort von pre-commit selbst geladen; in der Cloud
  wurde das System-Node benutzt).
- Abweichungen durch den Unterschied Image `odoo:19.0-hm-test` (19.0-20260908) ↔ Git-Stand und pylint-Version.

Umgebungsartefakte der Cloud-Sitzung, die **keine** Befunde sind: 9 Docstring-Fehler (Pygments fehlte; nach Installation
grün), `test_eslint` mit ESLint 9 (`--eslintrc` entfernt; mit ESLint 8.57.1 läuft er), odoo-ls-Fehlalarme `OLS02001`
für Bibliotheken außerhalb des Pfads (mit `PYTHONPATH` weg), Modell `documents.document` (Enterprise) in `onlyoffice_odoo`.
Auf Tower ist ESLint im Image nicht vorhanden → `test_eslint` wird dort **übersprungen**, nicht bestanden.

## 4. Befunde im Altbestand (Stand der Prüfung)

`test_lint` schlägt auf dem heutigen Code **fehl** (Odoo prüft alle Addon-Pfade, auch die Altmodule). Echte Befunde:

| Test | Befund | Ort |
|---|---|---|
| `test_manifests` | Schlüssel `application` auf Standardwert (`False`) | `int_generic`, `int_legacy_erp_import`, `int_repair_workshop`, `int_fleet_kanban_width` |
| `test_orm_import` | Import direkt aus `odoo.orm` statt `odoo` | `int_filemanager/acl_rules.py` |
| `test_user_content_as_prop_is_translatable` (i18n) | Literal-Prop nicht übersetzbar (`title="'Mit Kontakt verknüpfen'"`) | `int_filemanager/static/src/int_filemanager/shared/link_record_dialog.xml` |
| `test_pylint` E8507 (statischer Text in `UserError`/`ValidationError`/`AccessError` ohne `_()`) | 10 × `int_filemanager` (`acl_rules.py:204`, `path_utils.py:85/97/109`, `authz.py:97`, `controllers/webdav.py:51/56`, `models/filemanager_protected_folder.py:45/47`, `models/ir_attachment.py:27`), 1 × `onlyoffice_odoo/controllers/controllers.py:519` | s. Spalte |
| `test_eslint` (nur mit ESLint 8) | 10 Fehler in `onlyoffice_odoo` (`owl`/`DocsAPI` undefiniert, Komponenten ohne `static props`/`template`, ungenutzte `_error`) | Drittanbieter-Modul |

odoo-ls (mit Bibliotheken im Pfad, alle Dateien): `int_filemanager` ohne Befund; offen bleiben `int_generic`
(doppelte Template-ID `list_column_reorder.xml`) und `onlyoffice_odoo` (`documents.document` = Enterprise-Modell).
Das deckt sich mit dem Probelauf vom 2026-09-26 in Konventionen Abschnitt 9.

Diese Befunde sind **nicht behoben**: Altcode wird nach der Odoo-Regel nicht angefasst, und die Änderungen betreffen
Benutzertexte (`_()`/Übersetzung) bzw. Manifeste und sollten bewusst entschieden werden.

## 5. Offene Entscheidungen

1. **Altbefunde:** beheben (kleine, mechanische Änderungen: `application` entfernen, `odoo.orm`-Import, Fehlertexte in
   `_()`, Prop übersetzbar) oder `test_lint` vorerst mit bekannten Ausnahmen betreiben? Empfehlung: beheben, aber getrennt vom v2-Umbau.
2. **Autor** im Manifest (`manifest-required-author`) und README je Modul: in `.pylintrc-mandatory` bewusst **nicht**
   erzwungen (kein OCA-Umfeld). Autorname festlegen, dann Regel einschalten.
3. **Wo läuft pre-commit?** Beschluss: Arbeitsrechner. Ohne Server-Hook ist es freiwillig; ein Commit ohne installierten
   Hook umgeht die Prüfung (keine GitHub Action beschlossen).
4. **`test_eslint` auf Tower:** läuft nur mit installiertem ESLint 8 (nicht im Image), sonst wird er übersprungen.
5. Auf welchem Branch gelten die Dateien: sie liegen auf `claude/festive-goldberg-f6on8h`; die Entwicklung läuft laut
   Konzept auf `feature/int-filemanager-v2` → dorthin übernehmen (Merge/Cherry-pick).

## 6. Stand auf `feature/int-filemanager-v2`

Die Prüfautomatik ist am 2026-10-02 von `master` auf diesen Branch übernommen worden und ersetzt die frühere, rohe OCA-Fassung der Konfigurationsdateien. Anpassungen für v2:

- **LEGACY-Block:** Referenz bleibt das Tag `int_filemanager-v1`. 102 der 109 Dateien von `int_filemanager` sind hier unverändert und damit Altbestand. Die 7 seit dem Tag geänderten Dateien stehen in `REWRITTEN_FILES` (`scripts/lint/sync_legacy_excludes.py`) und werden geprüft. Wird eine weitere Altdatei umgeschrieben, trägt man sie dort ein und startet das Skript.
- **ESLint:** zusätzlicher Block für `int_filemanager/static/**/*.mjs` (ES-Module, Node-Global `Buffer`), weil die Tests als `.mjs` mit `node --test` laufen. Auf `master` gibt es diese Dateien nicht.
- **Autor im Manifest:** Die frühere v2-Fassung erzwang `manifest-required-authors=Waldemar Toews`. Das entfällt, `.pylintrc` und `.pylintrc-mandatory` entsprechen wieder `master` (Autor nur als nicht blockierende Prüfung).
- **Neben `tools/v2check/`:** `tools/v2check/v2check.sh` bleibt der Aufruf für `int_filemanager` 2 auf Tower; `scripts/lint/run_test_lint.sh` und `run_odoo_ls.sh` sind die allgemeine Fassung aus `master`. Beide laufen unabhängig voneinander; ob eine wegfällt, ist offen.
- **Nicht erneut verifiziert:** Die Läufe in Abschnitt 3 und die Befunde in Abschnitt 4 stammen vom Stand `master`. Auf diesem Branch wurden `pre-commit`, `test_lint` und odoo-ls nach der Übernahme **nicht** ausgeführt, nur die Syntax der Dateien geprüft.
