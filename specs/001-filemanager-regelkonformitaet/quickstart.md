# Quickstart: Ablauf zur Überprüfung der Regelkonformität

Voraussetzung: Git Bash im Repo-Stamm, Python 3.13 mit `pre-commit` 4.6.2, SSH-Zugang
`unraid` (Tower), Node 22 oder neuer. Alle Aufrufe sind lesend oder laufen in
Wegwerf-Containern.

## 1. Einrichtung (einmal)

```bash
powershell -File scripts/lint/setup_windows.ps1
```

Erwartung: `PYTHONUTF8=1` als Benutzervariable, Hook-Stufen `pre-commit` und
`commit-msg` installiert. Neue Shell öffnen.

## 2. Commit-Prüfung (täglich, automatisch bei `git commit`)

```bash
py -3.13 -m pre_commit run --files int_filemanager/models/int_filemanager_node.py
```

Erwartung: alle Hooks bestanden. Eine geänderte Altdatei lässt den Hook
`legacy exclude block in sync` fehlschlagen; danach
`py -3.13 scripts/lint/sync_legacy_excludes.py` ausführen und erneut committen.

## 3. Probe: erkennt die Prüfautomatik alles?

```bash
py -3.13 tools/v2check/probe/run_probe.py
```

Erwartung: `30/30 cases detected`, jede Meldung vollständig lesbar.

## 4. Gebündelte Prüfung vor dem Commit (einmal je Etappe)

```bash
tools/v2check/v2check.sh        # test_lint und odoo-ls, ca. 8 Minuten
tools/v2check/jscheck.sh
tools/v2check/owlcheck.sh       # 24 von 24 Templates
tools/v2check/hoot.sh           # Hoot-Tests und Tour im Chrome-Image
tools/v2check/tests.sh          # 645 Odoo-Tests plus neue Tests
```

Erwartung: überall 0 neue Befunde, `owlcheck` nennt alle Templates, Hoot-Lauf
`Test suite succeeded`.

## 5. Migration der XML-IDs belegen

```bash
tools/v2check/tests.sh --test-tags /int_filemanager:TestV2MigrationXmlids
```

Erwartung: Test installiert den Stand `19.0.1.23.0` in einer Wegwerf-Datenbank, startet
das Update auf `19.0.1.24.0` und prüft, dass die 21 neuen IDs existieren, die 21 alten
nicht mehr, und dass die Zahl der Datensätze von `ir.ui.view`, `ir.rule` und
`ir.actions.act_window` unverändert ist.

## 6. Follower belegen

```bash
tools/v2check/tests.sh --test-tags /int_filemanager:TestV2Followers
```

Erwartung: nach Anlage von Ordner, Datei und Kopie steht kein Satz für
`int_filemanager.node` in `mail.followers`.

## 7. Regelwerk belegen

Die Prüfmatrix `docs/pruefmatrix_2026-10-04.md` öffnen: jede Zeile hat Prüfweg,
Fundstelle und Ergebnis; Zeilen mit `W:` nennen einen Probefall.
