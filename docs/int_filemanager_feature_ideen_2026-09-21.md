# int_filemanager: Feature-Ideenkatalog

Stand 2026-09-21. Reine Analyse/Ideensammlung auf ausdrücklichen Wunsch ("sehr detailliert, in
allen Bereichen"), **nichts hiervon ist umgesetzt oder beauftragt**. Grundlage: vollständige
Durchsicht des aktuellen Codes (`int_filemanager/`, 46 Python- + ~25 JS/XML-Dateien) und aller
bestehenden Planungsdokumente, damit hier nichts doppelt vorgeschlagen wird, was bereits
umgesetzt, geplant oder bewusst verworfen ist.

## Ausgangslage: was heute schon da ist

Das Modul ist deutlich weiter als ein einfacher Dateibrowser. Bereits produktiv/umgesetzt:
Hash-basierte Identität (Rename-Erkennung), feingranulare ACL über Schutzordner, Versionierung
mit atomarem Schreibvorgang, Bild-/PDF-/Audio-/Video-Vorschau (inkl. Range-Streaming), interne
und externe Freigaben (Portal + anonymer Link), Volltextsuche mit OCR-Fallback (Tesseract +
AcroForm-Formularfelder), selbstdefinierte Extraktionsfelder mit PDF-Highlighting, Tags,
`mail.thread`/Aktivitäten/Chatter, ein Ampel-Freigabestatus, WebDAV-Einzeldatei-Bearbeitung
(Word/Excel lokal öffnen), ONLYOFFICE-Integration, natives `ListView`/`SearchPanel`-Ordnerbaum,
Drag&Drop-Upload, ZIP-Browsing, Datensatz-Verknüpfung (`res_reference`) u.a. auf Kontakte, ein
Text-Editor-Dialog und ein Reconciliation-Fallback-Scan für CIFS-Freigaben ohne SMB-Notify.

**Bereits geprüft und bewusst verworfen** (nicht hier nochmal vorschlagen, außer mit neuem
Blickwinkel explizit markiert): digitale Signatur (Lizenzfrage offen), GoBD-Unveränderlichkeit
(Compliance-Entscheidung, nicht technisch), E-Mail-Archivierung über `fetchmail.server`
(Voraussetzung ungeklärt), Verschlüsselung at-rest (Infrastrukturebene), eigene mobile App,
NAS-spezifische Integrationen, LLM-basierte Erkennung (Kosten/Datenschutz).

**Bereits geplant, aber noch nicht umgesetzt** (siehe jeweiliges Dokument, hier nicht
wiederholt): ACL-Performance-Fix bei 1,38 Mio. Zeilen (`archiv/int_filemanager_acl_perf_plan.md`),
Abschluss der nativen ListView-Migration inkl. Löschen des alten UI-Pfads
(`int_filemanager_native_ui.md`), Optimierung des CIFS-Reconciliation-Scans (`~289s` unabhängig
von der tatsächlichen Änderungsmenge, `archiv/int_filemanager_external_change_watcher_regression.md`).

Die folgenden Ideen sind nach Bereich sortiert, nicht nach Priorität — ein Priorisierungsvorschlag
steht ganz am Ende.

---

## A. Datensicherheit — der auffälligste echte Fund dieser Analyse

**A1. Papierkorb / Soft-Delete.** `delete()` in `controllers/main.py` ruft aktuell direkt
`shutil.rmtree()`/`os.remove()` — eine gelöschte Datei ist unwiderruflich weg, bis auf externe
Backups. Bei einem System, das echte Kollegen im Alltag als Explorer-Ersatz nutzen (ausdrückliches
UX-Ziel laut `int_filemanager_native_ui.md`), ist ein Fehlklick auf "Löschen" ohne
Wiederherstellung ein reales Risiko — und eine Lücke gegenüber dem Schwesterprojekt
`web-filemanager`, das genau dafür bereits ein Trash-Konzept hat. Naheliegende Umsetzung:
`delete()` verschiebt statt zu löschen (z.B. in einen versteckten `.trash/<uuid>`-Unterordner
innerhalb des Root-Pfads, oder ein konfigurierbares separates Trash-Verzeichnis), ein neues
leichtes Modell/View listet den Papierkorb-Inhalt mit "Wiederherstellen"/"Endgültig löschen", ein
Retention-Cron (bestehendes Muster, siehe Version-Pruning-Cron) räumt nach X Tagen automatisch
auf. Fügt sich sauber neben die bestehende Versionierung: Versionierung schützt vor
Überschreiben, Papierkorb schützt vor Löschen — zwei verschiedene, komplementäre Sicherheitsnetze.

**Nachtrag 2026-09-24: A1 ist umgesetzt.** Commit `b53fed2` (2026-09-21, gleicher Tag wie dieser
Fund) hat den Papierkorb bereits gebaut — `.trash/`-Unterbaum, Felder `trashed`/`trashed_at`/
`trashed_by`/`original_path`, Wiederherstellung, Pro-Nutzer-Sichtbarkeit per `ir.rule`, eigener
Menüpunkt, 30-Tage-Retention-Cron. Die hier skizzierte Umsetzung ("`.trash/<uuid>`-Unterordner",
neues Modell/View) beschreibt im Kern, was tatsächlich gebaut wurde. Details und ein noch offener
Bug (Vollscan kann Papierkorb-Einträge versehentlich endgültig löschen, B1) in
`int_filemanager_konzept_db_vorrang_2026-09-24.md` (Branch `docs/konzept-db-vorrang`), Abschnitt
16.1 — dort auch der Vorschlag, `trashed` durch natives `active` zu ersetzen.

**A2. Undo der letzten Aktion.** Kleinere Ergänzung zu A1: ein Toast/Notification nach
Löschen/Verschieben/Umbenennen mit "Rückgängig"-Aktion (analog Gmail/Windows-Explorer),
technisch nur ein UI-Komfort über die ohnehin vorhandenen Routen (Restore aus Papierkorb,
`move`/`rename` mit vertauschten Argumenten).

**A3. Bearbeitungskonflikte außerhalb ONLYOFFICE/WebDAV sichtbar machen.** WebDAV kennt
LOCK/UNLOCK, ONLYOFFICE hat seinen eigenen Sync-Mechanismus — aber zwei Nutzer, die beide den
Text-Editor-Dialog (`text_editor_dialog.js`) auf derselben Datei offen haben, überschreiben sich
aktuell stillschweigend (letzter Schreibvorgang gewinnt, kein Konflikthinweis). Ein einfacher
optimistischer Check (mitgeschickter `mtime`/Hash beim Öffnen, Vergleich beim Speichern, bei
Abweichung Warnung statt stillem Überschreiben) würde diese Lücke schließen, ohne die
bestehende Session-Lock-Infrastruktur aus der Versionierung anzufassen.

---

## B. Auffindbarkeit & Suche

**B1. Duplikat-Finder.** `content_sha256` wird bereits laufend gepflegt (Phase 1,
Scan-Identität) — aktuell nur intern für Rename-Erkennung genutzt. Eine simple Auswertung
(`GROUP BY content_sha256 HAVING COUNT(*) > 1`) plus eine Listen-/Pivot-Ansicht "Duplikate"
würde doppelt abgelegte Dateien (typisch bei Netzlaufwerken: dieselbe Rechnung in zwei
Projektordnern) sichtbar machen — praktisch geschenkt, da die teure Arbeit (Hashing) schon
läuft. Aufräumen bliebe manuell (Duplikat behalten/löschen), aber allein die Sichtbarkeit ist
ein Wert an sich.

**B2. Gespeicherte Suchen / Smart-Ordner.** Odoo bringt mit `ir.filters` bereits
"Favoriten"-Speicherung für jede Search-View nativ mit (das kleine Sternchen-Menü über jeder
Liste) — sofern `filemanager_file_search.xml` das nicht explizit blockiert, ist das potenziell
schon nutzbar oder mit minimalem Aufwand aktivierbar. Ergebnis wäre ein "Smart-Ordner"-Konzept
(z.B. "Alle Rechnungen 2026", "Von mir freigegeben, noch nicht abgelaufen") ganz ohne neues
Modell, nur eine gespeicherte Domain — analog zum bereits verworfenen `fields.Properties`-Weg
sollte hier zuerst geprüft werden, was Odoo nativ schon mitbringt, bevor selbst gebaut wird.

**B3. Volltextsuche auf Office-Dokumente ausweiten.** In `int_filemanager_paperoffice_recherche.md`
als "Baustein 1b" offen gelassen: `content_text` wird heute nur für PDF/reine Textformate
befüllt. `docx`/`xlsx`/`pptx` ließen sich über `python-docx`/`openpyxl`/`python-pptx` (reine
Text-/Zellextraktion, kein Rendering) in dieselbe `content_text`-Pipeline einspeisen — technisch
dieselbe Pending-State-Cron-Architektur wie OCR, nur eine weitere Extraktionsfunktion in
`fulltext.py`. Ohne Positions-/Highlighting-Anspruch (der ist PDF-spezifisch) ein
vergleichsweise kleiner Zusatzbaustein mit hohem Alltagsnutzen, da Office-Dateien vermutlich
einen großen Teil des realen Bestands ausmachen.

**B4. Trefferausschnitte in der Suche.** Aktuell liefert die Volltextsuche nur "Treffer/kein
Treffer" auf Dateiebene. Da `content_text` bereits wort-indiziert vorliegt (Phase-C-Umbau für
das PDF-Highlighting, `_build_indexed_text`), ließe sich ein kurzer Kontext-Ausschnitt um den
Treffer ("… Rechnung Nr. **12345** vom …") in der Listenansicht/im Suchresultat anzeigen —
nutzt dieselbe Infrastruktur, die für die Werterkennung ohnehin schon da ist.

