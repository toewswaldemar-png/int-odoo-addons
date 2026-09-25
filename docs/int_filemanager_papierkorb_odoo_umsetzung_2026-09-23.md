# int_filemanager: Papierkorb — optimale Umsetzung, geprüft am echten Odoo-19-Quellcode

Stand 2026-09-23. Ergänzt [`int_filemanager_feature_ideen_2026-09-21.md`](int_filemanager_feature_ideen_2026-09-21.md)
(dort Punkt A1: fehlender Papierkorb als auffälligster Fund) und
[`erp-odoo-vs-cloudreve-vergleich-2026-09-21.md`](erp-odoo-vs-cloudreve-vergleich-2026-09-21.md)
(dort die erste, noch grobe Skizze "`active`/`deleted_at`-Feld statt `.trash`-Unterordner"). Dieses
Dokument prüft diese Skizze **direkt am lokal geklonten Odoo-19-Quellcode**
(`C:\Users\Admin\Documents\GitHub\odoo`, Branch `19.0`) nach — mit Datei-/Zeilenangaben, nicht nur
Erinnerung — und gleicht sie mit dem tatsächlichen `int_filemanager`-Code ab. Reine Analyse, nichts
umgesetzt.

**Nachtrag 2026-09-24: Dieses Dokument war gegenstandslos, als es geschrieben wurde.** Der
Papierkorb existierte bereits seit dem 2026-09-21 (Commit `b53fed2`, zwei Tage vor diesem
Dokument) — allerdings über ein eigenes `trashed`-Boolean-Feld mit `.trash/`-Unterbaum, nicht über
das hier geplante `active`. Der komplette unten stehende Plan wurde also nie gebraucht. Die
tatsächlich noch offene, echte Lücke: der tägliche Vollscan prüft beim Stale-Abgleich nicht auf
`trashed`/`.trash`-Präfix und läuft mit `sudo()` (an `rule_file_trash_visibility` vorbei) — ein in
den Papierkorb verschobener Eintrag kann dadurch beim nächsten 03:00-Lauf **endgültig** gelöscht
werden statt erst nach der Aufbewahrungsfrist (Fund B1). Vollständige Analyse inkl. Migrationsplan
`trashed` → natives `active` in `int_filemanager_konzept_db_vorrang_2026-09-24.md`
(Branch `docs/konzept-db-vorrang`), Abschnitte 16.1 und 16.2. Der Rest dieses Dokuments bleibt nur
als Beleg stehen, wie Odoos `active`-Mechanismus grundsätzlich funktioniert — nicht als gültiger
Bauplan.

---

## 1. Odoo hat kein natives "Papierkorb"-Konzept — nur "Archivieren"

Direkt geprüft: keine Treffer für `recycle`/`trash` als echtes Feature irgendwo im Odoo-19-
Kerncode (nur zufällige Wortfragmente in `.po`-Übersetzungsdateien, kein Code). Das einzige
native Bordmittel in diese Richtung ist die **Archivieren/Dearchivieren**-Mechanik über ein Feld
namens `active` — dieselbe Funktion hinter dem in fast jeder Odoo-Liste bekannten
"Archiviert"-Filter. Wichtig für die Erwartungshaltung: das ist konzeptionell näher an "dauerhaft
ausblenden, jederzeit reaktivierbar" als an einem echten Papierkorb mit automatischer
Endgültig-Löschung nach Frist — letzteres muss on top selbst gebaut werden (Abschnitt 5).

---

## 2. Der `active`-Mechanismus im Detail (mit Quellcode-Beleg)

**Automatische Erkennung, kein Registrierungsaufwand** (`odoo/orm/model_classes.py:443-453`):

```python
elif 'active' in model_cls._fields:
    model_cls._active_name = 'active'
```

Ein Feld, das exakt `active = fields.Boolean(...)` heißt, wird von Odoo automatisch als
Archivierungsfeld erkannt — keine explizite Konfiguration nötig.

