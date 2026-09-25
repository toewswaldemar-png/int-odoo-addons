# int_filemanager: Ordnernavigation — erschöpfende Prüfung über ALLE hierarchischen Modelle im Odoo-Kern

Stand 2026-09-24. Siebte und methodisch vollständigste Prüfung in dieser Reihe. Odoo hat mehrere
Millionen Zeilen Code — buchstäblich jede Datei einzeln zu lesen ist nicht sinnvoll möglich. Statt
weiterer thematischer Stichproben wurde deshalb die **Grundgesamtheit selbst vollständig
bestimmt**: jedes einzelne Modell im gesamten Repository (`addons/` + `odoo/`), das überhaupt eine
echte, native Baumstruktur besitzt (`_parent_store = True`), gefunden und **einzeln** auf seine
Navigations-Lösung geprüft — keine Annahme, jedes Modell einzeln am Code verifiziert.

```
grep -rln "_parent_store\s*=\s*True" --include=*.py addons odoo
```

Ergebnis: **genau 12 Modelle im gesamten Odoo-Kern**, keines übersehen, keines durch Auswahl
vorgefiltert:

| # | Modell | Datei | Typischer Umfang |
|---|---|---|---|
| 1 | `hr.department` | `addons/hr/models/hr_department.py` | klein-mittel (Dutzende bis Hunderte) |
| 2 | `product.category` | `addons/product/models/product_category.py` | klein-mittel |
| 3 | `stock.location` | `addons/stock/models/stock_location.py` | **potenziell groß** (Lager/Logistik) |
| 4 | `stock.package` (Quant Package) | `addons/stock/models/stock_package.py` | **potenziell groß** |
| 5 | `uom.uom` | `addons/uom/models/uom_uom.py` | winzig (Maßeinheiten-Umrechnung) |
| 6 | `website.menu` | `addons/website/models/website_menu.py` | klein (Navigationsmenü) |
| 7 | `product.public.category` | `addons/website_sale/models/product_public_category.py` | klein-mittel |
| 8 | `ir.ui.menu` | `odoo/addons/base/models/ir_ui_menu.py` | klein-mittel (App-Menü) |
| 9 | `res.company` | `odoo/addons/base/models/res_company.py` | winzig (Mandanten) |
| 10 | `res.partner.category` | `odoo/addons/base/models/res_partner.py` | klein (Kontakt-Tags) |
| 11 | `analytic.plan` | `addons/analytic/models/analytic_plan.py` | klein-mittel |
| 12 | `test_orm` (Testfixture) | `odoo/addons/test_orm/models/test_orm.py` | irrelevant (Test) |

**Wichtige Korrektur einer eigenen Vermutung:** `res.partner` (Kontakte) selbst hat **kein**
`_parent_store` — nur `res.partner.category` (Kontakt-Tags) hat es. Die
"Übergeordnetes Unternehmen"-Beziehung bei Kontakten ist ein einfaches `many2one`, keine
Nested-Set-Hierarchie. Die eigene Vermutung, eine potenziell sehr große Kontaktdatenbank könnte ein
bisher übersehenes Vorbild für große Hierarchien sein, war damit falsch — durch Nachprüfen
widerlegt, nicht durch Weglassen vermieden.

---

## Die zwei einzigen Modelle mit realistisch großem Umfang — beide geprüft, kein Baum-Widget

**`stock.location`** (Lagerorte) und **`stock.package`** (verschachtelte Versandpackstücke,
`parent_package_id`) sind die einzigen beiden Modelle in der ganzen Liste, deren reale
Größenordnung mit `int_filemanager`s Problem vergleichbar sein kann (große Logistikbetriebe können
zehntausende Lagerplätze/Packstücke haben). Beide vollständig geprüft:

- **Keine SearchPanel-Nutzung** für die Ortshierarchie (`view_location_search` enthält kein
  `<searchpanel>`-Element, geprüft).
- **Kein eigenes JS-Tree-Widget** (`find addons/stock/static/src -iname "*location*"` — keine
  Treffer).
