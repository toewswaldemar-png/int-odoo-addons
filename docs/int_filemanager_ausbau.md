# int_filemanager-Ausbau: Status & Plan

## Status (Stand 2026-09-02, aktualisiert nach Phase 5 - Plan vollständig umgesetzt)

**Umgesetzt** (`master`): Phase 1–5, der gesamte unten stehende Plan. Phase 1–3 committet in `74bd050`, Phase 4 in `78d23cc`, Phase 5 folgt in einem eigenen Commit (siehe Ist-Stand-Abschnitt bei Phase 5 unten für Abweichungen vom ursprünglichen Plan).

| Phase | Inhalt | Code | Tests |
|---|---|---|---|
| 1 | Scan-Identität (Hash-basierte Rename-Erkennung) | ✅ | ✅ 16 Tests |
| 2 | Feingranulare Rechte (ACL) + Authorization-Service | ✅ | ✅ 11 Tests |
| 3 | Versionierung (Snapshot, atomarer Schreibvorgang, Journal) | ✅ | ✅ 10 Tests |
| 4 | Vorschau & Metadaten | ✅ | ✅ 11 Tests |
| 5 | Freigaben (intern/extern) | ✅ | ✅ 18 Tests |

**Getestet wie:** alle 66 Tests (`TransactionCase` + `HttpCase`) liefen echt gegen eine Wegwerf-Odoo-19-Instanz auf HM-SRV (eigene Test-DB `int_filemanager_test`, eigenes Docker-Image mit `pyjwt` + `mutagen==1.47.0` nachinstalliert, danach vollständig entfernt — DB gedroppt, Image entfernt, Temp-Verzeichnisse gelöscht, Produktiv-Container `odoo`/`odoo_db` zu keinem Zeitpunkt berührt). 0 failed, 0 error(s) of 66 tests. Der erste Testlauf von Phase 5 fand dabei zwei echte Bugs (fehlendes `@api.depends` auf `share_url`, fehlender `id`-Tiebreaker in `share_log`s Sortierung bei gleichem `create_date`) - beide durch die Tests aufgedeckt, nicht durch Code-Review.

**Korrektur (2026-09-08, per direkter DB-Abfrage auf `unraid`/192.168.188.67 verifiziert):** Der Rollout auf die Produktivinstanz **ist bereits passiert** — vermutlich beim "Deploy auf Unraid"-Sync vom 2026-09-04 (siehe [docs/int_filemanager_native_ui.md](int_filemanager_native_ui.md)), aber nie an dieser Stelle nachgetragen. `int_filemanager` läuft dort produktiv als **Version 19.0.1.5.0** (`ir_module_module.state = installed`, DB `odoo`, 427.913 Zeilen in `int_filemanager_file`), `hm_filemanager` ist deinstalliert. Der untenstehende Absatz "Kein Rollout" war bis heute falsch und ist hiermit richtiggestellt.

**Trotzdem noch offen:**
- **Produktivstand ist veraltet:** 19.0.1.5.0 läuft, das Repo steht aktuell bei `19.0.1.6.0` (`experiment/native-listview`) — u. a. mit dem neuen `watcher_enabled`-Kill-Switch, der damit noch NICHT in Produktion aktiv ist.
- **Dependency-Lücke in Produktion, real und aktiv (nicht nur ein Vor-Rollout-Checklistenpunkt):** `/mnt/user/appdata/odoo/Dockerfile` installiert bislang nur `pyjwt` — `mutagen`, `tesseract-ocr`/`poppler-utils`, `pytesseract`, `pdf2image` fehlen. Das bereits laufende 19.0.1.5.0 nutzt aber schon Audio-Metadaten (mutagen) und Volltext-OCR (tesseract/pytesseract/pdf2image) — diese Funktionen dürften in der aktuellen Produktivinstanz daher schon jetzt fehlschlagen, nicht erst bei einem künftigen Update.
- Bei einem künftigen Upgrade einer bereits laufenden Installation (nicht bei einer Erstinstallation) muss `rebuild_rules` einmalig manuell angestoßen werden - `post_init_hook` feuert laut Odoo-Quellcode nur bei `update_operation == 'install'`, nicht bei `'upgrade'` (siehe Phase-5-Ist-Stand unten). Da 19.0.1.5.0 schon installiert ist, wäre der nächste Deploy-Schritt ein **Upgrade**, kein Neu-Install — dieser Punkt ist also jetzt relevant, nicht mehr nur theoretisch.

**Wie weiterarbeiten:** Nächster Schritt ist ein reguläres Modul-Upgrade (19.0.1.5.0 → 1.6.0) auf der bereits laufenden Produktivinstanz, kein Erstinstall. Der `watcher_enabled`-Kill-Switch ist implementiert und gegen eine Wegwerf-Instanz mit vollem Testlauf verifiziert (69 Tests, 0 failed/0 error, 2026-09-08) - vor dem eigentlichen Deploy zusätzlich das Dockerfile-mutagen/tesseract-Gap schließen und `rebuild_rules` nach dem Upgrade manuell anstoßen (siehe oben).

---

<!-- Ab hier: vollständiger, freigegebener Plan (Stand nach Review-Runde 4) -->

## Context

Auf HM-SRV läuft produktiv das Odoo-Addon `int_filemanager` (Verzeichnis auf der Platte als Quelle der Wahrheit, Indexierung + Live-Watcher). Ziel: `int_filemanager` direkt ausbauen, Odoos eigene Stärken nutzen statt sie neu zu bauen.

Dieser Plan hat **vier** Review-Runden durchlaufen, Runden 2–4 jeweils direkt gegen den echten Odoo-19-Quellcode geprüft (der auf HM-SRV laufende Code, nicht nur die generische GitHub-Quelle). Jede Runde fand weitere, empirisch bestätigte Blocker. Diese vierte Fassung behebt:
- Rundе 4: `domain_force`-Validierungslücke bei phasenübergreifenden Feldreferenzen, fehlende Multi-Kontext-Validierung des Regel-Generators, unentschiedene Semantik verschachtelter Schutzordner, ein Nebenläufigkeitsloch in der Versionssperre (Lock endet vor dem eigentlichen Schreiben), ein zu armes Journal-Modell für echtes Recovery, plus mehrere hohe Risiken (Hash-Race, leere-Ordner-Fehl-Merge, SQL-Wildcard-Escaping, fehlende Portal-Leserechte auf Modellebene, nicht-atomare Schutzordner-Umbenennung) und Detailkorrekturen (Dockerfile-USER-Wechsel, Tempfile-Widerspruch, Audit-Log-Überleben bei Löschung, unentschiedenes Großdatei-Verhalten bei Versionierung).

