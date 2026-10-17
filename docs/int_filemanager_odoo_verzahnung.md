# int_filemanager: Verzahnung mit Odoo (Konzept)

Stand 2026-10-16. **Gebaut:** der Kern von Funktion 1 (§3.1 bis §3.3) mit `res.partner`, dazu das Hochladen am Datensatz mit Ablageordner je Modell (`int.filemanager.model.folder`, Menü „Upload-Ordner“); volle Suite grün (605 Tests). **Noch offen:** Dialog zum Verknüpfen vom Datensatz aus, Hinweis bei eingeschränktem Ordner, `int_filemanager_repair`, alles aus §5. Maßgeblich ist der Code. Belege zum Odoo-19-Kern stehen in §7; was nur im
Quelltext gelesen und noch nicht in einer Wegwerf-Datenbank getestet ist, steht in §8.

## 1. Ziel

Dokumente des Filemanagers und Datensätze von Odoo (Kunde, Reparaturauftrag, Rechnung, Fahrzeug …) kennen einander. Am Reparaturauftrag sieht man
dessen Dokumente samt Vorschau, am Kunden alles zu diesem Kunden, im Chatter steht, wann etwas dazukam, und man findet Aufträge über Wörter im Text ihrer
Dokumente. Die Datei liegt dabei weiter **einmal** in **einem** Ordner und bleibt über die Volltextsuche auffindbar.

## 2. Grundsätze

- **Der Datensatz ist die führende Struktur (Entscheidung 2026-10-16).** Langfristig soll Odoo mit seinen Möglichkeiten genutzt werden und sich nicht
  der heutigen Ablage auf dem Fileserver anpassen. Die Ordner sind Ablage und Ordnung, nicht die Quelle der Zuordnung; Verweise hängen an IDs und
  überleben jede spätere Umordnung der Ordner. Wer einen Datensatz lesen darf, sieht dessen Dokumente, wie bei den Anhängen von Odoo.
- **Der Kern bleibt unabhängig.** `int_filemanager` hängt weiter nur von `base` und `mail` ab. Jede Anbindung an eine App ist ein eigenes
  Verbindungsmodul `int_filemanager_<app>` mit `auto_install` (Odoos Muster: `account_fleet`, `hr_fleet`, `sale_project`). Zwei Ausnahmen im Kern: das
  Verweis-Modell samt Mixin (es kennt keine App) und die Anbindung von `res.partner` (liegt in `base`, bringt keine Abhängigkeit).
- **Nichts doppelt speichern.** Ein Verweis ist ein Verweis, keine Kopie. Der Chatter-Anhang (`ir.attachment`) bleibt, was er ist; wer eine Datei im
  Filemanager haben will, verknüpft sie oder lädt sie am Datensatz hoch.
- **Verknüpfen ist eine bewusste Freigabe.** Ein Dokument aus einem geschützten Ordner wird mit dem Verweis für alle sichtbar, die den Datensatz lesen
  dürfen. Darum dürfen nur Nutzer mit Ordnerzugriff verknüpfen, und die Oberfläche weist darauf hin (§3.3).
- **Verknüpfen ist keine Automatik.** Vorschläge (z. B. aus dem OCR-Text) bestätigt immer ein Mensch.

## 3. Funktion 1: Dokument ↔ Datensatz verknüpfen

Grundlage aller weiteren Funktionen (§5).

### 3.1 Verhalten

- **Am Dokument:** Reiter „Verknüpfungen“ mit einer Liste (Modell, Datensatz, wer, wann). Hinzufügen über ein Referenzfeld (Modell wählen, Datensatz
  suchen), entfernen mit dem Papierkorb.
- **Am Datensatz:** Schaltfläche „Dokumente (n)“. Ein Klick öffnet die Dokumente des Datensatzes in der gewohnten Ansicht (Liste, Kanban, Vorschau).
  Hinzufügen vom Datensatz aus: Dialog mit Suche über alle Dokumente, die der Nutzer über den Ordner sehen darf.
