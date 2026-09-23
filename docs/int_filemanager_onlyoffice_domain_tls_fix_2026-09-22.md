# OnlyOffice/Odoo: DNS, Zertifikat und Host-Header-Fehler behoben

Stand 2026-09-22. Ausgangssymptom: `.docx`/`.xlsx`-Dateien ließen sich über `int_filemanager` mit
ONLYOFFICE nicht öffnen ("ONLYOFFICE kann nicht erreicht werden"), zunächst nur über VPN gemeldet,
später auch lokal reproduziert. Die Fehlermeldung blieb bei jedem der fünf gefundenen Probleme
identisch — das hat die Diagnose deutlich erschwert, da dieselbe Oberfläche fünf unabhängige
Ursachen verdeckt hat.

Betroffene Infrastruktur: Unraid-Host `unraid-odoo` (192.100.0.119) mit Docker-Containern `Odoo19`,
`odoo_db` (Postgres), `Cloudreve_office` (ONLYOFFICE Document Server), `Nginx-Proxy-Manager-Official`
(NPM, TLS-Terminierung/Reverse-Proxy). DNS über die AD-Domäne `Herrmann.local`
(Controller `HM-DC01`/`HM-DC02`).

---

## 1. DNS: `onlyoffice.local` / `odoo.lan` waren nie echte Domänen-Einträge

Beide Hostnamen waren in NPM/Odoo konfiguriert, existierten aber auf keinem der DNS-Server der
Domäne (`HM-DC01`, `HM-DC02`, weitere NS-Einträge der Zone). Sie funktionierten bislang nur
zufällig auf manchen Geräten:

- `onlyoffice.local` vermutlich per mDNS (die `.local`-TLD ist dafür reserviert, RFC 6762) —
  funktioniert nur zwischen Geräten im selben Layer-2-Segment wie der Host.
- `odoo.lan` vermutlich über einen Router, der `.lan`-Namen für DHCP-Clients auflöst, nicht über die
  Domänen-DNS.

**Fix:** Neue A-Records innerhalb der bestehenden, echten AD-Zone `Herrmann.local` angelegt:

| Name | IP |
|---|---|
| `onlyoffice.herrmann.local` | 192.100.0.119 |
| `odoo.herrmann.local` | 192.100.0.119 |

Repliziert automatisch auf beide Domain Controller (per `Resolve-DnsName` gegen `HM-DC02` bestätigt).
Eine dritte, für `odoo.lan` naheliegende eigene DNS-Zone `lan` wurde bewusst **nicht** angelegt
(deutlich invasiverer Eingriff auf einem Produktiv-DC als ein Host-Eintrag in einer bestehenden
Zone) — stattdessen Odoo komplett auf `odoo.herrmann.local` umgezogen (siehe Abschnitt 3).

---

## 2. Zertifikat: abgelaufen und falscher Name

In NPM (SQLite-DB unter `/mnt/user/appdata/Nginx-Proxy-Manager-Official/data/database.sqlite`,
Tabelle `certificate`) fanden sich zwei selbstsignierte "Custom"-Zertifikate:

| Zertifikat | Ausgestellt für | Gültig bis |
|---|---|---|
| `odoo.lan` | `odoo.lan` + IP-SAN | 2036 (frisch, sauber gebaut) |
| `onlyoffice.lan` | nur `onlyoffice.lan`, keine IP-SAN | **2025-11-21 — seit Monaten abgelaufen** |

Zusätzlich stimmte der Proxy-Host-Domainname (`onlyoffice.local`) mit keinem der beiden je
existierenden Zertifikatsnamen (`onlyoffice.lan`) überein — ein zweites, unabhängiges
Zertifikatsproblem neben dem Ablauf.

**Fix:** Neue selbstsignierte Zertifikate nach dem robusteren Muster von `odoo.lan` erzeugt
(RSA 2048, 10 Jahre Laufzeit, SAN mit Hostname **und** IP):

```bash
openssl req -x509 -nodes -newkey rsa:2048 \
  -keyout <name>.key -out <name>.crt -days 3650 \
  -subj "/CN=<name>" \
  -addext "subjectAltName=DNS:<name>,IP:192.100.0.119" \
  -addext "basicConstraints=CA:TRUE" \
  -addext "keyUsage=digitalSignature,keyCertSign,cRLSign" \
  -addext "extendedKeyUsage=serverAuth"
```

