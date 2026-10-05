<!--
Sync Impact Report
Version change: 1.0.0 → 1.0.1 (PATCH: Zeilenlänge)
Modified principles: keine; Zusätzliche Vorgaben: Zeilenlänge 120 ergänzt
Added sections: Core Principles I–VII, Zusätzliche Vorgaben, Arbeitsablauf, Governance
Removed sections: keine
Follow-up TODOs: keine; Quellen sind CLAUDE.md, docs/odoo_regeln/, docs/pruefautomatik_2026-10-02.md
-->
# int-odoo-addons Constitution

Geltungsbereich: alle Module dieses Repos, vorrangig `int_filemanager` (Branch `feature/int-filemanager-v2`). Abgeleitet aus `CLAUDE.md`,
`docs/odoo_regeln/`, den lokalen Referenzen `docs/odoo19_reference/` und `docs/owl2_reference/` sowie `docs/pruefautomatik_2026-10-02.md`.
Bei Widerspruch gilt die Odoo-Quelle vor dem Destillat, das Destillat vor der Annahme.

## Core Principles

### I. Odoo-Core vor Eigenbau (NON-NEGOTIABLE)
Nie "gibt es in Odoo nicht" oder "müssen wir selbst bauen" behaupten, ohne den Odoo-19-Core geprüft zu haben. Das Suchraster hat fünf Punkte, alle sind
zu durchlaufen: Core-Grep im Container (`/usr/lib/python3/dist-packages/odoo/`), vergleichbare Odoo-Module (`documents`, `mail`, `project`, `hr`),
im Image vorhandene Bibliotheken, Odoo-Feld- und Modell-Defaults (`active`, `ir.rule`, `res.groups`, `mail.thread`, `image.mixin`, `@api.autovacuum`,
`@api.ondelete`), kurze empirische Bestätigung. Der Plan nennt zu jedem Baustein die Fundstelle. Grund: die Aussage "kein Bordmittel" war mehrfach falsch.

### II. Odoo-19-Regeln einhalten
Neuer Code verletzt die Regeln in `docs/odoo_regeln/` nicht (Coding Guidelines, Git Guidelines, ORM, Sicherheit, Performance, Daten und Manifest, Aktionen/Cron/HTTP,
Views, QWeb, Tests, Mixins) und die Hausregeln aus Abschnitt 8 der Coding Guidelines. Bei API-Unsicherheit wird in `docs/odoo19_reference/` oder im Core
nachgeschlagen, nicht aus dem Gedächtnis geschrieben. Bestehender Code wird nicht umformatiert; größere Umstellungen erst als reiner Verschiebe-Commit.
Wo ein Destillat der Odoo-Quelle widerspricht, wird das Destillat korrigiert.

### III. Owl 2.8.4 und das Odoo-JS-Framework
Odoo 19 liefert Owl 2.8.4 mit; für Owl-Code gilt nur `docs/owl2_reference/`. Die Online-Doku zu Owl 3 (Signals, Plugins, Effects, Computed Values) gilt für
Odoo 19 nicht. Neuer JS-Code nutzt native ES-Module, `setup()` statt `constructor`, `static template` und `static props`, Dienste über `useService`
(`orm` für Modelle, `rpc` nur für Controller), Browser-Funktionen über `@web/core/browser/browser` und Patches nur, wo kein Registry-Punkt reicht.

### IV. Die Prüfautomatik erzwingt, was prüfbar ist
Jede maschinell prüfbare Regel gehört in die Prüfkonfiguration, nicht nur in Prosa. pre-commit (OCA-Vorlage, nur neuer Code, bei jedem Commit) und
`tools/v2check/v2check.sh` (`test_lint` und odoo-ls auf Tower, einmal vor dem Commit bei Änderungen an Python, XML, Manifest oder i18n) müssen ohne neuen
Befund laufen. Regeln ohne Werkzeug bleiben ausdrücklich als Review-Checkliste geführt. Nie `pre-commit run --all-files` im Arbeitsbaum (die Hooks schreiben
Dateien um); nur `pre-commit run` (staged) oder `--files <Datei>`. Altdateien im LEGACY-Block sind nur solange ausgenommen, wie sie unverändert Altbestand sind.

