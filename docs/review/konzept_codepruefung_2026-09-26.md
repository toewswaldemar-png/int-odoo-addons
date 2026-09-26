# Code-Prüfung des Gesamtkonzepts int_filemanager 2 (2026-09-26)

Geprüft: `docs/int_filemanager_v2_konzept_2026-09-26.md` (alle Abschnitte 1–19, 1.090 Zeilen), gegen Kern und
Prototyp-Code. **Keine Dokumente geändert**; dies ist nur der Prüfbericht.

**Grundlage der Prüfung**
- Odoo-Code: Live-Container `odoo` auf Tower, **nur lesend** (`grep`/`sed`), Version `odoo.release` = **19.0-20260817**.
- Abgleich mit GitHub `odoo/odoo` Zweig **19.0** (Stand 2026-09-26) für alle 28 zitierten Core-Dateien (Abschnitt C).
- Zeilennummern neu ermittelt (Image-Stand); Abschnitt 19 nicht als Beweis übernommen.
- Empirisch nur auf der Testumgebung: PostgreSQL `fmtest_pg` (DB `fmv2`, nur **TEMP-Tabellen** bzw. eine sofort
  gelöschte Hilfstabelle `zz_race`), Test-Share `fmv2blobs` (Testdateien danach gelöscht). Die Test-Odoo-Instanz
  (`fmv2_*`) ist gestoppt und wurde nicht gestartet; Live-DB und Live-Share nicht angefasst.
- Externe Stände: PyPI-JSON, GitHub-API (OCA, Vertel, Nextcloud, odoo/documentation), lokales Cloudreve-Repo.

**Urteile:** bestätigt · widerlegt · ungenau (im Kern richtig, aber unvollständig/falsch begründet/falsche Stelle) ·
nicht prüfbar (mit Grund). "nicht erneut" = Messung aus Abschnitt 19, ohne erneuten Lauf nicht prüfbar.

---

## A. Lücken und Widersprüche, nach Schwere

