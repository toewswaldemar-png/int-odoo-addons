# int_filemanager: natives Favoriten/Lesezeichen-System (`ir.filters`) — vermutlich bereits funktionsfähig, ungetestet

Stand 2026-09-24. Elftes Dokument der Reihe. Neuer Ausgangspunkt: Odoos natives
"Favoriten"-Menü (Stern-Symbol in der Suchleiste, "Aktuelle Suche speichern") — bisher in der
gesamten Reihe nicht geprüft. Ergebnis: ein konkreter, potenziell bereits ohne jeden Zusatzcode
funktionsfähiger Baustein für "Ordner als Lesezeichen speichern", der noch **live verifiziert**
werden müsste, aber strukturell am Code sauber hergeleitet ist. Reine Recherche, nichts umgesetzt.

---

## Der Mechanismus, vollständig nachvollzogen

`addons/web/static/src/search/custom_favorite_item/custom_favorite_item.js` (96 Zeilen, komplett
gelesen) → `createNewFavorite()` → `_getIrFilterDescription()`
(`addons/web/static/src/search/search_model.js:1977-2022`, komplett gelesen):

```js
const domain = this._getDomain({ raw: true, withGlobal: false }).toString();
```

**Entscheidende Stelle:** `this._getDomain(...)` ist exakt dieselbe Methode, die
`IntFilemanagerSearchModel` in `native_search_model.js` überschreibt (siehe
`int_filemanager_odoo_suche_navigation_vollstaendig_2026-09-24.md`, Abschnitt 2) — dort wird die
aktuelle Ordnerpfad-Domain (`_getIntFilemanagerFolderDomain()`) per AND an die native Domain
angehängt. **Wenn ein Nutzer im aktuell offenen Ordner auf das Stern-Symbol klickt und die Suche
als Favorit speichert, würde die dabei serialisierte Domain automatisch die aktuelle
Ordnerbeschränkung enthalten** — nicht weil `int_filemanager` das eigens eingebaut hätte, sondern
weil der native Favoriten-Mechanismus grundsätzlich genau die (ggf. überschriebene) `_getDomain()`
abfragt, die jede Ansicht ohnehin für ihre Daten verwendet.

Serverseitig (`odoo/addons/base/models/ir_filters.py`, 126 Zeilen, komplett gelesen): reines,
generisches `ir.filters`-Modell — `domain`/`context` als Text, `is_default` (automatisches Anwenden
beim Öffnen der Ansicht), `user_ids` (privat vs. geteilt), `action_id`-Bindung (Favorit nur für
diese eine Action/dieses Menü sichtbar oder global). Funktioniert für jedes Modell automatisch,
keine modell-spezifische Anpassung nötig oder vorhanden.

**Kontrolliert, dass `int_filemanager` diesen Mechanismus nirgends unterdrückt oder anfasst:**
Grep über alle eigenen `native_ui`-Dateien nach "favorite"/"Favorite" — **keine Treffer**. Die
eigene `SearchBar`-Komponente wird unverändert aus dem Kern übernommen (`native_list_view.js`:
`import { SearchBar } from "@web/search/search_bar/search_bar"`), keine eigene Einschränkung.

---

## Was das praktisch bedeuten würde

Ein Nutzer, der oft in einen bestimmten Ordner navigiert, könnte dort auf "Favoriten speichern"
klicken — und bekäme (falls sich die Herleitung live bestätigt) eine echte, dauerhafte
Lesezeichen-Funktion für Ordner **komplett kostenlos**: als "Standardfavorit" markiert, öffnet
sich dieser Ordner sogar automatisch beim nächsten Öffnen von `int_filemanager` (`is_default`).
Das wäre eine bisher in keinem Feature-Katalog dieser Session erwähnte, aber naheliegende
Explorer-Paritätsfunktion (vgl. Windows-Explorer "Schnellzugriff"/Favoriten).

**Ausdrücklich als Hypothese markiert, nicht als bestätigte Tatsache:** die Code-Herleitung ist
vollständig und in sich stimmig, aber nicht live getestet — insbesondere ungeprüft, ob die
`recursive`-Markierung (`filter_search_recursive`, ein reiner Namens-Marker ohne eigene Domain,
siehe `native_search_model.js`) beim Wiederherstellen eines Favoriten korrekt erneut als aktiver
Suchbegriff erkannt wird, und ob das gespeicherte `domain`-Textfeld beim erneuten Anwenden exakt
so interpretiert wird wie erwartet. **Nächster sinnvoller Schritt wäre ein kurzer Live-Test**
(Ordner öffnen → Favorit speichern → Browser neu laden → Favorit anwenden → prüfen, ob wirklich
genau dieser Ordner erscheint), keine Implementierung.

---

## Einordnung in die Gesamtkarte

Ergänzt `int_filemanager_odoo_such_navigationsmuster_gesamtkarte_2026-09-24.md` um einen
18. Baustein: **natives `ir.filters`/Favoriten-System — potenziell bereits nutzbar, ungetestet,
kein Code geschrieben oder geändert.** Anders als alle bisherigen Funde dieser Reihe keine
"Chance, die noch gebaut werden müsste", sondern möglicherweise eine **bereits vorhandene,
unbemerkte Fähigkeit** — der bisher am wenigsten aufwendige denkbare Fund, falls er sich bestätigt.
