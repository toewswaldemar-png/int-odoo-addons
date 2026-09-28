# int_filemanager: Wie FileBrowser Quantum das Thema (Watcher/Reconciliation) löst — und ein konkreter Rückschluss für `_shallow_reconcile()`

Stand 2026-09-23. Direkt am Quellcode von **FileBrowser Quantum**
(`github.com/gtsteffaniak/filebrowser` — die aktiv gepflegte Weiterentwicklung, nicht das
originale `filebrowser/filebrowser`, das inzwischen archiviert ist) untersucht, nicht am README
geraten. Ergänzt die bisherige Cloudreve-/OpenCloud-Recherche um ein drittes, architektonisch
**komplett anderes** Vorbild — und liefert einen direkt anwendbaren Verbesserungsvorschlag für
die bereits als ineffizient dokumentierte `_shallow_reconcile()`.

---

## 1. Überraschender Kernbefund: kein Watcher überhaupt — reiner adaptiver Scan

**`go.mod` des Projekts enthält keine `fsnotify`-Abhängigkeit** (oder irgendein Äquivalent) —
bestätigt: FileBrowser Quantum verzichtet **komplett** auf OS-Ereignisbenachrichtigung
(inotify/fsnotify) als Erkennungsmechanismus. Anders als `int_filemanager` (Watcher als primärer
Weg, periodischer Scan nur als CIFS-Fallback) oder Cloudreve/OpenCloud (DB als Wahrheit, kein
externer Zugriff vorgesehen) setzt FileBrowser Quantum bewusst **ausschließlich auf Scannen** —
aber ein deutlich durchdachteres als ein simpler fester Intervall-Job.

---

## 2. Der eigentlich interessante Teil: adaptive, pro-Teilbaum eigenständige Scan-Planung

Direkt aus `backend/pkg/indexing/indexingSchedule.go`:

**Zehn Geschwindigkeitsstufen statt eines festen Intervalls:**
```go
var scanScheduleTiers = []time.Duration{
    5*time.Minute, 10*time.Minute, 20*time.Minute, 40*time.Minute,
    1*time.Hour, 2*time.Hour, 3*time.Hour, 4*time.Hour, 8*time.Hour, 12*time.Hour,
}
```

**Selbstjustierend nach tatsächlicher Aktivität:** ändert sich bei einem Scan etwas, springt der
Scanner auf eine schnellere Stufe (bei aktuell langsamer Stufe direkt auf 40 Minuten, sonst eine
Stufe schneller); bleibt es ruhig, driftet er automatisch zu selteneren Läufen. Kein globaler,
für alle Ordner gleicher Rhythmus.

**Ein eigener, unabhängiger Scanner pro Wurzel-Unterordner**, nicht ein einziger Scan-Job für den
gesamten Baum (`setupMultiScanner()`, ein `Scanner` je Top-Level-Verzeichnis). Ein viel genutzter
Projektordner kann alle 5 Minuten geprüft werden, ein ruhiges Archiv-Verzeichnis daneben nur alle
12 Stunden — unabhängig voneinander.

**Komplexitäts-basierte Untergrenze gegen genau das Problem, das `_shallow_reconcile()` hat**
(`scheduleTierBoundsForComplexity()`): ein Teilbaum mit hoher Komplexität (viele Verzeichnisse
**und/oder** lange Scan-Dauer, siehe `calculateComplexity()` — Maximum aus einem
Verzeichniszahl-Score und einem Scandauer-Score, je 1–10) bekommt eine **erzwungene Mindest-
Wartezeit** zwischen zwei Läufen (z.B. ab Komplexität 10: mindestens 1 Stunde), **selbst wenn er
gerade als "aktiv" markiert wäre**. Genau das verhindert, dass ein großer, teurer Teilbaum in
eine Dauerschleife häufiger Scans gerät.

**Zwei Scan-Tiefen im Wechsel:** `fullScanCounter` (0–4) steuert einen Zyklus aus **1 vollem +
4 schnellen** Scans, bevor wieder ein voller folgt — `quickScanTime`/`fullScanTime` getrennt
gemessen und persistiert. Ein schneller Scan ist vermutlich strukturell günstiger (nur
Verzeichnis-/Datei-Existenz und Zeitstempel), der volle Scan aufwendiger (vermutlich inklusive
Prüfsummen/Volltext, analog zu `int_filemanager`s eigenem Hash-Cron aus Phase 1).

