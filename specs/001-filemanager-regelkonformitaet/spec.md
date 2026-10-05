# Feature Specification: int_filemanager erfüllt die verbindlichen Regeln, und die Prüfautomatik erzwingt sie

**Feature Branch**: `feature/int-filemanager-v2` (kein eigener Branch; Modul
`int_filemanager` 19.0.1.23.0)

**Created**: 2026-10-04

**Status**: Draft

**Input**: User description: "Prüfe das Odoo-Filemanager-Repo nur mit Bezug auf
docs/Regeln, Odoo- und Owl-Referenzen und Prüfautomatik, die restlichen Markdown-Dateien
ignorieren. Speckit sauber für dieses Repo aufsetzen und vollständig danach laufen
lassen."

## Umfang

**Maßgebliche Quellen:** die verbindlichen Regeln (`CLAUDE.md`, `docs/odoo_regeln/`),
die Odoo-19-Referenz (`docs/odoo19_reference/`) und der Odoo-Core im Image, die
Owl-2.8.4-Referenz (`docs/owl2_reference/`) und die Prüfautomatik
(`docs/pruefautomatik_2026-10-02.md` mit Konfiguration und Werkzeugen). **Nicht Teil
dieser Spezifikation:** Funktionen und Grundregeln des Dateimanagers (Stand-,
Entscheidungs- und Ideenkatalog-Dokumente, README); sie gelten als gegeben.

**Ausgangslage (Prüfung vom 2026-10-04, Vorarbeit:
`speckit-liedanzeige/specs/008-int-filemanager-regelpruefung/analysis.md`, außerhalb
dieses Repos):** Alle Prüfwerkzeuge laufen ohne neuen Befund. Offen sind: 12 geänderte
Altdateien entgehen der Prüfung, ein Prüfwerkzeug bricht unter Windows ab, einige Regeln
erkennt kein Werkzeug, das Dokument zur Prüfautomatik ist veraltet, eine Regel der
Quelle ist überholt, und im neuen Code gibt es 7 Abweichungen von Hausregeln (davon 2
mit Laufzeitfolgen).

## Clarifications

### Session 2026-10-04

- Q: Wie werden die 12 in diesem Branch geänderten Altdateien behandelt? → A: Ganze
  Datei prüfen (gelten als neu geschrieben)
- Q: Wie sollen Browser-Tests aussehen? → A: Alles nach Odoo-Regel mit Hoot (plus Tour);
  die 75 Node-Testfälle werden nach Hoot übernommen
- Q: Was passiert mit den vom Schema abweichenden XML-IDs? → A: Alle umbenennen, mit
  Migrationsskript
- Q: Neue Prüfungen: Commit stoppen oder nur warnen? → A: Stoppen (blockierend wie die
  bestehenden Pflichtprüfungen)
- Q: Commit-Zeile automatisch prüfen? → A: Ja; Tag-Liste streng nach Odoo-Git-Regeln,
  `[DOC]` nicht erlaubt

## User Scenarios & Testing _(mandatory)_

### User Story 1 - Ein Regelverstoß fällt vor dem Commit auf (Priority: P1)

Wer Code zu `int_filemanager` schreibt, bekommt beim Commit jeden Verstoß gegen eine
maschinell prüfbare Regel gemeldet, lesbar und mit Fundstelle. Das gilt für jede Datei,
die in diesem Branch neu geschrieben oder geändert wurde, auch für ursprünglich alte
Dateien.

**Why this priority**: Eine Regel, die niemand erzwingt, bleibt Absicht. Heute entgehen
der Prüfung 12 geänderte Altdateien und mehrere Regelarten.

**Independent Test**: Ein Probemodul mit je einem Verstoß jeder als prüfbar geführten
Regel läuft durch die Prüfautomatik; jeder Verstoß wird gemeldet, auch auf dem
Windows-Arbeitsrechner.

**Acceptance Scenarios**:

1. **Given** eine Altdatei, die seit dem Basis-Stand geändert wurde, **When** committet
   wird, **Then** wird sie geprüft oder ihre geänderten Zeilen werden geprüft, und die
   Prüfung meldet Verstöße.
2. **Given** ein Verstoß, den bisher kein Werkzeug erkennt (veraltete Aufrufe wie
   `_context`/`_uid`, zusammengeklebte Listen-Domains, `<tree>`/`attrs`/`t-raw` in XML,
   Standardwerte im Manifest), **When** committet wird, **Then** wird er gemeldet.
