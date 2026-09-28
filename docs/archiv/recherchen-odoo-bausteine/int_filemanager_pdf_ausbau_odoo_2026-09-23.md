# int_filemanager: PDF-Funktionsumfang vollständig ausbauen — geprüft am echten Odoo-19-Quellcode

Stand 2026-09-23. Untersuchung, welche PDF-Fähigkeiten (Bearbeiten, Teilen, alles Weitere) sich
nativ aus Odoo 19 ziehen lassen — direkt am lokal geklonten Quellcode geprüft
(`C:\Users\Admin\Documents\GitHub\odoo`), nicht angenommen. **Wichtigster Fund vorweg:** ein
großer Teil der "Bearbeiten"-Fähigkeit ist bereits heute im Code vorhanden und lauffähig — nur
ohne Rückschreib-Anbindung an `int_filemanager` selbst (Abschnitt 3). Reine Analyse, nichts
umgesetzt.

---

## 1. Odoos native PDF-Werkzeugkiste: `odoo/tools/pdf/`

Ein eigenständiges Python-Paket (nicht nur eine Datei), Community-verfügbar, von `int_filemanager`
bereits teilweise genutzt (`odoo.tools.pdf.PdfReader` für `page_count` in `mediameta.py`). Die
öffentliche API (`odoo/tools/pdf/__init__.py`):

| Funktion | Was sie tut |
|---|---|
| `merge_pdf(pdf_data)` | mehrere PDFs zu einem zusammenfügen |
| `fill_form_fields_pdf(writer, form_fields)` | AcroForm-Felder programmatisch befüllen (Schreib-Gegenstück zu dem, was `fulltext.py` heute schon lesend nutzt) |
| `rotate_pdf(pdf)` | alle Seiten um 90° drehen |
| `extract_page(attachment, num_page=0)` | eine einzelne Seite als eigenständiges PDF extrahieren |
| `to_pdf_stream(attachment)` | Bild → PDF konvertieren (nutzt Pillow, bereits eine bestehende Abhängigkeit dieses Moduls) |
| `add_banner(pdf_stream, text=None, logo=False, thickness=...)` | **diagonales Wasserzeichen/Banner** in die obere rechte Ecke, mit ReportLab (bereits Odoo-Kernabhängigkeit) |
| `OdooPdfFileReader.getAttachments()` | in der PDF eingebettete Dateien auslesen (z.B. XML-Daten in PDF/A-3-E-Rechnungen) |
| `OdooPdfFileWriter` | kann umgekehrt Dateien **in** eine PDF einbetten |
| `odoo/tools/pdf/signature.py::PdfSigner` | **echte kryptographische PDF-Signatur** (X.509-Zertifikat, Adobe-PDF-Signatur-Standard) — in Community aktuell nur in einem Test genutzt (`odoo/addons/base/tests/test_signature.py`), kein produktives Community-Modul ruft es auf, aber vollständig vorhanden und funktionsfähig |

**Reales Anwendungsbeispiel im Code:** `addons/sale_pdf_quote_builder/` — füllt vordefinierte
AcroForm-Felder eines Design-PDFs mit Verkaufsdaten und fügt mehrere PDF-Bausteine (Kopf/Fuß/
Produktblätter) zu einem fertigen Angebot zusammen, über genau `fill_form_fields_pdf`/`merge_pdf`.
Zeigt das reale, produktiv genutzte Nutzungsmuster dieser Funktionen.

**Bewusste Lücke:** kein fertiges Passwortschutz/Verschlüsselungs-Convenience-Wrapper in Odoos
eigener Schicht — die zugrundeliegende `pypdf`-Bibliothek kann das (`writer.encrypt(password)`),
müsste aber direkt aufgerufen werden, nicht über eine vorgefertigte Odoo-Funktion.

---

## 2. Freigabe/"Teilen" — bereits generisch vorhanden, PDF-spezifisch erweiterbar

