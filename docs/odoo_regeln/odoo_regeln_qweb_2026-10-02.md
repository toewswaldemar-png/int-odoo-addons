# Odoo 19 Regeln: QWeb-Templates (Destillat)

Quellen (Rangfolge: Odoo-19-Code vor Doku): Odoo-19-Core (`odoo/addons/base/models/ir_qweb.py` mit Docstring zu den
Direktiven, `odoo/addons/base/models/ir_ui_view.py`, `odoo/addons/base/models/assetsbundle.py`) und
Odoo-19-Entwicklerdoku (`odoo/documentation`, Branch 19.0, `content/developer/reference/frontend/qweb.rst`).
Wo Core und Doku abweichen, gilt der Core.
(Web: <https://www.odoo.com/documentation/19.0/developer/reference/frontend/qweb.html>).
Geprüft: 2026-10-02, Core-Abgleich 2026-10-08. QWeb-Berichte: `docs/odoo_regeln/odoo_regeln_actions_cron_http_reports_2026-10-02.md` Abschnitt 4.
Index: `docs/odoo_regeln/odoo_regeln_index_2026-10-02.md`.

**Vorsicht, Doku teils veraltet:** der Doku-Abschnitt "Javascript" (`QWeb2.Engine`, `core.qweb`, `t-extend`/`t-jquery`,
`t-js`) beschreibt das alte System; `t-extend` kommt in den Templates unter `addons/*/static/src` nicht mehr vor.
Für neue Owl-Templates gilt Owl-Syntax (siehe `docs/odoo_regeln/odoo_regeln_js_framework_2026-10-02.md` Abschnitt 7).

## 1. Direktiven (Python- und JS-QWeb)

- Direktiven sind XML-Attribute `t-…`; `<t>` ist der Platzhalter ohne eigene Ausgabe.
- **Ausgabe: `t-out`** escaped automatisch (XSS-Schutz). `t-esc` ist veraltet (Core: Docstring in `ir_qweb.py`; `_compile_directive_esc` warnt im Dev-Modus; die Doku nennt
  es noch "nicht formal veraltet").
  **`t-raw` ist seit 15.0 veraltet** (emittiert nie escaped; schwer zu prüfen, ob Inhalt Markup sein darf) →
  `t-out` mit `markupsafe.Markup`-Wert.
- **Bedingungen:** `t-if`, `t-elif`, `t-else` (am Träger-Element, nicht nur `<t>`).
- **Schleifen:** `t-foreach="liste" t-as="i"`; iterierbar: Array (Wert) oder Mapping (Schlüssel);
  **Iteration über eine Ganzzahl ist veraltet**. Hilfsvariablen `i_value`, `i_index`, `i_size`, `i_first`, `i_last`;
  **veraltet:** `i_all` (nur JS), `i_parity`, `i_even`, `i_odd`. Variablen der Schleife gelten nur darin; existierte
  die Variable außerhalb, wird der Wert am Ende zurückkopiert.
- **Attribute:** `t-att-NAME="ausdruck"`, `t-attf-NAME="text {{ausdruck}}"` (Format-String; Alternativsyntax
  `#{…}`), `t-att="mapping"` oder `t-att="[name, wert]"`.
- **Variablen:** `t-set="x" t-value="ausdruck"` oder `t-set="x"` mit Körper (Körper = sicherer Inhalt).
- **Unterschablonen:** `t-call="name"` nutzt den Kontext des Aufrufers; Variablen, die im **Körper** des `t-call`
  gesetzt werden, sind nur lokal; der gerenderte Körper steht in der Vorlage als `0` (`<t t-out="0"/>`) bereit.

## 2. Ausgabe und Sicherheit ("safe content")

- Einzig plattformübergreifend "sicher": Ausgabe von `t-call` und `t-set` mit Körper.
- Python: sicher markiert (nicht erneut escaped) sind HTML-Felder, `html_escape`/`markupsafe.escape` (kein
  Doppel-Escaping), `html_sanitize`, `markupsafe.Markup`. **`Markup` ist eine Behauptung, die nicht geprüft wird** –
  mit Vorsicht benutzen. `to_text` strippt die Sicherheitsmarkierung nicht, setzt sie aber auch nicht.
- **Doppeltes Escapen erzwingen:** zurück in `str` wandeln (`str(inhalt)` in Python, `String(inhalt)` in JS).
- Unterschied (nur laut Doku, im Core nicht geprüft): Python-`Markup` escaped den anderen Operanden bei Verkettung, JS-`Markup` **nicht** (Verkettung
  liefert `String`, der andere Operand bleibt unescaped).
- Ausführlich: `docs/odoo_regeln/odoo_regeln_security_2026-10-02.md` (Escaping vs. Sanitizing, `Markup`-Muster).

## 3. Nur Python-QWeb

- **`t-field`** nur bei Feldzugriff `a.b` auf "smarte" Datensätze (Ergebnis von `browse`); formatiert nach Feldtyp,
  integriert in den Website-Editor; Optionen über `t-options` (häufig `widget`).
- **`t-debug=""`** ruft `breakpoint()` auf (Debugger); Werte wie `pdb` sind seit 17.0 veraltet (stattdessen
  `PYTHONBREAKPOINT`/`sys.setbreakpointhook`, Docstring in `ir_qweb.py`).
- **Weitere Python-Direktiven** (Docstring in `ir_qweb.py`): `t-groups` (Alias `groups`; Gruppennamen, `!` =
  ausgeschlossen), `t-valuef` bzw. `t-valuef.translate` (Format-String für `t-set`), `t-options`/`t-options-*`
  (am selben Knoten wie `t-out`, `t-field` oder `t-call`), `t-lang` (mit `t-call`, rendert in anderer Sprache),
  `t-call-assets` (Asset-Bundle). `t-out` zeigt bei falsy-Wert den Tag-Inhalt als Standardwert.
- **Rendern aus Controllern:** `request.render('template', {…})` → `Response`. Direkt: `ir.qweb._render(id,
  values)` (mit DB) bzw. Modulmethode `render` (ohne DB). Standardkontext von `_prepare_environment`
  (Core): `true`, `false`, `debug`, `user_id`, `res_company`, `request`, `test_mode_enabled`, `json`, `quote_plus`,
  `time`, `datetime`, `relativedelta`, `image_data_uri`, `floor`, `ceil`, `env`, `lang`, `keep_query`. Mit der
  Option `minimal_qcontext=True` (so ruft die Modulfunktion `render` auf) entfallen alle außer `true`/`false`;
  die Doku nennt fälschlich `minimal_qcontext=False`.
- Template-Vererbung für Backend-/Website-Templates läuft über `<template inherit_id=…>` und XPath
  (siehe Views-Destillat Abschnitt "QWeb-Views"); für JS/Owl-Templates über `t-inherit`.

## 4. JavaScript-Templates (Owl)

- **`t-name`** nur auf oberster Ebene einer Template-Datei (`<templates><t t-name="addon.Name">…</t></templates>`);
  bei `<t>`-Träger genau **ein** Kind. Namen punktgetrennt hierarchisch.
- **Vererbung:** `t-inherit="basis"` + `t-inherit-mode="primary"` (neues Kind-Template mit `t-name`; `primary` ist der Standard, wenn
  `t-inherit-mode` fehlt, `assetsbundle.py`) oder
  `"extension"` (in-place); Änderungen per **XPath** (`<xpath expr=… position="inside|after|before|replace|
  attributes|move">`).
- **Veraltet:** `t-extend` + `t-jquery` + `t-operation` (jQuery-Selektor; ohne `t-operation` wird JS ausgeführt –
  "schwer zu debuggen und zu warten, vermeiden").
- Debug: `t-log`, `t-debug` (Haltepunkt); `t-js` gehört zum alten System.
- Props mit Anzeigetext tragen den Suffix `.translate` (`<Dialog title.translate="Text"/>`), sonst werden sie nicht übersetzt.
- Namenskonvention Templates: **`addon_name.ComponentName`**.
