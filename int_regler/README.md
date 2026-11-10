# int_regler

Regler der Fahrzeuge in Odoo ansehen und bedienen, über den **Reglerdienst** (das Go-Programm aus dem Repository `micserv-rekonstruktion`, `go/reglerdienst`), der die serielle Leitung zum 11HA-Regler hält. **Status: auf einer Wegwerf-Instanz installiert und mit einem echten Regler (11HA35D, Projekt `TRAXX3002/Pro_1`) durchgespielt: Bericht, Klemmen und Lösen aus der Seite, Klemmprotokoll, Takt nach Bedarf, Ergebnis per Bus.** Modultests, Seitenprüfung und Lasttest laufen; nicht geprüft sind Reverse-Proxy/https, der Betrieb auf einem Odoo mit echter Bedienlast und mehr als ein Regler im Alltag.

## Prinzip

```
Regler  <-COM/TCP->  Reglerdienst (Go)  --JSON-2-->  Odoo  <-- Bus + ORM -->  Browser
```

- **Der Dienst ruft Odoo an, nicht umgekehrt und nicht der Browser den Dienst.** Der Dienst steht am Laptop beim Regler; Odoo und die Seite brauchen keinen Weg dorthin. Damit entfallen die Sperre der Browser für Aufrufe an `127.0.0.1` von fremden Seiten, CORS und https/http-Mischung.
- **Der Takt richtet sich danach, ob jemand hinsieht.** Die Seite sagt Odoo alle 10 s („ich schaue“, `watch`), solange sie offen und sichtbar ist. Odoo gibt dem Dienst in jeder Antwort vor, wann er wieder fragt und wie oft er berichtet (`poll_ms`, `report_ms`):

  | | Abfrage | Bericht |
  |---|---|---|
  | jemand schaut (in den letzten 30 s) | 250 ms | alle 2 s |
  | niemand schaut | 2 s | alle 60 s |

  Die Werte sind Systemparameter (`int_regler.poll_fast_ms`, `poll_idle_ms`, `report_fast_ms`, `report_idle_ms`), begrenzt auf sinnvolle Grenzen. Im Ruhezustand kostet ein Regler etwa 0,8 % eines Odoo-Kerns und 3 MB Journal pro Tag; die Last wächst mit der Zahl der Betrachter, nicht mit der Zahl der Regler. Öffnet jemand die Seite, schaltet der Dienst innerhalb eines Ruhetakts (höchstens 2 s) auf schnell.
- **Die Aufrufe des Dienstes** gehen an `POST /json/2/int.regler.device/service_sync` mit dem API-Schlüssel des Dienst-Benutzers (`Authorization: bearer …`, `X-Odoo-Database`). Ein Aufruf trägt, wenn es dran ist, den **Bericht** (Status, Werte, Klemmen, Fehler, Fehlerspeicher, Uhr, wie der Dienst sie als JSON liefert; die Werte ohne Parameterbeschreibung) und die **Ergebnisse** der zuletzt geholten Klemmaufträge. Odoo antwortet mit `{commands, watched, poll_ms, report_ms}`.
- **Klemmen sind Aufträge** (`int.regler.command`: Regler, Zeile, Aktion, Wert, Odoo-Benutzer, Zustand). Die Seite legt einen an. Der Dienst führt ihn über seine eigenen Routen aus, **als der Odoo-Benutzer** (`odoo:<login>`, Recht `clamp`): Freigaben des Dienstes (`-klemmen-original` …), Schreibsperre der Leitung und das SQLite-Schreibprotokoll des Dienstes gelten wie für jede Klemmung. Das Ergebnis geht zusammen mit einem frischen Bericht zurück, damit Odoo den neuen Zustand zeigt, wenn es das Ergebnis zeigt.
- **Das Ergebnis kommt per Bus.** Odoo sendet beim Eintragen des Ergebnisses eine kleine Nachricht (`int_regler/command`: id, Zustand, Text) an den Kanal des Reglers (`bus.listener.mixin`; `ir.websocket._build_bus_channel_list` übersetzt den Namen `int.regler.device_<id>` nach einer Suche mit den Rechten des Benutzers in den Datensatz). Die Seite fragt nicht alle 0,4 s nach, sondern wartet auf die Nachricht und schaut in Odoo höchstens nach 0,4 s und dann alle 1,5 s nach, falls eine Nachricht ausblieb.
- **Aufträge sind kurzlebig und wiederholungsfest.** Ein Auftrag gilt 15 s (`expires_in_ms` geht mit); die Seite wartet 20 s, bekommt also immer eine Antwort von Odoo und nie ein Klemmen nach dem Aufgeben. Der Dienst führt einen abgelaufenen Auftrag nicht aus. Ohne Ergebnis wird ein ausgegebener Auftrag nach 3 s erneut ausgegeben (die Antwort kann verloren gegangen sein); der Dienst führt jede ID nur einmal aus und meldet das Ergebnis nochmal. Zustände: `pending` → `sent` → `done` / `failed` / `unconfirmed` / `unknown` (ausgegeben, aber kein Ergebnis oder der Dienst hörte auf zu warten: es kann geklemmt sein) / `expired` (nie ausgegeben). „Erfolgreich“ erscheint erst nach der Bestätigung des Reglers.
- **Rechte stehen in Odoo.** Wer klemmen darf, bestimmt die Gruppe, nicht eine zweite Anmeldung am Dienst. Jede Klemmung steht mit Odoo-Benutzer und Zeit im Klemmprotokoll (Menü *Clamp log*).

