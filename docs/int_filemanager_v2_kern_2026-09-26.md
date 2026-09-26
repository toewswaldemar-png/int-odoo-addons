# int_filemanager 2 – Kern

Stand 2026-09-26. **Kurzfassung zum Prüfen und Freigeben.** Die Einzelheiten, Messungen und Belege stehen im
ausführlichen Konzept `int_filemanager_v2_konzept_2026-09-26.md` (Verweise wie "→ K 5" = Konzept Abschnitt 5).
Bei einem Widerspruch zwischen beiden gilt das Konzept; ein Widerspruch ist ein Fehler und wird in beiden behoben.

---

## 1. Worum es geht

Die Dateien vom Share `Daten` (Tower, ca. 1,8 TB) werden in einen neuen Dateimanager **in Odoo** übernommen. Danach
**schreibt nur noch Odoo** die Dateien. Niemand sonst ändert sie direkt auf der Platte – kein Explorer über SMB, kein
anderes Programm. Genau das direkte Schreiben von außen war die Ursache fast aller Fehler des heutigen Moduls
(→ K 1, DB-Vorrang-Konzept 19/20).

## 2. Die Grundregeln

Diese Regeln gelten immer, auch bei Absturz und Last. Jede hat Tests (→ K 2).

| # | Regel | in einfachen Worten |
|---|---|---|
| I1 | Nur Odoo schreibt in den Dateispeicher. | Keine Hintertür auf die Dateien. |
| I2 | Ein gespeicherter Inhalt wird nie verändert. | Neue Fassung = neue Datei im Speicher, benannt nach ihrer Prüfsumme. |
| I3 | Erst die Datenbank, dann die Wirkung nach außen. | Mails, Umwandlungen usw. erst, wenn der Vorgang sicher gespeichert ist. |
| I4 | Inhalte werden erst gelöscht, wenn nichts mehr auf sie verweist. | Kein Datenverlust durch Aufräumen. |
| I5 | Nichts wird gelöscht, nur weil es nicht gesehen wurde. | Kein Watcher, kein Scan, der Dateien entfernt. |
| I6 | Jede gespeicherte Fassung ist wiederherstellbar. | Versionen und Papierkorb. |
| I7 | Rechte prüft nur Odoo. | Kein Umgehen über Admin-Rechte im Code. |
| I8 | Verweise über Nummern (IDs), nie über Pfade. | Umbenennen und Verschieben brechen nichts. |
| I9 | Jeder Vorgang ganz oder gar nicht; Wiederholungen erzeugen keine Doppelungen. | Doppelklick, Abbruch, erneutes Senden sind harmlos. |
| I10 | Odoo selbst wird nicht verändert. | Updates bleiben möglich. |
| I11 | Fremde Dateiformate werden außerhalb von Odoo verarbeitet. | Vorschaubilder/OCR in einem eigenen Container. |
| I12 | Keine ganzen großen Dateien im Arbeitsspeicher. | Hoch- und Herunterladen als Datenstrom. |

## 3. Aufbau

```text
 Browser (Odoo-Oberfläche, ONLYOFFICE)          Scanner / Handy / Kopien
        │                                              │
        ▼                                              ▼
 nginx (HTTPS, liefert Dateien direkt aus)      Eingangsordner (Samba, nur hineinlegen)
        │                                              │ Odoo holt ab
        ▼                                              ▼
 Odoo (Prefork) ── Datenbank (PostgreSQL) ── Dateispeicher (nur Odoo schreibt)
        │
        └── Umwandler-Container (Vorschaubilder, Texterkennung)
```

- **Datenbank:** Ordner, Dateien, Versionen, Rechte, Tags, Status, Texterkennung (→ K 4).
- **Dateispeicher:** eigener Ordner auf dem Array; jede Fassung einmal, benannt nach ihrer SHA-256-Prüfsumme; gleiche
  Inhalte werden nur einmal gespeichert (→ K 5). `ir.attachment` reicht dafür nicht (kein Datenstrom, → K 5).
- **nginx** liefert Downloads direkt von der Platte, Odoo prüft nur die Rechte (→ K 8).

## 4. Was man damit tun kann – zum Start

| Kann | Wie |
|---|---|
| Ordner und Dateien verwalten | Odoo-Oberfläche: anlegen, umbenennen, verschieben, kopieren, löschen (Papierkorb 30 Tage) |
| Hochladen | im Browser, auch ganze Ordner und große Dateien (in Stücken, abgebrochene Uploads werden fortgesetzt, → K 7) |
| Herunterladen | einzeln oder als ZIP |
| Office-Dateien bearbeiten | im Browser mit ONLYOFFICE (→ K 10) |
| Andere Dateien bearbeiten | herunterladen, lokal bearbeiten, hochladen – wird eine neue Version; wer inzwischen geändert hat, bekommt einen Hinweis statt stillem Überschreiben |
| Versionen | jede Fassung bleibt, wiederherstellbar (unbegrenzt) |
| Suchen | nach Namen, nach Inhalt (Texterkennung), nach Tags/Status/Kontakt |
| Einliefern | Scanner, Handy, Kopien in den Eingangsordner legen; Odoo übernimmt (→ K 11.1) |
| Teilen | Freigabe-Links mit Ablauf, Kundenportal |

