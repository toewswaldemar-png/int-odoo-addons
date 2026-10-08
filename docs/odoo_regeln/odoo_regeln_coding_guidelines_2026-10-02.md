# Odoo 19 Regeln: Coding Guidelines (Modul, Python, XML, JS/SCSS)

Quellen: nur die offizielle Odoo-Dokumentation 19.0 (Coding Guidelines, lokale Kopie `docs/odoo19_reference/contributing/coding_guidelines.md`) und der Odoo-19-Quelltext
(`odoo/addons/test_lint/tests/`, `ruff.toml` im Odoo-Repository, `addons/web/tooling/`). Marke **[Code]** = steht nur im Quelltext, nicht in der Doku.
Bei Widerspruch gilt der Quelltext. Überarbeitet 2026-10-08: OCA-Regeln, Hausregeln und alles ohne Beleg wurden entfernt.
Git: `odoo_regeln_git_guidelines_2026-10-02.md`. Index: `odoo_regeln_index_2026-10-02.md`.

## Geltungsbereich (Doku)

Die Guidelines gelten für jedes neue Modul und jede Neuentwicklung. Bei Änderungen an **bestehenden Dateien in einer stabilen Version** hat der vorhandene Dateistil Vorrang;
bestehende Dateien nicht umformatieren, Diffs minimal halten. In der Entwicklungsversion (master) gelten die Guidelines für geänderten Code oder wenn der größte Teil der Datei
überarbeitet wird; dann zuerst ein reiner Verschiebe-Commit (move), danach die Änderung.

## 1. Modul

- **Name:** Für Community-Module wird ein Präfix wie der Firmenname dringend empfohlen.
- **Verzeichnisse:** `data/` (Demo- und Daten-XML), `models/`, `controllers/`, `views/`, `static/` (`css/`, `js/`, `img/`, `lib/` …); optional `wizard/` (TransientModels und ihre Views),
  `report/` (druckbare Berichte und SQL-View-Modelle), `tests/`.
- **Dateinamen** nur `[a-z0-9_]`. Rechte: Ordner 755, Dateien 644.
  - **Modelle:** Gruppen zusammengehöriger Modelle je Datei, benannt nach dem Hauptmodell (`models/plant_order.py`); hat das Modul nur ein Modell, heißt die Datei wie das Modul;
    jedes geerbte Modell in eigener Datei (`models/res_partner.py`).
  - **Sicherheit:** `security/ir.model.access.csv`, Gruppen `security/<modul>_groups.xml`, Regeln `security/<modell>_security.xml`.
  - **Views:** Backend-Views `views/<modell>_views.xml`; Hauptmenüs ohne Aktion optional `views/<modul>_menus.xml`; Templates (Portal/Website) `views/<modell>_templates.xml`.
  - **Daten:** `data/<hauptmodell>_data.xml` bzw. `…_demo.xml`; Daten zu anderen Modulen (z. B. `mail_data.xml`) getrennt nach Zweck.
  - **Controller:** `controllers/<modulname>.py`; `main.py` gilt als veraltet; erbt man einen Controller eines anderen Moduls, heißt die Datei `<geerbtes_modul>.py` (`portal.py`).
  - **Wizard:** `wizard/<transient>.py` und `wizard/<transient>_views.xml`.
  - **Berichte:** SQL-/Statistikberichte `report/<modell>_report.py` + `…_report_views.xml`; druckbare Berichte `…_reports.xml` (Aktionen, Papierformat) + `…_templates.xml`.
  - **Statisches:** `static/src/js|scss|xml`, `static/src/js/tours` (Endnutzer-Tours), `static/tests/tours` (Test-Tours), `static/lib/<name>/`, `static/fonts`, `static/img`, `static/tests`;
    eine Komponente je Datei mit sprechendem Namen, Templates und Styles analog. Keine externen URLs auf Bilder oder Bibliotheken, in die Codebasis kopieren.
- **`__init__.py`** in jedem Modul **[Code]** (`test_dunderinit`).

## 2. Manifest

