# Odoo-Konventionen (Stand Odoo 19, geprüft 2026-09-26)

Zusammenfassung aller Konventionen für Odoo-Code aus den maßgeblichen Quellen auf GitHub. Gilt für neuen Code in
diesem Repo, insbesondere int_filemanager 2. Englische Fachbegriffe bleiben, wo sie im Code so heißen.

## Quellen und Rangfolge

| # | Quelle | Art |
|---|---|---|
| 1 | Odoo **Coding Guidelines** 19.0 – `odoo/documentation`, `content/contributing/development/coding_guidelines.rst` | offizielle Regeln |
| 2 | Odoo **Git Guidelines** 19.0 – `…/git_guidelines.rst` | Commit-Nachrichten |
| 3 | Odoo **Security Pitfalls** – `content/developer/reference/backend/security.rst` | Sicherheitsregeln, von 1 ausdrücklich verlangt |
| 4 | Odoo **`test_lint`** – `odoo/addons/test_lint/tests/` (im Image `odoo:19.0`) | was Odoos CI **maschinell** prüft; läuft über **alle** Addon-Pfade, also auch über unsere Module |
| 5 | **OCA Guidelines** – `OCA/odoo-community.org`, `website/Contribution/CONTRIBUTING.rst` | Community-Regeln (Stand-Datum 2018, teils veraltet; Tests/Commits aktualisiert) |
| 6 | **OCA-Repo-Vorlage** – `OCA/oca-addons-repo-template` (`.pre-commit-config.yaml`, `.pylintrc-mandatory`) | was die OCA **maschinell** prüft (Stand 09/2026) |
| 7 | **odoo-ls** – `odoo/odoo-ls` (Odoo Language Server, Release 1.6.0 vom 2026-09-22) | Odoo-eigene statische Prüfung, die Modelle, Felder und Abhängigkeiten kennt (Abschnitt 9) |
| 8 | **upgrade-util** – `odoo/upgrade-util` | Odoos eigene Hilfsfunktionen für Migrationsskripte (Abschnitt 1) |

Rangfolge: Odoo (1–4) vor OCA (5–6); 7 und 8 sind Odoo-Werkzeuge, keine Regeln. Bei Änderungen an **bestehendem** Code gilt nach Odoo 1: vorhandenen Stil nicht
umformatieren, Diffs klein halten; größere Umstellungen erst als reiner Verschiebe-Commit, dann die Änderung.

---

## 1. Modul

- **Name mit Präfix** der eigenen Firma/des eigenen Kürzels (Odoo 1: "strongly recommended"), hier `int_`. Einzahl
  (OCA 5). Erweitert man ein Odoo-Modul, dessen Name vorn (OCA 5: `mail_forward`).
- **Verzeichnisse:** `models/`, `views/`, `security/`, `data/`, `demo/` (OCA), `controllers/`, `static/`, `wizard/`
  (Odoo) bzw. `wizards/` (OCA), `report/`, `tests/`, `migrations/<version>/` (pre-/post-migration), `i18n/`.
- **Dateinamen** nur `[a-z0-9_]`; Ordner 755, Dateien 644.
  - Modelle: **eine Datei je Hauptmodell**, benannt nach dem Modell (`models/plant_order.py`); jedes geerbte Modell in
    eigener Datei (`models/res_partner.py`).
  - Views: `views/<model>_views.xml`, Menüs optional `views/<module>_menus.xml`, Portal/QWeb `<model>_templates.xml`.
  - Security: `security/ir.model.access.csv`, Gruppen `security/<module>_groups.xml`, Regeln `security/<model>_security.xml`.
  - Daten: `data/<model>_data.xml`, Demo `data/<model>_demo.xml` (OCA: eigener Ordner `demo/`).
  - Controller: `controllers/<module>.py` (Odoo; `main.py` gilt als veraltet – OCA nennt noch `main.py`).
  - Wizard: `wizard/<transient>.py` + `<transient>_views.xml`.
  - Statisches: `static/src/js|scss|xml|img`, Bibliotheken `static/lib/<name>/`, Tests `static/tests/`; eine Komponente
    je Datei. Keine externen URLs auf Bilder/Bibliotheken – ins Modul kopieren.
