# int_filemanager: Odoo-Bausteine – Ergebnisse der Recherchen vom 2026-09-21 bis 2026-09-24

Stand 2026-09-28. Fasst 18 Einzeldokumente zusammen; die Originale liegen unverändert in
[`archiv/recherchen-odoo-bausteine/`](archiv/recherchen-odoo-bausteine) und bleiben die Quelle für jede Zeilenangabe und
jeden Gedankengang. **Zweck:** vor jeder Aussage "gibt es in Odoo nicht" oder "müssen wir selbst bauen" hier zuerst
nachsehen (Regel in `CLAUDE.md`), statt die Suche zu wiederholen.

## 1. Methode und Grenzen

- Geprüft am lokal geklonten Odoo-19-Kern (`origin/19.0`, Commit `2e2acfd6`, Stand 2026-09-08), nicht aus dem Gedächtnis.
  Ohne Live-Test an der Instanz blieben die Analyse zur tieferen Verzahnung (Abschnitt 10, mit Web-Recherche zu
  Enterprise-Fragen) und die Untersuchung zum Rich-Text-Editor (Abschnitt 7, teils Web-Recherche). Beides ist dort als
  ungeprüft markiert.
- **Grundgesamtheit statt Stichproben:** alle 12 Modelle mit `_parent_store = True`, alle 57 Bausteine unter
  `addons/web/static/src/core/`, alle View-Typen der Registry (~140 Einträge), jede Datei mit Bildbezug (23 PIL-Importe
  plus 27 Dateien in `html_editor`). Gegenprobe mit `_parent_name` bestätigte die Technik (der Klassenstandard
  `'parent_id'` erklärt die scheinbar fehlenden Treffer).
- **Nicht vollständig gelesen:** 30 von 57 `core/`-Bausteinen (Abschnitt 9), Gantt und Map (nur Enterprise, nicht im Klon).
- **Korrekturen im Lauf der Reihe:** `useNestedSortable` galt zuerst als "nur flache Listen", weil die Datei nicht gelesen
  war (falsch, Abschnitt 3.2). Ein Papierkorb-Bauplan war gegenstandslos, weil es den Papierkorb schon gab (Abschnitt 8).
  Die Annahme "MDXEditor ist framework-unabhängig" stimmte nicht (Abschnitt 7).
- **Code-Abgleiche beziehen sich auf den v1-Stand** (`native_ui/`, `int_filemanager.file`, Stand 2026-09-24). Die Aussagen
  über Odoo selbst gelten unverändert. Wo der v2-Code (`static/src/int_filemanager/v2/`, 2026-09-28) geprüft wurde, steht
  "Stand v2".

## 2. Kurzübersicht

| Frage | Ergebnis |
|---|---|
| Ordnerbaum als Seitenleiste | **Kein nativer Baustein**, in keinem der 12 hierarchischen Modelle. Eigenbau bleibt richtig (3.1). |
| Direkt zu einem Ordner springen | Nativ vorgesehen: gespeicherter Volltext-Pfad plus `name_search`, dazu Befehlspalette (3.2). Für v2 noch nicht gebaut. |
| Listenansicht | Nativ (`ListView`); nur Klicksemantik, Rubberband und Klick-daneben sind Eigenbau (4). |
| Bildgrößen, Thumbnails | Nativ: `fields.Image`, `image.mixin`, `/web/image/...` (5). |
| Bild zuschneiden, drehen, filtern | Nativ nutzbar über Cropper.js und die Canvas-/WebGL-Filter aus `html_editor`; Rückschreiben ist Eigenbau (5). |
| EXIF-Datum/GPS, Bildähnlichkeit, PDF-Seiten als Bild, GIF-Bearbeitung | **Eigenbau bestätigt** (5). |
| PDF zusammenfügen, drehen, Wasserzeichen, Seite extrahieren | Nativ: `odoo.tools.pdf` (6). |
| PDF markieren, kommentieren, zeichnen | Steckt bereits im mitgelieferten pdf.js 4.8.69; es fehlt nur das Rückschreiben (6). |
| Text mit dem Rich-Text-Editor bearbeiten | Für `txt/csv/log/json` falsch; `md` nur mit eigener Konvertierung; Chatter-Notiz deckt den Bedarf (7). |
| Papierkorb | Odoo kennt nur "Archivieren" über `active`; das ist der richtige Unterbau (8). |
| Drag-&-Drop-Zone beim Upload | Nativ: `useDropzone`. Der eigene Code ist fast wortgleich (9). |
| Favoriten für Ordner | Vermutlich schon nativ über `ir.filters` (3.4, **ungetestet**). |