- **Hochladen am Datensatz:** Das neue Dokument kommt in den **Ablageordner des Modells** (§3.2), wird verknüpft, und der Hochladende sieht es über den
  Datensatz. So brauchen Werkstatt-Mitarbeiter weder Gruppe noch Ordnerzugriff.
- **Im Chatter:** beim Verknüpfen und Lösen steht eine Notiz am Datensatz und am Dokument („Dokument … verknüpft“), mit Link.
- **In der Suche des Datensatzes:** Feld „Dokument enthält“ (Wörter aus dem Text der verknüpften Dokumente, nutzt `content_search`).
- Ein Dokument kann an beliebig vielen Datensätzen hängen, auch an verschiedenen Modellen; ein Datensatz hat beliebig viele Dokumente.
- Verweis löschen lässt die Datei bestehen. Dokument löschen entfernt seine Verweise. Archivieren eines Dokuments blendet es am Datensatz aus.
- **Hinweis beim Verknüpfen:** liegt das Dokument in einem eingeschränkten Ordner, fragt die Oberfläche nach („für alle sichtbar, die diesen Datensatz
  lesen dürfen“).

### 3.2 Datenmodell

Neues Modell `int.filemanager.link`, Muster von `ir.attachment` (`res_model`, `res_id`) und `mail.activity` (`res_model_id`):

| Feld | Art | Anmerkung |
|---|---|---|
| `document_id` | Many2one `int.filemanager.document` | Pflicht, `ondelete='cascade'`, Index |
| `res_model_id` | Many2one `ir.model` | Pflicht, `ondelete='cascade'` (Modell-Deinstallation räumt auf) |
| `res_model` | Char, related `res_model_id.model`, gespeichert | Index zusammen mit `res_id` |
| `res_id` | Many2oneReference, `model_field='res_model'` | Pflicht |
| `create_uid`, `create_date` | Standard | „wer, wann“ |

Eindeutig je (`document_id`, `res_model`, `res_id`). Am Dokument `link_ids` (One2many).

Mixin `int.filemanager.linkable` (AbstractModel, im Kern), das ein Zielmodell erbt:
- `link_ids` (One2many auf `res_id`; der ORM ergänzt den Filter auf das Modell selbst), `document_count` (per `_read_group`), `action_open_documents()`,
- Suchfeld `document_search` über `content_search` der verknüpften Dokumente,
- `unlink()`-Überschreibung, die die Verweise der gelöschten Datensätze entfernt (wie `mail.thread.unlink` Nachrichten und Follower entfernt: die
  Datenbank kann über (`res_model`, `res_id`) nicht kaskadieren),
- Eintrag in einer Liste der verknüpfbaren Modelle (Registry), aus der die Rechteprüfung (§3.3) ihre Teilabfragen baut.

Dazu ein `@api.autovacuum`, der Verweise auf nicht mehr vorhandene Datensätze löscht (Zielmodell ohne `mail.thread` und direkte SQL-Löschungen gehen am
`unlink()` vorbei).

**Ablageordner je Modell:** kleines Modell `int.filemanager.model.folder` (`res_model_id`, `folder_id`, Firma; je Modell und Firma eindeutig), nur für
Administratoren. Es sagt, wohin ein am Datensatz hochgeladenes Dokument kommt, z. B. `Reparatur` für `repair.order`. Ohne Eintrag ist Hochladen am
Datensatz nicht möglich (Fehlermeldung mit Hinweis an den Administrator).

### 3.3 Rechte

Das Rechtemodell ersetzt die bisherige reine Ordnerregel (`int_filemanager_document_rule_user`).