## Aufbau

| Baustein | Inhalt |
|---|---|
| Modell `int.regler.device` | Name (eindeutig), Kennung im Dienst (`device_ref`), Dienst-Benutzer (`service_user_id`), Archiv, Notiz; der letzte Bericht (`snapshot`, `snapshot_at`), wann der Dienst zuletzt fragte (`seen_at`) und wann zuletzt jemand schaute (`viewer_at`), dazu die Alter nach der Uhr des Servers (`report_age`, `seen_age`, `watched`). Methoden `service_sync(device_ref, snapshot, results)` für den Dienst und `watch()` für die Seite |
| Modell `int.regler.command` | ein Klemmauftrag; wer fragt und wie es steht, setzt der Server, nicht der Aufrufer; `parameter_id` zeigt auf die Zeile, wenn der Dienst sie gemeldet hat (der Dienst arbeitet mit dem `code`) |
| Modell `int.regler.parameter` | **ein Prozesswert je Regler und Zeile als gewöhnlicher Datensatz** (Code, Name, Anzeigetext, Zahl, Einheit, Status, Seiten, klemmbar, analog, geklemmt, Klemmwert); nur lesbar, vom Server aus dem Bericht abgeglichen (`_sync`): geschrieben wird nur, was sich geändert hat, verschwundene Zeilen werden gelöscht. Suchen, Filtern, Gruppieren und Export wie bei jedem Modell. Nur der aktuelle Wert, kein Verlauf |
| Gruppen | `Controller / User` (Seite, Regler und Klemmprotokoll lesen), `Operator` (klemmt; schließt `User` ein), `Manager` (Regler anlegen und ändern; schließt `User` ein), `Service` (technisch: nur für den Benutzer des Dienstes; Schlüssel bis 365 Tage) |
| Menü | `Controller > Monitor` (die Seite), `Process values` (die Zeilen als Liste), `Clamp log` (alle Aufträge), `Controllers` (nur Manager) |
| Liste `Process values` (`js_class="int_regler.parameter_list"`) | Filter *Clamped / Can be clamped / Analog / Problems*, Gruppierung nach Regler, Status, Einheit, Seiten. Wie die Seite meldet sie dem Server „ich schaue“ (nur für die Regler der Zeilen auf dem Bildschirm). Die Bus-Meldung `int_regler/values` nennt die geänderten Zeilen (`ids`) und ob neu zu laden ist (`reload`: Zeilen kamen oder gingen, oder mehr als 30 Änderungen). Die Liste lädt dann nur die geänderten Zeilen auf dem Bildschirm mit `record.load()` (entprellt, 300 ms; Muster der Live-Chat-Liste des Kerns): dieselben Datensätze, also bleiben Häkchen, Fokus und Scrollposition. Ganz neu lädt sie bei `reload` und wenn Filter oder Gruppierung `status`, `clamped` oder `can_clamp` verwenden (dort kann eine geänderte Zeile die Gruppe wechseln oder aus dem Filter fallen); die Auswahl wird dabei nicht wiederhergestellt, wie überall in Odoo. **Stern** (`is_favorite`, Widget `boolean_favorite`) pro Benutzer nach dem Muster von `project.project` (Tabelle `favorite_user_ids`, berechnetes Feld mit Suche, Schreiben mit `sudo`; Filter *Favorites*). **Reihenfolge** (`sequence`, Widget `handle`): Ziehen der Zeilen, gilt für alle; schreiben dürfen nur Operator und Manager, und nur `sequence` (`write` wird für dieses eine Feld mit `sudo` durchgelassen). Neue Zeilen kommen in der Reihenfolge des Berichts, ein Regler nach dem anderen; ein Bericht ändert weder Stern noch Reihenfolge. Ziehen geht nur ungruppiert und mit der Sortierung nach `sequence` (Regel des Kerns). Die Liste hat `edit="1"`: ohne Schreibrecht auf das Modell setzt der Server `edit="False"` und Stern und Griff wären grau; ein ausdrückliches `edit` der Ansicht lässt er stehen. Den Griff sehen nur Operator und Manager (`groups` am Feld) Die Spalte *Clamp* (Feld-Widget `int_regler.clamp`) steht neben dem Wert und ist je klemmbarer Zeile ein Gruppenschalter *Auto / 0 / 1* (analog: *Auto* und ein Zahlensegment, das den aktuellen Wert bzw. die Klemmung zeigt und beim Klick ein **Popover** öffnet, `regler_clamp_popover.js`, über `usePopover` des Kerns: Eingabe nach dem Muster des Float-Felds von Odoo (Text mit Dezimaltastatur, Zahlenformat des Benutzers, Dezimaltaste des Ziffernblocks, ohne Spinner-Pfeile), Schritttasten −1 / −0,1 / +0,1 / +1, *Clamp* oder Enter klemmt, *Cancel*, Escape oder ein Klick daneben verwirft; erst *Clamp* fragt den Regler, ein Tippfehler oder ein Schritt nicht. In der Liste steht kein Eingabefeld, die Zeilen sind gleich hoch). Das gefüllte Segment ist der Stand der Zeile: *Auto* ruhig grau, eine Klemmung gelb mit Schloss (die Ausnahme fällt auf), dazu der Wert der Zeile in Warnfarbe; *Auto* löst; beim Warten auf den Dienst dreht ein Spinner im gedrückten Segment. Drücken dürfen nur Operatoren, andere sehen den Stand als Text (Schloss und Klemmwert, sonst „Auto“). Der Lesestatus (`status`: ok, no_value, out_of_range, error …) ist eine Diagnose und standardmäßig ausgeblendet (Spaltenmenü); Filter *Problems* und Gruppierung nach Status bleiben in der Suche. Reglerspalte ebenfalls versteckt. **Spalten anpassen** wie in jeder Odoo-Liste: ein- und ausblenden über das Menü am Ende der Kopfzeile, Breite durch Ziehen am Rand der Kopfzelle (Odoo merkt sich die Breite nicht, die Ansicht gibt sinnvolle Startbreiten vor). Die Reihenfolge der Spalten kann der Kern nicht; sie kommt, wenn installiert, vom Modul `int_generic` (alle Listen, im Browser gespeichert), `int_regler` hängt nicht davon ab |
| Seite (Client-Aktion `int_regler.app`) | Reglerwahl und zwei Ansichten: Übersicht und Fehler (nur lesend; zeigt, was der Dienst über Zustand, Fehler und Uhr gemeldet hat). Die Prozesswerte und das Klemmen sind die Liste *Process values*. Ein verstecktes Tab liest nicht und meldet nicht „ich schaue“. Die Seite hört nicht auf den Bus |
| `static/src/regler_client.js` | liest den Bericht aus dem Reglerdatensatz (eine Abfrage bedient alle Ansichten der Seite) und legt Klemmaufträge an und wartet auf die Nachricht des Busses (das braucht der Klemm-Dienst der Liste); ohne Import aus Odoo, damit er allein prüfbar ist |
| `static/src/regler_poll.js` | liest eine Route des Berichts in einem Takt und verwirft veraltete Antworten |
| `static/src/regler_parameters.js`, `regler_clamp_field.js/.xml`, `regler_clamping_service.js` | Controller der Liste (Bus, Herzschlag, Neuladen), das Klemm-Widget und der Dienst, der die Aufträge anlegt und auf den Bus wartet (öffnet selbst nichts am Bus) |

