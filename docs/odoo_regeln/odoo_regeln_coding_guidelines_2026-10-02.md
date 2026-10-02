# Odoo 19 Regeln: Coding Guidelines (Modul, Manifest, Python, XML, JS/SCSS, Tests) und Hausregeln

Quelle: Odoo-Coding-Guidelines 19.0 (`odoo/documentation`, `content/contributing/development/coding_guidelines.rst`, Commit `eee2e56`,
Stand 2026-10-02), ergänzt um die OCA-Richtlinien und die Hausregeln dieses Repos (Abschnitt 8). Git: `odoo_regeln_git_guidelines_2026-10-02.md`.
Gilt für **neuen** Code, insbesondere `int_filemanager` 2. Englische Fachbegriffe bleiben, wo sie im Code so heißen. Index:
`docs/odoo_regeln/odoo_regeln_index_2026-10-02.md`.

## Quellen und Rangfolge

| # | Quelle | Art |
|---|---|---|
| 1 | Odoo **Coding Guidelines** 19.0 | offizielle Regeln |
| 2 | Odoo **Security Pitfalls** (`backend/security.rst`) | von 1 ausdrücklich verlangt, siehe `odoo_regeln_security_2026-10-02.md` |
| 3 | Odoo **`test_lint`** (`odoo/addons/test_lint/tests/`, im Image `odoo:19.0`) | was Odoos CI maschinell prüft; läuft über **alle** Addon-Pfade, also auch über unsere Module |
| 4 | **OCA Guidelines** (`OCA/odoo-community.org`, `CONTRIBUTING.rst`) | Community-Regeln (Stand-Datum 2018, teils veraltet; Tests/Commits aktualisiert) |
| 5 | **OCA-Repo-Vorlage** (`.pre-commit-config.yaml`, `.pylintrc-mandatory`) | was die OCA maschinell prüft |
| 6 | **odoo-ls**, **upgrade-util** | Odoo-Werkzeuge, keine Regeln (`docs/pruefautomatik_2026-10-02.md`, Abschnitt 2 hier) |

Rangfolge: Odoo (1–3) vor OCA (4–5). Bei Änderungen an **bestehendem** Code gilt: vorhandenen Stil nicht umformatieren, Diffs klein halten;
größere Umstellungen erst als reiner Verschiebe-Commit (`[MOV]`), dann die Änderung.

---

## 1. Modul

- **Name mit Präfix** der eigenen Firma/des eigenen Kürzels ("strongly recommended"), hier `int_`. Einzahl (OCA). Erweitert man ein Odoo-Modul,
  steht dessen Name vorn (OCA: `mail_forward`).
- **Verzeichnisse:** `models/`, `views/`, `security/`, `data/`, `demo/` (OCA), `controllers/`, `static/`, `wizard/` (Odoo) bzw. `wizards/` (OCA),
  `report/`, `tests/`, `migrations/<version>/` (pre-/post-migration), `i18n/`.
- **Dateinamen** nur `[a-z0-9_]`; Ordner 755, Dateien 644.
  - Modelle: **eine Datei je Hauptmodell**, benannt nach dem Modell (`models/plant_order.py`); jedes geerbte Modell in eigener Datei (`models/res_partner.py`).
  - Views: `views/<model>_views.xml`, Menüs optional `views/<module>_menus.xml`, Portal/QWeb `<model>_templates.xml`.
  - Security: `security/ir.model.access.csv`, Gruppen `security/<module>_groups.xml`, Regeln `security/<model>_security.xml`.
  - Daten: `data/<model>_data.xml`, Demo `data/<model>_demo.xml` (OCA: eigener Ordner `demo/`).
  - Controller: `controllers/<module>.py` (Odoo; `main.py` gilt als veraltet, OCA nennt noch `main.py`).
  - Wizard: `wizard/<transient>.py` + `<transient>_views.xml`.
  - Statisches: `static/src/js|scss|xml|img|css`, Onboarding-Tours für Endnutzer `static/src/js/tours/`, Test-Tours `static/tests/tours/`,
    Bibliotheken `static/lib/<name>/`, Schriften `static/fonts`, Tests `static/tests/`; eine Komponente je Datei. Keine externen URLs auf
    Bilder/Bibliotheken, ins Modul kopieren.
