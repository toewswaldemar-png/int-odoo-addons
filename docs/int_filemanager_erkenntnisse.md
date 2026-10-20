# int_filemanager: Erkenntnisse (Betrieb, Messungen, Odoo-Eigenheiten)

Gebaut: Mehrfach-Download und Ordner-Download als ZIP, Ordner-Upload, Verschieben über die Mehrfachbearbeitung und den Dialog „Move to...“, Zielprüfung in `write()`, Pfadname im Ordnerfeld. Diese Datei hält nur, was nicht aus dem Code ersichtlich ist: gemessene Werte, Odoo-Eigenheiten und Entscheidungen mit Grund. Messwerte gelten für das Betriebs-Image `odoo:19.0-hm` (sha256:4ea41539…), Core 19.0-20260817, Python 3.12.3, Werkzeug 3.0.1; bei einem anderen Stand prüfen, ob sie noch stimmen.

## 1. Betrieb am Tower (aus der Konfiguration gelesen)
- `workers=0` (Threaded, ein Prozess), `limit_time_real=1800`, `limit_time_cpu=1500`, `limit_memory_soft` 2 GiB (zählt `vms`, nicht RSS), `proxy_mode=True`, `x_sendfile` aus.
- Proxy: Nginx Proxy Manager, `proxy_read_timeout`/`proxy_send_timeout` 90 s, `client_max_body_size` 2000m, Puffer Standard, keine Location `/web/filestore`, Request-Zeile 8 KB (etwa 1.000 IDs in der URL; 1.300 gaben 414).
- Daten liegen unter `/mnt/user/...` = FUSE (`shfs`): `stat` kostet 0,28 ms je Datei, Anlegen vieler Dateien 7 ms. Für Messungen mit vielen Dateien direkt auf `/mnt/cache/appdata/...` schreiben, gelesen wird über den Betriebspfad.

## 2. Gemessene Befunde zur Übertragung
- Odoo prüft `limit_time_real` nur im 60-s-Takt, wartet danach bis zu 60 s auf andere Anfragen, dann Reload des ganzen Prozesses (etwa 1 s, alle Anfragen weg). Wirksam also 1800 s plus 0 bis 120 s. Gilt auch für lange Einzel-Downloads.
- Der Proxy nimmt etwa 1 GB der Antwort schnell auf; darüber bremst er Odoo auf das Tempo des Clients (Thread bleibt belegt). Rechenregel: Belegung ≈ (Größe − 1 GB) / Client-Tempo. Darum Obergrenze 10 GB (Systemparameter `int_filemanager.zip_max_size`) für alle ZIPs.
- Stille vor dem ersten Byte: der Proxy antwortet nach 90 s mit 504. Ein ZIP erst vollständig zu bauen und dann zu senden trägt nicht; deshalb Strom (V1) mit vorab berechneter `Content-Length`.
- Ohne `Content-Length` kürzt der Prefork-Betrieb (HTTP/1.0, 2-s-Socket-Timeout) den Strom **still**: der Client meldet Erfolg bei Teil-Datei. Threaded antwortet chunked, ein Abbruch ist dort erkennbar. Mit `Content-Length` ist jeder Abbruch ein Fehler im Browser.
- Die Länge eines `ZIP_STORED`-Archivs ist vorab auf das Byte berechenbar (auch ZIP64 über 2 GiB und mit mehr als 65.535 Einträgen; Länge gegen den echten Writer geprüft, Tests in `test_zip_stream.py`). `zipfile` schreibt auf einen nicht rückspulbaren Ausgang mit Datendeskriptoren. Leere Ordner: Eintrag mit `/` am Ende; `CRC`, `compress_size`, `file_size` auf 0 setzen, sonst fehlt `CRC`.
- Der Cursor ist beim Senden geschlossen: der Generator darf weder ORM noch `request` benutzen, nur fertige Einträge. Der Cache der Anfrage lebt so lange wie der Strom, darum vor dem Senden `request.env.invalidate_all()`.
- Mit `x_sendfile` und interner nginx-Location ist der Odoo-Thread nach 4 ms frei (nginx liefert mit Länge und Range, Direktaufruf der internen Location: 404). Betriebsänderung für spätere Ausbaustufen (Zwischendatei), für das jetzige Verfahren nicht nötig.
- Zwischendatei im Filestore: `_gc_blobs` räumt nur die Checkliste und fasst fremde Dateien nie an; `_gc_blob_uploads` löscht unter `.upload` nach 24 h, auch mitten in einer Übertragung. Eine Altersgrenze muss länger sein als die längste Übertragung.
- `http.Stream.from_path` nimmt nur Addon-Pfade; für Pfade im Filestore `http.Stream(type="path", …)` von Hand wie `ir.binary`.
- Quelldatei verschwindet mitten im Strom: der Client sieht einen Fehler. Client bricht ab: Thread nach 3 s frei, keine offenen Dateien.

