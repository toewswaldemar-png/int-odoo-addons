# int-odoo-addons

Eigene Odoo-19-Module, dazu die Werkzeuge, Regeln und Unterlagen für ihre Entwicklung. Alles unter LGPL-3.

## Module

| Modul | Wofür |
|---|---|
| [`int_filemanager`](int_filemanager/) | Dateimanager aus Odoos eigenen Bausteinen: Ordner (mit Eltern-Ordner) und Dokumente als gewöhnliche Datensätze; die Datei liegt in einem Binary-Feld, das Odoo selbst in `ir.attachment` und im Filestore ablegt. Suchpanel als Ordnerbaum, Tags, Chatter, Mehrfirmen-Regel. Erweiterungen (Versionen, Portal, Office im Browser, Texterkennung, Import) sind als eigene Module geplant. |
| [`int_repair_workshop`](int_repair_workshop/) | Werkstattfelder am Reparaturauftrag (Auftragsart, Eingangsdatum, Resttage, sieben Werkstattstufen mit Mitarbeiter) und eine Listenansicht. Die Liste ist eine Übersicht, **keine** Belegmaske für Kunde, Kostenvoranschlag oder Versand |
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
| `docs/odoo_regeln/` | Odoo-19-Regeln: Coding und Git Guidelines, Developer Reference (nur Odoo-Doku und Odoo-Code) |
| `docs/odoo19_reference/`, `docs/owl2_reference/` | Volltext-Referenzen zum Nachschlagen (Odoo 19, Owl 2.8.4) |
| `docs/odoo/` | Odoo-19-Quellcode als lokale Kopie (nicht Teil des Repos) |
| `docs/pruefautomatik_2026-10-02.md` | Prüfwerkzeuge, Aufruf und was sie prüfen |
| `tools/check/` | Prüf- und Testskripte für `int_filemanager` (Modultests, odoo-ls und `test_lint`, Test-Instanz, Übersetzungsexport) |
| `scripts/lint/` | Läufe für `test_lint` und odoo-ls |
| `.pre-commit-config.yaml`, `ruff.toml`, `.eslintrc.json` | Prüfautomatik (Odoos eigene Konfiguration) |
| [`CLAUDE.md`](CLAUDE.md) | verbindliche Arbeitsregeln für die Arbeit mit Claude Code |

## Branches

- `master`: Hauptlinie.
- `feature/<thema>`: Entwicklung je Thema, z. B. `feature/int-filemanager-kern` und `feature/int-liedanzeige`.

## Entwickeln

- **Regeln:** vor Code in einem Bereich die zugehörige Datei in [`docs/odoo_regeln/`](docs/odoo_regeln/) lesen; vor jeder Aussage "das gibt es in Odoo nicht" den
  Odoo-19-Core durchsuchen (`docs/odoo/`).
- **Prüfen:** pre-commit (Ruff, ESLint nach Odoos Konfiguration) bei jedem Commit; `test_lint` und odoo-ls als eigene Läufe. Aufruf und Umfang: [`docs/pruefautomatik_2026-10-02.md`](docs/pruefautomatik_2026-10-02.md).
  Für `int_filemanager`: `tools/check/tests.sh` (Modultests) und `tools/check/check.sh`.
- **Commits:** `[TAG] modul: kurzer Satz` (Odoo-Git-Guidelines), Commit nur auf Ansage.