3. **Given** ein Verstoß, **When** die Meldung auf dem Windows-Arbeitsrechner erscheint,
   **Then** ist sie vollständig lesbar und bricht nicht ab.

---

### User Story 2 - Wer prüft was, ist nachlesbar (Priority: P1)

Wer reviewt oder plant, findet an einer Stelle, welche Regel von welchem Werkzeug
geprüft wird, welche nur per Review, und wie man die Prüfungen aufruft. Das Dokument zur
Prüfautomatik stimmt mit der Konfiguration und mit `CLAUDE.md` überein.

**Why this priority**: Das Regelwerk umfasst 17 Dateien; ohne Übersicht ist eine
vollständige Prüfung nicht wiederholbar. Das heutige Dokument kennt vier vorhandene
Prüfwerkzeuge nicht und widerspricht `CLAUDE.md`.

**Independent Test**: Für jede Regel des Regelwerks ist in der Übersicht ein Prüfweg
genannt; jedes im Repo vorhandene Prüfwerkzeug taucht im Dokument auf; ein Abgleich
Dokument gegen Konfiguration zeigt keine Abweichung.

**Acceptance Scenarios**:

1. **Given** eine Regel aus `docs/odoo_regeln/`, **When** man in der Übersicht
   nachsieht, **Then** steht dort Werkzeug oder "Review" mit Checklistenpunkt.
2. **Given** das Prüfautomatik-Dokument, **When** man es mit Konfiguration und
   `CLAUDE.md` vergleicht, **Then** widersprechen sich Aufruf, Zahlen und Werkzeugliste
   nicht.

---

### User Story 3 - Der neue Code hält die Hausregeln ein (Priority: P2)

Der neue Code von `int_filemanager` weicht von keiner Regel der Destillate und der
Hausregeln mehr ab, oder die Abweichung ist begründet festgehalten. Zwei Abweichungen
wirken sich zur Laufzeit aus: rohes SQL ohne die vorgeschriebene Form und fehlende
Unterdrückung von Follower-Einträgen am Knoten, die bei einer Bestandsübernahme von rund
209.000 Bildern unnötige Datensätze erzeugen.

**Why this priority**: Die Regeln sind für neuen Code verbindlich; die Folgen sind
klein, aber sie summieren sich bei der geplanten Übernahme.

**Independent Test**: Die Werkzeuge und die Review-Suche aus Story 2 laufen ohne
Abweichung; ein Test belegt, dass eine hochgeladene Datei keinen Follower-Eintrag
erzeugt.

**Acceptance Scenarios**:

1. **Given** eine neu angelegte Datei oder ein neuer Ordner, **When** der Eintrag
   entsteht, **Then** entsteht kein Follower-Datensatz für den Nutzer.
2. **Given** die Modelle mit rohem SQL, **When** der Code geprüft wird, **Then** nutzt
   jede Abfrage die vorgeschriebene SQL-Form oder ist als Ausnahme begründet.
3. **Given** ein Browser-Aufruf im JS-Code (Timer, Netzwerk, neues Fenster), **When**
   der Code geprüft wird, **Then** läuft er über das Browser-Objekt von Odoo oder ist
   als Ausnahme begründet.

---

### User Story 4 - Das Regelwerk stimmt mit den Referenzen überein (Priority: P2)

Jede Regel der 17 Destillate ist gegen die lokale Odoo-19- oder Owl-2.8.4-Referenz und
den Core geprüft; überholte oder zu ergänzende Regeln sind korrigiert.

**Why this priority**: Der Index nennt die Destillate "nicht gegenvalidiert", sie gelten
aber als verbindlich. Eine falsche Regel erzeugt falsche Prüfungen. Bekannt: die Regel
"JS-Code ES2019-kompatibel" ist überholt, und die Aussage zu `t-out` gegenüber `t-esc`
gilt für Owl-Templates nicht.

**Independent Test**: Eine Prüfliste führt jede Regel mit Fundstelle in Referenz oder
Core und dem Ergebnis "stimmt", "überholt" oder "ergänzen".

**Acceptance Scenarios**:

1. **Given** eine Regel des Regelwerks, **When** sie gegen Referenz und Core gelegt
   wird, **Then** ist das Ergebnis mit Fundstelle festgehalten.