**Empirisch geprüft, Runde 4 (HM-SRV, laufender `Odoo19`-Container):**
- `ir_rule.py` `_check_domain()`: validiert `domain_force` durch Auswertung mit `self.env.user` = dem **gerade aktiven** Nutzer (typischerweise der Installateur/Admin) und prüft nur das **Ergebnis** dieses einen Kontexts. Ein Python-Ternary-Ausdruck wertet den nicht gewählten Zweig gar nicht erst aus — verweist dieser Zweig auf ein zum Installationszeitpunkt noch nicht existierendes Feld (`shared_partner_ids`, das erst in Phase 5 angelegt wird), schlägt die Constraint-Prüfung **nicht** fehl, solange als Admin installiert wird. Der Fehler tritt erst live auf, wenn ein Portal-Nutzer tatsächlich diesen Zweig durchläuft.
- `safe_eval.py` `_BUILTINS`: enthält u. a. `'set': set` und `'bool': bool` — beides in `domain_force`-Ausdrücken technisch nutzbar, bestätigt.
- `docker inspect odoo:latest --format '{{.Config.User}}'` → `odoo` (bestätigt durch `docker exec Odoo19 id` → `uid=100(odoo)`). Das offizielle Image läuft **nicht** als root — ein `RUN pip install ...` direkt nach `FROM odoo@sha256:...` ohne expliziten `USER root`-Wechsel schlägt mangels Schreibrechten auf die System-Packages fehl oder installiert unbrauchbar.
- Aus Runde 3 weiterhin gültig: `user.all_group_ids` (nicht `groups_id`), `ir.rule._compute_domain()`-Kombinationslogik, `portal_mixin`-Token als bewusster Rechte-Umgehungsmechanismus, `public=True` liefert ohne Token, `fields.Binary` erwartet Base64, `ir_cron` `SKIP LOCKED` + `_commit_progress()`.
- `/mnt/hm-daten` ist `shfs` (Unraid-FUSE), Postgres 17, `portal`-Modul installiert, Pillow/PyPDF2 vorhanden, `mutagen` fehlt, Image-Digest `sha256:f99ffac95cb39a0924622ea4118481c95651d9c84187e5b30a21c2cc4419c7dd` (Build `19.0-20260817`).
- `_path_uniq`/`_name_uniq` (`models.Constraint`) und `watcher.py`s `_run()`-Helfer (frischer Cursor/Env je Event) sind die etablierten Muster dieses Moduls, weiterhin wiederverwendet.

## Reihenfolge

1. Scan-Identität
2. Feingranulare Rechte + zentraler Authorization-Service (ohne Portal-Zweig — der kommt in Phase 5)
3. Versionierung (Journal + Session-Lock über den gesamten Schreibvorgang)
4. Vorschau & Metadaten
5. Freigaben (erweitert die Read-Regel aus Phase 2 um den Portal-Zweig, jetzt mit existierendem `shared_partner_ids`-Feld)

---

## Phase 1 — Scan-Identität ✅ umgesetzt

Persistierter SHA-256 statt Größenraten, Hash wird laufend gepflegt (nicht erst beim Kalt-Scan berechnet), asynchroner Backfill — Grundverfahren aus Runde 3 bestätigt tragfähig, hier um zwei in Runde 4 gefundene Lücken ergänzt.

**Hash-Race gegen parallele Änderungen (Runde 4):** ein Hash, der während ein anderer Prozess gerade in dieselbe Datei schreibt, kann einen Mischzustand einfangen, der nie tatsächlich auf der Platte existierte. Korrigiertes Verfahren, sowohl für den laufenden Hash-Cron als auch für den Kalt-Scan-Direkthash neuer Dateien:
1. `stat()` vor dem Lesen (Größe, `mtime_ns`).
2. Datei blockweise hashen.
3. `stat()` erneut nach dem Lesen.
4. Hash **nur** speichern, wenn Größe und `mtime_ns` vor und nach dem Lesen identisch sind (Inode zusätzlich, wo verfügbar) — sonst `hash_state` auf `pending` belassen, im nächsten Lauf erneut versuchen.

**Hash-Budget pro Kalt-Scan (Runde 4):** "nur wenige Kandidaten" ist keine garantierte Eigenschaft — eine große, neu aufgetauchte Datei könnte den Scan sonst lange blockieren. Der Scan begrenzt das Gesamt-Hashbudget pro Lauf (konfigurierbar, z. B. maximale Gesamt-Bytes oder Kandidatenzahl); Kandidaten über dem Budget bleiben unangetastet `pending` und werden konservativ **nicht** in diesem Lauf gemergt (heutiges Verhalten für sie), sondern beim nächsten Lauf erneut versucht.

**Leere Ordner nicht mergen (Runde 4):** die vorherige Regel "genau ein stale/neues Ordnerpaar mit übereinstimmenden Kindern" würde zwei leere Ordner fälschlich als identisch behandeln — beide haben dieselbe (leere) Kindmenge, das ist kein Identitätsbeweis. Korrigiert: ein Ordner-Merge verlangt **mindestens ein eindeutig über Inhalt bestätigtes gemeinsames Kind** (Datei mit bestätigtem Hash-Match, oder rekursiv ein bereits bestätigtes Unterordner-Merge). Ohne mindestens ein bestätigtes Kind: kein Merge, unabhängig davon, wie eindeutig die Ordner-Paarung sonst erscheint.

- Felder: `content_sha256`, `hash_size`, `hash_source_mtime_ns` (Char, verlustfrei), `hash_state` (`pending`/`running`/`done`/`error`).
- Watcher setzt bei jedem `CREATE`/`MODIFY` unbedingt `pending`; asynchroner Batch-Cron (`_commit_progress()`) berechnet, mit obigem Stat-vor/nach-Schutz.
- Backfill für Bestandsdaten gedrosselt/fortsetzbar über dieselbe Queue.
- Merge-Kriterium: `size` gleich, `content_sha256` gleich, eindeutig, Kandidat `hash_state='done'`. Mehrdeutigkeit/fehlender Hash/Budget-Überschreitung → kein Merge, heutiges Verhalten.
- Audit-Log `int_filemanager.scan_log` (`merged`/`ambiguous`/`rejected`), Retention-Cron.

