# int_filemanager: Aufteilung in Module

`int_filemanager` ist der Kern. Was nicht jeder Betrieb braucht, steht in Erweiterungsmodulen, die vom Kern abhängen und nur über `_inherit`, View-Vererbung und die Erweiterungspunkte unten an ihn anknüpfen. Der Kern kennt keines davon.

```
                 int_filemanager_record_ocr (auto_install)
                          /                \
int_filemanager_share   int_filemanager_record   int_filemanager_ocr   int_filemanager_image_editor   int_filemanager_import
            \                  |                        |                         |                       /
                                  int_filemanager (Kern)
                                       base, mail
```

| Modul | Inhalt |
|---|---|
| `int_filemanager` | Ordner, Dokumente, Storage (Blobs), Thumbnails und Office-Vorschau, ZIP, Rechte (Ordner entscheiden), Oberfläche (Liste, Kanban, Viewer) |
| `int_filemanager_record` | Dokumente an Datensätzen: Modelle `link` und `model.folder`, Mixin `linkable` (Kontakt `res.partner`), Sichtbarkeit über den verknüpften Datensatz (Einstellung), Upload am Datensatz, Ablageordner je Modell. Konzept: `docs/int_filemanager_record/datensatz_verknuepfung.md` |
| `int_filemanager_record_ocr` | `auto_install` mit `record` und `ocr`: die Suche „Dokument enthält“ am Kontakt (`document_search`) |
| `int_filemanager_share` | Freigabe-Links: Modell, Routen, Gast-Seiten im Portal-Layout (hängt von `portal` ab), Upload-Skript, Bremsen, Settings; `share_id` am Dokument, Share-Knöpfe an Dokument und Ordner |
| `int_filemanager_ocr` | Volltextsuche und OCR: Modelle `text` und `text_page`, Cron, `content_search` und `content_hits` am Dokument, `ocr_images` am Ordner, Settings und Status, Widgets der Treffer |
| `int_filemanager_image_editor` | Bildeditor (Fabric, lazy Bundle), `edit_state` und `edit_source_id` am Dokument, `get_edit_session` |
| `int_filemanager_import` | Einlesen eines Ordners der Serverplatte, `origin_path` am Dokument |

## Erweiterungspunkte des Kerns

Wer den Kern erweitert, überschreibt diese Stellen mit `super()`:

| Stelle | Zweck | Benutzt von |
|---|---|---|
| `int.filemanager.cron` (abstrakt: `_time_reserve`, `_budget`, `_pass_deadline`) | Die Zeit eines Cron-Laufs | Vorschau (Kern), `int.filemanager.text` (`_inherit`) |
| `document._crons_after_preview()` | Welche Crons nach einer fertigen Vorschau geweckt werden | `ocr` (Text der alten Formate) |
| `document._gc_lock_tables()` und `document._blobs_in_use(names)` | Der Blob-Cleaner sperrt diese Tabellen und kennt diese Prüfsummen als benutzt | `ocr` (erkannte PDFs) |
| `document._compute_viewer_pdf_checksum` | Das PDF, das der Viewer statt der Datei zeigt (Vorschau; `ocr` ergänzt das erkannte PDF) | `ocr` |
| `controllers.IntFilemanager._upload_values(**kwargs)` | Felder, die das Formular des Uploads zum Dokument hinzufügt | `image_editor` |
| Dienst `int_filemanager.image_editor` (JS, optional) | Knopf „Bearbeiten“ im Viewer und im Formular | `image_editor` |
| `controllers.IntFilemanager._upload_folder(folder_id, **kwargs)` und `_after_upload(document, **kwargs)` | Wohin die Datei des Uploads kommt (im Kern der Ordner des Formulars, wie der Nutzer ihn sieht; das Schreibrecht prüft `_create_from_stream`, wer es anders geprüft hat, gibt den Ordner als Superuser zurück) und was danach folgt | `record` (Upload am Datensatz) |
| `document._filtered_folder_access(operation)` | Die Dokumente, deren Ordner der Nutzer lesen darf, ohne andere Wege, ein Dokument zu sehen. Wer ein Dokument weitergibt (Verknüpfen, Freigabe), fragt dies, nicht `_filtered_access` | `share`, `record` |
| `document._documents_referenced()` | Welche Dokumente etwas anderes noch braucht (im Kern keine); ein Gast der Freigabe nimmt sie nicht weg | `share` fragt, `record` antwortet |
| `DocumentListController.uploadTarget` (JS) | Wohin die Dateien der Ablagefläche gehen, wenn nicht in den Ordner des Bereichs: Text und Formularfelder | `record` |
| `write()` | Jedes Modul wirft seine eigenen, nur vom Server gesetzten Felder für Nicht-Superuser weg (`STORAGE_FIELDS` im Kern, `EDIT_FIELDS`, `SHARE_FIELDS`) | alle |

