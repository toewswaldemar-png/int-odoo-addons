# int_filemanager 2 – Kern

Stand 2026-09-26, überarbeitet 2026-09-27 nach der Code-Prüfung, **freigegeben am 2026-09-27.** Architekturüberblick: Regeln, Aufbau, Reihenfolge mit Abnahmekriterien. Begründungen und verworfene Wege:
`int_filemanager_v2_entscheidungen.md`; aktueller Stand: `int_filemanager_v2_stand.md`. Gilt bei Widerspruch der Code.

---

## 1. Worum es geht

Die Dateien vom Share `Daten` (Tower, ca. 1,8 TB) werden in einen neuen Dateimanager **in Odoo** übernommen. Danach
**schreibt nur noch Odoo** die Dateien. Niemand sonst ändert sie direkt auf der Platte – kein Explorer über SMB, kein
anderes Programm. Genau das direkte Schreiben von außen war die Ursache fast aller Fehler des heutigen Moduls.

## 2. Die Grundregeln

Diese Regeln gelten immer, auch bei Absturz und Last. Jede hat Tests.

| # | Regel | in einfachen Worten |
|---|---|---|
| I1 | Nur Odoo schreibt in den Dateispeicher. | Keine Hintertür auf die Dateien. |
| I2 | Ein gespeicherter Inhalt wird nie verändert. | Neue Fassung = neue Datei im Speicher, benannt nach ihrer Prüfsumme. |
| I3 | Erst die Datenbank, dann die Wirkung nach außen. | Mails, Umwandlungen usw. erst, wenn der Vorgang sicher gespeichert ist. |
| I4 | Inhalte werden erst gelöscht, wenn nichts mehr auf sie verweist **und** eine Schonfrist abgelaufen ist; im Zweifel bleiben sie. | Kein Datenverlust durch Aufräumen, auch nicht, wenn gerade jemand denselben Inhalt hochlädt. |
| I5 | Nichts wird gelöscht, nur weil es nicht gesehen wurde. | Kein Watcher, kein Scan, der Dateien entfernt. |
| I6 | Jede gespeicherte Fassung ist wiederherstellbar. | Versionen und Papierkorb. |
| I7 | Rechte prüft nur Odoo – für jede Tabelle und jeden Zugriffsweg. | Auch Versionen und Inhalte sind geschützt, nicht nur Ordner und Dateien; Admin-Rechte im Code erst nach der Prüfung. |
| I8 | Verweise über Nummern (IDs), nie über Pfade. | Umbenennen und Verschieben brechen nichts. |
| I9 | Was Nutzer sehen, ändert sich ganz oder gar nicht; Wiederholungen und gleichzeitige Zugriffe erzeugen keine Doppelungen. | Doppelklick, Abbruch, erneutes Senden, zwei gleichzeitige Uploads sind harmlos. |
| I10 | Odoo selbst wird nicht verändert. | Updates bleiben möglich. |
| I11 | Fremde Dateiformate werden außerhalb von Odoo verarbeitet. | Vorschaubilder/OCR in einem eigenen Container. |
| I12 | Keine ganzen großen Dateien im Arbeitsspeicher. | Hoch- und Herunterladen als Datenstrom. |
| I13 | Odoo öffnet keine fremden Dateibytes, auch nicht die Ergebnisse des Umwandlers. | Vorschaubilder und Text liegen im Dateispeicher und werden nur ausgeliefert, nicht von Odoo gelesen. |

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
        └── Umwandler-Container (Vorschaubilder, Texterkennung, Metadaten)
