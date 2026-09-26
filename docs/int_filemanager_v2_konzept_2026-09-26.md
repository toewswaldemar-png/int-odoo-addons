# int_filemanager 2: Odoo als alleiniger Schreiber

Stand 2026-09-26. **Konzept, nichts umgesetzt. Vor der Freigabe durch den Nutzer wird kein Code geschrieben.**

**Entscheidungen des Nutzers (2026-09-26):**
1. Der Dateimanager wird **vollständig als Odoo-Addon** gebaut. Odoo-Bausteine werden genutzt; **selbst gebaut wird
   nur dort, wo Odoo nachweislich an Grenzen stößt.**
2. **Odoo ist alleiniger Schreiber** der Dateiinhalte.
3. Der Bestand wird **kopiert**, nicht per Hardlink übernommen.

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
"Odoo als alleiniger Schreiber" unvereinbar. Explorer-Zugriff ist über Odoo möglich (Abschnitt 11).

## 2. Invarianten

Grundregeln, die **immer** gelten, unabhängig von Funktion, Fehlerfall, Absturz oder Last. Jede neue Funktion und
jede Änderung wird dagegen geprüft; jede Invariante hat Tests (Abschnitt 16).

| # | Invariante | verhindert (Befund) |
|---|---|---|
| I1 | **Nur Odoo schreibt in den Blob-Speicher.** Kein Mount, keine Freigabe mit Schreibrecht, kein anderes Programm. | Überlauf, Identitätsverlust Word/Excel, Geisterzeilen, NFD, P10 |
| I2 | **Ein Blob wird nie verändert.** Neuer Inhalt = neuer Blob; der Name ist der SHA-256 des Inhalts. | stilles Überschreiben, falsche ETags |
| I3 | **Erst die DB, dann die Wirkung nach außen.** Vor dem Commit werden nur Blobs angelegt (harmlos bei Abbruch); alles andere Externe (E-Mail, Umwandler, WebDAV-Antworten mit Folgen) erst danach. | B2 |
| I4 | **Bytes werden nie vor ihrer DB-Zeile gelöscht**, nur durch den Aufräumjob, wenn kein Verweis mehr existiert. | B14 |
| I5 | **Nichts wird gelöscht, weil etwas nicht beobachtet wurde.** Es gibt keinen Watcher und keinen Scan, der Zeilen entfernt. | B1, B13 |
| I6 | **Jede bestätigte Änderung ist wiederherstellbar.** Jede ersetzte Fassung bleibt als Version erhalten (Aufbewahrung konfigurierbar, Löschen nur per Regel). | B5, B6 |
| I7 | **Rechte werden ausschließlich über Odoos Rechtesystem geprüft** (`ir.model.access`, `ir.rule`). Öffentliche Methoden arbeiten nie mit `sudo()` auf nutzergesteuerten Eingaben. | N1 |
| I8 | **Verweise gehen über IDs, nie über Pfade.** Pfade sind abgeleitete Anzeige. | B7 |
| I9 | **Jeder Schreibvorgang ist eine Transaktion** und entweder ganz oder gar nicht sichtbar. Wiederholungen (`retrying`, Doppelklick, erneutes Senden) erzeugen keine Doppelungen (Vorgangs-ID). | B2, P3 |
| I10 | **Der Odoo-Core wird nicht verändert oder gepatcht.** Erweiterung nur über dokumentierte Mechanismen (Vererbung, Hooks, Routen). | Update-Brüche |
| I11 | **Native Bibliotheken für fremde Dateiformate laufen außerhalb des Odoo-Prozesses.** | Abstürze und Speicherfresser im Odoo-Prozess, Pillow-Beschränkung |
| I12 | **Keine Dateibytes im RAM des Odoo-Prozesses** über eine feste Grenze hinaus; Übertragung per Streaming und `x_sendfile`. | 128-MiB-Grenze, RAM |

## 3. Architektur