- **Hooks** (`pre_init_hook`, `post_init_hook`, `uninstall_hook`, `post_load`) in `hooks.py`, im `__init__.py`
  importiert (OCA 5).
- `__init__.py` in jedem Modul (Odoo 4, `test_dunderinit`).

## 2. Manifest (`__manifest__.py`)

- Nur erlaubte Schlüssel (Odoo 4, `test_manifests`): Pflicht `name`, `author`, `license`; übliche optionale
  (`version`, `summary`, `description`, `category`, `depends`, `data`, `demo`, `assets`, `external_dependencies`,
  `installable`, `application`, `auto_install`, `post_load`, Hooks, `countries`, `images`, `icon` …), informativ
  `contributors`, `maintainer`, `url`, App-Store-Schlüssel. Unbekannte Schlüssel = Fehler.
- **Keine Schlüssel auf ihren Standardwert setzen** (z. B. `application: False`, `auto_install: False`,
  `demo: []`) – Odoo 4 meldet das als Fehler; `icon` nicht auf den Standardpfad setzen.
- **Version** `19.0.x.y.z`: x = Datenmodell/Views mit Migrationsbedarf, y = neue Funktion abwärtskompatibel,
  z = Fehlerbehebung (OCA 5). Bei brechenden Änderungen Migrationsskript in `migrations/19.0.x.y.z/`.
- **Migrationsskripte** mit `odoo/upgrade-util` schreiben statt eigenem SQL (`from odoo.upgrade import util`: Felder/Modelle
  umbenennen oder entfernen, Datensätze verschieben, Domains anpassen, SQL-Helfer). Einbinden über
  `--upgrade-path=<upgrade-util>/src` oder `pip install git+https://github.com/odoo/upgrade-util@master`
  (im Image nicht enthalten). Dieselben Helfer nutzt Odoo für seine eigenen Versionssprünge.
- `license` und (OCA) `images` angeben, keine leeren Schlüssel. Externe Python-Pakete/Programme in
  `external_dependencies`.

## 3. Python

### Stil und Imports
- PEP8; Odoo ignoriert E501 (Zeilenlänge), E301, E302. OCA formatiert automatisch mit **black** (bzw. ruff), räumt
  mit **autoflake** auf (ungenutzte Imports/Variablen).
- **Import-Reihenfolge:** 1. Standardbibliothek/externe Bibliotheken, 2. `odoo`-Module, 3. `odoo.addons.*` (selten);
  innerhalb alphabetisch. Beispiel: `from odoo import Command, _, api, fields, models`, `from odoo.fields import Domain`.
- **Nicht** direkt aus `odoo.orm` importieren, sondern aus `odoo` (`api`, `fields`, `models`) – Odoo 4.
- Veraltete Module nicht benutzen: `csv`, `urllib`, `cgi`, Debugger-Module; kein `input()` – Odoo 4.
- **Englisch** für Namen und Kommentare (OCA 5); Texte für Nutzer über die Übersetzung.
- Bei umbrochenen Aufrufen/Listen: am öffnenden Zeichen umbrechen, **Komma nach dem letzten Element** (OCA 5).

### Idiome
- Lesbarkeit vor Kürze; sprechende Namen; kleine Methoden mit **einer** Aufgabe ("Think extendable": Domains und
  Kriterien in eigene, überschreibbare Methoden auslagern).
- `dict(x)`/`list(x)` statt `.clone()`; Dicts direkt mit Werten anlegen; `dict.get('k')` statt `get('k', None)`;
  `if collection:` statt `if len(...)`; über Dicts direkt iterieren; `setdefault`; Comprehensions.