**Dateien:** [models/filemanager_file.py](../int_filemanager/models/filemanager_file.py), neu `models/filemanager_scan_log.py`, [watcher.py](../int_filemanager/watcher.py), [index_utils.py](../int_filemanager/index_utils.py), geteilte Hash-Cron-Infrastruktur (mit Phase 4 geteilt).

**Tests:** wie Runde 3, plus: Hash-Berechnung während simulierter Parallelschreibung → verworfen, nicht gespeichert; Kalt-Scan mit einer Datei über dem Hash-Budget → bleibt unangetastet, kein Merge in diesem Lauf; zwei leere, unterschiedlich benannte leere Ordner ohne gemeinsames Kind → kein Merge.

**Umsetzung (Ist-Stand):** genau wie geplant, plus zwei zusätzliche, beim Testen gefundene Korrekturen: (1) gruppenbasierter statt sequentieller Größe/Hash-Abgleich (verhindert einen order-abhängigen Fehl-Merge bei identischem Inhalt an mehreren neuen Orten), (2) `scan_run_id` (UUID pro Lauf) statt Zeitstempelvergleich für die Stale-Erkennung — `last_seen < scan_started` erkennt nichts als stale, wenn zwei Scans innerhalb derselben Sekunde laufen (Odoo-`Datetime` ist nur sekundengenau).

---

## Phase 2 — Feingranulare Rechte (ACL) + zentraler Authorization-Service ✅ umgesetzt

Grundarchitektur aus Runde 3 bestätigt (drei getrennte globale Read/Write/Unlink-Regeln statt gemeinsamer Gruppenmenge, `user.all_group_ids`, generierter statt gespeicherter Schutz, `tree_dir` über ORM). Runde 4 fand vier weitere Lücken in genau diesem Kern.

**1. Phasenübergreifende Feldreferenz behoben:** die Read-Regel referenzierte `shared_partner_ids`, das erst in Phase 5 angelegt wird — bei Installation als Admin schlägt die Constraint-Prüfung dank Ternary-Kurzschluss **nicht** fehl (siehe Context), der Fehler träte live und verzögert bei echten Portal-Nutzern auf. **Entschieden (Reviewer-Empfehlung, hält Phasen sauber):** Phase 2 installiert die drei globalen Regeln **ohne** Portal-Zweig (nur Admin-Bypass + interner Zweig). Phase 5 erweitert `domain_force` der Read-Regel erst dann um den Portal-Zweig, wenn `shared_partner_ids` bereits existiert.

**2. Domain-Generator sauber komponiert statt handformatierter String (Runde 4):** `set()`/`bool()` sind zwar technisch in `safe_eval` erlaubt (bestätigt), trotzdem baut `acl_rules.py` die Domain-Struktur intern über `odoo.fields.Domain`-Objekte (`Domain.AND(...)`, `Domain.OR(...)`) zusammen, statt Teilstrings manuell zu verketten — nur das fertig komponierte Ergebnis wird serialisiert. **Nach jeder Regenerierung** läuft ein Selbsttest über mindestens diese Kontexte, bevor die neue `domain_force` committet wird (bei Fehlschlag: alte Fassung behalten, Fehler loggen, nicht scharf schalten):
  - Admin,
  - interner Nutzer ohne jede Schutzgruppe,
  - je Schutzordner ein Nutzer mit Lese-, mit Schreib-, mit Unlink-Gruppe,
  - Portal-Nutzer (ab Phase 5),
  - anonymer/Public-Nutzer.

  Für jeden Kontext: `safe_eval()` + `Domain(...).validate(model)`, zusätzlich eine echte `search()` gegen eine kleine Fixture-Menge bekannter Testpfade, deren erwartetes Ergebnis bekannt ist — Odoos eigener Constraint prüft wegen der nutzerabhängigen Zweige eben **nicht** automatisch alle Varianten (Runde-4-Fund), das muss der Generator selbst leisten.

**3. Semantik verschachtelter Schutzordner explizit entschieden (Runde 4):** bei `Buchhaltung` (Gruppe A) und `Buchhaltung/Gehaltsdaten` (Gruppe B) ergab die ursprüngliche AND-Verknüpfung aller Vorfahren-Implikationen fälschlich "Gruppe A **und** Gruppe B nötig". **Entschieden: Override-Semantik — der spezifischste (tiefste) Schutzordner-Eintrag gewinnt vollständig**, konsistent mit dem "genauester Pfad gewinnt"-Prinzip, das auch bei der ACL-Recherche zu web-filemanager als Referenzmuster diente. Der Generator bildet für jeden Schutzordner-Eintrag disjunkte Pfadbereiche: die Klausel von `Buchhaltung` gilt für `Buchhaltung/%` **abzüglich** des Bereichs jedes tieferen Schutzordner-Eintrags (`Buchhaltung/Gehaltsdaten` und dessen `%`-Unterbaum) — wer nur in Gruppe A ist, sieht `Buchhaltung/Sonstiges/...` aber nicht `Buchhaltung/Gehaltsdaten/...`; wer nur in Gruppe B ist, sieht ausschließlich `Buchhaltung/Gehaltsdaten/...`, nicht den Rest von `Buchhaltung`.

**4. SQL-Wildcards in Pfadnamen maskiert (Runde 4):** `%` und `_` haben in `LIKE`/`=like`-Domains SQL-Wildcard-Bedeutung — ein Ordner namens `Plan_2026` würde ungeschützt zusätzliche Pfade treffen (`_` matcht ein beliebiges Zeichen). Der Generator maskiert `%`, `_` und das Escape-Zeichen selbst beim Aufbau jeder `LIKE`-Klausel; ein eigener Test legt genau einen Schutzordner mit `_`/`%` im Namen an und prüft, dass nur exakt dieser Pfad (und seine echten Unterpfade) getroffen wird.

