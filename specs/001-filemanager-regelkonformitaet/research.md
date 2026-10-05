# Research: int_filemanager Regelkonformität und Prüfautomatik

Stand 2026-10-04. Jede Entscheidung nennt die Fundstelle und wie sie geprüft wurde
(Constitution I und V). Quellen: Odoo-Core im Image `odoo:19.0-hm-test` auf Tower
(`/usr/lib/python3/dist-packages/odoo/`), lokale Referenzen in `docs/`, Läufe auf dem
Arbeitsrechner.

## R1: Wie werden neue Regeln blockierend erzwungen?

- **Decision**: Zwei Bordmittel, kein Eigenbau: (a) lokale `pygrep`-Hooks in
  `.pre-commit-config.yaml` für Regeln, die ein Muster sind (`_context`/`_uid`,
  Listen-Domain-Verkettung, `<tree`/`attrs=`/`states=`/`t-raw` in XML außerhalb von
  `static/`, Manifest-Manifest-Schlüssel `application`, `auto_install`, `demo` mit
  Standardwert); (b) ESLint-Regeln `no-restricted-globals` und
  `no-restricted-properties` für `localStorage`, `sessionStorage`, `window.location`,
  `window.history`, `window.navigator` in `static/src/**`.
- **Rationale**: `language: pygrep` ist Teil von pre-commit; auf diesem Arbeitsrechner
  erprobt (Python 3.13, Windows): ein Python-Beispiel mit `self._context` und
  `domain + [...]` und ein XML-Beispiel mit `<tree/>` und `t-raw` wurden von den drei
  Hooks gemeldet, Exit 1. ESLint 9.35 ist bereits Hook (`--fix`, Fehler blockieren,
  Warnungen nicht).
- **Alternatives considered**: eigene pylint-Plugins (Aufwand, Pflege); ein
  Python-Skript als lokaler Hook (mehr Code als eine Regex); Warnung statt Stopp (vom
  Nutzer abgelehnt).
- **Grenze**: `pygrep` ist textbasiert. Ein Treffer in einem Kommentar oder String
  blockiert ebenfalls; dafür gilt die Konvention `# noqa`-ähnlicher Ausschluss nicht,
  die Hooks bekommen `exclude` je Datei bei begründeten Ausnahmen. Die Zahl heutiger
  Treffer im neuen Code ist 0 (Prüfung vom 2026-10-04).
- **Nicht pre-commit-fähig**: Parameter `ids`/`context` an öffentlichen Modellmethoden
  prüft Odoos `test_lint` (`test_naming`) auf Tower; bleibt Teil von `v2check.sh`.
  `installable` prüft Odoos `test_manifests` nicht (Quelltext: `# todo installable ?`);
  dafür der `pygrep`-Hook für Manifeste.

## R2: Wie wird die Commit-Kopfzeile geprüft?

- **Decision**: `pygrep`-Hook in der Stufe `commit-msg` mit `--multiline`; erlaubt ist
  `[TAG] modul: Satz`, Tags laut Odoo-Git-Regeln ohne `DOC` (FIX, REF, ADD, REM, REV,
  MOV, REL, IMP, MERGE, CLA, I18N, PERF, CLN, LINT, MIG), ganze Zeile höchstens 80
  Zeichen, Zusatz `Merge `-Zeilen von Git bleiben erlaubt.
- **Rationale**: erprobt auf dem Arbeitsrechner: `[FIX] int_filemanager: …` Exit 0;
  `[DOC] …`, `fix stuff`, zu lange Zeile und `Merge branch x` Exit 1 (der Merge-Fall
  wird in der endgültigen Regex ausgenommen). Der Hook läuft nur, wenn
  `pre-commit install --hook-type commit-msg` ausgeführt wurde; das macht
  `scripts/lint/setup_windows.ps1`.
- **Alternatives considered**: `commitlint` (Node-Abhängigkeit, eigene Regeln); Review
  (vom Nutzer abgelehnt).
- **Offen für die Umsetzung**: Die endgültige Regex mit Längenprüfung und Merge-Ausnahme
  wird in der Aufgabe getestet; die erprobte Fassung prüfte 60 Zeichen für den Satz
  statt 80 für die ganze Zeile.

## R3: LEGACY-Block ohne Handarbeit

