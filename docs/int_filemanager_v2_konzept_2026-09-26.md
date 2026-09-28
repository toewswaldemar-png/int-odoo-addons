# int_filemanager 2: Odoo als alleiniger Schreiber

Stand 2026-09-26. **Vom Nutzer freigegeben am 2026-09-27.** Umsetzung nach Abschnitt 18, beginnend mit Schritt 3.

**Kurzfassung zum Prüfen und Freigeben: `int_filemanager_v2_kern_2026-09-26.md`.** Dieses Dokument ist die
ausführliche Referenz mit allen Belegen; bei einem Widerspruch gilt dieses Dokument, und der Kern wird angepasst.

**Stand: festgeschrieben am 2026-09-26** (Prototyp-Befunde aus 19 und alle Entscheidungen aus 17 eingearbeitet,
Start ohne Explorer-Zugriff, WebDAV/SMB vorbereitet); **freigegeben am 2026-09-27.**

**Überarbeitet am 2026-09-27:** Befunde A1–A21 der Code-Prüfung (`docs/review/konzept_codepruefung_2026-09-26.md`)
und die Entscheidungen 6–8 eingearbeitet; neue Tests und Messungen in 19.17.

**Überarbeitet am 2026-09-28:** Abschnitt 8 (abgeleitete Dateien: Vorschau, Text, Metadaten, Umwandler) neu gefasst;
Entscheidungen 11–15; neue Grundregel I13; Modell `int_filemanager.derivative` (4), Rechte (12), Tests (16),
Reihenfolge (18). Grundlage: Prüfung des Odoo-19-Cores (Klon `8d05257d`), Vergleich mit FileRun und Cloudreve.

**Entscheidungen des Nutzers (2026-09-26):**
1. Der Dateimanager wird **vollständig als Odoo-Addon** gebaut. Odoo-Bausteine werden genutzt; **selbst gebaut wird
   nur dort, wo Odoo nachweislich an Grenzen stößt.**
2. **Odoo ist alleiniger Schreiber** der Dateiinhalte.
3. Der Bestand wird **kopiert**, nicht per Hardlink übernommen.
4. **Start ohne Explorer-Zugriff:** gearbeitet wird in der Odoo-Oberfläche (Office im Browser über ONLYOFFICE),
   dazu ein **Eingangsordner** für Scanner u. Ä. Ob und wie später ein Netzlaufwerk dazukommt (WebDAV über
   `odoo fmdav` oder SMB über ein Odoo-FUSE-Dateisystem), wird **nach der Nutzung** entschieden (11, Entscheidung
   2026-09-26); **ganzer Share** wird übernommen; Versionen
   **unbegrenzt**; Papierkorb **30 Tage**; Rechte-Bereiche **minimal**; **HM-SRV bleibt vorerst beim heutigen
   Modul** (17).

5. Code nach den Odoo-/OCA-Konventionen (`docs/odoo_konventionen_2026-09-26.md`): **Englisch** in Namen, Kommentaren, Docstrings, Log-Meldungen und Commits (`[TAG] modul: …`); Oberflächentexte englisch im Code, deutsche Übersetzung in `i18n/de.po`. Prüfwerkzeuge: **pre-commit** nach OCA-Vorlage (nur für neuen Code), Odoos **`test_lint`** und **odoo-ls** (Parse-Modus, nur eigene Pfade) auf der Testinstanz; **keine** GitHub Action; Migrationsskripte mit **`odoo/upgrade-util`** (Entscheidung 2026-09-26).
6. **Eingangsordner:** Eine Datei gilt als fertig, wenn Größe und Änderungszeit eine **Ruhezeit** lang unverändert
   sind (11.1) (Entscheidung 2026-09-27).
7. **ZIP-Download:** bis zu einer Grenze direkt gestreamt, darüber als **Hintergrundjob** (8) (Entscheidung 2026-09-27).
8. **Blob-Speicher** auf einem Unraid-Share unter `/mnt/user/<name>` mit Plattenauswahl **disk2 + disk3** und ohne
   Cache (Tower; `link`/`rename` über Plattengrenzen geprüft, 19.17) (Entscheidung 2026-09-27).
9. **Umsetzung im Modul `int_filemanager`** (Version 19.0.2.0.0): neue Modelle neben den alten, bis die Migration
   abgenommen ist, dann alte Teile entfernen. Odoo löscht beim Update die Tabelle eines aus dem Code entfernten
   Modells nicht (`ir.model._drop_table` greift nur für Modelle in der Registry) – Altdaten bleiben für die Migration
   lesbar, Aufräumen danach ausdrücklich per upgrade-util. Entwicklung auf dem Branch `feature/int-filemanager-v2`;
   der Stand des heutigen Moduls wird als Tag `int_filemanager-v1` festgehalten (HM-SRV, Tower-Live bis zur
   Umstellung) (Entscheidung 2026-09-27).
10. **Test-Image** mit eigenem Tag `odoo:19.0-hm-test` (Live-Tag `odoo:19.0-hm` unberührt); **pre-commit** läuft auf
   dem Arbeitsrechner (Entscheidung 2026-09-27).
11. **Abgeleitete Dateien** (Vorschaubilder, Vorschau-PDFs, Text, Metadaten) liegen im **eigenen Blob-Speicher**,
    nicht in `ir.attachment`; Odoo dekodiert sie nie (8.1, 8.9; Entscheidung 2026-09-28).
12. **Erzeugung als Mischform:** dauerhafte Warteschlange in der Datenbank, gedrosselt im Hintergrund; was gerade auf
    dem Bildschirm steht, kommt zuerst (8.4; Entscheidung 2026-09-28).
13. **Zwei Bildgrößen:** Kachel und Vorschau (8.3; Entscheidung 2026-09-28).
14. **Werterkennung** (Muster, extrahierte Werte) bleibt in Odoo, arbeitet nur auf dem Text (9; Entscheidung 2026-09-28).
15. **Umfang Schritt 5 = Kern** (Bilder inklusive HEIC/RAW/TIFF, Video-Standbild, Office, PDF, Scans mit Texterkennung,
    Metadaten, Verwalter-Diagnose); E-Book, 3D, Kontaktbögen u. a. als spätere Erweiterung (8.8; Entscheidung 2026-09-28).

**Grundlage:** Live-Prüfungen auf Tower und Code-Prüfungen im Odoo-19-Core, dokumentiert in
`int_filemanager_konzept_db_vorrang_2026-09-24.md` (Abschnitte 19 und 20). Dort ist belegt, dass fast alle Fehler
des heutigen Moduls aus dem Betrieb über lesbaren, **von außen beschriebenen** Ordnern entstehen (Watcher, Scan,
rohes SQL, Dateizugriffe neben der DB). Dieses Konzept beseitigt die Ursache, statt die Symptome zu flicken
(Umbau-Regel 7 im DB-Vorrang-Konzept).

---

## 1. Ziel und Abgrenzung

Ein Dateimanager in Odoo, der Dateien, Ordner, Versionen, Papierkorb, Rechte, Vorschau, Suche, OCR und
Geschäftsbezug in **einem** System vereint. Alles, was Odoo mitbringt (Nutzer, 2FA, Gruppen, Rechte, Transaktionen,
Crons, Oberfläche, Chatter, Aktivitäten, E-Mail, Portal, Geschäftsobjekte), wird genutzt und nicht nachgebaut.

**Nicht Ziel:** direkter SMB-Schreibzugriff auf die Dateien. Er ist die Wurzel der heutigen Probleme und mit
"Odoo als alleiniger Schreiber" unvereinbar. Zum Start wird ohne Explorer-Zugriff gearbeitet; ein späteres
Netzlaufwerk läuft in jedem Fall durch Odoo (Abschnitt 11).

## 2. Invarianten

Grundregeln, die **immer** gelten, unabhängig von Funktion, Fehlerfall, Absturz oder Last. Jede neue Funktion und
jede Änderung wird dagegen geprüft; jede Invariante hat Tests (Abschnitt 16).

| # | Invariante | verhindert (Befund) |
|---|---|---|
| I1 | **Nur Odoo schreibt in den Blob-Speicher.** Kein Mount, keine Freigabe mit Schreibrecht, kein anderes Programm. | Überlauf, Identitätsverlust Word/Excel, Geisterzeilen, NFD, P10 |
| I2 | **Ein Blob wird nie verändert.** Neuer Inhalt = neuer Blob; der Name ist der SHA-256 des Inhalts. | stilles Überschreiben, falsche ETags |
| I3 | **Erst die DB, dann die Wirkung nach außen.** Vor dem Commit werden nur Blobs angelegt (harmlos bei Abbruch); alles andere Externe (E-Mail, Umwandler, WebDAV-Antworten mit Folgen) erst danach. | B2 |
| I4 | **Bytes werden nie vor ihrer DB-Zeile gelöscht**, nur durch den Aufräumjob, wenn keine Revision mehr auf den Blob verweist **und** die Schonfrist seit seiner letzten Verwendung abgelaufen ist; im Zweifel wird nicht gelöscht (5). | B14, Prüfung A4 |
| I5 | **Nichts wird gelöscht, weil etwas nicht beobachtet wurde.** Es gibt keinen Watcher und keinen Scan, der Zeilen entfernt. | B1, B13 |
| I6 | **Jede bestätigte Änderung ist wiederherstellbar.** Jede ersetzte Fassung bleibt als Version erhalten (Aufbewahrung konfigurierbar, Löschen nur per Regel). | B5, B6 |
| I7 | **Rechte werden ausschließlich über Odoos Rechtesystem geprüft** (`ir.model.access`, `ir.rule`) – für **jedes** Modell des Moduls, nicht nur den Knoten, und für **jeden** Zugriffsweg (Oberfläche, `call_kw`, JSON-2, Routen, `/web/image`, Freigabe-Links). Kein `sudo()` in einem nutzererreichbaren Pfad, bevor die Prüfung unter der Nutzeridentität abgeschlossen ist; danach nur eng begrenzt (12). | N1, Prüfung A1/A2 |
| I8 | **Verweise gehen über IDs, nie über Pfade.** Pfade sind abgeleitete Anzeige. | B7 |
| I9 | **Der sichtbare Zustand jedes Schreibvorgangs wird in einer PostgreSQL-Transaktion geschrieben** – ganz oder gar nicht. Blobs, die vor einem gescheiterten Commit entstanden sind, dürfen liegen bleiben und werden später sicher entfernt (I4). Wiederholungen (Doppelklick, erneutes Senden, Konflikt zweier Worker) erzeugen keine Doppelungen: Vorgangs-ID, Eindeutigkeit durch die DB, Konflikte werden ausdrücklich behandelt (6). | B2, P3, Prüfung A3 |
| I10 | **Der Odoo-Core wird nicht verändert oder gepatcht.** Erweiterung nur über dokumentierte Mechanismen (Vererbung, Hooks, Routen, Auth-Methoden, CLI-Befehle aus Addons). | Update-Brüche |
| I11 | **Native Bibliotheken für fremde Dateiformate laufen außerhalb des Odoo-Prozesses.** | Abstürze und Speicherfresser im Odoo-Prozess, Pillow-Beschränkung |
| I12 | **Keine Dateibytes im RAM des Odoo-Prozesses** über eine feste Grenze hinaus; Übertragung per Streaming und `x_sendfile`. | 128-MiB-Grenze, RAM |
| I13 | **Odoo öffnet und dekodiert keine Dateibytes fremder Herkunft** – weder Originale noch Ergebnisse des Umwandlers. Abgeleitete Dateien werden nur gespeichert und ausgeliefert; sie liegen im Blob-Speicher, nicht in `ir.attachment` (8.9). | Bild- und PDF-Parser im Odoo-Prozess (Pillow in `_check_contents`, `_index`, `image_width`, `/web/image`, `pdf_first_page`) |

## 3. Architektur

```text
 Browser / ONLYOFFICE              [später, optional: Netzlaufwerk über odoo fmdav oder SMB+FUSE, 11]
        │                                  │
        ▼                                  ▼
 nginx (HTTPS) ── X-Accel (Auslieferung der Blobs direkt von der Platte)      Eingangsordner (Samba, nur
                                                                                hineinlegen) ──► Import-Cron
        │  /                               │  /dav
        ▼                                  ▼
 Odoo (Prefork, workers>0)          odoo fmdav (11): derselbe Code, eigener Prozess/Container,
 ├─ Oberfläche (OWL)                 WsgiDAV + Thread-Server, ORM direkt (Registry, Cursor,
 ├─ Routen: Upload (Stücke),         retrying), Rechte des angemeldeten Nutzers
 │  Download (Stream),                     │
 │  ONLYOFFICE-Callback                    │
 ├─ Crons: Vorschau/OCR, Aufräumen         │
 │  (Blobs, Uploads, Temp-Dateien)         │
 └─ Modelle + Rechte ─────────── gemeinsam: int_filemanager.node, int_filemanager.revision, int_filemanager.blob, int_filemanager.derivative, int_filemanager.scope, int_filemanager.upload,
                                  (mit WebDAV: .dav_lock, .dav_prop), Tags, Status, OCR-Werte; ir.model.access + ir.rule
        │                               │
        ▼                               ▼
 PostgreSQL (C-Kollation)        Blob-Speicher (Array-Share, nur Odoo-Prozesse schreiben)
                                        ▲
 Umwandler-Container (vips, ffmpeg, LibreOffice, Pillow voll, OCR) ── liest Blobs, liefert Vorschaubilder, Text und Metadaten an Odoo
```

## 4. Datenmodell

Modellnamen mit Modulpräfix `int_filemanager.` (Odoo Coding Guidelines, `docs/odoo_konventionen_2026-09-26.md`;
Entscheidung 2026-09-26). In den Prototypen (Abschnitt 19) hießen die Modelle noch `fm.*`, die Tabellen `fm_*`.

| Modell | Zweck | Wesentliche Felder / Regeln |
|---|---|---|
| `int_filemanager.node` | Ordner und Dateien (Verzeichniseintrag) | `name`, `parent_id` (`_parent_store`), `is_dir`, `active`, `removal_reason` (`trash`), `scope_id`, `current_revision_id`, `size`, `mime`, `tag_ids`, `status_id`, `partner_id`, `mail.thread`; für WebDAV `vacated_parent_id`/`vacated_name`/`vacated_at`/`vacated_uid` und `shadow_of_id` (Identitätsregel, 11). **Teil-Unique-Index** `(parent_id, lower(name COLLATE "und-x-icu")) NULLS NOT DISTINCT WHERE active` über `models.UniqueIndex`: Name je Ordner **ohne Rücksicht auf Groß/Klein** eindeutig wie unter Windows (19.4; geprüft: `größe.TXT` neben `Größe.txt` abgelehnt, `GRÖSSE.txt` erlaubt wie auf NTFS), Papierkorb blockiert nicht. `NULLS NOT DISTINCT`, weil PostgreSQL leere Eltern sonst als verschieden zählt und gleichnamige Wurzelknoten zuließe (19.17, A6). Namenssuchen nutzen denselben Ausdruck, damit der Index greift. Pfad nur berechnet/zur Anzeige. **Jede Datei hat eine aktuelle Revision, auch eine leere** (Revision auf den 0-Byte-Blob, A7); die Sonderregel für den leeren Vorab-`PUT` des Windows-Explorers gehört in die WebDAV-Schicht (11.2). |
| `int_filemanager.revision` | eine Fassung einer Datei | `node_id`, `revision_no`, `blob_id`, `size` (`Float`, 19.2), `origin` (`upload`, `webdav`, `office`, `edit`, `restore`, `import`), `create_uid`, `create_date`, `operation_id`. Nie verändert. |
| `int_filemanager.blob` | Inhalt | `sha256` (eindeutig), `size` (**`Float`**, weil `fields.Integer` `int4` ist, 19.2), `state` (`present`), `last_used` (bei jeder Verwendung im Abschluss-Commit gesetzt; Grundlage der Schonfrist, 5). Anlegen im Savepoint, bei `UniqueViolation` die vorhandene Zeile nehmen (zwei Worker mit gleichem Inhalt, 6). Speicherort aus dem Hash abgeleitet, nicht gespeichert. |
| `int_filemanager.derivative` | abgeleitete Daten zu einem Blob (Vorschaubild, Vorschau-PDF, Text, Metadaten) | Einzelheiten 8.3. Für Nutzer **kein** Zugriff. |
| `int_filemanager.scope` | Rechte-Bereich | `name`, `read_group_ids`, `write_group_ids`, `manage_group_ids`, `purge_group_ids`. Knoten erben den Bereich des nächsten Ordners mit eigenem Bereich (gespeichert, beim Verschieben per ORM für den Teilbaum gesetzt). |
| `int_filemanager.upload` | laufender Upload in Stücken | `operation_id` (eindeutig), `create_uid`, Zielordner/-datei, erwartete Größe (`Float`, unbekannt erlaubt), bisherige Größe, Temp-Datei, `state` (`open`, `processing`, `done`, `failed`), Ablauf. |
| `int_filemanager.dav_lock` (erst mit WebDAV) | WebDAV-Sperren | `token` (eindeutig), `root` (Pfad, wie WsgiDAV sperrt), `data` (Sperre als JSON), `expire`; zusätzlich `node_id` für die Anzeige in der Oberfläche ("wird in Word bearbeitet") und ONLYOFFICE. In der DB, damit alle Prozesse sie sehen und ein Neustart sie nicht verliert (19.7, 19.10). LOCK/UNLOCK über `pg_advisory_xact_lock` serialisiert. |
| `int_filemanager.dav_prop` (erst mit WebDAV) | tote WebDAV-Eigenschaften | `node_id` (Kaskade), `name`, `value`; an der Knoten-ID, übersteht Verschieben (I8). Windows-Zeitstempel werden nicht gespeichert (Änderungsdatum = Revision). |
| `int_filemanager.operation` | Vorgangs-IDs | `key` (eindeutig), Ergebnis. Doppelte Anfragen liefern das gespeicherte Ergebnis. |
| bestehend | Tags, Status, Extraktionsmuster, extrahierte Werte, Freigabe-Log | werden auf `int_filemanager.node` umgehängt. |
| Geschäftsbezug | Mixin für Geschäftsobjekte | heute `int_filemanager.linkable.mixin` fest auf `partner_id`. Künftig generisch (`res_model`/`res_id`-Verknüpfungen mit Rechteprüfung nach dem Muster von `mail.activity`: `_check_access` **und** `_search` überschreiben, `exists()` vor der Prüfung – beides dort vorhanden). Zusätzlich ein **eigener** Aufräumjob für per DB-Kaskade gelöschte Ziele (`mail.activity` hat keinen, es überspringt solche Ziele nur, A16). `_check_access` ist laut Odoo-Docstring zum Überschreiben gedacht; die `_search`-Signatur hat sich in 19 geändert (`bypass_access`) → Update-Test (16). |

**Datenbank:** C-Kollation (Odoo-Standard, `service/db.py:146`). Präfix- und Teilbaum-Abfragen nutzen dann die
normalen Indizes, und `_parent_store_update` des neueren Cores ist korrekt (auf `en_US.utf8` zerstört er
Teilbäume, belegt in 19.2). Namens-Sortierung wie im Explorer über den Hook `_order_field_to_sql` + ICU-Kollation
+ passenden Index (DB-Vorrang-Konzept 15.5). Namenssuche mit Trigram-Index (185 statt 37 Anfragen/s, 20.3).
Unicode-Namen werden beim Anlegen einheitlich nach NFC normalisiert (es gibt keine Fremdschreiber mehr, die NFD
liefern könnten).

## 5. Blob-Speicher (Eigenbau, weil `ir.attachment` hier nicht reicht)

**Warum eigen:** `ir.attachment` ist Odoos allgemeines Anhang-System, kein revisionsorientierter Speicher für einen
großen Dateibestand. Konkret: Inhalte nur als Bytes im Speicher (`_set_attachment_data`), `store_fname` nicht setzbar
(`write`/`create` entfernen es), Prüfsumme SHA-1 (`_compute_checksum`), kein `fsync` beim Schreiben (`_file_write`),
Rechte hängen am Elterndatensatz. Große Dateien, Streaming und fortsetzbare Uploads sind damit nicht möglich
(Code-Prüfung Nr. 33–35). `ir.attachment` bleibt Odoos Anhangssystem für Geschäftsdatensätze; für Dateiinhalte **und**
für abgeleitete Dateien (Vorschau, Text) wird es nicht genutzt (8.9, I13).

**Aufbau:** Nachbildung des Filestore-Musters, erweitert um Streaming.
- **Ablage:** `<blobroot>/<sha[0:2]>/<sha[2:4]>/<sha>`. `<blobroot>` ist ein **Unraid-Share unter `/mnt/user/<name>`**;
  Odoo greift nur über diesen shfs-Pfad zu, nie direkt auf `/mnt/diskN`. Die Share-Einstellung "Included disks" legt
  fest, wo shfs die Dateien physisch ablegt: **disk2 + disk3** (disk1 ist zu 76 % belegt und trägt andere Daten;
  feste Platten erleichtern Backup und Wiederherstellung), **kein Cache-Pool** (95 GB frei auf der SSD, und der Mover
  würde Blobs nachträglich verschieben) (Entscheidung 8; shfs legt fehlende Ordner auf der Platte der Datei an, `link`/`rename` funktionieren über
  Plattengrenzen, ein vorhandener Name auf der anderen Platte wird mit `EEXIST` abgelehnt, 19.17) und wird im
  Container **unterhalb von `<data_dir>/filestore/<db>/`** eingebunden. Nur so gilt Odoos `x_sendfile`-Pfadprüfung
  (`http.Stream.get_response`, prüft "unterhalb von `data_dir/filestore`"). Samba gibt diesen Share nicht frei (I1).
