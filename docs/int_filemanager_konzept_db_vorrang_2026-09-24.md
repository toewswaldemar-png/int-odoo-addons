# int_filemanager: Konzept "Datenbank hat Vorrang" — App-Änderungen, externe Änderungen, Watcher

Stand 2026-09-24. **Reines Konzept, nichts umgesetzt.** **Entscheidung des Nutzers (2026-09-24):
Variante B — DB als Wahrheit, lesbare Ordner auf dem Share, Odoo schreibt, minimaler Watcher.
`ir.attachment`/Filestore (Variante A) bleibt spätere Option pro Bereich; Versionen liegen schon dort.** Bündelt das Ergebnis der Prüfrunden vom
2026-09-24 (Code-Durchsicht, Live-Prüfung auf HM-SRV, Odoo-19-Core im Container, externes Review
`ODOO_DB_WAHRHEIT_PRUEFUNG_2026-09-24.md`) in einem Dokument. Prüfgrundlage: Repo `int-odoo-addons`
HEAD `432a95f`, Live-Instanz HM-SRV (192.100.0.119), Container `Odoo19` / `odoo_db`.

**Nachtrag 2026-09-25:** Die offenen und ungeprüften Punkte wurden auf dem zweiten Unraid-Server (lokal,
"Tower") in einer isolierten Testumgebung live geprüft, mit einer lesend erstellten Kopie der Tower-Live-DB und
echten SMB-Zugriffen von Windows (Abschnitt 19). Die betroffenen Stellen sind unten mit "→ 19" markiert. Eine
zweite Runde am selben Tag (Abschnitt 20) hat die Code-Befunde B2–B15 live ausgelöst, die Pflichttests gegen den
Durchstich 1.15.0 ausgeführt und `trashed` → `active` sowie einen `watchdog`-Watcher als Prototyp erprobt.

Löst in Teilen die Docs vom 2026-09-23/24 ab (siehe Abschnitt 9) — sie bleiben als Recherchebasis
stehen, ihre Schlussfolgerungen gelten nur noch, soweit sie hier nicht korrigiert werden.

---

## 1. Leitprinzipien (vom Nutzer vorgegeben)

1. **Die Datenbank hat oberste Priorität.** Was die DB als gültig führt, gilt. Die Platte (Share)
   folgt nach.
2. **Extern ordnet sich unter.** Änderungen aus dem Explorer sind Eingaben, über die die DB nach
   Regeln entscheidet (annehmen oder zurücksetzen). Ehrlich begrenzt: Odoo kann einen Schreibvorgang
   im Explorer nicht *verhindern*, nur nachträglich angleichen (Abschnitt 6).
3. **So weit wie möglich mit Odoo-Bordmitteln**, nicht an Odoos Transaktions- und Datenbankverwaltung
   vorbei (keine eigenen DB-Verbindungen, kein rohes SQL, keine Advisory-Locks).
4. **Änderungen über die App sind absolut stabil**, unabhängig vom Watcher.
5. **Der Watcher ist nur Zulieferer**, kein Entscheider (Abschnitt 5).
6. Die drei CIFS-Freigaben sind **Testfreigaben**; Produktivbetrieb ist der lokale Share.
7. **Nativ vor Bestand, Ursache statt Symptom (Umbau-Regel, Vorgabe des Nutzers 2026-09-24):** Wo Odoo einen
   Baustein mitbringt, ersetzt er den Eigenbau **vollständig** (der Eigenbau wird gelöscht, nicht daneben
   betrieben). Symptome werden nicht am Eigenbau korrigiert, wenn der native Baustein die Ursache beseitigt.
   Vor jedem "kein Bordmittel" gilt das Suchraster aus 16.4. Bilder/Vorschau: Abschnitt 17.

---

## 2. Verifizierter Ist-Stand

### 2.1 Live (HM-SRV, read-only geprüft am 2026-09-24)

| Punkt | Befund |
|---|---|
| Index | ~1,39 Mio. Zeilen, Dateien zusammen **1,3 TB**; DB 3,8 GB; Versionen: 54 Stück, 32 MB |
| Verteilung | 99,96 % der Zeilen auf den drei CIFS-Freigaben (Daten, Produktiv-HM-Datenbank, Transfer). Lokaler Share `HM-Daten` enthält nur `Test` (20 Ordner, 591 Dateien) |
| `_shallow_reconcile()` | **Existiert nicht** (kein Cron live, ID 53 fehlt; in keinem Git-Commit). Die Docs vom 09-23 nennen ihn fälschlich "produktiv" |
| Vollscan-Cron | täglich 03:00, Lauf 03:00:32–03:27:26 (~27 min), entfernte 21 verwaiste Einträge |
| Watcher | läuft, 69.195 inotify-Watches (fast alle auf CIFS), keine Fehler im Log seit Containerstart |
| Limits | `max_user_watches` 524.288 (13 % genutzt), `max_queued_events` 16.384, Instanzen 1/128 |
| Betriebsmodus | ein Prozess (`/usr/bin/odoo`), Threaded, effektiv `workers=0` (nicht als Architekturvoraussetzung verwenden) |
| Papierkorb | 0 `trashed`-Zeilen, kein `.trash` auf der Platte (unklar, ob nie genutzt oder bereits gelöscht, siehe B1) |
| Mounts | alle `rprivate` (Notizen nannten `rslave` als Fix — Diskrepanz nicht untersucht) |

### 2.2 Befunde im Code (aus dem Code abgeleitet, **nicht** live ausgelöst, sofern nicht anders vermerkt)

| # | Schwere | Befund | Stelle |
|---|---|---|---|
| B1 | **kritisch** | Der Vollscan überspringt `.trash`, sucht Stale-Zeilen aber ohne Filter auf `trashed`; `remaining_stale.unlink()` ruft das `unlink()`-Override, das die Bytes aus `.trash` löscht. Ein in den Papierkorb verschobener Eintrag wäre beim nächsten 03:00-Scan **endgültig weg** (statt nach 30 Tagen). | `models/filemanager_file.py:829, 885, 1065, 401-407` |
| B2 | hoch | Datei wird **vor** dem Commit geändert; Odoos `retrying()` führt den Controller bei `40001`/Deadlock bis zu 5× neu aus → Wiederholung findet z. B. die Datei schon im Papierkorb ("Eintrag nicht gefunden"), Index zeigt alten Pfad. | `controllers/main.py:224-227, 262-264, 284-286` |
| B3 | hoch | `suppress_watcher()` endet vor dem Commit, ohne Referenzzählung, nur exakte Pfade, weg bei Absturz. | `path_utils.py:33-57` |
| B4 | hoch | ONLYOFFICE-Save, Upload-Überschreiben, Version-Restore und WebDAV-PUT pflegen den Index **nicht selbst**; sie hängen am Watcher (Größe, mtime, `hash_state` bleiben sonst bis 03:00 veraltet). | `write_service.py:13`, `ir_attachment.py:85`, `webdav.py:158-167` |
| B5 | hoch | WebDAV-PUT (= "Lokal öffnen" für Word/Excel) schreibt mit `open("wb")` direkt: keine Version, kein Lock, kein Journal, ETag nur aus ganzzahliger mtime, PUT ohne Lock-Token-/Revisionsprüfung. (Ein Verbindungsabbruch *beim Empfang* schadet nicht, der Body wird vorher komplett gelesen; Prozess-/Plattenfehler beim Schreiben schon.) | `controllers/webdav.py:158`, `webdav_tokens.py` |
| B6 | mittel | `write_text` und Upload-Neuanlage schreiben nicht atomar; Upload überschreibt eine auf der Platte vorhandene, aber nicht indexierte Datei ohne Version. | `controllers/main.py:298, 321-340` |
| B7 | hoch | Editorsitzungen sind pfadgebunden (ONLYOFFICE `int_filemanager_path`, WebDAV-Token = relativer Pfad); nach Umbenennen kann ein Save die alte Datei neu anlegen. | `models/ir_attachment.py:60-73` |
| B8 | mittel | Bestehende Sperre (`pg_advisory_lock` auf `file_id`) liest den Pfad vor dem Lock und wird von Rename/Move/Watcher/WebDAV nicht genutzt. | `write_service.py:60, 106` |
| B9 | mittel | Journal ist Diagnose, kein wiederanlaufbarer Auftrag; 30-min-Timeout kann einen langsamen, noch laufenden Vorgang erfassen. | `models/filemanager_write_journal.py:46` |
| B10 | mittel | `_upsert_by_path` (rohes `INSERT … ON CONFLICT`) beseitigt `40001` unter `REPEATABLE READ` **nicht** — im Test bestätigt (Docstring stimmt nicht). Der Watcher wiederholt nicht → Ereignis geht verloren. | `index_utils.py:111-161`, `watcher.py:38-56` |
| B11 | mittel | Watcher: `inotify.read()`/`add_watch()` ungesichert (kein Restart), `Q_OVERFLOW` ignoriert, kein Nachholscan beim Start, Move-Cookies nur je Batch (sonst Löschen + Neuanlage → Kaskade auf Versionen), Watches von nach `.trash` verschobenen Ordnern behalten den alten Pfad (spätere DELETE-Ereignisse beim Purge treffen ggf. neu belegte Pfade). | `watcher.py:94-199` |
| B12 | mittel | Überschreiben ohne Kollisionsschutz: `exists()` + `rename` bzw. `open("wb")` (POSIX-`rename` überschreibt still). | `index_utils.py:396-406`, `main.py:339` |
| B13 | mittel | Scan: `os.walk` ohne `onerror`, ein sichtbarer Mountpoint zählt als "erreicht", Stale-Liste ohne Abdeckungsnachweis; Scan ist globale Löschliste. | `filemanager_file.py:829-885` |
| B14 | mittel | `unlink()` löscht Bytes **vor** der DB-Zeile (Odoo-Core macht es umgekehrt). | `filemanager_file.py:401-407` |
| B15 | niedrig | Kein fsync des Elternverzeichnisses nach `os.replace` (Odoo-Core selbst schreibt ohne fsync). | `write_service.py:198-201` |

Korrekturen früherer Aussagen: WebDAV-Abbruch (B5, s. o.); ein reiner In-Memory-Lock als Lösung ist
verworfen; `max_user_watches` ist bei dieser Größe kein Risiko.

---

## 3. Was Odoo selbst tut (Bordmittel, im Core gelesen)

Odoo hat **keinen Ordner-Watcher** (einziger Watcher im Core: Code-Reload im Entwicklermodus,
`service/server.py`). Für "DB plus Dateien" und "externes System, das sich unabhängig ändert" gibt es
aber belastbare Muster:

| Baustein | Fundstelle (Odoo 19 im Container) | Aussage |
|---|---|---|
| Blob vor dem Commit, unveränderlich | `ir_attachment.py:754-800` `create`, `:158` `_file_write` | Reihenfolge in Odoo: erst DB-Zeile (`super().create`, Name `store_fname` aus dem Hash vorab bekannt), dann Blob (`_file_write`), beides vor dem Request-Commit. Name = sha1, nur schreiben wenn nicht vorhanden, vorher in Checkliste. Abbruch → Rollback der Zeile, Blob bleibt als harmloser Orphan (GC). Zugesichert ist also "Blob liegt vor dem Commit", nicht "Blob vor der Zeile" |
| Löschen: erst DB, Bytes später | `ir_attachment.py:741` `unlink`, `_file_delete`, `_gc_file_store` | Bytes nur per GC-Cron, nie sofort |
| Externe Wirkung nach Commit | `sql_db.py:165-168, 566-577`; `mail_mail.py:689`; `ir_actions.py:1062`; `bus.py:139-150` | `cr.postcommit`; bei `rollback()` wird `postcommit.clear()` aufgerufen → **Retry wiederholt nur DB-Arbeit** |
| Hooks fangen nichts ab | `tools/misc.py` `Callbacks.run` | Ein Fehler im Hook = 500 trotz Commit → Hook muss selbst try/except |
| Sperren | `orm/models.py` `lock_for_update()` / `try_lock_for_update()` (`SKIP LOCKED`); Cron `FOR NO KEY UPDATE SKIP LOCKED` | Zeilensperren; Advisory-Lock nur **einmal** im Core (`mail_thread.py:1488`, `pg_try_advisory_xact_lock(hashtext(message_id))` zur Duplikatserkennung eingehender Mails, Korrektur 2026-09-25) |
| Isolation / Retry | `sql_db.py:373` `REPEATABLE READ`; `service/model.py:185-239` `retrying` (bis 5×, bei `40001`/Deadlock/LockNotAvailable) | `retrying(func, env)` ist auch für Hintergrundarbeit nutzbar |
| Externes System synchronisieren | `google_calendar/models/google_sync.py` | `need_sync`-Flag, `@after_commit` (postcommit + eigener Cursor + try/except, nur loggen), Pull per Cron, `need_sync=False` beim Schreiben von extern (Echo-Vermeidung), Archivieren (`active=False`) statt Löschen, "Last updated wins" (Kommentar im Code: "dangerous" bei Uhrenabweichung) |
| Cron-Werkzeuge | `ir_cron.py:735` `_trigger()`, `:846` `_commit_progress()`; `server.py:542-583` | `_trigger()` weckt den Cron-Thread per `LISTEN cron_trigger` (sonst alle 60 s); `at=` nur minutengenau; Batches mit Zeitbudget und Fortschritt |
| Editor-Revision | `onlyoffice_odoo/controllers/controllers.py:271` | ONLYOFFICE-Key = `attachment.id + checksum` |
| Snapshot-Fresh-Lock | `ir_attachment.py:197-212` | Odoo nutzt `LOCK TABLE` als *erstes* Statement in neuer Transaktion; ein Advisory-Lock in bestehender `REPEATABLE READ`-Transaktion erneuert den Snapshot **nicht** |

**Nachprüfung der Tabelle (2026-09-24, zweiter Durchgang im Core, Ergänzungen und Korrekturen):**

- **Blob:** In `create()` wird zuerst die DB-Zeile in der Transaktion angelegt, danach `_file_write` —
  der Blob liegt vor dem *Commit* auf der Platte, nicht vor der DB-Zeile. `_get_path` vergleicht bei
  vorhandenem sha1-Namen den Inhalt und wirft bei Abweichung `UserError` ("collides"); `_file_write`
  selbst schreibt nicht atomar (`open(..., 'wb')`), eine halb geschriebene Datei würde also als
  Kollision auffallen, nicht repariert.
- **GC:** `_gc_file_store` läuft über `@api.autovacuum` (täglicher Cron `autovacuum_job`).
- **postcommit und Savepoints:** `rollback()` und `retrying` verwerfen `postcommit`-Hooks. Ein
  Rollback auf einen **Savepoint** (`_FlushingSavepoint.rollback` → `cr.clear()`) verwirft aber nur
  `precommit`-Hooks. Ein Hook, der in einem gescheiterten `with cr.savepoint()`-Block registriert
  wurde, läuft nach dem Commit trotzdem. Regel: Hook erst am Ende registrieren und im Hook den Zustand
  aus der DB prüfen (idempotent).
- **Sperren:** Im Core genau ein Advisory-Lock: `pg_try_advisory_xact_lock` in `mail_thread.py:1488`
  (Dedupe je `message_id`; der Grep vom 09-24 suchte `pg_advisory` und verfehlte `pg_try_advisory`,
  Korrektur 2026-09-25). Die Entscheidung gegen Advisory-Locks stützt sich daher **nicht** auf "Odoo
  nutzt keine", sondern darauf, dass `lock_for_update` auf der Zeile genügt. Tabellensperren nur in
  `ir_attachment` (GC), `ir_module`, `transifex`. `lock_for_update()` wirft
  `LockError` (UserError), wenn nicht alle Zeilen sperrbar sind, es wartet nicht.
- **Cron läuft nicht in `retrying`.** Ein `40001` im Cron ist ein Fehlschlag des Jobs
  (`failure_count`+1); Deaktivierung erst bei ≥5 Fehlern in Folge **und** erstem Fehler älter als
  7 Tage (`MIN_FAILURE_COUNT_BEFORE_DEACTIVATION`, `MIN_DELTA_BEFORE_DEACTIVATION`, Admin-Meldung).
  Der Abgleich-Cron muss `40001` daher pro Batch/Pfad selbst abfangen und `_commit_progress` nutzen.
- **Google-Sync, Löschen:** Ein extern vorhandener Datensatz wird beim Löschen zunächst **archiviert**
  (`unlink` → `action_archive`), damit Odoo das externe Löschen noch auslösen kann; erst nach der
  Bestätigung der Gegenseite wird er endgültig gelöscht. Archivieren ist dort ein Wartezustand, kein
  dauerhafter Tombstone. Die Schonfrist für "extern entfernt" ist unsere eigene Regel.
