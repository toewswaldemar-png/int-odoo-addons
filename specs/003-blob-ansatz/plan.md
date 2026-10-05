# Implementation Plan: Ablage großer Dateien im Dateimanager (Blob-Ansatz)

**Branch**: `feature/int-filemanager-v2` (Spec-Ordner `003-blob-ansatz`) | **Date**:
2026-10-05 (auf Option D' umgeschrieben 2026-10-06) | **Spec**: [spec.md](spec.md)
**Input**: Spezifikation und Recherche (`research.md`); die bisherige Umsetzung bleibt
außer Betracht.

## Summary

Dateiinhalte liegen als Dateien unter dem Odoo-Filestore, benannt nach ihrem SHA-256. Es
gibt **keine Blob-Tabelle**: Die Version einer Datei trägt den Hash (`sha256`) und die
Größe (`size`) selbst und die Rechte. Das ist Odoos Muster für Anhänge (Dateiname =
Prüfsumme, Merkzettel, Tabellensperre beim Aufräumen, `ir.attachment._gc_file_store`),
erweitert um das, was der Core nicht kann: Schreiben als Strom statt als Bytes, SHA-256,
Größen über 2 GiB und ein fortsetzbarer Upload. Der Aufräum-Lauf kennt genau diese eine
Tabelle, so wie `ir.attachment._gc_file_store` seine eine Tabelle kennt. Jede spätere
Tabelle, die Inhalt braucht (Vorschau, Freigabe), verweist per Many2one auf die Version
und trägt keinen eigenen Hash; so verweisen im Core alle Modelle auf `ir.attachment`
(`research.md` E34). Aufgeräumt wird nach dem Muster des Cores (Merkzettel,
`LOCK … SHARE MODE` als erste Anweisung, Whitelist-Abfrage in Stapeln) in einem eigenen
Cursor, ergänzt um eine **Schonfrist am Merkzettel** und **markierte Löschwege**
(`Revision.unlink`, `Node.unlink`). Der Abschluss großer Uploads (Hashen, Ablegen) läuft
als Hintergrundauftrag über `ir.cron._trigger()`. Bausteine:

1. **Ablage** (FR-001 bis FR-005): Datei per `os.link` unter ihrem Hash, ein vorhandener
   Name wird nie angefasst, Pfade nur aus geprüftem Hash, Zeile der Version **vor** dem
   Ablegen der Datei.
2. **Upload** (FR-006 bis FR-010): fortsetzbarer Upload mit Zwischendatei, begrenzten
   Teilen, Abschneiden vor dem Anhängen und Größenprüfung; die Upload-Zeile ist ein
   `TransientModel`.
3. **Auslieferung** (FR-011, FR-012): `Stream(type='path')` mit `safe_join`,
   Rechtsprüfung an der Version.
4. **Aufräumen** (FR-013 bis FR-015): `@api.autovacuum`, Merkzettel mit Schonfrist,
   Tabellensperre, Löschwege markieren.
5. **Betrieb** (FR-018, FR-019): Ablageort über `--data-dir`, Sicherung als `dump` plus
   Dateiabgleich, Auslieferung über `--x-sendfile`.

## Technical Context

**Language/Version**: Python 3.12 (Odoo 19.0), JavaScript für den Upload-Client (native
ES-Module, Owl 2.8.4) **Primary Dependencies**: nur Odoo-Core und Standardbibliothek
(`hashlib`, `os`, `shutil`); keine neue Bibliothek **Storage**: Dateien unter
`config.filestore(<db>)/int_filemanager/`; Datenbank: `sha256` und `size` an der Version
(Felder der Version), Zeile für den laufenden Upload (`TransientModel`); keine
Blob-Tabelle **Testing**: Odoo-Tests (`TransactionCase`, `HttpCase`), Echtprozess-Tests
für Gleichzeitigkeit und Absturz auf einer Wegwerf-Instanz mit zwei Workern **Target
Platform**: Odoo-Server (Linux, Docker, Unraid), Entwicklung auf Windows **Project
Type**: Odoo-Addon (Modul `int_filemanager`) **Performance Goals**: Upload einer
5-GB-Datei ohne Speicherwachstum des Workers über 512 MB; Abschluss unabhängig vom
Proxy-Zeitlimit; Aufräumen in Stapeln zu `cr.IN_MAX` (1.000) Merkzetteln
**Constraints**: Regeln aus `docs/odoo_regeln/`; kein eigener Cursor für
Datenbankzeilen; in Crons `_commit_progress`; rohes SQL nur mit `SQL`; Wegwerf-Container
und -Datenbanken **Scale/Scope**: Dateien bis ca. 5 GB; Bestand in der Größenordnung
hunderttausender Dateien und mehrerer Terabyte (Aufräumen in Stapeln, Ablage auf dem
Array)

## Constitution Check

| Grundsatz                       | Prüfung                                                                                                                                                                                                                                                                                                                                      | Stand                               |
| ------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------- |
| I. Odoo-Core vor Eigenbau       | `research.md` Tabelle E1–E19, E30–E34 mit Fundstellen und Abschnitt "Odoo-Bausteine je Anforderung"; Eigenbau nur für Streaming-Schreiben, SHA-256, Größen über 2 GiB, Chunk-Protokoll, `os.link`-Ablage und Schonfrist (E1–E3, E9, E10, V11, V13); Aufräumen, Hintergrundabschluss, Sicherung, Auslieferung und Zugriff über Core-Bausteine | bestanden                           |
| II. Odoo-19-Regeln              | Abgleich in `research.md`; Abweichungen in Complexity Tracking                                                                                                                                                                                                                                                                               | bestanden                           |
| III. Owl 2.8.4                  | Upload-Client nutzt Dienste per `useService`, Browser-Funktionen über `@web/core/browser/browser`; keine Owl-3-API                                                                                                                                                                                                                           | bestanden (bei Umsetzung zu prüfen) |
| IV. Prüfautomatik erzwingt      | neue Regeln (Hash-Format, `SQL`, Stapel) in `test_lint`-Läufe und Tests; Schutztest, dass nur die Version eine Spalte `sha256` hat; kein neues Werkzeug nötig                                                                                                                                                                                | bestanden                           |
| V. Verifizieren                 | V2, V3 (teilweise überholt, V17), V5 bis V21 am 2026-10-05 und 2026-10-06 auf dem Tower gemessen oder gelesen (`research.md`); offen: HM-SRV, Kaltlesung, Last bei vielen Merkzetteln und der Echtprozess-Test mit zwei Workern im Odoo-ORM (Pflicht vor Abschluss der Umsetzung)                                                            | bestanden mit offenen Messungen     |
| VI. Produktentscheidungen vorab | Dateigröße, Fortsetzen, Duplikate, Sicherung am 2026-10-05 entschieden; am 2026-10-06 vom Nutzer entschieden: Ansatz D' (Hash an der Version) und Transport der Teile als Multipart-Teil über `file_upload_service` (gemessen, V17–V23)                                                                                                      | bestanden                           |
| VII. Ursachen beheben           | jede Behebung mit Test; Gleichzeitigkeit und Absturz mit echten Prozessen                                                                                                                                                                                                                                                                    | bestanden                           |

## Design

### Dateiablage

```
<filestore>/int_filemanager/
├── <ab>/<cd>/<sha256>        # Inhalt, genau eine Datei je Hash
├── tmp/<upload-id>           # Zwischendatei eines laufenden Uploads (id = Datenbank-ID, Zahl)
└── checklist/<ab>/<sha256>   # Merkzettel (Muster `ir.attachment._mark_for_gc`): Datei wird beim Löschen oder Ablegen markiert; Alter = `mtime`, beim Markieren angefasst
```

- Der Hash wird auf `^[0-9a-f]{64}$` geprüft, bevor ein Pfad entsteht (Eingabe,
  Datenbankwert und Dateiname des Merkzettels). Der Name der Zwischendatei entsteht nur
  aus der Datenbank-ID des Uploads.
- `tmp` liegt unter demselben Ordner und damit im selben Dateisystem wie die Ablage.
  `dump_db` (Zip) und `duplicate_database` nehmen `tmp` mit; offene Uploads verfallen
  nach der Upload-Frist.
- Ablageort: Odoos `--data-dir` (Filestore = `data_dir/filestore/<db>`,
  `config.filestore`) zeigt auf den Array-Share, oder nur
  `filestore/<db>/int_filemanager` wird als eigenes Volume eingehängt. Zwischendatei und
  Ablage bleiben dabei auf einem Dateisystem. Fällt `os.link` mit etwas anderem als
  `FileExistsError` aus (anderes Dateisystem, kein Hardlink möglich), kopiert
  `shutil.move` auf einen Namen im Zielordner, danach `os.replace`.

### Datenbank

- Version (`int_filemanager.revision`): trägt `sha256` (Char, `size=64`, Index, **kein**
  Unique, weil viele Versionen denselben Inhalt haben; ein `models.Constraint` prüft das
  Hexformat) und `size` (Float, wegen int4 im ORM, bis 2^53 exakt) sowie die
  Zeilenrechte (an der Version und ihrem Knoten). Die Version hängt per
  `ondelete="cascade"` am Knoten, der Knoten per `restrict` am Elternknoten: Jeder
  Teilbaum wird nur über `Node.unlink` gelöscht, das alle Versionen darin kennt (E33).
  Die Aufräum-Methode `_gc_content` liegt an der Version.
- **Einzige Tabelle mit Hash:** Der Aufräum-Lauf fragt `int_filemanager_revision` ab,
  wie `ir.attachment._gc_file_store` `ir_attachment` abfragt. Eine spätere Tabelle, die
  Inhalt braucht (Vorschau, Freigabe), verweist per Many2one auf die Version und trägt
  keinen eigenen Hash (E34). Ein kleiner Test sichert die Regel: Kein anderes Modell hat
  eine Spalte `sha256`. Würde je eine zweite Tabelle mit eigenem Hash nötig, wird der
  Lauf erweitert (Tabellenliste, `LOCK` und Abfrage über alle); ein abstrakter Baustein
  mit `registry.descendants` ist dafür gemessen (V15, V16), aber heute nicht gebaut.
- Upload (`int_filemanager.upload`, `TransientModel`, `_transient_max_hours` =
  Upload-Frist, E32): `expected_size`, `received_size` mit
  `models.Constraint("CHECK(received_size <= expected_size)")`, Status. Ein
  Transient-Modell braucht eine Zugriffszeile für Nutzer (`ir.model.access.csv`) und
  eine `ir.rule` `create_uid = user.id` (`create_uid` gibt es bei Transient-Modellen
  immer, `_log_access` ist Pflicht; kein eigenes Eigentümerfeld). Sein `unlink` löscht
  die Zwischendatei.
- Es gibt keine Zugriffszeile für Blobs und keinen Fremdschlüssel auf den Inhalt. Der
  Schutz benutzter Inhalte ist der Abgleich des Aufräum-Laufs gegen die Version.

### Ablegen (Reihenfolge, im Abschlussauftrag)

1. Zwischendatei vollständig und mit `fsync` auf der Platte; `os.stat().st_size` muss
   `expected_size` entsprechen, sonst `UserError`.
2. SHA-256 über die Zwischendatei (`hashlib.file_digest`) und Vergleich mit dem
   erwarteten Hash, wenn der Client einen mitschickt.
3. **Zeile der Version anlegen und `flush`** (hält `ROW EXCLUSIVE`, der Aufräum-Lauf
   wartet darauf, V9).
4. **Merkzettel** anlegen oder anfassen (`mtime`).
5. **Datei** per `os.link(tmp, final)`; `FileExistsError` ignorieren (der Inhalt liegt
   schon dort, ein vorhandener Name wird nie angefasst, V13); Zwischendatei löschen;
   `fsync` des Ordners.
6. Commit durch Odoo (Cursor des Auftrags, kein eigener Cursor).

Warum diese Reihenfolge: Die Zeile steht (für den Lauf sichtbar, über die Sperre) vor
der Datei, und der Lauf löscht nur Dateien mit Merkzettel, die älter als die Schonfrist
sind und die keine Tabelle mehr nennt. Ein Upload, der seine Zeile eingefügt hat, wird
vom Lauf erst nach dem Commit gesehen und wartet dazu auf die Sperre (V9, V10); gemessen
mit zehn parallelen Uploads gegen einen Lauf in Dauerschleife: 0 verlorene Dateien
(V12). Stürzt der Prozess vor dem Commit ab, bleibt höchstens eine Datei mit Merkzettel
ohne Version: Der nächste Lauf entfernt sie nach der Schonfrist (V14). Davor bleibt nur
die Zwischendatei, die der Upload-Lauf entfernt.

### Aufräumen

`_gc_content` an `int_filemanager.revision`, `@api.autovacuum`, Name mit `_`, Muster
`ir.attachment._gc_file_store`:

1. **Eigener Cursor** (`with self.env.registry.cursor() as cr`, Kommentar nennt den
   Grund: frischer Snapshot, die Sperre muss die erste Anweisung der Transaktion sein;
   der Core erreicht das mit `cr.commit()` am Cron-Cursor, die Hausregel erlaubt
   `commit` nur im selbst geöffneten Cursor). Darin `SET LOCAL lock_timeout TO '10s'`
   und `LOCK int_filemanager_revision IN SHARE MODE` als erste Anweisung (V9, V12),
   Tabelle über `SQL.identifier`. Gelingt die Sperre nicht (`LockNotAvailable`):
   Rollback, Rückgabe ohne Rest, nächster Lauf.
2. Merkzettel durchgehen, in Stapeln zu `cr.IN_MAX` (nach Alter sortiert, nur Merkzettel
   **älter als die Schonfrist**): Whitelist-Abfrage
   `SELECT sha256 FROM int_filemanager_revision WHERE sha256 IN %s`. Hash gefunden: nur
   den Merkzettel löschen. Nicht gefunden: Datei löschen, dann Merkzettel.
3. Der Commit des eigenen Cursors gibt die Sperre frei (nach jedem Stapel, damit Uploads
   nicht lange warten). Rückgabe wie im Core `(done, remaining)` mit
   `remaining = len(stapel) == cr.IN_MAX`. Ein Stapel ohne Fortschritt zählt nicht als
   "übrig"; eine Ausnahme fängt der Läufer selbst (`ir_autovacuum.py`,
   `_run_vacuum_cleaner`), rollt zurück und stellt die Methode nicht neu an.

**Löschwege markieren:** `Revision.unlink` schreibt vor dem Löschen für jede betroffene
Version den Merkzettel (Muster `ir.attachment.unlink` → `_file_delete`, E31).
`Node.unlink` sammelt die Versionen aller Knoten im Teilbaum über `child_of` und
markiert sie, bevor die Kaskade im Datenbankserver sie entfernt (E33). Kopieren und
Wiederherstellen brauchen keinen Sonderweg: Der Merkzettel des Löschens wird durch die
Schonfrist überbrückt (V11).

**Schonfrist** (`int_filemanager.content_gc_grace_hours`, Standard 24, Mindestdauer 1;
ein Wert darunter oder ungültig fällt mit Warnung auf den Standard zurück): Sie wirkt
auf das Alter des Merkzettels und ist **Pflicht**: Ohne sie geht eine Datei verloren,
wenn eine Kopie gelesen, die Quelle gelöscht und der Lauf dazwischen gelaufen ist, bevor
die Kopie ihre Zeile einfügt (V11). Eine Kopie, die länger als die Schonfrist braucht,
könnte die Datei verlieren (Kopien dauern Millisekunden).

Offene Uploads und Zwischendateien älter als die Upload-Frist (Standard 7 Tage) entfernt
der Autovacuum des `TransientModel` (E32); sein `unlink` löscht die Zwischendatei.

### Auslieferung

`http.Stream(type='path', path=…, size=…, etag=<sha256>, mimetype=…, last_modified=…)`
wie in `ir.attachment._to_http_stream`; der Pfad entsteht über die Hash-Prüfung und
`safe_join` unterhalb von `filestore/<db>/int_filemanager`. Vorher prüft der Controller
`version.check_access("read")`. Nutzer haben keinen Zugriff auf Dateien oder Hashes ohne
diesen Weg. Damit ein großer Download keinen Worker bindet: Odoo mit `--x-sendfile` und
in nginx eine interne Stelle
`location /web/filestore { internal; alias <data_dir>/filestore/; }`
(`http.py:669-674`); der Pfad liegt unter `data_dir/filestore`, die Übergabe greift
also.

### Upload

Modell `int_filemanager.upload` (laufender Vorgang: Eigentümer = `create_uid`, Ziel,
`expected_size`, `received_size`, Status). Es gibt keinen Operationsschlüssel: Die
Wiederholung wirkt über den Status (offen, wird abgeschlossen, fertig) und die
Zeilensperre. Aufrufe:

- `upload_init` (Ziel, erwartete Größe, optional Hash): prüft Recht und Gesamtgrenze,
  legt Zeile und Zwischendatei an. Der Client merkt sich die `upload_id`; ein
  wiederholtes `upload_init` ohne sie legt eine zweite Zeile an, deren Rest der
  Autovacuum entfernt.
- Teil senden (HTTP-Route, `csrf=True` als Voreinstellung; der Client ruft Odoos
  `file_upload_service.upload(route, [Teil], {buildFormData})` je Teil auf: Multipart
  mit Feld `ufile`, dazu `upload_id` und `offset` im Formular, das CSRF-Token fügt der
  Dienst selbst ein; Teile von 8 MiB, E35, V17–V20). Der Server liest `ufile` wie
  `mail_attachment_upload`; Werkzeug hat das Teil bis dahin als suchbare Spool-Datei auf
  die Platte gelegt. **Reihenfolge im Handler:** (1) Zeile mit `SELECT … FOR UPDATE`
  sperren, `lock_timeout 5 s` (Sperr- und Serialisierungsfehler wiederholt Odoo und
  spult das Teil selbst zurück, `service/model.py:196-206`, V19); (2) `offset` mit
  `received_size` vergleichen (kleiner: ignorieren; größer: ablehnen); (3) Zwischendatei
  öffnen, `truncate(received_size)` und `seek`, `ufile.stream` hineinkopieren und
  `fsync` (deckt den Absturz zwischen Anhängen und Fortschreiben ab); (4)
  `received_size` fortschreiben. Ein Teil, dessen Körper abbricht, erreicht den Handler
  nicht (V20); der Client fragt den Stand ab und sendet neu. Ein Teil größer als der
  Parameter für die Teilgröße wird abgelehnt. Nicht `request.httprequest.stream` und
  nicht `get_data()` für den Körper verwenden (V17, V18). Die Gesamtfortschrittsanzeige
  über alle Teile ist Eigenbau (der Dienst zeigt Fortschritt je Teil).
- `upload_status`: `received_size` und Status für das Fortsetzen und den Abschluss.
- `upload_finish`: setzt den Status "wird abgeschlossen" und stößt den Abschlussauftrag
  an (`ir.cron._trigger()`); ein wiederholter Aufruf bei Status "wird abgeschlossen"
  oder "fertig" liefert denselben Stand. Der Auftrag (Cron, `_commit_progress`) prüft
  die Größe, hasht, legt ab (siehe oben) und legt die Version an; das Ergebnis steht im
  Status des Uploads, der Client fragt es per `upload_status` ab (ohne Bus-Meldung: das
  Abfragen braucht der Client ohnehin, etwa nach einem Neuladen). Damit gilt nicht das
  Proxy-Zeitlimit (90 s auf dem Tower). Der Abschluss läuft aber unter dem Zeitlimit des
  Crons: `limit_time_real_cron` folgt standardmäßig `limit_time_real` (Standard 120 s,
  Tower 1800 s), und das Hashen lässt sich nicht stückeln (der Zustand von `hashlib` ist
  nicht speicherbar). Für den echten Bestand muss das Limit des Crons über der
  Kaltlesezeit der größten Datei liegen (5 GiB am Array rund 2 Minuten).

### Sicherung

- Kleine Bestände: Odoos Datenbank-Manager (`zip` mit Filestore, `dump_db` kopiert den
  Filestore erst in einen Ordner und zippt ihn; Platzbedarf etwa das Doppelte, Dauer
  proportional).
- Große Bestände (Terabyte): `backup_format="dump"` ohne Filestore
  (`/web/database/backup`, `filestore=False`) für die Datenbank; der Ordner
  `int_filemanager` wird per Dateiabgleich (rsync oder Snapshot) gesichert. Das ist
  einfach, weil Inhalte nach Hash benannt und unveränderlich sind. Beim Wiederherstellen
  kommen Dump und Ordner getrennt zurück.
- `duplicate_database` kopiert den ganzen Filestore (`shutil.copytree`); für große
  Bestände ist ein Test-Duplikat nur mit eigener Anleitung sinnvoll.

## Project Structure

### Documentation (this feature)

```text
specs/003-blob-ansatz/
├── spec.md
├── research.md
├── plan.md
├── messungen/option_d_rennen.py
└── checklists/requirements.md
```

### Source Code (Entwurf für eine Umsetzung bei null)

```text
int_filemanager/
├── content_store.py                     # Pfade, Hash-Prüfung, Merkzettel, Ablegen per os.link, Lesen (reine Funktionen auf dem Filestore)
├── models/int_filemanager_revision.py   # sha256, size, Hexformat-Prüfung; unlink markiert; _gc_content (@api.autovacuum)
├── models/int_filemanager_upload.py     # TransientModel; Abschlussauftrag
├── controllers/int_filemanager_content.py   # Auslieferung (Stream) und Teil-Upload per HTTP
├── security/                            # Zeilenrechte an der Version und am Upload
├── data/                                # Systemparameter: Maximum, Teilgröße, Schonfrist, Upload-Frist; Cron für den Abschluss
└── tests/
    ├── test_content_store.py            # Hash-Prüfung, Ablegen, Duplikat, Pfadsicherheit
    ├── test_content_upload.py           # Fortsetzen, Duplikate, Lücke, Abschneiden, falsche Größe, falscher Hash, Wiederholung
    ├── test_content_gc.py               # Schonfrist am Merkzettel, referenziert/unreferenziert, Kaskade vom Knoten, Stapel, Schutztest (nur die Version hat `sha256`), Autovacuum läuft einmal

tools/blob_races/                        # Echtprozess-Skripte, bewusst nicht `test_*` und nicht unter `tests/` (Odoos `test_test_holes` verlangt, dass jede `test_*.py` dort importiert ist): zehn gleiche Uploads, Absturz an den Haltepunkten, Aufräumen gegen Schreiben
```

`content_store.py` vermeidet die Verwechslung mit Odoos `ir.attachment`-Filestore.
Dateiname = voller Modellname.

## Tests (aus der Spezifikation)

| Test                                                                                                                                                                    | Belegt                 |
| ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------- |
| 10 parallele Uploads desselben neuen Inhalts (echte Prozesse): genau eine Datei, zehn Versionen, kein Fehler                                                            | SC-002, FR-002, V12    |
| Absturz nach Zwischendatei, nach Zeile, nach Merkzettel, nach Ablegen, vor Commit (`os._exit`)                                                                          | SC-004, FR-014, V14    |
| Aufräumen läuft, während ein Upload denselben Inhalt abschließt (an jeder Stelle des Ablegens): nichts geht verloren; Negativkontrolle ohne `LOCK` schlägt fehl         | FR-014, V9, V10, V12   |
| Kopie einer Version gegen Löschen der Quelle und einen Lauf dazwischen: ohne Schonfrist ginge die Datei verloren, mit Schonfrist bleibt sie                             | FR-013, FR-014, V11    |
| Teil abgebrochen mitten im Körper, Absturz zwischen Anhängen und `received_size`: nächster Teil ergibt trotzdem eine richtige Datei; falsche Gesamtgröße wird abgelehnt | FR-007, FR-009         |
| Knoten löschen (Kaskade im Datenbankserver): Datei verschwindet erst nach der Schonfrist ab der Markierung                                                              | FR-013, SC-006, E33    |
| Datei mit Verweis einer Version bleibt, Datei ohne Verweis nach der Schonfrist wird entfernt                                                                            | FR-013, SC-006         |
| Schutztest: Kein anderes Modell als die Version hat eine Spalte `sha256`                                                                                                | FR-013                 |
| Der Autovacuum `_gc_content` läuft je Lauf genau einmal (nicht je erbender Tabelle)                                                                                     | FR-014                 |
| 3-GB-Upload mit Abbruch und Fortsetzen, Speichergrenze; Abschluss im Hintergrund nach Kaltlesung                                                                        | SC-001, FR-006, SC-008 |
| Manipulierter Hash in Eingabe, Datenbank und Merkzettel                                                                                                                 | SC-007, FR-005         |
| Ablegen: vorhandener Endname wird nie angefasst, Leser sehen nie einen fehlenden Namen                                                                                  | FR-003, V13            |
| Teilabruf und `If-None-Match`                                                                                                                                           | SC-005, FR-012         |
| Sicherung und Wiederherstellung über Odoos Verfahren (Zip und `dump` plus Ordner)                                                                                       | SC-003                 |
| Größe über 2 GiB in der Datenbank                                                                                                                                       | FR-004                 |
| Teil-Route ohne CSRF-Token wird abgelehnt, fremder Upload wird abgelehnt                                                                                                | FR-011                 |

## Complexity Tracking

| Abweichung                                                                                     | Warum nötig                                                                                                                                                                                            | Einfachere Alternative abgelehnt, weil                                                        |
| ---------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------- |
| Eigener Dateispeicher statt `ir.attachment`                                                    | `file_size` ist `int4`, `create` ignoriert `store_fname`/`checksum`/`file_size`, Inhalt nur als Bytes im Speicher, SHA-1 (E1–E3)                                                                       | `Binary(attachment=True)` und `ir.attachment` stellen 5 GB nicht dar                          |
| Hash an der Version statt Blob-Tabelle (D')                                                    | spart Tabelle, eigenen Cursor, `ON CONFLICT`, Savepoints und den Anlege-Wettlauf (V1, V8); die Lücken gegen D (Löschen markiert nichts, mehrere Tabellen) sind mit Core-Mitteln gelöst (E31, E33, E34) | Blob-Tabelle mit Fremdschlüssel (C) ist mehr Eigenbau, als Odoo nötig macht                   |
| Schutztest: nur die Version hat eine Spalte `sha256`                                           | Eine zweite Tabelle mit eigenem Hash bliebe dem Lauf unsichtbar; die Regel "spätere Tabellen verweisen per Many2one auf die Version" wird so erzwungen                                                 | ohne Test wäre die Lücke unentdeckt                                                           |
| Eigener Cursor im Aufräum-Lauf                                                                 | Die Sperre muss die erste Anweisung der Transaktion sein; Hausregel: `commit` nur im selbst geöffneten Cursor (der Core committet am Cron-Cursor)                                                      | `cr.commit()` am Cron-Cursor wie `ir.attachment._gc_file_store`: verstößt gegen die Hausregel |
| Eigenes Chunk-Protokoll (Ablauf init, Stand, Teile, Abschluss) auf Odoos `file_upload_service` | der Core hat keines (E10, E35); 128 MiB je Anfrage (E4)                                                                                                                                                | ein einziger Multipart-POST scheitert über 128 MiB und lässt sich nicht fortsetzen            |
| `os.link` zum Ablegen                                                                          | der Core schreibt direkt und nicht atomar (E9); auf dem Tower-Dateisystem sieht ein Leser nach `os.replace` auf einen vorhandenen Namen kurz einen fehlenden Namen (V13)                               | `os.replace` oder direktes Schreiben wie im Core                                              |
| Eigener Merkzettel-Ordner neben dem des Cores                                                  | der Core räumt nur seinen Ordner (E6); ein eigener Ordner vermeidet Eingriffe                                                                                                                          | gemeinsame Liste würde Odoos Aufräumen mit fremden Namen belasten                             |
| Schonfrist am Merkzettel                                                                       | ohne sie geht bei Kopie gegen Löschen gegen Lauf die Datei verloren (V11)                                                                                                                              | der Core hat sie nicht; D' braucht sie wegen der Kopie                                        |
| Tabellensperre beim Aufräumen (`SHARE MODE`, Lock-Timeout) auf der Version                     | Core-Muster (E6); macht Prüfung und Löschen gegenüber gleichzeitigen Uploads zu einem Schritt (V9, V12)                                                                                                | Aufräumen ohne Sperre: 6 von 12 Runden verlieren Dateien (V12, Negativkontrolle)              |
| Hintergrundauftrag für den Abschluss                                                           | Hashen und Ablegen einer 5-GB-Datei kann bei kalter Platte das Proxy-Zeitlimit überschreiten (V5, V6)                                                                                                  | Abschluss im Request ist nur im warmen Fall belegt                                            |

## Offene Punkte

- **Transport der Teile (entschieden 2026-10-06):** **HTTP-Route je Teil als Multipart
  über `file_upload_service`** (nicht Rohkörper, nicht RPC mit Base64). Gemessen:
  Speicher flach, Wiederholung und CSRF ohne Sonderweg, abgebrochene Teile erreichen den
  Handler nicht (V18–V20); der Rohkörper ist in Odoo nur über `get_data()` lesbar und
  behält etwa die ganze Datei (V17, V18). Der Proxy des Towers lässt 2000 MB je Anfrage
  zu, das Standardlimit von 128 MiB genügt. Auf HM-SRV ist die Proxy-Einstellung nicht
  geprüft (nicht erreichbar). Teilgröße 8 MiB bleibt: `fsync` je Teil kostet auf dem
  SSD-Cache 174 MiB/s, am Array 38 MiB/s gegen 43–45 MiB/s Plattengrenze (V22, V23);
  größere Teile gewinnen kaum, Teile unter 4 MiB lohnen sich nicht.
- **Ansatz D' (entschieden 2026-10-06):** Hash an der Version statt Blob-Tabelle;
  Spezifikation, Plan und Recherche sind umgeschrieben, nichts committet.
- **Echtprozess-Test** im Odoo-ORM mit zwei Workern (`flush`, `unlink`-Überschreibungen,
  Abgleich unter Last) und die Last bei hunderttausenden Merkzetteln sind noch nicht
  gemessen.
