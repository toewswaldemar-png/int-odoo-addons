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
