# Übergabe: Modul int_bible (Einstieg für eine neue Sitzung, Stand 24.10.2026)

Diese Datei reicht, um ohne Vorwissen weiterzumachen. Der ganze Entwurf steht in `docs/int_bible_plan.md`. Es gibt noch keinen Code.

## Ziel (ein Satz)

Ein Odoo-19-Modul `int_bible`, mit dem angemeldete Benutzer die Bibel im Odoo lesen (zwei Übersetzungen nebeneinander), durchsuchen, mit Lesezeichen und eigenen Notizen versehen können. Die Navigation Testament > Buch > Kapitel läuft über das native Searchpanel, im ersten Wurf ohne eigenes JavaScript. Querverweise (Phase 2) und Lesepläne (Phase 3) folgen später.

## Wo was liegt

- Dieses Repo: `C:\Users\Admin\Documents\GitHub\int-odoo-addons` (öffentlich). Das Modul entsteht als Ordner `int_bible/` in der Wurzel, neben den anderen Modulen.
- Maßstab ist allein der Odoo-19-Quelltext und die Odoo-19-Doku, in diesem Repo:
  - Quelltext: `docs/odoo` (Branch 19.0, flacher Klon, Stand 01.10.2026, nicht versioniert; vor Beginn mit `git -C docs/odoo pull` auffrischen)
  - Doku: `docs/odoo19_reference/INDEX.md`, Coding-Guidelines: `docs/odoo19_reference/contributing/coding_guidelines.md`
  - Owl: `docs/owl2_reference/INDEX.md`
- Vorbilder im selben Repo: `int_filemanager` (Aufteilung der Modelle nach Themen, Volltextsuche, Import, Tests), `int_liedanzeige` (Manifest, Gruppen, Zugriffsrechte), `int_presenter` (Gerüst, Ziel von Phase 4: Bibelvers auf den Beamer).

## Regeln für die Arbeit (vom Nutzer)

- Der Nutzer ist kein Programmierer: Entscheidungen in Alltagssprache mit Beispiel, eine Empfehlung und eine Entscheidung, Fachbegriffe nur in Klammern.
- Nur committen, wenn der Nutzer es sagt. Keine weiteren `.md`-Dateien ohne Ansage.
- Vor dem ersten Code den Skill `odoo-quellcode-schreiben` laden und die Hinweise des Hooks „Odoo guidelines check“ abarbeiten. Ein Hinweis kann falsch sein: vor dem Befolgen am Richtlinientext prüfen. Die Hooks sind für dieses Repo eingerichtet.
- Odoo-Bausteine nicht nachbauen, erst im Odoo-Core nachsehen (Fundstellen stehen im Plan). Vor dem Überschreiben einer Core-Funktion sie ganz lesen.
- Jede Abweichung vom Plan vorab melden. Zwischendurch nur gezielte, schnelle Tests. Die volle Prüfung einmal vor dem Commit.
- Der Nutzer testet im Browser selbst. Keine Chrome-Erweiterung zum Testen verwenden.
- Keine Bibeltexte und keine Querverweisdaten ins Repo (das Repo ist öffentlich). Texte kommen nur per Import-Assistent aus einer Datei, die der Nutzer freigibt.
- Dateien herunterladen nur nach Rückfrage (Name, Quelle, Größe nennen).

## Schon entschieden (Details in docs/int_bible_plan.md)

- Positionsmodell: `int.bible.verse` ist die Stelle, `int.bible.verse.text` der Text je Übersetzung. Dazu die Zuordnung `int.bible.verse.map` für abweichende Verszählung und ein gespeichertes Feld `ordinal` (fortlaufende Nummer der Stelle) für Bereiche.
- Listenansicht mit `<searchpanel>` (Baum aus `int.bible.section`, `limit="false"`), zwei Textspalten nebeneinander (`text_1`, `text_2`), zwei weitere optional ausgeblendet. Übersetzungswahl je Benutzer über `res.users.settings`.
- Kein JavaScript im ersten Wurf. Ein eigener Lese-Bildschirm nur, wenn die Liste im Alltag nicht reicht.
- Dateiaufteilung nach Themen (siehe Zielstruktur in docs/int_bible_plan.md), englische Quelltexte plus `i18n/de.po`.
- Phase 2: Querverweise (Datensatz von openbible.info, CC BY, per Assistent laden). Phase 3: Bibellesepläne. Phase 4: Verbindung zu `int_presenter`.

## Entscheidungen vom 24.10.2026 (Nutzer: alle Empfehlungen übernommen)

1. **Kapitel:** Das Modul liefert nur 2 Testamente und 66 Bücher als Datei. Die rund 1.189 Kapitel entstehen beim Import der ersten Übersetzung (Referenz-Zählung). Vor dem ersten Import zeigt der Baum nur die Bücher.
2. **Buchkürzel:** Claude erstellt einen Vorschlag (Lutherbibel-Kürzel nach den Loccumer Richtlinien) für alle 66 Bücher, der Nutzer prüft ihn.
3. **Modultrennung für Phase 2 und 3:** wird erst zu Beginn von Phase 2 entschieden. Der erste Wurf ist ein einziges Modul.
4. **Übersetzungswahl:** eigener Menüpunkt „Bibel > Meine Übersetzungen“ (nicht der persönliche Einstellungsdialog). Technische Umsetzung in S5 gegen den Core prüfen.
5. **Testinstanz:** lokaler Tower (`ssh unraid`) mit eigenem Test-Container und eigener Datenbank, nicht im Container `odoo` oder in `odoo_db`.
6. **Textquelle:** eBible.org (Rechtsstatus je Text dort ausgewiesen). Erstes Einlese-Format ist deshalb **USFX** (XML) statt Zefania. Zefania kommt später als zweites Format.