**Automatische Filterung in jedem `search()`** (`odoo/orm/models.py:5368-5376`):

```python
domain = Domain(domain)
# inactive records unless they were explicitly asked for
if (
    self._active_name
    and active_test
    and self.env.context.get('active_test', True)
    and not any(leaf.field_expr == self._active_name for leaf in domain.iter_conditions())
):
    domain &= Domain(self._active_name, '=', True)
```

Drei Wege, wie sich das steuern lässt — entscheidend für den Papierkorb-Entwurf:
1. **Normale Suche** (kein `active` in der Domain erwähnt) → automatisch nur `active=True`-Zeilen.
2. **`with_context(active_test=False)`** → zeigt alles, aktiv und inaktiv.
3. **Domain erwähnt `active` bereits explizit** (z.B. `[('active', '=', False)]`) → die
   Auto-Filterung wird **übersprungen** (`not any(leaf.field_expr == self._active_name ...)`),
   der Aufrufer bekommt exakt das, was er verlangt hat — **das ist der native Weg, eine
   "Papierkorb"-Ansicht zu bauen**: eine Search-View/Domain, die gezielt `active=False` filtert,
   ganz ohne Zusatzkonzept.

**Native Aktionen, aber Achtung — API-Änderung in 19.0** (`odoo/orm/models.py:5802-5830`):

```python
@api.deprecated("Deprecated since 19.0, use action_archive or action_unarchive")
def toggle_active(self):
    ...

def action_archive(self):
    """Set :attr:`active` to ``False`` on a recordset for active records."""
    ...

def action_unarchive(self):
    """Set :attr:`active` to ``True`` on a recordset for inactive records."""
    ...
```

`toggle_active()` ist **seit Odoo 19.0 offiziell deprecated** — für eine Neuentwicklung auf dieser
Version sind `action_archive()`/`action_unarchive()` die richtige, zukunftssichere Wahl, nicht die
in älteren Tutorials/Trainingsdaten oft noch genannte `toggle_active()`.

---

## 3. Warum das der strukturell richtige Baustein ist — nicht nur "auch möglich"

Der entscheidende Vorteil gegenüber einem selbst gebauten `deleted_at`/`is_deleted`-Feld (wie es
z.B. Cloudreve mit seinem `CommonMixin` macht, siehe Vergleichsdokument): **jede bestehende
`search()`-Aufrufstelle im gesamten `int_filemanager`-Code filtert automatisch mit**, ohne dass
auch nur eine einzige Zeile davon angefasst werden müsste — die Listenansicht, `acl_rules.py`s
Multi-Kontext-Selbsttest, der Watcher/Scan-Reconciliation-Code, die ONLYOFFICE-Bridge, die
Duplikat-/Volltextsuche. Bei einem Custom-Feld müsste **jede** dieser Stellen einzeln um
`('is_deleted', '=', False)` ergänzt werden — fehleranfällig und sicherheitsrelevant (eine
vergessene Stelle könnte gelöschte Dateien in ACL-Auswertungen oder Suchergebnissen wieder
auftauchen lassen). Das ist exakt das Risiko, das der etablierte Sorgfaltsgrad dieses Moduls
(Multi-Kontext-Selbsttest bei jeder ACL-Änderung, siehe `int_filemanager_ausbau.md` Phase 2)
konsequent vermeiden will.

---

## 4. Die eigentliche Komplexität liegt nicht im Odoo-Feld, sondern in der Interaktion mit dem bestehenden Lösch-/Watcher-Code

Hier zeigt sich, warum "einfach ein `active`-Feld ergänzen" allein **nicht** reicht — am
tatsächlichen `int_filemanager`-Code geprüft:

**`controllers/main.py:264-280`** (`delete()`) löscht heute physisch **und** ruft danach selbst
`index_remove_tree()` auf:

```python
if os.path.isdir(abs_path):
    shutil.rmtree(abs_path)
else:
    os.remove(abs_path)
index_remove_tree(request.env, rel)
```