**Bestehendes Grundmodell (unverändert aus Runde 3):**
- `int_filemanager.protected_folder`: `path` (unique, Wurzel nicht erlaubt), `read_group_ids`/`write_group_ids`/`unlink_group_ids`.
- Drei strukturelle, per XML-Data angelegte globale `ir.rule`-Datensätze (Read/Write/Unlink, je `perm_read`/`perm_write`/`perm_unlink`), deren `domain_force`-**Inhalt** `acl_rules.py` bei jeder Änderung an `protected_folder` neu generiert (jetzt: über `Domain`-Objekte, mit Override-Semantik, maskierten Pfaden, Multi-Kontext-Selbsttest — siehe oben) statt ihn wie in Runde 2 vermutet direkt in einer denormalisierten Many2many-Spalte auf `int_filemanager.file` zu pflegen.
- Kein `create`-Regel nötig (Anlage läuft immer über `.sudo()` im Watcher/Scan-Pfad, echter Torwächter ist `authz.require(zielordner, "write")`).
- Zentraler `authz.py`, Route-Matrix (`tree_dir` über nicht-sudo ORM-Query statt `os.scandir`, `delete` mit Vollständigkeitscheck über den Unterbaum, `move` mit Prüfung auf Quelle **und** Ziel), Rename/Move über eine Schutzgrenze hinweg nur mit Admin-Gruppe.
- Pfad-Robustheit: `..`/Symlinks bereits durch `realpath` abgedeckt (bestätigt), Unicode-NFC-Normalisierung ergänzt.

**Dateien:** [models/filemanager_protected_folder.py](../int_filemanager/models/filemanager_protected_folder.py), [acl_rules.py](../int_filemanager/acl_rules.py) (`Domain`-Komposition, Override-Berechnung, Escaping, Multi-Kontext-Selbsttest), [authz.py](../int_filemanager/authz.py), `security/security.xml` (Admin-Gruppe, drei Platzhalter-`ir.rule`, **ohne** Portal-Zweig), `security/ir.model.access.csv`, [views/filemanager_protected_folder_views.xml](../int_filemanager/views/filemanager_protected_folder_views.xml), [controllers/main.py](../int_filemanager/controllers/main.py), [path_utils.py](../int_filemanager/path_utils.py).

**Tests:** wie Runde 3, plus: Regel-Selbsttest schlägt bei einem absichtlich kaputten `domain_force`-Kandidaten fehl und verhindert das Scharfschalten; verschachtelte Schutzordner → Override statt Kumulation, mit genau den oben beschriebenen Erwartungen; Schutzordner-Name mit `_`/`%` → nur exakter Pfad betroffen.

**Umsetzung (Ist-Stand):** genau wie geplant. `acl_rules.py` wurde in Phase 3 generalisiert, um zusätzlich `int_filemanager.version` abzudecken (`path_field="file_id.path"`, dieselbe Generator-Logik wiederverwendet statt dupliziert).

---

## Phase 3 — Versionierung ✅ umgesetzt

**Nebenläufigkeitsloch behoben (Runde 4 — härtester Fund dieser Runde):** der bisherige Ablauf (kurze committete Transaktion mit `pg_advisory_xact_lock`, danach erst Tempfile+`os.replace()`) gibt die Sperre frei, **bevor** der eigentliche Schreibvorgang beginnt — zwei gleichzeitige Speicherungen können beide denselben "alten Inhalt" sichern, dann nacheinander schreiben, wobei die zweite die erste stillschweigend überschreibt, ohne dass eine Version den Zwischenstand der ersten je enthielte.

**Korrigiert — Session-Lock über den gesamten kritischen Bereich:** der zentrale Snapshot-/Schreibdienst öffnet für die Dauer des **gesamten** Ablaufs eine **eigene, dedizierte DB-Verbindung** und hält darauf `pg_advisory_lock(file_id)` als **Session**-Lock (nicht transaktionsgebunden) in einem `try`/`finally`:
1. Session-Lock erwerben (dedizierte Verbindung).
2. Alten Inhalt als Version sichern (eigene kurze Transaktion, committet, Lock bleibt weiterhin gehalten — er hängt an der dedizierten Verbindung, nicht an dieser Transaktion).
3. Temporärdatei schreiben, `flush()` + `fsync()`.
4. `os.replace()`.
5. Hauptindex aktualisieren.
6. Journal abschließen.
7. **`finally`:** `pg_advisory_unlock(file_id)` auf derselben dedizierten Verbindung, unabhängig davon, ob Schritt 2–6 erfolgreich waren.

Damit ist der gesamte Ablauf für dieselbe Datei serialisiert — eine zweite gleichzeitige Speicherung wartet vor Schritt 1, bis die erste bei Schritt 7 fertig ist. Alternative (nicht gewählt, aber dokumentiert): ein prozessweiter Dateisystem-Lock, den alle Schreibpfade (Controller, ONLYOFFICE-Sync, Watcher) konsequent verwenden müssten — der Session-Advisory-Lock ist einfacher, da er nicht von jedem Aufrufer diszipliniert eingehalten werden muss, sondern zentral im Dienst selbst sitzt.

**Journal um Recovery-fähige Information erweitert (Runde 4):** `file_id`, `state` und `started_at` allein sagen einem Recovery-Cron nicht, **wo genau** ein abgebrochener Vorgang stehengeblieben ist. Erweitert um: `operation` (Selection), `stage` (Selection `created`/`snapshot_committed`/`temp_synced`/`replaced`/`done`/`failed`), `version_id`, `old_sha256`, `new_sha256`, `temp_path`, `finished_at`, `error`. Der Recovery-Cron vergleicht bei einem hängengebliebenen Eintrag den tatsächlichen Plattenzustand gegen `stage` und kann daraus ableiten, ob der Vorgang sicher fortgesetzt, zurückgerollt oder nur zur manuellen Prüfung markiert werden muss.

**Großdatei-Verhalten explizit entschieden (Runde 4):** für Dateien über `version_max_size_mb` (Default 200) galt bisher unentschieden "wird nicht automatisch versioniert". **Entschieden: Überschreiben wird abgelehnt**, nicht stillschweigend ohne Version durchgeführt — insbesondere für den ONLYOFFICE-Sync-Pfad, wo kein sinnvoller Bestätigungsdialog für "ohne Sicherung überschreiben" existiert.

**Tempfile-Verhalten präzisiert (Runde 4, war widersprüchlich):** in `finally` wird die Temporärdatei bei **jedem regulär behandelbaren Fehler** entfernt. Nur ein harter Prozessabsturz kann sie zurücklassen — dafür ist der Recovery-Cron die zweite Verteidigungslinie.