Der Bericht, den der Dienst schickt, wird in **Zeilen** abgeglichen (`values`, `clamps`) und am Regler nur in dem Teil als Json gehalten, den die Seite braucht (Zustand, Fehler, Uhr; `values`, `clamps` und `pages` werden nicht gespeichert). Der Abgleich der Zeilen kostet gemessen etwa 3 ms je Bericht und schreibt weniger ins Journal als das ganze Json (2,2 statt 5,4 kB je Bericht, 23 Zeilen); das Json am Regler ist damit von etwa 20 kB auf etwa 1,2 kB geschrumpft. Die Nachricht an die Liste kostet nach dem Commit etwa 15 ms und wird nur gesendet, wenn sich eine Zeile geändert hat und jemand schaut.

Die Seite zeigt „No report from the controller service“, wenn der Dienst länger als 20 s nicht gefragt hat; ein Bericht, der älter als 10 s ist, wird mit seinem Alter angezeigt („report 45 s old“), bis der Dienst nach dem Öffnen der Seite einen neuen schickt.

## Einrichten

1. **Dienst-Benutzer** anlegen (Einstellungen > Benutzer), nur mit der Gruppe `Controller / Service`. Unter *Kontosicherheit > Neuer API-Schlüssel* einen Schlüssel erzeugen (höchstens 365 Tage, die Grenze der Gruppe); ein Schlüssel ist nur einmal lesbar.
2. **Regler** anlegen (Menü *Controllers*): Name, Kennung im Dienst (Vorgabe `main`), Dienst-Benutzer.
3. **Operatoren** bekommen die Gruppe `Controller / Operator`.
4. **Dienst** mit Odoo verbinden (der Schlüssel kommt aus einer Datei oder der Umgebungsvariable `MICSERV_ODOO_KEY`, nie auf die Kommandozeile):