- **ONLYOFFICE-Callback prüft den Key nicht:** `/onlyoffice/editor/callback/<attachment_id>` lädt bei
  Status 2/3 die Datei und ruft `attachment.write({"raw": …})` ohne Vergleich mit der aktuellen
  Checksum. Ein veralteter Save überschreibt still. Die Basisrevisionsprüfung (Body-`key` gegen
  `id + aktuelle checksum`) müssen wir ergänzen (das `key`-Feld im Callback-Body ist laut
  ONLYOFFICE-API vorhanden, im Code nicht geprüft). Code liegt im Repo
  (`onlyoffice_odoo/controllers/controllers.py:200-275`, am 2026-09-25 gelesen): Callback vergleicht
  `body["key"]` nicht; der Key wird beim Öffnen als `id + checksum` gebildet (`:271`). Status 3 wird wie
  Status 2 geschrieben (`:236`); nach der ONLYOFFICE-API bedeutet 3 einen Speicherfehler, die URL ist dann
  evtl. unbrauchbar (aus API-Wissen, nicht gegen die Doku geprüft).
- **Snapshot-Test (Wegwerf-Postgres 17):** `LOCK TABLE` als erstes Statement einer
  `REPEATABLE READ`-Transaktion sieht die inzwischen committete Zeile (1); ein Advisory-Lock als
  erstes Statement sieht sie nicht (0); "erst SELECT, dann LOCK" ebenfalls nicht (0).

---

## 4. Zielbild für App-Änderungen ("Odoo-Weg")

Grundsatz: **DB-Commit = Wahrheit, Platte folgt im selben Request, Zustand ist persistent sichtbar.**

Neues Feld `share_state` auf `int_filemanager.file`: `synced` / `pending` / `conflict`
(Hinweis-Zustand, siehe 6). Bestandszeilen bei der Migration auf `synced`.

### 4.1 Inhalt ändern (App-Speichern, ONLYOFFICE, WebDAV, Text, Version-Restore)
1. Rechte und Editorsitzung prüfen (Sitzung an **Dokument-ID + Basisrevision/Checksum** gebunden).
2. Neue Bytes als **Blob im Filestore** bereitstellen (harmlos bei Abbruch; GC räumt auf). Wie in
   Odoo (`ir_attachment.create`) geschieht das **innerhalb der Request-Transaktion, vor dem Commit**, und
   zwar **erst die DB-Zeile, dann der Blob** — die Reihenfolge ist *nicht* gleichgültig: Der GC löscht
   Blobs ohne committete Zeile und wartet nur auf Transaktionen, die schon eine Zeile eingefügt haben
   (`ir_attachment.py:190-217, 794-797`; Korrektur 2026-09-25). Blob nie nach dem Commit.
3. Request-Transaktion: Dateizeile per `lock_for_update` sperren, Version anlegen (Filestore,
   Odoo-GC), Größe/Checksum/Revision setzen, `share_state='pending'`. **Commit = verbindlich.**
4. `postcommit`-Hook (mit eigenem Cursor, komplett in try/except): **Vorher-Nachher-Prüfung** —
   Plattenstand (Größe, mtime_ns, Inode) mit dem letzten bekannten Stand vergleichen; bei Abweichung
   den Plattenstand lesen und als Version mit Herkunft "extern" ablegen; unmittelbar vor dem Austausch
   erneut `stat` prüfen, bei Änderung erneut lesen (begrenzte Wiederholungen). Dann neue Datei mit
   `os.replace` einsetzen (Temp im selben Ordner, fsync auch des Elternordners), dann
   `share_state='synced'`. Es bleibt ein Restfenster von Millisekunden (Abschnitt 6).
5. Fehler im Hook → Zustand bleibt `pending`; der Abgleich-Cron holt nach (idempotent, Publish aus
   dem Blob, nur wenn Revision noch aktuell).

### 4.2 Umbenennen / Verschieben / Papierkorb / Ordner anlegen
DB zuerst (neuer Pfad/Zustand + Marker Quelle→Ziel, `pending`), Commit, dann Hook mit `os.rename`
(**ohne Überschreiben**, auf shfs getestet: `renameat2` ist dort unbrauchbar (`EINVAL`); Dateien per
`os.link` + `os.unlink`, Ordner per `os.mkdir` + `os.rename`, siehe Abschnitt 13), dann `synced`.
Teilbäume: Pfadumschreiben möglichst als eine Operation (ORM `_parent_store`; SQL-Variante nur nach
Prüfung von `parent_path`). Download bei `pending` liest vom Blob bzw. alten Pfad.

### 4.3 Endgültig löschen
Zeile zuerst als gelöscht markieren/entfernen, Bytes später per Cron (GC-Muster). Nie umgekehrt.

### 4.4 Retry-Sicherheit
Nichts Externes passiert vor dem Commit → Odoos `retrying()` ist für die DB-Arbeit unproblematisch.
Zusätzlich vom Client mitgeschickte **Vorgangs-ID** gegen Doppelklick/erneutes Senden.

**Was `retrying` wiederholt und was nicht** (`service/model.py:196-214`, 2026-09-25): nur 40001,
Deadlock, `LockNotAvailable` und `ConcurrencyError`. `IntegrityError` wird zu einem `ValidationError`
**ohne** Wiederholung. `LockError` (`lock_for_update`) ist ein `UserError` und wird ebenfalls nicht
wiederholt: Ein Doppelklick auf dieselbe Datei liefert sofort eine Fehlermeldung, kein stilles Warten —
das fängt nur die Vorgangs-ID ab. Positiv (**2026-09-25 auf PostgreSQL 16 ausgeführt, → 19.2**):
`FOR UPDATE SKIP LOCKED` auf einer nach dem Snapshot committeten Zeile wirft unter `REPEATABLE READ` 40001
(ebenso `FOR NO KEY UPDATE SKIP LOCKED` und `NOWAIT`); ist die Zeile von einer offenen Transaktion gesperrt,
liefert `SKIP LOCKED` leer. Der Retry liest dann frisch und erkennt die geänderte Basisrevision.

**Einschränkung Upload-Body (aus `service/model.py` `retrying` abgeleitet, nicht ausgelöst, 2026-09-25):**
Beim Retry spult Odoo nur `request.httprequest.files` zurück, und nur wenn sie `seekable` sind (sonst
`RuntimeError`). Ein roher Body (WebDAV-PUT) steht nicht in `.files`. Wird er im Controller in die
Temp-Datei gestreamt (4.1 Schritt 2), liest ein zweiter Versuch einen bereits verbrauchten Body und
könnte eine **leere Datei** veröffentlichen. Das Staging muss deshalb **idempotent** sein: Temp-Datei je
Vorgangs-ID mit Fertig-Marker, die ein Retry wiederverwendet, statt den Body erneut zu lesen.

### 4.5 Was entfällt
`suppress_watcher()`, `_upsert_by_path` (rohes SQL), eigene psycopg2-Verbindung und `pg_advisory_lock`
in `write_service`, mehrere Commits mitten im Request, das 30-min-Journal als Recovery (ersetzt durch
`pending` + Cron; `write_journal` bleibt höchstens als Log).

---

## 5. Externe Änderungen und Watcher

### 5.1 Rollen
| Aufgabe | Wer |
|---|---|
| Ereignisse sammeln, Namen-Filter (`~$…`, `.~lock`, `.int_filemanager_tmp_…`), Watches pflegen, `dirty`-Einträge und Herzschlag über einen **eigenen kurzen Cursor** schreiben | **Watcher** (kein DB-Lesen zum Entscheiden, keine Schreibung in Index-Tabellen) |
| DB lesen, Zustand vergleichen, entscheiden, schreiben | **Abgleich-Cron** (Odoo-Framework) |

Der Watcher **liest die DB nicht zum Entscheiden** und verwirft nie ein Ereignis wegen des
DB-Zustands (sonst gehen Signale verloren, z. B. Explorer-Schreiben während `pending`).

### 5.2 Minimaler Watcher
1. Watches registrieren/pflegen (neue Ordner, Umschreiben bei Ordner-Umbenennung, `IGNORED`,
   Watches von nach `.trash` verschobenen Ordnern entfernen).
2. Pfade als "dirty" im Speicher vormerken; bei Move den **alten Pfad als Hinweis** mitgeben.
3. Einmal pro Sekunde gebündelt in Tabelle `dirty` (ORM, Pfad eindeutig) schreiben, dann
   `cron._trigger()` (legt `ir.cron.trigger` an, im selben Cursor). Das ist eine DB-Schreibung außerhalb
   eines Requests und braucht deshalb einen **eigenen kurzen Cursor** (`Registry(dbname).cursor()` mit
   Commit, wie Odoos `after_commit`/Mail-Versand). Scheitert er (DB weg, `40001`), bleiben die Einträge im
   Speicher und werden im nächsten Takt erneut versucht; wächst der Speicher über ein Limit, wird
   "Vollabgleich nötig" gesetzt. Bewusst **keine** reine Speicher-Liste: die würde nur funktionieren,
   solange Watcher und Cron im selben Prozess laufen (`workers=0`). **Trigger sparsam setzen:** jeder
   `_trigger()`-Aufruf legt eine `ir.cron.trigger`-Zeile an (`ir_cron.py:~787`); sie wird beim Lauf gelöscht
   (`_clear_schedule`). Der Autovacuum `_gc_cron_triggers` (`ir_cron.py:906-916`) räumt nur Trigger
   **inaktiver** Crons nach einer Woche auf, nicht die eines aktiven, aber hängenden Crons. Bei 1 Aufruf/s
   wären das bis zu 86.400 Zeilen/Tag, ohne dass jemand aufräumt → nur triggern, wenn `dirty` von leer auf
   nicht leer wechselt.
4. Herzschlag (Zeitstempel pro Minute).
5. Aufpasser: Absturz von `read()` → Neustart, Watches neu, "Vollabgleich nötig"; `Q_OVERFLOW` →
   "Vollabgleich nötig". Kein Schreiben in Index-Tabellen.

### 5.3 Abgleich-Cron
- Bearbeitet nur `dirty`-Pfade, die älter als 2–3 s sind (Ruhezeit, **Debounce per Zeitstempel**, da
  `_trigger(at=…)` nur minutengenau ist). **Wartet in der Ruhezeit im Lauf selbst** (Zeitbudget je Lauf
  ca. 10 s, `MIN_TIME_PER_JOB`), statt sich per `_trigger()` neu anzustoßen: Der Cron-Thread wartet nach
  `_process_jobs` wieder auf NOTIFY oder 60 s (`server.py:542-616`); ein Selbst-Trigger pro Lauf liefe im
  Sekundentakt heiß (Acquire, Trigger-INSERT, NOTIFY). Meldet der Lauf `remaining>0` ohne Fortschritt
  (`PARTIALLY_DONE`), legt `_reschedule_asap` einen Trigger **ohne** NOTIFY an (nur mit
  `ODOO_NOTIFY_CRON_CHANGES`, `ir_cron.py:436-441, 659-669`); der nächste Lauf kommt dann erst nach ≤60 s.
  `_run_job` ruft den Callback bis zu 10-mal auf, solange `remaining>0` und `done>0` gemeldet werden — die
  Fortschrittsmeldung muss stimmen.
- Cron läuft nicht, solange irgendein Modul auf "to upgrade/install/remove" steht (`_check_modules_state`,
  `ir_cron.py:250-283`): Bei Rollouts staut sich `dirty` auf; der Rückstau muss verkraftbar sein.
- Batches mit `_commit_progress`, ORM-Schreibzugriffe, Kontext-Flag `int_filemanager_syncing_index`
  (existiert bereits) statt Echo, `retrying` bei `40001`.
- **Eine** Abgleich-Funktion `reconcile_path(pfad)` für Watcher-Signale, Nachholabgleich, Scan und
  Recovery. Ein Scan ist nur ein Lauf dieser Funktion über größere Bereiche.
- Zeilen mit `share_state != 'synced'` werden zurückgestellt und danach nachgeprüft.
- **Nachholabgleich** des lokalen Shares beim Start und regelmäßig (mtime-basiert). Kosten lokal
  **noch nicht gemessen**.

### 5.4 Was bei Explorer-Aktionen passiert
| Aktion | Ergebnis in der DB |
|---|---|
| Datei ändern/speichern | Gleiche Zeile: neue Größe/mtime, Revision +1, Herkunft "extern", `hash_state=pending`; Crons rechnen Hash/Meta/Volltext nach; Bus aktualisiert die Ansicht |
| Umbenennen/Verschieben (gleicher Share) | Gleiche Zeile bekommt neuen Pfad (Tags, Versionen, Freigaben bleiben); Ordner: Teilbaum umschreiben |
| Neue Datei kopieren | Abgleich erst nach `CLOSE_WRITE`/Ruhe; neue Zeile, Hash pending |
| Löschen | **Nicht** hartes Löschen: Zeile archiviert (`active=False`, Grund "extern entfernt"), Schonfrist offen |
| Unsichere Umbenennung (Paar getrennt) | Alter Eintrag "extern entfernt", neuer angelegt; Hash-Abgleich im Scan kann beides später zusammenführen |
| Office-Safe-Save (Temp-Dateien, Umbenennungen) | Ruhezeit + Endzustand statt Einzelereignissen → Original-Zeile behält Identität |

Latenz: Sekunden bis etwa eine Minute (heute: Sekunden, direkt durch den Watcher).

### 5.5 Archivieren statt Löschen — Stolperstein
`unique(path)` gilt auch für archivierte Zeilen: Neue Datei mit gleichem Pfad würde kollidieren.
Beim Archivieren Pfad freigeben oder Unique-Index nur für aktive Zeilen definieren. **Empfehlung:**
partieller Unique-Index, in Odoo 19 nativ als `models.UniqueIndex` mit `WHERE`-Klausel (Abschnitt 15).

**Achtung, doppelte Bedeutung von `active` (Konzeptlücke, 2026-09-25):** Abschnitt 16.1 will den Papierkorb
ebenfalls als `active=False` abbilden. Odoo kennt nur **ein** `active` (`orm/models.py:5371-5374`). Dann zeigt
die Papierkorb-Ansicht `[('active','=',False)]` auch Tombstones "extern entfernt", "Wiederherstellen" hätte für
sie keine Datei in `.trash`, und der Purge-Cron träfe beide. Aus der Semantik abgeleitet, nicht ausprobiert.
Nötig ist ein Unterscheidungsmerkmal (Grund-Feld/Status, z. B. `removal_reason`: `trash` / `external`) oder
Tombstones nicht über `active` zu führen; Papierkorb-Ansicht, Restore und Purge filtern dann auf den Grund.

---

## 6. Vorrang, Konflikte, Ordner-Modi

**Regel:** Die App-Version wird immer aktuell (kein blockierender `conflict`). Externer Inhalt, der
dabei überschrieben würde, wird **vorher als Version gesichert** (Herkunft "extern"). Externe
Schreibvorgänge *nach* dem Veröffentlichen sind neue externe Änderungen (Abschnitt 5.4).

Bereits heute so (Teilstück): `write_service.py` liest vor dem Schreiben den Plattenstand und sichert
ihn als Version. Lücken: Änderungen zwischen Lesen und `os.replace` gehen verloren; ab 200 MB wird das
Überschreiben komplett abgelehnt (`write_service.py:117`). Die **Vorher-Nachher-Prüfung** (4.1)
verkleinert die erste Lücke auf die Millisekunden zwischen letztem `stat` und `os.replace`; ganz
schließen lässt sie sich mit POSIX nicht (kein Compare-and-Swap für Dateien). `renameat2(RENAME_EXCHANGE)`
würde sie atomar schließen, ist auf shfs aber **nicht nutzbar** (getestet: `EINVAL`). **Hardlinks als
Sicherung wurden verworfen** (hinterlassen bei Absturz sichtbare Restlinks, bringen gegenüber der Prüfung
kaum Gewinn); sie funktionieren auf shfs aber grundsätzlich (getestet) und dienen dem No-Replace-Rename.

**Odoo-Core-Befund zum Restfenster (2026-09-24, im Container gelesen):** Der Core hat dafür **keinen**
Baustein. Kein Compare-and-Swap für Dateien, keine Dateisperren (`fcntl` nur für Sockets in
`service/server.py`), kein `O_EXCL`/`fsync`-Muster, keine Revisionsprüfung im ORM
(`__last_update`/`CONCURRENCY_CHECK_FIELD` in `orm`, `http`, `service` nicht vorhanden;
`ConcurrencyError` ist nur ein Retry-Signal und wird nur in einem Test ausgelöst). Odoos Antwort ist
konstruktiv: **ein einziger Schreiber** pro Speicher (Filestore) und **unveränderliche Blobs**
(`_file_write` schreibt nur, wenn nicht vorhanden; Session-Store: Temp + Rename). Für uns heißt das:
Das Restfenster verschwindet nur dort vollständig, wo Odoo alleiniger Schreiber ist (Modus
"Explorer read-only"). Zwischen zwei App-Nutzern gilt der native Weg: Zeile per `lock_for_update`
sperren und die Basisrevision (Checksum, wie der ONLYOFFICE-Key) in derselben Transaktion prüfen. Ein
zwischenzeitlich committeter Save löst unter `REPEATABLE READ` 40001 aus, der Retry sieht dann die neue
Revision (siehe 4.4).