| # | Schwere | Befund | Beleg | Folge fürs Konzept |
|---|---|---|---|---|
| A1 | **hoch** | **Neben-Modelle haben ohne eigene Regeln keine Knoten-Rechte.** Konzept 12: "Revisionen, Vorschauen, OCR-Werte erben die Rechte des Knotens (keine eigenen Regelsätze)". `ir.rule` wirkt je Modell; übernommen werden nur Regeln von `_inherits`-Eltern. Ohne eigene Regeln sind `int_filemanager.revision`/`.blob`/`.upload`/`.operation` für jeden mit Lese-ACL vollständig lesbar (`search_read` per `call_kw`/JSON-2). | `base/models/ir_rule.py:141-173` (`_compute_domain`, nur `model._inherits` :146-150) | Für jedes Neben-Modell entweder eigene Regel über den Knoten (`[('node_id.scope_id.read_group_ids','in',…)]`) oder **keine** ACL für Nutzer und Zugriff nur über geprüfte Methoden; in den Rechte-Tests alle Modelle abdecken |
| A2 | **hoch** | **Öffentliche Methoden sind nicht nur über JSON-2 erreichbar**, sondern für **jeden angemeldeten Nutzer** über `/web/dataset/call_kw` (Sitzung, kein API-Schlüssel), mit derselben Freigaberegel. Konzept 12/19.16 nennt nur JSON-2. | `web/controllers/dataset.py:29` (`auth="user"`) → `service/model.py:74-80` → `get_public_method` :45-70; `rpc` ist Standard-Server-Modul `tools/config.py:30` | Konzept 12 und Kern 7 erweitern: Angriffsfläche = alle öffentlichen Methoden für jeden internen Nutzer |
| A3 | **hoch** | **`retrying()` wiederholt Namens- und Sperrkonflikte nicht.** `IntegrityError` (auch `UniqueViolation`) → sofort `ValidationError`; `lock_for_update()` wartet nicht (`SKIP LOCKED`) und wirft `LockError`, eine `UserError` → wird gar nicht gefangen. Empirisch: gleichzeitiges Anlegen desselben Namens endet unter REPEATABLE READ als `UniqueViolation` (auch wenn der Snapshot vor dem Commit des anderen lag). Damit sind Konzept 6 ("`retrying()` kann jeden Schreibvorgang gefahrlos wiederholen", "Zeilen sperren (`lock_for_update`)"), 19.8 #7 ("Unique-Index + Retry") und 19.10 ("10 gleichzeitige PUT → 1 Knoten, 10 Revisionen") nicht belastbar; der Test hat den Wettlauf offenbar zeitlich nicht getroffen. | `service/model.py:192-214`; `orm/models.py:5564-5589`; `exceptions.py:109` (`LockError(UserError)`); Test `zz_race` auf `fmtest_pg` (PG 16.15) | Wettläufe explizit behandeln: Anlegen per Savepoint + `UniqueViolation` → vorhandenen Knoten nehmen (wie `fm.blob._get_or_create`), Sperren wartend (`SELECT … FOR UPDATE` ohne `SKIP LOCKED`, oder `pg_advisory_xact_lock` je Elternordner) oder `LockError` → 409/erneut versuchen; Parallelitätstests mit erzwungener Überlappung (Barriere/Fehlerinjektion) statt "gleichzeitig starten" |
| A4 | **hoch** | **Aufräumjob-Wettlauf beim Wiederverwenden eines Blobs.** Prototyp: `mark_for_gc` öffnet die Markierung mit `"ab"` – ändert die mtime einer vorhandenen Markierung nicht. Ist eine alte Markierung da (Blob-Zeile im letzten Lauf gelöscht), findet ein Schreiber die Datei (Deduplizierung, Temp gelöscht), der nächste Lauf löscht sie, bevor der Schreiber seine Zeile committet → Verweis ins Leere. Odoo hat dieselbe Lücke (`_file_write` markiert nur beim Neuschreiben), toleriert sie aber (täglicher Lauf, Bytes-API). | `fm_proto/blobstore.py:53-86`, `fm_proto/models.py:36-75`; `base/models/ir_attachment.py:158-168, 191-252` | Markierung bei jeder Wiederverwendung erneuern (`os.utime`), Temp-Datei bis nach dem Commit behalten und im Abschluss nach Sperre der Blob-Zeile prüfen, ob die Datei existiert (sonst neu verlinken); Test "Aufräumjob gegen Wiederverwendung" |
| A5 | mittel | **Image veraltet:** Tower läuft 19.0-20260817; im aktuellen 19.0 ist u. a. ein **Sicherheits-Fix** dazugekommen: `create`/`write` prüfen jetzt Zugriffsrechte bei Relations-Befehlen (`DELETE`/`UPDATE`/`LINK`) auf dem Zielmodell. | GitHub 19.0 `odoo/orm/models.py` +1331-1343 (fehlt im Image); `res_users.py` +1588 (Ablaufdatum in der Vergangenheit) | Vor Schritt 3 Image aktualisieren (`docker build --pull`), Tests gegen den aktuellen Stand |
| A6 | mittel | **Gleichnamige Wurzelknoten möglich:** Im Teil-Unique-Index gelten NULL-Eltern als verschieden. | Test `n1`: zwei Wurzeln `Daten`/`daten` angelegt; mit `NULLS NOT DISTINCT` (PG ≥ 15, Tower 16.15) abgelehnt; `UniqueIndex` nimmt freie Definition (`orm/table_objects.py:125-205`) | Index mit `NULLS NOT DISTINCT` oder genau ein Wurzelknoten |
| A7 | mittel | **Leere Datei doppelt abgebildet:** Konzept 4/6/19.4: leere Datei = Knoten ohne Revision; Prototyp legt beim Kürzen auf 0 Byte einen leeren Blob an (`ensure_empty_blob`). Der Grund (leerer `PUT` des Explorers) besteht erst mit WebDAV. | `fm_proto/blobstore.py:15, 101-110`; `dav_server.py:314` | Einheitlich 0-Byte-Blob; WebDAV-Sonderfall später in der WebDAV-Schicht |
| A8 | mittel | **Eingangsordner: "nicht mehr geöffnet" ist aus dem Odoo-Container nicht feststellbar** – offene Samba-Handles kennt nur der Host (`smbstatus`). | Konzept 11.1; Samba läuft auf dem Host (`/etc/samba/smb.conf`) | Nur Ruhezeit (Größe+mtime) plus Umbenennungs-Konvention oder Host-Hilfsskript; Testfall "große Kopie mit Pausen" |
| A9 | mittel | **ZIP-Download mehrerer Dateien** läuft gestreamt durch einen Odoo-Worker (kein `x_sendfile` möglich) → Worker für die ganze Dauer belegt, `limit_time_real` bricht große ZIPs ab. | Konzept 8; Prefork ein Request je Worker (`service/server.py:1361`), Zeitlimit `:891, 1012` | Größengrenze oder ZIP als Hintergrundjob in eine Temp-Datei, dann Auslieferung per `x_sendfile` |
| A10 | mittel | **Regel-Semantik ungenau:** "Odoo-Regeln erlauben nur, sie verbieten nicht" gilt nur für **Gruppen**-Regeln (ODER); **globale** Regeln verbieten (UND). "Beim Ändern von Bereichen `registry.clear_cache()`" ist unnötig: `_compute_domain` ist je Nutzer/Modell/Modus gecacht, die Gruppen des Bereichs stehen in der SQL-Unterabfrage und wirken sofort; `clear_cache()` leert alle Caches aller Worker. | `ir_rule.py:138-173`; Cache-Leerung nur beim Ändern von Regeln `:187-205` | Formulierung korrigieren; kein `clear_cache()` bei Bereichsänderungen |
| A11 | mittel | **Backup: Reihenfolge und Aufräumfenster fehlen.** Wird ein Blob zwischen DB-Sicherung und Blob-Sicherung aufgeräumt, fehlt er im Backup, obwohl die gesicherte DB auf ihn zeigt. | Konzept 5 "Backup" | DB zuerst, dann Blobs; Schonfrist des Aufräumjobs > Dauer eines Backup-Laufs (oder Aufräumjob während Backup aus); regelmäßiger Abgleich "alle referenzierten Blobs im Backup" |
| A12 | niedrig | **Hardlink nur auf einer Platte geprüft.** `link` (Temp → Hash-Name) funktionierte auf `fmv2blobs` (nur `disk3`); bei einem Share über mehrere Platten können Temp- und Zielordner auf verschiedenen Platten liegen (vermutlich `EXDEV`). | Test: `os.link` auf `fmv2blobs` ok, `nlink=2`; `fmv2blobs.cfg`: `shareInclude="disk3"` | Blob-Share auf eine Platte/einen Pool festlegen oder Temp je Zielordner; in den Betriebsvoraussetzungen nennen |
| A13 | niedrig | **`fsync` mit Ausreißern:** Median 33 ms (bestätigt ~28 ms), aber ein Aufruf **7,3 s** – vermutlich Anlaufen der Platte (`spindownDelay="30"`). | 20 × 4 KiB auf `fmv2blobs`; `/boot/config/disk.cfg` | Zeitlimits (WebDAV, Eingangsordner, Upload-Stücke) und Bedienung auf Anlaufzeiten auslegen; oder Blob-Speicher auf SSD-Pool |
| A14 | niedrig | **ONLYOFFICE-Callback prüft Rechte heute nicht wirksam:** `attachment.has_access("write")` und `_can_return_content(...)` werden aufgerufen, ihr Ergebnis aber verworfen; Schutz hängt allein am JWT. | `onlyoffice_odoo/controllers/controllers.py:214-215`; `has_access` liefert nur bool (`orm/models.py:4117-4122`) | Muster nicht übernehmen; in Schritt 6 JWT verpflichtend und `check_access` |
| A15 | niedrig | **Kern 13 widerspricht dem Konzept:** Kern: `_check_access`/`_search` werden "für die Rechte" überschrieben; Konzept 4/12: Knoten-Rechte über `ir.rule`, Override nur für die allgemeine Verknüpfung (Mixin). | Kern 13; Konzept 4 (Geschäftsbezug), 12 | Kern präzisieren (bei nächster Freigaberunde) |
| A16 | niedrig | **mail.activity hat keinen Aufräumjob für per DB-Kaskade gelöschte Ziele**, es überspringt sie nur mit `exists()`. "nach dem Muster von `mail.activity`" trifft für den Aufräumjob nicht zu. | `mail/models/mail_activity.py:417, 541` (`exists()`); einziger Autovacuum `:860-861` (überfällige Aktivitäten) | Aufräumjob als eigene Festlegung formulieren |
| A17 | niedrig | **Prototyp löst WebDAV-Namen exakt auf**, Konzept verlangt Auflösung ohne Groß/Klein. | `fm_proto/dav.py:69-71` (`("name", "=", name)`) vs. Konzept 19.4 "Folgen", 4 | Bei Umsetzung Suche über `lower(name COLLATE "und-x-icu")` (Index greift, siehe Nr. 20) |
| A18 | niedrig | **Heutige WebDAV-Tokens sind nicht nur flüchtig, sondern je Prozess:** bei `workers>0` sieht ein Worker die Tokens des anderen nicht. | `int_filemanager/webdav_tokens.py:5-7` | Nur Hinweis zum heutigen Modul (HM-SRV) |
| A19 | niedrig | **`http.Stream.from_path` ist für Blobs unbrauchbar** (erlaubt nur Addon-Pfade über `file_path`); der Prototyp baut `Stream(type='path', …)` direkt – das ist der richtige Weg, steht aber nirgends. | `http.py:551-573` | In Konzept 5 "Lesen" festhalten |
| A20 | niedrig | Diagramm in 3 führt `dav_lock`/`dav_prop` unter "gemeinsam", Abschnitt 4 sagt "erst mit WebDAV". | Konzept 3 vs. 4 | redaktionell |
| A21 | niedrig | Kleinere Ungenauigkeiten: Zeilenzahlen (`dav.py` 480 statt ~430, `dav_inproc.py` 641 statt ~560), Cloudreve-Stand (lokal jetzt 4.19.1), freier Platz (3,6 statt 3,7 TB), mehrere Zeilennummern verschoben (Tabelle B). | siehe B | redaktionell |