```text
 Browser / Explorer (WebDAV) / ONLYOFFICE
        │
        ▼
 nginx ── X-Accel (Auslieferung der Blobs direkt von der Platte)
        │
        ▼
 Odoo (workers>0 möglich, da kein Watcher)
 ├─ Oberfläche (OWL, aus int_filemanager weiterentwickelt)
 ├─ Modelle: fm.node, fm.revision, fm.blob, fm.scope, fm.upload, Tags, Status, OCR-Werte
 ├─ Routen: Upload (Stücke), Download (Stream), WebDAV, ONLYOFFICE-Callback
 ├─ Crons: Vorschau/OCR anstoßen, Aufräumen (Autovacuum), Uploads verwerfen
 └─ Rechte: ir.model.access + ir.rule (Rechte-Bereiche)
        │                               │
        ▼                               ▼
 PostgreSQL (C-Kollation)        Blob-Speicher (Array-Share, nur Odoo schreibt)
                                        ▲
 Umwandler-Container (vips, ffmpeg, LibreOffice, Pillow voll, OCR) ── liest Blobs, liefert PNG/JPEG/Text an Odoo
```

## 4. Datenmodell

| Modell | Zweck | Wesentliche Felder / Regeln |
|---|---|---|
| `fm.node` | Ordner und Dateien (Verzeichniseintrag) | `name`, `parent_id` (`_parent_store`), `is_dir`, `active`, `removal_reason` (`trash`), `scope_id`, `current_revision_id`, `size`, `mime`, `tag_ids`, `status_id`, `partner_id`, `mail.thread`. **Teil-Unique-Index** `(parent_id, name) WHERE active` über `models.UniqueIndex` (Name je Ordner eindeutig, Papierkorb blockiert nicht). Pfad nur berechnet/zur Anzeige. |
| `fm.revision` | eine Fassung einer Datei | `node_id`, `revision_no`, `blob_id`, `size`, `origin` (`upload`, `webdav`, `office`, `edit`, `restore`, `import`), `create_uid`, `create_date`, `operation_id`. Nie verändert. |
| `fm.blob` | Inhalt | `sha256` (eindeutig), `size`, `state` (`present`). Speicherort aus dem Hash abgeleitet, nicht gespeichert. |
| `fm.scope` | Rechte-Bereich | `name`, `read_group_ids`, `write_group_ids`, `manage_group_ids`, `purge_group_ids`. Knoten erben den Bereich des nächsten Ordners mit eigenem Bereich (gespeichert, beim Verschieben per ORM für den Teilbaum gesetzt). |
| `fm.upload` | laufender Upload in Stücken | `operation_id` (eindeutig), `create_uid`, Zielordner/-datei, erwartete Größe, bisherige Größe, Temp-Datei, Ablauf. |
| `fm.operation` | Vorgangs-IDs | `key` (eindeutig), Ergebnis. Doppelte Anfragen liefern das gespeicherte Ergebnis. |
| bestehend | Tags, Status, Extraktionsmuster, extrahierte Werte, Freigabe-Log | werden auf `fm.node` umgehängt. |
| Geschäftsbezug | Mixin für Geschäftsobjekte | heute `int_filemanager.linkable.mixin` fest auf `partner_id`. Künftig generisch (`res_model`/`res_id`-Verknüpfungen mit Rechteprüfung nach dem Muster von `mail.activity`: `_check_access` **und** `_search` überschreiben, `exists()` vor der Prüfung, Aufräumjob für per DB-Kaskade gelöschte Ziele). |

**Datenbank:** C-Kollation (Odoo-Standard, `service/db.py:146`). Präfix- und Teilbaum-Abfragen nutzen dann die
normalen Indizes, und `_parent_store_update` des neueren Cores ist korrekt (auf `en_US.utf8` zerstört er
Teilbäume, belegt in 19.2). Namens-Sortierung wie im Explorer über den Hook `_order_field_to_sql` + ICU-Kollation
+ passenden Index (DB-Vorrang-Konzept 15.5). Namenssuche mit Trigram-Index (185 statt 37 Anfragen/s, 20.3).
Unicode-Namen werden beim Anlegen einheitlich nach NFC normalisiert (es gibt keine Fremdschreiber mehr, die NFD
liefern könnten).