```
service.exe -projekt <Projektordner> -leitung \\.\COM1 -klemmen-original ^
  -odoo-url https://odoo.example.com -odoo-datenbank <db> -odoo-schluessel-datei <Datei>
```

Der Dienst braucht dafür weder `-erlaubte-herkunft` noch ein Token für Odoo; seine eigene Bedienseite läuft daneben wie bisher. `-odoo-intervall` gilt nur bis zur ersten Antwort von Odoo. Mit `-regler` hat jeder Regler optional `odoo_ref` (Vorgabe: seine Kennung).

Der Bus braucht den Websocket von Odoo: im Betrieb mit einem Prozess (`workers` nicht gesetzt) ist er im Server, mit mehreren Prozessen über den Evented-Port (Standard-Voraussetzung jedes Odoo-Bus).

## Grenzen

- **Kapazität (gemessen, Wegwerf-Instanz, ein Prozess, simulierte Dienste mit dem echten Bericht):** Bei 100 Diensten im alten Dauertakt (1 s) lag die CPU bei 135 % eines Kerns, bei 250 ms ging Odoo in die Sättigung und gewöhnliche Anfragen wurden 9- bis 30-mal langsamer; im Ruhetakt (2 s, Bericht alle 10 s) kosten 100 Dienste 51 Aufrufe pro Sekunde, 69 % eines Kerns und 50 kB/s Journal (mit Bericht alle 60 s etwas weniger Journal); bei 24 Reglern wären es hochgerechnet etwa 14 %. Zum Vergleich: im 30-s-Takt (Bericht 60 s) kosten 100 Dienste nur 2,5 Aufrufe pro Sekunde, 11,5 % und 8 kB/s. Ein Prozess trägt etwa 50 Aufrufe pro Sekunde gut. Der Ruhetakt (`int_regler.poll_idle_ms`) ist ein Tausch: länger heißt weniger Last, aber die erste Reaktion nach dem Öffnen der Seite dauert entsprechend länger. Für Hunderte Regler oder Regler hinter Netztrennung wäre ein Wecken (MQTT oder ein Aufruf von Odoo an den Dienst) der nächste Schritt; „ein paar Dutzend“ trägt der Ruhetakt.
- Der Bericht wird im Betrieb mit Betrachter alle 2 s abgeglichen: nur die geänderten Zeilen werden geschrieben (je Bericht im Schnitt 3 von 23), dazu das kleine Json (etwa 1 kB); ohne Betrachter alle 60 s.
- Klick bis Bestätigung des Reglers (gemessen, echter Regler 11HA35D, Odoo-Datenbank auf SSD, 15 Aufträge, Nachricht des Busses): Median 388 ms, p90 441 ms, höchstens 457 ms. Die erste Reaktion nach dem Öffnen der Seite kann bis zu 2 s dauern (Ruhetakt).
- Es gibt nur Klemmen und Lösen. Konsole, Prüfprogramm, Programmieren und Fehlerspeicher löschen kann der Dienst, Odoo zeigt sie nicht.

