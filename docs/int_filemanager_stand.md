# int_filemanager – Stand und nächste Schritte (Einstieg für neue Sitzungen)

Stand 2026-10-02. Branch `feature/int-filemanager-v2` (der bisherige Stand liegt auf `master`, Tag `int_filemanager-v1`), Modulversion 19.0.1.23.0.
Der Code ist maßgeblich; **warum** etwas so ist, steht in `int_filemanager_entscheidungen.md`, die Grundregeln I1–I13 ebenfalls dort. Der Aufbau steht in Abschnitt 7. Alte, ausführliche Dokumente: Git-Tag `docs-vor-aufraeumen-2026-10-02`.

## 1. Was steht

Jeder Schritt ist erst fertig, wenn seine Abnahme erfüllt ist; der nächste beginnt danach. **Für jeden Schritt zusätzlich:** pre-commit, `test_lint` und
odoo-ls ohne Befund im eigenen Code, `i18n/de.po` vollständig, Gegenlese durch ein zweites Modell.

| Schritt | fertig, wenn | Stand |
|---|---|---|
| 3 Fundament (Datenmodell, Blob-Speicher, Schreibwege, Rechte) | je Grundregel ein grüner Test, für I1–I6 und I9 auch mit Abbruch mitten im Vorgang; Rechte-Tests für Nicht-Admins über alle Wege **und alle Tabellen**; kein `sudo` auf Nutzereingaben | fertig; 16 Rennszenarien (`tools/v2check/race.sh`) auf Tower zuletzt 2026-10-02 grün |
| 4 Oberfläche (Explorer auf `int_filemanager.node`) | alle Funktionen (außer Office/Einliefern) in der Oberfläche bedienbar; Upload 3 GB mit Abbruch und Fortsetzen | gebaut; Abnahme frei durch den Nutzer, nicht per Checkliste |
| 5 Vorschau, Text, Metadaten, OCR mit Wortpositionen | Vorschau für die häufigen Formate (inkl. HEIC/RAW/TIFF, Video-Standbild, Office, PDF, Scans mit OCR); Metadaten; Fehler sichtbar statt still; Odoo-Prozess bleibt bei defekten Dateien stabil; Test, dass Odoo Ergebnisse nie dekodiert (I13) | fertig im Server; Verwalter-Werkzeuge (Diagnose, "neu erzeugen", Konfiguration) **nicht** gebaut |
| 5 Werterkennung | (eigene Scheiben, siehe Entscheidungen 5) | Server (Katalog, Erkennung, Lernen pro Absender, Spalten-/Rechte-Entwurf), Volltextsuche, Formularfelder, **Eigenschaften-Formular** (Rechtsklick → Eigenschaften) gebaut; Wortklick nur für PDF |
| 6 Office (ONLYOFFICE) | Speichern ergibt neue Fassung; zwei gleichzeitige Bearbeitungen führen zu Hinweis statt Verlust | offen |
| 7 Eingangsordner | Scanner-Datei wird erst nach Fertigschreiben übernommen; kein Duplikat nach Abbruch; Fehlerablage funktioniert | offen |
| 8 Übernahme des Bestands | Probelauf auf der Testinstanz vollständig; Zählung und Prüfsummen stimmen; Rückweg geprobt | offen |
| 9 Netzlaufwerk | nach Erfahrungen aus 4–8 entscheiden | später |

**Ideenkatalog** (`int_filemanager_paperoffice_ideenkatalog_2026-10-01.md`): A1 (Wortklick) nur für PDF umgesetzt, A2 teilweise (Umrandung im Dokument, Warnsymbol bei unsicheren Werten, aber keine Markierung "automatisch gelesen" am Feld), A7 nur geplant; C10, B5, E4, F1, F3, F5 und H6 sind schon vorhanden oder im Neubau vorgesehen; alle anderen nicht begonnen.

Zuletzt geprüft (2026-10-01): pre-commit grün, 555 Odoo-Tests, 76 Umwandler-Tests, 72 Node-Tests, `v2check` ohne neue Befunde
(12 alte Befunde im bestehenden Code unverändert). **Neu 2026-10-02:** Prüfautomatik und Odoo-19-Regeln aus `master` übernommen
(`pruefautomatik_2026-10-02.md`, `odoo_regeln/`); Docker-Läufe auf Tower und pre-commit auf Windows noch nicht verifiziert.
**Review 2026-10-02:** gesamtes Modul gegen alle Regeldateien gelesen (Ergebnis in 3.1 bis 3.5); dabei wurde nichts ausgeführt, auch nicht pre-commit,
`test_lint`, odoo-ls oder die Tests. Ein pre-commit-Hook ist auf dem Arbeitsrechner nicht installiert (`.git/hooks` leer, `pre_commit` fehlt).
**Umbau `int_filemanager_node.py` 2026-10-02** (3.6): pre-commit (ruff, pylint-odoo) auf den geänderten Dateien grün, 642 Odoo-Tests (davon 22 neu), 16 Rennszenarien,
`v2check.sh` (odoo-ls, `test_lint`) ohne neue Befunde (12 alte im bestehenden Code); nichts davon committet.

## 2. Nächste Schritte (in dieser Reihenfolge)

**Vorrang vor allem anderen:** die offenen Sicherheitsbefunde aus 3.1 (Altcode live auf HM-SRV); N1 und das Löschen beliebiger Pfade sind auf dem
Branch behoben (noch nicht committet, noch nicht auf HM-SRV), ebenso 3.2 (Rechtemodell des Branches). Die Regelabweichungen aus 3.3 bis 3.5 folgen
getrennt davon.

