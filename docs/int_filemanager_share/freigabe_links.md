# int_filemanager: Freigabe-Links (Erkenntnisse)

Die Freigabe-Links sind umgesetzt. **Der Code ist maßgeblich** (Modul `int_filemanager_share`: `models/int_filemanager_share.py`, `controllers/int_filemanager.py`, `views/int_filemanager_share_templates.xml`, `static/src/interactions/`). Diese Datei hält nur fest, was der Code nicht zeigt: Entscheidungen, Sicherheitsgründe, Grenzen und offene Prüfungen.

**Ziel:** Ein Nutzer gibt eine Datei oder einen Ordner über einen Link frei. Wer den Link hat, braucht kein Konto und darf genau das, was am Link eingestellt ist (ansehen, herunterladen, hochladen), bis der Link abläuft, sein Limit erreicht oder gesperrt wird.

## 1. Entscheidungen

1. Eine Freigabe ist ein eigener Datensatz (`int.filemanager.share`) mit Ablauf; Sperren = Archivieren.
2. Die Rechte hängen am Link, nicht am Ersteller. Ein Link bleibt gültig, auch wenn der Ersteller den Zugriff verliert.
3. Der Token steht im Pfad. Mehrere Links im selben Browser stören sich nicht. Einziges Cookie ist der Schlüssel eines Passwort-Links (siehe 3), eine Sitzung gibt es nie.
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
15. **Die Gast-Seiten sind serverseitig gerendert, im Layout des Portals** (`portal.frontend_layout`, `portal.portal_searchbar`, `portal.portal_table`, `portal.pager`), wie `project` und `sale` einen Datensatz mit `access_token` zeigen. Ein Ordner ist eine Seite (`…/folder/<id>`, 30 Einträge je Seite, Ordner zuerst). Das Modul hängt deshalb von `portal` ab. Es gibt **keine** Gast-App mit Core-Listen und **kein** Gateway mehr (frühere Fassung: eigene Whitelist auf dem ORM als Superuser, Bundle mit ~40 Core-Pfaden). Begründung und Vergleich der Wege: Arbeitsstand vom 26.10.2026, Muster P1 (Token-Seite) aus `portal/controllers/portal.py` (`_document_check_access`).
16. Gäste suchen nach Namen (im Ordner und darunter). Keine Volltextsuche, keine Tags, kein Kanban, kein Ordnerbaum: Sie wäre teuer (Zeitgrenze, eigene Bremse), und Trefferausschnitte könnten Text aus verborgenen Ordnern verraten.
17. **Nicht enthalten:** ZIP-Download eines freigegebenen Ordners für Gäste (müsste `_scope_domain` beachten, `folder._zip_entries` kennt ihn nicht), Benachrichtigung bei Upload, Nutzungsbedingungen vor dem Download, „nur für angemeldete Nutzer“, Bearbeiten oder Kommentieren durch Gäste.

## 2. Aufbau in Kürze

Modell, Routen und Seiten: Code.

- **Rechte:** Nutzer sehen nur die eigenen Freigaben (Regel `create_uid`), Administratoren alle. Anlegen darf man nur, was die **Ordner** dem Nutzer zeigen; eine Datei, die er nur über einen verknüpften Datensatz sieht, darf er nicht weitergeben. Die Einstellung `share_creators` kann das auf Administratoren beschränken.
- **Prüfwerkzeuge:** Tests `test_share_*.py`, dazu `tools/check/share_live.sh`, `share_attacks.py`, `share_parallel.py` (Angriffsfälle, parallele Verbindungen und Seitenzeiten auf einer Wegwerf-Instanz). Das Upload-Skript ist **nur im Browser** prüfbar (siehe 5).

## 3. Sicherheitsgründe, die der Code allein nicht zeigt