## Offen

- Übersetzung (`i18n/de.po`); die Quelltexte sind englisch.
- Verknüpfung mit dem Reparaturauftrag (Fehler und Klemmungen als Datensätze), falls Odoo das Produktivsystem der Werkstatt wird.
- Zeilen kennen noch nicht, wer sie geklemmt hat und wann (steht im Klemmprotokoll).
- Die Reihenfolge der Zeilen gilt für alle; eine persönliche Reihenfolge je Benutzer wäre eine Tabelle (Benutzer, Zeile, Nummer) mit berechnetem Feld und `_order_field_to_sql` wie beim Stern, und ist nicht gebaut.
- Mehrere Regler an einem Dienst und mehrere Dienste in einer Odoo-Instanz im Betrieb.
- Aufräumen alter Aufträge (Klemmprotokoll wächst).
- Wecken statt Abfragen im Ruhetakt (MQTT oder Aufruf von Odoo an den Dienst), falls die Zahl der Regler wächst.

## Prüfung

| Prüfung | Aufruf | Stand |
|---|---|---|
| Client ohne Odoo (16) | `node --test tools/int_regler/regler_client.test.mjs` | läuft, alle bestanden |
| Seite (Übersicht, Fehler) mit echtem Owl in jsdom (32), Odoo gespielt | `cd tools/int_regler && npm install && node --import ./register.mjs components.check.mjs` | läuft, alle bestanden; braucht den Quelltext von Odoo 19 (`docs/odoo`, `../odoo` oder `ODOO_SRC`) |
| Liste, Klemm-Widget und Dienst mit echtem Owl in jsdom (50) | `cd tools/int_regler && node --import ./register.mjs parameters.check.mjs` | läuft, alle bestanden; der Kern-Listencontroller ist ein Stand-in |
| Modultests in Odoo (`tests/`, 73 Tests) | Installation in einer Wegwerf-Datenbank mit `--test-tags /int_regler` | 9.11.2026: 0 Fehler |
| Go (`odoosync`, 20) | `go test ./odoosync` in `micserv-rekonstruktion/go/reglerdienst` | läuft, alle bestanden |
| Ende zu Ende mit Bus | Websocket auf den Kanal des Reglers, Herzschlag, 15 Aufträge am 11HA35D | 9.11.2026: Dienst schaltet nach 0,9 s auf schnell, 15 von 15 Nachrichten, nach Schließen der Seite nach 22 s zurück auf ruhig |
| Last | 100 simulierte Dienste in der Wegwerf-Instanz (siehe Grenzen) | 9.11.2026 gemessen |

Die jsdom-Prüfungen ersetzen weder die Modultests noch einen Handtest im Browser. Nicht geprüft: das Aussehen mit dem CSS von Odoo in verschiedenen Fenstergrößen, der echte Bus-Dienst im Browser (die Prüfung spielt ihn, der Ende-zu-Ende-Test nutzt einen eigenen Websocket-Client) und die Abläufe mit https-Odoo hinter einem Proxy.