1. **Rückmeldung des Nutzers zum Eigenschaften-Formular** abwarten (Zoom auf den Wert, Rahmenrand, Layout).
2. **Prüf-Fenster entfernen:** `static/src/int_filemanager/v2/value_review/` (Client-Aktion, XML, SCSS, Tests), Menüpunkt `int_check_values`,
   `onCheckValues` in `controller_mutations.js`, Übersetzungen. Vorher `viewer_overlay.js`, `value_review_geometry.js`,
   `value_review_edits.js` (+ Node-Tests) nach `properties/` verschieben und Importe nachziehen.
3. **Wortklick fertigstellen:** Bilder (Wortschicht über `<img>`), Handy (zum Dokument scrollen und zurück).
4. **A7 Wörterbuch** für OCR-Korrekturen: Modell `int_filemanager.ocr_correction`, bearbeitbare Liste, reine Funktion `apply_corrections` in
   `_recognition_page`, nur bei `ocr != "none"`. Offene Entscheidungen: sofort wirken lassen, Sprache weglassen, nur Einzelwörter.
5. **Ideenkatalog** `int_filemanager_paperoffice_ideenkatalog_2026-10-01.md` (A1–H6) mit dem Nutzer durchgehen. Offene Entscheidungen dort:
   Was ist der "Dokumenttyp" (Tag/Status/Feld)? Virtuelle Ordner? Notizen auf Bereichen und Stempel? Papier-Workflows?
6. **Gegenlese-Befunde** (Codex, 2026-10-01) bearbeiten, siehe 3.
7. Danach Schritt 6 (Office), 7 (Eingangsordner), 8 (Übernahme).

**Vor Schritt 6/8 klären:**
- **ONLYOFFICE-Zertifikat** (heute nur auf einem Rechner vertraut; die AD-CAs sind offline); ohne Lösung ist der Branch für Word/Excel ein Rückschritt gegenüber `master`.
- **Notfall-Export ohne Odoo** (rekursive SQL-Abfrage über `parent_id` + Kopie aus `blobs/ab/cd/<sha256>`; auf HM-SRV-Testinstanz 33 Ordner,
  219 Dateien, 0 Prüfsummenfehler): als festes Werkzeug ins Repo (kopieren statt Hardlink, Änderungsdatum übernehmen, Prüfsumme je Datei),
  Probelauf gegen das Backup in die Abnahme von Schritt 8.
- **Blob-Prüflauf:** `adopt_hashed` vertraut beim Zusammenlegen einer vorhandenen Datei dem Hash, ohne nachzurechnen; ein beschädigter Blob
  würde eine gute neue Kopie verdrängen. Cron, der Blobs nachrechnet und meldet, plus Ersetzen eines als beschädigt bekannten Blobs.
- Nachholen des ganzen Bestands (Kacheln für 209k Bilder) nur gedrosselt vorgesehen, noch nicht am echten Bestand gemessen.
- Umwandler-Image `fmconverter:dev` ist nur auf Tower gebaut, noch kein Deployment-Weg.
- Netzlaufwerk-Entscheidung (WebDAV `odoo fmdav` oder SMB über Odoo-FUSE) erst nach Nutzung, Hintergrund in den Entscheidungen, Abschnitt 3.

**Aus der früheren Dauerlauf-Liste noch offen (Analyse, nichts bauen):** (A5) die Modelle von `master` (`extracted_value`, Muster) gegen das Schema des Branches legen,
Vorschlag "übernehmen / verwerfen / neu erkennen" je Feld an einer Kopie; (A6) alle seit dem Tag `int_filemanager-v1` geänderten Dateien mit zweitem
Modell gegenlesen und Befundliste ablegen; (A7) fehlt dem Image `odoo:19.0-hm-test` noch ein 19.0-Sicherheits-Fix, Update-Weg vorschlagen.

## 3. Bekannte Mängel und offene Befunde

- Gesamtbetrag der Henrich-Rechnung hat keinen gespeicherten Ort (springt nicht).
- Gedrehte PDF-Seiten bekommen keinen Zoom auf den Wert.
- Weitere unsichtbare Textarten (Schrift < 1 pt, außerhalb der Seite) werden nicht gefiltert; weiß gefüllter Text mit schwarzer Kontur wird entfernt (bekannte Grenze).
- Modulversion nicht erhöht (19.0.1.23.0).
- **Codex-Gegenlese 2026-10-01:** (1) *echt:* `ViewerOverlay.attach()` lädt die Wörter **aller** Seiten sofort (`page_words` je Seite), bei langen PDFs viele
  Aufrufe; Fix: erst im Wortmodus oder nur sichtbare Seiten. (2) *plausibel, im Browser prüfen:* ein getippter Wert geht verloren, wenn man mit dem
  Speichern-Kürzel speichert, ohne das Feld zu verlassen (`useInputField` hängt am Bus des inneren `Record`); Fix: im Werte-Widget `hooks.onRootLoaded`
  das innere Record merken und das Ereignis des Formulars dorthin weiterreichen. (3) *selten:* Kontaktwechsel lässt die Vorschläge beim alten
  Absender; Fix: nach Kontaktwechsel `values_json` neu lesen.
- Vom ersten Handtest (2026-09-28) noch zu prüfen: `rememberBase` wird nie aufgerufen (`uploads_service.js`), "Neue Fassung" nimmt dann die beim
  Seitenladen aktuelle Fassung als Basis; Meldung "frühere Uploads wurden unterbrochen" kann veraltet sein (`upload_manager.js`).