## 5. Blob-Speicher (Eigenbau, weil `ir.attachment` hier nicht reicht)

**Warum eigen:** `ir.attachment` nimmt Inhalte nur als Bytes im Speicher (`_set_attachment_data`,
`ir_attachment.py:284-313`), und `store_fname` ist nicht setzbar (`create`/`write` entfernen es, Z. 723, 762). Große
Dateien und Streaming sind damit nicht möglich. `ir.attachment` bleibt für Vorschaubilder und Anhänge an
Geschäftsdatensätzen.

**Aufbau:** Nachbildung des Filestore-Musters, erweitert um Streaming.
- **Ablage:** `<blobroot>/<sha[0:2]>/<sha[2:4]>/<sha>`. `<blobroot>` liegt auf einem **Array-Share** (Platz) und wird im
  Container **unterhalb von `<data_dir>/filestore/<db>/`** eingebunden. Nur so gilt Odoos `x_sendfile`-Pfadprüfung
  (`http.py:665-680`, prüft "unterhalb von `data_dir/filestore`"). Samba gibt diesen Share nicht frei (I1).
- **Schreiben (vor dem Commit):** Stream in Temp-Datei im selben Dateisystem, SHA-256 beim Schreiben, `fsync`,
  existiert der Ziel-Hash schon → Temp löschen (Deduplizierung), sonst `link`/`rename` ohne Überschreiben auf den
  Hash-Namen, `fsync` des Ordners. Erst danach die DB-Zeilen (`fm.blob`, `fm.revision`) in der Request-Transaktion.
  Ein Abbruch hinterlässt höchstens einen unreferenzierten Blob, den der Aufräumjob entfernt.
- **Aufräumen:** `@api.autovacuum`: Blobs ohne Verweis aus `fm.revision` (und ohne laufende Uploads) älter als eine
  Schonfrist löschen. Wie Odoos `_gc_file_store` (`ir_attachment.py:191-263`) unter einer Tabellensperre als erstem
  Statement einer frischen Transaktion, damit kein gerade committeter Verweis übersehen wird (Snapshot-Befund 3).
- **Lesen:** `http.Stream(type='path')` mit `etag=sha256`, Range-Anfragen (`send_file` mit `accept_ranges`,
  `http.py:653-680`), Auslieferung über nginx per `X-Accel-Redirect`.
- **Prüfen:** periodischer Hash-Abgleich in Stichproben (Bitfäule, Plattenfehler) als Cron mit Zeitbudget.
- **Backup:** DB und Blob-Speicher gehören zusammen. Weil Blobs unveränderlich sind, reicht für den Blob-Speicher ein
  inkrementelles Backup; wiederhergestellt wird immer DB-Stand plus alle Blobs, die dieser Stand referenziert.

## 6. Schreibwege

Alle Schreibwege folgen demselben Ablauf: Rechte prüfen → Vorgangs-ID prüfen → ggf. Blob anlegen (Abschnitt 5) →
Zeilen sperren (`lock_for_update`) und Basisrevision prüfen → DB schreiben → Commit. Keine Plattenoperation
außer "Blob anlegen", kein `sudo` auf Nutzereingaben.

