# int_filemanager: Recherche PaperOffice DMS — elegante Ausbaumöglichkeiten

Stand 2026-09-04. Getrennt von [int_filemanager_ausbau.md](int_filemanager_ausbau.md) (Backend-
Phasen 1-5, alle umgesetzt) und [int_filemanager_native_ui.md](int_filemanager_native_ui.md)
(UI-Migration). Hier: Recherche zu [PaperOffice](https://start.paperoffice.com/de/dms-dokumentenmanagement-system/)
(kommerzielles, KI-gestütztes DMS, on-premise/NAS/Windows-Linux-Server) und wie sich dessen
Kernfunktionen **elegant** — d.h. durch Erweiterung bestehender Muster statt neuer Baustellen —
auf `int_filemanager` übertragen ließen. Reine Recherche/Konzept, keine Umsetzung in dieser Session.

## Was ist PaperOffice, konkret

PaperOffice ist ein KI-gestütztes Dokumentenmanagementsystem (DMS) für KMUs, deploybar auf
lokalem PC, Windows/Linux-Server, Synology/QNAP-NAS oder Cloud (AWS/Azure). Kernversprechen:
Dokumente werden beim Import automatisch erkannt, per OCR volltext-durchsuchbar gemacht,
KI-basiert verschlagwortet und abgelegt — ohne manuelle Sortierarbeit.

**Recherchierte Funktionsbausteine** (Quellen unten):

| Kategorie | Konkrete Funktionen |
|---|---|
| Erfassung | Scan/Stapelscan, E-Mail-Archivierung (Outlook-Anbindung), mobile Erfassung, Web-Formulare |
| KI/OCR | Volltext-OCR (~160 Sprachen), automatische Spracherkennung, trainierbare Texterkennungs-Korrektur ("SmartSpell"), automatische Dokumentenwert-Erkennung, KI-basierte Verschlagwortung, automatische Kontakterkennung |
| Suche | SQL-basierte Volltext-Indizierung, "Google-artige" Live-Suche, REGEX-Filter |
| Workflow | Digitale Workflows, Aufgaben-/Fristenverwaltung, Ampel-System (Rot-Grün-Freigaben, z.B. Rechnungsfreigabe), Stempel/Notizen/virtuelle Post-Its |
| Sicherheit/Compliance | Verschlüsselung, Benutzerverwaltung/Zugriffsrechte, GoBD-revisionssichere Archivierung, DSGVO, Versionierung, Audit-Trail |
| Integration | Microsoft-Office-Anbindung (Outlook/Word/Excel), API/Schnittstellen, Druckerbefehl-Automatisierung, NAS-Integrationen |
| Sonstiges | Kontakt-/Kalenderverwaltung mit Dokumentenverknüpfung, digitale Signatur/Freigabe |

**Quellen:**
- [PaperOffice DMS Dokumentenmanagement System mit KI-Integration](https://start.paperoffice.com/de/dms-dokumentenmanagement-system/?d=1)
- [7 wichtigste Funktionen, die Ihr DMS erfüllen muss](https://start.paperoffice.com/en/dms-document-management-system-most-important-functions)
- [Perfekte OCR Texterkennung und Suchfilter](https://start.paperoffice.com/en/functions/dms-document-management-system-with-ocr-text-recognition-and-keyword-search)
- [PaperOffice Classic DMS — On-premise Windows & NAS](https://start.paperoffice.com/en/dms-document-management-system)
- [FALKConS: Willkommen beim DMS von PaperOffice](https://falkcons.de/willkommen-beim-dokumentenmanagement-system-dms-von-paperoffice/)

## Grundprinzip des Ausbauvorschlags

`int_filemanager` hat bereits mehrere Bausteine, auf die PaperOffice-Funktionen **direkt aufsetzen**
lassen, ohne neue Architektur einzuführen:

- Einen **Pending-State-Pipeline-Mechanismus** ([mediameta.py](../int_filemanager/mediameta.py) +
  `meta_state`/`meta_error`/`meta_attempts`-Felder auf `int_filemanager.file`, Hash-Budget-limitiert,
  Cron-getrieben) — aktuell für Bild-/PDF-/Audio-Metadaten, strukturell identisch für OCR/Volltext
  wiederverwendbar.
- Ein **Tag-Modell** (`int_filemanager.tag`, `tag_ids` many2many, natives `many2many_tags`-Widget
  bereits in der Liste) — direktes Ziel für KI-Verschlagwortung.
- Eine **polymorphe Verknüpfung** (`res_reference` + `IntFilemanagerLinkableMixin`,
  [filemanager_linkable_mixin.py](../int_filemanager/models/filemanager_linkable_mixin.py)) — für
  Kontakt-/Vorgangsverknüpfung bereits vorhanden, nicht neu zu bauen.
- Eine **Versionierung mit Hash-Dedupe** ([filemanager_version.py](../int_filemanager/models/filemanager_version.py)) —
  Grundlage für revisionssichere Historie.
- Eine **ACL-Regel-Generierung pro Schutzordner** ([acl_rules.py](../int_filemanager/acl_rules.py)) —
  Erweiterungspunkt für WORM/Unveränderlichkeits-Regeln.
- Ein **Freigabe-Mechanismus** (`share_token`, `action_generate_share_token`,
  [filemanager_share_log.py](../int_filemanager/models/filemanager_share_log.py)) — Vorbild/Baustein
  für Freigabe-Workflows.
- Die **native ListView/SearchPanel/ActionMenus-Architektur**
  ([native_list_view.js](../int_filemanager/static/src/int_filemanager/native_ui/native_list_view.js)) —
  jeder neue Aktions-Knopf (Signatur, Workflow-Status ändern, …) folgt demselben, heute schon
  etablierten Muster (`getStaticActionMenuItems()`).

Die folgenden Bausteine sind nach **Eleganz** sortiert — d.h. danach, wie viel bestehende
Infrastruktur wiederverwendet wird, bevor irgendein neues Konzept eingeführt werden muss.

---

## Baustein 0 ✅ Drag&Drop umgesetzt (2026-09-05) — Erfassungs-Parität zur aktuellen Praxis

**Bevor Suche/KI/Workflow überhaupt zählen, muss die tägliche Erfassungs-Routine erhalten
bleiben.** Recherchierte/beschriebene Realität bei den Mitarbeitern (2026-09-05): Sie ziehen PDFs
per Drag & Drop direkt aus dem Dateisystem, ziehen Anhänge direkt aus Outlook, oder scannen direkt
in PaperOffice. Alle drei Fälle einzeln der bestehenden Architektur zugeordnet:

- **Drag & Drop aus dem Dateisystem — umgesetzt und live verifiziert** (Details:
  [int_filemanager_native_ui.md](int_filemanager_native_ui.md), Punkt 21): `window`-weite Drag-
  Events statt einer einzelnen Drop-Zone, derselbe bestehende Upload-Pfad wie der "Hochladen"-
  Button. Dabei einen echten, vorbestehenden Bug in `controllers/main.py` gefunden und behoben
  (`FileStorage.save()` erwartete in diesem Odoo-Build ein offenes Dateiobjekt, kein Pfad-String -
  betraf auch den alten Button, nicht nur Drag&Drop).
- **Anhang aus Outlook ziehen:** technisch **derselbe Mechanismus** wie oben — beide Quellen
  kommen im Browser als `DataTransfer.files`-Event an, dieselbe Drop-Zone deckt beides ab.
  **Offener Prüfpunkt, bewusst nicht ungeprüft behauptet:** ob ein Drag aus der konkret
  eingesetzten Outlook-Version (klassisches Desktop-Outlook vs. neues Outlook/WebView2 vs. OWA im
  Browser) tatsächlich als echtes Datei-Drag beim Browser ankommt, ist versionsabhängig — vor
  Umsetzung live gegen die tatsächlich genutzte Outlook-Version zu verifizieren, nicht anzunehmen.
- **Scannen direkt ins DMS:** einziger Fall, der **keine reine Web-Funktion** ist — Browser haben
  keinen Zugriff auf TWAIN/WIA-Scanner-Treiber, dafür existiert kein Web-Standard. Zwei Wege:
  - **Praktisch aufwandsfreie Lösung:** Scanner-Software auf einen vom Watcher beobachteten
    Eingangs-Unterordner einstellen (z.B. `/Eingang-Scan/<Mitarbeiter>/`) - der bestehende Watcher
    ([watcher.py](../int_filemanager/watcher.py)) nimmt jede neu erscheinende Datei automatisch
    auf, **ganz ohne Code-Änderung**. Die meisten Scan-Programme (auch an Multifunktionsdruckern)
    beherrschen "Scan in Netzwerkordner" bereits nativ.
  - Ein echter In-App-Scan-Button wie bei PaperOffice bräuchte einen TWAIN-Brücken-Client o.ä. -
    deutlich größerer, fragilerer Aufwand für einen Komfortgewinn, den der
    Eingangsordner-Weg praktisch gleichwertig abdeckt.

Empfehlung: Drag & Drop (deckt Fall 1 und 2 gemeinsam ab) zuerst umsetzen - kleine, klar
umrissene Ergänzung an einer bestehenden Funktion, größter Alltagsnutzen. Scan-Eingangsordner ist
reine Konfiguration, keine Entwicklung - kann parallel eingerichtet werden.

## Baustein 1: Volltextsuche mit OCR

**Größte fehlende Fähigkeit.** Aktuell durchsucht die Suchleiste nur `name` und `tag_ids`
(`filemanager_file_search.xml`) — der eigentliche Dokumenteninhalt ist unsichtbar für die Suche.
Das ist PaperOffice größtes Alleinstellungsmerkmal ("beste Volltextsuche aller Zeiten").

**Vorschlag:**
- Neues Feld `content_text` (`fields.Text`, oder direkt eine Postgres-`tsvector`-Spalte mit
  GIN-Index für native Volltext-Rankings) auf `int_filemanager.file`.
- Befüllung als **neue Pending-State-Pipeline-Stufe**, strukturell identisch zu
  `mediameta.py`/`meta_state`: eigener `ocr_state`, damit OCR (teuer, oft Sekunden pro Seite) nicht
  denselben Hash-Budget-Topf wie die schon vorhandene, günstigere Metadaten-Extraktion belegt.
  - PDFs mit Textlayer: direkte Extraktion (PyPDF2 ist laut [int_filemanager_ausbau.md](int_filemanager_ausbau.md)
    bereits vorhanden).
  - Gescannte PDFs/Bilder: OCR via `pytesseract`/`ocrmypdf` (neue Abhängigkeit, analog zu
    `mutagen` fürs Dockerfile).
  - Office-Dokumente: Text extrahierbar über python-docx/openpyxl **oder** über die ohnehin
    vorhandene ONLYOFFICE-Anbindung (Document-Server kann in Klartext konvertieren) — zweite
    Option vermeidet eine weitere Abhängigkeit.
- **Suchintegration braucht keine einzige Zeile JavaScript:** `<field name="content_text"
  string="Inhalt"/>` in `filemanager_file_search.xml` reicht — das native "Search Inhalt for: …"
  fügt sich automatisch ins bestehende Dropdown-Muster ein (dasselbe, das heute schon "Search Name"/
  "Search Tags" anbietet), inklusive der heute schon gebauten rekursiven Suche
  ([search_model_patch.js](../int_filemanager/static/src/int_filemanager/native_ui/search_model_patch.js),
  siehe Punkt 3 dort — `this.query.length > 0` triggert automatisch `child_of`, unabhängig vom
  Feldnamen).

## Baustein 2: `mail.thread`/`mail.activity.mixin` erben — deckt drei PaperOffice-Features auf einmal ab

**Der günstigste Gewinn im ganzen Vorschlag.** `int_filemanager.file` erbt aktuell nur von
`models.Model`. Odoo bringt mit `mail.thread` + `mail.activity.mixin` **nativ** genau das mit, was
PaperOffice als eigene Features verkauft:

| PaperOffice-Feature | Odoo-Bordmittel bei `_inherit = ["mail.thread", "mail.activity.mixin"]` |
|---|---|
| Aufgabenverwaltung mit Fristüberwachung | `mail.activity` (native "Aktivität planen", Fälligkeitsdatum, Erinnerungen) |
| Virtuelle Post-Its/Notizen | Chatter-"Protokollieren"-Notizen |
| Audit-Trail | Automatisches Log jeder Feldänderung im Chatter |
| Team-Benachrichtigungen/Follower | `message_follower_ids` nativ |

Aufwand: eine Zeile (`_inherit`) plus ein `<chatter/>`-Element in der bestehenden
`filemanager_file_form_view.xml` (dem Formular-Dialog, den der Pfeil-Button in der Liste schon
öffnet, siehe Punkt 6 in [int_filemanager_native_ui.md](int_filemanager_native_ui.md)). Kein
neues Modell, kein neuer Controller, keine neue UI-Komponente — vier PaperOffice-Funktionen
"kostenlos nativ", derselbe Grundsatz, der die gesamte UI-Migration in
[int_filemanager_native_ui.md](int_filemanager_native_ui.md) geleitet hat.

## Baustein 3: KI-Verschlagwortung + automatische Dokumentenwert-Erkennung

Nach Baustein 1 (Volltext liegt vor) ist automatische Verschlagwortung eine weitere
Pipeline-Stufe: `content_text` an ein LLM geben (naheliegend: Anthropic API, da bereits
Umgebungskontext in diesem Projekt), Ergebnis in zwei bestehende bzw. native Bausteine schreiben:

- **Tags:** direkt in `tag_ids` (`int_filemanager.tag`) — bestehendes Modell, bestehendes Widget,
  keine Änderung nötig, nur ein neuer Schreiber.
- **Extrahierte Werte** (Rechnungsnummer, Datum, Absender, Betrag, …): Odoos natives
  `fields.Properties`-Feld — flexible, pro Datensatz unterschiedliche Key/Value-Metadaten, exakt
  für diesen Fall entworfen. Bereits an anderer Stelle im Projekt als Konzept erwähnt (optionale
  Spalten-Aufsplittung, [int_filemanager_native_ui.md](int_filemanager_native_ui.md) Punkt 3) —
  hier wäre die naheliegende praktische Anwendung dafür.

## Baustein 4: Ampel-Freigabe-Workflow

PaperOffice bewirbt ein "Ampel-System" für Freigaben (z.B. Rechnungsfreigabe). Odoo hat dafür
bereits ein **natives Widget**: `kanban_state` (das rot/gelb/grün-Kreis-Icon, das man aus Odoo-
Kanban-Karten kennt) — keine eigene Ampel-Komponente nötig, nur ein neues Selection-Feld auf
`int_filemanager.file` (`state = fields.Selection([...], default="normal")`,
`widget="kanban_state"` in Liste/Formular) plus optional ein `ir.rule`/`type="object"`-Button
analog zu `action_generate_share_token`, um den Status zu wechseln. Passt als weiterer Eintrag in
`getStaticActionMenuItems()` (`native_list_view.js`), Muster identisch zu "Freigeben"/"Lokal
öffnen" (siehe Commit `d0c7324`, heute).

## Baustein 5: Digitale Signatur

Statt eine eigene Signaturlösung zu bauen: Odoo hat mit **Odoo Sign** (`sign`-Modul) bereits eine
vollständige native E-Signatur-App. Elegante Anbindung: ein weiterer `ActionMenus`-Eintrag
("Signieren"), der — analog zu `onShare()` (`this.actionService.doAction(...)`, heute committet) —
einen `sign.request` für das verlinkte `ir.attachment` der Datei erzeugt. Setzt voraus, dass
`sign` als optionale Abhängigkeit ergänzt wird (`depends`); die Anbindung selbst folgt demselben
Muster wie die heutige ONLYOFFICE-/Freigeben-Portierung.

## Baustein 6: Revisionssichere/unveränderliche Archivierung (GoBD-Analogie)

Versionierung existiert bereits ([filemanager_version.py](../int_filemanager/models/filemanager_version.py)).
Was fehlt, ist eine **Unveränderlichkeits-Garantie** nach Archivierung. Eleganteste Anbindung:
Erweiterung der bestehenden `protected_folder`-ACL-Regel-Generierung
([acl_rules.py](../int_filemanager/acl_rules.py), `rebuild_rules()`) um ein Flag
`immutable_after` (Datum) pro Schutzordner — dieselbe Pipeline, die heute schon read/write/unlink-
Regeln pro Ordner erzeugt, bekommt eine zusätzliche Dimension ("niemand, auch kein Admin, darf
löschen/überschreiben nach Datum X"), statt eine zweite, parallele Sicherheitsschicht einzuführen.

## Baustein 7: E-Mail-Archivierung

Odoo hat mit `fetchmail.server`/`mail.thread` bereits eingehende Mailverarbeitung. Elegante
Anbindung: ein Cron, der Anhänge (oder die komplette `.eml`) von markierten `mail.message`-
Datensätzen automatisch als `int_filemanager.file` ablegt und über die **bereits vorhandene**
`res_reference`-Verknüpfung ([filemanager_linkable_mixin.py](../int_filemanager/models/filemanager_linkable_mixin.py))
mit dem ursprünglichen Datensatz/Kontakt verbindet — keine neue Verknüpfungslogik, nur ein neuer
Schreiber in bestehende Felder.

---

## Bewusst nicht übernommen (bzw. nicht elegant genug für einen eigenen Baustein)

- **Verschlüsselung at-rest:** Infrastruktur-/Dateisystemebene (z.B. LUKS auf dem Server), keine
  Modul-Funktion — würde hier nur vorgetäuschte Sicherheit ohne echten Mehrwert im Code bedeuten.
- **Eigene mobile App / Scanner-Hardware-Anbindung:** der bestehende `/int_filemanager/upload`-
  Endpunkt plus die Portal-Templates ([portal_templates.xml](../int_filemanager/views/portal_templates.xml))
  decken "von unterwegs hochladen" bereits ausreichend ab, ohne dass eine native App gerechtfertigt
  wäre.
- **NAS-spezifische Integrationen (Synology/QNAP):** irrelevant, da `int_filemanager` bereits
  filesystem-agnostisch ist (jedes gemountete Verzeichnis funktioniert, siehe `int_filemanager.root_path`).

## Empfohlene Reihenfolge (bei Umsetzung)

**Baustein 0 (Drag & Drop) zuerst** - ohne erhaltene Erfassungs-Routine nutzen Mitarbeiter das
Tool im Alltag nicht, unabhängig davon, wie gut Suche/KI später sind; Scan-Eingangsordner ist
reine Konfiguration und kann parallel eingerichtet werden. Danach Baustein 2 (mail.thread/
activity) - praktisch aufwandsfrei, deckt die meisten übrigen Features ab, kein
Abhängigkeitsrisiko. Danach Baustein 1 (Volltextsuche/OCR) - größter Nutzen, aber neue
Abhängigkeit (OCR-Library) und Rechenkosten, verdient eine eigene Kapazitäts-/Performance-Prüfung
wie die SearchPanel-Arbeit heute. Bausteine 3-7 bauen jeweils auf 1 oder 2 auf bzw. sind
unabhängige, kleine Ergänzungen, die sich einzeln priorisieren lassen, sobald der Bedarf feststeht.