- Recordset-Methoden: `filtered`, `mapped`, `sorted`, `grouped`.
- Keine eigenen Generatoren/Dekoratoren, nur die der Odoo-API.
- Docstrings für Methoden, Kommentare nur für knifflige Stellen.

### Kommentare und Docstrings

**Odoo/OCA-Regeln:**
- Englisch (für dieses Repo entschieden 2026-09-26).
- **Docstring** an Methoden: erklärt den **Zweck** (OCA). Werden Parameter dokumentiert (`:param x:`, `:return:`,
  reStructuredText wie im Odoo-Kern), müssen sie zur Signatur passen – Odoo 4 prüft das (`test_docstring`).
- **Kommentare nur für knifflige Stellen** (Odoo); viele Kommentare sind meist ein Zeichen für unklaren Code (OCA) –
  dann umbenennen oder aufteilen statt kommentieren. Sprechende Namen statt erklärender Kommentare.
- **Pflicht-Kommentare:** jedes `cr.commit()` (warum nötig und korrekt, Odoo 1); jedes `position="replace"` in Views
  (warum unvermeidbar, OCA).

**Hausregeln dieses Repos** (ergänzend, Entscheidung 2026-09-26):
1. **Warum statt Was:** der Kommentar nennt den Grund, nicht was der Code ohnehin sagt
   (schlecht: `# increase counter`; gut: `# Blob must be on disk before its row is committed (I3/I4); a crash leaves
   only an orphan the GC removes.`).
2. **Grundregeln benennen:** wo Code eine Invariante absichert, steht ihr Kürzel dabei (`I1` … `I12`, Konzept
   int_filemanager 2, Abschnitt 2) – damit bei Änderungen sichtbar ist, was nicht brechen darf.
3. **Odoo-Stellen per Funktionsname, nicht per Zeilennummer** (`# odoo.http.Stream.get_response only uses X-Accel
   below data_dir/filestore`, nicht `# see http.py:665`) – Zeilennummern verschieben sich mit jedem Update.
4. **Kein auskommentierter Code, keine Autor-/Datumszeilen** (steht in Git); `TODO` nur mit Begründung.
5. **Begründung einer Änderung in die Commit-Nachricht** (Odoo 2: das *Warum*); der Kommentar erklärt, warum der Code
   *jetzt* so ist.
6. **Dichte wie im umgebenden Code**; keine Kommentarwände, bei Odoo-typischem Code (Felder, Views) meist keine.
7. Prototypen unter `docs/prototypes/` bleiben unverändert (Belege, kein Modul-Code).

Beispiel:

```python
def begin_write(self, *, content_type=None):
    """Start receiving the request body into a temporary blob file."""
    # Commit on our own cursor before streaming so no transaction stays open for the whole
    # upload (would hold the snapshot and block VACUUM); nothing has been written yet.
    self.env.cr.commit()
```

### Odoo-spezifisch
- **Kontext** nur über `with_context(...)`; eigene Kontextschlüssel mit Modulpräfix (Vorbild `mail_notrack`);
  Vorsicht mit `default_*`-Schlüsseln (wirken auf alle erzeugten Datensätze).
- **Nie `cr.commit()`/`cr.rollback()`** – außer im **selbst geöffneten** Cursor; dann mit **ausdrücklichem Kommentar**,
  warum nötig und korrekt (Odoo 1). Odoo stellt je Request, Test und Cron die Transaktion. (Pylint-OCA: `invalid-commit`.)
- **Ausnahmen:** nur konkrete Typen fangen, kleiner `try`-Block; Framework-Fehler nur mit `with self.env.cr.savepoint():`
  abfangen (≤ 64 Savepoints je Transaktion, in Schleifen Batches). Kein `except: pass` (OCA `except-pass`).
  Fehlermeldungen für Nutzer: `UserError`/`ValidationError`/`AccessError` aus `odoo.exceptions`.
