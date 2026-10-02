# Odoo 19 Regeln: Testen (Destillat)

Quelle: `odoo/documentation`, Branch 19.0, Commit `eee2e56` (2026-10-02),
`content/developer/reference/backend/testing.rst`
(Web: <https://www.odoo.com/documentation/19.0/developer/reference/backend/testing.html>).
Geprüft: 2026-10-02. Ergänzt `docs/odoo_konventionen_2026-09-26.md` Abschnitt 7. JS-Tests (Hoot, Mock-Server,
Web-Helfer): `docs/odoo_regeln_js_tests_2026-10-02.md`. Index: `docs/odoo_regeln_index_2026-10-02.md`.

**Grenze der Quelle:** Klassen und Methoden (`TransactionCase`, `HttpCase`, `Form`, `assertQueryCount`, `tagged` …)
sind *autodoc* – Details im Core-Quellcode.

## 1. Drei Testarten

| Art | Wofür | Ort |
|---|---|---|
| Python-Unit-Tests (`unittest`) | Geschäftslogik der Modelle | `tests/` |
| JS-Unit-Tests (Hoot) | JS-Code isoliert | `static/tests/` |
| Tours | Zusammenspiel Server ↔ Webclient (Szenario eines Geschäftsablaufs) | `static/tests/tours/` + Aufruf aus `tests/` |

## 2. Python-Tests

- Unterpaket `tests/`, Moduldateien **`test_*.py`**, Methoden **`test_*`**.
- **Jede Testdatei MUSS in `tests/__init__.py` importiert werden** (`from . import test_foo, test_bar`) – sonst
  läuft sie nicht (Odoo `test_test_holes` prüft das).
- Basisklassen: `TransactionCase` (Normalfall: eine Eigenschaft je Methode), `SingleTransactionCase`,
  `HttpCase` (`url_open`, `browser_js`, `start_tour`). Hilfen: `self.ref`, `self.browse_ref`, `Form` (simuliert
  das Formular, mit `M2MProxy`/`O2MProxy`).
- Tests laufen automatisch bei Installation/Update, wenn der Server mit `--test-enable` gestartet wurde. **Nur in
  installierten Modulen**; frische DB: einmal `-i`, bei Änderungen `-u`.

### Tags und Auswahl
- Unterklassen von `BaseCase` sind automatisch `standard` + `at_install`.
- `@tagged(...)` ist ein **Klassen**-Dekorator, wirkt **nicht** auf Funktionen/Methoden (Quelle: "danger").
  `-` vor dem Tag entfernt ihn (`@tagged('-standard', 'nice')`).
- `post_install` = nach Installation **aller** Module (meist für `HttpCase`): `@tagged('-at_install', 'post_install')`.
- **Reines `unittest.TestCase` erbt keine Tags** und läuft sonst nicht → `@tagged('standard', 'at_install')`.
- `--test-tags` impliziert `--test-enable`, Standardwert `+standard`, Werte sind additiv;
  Syntax `[-][tag][/modul][:klasse][.methode]` (`--test-tags /int_filemanager`,
  `--test-tags '/int_filemanager,-slow'`).

### Abfragenzahl
- `with self.assertQueryCount(n): …` begrenzt die Zahl der SQL-Abfragen; manuell `--log-sql`.
  Mit `self.profile()` **außerhalb** von `assertQueryCount` kombinieren (Performance-Destillat).

## 3. Tours (Integrationstests)

- Dateien: `static/tests/tours/<name>.js` + `tests/test_<name>.py` (erbt `HttpCase`, ruft
  `self.start_tour("/web", "tour_name", login="admin")`).
- **Manifest:** `'assets': {'web.assets_tests': ['mod/static/tests/tours/<name>.js']}`.
- Registrierung: `import tour from 'web_tour.tour'; tour.register('name', {url: '/web'}, [steps])`.
- **Step:** Pflicht `trigger` (Selektor, Tour wartet auf sichtbares Element); optional `run` (Aktionsname wie
  `click`, `fill`, `edit`, `check`, `select`, `drag_and_drop`, … oder async-Funktion), `content` (**empfohlen**:
  Tooltip und Log), `isActive` (Bedingungen: desktop/mobile, community/enterprise, auto/manual), `tooltipPosition`,
  `timeout` (Standard 10 s). Vordefinierte Schritte `tour.stepUtils.*`.
- **Die letzten Schritte MÜSSEN den Client in einen stabilen Zustand bringen** (keine laufende Bearbeitung, alle
  Netzwerkrequests fertig), sonst Race Conditions/Fehler beim Teardown.
- Debuggen: `watch=True` (sichtbares Chrome), `debug=True` (Devtools, Breakpoint; Step-Property `break: true`,
  `pause: true` + `play()`), `odoo.startTour("name")` im Browser oder `?debug=tests`. Screenshots bei Fehlschlag
  unter `/tmp/odoo_tests/{db}/screenshots/`; `--screenshots`, `--screencasts`.
- **Onboarding-Tours** (Benutzerführung): `static/src/js/tours/*.js` in `web.assets_backend` plus
  `web_tour.tour`-Datensatz (`name` = JS-Registrierung, `sequence`, `url`, `rainbow_man_message`).

## 4. Hausregeln (ergänzend aus `docs/odoo_konventionen_2026-09-26.md` Abschnitt 7, bleiben gültig)

- Jede Fehlerbehebung mit einem Test, der ohne die Behebung fehlschlägt.
- Mit möglichst geringen Rechten testen (`new_test_user`, `@users`); Flaky-Test-Fallen vermeiden
  (`subTest` setzt DB/Cache nicht zurück; feste Daten statt `now()`; externe Dienste mocken).
