# int-odoo-addons

Eigene Odoo-19-Module, dazu Werkzeuge und Unterlagen für ihre Entwicklung. Alles unter LGPL-3.

## Module

| Modul | Wofür |
|---|---|
| [`int_filemanager`](int_filemanager/) | Dateimanager aus Odoos eigenen Bausteinen (hängt nur von `base` und `mail` ab): Ordner (mit Eltern-Ordner) und Dokumente als gewöhnliche Datensätze. Die Dateien liegen als Blobs (SHA-256) in einem eigenen Ordner des Odoo-Filestores, nicht in `ir.attachment`; Upload und Download laufen als Stream, auch für sehr große Dateien. Rechte pro Ordner (erlaubte Benutzer und Gruppen, Follower, Mehrfirmen-Regel), Archivieren und Wiederherstellen samt Inhalt, Tags, Chatter mit Tracking und Aktivitäten. Oberfläche: Liste, Kanban (Kartengröße klein/mittel/groß je Nutzer wählbar, am Handy mehrere Karten pro Zeile), Pivot und Graph mit Suchpanel als Ordnerbaum, Vorschau der Datei neben dem Formular und Vollbild-Viewer, am Handy mit Wischen zum Blättern, Zwei-Finger-Zoom und Doppeltipp, Bilder bearbeiten (Formen, Pinsel, Text, Verläufe, Schatten, Filter, Zuschneiden und Drehen, Teile verdecken, Raster, Zoom, Bilder einfügen; Speichern als neues Dokument in PNG, JPEG, WebP oder SVG, die Markierungen bleiben beim nächsten Öffnen bearbeitbar; Bibliothek Fabric.js 7.4.0 unter `static/lib/fabric`, MIT; Konzept und Stolpersteine: `docs/int_filemanager_bildeditor.md`), Hochladen per Knopf oder Drag & Drop, auch ganzer Ordner mit Unterordnern (gleichnamige Ordner werden zusammengeführt, gleichnamige Dateien nummeriert), Herunterladen mehrerer Dateien oder eines ganzen Ordners als ZIP (nur was der Nutzer sieht, Obergrenze als Systemparameter `int_filemanager.zip_max_size`), Verschieben über die Mehrfachbearbeitung oder den Dialog „Move to...“ mit Pfadanzeige und geprüftem Ziel (Konzept und Messungen: `docs/int_filemanager_erkenntnisse.md`). Volltextsuche in den Dateien (je Seite, mit Treffern im Viewer) und Texterkennung für Scans und Bilder (`ocrmypdf`, per Cron, Konzept: `docs/int_filemanager_volltextsuche_ocr.md`). Verknüpfung von Dokumenten mit Datensätzen anderer Modelle (derzeit Kontakte; ein Dokument ist über den Ordner **oder** über einen lesbaren verknüpften Datensatz sichtbar, am Datensatz hochgeladene Dateien kommen in den Ablageordner des Modells (Menü Upload-Ordner), Konzept: `docs/int_filemanager_datensatz_verknuepfung.md`). Einlesen eines Serverordners (Prüfbericht, dann Kopieren per Cron), Aufräumer für unbenutzte Blobs. Freigabe-Links für Gäste ohne Konto (Datei oder Ordner; Ansehen, Herunterladen, Hochladen in einen eigenen Unterordner; Passwort, Ablauf, Download-Limit, Besuchszähler, Bremsen gegen Missbrauch; Knopf „Teilen“ am Ordner und an der Datei, Konzept: `docs/int_filemanager_freigabe_links.md`). Nicht enthalten: Versionen, Portal, Office im Browser. |
| [`int_repair_workshop`](int_repair_workshop/) | Werkstattfelder am Reparaturauftrag (Auftragsart, Eingangsdatum, Resttage, sieben Werkstattstufen mit Mitarbeiter) und eine Listenansicht. Die Liste ist eine Übersicht, **keine** Belegmaske für Kunde, Kostenvoranschlag oder Versand |
| [`int_keepass`](int_keepass/) | Gruppen und Einträge eines KeePass-Tresors (`.kdbx`) oder eines Vaultwarden-Kontos als virtuelle Datensätze, ohne sie in der Datenbank zu speichern (Experiment, nur lesen). Das Master-Passwort bleibt im Speicher des Browsers und geht als Header an den Server, der Worker hält nur Namen und Adressen für fünf Minuten; Zertifikat eines selbst signierten Vaultwarden per Fingerabdruck festgesetzt. Dazu eine Namensliste für die Anmeldung von AIDA-Web (Endpunkt mit Token, Erweiterung unter `extensions/aida_login_list`) |
| [`int_generic`](int_generic/) | Sammelmodul für kleine Anpassungen ohne Bindung an eine Business-App (derzeit: Spaltenreihenfolge in Listenansichten per Drag & Drop); braucht nicht mehr als `base` und `web` |
| [`int_fleet_kanban_width`](int_fleet_kanban_width/) | Die Spalten des Fahrzeug-Kanban teilen sich die verfügbare Breite, statt zu scrollen; eigenes Modul, weil es an `fleet` hängt |
| [`int_legacy_erp_import`](int_legacy_erp_import/) | Produktfelder aus einem Fremdsystem (Artikelnummer, Bestellnummer, Hersteller-Referenzen); rein zum Testimport, kein produktiver Datenimport |
| [`onlyoffice_odoo`](onlyoffice_odoo/) | Anbindung an ONLYOFFICE Docs (Drittanbieter-Modul, Autor ONLYOFFICE); `int_filemanager` braucht es nicht mehr |