- Nach neuer Wörter-Spec werden vorhandene `words`-Ergebnisse gelöscht und im Hintergrund neu gelesen; bis dahin findet die Volltextsuche diese PDFs nicht.
- Live-Datenbanken auf `pg_trgm` nicht geprüft; die Migration legt die Erweiterung an, wenn der DB-Benutzer darf, sonst Warnung.
- Der Code von `master` (u. a. `native_ui/`, `models/filemanager_file.py`, `publish_service.py`) verweist in Kommentaren noch auf gelöschte Dokumente (Papierkorb, Ausbau, native UI, DB-Vorrang-Konzept); die Verweise verschwinden mit dem Entfernen des alten Codes in Schritt 8, die Dokumente stehen im Git-Tag.
- Sicherheitslücke **N1** und das Löschen beliebiger Pfade sind auf dem Branch behoben (3.1), `master` und damit HM-SRV haben den Fix **noch nicht**;
  weitere Altcode-Lücken stehen in 3.1. In `web-filemanager` liegen nicht committete Änderungen des Nutzers (unberührt lassen).

### 3.1 Sicherheit im Altcode (`master`, läuft live auf HM-SRV)

**Behoben auf dem Branch am 2026-10-02, noch nicht committet, nicht auf `master`/HM-SRV.** Gemeinsame Ursache von N1 und dem Löschen beliebiger
Pfade: `int_filemanager.file` ist nur der Index der Platte, aber jeder Dateimanager-Nutzer durfte die Zeilen per ORM (`call_kw`, `/json/2`) anlegen
und in allen Feldern beschreiben, und mehrere Stellen setzten `rec.path` ungeprüft auf die Platte um. Ein gefälschter Eintrag
(`path="x/../Buchhaltung"` oder ein absoluter Pfad) konnte deshalb den Ordner löschen (`unlink`), per anonymem Freigabe-Link jede lesbare Datei des
Servers ausliefern (`share_token` ist ebenfalls frei beschreibbar), über `ocr_state=pending` Text beliebiger Dateien in `content_text` ablegen,
über `pending_content` jede Datei überschreiben oder per `action_restore` verschieben. Behoben an der Wurzel und zusätzlich an jeder Senke:

- **Feldrechte (Erlaubnisliste):** schreibbar durch Nutzer sind nur `name` (über den Umbenennen-Weg), `tag_ids`, `status_id`, `partner_id` und
  `shared_partner_ids` (`USER_WRITABLE_FIELDS`). Jedes andere Feld des Moduls ist nur mit `env.su` schreibbar (`_has_field_access`; ein neues Feld
  ist damit von Anfang an gesperrt; `fields_get` meldet sie `readonly`). Die Nutzer-ACL hat kein `create` mehr; Index-Zeilen legt nur der Server an.
  Mehrere Zeilen mit `name` auf einmal zu schreiben ist abgelehnt (es würde nur das Etikett ändern und die Rechteprüfung des Umbenennens überspringen).
- **Löschen:** Nutzer dürfen per ORM nur Papierkorb-Einträge löschen, deren Pfad wirklich unterhalb von `.trash/` liegt (`@api.ondelete`,
  `index_utils.trash_disk_path`: `resolve_path`, kein `..`, kein Link nach draußen). Die Bytes werden erst nach dem Löschen der Zeilen entfernt (vorher
  geschah das vor der Rechteprüfung) und nur, wenn der Pfad unter `.trash/` liegt; sonst bleiben sie stehen und der Fehler wird geloggt.
- **Wiederherstellen:** `action_restore` prüft das Schreibrecht, dass der Eintrag eine Papierkorb-Wurzel ist und das Schreibrecht auf den
  ursprünglichen Ordner (der Schutz kann sich seit dem Löschen geändert haben); `index_restore_tree` verschiebt nur noch aus `.trash/`. Dann erst
  `sudo()`.
- **Freigabe-Link:** `action_generate_share_token`/`action_revoke_share_token` prüfen das Schreibrecht, schreiben danach per `sudo()`.
- **N1:** `action_analyze_document` und `action_apply_extracted_values` heißen jetzt `_analyze_document` und `_apply_extracted_values` (per RPC nicht
  mehr erreichbar); die Routen prüfen wie bisher `authz.require(…, "write")`. Die Eingabe des Prüf-Dialogs wird geprüft (Typen, Länge, Zahl,
  vorhandenes Muster) und endet bei Fehlern als `UserError` statt als 500; ungültige Eingabe lässt die vorhandenen Werte unberührt.
- **Senken:** jede Stelle, die einen Index-Pfad auf die Platte abbildet, geht über `_absolute_path()` (`resolve_path`): anonymer Freigabe-Download,
  Portal-Download, Veröffentlichen (`stage_overwrite`, Phase A: `share_state='conflict'`), Schreibdienst (`snapshot_and_write`, also auch ONLYOFFICE-Sync
  und Versions-Wiederherstellung) und die drei Crons für Hash, Metadaten und Text (Zeile geht auf `error`, der Lauf geht weiter).
- **Tests:** `tests/test_index_rights.py` (39 Tests): jeder Angriff oben je Senke, Schreibversuch auf jedes Serverfeld einzeln, Prüfung, dass `fields_get`
  alle als `readonly` meldet, die Liste der öffentlichen Methoden des Modells (eine neue öffentliche Methode fällt dort auf), HTTP-Tests für Freigabe-Link,
  Portal und beide Routen. Gegen den Stand vor dem Fix sind 17 der 39 Tests rot (mit 117 fehlgeschlagenen Teilfällen), der Rest sind Gegenproben, dass
  der erlaubte Weg weiter funktioniert. Lauf auf HM-SRV in Wegwerf-DB (`fmtest_pg`, Image `int-filemanager-odoo:19.0-ocr`): 609 Tests, 0 Fehler.
