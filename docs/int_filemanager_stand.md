# int_filemanager – Stand und nächste Schritte (Einstieg für neue Sitzungen)

Stand 2026-10-02. Branch `feature/int-filemanager-v2` (der bisherige Stand liegt auf `master`, Tag `int_filemanager-v1`), Modulversion 19.0.1.23.0.
Der Code ist maßgeblich; **warum** etwas so ist, steht in `int_filemanager_entscheidungen.md`, die Grundregeln I1–I13 ebenfalls dort. Der Aufbau steht in Abschnitt 7. Alte, ausführliche Dokumente: Git-Tag `docs-vor-aufraeumen-2026-10-02`.

## 1. Was steht

Jeder Schritt ist erst fertig, wenn seine Abnahme erfüllt ist; der nächste beginnt danach. **Für jeden Schritt zusätzlich:** pre-commit, `test_lint` und
odoo-ls ohne Befund im eigenen Code, `i18n/de.po` vollständig, Gegenlese durch ein zweites Modell.

| Schritt | fertig, wenn | Stand |
|---|---|---|
| 3 Fundament (Datenmodell, Blob-Speicher, Schreibwege, Rechte) | je Grundregel ein grüner Test, für I1–I6 und I9 auch mit Abbruch mitten im Vorgang; Rechte-Tests für Nicht-Admins über alle Wege **und alle Tabellen**; kein `sudo` auf Nutzereingaben | fertig; 17 Rennszenarien (`tools/v2check/race.sh`) auf Tower zuletzt 2026-09-30 grün |
| 4 Oberfläche (Explorer auf `int_filemanager.node`) | alle Funktionen (außer Office/Einliefern) in der Oberfläche bedienbar; Upload 3 GB mit Abbruch und Fortsetzen | gebaut; Abnahme frei durch den Nutzer, nicht per Checkliste |
| 5 Vorschau, Text, Metadaten, OCR mit Wortpositionen | Vorschau für die häufigen Formate (inkl. HEIC/RAW/TIFF, Video-Standbild, Office, PDF, Scans mit OCR); Metadaten; Fehler sichtbar statt still; Odoo-Prozess bleibt bei defekten Dateien stabil; Test, dass Odoo Ergebnisse nie dekodiert (I13) | fertig im Server; Verwalter-Werkzeuge (Diagnose, "neu erzeugen", Konfiguration) **nicht** gebaut |
| 5 Werterkennung | (eigene Scheiben, siehe Entscheidungen 5) | Server (Katalog, Erkennung, Lernen pro Absender, Spalten-/Rechte-Entwurf), Volltextsuche, Formularfelder, **Eigenschaften-Formular** (Rechtsklick → Eigenschaften) gebaut; Wortklick nur für PDF |
| 6 Office (ONLYOFFICE) | Speichern ergibt neue Fassung; zwei gleichzeitige Bearbeitungen führen zu Hinweis statt Verlust | offen |
| 7 Eingangsordner | Scanner-Datei wird erst nach Fertigschreiben übernommen; kein Duplikat nach Abbruch; Fehlerablage funktioniert | offen |
| 8 Übernahme des Bestands | Probelauf auf der Testinstanz vollständig; Zählung und Prüfsummen stimmen; Rückweg geprobt | offen |
| 9 Netzlaufwerk | nach Erfahrungen aus 4–8 entscheiden | später |

**Ideenkatalog** (`int_filemanager_paperoffice_ideenkatalog_2026-10-01.md`): A1 (Wortklick) nur für PDF umgesetzt, A2 teilweise (Umrandung im Dokument, Warnsymbol bei unsicheren Werten, aber keine Markierung "automatisch gelesen" am Feld), A7 nur geplant; C10, B5, E4, F1, F3, F5 und H6 sind schon vorhanden oder im Neubau vorgesehen; alle anderen nicht begonnen.

Zuletzt geprüft (2026-10-01): pre-commit grün, 555 Odoo-Tests, 76 Umwandler-Tests, 72 Node-Tests, `v2check` ohne neue Befunde
(12 alte Befunde im bestehenden Code unverändert). **Neu 2026-10-02:** Prüfautomatik und Odoo-19-Regeln aus `master` übernommen
(`pruefautomatik_2026-10-02.md`, `odoo_regeln/`); Docker-Läufe auf Tower und pre-commit auf Windows noch nicht verifiziert.

## 2. Nächste Schritte (in dieser Reihenfolge)

1. **Rückmeldung des Nutzers zum Eigenschaften-Formular** abwarten (Zoom auf den Wert, Rahmenrand, Layout).
2. **Prüf-Fenster entfernen:** `static/src/int_filemanager/v2/value_review/` (Client-Aktion, XML, SCSS, Tests), Menüpunkt `int_check_values`,
   `onCheckValues` in `controller_mutations.js`, Übersetzungen. Vorher `viewer_overlay.js`, `value_review_geometry.js`,
   `value_review_edits.js` (+ Node-Tests) nach `properties/` verschieben und Importe nachziehen.