## Noch zu klären (kurz, zu Beginn der neuen Sitzung)

- **Buchkürzel:** Vorschlag liegt noch nicht vor, in S1 erstellen und vom Nutzer prüfen lassen.
- **Textdateien:** Prüfen, ob Luther 1912 (`https://ebible.org/find/details.php?id=deu1912`) und Elberfelder 1905 (`...id=deuelo`) dort wirklich als USFX vorliegen (bei der Recherche nicht einzeln geprüft). Herunterladen nur nach Rückfrage mit Name, Quelle und Größe.
- **Tower:** Zustand und Zugang prüfen (Notizen sind einige Tage alt). Quelle der Angaben: `ssh unraid`, Container `odoo`, Addons unter `/mnt/user/appdata/odoo/extra-addons`; HM-SRV ist von hier nicht erreichbar. Vor dem Anlegen eines Test-Containers kurz beim Nutzer bestätigen.

## Schritte (jeder einzeln abnehmen)

| Schritt | Inhalt | Abnahme |
|---|---|---|
| S1 | Gerüst und Stammdaten: Manifest, Gruppen, Rechte, Modelle `translation` und `section` (nur Bücher und Testamente), Ansichten und Menü für Übersetzungen, Tests | Installation fehlerfrei, Menü für Manager sichtbar, Tests grün |
| S2 | Stelle: `verse`, `verse.text`, `verse.map`, `ordinal`, Constraints, Tests | Tests grün, Eindeutigkeit geprüft |
| S3 | Import: Parser-Schnittstelle, USFX-Parser, `translation_load` (legt Kapitel an), Assistent, Tests mit kleiner Testdatei | Beispieldatei lädt, Abbruch bei kaputter Datei sauber |
| S4 | Schreibweise: „Joh 3,16“ und „Röm 5-8“ lesen und schreiben, Stellensuche | Tests grün |
| S5 | Leseansicht: Liste mit Searchpanel, zwei Textspalten, Überschriften, Übersetzungswahl, Menüs | Nutzer prüft im Browser |
| S6 | Lesezeichen und Notizen mit Rechten | Rechte-Tests grün, Nutzer prüft |
| S7 | Filter, Gruppierungen, mitgelieferte Favoriten, `de.po` | Nutzer prüft |
| S8 | Messung (Searchpanel, Suche, Import bei 31.000 und 155.000 Zeilen), volle Prüfung, Commit auf Ansage | Zahlen im Bericht |

## Schritt S1 im Einzelnen

Ziel: ein installierbares, leeres Gerüst mit den Stammdaten, sonst nichts.

- `int_bible/__init__.py`, `__manifest__.py` (Name, Version `19.0.1.0.0`, `application: True`, `license: LGPL-3`, `depends: ['web']`, `data`-Reihenfolge: Gruppen, Rechte, Daten, Ansichten, Menüs zuletzt).
- `models/int_bible_translation.py`: Name, Kürzel (eindeutig, `models.Constraint`), Sprache, Rechtsstatus, Quellenvermerk, Status, Reihenfolge.
- `models/int_bible_section.py`: Baum mit `_parent_store`, `parent_id`, `sequence`, `_order = 'sequence'`, Art (Testament, Buch, Kapitel), Kapitelnummer, OSIS-Kürzel, Namen und Kürzel (übersetzbar), `display_name` kurz.
- `data/int.bible.section.csv`: zwei Testamente und 66 Bücher (Name, OSIS-Kürzel, Kürzel nach Loccum-Vorschlag, Reihenfolge). Keine Kapitel (Entscheidung 1).
- `security/int_bible_groups.xml` (`int_bible_group_user`, `int_bible_group_manager`), `security/ir.model.access.csv`.
- `views/int_bible_translation_views.xml`, `views/int_bible_section_views.xml`, `views/int_bible_menus.xml`.
- `tests/test_translation.py`, `tests/test_section.py` (eindeutiges Kürzel, Baum mit `parent_path`, Bücher geladen).
- Nicht in S1: Verse, Import, Searchpanel, Notizen, Übersetzungen der Oberfläche.

Vor dem Code: Skill `odoo-quellcode-schreiben` laden, `coding_guidelines.md` (Modulstruktur, XML-IDs, Reihenfolge im Modell) und ein Vorbild lesen (`int_liedanzeige/__manifest__.py`, `int_filemanager/models/int_filemanager_folder.py` für `_parent_store`).

## Startsatz für die neue Sitzung

Neue Sitzung im Ordner `C:\Users\Admin\Documents\GitHub\int_bible` öffnen und eingeben:

> Lies zuerst docs/int_bible_uebergabe_2026-10-24.md und docs/int_bible_plan.md. Die Entscheidungen vom 24.10.2026 gelten. Kläre nur „Noch zu klären“ kurz mit mir und mach dann Schritt S1 nach docs/int_bible_uebergabe_2026-10-24.md. Committe nicht ohne meine Ansage.