- **Offen dazu:** `race.sh`, Tower, `test_lint`, odoo-ls und pre-commit sind nach dieser Änderung nicht gelaufen. Die geänderten Altdateien bleiben im
  LEGACY-Block (nur die geänderten Zeilen folgen den Regeln, nichts umformatiert). Nach dem Einspielen auf HM-SRV: `-u int_filemanager` (die ACL
  ändert sich).

**Noch offen (Altcode, durch Lesen belegt, nicht ausgeführt):**

- **Nicht indexierte Pfade sind ungeschützt:** `authz.require` lässt einen Pfad ohne Index-Eintrag durch. Auf CIFS-Freigaben ohne Watcher-Ereignis wird
  eine Datei bis zum nächsten Vollscan nicht indexiert und ist in einem Schutzordner für jeden Nutzer erreichbar.
- **Vollscan löscht den Papierkorb:** `_scan_and_reconcile` sucht die verwaisten Zeilen ohne `trashed`-Filter (`scan_run_id != Lauf`), `.trash/` wird
  beim Gehen übersprungen; alle Papierkorb-Einträge gelten als verwaist und werden samt Bytes entfernt. Per Testlauf bestätigt (Datei in den Papierkorb,
  dann `_scan_and_reconcile`: Zeile und Bytes weg), vor wie nach dem Fix oben; nur die Zeile `.trash` selbst bleibt samt Ordner stehen.
- `int_filemanager.share_log` ist für alle Nutzer lesbar, ohne Rule; Pfade und Namen von Dateien, die der Nutzer nicht sehen darf, werden sichtbar
  (das Modell nutzt auch der Branch).
- Die Route `/int_filemanager/upload` hat `csrf=False`; der WebDAV-Weg (`_put`) schreibt ohne Größengrenze; der Token-Speicher in `webdav_tokens.py` liegt
  im Prozessspeicher und bricht bei Prefork-Betrieb.
- `share_download` und `zip_extract_entry` lesen ganze Dateien in den Speicher (Grundregel I12).

### 3.2 Rechtemodell des Branches: direkte ORM-Zugriffe (behoben 2026-10-02, noch nicht committet)

Verletzte die Grundregel I7: über `/json/2` und `call_kw` waren die Modelle mit allen Feldern schreibbar, die Prüfungen standen nur in den
Hilfsmethoden. Behoben und mit `tests/test_v2_orm_rights.py` abgesichert (14 Tests, vorher 11 rot; ganze Modul-Suite 570 Tests grün auf HM-SRV):

- **Knoten:** `scope_id`, `parent_id`, `current_revision_id`, `size`, `mime`, `review_state`, `active`, `removal_reason` und `trashed_at` sind nur noch mit
  `env.su` schreibbar (`_has_field_access` am Modell, `SERVER_ONLY_FIELDS`; `fields_get` meldet sie als `readonly`). Nutzer legen Knoten, Revisionen und
  Uploads nicht mehr selbst an (ACL ohne `create` bzw. `write`); die Methoden prüfen das Recht und schreiben dann per `sudo()`. `trash`, `restore` und
  `delete_permanently` prüfen den ganzen Teilbaum, bevor sie per `sudo()` schreiben.
- **Upload:** Nutzer haben nur Leserecht auf ihre eigenen Uploads; `temp_file` setzt allein der Server. Beim Abschluss eines Uploads für eine neue Datei wird
  das Schreibrecht auf den Zielordner erneut geprüft.
- **Scope:** Anlegen nur noch für `group_filemanager_admin`; die Nutzer-ACL hat kein `create` und kein `unlink` mehr.
- **Verschieben:** nur Nachfahren mit dem Scope des Knotens wechseln mit; ein Unterordner mit eigenem Scope behält ihn (der Nutzer sieht ihn eventuell
  nicht). Die abhängigen gespeicherten Felder (`is_scope_root`) werden über `modified()` neu berechnet.
- **Offen:** die Rennszenarien (`tests/tower/race.sh`) und der Lauf auf Tower sind nach dieser Änderung nicht gelaufen; `test_lint`, odoo-ls und
  pre-commit ebenfalls nicht.

### 3.3 Fehler und Leistung im neuen Code

- **Umbenennen-Knopf fehlt auf Deutsch:** `static/src/int_filemanager/v2/upload_panel.js` (`canRename`) prüft den Fehlertext mit `/exists/`; die deutsche
  Übersetzung ("existiert hier bereits") passt nicht. Der Knopf erscheint für deutsche Nutzer nie. Korrektur: am Fehlertyp erkennen, nicht am Text.
- **Follower-Zeile je Knoten:** beim Anlegen ist nur `mail_create_nolog` gesetzt, nicht `mail_create_nosubscribe` (`create_file`, `create_folder`,
  `copy_node`, `_copy_children`, `_finish_now`); Odoo legt dadurch je Knoten eine Zeile in `mail_followers` an (bei der Übernahme von 1,8 TB Hunderttausende).
- **Textdatei-Editor ohne Größenlimit:** `controller_mutations.js` (`onEditText`) lädt jede `.txt`/`.log`/`.csv`/`.json`/`.md` vollständig in den Browser.
- **Eingabeprüfung der öffentlichen Methoden:** am Knoten behoben (3.6); `upload_chunk` und `create_link` nehmen noch beliebige Typen, schlechte Eingabe
  endet dort als 500 statt als `UserError`. Nicht ausnutzbar, aber unsauber. Die Prüfhelfer stehen in `params.py`.
