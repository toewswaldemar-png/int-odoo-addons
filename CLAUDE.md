# int-odoo-addons

Projektbeschreibung und Modulübersicht: `README.md`. Hier stehen nur die verbindlichen Arbeitsregeln.

Es gibt mehrere voneinander getrennte Odoo-Instanzen: nie annehmen, dass ein Stand von einer Instanz auf einer anderen liegt.

## Verbindlich: vor jeder "kein Bordmittel"/Eigenbau-Aussage Odoo-Core prüfen

**Nie "das gibt es in Odoo nicht" oder "das müssen wir selbst bauen" behaupten, ohne im
Odoo-19-Core-Quellcode nachgesehen zu haben.** Grund: das ist wiederholt falsch gewesen und musste
später korrigiert werden — jedes Mal stand vorher "kein Bordmittel", dann fand sich beim
genaueren Suchen doch eine native Entsprechung:

- Eigene Watch-Buchhaltung im Watcher → **`watchdog`-Bibliothek** ist im Image installiert, der
  Core nutzt sie selbst (`service/server.py`, `FSWatcherWatchdog`).
- ACL-Regeln als generierter Text (`acl_rules.py`) → `ir.rule`-Kontext kann über `user.env[...]`
  zur Auswertungszeit selbst abfragen (`base/models/ir_rule.py`, `_eval_context`/`ormcache`),
  Regenerierung bei jeder Schutzordner-Änderung wäre vermeidbar gewesen.
- Eigenes `trashed`-Boolean-Feld → natives `active` (`_search` filtert das automatisch, auch unter
  `sudo()`, außer mit `active_test=False`).
- Eigene PIL-Aufrufe für Thumbnails → `odoo.tools.image` (`image_process`, `image_fix_orientation`,
  `binary_to_image`).
- Sortierung/Präfix-Suchen/`unique(path)` — mehrfach zuerst als Eigenbau-notwendig eingeschätzt,
  dann doch nativ lösbar gefunden.

### Suchraster (immer alle Punkte, nicht nur den ersten Treffer)

1. **Core-Grep in der lokalen Kopie des Odoo-19-Quellcodes:** `grep -rn "<Begriff>" docs/odoo/odoo docs/odoo/addons`
   (Kopie liegt in `docs/odoo/`, ist nicht Teil des Repos und muss mit dem Odoo-Image übereinstimmen).
2. **Vergleichbare andere Odoo-Module** auf dasselbe Muster prüfen (z.B. `documents`, `mail`,
   `project`, `hr` — oft existiert das Muster schon für einen anderen Anwendungsfall).
3. **`pip list` im Odoo-Image** — welche Bibliotheken sind bereits vorhanden und
   werden vom Core selbst genutzt.
4. **Odoo-eigene Feld-/Modell-Defaults** prüfen (`active`, `ir.rule`, `res.groups`,
   `mail.thread`, `image.mixin`, `@api.autovacuum`, `@api.ondelete` usw.), bevor ein eigenes
   Äquivalent gebaut wird.
5. **Kurz empirisch bestätigen** (z.B. `odoo shell` in einem Wegwerf-Container), nicht nur aus dem
   Quellcode vermuten — siehe ACL-Beispiel oben, wo eine Vermutung im Code (safe_eval habe keinen
   `env`-Zugriff) sich bei echtem Test als unvollständig herausstellte.

Erst wenn alle fünf Punkte durchlaufen sind und nichts Passendes auftaucht, ist "Eigenbau nötig"
eine belastbare Aussage.

## Verbindlich: Odoo-19-Regeln (Coding Guidelines + Developer Reference)

Die Regeln der Odoo-19-Dokumentation (Quelle `odoo/documentation`, Branch 19.0) sind in
`docs/odoo_regeln/odoo_regeln_index_2026-10-02.md` und den dort verlinkten Destillaten im selben Ordner `docs/odoo_regeln/` festgehalten
(Coding Guidelines und Hausregeln: `docs/odoo_regeln/odoo_regeln_coding_guidelines_2026-10-02.md`, Git: `…/odoo_regeln_git_guidelines_2026-10-02.md`).

- **Jede Sitzung mit Code-Änderung:** zuerst `odoo_regeln_index_2026-10-02.md`, dann **alle Dateien in `docs/odoo_regeln/` vollständig lesen**
  (einmal pro Sitzung, ca. 39.000 Tokens; wächst der Ordner über 50.000 Tokens, auf Datei je Bereich zurückgehen: ORM, Views/XML, Sicherheit,
  Daten/Manifest, Aktionen/Cron/Controller/Berichte, JS/Owl/QWeb/Assets, Tests, CLI/Upgrade; Zuordnung im Index) und die Regeln einhalten.
  Bei reinen Doku-Änderungen und kleinen Textkorrekturen reichen Index und Coding Guidelines.
