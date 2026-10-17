# Übergabe: Freigabe-Links für int_filemanager (Stand 2026-10-16)

Für die nächste Sitzung ohne Erinnerung an diese. Ziel in einem Satz: Jeder Nutzer kann eine Datei oder einen Ordner über einen Link freigeben; wer den Link hat, braucht kein Konto und darf genau das, was am Link eingestellt ist (ansehen, herunterladen, hochladen), bis der Link abläuft, sein Limit erreicht oder gesperrt wird.

## Wo steht was

| Was | Wo |
|---|---|
| Bauplan (Revision 6, Hauptdokument) | `docs/int_filemanager_gast_freigabe_bauplan.md` |
| Branch | `feature/int-filemanager-gast-freigabe`, von `origin/master` = 5fd23cf, **nicht gepusht** |
| Stand der Dateien | Plan und diese Übergabe sind committet (Kopfzeile „docs: plan of the share links for guests (revision 6)“, im Branch); Commit und Push immer nur auf Ansage des Nutzers |
| Spike (Referenz, kein Cherry-Pick) | `origin/spike/gast-ui` (be68cae, 2fc23e5, 83cf0f2), darin `controllers/spike.py` und `docs/spike_gast_ui/spike_attacks_final.txt` |
| Memory | `project_gast_ui_spike_entscheidungen_20261016.md` |

## Stand am Abend des 16.10. (zweite Sitzung): Schritte 1 bis 3 gebaut, nichts committet

Der Nutzer gab den Plan frei („Leg los“, ohne Basteleien und faule Kompromisse, autonom bis zum Limit). Gebaut im Arbeitsbaum des Branches `feature/int-filemanager-gast-freigabe`, **nicht committet** (Commit nur auf Ansage; Vorschlag: je Schritt ein `[IMP]`-Commit, Übersetzungen als `[I18N]`). Wochenlimit stand bei 94 %, darum hier Schluss mit dem Bauen und Übergabe.

| Schritt | Inhalt (Dateien unter `int_filemanager/`) | Tests (alle grün auf dem Tower) |
|---|---|---|
| 1 | Modell `models/int_filemanager_share.py`, `share_id` am Dokument (`STORAGE_FIELDS`), `Folder._create_numbered`, `security/int_filemanager_share_security.xml` + Zeile in `ir.model.access.csv`, `views/int_filemanager_share_views.xml` (Liste, Formular, Suche, Menü „Shares“), Einstellungen (`res_config_settings.py` + Block „Share links“) | `test_share.py` (33), `test_share_settings.py` (4) |
| 2 | `tools/request_brake.py` (Zähler im Speicher, Lock, begrenzte Schlüssel), `ShareDenied`-Familie (404/403/410/429) und `_resolve`/`_find_by_token`/`_unlock`/`_unlock_key`/`_key_is_valid` im Modell, Modell `int.filemanager.share.attempt` (Passwortversuche in der Datenbank), `controllers/int_filemanager_share.py` mit der Route `unlock` und den Antwortköpfen | `test_share_brake.py` (12), `test_share_unlock.py` (17 inkl. Prüfreihenfolge) |
| 3 | `Share._hidden_folders`, `Share._scope_domain(model)`, `Folder._read_format` mit Kontextschlüssel `SHARE_ROOT_KEY` (Elternordner der Wurzel verborgen) | `test_share_scope.py` (11, darunter Suchpanel mit Wurzel im Unterordner) |

**Schritt 4 (dritte Sitzung, gebaut, nicht committet):** `tools/share_gateway.py` (Klasse `ShareGateway`, Methodentabelle, Feldlisten, Prüfungen), Route `rpc` im Controller (`type="http"`, Statuscodes statt Traceback), `ShareBadRequest` (400), Gast-Views (Liste, Kanban ohne Prüfsumme, Suche) in `views/int_filemanager_document_views.xml`, `tests/test_share_gateway.py` (30 Tests, grün). Der Test fand eine echte Lücke (`parent_id any […]` hätte den Namen des Elternordners verraten); behoben. js_class der Gast-Views (`int_filemanager_guest_list/kanban`) gibt es erst mit Schritt 6.

