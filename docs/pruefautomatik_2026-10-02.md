# Prüfautomatik (Ruff, ESLint/Prettier, test_lint, odoo-ls)

Maschinelle Prüfung des Codes, ausschließlich mit den Werkzeugen und Konfigurationen, die Odoo selbst festlegt (überarbeitet 2026-10-08).
Es gibt keine GitHub Action. Regeln: `docs/odoo_regeln/odoo_regeln_index_2026-10-02.md`.

## 1. Bestandteile

| Werkzeug | Konfiguration | Herkunft | Wo läuft es | Was es prüft |
|---|---|---|---|---|
| **Ruff** | `ruff.toml` (unverändert aus dem Odoo-Repository) | Odoo-Repository, Datei `ruff.toml` (von der Runbot nächtlich erzeugt, verlangt Ruff ≥ 0.16.1) | Arbeitsrechner über pre-commit bei `git commit` | Lint nach Odoos Regelliste; E501 und C901 sind dort ignoriert; kein Formatierer |
| **ESLint + Prettier** | `.eslintrc.json` (unverändert aus `addons/web/tooling/_eslintrc.json`) | Odoo-Repository, Entwickler-Werkzeug `addons/web/tooling` (ESLint 8, Prettier 2: `printWidth` 100, `tabWidth` 4) | Arbeitsrechner über pre-commit | `eslint:recommended`, Odoo-Regeln (u. a. `curly`, `prefer-const`, `no-unused-vars`) und Prettier-Format |
| **`test_lint`** | `scripts/lint/run_test_lint.sh` | Odoo-Modul `test_lint` | Tower, Wegwerf-Container aus `odoo:19.0-hm-test` | Odoos eigene Lint-Tests (Abschnitt 3) |
| **odoo-ls** | `scripts/lint/run_odoo_ls.sh`, `scripts/lint/odoo_ls_check.py` | Offizielles Projekt `odoo/odoo-ls`; laut Projektseite in Entwicklung, nicht als stabil freigegeben | Tower (Docker) oder lokal | Registry-Wissen: unbekannte Modelle/Felder, fehlendes `depends`, falsche Aufrufargumente, doppelte Template-IDs |

pre-commit ist nur der Läufer (`.pre-commit-config.yaml`); es gehören keine weiteren Hooks dazu. Beide Hooks schreiben **keine** Dateien um (Ruff `--no-fix`, ESLint ohne `--fix`), weil die
Coding Guidelines verbieten, bestehende Dateien zur Anpassung an die Guidelines umzuformatieren. Das Ruff-Hook ignoriert die Regeln, die Odoo in der Kopfzeile der `ruff.toml` als „empfohlen, aber nicht erzwungen“
nennt (B904, COM812, E741, EM101, I001, RET, RUF021, RUF102, TID252, TRY002, UP006, UP007).
`docs/`, `scripts/`, `tools/`, `CLAUDE.md`, `README.md`, `Dockerfile`, `/vendor/`, `static/lib/` und `.svg`-Dateien werden von pre-commit nicht geprüft.
`tools/v2check/v2check.sh` ist der gebündelte Aufruf für `int_filemanager` 2 auf Tower; er läuft unabhängig von `scripts/lint/`.

## 2. Aufruf

```bash
# einmalig auf dem Arbeitsrechner (Windows: py -3.13 -m pre_commit)
pip install pre-commit && pre-commit install
pre-commit run --files <Datei> ...                # oder bei jedem Commit automatisch (nur geänderte Dateien)

# Tower (ssh unraid), im Repo-Checkout
scripts/lint/run_test_lint.sh                    # braucht pylint in $PYLIB (Hinweis im Skript beim ersten Lauf)
MODE=docker scripts/lint/run_odoo_ls.sh          # braucht /tmp/odoo-ls (odoo_ls_server + typeshed/)
```

Rückgabe: Exit-Code ≠ 0 bei Befunden. odoo-ls: Fehler und Warnungen (Stufe 1–2) zählen, Stufe 3 (Information, z. B. `OLS03024`) nicht.

## 3. Was Odoos `test_lint` prüft (Nachschlagewerk)

Läuft mit `--test-tags /test_lint`. Quelle: `odoo/addons/test_lint/tests/`.