## Regeln beim Weiterbauen

- Externe IDs, Vorlagen, Bundles und Hoot-Modulnamen tragen den Namen des Moduls, das sie definiert (`int_filemanager_share.share_folder_page`, `@int_filemanager_ocr/content_hits/...`). Systemparameter und Routen blieben bei `int_filemanager.*` und `/int_filemanager/...`.
- Ein Erweiterungsmodul fügt Felder zu Views per `xpath` hinzu (Settings-Blöcke: `//block[@name=...]`).
- Settings sind Systemparameter `int_filemanager.<name>` und werden wie im Odoo-Kern gelesen: `get_param(key, KONSTANTE)` am Ort der Verwendung, ein kleiner Getter am Modell, wenn mehrere Stellen dieselbe Einstellung brauchen. Der Default steht einmal als Modul-Konstante und dient dem Feld in `res.config.settings` als `default=` (Muster `cloud_storage`). Mindestwerte der Zahlen erzwingt ein `@api.onchange` an der Maske (Muster `auth_password_policy`); Share prüft sie als `@api.constrains`. Es gibt keinen eigenen Helfer.
- Tests eines Moduls liegen im Modul. Gemeinsame Bausteine der Tests (`AccessCase`, `BlobCase`, `text_files`) stehen im Kern und werden mit `odoo.addons.int_filemanager.tests...` importiert.
- Übersetzungen: jedes Modul hat `i18n/<modul>.pot` und `de.po`; Begriffe stehen in dem Modul, das sie definiert.
- Tests auf der Test-Instanz: `TESTS_MODULE=int_filemanager,int_filemanager_share,... tools/check/tests.sh` (Komma-Liste; liefert auch alle `int_filemanager*`-Ordner mit).

## Entscheidungen

- **Vorschau und Thumbnails bleiben im Kern.** Der Viewer für Office-Dateien braucht sie, und sie sind unabhängig von OCR.
- **Der Kern hat keine Datenbank-Migration für die Aufteilung.** Die Tabellen und Spalten der verschobenen Modelle sind unverändert; bei einer bestehenden Datenbank mit Daten müssten vorher die externen IDs (`ir_model_data.module`) der verschobenen Modelle, Felder, Views, Crons, Regeln und Zugriffsrechte auf die neuen Module umgeschrieben werden, sonst löscht das Update des Kerns deren Tabellen. Gebaut wurde das nicht, weil die vorhandene Datenbank nur Testdaten hat.
- **Die Verknüpfung ist ein eigenes Modul, weil die Rechte der Ordner ohne sie vollständig sind.** Der Kern hat die Regeln für Firma, Sichtbarkeit und Administrator an Ordner und Dokument und sonst nichts; `record` fügt dem Dokument eine zweite Gruppenregel (über den Datensatz) und dem Link eigene hinzu. Auch hier gibt es keine Datenbank-Migration: die externen IDs der Modelle `link` und `model.folder`, ihrer Regeln, Zugriffsrechte und Views (`ir_model_data.module`) müssten bei einer bestehenden Datenbank mit Daten vor dem Update des Kerns auf `int_filemanager_record` umgeschrieben werden, sonst löscht es deren Tabellen. Die Testdatenbank wird neu aufgesetzt.
- **Die Tabelle der Freigaben gehört `int_filemanager_share`.** Der Kern hat keine Migration (das frühere Skript für die Tabellen alter Modellstände ist entfernt); die alten Spalten von `int_filemanager_share` (`node_id`, `expires_at`, `revoked_at`) räumt der `pre_init_hook` des Share-Moduls ab (Migrationsskripte laufen bei einer Installation nicht).
- **Stand der Prüfung (Aufteilung):** statisch geprüft (Syntax, externe IDs, Importe, Manifeste, Testpakete). Die Odoo-Tests und die Hoot-Tests sind nach der Aufteilung noch nicht gelaufen.