3. **Wortklick fertigstellen:** Bilder (Wortschicht über `<img>`), Handy (zum Dokument scrollen und zurück).
4. **A7 Wörterbuch** für OCR-Korrekturen: Modell `int_filemanager.ocr_correction`, bearbeitbare Liste, reine Funktion `apply_corrections` in
   `_recognition_page`, nur bei `ocr != "none"`. Offene Entscheidungen: sofort wirken lassen, Sprache weglassen, nur Einzelwörter.
5. **Ideenkatalog** `int_filemanager_paperoffice_ideenkatalog_2026-10-01.md` (A1–H6) mit dem Nutzer durchgehen. Offene Entscheidungen dort:
   Was ist der "Dokumenttyp" (Tag/Status/Feld)? Virtuelle Ordner? Notizen auf Bereichen und Stempel? Papier-Workflows?
6. **Gegenlese-Befunde** (Codex, 2026-10-01) bearbeiten, siehe 3.
7. Danach Schritt 6 (Office), 7 (Eingangsordner), 8 (Übernahme).

**Vor Schritt 6/8 klären:**
- **ONLYOFFICE-Zertifikat** (heute nur auf einem Rechner vertraut; die AD-CAs sind offline); ohne Lösung ist der Branch für Word/Excel ein Rückschritt gegenüber `master`.
- **Notfall-Export ohne Odoo** (rekursive SQL-Abfrage über `parent_id` + Kopie aus `blobs/ab/cd/<sha256>`; auf HM-SRV-Testinstanz 33 Ordner,
  219 Dateien, 0 Prüfsummenfehler): als festes Werkzeug ins Repo (kopieren statt Hardlink, Änderungsdatum übernehmen, Prüfsumme je Datei),
  Probelauf gegen das Backup in die Abnahme von Schritt 8.
- **Blob-Prüflauf:** `adopt_hashed` vertraut beim Zusammenlegen einer vorhandenen Datei dem Hash, ohne nachzurechnen; ein beschädigter Blob
  würde eine gute neue Kopie verdrängen. Cron, der Blobs nachrechnet und meldet, plus Ersetzen eines als beschädigt bekannten Blobs.
- Nachholen des ganzen Bestands (Kacheln für 209k Bilder) nur gedrosselt vorgesehen, noch nicht am echten Bestand gemessen.
- Umwandler-Image `fmconverter:dev` ist nur auf Tower gebaut, noch kein Deployment-Weg.
- Netzlaufwerk-Entscheidung (WebDAV `odoo fmdav` oder SMB über Odoo-FUSE) erst nach Nutzung, Hintergrund in den Entscheidungen, Abschnitt 3.

**Aus der früheren Dauerlauf-Liste noch offen (Analyse, nichts bauen):** (A5) die Modelle von `master` (`extracted_value`, Muster) gegen das Schema des Branches legen,
Vorschlag "übernehmen / verwerfen / neu erkennen" je Feld an einer Kopie; (A6) alle seit dem Tag `int_filemanager-v1` geänderten Dateien mit zweitem
Modell gegenlesen und Befundliste ablegen; (A7) fehlt dem Image `odoo:19.0-hm-test` noch ein 19.0-Sicherheits-Fix, Update-Weg vorschlagen.

## 3. Bekannte Mängel und offene Befunde

- Gesamtbetrag der Henrich-Rechnung hat keinen gespeicherten Ort (springt nicht).
- Gedrehte PDF-Seiten bekommen keinen Zoom auf den Wert.
- Weitere unsichtbare Textarten (Schrift < 1 pt, außerhalb der Seite) werden nicht gefiltert; weiß gefüllter Text mit schwarzer Kontur wird entfernt (bekannte Grenze).
- Modulversion nicht erhöht (19.0.1.23.0).
- **Codex-Gegenlese 2026-10-01:** (1) *echt:* `ViewerOverlay.attach()` lädt die Wörter **aller** Seiten sofort (`page_words` je Seite), bei langen PDFs viele
  Aufrufe; Fix: erst im Wortmodus oder nur sichtbare Seiten. (2) *plausibel, im Browser prüfen:* ein getippter Wert geht verloren, wenn man mit dem
  Speichern-Kürzel speichert, ohne das Feld zu verlassen (`useInputField` hängt am Bus des inneren `Record`); Fix: im Werte-Widget `hooks.onRootLoaded`
  das innere Record merken und das Ereignis des Formulars dorthin weiterreichen. (3) *selten:* Kontaktwechsel lässt die Vorschläge beim alten
  Absender; Fix: nach Kontaktwechsel `values_json` neu lesen.
