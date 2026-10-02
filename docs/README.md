# docs/ – Wegweiser

Stand 2026-10-02. Projektbeschreibung: [`../README.md`](../README.md). Arbeitsregeln für Claude Code: [`../CLAUDE.md`](../CLAUDE.md).

Frühere Dokumente (Konzepte, Pläne, Übergabe-Verlauf, Messungen, Recherchen, Prototypen, Doku des bisherigen Stands) stehen im Git-Tag
`docs-vor-aufraeumen-2026-10-02`: `git show docs-vor-aufraeumen-2026-10-02:docs/<Pfad>`.

## int_filemanager

| Dokument | Wofür |
|---|---|
| [`int_filemanager_stand.md`](int_filemanager_stand.md) | **Einstieg:** Stand und Abnahme je Schritt, nächste Schritte, bekannte Mängel, Arbeitsweise, Testumgebung, Aufbau, Plan der Übernahme |
| [`int_filemanager_entscheidungen.md`](int_filemanager_entscheidungen.md) | Grundregeln I1–I13, warum so, was verworfen wurde, Odoo-19-Fallen |
| [`int_filemanager_paperoffice_ideenkatalog_2026-10-01.md`](int_filemanager_paperoffice_ideenkatalog_2026-10-01.md) | Backlog: Ideen A1–H6 aus PaperOffice Classic mit Odoo-Weg, Aufwand, Einordnung, offenen Entscheidungen |

## Code-Regeln

| Dokument | Wofür |
|---|---|
| [`odoo_regeln/`](odoo_regeln/) | Odoo-19-Regeln: Coding und Git Guidelines mit den Hausregeln dieses Repos, Developer Reference in Themendateien. Einstieg: [`odoo_regeln/odoo_regeln_index_2026-10-02.md`](odoo_regeln/odoo_regeln_index_2026-10-02.md) |
| [`pruefautomatik_2026-10-02.md`](pruefautomatik_2026-10-02.md) | pre-commit, `test_lint`, odoo-ls: Aufruf, Verifikationsstand, Altbefunde, Was die Werkzeuge prüfen |

## Alt-ERP und Odoo-Umstieg

[`erp/`](erp/): Reverse Engineering des Alt-ERP (Delphi-Anwendung `Herrmann.exe`) und Vergleich mit Odoo 19. Hängt nicht an einem Addon,
sondern ist die Grundlage für die Frage, ob und wie ein Umstieg gelingt.

| Dokument | Wofür |
|---|---|
| [`erp/erp-odoo-modulvergleich.md`](erp/erp-odoo-modulvergleich.md) | Menü- und Feldübersicht des Alt-ERP gegen Odoo-Standardmodule und `int_*`-Addons |
| [`erp/erp-odoo-abschlussdokument.md`](erp/erp-odoo-abschlussdokument.md) | Feldkatalog mit Einstufung Information / Verknüpfung / Logik |
| [`erp/erp-odoo-plattform-analyse-2026-09-21.md`](erp/erp-odoo-plattform-analyse-2026-09-21.md) | Odoo allgemein: welche Plattform-Bausteine welche Alt-ERP-Funktionen ersetzen |
| [`erp/legacy-schema/`](erp/legacy-schema/) | Belege: Schema, Prozeduren, Formulare (`dfm-tool/` zum Auslesen der Delphi-Formulare) |

## Betrieb

| Dokument | Wofür |
|---|---|
| [`meshcentral-zugang.md`](meshcentral-zugang.md) | Fernzugriff auf die Rechner per MeshCentral (CLI-Wrapper) |