---

## B. Behauptungen einzeln

Zeilennummern beziehen sich auf das Image 19.0-20260817 (Pfade relativ zu `odoo/`, Addons unter `addons/…`);
wo das Konzept andere Zeilen nennt, steht die aktuelle Stelle im Beleg.

### Abschnitte 1–3

| Nr. | Abs. | Behauptung (kurz) | Urteil | Beleg | Folge |
|---|---|---|---|---|---|
| 1 | 1 | Odoo bringt 2FA, Portal, Crons, Chatter, Aktivitäten, E-Mail mit | bestätigt | `addons/auth_totp`, `auth_totp_portal`, `portal`, `mail` vorhanden | – |
| 2 | 2 | I7: Rechte nur über `ir.model.access`/`ir.rule` | ungenau | gilt für ORM-Zugriffe als Nutzer; Routen mit `auth='public'`, `_can_return_content`/`access_token` (`base/models/ir_binary.py:50-53`) und `sudo`-Pfade prüfen separat; Neben-Modelle A1 | A1, A2 |
| 3 | 2 | I9: jeder Vorgang ganz oder gar nicht | ungenau | Dateisystem und DB sind nicht gemeinsam transaktional; gemeint ist der sichtbare DB-Zustand (Review-Formulierung "logische Atomarität") | Wortlaut |
| 4 | 2 | I9: Wiederholungen (`retrying`, Doppelklick) erzeugen keine Doppelungen | ungenau | `retrying` wiederholt nur Konkurrenzfehler, nicht `IntegrityError`/`LockError` (`service/model.py:192-214`) | A3 |
| 5 | 2 | I10: Erweiterung über Vererbung, Hooks, Routen, Auth-Methoden, CLI aus Addons | bestätigt | `_auth_method_{auth}` `base/models/ir_http.py:282`; `load_addons_commands` `cli/command.py:68`; `post_load` `modules/module.py:512-513` | – |
| 6 | 2 | I11: Odoos Pillow ist beschränkt | bestätigt | `tools/image.py:27-28` (`Image.preinit()`, `_initialized = 2`) | – |
| 7 | 2 | I12: 128-MiB-Grenze | bestätigt | `http.py:247` `DEFAULT_MAX_CONTENT_LENGTH`, gesetzt `:1484` | – |
| 8 | 3 | nginx liefert Blobs per X-Accel direkt von der Platte | bestätigt | `http.py:669-683` | – |
| 9 | 3 | `odoo fmdav`: ORM direkt über Registry, Cursor, `retrying` wie Odoo selbst | bestätigt | `base/models/ir_cron.py:235, 677-693`; `bus/websocket.py:924-932` | A3 beachten |
| 10 | 3 | `dav_lock`/`dav_prop` gemeinsam | ungenau | Abschnitt 4: "erst mit WebDAV" | A20 |

### Abschnitt 4 (Datenmodell)

| Nr. | Abs. | Behauptung | Urteil | Beleg | Folge |
|---|---|---|---|---|---|
| 11 | 4 | `_parent_store` pflegt `parent_path` beim Verschieben des Teilbaums | bestätigt | `orm/models.py:4608` (in `write`), `:5020-5048` | – |
| 12 | 4 | `active` filtert automatisch | bestätigt | `orm/models.py` `active_test` (z. B. `:3796`) | – |
| 13 | 4 | Teil-Unique-Index über `models.UniqueIndex` | bestätigt | `orm/table_objects.py:125-205` (freie Definition inkl. `WHERE`) | – |
| 14 | 4 | `lower(name COLLATE "und-x-icu")`: `größe.TXT` = `Größe.txt`, `GRÖSSE.txt` verschieden | bestätigt | empirisch PG 16.15: `größe.txt`/`größe.txt`/`grösse.txt` | – |
| 15 | 4 | "wie auf NTFS" | nicht prüfbar | Windows-Verhalten, kein Windows-Test | – |
| 16 | 4 | Papierkorb blockiert den Namen nicht (`WHERE active`) | bestätigt | Index-Definition; empirisch `n1` | – |
| 17 | 4 | Namenssuchen mit demselben Ausdruck nutzen den Index | bestätigt | `EXPLAIN`: Index Scan `n3_u`; mit `lower(name)` ohne Kollation nur Filter | Suchen genau so formulieren |
| 18 | 4 | Name je Ordner eindeutig (auch Wurzel) | ungenau | NULL-Eltern → Duplikate möglich (Test `n1`), `NULLS NOT DISTINCT` hilft (`n2`) | A6 |
| 19 | 4 | Leere Datei = Knoten ohne Revision | ungenau | Prototyp: `ensure_empty_blob` | A7 |
| 20 | 4 | `size` als `Float`, weil `fields.Integer` `int4` ist | bestätigt | `orm/fields_numeric.py:20` (`int4`), `:133` (`float8`) | – |
| 21 | 4 | `Float` exakt bis 2^53 | bestätigt | `float8` = IEEE-double | – |
| 22 | 4 | `dav_lock`: LOCK/UNLOCK über `pg_advisory_xact_lock` | bestätigt | Prototyp `dav_server.py:572`, `dav_inproc.py:608` | – |
| 23 | 4 | Muster `mail.activity`: `_check_access` und `_search` überschreiben | bestätigt | `mail/models/mail_activity.py:197, 363`; `_check_access` laut Docstring überschreibbar `orm/models.py:4135-4144`; `_search`-Signatur in 19 neu (`bypass_access`) → Update-Risiko | Update-Test |
| 24 | 4 | `exists()` vor der Prüfung | bestätigt | `mail_activity.py:417, 541` | – |
| 25 | 4 | Aufräumjob für kaskadiert gelöschte Ziele "nach dem Muster von mail.activity" | ungenau | kein solcher Job in `mail_activity.py` (nur `:860-861`) | A16 |
| 26 | 4 | heute `linkable.mixin` fest auf `partner_id` | bestätigt | `int_filemanager/models/filemanager_linkable_mixin.py:4-18` | – |
| 27 | 4 | C-Kollation ist Odoo-Standard (`service/db.py:146`) | bestätigt | `service/db.py:142-146` (nur mit `template0`); `fmv2`: Collate C, Ctype en_US.utf8 | – |
| 28 | 4 | Präfix-/Teilbaum-Abfragen nutzen bei C-Kollation normale Indizes | bestätigt | `EXPLAIN` `n4`: `Index Cond: parent_path >= '1/7/' AND < '1/70'` | – |
| 29 | 4 | `_parent_store_update` zerstört Teilbäume auf `en_US.utf8` | nicht prüfbar | Code nutzt `LIKE concat(parent_path, …)` (`orm/models.py:5035-5040`); Fehlerbild nur im DB-Vorrang-Konzept 19.2 belegt, keine en_US-Test-DB vorhanden | vor HM-SRV-Update gezielt testen |
| 30 | 4 | Namens-Sortierung über Hook `_order_field_to_sql` | bestätigt | `orm/models.py:5262` | – |
| 31 | 4 | Trigram-Index für Namenssuche | bestätigt | `orm/fields.py:116` (`index='trigram'`); `pg_trgm` 1.6 in `fmv2` installiert; Messwert (185/37) nicht erneut | – |
| 32 | 4 | NFC-Normalisierung beim Anlegen nötig | bestätigt | empirisch: `lower(NFD) ≠ lower(NFC)` | – |

