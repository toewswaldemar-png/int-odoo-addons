# Odoo 19 Regeln: ORM (Destillat)

Quelle: `odoo/documentation`, Branch 19.0, Commit `eee2e56` (2026-10-02),
`content/developer/reference/backend/orm.rst` und `backend/orm/changelog.rst`
(Web: <https://www.odoo.com/documentation/19.0/developer/reference/backend/orm.html>).
Geprüft: 2026-10-02. Index und Einordnung: `docs/odoo_regeln/odoo_regeln_index_2026-10-02.md`.

**Grenze der Quelle:** `orm.rst` ist größtenteils *autodoc* – Feldparameter, Signaturen und Details von
`create`/`write`/`search`/`_read_group`/`unlink`/`copy`/`with_context` usw. stehen **nur im Docstring des
Odoo-Quellcodes**, nicht in der `.rst`. Dieses Destillat enthält nur, was in der `.rst` selbst steht.
Für alles andere gilt das Suchraster der `CLAUDE.md` (Core-Grep im Container, Punkt 1–5).

Legende: **MUSS/NIE** = Regel der Quelle; *Hinweis* = Verhalten/Fallstrick; `[prüfbar]` = maschinell prüfbar
(pylint-odoo, `test_lint`, odoo-ls).

## 1. Modelle und Felder

- Felder sind Klassenattribute. **Feld und Methode dürfen nicht gleich heißen** – das letzte überschreibt
  stillschweigend die früheren.
- Label (`string`) ist standardmäßig der kapitalisierte Feldname; nur setzen, wenn er abweicht
  (OCA `attribute-string-redundant`).
- Defaults als Parameter des Feldes: Wert oder `default=lambda self: self._default_x()` (vererbbar).
- `_log_access` ist standardmäßig wie `_auto`; **bei `TransientModel` MUSS es aktiv sein**.
- Reservierte Feldnamen mit Sonderverhalten – nur definieren, wenn das Verhalten gewollt ist:
  `name` (Standard für `_rec_name`), `active` (Archivierung; `action_archive`/`action_unarchive`), `state`
  (Lebenszyklus), `parent_id` (Standard für `_parent_name`; aktiviert `child_of`/`parent_of`), `parent_path`
  (bei `_parent_store`; **MUSS `index=True`** haben), `company_id` (Multi-Company; `_check_company`;
  leer = zwischen Firmen geteilt).
- `display_name` = `_rec_name`, anpassbar über `_compute_display_name`; Suche nach Name über
  `_search_display_name` (seit 18.0). `name_get` ist seit 16.4 veraltet → `display_name` lesen.
- Automatische Felder: `id`, `create_date`, `create_uid`, `write_date`, `write_uid`.

### Constraints und Indizes (seit 18.1 als Modellattribute)
- `models.Constraint("CHECK (x > y)", "message")`, `models.Index("(a, b)")`, `models.UniqueIndex(...)`.
- Attributname **MUSS mit `_` beginnen** (Namenskollision mit Feldern).
- Fehlertext: String (Übersetzung läuft über die Constraint-Tabelle) oder Funktion `(env, diag)`.

### Datum/Datetime
- Zuweisen: `date`/`datetime`-Objekt, String im Serverformat (`YYYY-MM-DD` bzw. `YYYY-MM-DD HH:MM:SS`),
  `False`/`None`. Fremde Werte mit `fields.Date.to_date(...)` / `fields.Datetime.to_datetime(...)` wandeln.
- **Date nur mit `date`, Datetime nur mit `datetime` vergleichen.** Strings vergleichen ist "heavily discouraged"
  (ein Datetime-String ist immer größer als ein Date-String).
- Rechnen/Periodenanfang: `Date`/`Datetime`-Helfer (`add`, `subtract`, `start_of`, `end_of`) oder
  `odoo.tools.date_utils`.
- Datetime wird **in UTC ohne Zeitzone** gespeichert; Zeitzonenumrechnung macht nur der Client
  (`context_timestamp`, `context_today`).

### Computed Fields
- Die Compute-Methode **MUSS jedem berechneten Feld einen Wert zuweisen**; Abhängigkeiten mit `@api.depends`
  (auch Pfade `'line_ids.value'`).
- Nicht gespeichert, nicht suchbar, nicht gruppierbar – außer `store=True` (dann suchbar/gruppierbar) oder
  `search='_search_x'` (Methode liefert eine Domain, `Domain(...)`).
- `store=True` setzt standardmäßig `compute_sudo=True`.
- Computed ist readonly; schreibbar nur mit `inverse='_inverse_x'`.
- Mehrere Felder von derselben Compute-Methode: erlaubt (alle zuweisen). Dieselbe **Inverse-Methode für mehrere
  Felder: nicht empfohlen** – während des Inverse sind *alle* ihre Felder geschützt und liefern bei Cache-Miss `False`.
- `no-write-in-compute` (OCA) `[prüfbar]`.

### Related Fields
- `related='a_id.b_id.name'`; Standard: **nicht gespeichert, nicht kopiert, readonly, im Superuser-Modus berechnet**.
- Automatisch übernommen, wenn nicht neu definiert: `string`, `help`, `required` (nur wenn alle Glieder required),
  `groups`, `digits`, `size`, `translate`, `sanitize`, `selection`, `comodel_name`, `domain`, `context`.
- Mit `store=True` gespeichert; `depends=[...]` engt Neuberechnung auf bestimmte Felder ein.
- **NIE One2many/Many2many in der Kette verketten** (`related='m2m_ids.m2m_ids'` → falsche Aggregation); eigenes
  Many2many-Compute-Feld nutzen. Erlaubt: M2O-Glied, dann O2M/M2M als letztes Glied.

## 2. Recordsets

- Recordsets können Duplikate enthalten (kann sich ändern). `self` in Modellmethoden ist ein Recordset
  (0…alle Datensätze); Iteration liefert Singletons.
- Feldzugriff als Attribut oder `record[field_name]` (sicherer als `getattr` bei dynamischen Namen).
  **Nicht-relationale Felder auf mehreren Datensätzen lesen = Fehler** → `mapped()`.
  Relationale Felder liefern **immer** ein Recordset (leer, wenn nicht gesetzt).
- Mehrstufiger Relationszugriff entspricht `mapped` (`records.partner_id.bank_ids`).
- **Cache/Prefetch:** erster Zugriff liest alle einfachen gespeicherten Felder für das ganze Prefetch-Set;
  Prefetch gilt auch für sekundäre Datensätze. Wo Prefetch nicht greift: `search_fetch` / `fetch`.
  Folgerung (nicht wörtlich in der Quelle): über das Recordset iterieren statt pro ID neu `browse(id)` zu erzeugen,
  sonst geht das Prefetch-Set verloren.
- Mengenoperationen (`|`, `&`, `-`, `in`, `<=` …) liefern neue Recordsets; Recordsets sind unveränderlich.
  `filtered`, `filtered_domain` (erhält Reihenfolge seit 15.3), `mapped`, `sorted`, `grouped` statt
  `map`/`sorted()` der Standardbibliothek, wenn ein Recordset weiterverwendet wird.
- `browse` akzeptiert kein `str` als `ids` (seit 15.3).

## 3. Domains

- **`odoo.fields.Domain` benutzen** (seit 18.1): `Domain('f', '=', v) & Domain(...)`, `|`, `~`,
  `Domain.AND([...])`, `Domain.OR([...])`, `Domain.TRUE`/`FALSE`. Listen-Domains nur noch zum Ein-/Ausgeben
  (`Domain(list)`, `list(domain)`; Präfixnotation `&`, `|`, `!`).
- Operatoren: `= != > >= < <= =? like ilike =like =ilike in child_of parent_of any any!` (+ `not` davor).
  `any` prüft Zugriffsrechte, **`any!` umgeht sie** (nur bewusst).
- Feldausdruck: Feldname oder M2O-Pfad mit Punkt; bei Datumsfeldern `feld.granularity` mit Ganzzahlwert
  (`year_number`, `quarter_number`, `month_number`, `iso_week_number`, `day_of_week`, `day_of_month`,
  `day_of_year`, `hour_number`, `minute_number`, `second_number`).
- Dynamische Zeitwerte in Datums-Domains (19.0): `'now'`, `'today'`, `'-3d +1H'`, `'=monday -1w'` …
  (Einheiten d, w, m, y, H, M, S; `+`/`-`/`=`).
- Der interne Operator `inselect` ist entfernt (17.4) → `in` mit `Query`/`SQL`.
- Domain-Optimierung läuft vor `Fields.search` (18.3): `=` entspricht `in`.
- `args` heißt seit 15.3 `domain` bei `search`/`search_count`/`_search`.

## 4. Environment, Kontext, sudo

- `self.env` erbt sich auf abgeleitete Recordsets; `env.uid`, `env.user`, `env.company`, `env.companies`,
  `env.lang`; `env.ref('xmlid')`; `env.is_superuser()/is_admin()/is_system()`.
- Umgebung ändern nur über `with_context`, `with_user`, `with_company`, `with_env`, `sudo` (neue Recordsets).
- **Veraltet in 19.0:** `record._cr`, `record._context`, `record._uid` (→ `self.env.cr/context/uid`),
  Modul `odoo.osv`. Übersetzung über `self.env._()` (seit 18.0).
- `check_access`, `has_access`, `_filtered_access` prüfen Zugriffsrechte **und** Record-Regeln gemeinsam (seit 18.0).

## 5. Rohes SQL

- Rohes SQL **umgeht ORM und Sicherheitsregeln** → nur wenn das ORM es nicht kann (komplexe Joins, Performance);
  Nutzereingaben immer parametrisieren.
- **`odoo.tools.SQL`** zum Zusammenbauen (`SQL("… %s", wert)`, `SQL.identifier`, `SQL.join`); nie Werte per
  `+`/`%`/f-String einsetzen (`sql-injection` `[prüfbar]`). Ausführen über `env.execute_query(SQL(...))`
  (flusht automatisch, 17.1; `_flush_search` ist veraltet).
- **Flush vor jeder SQL-Abfrage**, so spezifisch wie möglich: `flush_model([felder])`, `flush_recordset`,
  `flush_all` (sparsam).
- **Invalidate nach `CREATE`/`UPDATE`/`DELETE` in SQL** (nicht nach `SELECT`): `invalidate_model([felder])` /
  `invalidate_recordset` / `invalidate_all` (sparsam).
- Wurden Compute-Abhängigkeiten per SQL geändert: zusätzlich **`records.modified([felder])`** aufrufen
  (`UPDATE … RETURNING id` liefert die geänderten IDs ohne Extra-Query).
- Reihenfolge: `flush_model` → SQL → `invalidate_recordset` → `modified`.

## 6. Vererbung

- **Klassisch** (`_inherit` + `_name`): neues Modell als Kopie. **Erweiterung** (`_inherit` ohne `_name`):
  ersetzt/erweitert das Modell an Ort und Stelle. Achtung: `_inherit` als **String** setzt `_name` auf denselben
  Wert, außer `_name` ist ausdrücklich gesetzt.
- **Delegation** (`_inherits`): erbt nur **Felder, keine Methoden**; "hat ein" statt "ist ein"; M2O mit
  `required=True, ondelete="cascade"`. Quelle: "more or less implemented, avoid it if you can"; **verkettetes
  `_inherits` ist praktisch nicht implementiert** (keine Garantie).
- Feld inkrementell überschreiben: gleiche Bezeichnung und **gleicher Typ** im Erben, nur die geänderten
  Attribute angeben (z. B. nur `help=`).

## 7. Methoden-Dekoratoren und Fehler

- `@api.depends`, `@api.depends_context`, `@api.constrains`, `@api.onchange`, `@api.autovacuum`, `@api.model`,
  `@api.model_create_multi`, `@api.private`, `@api.ondelete`. Details (Parameter, Semantik) stehen nur im
  Docstring des Cores.
- `@api.private` (18.2) trennt öffentliche Python-Methoden von per RPC erreichbaren – für Methoden, die nicht per
  RPC aufrufbar sein sollen, nutzen (zusätzlich zu `_`-Präfix, siehe Security-Destillat).
- Fehler: `odoo.exceptions` – `UserError`, `ValidationError`, `AccessError`, `AccessDenied`, `MissingError`,
  `RedirectWarning`, `CacheMiss`.

## 8. Änderungs-Chronik, die neuen Code betrifft (Auszug Changelog)

| Seit | Folge für neuen Code |
|---|---|
| 19.0 | `odoo.osv` und `_cr/_context/_uid` meiden; dynamische Datums-Domains verfügbar |
| 18.4 | Eigene Domains können SQL einbetten (Changelog: "injecting arbitrary SQL") – nur mit `SQL`-Objekt, nie mit Nutzertext; `reinit`-Option im CLI |
| 18.3 | Cron-API für Fortschritt mit Batch-Commits (siehe Data/Module-Destillat); Demo-Daten nicht mehr standardmäßig |
| 18.2 | `read_group` veraltet → `_read_group` (Backend) bzw. `formatted_read_group` (öffentlich); `@api.private`; native Namespaces (PEP 420) für `odoo` |
| 18.1 | `odoo.Domain`; Constraints/Indizes als Attribute; `json`-Controller heißen `jsonrpc` |
| 18.0 | `_search_display_name`; `check_access`/`has_access`/`_filtered_access`; `self.env._` |
| 17.3 | Gruppieren nach Datumsteil-Zahlen in `_read_group` und Domains |
| 17.2 | `group_operator` heißt `aggregator`; Gruppieren/Ordnen nach related-Nicht-Store-Feld |
| 17.0 | `odoo.tools.SQL` |
| 16.2 | `search_fetch` / `fetch` |
| 16.0 | Übersetzungen als JSONB in der Spalte; `search_count` beachtet `limit` |
| 15.4 | Flush-/Invalidate-API (siehe Abschnitt 5) |
| 15.3 | `args`→`domain`; `fields_get_keys`/`get_xml_id` veraltet; `limit` an One2many/Many2many entfernt |
| 15.2 | Index-Typen am Feld; `_sequence` entfernt; `column_format`/`deprecated` an Feldern entfernt |

## 9. Folgen für dieses Repo

- Bestehende Verstöße prüfen (Stichprobe, nicht Teil dieses Destillats): `cr.execute` mit String-Formatierung statt
  `SQL`, fehlendes `flush_model`/`invalidate_*` um Roh-SQL, Listen-Domains per `+` zusammengeklebt, `_cr`/`_context`
  im Code. Befund und Plan gehören in die Übergabe-Dokumente von `int_filemanager`, nicht hierher.