- Vom ersten Handtest (2026-09-28) noch zu prüfen: `rememberBase` wird nie aufgerufen (`uploads_service.js`), "Neue Fassung" nimmt dann die beim
  Seitenladen aktuelle Fassung als Basis; Meldung "frühere Uploads wurden unterbrochen" kann veraltet sein (`upload_manager.js`).
- Nach neuer Wörter-Spec werden vorhandene `words`-Ergebnisse gelöscht und im Hintergrund neu gelesen; bis dahin findet die Volltextsuche diese PDFs nicht.
- Live-Datenbanken auf `pg_trgm` nicht geprüft; die Migration legt die Erweiterung an, wenn der DB-Benutzer darf, sonst Warnung.
- Der Code von `master` (u. a. `native_ui/`, `models/filemanager_file.py`, `publish_service.py`) verweist in Kommentaren noch auf gelöschte Dokumente (Papierkorb, Ausbau, native UI, DB-Vorrang-Konzept); die Verweise verschwinden mit dem Entfernen des alten Codes in Schritt 8, die Dokumente stehen im Git-Tag.
- Sicherheitslücke **N1** auf `master` (HM-SRV) ist **nicht** gefixt. In `web-filemanager` liegen nicht committete Änderungen des Nutzers (unberührt lassen).

## 4. Arbeitsweise des Nutzers

- **Commit erst auf Ansage.** Test-Instanz ohne Rückfrage aktualisieren: `bash tools/v2check/ui_instance.sh` (aktualisiert mit `--i18n-overwrite`).
- Odoo-Code gründlich auf native Bausteine prüfen; Ursachen im Code mit Test beheben, keine Handeingriffe in DB/Container.
- Oberfläche testet der Nutzer frei im Browser; keine Checkliste, keine Browser-Automatik. Nur kurze Tests (gezielte Klassen, Node-JS-Tests, `jscheck`);
  volle Suite/`v2check` nur bei Server-Änderungen oder am Ende.
- Abdeckung offenlegen (vollständig vs. Stichprobe), Alternativen zeigen, Fragen einzeln durchgehen, Produktentscheidungen beim Nutzer lassen.
- Dokumentation: kein Konzeptdokument je Feature. Vor einem größeren Feature eine halbe Seite (Ziel, offene Fragen), nach der Umsetzung das Ergebnis in
  die Entscheidungen und die Notiz löschen.

## 5. Testumgebung (Tower, `ssh unraid`)

- Test-Instanz der Oberfläche: `http://192.168.188.67:8085`, Login-Datei `/mnt/user/appdata/fmtest/v2ui/LOGIN.txt` auf Tower (der Nutzer tippt das
  Passwort selbst). Testdateien: Henrich-Rechnung (Knoten 2) und "Bescheid A/B/C" (selbst erzeugt, ungefährlich).
- Test-Image `odoo:19.0-hm-test` (19.0-20260908); das Live-Tag `odoo:19.0-hm` ist unberührt. Test-PostgreSQL `fmtest_pg`.
- Prüfwerkzeuge: `tools/v2check/v2check.sh [--quick]` (odoo-ls + `test_lint`, filtert auf neue/geänderte Dateien), `race.sh` (Rennszenarien in
  Wegwerf-Umgebung), `tests.sh`, `jscheck.sh`, `owlcheck.sh`, `i18n_export.sh`. pre-commit: `py -3.13 -m pre_commit` (Programme unter `%APPDATA%\Python\Python313\Scripts`).
- Blob-Speicher der Tests: Share `fmv2blobs` (nur disk3, kein Cache, keine SMB-Freigabe, ca. 53 GB).
- **Private Testsammlung** (nie ins Repo, nie in Berichte mit Werten): `/mnt/user/test/werterkennung/` (528 Dateien, 513 PDFs), abgeleitete Wortlisten
  `/mnt/user/test/werterkennung_words_v3/`, Messdaten und Bewertungen `/mnt/user/test/werterkennung_w6/` (`chmod 700`). Messwerkzeuge
  (`w6_sample.py`, `w6_recheck.py` für den Regressionstest nach jeder Regeländerung, `keyword_search.py` u. a.) nur noch im Git-Tag `docs-vor-aufraeumen-2026-10-02`, Pfad `docs/prototypes/werterkennung/` (mit README). Formate-Testsammlung: `/mnt/user/test/formats` (95 Dateien, `tools/fmconverter/run_formats.py`).
- Prototyp-Container `fmv2_*`, `fmtest_*`, `fmreal_odoo` auf Tower sind WebDAV-/Prototyp-Reste: **vor dem Löschen den Nutzer fragen**.
- **HM-SRV** ist von hier nicht erreichbar; vor jedem Odoo-Image-Update DB-Kollation prüfen (siehe Entscheidungen 2).