## 3. Ordnernavigation und Suche

### 3.1 Es gibt keinen nativen Baum, der zu dieser Größenordnung passt

- **`<searchpanel type="category">`:** `search_panel_select_range()` (`addons/web/models/models.py`) läuft ohne Einschränkung
  auf `hierarchize=True`, damit über `formatted_read_group` als `GROUP BY parent_id` über die ganze Tabelle; mit
  `expand="1"` liest es alle Ordner. Bei 69.000 Ordnern und 1,38 Mio. Dateien ist das teuer. Der billige Kurzschluss
  greift nur bei Feldern ohne `_parent_name` (z. B. `status_id`).
- **12 Modelle mit `_parent_store`:** `hr.department`, `product.category`, `stock.location`, `stock.package`, `uom.uom`,
  `website.menu`, `product.public.category`, `ir.ui.menu`, `res.company`, `res.partner.category`, `analytic.plan`, dazu
  eine Testfixture. `res.partner` hat kein `_parent_store`. Die zwei großen (`stock.location`, `stock.package`) und
  `analytic.plan` nutzen **kein Baum-Widget**, sondern eine flache Liste, sortiert und durchsucht über das gespeicherte
  Feld `complete_name`. Kleine Hierarchien lädt Odoo komplett (`ir.ui.menu` eager mit `localStorage`, `website.menu`).
- **`web_hierarchy`** (`hierarchy_read()`): lädt Kinder gezielt für eine bekannte ID-Menge, skaliert also. Die zugehörige
  Ansicht zeichnet aber 250 px breite Organigramm-Karten, und das Modell arbeitet mit IDs statt Pfaden. Kein Ersatz für
  eine Seitenleiste.
- **`hr_org_chart`:** eigener kleiner Controller (Vorgesetzte, direkte Kinder), pro Klick ein neuer RPC. Odoo baut hier
  selbst lieber einen schmalen Controller, genau wie `/int_filemanager/tree`.
- **Gemeinsames Prinzip:** gezielt pro Knoten oder Gruppe nachladen, nie global aggregieren. Es kehrt in Pivot
  (`_expandGroup`), Calendar (`setDate`) und Kanban ("Mehr laden") wieder.
- **Stand v2:** Der Schritt-4-Plan nennt den Ordnerbaum als Eigenbau, mit Verweis auf diese Recherche.

### 3.2 Bausteine, die für Navigation und Schnellsuche taugen