**Ergebnis wird per Server-Sent Events live in die UI gepusht** (`SendSourceUpdateEvent()`) — kein
Nutzer muss manuell neu laden, aber der zugrunde liegende Mechanismus bleibt Scan-basiert, nur mit
kurzer Verzögerung bis zum nächsten (ggf. sehr baldigen, wenn Aktivität erkannt wurde) Lauf.

---

## 3. Direkter, konkreter Rückschluss auf `_shallow_reconcile()`

Genau das in `int_filemanager_external_change_watcher_regression.md` dokumentierte Problem —
**`_shallow_reconcile()` läuft alle 5 Minuten mit ~289s Laufzeit, unabhängig davon, wie viel sich
tatsächlich geändert hat** (nur 1 Verzeichnis wirklich verändert, trotzdem voller Aufwand über
alle drei CIFS-Freigaben) — ist exakt das Muster, gegen das FileBrowser Quantums
Komplexitäts-Untergrenze und Pro-Teilbaum-Scanner gebaut wurden.

**Übertragbare Idee, ohne das gesamte Watcher-Konzept umzubauen:** statt eines einzigen,
pauschalen 5-Minuten-Crons über alle drei CIFS-Freigaben zusammen, **je Freigabe (oder sogar je
Top-Level-Unterordner einer Freigabe) einen eigenen, adaptiven Intervall-Zustand** führen:
- Wurde bei den letzten Läufen nichts gefunden → Intervall schrittweise verlängern (z.B. 5 → 15 →
  60 Minuten), bis zu einer sinnvollen Obergrenze.
- Wird etwas gefunden → auf das kürzeste Intervall zurückspringen.
- Eine **feste Mindestlaufzeit-Untergrenze pro Lauf** (analog zur Komplexitätsgrenze), damit ein
  einzelner sehr großer Ordner sich nicht in eine 289s-Dauerschleife hineinmanövrieren kann, egal
  wie "aktiv" er kurzzeitig erscheint.

Würde die im Watcher-Regressions-Dokument selbst schon als offen vermerkte Optimierung
("Laufzeit ist praktisch unabhängig davon, wie viel sich tatsächlich geändert hat ... Optimierung
folgt") konkret ausformulieren, statt bei "muss noch optimiert werden" stehen zu bleiben — mit
einem realen, produktiv laufenden Vorbild, nicht nur einer Idee.

---

## 4. Einordnung im Vergleich zu den bisher untersuchten Systemen

| System | Mechanismus | Kernidee |
|---|---|---|
| `int_filemanager` | Live-Watcher (inotify) + fester 5-Min-Scan nur für CIFS | Reagieren, wo möglich; pauschal pollen, wo nicht |
| Cloudreve/OpenCloud | Kein externer Zugriff vorgesehen (DB ist Wahrheit) | Das Problem architektonisch vermeiden |
| **FileBrowser Quantum** | **Nur Scan, aber adaptiv + komplexitätsbegrenzt + pro Teilbaum** | **Das Problem nicht vermeiden, sondern das Scannen selbst intelligent machen** |

FileBrowser Quantum zeigt damit einen dritten, bisher nicht betrachteten Weg — nicht "Watcher vs.
kein Watcher", sondern "wie baut man einen Scan, der sich selbst an die tatsächliche
Änderungshäufigkeit anpasst". Für die drei CIFS-Freigaben, bei denen laut
`int_filemanager_external_change_watcher_regression.md` ein echter Live-Watcher wegen des
Server-seitigen Fehlens von CHANGE_NOTIFY **grundsätzlich unmöglich** ist, ist das die
relevanteste der bisher untersuchten Referenzarchitekturen — direkt anwendbar, ohne eine der schon
verworfenen größeren Architekturentscheidungen (DB ist Wahrheit, WebDAV-Vollausbau,
Sync-Client) zu brauchen.

**Quelle:** [github.com/gtsteffaniak/filebrowser](https://github.com/gtsteffaniak/filebrowser), insbesondere `backend/pkg/indexing/indexingSchedule.go` und `backend/internal/database/dbindex/indexing.go`.
