# Liedanzeige in Odoo 19 – Prüfung und Bauvorschlag

Prüfdatum: 23.10.2026. Grundlage: lokale Repositories `Liedanzeige`, `int-odoo-addons` und Odoo-Core Branch 19.0, Commit `8d05257d`. Addons-Stand beim Lesen: `14ec7d3`. Kein Online-Fetch, keine Änderung an den Repositories und keine Installation oder Tests auf einer produktiven Datenbank.

## Ergebnis

Das vorhandene Modul `int_liedanzeige` ist eine tragfähige Grundlage und bereits deutlich weiter als ein Gerüst. Es sollte als eigenständige Owl-Anwendung innerhalb von Odoo fertiggestellt werden. Odoo übernimmt Zustand, Eingaben, Einstellungen, Liedverwaltung und Echtzeitnachrichten. Ein zusätzlicher Go-Server ist für diese Zielarchitektur nicht erforderlich. Die Windows-Kiosk-Anwendung bleibt als native Hülle für Bildschirme und globale Tastatureingaben erhalten und erhält eine Odoo-Anbindung.

Eine einfache Einbettung der bestehenden React-Seiten würde dagegen weiterhin deren Go-Protokoll und einen zweiten Zustandsserver benötigen. Deshalb empfehle ich die vorhandene Owl-Umsetzung weiterzuführen. Diese Empfehlung bezieht sich auf den Funktionsumfang, nicht auf eine bereits nachgewiesene Produktionsreife.

## Was konkret vorhanden ist

| Funktion | Bestehende Go/React-Anwendung | Odoo-Modul |
|---|---|---|
| Lied- und Choranzeige | `/lied`, `/chor` | Gleiche Pfade, öffentliche Owl-Seiten |
| Uhr, Datum, Nummer, kleine Uhr | React und CSS | Owl, SCSS, dynamische Textskalierung |
| Zwei Steuerseiten | `/steuerung/lied`, `/steuerung/chor` | Vorhanden, Anmeldung und Bedienergruppe |
| Gemeinsame Bediennummer | `steuerungState` | `control_state` im Zustandsmodell |
| Lied wirkt auf beide Anzeigen | Go-Hub | Python-Aktionshandler |
| Chor separat | Go-Hub | Separater Zielparameter |
| Vier Stellen, Löschen, Rücktaste | Vorhanden | Vorhanden, inklusive Hilfstests |
| Einstellungen | JSON-Datei und WebSocket | Modellfelder, Wertebereiche und ORM |
| Echtzeit | Eigenes WebSocket-Protokoll | `bus.bus` und `bus_service` |
| Wiederverbindung | Go-WebSocket und Synchronisation | Zustandsabfrage über RPC angelegt |
| Liedverzeichnis | Im untersuchten Original kein entsprechendes Modell | Nummer, Titel, Text, Listen-/Formularansicht |
| Dirigent | Im untersuchten Original keine entsprechende Seite | `/dirigent`, eigene Gruppe, Liedtext |
| Kiosk-Fensterbefehle | Native Ausführung über Go | Befehle werden auf Bus-Kanal publiziert |
| Globale Numpad-Eingabe | Native Windows-Hooks | Noch keine Verbindung vom Original-Kiosk zum Odoo-Modul |
| Ereignisprotokoll | Go-Logkanal mit Historie | Keine entsprechende Moduloberfläche gefunden |

Das Modul hängt nur von `base`, `bus`, `web` ab. Ein eigenes Website-Modul ist für diese Seiten nicht erforderlich. Es verwendet einen gemeinsamen Zustandsdatensatz `state_main`; mehrere unabhängige Säle sind damit noch kein vorhandenes Produktmerkmal.

## Wichtige Befunde aus dem Code

### 1. Die Rückkehr zur Uhr braucht eine gemeinsame Zeitbasis

**Belegt:** Im Modell fehlen Zeitpunkt der letzten Eingabe und Ablaufzeit. Die Lied-Steuerseite führt ihren Timer im Browser und speichert dessen Start in `sessionStorage`. Jede Anzeige hat zusätzlich ihren eigenen lokalen Timer. Bei Ablauf einer Anzeige wird nur deren lokale Nummer geleert; der Datenbankzustand bleibt davon unberührt.

**Konkreter Fehlerfall aus dem Ablauf abgeleitet:** Alle Steuerseiten werden geschlossen, eine Anzeige fällt lokal auf die Uhr zurück. Ein späteres Neuladen holt die weiterhin gespeicherte Nummer erneut. Unterschiedlich spät geöffnete Anzeigen können zu unterschiedlichen Zeitpunkten ablaufen.