| Aktion | Wer |
|---|---|
| **Dokument lesen** (Liste, Formular, Vorschau, Download, Suche) | über den **Ordner** (wie bisher: offen, erlaubter Nutzer/Gruppe, Follower) **oder** wer mindestens einen **verknüpften Datensatz lesen** darf; dazu die Mehrfirmenregel |
| **Dokument ändern, verschieben, löschen** | nur über den Ordner (und Administratoren); ein Leser über den Datensatz darf nichts verändern |
| **Verknüpfen und Lösen** | nur wer das Dokument **über den Ordner** sehen darf **und** den Zieldatensatz schreiben darf; sonst könnte ein Leser über den Datensatz das Dokument an weitere Datensätze hängen und so immer weiter freigeben |
| **Hochladen am Datensatz** | wer den Datensatz schreiben darf; das Dokument entsteht im Ablageordner des Modells (mit erhöhten Rechten) und wird sofort verknüpft |
| **Verweis lesen** | wie das Dokument |

- **Umsetzung (in Schritt 0 gebaut und getestet, §8):** Die Ordnerregel (`int_filemanager_document_rule_user`) und die Mehrfirmenregel bleiben
  unverändert. Neu ist eine **zweite Gruppenregel** auf `base.group_user`, nur Lesen, mit der Domain `[('access_via_record', '=', True)]`. `access_via_record` ist
  ein nicht gespeichertes, **durchsuchbares Berechnungsfeld** am Dokument. Odoo verknüpft die Gruppenregeln mit ODER, die globale Mehrfirmenregel mit
  UND; damit gilt „Ordner oder Datensatz, und die Firma stimmt“ ohne Eingriff in `_search` oder `_check_access`.
  - **Suchmethode** (SQL): je verknüpfbarem Modell `Domain('link_ids', 'any!', [('res_model', '=', M), ('res_id', 'in', <M>._search([]))])`, ODER-verknüpft;
    das ist die Teilabfrage von `ir.attachment._search`, nur als Feldsuche.
  - **Berechnung** (Python): `_check_access` wertet Regeln mit `filtered_domain` auf `sudo()`-Datensätzen aus (`models.py`, `_check_access`); das Feld
    rechnet deshalb für jedes Dokument, ob mindestens ein verknüpfter Datensatz für den Nutzer lesbar ist.
  - **Vorbilder im Core:** `ir.attachment` (`_check_access`/`_search`) und `mail.activity` (Regel plus `_check_access`/`_search` über den verknüpften
    Datensatz), dazu `mail.message` (`_search`). Alle drei überschreiben `_search`/`_check_access`. Hier genügt das Feld, weil die Regelmaschine den
    Rest erledigt. Die Dokumentation nennt genau diesen Weg: Gruppenregeln vereinigen sich und „können Zugriff erweitern“
    (`docs/odoo19_reference/backend/security.md`, Abschnitt „Record Rules“).
  - **Der Core-Weg als Alternative** (nicht gebaut, nicht getestet): `_check_access` überschreiben und die von der Regel abgelehnten Dokumente
    nachträglich über den verknüpften Datensatz freigeben (so macht es `mail.activity` bei `write`/`unlink`; die Regel muss dafür **nicht**
    nachgebaut werden). Für `_search` gibt es im Core keine Vorlage für „Regel ODER Datensatz“: `mail.activity` und `mail.message` lassen großzügige
    Regeln stehen und filtern die Zeilen danach in Python (bei 400.000 Dokumenten zu langsam), `ir.attachment` nutzt eine SQL-Teilabfrage ohne
    Regeln. Es bliebe eine eigene Zusammensetzung aus beiden, mit eigener Behandlung der Mehrfirmenregel.
  - Einen Core-Fall, in dem eine Regel ein solches Berechnungsfeld nutzt, um andere Datensätze abzufragen, habe ich nicht gefunden (grobe Suche,
    kein Beweis, dass es keinen gibt).
  - **Zwei Fallen, beide belegt:** (1) Odoo optimiert die Regel-Domain mit `self.sudo()` (`models.py`, `_search`): Suchmethode **und** Berechnung müssen
    den Nutzer wiederherstellen (`with_user(self.env.uid)`), sonst werden Datensätze anderer Firmen mitgezählt (Test 05 schlug so fehl). (2) Ein Nutzer
    mit Leserecht in der ACL, auf den keine Regel passt, sieht **alles**: die Regel auf `base.group_user` muss immer aktiv bleiben (Test 02).
