# int_filemanager: Erkenntnisse (Messungen, Odoo-Eigenheiten, Entscheidungen)

Diese Datei hält nur, was nicht aus dem Code ersichtlich ist: gemessene Werte, Odoo-Eigenheiten und Entscheidungen mit Grund. Messwerte hängen von Hardware, Image und Core-Stand ab; bei einem anderen Stand neu messen.

## 1. Übertragung großer Dateien und vieler Dateien

- Odoo prüft `limit_time_real` nur im 60-s-Takt und wartet danach bis zu 60 s auf andere Anfragen. Wirksam sind also Limit plus 0 bis 120 s, auch bei langen Einzel-Downloads.
- Ein Reverse-Proxy nimmt etwa 1 GB der Antwort schnell auf und bremst Odoo darüber auf das Tempo des Clients; der Thread bleibt belegt. Belegung ≈ (Größe − 1 GB) / Client-Tempo. Darum die Obergrenze 10 GB (`int_filemanager.zip_max_size`) für alle ZIPs.
- Schweigt Odoo vor dem ersten Byte, antwortet der Proxy nach seinem Timeout mit 504. Ein ZIP erst ganz zu bauen und dann zu senden trägt nicht; darum ein **Strom mit vorab berechneter `Content-Length`**. Ohne `Content-Length` kürzt der Prefork-Betrieb (HTTP/1.0) den Strom still, der Client meldet Erfolg bei einer Teil-Datei.
- Die Länge eines `ZIP_STORED`-Archivs ist vorab auf das Byte berechenbar (auch ZIP64); `zipfile` schreibt auf einen nicht rückspulbaren Ausgang mit Datendeskriptoren. Leere Ordner: Eintrag mit `/` am Ende, `CRC`, `compress_size`, `file_size` auf 0. Belege: `tests/test_zip_stream.py`.
- Beim Senden ist der Cursor geschlossen: der Generator darf weder ORM noch `request` benutzen, nur fertige Einträge; vor dem Senden `request.env.invalidate_all()`.
- `http.Stream.from_path` nimmt nur Addon-Pfade; für Pfade im Filestore `http.Stream(type="path", …)` von Hand, wie `ir.binary`.
- `_gc_blob_uploads` löscht unter `.upload` nach 24 h, auch mitten in einer Übertragung: eine Altersgrenze muss länger sein als die längste Übertragung.
- Auf einem FUSE-Dateisystem kostet `stat` je Datei merklich (0,28 ms). Bei 390.600 Dokumenten brauchte `os.stat` 87 s von 101 s; Verzeichnislisten (`os.scandir` je Prüfsummen-Präfix) plus Größe aus der Datenbank brachten 9,7 s. Felder, die eine Schleife braucht, in `search_fetch` nennen (ein nicht mitgelesenes Feld kostete 313 Einzelabfragen und über 50 s).
- Speicher beim ZIP: etwa 1 bis 1,5 KB je Datei. Eine Obergrenze für die Dateianzahl gibt es nicht.
- `x_sendfile` ist für das jetzige Verfahren nicht nötig.

## 2. Odoo-Eigenheiten, die Fehler verursachen

