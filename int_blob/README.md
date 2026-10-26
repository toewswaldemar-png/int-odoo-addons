# int_blob

Odoos Anhangsspeicher (`ir.attachment` mit Filestore) bekommt eine Ergänzung: den Upload großer Dateien als Strom. Alles andere bleibt beim Kern. **Status: `_create_from_stream` ist gebaut; 35 Tests und ein Test mit 2 GiB laufen grün auf einer Wegwerf-Instanz (Odoo 19). Noch von keinem Modul benutzt.**

## Ziel

Gemeinsame Grundlage für Module, die Dateien ablegen. Das Modul hängt nur von `base` ab, damit jedes andere Modul es gefahrlos nutzen kann.

## Prinzip

`ir.attachment` bleibt der Speicher. `int_blob` erweitert es per `_inherit` nur um **ein Feld und zwei Methoden** und überschreibt keine Methode des Kerns:

| Am Modell | Wofür |
|---|---|
| Feld `int_blob_size` (bigint) | wahre Größe, auch über 2 GiB |
| `_create_from_stream` | der Upload als Strom |
| `_gc_int_blob_uploads` | räumt liegen gebliebene Zwischendateien ab |

Die Schritte dazwischen (`store_stream`, `publish`, `set_row`, `blob_fname`) sind einfache Funktionen des Moduls und stehen nicht im Namensraum von `ir.attachment`.

```
 Modul (eigenes Modell, eigene Rechte, eigene Oberfläche)
        │  zeigt auf (res_model, res_id, res_field)
 int_blob                             nur: Datei als Strom ablegen
        │  _inherit
 ir.attachment + Filestore (Kern)     Ablage, Aufräumen, Download, Rechte, Dateityp
```

| Aufgabe | Zuständig |
|---|---|
| Ablage im Filestore (Name = SHA-1) | Kern |
| Aufräumen verwaister Dateien | Kern (`_gc_file_store`, Merkzettel `checklist`) |
| Download als Strom | Kern (`_to_http_stream`) |
| Rechte | Kern: der Anhang folgt dem Besitzer-Datensatz |
| Dateityp | Kern (`_check_contents`) |
| **Upload als Strom (nicht im Speicher)** | **`int_blob`** |
| **Größe über 2 GiB** | **`int_blob`**: eigene 64-Bit-Spalte `int_blob_size` |

Der Kern liest beim Schreiben die ganze Datei in den Speicher (`_file_write(bin_value, checksum)`). Das Lesen streamt schon: `_to_http_stream` gibt bei `store_fname` einen Pfad-Stream zurück.

## Der Besitzer

Jeder Anhang trägt `res_model`, `res_id` und optional `res_field`.

- Wer den Besitzer-Datensatz lesen darf, darf auch die Datei lesen (`ir.attachment._check_access`).
- Ohne Besitzer ist der Anhang nur für Ersteller und Administrator sichtbar. Der Besitzer muss also **vor dem Upload existieren**.
- Mit `res_field` findet das `fields.Binary(attachment=True)` des Besitzers die Datei selbst, eine pro Feld und Datensatz.
- Rechte entstehen am Besitzer (gewöhnliche `ir.rule`, Gruppen, Feldrechte). `int_blob` hat kein eigenes Rechtesystem.

## Die Methode

```python
env["ir.attachment"]._create_from_stream(
    stream, name, res_model, res_id, res_field=False, mimetype=None, check=None
)
```

1. Zwischendatei im Filestore schreiben, Block für Block (SHA-1 und Größe laufen mit). Eine Größenbegrenzung gibt es nicht.
2. Dateityp mit dem Kern bestimmen (`_check_contents` mit Name und Dateikopf).
3. Zeile in `ir_attachment` leer anlegen (`create` ohne Inhalt, mit `res_model`, `res_id`, `res_field`, `mimetype`), dann `store_fname`, `checksum`, `file_size` und `int_blob_size` mit dem `write` des Basismodells setzen (`super(IrAttachment, …).write`, wie `_set_attachment_data`) und flushen. `create` und `write` des Kerns verwerfen diese drei Felder.
4. Datei an ihren Platz verschieben: Ist der Platz belegt, den Inhalt prüfen und die Zwischendatei löschen; sonst vorher auf den Merkzettel (`_mark_for_gc`), dann verschieben. `_get_path(bin_data, sha)` des Kerns braucht die ganze Datei im Speicher und fällt für den Vergleich aus: Pfad mit `_full_path` bilden, Inhalt blockweise vergleichen.