**Zum Start nicht:** Netzlaufwerk im Explorer, Word/Excel am Desktop direkt vom Server öffnen, Programme, die mit
Ordnern und Pfaden arbeiten (z. B. Audio-Projekte). Ob und wie ein Netzlaufwerk dazukommt, wird nach der Nutzung
entschieden; zwei Wege sind vorbereitet (→ K 11, K 19.10, K 19.14).

## 5. Die wichtigsten Bausteine im Datenmodell

| Baustein | ist |
|---|---|
| **Knoten** (`int_filemanager.node`) | ein Ordner oder eine Datei: Name, übergeordneter Ordner, Rechte-Bereich, aktuelle Fassung, Tags, Status. Namen je Ordner eindeutig, **ohne Rücksicht auf Groß/Klein** (wie Windows). Leere Datei = Knoten ohne Fassung. |
| **Fassung** (`int_filemanager.revision`) | eine Version einer Datei; wird nie verändert |
| **Inhalt** (`int_filemanager.blob`) | eine Datei im Dateispeicher (Prüfsumme, Größe) |
| **Rechte-Bereich** (`int_filemanager.scope`) | wer lesen, schreiben, verwalten, endgültig löschen darf; gilt für einen Ordner samt Inhalt |

→ Einzelheiten K 4.

## 6. Wie Schreiben funktioniert

Jeder Schreibvorgang läuft gleich ab (→ K 6):
1. Rechte prüfen, Vorgangsnummer prüfen (gegen Doppelungen).
2. Falls neuer Inhalt: als Datenstrom in den Dateispeicher, Prüfsumme dabei berechnen. Das ist harmlos, falls danach
   etwas schiefgeht – der Aufräumjob entfernt unbenutzte Inhalte.
3. Kurze Datenbank-Transaktion: Knoten/Fassung anlegen oder ändern, dabei prüfen, ob inzwischen jemand anderes
   geändert hat.
4. Erst danach Wirkungen nach außen.

Umbenennen, Verschieben und Kopieren ändern nur die Datenbank – keine Datei wird bewegt oder kopiert.

## 7. Rechte

Zum Start **minimal**: ein Bereich "Alle" und der heutige Schutzordner als eigener Bereich. Unterordner mit engeren
Rechten bekommen bei Bedarf einen eigenen Bereich. Rechte gelten für alle Wege gleich (Liste, Suche, Vorschau,
Download, Freigabe-Links); öffentliche Methoden arbeiten nie mit Admin-Rechten auf Nutzereingaben (→ K 12).
**Wichtig:** Odoo 19 macht jede öffentliche Modellmethode über seine externe Schnittstelle **JSON-2** für jeden
Nutzer mit API-Schlüssel aufrufbar – öffentlich ist deshalb nur, was mit beliebigen Argumenten sicher ist; alles
andere bleibt intern (→ K 12, K 19.16).

## 8. Übernahme des Bestands

Der Bestand wird **kopiert**, nicht verschoben (→ K 14):
1. Erstkopie im laufenden Betrieb (wiederholbar, fortsetzbar): ca. 18 Stunden für 1,8 TB (gemessen 27,5 MB/s).
   Etwa 7 % sind doppelte Inhalte und werden nur einmal gespeichert; Platzbedarf ca. 1,7 TB, frei sind ca. 3,7 TB.
2. Tags, Status, Kontakte, Texterkennung, Freigaben und alte Versionen aus dem heutigen Modul übernehmen.
3. Änderungen seit der Erstkopie nachziehen.
4. Share schreibgeschützt, letzter Abgleich, umschalten.
5. Prüfen: Anzahl und Prüfsumme jeder Datei gegen die Quelle.
6. Bis zur Abnahme bleibt der alte Stand schreibgeschützt erhalten – **Rückweg möglich**.

## 9. Betrieb

- Odoo im Prefork-Modus (mehrere Prozesse), nginx davor, Umwandler-Container (→ K 13).
- Aufräumjobs: unbenutzte Inhalte, abgebrochene Uploads, Temp-Dateien.
- Backup: Datenbank **und** Dateispeicher gehören zusammen; da Inhalte nie verändert werden, reicht für den Speicher
  ein inkrementelles Backup.
- Überwachung: Upload-Reste, fehlerhafte Vorschauen, Prüfsummenfehler, freier Platz.
- HM-SRV behält vorerst das heutige Modul; dort ist die Sicherheitslücke N1 separat zu schließen.

## 10. Entscheidungen

