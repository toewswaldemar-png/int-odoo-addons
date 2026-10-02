# Odoo 19 Regeln: JavaScript-Framework (Destillat)

Quelle: `odoo/documentation`, Branch 19.0, Commit `eee2e56` (2026-10-02), Verzeichnis
`content/developer/reference/frontend/`: `framework_overview.rst`, `javascript_modules.rst`, `assets.rst`,
`registries.rst`, `services.rst`, `hooks.rst`, `patching_code.rst`, `javascript_reference.rst` (ohne Feld-Widgets,
siehe `docs/odoo_regeln_js_fields_2026-10-02.md`), `owl_components.rst`, `error_handling.rst`, `odoo_editor.rst`,
`mobile.rst`. Web-Wurzel: <https://www.odoo.com/documentation/19.0/developer/reference/frontend/>.
Geprüft: 2026-10-02. QWeb: `docs/odoo_regeln_qweb_2026-10-02.md`. JS-Tests: `docs/odoo_regeln_js_tests_2026-10-02.md`.
Index: `docs/odoo_regeln_index_2026-10-02.md`.

**Vorsicht, Quelle teils inkonsistent/veraltet:** `framework_overview.rst` zeigt `this.env._t(...)` und
`env.services.action_manager`, `javascript_reference.rst` zeigt dagegen `import { _t } from
"@web/core/l10n/translation"` und `useService`. Maßgeblich ist das jüngere Muster (Import von `_t`, `useService`).
Bundlenamen (`web.assets_common`) und Beispiele vor Gebrauch im Core des Containers prüfen (Suchraster `CLAUDE.md`).

## 1. Grundsätze

- **Neuer Code in Owl**, "wenn möglich". Wort "Komponente" = Owl, "Widget" = altes Odoo-Widget.
- **Native JS-Module** (ES-Module) für alle neuen Dateien; "Odoo-Module" (`odoo.define`) nur für alte, nicht
  umgestellte Dateien; **Plain-JS** nur für externe Bibliotheken und kleine Low-Level-Zwecke (dann als IIFE).
- JS-Code **ECMAScript-2019-kompatibel** (Quelle Owl-Abschnitt).
- Eigenen Code **nicht** in den globalen Scope legen (Namenskonflikte, implizite Reihenfolge).
- Seit Odoo 14 teilen alle Versionen dieselbe Owl-Version; Änderungen an Owl nur per PR an `odoo/owl`.

## 2. JavaScript-Module

- Transpiliert werden Dateien unter **`/static/src`** und **`/static/tests`** automatisch (Opt-out mit erster Zeile
  `/** @odoo-module ignore **/`); in anderen Ordnern per Opt-in `/** @odoo-module **/` in der ersten Zeile.
- Modulname: `@<addon>/pfad/zur/datei` (ohne `static/src`). **Relative Imports nur innerhalb desselben Addons**;
  addon-übergreifend immer voller Name (`import {x} from "@web/file_a"`). `@web/…` = `web/static/src/…`.
- Alias für Altcode: `/** @odoo-module alias=web.someName **/` (exportiert `default`; mit `default=0` das ganze
  Modul). Nur **ein** Alias je Datei.
- **Einschränkungen des Transpilers** (kein vollständiger Parser): `import`/`export` nicht hinter einem
  Nicht-Leerzeichen in derselben Zeile; mehrzeilige Kommentare/Strings dürfen keine Zeile mit `import`/`export`
  beginnen; **in `export { … }` keine Kommentare**; ein Name mit `/` gilt als Pfad (keine Modulnamen mit `/`).
- Altes System (`odoo.define(name, deps, fn)`): Name `addon.Beschreibung`, eindeutig; **keine zirkulären
  Abhängigkeiten**; fehlende Abhängigkeiten → Modul wird nicht geladen (Konsole: Missing / Failed / Rejected /
  Non loaded modules).

## 3. Assets

- Drei Typen: Code (js), Stil (css/scss), Templates (xml; werden nicht gebündelt, sondern vom Dateisystem gelesen
  und über `/web/webclient/qweb/` geliefert).
- Bundles im Manifest unter `assets` (Dict Bundlename → Liste von Pfaden, **Glob** erlaubt). Wichtige Bundles:
  `web.assets_backend` (Webclient), `web.assets_frontend` (Website/Portal), `web.assets_common`, 
  `web.assets_unit_tests`; Tours: `web.assets_tests`; Berichte: `web.report_assets_common` bzw. `web.reports_assets_common` (Schreibweise in der Quelle uneinheitlich, im Core prüfen; Actions-Destillat).
  Unterbundles beginnen per Konvention mit `_`.
