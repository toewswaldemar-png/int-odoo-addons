# Prüfprompt: Konzept int_filemanager Volltextsuche und OCR (2026-10-13)

Zweck: Prompt für eine neue Sitzung, die `docs/int_filemanager_volltextsuche_ocr_2026-10-13.md` gegen Odoo-19-Quelltext, Odoo-Regeln und Odoo-Doku prüft.
Ergebnis der Prüfung ist ein Bericht im Chat, keine Änderung an Konzept oder Code.

---

Prüfe das Konzept `docs/int_filemanager_volltextsuche_ocr_2026-10-13.md` (Entwurf, nichts gebaut) gründlich gegen den Odoo-19-Quelltext, die Odoo-Regeln und die offizielle Odoo-Dokumentation. Ändere das Konzeptdokument und den Code NICHT. Ergebnis ist ein Prüfbericht im Chat. Eine Datei schreibst du nur, wenn ich es danach ausdrücklich sage.

## Maßstab (CLAUDE.md, verbindlich)
- Maßgeblich sind ausschließlich der Odoo-19-Quelltext und die offizielle Odoo-19-Doku. Bei Widerspruch gilt der Quelltext. Keine OCA- oder Hausregeln.
- Lies zuerst `docs/odoo_regeln/odoo_regeln_index_2026-10-02.md`, dann alle Dateien in `docs/odoo_regeln/` vollständig (ORM, Sicherheit, Daten/Manifest, Aktionen/Cron, JS/Owl, Tests, CLI).
- Lies beide `INDEX.md` (`docs/odoo19_reference/`, `docs/owl2_reference/`) und die zu den Themen gehörenden Referenzdateien. Nenne bei jeder Aussage die Fundstelle (Datei und Abschnitt oder Zeile).
- Odoo-Quelltext: lokaler Klon `C:\Users\waldemar.toews\Documents\GitHub\odoo` (Shallow 19.0). Das Konzept beruft sich auf Commit `8d05257`. Prüfe per fetch+diff, ob der Klon davon abweicht, und ob die zitierten Zeilennummern noch stimmen. Rekursives grep ist dort langsam, also gezielt nach Datei suchen.
- Das Konzept soll deployment-unabhängig sein (Prefork oder Threaded, mit oder ohne Docker). Prüfe auch, ob irgendwo doch eine versteckte Annahme über Docker, Linux oder die HM-SRV steckt.

## Teil 1: Jede Fundstelle in Abschnitt 6 nachprüfen
Gehe die Tabelle Zeile für Zeile durch und gib je Zeile an: stimmt / stimmt mit Abweichung / falsch / nicht auffindbar.
Prüfe besonders:
- `ir_cron.py`: Gilt die Behauptung "≥ 10-mal und ≥ 10 s", `_reschedule_asap`, `timed_out_counter` und `CONSECUTIVE_TIMEOUT_FOR_FAILURE = 3`? Gibt es in Odoo 19 genau `_commit_progress(processed, remaining=…)`? Wie lauten Signatur und Semantik? Ist `try_lock_for_update` dort so verfügbar?
- `server.py`: Wird `thread.start_time` je Durchlauf wirklich über alle fälligen Crons gesetzt? Ist es in Prefork gesetzt (Abschnitt 12 ist offen)? Wie arbeiten `limit_time_real_cron` mit -1 und 0, `RLIMIT_CPU` und `RLIMIT_AS` im Prefork-Worker? Werden die Limits an Kindprozesse vererbt?
- `models.Index` in `orm/table_objects.py`: Kann man damit einen GIN-Index auf einen Ausdruck definieren, so wie in Abschnitt 3? Wie wird der Ausdruck ausgewertet? Muss die Faltungsfunktion `immutable` sein, und akzeptiert Odoo `to_tsvector('german', …)` dort?
- `search=` mit `[('checksum','in', SQL(…))]` und `NotImplemented` bei anderen Operatoren: Entspricht das Muster in `mail_thread.py`, `hr_applicant.py` und `domains.py` dem, was das Konzept beschreibt? Ist `NotImplemented` in 19 der richtige Weg?
- `attachment_indexation`: Gibt es das Modul in 19? Wie arbeiten `_index` und `index_content`? Wird wirklich für ALLE Anhänge der Instanz indexiert (Nebenwirkung in Abschnitt 2)? Prüfe die Größe der Auswirkung, etwa auf `ir.attachment.create`, Performance und Speicher.
- pdf.js-Parameter `#page=N&search=…`: Stimmt das für die in Odoo 19 gebündelte pdf.js-Version? Wie baut der Core die Viewer-URL, und gibt es dort Stellen, die Fragmente verwerfen?