**Schritt 5 (gebaut, nicht committet):** Routen `content`, `download` (POST), `thumbnail`, `image` im Controller; `Share._count_visit` (höchstens je Minute), `Share._count_download` (exakt, bedingtes SQL), ETag als HMAC, Pixel- und Größengrenze für Bilder; `tests/test_share_files.py` (22 Tests). Funde dabei: (1) Zähler und `max_downloads` brauchen `default=0` (NULL + 1 ist NULL, das SQL zählte sonst nichts); (2) `_find_by_token` gab den Link mit `active_test=False` weiter, dadurch fanden die Dateiroutes archivierte Dokumente – jetzt `with_context(active_test=True)`; (3) die Gast-Views brauchen `priority=99`, sonst werden sie zur Standardansicht von Liste/Kanban/Suche der Nutzer (6 alte Tests schlugen an). **Volle Suite nach Schritt 5: 655 Tests grün.** Nicht gebaut aus Schritt 5: der Aufruf-Zähler `_count_visit` wird erst von der Seite (Schritt 6) aufgerufen.

**Schritt 6 (gebaut, nicht committet, UI ungeprüft im Browser):** Seiten im Controller (`GET /share/<token>`, `POST …/page`), Templates `views/int_filemanager_share_templates.xml` (Dateiseite ohne Skript, Ordnerseite startet die Owl-App, Passwort-Hülle), `static/src/password_page/password_page.js` (Hülle: `unlock`, Schlüssel im `sessionStorage`, `POST …/page`, Seite ersetzt die Hülle per `document.write` – Abweichung: `/page` liefert ein ganzes HTML-Dokument statt Fragment/Startwerten, damit auch die Ordnerseite samt Bundle nach dem Entsperren startet), Bundle `int_filemanager.assets_guest` und `assets_guest_password` im Manifest, Gast-JS `static/src/guest/` (boot, App, `GuestORM` mit `fetch` auf das Gateway und Statuscodes, Adressen `guest_addresses.js`, Stand-in für den `action`-Dienst, `user`-Patch, Gast-Views). Haken in `static/src/int_filemanager/document_file.js`: das exportierte Objekt `addresses` (`content`, `image`, `params`); die Gast-Seite ersetzt die Funktionen, der Nutzerbetrieb ist unverändert. Die Prüfsumme gibt es für Gäste nicht: das Gateway antwortet auf `checksum`/`ocr_checksum` in einer Spezifikation mit `False` (die Widgets fragen danach; `MASKED` in `tools/share_gateway.py`), die Bild-Adressen nehmen `write_date` als `unique`. `tests/test_share_pages.py` (13 Tests, darunter der Bundle-Bau). **Volle Suite: 669 Tests grün; ruff und eslint grün.** Test-Instanz :8085 steht auf diesem Stand.

**Nicht geprüft / offen aus Schritt 6 (ehrlich):** (1) Ob die Owl-App im echten Browser startet, Liste/Kanban zeigt, Vorschaubilder und Betrachter laden, das Passwort-Neuladen im Tab geht – das kann nur der Nutzer auf :8085 abnehmen (Plan: Abnahme am Handy). Zum Ausprobieren: Menü Filemanager > Shares > Neu (Ordner wählen), Adresse kopieren, im privaten Fenster öffnen. (2) Hoot-Tests (Plan §11, JS) fehlen: ohne Browser nicht lauffähig, daher nicht geschrieben statt ungeprüft geschrieben. (3) Der Knopf „Teilen“ und die Adresse im Formular folgen in Schritt 8. (4) Bundle-Größe und „kein Aufruf an /web/“ im Gast-Bundle sind nicht gemessen (Plan §8). (5) Der Betrachter der Gäste: `document_preview*` ist aus dem Bundle genommen wie im Spike; ob `DocumentFileViewer` ohne die Nutzer-Route lädt, zeigt erst der Browser.