- **Schreiben:** Stream in Temp-Datei im selben Dateisystem, **SHA-256 beim Empfang**, `fsync`, Aufräum-Markierung
  für den Hash setzen **oder erneuern** (`os.utime`), `link` ohne Überschreiben auf den Hash-Namen (existiert er schon:
  Deduplizierung), `fsync` des Ordners. **Die Temp-Datei bleibt bis nach dem Commit.** Dann in einer **kurzen**
  Transaktion: Blob-Zeile anlegen oder ihr `last_used` setzen, **danach** prüfen, ob die Blob-Datei existiert (fehlt
  sie, aus der Temp-Datei neu verlinken), Revision anlegen, Commit, Temp-Datei löschen. Das Setzen von `last_used`
  sperrt die Zeile gegen den Aufräumjob; hat der Aufräumjob sie gerade gelöscht, meldet PostgreSQL unter REPEATABLE
  READ (Odoos Isolationsstufe, `sql_db.py`) einen Serialisierungsfehler, den `retrying()` wiederholt (19.17, A4).
  **Während des Datenstroms ist keine Transaktion offen** (19.8: sonst hält sie den Snapshot, bremst VACUUM und
  belegt die Verbindung). Ein Abbruch hinterlässt höchstens einen unreferenzierten Blob (Aufräumjob) oder eine
  Temp-Datei (eigener Aufräumjob für Temp-Dateien älter als N Stunden). `fsync` kostet auf dem Unraid-Array ~28 ms je
  Datei, die Schreibrate liegt bei ~46 MB/s (19.7); nach dem Einschlafen der Platten (Spindown 30 min) dauerte der
  erste Schreibzugriff 7,3 s (19.17, A13) – Zeitlimits entsprechend großzügig.
- **Aufräumen:** `@api.autovacuum`, wie Odoos `_gc_file_store` in einer frischen Transaktion mit der Sperre von
  Blob- und Revisionstabelle als **erstem** Statement (sonst sieht der Snapshot gerade committete Verweise nicht,
  Snapshot-Befund 3). Gelöscht werden nur Blob-Zeilen ohne Revision (und ohne laufende Uploads), deren `last_used`
  älter als die Schonfrist ist, sowie Dateien, deren Markierung älter als die Schonfrist ist und zu denen keine Zeile
  existiert. Die Schonfrist ist länger als ein Backup-Lauf (unten). Odoos eigener Aufräumjob hat beim Wiederverwenden
  dieselbe Lücke (`_file_write` markiert nur beim Neuschreiben) – deshalb die Regeln unter "Schreiben" (A4).
- **Lesen:** `http.Stream(type='path', …)` direkt erzeugen (nicht `Stream.from_path`, das nur Addon-Pfade zulässt,
  A19) mit `etag=sha256`; Range und bedingte Anfragen über `send_file` (`conditional`), Auslieferung über nginx per
  `X-Accel-Redirect` (`Stream.get_response`).
- **Prüfen:** periodischer Hash-Abgleich in Stichproben (Bitfäule, Plattenfehler) als Cron mit Zeitbudget.
- **Backup:** DB und Blob-Speicher gehören zusammen. Weil Blobs unveränderlich sind, reicht für den Blob-Speicher ein
  inkrementelles Backup; wiederhergestellt wird immer DB-Stand plus alle Blobs, die dieser Stand referenziert.
  **Reihenfolge:** erst die DB sichern, dann die Blobs; die Schonfrist des Aufräumjobs ist länger als ein Backup-Lauf
  (sonst kann ein Blob, auf den die gesicherte DB zeigt, dazwischen gelöscht werden). Regelmäßig prüfen, dass alle
  von der gesicherten DB referenzierten Blobs im Blob-Backup liegen (A11).

## 6. Schreibwege

Alle Schreibwege folgen demselben Ablauf: Rechte prüfen → Vorgangs-ID prüfen → ggf. Blob anlegen (Abschnitt 5) →
Zeilen **wartend** sperren (siehe unten) und Basisrevision prüfen → DB schreiben → Commit. Keine Plattenoperation
außer "Blob anlegen", kein `sudo` auf Nutzereingaben (I7).

| Vorgang | Ablauf | Bemerkung |
|---|---|---|
| Hochladen (neu) | Upload in Stücken (7) → Blob → `int_filemanager.node` + `int_filemanager.revision` | Name kollidiert → Fehlermeldung oder Nutzerwahl "ersetzen/umbenennen" |
| Neue Fassung (Upload, Bearbeiten, ONLYOFFICE, WebDAV-PUT) | Blob → neue `int_filemanager.revision`, `current_revision_id` umhängen | **Basisrevision** mitgeben (WebDAV: Sperre/ETag); weicht sie ab → Konflikt statt stillem Überschreiben; alte Fassung bleibt (I6). **Gleicher Inhalt → keine neue Revision**; leerer Inhalt auf einer Datei ohne Revision → bleibt ohne Revision |
| Umbenennen, Verschieben | reines `write` auf `int_filemanager.node`; beim Verschieben in anderen Rechte-Bereich `scope_id` des Teilbaums im selben Commit | keine Plattenoperation, deshalb kein B2/B7. Verschieben auf einen belegten Namen: Ziel bekommt den Inhalt als neue Revision (Identitätsregel, 11) |
| Löschen | `active=False`, `removal_reason='trash'` (Teilbaum) | Papierkorb-Ansicht filtert auf den Grund |
| Wiederherstellen | `active=True`; Namenskollision im Zielordner → Fehlermeldung | |
| Endgültig löschen | Zeilen löschen; Blobs später per Aufräumjob | I4 |
| Kopieren | neuer Knoten, neue Revision auf **denselben** Blob | kein Kopieren von Bytes |
| Version wiederherstellen | neue Revision auf den alten Blob | keine Bytes kopiert |
| Text bearbeiten | wie "neue Fassung" | heute `write_text` nicht atomar (B6) |

**ORM und Namensindex:** Das ORM kennt den Teil-Unique-Index nicht und schreibt Änderungen erst beim nächsten Flush.
Wird in einem Vorgang ein Name frei gemacht (Papierkorb, Umbenennen) und danach wieder belegt, muss dazwischen
`flush_recordset()` stehen, sonst scheitert der Vorgang am Index (19.4, litmus copymove).

**Wiederholungssicherheit:** Da vor dem Commit nur Blobs angelegt werden (idempotent über den Hash), darf Odoos
`retrying()` einen Schreibvorgang wiederholen. `retrying()` wiederholt aber **nur** Serialisierungsfehler, Deadlocks
und `LockNotAvailable` (`service/model.py`, `PG_CONCURRENCY_EXCEPTIONS_TO_RETRY`); eine `IntegrityError` (auch der
Namensindex) wird sofort zur Fehlermeldung, und `lock_for_update()` wartet nicht (`SKIP LOCKED`) und wirft
`LockError`, eine `UserError`, die gar nicht wiederholt wird (A3). Deshalb:
- **Sperren:** `SET LOCAL lock_timeout` (wenige Sekunden) und `SELECT … FOR UPDATE` über `odoo.tools.SQL` statt
  `lock_for_update()`; läuft die Zeit ab, meldet PostgreSQL `LockNotAvailable`, und `retrying()` wiederholt (19.17;
  `lock_timeout` setzt auch `_gc_file_store` selbst).
- **Anlegen:** `create` in einem Savepoint; bei `UniqueViolation` die inzwischen vorhandene Zeile nehmen und nach der
  Regel des Schreibwegs fortfahren (Upload/`PUT`: neue Revision des vorhandenen Knotens; Umbenennen/Verschieben auf
  einen belegten Namen: Meldung an den Nutzer). Muster: Blob-Anlage im Prototyp (`fm.blob._get_or_create`).
- **Tests mit erzwungener Überlappung** (Barriere bzw. Fehlerinjektion zwischen Prüfen und Schreiben), nicht durch
  gleichzeitiges Starten: Der Prototyp-Test "10 gleichzeitige `PUT` auf denselben neuen Namen → 1 Knoten,
  10 Revisionen" (19.10) hat den Wettlauf zeitlich nicht getroffen; der Code hätte dort mit `ValidationError` bzw.
  `LockError` abgebrochen.

Wird der Inhalt als Strom empfangen (WebDAV-`PUT`), liegt er vor der DB-Arbeit vollständig als Blob vor; wiederholt
wird nur der kurze Abschluss.

## 7. Upload aus dem Browser in Stücken

**Warum Stücke:** Abgebrochene Uploads großer Dateien können fortgesetzt werden, und jeder Request bleibt kurz (ein
Prefork-Worker ist nie lange belegt, `limit_time_real` greift nicht). Odoo-Routen lesen den Body über die öffentliche
API ganz in den RAM (19.2); das Streamen ginge nur über ein internes Attribut (19.6) und wird deshalb in Odoo-Routen
**nicht** genutzt. WebDAV streamt dagegen im eigenen Prozess (`odoo fmdav`, 11).
- **Stücke von 4 MB** (19.2: größere Stücke lassen die Worker bis 1,9 GB wachsen); Route mit eigenem
  `max_content_length` knapp darüber; `limit_memory_soft`/`hard` bewusst setzen.
- Ablauf: `init` (Vorgangs-ID, Größe, Ziel) → `chunk` (Offset, idempotent) → `finish` (Hash prüfen, Blob anlegen,
  Knoten/Revision in einer Transaktion). Abgebrochene Uploads können fortgesetzt werden.
- **Dateien bis 4 MB in einem Request** und einem Commit (spart zwei Odoo-Aufrufe, 19.4).
- **`finish` großer Dateien als Hintergrundjob:** Über mehrere Requests (und Worker) lässt sich der SHA-256 nicht
  fortschreiben; `finish` liest die Datei deshalb erneut (3 GB: 46–56 s). Ab einer Grenze (z. B. 256 MB) setzt
  `finish` den Upload auf `processing`, ein Cron legt Blob und Revision an; die Oberfläche zeigt "wird verarbeitet".
  (WebDAV betrifft das nicht: dort wird beim Empfang gehasht.)
- Verwaiste Uploads räumt ein Cron nach Ablauf auf.
- Das Frontend teilt Dateien in Stücke; bestehende Upload-Oberfläche wird angepasst.

## 8. Lesen, Vorschau, Medien

- **Download und Video:** Stream mit Range und `x_sendfile` (5). Rechteprüfung über das ORM vor der Auslieferung.
- **Mehrere Dateien/Ordner als ZIP (Entscheidung 7):** Bis zu einer Grenze (Vorschlag 500 MB Summe) direkt gestreamt,
  ohne die ganze ZIP-Datei im Speicher (I12); das belegt einen Worker für die Dauer. Darüber baut ein Cron das ZIP
  unter der Identität des anfordernden Nutzers in eine Temp-Datei **unterhalb von `<data_dir>/filestore`** (sonst
  kein `x_sendfile`), der Nutzer bekommt eine Benachrichtigung, ausgeliefert wird per nginx; Temp-ZIPs nach 24 h
  löschen (A9). Rechte je enthaltener Datei.

### 8.1 Abgeleitete Dateien: Ziel und Umfang (Entscheidungen 11–15, 2026-09-28)

Zu jedem Blob entstehen automatisch **abgeleitete Daten**: Vorschaubilder, Vorschau-PDFs (Office), Text (aus dem
Dokument, aus Scans per Texterkennung) und Metadaten. Sie werden nur im Umwandler (8.2) erzeugt. Odoo speichert und
liefert sie aus, öffnet oder dekodiert sie nie (I13). Fehler sind sichtbar; eine defekte Datei stört Odoo nicht.

**Umfang von Schritt 5 (Entscheidung 15):**

- Bilder: JPEG, PNG, GIF, BMP, WebP, AVIF, TIFF, HEIC/HEIF und Kamera-RAW.
- Video: Standbild; die Wiedergabe läuft im Browser über den Stream mit Range (oben).
- Office (Word, Excel, PowerPoint, ODF, RTF): Vorschau-PDF und Vorschaubild. PDF: Seite 1 als Bild.
- Text: eingebetteter Text aus PDF und Office, Text aus Scans per Texterkennung, Textdateien.
- Audio: Cover aus den Tags.
- Metadaten (8.7), Verwalter-Diagnose (8.6).

Spätere Erweiterungen: 8.8.

### 8.2 Umwandler (I11)

Eigener Container aus einem eigenen Image, **kein zweites Odoo**: kleiner HTTP-Dienst ohne Internetzugang. Der
Blob-Speicher ist **schreibgeschützt** eingebunden; der Umwandler liest über den Hash-Pfad. Odoo schickt einen Auftrag
(Blob, Art, Spezifikation, Grenzen), der Umwandler liefert das Ergebnis (Datenstrom oder JSON) und **schreibt selbst
nichts** (I1). Die OCR-Werkzeuge des heutigen Moduls (Tesseract mit deutschem Sprachpaket, OCRmyPDF, Ghostscript,
qpdf) ziehen aus dem Odoo-Image in den Umwandler. Fällt er aus oder ist er nicht erreichbar, bleiben die Aufträge
offen; die Oberfläche zeigt Symbole.

**Kette von Bausteinen** (Muster aus Cloudreve, `pkg/thumb`): Jeder Baustein hat eine Liste von Dateiendungen bzw.
Typen, eine Größengrenze, ein Zeitlimit, einen Ein/Aus-Schalter, eine Reihenfolge und eine Grenze für gleichzeitige
Aufträge. Ein Baustein darf ein **Zwischenergebnis** an den nächsten weiterreichen (Office → PDF → Bild →
Vorschaubild). Passt keiner oder scheitert er, geht der Auftrag an den nächsten; sonst wird das Ergebnis
`not_applicable` bzw. `failed` (8.4).

| Baustein | Dateiarten | Ergebnis |
|---|---|---|
| Bild (Pillow mit allen Plugins, vips, libheif, libraw) | JPEG, PNG, GIF, BMP, WebP, AVIF, TIFF, HEIC/HEIF, RAW | Kachel, Vorschau, Metadaten |
| Video (ffmpeg, ffprobe) | gängige Videoformate | Standbild (weiter an Bild), Metadaten |
| Office (LibreOffice) | Word, Excel, PowerPoint, ODF, RTF | Vorschau-PDF (weiter an PDF) |
| PDF (Ghostscript) | PDF | Seite 1 als Bild, eingebetteter Text |
| Texterkennung (OCRmyPDF, Tesseract) | Scans, Bilder mit Text | Text |
| Audio (Tags) | MP3, M4A, OGG, FLAC | Cover, Musik-Metadaten |
| Text | txt, md, csv, log, json u. a. | Text |

**Schutzgrenzen** (Startwerte nach Cloudreve, auf Tower zu messen): Größe je Baustein (Bild, Office, RAW 75 MB; Video
großzügiger, bei Cloudreve 10 GB), Obergrenze für Bildpunkte gegen Bildbomben (64 Megapixel), Zeitlimit je
Auftrag, **LibreOffice höchstens 1–2 gleichzeitig** (Cloudreve dokumentiert Startfehler bei mehr). Werkzeuge werden
über Argumentlisten gestartet (keine Shell), in einem eigenen Arbeitsordner je Auftrag, der danach gelöscht wird.

### 8.3 Datenmodell `int_filemanager.derivative`

Eine Zeile je Quell-Blob, Art und Spezifikation. Die Rolle "Original" oder "abgeleitet" hängt am **Verweis**, nicht am
Blob: derselbe Hash kann Original einer Revision und Ergebnis eines Derivats sein (z. B. ein kleines JPEG, dessen
Vorschau es selbst ist).

| Feld | Bedeutung |
|---|---|
| `source_blob_id` | Quelle (Many2one Blob, `ondelete="restrict"`) |
| `kind` | `tile` (Kachel), `preview` (Vorschaubild), `preview_pdf`, `text`, `meta` |
| `spec` | Größe bzw. Werkzeugversion; **Eindeutigkeit** `(source_blob_id, kind, spec)` |
| `state` | `pending`, `running`, `done`, `failed`, `not_applicable` |
| `derived_blob_id` | Ergebnis im Blob-Speicher (leer bei Text und Metadaten); darf gleich `source_blob_id` sein |
| `text` | extrahierter Text (Suche, 9) |
| `meta`, dazu Spalten | Metadaten als Sammelfeld (JSON); zum Filtern und Sortieren eigene Spalten: Aufnahmezeit, Kamera, GPS, Breite, Höhe, Dauer |
| `attempts`, `tool`, `tool_version`, `started_at`, `finished_at`, `priority` | Ablauf, Diagnose |
| `error` | technischer Fehlertext, **nur für Verwalter** (12) |

- **Zwei Bildgrößen (Entscheidung 13):** Kachel (Listen, Kacheln) und Vorschau (große Ansicht). Startwerte 400 × 300
  und 1920 × 1920, an der Oberfläche zu prüfen. **Browserfähige Formate** (JPEG, PNG, WebP, AVIF, GIF) zeigt die große
  Ansicht direkt vom Original: `preview` ist dort `done` mit `derived_blob_id = source_blob_id`; nur die Kachel wird
  erzeugt.
- Ergebnisse gehören zum **Blob**: gleicher Inhalt wird nur einmal umgewandelt, alte Fassungen behalten ihre Vorschau,
  ein "veraltetes Ergebnis" gibt es nicht (I2).
- Der Dateityp (Foto, Video, Audio, Dokument, Archiv, Sonstiges) am Knoten wird aus `mime` berechnet (gespeichert,
  zum Filtern).

### 8.4 Auslösung und Warteschlange (Entscheidung 12)

- **Dauerhaft in der Datenbank:** offene Aufträge sind Zeilen mit `state = pending`; sie überstehen Neustarts (anders
  als Cloudreves Warteschlange im Arbeitsspeicher). Ein Cron legt die fehlenden Zeilen an (Blobs mit Revision ohne
  Derivat); **die Schreibwege bleiben unberührt** (6).
- **Mischform:** Der Cron arbeitet gedrosselt im Hintergrund (Zeitbudget je Lauf, Grenze je Baustein). Was der Nutzer
  gerade in einem Ordner sieht, kommt **vorn** in die Reihenfolge: eine öffentliche, rechtegeprüfte Methode
  `request_previews(node_ids)` (begrenzte Anzahl) setzt nur `priority` der offenen Zeilen. Die Anfrage wartet **nicht**;
  bis das Bild da ist, zeigt die Oberfläche das Symbol, danach kommt eine Meldung über den Bus, und das Bild erscheint.
- **Übernehmen eines Auftrags:** `SELECT … FOR UPDATE SKIP LOCKED`, `state = running` mit Ablaufzeit (stirbt ein Lauf,
  wird der Auftrag nach Ablauf wieder frei). Der Umwandler wird erst **nach dem Commit** aufgerufen (I3).
- **Ergebnis übernehmen:** Bytes als Datenstrom in den Blob-Speicher (SHA-256, `fsync`, Markierung, `link`) wie in 5;
  danach in einer kurzen Transaktion `derived_blob_id` und `last_used` setzen (Schutz gegen den Aufräumjob wie bei
  Revisionen, A4), Commit, Bus-Meldung. Ist die Quelle inzwischen gelöscht, verwirft der Fremdschlüssel den Auftrag.
- **Fehler:** Versuche mit wachsendem Abstand (Startwert 3), danach `failed`. `failed` bleibt bestehen, bis sich die
  Werkzeugversion oder die Bausteinliste ändert oder ein Verwalter neu anstößt (8.6). `not_applicable`: kein passender
  Baustein, Format unbekannt oder zu groß; wird bei geänderter Bausteinliste neu bewertet. Neuer Inhalt = neuer Blob =
  neuer Zustand.
- **Altbestand:** dieselbe Warteschlange mit niedriger Priorität, gedrosselt über Tage (209.429 Bilder auf Tower, 20.3);
  ein Nachtfenster ist möglich. Der Verwalter sieht den Fortschritt.

### 8.5 Auslieferung und Rechte

- **Eigene Route** `/int_filemanager/v2/preview/<revision_id>/<kind>`: prüft das Leserecht der **Revision** (deren
  `ir.rule`) unter der Nutzeridentität, sucht das Derivat über `revision.blob_id` und `kind` und streamt den Ergebnis-Blob
  (`http.Stream` vom Typ `path`, ETag = SHA-256, `x_sendfile`) wie die Download-Route. Ohne fertiges Ergebnis: 404, die
  Oberfläche zeigt das Symbol. Freigabe-Links und Portal nutzen dieselbe Route mit ihrem Token.
- **Kein `/web/image`, kein `/web/content`:** `int_filemanager.derivative` hat für Nutzer **keinen** Zugriff (12). Die
  Oberfläche erhält nur den Zustand (`preview_state`, berechnet, gestapelt über die geladene Seite) und baut daraus die
  URL. Fehlertexte sind damit für Nutzer nicht lesbar.
- **Verwalter** (Gruppe "Verwalter") lesen das Derivat einschließlich `error` (8.6).

### 8.6 Verwalter-Werkzeuge

- **Diagnose je Datei:** Zustand je Art, Werkzeug mit Version, Dauer, Versuche, Fehlertext (Muster: FileRun, Cloudreve).
- **Liste** der fehlgeschlagenen Umwandlungen mit Filter (Art, Format, Fehler); **"Neu erzeugen"** für Datei, Ordner oder
  Bestand; Fortschritt des Nachholens.
- **Konfiguration** der Bausteine (Ein/Aus, Endungen, Grenzen, gleichzeitige Aufträge) über `ir.config_parameter` und
  `res.config.settings`.