## 3. Messung vieler Dateien (E2: 390.600 Dokumente, 28.830 Ordner, 312.480 sichtbar)
- `os.stat` je Datei: 87 s von 101 s Gesamtzeit, über dem 90-s-Limit des Proxys. Jetzt: Verzeichnislisten (`os.scandir`, eine je Prüfsummen-Präfix) plus Größe aus der Datenbank (Fallback `stat`, wenn die Größe 0 ist): 9,7 s gesamt. Fehlen einer Datei wird vor dem ersten Byte erkannt, eine Datei anderer Länge bricht den Strom ab.
- Ein nicht mitgelesenes Feld (`size`) kostete beim späteren Zugriff 313 Einzelabfragen und über 50 s: Felder, die die Schleife braucht, in `search_fetch` nennen.
- Speicher: Spitze 580 bis 700 MB bei 115 MB Grundlast, etwa 1 bis 1,5 KB je Datei während Bau und Senden. Eine Obergrenze für die Dateianzahl gibt es nicht; mehrere gleichzeitige Riesen-Downloads könnten `limit_memory_soft` erreichen.
- Senden sehr vieler kleiner Dateien: 0,45 ms je Datei auf FUSE (20.000 Dateien in 9 s); bei normalen Größen bestimmt die Leitung.
- Ordnerbaum (`parent_path =like`, Regeln als Nutzer): 0,22 s; Größensumme per Datenbank 0,25 s.
- Verschieben (E7): 1.000 Dokumente 2,5 s mit 1.000 Chatter-Nachrichten (eine je Dokument, so entschieden), 300 Ordner 1,2 s.

