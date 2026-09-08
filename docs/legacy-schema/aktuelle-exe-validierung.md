# Validierung gegen die aktuelle Herrmann.exe (Stand 2026-09-06)

Belege für die "Validiert 2026-09-08"-Vermerke in
[`../erp-odoo-modulvergleich.md`](../erp-odoo-modulvergleich.md). Extrahiert per
`strings -n 4` (ASCII) und `strings -n 4 -e l` (UTF-16LE) auf
`Herrmann_Work/Herrmann.exe` (06.09.2026) – kein Quellcode, nur eingebettete
Strings/SQL-Fragmente aus dem kompilierten Binary.

## Adressen-Suchen-Dialog: "Sortierung" ist eine Suchfeld-Auswahl, kein Sortiermenü (2026-09-09)

DFM-Ausschnitt zeigt die `TGroupBox gbxSort` ("Sortierung") mit acht darin
deklarierten `TRadioButton`-Kindelementen, eins pro Suchfeld:

```
TGroupBox  gbxSort       Caption "Sortierung"
TRadioButton rbtName1    Checked=True   (Vorauswahl)
TRadioButton rbtName2
TRadioButton rbtName3
TRadioButton rbtKurzname
TRadioButton rbtPlz
TRadioButton rbtOrt
TRadioButton rbtDebNr
TRadioButton rbtKredNr
```

Bestätigt: nur ein Suchfeld ist zur Zeit "aktiv" (Radiobutton-Gruppe = exklusiv),
nicht eine UND-Verknüpfung mehrerer gefüllter Felder wie in Odoo.

Weitere Feldbindungen aus demselben DFM-Block:

```
TEdit    edtDebNr                                    (Debit.-Nummer / allg. Nummer -- EIN Feld)
TEdit    edtGruppe      ReadOnly  Color clSilver      (Gruppe -- nicht direkt eintippbar)
TMaskEdit edtGruppeBez  Color clSilver                (Gruppenbezeichnung, auch ReadOnly)
TCheckBox cbxFilter     Caption "Adressen Filtern"  Checked=True  State cbChecked
TDBGrid  dbgTreffer_alt DataSource dsSuchen           (Ergebnisgrid, Namenszusatz "_alt")
```

`btnLastSearch` ("letzte Suche") und die Beschriftung "Alle markieren"
(mehrfach im Programm wiederverwendet, nicht Adressen-spezifisch) ebenfalls
bestätigt.

Zu den beiden kleinen Kästchen direkt neben den Eingabefeldern
"Debit.-Nummer" und "Kredit.-Nummer" (im Screenshot sichtbar) wurde kein
eigenes Steuerelement gefunden – ungeklärt.

## Adress-Info-Dialog: Live-Beispiel Railpool GmbH (2026-09-09)

Screenshot des "Adress Info"-Dialogs (Reiter "Allgemein"), aufgerufen über
den "Ansprechpartner"-Button auf der Reparatur-Belegmaske. Bestätigt bzw.
präzisiert mehrere Felder:

- **Art-Radiogruppe** (Allgemein/Kunde/Lieferant): Live-Beispiel zeigt
  "Kunde" ausgewählt bei `DebNr` = 11722 (gefüllt) und `KredNr` leer –
  passt zur These, dass die Auswahl aus `DebNr`/`KredNr`-Belegung abgeleitet
  wird. Kein direktes Steuerelement dafür in den Strings gefunden.
- **Postfach**: zwei Felder im Formular sichtbar (Postfach-Text + eigene
  PLZ daneben) → bestätigt `POSTFACH` + `POSTFACHPLZ` als getrennte Felder.
- **Fon 2**: eigenes, von Fon/Fon1 unabhängiges Feld im Formular sichtbar
  → bestätigt `FON2` als eigenständige Spalte.
- **Ansprechpartner-Grid, Spalte "Funktion"**: zeigt Werte wie
  "Instandhaltung"/"Ersatzteile" (im Screenshot abgeschnitten). Fund:
  ```sql
  Select distinct Notiz from AdressenAnsprech order by Notiz
  ```
  → die "Funktion"-Spalte ist tatsächlich `ADRESSENANSPRECH.NOTIZ`, als
  Werteliste wiederverwendet. Kein eigenes `FUNKTION`-Feld.

