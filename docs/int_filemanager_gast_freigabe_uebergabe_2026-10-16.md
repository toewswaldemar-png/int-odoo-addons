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

Es gibt **noch keine Zeile Code**.

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

1. Der Nutzer gibt den Plan (Revision 6) frei; dann erst Code. Der Plan ist durchgelesen, nichts Offenes bei den Entscheidungen.
2. Vor Code alle Dateien in `docs/odoo_regeln/` lesen (Pflicht laut `CLAUDE.md`).
3. Dann: vor Code alle Dateien in `docs/odoo_regeln/` lesen (Pflicht laut `CLAUDE.md`), dann Schritt 1 des Plans (§14): Modell `int.filemanager.share`, `share_id` am Dokument, Rechte und Regeln, Verwaltungsansichten, Einstellungen, Tests `test_share.py`.

Vorschlag für den ersten Satz der neuen Sitzung:

> Lies docs/int_filemanager_gast_freigabe_uebergabe_2026-10-16.md und die Regeln in docs/odoo_regeln/. Dann Schritt 1 des Bauplans (§14), erst die Tests, dann der Code.

## Stolpersteine

- `_store_stream` glaubt zuerst der Typangabe des Browsers; für Gäste `mimetype=None` übergeben und selbst gegen die Endung prüfen.
- Einstellungen speichern keine 0 und einen Boolean mit Standard „an“ nie als „aus“; Selection verwenden.
- Odoo liest das Mehrteil-Formular vor dem Handler: `max_content_length` gehört in den Routenparameter, nicht in den Handler.
- Hilfsagenten ausdrücklich anweisen, nichts aus dem Internet zu laden (einer hat ungefragt ein PyPI-Wheel geladen, nur gelesen und gelöscht).
- Codex ist nur eine Zweitmeinung; Befunde vor dem Einarbeiten im Quelltext belegen.
- Nutzung: Wochenlimit war am 16.10. bei 91 %; Sitzungen mit `get_usage` im Blick behalten.
