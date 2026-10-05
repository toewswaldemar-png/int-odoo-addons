# Feature Specification: Ordnerbaum aus Odoo-Bausteinen, Teil für Teil geprüft

**Feature Branch**: `feature/int-filemanager-v2` (Spec-Ordner
`002-ordnerbaum-bausteine`)

**Created**: 2026-10-04

**Status**: Draft (Prüfung abgeschlossen in `research.md`, Entscheidungen offen)

**Input**: "Prüfe nach Speckit, aus welchen einzelnen Teilen ein Ordnerbaum gebaut
werden kann."

## Umfang

Gegenstand ist der Ordnerbaum links im Dateimanager (`v2/folder_tree.js`,
`folder_tree.xml`, Server: `tree_children`, `breadcrumb`) und seine Einbettung. Quellen
für das Soll: Constitution Grundsatz I (Odoo-Core vor Eigenbau, fünf Suchraster-Punkte),
die Odoo-19-Regeln in `docs/odoo_regeln/` und die Referenzen. Nicht Gegenstand:
Funktionen des Dateimanagers außerhalb des Baums, Regelkonformität des Codes (Spec
`001`).

## User Scenarios & Testing _(mandatory)_

### User Story 1 - Jedes Teilstück des Baums hat eine belegte Antwort (Priority: P1)

Wer den Baum plant, ändert oder prüft, sieht für jedes Teilstück (Hierarchie speichern,
Ebene laden, Zustand halten, darstellen, auswählen, Tastatur, Größe, Handy, Verschieben,
Hochladen per Ziehen, Kontextmenü, Zähler, Aktualisieren, Rechte) drei Dinge: welche
Odoo-Bausteine es dafür gibt (mit Fundstelle im Core), welchen der Baum heute nutzt, und
ob ein Eigenbau begründet ist.

**Why this priority**: Grundsatz I verlangt das vor jeder Eigenbau-Aussage; bisher stand
nur die Begründung für den Baum als Ganzes im Code.

**Independent Test**: Für jedes der 17 Teilstücke in `research.md` stehen Kandidaten mit
Fundstelle, Ist-Zustand und Urteil; kein Urteil lautet "unbekannt".

**Acceptance Scenarios**:

1. **Given** ein Teilstück des Baums, **When** man in `research.md` nachsieht, **Then**
   stehen dort mindestens ein Kandidat mit Datei im Core oder die Aussage "kein
   Baustein" mit Suchbeleg.
2. **Given** ein Urteil "Eigenbau begründet" mit Zahlenbehauptung, **When** die
   Behauptung nachgemessen wird, **Then** liegt das Messergebnis bei.

---

### User Story 2 - Der Baum ist mit Tastatur bedienbar und für Hilfsprogramme lesbar (Priority: P2)

Nutzer navigieren im Baum mit Pfeiltasten, öffnen und schließen Ordner mit Rechts und
Links und wählen mit Enter; Hilfsprogramme erkennen Ebene und Auf-/Zugeklapptstatus
jedes Ordners.

**Why this priority**: Die Prüfung zeigt, dass diese Teile heute fehlen, obwohl der Core
dafür Bausteine hat (Navigation, ARIA-Muster im Export-Dialog).

**Independent Test**: Ein Hoot-Test bedient den Baum nur mit der Tastatur; die Knoten
tragen Rolle, Ebene und Zustand.

**Acceptance Scenarios**:

1. **Given** der Baum hat den Fokus, **When** Pfeil-runter und Rechts gedrückt werden,
   **Then** wird der nächste Ordner markiert und ein geschlossener Ordner mit
   Unterordnern geöffnet.
2. **Given** ein Ordner mit Unterordnern, **When** ein Hilfsprogramm ihn liest, **Then**
   nennt es Ebene und "aufgeklappt" oder "zugeklappt".

---

### User Story 3 - Der Baum bleibt bei sehr breiten Ebenen schnell (Priority: P3)

Auch ein einzelner Ordner mit mehreren tausend Unterordnern öffnet ohne Verzögerung,
weil nur sichtbare Zeilen gezeichnet werden.

**Why this priority**: Das Laden pro Ebene ist gemessen schnell (6 bis 9 ms bei 70.446
Ordnern, Ebenen mit 40 Kindern); die Darstellung sehr breiter Ebenen ist nicht gemessen,
der Core hat dafür `useVirtualGrid`.

**Independent Test**: Messung mit einer Ebene von 5.000 Unterordnern; Öffnen unter 200
ms Darstellungszeit.

**Acceptance Scenarios**:

1. **Given** ein Ordner mit 5.000 Unterordnern, **When** er geöffnet wird, **Then**
   erscheint die Liste in unter 200 ms und scrollt flüssig.

---

### Edge Cases

- Ordner, die der Nutzer nicht lesen darf, tauchen im Baum nicht auf (Serverrechte,
  nicht Sache der Oberfläche).
