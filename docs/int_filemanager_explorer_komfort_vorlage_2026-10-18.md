# Entscheidungsvorlage (Revision 2): Explorer-Komfort für int_filemanager

Stand 2026-10-18, überarbeitet nach Ihrer Prüfung (K1 bis K6 und die zwei Zusatzpunkte). Reine Recherche: nichts geändert, gestartet oder committet. Vertrauensgrad: **[B]** belegt (Quelltext gelesen), **[P]** plausibel (abgeleitet, nicht ausgeführt), **[U]** ungeprüft (nur durch Versuch klärbar). `M/` = `int_filemanager/`, `D/` = `docs/odoo/`.

## Ziel (ein Satz)
Markierte Dateien und Ordner als ZIP mitnehmen, Ordner samt Unterordnern hochladen und gezielt verschieben, mit Odoo-Bordmitteln und nur dem nachgewiesen fehlenden Eigenbau.

## 0. Was sich gegenüber Revision 1 ändert

| Punkt | Änderung |
|---|---|
| K1 | **V1 (Strom im Odoo-Thread) und V2 (Zwischendatei) sind gleichberechtigte Kandidaten**, bis Messungen vorliegen. V2 gilt nur dann als Lösung für lange Übertragungen, wenn der Proxy die Auslieferung wirklich übernimmt. `limit_time_real` pauschal erhöhen ist **keine** Lösung und steht nicht mehr als Option da. |
| K2 | Die Forderung „ZIP bleibt immer gültig, `_FEHLER.txt`“ ist **gestrichen**. Stattdessen eine Fehlertabelle (Abschnitt 2A) mit ehrlichen Garantien. |
| K3 | Ein **gemeinsames Rechtekonzept** (Begriff „sichtbare Ordnerhierarchie“) kommt als erster Schritt, vor ZIP und Verschieben. |
| K4 | Die **Zielprüfung gehört in `write()` des Modells**, nicht in Assistent oder Controller. |
| K5 | Ordner-Upload: **Transaktionsgrenzen, Pfadprüfung, Gleichzeitigkeit, ehrlicher Fortschritt** sind festgelegt (2C). |
| K6 | **Gespeicherte Namen bleiben unverändert**, nur der ZIP-Exportname wird normalisiert; Testliste erweitert. |
| Zusatz 1 | Messung **Ende zu Ende** (Odoo-Route, Datenbank, Manifest, ZIP-Verzeichnis), nicht nur der ZIP-Erzeugung. |
| Zusatz 2 | X-Sendfile ist **keine automatische Lösung** (Abschnitt 4, E9). |
| Reihenfolge | Rechtekonzept und Experimente vor allem anderen; Mehrfach-Download als erste Umsetzung, sobald der Übertragungsweg feststeht. |

## 1. Verifizierte Bestandsaufnahme

