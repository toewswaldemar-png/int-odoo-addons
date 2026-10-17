# Prüfautomatik (Ruff, ESLint/Prettier, test_lint, odoo-ls)

Maschinelle Prüfung des Codes mit Werkzeugen und Konfigurationen aus dem Odoo-19-Projekt (überarbeitet 2026-10-08).

## 1. Bestandteile

| Werkzeug | Konfiguration | Herkunft | Wo läuft es | Was es prüft |
|---|---|---|---|---|
| **Ruff** | `ruff.toml` (unverändert aus dem Odoo-Repository) | Odoo-Repository, Datei `ruff.toml` (von der Runbot nächtlich erzeugt, verlangt Ruff ≥ 0.16.1) | Arbeitsrechner über pre-commit bei `git commit` | Lint nach Odoos Regelliste; E501 und C901 sind dort ignoriert; kein Formatierer |
| **ESLint + Prettier** | `.eslintrc.json` (unverändert aus `addons/web/tooling/_eslintrc.json`) | Odoo-Repository, Entwickler-Werkzeug `addons/web/tooling` (ESLint 8, Prettier 2: `printWidth` 100, `tabWidth` 4) | Arbeitsrechner über pre-commit | `eslint:recommended`, Odoo-Regeln (u. a. `curly`, `prefer-const`, `no-unused-vars`) und Prettier-Format |
| **`test_lint`** | `tools/check/check.sh`, `tools/check/check_filter.py` | Odoo-Modul `test_lint` | Tower, Wegwerf-Container aus `odoo:19.0-hm-test` | Odoos eigene Lint-Tests (Abschnitt 3) |
| **odoo-ls** | `tools/check/check.sh`, `tools/check/check_filter.py` | Offizielles Projekt `odoo/odoo-ls`; laut Projektseite in Entwicklung, nicht als stabil freigegeben | Tower (Docker) | Registry-Wissen: unbekanntes Modell, unbekanntes Feld, Modell nicht in `depends`, falsche Aufrufargumente (Nachweis: Abschnitt 4) |

pre-commit ist nur der Läufer (`.pre-commit-config.yaml`); es gehören keine weiteren Hooks dazu. Beide Hooks schreiben **keine** Dateien um (Ruff `--no-fix`, ESLint ohne `--fix`). Das ist eine bewusste
Projektentscheidung: Ein Prüfkommando soll keine unerwarteten Änderungen erzeugen. Die Odoo-Regel dazu steht in den Coding Guidelines: In stabilen Versionen sollen bestehende Dateien nicht allein zur Anpassung
an die Guidelines umformatiert werden (Diff minimal halten); in `master` gelten die Guidelines für neu geschriebenen und geänderten Code. Das Ruff-Hook ignoriert die Regeln, die Odoo in der Kopfzeile der `ruff.toml` als „empfohlen, aber nicht erzwungen“
nennt (B904, COM812, E741, EM101, I001, RET, RUF021, RUF102, TID252, TRY002, UP006, UP007).
`docs/`, `tools/`, `CLAUDE.md`, `README.md`, `Dockerfile`, `/vendor/`, `static/lib/` und `.svg`-Dateien werden von pre-commit nicht geprüft.
`tools/check/check.sh` ist der gebündelte Aufruf für `int_filemanager` auf Tower (odoo-ls und `test_lint`). `tools/check/tests.sh` führt die Modultests in einer Wegwerf-Datenbank aus.

**Regelquelle und lokale Entscheidung.** Die Regeln von Ruff und ESLint/Prettier, die Tests von `test_lint` und die Meldungen von odoo-ls stammen aus dem Odoo-Projekt. Folgendes ist dagegen lokal festgelegt und keine Odoo-Vorgabe:

- welche Verzeichnisse pre-commit ausschließt (Zeile oben) und dass Ruff und ESLint keine Dateien ändern;
- welche odoo-ls-Schweregrade den Lauf abbrechen (Stufe 1–2) und dass nur Befunde unter `int_filemanager` zählen;
- wie `test_lint` ausgewertet wird: `check_filter.py` wertet die Abschlusszeile von Odoo aus; ein fehlgeschlagener Test ist nur dann akzeptiert, wenn er auf der Ausnahmeliste für bekannte Core-Befunde steht (derzeit nur `TestPyLint.test_pylint`, und nur ohne Befund in `int_filemanager`);
- welches Docker-Image verwendet wird (`odoo:19.0-hm-test`).

## 2. Aufruf