### 8.7 Metadaten

Aus dem Umwandler, je Blob: Bild (Aufnahmezeit, Kamera, Objektiv, Belichtung, GPS, Ausrichtung, Software, Urheber,
Breite, Höhe), Audio (Titel, Interpret, Album, Komponist, Genre), Video (Dauer, Bitrate, Bildrate, Codec, Tonspuren,
Kapitel), Dokument (Seitenzahl). Sie dienen der Suche, den Filtern, der Detailleiste und dem Player. Odoo hat dafür
keinen Baustein (nur die EXIF-Ausrichtung in `image_fix_orientation`). **Keine Auflösung von Ortsnamen über
Onlinedienste** (Koordinaten verlassen das Haus nicht); ein lokaler Dienst wäre eine spätere Erweiterung.

### 8.8 Bewusst später (Entscheidung 15)

E-Book-Leser (EPUB), 3D-Modelle (OBJ, STL, GLTF u. a.), Kontaktbögen, PSD und EPS (ImageMagick), Bildeditor mit
Speichern, PDF zusammenfügen und teilen (`odoo.tools.pdf` bietet die Werkzeuge), Archive entpacken. CAD nur über
Onlinedienste – für uns wegen der Kundendaten ausgeschlossen. Die Bausteinstruktur (8.2) erlaubt jede Ergänzung ohne
Umbau.

### 8.9 Warum nicht `ir.attachment` (Prüfung des Odoo-19-Cores, 2026-09-28)

Die Prüfung ging über alle 26 Erweiterungen von `ir.attachment`, alle 15 Controller mit Attachment-Bezug und alle
Stellen, die Bilder dekodieren oder PDFs parsen. Ergebnis: Odoo öffnet Anhangsinhalt an vielen Stellen selbst, und ein
später installiertes Modul kann weitere ergänzen. Eine Wache je Stelle wäre nie abgeschlossen.

| Stelle | Was passiert |
|---|---|
| `_check_contents` → `_postprocess_contents` (`ir.attachment`, `create`/`write`, auch `force_storage`) | Pillow öffnet PNG, JPEG, BMP, TIFF; Verkleinern ab 1920 × 1920 (nur `image_no_postprocess` schaltet ab) |
| `_index`, `attachment_indexation` | pdfminer, openpyxl, ZIP-XML; Fehler werden verschluckt; Aufrufer erhält nur die Menge, nicht `res_model` |
| `fields.Image` (`create`/`write`) | `image_process` im Prozess |
| `html_editor`: `image_width`/`image_height` | berechnetes Feld mit `base64_to_image`, per RPC lesbar |
| `/web/image` (`_get_image_stream_from`) | bei `width`/`height`/`crop` (Pfad oder Query) oder bei Feldnamen mit Endzahl liest es die Datei, wechselt von `path` auf `data`, `image_process`; kein `x_sendfile` |
| `/mail/attachment/pdf_first_page/<id>` | `extract_page`: pypdf, bei Bildern Pillow |
| `html_editor` `modify_image`, `image_shape` | Kopie mit Pillow; `image_shape` dekodiert (nur über XML-ID erreichbar) |

`groups=NO_ACCESS` an den Feldern schließt viele Lesewege, ist aber keine lückenlose Sperre (`sudo()`, `is_system()`,
`public`, Zugriffstoken). Weg A (`ir.attachment` mit Sperren) würde zusätzlich Überschreibungen von `create`/`write`
(mit `default_get` und Zuordnungswechsel), `_index` über Kontext, ein Integrationsmodul für die Ladereihenfolge und
das ORM-Löschen der Derivate vor dem Blob verlangen, und die Auslieferung liefe trotzdem über eine eigene Route. Der
eigene Blob-Speicher braucht nichts davon. Der Aufräumjob für Blobs (5) löscht Zeilen per SQL und würde Anhänge
hinterlassen; mit Derivat-Zeilen ohne Anhänge ist das unkritisch.

Unser bisheriges `int_filemanager/models/ir_attachment.py` (Synchronisieren auf die Platte, v1) entfällt mit v1
(Reihenfolge, Schritt 8).

### 8.10 Aufräumen und Sicherung

- **Aufräumjob** (5) erweitert, in einer Transaktion mit Sperre auf Blob, Revision **und** Derivat: (1) Derivat-Zeilen
  löschen, deren Quell-Blob keine Revision mehr hat; (2) Blobs löschen ohne Revision **und** ohne Verweis eines Derivats,
  nach der Schonfrist. Bei `derived_blob_id = source_blob_id` verschwinden Zeile und Blob nach der Frist gemeinsam.
- **`last_used`** wird auch gesetzt, wenn ein Derivat auf einen Blob verweist.
- **Sicherung:** alles sichern (Original und Ergebnis lassen sich nicht sauber trennen, weil ein Blob beides sein kann).
  Ob ein Ausschluss reiner Ergebnis-Blobs lohnt, hängt von ihrer Größe ab; sie ist noch nicht gemessen.

## 9. Suche, OCR, Geschäftsbezug

- Namenssuche mit Trigram-Index; Volltext über `int_filemanager.derivative.text` (Art `text`, 8.3) in PostgreSQL – kein
  Elasticsearch, kein Tika, keine `attachment_indexation`-Logik in Odoo (I13). Trigram- oder Volltextindex wird bei der
  Umsetzung gemessen. Treffer-Ausschnitte aus dem Text.
- **Reihenfolge der Texterkennung:** zuerst eingebetteter Text (PDF-Textebene, Office); nur wenn er fehlt oder zu
  kurz ist (heute: weniger als 20 Zeichen je Seite), startet OCR als **eigene, gedrosselte, abschaltbare Stufe**
  (Deutsch), weil sie langsam ist. Sie läuft im Umwandler (8.2).
- **Werterkennung bleibt in Odoo** (Entscheidung 14): Muster und extrahierte Werte arbeiten nur auf dem fertigen Text,
  öffnen keine fremde Datei und behalten Rechte und Vorschlagsdialog. Sie hängen wie bisher am Knoten bzw. an der
  Revision.
- Die heutigen öffentlichen Methoden `action_analyze_document`/`action_apply_extracted_values` (N1) werden privat
  und prüfen Rechte selbst.
- Geschäftsbezug generisch über das Verknüpfungs-Mixin (4), Smart-Button und Dateiliste am Datensatz.

## 10. Office

- **ONLYOFFICE im Browser:** Callback-Route speichert als neue Revision mit **Basisrevisionsprüfung** über den
  Dokument-Key (heute fehlt die Prüfung, 13.1). Editor-Sitzung an Knoten-ID + Revision gebunden (I8). **JWT
  verpflichtend** und echte Rechteprüfung mit `check_access`: Das heutige `onlyoffice_odoo` ruft im Callback
  `has_access("write")` auf und verwirft das Ergebnis (`has_access` liefert nur `True`/`False`, A14).
- **Start:** Office-Dateien werden im Browser mit ONLYOFFICE bearbeitet; andere Formate herunterladen, lokal
  bearbeiten, hochladen (neue Revision mit Basisrevisionsprüfung, 6).
- **Idee, ungetestet:** "Lokal bearbeiten" über die File System Access API (Chrome/Edge): die Odoo-Seite öffnet eine
  lokale Kopie mit Erlaubnis des Nutzers und lädt jede gespeicherte Änderung hoch. Grenzen: nur Chromium-Browser,
  Seite muss offen bleiben, Erlaubnis je Sitzung.
- **"Lokal öffnen" (Word/Excel) erst mit Netzlaufwerk (11):** Desktop-Office öffnet Dateien vom Server nur über
  WebDAV oder SharePoint. Dann über `odoo fmdav` (11) statt eigener Einzeldatei-Routen. Anmeldung wahlweise mit
  API-Schlüssel oder einem kurzlebigen Token je Datei (in der DB, an Knoten-ID gebunden; heute nur im Speicher und
  nach Neustart ungültig); `PUT` = neue Revision mit Sperrprüfung (`int_filemanager.dav_lock`); ETag = SHA-256.

## 11. Explorer-Zugriff und Eingangsordner

**Entscheidung 2026-09-26: Start ohne Explorer-Zugriff (Option C) plus Eingangsordner.** Gearbeitet wird in der
Odoo-Oberfläche; Office-Dateien im Browser über ONLYOFFICE (10). Ob später ein Netzlaufwerk dazukommt, wird **nach
der Nutzung** als eigene Entscheidung getroffen. Zur Wahl stehen dann die beiden vorbereiteten Wege:
- **WebDAV über `odoo fmdav`** (11.2; Prototyp und Messungen 19.10, Stolpersteine 19.8/19.12): Protokollschicht
  WsgiDAV, eigener Container, auf den Windows-Rechnern HTTPS-Vertrauen und angehobene Download-Grenze nötig; auch für
  Zugriff ohne VPN und für "Lokal öffnen" aus dem Browser.
- **SMB über Samba mit einem Odoo-FUSE-Dateisystem dahinter** (19.14; noch ohne Prototyp): normales Netzlaufwerk ohne
  Einrichtung auf Windows; offen sind Rechte je Nutzer über die UID-Zuordnung, Schreibpuffer bis zum Schließen,
  Metadaten-Tempo, FUSE im Container.

Nicht in Frage kommen Samba + inotify (19.15: zweiter Schreiber, Rechte an Odoo vorbei, verlorene Fassungen) und die
übrigen Wege aus 19.14.

**Warum so:** Ohne Netzlaufwerk sind alle Invarianten ohne Zusatzteile erfüllt (ein Schreibweg, Rechte nur über Odoo,
keine Einrichtung auf den Clients, kleinste Angriffsfläche). Was fehlt – Desktop-Office, Programme mit Ordnern und
Pfaden (z. B. Audio-Projekte), Scanner, die in einen Ordner schreiben – deckt teils der Eingangsordner ab, der Rest
entscheidet über den späteren Weg.

### 11.1 Eingangsordner

Eine kleine Samba-Freigabe **nur zum Hineinlegen** (Scanner, Handy-Sicherungen, Kopien von Rechnern). Sie ist **nicht**
der Dateispeicher: Odoo holt die Dateien ab, danach sind sie im Eingangsordner weg. Damit bleibt Odoo alleiniger
Schreiber des Bestands (I1).
- **Zuordnung:** je Eingangsordner (bzw. Unterordner) ein Zielordner in Odoo und ein Odoo-Nutzer als Urheber; Rechte
  über den Rechte-Bereich des Zielordners (I7). Die Samba-Freigabe selbst nur für die Geräte/Nutzer, die einliefern.
- **Abholen:** Cron in kurzen Abständen (kein Watcher nötig; der Ordner ist klein und flüchtig). Eine Datei gilt als
  fertig, wenn Größe und Änderungszeit eine **Ruhezeit** lang (Vorschlag 2 min) gleich bleiben (Entscheidung 6;
  Samba-Temp- und Punktnamen ignorieren). Ob Samba die Datei noch offen hält, sieht der Odoo-Container nicht, das
  weiß nur der Host (A8). Dann: Strom in den Blob-Speicher mit SHA-256 (5), Knoten + Revision `origin='import'` in
  einer kurzen Transaktion, **erst nach dem Commit** die Datei in den Unterordner `_übernommen` verschieben (I3/I4)
  und dort erst nach 24 h ohne Änderung löschen. Grund: Wird eine sehr langsame Kopie mit langer Pause zu früh
  übernommen, schreibt Samba über das offene Handle in die verschobene Datei weiter (gleiches Dateisystem); der
  nächste Lauf sieht die Änderung und übernimmt sie als weitere Revision – nichts geht verloren (I6). Direktes
  Löschen würde diese Schreibvorgänge verlieren. Namenskonflikt im Ziel → Zusatz im Namen, nicht überschreiben.
- **Fehler:** Datei in einen Unterordner `_fehler` verschieben, Grund protokollieren und in Odoo als Aktivität melden.
- **Wiederholung:** idempotent über Pfad + Größe + Änderungszeit + Hash; ein Abbruch nach dem Commit, aber vor dem
  Verschieben führt beim nächsten Lauf zu "schon übernommen" → nur verschieben.
- Ordnerstruktur im Eingang wird im Ziel nachgebildet (für Kopien ganzer Ordner).

### 11.2 Vorbereitete Bauform WebDAV: `odoo fmdav`

Stand der Prototypen, falls später WebDAV gewählt wird:

**Bauform `odoo fmdav`** (vom Nutzer als WebDAV-Bauform bestätigt 2026-09-26; Prototyp und Messungen 19.10).
Verworfene WebDAV-Bauformen: separater Dienst mit JSON-RPC
(19.4: langsamer, zweites Hashen, zwei Code-Stände) und WebDAV in einer Odoo-Route (19.7/19.8: offene Transaktion,
Zeitlimits, belegte Worker, internes Attribut – nur mit Kniffen beherrschbar).

- **Befehl aus dem Addon:** `<addon>/cli/fmdav.py` (Unterklasse von `odoo.cli.command.Command`, von Odoo aus den
  Addons geladen, `odoo/cli/command.py:68-105`). Aufruf `odoo --addons-path=<pfade> fmdav -c odoo.conf -d <db>
  --dav-root=<knoten> --dav-accel=/web/filestore` (`--addons-path` **vor** dem Befehlsnamen). Eigener Container aus
  demselben Image; nach Modul-Updates mit neu starten.
- **Laufzeit:** werkzeugs Thread-Server (wie Odoo im Thread-Modus), ein Thread je Verbindung; **keine
  Prefork-Worker, kein `limit_time_real`**; `wsgi.input` über `werkzeug.wsgi.get_input_stream()` begrenzt.
- **ORM wie `ir_cron`/`odoo shell`:** je Anfrage `Registry(db).check_signaling()`, `registry.cursor()`,
  `api.Environment(cr, uid, …)` mit dem angemeldeten Nutzer (I7), danach `signal_changes()` bzw. `reset_changes()`;
  Wiederholung mit Odoos `retrying()` (ganze Anfrage außer `PUT`, XML-Body gepuffert; beim `PUT` nur der Abschluss);
  Namens- und Sperrkonflikte nach den Regeln in 6 (A3).
- **Protokollschicht WsgiDAV** (Version festnageln; zwei Eigenheiten im Provider bzw. per Middleware umgangen:
  Sperrprüfung beim `DELETE`, Content-Type der LOCK-Antwort, 19.4). WsgiDAV und `json5` kommen ins Odoo-Image.
- **Anmeldung:** Basic mit Odoo-Login und **API-Schlüssel** über HTTPS, geprüft mit Odoos
  `res.users.apikeys._check_credentials` – aber mit **eigenem Geltungsbereich** `int_filemanager.dav` statt `rpc`
  (19.16): ein eigens erzeugter Laufwerks-Schlüssel gilt dann **nur** für WebDAV, nicht für JSON-2; globale Schlüssel
  (ohne Bereich) gelten weiter überall. Geprüfte Zugangsdaten 60 s zwischengespeichert (Widerruf wirkt spätestens nach
  60 s). `OPTIONS` ohne Anmeldung. Laufzeit der Schlüssel: Nicht-Admins brauchen ein Ablaufdatum bis zur
  Höchstdauer ihrer Gruppe (`res.groups.api_key_duration`, sonst 1 Tag) – für ein Netzlaufwerk vor dem Einsatz
  festzulegen.
  Kein anonymer Zugang (nur auf der Testinstanz für eine IP).
- **`PUT`** wie Cloudreve: lesen/prüfen → Transaktion beenden → Datenstrom ohne Transaktion in den Blob-Speicher
  (SHA-256 beim Empfang, `fsync`, 5) → kurzer Abschluss mit **erneuter Sperr- und Zielprüfung**. Leerer Body ohne
  Temp-Datei (der Explorer schickt vor jeder Datei einen leeren `PUT`).
- **`GET`** auf Dateien: Antwort mit `X-Accel-Redirect`, nginx liefert (Range, ETag = SHA-256; in nginx
  `etag off; add_header ETag $upstream_http_etag;` in der internen Location).
- **Identitätsregel** (Word/Excel speichern über Temp-Datei und Umbenennen): Verschieben auf belegten Namen → neue
  Revision des Ziels; jeder Verschiebe-/Löschvorgang einer Datei merkt sich den geräumten Platz, eine frische Datei
  desselben Nutzers auf diesem Platz tauscht mit dem Original; Temp-Knoten ("Schatten"), deren Inhalte vollständig in
  den Versionen des Originals liegen, werden beim Löschen endgültig entfernt, alles andere geht in den Papierkorb.
  Fenster 10 min (einstellbar). Geprüft mit Word-, Excel- und "löschen-dann-umbenennen"-Muster und LibreOffice.
- **Sperren** in `int_filemanager.dav_lock`, **tote Eigenschaften** in `int_filemanager.dav_prop` (4).
- **Pfadauflösung in einer Abfrage** (rekursive CTE, danach `check_access('read')` auf dem Treffer); Namen **ohne
  Groß/Klein** über denselben Ausdruck wie der Namensindex (`lower(name COLLATE "und-x-icu")`, 4) – der Prototyp
  vergleicht noch exakt (A17).
- **Aus dem Cloudreve-Vergleich (19.5):** je Zugang (API-Schlüssel) optional eigener Wurzelordner und "nur lesen";
  Punkt-/Systemdateien optional sperren; macOS Finder testen (chunked `PUT` funktioniert).
- **Grenzen, bewusst hingenommen:** viele kleine Dateien langsamer als SMB (71 Dateien 13 s, WebClient: 8 Requests je
  Datei, `fsync` je Datei); je Windows-Client HTTPS-Vertrauen und angehobene Download-Grenze nötig (13);
  Test mit echtem Word/Excel entfallen (Restrisiko, bei Schritt 7 in 18 beobachten).

### 11.3 Die ursprüngliche Abwägung

| Option | Beschreibung | Folgen |
|---|---|---|
| **A. WebDAV-Netzlaufwerk über Odoo** | Odoo stellt ganze Ordner per WebDAV bereit, der Explorer liest und schreibt **über Odoo** (I1 bleibt erfüllt) | größter Eigenbau: WebDAV-Methoden (`PROPFIND`, `GET`, `PUT`, `MKCOL`, `MOVE`, `COPY`, `DELETE`, `LOCK`/`UNLOCK`), Regeln für die Speicherabläufe von Word/Excel/LibreOffice ("Ersetzen durch Umbenennen behält die Identität"), Eigenheiten des Windows-WebDAV-Clients (HTTPS nötig, Größenlimit per Registry, nicht am Code geprüft) |
| **B. Schreibgeschützter Spiegel** | Odoo veröffentlicht einen lesbaren Ordnerbaum auf einem Share, den Samba nur lesend freigibt; Bearbeiten über "Lokal öffnen" | Speicher doppelt oder Spiegel als Verknüpfungen; eine Veröffentlichungsschicht (Muster des Durchstichs); keine Fremdschreiber |
| **C. Kein Explorer-Zugriff** | Arbeit nur in der Odoo-Oberfläche | kein Eigenbau |

**Vor der Entscheidung:** Prototyp A auf Tower (Explorer, Word, Excel, LibreOffice als Netzlaufwerk; Identität,
Sperren, Größen, Tempo). **Ergebnisse: 19.4–19.10** (drei Bauformen geprüft, gewählt `odoo fmdav`; Test mit echtem
Word/Excel auf Wunsch des Nutzers entfallen, HTTPS am Windows-Client ungetestet).

## 12. Rechte

- **Anfangsausstattung (17.5):** ein Bereich "Alle" für den ganzen Share, der heutige Schutzordner als eigener
  Bereich; weitere erst bei Bedarf.
- **Öffentliche Methoden sind die externe API:** Odoo 19 macht jede öffentliche Modellmethode (ohne `_`, nicht
  `@api.private`) mit beliebigen Argumenten aufrufbar – über **JSON-2** (`POST /json/2/<modell>/<methode>`) für jeden
  Nutzer mit API-Schlüssel **und** über `/web/dataset/call_kw` für **jeden angemeldeten Nutzer** ohne Schlüssel
  (`auth="user"`, dieselbe Freigaberegel `get_public_method`; das Modul `rpc` lädt Odoo standardmäßig; 19.16, A2).
  Deshalb: öffentlich nur, was mit fremden Argumenten sicher ist (I7, N1); interne Logik `_…` oder `@api.private`;
  nur lesende Methoden mit `@api.readonly` (lesender Cursor).
- **`sudo()`** nur nach abgeschlossener Prüfung unter der Nutzeridentität und nur für den geprüften Datensatz (z. B.
  Blob-Pfad nach der Knotenprüfung). Die `/web/image`-Hooks `_can_return_content` und Zugriffstoken liefern `sudo`
  – für Dateimanager-Modelle nicht öffnen (Code-Prüfung Nr. 61).
- Rechte-Bereiche (`int_filemanager.scope`) statt Pfad-Präfix-Regeln. Regel-Domains nur über indizierte Felder
  (`[('scope_id.read_group_ids', 'in', user.all_group_ids.ids)]`), damit keine Vollscans entstehen (heute 269 ms
  für Nicht-Admins, 19.2).
- Unterordner mit engeren Rechten bekommen einen eigenen Bereich: Gruppenregeln werden ODER-verknüpft und können nur
  erweitern; nur **globale** Regeln schränken ein (UND, `ir.rule._compute_domain`, A10).
- Beim Ändern von Bereichen **kein** `registry.clear_cache()`: Der Regel-Cache gilt je Nutzer/Modell/Modus
  (`_compute_domain`, `ormcache`); welche Gruppen ein Bereich hat, steht in der SQL-Unterabfrage und wirkt sofort.
  `clear_cache()` würde alle Caches aller Worker leeren (A10). Ändern sich die Gruppen eines Nutzers, leert Odoo den
  Cache selbst (`res.users.write`, `_get_invalidation_fields`).