## 6. Stolpersteine

- Neue Wörter-Spec nur mit Eintrag in `server.py` `WORDS_SPECS`, sonst 400 vom Umwandler.
- gs-Test-PDFs brauchen ≥ 20 sichtbare Zeichen, sonst liest der Umwandler per OCR.
- pdfminer nimmt für Standardschriften (Helvetica …) die Maße aus seinen Tabellen, nicht aus dem Beschreiber.
- pdf.js entfernt fremde Kinder einer Seite beim Neuzeichnen (MutationObserver in `viewer_overlay.js`).
- Bash-Heredocs mit `'''` oder `\n` in Python-Strings brechen: Dateien mit dem Schreibwerkzeug ändern.
- `pre-commit` prüft nur gestagte Dateien; der Hook formatiert JS/XML/Python um (danach neu stagen).
- Startkatalog ist `noupdate`: bestehende Datenbanken bekommen neue Stichwörter/Felder nicht von selbst.
- Wer `odoo shell`/`odoo -u` gegen die Watcher-DB startet, startet einen zweiten Watcher (Entscheidungen 8).

## 7. Aufbau im Überblick

```text
 Browser (Odoo-Oberfläche, ONLYOFFICE)          Scanner / Handy / Kopien
        │                                              │
        ▼                                              ▼
 nginx (HTTPS, liefert Dateien direkt aus)      Eingangsordner (Samba, nur hineinlegen)
        │                                              │ Odoo holt ab
        ▼                                              ▼
 Odoo (Prefork) ── PostgreSQL ── Blob-Speicher (nur Odoo schreibt)
        │
        └── Umwandler-Container (Vorschaubilder, Texterkennung, Metadaten)
```

- **Ziel:** die Dateien vom Share `Daten` (Tower, ca. 1,8 TB) kommen in den neuen Dateimanager in Odoo; danach schreibt nur noch Odoo.
- **Bausteine im Datenmodell:** Knoten (`int_filemanager.node`: Ordner oder Datei, Name je Ordner ohne Groß/Klein eindeutig, auch eine leere Datei hat eine
  Fassung), Fassung (`.revision`, wird nie verändert), Inhalt (`.blob`, Datei im Speicher mit Prüfsumme), abgeleitete Daten (`.derivative`: Vorschau, Text,
  Metadaten, nur über eine eigene Route mit den Rechten der Fassung ausgeliefert), Rechte-Bereich (`.scope`: wer lesen, schreiben, verwalten, endgültig löschen darf).
- **Schreiben** läuft immer gleich: Rechte und Vorgangsnummer prüfen → neuer Inhalt als Datenstrom in den Speicher (Prüfsumme dabei, Zwischendatei bleibt bis zum
  Abschluss, unbenutzte räumt der Aufräumjob) → kurze Datenbank-Transaktion mit Prüfung, ob inzwischen jemand anderes geändert hat → erst danach Wirkungen nach außen.
  Umbenennen, Verschieben und Kopieren ändern nur die Datenbank. Treffen zwei Vorgänge aufeinander, wartet der zweite kurz oder wird wiederholt; Odoo erledigt das
  nicht von selbst, der Code regelt es ausdrücklich.
- **Rechte** zum Start minimal (Bereich "Alle" und der heutige Schutzordner) und für alle Wege gleich (Liste, Suche, Vorschau, Download, Freigabe-Links).
- **Betrieb:** Odoo im Prefork-Modus, nginx davor, Umwandler-Container, Aufräumjobs für unbenutzte Inhalte, abgebrochene Uploads und Temp-Dateien. Überwachen:
  Upload-Reste, fehlerhafte Vorschauen, Prüfsummenfehler, freier Platz. Schlafende Platten brauchen beim ersten Zugriff einige Sekunden.

## 8. Übernahme des Bestands (Plan für Schritt 8)

Der Bestand wird **kopiert**, nicht verschoben:
1. Erstkopie im laufenden Betrieb (wiederholbar, fortsetzbar): ca. 18 Stunden für 1,8 TB (gemessen 27,5 MB/s). Etwa 7 % sind Dubletten und werden nur einmal
   gespeichert; Platzbedarf ca. 1,7 TB, frei sind ca. 3,7 TB.
2. Tags, Status, Kontakte, Texterkennung, Freigaben und alte Versionen aus dem Stand von `master` übernehmen.
3. Änderungen seit der Erstkopie nachziehen.
4. Share schreibgeschützt, letzter Abgleich, umschalten.
5. Prüfen: Anzahl und Prüfsumme jeder Datei gegen die Quelle.
6. Bis zur Abnahme bleibt der alte Stand schreibgeschützt erhalten (**Rückweg möglich**).
