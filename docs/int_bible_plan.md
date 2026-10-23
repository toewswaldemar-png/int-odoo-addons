> Stand 24.10.2026. Planungsstand, es gibt noch keinen Code. Dieser Plan ist das Ergebnis einer Recherche- und Entwurfssitzung mit Odoo-19-Quelltext.
> Namen: Das Modul heißt `int_bible`, seine Modelle `int.bible.*` (in der Recherche hieß es `int_bibel`). Menüs und Oberfläche bleiben deutsch (über `i18n/de.po`).
> Pfade wie `docs/odoo/...`, `docs/odoo19_reference/...` und Kurzformen wie `W/` (= `addons/web/static/src`) beziehen sich auf dieses Repo (`docs/odoo` ist lokal, nicht versioniert, Odoo 19.0).
> Einstieg für eine neue Sitzung: `docs/int_bible_uebergabe_2026-10-24.md`.

# Bibelmodul für Odoo 19 (`int_bible`): Entscheidungsvorlage (Stand nach Prüfung Searchpanel und Parallelstellen)

## Ziel
Neues Modul `int_bible` in diesem Repo (Ordner `int_bible/` in der Wurzel, neben den anderen Modulen): Bibeltext im Odoo lesen und durchsuchen, mehrere Übersetzungen parallel in der Liste, Lesezeichen und eigene Notizen, später Querverweise (Parallelstellen). Nur für angemeldete Odoo-Benutzer (Backend). Navigation Testament > Buch > Kapitel über das native Searchpanel, kein eigener JavaScript-Bildschirm im MVP. Beamer ist nicht Teil dieser Stufe.

## Entscheidungen vom 24.10.2026
Kapitel entstehen beim Import (Datei enthält nur 2 Testamente und 66 Bücher). Buchkürzel: Vorschlag von Claude, Prüfung durch den Nutzer. Modultrennung für Phase 2 und 3 erst zu Beginn von Phase 2. Übersetzungswahl über den Menüpunkt „Bibel > Meine Übersetzungen“. Testinstanz: lokaler Tower mit eigenem Test-Container und eigener Datenbank. Textquelle eBible.org, erstes Einlese-Format USFX (Zefania später). Einzelheiten und noch zu klärende Kleinigkeiten: `docs/int_bible_uebergabe_2026-10-24.md`.

## Bestand im Repo (belegt)
- `int_presenter`: Grundgerüst, Ablauf soll Eintragsart „Bibelvers“ bekommen (`int_presenter/README.md:8-9,19`). Das Bibelmodul wäre die Textquelle.
- `int_liedanzeige`: Hausmuster für Manifest, Gruppen (`res.groups.privilege`), ACL, `models.Constraint`, Menüs.
- `int_filemanager`: Volltextsuche (`models/int_filemanager_text_page.py:106-200`) und Import mit Wiederaufnahme (`models/int_filemanager_import.py:248-262`) als Reserve.
- Das Repo ist **öffentlich**: kein urheberrechtlich geschützter Text und keine Querverweisdaten hinein.

## Core-Fundstellen (Odoo 19.0, `docs/odoo`)
| Baustein | Fundstelle | Aussage |
|---|---|---|
| Searchpanel-Attribute | `docs/odoo19_reference/user_interface/view_architectures/04_search.md:659-916`, `odoo/addons/base/rng/common.rng:209-235` | `select`, `hierarchize`, `enable_counters`, `expand`, `limit` (Default 200, `false` = alle); `depth` fehlt im RNG |
| Feldtypen / Hierarchie | `addons/web/models/models.py:1688-1696,1714-1724` | select=one nur many2one/selection; Elternfeld = `_parent_name`; ganzer Baum in einem Aufruf |
| Filter / Zähler | `search_model.js:1531-1540`, `models.py:1511-1541` | `child_of` über `parent_path`; Zähler nach oben summiert, bei Suche = Treffer je Knoten |
| Limit | `models.py:28,1754-1761`, `account_account_views.xml:167` | Überschreitung = Fehlermeldung statt Baum; Core nutzt `limit="false"` |
| Kategorien | `search_model.js:1452`, `models.py:1699-1702` | Mehrere Kategorien engen sich nicht ein, daher ein Baum |
| Vorwahl | `search_model.js:1406-1423` | `searchpanel_default_<feld>` im Action-Kontext |
| Lange Texte in Liste | `list_renderer.js:74-79`, `list_renderer.scss:132-141` | Text-Felder brechen um; Html-Zellen bleiben einzeilig (`text-truncate`) |
| Seitenlimit Liste | `ir_actions.py:328`, `list_arch_parser.js:211` | Standard 80; Psalm 119 hat 176 Verse, also `limit="200"` |
| Nicht gespeichert, kontextabhängig | `addons/sale/models/product_product.py:52-66`, `product_product.py:339,358` | `@api.depends_context` plus ein `_read_group` für das ganze `self` (kein N+1); Cache je Kontextwert (`odoo/orm/environments.py:471`) |
| Berechnetes Feld durchsuchen | `odoo/orm/fields.py:906-907`, `sale/.../product_product.py:18` | ohne `search=` nicht durchsuchbar, nicht sortierbar |
| Spalten ein/aus | `list_arch_parser.js:119`, `list_renderer.js:327-329`, `crm_lead_to_opportunity_views.xml:24` | `optional="show|hide"`, `column_invisible` mit Kontext; Spalten fest im Arch |
| Dynamische Spalten | `addons/analytic/models/analytic_line.py:121-146` | einziges Community-Vorbild (`_get_view`-Hook), hier überdimensioniert |
| Pivot / Kanban | `W/views/utils.js:85-99`, `kanban_arch_parser.js:88-94` | Pivot zeigt nur Zahlen; Kanban ohne x2many-Unterlisten, nicht empfohlen |
| Gruppierte Liste | `list_arch_parser.js:221`, `models.py:29,599` | `expand="1"` öffnet höchstens 10 Gruppen; als Parallelansicht ungeeignet |
| Favoriten / Rechte | `addons/project/models/project_project.py:83-103`, `lunch_security.xml:23-35` | M2M `favorite_user_ids`; Record Rule `user_id = user.id` |
| Große Daten laden | `odoo/tools/convert.py:707-760`, `odoo/orm/models.py:117` | CSV ein `load()`, 100er-Blöcke; größte Core-CSV 9.455 Zeilen, daher Import per Wizard |
| Zuordnungstabelle | `docs/odoo19_reference/backend/orm/03_constraints_and_indexes__method_decorators.md:24`, `backend/data.md:341-355` | `models.Constraint`, CSV mit `noupdate` |