- **Regeln für jedes Modell (A1):** `ir.rule` wirkt je Modell; übernommen werden nur Regeln von `_inherits`-Eltern
  (`ir.rule._compute_domain`). Ohne eigene Regeln wären Revisionen, Blobs und Uploads für jeden mit Lese-ACL
  vollständig lesbar. Festlegung:

  | Modell | Zugriff für Nutzer |
  |---|---|
  | `int_filemanager.revision`, extrahierte Werte (Werterkennung) | eigene Regeln über den Knoten (`[('node_id.scope_id.read_group_ids', 'in', user.all_group_ids.ids)]`, schreibend entsprechend) |
  | `int_filemanager.blob` | **keine** ACL für Nutzer; Zugriff nur über Methoden, die vorher den Knoten unter der Nutzeridentität geprüft haben |
  | `int_filemanager.derivative` | **keine** ACL für Nutzer (wie der Blob); Zugriff nur über die Vorschau-Route (8.5), die vorher die **Revision** unter der Nutzeridentität geprüft hat. Verwalter dürfen lesen, damit die Fehlertexte nur dort sichtbar sind; Schreiben nur über den internen Weg. |
  | `int_filemanager.upload`, `int_filemanager.operation` | nur eigene Datensätze (`create_uid` = Nutzer) |
  | `int_filemanager.scope` | lesen für interne Nutzer, ändern nur mit dem Recht "verwalten" |
  | `int_filemanager.dav_lock`, `.dav_prop` (mit WebDAV) | wie Revision, über `node_id` |

  Die Rechte-Tests (16) decken **jedes** Modell über **jeden** Weg ab.
- Freigabe-Links für Externe: eigene Tokens mit Ablauf und Log (bestehend), Auslieferung über dieselbe Stream-Route.
- Kundenportal über `portal`.

## 13. Betrieb

- `workers>0` (Prefork) möglich, weil es keinen Watcher mehr gibt; große Downloads über nginx (`x_sendfile`).
- Cron-Datensätze mit `noupdate="1"` (sonst schaltet ein Modul-Update sie wieder ein, N6).
- Modul-eigene `data/neutralize.sql` (Crons, externe Dienste); Testkopien nur neutralisiert.
- **HM-SRV:** behält vorerst das heutige Modul (17.6). DB vor jedem Image-Update auf C-Kollation umstellen (19.2);
  Sicherheitslücke N1 dort separat beheben. Die heutigen WebDAV-Tokens liegen je Prozess im Speicher
  (`webdav_tokens.py`) – mit `workers>0` sieht ein Worker die Tokens des anderen nicht (A18).
- **Blob-Speicher:** Share unter `/mnt/user/<name>`, Plattenauswahl disk2 + disk3, kein Cache (Entscheidung 8;
  am 2026-09-27 3,2 TB frei). Die Platten schlafen nach
  30 min (Spindown), der erste Zugriff kann Sekunden dauern (19.17) – Zeitlimits für Upload-Abschluss,
  Eingangsordner und WebDAV darauf auslegen.
- **Image aktuell halten:** Vor Schritt 3 das Test-Image auf den aktuellen 19.0-Stand bringen (`docker build --pull`;
  erledigt 2026-09-27: `odoo:19.0-hm-test` = 19.0-20260908, eigener Build-Ordner, weil im Appdata-Ordner die
  Live-Datenbankdateien liegen).
  Das Tower-Image 19.0-20260817 enthält einen späteren Sicherheits-Fix noch nicht (Zugriffsprüfung bei
  Relations-Befehlen in `create`/`write`, A5). Das Update der Live-Instanz ist eine eigene Entscheidung.
- Überwachung: Upload-Reste, fehlerhafte Vorschauen (Zahl der `failed`-Derivate, Alter der ältesten offenen), Hash-Prüffehler,
  Platz im Blob-Speicher.
- **Umwandler-Container:** eigenes Image (Python, vips, libheif, libraw, ffmpeg, LibreOffice, Ghostscript, Tesseract mit
  Deutsch, OCRmyPDF), im internen Netz mit Odoo, **ohne Internet**, Blob-Speicher schreibgeschützt, Grenzen für
  Prozessor und Arbeitsspeicher, Neustart-Richtlinie, eigener Arbeitsordner. Lässt sich unabhängig von Odoo
  aktualisieren. Das Odoo-Image verliert die OCR-Bibliotheken.
- **Konfiguration:** nur `db_name` setzen, **kein `dbfilter` zusätzlich** – sonst baut Odoo bei jedem Request ohne
  Sitzung (API-Schlüssel, `/web/health`) eine neue Verbindung zur `postgres`-DB auf (~20 ms, 19.6).
- **Eingangsordner (11.1):** Samba-Freigabe auf Tower über `/boot/config/smb-extra.conf`, nur für die einliefernden
  Geräte/Nutzer; Pfad außerhalb des Blob-Speichers; Import-Cron mit `noupdate="1"`.
- **Später, falls WebDAV gewählt – `odoo fmdav`:** eigener Container aus demselben Image (Befehl siehe 11.2), neben dem Prefork-Odoo; nginx leitet
  `/dav` dorthin (`client_max_body_size 0`, `proxy_request_buffering off`, `proxy_read_timeout` großzügig,
  `Host $http_host` – sonst scheitert WsgiDAVs `Destination`-Prüfung). Nach Modul-Updates beide Prozesse neu starten.
  Grenze sind Threads und DB-Verbindungen (`db_maxconn`). Neustart-fest (Sperren in der DB). Log je Request mit
  Dauer.
- **Aufräumjobs:** Blobs ohne Verweis (5), abgelaufene Browser-Uploads (7), Temp-Dateien abgebrochener Uploads
  (Browser, Eingangsordner, später WebDAV; 19.8: 108 MB blieben liegen).
- **Nur bei WebDAV – Voraussetzungen je Windows-Client** (nicht im Code lösbar, 19.4): HTTPS-Zertifikat, dem der Client vertraut
  (Tower: noch keines vorhanden – eigene CA auf den Clients einspielen oder öffentliches Zertifikat; Entscheidung und
  Eingriff beim Nutzer); `FileSizeLimitInBytes` des WebClient-Dienstes anheben (Standard 50 MB, höchstens 4 GB).
  `BasicAuthLevel` bleibt auf dem sicheren Standard (Basic nur über HTTPS).

## 14. Migration (Kopie)

**Umfang (entschieden 17.2: ganzer Share):** der bisherige Share (Tower: `Daten`, ca. 1,8 TB, 429.184 Einträge, 29.316 Ordner). Etwa 7 % sind
doppelte Inhalte (98 GB gemessen) und werden nur einmal gespeichert. Platzbedarf ca. 1,65–1,7 TB; auf dem Array
von Tower sind ca. 3,6 TB frei (2026-09-27), davon 3,2 TB auf disk2 + disk3 (Entscheidung 8).

**Ablauf:**
1. **Erstkopie im laufenden Betrieb:** Importwerkzeug (Odoo-Cron oder CLI) liest den alten Share, schreibt Blobs
   (Hash beim Kopieren), legt Knoten und Revision `origin='import'` an. Wiederholbar, fortsetzbar, in Batches.
2. **Metadaten übernehmen:** Tags, Status, Partner-Verknüpfungen, OCR-Werte, Freigabe-Tokens aus
   `int_filemanager.file` (über den alten Pfad zugeordnet); bisherige Versionen aus `int_filemanager.version`
   als ältere Revisionen; Schutzordner → Rechte-Bereiche (Tower: 1 Schutzordner → eigener Bereich, Rest "Alle").
   **Namen, die sich nur in Groß/Klein unterscheiden,** können im Bestand vorkommen: Der Share wird nicht nur über
   SMB beschrieben, sondern auch von Linux-Prozessen (heutiges Modul, Container). Vor dem Import prüfen und melden.
3. **Abgleich** der Änderungen seit der Erstkopie (Größe, mtime, Hash).
4. **Share schreibgeschützt** setzen.
5. **Letzter Abgleich**, dann **Umschalten** (neue Oberfläche aktiv, alter Watcher und Scan aus).
6. **Prüfung:** Anzahl und Hash jeder Datei gegen die Quelle.
7. Originale bleiben **schreibgeschützt** bis zur Abnahme, danach Freigabe des Platzes.

**Dauer:** auf Tower gemessen 27,5 MB/s über einen gemischten Teilbestand (19.3), hochgerechnet rund 18 Stunden für
1,8 TB; der Import läuft wiederholbar in Etappen.

**Rückfall:** Bis zur Abnahme kann der alte Stand wieder beschreibbar gemacht werden.

## 15. Was aus int_filemanager bleibt, was entfällt

| Bleibt (angepasst) | Entfällt |
|---|---|
| Explorer-Oberfläche (Ordnerbaum, Liste, Kacheln, Kontextmenü, Vorschau-Dialoge, PDF-Markierung) | Watcher (`watcher.py`), Vollscan, Hash-Abgleich mit der Platte |
| OCR, Extraktionsmuster, extrahierte Werte, Prüf-Dialog | `index_utils.py` mit rohem SQL, `path_utils.suppress_watcher` |
| Tags, Status, Partner-Verknüpfung (generalisiert), Freigabe-Links, Audio-Player | `write_service.py`, `publish_service.py`, `write_journal` |
| Muster des Durchstichs (Sperren, Vorgangs-ID, Fehlerinjektion in Tests) | pfadbasierte Routen, WebDAV-Tokens im Speicher |
| ONLYOFFICE-Anbindung (auf Revisionen umgestellt) | Schutzordner mit generiertem Regeltext (`acl_rules.py`) |

## 16. Testplan

- **Je Invariante** mindestens ein Test; I1–I6 und I9 zusätzlich mit **Fehlerinjektion** (Prozessabbruch nach jeder
  Stufe, Platte voll, DB weg), wie in 20.2 erprobt.
- **Zuerst – vor dem Code von Schritt 3 – Tests für die Befunde der Code-Prüfung:**
  - **A1/A2 Rechte:** Ein Nicht-Admin liest und schreibt über `call_kw`, JSON-2, `search_read` und `read_group` auf
    **jedem** Modell des Moduls (Knoten, Revision, Blob, Upload, Vorgang, Bereich) – nur Erlaubtes kommt zurück.
  - **A3 Wettläufe:** zwei Prozesse, per Barriere bzw. Fehlerinjektion **zwischen Prüfen und Schreiben** angehalten:
    gleicher neuer Name (→ ein Knoten mit zwei Revisionen bzw. Meldung), gleiche Basisrevision, Umbenennen auf
    denselben Namen, Verschieben gegen Löschen, Sperre länger als `lock_timeout` (→ Wiederholung).
  - **A4 Aufräumjob:** läuft zwischen Deduplizierung und Commit eines Schreibers; alte Markierung; Absturz des
    Aufräumjobs nach dem Löschen einer Datei, vor dem Commit.
  - **Echte Prozesse** für Abbruchtests (`os._exit`/`kill -9`, Neustart, danach Invarianten prüfen);
    `TransactionCase` führt Post-Commit-Hooks nicht aus (`odoo/tests/test_cursor.py`) und simuliert keinen Absturz.
  - Namensindex: gleichnamige Wurzeln werden abgelehnt (A6); eine leere Datei hat eine Revision auf den 0-Byte-Blob
    (A7).
- **Rechte:** Nicht-Admins, Portal-Nutzer und anonyme Freigaben gegen **alle** Zugriffswege: Listen, Suche,
  Gruppierung, `/web/image`, Download-Route, RPC (`call_kw`) auf jede öffentliche Methode, WebDAV.
- **Abgeleitete Dateien (I13):**
  - **Odoo dekodiert nichts:** `image_process`, `ImageProcess` und die PDF-Parser (`pdfminer`, `pypdf`) patchen und mit
    `assert_not_called()` prüfen (`_index_pdf` fängt jede Ausnahme, auch `AssertionError`; eine Ausnahme allein
    beweist nichts). Index-Cache leeren, Gegenprobe mit einem normalen Anhang (der Test darf nicht nur einen
    unbenutzten Pfad bestätigen). Wege: Ergebnis übernehmen, Route ausliefern, Blob-Aufräumjob, alle Rechte-Wege.
  - **Rechte:** Nutzer ohne Leserecht der Revision bekommt nichts; `int_filemanager.derivative` ist für Nicht-Admins über
    `call_kw`, JSON-2, `/web/image` und `/web/content` nicht lesbar; Portal und Freigabe-Link; Fehlertext nur für
    Verwalter.
  - **Aufräumen:** Wettlauf zwischen Aufräumjob und neuem Derivat (wie A4), `derived_blob_id = source_blob_id`, Löschen der
    Quelle, Absturz (`os._exit`) nach dem Ablegen des Ergebnisses vor dem Commit → kein Verlust, Auftrag wird wieder frei.
  - **Warteschlange:** zwei Läufe gleichzeitig (`SKIP LOCKED`), abgelaufene Übernahme, "sichtbares zuerst", Neustart.
  - **Umwandler:** defekte, leere, passwortgeschützte, riesige Datei (Bildbombe), Zeitüberschreitung, Absturz des
    Umwandlers, Umwandler nicht erreichbar → `failed` bzw. Aufträge bleiben offen, Odoo bleibt stabil.
  - **Formate:** Testdateien aus dem echten Bestand je Baustein (Tower).
- **Gleichzeitigkeit:** zwei Saves derselben Basisrevision, Doppelklick, Timeout nach Commit, Verschieben gegen Save.
- **Migration:** Probelauf auf der Testinstanz mit Teilbestand und Vollbestand (Kopie der Live-DB wie in 19.1),
  Zählung und Hash-Abgleich.
- **Last:** wie 20.3 (Baum, Liste, Suche, Download) mit 1–20 Nutzern, zusätzlich Uploads in Stücken.
- **Eingangsordner:** Datei noch im Schreiben (Scanner, große Kopie) wird nicht zu früh übernommen; Abbruch nach dem
  Commit, vor dem Löschen → kein Duplikat; Namenskonflikt im Ziel; Fehlerablage `_fehler`; Rechte des Zielordners.
- **Später, bei WebDAV (`odoo fmdav`):** litmus als automatischer Test; Identitätsregel (Word-, Excel- und
  "löschen-dann-umbenennen"-Muster, Nebenwirkung bei manuellem Umbenennen), Sperrprüfung beim `DELETE`, Groß/Klein,
  leere Datei, gleicher Inhalt, gleichzeitige `PUT` auf denselben Namen, keine offene Transaktion während eines großen
  Uploads (`pg_stat_activity`), paralleler und gedrosselter Upload, Rechte über `ir.rule`; Skripte aus
  `docs/prototypes/fm2/fmdav/tests/` als Vorlage.
- **Werkzeuge (Entscheidung 2026-09-26):** pre-commit nach der OCA-Vorlage (`OCA/oca-addons-repo-template`: black
  bzw. ruff, autoflake, pylint-odoo mit der OCA-Pflichtliste, oca-checks-odoo-module/-po, prettier, eslint) – nur für
  den neuen Code, bestehende Module ausgenommen (Odoo-Regel: vorhandenen Code nicht umformatieren); Odoos `test_lint`
  (`--test-tags /test_lint`) bei jedem Testlauf auf der Testinstanz, pylint dafür per `PYTHONPATH` eingebunden (im
  Image nicht enthalten); **odoo-ls** im Parse-Modus (`odoo/odoo-ls`, Wegwerf-Container aus dem Odoo-Image, Befunde
  nach eigenen Pfaden gefiltert; Aufruf und Fallstricke in `docs/odoo_konventionen_2026-09-26.md` Abschnitt 9).
  Beides zusammen: `tools/v2check/v2check.sh` – scheitert nur an Befunden in seit `int_filemanager-v1` geänderten
  oder neuen Dateien (eingerichtet 2026-09-27).
  Keine GitHub Action. Übersetzung: `i18n/de.po` wird mit jedem Schritt aktualisiert. Datenmodell-Änderungen nach
  Inbetriebnahme über `migrations/` mit `odoo/upgrade-util`, getestet an einer Kopie der Live-DB.
- **Update-Absicherung:** Tests für die genutzten halb-internen Odoo-Stellen (`_check_access`/`_search`-Muster,
  `x_sendfile`-Pfad, Routen, `odoo.cli.command.Command` + Laden aus Addons, `Registry.check_signaling`/
  `signal_changes`, `odoo.service.model.retrying` und welche Fehler es wiederholt, `res.users.apikeys._check_credentials`,
  `_search`-Signatur); ein Image-Update erst nach
  grünem Testlauf auf der Testinstanz.

### 16.1 Zuordnung Grundregeln und Befunde → Tests (Stand 2026-09-28)

Code, Kommentare und Docstrings enthalten keine Kürzel und keine Verweise auf dieses Konzept (Entscheidung
2026-09-28, `docs/odoo_konventionen_2026-09-26.md` Abschnitt 3); die Zuordnung steht nur hier. Testnamen ohne Datei
stehen in `int_filemanager/tests/tower/race_scenarios.py` (echte Prozesse, nur auf der Testinstanz).

| | Tests |
|---|---|
| A1 | `test_v2_access`: `test_revision_has_own_rule_not_inherited_from_node`, `test_blob_not_readable_by_any_non_admin_user`; `test_v2_write_paths`: `test_dedup_check_works_without_a_warm_cache` |
| A2 | `test_v2_access_http` (ganze Datei: `call_kw` und JSON-2) |
| A3 | `scenario_same_new_name_twice`, `scenario_same_base_revision_twice`, `scenario_rename_to_same_name`, `scenario_move_against_delete`, `scenario_lock_timeout_triggers_retry`; `test_v2_blobstore`: `test_recovers_from_concurrent_unique_violation`; `test_v2_fault`: `TestCrossProcessBarrier` |
| A4 | `scenario_blob_gc_against_reuse`; `test_v2_blobstore`: `test_mark_for_gc_renews_mtime_on_existing_marker`, `test_blob_without_revision_past_grace_is_removed`, `test_blob_without_revision_within_grace_survives` |
| I3 | `scenario_crash_create_file`, `scenario_crash_new_revision` |
| I4 | `test_v2_tree`: `test_expired_trash_is_purged_with_its_whole_subtree` |
| I6 | `test_v2_write_paths`: `test_stale_base_revision_raises_conflict_not_silent_overwrite`; `scenario_same_base_revision_twice`, `scenario_crash_new_revision` |
| I7 | `test_v2_upload`: `test_cron_finish_uses_the_uploaders_rights_not_the_crons`; `test_v2_access`, `test_v2_access_http` |
| I9 | `scenario_crash_create_file`, `scenario_crash_new_revision`, `scenario_crash_rename_and_trash` |
| I13 | folgen mit Schritt 5 (Abschnitt 16, "Abgeleitete Dateien") |

## 17. Entscheidungen (Stand 2026-09-26; 17.7 fällt später)

1. **Explorer-Zugriff:** → **entschieden 2026-09-26: Start ohne Explorer-Zugriff (C) plus Eingangsordner (11.1).**
   Ob später WebDAV (`odoo fmdav`, als Bauform bestätigt) oder SMB über Odoo-FUSE dazukommt, wird nach der Nutzung
   entschieden (neue Entscheidung, 17.7).
2. **Umfang:** ~~ganzer Share oder Bereiche außerhalb~~ → **entschieden 2026-09-26: der ganze Share.**
3. **Versionsaufbewahrung:** ~~unbegrenzt oder Regeln~~ → **entschieden 2026-09-26: unbegrenzt** (Aufräumregel kann
   später ergänzt werden).
4. **Papierkorb-Frist:** → **entschieden 2026-09-26: 30 Tage** (wie heute).
5. **Rechte-Bereiche:** → **entschieden 2026-09-26: minimal.** Ein Bereich "Alle" für den ganzen Share, der heutige
   Schutzordner (Tower: 1 Stück) als eigener Bereich; weitere Bereiche erst bei Bedarf. (Tower hat einen internen
   Nutzer außer Admin und keine Portal-Nutzer.)
6. **HM-SRV:** → **entschieden 2026-09-26: HM-SRV behält vorerst das heutige Modul**, Entscheidung später. Folge: die
   Sicherheitslücke N1 (`action_analyze_document`/`action_apply_extracted_values` per RPC mit `sudo`) ist im heutigen
   Modul separat zu beheben, und vor jedem Image-Update dort die C-Kollation (19.2 DB-Vorrang-Konzept).
7. **Später: Netzlaufwerk ja/nein, und wenn ja WebDAV oder SMB-FUSE** – nach Erfahrungen mit Oberfläche und
   Eingangsordner (11).

## 18. Reihenfolge

Abnahmekriterien je Schritt ("fertig, wenn …") und Gegenlesen durch eine zweite Instanz: Kern, Abschnitt 11.

1. ~~Prototypen auf Tower~~ (erledigt, 19).
2. ~~Konzept festschreiben~~ (erledigt 2026-09-26), ~~Freigabe durch den Nutzer~~ (erteilt 2026-09-27).
3. **Fundament:** Test-Image aktualisieren (13), pre-commit, `test_lint` und odoo-ls einrichten (16), **dann die Tests
   für A1–A4 schreiben** (16: erzwungene Überlappung, echter Prozessabbruch), dann Modelle, Blob-Speicher,
   Schreibwege, Rechte, Tests je Invariante.