- `__init__.py` in jedem Modul (Odoo `test_dunderinit`).

## 2. Manifest (`__manifest__.py`)

- Nur erlaubte Schlüssel (Odoo `test_manifests`): Pflicht `name`, `author`, `license`; übliche optionale (`version`, `summary`, `description`,
  `category`, `depends`, `data`, `demo`, `assets`, `external_dependencies`, `installable`, `application`, `auto_install`, `post_load`, Hooks,
  `countries`, `images`, `icon` …), informativ `contributors`, `maintainer`, `url`, App-Store-Schlüssel. Unbekannte Schlüssel sind ein Fehler.
- **Keine Schlüssel auf ihren Standardwert setzen** (z. B. `application: False`, `auto_install: False`, `demo: []`); `icon` nicht auf den Standardpfad.
- **Version** `19.0.x.y.z`: x = Datenmodell/Views mit Migrationsbedarf, y = neue Funktion abwärtskompatibel, z = Fehlerbehebung (OCA). Bei brechenden
  Änderungen Migrationsskript in `migrations/19.0.x.y.z/`.
- **Migrationsskripte** mit `odoo/upgrade-util` schreiben statt eigenem SQL (`from odoo.upgrade import util`: Felder/Modelle umbenennen oder entfernen,
  Datensätze verschieben, Domains anpassen, SQL-Helfer). Einbinden über `--upgrade-path=<upgrade-util>/src` oder
  `pip install git+https://github.com/odoo/upgrade-util@master` (im Image nicht enthalten). Dieselben Helfer nutzt Odoo für seine eigenen Versionssprünge.
- `license` und (OCA) `images` angeben, keine leeren Schlüssel. Externe Python-Pakete/Programme in `external_dependencies`
  (kein `try: import … except ImportError: … = object` als Ersatz).

## 3. Python

### Stil und Imports
- PEP8; Odoo ignoriert E501 (Zeilenlänge), E301, E302. OCA formatiert automatisch mit **black** (bzw. ruff), räumt mit **autoflake** auf.
- **Import-Reihenfolge:** 1. Standardbibliothek/externe Bibliotheken, 2. `odoo`-Module, 3. `odoo.addons.*` (selten); innerhalb alphabetisch.
  Beispiel: `from odoo import Command, _, api, fields, models`, `from odoo.fields import Domain`.
- **Nicht** direkt aus `odoo.orm` importieren, sondern aus `odoo` (`api`, `fields`, `models`).
- Veraltete Module nicht benutzen: `csv`, `urllib`, `cgi`, Debugger-Module; kein `input()`.
- **Englisch** für Namen und Kommentare; Texte für Nutzer über die Übersetzung.
- Bei umbrochenen Aufrufen/Listen am öffnenden Zeichen umbrechen, **Komma nach dem letzten Element** (OCA).

### Idiome
- Lesbarkeit vor Kürze; sprechende Namen; kleine Methoden mit **einer** Aufgabe ("Think extendable": Domains und Kriterien in eigene, überschreibbare
  Methoden auslagern).
- `dict(x)`/`list(x)` statt `.clone()`; Dicts direkt mit Werten anlegen; `dict.get('k')` statt `get('k', None)`; `if collection:` statt `if len(...)`;
  über Dicts direkt iterieren; `setdefault`; Comprehensions.
- Recordset-Methoden: `filtered`, `mapped`, `sorted`, `grouped`.
- Keine eigenen Generatoren/Dekoratoren, nur die der Odoo-API.
- Docstrings für Methoden, Kommentare nur für knifflige Stellen.

### Kommentare und Docstrings

**Odoo/OCA-Regeln:**
- **Docstring** an Methoden erklärt den **Zweck**. Werden Parameter dokumentiert (`:param x:`, `:return:`, reStructuredText wie im Odoo-Kern), müssen sie
  zur Signatur passen (`test_docstring`).
- **Kommentare nur für knifflige Stellen**; viele Kommentare sind meist ein Zeichen für unklaren Code, dann umbenennen oder aufteilen statt kommentieren.
- **Pflicht-Kommentare:** jedes `cr.commit()` (warum nötig und korrekt); jedes `position="replace"` in Views (warum unvermeidbar).

**Hausregeln** siehe Abschnitt 8.

