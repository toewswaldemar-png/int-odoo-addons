# int_keepass: Passwort-Tresor als virtuelle Odoo-Datensätze

Zeigt die Gruppen und Einträge (Titel, Benutzername, Adresse) einer KeePass-Datei (`.kdbx`) oder eines Vaultwarden-Kontos als gewöhnliche Datensätze in Odoo: Liste, Formular, Gruppenbaum im Suchpanel. Nichts davon liegt in der Datenbank, und Passwörter oder Notizen werden nie gelesen. Nur lesend.

Das Modul hängt nur von `base` und `web` ab (dazu die Python-Pakete `pykeepass` und `argon2-cffi`, beide in `external_dependencies`; Odoo installiert das Modul ohne sie nicht), nicht von `int_filemanager`.

## Aufbau

- **Virtuelle Modelle** `int.keepass.group` und `int.keepass.entry` nach dem Muster von `account.code.mapping` im Odoo-Kern: `_auto = False`, `_table_query = "0"`, ein `_search`-Override, der die Ids liefert (`_as_query()`), die Felder werden berechnet. Die Ids sind ganze Zahlen aus der UUID des Eintrags (`uuid % (2**31-1) + 1`); eine Kollision bricht mit einer Meldung ab.
- **Lesequellen** hinter `int.keepass.source`: `kdbx.py` (pykeepass, ohne Odoo-Importe) und `vaultwarden.py` (eigener Client für das Bitwarden-Protokoll: Schlüssel aus dem Master-Passwort per PBKDF2 oder Argon2id, HKDF, Anmeldung, `/api/sync`, Entschlüsselung der EncStrings vom Typ 2). Beide liefern dieselbe Form: `{"groups": [...], "entries": [...]}`.
- **Das Suchpanel** gruppiert nicht nach dem Gruppenfeld (es hat keine Spalte): `expand="1"` ohne Zähler.

## Passwort-Fluss

- Das Master-Passwort (bei Vaultwarden auch die E-Mail-Adresse) bleibt im Speicher der Seite: nicht im Storage, nicht in der Adresse, nicht im Kontext. Ein Neuladen vergisst es.
- Jeder Aufruf an `int.keepass.*` trägt es als Header (`X-Int-Keepass-Password`, `X-Int-Keepass-Email`, Base64 von UTF-8). Das macht ein Umbau von `rpc._rpc` in `keepass_header.js`; ohne Passwort wird der Aufruf zurückgehalten und der Entsperr-Bildschirm öffnet sich.
- Der Server entschlüsselt nur im Speicher der Anfrage. Ein Worker hält die gelesenen Namen und Adressen (nie Passwörter) fest `int_keepass.cache_seconds` Sekunden (Standard 300), geschlüsselt nach Quelle, Dateistand und Zugangsdaten. **Open** und **Refresh** lesen frisch, **Lock** vergisst auch im Browser.

## Menü

KeePass → **Open** (Entsperr-Bildschirm, danach die Liste), **Refresh**, **Lock**. Zugriff haben nur Systemadministratoren.

## Systemparameter

| Schlüssel | Bedeutung |
|---|---|
| `int_keepass.source` | `kdbx` (Standard) oder `vaultwarden`; gilt für alle |
| `int_keepass.kdbx_path` | Pfad der `.kdbx` aus Sicht des Odoo-Servers |
| `int_keepass.vaultwarden_url` | Adresse des Vaultwarden, ohne Pfad |
| `int_keepass.vaultwarden_cert_sha256` | Fingerabdruck eines selbst signierten Zertifikats (setzt es fest, statt die Kette zu prüfen) |
| `int_keepass.cache_seconds` | Haltedauer im Worker, `0` schaltet ab |

## Einspielen

Das Image braucht `pykeepass` (siehe `Dockerfile`). Ordner `int_keepass` nach `extra-addons` kopieren (ohne `__pycache__`), Modul installieren oder `-u int_keepass`, Odoo neu starten (JS und XML).

## Prüfen

Skripte in `tools/int_keepass/` (Wegwerf-Umgebung auf dem Testserver, der Live-Betrieb wird nicht berührt): Tests gegen einen Wegwerf-Vaultwarden (`odoo_vaultwarden_check.sh`), dazu gegen eine echte Datei (`odoo_real_check.sh`), Lesen einer echten Quelle ohne Odoo (`read_check.py`, `vaultwarden_check.py`), Gegenprobe mit der Bitwarden-CLI (`bw_crosscheck.sh`) und die Browser-Hilfe (`header.test.mjs`, `node --test`).

Der Odoo-Core blockiert Netzwerkzugriffe in Tests mit dem Tag `standard`; der Test gegen einen echten Vaultwarden trägt deshalb `external` und wird mit `--test-tags /int_keepass,external/int_keepass` gewählt.

## Grenzen und offen

- Nur lesen; Anlegen, Ändern und Löschen sind nicht gebaut.
- Das Master-Passwort läuft über die Leitung zum Odoo-Server: ohne HTTPS im Klartext. Eine Pflicht zu HTTPS und eine Bremse gegen Raten (Vaultwarden bremst selbst pro IP-Adresse, alle Odoo-Nutzer teilen eine) fehlen noch.
- Vaultwarden: Organisationen und Sammlungen (ihre Einträge werden übersprungen), Zwei-Faktor-Anmeldung und das neue Schlüsselformat (Typ 7) fehlen. Neuere Bitwarden-Clients rufen `/identity/accounts/prelogin/password`, das ältere Server nicht kennen; der Client hier nutzt den bisherigen Pfad.
- Die Oberfläche wurde mit Tests und von Hand geprüft, nicht mit einem automatischen Browser-Test (im Test-Image gibt es keinen Chrome).
