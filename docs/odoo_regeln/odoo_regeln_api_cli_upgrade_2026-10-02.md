# Odoo 19 Regeln: Externe APIs, CLI, Upgrade-Skripte, Standardmodule (Destillat)

Quelle: `odoo/documentation`, Branch 19.0, Commit `eee2e56` (2026-10-02), `content/developer/reference/`:
`external_api.rst` (JSON-2), `external_rpc_api.rst` (XML-/JSON-RPC, veraltet), `extract_api.rst`, `cli.rst`,
`upgrades/upgrade_scripts.rst`, `upgrades/upgrade_utils.rst`, `standard_modules*`
(Web: <https://www.odoo.com/documentation/19.0/developer/reference/external_api.html> usw.).
Geprüft: 2026-10-02. Migrationsregel des Repos: `odoo_regeln_coding_guidelines_2026-10-02.md` Abschnitte 2 und 8.
Index: `docs/odoo_regeln/odoo_regeln_index_2026-10-02.md`.

## 1. Externe JSON-2-API (neu in 19.0 – gewünschter Weg für Integrationen)

- **Request:** `POST /json/2/<model>/<method>` (Modul `rpc`, `auth='bearer'`); Header `Host`, `Authorization: bearer <API-Key>`,
  `Content-Type: application/json` (Charset empfohlen), optional `X-Odoo-Database` (nötig, wenn mehrere DBs und
  `dbfilter` nicht über `Host` filtert), `User-Agent` (empfohlen). Body = JSON-Objekt mit `ids` (leer/fehlend bei
  `@api.model`-Methoden), `context`, und **allen Methodenparametern benannt** (**keine Positionsargumente**).
- **Response:** 200 + JSON-Rückgabewert; sonst 4xx/5xx mit Objekt `name`, `message`, `arguments`, `context`,
  `debug` (Traceback).
- **Rechte:** normale Odoo-Sicherheit (Access Rights, Record Rules, Feldzugriff). Für **dauerhafte Automatisierung
  dedizierte Bot-Nutzer** mit minimalen Rechten (Passwort leer = kein Login; `create_uid`/`write_uid` zeigen den
  Bot); persönliches Konto nur für interaktive Erkundung und Einmal-Skripte.
- **Transaktion:** **jeder Aufruf = eigene Transaktion** (Erfolg = Commit, Fehler = Rollback); keine Ketten in einer
  Transaktion. Daher **zusammengehörige Operationen in einer einzigen Methode** auf dem Server (z. B. `action_*`,
  `search_read`) bündeln – gefährlich bei Reservierungen/Zahlungen. Fehlt eine Methode: in eigenem Modul anlegen.
- **API-Keys:** UI: Einstellungen → Konto-Sicherheit → neuer Schlüssel (Beschreibung + Laufzeit Pflicht; **Höchstlaufzeit je Gruppe** im Feld `api_key_duration` (Standard 90 Tage, ohne Gruppenwert 1 Tag), interaktiv kurz, z. B. 1 Tag; 160-Bit-Zufallswert, **nur einmal sichtbar**). Programmatisch:
  `res.users.apikeys/generate` (`key`, `scope` – `rpc` oder `null`, `name`, `expiration_date` ISO-8601) und `…/revoke`
  (`key`); Standard nur für Nutzer mit Einstellungen-Adminrecht, Freigabe für andere über Systemparameter
  `base.enable_programmatic_api_keys=True`; Limit 10 Schlüssel (`base.programmatic_api_keys_limit`, Überschreitung 422).
  **Rotation:** neuen Schlüssel erzeugen → sicher ablegen → Dienste umstellen → alten widerrufen (mit dem neuen
  authentifizieren); je Dienst ein eigener Schlüssel; Schlüssel nie im Quelltext.
- Dynamische Doku: `/doc` der Instanz (laut Quelle "Under construction").
- Hinweis der Quelle: Zugriff auf externe API ist bei Odoo **Online** nur im Tarif *Custom*; für selbst betriebenes
  Community nicht relevant. `int_filemanager` nutzt JSON-2 mit API-Key-Scope.
- **Ablösung:** `/xmlrpc`, `/xmlrpc/2`, `/jsonrpc` (Dienste `common`, `db`, `object`) sind **veraltet und werden in
  Odoo 22 (Herbst 2028) entfernt** → für neue Integrationen nur JSON-2. Ersatz: `common.version` → `GET
  /web/version`; `authenticate` entfällt (API-Key; eigene ID über `res.users/context_get`); `object.execute(_kw)` →
  JSON-2; DB-Funktionen teils über `/web/database/*`. `@route(type='jsonrpc')` (bis 18.0 `type='json'`) ist **nicht**
  betroffen.

## 2. Altes RPC-API (nur zum Lesen vorhandenen Codes)

- Zugangsdaten: statt Passwort **API-Key** (seit 14.0), Login bleibt. `execute_kw(db, uid, pw|key, model, method,
  args, kwargs)`.
- Verhalten, das auch für JSON-2 gilt: `search` hat `offset`/`limit` (Pagination), `search_count` zählt nur;
  **`search` + `search_count`/`read` in getrennten Aufrufen können bei Nebenläufigkeit inkohärent sein** (→ `search_read`);
  `read` ohne `fields` liefert **alle** lesbaren Felder (viel); `id` kommt immer mit; Datum/Datetime/Binary sind
  **Strings**; One2many/Many2many schreibt man über das **Command-Protokoll** (`Command`);
  `write` setzt für alle Datensätze **dieselben** Werte (keine berechneten Updates); `unlink` löscht in Bulk.
- Metamodelle: `ir.model` (neue Modelle zur Laufzeit: Name beginnt mit **`x_`**, `state='manual'`, **nur Felder, keine
  Methoden**), `ir.model.fields` (nur `state='manual'` aktiv; **keine Compute-Felder**, kein Default/Onchange).

## 3. Extract API (kostenpflichtiger IAP-Dienst)

JSON-RPC2 auf `https://extract.api.odoo.com`; Dokumenttypen Rechnung, Kontoauszug, Spesen, Bewerbung; Ablauf
`/parse` (Dokument als Base64: pdf/png/jpg, ein Dokument je Aufruf, Kosten 1 Credit, `account_token`, optional
`webhook_url`) → `document_token` → `/get_result` (Polling oder Webhook). Testtoken `integration_token`
(ratenbegrenzt). **Für dieses Repo nicht relevant** (kein IAP; OCR ist in `int_filemanager` ein eigenes Thema).

## 4. CLI (`odoo-bin` bzw. `odoo`; im Docker-Image `odoo`)

- **Server:** `-d`, `-i` (installieren), `-u` (aktualisieren; `all` = alle), `--reinit` (nur Debug/Entwicklung,
  **nie in Produktion** – lädt `noupdate`-Daten neu), `--addons-path`, `--upgrade-path`, `--pre-upgrade-scripts`,
  `--load`, `-c` (Konfig; sonst `ODOO_RC`, `~/.odoorc`), `-D` (Data-Dir), `-s` (speichern), `--without-demo` (Standard),
  `--with-demo`, `--skip-auto-install`, `--stop-after-init`.
- **Tests:** `--test-enable` (impliziert `--stop-after-init`), `--test-file`, `--test-tags [-][tag][/modul][:klasse][.methode]` (impliziert Enable;
  Standard `standard`; `*` = alle; Include ohne Tag = `standard`, Exclude ohne Tag = `*`); Filterung läuft **zweimal**
  (nach jeder Modulinstallation und am Ende des Ladens). `--screenshots`, `--screencasts` (braucht `ffmpeg`).
- **Datenbank/HTTP/Logging:** `--db-filter` (Regex mit `%h`/`%d`; wirkt **nicht** auf Cron-Worker), `--no-database-list`,
  `--db_sslmode`, `--unaccent`; `--no-http` (wirkungslos mit `--test-enable`), `-p/--http-port` (8069), `--gevent-port`
  (8072), `--proxy-mode` (**nur hinter Reverse Proxy**), `--x-sendfile`; `--logfile`, `--log-db`, `--log-handler
  LOGGER:LEVEL`, `--log-sql`, `--log-level`.
- **Developer-Features:** `--dev=xml|reload|qweb|replica|access|all` (`all` = access, qweb, reload, xml) – **nur Entwicklung, nie Produktion**.
- **Mehrprozess:** `--workers`, `--limit-request` (65536), `--limit-memory-soft` (2048 MiB), `--limit-memory-hard`
  (2560 MiB), `--limit-time-cpu` (60), `--limit-time-real` (120), `--max-cron-threads` (2),
  `--limit-time-real-cron` (Standard -1 = wie `--limit-time-real`).
- **Konfigdatei:** Optionsnamen ohne `--`, `-` → `_`; Ausnahmen: `dbfilter`, `http_enable`, `smtp_server`, `db_name`;
  Abschnitt `[options]`.
- **Unterbefehle:** `shell` (**läuft in Transaktion, Rollback beim Beenden – nur `env.cr.commit()` schreibt**;
  `--shell-file`, `--shell-interface`), `db` (`init`, `dump`, `load`, `duplicate`, `rename`, `drop`; mit `--neutralize`),
  `i18n` (`import`, `export`, `loadlang`; Sprachcodes im POSIX-Format), `module` (`install`, `uninstall`, `upgrade
  [--outdated]`, `forcedemo` – **nicht umkehrbar, vorher Dump**), `neutralize` (`--stdout`), `scaffold`, `populate`,
  `cloc` (`cloc_exclude` im Manifest), `obfuscate` (**kein sicheres Anonymisieren**), `deploy` (braucht
  `base_import_module`), `upgrade_code --from 18.0 --to 19.0 [--dry-run]`.
- **Folgen für dieses Repo:** `odoo shell`/`odoo -u` gegen die Watcher-DB startet einen zweiten Watcher
  (`CLAUDE.md`) – das ist unabhängig von der Referenz, aber der Shell-Rollback gilt weiter.
  Tests über `--test-tags /int_filemanager` (und `/test_lint`) auf der Testinstanz.

## 5. Upgrade-Skripte

- Datei mit `migrate(cr, version)`; Pfad **`<modul>/migrations/<version>/{pre,post,end}-*.py`** (ab 13 auch
  `upgrades/`, **bevorzugt**: "migrate" kann mit "aus Odoo heraus" verwechselt werden). `<version>` = volle Version
  (`19.0.x.y.z`).
- Läuft **nur beim Update** des Moduls, und nur wenn die Zielversion **höher als die installierte und ≤ der
  aktualisierten** ist.
- **Phasen:** `pre` (vor dem Laden des Moduls), `post` (nach Modul und Abhängigkeiten geladen/aktualisiert),
  `end` (nach allen Modulen dieser Version); innerhalb der Phase **lexikalische Reihenfolge** (`pre-10-…`, `pre-20-…`).
- **`odoo/upgrade-util`** (`from odoo.upgrade import util`; `util.env(cr)` für ORM): Module, Modelle, Felder,
  Datensätze, ORM, Domains, SQL (`pg`), Misc, Report; Tests über `odoo.upgrade.testing`. Installation: `--upgrade-path=
  <upgrade-util>/src` oder `pip install git+https://github.com/odoo/upgrade-util@master` (nicht im Image; Odoo.sh:
  `requirements.txt`). Vorteile: konsistente Daten, indirekte Referenzen, weniger eigener Code.
  **Hausregel: Helfer statt eigenem SQL** (Coding Guidelines 2).

## 6. Standardmodule

`standard_modules/account/*` und `payment/*` sind reine autodoc-Verzeichnisse (Felder von `account.account`,
`account.tax`, `payment.provider`, `payment.transaction` …). Nicht relevant für dieses Repo; bei Bedarf im Core nachsehen.
