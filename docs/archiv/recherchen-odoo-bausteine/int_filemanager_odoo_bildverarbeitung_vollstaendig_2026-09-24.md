# int_filemanager: Vollständige Bestandsaufnahme der nativen Odoo-Bildverarbeitung (Server + Client)

Stand 2026-09-24. Auf ausdrücklichen Wunsch **vollständig, nicht stichprobenartig** geprüft — jede
Datei mit Bildbezug im lokal geklonten Odoo-19-Kern (`C:\Users\Admin\Documents\GitHub\odoo`, auf
`origin/19.0` aktualisiert, Commit `2e2acfd6`, 2026-09-08) wurde identifiziert und gelesen, nicht nur
die bereits aus `../../int_filemanager_konzept_db_vorrang_2026-09-24.md` (Abschnitt 17) bekannten Stellen.
Ziel: für jeden Baustein, den `int_filemanager` für Bildvorschau/-bearbeitung bräuchte, verbindlich
klären, ob er nativ existiert, bevor irgendetwas selbst gebaut wird (entspricht Umbau-Regel 7 /
Suchraster 16.4 des Konzeptdokuments). Reine Recherche, nichts umgesetzt.

**Vorgehen:** `grep` über den gesamten Kern (`addons/`, `odoo/`) nach jedem Python-Import von PIL/
Pillow (23 Fundstellen, davon 14 reine Tests) plus gezielte Dateisuche nach `*image*` im
`html_editor`-Modul (27 Treffer) — jede produktionsrelevante Datei wurde vollständig gelesen, nicht
nur angerissen.

---

## 1. Server-seitiges Kern-Werkzeug: `odoo/tools/image.py` (vollständig gelesen, 602 Zeilen)

Die zentrale, einzige Bildverarbeitungs-Bibliothek des Kerns. Vollständige Fähigkeitsliste der
Klasse `ImageProcess` und der Modulfunktionen:

| Fähigkeit | Methode/Funktion | Details |
|---|---|---|
| Verkleinern, Seitenverhältnis erhalten | `resize(max_width, max_height, expand=False)` | Kein Vergrößern außer `expand=True`; **nicht unterstützt für GIF** ("wir behandeln nicht alle Frames korrekt") |
| Zuschneiden auf Ziel-Seitenverhältnis + verkleinern | `crop_resize(max_width, max_height, center_x=0.5, center_y=0.5)` | Zuschnitt so, dass möglichst viel erhalten bleibt; `center_x`/`center_y` steuern die Zuschnittposition (in `image_process()` als `crop='top'`/`'bottom'` verdrahtet); **ebenfalls nicht für GIF** |
| EXIF-Rotation korrigieren | `image_fix_orientation()` | Nur der EXIF-Tag `0x112` (Orientation) — alle 8 Standardwerte abgedeckt (Flip/Rotate-Kombinationen) |
| Format/Qualität setzen | `image_quality(quality, output_format)` | PNG (inkl. Web-Palette-Dithering), JPEG (Qualität 1–95), GIF, ICO; BMP wird automatisch zu PNG, alles andere zu JPEG |
| Transparenten Hintergrund einfärben | `colorize(color=None)` | Zufällige oder feste RGB-Farbe |
| Rand hinzufügen | `add_padding(padding)` | |
| Alles kombiniert | `image_process(source, size, quality, crop, colorize, output_format, padding, verify_resolution)` | Freie Modulfunktion, die intern eine `ImageProcess`-Instanz aufbaut — **das** zentrale Einstiegs-API |
| Dominante Farbe berechnen | `average_dominant_color(colors, ...)` | Aus `PIL.Image.getcolors()`-Ausgabe, gruppiert ähnliche Farben, gibt Mittelwert zurück |
| WEBP-Maße ohne volles Decodieren | `get_webp_size(source)` | Parst VP8/VP8X/VP8L-Container-Header direkt binär, kein PIL-Decode nötig |
| Größenvergleich zweier Bilder | `is_image_size_above(b64_1, b64_2)` | Immer `False` bei SVG |
| Data-URI bauen | `image_data_uri(base64_source)` | RFC 2397 |
| Farbraum-Hilfen | `get_saturation`, `get_lightness`, `hex_to_rgb`, `rgb_to_hex` | HSL-Berechnungen |

**Auflösungsgrenze:** `IMAGE_MAX_RESOLUTION = 50e6` (50 MP) — bei Überschreitung `UserError`, kein
Absturz. Bewusst gewählt, um u. a. 8K-Fotos abzudecken (Kommentar im Code).

