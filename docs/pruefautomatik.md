# Prüfautomatik

Zwei kleine Prüfungen. Sie ergänzen die Modultests (`tools/check/tests.sh`), ersetzen sie nicht: Logik, Rechte und Performance prüft keines dieser Werkzeuge.
Odoo verlangt keine dieser Prüfungen von einem Drittmodul; die Coding Guidelines sind Empfehlungen. Die Auswahl ist eine Entscheidung des Projekts.

## 1. Ruff beim Commit

| | |
|---|---|
| Konfiguration | `ruff.toml`, unverändert aus dem Odoo-Repository (von der Runbot nächtlich erzeugt, verlangt Ruff ≥ 0.16.1) |
| Läufer | pre-commit (`.pre-commit-config.yaml`), Ruff in der Version aus `.pre-commit-config.yaml`, `--no-fix`: der Hook schreibt keine Dateien um |
| Umfang | geänderte Python-Dateien; nicht geprüft werden `docs/`, `tools/`, `/static/lib/`, `/static/src/lib/`, `/vendor/`, `/build/`, `/dist/` |

Der Hook ignoriert die Regeln, die Odoo in der Kopfzeile der `ruff.toml` als „empfohlen, aber nicht erzwungen“ nennt
(B904, COM812, E741, EM101, I001, RET, RUF021, RUF102, TID252, TRY002, UP006, UP007). Wer sie prüfen will:
`ruff check --no-fix --select <Regel> <Modul>`. Im Bestand fallen vor allem COM812 und TID252 an, dazu I001 (meist Zeilenumbrüche langer Importe) und EM101.
E501 und C901 sind in der `ruff.toml` selbst ignoriert; Ruff formatiert nicht.

Einrichten (einmalig; Windows: `py -3.13 -m pre_commit`):

```bash
pip install pre-commit && pre-commit install
pre-commit run --files <Datei> ...    # oder automatisch bei jedem Commit
```

**Bestand:** `ruff check` mit den Hook-Optionen über alle eigenen Module soll nichts melden. Imports stehen wie in Odoo am Dateikopf; optionale Bibliotheken kennzeichnet Odoo mit `try/except ImportError`, bewusste Importe in Funktionen mit `# noqa: PLC0415`.
Ein Commit ohne installierten Hook (oder mit `--no-verify`) umgeht die Prüfung.

## 2. odoo-ls auf Tower

`tools/check/check.sh` (Git Bash im Repo, läuft über ssh auf dem Tower, SSH-Alias `unraid`; etwa 30 Sekunden) kopiert `int_filemanager` auf den Tower, lässt `odoo_ls_server --parse` in einem Wegwerf-Container aus `odoo:19.0-hm-test` laufen
und wertet die Ausgabe mit `tools/check/check_filter.py` aus. odoo-ls kennt die Odoo-Registry und findet damit, was Ruff nicht sieht. Voraussetzung: `odoo_ls_server` und `typeshed/` unter `/mnt/user/appdata/fmtest/odoo-ls` auf dem Tower.

Der Lauf meldet nur dann `OK`, wenn unter `int_filemanager/` kein Befund der Stufe 1 (Fehler) oder 2 (Warnung) liegt. Stufe 3 (Information, z. B. `OLS03024`) zählt nicht. odoo-ls beendet sich unabhängig von den Befunden normal und meldet auch rund 1.800 Befunde im Odoo-Kern,
deshalb filtert `check_filter.py` nach Pfad; seine Auswertung hat eigene Tests: `python tools/check/test_check_filter.py`.

**Festgelegter Stand:** `odoo_ls_server 1.6.0`, SHA-256 `bdbb18d519462e77a2d5b1d59af079f0c02d024213428b5cd31bc338f2530023`, ein regulärer Release (das neuere 1.6.1 ist nicht getestet). Das mitgelieferte `typeshed` hat keine Versionsangabe.
Bei einem neuen Release müssen die Nachweise unten wiederholt werden.

**Nachgewiesen** (2026-10-17, absichtlich fehlerhafter Code in `int_filemanager`; jeder Fehler wurde als Stufe 1 gemeldet und ließ den Lauf rot werden):

| Absichtlicher Fehler | Meldung |
|---|---|
| `self.env["kein.solches.modell"]` | `OLS03002` Unknown model |
| `search([("kein_feld", "=", 1)])` auf `res.partner` | `OLS03011` Invalid search domain field |
| `self.env["sale.order"]` ohne `sale` in `depends` | `OLS03001` Model not in the dependencies |
| `self.write()` ohne Werte | `OLS01007` Falsche Zahl der Argumente |
| `<field name="kein_feld">` in einer XML-Datenzeile | `OLS05057` Field not found in model |

**Im Kontrollfall nicht gemeldet** (also nicht als geprüft anzusehen): eine nicht vorhandene Methode auf einem Recordset, zu viele Argumente bei `mapped`, doppelte `<template id>` und doppelte `<record id>` in derselben XML-Datei.
Nicht ausprobiert: Compute-Methode, die das Feld nicht setzt, und Related-Feld mit falschem Typ. JavaScript prüft dieser Lauf nicht.
Fallstricke: `typeshed.zip` aus dem Release gehört dazu, sonst bricht der Lauf ab; Bibliotheken außerhalb des Images per `PYTHONPATH` sichtbar machen, sonst Fehlalarme.

## 3. Grenzen

- Beide Prüfungen sind auf Python (Ruff) beziehungsweise auf `int_filemanager` (odoo-ls) beschränkt. Die anderen Module, XML, SCSS, QWeb und JavaScript prüft keine Automatik.
- Es gibt weder ESLint noch Prettier noch Odoo-`test_lint`. Damit fehlen auch die Odoo-Pylint-Prüfungen auf fehlendes `_()` in Fehlermeldungen und auf SQL-Injection sowie die Manifest-Prüfung.
  Beim Entfernen aufgefallen: mehrere Module setzen `application: False` (Odoos Standardwert, von `test_manifests` beanstandet) oder haben kein `author`; Ruff und odoo-ls prüfen das nicht.
- Image (`odoo:19.0-hm-test`) und Odoo-Kern können sich unterscheiden; Befunde können dadurch abweichen.