- **`REPEATABLE READ`** (`odoo/sql_db.py`): Nach einer Eindeutigkeitsverletzung durch eine parallele Transaktion findet eine neue Suche in derselben Transaktion den fremden Datensatz **nicht**. „Bei `IntegrityError` erneut suchen“ funktioniert nicht. Weg von Odoo: `ConcurrencyError` auslösen, `service.model.retrying` rollt zurück und wiederholt (bis 5 Mal). `IntegrityError` allein wird nicht wiederholt.
- `child_of` auf `folder_id` wird zu `any!` und umgeht die Ordnerregel (Sudo-Comodel, schließt archivierte Nachfahren ein). Für Sichtbarkeit nach unten: `parent_path =like` als Nutzer suchen und die Kette im Speicher prüfen (ein versteckter Ordner nimmt alles darunter mit).
- Die Create-Regel eines Ordners gilt nur bei `create`; `write` prüft das Schreibrecht nur am Datensatz, nicht das neue Ziel (`parent_id`/`folder_id`) und nicht die Firma. Darum steht die Zielprüfung im `write()` des Modells (Rechte nur für Nutzer, Invarianten auch unter `sudo()`).
- `Many2one.convert_to_read` gibt den Namen des direkten Ordners frei, auch wenn der Nutzer das Dokument nur über `access_via_record` lesen darf. Im ZIP und im Pfadnamen erscheint der Ordnername nur, wenn die Kette sichtbar ist.
- GET-Routen kennen den Firmenkontext der Liste nicht: Cookie `cids` lesen, gegen den Nutzer prüfen (unter `sudo()` entfällt die Prüfung) und als `allowed_company_ids` setzen, bevor etwas gelesen wird. Jeder Download prüft neu.
- Der Konverter `models` in Routen prüft nichts; `_pre_dispatch` gibt für eingeloggte Nutzer bei existierendem, nicht lesbarem Datensatz 403, nur bei fehlendem 404.
- Transient-Modelle sind in Odoo 19 **nicht** auf ihren Ersteller beschränkt; eine ACL-Zeile ist nötig.
- Tracking-Nachrichten entstehen erst in `cr.precommit`; in `TransactionCase` vor dem Zählen `env.cr.precommit.run()` aufrufen.
- Ordnernamen werden außer im Server-Import nirgends bereinigt; Dokument- und Ordnername dürfen im selben Ordner gleich sein (getrennte Indizes). Das ZIP normalisiert nur den **Exportnamen** (Windows-Zeichen, reservierte Namen, Länge, Kollisionen).
- Core-ZIP-Funktionen bauen im Speicher (`BytesIO`); es gibt kein Streaming-ZIP. `act_url` mit `target=download` öffnet einen neuen Tab (Popup-Blocker nach asynchronem RPC möglich).
- Das Core-Suchpanel hat keinen Baum-Auswähler und kein Drop-Ziel; Kanban-Ziehen schreibt `folder_id`, aber nur für vorhandene Spalten.
- Chrome liefert `readEntries` höchstens 100 Einträge je Aufruf: bis zur leeren Antwort lesen; die Einträge von `webkitGetAsEntry()` müssen synchron im Drop-Ereignis eingesammelt werden.

## 3. Entscheidungen mit Grund

- **Ordner-Upload:** Ordner zuerst als Paket (`action_make_paths`, höchstens 500 Pfade, als Nutzer; vorhandene sichtbare Ordner werden ohne Beachtung der Schreibweise wiederverwendet), Dateien danach einzeln über die unveränderte Upload-Route. Gleichnamige Ordner werden zusammengeführt, gleichnamige Dateien nummeriert. Bei Abbruch bleibt das Hochgeladene stehen; nach fünf Fehlern in Folge stoppt der Upload.
- **Firma:** Ein Unterordner hat immer die Firma seines Elternordners und ist nur am obersten Ordner änderbar; der Teilbaum zieht mit.
- **Verschieben:** Mehrfachbearbeitung plus Dialog „Move to...“ (Muster `crm.lead.lost`, alles oder nichts), Auswahlfeld mit Pfadanzeige statt Baum, ein Chatter-Eintrag je Dokument.
- **Notiz am verknüpften Datensatz neutral** (Modul `int_filemanager_record`): „A document was linked.“ ohne Dateiname und Link, denn die Follower eines Kontakts sehen die Datei womöglich nicht. Kein Core-Vorbild, bewusste Entscheidung.
- **Zugriff über verknüpfte Datensätze ist eine Einstellung, Standard aus** (Modul `int_filemanager_record`): `_toggle_access_via_record` schaltet die Regel `int_filemanager_record.int_filemanager_document_rule_record` und die beiden ACL-Zeilen der internen Nutzer zusammen (Vorbild `project/models/project_collaborator.py`). Die drei Datensätze stehen mit `active=False` in `noupdate`, sonst setzte ein Update den Schalter zurück; die Einstellung liest ihren Zustand aus der Regel. Eine ACL-Zeile ohne die Regel zeigte jedem internen Nutzer alle Dokumente. Ohne ACL zählt `document_count` 0 statt zu scheitern (Muster `sale/models/res_partner.py`).
- **Regeln eines Links buchstabieren die des Dokuments aus** (Modul `int_filemanager_record`): Odoo wertet die Domain einer Regel als Superuser aus; ein `('document_id', 'any', [])` wendet die Regeln des Dokuments dort nicht an, der Link war jedem mit Leserecht sichtbar. Nur das Prüfen einzelner Datensätze in Python setzt den Superuser zurück.
- **Zugriff auf einen Ordner nur über die Listen, nicht über Follower:** `project` gibt seinen Projekten Follower als Einladung, aber dort schreibt nur der Manager am Projekt. Hier darf jeder Nutzer an den Ordnern schreiben, die er sieht, und `message_subscribe` verlangt nur Schreibrecht: über Follower hätte jeder Nutzer anderen Zugriff geben können, und wer einem Ordner entfolgt, hätte ihn verloren. Darum entscheiden `access_mode`, `access_user_ids` und `access_group_ids` (nur Administratoren schreiben sie, wie `discuss.channel` seine Mitglieder und `slide.channel` seine Gruppen trennt); Follower bekommen nur die Mitteilungen. Wer einen obersten Ordner anlegt, steht danach in `access_user_ids` (`create` des Ordners, als Superuser geschrieben, nicht bei Superuser-Anlage). Die Anlegen-Regel bleibt, denn Odoo prüft `create` vor diesem Eintrag. Versucht und verworfen (2026-10-26): den Ersteller als `default` von `access_user_ids` eintragen, damit die Leseregel schon beim Anlegen passt. `fields_relational.write_real` liest das Feld beim Anlegen als Nutzer zurück (`old_relation`), und das für Administratoren gesperrte Feld verweigert das (`_check_field_access`); 24 Tests scheiterten. Der Upload-Ordner einer Freigabe trug die Liste schon immer selbst (`mail_create_nosubscribe`).
- **Drei Stufen im Privileg:** Leser ⊂ Nutzer ⊂ Administrator über `implied_ids`; die Benutzerform zeigt sie als eine Auswahl. Sichtbarkeit und Ändern folgen derselben Bedingung, darum hängt eine Regel für alle Vorgänge an der Gruppe Leser und gilt über die Implikation auch für den Nutzer; nur Anlegen hat eine eigene Regel. Vorbild `project`.
- **Kein `is_editable`:** `ir_ui_view.py` setzt `create`/`edit`/`delete` an Liste, Kanban und Formular auf `False`, wenn der Nutzer das Recht auf das Modell nicht hat. Der Leser bekommt reine Leseansichten ohne eigenes Feld. Knöpfe „Share“ und „Move to...“ tragen `groups` des Nutzers, die Zugriffsfelder des Ordners die des Administrators.
- **Oberfläche des Lesers:** „New“, „Upload a folder“ und die Ablagefläche prüfen `user.checkAccessRight("int.filemanager.folder", ...)`; der Leser behält „Download folder“. Der Server prüft alles ohnehin.
- **Pfadname:** `complete_name` ist gespeichert (nur zum Sortieren, nicht ausgegeben). Der angezeigte Pfad wird mit den Rechten des Nutzers berechnet; für Gäste und Tracking bleibt der schlichte Name.

