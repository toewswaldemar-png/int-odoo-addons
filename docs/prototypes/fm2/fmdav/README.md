# fmdav – Prototyp WebDAV-Dienst neben Odoo (int_filemanager 2, Konzept 11 A)

Ergebnisse: `docs/int_filemanager_v2_konzept_2026-09-26.md`, Abschnitt 19.4. Odoo-Seite: `../fm_proto/dav.py`.

- `dav_service.py` – WsgiDAV-Provider; reicht jede Operation mit dem API-Schlüssel des Nutzers (`auth='bearer'`) an
  Odoo weiter, schreibt selbst nichts auf die Platte.
- `Dockerfile` – `python:3.12-slim` + wsgidav 4.3.5, cheroot 11.1.2, requests 2.32.5.
- `tests/windows_webclient.ps1` – Tests über den Windows-WebClient (Netzlaufwerk).
- `tests/lo_edit.py` – LibreOffice per UNO: Dokument vom Netzlaufwerk öffnen, zweimal speichern.

Tower (Testinstanz): Image `fmdav:proto`, Container `fmv2_dav` (Port 8082 → 8080, Netz `fmtest-net`), Konfiguration
`/mnt/user/appdata/fmtest/fmdav/env` (nur root lesbar: `FM_DAV_ROOT_ID`, `FM_ODOO_URL`, `FM_DAV_ANON_IPS`,
`FM_DAV_ANON_KEY` = API-Schlüssel des Testnutzers `davuser` der Test-DB `fmv2`).

```bash
docker start fmtest_pg fmv2_odoo fmv2_nginx fmv2_dav
```

litmus (Konformität), Anmeldung mit Login + API-Schlüssel:

```bash
docker run --rm --network fmtest-net debian:bookworm-slim sh -c 'apt-get update -qq && apt-get install -y -qq litmus >/dev/null; litmus http://fmv2_dav:8080/litmus/ davuser <API-Schlüssel>'
```
