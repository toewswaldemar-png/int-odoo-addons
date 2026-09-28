# int_filemanager: Bildvorschau & Bildbearbeitung — geprüft am echten Odoo-19-Quellcode

Stand 2026-09-23. Direkt am lokal geklonten Odoo-19-Quellcode geprüft
(`C:\Users\Admin\Documents\GitHub\odoo`), nicht angenommen — Fortsetzung derselben Methodik wie
`int_filemanager_papierkorb_odoo_umsetzung_2026-09-23.md` und
`int_filemanager_pdf_ausbau_odoo_2026-09-23.md`. **Ergebnis vorweg:** Odoo hat eine echte,
überraschend umfangreiche Bildbearbeitung (Zuschneiden, Filter, Formmasken, Qualität/Format) —
aber wie bei PDF/Rich-Text bereits mehrfach in dieser Session festgestellt, ist sie fest an
`ir.attachment` + einen konkreten Datensatzkontext gekoppelt, nicht als eigenständiges
"beliebige Datei bearbeiten"-Werkzeug gebaut. Reine Analyse, nichts umgesetzt.

---

## 1. Bildvorschau — was `int_filemanager` heute schon (kostenlos) nutzt

`int_filemanager`s Vorschau läuft laut `../../int_filemanager_native_ui.md` bereits vollständig über
Odoos natives `FileViewer`/`useFileViewer` (`addons/web/static/src/core/file_viewer/file_viewer.js`).
Direkt am Quellcode bestätigt, was dieser Baustein **bereits mitbringt**, unabhängig von
`int_filemanager`s eigenem Code:

- **Zoom** (Mausrad **mit Cursor-Fixpunkt** sowie +/‑-Tasten, `zoomIn()`/`zoomOut()`,
  `scrollZoomStep`).
- **Pan/Verschieben** bei aktivem Zoom (Drag, `translate.dx`/`dy`).
- **Rotieren** in 90°-Schritten (`rotate() { this.state.angle += 90; }`).
- **Galerie-Navigation** vor/zurück per Pfeiltasten (`next()`/`previous()`), sofern der Aufrufer
  eine Liste mehrerer Dateien übergibt statt nur einer einzelnen.

**Wichtige Einschränkung, direkt am Code erkennbar:** `rotate()`/`zoomIn()`/`zoomOut()` verändern
ausschließlich `this.state.*` — reiner **Anzeige-Zustand** (CSS-Transform), **nichts davon wird
persistiert**. Schließt man die Vorschau und öffnet sie erneut, ist die Rotation wieder auf 0° —
das ist eine bewusste Lightbox-Komponente, kein Editor, auch nicht ansatzweise als einer gedacht.

**Für "Bildvorschau vollständig machen" bleiben damit zwei konkrete, kleine Lücken:**
1. **Rotation nicht persistiert** — ein Nutzer, der ein falsch herum liegendes Foto dreht, erwartet
   vermutlich, dass das beim nächsten Öffnen so bleibt. Naheliegende Lösung: beim Schließen der
   Vorschau, falls `state.angle != 0`, anbieten, die Rotation über `rotate_pdf`-artige Logik (für
   Bilder: Pillow `Image.rotate()`, serverseitig) tatsächlich in die Datei zu schreiben — über
   dieselbe `write_service`-Pipeline wie jede andere Änderung.
2. **Galerie-Navigation zwischen allen Bildern eines Ordners** — zu prüfen, ob `int_filemanager`
   dem `FileViewer` beim Öffnen tatsächlich die komplette gefilterte Bilderliste des aktuellen
   Ordners übergibt (dann funktioniert Vor/Zurück bereits heute) oder nur die einzelne angeklickte
   Datei (dann wäre das eine kleine, aber spürbare UX-Lücke gegenüber echtem Explorer-Verhalten).

---

## 2. Bildbearbeitung existiert — aber nur innerhalb von `html_editor`, nicht als generisches Werkzeug

**Wichtiger Namens-Hinweis:** das aus der Rich-Text-Recherche bekannte `web_editor`-Modul heißt in
Odoo 19 **`html_editor`** (Umbenennung/Neuschnitt seit der Editor-Überarbeitung) — unter
`addons/html_editor/static/src/main/media/` liegt eine vollständige Bildbearbeitungs-Suite:

| Datei | Funktion |
|---|---|
| `image_crop.js` + vendortes **Cropper.js** (`addons/html_editor/static/lib/cropperjs/`) | Freihand-/Seitenverhältnis-Zuschnitt |
| `image_transformation.js` | freies Rotieren/Skalieren per Zieh-Anfasser direkt auf dem Bild |
| `image_post_process_plugin.js` | Filter-Engine (Canvas 2D **und** WebGL) |
| `image_plugin.js` | Formmasken: `rounded`, `rounded-circle`, `shadow`, `img-thumbnail` |
| `image_save_plugin.js` | Speicherlogik (Abschnitt 3) |

**Filter-Umfang, direkt aus `image_transformation.js`/`image_post_process_plugin.js` bestätigt:**
Unschärfe (`blur`), Kontrast, Helligkeit, Sepia, Entsättigung/Graustufen
(`desaturateLuminance`), ein freier Farb-Overlay-Filter, sowie **vorgefertigte Instagram-artige
Filterpresets** (im Code u.a. `"1977"` als Presetname erkennbar) — über WebGL beschleunigt, wo
verfügbar (`isWebGLEnabled()`), mit Canvas-2D-Fallback. Plus **Qualität/Format-Umwandlung**
(`DEFAULT_IMAGE_QUALITY = "92"`, Export als `image/jpeg`/`image/png`/`image/webp`).