## 4. Invarianten (gelten für jede künftige Änderung)

1. Lesen ist nicht Pfad sehen: die Menge der lesbaren Dokumente, die Menge der Ordner mit vollständig sichtbarer Vorfahrenkette und die Menge der für ein Ordner-ZIP zulässigen Dokumente sind getrennt.
2. Verschieben prüft den Zielzustand samt Teilbaum (Firma, Archiv, Namen, Zyklus) auch unter `sudo()`; die Rechteprüfung gilt nur für Nutzer.
3. Jeder Download autorisiert in der GET-Route neu.
4. Eine ZIP-Auslieferung hält keine Datei länger als ihre Übertragung.

## 5. Stolpersteine beim Arbeiten am Modul

- `tests/__init__.py` muss jede neue Testdatei importieren, sonst laufen null Tests.
- Ruff (`docs/pruefautomatik.md`) verbietet `self = self.with_context(...)` in Methoden und `collections.namedtuple`.
- HttpCase mit eigenem Cookie: `self.opener.cookies.set("cids", …, domain="127.0.0.1", path="/")`.
- Übersetzungsschlüssel sind global: „Upload folder“ ist schon das Feld des Freigabe-Upload-Ordners; neue Texte erst gegen `de.po` prüfen (`tools/check/i18n_export.sh`).
- Wegwerf-Umgebungen auf dem Testserver: eigene Datenbank, Container immer mit eigenem Namen und nur per Namen stoppen (nie per Image-Filter: das beendete einmal den Produktiv-Container).
- Dokumente mit echtem Blob im Test: `_create_from_stream` und `addCleanup(remove, …_blob_path)`.

## 6. Browser und Oberfläche (Gründe, die nicht im Code stehen)

