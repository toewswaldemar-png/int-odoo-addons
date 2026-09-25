# int_filemanager: Vollständige Bestandsaufnahme der nativen Odoo-Listenansicht (Server + Client)

Stand 2026-09-24. Wie bei der Bildverarbeitungs-Prüfung **vollständig, nicht stichprobenartig**:
jede Datei des nativen List-View-Moduls im lokal geklonten Odoo-19-Kern
(`C:\Users\Admin\Documents\GitHub\odoo`, `origin/19.0`, Commit `2e2acfd6`) sowie `int_filemanager`s
eigene Listen-Dateien wurden vollständig gelesen — `list_renderer.js` (2312 Zeilen),
`list_controller.js` (590 Zeilen), `column_width_hook.js` (572 Zeilen), `list_arch_parser.js`
(251 Zeilen) auf Odoo-Seite; `native_list_view.js` (94 Zeilen) und `native_list_renderer.js`
(502 Zeilen) auf `int_filemanager`-Seite. Reine Recherche, nichts umgesetzt.

---

## 1. Ausgangslage — anders als bei der Bildverarbeitung: bereits nativ, nicht Eigenbau

Der wichtigste Unterschied zur Bildverarbeitungs-Prüfung: **`int_filemanager`s Listenansicht ist
bereits Odoos native `ListView`/`ListController`/`ListRenderer`**, nicht neu gebaut. Bestätigt durch
den Kopfkommentar in `native_list_view.js` selbst: *"A real Odoo list view, bound directly to
int_filemanager.file"*. Registriert wird sie ganz reguär über die View-Registry
(`registry.category("views").add("int_filemanager_list", {...listView, Controller: ...,
Renderer: ..., SearchModel: ...})`) — echte Unterklassen von `ListController` und `ListRenderer`,
keine Kopie, kein `patch()`. Sortierung, optionale Spalten (inkl. Properties-Aufteilung), Pager sind
laut eigenem Kommentar *"untouched native ListView behaviour"*.

Die Fragestellung ist hier also nicht "was fehlt, das nativ existiert", sondern präziser: **welche
der ca. 500 Zeilen eigener `native_list_renderer.js`-Logik dupliziert etwas, das die von ihr
geerbte Basisklasse bereits mitbringt — und welche nativen Bausteine (Aggregate, Archivieren,
Export, Dekorationen) werden noch gar nicht genutzt, obwohl sie sich anbieten würden.**

---

## 2. Vollständige Fähigkeitskarte der nativen `ListRenderer`/`ListController`

| Bereich | Fundstelle | Status bei `int_filemanager` |
|---|---|---|
| Sortierung (Klick auf Spaltenkopf) | `list_renderer.js:1194` `onClickSortColumn`, `:909` `isSortable` | genutzt, unverändert |
| Optionale Spalten ein-/ausblenden | `:630-665` `optionalFieldGroups`/`hasOptionalFields` | genutzt, unverändert |
| **Spalten-Größenänderung per Drag** | `column_width_hook.js` (572 Zeilen, eigenes Freeze-/Auto-Width-System), Ziehgriff `.o_resize` in `list_renderer.xml:40` | **vollständig nativ vererbt, kein eigener Code** — automatische Breitenoptimierung beim ersten Rendern, manuelles Ziehen überschreibt sie bis zum nächsten Fensterresize/Spaltenwechsel (bewusst NICHT persistent, kein `localStorage`-Fund) |
| Gruppierung mit Aggregaten | `:692-786` `computeAggregates`, `:828` `formatGroupAggregate` | **ungenutzt** — siehe Abschnitt 4 |
| **Spalten-Summe/-Mittelwert per Arch-Attribut** | `:692-786`, Attribute `sum`/`avg`/`max`/`min` auf `<field>` | **ungenutzt**, direkt für „Speicherplatz-Dashboard“ nutzbar (Abschnitt 4) |
| Tastatur-Navigation (Pfeiltasten, Tab, Enter) | `:1225-1978` (`onCellKeydown*`-Familie, ~750 Zeilen) | vollständig vererbt; **kein natives Delete/F2** (Abschnitt 5) |
| Tastatur-Bereichsauswahl (Shift+Pfeil) | `:1530` `expandCheckboxes`, `:1575` `applyCellKeydownMultiEditMode` | vererbt, funktioniert automatisch mit `int_filemanager`s Checkbox-Spalte |
| **Touch-Long-Press zum Auswählen** | `:2190-2221` `onRowTouchStart/-End/-Move`, `:105` `LONG_TOUCH_THRESHOLD = 400`, verdrahtet in `list_renderer.xml:279-281` (`t-on-touchstart`/`-end`/`-move` auf jeder `<tr>`) | **bereits aktiv, geerbt — parallel zu eigenem Long-Press-Code**, siehe Abschnitt 3 |
| Zeilen per Drag umsortieren (`handle`-Feld) | `:468` `canResequenceRows`, `:2232-2290` `sortStart/-Stop/-Drop` | nicht anwendbar (keine manuelle Reihenfolge in `int_filemanager`), zu Recht ungenutzt |
| Inline-Zelleneditierung + Mehrfachbearbeitung | `:1404` `isInlineEditable`, `:1575` `applyCellKeydownMultiEditMode` | bewusst deaktiviert (Listenzeilen sind reine Anzeige, Umbenennen läuft über ein eigenes Namensfeld-Widget) |
| Bedingte Zeilen-/Zellen-Formatierung (`decoration-*`) | `list_arch_parser.js`, ausgewertet in `list_renderer.js:931` `getRowClass` | **ungenutzt** — deklarativ per Python-Ausdruck im Arch, kein JS nötig |
| **Archivieren/Dearchivieren als fertiger Menüpunkt** | `list_controller.js:446-460` `getStaticActionMenuItems` (`archive`/`unarchive`, `toggleArchiveWithConfirmation`) | **ungenutzt, aber direkt relevant** — siehe Abschnitt 6 (Bezug zu heutigem DB-Vorrang-Fund) |
| Löschen mit Bestätigungsdialog | `:265` `deleteConfirmationDialogProps`, `:461-467` | teilweise genutzt (eigene `delete()`-Route, aber der native Bestätigungsdialog-Baustein wäre wiederverwendbar) |
| Export (XLSX/CSV beliebiger Felder) | `:269` `getExportableFields`, `export_all/export_all.js` | ungenutzt, kein akuter Bedarf erkennbar |
| Globaler Klick-Handler | `:2127` `onGlobalClick` | **kein Überschneidung** — reagiert nur bei aktiver Inline-Bearbeitung (`editedRecord`), die bei `int_filemanager` nie aktiv ist; eigener `onDocumentClick`-Deselect-Handler in `native_list_renderer.js` deckt einen anderen Fall ab |

