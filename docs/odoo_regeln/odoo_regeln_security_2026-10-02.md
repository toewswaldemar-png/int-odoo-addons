# Odoo 19 Regeln: Sicherheit (Destillat)

Quellen (nur diese): Odoo-19-Core (Branch 19.0) und die offizielle Entwicklerdokumentation
`developer/reference/backend/security`
(<https://www.odoo.com/documentation/19.0/developer/reference/backend/security.html>).
**Rangfolge: Core-Code vor Dokumentation.** Wo die Dokumentation veraltet ist, steht hier der Core-Stand.
Geprüft: 2026-10-02, Korrekturen gegen den Core: 2026-10-08.

## 1. Zugriffsmodell

Zwei datengetriebene Mechanismen, beide an **Gruppen** (`res.groups`) gebunden; ein Nutzer hat beliebig viele
Gruppen. Dazu Feldzugriff (`groups=` am Feld) und eigener Code.

### Gruppen (`res.groups`)
- `name` (Rolle/Zweck), `privilege_id` (`res.groups.privilege`: bündelt Gruppen eines Bereichs, hat die Modulkategorie `category_id`
  → exklusive Auswahl im Nutzerformular; Core-Stand 19.0: `res.groups` selbst hat kein `category_id` mehr, die Doku nennt es noch dort),
  `implied_ids` (Pseudo-Vererbung: eine implizierte Gruppe kann einem Nutzer **explizit entzogen**
  werden, ohne die implizierende zu entfernen), `comment`.
- Am Nutzer: `group_ids` (explizit zugewiesen), `all_group_ids` (einschließlich impliziter). `user.has_group('modul.xmlid')`
  (Core: `res.users.has_group`) darf nur für den eigenen Nutzer, im sudo-Modus oder von einem internen Nutzer aufgerufen werden
  (sonst `AccessError`); `base.group_no_one` wirkt nur im Debug-Modus.

### Access Rights (`ir.model.access`, CSV)
- Gewähren Zugriff auf ein **ganzes Modell** je Operation (`perm_create/read/write/unlink`, alle standardmäßig aus).
- **Ohne passenden Eintrag: kein Zugriff** (default-deny).
- **Additiv:** Rechte eines Nutzers = Vereinigung über alle seine Gruppen.
- `group_id` leer = **jeder Nutzer**, auch Portal und Public → nur bewusst leer lassen.

### Record Rules (`ir.rule`)
- Bedingungen, die **je Datensatz** gelten, nach den Access Rights ausgewertet. **Default-allow**: gewähren die
  Access Rights Zugriff und keine Regel greift, ist der Zugriff erlaubt.
- `domain_force` ist ein **Python-Ausdruck** mit den Variablen `time`, `user` (Singleton), `company_id`
  (einzelne ID), `company_ids` (Liste der **aktivierten** Firmen). Bei `_inherits`-Modellen gelten die Regeln der Elternmodelle mit.
- `perm_*` haben **andere Semantik** als bei ACL: sie geben an, **für welche Operation** die Regel gilt;
  nicht gewählt = Regel wird dafür nicht geprüft. Standard: alle gewählt.
- **Global** (keine Gruppe) vs. **Gruppe:**
  - Globale Regeln **schneiden** sich (alle müssen erfüllt sein) → sie schränken immer weiter ein.
  - Gruppenregeln **vereinigen** sich (eine genügt) → sie können Zugriff erweitern, aber nicht über die globalen
    Grenzen hinaus.
  - Globale und Gruppen-Regelsatz **schneiden** sich: die erste Gruppenregel auf einen globalen Satz schränkt ein.
- **GEFAHR:** mehrere globale Regeln können nicht überlappende Mengen ergeben → **kein Zugriff mehr**. Globale
  Regeln sparsam, jede einzeln begründen und testen.

### Feldzugriff
- `groups="mod.group_a,mod.group_b"` (kommagetrennte XML-IDs). Gehört der Nutzer zu keiner: Feld wird aus Views
  entfernt, aus `fields_get` entfernt, explizites Lesen/Schreiben → Zugriffsfehler.
- Core-Stand: der Superuser (sudo-Modus) umgeht `groups` an Feldern überall (`_has_field_access` in `odoo/orm/models.py`,
  auch von `fields_get` benutzt).

## 2. Security Pitfalls (verbindlich)

### Öffentliche Methoden
- **Jede öffentliche Methode ist per RPC mit frei gewählten Parametern aufrufbar.** Methoden mit `_`-Präfix sind
  von Action-Buttons und externer API aus **nicht** aufrufbar.
- In öffentlichen Methoden sind **Datensatz und Parameter nicht vertrauenswürdig**; ACL wird nur bei CRUD geprüft.
  Berechtigung selbst prüfen (`self.env.user.has_group(...)`), dann die eigentliche Arbeit in eine **private**
  Methode legen.
- **Privat allein reicht nicht** – die private Methode muss richtig benutzt werden (Beispiel der Quelle:
  `_set_state` ruft `sudo().write`, wird nur nach Rechteprüfung aufgerufen).

### ORM nicht umgehen
- **Nie** `cr` direkt benutzen, wenn das ORM dasselbe kann (verloren gehen Übersetzung, Cache-Invalidierung,
  `active`, Zugriffsrechte; Code wird schwerer lesbar und unsicherer).
- Stufen der Quelle: String-Verkettung = "very very wrong"; `cr.execute` mit Parameter-Tupel = "no injection, but
  still wrong"; `env.execute_query(SQL(...))` = "nearly there"; **`search([...])` = "better"**.

### SQL-Injection
- **Nie** Variablen per `+` oder `%` in den SQL-Text einsetzen. Formatierung der Parameter ist Aufgabe der
  Datenbank-Schicht (psycopg2), nicht des Entwicklers (Listen → `IN %s` mit `tuple(ids)`).
- Besser: **`odoo.tools.SQL`** mit Template (`SQL("… WHERE parent_id IN %s", tuple(ids))`).
- Beim Refactoring besonders aufpassen; die schlechten Muster der Quelle **nicht kopieren**.

### Domains bauen
- Listen-Domains nicht manuell zusammenfügen: Nutzer kann sich einschleusen (`['|', ('id', '>', 0)]` ohne
  Normalisierung öffnet alles); `domain += …` hat Seiteneffekte, wenn die Domain ein Funktionsargument ist.
- **`Domain(...)` benutzen:** `domain = Domain(user_input); domain &= Domain('user_id', '=', self.env.uid)`.

### Nicht escapter Feldinhalt (XSS)
- **`t-raw` vermeiden** (häufiger XSS-Vektor): die Integrität lässt sich von der Berechnung bis ins DOM kaum
  kontrollieren; ein heute korrekt escaptes `t-raw` kann nach einer Änderung unsicher werden.
- Struktur und Inhalt trennen: Text als Variablen übergeben, im Template mit **`t-out`** (Doku: `t-esc`)
  ausgeben, Formatierung per CSS-Klasse (`.subject { font-weight: bold }`). Core-Stand 19.0 (`ir_qweb.py`): `t-esc`
  und `t-raw` sind beide veraltet, die Ausgabe-Direktive ist `t-out`.
- Nutzerdaten **nie in HTML-Strings verketten** (`"…" + product.name + "…"`).

### `markupsafe.Markup` (HTML in Python)
- `Markup` escaped **Parameter** automatisch bei `+`, `%`, `.format`. Sicheres HTML = `Markup`-Literal und
  Nutzerdaten **hineinformatieren**: `Markup('<p>%s</p>') % wert`.
- **Falsch:** `Markup("<p>Foo %</p>" % bar)` (bar wird vor dem Escapen eingesetzt);
  `Markup(f"<p>{self.bar}</p>")` (kein f-String); `"Click %s" % link` (Ergebnis ist Text, `Markup` wirkungslos) →
  `escape("Click %s") % link` bzw. zwei Markups zusammenformatieren.
- Richtig: `Markup("<p>Foo {bar}</p>").format(bar=self.bar)`; mehrere Teile mit `Markup().join(...)`.
- `Markup.replace` verhält sich überraschend (Argumenttyp entscheidet) → Operationen auf `Markup` mit
  `Markup`-Argumenten.
- `markupsafe.escape` / `odoo.tools.misc.html_escape` macht `str` → `Markup` und escaped; ein vorhandenes `Markup`
  wird **nicht** nochmal escaped.
- **Übersetzungen:** HTML und Text trennen. Übersetzungsfunktionen nehmen `Markup`-Parameter und escapen die
  Übersetzung, sobald mindestens einer übergeben wird (`_("Order %s confirmed", Markup("<a>%s</a>") % name)`).

### Escaping vs. Sanitizing
- **Escaping ist immer zwingend**, wenn Daten (TEXT) mit Code (CODE) gemischt werden – egal wie "sicher" die Daten
  sind (auch Korrektheit des Layouts; gilt auch für Python-Code in `safe_eval`).
- **Sanitizing** (`html_sanitize`, `fields.Html`-Optionen) wandelt unsicheren CODE in sichereren CODE, **nur** nötig
  bei nicht vertrauenswürdigem HTML; wirkt **nicht** auf TEXT. **Sanitizing ohne vorheriges Escapen zerstört die
  Daten** (`html_sanitize("<R&D>") → ''`). Reihenfolge: erst `html_escape`, dann ggf. `html_sanitize`.
- Sanitizing kann Funktionen brechen (Styles/Klassen entfernen, `strip_classes=True`); Optionen je nach Herkunft
  der Daten abwägen: sicherer = eher kaputt.

### Auswerten von Inhalt (`eval`)
- **`eval` nie** für Nutzerinhalt. `odoo.tools.safe_eval` ist sandboxed, gibt aber **enorme Fähigkeiten**; nur für
  **vertrauenswürdige, privilegierte** Nutzer.
- Parsen braucht kein `eval`: `int()`/`float()` (Python), `parseInt`/`parseFloat` (JS), `json.loads` /
  `ast.literal_eval` (dict), `JSON.parse` (JS). **Gut:** `literal_eval(self.filter_domain)`.

### Objektattribute dynamisch lesen
- **`getattr`/`setattr` mit nutzergesteuertem Namen sind unsicher** (erlauben private Attribute und Methoden).
  Stattdessen **`record[field_name]`** (`__getitem__` des Recordsets).
- Auch das ist "noch zu optimistisch": ID und Feldwert zusätzlich prüfen.

## 3. Prüfbarkeit (Odoo `test_lint`, `odoo/addons/test_lint`)

| Regel | Prüfung |
|---|---|
| SQL per String-Bau | `sql-injection` |
| `eval` | `eval-used` |
| Variablen/Platzhalter in Übersetzungen | `gettext-variable`, `gettext-placeholders`, `gettext-repr` |
