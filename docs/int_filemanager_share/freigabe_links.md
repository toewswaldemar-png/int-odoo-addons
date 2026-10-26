# int_filemanager: Freigabe-Links (Erkenntnisse)

Die Freigabe-Links sind umgesetzt. **Der Code ist maßgeblich** (Modul `int_filemanager_share`: `models/int_filemanager_share.py`, `controllers/int_filemanager.py`, `tools/share_gateway.py`). Diese Datei hält nur fest, was der Code nicht zeigt: Entscheidungen, Sicherheitsgründe, Grenzen und offene Prüfungen.

**Ziel:** Ein Nutzer gibt eine Datei oder einen Ordner über einen Link frei. Wer den Link hat, braucht kein Konto und darf genau das, was am Link eingestellt ist (ansehen, herunterladen, hochladen), bis der Link abläuft, sein Limit erreicht oder gesperrt wird.

## 1. Entscheidungen

1. Eine Freigabe ist ein eigener Datensatz (`int.filemanager.share`) mit Ablauf; Sperren = Archivieren.
2. Die Rechte hängen am Link, nicht am Ersteller. Ein Link bleibt gültig, auch wenn der Ersteller den Zugriff verliert.
3. Der Token steht im Pfad, es gibt kein Cookie. Mehrere Links im selben Browser stören sich nicht.
4. Ansehen, Herunterladen und Hochladen sind frei kombinierbar (mindestens eines).
5. Gäste laden in einen eigenen Unterordner hoch, mit Grenzen je Link (Dateigröße, Gesamtgröße, Anzahl, Endungen).
6. Die Prüfsumme wird Gästen nie gezeigt.
7. Unterordner mit „nur erlaubte Nutzer“ bleiben dem Gast verborgen, samt Inhalt. Dasselbe gilt für Upload-Ordner **aller** Freigaben.
8. Gäste sehen Uploads **anderer** nicht, ihre **eigenen** schon und dürfen sie entfernen, solange die Datei noch im Upload-Ordner liegt und kein Nutzer sie übernommen hat.
9. Grenzen, Bremsen und Schwellen sind Einstellungen.
10. „Ansehen ohne Herunterladen“ gilt mit der Grenze aus „Bekannte Grenzen“.
11. Das Ziel eines Links ist nach dem Anlegen nicht änderbar (neuer Link statt Umbau).
12. Der Upload-Ordner entsteht beim Speichern des Links, nicht beim ersten Upload (sonst legen ihn zwei gleichzeitige Gäste doppelt an).
13. Der Upload-Zähler zählt, was hochgeladen wurde, nicht was noch da ist. Frei wird er nur, wenn der Gast seine eigene Datei entfernt.
14. Das Download-Limit zählt nur den Download-Knopf, jeder Klick zählt.
15. Links mit Passwort zeigen die Seite nach dem Entsperren über eine zweite Anfrage (kleines Skript); Links ohne Passwort bleiben rein serverseitig.
16. Keine Volltextsuche für Gäste: Sie wäre teuer (Zeitgrenze, eigene Bremse) und Trefferausschnitte könnten Text aus verborgenen Ordnern verraten. Gäste suchen nach Namen und Tags.
17. **Nicht enthalten:** Benachrichtigung bei Upload (billig nachrüstbar), Nutzungsbedingungen vor dem Download, „nur für angemeldete Nutzer“, Bearbeiten oder Kommentieren durch Gäste.

## 2. Aufbau in Kürze

Modell, Routen und Gast-Oberfläche: Code (`models/int_filemanager_share.py`, `controllers/int_filemanager.py`, `tools/share_gateway.py`).