**`index_utils.py:114-122`** (`index_remove_tree()`) — dieselbe Funktion, die **auch** der Watcher
bei jedem beobachteten Datei-Verschwinden aufruft (egal ob ausgelöst durch diesen Controller, einen
externen SMB-Client oder den Reconciliation-Scan) — macht ein **hartes** `unlink()`:

```python
Model.search([...]).unlink()
```

**Konsequenz für einen Papierkorb-Entwurf:** Es reicht nicht, `delete()` nur um
`action_archive()` statt physischem Löschen zu ergänzen — dabei müssen **zwei unabhängige
Auslöser** von `index_remove_tree()`/`unlink()` bedacht werden:

1. **Der Controller selbst** darf bei "Papierkorb" natürlich nicht mehr `index_remove_tree()`
   (= hartes `unlink()`) aufrufen — stattdessen `action_archive()` auf dem Datensatz.
2. **Der Watcher** beobachtet weiterhin denselben Pfad per inotify. Bleibt die Datei physisch am
   selben Ort liegen (reine Feld-Änderung ohne Verschieben), sieht der Watcher gar kein
   DELETE-Ereignis — unproblematisch, aber dann taucht die "gelöschte" Datei bei einem externen
   Zugriff (SMB, direkter Server-Zugriff) weiterhin normal im Dateisystem auf, was dem
   Papierkorb-Gedanken widerspricht (die Datei sollte auch auf Dateisystemebene "weg vom
   ursprünglichen Ort" sein). **Wird die Datei dagegen zusätzlich physisch in einen
   Trash-Unterordner verschoben** (der naheliegendere, konsistentere Ansatz, siehe Abschnitt 5),
   entsteht am ursprünglichen Pfad ein echtes DELETE-Inotify-Ereignis — genau das würde vom
   Watcher aktuell **unbedingt** in `index_remove_tree()`/`unlink()` münden und den gerade erst
   liebevoll archivierten Datensatz sofort wieder hart löschen, den Papierkorb-Mechanismus also
   augenblicklich aushebeln. **Der Watcher-Pfad braucht deshalb einen expliziten Schutz:** ein
   DELETE-Ereignis für einen Pfad, dessen zugehöriger Datensatz bereits `active=False` ist (vom
   Controller absichtlich gerade eben gesetzt), darf `index_remove_tree()` **nicht** aufrufen,
   sondern muss dieses Ereignis als erwartete Nebenwirkung des eigenen Verschiebens erkennen und
   ignorieren — sonst gewinnt in der Praxis meist der Watcher (asynchron, per inotify) gegen den
   synchronen Controller-Aufruf, mit nicht-deterministischem Ausgang je nach Timing.

Das ist keine triviale Ein-Zeilen-Änderung, sondern berührt mindestens: `controllers/main.py`
(neue Verschieben-statt-Löschen-Logik), `index_utils.py`/`watcher.py` (Guard gegen versehentliches
Hart-Löschen bereits archivierter Datensätze), plus die in Abschnitt 5 skizzierten neuen
Bausteine.

---

## 5. Konkreter Bauplan (nicht umgesetzt, nur entworfen)

1. **Neues Feld** `active = fields.Boolean(default=True, index=True)` auf
   `int_filemanager.file` — keine Migration von Bestandsdaten nötig (Default `True` deckt alle
   bestehenden Zeilen automatisch ab).
2. **`delete()`-Route umbauen:** statt `shutil.rmtree`/`os.remove` die Datei/den Ordner physisch in
   einen versteckten Trash-Unterordner innerhalb des konfigurierten Stammverzeichnisses
   verschieben (z.B. `.trash/<uuid>/<urspruenglicher-name>`, damit Namenskollisionen beim
   mehrfachen Löschen gleichnamiger Dateien unmöglich sind und der Originalname fürs
   Wiederherstellen erhalten bleibt), danach `record.action_archive()` statt
   `index_remove_tree()`.
3. **Watcher-Guard:** im DELETE-Handler (`watcher.py`/`index_utils.py`) vor jedem
   `index_remove_tree()`-Aufruf prüfen, ob der zugehörige Datensatz bereits `active=False` ist —
   falls ja, Ereignis ignorieren (erwartete Nebenwirkung des eigenen Verschiebens), kein
   `unlink()`. Der `.trash/`-Unterordner selbst sollte vom Watcher/Scan konsequent ausgenommen
   werden (analog zu bereits bestehenden Pfad-Ausschlüssen im Modul), damit die dorthin
   verschobenen Dateien nicht versehentlich erneut als "neue" Dateien indexiert werden.
4. **Neue Route** `/int_filemanager/restore` (analog zu `version_restore`): Datei aus dem
   Trash-Unterordner zurück an den ursprünglichen (gespeicherten) Pfad verschieben,
   `record.action_unarchive()`. Konfliktfall (am Zielort existiert inzwischen wieder eine Datei
   mit demselben Namen) explizit behandeln, nicht stillschweigend überschreiben.
5. **Papierkorb-Ansicht:** eine Search-View/Menüpunkt mit Domain `[('active', '=', False)]` —
   nach Abschnitt 2 reicht das allein schon aus, damit Odoos Auto-Filterung nicht eingreift, kein
   Sonderparameter/`active_test`-Trick nötig. "Wiederherstellen"/"Endgültig löschen" als
   `ActionMenus`-Einträge, demselben Muster folgend, das `int_filemanager`s native UI bereits für
   Freigeben/Verknüpfen/Umbenennen nutzt.
6. **Retention-Cron:** wie in `int_filemanager_feature_ideen_2026-09-21.md` (Punkt I2) bereits
   skizziert — ein `ir.cron`, der Papierkorb-Einträge älter als X Tage endgültig entfernt (echtes
   `unlink()` **und** physisches Löschen aus `.trash/`), demselben etablierten Cron-Muster
   folgend, das bereits für Version-Pruning existiert.
7. **ACL-Konsequenz, unbedingt zu bedenken:** `acl_rules.py`s generierte `ir.rule`-Domains
   arbeiten bereits mit expliziten Pfad-Bedingungen — zu prüfen, ob eine dort erzeugte Domain
   jemals selbst das `active`-Feld referenziert (aktuell nicht der Fall, also unproblematisch,
   aber bei künftigen Änderungen an `acl_rules.py` im Hinterkopf behalten: sollte dort je eine
   Domain versehentlich `active` explizit erwähnen, würde das laut Abschnitt 2 Odoos
   Auto-Filterung für genau diese Regel abschalten).

---

## 6. Empfehlung

Odoos `active`-Mechanismus ist der eindeutig richtige Unterbau (kostenlos für den gesamten
bestehenden Code, native Actions, kein Sonderweg) — aber **nicht** als reiner Ein-Feld-Zusatz,
sondern nur in Kombination mit dem physischen Verschieben in einen Trash-Unterordner **und** dem
beschriebenen Watcher-Guard. Wird nur das Feld ergänzt, ohne den Watcher-Konflikt zu lösen, ist das
Ergebnis bestenfalls ein "Archivieren"-Filter (Datei bleibt sichtbar am alten Platz im
Dateisystem, nur in Odoo ausgeblendet) — kein echter Papierkorb im vom Nutzer gemeinten Sinn
(Datei ist weg, aber wiederherstellbar). Umsetzungsreihenfolge wie in Abschnitt 5 nummeriert;
Punkt 3 (Watcher-Guard) ist der sicherheitsrelevanteste Teil und sollte vor jedem Live-Test zuerst
durch einen gezielten Test abgedeckt werden (Datei löschen → prüfen, dass der Datensatz danach
weiterhin existiert und `active=False` ist, nicht komplett aus der DB verschwunden).