**Explizit ausgeschlossen (kein Trick, keine versteckte Funktion gefunden):**
- **SVG:** `image_process` verarbeitet SVG überhaupt nicht (`source[:1] == b'<'` → `self.image = False`,
  wird unverändert durchgereicht). Auflösungsprüfung greift dort ebenfalls nicht.
- **GIF:** weder `resize` noch `crop_resize` wirken (Animationsframes würden zerstört).
- **EXIF jenseits der Orientierung:** einzige EXIF-Auswertung im gesamten Kern ist Tag `0x112`
  (Orientation). Verifiziert per Grep über `addons/` + `odoo/` nach `getexif`/`_getexif`/`ExifTags`/
  `DateTimeOriginal` — **keine einzige weitere Fundstelle**. Aufnahmedatum, GPS, Kameramodell: nicht
  vorhanden, bestätigt Eigenbau-Notwendigkeit aus dem Konzeptdokument (Abschnitt 17.3 `taken_at`).
- **Keine perzeptive Bild-Ähnlichkeitserkennung (Duplikat-Finder):** Grep über den ganzen Kern nach
  `imagehash`/`perceptual hash`/`phash`/`dhash`/`ahash` liefert nur Fehlalarme (WebAuthn-Krypto-Code,
  ungarische E-Rechnung) — für einen Duplikat-Finder auf Bildähnlichkeit (nicht nur exakter SHA256-
  Übereinstimmung) bleibt das vollständig Eigenbau.

---

## 2. Feld-Ebene: `fields.Image` (`odoo/orm/fields_binary.py:246-366`, vollständig gelesen)

Erbt von `Binary`. Wichtigste, bisher nicht dokumentierte Detailfunde:

**WEBP wird serverseitig NICHT über `image_process` verkleinert** (Zeilen 327-349) — stattdessen
sucht `_image_process()` bei WEBP-Quellen per Checksumme nach einer **bereits vorhandenen**,
passend benannten Geschwister-Anlage (`ir.attachment` mit `description = 'resize: <Zielgröße>'`) und
verwendet sie, falls gefunden; sonst bleibt das Originalbild unverkleinert im kleineren Feld
stehen. Das schließt sich erst mit Abschnitt 4 unten (client-seitige `alt_data`-Uploads) zu einem
vollständigen Bild — **wichtig für `int_filemanager`:** ein eigenes `fields.Image("preview", ...)`
würde hochgeladene WEBP-Dateien NICHT automatisch verkleinern, nur JPEG/PNG/GIF.

**`readonly`-Kurzschluss** (Zeilen 311-321): bei einem `readonly`-Feld ohne eigene Maße, oder einem
`related`-Feld mit identischen Maßen wie die Quelle, wird gar nicht erst verarbeitet — spart
unnötige Arbeit bei reinen Anzeigefeldern.

**Setup-Warnung:** jedes `fields.Image` verlangt `_log_access = True` auf dem Modell (Zeile 269-270,
`warnings.warn`) — `int_filemanager.file` hat das bereits (Standard-Odoo-Modell), kein Hindernis.

---

## 3. Muster für abgeleitete Größen: `image.mixin` (`odoo/addons/base/models/image_mixin.py`, vollständig, 20 Zeilen)

```python
image_1920 = fields.Image("Image", max_width=1920, max_height=1920)
image_1024 = fields.Image(..., related="image_1920", max_width=1024, ..., store=True)
image_512  = fields.Image(..., related="image_1920", max_width=512,  ..., store=True)
# ... 256, 128
```

Eine Quelle, mehrere `related`+`store=True`-Ableitungen — jede Größe wird automatisch beim
Schreiben der Quelle neu berechnet (`_inverse_related`/`_process_related` in `fields_binary.py`).
Kein eigener Cron/Cache-Invalidierungscode nötig. Genau das Muster, das
`../../int_filemanager_konzept_db_vorrang_2026-09-24.md` Abschnitt 17.3 bereits für `preview`/`thumbnail`
vorschlägt — hier am Original bestätigt, nicht nur nacherzählt.

---

## 4. Server-Endpunkt für Bearbeitung: `modify_image` (`addons/html_editor/controllers/main.py:406-499`, vollständig gelesen)

Route `/html_editor/modify_image/<model("ir.attachment"):attachment>`. Bisher unbekanntes, jetzt
verifiziertes Detail — **wie Filter/Zuschnitt tatsächlich serverseitig ankommen:**

