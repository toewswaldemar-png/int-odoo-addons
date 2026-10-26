# int-odoo-addons

Eigene Odoo-19-Module, dazu Werkzeuge und Unterlagen für ihre Entwicklung. Alles unter LGPL-3.

## Module

| Modul | Wofür |
|---|---|
| [`int_filemanager`](int_filemanager/) | Dateimanager aus Odoos eigenen Bausteinen (hängt nur von `base` und `mail` ab): Ordner und Dokumente als gewöhnliche Datensätze, Dateien als Blobs im Odoo-Filestore, Upload und Download als Stream. Rechte pro Ordner, Liste, Kanban, Pivot und Graph mit Ordnerbaum, Vorschau und Viewer, ZIP-Download, Ordner-Upload, Verknüpfung mit Datensätzen. Der Kern; Erweiterungen sind eigene Module (nächste Zeilen). Konzepte und Gründe: `docs/int_filemanager/` (`erkenntnisse.md`, `modulaufteilung.md`, `datensatz_verknuepfung.md`). Nicht enthalten: Versionen, Portal, Office im Browser |
| [`int_filemanager_share`](int_filemanager_share/) | Freigabe-Links für Gäste (Datei oder Ordner, ohne Konto): Gast-Seite, Gateway mit Whitelist, Passwort, Grenzen und Bremsen. Konzept: `docs/int_filemanager_share/freigabe_links.md` |
| [`int_filemanager_ocr`](int_filemanager_ocr/) | Volltextsuche im Inhalt der Dateien und Texterkennung für Scans (OCR) mit `ocrmypdf` und Tesseract. Konzept: `docs/int_filemanager_ocr/volltextsuche_ocr.md` |
| [`int_filemanager_image_editor`](int_filemanager_image_editor/) | Bildeditor für die Bilder des Filemanagers (Fabric.js, wird beim ersten Klick geladen). Konzept: `docs/int_filemanager_image_editor/bildeditor.md` |
| [`int_filemanager_import`](int_filemanager_import/) | Einen Ordner der Platte des Servers in den Filemanager einlesen (Prüfen, dann Kopieren in Schritten) |
| [`int_repair_workshop`](int_repair_workshop/) | Werkstattfelder am Reparaturauftrag (Auftragsart, Eingangsdatum, Resttage, sieben Werkstattstufen mit Mitarbeiter) und eine Listenansicht. Die Liste ist eine Übersicht, **keine** Belegmaske für Kunde, Kostenvoranschlag oder Versand |
| [`int_keepass`](int_keepass/) | Gruppen und Einträge eines KeePass-Tresors (`.kdbx`) oder eines Vaultwarden-Kontos als virtuelle Datensätze, ohne sie in der Datenbank zu speichern (nur lesen). Das Master-Passwort bleibt im Speicher des Browsers und geht als Header an den Server, der Worker hält nur Namen und Adressen für fünf Minuten; Zertifikat eines selbst signierten Vaultwarden per Fingerabdruck festgesetzt. |
| [`int_liedanzeige`](int_liedanzeige/) | Lied- und Chornummern auf Beamer-Bildschirmen (kirchliches Anzeigesystem): öffentliche Anzeigeseiten `/lied` und `/chor` (nur Nummern), Steuerseiten für Bediener unter `/steuerung`, Dirigentenansicht `/dirigent` mit Liedtext (eigene Gruppe), Liedverzeichnis (Nummer und Text) und ein Kiosk-Benutzer. Die Bildschirme folgen dem Zustand live über `bus.bus`; hängt von `base`, `bus` und `web` ab. Prüfbericht mit offenen Punkten: `docs/int_liedanzeige/pruefung.md` |
| [`int_presenter`](int_presenter/) | Einen Beamer aus Odoo bespielen, ähnlich wie SongBeamer oder OpenSong: Liederdatenbank, Ablaufplan, Design, Bedienseite und Beamer-Seite, die live folgt. Grundgerüst mit Konzept in der `README.md` des Moduls, noch keine Funktion |
| [`int_signage`](int_signage/) | Anzeigetafeln aus Odoo: Bildschirme und ihre Folien (Reihenfolge, Dauer, Gültigkeit), die ein Kiosk-Browser auf einem Minipc im Vollbild zeigt. Grundgerüst mit Konzept in der `README.md` des Moduls, noch keine Funktion |
| [`int_bible`](int_bible/) | Die Bibel im Odoo lesen und durchsuchen: mehrere Übersetzungen nebeneinander in einer Liste, Navigation Testament, Buch, Kapitel über das Searchpanel, Lesezeichen und Notizen; später Querverweise und Lesepläne. Status und Plan: `int_bible/README.md`, `docs/int_bible/plan.md` |
| [`int_generic`](int_generic/) | Sammelmodul für kleine Anpassungen ohne Bindung an eine Business-App (zum Beispiel: Spaltenreihenfolge in Listenansichten per Drag & Drop); braucht nicht mehr als `base` und `web` |
| [`int_fleet_kanban_width`](int_fleet_kanban_width/) | Die Spalten des Fahrzeug-Kanban teilen sich die verfügbare Breite, statt zu scrollen; eigenes Modul, weil es an `fleet` hängt |
| [`int_legacy_erp_import`](int_legacy_erp_import/) | Produktfelder aus einem Fremdsystem (Artikelnummer, Bestellnummer, Hersteller-Referenzen); rein zum Testimport, kein produktiver Datenimport |
| [`onlyoffice_odoo`](onlyoffice_odoo/) | Anbindung an ONLYOFFICE Docs (Drittanbieter-Modul, Autor ONLYOFFICE); `int_filemanager` braucht es nicht mehr |

