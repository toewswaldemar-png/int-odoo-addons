# Contract: Prüfwerkzeuge

Schnittstelle des Repos nach außen sind die Aufrufe der Prüfwerkzeuge, ihre Ausgabe und
ihre Exit-Codes. Alle Aufrufe stehen mit Beispiel in `docs/pruefautomatik_2026-10-02.md`
(nach Angleichung) und in `quickstart.md`.

| Werkzeug                                 | Aufruf (Arbeitsrechner, Git Bash)                                                    | Läuft wo                  | Exit 0                                                                           | Exit ≠ 0                                                                      | Blockiert Commit                        |
| ---------------------------------------- | ------------------------------------------------------------------------------------ | ------------------------- | -------------------------------------------------------------------------------- | ----------------------------------------------------------------------------- | --------------------------------------- |
| pre-commit (Stufe `pre-commit`)          | automatisch bei `git commit`; manuell `py -3.13 -m pre_commit run --files <Dateien>` | Arbeitsrechner            | alle Hooks bestanden                                                             | mindestens ein Hook fehlgeschlagen; Meldung `Datei:Zeile: Regel`              | ja                                      |
| pre-commit (Stufe `commit-msg`)          | automatisch bei `git commit`                                                         | Arbeitsrechner            | Kopfzeile `[TAG] modul: Satz` ≤ 80 Zeichen, Tag erlaubt                          | Kopfzeile falsch                                                              | ja                                      |
| `scripts/lint/sync_legacy_excludes.py`   | `py -3.13 scripts/lint/sync_legacy_excludes.py [--check]`                            | Arbeitsrechner            | `--check`: Block aktuell; ohne Option: Block neu geschrieben                     | `--check`: Block veraltet, Liste der Dateien auf stdout                       | ja (als Hook `legacy-excludes-in-sync`) |
| `scripts/lint/setup_windows.ps1`         | `powershell -File scripts/lint/setup_windows.ps1`                                    | Arbeitsrechner            | `PYTHONUTF8` gesetzt, beide Hook-Stufen installiert                              | Voraussetzung fehlt (Python, pre-commit), Meldung                             | nein                                    |
| `tools/v2check/v2check.sh [--quick]`     | Git Bash                                                                             | Tower (Wegwerf-Container) | `== result: OK (… changed files checked as new)`                                 | `== NEW (must be fixed): n` mit Liste                                         | nein (vor dem Commit von Hand)          |
| `tools/v2check/jscheck.sh`               | Git Bash                                                                             | Tower                     | `0 problem(s)`                                                                   | Problemliste                                                                  | nein                                    |
| `tools/v2check/owlcheck.sh`              | Git Bash                                                                             | lokal + Tower-Image       | `<n> template(s) compiled, 0 problem(s)` mit n = Zahl aller Templates des Moduls | Problemliste                                                                  | nein                                    |
| `tools/v2check/hoot.sh` (neu)            | Git Bash                                                                             | Tower, Image mit Chrome   | `[HOOT] Test suite succeeded` und Odoo-Meldung `0 failed`                        | fehlgeschlagene Hoot-Tests, Meldung `[HOOT] Test "@int_filemanager/…" failed` | nein                                    |
| `tools/v2check/tests.sh`                 | Git Bash                                                                             | Tower                     | `… tests in …, 0 failed`                                                         | Fehlerliste                                                                   | nein                                    |
| `tools/v2check/probe/run_probe.py` (neu) | `py -3.13 tools/v2check/probe/run_probe.py`                                          | Arbeitsrechner            | `30/30 cases detected`                                                           | `n/30 detected`, fehlende Fälle mit Nummer                                    | nein                                    |

## Ausgabeformat der Meldungen

- Python (pylint-odoo): `<Datei>:<Zeile>: [<Id>(<symbol>), <Objekt>] <Text>`
- pygrep-Hooks: `<Datei>:<Zeile>:<Zeileninhalt>`; die Hook-Überschrift nennt die Regel
  (z. B. `deprecated record._cr/_context/_uid`)
- ESLint: `<Zeile>:<Spalte> error|warning <Text> <Regel>`; Fehler blockieren, Warnungen
  nicht (nach der Bereinigung gibt es keine Dauerwarnungen)
- `oca-checks-odoo-module`: `<Datei>:<Zeile>: <regel> <Text>`, ab Einrichtung durch
  `setup_windows.ps1` ohne Abbruch

## Regeln des Vertrags

1. `--all-files` ist nie ein dokumentierter Aufruf (Hooks schreiben Dateien um).
2. Jede Regel mit Prüfweg `W` hat einen Probefall in `probe_rules/`; ein neuer Hook ohne
   Probefall ist unvollständig.
3. Die Konfiguration nennt jeden Hook mit derselben Bezeichnung wie das
   Prüfautomatik-Dokument.
4. Prüfungen auf Tower laufen in Wegwerf-Containern und -Datenbanken; keine berührt die
   Live-Instanz.
