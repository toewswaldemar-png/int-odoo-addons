# Papierkorb für int_filemanager — Recherche + Konzept

Stand 2026-09-21. Reine Recherche/Konzeptphase, noch nichts umgesetzt oder entschieden.
Auslöser: Nutzerfrage nach dem Löschen einer Datei ("hat Odoo nativ eine Papierkorb-Funktion?"),
danach Auftrag, das nativ Verfügbare zu prüfen und eine saubere, vollständige Umsetzung zu
recherchieren.

## Was Odoo nativ bereits bietet

**Kein systemweiter Papierkorb.** Odoo-Kern (Community, das hier laufende Setup) hat kein
generisches, wiederverwendbares Papierkorb-Konzept.

- **`active`-Feld-Konvention** (verbreitetstes Muster im Kern): ein Boolean-Feld `active`,
  Standardfilter blendet `active=False`-Datensätze aus, über "Archiviert"-Filter wieder
  einblend-/wiederherstellbar. Kein eigener Mixin dafür im Kern - jedes Modell deklariert das
  Feld selbst und verlässt sich auf ir.rule/search-Domain-Defaults. `int_filemanager.file` hat
  dieses Feld aktuell **nicht**.
- **`ir.attachment`** (das eingebaute Datei-Modell, am nächsten am hier verwendeten
  Anwendungsfall): am installierten Odoo-19-Quellcode geprüft (`base/models/ir_attachment.py`) -
  **kein** `active`-Feld, `unlink()` löscht wirklich. Odoo selbst hat also für sein eigenes
  Datei-Modell keinen Papierkorb.
- **Odoo Documents** (die "echte" Dokumentenverwaltungs-App mit einem tatsächlichen
  Papierkorb-Ordner samt Aufbewahrungsfrist): ist **Enterprise-only** und in diesem
  Community-Image nicht vorhanden (`ls .../odoo/addons/` enthält kein `documents`-Modul) - keine
  Vorlage, von der aus dependiert werden könnte, nur als Referenzidee brauchbar.

**Fazit:** nichts, das man direkt einbinden/erben könnte. Ein Papierkorb für `int_filemanager`
wäre eine vollständige Eigenentwicklung, kein "Odoo-Bordmittel aktivieren".

## Leitprinzip: Papierkorb muss zum Kernprinzip "Platte ist Quelle der Wahrheit" passen

Ein reines DB-Flag (`active=False`) auf einem Datensatz, dessen Datei auf der Platte bereits
gelöscht wurde, wäre eine Lüge gegenüber diesem Prinzip (siehe [[project_hm_odoo_filemanager]]) -
die DB würde "existiert im Papierkorb" behaupten, obwohl die Bytes weg sind. Papierkorb muss daher
**physisch** sein: die Datei wird beim "Löschen" nicht gelöscht, sondern auf derselben Platte in
einen Papierkorb-Bereich **verschoben** (`shutil.move`, kein `shutil.rmtree`/`os.remove` mehr für
den normalen Löschvorgang) - identisch zum Prinzip, wie Windows Explorer/die meisten
Dateimanager Papierkorb umsetzen.

## Vorgeschlagener Ort: `.trash/` innerhalb des Wurzelverzeichnisses

Sowohl der Watcher als auch der Vollscan schließen punktpräfixierte Namen bereits aus
(`watcher.py:_is_hidden()`, `models/filemanager_file.py:669/671` - `dirnames[:] = [d for d in
dirnames if not d.startswith(".")]`). Ein `.trash`-Ordner direkt unter der konfigurierten Wurzel
wird von **beiden bestehenden Mechanismen automatisch ignoriert**, ohne dass irgendein
Ausschluss-Code neu geschrieben werden müsste - der Papierkorb-Code selbst pflegt seine eigenen
Datensätze für diesen Unterbaum, Scan/Watcher fassen ihn nie an. Alternative (separate,
konfigurierbare Papierkorb-Wurzel außerhalb des Baums) hätte zusätzlich das Risiko eines
Filesystem-Wechsels beim Verschieben (`shutil.move` über Mount-Grenzen hinweg wird zu
Kopieren+Löschen statt einem billigen `rename()`) - bei den großen Dateien/CIFS-Mounts in diesem
Setup ein echter Nachteil. `.trash` auf derselben Wurzel vermeidet das strukturell.

