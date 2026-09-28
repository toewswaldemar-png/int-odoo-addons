# int_filemanager: Grundsatzentscheidung + Roadmap zum vollwertigen Explorer/Directory-Opus-Ersatz

Stand 2026-09-23. Ergebnis eines grundsätzlichen Architektur-Gesprächs (DB- vs. Platte-als-Wahrheit,
WebDAV, Desktop-Sync-Client) mit einem klaren Zielsatz am Ende: **das Modul massiv so ausbauen,
dass Explorer/Directory-Opus-artiges Arbeiten möglich ist** — deckt sich mit dem bereits in
`../int_filemanager_native_ui.md` festgehaltenen Ursprungsziel ("Mitarbeiter sollen vom Windows
Explorer auf die WebUI umsteigen — Parität zu Explorer/Directory Opus als Messlatte"), nicht neu,
aber jetzt explizit als Leitentscheidung bestätigt statt nur implizit verfolgt. Reine Planung,
nichts umgesetzt.

---

## 1. Die Architekturfrage löst sich am Ziel selbst, nicht durch einen harten Schnitt

Aus dem Gespräch (Zusammenfassung, Details in den zitierten Fundstellen):

- **"DB ist Wahrheit"** würde jede externe Änderung (Explorer, SMB) unsichtbar machen, außer sie
  läuft über einen von Odoo kontrollierten Weg (WebDAV, Upload). Sauber, aber ein harter
  Verhaltensbruch für alle, die heute noch direkt auf die Freigabe zugreifen.
- **WebDAV als Netzlaufwerk** würde den Zugriff technisch durch Odoo leiten (löst das
  Wahrheits-Problem), hat aber reale Grenzen (Windows-Bordmittel-Client: 50-MB-Grenze,
  spürbar langsamer als SMB, unzuverlässig) und würde einen viel vollständigeren WebDAV-Server
  erfordern als heute vorhanden (`webdav.py` kann aktuell nur Einzeldatei-Token, kein
  `MOVE`/`DELETE`/`MKCOL`/echtes `PROPFIND`).
- **Ein Desktop-Sync-Client** löst das Problem nicht, sondern vervielfacht es (ein Watcher pro
  Client-Rechner statt einer zentral) und ist ein eigenständiges, sehr aufwendiges Projekt.

**Die Klärung, die das Gespräch aufgelöst hat:** Das eigentliche, schon länger bestehende Ziel ist
nicht "SMB-Zugriff dauerhaft gleichwertig neben der WebUI erhalten", sondern **"die WebUI so gut
machen, dass Explorer-Zugriff überflüssig wird"**. Damit verschiebt sich die Fragestellung: Statt
"wie bewahren wir Platte-als-Wahrheit für alle Zugriffswege" wird die Frage "wie gut muss die
WebUI werden, damit die Frage sich von selbst erledigt" — **kein sofortiger harter Umstieg auf
'DB ist Wahrheit' nötig**, aber jede Investition in Explorer-Parität der WebUI reduziert die
Abhängigkeit vom heutigen Watcher/Reconciliation-Aufwand organisch, ohne bestehende funktionierende
Wege (Scan-Eingangsordner, Drag&Drop) sofort zu brechen.

**Empfehlung:** die Architekturfrage (DB- vs. Platte-Autorität) nicht isoliert vorab entscheiden,
sondern als **Konsequenz** des Ausbaus behandeln — je weiter die WebUI Explorer ersetzt, desto
eher wird "DB ist stärker autoritativ" von selbst zur natürlichen, risikoarmen nächsten
Entscheidung (weniger Menschen/Prozesse verlassen sich noch auf direkten Plattenzugriff). Diese
Entscheidung explizit **offen halten und später erneut bewerten**, nicht jetzt festlegen.

**Nachtrag (gleicher Tag, Ende-zu-Ende durchgespielt): "DB ist Wahrheit" wird nicht
weiterverfolgt — die Bilanz ist zu Ende gerechnet, kein offener Punkt mehr.** Durchgespielt wurden
WebDAV-als-Netzlaufwerk (Windows-Client-Grenzen, eigenständiger Server-Ausbau nötig),
Desktop-Sync-Client (verschlimmert das Problem, ein Watcher pro Rechner statt einem zentral) und
periodischer Scan als Watcher-Ersatz (keine echte "DB ist Wahrheit", nur eine langsamere Variante
von "Platte ist Wahrheit" — und nachweislich teuer: der bereits produktive `_shallow_reconcile()`
läuft alle 5 Minuten ~289s allein für die drei CIFS-Freigaben). Selbst im besten Fall bliebe die
Hash-/Rename-Erkennung aus Phase 1 vollständig im Code erhalten, nur seltener aufgerufen statt
kontinuierlich. **Ergebnis:** der einzige tatsächlich verbleibende Nutzen wäre ein etwas
einfacherer Papierkorb (kein Watcher-Guard nötig) — zu schmal, um den Explorer-Zugriff
aufzugeben und einen vollständigen WebDAV-Server neu zu bauen. **Papierkorb wird stattdessen wie
in `recherchen-odoo-bausteine/int_filemanager_papierkorb_odoo_umsetzung_2026-09-23.md` geplant über den Watcher-Guard
gelöst**, kein Architekturwechsel nötig.

**Nachtrag 2026-09-24 (Entscheidung revidiert): diese Ablehnung gilt nicht mehr.** Nach deutlich
tieferer, live auf HM-SRV getesteter Prüfung (eigene Testinstanz, echte Postgres-/Dateisystem-
Experimente, vollständiger Odoo-19-Core-Durchgang) hat der Nutzer am 2026-09-24 das Gegenteil
entschieden: **Variante B — DB als Wahrheit**, dokumentiert in
`../int_filemanager_konzept_db_vorrang_2026-09-24.md` (Branch `docs/konzept-db-vorrang`). Der
seinerzeitige Ausschlussgrund ("Erstellen/Umbenennen/Löschen/Verschieben von extern wären
unsichtbar") gilt dort nicht mehr, weil ein eigens gebauter, auf einen Zulieferer reduzierter
Watcher plus Abgleich-Cron genau diese externen Änderungen weiterhin einsammelt — nur die
Datenautorität selbst liegt bei der DB, nicht mehr bei der Platte. Die Roadmap in Abschnitt 3
dieses Dokuments bleibt inhaltlich meist gültig, ihre Reihenfolge wird aber von Abschnitt 10 des
neuen Konzeptdokuments überstimmt (Hotfix Papierkorb-Scan-Bug zuerst, dann App-Schreibwege, dann
Watcher/Abgleich-Cron — erst danach CIFS-Optimierung).

---

## 2. Was "massiver Ausbau" konkret heißt — Zusammenführung aller bisherigen Funde dieser Session

Kein neuer Katalog — alles bereits einzeln recherchiert und dokumentiert, hier nur nach
Explorer/Directory-Opus-Parität geordnet:

**Navigation & Bedienung** (`../int_filemanager_feature_ideen_2026-09-21.md`, Abschnitt C):
Adressleiste ("Gehe zu Pfad"), Zwei-Spalten-/Splitview, Favoriten/Quick-Access, Zuletzt verwendet,
Galerie-/Rasteransicht für Bilder, Tastenkürzel (Entf/F2/Strg+C/V/X), Kopieren als eigene
Operation.

**Sicherheit/Datenintegrität** (`recherchen-odoo-bausteine/int_filemanager_papierkorb_odoo_umsetzung_2026-09-23.md`):
Papierkorb — vollständiger Bauplan bereits steht (Odoo-`active`-Feld, Watcher-Guard,
Restore-Route, Retention-Cron). Größte bereits gefundene Einzellücke im ganzen Modul.

**Vorschau & Bearbeitung** (`recherchen-odoo-bausteine/int_filemanager_pdf_ausbau_odoo_2026-09-23.md`,
`recherchen-odoo-bausteine/int_filemanager_bildvorschau_bearbeitung_odoo_2026-09-23.md`): PDF-Annotationen bereits im
Vorschau-Dialog lauffähig, nur ohne Rückschreib-Anbindung; Bildbearbeitung (Zuschneiden, Filter)
über wiederverwendbare Odoo-Bausteine (Cropper.js, Canvas/WebGL-Filter); Bild-Rotation in der
Vorschau bereits vorhanden, aber nicht persistiert.

**Auffindbarkeit** (`../int_filemanager_feature_ideen_2026-09-21.md`, Abschnitt B):
Duplikat-Finder (Hash-Infrastruktur existiert schon), gespeicherte Suchen, Office-Dokumente in
die Volltextsuche einbeziehen, Trefferausschnitte.

**Auswertung** (Abschnitt D): Speicherplatz-Dashboard, größte/älteste Dateien — reine
Pivot/Graph-Views auf bereits vorhandenen Feldern, praktisch kostenlos.

**Performance-Grundlage, die vor größerem UI-Ausbau tragen muss:**
`int_filemanager_acl_perf_plan.md` — geplant (indexiertes `protected_folder_id`-Feld statt
LIKE-Klauseln), noch nicht umgesetzt, aktuell ~580ms pro ACL-Auswertung bei 1,38 Mio. Zeilen.
**Sollte vor einem umfangreichen UI-Ausbau angegangen werden** — jede neue, schnellere UI-Aktion
(Splitview, Galerie, Schnellsuche) macht die bestehende ACL-Langsamkeit nur spürbarer, nicht
weniger relevant.

**Unfertige native-UI-Migration** (`../int_filemanager_native_ui.md`): alte und neue UI koexistieren
teils noch. Sollte vor massivem Ausbau der neuen UI abgeschlossen werden (inkl. der bereits
gefundenen `bus.bus`-Live-Refresh-Lücke, siehe `recherchen-odoo-bausteine/int_filemanager_odoo_native_integration_2026-09-21.md`,
Punkt 1) — sonst wächst der Wartungsaufwand mit jedem neuen Feature doppelt.

**WebDAV-Vollausbau** (aus dem heutigen Architekturgespräch, neu): ein vollständiger, allgemeiner
WebDAV-Server (statt der heutigen Einzeldatei-Token-Lösung) wäre sowohl ein eigenständiger
Explorer-Parität-Baustein (Netzlaufwerk-Option für alle, die das wollen) als auch die technische
Grundlage, falls später doch Richtung "DB ist Wahrheit" gegangen werden soll — zwei Fliegen mit
einer Klappe, aber ein eigenständiges, nicht triviales Vorhaben.

---

## 2a. Nachtrag (gleicher Tag): Office/ONLYOFFICE-Zuverlässigkeit ist die eigentliche Messlatte, nicht nur ein Punkt unter vielen

Zugespitzte Erkenntnis aus dem Gespräch: da im Unternehmen **hauptsächlich noch mit Office-
Dateien** gearbeitet wird und die ganze Strategie darauf beruht, dass Kollegen **zwangsläufig**
über `int_filemanager` arbeiten (Abschnitt 1), entscheidet sich an genau diesem einen Workflow,
ob die Strategie trägt — nicht an Navigation, Papierkorb oder Vorschau. Reibung dort ist ärgerlich,
aber verkraftbar; Reibung beim täglichen Kernworkflow (Office-Datei öffnen/bearbeiten) führt aus
reiner Notwendigkeit zurück zu Explorer/lokalen Kopien und unterläuft die gesamte
Grundsatzentscheidung. Die drei bereits vollständig untersuchten, bauplanfertigen Punkte rücken
damit vor alles andere in Abschnitt 3:

1. `../int_filemanager_onlyoffice_ladezeit_untersuchung_2026-09-22.md` — bestätigter
   Redundant-Write-Bug bei jedem Öffnen, inkl. der präzisierten Stat-Vergleich-Lösung
   (Nachtrag 2026-09-23).
2. Dasselbe Dokument, Abschnitt 4 — DocsAPI-Script dateiunabhängig vorladen, größter Einzelgewinn
   bei geringstem Risiko.
3. `../int_filemanager_lokal_oeffnen_warnungen_2026-09-23.md` — Protokoll-Entscheidung (intern HTTP,
   extern über Reverse-Proxy mit echtem Zertifikat, `proxy_mode` in Odoo aktivieren) plus zwei
   GPO-Verteilungen (Browser-Protokoll-Freigabe, Office-Trusted-Protocols).

## 3. Vorschlag zur Reihenfolge (nicht final, Diskussionsgrundlage)

1. **Office/ONLYOFFICE-Zuverlässigkeit zuerst, vor allem anderen** (siehe 2a) — das ist die
   Voraussetzung dafür, dass die Grundsatzentscheidung selbst hält.
2. **Fundament danach:** ACL-Performance-Fix + native-UI-Migration abschließen (inkl.
   `bus.bus`-Lücke) — sonst trägt die Basis den weiteren Ausbau nicht.
3. **Größter Einzelgewinn mit vorhandenem Bauplan:** Papierkorb — Sicherheitsrelevant, Bauplan
   steht, sollte nicht länger als nötig fehlen, besonders mit dem Langfristziel persönlicher
   Dateien im Hinterkopf.
4. **Navigation/Bedienung:** die in Abschnitt 2 gelisteten Explorer-Paritätspunkte — hier
   entscheidet sich am direktesten, ob Kollegen tatsächlich wechseln.
5. **Vorschau/Bearbeitung:** PDF-Rückschreib-Hook, Bild-Zuschneiden — sichtbare, spürbare
   Funktionsgewinne, Bausteine bereits identifiziert.
6. **Auffindbarkeit/Auswertung:** kann parallel zu 4/5 laufen, geringe gegenseitige Abhängigkeit.
7. **WebDAV-Vollausbau** bleibt zurückgestellt — "DB ist Wahrheit" wurde bereits abschließend
   verworfen (siehe Nachtrag oben), WebDAV bliebe nur noch als eigenständiger
   Explorer-Paritäts-Baustein relevant, kein Architekturgrund mehr dafür.

**Nicht Teil dieser Reihenfolge, bewusst offen gelassen:** ob/wann direkter SMB-Zugriff
eingeschränkt wird — das ist eine organisatorische Entscheidung (betrifft Kollegen-Gewohnheiten,
Scan-Software-Konfiguration), die sich aus dem tatsächlichen Nutzungsverhalten nach Schritt 3/4
ergeben sollte, nicht aus einer vorab getroffenen technischen Grundsatzentscheidung.