**Ordner-Modi** (Konfiguration je Ordner):

| Modus | Verhalten bei externer Änderung | Voraussetzung |
|---|---|---|
| **annehmen** (Standard) | DB übernimmt sie als neue Revision | keine |
| **zurücksetzen** | Externes wird gesichert, DB-Fassung wiederhergestellt | DB hat Inhaltskopie → nur "verwaltete" Ordner |
| **Explorer read-only** | Verhindert das Schreiben an der Quelle | Samba-Rechte (Infrastruktur, nicht Odoo) |

Bei `pending` oder aktiver Bearbeitung (ONLYOFFICE) gilt immer "zurücksetzen und externen Stand
sichern", unabhängig vom Modus. **Nur "Explorer read-only" ist echtes Unterordnen**; alles andere ist
Angleichung im Nachhinein.

Kein vollständiger Inhaltsspeicher: bei 1,3 TB wäre das eine Vollkopie. Inhaltskopien halten wir nur
für Versionen und "verwaltete" Ordner.

---

## 7. Was bleibt (Grenzen, nicht lösbar)

- **Gleichzeitiges Schreiben Explorer/App** kann erkannt, nicht verhindert werden.
- **Alter Inhalt bei externem Überschreiben** ist weg, wenn die App ihn nicht vorher versioniert hat
  (Unraid-Snapshots/Backup wären die einzige Rettung).
- **Clients mit offenem Dateihandle** schreiben nach dem Austausch in den alten Inode; diese
  Schreibungen sind danach nicht mehr erreichbar. **Über SMB bestätigt (→ 19.3):** Der Windows-Client bekommt
  keinen Fehler; auch eine Sperre wie bei Word (`FileShare.Read`, andere dürfen nicht schreiben) hält das
  `os.replace` auf dem Server nicht auf. Word, Excel und LibreOffice speichern per Umbenennen und sind davon beim
  Speichern selbst nicht betroffen (→ 19.3).
- **Latenz externer Änderungen** Sekunden bis eine Minute; Lesewege müssen `pending` behandeln.
- **Ereignisverlust** lässt sich nie ausschließen → Nachholabgleich bleibt Pflicht.
- Odoo-Filestore hat kein fsync im Core (für unsere Publish-Pfade ergänzen).

---

## 8. Native vs. selbstgebaut

| Baustein | Herkunft |
|---|---|
| ORM, Transaktionen, `retrying`, Zeilensperren | nativ |
| `postcommit`/Rollback-Verwerfen, `bus.bus` | nativ |
| Cron, `_trigger`, `_commit_progress`, exklusive Jobsperre | nativ |
| `active`-Archivierung, Filestore/GC/Blob-Muster | nativ |
| `need_sync`-Muster (→ `share_state`) | nativ als Muster, Umsetzung eigen |
| Ordner-Watcher (inotify) | **selbstgebaut** (Odoo hat keinen) |
| `dirty`-Liste, Ruhezeit, Abgleich Platte↔DB, Umbenennungs-Erkennung, Vorher-Nachher-Prüfung beim Veröffentlichen, Ordner-Modi | **selbstgebaut** |

Konsequenz: Der DB-Teil steht auf erprobten Odoo-Mustern; **alles, was die Platte betrifft, ist
Eigenbau und braucht die meisten Tests.**

---

## 9. Bezug zu bestehenden Docs

| Doc | Einordnung |
|---|---|
| `archiv/int_filemanager_wahrheitsmodell_watcher_reduktion_2026-09-24.md` | Idee "Schnitt lokal/CIFS" trägt nicht (Daten liegen fast nur auf CIFS-Testfreigaben, lokal nur `Test`); Zeile "App-Schreibvorgänge sind DB-geführt" trifft nicht zu (B4) |
| `archiv/int_filemanager_filebrowser_scan_architektur_2026-09-23.md` | Bezieht sich auf `_shallow_reconcile()`, der nicht existiert; CIFS-Scanstrategie ist Testbetrieb und niedrig priorisiert |
| `archiv/recherchen-odoo-bausteine/int_filemanager_papierkorb_odoo_umsetzung_2026-09-23.md` | Papierkorb ist bereits mit `trashed`-Feld umgesetzt (Commit `b53fed2`), nicht mit `active`; Watcher-Guard-Argument überholt |
| `archiv/int_filemanager_watcher_stille_fehlschlaege_2026-09-23.md` | Funde bleiben gültig, Bewertung ändert sich (`max_user_watches` unkritisch; Watchdog wichtig, aber Watcher wird zum Zulieferer) |
| `archiv/int_filemanager_grundsatz_explorer_ausbau_2026-09-23.md` | Roadmap bleibt; Reihenfolge Abschnitt 10 dieses Docs hat Vorrang für das Fundament |
| `archiv/recherchen-odoo-bausteine/int_filemanager_bildvorschau_bearbeitung_odoo_2026-09-23.md` | Recherchebasis; die Empfehlung "Cropper.js selbst einbinden, Filterfunktionen kopieren, Rotation per Pillow" ist durch Abschnitt 17 (nativer Bauplan) **ersetzt** |
| Externes Review (Desktop\SOPRANO) | Weitgehend bestätigt (B1 verifiziert). Eingeschränkt: kein vollständiger Inhaltsspeicher (1,3 TB); Share-Ausführung synchron mit persistentem Zustand statt reiner Hintergrund-Queue |

---

## 10. Umsetzungsreihenfolge

1. **Hotfix Scan/Papierkorb (B1):** `trashed`/Punktpräfix aus dem Stale-Abgleich nehmen, Scan und
   Watcher führen keine fachlichen Löschungen mehr aus; "nicht erreichbar/unklar" heißt "unbekannt",
   nie "gelöscht". Unabhängig vom Rest, zuerst.
2. **Durchstich "Upload überschreiben"** komplett im neuen Ablauf (4.1) mit Fehlerinjektion nach
   jedem Schritt. Entscheidet, ob der Ablauf trägt, bevor alles umgebaut wird.
3. **Übrige App-Schreibwege** (ONLYOFFICE, WebDAV-PUT, Textbearbeitung, Upload-Neu, Restore) und
   Struktur-Operationen (4.2), Editorsitzungen an Dokument-ID + Revision, No-Replace-Umbenennen.
4. **Abgleich-Cron + `dirty`-Tabelle + minimaler Watcher** (Abschnitt 5), Nachholabgleich,
   Herzschlag, Watchdog, Tombstone/Archivierung.
5. **Ordner-Modi** und Konfliktanzeige (Abschnitt 6).
6. Erst danach CIFS/Scan-Optimierung (Testbetrieb).

### Pflichttests (isoliert, Testinstanz mit echten unabhängigen Prozessen)
- Alle App-Operationen bei **abgeschaltetem Watcher**.
- Prozessabbruch nach jeder dauerhaften Stufe; Wiederholung ohne Doppelversion/Datenverlust.
- Identischer Request zweimal; Timeout nach erfolgreichem Commit; Vorgangs-ID mit anderem Payload.
- Zwei Saves derselben Basisrevision; verspäteter Office-Save nach Rename und Neubelegung des Pfads.
- Ordner-Move gegen Kind-Save; Rename gegen Upload ins Ziel; Explorer-Schreiben während `pending`.
- Platte voll, DB weg, Mount weg, Ziel fremd belegt, Cross-Mount-Move.
- Papierkorb und Versionen über mehrere Scans erhalten; partielle Scanfehler löschen nichts.
- Echte Word-/Excel-Saves über Samba/shfs (Safe-Save-Ereignisse), Ordner-Rename im Explorer,
  (No-Replace-Rename auf shfs ist getestet, siehe Abschnitt 13; offen: echte Office-/Explorer-Saves per SMB).
- Backup/Restore stellt jede bestätigte Version lesbar wieder her.

---

## 11. Offene Entscheidungen

1. **Löschen von außen:** Schonfrist des Tombstones und Darstellung (Filter "Extern entfernt" oder
   eigene Liste)?
2. **Ordner-Modi:** Standard "annehmen" bestätigen; welche Ordner "verwaltet"/read-only?
3. **Konflikt:** reicht ein Hinweis "externe Version gesichert", oder soll die App eine Auswahl
   anbieten (eigene Version als Kopie / externe übernehmen)?
4. **Rename-Erkennung:** zusätzlich Inode/Gerät je Zeile speichern (verlässlicher auf lokalem FS) oder
   bei Hinweis + Größe/mtime bleiben?
5. **`unique(path)` und Archivierung:** Empfehlung partieller Unique-Index (`models.UniqueIndex` mit `WHERE`,
   Abschnitt 15) statt Pfad freigeben — bitte bestätigen.
6. Ob und wann Samba-Rechte für Explorer-Nutzer eingeschränkt werden (organisatorisch).

---

## 12. Verifikationsstatus dieser Aussagen

- **Getestet:** `INSERT … ON CONFLICT DO UPDATE` unter `REPEATABLE READ` gegen nach dem Snapshot
  committete Zeile → `could not serialize access due to concurrent update` (Wegwerf-Postgres 17);
  unter `READ COMMITTED` läuft es durch.
- **Im Odoo-Core gelesen** (Container `Odoo19`): alle Fundstellen in Abschnitt 3.
- **Aus dem Repo-Code abgeleitet, nicht ausgelöst:** B1–B15.
- **Auf der Testinstanz getestet (2026-09-24):** alles in Abschnitt 13.
- **Nicht geprüft:** Gesamtkonzept als Prototyp (Durchstich mit Fehlerinjektion); echte Word-/Excel-Saves
  und Explorer-Aktionen per SMB (Share `TestRepo_UNRAID` ist nicht freigegeben); Ordner-Rename über
  mehrere Array-Platten; ob Enterprise-`documents`/OCA-Module etwas Vergleichbares für externe Ordner
  bieten.
- **Nachtrag 2026-09-25 (→ 19):** Durchstich "Upload überschreiben" mit Fehlerinjektion, Explorer-Aktionen,
  Word-/Excel-Speicherabläufe und echte LibreOffice-Saves per SMB sowie Ordner-Rename über mehrere Array-Platten
  sind auf Tower geprüft. Echtes MS Office war nicht verfügbar; Word und Excel wurden mit ihren bekannten
  Dateioperationen über SMB nachgebildet. Enterprise/OCA weiterhin offen.

---

## 13. Testergebnisse (Testinstanz auf HM-SRV, 2026-09-24)

Aufbau: eigene Container `fmtest_odoo` / `fmtest_pg` (Image `int-filemanager-odoo:19.0-ocr`, Repo-Stand
`432a95f`, Threaded, Watcher aktiv), eigene DB, Wurzel `/mnt/user/TestRepo_UNRAID/fmroot` (shfs auf dem
Cache-Pool wie `HM-Daten`). Externe Änderungen wurden vom Host aus auf demselben shfs erzeugt (wie
Samba). Die Live-Instanz blieb unberührt.

### 13.1 Odoo-Verhalten (Scratch-Odoo, `retrying()` direkt aufgerufen)
| Test | Ergebnis |
|---|---|
| Echter `40001` + `postcommit`-Hook | 2 Versuche, **nur der Hook aus Versuch 2** lief |
| Hook in gescheitertem Savepoint-Block | Hook läuft **trotzdem** nach dem Commit (DB-Änderung war zurückgerollt) |
| Hook wirft Exception | Exception geht nach außen, **DB trotzdem committet**, folgender Hook läuft nicht |
| `lock_for_update` bei gesperrter Zeile | `LockError` sofort (0,00 s); `try_lock_for_update` → leer |
| `cron._trigger()` (Threaded) | Cron läuft nach **~0,05 s** |
| `_trigger(at=+3 s)` | läuft erst nach **~58 s** (nächster 60-s-Takt) → für Debounce unbrauchbar |
| 20 Trigger in 4 s, Job dauert 1 s | 6 Läufe (zusammengefasst); Trigger während eines Laufs → ein weiterer Lauf, **nie parallel** |
| ONLYOFFICE-Callback mit veraltetem Key | **wird still angenommen** (`{"error":0}`), Datei = veraltete Fassung; beide Vorgänger als Versionen gesichert, kein Datenverlust, aber falscher Gewinner |

### 13.2 Dateisystem shfs (Container-Sicht)
| Test | Ergebnis |
|---|---|
| `os.rename` auf vorhandene Datei / leeren Ordner | überschreibt **still** |
| `renameat2(NOREPLACE)` | Ziel existiert → `EEXIST`, aber freier Name → **`EINVAL`** (unbrauchbar) |
| `renameat2(EXCHANGE)` | `EINVAL` (nicht unterstützt) |
| `os.link` (Hardlink) | funktioniert |
| `O_CREAT|O_EXCL`, `fsync` auf Verzeichnis | funktionieren |
| No-Replace per `link`+`unlink` (Datei), `mkdir`+`rename` (Ordner) | **funktioniert**, lehnt vorhandenes Ziel ab |
| Inode vor/nach Rename (Datei, Ordner) | **stabil**; `os.replace` wechselt den Inode |
| Ordner-Rename mit 10.000 Dateien | 0,000 s |
| Dateien anlegen | ~1.900/s |

### 13.3 Watcher und Scan (bestehender Code, externe Änderungen vom Host)
| Szenario | Ergebnis |
|---|---|
| Anlegen, in place ändern, Umbenennen, Ordner-Rename, Löschen | wird innerhalb ~3 s korrekt abgebildet (Umbenennen behält die Zeile) |
| In-place-Überschreiben | Zeile und Token bleiben |
| **Word-Safe-Save** (schnell) | Zeile mit Token **weg, neue Datei nicht indexiert** |
| Word-Safe-Save (langsam) | neue Zeile, **Token/Identität verloren** |
| **Excel-Safe-Save** | neue Zeile, **Token verloren** |
| `mv -f a b` über vorhandenen Namen | `UniqueViolation` im Watcher, Ereignis verloren, **Geisterzeile** für `a` |
| Kollision Watcher ↔ eigener `index_upsert` (Testskript) | Watcher-Ereignis scheitert mit `40001`, ohne Retry (Log) |
| 20.000 Dateien in 200 neuen Ordnern | vollständig, aber **~12 min** Rückstau (~1.700 Einträge/min) |
| **20.000 Dateien einzeln in einem Ordner** | nur **5.575** im Index, Rest **dauerhaft verloren** (Überlauf) |
| Odoo stoppen, extern ändern, starten | **keine Nachholung** (neue Dateien fehlen, gelöschte/umbenannte Zeilen bleiben) |
| Vollscan lokal (20.211 Einträge) | 18,9 s (~1.070/s), Walk+stat allein 6,4 s; Hochrechnung 1,39 Mio.: **~22 min** (Walk ~7 min) |
| Scan als Sicherheitsnetz | entfernt Geisterzeile, indexiert vergessene Datei (Metadaten bleiben verloren) |

### 13.4 Schlüsse für das Konzept
- Die **Zustands- und Endzustandslogik** (Abschnitt 5) ist nötig: Safe-Save, `mv` über vorhandene Namen und
  Überlauf sind mit dem heutigen Ereignis-Anwenden nachweislich nicht sicher.
- **Nachholabgleich** beim Start und **Überlauf-Erkennung mit Rescan** sind Pflicht.
- Der Scan ist nur ab dem Schreiben pro Zeile teuer (Dateisystemzeit ~1/3): ein Vergleich vor dem Schreiben
  (unveränderte Zeilen überspringen) verkürzt ihn deutlich.
- `_trigger()` ohne `at` weckt den Abgleich-Cron sofort; die Ruhezeit muss per Zeitstempel in der
  `dirty`-Tabelle gelöst werden.
- ONLYOFFICE-Callback braucht die eigene Basisrevisionsprüfung.
- Rename-Erkennung per **Inode als Hinweis** ist auf shfs machbar (stabil beim Rename, ungeprüft über
  Neustart/Plattenwechsel). **→ 19.3:** Die Inode ist auch plattenübergreifend, nach `drop_caches` und im neuen
  Container stabil, **ändert sich aber**, wenn der Mover eine Datei auf eine andere Platte umzieht (gleicher Pfad).

---

## 14. Vergleich mit FileBrowser (Quellcode gelesen, 2026-09-24)

Gelesen wurden FileBrowser Quantum (`gtsteffaniak/filebrowser`, Branch `main`: `internal/web/resource.go`,
`internal/adapters/fs/files/files.go`, `fileutils/file.go`, `pkg/indexing/*`, `go.mod`) und das Original
(`filebrowser/filebrowser`, Branch `master`: `http/resource.go`, `go.mod`). Nichts ausgeführt; das
Scan-Scheduling ist zusätzlich in `archiv/int_filemanager_filebrowser_scan_architektur_2026-09-23.md` beschrieben.