## Adress-Info "Sonstiges"-Tab: zwei Konditionen-Paare (2026-09-09)

```
52572: ZKondiL
52574: VersandL
73115: ZkondiL
73117: VersandL
101902: cdsAdressenversandL
101903: cdsAdressenzkondil
214255: Bedingungen Herrmann (Angebot)
218202: Bedingungen Herrmann
218272: Bedingungen des Lieferanten / Kunden
```

`ZKONDI`/`VERSAND` = Konditionen des Geschäftspartners, `ZKONDIL`/`VERSANDL`
= Herrmanns eigene Konditionen – zwei getrennte Feldpaare, kein einzelnes
Konditionen-Set.

```
52540: Liefertage
73084: gbxLiefertage
101906: cdsAdressenLiefertage
```

`LIEFERTAGE` (`ADRESSEN`, `VARCHAR30`) hinter der 7-Checkbox-Gruppe.

```
52645: Select OID from AdressenLiefer where SOID = :parOID
58445: Select * from AdressenLiefer where SOID = :oid
```

`ADRESSENLIEFER` bestätigt als Backing-Tabelle des Lieferadressen-Grids.

## Adress-Info "Kartei"-Tab: Preishistorie je Artikel/Kunde (2026-09-09)

```
tshKartei     TTabSheet   Caption "Kartei"
dbgBeleg      TDBGrid     DataSource dsKartei
TSQLGetKartei                                  (Prozedurname bestätigt)
```

Analoges, vollständig lesbares Query-Muster an anderer Stelle im Programm
(Beleg+Belegpos-Join mit denselben Spalten wie im Kartei-Grid):

```sql
select B.Belegdatum, B.Adrnr, B.Name1, B.Ort, P.Artnr, P.Stck, P.Text, P.Epreis
from Beleg B, Belegpos P
where B.oid = p.soid and B.Belegart = :parArt and B.Adroid = :parAdr
  and B.Belegdatum between :parVon and :parBis
order by Belegdatum, Artnr
```

## Adressen: vollständige SELECT-Query (Ladeformular)

```sql
Select OID, DebNr, KredNr, Nummer, Name1, Name2, EMail, Fon1, Fax1, Mobil,
Bemerkung, MailAngebot, MailAuftrag, MailLieferschein, MailRechnung, MailBestellung,
EmailBuchhaltung, EMailVT, EmailEK, EmailGL, EmailInfo, RechCopyAll,
BUCHHALTUNGCC, BUCHHALTUNGBCC, VTCC, VTBCC, EKCC, EKBCC, GLCC, GLBCC,
InfoCC, InfoBCC, EmailCC, EmailBCC, RechCopyNorm, RechCopyVT, RechCopyFibu,
RechCopyOpos, SnrDruck, BEWUMG, Sperre, Xemail, Xrech, EmailFibu
from Adressen where OID = :parOID
```

Damit bestätigt: Zentral-/Buchhaltungs-/Vertriebs-/Einkaufs-/GL-/Info-E-Mail
je mit eigenem CC/BCC-Feldpaar, plus separate Versand-Flags pro Belegtyp und
Rechnungskopie-Routing. Keines dieser Felder existiert im 2011er-Schema
(`full_schema.sql`).

## XRechnung / Gelangensbestätigung (Feldnamen, nicht in der 2011-DB)

- `cdsAdressenLeitwegID` → Feld `LeitwegID`
- `cdsAdressenBuyerRef` / `cdsAdressenBuyerReference` → Felder `BuyerRef`, `BuyerReference`
- `Xemail`, `Xrech` (Flags), Aufruf von externem `xrechnung.exe`
- `cdsBelegPosgelangendatum` → Feld `GelangenDatum` auf `Belegpos`
- `GelangAngefordert` (Belegpos), `GelangenKopf`/`GelangenFuss` (Textbausteine)
- `TCreateGelangenExcel`, `TfrmGelangenDlg`, `Help\GelangenHelp.doc`

## Nicht bestätigt

- Kein eigenes Feld für "Art: Allgemein/Kunde/Lieferant (exklusiv)" gefunden –
  weder 2011-DB noch aktuelle EXE-Strings zeigen ein solches Feld auf
  `Adressen`. `DebNr`/`KredNr` sind unabhängige, nicht-exklusive Felder.
  Vermutlich reine UI-Radiobutton-Logik.