- **Übersetzung:** `self.env._('Literal %s', wert)` – nur feste Zeichenketten, Formatierung **als Argument**, nie
  vorher (`_('… %s' % x)` ist falsch); mehrere Platzhalter benannt `%(name)s`; `%` statt `.format()`; keine
  f-Strings (Odoo 4 `gettext-*`, OCA `translation-*`). Feldwerte nicht über `_()` übersetzen (`translate=True` am Feld).
- **`unlink()` überschreiben:** kein `raise` darin – Prüfungen mit `@api.ondelete(at_uninstall=False)` (Odoo 4
  `raise-unlink-override`).
- Öffentliche Methoden: keine Parameter namens `ids` oder `context` (Odoo 4 `test_naming`).
- Überschreibungen behalten die **Signatur** der Elternmethode (Odoo 4 `test_override_signatures`), rufen `super()` auf
  (OCA `method-required-super`).
- Many2one, die Gegenstück eines One2many sind: **Index** (`index=True`, Odoo 4 `test_index`).
- Keine Domains aus `@api.onchange` zurückgeben (veraltet, Odoo 4).
- Kein `print` (OCA), `logging` über `_logger = logging.getLogger(__name__)`.
- Externe HTTP-Aufrufe immer mit `timeout` (OCA `external-request-timeout`).
- Kein Schreiben in Compute-Methoden (OCA `no-write-in-compute`); kein `search([])` über alles ohne Grund
  (`no-search-all`).

### Namen (Symbole)
- **Modellnamen:** Punkt-Schreibweise, **mit Modulpräfix**, **Einzahl** (`sale.order`, nicht `sale.orders`).
  Transient: `<basismodell>.<aktion>` ohne "wizard" (`account.invoice.make`). SQL-Report: `<basis>.report.<aktion>`.
- **Klassen** PascalCase (`class AccountInvoice(models.Model)`).
- **Variablen** snake_case; Modell-Variablen PascalCase (`Partner = self.env['res.partner']`); `_id`/`_ids` **nur**
  für IDs, nicht für Datensätze. Konstanten GROSS.
- **Felder:** Many2one `…_id`, One2many/Many2many `…_ids`. Kein `string=`, wenn er dem Feldnamen entspricht (OCA).
  Standardwerte als `lambda self: self._default_x()`, damit vererbbar (OCA).
- **Methoden:** `_compute_<feld>`, `_inverse_<feld>`, `_search_<feld>`, `_default_<feld>`, `_selection_<feld>`,
  `_onchange_<feld>`, `_check_<bedingung>`, Aktionen `action_<…>` (mit `self.ensure_one()` bei Einzeldatensatz).
- **Reihenfolge im Modell:** private Attribute (`_name`, `_description`, `_inherit`, …) → Default-Methoden →
  Felder → SQL-Constraints/Indizes → Compute/Inverse/Search (in Feldreihenfolge) → Selection-Methoden →
  `@api.constrains`/`@api.onchange` → CRUD-Überschreibungen → Aktionen → übrige Geschäftsmethoden.

## 4. Sicherheit (Odoo 3, verbindlich)

- **Öffentliche Methoden sind per RPC mit beliebigen Argumenten aufrufbar.** Datensatz und Parameter nicht vertrauen;
  Zugriffsrechte greifen nur bei CRUD. Heikles in private Methoden (`_…`) auslagern – privat allein reicht nicht,
  Rechte bewusst prüfen. `sudo()` nie auf nutzergesteuerte Eingaben.
- **ORM nicht umgehen:** kein direktes SQL, wenn das ORM es kann (sonst fehlen Übersetzung, Cache-Invalidierung,
  `active`, Rechte). Wo SQL nötig ist: **`odoo.tools.SQL`** mit Parametern, nie `+`/`%` in den SQL-Text (Odoo 4
  `sql-injection`).