| Punkt | FileBrowser | Unser Konzept |
|---|---|---|
| Wahrheit | Platte. Quantum: Index im Speicher, DB nur für Nutzer, Freigaben, Scan-Zeitplan (`index_info`). Original: kein Index | DB |
| Inhalt des Index | keine Nutzerdaten; Freigaben/Regeln hängen an Pfaden; Index jederzeit neu aufbaubar | Versionen, Tags, Freigabe-Token, ACL, extrahierte Werte |
| Schreiben | `O_RDWR\|O_CREATE\|O_TRUNC` + Kopieren, keine Temp-Datei/Rename, keine Versionen; Original ruft `file.Sync()`, Quantum nicht | Temp-Datei, `os.replace`, fsync, Version |
| Reihenfolge | Platte zuerst, Index danach; beim Quantum-Move Nachpflege asynchron (Goroutinen), Fehler nur geloggt | DB zuerst, Hook danach, Zustand persistent |
| Löschen | `os.RemoveAll`, endgültig, kein Papierkorb; Indexfehler nur Log | Papierkorb, Tombstone |
| Verschieben | `os.Rename`, danach Metadaten löschen + neu indexieren (keine Identität); Freigaben/Regeln extra nachgezogen; Fallback bei Rename-Fehler: Kopieren + asynchrones `RemoveAll` | gleiche Zeile, neuer Pfad; Fallback nur mit Copy/Verify/Publish/Delete |
| Externe Änderungen | Quantum ohne Watcher (kein `fsnotify` in `go.mod`), adaptive Scans je Unterbaum; extern umbenannte Pfade brechen pfadgebundene Freigaben. Original liest live von der Platte | Watcher meldet, Cron gleicht Endzustand ab |
| Konflikte | keine (letzter Schreiber gewinnt) | Revision, Vorher-Nachher-Prüfung, Versionen |
| Read-only | `Config.ReadOnly` je Quelle, nur für die App selbst | Samba-Rechte für Explorer-Nutzer |

**Schlüsse:**
1. FileBrowser kann sich "Platte zuerst, Index best effort" leisten, weil sein Index **keine Nutzerdaten**
   trägt. Bei uns trägt die Tabelle Versionen, Tags, Freigaben und Rechte — deshalb dürfen Scan und
   Watcher dort keine Zeilen hart löschen (bestätigt den Hotfix B1) und Identität muss erhalten bleiben.
2. Schreiben in place, endgültiges Löschen und asynchrones Best-Effort sind **kein Vorbild** — es sind
   die Muster, die die Tests (Abschnitt 13) als unsicher gezeigt haben.
3. **Übernehmen:** adaptive Scan-Planung je Unterbaum mit Komplexitäts-Untergrenze für den
   Nachholabgleich in freien Zonen (statt einem täglichen Lauf von ~27 min).
4. **Vorteil unseres Modells:** Pfadgebundene Freigaben brechen bei FileBrowser nach einer externen
   Umbenennung; bei uns behält die Zeile ihre Identität.

---

## 15. Weiterer Odoo-Core-Durchgang und Messung an einer Kopie der Live-Tabelle (2026-09-24)

Ziel: nichts übersehen und nichts nachbauen, was Odoo schon kann. Gelesen wurde der Core im Container
`Odoo19` (Odoo 19); die Messung lief auf der Testinstanz, die Live-DB wurde nur gelesen.

### 15.1 Funde im Core
| Fund | Fundstelle | Konsequenz für das Konzept |
|---|---|---|
| Upload-Limit **128 MiB pro Request** (`DEFAULT_MAX_CONTENT_LENGTH`), global über ICP `web.max_file_upload_size` (live nicht gesetzt), pro Route überschreibbar mit `@route(max_content_length=…)` | `http.py:247, 1484, 2440`; `base/models/ir_http.py:298-318` | Unsere `/upload`-Route und der WebDAV-PUT haben keine Überschreibung: Dateien >128 MiB (501 im Bestand) gehen weder hoch noch per "Lokal öffnen" zurück. Nötig: Route-Limit + Streaming in eine Temp-Datei (kein `f.read()`/`get_data()`), Blob-Staging in 4.1 entsprechend |
| `postcommit`-Hooks laufen im Testmodus **nicht** (`TestCursor`: "post-commit hooks are ignored"); `mail_mail` weicht mit `modules.module.current_test` aus | `tests/test_cursor.py`, `base/tests/test_db_cursor.py:284-338`, `mail/models/mail_mail.py:681` | Veröffentlichen-Hook als einzeln aufrufbare Methode bauen; Fehlerinjektion in der Testinstanz mit echten Prozessen, nicht in `TransactionCase` |
| `models.UniqueIndex(…)` mit `WHERE` | `orm/table_objects.py:185-200` | löst `unique(path)` vs. Archivierung (5.5) sauber: `(path) WHERE active IS TRUE` |
| `@api.ondelete(at_uninstall=False)` statt `unlink()`-Override (Odoo warnt: Override verträgt sich nicht mit Modul-Deinstallation) | `orm/decorators.py:130` | Schutz "Scan löscht keine Zeilen mit Nutzerdaten" als `_unlink_except_…`; Bytes-Löschung aus `unlink()` heraus in Nachwirkung/Cron. Die Methode läuft bei **jedem** `unlink()`, auch mit `sudo`, nach `check_access`, außer beim Deinstallieren (`orm/models.py:4199-4216`): Ein Scan-Batch, der eine geschützte Zeile löschen will, bekommt einen `UserError` statt stillem Überspringen → der Scan filtert vorher |
| `@api.autovacuum` (tägliche GC-Methoden ohne eigenen Cron, mit Fortschritt `(done, remaining)`) | `orm/decorators.py:299` | Papierkorb-Purge, `scan_log`, Versionen, `write_journal`, `dirty`-Aufräumen als Autovacuum statt eigener Cron-Einträge. Läuft nur als Admin mit `cron_id`, einmal täglich, in zufälliger Reihenfolge; ein Fehler führt zu Rollback und Log, ohne `failure_count` (`base/models/ir_autovacuum.py`) → richtig für Aufräumen, ungeeignet für Zeitkritisches |
| `fields.Char(index='trigram')` (GIN, braucht `pg_trgm`) | `orm/fields.py:116`, `fields_textual.py:439-451`, Nutzung z. B. in `account` | Namenssuche (siehe Messung). `pg_trgm` ist im Live-Postgres verfügbar, aber nicht installiert. **Ohne die Extension wird `index='trigram'` still ignoriert** (`orm/registry.py:869-870`; `has_trigram` prüft nur `word_similarity`, `modules/db.py:192`); Odoo legt sie nur beim Anlegen einer DB an (`service/db.py:154`). Nach dem `pg_restore`-Umzug (15.5) ist sie nur vorhanden, wenn der Dump sie enthält, sonst manuell `CREATE EXTENSION pg_trgm`. Ist `--unaccent` aktiv, baut Odoo `unaccent(name) gin_trgm_ops` (`registry.py:885-891`) — abweichend vom gemessenen Index `name gin_trgm_ops`; Messung W2 dann neu. **→ 19.2:** Beim Anlegen einer DB durch Odoo entsteht `pg_trgm` bestätigt automatisch; Tower-Live hat sie; der Index greift auf der echten ORM-SQL (`rechnung` 267 → 0,3 ms) |
| `@route(readonly=True)` (RO-Cursor, bei Schreibversuch automatischer Retry mit RW) | `http.py:796, 2276-2298` | Leserouten (`tree`, `download`, `versions`, `zip_list`, `thumbnail`) ohne Schreib-/Konfliktlast; klein, risikoarm |
| `mail.mail`-Queue: `state`, `failure_type`, `scheduled_date`, `process_email_queue(batch_size)`, `auto_commit = not current_test` | `mail/models/mail_mail.py:69-100, 194-244` | Vorlage für `dirty`-/`pending`-Verarbeitung (Batches, Fehlerarten, Testschalter) |
| `attachment_indexation`: `_index_docx/_pptx/_xlsx/_opendoc/_pdf` (pdfminer) | `attachment_indexation/models/ir_attachment.py` | Office-Volltext nativ nutzbar statt eigene Extraktion (Feature-Idee B). **→ 19.2:** pdfminer ist im Image `odoo:19.0-hm` vorhanden (`pdfminer.six` 20260107 per pip über pdfplumber, überdeckt apt 20221105); `attachment_indexation` installiert und extrahiert DOCX und PDF |
| `portal.mixin`: `access_token`, `_get_share_url`, `action_share` | `portal/models/portal_mixin.py` | Alternative zum eigenen `share_token`; unsere Freigabe kann mehr (Ablauf, Log) — nur Prüfpunkt |
| `x_sendfile` greift nur für Dateien unter `<data_dir>/filestore` | `http.py:668-676` | Für Share-Dateien nicht nutzbar; große Downloads belegen im Threaded-Modus einen Thread (eigener Offload wäre Eigenbau) |

### 15.2 Messung: Präfix-Suchen und Rechte auf 1,39 Mio. Zeilen
**Ursache:** Die Live-DB hat die Kollation `en_US.utf8`; die Indizes auf `path` und `parent_path` sind normale
btrees. `LIKE 'Präfix%'` kann sie nicht nutzen und läuft als Parallel Seq Scan über alle Zeilen (auf der
Live-Tabelle per `EXPLAIN` bestätigt). Das betrifft alle `=like`-Domains: ACL-Regeln, `authz`,
`index_remove_tree`/`index_move_tree`/`index_trash_tree` und `child_of` (das Odoo intern als
`parent_path =like 'Pfad%'` umsetzt, `orm/domains.py:1800`).

**Aufbau:** Kopie der Live-Tabelle (1.388.768 Zeilen, nur Pfad-Spalten `id, name, path, folder_path, is_dir,
trashed, parent_id, parent_path, size`, dieselben btree-Indizes wie live) in eine eigene DB der Testinstanz
(danach gelöscht). Rechtsprädikat aus der echten Live-Regel: 7 Schutzordner, Nutzer ohne Zugriff
(`path <> P AND path NOT LIKE 'P/%'` je Ordner). Jede Abfrage zweimal, gemessen der zweite Lauf. Die Kopie ist
schmaler als die Live-Tabelle, Seq Scans sind hier also eher zu schnell; Live-Vergleich (breite Tabelle):
W1 742 ms, W4 512 ms, W5 518 ms.

| Abfrage | heute (btree) | + `varchar_pattern_ops` auf `path`, `parent_path` | + Feld `protected_folder_id` |
|---|---|---|---|
| W1 alle sichtbaren zählen (Vollscan) | 516 ms | 524 ms | 315 ms |
| W2 Namenssuche `ilike '%rechnung%'` + Rechte | 618 ms | 624 ms | 665 ms |
| W3 Ordnerliste (`folder_path =`) | 0,16 ms | 0,15 ms | 0,12 ms |
| W4 Unterbaum QM + Rechte | 279 ms | **8,8 ms** | 7,0 ms |
| W5 sehr großer Präfix (408k Zeilen, 29 %) | 295 ms | 282 ms (Planer bleibt beim Scan) | 302 ms |
| W6 `index_remove/move_tree` (kleiner Unterbaum) | 291 ms | **0,19 ms** | 0,14 ms |
| W7 `child_of` (Literal wie bei Odoo) | 266 ms | **6,4 ms** | — |
| W2 mit Trigram-Index auf `name` | 618 ms | — | **7,3 ms** (selten: 2,2 ms; sehr häufiger Begriff `.pdf`: 715 ms) |

Indexkosten: `path` 179 MB, `parent_path` 106 MB, Trigram-`name` 64 MB; Bau je ~15 s auf 1,39 Mio. Zeilen.

**Ergebnis:**
1. **`varchar_pattern_ops` auf `path` und `parent_path` bringt die großen Gewinne für alle Präfix-Operationen**
   (30× bis über 1.000×) bei geringem Aufwand. Native Definition: `models.Index("(path varchar_pattern_ops)")`.
2. **`protected_folder_id` (Plan in `archiv/int_filemanager_acl_perf_plan.md`) bringt danach nur noch wenig:** ca.
   200 ms von 520 ms im Vollscan (W1), sonst nichts Messbares — der Vollscan selbst bleibt. Empfehlung:
   zuerst nur die Indizes einführen, den Rest neu bewerten und den Feld-Umbau zurückstellen.
3. **Namenssuche:** ein Trigram-Index macht selektive Begriffe ~85× schneller (618 → 7 ms); sehr häufige
   Begriffe bleiben wie ein Scan.
4. **Ordnerlisten sind schon heute schnell** (0,16 ms); die spürbare Langsamkeit kommt von Suchen ohne
   Ordnerbezug und von Präfix-Operationen.

**Kollationsbefund und Entscheidung (2026-09-24):** Odoo legt seine eigenen Datenbanken mit
`LC_COLLATE 'C'` an (`service/db.py:146`, Kommentar im Code: "provides more useful indexes"). Die Live-DB
`odoodb` hat `en_US.utf8`, wurde also nicht von Odoo angelegt. Test im Wegwerf-Postgres (1,4 Mio. Zeilen, ein
**normaler** btree): `en_US.utf8` → Parallel Seq Scan 62,7 ms; `C` → Bitmap Index Scan **5,9 ms**. Bei C-Kollation
sind daher weder `pattern_ops`-Indizes noch ein `protected_folder_id`-Feld nötig; die vorhandenen Indizes auf
`path`, `parent_path` und `folder_path` greifen von selbst. `models.Index("(path varchar_pattern_ops)")` wäre
nativ deklarierbar (freie SQL-Definition, `orm/table_objects.py:125-180`), aber Odoo hat dafür keine eigene
Feld-Option (`index` kennt nur `btree`, `btree_not_null`, `trigram`).
**Kollation ist auch ein Korrektheitsargument (2026-09-25):** `_parent_store_update` verschiebt Teilbäume
per Bereichsvergleich `parent_path >= node.parent_path AND parent_path < left(node.parent_path,-1)||'0'`
(`orm/models.py:5039-5054`); der Code-Kommentar setzt voraus, dass `/` direkt vor `0` sortiert. Unter
Byte-Ordnung (C) ist das sicher, unter `en_US.utf8` (Live) hängt es von der glibc-Sortierung ab.
~~Vermutlich funktioniert es auf dem aktuellen Image, nicht getestet.~~ **Geprüft 2026-09-25 (→ 19.2):** Die
Literalprüfung liefert unter `en_US.utf8` **`false`**. Die Bereichsprüfung steht nur im **neueren** Core des
lokalen Repos; das laufende Image (Build 2026-08-17) nutzt noch `LIKE` und ist kollationsunabhängig. Mit
exakt dem neuen SQL auf einer `en_US`-Spalte aktualisiert das Verschieben eines Ordners mit 35 Knoten nur den
Ordner selbst, **34 Nachkommen behalten einen falschen `parent_path`**. Ein Image-Update auf einer
`en_US`-DB zerstört damit bei jedem Ordner-Verschieben den Baum. **Die C-Umstellung muss vor jedem
Image-Update erfolgen.**
**Entscheidung des Nutzers:** Da die Odoo-Instanz noch nicht produktiv ist, wird die DB sauber auf
**C-Kollation** umgestellt (Weg B, Odoo-Standard) statt Zusatzindizes zu legen.
Folgen und Aufgaben: (1) Umzug per Dump/Restore in eine neue DB mit `LC_COLLATE 'C'` (`template0`), alte DB
bleibt bis zur Abnahme als Rückfall; vorher Probelauf auf der Testinstanz, die Kopie mit `odoo neutralize`
entschärfen (Mail-/Cron-Einstellungen). (2) **Sortierung:** `_order = "is_dir desc, name"` sortiert bei C
byteweise (`B` < `a`, Umlaute nach `z`) — für einen Dateimanager nach Explorer-Vorbild unerwünscht;
Gegenmaßnahme: nativer Hook `_order_field_to_sql` + ICU-Kollation + passender Index (Abschnitt 15.5), kein
zusätzliches Sortierfeld.
(3) Sortier- und Indexverhalten nach dem Umzug an der echten ORM-SQL messen.

### 15.3 Konsequenzen für das Konzept
- Teilbaum-Operationen (4.2), Abgleich-Cron und Papierkorb (5.3, 5.5) setzen die Präfix-Indizes voraus;
  ohne sie kostet jedes Verschieben/Löschen eines Ordners auf dem Live-Bestand ~0,3–0,5 s Scan.
- Upload-/WebDAV-Routen: `max_content_length` und Streaming (4.1), sonst bleiben große Dateien außen vor.
- Testdesign: Veröffentlichen-Hook einzeln aufrufbar, Fehlerinjektion in echten Prozessen (Abschnitt 10).
- 5.5: partieller Unique-Index; Löschschutz per `@api.ondelete`; Aufräumen per `@api.autovacuum`.
- Optional: `readonly=True` auf Leserouten, `attachment_indexation` für Office-Volltext, `mail.mail` als
  Queue-Vorlage.