- **Decision**: `scripts/lint/sync_legacy_excludes.py` leitet die Altdateien aus
  `git diff --name-only int_filemanager-v1` ab: eine Baseline-Datei ist Altbestand,
  solange sie dort unverändert ist. `REWRITTEN_FILES` entfällt (außer für entfernte
  Dateien). Der Hook `legacy-excludes-in-sync` läuft künftig bei jeder Änderung unter
  `int_filemanager/`, nicht nur bei Änderung der Konfiguration.
- **Rationale**: Heute stehen 12 von 19 geänderten Altdateien im Block, weil die Pflege
  von `REWRITTEN_FILES` Handarbeit ist (Messung 2026-10-04). Mit Ableitung schlägt der
  Hook beim ersten Commit einer geänderten Altdatei fehl, das Skript nimmt sie aus dem
  Block, und ab dann prüfen alle Hooks die ganze Datei (Entscheidung des Nutzers).
- **Alternatives considered**: Diff-Zeilen-Prüfung (Werkzeug müsste gebaut werden; vom
  Nutzer abgelehnt); Handpflege plus Prüfliste (Fehler wiederholt sich).
- **Folge**: Die 12 Dateien müssen vor dem Umstellen sauber sein, sonst blockiert der
  nächste Commit. Messung für die Bereinigung: 51 blockierende pylint-Befunde
  (`prefer-env-translation` 35, `invalid-commit` 4, `except-pass` 5,
  `translation-not-lazy` 5, `translation-required` 1, `attribute-string-redundant` 1),
  `E501`: 469 bei 88 Zeichen, **4 bei 120** (Zeilenlänge 120 entschieden 2026-10-05);
  `ruff format` und Prettier ändern Zeilen.

## R4: Windows-Abbruch von `oca-checks-odoo-module`

- **Decision**: `PYTHONUTF8=1` als Benutzer-Umgebungsvariable (`setx`), gesetzt und
  geprüft durch `scripts/lint/setup_windows.ps1`; im Prüfautomatik-Dokument beschrieben.
  Ein Hook-Eintrag mit Umgebung ist nicht möglich: `pre-commit` kennt für `repo`-Hooks
  kein `env`.
- **Rationale**: Ursache belegt:
  `UnicodeEncodeError: 'charmap' codec can't encode character '\U0001f534'` im Hook beim
  Ausgeben eines Befunds (colorama, Codepage `cp1252`); mit `PYTHONUTF8=1` erscheint die
  Meldung vollständig (erprobt 2026-10-04).
- **Alternatives considered**: Hook-Version wechseln (die Ausgabe mit Emoji ist
  Verhalten der Version 0.1.7; neue Version nicht geprüft); `chcp 65001` (wirkt nicht
  für Git-Hook-Umgebungen).

## R5: Wie laufen Hoot-Tests automatisch?

- **Decision**: Odoos eigener Läufer `web/tests/test_js.py`
  (`WebSuite.test_unit_desktop`) öffnet `/web/tests?headless&…&id=<Hash>` in Chrome; die
  Hoot-Test-ID eines Moduls ist der Hash von `@int_filemanager`. Aufruf:
  `odoo … --test-tags '/web:WebSuite.test_unit_desktop@int_filemanager'` (genaue
  Tag-Syntax in der Aufgabe geprüft) in einem Wegwerf-Container mit Chrome.
- **Rationale**: Quelltext im Image gelesen: `test_unit_desktop` ruft `browser_js` mit
  Erfolgssignal `[HOOT] Test suite succeeded`; `_find_executable` in
  `odoo/tests/common.py` sucht `google-chrome`, `chromium`, `chromium-browser`,
  `google-chrome-stable` und die Umgebungsvariable `ODOO_BROWSER_BIN`. Kein Eigenbau
  eines Läufers.
- **Befund im Image**: kein Browser (`which` leer), `websocket-client` fehlt
  (`ModuleNotFoundError: websocket`), `apt-cache` ohne Paketlisten; `dl.google.com` ist
  von Tower erreichbar (DNS-Auflösung geprüft). Ubuntu 24.04: das apt-Paket
  `chromium-browser` ist ein Snap-Platzhalter und taugt im Container nicht.
- **Decision (Image)**: `tools/docker/Dockerfile.test` baut `odoo:19.0-hm-test-chrome`
  aus `odoo:19.0-hm-test` mit `google-chrome-stable` (.deb von Google) und
  `pip install websocket-client`. **Das ist ein Download; er wird erst nach
  ausdrücklicher Freigabe des Nutzers ausgeführt** (Aufgabe T-Freigabe).