### Abschnitt 5 (Blob-Speicher)

| Nr. | Abs. | Behauptung | Urteil | Beleg | Folge |
|---|---|---|---|---|---|
| 33 | 5 | `ir.attachment` nimmt Inhalte nur als Bytes (`:284-313`) | bestätigt | `base/models/ir_attachment.py:287` `_set_attachment_data(asbytes)` | – |
| 34 | 5 | `store_fname` nicht setzbar (`:723, 762`) | bestätigt | `:723` (`write`), `create` ab `:754` filtert `file_size`/`checksum`/`store_fname` | – |
| 35 | 5 | "`ir.attachment` reicht hier nicht" | ungenau | richtig, aber Begründung erweitern: SHA-1 (`:337`), kein `fsync` (`:158-168`), Rechte am Elterndatensatz | Wortlaut (Review) |
| 36 | 5 | Blobs unter `<data_dir>/filestore/<db>/` → `x_sendfile` greift (`http.py:665-680`) | bestätigt | `http.py:669-683` (`relative_to(data_dir/filestore)`, `X-Accel-Redirect`, `Content-Length: 0`) | A19 |
| 37 | 5 | Samba gibt den Blob-Share nicht frei | bestätigt (Test) | `fmv2blobs` ohne SMB (Konfiguration geprüft) | – |
| 38 | 5 | `link` ohne Überschreiben, `fsync` des Ordners | bestätigt | Prototyp `blobstore.py:81-87`; `os.link` auf shfs/`disk3` empirisch ok | A12 |
| 39 | 5 | Keine Transaktion während des Datenstroms | bestätigt (Prototyp) | `dav_server.py` Ablauf; Messung 19.10 nicht erneut | – |
| 40 | 5 | `fsync` ~28 ms je Datei auf dem Array | bestätigt | Median 33 ms, min 25 ms (20 × 4 KiB) | A13 (Ausreißer 7,3 s) |
| 41 | 5 | Schreibrate ~46 MB/s | nicht erneut | – | – |
| 42 | 5 | `@api.autovacuum` | bestätigt | `orm/decorators.py:299` | – |
| 43 | 5 | Aufräumen wie `_gc_file_store` (`:191-263`) mit Tabellensperre als erstem Statement | bestätigt | `ir_attachment.py:191-252`, `LOCK` `:212` | – |
| 44 | 5 | …dadurch wird "kein gerade committeter Verweis übersehen" | ungenau | schützt nicht bei Wiederverwendung eines alten Blobs | A4 |
| 45 | 5 | Lesen per `http.Stream(type='path')`, ETag, Range über `send_file` | bestätigt | `http.py:537` (`conditional=True`), `:652-683` | A19 |
| 46 | 5 | Backup: DB + referenzierte Blobs, inkrementell | ungenau | Reihenfolge/Aufräumfenster fehlen | A11 |

### Abschnitt 6 (Schreibwege)

| Nr. | Abs. | Behauptung | Urteil | Beleg | Folge |
|---|---|---|---|---|---|
| 47 | 6 | Zeilen sperren mit `lock_for_update` | ungenau | `SKIP LOCKED`, wirft `LockError(UserError)`, wartet nicht (`orm/models.py:5564-5589`, `exceptions.py:109`) | A3 |
| 48 | 6 | Umbenennen/Verschieben = reines `write` | bestätigt | Nr. 11 | – |
| 49 | 6 | `flush_recordset()` nötig zwischen Freimachen und Belegen eines Namens | bestätigt | `orm/models.py:6367`; ORM schreibt verzögert; litmus-Befund 19.4 | – |
| 50 | 6 | `retrying()` wiederholt jeden Schreibvorgang gefahrlos | ungenau | nur Serialisierung/Deadlock/LockNotAvailable/ConcurrencyError; Datei-Uploads nur, wenn zurückspulbar, sonst `RuntimeError` (`service/model.py:192-214`) | A3 |
| 51 | 6 | 10 gleichzeitige `PUT` auf neuen Namen → 1 Knoten, 10 Revisionen | ungenau | Code: `create` ohne Savepoint (`dav_server.py:426-429`) → `UniqueViolation` → `ValidationError`; empirisch `zz_race` | A3 |
| 52 | 6 | Blob-Anlage idempotent über den Hash | bestätigt | Prototyp `models.py:26-34` (Savepoint + `UniqueViolation`) | – |
| 53 | 6 | Kopieren/Version wiederherstellen ohne Bytes zu kopieren | bestätigt (Entwurf) | Datenmodell | – |

### Abschnitt 7 (Upload in Stücken)

| Nr. | Abs. | Behauptung | Urteil | Beleg | Folge |
|---|---|---|---|---|---|
| 54 | 7 | Öffentliche API liest den Body ganz in den RAM | bestätigt | `HTTPREQUEST_ATTRIBUTES` ohne `stream` `http.py:1500-1510`; `environ` ohne `wsgi.input` `:1480-1489` | – |
| 55 | 7 | Streamen nur über internes Attribut | bestätigt | `_HTTPRequest__wrapped` `http.py:1469-1476`; Odoo selbst `:2149` | – |
| 56 | 7 | Route mit eigenem `max_content_length` | bestätigt | `http.py:2440-2444` | – |
| 57 | 7 | kurze Requests → `limit_time_real` greift nicht | bestätigt | `service/server.py:891, 1012` (je Request) | – |
| 58 | 7 | 4-MB-Stücke begrenzen Worker-Wachstum; Worker wird nach `limit_memory_soft` recycelt | bestätigt (Mechanismus) | `service/server.py:1285`; Messwerte nicht erneut | – |
| 59 | 7 | SHA-256 über mehrere Requests nicht fortschreibbar | bestätigt | `pickle.dumps(hashlib.sha256())` → `TypeError` | – |
| 60 | 7 | `finish` 3 GB 46–56 s | nicht erneut | – | – |

