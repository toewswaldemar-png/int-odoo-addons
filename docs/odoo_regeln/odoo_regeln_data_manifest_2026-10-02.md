# Odoo 19 Regeln: Datendateien und Manifest (Destillat)

Quellen (nur offiziell, bei Widerspruch gilt der Code vor der Doku): Odoo-19.0-Quellcode (`odoo/modules/module.py`,
`odoo/tools/convert.py`, `odoo/addons/test_lint/tests/test_manifests.py`) und `odoo/documentation`, Branch 19.0,
`content/developer/reference/backend/data.rst` und `backend/module.rst`
(Web: <https://www.odoo.com/documentation/19.0/developer/reference/backend/data.html>,
<…/backend/module.html>). Geprüft: 2026-10-02. Ergänzt `odoo_regeln_coding_guidelines_2026-10-02.md` Abschnitte 1, 2 und 5.
Index: `docs/odoo_regeln/odoo_regeln_index_2026-10-02.md`.

## 1. Manifest (`__manifest__.py`)

Ein einziges Python-Dict. Schlüssel laut Referenz:

| Schlüssel | Typ / Standard | Regel |
|---|---|---|
| `name` | str, **Pflicht** | Anzeigename |
| `version` | str, Standard `1.0` | 2 bis 5 Zahlenteile; bei höchstens 3 Teilen setzt Odoo `19.0.` davor; beginnt sie mit einer anderen Serie, ist das Modul nicht installierbar (`adapt_version`/`check_version` in `odoo/modules/module.py`) |
| `summary` | str | Kurzbeschreibung |
| `description` | str, Standard README | reStructuredText |
| `author`, `website`, `maintainer` | str | Maintainer ist standardmäßig der Autor |
| `license` | str, Standard `LGPL-3` (fehlt der Schlüssel, warnt Odoo) | `GPL-2`, `GPL-2 or any later version`, `GPL-3`, `GPL-3 or any later version`, `AGPL-3`, `LGPL-3`, `Other OSI approved licence`, `OEEL-1`, `OPL-1`, `Other proprietary` |
| `category` | str, Standard `Uncategorized` | bestehende Kategorien bevorzugen; unbekannte werden angelegt; Hierarchie mit `/` (`Foo / Bar`) |
| `depends` | list | Module, die zuerst geladen sein müssen (Funktionen nutzen **oder** Ressourcen ändern). `base` ist immer installiert, soll laut Referenz aber trotzdem genannt werden, damit das Modul bei einem `base`-Update mitaktualisiert wird; eine leere Liste wird im Core (`Manifest` in `odoo/modules/module.py`) zu `['base']` |
| `data` | list | immer geladene Dateien, Pfade ab Modulwurzel |
| `demo` | list | nur im Demo-Modus |
| `auto_install` | bool oder list, Standard `False` | für "Verbindungsmodule" (`sale_crm`); Liste = Teilmenge der `depends`, leere Liste = immer installieren |
| `external_dependencies` | dict | `{'python': [...], 'bin': [...]}`; Modul installiert nicht, wenn etwas fehlt |
| `application` | bool, Standard `False` | vollwertige App vs. technisches Modul |
| `assets` | dict | Bundles (siehe Frontend-Assets-Destillat) |
| `installable` | bool, Standard `True` | darf gesetzt werden, muss nicht |
| `{pre_init, post_init, uninstall}_hook` | str | Funktionsname in `__init__.py`, Argument ist `env`; **nur nutzen, wenn Setup/Aufräumen über die API extrem schwierig oder unmöglich ist** |
| `sequence` | int, Standard 100 | Reihenfolge in der Apps-Liste |
| `post_load` | str | Funktionsname in `__init__.py`, ohne Argumente; läuft direkt nach dem Import des Moduls |
| `countries`, `images`, `cloc_exclude` | list | Länderbezug (bei einem Land `l10n` im Modulnamen), Bilder, von `cloc` ausgenommene Pfade |
| `active` | — | **veraltet** → `auto_install` |

