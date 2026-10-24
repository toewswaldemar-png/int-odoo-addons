# int_bible: Bausteine nach Herkunft (Odoo-Bordmittel und Eigenbau)

Zweck: Von Anfang an sichtbar machen, was Odoo selbst liefert (mit Fundstelle) und was eigener Code ist. Die Tabelle wird in jedem Schritt (S1 bis S8) mitgepflegt. Belege und Begründungen stehen hier, nicht im Code. Pfade `docs/odoo/...` sind der Odoo-19-Quelltext (Branch 19.0), `coding_guidelines.md` liegt unter `docs/odoo19_reference/contributing/`.

**Stufen:**
1. Konfiguration oder vorhandenes Odoo-Modell, kein eigener Code (XML, CSV, Rechte)
2. Erweiterung mit einem Odoo-Mechanismus (`_inherit`, Felder, Compute, `search=`, Hooks)
3. Bibliothek, die im Odoo-Image enthalten ist
4. Eigenbau, nur für die nachgewiesen fehlende Funktion
5. Ersatz eines Odoo-Teils (keiner geplant)

**Status:** geplant, gebaut, getestet, abgenommen. **Vertrauen:** belegt (Fundstelle gelesen), Annahme (nicht geprüft).

## Bausteine

| Nr | Baustein | Stufe | Datei (geplant) | Beleg im Odoo-Kern | Vertrauen | Status |
|---|---|---|---|---|---|---|
| 1 | Navigationsbaum Testament > Buch > Kapitel im Searchpanel, `limit="false"`, Zähler | 1 | `views/int_bible_verse_views.xml` | `04_search.md:659-916`, `account_account_views.xml:167`, `hr_employee_views.xml:12-15` | belegt | geplant |
| 2 | Liste mit umbrechendem Text, `limit="200"`, optionale Spalten | 1 | `views/int_bible_verse_views.xml` | `list_renderer.js:74-79`, `list_arch_parser.js:119,211` | belegt | geplant |
| 3 | Filter, Gruppierungen, Stellen-/Textsuchfelder in der Suchleiste | 1 | `views/int_bible_verse_views.xml` | `search_arch_parser.js:99-113`, `res_partner_views.xml:319` | belegt | geplant |
| 4 | Mitgelieferte Favoriten (gespeicherte Suchen) | 1 | `data/ir_filters_data.xml` | `hr_applicant_views.xml:712-718`, `ir_filters.py:14` | belegt | geplant |
| 5 | Gruppen, Zugriffsrechte, Regel „nur eigene Notizen“ | 1 | `security/*` | `lunch_security.xml:25-36`, `coding_guidelines.md:71-84` | belegt | geplant |
| 6 | 2 Testamente und 66 Bücher als Datendatei | 1 | `data/int.bible.section.csv` | `convert.py:707-760`, `res.country.state.csv` | belegt | geplant |
| 7 | Menüs und Aktionen, Menü „Meine Übersetzungen“ | 1 | `views/int_bible_menus.xml` | `coding_guidelines.md:282-298` | belegt (Umsetzung des Menüs: Annahme) | geplant |
| 8 | Navigationsbaum als Modell (`_parent_store`) | 2 | `models/int_bible_section.py` | `product_category.py:12-23`, `models.py:3216-3220` | belegt | geplant |
| 9 | Stellenmodell, Text je Übersetzung, eindeutige Schlüssel (`models.Constraint`) | 2 | `models/int_bible_verse.py`, `int_bible_verse_text.py` | `03_constraints_and_indexes__method_decorators.md:24` | belegt | geplant |
| 10 | Gespeicherte Hilfsfelder `book_id`, `testament`, `ordinal` | 2 | `models/int_bible_verse.py` | `account_move_line.py:57` (related, store, precompute) | belegt | geplant |
| 11 | Zwei bis vier Textspalten als berechnete Felder je Benutzer, eine Abfrage je Seite | 2 | `models/int_bible_verse.py` | `product_product.py:52-66`, `02_fields.md:952-953`, `environments.py:471` | belegt (Geschwindigkeit: Annahme) | geplant |
| 12 | Spaltenüberschrift mit dem Namen der gewählten Übersetzung | 2 | `models/int_bible_verse.py` | `analytic_line.py:109-119`, `ir_ui_view.py:2953` | belegt (Cache-Verhalten: Annahme) | geplant |
| 13 | Lesezeichen je Benutzer | 2 | `models/int_bible_verse.py` | `project_project.py:73-103` | belegt | geplant |
| 14 | Notizen je Benutzer | 2 | `models/int_bible_note.py` | `slide_channel_partner.py`, `lunch_security.xml` | belegt | geplant |
| 15 | Übersetzungswahl je Benutzer | 2 | `models/res_users_settings.py` | `res_users_settings.py:8-14` | belegt (Bearbeitung im Menü: Annahme) | geplant |
| 16 | Einlese-Assistent (Dialog, Datei hochladen) | 2 | `wizard/int_bible_translation_import.py` | `hr_leave_generate_multi_wizard.py:104-125`, `coding_guidelines.md:851-854` | belegt | geplant |
| 17 | Massen-Einfügen der Verse | 2 | `models/int_bible_translation.py` | `account_full_reconcile.py:26` (`execute_values`), `models.py:117` | Annahme (Importzeit nicht gemessen) | geplant |
| 18 | XML lesen | 3 | `tools/usfx.py` | `lxml` im Image (Standardbibliothek `xml` als Alternative) | Annahme | geplant |
| 19 | Einlesen einer Bibeldatei (USFX) | 4 | `tools/usfx.py` | siehe Eigenbau 1 | belegt | geplant |
| 20 | Zuordnung abweichender Verszählung | 4 | `models/int_bible_verse_map.py` | siehe Eigenbau 2 | belegt | geplant |
| 21 | Schreibweise „Joh 3,16“, „Röm 5-8“ lesen und schreiben | 4 | `tools/reference.py` | siehe Eigenbau 3 | belegt | geplant |
| 22 | Suche „alle Wörter“ | 4 | `tools/words.py` | siehe Eigenbau 4 | belegt | geplant |
| 23 | Knöpfe „Vorheriges/Nächstes Kapitel“: Schaltflächen im Listenkopf (Stufe 1) und Bestimmung des Nachbarkapitels (Stufe 4, Datenbank) | 1 und 4 | `views/int_bible_verse_views.xml`, `models/int_bible_section.py` | `list_controller.xml:18-21` (`display="always"`), `multi_record_view_button.js:9-13` (Kontext `active_domain`), `search_model.js:1417` (`searchpanel_default_*`), `action_service.js:1458` (`target: "main"`) | belegt (ob `active_domain` das Kapitel zuverlässig liefert: Annahme, Test in S5) | geplant, nur nach Test |