### Abschnitte 8–10

| Nr. | Abs. | Behauptung | Urteil | Beleg | Folge |
|---|---|---|---|---|---|
| 61 | 8 | `/web/image`: Rechte greifen nativ | bestätigt | `base/models/ir_binary.py:23-55` (`check_access("read")` `:54`); Achtung: `_can_return_content`/Token liefern `sudo` `:50-53` | Hooks nicht öffnen |
| 62 | 8 | `image.mixin`-Muster | bestätigt | `base/models/image_mixin.py:8` | – |
| 63 | 8 | ZIP gestreamt ohne ganze Datei im Speicher | ungenau | machbar, aber belegt den Worker für die Dauer | A9 |
| 64 | 8 | Odoos Pillow-Beschränkung bleibt unberührt | bestätigt | Nr. 6 | – |
| 65 | 8 | 209.429 Bilder auf Tower | nicht prüfbar | Live-DB nicht angefasst | – |
| 66 | 9 | `attachment_indexation`-Logik vorhanden | bestätigt | `addons/attachment_indexation/models/ir_attachment.py` | – |
| 67 | 9 | N1: `action_analyze_document`/`action_apply_extracted_values` öffentlich mit `sudo` | bestätigt | `int_filemanager/models/filemanager_file.py:707-744` (`@api.model`, `sudo().search` `:724, :744`); erreichbar über `call_kw` | A2 |
| 68 | 10 | ONLYOFFICE-Callback heute ohne Basisrevisionsprüfung | bestätigt | `onlyoffice_odoo/controllers/controllers.py:236-254` (schreibt `raw` ohne Key-Vergleich) | A14 |
| 69 | 10 | WebDAV-Tokens heute nur im Speicher | bestätigt | `int_filemanager/webdav_tokens.py:5-7` | A18 |
| 70 | 10 | Desktop-Office öffnet Serverdateien nur über WebDAV/SharePoint | nicht prüfbar | Microsoft-Verhalten | – |
| 71 | 10 | File System Access API nur Chrome/Edge | nicht prüfbar | Browser-Verhalten | – |

### Abschnitt 11 (Explorer-Zugriff, Eingangsordner, fmdav)

| Nr. | Abs. | Behauptung | Urteil | Beleg | Folge |
|---|---|---|---|---|---|
| 72 | 11 | SMB+FUSE-Punkte (UID-Zuordnung, Puffer, Metadaten, FUSE im Container) | nicht prüfbar | kein Prototyp | – |
| 73 | 11.1 | Eingangsordner: Datei "nicht mehr geöffnet" erkennbar | ungenau | aus dem Container nicht sichtbar | A8 |
| 74 | 11.1/13 | Samba-Freigabe über `/boot/config/smb-extra.conf` | bestätigt | `/etc/samba/smb.conf:42` (`include`); Datei existiert noch nicht | – |
| 75 | 11.2 | Befehl aus dem Addon (`cli/command.py:68-105`) | bestätigt | `cli/command.py:68-106` | – |
| 76 | 11.2 | `--addons-path` vor dem Befehlsnamen | bestätigt | `cli/command.py:112-117` | – |
| 77 | 11.2 | werkzeugs Thread-Server wie Odoo im Thread-Modus | bestätigt | `service/server.py:241` (`ThreadedWSGIServerReloadable` ⊂ `werkzeug.serving.ThreadedWSGIServer`) | – |
| 78 | 11.2 | keine Prefork-Worker, kein `limit_time_real` | bestätigt | Zeitlimit nur in Odoos Servern (`server.py:503-523, 891`) | – |
| 79 | 11.2 | `get_input_stream(environ)` nötig | bestätigt (Prototyp) | Beobachtung 19.10, nicht erneut | – |
| 80 | 11.2 | ORM-Muster `check_signaling`/`signal_changes`/`reset_changes` | bestätigt | `ir_cron.py:235, 677-693` | – |
| 81 | 11.2 | Wiederholung mit `retrying()` für die ganze Anfrage | ungenau | A3 | A3 |
| 82 | 11.2 | WsgiDAV-Eigenheiten: LOCK-Content-Type, Sperrprüfung beim DELETE | bestätigt | WsgiDAV 4.3.5 `request_server.py:1283` (`"application; charset=utf-8"`), `:585-593` (nur Elternordner) | Version festnageln |
| 83 | 11.2 | Prüfung mit `res.users.apikeys._check_credentials` und eigenem Bereich | bestätigt | `base/models/res_users.py:1574-1575`; SQL `scope IS NULL OR scope = %(scope)s` `:1741` | – |
| 84 | 11.2 | Nicht-Admins: Ablaufdatum bis `api_key_duration`, sonst 1 Tag | bestätigt | `res_users.py:1577-1587` (`is_system()` ausgenommen), `res_groups.py:32` | – |
| 85 | 11.2 | `GET` per `X-Accel-Redirect`, nginx `etag off; add_header ETag $upstream_http_etag` | bestätigt | Testkonfiguration `config_v2/nginx.conf:11`; Wirkung 19.7 nicht erneut | – |
| 86 | 11.2 | Identitätsregel (vacated/Tausch/Schatten) | bestätigt (Prototyp) | `fm_proto/dav.py`; Tests 19.4/19.10 nicht erneut | – |
| 87 | 11.2 | Pfadauflösung per CTE, danach `check_access('read')` | bestätigt | `orm/models.py:4100`; Prototyp `dav.py` | A17 |
| 88 | 11.2 | Grenzen (71 Dateien 13 s usw.) | nicht erneut | – | – |

### Abschnitte 12–18