**Anfrage und Sitzung**
- **Die Seiten sind Frontend-Routen (`website=True`).** Nur dann liefert Odoo dem Portal-Layout die Sprachen (`frontend_languages`), sonst bricht das Rendern ab. Folge: Odoo setzt das Cookie `frontend_lang` und akzeptiert Sprachpräfixe (`/de/int_filemanager/…`). Das Cookie des Schlüssels hat deshalb den Pfad `/` (ein engerer Pfad ginge mit dem Präfix verloren) und trägt den Token im **Namen** (`int_filemanager_share_key_<token>`), damit sich Links nicht überschreiben. Die Tests prüfen „keine Sitzung, kein Schlüssel“, nicht „kein Cookie“.
- **Fehler:** Die Routen sind `type="http"`, nicht `jsonrpc`. Der JSON-RPC-Dispatcher antwortet immer mit HTTP 200 und hängt jeder Ausnahme den **vollständigen Traceback** an. `type="http"` gibt bei `UserError` nur Status und Text zurück. Eigene Fehler sind `UserError`-Unterklassen mit `http_status`.
- **Alle Gast-Routen:** `save_session=False` (sonst bekommt jeder Gast ein `session_id`-Cookie), `csrf=False` bei POST (die Berechtigung ist der Token; `unlock` setzt nur das Cookie dieses Links für den, der das Passwort kennt, und jeder Versuch wird gezählt), kleine `max_content_length`.
- **Öffentlicher Benutzer erzwingen.** `auth="public"` stellt ihn nur ein, wenn die Sitzung keine UID hat. Öffnet ein angemeldeter Nutzer den Link, liefen Uploads unter dessen Rechten. Deshalb als Erstes `request.update_env(user=base.public_user)`.
- **Antwortköpfe:** `Referrer-Policy: no-referrer` (der Token steht in der Adresse), `X-Robots-Tag: noindex`, `Cache-Control: private, no-cache`. Der Core-`ETag` ist die Prüfsumme, deshalb wird er pro Link als HMAC neu gesetzt.
- **Ein NUL-Byte im Pfad** (`…/folder/1%00`) gibt einen 500 des **Core**: Jede Adresse ohne Route geht an `ir.http._serve_fallback`, das sie als URL eines Anhangs sucht, und die Datenbank lehnt das NUL ab. Das trifft jede Odoo-Instanz und steht nicht in `share_attacks.py`.

**Bereich (Lesen als Superuser)**
- Die Seiten lesen als Superuser, **nachdem** der Token geprüft ist; die Gäste haben keine Rechte auf den Datensätzen. Der Bereich (`_scope_domain`) ist das **Einzige**, was begrenzt: Ordner `child_of` Wurzel, ohne verborgene Unterordner, nur aktiv, Firma der Freigabe. Er wird an **jede** Suche gehängt, und der Ordner der Adresse muss darin liegen (sonst 404, dasselbe für verborgene, archivierte und fremde Ordner).
- **Nur einfache Werte gehen ins Template** (Name, Größe als Text, Datum, Adressen). Keine Datensätze, keine Prüfsumme. Alles geht durch `t-out`.
- **Der Elternordner der Wurzel steht nirgends:** Der Pfad (`breadcrumbs`) beginnt bei der freigegebenen Wurzel. Ein Ordner über der Wurzel liegt nicht im Bereich und ist damit 404.
- **Suchtext:** Odoos `ilike` nimmt `%` und `_` als Muster. Der Text wird mit `escape_psql` entschärft, Steuerzeichen werden entfernt (ein NUL gab sonst einen 500 der Datenbank) und auf 100 Zeichen gekürzt. Die Sortierung kommt aus einer festen Tabelle (`SORTINGS`), die Seite aus `portal.pager` (begrenzt auf die Zahl der Seiten). Eine Suche zeigt Treffer unterhalb des Ordners und die Spalte „Ordner“.