Für `onlyoffice.herrmann.local` und `odoo.herrmann.local` je einmal ausgeführt, als "Custom
Certificate" in NPM hochgeladen und dem jeweiligen Proxy-Host zugewiesen. Proxy-Host-Domainnamen
entsprechend von `onlyoffice.local`/`odoo.lan` auf `onlyoffice.herrmann.local`/`odoo.herrmann.local`
geändert.

**Offener Punkt, nicht umgesetzt:** `basicConstraints=CA:TRUE` ist eigentlich für ein
Server-/Leaf-Zertifikat unüblich (das ist eine CA-Eigenschaft) — hat sich in dieser Session nicht als
Problemursache gezeigt, wäre aber bei einer sauberen Neuausstellung zu korrigieren
(`basicConstraints=CA:FALSE`, `keyUsage=digitalSignature,keyEncipherment`).

**Diskutiert, bewusst zurückgestellt:** echte CA-signierte Zertifikate statt selbstsigniert, entweder
über eine interne AD Certificate Services-CA (automatisches Vertrauen für alle domänenverbundenen
Geräte) oder über Let's-Encrypt-DNS-01-Challenge auf der vorhandenen Strato-Domain (öffentlich
vertrauenswürdig, ohne dass der Hostname öffentlich erreichbar sein muss, aber laufende
Erneuerungsautomatisierung nötig, da Let's-Encrypt-Zertifikate nur 90 Tage gültig sind). Keine
Entscheidung, aktuell bleibt es bei den selbstsignierten Zertifikaten.

---

## 3. Odoo: Parameteränderung per SQL wurde durch In-Memory-Cache ignoriert

`onlyoffice_connector.doc_server_public_url` wurde direkt per `UPDATE ir_config_parameter ...`
(psql) geändert, nicht über Odoos ORM (`env["ir.config_parameter"].set_param()`). Odoo hält
Konfigurationsparameter in einem `ormcache` pro Worker-Prozess, der nur bei einer Änderung über die
ORM automatisch invalidiert wird — ein rohes SQL-`UPDATE` umgeht das. Der laufende Worker hat
danach weiter den **alten** Wert (`https://onlyoffice.local:18443/`) ausgeliefert, obwohl `SELECT`
in Postgres bereits den neuen Wert zeigte.

Sichtbare Folge: `docApiJS` in der `get_config`-Antwort zeigte weiterhin auf den alten,
nicht mehr gültigen Hostnamen → `net::ERR_SSL_UNRECOGNIZED_NAME_ALERT`, weil nginx für
`onlyoffice.local` nach der Umbenennung des Proxy-Hosts keinen Server-Block mehr hatte.

**Fix:** `docker restart Odoo19` (Cache-Reset durch Neustart). Zusätzlich `web.base.url` von
`https://odoo.lan:18443` auf `https://odoo.herrmann.local:18443` umgestellt (ebenfalls per SQL,
daher derselbe Neustart nötig) — betrifft u.a. die lokale Office-WebDAV-Öffnen-Funktion
(`ms-word:ofe|u|<web.base.url>/...`): Word läuft zwar lokal auf dem Client, muss aber selbst eine
Netzwerkverbindung zu dieser URL aufbauen, um die Datei zu laden/speichern — DNS-Auflösung auf dem
Client ist also auch dafür zwingend nötig.

**Lehre für künftige Config-Änderungen:** `ir.config_parameter`-Werte über die ORM/Odoo-Shell
ändern, nicht per rohem SQL — sonst braucht es einen Neustart, um den Cache zu leeren.

---

## 4. NPM: `$host` statt `$http_host` schneidet den Port aus dem Host-Header

Odoo ist von diesem Bug nicht betroffen (baut seine URLs aus `web.base.url`), ONLYOFFICE aber
schon: Es konstruiert eigene absolute URLs (Redirect auf `/welcome/`, Cache-Datei-Downloads wie
`/cache/files/.../Editor.bin`) aus dem eingehenden `Host`-Header. NPMs gemeinsam genutztes
Include `conf.d/include/proxy.conf` (gilt für **alle** Proxy-Hosts) setzt

```
proxy_set_header Host $host;
```