Gezielte Läufe vor Schritt 4: 77 Tests grün. Volle Suite und `check.sh --quick` nach Schritt 1: nur der alte Fund `test_link.py:5` (Form-Import, nicht von mir). Der volle Lauf nach Schritt 3 lief am Ende der Sitzung im Hintergrund; Ergebnis steht in der Sitzung, nicht hier: **vor dem Commit einmal neu laufen lassen** (`tools/check/tests.sh`, `tools/check/check.sh`, pre-commit).

**Abweichungen vom Plan (Revision 6), alle mit Grund; bei Bedarf in den Plan als Revision 7 übernehmen:**
1. **Kein Schutz von `share_id` in `Document.create`:** Nutzer haben kein Recht, Dokumente anzulegen (ACL `perm_create=0`, geprüft in `test_a_user_cannot_make_a_document`); der Schutz in `write` genügt (`share_id` steht in `STORAGE_FIELDS`). Ein Schutz in `create` wäre toter Code.
2. **Kein `consteq` in `_find_by_token`:** der Treffer kommt aus der Suche mit `token = …` über den eindeutigen Index; ein Vergleich danach prüft Gleichheit, die schon gilt.
3. **Kein `Retry-After`-Kopf bei 429:** der `UserError`-Weg des Dispatchers (`werkzeug_default_exceptions[status](text)`) kennt ihn nicht. Wer ihn will, fängt `ShareBusy` in der Route und baut die Antwort selbst (Schritt 4 entscheidet, ob das für das Gateway ohnehin nötig ist).
4. `_resolve` hat statt `unlocking` zwei Schalter: `needs_key=False` (Seite ohne Schlüssel, `unlock`) und `braked=False` (nur `unlock`), weil die Seite zwar ohne Schlüssel, aber unter der Anfragenbremse laufen soll.
5. `name` ist ein gespeichertes berechnetes Feld (`readonly=False`, `precompute`), das mit dem Namen des Ziels startet.
6. Die Meldung beim Löschen eines Ordners mit Upload-Ordner ist die vorhandene „Der Ordner … ist nicht leer“ (nennt den freigegebenen Ordner, nicht den Upload-Ordner); `test_the_folder_of_the_uploads_keeps_the_shared_folder_from_being_deleted` hält das Verhalten fest.
7. Einstellungen für die Upload-Bremse und die Suchbremse kommen mit ihren Schritten (7, 9), nicht jetzt; vorhanden sind: Wer macht Freigaben, Vorgaben und Höchstwerte der Uploads, Passwortlänge, Stunden des Schlüssels, Schalter und Zahlen der Bremsen (`SHARE_DEFAULTS` im Modell ist die eine Stelle der Standardwerte).
8. `Folder._create_numbered` ist neu (Nummerieren eines Ordnernamens); `int_filemanager_import_line.py` hat dieselbe Schleife noch einmal, ich habe sie nicht umgebaut (kleiner Diff).
9. **Übersetzungen `de.po` fehlen noch für alle neuen Zeichenfolgen** (Plan: Schritt 8). Werkzeug: `tools/check/i18n_export.sh`.

**Test-Instanz** `:8085` steht auf dem Stand nach Schritt 1 (Formular „Shares“ bedienbar); Schritte 2 und 3 haben keine Oberfläche außer den neuen Einstellungen: `tools/check/ui_instance.sh` bringt sie auf den heutigen Stand.

**Bash-Falle in dieser Umgebung:** lange Heredocs mit Python oder Testdateien brechen im Bash-Werkzeug mit „unexpected EOF“ ab. Dateien mit dem Schreibwerkzeug anlegen und kurze Befehle ausführen; Patch-Skripte als Datei in den Scratchpad schreiben und starten.