## Artikel: Fremdschlüssel-Bestätigung (Gruppe, Hauptlieferant)

```sql
-- Gruppe ist FK gegen Artikelgruppen.GID, nicht Freitext:
select A.Artnr, ..., G.Bezeichnung as Artgruppe, ...
from ARTIKELGRPPREISE R, Artikel A
left join Artikelgruppen G on G.GID = coalesce(A.Gruppe,-1)
where R.SOID = A.OID ...

-- Hauptlieferant referenziert Adressen (Lieferanten mit KredNr):
Select OID, Name1, Nummer, Krednr, Debnr, Name2, Name3, Hauptlieferant
from Adressen where not Krednr is NULL and coalesce(Sperre, 'F') <> 'T'
order by coalesce(HauptLieferant, 'F') Desc, Name1
```

`IDENTNR`-Slots (Hersteller-/Ident-Referenzen) sind in der aktuellen EXE auf
12 Positionen gewachsen (2011-DB: nur 5) – siehe z. B.
`Select A.OID, A.ArtNr, A.Identnr1, ..., A.Identnr12, ... from Artikel A`.
Welche Position welchem Hersteller-Code (BT/LH/FY/…) entspricht, ließ sich aus
dem 2018er-Pascal-Code nicht ableiten (nur toter Code mit
`Z:\dokument\Liebherr\...`-Pfaden gefunden – Zeichnungsablage, keine
Feldbindung). Offener Punkt für eine spätere Prüfung.

## Reparatur: Belegstruktur (Belegart 154)

Reparaturaufträge sind KEIN eigenständiges Belegsystem, sondern laufen über den
generischen `BELEG`/`BELEGPOS`-Kopf mit `BELEGART = 154`, ergänzt um eine über
`BELEGNUMMER` (String-Join, kein FK) angehängte Satellitentabelle `REPKOPF`:

```sql
SELECT B.OID, B.Name1, B.nummer, A.Kurzname, B.Strasse, B.plz, B.Ort, B.Bestellnr,
  Trim(T.ORDERNR) as ORDERNR, T.ORDERZAEHL, T.IDENTNR, trim(T.Bezeichnung) as ABezeichnung,
  T.Status, R.Ustident, Upos, R.Kname, G.Bezeichnung as Gruppe,
  trim(R.Anrede) as Herkunftsort, R.Gewaehr, R.GewaehrH, R.famnr,
  R.Techniker as Meldnr, R.Schlagwort, R.liefschnr as Lnummer, B.Belegdatum,
  R.Anrede, B.Ort, B.Strasse, Fehler, Ausfall, RepBeschreib, B.Adrnr,
  B.Abschlagauftrag as Rahmen
From Beleg B
  left join RepKopf R on R.Belegnummer = B.Nummer and R.Belegnummer <> ''
  left join Repauftrag S on S.Belegnummer = B.nummer and S.Belegnummer <> ''
  left join RepArtikel T on T.OID = S.Geraetid
  left join RepGruppen G on G.OID = T.Gruppe
  left join Adressen A on A.OID = B.AdrOID
WHERE B.Belegart = 154
```

Gerätestatus-Update zur Bestätigung, dass `REPARTIKEL.STATUS` Gerätelebenszyklus
(nicht Werkstattstufe) abbildet:

```sql
Update Repartikel set Liefnr = :parLiefnr, Status = 'Im Einsatz' where OID = :parOID
```

### Material-Tab: Funktionsweise (validiert 2026-09-09)

`BELEGPOS`-Zeilen und `REPBUCHARTIKEL` (nicht im 2011-Schema, spätere
Ergänzung) werden für Druck-/Übersichtszwecke per `UNION` zusammengeführt:

```sql
with allArt as (
  Select OID, Artnr, Stck, text, IndentNrDruck, snralt, snrneu
  from Belegpos K where K.soid = :parOID and coalesce(Drucken, 'F') = 'F'
  union
  select OID, Artnr, Buchmenge as Stck, Bezeichnung1 as text, IdentNr, snralt, snrneu
  from REPBUCHARTIKEL K2 where K2.soid = :parOID2
)
select Artnr, Stck, text, IndentNrDruck, snralt, snrneu from allArt
```

