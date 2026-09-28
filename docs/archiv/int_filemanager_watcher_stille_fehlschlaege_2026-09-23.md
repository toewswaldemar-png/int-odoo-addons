# int_filemanager: Watcher — drei bisher unentdeckte stille Fehlschläge

Stand 2026-09-23. Vollständige, zeilengenaue Durchsicht von `watcher.py` plus der vendorten
`vendor/inotify_simple.py` auf ausdrücklichen Wunsch ("vielleicht findest du noch was"). Ergebnis:
**drei neue, bisher in keinem Dokument dieser Session festgehaltene Lücken**, alle mit demselben
gefährlichen Charakter — sie erzeugen **keinen Fehler, den irgendjemand bemerken würde**, sondern
lassen den Watcher (oder einzelne Ereignisse) klanglos ausfallen. Plus zwei kleinere, bereits am
Code erkennbare Performance-Punkte. Reine Analyse, nichts umgesetzt.

---

## 1. Kein Watchdog — stirbt der Watcher, bleibt er tot, ohne dass es irgendwo auffällt

**`_watch_loop()` (Zeile 162–177):**

```python
while True:
    events = inotify.read()          # <- NICHT abgesichert
    try:
        _process_batch(events, inotify, wd_to_path)
    except Exception:
        _logger.exception(...)
```

Nur der Aufruf von `_process_batch()` ist per `try`/`except` abgesichert — **`inotify.read()`
selbst nicht**. Direkt in der vendorten Bibliothek nachgelesen: `read()` "**Raises `OSError` on
failure**" (`inotify_simple.py`, Docstring). Tritt ein solcher Fehler auf — z.B. weil einer der
CIFS-Mounts währenddessen kurz nicht erreichbar ist (laut
`int_filemanager_external_change_watcher_regression.md` bereits mehrfach real beobachtetes
Verhalten dieser drei Freigaben) — läuft die Exception **ungefangen** durch `_watch_loop()` und
`_run_watcher()` nach oben durch.

**Konsequenz, je nach Startmodus (`start_watcher()`):**
- `workers=0`: der Watcher läuft in einem `threading.Thread(daemon=True)` — eine unbehandelte
  Exception dort beendet **nur diesen einen Thread**, protokolliert von Pythons Standard-
  Thread-Fehlerbehandlung (Traceback auf stderr), **der restliche Odoo-Prozess merkt nichts**.
- `workers>0`: der Watcher läuft als `gevent.spawn()`-Greenlet — eine unbehandelte Exception
  dort wird von gevents Hub geloggt, das Greenlet **endet** ebenfalls endgültig.

**In beiden Fällen: keine automatische Wiederherstellung.** Nichts im gesamten Modul startet den
Watcher neu — er bleibt für den **gesamten restlichen Lebenszyklus dieses Odoo-Prozesses** tot,
bis zum nächsten vollständigen Neustart. Und da `int_filemanager.watcher_enabled`
(`_watcher_enabled()`) nur beim **Start** geprüft wird, gibt es auch keinen periodischen
Gesundheitscheck, der das bemerken und melden würde. Der einzige Hinweis wäre ein einmaliger
Log-Eintrag zum Zeitpunkt des Absturzes — leicht zu übersehen, kein Alarm, kein Status-Indikator
irgendwo in der UI.

---

## 2. `add_watch()` ebenfalls ungesichert — realer Risikofaktor bei wachsender Ordnerzahl

**`_add_watches()`/`_bootstrap_subtree()`** rufen `inotify.add_watch(dirpath, _WATCH_FLAGS)` für
**jedes einzelne Verzeichnis** auf, ebenfalls ohne `try`/`except`. Laut derselben Bibliotheks-
Dokumentation: `add_watch()` "**Raises `OSError` on failure**".

**Konkreter, plausibler Auslöser: Linux' `fs.inotify.max_user_watches`-Grenze** (Standard oft
8192, je nach Distribution/Konfiguration auch höher) — bei **einem Watch pro Verzeichnis** und den
bereits dokumentierten Bestandsgrößen (29.121 bzw. 69.188 Verzeichnisse laut
`int_filemanager_native_ui.md`/`int_filemanager_external_change_watcher_regression.md`) ist das
keine theoretische Grenze, sondern eine, die bei diesem Datenbestand **bereits in Reichweite ist**.

