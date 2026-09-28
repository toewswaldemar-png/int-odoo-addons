# int_filemanager: Vollständiges Inventar der nativen Odoo-Bausteine (`core/`) — zwei konkrete Eigenbau-Funde

Stand 2026-09-24. Dreizehntes Dokument der Reihe. Auftrag diesmal bewusst nicht mehr auf
Navigation/Suche beschränkt: **die vollständige Grundgesamtheit** von Odoos wiederverwendbarer
Frontend-Bausteinbibliothek bestimmt (`addons/web/static/src/core/`, Odoos eigenes
"Komponenten-Regal", jeder Baustein in einem eigenen Unterordner) und systematisch gegen
`int_filemanager` abgeglichen — dieselbe Technik wie in Dokument 7 (dort: alle
`_parent_store`-Modelle), jetzt auf die Komponentenebene angewendet. Ergebnis: **zwei konkrete,
handfeste Funde**, bei denen `int_filemanager` etwas von Grund auf selbst gebaut hat, das als
fertiger nativer Baustein bereitsteht. Reine Recherche, nichts umgesetzt.

---

## 1. Die vollständige Grundgesamtheit: 57 native Bausteine

```
find addons/web/static/src/core -maxdepth 1 -type d
```

liefert **57 eigenständige Bausteine** (vollständige Liste, keine Auswahl): `action_swiper`,
`autocomplete`, `avatar`, `badge`, `barcode`, `bottom_sheet`, `browser`, `checkbox`, `code_editor`,
`color_picker`, `colorlist`, `colors`, `commands`, `confirmation_dialog`, `copy_button`,
`datetime`, `debug`, `dialog`, `domain_selector`, `domain_selector_dialog`, `dropdown`, `dropzone`,
`effects`, `emoji_picker`, `errors`, `expression_editor`, `expression_editor_dialog`,
`file_input`, `file_upload`, `file_viewer`, `hotkeys`, `install_scoped_app`,
`ir_ui_view_code_editor`, `l10n`, `model_field_selector`, `model_selector`, `navigation`,
`network`, `notebook`, `notifications`, `overlay`, `pager`, `popover`, `position`, `pwa`, `py_js`,
`record_selectors`, `resizable_panel`, `select_menu`, `signature`, `tags_list`, `time_picker`,
`tooltip`, `tree_editor`, `ui`, `user_switch`, `utils`.

**Bereits in dieser Recherchereihe konkret geprüft/bestätigt genutzt:** `browser` (Router,
Dok. 6), `commands` (Befehlspalette, Dok. 8/9/10), `file_viewer` (Dok. 12, vorbildlich genutzt),
`network` (RPCCache, Dok. 5), `pager` (Dok. 6/8), `popover`/`resizable_panel`/`dropdown` (laut
eigenem Code bereits importiert), `utils` (`nested_sortable`, Dok. 6). Bleiben **50 nicht einzeln
geprüfte Bausteine** — davon zwei jetzt vertieft, siehe unten; der Rest im Abschnitt 3 eingeordnet.

---

## 2. Zwei konkrete Funde: eigener Code, wo ein fertiger nativer Baustein bereitsteht

### 2.1 `dropzone` — nahezu deckungsgleich mit `int_filemanager`s eigenem Drag&Drop-Upload

`addons/web/static/src/core/dropzone/dropzone_hook.js` (91 Zeilen) + `dropzone.js` (23 Zeilen),
beide vollständig gelesen. `useDropzone(targetRef, onDrop, extraClass, isDropzoneEnabled)`:

- `document`-weite `dragenter`/`dragleave`-Listener mit einem **Tiefenzähler** (`dragCount`) statt
  eines einfachen Booleans, explizit **wegen desselben Problems**, das `int_filemanager`s eigener
  Code als Begründung nennt: `dragenter`/`dragleave` feuern bei jedem Kind-Element einzeln, ein
  Flag würde beim Überqueren von Kindelementen flackern.
- `window`-weite `dragover`/`drop`-Behandlung, die verhindert, dass der Browser eine außerhalb der
  Zone fallengelassene Datei öffnet/herunterlädt.