## 4. Odoo-Eigenheiten, die Fehler verursachen
- **`REPEATABLE READ`** (`odoo/sql_db.py:373`): Nach einer Eindeutigkeitsverletzung durch eine parallele Transaktion findet eine neue Suche in derselben Transaktion den fremden Datensatz **nicht** (mit zwei Verbindungen gemessen: `23505`, danach 0 Treffer). „Bei `IntegrityError` erneut suchen“ funktioniert nicht. Weg von Odoo: `ConcurrencyError` auslösen, `service.model.retrying` rollt zurück, nimmt einen neuen Schnappschuss und wiederholt (bis 5 Mal, auch für RPC und hochgeladene Dateien). `IntegrityError` allein wird nicht wiederholt.
- `child_of` auf `folder_id` wird zu `any!` und umgeht die Ordnerregel (Sudo-Comodel, schließt archivierte Nachfahren ein). Für Sichtbarkeit nach unten: `parent_path =like` als Nutzer suchen und die Kette vom gewählten Ordner abwärts im Speicher prüfen (ein versteckter Ordner nimmt alles darunter mit, auch offene Unterordner).
- Die Create-Regel des Ordners gilt nur bei `create`; `write` prüft das Schreibrecht nur am Datensatz, nicht das neue Ziel (`parent_id`/`folder_id`) und nicht die Firma. Darum steht die Zielprüfung im `write()` des Modells (Rechte nur für Nutzer, Invarianten auch unter `sudo()`).
- `Many2one.convert_to_read` gibt den Namen des direkten Ordners frei, auch wenn der Nutzer das Dokument nur über `access_via_record` lesen darf. Der Ordnername bleibt dort vertraulich; im ZIP und im Pfadnamen erscheint er nur, wenn die Kette sichtbar ist.
- GET-Routen kennen den Firmenkontext der Liste nicht: Cookie `cids` lesen, gegen den Nutzer prüfen (fremde Firma gibt `AccessError`, unter `sudo()` entfällt die Prüfung) und als `allowed_company_ids` setzen, bevor etwas gelesen wird. Jeder Download prüft neu, Firmen-IDs aus einer RPC-Aktion sind kein Nachweis.
- Der Konverter `models` in Routen prüft nichts; `_pre_dispatch` gibt für eingeloggte Nutzer bei existierendem, nicht lesbarem Datensatz 403, nur bei fehlendem 404.
- Transient-Modelle sind in Odoo 19 **nicht** auf ihren Ersteller beschränkt; ein Nutzer der Gruppe kann einen Dialog lesen, wenn er die Nummer kennt (er enthält nur Nummern und die Zusammenfassung). Eine ACL-Zeile ist nötig.
- Tracking-Nachrichten entstehen erst in `cr.precommit`; in `TransactionCase` vor dem Zählen `env.cr.precommit.run()` aufrufen.
- Ordnernamen werden außer im Server-Import nirgends bereinigt (NFC, Steuerzeichen, Länge); Dokument- und Ordnername dürfen im selben Ordner gleich sein (getrennte Indizes). Das ZIP normalisiert nur den **Exportnamen** (Windows-Zeichen, reservierte Namen, Länge, Groß-/Kleinschreibung bei Kollisionen); gespeicherte Namen bleiben.
- Core-ZIP-Funktionen (`mail`, `account`, `web`) bauen im Speicher (`BytesIO`), es gibt kein Streaming-ZIP; der JS-Helfer `download()` lädt als Blob; `act_url` mit `target=download` öffnet einen neuen Tab (Popup-Blocker nach asynchronem RPC möglich).
- Kein Baum-Auswähler und kein Drop-Ziel im Core-Suchpanel; Kanban-Ziehen schreibt `folder_id`, aber nur für vorhandene Spalten und ohne Ordnerbaum.
- Chrome liefert `readEntries` höchstens 100 Einträge je Aufruf: bis zur leeren Antwort lesen; die Einträge von `webkitGetAsEntry()` müssen synchron im Drop-Ereignis eingesammelt werden.

