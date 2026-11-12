# int_workbench

Regler der Fahrzeuge in Odoo ansehen und bedienen, über die **Service Workbench** (das Go-Programm aus dem Repository `micserv`, `go/workbench`), die die Leitung zum Regler hält. Ein Modul für alle Reglerfamilien: Die Familien melden sich an, Odoo legt sie als Datensätze an, und die Ansichten blenden aus, was ein Regler nicht kann. Eine neue Familie ist ein neuer Treiber im Dienst; dieses Modul bleibt unberührt.

**Stand 12.11.2026:** Modultests laufen in einer Wegwerf-Datenbank (Abschnitt Prüfung). Die Oberfläche besteht nur aus Odoos Standardbausteinen (Listen, Formulare, Suchleisten mit Searchpanel, Knöpfe, Dialoge); die einzige Ausnahme ist ein kleiner Listen-Controller (`static/src/views/parameter_list.js`), der die Prozesswerte über den Bus aktuell hält. Nicht am echten Regler und nicht im Browser gesehen seit dem Umbau auf Standardbausteine.

## Prinzip

```
Regler  <-COM/TCP->  Service Workbench (Go)  --JSON-2-->  Odoo  <-- Bus + ORM -->  Browser
                                              <--HTTP---  (Benutzer, Protokoll, Projekte)
```

- **Der Dienst ruft Odoo an.** Berichte, Ergebnisse und Anmeldung der Familien gehen vom Dienst nach Odoo (JSON-2, API-Schlüssel eines Dienst-Benutzers); Odoo braucht dafür keinen Weg zum Dienst. Nur was Odoo vom Dienst *erfragt* (Benutzer, Protokoll, Projekte) braucht eine Adresse am Regler (`Dienstadresse`) und ein Token.
- **Der Takt richtet sich danach, ob jemand hinsieht.** Die Liste der Prozesswerte sagt Odoo alle 10 s „ich schaue“ (`watch`), solange sie offen und sichtbar ist; der Regler gilt dann 30 s als beobachtet. Odoo gibt dem Dienst in jeder Antwort vor, wann er wieder fragt und wie oft er berichtet (`poll_ms`, `report_ms`):

  | | Abfrage | Bericht |
  |---|---|---|
  | jemand schaut (die Klemmliste ist offen) | 250 ms | alle 2 s |
  | niemand schaut | 2 s | alle 60 s |

  Die Werte sind Systemparameter (`int_workbench.poll_fast_ms`, `poll_idle_ms`, `report_fast_ms`, `report_idle_ms`), begrenzt auf sinnvolle Grenzen. Eine dritte Stufe „Klemmseite schnell, sonst mittel“ gibt es nicht: außer der Klemmliste meldet keine Ansicht, dass jemand schaut (dafür wäre JS auf jeder Ansicht nötig).
- **Klemmen sind Aufträge** (`int.workbench.command`: Regler, Zeile, Aktion, Wert, Odoo-Benutzer, Zustand). Der Dienst führt sie als der Odoo-Benutzer aus; Freigaben, Schreibsperre und Schreibprotokoll des Dienstes gelten wie für jede Klemmung. Aufträge gelten 15 s, werden bei verlorener Antwort erneut ausgegeben und nur einmal ausgeführt.

## Modelle