## Entscheidung zum Datenmodell: Positionsmodell von Anfang an
Verse werden nicht je Übersetzung als eigene Zeile geführt, sondern über eine gemeinsame **Stelle**:
- `int.bible.verse` = Stelle (Kapitel-Knoten, Verszahl; Zählung der Referenz-Fassung).
- `int.bible.verse.text` = Text einer Stelle in einer Übersetzung.
Grund: Parallele Übersetzungen in einer Zeile gehen nur so (Listenzeile = Stelle). Lesezeichen, Notizen und Querverweise hängen an der Stelle und verrutschen beim Wechsel der Übersetzung nicht. Ein späterer Umbau von flachen Versen auf Positionen wäre eine Migration; jetzt ist er billig.

## Alternativen
- **A, nativ: Searchpanel + Listenansicht + Positionsmodell (Empfehlung):** keine Zeile JavaScript.
- **B, eigener Lese-Bildschirm (OWL):** schöneres Buch, Vers-Auswahl, Blättern. Als spätere Stufe, wenn A im Alltag nicht reicht.
- **C, alles eigen:** ohne Nutzen.

## Empfehlung: A
Alltagsbild: Das Searchpanel ist das Inhaltsverzeichnis am linken Rand, die Liste das aufgeschlagene Kapitel, eine Zeile je Stelle, die gewählten Übersetzungen stehen nebeneinander als Spalten (Standard zwei, bis vier möglich). Querverweise sind eine Liste im Formular der Stelle.

Was A nicht kann: kein „nächstes Kapitel“-Knopf (Klick im Baum), keine Mehrfachauswahl von Versen zum Kopieren, keine Trefferhervorhebung in der Liste (nativ ohne Highlight; die Hervorhebung des Filemanagers ist ein eigenes Widget), Sortierung und Suche über die berechnete Textspalte nur mit eigener `search=`-Methode, Zähler im Searchpanel zählen Stellen statt Verse einer Übersetzung (Annahme).