| Nr. | Abs. | Behauptung | Urteil | Beleg | Folge |
|---|---|---|---|---|---|
| 89 | 12 | Öffentliche Methoden über JSON-2 für jeden Nutzer mit API-Schlüssel | ungenau | zusätzlich `call_kw` ohne Schlüssel | A2 |
| 90 | 12 | intern `_…`/`@api.private`; lesend `@api.readonly` mit lesendem Cursor | bestätigt | `orm/decorators.py:328, 345`; `rpc/controllers/json2.py:23-35, 49-55` | – |
| 91 | 12 | Regel-Domain über `scope_id.read_group_ids` und `user.all_group_ids` | bestätigt | `res_users.py:258` | – |
| 92 | 12 | "Odoo-Regeln erlauben nur, sie verbieten nicht" | ungenau | globale Regeln UND, Gruppenregeln ODER (`ir_rule.py:141-173`) | A10 |
| 93 | 12 | Beim Ändern von Bereichen `registry.clear_cache()` | ungenau | nicht nötig (`ir_rule.py:138-141`), teuer | A10 |
| 94 | 12 | Revisionen/Vorschauen/OCR erben die Knoten-Rechte ohne eigene Regeln | **widerlegt** | `ir_rule.py:146-150` (nur `_inherits`) | A1 |
| 95 | 12 | Freigabe-Links mit eigenen Tokens bestehen | bestätigt | `int_filemanager/controllers/main.py`, `filemanager_file.py` (`share_token`) | – |
| 96 | 12 | Kundenportal über `portal` | bestätigt | `addons/portal` | – |
| 97 | 13 | Crons mit `noupdate="1"`, sonst setzt ein Update sie zurück | bestätigt | `tools/convert.py:273, 358-360` | – |
| 98 | 13 | Modul-eigene `data/neutralize.sql` | bestätigt | `modules/neutralize.py:30` | – |
| 99 | 13 | Nur `db_name` ohne `dbfilter` → keine DB-Verbindung je Request | bestätigt | `service/db.py:438-446`; `X-Odoo-Database` `http.py:1828` | – |
| 100 | 13 | Grenze `db_maxconn` | bestätigt | Standard 64, `tools/config.py:393` | – |
| 101 | 13 | Windows: `FileSizeLimitInBytes` 50 MB (max. 4 GB), `BasicAuthLevel` | nicht prüfbar | Windows; Messung 19.4 | – |
| 102 | 14 | Share 1,8 TB, 429.184 Einträge, 29.316 Ordner, 98 GB Duplikate | nicht erneut | Live-Share nicht gezählt | – |
| 103 | 14 | ca. 3,7 TB frei | ungenau | `df /mnt/user`: 3,6 TB frei (26.09.) | – |
| 104 | 14 | Groß/Klein-Duplikate im Bestand unmöglich (SMB) | ungenau | Share wird auch von Linux-Prozessen beschrieben (heutiges Modul, Container) – Duplikate möglich; Prüfung vor Import bleibt nötig | – |
| 105 | 14 | 27,5 MB/s, ~18 h | nicht erneut | – | – |
| 106 | 15 | Entfallende Teile existieren (Watcher, `index_utils`, `suppress_watcher`, `write_service`, `publish_service`, `write_journal`, `acl_rules`) | bestätigt | `int_filemanager/…` alle gefunden, `path_utils.py:38` | – |
| 107 | 16 | Abbruchtests nicht in `TransactionCase` (Post-Commit-Hooks laufen nicht) | bestätigt | `tests/test_cursor.py:104` | echte Prozesse |
| 108 | 16 | `test_lint` im Image, pylint nicht | bestätigt | `addons/test_lint/tests/`; `import pylint` → `ModuleNotFoundError` | – |
| 109 | 16 | Update-Absicherung: genannte halb-internen Stellen existieren | bestätigt | alle gefunden (Nr. 23, 36, 55, 75, 80, 83) | – |
| 110 | 17 | Tower: 1 interner Nutzer außer Admin, keine Portal-Nutzer | nicht prüfbar | Live-DB nicht angefasst | – |

### Abschnitt 19 (Prototyp-Ergebnisse)

