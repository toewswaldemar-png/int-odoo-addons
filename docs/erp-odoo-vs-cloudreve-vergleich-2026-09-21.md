# Odoo vs. Cloudreve — detaillierter Vergleich

Stand 2026-09-21. Ergänzt die bisherige Odoo-Recherche dieser Session
([`erp-odoo-plattform-analyse-2026-09-21.md`](erp-odoo-plattform-analyse-2026-09-21.md),
[`int_filemanager_feature_ideen_2026-09-21.md`](int_filemanager_feature_ideen_2026-09-21.md),
[`int_filemanager_odoo_native_integration_2026-09-21.md`](int_filemanager_odoo_native_integration_2026-09-21.md))
um einen Vergleich mit **Cloudreve**, der zweiten, unabhängig vom `int-odoo-addons`-Repo laufenden
Eigenentwicklung/Anpassung des Nutzers (`cloudreve-custom`, siehe dortiges
`assets/UI_CUSTOMIZATIONS.md`). Reine Analyse, keine Entscheidung vorweggenommen.

**Methodik:** direkte Codedurchsicht des `cloudreve`-Repos in dieser Session (`go.mod`, `README.md`,
`ent/schema/`, `pkg/`) statt Web-Recherche — Cloudreve liegt lokal vor, die Fakten unten sind damit
**am tatsächlichen Code dieser konkreten Installation verifiziert**, nicht nur aus Dokumentation
übernommen. Für Odoo gilt weiterhin der Stand aus den drei oben verlinkten Dokumenten dieser
Session (dort mit eigenen Quellenangaben).

---

## 1. Kategorie-Einordnung — kein Vergleich auf Augenhöhe, aber ein berechtigter Vergleich

Odoo ist eine **vollständige ERP-Suite** (Verkauf, Einkauf, Fertigung, Buchhaltung, Reparatur,
Personal, …), Dateiverwaltung ist dort bestenfalls eine Funktion unter vielen — in diesem konkreten
Fall sogar eine komplett selbst gebaute (`int_filemanager`), weil Odoos eigene native Lösung
(Documents-App) Enterprise-only ist. Cloudreve dagegen ist laut eigener Beschreibung ein
**"Self-hosted file management system with multi-cloud support"** — ein einziges, klar
umrissenes Werkzeug, das genau eine Aufgabe sehr gründlich löst.

Der Vergleich ist trotzdem berechtigt und praktisch relevant, weil **beide Systeme beim Nutzer
real für sich beanspruchen, Dateien zu verwalten** — Odoo/`int_filemanager` für ein
Firmenverzeichnis mit Geschäftsbezug, Cloudreve als eigenständiger Cloud-Speicher. Der sinnvolle
Vergleich ist daher nicht "Odoo als Ganzes vs. Cloudreve", sondern **"Odoos
Dateiverwaltungs-Fähigkeiten (nativ + `int_filemanager`) vs. Cloudreve als dediziertes
Werkzeug für exakt dasselbe Teilproblem"** — genau in diesem Rahmen ist der Rest dieses Dokuments
aufgebaut.

---

## 2. Architektur & Stack

| | Odoo (+`int_filemanager`) | Cloudreve |
|---|---|---|
| Backend | Python, monolithischer WSGI-Server, PostgreSQL, eigenes ORM (`models.Model`) | Go, `Gin`-Webframework, `ent` (typsicheres Go-ORM/Code-Generator), MySQL/PostgreSQL/SQLite |
| Frontend | OWL (Odoos eigenes Reaktivitäts-Framework, serverseitig gerenderte Views + Web-Components) | React + Redux + Material-UI, vollständige SPA |
| Datenmodell für Dateien | `int_filemanager.file`: **ein** ORM-Datensatz pro Datei/Ordner, Platte ist Wahrheit, Index wird nachgeführt (Watcher/Scan/Reconciliation) | `ent`-Schema mit eigenen Entitäten (`entity`, `fsevent`, `metadata`, `storagepolicy`, `node`, …) — Datenbank ist die primäre Wahrheit, Speicher-Backends sind austauschbare Ziele |
| Lizenz | Odoo Community: LGPL-3 (Kern), Enterprise: proprietär/Abo | GPL v3, **vollständig frei, kein Feature hinter einer Bezahlschranke** |
| Deployment hier | Docker auf Unraid (HM-SRV/Tower) | eigener Build-Prozess (`.build/build-assets-windows.ps1`), ebenfalls self-hosted |