1. Erstellt **immer eine Kopie** der Anlage (`attachment.sudo().copy(fields)`), nie ein Überschreiben
   — `fields['original_id'] = attachment.id` verknüpft zurück zum Original. Rechteprüfung: Lesen auf
   dem Ursprungsdatensatz, Schreiben auf dem Zieldatensatz (Zeilen 443-449).
2. **`alt_data`-Mechanismus** (Zeilen 457-478): der Client kann zusätzlich zum Hauptbild mehrere
   vorverkleinerte Varianten in verschiedenen Formaten mitschicken
   (`alt_data = {"<Zielgröße>": {"image/webp": ..., "image/jpeg": ...}}`). Diese werden als eigene,
   mit `description = 'resize: <Größe>'` bzw. `'format: jpeg'` getaggte Geschwister-Anlagen
   gespeichert (`attachment.create_unique(...)`). **Das ist exakt die Gegenseite zu dem in
   Abschnitt 2 gefundenen WEBP-Nachschlage-Mechanismus von `fields.Image`** — der Client erzeugt die
   Größen/Formate (vermutlich per Canvas/`toBlob()`), der Server speichert sie nur noch mit der
   richtigen Namenskonvention, `fields.Image` findet sie später automatisch wieder.
3. Unterstützte Formate (`SUPPORTED_IMAGE_MIMETYPES`, `addons/html_editor/models/ir_attachment.py:9-17`):
   GIF, JPE, JPEG, JPG, PNG, SVG, WEBP.

---

## 5. Streaming/Auslieferung: `ir.binary` + `/web/image/...`-Routen (vollständig gelesen)

**`odoo/addons/base/models/ir_binary.py:156-250` (`_get_image_stream_from`)** — bestätigt und
erweitert Abschnitt 17 des Konzeptdokuments:
- Nimmt `width`, `height`, `crop`, `quality` entgegen und ruft bei Bedarf **live** `image_process()`
  auf dem gespeicherten Original auf — keine vorab gespeicherte Größe ist zwingend nötig.
- **ETag inkludiert die Anfrageparameter** (`stream.etag += f'-{width}x{height}-crop={crop}-quality={quality}'`,
  Zeile 227) — korrektes HTTP-Caching pro Variante, nicht nur ein globaler `max-age`-Header wie die
  heutige `int_filemanager`-eigene `/int_filemanager/thumbnail`-Route.
- **Platzhalterbild automatisch** bei fehlendem/unzugänglichem Bild, Pfad überschreibbar per
  `_get_placeholder_filename`-Hook — direkt nutzbar für Schutzordner ohne eigenen Code.
- `stream.type == 'url'`: Verkleinerung wird für extern verlinkte Bilder übersprungen (nicht
  relevant für `int_filemanager`, da alle Dateien lokal liegen).

**`addons/web/controllers/binary.py:165-206` (`content_image`)** — die tatsächliche URL-Fläche,
vollständig gelesen: `/web/image/<model>/<id>/<field>/<width>x<height>` (plus Kurzformen über
`xmlid`) mit `crop`, `download`, `access_token` als Zusatzparameter. **Das ist ein vollständiger,
generischer On-Demand-Thumbnail-Dienst** — jede beliebige Zielgröße per URL, kein eigener
`/int_filemanager/thumbnail`-Endpunkt nötig, sobald das Bild in einem `fields.Image`-Feld liegt.

---

## 6. Client-seitige Bearbeitung: `html_editor`-Modul (27 bildbezogene Dateien, alle identifiziert)

### 6.1 Zuschneiden/Drehen/Spiegeln — echte, destruktive Bearbeitung

`addons/html_editor/static/src/utils/image_processing.js` (vollständig gelesen, 307 Zeilen) —
**eigenständig importierbares Modul**, nicht in den restlichen Editor verwoben:

- `activateCropper(image, aspectRatio, dataset, {onReady})` (Zeilen 153-187): lädt bei Bedarf das
  Bundle `html_editor.assets_image_cropper` nach (`loadBundle`, kein Grundlast-Overhead) und
  initialisiert **Cropper.js** direkt auf dem `<img>`-Element.
- `cropperDataFields = ["x", "y", "width", "height", "rotate", "scaleX", "scaleY"]` (Zeile 8) —
  **Cropper.js unterstützt bereits freie, nicht nur 90°-Rotation** sowie horizontales/vertikales
  Spiegeln über `scaleX`/`scaleY`. **Korrektur einer früheren Session-Annahme**
  ([[project_int_filemanager_bild_ausbau]] hatte nur "Rotation in der Vorschau, nicht persistiert"
  vermerkt, ohne die freie Rotationsfähigkeit von Cropper.js selbst zu prüfen).