**Weiterer belegter Ablauf:** `display.js` ruft bei Nachrichten zuerst `applyNumber()` auf und setzt erst danach neue Einstellungen. Ein bestehender Timer wird bei gleicher Nummer nicht neu angelegt. Eine Änderung von `reset_delay` wirkt deshalb nicht zuverlässig sofort auf die laufende Anzeige.

**Bauvorschlag:** Ablaufzeit je unabhängigem Anzeigestrom serverseitig speichern. Nutzdaten enthalten `expires_at`, `server_now` und `revision`. Jede Ansicht berechnet die Restzeit aus demselben Ablaufzeitpunkt. Lese- und Aktionsmethoden behandeln abgelaufene Nummern konsistent. Lokale Timer dienen nur der Darstellung. Falls ein Cron den Datensatz zusätzlich bereinigt, darf dessen Takt nicht die sichtbare Umschaltgenauigkeit bestimmen.

Für die fachliche Parität explizit festlegen: Neue Ziffer startet Frist neu; Rücktaste hält die Frist oder startet sie neu; eine neue Liednummer aktualisiert beide Ziele, eine Chornummer nur Chor. Diese Regeln dann zentral abbilden und testen.

### 2. Der Windows-Kiosk ist protokollseitig noch nicht verbunden

**Belegt:** Der Original-Kiosk verbindet sich mit `ws://host:port/ws/steuerung` und `/ws/kiosk`. Die Standardeinstellung ist Port 1980. Das Odoo-Modul stellt diese Routen nicht bereit. Es publiziert Odoo-Bus-Nachrichten mit anderer Nutzdatenstruktur. Allein die Serveradresse auf Odoo umzustellen genügt daher nicht.

**Belegt:** Im Odoo-Frontend findet sich kein Empfänger für den Kiosk-Buskanal, der native Fensterbefehle ausführt. Die Anzeigeseite bietet bereits `window.__kioskBlackout`; das ersetzt keine Befehlsanbindung. Der Original-Kiosk kennt unter anderem `move_to`; die Odoo-Kommandoliste bietet derzeit keinen solchen zielbezogenen Auftrag.

**Empfohlene Lösung:** Go/Win32/WebView2 weiterverwenden. Eine eigene authentifizierte Odoo-Kioskseite empfängt Busmeldungen und übergibt ausschließlich erlaubte Fensterbefehle über die WebView2-Nachrichtenbrücke an Go. Go übernimmt Vollbild, Fenster, Monitorzuordnung, Neuladen und Beenden. Globale Numpad-Eingaben gehen über dieselbe Brücke zurück an die Odoo-Seite und deren authentifizierte Aktionsschnittstelle. Eine zentrale Kiosksteuerung pro Prozess verhindert doppelte Ausführung auf beiden Bildschirmfenstern.

Alternativ ist ein nativer Odoo-Client möglich; dieser müsste Sitzungsverwaltung, Wiederverbindung und das Odoo-Bus-Protokoll selbst implementieren. Die Browserbrücke nutzt die bereits vorhandenen Odoo-Dienste und reduziert diese Kopplung.

Kioskregistrierung mit Geräte-ID, letzter Rückmeldung, Monitoren, angewendeter Revision und Befehlsbestätigungen ergänzen. Der vorhandene globale Boolean `kiosk_fullscreen` kann mehrere Geräte oder abweichende Fensterzustände nicht darstellen. Zeitstempel `sent_at` wird bereits gesendet; Verwerfen alter Befehle und Bestätigung müssen im Empfänger tatsächlich implementiert werden.

### 3. Reihenfolge und Zustandsabgleich absichern

**Belegt:** Ziffern werden innerhalb einer Steuerseite über eine Promise-Kette serialisiert. Einstellungen haben eine eigene zusammenfassende Warteschlange. Das Modell liefert vollständige Zustände zurück und verschickt vollständige Bus-Nachrichten. Eine Zustandsrevision fehlt.

**Empfehlung:** Zustandsänderungen pro Kanal/Sitzung konsistent serialisieren und eine monotone Revision mitsenden. Clients ignorieren ältere Antworten. Das verhindert Rücksprünge durch verspätete RPC-Antworten neben neueren Busmeldungen. Parallelaktionen aus zwei Browsern gezielt gegen Odoos tatsächliche Transaktions- und Retry-Verarbeitung testen; aus fehlendem Python-Lock allein lässt sich kein bewiesener Datenverlust ableiten.

**Belegt:** Anzeige hört auf erste Verbindung und Wiederverbindung. Steuerung und Dirigent laden nur bei `BUS:RECONNECT` neu. Zwischen gerenderter Startkonfiguration und erster Busverbindung kann sich der Zustand ändern. Nach abgeschlossener erster Anmeldung/Subscription einen aktuellen Snapshot holen und mit Revision absichern.

