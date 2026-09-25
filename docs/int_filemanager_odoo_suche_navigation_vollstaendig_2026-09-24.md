# int_filemanager: Vollständige Bestandsaufnahme von Suche/FolderTree/Breadcrumbs gegen den Odoo-Kern

Stand 2026-09-24. Dritte Prüfung in derselben Reihe (nach Bildverarbeitung und Listenansicht) —
vollständig, nicht stichprobenartig: `native_search_model.js` (109 Zeilen), `folder_tree.js`
(190 Zeilen), die Breadcrumb-Abschnitte von `filemanager_controller_mixin.js` (1672 Zeilen
Gesamtdatei) und `filemanager_file_search.xml` auf `int_filemanager`-Seite vollständig gelesen;
`search_model.js`, `search_panel.js` (451 Zeilen), `breadcrumbs.js`/`.xml` sowie die serverseitige
`search_panel_select_range`-Familie in `addons/web/models/models.py` im Odoo-19-Kern vollständig
gelesen. Reine Recherche, nichts umgesetzt.

---

## 1. FolderTree ersetzt Odoos native SearchPanel-Kategorie — jetzt am Quellcode nachgerechnet, nicht nur zitiert

`int_filemanager` hat am 2026-09-16 sein eigenes, wirklich lazy ladendes `FolderTree`
(`folder_tree.js`) gebaut, um Odoos natives `<searchpanel type="category">`-Kategoriefeld
(`parent_id`) als Ordner-Navigationsquelle zu ersetzen. Der eigene Code-Kommentar behauptet: bei
69k Ordnern/1,38 Mio. Dateien sei **jeder** native Pfad mehrere Sekunden teuer — sowohl mit
`expand="1"` als auch ohne. Diese Behauptung wurde jetzt **direkt an der Odoo-19-Quelle
nachvollzogen**, nicht nur übernommen:

- `search_model.js:_fetchCategories()` ruft serverseitig `search_panel_select_range()` auf
  (`addons/web/models/models.py:1646-1775`, vollständig gelesen).
