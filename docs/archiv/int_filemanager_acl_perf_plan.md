# ACL-Performance-Fix: geplant, noch nicht umgesetzt

Stand 2026-09-16. Durchgeplant und mehrfach gegengeprüft, aber bewusst noch nicht implementiert -
dieses Dokument ist der Umsetzungsplan für ein künftiges Gespräch/eine künftige Session.

## Problem

Live per `EXPLAIN ANALYZE` gegen die Produktions-DB (1,38 Mio. Zeilen in `int_filemanager.file`)
nachgewiesen: `acl_rules.py`s generierter `domain_force`-Text baut pro geschütztem Ordner eine
`path NOT LIKE 'X/%'`-Klausel. Die DB-Collation ist `en_US.utf8` (nicht `C`), ein normaler B-Tree-
Index auf `path` beschleunigt LIKE-Präfixsuchen darunter nicht. Gemessen: die volle Domain (7
aktuell konfigurierte Schutzordner) kostet **~580ms pro Aufruf** (Parallel Seq Scan über die
komplette Tabelle) - bei jeder einzelnen Abfrage, für jeden Nutzer ohne die Administrator-Gruppe
(Admins bekommen `[(1,'=',1)]` und umgehen die LIKE-Auswertung komplett).

## Kernidee

Ein neues, indexiertes Feld `protected_folder_id` (Many2one auf `int_filemanager.protected_folder`)
auf `int_filemanager.file`, das den *tiefsten* zutreffenden Schutzordner vorberechnet speichert
(oder leer, wenn keiner zutrifft). Die Regel wird dadurch zu einem simplen indexierten Join:

```python
['|', ('protected_folder_id', '=', False),
      ('protected_folder_id.read_group_ids', 'in', user.all_group_ids.ids)]
```

Keine Pro-Ordner-Ausschluss-Komposition mehr zur Laufzeit nötig - "tiefster Ordner gewinnt" ist
bereits im gespeicherten Wert kodiert, statt bei jeder Abfrage neu berechnet zu werden.

## Wie das Feld gepflegt wird

**Verworfen:** `@api.depends("path")`-Computed-Field. Im Odoo-19-Quellcode
(`orm/fields.py`, `Field.write()`) filtert `_filter_not_equal()` zwar unveränderte Werte vor dem
Dirty-Markieren heraus, aber `self.modified(vals)` in `orm/models.py`s `write()` läuft trotzdem
unbedingt über die im Aufruf übergebenen Feldnamen. Ob das am Ende unnötige Neuberechnungen bei
jedem vollen Scan vermeidet, ließ sich ohne echten Test nicht sicher klären - zu unsicher für einen
sicherheitsrelevanten Mechanismus.

**Stattdessen:** zentrale Überschreibung von `create()`/`write()` auf `int_filemanager.file` selbst
(erweitert die dort bereits bestehende `write()`-Überschreibung, die "name"-Änderungen zu
`rename_entry()` umleitet). Wenn `path` im vals-Dict steht, wird `protected_folder_id` explizit neu
aufgelöst und mitgeschrieben:

```python
def write(self, vals):
    if "path" in vals:
        vals = dict(vals, protected_folder_id=self._resolve_protected_folder_id(vals["path"]))
    return super().write(vals)
```

Vorteile:
- Funktioniert automatisch überall, wo `path` geschrieben wird - auch im bestehenden Test-Helper
  `_make_file()` in `tests/test_acl.py`, der direkt `Model.create({...})` ruft, ohne über
  `index_utils.py` zu laufen. Kein Testcode muss angepasst werden.
- Deckt über dieselbe `write()`-Überschreibung automatisch auch `index_move_tree()` mit ab (dessen
  Schreibvorgänge auf Nachfahren laufen durch dieselbe Methode).

Bekannter, bewusst akzeptierter Kompromiss: `_scan_and_reconcile()`s `flush()` schreibt `path` bei
jedem gescannten Datensatz mit, auch wenn er sich nicht geändert hat - ein Voll-Scan löst dadurch
pro Zeile eine kleine Neuauflösung aus (ohne DB-Zusatzabfrage dank In-Memory-Cache der ~7-20
Schutzordner-Einträge während eines Aufrufs).

## Wiederverwendung statt Duplikat

`authz.py` hat bereits `_protection_signature(env, rel_path)` - findet exakt den tiefsten
zutreffenden Schutzordner für einen Pfad (genutzt für den Umbenennen/Verschieben-Grenzcheck in
`require_rename_or_move_allowed`). Diese Funktion nach `acl_rules.py` verschieben (z.B. als
`resolve_protected_folder`), `authz.py` importiert sie von dort - eine einzige Quelle der Wahrheit
statt einer zweiten, potenziell abweichenden Kopie in `filemanager_file.py`.

Bemerkenswert: `_protection_signature` sortiert `order="path desc"` und nimmt den ersten Treffer -
funktioniert korrekt, weil ein Pfad-Präfix alphabetisch immer vor jeder eigenen Erweiterung kommt
(z.B. `"A/B"` < `"A/B/C"`), kein Zufall. Die verschobene Funktion sollte dieselbe erprobte Logik
übernehmen statt eine eigene längenbasierte Variante neu zu bauen.