## Was geschehen ist

1. Spike-Befund und die acht Entscheidungen vom 16.10. in einen Bauplan überführt.
2. Plan mit der Sicht normaler Nutzer erweitert (Vergleich mit Cloudreve und FileRun): Datei- und Ordnerlinks, Passwort, Download-Limit, Zähler, „Meine Freigaben“, Knopf „Teilen“.
3. Antworten des Nutzers eingearbeitet: eigene Uploads sehen und entfernen, Grenzen und Bremsen als Einstellungen, Volltextsuche für Gäste als Schritt 9.
4. Hilfsagent prüfte den Plan gegen Odoo-Quelltext, Bausteine und Regeln (Revision 4).
5. Codex (`codex exec -p review`, nur lesend) fand 16 weitere Befunde, vom Hilfsagenten im Quelltext belegt und eingearbeitet (Revision 5).
6. Plan vollständig gelesen, Widersprüche gefunden und mit dem Nutzer geklärt (Revision 6): Besuchszähler je Minute, Passwortbremse nicht abschaltbar, Bauschritte umsortiert (`_read_format` nach Schritt 3, Passwortseite in Schritt 6, Upload-Test in Schritt 7), `share_id` auch in `create` geschützt, Upload-Ordner bleibt bei ausgeschaltetem „Hochladen“, Textfehler. Alle sieben offenen Punkte vom Nutzer mit „so“ bestätigt.

## Entscheidungen des Nutzers (gelten)

- Link = eigener Datensatz `int.filemanager.share` mit optionalem Ablaufdatum; Sperre = Archivieren (`active`).
- Rechte am Link, nicht am Ersteller; Token in der Adresse, kein Cookie.
- Ansehen, Herunterladen, Hochladen frei kombinierbar; Upload-Grenzen je Link (Datei, gesamt, Endungen) in einem eigenen Unterordner.
- Prüfsumme nie zeigen. „Versteckt“ heißt: Unterordner mit „nur erlaubte Nutzer“ bleiben dem Gast verborgen.
- Gäste sehen fremde Uploads nie, ihre eigenen aber schon und dürfen sie entfernen (Quittung im `localStorage`). Das ändert den früheren Beschluss „Gast kann nicht löschen“.
- Grenzen, Bremsen, Passwort-Mindestlänge und weitere Werte sind Einstellungen (`res.config.settings`).
- „Ansehen ohne Herunterladen“ verhindert nur den Download-Knopf, nicht das Speichern angezeigter Dateien; akzeptiert.
- Volltextsuche für Gäste kommt rein (Schritt 9, Schalter am Link, Zeitgrenze).

## Offene Entscheidungen: alle bestätigt (16.10., „alle so“, dazu „ja“ zu Punkt 8)

1. Ziel eines Links ist nach dem Anlegen nicht mehr änderbar (neuer Link statt Ziel ändern).
2. Links mit Passwort: Seite wird nach dem Entsperren per zweiter Anfrage aufgebaut; Neuladen im selben Tab fragt nicht neu.
3. Download-Limit zählt jeden Klick auf den Download-Knopf (POST).
4. Upload-Zähler zählt das Hochgeladene; frei wird er nur, wenn der Gast seine eigene Datei entfernt.
5. Upload-Ordner entsteht beim Speichern des Links.
6. Wer darf Links anlegen: Einstellung, Standard alle Nutzer, die das Ziel sehen.
7. Benachrichtigung bei Upload, Nutzungsbedingungen, „nur für angemeldete Nutzer“: nicht in der ersten Version.
8. Ein Gast darf einen eigenen Upload entfernen, solange die Datei im Upload-Ordner liegt und kein Nutzer sie übernommen hat (A7 im Plan).

## Unbelegt (nur durch Versuch oder durch den Nutzer klärbar)