- **[Code]** `test_manifests`: Unbekannte Schlüssel sind ein Fehler. Erlaubt sind die Schlüssel aus `_DEFAULT_MANIFEST` (`odoo/modules/module.py`) sowie `name`, `icon`, `addons_path`, `author`, `license`,
  `contributors`, `maintainer`, `url`, `price`, `currency`, `support`, `live_test_url`.
- **[Code]** `application`, `auto_install`, `summary`, `description`, `author`, `demo`, `data`, `test` nicht auf ihren Standardwert setzen; `icon` nicht auf den Standardpfad.
- **[Code]** `name`, `author`, `license` sind im Code als Pflichtfelder vermerkt; eine fehlende `license` ergibt nur eine Warnung (Standard LGPL-3).
- Einzelheiten und alle Schlüssel: `odoo_regeln_data_manifest_2026-10-02.md`.

## 3. Python

### PEP8 und Imports
- Odoo ignoriert die PEP8-Meldungen E501 (Zeilenlänge), E301 und E302 (Doku). Es gibt keine vorgeschriebene Zeilenlänge.
- **Import-Reihenfolge** (Doku): 1. Python-Standardbibliothek und externe Bibliotheken (je Zeile eine, sortiert), 2. `odoo`-Untermodule, 3. Odoo-Addons (selten, nur wenn nötig); innerhalb der Gruppen alphabetisch.
  Beispiel: `from odoo import Command, _, api, fields, models`, `from odoo.fields import Domain`, `from odoo.addons.web.controllers.main import …`.
- **[Code]** Nicht aus `odoo.orm` importieren, sondern aus `odoo` (`test_orm_import`).
- **[Code]** `test_pylint`: Funktion `input` verboten; Module `csv`, `urllib`, `cgi` und Debugger-Module (`SUPPORTED_DEBUGGER`) als veraltet gemeldet; aktive Prüfungen u. a. `used-before-assignment`,
  `undefined-variable`, `eval-used`, `unreachable`, `function-redefined` und die Odoo-Prüfungen aus Abschnitt „Übersetzung“ und „SQL“.
- **[Code]** `ruff.toml` im Odoo-Repository (automatisch von der Runbot erzeugt) legt die von Odoo geprüften Ruff-Regeln fest; E501 und C901 sind dort ausdrücklich ignoriert, ein Formatierer ist nicht konfiguriert.
  Die Datei nennt zusätzlich Regeln, die „empfohlen, aber nicht erzwungen“ sind: B904, COM812, E741, EM101, I001, RET, RUF021, RUF102, TID252, UP006, UP007.

### Idiome (Doku)
- Lesbarkeit vor Kürze; sprechende Namen; keine überflüssigen Hilfsvariablen; mehrere `return` sind erlaubt, wenn einfacher.
- Kein `.clone()`, sondern `dict(x)` / `list(x)`; Dicts direkt mit Werten anlegen, `update` für Mehrfachänderungen; `dict.get('key')` statt `get('key', None)`.
- Comprehensions statt Schleifen mit `append`; `if collection:` statt `if len(collection):`; direkt über Dicts iterieren; `dict.setdefault`.
- Methoden `filtered`, `mapped`, `sorted` des Recordsets nutzen. Keine eigenen Generatoren und Dekoratoren, nur die der Odoo-API.
- Dokumentieren: Docstring an Methoden, einfache Kommentare für knifflige Stellen.

### Odoo-spezifisch (Doku)
- **Kontext:** Er ist ein `frozendict`; ändern nur über `with_context(...)`. Kontextschlüssel haben Nebenwirkungen (z. B. `default_<feld>` wirkt auf alle in der Aktion erzeugten Datensätze);
  eigene Schlüssel mit gutem Namen, gegebenenfalls mit Modulpräfix (Vorbild `mail_create_nosubscribe`, `mail_notrack`).
- **Erweiterbar bauen („Think extendable“):** Methoden klein halten, eine Verantwortung je Methode; Domains und Kriterien in eigene überschreibbare Methoden auslagern, mit Augenmaß.
- **Transaktion:** Nie `cr.commit()` oder `cr.rollback()` selbst aufrufen, **außer** auf einem selbst geöffneten Cursor; jedes `cr.commit()` außerhalb des Frameworks braucht einen ausdrücklichen Kommentar
  (warum nötig, warum korrekt, warum keine Transaktion bricht). Kein `commit()` nötig in `_auto_init`, in Berichten und in `TransientModel`-Methoden.
  Geplante Aktionen laufen in eigener Transaktion: fängt man dort Fehler und will weitermachen, `rollback`; Fortschritt über `_commit_progress` (`odoo_regeln_actions_cron_http_reports_2026-10-02.md`).