| Baustein | Was er kann | Einschränkung |
|---|---|---|
| `complete_name` plus `name_search` | Gespeicherter, rekursiv berechneter Pfadname als `_rec_name`; `name_search` durchsucht ihn indexgestützt, ohne Baumdurchlauf. Muster in `product.category`, `stock.location`, `stock.package`, `analytic.plan`. | In v1 erfüllte `int_filemanager.file.path` das schon. Für v2 zu prüfen. |
| Befehlspalette (`command_provider`, Strg+K) | Eigener Provider "Gehe zu Ordner" mit Registry-Eintrag. | Die Palette filtert das Ergebnis zusätzlich clientseitig per `fuzzyLookup`. Der Provider **muss** `options.searchValue` selbst nutzen und serverseitig vorfiltern, sonst scheitert er wie das SearchPanel. |
| `Many2XAutocomplete` (`relational_utils.js`) | `searchThreshold` (Mindestzeichen), `lastEmptySearch` (keine erneute Anfrage bei Verfeinerung eines leeren Ergebnisses), `web_name_search` (Suche plus Feldabruf in einem Round-Trip), `KeepLast` (veraltete Antworten verwerfen). | Referenz, wie eine robuste Schnellsuche aussieht. |
| `RPCCache` (`rpc_cache.js`) | IndexedDB-Cache für jeden RPC, AES-GCM-verschlüsselt, Stale-while-revalidate über `update: "always"`, Invalidierung über Tabellennamen. | In v1 vom `FolderTree` nicht genutzt (jede Ebene ein ungecachter RPC). |
| `SelectCreateDialog` | Bettet eine komplette Liste oder Kanban-Ansicht in einen Auswahldialog ein. | Ohne neue Suchlogik für "Ziel wählen" beim Verschieben. |
| `useNestedSortable` | Drag & Drop mit echter Verschachtelung (`nest`, `maxLevels`, `isAllowed`). | Nur für Bäume, die komplett im Speicher liegen (Website-Menü). Grundlage, falls Ordner je im Baum verschoben werden sollen. |
| `useVisible`, `useOnBottomScrolled` (`mail/hooks.js`) | Endlos-Scroll statt Pager. | Für eine Galerie mit vielen Bildern denkbar. |
| Barcode-Scan im `Many2one` | Gescannter Code läuft als `name_search`; genau ein Treffer wird direkt gewählt. | Nur relevant, falls Papier mit QR-Code auf Dateien verweisen soll. |

### 3.3 Weitere geprüfte Stellen

- **Breadcrumbs:** Desktop vollständig nativ (`env.config.breadcrumbs`, im `onMounted` setzen, nicht in `setup()`). Mobil
  eigener Header, weil Odoos Vorlage bei mehreren Einträgen kleiner rendert. Odoos native Mobil-Kollabierung zeigt
  immer die letzten zwei Krumen; die eigene Breitenmessung ist genauer.
- **`SearchModel`:** Überschreiben von `_getDomain()` ist der schmalste Erweiterungspunkt. `router.addLockedKey()` hält
  den Pfad in der URL.
- **Graph:** hat keinerlei Navigation. **Router:** `hideKeyFromUrl()` hat keinen Anwendungsfall.

### 3.4 Favoriten über `ir.filters` (Hypothese)

Der Stern in der Suchleiste serialisiert `_getDomain()`, und genau das überschreibt das Suchmodell mit der
Ordnerbedingung. Ein gespeicherter Favorit würde also den Ordner enthalten, und `is_default` würde ihn beim Öffnen
laden. **Nicht getestet.** Offen ist, ob der Marker-Filter `filter_search_recursive` beim Wiederherstellen richtig erkannt
wird. Test: Ordner öffnen, Favorit speichern, neu laden, Favorit anwenden.

## 4. Listenansicht

`int_filemanager` nutzt echte Unterklassen von `ListView`, `ListController` und `ListRenderer`. Nativ und unverändert
geerbt: Sortierung, optionale Spalten, Spaltenbreite per Ziehen (nicht dauerhaft gespeichert), Tastaturnavigation,
Shift-Bereichsauswahl, Pager, Touch-Long-Press (400 ms).

- **Ungenutzt, aber passend:** `sum`/`avg`/`max`/`min` im Arch (Summe der markierten Dateien oder je Gruppe ohne
  eigenen Code), `decoration-*` (bedingte Formatierung), Menüpunkte Archivieren/Wiederherstellen für Modelle mit `active`,
  nativer Lösch-Bestätigungsdialog, Export.
- **Verdacht:** Zwei parallele Long-Press-Mechanismen (nativ 400 ms plus eigener Pointer-Code mit 500 ms). Ob der eigene
  noch gebraucht wird, lässt sich nur auf einem Touch-Gerät klären.