| # | Ausgangsbefund | Urteil | Beleg / Ergänzung |
|---|---|---|---|
| 1 | Mehrfach-Download angeboten, `action_download` nur für einen Datensatz | **bestätigt [B]** | `M/models/int_filemanager_document.py:315-343` (`_check_one_selected`, „Select exactly one document.“); Knopf im Listenkopf `M/views/int_filemanager_document_views.xml:20`, automatisch im Rechtsklickmenü (`document_list_context_menu_renderer.js:62-66`). Kein Test für `action_download` mit mehreren Zeilen. |
| 2 | Ordner als ZIP fehlt | **bestätigt [B]** | Kein ZIP im Modul. Ergänzung: die Liste zeigt nur Dokumente; das Core-Suchpanel hat keine Aktionen je Eintrag (`D/addons/web/static/src/search/search_panel/search_panel.xml:180-225`). Einstieg muss also an anderer Stelle liegen. |
| 3 | Core `_make_zip` im Speicher | **bestätigt [B]** | `D/addons/mail/controllers/attachment.py:22-47` (TODO des Core), `account/controllers/download_docs.py:21-26`, `web/controllers/vcard.py`. Kein Core-Streaming-ZIP. Einziges Vorbild für große Archive: DB-Backup mit Temp-Datei und `direct_passthrough` (`D/odoo/service/db.py:293-308`, `web/controllers/database.py:143`). Der JS-Helfer `download()` lädt als Blob in den Browser (`web/static/src/core/network/download.js:496-591`), `act_url` mit `target=download` streamt nativ (`action_service.js:1181-1200`). |
| 4 | Browser-Ordner-Upload abgewiesen | **bestätigt [B]** | `M/static/src/int_filemanager/views/list/document_list_controller.js:146-163`, Gast-Seite `guest_uploads.js:128`. Der Core hat nirgends `webkitGetAsEntry`/`webkitdirectory`/`webkitRelativePath`. Serverimport: `M/models/int_filemanager_import*.py` (nur Administratoren, Cron, Ordner unter `import_root`). |
| 5 | Verschieben über Mehrfachbearbeitung | **teilweise [B]** | `multi_edit="1"` an beiden Listen (`views.xml:12`, `folder_views.xml:9`; Core `list_arch_parser.js:200-202`, `dynamic_list.js:304-347`). Lücken: Ordnerfeld zeigt nur den Namen (kein Pfad, `int.filemanager.folder` hat weder `complete_name` noch `_compute_display_name`); Zielordner ungeprüft (K4); ein Namenskonflikt bricht den ganzen Stapel (Unique-Index `document.py:182-185`); Tracking = eine Chatter-Nachricht je Dokument. Ziehen: Kanban nach Ordner gruppiert (2D), nicht auf den Ordnerbaum. |
| 6 | Rechte für ZIP wiederverwendbar | **teilweise [B]** | Dokumentregeln `M/security/int_filemanager_document_security.xml` taugen. Aber `child_of` auf `folder_id` wird zu `any!` und umgeht die Ordnerregel (`D/odoo/orm/domains.py:1731-1790`), nur die Dokumentregel filtert; `access_via_record` macht Dokumente in Ordnern sichtbar, deren Pfad man nicht lesen darf; GET-Routen kennen den Firmenkontext der Liste nicht (der Core liest `cids` serverseitig nirgends, nur der Browser schickt `allowed_company_ids` im RPC-Kontext; Fallback `D/odoo/orm/environments.py:228-246` = alle Firmen des Nutzers). Einziger `child_of`-Test für Dokumente läuft als Superuser (`tests/test_document.py:300-308`). |

**Neue Befunde**
- **N1 Zeitlimit [B]:** Threaded-Betrieb (`workers=0`; so läuft laut Plan-Doku der Tower, nicht verifiziert): `limit_time_real` (Standard 120 s, Doku `D/../odoo19_reference/cli.md:582-590`) zählt ab Thread-Start inklusive Übertragung (`D/odoo/service/server.py:300`, `:509-530`; `start_time` wird für HTTP-Threads nie zurückgesetzt). Überschreitung löst einen **Neustart des ganzen Prozesses** aus, etwa 120 bis 240 s nach Start (`:735-760`, `:770`). Prefork: nur der eine Worker wird getötet (`:1018-1028`). Gilt schon heute für jeden langen Einzel-Download und Upload ohne `x_sendfile`. Ob HTTP/1.1 mit Keep-Alive die Zählung verlängert und ob die Antwort chunked oder per Verbindungsende abgeschlossen wird, ist **[U]** (Werkzeug lokal nicht vorhanden).
- **N2 Zielordner ungeprüft [B]:** `write()` prüft nur das Dokument (`D/odoo/orm/models.py:4384`); Create-Regel des Ordners gilt nur bei `create` (`M/security/int_filemanager_folder_security.xml:35-49`). Integritätsproblem, kein Vertraulichkeitsleck.
- **N3 Namen [B]:** `_clean_name` (`document.py:554-568`) entfernt nur Steuerzeichen/Pfadteile; Ordnernamen werden gar nicht bereinigt. Ein Dokument „x“ und ein Unterordner „x“ dürfen im selben Ordner nebeneinander liegen (getrennte Unique-Indizes) und würden im ZIP denselben Archivpfad bekommen.
- **N4 Kürzungsfalle [P/U]:** Bei Verbindungsabschluss ohne `Content-Length` und ohne Chunk-Ende sieht ein Client einen abgebrochenen Strom unter Umständen als vollständig. Ob das hier eintritt, hängt an N1/HTTP-Version und ist in E3 zu klären.

## 2. Anforderungen

### 2A Mehrfach-Download (Dokumente)
- 1 Datei: wie heute, direkter Download. Mehrere: ein ZIP mit den Originaldateien (nie `ocr_content`), **flach**, ZIP-Namen kollisionsfrei (Abschnitt „Namen“).
- Rechte: nur lesbare Dokumente. Ist eine angeforderte ID nicht lesbar: ganze Anfrage 404, ohne Angabe warum.
- Auslösung: bestehender Knopf „Download“ (damit auch Rechtsklick). RPC-Methode liefert `act_url` mit `target=download` auf eine GET-Route; die **Firmenkontext-IDs gibt die Methode explizit mit** (aus ihrem eigenen Kontext, validiert vom Core). IDs in der URL; zu lange Auswahl → Meldung, Ordner-ZIP benutzen (URL-Grenze E8).
- **Fehlertabelle (ehrliche Garantien):**

