# Prüfautomatik (pre-commit, test_lint, odoo-ls)

Maschinelle Prüfung des Codes: pre-commit (Ruff, Prettier, ESLint, Standard-Hooks), Odoos `test_lint` und odoo-ls im Parse-Modus. Es gibt keine GitHub Action.
Regeln selbst: `docs/odoo_regeln/odoo_regeln_index_2026-10-02.md` und `docs/odoo_regeln/odoo_regeln_coding_guidelines_2026-10-02.md`.

## 1. Bestandteile

| Werkzeug | Dateien | Wo läuft es | Was es prüft |
|---|---|---|---|
| **pre-commit** | `.pre-commit-config.yaml`, `.ruff.toml` (Zeilenlänge 120), `eslint.config.cjs`, `prettier.config.cjs`, `.editorconfig` | Arbeitsrechner, bei `git commit` | Ruff (Lint + Format), ESLint, Prettier (XML/JS/…), Standard-Hooks (Whitespace, XML, Merge-Marker …) |
| **`test_lint`** | `scripts/lint/run_test_lint.sh` | Tower, Wegwerf-Container aus `odoo:19.0-hm-test` | Odoos eigene Lint-Tests über alle Addon-Pfade (Pylint-Sonderprüfungen, Manifest, `__init__`, Docstring, i18n, Routen …) |
| **odoo-ls** | `scripts/lint/run_odoo_ls.sh`, `scripts/lint/odoo_ls_check.py` | Tower (Docker) oder lokal | Registry-Wissen: unbekannte Modelle/Felder, fehlendes `depends`, falsche Aufrufargumente, doppelte Template-IDs |

`docs/`, `scripts/`, `tools/`, `CLAUDE.md`, `README.md`, `Dockerfile`, `/vendor/`, `static/lib/` und `.svg`-Dateien werden von pre-commit nicht geprüft.
`tools/v2check/v2check.sh` ist der gebündelte Aufruf für `int_filemanager` 2 auf Tower; er läuft unabhängig von `scripts/lint/`.

## 2. Aufruf

```bash
# einmalig auf dem Arbeitsrechner (Windows: py -3.13 -m pre_commit, Programme unter %APPDATA%\Python\Python313\Scripts)
pip install pre-commit && pre-commit install
pre-commit run --all-files                       # oder nur geänderte Dateien bei jedem Commit

# Tower (ssh unraid), im Repo-Checkout
scripts/lint/run_test_lint.sh                    # braucht pylint in $PYLIB (Hinweis im Skript beim ersten Lauf)
MODE=docker scripts/lint/run_odoo_ls.sh          # braucht /tmp/odoo-ls (odoo_ls_server + typeshed/)
```

Rückgabe: Exit-Code ≠ 0 bei Befunden. odoo-ls: Fehler und Warnungen (Stufe 1–2) zählen, Stufe 3 (Information, z. B. `OLS03024`) nicht.

## 3. Grenzen

- pre-commit läuft nur mit installiertem Hook; ein Commit ohne Hook umgeht die Prüfung.
- Im Docker-Image fehlt ESLint: `test_eslint` wird dort **übersprungen**, nicht bestanden.
- Image (`odoo:19.0-hm-test`) und Git-Checkout des Odoo-Kerns können sich unterscheiden; Befunde können dadurch abweichen.
- Logik, Rechte und Performance prüft keines der Werkzeuge; dafür gibt es Tests.

## 4. Was die Werkzeuge prüfen (Nachschlagewerk)

**Odoo `test_lint`** (läuft mit `--test-tags /test_lint`): Pylint mit `used-before-assignment`, `undefined-variable`, `eval-used`,
`unreachable`, `function-redefined`, `sql-injection` (E8501), `raise-unlink-override` (E8503), `gettext-variable` (E8502), `gettext-placeholders` (E8505),
`gettext-repr` (E8506) und `missing-gettext` (E8507: statische Zeichenkette in `UserError`, `ValidationError`, `AccessError`, `AccessDenied`, `MissingError`
ohne `_()`), verbotene Funktion `input`, veraltete Module `csv`/`urllib`/`cgi` und Debugger-Module; dazu Tests für Manifest (Pflichtschlüssel `name`, `author`,
`license`; `application`, `auto_install`, `summary`, `description`, `demo`, `data`, `test` nicht auf dem Standardwert), `__init__.py`, Docstring ↔ Signatur,
ESLint, JS-Übersetzungen, Übersetzbarkeit von Props mit Anzeigetext in Templates (`test_i18n`, Suffix `.translate`), Index auf One2many-Gegenstücken,
Merge-Konfliktmarker, Parameternamen `ids`/`context`, keine Onchange-Domains, kein Import aus `odoo.orm`, Überschreibungs-Signaturen, doppelte `.pot`-Einträge,
`l10n`-Testtags, Routen-Vererbung (unveränderte Werte nicht wiederholen), nicht importierte Testdateien. `test_pylint` prüft den Odoo-Kern (`odoo/`) und alle
Addon-Pfade **außerhalb** von `<root_path>/addons`: Im Git-Checkout liegen die Core-Addons daneben und werden mitgeprüft, im Docker-Image liegen sie darunter und
entfallen. Der Core selbst kann Pylint-Befunde haben; `tools/v2check/v2check_filter.py` filtert auf `int_filemanager`.

**odoo-ls, Parse-Modus:** `odoo_ls_server --parse -c <Odoo-Pfad> -a <Addon-Pfad> -t <Addon-Pfad> --python <python> --stdlib <typeshed>/stdlib
-s <typeshed>/stubs -o out.json` schreibt alle Befunde als JSON. Es findet, was pylint nicht sehen kann, weil es die Odoo-Registry kennt: unbekanntes Modell,
Modell nicht in `depends`, Feld existiert nicht, ungültiges Domain-Feld, Methode existiert nicht, Compute-Methode setzt das Feld nicht, Related-Feld mit
falschem Typ, falsche Aufrufargumente; dazu ESLint (oxc) für JS. Fallstricke: (1) `typeshed.zip` aus dem Release gehört dazu, sonst bricht der Lauf ab;
(2) Bibliotheken außerhalb des Images (z. B. `wsgidav` in `/mnt/pylib`) per `PYTHONPATH` sichtbar machen, sonst Fehlalarme; (3) die Ausgabe enthält auch
Befunde aus dem Odoo-Kern, nach eigenen Pfaden filtern; (4) Hinweise mit Stufe 3 (z. B. `OLS03024`) sind Information, kein Fehler. Das Programm beendet
sich unabhängig von den Befunden normal, deshalb wertet `scripts/lint/odoo_ls_check.py` das JSON aus.

**pre-commit** (Konfiguration dieses Repos): Prettier mit `@prettier/plugin-xml`, ESLint, Standard-Hooks (`trailing-whitespace`, `end-of-file-fixer`,
`debug-statements`, `check-case-conflict`, `check-docstring-first`, `check-executables-have-shebangs`, `check-merge-conflict`, `check-symlinks`, `check-xml`,
`mixed-line-ending`), `ruff` (Lint mit `B`, `C90`, `E501`, `I`, `UP`) und `ruff-format`.