- **Ohne `expand`** (Standardfall beim ersten Öffnen des Baums): `hierarchize` ist serverseitig
  **standardmäßig `True`** (Zeile 1714, `kwargs.get('hierarchize', True)`) — für ein
  `parent_id`-Feld mit vorhandenem `_parent_name` bleibt `hierarchize` damit praktisch immer aktiv,
  der scheinbar günstige Kurzschluss `if not (expand or hierarchize or comodel_domain): return
  domain_image.values()` (Zeile 1738) ist für diesen Feldtyp **faktisch unerreichbar**, außer ein
  Aufrufer setzt `hierarchize=False` explizit. Stattdessen läuft `_search_panel_field_image()` →
  `_search_panel_domain_image()` (Zeilen 1404-1508), die intern `formatted_read_group(domain,
  [field_name], ['__count'])` aufruft (Zeile 1491) — bei leerem Suchdomain (Wurzelansicht, "Alle
  Ordner") ist das ein **`GROUP BY parent_id` über die gesamte, ungefilterte Tabelle**. Bei 1,38
  Mio. Zeilen exakt die vom Kommentar behauptete teure Operation — jetzt bis auf die konkrete
  SQL-Charakteristik verifiziert, nicht nur behauptet.
- **Mit `expand="1"`**: `domain_image` wird übersprungen (nur wenn zusätzlich `enable_counters`
  falsch ist), stattdessen läuft `Comodel.search_read(comodel_domain, field_names, limit=limit)`
  (Zeile 1754) mit unverändertem `comodel_domain` (Standard `[]`) — ein **vollständiger Read über
  alle ~69k Ordner-Datensätze**, unabhängig vom aktuellen Suchfilter. Ebenfalls exakt die im
  Kommentar behauptete Charakteristik.

**Ergebnis der Nachprüfung: die Begründung für den Eigenbau ist korrekt und jetzt zusätzlich am
exakten Codepfad (nicht nur per `EXPLAIN ANALYZE` auf der Live-Instanz) bestätigt.** Kein
Korrekturbedarf, aber ein wichtiger, bisher nicht dokumentierter Zusatzfund: der scheinbare
"billige Pfad" in `search_panel_select_range()` existiert nur auf dem Papier, weil `hierarchize`
serverseitig standardmäßig aktiv ist — relevant, falls `int_filemanager` diesen Baustein je erneut
in Betracht zieht (z.B. für eine kleinere, nicht-hierarchische Kategorie wie `status_id`, wo
`hierarchize` mangels `_parent_name` automatisch `False` wird und der billige Pfad dort tatsächlich
greifen würde).

**Zusätzlich bestätigt:** `folder_tree.js`s eigene Klick-Semantik (Navigation + Auf-/Zuklappen in
einem Klickziel, Zuklappen nur wenn bereits aktiv+aufgeklappt) wurde laut eigenem Kommentar 1:1 an
`search_panel.js:toggleCategory()` (Zeilen 303-317, hier verifiziert) nachgebildet — bewusste
Wiederverwendung des nativen Interaktionsmusters, nicht nur der Daten-Idee.

---

## 2. `IntFilemanagerSearchModel` — korrekt am nativen Erweiterungspunkt angesetzt

`native_search_model.js` überschreibt ausschließlich `_getDomain()` (den zentralen Punkt, an dem
`SearchModel` alle Domain-Quellen zusammenführt) und fügt genau eine zusätzliche AND-Klausel hinzu.
Kein Duplizieren der nativen Domain-Berechnung selbst (`super._getDomain(params)` wird weiterhin
aufgerufen). Die Ordnerpfad-URL-Persistenz nutzt mit `router.addLockedKey()` einen von Odoo dafür
vorgesehenen, dokumentierten Erweiterungspunkt (verifiziert: ohne diesen Eintrag verwirft Odoos
eigener `pushState({replace:true})`-Aufruf bei jedem Controller-Mount alle nicht gesperrten
URL-Query-Keys). Kein Eigenbau-Risiko gefunden — dies ist der schmalstmögliche Override.

---

## 3. Natives `<search>`-Arch wird vollständig und korrekt weiterverwendet

`filemanager_file_search.xml` (vollständig gelesen) nutzt ausschließlich native Bausteine: Freitext-
Suchfelder (`name`, `tag_ids`, `status_id`, `content_text` — reiht sich laut eigenem Kommentar
automatisch ins native "Suche nach X: Y"-Dropdown ein), boolesche `<filter>`-Domains, `group_by`,
`<separator/>`. Einzige Nicht-Standard-Nutzung: `filter_search_recursive` ist ein reiner
Marker-Filter ohne eigene Domain, dessen Aktivierung `native_search_model.js` anhand des
`name`-Attributs erkennt (`RECURSIVE_FILTER_NAME`, per `node.getAttribute("name")` aus
`search_arch_parser.js` verifiziert) — eine acht Zeilen kleine, bewusste Zusatzinterpretation eines
sonst ungenutzten Filters, kein Duplizieren der Filter-Infrastruktur selbst.

---

## 4. Breadcrumbs — Desktop vollständig nativ, Mobil bewusst separat (mit einer bisher unerwähnten Nuance)

**Desktop:** `updateBreadcrumbs()` (`filemanager_controller_mixin.js:758-802`) schreibt die aus dem
aktuellen Ordnerpfad abgeleiteten Krumen **direkt in `env.config.breadcrumbs`** — Odoos eigenes,
für den gesamten Webclient zentrales Action-Stack-Array, gerendert vom nativen
`Breadcrumbs`-Component (`addons/web/static/src/search/breadcrumbs/breadcrumbs.js`, 20 Zeilen,
vollständig gelesen). Kein eigenes Breadcrumb-Rendering auf Desktop. Ein dokumentierter, live auf
Tower reproduzierter Timing-Bug (`onMounted()` statt synchron in `setup()` aufrufen, sonst Absturz
in Odoos eigenem Template beim allerersten View-Wechsel) zeigt echtes Verständnis der nativen
Rendering-Reihenfolge, keine Blackbox-Behandlung.

**Mobil:** bewusst **nicht** über `env.config.breadcrumbs`, sondern über eine eigene
`mobileBreadcrumbs`-Property + eigenes Template (`native_list_view.xml`). Begründung im Code:
Odoos natives Breadcrumb-Template rendert einen einzelnen vs. mehrere Einträge sichtbar
unterschiedlich (kleinere Schrift, zusätzlicher Zurück-Pfeil ab dem zweiten Eintrag) — auf dem
schmalen mobilen App-Navbar unerwünscht, live beobachtet.

**Bisher nicht dokumentierte, jetzt geprüfte Nuance:** `breadcrumbs.xml` (vollständig gelesen) hat
**bereits eine eigene native Mobil-Kollabierung** (`t-if="env.isSmall"`, Zeilen 6-33):
`visiblePathBreadcrumbs = props.breadcrumbs.slice(-3, -1)` (die letzten zwei Pfad-Krumen vor der
aktuellen bleiben sichtbar) und `collapsedBreadcrumbs = props.breadcrumbs.slice(0, -3).reverse()`
(alles Ältere in ein Dropdown). Das ist aber eine **feste Anzahl-Heuristik** (immer genau die
letzten zwei sichtbar), keine Breiten-Messung — strukturell etwas anderes als `int_filemanager`s
eigene `_checkMobileBreadcrumbOverflow()` (echtes `scrollWidth > clientWidth`, passt sich an
tatsächliche Segmentlänge und Bildschirmbreite an). Da `int_filemanager` auf Mobil `env.config.
breadcrumbs` ohnehin leer lässt (siehe oben), kommt diese native Kollabierung für die
Ordner-Krumen nie zur Anwendung — der im Code genannte Styling-Grund bleibt der eigentliche,
bestätigte Ausschlussgrund; die native Kollabierung wäre für den eigenen, adaptiveren Anspruch
ohnehin nicht ausreichend gewesen. Kein Korrekturbedarf, aber eine Präzisierung: "Odoo hat dafür
gar keine Kollabierung" wäre falsch gewesen — richtig ist "Odoos Kollabierung ist vorhanden, aber
sowohl stilistisch als auch von der Anpassungsgenauigkeit her nicht das, was gebraucht wird".

---

## 5. Gesamteinordnung

| Baustein | Nativ genutzt? | Bewertung nach vollständiger Prüfung |
|---|---|---|
| Ordner-Navigationsquelle | Nein (FolderTree, Eigenbau) | **Begründung jetzt bis zum exakten SQL-Verhalten verifiziert**, nicht nur per Kommentar behauptet — Eigenbau bleibt richtig |
| Domain-Zusammenführung | Ja (`_getDomain()`-Override) | Minimal-invasiver, korrekter nativer Erweiterungspunkt |
| Freitextsuche/Filter/Gruppierung | Ja, vollständig | Kein Eigenbau, nichts zu vermeiden |
| Breadcrumbs Desktop | Ja, vollständig (`env.config.breadcrumbs`) | Kein Eigenbau |
| Breadcrumbs Mobil | Nein (eigener Header) | Begründet (Styling-Bug + native Kollabierung ist fester, weniger genauer Mechanismus als die eigene Breitenmessung) |

Alle drei geprüften Eigenbau-Stellen (FolderTree, Klick-Semantik-Nachbau, Mobil-Breadcrumbs) sind
nach vollständiger Prüfung sachlich begründet — anders als teilweise bei der Bild-/Listenansicht-
Prüfung wurde hier **kein ungenutzter nativer Baustein gefunden, der etwas Bestehendes ersetzen
könnte**. Der Wert dieser Prüfung liegt stattdessen darin, zwei bisher nur behauptete
Kosten-Charakteristiken (SearchPanel-GROUP-BY, native Mobil-Kollabierung) jetzt am exakten
Quellcode bestätigt zu haben.
