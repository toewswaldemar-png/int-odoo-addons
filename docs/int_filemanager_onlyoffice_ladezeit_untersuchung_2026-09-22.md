# int_filemanager: Warum ONLYOFFICE-Dokumente (z.B. DOCX) beim Öffnen langsam laden

Stand 2026-09-22. Untersuchung des gemeldeten Symptoms "Öffnen einer `.docx` über 'Bearbeiten'
dauert lange, erst kommt ein Ladebalken" — vollständig am Code dieser Session nachvollzogen
(`controllers/main.py::open_editor`, `models/ir_attachment.py`, `write_service.py`,
`onlyoffice_odoo/controllers/controllers.py`). **Ein konkreter, im Code bestätigter Bug/eine
klare Ineffizienz gefunden** (Abschnitt 1) — unabhängig davon ein zweiter, plausibler, aber noch
nicht live verifizierter Verdachtspunkt (Abschnitt 2), und ein dritter Faktor, der kein Bug ist,
sondern ONLYOFFICEs eigenes, erwartbares Verhalten (Abschnitt 3). Reine Analyse, noch keine
Umsetzung.

---

## Der vollständige Ablauf beim Klick auf "Bearbeiten"

1. Frontend (`filemanager_controller_mixin.js::onEdit`) ruft **synchron**
   `/int_filemanager/open_editor` per RPC auf und **wartet auf die Antwort**, bevor der
   ONLYOFFICE-Editor überhaupt geöffnet wird (`await rpc(...)`, danach erst
   `this.actionService.doAction(...)`). Alles, was in Schritt 2 auf der Serverseite passiert,
   liegt damit **vor** dem ersten sichtbaren Editor-Ladebalken.
2. `open_editor()` (`controllers/main.py:474`) liest die Datei komplett von der Platte
   (`f.read()`) und schreibt die Bytes in ein `ir.attachment` (`attachment.write(vals)` bei
   bereits existierendem Attachment — der Regelfall ab dem **zweiten** Öffnen derselben Datei).
3. `ir.attachment.write()` ist in diesem Modul überschrieben (`models/ir_attachment.py:38`):
   sobald `raw` im `vals`-Dict steht — was bei jedem `open_editor()`-Aufruf **unbedingt** der Fall
   ist —, wird `_int_filemanager_sync_to_disk()` ausgelöst.
4. Ist die Datei bereits indexiert (Regelfall), ruft das **den vollen versionierten
   Schreibdienst** auf: `write_service.snapshot_and_write()`.
5. Erst danach kehrt die RPC-Antwort zurück, der Editor wird geöffnet, **erst jetzt** beginnt
   ONLYOFFICE Document Server selbst mit dem eigentlichen Laden/Konvertieren (Abschnitt 3).

---

## 1. Bestätigter Befund: jedes Öffnen (nicht nur jede echte Bearbeitung) löst den vollen Versionierungs-Schreibvorgang auf unverändertem Inhalt aus

`snapshot_and_write()` (`write_service.py:96`) prüft an **keiner Stelle**, ob `new_content`
überhaupt vom bestehenden Dateiinhalt abweicht — es läuft immer die volle Kette, auch wenn beim
bloßen Öffnen zum Bearbeiten (noch) gar nichts geändert wurde:

1. **Zweiter Festplatten-Lesevorgang** der gesamten Datei (`_do_snapshot_and_write`, Zeile 148) —
   zusätzlich zum ersten Lesevorgang, der schon in `open_editor()` selbst passiert ist. Dieselbe
   Datei wird also für einen einzigen "Bearbeiten"-Klick zweimal komplett von der Platte gelesen.
2. **Eigene, dedizierte PostgreSQL-Verbindung** außerhalb von Odoos Connection-Pool
   (`_raw_connect`) plus ein **Session-Advisory-Lock** (`pg_advisory_lock`) — bewusst so gebaut
   für echte parallele Schreibkonflikte (siehe Kommentar im Datei-Kopf), aber eben auch bei einem
   reinen Öffnen ohne jede Konkurrenzsituation.