## Teil 2: Konzept gegen Odoo-Regeln und -Muster prüfen
Prüfe jede Designentscheidung (Abschnitte 2, 3, 4, 5, 9, 10) gegen die Destillate in `docs/odoo_regeln/` und gegen Core-Muster:
1. **ORM/Modelle:** `_sql_constraints` oder `models.Constraint` für `checksum` eindeutig? Regex-Validierung wie beim Dokument? Feldtypen, Textfelder mit 500.000 Zeichen? `Index`-Definition? Datei je Modell?
2. **Sicherheit:** Reicht "keine ACL für Nutzer auf den Textmodellen" in Verbindung mit einem Suchfeld am Dokument? Wirkt die `ir.rule` des Dokuments wirklich auf die SQL-Unterabfrage? Die Unterabfrage läuft auf Checksummen und umgeht die Regeln, also: Kann ein Nutzer über `content_search` auf Treffer in Dokumenten schließen, die er nicht sehen darf (z. B. wenn ein anderer Ordner dieselbe Prüfsumme hat, Stichwort Dedup)? Prüfe das konkret. Gilt dasselbe für den Seiten-/Textauszug, der "erst für sichtbare Treffer" entsteht, und für Zugriffe mit `sudo()`?
3. **Cron:** Passt das Muster `_cron_ocr` zu den Cron-Regeln und zum Core (Bedeutung von `priority`, `numbercall`/Aufrufmodell in 19, `_commit_progress`, `try_lock_for_update`, Transaktionsgrenzen)? Ist die Annahme "Der Core lässt von einem Cron nie zwei Läufe gleichzeitig zu" belegt, auch bei mehreren Workern? Ist "`running`-Zeilen sind zu Beginn eines Aufrufs veraltet" korrekt? Was passiert bei Commit/Rollback mitten im Stapel, und kann der OCR-Prozess Zeilen halb committen?
4. **Einstellungen:** `res.config.settings` und `ir.config_parameter` (Cache-Signal `set_param`), Gruppenrechte, Standardwerte, `config_parameter=`-Felder, Zeitzone/Zeitfenster. Reicht das Konzept für "wirken ohne Neustart"?
5. **Manifest/Daten:** `depends`, `external_dependencies` leer (stimmt die Begründung?), Cron-XML (`noupdate`), Gruppen, Zugriffsrechte-CSV.
6. **Blob-Verwaltung:** `_gc_blobs`, `_store_stream`, `_publish_blob` und die abgeleiteten OCR-PDFs: Gibt es im bestehenden Code von `int_filemanager` Stellen, die das Konzept nicht berücksichtigt (Quota, Löschen, Dedup, Verschieben)? Lies dazu den aktuellen Code des Moduls und vergleiche mit Abschnitt 10 (Realitätscheck).
7. **Prefork und Threaded:** Lässt sich der Cron-Pfad mit `threading.current_thread().start_time` und dem Eigenzähler in beiden Betriebsarten sauber umsetzen? Was ist auf Nicht-Linux-Systemen (`resource`, `psutil`, Signale)? Ist `psutil` im Odoo-Image/Requirements garantiert? Prüfe `requirements.txt` und `setup`-Dateien des Odoo-Quelltexts.
8. **Odoo-eigene Bordmittel:** Wende das Suchraster aus CLAUDE.md vollständig an (Core-Grep, vergleichbare Module, Bibliotheken im Image, Feld-/Modell-Defaults, empirische Kurzprüfung). Gibt es für einen der Eigenbau-Teile (Suche, Textextraktion, Cron-Zeitbudget, Subprozess-Start, Einstellungen, GC) eine native Entsprechung, die das Konzept übersieht? Prüfe auch, ob Odoo 19 selbst eine Volltext- oder `unaccent`-Funktion bietet (`unaccent`-Option der Datenbank, `base.unaccent`, `tools.sql`), und ob die eigene Umlautfaltung ü→ue dazu im Widerspruch steht oder nützlich ist.
9. **Frontend (Viewer-Anbindung, Treffer-Ansicht):** Welche JS-Regeln (`js_framework`, `js_fields`, Owl 2.8.4 aus `owl2_reference/`) betreffen den Schritt? Passt `DocumentFile.defaultSource` zu den Mustern des Cores?