## 5. Entscheidungen mit Grund
- **ZIP als Strom mit `Content-Length`, nicht Zwischendatei:** 504 nach 90 s ohne Byte, Aufräumen und Lebensdauer einer Datei wären zusätzliche Fehlerquellen.
- **Verzeichnislisten statt `stat`:** FUSE (siehe 3).
- **Ordner-ZIP:** der gewählte Ordner ist die oberste Ebene; nur leere Ordner bekommen einen eigenen Eintrag; Ordner behalten ihren Namen, gleichnamige Dateien werden nummeriert; Ziel „wählbar“ wie beim Upload (nach Regeln sichtbar und schreibbar).
- **Firma:** Ein Unterordner hat immer die Firma seines Elternordners und ist nur am obersten Ordner änderbar; der Teilbaum zieht mit.
- **Ordner-Upload:** Ordner zuerst als Paket (`action_make_paths`, höchstens 500 Pfade, als Nutzer, vorhandene sichtbare Ordner werden ohne Beachtung der Schreibweise wiederverwendet), Dateien danach einzeln über die unveränderte Upload-Route. Gleichnamige Ordner werden zusammengeführt, gleichnamige Dateien nummeriert. Bei Abbruch bleibt das Hochgeladene und bleiben angelegte Ordner stehen; nach fünf Fehlern in Folge stoppt der Upload.
- **Verschieben:** Mehrfachbearbeitung bleibt, dazu der Dialog „Move to...“ (Muster `crm.lead.lost`, ein `write` je Art, alles oder nichts); Auswahlfeld mit Pfadanzeige (Kontext `hierarchical_naming`, an der ersten unlesbaren Stufe „…“) statt Baum; ein Chatter-Eintrag je Dokument.
- **Notiz am verknüpften Datensatz neutral:** „A document was linked.“ ohne Dateiname und Link. Die Follower eines Kontakts sehen die Datei womöglich nicht; Name und Link stehen nur im Verlauf der Datei (kein Vorbild im Core, bewusste Entscheidung).
- **Zugriff über verknüpfte Datensätze ist eine Einstellung, Standard aus:** `_toggle_access_via_record` schaltet die Regel `int_filemanager_document_rule_record` und die beiden ACL-Zeilen der internen Nutzer zusammen (Vorbild `project/models/project_collaborator.py:42-62`, `project/security/ir.model.access.xml:3-16`, `project_security.xml:43,220-223`). Die drei Datensätze stehen mit `active=False` in `noupdate`, sonst setzte ein Update den Schalter zurück; die Einstellung liest ihren Zustand aus der Regel (`get_values`), es gibt keinen zweiten Wert. Eine ACL-Zeile ohne die Regel zeigte jedem internen Nutzer alle Dokumente. `access_via_record` und `FOLDER_ONLY_KEY` bleiben: bei eingeschaltetem Weg braucht `_manageable` weiter die Frage „zeigt der Ordner es?“. Ohne ACL zählt `document_count` 0 statt zu scheitern (Muster `sale/models/res_partner.py:22-25`).
- **Regeln eines Links buchstabieren die des Dokuments aus:** Odoo wertet die Domain einer Regel als Superuser aus (`orm/models.py:5388-5393`); ein `('document_id', 'any', [])` wendet die Regeln des Dokuments dort nicht an, der Link war jedem mit Leserecht sichtbar (Suche, `document_count`). Nur das Prüfen einzelner Datensätze in Python setzt den Superuser zurück (`fields_relational.py:186-190`). Vorbild für Pfade des Elternobjekts: `project/security/project_security.xml:80-99`.
- **Drei Stufen im Privileg, die Regeln gehören dem Leser:** Leser ⊂ Nutzer ⊂ Administrator über `implied_ids`; die Benutzerform zeigt sie als eine Auswahl (`res_groups.py:349` ordnet nach den implizierten Gruppen). Sichtbarkeit und Ändern folgen derselben Bedingung, darum hängt eine Regel für alle Vorgänge an der Gruppe Leser und gilt über die Implikation auch für den Nutzer; nur Anlegen hat eine eigene Regel (Nutzer). Wer nur eine ACL-Zeile mit `perm_write` hat, ändert nur, was die Regel zeigt. Vorbild für die Stufen `project/security/ir.model.access.csv:2-3`, `project_security.xml:80-99`.
- **Kein `is_editable`:** `ir_ui_view.py:1375-1383` setzt `create`/`edit`/`delete` an Liste, Kanban und Formular auf `False`, wenn der Nutzer das Recht auf das Modell nicht hat. Der Leser bekommt reine Leseansichten ohne eigenes Feld; `is_editable` (`discuss_channel.py:229-232`) braucht, wer je Datensatz anders darf, wir nicht. Knöpfe „Share“ und „Move to...“ tragen `groups` des Nutzers, die Zugriffsfelder des Ordners die des Administrators (wie `ocr_images`).
- **Oberfläche des Lesers:** Das Menü „New“, „Upload a folder“ und die Ablagefläche prüfen `user.checkAccessRight("int.filemanager.folder", ...)` (`core/user.js:189`), die Dateien an einem Datensatz gehen nach dem Recht am Datensatz. Der Leser behält „Download folder“. Der Server prüft alles ohnehin (`folder.check_access("write")` im Upload, ACL).
- **Pfadname** nicht gespeichert (kein `complete_name`), sondern mit den Rechten des Nutzers berechnet; für Gäste und Tracking bleibt der schlichte Name.

## 6. Invarianten (gelten für jede künftige Änderung)
1. Lesen ist nicht Pfad sehen: die Menge der lesbaren Dokumente, die Menge der Ordner mit vollständig sichtbarer Vorfahrenkette und die Menge der für ein Ordner-ZIP zulässigen Dokumente sind getrennt.
2. Verschieben prüft den Zielzustand samt Teilbaum (Firma, Archiv, Namen, Zyklus) auch unter `sudo()`; die Rechteprüfung gilt nur für Nutzer.
3. Jeder Download autorisiert in der GET-Route neu.
4. Eine ZIP-Auslieferung hält keine Datei länger als ihre Übertragung.