3. **Fünf separate Mini-Transaktionen** über `_run_own_cursor()` (je ein frischer
   `Registry(dbname)`-Zugriff + `reg.cursor()` + Commit + Schließen) — eine für die
   Journal-Anlage, eine für jeden der vier `_update_journal(...)`-Aufrufe (`snapshot_committed`,
   `temp_synced`, `replaced`, `done`). Fünf einzelne Datenbank-Round-Trips mit je eigenem Commit,
   statt einer gemeinsamen Transaktion.
4. **Eine komplett überflüssige neue Version wird angelegt** (`_create_version`, Zeile 156): der
   **alte** (= bei bloßem Öffnen identische) Inhalt wird Base64-kodiert als neuer
   `int_filemanager.version`-Datensatz gespeichert — bei jedem Öffnen einer bereits einmal
   editierten Datei entsteht so ein neuer Versionseintrag, auch wenn nichts geändert wurde.
   **Nebenwirkung über die Performance hinaus:** die Versionshistorie einer oft geöffneten Datei
   füllt sich mit inhaltlich identischen Duplikaten — ein Datenhygiene-Problem, nicht nur ein
   Tempo-Problem.
5. **Tempfile-Schreibvorgang mit `fsync()`** (Zeile 177-182) für Inhalt, der **byteidentisch**
   zum bereits auf der Platte liegenden Inhalt ist, gefolgt von `os.replace()` und einem
   `chmod`-Aufruf (`make_shareable`). `fsync()` erzwingt einen echten Schreibvorgang bis zum
   Datenträger — bei den in diesem Repo dokumentierten CIFS-Netzlaufwerken (siehe
   `int_filemanager_external_change_watcher_regression.md`) potenziell spürbar langsamer als bei
   lokalem Speicher.

**Alles davon läuft synchron innerhalb der `/int_filemanager/open_editor`-Anfrage, bevor der
Nutzer überhaupt den ONLYOFFICE-Editor zu Gesicht bekommt** — bei einer größeren `.docx`
(eingebettete Bilder, mehrere MB) mit entsprechend längeren Lese-/Kodier-/Schreibzeiten, potenziell
zusätzlich verschärft durch Netzlaufwerk-Latenz, ist das eine plausible, direkte Erklärung für
einen spürbaren Ladebalken **vor** dem eigentlichen Editor-Start — unabhängig von ONLYOFFICE
selbst.

**Root Cause zusammengefasst:** `open_editor()` behandelt "Datei zum Bearbeiten öffnen" technisch
identisch zu "Datei wurde geändert" — es gibt keinen Unterschied zwischen einem reinen Lesevorgang
(Editor öffnen, aber noch nichts bearbeitet) und einem echten Schreibvorgang. Der volle,
absichtlich für **echte** gleichzeitige Schreibkonflikte gebaute Versionierungs-/Lock-Mechanismus
wird bei **jedem einzelnen Öffnen** ausgelöst, nicht nur beim tatsächlichen Speichern durch
ONLYOFFICE.

---

## 2. Plausibler, aber nicht live verifizierter Zusatzverdacht: ONLYOFFICEs eigener Konvertierungs-Cache könnte durch denselben Mechanismus mit ausgehebelt werden

`onlyoffice_odoo` (das Drittanbieter-Modul, das die eigentliche Editor-Anbindung liefert)
bestimmt den Cache-Schlüssel, unter dem der ONLYOFFICE Document Server ein bereits konvertiertes
Dokument wiedererkennt, so (`controllers/controllers.py:270-271`):

```python
data = attachment.read(["id", "checksum", "public", "name", "access_token"])[0]
key = str(data["id"]) + str(data["checksum"])
```