Bei Abbruch räumen Rollback, Merkzettel und eine Altersgrenze für Zwischendateien auf (`_gc_int_blob_uploads`, 24 Stunden, Parameter `int_blob.upload_max_age_hours`).

Vor dem ersten gelesenen Byte wird geprüft: Speicherort ist der Filestore (`location = file`), der Besitzer existiert, der Aufrufer darf ihn schreiben (`check_access("write")`). Der Pfad im Filestore entsteht nur aus einer SHA-1 (`_int_blob_fname`, `ValueError` bei allem anderen), nie aus einer Eingabe. Mit `res_field` ersetzt ein zweiter Aufruf die Datei derselben Zeile; der alte Blob kommt auf den Merkzettel.

## Die Größe

Der Kern speichert die Größe in `ir_attachment.file_size`, einer 32-Bit-Spalte: 2 GiB und mehr passen nicht hinein (belegt, `integer out of range`).

- `int_blob` hängt per `_inherit` eine **eigene** Spalte `int_blob_size` (bigint) an `ir.attachment`. Sie trägt bei jeder von `int_blob` gespeicherten Datei die wahre Größe, bei allen anderen Anhängen ist sie 0.
- `file_size` bekommt `min(Größe, 2**31 − 1)`, bei Dateien ab 2 GiB also den Höchstwert. Wer die Größe braucht, liest `int_blob_size or file_size`.
- Der Kern benutzt `file_size` nur zur Anzeige, zum Summieren der Größe von Mail-Anhängen, beim Vergleich in `create_unique` und im Bericht von `cloud_storage_migration`. Der Download liest die Größe nicht daraus, sondern per `stat` von der Datei.
- Die Spalte des Kerns bleibt unverändert. Ein Versuch, sie im Modul auf `bigint` zu stellen, lief bei Installation und bei `-u base` sauber, scheiterte aber nach der Deinstallation: Der Kern wandelt die Spalte zurück auf `int4`, und mit einem Wert über 2 GiB (`integer out of range`) lädt die Datenbank nicht mehr. Eine Spalte, die das Modul selbst anlegt, entfernt Odoo beim Deinstallieren selbst.

## Nicht enthalten

Ordner, ZIP, Freigaben, Vorschau, OCR, Versionen, Menüs, Ansichten, eigene Tabelle, eigene Rechte, Referenzzähler.

## Belegt auf einer Wegwerf-Instanz

Aufruf: `TESTS_MODULE=int_blob tools/check/tests.sh` (frische Datenbank auf der Test-Instanz, Odoo 19). 35 Tests, alle grün; dazu einer auf Abruf.

**`tests/test_core_assumptions.py` (9):** was das Konzept vom Kern annimmt.

| Annahme | Ergebnis |
|---|---|
| Das Binary-Feld findet einen von Hand angelegten Anhang | belegt (`res.partner.image_1920`) |
| Anhang mit `res_field` bleibt aus der gewöhnlichen Suche | belegt (nur mit `skip_res_field_check` sichtbar) |
| Rechte folgen dem Besitzer; ohne Besitzer nur Ersteller und Admin; Besitzer ohne Zugriff sperrt | belegt (interner Benutzer) |
| Merkzettel: markierte Datei ohne Zeile wird entfernt, mit Zeile bleibt sie | belegt (`_gc_file_store_unsafe`) |
| `_check_contents` bestimmt den Typ aus Name und Dateikopf | belegt (mp3, png) |
| Name = SHA-1, `sha[:2]/sha`; andere Datei am selben Platz wird abgelehnt | belegt (`UserError`) |
| `ir_attachment.location = db`: keine Datei, Daten in `db_datas`, Aufräumer tut nichts | belegt |
| `create` und `write` verwerfen `store_fname`, `checksum`, `file_size` | belegt; `write` entfernt sie dazu aus dem übergebenen Dictionary |
| `file_size` ist `int4`, 2 GiB und mehr passen nicht | belegt (`NumericValueOutOfRange`) |

**`tests/test_stream.py` (26):** was die Methode tut.

