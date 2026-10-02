# Odoo 19 Regeln: Aktionen, Cron, Controller, Berichte (Destillat)

Quelle: `odoo/documentation`, Branch 19.0, Commit `eee2e56` (2026-10-02),
`content/developer/reference/backend/actions.rst`, `backend/http.rst`, `backend/reports.rst`
(Web: <https://www.odoo.com/documentation/19.0/developer/reference/backend/actions.html>, `…/http.html`,
`…/reports.html`). Geprüft: 2026-10-02. Index: `docs/odoo_regeln_index_2026-10-02.md`.

**Grenze der Quelle:** `odoo.http.route`, `Request`, `Response`, `IrCron._commit_progress`/`method_direct_trigger`/
`_trigger` sind *autodoc* – Parameter (`auth`, `type`, `csrf`, `methods`, `cors`, `website` …) stehen nur im
Core-Docstring, nicht in der `.rst`.

## 1. Aktionen allgemein

- Pflichtattribute jeder Aktion: `type`, `name`. Aktionen liegen in der DB oder werden als Dict aus
  Button-Methoden zurückgegeben.
- Ein Client versteht 4 Formen: `False` (offenen Dialog schließen), String (Client-Action-Tag, sonst Zahl), Zahl
  (DB-ID oder externe ID), Dict (Client-Action-Beschreibung).
- **Bindings** (optional): `binding_model_id` (bei Server-Aktionen `model_id`), `binding_type` (`action` =
  Menü "Aktion", `report` = Menü "Drucken"), `binding_view_types` (Standard `list,form`).

### Window Actions (`ir.actions.act_window`)
- Felder: `res_model`, `views` (Liste `(view_id|False, typ)`; erster Typ = Standardansicht; **jeder Typ höchstens
  einmal**), `res_id`, `search_view_id`, `target` (`current`, `fullscreen`, `new`; `main` leert Breadcrumbs),
  `context`, `domain` (wird implizit zu allen Suchen addiert), `limit` (Standard 80).
- In der DB zusätzlich `view_mode` (Standard `list,form`, **ohne Leerzeichen**), `view_ids`, `view_id`.
  **Mehrere Ansichten bevorzugt über `ir.actions.act_window.view`** (mit `sequence`, `view_mode`, `view_id`,
  `act_window_id`) statt `view_ids`.
- Serverseitige Zusammensetzung von `views`: erst `view_ids` (nach `sequence`), dann `view_id` falls Typ noch
  frei, dann `(False, typ)` für jeden offenen Typ in `view_mode`.

### URL Actions (`ir.actions.act_url`)
- `url`, `target` (Standard `new`; `self`, `download`).

### Server Actions (`ir.actions.server`)
- `state`: `code` (Python), `object_create` (`crud_model_id`, `link_field_id`, `fields_lines`), `object_write`
  (`fields_lines`), `multi` (`child_ids`; die letzte zurückgegebene Aktion gewinnt).
- `code` kann eine Variable `action` setzen = nächste Client-Aktion. **Kontext:** `model`, `record`/`records`,
  `env`, `datetime`, `dateutil`, `time`, `timezone`, `log(message, level='info')` (Tabelle `ir.logging`),
  `UserError`.
- Hausregel (abgeleitet): Logik in Python-Methoden des Moduls, Server-Aktion nur als dünner Aufruf; Code in
  Daten-XML ist schwer zu testen und zu reviewen.

### Report Actions (`ir.actions.report`)
- Pflicht: `name`, `model`, `report_name` (externe ID der QWeb-Vorlage). `report_type` Standard `qweb-pdf`
  (oder `qweb-html`). Als `<record>` statt Kurzform: `binding_model_id` setzen, damit er im Menü "Drucken" erscheint
  (`binding_type` ist implizit `report`).
- Weitere: `print_report_name` (Python-Ausdruck), `groups_id`, `multi` (nicht im Formular zeigen),
  `paperformat_id` (sonst Firmenformat), `attachment_use` (nur einmal erzeugen und aus Anhang neu drucken, z. B.
  gesetzliche Pflicht), `attachment` (Ausdruck für den Dateinamen, Datensatz heißt `object`).

### Client Actions (`ir.actions.client`)
- `tag` (clientseitige Kennung), `params`, `target`. Der Server kennt die Umsetzung nicht.

## 2. Geplante Aktionen (`ir.cron`)

- Felder: `name`, `interval_number`, `interval_type` (`minutes`, `hours`, `days`, `weeks`, `months`), `model_id`,
  `code` (z. B. `model.<methode>()`), `nextcall`, `priority`.
- **Batch-Regel (verbindlich laut Quelle):** Arbeit in Stapel teilen, die **wenige Sekunden** dauern, damit kein
  Worker lange blockiert und kein Timeout auftritt. **Das Framework committet nach jedem Stapel** und ruft die
  Funktion so oft wie nötig erneut auf. **Den Job nicht selbst neu einplanen.**
- Fortschritt melden: `self.env['ir.cron']._commit_progress(processed, remaining=…)`. Muster mit `limit`-Parameter:
  `records = self.search(domain, limit=limit)` → verarbeiten → `remaining = 0 if len(records) == limit else
  self.search_count(domain)` → `_commit_progress(len(records), remaining=remaining)`.
