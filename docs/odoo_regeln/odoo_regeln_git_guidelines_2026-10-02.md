# Odoo 19 Regeln: Git Guidelines (Commit-Nachrichten)

Quelle: Odoo-Git-Guidelines 19.0 (`odoo/documentation`, `content/contributing/development/git_guidelines.rst`, Commit `eee2e56`, Stand 2026-10-02),
ergänzt um die OCA-Richtlinien. Code-Regeln: `odoo_regeln_coding_guidelines_2026-10-02.md`. Index: `docs/odoo_regeln/odoo_regeln_index_2026-10-02.md`.

## Kopfzeile

- Format `[TAG] modul: kurzer Satz` (ca. 50 Zeichen). Die Kopfzeile muss mit "Wenn angewendet, wird dieser Commit …" einen gültigen Satz ergeben,
  nie Einzelwörter wie "bugfix" oder "improvements".
- Tags: `[FIX]` `[REF]` `[ADD]` `[REM]` `[REV]` `[MOV]` `[REL]` `[IMP]` `[MERGE]` `[CLA]` `[I18N]` `[PERF]` `[CLN]` `[LINT]`; OCA zusätzlich `[MIG]`.
- **`[MOV]`** nur mit `git mv` und **ohne Inhaltsänderung** (sonst geht die Historie verloren; gilt auch beim Verschieben von Code zwischen Dateien).
- Mehrere Module: auflisten oder `various`.
- Hinweis: Die OCA-Richtlinie sagt zugleich "ohne Präfix" und "Tags wie bei Odoo"; in der Praxis nutzt die OCA `[TAG] modul: …`.

## Text

- Vor allem **warum**, das Was steht im Diff; technische Entscheidungen begründen.
- Englisch, Imperativ ("Fix …", nicht "Fixes …"), Zeilen ≤ 80 Zeichen (OCA).
- Referenzen am Ende im Format `Fixes #123`, `Closes #123`, `task-123`, `opw-123`.

## Zuschnitt

- Möglichst **ein Modul je Commit**; ein Commit je logischer Änderung (keine "fix pep8"-Nachträge, OCA).
- Bestehender Code: Stil nicht umformatieren; bei großem Umbau erst reinen Verschiebe-Commit (`[MOV]`), dann die Änderung.
- `user.name` und `user.email` gesetzt.

## Dieses Repo

- Für Modul-Code `[TAG] modul: …` (frühere Commits trugen `docs: …`, `CLAUDE.md: …`; ab Odoo-Code gilt das Odoo-Format).
- Ein Commit nur auf ausdrückliche Ansage des Nutzers.
