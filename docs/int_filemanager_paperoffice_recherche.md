# int_filemanager: Recherche PaperOffice DMS — elegante Ausbaumöglichkeiten

Stand 2026-09-04. Getrennt von [int_filemanager_ausbau.md](int_filemanager_ausbau.md) (Backend-
Phasen 1-5, alle umgesetzt) und [int_filemanager_native_ui.md](int_filemanager_native_ui.md)
(UI-Migration). Hier: Recherche zu [PaperOffice](https://start.paperoffice.com/de/dms-dokumentenmanagement-system/)
(kommerzielles, KI-gestütztes DMS, on-premise/NAS/Windows-Linux-Server) und wie sich dessen
Kernfunktionen **elegant** — d.h. durch Erweiterung bestehender Muster statt neuer Baustellen —
auf `int_filemanager` übertragen ließen. Ursprünglich reine Recherche, mittlerweile teilweise
umgesetzt (Bausteine 0 und 1, siehe unten) - für den aktuellen Stand und wie es weitergeht direkt
zum Abschnitt "Für eine neue Session: hier weitermachen" springen.

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

## Baustein 1 ✅ umgesetzt (2026-09-05): Volltextsuche mit OCR + interaktive Werterkennung

**War die größte fehlende Fähigkeit.** Details der tatsächlichen Umsetzung (Umfang enger als hier
ursprünglich skizziert, plus ein interaktiver Kontroll-Dialog analog PaperOffice - siehe
Konversation 2026-09-05):
[int_filemanager_native_ui.md](int_filemanager_native_ui.md), Punkt 22.

Kurzfassung der tatsächlichen Umsetzung ggü. diesem ursprünglichen Entwurf:
- **v1 bewusst nur PDF + reine Textformate**, nicht Office-Dokumente/Bilder (siehe dort für die
  Begründung) - Office-Textextraktion bleibt ein möglicher Baustein 1b.
- **Zweistufige PDF-Behandlung** umgesetzt wie geplant: Textlayer zuerst (PyPDF2), OCR
  (`pytesseract`/`pdf2image`, nicht `ocrmypdf`) nur als Fallback bei zu wenig Text pro Seite.
- **Eigener `ocr_state`** wie geplant, plus feste Felder (`extracted_date`/
  `extracted_invoice_number`/`extracted_amount`) statt eines `fields.Properties` - Regex-Erkennung
  liefert ein festes, kleines Wertschema, kein dynamisches (siehe Punkt 22 für die Begründung).
- **Suchintegration exakt wie hier vorhergesagt** - eine Zeile in der Search-View, kein JS nötig,
  live bestätigt (Volltextsuche nach einem Wort, das nur im Dateiinhalt vorkommt, findet die
  Datei).
- **Zusätzlich, über diesen ursprünglichen Entwurf hinaus:** ein interaktiver Kontroll-Dialog
  (PaperOffice-Vorbild: "reingezogene Datei wird direkt erkannt, Werte werden zur Kontrolle
  angezeigt") - einfache Regex/Bestandsabgleich statt KI (Nutzerentscheidung), ein Dialog pro
  Datei bei Mehrfach-Upload. Kein automatischer Backfill für bereits bestehende Dateien
  (Nutzerentscheidung) - nur neu ankommende/manuell ausgewählte Dateien.

## Baustein 2 ✅ umgesetzt (2026-09-06): `mail.thread`/`mail.activity.mixin` erben — deckt drei PaperOffice-Features auf einmal ab

**Der günstigste Gewinn im ganzen Vorschlag.** Umgesetzt wie unten beschrieben, live auf der
Tower-Testinstanz verifiziert (Notiz geloggt, Aktivität geplant) - Details, inklusive einer
aufgeklärten Verwirrung um fehlenden Chatter im Formular-Dialog (Odoo-Kernverhalten, kein Bug) und
eines dabei entdeckten unabhängigen Bugs (Hash-Cron/int4-Overflow bei Dateien >2GB, separat
geflaggt): [int_filemanager_native_ui.md](int_filemanager_native_ui.md), Punkt 23.

`int_filemanager.file` erbte zuvor nur von
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

## Baustein 3 ⚠️ größtenteils durch Baustein 1 erledigt — nur noch "Regex → LLM" offen

**Bei der Umsetzung von Baustein 1 (2026-09-05) ist das hier bereits mit erledigt worden**, nur
anders als ursprünglich skizziert: der interaktive Kontroll-Dialog dort schreibt Tags (aus
Bestandsabgleich, nicht LLM) bereits in `tag_ids`, und Werte (Datum/Rechnungsnr./Betrag) bereits in
feste Felder (nicht `fields.Properties` - siehe Begründung in
[int_filemanager_native_ui.md](int_filemanager_native_ui.md), Punkt 22: ein `Properties`-Feld ist
für dynamische, pro Dokumenttyp wechselnde Schemata gedacht, die Regex-Erkennung liefert aber ein
festes, kleines Set). **Kein eigener Baustein mehr, nur noch eine mögliche spätere Erweiterung:**

- Falls die Regex-Erkennung (Nutzerentscheidung 2026-09-05, bewusst gegen ein LLM) sich als zu
  eingeschränkt erweist: `suggest_from_text()` (`fulltext.py`) durch einen LLM-Aufruf ersetzen
  oder ergänzen - der Rest der Pipeline (Dialog, Schreibpfad, `res_reference`-Vorschlag) bleibt
  unverändert, nur die Vorschlagsquelle würde sich ändern. **Echte Produktentscheidung, kein
  Implementierungsdetail** - erst auf ausdrücklichen Wunsch angehen, nicht selbstständig
  einführen (externe API, laufende Kosten, war schon einmal bewusst abgelehnt worden).
- Falls doch einmal wirklich pro Dokumenttyp unterschiedliche Wertschemata gebraucht werden
  (z.B. Verträge mit anderen Feldern als Rechnungen): dann wäre `fields.Properties` die richtige
  native Wahl, aber erst wenn dieser Bedarf tatsächlich auftritt, nicht vorsorglich.

## Baustein 4: Ampel-Freigabe-Workflow

PaperOffice bewirbt ein "Ampel-System" für Freigaben (z.B. Rechnungsfreigabe). Odoo hat dafür
bereits ein **natives Widget**: `kanban_state` (das rot/gelb/grün-Kreis-Icon, das man aus Odoo-
Kanban-Karten kennt) — keine eigene Ampel-Komponente nötig, nur ein neues Selection-Feld auf
`int_filemanager.file` (`state = fields.Selection([...], default="normal")`,
`widget="kanban_state"` in Liste/Formular) plus optional ein `ir.rule`/`type="object"`-Button
analog zu `action_generate_share_token`, um den Status zu wechseln. Passt als weiterer Eintrag in
`getStaticActionMenuItems()` (`native_list_view.js`), Muster identisch zu "Freigeben"/"Lokal
öffnen" (siehe Commit `d0c7324`, heute).

## Baustein 5 ⚠️ Voraussetzung ungeprüft: Digitale Signatur

Statt eine eigene Signaturlösung zu bauen: Odoo hat mit **Odoo Sign** (`sign`-Modul) bereits eine
vollständige native E-Signatur-App. Elegante Anbindung: ein weiterer `ActionMenus`-Eintrag
("Signieren"), der — analog zu `onShare()` (`this.actionService.doAction(...)`, heute committet) —
einen `sign.request` für das verlinkte `ir.attachment` der Datei erzeugt. Setzt voraus, dass
`sign` als optionale Abhängigkeit ergänzt wird (`depends`); die Anbindung selbst folgt demselben
Muster wie die heutige ONLYOFFICE-/Freigeben-Portierung.

**Vor der Umsetzung zu klären, nicht anzunehmen:** ob `sign` auf HM-SRV überhaupt lizenziert/
installiert ist (Odoo Sign kann je nach Lizenzmodell Enterprise-only sein - auf der Tower-
Testinstanz noch nicht geprüft, live verifizieren statt zu vermuten, bevor die Abhängigkeit
ergänzt wird).

## Baustein 6 ⚠️ echte Produktentscheidung, nicht nur Implementierung: Revisionssichere Archivierung

Versionierung existiert bereits ([filemanager_version.py](../int_filemanager/models/filemanager_version.py)).
Was fehlt, ist eine **Unveränderlichkeits-Garantie** nach Archivierung. Eleganteste Anbindung:
Erweiterung der bestehenden `protected_folder`-ACL-Regel-Generierung
([acl_rules.py](../int_filemanager/acl_rules.py), `rebuild_rules()`) um ein Flag
`immutable_after` (Datum) pro Schutzordner — dieselbe Pipeline, die heute schon read/write/unlink-
Regeln pro Ordner erzeugt, bekommt eine zusätzliche Dimension ("niemand, auch kein Admin, darf
löschen/überschreiben nach Datum X"), statt eine zweite, parallele Sicherheitsschicht einzuführen.

**Bewusst nicht ohne Rücksprache umsetzen:** eine Funktion, die selbst Admins das Löschen/
Überschreiben verwehrt, ist eine Sicherheits-/Compliance-Entscheidung mit echten Konsequenzen
(ein Fehler hier sperrt euch selbst aus), keine reine Implementierungsfrage wie die meisten
anderen Bausteine hier. Vor Umsetzung: Rückfrage, ob GoBD-Konformität hier tatsächlich rechtlich
gebraucht wird und wer die Ausnahme-Berechtigung bekommen soll.

## Baustein 7 ⚠️ Voraussetzung ungeprüft: E-Mail-Archivierung

Odoo hat mit `fetchmail.server`/`mail.thread` bereits eingehende Mailverarbeitung. Elegante
Anbindung: ein Cron, der Anhänge (oder die komplette `.eml`) von markierten `mail.message`-
Datensätzen automatisch als `int_filemanager.file` ablegt und über die **bereits vorhandene**
`res_reference`-Verknüpfung ([filemanager_linkable_mixin.py](../int_filemanager/models/filemanager_linkable_mixin.py))
mit dem ursprünglichen Datensatz/Kontakt verbindet — keine neue Verknüpfungslogik, nur ein neuer
Schreiber in bestehende Felder.

**Vor der Umsetzung zu klären, nicht anzunehmen:** ob auf HM-SRV überhaupt ein `fetchmail.server`
konfiguriert ist bzw. eingehende Mails über Odoo laufen - ohne das ist dieser Baustein
gegenstandslos, live prüfen statt anzunehmen.

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

~~Baustein 0 (Drag & Drop) zuerst~~ ✅ erledigt. ~~Baustein 1 (Volltextsuche/OCR)~~ wurde vorgezogen
zuerst umgesetzt ✅ (Nutzerentscheidung, mehr Priorität als ursprünglich hier vorgeschlagen).
~~Baustein 2 (mail.thread/activity)~~ ✅ erledigt. **Nächster sinnvoller Schritt: Baustein 4**
(Ampel-Freigabe via `kanban_state`) - weiterhin praktisch aufwandsfrei, kein Abhängigkeitsrisiko,
keine offene Rückfrage. Danach 5/6/7 (jeweils mit ungeprüfter Voraussetzung bzw. echter
Produktentscheidung, siehe die Warnhinweise dort).

## Für eine neue Session: hier weitermachen

**Stand 2026-09-06, Branch `experiment/native-listview`.** Fertig: Baustein 0 (Drag&Drop),
Baustein 1 (Volltextsuche/OCR + Kontroll-Dialog, deckt Baustein 3 mit ab), Baustein 2
(mail.thread/mail.activity.mixin). Offen: Bausteine 4, 5, 6, 7 (siehe oben, in dieser Reihenfolge).

**Separat geflaggter, unabhängiger Bug (noch offen):** Hash-Cron schlägt bei Dateien >2GB fehl
(`hash_size` int4-Overflow) - siehe [int_filemanager_native_ui.md](int_filemanager_native_ui.md),
Punkt 23, letzter Absatz.

**Bevor an einem der offenen Bausteine weitergearbeitet wird, unbedingt zuerst lesen:**
[int_filemanager_native_ui.md](int_filemanager_native_ui.md) (Punkte 15-22) - dort steht die
tatsächliche Arbeitsweise, die sich in dieser Session bewährt hat, nicht nur das Ergebnis:

- **Änderungen live gegen die Odoo-19-Testinstanz auf Tower verifizieren, nicht nur Code schreiben
  und committen.** SSH-Key `claude-code-unraid` liegt in `authorized_keys` auf Tower
  (`192.168.178.73`, Container `odoo19-test`/`odoo19-test-db`, Login `admin`/`admin_test_2026`,
  LAN-erreichbar unter `http://192.168.178.73:8169`). Reale Daten dort sind bewusst read-only
  gemountet (`/mnt/user/Daten`, echte persönliche Daten - nicht schreibend testen ohne
  Rücksprache).
- **Vor Codeänderungen an nicht-trivialen Stellen den echten Odoo-19-Quellcode im Container lesen**
  (`docker exec odoo19-test cat /usr/lib/python3/dist-packages/odoo/...`) statt aus dem Training
  zu raten - mehrfach in dieser Session der Unterschied zwischen einer falschen und einer
  funktionierenden Lösung gewesen (z.B. `useExternalListener` kommt aus `@odoo/owl`, nicht
  `@web/core/utils/hooks`; `child_of` auf einem `_parent_name`-Feld ist selbst-inklusiv).
- **Nach jeder Änderung: Modul-Upgrade/Neustart auf Tower, live durchklicken, danach die isolierte
  Testsuite** (separate DB `odoo19test_ci`, niemals gegen die DB mit echten/großen Testdaten -
  ein Testlauf gegen die befüllte DB lief in dieser Session einmal stundenlang fest).
- **Jede Änderung dokumentieren** (neuer nummerierter Punkt in `int_filemanager_native_ui.md`,
  Was/Warum/Live-Verifikation) **und committen**, bevor zum nächsten Baustein übergegangen wird -
  nicht mehrere Bausteine gebündelt.
- **Bei echten Produktentscheidungen (nicht Implementierungsdetails) nachfragen statt zu raten** -
  in dieser Session hat sich das mehrfach ausgezahlt (Baustein 1 hat sich durch Rückfragen dreimal
  wesentlich geändert: LLM→Regex, automatischer Hintergrund→interaktiver Kontroll-Dialog,
  Backfill→kein Backfill). Die ⚠️-Markierungen bei den Bausteinen 5/6/7 oben zeigen konkret, wo das
  vermutlich wieder relevant wird.
