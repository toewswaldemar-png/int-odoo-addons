# int_filemanager: Abgleich mit den Odoo-19-Vorgaben (Stand 23.10.2026)

Ergebnis der Prüfung: `int_filemanager` ist fachlich und thematisch nach Odoo aufgebaut; die Abweichungen sind überwiegend bewusst und begründet. Geprüft mit Stichproben (Manifest, Sicherheit, Modelle, Ansichten, Controller, JS-Struktur). Nicht gelaufen bei der Prüfung selbst: `check.sh`, Browser. Maßstab: `docs/odoo19_reference/` und `docs/odoo/`.

## Erledigt

- [x] **Fabric minifiziert.** `static/lib/fabric/fabric.min.js` ersetzt durch die lesbare Fassung derselben Version (`fabric.js`, Fabric 7.4.0, Byte für Byte `dist/index.js` des npm-Pakets). Regel: `coding_guidelines.md:990`, „Never add minified Javascript Libraries“. Commit `29604cc`. Offen dazu nur die Probe im Browser (Bild öffnen, „Bearbeiten“, zeichnen, speichern).
- [x] **Zu große Modelle.** Hilfen nach `tools/` (`files.py`, `programs.py`, `NAME_TRIES` in `clash.py`), dazu `int_filemanager_text_ocr.py`, `int_filemanager_document_storage.py`, `int_filemanager_document_rendition.py`. `int_filemanager_text.py` 1560 → 897 Zeilen, `int_filemanager_document.py` 1209 → 590. Commits `8ef0dab`, `1e85df6`, `3d81138`, `ffbe381`; 994 Tests grün am Tower. Die frühere Aussage „der Core verteilt große Modelle auf Dateien“ war zu stark: der Core hat Modelle bis 7500 Zeilen in einer Datei, die Aufteilung per `_inherit` ist aber belegt (9 Fälle, `<modell>_<thema>.py`, z. B. `account_journal_dashboard.py`).
- [x] **Dateiname `int_filemanager_document_link.py`** und das **Transient-Modell in `wizard/`**: geklärt, kein Befund. `<modell>_<thema>.py` ist das Muster des Cores für eine zweite Datei desselben Modells, und `wizard/` ist laut Odoo-Richtlinie der Ort für Transient-Modelle (auch `int_filemanager_share_attempt.py`, das keinen Dialog hat).

## Offen

### Befunde

- [ ] **1. Gäste-Zugang der Freigabe-Links** (`tools/share_gateway.py`, 526 Zeilen; Controller `controllers/int_filemanager_share.py`).
  - Gäste sprechen über eine eigene Whitelist (Modelle, Felder, Operatoren, Grenzen) mit dem ORM; die Aufrufe laufen als Superuser. Odoos Regeln und Zugriffsrechte gelten dort nicht, nur diese eine Datei schützt die Daten.
  - Das Gäste-Bundle in `__manifest__.py` listet 39 `web/static/…`-Pfade einzeln auf; bei jedem Odoo-Update kann das brechen.
  - Nächster Schritt: unabhängige Prüfung der Whitelist Zeile für Zeile (zum Beispiel mit dem Codex-Gegenleser, `codex -p review`), dabei auch klären, ob die Gäste-Seite mit weniger Core-Pfaden auskommt. Konzept: `docs/int_filemanager_freigabe_links.md`.
- [ ] **2. Dokumente nur über `_create_from_stream`.** Nutzer haben kein `create` auf Dokumente (CSV: `0`); angelegt wird als Superuser, der Controller prüft vorher. Begründet (`ir.attachment.file_size` ist int4, die Datei läge im Speicher), aber ein anderes Modul kann kein Dokument über `create()` anlegen. Entscheidung: so lassen und im Konzeptdokument festhalten, oder `create()` mit Prüfung öffnen.

### Kleinere Punkte

- [ ] **App-Symbol fehlt.** `application: True`, aber kein `static/description/icon.png` und kein `web_icon` am Wurzelmenü `menu_int_filemanager_root` (`views/int_filemanager_menus.xml`).
- [ ] **Keine Übersetzungsvorlage.** `i18n/` enthält nur `de.po`. Export mit `tools/check/i18n_export.sh`, dann `int_filemanager.pot` ablegen und `de.po` abgleichen (Skill `pruefen-und-committen`, Abschnitt 3).
- [ ] **Namen von Ansichten und Menüs.**
  - `res_users_view_form_preferences` (`views/res_users_views.xml:4`) trägt nicht die ID der Originalansicht `view_users_form_simple_modif`.
  - Menü-IDs `menu_int_filemanager_root` (`int_filemanager_menus.xml:4`) und `menu_int_filemanager_configuration` (`int_filemanager_folder_views.xml:174`) weichen vom Schema `<modell>_menu` ab.
  - Namenszusatz der Erbansichten uneinheitlich: `inherit.int.filemanager` (`res_partner_views.xml:4,23`) gegen `inherit.int_filemanager` (`res_config_settings_views.xml`, `res_users_views.xml`).
  - Vorsicht: Eine ID umzubenennen ändert die externe ID in bestehenden Datenbanken; vorher prüfen, ob Verweise (`ref=`, Menü-Eltern, Übersetzungen, Tests) darauf zeigen.
- [ ] **Compute ohne `@api.depends`:** `_compute_content`, `_compute_ocr_content`, `_compute_content_search` (alle `models/int_filemanager_document.py`), `_compute_document_search` (`int_filemanager_linkable.py`), `_compute_password` (`int_filemanager_share.py:446`). Platzhalter für Such- und Eingabefelder; Hinweis, kein Fehler. Prüfen, ob der Core dasselbe tut, sonst `@api.depends()` ergänzen.
- [ ] **Veraltete Doku:** `docs/int_filemanager_erkenntnisse.md:57` sagt „Pfadname nicht gespeichert (kein `complete_name`)“. Der Code speichert `complete_name` (`models/int_filemanager_folder.py:56`, `store=True`, nur zum Sortieren, wird in `_read_format` für Nutzer nicht ausgegeben). Den Satz richtigstellen.

## Nicht geprüft

- Ruff, ESLint, `check.sh` und die Tests liefen bei der Ausgangsprüfung nicht; seit den Änderungen oben laufen Ruff und die 994 Python-Tests am Tower grün, `check.sh` nicht.
- Browser: Bildeditor mit der lesbaren Fabric-Fassung, Hoot-Tests (`static/tests/`), Oberfläche allgemein.
- JS, Freigabe-Gateway und Ansichten nur mit Stichproben, nicht Zeile für Zeile.