| Modell | Inhalt | Quelle |
|---|---|---|
| `int.workbench.device` | Regler: Name, Kennung im Dienst, Dienst-Benutzer, Dienstadresse und -token, Familie, Fähigkeiten, Bericht (Json: Zustand, Uhr) | Manager legt an; Familie und Fähigkeiten setzt der Dienst |
| `int.workbench.family` | Familie: Name, Bezeichnung, Transporte, Fähigkeiten | `service_register` |
| `int.workbench.capability` | Fähigkeit (`clamps`, `clock`, `console`, `can_control`, `flash`, `line_switch`, `error_memory`, `error_files`, `intermediate`, `project_files`; unbekannte kommen mit ihrem Kürzel als Namen dazu) | Daten des Moduls, `service_register` |
| `int.workbench.parameter` | Prozesswert und Klemme einer Zeile; Stern und Reihenfolge je Benutzer bzw. für alle | Bericht (`service_sync`) |
| `int.workbench.command` | Klemmauftrag und sein Ausgang (Klemmprotokoll) | Bediener, Ergebnis vom Dienst |
| `int.workbench.error` | aktive Fehler (Fehlerwort, Bit, Text) | Bericht |
| `int.workbench.log` | Schreibprotokoll des Dienstes (die neuesten 1000 Einträge) | Knopf *Fetch log* |
| `int.workbench.user` | Konten des Dienstes (ohne Passwörter) | Knopf *Fetch users* |
| `int.workbench.project` | Stände der Projektbibliothek: Fahrzeug und Projekt (aus der ersten Herkunft), kurze Kennung, Zeilenzahl, ladbar oder Grund, Herkunft | Knöpfe *Fetch projects* und *Take over new folders* |
| `int.workbench.parameter.clamp` | Dialog „Klemmen“ (Wert eingeben) | transient |
| `int.workbench.project.import` | Dialog „Neue Ordner übernehmen“: fragt `GET /api/v1/projects/inventory`, schickt die neuen Ordner in Paketen zu 25 an `POST /api/v1/projects/import`, holt danach die Stände | transient |

Nicht gebaut: ein Feld „nutzender Regler“ an den Ständen (die Schnittstelle des Dienstes sagt nicht, welcher Regler welchen Stand benutzt) und die Zuweisung von Ständen an Regler.

## Fähigkeiten steuern die Ansicht

Der Regler trägt je Fähigkeit ein berechnetes Kennzeichen (`cap_clamps`, `cap_project_files` …); Ansichten benutzen es mit `invisible`. Heute hängen daran: die Klemmknöpfe der Liste (über `device_cap_clamps` an der Zeile) und die Knöpfe für Projekte am Regler-Formular. Ein Regler, dessen Dienst sich noch nicht angemeldet hat (älterer Dienst, keine Familie), behält das Klemmen; alles andere bleibt für ihn verborgen. Ein Klemmauftrag für einen Regler mit Familie, die nicht klemmen kann, wird abgelehnt.

## Die Aufrufe des Dienstes

Beide mit dem API-Schlüssel eines Benutzers der Gruppe `Workbench / Service`, nur für die ihm zugewiesenen Regler (`Authorization: bearer …`, `X-Odoo-Database`):

- `POST /json/2/int.workbench.device/service_sync` mit `{device_ref, snapshot, results}`: Bericht (Status, Werte, Klemmen, Fehler, Uhr; die Werte, Klemmen und Fehler werden Zeilen, nur der Rest bleibt als Json am Regler) und Ergebnisse der geholten Aufträge. Antwort: `{commands, watched, poll_ms, report_ms}`.
- `POST /json/2/int.workbench.family/service_register` mit `{device_ref, family, capabilities: [...], families: [{name, label, transports, capabilities}]}`: legt Familien an oder bringt sie auf den Stand, setzt Familie und Fähigkeiten am Regler. Antwort: `{family, capabilities, families}`. Der Dienst schickt den Aufruf einmal nach dem Start; Fehler 4xx (älteres Modul) beendet den Versuch, ohne dass der Regler leidet.

## Einrichten