### 15.4 Nicht gemessen / Grenzen
Die ORM-erzeugte SQL im echten Ablauf (die Regelstruktur wurde nachgebaut, nicht über die ORM ausgeführt),
Schreibkosten der zusätzlichen Indizes, andere Rollen (Nutzer mit Zugriff nur einmal in W1), Verhalten unter
Last, `pg_trgm`-Installation durch Odoo, Verfügbarkeit von pdfminer, `mail.thread`-Tracking als Audit-Baustein
und Enterprise-Module (nicht vorhanden). **→ 19.2:** ORM-SQL, `pg_trgm`, pdfminer und Tracking sind auf Tower
geprüft; offen bleiben Schreibkosten der Indizes, Last und Enterprise.

### 15.5 Probelauf C-Kollation (Testinstanz, 2026-09-24)
**Ablauf:** neue DB `odoodb_c` (`CREATE DATABASE … ENCODING 'unicode' LC_COLLATE 'C' TEMPLATE template0`, wie Odoo
selbst) im Test-Postgres; Dump direkt von der Live-DB gestreamt (`pg_dump -Fc | pg_restore`, nur lesend):
**5,6 min, fehlerfrei**, 1.388.768 Zeilen, Größe **2,2 GB** (Live 3,8 GB; frisch aufgebaut ohne Aufblähung).
Danach Watcher-Parameter aus und `odoo neutralize` (aktive Crons 46 → 1, `database.is_neutralized = true`).
Gemessen über die echte ORM mit einem Nicht-Admin-Nutzer (`int_filemanager.group_filemanager_user`, alle
7 Schutzordner-Regeln aktiv), zweiter Lauf:

| Abfrage (ORM) | en_US.utf8 (Messung 15.2 auf Kopie / Live) | **C-Kollation, ORM** | Plan |
|---|---|---|---|
| W3 Ordnerliste | 0,16 ms | 1,3 ms | Index |
| W4 Unterbaum QM (`=like`) + Rechte | 279 ms (Live 512 ms) | **12,5 ms** | Index Scan `path_index` |
| W6 `index_remove/move_tree` klein | 291 ms | **1,0 ms** | Bitmap Heap Scan |
| W7 `child_of` | 266 ms | **4,0 ms** | Index Scan `parent_path_index` |
| W1 alle sichtbaren zählen | 516 ms (Live 742 ms) | 554 ms | Seq Scan (Vollscan mit `NOT LIKE`) |
| W2 Namenssuche `ilike` | 618 ms | 680 ms | Seq Scan (Trigram-Index wäre die Lösung, 15.2) |
| W5 sehr großer Präfix (433k Zeilen) | 295 ms | 439 ms | Scan (29 % der Tabelle) |

Die vorhandenen btree-Indizes greifen bei C-Kollation ohne Zusatzindex, auch mit den Rechte-Regeln. Vollscans
(W1, W2, W5) bleiben unverändert; dafür gilt weiter: Trigram-Index für Namen, und Suchen möglichst mit
Ordnerbezug.

**Sortierung (Nachteil, an echten Namen bestätigt):** `_order = "is_dir desc, name"` sortiert byteweise:
`… 'PDF', 'Papierkorb', 'Personal'`, `'AVL', 'Akiem', 'Alphitan Germany'`. `order='lower(name)'` ist in Odoo
**nicht erlaubt** (`UserError: Invalid "order" specified`) — eine Funktion im `_order`-String geht also nicht.
**Native Lösung (im Core gelesen und über die ORM getestet, kein `name_sort`-Feld nötig):**
1. **Offizieller Hook `_order_field_to_sql(alias, field_name, direction, nulls, query)`** (`orm/models.py:5268`,
   lokal `5275`; überschrieben in `stock`, `project`, `hr_recruitment`, `res_device`). Für `name` liefert er
   `SQL("%s COLLATE %s %s %s", sql_field, SQL.identifier('fm_natural'), direction, nulls)`; `_order` bleibt
   `"is_dir desc, name"`. Der Core selbst nutzt nirgends `COLLATE`. **Der Override muss den Ausdruck wie die
   Basis in `query._order_groupby` eintragen** (`orm/models.py:5332`), sonst scheitert Gruppierung nach Ordner
   (`parent_id`, many2one mit Comodel-Order) vermutlich mit "must appear in GROUP BY" (aus dem Code
   abgeleitet, nicht getestet).
2. **ICU-Kollation** in PostgreSQL (Image `postgres:17` hat 871 ICU-Kollationen):
   `CREATE COLLATION fm_natural (provider = icu, locale = 'de-u-kn', deterministic = true)` — Groß/Klein und
   Umlaute wie im Explorer, natürliche Zahlenfolge (`datei2` < `datei10`). Odoo verwaltet keine Kollationen:
   Anlegen in `_auto_init` vor `super()` bzw. `pre_init_hook`; einfachere Variante ohne eigene Kollation:
   eingebaute `de-x-icu` (ohne natürliche Zahlenfolge). Voraussetzung: PostgreSQL mit ICU.
3. **Passender Index** per `models.Index` — er muss exakt den Ausdruck der ORM tragen (die ORM wickelt
   Booleans in `COALESCE(is_dir, FALSE)`): `((COALESCE(is_dir, FALSE)) DESC, name COLLATE fm_natural)`, 42 MB, Bau 6 s.
**Messung (ORM-SQL, Kopie mit C-Kollation):** ORDER BY-Fragment der ORM
`COALESCE("is_dir", FALSE) DESC, "name" COLLATE "fm_natural"`; ungefilterte Top-80-Liste ohne Index
448 ms (Admin) / 833 ms (Nicht-Admin mit Rechten), **mit Index 0,42 / 0,44 ms ohne Sort-Schritt**; Ordnerliste
0,13 ms. Sortierung an echten Namen: `Papierkorb, PDF, Personal`; `AFS-Federhenn, Akiem, Alphitan Germany,
Alstom, Arinko, Augsburger Verkehrsbtriebe, Auler Handkühlgerät, AVL`.
`_read_group` läuft nur bei Gruppierung nach many2one mit Comodel-Order über `_order_to_sql`
(`orm/models.py:2200-2207`, im lokalen Core 2026-09-25 gelesen); Gruppierung direkt nach `name` sortiert
**nicht** mit `fm_natural`.
Ungeprüft bleibt das Verhalten in der Oberfläche (Spaltenkopf-Sortierung).
**Nicht Teil des Probelaufs:** Server/UI auf der Kopie (nur `odoo shell`), Schreibkosten, Live-Umschaltung.

---

## 16. Eigenbau-Inventur: native Entsprechungen im Odoo-Core (tieferer Durchgang, 2026-09-24)

Anlass: Mehrfach hatte zuerst "kein Bordmittel" gestanden, das sich bei genauerem Suchen als falsch
erwies (Sortierung, `unique(path)`, Präfix-Suchen). Dieser Abschnitt geht die Eigenbau-Teile des Konzepts und
des heutigen Codes gezielt gegen den Core (Container `Odoo19`, Odoo 19) durch.

### 16.1 Neue Funde
| Eigenbau (Konzept/Code) | Nativ gefunden | Fundstelle / Prüfung | Konsequenz |
|---|---|---|---|
| **Watch-Buchhaltung** im Watcher (`wd_to_path`, Ordner-Umschreiben, `moved_from` je Batch, Watches nach `.trash`) | **`watchdog` 3.0.0** ist im Image installiert. Der Core nutzt es nur als **Fallback** für den Auto-Reload im Entwicklermodus, wenn das Paket `inotify` fehlt (`service/server.py:29-50`, `FSWatcherWatchdog`, `Observer.schedule(..., recursive=True)`); es steht in **keiner** Abhängigkeitsliste des Cores (`requirements.txt`, `setup.py`, `debian/control`). Daher: im Manifest unter `external_dependencies` deklarieren, Version pinnen, Image-Build muss es enthalten (Korrektur 2026-09-25). Die Bibliothek führt `_wd_for_path`/`_path_for_wd`, schreibt Watches bei Moves um und merkt Move-Kennungen **über Lesevorgänge hinweg** (`_moved_from_events`); der `InotifyBuffer` paart `MOVED_FROM`/`MOVED_TO` mit 0,5 s Verzögerung | `watchdog/observers/inotify_c.py:172-182, 220-225, 322-333`; `inotify_buffer.py:28-110` | Punkt 1 des minimalen Watchers (5.2, "Watches pflegen") entfällt weitgehend; das Batch-Grenzen-Problem (B11) ist in der Bibliothek gelöst. **Nicht abgedeckt:** Überlauf (`IN_Q_OVERFLOW` nur als Konstante, `inotify_c.py:70`) — Rescan, Neustart-Abgleich und Herzschlag bleiben Eigenbau. ~~Ungeprüft: gevent, Last, `FileClosedEvent`~~ **→ 19.2:** `python3-watchdog` kommt aus dem offiziellen Image `odoo:19.0` (apt), nicht aus Odoos Abhängigkeiten. `FileClosedEvent` wird bei `IN_CLOSE_WRITE` erzeugt. **Unter gevent-Monkeypatching blockiert der Observer den ganzen Prozess** (für `workers>0` so unbrauchbar). Threaded: 30.000 Dateien in 4,4 s bei langsamem Handler ohne Verlust. Den Überlauf **verwirft die Bibliothek stillschweigend** (`inotify_c.py:320`) |
| **ACL-Regeltext-Generator** (`acl_rules.py`, ~250 Zeilen: Textbau, Platzhalter, `rebuild_rules`, Selbsttests) | **Regel-Domain darf zur Auswertungszeit abfragen:** `ir.rule`-Kontext enthält `user` (= `env.user`), das Regelergebnis wird pro Nutzer gecacht. Im Test lieferte `safe_eval("user.env['int_filemanager.protected_folder'].search_count([])", …)` den Wert 7 | `base/models/ir_rule.py:38-52` (`_eval_context`), `:138-141` (`ormcache` auf `_compute_domain`); Test in `odoodb_c` | Eine kurze Regel könnte die Schutzordner selbst abfragen statt eines generierten Textes. **Cache (2026-09-25 im Core bestätigt, sicherheitsrelevant):** `_compute_domain` ist per `ormcache` (Schlüssel `uid, su, model, mode, Kontextwerte`) gecacht (`ir_rule.py:138`) und wird nur bei Änderungen an `ir.rule` selbst geleert (`registry.clear_cache()`, Zeilen 187/195/205). Änderungen an `protected_folder` wirken sonst erst nach einem Cache-Clear → beim Anlegen/Ändern/Löschen von Schutzordnern **explizit** `registry.clear_cache()` aufrufen. Der Cache ist nur aktiv, wenn `xml` nicht in `dev_mode` steht (`tools.conditional`), Tests im Dev-Modus verdecken das Problem. **Offen:** `@api.private` gegen RPC-Aufruf, Selbsttests, die `NOT LIKE`-Struktur bleibt (Vollscans, 15.2). ~~Ungeklärt (2026-09-25): Regelkontext ohne `sudo`, `AccessError` für Nicht-Admins möglich.~~ **Geklärt (→ 19.2):** `env.user` ist in Odoo 19 immer `sudo` (`orm/environments.py:213`, "current user - sudoed"). Die Abfrage läuft daher auch für Nicht-Admins **ohne** `AccessError` und ohne `user.sudo()`; live mit einem Nutzer ohne Leserecht auf `protected_folder` getestet. Der **Cache-Befund ist live bestätigt**: Ein neuer Schutzordner ohne `ir.rule`-Schreibvorgang bleibt für den Nutzer unsichtbar, bis `registry.clear_cache()` läuft. Nur Machbarkeit geprüft, nicht umgesetzt |
| **`trashed` (eigenes Boolean)** | **Natives `active`**: `_search` filtert Archiviertes automatisch, auch für `sudo()`; ein `active`-Blatt in der Domain oder `active_test=False` hebt das gezielt auf | `orm/models.py:5371-5376` (`_active_name`, `active_test`) | **Befund im Modul:** 47 `search()`/`search_count()`-Aufrufe, **0** mit `trashed`-Bezug; die Regel `rule_file_trash_visibility` greift nur für Nicht-`sudo`, Watcher/Scan/Index-Funktionen laufen mit `sudo` — B1 ("Scan löscht Papierkorb") ist genau diese Auslassung. Mit `active` entfällt die ganze Fehlerklasse |
| **`PIL` direkt** für Thumbnails/Vorschau (`mediameta.py`) | `odoo.tools.image`: `image_process`, `ImageProcess`, `image_fix_orientation`, `binary_to_image` (mit Auflösungsgrenze) | `tools/image.py:60, 295, 391, 428` | niedrige Priorität; bei nächster Änderung an `mediameta.py` prüfen |

**`trashed` → `active` (Umfang):** 5 Dateien, 48 Stellen (`index_utils.py`, `models/filemanager_file.py`,
`security/security.xml`, `views/filemanager_file_list_view.xml`, `views/filemanager_trash_views.xml`).
Nötig: Migration (`active = false` wo `trashed`), Papierkorb-Ansicht mit explizitem `[('active','=',False)]`,
Sichtbarkeitsregel für eigene Einträge, `_cron_purge_trash` mit `active_test=False`. `unique(path)` bleibt
unproblematisch, weil Papierkorb-Pfade unter `.trash/` liegen. Alternative Minimal-Hotfix für B1: `trashed`-Filter
im Scan; er behebt nur diese eine Stelle.

### 16.2 Gesamtübersicht: Eigenbau → nativ (Stand dieses Konzepts)
| Bereich | Nativer Baustein | Abschnitt |
|---|---|---|
| Sortierung nach Namen (Explorer-Reihenfolge) | `_order_field_to_sql`-Hook + ICU-Kollation + `models.Index` | 15.5 |
| Präfix-Suchen (`=like`, `child_of`) | DB-Kollation `C` (Odoos Standard, `service/db.py:146`) | 15.2, 15.5 |
| Namenssuche (`ilike`) | `fields.Char(index='trigram')` | 15.1, 15.2 |
| `unique(path)` bei Archivierung | `models.UniqueIndex(... WHERE ...)` | 15.1 |
| Löschschutz statt `unlink()`-Override | `@api.ondelete(at_uninstall=False)` | 15.1 |
| Tägliches Aufräumen | `@api.autovacuum` | 15.1 |
| Papierkorb-Filterung | `active` (`_search`) | 16.1 |
| Nebenwirkung nach Commit, Retry-Sicherheit | `cr.postcommit` (verwirft bei Rollback) | 3, 13.1 |
| Zeilensperren | `lock_for_update` / `try_lock_for_update` | 3, 13.1 |
| Externen Zustand abgleichen | `need_sync`-Muster (Kalender-Sync) | 3, 5 |
| Abgleich anstoßen und in Batches | `cron._trigger()`, `_commit_progress` | 3, 13.1 |
| Warteschlange (`dirty`/`pending`) | `mail.mail`-Muster (`state`, `failure_type`, `scheduled_date`, Batches) | 15.1 |
| Watcher-Buchhaltung, Move-Paare | `watchdog` (im Image, vom Core genutzt) | 16.1 |
| Rechte-Regeln | dynamische `ir.rule`-Domain (`user.env[...]`) | 16.1 |
| Office-/PDF-Text für die Suche | `attachment_indexation` | 15.1 |
| Freigabe-Links | `portal.mixin` (Prüfpunkt) | 15.1 |
| Leserouten | `@route(readonly=True)` | 15.1 |
| Bilder | `odoo.tools.image` | 16.1 |

### 16.3 Bleibt Eigenbau (nach gezielter Suche kein Bordmittel)
Überlauf-Behandlung, Neustart-/Nachholabgleich und Herzschlag des Watchers; Abgleich Platte ↔ DB
(`reconcile_path`) und Rename-Identität; Ordner-Modi; atomares Veröffentlichen auf den Share (Temp-Datei,
`os.replace`, fsync, No-Replace per `link`+`unlink` bzw. `mkdir`+`rename`); WebDAV-Server für "Lokal öffnen";
OCR und Werteerkennung (Odoo-Community hat keine OCR).

### 16.4 Suchraster vor jedem "kein Bordmittel"
1. `orm/decorators.py`, `orm/table_objects.py`, `http.py` (Route-Parameter), Feld-`index`-Optionen.
2. Überschreibungs-Beispiele der Hooks in `stock`/`project`/`account`/`mail` (`grep -rn "def <hook>" addons`).
3. `pip list` im Image: Bibliotheken, die der Core selbst nutzt.
4. Odoos eigene Defaults und Anlage (`service/db.py`, `sql_db.py`) als Ursache statt Symptom.
5. Test-Infrastruktur (`tests/test_cursor.py`, `base/tests/test_db_cursor.py`).
6. Kurz empirisch prüfen (Wegwerf-Container, Testinstanz), bevor "geht nicht" behauptet wird.

