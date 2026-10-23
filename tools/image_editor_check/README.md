# Prüfungen des Bildeditors ohne Browser

Prüft `int_filemanager/static/src/image_editor/` und die Einbindung in den Datei-Viewer mit Node:
das echte Fabric (`static/lib/fabric/fabric.js`), das echte Owl aus dem Odoo-Quelltext, jsdom als
Browser und `@napi-rs/canvas` als Zeichenfläche. Odoo-Dienste und die meisten Core-Komponenten
(`@web/...`) sind gestellt (`loader.mjs`); nur der Datei-Viewer des Cores und seine Template-Vererbung
laufen echt.

Das ersetzt weder die Hoot-Tests (`static/tests/image_editor/`) noch den Handtest im Browser. Es findet
Fehler in Logik, Zusammenspiel von Fabric und Owl und in den Templates, nicht solche, die nur das
echte Odoo-CSS zeigt.

## Voraussetzungen

- Node 22 oder neuer.
- Einmal `npm install` in diesem Ordner (jsdom, `@napi-rs/canvas`). Wer die Pakete schon woanders hat,
  setzt stattdessen `IMAGE_EDITOR_CHECK_MODULES` auf den Ordner, der deren `node_modules` enthält.
- Der Quelltext von Odoo 19 (`addons/web/static/lib/owl/owl.js` und `addons/web/static/src/core/...`),
  gefunden in `docs/odoo/`, in `../odoo` neben dem Repository, oder über `ODOO_SRC`. Branch und Commit
  sollten zur Installation passen (siehe `CLAUDE.md`).

## Aufruf

```bash
cd tools/image_editor_check
node run.mjs                  # alle Prüfungen
node run.mjs viewer cursors   # nur einige
```

Ein Lauf endet mit Status 1, sobald eine Prüfung `FAIL` meldet oder ein Skript mit einem Fehler
abbricht. Bilder, die die Prüfungen zur Ansicht erzeugen (`full.png`, `saved.png`,
`rotate_cursor.png`), liegen in `<Temp>/image_editor_check/`.

## Aufbau

| Datei | Inhalt |
| --- | --- |
| `run.mjs` | startet jedes Skript mit den richtigen Schaltern und zählt `PASS`/`FAIL` |
| `paths.mjs` | alle Pfade (aus dem Ort des Repositorys), Suche nach dem Odoo-Quelltext und den Paketen |
| `env.mjs` | jsdom, Fabric und die Zeichenfläche |
| `register.mjs`, `loader.mjs` | Hooks des Modul-Loaders: `@int_filemanager/...` auf die Quelldateien, Stellvertreter für `@web/...`, `@odoo/...` |
| `shim_picture.mjs` | `picture.js` mit einem `loadPicture`, das ein Bild der Prüfung liefert statt vom Server zu laden |
| `logic.check.mjs` | Geometrie, Filter, Verlauf, Zustand, Marken, Export (37) |
| `component.check.mjs` | die Komponente `DocumentImageEditor`: Zeichnen, Ziehen, Zuschneiden, Speichern (93) |
| `templates.check.mjs` | die Templates mit echtem Owl (46) |
| `svg_import.check.mjs` | Import und Bereinigung von SVG (11) |
| `viewer.check.mjs` | Datei-Viewer gegen den echten Core-Viewer samt Template-Vererbung (22) |
| `cursors.check.mjs` | Mauszeiger der Griffe, Dreh-Griff (17) |
| `sharpness.check.mjs` | Text und große Marken im Export nicht verwaschen (1) |
| `text_handles.check.mjs` | Textgriffe: Seitengriffe weg, Skalierung wird eingebacken (14) |

## Neue Prüfung

Eine Datei `<name>.check.mjs` anlegen, die mit `import "./env.mjs";` beginnt, `PASS <name>` oder
`FAIL <name>` auf die Ausgabe schreibt und in `run.mjs` in `CHECKS` eintragen. Läuft eine Prüfung
mit echtem Owl, bekommt sie `REAL_OWL: "1"`, mit dem Viewer des Cores zusätzlich `REAL_CORE_VIEWER`.
Eine neue Prüfung zuerst rot sehen (ohne die Korrektur), dann grün.