## 7. Stolpersteine beim Arbeiten am Modul
- `tests/__init__.py` muss jede neue Testdatei importieren, sonst laufen null Tests; `tools/check/tests.sh --test-tags "/int_filemanager:Klasse"` wählt nur Klassen daraus.
- Ruff (`py -3.13 -m pre_commit run --files …`) verbietet `self = self.with_context(...)` in Methoden und `collections.namedtuple`.
- HttpCase mit eigenem Cookie: `self.opener.cookies.set("cids", …, domain="127.0.0.1", path="/")`.
- Übersetzungsschlüssel sind global: „Upload folder“ ist schon das Feld des Freigabe-Upload-Ordners; neue Texte erst gegen `de.po` prüfen. Abgleich mit `tools/check/i18n_export.sh`.
- Wegwerf-Umgebungen auf dem Tower: eigene Datenbank auf `fmtest_pg`, Container immer mit eigenem Namen und nur per Namen stoppen (nie per Image-Filter: das beendete einmal den Produktiv-Container).
- Dokumente mit echtem Blob im Test: `_create_from_stream` und `addCleanup(remove, …_blob_path)`.

## 8. Browser und Oberfläche (Gründe, die nicht mehr im Code stehen)

**Datei-Viewer und Touch**
- Der Bild-Zoom des Core-`FileViewer` kennt nur die Maus und zoomt um die Bildschirmmitte; ein PDF kann der Browser selbst zoomen. Unser `DocumentFileViewer` behält `state.scale` und `translate` des Core und steuert sie nur mit den Fingern.
- Das Gleiten nach dem Loslassen spielt der Browser ab (`Element.animate`, eigener Thread); Verschieben per Code in jedem Bild ruckelt. `transition-base` ist im Core-Template `!important`, nur `transition: none !important` im gebundenen Stil überstimmt es, und der gebundene `style` ersetzt das ganze Attribut bei jeder Änderung. Eine 0,2-s-Verschiebung bei jedem Touch-Ereignis lässt das Bild den Fingern nachhängen: sie ist nur beim Drehen erlaubt.
- Zoom-Konstanten stammen vom PDF-Viewer des Core (`pdfjs/web/viewer.js`): 0,1 bis 10, Schritt 1,1, ein Rad-Tick je 30 Pixel; Trackpad-Zoom kommt als Rad mit Strg und kleinen Pixelschritten.
- Die Nachbarn werden vorgeladen wie im Modul `survey` (`Image` mit der Quelle, das `<img>` nutzt es wieder; die Adresse trägt die Prüfsumme, die Route antwortet mit einem Jahr Cache); höchstens zwei vorab, nicht mehr gebrauchte werden abgebrochen.
- PDFs und Texte stecken in einem iframe, der seine Touch-Ereignisse nicht nach außen gibt; ein Frame gleicher Herkunft ist erreichbar (`contentDocument` ist sonst `null`), und jede Datei ist ein neues Dokument, also nach jedem `load` neu anbinden. Text wird per `transform: scale` vergrößert, nicht per Schrift (sonst brechen die Zeilen neu um); `touch-action: pan-x pan-y` stoppt das Seiten-Zoomen des Browsers.
- Treffer im PDF: Der PDF-Viewer nimmt die Seite aus dem Hash (`setHash`), die Wörter markiert der Viewer nach dem Laden (die Hash-Suche beginnt zur falschen Zeit und legt das Wort an den oberen Rand); `entireWord: true` entspricht der Ganzwort-Suche des Servers; der erste Treffer wird einmal mittig gerückt (`scrollMatchIntoView` scrollt nur beim ersten Zeichnen).
- Wischen: 60 Pixel (der Core nimmt 100 zum Schließen des Menüs, Bootstrap 40); ein Wisch, der mit Textauswahl endet oder auf etwas beginnt, das seitlich scrollt, gehört nicht dem Viewer; das Video-Bedienfeld (64 Pixel) bleibt dem Video. Nach einem Zoom scrollt je nach Browser der verbliebene Finger selbst oder nicht, das Ereignis verrät es nicht: `createPanFollower` erkennt es an der Scroll-Position. Doppeltipp: unter 250 ms und 10 Pixel je Tipp, der zweite innerhalb 300 ms und 40 Pixel; `touch-action: manipulation` schaltet den Seitenzoom des Browsers ab.