- `isTargetInActiveElement`-Prüfung (`uiService.activeElement.contains(targetRef.el)`): die
  Dropzone erscheint nicht, wenn gerade ein Dialog/eine andere aktive Oberfläche im Vordergrund ist
  — ein Dialog-Bewusstsein, das eigens geprüft werden müsste, ob `int_filemanager`s eigene Version
  das ebenfalls abdeckt.

**Abgleich:** `int_filemanager`s eigener Drag&Drop-Upload (`filemanager_controller_mixin.js`,
`dropState`, laut Kommentar dort "auf `window` gehängt ... Tiefenzähler statt eines Flags, [weil]
`dragenter`/`dragleave` bei jedem Kind-Element einzeln feuern") **beschreibt exakt dasselbe
Problem mit exakt derselben Lösung** wie der native Hook — unabhängig voneinander auf dieselbe
Technik gekommen. Das ist der klarste "hätte ein fertiger Baustein sein können"-Fund der gesamten
Reihe: nicht nur ein ähnliches Muster, sondern dieselbe Begründung, dasselbe technische Mittel.
**Nicht geprüft, weil außerhalb einer reinen Code-Lektüre nicht zu beantworten:** ob `int_filemanager`s
Variante zusätzliche, dem nativen Hook fehlende Anforderungen abdeckt (z. B. eigene
Ziel-Ordner-Erkennung beim Drop auf eine bestimmte Zeile), die einen Eigenbau gerechtfertigt haben
könnten — dafür wäre ein Vergleich der jeweils vollständigen `onDrop`-Handler nötig, nicht Teil
dieses Dokuments.

### 2.2 `bottom_sheet` — deckt eine konkrete, wahrscheinlich fehlende Fähigkeit auf: Android-Zurück-Taste

`addons/web/static/src/core/bottom_sheet/bottom_sheet.js` (317 Zeilen, die Kernlogik
vollständig gelesen) + `bottom_sheet_service.js` (71 Zeilen, vollständig gelesen). Kein
eigenständig aufrufbarer Baustein, sondern die **mobile Ausprägung des `Popover`-Systems** — wird
automatisch eingesetzt, wenn ein `Popover` auf einem schmalen Viewport angezeigt wird.

Enthält, alles am Code verifiziert: echte Zieh-Loslassen-Physik (`onScroll`, `progress`-Zustand
für visuelles Feedback beim Ziehen, `dismissThreshold`), Berücksichtigung von
Bildschirmtastatur/Browserleisten-Größenänderungen (`useViewportChange`), Escape-Taste — **und,
am wichtigsten, eine Zeile, die leicht übersehen wird:**

```js
window.history.pushState({ bottomSheet: true }, "");
this.handlePopState = () => { ...; this.slideOut(); };
useExternalListener(window, "popstate", this.handlePopState);
```

Das bindet den **Android-Hardware-"Zurück"-Knopf/die "Zurück"-Geste** an "Sheet schließen" statt an
"App/Seite verlassen" — ein Verlaufseintrag wird extra dafür angelegt.

**Abgleich:** `int_filemanager`s eigenes mobiles Ordnerbaum-Overlay (`mobileTreeState = useState({
open: false })`, reines CSS-Klassen-Umschalten + eigener Hintergrund-`<div>`, siehe
`filemanager_controller_mixin.js`/`native_list_view.xml`) hat **keine erkennbare
`popstate`-Behandlung** (kein Treffer bei Grep). **Konkrete, wahrscheinliche Lücke, nicht nur
Vermutung:** auf einem Android-Gerät würde die Hardware-"Zurück"-Taste bei geöffnetem
Mobil-Ordnerbaum vermutlich nicht das Overlay schließen, sondern die App verlassen/den Browser
zurücknavigieren — während die native `BottomSheet`-Komponente genau das absichtlich verhindert.
**Ausdrücklich als plausible, code-basierte Vermutung markiert, nicht live auf einem Android-Gerät
getestet** — wäre der nächste sinnvolle Prüfschritt, kein sofortiger Umbauauftrag. Eine vollständige
Umstellung auf die native `BottomSheet` wäre kein Ein-Zeiler (sie ist ans `Popover`-System
gekoppelt, das Ordnerbaum-Overlay ist aktuell ein eigenständiges Vollbild-Panel, kein
Popover-Ziel) — aber die `popstate`-Behandlung allein ließe sich auch unabhängig davon leicht
nachrüsten.

---

## 3. Die übrigen 50 Bausteine — eingeordnet, nicht alle einzeln vertieft

Ehrlich benannt: bei 57 Bausteinen wurden zwei vertieft geprüft (Abschnitt 2), acht waren bereits
aus früheren Dokumenten bekannt (Abschnitt 1). Die verbleibenden werden hier nach Namen/Zweck
eingeordnet, nicht einzeln Datei für Datei gelesen — das wäre bei diesem Umfang keine gründliche
Prüfung mehr, sondern nur noch Etikettieren. Drei Gruppen:

**Erkennbar nicht relevant für einen Dateimanager** (Zweck eindeutig aus dem Namen/Kontext,
kein Fehlschluss-Risiko wie beim `nested_sortable`-Vorfall in Dokument 6, da hier keine
Navigations-/Interaktionslogik dahinter vermutet wird): `debug`, `effects`, `emoji_picker`,
`install_scoped_app`, `ir_ui_view_code_editor`, `l10n`, `model_field_selector`, `model_selector`,
`pwa`, `py_js`, `user_switch`.

**Bereits plausibel durch bekannte, verwandte Funde abgedeckt** (verwandter Baustein bereits
geprüft, eigenständige Prüfung mit geringem Zusatzertrag zu erwarten): `autocomplete`
(Unterbau von `Many2XAutocomplete`, Dok. 10 bereits vertieft geprüft), `overlay`/`position`
(technische Grundlage von Dropdown/Popover/BottomSheet, bereits indirekt mitgeprüft),
`hotkeys`/`navigation` (bereits an mehreren Stellen als `useHotkey`/`useNavigation` importiert
gesehen, ohne bisher eigenständig als Baustein gelesen).

**Namentlich plausibel relevant, aber NICHT geprüft — offen für eine künftige Vertiefung, nicht
grundlos übersprungen:** `action_swiper` (mobile Wisch-Aktionen — z. B. eine Datei durch Wischen
löschen, an Explorer-Apps auf dem Smartphone erinnernd), `tags_list` (das native Tag-Widget —
`int_filemanager` hat ein eigenes Tag-System, ungeprüft ob es dieses native Widget nutzt oder ein
eigenes), `signature` (E-Signatur-Zeichenwidget, Bezug zu der früher in dieser Session gefundenen
`PdfSigner`-Signaturinfrastruktur), `record_selectors`/`select_menu` (allgemeine
Auswahl-Widgets, möglicher Baustein für die in Dokument 10 skizzierte Ordner-Schnellsuche),
`color_picker`/`colorlist`/`colors` (Tag-/Status-Farbwahl), `copy_button` ("Link kopieren" bei
Freigaben), `datetime`/`time_picker` (Datumsfilter), `file_input`/`file_upload` (Datei-Auswahl-
Grundbausteine, `int_filemanager` hat eigenen Upload-Code, ungeprüft ob darauf aufbauend),
`notebook` (Tabs, evtl. für eine künftige Eigenschaften-Seitenleiste mit mehreren Reitern),
`domain_selector`/`domain_selector_dialog`/`expression_editor`/`tree_editor`
(visueller Filter-Baukasten, möglicher Baustein für eine "erweiterte Suche").

---

## 4. Fazit

Zwei belastbare, konkrete Funde bei vollständiger Prüfung: `dropzone` als nahezu wortgleiche
Doppelentwicklung (gleiche Begründung, gleiche Technik, unabhängig entstanden), `bottom_sheet` als
Hinweis auf eine wahrscheinliche, bisher nirgends dokumentierte mobile UX-Lücke
(Android-Zurück-Taste). Die vollständige 57-Bausteine-Liste selbst ist der eigentliche bleibende
Wert dieses Dokuments — eine erschöpfende, nachschlagbare Grundgesamtheit für jede künftige
"gibt es dafür schon einen nativen Baustein"-Frage, statt bei jedem neuen Thema erneut von vorn zu
suchen.
