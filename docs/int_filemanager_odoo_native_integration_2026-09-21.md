# int_filemanager: tiefere Verzahnung mit Odoo-Bordmitteln — Analyse

Stand 2026-09-21. Separates Dokument, ergänzt
[int_filemanager_feature_ideen_2026-09-21.md](int_filemanager_feature_ideen_2026-09-21.md)
(dort: Features allgemein) — hier ausschließlich die Frage: **wo lässt sich das Modul noch enger
an echte Odoo-Bordmittel anschließen statt eigene Mechanik zu pflegen**, betrachtet aus dem
weiteren Kontext des gesamten Repos (`int-odoo-addons`, nicht nur `int_filemanager` isoliert) und
der Odoo-19-Plattform insgesamt. Reine Analyse, nichts umgesetzt oder beauftragt.

**Methodik/Grenzen dieser Session:** vollständige Codedurchsicht (`int_filemanager/` +
Geschwister-Module im selben Repo) plus gezielte Web-Recherche zu Odoo-19-Bordmitteln
(Quellen am Ende jedes Abschnitts, wo relevant). **Keine Live-Verifikation gegen HM-SRV/Tower in
dieser Session** — anders als der sonst in diesem Repo etablierte Standard ("live am
Quellcode/an der Instanz geprüft, nicht angenommen", siehe `int_filemanager_native_ui.md`).
Jede Aussage, die von der tatsächlichen Odoo-Edition (Community vs. Enterprise) oder vom
Lizenzstand abhängt, ist unten explizit als **vor Umsetzung zu verifizieren** markiert — genau
das Muster, das bei Baustein 5 der PaperOffice-Recherche (Odoo Sign) bereits einmal nötig war.

---

## 0. Bestandsaufnahme: was heute schon "nativ" ist

Bevor neue Anschlusspunkte gesucht werden, zur Einordnung, wie viel davon bereits genutzt wird
(sonst droht, Bekanntes als "neu" vorzuschlagen):

| Odoo-Bordmittel | Wie genutzt |
|---|---|
| `mail.thread`/`mail.activity.mixin` | Chatter, Aktivitäten, Follower auf `int_filemanager.file` (Baustein 2) |
| `bus.bus` | Live-Refresh-Signal bei Indexänderung — **aber nur in der alten UI verdrahtet, siehe Punkt 1** |
| `ir.rule` + `ir.model.access` | Komplettes ACL-System (Schutzordner, Portal-Zweig) |
| `fields.Reference` + eigener Mixin | Verknüpfung mit beliebigen Datensätzen (bisher nur `res.partner` verdrahtet) |
| `ir.attachment` (synthetisiert) | Brücke zu ONLYOFFICE (`open_editor`), Versions-Dedup |
| `state_selection`/`badge`-Widget | Ampel-Freigabestatus |
| Natives `ListView`/`SearchPanel`/`ActionMenus` | Ordnerbaum + Dateiliste (Migration laufend) |
| `CodeEditor`, `FileViewer`, `http.Stream` | Text-Editor, Vorschau, Video-Streaming |
| `ir.cron`, `pg_advisory_lock` | Scan/Extraktion/Versionierung |
| `ir.config_parameter` + `res.config.settings` | Einstellungen |
| `portal.` (Templates, nicht `portal.mixin`) | Externe Freigabe-Seite |

Das Modul ist also schon deutlich "nativer" als ein typisches Custom-Modul. Die folgenden Punkte
sind die verbleibenden, noch nicht genutzten oder nur teilweise genutzten Anschlussstellen.

---

## 1. Konkrete Lücke, kein Vorschlag: Live-Refresh fehlt in der neuen UI

**Live am Code dieser Session gefunden, nicht nur vermutet:** `index_utils.py::_notify_change()`
sendet bei jeder Indexänderung über `env["bus.bus"]._sendone(BUS_CHANNEL, ...)` ein
Live-Signal. `filemanager_controller_mixin.js` (die **alte** UI) abonniert das
(`busService.subscribe("int_filemanager.change", ...)`) und lädt die Liste automatisch neu —
das ist der Mechanismus, der z.B. externe CIFS-Änderungen (nach dem Reconciliation-Scan) oder
Änderungen eines Kollegen am selben Ordner in Echtzeit im Browser sichtbar macht, ganz ohne
manuellen Refresh.

`native_list_view.js` (die **neue**, aktiv weiterentwickelte UI) hat **keine** entsprechende
`busService`-Subscription — geprüft per Grep, kein Treffer. Solange beide UIs parallel existieren
ist das nur ein Komfortverlust in der neuen UI. Laut
`int_filemanager_native_ui.md` ("Empfohlene Reihenfolge", Schritt 3) ist aber geplant, die alte
UI + den `/int_filemanager/list`-Endpunkt **zu löschen, sobald Funktionsparität erreicht ist** —
und genau diese eine Parität fehlt noch. Kein neuer Vorschlag, sondern eine konkrete
Nachtrag-Position für die ohnehin laufende Migration: `busService.subscribe(...)` +
`model.load()` (ohne Domain-Argument, analog dem bestehenden `reload()`-Muster) in
`native_list_view.js` nachziehen, **bevor** der alte Pfad gelöscht wird — sonst wäre die
Löschung eine stille Funktionsregression.

---

## 2. `ir.attachment`s generische `res_model`/`res_id`-Verknüpfung — Alternative zur eigenen Mixin-Lösung

**Heutiger Zustand:** `res_reference` (`fields.Reference`) + `IntFilemanagerLinkableMixin` +
Smart-Button — funktioniert, aber jedes neue Zielmodell braucht laut eigener Doku "einen reinen
Vererbungs-Einzeiler" (Code-Änderung, Modul-Update). Odoo selbst löst genau dieses Problem
("beliebiger Datensatz kann Dateien haben") **bereits universell** über `ir.attachment.res_model`
+ `ir.attachment.res_id` — das ist exakt der Mechanismus, der die Büroklammer/den
Anhänge-Zähler im Chatter **jedes** Modells ohne jede Modell-spezifische Code-Zeile zum Laufen
bringt. Es gibt im Modul bereits einen Präzedenzfall dafür, dass Dateien vom Plattensystem in
eine `ir.attachment`-Repräsentation überführt werden können, wenn ein nativer Konsument das
braucht: `open_editor()` synthetisiert für ONLYOFFICE genau das.

**Denkbare Weiterentwicklung (großer, eigenständiger Umbau — nicht nebenbei):** statt
`res_reference` (Ziel → eine Datei) könnte pro Verknüpfung ein "Schatten"-`ir.attachment`
angelegt werden, das `res_model`/`res_id` auf den Zieldatensatz UND einen Verweis zurück auf
`int_filemanager.file` trägt. Ergebnis: die Datei erscheint automatisch im nativen
Anhänge-Widget **jedes** Modells (Rechnung, Projektaufgabe, Reparaturauftrag, Mitarbeiter, CRM-
Lead — ganz ohne Mixin-Vererbung pro Modell), inklusive nativer Anhänge-Vorschau im Chatter.

**Bewusst nicht als Empfehlung, nur als Option festgehalten:** das ist ein Architekturwechsel,
kein Feature-Zusatz. Trade-offs, die vor einer Entscheidung geklärt werden müssten: doppelte
Buchführung (Sync bei Verschieben/Umbenennen/Löschen der Originaldatei nötig, analog zu den
bereits bekannten Nebenläufigkeitsfallen aus der Versionierung), `ir.attachment` hat eigene,
von `acl_rules.py` unabhängige Zugriffsregeln (Sicherheitsimplikation, bräuchte denselben
Review-Aufwand wie die ursprüngliche ACL-Einführung), und der aktuelle Ansatz (`res_reference`)
funktioniert bereits produktiv und getestet. **Realistischer Zwischenschritt statt Vollumbau:**
den Mixin einfach auf weitere konkrete Modelle ausweiten (siehe Punkt 8) — bringt den
Haupt-Nutzen (Verknüpfung ohne Custom-UI) ohne den Architekturwechsel.

---

## 3. Automatisierung: `base_automation`/Studio sind vermutlich Enterprise-only — vor Ort verifizieren

Recherche ergab: die "Automatisierte Aktionen"/"Automation Rules" (`base_automation`) sind in
aktuellen Odoo-Versionen an **Studio gekoppelt, und Studio ist ein Enterprise-Feature** — in der
Community-Edition fehlt das Menü typischerweise komplett. Das deckt sich mit einem Muster, das
in diesem Modul schon mehrfach beobachtet wurde: statt der nativen **Approvals**-App (ebenfalls
Enterprise-only, per Recherche bestätigt) wurde ein eigenes `int_filemanager.status`-Modell
gebaut; statt der nativen **Documents**-App (ebenfalls Enterprise, siehe Punkt 11) wurde
`int_filemanager` komplett neu gebaut. Das spricht stark dafür, dass HM-SRV/Tower auf Community
laufen — **aber nicht mit Sicherheit**, ohne das explizit zu prüfen (`Einstellungen → Technisch →
Automatisierung → Automatisierte Aktionen` — fehlt das Menü/ist es leer trotz Entwicklermodus, ist
es bestätigt Enterprise-gated).

**Falls nicht verfügbar** (wahrscheinlich): der native, Community-sichere Ersatz sind
`ir.actions.server` (Server-Aktionen) — die gibt es in Community, sie lassen sich per `ir.cron`
zeitgesteuert **oder** als Button/Menüpunkt auslösen, **ohne** dass jede Regel neuer Python-Code
sein muss (der Server-Aktions-Editor kann einfache Python-Snippets im UI halten). Genau dieses
Muster nutzt das Modul bereits an einer Stelle (`res_config_settings.action_scan_now()` ruft
einen Cron-Entry-Point manuell auf). Eine konkrete Anwendung: die in
`int_filemanager_feature_ideen_2026-09-21.md` (Punkt I1) skizzierten Ordner-Regeln
("neue Datei unter Pfad X → Tag Y") ließen sich als **Daten** (eine kleine
`int_filemanager.folder_rule`-Tabelle, editierbar ohne Code) mit einer **festen**, einmalig
geschriebenen Auswertungslogik im bestehenden Scan-/Watcher-Cron umsetzen — das ist ohnehin der
robustere Weg (keine Abhängigkeit von einer möglicherweise fehlenden Enterprise-App), nicht nur
ein Ausweichmanöver.

**Quellen:** [Automation rules — Odoo 19.0 documentation](https://www.odoo.com/documentation/19.0/applications/studio/automated_actions.html), [Does Odoo Studio work on custom modules?](https://www.odoo.com/forum/help-1/does-odoo-studio-work-on-custom-modules-if-i-self-host-odoo-enterprise-will-it-work-the-same-way-for-my-modules-that-it-does-for-odoo-modules-141775), [Approval Management in Odoo: Options in Odoo Enterprise and OCA](https://www.dixmit.com/en/blog/our-blog-1/approvals-in-odoo-31)

---

## 4. `Knowledge`-App für Endnutzer-Dokumentation — eine auffällige Lücke in die andere Richtung

Auffällig beim Durchsehen aller `docs/int_filemanager_*.md`: es existiert eine **außerordentlich
gründliche Entwickler-/Betriebsdokumentation** (dieses Repo), aber **keine sichtbare
Endnutzer-Hilfe** innerhalb von Odoo selbst ("Wie lege ich eine Freigabe an?", "Was bedeutet die
Ampel-Farbe?", "Wie öffne ich eine Datei lokal in Word?"). Odoos `Knowledge`-App (nativ, seit
mehreren Versionen Teil von **Community und Enterprise** — Enterprise ergänzt kollaboratives
Editieren und eingebettete Live-Ansichten, die Grundfunktion "Artikel/Wiki" ist aber
Community-verfügbar) wäre der naheliegende Ort dafür: ein paar Artikel, aus dem Filemanager-Menü
verlinkt (oder als Hilfe-Icon in der Toolbar) oder — für Enterprise, falls vorhanden — sogar mit
einer eingebetteten Live-Ansicht (z.B. "aktuell offene Freigaben"). Geringer Aufwand (reine
Content-Arbeit, kein Code), hoher Nutzen für die eigentliche Zielgruppe (Kollegen, nicht
Entwickler) — bisher nirgends im Repo als Thema aufgetaucht.

**Quelle:** [Knowledge — Odoo 19.0 documentation](https://www.odoo.com/documentation/19.0/applications/productivity/knowledge.html)

---

## 5. Pivot/Graph-Views — sicher Community, unabhängig von der "Dashboards"-App

Zur Einordnung von Punkt D1–D3 im Feature-Ideenkatalog: `<pivot>`/`<graph>`-Viewtypen sind
Kernbestandteil von `web` selbst (seit jeher Community), komplett unabhängig von der separaten,
Enterprise-lastigen "Dashboards"-App (die im Kern nur vorgefertigte Spreadsheet-Kacheln aus
genau solchen Pivot/Graph-Quellen zusammenstellt). Eine `<pivot>`-View + Menüpunkt auf
`int_filemanager.file` ist damit **mit hoher Sicherheit** ohne Lizenzfrage nutzbar — die einzige
in diesem Dokument aufgeführte Idee, die praktisch risikofrei als "nativ, garantiert verfügbar"
gilt, im Gegensatz zu den Enterprise-unsicheren Punkten 3/11.

**Quelle:** [Dashboards — Odoo 19.0 documentation](https://www.odoo.com/documentation/19.0/applications/productivity/dashboards.html), [Spreadsheet Dashboard Oca (OCA-Alternative)](https://odoo-community.org/shop/spreadsheet-dashboard-oca-715222)

---

## 6. `calendar.event` für Fristen aus erkannten Werten

Ergänzt Punkt I4 im Feature-Ideenkatalog (dort: `mail.activity`): `calendar.event` ist
Community-nativ und unterstützt — wie `ir.attachment` — eine generische `res_model`/`res_id`-
Verknüpfung zurück auf den Ursprungsdatensatz. Für ein per Extraktionsmuster erkanntes
Ablaufdatum (Vertragsende, Garantie, Frist) wäre ein **echter Kalendereintrag** (statt nur einer
Aktivität, die nur im Odoo-Backend sichtbar ist) sinnvoll, weil er automatisch in die private
Kalenderansicht des zuständigen Mitarbeiters einsortiert wird und — falls konfiguriert — auch per
CalDAV/Sync auf dessen Handy landet. Reine Zusatzoption neben der Aktivität, kein Ersatz.

---

## 7. Discuss-Kanäle statt reiner Follower-Benachrichtigung

`mail.thread`-Follower (Baustein 2) benachrichtigen einzeln Abonnierte. Für ein ganzes Team, das
gemeinsam einen Eingangsordner beobachtet (z.B. "neue Rechnung im Scan-Eingang"), wäre ein
`mail.channel`-Post (Discuss, ebenfalls Community-Kernbestandteil) in einen Team-Kanal
sichtbarer als eine Einzel-Notification pro Follower — dieselbe Grundidee wie Punkt I3 im
Feature-Ideenkatalog, hier auf einen Team-Kanal statt Einzelpersonen gerichtet.

---

## 8. Repo-weiter Kontext: Verzahnung mit den Geschwister-Modulen

Der eigentliche "weite Kontext" — `int_filemanager` existiert nicht isoliert, sondern neben
`int_repair_workshop` (Reparaturaufträge, hängt bereits von `hr` ab), `int_generic`
(App-unabhängige Odoo-Anpassungen) und den in der Memory vermerkten Plänen für ein künftiges
Prüfprotokoll-Odoo-Modul.

**8a. `hr.employee` — ein Einzeiler, direkt nach etabliertem Muster.** Der
`IntFilemanagerLinkableMixin` ist laut eigener Doku "bewusst modellagnostisch gehalten, weitere
Modelle sind ein reiner Vererbungs-Einzeiler" — bisher nur auf `res.partner` verdrahtet.
`hr.employee` wäre der naheliegende nächste Kandidat: Personalakten-Dokumente (Verträge,
Zertifikate, Schulungsnachweise) direkt am Mitarbeiterdatensatz sichtbar, exakt dasselbe
Smart-Button-Muster wie bei Kontakten. Besonders naheliegend, weil `int_repair_workshop` bereits
von `hr` abhängt und mit Mitarbeiter-Feldern arbeitet (sieben Werkstattstufen, je ein
Mitarbeiterfeld) — dieselben Mitarbeiter tauchen also in beiden Modulen auf.

**8b. `repair.order` — schließt zwei bisher getrennte Initiativen kurz.** `int_repair_workshop`
(Werkstatt-Felder am Reparaturauftrag) hat aktuell keine Dateiverknüpfung. Fotos
vor/nach Reparatur, ein Prüfprotokoll-PDF, technische Unterlagen zum betroffenen Gerät — alles
Dinge, die heute vermutlich (falls überhaupt digital) lose irgendwo im Dateibaum liegen, ohne
Bezug zum Odoo-Reparaturauftrag. Derselbe Mixin-Einzeiler wie 8a. **Besonders relevant im
Kontext der Memory-Notiz** zu einem geplanten Prüfprotokoll-Odoo-Modul (die alte
Prüfprotokoll-Anwendung wurde gelöscht, Neubau als Odoo-Modul vorgesehen) — sollte dieser
Neubau tatsächlich angegangen werden, wäre "Prüfprotokolle sind Dateien im Filemanager,
verknüpft mit `repair.order`/einem neuen Prüfprotokoll-Modell über genau diesen Mixin" eine
naheliegende, mit minimalem Aufwand realisierbare Architekturentscheidung — statt ein drittes,
unabhängiges Dateiablage-Konzept für Prüfprotokolle zu bauen. Nur als Denkanstoß festgehalten,
keine Vorwegnahme einer noch nicht getroffenen Produktentscheidung.

**8c. `int_generic`s Scoping-Muster wiederverwendbar.** Der bereits etablierte Patch-Stil
(`patch(SearchModel.prototype, {...})`, gescopet auf `this.resModel === "..."`, siehe
`search_model_patch.js` und `int_generic/list_column_reorder.js`) ist ein wiederkehrendes,
bewährtes Muster in diesem Repo für "natives Verhalten gezielt für ein Modell anpassen, ohne
Core-Dateien anzufassen oder andere Views zu beeinflussen" — jede künftige UI-Anpassung
(z.B. Punkt 9 unten) sollte konsequent demselben Muster folgen, nicht neu erfunden werden.

**8d. Multi-Company — offene Frage, nicht vorschnell bauen.** `int_filemanager.root_path` ist
ein einzelner globaler `ir.config_parameter`, kein `company_id`-Feld. Falls HM-SRV/Tower/die
Instanzen mit mehreren `res.company`-Datensätzen arbeiten (unklar, nicht geprüft) und
unterschiedliche Firmen unterschiedliche Wurzelverzeichnisse brauchen sollten, wäre das eine
echte native-Integrationslücke (Standard-Odoo-Muster: `company_id`-Feld + Record-Rule-Erweiterung
um `('company_id', 'in', company_ids)`). **Nur bei tatsächlichem Bedarf prüfen** — auf keinen
Fall vorsorglich bauen, ohne dass eine zweite Firma mit eigenem Dateibestand real existiert.

---

## 9. Command Palette (Strg+K) — Dateisuche in der globalen Odoo-Schnellsuche

Odoo hat eine globale Befehlspalette (Tastenkürzel i.d.R. Strg+K/Alt+K, `@web/core/commands`),
über die sich Menüs, Datensätze und Apps schnell erreichen lassen — erweiterbar über
`registry.category("command_provider")`. Ein eigener kleiner Provider (gescopet, siehe Punkt 8c),
der Dateinamen aus `int_filemanager.file` in dieses globale Sucherlebnis einspeist, würde die
"sofort tippen und finden"-Erfahrung, die für das Explorer-Parität-Ziel angestrebt wird, auf die
**gesamte** Odoo-Oberfläche ausdehnen — nicht nur innerhalb der Filemanager-Ansicht selbst
auffindbar, sondern von überall in Odoo aus per Tastenkürzel. Moderater JS-Aufwand
(ein Provider, eine RPC-Anfrage gegen die bestehende Such-Query), kein Backend-Neuland.

---

## 10. Nativer Export/Druck als Nebeneffekt der laufenden ListView-Migration

Kein neuer Vorschlag, sondern ein zusätzliches Argument für ein bereits geplantes Vorhaben:
solange `/int_filemanager/list` rohe Dicts statt echter ORM-Records liefert (alte UI), fehlt der
native Excel-/CSV-Export und Druck, den jede normale Odoo-Liste automatisch hat. Die auf
`experiment/native-listview` bereits verifizierte Umstellung auf echte `int_filemanager.file`-
Records (siehe `int_filemanager_native_ui.md`) bringt diesen Export/Druck **automatisch mit**,
ohne dass dafür je etwas Eigenes gebaut werden müsste — ein zusätzlicher, bisher nicht genannter
Nutzen der ohnehin laufenden Migration, der die Priorität dieses Abschlusses eher noch erhöht.

---

## 11. Enterprise-gated native Apps — zur Einordnung, nicht zur Nachahmung

Nur zur Vollständigkeit, da "weiter Kontext" auch heißt: wissen, wovon bewusst abgewichen wird.
Odoos eigene **Documents**-App (Enterprise) organisiert Dateien in "Workspaces" (hierarchische,
smarte Ordner mit eigenen Tags/Regeln — konzeptionell nah an `int_filemanager`s
Schutzordner+Tag-Kombination) und hat ein **"Anfordern"-Feature**: ein Platzhalter-Eintrag wird
angelegt, ein Kontakt/Kollege wird gebeten, die fehlende Datei hochzuladen, mit Fälligkeitsdatum
und automatischer Erinnerung. Das ist eine elegante Idee unabhängig von der Lizenzfrage — ließe
sich als eigenes, schlankes Konzept nachbauen (ein `int_filemanager.file`-Platzhalter-Datensatz
ohne Plattendatei, `state='requested'`, Portal-Upload-Link an den Empfänger, Cron-Erinnerung bei
Fälligkeit) **ohne** die Enterprise-App selbst zu brauchen — dieselbe "Idee übernehmen, nicht das
Produkt" wie bereits erfolgreich bei der PaperOffice-Recherche praktiziert. Nur als Denkanstoß,
kein ausgearbeiteter Plan.

Approvals (Enterprise) und Automation Rules/Studio (Enterprise) wurden in Punkt 3 bereits
eingeordnet. Odoo Sign bleibt wie in `int_filemanager_paperoffice_recherche.md` (Baustein 5)
festgehalten: Lizenzstatus vor jeder weiteren Prüfung erst verifizieren.

**Quelle:** [Documents — Odoo 19.0 documentation](https://www.odoo.com/documentation/19.0/applications/productivity/documents.html)

---

## Priorisierungsvorschlag

**Sofort einzuplanen, kein Enterprise-Risiko, korrigiert eine echte Lücke:** Punkt 1
(Bus-Live-Refresh in der neuen UI nachziehen) — sollte vor dem geplanten Löschen der alten UI
passieren, sonst stille Regression.

**Risikofrei nativ, geringer Aufwand:** Punkt 5 (Pivot/Graph-Dashboard), Punkt 4
(Knowledge-Artikel für Endnutzer), Punkt 8a/8b (Mixin auf `hr.employee`/`repair.order`
ausweiten, je ein Einzeiler), Punkt 6/7 (Kalender/Discuss als Ergänzung zu bereits vorhandenen
Aktivitäten/Followern).

**Moderater Aufwand, hoher UX-Gewinn:** Punkt 9 (Command-Palette-Provider), Punkt 10 (fällt der
laufenden Migration praktisch zu, kein Extra-Projekt).

**Erst nach Vor-Ort-Verifikation der Odoo-Edition sinnvoll planbar:** Punkt 3
(Automatisierungsregeln — falls Enterprise fehlt, direkt den beschriebenen
Community-Ersatzweg über `ir.actions.server`/eigene Regel-Tabelle nehmen, nicht auf die
Enterprise-App warten).

**Große, eigenständige Architekturentscheidungen, nicht nebenbei umsetzen:** Punkt 2
(`ir.attachment`-generische Verknüpfung als Ersatz/Ergänzung zu `res_reference`) und Punkt 8d
(Multi-Company) — beide nur mit explizitem Auftrag und eigener Review-Runde, analog der
Sorgfalt, die die ursprüngliche ACL-Einführung bekommen hat.