- **Domains** nicht als Listen zusammenkleben; `odoo.fields.Domain` benutzen (`domain &= Domain(...)`), sonst können
  Nutzer Bedingungen einschleusen.
- **Kein `t-raw`**/ungeprüftes HTML; `t-esc`/`t-out`; HTML in Python nur mit `markupsafe.Markup` und Formatierung
  **nach** dem Literal (`Markup('<p>%s</p>') % wert`), keine f-Strings in `Markup`. Escapen statt Säubern, wo möglich.
- **Kein `eval`**; `safe_eval` nur für vertrauenswürdige, privilegierte Eingaben; zum Einlesen `ast.literal_eval`,
  `json.loads`, `int()` usw.

## 5. XML

- `<record>`: `id` vor `model`; bei `<field>` zuerst `name`, dann Wert/`eval`, dann weitere Attribute. Nach Modell
  gruppieren. 4 Leerzeichen Einrückung (OCA).
- `<data>` nur für gemischte `noupdate`-Blöcke; sonst `<odoo>` bzw. `<odoo noupdate="1">`.
- `<menuitem>` und `<template>` statt `<record>` für Menüs/QWeb.
- **XML-IDs:** Menü `<model>_menu[_<zweck>]`; View `<model>_view_<typ>`; Aktion `<model>_action[_<detail>]`, Fenster
  `…_action_view_<typ>`; Gruppe `<module>_group_<name>`; Regel `<model>_rule_<gruppe>`; Demo-Datensätze mit Suffix
  `demo` (OCA). **Kein** Modulpräfix in der eigenen ID (OCA). View-`name` = XML-ID mit Punkten.
- **Geerbte Views:** gleiche ID wie das Original, `name` mit `.inherit.<modul>`; neue Primär-Views ohne Suffix.
  `position="replace"` vermeiden (OCA; wenn doch: Kommentar + hohe `priority`); ein Modul erweitert eine View nur einmal.
- Keine veralteten Attribute/Knoten (OCA `xml-deprecated-*`); `ir.filters` mit ausdrücklichem `user_id`.

## 6. JavaScript, CSS/SCSS

- Struktur `static/src/js|scss|xml`, `static/lib/`, `static/tests/` (Tours unter `static/tests/tours`).
- ESLint (Odoo 4 prüft alle JS-Dateien), prettier (OCA); keine minifizierten Bibliotheken; Klassen PascalCase.
- **CSS-Klassen** mit Präfix `o_<modul>` (Webclient: `o_`), keine ID-Selektoren, Bootstrap-Klassen nutzen,
  verschachtelte Elemente nach dem "Enkel"-Prinzip (`o_element_entry`, nicht `o_element_wrapper_entries_entry`).
- **SCSS-Format:** 4 Leerzeichen, max. 80 Zeichen, `{` nach Leerzeichen, `}` in eigener Zeile, eine Deklaration je
  Zeile. Eigenschaften "von außen nach innen" (Position → Box → Rahmen → Hintergrund → Schrift → Effekte), lokale
  Variablen zuoberst.
- **Variablen:** SCSS global `$o-[root]-[element]-[eigenschaft]-[modifier]`, SCSS lokal `$-[name]`, Mixins/Funktionen
  `o-[name]` (Funktionen mit Verb), CSS-Variablen BEM `--[Root]__[element]-[eigenschaft]--[modifier]` und nur für
  DOM-bezogene Anpassungen.
- JS-Übersetzungen: keine Template-Strings mit Ausdrücken in `_t(...)` (Odoo 4 `test_jstranslate`).

## 7. Tests

- Jede Fehlerbehebung mit einem Test, der ohne die Behebung fehlschlägt; neue Funktionen möglichst vollständig testen
  (OCA 5).
- **Mit möglichst geringen Rechten testen** (`new_test_user`, `@users`, `uid`/`env` in `setUpClass`) – sonst
  falsch-positive Tests.
