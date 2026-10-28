# Dateimanager: Verbesserungen der Oberfläche

Grundlage: Screenshot der Dokumentenliste (Odoo 19, Deutsch) und der Code von `int_filemanager`
(Frontend unter `static/src/int_filemanager/`, Views in `views/int_filemanager_document_views.xml`).
Das Mockup dazu liegt in `docs/int_filemanager/mockup/` (siehe dort `README.md`).

**Lesen und Testen:** Alles unten ist aus Screenshot und Code gelesen. Nichts davon wurde in Odoo
gebaut oder getestet; das Mockup ist eine eigenständige Owl-Demo ohne Odoo-Anbindung. Die Odoo-Tests
und die Hoot-Tests des Moduls wurden nicht angefasst.

## Befunde

| # | Befund | Beleg | Vorschlag |
|---|--------|-------|-----------|
| 1 | Schwarzer Punkt links im Suchpanel (zwischen Ordnerbaum und „Tags“). Wahrscheinlich der Menü-Anker als `<li>`: `position: fixed` mit Größe 0 versteckt die Aufzählungsmarke eines `li` nicht sicher. Nicht im Browser nachgewiesen. | `views/search_panel/document_search_panel.xml:25`, `views/list/document_list_context_menu_renderer.scss:3` | Anker als `<span>` wie in der Liste (`document_list_context_menu_renderer.xml:21`) oder `list-style: none`. Zuerst im DOM prüfen. |
| 2 | Die Spalte „Ablageort“ zeigt den vollen Pfad und wird abgeschnitten (`Test / Anträge und Formulare / Kinderzuschlag & Wohngeld / 2025-02Kinderzuschlag / Antrag …`). Gerade der unterscheidende Teil am Ende geht verloren; bei den vielen gleichnamigen Dateien ist das die wichtigste Information. | `views/int_filemanager_document_views.xml:21` (`folder_id` mit `display_name`) | Feld-Widget: letzter Ordner fett, darüber der Pfad klein und grau, voller Pfad im Tooltip, Klick filtert den Ordner. |
| 3 | Vorschaubilder sind 1,7 em (etwa 27 px) groß. Die erste PDF-Seite ist so nicht erkennbar, alle Zeilen sehen gleich aus. | `fields/name/document_name_field.scss:5` (`--Avatar-size`), `document_name_field.js:6` (angefordert werden 64 px, serverseitig 256 px) | Etwa 38 px hoch im Hochformat (Seitenverhältnis 1:1,2), Dateityp als farbiges Etikett. Das Bild ist schon in 64 px vorhanden; retina-tauglich wären 96 px. |
| 4 | Der leere Stern steht in jeder Zeile (`optional="show"`) und ist Rauschen; nur zwei Favoriten fallen kaum auf. | `views/int_filemanager_document_views.xml:18` | Leeren Stern erst beim Überfahren zeigen (reine CSS-Regel auf `.o_data_row`). |
| 5 | Duplikate sind unsichtbar: Spalte `is_duplicated` ist `optional="hide"`, obwohl im Screenshot dieselben Namen mehrfach stehen. | `views/int_filemanager_document_views.xml:28` | Kleines Etikett „Duplikat“ im Namen (Widget kennt `is_duplicated` schon über `fieldDependencies`, muss es nur ergänzen). |
| 6 | Typfilter (PDF, Bilder, Office), Favoriten und Duplikate stecken im Filter-Dropdown. Das sind die häufigsten Filter. | `views/int_filemanager_document_views.xml:170-210` | Zeile mit Filter-Pills unter dem Control Panel, mit Zähler. In Odoo: eigene `js_class`-Control-Panel-Slot-Erweiterung, die dieselben `searchModel.toggleSearchItem`-Aufrufe nutzt (keine neue Filterlogik). |
| 7 | „Hochladen“ ist nur im Menü „Neu“ und per Drag. Ohne Ordner im Panel erscheint nur eine Warnung („Choose a folder in the panel on the left first“). | `views/list/document_list_controller.js:243`, `:382`; `document_list_controller.xml:437` | Bei „Alle“ einen Ordner-Wähler anbieten statt abzulehnen; Dropzone zeigt das Ziel bereits (`getFolderName`). |
| 8 | Die Tabelle läuft über 8 Spalten; „Geändert“ zeigt bei 18 Zeilen immer dieselbe Uhrzeit. | `views/int_filemanager_document_views.xml:26` | Relative Anzeige („Heute 12:07“, „Gestern“, „12. Okt.“), volles Datum im Tooltip. |
| 9 | Auswahl, Verschieben und Archivieren stehen im Odoo-Standardmenü „Aktionen“; nach dem Verschieben (Drag auf Ordner) gibt es keine Rückmeldung mit Undo. | `views/list/document_list_controller.js:84-100`, `views/drag/document_move.js` | Schwebende Auswahlleiste, Toast „N Dokumente verschoben · Rückgängig“ (der Rückgängig-Aufruf schreibt `folder_id` zurück). |
| 10 | Keine Detailansicht neben der Liste: Ein Klick öffnet das Formular und verlässt die Liste, Vorschau nur über das Bild. | `views/list/document_list_renderer.js:526-583` | Rechtes Detailpanel (Vorschau, Eigenschaften, Verlauf) mit Leertaste für Vollbild; der Viewer (`document_file_viewer.js`) bleibt der Vollbild-Teil. |
| 11 | Kachelgröße gibt es nur in der Kanban-Ansicht, Zeilenhöhe der Liste ist fest. | `views/kanban/document_kanban_controller.xml`, Liste ohne Pendant | Dichte-Umschalter (kompakt/komfortabel) für die Liste. |

## Was das Mockup zeigt

Dieselben Daten und dieselbe Struktur wie der Screenshot (Menüleiste, Control Panel mit „Neu“, Suche,
Pager `1–80 / 199`, vier Ansichten, Ordnerbaum, Tags, Spalten Name, Ablageort, Größe, Geändert, Tags),
dazu: Filter-Pills mit Zählern, Ablageort als Etikett mit Pfad, Seitenvorschau mit Dateityp, Stern erst
beim Überfahren, Duplikat-Etikett, Zeilenaktionen beim Überfahren, Kontextmenü, schwebende
Auswahlleiste, Detailpanel, Vollbild-Vorschau (Leertaste, Pfeiltasten), Drag auf Ordner mit
Rückgängig-Toast, Dropzone beim Ziehen von Dateien, Upload-Fortschritt, Gruppierung, Dichte,
Kacheln, Pivot, Diagramm und Dunkelmodus.

## Umsetzung in Odoo, wenn gewünscht

Reihenfolge nach Aufwand (alles mit Odoo-Mitteln: Feld-Widgets, `t-inherit`, SCSS, keine neue Bibliothek):

1. Befunde 1, 4: wenige Zeilen CSS/XML. Vorher im Browser prüfen, dass der Punkt wirklich der Anker ist.
2. Befunde 2, 3, 5, 8: Anpassung von `DocumentNameField` und ein Feld-Widget für `folder_id`.
3. Befund 6: Filter-Pills als Control-Panel-Erweiterung der Listen-`js_class`.
4. Befunde 9, 10: Auswahlleiste und Detailpanel, das größte Stück; Hoot-Tests dafür nötig.

Befund 7 (Ordner-Wähler) braucht eine Entscheidung zum Verhalten bei „Alle“ und ist deshalb nicht
nur eine Oberflächenänderung.