- **Rechenaufwand beim Öffnen des Formulars:** `_learn_labels` sucht je Feld (nur beim Speichern, für einzelne Dokumente unkritisch).
- **Crons:** der Rückgabewert von `_commit_progress` (Restzeit) wird in `_cron_finish_pending`, `_cron_build_zips` und `_cron_run` ignoriert; die Regel
  verlangt, bei 0 sofort zurückzukehren (`_cron_purge_trash` am Knoten ist umgestellt, 3.6).
- Die Prüf-Client-Aktion `value_review` ist noch geladen und im Menü, obwohl entschieden war, sie zu entfernen (Schritt 2 oben); das Modul hat zwei
  Wurzelmenüs ("Dateimanager" und "Files").
- `tests/tower/bootstrap_fixtures.py` enthält ein festes Testpasswort (`race_driver_pw_1`) und liegt im Modulordner; beides nur für die Testinstanz gedacht.

### 3.4 Abweichungen von den Odoo-19-Regeln und Hausregeln (neuer Code)

Nach den Regeldateien in `docs/odoo_regeln/` geordnet; Stand der Prüfung per Lesen, kein Werkzeuglauf.

- **Python/ORM:**
  - Roh-SQL ohne `odoo.tools.SQL`: f-String in `models/int_filemanager_derivative.py` (`_enqueue_missing`, mit `# noqa: S608`) und gut 10 weitere
    `cr.execute("...", [...])` in `int_filemanager_blob.py`, `_derivative.py` und `_upload.py` (Hausregel: `SQL()`); `_node.py` ist umgestellt.
  - `except Exception` ohne konkreten Typ an zwei Stellen: `int_filemanager_upload.py` (`_finish_pending_one`), `int_filemanager_zip_job.py` (`_build_one`).
  - `_remove_if_exists` steht dreimal (`_node`, `_upload`, `_zip_job`), obwohl `blobstore.remove_if_exists` existiert.
  - Zwei lesende öffentliche Methoden ohne `@api.readonly`: `upload_status`, `zip_job_status` (Entscheidungen, Abschnitt 8); am Knoten ist es gesetzt.
  - Docstrings: außerhalb von `_node.py` und `_value_recognition.py` haben noch Dateien mehr als fünf Zeilen (Hausregel: wenige Zeilen) und öffentliche
    Funktionen keinen.
  - In `value_suggest.py` überschreibt `Page.in_area` die Parameter `start` und `end`; Kommentare mit Fundgeschichte ("test collection").
- **Sprache und Verweise (Hausregel 8):**
  - `__init__.py`: deutscher Docstring, "Phase 5", Verweis auf das gelöschte `docs/int_filemanager_ausbau.md`.
  - `views/int_filemanager_node_views.xml`: Kommentar mit "Schritt 4b" und veraltetem Dateinamen (`int_filemanager_v2_search_model.js`, richtig `v2/search_model.js`).
  - `data/int_filemanager_upload_cron.xml`: Verweis "N6".
  - `views/portal_templates.xml`: hartcodierte deutsche Texte, `t-esc` statt `t-out`, deutsche Kommentare.
  - `systray/` (Audio-Player, wird von v2 genutzt) und `shared/` haben deutsche Quelltexte in Templates und `_t`; sie fehlen in `i18n/de.po`.
  - `README.rst` verweist auf Dokumente (erlaubt, aber nach Schritt 8 prüfen).
- **Manifest und Daten:**
  - `installable: True` ist der Standardwert.
  - `external_dependencies` fehlt für `pdfplumber`, `ocrmypdf` und `mutagen` (Altcode, aber das Manifest ist umgeschrieben).
  - Die Hooks (`pre_init_hook`, `post_init_hook`, `post_load`) stehen in `__init__.py` und `pg_extensions.py` statt in `hooks.py`.
  - `<field name="active">True</field>` in den Cron-Records und `<field name="context">{}</field>` in `action_int_filemanager_node` sind Standardwerte.
- **Views/XML:**
  - IDs: `action_int_filemanager_node` statt `int_filemanager_node_action`; Views ohne `_view_` im Namen; Menü `menu_int_filemanager_v2_root`.
  - Redundantes `string=` an `name` und `size` in `int_filemanager_node_views.xml`.
  - `position="replace"` in `v2/list_view.xml` und `v2/kanban_view.xml` ohne Begründungskommentar an der Stelle.
- **Benennung "v2":** Beschreibungen der Modelle außer dem Knoten ("Filemanager v2 ..."), Routen `/int_filemanager/v2/...`, Registry-Schlüssel `int_filemanager_v2_*`,
  Dateiname `controllers/int_filemanager_v2.py` (Regel: `controllers/<modul>.py`). Der Freigabe-Link `/int_filemanager/v2/share/<token>` geht an Kunden;
  eine spätere Umbenennung bricht diese Links, deshalb **vor Schritt 8 entscheiden**.
- **JavaScript/Owl:**
  - `fetch` (`controller_mutations.js`, `uploads_service.js`), `window.open` (`controller_mutations.js`), `setTimeout` und `document.addEventListener`
    (`list_renderer.js`, `controller_previews.js`, `viewer_overlay.js`, `uploads_service.js`) statt `browser.*` / `useExternalListener`.
  - `/** @odoo-module **/` ist unter `static/src` überflüssig.
  - `window`-weiter `dragover`-Listener mit `preventDefault()` auch für fremde Drags (`controller_uploads.js`).
  - `viewer_overlay.js` hängt an Interna von pdf.js (`PDFViewerApplication`), bei einem Odoo-Update zu prüfen.