### 16.5 Nicht geprüft
JS-Seite der Oberfläche (native Komponenten), `mail.thread`-Tracking als Audit-Baustein, ZIP-Behandlung,
`bus.bus` im Detail, Umstellung von `trashed` auf `active` in der Praxis, `watchdog` unter Last und gevent.
**→ 19.2:** Tracking und `watchdog` sind geprüft; bei `trashed` → `active` wurde nur der Umfang bestätigt (weiterhin
5 Dateien, 48 Stellen), die Umstellung selbst ist nicht ausprobiert.

---

## 17. Native Medienarchitektur: Bilder, Vorschau, Bearbeitung (Zielbild für den Umbau)

Grundlage: Umbau-Regel 7 (Abschnitt 1). Gelesen und teils getestet im Core (`Odoo19`): `orm/fields_binary.py`,
`tools/image.py`, `base/models/image_mixin.py`, `base/models/ir_binary.py`, `web/controllers/binary.py`,
`html_editor/controllers/main.py`, `html_editor/static/src/utils/image_processing.js`, `html_editor/__manifest__.py`.

### 17.1 Fundamentaler Befund (Ursache statt Symptom)
Unser Modell benutzt bereits das native `fields.Image` (`thumbnail` 320 px, `preview` 1920 px, `attachment=True`,
`models/filemanager_file.py:273, 279`). Der Eigenbau davor und danach macht das native Feld wirkungslos:
`mediameta._extract_image` dekodiert mit PIL, `_resized_jpeg` verkleinert selbst (JPEG Q85, EXIF geht verloren) und
schreibt fertige Base64-JPEGs in beide Felder; `/int_filemanager/thumbnail` decodiert sie im RAM wieder. Das
native Feld sollte genau das leisten: **Orientierung, Verkleinerung, Qualität, Format und Auflösungsgrenze
(50 MP)** (`Image.write` → `image_process`, `fields_binary.py:246`). Das sichtbare Symptom (Hochformatfotos in
der Kachelvorschau gedreht) ist Folge dieser Vorverarbeitung, **nicht** ein fehlender EXIF-Aufruf.
**Einschränkung (Core 2026-09-25 gelesen):** `ImageProcess` korrigiert die Orientierung zwar immer
(`tools/image.py:103`), zählt das aber nicht als Operation; ohne Verkleinern gibt `image_process` die Quelle
**unverändert** zurück (`image.py:142`). Bilder unter 320 px (Thumbnail) bzw. 1920 px (Preview) behalten
also unrotierte Pixel samt EXIF-Tag und erscheinen nur richtig, weil Browser den Tag anwenden. Erst
verkleinerte Bilder werden gedreht und ohne EXIF gespeichert. **WebP** wird vom Feld nie skaliert, nur auf die
Auflösung geprüft (`fields_binary.py` `_image_process`, `image.py:84-91`): das `thumbnail` wäre dort das
Original in voller Größe. **Korrektur (→ 20.1, live geprüft):** Im Odoo-Prozess scheitert WebP schon vorher mit
`UnidentifiedImageError`, weil `odoo/tools/image.py:27-28` Pillow auf die Formate aus `Image.preinit()` beschränkt
(BMP, GIF, JPEG, PPM, PNG). Auf Tower-Live stehen alle 22 WebP-Dateien auf `meta_state=error`. Kleine Bilder mit EXIF
und das Drehen großer Bilder sind wie beschrieben bestätigt; über 50 MP gibt es einen `UserError`. Es wird
deshalb nicht in `mediameta` nachgebessert, sondern durch den Umbau beseitigt.

### 17.2 Ist gegen nativ
| Aspekt | heute | nativ (Zielbild) |
|---|---|---|
| Felder | `thumbnail` und `preview` unabhängig, je von uns gefüllt | **`image.mixin`-Muster** (`base/models/image_mixin.py`): eine Quelle (`fields.Image(max_width=1920)`) und abgeleitete Größen als `fields.Image(related=…, max_width=…, store=True)`; Schreiben der Quelle erzeugt alle Größen |
| Erzeugung | PIL-Decode, 2× `_resized_jpeg`, Base64 | Originaldatei **Base64-kodiert** in das **Quellfeld** schreiben (`_image_process` ruft `b64decode`, `fields_binary.py:322`); Odoo verarbeitet |
| Auslieferung | `/int_filemanager/thumbnail?path=…`: pfadbasiert, eigene `authz`-Prüfung, `b64decode` im RAM, fester Typ `image/jpeg`, `max-age=3600`, kein ETag | **`/web/image/int_filemanager.file/<id>/thumbnail`** (`web/controllers/binary.py:165-179`): `ir.binary._find_record` prüft `check_access("read")` — unsere Rechteregeln greifen ohne Eigencode; Streaming aus dem Filestore; ETag/Last-Modified und `unique=` (Cache), Platzhalter; `_can_return_content` ist in der Basis `False` (`orm/models.py:5868`), unsere Regeln greifen also. Der `access_token` ist ein HMAC je Datensatz und Feld (`limited_field_access_token(record, field, scope="binary")`, `ir_binary.py:50`), **kein** Freigabe-Token wie bei `portal.mixin`, und nur **14 bis 42 Tage** gültig (`tools/misc.py:1866ff`); Freigabe-Links mit eigener Ablauflogik müssten ihn selbst erzeugen oder eine eigene Route nutzen |
| Anzeige | JS baut Pfad-URLs | URLs aus `record.id` (Kanban-Helfer `getImageSrcFromRecordInfo`, `web/static/src/views/kanban/kanban_record.js:119`, baut `imageUrl(model, id, field, {unique: write_date})`; `kanban_arch_parser.js:123` ist nur ein Regex, der `write_date` nachlädt). Das Cache-Busting hängt also am `write_date` der Datei-Zeile und greift nur, wenn die Vorschau per ORM geschrieben wird, nicht per SQL. `FileViewer` bleibt (bereits nativ) |
| Bearbeiten | nicht vorhanden | Client: `activateCropper` (siehe 17.3); Server: `odoo.tools.image` (`image_process`, `crop_resize`, `image_quality`, `image_fix_orientation`) |
| Lebenszyklus | `meta_state` + Cron | bleibt: abgeleitete Assets sind Zustand **pro Inhaltsrevision**, Regeneration im Abgleich-Cron (Abschnitt 5) |

### 17.3 Zielbild
1. **Modell:** `preview` wird die Quelle (`fields.Image(max_width=1920, max_height=1920, attachment=True)`),
   `thumbnail` wird `fields.Image(related="preview", max_width=320, max_height=320, store=True)`. Das
   `image.mixin` selbst wird nicht übernommen (5 Größen = 5 Attachments je Bild), nur sein Muster.
2. **Erzeugung:** Der Meta-/Abgleich-Cron liest die Originaldatei (Grenze `meta_max_bytes_image`) und schreibt
   **nur** das Quellfeld mit den Originalbytes (Base64-kodiert). Ein `UserError` (Auflösung über 50 MP, ungültiges Bild) setzt
   `meta_state='error'`. Veraltungsschutz: Größe/mtime (bzw. `content_sha256`) vor und nach dem Lesen vergleichen;
   nur schreiben, wenn die Revision unverändert ist (Testliste "veraltete OCR-/Hash-Ergebnisse", Abschnitt 10).
3. **Auslieferung:** ausschließlich `/web/image/…` mit Datensatz-ID; Cache-Busting per `unique`. Ohne Vorschau:
   nativer Platzhalter; das Original liefert weiter die Download-Route (`http.Stream`). Die Route
   `/int_filemanager/thumbnail` entfällt.
4. **Bearbeiten (Crop, Drehen, später Filter):** OWL-Dialog mit **`activateCropper(image, aspectRatio, dataset,
   {onReady})`** aus `@html_editor/utils/image_processing` (eigenständig exportiert, lädt das Bundle
   `html_editor.assets_image_cropper` bei Bedarf; enthält Cropper.js **und** `webgl-image-filter.js`,
   `html_editor/__manifest__.py:96-99`; `html_editor` ist `auto_install` mit nur `base`, `bus`, `web`). Der
   Dialog muss das **Original** laden (Download-Route), nicht `/web/image/…/preview`: `activateCropper`
   arbeitet mit dem `src` des übergebenen `<img>`, Odoos eigener Ablauf schneidet ebenfalls das Original
   (`image_post_process_plugin.js:97-115`); mit der 1920-px-Vorschau wäre das Ergebnis auf 1920 px begrenzt. Ergebnis über
   `getCroppedCanvas().toDataURL(mimetype, 0.92)` (Odoo-Standardqualität 92) an **unsere Schreibroute**
   (Konzept 4.1: Blob-Staging, DB-Commit, Hook veröffentlicht). Das **Original bleibt als Version** erhalten —
   dasselbe Prinzip wie Odoos `modify_image` (`html_editor/controllers/main.py:406`: Kopie mit
   `original_id`, Original nie überschrieben), aber DB-geführt und mit unserer Versionierung. "Als Kopie
   speichern" ist optional. Was `odoo.tools.image` **nicht** kann (freies Drehen, beliebiger Zuschnitt, Filter), läuft
   im Browser; die Filter-Pipeline des Editors (`ImagePostProcessPlugin`) ist nicht eigenständig nutzbar,
   `WebGLImageFilter` direkt schon. GIF/SVG werden nicht transformiert.
5. **Entfällt:** `mediameta._resized_jpeg`, der PIL-Decode für Vorschauzwecke, Route und Base64-Handling in
   `controllers/main.py`, eigene Cache-Header.
6. **Bleibt Eigenbau (kein Bordmittel gefunden):** PDF-Seitenzahl und PDF-Vorschau (Community rendert PDF nicht
   serverseitig zu Bildern), Audio-Tags, EXIF-Aufnahmedatum (`taken_at`), Extraktionsgrenzen je Medientyp.
   Breite/Höhe: prüfen, ob `ImageProcess`/`get_image_size` sie liefert.

### 17.4 Migration
Bestand nicht umbauen, sondern **neu ableiten**: Felder umstellen (Modell-Update), betroffene Bilddateien auf
`meta_state='pending'` setzen, der Cron erzeugt Quelle und abgeleitete Größe neu (Backfill in Batches mit
`_commit_progress`); danach Frontend-URLs auf `/web/image/…`, dann Route und `_resized_jpeg` löschen.
Zu prüfen: dass die generierte Leserechte-Regel für `check_access("read")` in `ir.binary` greift (Schutzordner),
und der `access_token`-Weg für externe Freigaben. **→ 19.2:** Die Regel greift (Nicht-Admin: Schutzordner-Bild →
Platzhalter bzw. 404, offenes Bild → JPEG); der `access_token`-Weg ist weiter offen.

### 17.5 Abnahme
EXIF-Orientierungen 1–8, **auch für kleine Bilder unter 320/1920 px** (bleiben unverändert, Anzeige hängt am Browser); WebP (Vorschau in voller Größe, Limit oder akzeptieren); Bild über 50 MP (`meta_state='error'`, kein Absturz); Nicht-Admin auf Schutzordner
(kein Bild, Platzhalter); ETag/`304`; Range; Bearbeiten → Original als Version vorhanden, Vorschau neu erzeugt,
veralteter Cron-Lauf überschreibt keine neuere Revision; GIF/SVG unverändert; Backfill-Lauf ohne Fehler auf der
Testinstanz.

### 17.6 Nicht geprüft
Prototyp (`related` + `store` bei sehr vielen Zeilen, Speicherbedarf: zwei Attachments je Bild); Verhalten von
`kanban_image` in Liste/Dialog; Canvas-/Speichergrenzen im Browser bei sehr großen Bildern; Anzahl der Bilddateien
im Bestand; `attachment_indexation` ist auf Live nicht installiert. **→ 19.2:** Bestand Tower: 209.429 Bilddateien
(davon 187.914 JPG mit 565 GB, 15.204 PNG, 5.371 GIF, 42 TIFF, 22 WebP; gezählt ohne Unterscheidung der
Groß-/Kleinschreibung), 209.390 Vorschau-Attachments, Filestore 3 GB.

---

## 18. Gegenprüfung gegen den lokalen Odoo-Quellcode (2026-09-25)

Geprüft wurden die Odoo-Aussagen der Abschnitte 3, 15, 16 und 17 gegen `GitHub\odoo` (Odoo 19.0, HEAD
`8d05257d`, 10. Aug 2026). Das Container-Image kann eine leicht andere Revision haben (z. B.
`_order_field_to_sql` lokal `models.py:5275`, im Doc 5268); Zeilennummern können um einige Zeilen abweichen.

**Korrigiert (eingearbeitet):** Advisory-Lock im Core (Abschnitt 3), `watchdog` nur optionaler Fallback
(16.1).

**Ergänzt (eingearbeitet):** Upload-Body bei `retrying` (4.4), Trigger-Volumen (5.2), doppelte Bedeutung von
`active` (5.5), `ir.rule`-Cache (16.1), EXIF bei kleinen Bildern und WebP (17.1, 17.5), Bedeutung des
`access_token` (17.2), `_read_group`-Sortierung (15.5).

**Zweiter Durchgang (2026-09-25, unabhängig, zusätzlich `mail`, `google_calendar`, `html_editor`,
`attachment_indexation`, `web`, `onlyoffice_odoo`), direkt in den Abschnitten korrigiert:** Reihenfolge
Zeile/Blob und GC-Race (4.1, einzige inhaltlich falsche Aussage), Trigger-Autovacuum nur für inaktive Crons
(5.2), Debounce/Selbst-Trigger und `_check_modules_state` (5.3), Retry-Grenzen und `LockError` (4.4, 6),
`@api.ondelete`/Autovacuum-Semantik (15.1), `pg_trgm`-Voraussetzung und `unaccent`-Index (15.1),
Kollation als Korrektheitsargument für `_parent_store_update` (15.2), `_order_groupby` im Sortier-Hook und
`_read_group`-Reichweite (15.5), `user`-Kontext der Regel-Domain ohne `sudo` (16.1), Base64, Original statt
Vorschau beim Bearbeiten, Kanban-Helfer, `access_token`-Gültigkeit (17), ONLYOFFICE-Callback (3).

**Bestätigt:** `postcommit` wird bei `rollback()` verworfen, Savepoint-Rollback leert nur `precommit`;
`retrying` 5 Versuche; Cron nicht in `retrying`; `TestCursor` ignoriert `postcommit`; `_trigger` minutengenau
und meldet per `postcommit`; `_commit_progress` committet außerhalb eines Crons nur; Fehlerkonstanten 5 / 7
Tage; `lock_for_update` (`SKIP LOCKED`, `LockError`); Filestore-Ablauf (`create` → `_file_write`, nicht
atomar, Kollisionsprüfung, `_mark_for_gc`, Autovacuum-GC, `LOCK` als erstes Statement); `models.Index` /
`UniqueIndex` mit `WHERE`; `@api.ondelete`, `@api.autovacuum`, `@api.private`; `index='trigram'`;
`_order_field_to_sql` (Overrides in `stock`, `project`, `hr_recruitment`, `res_device`); `LC_COLLATE 'C'`
(`service/db.py:146`); `active_test` auch für `sudo()`; 128-MiB-Limit, ICP-Override, Route-Override;
`readonly=True` mit RW-Fallback; `x_sendfile` nur unter `filestore`; `image.mixin`-Muster, 50-MP-Grenze,
`activateCropper` mit Bundle, `modify_image` mit `original_id`; `attachment_indexation._index*`;
`google_sync`-Muster (`need_sync`, `after_commit`, Archivieren statt Löschen); Bus-, Webhook- und
Mail-`postcommit`-Belege.

**Lokal nicht prüfbar:** Interna der `watchdog`-Bibliothek, alle Live- und Testinstanz-Messungen, der
Eigencode B1–B15, Abweichungen zwischen Container-Image und lokalem HEAD. Der ONLYOFFICE-Callback liegt im
Repo (`onlyoffice_odoo`) und wurde gelesen (Abschnitt 3). Aus PostgreSQL-Semantik abgeleitet und nicht
ausgeführt: `SKIP LOCKED` unter `REPEATABLE READ` (4.4), Byte-Ordnung von `parent_path` unter `en_US.utf8`
(15.2).

**→ 19:** Die Punkte "Interna der `watchdog`-Bibliothek", "Abweichungen Image/lokaler HEAD", `SKIP LOCKED` und
Byte-Ordnung sind inzwischen live geprüft.

---

## 19. Live-Prüfung der offenen Punkte auf Tower (2026-09-25)

### 19.1 Aufbau und Grenzen
- **Server:** zweiter Unraid-Server "Tower" (anderer Standort als HM-SRV). Tower-Live: Container `odoo` / `odoo_db`
  (PostgreSQL **16**, DB bereits mit **C-Kollation**, `pg_trgm` installiert), 427.914 Indexzeilen, 1 Schutzordner,
  1 interner Nutzer, Wurzel `/mnt/user/Daten` (Array, 1,8 TB, **keine** CIFS-Freigaben). Die Zahlen sind also nicht
  1:1 auf HM-SRV übertragbar.
