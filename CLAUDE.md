# int-odoo-addons

Custom-Odoo-19-Addons. Module: `int_filemanager` (Dateiverwaltung/DMS), `int_repair_workshop`
(Reparatur-Werkstatt), `int_fleet_kanban_width`, `int_generic`, `int_legacy_erp_import`,
`onlyoffice_odoo`.

Es gibt zwei Unraid-Server an unterschiedlichen Standorten, jeweils mit eigener Odoo-Instanz:

- **HM-SRV:** Container `Odoo19`, Host `unraid-odoo`.
- **Lokal (Tower):** Container `odoo` (+ `odoo_db`, `OnlyOfficeDocumentServer`), per SSH über
  den Host-Alias `unraid` erreichbar. Addons liegen unter `/mnt/user/appdata/odoo/extra-addons`
  (einfache Kopie, kein Git-Checkout), dort nur `int_filemanager` und `onlyoffice_odoo`.

Die `docker exec Odoo19 …`-Beispiele unten gelten für HM-SRV; auf Tower heißt der Container `odoo`.

## Verbindlich: vor jeder "kein Bordmittel"/Eigenbau-Aussage Odoo-Core prüfen

**Nie "das gibt es in Odoo nicht" oder "das müssen wir selbst bauen" behaupten, ohne im
Odoo-19-Core-Quellcode nachgesehen zu haben.** Grund: das ist wiederholt falsch gewesen und musste
später korrigiert werden — jedes Mal stand vorher "kein Bordmittel", dann fand sich beim
genaueren Suchen doch eine native Entsprechung:

- Eigene Watch-Buchhaltung im Watcher → **`watchdog`-Bibliothek** ist im Image installiert, der
  Core nutzt sie selbst (`service/server.py`, `FSWatcherWatchdog`).
- ACL-Regeln als generierter Text (`acl_rules.py`) → `ir.rule`-Kontext kann über `user.env[...]`
  zur Auswertungszeit selbst abfragen (`base/models/ir_rule.py`, `_eval_context`/`ormcache`),
  Regenerierung bei jeder Schutzordner-Änderung wäre vermeidbar gewesen.
- Eigenes `trashed`-Boolean-Feld → natives `active` (`_search` filtert das automatisch, auch unter
  `sudo()`, außer mit `active_test=False`).
- Eigene PIL-Aufrufe für Thumbnails → `odoo.tools.image` (`image_process`, `image_fix_orientation`,
  `binary_to_image`).
- Sortierung/Präfix-Suchen/`unique(path)` — mehrfach zuerst als Eigenbau-notwendig eingeschätzt,
  dann doch nativ lösbar gefunden.

### Suchraster (immer alle Punkte, nicht nur den ersten Treffer)

1. **Core-Grep im laufenden Container:** `docker exec Odoo19 grep -rn "<Begriff>"
   /usr/lib/python3/dist-packages/odoo/` (Core-Quellcode liegt dort, nicht im eigenen Repo).
2. **Vergleichbare andere Odoo-Module** auf dasselbe Muster prüfen (z.B. `documents`, `mail`,
   `project`, `hr` — oft existiert das Muster schon für einen anderen Anwendungsfall).
3. **`docker exec Odoo19 pip list`** — welche Bibliotheken sind im Image bereits vorhanden und
   werden vom Core selbst genutzt.
4. **Odoo-eigene Feld-/Modell-Defaults** prüfen (`active`, `ir.rule`, `res.groups`,
   `mail.thread`, `image.mixin`, `@api.autovacuum`, `@api.ondelete` usw.), bevor ein eigenes
   Äquivalent gebaut wird.
5. **Kurz empirisch bestätigen** (z.B. `docker exec Odoo19 odoo shell`), nicht nur aus dem
   Quellcode vermuten — siehe ACL-Beispiel oben, wo eine Vermutung im Code (safe_eval habe keinen
   `env`-Zugriff) sich bei echtem Test als unvollständig herausstellte.

Erst wenn alle fünf Punkte durchlaufen sind und nichts Passendes auftaucht, ist "Eigenbau nötig"
eine belastbare Aussage.

## Weitere Grundsätze

- **Code-Konventionen:** `docs/odoo_konventionen_2026-09-26.md` (Odoo Coding/Git Guidelines 19.0, Security Pitfalls,
  Odoos `test_lint`, OCA-Richtlinien und -pre-commit) gelten für neuen Code; Abschnitt 10 dort listet die
  Abweichungen dieses Repos. Entschieden 2026-09-26: neuer Code **englisch** (Namen, Kommentare, Docstrings, Logs,
  Commits `[TAG] modul: …`), Oberflächentexte englisch + `i18n/de.po`; **pre-commit** (OCA-Vorlage, nur neuer
  Code), Odoos **`test_lint`** und **odoo-ls** (Parse-Modus, Konventionen Abschnitt 9) müssen grün sein; keine GitHub Action;
  Migrationsskripte mit `odoo/upgrade-util`. Bestehende Module nicht umformatieren.
  Kommentare: Hausregeln in Abschnitt 3 "Kommentare und Docstrings" (Warum statt Was, keine Kürzel/Verweise auf Dokumente, kurze Docstrings wie im Odoo-Kern, Odoo-Stellen
  per Funktionsname statt Zeilennummer).

- **Claims immer verifizieren**, nie "sollte sicher funktionieren" — im Code/Container nachsehen,
  live testen, nicht raten.
- **Produktentscheidungen vorab mit dem Nutzer klären**, nicht impliziten Annahmen folgen.
- **Einstieg int_filemanager: `docs/int_filemanager_v2_uebergabe_2026-09-26.md`** (Stand, Entscheidungen, nächste
  Schritte, Testumgebung auf Tower). Kurzfassung: `docs/int_filemanager_v2_kern_2026-09-26.md`.
  Leitfaden ist das Konzept `docs/int_filemanager_v2_konzept_2026-09-26.md`
  (Nutzerentscheidung 2026-09-26: vollständig Odoo-Addon, Odoo alleiniger Schreiber, eigener Blob-Speicher).
  Hintergrund und Befunde zum heutigen Modul: `docs/int_filemanager_konzept_db_vorrang_2026-09-24.md`
  (Abschnitte 19/20). Konzept und Kern am 2026-09-27 freigegeben; Umsetzung nach Konzept 18 / Kern 11 mit Abnahme je Schritt.
  v2-Code nur auf Branch `feature/int-filemanager-v2` (Tag `int_filemanager-v1` = heutiges Modul). Prüfungen:
  pre-commit (`py -3.13 -m pre_commit`, Hook installiert) und `tools/v2check/v2check.sh [--quick]` (odoo-ls +
  `test_lint` auf Tower, Konventionen Abschnitt 9).
- `odoo shell` / `odoo -u` gegen die Watcher-DB startet einen zweiten Watcher (Konzept 19.5, N5). Workaround:
  vorher `int_filemanager.watcher_enabled` auf `false`, danach zurück auf `true` (der laufende Server prüft den
  Schalter nur beim Start, sein Watcher läuft weiter).