**Datei-Viewer und Touch**
- Der Bild-Zoom des Core-`FileViewer` kennt nur die Maus und zoomt um die Bildschirmmitte. Der `DocumentFileViewer` behält `state.scale` und `translate` des Core und steuert sie nur mit den Fingern. Zoom-Konstanten stammen vom PDF-Viewer des Core (0,1 bis 10, Schritt 1,1).
- Das Gleiten nach dem Loslassen spielt der Browser ab (`Element.animate`); Verschieben per Code ruckelt. `transition-base` ist im Core-Template `!important`, nur `transition: none !important` im gebundenen Stil überstimmt es. Eine Verschiebung mit Übergang bei jedem Touch-Ereignis lässt das Bild den Fingern nachhängen: sie ist nur beim Drehen erlaubt.
- Nachbarn werden vorgeladen wie im Modul `survey` (höchstens zwei vorab, nicht mehr gebrauchte werden abgebrochen).
- PDFs und Texte stecken in einem iframe, der seine Touch-Ereignisse nicht nach außen gibt; ein Frame gleicher Herkunft ist erreichbar, und jede Datei ist ein neues Dokument, also nach jedem `load` neu anbinden. Text wird per `transform: scale` vergrößert, nicht per Schrift (sonst brechen die Zeilen neu um).
- Treffer im PDF: Der PDF-Viewer nimmt die Seite aus dem Hash; die Wörter markiert der Viewer nach dem Laden (die Hash-Suche beginnt zur falschen Zeit); `entireWord: true` entspricht der Ganzwort-Suche des Servers.
- Wischen: 60 Pixel. Ein Wisch, der mit Textauswahl endet oder auf etwas beginnt, das seitlich scrollt, gehört nicht dem Viewer. Nach einem Zoom scrollt je nach Browser der verbliebene Finger selbst oder nicht; `createPanFollower` erkennt es an der Scroll-Position. Doppeltipp: unter 250 ms und 10 Pixel je Tipp.

**Listen, Felder, Kanban**
- `humanNumber` klebt Zahl und Vorsatz zusammen („2M“), darum die Größe als `Float` mit eigenem Formatter (die Größe überschreitet bei 2 GiB int4). Die Namensspalte bekommt mit `listViewWidth: [200]` Platz.
- Bilder liefert der Server nur in 64/128/256/512/1024; ein Gast darf Bilder nur mit `can_view` und bekommt die Prüfsumme nicht (`write_date` dient dem Browser-Cache).
- Die Kartengröße steht in `res.users.settings`, wie der Core Wahlen des Nutzers hält.
- Das Menü „New“: der Input liegt neben dem Menü, nicht darin (das Menü ist weg, bevor die Dateien gewählt sind). Das Suchpanel lädt seinen Baum nicht von selbst neu: nach Änderungen `soft_reload`.
- `file_upload` wartet nicht auf das Ende und gibt die Antwort nicht zurück (daher das Lauschen auf `FILE_UPLOAD_LOADED`/`ERROR`).

**Seite eines Dokuments**
- Eigener Form-Controller (`js_class`) und eigene Vorlage; der Renderer ist der Standard. Die Vorlage erbt `web.FormView`, setzt die Knöpfe in den Slot `control-panel-navigation-additional` und ersetzt den Renderer-Aufruf durch das Layout mit Vorschau und `ResizablePanel`.
- Die Ansicht hat kein `<chatter/>`, sonst legt mail es neben die Seite. Das Seitenfeld baut den Chatter selbst; er liest `env.chatter` vom Form-Controller, also muss er unter dem Controller stehen. Mindestbreiten: Formular 320, Chatter 530.
- CSS-Klassen heißen `o_<Modul>_…` (Richtlinie), SCSS-Zeilen höchstens 80 Zeichen.

**Gäste**
- Das Gateway antwortet mit Status und kurzem Text, nicht mit JSON-RPC (`guestRpc` macht daraus einen `RPCError`). `user` ist ein Modul, kein Dienst, und braucht einen Login, darum für Gäste gepatcht. Der Freigabe-Schlüssel liegt nur im `sessionStorage` des Tabs, Quittungen im `localStorage` je Freigabe.

## 7. Nicht gebaut / offen

- Browser-Abnahme (Chrome/Edge) der Ordner-Upload-Oberfläche mit mehreren tausend Dateien, tiefem Baum, leeren Ordnern und „Anhalten“.
- ZIP für Freigabe-Gäste, Ziehen auf den Ordnerbaum, Wiederaufnahme beim Upload (bis dahin Dubletten bei Wiederholung), parallele Uploads, „Move to...“ auf Kanban-Karten und im Dokumentformular, Entpackpfade über 260 Zeichen unter Windows, Obergrenze für die Dateianzahl eines ZIPs, Versionen.
- Office im Browser: ONLYOFFICE bräuchte eigene WOPI-Routen (Token je Datei mit Ablaufzeit, Prüfung über die Ordner-Rechte); der Connector `onlyoffice_odoo` hängt an `ir.attachment`. Hürden: zweiter Hostname mit vertrauenswürdigem Zertifikat auf allen Geräten, HTTP/HTTPS-Mischinhalt.
- Die Office-Vorschau (LibreOffice nach PDF per Cron) wandelte in der Messung die üblichen Formate in 1 bis 4 s, die größte Datei (`.doc`, 474 MB) in etwa 50 s.