- Flaky Tests vermeiden: `subTest` setzt DB und Cache **nicht** zurück; in Klassenvariablen gespeicherte Datensätze
  tragen altes `env` (Nutzer, sudo, Kontext) mit; feste Daten statt `now()` (`freezegun`); externe Dienste mocken
  (`unittest.mock`, `classPatch`).
- Testdateien müssen in `tests/__init__.py` importiert sein (Odoo 4 `test_test_holes`).

## 8. Git

- **Odoo 2:** Kopfzeile `[TAG] modul: kurzer Satz` (≈ 50 Zeichen), ergänzt "Wenn angewendet, wird dieser Commit …".
  Tags: `[FIX]` `[REF]` `[ADD]` `[REM]` `[REV]` `[MOV]` `[REL]` `[IMP]` `[MERGE]` `[CLA]` `[I18N]` `[PERF]` `[CLN]`
  `[LINT]`; OCA zusätzlich `[MIG]`.
- Text: vor allem **warum**, das Was steht im Diff; technische Entscheidungen begründen; Verweise (`Fixes #123`).
- Möglichst **ein Modul je Commit**; ein Commit je logischer Änderung (keine "fix pep8"-Nachträge, OCA).
- Englisch, Imperativ ("Fix …", nicht "Fixes …"), Zeilen ≤ 80 Zeichen (OCA).
- `user.name`/`user.email` gesetzt.
- Hinweis: Die OCA-Richtlinie sagt zugleich "ohne Präfix" und "Tags wie bei Odoo" – in der Praxis nutzt die OCA
  `[TAG] modul: …`.

## 9. Was maschinell geprüft wird

**Odoo `test_lint`** (Odoo 4, läuft beim Testen mit `--test-tags /test_lint` auch über unsere Module):
Pylint mit `used-before-assignment`, `undefined-variable`, `eval-used`, `unreachable`, `function-redefined`,
`sql-injection`, `missing-gettext`, `gettext-variable`, `gettext-placeholders`, `gettext-repr`,
`raise-unlink-override`, verbotene Funktion `input`, veraltete Module `csv`/`urllib`/`cgi`; dazu Tests für Manifest,
`__init__.py`, Docstring ↔ Signatur, ESLint, JS-Übersetzungen, Index auf One2many-Gegenstücken, Merge-Konfliktmarker,
Parameternamen `ids`/`context`, keine Onchange-Domains, kein Import aus `odoo.orm`, Überschreibungs-Signaturen,
doppelte `.pot`-Einträge, Routen-Vererbung, nicht importierte Testdateien.

**odoo-ls, Parse-Modus** (Odoo 7): `odoo_ls_server --parse -c <Odoo-Pfad> -a <Addon-Pfad> -t <Addon-Pfad>
--python <python> --stdlib <typeshed>/stdlib -s <typeshed>/stubs -o out.json` schreibt alle Befunde als JSON.
Findet, was pylint nicht sehen kann, weil es die Odoo-Registry kennt: unbekanntes Modell, Modell nicht in `depends`,
Feld existiert nicht, ungültiges Domain-Feld, Methode existiert nicht, Compute-Methode setzt das Feld nicht,
Related-Feld mit falschem Typ, falsche Aufrufargumente; dazu ESLint (oxc) für JS.
*Probelauf 2026-09-26 auf Tower* (Wegwerf-Container aus `odoo:19.0-hm`, `--network none`, nur lesend eingebunden:
`fm_proto` und die Live-Addons): ~30 s. Echte Funde: 7 × `documents.document` in `onlyoffice_odoo` ohne
`documents` in `depends` (Enterprise-Modell), ESLint-Hinweise in `onlyoffice_odoo`, 4 × doppelte Basisklasse im
Prototyp durch `try: import wsgidav … except ImportError: … = object` (sauber: `external_dependencies` im
Manifest statt Ersatzklasse). Fallstricke: (1) `typeshed.zip` aus dem Release gehört dazu, sonst bricht der Lauf
ab; (2) Bibliotheken außerhalb des Images (z. B. `wsgidav` in `/mnt/pylib`) per `PYTHONPATH` sichtbar machen, sonst
Fehlalarme; (3) die Ausgabe enthält auch ~1.800 Befunde aus dem Odoo-Core → nach eigenen Pfaden filtern;
(4) Hinweise mit Stufe 3 (z. B. `OLS03024`, Klassen in Testfunktionen) sind Information, kein Fehler.
Das Programm beendet sich unabhängig von den Befunden normal, deshalb wertet ein kleines Skript das JSON aus und
scheitert bei Fehlern/Warnungen in eigenen Pfaden.