4. **Oberfläche** auf das neue Modell umstellen.
5. **Vorschau, Text und Metadaten** über den Umwandler (8): **(a)** Testdateien je Format aus dem Bestand sammeln;
   **(b)** dünner Durchstich (JPEG von der Revision bis zur Anzeige, mit Aufräumen, Rechten und den Tests zu I13);
   **(c)** Bausteine parallel (Bild/RAW, Video, Office, PDF und OCR, Metadaten, Text); **(d)** Zusammenspiel und Last
   (Nachholen des Bestands gedrosselt, Absturz- und Wettlauftests auf Tower); **(e)** Gegenlesen, Abnahme mit echten
   Dateien.
6. **Office:** ONLYOFFICE im Browser auf Revisionen umstellen ("Lokal öffnen" erst mit Netzlaufwerk, 10).
7. **Eingangsordner** (11.1): Samba-Freigabe, Import-Cron, Fehlerablage.
8. **Migration:** Probelauf, dann Umstellung Tower. HM-SRV später (17.6).
9. **Später, nach Nutzung:** Entscheidung Netzlaufwerk (17.7); bei WebDAV `odoo fmdav` (11.2) mit
   `int_filemanager.dav_lock`/`int_filemanager.dav_prop`, nginx `/dav`, HTTPS-Zertifikat; bei SMB zuerst Prototyp Samba + Odoo-FUSE (19.14).

---

## 19. Prototyp-Ergebnisse (Tower, 2026-09-26)

**Aufbau:** Testmodul `fm_proto` (auf Tower, Kopie unter `docs/prototypes/fm2/fm_proto`) mit `fm.blob`/`fm.node`/`fm.revision`/`fm.upload`,
eigene DB `fmv2` (PostgreSQL 16), Odoo im **Prefork-Modus** (`workers=2`, `x_sendfile=True`) hinter **nginx**
(`X-Accel-Redirect`, `location /web/filestore/ internal`). Blob-Speicher auf einem temporären Array-Share
`fmv2blobs` (nur `disk3`, kein Cache, **keine** SMB-Freigabe), eingehängt unter `<data_dir>/filestore/fmv2/fm`.
Tests aus einem Hilfscontainer über nginx.

### 19.1 Blob-Speicher, Upload in Stücken, Auslieferung
| Test | Ergebnis |
|---|---|
| 3-GB-Datei hochladen (Stücke 16 MB / 4 MB) | 115 MB/s bzw. 84 MB/s; Hash identisch mit der Quelle; Blob liegt auf `disk3` |
| `finish` (Hash erneut lesen, `fsync`, DB) für 3 GB | **51–56 s im Request**. Für sehr große Dateien gehört das in einen Hintergrundjob (`finish` → Status "wird verarbeitet" → Cron) |
| Download 3 GB über nginx | 9,6 s, Hash identisch; Odoo braucht **5 ms** (nginx liefert per `x_sendfile`, Pfadprüfung `http.py:665-680` greift für den eingehängten Share), kein `X-Accel-Redirect` sichtbar beim Client |
| Range `bytes=1000-1999` | 206, 1000 Bytes, Inhalt korrekt, `Content-Range` korrekt |
| `If-None-Match` mit SHA-256-ETag | 304 |
| Abbruch nach 5 Stücken, Fortsetzen | fortgesetzt ab dem Server-Stand; wiederholtes Stück wird übersprungen (idempotent); Stück mit Lücke → 409 |
| `finish` doppelt | zweites liefert dieselbe Revision (`repeated`), genau **1** Revision |
| Gleicher Inhalt unter anderem Namen | 1 Blob, 2 Knoten (Deduplizierung) |
| Worker-Abbruch (`os._exit`) nach dem Verlinken des Blobs bzw. vor dem Commit | im Prefork stirbt nur der Worker (nginx meldet Fehler, Odoo startet ihn neu); danach Blob auf der Platte, keine DB-Zeile, Upload offen; erneutes `finish` → korrekt, genau 1 Revision (Temp-Datei wird erst nach dem Commit gelöscht) |
| Fehler vor dem Commit → verwaister Blob | Aufräumjob (`@api.autovacuum`, Tabellensperre als erstes Statement, Checkliste) entfernt ihn; referenzierte Blobs bleiben |
| Temp-Datei eines nie abgeschlossenen Uploads | bleibt liegen → Cron für abgelaufene Uploads nötig (geplant) |

### 19.2 Befunde im Odoo-Code, die das Konzept ändern
- **Kein Zugriff auf den rohen Request-Strom über die öffentliche API** (**korrigiert in 19.6:** über das
  mitgeführte Werkzeug-Objekt geht es doch, 3 GB mit konstantem Speicher). Odoos `HTTPRequest` reicht `stream` nicht durch (`HTTPREQUEST_ATTRIBUTES`,
  `http.py:1498-1510`) und filtert `wsgi.input` aus `environ` (`http.py:1480-1495`). Ein Body ist nur über
  `get_data()` erreichbar und liegt dann **ganz im RAM** (begrenzt durch `max_content_length` der Route). Deshalb ist
  der Upload in Stücken zwingend.
- **Speicher der Worker:** Große Request-Bodies lassen die Worker wachsen (bis 1,5–1,9 GB bei 16-MB-Stücken und 3 GB
  Upload). `tracemalloc` zeigt **kein** Python-Leck (keine großen Objekte mehr referenziert); der Speicher liegt in
  anonymen Bereichen und wird vom Allokator nicht zurückgegeben. `MALLOC_MMAP_THRESHOLD_`, `MALLOC_TRIM_THRESHOLD_`
  und `MALLOC_ARENA_MAX` helfen nicht verlässlich. Odoo begrenzt es selbst: Im Prefork-Modus wird ein Worker nach dem
  Request recycelt, sobald `limit_memory_soft` überschritten ist (beobachtet). Kleinere Stücke begrenzen das
  Wachstum (1 MB: 160 MB, 4 MB: rund 200–600 MB, 16 MB: bis 1,9 GB). **Festlegung: Stücke von 4 MB,
  `limit_memory_soft`/`hard` bewusst setzen.**
- **Folge für den Explorer-Zugriff per WebDAV (11 A):** Der Windows-Explorer schickt eine Datei mit **einem** `PUT`.
  Im Odoo-Prozess landet sie komplett im RAM; Dateien im GB-Bereich sind so nicht sauber möglich (Grenze
  `limit_memory_hard`). Option A braucht daher für große Dateien einen WebDAV-Teil **außerhalb** des Odoo-Prozesses
  (eigener kleiner Dienst, der streamt, den Blob schreibt und dann Odoo den Commit machen lässt) oder eine
  Größengrenze für WebDAV-Schreibzugriffe. Das ist beim WebDAV-Prototyp zu klären.
- **`fields.Integer` ist `int4`** (max. ca. 2,1 GB): Dateigrößen als `Float` (double, exakt bis 2^53) oder eigene
  `bigint`-Spalte speichern.

### 19.3 Kopierrate (Migration)
Importwerkzeug (Kopie in einem Durchgang mit Hash, `sync` vor jedem Commit von 500 Dateien, danach DB-Zeilen per
ORM) von der Live-Freigabe (nur lesend, shfs, Array) in den Blob-Speicher (shfs, `disk3`, Array mit Parität):

| Teilbestand | Dateien | Größe | Dauer | Rate |
|---|---|---|---|---|
| `Gemeinde/08 Tontechnik` (viele kleine Dateien) | 59.924 | 29,8 GB | 1.279 s | 23,3 MB/s, 46,9 Dateien/s |
| `Bilder/06 Verwandtschaft Enns` (Fotos) | 2.930 | 12,3 GB | 446 s | 27,7 MB/s |
| `Programme/Mac` (wenige große Dateien) | 32 | 13,0 GB | 283 s | 46,0 MB/s |
| **Gesamt** | **62.886** | **55,1 GB** | **2.008 s** | **27,5 MB/s, 31,3 Dateien/s** |

- 0 Fehler; 32.274 Dateien waren inhaltsgleich mit bereits gespeicherten (vor allem kleine Dateien in `Tontechnik`),
  daher rund 2,5 GB weniger Speicher.
- **Unversehrtheit:** Stichprobe von 300 zufälligen Dateien: Blob-Inhalt = Blob-Name (SHA-256) = Quelldatei, 300 von 300.
- **Hochrechnung für den ganzen Share (1,8 TB):** bei 27,5 MB/s etwa **18 Stunden**, bei 46 MB/s (große Dateien) etwa
  11 Stunden. Begrenzend ist das Array mit Parität (Quelle und Ziel liegen beide auf dem Array). Unraids Schreibmodus
  "reconstruct write" (Turbo Write) dürfte die Rate erhöhen, ist aber nicht getestet. Der Import ist wiederholbar und
  kann über mehrere Nächte laufen (Abschnitt 14).

### 19.4 WebDAV-Netzlaufwerk (Option 11 A)

**Aufbau:** eigener WebDAV-Dienst `fmdav` als Container **neben** Odoo (wegen 19.2 nicht im Odoo-Prozess). Die
Protokollschicht ist die Bibliothek **WsgiDAV 4.3.5** (PROPFIND, LOCK, Windows-/Office-Eigenheiten); selbst
geschrieben ist nur der Provider (`docs/prototypes/fm2/fmdav/dav_service.py`, ca. 530 Zeilen) und die Odoo-Seite
(`docs/prototypes/fm2/fm_proto/dav.py`, ca. 480 Zeilen nach 19.10). Kein WebDAV im Odoo-19-Core (`PROPFIND` kommt dort nicht
vor).
- Der Dienst **schreibt nichts auf die Platte** und hat den Blob-Speicher nicht eingebunden. Jede Operation geht mit dem
  **API-Schlüssel des Nutzers** an Odoo (`auth='bearer'`, Odoo-Bordmittel, `base/models/ir_http.py:212-251`); Odoo
  prüft Rechte und schreibt (I1, I7).
- `PUT`: Der Dienst streamt den Körper und gibt ihn in **4-MB-Stücken** an die Upload-Routen (7, 19.2); Dateien bis
  4 MB in **einem** Aufruf und einem Commit. `GET`: Odoo liefert per `x_sendfile` über nginx, der Dienst reicht durch
  (Range über `seek`).
- Anmeldung: Basic mit Odoo-Login und API-Schlüssel als Passwort. Für den Windows-Test ohne HTTPS: anonymer Zugang
  **nur** für die IP des Arbeitsrechners und nur auf einen Testordner (Testinstanz).
- Sperren und tote Eigenschaften (Win32-Zeitstempel) im Speicher des Dienstes (nur Prototyp).

| Test | Ergebnis |
|---|---|
| **litmus** (Standard-Konformitätstest), Anmeldung mit Login + API-Schlüssel | basic 16/16, copymove 13/13, props 30/30, locks 41/41, http 4/4. Zwei Warnungen (204 statt 201 bei COPY/MOVE auf ein neues Ziel) kommen aus WsgiDAV |
| Windows-WebClient als Netzlaufwerk: Ordnerbaum mit 71 kleinen Dateien kopieren | **20,2 s** (0,28 s je Datei); erneut darüber kopieren 11,9 s; rekursiv auflisten 0,29 s. Vergleich reines WsgiDAV mit Dateisystem auf demselben Server: 2,0 s |
| Upload 40 / 60 MB (Netzlaufwerk) | 2,9 s / 3,2 s |
| Download 40 / 60 MB (Netzlaufwerk) | 0,6 s, Hash identisch / **vom Windows-Client abgelehnt** ("Dateigröße überschreitet die maximal zulässige Größe", `FileSizeLimitInBytes`, Standard 50 MB) |
| 3 GB per `PUT` (curl, Anmeldung per API-Schlüssel) | 90,5 s gesamt, davon **46,5 s Hash-Prüfung in `finish`**; Dienst konstant ~85 MB RAM (Streaming); Odoo-Container max. 1,0 GB; `GET` 10,8 s; Hash identisch |
| **Word-Muster** (Temp schreiben → Original wegbenennen → Temp auf Originalnamen → Weggebenanntes löschen), zweimal gespeichert | **1 Knoten, Revisionen 1–3**, gleiche ID; Temp-Knoten endgültig entfernt (ihr Inhalt liegt in den Versionen), Papierkorb leer |
| **Excel-Muster** (Temp ohne Endung, Original → `.tmp`) | 1 Knoten, Revisionen 1–2 |
| "Original löschen, dann Temp umbenennen" | Original aus dem Papierkorb zurückgeholt, Revision 2 |
| **LibreOffice 26.2** (UNO, Datei vom Netzlaufwerk geöffnet, zweimal gespeichert, `.odt` und `.docx`) | `LOCK` und `PUT` direkt auf die Datei; je 1 Knoten, Revisionen 1–3 |
| Umlaute (`Größe_Übersicht äöü ß.txt`) | korrekt |
| Ordner verschieben / löschen | korrekt; Löschen legt Ordner und Inhalt in den Papierkorb (3 Ordner + 71 Dateien) |
| **Groß/Klein** | Server unterscheidet, Windows nicht: `KLEIN.txt` **und** `klein.txt` entstanden im selben Ordner |

Word und Excel sind hier nur auf Dateiebene nachgespielt (auf dem Arbeitsrechner gibt es kein MS Office). Der Test mit
echtem Word/Excel **entfällt** (Nutzerentscheidung 2026-09-26); bleibt als Restrisiko bis zur Umsetzung von 11 A.

**Befunde:**
1. **Odoo-Grundlast ~25 ms je Request** (**korrigiert in 19.6:** fast ganz Konfiguration, mit `X-Odoo-Database`
   3 ms bzw. 15 ms mit API-Schlüssel) auf Tower, auch für `/web/health` und auf der Live-Instanz (27–33 ms); der
   API-Schlüssel kostet ~7 ms zusätzlich. Der Windows-WebClient schickt je neuer Datei **8 Requests** (PROPFIND,
   leerer PUT, LOCK, PROPPATCH, HEAD, PUT, PROPPATCH, UNLOCK). Ohne Gegenmaßnahme 0,67 s je Datei. Mit einem
   **3-s-Zustands-Cache** im Dienst (eigene Schreibvorgänge verwerfen die Einträge sofort; Änderungen aus der
   Oberfläche sind nach höchstens 3 s sichtbar, vergleichbar dem 10-s-Verzeichnis-Cache von SMB) und dem PUT in einem
   Aufruf: 0,28 s je Datei (3 Odoo-Aufrufe). Weitere Einsparungen sind möglich, die Größenordnung bleibt: **viele kleine
   Dateien sind über das Netzlaufwerk deutlich langsamer als über SMB.**
2. **Identitätsregel ohne Namensmuster:** (a) `MOVE` auf einen belegten Namen: das Ziel bekommt den Inhalt als neue
   Revision. (b) Jeder `MOVE`/`DELETE` einer Datei merkt sich den geräumten Platz (`vacated_*`); zieht **derselbe
   Nutzer** binnen 10 min eine **frische** Datei (≤ 10 min alt) auf diesen Platz, tauschen Original und Temp-Datei
   (Original bekommt Namen und neuen Inhalt zurück). (c) Eine Temp-Datei ("Schatten"), deren Inhalte alle in den
   Versionen des Originals liegen, wird beim Löschen endgültig entfernt, alles andere geht in den Papierkorb (I6).
   Nebenwirkung: Benennt jemand von Hand Datei A weg und binnen 10 min eine neue Datei auf A's Namen, führt A's Verlauf
   mit dem neuen Inhalt weiter; Inhalte gehen dabei nicht verloren. Außerdem: **leere Datei = Knoten ohne Revision**
   (der Explorer legt jede Datei zuerst leer an), **gleicher Inhalt → keine neue Revision**.
3. **Windows-Client-Einstellungen (nicht im Code lösbar):** Basic-Anmeldung nur über HTTPS (`BasicAuthLevel=1`,
   Standard) → HTTPS mit einem Zertifikat, dem die Clients vertrauen (interne CA per Gruppenrichtlinie oder
   öffentliches Zertifikat). Download-Grenze 50 MB (`FileSizeLimitInBytes`, höchstens 4 GB) je Client per
   Gruppenrichtlinie/Registry anheben. Auf dem Arbeitsrechner wurde nichts geändert.
4. **Große Dateien:** Streaming funktioniert mit konstantem Speicher. `finish` liest die Datei für den SHA-256 aber
   noch einmal (3 GB: 46,5 s) – beim WebDAV-`PUT` wartet der Client so lange; das Windows-Zeitlimit dafür ist nicht
   geprüft. Möglichkeiten: Hash im selben Prozess während des Empfangs berechnen (dann schreibt der Dienst die
   Temp-Datei, I1 wäre aufzuweichen) oder Nachbearbeitung als Hintergrundjob mit Zustand "wird verarbeitet" (7).
5. **WsgiDAV-Eigenheiten** (bei Übernahme Version festnageln, Tests für diese Stellen): LOCK-Antwort mit falschem
   `Content-Type: application` (`request_server.py:1283`, im Dienst korrigiert); bei selbst behandeltem `DELETE` prüft
   WsgiDAV nur die Sperre des Elternordners, nicht die der Ressource (`request_server.py:585-599`, im Provider
   ergänzt – ohne das ließ sich eine gesperrte Datei ohne Token löschen); 204 statt 201 bei COPY/MOVE.
6. **Odoo-ORM und eindeutiger Namensindex:** Das ORM kennt den Teil-Unique-Index nicht und schreibt ein
   `UPDATE active=false` erst beim nächsten Flush; ein folgendes `INSERT`/`UPDATE` mit demselben Namen scheitert
   (litmus copymove). Nach dem Verschieben in den Papierkorb und zwischen den Umbenennungen beim Tausch ist
   `flush_recordset()` nötig. Das gilt für alle Schreibwege (6), nicht nur für WebDAV.
7. **Nicht geprüft / nur Prototyp:** Sperren und Eigenschaften liegen nur im Speicher des Dienstes (Neustart verliert
   sie; Odoo-Oberfläche und ONLYOFFICE sehen WebDAV-Sperren nicht) → im Betrieb in Odoo speichern. Rechte-Bereiche
   (`ir.rule`) nicht getestet (`fm_proto` hat keine Regeln). HTTPS am Windows-Client nicht getestet; echtes Word/Excel
   entfällt (siehe oben).

**Folgen für das Konzept (einzuarbeiten beim Festschreiben):**
- **Namen je Ordner ohne Rücksicht auf Groß/Klein eindeutig** (wie SMB/Windows): Teil-Unique-Index auf `lower(name)`
  bzw. eine ICU-Kollation, Auflösung von WebDAV-Pfaden ohne Groß/Klein (4).
- Option A = **WebDAV-Dienst neben Odoo** mit WsgiDAV; Sperren in Odoo (eigenes Modell), damit Oberfläche und
  ONLYOFFICE sie sehen.
- Client-Voraussetzungen (HTTPS-Vertrauen, 50-MB-Grenze) gehören in die Betriebsdoku (13) und sind je Standort
  (Tower, HM-SRV mit AD) zu lösen.

### 19.5 Vergleich: WebDAV in Cloudreve (Code-Stand `cloudreve` lokal, damals 4.18.0; inzwischen 4.19.1)

Geprüft im Quellcode (`pkg/webdav/`, `middleware/auth.go:105-178`, `pkg/filemanager/`), nicht live.

| Punkt | Cloudreve | fmdav (19.4) |
|---|---|---|
| Aufbau | angepasste Kopie von Gos `golang.org/x/net/webdav`, **im Hauptprozess** (`pkg/webdav/webdav.go`, Route `/dav`) | eigener Dienst neben Odoo, WsgiDAV |
| Anmeldung | eigene **WebDAV-Konten** je Nutzer (`ent/schema/davaccount.go`): Name, Zufallspasswort (32 Kleinbuchstaben), **eigener Wurzelordner** (`uri`), Optionen *nur lesen*, *Proxy*, *Systemdateien sperren* (Punkt-Dateien). Passwort liegt **im Klartext** in der DB und wird per SQL-Gleichheit verglichen (`inventory/user.go:435-446`); `OPTIONS` ohne Anmeldung | Odoo-API-Schlüssel (gehasht, benennbar, widerrufbar, optional mit Ablauf), Rechte über Odoo |
| Schreiben (`PUT`) | Stream direkt in den Speicher-Treiber, keine Stücke nötig (Go liest den Body nicht in den RAM) | 4-MB-Stücke an Odoo (Odoo liest Bodies ganz in den RAM, 19.2) |
| Versionen bei `PUT` | nur wenn der Nutzer **Versionsaufbewahrung** einschaltet (`dbfs/upload.go:305-317`), sonst 1 Version = Überschreiben | jede Fassung eine Revision (I6), gleicher Inhalt keine neue |
| `MOVE`/`COPY` mit Überschreiben | **Ziel löschen, Quelle verschieben, umbenennen** (`performCopyMove`, `webdav.go:680-708`) | Ziel behält Identität, bekommt neue Revision |
| Word/Excel-Speichermuster | **keine Sonderbehandlung** (kein Tausch, keine Temp-Erkennung): nach dem Speichern ist `Bericht.docx` ein **neuer** Datensatz; das Original mit Versionen, Freigaben, Tags landet als `~WRL….tmp` im Papierkorb | Identitätsregel (vacated/Tausch/Schatten) |
| Löschen | Papierkorb (`SoftDelete`: Name → UUID, Elternbezug entfernt, `inventory/file.go:409-421`) | Papierkorb (`active=False`) |
| Sperren | **im Speicher** (`pkg/filemanager/lock/memlock.go`), aber **gemeinsam** mit Web-Oberfläche und WOPI; Neustart verliert sie | Prototyp im Speicher des Dienstes; Konzept: `fm.lock` in Odoo |
| Tote Eigenschaften (Win32-Zeiten) | **gespeichert** als Datei-Metadaten mit Präfix `dav:` (`pkg/webdav/prop.go:90-160`) | Prototyp im Speicher; Konzept: nicht speichern |
| Groß/Klein | Namensvergleich exakt, eindeutiger Index `(file_children, name)` → **gleiches Problem** wie im Prototyp | Konzept: Index auf `lower(name COLLATE "und-x-icu")` |
| Lesen (`GET`) | Proxy durch Cloudreve oder **302-Umleitung** auf eine signierte Speicher-URL | Odoo `x_sendfile` über nginx, Dienst reicht durch |
| macOS Finder | `X-Expected-Entity-Length` als Größe akzeptiert (`pkg/request/utils.go:9-33`) | nicht getestet |
| Tests | 2 Unit-Tests (`webdav_test.go`: Overwrite-Header, `performCopyMove`), kein litmus im Repo | litmus 100 % |