**Weiterhin aus Runde 3 gültig:** `UNIQUE(file_id, version_no)`-Constraint als harte letzte Absicherung, Base64 explizit, `size` explizit gesetzt, Restore nur über `version_id` (kein frei wählbarer Zielpfad), eigene Rechte für `int_filemanager.version`, Dedup über `ir.attachment` bestätigt.

**Schutzkonfiguration und Dateisystem ebenfalls nicht atomar (Runde 4, betrifft Phase 2s Admin-Rename eines Schutzordners):** PostgreSQL und `os.rename()`/`shutil.move()` teilen keine Transaktion. **Noch offen** — dieser konkrete Journal-Einsatz für Schutzordner-Umbenennung ist bislang nicht implementiert; `authz.require_rename_or_move_allowed()` verweigert das Umbenennen/Verschieben eines registrierten Schutzordners aktuell komplett (auch für Admins), statt es atomar nachzuziehen. Sicher, aber einschränkend — bei Bedarf nachziehen.

**Dateien:** [models/filemanager_version.py](../int_filemanager/models/filemanager_version.py), [models/filemanager_write_journal.py](../int_filemanager/models/filemanager_write_journal.py), [write_service.py](../int_filemanager/write_service.py), [models/ir_attachment.py](../int_filemanager/models/ir_attachment.py), [controllers/main.py](../int_filemanager/controllers/main.py), `security/ir.model.access.csv`, `security/security.xml`, `data/ir_cron.xml` (Pruning, Recovery).

**Tests:** zwei echte simultane Schreibvorgänge (separate DB-Verbindungen/Threads) auf dieselbe Datei → der Session-Lock serialisiert sie tatsächlich, keine verlorene Zwischenversion; Überschreiben einer Datei über der Größengrenze → abgelehnt mit klarer Fehlermeldung.

**Umsetzung (Ist-Stand):**
- Kein `index_updated`-Stage im Journal (anders als ursprünglich geplant): `write_service.py` ruft bewusst **kein** `index_upsert()` nach dem Schreiben auf — der bestehende Watcher beobachtet den Schreibvorgang per inotify ohnehin und aktualisiert den Index selbst; ein zusätzlicher direkter Aufruf hier würde exakt das Race auslösen, das im bestehenden Code-Kommentar in `ir_attachment.py` bereits dokumentiert war (überlappende Transaktionen auf dieselbe Zeile, von Postgres abgelehnt). Journal-Stages entsprechend reduziert auf: `created`/`snapshot_committed`/`temp_synced`/`replaced`/`done`/`failed`.
- Kein UI-Teil umgesetzt (`static/src/int_filemanager/preview_action.js`/`.xml` "Versionen (n)"-Button, `views/filemanager_version_views.xml`) — bewusst zurückgestellt zugunsten von Backend-Testtiefe. Die Routen `/int_filemanager/versions` (Auflisten) und `/int_filemanager/version_restore` existieren bereits und sind vollständig getestet, nur ohne Oberfläche.
- **Wichtiger Test-Infrastruktur-Fund:** ein echter Zwei-Thread-Concurrency-Test über zwei parallele `url_open()`-HTTP-Requests scheitert an Odoos eigenem `HttpCase`-internen `allow_requests()`-Kontextmanager, der Test-Requests serialisiert — kein Fehler im eigenen Code. Die Sperre wird stattdessen isoliert direkt getestet (`write_service._file_write_lock` mit zwei echten Threads/DB-Verbindungen, willkürlicher Lock-Key statt echtem `file_id` nötig, weil `write_service` eigene, von der Testtransaktion unabhängige Verbindungen nutzt und daher committete Daten braucht).

---

## Phase 4 — Vorschau & Metadaten ✅ umgesetzt

Grundverfahren aus Runde 3 bestätigt tragfähig (Zustand statt Flag, asynchrone Extraktion, `_commit_progress()`, Pillow/PyPDF2/mutagen, `fields.Image`). Runde 4 präzisiert nur die UI-Behandlung veralteter Werte.

**Veraltete Werte sichtbar kennzeichnen (Runde 4):** "alte Werte bei `pending` weiter anzeigen" bleibt richtig, muss aber in der UI **sichtbar als veraltet/„wird aktualisiert"** markiert werden, nicht kommentarlos wie aktuell dargestellt. Bei `meta_state='error'` macht die UI zusätzlich deutlich, dass angezeigte Werte vom vorherigen (möglicherweise nicht mehr zutreffenden) Inhalt stammen können.

- Felder: `meta_source_mtime_ns` (verlustfrei, gleiches Muster wie Phase 1s Hash-Feld), `meta_source_size`, `meta_state`, `meta_error`, `meta_attempts`.
- Watcher setzt bei jedem `MODIFY` unbedingt `pending`; Extraktion ausschließlich im Batch-Cron (`_commit_progress()`).
- Bilder: Pillow, Thumbnail als `fields.Image(max_width=320, max_height=320, attachment=True)`, Wert Base64-kodiert gesetzt. PDF: `odoo.tools.pdf.PdfReader`. Audio: `mutagen==1.47.0`. Video: nicht in v1.
- Ressourcengrenzen je Medientyp über `ir.config_parameter`; `taken_at` naiv (Kamera-Lokalzeit, keine Zeitzonenumrechnung).

**Dockerfile korrigiert (Runde 4, am Image bestätigt):** das offizielle Image trägt `USER odoo` — ein `RUN pip install` direkt danach scheitert an fehlenden Schreibrechten.
```dockerfile
FROM odoo@sha256:f99ffac95cb39a0924622ea4118481c95651d9c84187e5b30a21c2cc4419c7dd

USER root
RUN pip install --no-cache-dir mutagen==1.47.0
USER odoo
```
Wird im Pre-Flight (siehe Verifikation) gebaut und getestet, bevor er auf HM-SRV verwendet wird. **Noch nicht angelegt.**

**Dateien:** neu `mediameta.py`, [models/filemanager_file.py](../int_filemanager/models/filemanager_file.py), [watcher.py](../int_filemanager/watcher.py), [index_utils.py](../int_filemanager/index_utils.py), `data/ir_cron.xml`, `static/src/int_filemanager/preview_action.js`/`.xml` (Veraltet-Kennzeichnung), neu `Dockerfile`.

**Tests:** `pending`-Zustand zeigt in der UI sichtbar "wird aktualisiert" statt kommentarlos alte Werte; Dockerfile-Build + `mutagen`-Import-Test im Pre-Flight.

