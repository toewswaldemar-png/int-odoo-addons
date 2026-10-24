# int_filemanager: Verknüpfung von Dokumenten mit Datensätzen

Dokumente des Filemanagers und Datensätze anderer Modelle kennen einander: am Datensatz die Schaltfläche „Dokumente (n)“, im Chatter eine Notiz beim Verknüpfen und Lösen, in der Suche das Feld „Dokument enthält“. Die Datei liegt weiter einmal in einem Ordner. Gebaut ist das für `res.partner`; die Bausteine stehen im Kern (`int.filemanager.link`, Mixin `int.filemanager.linkable`, `int.filemanager.model.folder` als Ablageordner je Modell für Dateien, die am Datensatz hochgeladen werden). Diese Datei hält die Gründe und das, was nicht aus dem Code ersichtlich ist.

## 1. Grundsätze
- **Der Datensatz ist die führende Struktur.** Odoo soll mit seinen Möglichkeiten genutzt werden und sich nicht der Ordnerstruktur des Fileservers anpassen. Ordner sind Ablage und Ordnung, nicht die Quelle der Zuordnung; Verweise hängen an IDs und überleben jede Umordnung. Wer einen Datensatz lesen darf, sieht dessen Dokumente, wie bei den Anhängen von Odoo.
- **Der Kern bleibt unabhängig** (`base`, `mail`). Eine Anbindung an eine App wäre ein eigenes Verbindungsmodul `int_filemanager_<app>` mit `auto_install` (Muster `account_fleet`, `hr_fleet`, `sale_project`); es besteht nur aus `_inherit = [<Modell>, "int.filemanager.linkable"]`, einer Schaltfläche, einer Übersetzung und einem Test. Ausnahmen im Kern: das Verweis-Modell samt Mixin und `res.partner` (liegt in `base`, bringt keine Abhängigkeit).
- **Nichts doppelt speichern.** Ein Verweis ist keine Kopie; der Chatter-Anhang (`ir.attachment`) bleibt, was er ist.
- **Verknüpfen ist eine bewusste Freigabe.** Ein Dokument aus einem geschützten Ordner wird mit dem Verweis für alle sichtbar, die den Datensatz lesen dürfen. Darum verknüpft nur, wer das Dokument über den **Ordner** sehen darf und den Zieldatensatz schreiben darf; sonst könnte ein Leser über den Datensatz es an weitere Datensätze hängen und immer weiter freigeben.
- **Verknüpfen ist keine Automatik;** Vorschläge (z. B. aus dem OCR-Text) bestätigt ein Mensch.

## 2. Rechtemodell
| Aktion | Wer |
|---|---|
| Dokument lesen (Liste, Formular, Vorschau, Download, Suche) | über den Ordner (offen, erlaubter Nutzer/Gruppe, Follower) **oder** wer mindestens einen verknüpften Datensatz lesen darf; dazu die Mehrfirmenregel |
| Dokument ändern, verschieben, löschen | nur über den Ordner (und Administratoren) |
| Verknüpfen und Lösen | Ordnerzugriff auf das Dokument **und** Schreibrecht am Zieldatensatz |
| Hochladen am Datensatz | wer den Datensatz schreiben darf; das Dokument entsteht im Ablageordner des Modells (mit erhöhten Rechten) und wird sofort verknüpft; ohne Ablageordner ist es nicht möglich |

**Umsetzung:** Die Ordnerregel und die Mehrfirmenregel bleiben unverändert. Dazu kommt eine **zweite Gruppenregel** auf `base.group_user`, nur Lesen, mit der Domain `[('access_via_record', '=', True)]`. `access_via_record` ist ein nicht gespeichertes, durchsuchbares Berechnungsfeld am Dokument. Gruppenregeln vereinigen sich mit ODER, die globale Mehrfirmenregel gilt mit UND: „Ordner oder Datensatz, und die Firma stimmt“, ohne Eingriff in `_search` oder `_check_access`.
- Suchmethode (SQL): je verknüpfbarem Modell `Domain('link_ids', 'any!', [('res_model', '=', M), ('res_id', 'in', <M>._search([]))])`, ODER-verknüpft (die Teilabfrage von `ir.attachment._search`, als Feldsuche). Berechnung (Python): `_check_access` wertet Regeln mit `filtered_domain` auf `sudo()`-Datensätzen aus, das Feld rechnet je Dokument, ob mindestens ein verknüpfter Datensatz für den Nutzer lesbar ist.
- Vorbilder im Core: `ir.attachment`, `mail.activity`, `mail.message`; alle überschreiben `_search`/`_check_access`. Für „Regel ODER Datensatz“ in `_search` gibt es dort keine Vorlage: `mail.activity` und `mail.message` filtern die Zeilen nachträglich in Python (bei 400.000 Dokumenten zu langsam), `ir.attachment` nutzt eine SQL-Teilabfrage ohne Regeln.
- **Drei belegte Fallen:**
  1. Odoo optimiert die Regel-Domain mit `self.sudo()` (`models.py`, `_search`): Suchmethode **und** Berechnung müssen den Nutzer wiederherstellen (`with_user(self.env.uid)`), sonst werden Datensätze anderer Firmen mitgezählt.
  2. Ein Nutzer mit Leserecht in der ACL, auf den keine Regel passt, sieht **alles**: die Regel auf `base.group_user` muss immer aktiv bleiben.
  3. Eine Gruppenregel mit `user.env[…].search([]).ids` in der Domain wird zwischengespeichert (`ir.rule._compute_domain` ist `ormcache`d): ein neu verknüpfter Datensatz bleibt unsichtbar, bis der Zwischenspeicher geleert wird. Darum das Berechnungsfeld.