**B5. "Ähnliche Dokumente".** Auf Basis vorhandener Signale (gleicher `tag_ids`-Überschneidung,
gleicher `res_reference`-Zieldatensatz, ähnliche erkannte `extracted_value`-Werte wie
Rechnungsnummer/Partner) ließe sich im Formular-Dialog eine kleine "Ähnliche Dateien"-Liste
anzeigen — reine Lesequery über bestehende Felder, kein neues Konzept.

---

## C. Navigation & Bedienung (Explorer-/Directory-Opus-Parität ist das erklärte UX-Ziel)

**C1. Adressleiste ("Gehe zu Pfad").** Directory Opus/Total Commander lassen Pfade direkt
eintippen statt zu klicken — ein Eingabefeld in der Toolbar, das per `parent_id`-Auflösung
(bestehende `SearchPanel`-Mechanik) direkt zum Zielordner navigiert. Kleine Ergänzung mit hohem
Tempo-Gewinn für Power-User, genau auf das in `int_filemanager_native_ui.md` explizit genannte
Ziel "Explorer-Tempo" einzahlend.

**C2. Zwei-Spalten-/Splitview.** Directory Opus' Kernfeature: zwei Ordner nebeneinander, um
zwischen ihnen zu verschieben/kopieren/vergleichen. Größerer UI-Umbau (zwei unabhängige
`IntFilemanagerListController`-Instanzen nebeneinander mit eigenem `SearchPanel`-Zustand), aber
folgt architektonisch demselben nativen `ListView`-Muster, das für die einspaltige Ansicht
bereits etabliert ist — kein neues Grundkonzept, nur eine Verdopplung mit Koordination
(Drag zwischen den beiden Panels).