### Odoo-spezifisch
- **Kontext** nur über `with_context(...)`; eigene Kontextschlüssel mit Modulpräfix (Vorbild `mail_notrack`); Vorsicht mit `default_*`-Schlüsseln
  (wirken auf alle erzeugten Datensätze).
- **Nie `cr.commit()`/`cr.rollback()`**, außer im **selbst geöffneten** Cursor, dann mit ausdrücklichem Kommentar. Odoo stellt je Request, Test und Cron
  die Transaktion. Kein `commit()` nötig in `_auto_init`, Reports und `TransientModel`-Methoden. Fängt eine geplante Aktion Fehler und soll weiterlaufen:
  **rollback**; Crons laufen in eigener Transaktion, Fortschritt über `IrCron._commit_progress`
  (`odoo_regeln_actions_cron_http_reports_2026-10-02.md`, Abschnitt 2). Pylint-OCA: `invalid-commit`.
- **Ausnahmen:** nur konkrete Typen fangen, kleiner `try`-Block; Framework-Fehler nur mit `with self.env.cr.savepoint():` abfangen (≤ 64 Savepoints je
  Transaktion, in Schleifen Batches). Kein `except: pass` (OCA `except-pass`). Fehlermeldungen für Nutzer: `UserError`/`ValidationError`/`AccessError`.
- **Übersetzung:** `self.env._('Literal %s', wert)`, nur feste Zeichenketten, Formatierung **als Argument**, nie vorher (`_('… %s' % x)` und `_('…') % x`
  sind falsch); bei einem Platzhalter `%`, bei mehreren benannt `%(name)s`; `%` statt `.format()`; keine f-Strings (Odoo `gettext-*`, OCA `translation-*`).
  Feldwerte nicht über `_()` übersetzen (`translate=True` am Feld).
- **`unlink()` überschreiben:** kein `raise` darin, Prüfungen mit `@api.ondelete(at_uninstall=False)` (`raise-unlink-override`).
- Öffentliche Methoden: keine Parameter namens `ids` oder `context` (`test_naming`).
- Überschreibungen behalten die **Signatur** der Elternmethode (`test_override_signatures`) und rufen `super()` auf (OCA `method-required-super`).
- Many2one, die Gegenstück eines One2many sind: **Index** (`index=True`, `test_index`).
- Keine Domains aus `@api.onchange` zurückgeben (veraltet).
- Kein `print`, `logging` über `_logger = logging.getLogger(__name__)`.
- Externe HTTP-Aufrufe immer mit `timeout` (OCA `external-request-timeout`).
- Kein Schreiben in Compute-Methoden (`no-write-in-compute`); kein `search([])` über alles ohne Grund (`no-search-all`).

### Namen (Symbole)
- **Modellnamen:** Punkt-Schreibweise, **mit Modulpräfix**, **Einzahl** (`sale.order`). Transient: `<basismodell>.<aktion>` ohne "wizard"
  (`account.invoice.make`). SQL-Report: `<basis>.report.<aktion>`.
- **Klassen** PascalCase. **Variablen** snake_case; Modell-Variablen PascalCase (`Partner = self.env['res.partner']`); `_id`/`_ids` **nur** für IDs,
  nicht für Datensätze. Konstanten GROSS.
- **Felder:** Many2one `…_id`, One2many/Many2many `…_ids`. Kein `string=`, wenn er dem Feldnamen entspricht. Standardwerte als
  `lambda self: self._default_x()`, damit vererbbar.
- **Methoden:** `_compute_<feld>`, `_inverse_<feld>`, `_search_<feld>`, `_default_<feld>`, `_selection_<feld>`, `_onchange_<feld>`, `_check_<bedingung>`,
  Aktionen `action_<…>` (mit `self.ensure_one()` bei Einzeldatensatz).
- **Reihenfolge im Modell:** private Attribute (`_name`, `_description`, `_inherit`, …) → Default-Methoden → Felder → SQL-Constraints/Indizes →
  Compute/Inverse/Search (in Feldreihenfolge) → Selection-Methoden → `@api.constrains`/`@api.onchange` → CRUD-Überschreibungen → Aktionen → übrige Geschäftsmethoden.

## 4. Sicherheit

