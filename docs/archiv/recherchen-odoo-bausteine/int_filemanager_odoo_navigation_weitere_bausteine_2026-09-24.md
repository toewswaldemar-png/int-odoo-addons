# int_filemanager: Ordnernavigation — sechste Prüfung, ganze Dateien statt Stichproben

Stand 2026-09-24. Sechste Prüfung in der Reihe, auf ausdrücklichen Nutzerwunsch **jede betrachtete
Datei vollständig gelesen, keine Stichproben** — inklusive einer expliziten Korrektur eines Fehlers
aus dem vorherigen Dokument, der genau daraus entstand, dass eine Datei NICHT vollständig gelesen
wurde. Geprüft (alle vollständig gelesen): `router.js` (437 Zeilen), `pager.js` (208 Zeilen),
`menu_service.js` (110 Zeilen), `nested_sortable.js` (407 Zeilen), `edit_menu.js` (420 Zeilen,
Website-Menü-Editor), Ausschnitte aus `mail`s `hooks.js` (673 Zeilen Gesamtdatei, die zwei
relevanten Funktionen vollständig gelesen). Reine Recherche, nichts umgesetzt.

---

## 1. Korrektur einer eigenen Fehleinschätzung: `nested_sortable.js` ist kein "nur flache Listen"-Baustein

Im vorherigen Dokument (`int_filemanager_odoo_ordnernavigation_bausteine_2026-09-24.md`, Abschnitt 4)
steht: *"`nested_sortable.js` geprüft und verworfen — reine Drag&Drop-Sortierhilfe für flache
Listen ..., keine Hierarchie-Navigation."* **Das war falsch, und zwar genau deshalb, weil die
Datei damals nicht wirklich gelesen wurde** — nur ihr Name eingeordnet. Jetzt vollständig gelesen:

`useNestedSortable()` (`addons/web/static/src/core/utils/nested_sortable.js`) ist ein generischer,
wiederverwendbarer OWL-Hook für **Drag & Drop mit echter Verschachtelung**: `nest: true` aktiviert
eine horizontale Zieh-Geste, die ein Element in die nächsttiefere/-höhere Hierarchieebene verschiebt
(Zeilen 236-303, mit ausführlich kommentierten ASCII-Diagrammen der Nest-Logik), `maxLevels`
begrenzt die Tiefe, `isAllowed` erlaubt eigene Validierung pro Zielposition. Tatsächlich im Einsatz
für genau eine kompakte, einrückbare Baumliste mit Drag & Drop: Websites eigener Menü-Editor
("Site → Menüs", `addons/website/static/src/components/dialog/edit_menu.js`, vollständig gelesen,
Zeile 213-234: `useNestedSortable({ ref: this.menuEditor, nest: true, maxLevels: 2, onDrop:
this._moveMenu.bind(this), ... })`).

