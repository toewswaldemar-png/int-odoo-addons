# int_filemanager: Rechtemodell, Übergabe (20.10.2026)

Maßstab ist allein Odoo 19 (`docs/odoo`, `docs/odoo19_reference`). Zu jedem Schritt vorher das Core-Vorbild mit Fundstelle nennen. Eine Hook-Meldung "nichts gefunden" heißt nur, dass die mechanischen Regeln eingehalten sind, nicht dass die Lösung Odoo-konform ist.

## Stand

Fertig und gepusht: `b177f61` (Listenzellen vertikal zentriert, `align-middle` an der Tabelle in `document_list_renderer.xml`). Sonst nichts offen im Repo.

## Beschlossen (Nutzer: "wie empfohlen")

1. **Gruppe "Filemanager Reader" (nur lesen)** im selben Privileg `privilege_int_filemanager`, unter "User" und "Administrator" (`implied_ids`-Kette: Admin ⊃ User ⊃ Reader). Keine Listen "Ändern" je Ordner. Vorbild: `project` (`project/security/ir.model.access.csv:2-3`, Rechte je Vorgang in `project_security.xml:83-98`, `121-132`).
2. **Zugriffsfelder** (`access_mode`, `access_user_ids`, `access_group_ids`) nur für Admins (`groups=` am Feld, wie `ocr_images`). **Einladen** (Follower) bleibt für alle mit Änderungsrecht (getestet: `test_a_follower_may_invite_others`).
3. **Zugriff über verknüpfte Datensätze** wird eine Einstellung, Standard **aus**. Sie schaltet per `active` die Regel `int_filemanager_document_rule_record` **und** die ACL-Zeilen `access_int_filemanager_document_internal` und `access_int_filemanager_link_internal` um. Vorbild: `project/models/project_collaborator.py` (`_toggle_project_sharing_portal_rules`). Beides muss mit, sonst dürfte jeder interne Nutzer alle Dokumente lesen (Kommentar bei `int_filemanager_document_security.xml:24`). Das ersetzt `access_via_record` und `FOLDER_ONLY_KEY` (in `int_filemanager_link.py`, `int_filemanager_document_link.py`, `int_filemanager_share.py`).
4. **Notiz am verknüpften Datensatz neutral**, ohne Dateiname und Link (`int_filemanager_link.py:210-224`, `_post_notes`). Der volle Text bleibt nur im Verlauf der Datei. Kein Core-Vorbild, bewusste Entscheidung.
5. **Oberfläche 1:1 Core:** berechnetes Feld `is_editable` aus `has_access("write")` mit `@api.depends_context("uid")`, in der Ansicht `<field name="is_editable" invisible="1"/>` und `readonly="not is_editable"` (`mail/models/discuss/discuss_channel.py:229-232`, `mail/views/discuss_channel_views.xml:57-77`). Einstellung als `<setting>` (Muster: Freigabe-Einstellungen in `res_config_settings_views.xml`).

## Reihenfolge

| Schritt | Inhalt |
|---|---|
| 0 | Tests vorab: Rechte-Matrix (wer sieht, ändert, löscht was), auch die heutigen Lücken |
| 1 | Befund 3: neutrale Notiz |
| 2 | Befund 2: Einstellung, Standard aus, Umschalten von Regel und ACL |
| 3 | Befund 1: Gruppe Reader, ACL und Regeln je Vorgang, `is_editable` in Dokument- und Ordner-Formular, `groups=` an den Zugriffsfeldern |
| 4 | Übersetzungen (`i18n/de.po`), Tests der betroffenen Klassen |

Ein Commit je Thema, Kopfzeile nach den Odoo Git Guidelines.

## Befunde der Rechteprüfung (Quelltext, nichts ausgeführt)