— nginx' `$host` ist der Hostname **ohne Port**. Der Port ging beim Weiterleiten an den
ONLYOFFICE-Container verloren, wodurch dessen selbst gebaute URLs auf Port 443 statt 18443 zeigten
(`ERR_CONNECTION_REFUSED`, da auf 192.100.0.119:443 nichts lauscht).

**Fix:** Nicht die gemeinsame Datei angefasst (Blast-Radius: alle Proxy-Hosts), stattdessen im
NPM-Proxy-Host `onlyoffice.herrmann.local` unter **Advanced → Custom Nginx Configuration** ergänzt
(zusätzlich zum vorhandenen, ungenutzten Collabora/`loleaflet`-Vorlagen-Inhalt):

```nginx
location ~ ^/ {
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection $http_connection;
    proxy_http_version 1.1;
    proxy_set_header Host $http_host;
    proxy_set_header X-Forwarded-Scheme $scheme;
    proxy_set_header X-Forwarded-Proto  $scheme;
    proxy_set_header X-Forwarded-For    $proxy_add_x_forwarded_for;
    proxy_set_header X-Real-IP          $remote_addr;
    proxy_pass       $forward_scheme://$server:$port$request_uri;
}
```

Funktioniert, weil NPMs generierter Standard-`location /`-Block **ohne** `^~`-Modifikator ist —
eine Regex-Location wird von nginx vor einer einfachen Präfix-Location geprüft und gewinnt damit,
ohne die geteilte Datei zu ändern. Ein einzelnes `proxy_set_header Host $http_host;` auf
Server-Ebene hätte **nicht** gereicht: Sobald eine Location eigene `proxy_set_header`-Direktiven
setzt (hier über das eingebundene `proxy.conf`), werden Werte der übergeordneten Ebene komplett
ignoriert statt nur ergänzt — eine nginx-Eigenheit.

**Nicht bereinigt, aber harmlos:** Der bestehende Custom-Config-Inhalt für diesen Proxy-Host
(`/loleaflet`, `/lool/*`, `/hosting/discovery`) stammt aus einer Collabora/LibreOffice-Online-Vorlage,
nicht aus einer ONLYOFFICE-Vorlage — wird aber von keinem tatsächlichen ONLYOFFICE-Request
getroffen, daher wirkungslos statt schädlich.

---

## 5. Zertifikatsvertrauen ist pro Gerät/Browser, nicht pro Server

Nach allen Server-seitigen Fixes schlug das Laden von `api.js` weiterhin auf einzelnen
Geräten/Browsern fehl (`ERR_CERT_AUTHORITY_INVALID`) — nicht weil der Server falsch antwortete,
sondern weil das jeweilige Gerät das selbstsignierte Zertifikat für genau diese Origin
(`onlyoffice.herrmann.local:18443`) noch nie akzeptiert hatte. Ein Hintergrund-Skript-Ladevorgang
(`<script src="...">`) kann anders als eine normale Seitennavigation keine
Klickdurch-Zertifikatswarnung anzeigen — er schlägt bei unbekanntem Zertifikat einfach lautlos fehl.

**Workaround pro Gerät:** einmalig direkt `https://onlyoffice.herrmann.local:18443/healthcheck`
aufrufen (nicht `/`, das leitet wegen eines separaten, hier irrelevanten OnlyOffice-eigenen
Redirect-Bugs ohne Port auf `/welcome/` um) und die Zertifikatswarnung dort akzeptieren. Muss pro
Browser/Gerät einmalig wiederholt werden — der Grund, warum "funktioniert bei mir" und "funktioniert
nicht bei dir" während der Diagnose gleichzeitig beide stimmten.

---

## Endzustand

| Dienst | URL | DNS | Zertifikat |
|---|---|---|---|
| ONLYOFFICE | `https://onlyoffice.herrmann.local:18443` | ✅ (Herrmann.local-Zone) | ✅ selbstsigniert, bis 2036 |
| Odoo | `https://odoo.herrmann.local:18443` | ✅ (Herrmann.local-Zone) | ✅ selbstsigniert, bis 2036 |

Odoo-Parameter: `onlyoffice_connector.doc_server_public_url` und `web.base.url` beide auf
`*.herrmann.local` umgestellt. `onlyoffice_connector.doc_server_odoo_url`
(`http://192.100.0.119:8069/`, Server-zu-Server-Rückverbindung für Dateiinhalt) unverändert, war nie
betroffen.