| Behauptung | Test |
|---|---|
| Die Zeile ist dieselbe, die der Kern bei `create(raw=…)` macht (`store_fname`, `checksum`, `file_size`, `mimetype`), die Datei ist byte-gleich | ja |
| Das Binary-Feld liest die Datei; Typ aus Name und Dateikopf; HTML bekommt denselben Typ wie beim `create` des Kerns (für Admin und Nicht-Admin verglichen) | ja |
| 400 MB wachsen den Speicher um weniger als 64 MiB (gemessen am Prozess, mit echten Daten) | ja |
| Eine Datei über der Spalte des Kerns wird gespeichert: `file_size` bekommt den Höchstwert, `int_blob_size` die wahre Größe, die Datei ist ganz (mit kleiner Grenze getestet) | ja |
| `int_blob_size` ist `bigint`, nimmt 5 GB und wird mit dem Modul entfernt | ja |
| **Auf Abruf** (`--test-tags int_blob_big`, 2,1 GiB Platz): eine Datei von 2 GiB + 5 MiB wird gestreamt, Prüfsumme, Größe in `int_blob_size`, Speicherzuwachs unter 64 MiB | grün (6 s) |
| Abbruch des Stroms, abgelehnte Datei (`check`), Rollback: keine Zwischendatei, keine Zeile; nach Rollback räumt der Kern den Blob ab | ja |
| `location = db`, fehlender oder unbekannter Besitzer: abgelehnt, nichts bleibt zurück | ja |
| Fehlendes Schreibrecht am Besitzer: `AccessError`, **bevor** ein Byte gelesen wird | ja |
| Dieselbe Datei zweimal: ein Blob, zwei Zeilen; erst nach der zweiten Löschung räumt der Kern ab | ja |
| Anderer Inhalt am selben Platz: `UserError`, vorhandene Datei bleibt unverändert | ja |
| Ersetzen im selben Feld: gleiche Zeile, alter Blob wird abgeräumt | ja |
| `_int_blob_fname` nimmt nur eine SHA-1 (`../../etc/passwd`, falsche Längen, Großbuchstaben: `ValueError`) | ja |
| Zwischendateien: alte werden entfernt, frische bleiben | ja |
| Acht gleichzeitige Veröffentlichungen derselben Datei brauchen keine Sperre: alle gelingen, ein Leser sieht nie eine halbe Datei, ein Blob bleibt | ja |
| HTTP: `/web/content/<id>` liefert die Bytes und `Range` (206) | ja |
| HTTP: eine Datei von 3 GiB (Lochdatei) wird mit `Content-Range: bytes 0-9/3221225472` ausgeliefert; die Größe kommt aus der Datei, nicht aus der Spalte | ja |

**Die Tests sind nicht aus Zufall grün.** Drei absichtliche Fehler wurden je von genau einem Test erkannt: Blöcke im Speicher behalten (Speichertest), `os.replace` durch Kopieren ersetzen (Leser sieht halbe Datei), frühe Rechteprüfung entfernen (es wurde schon gelesen). Dabei zeigte sich, dass ein Strom aus Nullen (`bytes(n)`) den Speichertest unwirksam macht, weil unbeschriebener Speicher nicht belegt wird; er nimmt jetzt echte Daten.

**Deinstallation und Update:** `int_blob` deinstalliert (mit 5 GB in `int_blob_size`), danach `-u base`: keine Fehler, `int_blob_size` ist entfernt, `file_size` bleibt `integer`, die Anhänge sind unversehrt.

## Kritische Prüfung

Beim Durchsehen des Codes sind fünf Mängel aufgefallen, jeweils zuerst als fehlschlagender Test belegt und dann behoben:

