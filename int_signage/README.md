# int_signage

Anzeigetafeln aus Odoo: Informationen und Datensätze auf großen Bildschirmen zeigen, die jeweils an einem Minipc hängen. **Status: Grundgerüst, noch keine Funktion.**

## Ausgangslage

- zwei große Informationsbildschirme, jeder von einem Minipc gespeist
- ein Unraid-Server, auf dem Odoo als Container läuft
- alles im selben Netzwerk

## Prinzip

Odoo schickt nichts an die Bildschirme. Jeder Minipc startet beim Einschalten einen Browser im Kiosk-Modus (Vollbild, ohne Menü) und öffnet eine feste Adresse des Moduls:

```
Odoo (Container auf Unraid)  <-  Kiosk-Browser (Minipc 1 / Minipc 2)  ->  HDMI  ->  Bildschirm
```

Die Seite zeigt die Folien der Anzeige nacheinander und lädt sich selbst neu, sodass Änderungen in Odoo nach kurzer Zeit auf dem Bildschirm erscheinen.

## Geplanter Umfang

| Baustein | Inhalt |
|---|---|
| Anzeige (`int_signage_screen`) | ein Bildschirm, z. B. „Bildschirm Foyer“; trägt einen geheimen Schlüssel, der Teil der Adresse ist, sodass der Minipc kein Passwort braucht |
| Folie (`int_signage_slide`) | gehört zu einer Anzeige; Reihenfolge, Anzeigedauer, Gültig von/bis |
| Adresse | `/signage/<Schlüssel>`, Vollbildseite ohne Odoo-Oberfläche, Größen relativ zum Bildschirm (16:9) |

Folienarten:

- **Freie Folie** (Text, Bild, Ankündigung): Feld mit dem normalen Odoo-Editor (Überschriften, Farben, Bilder, Tabellen), dazu Hintergrundfarbe oder -bild. Aufwendigere Gestaltung später über Seiten des Website-Editors, die mit der Folie verknüpft werden.
- **Datenfolie** (Termine, Aufgaben, Lagerstand, Lieder …): feste, gut lesbare Vorlage, die sich aus Odoo-Daten füllt. Welche Daten, ist noch offen.

## Entscheidungen

- Ein Modul `int_signage` für Bildschirme und Folien (ein Modul zusammenhalten, wie `int_filemanager`). Datenfolien kommen später ins selbe Modul, außer sie brauchen viele fremde Module (dann Zusatzmodul).
- Dateiname = voller Modellname, Firmenpräfix `int_`.
- Odoo-Bordmittel zuerst: Website-Editor und seine Bausteine, Odoo-Bus für Live-Aktualisierung, HTML-Feld mit Editor. Die IoT Box scheidet aus (Enterprise, auf Kassendisplays zugeschnitten).

## Offen

- Datenquellen der Datenfolien
- Betriebssystem der Minipcs (Windows oder Linux): nur für den Kiosk-Autostart relevant, nicht für das Modul
- Live-Aktualisierung über den Odoo-Bus oder einfaches Nachfragen alle 30 bis 60 Sekunden
- Verhältnis zur geplanten kirchlichen Liedanzeige (Spezifikation im Repo vorher lesen)

## Kiosk-Einrichtung am Minipc (später)

Browser beim Start im Kiosk-Modus mit der Adresse der Anzeige öffnen (z. B. `chrome --kiosk <Adresse>`), Bildschirmschoner und Energiesparen ausschalten, für den Unraid-Server einen festen Hostnamen oder eine feste IP verwenden.