- **Einfachere Variante nicht verwenden:** eine Gruppenregel mit `user.env[…].search([]).ids` in der Domain wird von Odoo zwischengespeichert
  (`ir.rule._compute_domain` ist `ormcache`d). Gemessen: Ein neu verknüpfter Datensatz bleibt für den Nutzer unsichtbar, bis der Zwischenspeicher
  geleert wird (Test 30).
- **Anlegen:** `ir.model` ist für normale Nutzer nicht lesbar; `create()` des Verweises liest `res_model_id.model` mit `sudo()` (wie `mail.activity`).
- **ACL:** `base.group_user` lesen auf Dokument und Verweis (nötig für den Weg über den Datensatz; sichtbar wird nur, was die Prüfung freigibt);
  Schreiben, Anlegen und Löschen weiter nur `int_filemanager_group_user` und, wo oben beschrieben, die Prüfung in `create()`/`unlink()`.
  Textmodelle bleiben nur für Administratoren lesbar.
- Schaltfläche und Reiter sind für jeden Nutzer sichtbar, der den Datensatz sieht; sie zeigen nur, was die Prüfung freigibt.

### 3.4 Verbindungsmodule

| Modul | Hängt an | Inhalt |
|---|---|---|
| (im Kern) | `res.partner` | Mixin erben, Schaltfläche und Reiter am Kontakt |
| `int_filemanager_repair` | `repair` | dasselbe am Reparaturauftrag; **kein** Eingriff in `int_repair_workshop` (dessen Listenansicht bleibt eine reine Werkstattübersicht) |
| `int_filemanager_sale`, `_purchase`, `_account`, `_fleet` | je App | nach Bedarf, jedes nur Mixin + Schaltfläche |

Jedes Verbindungsmodul besteht aus `_inherit = [<Modell>, "int.filemanager.linkable"]`, einer Schaltfläche in der Formularansicht, einem Eintrag
in `de.po` und einem Test. Keine Logik, die nicht im Mixin steht.

### 3.5 Prüfungen vor „fertig“

Modultests in der Wegwerf-Datenbank (`tools/check/tests.sh`):
- Eindeutigkeit, Zähler, `document_search`, Mehrfirmen, Chatter-Notizen.
- **Rechte über den Datensatz:** ein Nutzer ohne Ordnerzugriff und ohne Gruppe sieht das Dokument über den lesbaren Datensatz, nicht über einen anderen;
  er kann es weder ändern noch löschen noch weiter verknüpfen; verliert er das Lesen am Datensatz, verliert er das Dokument.
- **Rechte über den Ordner:** wie bisher; Verknüpfen ohne Schreibrecht am Ziel scheitert.
- Dokument in einen anderen Ordner verschieben: Verweise bleiben, die Sichtbarkeit über den Datensatz bleibt.
- Hochladen am Datensatz mit und ohne Ablageordner; das Dokument ist danach nur über Ordner-Weg oder Datensatz-Weg sichtbar.
- Löschen des Ziels entfernt die Verweise; der Autovacuum räumt Verwaiste.
- Sichtbarkeit sofort nach Änderung am Datensatz (Zwischenspeicher-Falle, §3.3).
- Geschwindigkeit des Dokumentverzeichnisses mit der zusätzlichen Prüfung bei vielen Dokumenten und wenigen/vielen Verweisen.

Dazu `check.sh` (odoo-ls, `test_lint`) und pre-commit. Vor dem Bauen die passenden Originalseiten für ORM, Sicherheit, Mixins, Views, Daten/Manifest und Tests
über `docs/odoo19_reference/INDEX.md` sowie die Owl-Referenz öffnen und das Verhalten im passenden Odoo-19-Core prüfen.

## 4. Reihenfolge

1. **Schritt 0 (erledigt 2026-10-16):** Rechtemodell, Zwischenspeicher, Schreibprüfung am Ziel, Aufräumen und Geschwindigkeit in einer
   Wegwerf-Datenbank geprüft, Ergebnisse in §8.