**Einordnung, jetzt korrekt:** Websites Menü-Editor lädt seinen Baum als Ganzes
(`orm.call("website.menu", "get_tree", ...)`, keine Lazy-Loading-Notwendigkeit, weil ein
Website-Navigationsmenü immer klein ist — wenige bis einige Dutzend Einträge), hält alle
Änderungen nur im Speicher (`this.map`, ein flaches `Map<id, node>` für O(1)-Zugriff beim Ziehen)
und schreibt erst bei "Speichern" alles auf einmal zurück (`orm.call("website.menu", "save", ...)`).
Für `int_filemanager` ist das Laden-Muster damit **nicht** übertragbar (69k Ordner sind nicht "ein
paar Dutzend"), aber `useNestedSortable` selbst ist ein eigenständiger, von der Ladefrage
unabhängiger Baustein: **falls `FolderTree` je eigene Drag&Drop-Umsortierung/-Verschiebung von
Ordnern direkt im Baum bekommen soll** (heute nicht vorhanden — Ordner werden nicht manuell
sortiert, nur Dateien werden per `_makeRecordsDraggable()` aus der Liste auf einen Baumknoten
gezogen), wäre dieser Hook die native, korrekte Grundlage dafür, nicht Eigenbau.

---

## 2. Bestätigung statt Neufund: `router.js`, `pager.js`, `menu_service.js` vollständig geprüft

Alle drei vollständig gelesen, keine neuen nutzbaren Bausteine für `int_filemanager` gefunden,
aber der Vollständigkeit halber festgehalten (entspricht dem Auftrag, nicht nur zu raten):

- **`router.js`** (437 Zeilen): reine URL-/Verlaufs-Zustandsverwaltung. Neben dem bereits genutzten
  `addLockedKey()` gibt es noch `hideKeyFromUrl()` (Zeile 425) — ein Schlüssel bleibt im Zustand,
  erscheint aber nicht in der sichtbaren URL. Aktuell kein erkennbarer Anwendungsfall für
  `int_filemanager` (der Ordnerpfad soll ja gerade sichtbar/teilbar in der URL stehen).
- **`pager.js`** (208 Zeilen): Der native Pager unterstützt bereits direktes Eintippen eines
  Bereichs ("80-100") per Klick auf den Zahlenwert, inklusive Rundlauf (nach der letzten Seite
  wieder zur ersten). Wird von `int_filemanager`s nativer `ListView`/`KanbanView` bereits
  automatisch mitgenutzt (siehe `native_list_view.js`-Kommentar "Pager ... untouched native
  behaviour") — keine neue Erkenntnis, nur Bestätigung.
- **`menu_service.js`** (110 Zeilen, das eigentliche `ir.ui.menu`-Seitenmenü/App-Umschalter): lädt
  seinen gesamten Menübaum **eager, in einem Stück** (`/web/webclient/load_menus`, kein `path`-
  oder `parent_id`-Parameter), gecacht per **eigenem, handgeschriebenem `localStorage`-Muster**
  (Version über `session.registry_hash`, nicht der generische `RPCCache` aus dem vorherigen
  Dokument) — ein **vierter unabhängiger Beleg**, dass Odoo selbst "ganzen Baum laden" nur für
  kleine Hierarchien (hier: Menüpunkte, typischerweise Hunderte, nie Millionen) für vertretbar
  hält. Nebenbefund: Odoo hat also mindestens zwei verschiedene, beide legitime native
  Cache-Muster nebeneinander (generischer `RPCCache`/IndexedDB vs. handgeschriebenes
  `localStorage` hier) — kein Widerspruch zum vorherigen `RPCCache`-Fund, nur ein Beleg, dass ein
  schlankeres, selbstgebautes Caching (wie es `FolderTree` heute mit seinem reinen In-Memory-
  `useState` schon tut) ebenfalls ein anerkanntes natives Muster ist, nicht zwingend minderwertig.

---

## 3. Neuer, orthogonaler Fund: natives Infinite-Scroll-Muster aus Discuss — eine Alternative zum Paging

Andere Richtung als bisher: statt "wie navigiere ich einen Baum", die Frage "wie navigiert Odoo
selbst durch sehr viele flache Datensätze, wenn nicht per Pager?" Fund in `mail`s
Hilfsfunktionen-Datei (`addons/mail/static/src/utils/common/hooks.js`, die zwei relevanten
Funktionen vollständig gelesen, Zeilen 274-319):

- **`useOnBottomScrolled(refName, callback, threshold)`**: einfacher, scroll-Positions-basierter
  Endlos-Nachlade-Hook (Abstand zum unteren Rand < `threshold` → `callback()`).
- **`useVisible(refName, cb, { ready })`**: derselbe Zweck, aber über `IntersectionObserver`
  (Zeilen 293-319) — der modernere, performantere Ansatz (kein `scroll`-Event-Spam), liefert
  reaktiv `isVisible` zurück.

Beide sind das Fundament von Discuss' eigenem "beim Hochscrollen ältere Nachrichten nachladen"
(unendlicher Chatverlauf). **Relevanter Unterschied zu allem bisher Geprüften:** das ist kein
Baum-Navigationsmuster, sondern eine Alternative zum klassischen Pager für **sehr viele flache
Einträge** — direkt einsetzbar für eine mögliche künftige "alle Dateien eines sehr großen Ordners
in einem endlosen Bilder-/Dateiraster statt in Seiten von 80" -Ansicht, falls das je gewünscht
wäre. **Kein neuer Abhängigkeits-Aufwand:** `int_filemanager` bindet `mail` bereits ein (nutzt
`Chatter` aus `@mail/chatter/web_portal/chatter` laut `native_list_view.js`), der Hook wäre also
ohne zusätzliches Modul direkt importierbar.

**Einordnung:** kein Ersatz für den nativen Pager (der bleibt für "wie viele Dateien insgesamt,
gezielt zu Seite X springen" besser geeignet), sondern eine zusätzliche, bisher nicht betrachtete
Option für eine andere Anzeigeart (z. B. eine Galerie-/Kachelansicht mit Endlos-Scroll statt
Seiten) — passt zur in `../../int_filemanager_feature_ideen_2026-09-21.md` (Abschnitt C) ohnehin schon
gewünschten "Galerie-/Rasteransicht für Bilder".

---

## 4. Fazit dieser Runde

Der wichtigste Ertrag ist nicht ein weiterer Baustein, sondern die **Korrektur einer eigenen
vorherigen Verkürzung** (`nested_sortable.js`) — ein direkter Beleg dafür, warum "ganze Dateien
lesen statt Namen einordnen" der richtige Auftrag war. Zusätzlich: eine vierte, unabhängige
Bestätigung des "kleine Hierarchie = eager, große Hierarchie = lazy"-Prinzips (`menu_service.js`),
und ein orthogonaler, bisher nicht betrachteter Baustein für eine ganz andere Anzeigeart
(Endlos-Scroll statt Baum oder Pager). Keiner der Funde ändert die bisherige Kernentscheidung
(`FolderTree` bleibt richtig) — sie erweitern nur das Bild um zwei konkret nutzbare Bausteine
(`useNestedSortable` für künftiges Drag&Drop im Baum, `useVisible`/`useOnBottomScrolled` für eine
künftige Endlos-Ansicht) und eine Selbstkorrektur.