- **Tests:**
  - Keine Hoot-Tests und keine Tours; die `.mjs`-Tests laufen nur mit `node --test`, nicht in Odoos Testlauf.
  - `test_fulltext_word_index.py` hat kein `@tagged`.
  - Skripte für Tower liegen im Modulordner (`tests/tower`), werden mit dem Modul ausgeliefert.
- **i18n:** `i18n/de.po` Eintrag "A name must not contain / \ : ...": im `msgstr` steht ein einzelner Backslash statt `\\`. In den v2-JS-Dateien fehlen
  "Delete" (kommt aus dem Odoo-Kern) und "Bytes" in `de.po`.
- **SCSS:** neun Zeilen über 80 Zeichen in `v2/previews.scss`, `v2/upload_panel.scss`, `v2/properties/preview_field.scss` und
  `v2/value_review/value_review_action.scss`; letztere nutzt `var(--bs-primary-rgb)`, obwohl die Entscheidungen festhalten, dass Odoo 19 Community keine
  `--bs-*`-Farbvariablen zur Laufzeit hat; `.o_int_filemanager_move_tree` steht in `upload_panel.scss`.
- **Prüfautomatik:** `pre_commit`, pylint-odoo, `test_lint` und odoo-ls sind für den Stand dieser Review nicht gelaufen.

### 3.5 Altcode: Abweichungen, die bis Schritt 8 stehen bleiben

Nach der Regel "bestehenden Code nicht umformatieren" nicht angefasst; bekannt aus `pruefautomatik_2026-10-02.md` und ergänzt.

- Fehlertexte ohne `_()`, `odoo.orm`-Import in `acl_rules.py`, Prop in `link_record_dialog.xml` nicht übersetzbar, `application: False` in den
  Manifesten der anderen Module (`test_lint`).
- Deutsche Namen, Docstrings, Kommentare und Oberflächentexte im ganzen Altcode; Kommentare mit Verweisen auf gelöschte Dokumente und auf Memory-Notizen
  (`views/filemanager_file_search.xml`).
- `cr.commit()` mitten im Scan (`_scan_and_reconcile`) und im Watcher statt `_commit_progress`; `search_count([])`.
- Alt-Crons in `data/ir_cron.xml`, Status und Erkennungsmuster ohne `noupdate`: ein Modul-Update aktiviert abgeschaltete Crons wieder und überschreibt
  geänderte Status-Namen und Muster.
- `index_utils._upsert_by_path` baut das SQL mit `.format`; `fulltext.py`, `mediameta.py` und `watcher.py` verarbeiten fremde Dateien im Odoo-Prozess
  (Grundregeln I11 und I13) und starten in `post_load` einen Watcher, der der Grundregel "nur Odoo schreibt" (I1/I5) widerspricht.
- Doppelte Fehlerinjektion (`publish_service.fault_point` und `fault.py`), doppelte Dialoge und Größenformatierung (`shared/`, `native_ui/` und `v2/`).
- `native_ui/native_search_model.js`: rekursive Suche mit `=like` ohne Maskierung von `_` und `%` im Ordnernamen (findet Dateien von Nachbarordnern).
- `int_filemanager.linkable.mixin`: `search_count` je Datensatz in der Liste (N+1).

### 3.6 Prüfung und Umbau von `int_filemanager_node.py` (2026-10-02)

Die größte Python-Datei (1930 Zeilen) wurde gegen die Regeldateien gelesen und dann umgebaut. Was der Odoo-Kern im Test-Image sagt, wurde dort nachgesehen:

- **Aufteilung:** die Werterkennung (42 % der Datei) steht jetzt in `models/int_filemanager_value_recognition.py` (abstraktes Modell
  `int_filemanager.value_recognition`, vom Knoten geerbt; die RPC-Aufrufe am Knoten bleiben gleich). `params.py` prüft die Argumente der öffentlichen Methoden
  (`require_id`, `optional_id`, `require_ids`, `require_text`, `require_choice`). Der Knoten folgt der Reihenfolge der Regeln (Felder, Index, Compute/Suche,
  CRUD, Actions, Geschäftsmethoden); die längsten Methoden sind von 103 auf unter 65 Zeilen geteilt.
- **Eingaben:** jede öffentliche Methode am Knoten prüft ihre Argumente und antwortet mit `UserError` statt 500. Im Kern belegt: `check_access` auf einem leeren
  Recordset prüft nur das Modell, ein leerer Elternordner (`None`) wurde also nicht abgewiesen. Der Vorgangsschlüssel muss ein Text von höchstens 200 Zeichen
  sein, `create_new_revision` nimmt vom Client nur die Herkunft `upload` oder `edit`, Inhalt muss Bytes oder gültiges Base64 sein.
- **Cron:** `_cron_purge_trash` meldet den Fortschritt (`_commit_progress`), committet je Teilbaum und hört bei abgelaufener Zeit auf; die abgelaufenen Wurzeln
  werden in der Datenbank mit Limit gesucht, nicht mehr alle geladen und dann abgeschnitten. Fehler eines Teilbaums werden mit konkreten Typen gefangen.
- **SQL:** `execute_query(SQL(..., to_flush=...))` statt `cr.execute` plus `flush_model()`; die Namenssuche des Absenders mit `IN (SELECT unnest(...))`. Gemessen
  auf Tower mit 20 000 Firmen und 18 000 Wortgruppen: 19,3 s mit `= ANY(Array)`, 54 ms mit dem Hash-Join. `_touch_active_parent` invalidiert `write_date`.
