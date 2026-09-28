# int_filemanager 2 – Schritt 4: Oberfläche auf das neue Modell

Stand 2026-09-28. Grundlage: Kern 4/11 und Konzept 6–8/15. **Fertig, wenn** (Kern 11): alle Funktionen aus Kern 4
(außer Office und Einliefern) in der Oberfläche bedienbar sind und ein Upload von 3 GB mit Abbruch und Fortsetzen
funktioniert – zusätzlich pre-commit, `test_lint`, odoo-ls ohne Befund, `i18n/de.po` vollständig, Gegenlesen per
`codex -p review`.

## Entscheidungen zur Bauform

1. **v2-Oberfläche entsteht parallel** (`static/src/int_filemanager/v2/`, neue Views/Actions/Menü auf
   `int_filemanager.node`); die v1-Oberfläche (`native_ui/`, Views auf `int_filemanager.file`, pfadbasierte Routen)
   bleibt bis zur Umstellung (Schritt 8) unberührt und wird dort **gelöscht** (Konzept 15). Grund: das Modul bleibt
   nach jedem Schritt installierbar und testbar; das v1-Verhalten dient als Vorlage beim Umschreiben.
2. **Nichts Neues im Frontend, was Odoo schon kann:** native `list`/`kanban`/`form`/`search`-Views auf dem Knoten,
   Odoos `FileUploader`/Dialoge/Notifications, `useService`. Eigenbau nur für: Ordnerbaum (die Baum-Seitenleiste hat
   Odoo nicht, Recherche 2026-09-24), Chunk-Upload (Odoos Upload sendet die ganze Datei in einem Request), Kontextmenü.
3. **Alles Schreibende läuft über die Modellmethoden aus Schritt 3** (`create_file`, `rename_or_move`, …), nie über
   `write()` aus dem Browser; Vorgangsnummer (UUID) je Nutzeraktion, Wiederholung ist harmlos (I9).
4. **Frontend wird nicht per Browser-Automatik getestet** (Nutzerregel): Serverseite vollständig mit Odoo-Tests und
   Echtprozess-Skripten, Frontend mit `eslint`/`prettier` (pre-commit) und freiem Nutzertest (keine Checkliste; Entscheidung 2026-09-28).

## Scheiben

**4a Server (testbar ohne Browser)**

| # | Inhalt | Abnahme |
|---|---|---|
| 4a-1 | Knoten: Namensprüfung (NFC, keine `/ \ NUL`, nicht `.`/`..`), `create_folder`, Ordner kopieren (rekursiv), Verschieben in den eigenen Teilbaum verboten, Felder `tag_ids`/`status_id`/`partner_id`/`revision_ids`/`trashed_at` | Odoo-Tests grün |
| 4a-2 | Download-Route (`/int_filemanager/v2/download/<id>`, Rechte per ORM, Range, `x_sendfile`), Revision-Download | HttpCase mit Nicht-Admin, Range-Test |
| 4a-3 | Upload-Routen (Chunk als Rohdaten, `status` zum Fortsetzen), Aufräumen abgelaufener Uploads | HttpCase + **3-GB-Skript mit Abbruch und Fortsetzen** auf Tower |
| 4a-4 | ZIP (bis 500 MB direkt als Strom, darüber Cron + Benachrichtigung), Temp-Aufräumen | Tests inkl. Rechte je Datei |
| 4a-5 | Papierkorb-Frist: Cron löscht nach 30 Tagen endgültig (`trashed_at`) | Test mit künstlich altem Datum |
| 4a-6 | Freigabe-Links für Knoten (Token, Ablauf, öffentlicher Download, Protokoll) | Test anonym/abgelaufen/widerrufen |

**4b Oberfläche (Nutzertest)**

| # | Inhalt |
|---|---|
| 4b-1 | Menü, Actions, Search/List/Kanban/Form auf `int_filemanager.node`, Ordnerbaum, Breadcrumb, Öffnen von Ordnern |
| 4b-2 | Ordner anlegen, Umbenennen, Löschen (Papierkorb), Papierkorb-Ansicht mit Wiederherstellen |
| 4b-3 | Upload (Dateien und ganze Ordner) mit Chunking, Fortschritt, Abbruch, Fortsetzen; Namenskonflikt-Dialog |
| 4b-4 | Verschieben (Auswahldialog), Kopieren, Drag & Drop |
| 4b-5 | Download einzeln/ZIP, Versionen (Liste, Wiederherstellen, alte Fassung laden), lokal bearbeiten = Neue Fassung mit Konfliktmeldung |
| 4b-6 | Tags/Status/Kontakt, Freigabe-Dialog, Kontakt-Smart-Button |

Reihenfolge: 4a komplett, dann 4b in Scheiben; nach jeder Scheibe Commit + Push, Übergabe-Dokument nachziehen.
Suche nach Inhalt (Texterkennung) gehört zu Schritt 5, Vorschaubilder ebenso – in Schritt 4 zeigt die Kachel Symbole.