- Ein Ordner wird in einer anderen Sitzung gelöscht oder verschoben, während er im Baum
  offen ist.
- Sehr tiefe Ordnerketten (mehr als 20 Ebenen) und sehr lange Namen.
- Handy: Zurück-Taste während der Ordnerbaum offen ist.
- Mehrere Ordner derselben Ebene, die sich nur in Groß-/Kleinschreibung unterscheiden.

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: Für jedes Teilstück des Baums MUSS `research.md` Kandidaten-Bausteine mit
  Fundstelle im Odoo-19-Core, den Ist-Zustand und ein Urteil enthalten (Grundsatz I).
- **FR-002**: Jede Zahlenbehauptung, die einen Eigenbau begründet, MUSS gemessen und mit
  Messbedingungen belegt sein.
- **FR-003**: Der Baum MUSS Tastaturbedienung bieten (Pfeile, Rechts/Links zum Öffnen
  und Schließen, Enter) [NEEDS CLARIFICATION: Soll der Baum denselben Tastaturbaustein
  nutzen wie die Liste (`useNavigation`) oder ein eigenes Muster nach dem Export-Dialog
  des Cores?].
- **FR-004**: Jeder Knoten MUSS Rolle, Ebene und Auf-/Zugeklapptstatus für
  Hilfsprogramme tragen (`role="treeitem"`, `aria-level`, `aria-expanded`).
- **FR-005**: Das Öffnen einer Ebene MUSS unabhängig von der Gesamtzahl der Ordner
  schnell bleiben (gemessen heute: 6 bis 9 ms bei 70.446 Ordnern).
- **FR-006**: Die Baum-Icons MÜSSEN der Icon-Regel des Regelwerks folgen (FontAwesome
  als Standard, `oi`-Icons nur für Lücken;
  `docs/odoo_regeln/odoo_regeln_ui_icons_scss_2026-10-02.md`). Der Baum erfüllt das
  heute mit `fa-caret-*` und `fa-folder`; der Export-Baum des Cores nutzt
  `oi-chevron-*`, ein Wechsel ist nur optisch.
- **FR-007**: Am Handy MUSS die Zurück-Taste den geöffneten Baum schließen, nicht die
  Seite verlassen [NEEDS CLARIFICATION: Soll der Baum dafür den Core-Baustein
  `bottom_sheet` nutzen, oder genügt eine eigene Behandlung von `popstate`?].
- **FR-008**: Verschieben per Ziehen auf einen Baumknoten MUSS erhalten bleiben; ob
  dafür ein Core-Baustein (`useDraggable`, `useNestedSortable`, das Muster aus
  `web_hierarchy`) eingesetzt wird, ist im Plan zu entscheiden [NEEDS CLARIFICATION: Ist
  der Aufwand eines Umbaus von rohem Drag & Drop auf Core-Hooks gewünscht, oder bleibt
  der Eigenbau begründet bestehen?].
- **FR-009**: Der alte Ordnerbaum (`native_ui/folder_tree.js`) MUSS entweder entfernt
  oder als noch benutzt belegt sein.

### Key Entities

- **Teilstück**: eine abgrenzbare Aufgabe des Baums (Laden, Zustand, Darstellung …).
- **Baustein**: eine Komponente, ein Hook, ein Dienst oder eine Server-Methode des
  Odoo-Cores.
- **Urteil**: `nativ genutzt`, `nativ möglich, nicht genutzt`, `Eigenbau begründet`,
  `Eigenbau offen`.

## Success Criteria _(mandatory)_

### Measurable Outcomes

- **SC-001**: 17 von 17 Teilstücken haben Kandidaten, Ist-Zustand und Urteil (heute 17
  von 17 in `research.md`).
- **SC-002**: 0 Urteile "unbekannt"; jede Zahlenbehauptung hat ein Messergebnis (heute:
  1 gemessen, 70.446 Ordner).
- **SC-003**: Der Baum ist vollständig mit der Tastatur bedienbar (0 Aktionen, die nur
  mit der Maus gehen) und jeder Knoten trägt Ebene und Zustand.
- **SC-004**: Das Öffnen einer Ebene mit 5.000 Unterordnern dauert unter 200 ms.
- **SC-005**: Es gibt genau einen Ordnerbaum im ausgelieferten Code (heute 2, siehe
  FR-009).

## Assumptions

- Maßgeblich ist der Odoo-19-Core im Image `odoo:19.0-hm-test` auf Tower;
  Referenz-Dokumentation ist autodoc-arm, der Quelltext entscheidet.
- Es gilt der Community-Umfang; Enterprise-Bausteine (z. B. Documents) stehen nicht zur
  Verfügung.
- Die Messung gilt für die Serverseite (Datenbank und Python); Übertragung und Aufbau im
  Browser sind nicht gemessen.
- Entscheidungen, die die Bedienung ändern (Tastatur, Handy-Verhalten, Umbau des
  Ziehens), trifft der Nutzer (Grundsatz VI).