- **Testumgebung, isoliert:** `fmtest_pg` (postgres:16) und `fmtest_odoo` (Image `odoo:19.0-hm` wie Live, Repo-Stand
  `master` `aef0b4d`, Modul 1.15.0, `workers=0`, Watcher aktiv), eigenes Docker-Netz, Port 8070.
  - DB `fmtest`: frisch von Odoo angelegt (`LC_COLLATE C`, `LC_CTYPE en_US.utf8`), Wurzel `/mnt/user/test/fmroot`
    (shfs auf dem Cache-Pool).
  - DB `fmreal`: `pg_dump` der Tower-Live-DB (nur lesend, Restore 97 s, 523 MB), Filestore kopiert (3 GB, 8 min),
    `odoo neutralize`, Watcher aus, Wurzel = Live-Daten **schreibgeschützt** (`/mnt/live-ro:ro`).
  - SMB: temporäre Freigabe `fmtest` (Samba 4.23.2, Optionen wie `Daten`: Gast, `catia fruit streams_xattr`) auf
    der Testwurzel, Zugriff von Windows 10 (Laufwerk T:). Ein zweiter, reiner Ereignis-Logger
    (`watchdog.observers.inotify_c.Inotify`) protokollierte alle rohen inotify-Ereignisse.
- **Live-Instanz:** nur lesende Abfragen, ein `pg_dump` und lesende Verzeichnisdurchläufe; nichts geändert.
- **Nicht verfügbar:** echtes MS Office. Word/Excel wurden mit ihren bekannten Speicherabläufen als echte
  SMB-Dateioperationen nachgestellt; LibreOffice (echt) und die Explorer-Shell (`Shell.Application`, gleiche
  Kopier-/Verschiebe-Engine wie der Explorer) liefen original.
- **Code-Stände:** Das Image (Build `19.0-20260817`) weicht vom lokalen Odoo-Repo (HEAD `2e2acfd6`, 24.09., flacher
  Clone) in **958 von 20.010** vergleichbaren `.py/.js/.xml`-Dateien ab, darunter `orm/models.py`, `http.py`,
  `sql_db.py`, `service/server.py`, `ir_binary.py`, `mail_thread.py`, `tools/misc.py`. Zeilenangaben dieses Docs
  stammen teils aus dem Image, teils aus dem lokalen Repo. Für Verhalten gilt das Image (siehe 19.2, `parent_path`).

### 19.2 Odoo-Core und Datenbank
| Punkt (Abschnitt) | Ergebnis | Beleg |
|---|---|---|
| `ir.rule` mit `user.env[...]` für Nicht-Admins (16.1) | **Kein `AccessError`, kein `sudo()` nötig:** `env.user` ist immer `sudo` | `orm/environments.py:213` (Image und lokal gleich); Nicht-Admin ohne Leserecht auf `protected_folder`: Regel mit und ohne `.sudo()` liefert dasselbe Ergebnis |
| `ir.rule`-Cache (16.1) | **Bestätigt:** Neuer Schutzordner (ohne `ir.rule`-Schreibvorgang) wirkt erst nach `registry.clear_cache()`, auch über neue Transaktionen hinweg; `dev_mode` war aus. Jedes `ICP.set_param` leert den Cache nebenbei (zufällige Heilung, kein Mechanismus) | Test in `fmtest` |
| `@api.private` (16.1) | Wirkt über die ganze MRO; `_`-Methoden sind ohnehin gesperrt. Per RPC geprüft: `_cron_scan_filemanager` und `lock_for_update` → "Private methods … cannot be called remotely" | `service/model.py:45-70` |
| `ir.binary` + Schutzordner (17.4) | **Regeln greifen:** Nicht-Admin, `/web/image/…/thumbnail` im Schutzordner → Platzhalter (PNG 6078 B), `/web/content` → 404; offener Ordner → JPEG 200. Eigene Route: 403 / 200 | HTTP-Test mit echtem Bild |
| pdfminer / `attachment_indexation` (15.1) | vorhanden (`pdfminer.six` 20260107 per pip, überdeckt apt 20221105); Modul installiert, DOCX- und PDF-Text werden extrahiert | Test in `fmtest` |
| `pg_trgm` (15.1, 15.4) | Odoo legt sie beim Anlegen einer DB selbst an (bestätigt), Tower-Live hat sie. Trigram-Index auf `name` greift auf der **echten ORM-SQL** (Nicht-Admin mit Regeln): `rechnung` 267 → **0,30 ms**, `IMG_20` 265 → 17 ms, `.jpg` 561 → 128 ms; 20 MB. `unaccent` ist aus | `fmreal`, 427.914 Zeilen |
| ORM-SQL der Rechte (15.4) | Nicht-Admin, C-Kollation: W1 alle zählen 269 ms (Parallel Seq Scan; Admin 37 ms), W2 Name 275 ms, W3 Ordnerliste 2,6 ms, W4 Unterbaum 1,8 ms, W5 großer Präfix (188k Zeilen) 491 ms, W7 `child_of` 1,6 ms, Top-80-Liste sortiert 2,7 ms. Form: `path LIKE … AND (path NOT IN … AND path NOT LIKE … AND (trashed IS NOT TRUE OR trashed_by IN …))` | `fmreal` |
| `SKIP LOCKED` unter `REPEATABLE READ` (4.4) | **Bestätigt:** `FOR UPDATE`, `… SKIP LOCKED`, `FOR NO KEY UPDATE SKIP LOCKED`, `NOWAIT` auf eine nach dem Snapshot committete Zeile → jeweils `40001`; Zeile von offener Transaktion gesperrt → `SKIP LOCKED` leer | PostgreSQL 16.15 |
| `parent_path` und Kollation (15.2) | Literalprüfung: `en_US.utf8` **false**, C true. Echte Werte: 294 von 300 Ordnern bekämen unter `en_US` einen falschen Teilbaum (47.313 Nachkommen fehlen). **Das Image nutzt noch `LIKE`** (unkritisch), der neuere Core die Bereichsprüfung. Exaktes neues `UPDATE` auf `en_US`-Spalte (zurückgerollt): Ordner mit 35 Knoten → **1 aktualisiert, 34 Nachkommen falsch** | Image `orm/models.py:5020-5045` vs. lokal `5027-5058`. **Folge:** Vor einem Image-Update muss eine `en_US`-DB (HM-SRV laut 15.2) auf C umgestellt sein; der Punkt eignet sich als Upstream-Meldung an Odoo |
| `mail.thread`-Tracking als Audit (15.4, 16.5) | Nur `status_id` hat `tracking=True` (1 Nachricht + 1 Tracking-Wert je Änderung, entsteht im `precommit`). Name, Pfad, Partner werden nicht erfasst; Schreibwege mit rohem SQL (`index_utils.py:158`) umgehen das Tracking ganz | Test in `fmtest` |
| `trashed` → `active` (16.1) | Umfang unverändert: 5 Dateien, 48 Stellen (Stand 1.15.0) | `grep` |
| Migration 1.15.0 an echten Daten | 427.914 Zeilen, Modul in **3,5 s** geladen (`ADD COLUMN … DEFAULT` ohne Umschreiben). **Aber:** Das Update schaltet alle 9 `int_filemanager`-Crons wieder ein (`ir_cron.xml` ohne `noupdate`), auch nach `neutralize` oder manuellem Abschalten | `fmreal` |
| `watchdog` (16.1) | Herkunft: offizielles Image `odoo:19.0` (apt `python3-watchdog 3.0.0-1`). `FileClosedEvent` bei `IN_CLOSE_WRITE` (`inotify.py:184`). **gevent:** Observer nach `monkey.patch_all()` blockiert den ganzen Prozess (Container hing > 6 min). **Threaded:** 30.000 Dateien in 4,4 s, Handler 2 ms je Ereignis → alle 30.000 nach 70 s angekommen (der Lesethread leert die Kernel-Queue in eine unbegrenzte Python-Queue). **Überlauf:** `IN_Q_OVERFLOW` wird verworfen (`inotify_c.py:320`, `if wd == -1: continue`); roh 16.384 von ca. 40.000 Ereignissen ohne jedes Signal. Tower-Live hält 29.131 Watches für 29.318 Ordner (Grenze 524.288) | Wegwerf-Container |

### 19.3 Dateisystem und SMB
**shfs-Inode (13.4, 11.4):** 64-Bit-Werte (Platte + Platten-Inode). Stabil bei: Umbenennen, Verschieben in einen Ordner,
der nur auf einer anderen Platte liegt (die Datei bleibt physisch auf ihrer Platte), Verschieben Cache → Array-Ordner,
Umbenennen eines Ordners, der auf zwei Platten verteilt ist (Ordner und Kinder), nach `drop_caches`, in einem neuen
Container, Host- und Container-Sicht identisch. **Geändert** hat sie sich beim Umzug im Stil des Movers (Cache →
`disk3`, gleicher Pfad): `12103423999611841` → `649362771271483443`. Die Inode taugt also als Hinweis; gleicher Pfad
mit neuer Inode darf nicht als neue Datei gelten.

**Offenes Dateihandle (7):** Windows-Client öffnet eine Datei über SMB, schreibt, der Server tauscht sie per
`os.replace` aus, der Client schreibt weiter und schließt: Die zweite Schreibung ist **still verloren**, der Client
bekommt keinen Fehler. Mit `FileShare.Read` (andere dürfen nicht schreiben, wie bei Word) genauso: Samba-Sperren
halten ein `os.replace` auf dem Server nicht auf.

**SMB-Abläufe (Watcher = heutiger Code, 1.15.0):**
| Aktion (Windows) | Rohe Ereignisse auf dem Server | Ergebnis im Index |
|---|---|---|
| Ordner anlegen | Samba legt `.::TMPNAME:D:…:<name>` an und benennt um; shfs meldet zusätzlich `CREATE <name>` | korrekt (Punktnamen werden ignoriert) |
| Neue Datei | `CREATE`, `ATTRIB` (2×), `MODIFY`, `CLOSE_WRITE` | korrekt |
| Speichern im Editor, Explorer-Kopie "Ersetzen" | nur `CLOSE_WRITE` (gleiche Inode) | Zeile und Token bleiben, Größe aktualisiert |
| Umbenennen, Verschieben, Ordner umbenennen/verschieben, nur Groß-/Kleinschreibung (Explorer-Shell) | ein `MOVED`-Paar mit Cookie | Zeile und Token bleiben, auch für Kinder |
| Verschieben über vorhandenen Namen (`MoveFileEx` mit Ersetzen) | Samba: **`DELETE` des Ziels, dann `MOVED`** | Zielzeile gelöscht (Token/Versionen weg), Quellzeile übernimmt den Pfad; **keine** `UniqueViolation` (anders als `mv -f` auf dem Host, 13.3) |
| Löschen | `DELETE` | Zeile hart gelöscht (heutiges Verhalten) |
| **Word-Speicherablauf** (schnell und mit 2-s-Pausen) | `~$…` anlegen, `~WRD0000.tmp` schreiben, Original → `~WRL0001.tmp`, `~WRD…` → Original, `DELETE ~WRL…`, `DELETE ~$…` | **Original-Zeile gelöscht, neue Zeile ohne Token** (11 → 21, 21 → 23); `~$`-Besitzerdatei wird kurz indexiert |
| **Excel-Speicherablauf** | wie Word mit 8-stelligen Hex-Namen | neue Zeile, Token verloren (12 → 25) |
| **LibreOffice** (echt, Überschreiben) | `.~lock…#`, `lu….tmp` schreiben, dann Windows `ReplaceFile`: `…~RFd….TMP` anlegen, Original → `~RFd`, `lu…` → Original, `DELETE ~RFd` | Zeile behält Token **zufällig** (Umbenennen nach `~RFd` ignoriert, `lu…` → Original scheitert mit `UniqueViolation`); **Geisterzeile** `lu….tmp` bleibt |
| 3-GB-Datei kopieren | `CREATE`, 27 s später `CLOSE_WRITE` | **Die Größe steht sofort auf 3 GB** (Windows reserviert vorab); nur `CLOSE_WRITE` zeigt das Ende an. Hash-Cron während der Kopie: `compute_stable_hash` erkennt die Änderung, bleibt `pending` (richtig) |
| 20.000 Dateien (robocopy `/MT:16`) | ca. 13 Dateien/s (shfs 108 % CPU) | Watcher schafft ca. 8/s; Endstand **16.576 von 20.000 (17 % dauerhaft verloren)**; der Logger (eigene Queue) sah keinen Überlauf, der Verlust liegt in der Queue des Watchers (B11). Ordner, die im Rückstau angelegt wurden, bekamen **keinen Watch**, spätere Saves darin blieben unsichtbar. Erst der Vollscan (17,6 s) holte alles nach |
| Name mit NFD-Zeichen (`e` + U+0301) | Name auf der Platte in NFD | **Index speichert NFC** (`index_utils.py:38, 42`, `path_utils.py:107`, `filemanager_file.py:879`) → Pfad existiert so nicht; Download liefert **422** |

Rechte: Über SMB angelegte Ordner erhalten 0777. Auf dem Host als root angelegte Ordner (0755) kann Odoo (uid 100) nicht
beschreiben, dann scheitert jedes Veröffentlichen (Temp-Datei im Zielordner).

**Kosten Nachholabgleich (5.3), Tower-Live-Daten nur lesend:** `scandir` + `stat` aller Einträge (429.184 Einträge,
29.316 Ordner): **211 s kalt, 214 s im zweiten Lauf** (shfs profitiert praktisch nicht vom Cache); nur Ordner
(`scandir` aller Einträge, `stat` nur je Ordner, als Grundlage eines mtime-basierten Abgleichs): **38 s** für 29.317 Ordner, also rund 5,5-mal schneller. Der tägliche Vollscan auf Tower-Live
braucht zum Vergleich ca. 11 min (03:00:53–03:12:00).

### 19.4 Durchstich 1.15.0 und Pflichttests
- **Modul-Tests:** 95 Tests, 0 Fehler (86 s, Wegwerf-DB, eigene leere Wurzel).
- **Upload überschreiben + Explorer schreibt während `pending`:** Fehlerinjektion `hook_before_snapshot` → Zeile
  `pending`, Revision 1, Platte unverändert (richtig). Dann per SMB `EXTERN-V3`; danach Nachholen per
  `publish_pending` → Platte = App-Fassung, `synced`, die externe Fassung ist **als Version gesichert**
  (27 Bytes), kein Verlust. **Aber:** Herkunft `app` statt `extern`, weil der Watcher den Index vorher schon auf
  den externen Stand gezogen hatte und `_differs_from_index` gegen diesen Index vergleicht. Die zuvor extern
  überschriebene Ausgangsfassung V1 ist erwartungsgemäß weg (Abschnitt 7).
- **B10 live:** Das Watcher-Ereignis zur selben Zeile scheiterte mit `40001`. **Zusätzlich** bricht damit der Rest
  des Ereignis-Batches ab: `_run` fängt die Ausnahme, danach committet `with reg.cursor()` die abgebrochene
  Transaktion → `InFailedSqlTransaction` → "error processing event batch" (`watcher.py:36-56`).
- **B1 live bestätigt:** Datei über `/int_filemanager/delete` in den Papierkorb, danach ein normaler Vollscan →
  Papierkorb-Zeile **und** Datei auf der Platte gelöscht, `.trash` verschwunden. Tower-Live ist derzeit nicht
  betroffen: Der dort laufende Stand hat keine `trashed`-Spalte, obwohl er als 1.14.0 geführt wird (der
  Papierkorb-Commit `b53fed2` hat die Version nicht erhöht; eine Versionsnummer beschreibt damit mehrere
  Code-Stände).

### 19.5 Neue Befunde (nicht im Konzept)
| # | Schwere | Befund | Beleg |
|---|---|---|---|
| N1 | **kritisch (Sicherheit)** | `action_analyze_document(path)` und `action_apply_extracted_values(path, values)` sind öffentliche `@api.model`-Methoden, arbeiten mit `sudo()` und verlassen sich auf `authz.require` im Controller. Per RPC (`/web/dataset/call_kw`) umgeht man den Controller: Ein Nicht-Admin bekam den **Volltext einer Datei im Schutzordner** (`content_text_preview`) und konnte dort extrahierte Werte **überschreiben**. Auch im Tower-Live-Code vorhanden (dort nur 1 interner Nutzer). Abhilfe: Methoden privat machen (`_`-Präfix oder `@api.private`) oder die Rechte in der Methode selbst prüfen | RPC-Test als Nicht-Admin |
| N2 | hoch | NFD-Namen: Index in NFC, Platte in NFD → Datei per App nicht erreichbar (422). Betrifft macOS-Clients (`fruit`) und Namen mit kombinierenden Zeichen | 19.3 |
| N3 | hoch | Überlauf hinterlässt Ordner **ohne Watch**; alles darin bleibt bis zum Scan oder Neustart unsichtbar | 19.3 |
| N4 | mittel | Ein fehlgeschlagenes Ereignis verwirft den Rest seines Batches | 19.4 |
| N5 | mittel | Jeder CLI-Start mit derselben DB (`odoo shell`, `odoo -u`) startet einen **zweiten Watcher** (`_resolve_dbname` über `db_name`), auf Live also doppelte Verarbeitung, solange die Shell läuft | Log "watcher active" im Shell-Prozess |
| N6 | mittel | Modul-Update schaltet alle Crons wieder ein (`noupdate` fehlt) | 19.2 |
| N7 | mittel | Herkunft `app` statt `extern`, wenn der Watcher den externen Stand vorher indexiert hat | 19.4 |
| N8 | niedrig | Frische Installation: `share_state`/`revision` sind bei Watcher-Zeilen `NULL` (rohes `INSERT`, DB-Default gibt es nur über die Migration). Der Code verträgt es (`revision or 0`, Vergleiche auf `'pending'`); der Teilindex `WHERE share_state <> 'synced'` schließt `NULL` aus | `fmtest` |
| N9 | niedrig | Versionsnummern mehrdeutig (Code-Änderungen ohne Versionssprung) | 19.4 |