| Zustand | Verhalten |
|---|---|
| Blob fehlt vor dem Start (`os.stat` aller Blobs im Manifest vor dem ersten Byte) | Anfrage wird abgelehnt, Meldung nennt die betroffenen Dokumente; kein Teil-ZIP |
| Blob verschwindet/wird unlesbar nach Start (V1) | Antwort wird **abgebrochen** (Verbindung hart beenden bzw. Ausnahme im Generator), Fehler im Serverlog; Garantie nur: „Client erkennt Abbruch“, falls `Content-Length`/Chunk-Ende das hergibt (E3); sonst als Risiko dokumentiert |
| Blob verschwindet nach Start (V2) | kann nicht vorkommen: ZIP wird vollständig gebaut, bevor das erste Byte geht; Fehler beim Bau → normaler HTTP-Fehler |
| Client bricht ab | Dateien/Handles schließen, Thread frei, Log; kein „Erfolg“ |
| Rechte ändern sich zwischen Auswahl und Auslieferung | maßgeblich ist der Zeitpunkt des Manifest-Aufbaus (eine Transaktion); danach nicht erneut geprüft, Dokumentation |
| Dokument zwischen Aufbau und Übertragung gelöscht | Blob bleibt bis zur Löschung durch `_gc_blobs` (läuft täglich, nur über Checkliste, `document.py:461-505`); Fenster klein, aber E4 prüft es |

### 2B Ordner als ZIP
- Einstieg: Eintrag im Menü des Listenkopfs „Ordner herunterladen“ (wirkt auf den im Suchpanel gewählten Ordner, `getFoldersSection().activeValueId` ist schon im Code) und Knopf im Ordnerformular. Kein Suchpanel-Umbau, kein neuer Baum.
- Inhalt: Ordner samt Unterordnern **mit Struktur**; leere sichtbare Ordner als Verzeichniseinträge; archivierte Ordner/Dokumente nicht.
- Sichtbarkeit nach dem gemeinsamen Rechtekonzept (Abschnitt 6, Schritt 1): erst die Menge der sichtbaren Ordner **mit** Ordnerregeln bestimmen, nur Ketten ohne unlesbares Zwischenglied zulassen, dann Dokumente dieser Ordner. Namen versteckter Ordner erscheinen nie.
- Keine willkürliche Dateizahl-/Größenobergrenze. Wirkliche Grenzen liefern die Messungen (Übertragungszeit, Manifest-Speicher). Falls nötig als Systemparameter ohne Vorgabe.
- Ein gemeinsamer ZIP-Baustein für A und B, der **nur Dateien und Archivnamen** kennt (Eingabe: Liste aus Archivname, Blob-Pfad, Größe, Datum; Ausgabe: Bytes). Rechte, Ordnersuche, Datensätze bleiben außerhalb.