Später (Phase 2 und 3): Querverweise (Spalte als berechnetes One2many, `stock_move.py:608-615`; Eigenbau nur: Top-5-Auswahl und Import des Datensatzes), Lesepläne (Muster `website_slides`; Eigenbau nur: Plan-Erzeuger, `ordinal`-Bereiche).

## Eigenbau: nachgewiesene Lücken

| Nr | Eigenbau | Was Odoo nicht hat | Gesucht und gefunden | Verworfene Alternative |
|---|---|---|---|---|
| 1 | USFX-Einlesen | kein Import von Bibelformaten; der eingebaute Import liest nur CSV, XLS und XLSX | Suche `usfx\|zefania\|osis` in `docs/odoo/addons` und `docs/odoo/odoo` (.py, .js, .xml): nur ein Zufallstreffer in `addons/l10n_dz/__manifest__.py`, nicht einzeln geprüft; Suche `bible\|bibel\|scripture`: kein Treffer; Formate des Imports: `base_import/static/src/import_action/import_action.js:57-74` | `base_import` mit einer extern aufbereiteten CSV: braucht ein Umwandlungsskript außerhalb von Odoo (also auch Eigenbau) und legt Stelle und Zuordnung nicht an |
| 2 | Zuordnung der Verszählung | keine Zuordnung zwischen Zählweisen derselben Stelle | Fachlich: Psalmen, Maleachi 3/4, 3. Johannes unterscheiden sich je Ausgabe (Recherche); Odoo-Seite: kein Treffer bei der Suche nach `bible` | keine; das Modell selbst ist Stufe 2 (`models.Constraint`), nur die Daten sind fachlich |
| 3 | Schreibweise von Bibelstellen | kein Parser für Stellenangaben; Vorbild für eine Referenzschreibweise im Kern: `account/tools/structured_reference.py` | Suche `book.*chapter.*verse` in `addons` und `odoo` (.py): kein Treffer; Muster für eine eigene Suchlogik: `account_account.py:855-868`, `product_product.py:880-920` | Texteingabe nur über `ilike`: versteht „Joh 3,16“ nicht |
| 4 | Suche „alle Wörter“ | `ilike` bildet ein einziges Muster `%wert%` und zerlegt nichts | `docs/odoo/odoo/orm/fields.py:1318-1334`; mehrere Werte im selben Suchfeld verknüpft Odoo mit ODER (`search_model.js:1746-1764`), zwei getrennte Pfadbedingungen auf `text_ids` können zwei verschiedene Übersetzungen mischen (`domains.py:931-938`) | zwei Suchfelder „Wort 1“ und „Wort 2“ mit UND: gehen, sind aber unbequem und mischen Übersetzungen |
| 5 | Nachbarkapitel bestimmen (Kapitelwechsel) | Odoo kennt keine Reihenfolge „nächstes Kapitel“ über Buchgrenzen; die Listenknöpfe selbst sind Bordmittel (Nr. 23) | Suche `searchpanel_default` und `display="always"` in `docs/odoo/addons/web/static/src` und `list_controller.xml`: Knopf und Vorbelegung des Searchpanels vorhanden, keine Kapitelfolge | Klick im Baum (Plan Variante A): geht ohne Eigenbau, ist aber ein Klick mehr je Kapitel |

## Noch zu füllen

Beim Bau jedes Schrittes: Status (gebaut, getestet, abgenommen) je Zeile und neue Zeilen für Bausteine, die der Plan noch nicht kennt.
