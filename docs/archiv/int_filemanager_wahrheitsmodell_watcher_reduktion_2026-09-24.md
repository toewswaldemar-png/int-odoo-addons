# int_filemanager: Wahrheitsmodell und Watcher auf ein stabiles Maß reduzieren (statt global entscheiden)

Stand 2026-09-24. Ergänzung zu `int_filemanager_grundsatz_explorer_ausbau_2026-09-23.md`, die dort
noch offene Frage "DB- vs. Platte-als-Wahrheit ist keine Entweder-Oder-Frage" konkret ausformuliert
— zusammen mit einem direkt anwendbaren Schnitt für den fragilen Watcher, basierend auf den bereits
dokumentierten Funden zu `watcher.py` (`int_filemanager_watcher_stille_fehlschlaege_2026-09-23.md`)
und FileBrowser Quantum (`int_filemanager_filebrowser_scan_architektur_2026-09-23.md`). Reine
Planung, nichts umgesetzt.

**Nachtrag 2026-09-24 (noch am selben Tag überholt): Dieses Dokument ist durch
`../int_filemanager_konzept_db_vorrang_2026-09-24.md` (Branch `docs/konzept-db-vorrang`) ersetzt.**
Der Nutzer hat dort — live auf HM-SRV getestet, nicht nur konzeptionell — bereits **Variante B: DB
als Wahrheit** entschieden, das genaue Gegenteil der hier zugrunde gelegten Annahme ("DB ist
Wahrheit wurde verworfen"). Das Dokument dort benennt den Denkfehler hier explizit (Abschnitt 9):
der "Schnitt lokal/CIFS" trägt nicht, weil 99,96 % der Daten tatsächlich auf den drei
CIFS-Testfreigaben liegen, nicht lokal — die Prämisse "lokal ist der stabile, primäre Teil" war
falsch. Ebenso trifft die hier gemachte Annahme "App-Schreibvorgänge sind bereits DB-geführt"
nicht zu (Fund B4: ONLYOFFICE-Save, Upload-Überschreiben, Version-Restore und WebDAV-PUT pflegen
den Index nicht selbst, sondern hängen vom Watcher ab). Als Referenz zum "SMB-Watcher"-Gespräch von
heute bleibt nur der Fund zu SMB2 `CHANGE_NOTIFY` (Abschnitt weiter unten in diesem Chat, nicht in
diesem Dokument) gültig — er betrifft die Protokollebene, nicht die hier verworfene
Architekturentscheidung.

---

## 1. Die Grundidee: beide Prinzipien nur dort einsetzen, wo sie bereits nachweislich stabil sind

"DB ist Wahrheit" wurde am 2026-09-23 als globale Architekturentscheidung abschließend verworfen
(externe Änderungen über Explorer/CIFS blieben sonst komplett unsichtbar). Das bleibt richtig — aber
die Ablehnung war global gemeint. Sie schließt nicht aus, das Prinzip **lokal, für einen bereits
tatsächlich DB-geführten Teilbereich**, einfach nur anzuerkennen, statt es zu erzwingen. Ebenso ist
der Live-Watcher nicht insgesamt unbrauchbar — nur sein aktueller Zuschnitt (ein gemeinsamer
inotify-Deskriptor für lokale Freigabe UND drei CIFS-Mounts) überträgt die Instabilität des
schwächsten Teils auf den robusten Teil.

**Der Schnitt läuft nicht "DB vs. Platte" oder "Watcher vs. Scan", sondern entlang der bereits
bestehenden Grenze zwischen Schreibpfaden bzw. Speicherorten:**

| Bereich | Bereits heute stabil? | Empfohlenes Prinzip |
|---|---|---|
| Schreibvorgänge über int_filemanager selbst (UI, WebDAV-Einzeldatei, ONLYOFFICE-Save) | Ja — `write_service.py` schreibt DB-Zeile unter Session-Lock, dann atomar auf Platte | **DB ist Wahrheit** (bereits Realität, nur nicht so benannt) |
| Lokale Array-Freigabe (ntfs3, kein Netzwerk) | Ja — fsprobe-Messung 2026-08-03 bestätigt: liefert zuverlässig inotify-Events | **Live-Watcher**, aber mit den 3 bekannten Fixes |
| Drei CIFS-Freigaben | Nein — Server liefert kein `CHANGE_NOTIFY`, Mount kann kurzzeitig verschwinden | **Kein Live-Watcher-Anspruch mehr**, nur adaptiver Scan |

Jede Zeile für sich ist bereits einzeln belegt (write_service-Code, fsprobe-Messung, CIFS-
CHANGE_NOTIFY-Fund) — neu ist nur, sie nebeneinanderzustellen und daraus einen konkreten Schnitt
abzuleiten, statt eine einzige globale Antwort zu suchen.

---

## 2. Warum das den Watcher tatsächlich stabiler macht, nicht nur anders benennt

Der entscheidende, bereits dokumentierte Fund aus dem Nachtrag vom 24.09. in
`int_filemanager_watcher_stille_fehlschlaege_2026-09-23.md`: `_watch_loop()` läuft als **eine**
Schleife über **einen** inotify-Deskriptor für den gesamten `root_path` — lokale Freigabe und die
drei CIFS-Mounts sitzen im selben Baum. Das bedeutet konkret: stürzt `inotify.read()` wegen eines
kurz verschwindenden CIFS-Mounts mit einer ungefangenen `OSError` ab (Finding 1, kein Watchdog),
stirbt der Watcher-Thread für den **gesamten** Baum — inklusive der lokalen Freigabe, die für sich
genommen überhaupt kein Problem hätte.

**Der Reduktions-Schritt trennt genau diese Kopplung:**

1. **Zwei getrennte Watch-Bäume statt einem.** Ein `_watch_loop()`-Deskriptor nur für die lokale
   Array-Freigabe, ein zweiter (oder: gar keiner mehr) für die drei CIFS-Mounts. Eine CIFS-Störung
   kann dann strukturell nicht mehr den Watcher der lokalen Freigabe mitreißen — nicht weil der Bug
   behoben wäre, sondern weil die betroffene Komponente nicht mehr existiert.
2. **Die 3 bekannten Fixes nur noch auf einen kleineren, tatsächlich beherrschbaren Bereich
   anwenden:** Watchdog um `read()`/`add_watch()` (Finding 1+2), `Q_OVERFLOW`-Behandlung
   (Finding 3) — für die lokale Freigabe allein ist das ein klar abgegrenzter, gut testbarer
   Umfang, keine Ergänzung, die gegen unvorhersehbares CIFS-Verhalten bestehen muss.
3. **CIFS verliert nichts, was es vorher wirklich hatte.** Da `CHANGE_NOTIFY` dort serverseitig
   ohnehin fehlt, war der heutige "Live"-Watcher für CIFS schon vorher nur ein Notbehelf, der sich
   in der Praxis auf den ergänzenden `_shallow_reconcile()`-Scan verlassen musste. Der Schnitt macht
   diesen faktischen Zustand nur explizit, statt ihn hinter einer gemeinsamen Codepfad-Fiktion zu
   verstecken.
4. **CIFS bekommt dafür einen tatsächlich besseren Scan** statt des heutigen pauschalen 5-Minuten-
   Crons mit ~289s Laufzeit unabhängig vom Änderungsvolumen: adaptiv pro Freigabe (oder sogar pro
   Top-Level-Unterordner einer Freigabe), mit Komplexitäts-Untergrenze nach FileBrowser-Quantum-
   Vorbild (Details bereits in `int_filemanager_filebrowser_scan_architektur_2026-09-23.md`,
   Abschnitt 3) — ruhige Freigaben laufen seltener, aktive öfter, ein einzelner teurer Teilbaum kann
   sich nicht in eine Dauerschleife hineinmanövrieren.

Der tägliche Vollscan (`_scan_and_reconcile()`, am 2026-09-24 mit derselben Sorgfalt wie `watcher.py`
geprüft und als bereits gut incident-gehärtet bestätigt) bleibt unverändert das gemeinsame
Sicherheitsnetz über beide Bereiche hinweg — daran ändert dieser Schnitt nichts.

---

## 3. Was dieser Schritt NICHT ist

- **Keine Rückkehr zur globalen "DB ist Wahrheit"-Diskussion.** Externe Änderungen auf der lokalen
  Freigabe (z.B. direkt am Server, außerhalb von int_filemanager) bleiben weiterhin nur über den
  Watcher/Vollscan sichtbar, nicht über die DB-Autorität. Nur der ohnehin schon DB-geführte Anteil
  (Schreibvorgänge über int_filemanager selbst) wird als das benannt, was er bereits ist.
- **Kein Ersatz für den Papierkorb-Bauplan.** Der Watcher-Guard aus
  `../int_filemanager_papierkorb_odoo_umsetzung_2026-09-23.md` bleibt unabhängig davon nötig — er
  betrifft die Löschlogik, nicht die Watch-Baum-Aufteilung.
- **Kein einziger großer Umbau.** Die Trennung der Watch-Bäume, die 3 Watchdog-Fixes und die
  adaptive CIFS-Scan-Umstellung sind drei unabhängig umsetzbare, klar abgegrenzte Schritte — keiner
  davon setzt einen anderen voraus.

---

## 4. Einordnung in die bestehende Roadmap

Passt in `int_filemanager_grundsatz_explorer_ausbau_2026-09-23.md`, Abschnitt 3, am ehesten neben
Punkt 2 ("Fundament") — vor dem Papierkorb (Punkt 3), da der Watcher-Guard des Papierkorbs auf
genau dem Watch-Baum aufsetzt, der hier stabilisiert wird. Kein neuer eigener Platz in der
Reihenfolge nötig, aber sollte vor der Papierkorb-Umsetzung angegangen werden, damit der
Watcher-Guard nicht auf einem bekanntermaßen instabilen Fundament aufbaut.