- **Operationen** (Tupel): `append` (Standard: nur Pfad), `('prepend', pfad)`, `('before', ziel, pfad)`,
  `('after', ziel, pfad)`, `('include', bundle)`, `('remove', ziel)`, `('replace', ziel, pfad)`.
  `before/after/remove/replace` brauchen ein **vorher deklariertes** Ziel – das ändernde Modul muss vom deklarierenden
  **abhängen** (sonst Fehler).
- **Ladereihenfolge:** `ir.asset` mit `sequence < 16` → Manifeste in Abhängigkeitsreihenfolge (jede Datei nur beim
  ersten Vorkommen) → restliche `ir.asset` (`sequence ≥ 16`). Reihenfolge innerhalb eines Globs: Datei **vor** dem
  Glob einzeln nennen (`'lib/jquery/jquery.js', 'lib/jquery/**/*'`).
- **`ir.asset`** (DB, `<asset>`-Kurzform bevorzugen): `name`, `bundle`, `directive`, `path`, `target`, `active`
  (nur bei Erstellung wirksam), `sequence` (16). Haupteinsatz Website (bedingte Assets).
- **Lazy Loading:** `loadAssets({jsLibs: [...], cssLibs: [...]})`, Hook `useAssets(...)` in `onWillStart`
  (`@web/core/assets`) für selten gebrauchte große Bibliotheken.
- Entwicklung: Server neu starten, `--dev=xml` (prüft Bundles bei jedem Zugriff; **nicht in Produktion**),
  Debug-Menü "Assets regenerieren", `?debug=assets` (nicht minifiziert + Source-Maps), Seite neu laden (kein HMR).

## 4. Webclient-Architektur

- `env` (Owl-Umgebung): `qweb`, `bus`, `services`, `debug`, `_t`, `isSmall` (≤ 767 px).
- Bausteine: **Registries, Services, Komponenten, Hooks**.
- **Kontext:** *User-Context* (`user.context`: `allowed_company_ids` – erstes Element = Hauptfirma –, `lang`, `tz`;
  der `orm`-Service hängt ihn automatisch an) und *Action-Context* (Feld `context` der Aktion als String,
  z. B. `{'search_default_customer': 1}`; erweitern mit `doAction(..., {additional_context: {...}})`). Kontext
  **sparsam** nutzen – vieles geht ohne.
- **Python-Interpreter** im Browser (`@web/core/py_js/py`: `evaluateExpr`, `parseExpr`, `evaluate`) für
  View-Modifier/Domains.
- **Domains in JS:** Liste (Präfixnotation, `&` implizit) oder String-Ausdruck (kann Python/Variablen enthalten);
  Klasse `Domain` (`contains`, `toString`, `toList(context)`, statisch `and/or/not/combine`).
- **Bus** (`env.bus`, Owl-`EventBus`): Ereignisse wie `WEB_CLIENT_READY`, `ROUTE_CHANGE`, `RPC:REQUEST/RESPONSE`,
  `ACTION_MANAGER:UI-UPDATED`, `CLEAR-CACHES`, `CLEAR-UNCOMMITTED-CHANGES`; Listener per **`useBus`** (räumt beim
  Unmount auf).
- **`browser`-Objekt** (`@web/core/browser/browser`) statt direkter Browser-Globals (`setTimeout`, `localStorage`,
  `fetch`, `location` …): **testbar durch Mocking**.
- **Debug-Modus:** `env.debug` (String); `assets` (nicht minifiziert, Source-Maps), `tests` (injiziert
  `web.assets_tests`). Elemente nur im Debug zeigen: `groups="base.group_no_one"`.
- **Tooltips:** `data-tooltip`, `data-tooltip-position` (`top|bottom|left|right`), `data-tooltip-delay` (400),
  für dynamischen/HTML-Inhalt `data-tooltip-template` + `data-tooltip-info` statt `title`.

## 5. Registries

- Geordnete Key/Value-Maps = **die** Erweiterungspunkte. `registry.category("fields" | "services" | "views" |
  "actions" | "systray" | "main_components" | "user_menuitems" | "formatters" | "parsers" | "effects" |
  "error_handlers")`.
- `add(key, value, {force, sequence})` – doppelter Key wirft Fehler (außer `force`); `get`, `contains`, `getAll`
  (nach `sequence`), `remove`, `category()`. Registries sind Event-Busse (`UPDATE`).