## Rebuild bei Schutzordner-Änderungen

Wenn sich `int_filemanager.protected_folder` selbst ändert (Admin legt/ändert/löscht einen
Schutzordner-Eintrag), muss `protected_folder_id` potenziell für alle Zeilen neu berechnet werden.
Dafür nicht über die ORM iterieren (zu langsam bei 1,38 Mio. Zeilen), sondern per rohem SQL-UPDATE,
sortiert von flachstem zu tiefstem Schutzordner-Pfad (spätere, tiefere Updates überschreiben
absichtlich frühere, flachere - implementiert "tiefster gewinnt" korrekt, ohne die komplexe
Ausschluss-Domain-Logik, die `_internal_branch_text` aktuell zur Laufzeit macht):

```sql
UPDATE int_filemanager_file SET protected_folder_id = NULL;
-- pro Schutzordner, aufsteigend nach Pfadlänge:
UPDATE int_filemanager_file SET protected_folder_id = %(folder_id)s
WHERE path = %(folder_path)s OR path LIKE %(folder_path_escaped)s || '/%%';
```

`escape_psql()` (aus `odoo.tools.sql`, bereits im Projekt für genau diesen Zweck genutzt) bleibt
hier nötig (echtes SQL LIKE) - anders als bei der Pro-Datensatz-Python-`str.startswith()`-Auflösung
oben, wo das Wildcard-Escaping-Problem (z.B. Schutzordner `"Plan_2026"` vs. unbeteiligter Ordner
`"PlanX2026"`, `_` ist ein SQL-LIKE-Wildcard) komplett gegenstandslos wird, weil dort kein SQL LIKE
mehr im Spiel ist.

Nach dem SQL-Rebuild `env["int_filemanager.file"].invalidate_model(["protected_folder_id"])`
aufrufen (Methode am Odoo-19-Quellcode verifiziert: `orm/models.py`,
`invalidate_model(fnames=None, flush=True)`).

**Selbstheilung bei jedem Serverneustart nicht unconditional machen:** `filemanager_protected_folder.py`s
`_register_hook()` ruft `_rebuild_acl_rules()` heute bei jedem Registry-Aufbau auf (auch reiner
Neustart ohne Änderung - Lehre aus einem echten vorherigen Vorfall mit zurückgesetztem
`domain_force`). Ein volles SQL-Update über 1,38 Mio. Zeilen bei jedem Neustart (bei diesem
Deploy-Workflow: nach praktisch jedem Deploy) wäre unverhältnismäßig teuer. Lösung: eine Signatur
der aktuellen Schutzordner-Konfiguration (z.B. Hash über alle `(path, read/write/unlink group
ids)`-Tupel) in `ir.config_parameter` ablegen, bei `_register_hook()` vergleichen, nur bei
Abweichung den vollen Rebuild auslösen. Bei echten `create()`/`write()`/`unlink()`-Aufrufen auf
`protected_folder` dagegen immer unbedingt rebuilden (dort ist eine Änderung sicher passiert).

## Regelgenerierung wird viel einfacher

`_domain_force_text`/`_internal_branch_text` in `acl_rules.py` (aktuell: pro Schutzordner eine
Ausschluss-Klausel gegen alle tieferen Schutzordner komponieren) entfällt fast komplett - die neue
Regel ist strukturell immer gleich (siehe Domain oben), hängt gar nicht mehr von der Anzahl/den
Pfaden der konfigurierten Schutzordner ab. Die `int_filemanager.version`-Regel braucht kein eigenes
Feld, traversiert einfach `file_id.protected_folder_id.read_group_ids` (dieselbe
Punktnotation-Mechanik wie aktuell schon `file_id.path`).

## Tests

`tests/test_acl.py` sollte bis auf `test_broken_generation_keeps_previous_domain_force`
unverändert funktionieren (Test-Helper `_make_file()` deckt sich automatisch ab, siehe oben). Dieser
eine Test patcht `_internal_branch_text` mit ungültigem Text und prüft, dass eine fehlgeschlagene
Regenerierung die vorherige `domain_force` unangetastet lässt - muss an die neue, viel simplere
Regelgenerierungsfunktion angepasst werden (Name/Struktur ändert sich).

## Bewusst nicht mit angefasst

`authz.require_subtree_deletable()` macht einen eigenen, separaten `path =like 'X/%'`-Scan
(Vollständigkeitscheck beim Löschen: "enthält der zu löschende Ordner etwas, das der Nutzer nicht
sehen darf"). Derselbe Kostentreiber, aber nur beim Löschen aktiv (viel seltener als jede
Leseabfrage) - eigenständiges, kleineres Performance-Thema, absichtlich außerhalb dieses Scopes
gelassen.

## Nächster Schritt

Umsetzung + Deploy + Live-Test (EXPLAIN ANALYZE wie beim Ordnerbaum-Fix, siehe
`../int_filemanager_native_ui.md`/Commit `89e0c9c`) auf ausdrücklichen Auftrag hin.
