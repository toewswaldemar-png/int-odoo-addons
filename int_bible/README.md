# int_bible

Die Bibel im Odoo lesen und durchsuchen: mehrere Übersetzungen nebeneinander in einer Liste, Navigation Testament > Buch > Kapitel über das native Searchpanel, Suche nach Wörtern und Stellen, Lesezeichen und eigene Notizen. **Status: Grundgerüst, noch keine Funktion.**

## Plan

Der Entwurf mit Odoo-Fundstellen, Datenmodell, Zielstruktur und Phasen steht in [`docs/int_bible/plan.md`](../docs/int_bible/plan.md). Den Einstieg für die Umsetzung (Entscheidungen, offene Punkte, Schritte S1 bis S8) gibt [`docs/int_bible/uebergabe.md`](../docs/int_bible/uebergabe.md).

## Kurzfassung

- Positionsmodell: eine Stelle (z. B. Joh 3,16) mit einem Text je Übersetzung; Lesezeichen, Notizen und später Querverweise hängen an der Stelle.
- Ansicht: Liste mit Searchpanel, zwei Textspalten (zwei weitere einblendbar), kein eigenes JavaScript im ersten Wurf.
- Bibeltexte liegen nicht im Repo; sie werden über einen Import-Assistenten aus Dateien geladen (zuerst gemeinfreie Fassungen von eBible.org im Format USFX).
- Später: Querverweise (Phase 2), Bibellesepläne (Phase 3), Anbindung an `int_presenter` (Phase 4).