| Vorgang | Ablauf | Bemerkung |
|---|---|---|
| Hochladen (neu) | Upload in Stücken (7) → Blob → `fm.node` + `fm.revision` | Name kollidiert → Fehlermeldung oder Nutzerwahl "ersetzen/umbenennen" |
| Neue Fassung (Upload, Bearbeiten, ONLYOFFICE, WebDAV-PUT) | Blob → neue `fm.revision`, `current_revision_id` umhängen | **Basisrevision** mitgeben; weicht sie ab → Konflikt statt stillem Überschreiben; alte Fassung bleibt (I6) |
| Umbenennen, Verschieben | reines `write` auf `fm.node`; beim Verschieben in anderen Rechte-Bereich `scope_id` des Teilbaums im selben Commit | keine Plattenoperation, deshalb kein B2/B7 |
| Löschen | `active=False`, `removal_reason='trash'` (Teilbaum) | Papierkorb-Ansicht filtert auf den Grund |
| Wiederherstellen | `active=True`; Namenskollision im Zielordner → Fehlermeldung | |
| Endgültig löschen | Zeilen löschen; Blobs später per Aufräumjob | I4 |
| Kopieren | neuer Knoten, neue Revision auf **denselben** Blob | kein Kopieren von Bytes |
| Version wiederherstellen | neue Revision auf den alten Blob | keine Bytes kopiert |
| Text bearbeiten | wie "neue Fassung" | heute `write_text` nicht atomar (B6) |

**Wiederholungssicherheit:** Da vor dem Commit nur Blobs angelegt werden (idempotent über den Hash), kann Odoos
`retrying()` jeden Request gefahrlos wiederholen. Upload-Körper, die nicht in `request.httprequest.files` liegen
(WebDAV-PUT), werden je Vorgangs-ID in eine Temp-Datei gestreamt und bei einer Wiederholung wiederverwendet
(DB-Vorrang-Konzept 4.4).

## 7. Upload in Stücken (Eigenbau, weil Odoo 128 MiB je Request und Bytes im RAM hat)

- Route mit eigenem `max_content_length` pro Stück (z. B. 16 MiB), Streaming direkt in die Temp-Datei.
- Ablauf: `init` (Vorgangs-ID, Größe, Ziel) → `chunk` (Offset, idempotent) → `finish` (Hash prüfen, Blob anlegen,
  Knoten/Revision in einer Transaktion). Abgebrochene Uploads können fortgesetzt werden.
- Verwaiste Uploads räumt ein Cron nach Ablauf auf.
- Das Frontend teilt Dateien in Stücke; bestehende Upload-Oberfläche wird angepasst.

## 8. Lesen, Vorschau, Medien

- **Download und Video:** Stream mit Range und `x_sendfile` (5). Rechteprüfung über das ORM vor der Auslieferung.
- **Vorschaubilder:** `fields.Image` am Knoten bzw. an der Revision (Größen nach dem `image.mixin`-Muster), Auslieferung
  über `/web/image` (Rechte greifen nativ, geprüft in 19.2).
- **Umwandler als eigener Container (I11):** kleiner HTTP-Dienst ohne Internetzugang, liest Blobs schreibgeschützt und
  liefert PNG/JPEG bzw. Text zurück. Werkzeuge: Pillow mit allen Plugins (WebP, AVIF, TIFF), vips, libheif, libraw,
  ffmpeg (Standbild), Ghostscript (PDF), LibreOffice (Office → PDF → Bild). Odoos eigene Pillow-Beschränkung
  (`tools/image.py:26-28`) bleibt unberührt.
- **Auslösung:** Cron in Batches mit Zeitbudget, gebunden an die **Revision** (veraltete Ergebnisse werden verworfen),
  Zeit- und Größenlimits je Format, Fehlerzustand sichtbar.
- **Nachholen im Bestand:** gedrosselt über Tage (209.429 Bilder auf Tower, 20.3).

## 9. Suche, OCR, Geschäftsbezug

- Namenssuche mit Trigram-Index; Volltext über den Text aus dem Umwandler bzw. `attachment_indexation`-Logik.
- OCR und Werterkennung aus `int_filemanager` bleiben fachlich gleich, laufen aber als Batch über den Umwandler.
- Die heutigen öffentlichen Methoden `action_analyze_document`/`action_apply_extracted_values` (N1) werden privat
  und prüfen Rechte selbst.
