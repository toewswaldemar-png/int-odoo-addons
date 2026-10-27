# int_filemanager: Betrieb

Was der Betreiber des Servers wissen muss und der Code nicht lösen kann.

## Platz für Uploads

Eine Upload-Anfrage (`/int_filemanager/upload`, bis „Größter Upload“ in den Einstellungen des Filemanagers, `int_filemanager.upload_max_gb`, Standard 20 GB) liest Werkzeug **vor** dem Controller in eine temporäre Datei (`TMPDIR`, sonst `/tmp`). Danach kopiert die Ablage sie Block für Block nach `<Filestore>/int_filemanager/.upload` und legt sie als Blob ab. Während einer Übertragung liegt die Datei also zweimal auf der Platte, und die Temp-Datei fällt unter den Platz von `TMPDIR`, nicht des Filestores.

- `TMPDIR` des Odoo-Prozesses braucht Platz für die größte Datei, die gleichzeitig kommen darf, mal die Zahl der gleichzeitigen Uploads.
- Im Container: `TMPDIR` auf ein Volume mit diesem Platz legen (nicht in die Schicht des Containers, nicht auf ein `tmpfs` im Arbeitsspeicher).
- Geht der Platz aus, antwortet der Upload mit 507 („There is no space left to store the file.“), und die Ablage räumt ihre Teilarbeit ab.
- Die Anfrage wartet, bis der Client fertig ist; ein langsamer Client hält einen Thread. Die Obergrenze gilt nur für Nutzer der Gruppe „Filemanager User“, alle anderen behalten die 128 MiB des Cores.

Eine Änderung am Eingang (ein eigener `stream_factory` von Werkzeug, der direkt nach `.upload` schreibt) hat der Core nicht vorgesehen; sie hieße, die Anfrage von Odoo zu ersetzen. Darum bleibt es bei der Kopie.

## Programme

Die Vorschau der Office-Dateien braucht auf dem Server `soffice` (LibreOffice) sowie `nice` und `timeout` (GNU coreutils); fehlt eines, macht der Job nichts und sagt es im Log und in den Einstellungen. Darum läuft sie nur unter Linux. Die Bilder der PDFs brauchen das Python-Paket `pypdfium2`; fehlt es, bleiben sie aus, und die Einstellungen zeigen es in der Statuszeile „Bilder von PDFs“.

Nichts davon steht in `external_dependencies`: Odoo bricht damit die Installation ab, und das Modul läuft auch ohne diese Programme (nur die jeweilige Funktion fehlt). Die Beschreibung in der Apps-Liste (`README.rst` des Moduls) nennt sie.

## Deinstallieren

Mit dem Modul gehen die Dokumente, und `uninstall_hook` entfernt `<Filestore>/int_filemanager` (die Dateien der Dokumente, ihre Vorschauen, die Warteschlange des Reinigers). Der Filestore der Anhänge bleibt unberührt. Wer die Dateien behalten will, sichert den Ordner vorher.