Der Schlüssel hängt direkt vom `checksum`-Feld des `ir.attachment`-Datensatzes ab — Odoos eigenes,
inhaltsbasiertes Prüfsummenfeld. **Offene Frage, nicht abschließend geklärt in dieser Session:**
verändert sich `checksum` durch den in Abschnitt 1 beschriebenen, inhaltlich folgenlosen
`attachment.write({"raw": <unveränderte Bytes>, ...})`-Aufruf tatsächlich? Wenn der Inhalt wirklich
byteidentisch ist, **sollte** Odoos eigene, inhaltsbasierte Prüfsummenberechnung denselben Wert wie
zuvor liefern — dann bliebe der ONLYOFFICE-`key` stabil und der Document-Server-Cache griffe
weiterhin. Sollte sich der `checksum` aus irgendeinem Grund trotzdem ändern (z.B. weil Odoo ihn
nicht rein inhaltsbasiert, sondern auch von Metadaten/Zeitpunkt der Speicherung ableitet, oder weil
der Schreibpfad über `ir.attachment`s Filestore-Mechanik eine neue Version anlegt), würde
**jedes** Öffnen für den Document Server wie ein **komplett neues Dokument** aussehen — mit der
Folge, dass die (bei größeren/komplexeren `.docx`-Dateien nicht triviale) `x2t`-Konvertierung bei
**jedem** Öffnen von Neuem läuft, statt eine bereits vorhandene, gecachte Konvertierung
wiederzuverwenden.

**Zur Klärung nötig (nicht in dieser Session durchgeführt, da keine Live-Instanz verfügbar):**
`ir.attachment.checksum` vor und nach einem `open_editor()`-Aufruf auf dieselbe, unveränderte Datei
vergleichen (z.B. per `odoo shell`: Attachment-Datensatz lesen, `open_editor()`-Route erneut
auslösen, erneut lesen, `checksum`-Werte gegenüberstellen).

---

## 3. Nicht Teil des Bugs, sondern ONLYOFFICEs eigenes, erwartbares Verhalten

Unabhängig von den Punkten 1/2: **sobald** der ONLYOFFICE-Editor tatsächlich startet, muss der
Document Server das Dokument von der angegebenen URL abrufen und mit seinem eigenen `x2t`-
Konvertierungswerkzeug in sein internes Bearbeitungsformat umwandeln — das ist bei **jeder**
ONLYOFFICE-Integration (nicht nur bei dieser) ein bekannter, erwarteter Zeitaufwand beim ersten
Öffnen eines Dokuments, sichtbar als Lade-/Fortschrittsanzeige im Editor selbst. Einflussfaktoren,
die hier zusätzlich zu Punkt 1/2 eine Rolle spielen können, aber **kein Bug in diesem Modul** sind:

- **Ressourcen des Document-Server-Containers** (CPU/RAM) — ONLYOFFICE empfiehlt für die
  Konvertierung spürbar mehr als minimale Docker-Defaults, insbesondere bei mehreren gleichzeitigen
  Konvertierungen.
- **Netzwerklatenz zwischen Odoo und dem Document-Server-Container** — der Document Server muss
  das Dokument aktiv per HTTP von der in der Editor-Konfiguration übergebenen URL abrufen
  (`odoo_url + "onlyoffice/file/content/" + ...`), das ist ein zusätzlicher Netzwerk-Hop, keine
  direkte Dateiübergabe.
- **Dokumentkomplexität** — viele eingebettete Bilder, komplexe Formatierung, große Dateigröße
  verlängern die `x2t`-Konvertierungszeit unabhängig von allem anderen.

**Diese drei Punkte sollten von Punkt 1 klar getrennt bewertet werden** — selbst wenn Punkt 1
behoben wäre, bliebe ein gewisser, für ONLYOFFICE-Integrationen normaler Ladebalken beim ersten
Öffnen eines Dokuments bestehen. Punkt 1 ist der Teil, der **zusätzlich** und **unnötig** obendrauf
kommt, speziell bei wiederholtem Öffnen derselben, bereits editierten Datei.