- **Rechte:** Nutzer sehen nur die eigenen Freigaben (Regel `create_uid`), Administratoren alle. Anlegen darf man nur, was die **Ordner** dem Nutzer zeigen; eine Datei, die er nur über einen verknüpften Datensatz sieht, darf er nicht weitergeben. Die Einstellung `share_creators` kann das auf Administratoren beschränken.
- **Prüfwerkzeuge:** Tests `test_share_*.py`, dazu `tools/check/share_live.sh`, `share_attacks.py`, `share_parallel.py` (Angriffsfälle und parallele Verbindungen auf einer Wegwerf-Instanz).

## 3. Sicherheitsgründe, die der Code allein nicht zeigt

**Anfrage und Sitzung**
- **Gateway ist `type="http"`, nicht `jsonrpc`.** Der JSON-RPC-Dispatcher antwortet immer mit HTTP 200 und hängt jeder Ausnahme den **vollständigen Traceback** an, Gäste sähen also Pfade und Codestellen. `type="http"` gibt bei `UserError` nur Status und Text zurück, bei allem anderen ein schlichtes 500. Eigene Fehler sind `UserError`-Unterklassen mit `http_status`.
- **Alle Gast-Routen:** `save_session=False` (sonst bekommt jeder Gast ein `session_id`-Cookie), `csrf=False` bei POST (die Berechtigung ist der Token, kein Cookie), kleine `max_content_length`.
- **Öffentlicher Benutzer erzwingen.** `auth="public"` stellt ihn nur ein, wenn die Sitzung keine UID hat. Öffnet ein angemeldeter Nutzer den Link, liefen Uploads unter dessen Rechten. Deshalb als Erstes `request.update_env(user=base.public_user)`; `sudo()` ändert nur den Superuser-Modus.
- **Antwortköpfe:** `Referrer-Policy: no-referrer` (der Token steht in der Adresse), `X-Robots-Tag: noindex`, `Cache-Control: private, no-cache`. Der Core-`ETag` ist die Prüfsumme, deshalb wird er pro Link als HMAC neu gesetzt (verrät nichts und ist je Link verschieden).

**Bereich und Gateway (`sudo()` schaltet alle Zugriffsregeln ab)**
- Der Bereich (`_scope_domain`) ist das **Einzige**, was Gäste begrenzt: Ordner `child_of` Wurzel, ohne verborgene Unterordner, nur aktiv, Firma der Freigabe. Er wird an jede Suche gehängt und bei jeder genannten ID geprüft.
- **`any` wird unter Superuser zu `any!`:** Unterdomänen auf Nebenmodellen laufen ohne Regeln.
- **Der Elternordner der Wurzel liegt außerhalb des Bereichs.** Many2one-Werte liest der Core immer als Superuser; über `parent_id` ließen sich Namen und IDs außerhalb herauslesen (auch über Pfade wie `folder_id.parent_id.name`). Darum ist `parent_id` nur als einfaches Feld erlaubt, nie in Pfaden, `any`, Gruppierung oder Sortierung.
- **Das Suchpanel bricht bei einer Wurzel mit Elternordner.** `search_panel_select_range` behält nur Ketten, die bis zu einem Eintrag ohne Eltern vollständig in der Ergebnismenge liegen. Zeigt `parent_id` der Wurzel nach draußen, ist das Panel leer. Lösung: `int.filemanager.folder._read_format` liefert `parent_id = False` für die Wurzel, gesteuert über den **vom Gateway gesetzten** Kontextschlüssel `int_filemanager_share_root`. Das maskiert Panel und `web_read` in einem Zug.
- **`child_of`/`parent_of` lösen mit `comodel.sudo()` auf**, ohne Bereich: `parent_of` ist für Gäste gesperrt; `child_of` bleibt (das Suchpanel braucht es), aber nur mit ganzen Zahlen, die im sichtbaren Bereich liegen.
- **Strings als Werte von Beziehungsfeldern** suchen im Nebenmodell nach Namen. Deshalb sind dort nur ganze Zahlen erlaubt.
- **`opening_info`:** `limit` wird ungeklemmt benutzt und `progressbar_domain` als ungeprüfte Domäne. Es gehen nur `value`, `folded`, `offset`, `limit` (auf 80 geklemmt) und `groups` (Tiefe 3) durch.
- Gesperrt bleiben: Schreiben, `read`, `search_read`, `export_data`, Methoden außerhalb der Tabelle, Kontext vom Client (wird neu gebaut), Domänen über 20.000 Zeichen oder tiefer als 6, mehr als 80 Zeilen, `count_limit` über 1000. Das Gateway antwortet gar nicht ohne `can_view` oder `can_download` (ein Briefkasten-Link liest nichts).
- Domänen werden mit `Domain(...)` zusammengesetzt, `not child_of` ist kein Operator (`~Domain`).
- **Prüfsumme und `ocr_content`** fallen aus der Feld-Whitelist (auch für Gruppieren, Sortieren, Suchen); die Bildadresse bekommt `write_date` statt Prüfsumme.