- **Echte Lücke:** kein natives Entf oder F2 in der Tastatursteuerung (`onCellKeydownReadOnlyMode`).
- **Zu Recht Eigenbau:** Explorer-Klicksemantik (Klick wählt, Doppelklick öffnet), Rubberband-Auswahl, Klick daneben
  hebt die Auswahl auf.

## 5. Bilder und Vorschau

**Server (`odoo/tools/image.py`, 602 Zeilen):** `image_process` mit `resize`, `crop_resize`, `image_fix_orientation`
(nur EXIF-Tag 0x112), Qualität und Format, `colorize`, `add_padding`; Grenze 50 Megapixel. **Nicht unterstützt:** SVG
(wird durchgereicht), GIF-Größenänderung.

- **`fields.Image`:** WEBP wird serverseitig **nicht** verkleinert. Es sucht nur nach einer vorhandenen Geschwister-Anlage
  mit `description = 'resize: <Größe>'`; sonst bleibt das Original stehen. Das Feld verlangt `_log_access`.
- **`image.mixin`:** eine Quelle plus `related`-Größen mit `store=True` (1920, 1024, 512, 256, 128), automatisch neu
  berechnet. Das Muster für `preview` und `thumbnail`.
- **`/web/image/<model>/<id>/<field>/<w>x<h>`** (`content_image`, `ir.binary`): Thumbnails in beliebiger Größe per URL,
  mit ETag inklusive Größe, Zuschnitt und Qualität, Platzhalter bei fehlendem Bild. Die eigene Thumbnail-Route mit festem
  `max-age` ist in jeder Hinsicht schlechter.
- **Bearbeiten (`html_editor`):**
  - `modify_image` legt immer eine **Kopie** an und speichert per `alt_data` vorverkleinerte Varianten als
    Geschwister-Anlagen. Die Route ist fest an `ir.attachment` mit `res_model`/`res_id` gebunden.
  - `activateCropper` (`utils/image_processing.js`) ist ein eigenständiges Modul und lädt Cropper.js nach Bedarf.
    Cropper.js beherrscht **freie Rotation und Spiegeln** (`rotate`, `scaleX`, `scaleY`); damit braucht "Drehen dauerhaft
    speichern" keinen eigenen Rotationscode, nur die Anbindung an die eigene Schreibroute.
  - Filter (`image_post_process_plugin.js`): Regler für Blur, Kontrast, Helligkeit, Sepia, Entsättigung, Farbüberlagerung
    plus mindestens 15 Presets, über `WebGLImageFilter` mit Canvas-2D-Ersatz; GIF ausgeschlossen.
  - Formmasken (`rounded`, `shadow` …) sind nur CSS-Klassen und für eine echte Datei nicht brauchbar.
  - `image_transformation.js` dreht nur per CSS (nicht dauerhaft).
- **Bauplan (Empfehlung der Recherche):** nicht das ganze Plugin-System einbinden, sondern Cropper.js und die
  Canvas-Funktionen einzeln nutzen und das Ergebnis über die eigene Schreibroute mit Versionierung zurückschreiben.
  Reihenfolge nach Nutzen: Rotation persistieren, Zuschneiden, Filter. Formmasken und Mehrgrößen-Erzeugung
  zurückstellen.
- **Eigenbau bestätigt (nach vollständiger Suche):** EXIF-Aufnahmedatum und GPS (der Kern wertet nur die Orientierung
  aus), perzeptive Bildähnlichkeit (Duplikatfinder), PDF-Seiten als Bild, Audio, GIF-Bearbeitung, SVG-Rastern.

**Vorschau (`FileViewer`, 261 Zeilen):** Vor und zurück mit Rundlauf, Zoom, Drehen und Verschieben, Drucken und
Herunterladen, PDF als pdf.js-Iframe. Drehen und Zoomen sind reiner Anzeigezustand und werden beim Schließen verworfen;
das ist Bauweise des Bausteins, kein Fehler. **Stand v2:** `useFileViewer` wird genutzt und bekommt die ganze Liste der
vorschaubaren Dateien des Ordners (`onPreview` in `controller_mutations.js`), die Pfeiltasten blättern also durch den
Ordner.