- Neuer Code verletzt sie nicht; bei bestehendem Code Stil nicht umformatieren (Coding Guidelines, "Quellen und Rangfolge").
- Die Destillate sind **kein Ersatz** für den Core-Grep oben: wo die Quelle autodoc ist (Signaturen, Feldparameter),
  gilt der Odoo-Core (`docs/odoo/`). Bei Widerspruch gilt die Odoo-Quelle, nicht das Destillat – Destillat dann korrigieren.
- **Planung und neue Features:** zusätzlich beide `INDEX.md` der Referenzen lesen (`docs/odoo19_reference/`, `docs/owl2_reference/`) und die zum
  Feature gehörenden Referenzdateien; die Fundstellen (Datei und Abschnitt) im Plan nennen. Die Referenzen sind zu groß für ein vollständiges
  Laden (odoo19_reference ca. 320.000, owl2_reference ca. 58.000 Tokens).
- **Volltext-Referenzen zum Nachschlagen** (nicht pauschal laden): `docs/odoo19_reference/` (Odoo-19-Developer-Reference
  plus Coding Guidelines) und `docs/owl2_reference/` (Owl 2.8.4); Einstieg jeweils `INDEX.md`, dann nur die passende Datei lesen.
  Bei Unsicherheit über API-Details (Signaturen, Feldparameter, View-Attribute) hier nachschlagen statt aus dem Gedächtnis
  zu schreiben. **Owl:** Odoo 19 nutzt Owl 2.8.4 – für Owl-Code gilt nur `owl2_reference/`; die Online-Doku `…/owl/documentation/v3/`
  (Owl 3: Signals, Plugins, Effects) gilt für Odoo 19 nicht. Verbindliche Regeln bleiben die Destillate in `docs/odoo_regeln/`.
- Prüfautomatik (pre-commit, `test_lint`, odoo-ls) ist eingerichtet (`docs/pruefautomatik_2026-10-02.md`: Aufruf, Umfang, Grenzen); Regeln ohne
  Werkzeug bleiben Review-Checkliste in den Destillaten. Neuer Code muss `pre-commit run` bestehen.
  **Wann:** nicht bei jeder Bearbeitung. pre-commit läuft bei jedem Commit automatisch (nur geänderte Dateien);
  `tools/v2check/v2check.sh` (`test_lint` + odoo-ls, langsam) einmal vor dem Commit, wenn Python/XML/Manifest/i18n berührt
  wurden; zwischendurch nur gezielte schnelle Tests. **Nie `pre-commit run --all-files` im Arbeitsbaum** (Windows, `autocrlf`): die Hooks schreiben Dateien um
  (Zeilenenden, ruff format); nur `pre-commit run` (staged) bzw. `--files <Datei>`.

## Weitere Grundsätze

- **Code-Konventionen:** `docs/odoo_regeln/odoo_regeln_coding_guidelines_2026-10-02.md` und
  `…_git_guidelines_2026-10-02.md` (Odoo Coding/Git Guidelines 19.0, Security Pitfalls) gelten für neuen
  Code; Abschnitt 8 der Coding Guidelines enthält die Hausregeln dieses Repos. Neuer Code **englisch** (Namen, Kommentare, Docstrings, Logs,
  Commits `[TAG] modul: …`), Oberflächentexte englisch + `i18n/de.po`; **pre-commit**, Odoos **`test_lint`** und **odoo-ls** (Parse-Modus,
  `docs/pruefautomatik_2026-10-02.md`) müssen grün sein; keine GitHub Action;
  Migrationsskripte mit `odoo/upgrade-util`. Bestehende Module nicht umformatieren.
  Kommentare: Hausregeln in Abschnitt 8 der Coding Guidelines (Warum statt Was, keine Kürzel/Verweise auf Dokumente, kurze Docstrings wie im Odoo-Kern, Odoo-Stellen
  per Funktionsname statt Zeilennummer).

- **Claims immer verifizieren**, nie "sollte sicher funktionieren" — im Code nachsehen,
  live testen, nicht raten.
- **Produktentscheidungen vorab mit dem Nutzer klären**, nicht impliziten Annahmen folgen.
- **int_filemanager:** Der Code ist maßgeblich; Projektbeschreibung: `README.md`.
  `int_filemanager` wird nur auf dem Branch `feature/int-filemanager-v2` entwickelt. Prüfungen:
  pre-commit (`py -3.13 -m pre_commit`, Hook installiert) und `tools/v2check/v2check.sh [--quick]` (odoo-ls + `test_lint`,
  `docs/pruefautomatik_2026-10-02.md`).
- `odoo shell` / `odoo -u` gegen die Watcher-DB startet einen zweiten Watcher. Workaround:
  vorher `int_filemanager.watcher_enabled` auf `false`, danach zurück auf `true` (der laufende Server prüft den
  Schalter nur beim Start, sein Watcher läuft weiter).