### 2C Ordner hochladen
- Wege: Drop eines Ordners und Knopf „Ordner hochladen“ (`<input webkitdirectory>`) im Menü „New“; Ziel = im Suchpanel gewählter Ordner. Leere Ordner nur beim Drop erfassbar.
- **Transaktion:** eine Anfrage = eine Datei + die dafür nötige Ordnerkette, in **einer** Odoo-Transaktion. Scheitert die Datei, wird die in dieser Anfrage angelegte Kette zurückgenommen; früher abgeschlossene Anfragen bleiben bestehen.
- **Pfadprüfung auf dem Server:** relativer Pfad als zusätzliches Formularfeld; abgelehnt werden: absolut, `.`/`..`-Teile, leere Teile, `\`, NUL/Steuerzeichen, Teile über der Namenslänge von `_clean_name`. Anlegen nur unter den Rechten des Nutzers (Create-Regel) und mit Schreibrecht an jedem wiederverwendeten Ordner.
- **Gleichzeitigkeit:** „suchen, sonst im Savepoint anlegen, bei `IntegrityError` erneut suchen“ (Muster `_read_in_folder`/`_create_numbered`), damit zwei Uploads dieselbe Zielhierarchie benutzen.
- **Fortschritt:** zwei Zahlen: übertragen und **gespeichert** (erst nach erfolgreicher JSON-Antwort); Abschlussbericht mit den fehlgeschlagenen Namen. Abbruch über `upload.xhr.abort()`; Bereits Gespeichertes bleibt.
- **Wiederholung:** Wiederaufnahme ist **nicht** Teil dieser Stufe. Vor dem Start Warnhinweis: bereits vorhandene gleichnamige Dateien werden nummeriert („(2)“); bei Tausenden Dateien entstehen sonst Dubletten. Wiederaufnahme (z. B. überspringen bei gleichem Namen und gleicher Größe) bleibt späteres Feature.
- Kein ZIP-Upload mit serverseitigem Entpacken.

### 2D Verschieben
- Grundlage: vorhandene Mehrfachbearbeitung (Dokument: Ordner, Ordner: Elternordner) und Core-Dialog „Update N records?“.
- Vorbedingungen (Schritt 1): Pfadname in der Auswahl (Muster `hierarchical_naming`, siehe Abschnitt 3), **Zielprüfung in `write()`** (K4, unten), verständliche Konfliktmeldung mit Namen.
- Assistent „Verschieben nach…“: **nicht** vorab; nur wenn die Bedienung im Test nicht reicht.
- Kanban nach Ordner gruppiert: Ziehen schreibt `folder_id` (Core `kanban_renderer.js:293-318`, `dynamic_group_list.js:105-155`; im Modul nicht blockiert); Grenzen: nur Ordner mit vorhandenen Dokumenten als Spalten, Gruppenlimit 80, nur Desktop, kein Neusortieren ohne Handle-Feld. Bleibt Nebenweg, kein Entwicklungsziel.
- Zielprüfung (K4), in Modell-`write()` bei `folder_id`/`parent_id` (nicht für Superuser-Aufrufe der Speicherschicht): Ausgangsobjekt schreibbar; Zielordner **sichtbar, schreibbar** (gleiche Prüfung wie der Upload, `controllers/int_filemanager.py:107-116`), aktiv, Firma im erlaubten Firmenkontext; bei Ordnern zusätzlich Zyklus (vorhanden), Namenskonflikt, Firmenkonsistenz (zu klären, siehe Abschnitt 9). `_parent_store` bleibt unverändert. Tracking beim Stapel: eine Nachricht pro Verschiebe-Vorgang statt je Dokument, falls E7 es nötig macht (`mail_notrack` wie in `_cascade_active`, `M/models/int_filemanager_folder.py:219-228`).

### Namen (K6)
- Gespeicherte Dokument- und Ordnernamen bleiben unverändert.
- Nur der **ZIP-Exportname** wird je Pfadteil normalisiert: Unicode NFC, Steuerzeichen/`/`/`\` raus, Windows-Zeichen (`: ? * " < > |`) ersetzt, Schlussleerzeichen/-punkte weg, reservierte Namen (CON, PRN, NUL …) entschärft, Länge begrenzt. Kollisionen **nach** der Bereinigung (ohne Beachtung der Groß-/Kleinschreibung, auch Datei gegen Verzeichnis im selben Elternordner) werden nummeriert, deterministisch (sortiert nach ID).
- Keine ORM-Abhängigkeit im Baustein; reine Funktionen, einzeln testbar.

## 3. Odoo-Bausteine (Gegenüberstellung)

| Teil | Odoo liefert | Erweiterungspunkte | Hat das Modul | Neu | Einschränkung |
|---|---|---|---|---|---|
| A | nichts fertig | `act_url`+`target=download`; Konverter `models` für ID-Listen (`D/odoo/addons/base/models/ir_http.py:81-94`, Vorbild `account/controllers/download_docs.py:70`); `content_disposition` (`D/odoo/http.py:353-369`); Python `zipfile` | Einzel-Download (`models/ir_binary.py`, `_to_http_stream`) | ZIP-Baustein, Route, Manifest, Namensnormalisierung | Cursor ist beim Senden zu (`http.py:2303-2342`, `sql_db.py:579-581`): Generator darf weder ORM noch `request` benutzen |
| B | wie A | `Response(iterator)`/`direct_passthrough` (`http.py:1542-1571`, Vorbild `database.py:143`) | Ordnerbaum, Regeln, Menü „New“ mit Zielordner | Manifest für Baum, Einstieg | N1 |
| C | `file_upload`-Dienst mit `buildFormData` (`file_upload_service.js:41-47`), `useCustomDropzone` | Zusatzfeld im Formular | Upload-Route, `_folder_to_write`, `_create_from_stream`, `_create_numbered`, Logik `_read_in_folder`, Ordner-Erkennung beim Drop | Traversierung, Pfadparameter, get-or-create, Summenfortschritt | Browserverhalten **[U]** |
| D | `multi_edit` auch für Many2one **[B]**; Kanban-Ziehen; Wizard-Muster `crm.lead.lost` (`crm/wizard/crm_lead_lost*.xml`, `binding_model_id`) | `hierarchical_naming`-Muster (`product/models/product_category.py:56-61`; Suchpanel schaltet es selbst ab, `D/addons/web/models/models.py:1712,1852`) | `multi_edit`, Zyklusschutz | Pfadname, Zielprüfung | Core: kein Baum-Auswähler, kein Drop-Ziel im Suchpanel; `ir.actions.server` `object_write` fragt keinen Wert ab (`ir_actions.py:612-618`) |