**Grundlegender Architekturunterschied:** `int_filemanager` behandelt ein **bestehendes
Dateisystem** als Wahrheit und bildet es in Odoo ab (deshalb der ganze Aufwand mit Hash-Scan,
Watcher, Reconciliation, Rename-Erkennung — siehe `int_filemanager_ausbau.md`, Phase 1). Cloudreve
dreht das um: **die Datenbank ist die Wahrheit**, das eigentliche Speicher-Backend (lokal, S3,
OneDrive, …) ist nur ein austauschbares Ziel, das Cloudreve selbst vollständig kontrolliert
(`storagepolicy`-Entität). Das ist der Grund, warum Cloudreve viele der in `int_filemanager`
aufwendig nachgebauten Probleme (Fremdänderungen erkennen, Rename-Identität über Hash) strukturell
gar nicht erst hat — bei Cloudreve ändert sich eine Datei nie "von außen", jede Änderung läuft
durch Cloudreve selbst.

---

## 3. Speicher-Backends — der größte strukturelle Unterschied

`int_filemanager` (und Odoo allgemein) kennt nur **ein** Backend: einen lokalen Verzeichnispfad auf
dem Server-Dateisystem (`int_filemanager.root_path`). Cloudreve unterstützt laut eigenem README
**nativ**: Lokal, Remote-Node, OneDrive, S3-kompatible APIs, Qiniu Kodo, Aliyun OSS, Tencent COS,
Huawei Cloud OBS, Kingsoft KS3, Upyun — bestätigt durch die tatsächlichen SDK-Abhängigkeiten in
`go.mod` (`aws-sdk-go`, `aliyun-oss-go-sdk-v2`, `huaweicloud-obs`, …). Zusätzlich: **Direktübertragung
Client↔Speicher-Backend** ("Upload/Download in directly transmission from client to storage
providers") — Cloudreve selbst muss die Dateibytes bei Cloud-Backends gar nicht durchleiten, nur
signierte URLs ausstellen. `int_filemanager` leitet dagegen jeden Download/Upload durch den
Odoo-Prozess selbst (`controllers/main.py`), inklusive des dafür extra gebauten
Range-Request-Streamings (`http.Stream`, siehe `int_filemanager_native_ui.md`, Punkt 11).

**Einordnung:** für den aktuellen Einsatzzweck (ein Firmenverzeichnis auf einem Server im LAN)
ist das kein praktischer Nachteil — aber es zeigt, dass `int_filemanager` architektonisch auf genau
einen Anwendungsfall zugeschnitten ist, während Cloudreve von Grund auf für Cloud-/Multi-Backend-
Szenarien gebaut wurde. Sollte je ein Cloud-Backend (S3 o.ä.) für Firmendaten relevant werden, wäre
das in `int_filemanager` ein grundlegender Umbau, in Cloudreve eine reine Konfigurationsänderung.

---

## 4. Feature-für-Feature

| Bereich | `int_filemanager` (Odoo) | Cloudreve | Einschätzung |
|---|---|---|---|
| **Papierkorb/Soft-Delete** | **fehlt** (`shutil.rmtree`/`os.remove`, siehe eigener Fund in `int_filemanager_feature_ideen_2026-09-21.md`, Punkt A1) | **architektonisch fest verankert**: `CommonMixin` (`ent/schema/common.go`) implementiert Soft-Delete (`deleted_at`-Feld + Interceptor/Mutator) für **praktisch jede** Entität im Schema, nicht nur Dateien | klarer Cloudreve-Vorteil, direkt bestätigt am Code — stärkt die bereits vorhandene A1-Empfehlung zusätzlich |
| **WebDAV** | nur **Einzeldatei-Token**-WebDAV für lokales Word/Excel-Öffnen (`webdav.py`, `webdav_tokens.py`), kein vollständiges WebDAV-Filesystem-Mounting | vollständiges WebDAV **über alle Speicher-Backends hinweg** (`pkg/webdav`) — ein WebDAV-Client kann den kompletten Cloudreve-Baum mounten, nicht nur eine Datei | Cloudreve deutlich umfangreicher; `int_filemanager`s WebDAV ist bewusst schmal (nur Word/Excel-Brücke), kein Ersatz für echtes Netzlaufwerk-Mounting |
| **Office-Bearbeitung im Browser** | ONLYOFFICE-spezifisch verdrahtet (`onlyoffice_odoo`-Abhängigkeit, `open_editor()` synthetisiert `ir.attachment`) | **WOPI-Protokoll** (`pkg/wopi`, `middleware/wopi.go`) — der offene Standard, den Microsoft Office Online, Collabora **und** ONLYOFFICE alle unterstützen; Cloudreve ist damit nicht an einen Anbieter gebunden | Cloudreve strukturell flexibler (Anbieterwechsel ohne Codeänderung); `int_filemanager` funktioniert aber genauso gut, solange ONLYOFFICE die gewählte Lösung bleibt |
| **Authentifizierung** | Odoo-Login (Passwort, ggf. 2FA je nach Odoo-Konfiguration) | zusätzlich **WebAuthn/Passkey** nativ (`go-webauthn`, `ent/passkey`) | Cloudreve moderner in diesem Punkt |
| **Volltextsuche/OCR** | **vorhanden**: OCR-Fallback (Tesseract), AcroForm-Formularfelder, selbstdefinierte Extraktionsmuster mit PDF-Highlighting (siehe `int_filemanager_ocr_selbstdefinierte_felder.md`) | **kein Content-OCR** — Suche läuft laut Code (`pkg/searcher`, kein OCR/Fulltext-Treffer) nur über Dateiname/Metadaten/Tags, nicht über den eigentlichen Dokumentinhalt | klarer `int_filemanager`-Vorteil — hier hat die eigene Entwicklung Cloudreve tatsächlich überholt |
| **Medienmetadaten** | Bild/PDF/Audio (Pillow/PyPDF2/mutagen), kein Video | Bild/Audio/Video-Metadaten (`pkg/mediameta`, EXIF-Bibliotheken für JPEG/PNG/TIFF/HEIC in `go.mod`) | Cloudreve deckt zusätzlich Video-Metadaten ab |
| **Downloads im Hintergrund** | **kein Äquivalent** | Aria2/qBittorrent-Integration, mehrere Download-Knoten zur Lastverteilung (`pkg/downloader`, `pkg/balancer`) | reines Cloudreve-Alleinstellungsmerkmal, für ein Firmenverzeichnis ohnehin kaum relevant |
| **Diagramm-/Zeicheneditor** | nicht vorhanden | **Excalidraw** direkt integriert (`Viewers/Excalidraw`) | Cloudreve-Extra, kein `int_filemanager`-Äquivalent |
| **Archiv-Handling** | ZIP durchsuchen/einzelne Einträge extrahieren (`zip_utils.py`) | Komprimieren **und** Extrahieren (auch 7z, `bodgit/sevenzip` in `go.mod`), Batch-Download | Cloudreve etwas umfangreicher (auch Komprimieren, mehr Formate) |
| **Freigaben** | intern (Portal-Kontakte) + extern (anonymer Link mit Ablauf), Audit-Log (`share_log`) | Freigabelinks mit Ablaufdatum für Dateien **und** Ordner | funktional ähnlich, Cloudreve zusätzlich auf Ordnerebene |
| **Versionierung** | vorhanden, atomarer Schreibvorgang mit Session-Lock (`write_service.py`), Backend fertig, UI zurückgestellt (siehe Feature-Katalog, F1) | nicht im Kern-Feature-Set des READMEs genannt, nicht weiter geprüft in dieser Session | offen, nicht abschließend verglichen |
| **Multi-Nutzer-Modell** | Odoo-Gruppen + Schutzordner-ACL (`ir.rule`, feingranular, an Ordnerpfade gebunden) | eigenes Nutzer-/Gruppen-Modell mit Speicher-Kontingenten (`ent/group`, `ent/user`), auf Selbstregistrierung/Multi-Tenant ausgelegt | unterschiedliche Zielgruppen: `int_filemanager` für feste interne Belegschaft mit Organisationsbezug, Cloudreve eher für "viele unabhängige Nutzerkonten" (auch öffentlicher SaaS-artiger Betrieb denkbar) |
| **Mobil/PWA** | kein PWA, responsive-Status ungeklärt (siehe Feature-Katalog, H1) | **PWA nativ** laut README | Cloudreve-Vorteil, deckt sich mit der bereits im Feature-Katalog offen gelassenen Frage bei `int_filemanager` |
| **Geschäftsdatensatz-Verknüpfung** | `res_reference` + `IntFilemanagerLinkableMixin` — Dateien direkt an Kontakte/Reparaturaufträge/beliebige Odoo-Modelle koppelbar, Chatter/Aktivitäten (`mail.thread`), Ampel-Status-Workflow | **kein Konzept dafür** — Cloudreve kennt Dateien, Ordner, Nutzer, Freigaben; keine Verknüpfung zu einem "Kunden", "Auftrag" oder Geschäftsvorgang | fundamentaler `int_filemanager`-Vorteil, der aus der Odoo-Einbettung selbst kommt — genau der Teil, den Cloudreve grundsätzlich nicht leisten kann, unabhängig vom Funktionsumfang |

---

## 5. Lizenz & Kosten

Cloudreve ist **vollständig** GPL v3, jede im README genannte Funktion ist frei nutzbar — es gibt
keine Enterprise-Variante, keine bezahlpflichtige Funktionsstufe. Odoo dagegen hat, wie in
`erp-odoo-plattform-analyse-2026-09-21.md` (Abschnitt 2) bereits detailliert hergeleitet, eine
harte Trennung zwischen kostenloser Community Edition und kostenpflichtiger Enterprise Edition,
wobei ausgerechnet die native Dokumentenverwaltung (Documents-App) zu den Enterprise-exklusiven
Apps zählt — der eigentliche Grund, warum `int_filemanager` überhaupt als Eigenentwicklung
existiert. Wirtschaftlich betrachtet hat der Nutzer mit `int_filemanager` faktisch selbst
nachgebaut, was Cloudreve als fertiges, kostenloses Produkt vollständig mitbringt (abzüglich der
in Abschnitt 4 genannten OCR-Lücke bei Cloudreve und der Geschäftsdatensatz-Anbindung).

---

## 6. Wo welches System klar überlegen ist

**Cloudreve klar überlegen:** Papierkorb (architektonisch fest verankert, nicht nachgerüstet),
Multi-Cloud-Speicher-Flexibilität, vollständiges WebDAV, WOPI-Standardprotokoll statt
Anbieterbindung, WebAuthn/Passkey, PWA/Mobil, Hintergrund-Downloads, Diagramm-Editor — überall
dort, wo es um **reine, generische Dateiverwaltung** geht, ist Cloudreve das ausgereiftere,
gezielter dafür gebaute Werkzeug.

**`int_filemanager`/Odoo klar überlegen:** Volltextsuche mit OCR und selbstdefinierter
Werterkennung (Cloudreve hat das schlicht nicht), vor allem aber die **Einbettung in einen echten
Geschäftskontext** — eine Datei ist nicht nur eine Datei, sondern kann an einen Kunden, einen
Reparaturauftrag, eine Aktivität mit Frist gekoppelt sein, samt Audit-Trail, ACL entlang der
Organisationsstruktur und (potenziell, siehe `int_filemanager_odoo_native_integration_2026-09-21.md`)
weiteren Odoo-Apps. Das ist kein Funktionsumfang, den Cloudreve grundsätzlich nachrüsten könnte,
ohne selbst zu einem ERP zu werden.

---

## 7. Einordnung für die eigene Infrastruktur

Die beiden Systeme lösen **unterschiedliche Probleme**, auch wenn sie sich auf den ersten Blick
überschneiden:

- **`int_filemanager`** beantwortet "wo liegt die Datei, die zu diesem Kunden/Reparaturauftrag/
  Vorgang gehört, und wer aus der Belegschaft darf sie sehen" — Firmenverzeichnis mit
  Geschäftsbezug.
- **Cloudreve** beantwortet "wie bekomme ich eine Datei zuverlässig, plattformübergreifend, mit
  ordentlichem Papierkorb und ggf. Cloud-Anbindung gespeichert und geteilt" — allgemeiner,
  Geschäftskontext-loser Cloud-Speicher.

**Eine echte Überschneidung besteht nur dort, wo beide Systeme dieselbe rohe Aufgabe lösen**
(Datei ablegen, teilen, wiederfinden) — nicht bei der geschäftsbezogenen Funktionalität, die nur
`int_filemanager` hat. Ob beide Systeme parallel sinnvoll sind (klare Trennung: Geschäftsdokumente
in Odoo, alles andere in Cloudreve) oder ob sich Aufgaben unnötig doppeln, ist eine
Nutzungsfragen-Entscheidung, die hier nicht beantwortet wird — die Grundlage dafür liefert dieser
Vergleich.

**Konkrete Übernahme-Idee für `int_filemanager`, direkt aus diesem Vergleich abgeleitet:** der in
`int_filemanager_feature_ideen_2026-09-21.md` (Punkt A1) bereits vorgeschlagene Papierkorb sollte
sich am Cloudreve-Muster orientieren, nicht am blanken "Datei in Unterordner verschieben"-Ansatz —
Cloudreves Lösung ist ein **generischer Soft-Delete-Mixin auf ORM-Ebene** (`deleted_at`-Feld,
automatisch gefiltert, außer explizit eingeschlossen). Da `int_filemanager.file` bereits ein
vollwertiges Odoo-Modell ist, wäre ein äquivalenter Ansatz **nativ in Odoo nachbaubar**: ein
`active`/`deleted_at`-Feld auf `int_filemanager.file` selbst (Odoos eigenes `active`-Feld-Konzept
blendet standardmäßig aus Suchen aus, genau wie Cloudreves Interceptor) statt eines separaten
Dateisystem-Verschiebens in einen `.trash`-Unterordner — eine sauberere, direkt von Cloudreve
inspirierte Alternative zum ursprünglich skizzierten Ansatz, die die Platte gar nicht anfassen
müsste, solange die Datei physisch liegen bleibt und nur der Index sie als gelöscht markiert.

---

## Verweis

Zusammen mit `erp-odoo-plattform-analyse-2026-09-21.md` (Odoo allgemein),
`int_filemanager_feature_ideen_2026-09-21.md` (Feature-Ideen) und
`int_filemanager_odoo_native_integration_2026-09-21.md` (native Odoo-Verzahnung) ergibt sich aus
diesem Dokument ein vollständigeres Bild: was Odoo/`int_filemanager` bereits kann, was nativ noch
näher an Odoo heranrücken könnte, und — hier neu — wo ein bereits vorhandenes, komplett anderes
System (Cloudreve) zeigt, wie derselbe Problemraum architektonisch anders und in Teilen bereits
besser gelöst ist.
