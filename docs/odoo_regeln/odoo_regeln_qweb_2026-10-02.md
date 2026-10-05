# Odoo 19 Regeln: QWeb-Templates (Destillat)

Quelle: `odoo/documentation`, Branch 19.0, Commit `eee2e56` (2026-10-02),
`content/developer/reference/frontend/qweb.rst`
(Web: <https://www.odoo.com/documentation/19.0/developer/reference/frontend/qweb.html>).
Geprüft: 2026-10-02. QWeb-Berichte: `docs/odoo_regeln/odoo_regeln_actions_cron_http_reports_2026-10-02.md` Abschnitt 4.
Index: `docs/odoo_regeln/odoo_regeln_index_2026-10-02.md`.

**Vorsicht, Quelle teils veraltet:** der Abschnitt "Javascript" (`QWeb2.Engine`, `core.qweb`, `t-extend`/`t-jquery`,
`t-js`) beschreibt das alte System; die Quelle selbst markiert ihn mit "no longer relevant, section to rewrite".
Für neue Owl-Templates gilt Owl-Syntax (siehe `docs/odoo_regeln/odoo_regeln_js_framework_2026-10-02.md` Abschnitt 7).

## 1. Direktiven (Python- und JS-QWeb)

- Direktiven sind XML-Attribute `t-…`; `<t>` ist der Platzhalter ohne eigene Ausgabe.
- **Ausgabe: `t-out`** escaped automatisch (XSS-Schutz). `t-esc` ist ein (noch nicht formal veralteter) Alias.
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
- Unterschied: Python-`Markup` escaped den anderen Operanden bei Verkettung, JS-`Markup` **nicht** (Verkettung
  liefert `String`, der andere Operand bleibt unescaped).
- Ausführlich: `docs/odoo_regeln/odoo_regeln_security_2026-10-02.md` (Escaping vs. Sanitizing, `Markup`-Muster).

## 3. Nur Python-QWeb

- **`t-field`** nur bei Feldzugriff `a.b` auf "smarte" Datensätze (Ergebnis von `browse`); formatiert nach Feldtyp,
  integriert in den Website-Editor; Optionen über `t-options` (häufig `widget`).
- **`t-debug=""`** ruft `breakpoint()` auf (Debugger).
- **Rendern aus Controllern:** `request.render('template', {…})` → `Response`. Direkt: `ir.qweb._render(id,
  values)` (mit DB) bzw. Modulmethode `render` (ohne DB). Standardkontext von `_prepare_environment`:
  `request`, `debug`, `quote_plus`, `json`, `time`, `datetime`, `relativedelta`, `keep_query`
  (`minimal_qcontext=False` vermeidet die Defaults).
- Template-Vererbung für Backend-/Website-Templates läuft über `<template inherit_id=…>` und XPath
  (siehe Views-Destillat Abschnitt "QWeb-Views"); für JS/Owl-Templates über `t-inherit`.

## 4. JavaScript-Templates (Owl)

- **`t-name`** nur auf oberster Ebene einer Template-Datei (`<templates><t t-name="addon.Name">…</t></templates>`);
  bei `<t>`-Träger genau **ein** Kind. Namen punktgetrennt hierarchisch.
- **Vererbung:** `t-inherit="basis"` + `t-inherit-mode="primary"` (neues Kind-Template mit `t-name`) oder
  `"extension"` (in-place); Änderungen per **XPath** (`<xpath expr=… position="inside|after|before|replace|
  attributes|move">`).
- **Veraltet:** `t-extend` + `t-jquery` + `t-operation` (jQuery-Selektor; ohne `t-operation` wird JS ausgeführt –
  "schwer zu debuggen und zu warten, vermeiden").
- Debug: `t-log`, `t-debug` (Haltepunkt); `t-js` gehört zum alten System.
- Props mit Anzeigetext tragen den Suffix `.translate` (`<Dialog title.translate="Text"/>`), sonst werden sie nicht übersetzt.
- Namenskonvention Templates: **`addon_name.ComponentName`**.