**Pfadname und Vertraulichkeit:** Ein Pfadname aus den Namen aller Vorfahren verrät Namen unlesbarer Elternordner. Daher kein gespeichertes `complete_name` nach dem Muster von `product.category`, sondern ein Anzeigename, der die Kette mit den Rechten des Nutzers bildet und am ersten unlesbaren Vorfahren mit „…“ abbricht; für Gäste kurz bleiben (`hierarchical_naming=False` im Gateway, denn `FOLDER` gibt `display_name` frei, `M/tools/share_gateway.py:43`; `_read_format` maskiert den Elternordner der Freigabewurzel, `M/models/int_filemanager_folder.py:175-190`). Kosten und Verhalten sind in Schritt 1 zu messen.

## 4. Architekturvarianten für die Übertragung (A, B)

| | V1 Strom im Odoo-Thread | V2 Zwischendatei, dann Auslieferung | V3 Core-`BytesIO` | V4 Asynchroner Auftrag |
|---|---|---|---|---|
| Idee | Generator, `ZIP_STORED`, Manifest vorab | ZIP vollständig in Datei unter `filestore/<db>/int_filemanager/…`, dann `Stream(type='path')` | ZIP im Speicher | Cron baut, Nutzer wird benachrichtigt |
| Eigenbau | klein | mittel (+ Aufräumen, Zugang, Platz) | minimal | groß |
| Erstes Byte | sofort | erst nach dem Bau | nach dem Bau | später |
| Fehler vor Auslieferung erkennbar | nur Vorab-`stat` | ja, alle | ja | ja |
| Größe/`Content-Length` | nur mit eigener Berechnung | ja, exakt | ja | ja |
| Odoo-Thread/Worker | **während der ganzen Übertragung belegt, N1** | beim Bau belegt (Plattengeschwindigkeit); Übertragung nur dann nicht, wenn der Proxy sie übernimmt | RAM = ZIP-Größe (`limit_memory_soft` 2 GiB) | nein |
| Plattenbedarf | keiner | = Datenmenge (`STORED`) | keiner | wie V2 |
| Kommentar | beste Latenz, schwächste Garantien | stärkste Garantien, Voraussetzung Proxy | verworfen (Speicher) | nur falls V1/V2 scheitern |

- X-Sendfile: Die Blobs des Moduls liegen **im Odoo-Filestore** (`ir.attachment._filestore()`, `document.py:350,437-442`), erfüllen also die Pfadbedingung in `D/odoo/http.py:669-683` und der Test `test_document_download.py:137` deckt das ab. Es bleibt aber eine **Betriebsvoraussetzung**: `--x-sendfile`, eine interne nginx-Location `/web/filestore` und der richtige Datenpfad (laut Plan-Doku ist `x_sendfile` auf dem Tower nicht gesetzt). Für temporäre ZIPs gilt zusätzlich: eindeutiger, nicht erratbarer Name, Zugang nur über die autorisierte Route (Location `internal`), Platzprüfung vor dem Bau, Aufräumen per `@api.autovacuum` mit Altersgrenze (Muster `_gc_blob_uploads`, `document.py:507-530`), Verhalten bei Abbruch des Baus. Ohne Proxy-Übernahme bringt V2 gegenüber V1 nur Vorab-Fehlererkennung und Größe, **nicht** die Befreiung von N1.
- `limit_time_real` zu erhöhen ist nur für die Messung erlaubt, nicht als Dauerlösung.