**`mail.popout`:** generischer Dienst, der eine beliebige OWL-Komponente in einem eigenen Browserfenster oder per
`documentPictureInPicture` als schwebendes Fenster zeigt (mehrere Instanzen über IDs). Ungenutzt. Ein Popout-Knopf im
`FileViewer` wäre eigene Verdrahtung; `mail` ist ohnehin eingebunden.

## 6. PDF

**`odoo/tools/pdf/`:** `merge_pdf`, `fill_form_fields_pdf`, `rotate_pdf`, `extract_page`, `to_pdf_stream` (Bild zu PDF),
`add_banner` (Wasserzeichen mit ReportLab), `OdooPdfFileReader.getAttachments()` (eingebettete Dateien, z. B. XML in
E-Rechnungen), `OdooPdfFileWriter` (Einbetten), `PdfSigner` (kryptographische Signatur mit X.509). Ein reales Muster
liefert `sale_pdf_quote_builder`. Kein fertiger Passwortschutz (nur direkt über `pypdf`).

- **Größter Hebel:** Die mitgelieferte pdf.js-Version 4.8.69 enthält den AnnotationEditor; die Knöpfe für Markieren, Text,
  Zeichnen und Stempel sind in `viewer.html` vorhanden. Der Speichern-Knopf löst aber nur einen Browser-Download aus
  (`saveDocument()` → `downloadManager.download`). Fehlend ist eine Schreibroute plus Abfangen von
  `PDFViewerApplication.save` im Iframe (das Iframe-Muster gibt es schon in der Escape-Behandlung).
- **Kleine Zusatzaktionen:** Zusammenfügen und Drehen als Mehrfachauswahl-Aktion, Wasserzeichen beim externen
  Teilen (`add_banner`), Einzelseiten-Freigabe (`extract_page`).
- **Größer, mit Produktentscheidung:** Formularfelder ausfüllen, E-Rechnungs-Anhänge extrahieren.
- **Nur nach Rückfrage:** PDF-Signatur (Zertifikat, rechtliche Tragweite; in Community nur in einem Test genutzt) und
  Passwortschutz. Das clientseitige `signature`-Widget (Abschnitt 9) plus `PdfSigner` wären zusammen ein vollständiger
  nativer Bauplan für "PDF unterschreiben".

## 7. Text bearbeiten

Odoos Rich-Text-Editor (OdooEditor in `html_editor`, für `fields.Html`) erzeugt und liest nur HTML. (Untersuchung mit Web-Recherche, ohne Live-Test.)

- **`txt`, `csv`, `log`, `json`:** ungeeignet. Formatierung hätte beim Speichern kein Ziel, automatische
  Zeichenersetzung kann JSON zerstören, und der `CodeEditor` (Syntax, Zeilennummern) ist für diese Formate die richtige
  Wahl.
- **`md`:** einziger denkbarer Kandidat, aber Odoo kennt kein natives Markdown. Nötig wären Konvertierung in beide
  Richtungen und ein Umgang mit Rundreise-Drift (die Schreibweise ändert sich beim bloßen Öffnen und Speichern) sowie mit
  Bildern (kein `ir.attachment`, sondern relativer Pfad neben der Datei, wie Cloudreve es löst).
- **Vergleichssysteme:** Cloudreve nutzt MDXEditor (React-Komponente, für OWL ungeeignet), OpenCloud nutzt TipTap mit Yjs
  (ProseMirror, framework-unabhängiger Kern) und macht nur `.md` zum Rich-Text-Fall. Für OWL wäre TipTap der naheliegendste
  Ausgangspunkt; Milkdown und Toast UI sind ebenfalls möglich (Toast UI mit ca. 450 KB am größten). Live-Zusammenarbeit
  wäre ein eigener, großer Schritt.