---

## 4. Nachtrag (gleicher Tag): könnte man das Öffnen schon beim ersten Klick im Hintergrund anstoßen?

Nutzerfrage im Anschluss an diese Untersuchung. **Erste Klarstellung, am Code dieser Session
geprüft:** die native UI öffnet Dateien bereits heute per **einfachem** Klick, nicht per
Doppelklick — `native_list_renderer.js::onCellClicked()` ruft direkt `openRecord()` auf, es gibt
keine `dblclick`-Verdrahtung für das Öffnen (nur der PDF-Highlight-Viewer nutzt `dblclick` für
einen internen, unabhängigen Zweck). Es gibt also **heute keine künstliche Lücke zwischen "erstem"
und "zweitem" Klick**, die sich zeitlich ausnutzen ließe — der RPC-Aufruf startet bereits beim
einzigen registrierten Klick. Falls sich das Verhalten beim Nutzer tatsächlich wie ein
Doppelklick-Workflow anfühlt, lohnt sich vor einer Umsetzung zu prüfen, ob dort noch die ältere,
nicht-native UI (`legacy_ui/filemanager_action.js`) läuft statt der aktiven `native_list_view.js`
(siehe `int_filemanager_native_ui.md`, Migration war zuletzt noch nicht vollständig abgeschlossen).

**Der eigentliche, wertvolle Kern der Idee bleibt trotzdem gültig — nur mit anderem Ansatzpunkt als
"welcher Klick".** Am Code von `onlyoffice_odoo/static/src/actions/documents_action.js`
nachvollzogen, ist die tatsächliche Kette beim Öffnen **drei sequenzielle Wartepunkte** lang, nicht
nur einer:

1. `/int_filemanager/open_editor` (dieses Modul, siehe Abschnitt 1 — mit dem dort gefundenen
   überflüssigen Versionierungs-Schreibvorgang).
2. Erst danach, im gerade neu gemounteten `onlyoffice_editor`-Client-Action-Component
   (`onMounted()`): eine **zweite**, unabhängige RPC (`/onlyoffice/editor/get_config`) an
   `onlyoffice_odoo`, die die Editor-Konfiguration inkl. `docApiJS`-URL liefert
   (`prepare_editor_values()`, braucht die `attachment_id` aus Schritt 1 — kann also nicht vor
   Schritt 1 starten).
3. Erst danach: `if (!window.DocsAPI) { await this.loadDocsAPI(this.docApiJS) }` — ein
   **dynamisch nachgeladenes `<script>`-Tag**, das die JS-API des ONLYOFFICE Document Servers
   lädt. **Erst wenn dieses Skript geladen ist**, beginnt `new DocsAPI.DocEditor(...)` überhaupt
   erst den eigentlichen Dokumentabruf/die Konvertierung (Abschnitt 3).

**Der entscheidende Punkt für die Nutzerfrage:** Schritt 3 hängt **von keiner konkreten Datei ab**
— `docApiJS` ist eine feste, aus der Server-Konfiguration abgeleitete URL, identisch für jedes
Dokument. Der Code selbst überspringt Schritt 3 bereits automatisch, **wenn `window.DocsAPI`
schon vorhanden ist** (`if (!window.DocsAPI)`) — das ist heute nur ab dem zweiten in derselben
Browser-Session geöffneten Office-Dokument der Fall. Genau das ist der sichere, uneingeschränkt
empfehlenswerte Ansatzpunkt für "im Hintergrund vorbereiten":

- **Sicher, unabhängig von Abschnitt 1, keine Seiteneffekte:** das `DocsAPI`-Skript **eigenständig
  und dateiunabhängig vorab laden** — z.B. sobald die Dateiliste/-ordneransicht mit mindestens
  einer Office-Datei sichtbar ist, oder beim ersten Hover über eine Office-Datei-Zeile. Das ist
  reines JS-Nachladen einer festen URL, betrifft keinen Datensatz, kann beliebig oft "auf
  Verdacht" ausgelöst werden, ohne irgendein Risiko — anders als Schritt 1/2 unten. Würde Schritt 3
  faktisch für **jedes** Öffnen entfallen lassen, nicht nur ab dem zweiten Dokument einer Session.