2. Funktion 1 mit dem Kern und `res.partner`, danach `int_filemanager_repair` (Werkstatt zuerst, siehe §8).
3. Scan-Eingang über einen Ordner und das vorhandene Einlesen (§5).
4. Nr. 5 für neue Dokumente; Nr. 3 erst, wenn die Buchhaltung in Odoo läuft; Nr. 2 erst nach der Mail-Einrichtung.

## 5. Weitere Funktionen (nur Skizze, je eigener Entwurf vor dem Bau)

| Nr. | Funktion | Stand | Kern und Voraussetzung |
|---|---|---|---|
| – | **Scan-Eingang über Ordner** | vorhanden, nur Ablauf | Der Scanner legt Dateien in einem Ordner auf dem Share ab, das Einlesen (manuell gestartet) holt sie ab; danach Zuordnung am Datensatz. Braucht keine Mail. |
| 2 | **E-Mail an Ordner** | zurückgestellt | Ordner erbt `mail.alias.mixin.optional` (eigene Adresse, z. B. `scan@…`). Eigene `message_new`, die aus jedem Anhang ein Dokument macht: die Standardfassung legt nur einen Datensatz aus dem Betreff an und speichert keine Anhänge. Voraussetzung: Alias-Domain und Postfach in Odoo. Auf Live gibt es beides nicht (§8). |
| 3 | **Dokument → Eingangsrechnung** | zurückgestellt bis Buchhaltung | Button am PDF/XML ruft `account.journal._create_document_from_attachment` auf; XRechnung/ZUGFeRD liest `account_edi_ubl_cii` nativ. Die Datei wird dafür einmal als `ir.attachment` kopiert (Größengrenze, §8); Rückverweis Beleg ↔ Dokument über Funktion 1. |
| 4 | ~~Ordner zum Datensatz~~ | **gestrichen** | Würde neben der Fileserver-Struktur eine zweite, kundenbezogene aufbauen; widerspricht §2. Ersetzt durch den Ablageordner je Modell (§3.2). |
| 5 | **Zuordnungsvorschlag aus dem Text/Namen** | nach Funktion 1 | Rechnungsnummer aus dem Dateinamen (auf dem Fileserver heißen Ausgangsrechnungen nach ihrer Nummer), später Auftrags-, Kunden- und weitere Nummern aus dem OCR-Text; als Vorschlag zum Bestätigen. Der Altbestand lässt sich erst zuordnen, wenn die Datensätze in Odoo existieren (Datenübernahme). |
| 6 | **Erzeugte Belege ablegen** | später | Angebot, Rechnung, Lieferschein, Reparaturbericht werden beim Erzeugen als Dokument im Ablageordner des Modells abgelegt und verknüpft. Keine Aussage zu GoBD (Rechtsfrage, Steuerberater). |
| 7 | **Dokument per Mail senden** | später | Dokumente als Anhang im Mail-Assistenten; wie Nr. 3 eine temporäre `ir.attachment`-Kopie; zusätzlich gilt Odoos eigene Mailgrenze. |
| 8 | **Teilen mit Kunden** (Portal) | zuletzt | `portal.mixin`-Token mit Ablauf, nur ausdrücklich freigegebene Dokumente. Zuletzt, weil private Dateien im selben Speicher liegen. |

## 6. Abgrenzung

- Kein Ersatz für Chatter-Anhänge und kein Umzug alter Anhänge; `product.document` bleibt für Produktdatenblätter, wie es ist.
- Keine Odoo-Enterprise-Funktionen (Documents-App) und keine harte Abhängigkeit des Kerns von einer Business-App.
- Der Filemanager passt Odoo nicht an die Ordnerstruktur des Fileservers an (§2).
- Versionen, Portal und Office im Browser sind weiter nicht Teil des Moduls (siehe README).

## 7. Belege zum Odoo-19-Kern (Quelltext, Branch 19.0)