- **`.html`** wäre technisch der einzige Dateityp ohne Konvertierung, aber der Editor arbeitet mit Fragmenten und
  `html_sanitize()` entfernt Skripte.
- **Ohne Aufwand schon da:** Die Chatter-Notiz an jeder Datei nutzt denselben Editor. Sie deckt den Wunsch "formatierter Text
  an einer Datei" vermutlich ab.

## 8. Papierkorb und `active`

- Odoo kennt keinen Papierkorb, nur Archivieren über ein Feld `active` (automatisch erkannt in `model_classes.py`).
- Jede `search()` filtert automatisch auf `active = True`, auch unter `sudo()`. Ausnahmen: `active_test=False` im Kontext
  oder eine Domain, die `active` selbst nennt. Eine Papierkorb-Ansicht ist deshalb einfach eine Domain
  `[('active', '=', False)]`.
- `toggle_active()` ist seit 19.0 veraltet; `action_archive()` und `action_unarchive()` verwenden.
- Der Automatismus spart in jeder Suchstelle einen eigenen Filter. Das ist der eigentliche Vorteil gegenüber einem
  `trashed`-Boolean, weil eine vergessene Stelle sonst gelöschte Einträge wieder auftauchen lässt.
- **Historie:** v1 hatte den Papierkorb schon (eigenes `trashed`-Feld mit `.trash/`-Unterbaum). Der geplante Umbau auf
  `active` war deshalb gegenstandslos, und der tägliche Vollscan konnte Papierkorb-Einträge endgültig löschen (Fund B1,
  siehe Konzept "DB-Vorrang" 16.1). Der Watcher-Guard-Abschnitt des alten Dokuments betrifft nur v1.
  **Stand v2:** `int_filemanager.node` verwendet `active`.

## 9. Die `core/`-Bausteine (57)

Vollständige Liste: `action_swiper`, `autocomplete`, `avatar`, `badge`, `barcode`, `bottom_sheet`, `browser`,
`checkbox`, `code_editor`, `color_picker`, `colorlist`, `colors`, `commands`, `confirmation_dialog`, `copy_button`,
`datetime`, `debug`, `dialog`, `domain_selector`, `domain_selector_dialog`, `dropdown`, `dropzone`, `effects`,
`emoji_picker`, `errors`, `expression_editor`, `expression_editor_dialog`, `file_input`, `file_upload`, `file_viewer`,
`hotkeys`, `install_scoped_app`, `ir_ui_view_code_editor`, `l10n`, `model_field_selector`, `model_selector`, `navigation`,
`network`, `notebook`, `notifications`, `overlay`, `pager`, `popover`, `position`, `pwa`, `py_js`, `record_selectors`,
`resizable_panel`, `select_menu`, `signature`, `tags_list`, `time_picker`, `tooltip`, `tree_editor`, `ui`, `user_switch`,
`utils`.

- **`dropzone`** (`useDropzone`): nahezu wortgleiche Doppelentwicklung. Auch der native Hook nutzt einen Tiefenzähler
  gegen das Flackern durch Kindelemente und kennt zusätzlich die Dialog-Aktivität. **Stand v2:** Das Upload-Overlay ist
  weiter eigener Code (`dropState`, `shared.xml`). Ob der eigene Handler etwas kann, was der native nicht kann (Drop auf
  eine bestimmte Zeile), ist ungeprüft.
- **`bottom_sheet`:** legt beim Öffnen einen Verlaufseintrag an und schließt bei `popstate`, sodass die
  Android-Zurück-Taste das Sheet schließt statt die Seite zu verlassen. Das v1-Mobil-Baumoverlay hatte keine
  `popstate`-Behandlung, vermutlich mit falschem Zurückverhalten (nicht auf einem Gerät geprüft).
