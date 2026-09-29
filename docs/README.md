# docs/ – Wegweiser

Stand 2026-09-28. Lebende Dokumente oben, alles Übrige darunter. Nichts wurde gelöscht; was überholt ist, liegt in
[`archiv/`](archiv/) und in der Git-Historie.

## int_filemanager 2 (lebend)

| Dokument | Wofür |
|---|---|
| [`int_filemanager_v2_uebergabe_2026-09-26.md`](int_filemanager_v2_uebergabe_2026-09-26.md) | **Einstieg:** Stand, Entscheidungen, nächste Schritte, Testumgebung |
| [`int_filemanager_v2_kern_2026-09-26.md`](int_filemanager_v2_kern_2026-09-26.md) | Kurzfassung des Konzepts |
| [`int_filemanager_v2_konzept_2026-09-26.md`](int_filemanager_v2_konzept_2026-09-26.md) | Leitfaden mit allen Einzelheiten (gilt bei Widerspruch) |
| [`int_filemanager_v2_schritt4_plan_2026-09-28.md`](int_filemanager_v2_schritt4_plan_2026-09-28.md) | Plan der Oberfläche (Schritt 4) |
| [`int_filemanager_v2_werterkennung_plan_2026-09-29.md`](int_filemanager_v2_werterkennung_plan_2026-09-29.md) | Plan der Werterkennung (Schritt 5, Punkt 1) mit Befund Odoo 19 und Paperless-ngx |
| [`int_filemanager_v2_werterkennung_oberflaeche_konzept_2026-09-29.md`](int_filemanager_v2_werterkennung_oberflaeche_konzept_2026-09-29.md) | Konzept Prüf-Fenster mit Kasten-Auswahl (U1–U9 und N1–N9 entschieden, Freigabe offen): Vorbilder PaperOffice/Paperless-ngx/Odoo, geprüfte Odoo-Bausteine, Nachtrag PaperOffice AI, Scheiben U-1…U-10 |
| [`review/konzept_codepruefung_2026-09-26.md`](review/konzept_codepruefung_2026-09-26.md) | Code-Prüfung des Konzepts (194 Behauptungen) |
| [`odoo_konventionen_2026-09-26.md`](odoo_konventionen_2026-09-26.md) | Code-Konventionen für neuen Code |
| [`int_filemanager_konzept_db_vorrang_2026-09-24.md`](int_filemanager_konzept_db_vorrang_2026-09-24.md) | Hintergrund: Abschnitte 19 und 20 (Live-Prüfungen auf Tower) |

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

- `int_filemanager_native_ui.md` – v1-Oberfläche (Status und Punkte 1–25)
- `int_filemanager_ausbau.md` – v1-Backend-Phasen 1–5
- `int_filemanager_papierkorb_konzept.md` – v1-Papierkorb
- `int_filemanager_paperoffice_recherche.md` – PaperOffice-Recherche
- `int_filemanager_feature_ideen_2026-09-21.md`, `erp-odoo-vs-cloudreve-vergleich-2026-09-21.md` – Ideen und Vergleich

## Andere Themen

- [`erp/`](erp/) – Reverse Engineering des Legacy-ERP und Vergleich mit Odoo (`legacy-schema/` mit den DFM-Formularen)
- [`sonstiges/`](sonstiges/) – Liedanzeige als Odoo-Modul
- [`prototypes/fm2/`](prototypes/fm2/) – Prototypen von int_filemanager 2

## Archiv

- [`archiv/`](archiv/): v1-Watcher-, Scan- und ACL-Dokumente sowie die frühe Explorer-Roadmap, alle von v2 ersetzt.
- [`archiv/recherchen-odoo-bausteine/`](archiv/recherchen-odoo-bausteine/): 18 Recherchen zu nativen Odoo-Bausteinen
  (Navigation, Listenansicht, Bilder, PDF, Papierkorb, `core/`), für das v1-Modul geschrieben. Nachschlagewerk, nicht Teil
  des v2-Konzepts.