---

## 3. Konkreter Verdachtsfund: zwei parallele Long-Press-Mechanismen

**Nativ, geerbt, aktiv** (`list_renderer.js:2190-2221`, verdrahtet in `list_renderer.xml:279-281`):
jede `<tr>` hat bereits `t-on-touchstart`/`-touchend`/`-touchmove` auf `onRowTouchStart`/`-End`/
`-Move`, die bei 400ms Haltezeit (`LONG_TOUCH_THRESHOLD`) `toggleRecordSelection(record)` aufrufen.
`IntFilemanagerListRenderer` überschreibt keine dieser drei Methoden — sie laufen also unverändert
mit.

**Zusätzlich eigener Code** (`native_list_renderer.js:357-406`): ein komplett separater
`pointerdown`/`pointermove`/`pointerup`-Mechanismus mit eigenem 500ms-Timer, der bei
`env.isSmall && !this.props.list.selection.length` ebenfalls `record.toggleSelection(true)`
aufruft. Der Code-Kommentar begründet das damit, dass Odoos natives Verhalten nur das *Umschalten
weiterer* Zeilen übernehme, sobald schon etwas ausgewählt ist — impliziert also, dass die allererste
Auswahl (0→1) über den nativen Touch-Pfad zu diesem Zeitpunkt nicht (mehr) zuverlässig funktionierte.

**Nicht abschließend geklärt, weil nicht live getestet:** auf einem echten Touch-Gerät feuern für
denselben physischen Kontakt sowohl `touchstart` als auch `pointerdown` (Browser senden beide
Ereignisfamilien für Touch-Interaktionen) — das native 400ms-Timeout griffe demnach ca. 100ms VOR
dem eigenen 500ms-Timeout und würde die Auswahl bereits auslösen, bevor der eigene Code überhaupt
zum Zug kommt. Der eigene Timer würde dann 100ms später nochmals `toggleSelection(true)` auf einen
bereits ausgewählten Datensatz anwenden (vermutlich folgenlos) und zusätzlich `render()` aufrufen.
Ob der ursprüngliche Beweggrund (native Erstauswahl unzuverlässig) noch zutrifft oder aus einer
älteren Odoo-Version/einem inzwischen behobenen Zustand stammt, lässt sich ohne Gerätetest nicht
sicher sagen — **empfohlen: gezielt auf einem echten Touch-Gerät prüfen, ob der eigene
Long-Press-Block (Zeilen 357-406) noch gebraucht wird**, bevor er als notwendiger Eigenbau gilt.

---

## 4. Ungenutzter nativer Baustein mit direktem Bezug zu einer offenen Feature-Idee: Aggregate