**Wichtige Unterscheidung für eine spätere Umsetzung — nicht alles "bäckt" sich in echte
Bild-Bytes ein:**
- **Zuschnitt, Rotation, Filter, Qualität/Format** laufen über `<canvas>` → `toDataURL()` →
  erzeugen **echte neue Pixel-Daten**. Das ist portabel, ließe sich 1:1 auch für eine eigenständige
  Bilddatei auf der Platte nutzen.
- **Formmasken** (`rounded`, `rounded-circle`, `shadow`, `img-thumbnail`) setzen dagegen nur
  **CSS-Klassen** auf das `<img>`-Element (`setImageShape()` in `image_plugin.js`) — das
  funktioniert nur, solange das Bild innerhalb von Odoos eigenem HTML gerendert wird. Für eine
  eigenständige Bilddatei (z.B. "exportiere mir eine kreisrund zugeschnittene PNG") müsste das
  separat als echte Canvas-Maskierung nachgebaut werden — die Odoo-Funktion selbst liefert das so
  nicht.

---

## 3. Wie gespeichert wird — derselbe architektonische Befund wie bei PDF und Rich-Text

`image_save_plugin.js` bestätigt exakt das bereits zweimal in dieser Session gefundene Muster
(vgl. Rich-Text-Editor- und PDF-Dokument): **Bearbeitung erzeugt immer eine neue
`ir.attachment`**, nie ein "gib mir die neuen Bytes zurück"-Ergebnis:

> "Modifying an image always creates a copy of the original... as the other modified image may be
> used elsewhere" (Kommentar in `saveModifiedImage()`)

Der Ablauf: bearbeitetes Bild → `/html_editor/modify_image/<attachment_id>` (Route, erwartet
`res_model`/`res_id`) → neues `ir.attachment` → neue `src`-URL wird ins `<img>`-Tag zurück
geschrieben. Fest verdrahtet auf einen Odoo-Datensatzkontext — für `int_filemanager` (Bilder sind
rohe Dateien auf der Platte, kein `ir.attachment`-Datensatz mit `res_model`/`res_id`) **nicht**
direkt so nutzbar, ohne eine Brücke zu bauen.

---

## 4. Bauplan für `int_filemanager` — dieselbe Lehre wie bei PDF/Rich-Text: Bausteine statt Gesamtpaket wiederverwenden

**Nicht** die komplette `html_editor`-Bildbearbeitung (samt Plugin-System, Editor-Zustand,
`ir.attachment`-Bindung) einbinden — das wäre, wie bei MDXEditor/OdooEditor bereits festgestellt,
unnötig schwergewichtig und architektonisch am falschen Ort gebunden. Stattdessen die
darunterliegenden, weitgehend eigenständigen Bausteine direkt wiederverwenden:

1. **Cropper.js** (`addons/html_editor/static/lib/cropperjs/cropper.js`) — bereits vendort,
   MIT-lizenziert, framework-unabhängig (reine DOM/Canvas-Bibliothek, kein React/Vue-Zwang wie bei
   den Markdown-Editoren) — direkt in einen eigenen OWL-Dialog einbindbar.
2. **Die Filter-/Qualitäts-Funktionen aus `image_post_process_plugin.js`/`image_processing.js`**
   sind bereits reine Canvas/WebGL-Funktionen ohne zwingende Kopplung an das Plugin-System — als
   eigenständiges Modul in `int_filemanager`s Frontend kopierbar/adaptierbar (JS, kein Server-Code
   nötig für die Bearbeitung selbst).
3. **Rückschreiben statt neuer `ir.attachment`:** das Ergebnis (`canvas.toDataURL(...)`) an eine
   neue Route senden, die die Bytes decodiert und über `write_service.snapshot_and_write()`
   zurück auf die Originaldatei schreibt — exakt dasselbe, bereits etablierte Muster wie für
   `write_text`/den vorgeschlagenen PDF-Rückschreib-Hook. Versionierung/Papierkorb (siehe
   `int_filemanager_papierkorb_odoo_umsetzung_2026-09-23.md`) greifen dadurch automatisch mit.
4. **Formmasken bewusst zurückstellen oder separat als echte Pixel-Maskierung nachbauen** (nicht
   einfach die CSS-Klassen-Funktion übernehmen, siehe Abschnitt 2 — würde ohne echtes
   Canvas-Clipping für eine eigenständige Datei nicht funktionieren).
5. **Serverseitige Rotation für die Vorschau-Persistenz** (Punkt 1 aus Abschnitt 1): einfacher
   separater Fall, reines Pillow `Image.rotate()` in Python, kein Cropper.js/Canvas nötig.

---

## 5. Einordnung / Priorisierung

**Kleine, sofort sinnvolle Lücke aus der bereits genutzten Vorschau:** Rotation persistieren
(Abschnitt 1, Punkt 1) — kleiner, klar abgegrenzter Baustein, Pillow ist bereits eine bestehende
Abhängigkeit (`mediameta.py`).

**Mittlerer Aufwand mit spürbarem Alltagsnutzen:** Zuschneiden (Cropper.js direkt einbinden) —
der am häufigsten gewünschte Bildbearbeitungsschritt, technisch klar umrissen, Bibliothek bereits
vendort.

**Größerer, aber machbarer Baustein:** Filter/Qualität-Umwandlung — mehr UI-Aufwand (Regler,
Vorschau live), aber die zugrundeliegenden Funktionen existieren bereits vollständig und müssten
nur adaptiert, nicht neu erfunden werden.

**Bewusst zurückstellen:** Formmasken (CSS-basiert, kein direkter Nutzen für eigenständige
Dateien) und die serverseitige Multi-Größen-Generierung aus `saveModifiedImage()` (dort nur für
Odoo-eigene Report-Zwecke gedacht, für `int_filemanager` ohne erkennbaren Mehrwert).