### 4. Rechte sind sinnvoll begonnen, Kioskrolle ist zu breit

**Belegt:** Öffentliche Anzeigen erhalten nur Nummern und Einstellungen. Bedienung erfordert Bedienergruppe, Dirigentenansicht ihre eigene Gruppe. Bediener- und Dirigentennachrichten gehen über Gruppenrecords. Im untersuchten Core werden Benutzergruppen serverseitig zum Bus ergänzt; vom Client gelieferte Kanäle müssen Strings sein. Das schützt diese Gruppennachrichten vor bloßem Erraten eines Kanalnamens.

**Belegt:** Der angelegte Kiosk ist Portalbenutzer, trägt aber die Bedienergruppe. Über diese Gruppe besitzt er auch Schreib-, Erstell- und Löschrechte auf Liedern und kann sämtliche Bedienaktionen ausführen. Das ist mehr als eine reine Anzeigegeräterolle. API-Key-Erzeugung oder ein betriebsbereiter Kiosk-Login sind durch die Benutzeranlage allein nicht erledigt.

**Bauvorschlag:** Eigene Kioskgruppe und eng begrenzte Methoden für Gerätestatus und gegebenenfalls Numpad. Liedverwaltung getrennt halten. Anonyme Anzeigen weiterhin rein lesend. Kiosk-Befehle gerätebezogen und authentifiziert bereitstellen, keine Schlüssel in URLs oder öffentlichen HTML-Seiten ablegen.

Die bestehende Bediener-ACL erlaubt direkten Modell-Schreibzugriff. Falls alle Änderungen über validierte Aktionen und Bus laufen sollen, muss die Implementierung auch diesen Schreibweg berücksichtigen; sonst kann ein direkter ORM-Schreibaufruf den Aktionshandler umgehen.

### 5. Liedänderungen und Sprache vervollständigen

**Belegt:** Die Dirigentenansicht bekommt Liedtexte bei Zustandsbenachrichtigungen. Das Liedmodell überschreibt `create`, `write`, `unlink` nicht, um eine Änderung des aktuell angezeigten Texts mitzuteilen. Eine Textkorrektur ist deshalb nicht automatisch ein eigener Aktualisierungsimpuls für die geöffnete Dirigentenansicht.

Bei Änderung/Löschung des aktuell verwendeten Lieds gezielt aktualisieren. Führende Nullen sind gegenwärtig signifikant: `0012` und `12` sind unterschiedliche Textnummern. Diese Regel bewusst beibehalten oder normalisieren.

Die Oberflächen enthalten überwiegend englische Texte; ein deutsches Übersetzungsverzeichnis wurde im Modul nicht gefunden. Für die gewohnte deutsche Bedienung Übersetzung und Terminologie ergänzen.

## Technische Zielstruktur

Bediener- und Dirigentenansicht als eigenständige Owl-Seiten im Odoo-HTTP-Prozess betreiben. Keine komplette Odoo-Backendnavigation auf dem Beamer anzeigen. Das Grundmuster aus Controller, QWeb-Seite, eigenem Assetbundle und Owl-Komponente entspricht der offiziellen Anleitung.

Den manuellen Bootcode und das umfangreiche Assetbundle gegen `mountComponent` und die benötigten Dienste vereinfachen, soweit die Komponentenanforderungen das zulassen. Die öffentliche Seite muss den Odoo-Bus vollständig starten können. Die offizielle Anleitung verwendet `get_frontend_session_info`; das Modul nutzt `session_info`. Das ist ein gezielter Integrationsprüfpunkt, kein hier belegter Laufzeitfehler.

Empfohlene Verantwortlichkeiten:

- Python: verbindliche Aktionen, Zustandsrevision, Ablaufzeit, Rechte, Liedverwaltung und Bus-Publikation.
- Owl: Darstellung, Tastatur/Touch, Einstellungsbedienung, Verbindungsanzeige und Wiederabgleich.
- Native Hülle: Monitore, Fenster, globale Tasten und lokale Gerätefunktionen.
- PostgreSQL: persistenter Zustand und Einstellungen; Busnachrichten sind Aktualisierungsimpulse, der Zustand bleibt jederzeit abrufbar.

Bei einem einzigen Raum den Singleton zunächst behalten. Mehrere unabhängige Räume erst mit explizitem Sitzungs-/Raummodell und kanalbezogenen Rechten ergänzen; ein Raumfeld allein isoliert öffentliche Buskanäle nicht.

## Sinnvolle Reihenfolge der Umsetzung