`computeAggregates()` (`list_renderer.js:692-786`) wertet pro Spalte ein `sum`/`avg`/`max`/`min`-
Attribut im Arch aus und zeigt automatisch eine Fußzeile mit dem Ergebnis — **umgerechnet neu bei
jeder Auswahl** (nur ausgewählte Zeilen) **und pro Gruppe**, wenn gruppiert wird. Für die in
`int_filemanager_feature_ideen_2026-09-21.md` (Abschnitt D) skizzierte Idee
"Speicherplatz-Dashboard" bedeutet das: ein `sum="Gesamtgröße"`-Attribut auf der bestehenden
`size`-Spalte liefert bereits "Summe der markierten Dateien" und "Summe je Ordner (bei Gruppierung
nach Ordner)" **ganz ohne eigenen Code** — kein Dashboard-View nötig für diesen Teilaspekt, nur ein
Arch-Attribut auf einer bereits vorhandenen Spalte.

---

## 5. Bestätigte echte Lücke: kein natives Delete/F2 in der Tastatursteuerung

Vollständig gelesen: `onCellKeydownReadOnlyMode` (`list_renderer.js:1851-1974`, der für
nicht-editierbare Listen wie `int_filemanager` relevante Zweig). Abgedeckt: Pfeiltasten (volle
Grid-Navigation), Tab/Shift+Tab (Gruppenknopf-Navigation), Shift+Pfeil (Tastatur-Bereichsauswahl),
Shift+Leertaste (Auswahl umschalten), Enter (öffnen bzw. Inline-Bearbeitung starten bzw. das native
Lösch-Icon in der Zelle auslösen, `o_list_record_remove`). **Kein `case` für eine reine Entf-Taste,
kein `case` für F2.** Bestätigt exakt die in `int_filemanager_feature_ideen_2026-09-21.md`
(Abschnitt C) skizzierte Lücke "Tastenkürzel (Entf/F2/Strg+C/V/X)" als echten, nicht durch native
Bordmittel abgedeckten Aufwand — hier also zu Recht noch offen, kein Eigenbau-Vermeidungsfund.

---

## 6. Wichtigster Einzelfund: direkter Bezug zur heutigen DB-Vorrang/Papierkorb-Recherche

`getStaticActionMenuItems()` (`list_controller.js:430-470`) definiert **fertige, sofort nutzbare
Menüpunkte** "Archive"/"Unarchive" im nativen Aktionen-Dropdown (`this.model.root.
toggleArchiveWithConfirmation(true/false, this.archiveDialogProps)`) — automatisch verfügbar für
jedes Modell mit einem `active`-Feld, inklusive nativem Bestätigungsdialog. Das Aktionen-Dropdown
selbst wird in `int_filemanager` bereits genutzt (`native_list_renderer.js` referenziert
`.o_cp_action_menus` explizit in den Rubberband-/Deselect-Ausnahmeregeln).

**Das ist ein unabhängiger, zusätzlicher Fund** zu der bereits in
`int_filemanager_konzept_db_vorrang_2026-09-24.md` (Abschnitt 16.1) vorgeschlagenen Migration von
`trashed` (eigenes Boolean) zu nativem `active` — dort war die Begründung Fund B1 (Vollscan löscht
Papierkorb-Einträge versehentlich endgültig). Über die Listenansicht-Prüfung kommt jetzt ein
zweiter, eigenständiger Vorteil derselben Migration hinzu: **"In den Papierkorb verschieben" und
"Wiederherstellen" als Mehrfachauswahl-Aktion wären mit `active` ein reiner Konfigurationsschritt
(Menüpunkt aktivieren) statt eigenem Controller-Code** — beide Funde stützen sich gegenseitig,
gefunden über zwei komplett unabhängige Recherchewege (Scan-Sicherheit vs. UI-Bausteine).

---

## 7. Was zu Recht Eigenbau bleibt

Vollständig gegen die native Basisklasse geprüft, keine Überschneidung gefunden:

- **Datei-Explorer-Klicksemantik** (Einzelklick=auswählen statt öffnen, Doppelklick=öffnen) — Odoos
  Standardverhalten öffnet bei Einzelklick immer (eigener Kopfkommentar in
  `native_list_renderer.js` verweist korrekt auf das native `onCellClicked` als Gegenbeispiel).
- **Rubberband-Auswahl** (Ziehen über leeren Platz) — in der nativen `ListRenderer` nirgends
  vorhanden, reine Desktop-Explorer-Ergänzung.
- **Klick außerhalb deselektiert alles** — kein natives Äquivalent (das nativ vorhandene
  `onGlobalClick` dient einem anderen Zweck, siehe Tabelle oben).

Diese drei Bausteine sind nach vollständiger Prüfung tatsächlich notwendiger Eigenbau, keine
Dopplung vorhandener Odoo-Funktionalität.