## Teil 3: Technische Aussagen empirisch absichern
Prüfe, was sich ohne Eingriff in die Live-Umgebung prüfen lässt. Nur in einer Wegwerf-Umgebung arbeiten (siehe `tools/check/tests.sh` und `docs/pruefautomatik_2026-10-02.md`). Löse keine Deploys aus. Bevor du etwas löschst, prüfe die Mounts der laufenden Container. Wenn du etwas Empirisches nicht prüfen kannst, sage das und lass es ungeprüft.
- Postgres: `to_tsvector('german', …)` mit der geplanten Faltung (Müller/Mueller, Straße/Strasse), `immutable`, Indexnutzung bei `websearch_to_tsquery` mit der Unterabfrage (EXPLAIN), `tsvector`-Grenze von 1 MB.
- `ocrmypdf`-Verhalten nur dort, wo das Konzept es als gemessen ausgibt (Abschnitt 7), und nur stichprobenartig.
- Prüfe, ob Abschnitt 7 nur Messungen enthält, die tatsächlich gemessen wurden, und ob Abschnitt 12 alles Ungemessene vollständig aufführt.

## Teil 4: Logik und Vollständigkeit
- Innere Widersprüche zwischen Abschnitten (z. B. Entscheidungstabelle vs. Zielbild vs. Einstellungen vs. Tests).
- Fehlerfälle ohne Behandlung (Zustandsübergänge von `state`, Neu-OCR bei geänderter Engine-Version, Löschen und Wiederherstellen von Dokumenten, Prüfsummen-Kollisionen bei Ordnerrechten, Zeilen ohne Blob, Papierkorb/`active`).
- Testplan (Abschnitt 11): Deckt er die kritischen Pfade ab? Entspricht er den Test-Regeln (`TransactionCase`, `tests/__init__.py`, Tags)? Fehlen Tests zur Sicherheit (Teil 2, Punkt 2)?
- Reihenfolge (Abschnitt 13): Ist sie abhängigkeitsfrei umsetzbar?

## Berichtsformat
- Jeder Befund: Schweregrad (falsch / riskant / Lücke / Hinweis), betroffener Abschnitt des Konzepts, Beleg mit Quelle, Datei und Zeile, und ein konkreter Vorschlag zur Korrektur.
- Kennzeichne klar, was du im Quelltext oder der Doku belegt hast, was du empirisch geprüft hast und was nur Vermutung bleibt.
- Trenne Befunde (Zielbild stimmt nicht mit Odoo überein) von bloßen Verbesserungsideen. Das Zielbild des Konzepts übernimmst du so, wie es steht. Umsetzungsaufwand ist kein Grund, es abzuschwächen.
- Behaupte nirgends "gibt es in Odoo nicht" oder "geht nicht", ohne das Suchraster aus CLAUDE.md vollständig durchlaufen zu haben.
- Am Ende: eine Zusammenfassung mit den 5 wichtigsten Funden, eine Aussage, ob das Konzept so umsetzbar ist, und eine Empfehlung, wann das Prüfen genug ist. Benenne die Quelle der Funde, und höre auf, wenn neue Runden nur noch Kleinigkeiten liefern.