1. Sehen heißt voll bearbeiten: Regel `int_filemanager_folder_rule_user` erlaubt Lesen, Schreiben und Löschen jedem, der den Ordner sieht. Eine Nur-lesen-Rolle fehlt. Der Test `test_the_lists_are_read_by_the_administrators_only` prüft nur, dass ein Admin die Listen lesen darf.
2. Eine Verknüpfung öffnet die Datei für alle internen Nutzer (Regel `int_filemanager_document_rule_record`, Gruppe `base.group_user`), weil jeder Kontakte lesen darf (`base/security/base_security.xml:12-20`).
3. Der Dateiname steht im Verlauf des verknüpften Datensatzes (Kontakt).
4. Archivieren eines Ordners archiviert per `sudo()` auch versteckte Unterordner und Dokumente (`int_filemanager_folder.py:499`).
5. Bremsen für Anfragen, Uploads und falsche Tokens liegen im Speicher je Worker (`int_filemanager_share.py:664-670`). Die Passwort-Bremse ist in der Datenbank und robust.
6. Eine Freigabe bleibt gültig, wenn der Ersteller den Zugriff auf den Ordner verliert.
7. Tags sind global (jeder legt an, benennt um, löscht, alle sehen alle Namen).
8. Der Freigabe-Schlüssel steht als `k` im Query-String der GET-Routen und damit in Server-Logs.

Zurückgenommen: Ein früher gemeldeter Befund "`link_ids` im Mixin ohne Filter auf `res_model`" war falsch. Odoo ergänzt bei einem One2many mit `Many2oneReference` als Gegenfeld den Filter auf das Modell selbst (`odoo/orm/fields_relational.py:923-925`).

In Ordnung: Aufbau der Regeln (global ∩ Gruppe, vereinigt), ACL für alle konkreten Modelle, Downloads (`ir_binary.py:54` `check_access("read")`), ZIP-Routen, die ganze Gast-Schnittstelle (`tools/share_gateway.py`), Import (nur Admin, `realpath`, keine Symlinks).

## Stolpersteine

- **Hochladen am Datensatz** (Kontakt, Auftrag) hängt an der Verknüpfung: Controller `upload` mit `link_model`/`link_id`, Einstellung "Ordner je Modell" (`int_filemanager_model_folder.py`), JS `document_list_controller.js:49-60, 344`. Der Hochladende sieht die Datei nur über `access_via_record`. Mit der Einstellung "aus" ist das Hochladen am Datensatz ohne Ordnerrecht wirkungslos. Im Hilfetext der Einstellung sagen.
- Rechte-Regeln sind in 7 Dateien verstreut (`security/`), dieselbe Ordner-Bedingung steht dreimal (Ordner, Ordner anlegen, Dokument). Core-üblich, nicht zusammenlegen.
- Datei `int_filemanager_text.py` (1521 Zeilen) und `tools/request_brake.py` wurden nur auf Rechte-Stellen durchsucht.
- Noch zu prüfen vor Schritt 3: wie Odoo 19 ein Privileg mit drei Stufen im Benutzerformular zeigt, und ob ein interner Nutzer ohne Filemanager-Gruppe das Dokumentformular ohne Fehler öffnet (Ordner-ACL fehlt dort).
- Test-Instanz: `tools/check/ui_instance.sh` (Port 8085, Container `fmv2_ui`), nie das Live-Odoo `odoo`.

## Zweites Thema: Verknüpfungen im Formular (nach dem Rechtemodell)

Die Seite "Links" im Detail-Bereich (`int_filemanager_link_views.xml:22-34`) wirkt überladen (Tab mit einer Seite, Tabelle mit "Erstellt von/am"). Vorlage ist Enterprise Documents (Zeilen "Kontakt" und "Verknüpftes Modell").

Entscheidungen bisher:
- Mehrere Kontakte je Datei (Beispiel Gehaltsabrechnung: Familienkasse, Wohngeldbehörde, Firmenkontakt), also ein Many2many-Feld `partner_ids` mit `many2many_tags`, nach dem Muster `calendar_views.xml:85`.
- Zeile "Verknüpftes Modell" erst, wenn ein zweites Modell sie braucht (heute nutzt nur `res.partner` den Mixin).
- Wird `res.partner` aus dem Mixin genommen, leert das die Auswahl in "Ordner je Modell" und bricht das Hochladen am Kontakt. Vorher klären, wie die Kontakt-Seite ohne den Mixin weiter hochladen soll.
- Der Zugriff folgt dem Ordner, nicht den Kontakten.

Kein Notebook mit einer einzelnen Seite bauen (Odoo nutzt Notebooks mit mehreren Seiten).
