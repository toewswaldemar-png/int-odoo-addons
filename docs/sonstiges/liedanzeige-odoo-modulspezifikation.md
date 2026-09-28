# Liedanzeige als Odoo-Modul — Spezifikation

Status: **Konzept/Analyse, noch nicht umgesetzt.** Dieses Dokument fasst die Architekturentscheidungen zusammen, die für eine mögliche Portierung des eigenständigen Go/React-Systems ([README.md](../../Liedanzeige/README.md), [CLAUDE.md](../../Liedanzeige/CLAUDE.md), separates Repo `Liedanzeige`) auf ein Odoo-Modul getroffen wurden. Keine der Entscheidungen ist final umgesetzt.

## 1. Ziel und Abgrenzung

Die heutige Anwendung zeigt auf Beamer-Displays ausschließlich eine bis zu 4-stellige Liednummer (oder eine Uhr im Ruhezustand). Diese Grundfunktion bleibt für die öffentlichen Displays **unverändert** — keine Liedtexte, kein GEMA/CCLI-Thema, weil dort nach wie vor nur die Nummer projiziert wird (Nachschlagen im physischen Gesangbuch bleibt Aufgabe der Gemeinde/des Chors).

Neu hinzu kommt eine **dritte, nicht-öffentliche Rolle**: eine Dirigenten-Ansicht mit Zugriff auf hinterlegte Liedtexte, geschützt durch eine eigene Odoo-Berechtigungsgruppe. Diese Ansicht wird nicht projiziert, sondern von einer einzelnen berechtigten Person auf einem eigenen Bildschirm/Tablet genutzt.

### Drei Rollen im Überblick

| Rolle | Sichtbar für | Inhalt | Auth |
|---|---|---|---|
| Öffentliche Displays (`/lied`, `/chor`) | Beamer/Projektion | Nur Ziffer oder Uhr, wie heute | `auth='public'` |
| Steuerung (`/steuerung/lied`, `/steuerung/chor`) | Bedienperson | Numpad, Einstellungen, Kiosk-Fernsteuerung | `auth='user'`, Gruppe „Operator" |
| Dirigent (`/dirigent`) | Chorleiter:in | Chor-Nummer + Liedtext groß, Lied-Nummer optional klein daneben | `auth='user'`, Gruppe „Dirigent" |

## 2. Datenmodell

### `liedanzeige.state` — laufender Anzeigezustand (Singleton)

Ersetzt den In-Memory-`Hub` aus [hub.go](../../Liedanzeige/Development/server/hub.go) durch einen persistierten Odoo-Datensatz. Bei jeder Aktion (`input`/`backspace`/`reset`/`settings`) erfolgt ein normales ORM-`write()`, gefolgt von einem `bus.bus`-Push an die betroffenen Kanäle.

```python
class LiedanzeigeState(models.Model):
    _name = "liedanzeige.state"
    _description = "Laufender Anzeige-Zustand (Singleton pro Instanz)"

    lied_state = fields.Char(default="")
    chor_state = fields.Char(default="")
    steuerung_state = fields.Char(default="")

    time_size = fields.Integer(default=75)
    sub_clock_size = fields.Integer(default=75)
    gap_time_date = fields.Integer(default=0)
    font = fields.Selection([...], default="segoe-ui")
    shadow_strength = fields.Integer(default=40)
    reset_delay = fields.Integer(default=5)
```

Feldnamen/Defaults sind 1:1 aus [config.go](../../Liedanzeige/Development/server/config.go) und [types.ts](../../Liedanzeige/Development/frontend/src/lib/types.ts) übernommen (`DisplaySettings`/`DEFAULTS`), damit keine Bedeutung verloren geht.

### `liedanzeige.lied` — Liedtext-Datenbank (neu, nicht im Go-System vorhanden)

```python
class LiedanzeigeLied(models.Model):
    _name = "liedanzeige.lied"
    _description = "Lied/Choral mit Nummer und Text"
    _rec_name = "titel"

    nummer = fields.Char(required=True, index=True)   # Char statt Integer: führende Nullen/Suffixe möglich
    titel = fields.Char()
    liedbuch = fields.Char()          # z.B. "Gesangbuch XY", falls mehrere Bücher im Umlauf sind
    strophen = fields.Text()          # einfache erste Version; ggf. später one2many für Einzel-Strophen-Navigation

    _sql_constraints = [
        ("nummer_liedbuch_uniq", "unique(nummer, liedbuch)", "Diese Nummer existiert bereits in diesem Liedbuch."),
    ]
```