- `ir.model` ist für normale Nutzer nicht lesbar; `create()` des Verweises liest `res_model_id.model` mit `sudo()` (wie `mail.activity`).
- ACL: `base.group_user` darf Dokument und Verweis lesen (sichtbar wird nur, was die Regeln freigeben); Schreiben, Anlegen, Löschen nur `int_filemanager_group_user` plus die Prüfung in `create()`/`unlink()` des Verweises.

## 3. Datenmodell und Aufräumen
- `int.filemanager.link`: `document_id` (Many2one, `ondelete='cascade'`), `res_model_id` (`ir.model`, `ondelete='cascade'`), `res_model` (related, gespeichert, Index mit `res_id`), `res_id` (`Many2oneReference`); eindeutig je (Dokument, Modell, Datensatz). Muster von `ir.attachment` und `mail.activity`.
- Die Datenbank kann über (`res_model`, `res_id`) nicht kaskadieren: der Mixin entfernt beim `unlink()` des Zielmodells die Verweise (wie `mail.thread.unlink` Nachrichten und Follower), dazu ein `@api.autovacuum` für Verweise auf nicht mehr vorhandene Datensätze (Zielmodell ohne `mail.thread`, direkte SQL-Löschungen).
- Verweis löschen lässt die Datei bestehen; Dokument löschen entfernt seine Verweise; Archivieren blendet es am Datensatz aus; Verschieben in einen anderen Ordner ändert nichts an Verweisen und Sichtbarkeit über den Datensatz.

## 4. Gemessen

Bei 400.000 Dokumenten, 300 Ordnern und 20.000 Verweisen auf 5.000 Datensätze (synthetisch) kostet der Datensatzweg bei der Anzahl 0,29 s statt 0,08 s, die Liste (80) 0,014 s statt 0,003 s; im ungünstigsten Fall (alle Dokumente verknüpft) 1,3 s für die Anzahl, 0,19 s für die Liste. Die Anzahl am Listenende ist der teuerste Posten.

## 5. Core-Fundstellen (Branch 19.0)
| Aussage | Fundstelle |
|---|---|
| Verweis als `res_model` + `res_id` (`Many2oneReference`), Index auf beide | `odoo/addons/base/models/ir_attachment.py`: `_res_idx` |
| Ein Anhang ist zugänglich, wenn der verknüpfte Datensatz es ist; `create`/`unlink` zählen als `write` am Ziel | `ir_attachment.py`: `_check_access`, `_inaccessible_comodel_records` |
| Suche über Teilabfrage `res_id in (<Modell>._search(…))` für bis zu fünf Modelle, sonst Stapelprüfung in Python | `ir_attachment.py`: `_search` |
| One2many über ein `Many2oneReference` ergänzt den Filter auf das Modell | `odoo/orm/fields_relational.py`: `_additional_domain` |
| Kaskade über (`res_model`, `res_id`) nicht möglich, Aufräumen von Hand | `addons/mail/models/mail_thread.py`: `unlink` |
| `any` wendet die Regeln des Comodells an, `any!` umgeht sie | `fields_relational.py`: `bypass_search_access` |
| Verbindungsmodule mit `auto_install` | `addons/account_fleet`, `hr_fleet`, `sale_project`: `__manifest__.py` |

## 6. Nicht gebaut

- Dialog zum Verknüpfen vom Datensatz aus mit Hinweis bei einem Dokument im eingeschränkten Ordner; Verbindungsmodule (`int_filemanager_<app>`) für weitere Apps.
- Kein Ersatz für Chatter-Anhänge, kein Umzug alter Anhänge; keine Enterprise-Funktionen (Documents-App); Versionen, Portal und Office im Browser sind nicht Teil des Moduls.