**C3. Favoriten/Quick Access.** Eine "Zuletzt verwendet"/"Angeheftete Ordner"-Leiste analog
Windows Explorer. "Zuletzt verwendet" ließe sich rein clientseitig (`localStorage`, analog zum
bestehenden Muster für die optionale Spalten-Sichtbarkeit) ohne Backend-Änderung umsetzen;
"Angeheftete Ordner" bräuchte ein kleines Server-Feld (pro Nutzer, z.B. `res.users`-Erweiterung
oder ein simples `int_filemanager.favorite`-Modell), um geräteübergreifend zu funktionieren.

**C4. Galerie-/Rasteransicht für Bilder.** `native_kanban_view.js`/`.xml` existiert bereits im
Code — zu prüfen, wofür genau (falls das schon eine Bild-Kachelansicht ist, entfällt dieser
Punkt; falls es nur eine allgemeine Kanban-Ansicht ist, wäre eine dedizierte, großformatige
Foto-Rasteransicht mit den bereits vorhandenen 320×320-Thumbnails ein naheliegender
Zusatzbaustein für Bild-lastige Ordner).

**C5. Tastenkürzel.** Explorer-typisch: Entf (löschen, siehe A1), F2 (umbenennen), Strg+C/V/X
(kopieren/einfügen/ausschneiden — "Ausschneiden" existiert vermutlich noch nicht als Konzept,
nur Drag&Drop-Move), Strg+Klick/Shift-Klick-Mehrfachauswahl (falls nicht schon vorhanden), Alt+↑
(eine Ebene hoch). Kleine, aber in der Summe spürbare Tempo-Gewinne für Vielnutzer.