**Übernehmen:**
- **Eigener Wurzelordner und "nur lesen" je Zugang:** Ein kleines Modell je API-Schlüssel (Wurzelknoten, nur lesen) macht
  z. B. ein Laufwerk nur für "Scannen" oder einen Lesezugang für ein Gerät möglich. Rechte bleiben trotzdem bei Odoo.
- **`OPTIONS` ohne Anmeldung** beantworten (Windows-WebClient fragt so an; WsgiDAV: Hotfix
  `win_accept_anonymous_options` prüfen).
- **Punkt-/Systemdateien optional sperren** (`.DS_Store`, `._*`, `Thumbs.db`, `desktop.ini`), damit Mac/Windows den
  Bestand nicht mit Hilfsdateien füllen.
- **macOS Finder** (`X-Expected-Entity-Length`, chunked `PUT`) in den Testplan.

**Bestätigt das eigene Konzept:** Cloudreve verliert beim Speichern aus Word/Excel über WebDAV die Identität der
Datei samt Versionen und Freigaben; Versionen sind dort Nutzeroption; Sperren gehen beim Neustart verloren; Namen
unterscheiden Groß/Klein. Die Identitätsregel, "jede Fassung eine Revision" und `fm.lock` in Odoo gehen darüber
hinaus. Der Preis des eigenen Wegs ist die Odoo-Grundlast je Aufruf (19.4 Befund 1), die Cloudreve als ein Go-Prozess
nicht hat.

### 19.6 Nachprüfung: Streaming und Grundlast im Odoo-Prozess

Anlass: Frage, ob WebDAV wie in Cloudreve **im** Hauptprozess (hier: Odoo) laufen kann. Zwei Annahmen aus 19.2/19.4
nachgeprüft, beide waren falsch bzw. unvollständig.

**1. Streaming in einer Odoo-Route ist möglich.** Odoo filtert `wsgi.input` aus `request.httprequest.environ` und
reicht `.stream` nicht durch (`http.py:1480-1510`), führt das originale `werkzeug.Request` aber im Wrapper mit
(`request.httprequest._HTTPRequest__wrapped`; Odoo selbst greift in `make_request_wrap_methods` so darauf zu).
Werkzeug liest den Body erst bei Bedarf; Odoo puffert ihn nicht (bei `retrying` werden nur Formular-Dateien
zurückgespult, `service/model.py:201-204`). Test mit Diagnose-Route (`fm_proto/dav.py`, `FmStreamDiag`,
`max_content_length` 64 GB, direkt auf Odoo ohne nginx):

| Test | Ergebnis |
|---|---|
| 3 GB per `PUT`, in 1-MB-Blöcken in eine Temp-Datei, SHA-256 unterwegs | 36,0 s (~89 MB/s), Hash identisch, **Worker-RSS vorher 89 MB, nachher 89 MB**; Container max. 234 MB |

Folgen: Upload in Stücken ist **nicht** zwingend (für den Browser trotzdem sinnvoll wegen Fortsetzen); der Hash kann
**beim Empfang** berechnet werden, das erneute Lesen in `finish` (3 GB: 46 s) entfällt; WebDAV-`PUT` großer Dateien
ist **im Odoo-Prozess machbar**. Einschränkungen: Zugriff über ein internes, name-gemangeltes Attribut (kein
Core-Patch, I10 bleibt erfüllt, aber kein dokumentierter Weg → Test in der Update-Absicherung, 16); ein Retry nach
Serialisierungsfehler kann den Strom nicht erneut lesen → Body erst vollständig in die Temp-Datei, dann DB-Arbeit, bei
Wiederholung Temp-Datei wiederverwenden (6); nginx braucht passendes `client_max_body_size` und
`proxy_request_buffering off`.

**2. Die ~25 ms Grundlast sind fast ganz Konfiguration.** Profil im Prozess (werkzeug-Testclient, ohne Netz): Requests
ohne Sitzungs-Cookie (API-Schlüssel, `/web/health`) bestimmen die Datenbank über `db_list()`. Sind **`db_name` und
`dbfilter` beide gesetzt**, fragt `list_dbs()` bei **jedem** Request `pg_database` über eine **neue Verbindung** zur
`postgres`-DB ab (`service/db.py:434-452`, `http.py:1813-1840`; `psycopg2.connect` ~15 ms). Entfällt, wenn nur
`db_name` gesetzt ist (ohne `dbfilter`) oder der Client `X-Odoo-Database` schickt. Browser-Sitzungen sind nicht
betroffen (`session.db` ist gesetzt).

| Aufruf (im Prozess) | ohne Header | mit `X-Odoo-Database: fmv2` |
|---|---|---|
| `/web/health` | 21,9 ms | **3,0 ms** |
| `/fmp/dav/stat` mit API-Schlüssel | 34,1 ms | **15,1 ms** (davon 6 ms `pbkdf2_hmac` der API-Schlüssel-Prüfung, ~5 ms für 10 Queries) |

Folgen: Der WebDAV-Dienst (19.4) schickt `X-Odoo-Database` bzw. die Konfiguration setzt nur `db_name`; die
Messungen aus 19.4 (0,28 s je kleiner Datei) sind damit zu pessimistisch. Im Odoo-Prozess bleiben je Request ~3 ms
Grundlast plus Anmeldung plus eigene Queries.

**Folge für Option A (offen, Nutzerentscheidung):** Statt eines eigenen Dienstes kann WebDAV auch **in Odoo** laufen –
WsgiDAV (ein WSGI-Programm) hinter einer Odoo-Route unter `/dav/`, die den rohen Strom als `wsgi.input` weitergibt;
der Provider arbeitet dann direkt mit dem ORM statt über JSON-RPC. Voraussetzungen: `wsgidav` ins Odoo-Image,
Sperren in `fm.lock` (im Prefork-Modus haben die Worker keinen gemeinsamen Speicher), Anmeldung je Request (API-
Schlüssel-Hash 6 ms; ein kurzer Cache geprüfter Zugangsdaten wäre Eigenbau an der Anmeldung). Nicht als Prototyp
geprüft.

### 19.7 Prototyp: WebDAV im Odoo-Prozess

**Aufbau** (`docs/prototypes/fm2/fm_proto/dav_inproc.py`, ca. 640 Zeilen; Pfadauflösung in `dav.py`):
- **WsgiDAV hinter einer Odoo-Route** `/dav/…` (alle WebDAV-Methoden, `type='http'`, `csrf=False`,
  `max_content_length` 64 GB). Die Route reicht das originale WSGI-`environ` mit dem rohen Strom (19.6) an WsgiDAV
  weiter (`SCRIPT_NAME=/dav`), WsgiDAV ist nur Protokollschicht. Der Provider arbeitet **direkt mit dem ORM**
  (dieselben Methoden wie der Dienst: `_dav_move`, `_dav_copy`, `_dav_discard`, `_dav_set_content`, Identitätsregel).
- **Anmeldung** als eigene Auth-Methode `auth='fmdav'` (`ir.http._auth_method_fmdav`; Odoo ruft
  `_auth_method_<name>` generisch auf, `ir_http.py:270-283`): Basic mit Login + API-Schlüssel, dieselbe Prüfung wie
  `auth='bearer'`; geprüfte Zugangsdaten 60 s je Worker zwischengespeichert (6 ms `pbkdf2` je Request gespart,
  widerrufene Schlüssel gelten höchstens 60 s weiter). `OPTIONS` ohne Anmeldung.
- **`PUT`:** Strom direkt in eine Temp-Datei im Blob-Speicher, **SHA-256 beim Empfang**, `fsync`, `link` auf den
  Hash-Namen (`blobstore.adopt_hashed`), kein erneutes Lesen. Leerer Body → keine Temp-Datei (der Explorer schickt
  vor jeder Datei einen leeren PUT). Bei `retrying` wird das Ergebnis des ersten Durchlaufs am Request-Objekt
  wiederverwendet (der Strom ist nicht erneut lesbar).
- **`GET` auf Dateien** beantwortet die Route selbst mit `http.Stream` + `x_sendfile` (nginx liefert); nginx:
  `etag off; add_header ETag $upstream_http_etag;` in der internen Filestore-Location, sonst setzt nginx einen
  eigenen ETag statt des SHA-256.
- **Sperren in `fm.dav.lock`** (alle Worker sehen sie; LOCK/UNLOCK per `pg_advisory_xact_lock` serialisiert; je
  Request einmal geladen), **tote Eigenschaften in `fm.dav.prop` an der Knoten-ID** (überstehen Verschieben ohne
  Zusatzarbeit, I8). Windows-Zeitstempel übernimmt WsgiDAVs Hotfix (nicht gespeichert).
- **Fehler:** WsgiDAV-Antworten ≥ 400 rollen die Transaktion zurück; eigene Middleware statt `ErrorPrinter`, damit
  DB-Konkurrenzfehler bis zu Odoo durchlaufen (`retrying`) und WsgiDAVs Generatoren noch **innerhalb** der
  Transaktion laufen.
- **Pfadauflösung in einer Abfrage** (rekursive CTE, danach `check_access('read')` auf dem Treffer, I7) statt einer
  Abfrage je Ebene.
- Testkonfiguration: `dbfilter` entfernt (nur `db_name`, 19.6), nginx `client_max_body_size 0`, `Host $http_host`
  (sonst scheitert WsgiDAVs Prüfung der `Destination`, weil der Port fehlt).

| Test | Dienst (19.4) | **In Odoo** |
|---|---|---|
| litmus (Login + API-Schlüssel) | 100 % | **100 %** (basic, copymove, props, locks, http) |
| kleiner PUT (curl) | ~220 ms | **65–76 ms** |
| 71 kleine Dateien über das Netzlaufwerk | 20,2 s | **14,1 s** (0,20 s je Datei) |
| dieselben erneut darüber kopieren | 11,9 s | 9,8 s |
| Upload 40 / 60 MB (Netzlaufwerk) | 2,9 / 3,2 s | **1,6 / 2,1 s** |
| Download 40 MB | 0,6 s | 0,1 s |
| 3 GB `PUT` | 90,5 s (davon 46,5 s erneutes Hashen) | **71 s** = Schreibrate des Arrays (1 GiB mit `fsync`: 46 MB/s gemessen) |
| 3 GB `GET` | 10,8 s | 16,1 s (nginx `x_sendfile` in beiden Fällen; Schwankung der Platte) |
| Speicher | Dienst ~85 MB, Odoo bis 1,0 GB | Odoo-Container max. **265 MB** |
| Word-, Excel-, "löschen-dann-umbenennen"-Muster | Identität erhalten | **Identität erhalten** (3 / 2 / 2 Revisionen) |
| LibreOffice (odt, docx) | je 3 Revisionen | **je 3 Revisionen** |
| offene Sperren nach allen Tests | – | 0 |

**Wohin die Zeit bei kleinen Dateien geht** (je Datei 8 Requests, zusammen ~0,2 s): nach 19.6 keine
Verbindungs-Grundlast mehr; je Request 4–24 SQL-Abfragen (0,3–0,6 ms je Abfrage) plus 3–40 ms Python. Den größten
Einzelposten hat der PUT mit Inhalt: **`fsync` auf dem Unraid-Array ~28 ms je Datei** (gemessen; Anlegen, Link,
`fsync` des Ordners je 0,5–3 ms). Das `fsync` ist für I3 nötig; ein Blob-Speicher auf SSD (Cache-Pool) würde es
stark verkürzen – Entscheidung zum Speicherort beim Betrieb (13). Vergleich reines WsgiDAV auf tmpfs: 2,0 s.

**Befund: große Uploads belegen einen Odoo-Worker für die ganze Dauer.** Mit `workers=2` und zwei parallelen
3-GB-Uploads warteten **alle** anderen Anfragen bis zum Ende (57 s bzw. Zeitüberschreitung) – auch die Oberfläche.
(Der Dienst hatte das nicht, weil er in 4-MB-Stücken mit kurzen Requests schreibt.) **Lösung, getestet:** ein
**eigener Odoo-Prozess für `/dav/`** (gleiches Image, gleiche DB und Module, `--max-cron-threads=0`, hier
`--workers=4`), nginx leitet `/dav` dorthin. Während drei paralleler 3-GB-Uploads: Oberfläche 6–300 ms,
WebDAV-PROPFIND über den vierten Worker 37 ms, alle drei Uploads korrekt. Offen: parallele Uploads über die Zahl
der WebDAV-Worker hinaus blockieren WebDAV (nicht die Oberfläche) → Worker-Zahl und ggf. `limit_conn` in nginx für
`PUT` festlegen.

**Grenzen / offen:** Zugriff auf den Strom über ein internes Attribut (Test in der Update-Absicherung, 16); WsgiDAV
und `json5` müssen ins Odoo-Image (reines Python; im Test per `PYTHONPATH` eingebunden); `limit_time_real` muss
große Uploads abdecken (3 GB bei 46 MB/s: 70 s); Sperren sind wie in WsgiDAV pfadbasiert (für die Anzeige in der
Oberfläche zusätzlich Knoten-ID speichern); Rechte-Bereiche (`ir.rule`) weiterhin nicht getestet; litmus-Warnung
`delete_fragment` (Fragment im URI wird vor Odoo entfernt).

**Vergleich und Empfehlung:** "In Odoo" ist schneller (kein JSON-RPC, kein zweites Hashen), braucht keinen zweiten
Code-Stand und keine Übersetzungsschicht, Sperren und Eigenschaften liegen ohnehin in Odoo. Der eigene
Odoo-Prozess für `/dav/` ist nur eine zweite Instanz desselben Codes. **Empfehlung: Option A als WebDAV im
Odoo-Prozess mit eigenem Odoo-Prozess für `/dav/`** statt des separaten Dienstes aus 19.4 (Nutzerentscheidung).

### 19.8 Nachprüfung der Bauform "WebDAV in Odoo" gegen Cloudreve (Stolpersteine)

Anlass: Frage des Nutzers, ob 19.7 wirklich sauber ist. Geprüft an den Stellen, an denen Cloudreve als Go-Prozess
grundsätzlich anders arbeitet. **Cloudreve** (`pkg/filemanager/manager/upload.go:418-459`,
`pkg/filemanager/fs/dbfs/upload.go:183, 321`): Upload in drei Schritten – kurze Transaktion (Platzhalter-Datei, Sperre),
**Datenstrom ohne offene Transaktion**, kurze Transaktion zum Abschluss mit **erneuter Sperrprüfung**
(`ConfirmLock`); bei Fehlern `OnUploadFailed` (Aufräumen); keine Server-Zeitlimits (kein `ReadTimeout` im Code).

| # | Stolperstein | Befund (Tower) | Maßnahme | Stand |
|---|---|---|---|---|
| 1 | **Offene Transaktion während des Uploads** | Odoo hält die Request-Transaktion den ganzen Upload lang: `pg_stat_activity` zeigte `idle in transaction` nach 15/30/45 s (3 GB). Hält den Snapshot (bremst VACUUM der ganzen DB), belegt die Verbindung, macht Konflikte beim Abschluss wahrscheinlich. Betraf auch den Dienst aus 19.4 (`finish` mit 46 s Hashen in einer Transaktion). | Wie Cloudreve: **vor dem Datenstrom `commit()`** (bis dahin nur gelesen), ORM- und Sperren-Cache verwerfen; Abschluss in neuer kurzer Transaktion mit **erneuter Sperr- und Zielprüfung** | behoben, getestet: keine offene Transaktion während 3 GB, Datei korrekt |
| 2 | **Langsame Clients gegen `limit_time_real`** | Worker wird nach Ablauf abgeschossen: 200 MB mit 5 MB/s bei Limit 20 s → Abbruch nach 21 s (502). Mit 1800 s bräche z. B. 3 GB über 1,5-MB/s-VPN ab. Solange der Client sendet, ist der Worker belegt. | **nginx puffert WebDAV-`PUT`s** (`proxy_request_buffering on`, `client_body_temp_path` auf schnellem Speicher mit Platz): Odoo bekommt den Body erst, wenn er vollständig da ist, und ist nur für das Schreiben belegt | getestet: gleicher Fall → 201 nach 44 s, Worker-Limit 20 s eingehalten. Kosten: Temp-Platz in nginx für parallele Uploads, einmal mehr schreiben |
| 3 | **Verwaiste Temp-Dateien** | abgebrochener Upload hinterließ 108 MB in `<blobroot>/tmp` | Aufräumjob (Cron) für Temp-Dateien älter als N Stunden; wie `OnUploadFailed`/abgelaufene Upload-Sitzungen bei Cloudreve | offen (einfach) |
| 4 | Worker-Belegung durch große Uploads | siehe 19.7 | eigener Odoo-Prozess für `/dav/`; mit Maßnahme 2 belegt ein Upload einen Worker nur für die Schreibdauer (3 GB ≈ 70 s bei 46 MB/s) | getestet (19.7) |
| 5 | Zugriff auf den Strom über internes Attribut `_HTTPRequest__wrapped` | kein dokumentierter Weg (Cloudreve: nativ) | Test in der Update-Absicherung (16); bei Änderung durch Odoo bricht nur `PUT` | Restrisiko |
| 6 | Wiederholung nach DB-Konflikt (`retrying`) liest den Strom nicht erneut | Ergebnis des ersten Durchlaufs wird am Request wiederverwendet | eingebaut, **nicht mit Fehlerinjektion getestet** | offen |
| 7 | Zwei gleichzeitige `PUT` auf denselben neuen Namen | Cloudreve: zweiter scheitert an der Platzhalter-Sperre. Hier: beide streamen, der spätere wird neue Revision (Unique-Index + Retry), nichts geht verloren (I6) | bewusst so, oder Platzhalter wie Cloudreve | Entscheidung bei Umsetzung. **Korrektur 19.17:** `retrying()` wiederholt die `UniqueViolation` nicht → Regeln in 6 (A3) |
| 8 | Widerruf eines API-Schlüssels | durch den 60-s-Zwischenspeicher je Worker bis zu 60 s wirksam | Zeit kürzer wählen oder Cache abschalten (+6 ms je Request) | bewusst |
| 9 | WsgiDAV-Eigenheiten | zwei Fehler umgangen (19.4 Befund 5) | Version festnageln, Tests | bewusst |
| 10 | Windows-Client (HTTPS-Vertrauen, 50-MB-Grenze, Groß/Klein) | betrifft Cloudreve genauso | 13, 4 | unverändert |

Geprüft und **kein** Stolperstein: keine Sitzungsdateien durch WebDAV-Requests (0 vor/nach); chunked `PUT` ohne
Größenangabe (macOS Finder) funktioniert über nginx und direkt; nginx liefert Downloads per `x_sendfile` mit dem
SHA-256 als ETag (nach der Korrektur aus 19.7).

**Ergebnis:** Die Bauform aus 19.7 war **nicht** ohne Stolpersteine; drei davon (1–3) sind echte Fehler, die im
Betrieb aufgefallen wären. 1 und 2 sind behoben bzw. mit nginx-Konfiguration gelöst und getestet, 3 ist ein kleiner
Cron. Danach bleibt als grundsätzlicher Unterschied zu Cloudreve: Odoo braucht für lange Uploads einen eigenen
Prozess, einen Puffer in nginx und einen Griff an ein internes Attribut – Cloudreve braucht das als ein Go-Prozess
nicht. **Empfehlung unverändert** (WebDAV in Odoo mit eigenem Prozess für `/dav/`), aber nur zusammen mit den
Maßnahmen 1–3 und Tests für 5 und 6.

### 19.9 Internet-Recherche: fertige WebDAV-Lösungen für Odoo (2026-09-26)

Gesucht: ein gepflegtes Modul, das Odoo-Dateien per WebDAV bereitstellt (Odoo als WebDAV-**Server**, Netzlaufwerk).