**Einordnung — kein akuter Vorfall, aber ein unbeobachteter Risikofaktor:** die zitierten Log-
Einträge ("watcher active for ... (69188 directories)") belegen, dass der aktuell konfigurierte
Grenzwert auf HM-SRV zum jeweiligen Zeitpunkt ausgereicht hat. Aber: **falls dieser Grenzwert je
erreicht wird** (z.B. durch weiteres Wachstum — passend zum Langfristziel, perspektivisch auch
persönliche Dateien auf dieselbe Instanz zu bringen), bricht `_add_watches()`/`_bootstrap_subtree()`
mittendrin mit einer ungefangenen `OSError` ab — der Watcher startet dann gar nicht erst
vollständig, oder eine später live auftauchende Ordnerstruktur wird nur teilweise überwacht, ohne
erkennbare Fehlermeldung außer einem Log-Eintrag. Keine automatische Rückfallebene (z.B. "diesen
einen Ordner überspringen, Rest weiter überwachen, klar loggen, dass die Grenze erreicht wurde").
**Empfehlenswert, unabhängig von einer Code-Änderung:** den tatsächlich konfigurierten Wert von
`fs.inotify.max_user_watches` auf dem Docker-Host live prüfen und mit der aktuellen/erwarteten
Verzeichniszahl vergleichen, bevor eine größere neue Ordnermenge hinzukommt.

---

## 3. Kernel-Ereigniswarteschlangen-Überlauf wird komplett ignoriert

Die vendorte Bibliothek definiert (`inotify_simple.py:195`):

```python
Q_OVERFLOW = 0x00004000  #: Event queue overflowed
```

Das ist ein reales, vom Linux-Kernel gesendetes Ereignis, wenn die interne Inotify-Warteschlange
(begrenzt durch `fs.inotify.max_queued_events`, Standard häufig 16384) schneller gefüllt wird, als
der Watcher sie leert — z.B. bei einem großen Drag&Drop-Import mit tausenden Dateien auf einmal
(genau der Fall, der beim Langfristziel "persönliche Dateien importieren" absehbar auftreten
würde), oder wenn mehrere Kollegen gleichzeitig sehr viele Änderungen machen.

**`_process_batch()` (Zeile 94–159) prüft an keiner Stelle auf `flags.Q_OVERFLOW`.** Die
Ereignisschleife geht `IGNORED` → `MOVED_FROM` → `MOVED_TO` → `CREATE` → `MODIFY` →
`CLOSE_WRITE` → `DELETE` → `DELETE_SELF` durch — ein `Q_OVERFLOW`-Ereignis passt zu keinem dieser
Zweige und **fällt stillschweigend durch, ohne dass irgendetwas geloggt oder unternommen wird.**

**Was das bedeutet:** ein Warteschlangen-Überlauf ist per Definition ein Signal "der Kernel musste
eine unbekannte Anzahl Ereignisse verwerfen, weil du nicht schnell genug gelesen hast" — genau in
diesem Moment können beliebige Dateien/Ordner entstanden, geändert oder verschwunden sein, **ohne
dass der Watcher je davon erfährt**. Ohne Behandlung dieses speziellen Ereignisses bleibt das
komplett unbemerkt, bis (für lokale Pfade) der nächste tägliche Vollscan den Unterschied zufällig
aufdeckt — bis zu einem Tag Drift, ohne dass zwischenzeitlich irgendetwas darauf hingewiesen hätte,
dass gerade Ereignisse verloren gegangen sind.

**Naheliegende Behandlung (nicht umgesetzt, nur skizziert):** ein eigener Zweig für
`event.mask & flags.Q_OVERFLOW`, der mindestens laut/auffällig loggt ("Inotify-Warteschlange
übergelaufen, mögliche verpasste Änderungen") und im Idealfall einen sofortigen, gezielten
Reconciliation-Lauf anstößt statt bis zum nächsten planmäßigen Scan zu warten.

---

## 4. Zwei kleinere, aber real messbare Performance-Punkte (kein stiller Fehlschlag, nur Ineffizienz)

**a) O(N)-Scan über alle Watch-Deskriptoren bei jedem Ordner-Verschieben** (Zeile 118–121):

```python
for wd, path in list(wd_to_path.items()):
    if path == old_abs or path.startswith(prefix):
        wd_to_path[wd] = abs_path + path[len(old_abs):]
```

Bei jedem verschobenen/umbenannten **Ordner** wird das **komplette** `wd_to_path`-Dict (bei den
dokumentierten Bestandsgrößen: 29.000–69.000+ Einträge) linear durchsucht, um die eigenen
Nachfahren-Watches umzuschreiben — unabhängig davon, wie klein der verschobene Teilbaum tatsächlich
ist. Bei häufigen Ordner-Umbenennungen in einem großen Baum ein messbarer, bisher nicht
dokumentierter Kostenfaktor. (Der Präfix-Vergleich selbst ist korrekt implementiert — durch den
angehängten `os.sep` im `prefix` werden Namensverwechslungen wie `Ordner1` vs. `Ordner10`
zuverlässig vermieden, kein Bug an dieser Stelle.)

**b) Eine Datenbank-Transaktion pro Datei beim Erscheinen eines neuen Teilbaums** (`_bootstrap_subtree`,
Zeile 81–91): jede einzelne gefundene Datei/jeder Unterordner löst über `_upsert()` → `_run()`
einen **eigenen, frischen Cursor mit eigenem Commit** aus (siehe `_run()`-Docstring: "Open a fresh
cursor/env for one event"). Beim Erscheinen eines großen, neuen Ordners (z.B. Drag&Drop eines
kompletten Projektordners mit tausenden Dateien, oder — genau der absehbare Fall — dem geplanten
Import persönlicher Dateien) bedeutet das tausende sequenzielle, einzeln committete
Mini-Transaktionen statt eines gebündelten Vorgangs — spürbar langsamer, als es sein müsste,
für genau den Anwendungsfall, der beim Langfristziel ansteht.