**C6. "Kopieren" als eigene Operation.** Aktuell gibt es (soweit ersichtlich) Verschieben
(Rename/Move), aber keine explizite "Datei duplizieren/kopieren"-Aktion im UI — ein häufiger
Explorer-Alltagsfall (Vorlage duplizieren, Datei parallel in zwei Ordnern ablegen wollen ohne
den B1-Duplikat-Fall künstlich zu erzeugen). Naheliegend als neue Route analog `move`, nur mit
`shutil.copy2` statt `os.rename`.

---

## D. Auswertung & Reporting

**D1. Speicherplatz-Dashboard.** Odoos native Pivot-/Graph-Views auf `int_filemanager.file`
(gefiltert `is_dir=False`) liefern "Speicherplatz nach Ordner/Dateityp/Zeitraum" praktisch
kostenlos — alle nötigen Felder (`size`, `folder_path`, `mtime`, Dateiendung aus `name`
ableitbar) existieren bereits, es fehlt nur eine `<pivot>`/`<graph>`-View-Definition plus
Menüpunkt. Kein Backend-Aufwand, reine View-Arbeit.

**D2. "Größte Dateien" / "Älteste, nie geöffnete Dateien"-Report.** Sortierte Liste nach `size`
absteigend bzw. nach `mtime`/`last_seen` aufsteigend — hilft beim gezielten Aufräumen großer
Netzlaufwerke, wieder nur eine View auf Bestandsfeldern.

**D3. Konsolidierter Aktivitätsbericht.** Aktuell existieren drei getrennte Log-Modelle
(`scan_log`, `share_log`, `write_journal`) plus der `mail.thread`-Chatter pro Datei — aber keine
gemeinsame "was ist heute alles passiert"-Übersicht. Eine einfache Dashboard-Ansicht (z.B. als
eigenes `ir.actions.client` mit ein paar aggregierten Zahlen: neue Dateien heute, Freigaben
diese Woche, offene Aktivitäten) würde die bereits vorhandenen Audit-Daten sichtbar statt nur
"im Hintergrund vorhanden" machen.

**D4. Ordnergrößen im Baum anzeigen.** Der `SearchPanel`-Ordnerbaum zeigt bereits
Trefferzähler (`enable_counters`) — eine zusätzliche, on-demand berechnete Summe der
Unterbaum-Größe (z.B. als Tooltip beim Hover, nicht bei jedem Render, wegen der bekannten
Skalierungsgrenzen des Baums bei tausenden Ordnern) wäre die Explorer-typische
"Rechtsklick → Eigenschaften → Größe"-Funktion.

---

## E. Zusammenarbeit

**E1. "Wird gerade bearbeitet von"-Anzeige.** WebDAV kennt LOCK/UNLOCK bereits intern
(`webdav_tokens.py`), aber das ist für den Nutzer unsichtbar. Ein sichtbares Icon/Badge in der
Liste ("🔒 in Bearbeitung von Anna, seit 14:02") würde parallele Bearbeitungskonflikte (siehe
A3) bereits präventiv vermeiden, nicht erst hinterher auffangen — reine UI-Ergänzung auf
bestehenden Lock-Daten.

**E2. Interne Einzelfreigabe ohne Gruppenmitgliedschaft.** `shared_partner_ids` deckt aktuell
nur externe Portal-Kontakte ab (Phase 5, Portal-Zweig der ACL-Regel). Für einen internen
Kollegen, der keine Mitgliedschaft in der Schutzordner-Gruppe hat, aber gezielt eine einzelne
Datei aus einem geschützten Ordner sehen soll, gibt es aktuell keinen Weg außer
Gruppenzuweisung (alles-oder-nichts pro Ordner). Eine "an internen Nutzer X freigeben"-Ergänzung
(analog dem Portal-Zweig, aber für `base.group_user`-Mitglieder) würde diese Lücke schließen —
sicherheitsrelevante ACL-Erweiterung, siehe Hinweis am Ende zu Sorgfalt bei solchen Änderungen.