## Änderungsumfang (Modul `int_bible`, `application: True`, `depends` base, web)
- `int.bible.translation`: Name, Kürzel (eindeutig), Sprache, Rechtsstatus, Quellenvermerk, Status (neu, importiert, aktiv), Reihenfolge.
- `int.bible.section`: Navigationsbaum mit `_parent_store`, `parent_id`, `sequence`, `_order = 'sequence'`, Art (Testament, Buch, Kapitel), Kapitelnummer, OSIS-Kürzel; `display_name` kurz. Die 2 Testamente und 66 Bücher kommen als Stammdaten in `data/`, die rund 1189 Kapitel entstehen beim Import der ersten Übersetzung (Referenz-Zählung).
- `int.bible.verse` (Stelle): `section_id`, gespeichertes indiziertes `ordinal` (fortlaufende Nummer für Bereiche in Plänen, Notizen, Querverweisen), gespeicherte `related`-Felder `book_id` und `testament` (für Filter und Gruppierung), Vers (Integer), Anzeige „Joh 3,16“, vier berechnete, nicht gespeicherte Spaltenfelder `text_1` bis `text_4` (eine gemeinsame Compute-Methode setzt alle vier, dokumentiert in `02_fields.md:952-953`; `@api.depends_context('uid')`; liest die Übersetzungswahl des Benutzers; ein `search_fetch` auf `int.bible.verse.text` für das ganze `self`, kein N+1). Die Spaltenüberschrift trägt den Namen der gewählten Übersetzung über einen `fields_get`-Override (Vorbild `analytic_line.py:109-119`: `fields[fname]['string'] = plan.name`; `get_views` ruft `fields_get` bei jedem Aufruf, `ir_ui_view.py:2953`). Standard in der Liste: `text_1` und `text_2` sichtbar, `text_3` und `text_4` mit `optional="hide"`. `search=`-Methoden über `text_ids.text`, Lesezeichen als `favorite_user_ids` plus `is_favorite`. `_log_access = False`, eindeutig je (Kapitel, Vers), Index auf `section_id`.
- `int.bible.verse.text`: Stelle, Übersetzung, Text (`index='trigram'`), eindeutig je (Stelle, Übersetzung).
- `int.bible.verse.map`: Zuordnung abweichender Zählungen (Übersetzung, Verszahl der Übersetzung, Stelle), `models.Constraint` auf (Übersetzung, Verszahl). Standard ist Gleichheit, Ausnahmen als Daten (z. B. 3 Joh 14/15, Psalmenüberschriften, Mal 3/4). Der Import meldet Stellen, die in einer Übersetzung fehlen.
- Benutzerwahl der Übersetzungen: Vererbung von `res.users.settings` (1:1 je Benutzer, `UNIQUE(user_id)`, `odoo/addons/base/models/res_users_settings.py:8-14`) in `models/res_users_settings.py` mit vier Many2one-Feldern, Präfix `int_bible_`. Bearbeitet wird sie über einen eigenen Menüpunkt „Bibel > Meine Übersetzungen“ (entschieden 24.10.2026); die technische Umsetzung (Aktion auf den eigenen Datensatz von `res.users.settings`) ist in S5 gegen den Core zu prüfen (Annahme).
- `int.bible.note`: Benutzer, Stelle von/bis, Notiz, Farbe; Record Rule auf eigene Datensätze.
- `int.bible.translation.import` (Wizard, Transient-Namensmuster `<Basismodell>.<Aktion>`, `coding_guidelines.md:851-854`): Datei (USFX XML als erstes Format), Übersetzung. Der Wizard parst nur (`_parse_usfx`, je Format eine kleine Methode, erweiterbar) und ruft die Geschäftslogik im Basismodell auf (`int.bible.translation._import_verses`), kein `cr.commit()` (`coding_guidelines.md:642-692`).
- Views: Liste (`limit="200"`, Text umbrechend, Stern-Spalte), Search-View mit `<searchpanel>` (Baum „Bibel“, `limit="false"`, `enable_counters`, **ohne `depth`**), Formular der Stelle (Texte, Notiz), Notizen-Liste, Verwaltung der Übersetzungen. Menü: Bibel lesen, Notizen, Konfiguration.
- Sicherheit: Gruppen Benutzer/Manager (Muster `int_liedanzeige`). Texte lesen alle Benutzer, Pflege nur Manager.
- Keine Bibeltexte im Repo. Start mit gemeinfreien Fassungen (Luther 1912, Elberfelder 1905) von eBible.org (Rechtsstatus dort je Text ausgewiesen), Datei per Wizard.

## Suche: Filter, Gruppierungen, Favoriten (belegt, nativ)
Regeln der Suchleiste (belegt): Filter einer Gruppe = ODER, verschiedene Gruppen = UND (`search_arch_parser.js:99-110`, `search_model.js:1607-1630`); jedes `<field>` ist eine eigene Facette (`parser:113`); Gruppieren braucht ein gespeichertes Feld oder ein nicht gespeichertes `related` (`models.py:2929-2936`, sicherer: `store=True, precompute=True`, Muster `account_move_line.py:57`); Pfade im `<filter context>` werden nicht als Gruppierung erkannt (`parser:19-24`), daher eigene Felder an der Stelle.

