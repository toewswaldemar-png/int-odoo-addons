# int_filemanager: Konzept "Datenbank hat Vorrang" — App-Änderungen, externe Änderungen, Watcher

Stand 2026-09-24. **Reines Konzept, nichts umgesetzt.** **Entscheidung des Nutzers (2026-09-24):
Variante B — DB als Wahrheit, lesbare Ordner auf dem Share, Odoo schreibt, minimaler Watcher.
`ir.attachment`/Filestore (Variante A) bleibt spätere Option pro Bereich; Versionen liegen schon dort.** Bündelt das Ergebnis der Prüfrunden vom
2026-09-24 (Code-Durchsicht, Live-Prüfung auf HM-SRV, Odoo-19-Core im Container, externes Review
`ODOO_DB_WAHRHEIT_PRUEFUNG_2026-09-24.md`) in einem Dokument. Prüfgrundlage: Repo `int-odoo-addons`
HEAD `432a95f`, Live-Instanz HM-SRV (192.100.0.119), Container `Odoo19` / `odoo_db`.

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
| Blob zuerst, unveränderlich | `ir_attachment.py:158` `_file_write` | Name = sha1, nur schreiben wenn nicht vorhanden, vorher in Checkliste. Abbruch → harmloser Orphan |
| Löschen: erst DB, Bytes später | `ir_attachment.py:741` `unlink`, `_file_delete`, `_gc_file_store` | Bytes nur per GC-Cron, nie sofort |
| Externe Wirkung nach Commit | `sql_db.py:165-168, 566-577`; `mail_mail.py:689`; `ir_actions.py:1062`; `bus.py:139-150` | `cr.postcommit`; bei `rollback()` wird `postcommit.clear()` aufgerufen → **Retry wiederholt nur DB-Arbeit** |
| Hooks fangen nichts ab | `tools/misc.py` `Callbacks.run` | Ein Fehler im Hook = 500 trotz Commit → Hook muss selbst try/except |
| Sperren | `orm/models.py` `lock_for_update()` / `try_lock_for_update()` (`SKIP LOCKED`); Cron `FOR NO KEY UPDATE SKIP LOCKED` | Nur Zeilensperren; **kein einziger Advisory-Lock im Core** |
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
- **Sperren:** Im gesamten Core kein einziges `pg_advisory` (grep über alle `.py` außer Tests);
  Tabellensperren nur in `ir_attachment` (GC), `ir_module`, `transifex`. `lock_for_update()` wirft
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
  ONLYOFFICE-API vorhanden, im Code nicht geprüft).
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
2. Neue Bytes als **Temp-Blob** bereitstellen (harmlos bei Abbruch; GC räumt auf).
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
Nichts Externes passiert vor dem Commit → Odoos `retrying()` ist unproblematisch. Zusätzlich vom
Client mitgeschickte **Vorgangs-ID** gegen Doppelklick/erneutes Senden.

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
   solange Watcher und Cron im selben Prozess laufen (`workers=0`).
4. Herzschlag (Zeitstempel pro Minute).
5. Aufpasser: Absturz von `read()` → Neustart, Watches neu, "Vollabgleich nötig"; `Q_OVERFLOW` →
   "Vollabgleich nötig". Kein Schreiben in Index-Tabellen.

### 5.3 Abgleich-Cron
- Bearbeitet nur `dirty`-Pfade, die älter als 2–3 s sind (Ruhezeit, **Debounce per Zeitstempel**, da
  `_trigger(at=…)` nur minutengenau ist); triggert sich selbst erneut, solange welche fehlen.
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
sperren und die Basisrevision (Checksum, wie der ONLYOFFICE-Key) in derselben Transaktion prüfen.

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
  Schreibungen sind danach nicht mehr erreichbar (bei Excel vermutlich selten, weil es per Umbenennen
  speichert — ungeprüft).
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
| `int_filemanager_wahrheitsmodell_watcher_reduktion_2026-09-24.md` | Idee "Schnitt lokal/CIFS" trägt nicht (Daten liegen fast nur auf CIFS-Testfreigaben, lokal nur `Test`); Zeile "App-Schreibvorgänge sind DB-geführt" trifft nicht zu (B4) |
| `int_filemanager_filebrowser_scan_architektur_2026-09-23.md` | Bezieht sich auf `_shallow_reconcile()`, der nicht existiert; CIFS-Scanstrategie ist Testbetrieb und niedrig priorisiert |
| `int_filemanager_papierkorb_odoo_umsetzung_2026-09-23.md` | Papierkorb ist bereits mit `trashed`-Feld umgesetzt (Commit `b53fed2`), nicht mit `active`; Watcher-Guard-Argument überholt |
| `int_filemanager_watcher_stille_fehlschlaege_2026-09-23.md` | Funde bleiben gültig, Bewertung ändert sich (`max_user_watches` unkritisch; Watchdog wichtig, aber Watcher wird zum Zulieferer) |
| `int_filemanager_grundsatz_explorer_ausbau_2026-09-23.md` | Roadmap bleibt; Reihenfolge Abschnitt 10 dieses Docs hat Vorrang für das Fundament |
| `int_filemanager_bildvorschau_bearbeitung_odoo_2026-09-23.md` | Recherchebasis; die Empfehlung "Cropper.js selbst einbinden, Filterfunktionen kopieren, Rotation per Pillow" ist durch Abschnitt 17 (nativer Bauplan) **ersetzt** |
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
  Neustart/Plattenwechsel).