**Umsetzung (Ist-Stand):** Kernverfahren wie geplant (Zustand statt Flag, asynchrone Extraktion im Batch-Cron, `_commit_progress()`, Stat-vor/nach-Schutz analog Phase 1s Hash-Race-Fix), mit folgenden beim Bauen getroffenen/präzisierten Entscheidungen:

- **PDF ohne gerenderte Vorschau, nur Seitenzahl:** am echten Image bestätigt fehlen sowohl `poppler-utils` (`pdftoppm`/`pdftocairo`) als auch `PyMuPDF` (`fitz`) — beides wäre für ein gerendertes Thumbnail nötig. Statt das unentschieden zu lassen: PDF liefert in v1 nur `page_count` über `odoo.tools.pdf.PdfReader` (mit `strict=False`, da reale/gescannte PDFs oft eine leicht defekte xref-Tabelle haben und die Seitenzahl trotzdem zuverlässig ausgelesen werden soll). Ein gerendertes PDF-Thumbnail bliebe eine spätere, separate Entscheidung (zusätzliches Paket im Dockerfile).
- **Audio generisch über `mutagen.File(path, easy=True)`** statt einer Klasse pro Format — deckt mp3/wav/flac/ogg/m4a/aac/wma über dieselbe Extraktionsfunktion ab, liefert `audio_duration`/`audio_title`/`audio_artist`/`audio_album`.
- **`meta_state` ohne Feld-Default** (anders als `hash_state`): nur Dateien mit unterstützter Endung (`mediameta.media_type_of()`) durchlaufen überhaupt `pending`; Ordner und nicht unterstützte Typen bleiben `False` und werden vom Cron-Domain-Filter automatisch übersprungen — vermeidet ein sinnloses "pending" auf z.B. einer `.docx`.
- **Kein automatischer Retry nach Fehler:** anders als beim Hash-Cron (der bei `None` einfach `pending` belässt) setzt ein Extraktions-Fehler (defekte Datei, Format-Fehler) `meta_state='error'` mit `meta_error`-Text und zählt `meta_attempts` hoch — kein Endlos-Retry-Loop auf einer dauerhaft kaputten Datei. Erst eine erneute Watcher-`MODIFY` (echte Dateiänderung) setzt wieder auf `pending`. Nur eine transiente Bedingung (Datei ändert sich gerade während der Extraktion) bleibt `pending` für den nächsten Lauf.
- **Großdatei-Ablehnung analog Phase 3:** `int_filemanager.meta_max_bytes_<image|pdf|audio>` (Config-Parameter, Defaults 50/100/100 MB) — Überschreitung wird als `error` abgelehnt, nicht stillschweigend übersprungen.
- **Thumbnail-Auslieferung über eigene Route** (`/int_filemanager/thumbnail?path=...`), nicht als Base64 in der `/list`-JSON-Antwort eingebettet — bei 200 Zeilen pro Seite wäre das ein unnötig großer Payload; die Route liest den ACL-gefilterten Datensatz nicht-sudo (wie `/download`) und liefert nur bei `meta_state='done'` ein Bild.
- **UI:** Thumbnail-Spalte (24×24px, ersetzt das FontAwesome-Icon bei Bildern mit `meta_state='done'`), Refresh-Icon mit Tooltip bei `pending`/`running`, Warndreieck mit `meta_error` als Tooltip bei `error`, Info-Icon mit PDF-Seitenzahl bzw. Audio-Dauer/Titel/Interpret bei `done`. Keine eigene Detailansicht für Audio-Tags/Seitenzahl über das Tooltip hinaus — bewusst zurückgestellt, analog zur zurückgestellten Versionen-UI in Phase 3.
- **Dockerfile spiegelt das tatsächlich auf HM-SRV deployte** (`/mnt/user/appdata/odoo/Dockerfile`: `FROM odoo:19.0`, `USER root`, `pip3 install --break-system-packages`, `USER odoo`) statt der im ursprünglichen Plan skizzierten digest-gepinnten Variante — liegt jetzt im Repo (`Dockerfile`, Root-Ebene) mit `mutagen==1.47.0` ergänzt. Noch nicht auf das Produktiv-Dockerfile auf HM-SRV übertragen (Rollout weiterhin zurückgestellt).
- **Dateien:** neu [mediameta.py](../int_filemanager/mediameta.py), [models/filemanager_file.py](../int_filemanager/models/filemanager_file.py) (Felder + `_cron_extract_media_meta`), [index_utils.py](../int_filemanager/index_utils.py) (`meta_state` pending bei Watcher-Upsert), [controllers/main.py](../int_filemanager/controllers/main.py) (`/thumbnail`-Route, erweiterte `/list`-Antwort), `static/src/int_filemanager/filemanager_action.js`/`.xml`/`filemanager.scss`, `data/ir_cron.xml`, neu `Dockerfile` (Root-Ebene), neu [tests/test_media_meta.py](../int_filemanager/tests/test_media_meta.py) (11 Tests).

---

## Phase 5 — Freigaben (intern & extern) ✅ umgesetzt

**Portal-Zweig jetzt zeitlich korrekt eingeführt (Runde 4):** `shared_partner_ids` (Many2many `res.partner`) wird hier auf `int_filemanager.file` angelegt — **danach erst** erweitert `acl_rules.py` (derselbe Generator-Mechanismus wie in Phase 2, inkl. Multi-Kontext-Selbsttest) die bestehende Read-Regel um den Portal-Zweig:
```python
['|', ('shared_partner_ids','in',[user.partner_id.id]), (1,'=',2)] if user.has_group('base.group_portal') else <interner Zweig aus Phase 2>
```
Der Selbsttest aus Phase 2 läuft bei dieser Erweiterung erneut, jetzt inklusive des Portal-Kontexts (der in Phase 2 mangels Feld noch nicht sinnvoll testbar war).

**Portal braucht Lese-Modellrechte, nicht nur eine Record Rule (Runde 4):** `ir.model.access` ist — anders als `ir.rule` — **default-deny** pro Modell: ohne einen passenden CSV-Eintrag hat `base.group_portal` überhaupt keinen Zugriff auf `int_filemanager.file`, unabhängig von jeder Record Rule. Neuer Eintrag in `security/ir.model.access.csv`:
```
access_int_filemanager_file_portal,int_filemanager.file.portal,model_int_filemanager_file,base.group_portal,1,0,0,0
```
(`perm_read=1`, `perm_write=0`, `perm_create=0`, `perm_unlink=0` — die Record Rule aus Phase 2/5 schränkt danach zusätzlich ein, **welche** der grundsätzlich lesbaren Zeilen ein Portal-Nutzer tatsächlich sieht.)