Bestätigt: `BELEGPOS.DRUCKEN`/`BUCHEN` steuern Druck- bzw. Buchungsverhalten
unabhängig voneinander je Position (UI: "nicht drucken"/"nicht buchen",
invertiert dargestellt); `SNRALT`/`SNRNEU` existieren sowohl auf `BELEGPOS`
als auch auf `REPBUCHARTIKEL` – Bauteiltausch-Tracking je Materialzeile,
nicht nur am Gerät insgesamt.

Nicht geklärt: Bedeutung der "L"/"K"-Buttons neben dem Artikelfeld und die
genaue Funktion von "DruckID-Nr." (Dropdown, an elf Stellen im Programm
referenziert, aber ohne aufschlussreichen Kontext in den extrahierten
Strings) – keine Spekulation ohne Beleg.

### Gerät-Semantik: GID vs. IdentNr vs. Seriennr (Vergleich zweier Belege, 2026-09-09)

| | Beleg 9260929 | zweiter Beleg |
|---|---|---|
| GID | 17442 | **18866** |
| Gruppe | TKL AC3 | TKL AC3 |
| Bezeichnung | Klimagerät FRR TRAXX AC3 | Klimagerät FRR TRAXX AC3 |
| IdentNr | 3EGM064970R0001 | **3EGM064970R0001 (identisch)** |
| Seriennr | 0085/2015 | **1023/2022** |

Gleiche IdentNr/Gruppe/Bezeichnung, unterschiedliche GID und Seriennr →
`IDENTNR` = modellweite Hersteller-Typnummer, `GID` (`REPARTIKEL.OID`) =
interne ID des physischen Exemplars, `SERIENNR` (`REPAUFTRAG.SERIENNR`) =
Herstellerseriennummer dieses Exemplars. Odoo-Analogie: IdentNr ≈
`product.template`, GID+Seriennr zusammen ≈ `stock.lot` – `REPARTIKEL`
vermischt beide Ebenen in einer Tabelle.

### Kostenvoranschlag-Tab: DFM-Feldbindung KST/KFKT/KWERT (2026-09-09)

Direkter Ausschnitt aus der DFM-Ressource (Steuerelement-Deklarationen),
zeigt die Bindung der Befundung-Zeile an `REPKOPF`:

```
TDBEdit  dbebs  DataField KST1    DataSource dsRepKopf   (Std.)
TDBEdit  dbebw  DataField KWERT1  DataSource dsRepKopf   (Wert)
TDBEdit  dbebf  DataField KFKT1   DataSource dsRepKopf   (Faktor)
TDBEdit  dbers  DataField KST2    DataSource dsRepKopf   (Reparatur, Std.)
```

Präfix-Muster `dbeb*` = Befundung, `dber*` = Reparatur (Fortsetzung für
Reinigung/Abwicklung/Endprüfung analog, KST3-5/KFKT3-5/KWERT3-5).

`BELEG.ENDPRUEFUSER`/`ENDPRUEFDATUM` bestätigt separat:

```
53811: endpruefuser
61349: cdsBelegendpruefuser
61350: cdsBelegendpruefdatum
```

`BELEGPOS.REPLAGER` bestätigt:

```
78917:  cdsBelegPosReplager
100610: cdsBelegPosreplager
101036: REPLAGER
189011: Rep. Lager	DataField
189012: replager
```

`REPAUFTRAG.UEBERNOMMEN` bestätigt (aber auf Auftrags-, nicht sicher auf
Positionsebene):

```sql
Select NAME, KUNDENUMMER, BELEGNUMMER, DATUM, MITARBEITER, BERECHNET, NETTO,
  REPZEIT*60 as Rzeit, Schlagwort, LIEFSCHNR, KLIEFERNR, WEINGANGDATUM, STATUS,
  GERAETID, ABEZEICHNUNG, SERIENNR, GBEZEICHNUNG, GBESTELLNR, RARTIKELNR,
  GRUPPEID, PAUSCHALE, UEBERNOMMEN
from Repauftrag where GeraetID = :parOID
```