## 5. Offene Risiken und Experimente (nur Wegwerf-Instanz, nie produktive Daten)

Jedes Experiment: Aufbau, Messgrößen, Erfolgskriterium.

- **E1 Zeitlimit und Protokoll.** Aufbau: Container mit exakt dem Betriebs-Image (`odoo:19.0` + Repo-Dockerfile), Threaded und Prefork, `limit_time_real=20`, gedrosselter Download (`curl --limit-rate`), mit und ohne nginx/`x_sendfile`. Messen: HTTP-Version (1.0/1.1), Keep-Alive, Chunked oder Verbindungsende, Zeitpunkt des Reloads/Worker-Kills, Wirkung auf parallele Anfragen. Kriterium: Entscheidungstabelle „Übertragungsdauer × Betriebsart × Proxy → Folge“.
- **E2 Ende zu Ende.** Aufbau: Wegwerf-Datenbank mit synthetischem Bestand (bis 400.000 Dokumente in verschachtelten Ordnern, einige Dateien >4 GiB als Sparse-Dateien), echte Odoo-Route mit Manifest aus der Datenbank, V1 und V2. Messen: Zeit für Ordner-/Dokumentabfrage, Spitzen-RSS gegen Anzahl Einträge (Manifest **und** ZIP-Verzeichnis im Speicher), CPU-Zeit, Durchsatz, offene Dateien, Zeit bis zum ersten Byte. Kriterium: Speicher wächst höchstens linear und bleibt unter `limit_memory_soft`; sonst eigener, sparsamerer ZIP-Schreiber ohne `ZipInfo`-Liste prüfen.
- **E3 Abbruch und Kürzung.** Client bricht mitten im Strom ab; Quelle wird während des Strom unlesbar. Messen: Ressourcen frei, Logeinträge, ob der Client den abgebrochenen Download als fehlerhaft erkennt (HTTP-Version, `Content-Length` oder Chunk-Ende). Kriterium: kein „stiller Erfolg“; sonst `Content-Length` vorab berechnen (`ZIP_STORED` ist deterministisch) oder V2.
- **E4 Parallelität.** Dokument löschen/verschieben/archivieren und `_gc_blobs` laufen lassen, während ein ZIP entsteht. Kriterium: dokumentiertes, gutartiges Verhalten (Abbruch oder ZIP ohne Datei), nie ein stilles, unvollständiges „Erfolg“.
- **E5 Browser-Ordner-Upload.** 10.000 Dateien, tiefe Bäume, leere Ordner, >100 Einträge je Verzeichnis (Lesen in Paketen), Chrome/Edge/Firefox Desktop (Safari später). Kriterium: Baum vollständig, Zahlen „übertragen/gespeichert“ stimmen, Abbruch sauber.
- **E6 Rechte (Modultests).** ZIP-Menge = exakt die sichtbare Menge: restricted/inherit/open-unter-restricted, `access_via_record`, Mehrfirma mit explizitem Kontext, fremder Ordner, archiviert; als eingeschränkter Nutzer.
- **E7 Verschieben.** 1.000 Dokumente per Mehrfachbearbeitung: Dauer, Anzahl Chatter-Nachrichten; Kanban-Ziehen im Browser.
- **E8 URL-Länge.** Wie viele IDs verträgt der Proxy vor Odoo.
- **E9 Proxy-Auslieferung.** Wegwerf-nginx mit `/web/filestore`-Location; ZIP-Zwischendatei im Filestore wird per `X-Accel-Redirect` ausgeliefert; Zugang nur über die Route (direkter Aufruf der internen Location → 404), Aufräumen, Platzprüfung. Kriterium: Übertragung belegt keinen Odoo-Thread; keine Datei ohne Autorisierung erreichbar.
- **E10 Pfadname.** Kosten des rechtsabhängigen Anzeigenamens bei 29.000 Ordnern (Liste mit 80 Zeilen, Dropdown, Tracking-Nachrichten), Gast-Antworten unverändert kurz.

## 6. Empfohlene Lösung und Reihenfolge

Grundsatz: Odoo liefert Datensätze, Rechte, Liste, Aktionen; Eigenbau nur ZIP-Integration, Ordner-Upload und die fehlende Zielprüfung.