Zuschnitt: ein Modul je fachlicher Abhängigkeit (auch bei winzigen Änderungen), app-unabhängige Anpassungen gemeinsam in `int_generic`. Odoo sucht `addons_path` nur eine
Ebene tief, deshalb liegen alle Module flach im Wurzelordner.

## Repo-Aufbau

| Pfad | Inhalt |
|---|---|
| `int_*/`, `onlyoffice_odoo/` | die Module (jedes mit eigenem `__manifest__.py`) |
| [`Dockerfile`](Dockerfile) | Odoo-19-Image (Test und Betrieb); enthält noch Bibliotheken aus der früheren Fassung von `int_filemanager` (Audio-Metadaten, Tesseract/OCRmyPDF, pdfplumber, pyjwt) |
| [`docs/`](docs/) | Dokumentation |
| `docs/odoo19_reference/`, `docs/owl2_reference/` | Volltext-Referenzen zum Nachschlagen (Odoo 19, Owl 2.8.4) |
| `docs/odoo/` | Odoo-19-Quellcode als lokale Kopie (nicht Teil des Repos) |
| `docs/odoo19_abweichungen.md` | bestätigte Abweichungen zwischen offizieller Odoo-19-Dokumentation und Core, jeweils mit Fundstelle, Core-Commit und Test |
| `docs/pruefautomatik_2026-10-02.md` | Prüfwerkzeuge, Aufruf und was sie prüfen |
| `tools/check/` | Prüf- und Testskripte für `int_filemanager` (Modultests, odoo-ls und `test_lint`, Test-Instanz, Übersetzungsexport) |
| `tools/image_editor_check/` | Prüfungen des Bildeditors ohne Browser (Node: echtes Fabric und Owl in jsdom, Viewer gegen den Core-Viewer) |
| `extensions/aida_login_list/` | Edge-Erweiterung: Auswahlliste der Benutzernamen im Feld der AIDA-Anmeldung, Namen aus `int_keepass` (mit Tests in jsdom) |
| `.pre-commit-config.yaml`, `ruff.toml`, `.eslintrc.json` | Prüfautomatik (Odoos eigene Konfiguration) |
| [`CLAUDE.md`](CLAUDE.md) | kurzer Prüfablauf für offizielle Odoo-19-Dokumentation, Core und reproduzierbare Tests |