2. **Given** eine überholte Regel, **When** die Prüfung abgeschlossen ist, **Then** ist
   sie im Destillat korrigiert und das Prüfdatum aktualisiert.

---

### User Story 5 - Die Oberfläche wird nach Odoo-Regel getestet (Priority: P3)

Der Browser-Code wird mit den Werkzeugen getestet, die das Regelwerk vorschreibt (Hoot,
Tour), und die Tests laufen automatisch im Prüflauf. Die Prüfung der Owl-Templates deckt
alle Templates des Moduls ab, und die Statikprüfung des JS-Codes meldet echte Warnungen,
nicht Dauerrauschen.

**Why this priority**: Das Regelwerk verlangt Hoot-Tests; das Modul nutzt bisher nur
Node-Tests. Die Template-Prüfung lässt 5 von 24 Templates aus, und 108 Warnungen
verdecken echte.

**Independent Test**: Die Template-Prüfung meldet 24 von 24 Templates; die Statikprüfung
meldet keine Warnung ohne Handlungsbedarf; die 75 Testfälle laufen als Hoot-Tests im
Prüflauf.

**Acceptance Scenarios**:

1. **Given** die Hoot-Tests und eine Tour, **When** der Prüflauf auf der Testinstanz
   läuft, **Then** laufen sie automatisch und alle Testfälle der bisherigen Node-Tests
   sind enthalten.
2. **Given** die Template-Prüfung, **When** sie läuft, **Then** übersetzt sie alle
   Templates des Moduls, auch die im Unterordner `properties/`.
3. **Given** die Statikprüfung, **When** sie läuft, **Then** erzeugt der Odoo-eigene
   Kopfkommentar `@odoo-module` keine Warnung.

---

### Edge Cases

- Eine Altdatei wurde nur um eine Zeile geändert (kleine Änderung, großer Altbestand):
  die Prüfung darf nicht die ganze Altlast als neuen Befund melden.
- Ein Prüfwerkzeug findet nichts, weil die Datei nicht im Manifest steht: das darf nicht
  als "geprüft" gelten.
- Eine Regel erkennt ein Werkzeug nur unter anderem Namen als im Dokument: Dokument und
  Konfiguration müssen denselben Namen führen.
- Eine Regel ist laut Referenz richtig, widerspricht aber der Praxis des Odoo-Cores
  (ES2019): der Core im Image entscheidet.
- Das Umbenennen einer XML-ID würde bestehende Installationen berühren (externe IDs in
  der Datenbank).
- Ein Commit-Hinweis auf Dokumentation darf nicht `[DOC]` heißen; die Regel greift nur
  für neue Commits.
- Ein Prüflauf auf dem Arbeitsrechner darf keine Dateien umschreiben (`--all-files`
  bleibt verboten).
- Das Format der 12 Altdateien umzustellen ändert viele Zeilen; das darf die Historie
  nicht unlesbar machen (eigener Schritt vor inhaltlichen Änderungen).
- Hoot-Tests brauchen einen Browser im Prüflauf; ist er im Test-Image nicht vorhanden,
  muss das vor der Umsetzung geklärt sein.
- Das Migrationsskript für die Umbenennung läuft auf Datenbanken mit unterschiedlichem
  Stand (frisch, Test) und darf bei fehlenden Einträgen nicht abbrechen.

## Requirements _(mandatory)_

### Functional Requirements

**Durchsetzung**

- **FR-001**: Jede Datei von `int_filemanager`, die seit dem Basis-Stand
  `int_filemanager-v1` neu oder geändert ist, MUSS von der Commit-Prüfung erfasst
  werden; der Ausnahme-Block darf nur unverändert gebliebene Altdateien nennen, und das
  Werkzeug zum Pflegen des Blocks MUSS einen Verstoß dagegen melden.
- **FR-002**: Die 12 in diesem Branch geänderten Altdateien MÜSSEN künftig als neu
  geschrieben gelten und als ganze Datei geprüft werden (Entscheidung des Nutzers
  2026-10-04); ihre Altbefunde (heute 51 blockierende pylint-Befunde, 4 Zeilenlängen bei
  120 Zeichen, Format- und Prettier-Änderungen) MÜSSEN behoben sein, ohne dass dabei
  Verhalten ändert; reine Formatierung kommt als eigener Schritt vor inhaltlichen
  Änderungen.
