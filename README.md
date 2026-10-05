# int-odoo-addons

Eigene Odoo-19-Module, dazu die Werkzeuge, Regeln und Unterlagen für ihre Entwicklung. `int_filemanager` ist das große Modul. Alles unter LGPL-3.

## Module

| Modul | Wofür |
|---|---|
| [`int_filemanager`](int_filemanager/) | Dateiverwaltung (DMS) in Odoo: Ordner und Dateien mit Versionen, Papierkorb, Rechten, Vorschau, Suche, Texterkennung, Verknüpfung mit Datensätzen; Office im Browser über ONLYOFFICE. Odoo ist alleiniger Schreiber, die Inhalte liegen in einem eigenen Blob-Speicher. |
| [`int_repair_workshop`](int_repair_workshop/) | Werkstattfelder am Reparaturauftrag (Auftragsart, Eingangsdatum, Resttage, sieben Werkstattstufen mit Mitarbeiter) und eine Listenansicht. Die Liste ist eine Übersicht, **keine** Belegmaske für Kunde, Kostenvoranschlag oder Versand |
| [`int_generic`](int_generic/) | Sammelmodul für kleine Anpassungen ohne Bindung an eine Business-App (derzeit: Spaltenreihenfolge in Listenansichten per Drag & Drop); braucht nicht mehr als `base` und `web` |
| [`int_fleet_kanban_width`](int_fleet_kanban_width/) | Die Spalten des Fahrzeug-Kanban teilen sich die verfügbare Breite, statt zu scrollen; eigenes Modul, weil es an `fleet` hängt |
| [`int_legacy_erp_import`](int_legacy_erp_import/) | Produktfelder aus einem Fremdsystem (Artikelnummer, Bestellnummer, Hersteller-Referenzen); rein zum Testimport, kein produktiver Datenimport |
| [`onlyoffice_odoo`](onlyoffice_odoo/) | Anbindung an ONLYOFFICE Docs (Drittanbieter-Modul, Autor ONLYOFFICE); `int_filemanager` hängt davon ab |

Zuschnitt: ein Modul je fachlicher Abhängigkeit (auch bei winzigen Änderungen), app-unabhängige Anpassungen gemeinsam in `int_generic`. Odoo sucht `addons_path` nur eine
Ebene tief, deshalb liegen alle Module flach im Wurzelordner.

## Repo-Aufbau

| Pfad | Inhalt |
|---|---|
| `int_*/`, `onlyoffice_odoo/` | die Module (jedes mit eigenem `__manifest__.py`) |
| [`Dockerfile`](Dockerfile) | Odoo-19-Image mit den Bibliotheken von `int_filemanager` (Audio-Metadaten, Tesseract/OCRmyPDF, pdfplumber, pyjwt) |
| [`docs/`](docs/) | Dokumentation |
| `docs/odoo_regeln/` | Odoo-19-Regeln: Coding und Git Guidelines mit Hausregeln, Developer Reference |
| `docs/odoo19_reference/`, `docs/owl2_reference/` | Volltext-Referenzen zum Nachschlagen (Odoo 19, Owl 2.8.4) |
| `docs/odoo/` | Odoo-19-Quellcode als lokale Kopie (nicht Teil des Repos) |
| `docs/pruefautomatik_2026-10-02.md` | Prüfwerkzeuge, Aufruf und was sie prüfen |
| `tools/fmconverter/` | Umwandler-Container für `int_filemanager` (Vorschauen, OCR, Metadaten) |
| `tools/v2check/` | Prüf- und Testskripte für `int_filemanager` |
| `scripts/lint/` | Läufe für `test_lint` und odoo-ls |
| `.pre-commit-config.yaml`, `.ruff.toml`, `eslint.config.cjs`, `prettier.config.cjs` | Prüfautomatik |
| [`CLAUDE.md`](CLAUDE.md) | verbindliche Arbeitsregeln für die Arbeit mit Claude Code |

## Branches und Tags

- `master`: Hauptlinie.
- `feature/<thema>`: Entwicklung je Thema, z. B. `feature/int-filemanager-v2` und `feature/int-liedanzeige`.
- Tag `int_filemanager-v1`: der Stand von `int_filemanager` vor dem Neubau.

## Entwickeln

- **Regeln:** vor Code in einem Bereich die zugehörige Datei in [`docs/odoo_regeln/`](docs/odoo_regeln/) lesen; vor jeder Aussage "das gibt es in Odoo nicht" den
  Odoo-19-Core durchsuchen (`docs/odoo/`). Neuer Code englisch, Oberflächentexte englisch mit deutscher Übersetzung in `i18n/de.po`.
- **Prüfen:** pre-commit bei jedem Commit; `test_lint` und odoo-ls als eigene Läufe. Aufruf und Umfang: [`docs/pruefautomatik_2026-10-02.md`](docs/pruefautomatik_2026-10-02.md).
  Für `int_filemanager`: `tools/v2check/v2check.sh`.
- **Commits:** `[TAG] modul: kurzer Satz` (Odoo-Git-Guidelines), Commit nur auf Ansage.