- **Nutzbare Kandidaten, gelesen:** `action_swiper` (Wischgeste, z. B. löschen), `copy_button` (Link kopieren im
  Freigabe-Dialog), `colorlist` (Odoos 12 Farben für Tags), `signature` (Zeichenwidget für Unterschriften),
  `record_selector` (nutzt den `name`-Dienst mit eigenem Cache).
- **Als korrekt nicht genutzt bestätigt:** `file_input` (fest an `ir.attachment` gebunden; roh liegende Dateien brauchen
  den eigenen Upload) und `model_selector` (wählt Python-Modelle, nichts für Endnutzer). Bereits richtig genutzt:
  `confirmation_dialog`, `useNavigation`, `file_viewer`.
- **Ungelesen (30):** u. a. `autocomplete` (Basis), `avatar`, `badge`, `barcode`, `code_editor`, `color_picker`,
  `datetime`, `dialog`, `domain_selector`, `errors`, `expression_editor`, `hotkeys`, `notifications`, `overlay`,
  `position`, `select_menu`, `time_picker`, `tooltip`, `tree_editor` (2.772 Zeilen). Empfehlung der Recherche: nur bei
  konkretem Anlass gezielt aufschlagen.

## 10. Tiefere Verzahnung mit Odoo (Analyse vom 2026-09-21, ohne Live-Prüfung)

Die Aussagen zu Community und Enterprise stammen aus Dokumentation und sind **vor einer Umsetzung an der Instanz zu prüfen**.

- **Live-Refresh:** In v1 abonnierte nur die alte Oberfläche das Bus-Signal (`int_filemanager.change`); die neue musste es
  vor dem Löschen der alten nachziehen. **Stand v2 (Code 2026-09-28):** Der Explorer abonniert nur `int_filemanager_zip`
  (ZIP fertig); die Liste lädt sonst nur nach eigenen Uploads neu. Änderungen anderer Nutzer erscheinen erst beim
  nächsten Laden.
- **Verknüpfung mit beliebigen Datensätzen:** `ir.attachment.res_model/res_id` erscheint automatisch im Anhänge-Widget jedes
  Modells. Ein Schatten-Attachment wäre ein Architekturwechsel (doppelte Buchführung, eigene Zugriffsregeln); der
  Zwischenschritt ist, das Linkable-Mixin auf weitere Modelle auszuweiten (`hr.employee`, `repair.order`).
- **Enterprise-abhängig (vermutlich, ungeprüft):** `base_automation`/Studio, Approvals, Documents, Sign. Community-Ersatz:
  `ir.actions.server`, `ir.cron`, eigene Regel-Tabelle. Documents kennt eine "Anfordern"-Funktion (Platzhalter plus
  Portal-Upload plus Erinnerung), die sich als Idee nachbauen ließe.
- **Sicher in Community:** `<pivot>`- und `<graph>`-Ansichten, `Knowledge` (Grundfunktion), `calendar.event` für Fristen
  (mit `res_model/res_id`), Discuss-Kanäle für Team-Meldungen.
- **Weitere Anschlüsse:** Befehlspalette (3.2), nativer Export und Druck (kommen mit echten Records automatisch),
  `int_generic`-Muster `patch(...)` mit Bindung auf `this.resModel` für gezielte UI-Anpassungen, Multi-Company nur bei
  echtem Bedarf (`root_path` ist global, kein `company_id`).

## 11. Offene Punkte zum Nachprüfen

1. Favoriten über `ir.filters` live testen (3.4).
2. Doppelter Long-Press auf einem Touch-Gerät prüfen (4).
3. Zurück-Taste bei geöffnetem Mobil-Overlay auf Android prüfen (9).
4. Enterprise-Verfügbarkeit von Automatisierung, Approvals, Documents und Sign an der Instanz klären (10).
5. WEBP-Verkleinerung für `preview` und `thumbnail` mitplanen, falls WEBP hochgeladen wird (5).
6. Eigenen Drop-Handler gegen `useDropzone` vergleichen (9).