| Kandidat | Art | Bedarf |
|---|---|---|
| Lesezeichen | Filter | `favorite_user_ids in uid` (Muster `project_project_views.xml:157`) |
| Mit Notiz | Filter | `note_ids any user_id = uid` |
| Mit Querverweisen (Phase 2), Gewicht ab festem n | Filter | `any` auf dem One2many |
| Buchgruppen (Gesetz, Geschichte, Weisheit, Propheten, Evangelien, Briefe) | Filter, ODER-Gruppe | Selection am Buch-Knoten, an der Stelle als gespeichertes `related` |
| Text fehlt in Übersetzung X (nur Manager) | Filter | `text_ids not any [translation_id = X]`, X je Filter fest |
| Buch, Testament, Kapitel | Gruppieren | gespeicherte `related`-Many2one (`book_id`) und Selection (`testament`); Reihenfolge Many2one = `_order` des Knotens (`models.py:2198-2205`); Kapitel: 1189 Gruppen = 15 Seiten à 80 (`relational_model.js:123`) |
| Buchgruppe | Gruppieren | Selection mit `group_expand=True` für Definitionsreihenfolge |
| Stellensuche („Joh 3,16“, „Röm 5-8“) | Suchfeld | eigene `_search_display_name`/`search=`-Methode (Parser in Python), Vorbild `account_account.py:855-868` |
| Text enthält Wendung / alle Wörter | zwei Einträge desselben Feldes | `ilike` zerlegt nicht (`fields.py:1321-1333`); „alle Wörter“ braucht eigene Methode mit einem einzigen `any` (sonst mischen sich Übersetzungen) |
| Favoriten (gespeicherte Suchen) | Daten | `ir.filters` in XML, `user_ids` leer = für alle, Muster `hr_applicant_views.xml:712-718` |
| Notizen: eigene, Farbe, Datum (`date="create_date"`, `write_date:month`), Buch | Filter / Gruppieren | Standard |
| Nicht nativ: Verslänge (Zählfeld nötig), „zuletzt gelesen“ (eigenes Modell), alle Wörter ohne eigene Methode | | |
Panel: Zähler berücksichtigen Suchleiste und Filter, aber nicht die Gruppierung (`search_model.js:1433-1456`). Gleichzeitig nach Buch gruppieren und ein Kapitel im Panel wählen ist möglich. Panel braucht `limit="0"` bzw. `"false"`.

## Bibellesepläne: Phase 3, Datenmodell jetzt vorbereitet (Feld `ordinal` an der Stelle)
- **Vorbereitung im MVP:** gespeichertes, indiziertes Feld `ordinal` an `int.bible.verse` (fortlaufende Nummer 1 bis ca. 31.100 der Referenzzählung). Bereiche (Plan-Abschnitte, Notizen, Querverweise) werden damit zu zwei Zahlen. `between` gibt es serverseitig nicht (`domains.py:81-90`), also `>=` und `<=` (Domain-Editor macht es genauso, `virtual_operators.js:296-302`).
- **Variante X (Tageszeilen je Benutzer beim Start), belegt als die native Wahl:** nur vorhandene Datensätze funktionieren in Liste, Kalender, Pivot, Filter und Gruppierung (nicht gespeicherte Felder sind nicht filter- und gruppierbar, `fields.py:906-940`). Größenordnung 200 Benutzer × 3 Pläne × 365 Tage ≈ 220.000 Zeilen (Annahme), mit Indizes unkritisch.
- **Modelle:** `int.bible.plan` (Name, Tage), `int.bible.plan.day` (Plan, Tagnummer, berechneter Name „Jes 40-42; Joh 3“), `int.bible.plan.passage` (Tag, `ordinal_from`, `ordinal_to`), `int.bible.plan.enrollment` (Plan, Benutzer, Startdatum, gespeicherter Fortschritt in Prozent, `mail.activity.mixin`), `int.bible.plan.line` (Einschreibung, Tag, Datum, gelesen, Lesedatum).
- **Core-Vorbild Einschreibung und Fortschritt:** `website_slides` (`slide_channel_partner.py:6-33,88-117`, `slide_slide_partner.py:5-34`, Views `slide_channel_partner_views.xml:27-94`). **Odoo-Aktivitätspläne (`mail.activity.plan`) sind ungeeignet:** 365 Templates von Hand, 365 Aktivitäten auf einen Schlag, kein Fortschritt, keine Abschnitte (`mail_activity_plan_template.py:11-53`, `mail_activity_schedule.py:325-345`).
- **Views:** Kanban „Meine Pläne“ (Widget `progressbar`, Balken 100 × 15 px, Füllung Primärfarbe `#71639e`, `progress_bar_field.scss:1-7`), editierbare Liste „Offene Lesetage“ (Filter mit `context_today()`, `decoration-danger`/`-muted`, Schalter `boolean_toggle` oder Objekt-Button „Gelesen“, Button „Lesen“ gibt `ir.actions.act_window` mit OR-Domain auf `ordinal` zurück, Muster `sale_order.py:1455-1481`), Kalender nur als Anzeige (`date_start` als Date-Feld = ganztägig, `create="0"`, `quick_create="0"`, `calendar_model.js:662-664`), Pivot/Graph (Community) für Fortschritt.
- **Erinnerung:** Odoo-üblich ist täglicher Cron mit `activity_schedule` je Benutzer (Muster Fleet: `fleet_vehicle_log_contract.py:140-175`, Cron `fleet_data.xml:4-12`), Systray zeigt „Heute lesen: Jes 40-42“. „Heute“ je Benutzer mit `with_context(tz=user.tz)` (Cron läuft als OdooBot, vermutlich UTC, Annahme). Alternative: E-Mail-Digest nach dem Digest-Muster (`digest/data/ir_cron_data.xml:3-12`).
- **Plan erzeugen ohne fremde Pläne:** Wizard (Muster `hr_leave_generate_multi_wizard.py:104-125`): Bereich (Bibel, AT, NT, Bücher), Anzahl Tage, Startdatum; Algorithmus teilt nach Versanzahl aus dem Baum gleichmäßig auf, Kapitel kommt in den Tag, in dessen Mitte es liegt. Eigene CSV-Pläne über `base_import` nur mit eindeutigem Abschnittsnamen („Johannes 3“) und zwei Ordinal-Spalten für Versbereiche (`ir_fields.py:545`). Geschützte Pläne anderer nicht übernehmen.
- **Rechte:** persönliche Einschreibung (`user_id = uid`); Gruppe „Leseplan-Leiter“ sieht den Fortschritt aller (Muster `lunch_security.xml:25-36`, `hr_timesheet_security.xml:50-82`, Odoo-19-Privilegien). Hinweis: Lesefortschritt in einer Kirchengemeinde ist religiöse Information (DSGVO Art. 9), standardmäßig nur der Benutzer selbst, der Leiter nur mit dokumentiertem Zweck – keine Rechtsberatung.
- **Nicht nativ / ungeprüft:** Einklick-Umschalten mit `boolean_toggle` in der Liste (Annahme: erster Klick betritt die Zeile; reine Checkbox schaltet sofort, `list_renderer.js:~1253-1266`), grüner Fortschrittsbalken (nur über `overflow_class` oder CSS), Kalender mit direktem Abhaken, Filter „Diese Woche“ als Domain (nicht getestet).