- **Versuche vom 16.10. gelaufen und bestätigt** (Ergebnisse im Plan §12): `max_content_length`-Rückruf (413 vor dem Handler, Datenbankzugriff im Rückruf möglich), Pfadkonverter `int(max=…)`, Haken `check` in `_create_from_stream` (bei Ablehnung kein Blob), Suchpanel-Wurzel (ohne Maske leer, mit `_read_format`-Maske ok), Passwortprüfung etwa 0,5 s, `pip list` des Images (Werkzeug 3.0.1, keine Bibliothek zur Ratenbegrenzung), Live-Konfiguration (`proxy_mode = True`, keine Worker, eine Datenbank).
- Noch offen: Passwort-Neuladen im Browser (Nutzerabnahme), echte parallele Uploads und Downloads (nur mit parallelen Verbindungen, nicht mit `HttpCase`), `Range` bei `POST`, Verhalten bei mehreren Datenbanken, Zeitgrenze der Gast-Suche (`QueryCanceled`), Antwortzeiten bei großen Ordnerbäumen, `opening_info`, die Oberfläche selbst.
- Die FileRun-Spalte im Vergleich (§0 des Plans) stammt nur aus der Webseite.

## Erster Schritt der neuen Sitzung

1. Den Stand oben („Stand am Abend des 16.10.“) und `git status` lesen; der Nutzer entscheidet, ob und wie die Schritte 1 bis 3 committet werden (Skill `pruefen-und-committen`).
2. Vor Code den Prüfablauf aus `CLAUDE.md` anwenden: passende Originaldokumentation lesen, dann Signaturen und Verhalten im passenden Odoo-19-Core prüfen.
3. **(Erledigt in Sitzung 3: Schritte 4 bis 6.)** Weiter mit **Schritt 7 (Upload-Weg, §6, §8)**; vorher die Abnahme von Schritt 6 durch den Nutzer abwarten oder Befunde einarbeiten. Alter Text zu Schritt 4: erst `origin/spike/gast-ui` lesen (`controllers/spike.py`, `docs/spike_gast_ui/spike_attacks_final.txt`, Wiederholungs-Rezept in `docs/spike_gast_ui/spike_gast_ui_notizen.md`), dann die Angriffsfälle als Tests (`test_share_gateway.py`), dann das Gateway mit `type="http"`, `GatewayDenied` als `ShareDenied`-Unterklasse (Vorlage: die Klassen im Share-Modell), Bereich aus `Share._scope_domain`, Kontextschlüssel `SHARE_ROOT_KEY` im Gateway setzen, `parent_of` sperren, `child_of` nur mit sichtbaren IDs. Der Controller `controllers/int_filemanager_share.py` hat schon `_guest`, `_resolve` und `_guest_headers`.

Vorschlag für den ersten Satz der neuen Sitzung:

> Lies docs/int_filemanager_gast_freigabe_uebergabe_2026-10-16.md (Abschnitt „Stand am Abend“) und wende den Prüfablauf aus CLAUDE.md an. Dann Schritt 4 des Bauplans (§14), erst die Angriffsfälle als Tests, dann das Gateway.

## Stolpersteine

- `_store_stream` glaubt zuerst der Typangabe des Browsers; für Gäste `mimetype=None` übergeben und selbst gegen die Endung prüfen.
- Einstellungen speichern keine 0 und einen Boolean mit Standard „an“ nie als „aus“; Selection verwenden.
- Odoo liest das Mehrteil-Formular vor dem Handler: `max_content_length` gehört in den Routenparameter, nicht in den Handler.
- Hilfsagenten ausdrücklich anweisen, nichts aus dem Internet zu laden (einer hat ungefragt ein PyPI-Wheel geladen, nur gelesen und gelöscht).
- Codex ist nur eine Zweitmeinung; Befunde vor dem Einarbeiten im Quelltext belegen.
- Nutzung: Wochenlimit war am 16.10. bei 91 %; Sitzungen mit `get_usage` im Blick behalten.