- Bild-Caching über `URL.createObjectURL`/DataURL (Zeilen 91-132), damit Qualität/Filter interaktiv
  angepasst werden können, ohne das Originalbild mehrfach vom Server zu laden.
- Speichern läuft über den in Abschnitt 4 beschriebenen `modify_image`-Endpunkt.

**Wichtige Abgrenzung:** `image_transformation.js` (separates Modul, für die Website-Seitenerstellung)
setzt Rotation nur als **CSS-Transform** (`transform: rotate(Ndeg)`, Zeilen 291-292/350) direkt auf
das `<img>`-Element — nicht destruktiv, nicht in den Bilddaten gespeichert, nur eine Anzeige-Deko für
Snippets. **Für `int_filemanager` nicht brauchbar**, da eine wirklich gedrehte Datei gebraucht wird,
kein CSS-Wrapper — nur der Cropper.js-Weg (Abschnitt oben) kommt infrage.

### 6.2 Filter — vollständige Liste (`image_post_process_plugin.js`, vollständig gelesen)

Zwei Ebenen, je nach Browser-Fähigkeit (`isWebGLEnabled()`):

- **Manuelle Regler** (`defaultImageFilterOptions`, Zeilen 332-345): `blur`, `desaturateLuminance`,
  `contrast`, `brightness`, `sepia`, plus freie Farbüberlagerung (`filterColor`).
- **Vorgefertigte Instagram-artige Presets** (`glFilters`-Objekt, ab Zeile 368, mindestens 15 Stück
  identifiziert: `blur`, `1977`, `aden`, `brannan`, `earlybird`, `inkwell`, u. a.) — jedes eine feste
  Kombination aus Blend-Layer + Helligkeit/Kontrast/Sättigung/Sepia/Farbton-Verschiebung.
- Läuft über `WebGLImageFilter` (`addons/html_editor/static/lib/webgl-image-filter/webgl-image-filter.js`,
  MIT-artige Vendor-Bibliothek) mit Canvas2D-Fallback (`ctx.fillStyle`/`fillRect`-Blend), falls kein
  WebGL verfügbar ist.
- **GIF explizit ausgeschlossen** (`isGif`-Guard, Zeile 329 in Kombination mit `shouldTransformImage`)
  — konsistent mit der serverseitigen GIF-Ausnahme in `odoo/tools/image.py`.

---

## 7. Konsequenz für `int_filemanager` — was das gegenüber Abschnitt 17 des Konzeptdokuments ergänzt

Bestätigt den dortigen Bauplan vollständig und ergänzt drei bisher nicht explizit festgehaltene
Punkte:

1. **WEBP-Sonderfall ernst nehmen:** falls Nutzer WEBP-Bilder hochladen (zunehmend üblich, z. B. aus
   modernen Smartphone-Kameras/Screenshots), verkleinert `fields.Image` sie NICHT automatisch, außer
   der `alt_data`-Mechanismus aus Abschnitt 4 wird mitgebaut. Sonst bleiben `thumbnail`/`preview`
   bei WEBP-Quellen in Originalgröße — spürbare Performance-Falle bei großen Dateien.
2. **Cropper.js deckt Rotation bereits vollständig ab** (frei, nicht nur EXIF-90°-Schritte) — die in
   `int_filemanager_bildvorschau_bearbeitung_odoo_2026-09-23.md` noch offene Frage "Rotation
   persistieren" braucht keinen eigenen Code, nur die Anbindung von `activateCropper` +
   `modify_image`-Äquivalent an `int_filemanager`s eigene Schreibroute (Konzeptdokument Abschnitt
   17.3, Punkt 4 — hier jetzt mit dem exakten Rotationsmechanismus bestätigt).
3. **`/web/image/...` ersetzt die eigene Thumbnail-Route vollständig**, inklusive korrektem
   Query-Parameter-basiertem ETag-Caching — die heutige `/int_filemanager/thumbnail?path=...` mit
   festem `max-age=3600` ohne ETag ist in jeder Hinsicht schlechter als das native Bordmittel.

**Bleibt bestätigt Eigenbau** (nach vollständiger, nicht nur stichprobenartiger Suche): PDF-Seiten-
Rendering zu Bildern (Community hat dafür nichts), Audio-Tags, EXIF-Aufnahmedatum/GPS, perzeptive
Bildähnlichkeit für einen Duplikat-Finder, GIF-Bearbeitung jeder Art (weder Server noch Client
unterstützen es), SVG-Rastern/-Bearbeitung.
