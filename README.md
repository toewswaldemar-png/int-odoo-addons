# int-odoo-addons

Eigene Odoo-19-Module für die Firma, dazu die Werkzeuge, Regeln und Unterlagen für ihre Entwicklung. Sechs Module, davon ist
`int_filemanager` das große. Alles unter LGPL-3.

Stand 2026-10-02. Die Angaben zu Servern, Versionen und Deploy stammen aus der Arbeit bis September 2026 und sind nicht erneut gegen die
Live-Systeme geprüft.

## Module

| Modul | Version | Wofür | Stand |
|---|---|---|---|
| [`int_filemanager`](int_filemanager/) | 19.0.1.23.0 | Dateiverwaltung (DMS) in Odoo: Ordner und Dateien mit Versionen, Papierkorb, Rechten, Vorschau, Suche, Texterkennung, Verknüpfung mit Datensätzen; Office im Browser über ONLYOFFICE | `master` läuft auf HM-SRV und Tower. Der Neubau (Odoo als alleiniger Schreiber, eigener Blob-Speicher) entsteht auf dem Branch `feature/int-filemanager-v2` und soll `master` ablösen |
| [`int_repair_workshop`](int_repair_workshop/) | 19.0.1.0.0 | Werkstattfelder am Reparaturauftrag (Auftragsart, Eingangsdatum, Resttage, sieben Werkstattstufen mit Mitarbeiter) und eine Listenansicht; löst die manuelle Excel-Reparaturübersicht ab | Liste ist als Übersicht für die Produktion gedacht, **keine** Belegmaske für Kunde, Kostenvoranschlag oder Versand |
| [`int_generic`](int_generic/) | 19.0.1.0.1 | Sammelmodul für kleine Anpassungen ohne Bindung an eine Business-App; bisher: Spaltenreihenfolge in Listenansichten per Drag & Drop | wächst nur um Anpassungen, die nicht mehr als `base` und `web` brauchen |
| [`int_fleet_kanban_width`](int_fleet_kanban_width/) | 19.0.1.0.0 | Die Spalten des Fahrzeug-Kanban teilen sich die verfügbare Breite, statt zu scrollen | bewusst eigenes Modul, weil es an `fleet` hängt |
| [`int_legacy_erp_import`](int_legacy_erp_import/) | 19.0.1.0.0 | Testballon: Produktfelder aus dem Alt-ERP (Artikelnummer, Bestellnummer, Hersteller-Referenzen) für die Frage, ob ein Umstieg sinnvoll ist | rein zum Testimport, kein produktiver Datenimport |
| [`onlyoffice_odoo`](onlyoffice_odoo/) | 6.3.0 | Anbindung an ONLYOFFICE Docs (Drittanbieter-Modul, Autor ONLYOFFICE) | `int_filemanager` hängt davon ab; einige Prüfbefunde dort sind Altlasten des Drittanbieters |

Grundsatz zum Zuschnitt: ein Modul je fachlicher Abhängigkeit (auch bei winzigen Änderungen), app-unabhängige Anpassungen gemeinsam in
`int_generic`. Odoo sucht `addons_path` nur eine Ebene tief, deshalb liegen alle Module flach im Wurzelordner.

## Umgebung

Drei **voneinander getrennte** Unraid-Server, jeder mit eigener Odoo-19-Instanz in Docker, an verschiedenen Standorten und in verschiedenen Netzen.
Sie teilen weder Datenbank noch Addons-Ordner; jede Änderung muss je Instanz eingespielt werden.

| Name in den Docs | IP | Odoo / Container | Zugang | Hinweis |
|---|---|---|---|---|
| **HM-SRV** | 192.100.0.119 | `Odoo19` (Datenbank getrennt) | SSH-Alias `unraid-odoo` | Addons unter `/mnt/user/appdata/odoo18/extra-addons`. Der Ordnername ist irreführend: es ist Odoo 19. Hier läuft vorerst der Stand von `master` |
| **Tower** | 192.168.188.67 | `odoo`, `odoo_db`, `OnlyOfficeDocumentServer`; Testumgebung `fmtest_*`, `fmv2_*` | SSH-Alias `unraid` | Addons unter `/mnt/user/appdata/odoo/extra-addons` (einfache Kopie, nur `int_filemanager` und `onlyoffice_odoo`); Test-Instanz für den Branch (Port 8085) |
| **Tower (192.168.178.73)** | 192.168.178.73 | eigene Odoo-Instanz | in diesen Docs kein Alias | Container, Addons-Ordner, Datenbank und deployter Stand sind hier nicht dokumentiert (noch zu ergänzen) |

**Namensregel:** "Tower" ohne Zusatz bedeutet in allen Docs, Skripten und Kommentaren **192.168.188.67** (SSH-Alias `unraid`). Der andere Tower wird immer mit
seiner IP genannt.

**Erreichbarkeit** (geprüft 2026-10-02 vom Arbeitsrechner mit 192.100.0.182): im Firmennetz 192.100.0.x ist nur HM-SRV per SSH erreichbar. Beide Tower liegen in anderen Netzen (192.168.188.x und 192.168.178.x) und laufen von dort in den Timeout; der Alias `unraid` ist auf diesem Rechner nicht eingerichtet. Angaben zu den Towern in diesen Docs stammen aus Sitzungen auf einem Rechner mit Zugang und sind von hier nicht nachprüfbar.