- **Alternatives considered**: Hoot lokal im Windows-Chrome gegen eine Instanz auf Tower
  (nicht automatisch, Nutzerregel: der Nutzer testet im Browser selbst); Node mit jsdom
  (Hoot braucht echtes Layout, Odoo liefert dafür keinen Weg); Playwright-Chromium
  (zusätzlicher Download ohne Vorteil).
- **Bundle**: `web.assets_unit_tests` enthält im Core nur `web/static/tests/**/*`; die
  Module-Features kommen über `web.assets_unit_tests_setup`, das `web.assets_backend`
  einbindet. Das Modul trägt `static/tests/**/*` (ohne `tours/`) unter
  `web.assets_unit_tests` ein, die Tour unter `web.assets_tests`.

## R6: Portierung der 75 Node-Testfälle

- **Decision**: Jede der neun Testdateien `static/tests/js/*.test.mjs` wird zu
  `static/tests/<name>.test.js` mit
  `import { describe, expect, test } from "@odoo/hoot"`; der Modulname der geprüften
  Dateien ist `@int_filemanager/int_filemanager/v2/<datei>` (Addon `int_filemanager`,
  Pfad unter `static/src`). `fake_server.mjs` entfällt zugunsten `mockFetch`/`onRpc` aus
  Hoot und `web_test_helpers`. Die `.mjs`-Dateien werden erst gelöscht, wenn jede
  Testfall-Zeile als Hoot-Test belegt ist (Äquivalenzliste in den Aufgaben).
- **Rationale**: Regeln `odoo_regeln_js_tests` (Dateiname `*.test.js` ist Pflicht, kein
  eigenes `describe` nötig, `expect.step`/`verifySteps` statt Zähler); Quelle:
  `docs/odoo19_reference/frontend/unit_testing.md`, Zeile mit "Test files must end with
  `.test.js`".
- **Tour**: `static/tests/tours/int_filemanager_explorer.js` mit `tour.register(...)`,
  Bundle `web.assets_tests`; Python-Gegenstück `tests/test_v2_tour.py` (`HttpCase`,
  `start_tour`). Inhalt: Ordner anlegen, Datei hochladen, umbenennen, in den Papierkorb
  legen. Letzte Schritte bringen den Client in einen stabilen Zustand (Regel TEST 3).
- **Alternatives considered**: Node-Tests parallel behalten (vom Nutzer abgelehnt:
  "alles nach Odoo-Regel mit Hoot").

## R7: XML-ID-Umbenennung und `upgrade-util`

- **Decision**: `migrations/19.0.1.24.0/pre-migrate.py` benennt 21 XML-IDs mit
  `odoo.upgrade.util.rename_xmlid` um; das Image bekommt `upgrade-util`
  (Produktions-`Dockerfile` und `Dockerfile.test`). Fehlt ein alter Eintrag (frische
  Datenbank), tut der Aufruf nichts.
- **Rationale**: Regel CG 2: Migrationsskripte mit `odoo/upgrade-util`. Befund im Image:
  `odoo.upgrade` ist ein leerer Namensraum (nur `.gitkeep`),
  `from odoo.upgrade import util` schlägt fehl (geprüft 2026-10-04). Installation laut
  Regel: `pip install git+https://github.com/odoo/upgrade-util@master` (**Download,
  braucht Freigabe**).
- **Alternatives considered**: reines SQL auf `ir_model_data` (Regel verbietet eigenes
  SQL bei vorhandenem Werkzeug; Rename muss auch `ir.ui.view`/`ir.rule`-Verweise und
  Übersetzungsfundstellen konsistent halten); Umbenennung ohne Migration (Datenbanken
  würden doppelte Datensätze anlegen und die alten verwaist lassen).
- **Folgen**: `i18n/de.po` bekommt neue Fundstellen (`tools/v2check/i18n_export.sh`);
  Verweise in `controller_mutations.js` und `folder_tree.js` (Aktionsnamen) werden
  angepasst; `tools/v2check/po_tool.py` und `ui_instance.sh` nennen
  `action_int_filemanager_node`.
- **Außerhalb des Umfangs**: `docs/int_filemanager_stand.md` nennt zwei alte IDs; die
  Datei ist laut Auftrag ausgenommen und wird nicht geändert.

