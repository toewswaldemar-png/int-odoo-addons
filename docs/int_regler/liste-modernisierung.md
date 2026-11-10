# int_regler: Liste "Process values" modernisieren

Stand: 2026-11-10. **Paket A umgesetzt** (Widget, Ansicht, SCSS, README; Prüfskripte unter `tools/int_regler` laufen: `npm test`). **Nicht im Browser gesehen:** Zeilenhöhe (`--o-int-regler-clamp-height: 1.5rem`), Farben von `btn-secondary active` und die Spaltenbreiten sind aus dem Code gewählt, nicht gemessen. **2026-11-10 später: Zahlenfeld durch Popover ersetzt** (auf Wunsch, nach dem Ansehen der Variante "Feld in der Zeile"): analoge Zeilen zeigen `[Auto | Zahl ✎]`, die Zahl öffnet ein Popover (`usePopover`, Dateien `regler_clamp_popover.js/.xml`, `regler_numbers.js`) mit Eingabe, Schritttasten, Clamp/Cancel. Die Abschnitte zum Zahlenfeld unten beschreiben deshalb nur noch die Eingabe im Popover. Paket B offen.
Befunde (2026-11-09) aus Screenshot + Code.
Grundsatz: so nah wie möglich an Odoo 19 (Core-Muster, Bootstrap-Klassen, Standard-Listenattribute).

Betroffene Dateien:
- `int_regler/views/int_regler_device_views.xml` (Liste `int_regler_parameter_view_list`, Suche, Action)
- `int_regler/static/src/regler_clamp_field.js` / `.xml` (Widget `int_regler.clamp`)
- `int_regler/static/src/regler.scss`
- `int_regler/static/src/regler_parameters.js` (Listen-Controller)

## Befunde

1. **Hierarchie umgekehrt.** 20 von 23 Zeilen zeigen ein kräftig violettes "Auto" (`btn-primary`) = Normalzustand. Die Ausnahme (geklemmt) ist nur ein kleines gelbes Segment (`btn-warning`), "Auto" wird dann `btn-outline-secondary`.
2. **"ok"-Badge in jeder Zeile** (Feld `status`, `widget="badge"`). Rauschen; wichtig ist nur der Fehlerfall.
3. **Drei Spalten vor der Zeilennummer:** Checkbox (ohne Funktion), Griff (`sequence`), Stern (`is_favorite`).
4. **Zeilenhöhen ungleich.** Analoge Zeilen (Zahlenfeld) sind höher als digitale. In Zeile 0005 sieht das Feld wie reiner Text aus; vermutlich deaktiviert (`canUse` false) und gleiche Farbe wie die Hover-Zeile. Vermutung, nicht geprüft.
5. **Name und Clamp weit auseinander.** `name` nimmt den Rest der Breite, das Bedienelement sitzt rechts außen.
6. **Wert und Eingabefeld doppelt.** Analog: Spalte "Value" zeigt "27.4°C" (Text vom Regler, Punkt), das Feld "27,4" (Browser-Lokale, Komma). Im Zustand Auto sieht das Feld wie ein Sollwert aus.
7. **Ohne Recht nur graue Buttons** (`disabled`); sehen bedienbar aus, sind es aber nicht.
8. Modul hat keinen `i18n/`-Ordner: Oberfläche komplett englisch.

## Paket A: Optik der Liste (klein, ohne Server)