| Datum | Entscheidung |
|---|---|
| 2026-09-26 | Vollständig als Odoo-Addon; Eigenbau nur, wo Odoo nachweislich nicht reicht |
| 2026-09-26 | Odoo ist alleiniger Schreiber |
| 2026-09-26 | Bestand kopieren, kein Hardlink |
| 2026-09-26 | Ganzer Share; Versionen unbegrenzt; Papierkorb 30 Tage; Rechte minimal |
| 2026-09-26 | HM-SRV bleibt vorerst beim heutigen Modul |
| 2026-09-26 | Modellnamen mit Modulpräfix (`int_filemanager.node` usw.) nach Odoo-Konvention |
| 2026-09-26 | Code nach Odoo-/OCA-Konventionen: Englisch in Code, Kommentaren und Commits; Oberflächentexte englisch + deutsche Übersetzung (`i18n/de.po`) |
| 2026-09-26 | Prüfwerkzeuge: pre-commit (OCA-Vorlage, nur neuer Code) und Odoos `test_lint`; keine GitHub Action |
| 2026-09-26 | Start ohne Netzlaufwerk, mit Eingangsordner; Netzlaufwerk später nach Nutzung (WebDAV über `odoo fmdav` oder SMB über Odoo-FUSE) |

## 11. Reihenfolge mit Abnahme

Jeder Schritt ist erst fertig, wenn seine Abnahme erfüllt ist; der nächste beginnt erst danach. **Für jeden Schritt
gilt zusätzlich:** pre-commit und Odoos `test_lint` grün, `i18n/de.po` vollständig (keine englischen Texte in der
deutschen Oberfläche). Jeder Schritt wird
vor der Abnahme von einer zweiten Instanz gegengelesen (`codex -p review`). *(Abnahmekriterien: Vorschlag, mit der
Freigabe verbindlich.)*

| # | Schritt | fertig, wenn |
|---|---|---|
| 3 | **Fundament:** Prüfwerkzeuge einrichten, dann Datenmodell, Dateispeicher, Schreibwege, Rechte | je Grundregel ein grüner Test, für I1–I6 und I9 auch mit Abbruch mitten im Vorgang; Rechte-Tests für Nicht-Admins über alle Wege; kein `sudo` auf Nutzereingaben |
| 4 | **Oberfläche** auf das neue Modell | alle Funktionen aus Abschnitt 4 (außer Office/Einliefern) in der Oberfläche bedienbar; Upload 3 GB mit Abbruch und Fortsetzen |
| 5 | **Vorschau/Texterkennung** im Umwandler | Vorschau für die häufigen Formate; Fehler sichtbar statt still; Odoo-Prozess bleibt bei defekten Dateien stabil |
| 6 | **Office** (ONLYOFFICE im Browser) | Speichern ergibt neue Fassung; zwei gleichzeitige Bearbeitungen führen zu Hinweis statt Verlust |
| 7 | **Eingangsordner** | Scanner-Datei wird erst nach Fertigschreiben übernommen; kein Duplikat nach Abbruch; Fehlerablage funktioniert |
| 8 | **Übernahme** des Bestands | Probelauf auf der Testinstanz vollständig; Zählung und Prüfsummen stimmen; Rückweg geprobt |
| 9 | später: **Netzlaufwerk** entscheiden | nach Erfahrungen aus 4–8 |

## 12. Bewusst nicht (vorerst)

- Kein Netzlaufwerk zum Start; kein Samba + Watcher (zweiter Schreiber, → K 19.15).
- Keine Änderung am Odoo-Kern.
- Keine Erweiterungen, bevor das Fundament im Alltag trägt.

## 13. Offene Risiken

- **Viel Eigenbau** (Dateispeicher, Upload in Stücken, Umwandler) für einen Server mit heute einem Nutzer – bewusst
  entschieden, Umfang bleibt klein gehalten.
- **Odoo-Details, auf die wir uns verlassen** – alles läuft in Odoo, ist aber keine fest zugesicherte Schnittstelle:
  (a) Odoos offizielle Option `x_sendfile` übergibt Downloads nur für Dateien unterhalb von `data_dir/filestore` an
  nginx (dort liegt deshalb der Dateispeicher); (b) für die Rechte werden Odoos interne Methoden `_check_access`/`_search`
  überschrieben (wie in Odoos `mail.activity`). Durch Tests abgesichert, Odoo-Updates nur nach grünem Testlauf auf der
  Testinstanz. Ohne nginx liefert Odoo selbst aus – dann belegt jeder Download einen Odoo-Prozess für die ganze Dauer
  und lange Downloads laufen ins Zeitlimit. Deshalb bleibt es bei Odoos offizieller Auslieferung über `x_sendfile`:
  Odoo prüft Rechte und Datei, nginx liefert die Bytes.
- **`fsync` auf dem Array** kostet ~28 ms je Datei (Absturzsicherheit); ein Dateispeicher auf SSD würde es verkürzen –
  Entscheidung beim Betrieb.
- **Nicht mit echtem Word/Excel getestet** (nur nachgespielt), betrifft erst ein späteres Netzlaufwerk.

## 14. Wo was steht

| Thema | Konzept |
|---|---|
| Grundregeln, Aufbau, Datenmodell | K 2–4 |
| Dateispeicher, Schreibwege, Upload | K 5–7 |
| Vorschau, Suche, Office | K 8–10 |
| Netzlaufwerk-Vorarbeit, Eingangsordner | K 11, 19.4–19.15 |
| Rechte, Betrieb, Übernahme | K 12–14 |
| Tests | K 16 |
| Messungen und Prototypen | K 19 |
