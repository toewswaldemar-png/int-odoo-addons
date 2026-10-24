# Übergabe: Modul int_bible (Einstieg für eine neue Sitzung)

Diese Datei reicht, um ohne Vorwissen weiterzumachen. Der ganze Entwurf steht in `docs/int_bible/plan.md`. Den Umsetzungsstand nennt `int_bible/README.md`. Das Grundgerüst (`__init__.py`, `__manifest__.py`, `README.md`) liegt im Ordner `int_bible/`; S1 baut darauf auf und legt kein zweites Modul an.

## Wo was liegt

- Dieses Repo: `C:\Users\Admin\Documents\GitHub\int-odoo-addons` (öffentlich). Das Modul entsteht als Ordner `int_bible/` in der Wurzel, neben den anderen Modulen.
- Maßstab ist allein der Odoo-19-Quelltext und die Odoo-19-Doku, in diesem Repo:
  - Quelltext: `docs/odoo` (Branch 19.0, flacher Klon, nicht versioniert; vor Beginn mit `git -C docs/odoo pull` auffrischen)
  - Doku: `docs/odoo19_reference/INDEX.md`, Coding-Guidelines: `docs/odoo19_reference/contributing/coding_guidelines.md`
  - Owl: `docs/owl2_reference/INDEX.md`
- Vorbilder sind Core-Module in `docs/odoo/addons`: `lunch` (Manifest, Gruppen mit `res.groups.privilege`, Record Rule, `models.Constraint`), `hr` (`models/hr_department.py`, `_parent_store`), `account/tools` (Eigenbau ohne Datenbank). Im selben Repo liegt `int_presenter` (Gerüst, Ziel von Phase 4: Bibelvers auf den Beamer), kein Vorbild.

## Offene Punkte aus der Planung

- **Offen für S5 (Kapitelwechsel-Knöpfe):** Knöpfe im Listenkopf (`<header>`, `display="always"`) gehen ohne JavaScript. Offen ist, ob die Methode das gewählte Kapitel aus `active_domain` im Kontext zuverlässig lesen kann (nicht geprüft, erst Test im laufenden Odoo). Die Zielaktion setzt nur `searchpanel_default_section_id` im Kontext, keine `domain` (sonst leere Liste nach Klick im Baum) und `target: "main"` (sonst wächst die Brotkrumen-Leiste). Fällt der Test negativ aus, entfällt der Knopf. Abgleich Nr. 23.

## Entscheidungen (Nutzer: alle Empfehlungen übernommen)

1. **Kapitel:** Das Modul liefert nur 2 Testamente und 66 Bücher als Datei. Die rund 1.189 Kapitel entstehen beim Import der ersten Übersetzung (Referenz-Zählung). Vor dem ersten Import zeigt der Baum nur die Bücher.
2. **Buchkürzel:** Claude erstellt einen Vorschlag (Lutherbibel-Kürzel nach den Loccumer Richtlinien) für alle 66 Bücher, der Nutzer prüft ihn.
3. **Modultrennung für Phase 2 und 3:** wird erst zu Beginn von Phase 2 entschieden. Der erste Wurf ist ein einziges Modul.
4. **Übersetzungswahl:** eigener Menüpunkt „Bibel > Meine Übersetzungen“ (nicht der persönliche Einstellungsdialog). Technische Umsetzung in S5 gegen den Core prüfen.
5. **Testinstanz:** lokaler Tower (`ssh unraid`) mit eigenem Test-Container und eigener Datenbank, nicht im Container `odoo` oder in `odoo_db`.
6. **Textquelle:** eBible.org (Rechtsstatus je Text dort ausgewiesen). Erstes Einlese-Format ist deshalb **USFX** (XML) statt Zefania. Zefania kommt später als zweites Format.

## Noch zu klären (kurz, zu Beginn der neuen Sitzung)