## R8: `mail_create_nosubscribe` am Knoten

- **Decision**: `_create_nodes` setzt zusätzlich `mail_create_nosubscribe=True` und
  `mail_notrack=True`; ein Test (`test_v2_followers.py`) prüft, dass nach Anlage von
  Ordner, Datei und Kopie kein Satz in `mail.followers` für das Modell
  `int_filemanager.node` steht.
- **Rationale**: `mail/models/mail_thread.py` (Zeile 331): ohne
  `mail_create_nosubscribe` abonniert die Anlage den aktuellen Nutzer, wenn dieser aktiv
  und kein Portalnutzer ist; Zeile 99 beschreibt den Schlüssel. Der Code setzt heute nur
  `mail_create_nolog` (`int_filemanager_node.py:557`).
- **Alternatives considered**: `mail.thread` entfernen (der Chatter der Knoten-Formulare
  und `message_post` in `int_filemanager_value_recognition.py:969` brauchen es);
  Follower-Zeilen in der Migration löschen (nicht nötig, Testdatenbank; als Option im
  Datenmodell vermerkt, Entscheidung offen für den Nutzer vor Live).

## R9: SQL-Form und Flush

- **Decision**: Die 11 `cr.execute` mit Rohtext in `int_filemanager_blob.py`,
  `int_filemanager_derivative.py` und `int_filemanager_upload.py` werden auf
  `self.env.execute_query(SQL(...))` oder `cr.execute(SQL(...))` umgestellt;
  `flush_all()` wird zu `flush_model([...])` der betroffenen Modelle, `invalidate_all()`
  zu `invalidate_model`. Der f-String in `_enqueue_missing` wird zum `SQL`-Objekt mit
  `SQL.identifier`-freiem Konstantenteil.
- **Rationale**: Regel ORM 5 und Hausregel; die Form liegt im selben Modul schon vor
  (`int_filemanager_node.py`, `execute_query(SQL(..., to_flush=[...]))`). Verhalten
  bleibt gleich, abgesichert durch `test_v2_blobstore`, `test_v2_derivative*`,
  `test_v2_upload` und die Rennszenarien (`race.sh`).
- **Alternatives considered**: Rohtext mit Parametern belassen (Hausregel verlangt
  `SQL`).

## R10: Regelwerk gegen Referenzen belegen

- **Decision**: Die Prüfmatrix führt jede Regel (eine Zeile je Aussage mit MUSS/NIE/muss
  in den 17 Destillaten) mit Fundstelle in `docs/odoo19_reference/`,
  `docs/owl2_reference/` oder im Core (Datei und Funktion) und dem Ergebnis `stimmt`,
  `überholt` oder `ergänzen`. Wo die Referenz autodoc ist, gilt der Core im Image.
- **Rationale**: Index Folgepunkt 3 verlangt es; die Stichprobe vom 2026-10-04 (8
  Regeln) fand 2 Korrekturen (ES2019 überholt, `t-esc` für Owl).
- **Zählweise für SC-003/SC-005**: eine Regel = ein nummerierter Zeilenpunkt der Matrix;
  die Zahl steht nach der Erstellung fest und wird im Plan der Aufgaben nicht geschätzt.

## R11: ESLint-Rauschen

- **Decision**: `jsdoc/check-tag-names` bekommt `definedTags: ["odoo-module"]`;
  `sort-imports` und `no-inline-comments` werden abgeschaltet, weil kein Destillat sie
  verlangt (Importreihenfolge ist eine Python-Regel, CG 3); `complexity` steht für JS
  auf 20 (zwei Funktionen mit 16 und 17 überschreiten 15; Odoo-Regeln verlangen kein
  Limit).
- **Rationale**: Messung 2026-10-04: 108 Warnungen (53 `sort-imports`, 36 Tag, 17
  Inline-Kommentare, 2 `complexity`); keine ist in `docs/odoo_regeln/` begründet.
- **Alternatives considered**: alle 108 beheben (kostet Umbau ohne Regelgrundlage).

## R12: Nicht geklärt und bewusst nicht gelöst

- Upgrade der Hook-Version `odoo-pre-commit-hooks` (neuere Version könnte das
  Emoji-Problem lösen): nicht untersucht; `PYTHONUTF8` genügt.
- Wann und ob die Follower-Zeilen bestehender Knoten bereinigt werden:
  Produktentscheidung vor der Bestandsübernahme.