**OCA pre-commit** (Vorlage, Odoo ≥ 18): `whool`, `oca-gen-addon-readme` (README aus `readme/`-Bausteinen, Markdown),
`oca-fix-manifest-website`, `oca-gen-external-dependencies`, `oca-checks-odoo-module` (mit `--fix`), `oca-checks-po`,
`autoflake`, `black` (bzw. ruff), `prettier`, `eslint`, `trailing-whitespace`, `end-of-file-fixer`,
`debug-statements`; **pylint-odoo Pflichtprüfungen** u. a.: `invalid-commit`, `except-pass`, `print-used`,
`sql-injection`, `eval-used`, `method-required-super`, `method-compute/inverse/search` (Namensmuster),
`manifest-required-author/-key`, `manifest-version-format`, `license-allowed`, `missing-readme`,
`no-write-in-compute`, `no-search-all`, `no-raise-unlink`, `prohibited-method-override`, `translation-*`
(f-String, Positionsplatzhalter, Injection …), `external-request-timeout`, `context-overridden`,
`dangerous-view-replace-wo-priority`, `duplicate-xml-record-id`, `xml-deprecated-*`, `attribute-string-redundant`,
`no-wizard-in-models`, `deprecated-name-get`, `deprecated-self-cr`, `prefer-env-translation`.

---

## 10. Abgleich mit diesem Repo und int_filemanager 2

| Punkt | Stand | Folge |
|---|---|---|
| Modellnamen mit Modulpräfix | heutiges Modul: `int_filemanager.*` – eingehalten. Konzept v2 hatte `fm.*` | **erledigt 2026-09-26:** im Konzept (1–18) und Kern auf `int_filemanager.node`, `.revision`, `.blob`, `.scope`, `.upload`, `.operation`, `.dav_lock`, `.dav_prop` umgestellt |
| Englisch in Code und Kommentaren | Prototypen und Teile des heutigen Moduls deutsch (16 Python-Dateien mit deutschen Kommentaren/Docstrings) | **entschieden 2026-09-26:** vollständig nach Konvention – Code, Kommentare, Docstrings, Log-Meldungen, Commits englisch; Oberflächentexte englisch im Code + `i18n/de.po` |
| `cr.commit()` | heutiges Modul: 6 Stellen | in v2 nur im selbst geöffneten Cursor (`odoo fmdav`, Crons mit eigenem Cursor) und mit Kommentar |
| `sudo()` | heutiges Modul: 59 Stellen (N1-Lücke) | v2: I7 – nie auf Nutzereingaben; jede Stelle begründet |
| Rohes SQL | heutiges Modul: 13 × `cr.execute`; Prototyp: Pfadauflösung per rekursiver CTE | v2: nur wo das ORM nicht reicht, mit `odoo.tools.SQL`, Rechteprüfung über das ORM danach |
| Hooks | Prototyp `post_load` in `__init__.py` | in `hooks.py` (OCA) |
| Lint/pre-commit | im Repo **keine** Konfiguration | **entschieden 2026-09-26:** pre-commit nach OCA-Vorlage (nur neuer Code) + Odoos `test_lint` + **odoo-ls Parse-Modus** (nur eigene Pfade) auf der Testinstanz; keine GitHub Action |
| Migrationsskripte | im heutigen Modul keine `migrations/` | **entschieden 2026-09-26:** ab dem ersten Datenmodell-Wechsel nach Inbetriebnahme mit `odoo/upgrade-util` |
| Commit-Nachrichten | bisher `docs: …`, `CLAUDE.md: …` | für Modul-Code `[TAG] modul: …` (Odoo 2) |
| Manifest | `19.0.1.15.0`, `LGPL-3` – Format passt | keine Schlüssel mit Standardwert; `hooks`/`external_dependencies` (z. B. `wsgidav`) angeben, kein `except ImportError`-Ersatz |