- **Eigene Schleife** (gemeinsame Ressourcen, eigene Fehlerbehandlung): nach jedem Datensatz
  `_commit_progress(1)` aufrufen; liefert es **0** (keine Restzeit), **sofort zurückkehren**. Je Datensatz
  `try_lock_for_update().filtered_domain(domain)`, bei behandelter Ausnahme `self.env.cr.rollback()` und
  protokollieren. (Hinweis: das Codebeispiel der Quelle hat einen Syntaxfehler – `try` ohne `:` – Logik, nicht
  Wortlaut übernehmen.) Absicherung `assert self.env.context.get('cron_id')`.
- **Cron-Funktionen nicht direkt aufrufen:** `IrCron.method_direct_trigger` oder `IrCron._trigger`. Test: über
  `method_direct_trigger` im Registry-Testmodus.
- **Schutzmaßnahmen:** 3 Fehler/Timeouts in Folge → aktuelle Ausführung übersprungen, "fehlgeschlagen";
  5 Fehler in Folge über ≥ 7 Tage → Cron deaktiviert und DB-Admin benachrichtigt; harte DB-Grenze → Prozess wird
  beendet.
- **Bezug zur Hausregel "nie `cr.commit()`":** `_commit_progress` ist der vorgesehene Weg, in Crons zu committen;
  eigenes `cr.commit()` in Cron-Code ist dadurch nicht nötig.

## 3. Web-Controller

- Von `odoo.http.Controller` erben; Routen per `@route('/url', auth=…)`. Controller haben **einen eigenen
  Erweiterungsmechanismus** (kein Modell-Registry, weil DB evtl. noch nicht da ist).
- **Überschreiben:** von der Controller-Klasse erben, Methode überschreiben und **erneut mit `@route()`
  dekorieren** – eine überschriebene Methode ohne Dekorator wird **unveröffentlicht**. Dekoratoren werden
  kombiniert: `@route()` ohne Argumente behält alle vorherigen, angegebene Argumente überschreiben
  (`@route(auth='user')` macht `/some_url` login-pflichtig). `super()` aufrufen.
- Dispatcher: `JsonRPCDispatcher` (Typ `jsonrpc`, bis 18.0 `json` – siehe ORM-Changelog 18.1) und `HttpDispatcher`.
- `odoo.http.request` ist pro Request gesetzt.
- Sicherheit: Routen sind öffentlich erreichbar; `auth`, Rechteprüfung und Eingabevalidierung gehören in die
  Route (Sicherheits-Destillat). Parameter von Routen sind Nutzereingaben → kein `sudo()` darauf.

## 4. QWeb-Berichte

- HTML/QWeb, PDF-Erzeugung durch **wkhtmltopdf**. Deklariert über Report-Aktion + Vorlage; optional Papierformat.
- **Vorlage:** `<template id="…">` mit `t-call="web.html_container"` → `t-foreach="docs"` →
  `t-call="web.external_layout"` → `<div class="page">`. Die Vorlagen-ID muss dem `report_name` entsprechen.
- Standardvariablen: `time`, `user`, `res_company`, `website`, `web_base_url`, `context_timestamp(datetime)`
  (UTC → Nutzerzeitzone); im Standardkontext zusätzlich `docs`, `doc_ids`, `doc_model`.
- **Übersetzbare Berichte:** zwei Vorlagen (Haupt + übersetzbares Dokument); `t-lang` **nur an `t-call`** (nicht an
  anderen Knoten); bei übersetzbaren Feldern Datensatz mit `with_context(lang=…)` neu laden – **nur wenn nötig**
  (kostet Performance). Nur den Rumpf übersetzen: `t-call="web.external_layout" t-lang="en_US"`.
- Barcodes: `<img t-att-src="'/report/barcode/QR/%s' % text"/>` oder mit Query-String
  (`barcode_type`, `value`, `width`, `height`).
- Bootstrap und FontAwesome nutzbar; lokales CSS in der Vorlage, globales über Vererbung von `report.style`.
- **Papierformat** (`report.paperformat`): `name` (Pflicht), `format` (A4 Standard oder `custom`; **kein
  Standardformat zusammen mit Seitenmaßen**), `dpi` (90), Ränder in mm, `page_height/width`, `orientation`,
  `header_line`, `header_spacing`.
- **Eigene Berichte:** Modell `report.<modul.report_name>` (AbstractModel) mit
  `_get_report_values(self, docids, data=None)`; liefert den Renderkontext. **Dann fehlen `docs`, `doc_ids`,
  `doc_model`** – selbst liefern, falls gebraucht.
- Schriften: in das Bundle **`web.report_assets_common`** (Text der Quelle schreibt `web.reports_assets_common`, das Beispiel `web.report_assets_common` – im Core prüfen; nicht `web.assets_common`/`assets_backend`),
  `@font-face` in der eingebundenen Datei definieren. (Hinweis: Beispiel der Quelle nutzt noch `.less`; in 19
  SCSS/CSS laut Assets-Destillat prüfen.)
- Berichte sind Webseiten: `/report/html/<report_name>/<id>`, `/report/pdf/<report_name>/<id>`.