- Geschäftsbezug generisch über das Verknüpfungs-Mixin (4), Smart-Button und Dateiliste am Datensatz.

## 10. Office

- **ONLYOFFICE im Browser:** Callback-Route speichert als neue Revision mit **Basisrevisionsprüfung** über den
  Dokument-Key (heute fehlt die Prüfung, 13.1). Editor-Sitzung an Knoten-ID + Revision gebunden (I8).
- **"Lokal öffnen" (Word/Excel):** WebDAV für eine einzelne Datei; Tokens in der DB (heute nur im Speicher, nach
  Neustart ungültig), an Knoten-ID gebunden; `PUT` = neue Revision mit Sperrprüfung; ETag = SHA-256.

## 11. Explorer-Zugriff (offene Entscheidung nach Prototyp)

| Option | Beschreibung | Folgen |
|---|---|---|
| **A. WebDAV-Netzlaufwerk über Odoo** | Odoo stellt ganze Ordner per WebDAV bereit, der Explorer liest und schreibt **über Odoo** (I1 bleibt erfüllt) | größter Eigenbau: WebDAV-Methoden (`PROPFIND`, `GET`, `PUT`, `MKCOL`, `MOVE`, `COPY`, `DELETE`, `LOCK`/`UNLOCK`), Regeln für die Speicherabläufe von Word/Excel/LibreOffice ("Ersetzen durch Umbenennen behält die Identität"), Eigenheiten des Windows-WebDAV-Clients (HTTPS nötig, Größenlimit per Registry, nicht am Code geprüft) |
| **B. Schreibgeschützter Spiegel** | Odoo veröffentlicht einen lesbaren Ordnerbaum auf einem Share, den Samba nur lesend freigibt; Bearbeiten über "Lokal öffnen" | Speicher doppelt oder Spiegel als Verknüpfungen; eine Veröffentlichungsschicht (Muster des Durchstichs); keine Fremdschreiber |
| **C. Kein Explorer-Zugriff** | Arbeit nur in der Odoo-Oberfläche | kein Eigenbau |

**Vor der Entscheidung:** Prototyp A auf Tower (Explorer, Word, Excel, LibreOffice als Netzlaufwerk; Identität,
Sperren, Größen, Tempo).

## 12. Rechte

- Rechte-Bereiche (`fm.scope`) statt Pfad-Präfix-Regeln. Regel-Domains nur über indizierte Felder
  (`[('scope_id.read_group_ids', 'in', user.all_group_ids.ids)]`), damit keine Vollscans entstehen (heute 269 ms
  für Nicht-Admins, 19.2).
- Unterordner mit engeren Rechten bekommen einen eigenen Bereich (Odoo-Regeln erlauben nur, sie verbieten nicht).
- Beim Ändern von Bereichen `registry.clear_cache()` (Regel-Cache, 19.2).
- Revisionen, Vorschauen, OCR-Werte erben die Rechte des Knotens (keine eigenen Regelsätze).
- Freigabe-Links für Externe: eigene Tokens mit Ablauf und Log (bestehend), Auslieferung über dieselbe Stream-Route.
- Kundenportal über `portal`.

## 13. Betrieb

- `workers>0` (Prefork) möglich, weil es keinen Watcher mehr gibt; große Downloads über nginx (`x_sendfile`).
- Cron-Datensätze mit `noupdate="1"` (sonst schaltet ein Modul-Update sie wieder ein, N6).
- Modul-eigene `data/neutralize.sql` (Crons, externe Dienste); Testkopien nur neutralisiert.
- **HM-SRV:** DB vor jedem Image-Update auf C-Kollation umstellen (19.2).
- Überwachung: Upload-Reste, fehlerhafte Vorschauen, Hash-Prüffehler, Platz im Blob-Speicher.

## 14. Migration (Kopie)