| Aussage | Fundstelle |
|---|---|
| Verweis als `res_model` (Char) + `res_id` (`Many2oneReference`), Index auf beide | `odoo/addons/base/models/ir_attachment.py`: `res_model`, `res_id`, `_res_idx` |
| Ein Anhang ist zugänglich, wenn der verknüpfte Datensatz es ist; `create`/`unlink` zählen als `write` am Ziel | `ir_attachment.py`: `_check_access`, `_inaccessible_comodel_records` |
| Suche: Teilabfrage `res_id in (<Modell>._search(…))` für bis zu fünf Modelle, sonst Stapelprüfung in Python | `ir_attachment.py`: `_search` |
| Dasselbe Muster bei Followern; `res_model_id` als Many2one mit `ondelete='cascade'` bei Aktivitäten | `addons/mail/models/mail_followers.py`, `mail_activity.py` |
| One2many über ein `Many2oneReference` ergänzt den Filter auf das Modell | `odoo/orm/fields_relational.py`: `_additional_domain` |
| Kaskade über (`res_model`, `res_id`) nicht möglich, Aufräumen von Hand im `unlink` | `addons/mail/models/mail_thread.py`: `unlink` (Kommentar) |
| `any` wendet die Regeln des Comodells an, `any!` umgeht sie | `fields_relational.py`: `bypass_search_access`, `any!`; `any` in Regeln: `addons/project/security/project_security.xml` |
| Verbindungsmodule mit `auto_install` | `addons/account_fleet`, `hr_fleet`, `sale_project`: `__manifest__.py`; Referenz: `docs/odoo19_reference/backend/module.md` |
| Eingangsrechnung aus Anhängen | `addons/account/models/account_journal.py`: `_create_document_from_attachment`; `account_document_import_mixin.py`: `_create_records_from_attachments` |
| Standard-`message_new` speichert keine Anhänge als Dokument | `addons/mail/models/mail_thread.py`: `message_new` |
| Alias für beliebige Modelle | `addons/mail/models/mail_alias_mixin_optional.py` |
| Mailgrenze `base.default_max_email_size` (Standard 10 MB) | `odoo/addons/base/models/ir_mail_server.py`: `_get_max_email_size` |
| Produktdokumente im Kern | `addons/product/models/product_document.py` |

## 8. Entscheidungen, Befunde, Offenes

### Entschieden

1. **Rechte: Der Datensatz hat Vorrang** (Nutzer, 2026-10-16), Modell in §3.3. Begründung: Der Datenbestand auf der Platte kann später anders gegliedert
   sein; langfristig sollen die Möglichkeiten von Odoo genutzt werden und Odoo nicht dem aktuellen Bestand angepasst werden.

### Empfehlungen, vom Nutzer noch nicht bestätigt

Befunde stammen von Live (HM-SRV, 2026-10-16, nur lesend).

2. **Ordnerstruktur auf dem Fileserver.** Befund: Ablage nach Belegart und Zeitraum (`Kaufmännische Belege/Ausgangsrechnung/<Jahr>/<MM-JJJJ>/…`), keine
   Kundennummer im Pfad; Ausgangsrechnungen heißen nach ihrer Nummer (`260892.pdf`, Annahme aus fortlaufenden Namen); Auftragsbestätigungen uneinheitlich.
   Empfehlung: Nr. 4 streichen, Nr. 5 über Dateinamen und Text; Altbestand erst nach der Datenübernahme zuordnen.
3. **Alias-Domain und Postfach.** Befund: keine Alias-Domain, kein Ausgangs- oder Eingangs-Mailserver, `fetchmail_server` leer, `microsoft_outlook`
   installiert, aber nicht eingerichtet. Empfehlung: Nr. 2 zurückstellen (gemeinsames Postfach in Office 365 und Azure-Freigabe sind ein IT-Vorhaben);
   Scans bis dahin über Ordner und Einlesen.