Einordnung (Stand 2026-09-18): Odoo ist noch **kein** produktives ERP. Das Alt-ERP läuft weiter, ein Umstieg ist nicht entschieden;
Grundlage dafür sind die Analysen in [`docs/erp/`](docs/erp/).

Das [`Dockerfile`](Dockerfile) baut ein Odoo-19-Image mit den Bibliotheken für `int_filemanager` (Audio-Metadaten, Tesseract/OCRmyPDF, pdfplumber, pyjwt). Es geht vom auf HM-SRV deployten Image aus, hat aber den Start-Wrapper für die SMB-Freigaben nicht mehr.

## Repo-Aufbau

| Pfad | Inhalt |
|---|---|
| `int_*/`, `onlyoffice_odoo/` | die Module (jedes mit eigenem `__manifest__.py`) |
| [`docs/`](docs/) | Dokumentation, Einstieg [`docs/README.md`](docs/README.md) |
| `docs/odoo_regeln/` | Odoo-19-Regeln: Coding und Git Guidelines mit Hausregeln, Developer Reference |
| `tools/fmconverter/` | Umwandler-Container für `int_filemanager` (Vorschauen, OCR, Metadaten) |
| `tools/v2check/` | Prüf- und Testskripte für `int_filemanager` auf dem Tower |
| `scripts/lint/` | Läufe für `test_lint` und odoo-ls, Verwaltung der Altbestand-Ausnahmen |
| `.pre-commit-config.yaml`, `.pylintrc*`, `.ruff.toml`, `eslint.config.cjs`, `prettier.config.cjs` | Prüfautomatik für neuen Code |
| [`CLAUDE.md`](CLAUDE.md) | verbindliche Arbeitsregeln für die Arbeit mit Claude Code |

## Branches und Tags

- `master`: der bisherige Stand von `int_filemanager` (laufend auf HM-SRV und Tower) plus Dokumentation und Prüfautomatik.
- `feature/int-filemanager-v2`: der Neubau von `int_filemanager`, aktuelle Entwicklung. Ein Zeitpunkt für den Merge nach `master` ist nicht dokumentiert.
- Tag `int_filemanager-v1`: der Stand von `master` vor dem Neubau. Tag `docs-vor-aufraeumen-2026-10-02`: alle Dokumente vor der Aufräumaktion.

## Entwickeln

- **Regeln:** vor Code in einem Bereich die zugehörige Datei in [`docs/odoo_regeln/`](docs/odoo_regeln/) lesen; vor jeder Aussage "das gibt es in Odoo nicht"
  den Odoo-19-Core durchsuchen (Regeln in `CLAUDE.md`). Neuer Code englisch, Oberflächentexte englisch mit deutscher Übersetzung in `i18n/de.po`.
- **Prüfen:** `pre-commit run` für neuen Code (Altdateien stehen im LEGACY-Block); `test_lint` und odoo-ls auf dem Tower. Aufruf und Verifikationsstand:
  [`docs/pruefautomatik_2026-10-02.md`](docs/pruefautomatik_2026-10-02.md). Für `int_filemanager`: `tools/v2check/v2check.sh`.
- **Commits:** `[TAG] modul: kurzer Satz` (Odoo-Git-Guidelines), Commit nur auf Ansage.
- **Testinstanz** von `int_filemanager`: siehe [`docs/int_filemanager_stand.md`](docs/int_filemanager_stand.md), Abschnitt Testumgebung.

## Deploy auf HM-SRV (bisheriges Vorgehen, Stand 2026-09)

Das Git-Repo und der im Container gemountete Addons-Ordner sind **zwei getrennte Kopien ohne automatischen Abgleich**. Ein Commit bewirkt im
laufenden Odoo nichts. Der Windows-Mount `X:\odoo18\extra-addons` lässt sich für Dateien, die der Container erzeugt hat, oft nicht überschreiben.

1. Dateien per SSH (`unraid-odoo`) direkt auf den Host-Pfad schreiben (z. B. base64 oder `tar` über SSH), nicht über den `X:`-Mount.
2. Modul-Upgrade als kurzlebigen Zusatzprozess im laufenden Container:
   `docker exec --user=100:101 Odoo19 odoo -c /etc/odoo/odoo.conf -d <datenbank> -u <modul> --stop-after-init`. Der Hauptprozess läuft weiter und übernimmt die
   neue Registry per Datenbank-Signal.
3. Bei Änderungen an JS, XML-Templates oder SCSS reicht das Upgrade nicht immer, der Asset-Cache bleibt alt: danach `docker restart Odoo19`.
4. Prüfen, was wirklich geladen ist (z. B. `ir_ui_view.arch_db` per `psql`), bevor man dem Browser glaubt.

Vor einem Odoo-Image-Update auf HM-SRV die Datenbank-Kollation prüfen (muss `C` sein, sonst können Teilbäume beim Verschieben beschädigt werden).
Einzelheiten: [`docs/int_filemanager_entscheidungen.md`](docs/int_filemanager_entscheidungen.md), Abschnitt 2.