## Querverweise (Parallelstellen im engeren Sinn): Phase 2, Datenmodell jetzt vorbereitet
- Modell `int.bible.reference`: Quelle (Stelle), Ziel von/bis (Stelle), Gewicht (Votes), eigenes `_compute_display_name` („Joh 1,1-3“ für Bereiche). Eigenes Modell nötig, ein M2M auf die Stelle würde Bereiche und Gewicht verlieren.
- **Spalte „Querverweise“ neben dem Text (belegt, `many2many_tags_field.js:251`, `stock_move.py:192/608-615`, `mrp_production_views.xml:460`):** berechnetes, nicht gespeichertes One2many `reference_ids` auf der Stelle (Top 5 nach Gewicht), Widget `many2many_tags`, `readonly`, `optional="show"`, feste `width` (ca. 210 px). Compute für das ganze `self` mit einem `search_fetch([('from_id','in',self.ids)], order='votes desc')`, die ersten N je Quelle in Python. Namen werden in einem gemeinsamen `web_read` geladen, keine Abfrage je Tag (`web/models/models.py:~173-217`).
- Grenzen der Spalte (belegt): nur Anzeige – Klick auf ein Tag öffnet die Zeile (das Formular der Quellstelle), nicht die Zielstelle; kein „+N“ (nur die Avatar-Variante hat es, hier ungeeignet); der Zieltext erscheint nicht (nur Tooltip mit dem Namen); nicht sortierbar; viele Tags machen die Zeile höher; keine Hover-Vorschau im Core. Klickbare Tags oder Vorschau = eigenes JS (Unterklasse von `Many2ManyTagsField`), nur bei Bedarf.
- Weitere Anzeige: One2many-Liste im Formular der Stelle (Reiter „Parallelstellen“, Zielstelle, Text, Gewicht) und eigene Liste mit demselben Searchpanel-Baum (Filter nach Quellkapitel).
- Datenquelle: openbible.info Cross References, **CC BY** (Namensnennung nötig), rund 345.000 Verweise, englische Verszählung (entspricht der Referenz-Fassung). Laden per Wizard, nicht ins Repo. Empfehlung: nur Gewicht ≥ 3 und höchstens 10 je Vers (ca. 121.000 Zeilen). Quelle und Lizenz im Quellenvermerk anzeigen.
- Eine freie, deutsche oder maschinenlesbare Evangelien-Synopse gibt es nach der Recherche nicht. Falls gewünscht, als kleine selbst gepflegte Tabelle (ca. 150 bis 370 Perikopen).