- "Auto" ruhig (aktiv = `btn-light`/dezent). Nur das geklemmte Segment `btn-warning`, dazu Schloss-Symbol und `decoration-warning` auf Name oder Wert (Listen-Dekorationen sind Core: `list_renderer.js` wertet `decoration-*` je Zeile und je Feld aus).
- `status` (Lesestatus: ok / unread / no_value / out_of_range / error, sagt nichts über den Prozess) **kommt aus der Liste** bzw. wird `optional="hide"`. Entscheidung 2026-11-09: diese Info gehört in die Administration (siehe Paket B). Filter "Problems" und Gruppierung nach Status bleiben in der Suche.
- Spaltenreihenfolge: Zeile, Name, Wert, Clamp, Status. Feste Breite für `name`.
- Einheitliche Höhe für Buttons und Zahlenfeld (SCSS).
- **Zahlenfeld nach Core-Vorbild** (`web.FloatField`, geprüft in `addons/web/static/src/views/fields/float/`): Der Spinner des Browsers (`type="number"`, Pfeile ändern den Wert bei jedem Klick) fällt weg. Stattdessen `<input type="text" inputmode="decimal" class="o_input" t-ref="numpadDecimal">` (Unterlinie statt Kasten), `useNumpadDecimal()` (Dezimaltaste des Ziffernblocks setzt das Dezimalzeichen der Sprache), `parseFloat`/`formatFloat` aus `@web/views/fields/parsers` (Komma und Punkt, Anzeige im Format des Benutzers; beseitigt die Mischung "27.4°C" / "27,4"). Verhalten bleibt: Enter oder Verlassen klemmt, Escape verwirft. Verworfen: Klick-zum-Bearbeiten (ein Klick mehr am Fahrzeug) und Plus/Minus-Tasten (jeder Schritt wäre ein Klemmauftrag).
- Im Zustand Auto: Zahlenfeld zeigt den Istwert nur gedämpft (Platzhalter), erst bei Klemmung als Vorgabe (`border-warning`).
- Ohne Recht: "readonly" wie bei Odoo-Feldern, also Text (Auto / geklemmt 1) statt grauer Buttons.
- Kleinigkeiten: Escape verwirft die Eingabe (`typed = null`), beim Senden Spinner (`fa-spinner fa-spin`) im gedrückten Segment.

## Paket B: Bedienung (braucht Serverarbeit)

- **Checkbox bekommt Zweck:** `<header>`-Button "Release clamps" für markierte Zeilen (Standardmuster von Odoo-Listen, z. B. `account.move`). Braucht eine Server-Methode am Modell, die je Zeile einen Auftrag über `int.regler.command` anlegt (Recht Operator, gleicher Weg wie ein Klick).
- **Lesestatus in der Administration** (Menü *Controllers*, Formular `int.regler.device`): Statistik-Button `oe_stat_button` "Rows with problems" (Anzahl Zeilen mit `status != 'ok'`), Klick öffnet *Process values* gefiltert auf "Problems" und diesen Regler (Core-Muster: Statistik-Button mit Action und Kontext). Optional ein Zähler je Status im Formular. Die Liste bleibt für Bediener frei von Diagnose.
- **Favoriten als Standardfilter** über `context="{'search_default_favorites': 1}"` an `int_regler_parameter_action`. Vorsicht: solange kein Stern gesetzt ist, ist die Liste leer.
- **`i18n/de.po`** anlegen (Odoo-nativ). Begriff im README ist "Klemmen".

## Später, nur bei Bedarf

- Digitale Werte (0/1) als farbiger Punkt statt Ziffer (kleines eigenes Widget oder `badge` mit Dekoration auf `text`).
- Kanban-Ansicht mit größeren Touch-Flächen, falls am Fahrzeug mit Tablet bedient wird. Die jetzigen Buttons (`--btn-padding-y: 0`) sind dafür zu klein.

## Was der Core nicht hat

Kein Segment-Widget für Listen. `badge_selection` ist für Formulare (in der Liste nur Text). `boolean_toggle` ist ein Schalter mit zwei Zuständen, hier gibt es drei (Auto / 0 / 1). Daher bleibt `int_regler.clamp` als eigenes Widget.

## Empfehlung

Mit Paket A beginnen (nur Widget, XML-Ansicht, SCSS; Server und Dienst bleiben unberührt). Paket B danach.

## Offen

- `stale` (Wert veraltet, z. B. nach Verbindungsabbruch) ist ein anderer Fall als der Lesestatus: er betrifft die Bediener, weil alte Werte irreführen. Das Feld ist im Modell vorhanden, die Liste zeigt es nicht; ob die Status-Spalte bei Verbindungsverlust trotzdem "ok" zeigt, ist nur aus Feldnamen und Tests gelesen, nicht geprüft. Klären, ob und wie die Liste veraltete Werte kenntlich macht (z. B. Wert grau) oder ob der Hinweis der Monitor-Seite ("report 45 s old") reicht.
- Zeile 0005 (Feld wie Text): Ursache klären, deaktiviert (`busy`/Recht) oder Hover-Farbe.
- Nach Umsetzung im Browser prüfen: Zeilenhöhe, Dunkelmodus, Spaltenbreiten bei schmalem Fenster.