**E3. Kommentar-/Erwähnungs-Notification bereits vorhanden, aber ungenutzt sichtbar machen.**
`mail.thread` (Baustein 2, bereits umgesetzt) bringt `@Erwähnung`-Benachrichtigungen nativ mit —
zu prüfen, ob das im Chatter-Panel schon nutzbar ist oder ob es zusätzlicher Sichtbarkeit
bedarf (z.B. ein Hinweis-Icon in der Liste bei ungelesenen Chatter-Nachrichten, analog zum
Meta-/Hash-Status-Icon-Muster).

---

## F. Versionierung — Backend fertig, UI bewusst zurückgestellt

**F1. Versionen-UI nachrüsten.** Laut `int_filemanager_ausbau.md` Phase 3 bewusst
zurückgestellt: Routen `/int_filemanager/versions` und `/int_filemanager/version_restore`
existieren, vollständig getestet, aber ohne Oberfläche. Ein "Versionen (n)"-Button/Dialog
(Liste mit Zeitstempel/Größe/Wer, "Wiederherstellen"-Aktion) ist der naheliegendste "fertig
zu Ende bringen"-Punkt im ganzen Katalog — reine UI-Arbeit auf fertigem, getestetem Backend.

**F2. Text-Diff zwischen Versionen.** Für Textformate (die über den Text-Editor-Dialog ohnehin
schon bearbeitbar sind) wäre ein Zeilen-Diff zwischen zwei Versionen (z.B. über eine simple
JS-Diff-Bibliothek oder Odoos eigenen `CodeEditor` mit Diff-Modus, falls vorhanden) ein
natürlicher Ausbau von F1 speziell für Textdateien.

**F3. Papierkorb + Versionierung zusammendenken.** Sobald A1 existiert, liegt nahe: eine
gelöschte Datei im Papierkorb behält ihre komplette Versionshistorie, "Wiederherstellen" stellt
den zuletzt aktiven Stand wieder her — kein zusätzliches Konzept, nur konsequente
Wiederverwendung von F1/A1 zusammen.

---

## G. Vorschau & Konvertierung

**G1. Office-Thumbnails.** Aktuell gibt es Thumbnails nur für Bilder/PDF (Seitenzahl statt
Rendering) — Word/Excel/PowerPoint zeigen nur ein generisches Icon. Die bereits vorhandene
ONLYOFFICE-Integration hat typischerweise eine Konvertierungs-API (Dokument → Bild/PDF), die
sich für eine Thumbnail-Generierung zweckentfremden ließe, statt ein komplett neues
Rendering-Werkzeug einzuführen — zu prüfen, ob die bestehende `onlyoffice_odoo`-Abhängigkeit das
bereits mitbringt.

**G2. PDF-Rendering-Vorschau statt nur Seitenzahl.** In der Phase-4-Umsetzung bewusst
zurückgestellt (fehlende `poppler-utils`/`PyMuPDF` im Docker-Image, bewusste Lizenzentscheidung
gegen PyMuPDF/AGPL). Mit `pdfplumber` (bereits für die Extraktion eingeführt, permissive Lizenz)
ließe sich ein echtes Seiten-Thumbnail rendern, ohne ein neues Lizenzrisiko einzugehen — ggf.
sogar mit wenig Zusatzaufwand, da `pdfplumber` bereits geladen wird.

**G3. Audio-Wellenform statt reinem Player-Icon.** Kosmetische Ergänzung zum bereits
vorhandenen Systray-Audio-Player — eher ein "nice to have" als ein echter Bedarf, hier nur der
Vollständigkeit halber genannt.

---

## H. Mobiler & externer Zugriff

**H1. Direkt-Foto-Upload vom Handy in einen Zielordner.** Der bestehende
`/int_filemanager/upload`-Endpunkt und die Portal-Templates decken laut PaperOffice-Recherche
"von unterwegs hochladen" bereits ab — zu prüfen, ob die UI auf einem Handy-Browser tatsächlich
brauchbar bedienbar ist (responsive Check) und ob ein direkter Kamera-Zugriff
(`<input type="file" capture="environment">`) für den häufigen Fall "Foto eines Belegs sofort
ablegen" bereits genutzt wird oder leicht ergänzbar wäre.