## Prüfung der Struktur gegen die Odoo-Norm (`docs/odoo19_reference/contributing/coding_guidelines.md`)
Zielstruktur des Moduls `int_bible` (nur die Ordner, die das Modul wirklich braucht; Norm `:35-48`):
```text
int_bible/
|-- __init__.py                      (importiert models, wizard)
|-- __manifest__.py                  (depends: base, web; application: True; LGPL-3; data-Reihenfolge s. u.)
|-- models/                          (je Datei ein Thema, Aufteilung wie int_filemanager)
|   |-- __init__.py                  (Reihenfolge: Stammdaten, Inhalt, Benutzerdaten, Formate)
|   |-- int_bible_translation.py     (Thema Stammdaten: Übersetzung, Rechtsstatus, Status)
|   |-- int_bible_translation_load.py (Thema Einlesen: _inherit, Massen-Import der Verse, Bericht)
|   |-- int_bible_parser.py          (AbstractModel: Schnittstelle _parse() für Dateiformate)
|   |-- int_bible_parser_usfx.py     (AbstractModel: USFX XML, erstes Format; Zefania und weitere = weitere Dateien)
|   |-- int_bible_section.py         (Thema Navigation: Baum Testament > Buch > Kapitel, Namen, Kürzel)
|   |-- int_bible_section_reference.py (Thema Schreibweise: _inherit, „Joh 3,16“ lesen und schreiben)
|   |-- int_bible_verse.py           (Thema Stelle: Felder, ordinal, Constraints, Anzeigename)
|   |-- int_bible_verse_text.py      (eigenes Modell int.bible.verse.text: Text je Stelle und Übersetzung)
|   |-- int_bible_verse_map.py       (eigenes Modell int.bible.verse.map: Zählungs-Zuordnung)
|   |-- int_bible_verse_reading.py   (Thema Leseansicht: _inherit, Textspalten, fields_get, Suchmethoden)
|   |-- int_bible_verse_bookmark.py  (Thema Lesezeichen: _inherit, favorite_user_ids, is_favorite)
|   |-- int_bible_note.py            (Benutzerdaten: Notiz)
|   |-- res_users_settings.py        (geerbtes Modell, eigene Datei, Norm :59-61)
|-- wizard/
|   |-- int_bible_translation_import.py
|   |-- int_bible_translation_import_views.xml
|-- security/
|   |-- ir.model.access.csv
|   |-- int_bible_groups.xml         (Gruppen: int_bible_group_user, int_bible_group_manager)
|   |-- int_bible_note_security.xml  (Record Rule int_bible_note_rule_user)
|-- data/
|   |-- int.bible.section.csv        (2 Testamente, 66 Bücher; Kapitel entstehen beim Import; CSV benannt nach Modell wie res.country.state.csv)
|   |-- ir_filters_data.xml          (mitgelieferte Favoriten)
|   |-- int_bible_verse_demo.xml     (nur wenige Demo-Verse, gemeinfrei)
|-- views/
|   |-- int_bible_verse_views.xml    (list, search mit searchpanel, form, action)
|   |-- int_bible_translation_views.xml
|   |-- int_bible_section_views.xml
|   |-- int_bible_note_views.xml
|   |-- res_users_settings_views.xml (Übersetzungswahl, wie int_filemanager/views/res_users_views.xml)
|   |-- int_bible_menus.xml          (Hauptmenüs, optional laut Norm :88-91)
|-- i18n/
|   |-- int_bible.pot
|   |-- de.po
|-- tests/
|   |-- __init__.py
|   |-- test_translation_load.py, test_parser_usfx.py, test_section_reference.py,
|   |   test_verse_reading.py, test_verse_bookmark.py, test_searchpanel.py, test_note_security.py
```
Aufteilung nach Themen (belegt als Hausmuster und Core-Muster, Ausmaß geschätzt):
| Datei | Eine Verantwortung | Muster | ca. Zeilen |
|---|---|---|---|
| `int_bible_translation.py` | Stammdaten der Übersetzung | `product_category.py` (69 Z.) | 80 |
| `int_bible_translation_load.py` | Verse einer Übersetzung einlesen und melden | `int_filemanager_document_storage.py` (`_inherit` nach Thema) | 150 |
| `int_bible_parser*.py` | ein Dateiformat lesen, austauschbar | Core: `account_edi_xml_ubl_*.py` je Format ein AbstractModel | je 80 |
| `int_bible_section.py` | Navigationsbaum und Namen | `hr_department.py` (242 Z., `_parent_store`) | 120 |
| `int_bible_section_reference.py` | Schreibweise „Joh 3,16“ lesen/schreiben (Parser und Formatierer zusammen mit den Kürzeln der Bücher) | `_inherit` nach Thema | 120 |
| `int_bible_verse.py` | die Stelle selbst | `slide_slide_partner.py` (55 Z.) | 100 |
| `int_bible_verse_reading.py` | Textspalten für die Liste, Suche über die Texte | `int_filemanager_document_rendition.py` | 200 |
| `int_bible_verse_bookmark.py` | Lesezeichen je Benutzer | `project_project.py:83-103` | 60 |
| `int_bible_note.py` | Notiz je Benutzer | `slide_channel_partner.py` (257 Z.) | 100 |
Keine Datei über ca. 250 Zeilen (Hausmaß: `int_filemanager` bis 1140, Core `slide_slide.py` 1339). Keine Mixins im MVP (nichts wird von mehreren Modellen geteilt, sonst Muster `int_filemanager_linkable.py`). Das Parser-Schnittstellenmodell ist die einzige Abstraktion und hat einen Zweck: weitere Formate (USFX, OSIS) ohne Eingriff in bestehende Dateien.
Nicht vorhanden im MVP (Norm: nur anlegen, wenn nötig): `controllers/` (keine HTTP-Routen), `static/` (kein JavaScript), `report/`.