- **Ausnahmen:** Nur konkrete Typen fangen, `try`-Block so klein wie möglich. Framework-Ausnahmen nur mit `with self.env.cr.savepoint():` abfangen; ab etwa 64 Savepoints je Transaktion wird PostgreSQL langsamer,
  auf Replikaten ist der Aufwand hoch; in Schleifen Batches begrenzen.
- **Übersetzung** (Doku): `self.env._('Literal %s', wert)`. Nur für feste, von Hand geschriebene Zeichenketten; Feldwerte über `translate=True` am Feld. Formatierung **als Argument**, nie vorher
  (`_('… %s' % x)` und `_('…') % x` sind falsch); keine dynamischen Zeichenketten oder Verkettungen. Bei einer Variablen `%` statt `.format()`, bei mehreren benannte Platzhalter `%(name)s`.
  **[Code]** `test_pylint` prüft das: `gettext-variable` (E8502), `gettext-placeholders` (E8505: mehrere unbenannte Platzhalter), `gettext-repr` (E8506: kein `%r`),
  `missing-gettext` (E8507: statische Zeichenkette in `UserError`, `ValidationError`, `AccessError`, `AccessDenied`, `MissingError` ohne Übersetzungsaufruf).
- **[Code] SQL:** `sql-injection` (E8501) meldet möglichen SQL-Einschleusung in `execute`-Aufrufen.
- **[Code] `unlink()` überschreiben:** Kein `raise` darin (`raise-unlink-override`, E8503); stattdessen eine Methode mit `@api.ondelete(at_uninstall=False)`.
- **[Code]** Öffentliche Methoden: Parameter dürfen nicht `ids` oder `context` heißen (`test_naming`, wegen RPC).
- **[Code]** Überschreibungen müssen zur Signatur der Elternmethode passen (`test_override_signatures`).
- **[Code]** Many2one, die das Gegenstück eines One2many sind, brauchen einen Index (`test_index`); Domains dürfen nicht aus `@api.onchange` zurückgegeben werden (`test_onchange_domains`, veraltet);
  Docstring-Parameter müssen zur Signatur passen (`test_docstring`).

### Symbole und Namen (Doku)
- **Modellnamen:** Punktschreibweise mit Modulpräfix, **Einzahl** (`res.partner`). Transient (Wizard): `<basismodell>.<aktion>` ohne das Wort „wizard“ (`account.invoice.make`).
  SQL-Report: `<basismodell>.report.<aktion>`.
- **Klassen** PascalCase. **Variablen** snake_case, Modell-Variablen PascalCase (`Partner = self.env['res.partner']`); `_id`/`_ids` nur für IDs, nicht für Datensätze.
- **Felder:** Many2one `…_id`, One2many/Many2many `…_ids`.
- **Methodenmuster:** `_compute_<feld>`, `_search_<feld>`, `_default_<feld>`, `_selection_<feld>`, `_onchange_<feld>`, `_check_<bedingung>`; Aktionsmethoden `action_<…>` mit `self.ensure_one()` bei Einzeldatensatz.
- **Reihenfolge im Modell:** 1. private Attribute (`_name`, `_description`, `_inherit` …), 2. Default-Methoden und `default_get`, 3. Felder, 4. SQL-Constraints und Indizes, 5. Compute-/Inverse-/Search-Methoden in der Reihenfolge der Felder,
  6. Selection-Methoden, 7. `@api.constrains` und `@api.onchange`, 8. CRUD-Überschreibungen, 9. Aktionsmethoden, 10. übrige Geschäftsmethoden.

## 4. Sicherheit

Die Doku verlangt, die Security Pitfalls zu lesen: `odoo_regeln_security_2026-10-02.md`.

## 5. XML (Doku)