1. Zustandsvertrag festlegen: Kopplung Lied/Chor, gemeinsame Bediennummer, Sperrregeln, Ablaufregeln und Restartverhalten. In Regressionstests festhalten.
2. Ablaufzeiten und Revision im vorhandenen Modell ergänzen. Vollständige Snapshots bei Erstverbindung und Wiederverbindung. Zwei Bediener und verspätete Antworten testen.
3. Bestehende Owl-Seiten im echten Odoo-Browser starten, Assets und Bus prüfen; Timer, Einstellungen, Schriftgrößen und mobile Bedienung abnehmen.
4. Kioskrolle und Odoo-Kioskseite bauen; Go-Hülle über WebView2 anbinden. Numpad sowie native Monitor- und Fensterbefehle mit Bestätigungen testen.
5. Liedtextaktualisierung, deutsche Oberfläche und ein begrenztes Ereignisprotokoll ergänzen. API-Schlüssel niemals protokollieren.
6. In separater Odoo-Testdatenbank auf der tatsächlich eingesetzten Container-Version installieren und prüfen. Danach Pilot mit den realen Bildschirmen.

## Prüfnachweis und Abnahme

**Ausgeführt:** Die zwei vorhandenen JavaScript-Testsuiten liefen mit Node: 19 Tests bestanden, 0 fehlgeschlagen. Geprüft werden Numpad-/Timer-/Layout-Hilfen und Einstellungswarteschlange. Node meldet lediglich die automatische Erkennung von ES-Modulen ohne package-Typangabe.

**Im Repository vorhanden:** 59 Python-Testmethoden für Zustand, Bus, HTTP, Lieder und Kioskbenutzer. Diese wurden in dieser Prüfung nicht ausgeführt. Die HTTP-Tests prüfen unter anderem Antwortstatus und Assetabruf; sie sind kein Beleg, dass Owl in einem echten Browser fehlerfrei startet. Keine Browser-Tours oder `browser_js`-Tests im Modul gefunden.

Für die Betriebsfreigabe müssen mindestens diese Situationen bestehen:

- Zwei Steuerseiten tippen schnell und gleichzeitig, ohne Ziffern zu verlieren oder alte Zustände anzuzeigen.
- Anzeige wird nach Fristablauf neu geladen und bleibt bei der Uhr; dasselbe gilt ohne geöffnete Steuerseite.
- Änderung der Frist während einer Nummer wirkt konsistent auf alle Anzeigen.
- Odoo-/Proxy-Neustart und Netzwerkunterbrechung führen zu einem korrekten Snapshot.
- Anonyme Clients können nicht steuern oder Liedtexte lesen; Kiosk darf keine Lieder verwalten.
- Numpad funktioniert ohne Fensterfokus; Vollbild, Monitorwechsel und Quit werden einmal pro gewünschtem Ziel ausgeführt.
- Korrigierter Liedtext erscheint bei geöffnetem Dirigentenbildschirm.
- WebSocket-Verbindung funktioniert über genau den später eingesetzten Reverse Proxy. Bei Odoo-Multiprocessing ist die passende WebSocket-/Gevent-Weiterleitung zu prüfen; nicht pauschal Port 8072 für jede Betriebsart voraussetzen.

Die lokale Core-Kopie wurde gegen ihre tatsächlichen APIs gelesen. Ihre Gleichheit mit der produktiven Container-Version wurde nicht behauptet. Auf produktivem Odoo wurden keine Testdaten angelegt und keine Konfigurationen geändert.

## Quellen und zentrale Dateien

- Offizielle Odoo-19-Anleitung: https://www.odoo.com/documentation/19.0/developer/howtos/standalone_owl_application.html
- Odoo-Core lokal: `C:/Users/waldemar.toews/Documents/GitHub/odoo`, Branch 19.0, Commit 8d05257d. Besonders `addons/bus/models/ir_websocket.py`, `addons/bus/static/src/services/bus_service.js`, `addons/web/models/ir_http.py` und `odoo/orm/fields_textual.py`.
- Modul: `C:/Users/waldemar.toews/Documents/GitHub/int-odoo-addons/int_liedanzeige`.
- Original: `C:/Users/waldemar.toews/Documents/GitHub/Liedanzeige/Development`.

Konkrete Einstiegspunkte im Modul: `models/int_liedanzeige_state.py:71`, `static/src/display/display.js:122`, `static/src/control/control.js:198`, `static/src/common/boot.js`, `controllers/int_liedanzeige.py`, `security/ir.model.access.csv`.
Im Original: `Development/kiosk/numpad.go:160` und `Development/kiosk/screen.go:272` für das inkompatible Go-Protokoll.
