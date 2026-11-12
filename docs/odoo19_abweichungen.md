# Bestätigte Abweichungen zwischen Odoo-19-Dokumentation und Core

Diese Datei enthält keine eigenen Entwicklungsregeln. Sie dokumentiert ausschließlich konkret nachgewiesene Abweichungen zwischen der offiziellen Odoo-19-Dokumentation und dem Odoo-19-Core.

Verglichener Core: Branch `19.0`, Commit `7a74539a4aedf93e0a9d51064680b343477447aa` vom 2026-10-10. Die lokale Dokumentationskopie wurde am 2026-10-02 abgerufen. Vor einer Übernahme in Code sind die Fundstellen gegen den tatsächlich eingesetzten Odoo-Commit zu prüfen.

## A-001: Vertauschte Bedingung im Cron-Batch-Beispiel

**Status:** bestätigt durch Dokumentationsquelle, Core-Semantik und Minimaltest.

**Dokumentation:** `docs/odoo19_reference/backend/actions.md`, Funktion `_cron_do_something`, Zeilen 551–557. Die Dokumentation berechnet:

```python
remaining = 0 if len(records) == limit else self.search_count(domain)
```

**Core:**

- `docs/odoo/odoo/addons/base/models/ir_cron.py`, `IrCron._commit_progress`, Zeilen 846–887: Der übergebene Wert wird als aktuelle Restmenge gespeichert.
- dieselbe Datei, `_run_job`, Zeilen 510–529: Ein erfolgreicher Lauf mit `remaining == 0` wird als `FULLY_DONE` behandelt.

**Abweichung:** Ein voller Stapel (`len(records) == limit`) beweist nicht, dass keine weitere Arbeit vorhanden ist. Die Dokumentation meldet in diesem Fall dennoch `remaining=0`. Unter der im Beispiel vorausgesetzten Bedingung, dass `do_something()` die bearbeiteten Datensätze aus der Domain entfernt, lautet die korrekte Berechnung:

```python
remaining = self.search_count(domain) if len(records) == limit else 0
```

**Minimaltest:** ausgeführt am 2026-10-17 mit Python 3.14.5. Testfall: `limit=300`, voller Stapel mit 300 Datensätzen, danach 20 weitere Treffer. Dokumentationsformel: `0`; korrigierte Formel: `20`. Nach `_run_job` führt der dokumentierte Wert zum Status `FULLY_DONE`.

## A-002: `at_install` und `post_install` – Dokumentation erlaubt beide, Core warnt

**Status:** bestätigt durch Dokumentationsquelle und Core-Ausdruck; ein Importtest des vollständigen Odoo-Testmoduls war lokal nicht möglich, weil der Host-Python-Umgebung `psutil` fehlt.

**Dokumentation:** `docs/odoo19_reference/backend/testing.md`, Zeilen 550–558. Dort steht ausdrücklich, dass `post_install` nicht exklusiv mit `at_install` ist; üblicherweise wird `post_install` dennoch mit `-at_install` kombiniert.

**Core:** `docs/odoo/odoo/tests/common.py`, Funktion `tagged`, Zeilen 2728–2750. Nach der Tag-Vererbung berechnet der Core:

```python
if not (at_install ^ post_install):
    _logger.warning(...)
```

Damit warnt der Dekorator sowohl bei beiden Tags als auch bei keinem der beiden Tags.

**Abweichung:** Die Kombination ist technisch möglich und laut Dokumentation zulässig, erzeugt beim Einsatz des Core-Dekorators `tagged()` aber eine Warnung.

**Minimaltest:** Der Wahrheitswert des unveränderten Core-Ausdrucks `not (at_install ^ post_install)` wurde am 2026-10-17 für beide Tags mit `True` ausgewertet. Ein vollständiger Odoo-Lauf bleibt nachzuholen, falls das konkrete Logging-Verhalten für eine Entscheidung relevant ist.

## A-003: Rezept „Standalone Owl application“ – das Bündel übersetzt ohne `_variables-dark.scss` und `_maps.scss` nicht