- **Systray:** `{Component, props?, isDisplayed?(env)}`, Wurzelelement der Komponente `<li>`, `sequence` Standard 50
  (niedrig = rechts). **Hauptkomponenten:** `{Component, props?}`. **Usermenü:** Funktion `(env) → {description,
  callback, href?, hide?, sequence?}`.
- **Feld-Widget:** `registry.category("fields").add("name", {component, supportedTypes: [...]})`.
- **Client-Aktion:** `registry.category("actions").add("tag", Component)` + `ir.actions.client`-Datensatz mit `tag`.

## 6. Services

- Langlebige Code-Einheiten mit Abhängigkeiten (DI): `{dependencies: [...], async?, start(env, deps)}` in
  `registry.category("services")`; `start` darf Wert oder Promise liefern, `null` = kein Wert.
- **Nicht-Komponenten-Code mit Nebenwirkung in einen Service packen** – Tests können dann wählen, welche Services
  aktiv sind.
- Nutzung in Komponenten **nur über `useService("name")`** (verhindert Aufrufe/Fortsetzung nach Zerstörung der
  Komponente; `async`-Flag lässt Aufrufe zerstörter Komponenten hängen).
- Standardservices: `cookie`, `effect`, `http`, `notification`, `router`, `rpc`, `scroller`, `title`, `user`,
  `orm`, `action`, `dialog`, `error`.
  - **`orm`** für Modellmethoden: `this.orm.call("model", "method", [args])` (`/web/dataset/call_kw`).
  - **`rpc`** (`import { rpc } from "@web/core/network/rpc"`, `rpc("/route", params)`) **nur für Controller**,
    nicht für Modelle. POST/JSON; Serverfehler kommen mit HTTP 200 und `error`-Schlüssel, werden als Fehler
    behandelt; Netzwerkfehler → Hinweis, Server wird regelmäßig angepingt.
  - `notification.add(msg, {title, type: warning|danger|success|info, sticky, className, onClose, buttons,
    autocloseDelay})` liefert eine Schließfunktion; von Python über Client-Aktion `display_notification`.
  - `user`: `context`, `isAdmin`, `isSystem`, `lang`, `tz`, `userId`, `partnerId`, `hasGroup(xmlid)`
    (async), `updateContext`, `removeFromContext`.
  - `router`: `current`, `pushState(hash, replace?)` (löst **kein** `ROUTE_CHANGE` aus – Aufrufer aktualisiert die
    Anzeige), `redirect(url, wait?)`. `title`: `setParts({key: value|null})`. `cookie`: `setCookie`, `deleteCookie`.
  - `effect.add({type: "rainbow_man", message, …})`; eigener Effekt über Registry `effects`.
  - `http.get/post` für Low-Level-HTTP.

## 7. Komponenten und Hooks

- Komponente: Klasse mit `static template = "addon.ComponentName"` (**Templatename `addon_name.ComponentName`**).
  Template in `.xml`-Datei (damit übersetzbar), nicht per `xml\`…\``-Helfer (nur für Beispiele/Tests).
- Pro Komponente meist 2–3 Dateien am selben Ort: `my_component.js`, `my_component.xml`, optional `.scss`; alle ins
  Asset-Bundle.
- **Nie `constructor` überschreiben – `setup()` benutzen** (Konstruktoren sind nicht patchbar).
- Odoo-Hooks: `useService`, `useBus`, `useAutofocus` (`t-ref="autofocus"`), `usePosition` (`t-ref="popper"`),
  `usePager`, `useSpellCheck`, `useAssets`; Lifecycle-Hooks (`onWillStart`, `onMounted`, `onWillUnmount`) räumen auf.
  `useEffect` ist **nicht** der Effect-Service.
- Wiederverwendbare Komponenten (`@web/core/…`): `CheckBox`, `ColorList`, `Dropdown`/`DropdownItem`/`DropdownGroup`
  (+ `useDropdownState`; Menüinhalt liegt im Overlay am Dokumentende → Selektoren über `menuClass`/`class`),
  `Notebook`, `Pager` (`offset`, `limit`, `total`, `onUpdate`), `SelectMenu` (**natives `<select>` bevorzugen**,
  besser für Barrierefreiheit/Mobil), `TagsList`, `ActionSwiper`. Props und Beispiele: Quelle `owl_components.rst`.

## 8. Patchen

- `patch(obj, extension)` aus `@web/core/utils/patch`; liefert die Rückgängig-Funktion (v. a. Tests).
- **Nur wenn kein Erweiterungspunkt (Registry) reicht.** Patches gefährlich (ändern auch bestehende Instanzen) →
  **so früh wie möglich auf Modulebene** anwenden, nicht zur Laufzeit.