- **Nicht sicher, solange Abschnitt 1 nicht behoben ist:** Schritt 1 (`open_editor`) oder Schritt 2
  (`get_config`) spekulativ vorzuziehen (z.B. bei `pointerdown` statt erst nach vollständigem
  Klick, oder gar bei Hover) — **das würde den in Abschnitt 1 gefundenen Bug direkt vervielfachen**:
  jedes bloße Überfahren mehrerer Dateizeilen mit der Maus würde für jede davon einen unnötigen,
  vollständigen Versionierungs-Schreibvorgang samt überflüssiger neuer Version auslösen, auch für
  Dateien, die der Nutzer nie tatsächlich öffnet. **Reihenfolge ist hier wichtig:** erst der in
  Abschnitt 1 skizzierte Inhalts-Vergleich (kein Schreibvorgang bei unverändertem Inhalt), danach
  wäre ein vorgezogenes Auslösen von Schritt 1/2 (z.B. bei `pointerdown` statt `click`, mit kurzer
  Verzögerung/Abbruch bei erkanntem Drag&Drop-Vorgang, da dieses Modul Drag&Drop zum Verschieben
  unterstützt) ein risikoarmer, zusätzlicher Zeitgewinn.

**Zusammengefasst, als Reihenfolge:** (1) den in Abschnitt 1 gefundenen Bug beheben — Voraussetzung
für alles Weitere; (2) unabhängig davon und sofort umsetzbar: das `DocsAPI`-Skript dateiunabhängig
vorladen, sobald die Ansicht eine Office-Datei zeigt — der größte Einzelgewinn mit dem geringsten
Risiko; (3) erst danach, falls noch gewünscht: Schritt 1/2 auf ein früheres Signal als den fertigen
Klick vorziehen.

---

## 5. Nachtrag 2026-09-23: Abschnitt 2 endgültig geklärt + ein dritter, bisher unentdeckter Kostenpunkt in Odoos eigenem `ir.attachment`

Auslöser: der Auftrag, Office-Dateien "so reibungslos wie möglich" zu öffnen (Hauptarbeitsmittel im
Unternehmen), direkt am Odoo-19-Quellcode nachgeprüft statt nur vermutet.

**Abschnitt 2s offene Frage ist jetzt beantwortet: der ONLYOFFICE-Konvertierungs-Cache wird NICHT
mit ausgehebelt.** `ir.attachment._get_datas_related_values()` (`odoo/addons/base/models/ir_attachment.py:314`)
berechnet den `checksum` rein inhaltsbasiert (`self._compute_checksum(data)`) — bei byteidentischem
Inhalt entsteht **garantiert derselbe** Wert, unabhängig davon, wie oft `write({"raw": ...})`
aufgerufen wird. Der ONLYOFFICE-Cache-Schlüssel (`id + checksum`) bleibt also stabil, dessen eigener
Konvertierungs-Cache greift weiterhin. **Entwarnung für diesen Punkt.**

**Dafür ein neuer, unabhängiger Kostenpunkt gefunden: Odoos eigenes `ir.attachment` macht bei jedem
`write({"raw": ...})` unconditional echte Arbeit, selbst bei komplett unverändertem Inhalt** — die
Ineffizienz aus Abschnitt 1 sitzt also nicht nur in `int_filemanager`s eigenem Code, sondern
**zusätzlich** eine Ebene tiefer in Odoo selbst:

```python
# _set_attachment_data() → für jeden Aufruf, ohne Kurzschluss bei unveraendertem Inhalt:
vals = self._get_datas_related_values(bin_data, attach.mimetype)  # SHA1 ueber die GESAMTE Datei
...
super(IrAttachment, attach.sudo()).write(vals)                    # Metadaten-Schreibvorgang
...
self._file_write(raw, checksum)                                   # Filestore-Schreibversuch
```

Kein `_filter_not_equal`-Kurzschluss vor dieser Kette — anders als bei einem gewöhnlichen
gespeicherten Feld prüft ein `compute`/`inverse`-Feld wie `raw` nicht vorab, ob sich der Wert
überhaupt geändert hat, bevor die Inverse-Methode läuft. Konkret unconditional bei **jedem**
Öffnen einer bereits einmal editierten Office-Datei: eine vollständige SHA1-Berechnung über die
gesamte Dateigröße, plus ein `write()`-Aufruf auf die Attachment-Metadatenfelder. **Für Office-
Dateien selbst unkritisch ist dabei nur der `_index()`-Aufruf** (`ir_attachment.py:434`) — der
tut in Community-Odoo ausschließlich bei `text/*`-Mimetypes etwas (ein einfacher ASCII-String-Scan),
bei `application/vnd.openxmlformats-officedocument...` liefert er sofort `None`. Der eigentliche
Filestore-Schreibversuch selbst bleibt zwar folgenlos (siehe Abschnitt zu `_file_write` weiter oben
in dieser Analysereihe: Odoos Filestore ist content-addressiert, ein bereits vorhandener Pfad wird
übersprungen) — aber die **SHA1-Berechnung davor** passiert so oder so, jedes Mal.

**Präzisierter, "so reibungslos wie möglich"-tauglicher Fix — eine Stufe früher ansetzen als
ursprünglich vorgeschlagen:** nicht erst vor `snapshot_and_write()` prüfen (Abschnitt "Einordnung"
unten), sondern **noch vor dem allerersten `open()`-Aufruf in `open_editor()` selbst**. Da
`int_filemanager.file` aus Phase 1 (`int_filemanager_ausbau.md`) bereits `content_sha256`,
`hash_source_mtime_ns` und `hash_size` pflegt, ließe sich beim Öffnen zunächst nur ein billiger
`os.stat()` auf die Datei machen und dessen Größe/`mtime_ns` gegen die bereits bekannten,
gespeicherten Werte vergleichen — **stimmen sie überein, kann `open_editor()` sofort die
bestehende `attachment_id` zurückgeben, ganz ohne Datei zu lesen, ohne `attachment.write()`,
ohne SHA1-Berechnung, ohne die komplette `write_service`-Kette.** Das wäre die maximal
reibungslose Variante: ein wiederholtes Öffnen einer unveränderten Office-Datei kostet dann nur
noch einen einzigen schnellen Datenbank-/Dateisystem-Abgleich, bevor ONLYOFFICEs eigener (nicht
vermeidbarer) Konvertierungsschritt beginnt.

---

## Einordnung / möglicher Ansatzpunkt (nicht umgesetzt)

Der naheliegende Fix für Punkt 1 wäre ein **Inhalts-Vergleich vor dem Schreiben**: `open_editor()`
bzw. `_int_filemanager_sync_to_disk()` könnte den Hash des neu gelesenen Inhalts mit dem bereits
bekannten `content_sha256` von `file_record` (dasselbe Feld, das die Scan-Identität aus Phase 1
laut `int_filemanager_ausbau.md` ohnehin schon pflegt) vergleichen und `snapshot_and_write()` nur
dann aufrufen, wenn sich tatsächlich etwas geändert hat — ein reines Öffnen zum Bearbeiten würde
dann nur noch den (unvermeidbaren) Lesevorgang plus das Anlegen/Aktualisieren des Attachments für
ONLYOFFICE kosten, ohne die komplette Versionierungs-/Lock-/Journal-Kette. Nicht umgesetzt, da
nicht beauftragt — reine Analyse dieser Session.