### V. Verifizieren statt vermuten
Jede Aussage über Verhalten wird im Code oder live geprüft, nie "sollte sicher funktionieren". Behauptungen werden mit Fundstelle (Datei, Funktionsname)
oder Messwert belegt; nicht Geprüftes wird als solches ausgewiesen.

### VI. Produktentscheidungen vorab klären
Entscheidungen, die Funktionsumfang oder Bedienung ändern, trifft der Nutzer vor dem Plan, nicht die KI per Annahme. Der Nutzer ist kein Programmierer:
Entscheidungen werden in Alltagssprache mit Beispielen und einer klaren Empfehlung vorgelegt und gebündelt gestellt.

### VII. Ursachen beheben, nicht umgehen
Fehler werden im Code an der Ursache behoben, mit einem Test, der ohne die Behebung fehlschlägt. Keine Handeingriffe in Datenbank oder Container
als Ersatz für eine Codebehebung. Neuer Code wird mit möglichst geringen Rechten getestet.

## Zusätzliche Vorgaben

- **Zeilenlänge:** Python 120 Zeichen (`.ruff.toml`), JS und XML nach Prettier (`printWidth` 88).
- **Sprache und Namen:** neuer Code englisch (Namen, Kommentare, Docstrings, Logs, Commits); Oberflächentexte englisch plus `i18n/de.po`. Dateinamen nach dem
  vollen Modellnamen mit Präfix (`int_filemanager_node.py`), Modellnamen mit Modulpräfix im Singular.
- **Kommentare:** Warum statt Was, keine Verweise auf Dokumente oder Kürzel, Odoo-Stellen per Funktionsname statt Zeilennummer, kein auskommentierter Code.
- **Sicherheit:** öffentliche Methoden prüfen Rechte selbst; `sudo()` nie auf Nutzereingaben und an jeder Stelle begründet; rohes SQL nur mit `odoo.tools.SQL`;
  `cr.commit()` nur im selbst geöffneten Cursor und mit Kommentar; kein `eval`, kein `t-raw`.
- **Commits:** `[TAG] modul: kurzer Satz` im Imperativ, Tag aus der Liste der Git Guidelines, nur auf ausdrückliche Ansage des Nutzers.
- **Umgebung:** drei getrennte Unraid-Server (HM-SRV, Tower, Tower 192.168.178.73); nie annehmen, dass ein Stand von einem Server auf einem anderen liegt.
  Prüfläufe nur gegen Wegwerf-Container und -Datenbanken auf der Testinstanz, nie gegen die Live-Instanz.
- **Entwicklung** von `int_filemanager` nur auf dem Branch `feature/int-filemanager-v2`.

## Arbeitsablauf

- Reihenfolge: Spezifikation → Klärung → Plan → Aufgaben → Analyse → Umsetzung. Pläne nennen Fundstellen in den Odoo- und Owl-Referenzen.
- Vor jeder Sitzung mit Code-Änderung: `docs/odoo_regeln/` lesen (Index zuerst); bei Planung zusätzlich beide `INDEX.md` der Referenzen.
- Prüfungen gebündelt am Ende einer Etappe; zwischendurch nur gezielte schnelle Tests. Die Testinstanz auf Tower darf ohne Rückfrage aktualisiert werden.
- Neue Befunde der Prüfwerkzeuge werden gegen die Altbefunde in `docs/pruefautomatik_2026-10-02.md` abgeglichen.

## Governance

Diese Constitution steht über anderen Arbeitsweisen und Plänen; `CLAUDE.md` bleibt die kurze Pflichtfassung und verweist auf sie. Änderungen werden mit
Datum und Begründung festgehalten und nach Semantic Versioning nummeriert (MAJOR: Prinzip entfernt oder umgedeutet; MINOR: Prinzip oder Abschnitt
hinzugefügt; PATCH: Klarstellung). Jede Spezifikation, jeder Plan und jede Analyse prüft die Einhaltung; ein Verstoß gegen ein MUST-Prinzip ist ein
kritischer Befund und wird nicht durch Umdeuten aufgelöst. Abweichungen von den Odoo-Regeln müssen im Plan begründet werden (Abschnitt Complexity Tracking).

**Version**: 1.0.1 | **Ratified**: 2026-10-04 | **Last Amended**: 2026-10-05