**`public=True`-Fehler weiterhin behoben, `portal.mixin` weiterhin entfernt** (Runde 2/3 bestätigt, unverändert): eigenes `share_token`+`share_expires_at` auf `int_filemanager.file`, eigene Route `/int_filemanager/share/<token>` mit Live-Ablaufprüfung, frischer Inhalt von der Platte, einheitliche Fehlerantwort für unbekannt/abgelaufen/widerrufen, `Cache-Control: private, no-store`, erzwungener `Content-Disposition: attachment`.

**Audit-Log übersteht Löschung (Runde 4):** `int_filemanager.share_log.file_id` mit `ondelete='set null'` statt `cascade` (sonst verschwindet die Historie zusammen mit der gelöschten Datei) — zusätzlich `path`/`filename` als reiner Text-Snapshot zum Zeitpunkt des Ereignisses, damit der Log-Eintrag auch nach `file_id=NULL` noch lesbar bleibt. Kein Write-/Unlink-Modellrecht für normale Nutzer. Retention: unbegrenzt.

**Weiterhin aus Runde 3 gültig:** `write`-Capability für Erzeugen/Widerrufen/Partner-Zuordnen, Scope v1 nur Einzeldateien, Verhalten nach Rename/Delete ergibt sich automatisch aus Live-Auflösung, `authz.require(..., "read")` auch auf der Portal-Downloadaktion.

**Dateien:** [models/filemanager_file.py](../int_filemanager/models/filemanager_file.py) (`share_token`, `share_expires_at`, `shared_partner_ids`), neu `models/filemanager_share_log.py` (`ondelete='set null'`, Pfad-Snapshot), [acl_rules.py](../int_filemanager/acl_rules.py) (Portal-Zweig-Erweiterung), [controllers/main.py](../int_filemanager/controllers/main.py), `security/ir.model.access.csv` (Portal-Read-Zeile), `data/ir_cron.xml`, `static/src/int_filemanager/preview_action.js`/`.xml`, neue Portal-Template-XML.

**Tests:** Portal-Nutzer ohne den neuen `ir.model.access`-Eintrag → kein Zugriff, unabhängig von `shared_partner_ids` (bestätigt die Notwendigkeit der CSV-Zeile); gelöschte freigegebene Datei → Log-Eintrag bleibt mit Pfad-Snapshot lesbar, `file_id` ist `NULL`.

**Umsetzung (Ist-Stand):** Kernmechanismus wie geplant (zwei unabhängige Freigabewege: "intern" = `shared_partner_ids` über den Portal-Zweig der Read-Regel, "extern" = anonymer `share_token`-Link ganz ohne ir.rule), mit folgenden beim Bauen getroffenen Entscheidungen und einer beim ersten echten Testlauf gefundenen, zuvor nicht erkannten Sicherheitslücke:

- **Neu gefundene Lücke, behoben: `rebuild_rules()` lief bisher nur reaktiv.** Die ACL-Regelgenerierung aus Phase 2 wurde bislang ausschließlich bei einer Änderung an `protected_folder` angestoßen - beim Modul-Install/-Update selbst nie. Für Phase 2/3/4 war der in `security.xml` hinterlegte statische Platzhalter (`[(1,'=',1)]`, "alles offen") dabei unproblematisch, weil er exakt dem Verhalten vor Einführung der ACL entsprach (nur `group_filemanager_user`-Mitglieder hatten überhaupt Modellzugriff). Mit Phase 5s neuer `ir.model.access`-Zeile für `base.group_portal` wäre das nicht mehr harmlos: ein Portal-Nutzer hätte bis zur ersten `protected_folder`-Änderung nach dem Upgrade Lesezugriff auf **alle** Dateien statt nur die über `shared_partner_ids` freigegebenen - der neu gewährte Modellzugriff plus der noch nicht regenerierte, weiterhin "immer wahr" lautende Platzhalter hätten sich addiert. Behoben über einen neuen `post_init_hook` (`__init__.py`), der `rebuild_rules()` einmalig bei der Installation ausführt. **Bekannte Grenze:** Odoo ruft `post_init_hook` laut eigenem Quellcode (`odoo/modules/loading.py`) nur bei `update_operation == 'install'`, nicht bei `'upgrade'` - ein Upgrade einer bereits laufenden Installation braucht denselben Lauf einmal manuell (z.B. per Odoo-Shell: `env["int_filemanager.protected_folder"]._rebuild_acl_rules()`, oder eine beliebige `protected_folder`-Änderung/Resave). Für den Zeitpunkt des tatsächlichen Produktiv-Rollouts (ohnehin ein Neu-Install unter dem neuen Namen `int_filemanager`, kein Upgrade der alten `hm_filemanager`) ist das der ohnehin durchlaufene Pfad.
- **Portal-Zweig als eigener, vollständig getrennter Zweig** (nicht als Ergänzung des internen Zweigs): ein Portal-Nutzer sieht ausschließlich über `shared_partner_ids` freigegebene Dateien, nie zusätzlich etwas über Schutzordner-Gruppen (die für Portal-Kontakte ohnehin nie vergeben werden) - getestet in beide Richtungen (Portal-Nutzer ignoriert interne Gruppen, interner Nutzer ignoriert `shared_partner_ids`).
- **`share_expires_at` bewusst nicht frei editierbar** (readonly in der Formularansicht): nur "Link erzeugen/erneuern" setzt Token+Ablauf gemeinsam neu (Default-Gültigkeit `int_filemanager.share_default_days`, 30 Tage), damit nie ein verlängerter Ablauf an einem alten Token hängenbleibt.
- **"Freigeben"-UI als native Odoo-Formularansicht** (`views/filemanager_file_share_views.xml`, per `target="new"`-Dialog aus dem neuen "Freigeben"-Button in der Dateiliste geöffnet) statt eigenem OWL-Dialog - nutzt Odoos `many2many_tags`-Widget für `shared_partner_ids` und die bestehende Schreibregel (write-Capability) automatisch mit, kein zusätzlicher Berechtigungscode nötig. `share_url` ist ein reines Anzeige-Komfortfeld (`compute`, mit `CopyClipboardURL`-Widget), das den vollständigen Link aus `web.base.url` zusammensetzt.
- **Portal-Browsing-Seite bewusst minimal:** `/my/shared_files` (Liste) + `/my/shared_files/<id>/download`, ohne Paginierung/Breadcrumb-Integration (`no_breadcrumbs`) - Scope v1 sind Einzeldateien, meist wenige pro Kontakt freigegeben. Der Download-Endpoint holt den Datensatz bewusst über `browse().exists()` **plus explizites** `check_access("read")` (nicht `search()`) - liefert einen klaren 404 bei nicht existentem `file_id` und einen separaten `AccessError` bei fehlender Freigabe, beides für einen eingeloggten Portal-Nutzer unproblematisch offenzulegen (anders als beim anonymen Link, wo Runde 2/3 bewusst eine einheitliche Fehlerantwort verlangt, um nicht zu verraten, ob ein Token je existierte).
- **Zwei beim ersten echten Testlauf gefundene, sofort behobene Bugs** (Details siehe oben im Status-Abschnitt): fehlendes `@api.depends("share_token")` auf `_compute_share_url` (Link blieb nach Widerruf fälschlich sichtbar), fehlender `id`-Tiebreaker in `int_filemanager.share_log`s `_order` (Sortierung bei identischem `create_date` innerhalb derselben Transaktion nicht deterministisch).
- **Dateien:** [models/filemanager_file.py](../int_filemanager/models/filemanager_file.py) (`shared_partner_ids`, `share_token`, `share_expires_at`, `share_url`, `action_generate_share_token`, `action_revoke_share_token`), neu [models/filemanager_share_log.py](../int_filemanager/models/filemanager_share_log.py), [acl_rules.py](../int_filemanager/acl_rules.py) (Portal-Zweig, `PORTAL_GROUP_XML_ID`), [__init__.py](../int_filemanager/__init__.py) (`post_init_hook`), [controllers/main.py](../int_filemanager/controllers/main.py) (`/int_filemanager/share/<token>`), neu [controllers/portal.py](../int_filemanager/controllers/portal.py) (`/my/shared_files`, `/my/shared_files/<id>/download`), neu `views/filemanager_file_share_views.xml`, neu `views/portal_templates.xml`, `security/ir.model.access.csv` (Portal-Read-Zeile, `share_log`-Zeile), `static/src/int_filemanager/filemanager_action.js`/`.xml` ("Freigeben"-Button), neu [tests/test_sharing.py](../int_filemanager/tests/test_sharing.py) (18 Tests).