Verbindlich und ausführlich: `odoo_regeln_security_2026-10-02.md` (Security Pitfalls, Rechte, `Markup`, `Domain`, `eval`). Kernsätze:

- Öffentliche Methoden sind per RPC mit beliebigen Argumenten aufrufbar; `sudo()` nie auf nutzergesteuerte Eingaben.
- ORM nicht umgehen; wo SQL nötig ist, `odoo.tools.SQL` mit Parametern.
- Kein `t-raw`, kein `eval`; HTML in Python nur mit `Markup`.

## 5. XML

Ausführlich: `odoo_regeln_views_2026-10-02.md`, `odoo_regeln_data_manifest_2026-10-02.md`.

- `<record>`: `id` vor `model`; bei `<field>` zuerst `name`, dann Wert/`eval`, dann weitere Attribute. Nach Modell gruppieren. 4 Leerzeichen Einrückung (OCA).
- `<data>` nur für gemischte `noupdate`-Blöcke; sonst `<odoo>` bzw. `<odoo noupdate="1">`.
- `<menuitem>` und `<template>` statt `<record>` für Menüs/QWeb.
- **XML-IDs:** Menü `<model>_menu[_<zweck>]`; View `<model>_view_<typ>`; Aktion `<model>_action[_<detail>]`, Fenster `…_action_view_<typ>`; Gruppe
  `<module>_group_<name>`; Regel `<model>_rule_<gruppe>`; Demo-Datensätze mit Suffix `demo` (OCA). **Kein** Modulpräfix in der eigenen ID (OCA).
  View-`name` = XML-ID mit Punkten.
- **Geerbte Views:** gleiche ID wie das Original, `name` mit `.inherit.<modul>`; neue Primär-Views ohne Suffix. `position="replace"` vermeiden (wenn doch:
  Kommentar + hohe `priority`); ein Modul erweitert eine View nur einmal.
- Keine veralteten Attribute/Knoten (OCA `xml-deprecated-*`); `ir.filters` mit ausdrücklichem `user_id`.

## 6. JavaScript, CSS/SCSS

Ausführlich: `odoo_regeln_js_framework_2026-10-02.md`, `odoo_regeln_ui_icons_scss_2026-10-02.md`.

- Struktur `static/src/js|scss|xml`, `static/lib/`, `static/tests/`.
- ESLint (Odoo prüft alle JS-Dateien), prettier (OCA); `use strict` empfohlen (native Module sind es ohnehin); nie minifizierte Bibliotheken; Klassen PascalCase.
- **CSS-Klassen** mit Präfix `o_<modul>` (Webclient: `o_`), keine ID-Selektoren, Bootstrap-Klassen nutzen, verschachtelte Elemente nach dem
  "Enkel"-Prinzip (`o_element_entry`, nicht `o_element_wrapper_entries_entry`).
- **SCSS-Format:** 4 Leerzeichen, max. 80 Zeichen, `{` nach Leerzeichen, `}` in eigener Zeile, eine Deklaration je Zeile. Eigenschaften "von außen nach
  innen" (Position → Box → Rahmen → Hintergrund → Schrift → Effekte), lokale Variablen zuoberst.
- **Variablen:** SCSS global `$o-[root]-[element]-[eigenschaft]-[modifier]`, SCSS lokal `$-[name]`, Mixins/Funktionen `o-[name]` (Funktionen mit Verb),
  CSS-Variablen BEM `--[Root]__[element]-[eigenschaft]--[modifier]`.
- **CSS-Variablen sind ausschließlich DOM-bezogen** (kontextuelle Anpassung, Standardwert im Komponentenblock); das Design-System steckt in
  SCSS-Variablen, kombiniert über `color: var(--MyComponent-color, #{$o-component-color})`. **Keine CSS-Variablen auf `:root`** (Ausnahme: Templates,
  die über Bundles geteilt werden).
- JS-Übersetzungen: keine Template-Strings mit Ausdrücken in `_t(...)` (`test_jstranslate`).

## 7. Tests

Regeln und Hausregeln: `odoo_regeln_testing_2026-10-02.md` und `odoo_regeln_js_tests_2026-10-02.md`. Ergänzend gegen flaky Tests: in
Klassenvariablen gespeicherte Datensätze tragen ihr altes `env` (Nutzer, sudo, Kontext) mit; feste Daten statt `now()` (`freezegun`); externe Dienste
mocken (`unittest.mock`, `classPatch`).