**Offen:** Ob `strophen` ein einzelnes Textfeld bleibt oder als `one2many` auf ein `liedanzeige.strophe`-Modell aufgeteilt wird, hängt davon ab, ob der Dirigent später strophenweise vor-/zurückblättern soll. Für die erste Version reicht ein Textfeld, das der Dirigent-View komplett anzeigt/scrollt.

## 3. Odoo-Modulaufbau

```
liedanzeige/
├── __manifest__.py
├── models/
│   ├── liedanzeige_state.py
│   └── liedanzeige_lied.py
├── controllers/
│   └── main.py
├── static/src/
│   ├── display/            # /lied, /chor — unverändert zur heutigen Optik
│   │   ├── display.js
│   │   └── display.xml
│   ├── steuerung/          # /steuerung/lied, /steuerung/chor
│   │   ├── steuerung.js
│   │   └── steuerung.xml
│   └── dirigent/           # /dirigent — neu
│       ├── dirigent.js
│       └── dirigent.xml
├── security/
│   ├── ir.model.access.csv
│   └── liedanzeige_groups.xml   # group_liedanzeige_operator, group_liedanzeige_dirigent
└── views/
    └── liedanzeige_lied_views.xml   # Backend-Pflege der Liedtexte (Liste/Formular)
```

Falls das Modul tatsächlich umgesetzt wird, ist dieses Repo (`int-odoo-addons`, Präfix `int_`) der vorgesehene Ort — analog zu `int_filemanager`, `int_repair_workshop` etc. Modulname vermutlich `int_liedanzeige`.

## 4. Controller & Routen

Alle Seiten-Routen (`type='http'`, liefern das jeweilige QWeb-Template mit eingebettetem OWL-Root):

| Route | `auth` | Zweck |
|---|---|---|
| `/lied`, `/chor` | `public` | Anzeige-Displays (unverändert) |
| `/steuerung/lied`, `/steuerung/chor` | `user` (Gruppe Operator) | Bedienung |
| `/dirigent` | `user` (Gruppe Dirigent) | Chor-Nummer + Liedtext |
| `/health` | `public` | Health-Check für Kiosk-Polling |

Action-Endpoint für Eingaben (Numpad, Settings, Kiosk-Befehle):

```python
@http.route('/liedanzeige/action', type='http', auth='user', methods=['POST'], csrf=False)
def action(self, **kw):
    payload = json.loads(request.httprequest.data)
    ...
    return request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
```

**Entscheidung `type='http'` statt `type='jsonrpc'`:** siehe Abschnitt 8. Grund: sowohl die OWL-Steuerung als auch der native Go-Kiosk rufen diesen Endpoint auf; ein reiner JSON-Body ohne Odoo-eigene JSON-RPC-2.0-Hülle ist für den Go-Client deutlich einfacher zu implementieren und für die OWL-Seite über den `http`-Service ebenso einfach nutzbar — beide Aufrufer teilen sich exakt denselben Vertrag.

## 5. Echtzeit-Kommunikation (`bus.bus` statt eigenem WebSocket-Hub)

Ersetzt [hub.go](../../Liedanzeige/Development/server/hub.go) `broadcast()`. Kanäle (als einfache String-Kanäle, kein recordset-gebundener Kanal mit Leserechteprüfung — funktional äquivalent zur heutigen Origin-Check-basierten Offenheit):

| Kanal | Payload | Abonnenten |
|---|---|---|
| `liedanzeige_lied` | `{action, key/value, ...}` wie heutiges `WsMessage` | `/lied`-Display |
| `liedanzeige_chor` | dito | `/chor`-Display |
| `liedanzeige_steuerung` | `{action, target, steuerungState, ...}` | alle offenen Steuerung-Tabs |
| `liedanzeige_dirigent` | `{chorNummer, chorText, liedNummer}` | `/dirigent` |
| `liedanzeige_kiosk` | `{command, screen, monitor}` | Go-Kiosk (Fernsteuerung) |
| `liedanzeige_log` | `{level, message, ts}` | Log-Panel in Steuerung |

Transport: Odoos eingebautes `/websocket` (kein eigener Server-Prozess nötig). Jede State-Änderung: ORM-`write()` → `self.env['bus.bus']._sendone(channel, 'liedanzeige_notify', payload)`.

**Dirigent-Payload-Logik:** Bei jeder Chor-Nummern-Änderung sucht der Server `liedanzeige.lied` per `nummer == chorState`; Treffer → Text mitschicken, kein Treffer → nur Nummer, Anzeige zeigt dann nur die Zahl (kein Fehlerzustand). Lied-Nummer wird zusätzlich als reine Zahl mitgeschickt (kein Text-Lookup nötig), Anzeige im Dirigent-View ein-/ausblendbar (Toggle, reine Frontend-Einstellung, kein Server-Konzept).