**Korrektur einer früheren Aussage:** In diesem Dokument wurde zuvor unter
"x_werkstattstufe" notiert, die Label-Captions "Reparatur"/"Reinigung"/
"Abwicklung"/"Endprüfung" hätten kein rückführbares Datenbankfeld. Das war
falsch bzw. unvollständig – sie gehören zur Kalkulationstabelle im
Kostenvoranschlag-Tab (siehe oben) und sind sehr wohl DB-gebunden. Die
Kernaussage zu `x_werkstattstufe` (kein Werkstatt-Durchlaufstatus im
Altsystem) bleibt davon unberührt, nur die Begründung war ungenau.

### Versand-Eingang-Tab: DFM-Feldbindungen (2026-09-09)

```
dbeSPEDITION   DataField SPEDITION
dbeSPEDNR      DataField SPEDNR
dbeVEDATUM     DataField VEDATUM
dbeSENDNUMMER  DataField SENDNUMMER
dbeSENDORT     DataField SENDORT
dbeTransport   DataField Transport
dbcfrei        DataField FREI    (TDBCheckBox "frei")
dbcunfrei      DataField FREI    (TDBCheckBox "unfrei" – dasselbe Feld!)
```

Plus `KDLSNR` (Kundenlieferschein Nr.) mehrfach referenziert. Alle Felder
lagen bereits im 2011-Schema unter `REPKOPF` vor (`TRANSPORT`, `KDLSNR`,
`SPEDITION`, `SPEDNR`, `VEDATUM` stehen dort sogar direkt hintereinander;
`SENDNUMMER`/`SENDORT` weiter unten im selben Table) – bisher aber ohne
UI-Label-Zuordnung dokumentiert.

### Reparatur-Beschr.-Tab: DFM-Feldbindungen inkl. Feldwiederverwendung (2026-09-09)

```
TDBEdit  dbeTECHNIKER   DataField TECHNIKER    (Meldungs-Nr./Ausfall-Nr.)
TDBEdit  dbeFamnr       DataField Famnr        (FAM-Nummer)
TDBEdit  dbeHerkunft    DataField Anrede       (Herkunft-Ort -- Feld heisst Anrede!)
TDBEdit  DBEdit15       DataField RARTIKELNR   (Herkunft-Einheit)
TDBEdit  dbeAUSBAUDATM  DataField AUSBAUDATM   (Ausbaudatum)
TDBEdit  dbeEINSATZZEIT DataField EINSATZZEIT  (Einsatzzeit)
TDBCombo dbcschlagwort  DataField Schlagwort   (Schlagwort)
TDBEdit  DBEdit17       DataField USTIDENT     (Bezugsnummer -- Feld heisst USt-IdNr.!)
TDBEdit  DBEdit19       DataField KName        (K-Name)
TDBMemo  dbmAUSFALL     DataField AUSFALL      (Fehlerbeschreibung aus Meldung)
TDBMemo  dbmFEHLER      DataField FEHLER       (zweite, leere Memo-Box)
TDBMemo  dbmREPBESCHREIB DataField REPBESCHREIB (vermutlich die grosse Flaeche rechts)
```

Bemerkenswert: `DBEdit15`/`DBEdit17`/`DBEdit19` behielten ihre generischen
Delphi-Standardnamen (nie umbenannt) – ein Indiz dafür, dass diese
Feldwiederverwendung (Anrede→Herkunft-Ort, USTIDENT→Bezugsnummer) tatsächlich
nachträgliche Zweckentfremdung bestehender Felder war, nicht von Anfang an so
geplant (sonst hätte man die Controls vermutlich passend benannt wie bei den
`dbe*`-Controls mit sprechenden Namen).

### Geräte-Info-Tab: Reparaturhistorie + InfoDokumente/InfoNotizen (2026-09-09)

Reparaturhistorie-Query (linkes Grid):

```sql
Select B.OID, Name1, Ort, Nummer, AdrNr, Belegdatum, Gedruckt, Abgeschlossen,
  Hauptauftrag, Liefstrasse, Orderzaehl, Ordernr
from Beleg B, Repkopf K
  left join RepAuftrag A on A.Belegnummer = K.Belegnummer
  left join RepArtikel R on R.OID = A.Geraetid
WHERE B.Belegart = 154 And K.Belegnummer = B.Nummer and B.Abgeschlossen = 'F'
Order By Nummer DESC
```