Odoo sucht `addons_path` nur eine Ebene tief, deshalb liegen alle Module flach im Wurzelordner.

## Repo-Aufbau

| Pfad | Inhalt |
|---|---|
| `int_*/`, `onlyoffice_odoo/` | die Module (jedes mit eigenem `__manifest__.py`) |
| [`Dockerfile`](Dockerfile) | Odoo-19-Image (Test und Betrieb) mit den zusätzlichen Programmen und Bibliotheken der Module |
| [`docs/`](docs/) | Dokumentation |
| `docs/odoo19_reference/`, `docs/owl2_reference/` | Volltext-Referenzen zum Nachschlagen (Odoo 19, Owl 2.8.4) |
| `docs/odoo_wiki/` | unveränderte Kopie dreier Seiten des Odoo-GitHub-Wikis (JS- und SCSS-Guidelines, Contributing) |
| `docs/odoo/` | Odoo-19-Quellcode als lokale Kopie (nicht Teil des Repos) |
| `docs/odoo19_abweichungen.md` | bestätigte Abweichungen zwischen offizieller Odoo-19-Dokumentation und Core, jeweils mit Fundstelle, Core-Commit und Test |
| `docs/pruefautomatik.md` | Prüfwerkzeuge (Ruff, odoo-ls), Aufruf und Grenzen |
| `tools/check/` | Prüf- und Testskripte für `int_filemanager` (Modultests, odoo-ls, Test-Instanz, Übersetzungsexport) |
| `tools/image_editor_check/` | Prüfungen des Bildeditors ohne Browser (Node: echtes Fabric und Owl in jsdom, Viewer gegen den Core-Viewer) |
| `tools/int_keepass/` | Prüfskripte für `int_keepass`: Tests auf dem Testserver gegen einen Wegwerf-Vaultwarden, Lesen einer echten Quelle ohne Odoo, Gegenprobe mit der Bitwarden-CLI (Beschreibung: [`docs/int_keepass/beschreibung.md`](docs/int_keepass/beschreibung.md)) |
| `.pre-commit-config.yaml`, `ruff.toml` | Prüfautomatik (Ruff mit Odoos eigener Konfiguration) |
| [`CLAUDE.md`](CLAUDE.md) | kurzer Prüfablauf für offizielle Odoo-19-Dokumentation, Core und reproduzierbare Tests |
