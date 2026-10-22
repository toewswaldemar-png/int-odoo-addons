# int_presenter

Einen Beamer aus Odoo bespielen, ähnlich wie SongBeamer oder OpenSong: Lieder, Ablaufplan und Folien pflegen, am Bedienplatz die Folie wählen, auf dem Beamer erscheint sie sofort. **Status: Grundgerüst, noch keine Funktion.**

## Prinzip

```
Liederdatenbank  ->  Ablaufplan (Gottesdienst)  ->  Bedienseite  ->  Beamer-Seite
(Strophen, Refrain)  (Lied, Bibelvers, Text, Bild)  (Tablet/PC)       (Vollbild, live)
```

Der Beamer hängt an einem Rechner mit Kiosk-Browser im Vollbild. Er öffnet die Beamer-Seite des Moduls. Wer bedient, wählt auf der Bedienseite die Folie; die Beamer-Seite folgt über `bus.bus` ohne Neuladen.

## Geplanter Umfang

| Baustein | Inhalt |
|---|---|
| Lied | Titel, Nummer, Sprache, Tags, Text in Strophen und Refrain (je Folie), Rechtehinweis (CCLI, GEMA) |
| Ablauf | ein Gottesdienst oder Termin mit Einträgen in Reihenfolge: Lied, Bibelvers, Text, Bild, Video, Pause; sortierbar, kopierbar („wie letzte Woche“) |
| Design | Hintergrundbild oder -farbe, Schriftart, Größe, Rand; je Ablauf oder Eintrag wählbar |
| Bedienseite | Ablauf mit Folienvorschau, Knöpfe „Weiter“, „Zurück“, „Schwarz“, „Logo“; auch am Tablet |
| Beamer-Seite | Vollbild ohne Odoo-Oberfläche, zeigt nur die aktuelle Folie, mehrere Beamer mit unterschiedlichem Inhalt möglich |
| Rechte | Lieder pflegen, bedienen, nur ansehen als getrennte Gruppen |

## Abgrenzung

- `int_liedanzeige`: zeigt nur Lied- und Chornummern auf Anzeigen, ohne Liedtexte. Es hat bereits Zustand, Live-Aktualisierung über den Bus, Steuerseiten und Kiosk-Benutzer. Ob Teile davon hier wiederverwendet werden oder ob `int_presenter` davon abhängt, ist offen.
- `int_signage`: Bildschirme, die ohne Bediener von selbst durchlaufen. `int_presenter` ist dagegen für Betrieb mit Bediener gedacht.

## Grenzen von Odoo

- PowerPoint-Dateien lassen sich nicht direkt abspielen, nur nach Umwandlung in Bilder.
- Die Fensterverwaltung auf dem zweiten Bildschirm übernimmt der Kiosk-Browser oder der Go-Kiosk der Liedanzeige, nicht Odoo.
- Keine zeitkritische Videomischung.

## Entscheidungen

- Eigenes Modul `int_presenter` (statt Ausbau von `int_liedanzeige`), Firmenpräfix `int_`, Dateiname gleich vollem Modellnamen.
- Odoo-Bordmittel zuerst: Bus für die Live-Aktualisierung, HTML- und Bildfelder, Gruppen und Aktivitäten.

## Offen

- Ersatz der Nummern-Anzeige oder Betrieb daneben (Nummern im Foyer, Folien im Saal)
- Liedtexte auf dem Beamer: Rechtefrage (CCLI, GEMA), bestimmt die Form des Liedmodells
- Beziehung zu `int_liedanzeige` (eigenes Liedmodell oder gemeinsames) und zu `int_signage` (gemeinsame Beamer-Seite)
- Betriebssystem und Kiosk des Beamer-Rechners
- Import vorhandener Lieder (SongBeamer-, OpenSong-Dateien)