Prüfung durch Odoo (`test_manifests` in `odoo/addons/test_lint/tests/test_manifests.py`): unbekannte Schlüssel schlagen fehl;
für `application`, `auto_install`, `summary`, `description`, `author`, `demo`, `data` und `test` darf der Wert nicht dem Standardwert
entsprechen (Schlüssel dann weglassen); ein Modul mit genau einem Land in `countries` soll `l10n` im Namen tragen (Warnung).
Hooks nur nutzen, wenn Setup/Aufräumen über die API extrem schwierig oder unmöglich ist (Referenz).

## 2. XML-Datendateien

- Wurzel `<odoo>`, darin beliebig viele Operationen. **Dateien laufen sequentiell**; eine Operation kann nur auf
  Ergebnisse **vorheriger** Operationen verweisen (Reihenfolge in `data` beachten).
- **`noupdate`:** `<odoo noupdate="1">` oder Block `<data noupdate="1">` = nur bei Installation (`-i`) geladen;
  ohne = bei Installation und Update (`-i`/`-u`) neu geladen.
- **`<function>` in `noupdate`:** wird bei Updates übersprungen und läuft nur bei Installation (`_tag_function` in `odoo/tools/convert.py`).

### `<record>`
- `model` (Pflicht), `id` (externe ID, **dringend empfohlen**: bei Erstellung für spätere Bezüge, bei
  Änderung der Zieldatensatz), `context`, `forcecreate` (Update-Modus: anlegen, wenn nicht vorhanden; braucht
  externe ID; Standard `True`).
- Ein `<record>` ohne `<field>` nimmt alle Defaults (Neuanlage) oder tut nichts (Update).

### `<field>` (Wertangabe)
- Ohne Wert → implizit `False` (leeren oder Default vermeiden).
- `search` (Domain; nimmt bei Many2one nur den ersten Treffer), `ref` (externe ID; Many2one/Reference),
  `type` (`xml`/`html` mit `%(external_id)s` und `%%`, `file`, `char`, `base64` mit `file`-Attribut, `int`, `float`,
  `list`/`tuple` mit `<value>`), `eval` (beliebiger Python-Ausdruck; Kontext `time`, `datetime`, `timedelta`,
  `relativedelta`, `ref`, `obj`; der Core, `_get_eval_context` in `odoo/tools/convert.py`, liefert zusätzlich `Command`, `DateTime`, `version`, `pytz`).
- `eval` nur, wenn die anderen Formen nicht passen.

### `<delete>`, `<function>`
- `<delete model= id=|search=>` (die Referenz nennt `id` und `search` exklusiv; `_tag_delete` im Core verarbeitet beide gemeinsam).
- `<function model= name=>` ruft eine Methode auf (Parameter per `eval` oder `<value>`); Namen mit `__` und unsichere Attribute
  werden im Core abgelehnt (`_eval_xml` in `odoo/tools/convert.py`).

### Kurzformen
- **`<menuitem>`:** `sequence`, `active`, `web_icon`, `parent` (externe ID; ohne: Top-Level-Menü; verschachtelte `<menuitem>` erben die Eltern-ID. Die Referenz beschreibt außerdem
  `name` als `/`-getrennten Pfad mit automatisch angelegten Zwischenmenüs – das macht `_tag_menuitem` im Core (`odoo/tools/convert.py`)
  nicht: `name` bleibt unzerlegt), `name` (ohne: Name der verknüpften Aktion, sonst `id`), `groups` (kommagetrennte externe IDs;
  `-` davor entfernt die Gruppe), `action`, `id`. Für Menüs `<menuitem>` statt `<record>`.
- **`<template>`:** QWeb-View, nur `arch` nötig; optional `id`, `name`, `key`, `inherit_id` (externe ID), `priority`,
  `primary`, `groups`, `active`, `customize_show`. **`active` am Knoten wirkt nur bei der Erstellung**, nicht bei späteren Updates.
- **`<asset>`:** `id`, `name`, `active` (gleiche Einschränkung wie bei `<template>`), Kinder `<bundle>`
  (Attribut `directive`) und `<path>`, optional `<field>`.

## 3. CSV-Datendateien

- Für viele einfache Datensätze eines Modells (typisch: Zugriffsrechte).
- Dateiname **`<modellname>.csv`**; erste Zeile = Felder, Sonderfeld `id` = externe ID; jede weitere Zeile ein
  Datensatz. Beispiel: `security/ir.model.access.csv`. Referenzierte Datensätze (z. B. Land) müssen vorher
  definiert sein.
