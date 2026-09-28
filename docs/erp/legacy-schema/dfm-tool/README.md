# DFM-Decoder für Herrmann.exe

Reverse-Engineering-Werkzeug: liest die kompilierten Delphi-Formulare
(binäre DFM-Ressourcen, Format `TPF0`) direkt aus `Herrmann.exe` und
wandelt sie in lesbaren Text-DFM um — mit exakter Steuerelement-Hierarchie,
Koordinaten, Eigenschaften und `DataField`-Bindungen. Deutlich zuverlässiger
als das bisherige Verfahren (`strings` auf die ganze EXE, Zuordnung über
Zeilennähe geraten).

## Funktionsweise

Delphi kompiliert jedes Formular als `RCDATA`-Ressource, benannt nach der
Klasse (z. B. `TFRMARTIKELINFO2`). `list_rcdata.py`/`extract_rcdata.py`
nutzen `pefile`, um diese Ressourcen aus der EXE zu extrahieren.
`dfm_decode.py` implementiert das binäre Delphi-"Filer"-Streamformat
(dieselbe Logik wie `TReader` in Delphis `Classes.pas`) und wandelt es in
lesbaren Pseudo-Text-DFM um.

Wichtige, beim Debuggen gefundene Format-Details:
- Komponenten können ein optionales **Flags-Byte** (`0xF0`–`0xFF`) vor dem
  Klassennamen haben (z. B. `0xF1` = `ffInherited`). Ohne dessen Behandlung
  scheitert das Parsen an über einem Viertel aller Formulare.
- `TCollection`-Einträge (z. B. `TDBGrid.Columns`) nutzen ein eigenes
  Flag-Byte-Protokoll (`0`=Ende, `2`=expliziter Index folgt, sonst normales
  Element) statt eines generischen Werte-Tags.
- Strings sind `cp1252`-kodiert (deutsche Umlaute).

## Nutzung

```bash
python list_rcdata.py          # Inventar aller RCDATA-Ressourcen (Formularliste)
python extract_rcdata.py       # extrahiert jede Ressource als eigene .bin-Datei
python batch_decode.py         # dekodiert alle .bin-Dateien zu lesbarem Text-DFM
python dfm_decode.py <datei.bin>   # einzelne Datei, Ausgabe auf stdout
```

Pfade zur EXE sind aktuell hart in `list_rcdata.py`/`extract_rcdata.py`
eingetragen (`Herrmann_Work/Herrmann.exe`) – bei neuerer EXE-Version dort
anpassen.

## Validierung

Gegen mehrere bereits manuell (per `strings`) reverse-engineerte Formulare
geprüft (u. a. `TFRMARTIKELINFO2`) – Ergebnisse stimmen überein, decken aber
zusätzlich Details auf, die die manuelle Methode nicht zuverlässig liefern
konnte (z. B. echte `FieldName`-Werte in Grid-Spalten statt geratener
Tabellenherkunft). Alle 471 Formulare der EXE (Stand 06.09.2026) wurden ohne
Parserfehler und ohne unverbrauchte Restbytes dekodiert.

**Grenze:** SQL-Text von Queries, die zur Laufzeit im Pascal-Code
zusammengebaut werden (nicht als Design-Time-Property gesetzt), taucht
NICHT in den DFM-Ressourcen auf – dafür bleibt `strings` auf die EXE
nötig.

Die dekodierten Formulare liegen unter [`../forms-dfm/`](../../../legacy-schema/forms-dfm)
(471 Dateien, ca. 13 MB), benannt nach der Delphi-Klasse (z. B.
`TFRMARTIKELINFO2.dfm.txt`). Formularliste mit Größen:
[`forms_inventory.txt`](forms_inventory.txt).

## Zweite EXE: ProjektzeitenHM.exe

`extract_projektzeitenhm.py` wendet dasselbe Verfahren auf die vom
Hauptprogramm getrennte Stempel-Anwendung `ProjektzeitenHM.exe` an
(59 Formulare, keine Parserfehler). Ergebnis unter
[`../forms-dfm-projektzeitenhm/`](../../../legacy-schema/forms-dfm-projektzeitenhm). Diese
EXE löst SQL nicht serverseitig auf, sondern verdrahtet es als Klartext im
Client-Code — dadurch liegt hier zusätzliche Geschäftslogik offen, die aus
`Herrmann.exe` allein (DFM oder `strings`) nicht extrahierbar war. Details
und Befunde:
[`aktuelle-exe-validierung.md`](../aktuelle-exe-validierung.md#projektzeitenhmexe-eigenständige-stempel-anwendung-schreibt-prozesszeiten-2026-09-09).