| Kandidat | Befund |
|---|---|
| `document_webdav` / `document_webdav_fast` (Odoo S.A., initOS) | nur bis OpenERP 7/8, danach aus Odoo entfernt |
| OCA `base_dav` (server-backend) | nur CalDAV/CardDAV über Radicale, Stand Odoo 11; "plain WebDAV collections" stand nur auf der Roadmap; in `server-backend` 17.0/18.0 nicht mehr vorhanden (per GitHub-API geprüft), Issue "base_dav dead?" ohne Antwort geschlossen |
| OCA `dms`, `knowledge`, `storage` (17.0/18.0) | kein WebDAV-Server-Modul (Verzeichnisse per GitHub-API geprüft); `fs_folder_webdav` ist die **Gegenrichtung** (Odoo als Client externer WebDAV-Speicher, z. B. Nextcloud) |
| Odoo App Store, Suche "webdav" (auch kommerziell) | ausschließlich **Clients/Sync** (Nextcloud, NAS, Cloud-Speicher; 25–487 €); einziger Server: `document_webdav_fast` für 7.0 |
| Odoo Enterprise "Documents" | kein WebDAV; empfohlen wird Sync nach Google Drive/Nextcloud |
| **Vertel AB `dms_webdav`** (GitHub `vertelab/odoo-document`, Odoo 18, AGPL, Juni 2026, 0 Sterne) – einziges aktuelles Server-Modul, per GitHub-Code-Suche nach `PROPFIND` + `http.route` gefunden, Controller vollständig gelesen | eigener Minimal-WebDAV in einer Odoo-Route für OCA-DMS: **Body ganz im RAM** (`httprequest.data`) und zusätzlich base64 (`dms.file.content`), ebenso beim `GET`; Anmeldung mit **Passwort** und `session.authenticate` bei **jedem** Request über **alle** Datenbanken; **keine echten Sperren** (Token = Nutzer-ID, beliebiger Client entsperrt); `MOVE` ignoriert `Overwrite` und verweigert belegte Ziele (Word/Excel-Speichern scheitert oder verliert die Identität); XML per Zeichenkette ohne Escaping (Namen mit `&`/`<` brechen die Antwort); keine Tests mit litmus erkennbar |
| **Seafile `seafdav`** (Vergleich außerhalb Odoo) | **WsgiDAV-Fork** als **eigener Prozess** (gunicorn, 5 Worker) hinter nginx (`client_max_body_size 0`, `proxy_read_timeout 1200s`); Handbuch nennt dieselbe Windows-50-MB-Grenze und warnt vor Leistungsgrenzen beim Einbinden als Laufwerk ("eher für gelegentlichen Zugriff") |

**Ergebnis:** Es gibt **keine fertige, saubere WebDAV-Lösung für aktuelle Odoo-Versionen.** Der Markt löst
"Odoo-Dateien im Explorer" fast nur über Synchronisation in ein zweites System (Nextcloud, Google Drive) – das
widerspricht "Odoo als alleiniger Schreiber" (I1). Das einzige aktuelle Server-Modul (Vertel) hat genau die
Probleme, die 19.2–19.8 gefunden und gelöst haben (RAM, Sperren, Identität beim Speichern, Anmeldung). **Das
eigene Vorgehen – WsgiDAV als Protokollschicht, Odoo als Schreiber – entspricht dem bewährten Muster von Seafile.**
Seafile betreibt WsgiDAV als eigenen Prozess; das stützt beide Bauformen aus 19.4/19.7 (eigener Prozess), nicht
aber einen Einbau in die normalen Odoo-Worker ohne eigene Instanz.

### 19.10 Prototyp: WebDAV als eigener Odoo-Befehl `odoo fmdav`

**Idee:** WsgiDAV nutzt Odoos Registry und ORM direkt, läuft aber **außerhalb von Odoos HTTP-Schicht und
Prefork-Modell**. Odoo 19 lädt Befehle aus Addons: `<addon>/cli/<befehl>.py` mit einer Unterklasse von
`odoo.cli.command.Command` (`odoo/cli/command.py:68-105`; so auch `odoo shell`). Das frühere
`register_wsgi_handler` gibt es in Odoo 19 nicht mehr.

**Aufbau** (`docs/prototypes/fm2/fm_proto/cli/fmdav.py` ca. 50 Zeilen, `fm_proto/dav_server.py` ca. 630 Zeilen;
Modelle `fm.dav.lock`/`fm.dav.prop` und die `fm.node`-Methoden unverändert aus 19.4/19.7):
- Aufruf: `odoo --addons-path=<pfade> fmdav -c odoo.conf -d <db> --dav-root=<id> --dav-accel=/web/filestore`
  (`--addons-path` muss **vor** dem Befehlsnamen stehen, sonst findet Odoo den Befehl nicht, `command.py:112`).
  Gleiches Image, eigener Container; Start wie `odoo shell` (`config.parse_config`, `server.start(preload=[], stop=True)`).
- Server: werkzeugs `ThreadedWSGIServer` (wie Odoo im Thread-Modus, HTTP/1.1), ein Thread je Verbindung.
- Je Anfrage: `Registry(db).check_signaling()`, Anmeldung (API-Schlüssel wie `auth='bearer'`, 60 s Cache),
  `with registry.cursor()` + `api.Environment(cr, uid, {})` (Rechte des Nutzers, I7), danach `signal_changes()` bzw.
  bei Fehler `reset_changes()` – das Muster von `ir_cron` und `odoo shell`.
- Wiederholung bei DB-Konflikten mit Odoos `retrying()`: ganze Anfrage außer `PUT` (XML-Body bis 16 MB
  gepuffert); beim `PUT` nur der kurze Abschluss.
- `PUT` wie Cloudreve: lesen/prüfen → `commit` (eigener Cursor) → Datenstrom **ohne** Transaktion, SHA-256 beim
  Empfang, `fsync` → kurze Abschluss-Transaktion mit erneuter Sperr- und Zielprüfung.
- Der rohe Strom kommt direkt aus dem WSGI-`environ`; **nötig war** `werkzeug.wsgi.get_input_stream(environ)`, weil
  werkzeugs Server sonst den rohen Socket liefert und WsgiDAV bei Keep-Alive bis zum Verbindungsende wartet (PUT hing).
- `GET` auf Dateien: Antwort mit `X-Accel-Redirect`, nginx liefert (Range, ETag = SHA-256); der Thread ist sofort frei.
- `OPTIONS` ohne Anmeldung. Kein `dbfilter`/`db_list`, keine Sitzungen, kein internes Attribut.
- Befund am Rande: `my_default` greift in Odoo 19 nicht für nachträglich hinzugefügte Optionsgruppen – Standardwerte
  im Befehl setzen.

| Test | Dienst (19.4) | In Odoo (19.7/19.8) | **`odoo fmdav`** |
|---|---|---|---|
| litmus (Login + API-Schlüssel) | 100 % | 100 % | **100 %** (auf Anhieb) |
| kleiner PUT | ~220 ms | 65–76 ms | **60–65 ms** |
| 71 kleine Dateien (Netzlaufwerk) | 20,2 s | 14,1 s | **13,0 s** |
| erneut darüber kopieren | 11,9 s | 9,8 s | 9,3 s |
| Upload 40 / 60 MB | 2,9 / 3,2 s | 1,6 / 2,1 s | **1,4 / 2,0 s** |
| Download 40 MB | 0,6 s | 0,1 s | 0,1 s |
| 3 GB `PUT` | 90,5 s | 71 s | **71,5 s** (= Array-Schreibrate) |
| offene Transaktion während 3 GB | ja (in `finish`) | ja → mit Zwischen-Commit behoben | **nein** (15/30/45 s geprüft) |
| Speicher | Dienst 85 MB + Odoo bis 1 GB | Odoo 265 MB | **fmdav max. 108 MB** |
| 3 parallele 3-GB-Uploads + 1 langsamer (200 MB mit 5 MB/s) | – | mit `workers=2` alles blockiert; mit eigenem Prozess (4 Worker) ok | WebDAV 50–98 ms, Oberfläche 6–321 ms; alle korrekt |
| langsamer Client | – | Abbruch bei `limit_time_real` → nginx-Puffer nötig | **läuft durch** (40,6 s), kein Puffer, kein Zeitlimit |
| 10 gleichzeitige `PUT` auf denselben neuen Namen | – | – | **1 Knoten, 10 Revisionen**, kein Fehler (**Korrektur 19.17:** Wettlauf zeitlich nicht getroffen, A3) |
| Word-/Excel-/"löschen-dann-umbenennen"-Muster, LibreOffice | Identität erhalten | Identität erhalten | **Identität erhalten** (3/2/2 bzw. je 3 Revisionen), 0 offene Sperren |

**Stolpersteine aus 19.8 – Stand bei `odoo fmdav`:**

| # | Stolperstein | Stand |
|---|---|---|
| 1 | offene Transaktion während des Uploads | entfällt durch Aufbau (eigener Cursor, Transaktionen nur um die kurzen Schritte) – gemessen |
| 2 | langsame Clients / `limit_time_real` / belegte Worker | entfällt (Thread je Verbindung, kein Zeitlimit) – gemessen |
| 3 | verwaiste Temp-Dateien | **offen**: Aufräumjob (Cron im normalen Odoo) |
| 4 | Worker-Belegung | entfällt; Grenze sind Threads und DB-Verbindungen (`db_maxconn`, Standard 64) |
| 5 | internes Attribut `_HTTPRequest__wrapped` | entfällt (Strom direkt aus dem WSGI-`environ`) |
| 6 | Wiederholung nach DB-Konflikt | eingebaut mit Odoos `retrying()`; Wettlauf mit 10 gleichzeitigen PUTs korrekt |
| 7–10 | Namens-Wettlauf, Schlüssel-Widerruf 60 s, WsgiDAV-Eigenheiten, Windows-Client | wie 19.8 |

**Was bleibt:** ein eigener Prozess/Container (wie Seafile; nach Modul-Updates neu starten); der Befehl hängt an
öffentlichen, aber wenig dokumentierten Odoo-Einstiegspunkten (`Command`, `Registry`, `retrying`) → Test in der
Update-Absicherung (16); werkzeugs Entwicklungs-Server als Thread-Server (von Odoo selbst so genutzt; bei Bedarf
austauschbar, z. B. gegen cheroot); WsgiDAV/`json5` ins Image; `fsync`-Kosten auf dem Array; Aufräumjob.

**Empfehlung: Option A als `odoo fmdav`** – die sauberste der drei Bauformen: gleicher Code und direkter
ORM-Zugriff wie "in Odoo", aber ohne Odoos HTTP- und Prefork-Grenzen und ohne Kniffe (kein Zwischen-Commit in einer
Odoo-Route, kein internes Attribut, kein nginx-Puffer, keine Zeitlimit-Ausnahmen). Nutzerentscheidung.

### 19.11 Was in Odoo 19 Goroutinen am nächsten kommt (Code-Prüfung, 2026-09-26)

Anlass: Frage des Nutzers, welcher Odoo-Mechanismus Goroutinen am saubersten entspricht; der Entwurf aus 19.10 ist
dabei nicht als endgültig betrachtet. Geprüft: `odoo/service/server.py` (alle Server-Modi), `odoo/_monkeypatches/site.py`,
`addons/bus/websocket.py`, `addons/bus/controllers/websocket.py`.

**Was Odoo mitbringt:**

| Mechanismus | Fundstelle | Eigenschaften |
|---|---|---|
| **gevent-Prozess** (`odoo gevent`, "Evented Service") | `server.py:767-880` (`GeventServer`, `gevent.pywsgi`); im Prefork startet der Master ihn selbst als Unterprozess (`server.py:944-948`, `long_polling_spawn`), also **im selben Container**; `_monkeypatches/site.py:22-53`: `gevent.monkey.patch_all()` und ein psycopg2-Warte-Callback (PostgreSQL kooperativ) | **am nächsten an Goroutinen**: ein Greenlet je Verbindung, bedient **Odoos ganze WSGI-Anwendung** (alle Routen), **kein `limit_time_real`**, nur Speicherwächter (`limit_memory_soft_gevent`, Neustart per SIGTERM), eigene Verbindungsgrenze `db_maxconn_gevent` (`sql_db.py:823`). Ein Kern, kooperativ. |
| **Muster für lange Arbeit ohne lange Transaktion** | Websockets: Route antwortet sofort (Handshake), `response.call_on_close(...)` arbeitet **nach** dem Ende der Request-Transaktion auf dem rohen Socket weiter (`bus/websocket.py:1000-1037`); je Nachricht `Registry(db).check_signaling()`, eigener Cursor (`acquire_cursor`), `service_model.retrying` (`:906-935`) | genau das Cloudreve-Muster (kurze Transaktionen um die Arbeit). Der Socket kommt aus `request.httprequest._HTTPRequest__environ['socket']` – **Odoo selbst greift auf dieses interne Attribut zu**, gesetzt nur vom gevent-Server (`server.py:835-845`) und vom Thread-Server (`server.py:204-214`), nicht von Prefork-Workern |
| **Thread-Server** (`workers=0`) | `server.py:241-315, 451-535` | Thread je Request, optional begrenzt (`ODOO_MAX_HTTP_THREADS`, Semaphor); `limit_time_real` gilt auch für HTTP-Threads (`process_limit`), **außer** für Threads mit `type == 'websocket'` (vom Bus gesetzt, `bus/websocket.py:1118`) |
| Prefork-Worker | `server.py:1229-1403` | ein Request je Prozess, `limit_time_real`, kein Socket im environ |

**Eignung für WebDAV (dateilastig, große Bodies):**
- **gevent-Prozess:** Goroutinen-ähnlich und ohne zusätzlichen Container, aber drei Stolpersteine:
  1. **Blockierende Plattenarbeit hält den ganzen Prozess an.** gevent macht Dateizugriffe nicht kooperativ.
     Gemessen (Testskript `docs/prototypes/fm2/tests/gevent_fsync_blockade.py`, 1 GB auf das Array schreiben +
     `fsync`): **alle anderen Greenlets standen 22,4 s still**; mit `fsync` im gevent-Threadpool 0,23 s. Jede
     Plattenoperation (`fsync`, `link`, `makedirs`, `open` auf dem FUSE-Share) müsste ausgelagert werden – vergisst man
     eine, frieren alle Verbindungen ein.
  2. **Geteiltes Schicksal mit den Websockets:** Derselbe Prozess trägt die Live-Benachrichtigungen (Chat, Aktivitäten)
     **aller** Nutzer. Eine Blockade, ein Speicher-Neustart (`limit_memory_soft_gevent`, beendet auch laufende
     Uploads) oder ein Fehler in WebDAV trifft die ganze Oberfläche.
  3. **Odoos HTTP-Schicht bleibt:** WebDAV über normale Routen hätte wieder die Transaktion um den ganzen Request und
     den Strom nur über das interne Attribut (19.7/19.8), also wieder Kniffe. Das Websocket-Muster
     (`call_on_close`) hilft beim `PUT` nicht, weil der Body vor der Antwort gelesen werden muss.
- **Thread-Server als WebDAV-Weg:** nur mit `workers=0` und dem Kniff, den eigenen Thread als `websocket` zu
  markieren, um dem Zeitlimit zu entgehen – Zweckentfremdung.
- **`odoo fmdav` (19.10):** nutzt aus der Liste genau die sauberen Teile – das Transaktionsmuster der Websockets
  (`check_signaling`, eigener Cursor, `retrying`) und Threads, bei denen Plattenarbeit nur den eigenen Thread
  blockiert –, ohne Odoos HTTP-Schicht und ohne den Ereignisprozess mit den Websockets zu teilen.

**Ergebnis:** Odoos Entsprechung zu Goroutinen ist der **gevent-Prozess** – für viele meist ruhende Verbindungen
(Websockets) gebaut, nicht für Plattenarbeit. Für einen Dateiserver ist er nur mit strikter Disziplin (jede
Dateioperation in den Threadpool) und mit geteiltem Risiko für die Oberfläche nutzbar. **`odoo fmdav` mit Threads
bleibt die sauberste Bauform**; der zusätzliche Container ist der einzige Preis (Odoo selbst betreibt für lange
Verbindungen ebenfalls einen zweiten Prozess, nur startet ihn dort der Prefork-Master).

### 19.12 `odoo fmdav` ohne eigenen Container? (Code-Prüfung und Test, 2026-09-26)

**Einstiegspunkte im Odoo-19-Core für einen Dienst im selben Container/Prozess:**

| Stelle | Befund |
|---|---|
| `server_wide_modules` + Manifest `post_load` (`modules/module.py:512`, `service/server.py:1511, 1621`) | läuft in **jedem** Prozess, der die server-weiten Module lädt: Master bzw. Thread-Server, aber auch `odoo gevent` (neu gestartet), `odoo shell`, `odoo fmdav`, `-u --stop-after-init` → abgrenzen über `odoo.cli.COMMAND == 'server'`, `not odoo.evented`, `stop_after_init` |
| `CommonServer.on_stop(func)` (`server.py:437-449`) | dokumentierter Aufräum-Hook, im Core genutzt vom `bus` (`bus.py:276`, `websocket.py:1154`); wird beim normalen Stopp aufgerufen, **beim Neuladen im Prefork-Modus nicht** (`PreforkServer.stop`, Zweig `server_phoenix` → `fork_and_reload`, `server.py:1174-1186`) |
| Vorbild Hintergrund-Thread | `bus.ImDispatch` (`bus.py:225-290`): eigener Thread, Wiederanlauf-Schleife, Ende über `on_stop` |
| Prefork-Master (`server.py:995-1047`) | startet nur eigene Prozessarten (HTTP-/Cron-Worker, `odoo gevent`); **kein Hook** für weitere Prozesse; `process_zombie` sammelt **jedes** Kind ein (`waitpid(-1)`), startet fremde nicht neu; Kind mit Exit-Code 3 → Master beendet sich |
| WSGI-Einstieg | kein Registrieren zusätzlicher WSGI-Anwendungen mehr (`register_wsgi_handler` entfernt) |

**Geprüfte Varianten** (`fm_proto/dav_embed.py`, `fm_proto/__init__.py`: `post_load`; Start mit
`--load=base,rpc,web,fm_proto` und `FM_DAV_EMBED=1`):

| Variante | Test | Ergebnis |
|---|---|---|
| **C: Thread-Modus (`workers=0`)**, WebDAV-Server als Thread im Odoo-Prozess (Muster `bus.ImDispatch`) | Start | 1 Prozess, Odoo 8069 + WebDAV 8080 |
| | litmus | **100 %** |
| | Neuladen (SIGHUP, wie nach Modul-Installation) | sauber: Odoo ersetzt sich per `exec`, Thread startet neu, kein Port-Konflikt, PUT/GET ok |
| | Zeitlimit (`limit_time_real=20`), gedrosselter Upload 40 s | **läuft durch** (WebDAV-Threads sind Daemon-Threads ohne `start_time`, `process_limit` erfasst sie nicht) |
| | Oberfläche während 200-MB-gedrosselt + 3-GB-Upload | `/web/login` 6–351 ms, PROPFIND 53–60 ms |
| **B: Prefork (`workers=2`)**, Master startet `odoo fmdav` als Kindprozess (wie `odoo gevent`), Stopp über `on_stop` | Start | läuft neben Workern und gevent-Prozess, PUT ok |
| | Absturz (`kill -9` des Kindes) | Master sammelt es ein, **kein Neustart** → WebDAV bis zum Container-Neustart weg (502) |
| | Neuladen (SIGHUP) | `on_stop` wird nicht aufgerufen, der **alte `fmdav` mit altem Code läuft weiter**, der neue scheitert an "Port 8080 is in use" → nach jedem Modul-Update läuft WebDAV unbemerkt mit veraltetem Code |
| | Stopp (`docker stop`) | 2 s, sauber |

Nebenbefund, behoben: `odoo fmdav` rief wie `odoo shell` `server.start(stop=True)` auf; mit `workers>0` aus der
Konfiguration bindet das kurz einen Prefork-Server an den HTTP-Port (scheitert neben einem laufenden Odoo). Jetzt nur
`server.load_server_wide_modules()`. Außerdem: `config.rcfile` ist in Odoo 19 veraltet → `config['config']`.

**Ergebnis:**
- **Prefork-Odoo:** Es gibt **keinen sauberen Weg** ohne eigenen Container. Odoo kennt keinen Hook für zusätzliche,
  überwachte Prozesse; die Variante B hat zwei gemessene Stolpersteine (kein Neustart nach Absturz, veralteter Code
  nach dem Neuladen). Beheben ließe sich das nur durch Eingriffe in den Master (I10) oder einen eigenen Überwacher –
  das wäre ein Nachbau dessen, was Docker bereits leistet.
- **Odoo im Thread-Modus (`workers=0`):** **Variante C ist sauber** und getestet – ein Prozess, ein Container, nach
  dem Vorbild von `bus.ImDispatch`. Preis: ganz Odoo im Thread-Modus (von Odoo für den Produktivbetrieb nicht
  empfohlen, GIL und Speichergrenze werden mit der Oberfläche geteilt). Für Tower (ein Nutzer, Live-Instanz läuft
  heute schon ohne `workers`) vertretbar.
- **Derselbe Code trägt beide Betriebsarten:** `odoo fmdav` als eigener Container (Prefork, mehrere Nutzer,
  HM-SRV) oder eingebettet als Thread (Thread-Modus, Tower). Die Wahl ist Konfiguration, keine Architekturfrage.

**Nachtrag zu 19.9 – Python-WebDAV-Server insgesamt (PyPI/GitHub, 2026-09-26):**

| Paket | Stand | Bewertung für Odoo |
|---|---|---|
| **WsgiDAV** (MIT) | 4.3.5 vom 27.06.2026, letzter Push 20.09.2026, 1.234 Sterne | synchron (passt zum synchronen ORM), austauschbarer Provider, Sperr- und Eigenschaftsablage; Grundlage von Seafiles `seafdav`; **gewählt** |
| **ASGIWebDAV** (MIT, `rexzhang/asgi-webdav`) | 2.0.1 vom 20.02.2026, letzter Push 24.08.2026, 89 Sterne, ca. 8.100 Zeilen | einziger weitere aktuelle Voll-Server; litmus laut Projekt bestanden; **asynchron** (ASGI, `aiofiles`). Für Odoo ungünstig: das ORM ist synchron, jeder ORM-Aufruf müsste in einen Thread ausgelagert werden, und Odoos Cursor/Umgebung sind an einen Thread gebunden; Sperren nur im Speicher (`lock.py`, Dictionaries); Provider auf Dateisystem/Speicher/WebHDFS ausgelegt; braucht zusätzlich einen ASGI-Server (z. B. uvicorn) |
| PyWebDAV3 (LGPL) | 0.11.0 von 2024, letzter Push 11/2025 | Nachfolger der OpenERP-Grundlage, wenig Pflege |
| asgi_dav | letzter Push 2024, 0 Sterne | Minimalumsetzung über pyfilesystem2 |
| DjangoDav | 0.0.1b23 von 2017 | verwaist |
| Radicale, xandikos | aktuell | nur CalDAV/CardDAV |
| Zope (`webdav` im Zope-Server) | aktuell | an Zope/ZODB gebunden, nicht einbettbar |