- **FR-003**: Die Commit-Prüfung MUSS auf dem Windows-Arbeitsrechner jede Meldung
  vollständig ausgeben; die dafür nötige Einstellung MUSS festgelegt und dokumentiert
  sein.
- **FR-004**: Folgende Regelverstöße MÜSSEN von der Prüfautomatik gemeldet werden und
  den Commit stoppen (blockierend, nicht nur Warnung): veraltete Aufrufe
  `_cr`/`_context`/`_uid`, zusammengeklebte Listen-Domains,
  `<tree>`/`attrs`/`states`/`t-raw` in XML, Schlüssel mit Standardwert im Manifest,
  Parameter `ids`/`context` an öffentlichen Methoden.
- **FR-019**: Die Kopfzeile jedes Commits MUSS `[TAG] modul: kurzer Satz` mit einem Tag
  der Odoo-Git-Regeln (`[DOC]` ist nicht erlaubt), Imperativ und höchstens 80 Zeichen
  folgen; ein Verstoß MUSS den Commit stoppen. Frühere Commits bleiben unberührt.
- **FR-005**: Ein Probemodul mit je einem Verstoß jeder prüfbaren Regel MUSS als
  wiederholbarer Beleg in `tools/` liegen, und alle Verstöße MÜSSEN gemeldet werden.
- **FR-006**: Die Template-Prüfung MUSS alle Owl-Templates des Moduls erfassen.
- **FR-007**: Die Statikprüfung des JS-Codes MUSS ohne Dauerwarnungen laufen: der
  Odoo-eigene Tag `@odoo-module` ist erlaubt, und für Importreihenfolge und
  Inline-Kommentare steht fest, ob sie durchgesetzt oder abgeschaltet sind.

**Dokumentation**

- **FR-008**: Das Prüfautomatik-Dokument MUSS alle vorhandenen Prüfwerkzeuge nennen
  (pre-commit, `test_lint`, odoo-ls, `jscheck`, `owlcheck`, `tests.sh`, `race.sh`,
  Node-Tests), den Aufruf mit `--files` statt `--all-files` zeigen, aktuelle Zahlen und
  den Verifikationsstand für Windows tragen und mit `CLAUDE.md` übereinstimmen.
- **FR-009**: Eine Prüfübersicht MUSS zu jeder Regel des Regelwerks Werkzeug oder
  Review-Checklistenpunkt nennen.
- **FR-010**: Jede Regel der 17 Destillate MUSS gegen Referenz und Core geprüft und das
  Ergebnis mit Fundstelle festgehalten sein; überholte Regeln MÜSSEN korrigiert und
  Prüfdatum und Quell-Hash aktualisiert sein.
- **FR-011**: Browser-Tests MÜSSEN nach der Odoo-Regel aufgebaut sein (Entscheidung des
  Nutzers 2026-10-04): Hoot-Tests (`*.test.js`, Bundle `web.assets_unit_tests`) für
  Logik und Komponenten und mindestens eine Tour für den Ablauf Server–Client; jeder der
  heute 75 Node-Testfälle MUSS als Hoot-Testfall erhalten bleiben, und die Hoot-Tests
  MÜSSEN im Prüflauf auf der Testinstanz automatisch laufen.

**Code**

- **FR-012**: Neu angelegte Knoten MÜSSEN ohne Follower-Eintrag und ohne Wert-Verfolgung
  entstehen; ein Test MUSS das belegen.
- **FR-013**: Rohes SQL im neuen Code MUSS die vorgeschriebene SQL-Form nutzen
  (Parameter, kein String-Bau); Flush und Invalidate MÜSSEN so spezifisch wie möglich
  sein.
- **FR-014**: Speicher und Navigation im JS-Code (`localStorage`, `sessionStorage`,
  `location`, `history`, `navigator`) MÜSSEN über das Browser-Objekt von Odoo laufen;
  `setTimeout`, `fetch` und DOM-Zugriffe sind frei (heute erfüllt).
- **FR-015**: Die Ausnahmen von Regeln (Commit auf dem Cron-Cursor im Blob-GC, breite
  Ausnahmefänger im Cron) MÜSSEN im Regelwerk oder am Code begründet sein.
- **FR-016**: Manifest: `external_dependencies` MUSS die nicht im Image vorhandenen
  Pakete nennen (`installable: True` ist erlaubt).