| Punkt | Norm (Fundstelle) | Plan | Ergebnis |
|---|---|---|---|
| Modulpräfix | Firmenpräfix empfohlen (`:30-31`) | `int_bible` | passt |
| Dateiname = Modell, geerbte Modelle eigene Datei | `:57-69` | `int_bible_verse.py`, `res_users_settings.py` | passt |
| Transient-Modell | `<Basismodell>.<Aktion>`, ohne „wizard“ (`:851-854`), Dateien in `wizard/` (`:140-150`) | vorher `int.bible.import` | **angepasst** zu `int.bible.translation.import` |
| Sicherheitsdateien | `ir.model.access.csv`, `<module>_groups.xml`, `<model>_security.xml` (`:71-84`) | wie Baum | passt |
| XML-IDs | `<model_name>_view_<type>`, `_action`, `_menu`, `<module>_group_<name>`, `<model_name>_rule_<group>` (`:282-298`) | z. B. `int_bible_verse_view_list`, `int_bible_verse_action`, `int_bible_group_user`, `int_bible_note_rule_user` | passt |
| Views je Modell, Menüs getrennt | `:86-91` | wie Baum | passt |
| Daten nach Zweck und Modell | `_data.xml`, `_demo.xml` (`:104-115`) | CSV und XML getrennt nach Modell | passt |
| Feldnamen | Many2one `_id`, X2many `_ids` (`:876-877`) | `section_id`, `text_ids`, `reference_ids`, `favorite_user_ids` | passt |
| Methodennamen | `_compute_<feld>`, `_search_<feld>`, `_default_`, `_check_`, `action_` mit `ensure_one()` (`:880-888`) | Spalten-Compute als gemeinsame Methode `_compute_texts` (wie `_compute_seats` im Normbeispiel `:914-917,922`) | passt |
| Reihenfolge im Modell | private Attribute, Defaults, Felder, SQL-Constraints, Compute/Inverse/Search, Selection, Constrains, CRUD, Actions, Business (`:889-900`) | bei der Umsetzung einhalten | offen bis Code |
| Kontextschlüssel | mit Modulpräfix (`:595-598`) | `int_bible_…` | passt |
| Transaktion | kein `cr.commit()` (`:642-692`) | Import in einer Transaktion; Cron-Variante nur mit begründetem Commit | passt |
| Erweiterbar, kleine Methoden | `:600-640` | Wizard parst, Basismodell importiert; `_get_slot_translations`, `_get_references_domain` als Einhängepunkte | passt |
| Übersetzungen | `self.env._('…')` nur mit festen Texten (`:761-843`); Quelltexte englisch (so macht es `int_liedanzeige`), deutsche Texte in `i18n/de.po` | englische Quelltexte, `de.po` mitliefern (Lücke bei `int_liedanzeige`, `Liedanzeige_Odoo_Pruefung.md:83`) | **ergänzt** |
| Modultrennung | Kern trennt optionale Funktionen mit anderer Abhängigkeit in eigene Module (z. B. `website_slides_survey`, `hr_holidays_attendance`) | MVP = ein Modul `int_bible`; Querverweise und Lesepläne als **eigene Module** `int_bible_reference`, `int_bible_plan` (hängen von `int_bible`, Lesepläne zusätzlich von `mail`); Entscheidung endgültig erst zu Phase 2 | zu bestätigen, weicht von deiner Linie „ein Modul zusammenhalten“ beim Filemanager ab |

`__manifest__.py`, Reihenfolge `data`: `security/int_bible_groups.xml`, `security/ir.model.access.csv`, `security/int_bible_note_security.xml`, `data/int.bible.section.csv`, `data/ir_filters_data.xml`, dann `views/` (Modellviews, Wizard-Views), zuletzt `views/int_bible_menus.xml` (Menüs verweisen auf die Actions). Demo: `data/int_bible_verse_demo.xml` unter `demo`.

## Fehlerfälle
| Eingabe / Zustand | Verhalten |
|---|---|
| Baum mit mehr als `limit` Knoten | `limit="false"`; Test: 1257 Knoten ohne `error_msg` |
| Stelle fehlt in einer Übersetzung | Textfeld zeigt diese Übersetzung nicht oder „–“, Import-Bericht listet Lücken |
| Keine Übersetzung für Spalte 1/2 gewählt | Standard = die ersten aktiven Übersetzungen nach Reihenfolge; keine aktive = leere Spalten mit Hinweis |
| Spalte 3/4 nicht belegt | Spalte leer, Überschrift „Übersetzung 3“; bleibt per `optional="hide"` ausgeblendet |
| Import: kaputte oder fremde Datei | Abbruch vor dem ersten Schreiben, klare Meldung |
| Import: dieselbe Übersetzung zweimal | Eindeutigkeit, Meldung „bereits importiert“ |
| Import bricht ab | Status bleibt „neu“, Wiederholung räumt Teilbestand zuerst auf |
| Abweichende Verszählung ohne Eintrag in der Zuordnung | Verse landen auf der gleichnamigen Stelle; Bericht markiert Auffälligkeiten |
| Suche ohne Treffer / leer | leere Liste / alle Stellen mit Limit |
| Benutzer ohne Gruppe | Menü unsichtbar, ACL verweigert |
| Notizen anderer Benutzer | unsichtbar (Record Rule) |
| Mehrere Firmen | Text firmenunabhängig, Notizen persönlich |
| Querverweis-Ziel fehlt | Eintrag wird beim Import übersprungen und gezählt |
| Stelle ohne Querverweise | Spalte leer, keine Fehlermeldung |
| Stelle mit über 100 Querverweisen | Spalte zeigt nur die Top 5 nach Gewicht, das Formular alle |
| Querverweis auf Bereich | Tag zeigt „Joh 1,1-3“ über `_compute_display_name` der Referenz |
| Spalte ausgeblendet (`optional`) | Compute läuft vermutlich trotzdem (Annahme), Kosten klein |