## 8. Hausregeln dieses Repos

**Kommentare und Docstrings** (ergänzend, Entscheidung 2026-09-26):
1. **Warum statt Was:** der Kommentar nennt den Grund, nicht was der Code ohnehin sagt (schlecht: `# increase counter`; gut: `# Blob must be on disk
   before its row is committed; a crash leaves only an orphan the GC removes.`).
2. **Keine Verweise auf Dokumente** (Entscheidung 2026-09-28): keine Kürzel (`I1`, `A3` …), keine Konzept-Abschnitte, keine Prüfbericht-Nummern, keine
   Fundgeschichte ("found on Tower …"). Der Kommentar muss ohne Dokument verständlich sein; wo Code eine Grundregel absichert, steht der Grund im
   Klartext. Verweise auf Dateien im selben Repo-Ordner (z. B. eine README daneben) sind erlaubt.
3. **Docstrings wie im Odoo-Kern:** eine Zeile, was die Funktion tut (Imperativ: "Return …", "Create …"); nur wenn nötig danach wenige Zeilen zu
   Randbedingungen. Kein Ablaufprotokoll, keine Aufzählung der Aufrufer. Docstring an jeder Methode, deren Zweck nicht aus dem Namen folgt (Odoo Guidelines: "docstring on methods"); bei selbsterklärenden
   Methoden entfällt er (im Odoo-Kern hat ein Viertel der Methoden in `models/` einen, Median 3 Zeilen; gemessen 2026-10-02).
4. **Odoo-Stellen per Funktionsname, nicht per Zeilennummer** (`# odoo.http.Stream.get_response only uses X-Accel below data_dir/filestore`, nicht
   `# see http.py:665`); Zeilennummern verschieben sich mit jedem Update.
5. **Kein auskommentierter Code, keine Autor-/Datumszeilen** (steht in Git); `TODO` nur mit Begründung.
6. **Begründung einer Änderung in die Commit-Nachricht** (das *Warum*); der Kommentar erklärt, warum der Code *jetzt* so ist.
7. **Dichte wie im umgebenden Code**; keine Kommentarwände, bei Odoo-typischem Code (Felder, Views) meist keine.

Beispiel:

```python
def reserve_blob(self):
    """Create the blob row and commit it before the upload starts."""
    # Own cursor, so the request transaction stays untouched: committing before streaming
    # keeps no transaction open for the whole upload (would hold the snapshot, block VACUUM).
    with self.pool.cursor() as cr:
        blob = self.env(cr=cr)["int_filemanager.blob"].create({})
        cr.commit()
    return blob.id
```

**Sprache und Namen** (Entscheidung 2026-09-26):
- Neuer Code **englisch**: Namen, Kommentare, Docstrings, Log-Meldungen, Commits; Oberflächentexte englisch im Code, deutsche Übersetzung in `i18n/de.po`.
- Modellnamen mit Modulpräfix, z. B. `int_filemanager.node`.

**Code:**
- `cr.commit()` nur im selbst geöffneten Cursor (Crons mit eigenem Cursor, eigene Server-Prozesse) und mit Kommentar.
- `sudo()` nie auf Nutzereingaben; jede Stelle begründet.
- Rohes SQL nur, wo das ORM nicht reicht, mit `odoo.tools.SQL` und Rechteprüfung über das ORM danach.
- Migrationsskripte mit `odoo/upgrade-util` (ab dem ersten Datenmodell-Wechsel nach Inbetriebnahme).
- Manifest: keine Schlüssel mit Standardwert; `external_dependencies` angeben (z. B. `wsgidav`) statt `except ImportError`-Ersatz.
- Öffentlich ist nur, was mit beliebigen Argumenten sicher ist (JSON-2 macht jede öffentliche Modellmethode für jeden angemeldeten Nutzer aufrufbar).

**Werkzeuge:** pre-commit nach OCA-Vorlage (nur für neuen Code), Odoos `test_lint` und odoo-ls müssen ohne Befund im eigenen Code laufen; keine GitHub
Action. Aufruf, Altbestand und Verifikationsstand: `docs/pruefautomatik_2026-10-02.md`.
