# Odoo 19 Regeln: JavaScript-Unit-Tests – Hoot, Web-Helfer, Mock-Server (Destillat)

Quelle: `odoo/documentation`, Branch 19.0, Commit `eee2e56` (2026-10-02),
`content/developer/reference/frontend/unit_testing.rst`, `unit_testing/hoot.rst`, `unit_testing/web_helpers.rst`,
`unit_testing/mock_server.rst`
(Web: <https://www.odoo.com/documentation/19.0/developer/reference/frontend/unit_testing.html> und Unterseiten).
Geprüft: 2026-10-02. Python-Tests und Tours: `docs/odoo_regeln/odoo_regeln_testing_2026-10-02.md`.
Index: `docs/odoo_regeln/odoo_regeln_index_2026-10-02.md`.

Die Quelle ist ein API-Katalog; hier stehen die **Regeln und Fallstricke**. Matcher-/Helfer-Listen nur als
Namensübersicht, Details in der Quelle bzw. `@odoo/hoot` im Core.

## 1. Aufbau und Setup

- Framework **HOOT** (Hierarchically Organized Odoo Tests), Module: `@odoo/hoot-dom` (DOM abfragen/bedienen,
  auch in Tours nutzbar) und `@odoo/hoot` (nur Unit-Tests: `test`, `describe`, `expect`, Hooks, Zeit-Mocks,
  Netzwerk-Mocks + alles aus `hoot-dom`). Darüber `@web/../tests/web_test_helpers` (Web-Client-Helfer, Mock-Server).
- **Ablage:** `static/tests/` des Addons. **Dateiname `*.test.js` ist Pflicht** (sonst nicht vom Runner erfasst).
  Ausnahme: `*.hoot.js` = globale Module für den ganzen Testlauf (strenge Einschränkungen: eingeschränkte Imports,
  Speicherverwaltung, keine Seiteneffekte). Andere JS-Dateien = Produktivcode oder Hilfsdateien.
- **Bundle:** `'web.assets_unit_tests': ['mein_addon/static/tests/**/*']` im Manifest.
- **Ausführen:** URL **`/web/tests`** (Debug-Menü → "Run Unit Tests").
- Jede Testdatei läuft isoliert in einem globalen `describe` (Name = Dateipfad) → **kein eigenes `describe` nötig**,
  Untersuite nur zur Gliederung/Tag-Vergabe.

## 2. Runner-Optionen (URL-Parameter oder UI)

`bail`, `debugTest`, `fps`, `filter` (Name + Tags), `frameRate` (60), `headless`, `id`, `loglevel` (0–3), `manual`,
`notrycatch`, `order` (`fifo|lifo|random`), `preset`, `showdetail`, `tag`, `timeout` (5 s je Test).
Einschließende Filter (`filter`, `id`, `tag`) wirken als **OR**, ausschließende entfernen Tests.

## 3. Tests schreiben

- `import { describe, expect, test } from "@odoo/hoot"; test("Name", () => { expect(…).toBe(…); });`
- **Modifikatoren:** `not`, `resolves`, `rejects` (nur bei Promises).
- **Allgemeine Matcher:** `toBe` (strikt), `toEqual` (tief), `toBeCloseTo`, `toBeEmpty`, `toBeGreaterThan`,
  `toBeLessThan`, `toBeWithin`, `toBeInstanceOf`, `toBeOfType`, `toHaveLength`, `toInclude`, `toMatch`, `toThrow`.
  Letztes Argument jeweils optionales `{message}`.
- **DOM-Matcher** (Selektor oder Node): `toBeChecked`, `toBeDisplayed`, `toBeEnabled`, `toBeFocused`, `toBeVisible`,
  `toHaveAttribute`, `toHaveClass`, `toHaveCount` (ohne Argument = mindestens 1), `toHaveInnerHTML`,
  `toHaveOuterHTML`, `toHaveProperty`, `toHaveRect`, `toHaveStyle`, `toHaveText`, `toHaveValue`.
- **Schritte statt Assertionszähler:** `expect.step(wert)` + `expect.verifySteps([...])` (**bevorzugt** gegenüber
  `expect.assertions(n)`); **nicht verbrauchte Schritte lassen den Test scheitern**. Async-Varianten
  `expect.waitForSteps`, `expect.waitForErrors` (Timeout 2000 ms); `expect.errors(n)` / `expect.verifyErrors([...])`
  für erwartete Fehler.
- **Eigene Selektoren:** `:contains(text)`, `:displayed`, `:visible`, `:hidden`, `:empty`, `:eq(n)`, `:first`,
  `:last`, `:focusable`, `:iframe`, `:selected`, `:shadow`, `:scrollable`, `:value(text)`.
- **Abfragen:** `queryAll`, `queryOne` (erzwingt genau 1 Treffer), `queryFirst`, `queryText`, `queryValue`,
  `queryAttribute`, `queryAll{Texts,Values,Attributes,Properties}`; Optionen `count`, `displayed`, `focusable`,
  `root`, `visible`. **Warten:** `waitFor`, `waitForNone` (Standard 200 ms), `waitUntil` (5 s).
- **Interaktion (zeigerbasiert):** `click`, `dblclick`, `hover`, `drag` (`moveTo`, `drop`, `cancel`), `check`,
  `uncheck`, `scroll`, `setInputRange`, `pointerDown/Up`. **Ohne Ziel (aktives Element):** `fill` (hängt an),
  `edit` (= `clear` + `fill`), `clear`, `press`, `keyDown/Up`, `select`, `setInputFiles`, `leave`, `resize`, `unload`.

## 4. Mocks (Zeit, Netzwerk, Globals)

- **Standardmäßig gemockt:** Timer (`setTimeout`, `setInterval`, `requestAnimationFrame`), `Date`, `performance`,
  `clipboard`, `fetch`, `XMLHttpRequest`, Storage, History/Location (über Indirektion `@web/core/browser`),
  Navigator, Notification, Permissions, Touch. Timer werden am Testende **alle abgebrochen**.
- **NICHT gemockt:** `Promise` und OWL-Timer → auf OWL-Rendering mit **`animationFrame()`** warten.
- Zeit-Helfer: `advanceTime`, `advanceFrame`, `animationFrame`, `microTick`, `tick`, `delay`, `runAllTimers`,
  `cancelAllTimers`, `mockDate`, `mockTimeZone`, `setFrameRate`. **Feste Daten per `mockDate`** (siehe Python-Regel
  "keine `now()`").
- Netzwerk: `mockFetch`, `mockWebSocket`, `mockWorker`; `mockPermission`, `mockTouch`.
- **Location-Mock funktioniert nur**, wenn Produktivcode `window.location` über `@web/core/browser` anspricht →
  Konsequenz für eigenen Code: **immer das `browser`-Objekt statt Browser-Globals benutzen.**

## 5. Web-Test-Helfer

- **`makeMockEnv()`**: niedrigster Helfer für eine `env` (erzeugt `env`, Mock-Server, startet Services, räumt auf);
  für Services ohne Komponente. **Nur eine `env` je Test**; aktuelle per `getMockEnv()`.
- **`mountWithCleanup(Component, {props, target})`**: bindet Komponente ein (erzeugt `env` + Mock-Server).
  **Die Komponenteninstanz nicht für Assertions/Interaktion benutzen** – nur abgeleitete Informationen aus dem DOM
  abfragen (Ausnahme: schwer lesbare Anzeige wie `canvas`-Diagramme).
- **`mountView({type, resModel, arch})`**: Views einhängen (baut auf `mountWithCleanup`); Instanz ebenfalls nicht
  zurückholen (Ausnahme z. B. Graph-View).
- **`contains(selector).click()/.edit(...)`** statt rohem `click`/`edit`, wenn Elemente noch nicht im DOM sind oder
  Owl mindestens einen Animationsframe braucht (kombiniert Aktion + `animationFrame`). **Nicht Standard für alles:**
  Interaktionen, die in einem **exakten Zeitfenster** passieren müssen, kennt `contains` nicht.

## 6. Mock-Server

- Jeder Test mit `env` bekommt automatisch einen eigenen Mock-Server (fängt **alle** Requests ab; verhindert
  Zugriffe auf die echte DB). Vordefiniert: Routen für Menüs und Übersetzungen, `/web/dataset/call_kw` (ORM-Aufrufe
  an das Mock-Modell). **Ohne definiertes Modell scheitern ORM-Aufrufe.**
- **Modell definieren:** Klasse von `models.Model` mit `_name`, optional `_order`, `_description`, `_records`
  (Fake-Daten, werden beim Laden gegen die Felder validiert; **danach nicht mehr änderbar**), `_views`
  (Mapping Typ → XML-Arch, optional mit ID `"form,418"`), Felder als öffentliche Klassenfelder
  (`name = fields.Char({required: true})`) oder `_fields`, modellspezifische Methoden; dann
  `defineModels({ResPartner})` (gilt für die ganze Datei; in einem Test: nur dort). `_inherit` wirkt **nicht**
  wie erwartet – normale Klassenerweiterung nutzen. Änderungen an `_`-Schlüsseln werden am Testende zurückgesetzt.
- Standardfelder je Modell: `id`, `display_name`, `created_at`, `updated_at`. `compute`/`related` nur für einfachste
  Fälle verlässlich.
- Weitere: `defineMenus`, `defineActions`, `defineParams`.
- **`onRpc`** (mehrfach, Aufruf **vom letzten zum ersten**; ein Rückgabewert ≠ null/undefined beendet die Kette):
  Route (`"/…"`, optional `{pure: true}` für eigene `Response`), Methodenname(n), Modell + Methode, oder nur Callback
  für alle ORM-Aufrufe; Callback bekommt `args`, `kwargs`, `model`, `method`, `parent()`, `route`, `request`.
- `makeMockServer` **nur** für Low-Level-Tests ohne `env`; aktuelle Instanz: `MockServer.current`
  (`MockServer.env["res.partner"].create(...)` ändert nur die Fake-DB, **löst kein Neurendern aus**).