| Nr. | Abs. | Behauptung | Urteil | Beleg | Folge |
|---|---|---|---|---|---|
| 111 | 19 | Testaufbau: PG 16, `workers=2`, `x_sendfile`, `location /web/filestore/ internal` | bestätigt | `config_v2/odoo.conf`, `nginx.conf:11`; PG 16.15 | – |
| 112 | 19.1 | Upload 3 GB 115/84 MB/s, Hash identisch | nicht erneut | – | – |
| 113 | 19.1 | `finish` 51–56 s | nicht erneut | – | – |
| 114 | 19.1 | Download 3 GB 9,6 s, Odoo 5 ms | nicht erneut | Mechanismus Nr. 36 bestätigt | – |
| 115 | 19.1 | Range 206, `If-None-Match` 304 | nicht erneut | Mechanismus Nr. 45 bestätigt | – |
| 116 | 19.1 | Fortsetzen, idempotente Stücke, Lücke → 409 | bestätigt (Code) | Prototyp `controllers.py:53` (`lock_for_update` des Uploads) | A3 (LockError) |
| 117 | 19.1 | `finish` doppelt → 1 Revision | bestätigt (Code) | `controllers.py:60-63` (Temp nach Commit) | – |
| 118 | 19.1 | Deduplizierung 1 Blob, 2 Knoten | bestätigt (Code) | `models.py:26-34` | – |
| 119 | 19.1 | `os._exit` nach Verlinken/vor Commit → korrekt nach erneutem `finish` | nicht erneut | – | – |
| 120 | 19.1 | Aufräumjob entfernt verwaiste Blobs, behält referenzierte | bestätigt (Code) | `models.py:36-75` | A4 |
| 121 | 19.2 | kein `stream`, `wsgi.input` gefiltert (`:1480-1510`) | bestätigt | Nr. 54 | – |
| 122 | 19.2 | Worker-Speicher wächst, kein Python-Leck, `MALLOC_*` hilft nicht | nicht erneut | – | – |
| 123 | 19.2 | Recycling bei `limit_memory_soft` | bestätigt | Nr. 58 | – |
| 124 | 19.2 | `fields.Integer` = `int4` | bestätigt | Nr. 20 | – |
| 125 | 19.3 | Kopierraten, 0 Fehler, Stichprobe 300/300 | nicht erneut | – | – |
| 126 | 19.4 | WsgiDAV 4.3.5 | bestätigt | `pylib_v2/wsgidav-4.3.5.dist-info`; PyPI 2026-06-27 | – |
| 127 | 19.4 | `dav_service.py` ~530, `dav.py` ~430 Zeilen | ungenau | 528 / **480** | A21 |
| 128 | 19.4 | Kein WebDAV im Odoo-19-Core | bestätigt | `grep -r PROPFIND` leer | – |
| 129 | 19.4 | `auth='bearer'` (`ir_http.py:212-251`) | bestätigt | `base/models/ir_http.py:212` | – |
| 130 | 19.4 | litmus 100 %, Windows-Kopiermessungen | nicht erneut | – | – |
| 131 | 19.4 | Download 60 MB vom Windows-Client abgelehnt (50 MB) | nicht prüfbar | Windows | – |
| 132 | 19.4 | Word-/Excel-/LibreOffice-Muster halten die Identität | nicht erneut | – | – |
| 133 | 19.4 | Groß/Klein: Server unterschied, Windows nicht | nicht erneut | – | – |
| 134 | 19.4 B1 | ~25 ms Grundlast, 8 Requests je Datei | nicht erneut | in 19.6 korrigiert | – |
| 135 | 19.4 B5 | WsgiDAV `request_server.py:1283`, `:585-599` | bestätigt | Nr. 82 | – |
| 136 | 19.4 B6 | ORM kennt Teil-Index nicht → `flush_recordset` | bestätigt | Nr. 49 | – |
| 137 | 19.5 | Cloudreve-Code-Stand 4.18.0 | ungenau | lokales Repo jetzt `4.19.1-4-g37cf66d` | A21 |
| 138 | 19.5 | `performCopyMove` (`webdav.go:680-708`) | bestätigt | `pkg/webdav/webdav.go:702` | – |
| 139 | 19.5 | WebDAV-Passwort im Klartext per SQL-Gleichheit (`inventory/user.go:435-446`) | bestätigt | `inventory/user.go:443` (`davaccount.Password(pwd)`) | – |
| 140 | 19.5 | `SoftDelete` (`inventory/file.go:409-421`), `memlock.go`, `davaccount.go`, `X-Expected-Entity-Length` | bestätigt | Dateien/Stellen vorhanden | – |
| 141 | 19.6 | Odoo greift selbst über `_HTTPRequest__wrapped` zu (`make_request_wrap_methods`) | bestätigt | `http.py:1469-1476` | – |
| 142 | 19.6 | `retrying` spult nur Formular-Dateien zurück (`service/model.py:201-204`) | bestätigt | `service/model.py:200-206` | – |
| 143 | 19.6 | `db_name`+`dbfilter` → `list_dbs` mit neuer Verbindung (`db.py:434-452`, `http.py:1813-1840`) | bestätigt | `service/db.py:438-446`, `http.py:1828` | – |
| 144 | 19.6 | Messwerte 21,9/3,0/34,1/15,1 ms; 6 ms `pbkdf2` | nicht erneut | Mechanismus `KEY_CRYPT_CONTEXT` `res_users.py:1610` bestätigt | – |
| 145 | 19.6 | Streaming in einer Route 3 GB mit konstantem Speicher | nicht erneut | – | – |
| 146 | 19.7 | `_auth_method_<name>` generisch (`ir_http.py:270-283`) | bestätigt | `ir_http.py:282` | – |
| 147 | 19.7 | `dav_inproc.py` ~560 Zeilen | ungenau | **641** | A21 |
| 148 | 19.7 | Messungen (PUT 65–76 ms, 14,1 s, 71 s, 265 MB) | nicht erneut | – | – |
| 149 | 19.7 | große Uploads belegen einen Prefork-Worker, alles andere wartet | bestätigt (Mechanismus) | ein Request je Worker `server.py:1361` | – |
| 150 | 19.8 #1 | Request-Transaktion umspannt die ganze Anfrage (`idle in transaction`) | bestätigt | `http.py:2267-2329` (`_serve_db`, ein Cursor um `serve_func`) | – |
| 151 | 19.8 #2 | `limit_time_real` beendet den Worker | bestätigt | `server.py:891, 1012` | – |
| 152 | 19.8 #7 | Namens-Wettlauf: "Unique-Index + Retry", nichts geht verloren | **widerlegt** | `service/model.py:207-214`; `zz_race` | A3 |
| 153 | 19.8 | übrige Stolperstein-Messungen (#1–#3, macOS chunked) | nicht erneut | – | – |
| 154 | 19.9 | OCA `base_dav` nicht in `server-backend` 17/18 | bestätigt | GitHub-API: 0 Treffer in 17.0 und 18.0 | – |
| 155 | 19.9 | Vertel `dms_webdav` (Odoo 18, AGPL, 0 Sterne) | bestätigt | `vertelab/odoo-document` 18.0: `dms_webdav`, `dms_sftp`; AGPL-3.0; 0 Sterne | – |
| 156 | 19.9 | App-Store-, Enterprise-, Seafile-Aussagen | nicht prüfbar | keine Code-Quelle / nicht erneut | – |
| 157 | 19.10 | Befehl aus Addons, `register_wsgi_handler` gibt es nicht mehr | bestätigt | `cli/command.py:68-106`; `grep register_wsgi_handler` leer | – |
| 158 | 19.10 | Start wie `odoo shell` (`server.start(preload=[], stop=True)`) | bestätigt | `cli/shell.py:76` | – |
| 159 | 19.10 | `my_default` greift nicht für später hinzugefügte Optionsgruppen | bestätigt | Standardwerte werden beim Init gesammelt, `tools/config.py:159-187, 503-505` | – |
| 160 | 19.10 | `config.rcfile` veraltet → `config['config']` | bestätigt | `tools/config.py:190-197` | – |
| 161 | 19.10 | `server.load_server_wide_modules()` | bestätigt | `service/server.py:1511` | – |
| 162 | 19.10 | `cli/fmdav.py` ~50, `dav_server.py` ~630 Zeilen | bestätigt | 55 / 635 | – |
| 163 | 19.10 | Messungen (litmus, 60–65 ms, 13,0 s, 71,5 s, 108 MB, langsamer Client) | nicht erneut | – | – |
| 164 | 19.10 | 10 gleichzeitige PUT → 1 Knoten, 10 Revisionen | ungenau | Nr. 51 | A3 |
| 165 | 19.11 | `GeventServer` (`server.py:767-880`), `long_polling_spawn` (`:944-948`) | bestätigt | `server.py:767, 944` | – |
| 166 | 19.11 | `patch_all` + psycopg2-Warte-Callback (`site.py:22-53`) | bestätigt | `_monkeypatches/site.py:34-53` | – |
| 167 | 19.11 | `limit_memory_soft_gevent`, `db_maxconn_gevent` (`sql_db.py:823`) | bestätigt | `server.py:779`; `sql_db.py:823` | – |
| 168 | 19.11 | Websocket: `call_on_close` (`bus/websocket.py:1000-1037`), `retrying` (`:906-935`) | bestätigt | `bus/websocket.py:1014-1016`, `:924-932` | – |
| 169 | 19.11 | Socket aus `_HTTPRequest__environ['socket']`, gesetzt von gevent (`:835-845`) und Thread-Server (`:204-214`) | bestätigt | `bus/websocket.py:1014`; `server.py:208, 839` | – |
| 170 | 19.11 | `ODOO_MAX_HTTP_THREADS`; Zeitlimit für HTTP-Threads außer `websocket` (`websocket.py:1118`) | bestätigt | `server.py:247-250, 503-523` (`thread_type != 'websocket'`); `bus/websocket.py:1118` | – |
| 171 | 19.11 | Prefork-Worker (`server.py:1229-1403`) | bestätigt | `server.py:1229, 1361` | – |
| 172 | 19.11 | gevent: `fsync` hält alle Greenlets 22,4 s an | nicht erneut | Skript `docs/prototypes/fm2/tests/gevent_fsync_blockade.py` | – |
| 173 | 19.12 | `post_load` (`module.py:512`, `server.py:1511, 1621`) | bestätigt | `modules/module.py:512-513`; `server.py:1511`, Aufruf bei `:1621` | – |
| 174 | 19.12 | `CommonServer.on_stop` (`server.py:437-449`), genutzt von bus (`bus.py:276`, `websocket.py:1154`) | bestätigt | `server.py:438-445`; `bus/models/bus.py:276`; `bus/websocket.py:1154` | – |
| 175 | 19.12 | beim Prefork-Neuladen wird `on_stop` nicht aufgerufen | bestätigt | `server.py:1174-1183` (Rückkehr vor `super().stop()`) | – |
| 176 | 19.12 | `bus.ImDispatch` (`bus.py:225-290`) | bestätigt | `bus/models/bus.py:207-276` | – |
| 177 | 19.12 | `process_zombie` sammelt jedes Kind (`waitpid(-1)`), Exit-Code 3 beendet den Master | bestätigt | `server.py:995-1002` | – |
| 178 | 19.12 | Varianten B/C (Neuladen, `kill -9`, Zeitlimit) | nicht erneut | – | – |
| 179 | 19.12 | WsgiDAV 4.3.5 (27.06.2026), ASGIWebDAV 2.0.1 (20.02.2026), PyWebDAV3 0.11.0 (2024) | bestätigt | PyPI | Sterne/Push-Daten nicht erneut |
| 180 | 19.13 | Nextcloud: `FakeLockerPlugin` für MiniRedir/WebDAVFS/OneNote (`ServerFactory.php:122-130`) | bestätigt | `nextcloud/server` master `:125-129` | – |
| 181 | 19.13 | übrige Nextcloud-Aussagen (`files_lock`, `File.php`, Versionen) | nicht erneut | – | – |
| 182 | 19.14 | Samba 4.23.2 auf Tower | bestätigt | `smbd -V` | – |
| 183 | 19.14 | `pyfuse3` 3.5.0 (06/2026), `mfusepy` 3.1.1 | bestätigt | PyPI 2026-06-22 / 2026-03-13 | – |
| 184 | 19.14 | rclone/WinFsp, NFS, S3, impacket, Cloud Files API | nicht prüfbar | Fremdsoftware/Windows | – |
| 185 | 19.15 | Samba-Module `full_audit`, `recycle` auf Tower | bestätigt | `/usr/lib64/vfs/full_audit.so`, `recycle.so` | – |
| 186 | 19.15 | Ereignisverlust 17 %, Überlauf-Erkennung, stille Verluste bei zwei Schreibern | nicht erneut | Messungen im DB-Vorrang-Konzept | – |
| 187 | 19.16 | JSON-2-Route: `auth='bearer'`, `type='json2'`, `save_session=False`, `readonly` | bestätigt | `rpc/controllers/json2.py:49-55` | – |
| 188 | 19.16 | aufrufbar ist jede öffentliche Methode (Regeln von `get_public_method`) | bestätigt | `service/model.py:45-70` | A2 |
| 189 | 19.16 | `/xmlrpc`, `/jsonrpc` veraltet, Entfernung Odoo 22 | bestätigt | `rpc/controllers/__init__.py:6-8` | – |
| 190 | 19.16 | im Repo nutzt sie niemand | bestätigt | `grep xmlrpc\|/jsonrpc` (ohne `docs/`) leer | – |
| 191 | 19.16 | Schlüssel: `scope IS NULL OR scope = …` | bestätigt | `res_users.py:1741` | – |
| 192 | 19.16 | dauerhafte Schlüssel nur Admin/sudo | bestätigt | `res_users.py:1580-1582` (`is_system()`) | – |
| 193 | 19.16 | Doku empfiehlt `X-Odoo-Database` und `User-Agent` | bestätigt | `odoo/documentation` 19.0 `external_api.rst:36-37` | – |
| 194 | 19.16 | JSON-2 nur JSON, Binärdaten nur base64 | bestätigt | `type='json2'`; Binary-Felder base64 | – |

---

## C. Abgleich Image (19.0-20260817) gegen GitHub 19.0 (2026-09-26)

28 zitierte Dateien verglichen. **Unverändert:** `service/model.py`, `cli/command.py`, `cli/shell.py`,
`orm/table_objects.py`, `orm/decorators.py`, `modules/module.py`, `modules/neutralize.py`, `ir_attachment.py`,
`ir_rule.py`, `ir_cron.py`, `ir_http.py`, `rpc/controllers/json2.py` und `__init__.py`, `bus/models/bus.py`,
`mail_activity.py`, `web/controllers/dataset.py`.

**Geändert, ohne Einfluss auf die geprüften Aussagen** (Zeilen verschieben sich um wenige Stellen): `http.py`
(Debug-Modus, Pfadnormalisierung statischer Dateien), `service/server.py` (Websocket-Header, `while True`),
`service/db.py` (Neutralisieren vor dem Sichtbarwerden für Cron-Worker), `tools/image.py` (GIF-Animationen),
`sql_db.py`, `_monkeypatches/site.py`, `tools/config.py`, `orm/fields_numeric.py`, `bus/websocket.py`,
`ir_binary.py` (Download-Name nur bei Feldrecht).

**Relevant:** `orm/models.py` +1331-1343 – **Sicherheits-Fix**: bei `create`/`write` werden Relations-Befehle
`DELETE`/`UPDATE` (und bei One2many `UNLINK`/`LINK`) gegen die Rechte des Zielmodells geprüft; `res_users.py` +1588
(Ablaufdatum in der Vergangenheit abgelehnt). Beides fehlt im Tower-Image → A5.

---

## D. Nicht prüfbar – Gründe

| Grund | Nr. |
|---|---|
| Messung aus Abschnitt 19; erneuter Lauf braucht die gestoppte Test-Instanz bzw. Windows-Client | 41, 60, 88, 102, 105, 112–115, 119, 122, 125, 130, 132–134, 144, 145, 148, 153, 163, 172, 178, 181, 186 |
| Windows-/Microsoft-/Browser-Verhalten (kein Windows-Test in dieser Prüfung) | 15, 70, 71, 101, 131, 184 |
| Live-DB/Live-Share bewusst nicht angefasst | 65, 110 |
| keine en_US-Test-DB vorhanden | 29 |
| kein Prototyp | 72 |
| keine Code-Quelle (Markt-/Doku-Recherche) | 156 |

---

## E. Zählung

- **194 Behauptungen** inventarisiert (Abschnitte 1–19, Tabelle B, lückenlos nummeriert).
- **Geprüft: 158**
  - **bestätigt: 131**, davon 11 nur über Prototyp-Code, Mechanismus oder Testkonfiguration
    (Nr. 37, 39, 53, 58, 79, 86, 116, 117, 118, 120, 149), nicht über einen erneuten Lauf
  - **ungenau: 25**
  - **widerlegt: 2** (Nr. 94 Rechte-Vererbung → A1; Nr. 152 "Unique-Index + Retry" → A3)
- **Nicht prüfbar: 36** – 25 Messungen "nicht erneut", 11 ohne Prüfmöglichkeit (Gründe in D).
- Zusätzlich **21 Lücken und Widersprüche** (A1–A21): 4 hoch, 7 mittel, 10 niedrig.
