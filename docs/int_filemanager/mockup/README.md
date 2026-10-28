# Mockup: Dateimanager mit Owl

Eigenständige Demo der Dokumentenliste von `int_filemanager`, gebaut mit Owl (`owl.js` ist die
Kopie aus `docs/odoo/addons/web/static/lib/owl`, also die Version von Odoo 19). Keine Verbindung zu
Odoo, die Daten stehen in `data.js` (die 18 Zeilen des Screenshots plus erzeugte bis 199).

Starten, im Ordner dieser Datei:

```bash
python -m http.server 8765
```

Dann `http://localhost:8765/` öffnen. Ohne Server (`file://`) wurde es nicht geprüft.

Dateien: `app.js` (Store und Komponenten), `style.css` (Farben als Variablen, Dunkelmodus über
`data-theme`), `data.js`, `index.html`. Befunde und Umsetzung in Odoo:
`../ui_verbesserungen.md`.

Tasten: `/` Suche, `U` Hochladen, Leertaste Vorschau, Pfeile blättern, `Esc` schließen.
Strg-Klick wählt Zeilen, Zeilen lassen sich auf Ordner ziehen, Dateien aus dem Explorer auf die Seite.