## 6. Sicherheit / Rechte

- `group_liedanzeige_operator`: Zugriff auf `/steuerung/*` und den Action-Endpoint.
- `group_liedanzeige_dirigent`: Zugriff auf `/dirigent` und Lese-Zugriff auf `liedanzeige.lied`.
- Öffentliche Display-Routen bleiben `auth='public'`, Sicherheitsniveau entspricht dem heutigen Origin-Check (wer die URL/den Kanalnamen kennt, kann mitlesen) — für ein Gemeindegerät im eigenen LAN akzeptiert.
- Das ist gegenüber heute ein echter Sicherheitsgewinn: aktuell gibt es außer dem Origin-Check keinerlei Rechteprüfung; mit Odoo-Login entsteht erstmals eine echte Trennung Operator/Dirigent/Öffentlichkeit.

## 7. Frontend (OWL statt React)

Kein automatischer Port — Konzepte aus [Liedanzeige.tsx](../../Liedanzeige/Development/frontend/src/pages/Liedanzeige.tsx) / [Steuerung.tsx](../../Liedanzeige/Development/frontend/src/pages/Steuerung.tsx) müssen in OWL 2 neu geschrieben werden:

- Rescale-Hook (Text auf 100vw messen, Skalierung berechnen) — reine DOM-Logik, 1:1 übertragbar.
- Reset-Timer-Logik, Numpad-Sperre zwischen Lied/Chor — Zustandsmaschine bleibt gleich, nur React-Hooks → OWL-`useState`/`onWillUpdateProps`-Äquivalente.
- Server-Kommunikation: statt `useWebSocket.ts` (Handrolled, 2s-Reconnect) → Odoos `bus_service` (`@web/core/bus_service`), übernimmt Reconnect/Backoff.
- Action-Aufrufe: **`useService("http")`** (`.post(route, params)`) statt `rpc()` — siehe Abschnitt 8 für die Begründung.

## 8. JSON-RPC vs. JSON-2 vs. plain HTTP — Rechercheergebnis

Wichtige Klarstellung, die die Entscheidung in Abschnitt 4/7 trägt:

- Odoo 18 hat `@http.route(type='json')` in `type='jsonrpc'` umbenannt (alter String als deprecated Alias mit einmaliger Warnung erhalten, [PR #195132](https://github.com/odoo/odoo/pull/195132)/[#195169](https://github.com/odoo/odoo/pull/195169)). Dokumentiert sind für `@http.route` **nur** `'http'` und `'jsonrpc'` ([Web Controllers, Odoo 19.0](https://www.odoo.com/documentation/19.0/developer/reference/backend/http.html)) — **kein** `type="json2"`.
- „JSON-2" (`/json/2/<model>/<method>`, [External JSON-2 API](https://www.odoo.com/documentation/19.0/developer/reference/external_api.html)) ist etwas komplett anderes: Odoos **externe** RPC-Schnittstelle für Drittsysteme (API-Key/Bearer-Auth statt User/Passwort), Ersatz für `/xmlrpc`, `/xmlrpc/2`, `/jsonrpc` bei External-Integrationen. Betrifft **nicht** eigene Controller-Routen innerhalb unseres Moduls.
- Für unsere eigenen Endpunkte gibt es zwei valide Wege: `type='jsonrpc'` (Odoo-JSON-RPC-2.0-Hülle, passend zum JS-`rpc()`-Service) oder `type='http'` (roher JSON-Body, kein Envelope). Odoo hat für Letzteres einen eigenen, dedizierten JS-Service (`useService("http")`, `.get()`/`.post()`, [Services-Doku](https://www.odoo.com/documentation/19.0/developer/reference/frontend/services.html)) — **kein Zwang, `rpc()`/`jsonrpc` zu verwenden.**
- **Entscheidung:** `type='http'` + `useService("http")` für alle Action-Endpoints, weil sowohl die OWL-Steuerung als auch der Go-Kiosk exakt denselben simplen Vertrag (roher JSON-POST) nutzen sollen, ohne dass der Go-Client Odoos JSON-RPC-2.0-Envelope nachbauen muss.
- **Verbleibende Unsicherheit:** Kein verifiziertes Python+JS-Vollbeispiel für `useService("http")` in Kombination mit einer selbst geschriebenen `type='http'`-Route gefunden — vor der Umsetzung an einem bestehenden Odoo-Core-Modul gegenprüfen, das diesen Service tatsächlich nutzt.

## 9. Settings-Persistenz — Mapping der heutigen 3 Schichten

| Heute | Odoo |
|---|---|
| `localStorage` (Fallback-Erstwert) | bleibt identisch im OWL-Client |
| Hub-Memory (autoritativ zur Laufzeit) | `liedanzeige.state`-Datensatz im Python-Prozess/Request-Kontext |
| `settings.json` (Neustart-Persistenz) | Postgres-Zeile (automatisch persistent, kein eigener Schreib-Mechanismus nötig) |

## 10. Kiosk-Anpassung (bleibt natives Go/Win32-Programm)

Bestätigt: Fernsteuerung (Vollbild/Fenster, Reload, Monitor-Tausch, Beenden) und der fokus-unabhängige Numpad-Hook werden weiterhin gebraucht (Fenster kann Fokus verlieren) → der native Kiosk aus [Development/kiosk/](../../Liedanzeige/Development/kiosk) im Liedanzeige-Repo bleibt vollständig erhalten, nur die Transport-Schicht wird ausgetauscht:

- **Anzeige-Navigation:** WebView2 → `https://odoo-host/lied` / `/chor` statt `localhost:1980/...`.
- **Kiosk-Befehle empfangen:** Odoo-Websocket-Client (`subscribe`-Handshake) auf Kanal `liedanzeige_kiosk` statt eigenem WS-Kanal; Nachrichtenformat inhaltlich unverändert (`fullscreen`/`windowed`/`reload`/`move_to`/`quit`).
- **Numpad-Weiterleitung senden:** POST an `/liedanzeige/action` statt WS-Send an `hub.go`.
- **Health-Check:** `/health`-Route in Odoo-Controller nachbilden.
- Restliche Kiosk-Logik (Win32-Fenstermanagement, Hotkeys, Monitor-Erkennung, Fenster-Zustand in `%TEMP%`) — **unverändert**, kein Rewrite.

## 11. Bewusst nicht übernommen / entfällt

- **UDP-Discovery (Port 1981):** kein Odoo-Äquivalent; entweder Kiosk-Konfiguration mit fester Odoo-URL (typisch für Odoo-Deployments ohnehin üblich) oder die kleine Go-UDP-Antwortlogik bleibt als eigenständiges Zusatzprogramm bestehen.
- **Firewall-Autokonfiguration via `netsh`/UAC:** entfällt, wenn Odoo auf einem regulären Server (Standardport 8069/443) läuft statt als lokaler Prozess auf dem Anzeige-Rechner.
- **Eigener Go-HTTP-Server:** entfällt vollständig zugunsten der Odoo-Instanz.

## 12. Offene Punkte

1. **Ziel-Instanz:** Läuft das Modul auf der bestehenden `int-odoo-addons`-Unraid-Instanz (Odoo 19) oder auf einer eigenen, dedizierten Odoo-Instanz? Beeinflusst Multi-Tenancy-Fragen (aktuell keine vorgesehen) und Betriebsaufwand.
2. **Strophen-Datenmodell:** einfaches `Text`-Feld vs. `one2many` für Einzelstrophen-Navigation im Dirigent-View (siehe Abschnitt 2).
3. **`rpc()` vs. `http`-Service:** vor Implementierung an echtem Odoo-Core-Beispiel verifizieren (siehe Abschnitt 8).
4. **Websocket-Infrastruktur im Deployment:** Odoo-Worker-Modus (`ThreadedServer` vs. `PreforkServer`) und Reverse-Proxy-Konfiguration für WebSocket-Upgrade auf der Zielinstanz prüfen, bevor produktiv migriert wird.
5. **Liedtext-Erfassung:** manuelle Pflege über Odoo-Backend-Formular (Abschnitt 3, `views/`) reicht für den Start; Bulk-Import aus einer bestehenden Gesangbuch-Quelle ist nicht Teil dieser Spezifikation.

## 13. Nicht-Ziele

- Keine Liedtext-Anzeige auf den öffentlichen Displays (`/lied`, `/chor`) — vermeidet bewusst die GEMA/CCLI-Lizenzfrage, die bei tatsächlicher Projektion von Liedtexten entstünde.
- Kein Rewrite des Kiosk-Clients — nur Protokoll-Adapter (Abschnitt 10).
- Keine Gottesdienstplanungs-Integration (`calendar.event`-Anbindung o.ä.) in diesem ersten Zuschnitt — als spätere Erweiterungsidee im Hinterkopf behalten, aber nicht Teil dieser Spezifikation.