- **`test_pylint`:** Pylint mit `used-before-assignment`, `undefined-variable`, `eval-used`, `unreachable`, `function-redefined`, `sql-injection` (E8501), `raise-unlink-override` (E8503), `gettext-variable` (E8502),
  `gettext-placeholders` (E8505), `gettext-repr` (E8506) und `missing-gettext` (E8507: statische Zeichenkette in `UserError`, `ValidationError`, `AccessError`, `AccessDenied`, `MissingError` ohne Übersetzungsaufruf);
  verbotene Funktion `input`; veraltete Module `csv`/`urllib`/`cgi` und Debugger-Module. Geprüft werden der Odoo-Kern (`odoo/`) und alle Addon-Pfade **außerhalb** von `<root_path>/addons`:
  Im Git-Checkout liegen die Core-Addons daneben und werden mitgeprüft, im Docker-Image liegen sie darunter und entfallen. Der Core selbst kann Pylint-Befunde haben; `tools/v2check/v2check_filter.py` filtert auf `int_filemanager`.
- **`test_manifests`:** Unbekannte Manifest-Schlüssel sind ein Fehler; `application`, `auto_install`, `summary`, `description`, `author`, `demo`, `data`, `test` dürfen nicht auf dem Standardwert stehen; `icon` nicht auf dem Standardpfad.
  Dass `name`, `author`, `license` Pflicht sind, ist im Code nur als Kommentar vermerkt; eine fehlende `license` ergibt nur eine Warnung.
- **Weitere Tests:** `__init__.py` im Modul (`test_dunderinit`), Docstring ↔ Signatur (`test_docstring`), ESLint über die JS-Dateien der Module mit `test_lint/tests/eslintrc` (`test_eslint`; wird übersprungen, wenn ESLint fehlt),
  JS-Übersetzungen (`test_jstranslate`), Übersetzbarkeit von Props mit Anzeigetext in Templates (`test_i18n`, Suffix `.translate`), Index auf One2many-Gegenstücken (`test_index`), Merge-Konfliktmarker (`test_markers`),
  Parameternamen `ids`/`context` in öffentlichen Methoden (`test_naming`), keine Onchange-Domains (`test_onchange_domains`), kein Import aus `odoo.orm` (`test_orm_import`), Überschreibungs-Signaturen (`test_override_signatures`),
  doppelte `.pot`-Einträge (`test_pofile`), `l10n`-Testtags (`test_l10n`), Routen-Vererbung (unveränderte Werte nicht wiederholen, `test_routes`), nicht importierte Testdateien (`test_test_holes`).
- Im Docker-Image fehlt ESLint: `test_eslint` wird dort **übersprungen**, nicht bestanden.

## 4. odoo-ls, Parse-Modus

`odoo_ls_server --parse -c <Odoo-Pfad> -a <Addon-Pfad> -t <Addon-Pfad> --python <python> --stdlib <typeshed>/stdlib -s <typeshed>/stubs -o out.json` schreibt alle Befunde als JSON (Aufruf aus der Projektdoku Dritter,
im Repo von `odoo/odoo-ls` nicht geprüft). Es findet, was Pylint nicht sehen kann, weil es die Odoo-Registry kennt: unbekanntes Modell, Modell nicht in `depends`, Feld existiert nicht, ungültiges Domain-Feld,
Methode existiert nicht, Compute-Methode setzt das Feld nicht, Related-Feld mit falschem Typ, falsche Aufrufargumente; dazu ESLint (oxc) für JS. Fallstricke: (1) `typeshed.zip` aus dem Release gehört dazu, sonst bricht der Lauf ab;
(2) Bibliotheken außerhalb des Images (z. B. `wsgidav` in `/mnt/pylib`) per `PYTHONPATH` sichtbar machen, sonst Fehlalarme; (3) die Ausgabe enthält auch Befunde aus dem Odoo-Kern, nach eigenen Pfaden filtern;
(4) Hinweise mit Stufe 3 (z. B. `OLS03024`) sind Information, kein Fehler. Das Programm beendet sich unabhängig von den Befunden normal, deshalb wertet `scripts/lint/odoo_ls_check.py` das JSON aus.

## 5. Grenzen

- pre-commit läuft nur mit installiertem Hook; ein Commit ohne Hook umgeht die Prüfung.
- Image (`odoo:19.0-hm-test`) und Git-Checkout des Odoo-Kerns können sich unterscheiden; Befunde können dadurch abweichen.
- Logik, Rechte und Performance prüft keines der Werkzeuge; dafür gibt es Tests.