**Umfang:** der bisherige Share (Tower: `Daten`, ca. 1,8 TB, 429.184 Einträge, 29.316 Ordner). Etwa 7 % sind
doppelte Inhalte (98 GB gemessen) und werden nur einmal gespeichert. Platzbedarf ca. 1,65–1,7 TB; auf dem Array
von Tower sind ca. 3,7 TB frei.

**Ablauf:**
1. **Erstkopie im laufenden Betrieb:** Importwerkzeug (Odoo-Cron oder CLI) liest den alten Share, schreibt Blobs
   (Hash beim Kopieren), legt Knoten und Revision `origin='import'` an. Wiederholbar, fortsetzbar, in Batches.
2. **Metadaten übernehmen:** Tags, Status, Partner-Verknüpfungen, OCR-Werte, Freigabe-Tokens aus
   `int_filemanager.file` (über den alten Pfad zugeordnet); bisherige Versionen aus `int_filemanager.version`
   als ältere Revisionen; Schutzordner → Rechte-Bereiche.
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
- **Rechte:** Nicht-Admins, Portal-Nutzer und anonyme Freigaben gegen **alle** Zugriffswege: Listen, Suche,
  Gruppierung, `/web/image`, Download-Route, RPC (`call_kw`) auf jede öffentliche Methode, WebDAV.
- **Gleichzeitigkeit:** zwei Saves derselben Basisrevision, Doppelklick, Timeout nach Commit, Verschieben gegen Save.
- **Migration:** Probelauf auf der Testinstanz mit Teilbestand und Vollbestand (Kopie der Live-DB wie in 19.1),
  Zählung und Hash-Abgleich.
- **Last:** wie 20.3 (Baum, Liste, Suche, Download) mit 1–20 Nutzern, zusätzlich Uploads in Stücken.
- **Update-Absicherung:** Tests für die genutzten halb-internen Odoo-Stellen (`_check_access`/`_search`-Muster,
  `x_sendfile`-Pfad, Routen); ein Image-Update erst nach grünem Testlauf auf der Testinstanz.

## 17. Offene Entscheidungen

1. **Explorer-Zugriff:** A, B oder C (nach Prototyp).
2. **Umfang:** der ganze Share, oder bestimmte Bereiche (z. B. Fotos, Musik) außerhalb lassen?
3. **Versionsaufbewahrung:** unbegrenzt oder Regeln (Anzahl, Alter, Größe)?
4. **Papierkorb-Frist** (heute 30 Tage).
5. **Rechte-Bereiche:** Welche Bereiche und Gruppen gibt es anfangs?
6. **HM-SRV:** gleicher Weg wie Tower, und wann?

## 18. Reihenfolge

1. **Prototypen auf Tower** (Testinstanz): WebDAV-Netzlaufwerk (11 A); Blob-Speicher mit `x_sendfile` und Upload in
   Stücken; Messung der Kopierrate.
2. **Konzept festschreiben** nach den Prototypen, Entscheidungen aus 17 einarbeiten, Freigabe.
3. **Fundament:** Modelle, Blob-Speicher, Schreibwege, Rechte, Tests je Invariante.
4. **Oberfläche** auf das neue Modell umstellen.
5. **Vorschau/OCR** über den Umwandler.
6. **Office** (ONLYOFFICE, "Lokal öffnen").
7. **Explorer-Zugriff** nach Entscheidung.
8. **Migration:** Probelauf, dann Umstellung Tower; danach HM-SRV.

---

## 19. Prototyp-Ergebnisse (Tower, 2026-09-26)

**Aufbau:** Testmodul `fm_proto` (nur auf Tower, nicht im Repo) mit `fm.blob`/`fm.node`/`fm.revision`/`fm.upload`,
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
- **Kein Zugriff auf den rohen Request-Strom.** Odoos `HTTPRequest` reicht `stream` nicht durch (`HTTPREQUEST_ATTRIBUTES`,
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