`int_filemanager`s bestehender Freigabe-Mechanismus (`share_token`, Ablaufdatum, Audit-Log) gilt
bereits für jeden Dateityp inkl. PDF — nichts PDF-Spezifisches fehlt strukturell. Zwei native
Bausteine aus Abschnitt 1 passen aber direkt auf bereits im Feature-Katalog offen gelassene Punkte:

- **Wasserzeichen bei externem Teilen** (`../../int_filemanager_feature_ideen_2026-09-21.md`, Punkt J3,
  dort noch als "eher niedrigere Priorität, generisch über `pypdf`" eingeordnet) — mit
  `odoo.tools.pdf.add_banner()` bereits **fertig vorhanden**, kein Aufbau einer eigenen Lösung
  nötig: beim externen Download über `share_download()` (`controllers/main.py`) könnte für PDFs
  automatisch `add_banner(pdf_stream, text=f"Geteilt mit {partner.name} am {date}")` durchlaufen,
  bevor die Bytes ausgeliefert werden.
- **Einzelseiten-Freigabe** — mit `extract_page()` ließe sich "nur Seite 3 dieses PDFs teilen"
  als eigener Freigabe-Modus anbieten, ohne das gesamte Dokument preiszugeben.

---

## 3. Der zentrale Fund: PDF-Bearbeitung ist im Vorschau-Dialog bereits heute technisch vorhanden

**Direkt am Code verifiziert:** `int_filemanager` öffnet PDFs in der Vorschau über die
**vollständige** pdf.js-Viewer-Anwendung, nicht nur die Kernbibliothek:

```js
// filemanager_controller_mixin.js
defaultSource: isPdf
    ? `/web/static/lib/pdfjs/web/viewer.html?file=${encodeURIComponent(downloadUrl)}#pagemode=none`
    : ...
```

Die in Odoo 19 vendorte pdf.js-Version ist **4.8.69** (`addons/web/static/lib/pdfjs/build/pdf.js`)
— eine Version, die Mozillas vollständigen **AnnotationEditor** enthält. Am Markup von
`viewer.html` bestätigt: die Toolbar-Buttons für **Highlight, Text, Freihand-Zeichnen (Draw) und
Stempel/Bild einfügen** sind alle vorhanden (`#editorHighlightButton`, `#editorFreeTextButton`,
`#editorInkButton`, `#editorStampButton`), inklusive Farb-/Dicke-/Deckkraft-Einstellungen pro
Werkzeug. Sie sind im HTML initial `disabled`, werden aber — normales pdf.js-Verhalten — aktiviert,
sobald ein Dokument geladen ist.

**Konsequenz: wer heute in `int_filemanager` eine PDF-Vorschau öffnet, sieht bereits eine
vollwertige Werkzeugleiste zum Markieren/Kommentieren/Zeichnen/Stempeln** — nur `#pagemode=none`
wird von `int_filemanager` gesetzt (blendet nur die Miniaturansichten-Seitenleiste standardmäßig
aus, betrifft die Werkzeugleiste nicht).

**Was fehlt: die Rückschreib-Anbindung.** pdf.js' eigener Speichern-Button ruft laut Quellcode
(`viewer.js:13718-13750`) `pdfDocument.saveDocument()` auf (liefert die PDF-Bytes **inklusive**
gebackener Anmerkungen zurück) und übergibt das Ergebnis an `downloadManager.download(...)` — das
läuft heute auf einen normalen **Browser-Download**, nicht auf ein Zurückschreiben in
`int_filemanager` selbst. Die bearbeitete Version verlässt also den Dialog nur als separate
heruntergeladene Datei, die Originaldatei im Filemanager bleibt unverändert.