- **Buchkürzel:** Vorschlag liegt noch nicht vor, in S1 erstellen und vom Nutzer prüfen lassen.
- **Textdateien:** Prüfen, ob Luther 1912 (`https://ebible.org/find/details.php?id=deu1912`) und Elberfelder 1905 (`...id=deuelo`) dort wirklich als USFX vorliegen (bei der Recherche nicht einzeln geprüft). Herunterladen nur nach Rückfrage mit Name, Quelle und Größe.
- **Tower:** Zustand und Zugang prüfen (die Angaben stammen aus Notizen und können veraltet sein). Quelle der Angaben: `ssh unraid`, Container `odoo`, Addons unter `/mnt/user/appdata/odoo/extra-addons`; HM-SRV ist von hier nicht erreichbar. Vor dem Anlegen eines Test-Containers kurz beim Nutzer bestätigen.

## Schritte (jeder einzeln abnehmen)

| Schritt | Inhalt | Abnahme |
|---|---|---|
| S1 | Gerüst und Stammdaten: Manifest, Gruppen, Rechte, Modelle `translation` und `section` (nur Bücher und Testamente), Ansichten und Menü für Übersetzungen, Tests | Installation fehlerfrei, Menü für Manager sichtbar, Tests grün |
| S2 | Stelle: `verse`, `verse.text`, `verse.map`, `ordinal`, Constraints, Tests | Tests grün, Eindeutigkeit geprüft |
| S3 | Import: `tools/usfx.py` (reines Python), Einlesen in `models/int_bible_translation.py` (legt Kapitel an), Assistent, Tests mit kleiner Testdatei (reiner Python-Test für den Parser) | Beispieldatei lädt, Abbruch bei kaputter Datei sauber |
| S4 | Schreibweise: `tools/reference.py` („Joh 3,16“, „Röm 5-8“), Schreibweise in `models/int_bible_section.py`, Stellensuche, `tools/words.py` für „alle Wörter“ | Tests grün |
| S5 | Leseansicht: Liste mit Searchpanel, zwei Textspalten, Überschriften, Übersetzungswahl, Menüs | Nutzer prüft im Browser |
| S6 | Lesezeichen und Notizen mit Rechten | Rechte-Tests grün, Nutzer prüft |
| S7 | Filter, Gruppierungen, mitgelieferte Favoriten, `de.po` | Nutzer prüft |
| S8 | Messung (Searchpanel, Suche, Import bei 31.000 und 155.000 Zeilen), volle Prüfung, Commit auf Ansage | Zahlen im Bericht |

## Schritt S1 im Einzelnen

Ziel: ein installierbares, leeres Gerüst mit den Stammdaten, sonst nichts.

- `int_bible/__init__.py` (importiert `models`), `__manifest__.py`: das vorhandene Gerüst ergänzen (`application: True`, `data`-Reihenfolge: Gruppen, Rechte, Daten, Ansichten, Menüs zuletzt; `depends: ['web']` und Version `19.0.1.0.0` stehen schon; Standardwerte nicht eintragen).
- `models/int_bible_translation.py`: Name, Kürzel (eindeutig, `models.Constraint`), Sprache, Rechtsstatus, Quellenvermerk, Status, Reihenfolge.
- `models/int_bible_section.py`: Baum mit `_parent_store`, `parent_id`, `sequence`, `_order = 'sequence'`, Art (Testament, Buch, Kapitel), Kapitelnummer, OSIS-Kürzel, Namen und Kürzel (übersetzbar), `display_name` kurz.
- `data/int.bible.section.csv`: zwei Testamente und 66 Bücher (Name, OSIS-Kürzel, Kürzel nach Loccum-Vorschlag, Reihenfolge). Keine Kapitel (Entscheidung 1).
- `security/int_bible_groups.xml` (`int_bible_group_user`, `int_bible_group_manager`), `security/ir.model.access.csv`.
- `views/int_bible_translation_views.xml`, `views/int_bible_section_views.xml`, `views/int_bible_menus.xml`.
- `tests/test_translation.py`, `tests/test_section.py` (eindeutiges Kürzel, Baum mit `parent_path`, Bücher geladen).
- Nicht in S1: Verse, Import, Searchpanel, Notizen, Übersetzungen der Oberfläche.

Vor dem Code: Skill `odoo-quellcode-schreiben` laden, `coding_guidelines.md` (Modulstruktur, XML-IDs, Reihenfolge im Modell) und Core-Vorbilder lesen (`docs/odoo/addons/lunch/__manifest__.py`, `docs/odoo/addons/hr/models/hr_department.py` für `_parent_store`).
