# int_filemanager: Umsetzung der Review (2026-10-26)

20 Vorschläge aus der Durchsicht des Kerns gegen Odoo-19-Code und -Doku. Stand: alle sieben Module, 1036 Odoo-Tests, 0 Fehler (`tools/check/tests.sh`, Tower). Nicht gelaufen: Hoot-Tests, Tours (das Test-Image hat keinen Browser), Ruff (nicht installiert).

| # | Vorschlag | Umsetzung | Beleg |
|---|---|---|---|
| 1 | Pfad-Maskierung greift im Web-Client nicht | `_compute_display_name` fragt die Rechte als `self.env.uid` (`with_user`), nicht als Superuser des Many2one-Lesens; ohne Leserecht an Ordnern bleibt "…" | `test_folder_path`: `web_read` als Nutzer zeigt "… / Opened" |
| 2 | `complete_name` per Suche/Gruppierung lesbar | `groups` Administrator; Sortieren bleibt für alle über `_order_field_to_sql`; `_read_format`-Notbehelf entfällt | `test_folder_path`: lesen, suchen, gruppieren = AccessError, Sortieren geht, Umbenennen als Nutzer geht |
| 3 | Namen nur beim Upload bereinigt | Mixin `int.filemanager.named`: NFC, keine Steuerzeichen, trimmen in `create`/`write`; `@api.constrains` (nicht leer, nicht `.`/`..`, ≤ 255). Schrägstrich bleibt erlaubt (der Share-Test mit `<b>…</b>` zeigte, dass das gewollt ist) | `test_name` |
| 4 | Admin-Gruppe ohne Benutzer | `user_ids` mit `base.user_root` und `base.user_admin` (wie `project`) | `test_rights_matrix` |
| 5 | Chatter-Nachricht und Follower je Upload | `mail_create_nolog` und `mail_create_nosubscribe` für Dokumente, `mail_create_nolog` für nummerierte Ordner | `test_chatter` |
| 6 | Temp-Datei in voller Größe beim Upload | Nicht im Code lösbar (Werkzeug liest vor dem Controller). Dokumentiert in `betrieb.md` und im Docstring von `max_upload_size` | Dokumentation |
| 7 | `hierarchical_naming` gegenüber dem Core invertiert | Standard an wie bei `product.category`/`hr.department`; die acht `context=` in den Views entfallen; Suchpanel (Core) und Tracking bleiben schlicht | `test_folder_path`, Suchpanel-Test |
| 8 | Private `ir.attachment`-APIs | Ein Adapter `tools/filestore.py` (auch vom OCR-Modul genutzt) und `test_core_contract` für Signaturen und Typregeln | `test_core_contract` |
| 9 | Eigenes Cron-Zeitbudget hängt an Interna | Bewusst beibehalten (Begründung steht in `erkenntnisse.md`: Fenster von `ir.cron` ≠ Abbruchgrenze). Abgesichert: `test_core_contract` prüft `MIN_TIME_PER_JOB`, `SLEEP_INTERVAL`, `_commit_progress(remaining)` und die Optionen | `test_core_contract` |
| 10 | `size` als `Float` ungenau | Der Befund war zu streng: ein float8 hält ganze Zahlen bis 2^53 (8 PiB) exakt. Keine Änderung, nur der Kommentar | Kommentar am Feld |
| 11 | Namenslogik doppelt | Im Mixin: Bereinigung, Prüfung, Nummerierung (`_create_numbered_name`), Kollisionen beim Verschieben (`_names_taken`); Ordner und Dokument behalten ihre Signaturen (`_create_numbered`) | alle bestehenden Tests, `test_name` |
| 12 | Settings-Defaults dreifach, Prozess im Compute | Defaults aus `SETTINGS`/`PREVIEW_ENABLED_DEFAULT`; Version von `soffice` per `@tools.ormcache` | `test_document_office_preview` |
| 13 | Doppelte Konstanten und Routen | `FOLDER_ZIP_PATH` und `DOCUMENTS_ZIP_PATH` je einmal, vom Controller benutzt; `PATH_SEPARATOR` im Compute; `NAME_MAX_LENGTH` im Mixin | Zip-Tests |
| 14 | Tote Migration | `migrations/` und `test_migration_earlier_layers` entfernt | Lauf |
| 15 | Icon und Datenreihenfolge | Icon war kein Platzhalter (128 × 128, gültig): keine Änderung. Manifest: Gruppen, Regeln, dann CSV | Installation |
| 16 | Tests der Oberfläche | Neu: `test_core_contract`, `test_name`, `test_query_count`, `test_uninstall`, erweitert `test_folder_path`, `test_chatter`, `test_rights_matrix`. Tours und Hoot: nicht gebaut, weil nicht ausführbar (Test-Image ohne Browser) | 1036 Tests |
| 17 | Skalierung ungemessen | `test_query_count`: die Abfragen der Listen (Dokumente, Ordner, Suchpanel) sind für 3 und für 33 Unterordner gleich viele. Eine Messung mit Zehntausenden Ordnern steht aus | `test_query_count` |
| 18 | Tags halb fertig | Eindeutig ohne Beachtung der Schreibweise (`UniqueIndex`); Nutzer legen an und ändern, löschen nur Administratoren; `color_field` in allen Views | `test_rights_matrix` |
| 19 | Vorschau nur Linux | `missing_programs`: der Job prüft `soffice`, `nice`, `timeout` und meldet es in Log und Einstellungen; `limited()` bricht ohne `os.nice` nicht | Einstellungs-Test |
| 20 | Kein `uninstall_hook` | Entfernt `<Filestore>/int_filemanager` nach dem Commit (`cr.postcommit`), eine zurückgerollte Deinstallation verliert nichts | `test_uninstall` |

## Verbessert

- **Rechte:** Pfade versteckter Ordner stehen nicht mehr in Many2one-Feldern; der Sortierschlüssel verrät nichts; Tags löscht nur der Administrator.
- **Daten:** Ein Name ist überall derselbe Name (kein zerlegtes "ä" am Index vorbei, keine leeren Namen, keine 300 Zeichen).
- **Last:** Ein Upload ist ein Datensatz, nicht drei (kein Log, kein Follower).
- **Wartung:** Namenslogik einmal statt zweimal (Mixin), Core-Abhängigkeiten an einer Stelle mit Test, keine Views mit Kontext-Schlüssel, eine Quelle für Konstanten.
- **Betrieb:** Fehlende Programme werden gemeldet, `TMPDIR` und Deinstallation beschrieben, die Version von LibreOffice nicht bei jeder Änderung neu abgefragt.

## Bekannte Grenzen

- Der Name des **direkten** Elternordners, auf den ein sichtbarer Ordner zeigt, erscheint weiter mit dem Many2one (Core-Verhalten für jeden Datensatz); nur der Pfad darüber endet bei "…".
- Hoot-Tests, Tours und Ruff sind nicht gelaufen. `de.po` ist von Hand ergänzt: der Export mit `I18N_LANG=de_DE` zieht Core-Übersetzungen mit und verändert vorhandene Einträge, er wurde nicht übernommen.
- Das Test-Image hat keinen Browser; die Oberfläche (Suchpanel zeigt den schlichten Namen, Auswahlfelder den Pfad) ist an der Server-Seite geprüft, nicht im Browser angesehen.