- **Sperre:** `FOR NO KEY UPDATE` statt `FOR UPDATE`. Der Kern nimmt es mit `allow_referencing=True` für Zeilen, auf die andere zeigen und deren Kennung sich nicht
  ändert; `lock_for_update()` selbst wartet nicht (SKIP LOCKED, `LockError`), deshalb bleibt der eigene wartende Weg (`_lock_node`). Alle 16 Rennszenarien grün.
- **`@api.readonly`:** gesetzt an `tree_children`, `breadcrumb`, `existing_names`, `suggest_field_values`, `page_words`, `read_selection`. Im Kern: JSON-2 und
  `call_kw` lesen die Markierung; ein schreibgeschützter Cursor wird nur mit Lese-Replikat benutzt, bei einem Schreibversuch wird mit einem Schreib-Cursor
  wiederholt. Geprüft in einer Transaktion `READ ONLY` auf Tower: alle sechs laufen durch, ein Schreibversuch wird blockiert.
- **Kopieren:** je Baumebene ein `create` für die Knoten und ein `create` für alle Fassungen statt eines je Knoten; die Fassungen einer Kopie haben die
  Herkunft `copy` (vorher `restore`).
- **Compute-Felder:** `@api.depends` an `preview_state`, `values_json`, `is_visible_top` und `content`. `values_json` hängt bewusst nur an `is_dir` und der
  Fassung, nicht am Kontakt: das Formular hält die noch nicht gespeicherten Eingaben in diesem Feld. Die Kenndaten (Währungen, eigene Firmen) werden einmal
  je Aufruf gelesen, und für Knoten, die das Prefetch mitberechnet und die der Nutzer nicht lesen darf, wird nichts berechnet.
- **Kommentare:** `sudo()` begründet, Docstrings im Imperativ, höchstens sechs Zeilen; "v2" aus der Modellbeschreibung entfernt (`de.po` neu gebaut).
- **Berichtigung der Review:** `string="Tags"` an `tag_ids` ist kein Verstoß (ohne `string` hieße das Feld "Tag", `orm/fields.py`), es bleibt.
- **Tests:** `tests/test_v2_node_arguments.py` (22 Tests): falsche Argumente für alle Methoden, Herkunft, Markierung `_readonly`, Kopieren in wenigen
  Aufrufen, Fortschritt und Abbruch des Crons, ein Teilbaum, der nicht gelöscht werden kann, `values_json` für unlesbare Nachbarn.
- **Offen:** `upload_chunk`, `create_link` und die übrigen Modelle prüfen ihre Argumente noch nicht mit `params.py`; `_remove_if_exists` steht noch in `_upload` und
  `_zip_job`.

## 4. Arbeitsweise des Nutzers

- **Commit erst auf Ansage.** Test-Instanz ohne Rückfrage aktualisieren: `bash tools/v2check/ui_instance.sh` (aktualisiert mit `--i18n-overwrite`).
- Odoo-Code gründlich auf native Bausteine prüfen; Ursachen im Code mit Test beheben, keine Handeingriffe in DB/Container.
- Oberfläche testet der Nutzer frei im Browser; keine Checkliste, keine Browser-Automatik. Nur kurze Tests (gezielte Klassen, Node-JS-Tests, `jscheck`);
  volle Suite/`v2check` nur bei Server-Änderungen oder am Ende.
- Abdeckung offenlegen (vollständig vs. Stichprobe), Alternativen zeigen, Fragen einzeln durchgehen, Produktentscheidungen beim Nutzer lassen.
- Dokumentation: kein Konzeptdokument je Feature. Vor einem größeren Feature eine halbe Seite (Ziel, offene Fragen), nach der Umsetzung das Ergebnis in
  die Entscheidungen und die Notiz löschen.

## 5. Testumgebung (Tower 192.168.188.67, `ssh unraid`)

- Es gibt drei getrennte Unraid-Server (HM-SRV, Tower, Tower 192.168.178.73, siehe `README.md`). "Tower" ohne Zusatz ist 192.168.188.67; die hier beschriebene Testumgebung liegt dort.

- Test-Instanz der Oberfläche: `http://192.168.188.67:8085`, Login-Datei `/mnt/user/appdata/fmtest/v2ui/LOGIN.txt` auf Tower (der Nutzer tippt das
  Passwort selbst). Testdateien: Henrich-Rechnung (Knoten 2) und "Bescheid A/B/C" (selbst erzeugt, ungefährlich).
- Test-Image `odoo:19.0-hm-test` (19.0-20260908); das Live-Tag `odoo:19.0-hm` ist unberührt. Test-PostgreSQL `fmtest_pg`.
- Prüfwerkzeuge: `tools/v2check/v2check.sh [--quick]` (odoo-ls + `test_lint`, filtert auf neue/geänderte Dateien), `race.sh` (Rennszenarien in
  Wegwerf-Umgebung), `tests.sh`, `jscheck.sh`, `owlcheck.sh`, `i18n_export.sh`. pre-commit: `py -3.13 -m pre_commit` (Programme unter `%APPDATA%\Python\Python313\Scripts`).