---

## 14. Vergleich mit FileBrowser (Quellcode gelesen, 2026-09-24)

Gelesen wurden FileBrowser Quantum (`gtsteffaniak/filebrowser`, Branch `main`: `internal/web/resource.go`,
`internal/adapters/fs/files/files.go`, `fileutils/file.go`, `pkg/indexing/*`, `go.mod`) und das Original
(`filebrowser/filebrowser`, Branch `master`: `http/resource.go`, `go.mod`). Nichts ausgeführt; das
Scan-Scheduling ist zusätzlich in `int_filemanager_filebrowser_scan_architektur_2026-09-23.md` beschrieben.

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
| `@api.ondelete(at_uninstall=False)` statt `unlink()`-Override (Odoo warnt: Override verträgt sich nicht mit Modul-Deinstallation) | `orm/decorators.py:130` | Schutz "Scan löscht keine Zeilen mit Nutzerdaten" als `_unlink_except_…`; Bytes-Löschung aus `unlink()` heraus in Nachwirkung/Cron |
| `@api.autovacuum` (tägliche GC-Methoden ohne eigenen Cron, mit Fortschritt `(done, remaining)`) | `orm/decorators.py:299` | Papierkorb-Purge, `scan_log`, Versionen, `write_journal`, `dirty`-Aufräumen als Autovacuum statt eigener Cron-Einträge |
| `fields.Char(index='trigram')` (GIN, braucht `pg_trgm`) | `orm/fields.py:116`, `fields_textual.py:439-451`, Nutzung z. B. in `account` | Namenssuche (siehe Messung); `pg_trgm` ist im Live-Postgres verfügbar, aber nicht installiert (Anlage durch Odoo/Rechte ungeprüft) |
| `@route(readonly=True)` (RO-Cursor, bei Schreibversuch automatischer Retry mit RW) | `http.py:796, 2276-2298` | Leserouten (`tree`, `download`, `versions`, `zip_list`, `thumbnail`) ohne Schreib-/Konfliktlast; klein, risikoarm |
| `mail.mail`-Queue: `state`, `failure_type`, `scheduled_date`, `process_email_queue(batch_size)`, `auto_commit = not current_test` | `mail/models/mail_mail.py:69-100, 194-244` | Vorlage für `dirty`-/`pending`-Verarbeitung (Batches, Fehlerarten, Testschalter) |
| `attachment_indexation`: `_index_docx/_pptx/_xlsx/_opendoc/_pdf` (pdfminer) | `attachment_indexation/models/ir_attachment.py` | Office-Volltext nativ nutzbar statt eigene Extraktion (Feature-Idee B); Verfügbarkeit von pdfminer im Container ungeprüft |
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
2. **`protected_folder_id` (Plan in `int_filemanager_acl_perf_plan.md`) bringt danach nur noch wenig:** ca.
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
und Enterprise-Module (nicht vorhanden).

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
1. **Offizieller Hook `_order_field_to_sql(alias, field_name, direction, nulls, query)`** (`orm/models.py:5268`;
   überschrieben in `stock`, `project`, `hr_recruitment`, `res_device`). Für `name` liefert er
   `SQL("%s COLLATE %s %s %s", sql_field, SQL.identifier('fm_natural'), direction, nulls)`; `_order` bleibt
   `"is_dir desc, name"`. Der Core selbst nutzt nirgends `COLLATE`.
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
Ungeprüft: Sortierung über Spaltenkopf und `_read_group` laufen vermutlich ebenfalls über `_order_to_sql`
(im Test nur `search`/`_search`); Verhalten in der Oberfläche.
**Nicht Teil des Probelaufs:** Server/UI auf der Kopie (nur `odoo shell`), Schreibkosten, Live-Umschaltung.