`InfoDokumente` (mittleres Grid "Dokument"), generisches, anwendungsweites
Anhängesystem:

```sql
Select * from InfoDokumente Where ModulID = :parModulOID
  And ObjektID = :parObjektOID And (BenutzerID = :parBenutzerOID OR GlobalU = 'T')
Insert into InfoDokumente (OID, ModulID, ObjektID, BenutzerID, Titel, GlobalU, Pfad, Bemerkung, Schritte) Values (...)
```

`InfoNotizen`, strukturell identisches Muster (vermutlich rechtes Grid, nicht
zweifelsfrei dieser Stelle zugeordnet):

```sql
Select * from InfoNotizen Where ModulID = :parModulOID
  And ObjektID = :parObjektOID And (BenutzerID = :parBenutzerOID OR GlobalU = 'T')
Insert into InfoNotizen (OID, ModulID, ObjektID, BenutzerID, Titel, GlobalU, Notiz, Bemerkung) Values (...)
```

Keine Bestätigung für den genauen `ModulID`-Wert gefunden, der Reparatur/
Geräte kennzeichnet (`fidGeraeteValue = 162` aus `UConsts.pas` ist ein
Kandidat, aber nicht direkt in einer Query mit InfoDokumente/InfoNotizen
zusammen gesehen).

### UI-Tippfehler bestätigt

Der Button "Fehlerzuordnung" heißt im tatsächlichen UI **"Fehlerzuordnumg"**
(Screenshot 2026-09-09) – bisher in der Doku fälschlich korrekt geschrieben.

### Live-Screenshot 2026-09-09: Belegmaske Auftrag 9260929 (Railpool GmbH)

Vom Nutzer bereitgestellter Screenshot der produktiven Reparatur-Belegmaske,
bestätigt fast jedes zuvor per SQL abgeleitete Feld visuell:

- Beleg 9260929, Typ **"Kostenvoranschlag"** (bestätigt Belegtyp-Dropdown)
- Rahmen-Feld befüllt mit Wert `260020` (bestätigt `BELEG.ABSCHLAGAUFTRAG` produktiv genutzt, kein Leerfeld)
- "Bewerten"-Checkbox aktiv gesetzt (bestätigt `ADRESSEN.BEWERTEN` produktiv genutzt)
- Gerät-Block: GID `17442`, Gruppe `TKL AC3`, IdentNr `3EGM064970R0001`,
  Bezeichnung `Klimagerät FRR TRAXX AC3`, Seriennr `0085/2015` – UI-Label
  ist wörtlich "GID" (nicht nur intern `REPARTIKEL.OID`)
- **Neu entdeckt:** "Produktion >"-Button im Gerät-Block – direkte
  UI-Verlinkung von Reparatur zu `PRODUKTION`, bisher nur indirekt über
  gemeinsame Felder vermutet, jetzt als expliziter Navigationspunkt bestätigt
- **Neu entdeckt:** Positionszeile hat eigene "Snr Alt"/"Snr Neu"-Felder
  (bestätigt `BELEGPOS.SNRALT`/`SNRNEU`), Checkboxen "nicht drucken"/
  "nicht buchen" (Kehrwert von `BELEGPOS.DRUCKEN`/`BUCHEN`), sowie **FAM**-
  und **BGS**-Buttons direkt auf der Position – `BELEG.FAMID` und
  `BEGLEITSCHEIN` sind damit granularer (pro Position) verknüpft als zuvor
  angenommen (dort nur auf Belegebene vermutet)
- Rechte Listenansicht "Reparatur": Spalten Belegnummer + zwei weitere Werte
  im Format der Seriennummer bzw. IdentNr/Artikelnummer – Übersichtsliste
  über alle Reparaturaufträge, aktueller Datensatz farblich markiert

Kein Datenbankfeld für die sechs Werkstatt-Durchlaufstufen
(Außenreinigung/Eingangsprüfung/Gesamtreinigung/In Bearbeitung/Endprüfung/
Verpacken) gefunden – nur UI-Elemente (`btnEndpruefung`, statische Label-
Captions). `x_werkstattstufe` im Addon ist vermutlich eine Odoo-seitige
Neukonzeption.

## Einkauf/Bestellung: Belegart-Zuordnung