```

- **Datenbank:** Ordner, Dateien, Versionen, Rechte, Tags, Status, Texterkennung.
- **Dateispeicher:** eigener Ordner auf dem Array; jede Fassung einmal, benannt nach ihrer SHA-256-Prüfsumme; gleiche
  Inhalte werden nur einmal gespeichert. `ir.attachment` reicht dafür nicht (kein Datenstrom). Auch Vorschaubilder und Text liegen im
  Dateispeicher.
- **nginx** liefert Downloads direkt von der Platte, Odoo prüft nur die Rechte.

## 4. Was man damit tun kann – zum Start

| Kann | Wie |
|---|---|
| Ordner und Dateien verwalten | Odoo-Oberfläche: anlegen, umbenennen, verschieben, kopieren, löschen (Papierkorb 30 Tage) |
| Hochladen | im Browser, auch ganze Ordner und große Dateien (in Stücken, abgebrochene Uploads werden fortgesetzt) |
| Herunterladen | einzeln oder als ZIP; große ZIPs (über ca. 500 MB) werden im Hintergrund gepackt, dann kommt eine Nachricht |
| Office-Dateien bearbeiten | im Browser mit ONLYOFFICE |
| Andere Dateien bearbeiten | herunterladen, lokal bearbeiten, hochladen – wird eine neue Version; wer inzwischen geändert hat, bekommt einen Hinweis statt stillem Überschreiben |
| Versionen | jede Fassung bleibt, wiederherstellbar (unbegrenzt) |
| Ansehen | Vorschaubilder für Fotos (auch HEIC, RAW), Video, Office und PDF; Scans werden per Texterkennung durchsuchbar. Erzeugt im Hintergrund, was auf dem Bildschirm steht, kommt zuerst |
| Suchen | nach Namen, nach Inhalt (Texterkennung), nach Tags/Status/Kontakt |
| Einliefern | Scanner, Handy, Kopien in den Eingangsordner legen; Odoo übernimmt eine Datei, wenn sie sich 2 Minuten nicht mehr ändert |
| Teilen | Freigabe-Links mit Ablauf, Kundenportal |

**Zum Start nicht:** Netzlaufwerk im Explorer, Word/Excel am Desktop direkt vom Server öffnen, Programme, die mit
Ordnern und Pfaden arbeiten (z. B. Audio-Projekte). Ob und wie ein Netzlaufwerk dazukommt, wird nach der Nutzung
entschieden; zwei Wege sind vorbereitet.

## 5. Die wichtigsten Bausteine im Datenmodell

| Baustein | ist |
|---|---|
| **Knoten** (`int_filemanager.node`) | ein Ordner oder eine Datei: Name, übergeordneter Ordner, Rechte-Bereich, aktuelle Fassung, Tags, Status. Namen je Ordner eindeutig, **ohne Rücksicht auf Groß/Klein** (wie Windows). Auch eine leere Datei hat eine Fassung. |
| **Fassung** (`int_filemanager.revision`) | eine Version einer Datei; wird nie verändert |
| **Inhalt** (`int_filemanager.blob`) | eine Datei im Dateispeicher (Prüfsumme, Größe) |
| **Abgeleitete Daten** (`int_filemanager.derivative`) | Vorschaubild, Vorschau-PDF, Text oder Metadaten zu einem Inhalt; erzeugt vom Umwandler, für Nutzer nicht direkt lesbar, ausgeliefert über eine eigene Route mit den Rechten der Fassung |
| **Rechte-Bereich** (`int_filemanager.scope`) | wer lesen, schreiben, verwalten, endgültig löschen darf; gilt für einen Ordner samt Inhalt |

## 6. Wie Schreiben funktioniert

Jeder Schreibvorgang läuft gleich ab:
1. Rechte prüfen, Vorgangsnummer prüfen (gegen Doppelungen).
2. Falls neuer Inhalt: als Datenstrom in den Dateispeicher, Prüfsumme dabei berechnen; die Zwischendatei bleibt bis
   zum Abschluss liegen. Das ist harmlos, falls danach etwas schiefgeht – der Aufräumjob entfernt unbenutzte Inhalte.
3. Kurze Datenbank-Transaktion: Knoten/Fassung anlegen oder ändern, dabei prüfen, ob inzwischen jemand anderes
   geändert hat.
4. Erst danach Wirkungen nach außen.

Treffen zwei Vorgänge aufeinander (gleicher Name, gleiche Datei), wartet der zweite kurz oder wird wiederholt. Odoo
erledigt das nicht von selbst, der Code regelt es ausdrücklich.

Umbenennen, Verschieben und Kopieren ändern nur die Datenbank – keine Datei wird bewegt oder kopiert.

## 7. Rechte

Zum Start **minimal**: ein Bereich "Alle" und der heutige Schutzordner als eigener Bereich. Unterordner mit engeren
Rechten bekommen bei Bedarf einen eigenen Bereich. Rechte gelten für alle Wege gleich (Liste, Suche, Vorschau,
Download, Freigabe-Links); öffentliche Methoden arbeiten nie mit Admin-Rechten auf Nutzereingaben.
**Wichtig:** Odoo 19 macht jede öffentliche Modellmethode für **jeden angemeldeten Nutzer** aufrufbar – über die
Schnittstelle der Oberfläche und über **JSON-2** (mit API-Schlüssel). Öffentlich ist deshalb nur, was mit beliebigen
Argumenten sicher ist; alles andere bleibt intern. Außerdem braucht **jede** Tabelle eigene Regeln: Odoo überträgt
die Rechte eines Ordners nicht von selbst auf Versionen und Inhalte.

## 8. Übernahme des Bestands

Der Bestand wird **kopiert**, nicht verschoben:
1. Erstkopie im laufenden Betrieb (wiederholbar, fortsetzbar): ca. 18 Stunden für 1,8 TB (gemessen 27,5 MB/s).
   Etwa 7 % sind doppelte Inhalte und werden nur einmal gespeichert; Platzbedarf ca. 1,7 TB, frei sind ca. 3,7 TB.
2. Tags, Status, Kontakte, Texterkennung, Freigaben und alte Versionen aus dem heutigen Modul übernehmen.
3. Änderungen seit der Erstkopie nachziehen.
4. Share schreibgeschützt, letzter Abgleich, umschalten.
5. Prüfen: Anzahl und Prüfsumme jeder Datei gegen die Quelle.
6. Bis zur Abnahme bleibt der alte Stand schreibgeschützt erhalten – **Rückweg möglich**.

## 9. Betrieb

- Odoo im Prefork-Modus (mehrere Prozesse), nginx davor, Umwandler-Container.
- Aufräumjobs: unbenutzte Inhalte, abgebrochene Uploads, Temp-Dateien.
- Dateispeicher: Unraid-Share unter `/mnt/user/<name>`, abgelegt nur auf disk2 + disk3 (3,2 TB frei), ohne
  Cache-SSD; Odoo greift nur über `/mnt/user` zu. Schlafende Platten brauchen beim ersten Zugriff einige Sekunden.
- Backup: Datenbank **und** Dateispeicher gehören zusammen; da Inhalte nie verändert werden, reicht für den Speicher
  ein inkrementelles Backup. Erst die Datenbank sichern, dann den Dateispeicher; das Aufräumen wartet länger als ein
  Backup-Lauf.
- Das Odoo-Image vor Schritt 3 auf den aktuellen Stand bringen (dem heutigen fehlt ein Sicherheits-Fix).
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
| 2026-09-26 | Prüfwerkzeuge: pre-commit (OCA-Vorlage, nur neuer Code), Odoos `test_lint` und Odoos Language Server `odoo-ls` (prüft Modelle, Felder, Abhängigkeiten); keine GitHub Action |
| 2026-09-26 | Spätere Änderungen am Datenmodell über Migrationsskripte mit Odoos `upgrade-util` |
| 2026-09-26 | Start ohne Netzlaufwerk, mit Eingangsordner; Netzlaufwerk später nach Nutzung (WebDAV über `odoo fmdav` oder SMB über Odoo-FUSE) |
| 2026-09-27 | Eingangsordner: Datei gilt nach 2 Minuten ohne Änderung als fertig |
| 2026-09-27 | ZIP-Download bis ca. 500 MB direkt, darüber im Hintergrund |
| 2026-09-27 | Dateispeicher als Share unter `/mnt/user`, Plattenauswahl disk2 + disk3, ohne Cache (Tower) |
| 2026-09-28 | Abgeleitete Dateien (Vorschau, Text, Metadaten) im eigenen Dateispeicher statt in `ir.attachment`; Odoo dekodiert sie nie |
| 2026-09-28 | Erzeugung als Mischform: dauerhafte Warteschlange, gedrosselt im Hintergrund, Sichtbares zuerst |
| 2026-09-28 | Zwei Bildgrößen (Kachel, Vorschau); Werterkennung bleibt in Odoo; Umfang von Schritt 5 = Kern, Erweiterungen später |
| 2026-09-29 | OCR/Werterkennung mit Wortpositionen (Hervorhebung, wie v1s Phase A–C) für die volle Ausbaustufe, auch für Vorschau-PDFs aus Office; erst Server/Datenmodell, Oberfläche folgt als eigener Schritt. Kein Zerstückeln langer Dokumente: der Umwandler antwortet bei einer Umwandlung über 15 s mit einer Auftragsnummer statt zu blockieren, Odoo fragt später nach (Vorbild: FileRun, Nextcloud, Amazon/Google Document-Umwandlung, alle geprüft) |

## 11. Reihenfolge mit Abnahme

Jeder Schritt ist erst fertig, wenn seine Abnahme erfüllt ist; der nächste beginnt erst danach. **Für jeden Schritt
gilt zusätzlich:** pre-commit, Odoos `test_lint` und `odoo-ls` ohne Befund im eigenen Code, `i18n/de.po` vollständig (keine englischen Texte in der
deutschen Oberfläche). Jeder Schritt wird
vor der Abnahme von einer zweiten Instanz gegengelesen (`codex -p review`). *(Abnahmekriterien mit der Freigabe
am 2026-09-27 verbindlich.)*

| # | Schritt | fertig, wenn |
|---|---|---|
| 3 | **Fundament:** Test-Image aktualisieren, Prüfwerkzeuge einrichten, **zuerst die Tests für die vier schweren Befunde der Code-Prüfung (A1–A4)**, dann Datenmodell, Dateispeicher, Schreibwege, Rechte | je Grundregel ein grüner Test, für I1–I6 und I9 auch mit Abbruch mitten im Vorgang; die Tests für A1–A4 erzwingen die Überschneidung (zweiter Vorgang wird angehalten) und brechen echte Prozesse ab – nicht nur "gleichzeitig starten"; Rechte-Tests für Nicht-Admins über alle Wege **und alle Tabellen**; kein `sudo` auf Nutzereingaben |
| 4 | **Oberfläche** auf das neue Modell | alle Funktionen aus Abschnitt 4 (außer Office/Einliefern) in der Oberfläche bedienbar; Upload 3 GB mit Abbruch und Fortsetzen |
| 5 | **Vorschau, Texterkennung und Metadaten** im Umwandler | Vorschau für die häufigen Formate (Bilder inklusive HEIC/RAW/TIFF, Video-Standbild, Office, PDF, Scans mit Texterkennung); Metadaten; Fehler sichtbar statt still; Odoo-Prozess bleibt bei defekten Dateien stabil; Test, dass Odoo Ergebnisse nie dekodiert (I13) |
| 6 | **Office** (ONLYOFFICE im Browser) | Speichern ergibt neue Fassung; zwei gleichzeitige Bearbeitungen führen zu Hinweis statt Verlust |
| 7 | **Eingangsordner** | Scanner-Datei wird erst nach Fertigschreiben übernommen; kein Duplikat nach Abbruch; Fehlerablage funktioniert |
| 8 | **Übernahme** des Bestands | Probelauf auf der Testinstanz vollständig; Zählung und Prüfsummen stimmen; Rückweg geprobt |
| 9 | später: **Netzlaufwerk** entscheiden | nach Erfahrungen aus 4–8 |

## 12. Bewusst nicht (vorerst)

- Kein Netzlaufwerk zum Start; kein Samba + Watcher (zweiter Schreiber).
- Keine Änderung am Odoo-Kern.
- Keine Erweiterungen, bevor das Fundament im Alltag trägt.

## 13. Offene Risiken

- **Viel Eigenbau** (Dateispeicher, Upload in Stücken, Umwandler) für einen Server mit heute einem Nutzer – bewusst
  entschieden, Umfang bleibt klein gehalten.
- **Odoo-Details, auf die wir uns verlassen** – alles läuft in Odoo, ist aber keine fest zugesicherte Schnittstelle:
  (a) Odoos offizielle Option `x_sendfile` übergibt Downloads nur für Dateien unterhalb von `data_dir/filestore` an
  nginx (dort liegt deshalb der Dateispeicher); (b) für die Verknüpfung mit Geschäftsobjekten werden Odoos Methoden
  `_check_access`/`_search` überschrieben (wie in Odoos `mail.activity`) – die Ordnerrechte selbst laufen über normale
  Odoo-Regeln. Durch Tests abgesichert, Odoo-Updates nur nach grünem Testlauf auf der
  Testinstanz. Ohne nginx liefert Odoo selbst aus – dann belegt jeder Download einen Odoo-Prozess für die ganze Dauer
  und lange Downloads laufen ins Zeitlimit. Deshalb bleibt es bei Odoos offizieller Auslieferung über `x_sendfile`:
  Odoo prüft Rechte und Datei, nginx liefert die Bytes.
- **`fsync` auf dem Array** kostet ~28 ms je Datei (Absturzsicherheit); ein Dateispeicher auf SSD würde es verkürzen –
  Entscheidung beim Betrieb.
- **Nicht mit echtem Word/Excel getestet** (nur nachgespielt), betrifft erst ein späteres Netzlaufwerk.
- **Gleichzeitige Zugriffe:** Odoos automatische Wiederholung greift nicht bei Namenskonflikten und belegten Sperren;
  der eigene Code muss das regeln – deshalb in Schritt 3 die Tests zuerst.

## 14. Wo was steht

| Thema | Datei |
|---|---|
| Stand, nächste Schritte, Testumgebung | `int_filemanager_v2_stand.md` |
| Begründungen, verworfene Wege, Odoo-19-Fallen | `int_filemanager_v2_entscheidungen.md` |
| Frühere Konzepte, Messungen, Prüfberichte | Git-Tag `docs-vor-aufraeumen-2026-10-02` |