## Risiken
- **Lizenz:** Lutherbibel 2017, Elberfelder CSV, Hoffnung für Alle sind geschützt. Ein durchsuchbares Odoo-Modul fällt vermutlich nicht unter die Gemeindebrief-Ausnahme der Bibelgesellschaft (Einschätzung, nicht belegt). Nur gemeinfreie Fassungen liefern. Schlachter 1951: Quellen widersprechen sich. Querverweise: CC BY mit Quellenangabe.
- **Verszählung:** Schon Luther 1912 (14 Verse) und Elberfelder 1905 (15 Verse, mit Markierung) weichen bei 3 Joh ab. Die Zuordnungstabelle ist daher von Anfang an nötig, nicht erst später.
- **Searchpanel:** `depth` nicht im RNG (nicht verwenden). Mit Zählern lädt jede Änderung der Suche den Baum neu (1257 Knoten, `read_group` über bis zu 155.000 Zeilen, nicht gemessen). Auswahl nicht in der URL, nur über Aktionskontext vorwählbar.
- **Übersetzungsspalten:** Spaltenzahl fest im Arch (2 sichtbar + 2 optional), jede Spalte ca. 200 px bei eingeklapptem Searchpanel; auf schmalen Schirmen brechen die Texte stark um. Die Ansicht (`get_views`) liegt beim Client im Disk-Cache (`view_service.js:98`, `orm.cache({type: "disk"})`): nach Wechsel der Übersetzung kann die alte Überschrift beim ersten Laden noch kurz stehen (Annahme, nicht getestet).
- **Berechnete Textfelder:** Sortieren und Suchen nur mit eigener Methode; Highlight fehlt. Reicht das im Alltag nicht, kommt Stufe B (eigener Bildschirm).
- **Suche:** `ilike` mit Trigram findet Teilwörter, kein Ranking, keine Wortstämme. `pg_trgm` fehlt eventuell in bestehenden Datenbanken.
- **Importzeit** 31.000 Stellen und Texte je Übersetzung nicht gemessen.

## Tests
- Python: Import mit kleiner Beispieldatei (3 Bücher, 2 Übersetzungen, eine mit abweichender Zählung), Zuordnung, Eindeutigkeit, Abbruch bei kaputter Datei, `search_panel_select_range` liefert den Baum ohne `error_msg`, Zähler bei Suche, berechnetes Textfeld (1 und 2 Übersetzungen, genau eine Abfrage für die Liste), `search=` mit Umlauten, Rechte (Benutzer, Manager, fremde Notizen).
- Phase 2: Querverweis-Compute (eine Abfrage je Seite, Top-N-Reihenfolge, Bereichsname), Import der Querverweise mit überspringen/zählen, Rechte.
- Messung vor Freigabe: Antwortzeit Searchpanel mit Zählern und Suche bei 31.000 und 155.000 Textzeilen; Importzeit; Listenseite mit 200 Zeilen × 5 Tags.
- Regression: bestehende Module unverändert.

## Vertrauensgrad
- **Belegt:** alle Fundstellen oben, Hausmuster, Lizenzaussagen zu Luther 1912 und Elberfelder 1905, Eckdaten und Lizenz von openbible.info.
- **Getestet:** nichts.
- **Annahme:** Performance der Zähler und der Textspalte, Importzeit, Zählung der Stellen im Searchpanel, `text-wrap` bei Html (nicht benutzt), Trigram-Verfügbarkeit, Farbe der Auswahl im Panel (≈ `#d6ecfa`, überschlagen), Zeilenzahl der scrollmapper-Querverweistabelle.

## Phasen
1. MVP (diese Freigabe): Modelle (Positionsmodell, Zuordnung), Import, Searchpanel-Liste mit paralleler Textspalte, Übersetzungswahl, Lesezeichen, Notizen, Verwaltung.
2. Querverweise (Parallelstellen) mit Import aus openbible.info und Spalte neben dem Text; eigener Lese-Bildschirm (B) nur bei Bedarf.
3. Bibellesepläne (Modelle, Plan-Wizard, Kanban und Liste, Erinnerung per Aktivität).
4. Verbindung zu `int_presenter` (Bibelvers auf den Beamer) als eigener Auftrag.

## Prüfung nach der Umsetzung
Diff gegen diesen Plan, Fehlerfälle abhaken, gezielte Tests, volle Suite und Hook nur einmal vor dem Commit. Nicht committen, bis der Nutzer es sagt.
