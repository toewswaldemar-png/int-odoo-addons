# int_filemanager: offene Punkte aus dem Abgleich mit den Odoo-19-Vorgaben

Offen sind nur Punkte, die der Code noch zeigt. Maßstab: `docs/odoo19_reference/` und `docs/odoo/`.

## Befunde

1. **Gäste-Zugang der Freigabe-Links** (Modul `int_filemanager_share`: `tools/share_gateway.py`, Controller `controllers/int_filemanager.py`).
   - Gäste sprechen über eine eigene Whitelist (Modelle, Felder, Operatoren, Grenzen) mit dem ORM; die Aufrufe laufen als Superuser. Odoos Regeln und Zugriffsrechte gelten dort nicht, nur diese eine Datei schützt die Daten.
   - Das Gäste-Bundle in `__manifest__.py` listet `web/static/…`-Pfade einzeln auf; bei jedem Odoo-Update kann das brechen.
   - Nächster Schritt: unabhängige Prüfung der Whitelist Zeile für Zeile; dabei klären, ob die Gäste-Seite mit weniger Core-Pfaden auskommt. Konzept: `docs/int_filemanager/freigabe_links.md`.
2. **Dokumente nur über `_create_from_stream`.** Nutzer haben kein `create` auf Dokumente (CSV: `0`); angelegt wird als Superuser, der Controller prüft vorher. Begründet (`ir.attachment.file_size` ist int4, die Datei läge im Speicher), aber ein anderes Modul kann kein Dokument über `create()` anlegen. Entscheidung: so lassen und im Konzeptdokument festhalten, oder `create()` mit Prüfung öffnen.
3. **Tags sind global.** Jeder Nutzer der Gruppe darf Tags anlegen, umbenennen und löschen (`int_filemanager_tag_user`: 1,1,1,1); alle sehen alle Namen.

## Kleinere Punkte

- **App-Symbol fehlt.** `application: True`, aber kein `static/description/icon.png` und kein `web_icon` am Wurzelmenü `menu_int_filemanager_root`.
- **Übersetzungsvorlagen.** Die Module `int_filemanager_import`, `_image_editor`, `_ocr` und `_share` haben `.pot` und `de.po` (aus der alten `de.po` geteilt, nicht neu exportiert); der Kern hat noch keine `int_filemanager.pot`. Export mit `I18N_MODULE=<Modul> tools/check/i18n_export.sh`, dann `de.po` abgleichen.
- **Namen von Ansichten und Menüs.** `res_users_view_form_preferences` trägt nicht die ID der Originalansicht; die Menü-IDs `menu_int_filemanager_root` und `menu_int_filemanager_configuration` weichen vom Schema `<modell>_menu` ab; der Namenszusatz der Erbansichten ist uneinheitlich (`inherit.int.filemanager` gegen `inherit.int_filemanager`). Eine ID umzubenennen ändert die externe ID in bestehenden Datenbanken; vorher prüfen, ob `ref=`, Menü-Eltern, Übersetzungen oder Tests darauf zeigen.
- **Compute ohne `@api.depends`:** `_compute_content`, `_compute_ocr_content`, `_compute_content_search` (`int_filemanager_ocr`, `models/int_filemanager_document.py`), `_compute_document_search` (`int_filemanager_ocr`, `models/int_filemanager_linkable.py`), `_compute_password` (`int_filemanager_share`, `models/int_filemanager_share.py`). Platzhalter für Such- und Eingabefelder; Hinweis, kein Fehler. Prüfen, ob der Core dasselbe tut, sonst `@api.depends()` ergänzen.

## Nicht geprüft

- Der Browser: Bildeditor, Hoot-Tests (`static/tests/`), Oberfläche allgemein.
- JS, Freigabe-Gateway und Ansichten nur mit Stichproben, nicht Zeile für Zeile.