---

## 16. Eigenbau-Inventur: native Entsprechungen im Odoo-Core (tieferer Durchgang, 2026-09-24)

Anlass: Mehrfach hatte zuerst "kein Bordmittel" gestanden, das sich bei genauerem Suchen als falsch
erwies (Sortierung, `unique(path)`, Präfix-Suchen). Dieser Abschnitt geht die Eigenbau-Teile des Konzepts und
des heutigen Codes gezielt gegen den Core (Container `Odoo19`, Odoo 19) durch.

### 16.1 Neue Funde
| Eigenbau (Konzept/Code) | Nativ gefunden | Fundstelle / Prüfung | Konsequenz |
|---|---|---|---|
| **Watch-Buchhaltung** im Watcher (`wd_to_path`, Ordner-Umschreiben, `moved_from` je Batch, Watches nach `.trash`) | **`watchdog` 3.0.0** ist im Image installiert und wird vom Core selbst genutzt (`service/server.py`: `FSWatcherWatchdog`, `Observer.schedule(..., recursive=True)`). Die Bibliothek führt `_wd_for_path`/`_path_for_wd`, schreibt Watches bei Moves um und merkt Move-Kennungen **über Lesevorgänge hinweg** (`_moved_from_events`); der `InotifyBuffer` paart `MOVED_FROM`/`MOVED_TO` mit 0,5 s Verzögerung | `watchdog/observers/inotify_c.py:172-182, 220-225, 322-333`; `inotify_buffer.py:28-110` | Punkt 1 des minimalen Watchers (5.2, "Watches pflegen") entfällt weitgehend; das Batch-Grenzen-Problem (B11) ist in der Bibliothek gelöst. **Nicht abgedeckt:** Überlauf (`IN_Q_OVERFLOW` nur als Konstante, `inotify_c.py:70`) — Rescan, Neustart-Abgleich und Herzschlag bleiben Eigenbau. Ungeprüft: Verhalten unter gevent (`workers>0`), Last bei 69k Verzeichnissen, `FileClosedEvent`-Verfügbarkeit |
| **ACL-Regeltext-Generator** (`acl_rules.py`, ~250 Zeilen: Textbau, Platzhalter, `rebuild_rules`, Selbsttests) | **Regel-Domain darf zur Auswertungszeit abfragen:** `ir.rule`-Kontext enthält `user` (= `env.user`), das Regelergebnis wird pro Nutzer gecacht. Im Test lieferte `safe_eval("user.env['int_filemanager.protected_folder'].search_count([])", …)` den Wert 7 | `base/models/ir_rule.py:38-52` (`_eval_context`), `:138-141` (`ormcache` auf `_compute_domain`); Test in `odoodb_c` | Eine kurze Regel könnte die Schutzordner selbst abfragen statt eines generierten Textes. **Offen:** Cache-Invalidierung bei Änderungen an Schutzordnern, `@api.private` gegen RPC-Aufruf, Selbsttests, die `NOT LIKE`-Struktur bleibt (Vollscans, 15.2). Nur Machbarkeit geprüft, nicht umgesetzt |
| **`trashed` (eigenes Boolean)** | **Natives `active`**: `_search` filtert Archiviertes automatisch, auch für `sudo()`; ein `active`-Blatt in der Domain oder `active_test=False` hebt das gezielt auf | `orm/models.py:5362-5369` (`_active_name`, `active_test`) | **Befund im Modul:** 47 `search()`/`search_count()`-Aufrufe, **0** mit `trashed`-Bezug; die Regel `rule_file_trash_visibility` greift nur für Nicht-`sudo`, Watcher/Scan/Index-Funktionen laufen mit `sudo` — B1 ("Scan löscht Papierkorb") ist genau diese Auslassung. Mit `active` entfällt die ganze Fehlerklasse |
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
der Kachelvorschau gedreht) ist Folge dieser Vorverarbeitung, **nicht** ein fehlender EXIF-Aufruf. Es wird
deshalb nicht in `mediameta` nachgebessert, sondern durch den Umbau beseitigt.