- Stattdessen exakt dasselbe Muster wie `product.category`: ein rekursiv berechnetes, gespeichertes
  `complete_name`-Feld (`stock_location.py:18-30`: `_order = 'complete_name, id'`,
  `_rec_names_search = ['complete_name', 'barcode']`), `stock.package` identisch
  (`stock_package.py:21-26`: `_rec_name = 'complete_name'`). **Reine flache Liste, sortiert und
  durchsucht über den vollen Textpfad — keine interaktive Baumansicht.**

`analytic.plan` (Buchhaltung, Kostenstellen-artige Struktur) nutzt exakt dasselbe Muster
(`analytic_plan.py:17,52-54,139-143`, geprüft).

---

## Zusammengeführtes Gesamtbild über alle 12 Modelle

| Kategorie | Modelle | Lösung |
|---|---|---|
| Klein, aber mit echtem Nutzer-Browsing-Bedarf | `hr.department`/`hr.employee` | eigener `hr_org_chart`-Controller (siehe `int_filemanager_odoo_ordnernavigation_bausteine_2026-09-24.md`) |
| Klein, editierbar | `website.menu` | eigener `edit_menu.js` + `useNestedSortable` (siehe `int_filemanager_odoo_navigation_weitere_bausteine_2026-09-24.md`) |
| Klein, Filter/Kategorisierung | `product.category`, `product.public.category`, `res.partner.category` | natives `<searchpanel type="category">` |
| Klein, App-intern | `ir.ui.menu` | eigener eager-Load + `localStorage`-Cache (`menu_service.js`) |
| Winzig | `uom.uom`, `res.company` | keine dedizierte Navigation nötig |
| **Potenziell groß** | **`stock.location`, `stock.package`, `analytic.plan`** | **kein Baum-Widget — flache, textpfad-sortierte/-durchsuchte Liste (`complete_name`)** |

**Der entscheidende, jetzt vollständig abgesicherte Befund:** In keinem einzigen der 12
Modelle im gesamten Odoo-Kern — nicht einmal in den beiden, deren reale Größenordnung mit
`int_filemanager` vergleichbar sein kann — existiert eine **lazy ladende, indentierte
Baum-Seitenleiste** wie `FolderTree`. Odoos eigene Antwort auf "potenziell große Hierarchie" ist
durchgängig: **kein interaktiver Baum, sondern eine flache, über den vollen Pfadtext
sortierte/durchsuchbare Liste.** Nur `web_hierarchy` (Organigramm-Karten, siehe
`int_filemanager_odoo_ordnernavigation_bausteine_2026-09-24.md`) und die beiden bespoke
Controller (`hr_org_chart`, eigene `/int_filemanager/tree`-Route) laden überhaupt lazy — und beide
sind für kleine bis mittlere, nicht für dateisystemgroße Hierarchien gebaut.

---

## Fazit dieser Prüfungsreihe insgesamt

`int_filemanager`s `FolderTree` hat damit **kein Vorbild und keinen Ersatzbaustein irgendwo im
gesamten Odoo-Kern** — nicht, weil die Suche nicht breit genug war, sondern weil erschöpfend
nachgewiesen ist, dass Odoo selbst für diese Größenordnung an Hierarchie grundsätzlich keinen
interaktiven Baum baut, sondern auf Textsuche über einen vollen Pfadnamen ausweicht (Fund 2 aus
`int_filemanager_odoo_navigation_neue_perspektiven_2026-09-24.md` — dieselbe Lösung, jetzt an drei
weiteren realen Modellen bestätigt, nicht nur an zwei). Eine Kombination aus beidem — `FolderTree`
zum Browsen, plus eine `complete_name`/`name_search`-basierte Schnellsuche zum Direkt-Springen wie
in Abschnitt 2 des genannten Dokuments vorgeschlagen — deckt sich damit nicht nur mit einem, sondern
mit **fünf unabhängigen nativen Vorbildern** (`hr.department` bzgl. Org-Chart-Ergänzung,
`product.category`, `stock.location`, `stock.package`, `analytic.plan` bzgl. der
Textpfad-Suche) und ist die am besten durch den eigenen Odoo-Kern abgesicherte Kombination, die in
dieser gesamten Recherchereihe gefunden wurde.