---

## Verifikation & Rollout

- `TransactionCase` + `HttpCase` — **bestätigtes Vorgehen** (siehe Phase-1–3-Umsetzung, zuletzt erneut bestätigt am 2026-09-08 für den Kill-Switch): Wegwerf-DB + eigenes Docker-Image (Basis-Image-Digest bzw. `odoo:19.0` + `pyjwt` für `onlyoffice_odoo`) auf `unraid` (192.168.188.67), `--test-enable --test-tags=/int_filemanager`, danach vollständig entfernt (DB drop, Image rmi, temp-Dateien). Kein Test lief je gegen die Produktiv-DB `odoo` (nicht `odoodb` — korrigiert, siehe DB-Namenskorrektur oben).
- **Pre-Flight** pro Phase gegen eine wegwerfbare Testinstanz, zusätzlich für Phase 4: Dockerfile-Build + `mutagen`-Smoke-Test.
- Vor jedem Modul-Update auf Produktiv: DB-Backup, Teilbaum-Backup, Watcher-Kill-Switch (`int_filemanager.watcher_enabled` auf `false` setzen, Odoo neu starten — der Watcher liest das Flag nur beim Prozessstart in `_run_watcher()`, siehe unten), dokumentiertes Rollback (Backup zurückspielen + Code-Revert), Integritätsvergleich vor/nach Scan.
- Kein automatisiertes Browser-Verifizieren ohne expliziten Wunsch.

### Bekannte Lücken aus dem Rollout-Abschnitt, noch nicht umgesetzt
- ~~`int_filemanager.watcher_enabled`-Kill-Switch~~ **implementiert und verifiziert (2026-09-08):** `_watcher_enabled(env)` in `watcher.py` liest den `ir.config_parameter` (Default `"true"`, jeder Wert außer `false`/`0`/`no`/`off` gilt als aktiviert). Geprüft wird er in `_run_watcher()`, nicht in `start_watcher()` selbst — beim `post_load`-Aufruf von `start_watcher()` steht noch kein DB-Cursor zur Verfügung (`Registry(dbname)` ist zu diesem Zeitpunkt noch nicht fertig geladen, siehe Kommentar in `_run_watcher()`). Die Prüfung sitzt deshalb in derselben Retry-Schleife, die schon `get_root()` auflöst, direkt danach vor `_watch_loop()`. Folge: das Flag wirkt erst nach einem Odoo-Neustart, kein Live-Toggle im laufenden Prozess — genau der im Rollout-Ablauf oben vorgesehene Ablauf (Flag setzen → Neustart fürs Update → Flag zurücksetzen → erneuter Neustart). Unit-Test für die reine Entscheidungsfunktion in `tests/test_watcher.py`; komplette Testsuite (69 Tests inkl. der neuen) am 2026-09-08 gegen eine frische Wegwerf-DB auf `unraid` gelaufen — 0 failed, 0 error(s), Produktiv-Container `odoo`/`odoo_db` dabei nicht berührt. Noch nicht deployed - Produktiv läuft weiterhin 19.0.1.5.0 ohne den Kill-Switch.
- Der neue `post_init_hook` (Phase 5, regeneriert die ACL-`domain_force` bei Installation) feuert nur bei einer Erstinstallation, nicht bei einem Upgrade einer bereits laufenden Installation (Odoo-Verhalten, siehe Phase-5-Ist-Stand). **Jetzt relevant, nicht mehr nur theoretisch:** da `int_filemanager` in Produktion bereits als 19.0.1.5.0 installiert ist (siehe Korrektur oben), wäre jeder weitere Deploy ein **Upgrade**, kein Neu-Install — nach dem nächsten Produktiv-Update also einmalig `env["int_filemanager.protected_folder"]._rebuild_acl_rules()` manuell ausführen (oder eine beliebige `protected_folder`-Änderung/Resave), sonst bleibt die ACL-`domain_force` auf dem Stand vor dem Upgrade.