```bash
# einmalig auf dem Arbeitsrechner (Windows: py -3.13 -m pre_commit)
pip install pre-commit && pre-commit install
pre-commit run --files <Datei> ...                # oder bei jedem Commit automatisch (nur geänderte Dateien)

# Arbeitsrechner, Git Bash im Repo (läuft über ssh auf dem Tower, SSH-Alias unraid)
tools/check/check.sh --quick                    # odoo-ls (ca. 30 s); braucht odoo-ls und typeshed unter /mnt/user/appdata/fmtest/odoo-ls
tools/check/check.sh                            # odoo-ls und test_lint (ca. 8 Minuten); braucht pylint unter /mnt/user/appdata/fmtest/lintlib
```

Rückgabe: Fehlgeschlagene Tests erzeugen einen Fehlerstatus; einige Odoo-Prüfungen protokollieren lediglich Warnungen (z. B. `test_routes`) und lassen den Lauf nicht scheitern. odoo-ls: Fehler und Warnungen (Stufe 1–2) zählen, Stufe 3 (Information, z. B. `OLS03024`) nicht.
`tools/check/check.sh` meldet nur dann „OK“, wenn der Filter nichts findet (siehe Abschnitt 1).

Die Auswertung des `test_lint`-Logs und der odoo-ls-Ausgabe hat eigene Tests: `python tools/check/test_check_filter.py`.

## 3. Was Odoos `test_lint` prüft (Nachschlagewerk)

Läuft mit `--test-tags /test_lint`. Quelle: `odoo/addons/test_lint/tests/`.

- **`test_pylint`:** Pylint mit `used-before-assignment`, `undefined-variable`, `eval-used`, `unreachable`, `function-redefined`, `sql-injection` (E8501), `raise-unlink-override` (E8503), `gettext-variable` (E8502),
  `gettext-placeholders` (E8505), `gettext-repr` (E8506) und `missing-gettext` (E8507: statische Zeichenkette in `UserError`, `ValidationError`, `AccessError`, `AccessDenied`, `MissingError` ohne Übersetzungsaufruf);
  verbotene Funktion `input`; veraltete Module `csv`/`urllib`/`cgi` und Debugger-Module. Geprüft werden der Odoo-Kern (`odoo/`) und alle Addon-Pfade **außerhalb** von `<root_path>/addons`:
  Im Git-Checkout liegen die Core-Addons daneben und werden mitgeprüft; im Docker-Image liegen sie unter dem Odoo-Root und werden nicht nochmals einzeln hinzugefügt, gehören über den Odoo-Root-Pfad aber weiterhin zum Pylint-Lauf.
  Der Core selbst hat Pylint-Befunde (Stand 2026-10-16: E8501 und E8505 in `l10n_tr_nilvera`, `point_of_sale`, `purchase`), `test_pylint` schlägt deshalb immer fehl; `tools/check/check_filter.py` lässt diesen Fehlschlag nur zu, solange alle Befunde außerhalb von `int_filemanager` liegen.
- **`test_manifests`:** Unbekannte Manifest-Schlüssel sind ein Fehler; `application`, `auto_install`, `summary`, `description`, `author`, `demo`, `data`, `test` dürfen nicht auf dem Standardwert stehen; `icon` nicht auf dem Standardpfad.
  Dass `name`, `author`, `license` Pflicht sind, ist im Code nur als Kommentar vermerkt; eine fehlende `license` ergibt nur eine Warnung.
- **Weitere Tests:** `__init__.py` im Modul (`test_dunderinit`), Docstring ↔ Signatur (`test_docstring`), ESLint über die JS-Dateien der Module mit `test_lint/tests/eslintrc` (`test_eslint`; wird übersprungen, wenn ESLint fehlt),
  JS-Übersetzungen (`test_jstranslate`), Übersetzbarkeit von Props mit Anzeigetext in Templates (`test_i18n`, Suffix `.translate`), Index auf One2many-Gegenstücken (`test_index`), Merge-Konfliktmarker (`test_markers`),
  Parameternamen `ids`/`context` in öffentlichen Methoden (`test_naming`), keine Onchange-Domains (`test_onchange_domains`), kein Import aus `odoo.orm` (`test_orm_import`), Überschreibungs-Signaturen (`test_override_signatures`),
  doppelte `.pot`-Einträge (`test_pofile`), `l10n`-Testtags (`test_l10n`), Routen-Vererbung (`test_routes` meldet wiederholte Routenattribute nur als Warnung; der Lauf scheitert dadurch nicht), nicht importierte Testdateien (`test_test_holes`).