**Passwort**
- Der Schlüssel nach `unlock` ist `hash_sign` des Core mit `secret = database.secret + password_hash`. Der Hash steht nie in der lesbaren Nutzlast, und der Schlüssel verfällt, wenn das Passwort geändert wird. Vor `verify_hash_signed` Typ und Länge prüfen (Nicht-Strings werfen `AttributeError`).
- **Ablauf ohne Skript:** Die Passwortseite ist ein Formular (`POST …/unlock`). Ein richtiges Passwort setzt das Cookie (`HttpOnly`, `SameSite=Lax`, Dauer wie der Schlüssel) und leitet mit 303 auf die Seite. Ein falsches ergibt dieselbe Seite mit Meldung und Status 403, die Bremse 429. Ohne gültigen Schlüssel zeigt **jede** Seite des Links (auch `…/folder/<id>`) nur das Formular, ohne Name und Zahlen. Ein Schlüssel in der Adresse (`?k=`) gilt nicht mehr.
- **Die Passwortbremse ist echte Sicherheit** (eine Prüfung kostet etwa 0,5 s) und läuft daher in der **Datenbank**, nicht im Speicher: Zählung und Eintrag in einer eigenen Transaktion unter `LOCK TABLE … SHARE ROW EXCLUSIVE`, bevor der Hash geprüft wird. Ohne die Sperre sahen 40 gleichzeitige falsche Passwörter den Zähler alle bei 0. Die Bremse ist nicht abschaltbar.

**Downloads und Zähler**
- Bei Dateilinks mit Limit gibt es den Download nur als `POST`. Mit `GET` ließe sich das Limit per `Range: bytes=0-` umgehen, und Link-Prüfer in Mail und Chat verbrauchten ein Limit von 1.
- Gezählt wird **erst nach** der Prüfung von Dokument und Bereich, nie in `_resolve` (sonst verbraucht eine fremde ID das Limit).
- Zähler per bedingtem `UPDATE … RETURNING`. Danach `invalidate_recordset` **und** `modified(...)`, sonst bleibt `state` in der Transaktion veraltet.
- **Unter `REPEATABLE READ` wird eine viel besuchte Freigabe zur heißen Zeile:** `retrying` wiederholt die ganze Anfrage bis zu 5-mal, danach 500. Darum zählt `view_count` höchstens einen Besuch je Minute; `download_count` bleibt exakt. Die Serialisierungsfehler im Protokoll der Live-Prüfung sind dieses Wiederholen.
- Bilder: `ir.binary._get_image_stream_from` begrenzt weder Größe noch Pixel und liest die ganze Quelle in den Speicher. Darum feste Größenliste und vorher `ImageProcess(..., verify_resolution=True)` (Grenze 50 Mpx).

**Hochladen**
- **`max_content_length` im Handler wirkt nicht**, Odoo liest das Mehrteil-Formular vorher. Es gehört als Routenparameter mit Rückruf an die Route (`upload_limit`, liest den Schlüssel aus dem Cookie). Der Rückruf prüft den vollen Linkzustand ohne Nebenwirkung und liefert bei jedem Misserfolg 64 KiB, sodass ein ungültiger Link nie große Körper annimmt (413 statt 404/410).
- **Der Blob darf erst nach der Grenzprüfung veröffentlicht werden.** `_create_from_stream` hat dafür den Haken `check(stored)` nach dem Messen und vor dem Anlegen. Ein Savepoint-Rollback räumt keine Dateien weg.
- **Grenzen per bedingtem `UPDATE`**, nicht per `lock_for_update` (unter `REPEATABLE READ` zählt dieser mit altem Schnappschuss).
- Mimetype nie vom Browser übernehmen (`None` übergeben); HTML, SVG und XML werden `text/plain`. Endung gegen feste **Sperrliste im Code** und gegen die Liste des Links; bei Endungen mit verlässlicher Erkennung muss der Dateikopf zur Endung passen. Zeichen der Kategorie `Cf` und Punkte oder Leerzeichen am Namensende werden entfernt.
- **Eigene Uploads erkennt der Server an einer Quittung** (`limited_field_access_token`), gebunden an die Freigabe über `document.share_id`, mit ausdrücklichem Ablauf. Eingaben vorher prüfen (ID als int, Quittung als `str` nach festem Muster, höchstens 100 Einträge).
- **Das Skript** (`static/src/interactions/share_upload.js`) ist eine Odoo-`Interaction` im Bundle `web.assets_frontend`. Das Bundle liegt im **lazy** Teil des Frontends; Schaltflächen sperrt Odoo bis dahin und wiederholt den Klick danach. **`addListener` ist erst in `start()` erlaubt**, in `setup()` bricht die ganze Interaction beim Start ab, ohne sichtbaren Fehler (so ist es bei der ersten Fassung passiert; nur der Browser zeigte es). Die Meldungen stehen als `data-msg`-Elemente im Template, dort werden sie übersetzt; das Skript setzt nur Text (`textContent`), nie HTML.