Namensschema innerhalb `.trash/`: `<id>__<ursprünglicher Name>` (DB-ID als Präfix, nicht der
ursprüngliche Pfad gespiegelt) - vermeidet Kollisionen bei mehrfach gleichnamigen gelöschten
Dateien aus verschiedenen Ordnern, ohne eine eigene Kollisionsauflösung zu brauchen (die ID ist
per Definition eindeutig).

## Nötige Modell-Erweiterungen

Neue Felder auf `int_filemanager.file` (keine neue Tabelle - der Datensatz bleibt derselbe, nur
sein `path` zeigt jetzt auf den Papierkorb-Ort):

- `trashed = fields.Boolean(index=True, default=False)`
- `trashed_at = fields.Datetime()`
- `trashed_by = fields.Many2one("res.users")` (wer hat verschoben - Grundlage für den
  Pro-Nutzer-Papierkorb, siehe "Entschieden" Punkt 1)
- `original_path = fields.Char()` (für Anzeige + Wiederherstellen)

`path`/`folder_path`/`parent_id` werden beim Verschieben in den Papierkorb auf den **neuen**,
tatsächlichen Ort umgeschrieben - konsistent mit dem Prinzip, dass `path` immer den echten
Plattenort widerspiegelt (siehe oben). Normale Listen-/Suchansichten filtern `trashed=False`
implizit (wie das `active`-Muster, aber mit eigenem Feld statt Odoos eingebautem, weil hier
zusätzliche Metadaten - wann, woher - gebraucht werden, die das reine `active`-Feld nicht liefert).

## Der kritische Teil: Race gegen den Watcher (Lehre aus dieser Session)

Genau diese Session hat zwei Bugs live gefunden und behoben, bei denen Watcher und ein expliziter
Controller-Aufruf denselben `int_filemanager.file`-Datensatz gleichzeitig anfassen (siehe
Commits `fdb953b`, `4d63831` - `pg_advisory_xact_lock` in `index_upsert()`/`index_remove_tree()`).
Ein Papierkorb hat **dieselbe Gefahrenklasse, verschärft**:

`shutil.move(original_pfad, .trash/<id>__name)` feuert im Watcher ein `MOVED_FROM` auf dem
ursprünglichen, beobachteten Pfad - aber **kein** `MOVED_TO`, weil `.trash` nicht beobachtet wird
(dot-Präfix-Ausschluss, siehe oben). Laut der bestehenden Batch-Logik
(`watcher.py:_process_batch()`, Kommentar "Anything left here was moved outside the watched tree
entirely... triggers `_remove(old_abs)`") behandelt der Watcher das wie ein **echtes Löschen** des
Original-Pfads und versucht, den Datensatz zu **unlinken** - während der Papierkorb-Controller
im selben Moment versucht, genau diesen Datensatz auf den neuen Pfad **umzuschreiben** (nicht zu
löschen). Ohne Koordination kann der Watcher den Datensatz löschen, kurz bevor/während der
Papierkorb-Code ihn eigentlich nur umbenennen wollte - der Papierkorb-Zweck (Wiederherstellbarkeit)
wäre dann für genau diesen Fall verfehlt, obwohl die Bytes safe auf der Platte liegen.

Eine saubere Umsetzung braucht daher von Anfang an:

1. Denselben `pg_advisory_xact_lock` auf den **ursprünglichen** Pfad, **bevor** die
   Papierkorb-Route den Datensatz umschreibt - exakt dasselbe Muster wie in `index_upsert()`/
   `index_remove_tree()` schon etabliert, nicht neu erfunden.
2. Eine eigene `index_trash_tree()`-Funktion (kein Wiederverwenden von `index_move_tree()` 1:1,
   weil zusätzlich `trashed`/`trashed_at`/`original_path` gesetzt werden müssen), die - falls der
   Datensatz durch das oben beschriebene Rennen doch schon vom Watcher gelöscht wurde, bevor der
   Lock griff - den Datensatz aus der (bereits verschobenen!) Datei auf der Platte **neu anlegt**,
   statt zu scheitern. Gleiches Selbstheilungsprinzip wie die `UniqueViolation`-Robustheit, die
   diese Session bei `index_upsert()` schon eingeführt hat.
3. Symmetrisch für "Wiederherstellen" (`index_restore_tree()`): Datei zurück an `original_path`
   verschieben, Datensatz zurückschreiben - mit derselben Lock-Disziplin auf dem **Ziel**-Pfad
   (Kollisionsschutz: was, wenn der Zielort inzwischen von einer neuen Datei belegt ist? Siehe
   offene Frage unten).

## Entschieden (2026-09-21)

1. **Zugriffsmodell: Papierkorb pro Nutzer, nicht global admin-only** (Korrektur einer ersten,
   zu engen Entscheidung - Referenz war cloudreves Verhalten: Papierkorb steht dort für jeden
   Nutzer unten im Ordnerbaum, jeder verwaltet seinen eigenen). Wer eine Datei löscht, sieht/
   verwaltet sie danach in seinem **eigenen** Papierkorb (wiederherstellen + endgültig löschen
   selbst möglich); Admins sehen zusätzlich den Papierkorb **aller** Nutzer.

   Umgesetzt über `trashed_by` (siehe Modell-Erweiterungen oben) statt über eine
   Pfad-Präfix-Prüfung gegen Schutzordner - dadurch **kein** Ausbau der (schon komplexen)
   `acl_rules.py`-Regelgenerierung auf `original_path` nötig. Sicherheitsbegründung: ein Nutzer
   kann ohnehin nur etwas löschen (und landet damit automatisch in seinem eigenen Papierkorb),
   wenn er zum Löschzeitpunkt bereits Löschrecht auf den Original-Pfad hatte (bestehender
   `authz.require(rel_path, "unlink")`-Check, unverändert) - der Papierkorb zeigt also nie mehr,
   als der Nutzer ohnehin schon löschen durfte. Keine neue Rechteausweitung.

   Serverseitige Durchsetzung (nicht nur eine UI-Filterung - siehe Nachtrag unten) über eine
   eigene, statische `ir.rule` auf `int_filemanager.file` (neben, nicht als Ausbau der
   bestehenden Schutzordner-Regeln in `security.xml`):
   ```
   domain_force = ['|', ('trashed','=',False),
                    '|', ('trashed_by','=',user.id),
                    (1,'=',1) if user.has_group('int_filemanager.group_filemanager_admin') else (0,'=',1)]
   ```

   **Nachtrag (Nutzerfrage "was, wenn `.trash` selbst im Ordnerbaum sichtbar ist?" hat eine echte
   Lücke im ersten Entwurf aufgedeckt, weiterhin gültig):**
   - Der `.trash`-Container-Ordner braucht einen eigenen `int_filemanager.file`-Eintrag (damit
     `parent_id` für seine Kinder auflösbar ist) - dieser Eintrag bekommt beim Anlegen selbst
     ebenfalls `trashed=True`, sonst bliebe ein leerer, aber sichtbarer ".trash"-Ordner im
     normalen Baum stehen, obwohl seine Kinder schon gefiltert wären.
   - Eine reine Domain-Filterung auf der Haupt-Action (`("trashed","=",False)`) ist nur eine
     UI-Höflichkeit, **keine echte Zugriffskontrolle** - ein direkter ORM-Aufruf mit
     `trashed=True` in der Domain würde sie umgehen. Die obige `ir.rule` ist deshalb der
     eigentliche Schutz, die Domain auf der Action nur eine zusätzliche, redundante Höflichkeit.
2. **Aufbewahrungsfrist:** 30 Tage Default, als echtes Einstellungsfeld für Admins (nicht nur
   `ir.config_parameter` im Hintergrund) - gleiches Muster wie das bestehende
   Stammverzeichnis-Feld in `res_config_settings.py`/`res_config_settings_views.xml`, auf
   derselben Settings-Seite, änderbar ohne Entwicklermodus.
3. **Kollision beim Wiederherstellen:** hart blockieren mit klarer Fehlermeldung, kein stilles
   Umbenennen - dieselbe Linie wie der bestehende `move()`-Controller
   (`if os.path.exists(new_abs): raise UserError(...)`). Betrifft beides: Zielpfad ist inzwischen
   durch einen neuen Eintrag belegt, oder der ursprüngliche Elternordner existiert selbst nicht
   mehr - in beiden Fällen Fehlermeldung statt automatischer Ausweichlogik, Nutzer löst manuell auf.

## Bewusst außerhalb des Scopes

**Löschungen direkt über Explorer/SMB (auch Shift-Löschen)** landen NICHT im App-Papierkorb -
grundsätzliche Grenze, kein Implementierungsdetail: der Papierkorb kann nur Löschungen abfangen,
die durch die App laufen (`/int_filemanager/delete` verschiebt statt zu löschen). Bei einer
direkten Explorer-Löschung sind die Bytes bereits weg, bevor der Watcher überhaupt etwas
mitbekommt - nichts mehr da, das verschoben werden könnte; die App räumt nur noch den
Index-Eintrag auf. Ein serverseitiger Schutz dagegen (z. B. Windows Shadow Copies auf `HM-FL01`,
falls das ein Windows Server ist, oder Sambas Recycle-VFS-Modul) wäre ein komplett separates,
von Odoo unabhängiges Thema - auf Nutzerentscheid explizit nicht weiterverfolgt.

## Noch offen

4. **"Direkt endgültig löschen" (Shift-Löschen, wie in Windows Explorer):** normales Löschen
   verschiebt in den Papierkorb, eine zweite Aktion löscht sofort und endgültig daran vorbei -
   für Fälle, in denen bewusst nichts aufgehoben werden soll. Phase 2, nicht zwingend Teil der
   ersten Umsetzung.
5. **Speicherverbrauch.** Papierkorb-Inhalte belegen bis zur endgültigen Löschung weiter echten
   Plattenplatz - bei den bereits historisch klammen CIFS-Freigaben (siehe
   [[project_hm_odoo_filemanager_rshared_leak]]) operativ zu bedenken, kein Blocker, nur
   Beobachtungspunkt.

## UI-Umsetzung (verifiziert gegen den bestehenden Code, nicht nur angenommen)

**Hauptansicht (Explorer) bleibt unverändert**, bekommt nur einen zusätzlichen Domain-Zweig:
`native_search_model.js:_getDomain()` UNDet die Ordner-Navigation immer über
`super._getDomain(params)` (Odoos Standard-Domain-Zusammenführung, inkl. der statischen
Action-Domain) mit der eigenen `folderDomain` - ein zusätzliches `("trashed", "=", False)` auf
der bestehenden Action (`filemanager_file_list_view.xml`) ist sicher kombinierbar und bricht die
Unterordner-Navigation nicht, anders als eine pfadbezogene Domain (siehe bestehender Kommentar
dort zu `domain: []`). Kein JS-Code an der Hauptansicht selbst ändert sich.

**Papierkorb-Ansicht ist eine eigene, einfache Seite**, kein Ausbau der nativen
Explorer-Komponente - gleiches Muster wie die bestehende "Status"-Verwaltung
(`filemanager_status_views.xml`), jetzt für ALLE Nutzer erreichbar (nicht mehr nur unter
"Konfiguration"):

- Eigene `ir.actions.act_window` (`action_filemanager_trash`), feste Domain
  `[("trashed", "=", True)]` (die `ir.rule` von oben filtert serverseitig automatisch auf "eigene
  + ggf. alle bei Admin" - die Action selbst braucht keine Nutzer-Unterscheidung). **Standard**-
  Odoo-Listenansicht (kein `js_class`) - Name, ursprünglicher Pfad, gelöscht am, Größe.
- "Wiederherstellen": `<button name="action_restore" type="object">`, exakt dasselbe Muster wie
  die bestehenden `action_generate_share_token`/`action_scan_now`-Buttons.
- "Endgültig löschen": Odoos **eigener nativer Lösch-Button** der Liste, kein neuer Mechanismus -
  ein `unlink()`-Override entfernt bei `trashed=True`-Datensätzen zusätzlich die Bytes aus
  `.trash/`, analog zum bestehenden `write()`-Override fürs Umbenennen.

**Einstiegspunkt: fester Eintrag unten im Ordnerbaum** (Nutzerwunsch, cloudreve-Vorbild), nicht
nur ein Menüpunkt. Verifiziert gegen die tatsächliche Baum-/Layout-Struktur:

- `.o_int_filemanager_tree_sidebar` (`folder_tree_layout.scss`) ist heute ein einziger
  scrollbarer Block (`overflow-y: auto`) - `<FolderTree/>` füllt ihn komplett, ein einfach
  angehängter Eintrag würde mitscrollen. Sauberer, nativer Weg (dieselbe Flex-Panel-Technik wie
  z. B. Odoos Discuss-Sidebar): `FolderTree`s eigenes Root-Template wird eine Flex-Spalte mit
  zwei Teilen - oben der Baum (`flex: 1 1 auto; min-height: 0; overflow-y: auto`, die Werte
  wandern von der Sidebar eine Ebene tiefer), unten ein fester Papierkorb-Eintrag
  (`flex: 0 0 auto`, kein Overflow, bleibt immer sichtbar). `.o_int_filemanager_tree_sidebar`
  selbst verliert sein eigenes `overflow-y: auto`, wird nur noch zum reinen Rahmen.
- Der Eintrag gehört ins Template von `FolderTree` selbst, nicht als zusätzliches Markup an den
  zwei Einbettungsstellen (`native_list_view.xml` Desktop-Sidebar UND Mobil-Bottom-Sheet nutzen
  dieselbe Komponente) - sonst doppelte Pflege.
- Klick-Verhalten: kein neuer Navigationsweg - `filemanager_controller_mixin.js` ruft an zwei
  Stellen bereits `this.actionService.doAction("int_filemanager.action_xxx", ...)` für ähnliche
  Fälle (z. B. den Freigabe-Dialog). Klick auf den Papierkorb-Eintrag macht dasselbe:
  `doAction("int_filemanager.action_filemanager_trash")`.

**Nebenbefund:** alles, was innerhalb von `.trash/` passiert (also "Endgültig löschen"), hat gar
kein Watcher-Rennen, weil der Ordner bewusst nicht beobachtet wird - der
`pg_advisory_xact_lock` ist nur für die zwei Grenzübertritte nötig (rein beim Löschen, raus beim
Wiederherstellen), nicht für die reine Papierkorb-Verwaltung selbst.

## Vorgeschlagener Umfang der ersten Umsetzung (falls beauftragt)

Ein zusammenhängendes Stück, kein über mehrere Bausteine verteiltes Vorgehen (siehe
[[feedback_konzeptdocs_konsolidieren]]):

- Felder (`trashed`, `trashed_at`, `trashed_by`, `original_path`) + `.trash/`-Ablage +
  `index_trash_tree()`/`index_restore_tree()` mit Lock-Disziplin.
- "Löschen" in Controller/UI wird zu "In den Papierkorb verschieben" (Route bleibt
  `/int_filemanager/delete`, Verhalten ändert sich; Ordner-Löschen: `shutil.move()` des ganzen
  Unterbaums als ein Schritt statt der aktuellen `shutil.rmtree()`+rekursiver DB-Löschung).
- `ir.rule` für Pro-Nutzer-Sichtbarkeit (siehe "Entschieden" Punkt 1) + `unlink()`-Override für
  "Endgültig löschen".
- Eigene Papierkorb-Ansicht (Liste: Name, ursprünglicher Pfad, gelöscht am, Größe) mit
  "Wiederherstellen"/"Endgültig löschen"-Aktionen, für alle Nutzer erreichbar.
- Fester Papierkorb-Eintrag unten im Ordnerbaum (`FolderTree`-Template + Flex-Layout-Anpassung),
  Klick öffnet die Papierkorb-Ansicht per `doAction`.
- Retention-Cron für endgültige Löschung, Frist als Settings-Feld (Default 30 Tage).

**Nächster Schritt:** Kernfragen (1-3) sind geklärt, Umsetzung kann beauftragt werden. Punkt 4
(Shift-Löschen) bleibt offen und kann später nachgezogen werden. Explorer/SMB-seitiger Schutz
(siehe "Bewusst außerhalb des Scopes") ist kein Teil dieses Features.