4. **Werkstatt oder Buchhaltung zuerst.** Befund: 5 Reparaturaufträge, 1 Angebot, 1 Fahrzeug, 0 Rechnungen, 0 Einkaufsaufträge; Eingangsrechnungen laufen
   über PaperOffice. Empfehlung: Werkstatt zuerst (`int_filemanager_repair`), Nr. 3 erst mit der Buchhaltung.
5. **Größengrenze der temporären Kopie als `ir.attachment`.** Befund: Odoos Mailgrenze steht auf 10 MB. Empfehlung: Systemparameter, Vorschlag 25 MB
   (Setzung, kein Messwert), für den Mailversand zusätzlich Odoos eigene Mailgrenze.

### Schritt 0 (2026-10-16): getestet in einer Wegwerf-Datenbank auf HM-SRV

Prototyp als Wegwerf-Modul `s0_probe` (nicht im Repo), 18 Tests grün, Postgres 17, Image `int-filemanager-odoo:19.0-ocr`, Live nicht berührt.

- **Rechtemodell (§3.3):** bestätigt. Ein Nutzer ohne Gruppe und ohne Ordnerzugriff sieht ein Dokument über einen lesbaren Datensatz, kann es lesen,
  aber nicht ändern oder löschen; ein Datensatz einer fremden Firma gibt nichts frei; die Mehrfirmenregel des Dokuments gilt weiter; Verschieben in einen
  anderen Ordner ändert nichts an den Verweisen; Administratoren sehen alles.
- **Verknüpfen und Lösen:** nur mit Ordnerzugriff auf das Dokument (wer es nur über den Datensatz sieht, kann es nicht weitergeben) und Schreibrecht am
  Ziel; geprüft für `res.partner` und für `res.country` (kein `mail.thread`).
- **Aufräumen:** Löschen des Ziels entfernt die Verweise über den Mixin (`res.partner` mit `mail.thread` und `res.country` ohne), Löschen des Dokuments
  über `ondelete='cascade'`, der Autovacuum entfernt Verweise auf per SQL gelöschte Datensätze.
- **Suche „Dokument enthält“ am Datensatz** (`link_ids any document_id any content_search`): gibt nur Datensätze zurück, über die der Nutzer die
  Dokumente sehen darf.
- **Zwischenspeicher:** die einfache Regel veraltet (belegt), die Feld-Variante nicht.
- **Geschwindigkeit** (400.000 Dokumente, 300 Ordner, 20.000 Verweise auf 5.000 Datensätze; Nutzer mit Zugriff auf ein Drittel der Ordner):

  | Abfrage | nur Ordnerregel | mit Datensatzweg |
  |---|---|---|
  | Anzahl, Nutzer mit Ordnerzugriff | 0,08 s | 0,29 s |
  | Liste (80, absteigend), Nutzer mit Ordnerzugriff | 0,003 s | 0,014 s |
  | Namenssuche, Nutzer mit Ordnerzugriff | 0,12 s | 0,12 s |
  | Anzahl, Nutzer nur über Datensatz | – | 0,02 s |
  | Zähler „Dokumente“ für 80 Datensätze | < 0,01 s | 0,006 s |

  Ungünstigster Fall (alle 400.000 Dokumente verknüpft, 20.000 Datensätze): Anzahl für den Nutzer mit Ordnerzugriff 1,3 s, Liste (80) 0,19 s,
  Namenssuche 0,30 s; Nutzer nur über Datensatz: Anzahl 0,16 s, Liste (80) 0,012 s. Die Anzahl am Listenende ist der teuerste Posten; die Liste selbst
  bleibt schnell. Es ist ein synthetischer Bestand (gleichmäßig verteilt, 300 statt ~29.000 Ordner), kein echter.
- **Noch offen:** kein Test mit den echten 29.000 Ordnern und echten Namen; kein Test von Download, Vorschau und `ocr_content` über den Datensatzweg
  (laufen im Prototyp nicht über denselben Code wie im Modul; sie prüfen den Zugriff am Dokument, sollten also mitziehen); Chatter-Notizen und
  Ablageordner sind nicht Teil des Prototyps.
