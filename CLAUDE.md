# int-odoo-addons

Projektbeschreibung und Modulübersicht: `README.md`.

## Odoo 19 prüfen

Für Konventionen und unterstützte Verwendung gilt die offizielle Odoo-19-Dokumentation. Für das tatsächliche Laufzeitverhalten gilt der zur Installation passende Odoo-19-Quellcode.

Lokale Quellen:

- `docs/odoo19_reference/INDEX.md`: unveränderte Volltextkopie der offiziellen Odoo-19-Developer-Dokumentation,
- `docs/owl2_reference/INDEX.md`: Referenz der von Odoo 19 verwendeten Owl-Version,
- `docs/odoo/`: optionale, nicht versionierte Kopie des Odoo-19-Quellcodes; Branch und Commit müssen zur Installation passen.

Prüfablauf:

1. Die passende Seite der offiziellen Dokumentation lesen.
2. Signaturen und Laufzeitverhalten im passenden Odoo-Core und in vergleichbaren Odoo-Modulen prüfen.
3. Bei Widerspruch oder verbleibender Unklarheit einen kleinen reproduzierbaren Test ausführen.
4. Bestätigte Doku/Core-Abweichungen mit Fundstelle, Core-Commit und Test in `docs/odoo19_abweichungen.md` dokumentieren.

Zusammenfassungen und frühere Regeldestillate sind keine Quelle. Dieses Repository definiert keine zusätzlichen Odoo-Coding-, Review- oder Prozessregeln.