**Einstellungen**
- Odoo speichert in den Einstellungen **keine 0** und einen **Boolean mit Standard „an“ nie als „aus“**. Darum sind Zahlen mindestens 1, und Schalter mit Standard „an“ sind eine `Selection` `("1","0")`.

## 4. Bekannte Grenzen

- „Ansehen ohne Herunterladen“ verhindert den Download-Knopf, nicht das Speichern einer Datei, die der Browser anzeigen darf (PDF, Bild, Text), und nicht das Abfotografieren. Dasselbe gilt für das Download-Limit.
- Die Lese-Bremsen (ungültige Token, Anfragen je Minute, Uploads je Minute) zählen **im Speicher je Worker** und nach Neustart von vorn. Sie schützen vor Überlast, sie rechnen nichts ab. Hinter einer gemeinsamen Firmen-IP sperrt ein Gast mit vielen falschen Token andere Gäste derselben IP; die Sperre gilt deshalb nur für Anfragen mit **ungültigem** Token.
- Der Token steht in Zugriffsprotokollen von Odoo und Proxy. Gegenmittel sind Ablauf, Passwort und Sperre.
- Die Liste „Meine Uploads“ lebt im `localStorage` des Browsers. In einem anderen Browser hilft nur der Ersteller.
- Der Upload-Bereich steht auf jeder Seite des Ordnerbaums, die Uploads gehen immer in den Upload-Ordner des Links (nicht in den Ordner, den der Gast gerade ansieht).
- Der Upload-Ordner blockiert das Löschen des freigegebenen Ordners, solange er oder Dateien darin existieren (gewollt). Schaltet man „Hochladen“ am Link später aus, bleibt der Ordner mit den Dateien bestehen.
- Gast-Uploads laufen durch Parser (Vorschau, OCR) im bestehenden Cron mit dessen Zeitgrenzen.
- Das Portal-Layout zeigt „Anmelden“ und das Firmenlogo der Datenbank („Your logo“, wenn keines gesetzt ist) sowie die Fußzeile mit „Powered by Odoo“.

## 5. Noch offen (nur durch Ausprobieren zu klären)

- Abnahme am **Handy**; der Browser-Test des Desktops (Upload, zu große Datei, gesperrte Endung, „Meine Uploads“ nach Neuladen, Entfernen) lief am 26.10.2026 auf der Testinstanz durch, ein Hoot-Test des Skripts ist nicht geschrieben (der Testlauf hat keinen Browser).
- Passwortseite im Browser mit echter Eingabe (nur über HTTP geprüft: 403, Cookie, Seite mit und ohne Cookie).
- Verhalten der Sprachumschaltung im Fuß (`/de/…`) bei Links mit Passwort.
- Parallele Uploads und Downloads an der Grenze auf einer laufenden Instanz (`tools/check/share_parallel.py`): am 26.10.2026 in Ordnung (3 von 8 Uploads, 5 von 12 Downloads, Besuche und Passwortbremse wie erwartet).
- `Range` bei `POST` (aus Werkzeug gelesen, im Image nicht geprüft) und das Verhalten bei mehreren Datenbanken ohne `dbfilter`.