1. **Dienst-Benutzer** anlegen, nur mit der Gruppe `Workbench / Service`, und unter *Kontosicherheit > Neuer API-Schlüssel* einen Schlüssel erzeugen (höchstens 365 Tage; ein Schlüssel ist nur einmal lesbar).
2. **Regler** anlegen (Menü *Workbench > Configuration > Controllers*): Name, Kennung im Dienst (Vorgabe `main`), Dienst-Benutzer. Für Benutzer, Protokoll und Projekte zusätzlich *Dienstadresse* (zum Beispiel `http://workbench:8080`) und *Dienst-Token*.
3. **Bediener** bekommen `Workbench / Operator` (klemmen und lösen), **Verwalter** `Workbench / Manager` (Regler anlegen, Konten und Protokoll lesen, Projekte übernehmen), alle anderen `Workbench / User` (lesen).
4. **Dienst** mit Odoo verbinden (der Schlüssel kommt aus einer Datei oder der Umgebungsvariable, nie auf die Kommandozeile); die Adresse und Parameter stehen in der Beschreibung des Dienstes.

Der Bus braucht den Websocket von Odoo (im Betrieb mit einem Prozess im Server, mit mehreren über den Evented-Port).

## Grenzen

- **Kapazität (gemessen am 9.11.2026, Wegwerf-Instanz, ein Prozess, simulierte Dienste mit dem echten Bericht):** Im Ruhetakt (2 s, Bericht alle 10 s) kosten 100 Dienste 51 Aufrufe pro Sekunde, 69 % eines Kerns und 50 kB/s Journal; im 30-s-Takt (Bericht 60 s) nur 2,5 Aufrufe pro Sekunde, 11,5 % und 8 kB/s. Ein Prozess trägt etwa 50 Aufrufe pro Sekunde gut. Für Hunderte Regler wäre ein Wecken (MQTT oder ein Aufruf von Odoo an den Dienst) der nächste Schritt.
- Klick bis Bestätigung des Reglers (gemessen am 9.11.2026 mit der alten Seite, echter Regler 11HA35D): Median 388 ms. Die erste Reaktion nach dem Öffnen der Liste kann bis zu 2 s dauern (Ruhetakt). Mit den Knöpfen der Liste nicht neu gemessen.
- Odoo fragt den Dienst nur auf Knopfdruck; Benutzer, Protokoll und Projekte sind Abbilder, keine Echtzeit. Das Token des Dienstes steht in Odoo im Klartext (Feld nur für Verwalter sichtbar).
- Es gibt Klemmen und Lösen. Konsole, Prüfprogramm, Programmieren, Uhr und Fehlerspeicher löschen kann der Dienst; Odoo zeigt sie noch nicht (die Fähigkeiten dafür sind schon da).

## Offen

- Das Verhalten am echten Regler und im Browser (Aussehen der Liste mit Knöpfen und Searchpanel, Dialog, Benachrichtigung) ist nicht gesehen.
- Dritte Stufe des Taktes („sonst mittel“) und Zuweisung von Ständen an Regler (siehe oben).
- Verknüpfung mit dem Reparaturauftrag (Fehler und Klemmungen als Datensätze), falls Odoo das Produktivsystem der Werkstatt wird.
- Aufräumen alter Aufträge (Klemmprotokoll wächst) und alter Einträge des Schreibprotokolls.
- Neu einspielen: Das Modul ist aus `int_regler` umbenannt (Modelle `int.workbench.*`); auf einer Instanz mit `int_regler` muss es neu installiert werden, Daten werden nicht übernommen.

## Prüfung

| Prüfung | Aufruf | Stand |
|---|---|---|
| Modultests in Odoo (`tests/`, 101 Tests) | `TESTS_MODULE=int_workbench tools/check/tests.sh` | 12.11.2026: 0 Fehler (Wegwerf-Datenbank, Odoo 19.0-20260817) |
| Listen-Controller mit echtem Owl in jsdom (24 Prüfungen) | `cd tools/int_workbench && npm ci && npm test` | 12.11.2026: alle bestanden; braucht den Quelltext von Odoo 19 (`docs/odoo`, `../odoo` oder `ODOO_SRC`) |
| Go (`odoosync`, `drivers`) | `go test ./odoosync ./drivers/...` in `micserv/go/workbench` | siehe dort |

Die jsdom-Prüfung ersetzt weder die Modultests noch einen Handtest im Browser.