| Mangel | Folge | Behebung |
|---|---|---|
| Schlägt die Ablage fehl (zum Beispiel Kollision), blieb die Zeile ohne Datei stehen, wenn der Aufrufer den Fehler abfängt und mit der nächsten Datei weitermacht (Import vieler Dateien) | Zeile zeigt auf eine Datei, die es nicht gibt; beim Ersetzen geht die alte Datei verloren | Zeile, Ablage und Löschen der alten Datei laufen in einem Savepoint |
| `res_field` wurde nicht geprüft | Bei Admin entstehen Anhänge mit erfundenem Feld, bei anderen Benutzern sind sie unlesbar | Das Feld muss ein Binary-Feld des Besitzers mit `attachment=True` sein |
| `int_blob_size` konnte jeder Benutzer mit Schreibrecht über RPC setzen | gefälschte Größe; der Kern schützt `file_size` auf dieselbe Weise | **bewusst nicht behoben:** `create` und `write` des Kerns zu überschreiben wäre ein Eingriff in jeden Anhang. Die Größe ist nur Anzeige, der Download liest sie nicht (`stat`); `copy=False` verhindert, dass sie mitkopiert wird |
| Leere Datei legte einen leeren Blob mit Prüfsumme an | Der Kern speichert keine Datei ohne Inhalt (`store_fname` und `checksum` leer) | Ebenso: kein Blob, Zeile wie beim Kern |
| Der Test zur Kollision zeigte den Fehler nicht | `assertRaises` in Odoo rollt zu einem Savepoint zurück und verdeckt, was zurückbleibt | Die Tests fangen die Ausnahme von Hand ab (`catch`) |

**Zurückgebaut:** Ursprünglich überschrieb das Modul `create` und `write` (gegen die Fälschung der Größe) und setzte das Kontext-Flag `attachments_mime_plainxml`. Beides ist weg: Der Dateityp folgt jetzt genau der Regel des Kerns (HTML wird nur für Benutzer ohne Schreibrecht auf Ansichten zu `text/plain`; Test vergleicht mit dem Kern), und `ir.attachment` bekommt keine fremde Logik in `create` und `write`.

**Geprüft und in Ordnung:** Die Funktion für die Zwischendateien wird vom täglichen Vacuum von Odoo eingesammelt (`@api.autovacuum`, Test mit `is_autovacuum`). Die neuen Spalten und Überschreibungen verschwinden bei der Deinstallation; danach läuft `-u base` fehlerfrei.

**Bekannte Einschränkungen (nicht behoben):**

- **Das Feld im Code zu lesen lädt die ganze Datei.** `record.audio` (Binary-Feld) liest über die ORM die gesamte Datei und macht Base64 daraus; gemessen: 150 MiB Datei, 350 MiB mehr Speicher. Große Dateien nur über `_to_http_stream`, `ir.binary` oder den Pfad im Filestore ausliefern, nie über das Feld im Code. Die Oberfläche von Odoo liest das Feld mit `bin_size` (nur die Größe) und lädt nichts.
- **Bilder werden nicht verkleinert oder verarbeitet** (`image_no_postprocess`), anders als beim `create(raw=…)` des Kerns: Es liegt nur der Anfang der Datei vor.
- **Die Größe ist fälschbar:** wer eine Anhangszeile schreiben darf, kann `int_blob_size` setzen (siehe oben).
- **Kein Textindex:** `index_content` bleibt leer, die Volltextsuche im Inhalt (z. B. PDF, Word) findet gestreamte Dateien nicht.
- **Aufrufer mit `sudo()` umgehen die Rechteprüfung** (Besitzer und Feld), wie beim `create` des Kerns. Der Aufrufer muss selbst prüfen.
- **Schreibt der Kern gerade dieselbe Datei** (gleicher Inhalt über den gewöhnlichen Upload, `_file_write` schreibt direkt an den Platz), kann der Vergleich eine halb geschriebene Datei sehen und den Upload mit „collides“ ablehnen. Das ist ein falscher Alarm, kein Datenverlust; ein neuer Versuch klappt.
- **Zwei gleichzeitige Ersetzungen** im selben Feld: die letzte gewinnt, der Blob der anderen kommt auf den Merkzettel und wird vom Kern abgeräumt.
- Die Fehlermeldungen sind noch nicht übersetzt (`i18n/` fehlt).

## Offen

1. **Gleichzeitiger Upload auf mehreren Rechnern und Prozessen:** getestet ist die Veröffentlichung der Datei mit Threads im selben Prozess (atomares `os.replace`); mehrere Worker und Netzdateisysteme sind nicht gemessen. Die Instanz liegt auf einer Unraid-Freigabe, der Lauf dort war grün.
2. **Upload aus dem Browser:** `int_blob` nimmt einen Strom entgegen; für Dateien über 128 MiB (`web.max_file_upload_size`) braucht es einen eigenen Upload-Weg im aufrufenden Modul.
3. **Hash:** SHA-1 wie der Kern.
4. **Später möglich:** austauschbarer Speicherort über `_file_read`, `_file_write`, `_file_delete`; fortsetzbarer Upload in Teilen.
