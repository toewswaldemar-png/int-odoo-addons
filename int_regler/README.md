# int_regler

Regler der Fahrzeuge in Odoo ansehen und bedienen, über den **Reglerdienst** (das Go-Programm aus dem Repository `micserv-rekonstruktion`, `go/reglerdienst`), der die serielle Leitung zum 11HA-Regler hält. **Status: erste Fassung. Auf dem Testserver installiert und getestet, die Seite mit gespieltem Dienst geprüft; noch nicht mit einem echten Regler und nicht im Browser.**

## Prinzip

```
Regler  <-COM/TCP->  Reglerdienst (Go, 127.0.0.1:8085)  <-HTTP->  Browser  <-Odoo-Seite->  Odoo
```

- **Der Browser spricht direkt mit dem Dienst, Odoo nicht.** Odoo speichert nur, wo der Dienst erreichbar ist (Modell `int.regler.device`: Name, Adresse des Dienstes, Kennung des Reglers im Dienst). Werte, Fehler und Klemmungen laufen nie über den Server von Odoo. Das ist nötig, weil der Dienst am Laptop beim Regler läuft und ein Odoo-Server ihn nicht erreicht.
- **Die Anmeldung am Dienst ist eine eigene.** Der Dienst kennt seine Benutzer und Rollen (`read`, `clamp`, `service`, `flash`, `admin`) selbst und prüft sie bei jedem Schreiben. Die Seite meldet sich dort mit Name und Kennwort an; das Token liegt nur im Session-Speicher des Browser-Tabs, unter der Adresse des Dienstes, und geht nie an Odoo. Die Gruppen von Odoo (unten) regeln nur, wer die Seite und die Regler-Datensätze sieht, nicht was am Regler erlaubt ist.
- **Jede Klemmung steht im Schreibprotokoll des Dienstes**, mit dem Benutzer des Dienstes. Eine Zuordnung zum Odoo-Benutzer gibt es noch nicht.

## Aufbau

| Baustein | Inhalt |
|---|---|
| Modell `int.regler.device` | Name (eindeutig), Adresse des Dienstes, Kennung des Reglers, Archiv, Notiz. Adresse und Kennung werden geprüft (`http(s)://host:port` oder ein Pfad wie `/regler`; Kennung nur Buchstaben, Ziffern, `-`, `_`) |
| Gruppen | `Controller / User` (Seite öffnen, Regler lesen), `Controller / Manager` (Regler anlegen und ändern; schließt `User` ein) |
| Menü | `Controller > Monitor` (die Seite), `Controller > Controllers` (nur Manager) |
| Seite (Client-Aktion `int_regler.app`) | Reglerwahl, Anmeldung am Dienst, vier Ansichten: Übersicht, Prozesswerte (Seiten, Suche), Fehler (aktiv, Verlauf, Fehlerwörter), Klemmen (setzen ohne Rückfrage, lösen, alle lösen) |
| `static/src/core_client.js` | Adresse, Anmeldung und Aufrufe des Dienstes; ohne Import aus Odoo, damit er allein prüfbar ist |
| `static/src/regler_poll.js` | liest eine Route des Dienstes in einem Takt und verwirft veraltete Antworten |

Die Werte kommen durch Abfragen alle 2,5 bis 10 s. Der Ereignisstrom des Dienstes (SSE) ist noch nicht angeschlossen.

## Was der Dienst dafür braucht

Das Modul läuft nur, wenn der Browser den Dienst unter der eingetragenen Adresse erreicht. Heute geht das so:

1. **Gleicher Ursprung über einen Reverse-Proxy.** Den Dienst unter einem Pfad der Odoo-Adresse veröffentlichen (zum Beispiel `/regler`) und diesen Pfad als Adresse eintragen. Kein CORS nötig.
2. **Anderer Ursprung:** der Dienst kennt noch **kein CORS**. Ohne es lehnt der Browser den Aufruf ab, die Seite zeigt dann „The controller service cannot be reached“ mit der Adresse. Das muss im Dienst ergänzt werden (erlaubte Herkunft als Einstellung).

Der Dienst weist außerdem im Betrieb `-ohne-token` Anfragen mit fremdem `Origin` ab; für den Einsatz mit Odoo läuft er mit Anmeldung.

## Offen

- CORS im Dienst, oder die Entscheidung für den Reverse-Proxy (Entscheidung 4 und 7 in `micserv-rekonstruktion/PLAN.md`).
- Kurzlebiges Token von Odoo statt eigener Anmeldung am Dienst; Zuordnung von Odoo-Gruppen zu den Rollen des Dienstes.
- Verknüpfung mit dem Reparaturauftrag (Fehler und Klemmungen als Datensätze), falls Odoo das Produktivsystem der Werkstatt wird.
- Konsole, Prüfprogramm und Programmieren (der Dienst kann sie, die Seite zeigt sie nicht).
- Übersetzung (`i18n/de.po`); die Quelltexte sind englisch.
- Ereignisstrom statt Abfragen.

## Prüfung

| Prüfung | Aufruf | Stand |
|---|---|---|
| Kern-Client ohne Odoo (11) | `node --test tools/int_regler/core_client.test.mjs` | läuft, alle bestanden |
| Seite mit echtem Owl in jsdom (59), Dienst gespielt | `cd tools/int_regler && npm install && node --import ./register.mjs components.check.mjs` | läuft, alle bestanden; braucht den Quelltext von Odoo 19 (`docs/odoo`, `../odoo` oder `ODOO_SRC`) |
| Modultests in Odoo (`tests/`, 15) | `TESTS_MODULE=int_regler tools/check/tests.sh` (Testserver „Tower“) | 4.11.2026: frische Installation ohne Warnung, 15 Tests, 0 Fehler |
| Ruff mit der Konfiguration des Repos | `ruff check` wie im pre-commit-Hook | ohne Befund |

Die jsdom-Prüfung ersetzt weder die Modultests noch einen Handtest im Browser. Sie hat die Templates mit echtem Owl übersetzt, die Props geprüft und zwei Fehler der Seite gefunden (ein Handler ohne `this`, ein nach Reglerwechsel stehen gebliebener Status). Nicht geprüft: das Aussehen mit dem CSS von Odoo und der Ablauf der Seite in einem echten Browser gegen eine laufende Instanz. Der Asset-Test zeigt nur, dass die Dateien im Bündel stehen und ihre Importe existieren.