**Der Anschlusspunkt ist ebenfalls bereits im Code vorbereitet:** pdf.js exponiert sich selbst
global (`viewer.js:15163`: `window.PDFViewerApplication = PDFViewerApplication`) — und
`int_filemanager` reicht laut `../../int_filemanager_native_ui.md` bereits heute aktiv in das iframe
hinein (der dokumentierte ESC-Tastatur-Fix hängt einen eigenen Listener direkt auf
`iframe.contentWindow`). Genau dasselbe, bereits etablierte Cross-Frame-Muster ließe sich nutzen,
um `PDFViewerApplication.save` abzufangen bzw. `pdfDocument.saveDocument()` selbst aufzurufen und
das Ergebnis statt an `downloadManager.download()` an eine eigene Schreib-Route zu übergeben — nach
demselben Muster wie die bereits bestehende `/int_filemanager/write_text`-Route, aber binär statt
Text, und über `write_service.snapshot_and_write()` (also mit automatischer Versionierung, sobald
das versteht sich von selbst mit dem Papierkorb-Entwurf aus
`int_filemanager_papierkorb_odoo_umsetzung_2026-09-23.md` zusammenspielt).

---

## 4. Weitere direkt nutzbare Bausteine aus Abschnitt 1

- **Mehrere PDFs zusammenfügen** (`merge_pdf`) — als neue Mehrfachauswahl-Aktion im
  `ActionMenus` ("Ausgewählte PDFs zusammenfügen"), passt zum bereits etablierten Muster für
  andere Mehrfachauswahl-Aktionen.
- **Seiten drehen** (`rotate_pdf`) — einzelne falsch eingescannte Seiten korrigieren, ohne
  externes Werkzeug.
- **Formularfelder ausfüllen** (`fill_form_fields_pdf`) — Ergänzung zur bereits bestehenden
  Lese-Seite (`fulltext.py` liest AcroForm-Werte für die Volltextsuche/Werterkennung aus, siehe
  `../../int_filemanager_ocr_selbstdefinierte_felder.md`) — ein Schreib-Pfad würde erlauben, ein
  Formular-PDF direkt in `int_filemanager` auszufüllen, nicht nur auszulesen.
- **Eingebettete Anhänge extrahieren** (`OdooPdfFileReader.getAttachments()`) — direkt relevant
  für die in `erp/erp-odoo-modulvergleich.md` gefundene `LeitwegID`/`XRechnung`-Thematik: moderne
  PDF/A-3-E-Rechnungen betten die strukturierte XML-Rechnung direkt in die PDF-Datei ein — diese
  Funktion könnte sie automatisch herausziehen (z.B. für eine künftige Buchhaltungs-Integration).
- **PDF-Signatur** (`PdfSigner`) — technisch vollständig vorhanden, aber mit echter
  Infrastruktur-Voraussetzung (Firmenzertifikat/X.509), die vor jeder Nutzung geklärt werden
  müsste — kein Community-Modul nutzt es bisher produktiv, das ist also unerprobtes Terrain, nicht
  ein bereits bewährter Pfad wie Abschnitt 1-3.

---

## 5. Einordnung / Priorisierung

**Sofortiger, fast kostenloser Gewinn:** die Rückschreib-Anbindung aus Abschnitt 3 — die gesamte
Bearbeitungs-UI existiert bereits, es fehlt nur eine neue Route + der Cross-Frame-Hook, beides
nach bereits etablierten Mustern dieses Moduls. Das ist der mit Abstand größte Hebel dieser
gesamten Untersuchung.

**Kleine, klar abgegrenzte Zusatzaktionen:** Merge, Rotate, Wasserzeichen-bei-Freigabe,
Einzelseiten-Freigabe — jede für sich ein überschaubarer Baustein auf fertigen Odoo-Funktionen.

**Größerer Baustein mit echtem Mehrwert, aber neuer Infrastruktur:** Formularfelder ausfüllen
(Schreib-Pendant zur Werterkennung) und eingebettete E-Rechnungs-Anhänge extrahieren — beide
technisch bereits verfügbar, aber jeweils eigene Produktentscheidungen (welches Formular-Feld-
Konzept in der UI, was mit extrahierten E-Rechnungsdaten passieren soll).

**Nicht ohne Rückfrage angehen:** PDF-Signatur (Zertifikatsinfrastruktur, rechtliche Tragweite
einer digitalen Signatur) und Passwortschutz (kein fertiger Odoo-Baustein, müsste selbst mit
`pypdf` direkt gebaut werden) — beide eher eigenständige Folgeprojekte als Teil eines ersten
Ausbauschritts.