**H2. QR-Code am Arbeitsplatz/Aktenordner → Zielordner auf dem Handy.** Ein pro Ordner
generierbarer QR-Code (kodiert die Odoo-URL zu diesem `folder_path`), ausgedruckt z.B. an einem
physischen Aktenordner oder Arbeitsplatz — Scan öffnet direkt die passende Ansicht auf dem
Handy. Kleine Ergänzung (QR-Generierung ist in Odoo bereits an anderer Stelle vorhanden, z.B.
für Zahlungsreferenzen), praktischer Bezug zwischen physischer und digitaler Ablage.

**H3. "Im Explorer öffnen"-Link für LAN-Clients.** Für Mitarbeiter, die (noch) direkten
SMB-Zugriff auf denselben Server haben, ein Kontextmenü-Eintrag, der einen `file://`- oder
`\\server\share\...`-Pfad in die Zwischenablage kopiert oder als Link anbietet — Brücke
zwischen Web-UI und nativem Explorer für den Übergang, kein Ersatz für das eigentliche Ziel
"weg vom Explorer", aber ein pragmatischer Zwischenschritt.

---

## I. Automatisierung

**I1. Ordner-Regeln (Auto-Tag/Auto-Status bei Ablage).** Die extraktionsmuster-Cron-Architektur
(Pending-State + Batch-Cron) ließe sich verallgemeinern: "jede neue Datei unter
`Eingang-Scan/Buchhaltung/` bekommt automatisch Tag X und Status Y" — spart manuelles
Nachsortieren für vorhersehbar strukturierte Eingangsordner (siehe Baustein 0,
Scan-Eingangsordner-Konzept in der PaperOffice-Recherche, hier nur die logische Fortsetzung:
nicht nur automatisch indexieren, auch automatisch kategorisieren).