Aus `HMS/Module/UConsts.pas` (Formular-ID-Konstanten) plus Live-SQL-Gegenprobe
in der aktuellen EXE:

- `fidAngebotValue = 100` – bestätigt (`AngeboteBG`-Query, `Belegart = 100`)
- `fidAuftragValue = 101` – bestätigt
- `fidLieferscheinValue = 102` – bestätigt
- `fidRechnungValue = 103` – bestätigt
- `fidBestellungValue = 105` – bestätigt (mehrfach, u. a. Wareneingangs-/Obligo-Queries)
- `fidBlockBestellungValue = 74` – bestätigt als Rahmenbestellungs-Belegart:
  `... from beleg B where Abrufartikel = :parOID and B.Belegart = 74 and Abgeschlossen = 'F'`
- `fidAnfrageValue = 118` – bestätigt: `Update Beleg set Abgeschlossen = 'T' ... And Belegart = 118`
- `fid8DValue = 154` – **Widerspruch**: laut Konstante "8D", aber empirisch mit
  `REPKOPF` (Reparatur) verjoint (siehe Reparatur-Abschnitt oben). Entweder
  wurden 8D und Reparatur zusammengelegt, oder die 2018er-Pascal-Quelle ist an
  dieser Stelle nicht mehr aktuell. Nicht abschließend geklärt.

Rahmenbestellung-Restmenge wird nicht aus der gespeicherten Spalte gelesen,
sondern live nachgerechnet:

```sql
Select B.OID, B.AdrOID, ..., B.Abrufmenge, B.Abrufartikel, B.AbrufartikelNr,
  B.Abrufpreis, B.RahmenNr, A.ArtNr,
  (Select sum(Stck) from Belegpos BP where RahmenOID = B.OID) as Bestellmenge,
  (B.Abrufmenge - (Select sum(Stck) from Belegpos BP where RahmenOID = B.OID)) as restmenge
from Beleg B left join Artikel A on A.OID = B.Abrufartikel
where Belegart = 74 And B.Abgeschlossen = 'F' And Abschlagauftrag in :parGruppen
```

`BESTELLKOPF`/`BESTELLPOS` (2011-Schema) existieren weiterhin, werden aber nur
noch von einer neueren Stored Procedure `P_BestellPos` (nicht im 2011-Schema,
also nach 2011 hinzugefügt) sowie vereinzelten einfachen Inserts angesprochen –
nicht vom eigentlichen Bestellprozess.

## Produktion: EngpassCockpit-Ladequery

```sql
select P.OID, P.KW, P.Jahr, P.Menge, Ar.Sperre, P.Fertig, P.EkBearb, P.EKStatus,
  P.CriticPath, CountBPos, CountRest, CountBestDat, CountNotBestellt, CountNOAB, CountKP,
  P.Beginndatum, ...
from Produktion P, Beleg A, Stuecklisten S
  left Join Artikel Ar on S.Artoid = Ar.OID
  Join Belegpos Bp on (A.OID = Bp.Soid and Bp.Artnr = S.Nummer)
where S.OID = P.ArtOID and A.OID = P.AuftragOID and P.Status <> -1
order by P.Beginndatum desc
```

Bestätigt: alle Engpass-relevanten Werte (`CriticPath`, sechs `Count*`-Spalten,
`EKStatus`) liegen vorberechnet direkt auf `PRODUKTION`, kein separates
Cockpit-Modul/eigene Tabelle. UI unterscheidet zusätzlich "Materialengpass"
und "Personalengpass" als Anzeige-Kategorien (`Rot: Materialengpass,
Materialstatus ...`), aber ohne eigene DB-Spalten dafür.

## Produktion: Laufkarte wird über Beleg-Feld-Umwidmung gerendert

```sql
Select B.achtdnrjahr, B.RechName1 as Laufkarte, B.LIEFNAME3 as Produktion,
  B.Achtdnrlieferant as Verantwortl, B.RECHNAME2 as Arbeitsschritt,
  B.Vsonst as Kosten, B.Name1 as ArtBezeichnung, ...
from Beleg B left join Belegtexte BT on BT.SOID = B.OID
where Belegart = :parArt and Belegdatum >= :parvon and Belegdatum <= :parbis
```

