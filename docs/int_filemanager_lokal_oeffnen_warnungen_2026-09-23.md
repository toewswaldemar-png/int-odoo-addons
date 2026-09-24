# int_filemanager: "Lokal öffnen" möglichst ohne Warnungen/Zertifikatsfehler

Stand 2026-09-23. Untersuchung des "Lokal öffnen"-Features (`onOpenLocal()`, WebDAV-Protokoll-
Handoff an Word/Excel/PowerPoint Desktop via `ms-word:`/`ms-excel:`/`ms-powerpoint:ofe|u|<url>`).
**Wichtige Einordnung vorweg:** anders als bei den bisherigen Untersuchungen dieser Reihe liegt der
größte Teil der möglichen Warnungen **außerhalb von Odoo-/`int_filemanager`-Code** — es sind
Windows-/Office-/Browser-eigene Sicherheitsmechanismen, die auch bei jedem anderen
WebDAV-Server (Nextcloud, ownCloud, SharePoint) exakt genauso auftreten. Reine Analyse, nichts
umgesetzt. Drei getrennte Ebenen, jede mit eigener Ursache und eigenem Lösungsweg.

---

## Der bestehende Ablauf (am Code geprüft)

```js
// filemanager_controller_mixin.js
const res = await rpc("/int_filemanager/webdav_token", { path: record.data.path });
window.location.href = `${protocol}:ofe|u|${res.url}`;
```

```python
# webdav.py, webdav_token()
url = "%sint_filemanager/webdav/%s/%s" % (request.httprequest.host_url, token, filename)
```

Wichtig: `request.httprequest.host_url` übernimmt **exakt das Schema (http/https), über das die
Odoo-Seite selbst gerade aufgerufen wurde** — läuft der interne Zugriff auf `int_filemanager` heute
über schlichtes `http://`, bekommt Word/Excel ebenfalls eine `http://`-WebDAV-URL. Die
WebDAV-Routen selbst sind bewusst `auth="public"` **ohne** HTTP-Basic-Auth-Challenge — die
Sicherheit läuft komplett über den Bearer-artigen Token in der URL, nicht über einen
Anmelde-Dialog. Das ist relevant für Ebene 2 unten.

---

## Ebene 1: Browser-Warnung beim Auslösen des `ms-word:`-Protokolls

**Ursache, nichts mit Odoo/WebDAV zu tun:** jeder moderne Browser fragt bei **jedem** Klick, der
ein eigenes URL-Protokoll (nicht `http(s)://`) öffnen will, standardmäßig nach — "Diese Website
möchte Microsoft Word öffnen. Zulassen?" — ein generischer Browser-Schutzmechanismus gegen
Webseiten, die unbemerkt Programme starten, unabhängig vom Ziel-Protokoll.

**Lösung liegt komplett auf Client-/Browser-Seite, nicht im Code:**
- Nutzer kann beim ersten Mal "Immer erlauben für diese Seite" anhaken — danach verschwindet die
  Nachfrage für diesen Browser/dieses Profil dauerhaft.
- Für eine unternehmensweite, dauerhafte Lösung ohne Einzelklick pro Person: Chrome-/Edge-Policy
  (`AutoLaunchProtocolsFromOrigins`, per Gruppenrichtlinie/Registry verteilbar) erlaubt,
  `ms-word`/`ms-excel`/`ms-powerpoint` für die eigene Odoo-Domain fest freizugeben, ganz ohne
  Nutzerinteraktion.

---

## Ebene 2: Office-eigene "Diese Datei könnte Viren enthalten"-Warnung bei `ofe`-Links

**Ursache:** ein seit einem Office-Update bekanntes, community-dokumentiertes Verhalten (siehe
Quelle unten) — Office zeigt bei `ms-word:`-Links pauschal eine Sicherheitswarnung, unabhängig vom
tatsächlichen Ziel-Server.

**Lösung, ebenfalls Client-Konfiguration, nicht Server-Code:** Registry-Pfad
`HKEY_CURRENT_USER\Software\Policies\Microsoft\Office\<Version>\Common\Security\Trusted
Protocols\All Applications` — dort lässt sich das `ofe`-Protokoll als vertrauenswürdig
hinterlegen, unternehmensweit über Gruppenrichtlinie verteilbar (Office-ADMX-Vorlagen enthalten
diese Einstellung als GPO-Option, kein manuelles Registry-Gefummel pro Rechner nötig).

---

## Ebene 3: die eigentliche WebDAV-Verbindung — hier zählt die Server-Konfiguration wirklich

**Kein Basic-Auth-Problem, entgegen einer verbreiteten WebDAV-Fehlerquelle:** viele bekannte
"WebDAV+Windows"-Probleme drehen sich um `BasicAuthLevel` (Windows' `WebClient`-Dienst blockiert
per Default Basic-Auth-Anmeldung über reines HTTP, nur über HTTPS erlaubt). **Betrifft
`int_filemanager` nicht** — die eigenen WebDAV-Routen fragen gar keine HTTP-Basic-Auth ab
(`auth="public"`, bestätigt am Code), die Absicherung läuft ausschließlich über den Token in der
URL. Dieser oft zitierte Stolperstein entfällt hier von vornherein.

