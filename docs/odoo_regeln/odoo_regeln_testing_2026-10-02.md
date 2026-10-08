# Odoo 19 Regeln: Testen (Destillat)

Quellen (nur offiziell, bei Widerspruch gilt der Code vor der Doku): Odoo-19.0-Quellcode (`odoo/tests/common.py`, `odoo/tools/config.py`,
`odoo/addons/test_lint/tests/test_test_holes.py`, `addons/web_tour/static/src`) und `odoo/documentation`, Branch 19.0,
`content/developer/reference/backend/testing.rst`
(Web: <https://www.odoo.com/documentation/19.0/developer/reference/backend/testing.html>).
Geprüft: 2026-10-02. Ergänzt `odoo_regeln_coding_guidelines_2026-10-02.md` Abschnitt 7. JS-Tests (Hoot, Mock-Server,
Web-Helfer): `docs/odoo_regeln/odoo_regeln_js_tests_2026-10-02.md`. Index: `docs/odoo_regeln/odoo_regeln_index_2026-10-02.md`.

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
- Unterklassen von `BaseCase` sind automatisch `standard` + `at_install`; Tags werden vererbt. Eine Klasse muss genau eines von `at_install`
  und `post_install` tragen (sonst Warnung); `HttpCase` gehört nach `post_install`.
- `@tagged(...)` ist ein **Klassen**-Dekorator, wirkt **nicht** auf Funktionen/Methoden (Quelle: "danger").
  `-` vor dem Tag entfernt ihn (`@tagged('-standard', 'nice')`).
- `post_install` = nach Installation **aller** Module (meist für `HttpCase`): `@tagged('-at_install', 'post_install')`.
- **Reines `unittest.TestCase` erbt keine Tags** und läuft sonst nicht → `@tagged('standard', 'at_install')`.
- `--test-tags` impliziert `--test-enable`, Standardwert `+standard`, Werte sind additiv;
  Syntax `[-][tag][/modul][:klasse][.methode]` (`--test-tags /sale`,
  `--test-tags '/sale,-slow'`, Beispiele der Referenz).

### Abfragenzahl
- `with self.assertQueryCount(n): …` begrenzt die Zahl der SQL-Abfragen; manuell `--log-sql`.
  Mit `self.profile()` **außerhalb** von `assertQueryCount` kombinieren (Performance-Destillat).

## 3. Tours (Integrationstests)

- Dateien: `static/tests/tours/<name>.js` + `tests/test_<name>.py` (erbt `HttpCase`, ruft
  `self.start_tour("/web", "tour_name", login="admin")`).
- **Manifest:** `'assets': {'web.assets_tests': ['mod/static/tests/tours/<name>.js']}`.
- Registrierung: `registry.category("web_tour.tours").add("name", {url: "/odoo", steps: () => [...]})` (`registry` aus `@web/core/registry`;
  so registrieren die Tours im 19.0-Core, z. B. `addons/account/static/tests/tours`; die Referenz zeigt noch `tour.register(...)`).
- **Step:** Pflicht `trigger` (Selektor, Tour wartet auf sichtbares Element); optional `run` (Aktionsname wie
  `click`, `fill`, `edit`, `check`, `select`, `drag_and_drop`, … oder Funktion), `content` (**empfohlen**:
  Tooltip und Log), `isActive` (Liste von Bedingungen: desktop/mobile, community/enterprise, auto/manual), `tooltipPosition`
  (`top|bottom|left|right`), `timeout` (0 bis 60000 ms, Standard 10 s), `expectUnloadPage`. Vordefinierte Schritte `stepUtils` aus
  `@web_tour/tour_utils`.
- **Die letzten Schritte MÜSSEN den Client in einen stabilen Zustand bringen** (keine laufende Bearbeitung, alle
  Netzwerkrequests fertig), sonst Race Conditions/Fehler beim Teardown.
- Debuggen: `watch=True` (sichtbares Chrome), `debug=True` (Devtools, Breakpoint; Step-Property `break: true`,
  `pause: true` + `play()`), `odoo.startTour("name")` im Browser oder `?debug=tests`. Screenshots bei Fehlschlag
  unter `/tmp/odoo_tests/{db}/screenshots/`; `--screenshots`, `--screencasts`.
- **Onboarding-Tours** (Benutzerführung): `static/src/js/tours/*.js` in `web.assets_backend` plus
  `web_tour.tour`-Datensatz (`name` = JS-Registrierung, `sequence`, `url`, `rainbow_man_message`).

## 4. Ergänzungen aus Referenz und Core

- Gemeinsame Testdaten gehören laut Referenz in `setUpClass` (einmal je Klasse). `TransactionCase` räumt Record- und Registry-Cache
  nach jeder Methode auf, aber nicht Modelle/Felder der Registry: wer die Registry ändert, bereitet `self.registry.reset_changes()` vor.
- `assertQueryCount` (`odoo/tests/common.py`) kennt auch benannte Zähler je Nutzer (`assertQueryCount(admin=3, demo=5)`, für `@users`).
- Der Core warnt, wenn eine Klasse nicht genau eines von `at_install`/`post_install` trägt und wenn ein `HttpCase` nicht
  nur `post_install` ist (`odoo/tests/common.py`).
- Hilfen im Core: `new_test_user`, `users` (Dekorator), `freeze_time` (Klasse, ersetzt `freezegun.freeze_time` in den Odoo-Tests), alle in `odoo/tests/common.py`.