---

## 5. Nachtrag 2026-09-24: alle drei Punkte betreffen den gesamten Baum, nicht nur die CIFS-Freigaben

Wichtige Präzisierung im Nachgang: `_watch_loop(root_abs)` läuft als **eine einzige** Schleife
über **einen einzigen** `inotify`-Dateideskriptor für den kompletten `root_path` — die drei
CIFS-Freigaben sind Unterordner **innerhalb** desselben Baums, nicht separat überwacht. Es gibt
keine Trennung "lokaler Watcher" vs. "CIFS-Watcher", nur einen gemeinsamen.

**Konsequenz:** die lokale Array-Freigabe liefert zwar nachweislich zuverlässig echte
inotify-Ereignisse (siehe `int_filemanager_external_change_watcher_regression.md`) — aber das
gilt nur, **solange der Watcher-Prozess selbst läuft**. Stirbt `inotify.read()` an einer
ungefangenen `OSError` (Punkt 1), plausibel ausgelöst durch einen kurz nicht erreichbaren
CIFS-Mount, reißt das **dieselbe Schleife mit, die auch die lokale Freigabe überwacht** — der
Watcher kennt keine Unterscheidung zwischen den Teilbäumen. Dasselbe gilt für die
`max_user_watches`-Grenze (Punkt 2) und den Ereigniswarteschlangen-Überlauf (Punkt 3): beide
beziehen sich auf den kombinierten Baum, nicht auf einen isolierten Teil.

**Damit ist der Watchdog-Fix (Punkt 1) kein "nice to have speziell wegen CIFS", sondern schützt
direkt auch die lokale, täglich genutzte Freigabe** — ein durch die launischeren CIFS-Mounts
ausgelöster Absturz würde die Überwachung überall gleichzeitig stilllegen, obwohl die lokale
Seite selbst nichts falsch macht.

---

## Einordnung

Die Punkte 1–3 sind die eigentlich bedeutsamen Funde dieser Session, weil sie eine andere Klasse
von Problem sind als alles bisher in diesem Modul Dokumentierte: nicht "es ist langsam" oder "es
gibt einen bekannten Bug mit klarem Symptom", sondern **"es könnte gerade schon kaputt sein oder
werden, und niemand würde es merken"**. Keiner der drei Punkte hat aktuell ein bekanntes,
beobachtetes Symptom auf HM-SRV/Tower — das ist kein Entwarnungsgrund, sondern genau die
Eigenschaft, die sie gefährlich macht. Empfehlung: vor jedem größeren Wachstumsschritt (mehr
Ordner, größere Bulk-Importe) mindestens Punkt 1 (Watchdog/Neustart-Mechanismus) und Punkt 3
(Overflow-Behandlung) angehen — beides überschaubare, klar abgegrenzte Ergänzungen, kein
Architekturumbau.
