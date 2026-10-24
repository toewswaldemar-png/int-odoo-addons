# int_filemanager: Bildeditor (Erkenntnisse)

Der Bildeditor ist umgesetzt. **Der Code ist maßgeblich** (`static/src/image_editor/`, dazu `models/int_filemanager_document.py` und `controllers/int_filemanager.py` für den gespeicherten Zustand). Diese Datei hält nur fest, was der Code nicht zeigt: Entscheidungen, Sicherheitsgründe, Grenzen und die Stolpersteine, auf die wir gestoßen sind.

**Ziel:** Ein Bild eines Dokuments bearbeiten (zeichnen, beschriften, Filter, zuschneiden, Teile verdecken) und als **neues Dokument** im selben Ordner speichern. Das Original bleibt. Die Markierungen bleiben beim nächsten Öffnen als Objekte verschiebbar.

## 1. Entscheidungen

1. **Fabric.js 7.4.0** (`static/lib/fabric/fabric.js`, MIT), nur in einem eigenen Bundle `int_filemanager.assets_image_editor`. Es wird beim ersten Klick auf „Bearbeiten“ geladen (`lazy_components`), nicht mit jeder Seite. Gäste laden es nie. Ein Test hält die Version fest; wer Fabric tauscht, prüft den Editor dagegen und ändert die Zahl in `tests/test_assets.py`.
2. **Der Editor ist ein Dienst** (`int_filemanager.image_editor`), den der Viewer von selbst findet. So haben Liste, Kanban, Kontextmenü und Formular denselben Knopf „Bearbeiten“; die Gäste-Seite hat den Dienst nicht und damit keinen Knopf.
3. **Die Szene hat die Größe des Bildes.** Alle Marken liegen in Bildpunkten. Die Größen (Strichstärke, Schrift) richten sich nach dem Bild (`UNIT_PER_PIXEL`), damit sie auf einem Foto und auf einem Symbol gleich aussehen.
4. **Große Bilder:** Gezeigt und gefiltert wird eine Arbeitskopie (längste Seite höchstens 2048 Pixel). Das Bild in voller Größe kommt nur beim Speichern an die Stelle der Kopie (`Picture.show(true)`); die Filter laufen dann noch einmal darauf. Ob der Browser ein Canvas dieser Größe machen kann, wird ausprobiert (`canvasFits`); sonst bietet der Speichern-Dialog nur die Größen an, die gehen.
5. **Zuschnitt, Drehen und Spiegeln ändern das Bild nicht.** Der Zuschnitt ist ein Ausschnitt (`crop`), gespeichert wird nur er. Drehen und Spiegeln drehen das Bild und alle Marken mit (`scene_ops.js`); ein Text bleibt beim Spiegeln lesbar.
6. **Verdecken ist eine Marke** (`RedactMark`): Sie speichert Ort, Art (Pixel, Weichzeichnen, schwarz) und Stärke, nicht die Pixel; der verdeckte Teil wird aus dem Bild gezeichnet. In der gespeicherten Datei ist er endgültig weg, im **Ausgangsbild** nicht (siehe 3.).
7. **Der Zustand wird mit dem Bild gespeichert** (`edit_state`, JSON, höchstens 8 MiB) samt dem Ausgangsbild (`edit_source_id`). Öffnet man ein so gespeichertes Bild, lädt der Editor das **Ausgangsbild** mit den Marken darauf. Ein weiteres Speichern zeigt wieder auf dasselbe Ausgangsbild, die Kette wird nicht länger.
8. **Rückgängig** hält 50 Zustände als JSON-Text. Ein Zustand ist: Lage des Bildes, Filter, Zuschnitt und alle Marken.

## 2. Sicherheit

- `edit_state` und `edit_source_id` sind nur dem Speicher zu setzen (`STORAGE_FIELDS`) und nur für Systemverwalter lesbar (`groups`). Der Editor liest sie über `get_edit_session`.
- **Das Ausgangsbild bekommt nur, wer es lesen darf** (seine Regeln, nicht archiviert). Sonst startet der Editor mit dem flachen Bild; was jemand mit Zugriff auf das bearbeitete Bild sehen darf, hängt so nicht vom Ausgangsbild ab.
- Beim Hochladen prüft der Server: JSON-Objekt, höchstens 8 MiB, Ausgangsbild lesbar für den Nutzer. Sonst wird das Bild flach gespeichert (oder mit Fehler 400, wenn der Zustand kaputt ist).
- **Ein gespeicherter Zustand ist keine vertrauenswürdige Eingabe** (ein Nutzer hat ihn geschrieben, ein anderer öffnet ihn). `edit_state.js` lässt nur die Marken zu, die der Editor selbst macht, wirft `clipPath` und Filter weg, und ein Bild oder Muster darin muss seine Daten mitbringen (`data:image/...`). Sonst würde der Browser beim Öffnen eine fremde Adresse laden.
- Eingefügte Bilder werden vorher auf höchstens 1024 Pixel verkleinert.
- **Eingefügte SVG-Dateien werden vor dem Lesen bereinigt** (`sanitizeSvg`): Fabric lädt jedes Bild, das eine Zeichnung nennt, schon beim Lesen des Textes nach. Eine fremde Zeichnung könnte den Browser so zu Anfragen an einen Server ihres Urhebers bringen. Bilder und Verweise ohne eingebettete Daten, `url(...)` nach außen, `@import`, Skripte und Ereignis-Attribute fallen weg; danach läuft die Zeichnung durch denselben Filter wie ein gespeicherter Zustand.