**Passwort**
- Der Schlüssel nach `unlock` ist `hash_sign` des Core mit `secret = database.secret + password_hash`. Der Hash steht nie in der lesbaren Nutzlast, und der Schlüssel verfällt, wenn das Passwort geändert wird. Vor `verify_hash_signed` Typ und Länge prüfen (Nicht-Strings werfen `AttributeError`).
- Ohne Cookie kennt der Server den Schlüssel nicht aus dem Browser. Darum liefert `GET` bei Links mit Passwort nur eine Hülle ohne Name und Zahlen; `POST …/page` mit dem Schlüssel liefert die Anzeige.
- **Die Passwortbremse ist echte Sicherheit** (eine Prüfung kostet etwa 0,5 s) und läuft daher in der **Datenbank**, nicht im Speicher: Zählung und Eintrag in einer eigenen Transaktion unter `LOCK TABLE … SHARE ROW EXCLUSIVE`, bevor der Hash geprüft wird. Ohne die Sperre sahen 40 gleichzeitige falsche Passwörter den Zähler alle bei 0 (11 statt 5 Prüfungen). Die Bremse ist nicht abschaltbar.

**Downloads und Zähler**
- Bei Dateilinks mit Limit gibt es den Download nur als `POST`. Mit `GET` ließe sich das Limit per `Range: bytes=0-` umgehen, und Link-Prüfer in Mail und Chat verbrauchten ein Limit von 1.
- Gezählt wird **erst nach** der Prüfung von Dokument und Bereich, nie in `_resolve` (sonst verbraucht eine fremde ID das Limit).
- Zähler per bedingtem `UPDATE … RETURNING`. Danach `invalidate_recordset` **und** `modified(...)`, sonst bleibt `state` in der Transaktion veraltet.
- **Unter `REPEATABLE READ` wird eine viel besuchte Freigabe zur heißen Zeile:** `retrying` wiederholt die ganze Anfrage bis zu 5-mal, danach 500. Darum zählt `view_count` höchstens einen Besuch je Minute („Besuche“); `download_count` bleibt exakt.
- Bilder: `ir.binary._get_image_stream_from` begrenzt weder Größe noch Pixel und liest die ganze Quelle in den Speicher. Darum feste Größenliste und vorher `ImageProcess(..., verify_resolution=True)` (Grenze 50 Mpx).