Fachfremde `BELEG`-Felder (Rechnungsname-, Achtdnr-Felder) werden für
Laufkarten per Alias umgewidmet – kein eigenes Laufkarten-Objekt.

## Produktion: Begleitschein ist eine eigene Tabelle

```sql
Select OID, Bezeichnung, Ausfallnr, Ausfertigung from Begleitschein Order by OID DESC
Select OID, Bezeichnung, Ausfertigung, Artikelname, snr, identnr, ausfallnr from Begleitschein where ...
```

Kommentarzeile im UI: "siehe auch Reparaturbegleitschein" – Kreuzverweis zu
Reparatur; `Ausfallnr` deutet auf Verknüpfung zu `REPAUSFALL`.

## Vertrieb: Belegart-Zuordnung + Abschlagrechnung-Korrektur

- Angebot=100, Auftrag=101, Lieferschein=102, Rechnung=103, Mahnung=104,
  Abschlagrechnung=108, Vertreterabrechnung=115 – alle bestätigt über
  `UConsts.pas`-Konstanten und/oder Live-SQL.
- UI-Strings belegen eindeutig "Abschlagrechnung" (Anzahlungsrechnung), nicht
  "Abschlussrechnung": `Abschlagrechnung1`, `Abschlagrechnungkopieren1`,
  `abzgl. Zahlung zu Abschlagrechnung Nr.: `, `G_NrRechnungAbschlag`.

## Vertrieb: Hauptauftrag-Kette (Beleg-Verknüpfung über Nummer, nicht FK)

```sql
Select B.HauptAuftrag as Auftrag, b.Nummer, b.AdrNr, b.OID as BelegOID, b.netto,
  b.Belegdatum, bp.Bestellnr, b.endpruefdatum, b.name1, b.abgeschlossen,
  bp.Epreis, bp.stck, bp.Rabatt, bp.GPreis, bp.Geliefert, bp.artnr, bp.text
from Beleg b, Belegpos bp
where (b.Belegart = :art) and bp.artoid = :oid and b.oid = bp.soid
ORDER by B.Belegdatum desc
```

## Vertrieb: Vertreterabrechnung (Provisionsberechnung)

```sql
Select V.*, cast((Stck*Epreis* (Select NVALUE from P_NULL(V.ProvPos)))as Integer)/100 as ProvisionSumme
from V_Vertreter V
where Belegdatum >= :parDatumvon and BelegDatum <= :parDatumbis
  And VertreterNr = :parVertreter
Order by VertreterNr, KundeNr, BelegDatum, Belegnummer
```

`ProvPos` (Provisionssatz) kommt aus einer Parameter-/Konfigurationsstelle
(`P_NULL`-Funktion als Null-Fallback), Provision existiert zusätzlich als
direktes Feld auf `BELEGPOS.PROVISION` (Override je Position) und
`ADRESSEN.PROVISION`/`PROVISION2` (Grundsatz je Vertreter).

## System/Firmendaten: Berechtigung ist der aktive Mechanismus, nicht die BENUTZER-Flags

```sql
Select * from Berechtigung where (UserID = :parUserOID) and (FormID = :parFormID)
Select * from Berechtigung where (UserID = :parUserOID) and (ModulID = :parModulID)
Select OID, ModulID, FormID, Modulname, Status, Mandantid from Berechtigung
  where (UserID = :parUserOID) and (FormID = :parFormID) and (coalesce(MandantID, 0) = :parMandant)
```

Keine Treffer in den EXE-Strings für Lesezugriffe auf die einzelnen
`BENUTZER`-Berechtigungsspalten (`ARTIKEL`, `LIEFERSCHEIN` etc.) oder für
Insert/Update auf `PERSONAL` – beide vermutlich Altlast, aber mit den
verfügbaren Quellen (String-Extraktion, kein Volltext-Quellcode der aktuellen
Version) nicht abschließend zu beweisen, nur die Abwesenheit von Treffern.

## Reproduktion

```bash
strings -n 4 Herrmann_Work/Herrmann.exe > exe_strings_ascii.txt
strings -n 4 -e l Herrmann_Work/Herrmann.exe > exe_strings_unicode.txt
grep -in "xrechnung\|leitweg\|peppol\|gelangen" exe_strings_ascii.txt exe_strings_unicode.txt
```
