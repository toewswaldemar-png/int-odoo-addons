# docs/ – Wegweiser

Stand 2026-10-02. Lebende Dokumente oben, alles Übrige darunter. Was überholt ist, liegt in
[`archiv/`](archiv/) und in der Git-Historie (Tag `docs-vor-aufraeumen-2026-10-02`).

## int_filemanager 2 (lebend)

| Dokument | Wofür |
|---|---|
| [`int_filemanager_v2_stand.md`](int_filemanager_v2_stand.md) | **Einstieg:** Stand, nächste Schritte, bekannte Mängel, Arbeitsweise, Testumgebung |
| [`int_filemanager_v2_entscheidungen.md`](int_filemanager_v2_entscheidungen.md) | Warum so, was verworfen wurde, Odoo-19-Fallen |
| [`int_filemanager_v2_kern_2026-09-26.md`](int_filemanager_v2_kern_2026-09-26.md) | Grundregeln, Aufbau, Reihenfolge mit Abnahmekriterien |
| [`int_filemanager_paperoffice_ideenkatalog_2026-10-01.md`](int_filemanager_paperoffice_ideenkatalog_2026-10-01.md) | Backlog: Ideen A1–H6 aus PaperOffice Classic mit Odoo-Weg, Aufwand, Einordnung, offenen Entscheidungen |
| [`odoo_regeln/`](odoo_regeln/) | Odoo-19-Regeln: Coding und Git Guidelines mit Hausregeln, Developer Reference (Einstieg: `odoo_regeln/odoo_regeln_index_2026-10-02.md`) |
| [`pruefautomatik_2026-10-02.md`](pruefautomatik_2026-10-02.md) | pre-commit, `test_lint`, odoo-ls: Aufruf und Verifikationsstand |
| [`int_filemanager_konzept_db_vorrang_2026-09-24.md`](int_filemanager_konzept_db_vorrang_2026-09-24.md) | Hintergrund: Abschnitte 19 und 20 (Live-Prüfungen auf Tower) |

Konzept, Pläne, Übergabe-Verlauf, Messungen und Prüfberichte der Zeit bis 2026-10-02 stehen im Git-Tag
`docs-vor-aufraeumen-2026-10-02` (`git show docs-vor-aufraeumen-2026-10-02:docs/<Datei>`).

## Betrieb und Themen, die in v2 noch kommen

| Dokument | Wofür |
|---|---|
| [`int_filemanager_onlyoffice_domain_tls_fix_2026-09-22.md`](int_filemanager_onlyoffice_domain_tls_fix_2026-09-22.md) | ONLYOFFICE: DNS, Zertifikat, Host-Header |
| [`int_filemanager_onlyoffice_ladezeit_untersuchung_2026-09-22.md`](int_filemanager_onlyoffice_ladezeit_untersuchung_2026-09-22.md) | Warum DOCX langsam laden (Schritt 6, Office) |
| [`int_filemanager_lokal_oeffnen_warnungen_2026-09-23.md`](int_filemanager_lokal_oeffnen_warnungen_2026-09-23.md) | "Lokal öffnen" ohne Zertifikatswarnungen (Schritt 6) |
| [`int_filemanager_ocr_selbstdefinierte_felder.md`](int_filemanager_ocr_selbstdefinierte_felder.md) | Extraktionsfelder und PDF-Hervorhebung (Schritt 5) |
| [`meshcentral-zugang.md`](meshcentral-zugang.md) | MeshCentral-Zugang |

## Bleiben bis Schritt 8 (v1-Code verweist darauf)

Der v1-Code zitiert diese Dokumente in Kommentaren. Sie wandern ins Archiv, wenn der v1-Code mit Schritt 8 gelöscht wird
(dort auch das Zusammenführen der Ideen-Dokumente):

- `int_filemanager_ausbau.md` – v1-Backend-Phasen 1–5
- `int_filemanager_papierkorb_konzept.md` – v1-Papierkorb
- `int_filemanager_paperoffice_recherche.md` – PaperOffice-Recherche
- `int_filemanager_feature_ideen_2026-09-21.md`, `erp-odoo-vs-cloudreve-vergleich-2026-09-21.md` – Ideen und Vergleich

## Andere Themen

- [`erp/`](erp/) – Reverse Engineering des Legacy-ERP und Vergleich mit Odoo (`legacy-schema/` mit den DFM-Formularen)
- [`sonstiges/`](sonstiges/) – Liedanzeige als Odoo-Modul
- [`prototypes/fm2/`](prototypes/fm2/) – Prototypen von int_filemanager 2
- [`prototypes/werterkennung/`](prototypes/werterkennung/) – Prototyp-Skripte der Werterkennung (ohne persönliche Daten)

## Archiv

- [`archiv/`](archiv/): v1-Watcher-, Scan- und ACL-Dokumente sowie die frühe Explorer-Roadmap, alle von v2 ersetzt; dazu [`int_filemanager_native_ui.md`](archiv/int_filemanager_native_ui.md) (v1-Oberfläche, Status und Punkte 1–25, seit 2026-09-30 im Archiv – der v1-Code verweist in Kommentaren darauf).
- [`archiv/recherchen-odoo-bausteine/`](archiv/recherchen-odoo-bausteine/): 18 Recherchen zu nativen Odoo-Bausteinen
  (Navigation, Listenansicht, Bilder, PDF, Papierkorb, `core/`), für das v1-Modul geschrieben. Nachschlagewerk, nicht Teil
  des v2-Konzepts.