**Hochladen**
- **`max_content_length` im Handler wirkt nicht**, Odoo liest das Mehrteil-Formular vorher. Es gehört als Routenparameter mit Rückruf an die Route. Der Rückruf prüft den vollen Linkzustand ohne Nebenwirkung und liefert bei jedem Misserfolg 64 KiB, sodass ein ungültiger Link nie große Körper annimmt (413 statt 404/410).
- **Der Blob darf erst nach der Grenzprüfung veröffentlicht werden.** `_create_from_stream` hat dafür den Haken `check(stored)` nach dem Messen und vor dem Anlegen. Ein Savepoint-Rollback räumt keine Dateien weg; ohne den Haken könnte ein Inhaber eines vollen Links den Dateispeicher füllen.
- **Grenzen per bedingtem `UPDATE`**, nicht per `lock_for_update` (unter `REPEATABLE READ` zählt dieser mit altem Schnappschuss).
- Mimetype nie vom Browser übernehmen (`None` übergeben); HTML, SVG und XML werden `text/plain`. Endung gegen feste **Sperrliste im Code** (nicht in den Einstellungen) und gegen die Liste des Links; bei Endungen mit verlässlicher Erkennung muss der Dateikopf zur Endung passen. Zeichen der Kategorie `Cf` (Richtungsumkehr) und Punkte oder Leerzeichen am Namensende werden entfernt.
- **Eigene Uploads erkennt der Server an einer Quittung** (`limited_field_access_token`), gebunden an die Freigabe über `document.share_id`, mit ausdrücklichem Ablauf. Eingaben vorher prüfen (ID als int, Quittung als `str` nach festem Muster, höchstens 100 Einträge), weil `verify_limited_field_access_token` bei Nicht-Strings wirft.
- Der Core-Dienst `file_upload` gibt die Antwort nicht zurück: Ende über den Bus (`FILE_UPLOAD_LOADED`), Quittung aus `upload.xhr.responseText`. Die Reihenfolge „eine Datei nach der anderen“ gehört der Seite.

**Einstellungen**
- Odoo speichert in den Einstellungen **keine 0** und einen **Boolean mit Standard „an“ nie als „aus“**. Darum sind Zahlen mindestens 1, und Schalter mit Standard „an“ sind eine `Selection` `("1","0")`.

## 4. Bekannte Grenzen

- „Ansehen ohne Herunterladen“ verhindert den Download-Knopf, nicht das Speichern einer Datei, die der Browser anzeigen darf (PDF, Bild, Text), und nicht das Abfotografieren. Dasselbe gilt für das Download-Limit.
- Die Lese-Bremsen (ungültige Token, Gateway und Dateien, Uploads je Minute) zählen **im Speicher je Worker** und nach Neustart von vorn. Sie schützen vor Überlast, sie rechnen nichts ab. Hinter einer gemeinsamen Firmen-IP sperrt ein Gast mit vielen falschen Token andere Gäste derselben IP; die Sperre gilt deshalb nur für Anfragen mit **ungültigem** Token.
- Der Token steht in Zugriffsprotokollen von Odoo und Proxy. Gegenmittel sind Ablauf, Passwort und Sperre.
- Die Liste „Meine Uploads“ lebt im `localStorage` des Browsers. In einem anderen Browser hilft nur der Ersteller.
- Der Upload-Ordner blockiert das Löschen des freigegebenen Ordners, solange er oder Dateien darin existieren (gewollt). Schaltet man „Hochladen“ am Link später aus, bleibt der Ordner mit den Dateien bestehen.
- Gast-Uploads laufen durch Parser (Vorschau, OCR) im bestehenden Cron mit dessen Zeitgrenzen.

## 5. Noch offen (nur durch Ausprobieren zu klären)

- Abnahme der Gast-Oberfläche im **Browser und am Handy**, auch der Passwort-Neuladeweg (Hülle, Entsperren, Neuladen im selben Tab, zweiter Tab fragt neu) und „ZIP bei Ordnerfreigabe nur Herunterladen“.
- Parallele Uploads und Downloads an der Grenze auf einer laufenden Instanz (`tools/check/share_parallel.py`).
- Antwortzeit der Namenssuche und des Suchpanels mit Zählern bei sehr großen Ordnerbäumen im Gast-Gateway.
- Laden die Gast-Ansichten beim Neuladen mit der bereinigten `opening_info` richtig?
- `Range` bei `POST` (aus Werkzeug gelesen, im Image nicht geprüft) und das Verhalten bei mehreren Datenbanken ohne `dbfilter`.
- Hoot-Tests der Gast-Oberfläche sind nicht geschrieben (der Testlauf hat keinen Browser).