**I2. Aufbewahrungsregeln für alte Versionen/Papierkorb.** Ergänzt A1/F1: konfigurierbare
Cron-Regeln ("Papierkorb-Einträge älter als 90 Tage endgültig löschen", "nur die letzten N
Versionen pro Datei behalten") — nutzt dieselbe Cron-Infrastruktur, die für Version-Pruning
laut `int_filemanager_ausbau.md` bereits existiert, nur konfigurierbar statt fest verdrahtet.

**I3. Benachrichtigung bei neuer Datei in abonniertem Ordner.** `mail.thread`/Follower-Mechanik
ist bereits auf Dateiebene aktiv — ein Ordner selbst ist aber kein eigener Datensatz mit
Followern (Ordner sind reine `is_dir=True`-Zeilen in `int_filemanager.file`, könnten aber
genauso `mail.thread` erben und damit "abonnierbar" werden). Eine neue Datei im Ordner müsste
dann `message_post()` auf den Elternordner auslösen — nutzt exakt dasselbe Muster wie Baustein 2,
nur eine Ebene höher in der Hierarchie angewendet.

**I4. Regelbasierte Ablauf-/Erinnerungs-Workflows.** Die bereits vorhandene
`mail.activity.mixin`-Integration erlaubt "Aktivität planen" manuell — ein Cron, der z.B. bei
Erreichen eines `extracted_value`-Ablaufdatums (Vertragsende, Garantieablauf, falls über ein
Extraktionsmuster erfasst) automatisch eine Aktivität anlegt, wäre eine direkte Fortsetzung der
bereits vorhandenen selbstdefinierten Extraktionsfelder.

---

## J. Sicherheit bei Freigaben

**J1. Passwortschutz für externe Links.** `share_token` + `share_expires_at` decken Ablauf ab,
aber nicht "nur mit Kennwort abrufbar" — für sensible Einzeldokumente eine sinnvolle Ergänzung
(zusätzliches optionales Feld `share_password_hash`, Prüfung in `share_download()`).

**J2. Download-Zähler/-Limit für externe Links.** `share_log` protokolliert bereits jeden
Abruf — ein Limit ("Link erlischt nach 3 Downloads") wäre eine kleine Zusatzprüfung auf
bestehenden Log-Daten, kein neues Konzept.

**J3. Wasserzeichen bei externem PDF-Download.** Für Dokumente, die extern geteilt werden,
optional ein "Vertraulich — geteilt mit {Partner} am {Datum}"-Wasserzeichen ins ausgelieferte
PDF einfügen (z.B. via `pypdf`, bereits im Stack vorhanden über `pdfplumber`/PDF-Tooling) —
eher ein Enterprise-DMS-typisches Feature, hier der Vollständigkeit halber genannt, vermutlich
niedrigere Priorität als J1/J2.

---

## K. Schnittstellen & Integration

**K1. Dokumentierte REST/JSON-API für externe Systeme.** Die bestehenden
`/int_filemanager/*`-Routen sind aktuell intern für die eigene UI gedacht (Odoo-Session-Auth) —
eine separate, API-Key-basierte Außenschnittstelle (z.B. für ein externes Buchhaltungstool, das
Rechnungen automatisch ablegen will, oder ein Automatisierungswerkzeug wie n8n) wäre ein
größerer, eigenständiger Baustein: eigene Auth (nicht Session-Cookie), eigene Rate-Begrenzung,
eigene Doku. Nur sinnvoll, wenn es einen konkreten externen Konsumenten gibt — nicht auf
Vorrat bauen.

**K2. Webhook bei bestimmten Ereignissen.** Ergänzend zu K1: "bei neuer Datei unter Pfad X /
bei Statuswechsel auf Y einen HTTP-Callback auslösen" — nutzt dieselben Trigger-Punkte wie I1/I3
(Watcher-Events, Status-Änderung), nur mit einem HTTP-POST statt einer internen Odoo-Aktion als
Ziel.

---

## L. Bereits an anderer Stelle geplant — hier nur referenziert, nicht dupliziert

- ACL-Performance-Fix bei großem Datenbestand: `archiv/int_filemanager_acl_perf_plan.md`.
- Abschluss der nativen-ListView-Migration (alten UI-Pfad löschen): `int_filemanager_native_ui.md`,
  "Empfohlene Reihenfolge".
- CIFS-Reconciliation-Scan-Optimierung (Laufzeit unabhängig von tatsächlicher Änderungsmenge):
  `archiv/int_filemanager_external_change_watcher_regression.md`.
- Selbstdefinierte Extraktionsfelder (Phase A–C): bereits vollständig umgesetzt
  (`int_filemanager_ocr_selbstdefinierte_felder.md`).

---

## Priorisierungsvorschlag (grobe Einschätzung, keine Festlegung)

**Kleine, schnell wirksame Ergänzungen auf vorhandener Infrastruktur** (D1/D2 Dashboards, B1
Duplikat-Finder, F1 Versionen-UI, C1 Adressleiste, E1 Bearbeitungs-Anzeige): jeweils wenig
Backend-Aufwand, da die Daten größtenteils schon vorliegen — reine View-/UI-Arbeit.

**Ein echter, spürbarer Sicherheitsgewinn:** A1 Papierkorb — der auffälligste Fund dieser
Analyse, weil er eine reale, bisher ungedeckte Lücke schließt (unwiderrufliches Löschen in
einem von echten Kollegen im Alltag genutzten System) und Backend-technisch überschaubar ist
(neue Route + ein leichtes Modell + Cron, kein neues Grundkonzept).

**Mittlerer Aufwand mit hohem Alltagsnutzen:** B3 Office-Volltextsuche, I1 Ordner-Regeln, C3
Favoriten — erweitern bestehende Pipelines (Extraktion, Auto-Tagging-Vorstufe, lokale
UI-Zustände) um einen zusätzlichen Anwendungsfall, statt etwas grundlegend Neues einzuführen.

**Größere, eigenständige Vorhaben:** C2 Splitview, K1/K2 externe API, sollten nur bei
konkretem Bedarf (nicht auf Vorrat) angegangen werden — beides folgt aber, wenn gebraucht,
bereits etablierten Mustern (natives `ListView` bzw. Odoo-eigene API-Key-Mechanismen).

**Sicherheitsrelevant, nicht ohne Rückfrage umsetzen** (wie schon bei den verworfenen
Bausteinen 5/6 der PaperOffice-Recherche festgehalten): E2 interne Einzelfreigabe ohne
Gruppenmitgliedschaft — erweitert die ACL-Semantik, verdient dieselbe Sorgfalt (Multi-Kontext-
Selbsttest, Review-Runden) wie die ursprüngliche Schutzordner-Implementierung.