| Schritt | Inhalt | Akzeptanzkriterien | Tests |
|---|---|---|---|
| 0 | **Rechtekonzept** (kurzer Text im Chat, kein `.md`): Begriffe „lesbar“, „Pfad offenlegbar“, „Ziel wählbar“, „sichtbare Ordnerhierarchie“; Firmenkontext. **Dazu** E1, E3, E4, E8, E9 | Ihre Freigabe des Konzepts; Übertragungsweg V1 oder V2 durch Messung entschieden; Betriebsvorgabe geklärt | Skripte unter `tools/check/` (Muster `share_live.sh`) |
| 1 | Rechte-Fundament: Zielprüfung in `write()` (K4), Pfadname (E10), eine Funktion „sichtbare Ordnerhierarchie“, genutzt von Suchpanel-Prüfung, Verschieben und später ZIP | Verschieben in unsichtbaren/archivierten/fremden Zielordner → `AccessError`/`UserError`; Namenskonflikt nennt Namen; Auswahlfeld zeigt Pfad ohne unlesbare Vorfahren; Panel und Gäste unverändert | Eingeschränkter Nutzer, Konflikt, Zyklus, Firma, Gast-Namen, `child_of`/`any!` als Nicht-Superuser; Regression `test_folder_access`, `test_share_*`, `test_chatter` |
| 2 | **A Mehrfach-Download** (erste Umsetzung, sobald Schritt 0 den Übertragungsweg liefert; ZIP-Baustein mit Normalisierung) | Fehlermeldung weg; 1 Datei bleibt direkt; Rechte exakt; Fehlertabelle aus 2A erfüllt | Baustein ohne Odoo (Namenstabelle K6, ZIP64, Einträge >65.535); HttpCase Rechte/404/Mehrfirma; E2/E3 Teilmessung |
| 3 | **B Ordner-ZIP** | Struktur korrekt; versteckte Ketten fehlen; Datei/Verzeichnis-Kollision gelöst; leere Ordner | E6 vollständig, E2 vollständig |
| 4 | **C Ordner-Upload** mit Sicherheits-/Fehlerkonzept (2C) | Pfadangriffe abgelehnt; Race getestet; Fortschritt zweigeteilt; Dubletten-Warnung | Modultests get-or-create (Race, `..`, Länge, Rechte), Browser-Abnahme E5 durch Sie (es gibt keine Hoot-Tests) |
| 5 | D2 Assistent nur bei Bedarf; D1 wird nach Schritt 1 von Ihnen im Browser beurteilt | – | Konflikt-/Rechtetests |
| 6 | Doku (README), `de.po`, `docs/odoo19_abweichungen.md` nur auf Ansage | – | Export Deutsch ohne fehlende Texte |

Nicht im Umfang: ZIP für Freigabe-Gäste (eigener Bereichsnachweis, Download-Zähler, Gateway-Whitelist; Baustein bleibt wiederverwendbar), Ziehen auf den Ordnerbaum, Wiederaufnahme beim Upload, Versionen.

## 7. Entscheidungen (Stand 2026-10-18)
Entschieden von Ihnen:
- **Freigabe-Umfang jetzt: nur Schritt 0** (Rechtekonzept + Messungen in Wegwerf-Umgebung, kein produktiver Code).
- **Mehrfach-Download aus mehreren Ordnern:** flach mit Nummerierung.
- **Ordner-Upload, gleichnamiger Ordner vorhanden:** zusammenführen, gleichnamige Dateien nummerieren, nichts überschreiben.
- **Firma:** Unterordner hat immer dieselbe Firma wie der Elternordner (Regel beim Anlegen und Verschieben, Teil des Rechtekonzepts, wird in Schritt 1 gebaut).

Noch offen, von Ihnen zu beantworten (nicht per Code klärbar): **Betrieb.** Welcher Proxy steht vor Odoo (nginx?), ist die Location `/web/filestore` dort vorhanden, und ist Prefork (`workers>0`) auf dem Tower möglich? Ohne Antwort messe ich V1 und V2 ohne Proxy-Entlastung und weise das aus.

## 7a. Umfang der jetzigen Freigabe: Schritt 0 im Einzelnen

**Zweck:** Übertragungsweg (V1 oder V2) und Rechtekonzept entscheidungsreif machen. Es entsteht **kein Code im Repo** und es wird **nichts Produktives berührt**.