## 3. Grenzen

- GIF wird nicht bearbeitet (die Bilder der Animation gingen verloren). SVG als Ausgangsbild gibt es nicht (ist Text im Modul).
- Ein Bild, das größer ist als der Browser zeichnen kann (auf dem Handy früh), wird kleiner gespeichert. Der Dialog sagt es.
- Der Zustand wächst mit eingefügten Bildern. Ist er größer als 8 MiB, wird das Bild ohne ihn gespeichert; der Dialog sagt es vorher.
- Kein Radierer (Fabric 7 bringt ihn nicht mit). Marken löscht man, Teile des Bildes verdeckt man.
- Zwei Finger zoomen und verschieben (wie im Viewer). Zeichnet gerade ein Finger, wird das abgebrochen, sobald der zweite aufliegt.

## 4. Stolpersteine (Fabric 7.4.0, Owl)

1. `toCanvasElement` und `toSVG` lesen den Ausschnitt **im Raum der Ansicht**: bei Zoom steckte die Bildschirmansicht in der Datei. Vorher die Ansicht auf die Einheitsmatrix setzen (`withPlainView`).
2. `getBoundingRect()` liest zwischengespeicherte Koordinaten; eine frisch gezogene Marke ohne Rand hatte darin Größe 0. Der Zugweg des Zeigers entscheidet, nicht die Box.
3. `Group.removeAll()` lässt bei Teilen, deren Ursprung nicht die Mitte ist, falsche `left`/`top`-Werte zurück. `arrange.ungroup` rechnet die Lage aus den Matrizen aus.
4. Fabric 7 wendet die Standardwerte (`ownDefaults`) einer **eigenen Unterklasse** nicht an. `RedactMark` gibt sie im Konstruktor als Optionen mit.
5. **Owl-Templates kennen `Number`, `String` und `Boolean` nicht**; `Math` geht. Die Handler lesen die Werte in der Komponente.
6. **Odoo malt jedes `.modal` halb schwarz** (`.modal:not([data-bs-backdrop="false"])`). Der Editor setzt `data-bs-backdrop="false"` und malt seinen Grund selbst.
7. **Odoo 19 kennt das Dark-Theme von Bootstrap nicht**; es nutzt `--body-color`, `--body-bg`, `--border-color`, `--primary`. Der Editor nutzt diese Variablen mit Rückfallwerten.
8. **Die Dialoge von Odoo lagen hinter dem Editor** (beide `.modal` mit `z-index` 1055, was später im DOM steht, liegt oben). Der Editor liegt bei 1054; ein Test prüft die Regel. Der Viewer schließt sich, wenn der Editor sich öffnet (`useDocumentFileViewer`).
9. **`after:render` kommt auch für die obere Fläche.** Das Overlay (Rahmen, Raster, Führungslinien) wird nur auf die untere Fläche gemalt (`paintOverlay`), sonst bleiben Geister-Rahmen stehen.
10. **Außerhalb des Bildes wird nicht gezeichnet**, und Marken lassen sich nicht aus dem Bild schieben (`keepMarkInside`); eine Marke ganz außerhalb wäre nicht mehr zu greifen.
11. **`object:moving` kommt, bevor Fabric die Koordinaten ausrechnet.** Die Handler rufen `setCoords()` selbst vorher auf (`freshBox`, `constrainMoving`), sonst flackert eine Korrektur am Rand.
12. **Fabrics Mauszeiger für die Eckgriffe hängen vom Seitenverhältnis ab**; `controls.js` leitet den Zeiger aus der Ecke und dem Drehwinkel ab.
13. **Fabrics Objekt-Cache macht vergrößerte Marken unscharf** (kein Neuzeichnen beim Ziehen, Cache auf etwa zwei Millionen Pixel begrenzt, auch beim Speichern). Alle Marken werden deshalb ohne Cache gezeichnet (`objectCaching: false`).
14. **Fabrics Griffe strecken Text.** Der Editor blendet bei Text die Griffe aus, die verzerren (`setTextHandles`), setzt `uniScaleKey: null` und rechnet die Skalierung beim Loslassen in die Schriftgröße ein (`bakeTextScale`).

Aussehen: Die Kopfleiste ist die des Dateiviewers (dunkel), darunter ist alles hell wie Odoos eigene Panels. Die Werkzeuge links sind fünf einzelne Knöpfe und drei Dropdowns von Odoo (Zeichnen, Text, Formen; der Knopf zeigt das zuletzt benutzte Werkzeug), damit die Spalte kurz bleibt. Die Abschnitte rechts klappen (`<details>`), die Griffe der Marken haben Fabrics hellblauen Standardlook (`CONTROL_LOOK`).

Die Teile des Editors, die nur Zahlen und Fabric brauchen (`geometry`, `filters`, `history`, `snapping`, `edit_state`, `marks`, `scene_ops`, `arrange`, `export`), kann man ohne Browser mit jsdom und `@napi-rs/canvas` laufen lassen; so sind die Stolpersteine 1 bis 5 gefunden worden (6 und 7 zeigen sich nur im echten Odoo-CSS).

## 5. Prüfung

Tests: `tests/test_assets.py` (Bundle, Version von Fabric, Gäste-Bundle ohne Editor), `tests/test_document_upload.py` (gespeicherter Zustand), `static/tests/image_editor/` (Hoot) und `tools/image_editor_check/` (Node, ohne Browser; Aufbau dort im README). Nicht im Browser geprüft ist, was nur das echte Odoo-CSS zeigt.