**Status:** bestätigt durch Lauf auf einer Odoo-19-Instanz; die Dokumentationsseite liegt nicht in der lokalen Kopie `docs/odoo19_reference` und wurde am 2026-11-12 über die Webseite gelesen (die Liste des Manifests stammt aus dem Bericht eines Lese-Agenten, nicht aus einer wörtlichen Kopie): vor einer Übernahme die Seite selbst gegenlesen.

**Dokumentation:** `https://www.odoo.com/documentation/19.0/developer/howtos/standalone_owl_application.html`, Schritt „assets bundle“. Das Bündel soll aus diesen Einträgen bestehen, die ersten vier nennt die Seite „mandatory“:

```python
('include', 'web._assets_helpers'),
'web/static/src/scss/pre_variables.scss',
'web/static/lib/bootstrap/scss/_variables.scss',
('include', 'web._assets_bootstrap'),
('include', 'web._assets_core'),
'your_module/static/src/standalone_app/**/*',
```

**Core:** `addons/web/__manifest__.py`, Bündel `web.assets_backend` (Zeilen 49–56), `web.assets_backend_lazy` und weitere führen nach `_variables.scss` zusätzlich `web/static/lib/bootstrap/scss/_variables-dark.scss` und `web/static/lib/bootstrap/scss/_maps.scss` auf. `_maps.scss` definiert `$theme-colors-rgb` (Zeile 6), das `bootstrap/scss/_utilities.scss` (über `web._assets_bootstrap` → `import_bootstrap.scss`) braucht.

**Abweichung:** Mit genau den Einträgen der Dokumentation bricht die Übersetzung des Stylesheets ab. Odoo liefert dann statt des CSS nur einen Fehlerblock (`body::before { content: "A css error occured, using an old style to render this page" }`) mit der Meldung `Undefined variable: "$theme-colors-rgb"` in `web/static/lib/bootstrap/scss/_utilities.scss`, Zeile 92. Mit den zwei zusätzlichen Einträgen übersetzt dasselbe Bündel.

**Test:** ausgeführt am 2026-11-12 auf `Odoo Server 19.0-20260817` (Image `odoo:latest`, Datenbank `regler_demo`, Modul `int_regler_standalone`): `GET /web/assets/debug/int_regler_standalone.assets_hello.css` lieferte mit den Einträgen der Dokumentation 5 117 Byte (nur der Fehlerblock), nach dem Hinzufügen der beiden Dateien 340 114 Byte mit 3 365 Regeln und ohne Fehlerblock. Das Bündel `int_regler_standalone.assets_list` (das beide Dateien schon hatte) lieferte 770 089 Byte mit 7 053 Regeln. Die Bündel des Moduls liegen in `int_regler_standalone/__manifest__.py`.

**Einschränkung:** Der Core-Stand der Instanz (19.0-20260817) ist ein anderer als der verglichene Core dieser Datei (Commit `7a74539a…`, 2026-10-10) und als der lokale Quelltext (`8d05257d…`, 2026-08-10); die Zeilenangaben des Core stammen aus dem zweiten.

## A-004: Beispielseite „Standalone Owl application“ – `t-nocache` kennt der Core nicht

**Status:** bestätigt durch Lauf; Fundstelle der Dokumentation wie bei A-003.

**Dokumentation:** Die QWeb-Seite des Beispiels schreibt den CSRF-Token als `<t t-nocache="The csrf token must always be up to date." t-esc="request.csrf_token(None)"/>`.

**Core:** In `odoo/addons/base/models/ir_qweb.py` und `addons/web` kommt `t-nocache` nicht vor (Suche am 2026-11-12 ohne Treffer).

**Abweichung:** Beim Rendern warnt Odoo bei jedem Aufruf der Seite: `odoo.addons.base.models.ir_qweb: Unknown directives or unused attributes: {'t-nocache'}`. Die Seite wird trotzdem richtig erzeugt (Token vorhanden), das Attribut hat in diesem Modul keine Wirkung.

**Test:** `GET /int_regler_standalone/hello` am 2026-11-12 auf der Instanz von A-003: Antwort 200, die Warnung steht im Log der Instanz (`Unknown directives or unused attributes: {'t-nocache'} in 260`).