**Listen, Felder, Kanban**
- `humanNumber` klebt Zahl und Vorsatz zusammen („2M“), darum die Größe als `Float` mit eigenem Formatter (die Größe überschreitet bei 2 GiB int4); Pivot und Graph nehmen das Widget einer Messgröße aus der Registry `formatters`. Die Namensspalte bekommt mit `listViewWidth: [200]` Platz, sonst setzt die Liste 80 Pixel Mindestbreite je Spalte.
- Bilder liefert der Server nur in 64/128/256/512/1024; ein Gast darf Bilder nur mit `can_view`. Ein Gast bekommt die Prüfsumme nicht, `write_date` dient dem Browser-Cache.
- Die Kartengröße (klein, mittel, groß) steht in `res.users.settings`, wie der Core Wahlen des Nutzers hält; `DocumentThumbnailField` liest `env.documentTile`.
- Ein Klick auf Karte, Vorschaubild oder Treffer öffnet den Viewer (die Pfeiltasten laufen über die Dateien der Seite); „Properties“ öffnet das Formular mit Pager über die Seite und der Liste im Breadcrumb (die Modell-Methode öffnet eine eigene Aktion ohne Liste).
- Das Menü „New“: der Input liegt neben dem Menü, nicht darin (das Menü ist weg, bevor die Dateien gewählt sind); der Dropdown öffnet an seinem Toggler, im Kontextmenü rückt ein Anker ohne Größe an den Mauszeiger. Das Suchpanel lädt seinen Baum nicht von selbst neu: nach Änderungen `soft_reload`.
- Ordner-Upload: Die Route nimmt eine Datei je Anfrage, `action_make_paths` höchstens 500 Pfade (200 werden gesendet), fünf Fehler in Folge stoppen. `file_upload` wartet nicht auf das Ende und gibt die Antwort nicht zurück (daher das Lauschen auf `FILE_UPLOAD_LOADED`/`ERROR`).

**Seite eines Dokuments**
- Die Seite besteht aus einem eigenen Form-Controller (`js_class`) und seiner Vorlage; der Renderer ist der Standard. Die Vorlage erbt `web.FormView` (wie `mrp_subcontracting`), setzt die Knöpfe in den Slot `control-panel-navigation-additional` neben den Pager und ersetzt den Aufruf des Renderers durch das Layout mit Vorschau und `ResizablePanel`; `$0` setzt den Renderer ins Seitenfeld zurück (wie `account` es in seinem Listen-Renderer tut).
- Die Ansicht hat kein `<chatter/>`, sonst legt mail es neben die Seite. Das Seitenfeld baut den Chatter selbst mit Modell, Id und Record. Er liest `env.chatter`, das mail dem Form-Controller gibt (der Chatter muss also unter dem Controller stehen), und `has_activities` aus der Arch, die der Parser von mail für jedes Formular ergänzt. Mindestbreiten: Formular 320, Chatter 530 (`$o-mail-Chatter-minWidth`, darunter braucht die Knopfreihe einen Scrollbalken).
- CSS-Klassen heißen `o_<Modul>_…` (Richtlinie), SCSS-Zeilen höchstens 80 Zeichen.

**Gäste**
- Das Gateway antwortet mit Status und kurzem Text, nicht mit JSON-RPC (`guestRpc` macht daraus einen `RPCError`). Eine Antwort von Odoo selbst (zu großer Body, 413) kommt vor der Freigabe und ist kein JSON. `user` ist ein Modul, kein Dienst, und seine Aufrufe brauchen einen Login, darum für Gäste gepatcht. Der Freigabe-Schlüssel liegt nur im `sessionStorage` des Tabs, Quittungen im `localStorage` je Freigabe (Token im Schlüssel).

## 9. Nicht gebaut / offen
- Browser-Abnahme (Chrome/Edge) der Ordner-Upload-Oberfläche mit mehreren tausend Dateien, tiefem Baum, leeren Ordnern und „Anhalten“: Server und Lint sind geprüft, das Browser-Skript nur durch Lint.
- ZIP für Freigabe-Gäste (eigener Bereichsnachweis, Download-Zähler, Gateway-Whitelist), Ziehen auf den Ordnerbaum, Wiederaufnahme beim Upload (überspringen bei gleichem Namen und gleicher Größe; bis dahin Dubletten bei Wiederholung), parallele Uploads, Knopf „Move to...“ auf Kanban-Karten und im Dokumentformular, Entpackpfade über 260 Zeichen unter Windows, Obergrenze für die Dateianzahl eines ZIPs, Versionen.