### 17.2 Ist gegen nativ
| Aspekt | heute | nativ (Zielbild) |
|---|---|---|
| Felder | `thumbnail` und `preview` unabhängig, je von uns gefüllt | **`image.mixin`-Muster** (`base/models/image_mixin.py`): eine Quelle (`fields.Image(max_width=1920)`) und abgeleitete Größen als `fields.Image(related=…, max_width=…, store=True)`; Schreiben der Quelle erzeugt alle Größen |
| Erzeugung | PIL-Decode, 2× `_resized_jpeg`, Base64 | Rohbytes der Originaldatei in das **Quellfeld** schreiben; Odoo verarbeitet |
| Auslieferung | `/int_filemanager/thumbnail?path=…`: pfadbasiert, eigene `authz`-Prüfung, `b64decode` im RAM, fester Typ `image/jpeg`, `max-age=3600`, kein ETag | **`/web/image/int_filemanager.file/<id>/thumbnail`** (`web/controllers/binary.py:165-179`): `ir.binary._find_record` prüft `check_access("read")` — unsere Rechteregeln greifen ohne Eigencode; Streaming aus dem Filestore; ETag/Last-Modified und `unique=` (Cache), Platzhalter, `access_token` für Freigaben |
| Anzeige | JS baut Pfad-URLs | URLs aus `record.id` (Kanban-Helfer `kanban_image`, `web/static/src/views/kanban/kanban_arch_parser.js:123`); `FileViewer` bleibt (bereits nativ) |
| Bearbeiten | nicht vorhanden | Client: `activateCropper` (siehe 17.3); Server: `odoo.tools.image` (`image_process`, `crop_resize`, `image_quality`, `image_fix_orientation`) |
| Lebenszyklus | `meta_state` + Cron | bleibt: abgeleitete Assets sind Zustand **pro Inhaltsrevision**, Regeneration im Abgleich-Cron (Abschnitt 5) |

### 17.3 Zielbild
1. **Modell:** `preview` wird die Quelle (`fields.Image(max_width=1920, max_height=1920, attachment=True)`),
   `thumbnail` wird `fields.Image(related="preview", max_width=320, max_height=320, store=True)`. Das
   `image.mixin` selbst wird nicht übernommen (5 Größen = 5 Attachments je Bild), nur sein Muster.
2. **Erzeugung:** Der Meta-/Abgleich-Cron liest die Originaldatei (Grenze `meta_max_bytes_image`) und schreibt
   **nur** das Quellfeld mit den Rohbytes. Ein `UserError` (Auflösung über 50 MP, ungültiges Bild) setzt
   `meta_state='error'`. Veraltungsschutz: Größe/mtime (bzw. `content_sha256`) vor und nach dem Lesen vergleichen;
   nur schreiben, wenn die Revision unverändert ist (Testliste "veraltete OCR-/Hash-Ergebnisse", Abschnitt 10).
3. **Auslieferung:** ausschließlich `/web/image/…` mit Datensatz-ID; Cache-Busting per `unique`. Ohne Vorschau:
   nativer Platzhalter; das Original liefert weiter die Download-Route (`http.Stream`). Die Route
   `/int_filemanager/thumbnail` entfällt.
4. **Bearbeiten (Crop, Drehen, später Filter):** OWL-Dialog mit **`activateCropper(image, aspectRatio, dataset,
   {onReady})`** aus `@html_editor/utils/image_processing` (eigenständig exportiert, lädt das Bundle
   `html_editor.assets_image_cropper` bei Bedarf; enthält Cropper.js **und** `webgl-image-filter.js`,
   `html_editor/__manifest__.py:96-99`; `html_editor` ist über `mail` installiert). Ergebnis über
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
und der `access_token`-Weg für externe Freigaben.

### 17.5 Abnahme
EXIF-Orientierungen 1–8; Bild über 50 MP (`meta_state='error'`, kein Absturz); Nicht-Admin auf Schutzordner
(kein Bild, Platzhalter); ETag/`304`; Range; Bearbeiten → Original als Version vorhanden, Vorschau neu erzeugt,
veralteter Cron-Lauf überschreibt keine neuere Revision; GIF/SVG unverändert; Backfill-Lauf ohne Fehler auf der
Testinstanz.

### 17.6 Nicht geprüft
Prototyp (`related` + `store` bei sehr vielen Zeilen, Speicherbedarf: zwei Attachments je Bild); Verhalten von
`kanban_image` in Liste/Dialog; Canvas-/Speichergrenzen im Browser bei sehr großen Bildern; Anzahl der Bilddateien
im Bestand; `attachment_indexation` ist auf Live nicht installiert.
