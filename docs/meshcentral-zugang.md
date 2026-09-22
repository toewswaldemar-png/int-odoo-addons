# MeshCentral-Zugang

Stand: 2026-09-22

## Zugang

MeshCentral-Server: `https://192.100.0.210` (WebSocket-API: `wss://192.100.0.210`).

Der Zugriff erfolgt **nicht** über das Browser-Login, sondern über einen lokalen CLI-Wrapper (`connect.cjs`, ruft intern `meshctrl.js` auf). Der Wrapper liest die Zugangsdaten automatisch aus einer lokalen Datei ein — diese Datei nie ausgeben, committen oder teilen.

Jedes Gerät/jeder Agent mit Zugriff hat einen eigenen Login-Token und einen eigenen lokalen Wrapper-Ordner, damit Zugänge einzeln widerrufbar bleiben.

## Nutzung

Alle Befehle laufen im Verzeichnis, das `connect.cjs` enthält, mit `/`-Pfaden (unter Git-Bash sonst Pfadfehler):

```
node ./meshcentral-access/connect.cjs serverinfo
node ./meshcentral-access/connect.cjs listdevices
node ./meshcentral-access/connect.cjs help runcommand
```

- `serverinfo` — prüft die Verbindung zum Server und zeigt Basisdaten (Version, TLS-Hash, Ports).
- `listdevices` — listet alle Geräte gruppiert nach Gerätegruppe, mit Verbindungs- und Power-Status.
- `help runcommand` — zeigt die Syntax für Remote-Befehle auf einem Gerät.

## Gerätegruppen

`listdevices` zeigt die Geräte gruppiert nach Kategorie (Notebooks, Workstations, Mini-PCs, Server, Desktops). Die Server-Gruppe enthält die zentralen Infrastruktursysteme (u.a. Domain Controller, Fileserver, Hypervisor) — konkrete Gerätenamen bewusst nicht in diesem Dokument, per `listdevices` jederzeit aktuell abrufbar.

## Sicherheitshinweise

Das eingebettete Browser-Pane von Claude Code verweigert die Navigation zum MeshCentral-Server (vermutlich wegen selbstsigniertem Zertifikat) — der CLI-Wrapper ist deshalb der einzige praktikable Weg für KI-Agenten, ohne Zugangsdaten manuell in ein Formular einzugeben.

Zugangsdaten liegen ausschließlich lokal neben `connect.cjs` und werden nie in Dokumentation, Commits oder Chats übernommen. Wird ein neuer Zugang benötigt, wird er direkt in MeshCentral erzeugt und lokal auf dem jeweiligen Gerät hinterlegt.
