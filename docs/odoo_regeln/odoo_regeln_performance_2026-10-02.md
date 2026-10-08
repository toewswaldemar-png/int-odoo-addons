# Odoo 19 Regeln: Performance (Destillat)

Quellen (nur diese): Odoo-19-Core (Branch 19.0) und die offizielle Entwicklerdokumentation
`developer/reference/backend/performance`
(<https://www.odoo.com/documentation/19.0/developer/reference/backend/performance.html>).
**Rangfolge: Core-Code vor Dokumentation.**
Geprüft: 2026-10-02, Korrekturen gegen den Core: 2026-10-08.

## 1. Gute Praxis (die eigentlichen Regeln)

**Stapeln (Batch):** Mit Recordsets fast immer Operationen bündeln.
- **Keine Methode, die SQL ausführt, in einer Schleife über ein Recordset aufrufen** (läuft je Datensatz). Beispiel:
  `search_count` je Datensatz in einer Compute-Methode → stattdessen **ein** `_read_group` für das ganze Set
  (`other_model._read_group([('related_id', 'in', self.ids)], ['related_id'], ['__count'])`, dann
  `dict(...).get(record, 0)`). Die Quelle merkt an: nicht in jedem Fall optimal; Alternative ist, das inverse
  One2many zu prefetchen und zu zählen.
- **Datensätze nicht einzeln nacheinander `create`n:** Werte sammeln und `create([vals, …])` einmal aufrufen
  (Framework kann Compute-Felder bündeln).
- **Prefetch nicht zerstören:** nicht `model.browse(one_id)` je Schleifendurchlauf, sondern erst
  `model.browse(ids)` und dann über das Recordset iterieren. Prüfen: `record.prefetch_ids` enthält alle IDs.
  Wo Stapel unpraktisch ist: `with_prefetch(self.ids)` steuert das Prefetch-Set ausdrücklich.

**Algorithmische Komplexität senken:**
- Verschachtelte Schleifen O(n²) vermeiden: Ergebnisse vorher in ein `dict` (`{result['id']: result['foo']}`)
  legen und mit `.get` zugreifen.
- Für Mitgliedschaftstests **`set`** statt Liste (`set(invalid_ids)`), oder Recordset-Mengenoperationen
  (`self - invalid_ids`).

**Indizes:**
- `index=True` beschleunigt Suchen (Suchfeld in Views, `search`).
- **Nicht jedes Feld indizieren:** Indizes kosten Platz und verlangsamen `INSERT`/`UPDATE`/`DELETE`.
- Zusätzliche Regel aus Odoo `test_lint` (`test_index`): Many2one, das Gegenstück eines One2many ist, bekommt einen Index.

## 2. Profiling (Werkzeug, keine Pflichtregeln)

- Integrierter Profiler schreibt `ir.profile`-Datensätze, Anzeige in **speedscope** (Flamegraph).
  - **UI:** Developer-Modus → Tools → "Enable profiling" (global in der DB mit Ablaufzeit, dann in der Sitzung);
    nur Webrequests. **Odoo Online kann nicht profiliert werden.**
  - **Python:** `with Profiler(): …`, Parameter `collectors=['sql', PeriodicCollector(interval=0.1)]`; in Tests
    `with self.profile():` – **außerhalb** von `assertQueryCount`, damit Abfragen beim Verlassen (z. B. Flush)
    mitgezählt werden. `ExecutionContext(...)` trennt mehrfache Aufrufe im Ergebnis.
- Collectors (Standard: SQL + Periodic): `sql` (`SqlCollector`, Abfragen + Stacktrace, Overhead bei vielen kleinen
  Abfragen), `traces_async` (`PeriodicCollector`, eigener Thread, Intervall 10 ms; zu klein → Speicherprobleme, zu
  groß → kurze Funktionen gehen verloren; laut Doku eines der besten Mittel für Performanzanalyse), `qweb` (`QwebCollector`, für Views),
  `traces_sync` (`SyncCollector`, jeder Aufruf, **hoher Overhead**, nur zum Verstehen von Abläufen).
- Speedscope-Ansichten: Combined, Combined no context, sql (no gap) = reine SQL-Optimierung, sql (density) = SQL vs.
  Python, frames = nur Periodic.

### Fallstricke beim Profilieren
- Zufall (z. B. Garbage Collector) → mehrfach messen.
- Blockierende externe Aufrufe halten den GIL → lange Frames im Periodic Collector.
- **Caches** (View/Assets) beeinflussen Ergebnisse – vor dem Messen aufwärmen.
- Profiler-Overhead (SQL Collector bei vielen kleinen Abfragen): für die **echte Wirkung** einer Änderung ohne
  Profiler messen.
- Speicher: bei langen Requests/Installation ggf. `--limit-memory-hard $((8*1024**3))`, sonst HTTP 500.

## 3. Prüfbarkeit

Messbar mit Tests (`assertQueryCount`, `@warmup`, `@users`, siehe Testing-Destillat) und dem Profiler.
