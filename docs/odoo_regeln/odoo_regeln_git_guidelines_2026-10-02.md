# Odoo 19 Regeln: Git Guidelines (Commit-Nachrichten)

Quelle (nur offiziell): Odoo-Git-Guidelines 19.0 (`odoo/documentation`, `content/contributing/development/git_guidelines.rst`,
<https://www.odoo.com/documentation/19.0/contributing/development/git_guidelines.html>); abgeglichen 2026-10-08. Der Odoo-Code enthält keine
Commit-Regeln. Code-Regeln: `odoo_regeln_coding_guidelines_2026-10-02.md`. Index: `docs/odoo_regeln/odoo_regeln_index_2026-10-02.md`.

## Kopfzeile

- Format `[TAG] modul: kurzer Satz` (idealerweise < 50 Zeichen). Die Kopfzeile soll aussagekräftig sein und den Grund der Änderung enthalten, nie
  Einzelwörter wie "bugfix" oder "improvements". Sie muss mit "if applied, this commit will …" einen gültigen Satz ergeben
  (`[IMP] base: prevent to archive users linked to active partners`).
- Tags (offizielle Bedeutung):
  - `[FIX]` Fehlerbehebung (meist stabile Version, auch bei jungem Fehler in der Entwicklungsversion).
  - `[REF]` Refactoring: Funktion stark umgeschrieben.
  - `[ADD]` **nur** neue Module hinzufügen.
  - `[REM]` Ressourcen entfernen (toter Code, Views, Module).
  - `[REV]` Revert eines Commits.
  - `[MOV]` Dateien verschieben, auch Code von einer Datei in eine andere.
  - `[REL]` Release-Commits (neue Major-/Minor-Stable-Version).
  - `[IMP]` Verbesserungen: die meisten Änderungen in der Entwicklungsversion, die zu keinem anderen Tag gehören.
  - `[MERGE]` Merge-Commits (Forward-Port von Fixes, Hauptcommit eines Features aus mehreren Commits).
  - `[CLA]` Unterzeichnung der Odoo-Individual-Contributor-Lizenz.
  - `[I18N]` Änderungen an Übersetzungsdateien.
  - `[PERF]` Performance.
  - `[CLN]` Code-Aufräumen.
  - `[LINT]` Linting-Durchläufe.
- **`[MOV]`** mit `git mv` und **ohne Inhaltsänderung** (sonst verliert Git Spur und Historie der Datei).
- Modulname: der **technische Name** (der funktionale kann sich ändern). Mehrere Module: auflisten oder `various`.

## Text

- Vor allem **warum**, das Was steht im Diff. Das Was nur erklären, wenn technische Entscheidungen im Spiel sind, dann samt Grund.
- Im Body den betroffenen Codeteil nennen (Modul, Bibliothek, übergreifendes Objekt) und die Änderung beschreiben; zuerst das Warum,
  danach ggf. technische Entscheidungen. "Das Team hat es verlangt" ist kein gültiges Warum.
- Referenzen am Ende: `task-123` (Task), `Fixes #123` (schließt Issue auf GitHub), `Closes #123` (schließt PR), `opw-123` (Ticket).

## Zuschnitt

- Änderungen über mehrere Module in einem Commit vermeiden, außer wirklich nötig oder einfacher; getrennte Commits je betroffenem Modul
  erleichtern den Revert und das Nachvollziehen der Modulhistorie.
- `user.email` und `user.name` in der lokalen Git-Konfiguration setzen.