### 19.6 Bezug zu den offenen Entscheidungen (Abschnitt 11)
- **11.1 Tombstone:** Löschen über SMB ist auf dem Share endgültig (kein Papierkorb im Share). Der Tombstone ist
  danach die einzige Spur der Metadaten.
- **11.4 Inode:** hilft bei Umbenennen und Verschieben, die ohnehin als `MOVED`-Paar mit Cookie ankommen. Bei den
  Speicherabläufen von Word, Excel und LibreOffice entsteht eine **neue** Datei (neue Inode), dort hilft die Inode nicht.
  Identität braucht hier die Endzustandslogik aus 5.4 ("Pfad in der Ruhezeit gelöscht und wieder angelegt → gleiche
  Zeile"). Nach einem Mover-Umzug ändert sich die Inode bei gleichem Pfad.
- **11.5 Teilindex:** Verschieben über einen vorhandenen Namen kommt über SMB als `DELETE` + `MOVED`. Mit Archivieren
  statt Löschen hielte die archivierte Zielzeile den Pfad weiter → der partielle Unique-Index ist nötig (stützt die
  Empfehlung).
- **Die übrigen Entscheidungen (11.2, 11.3, 11.6)** sind Produktfragen; die Tests liefern dazu keine neuen Fakten.
- **Konsequenzen für die Reihenfolge (Abschnitt 10):** N1 vor allem anderen (Sicherheit). Hotfix B1 bleibt Punkt 1.
  Watcher: `watchdog` nur im Threaded-Modus. Der Überlauf muss selbst erkannt werden, da die Bibliothek ihn
  verschluckt, etwa mit einem eigenen Lesezugriff auf den Deskriptor oder einem regelmäßigen Nachholabgleich.
  Außerdem nötig: NFD-Behandlung und der Schutz vor einem zweiten Watcher bei CLI-Starts.

### 19.7 Nicht geprüft
Echtes MS Office (nur nachgestellte Abläufe); macOS-Clients; HM-SRV selbst (nicht erreichbar); `access_token`-Weg
für externe Freigaben (17.4); Enterprise/OCA; die Umstellung `trashed` → `active` und der partielle Unique-Index als
Code; Last mit mehreren gleichzeitigen Nutzern.

**→ 20:** `access_token`, die Umstellung `trashed` → `active` mit partiellem Unique-Index (als Prototyp) und Last mit
mehreren Nutzern sind inzwischen geprüft.

---

## 20. Zweite Prüfrunde auf Tower: Code-Befunde, Pflichttests, Prototypen (2026-09-25)

Aufbau wie in 19.1. Zusätzlich: Die Tests liefen aus einem Hilfscontainer im Testnetz (HTTP gegen `fmtest_odoo`,
direkter DB-Zugriff für Sperren und Prüfungen), damit sie auch einen absichtlich beendeten Odoo-Prozess überstehen.
Für "Platte voll", "Mount weg" und "anderes Dateisystem" bekam der Testcontainer zwei zusätzliche Mounts: ein
2-MB-tmpfs unter `voll/` und einen verschachtelten Ordner unter `p/nested/`. Die Prototypen liefen in einer
**Kopie** der Addons (`addons_proto`) auf eigenen Datenbanken; das Repo ist unverändert.

### 20.1 Befunde B2–B15 live ausgelöst
| # | Test | Ergebnis |
|---|---|---|
| B2 | Umbenennen, Verschieben, Löschen; `40001` erzwungen (zweite Transaktion sperrt die Zeile und committet nach dem Snapshot des Requests) | **Alle drei bestätigt.** Die Platte ist geändert, der Retry meldet dem Nutzer einen Fehler ("Eintrag nicht gefunden" bzw. "existiert bereits"). Umbenennen: Index zeigt weiter den alten Namen (Geisterzeile), der neue ist nicht indexiert. Verschieben: Geisterzeile am alten Ort plus neue Zeile am Ziel (Identität verloren). Löschen: Datei liegt in `.trash`, **ohne** Papierkorb-Zeile, also unsichtbar und vom Aufräum-Cron nie erfasst. **Auch ohne künstliche Sperre beobachtet:** Ein Umbenennen, während der Watcher das Ereignis eines WebDAV-PUT derselben Datei verarbeitete, lief in `40001` → Retry → Fehlermeldung, obwohl umbenannt war |
| B4/B5 | WebDAV-PUT ("Lokal öffnen") | **Überschreibt ohne Version** (V1 weg). PUT wird **trotz fremdem LOCK** angenommen. ETag aus ganzzahligen Sekunden: nach einem PUT in derselben Sekunde gleiches ETag, `If-None-Match` liefert **304 mit veraltetem Inhalt**. Ein PUT mit `Content-Type: application/x-www-form-urlencoded` schreibt **0 Bytes** und meldet 204 (werkzeug liest den Body als Formular). 129 MiB → 413 (Upload und PUT, 15.1 bestätigt). Tokens liegen nur im Speicher: **nach einem Server-Neustart 403**, ein offenes Office-Dokument kann dann nicht mehr zurückspeichern |
| B6 | Upload auf eine Datei, die nur auf der Platte liegt (z. B. nach Überlauf nicht indexiert) | **Ohne Version überschrieben** |
| B6 | `write_text` bei voller Platte | Datei abgeschnitten und nur teilweise neu geschrieben, **Original zerstört**, keine Version |
| B7 | WebDAV-Token, dann Umbenennen in der App, dann Save mit altem Token | **Legt die alte Datei neu an** (neue Zeile); die umbenannte Datei bleibt unverändert |
| B13 | Unterordner unlesbar (`chmod 000`), dann Vollscan | **Alle 5 Zeilen darin gelöscht**, Token weg, obwohl die Dateien existieren. Tower-Live hat einen solchen Ordner (`cloudreve/2/Musik/Kinderlieder`, root 0744, für Odoo nicht betretbar): Seine Einträge fehlen dauerhaft im Index |
| B13 | Verschachtelter Mount fällt weg (leerer Ordner an seiner Stelle), Vollscan, Mount kommt zurück | Zeilen gelöscht, danach **als neue Zeilen ohne Token** angelegt. Der Schutz greift nur für Ordner der obersten Ebene |
| B14 | Endgültiges Löschen, DB-Fehler beim Löschen der Zeile (Trigger in der Test-DB) | **Zeile bleibt, Bytes sind weg**; "Wiederherstellen" endet mit rohem "No such file or directory" |

### 20.2 Pflichttests gegen den Durchstich 1.15.0 (Upload überschreiben)
| Test | Ergebnis |
|---|---|
| **Harter Prozessabbruch** (`os._exit`) nach jeder Stufe: `stage_before_commit`, `hook_before_snapshot`, `hook_after_snapshot_commit`, `hook_after_temp_written`, `hook_after_replace`, `hook_before_finalize_commit`; danach Neustart und Nachholen | **Alle sechs korrekt:** Vor dem Commit bleibt V1 (nichts halb geschrieben); nach dem Commit liegt nach dem Nachholen V2 auf der Platte, V1 ist **genau einmal** gesichert, keine Temp-Reste, `synced`. Der Client sieht bei Abbrüchen im Hook einen Verbindungsabbruch, obwohl der Upload verbindlich gespeichert ist |
| Zwei gleichzeitige Saves derselben Basisrevision | einer 200, der andere **422 mit Meldung**, nichts still verloren |
| Identischer Upload zweimal | zweiter wird als byteidentisch übersprungen, keine Doppelversion |
| Umbenennen während `pending` | Nachholen schreibt an den neuen Pfad (richtig) |
| **Elternordner extern verschoben während `pending`** (in einen gerade neu angelegten Ordner) | **Datenverlust:** Der Watcher löscht die Zeilen und legt neue an; die `pending`-Zeile samt `pending_content`-Attachment ist weg, die bestätigte App-Fassung verloren. Praktischer Beleg für "Watcher und Scan löschen nie" (5.1, 10.1) |
| Zielordner nicht beschreibbar | Nutzer bekommt 200, Datei bleibt **dauerhaft `pending`**, der Cron scheitert bei jedem Lauf; der Nutzer erfährt nichts |
| **Platte voll** | Original unversehrt, `pending`, keine Temp-Reste; nach Freigabe von Platz holt der **echte Cron** nach (`synced`, genau eine Sicherung). Zum Vergleich: `write_text` und WebDAV-PUT zerstören bei voller Platte das Original (20.1) |
| Verschieben über Dateisystemgrenzen (App) | Zeile, Token und Versionen bleiben |
| Cron während Modul auf "to upgrade" (5.3) | **Bestätigt:** Odoo überspringt **alle** Crons der DB ("Skipping database … because of modules to install/upgrade/remove"), auch das Nachholen. Ein hängengebliebenes Update hält die Wiederherstellung unbegrenzt an |

### 20.3 Weitere Punkte
- **`access_token` (17.4):** `/web/image/…/thumbnail?access_token=…` funktioniert anonym, ist an das Feld gebunden (ein
  Token für `thumbnail` öffnet `preview` nicht) und umgeht bewusst die Schutzordner-Regel. Für Freigaben richtig,
  solange Tokens nur für freigegebene Dateien erzeugt werden.
- **`fields.Image` (17.5):** siehe Korrektur in 17.1. Zusätzlich: Pillow ist im Odoo-Prozess auf wenige Formate
  beschränkt, außerhalb von Odoo öffnet dasselbe Image die WebP-Datei problemlos.
- **Trigram-Schreibkosten (15.4):** 50.000 Updates 7,1 → 7,7 s (+8 %), 20.000 Inserts im Messrauschen, Indexbau 3,9 s.
- **Last (ein Odoo-Prozess wie live, Nicht-Admin, 428.000 Zeilen, je 30 s Mix aus Baum, Ordnerliste, Suche, Download):**

| Nutzer | ohne Trigram: Anfragen/s | Suche p50 / p95 | mit Trigram: Anfragen/s | Suche p50 / p95 |
|---|---|---|---|---|
| 1 | 13,8 | 355 / 437 ms | 58,7 | 15 / 48 ms |
| 5 | 35,6 | 668 / 904 ms | 187,5 | 21 / 65 ms |
| 10 | 33,4 | 1.164 / 2.735 ms | 186,9 | 38 / 82 ms |
| 20 | 37,3 | 2.145 / 4.380 ms | 184,5 | 85 / 130 ms |

  Keine Fehler. Baum, Ordnerliste und Download bleiben in beiden Fällen schnell. Ohne Trigram ist die Namenssuche der
  Engpass und bremst über den gemeinsamen Prozess alle anderen Anfragen; mit Index steigt der Durchsatz um das
  Fünffache.

### 20.4 Prototyp `trashed` → `active` mit partiellem Unique-Index
Minimaler Umbau in einer Kopie: `active` + `removal_reason` (`trash`/`external`),
`models.UniqueIndex("(path) WHERE active IS TRUE")` statt `unique(path)`, Papierkorb setzt zusätzlich `active=False`,
Migration mit DB-Default `true`. Absichtlich **nicht** alle 48 Stellen angepasst, um zu sehen, was bricht.
- **Teilindex:** Odoo 19 legt ihn korrekt an (`int_filemanager_file_path_uniq_active … WHERE (active IS TRUE)`) und
  entfernt die alte Constraint beim Update selbst.
- **Bruch 1:** `INSERT … ON CONFLICT (path)` in `_upsert_by_path` (auch vom Watcher genutzt) ist mit einem Teilindex
  unverträglich (`there is no unique or exclusion constraint matching the ON CONFLICT specification`, 7 von 95 Tests).
  Abhilfe: `ON CONFLICT (path) WHERE active IS TRUE`, oder `_upsert_by_path` wie in 4.5 vorgesehen ganz entfernen.
- **Bruch 2:** Bei einer frischen Installation legt Odoo `active` **ohne DB-Default** an. Rohe `INSERT`s erzeugen
  `active = NULL`: Diese Zeilen sind für die ORM unsichtbar und fallen nicht unter den Teilindex → **Duplikate**
  (Test: "182 != 179 … nicht duplizieren"). Abhilfe: DB-Default per Migration **und** Init-Hook, oder nur ORM-`create`.
- **Bruch 3:** Suchen ohne `active_test=False` finden archivierte Einträge nicht mehr (3 Papierkorb-Tests). Versteckte
  Folge: `_ensure_trash_folder` findet den archivierten `.trash`-Ordner nicht und legt **einen zweiten** an.
- **Wirkung:** **B1 ist behoben, ohne den Scan-Code anzufassen** (Papierkorb-Zeile und Bytes überstehen den
  Vollscan). Eine neue Datei am Pfad eines Tombstones "extern entfernt" lässt sich anlegen. **Doppelbedeutung
  bestätigt:** Eine naive Papierkorb-Ansicht `active=False` zeigt Tombstones mit an, erst `removal_reason` trennt.
- **Migration auf der Live-Kopie (428.000 Zeilen):** Modul in 4,0 s geladen, Gesamtlauf 17 s, alle Zeilen `active`.

### 20.5 Prototyp minimaler Watcher mit `watchdog` (5.2)
Threaded-Observer sammelt nur Pfade (Dirty-Satz), keine DB. Überlauferkennung per Patch auf
`Inotify._parse_event_buffer` (erkennt `wd == -1` mit `IN_Q_OVERFLOW`, bevor `watchdog` es verwirft). Auf shfs:
- **200 neue Ordner × 100 Dateien** (20.000 in 11,3 s): **alle 20.000** im Dirty-Satz, auch die in den neuen Ordnern
  (`watchdog` durchläuft neu angelegte Ordner selbst). Ruhe nach 18 s. Zum Vergleich der heutige Watcher: 17 % Verlust
  bei nur 13 Dateien/s über SMB (19.3).
- **Erzwungener Überlauf** (Leseprozess per SIGSTOP angehalten, 30.000 Dateien): nur 5.462 kommen an, der Überlauf wird
  aber **zuverlässig erkannt** und kann einen Vollabgleich auslösen.
- Damit tragen die Bausteine aus 5.2: `watchdog` für Watches und Move-Paare, eigene Überlauferkennung, danach Abgleich.
  Nicht Teil des Prototyps: `dirty`-Tabelle, Abgleich-Cron, gevent (dort blockiert `watchdog`, 19.2).

### 20.6 Folgen für die Reihenfolge (Abschnitt 10)
1. **N1 (RPC-Lücke)** zuerst, dann **Hotfix B1**. Der Prototyp zeigt, dass `active` B1 ohne Scan-Änderung behebt;
   Voraussetzung sind die drei Brüche aus 20.4.
2. **Watcher und Scan dürfen nichts löschen** (B13, P10-Verlust in 20.2). Das ist auch vor dem großen Umbau als
   Hotfix sinnvoll: Stale-Zeilen nur markieren, nie löschen.
3. **Übrige App-Schreibwege** auf den Durchstich-Ablauf umstellen: `write_text` und WebDAV-PUT zerstören bei Fehlern
   das Original und legen keine Version an; der Durchstich hat alle Abbruch- und Platte-voll-Tests bestanden. B2
   verschwindet mit dem Ablauf, weil vor dem Commit nichts mehr auf der Platte passiert.
4. WebDAV: Tokens persistent (Tabelle statt Speicher), an Datei-ID statt Pfad (B7), PUT mit Lock- und Revisionsprüfung,
   ETag aus `mtime_ns`/Revision.
5. **Trigram-Index** auf `name` früh einführen: großer, risikoarmer Gewinn unter Last.
6. Nutzer-Rückmeldung für dauerhaft `pending` (nicht beschreibbares Ziel) und für "Verbindung abgebrochen, aber
   gespeichert".

### 20.7 Weiterhin nicht geprüft
Echtes MS Office, macOS-Clients, HM-SRV, Enterprise/OCA-`dms`, dynamische `ir.rule` als Code, Bild-Zielbild 17.3 als
Code.