---

## 11. Abgleich mit dem Stand 2026-10-02 (Coding und Git Guidelines)

Geprüft gegen `odoo/documentation`, Branch 19.0, Commit `eee2e56` (2026-10-02),
`content/contributing/development/coding_guidelines.rst` und `git_guidelines.rst`. Die Abschnitte 1–10 bleiben
inhaltlich gültig; **Ergänzungen**, die dort fehlten:

- **Cron-Fehlerbehandlung (Python):** Fängt eine geplante Aktion Fehler und soll weiterlaufen, **rollback** machen;
  Crons laufen in eigener Transaktion, Fortschritt wird über `IrCron._commit_progress` gemeldet
  (`docs/odoo_regeln_actions_cron_http_reports_2026-10-02.md` Abschnitt 2). Das ersetzt `cr.commit()` im Cron-Code.
- **Commit mit `cr.commit()`:** Ausnahmen laut Guidelines nur im **selbst geöffneten** Cursor; **kein** `commit()` nötig in
  `_auto_init`, Reports und `TransientModel`-Methoden (laufen im Framework-Transaktionskontext).
- **Frontend-Ordner:** zusätzlich `static/src/js/tours/` (Onboarding-Tours für Endnutzer) neben
  `static/tests/tours/` (Test-Tours); `static/src/css`, `static/fonts`, `static/img`.
- **JS:** `use strict` ist empfohlen (native Module sind es ohnehin), Linter nutzen, nie minifizierte Bibliotheken.
- **SCSS/CSS-Variablen:** CSS-Variablen sind **ausschließlich DOM-bezogen** (kontextuelle Anpassung, Standardwert
  im Komponentenblock); das Design-System steckt in SCSS-Variablen, kombiniert über
  `color: var(--MyComponent-color, #{$o-component-color})`. **Keine CSS-Variablen auf `:root`** (Ausnahme: Templates,
  die über Bundles geteilt werden). Details: `docs/odoo_regeln_ui_icons_scss_2026-10-02.md`.
- **Übersetzung:** `_('…') % wert` (Formatierung außerhalb) ist ebenfalls falsch, nicht nur `_('…' % wert)`; bei einer
  Variablen `%`, bei mehreren `%(name)s`.
- **Git:** `[MOV]` nur mit `git mv` und **ohne Inhaltsänderung** (sonst geht die Historie verloren; gilt auch beim
  Verschieben von Code zwischen Dateien); Kopfzeile muss mit "if applied, this commit will …" einen gültigen Satz
  ergeben, nie Einzelwörter wie "bugfix"/"improvements"; mehrere Module: auflisten oder `various`; Referenzen am Ende
  im Format `Fixes #123`, `Closes #123`, `task-123`, `opw-123`.
- **Stabile Branches vs. Entwicklung:** an bestehenden Dateien Stil nicht umformatieren; bei großem Umbau erst
  reinen Verschiebe-Commit, dann die Änderung (bereits in "Quellen und Rangfolge" festgehalten).

Alle Regeln der **Developer Reference** (ORM, Views, JS, Tests …) stehen in den Destillaten
`docs/odoo_regeln_*_2026-10-02.md`, Einstieg über `docs/odoo_regeln_index_2026-10-02.md`.