- **Nachgewiesen** (2026-10-17, `tools/check/check.sh`): Ein unbekannter Manifest-Schlüssel in `int_filemanager/__manifest__.py` lässt den Lauf rot werden (`Subtest ManifestLinter.test_manifests (module='int_filemanager') failed`); ohne den Fehler endet derselbe Lauf mit `findings: 0`, `OK`, obwohl `test_pylint` wegen der Core-Befunde fehlschlägt. Für die übrigen `test_lint`-Tests gibt es keinen eigenen Kontrollfall; sie laufen mit, ihre Fehlschläge werden aber nicht mehr verschluckt, weil jeder erkannte Fehlschlag außerhalb der Ausnahmeliste den Lauf rot macht.
- Im Docker-Image fehlt ESLint: `test_eslint` wird dort **übersprungen**, nicht bestanden. Gemessen am 2026-10-17 mit Image `odoo:19.0-hm-test`, lokale Image-ID `sha256:4ea4153978f45179a370d3561734e1abf609e8896609a73db6153113822b66b5`: `command -v eslint` findet nichts. ESLint läuft also nur im pre-commit-Hook auf dem Arbeitsrechner, nicht im Tower-Lauf.

## 4. odoo-ls, Parse-Modus

`odoo_ls_server --parse -c <Odoo-Pfad> -a <Addon-Pfad> -t <Addon-Pfad> --python <python> --stdlib <typeshed>/stdlib -s <typeshed>/stubs -o out.json` schreibt alle Befunde als JSON (Aufruf aus der Projektdoku Dritter,
im Repo von `odoo/odoo-ls` nicht geprüft). Es kennt die Odoo-Registry und findet damit, was Pylint nicht sehen kann.

**Festgelegter Stand** (Tower, `/mnt/user/appdata/fmtest/odoo-ls/`): `odoo_ls_server 1.6.0`, SHA-256 `bdbb18d519462e77a2d5b1d59af079f0c02d024213428b5cd31bc338f2530023`, Datei vom 2026-09-22;
Ausgabeformat `{"events": [{"type": "diagnostic", "uri": …, "diagnostics": [LSP-Diagnose]}]}` (ausgewertet in `tools/check/check_filter.py`). Die Version des mitgelieferten `typeshed` ist nicht vermerkt:
der Release enthält keine Commit-Angabe. Bei einem neuen Release gelten die Nachweise unten nicht mehr und müssen wiederholt werden.

**Nachgewiesen** (2026-10-17, `tools/check/check.sh --quick` mit absichtlich fehlerhaftem Code in `int_filemanager`; jeder Fehler wurde als Stufe 1 gemeldet und ließ den Lauf rot werden):

| Absichtlicher Fehler | Meldung |
|---|---|
| `self.env["kein.solches.modell"]` | `OLS03002` Unknown model |
| `search([("kein_feld", "=", 1)])` auf `res.partner` | `OLS03011` Invalid search domain field |
| `self.env["sale.order"]` ohne `sale` in `depends` | `OLS03001` Model not in the dependencies |
| `self.write()` ohne Werte | `OLS01007` Falsche Zahl der Argumente |
| `<field name="kein_feld">` in einer XML-Datenzeile | `OLS05057` Field not found in model |

**Im Kontrollfall nicht gemeldet** (also nicht als geprüft anzusehen): eine nicht vorhandene Methode auf einem Recordset (`self.nicht_vorhandene_methode()`), zu viele Argumente bei `mapped`, doppelte `<template id>` und doppelte `<record id>` in derselben XML-Datei.
**Nicht ausprobiert:** Compute-Methode, die das Feld nicht setzt, und Related-Feld mit falschem Typ. Die Doku von odoo-ls nennt beides; ein Nachweis fehlt hier.
JavaScript prüft dieser Lauf nicht nachweislich; die Frage, welche JS-Diagnosen odoo-ls liefert, hängt von seinen Abhängigkeiten ab und ist hier nicht untersucht. Fallstricke: (1) `typeshed.zip` aus dem Release gehört dazu, sonst bricht der Lauf ab;
(2) Bibliotheken außerhalb des Images per `PYTHONPATH` sichtbar machen, sonst Fehlalarme; (3) die Ausgabe enthält auch Befunde aus dem Odoo-Kern, nach eigenen Pfaden filtern;
(4) Hinweise mit Stufe 3 (z. B. `OLS03024`) sind Information, kein Fehler. Das Programm beendet sich unabhängig von den Befunden normal, deshalb wertet `tools/check/check_filter.py` das JSON aus.

## 5. Grenzen

- pre-commit läuft nur mit installiertem Hook; ein Commit ohne Hook umgeht die Prüfung.
- Image (`odoo:19.0-hm-test`) und Git-Checkout des Odoo-Kerns können sich unterscheiden; Befunde können dadurch abweichen.
- Logik, Rechte und Performance prüft keines der Werkzeuge; dafür gibt es Tests.