- **FR-017**: Die Tests MÜSSEN Odoos Hilfen für Testnutzer verwenden statt eigener
  Kopien; Hilfsskripte gehören nicht in das Modulverzeichnis `tests/`.
- **FR-018**: Die XML-IDs aller Views, Aktionen und Zugriffsregeln des neuen Codes
  MÜSSEN dem Schema der Regeln folgen (Entscheidung des Nutzers 2026-10-04: alle
  umbenennen); ein Migrationsskript MUSS dafür sorgen, dass jede Instanz mit dem
  Branch-Stand (heute die Testinstanz auf Tower) ihre Einträge behält, und ein Test MUSS
  die Umbenennung auf einer bestehenden Datenbank belegen.

### Key Entities

- **Regel**: verbindliche Aussage des Regelwerks mit Quelle, Prüfweg (Werkzeug oder
  Review) und Ergebnis.
- **Prüfwerkzeug**: pre-commit, `test_lint`, odoo-ls, `jscheck`, `owlcheck`, Node-Tests,
  Probemodul.
- **Basis-Stand**: das Tag `int_filemanager-v1`; alles danach ist neuer Code.
- **Altbestand (Ausnahme-Block)**: Dateien, die vom Prüfen ausgenommen sind, weil sie
  unverändert Altbestand sind.
- **Prüfübersicht**: Zuordnung Regel → Prüfweg.

## Success Criteria _(mandatory)_

### Measurable Outcomes

- **SC-001**: 0 der seit dem Basis-Stand geänderten oder neuen Dateien entgehen der
  Commit-Prüfung (heute: 12 von 19 geänderten Altdateien).
- **SC-002**: Das Probemodul meldet 100 % seiner Verstöße (heute 18 von 24) und alle
  Meldungen sind auf dem Windows-Arbeitsrechner vollständig lesbar.
- **SC-003**: Jede der Regeln des Regelwerks hat in der Prüfübersicht einen Prüfweg; 0
  Regeln ohne Zuordnung.
- **SC-004**: Das Prüfautomatik-Dokument enthält 0 Abweichungen gegenüber Konfiguration
  und `CLAUDE.md` (heute 4 Abweichungsgruppen).
- **SC-005**: 100 % der Regeln der 17 Destillate sind gegen Referenz oder Core belegt
  (heute 8 Stichproben).
- **SC-006**: Die Template-Prüfung erfasst 24 von 24 Templates (heute 19); die
  Statikprüfung meldet höchstens die Warnungen, die als Handlungsbedarf gelten (heute
  108).
- **SC-007**: Der Upload einer Datei erzeugt 0 Follower-Datensätze (heute 1 je Knoten).
- **SC-008**: Alle Prüfwerkzeuge (pre-commit, `v2check`, `jscheck`, `owlcheck`,
  Hoot-Tests, Odoo-Tests) laufen nach der Änderung ohne neuen Befund und ohne Rückgang
  der heute 645 Odoo-Tests und der 75 Testfälle der bisherigen Node-Tests.
- **SC-009**: 100 % der XML-IDs des neuen Codes folgen dem Schema; ein Lauf des
  Migrationsskripts auf einer Kopie einer bestehenden Datenbank verliert 0 Einträge.

## Assumptions

- Die Regeldokumente beschreiben die Absicht des Nutzers; bei Widerspruch zwischen
  Destillat und Odoo gilt der Odoo-Core im Image.
- Alter Code außerhalb der in diesem Branch geänderten Dateien und alle anderen Module
  (`onlyoffice_odoo`, `int_generic` …) sind nicht Teil dieser Spezifikation.
- Die Prüfläufe laufen gegen die Testinstanz auf Tower in Wegwerf-Containern; die
  Live-Instanz bleibt unberührt.
- Commits macht der Nutzer; diese Spezifikation löst keinen aus.
- Die Oberfläche testet der Nutzer selbst im Browser; hier zählt nur, was statisch und
  per Node-Test prüfbar ist.
- Umbenennungen, die installierte Instanzen berühren, brauchen ein Migrationsskript; die
  Regel verlangt dafür `odoo/upgrade-util`, das im Image nicht enthalten ist
  (Abhängigkeit, im Plan zu klären).
- Ein Browser für Hoot-Tests im Prüflauf ist Abhängigkeit und im Plan zu klären
  (Constitution I: erst im Image und im Core nachsehen).