**Der tatsächlich relevante Punkt: Zertifikatsvertrauen, falls HTTPS verwendet wird.** Läuft der
Zugriff über `https://` mit einem selbstsignierten oder einer internen, nicht öffentlich
vertrauten CA ausgestellten Zertifikat, zeigt Office beim WebDAV-Zugriff einen Zertifikatsfehler —
ein sehr häufig gemeldetes Problem bei genau dieser Konstellation (Nextcloud-Forum-Belege siehe
Quellen, exakt derselbe zugrundeliegende Windows-/Office-Mechanismus wie hier).

**Zusätzlich ein häufig übersehener Stolperstein bei diesem Fehlerbild:** fehlende TLS-1.2-
Unterstützung auf dem Server/Reverse-Proxy führt zu einer unklaren Meldung
("Interner Fehler beim Laden der SSL-Bibliotheken"), die wie ein Zertifikatsproblem aussieht,
aber ein reines TLS-Versions-Problem ist — kurzer Check wert, falls Zertifikate selbst korrekt
sind und der Fehler trotzdem auftritt.

**Zwei konkrete, sich ausschließende Lösungswege — echte Entscheidung, keine Kleinigkeit:**
1. **Reiner HTTP-Zugriff beibehalten** (aktuell vermutlich der Fall bei rein internem
   LAN-Zugriff) — kein Zertifikatsproblem möglich, da gar kein TLS im Spiel. Ob moderne
   Office-Versionen WebDAV über reines HTTP überhaupt noch anstandslos akzeptieren, ist in der
   Community uneinheitlich dokumentiert (manche Berichte sprechen von zunehmend strengerem
   Verhalten neuerer Office-Builds) — **vor einer Entscheidung live mit der tatsächlich im
   Unternehmen eingesetzten Office-Version testen, nicht annehmen.**
2. **HTTPS mit einem von allen Firmen-PCs als vertrauenswürdig erkannten Zertifikat** — entweder
   ein öffentlich ausgestelltes Zertifikat (Let's Encrypt o.ä., falls der Server einen echten,
   von außen erreichbaren Hostnamen hat) oder das interne CA-Root-Zertifikat per Gruppenrichtlinie
   auf alle Windows-Rechner verteilen, damit ein selbstsigniertes/internes Zertifikat als
   vertrauenswürdig gilt. **Kein Server-Code-Problem, reine Infrastrukturentscheidung.**

---

## Zusammenfassung: was tatsächlich im eigenen Code liegt — sehr wenig

Von den drei Ebenen ist **keine einzige** durch eine Änderung an `int_filemanager`s eigenem Code
lösbar — alle drei sind Windows-/Office-/Browser-seitige Sicherheitsmechanismen, die bei jedem
WebDAV-Anbieter gleichermaßen auftreten. Der einzige Punkt, an dem der eigene Code überhaupt
mitspielt, ist indirekt: **welches Protokoll (`http`/`https`) der Odoo-Zugriff insgesamt nutzt**
(`request.httprequest.host_url` übernimmt das 1:1) — das ist aber eine Odoo-/Deployment-
Konfigurationsfrage (Reverse-Proxy/TLS-Setup), keine `int_filemanager`-Codeänderung.

**Empfohlene Reihenfolge zum "reibungslos machen":**
1. Klären, mit welchem Protokoll (`http`/`https`) intern tatsächlich zugegriffen wird — Grundlage
   für alles Weitere.
2. Live mit der tatsächlich eingesetzten Office-Version testen, ob Ebene 3 überhaupt ein
   Problem verursacht, bevor Infrastruktur umgebaut wird — nicht auf Verdacht ein
   Zertifikats-Rollout starten.
3. Falls Ebene 1/2 stört: die beiden GPO-Einstellungen (Browser-Protokoll-Auto-Erlaubnis,
   Office-Trusted-Protocols) unternehmensweit verteilen — einmaliger IT-Aufwand, danach für alle
   Kollegen dauerhaft gelöst.

**Quellen:** [Making Microsoft Office to Work with WebDAV Server](https://www.webdavsystem.com/server/documentation/ms_office_read_only/), [Certificate error (SSL) when opening files with Office products via WebDav (Nextcloud)](https://help.nextcloud.com/t/certificate-error-ssl-when-opening-files-with-office-products-via-webdav/200300), [BasicAuthLevel — Using Basic Authentication with Windows WebDAV Client](https://www.webdavsystem.com/server/prev/v2/documentation/authentication/basic_auth_vista/), [Security warning when opening document with URI Schema ms-word (Microsoft Q&A)](https://learn.microsoft.com/en-us/answers/questions/1186215/security-warning-when-opening-document-with-uri-sc), [Office - WebDav Certificate error / SSL libraries](https://learn.microsoft.com/en-sg/answers/questions/1852704/office-webdav-certificate-error-internal-error-in)