- Methoden einer Klasse → **`MyClass.prototype`** patchen; statische Member → die Klasse selbst.
- `super` nur in **Methoden** (nicht in `function`/Pfeilfunktion); Getter/Setter gehen.
- **Konstruktor nicht patchbar** → Logik in `setup()` o. Ä. legen und das patchen.
- Dieselbe Erweiterung nicht auf mehrere Objekte wiederverwenden und **Erweiterungsobjekte nicht kopieren/spreaden**
  (`super` zeigt sonst falsch): Fabrikfunktion, die das Objekt je Aufruf neu erzeugt; abgeleitete Erweiterung als
  getrennten Patch anwenden.

## 9. Fehlerbehandlung (JS)

- Nur **Error-Objekte** werfen; **Promises nur mit Error-Objekten ablehnen**; abgelehnte Promises = geworfene Fehler.
- **Fehler vermeiden/nicht für Kontrollfluss nutzen:** teuer, erschwert Debugging ("pause on exceptions"),
  überspringt Aufräumcode (Listener-Leaks). Stattdessen `null`/`undefined` zurückgeben oder
  `{val, err}` bzw. `[err, val]` (Fehler zuerst).
- **Fangen:** `try`-Block so klein wie möglich (genau **eine** Anweisung), unbekannte Fehler per
  `instanceof`-Prüfung **neu werfen**; `.catch` direkt am möglichen Fehlerpromise.
- **Wann werfen:** generische Fehler (UserError/AccessError/LostConnection – zentral über Registry
  `error_handlers`), verletzte Vorbedingungen (Code/Daten kaputt), selten bei tiefer Rekursion.
- **Top-Level-Fehler beim Modulladen sind kritisch:** Modul so schreiben, dass die Definition **nie** wirft.
- **Owl:** Fehler in `setup`/Render/Lifecycle-Hooks laufen in `onError`-Handler nach oben; unbehandelt zerstört Owl
  die Anwendung. Handler, der nicht behandeln kann, **muss neu werfen**; sonst Zustand reparieren und den Fehler
  getrennt melden (`Promise.reject(error)` ohne Weitergabe) – so machen es Action- und Dialog-Service.
- `error_handlers`-Registry: Handler gibt **truthy** zurück = behandelt; `preventDefault` am Event = erwarteter
  Geschäftsfehler (Test schlägt sonst fehl, weil "unerwartet").

## 10. Übersetzung, Session, Views, Benachrichtigungen

- **`_t` aus `@web/core/l10n/translation`; Argument muss ein fester Literal-String sein** (statisch extrahiert);
  Dynamisches über Platzhalter: `_t("Hello %s, you have %s", name, count)`. Keine Template-Strings mit Ausdrücken
  (Odoo `test_jstranslate`).
- **Session:** Daten für den Webclient über `ir.http.session_info()` (Python überschreiben, `super()` aufrufen), in
  JS `import { session } from "@web/session"`. **Nur billige, früh benötigte Daten** – langsames `session_info`
  verzögert den Start für alle.
- **Views (JS):** Controller + Model + Renderer-Struktur; Dekorationen `decoration-{bf,it,danger,info,muted,primary,
  success,warning}` → CSS `text-*`, Wert = Python-Ausdruck mit dem Datensatz als Kontext.
- **Benachrichtigungstypen:** `info` (Rückmeldung, kann nicht fehlschlagen), `success`, `warning` (teilweise/nicht vom
  Nutzer verursacht), `danger` (fehlgeschlagen).
- **Neu laden:** Owl/Odoo hat kein Hot-Reload; bei "Datei wird nicht geladen" prüfen: gespeichert, Konsole,
  `console.log` am Dateianfang, Bundle aktuell?

## 11. Odoo Editor, Mobile

- **Powerbox** (Editor, `/`-Befehle): nur **eine** Instanz, vom Editor selbst – **nie selbst instanziieren**.
  Befehle/Kategorien über die Editor-Optionen (`commands`, `categories`, `powerboxFilters`); Prioritäten wie
  `z-index` mit Bedacht wählen; Namen/Beschreibungen mit `_t`. Relevant für `onlyoffice_odoo`/Editor-Themen nur
  mittelbar.
- **Mobile (`web_mobile`):** nur Odoo-**Enterprise**-App; Methoden (`showToast`, `vibrate`, `showSnackBar`,
  `addContact`, `scanBarcode`, `switchAccount`) vor Aufruf auf Verfügbarkeit prüfen; für Community-Betrieb
  (HM-SRV/Tower) nicht relevant. Quelle nennt noch jQuery-Deferred-Rückgaben – veraltet.
