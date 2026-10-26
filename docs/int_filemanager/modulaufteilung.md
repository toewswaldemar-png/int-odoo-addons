# int_filemanager: Aufteilung in Module

`int_filemanager` ist der Kern. Was nicht jeder Betrieb braucht, steht in Erweiterungsmodulen, die vom Kern abhängen und nur über `_inherit`, View-Vererbung und die Erweiterungspunkte unten an ihn anknüpfen. Der Kern kennt keines davon.

```
int_filemanager_share   int_filemanager_ocr   int_filemanager_image_editor   int_filemanager_import
            \                  |                        |                         /
                                  int_filemanager (Kern)
                                       base, mail
```

| Modul | Inhalt |
|---|---|
| `int_filemanager` | Ordner, Dokumente, Storage (Blobs), Thumbnails und Office-Vorschau, ZIP, Verknüpfungen, Rechte, Oberfläche (Liste, Kanban, Viewer) |
| `int_filemanager_share` | Freigabe-Links: Modell, Routen, Gast-Seite und -Bundles, Gateway, Bremsen, Settings; `share_id` am Dokument, Share-Knöpfe an Dokument und Ordner |
| `int_filemanager_ocr` | Volltextsuche und OCR: Modelle `text` und `text_page`, Cron, `content_search` und `content_hits` am Dokument, `ocr_images` am Ordner, Settings und Status, Widgets der Treffer |
| `int_filemanager_image_editor` | Bildeditor (Fabric, lazy Bundle), `edit_state` und `edit_source_id` am Dokument, `get_edit_session` |
| `int_filemanager_import` | Einlesen eines Ordners der Serverplatte, `origin_path` am Dokument |

## Erweiterungspunkte des Kerns

Wer den Kern erweitert, überschreibt diese Stellen mit `super()`:

| Stelle | Zweck | Benutzt von |
|---|---|---|
| `int.filemanager.cron` (abstrakt: `_setting`, `_flag`, `_budget`, `_pass_deadline`) | Settings als Systemparameter und die Zeit eines Cron-Laufs; `_setting_defaults()` ergänzt Zahlen | Vorschau (Kern), `int.filemanager.text` (`_inherit`) |
| `document._crons_after_preview()` | Welche Crons nach einer fertigen Vorschau geweckt werden | `ocr` (Text der alten Formate) |
| `document._gc_lock_tables()` und `document._blobs_in_use(names)` | Der Blob-Cleaner sperrt diese Tabellen und kennt diese Prüfsummen als benutzt | `ocr` (erkannte PDFs) |
| `document._compute_viewer_pdf_checksum` | Das PDF, das der Viewer statt der Datei zeigt (Vorschau; `ocr` ergänzt das erkannte PDF) | `ocr` |
| `controllers.IntFilemanager._upload_values(**kwargs)` | Felder, die das Formular des Uploads zum Dokument hinzufügt | `image_editor` |
| Dienst `int_filemanager.image_editor` (JS, optional) | Knopf „Bearbeiten“ im Viewer und im Formular | `image_editor` |
| `write()` | Jedes Modul wirft seine eigenen, nur vom Server gesetzten Felder für Nicht-Superuser weg (`STORAGE_FIELDS` im Kern, `EDIT_FIELDS`, `SHARE_FIELDS`) | alle |

## Regeln beim Weiterbauen

- Externe IDs, Vorlagen, Bundles und Hoot-Modulnamen tragen den Namen des Moduls, das sie definiert (`int_filemanager_share.assets_guest`, `@int_filemanager_ocr/content_hits/...`). Systemparameter und Routen blieben bei `int_filemanager.*` und `/int_filemanager/...`.
- Ein Erweiterungsmodul fügt Felder zu Views per `xpath` hinzu (Settings-Blöcke: `//block[@name=...]`).
- Tests eines Moduls liegen im Modul. Gemeinsame Bausteine der Tests (`AccessCase`, `BlobCase`, `text_files`) stehen im Kern und werden mit `odoo.addons.int_filemanager.tests...` importiert.
- Übersetzungen: jedes Modul hat `i18n/<modul>.pot` und `de.po`; Begriffe stehen in dem Modul, das sie definiert.
- Tests auf der Test-Instanz: `TESTS_MODULE=int_filemanager,int_filemanager_share,... tools/check/tests.sh` (Komma-Liste; liefert auch alle `int_filemanager*`-Ordner mit).

## Entscheidungen

- **Vorschau und Thumbnails bleiben im Kern.** Der Viewer für Office-Dateien braucht sie, und sie sind unabhängig von OCR.
- **Der Kern hat keine Datenbank-Migration für die Aufteilung.** Die Tabellen und Spalten der verschobenen Modelle sind unverändert; bei einer bestehenden Datenbank mit Daten müssten vorher die externen IDs (`ir_model_data.module`) der verschobenen Modelle, Felder, Views, Crons, Regeln und Zugriffsrechte auf die neuen Module umgeschrieben werden, sonst löscht das Update des Kerns deren Tabellen. Gebaut wurde das nicht, weil die vorhandene Datenbank nur Testdaten hat.
- **Die Tabelle der Freigaben gehört `int_filemanager_share`.** Die Migration des Kerns löscht nur die Tabellen der entfernten Modelle; die alten Spalten von `int_filemanager_share` (`node_id`, `expires_at`, `revoked_at`) räumt der `pre_init_hook` des Share-Moduls ab (Migrationsskripte laufen bei einer Installation nicht).
- **Stand der Prüfung:** statisch geprüft (Syntax, externe IDs, Importe, Manifeste, Testpakete). Die Odoo-Tests und die Hoot-Tests sind nach der Aufteilung noch nicht gelaufen.