- Blob-Speicher der Tests: Share `fmv2blobs` (nur disk3, kein Cache, keine SMB-Freigabe, ca. 53 GB).
- **Private Testsammlung** (nie ins Repo, nie in Berichte mit Werten): `/mnt/user/test/werterkennung/` (528 Dateien, 513 PDFs), abgeleitete Wortlisten
  `/mnt/user/test/werterkennung_words_v3/`, Messdaten und Bewertungen `/mnt/user/test/werterkennung_w6/` (`chmod 700`). Messwerkzeuge
  (`w6_sample.py`, `w6_recheck.py` für den Regressionstest nach jeder Regeländerung, `keyword_search.py` u. a.) nur noch im Git-Tag `docs-vor-aufraeumen-2026-10-02`, Pfad `docs/prototypes/werterkennung/` (mit README). Formate-Testsammlung: `/mnt/user/test/formats` (95 Dateien, `tools/fmconverter/run_formats.py`).
- Prototyp-Container `fmv2_*`, `fmtest_*`, `fmreal_odoo` auf Tower sind WebDAV-/Prototyp-Reste: **vor dem Löschen den Nutzer fragen**.
- **HM-SRV** ist von hier nicht erreichbar; vor jedem Odoo-Image-Update DB-Kollation prüfen (siehe Entscheidungen 2).

## 6. Stolpersteine

- Neue Wörter-Spec nur mit Eintrag in `server.py` `WORDS_SPECS`, sonst 400 vom Umwandler.
- gs-Test-PDFs brauchen ≥ 20 sichtbare Zeichen, sonst liest der Umwandler per OCR.
- pdfminer nimmt für Standardschriften (Helvetica …) die Maße aus seinen Tabellen, nicht aus dem Beschreiber.
- pdf.js entfernt fremde Kinder einer Seite beim Neuzeichnen (MutationObserver in `viewer_overlay.js`).
- Bash-Heredocs mit `'''` oder `\n` in Python-Strings brechen: Dateien mit dem Schreibwerkzeug ändern.
- `pre-commit` prüft nur gestagte Dateien; der Hook formatiert JS/XML/Python um (danach neu stagen).
- Startkatalog ist `noupdate`: bestehende Datenbanken bekommen neue Stichwörter/Felder nicht von selbst.
- Wer `odoo shell`/`odoo -u` gegen die Watcher-DB startet, startet einen zweiten Watcher (Entscheidungen 8).

## 7. Aufbau im Überblick

```text
 Browser (Odoo-Oberfläche, ONLYOFFICE)          Scanner / Handy / Kopien
        │                                              │
        ▼                                              ▼
 nginx (HTTPS, liefert Dateien direkt aus)      Eingangsordner (Samba, nur hineinlegen)
        │                                              │ Odoo holt ab
        ▼                                              ▼
 Odoo (Prefork) ── PostgreSQL ── Blob-Speicher (nur Odoo schreibt)
        │
        └── Umwandler-Container (Vorschaubilder, Texterkennung, Metadaten)
```

- **Ziel:** die Dateien vom Share `Daten` (Tower, ca. 1,8 TB) kommen in den neuen Dateimanager in Odoo; danach schreibt nur noch Odoo.
- **Bausteine im Datenmodell:** Knoten (`int_filemanager.node`: Ordner oder Datei, Name je Ordner ohne Groß/Klein eindeutig, auch eine leere Datei hat eine
  Fassung; die Werterkennung erbt er von `int_filemanager.value_recognition`), Fassung (`.revision`, wird nie verändert), Inhalt (`.blob`, Datei im Speicher mit Prüfsumme), abgeleitete Daten (`.derivative`: Vorschau, Text,
  Metadaten, nur über eine eigene Route mit den Rechten der Fassung ausgeliefert), Rechte-Bereich (`.scope`: wer lesen, schreiben, verwalten, endgültig löschen darf).
- **Schreiben** läuft immer gleich: Rechte und Vorgangsnummer prüfen → neuer Inhalt als Datenstrom in den Speicher (Prüfsumme dabei, Zwischendatei bleibt bis zum
  Abschluss, unbenutzte räumt der Aufräumjob) → kurze Datenbank-Transaktion mit Prüfung, ob inzwischen jemand anderes geändert hat → erst danach Wirkungen nach außen.
  Umbenennen, Verschieben und Kopieren ändern nur die Datenbank. Treffen zwei Vorgänge aufeinander, wartet der zweite kurz oder wird wiederholt; Odoo erledigt das
  nicht von selbst, der Code regelt es ausdrücklich.
- **Rechte** zum Start minimal (Bereich "Alle" und der heutige Schutzordner) und für alle Wege gleich (Liste, Suche, Vorschau, Download, Freigabe-Links).
- **Betrieb:** Odoo im Prefork-Modus, nginx davor, Umwandler-Container, Aufräumjobs für unbenutzte Inhalte, abgebrochene Uploads und Temp-Dateien. Überwachen:
  Upload-Reste, fehlerhafte Vorschauen, Prüfsummenfehler, freier Platz. Schlafende Platten brauchen beim ersten Zugriff einige Sekunden.

## 8. Übernahme des Bestands (Plan für Schritt 8)

Der Bestand wird **kopiert**, nicht verschoben:
1. Erstkopie im laufenden Betrieb (wiederholbar, fortsetzbar): ca. 18 Stunden für 1,8 TB (gemessen 27,5 MB/s). Etwa 7 % sind Dubletten und werden nur einmal
   gespeichert; Platzbedarf ca. 1,7 TB, frei sind ca. 3,7 TB.
2. Tags, Status, Kontakte, Texterkennung, Freigaben und alte Versionen aus dem Stand von `master` übernehmen.
3. Änderungen seit der Erstkopie nachziehen.
4. Share schreibgeschützt, letzter Abgleich, umschalten.
5. Prüfen: Anzahl und Prüfsumme jeder Datei gegen die Quelle.
6. Bis zur Abnahme bleibt der alte Stand schreibgeschützt erhalten (**Rückweg möglich**).