**Ergebnisse (alle im Chat, kein `.md`):**
1. **Rechtekonzept** (Text): Begriffe „lesbar“, „Pfad offenlegbar“, „Ziel wählbar“, „sichtbare Ordnerhierarchie“, Firmenkontext, Firmenregel für Unterordner; je Begriff die betroffenen Stellen (Suchpanel, Download, Verschieben, Upload, Freigabe-Gateway) und welche Tests Schritt 1 braucht. Quelle: bereits gelesener Code, ergänzt um die Auflösung der Fälle aus E6 auf dem Papier.
2. **Messbericht** zu E1 (Zeitlimit, HTTP-Version, Keep-Alive, Reload), E3 (Abbruch/Kürzung), E4 (Parallelität mit `_gc_blobs`), E8 (URL-Länge), E9 (Proxy-Auslieferung einer Zwischendatei), jeweils mit Aufbau, Messwerten, Erfolgskriterium und Urteil.
3. **Entscheidungsempfehlung** V1 oder V2 mit den Messwerten und der Betriebsvorgabe, die daraus folgt.

**Wo etwas angelegt wird (nach Ihrer Freigabe, nicht vorher):**
- Auf dem Tower (`ssh unraid`), ausschließlich **eigene Wegwerf-Container und -Datenbank** (Namen `zipprobe_*`, eigenes Docker-Netz, eigenes Datenverzeichnis unter `/mnt/user/appdata/zipprobe`), gleiches Image wie der Betrieb (`odoo:19.0` + Repo-Dockerfile). **Nie** `odoo`, `odoo_db`, `/mnt/hm-daten` oder irgendein Produktivverzeichnis; synthetische Dateien, keine echten Daten.
- Ein **Wegwerf-Modul** `zip_probe` (nicht im Repo, nur im Wegwerf-Container) mit drei Routen: V1 (Generator-Strom, `ZIP_STORED`), V2 (Zwischendatei im Filestore, dann `Stream`), Vergleichsroute (große Einzeldatei ohne ZIP). Es hängt von keinem Produktivmodul ab und wird mit dem Container verworfen.
- Ein Wegwerf-nginx im selben Netz für E1/E8/E9 (mit und ohne `/web/filestore`-Location, mit und ohne `x_sendfile`).
- Skripte liegen im Scratchpad-Ordner der Sitzung, nicht im Repo. Ob sie später als `tools/check/zip_live.sh` ins Repo wandern, entscheiden Sie nach den Ergebnissen.

**Aufräumen und Grenzen:** Alle `zipprobe_*`-Container, Netze und Verzeichnisse werden am Ende entfernt (Liste im Bericht). Plattenbedarf vorab prüfen (`df`), Sparse-Dateien statt echter Daten für die großen Dateien, Abbruch bei weniger als der dreifachen benötigten Reserve. Ich beginne nicht, bevor Sie diese Planfassung freigegeben haben.

**Abnahme von Schritt 0:** Sie lesen Rechtekonzept, Messbericht und Empfehlung; erst danach legen Sie fest, ob und womit Schritt 1 beginnt.

## 8. Kritische Selbstprüfung
- **Zweitmeinung (unabhängiger Prüfer, nur Quelltext):** bestätigte N1 (mit der Präzisierung „120-240 s“), N2, kein Core-Streaming-ZIP, kein Core-Baum-Auswähler, Kanban-Ziehen; widerlegte meinen Pfadnamen-Vorschlag (Muster `hierarchical_naming` statt Eingriff in das Suchpanel); ergänzte `any!`-Umgehung, Mehrfirma-GET-Falle, Ordnernamen-Bereinigung. Ihre Prüfung ergänzte K1 bis K6; die Pfadnamen-Vertraulichkeit (Abschnitt 3) und die Datei/Verzeichnis-Kollision (N3) kamen aus der Nachprüfung dieser Revision.
- **Übersehene Vereinfachung:** Für kleine Auswahlen würde das Core-Muster `BytesIO` genügen. Es scheidet aber aus, weil derselbe Baustein große Ordner tragen muss und Speicher dort die Grenze wäre.
- **Weiter offen:** Windows-Pfadlänge (260 Zeichen) beim Entpacken tiefer Bäume; Zeitstempel (Datum vor 1980 im ZIP unzulässig); Python-Version im Image (3.12 vermutet, [P]); Keep-Alive/HTTP-Version (E1); Safari-Verhalten.
- **Annahmen, die noch kippen können:** Live-Betrieb ist Threaded; Mehrfach-IDs in der URL reichen für typische Auswahlen; PDF/JPEG/Office lohnen keine Kompression; ein zusammengesetzter Anzeigename ist bei 29.000 Ordnern schnell genug.

Stopp: keine Umsetzung ohne Ihre ausdrückliche Freigabe.
