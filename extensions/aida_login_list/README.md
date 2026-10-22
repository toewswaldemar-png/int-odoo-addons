# AIDA login list (Edge-Erweiterung)

Auf der Anmeldeseite von AIDA-Web erscheint im Feld „Benutzername“ eine Auswahlliste mit den Namen; getippt wird nur das Passwort. Die Namen kommen aus Odoo (`int_keepass`, Endpunkt `/int_keepass/aida_users`). Die Erweiterung kennt und speichert kein AIDA-Passwort und ändert nichts am Server.

## Wie es arbeitet

- Das Anmeldeformular von AIDA-Web ist ein AngularJS-Formular, das erst nach dem Laden der Seite entsteht. Das Skript wartet auf das Feld (`ng-model="$root.login.UserName"`) und setzt ein `<datalist>` daran.
- Eine Auswahl aus der Liste löst ein `input`-Ereignis aus, das AngularJS in sein Modell übernimmt (mit dem AngularJS von AIDA-Web geprüft, siehe Tests). Danach springt der Cursor ins Passwortfeld. Tippt man den Namen von Hand, bleibt der Cursor im Feld.
- Ist Odoo nicht erreichbar, nimmt die Erweiterung die Namen vom letzten Mal (im Speicher des Browsers). Ohne Einstellungen tut sie nichts.

## Einrichten zum Testen

1. In Odoo: **KeePass → Open** (Master-Passwort), dann **KeePass → Take over AIDA names**. Das übernimmt die Namen der Einträge, deren Adresse `ewas.central` enthält. Unter **KeePass → AIDA names** lässt sich die Liste von Hand pflegen.
2. In Edge: `edge://extensions` → Entwicklermodus einschalten → **Entpackte Erweiterung laden** → diesen Ordner wählen.
3. Die Optionen der Erweiterung öffnen: Adresse von Odoo (zum Beispiel `http://odoo.example:8069`, die Adresse deines Odoo) und das Token (Systemparameter `int_keepass.aida_token` in Odoo) eintragen, **Speichern und prüfen**.
4. Die AIDA-Anmeldeseite neu laden.

## Verteilen an mehrere PCs (nicht getestet)

Per Gruppenrichtlinie (Edge): `ExtensionInstallForcelist` mit der Erweiterung, dazu die Werte `odooUrl` und `token` als Richtlinie für die Erweiterung (`schema.json` beschreibt sie; sie gehen den Einstellungen der Optionsseite vor). Die Erweiterung muss dafür als `.crx` mit Update-Adresse bereitgestellt werden.

## Grenzen

- Das Skript läuft nur auf Seiten, deren Adresse `/de.aidaorga.aida.ewas.central/` enthält (`include_globs` in `manifest.json`), auf jedem Server von AIDA-Web. Die Erweiterung hat dafür das Recht auf alle http- und https-Seiten (`matches`). Für die Verteilung empfiehlt es sich, `matches` auf den Rechner von AIDA-Web einzuschränken, zum Beispiel `http://aida-server/*`.
- Das Token und die Namen laufen über HTTP im Klartext, solange Odoo nicht über HTTPS erreichbar ist. Die Namen selbst sind keine Geheimnisse.
- Nicht geprüft in einem echten Edge: das Verhalten zusammen mit der Bildschirmtastatur von AIDA (`ng-virtual-keyboard`) und mit der Ausfüllbox des Edge-Passwortmanagers. Das Skript setzt `autocomplete="off"` am Feld, damit die Box die Liste nicht verdeckt.
- Baut AIDA das Formular um, muss der Selektor in `content.js` (`USERNAME_SELECTOR`) angepasst werden.

## Tests

```bash
cd extensions/aida_login_list
npm install
npm test
```

Die Tests laufen in jsdom ohne Browser. Der Test mit AngularJS braucht dessen Datei von AIDA-Web: `AIDA_ANGULAR_URL=http://<aida-server>/<version>/de.aidaorga.aida.ewas.central/js/lib/angular.min.js npm test` liest sie einmal und legt sie im Temp-Ordner ab (danach geht es ohne die Variable). Ohne Datei wird dieser Test übersprungen.