### 19.13 Vergleich: WebDAV in Nextcloud (Code `nextcloud/server`, Stand 2026-09-26)

Geprüft im Quellcode (`apps/dav/lib/Connector/Sabre/`, `apps/files_versions/lib/Listener/FileEventsListener.php`,
App `nextcloud/files_lock`) und in der Nutzer-Doku; nicht live getestet.

| Punkt | Nextcloud | `odoo fmdav` |
|---|---|---|
| Protokollschicht | **SabreDAV** 4.7 (PHP), im Nextcloud-Prozess, Plugins je Funktion | WsgiDAV |
| Sperren im Kern | **keine echten WebDAV-Sperren**: für `Microsoft-WebDAV-MiniRedir` (Windows-Explorer), `WebDAVFS` (macOS Finder) und `OneNote` wird ein `FakeLockerPlugin` eingehängt, das jedes LOCK/UNLOCK bestätigt, ohne zu sperren (`ServerFactory.php:122-130`, `FakeLockerPlugin.php`). Das `LockPlugin` ist nur das interne, kurzzeitige Datei-Locking während eines Requests | echte Sperren in der DB (`fm.dav.lock`) |
| Sperren mit App | optionale App **`files_lock`**: Sperren in der DB, geteilt zwischen Oberfläche, Nextcloud Office/Text und WebDAV (Typ 2 = WebDAV-Token) | entspricht `fm.dav.lock` + Anzeige in der Oberfläche |
| `PUT` | Strom in eine Hilfsdatei `.ocTransferId<id>.part`, danach Umbenennen auf das Ziel unter exklusiver interner Sperre; Datei-ID bleibt beim Überschreiben erhalten; Prüfsumme **nur** wenn der Client `OC-Checksum` schickt (`File.php:115-420`) | Strom in Temp-Datei, SHA-256 **serverseitig** beim Empfang, Blob unveränderlich |
| Versionen | **am Pfad** (Standard-Backend): Umbenennen nimmt die Versionen mit (`rename_hook`); überschreibt eine Umbenennung ein bestehendes Ziel, wird dessen Inhalt vorher als Version gesichert (`pre_renameOrCopy_hook` → `Storage::store`); Löschen legt Datei samt Versionen in den Papierkorb | an der Knoten-ID, jede Fassung eine Revision |
| Word/Excel-Speichermuster | keine Sonderbehandlung gefunden: das Original wandert mit seinen Versionen auf `~WRL….tmp` und von dort in den Papierkorb; `Bericht.docx` ist danach ein neuer Eintrag ohne Vorgeschichte (aus dem Code abgeleitet, nicht getestet) | Identitätsregel, getestet |
| Anmeldung | App-Passwörter empfohlen – laut Doku, weil das normale Passwort bei jedem Request aufwendig geprüft wird | API-Schlüssel, 60-s-Zwischenspeicher |
| Windows-Explorer | Doku: HTTPS, `BasicAuthLevel`, `FileSizeLimitInBytes` auf 4 GB anheben; freier Platz wird nicht angezeigt; empfohlen wird ausdrücklich der **Sync-Client** statt eines Netzlaufwerks | gleiche Client-Voraussetzungen (13) |

**Ergebnis:** Nextcloud ist beim Netzlaufwerk nicht weiter als das eigene Konzept – eher weniger: ohne Zusatz-App
nur vorgetäuschte Sperren für den Windows-Explorer, Versionen am Pfad, keine Behandlung der Office-Speichermuster,
Prüfsumme nur vom Client. Übernehmenswert: Sperren **gemeinsam** für Oberfläche, Office und WebDAV (wie `files_lock`,
bei uns `fm.dav.lock` mit `node_id`), und die Zurückhaltung beim Netzlaufwerk (Nextcloud empfiehlt dafür den
Sync-Client – ein Sync-Client ist hier nicht geplant, WebDAV bleibt der Weg für den Explorer).

### 19.14 Alternativen zu WebDAV für den Explorer-Zugriff (Recherche, 2026-09-26)

Nicht getestet, außer wo vermerkt. Maßstab: Odoo bleibt alleiniger Schreiber (I1), Rechte über Odoo (I7), möglichst
nichts auf den Windows-Rechnern einrichten.

**A. Anderes Protokoll auf dem Server**

| Weg | Befund | Bewertung |
|---|---|---|
| **SMB über Samba, dahinter ein Odoo-FUSE-Dateisystem** | Unraids eigene Bauweise: `/mnt/user` ist FUSE (`shfs`), Samba 4.23.2 gibt es frei (auf Tower geprüft). Übertragen: ein Python-FUSE-Dateisystem (`pyfuse3` 3.5.0 vom 06/2026 oder `mfusepy` 3.1.1, gepflegt) arbeitet mit Odoos ORM und Blob-Speicher; Samba gibt den Mount frei. | **eleganteste Alternative für die Clients:** normales Netzlaufwerk, keine Einrichtung auf Windows (kein HTTPS-Vertrauen, keine 50-MB-Grenze, kein WebClient), echte SMB-Sperren und Leases durch Samba, Explorer-Tempo. Offen und zu prüfen: Rechte je Nutzer (FUSE sieht die Unix-UID des `smbd`-Prozesses des Nutzers → Zuordnung Unix-Nutzer ↔ Odoo-Nutzer, Mount mit `allow_other`); Schreiben über beliebige Offsets muss bis zum Schließen gepuffert werden (jede geschlossene Datei = neue Revision; große, direkt bearbeitete Dateien wie `.pst`, `.accdb`, VM-Abbilder werden bei jedem Schließen ganz neu gespeichert); Samba fragt Metadaten sehr häufig ab (FUSE-Attribut-Cache + schnelle ORM-Auflösung nötig); FUSE im Container braucht `/dev/fuse`, `SYS_ADMIN` und Mount-Propagation zum Host, damit Samba auf dem Host den Mount sieht; Groß/Klein löst Samba (`case sensitive = no`). Die Identitätsregel greift unverändert (Office-Speichern kommt als `rename` an). |
| SFTP (paramiko/asyncssh-Server) | gepflegt; Vorbild Vertel `dms_sftp` (Odoo 18): Server-Thread im Odoo-Prozess, per **Cron** gestartet, Stopp durch Überschreiben von `server.stop`, Server-Schleife in einem langlebigen Cursor | Windows kann SFTP **nicht** als Laufwerk einbinden (nur mit WinSCP, SSHFS-Win/WinFsp o. Ä.) → kein Vorteil gegenüber WebDAV für den Explorer; Vertels Umsetzung mit den bekannten Kniffen |
| FTP (`pyftpdlib`) | gepflegt | im Explorer nur eingeschränkt, unverschlüsselt → nein |
| S3-API | – | kein Windows-Bordmittel, kein Umbenennen im Protokoll (Kopieren + Löschen) → Office-Speichermuster ungünstig → nein |
| NFS | Windows-Client nur in Pro/Enterprise, UID-Abbildung, eigenes Backend in C (Ganesha FSAL) | nein |
| SMB-Server in Python (`impacket`) | laut Projekt kein gehärteter Produktiv-Server | nein |

**B. Anderer Client auf Windows, Server bleibt `odoo fmdav`**

| Weg | Befund | Bewertung |
|---|---|---|
| **rclone mount + WinFsp** (frei) | Laufwerksbuchstabe oder Netzlaufwerk (`--network-mode`); mit `--vfs-cache-mode writes` laut Doku alle normalen Dateioperationen, auch Office; `--vfs-case-insensitive`; Anmeldung und Größen ohne Windows-WebClient-Grenzen | gute Ergänzung, wenn der Windows-WebClient stört; Preis: Installation auf jedem Rechner (als Dienst), Hochladen erst nach dem Schließen (Standard 5 s Verzögerung) → mehr Konfliktfenster bei gleichzeitiger Bearbeitung |
| RaiDrive, Mountain Duck | kommerziell | wie rclone, mit Oberfläche |
| Eigener Sync-Client über die Windows Cloud Files API (wie OneDrive "Dateien bei Bedarf") | beste Einbindung (Platzhalter, offline), aber eigener Windows-Client oder Nachbau der Nextcloud-Client-Schnittstelle | zu groß |

**C. Anderes Grundprinzip**
- **Schreibgeschützter SMB-Spiegel** (Option 11 B): Verzeichnisbaum aus Verknüpfungen in den Blob-Speicher (kein
  doppelter Platz), Samba gibt ihn nur lesend frei; Bearbeiten über Odoo oder "Lokal öffnen". Schnell und einfach,
  aber kein Schreiben im Explorer.

**Ergebnis:** Die einzige Alternative, die für die Clients **eleganter** wäre als WebDAV, ist **SMB über Samba mit
einem Odoo-FUSE-Dateisystem dahinter** – Unraids eigene Bauweise, auf Windows nichts einzurichten. Sie ist aber
unerprobt; die offenen Punkte (Rechte je Nutzer über UID-Zuordnung, Schreibpuffer bis zum Schließen, Metadaten-Tempo,
FUSE im Container mit Mount-Propagation, Samba-Freigabe auf dem Host) brauchen einen Prototyp. WebDAV (`odoo fmdav`)
bliebe auch dann sinnvoll für Zugriff ohne VPN und für "Lokal öffnen" aus dem Browser.

### 19.15 Samba + inotify (Prüfung, 2026-09-26)

Samba schreibt echte Dateien, ein Watcher (inotify) meldet Änderungen, Odoo zieht nach. Das ist das Prinzip des
**heutigen** `int_filemanager` und der Variante B aus dem DB-Vorrang-Konzept; die Messungen dazu stammen aus dessen
Abschnitten 19.3, 19.5 und 20.5 (Tower, Samba 4.23.2 über `shfs`, echte SMB-Zugriffe von Windows).

**Gemessenes Verhalten über SMB:**

| Vorgang | Ereignisse / Befund | lösbar? |
|---|---|---|
| Word-/Excel-/LibreOffice-Speichern | Temp schreiben, Original wegbenennen, Temp auf Originalnamen, Weggebenanntes löschen → neue Datei, neue Inode; heutiger Code verliert Zeile/Token | ja, mit Endzustandslogik (wie die Identitätsregel, aber nachträglich aus Ereignissen rekonstruiert) |
| Verschieben über vorhandenen Namen | Samba erzeugt `DELETE` des Ziels, dann `MOVED` | ja, dieselbe Logik |
| Ereignisverlust | heutiger Watcher: bei 20.000 Dateien per robocopy **17 % dauerhaft verloren**, Ordner im Rückstau ohne Watch; Prototyp mit `watchdog` + eigener Überlauferkennung: alle 20.000 erfasst, erzwungener Überlauf **zuverlässig erkannt** → Vollabgleich (Tower-Bestand: 211 s) | ja, mit Aufwand (Überlauf erkennen, Nachholabgleich, Watchdog) |
| Wer hat geändert? | inotify kennt keinen Benutzer | teilweise: Samba-Modul `full_audit` (auf Tower vorhanden) protokolliert jede Operation mit Benutzer |
| Löschen über SMB | auf der Freigabe endgültig | teilweise: Samba-Modul `recycle` (vorhanden) = Papierkorb auf der Freigabe |
| NFD-Namen (macOS) | Platte NFD, Index NFC → Datei per App nicht erreichbar | ja, Normalisierung |
| Identität über Mover-Umzug | Inode ändert sich bei gleichem Pfad (shfs) | ja, Pfad + Endzustand statt Inode |
| **Gleichzeitiges Schreiben Odoo ↔ SMB-Client** | Odoo ersetzt die Datei (`os.replace`), während ein Windows-Client sie offen hat: die weitere Schreibung des Clients ist **still verloren**, Samba-Sperren halten das nicht auf | **nein** – zwei Schreiber auf denselben Dateien |
| **Rechte** | SMB-Zugriff läuft nur über Samba-/Unix-Rechte je Freigabe, **nicht** über Odoos `ir.rule`/Rechte-Bereiche | **nein** (nur durch Nachbilden der Rechte als Datei-ACLs, zweite Rechteverwaltung) |
| **Versionen externer Änderungen** | Speichern "an Ort und Stelle" überschreibt den alten Inhalt; Odoo sieht nur den neuen | **nein**, außer jede Änderung wird sofort in einen eigenen Speicher kopiert (doppelter Platz und doppelte Schreiblast, Zwischenstände zwischen zwei Ereignissen bleiben verloren) |

**Einordnung gegen die Entscheidungen und Invarianten:** Samba + inotify macht Samba zum **zweiten Schreiber** der
Dateien. Das widerspricht der Entscheidung "Odoo ist alleiniger Schreiber" (2026-09-26) und den Invarianten I1 (nur
Odoo schreibt), I5 (nichts löschen/verpassen, weil etwas nicht beobachtet wurde – der Abgleich muss Lücken
schließen), I6 (jede Fassung wiederherstellbar) und I7 (Rechte nur über Odoo). Genau diese Befunde haben am
2026-09-26 zur Entscheidung für int_filemanager 2 geführt. Die lösbaren Punkte sind mit viel Aufwand lösbar
(Watcher-Absicherung, Nachholabgleich, Endzustandslogik, `full_audit`, `recycle`); die drei nicht lösbaren bleiben.

**Ergebnis:** Samba + inotify ist **keine** saubere Alternative. Wenn SMB gewünscht ist, erfüllt nur **Samba über
einem Odoo-FUSE-Dateisystem** (19.14) die Invarianten: dort schreibt Samba nicht auf die Platte, sondern durch
Odoos Code, Rechte werden je Aufruf geprüft, jede geschlossene Fassung wird Revision – und inotify wird überflüssig,
weil jede Änderung ohnehin durch Odoo läuft.

### 19.16 JSON-2 (Odoos empfohlene externe Schnittstelle) und WebDAV (Code-Prüfung, 2026-09-26)

**Befund im Odoo-19-Core:**
- `addons/rpc/controllers/json2.py`: `POST /json/2/<model>/<method>` mit `auth='bearer'` (API-Schlüssel),
  `type='json2'` (JSON-Körper mit benannten Argumenten, `ids`, `context`), `save_session=False`, lesender Cursor für
  Methoden mit `@api.readonly`; aufrufbar ist **jede öffentliche Methode** (`service/model.py:get_public_method`:
  nicht mit `_` beginnend, nicht `@api.private`, keine class-/staticmethod). Eine Transaktion je Aufruf.
- `addons/rpc/controllers/__init__.py`: `/xmlrpc`, `/xmlrpc/2` und `/jsonrpc` sind in Odoo 19 **veraltet, Entfernung
  geplant für Odoo 22**. Im Repo nutzt sie niemand (geprüft).
- API-Schlüssel (`base/models/res_users.py`): Prüfung `scope IS NULL OR scope = <angefragt>` – ein Schlüssel ohne
  Bereich gilt überall, ein Schlüssel mit Bereich nur dort. `auth='bearer'`/JSON-2 fragt Bereich `rpc` an.
  Nicht-Admins müssen ein Ablaufdatum setzen, höchstens `api_key_duration` ihrer Gruppen (Standard 1 Tag);
  dauerhafte Schlüssel nur als Admin/sudo. Doku empfiehlt zusätzlich die Header `X-Odoo-Database` und `User-Agent`.

**Bezug zu WebDAV:**

| Bauform | Rolle von JSON-2 |
|---|---|
| `odoo fmdav` (gewählt, 11.2) | WebDAV spricht **nicht** per HTTP mit Odoo, sondern nutzt das ORM direkt – JSON-2 ist dafür nicht nötig. Die Anmeldung nutzt **denselben** Schlüssel-Mechanismus wie JSON-2; mit eigenem Bereich `int_filemanager.dav` (statt `rpc` wie im Prototyp) gelten Laufwerks-Schlüssel nicht für JSON-2 (geringste Rechte). |
| separater Dienst (19.4, verworfen) | Nach Odoos Empfehlung müsste ein externer Dienst JSON-2 statt eigener JSON-RPC-Routen benutzen. Datei-**Inhalte** gingen trotzdem nicht darüber: JSON-2 nimmt nur JSON, Binärdaten nur base64 im Speicher (I12) – eigene Upload-Routen blieben nötig. Bestätigt die Wahl von `odoo fmdav`. |

**Folgen für int_filemanager 2 (eingearbeitet in 11.2 und 12):**
1. **Jede öffentliche Methode von `int_filemanager.*` ist per JSON-2 erreichbar** – öffentlich nur, was mit
   beliebigen Argumenten sicher ist; sonst `_…`/`@api.private`; lesende mit `@api.readonly`. Das verallgemeinert die
   Lehre aus N1.
2. **WebDAV-Anmeldung mit eigenem Bereich** `int_filemanager.dav`; Oberfläche zum Erzeugen eines Laufwerks-Schlüssels
   und die Schlüssel-Laufzeit (`api_key_duration`) erst, wenn ein Netzlaufwerk kommt (17.7).
3. **Automatisierung von außen** (Skripte, spätere Werkzeuge) über JSON-2 für Metadaten (suchen, verschieben,
   taggen); Datei-Inhalte über die eigenen Upload-/Download-Routen mit API-Schlüssel (7, 8), nie base64 über JSON-2.
4. Externe Aufrufer senden `X-Odoo-Database` (spart die Datenbank-Ermittlung je Aufruf, 19.6) und einen `User-Agent`.

### 19.17 Code-Prüfung und Nachtests (2026-09-26/27)

Vollständige Prüfung dieses Konzepts gegen Odoo 19.0-20260817 und den aktuellen 19.0-Stand auf GitHub:
`docs/review/konzept_codepruefung_2026-09-26.md` (194 Behauptungen, 21 Befunde A1–A21; eingearbeitet in 2–6, 8,
10–14, 16, 18). Neue Tests nur auf dem Test-PostgreSQL `fmtest_pg` und auf temporären Test-Shares (danach entfernt):

| Test | Ergebnis |
|---|---|
| Namensindex mit leerem Elternteil | ohne `NULLS NOT DISTINCT` zwei Wurzeln `Daten`/`daten` angelegt, mit abgelehnt (A6) |
| NFD gegen NFC | `lower(NFD) ≠ lower(NFC)` → Normalisierung beim Anlegen nötig |
| Namens- und Präfixsuche | Index-Nutzung mit demselben Ausdruck bzw. mit C-Kollation bestätigt (`EXPLAIN`) |
| gleicher neuer Name in zwei Transaktionen (REPEATABLE READ) | `UniqueViolation`, auch mit Snapshot vor dem Commit des anderen → `retrying()` wiederholt nicht (A3) |
| `SET LOCAL lock_timeout` + `FOR UPDATE` gegen eine gehaltene Sperre | `55P03 lock_not_available` → `retrying()` wiederholt |
| `UPDATE` einer Zeile, die ein anderer löscht und committet (REPEATABLE READ) | `40001 could not serialize access due to concurrent delete` → `retrying()` wiederholt; Grundlage der `last_used`-Regel (5) |
| `fsync` 20 × 4 KiB auf dem Array | Median 33 ms, ein Ausreißer 7,3 s (Anlaufen nach Spindown, `spindownDelay=30`) (A13) |
| `_parent_store_update` ab Odoo-Commit `9b1872b179` (2026-09-08, "match parent_store descendants by range instead of LIKE": `child.parent_path >= node.parent_path AND < left(node.parent_path, -1) \|\| '0'`) | unter `C` korrekt; unter `en_US.utf8` fehlen echte Nachfahren (`1/2/5/`), ein fremder Pfad (`12/`) wird erfasst → Teilbäume würden beim Verschieben beschädigt. Belegt damit Abschnitt 4 (C-Kollation) und 13 (HM-SRV vor dem Image-Update umstellen). Tower-Live-DB `odoo`: Collate `C`. Im Test-Image 20260908 noch nicht enthalten |
| Test-Image `odoo:19.0-hm-test` (2026-09-27) | 19.0-20260908; enthält den Sicherheits-Fix `97e3d6152d` (A5); OCR-Bibliotheken laden; `pip check`: `maxminddb` verlangt neueres `setuptools` (aus der pip-Schicht des Dockerfiles, unkritisch) |
| `link`/`rename` über Plattengrenzen (temporärer Share über disk2 + disk3) | beide funktionieren; shfs legt den fehlenden Zielordner auf der Platte der Datei an; `link`/`O_EXCL` auf einen Namen, der auf der anderen Platte existiert → `EEXIST` (I2 hält) |

Belege im Code: Odoo-Cursor mit REPEATABLE READ (`sql_db.py`, `set_isolation_level`), wiederholte Fehlerklassen
(`service/model.py`, `PG_CONCURRENCY_EXCEPTIONS_TO_RETRY`, `retrying`), `LockError(UserError)` (`exceptions.py`),
`lock_for_update` mit `SKIP LOCKED` (`orm/models.py`). Außerdem gefunden: Das Tower-Image hat einen späteren
Sicherheits-Fix des 19.0-Zweigs noch nicht (A5); `onlyoffice_odoo` verwirft das Ergebnis seiner Rechteprüfung im
Callback (A14).