- **`<record>`:** `id` vor `model`; bei `<field>` zuerst `name`, dann Wert (im Tag oder `eval`), dann weitere Attribute nach Wichtigkeit. Records nach Modell gruppieren, soweit Abhängigkeiten es zulassen.
- **`<data>`** nur für nicht aktualisierbare Daten mit `noupdate="1"`; enthält die Datei nur solche, `noupdate="1"` am `<odoo>`-Tag und kein `<data>`.
- **`<menuitem>`** und **`<template>`** sind vorzuziehen gegenüber `<record>`.
- **XML-IDs:** Menü `<modell>_menu` (Untermenü `<modell>_menu_<zweck>`); View `<modell>_view_<typ>`; Aktion `<modell>_action`, weitere `<modell>_action_<detail>`, Fenster-Aktionen `<modell>_action_view_<typ>`;
  Gruppe `<modul>_group_<name>`; Regel `<modell>_rule_<gruppe>` (`user`, `public`, `company` …). `name` der View = XML-ID mit Punkten statt Unterstrichen; Aktionen bekommen einen echten Anzeigenamen.
- **Geerbte Views:** gleiche ID wie das Original, `name` mit Suffix `.inherit.<details>`; neue Primär-Views brauchen das Suffix nicht.

## 6. JavaScript und CSS/SCSS (Doku)

- **Struktur:** `static/lib` (Bibliotheken in Unterordnern), `static/src` (`css`, `js`, `js/tours`, `scss`, `xml`), `static/fonts`, `static/img`, `static/tests` (`tours` für Test-Tours).
- **JS:** `use strict` empfohlen; Linter verwenden; nie minifizierte Bibliotheken; Klassen PascalCase.
- **[Code]** Odoos eigenes Werkzeug `addons/web/tooling` (`_eslintrc.json`, `_package.json`) nutzt ESLint mit Prettier (`printWidth` 100, `tabWidth` 4, doppelte Anführungszeichen, `semi`); `test_eslint` (in `test_lint`) prüft alle JS-Dateien
  der Module mit `test_lint/tests/eslintrc`, wenn ESLint installiert ist.
- **[Code]** JS-Übersetzungen: keine Template-Strings mit Ausdrücken in `_t(...)` (`test_jstranslate`); Props mit Anzeigetext in Owl-Templates tragen das Suffix `.translate` (`test_i18n`).
- **SCSS-Format:** 4 Leerzeichen, keine Tabs, Spalten max. 80 Zeichen, `{` nach einem Leerzeichen, `}` in eigener Zeile, eine Deklaration je Zeile. Eigenschaften von „außen nach innen“ (Position zuerst, dekorative Regeln zuletzt),
  scoped SCSS-Variablen und CSS-Variablen ganz oben, durch Leerzeile getrennt.
- **Klassen:** Präfix `o_<modul>` (technischer Modulname bzw. Hauptroute; Webclient nur `o_`), keine ID-Selektoren, keine übermäßig spezifischen Namen; verschachtelte Elemente nach dem „Enkel“-Prinzip
  (`o_element_entry`, nicht `o_element_wrapper_entries_entry`).
- **SCSS-Variablen:** global `$o-[root]-[element]-[property]-[modifier]` (root = Komponente oder Modul, Komponente hat Vorrang); lokal `$-[name]`; Mixins und Funktionen `o-[name]`, Funktionen mit Verb im Imperativ, optionale Argumente als `$-[argument]`.
- **CSS-Variablen:** ausschließlich DOM-bezogen, zur kontextuellen Anpassung; Namen nach BEM `--[Root]__[element]-[property]--[modifier]`. Das Design-System steckt in SCSS-Variablen,
  kombiniert über `var(--MyComponent-color, #{$o-component-color})`. CSS-Variablen normalerweise **nicht** auf `:root` (Ausnahme: über Bundles geteilte Templates).

## 7. Tests

Regeln: `odoo_regeln_testing_2026-10-02.md` und `odoo_regeln_js_tests_2026-10-02.md`.

## 8. Prüfwerkzeuge von Odoo

Welche Werkzeuge Odoo selbst mitbringt und was sie prüfen: `docs/pruefautomatik_2026-10-02.md`.
