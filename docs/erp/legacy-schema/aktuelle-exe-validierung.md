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

## Artikel-Karteikarte: IDENTNR-Slot-Klärung + Bestände-Panel (2026-09-09)

Live-Screenshot zeigt Artikel "40803-ETL" (Klimagerät FRR TRAXX AC3) mit
zwölf beschrifteten ID-Nummer-Zeilen BT/LH/FY/NK/KO/VK/BE/TK/DB/HO/WE/SI.
`BT = 3EGM064970R0001` – identisch mit dem `IdentNr`-Wert, der zuvor am
selben Gerät in der Reparatur-Belegmaske (`REPARTIKEL.IDENTNR`) gesehen
wurde. Damit belegt: Reparatur-`IdentNr` wird aus dem BT-Slot befüllt.

`LH = 10672713` (mit Zeichnungsnummer `200060000`) ebenfalls befüllt.

Kein direkter DFM-Beweis für die exakte `IDENTNR1`…`IDENTNR12`-Reihenfolge
gefunden (nur die Feldliste selbst, aus einer Suchmasken-Query):

```sql
Select OID, ARTNR, BEZEICHNUNG1, BEZEICHNUNG2, BEZEICHNUNG3,
  IDENTNR1, IDENTNR2, IDENTNR3, IDENTNR4, IDENTNR5, IDENTNR6, IDENTNR7,
  IDENTNR8, IDENTNR9, IDENTNR10, IDENTNR11, IDENTNR12, EKNETTO, VKNETTO,
  LAGERFAEHIG, EINHEIT, BESTELLNR ...
```

Nebenbefund: Addon-Codeliste hat nur 11 Einträge, es gibt aber einen 12.
("SI") am Ende der UI-Liste.

Bestände-Panel bindet an `dsInfoBestand` (Computed-Felder, nicht rohe
`ARTIKEL`-Spalten):

```
TDBEdit dbeMeldebestand  DataField Prodoffen   DataSource dsInfoBestand
TDBEdit dbeReserviert    DataField Produktion  DataSource dsInfoBestand
TDBEdit dbeBestellt      DataField Bestellt    DataSource dsInfoBestand
TDBEdit dbeinauftrag     DataField Auftrag     DataSource dsInfoBestand
```

Control-Namen (`lblMeldebestand`→Caption "Fertigung offen",
`lblReserviert`→Caption "Bedarf Prod.Auftrag") passen nicht mehr zu ihren
Beschriftungen – Indiz für nachträgliche Relabeling ohne Umbenennung der
Komponenten. `P_Bestand(A.OID)` als vermutete Quelle an anderer Stelle
referenziert (`( (( Select Bestand from P_Bestand(A.OID)) < -0.01 )`).

## Stückliste (aufgerufen über "Fertigungsteil"): STUECKLISTEN/STUECKLISTENARTIKEL (2026-09-09)

2011-Schema-Auszug (`full_schema.sql`), direkt gegen die Live-Screenshot-Felder
abgeglichen:

```sql
CREATE TABLE STUECKLISTEN (OID D_INTEGER NOT NULL,
  NUMMER, ANLAGE, GRUPPE, BEZEICHNUNG1-3, EKNETTO, VKNETTO, MWST, LAGERFAEHIG,
  EINHEIT, LAGERORT, BEMERKUNG, ARTTEXT, KURZBEZEICHNUNG, ARTOID, PRODARTOID,
  SCHRITTZEIT1-7, NUTZMENGE, DURCHLAUF, RUESTZEIT1-7, MELDEN, VINUMMER,
  FREIGABE, FREIGABEAV, IDENTNR1-3, B1, B2, F1, F2, G1, G2, AUSGST, AUSZ,
  ZEICHNUNGSNR, ABMESS, AA, AB, AC, AD, BESTELLAUFLOESEN, GEPRUEFT, AUSG,
  AUSGZ, STATUS, STANDARDPFAD, NOSPLITT);

CREATE TABLE STUECKLISTENARTIKEL (OID, SOID, NUMMER, ANLAGE, GRUPPE,
  BEZEICHNUNG1-3, EKNETTO, VKNETTO, MWST, LAGERFAEHIG, EINHEIT, LAGERORT,
  BESTELLNR, ..., ARTNR, ANZAHL, ARTOID, GPREIS, HAUPTLIEFERANT, ...,
  IDENTNR1-5);
```

`ARTIKEL.STUECKOID` als Verknüpfung, bereits über die Artikelsuche-Query
bestätigt (`coalesce(StueckOID, 0) > 0` = Fertigungsteil).

`MELDEN`, `FREIGABEAV`, `AUSG`, `STATUS`, `ABMESS`, `GEPRUEFT` allesamt
exakte Namenstreffer zu den UI-Labels. `SCHRITTZEIT1-7`/`RUESTZEIT1-7`
erklären den Tab "Arbeitsgänge / Material" und verknüpfen sich mit
`KONSTPRODSCHRITTE` aus dem Produktionsabschnitt.

## Stückliste: Zeichnung/St.-Block + Bearb./Gepr./Freig. (2026-09-09, DFM)

```
TLabel  Label13  Caption "Bearb."
TLabel  Label14  Caption "Gepr."
TLabel  Label15  Caption "Freig."
TLabel  Label16  Caption "nd./Datum"        (= Änd./Datum)

TDBEdit dbeb1   DataField (leer/B1)   DataSource dsStueckliste
TDBEdit dbeg1   DataField (leer/G1)   DataSource dsStueckliste
TDBEdit dbef1   DataField (leer/F1)   DataSource dsStueckliste
TDBEdit dbeaenddat  DataField Anlage  DataSource dsStueckliste   -- wiederverwendet!
TDBEdit dbeb2   DataField (leer/B2)   DataSource dsStueckliste
TDBEdit dbeg2   DataField (leer/G2)   DataSource dsStueckliste
TDBEdit dbef2   DataField (leer/F2)   DataSource dsStueckliste

TGroupBox GroupBox5  Caption "Zeichnung/St."
TLabel  Label18  Caption "Ausg."
TLabel  Label17  Caption "Zustand Z."
TLabel  Label19  Caption "Zustand S."
TDBEdit dbeausg    DataField AUSG    DataSource dsStueckliste
TDBEdit dbeausgz   DataField AUSGZ   DataSource dsStueckliste
TDBEdit dbeausgst  DataField AUSGST  DataSource dsStueckliste
TDBEdit dbezeichnr DataField zeichnungsnr DataSource dsStueckliste
   Hint: "2. Zeile in Beleg"
```

Für `dbeb1`/`dbeg1`/`dbef1`/`dbeb2`/`dbeg2`/`dbef2` wurde die `DataField`-
Werzeile in der `strings`-Ausgabe nicht sauber neben dem Label ausgegeben
(leer/verschmolzen) – Zuordnung zu `B1`/`G1`/`F1`/`B2`/`G2`/`F2` stützt sich
auf die Namenskonvention der Steuerelemente (`b1`→`B1` usw.) und die
1:1-Übereinstimmung mit den bereits aus dem 2011-Schema bekannten
`STUECKLISTEN`-Spalten `B1, B2, F1, F2, G1, G2`, nicht auf eine explizit
ausgelesene Feldwert-Zeile.

Zusätzlich an anderer Stelle desselben Formulars bestätigt:

```
TDBEdit dbestatus  DataField STATUS   (bereits bekannt)
TDBEdit dbeabmess  DataField ABMESS   (bereits bekannt)
TCheckBox "keine Splittung"  DataField NOSPLITT
```

Keine Bindung gefunden für die beiden Kopf-Zahlenfelder ("22094"/"110376")
und für das zweite ID-Nummer-Panel neben dem Material-Grid – beide bleiben
ungeklärt.

## Artikelinfo (F2): Label-Block in exakter Bildschirm-Reihenfolge (2026-09-09)

```
Tfrmartikelinfo2 / FArtikelinfo2   (Fenstername)

Kupferzahl
GEWICHT
Kupferzuschlag / m:
Bestellt:
Rahmenbestellung offen:
Geliefert:
Bestand verfügbar:
Bestand Sperrlager:
Bedarf
Auftrag:
EK:
VK:
Aufschlag %:
LEK:  vom:
MEK:
alter EK: vom:
Lieferschein
Lager
Reparatur
```

Reihenfolge der Strings in der EXE entspricht exakt der visuellen Reihenfolge
im Fenster — starkes Indiz, dass es sich um einen zusammenhängenden
Report-/Label-Block handelt (kein `TDBEdit` mit einzeln auslesbarem
`DataField`, sondern vermutlich ein `TQuickRep` oder ähnliches
Report-Steuerelement mit Laufzeit-Formatierung).

`Select Kupferzahl, Gewicht from Artikel where OID = :parOID` und Prozedur
`TGetKupferZuschlag` bestätigen den Kupferzuschlag-Block direkt.

Benachbarte Grid-Handler im selben Fenster (`Tfrmartikelinfo2`):
```
dbgAnfrageDblClick
dbgBestellungenDblClick
dbgRahmenbestellungDblClick
dbg8dLDblClick
dbgAngeboteDblClick
dbgAuftragDblClick
dbgLieferscheinTSPDblClick
dbgRechnungenDblClick
dbgRepDblClick
```

Diese erklären die Tab-Leiste (Buchungen/Teileverwendung/Einkauf/Vertrieb/
Reservierung/Kommission/Inventurwerte) als Sammlung von Beleglisten für
diesen Artikel.

## Artikelinfo, Reiter "Buchungen": vollständige Query (2026-09-09)

```sql
select L.Datum as Buchdatum, A.Bezeichnung1,
  case when (L.Bemerkung like 'Fertigmeldung%' or L.Bemerkung like '%Fertigung%'
             or L.Bemerkung like '%Kostenvor%' or L.Bemerkung like '%Prod%')
       then L.Belegoid
       else case when B.Nummer > 0 then B.Nummer else BA.Nummer end
  end as Vorgangnummer,
  case when (...) then L.Datum else B.Belegdatum end as Belegdatum,
  case when (L.Bemerkung like 'Fertigmeldung%' or L.Bemerkung like '%Fertigung%'
             or L.Bemerkung like '%Prod%')
       then 'Produktion'
       else case when B.Nummer > 0 then B.Belegbez else BA.Belegbez end
  end as Vorgangart,
  L.Menge, L.Bemerkung,
  case when (L.Bemerkung like 'Fertigmeldung%' or L.Bemerkung like '%Fertigung')
       then -99 else B.Belegart end as ModFID,
  L.BelegOID,
  (select S.Nummer || s.bezeichnung1 from Stuecklisten S
     where S.oid = (Select ArtOID from Produktion P
                     where P.oid = L.Belegoid and l.Bemerkung like 'Entna%')) as BG,
  (Select ArtOID from Produktion P where P.oid = L.Belegoid and l.Bemerkung like 'Entna%') as STOID,
  (Select Sum(Menge) as Bestand from lagerbuchung B
     where B.artoid = L.Artoid and B.Datum <= L.Datum) as Bestand
from Lagerbuchung L
  left join Artikel A on L.Artoid = A.Oid
  left Join Beleg B on B.Oid = L.BelegOID
  left join Belegpos bp on bp.oid = l.posOID
  left Join Beleg BA on BA.Oid = L.Auftragoid
where L.Artoid = :parOID
order by Buchdatum desc, 12 desc
```

Aktive/Historie-Split (Sub-Tabs):

```sql
with AllBuchung as (
  select 'Aktiv' as Art, Posoid, belegoid, lageroid, auftragoid,
         menge as AktivMenge, menge, bemerkung, datum
  from lagerbuchung where artoid = :parOID
  union
  select 'Hist ' as Art, Posoid, belegoid, lageroid, auftragoid,
         0.0 as Aktivmenge, menge, bemerkung, datum
  from lagerbuchung_HIST where artoid = :parOID2
)
Select A.Art, AktivMenge, A.Menge, A.Bemerkung, A.Datum,
  case when Auftragoid < 1 then (B.Belegbez || ': ' || cast(B.Nummer as varchar(10)))
       else ('Produktion: ' || cast(Auftragoid as Varchar(10))) end as Belegart
from Allbuchung A left join Beleg B on B.OID = A.belegoid order By Datum
```

Verbrauchs-Aggregation (bereits als Vorstufe zum Verbrauch-12/24/36-Monate-Block
in der Artikelinfo erkennbar):

```sql
Select sum(l.Menge) as Verbrauch, b.belegart
from Lagerbuchung l left join beleg b on b.oid = l.belegoid
where ArtOID = :parOID and (Datum between :parVon and :parBis)
  and Menge < 0 and not (l.Bemerkung like '%Inven%')
group by 2 Order by belegart
```

## Artikelinfo, Reiter "Teileverwendung": Where-used-Query (2026-09-09)

```sql
Select A.OID, S.Nummer from Stuecklistenartikel A, Stuecklisten S
where A.ArtOID = :parOID and A.Soid = S.OID
```

Live-Beispiel: Artikel erscheint in Baugruppe "2927 – Druckschutzklappen
System kpl" an Position 33, Menge 1,00 – bestätigt Spalten Nummer/
Bezeichnung (aus `STUECKLISTEN`) und Pos/Menge (aus `STUECKLISTENARTIKEL.
NUMMER`/`.ANZAHL`).

## Artikelinfo, Reiter "Einkauf": DFM-Grid-Spalten (2026-09-09)

Bestellung-Sub-Tab (`tshBestellung` → `dbgBestellungen` → `dsBestellungen`):

```
FieldName Nummer               Title.Caption "Belegnr."
FieldName Liefertermin         Title.Caption "Lieferdatum"
FieldName name1                Title.Caption "Name"
FieldName artnr                Title.Caption "Artikel"
FieldName stck                 Title.Caption "Menge"
FieldName Geliefert            Title.Caption "Geliefert"
FieldName Epreis               Title.Caption "Preis"
FieldName Lieferpreis          Title.Caption "Rp-Preis"
FieldName PreisPreiseinheit    Title.Caption "Preis PE"
FieldName RABATT               Title.Caption "Rabatt"
FieldName Preiseinheit         (Spalte "PE")
FieldName abgeschlossen        (Checkbox-Spalte "G.")
```

Rahmenbestellung-Sub-Tab (`tshRahmenbestell` → `dbgRahmenbestellung` →
`dsRahmenbestellung`):

```
FieldName Nummer          Title.Caption "Belegnr."
FieldName Belegdatum      Title.Caption "Lieferdatum"
FieldName name1           Title.Caption "Name"
FieldName Abrufmenge      Title.Caption "Menge"
FieldName Bestelltermin   Title.Caption "Laufz. von"
FieldName Liefertermin    Title.Caption "Laufz. bis"
FieldName Rahmennr
FieldName Abrufpreis
FieldName projekt
FieldName abgeschlossen   (Checkbox)
```

Belastungsanzeige-Sub-Tab: Caption "Belastungsanzeige", aber Steuerelemente
`tsh8dl`/`dbg8dL`/`ds8dl` — Label vermutlich nachträglich von "8D Lieferant"
umbenannt, Komponenten nicht mit umbenannt.

## Artikelinfo, Reiter "Vertrieb"→"Reparatur": Herkunft=Anrede endgültig bestätigt (2026-09-09)

Live-Daten aus der Spalte "Herkunft" (= `trim(K.Anrede)`): **Kassel,
Bellinzona, Kamenz ("Vor Ort in Kamenz"), Dessau, Kassel-Waldau, Krefeld,
Uelzen, Aachen** – reale Bahn-Wartungsstandorte, keine Anrede-Werte wie
"Herr"/"Frau"/"Firma". Bestätigt endgültig die bereits im Reparatur-Beschr.-
Abschnitt vermutete Wiederverwendung von `REPKOPF.ANREDE` als Einsatzort-Feld.

Spalte "Artikel" zeigt trotz Namens `BELEGPOS.TEXT` (Beschreibung), nicht
`ARTNR` – Beispielwert "Winkelverschraubung drehbar" ist ein Freitext, keine
Artikelnummer.

## Artikelinfo, Reiter "Reservierung (Auftrag)": V_BereitMaterial (2026-09-09)

```sql
Select Anzahl, Prodmenge, Artnr, Bezeichnung1, Kw, Jahr
from V_BereitMaterial
where Artoid = :parOID And not ProdOID = :parAuftrag
```

Dieselbe View-Familie wie beim EngpassCockpit (`V_BereitMaterial`,
`V_BereitMaterialSub`, `V_BereitMaterialSubSub` – letztere zwei mit
zusätzlichem `ProdAnzahl` bestätigt: `Select ProdAnzahl, Anzahl, Prodmenge,
Artnr, Bezeichnung1, Kw, Jahr from V_BereitMaterialSub where Artoid = :parOID`).

## Artikelinfo, Reiter "Kommision": V_ProdMaterial-Belege (2026-09-09, unvollständig)

```sql
Select * from V_ProdMaterial where Artoid = :parOID
  And (Sollmenge - Buchmenge) > 0 and (Status <> -1 or Status is NULL) and (Einheitmenge > 0)

Select (Sollmenge-Buchmenge) as Fertigung from V_Prodmaterial where Artoid = :parOID and Status > -1

Select sum(Sollmenge - Buchmenge) as Bedarf from V_ProdMaterial where Artoid = :parOID
  And (Sollmenge - Buchmenge) > 0 and (Status <> -1 or Status is NULL and Einheitmenge > 0)
  And ((Kw < :parKW and Jahr = :parJahr) or (Jahr < :parJahr1))

select distinct Artoid, Artnr from V_prodmaterial where Sollmenge - Buchmenge > 0
  and Status <> -1 Order by Artnr
```

Keine `Select *`-Aufschlüsselung von `V_ProdMaterial` selbst gefunden (die
View-Definition liegt nicht im 2011-Schema, da nach 2011 hinzugefügt) –
Spalten wie `Kw`/`Jahr`/`Sollmenge`/`Buchmenge`/`Status`/`Einheitmenge`/
`Artoid` sind nur indirekt über ihre Verwendung in `WHERE`-Klauseln
bestätigt, nicht als vollständige Spaltenliste.

## Artikelinfo, Reiter "Inventurwerte": dynamische Multi-Tabellen-Query (2026-09-09)

```sql
Select cast('<tabellenname>' as varchar30) as Inventur,
  cast(Inventurdatum as varchar10) as Vom,
  Artnr, Bezeichnung1, Bestand as Sollbestand, Istbestand, Lagerorte
from <tabellenname> where OID = ...
UNION Select ... from <nächste Tabelle> ...

with AllInv as ( ... ) Select * from AllInv order by Inventur desc
```

`INVENTUR`-Spalte = Tabellenname selbst, per `cast()` ausgegeben. Format
`Inventur0` + `JJJJMMTT` verifiziert gegen mehrere VOM-Werte im Screenshot
(`Inventur020251215`→15.12.2025, `Inventur020210104`→04.01.2021,
`Inventur020241217`→17.12.2024 – alle exakt passend). Jede Inventur = eigene
Tabelle, dynamisch per UNION zusammengeführt.

## Artikel, Reiter "Zusätzlich": DFM-Bindungen inkl. vertauschter Labels (2026-09-09)

```
TDBMemo dbebemerkung  Caption-Gruppe "…nderungstext"  DataField Textintern  DataSource dsArtikelTexte
TDBMemo gbeTextZusatz Caption-Gruppe "Interner Text"   DataField Textzusatz  DataSource dsArtikelTexte

TDBEdit DBEdit1  DataField WEJAHR      DataSource dsArtikel
TDBEdit DBEdit2  DataField Bestand     DataSource dsArtikel   (Label "Inventurbestand")
TDBEdit DBEdit4  DataField INVDATUM   DataSource dsArtikel
TDBEdit DBEdit5  DataField WAMONAT    DataSource dsArtikel
TDBEdit DBEdit20 DataField Zeugnistext DataSource dsArtikel   (Label "Zeugnistext (EK)")

TDBCheckBox DBCheckBox2  Caption "Zeubnispflicht - Text"  DataField aoftest       DataSource dsArtikel
TDBCheckBox DBCheckBox3  Caption "Funktionstest"          DataField Funktionstest DataSource dsArtikel
```

`Zeugnistext` ist nicht Teil des 2011-Schema-Auszugs für `ARTIKEL` –
bestätigte spätere Ergänzung.

## Artikel, Reiter "Preise / Referenzen": DFM-Bindungen (2026-09-09)

```
TDBComboBox dbcbxMwst   DataField MWST    DataSource dsArtikel  Items: Voll/Halb/Ohne/Dupo
TDBEdit     dbeEKNetto  DataField EKNetto DataSource dsArtikel
TDBEdit     dbeVKNetto  DataField VKNETTO DataSource dsArtikel
TDBEdit     dbeVKBrutto DataField calcVPBrutto DataSource dsArtikel  ReadOnly
TDBText     dbtKalkDatum DataField Kalkpreisupdate DataSource dsArtikel
TDBCheckBox DBCheckBox8 Caption "kein Preisupdate" DataField noAutoUpdate DataSource dsArtikel
TDBEdit     dbeLEK      DataSource dsInfoBestand   (nicht dsArtikel!)
TCheckDBGrid dbgArtikelPreise  -> Tabelle ARTIKELPREISE
```

`dbeLEK` (Label "alter Wert"/"Letzter RP") bindet an `dsInfoBestand`, das
bereits von der Allgemein-Seite bekannte Computed-Dataset – kein
gespeichertes `ARTIKEL`-Feld. Live-Wert `2,92`/`22.10.2024` deckt sich exakt
mit der zweitletzten Bestellzeile (Beleg 241990) aus dem Einkauf-Tab.

## Artikel, Reiter "Lagerorte": Bestand je Standort + Lagerplatzverwaltung (2026-09-09)

```sql
Select L.Lager, Sum(B.Menge) as Bestand from Lagerorte L
left join Lagerbuchung B on B.LagerOID = L.OId and B.Artoid = :parOID and Storno = 'F'
group by L.lager
```

Vollständige Stored-Procedure-Definition (Klartext im Binary gefunden):

```sql
ALTER PROCEDURE P_BESTANDV (AOID INTEGER) RETURNS (BESTAND NUMERIC(15,2)) AS
  DECLARE VARIABLE ZUB NUMERIC(15,2);
  DECLARE VARIABLE SCHROTT NUMERIC(15,2);
BEGIN
  SELECT SUM(MENGE) FROM LAGERBUCHUNG WHERE ArtOID = :AOID
    AND (LAGEROID IN (SELECT OID from Lagerorte where coalesce(art,'0') <> 'S') OR LAGEROID = 0)
  INTO :ZUB;
  IF (:ZUB IS NULL) THEN ZUB = 0; ELSE ZUB = :ZUB;
  BESTAND = ZUB;
  SUSPEND;
END
```

Lagerplätze-Grid (`LAGERPLAETZE`/`LAGERPLATZCROSS`, nicht im 2011-Schema):

```sql
Select * from LagerPlaetze order by Name
select * from lagerplatzCross where MasterOID = :parPlatz And ClientOID = :parORT and ArtOID = :partArtID
select P.Name as Platz from LagerplatzCross C, Lagerplaetze P
  where C.ArtOID = :parArtikelID and C.isentry = 'T' and P.OID = C.MasterOID
select p.Name, p.beschreibung, c.menge from lagerplatzcross C, lagerplaetze P, Artikel A
  where C.isentry = 'T' and C.Artoid = A.Oid and P.oid = C.masteroid And A.Artnr = '...'
Insert into Lagerplatzcross (OID, MasterOID, ArtOID, IsEntry) Values(Gen_ID(G_Lagerplatzcross,1), ...)
```

## Pascal-Quellcode Auftrag/Bestellung/Produktion: relevante Auszüge (2026-09-10)

Quellen: `HMS/Module/Belege/FAuftragTSP.pas` (1222 Zeilen),
`HMS/Module/Bestellung/FBestellungTSP.pas` (1960 Zeilen),
`HMS/Module/Produktion/FProduktion.pas` (2521 Zeilen). Alle Stand 2018,
lokal unter `Herrmann_Work/`, nicht Teil dieses Repos.

```pascal
// FAuftragTSP.pas – HAUPTAUFTRAG-Ursprung
procedure TfrmAuftragTSP.btnInsertClick(Sender: TObject);
...
  DataModul.cdsBeleg.Edit;
  DataModul.cdsBelegHAUPTAUFTRAG.AsString := DataModul.cdsBelegNUMMER.AsString;
...

// FAuftragTSP.pas – tote Menüpunkte (nur Kommentar, kein Code)
procedure TfrmAuftragTSP.pmiBestellungClick(Sender: TObject);
begin
  //
end;
-- identisch leer: pmiSammellieferscheinClick, pmiRechnungClick,
   pmiSammelrechnungClick, Abschlagrechnung1Click, Schlussrechnung1Click

// FAuftragTSP.pas – Auftrag -> Lieferschein
procedure TfrmAuftragTSP.pmiLieferscheinClick(Sender: TObject);
...
  DataModul.CopyChangeBelegAuftragLieferschein(genNummerPrefix + tblLieferschein, fidLieferschein, rstTrue);
  ...
  DataModul.SetFullGeliefert(DataModul.cdsBelegOID.AsInteger);
```

```pascal
// FBestellungTSP.pas – Wareneingang buchen, Qualitäts-Gate + 8D-Trigger
procedure TfrmBestellungTSP.btnBuchenClick(Sender: TObject);
begin
  if (DataModul.ISPruefeArtikel = True) or (DataModul.ISZeugnisArtikel = True) then
  begin
    if (DataModul.cdsBelegPosgeprueft.AsString <> 'T') then
    begin
      MessageDlg('Erst Prüfung vornehmen.', mtError, mbOKCancel, 0); Exit;
    end;
    if DataModul.ISZeugnisArtikel = True then
      if (DataModul.cdsBelegPosZeugnis.AsString <> 'T') then
      begin
        MessageDlg('erst Zeugnis bestätigen.', mtError, mbOKCancel, 0); Exit;
      end;
  end;
  ...
  if DataModul.cdsBelegPosReplager.AsString <> 'T' then
    TBucheKanbanArtikel.Execute(...)
  if DataModul.cdsBelegPosReplager.AsString = 'T' then
    TBucheKanbanArtikel.ExecuteReplager(...)
  DataModul.SetBestellbuchung;
  if (dbeAusschuss.Text <> '0') then
  begin
    A8dAnzahl := StrToFloat(dbeAusschuss.Text);
    if A8dAnzahl > 0 then
    begin
      CreateBelastungsAnzeige;
      MessageDlg('Achtung 8D - Lieferant ausgelöst.', mtConfirmation, mbOKCancel, 0);
    end;
  end;
...

procedure TfrmBestellungTSP.CreateBelastungsAnzeige;
...
  ABelegOID := TCreateBeleg.Execute(fidBelastungValue, DataModul.cdsBelegADROID.AsInteger,
    'G_NrBelastung', '', '8D Lieferant', DataModul.GetCDSController);
  ...
  TSetBelegField.Execute(ABelegOID, 'Liefname3', DataModul.cdsBelegNUMMER.AsString, ftString, ...);
  ...
  TCreateExcel8D.Execute(ExcelApp1, ABelegObj.OID, 'L', ..., CurrentEnvirement.Pfade.AchtDLPath);
```

```pascal
// FProduktion.pas – "In Fertigung nehmen": Werktage-Rückwärtsterminierung
procedure TfrmProduktion.actInFertigungExecute(Sender: TObject);
...
  AGetWorkDays := TGetWorkDays.Create;
  AProdDatum := AGetWorkDays.Execute(AProdDatum, AVorlauf, Zurueck);
  AGetWorkDays.Free;
  AWeek := WeekOf(AProdDatum);
  AYear := YearOf(AProdDatum);
  ...
  if ASplittArt = nichtSplitten then
    TSetFertigung.Create(ABereitstellung, AProdMenge, DataModul.GetCDSController, True);
  if ASplittArt = inBaugruppensplitten then
    TSetFertigung.Create(DataModul.cdsSuchen, 0, DataModul.GetCDSController, True);
```

## Pascal-Quellcode Lieferschein/Rechnung/Zeiterfassung (2026-09-10)

Quellen: `HMS/Module/Belege/FLieferscheinTSP.pas` (1053 Zeilen),
`HMS/Module/Belege/FRechnungTSP.pas` (763 Zeilen),
`HMS/Module/Zeiterfassung/FMitarbeiterZeiterfassung.pas` (1790 Zeilen).

```pascal
// FLieferscheinTSP.pas – der einzige echte Weg zur Rechnung
procedure TfrmLieferscheinTSP.pmiRechnungClick(Sender: TObject);
begin
  if DataModul.cdsBelegABGESCHLOSSEN.AsString <> 'T' then
  begin
    if DataModul.AllPreisGeprueft = True then
    begin
      if MessageDlg('Lieferschein in Rechnung übernehmen?', mtConfirmation, mbOKCancel, 0) = mrOk then
        DataModul.CopyChangeBelegLieferschein(genNummerPrefix + tblRechnung,
          fidRechnungValue, 'T', '',
          'Liefer-/Leistungsdatum: ' + DataModul.cdsBelegBELEGDATUM.AsString +
          ' Lieferschein: ' + DataModul.cdsBelegNUMMER.AsString);
        ...
    end
    else
      MessageDlg('Übernahme nicht möglich, nicht alle Preise geprüft.', mtInformation, mbOKCancel, 0);
  end;
end;
```

```pascal
// FRechnungTSP.pas – Gutschrift
procedure TfrmRechnungTSP.RechnungnachGutschriftkopieren1Click(Sender: TObject);
begin
  if MessageDlg(mldRechnunginGutschrift, mtConfirmation, mbOKCancel, 0) = mrOk then
    DataModul.CopyChangeBelegGutschrift(genNummerPrefix + genRechnung, fidRechnung, 'F',
      DataModul.cdsBelegHAUPTAUFTRAG.AsString, DataModul.cdsBelegNUMMER.AsString, 0);
  ...
end;
-- zusätzlich: RechnungnachGutschriftkopierenmitRckbuchung1Click (mit Rückbuchung)
```

```pascal
// FMitarbeiterZeiterfassung.pas – Monatsabschluss
procedure TfrmMitarbeiterZeiterfassung.WriteMonatNew(AMonat, AJahr: Integer);
...
  AGrundValue := TGrundValues.Create;
  AGrundValue.GetValues(DataModul.cdsBenutzerOID.AsInteger, DataModul.GetCDSController);
  AMonatValue := TFQZeitform.ExecuteNoPrint(AVT, AUrlaubgen, DataModul.cdsBenutzerOID.AsInteger, ...);
  AMonatValue.MonatArbeitstage := WerktageImMonat(AMonat, AJahr, 5);
  ...
  DataModul.cdsMonatwert.FieldByName('Sollzeit').AsFloat := AMonatValue.MonatSollminuten / 60;
```

## Pascal-Quellcode F8D.pas: relevante Auszüge (2026-09-10)

Quelle: `HMS/Module/Belege/8D/F8D.pas` (1880 Zeilen, lokal unter
`Herrmann_Work/`, Timestamp 13.09.2018 – nicht Teil dieses Repos).
**Achtung Altersstand:** Wie die DB (2011) und der übrige Pascal-Code ist
auch diese Datei von 2018 – für Felder/Buttons, die erst nach 2018 ergänzt
wurden (z. B. `REPLAGER`, `UEBERNAHME`), zeigt der Quellcode entsprechend
nichts; dort bleibt die DFM/EXE-Extraktion die einzige verfügbare Quelle.

```pascal
procedure Tfrm8D.pnlKalkulationClick(Sender: TObject);
begin
  DataModul.DataKalkulation.GetKalkulation(DataModul.cdsBelegPosOID.AsInteger);
  TfrmKalkulation.Execute(DataModul.DataKalkulation.cdsKalkulation, fraBtn.btnSave.Enabled, DataModul);
end;

procedure Tfrm8D.Panel1Click(Sender: TObject);
begin
  TfrmLangtext.Execute(TfrmLangtext, DataModul.cdsRepKpos);
end;

procedure Tfrm8D.dbeefExit(Sender: TObject);
begin
  TChangeThreeFieldsDB.ExecuteDB(dbees, dbeef, dbeew, ChangeFieldThree, MathMultiplikation, 1);
end;

procedure Tfrm8D.btnRahmenClick(Sender: TObject);
...
  DataModul.cdsBeleg.edit;
  DataModul.cdsBelegABSCHLAGAUFTRAG.AsInteger := ABelegObj.Nummer;
...

procedure Tfrm8D.btnEndpruefungClick(Sender: TObject);
...
  DataModul.cdsBeleg.Edit;
  DataModul.cdsBelegendpruefuser.AsString := AName;
  DataModul.cdsBelegendpruefdatum.AsString := DateToStr(Date);
...

procedure Tfrm8D.dbcgPosPaintPanel(DBCtrlGrid: TDBCtrlGrid; Index: Integer);
begin
  if DataModul.cdsBelegPosRefOID.AsInteger > 0 then
    lblFam.Font.Color := clGreen else lblFam.Font.Color := clWhite;
  if DataModul.cdsBelegPosRefOID2.AsInteger > 0 then
    lblBgs.Font.Color := clGreen else lblBgs.Font.Color := clWhite;
end;

procedure Tfrm8D.pnlFamClick(Sender: TObject);
...
  AFam := TFAMObject.Create(DataModul.GetCDSController);
  AFam.New(famFam);
  ...
  AFam.STANDORT := dbeHerkunft.Text;
  AFam.AUSFALLNR := dbeFamnr.Text;
  AFam.IDENTNR := DataModul.cdsBelegPosIndentNrDruck.AsString;
  AFam.ARTIKELNR := AArtObj.HauptLiefer;
  AFam.BEZEICHNUNG := AArtObj.Bestellnr;
  ...
  DataModul.cdsBelegPos.Edit;
  DataModul.cdsBelegPosRefOID.AsInteger := AFamID;
...

procedure Tfrm8D.pnlBGSClick(Sender: TObject);
...
  AFam := TFAMObject.Create(DataModul.GetCDSController);
  AFam.New(famBGS);       -- gleiche Klasse, anderer Typ als pnlFamClick
  ...
  DataModul.cdsBelegPos.Edit;
  DataModul.cdsBelegPosRefOID2.AsInteger := AFamID;
...

procedure Tfrm8D.btnaktiv1Click(Sender: TObject);
begin
  if DataModul.cdsBelegpufferlager.AsString = 'T' then ShowMessage('Bereits in Lieferschein.');
  grpkva2.Color := clrFieldStandard; grpkva1.Color := clrKostAktiv;
  DataModul.cdsBeleg.Edit; DataModul.cdsBelegFromBelegart.AsInteger := 2;
end;
-- btnAktiv2Click analog, setzt FromBelegart := 1

procedure Tfrm8D.btnSearchAdrClick(Sender: TObject);
...
  DataModul.cdsBeleg.Edit;
  DataModul.cdsBelegMWSTSATZ.AsFloat := AAdressObject.AbwUst;
...

procedure Tfrm8D.dbmREPBESCHREIBEnter(Sender: TObject);
begin
  pnlBeschreib.Left := 19; pnlBeschreib.Width := 650;
end;
procedure Tfrm8D.dbmREPBESCHREIBExit(Sender: TObject);
begin
  pnlBeschreib.Left := 415; pnlBeschreib.Width := 350;
end;
```

Keine Fundstelle für "Werkstatt"/"Reinigung"/"Eingangsprüfung"/"Verpacken"
im gesamten File (`grep` über alle 1880 Zeilen, 0 Treffer).

## Echter Programmierfehler gefunden: doppelte DataField-Bindung (TFRMARTIKELINFO2)

```
object DBEdit8: TDBEdit    Top=19   DataField = 'Zeichnung'       -- BT-Zeile
object DBEdit9: TDBEdit    Top=43   DataField = 'ZeichnungsNr2'   -- LH-Zeile
object DBEdit10: TDBEdit   Top=67   DataField = 'ZeichnungsNr2'   -- FY-Zeile, SOLLTE ZeichnungsNr3 sein!
```

Beide `ReadOnly = True`. Erklärt den im Screenshot beobachteten identischen
Wert `200060000` bei LH und FY: `DBEdit10` liest denselben Datenbankwert wie
`DBEdit9`, weil beim Kopieren der Komponente das `DataField` nicht auf
`ZeichnungsNr3` umgestellt wurde – ein Bug im Originalformular, kein
Anzeige- oder Datenartefakt.

## Echte DFM-Extraktion, Runde 2 (2026-09-09): sieben weitere Klärungen

### IDENTNR1-12 = BT...SI, jetzt koordinatenbasiert bewiesen (TFRMARTIKELTSP)

```
GroupBox13 "ID-Nummer":
  Label62 "BT"  Top=20   dbeid1  Top=16  DataField=Identnr1
  Label63 "LH"  Top=43   dbeid2  Top=39  DataField=Identnr2
  Label64 "FY"  Top=67   dbeid3  Top=63  DataField=Identnr3
  Label65 "NK"  Top=90                   DataField=Identnr4
  Label66 "KO"  Top=114                  DataField=Identnr5
  Label68 "VK"  Top=138                  DataField=Identnr6
  Label69 "BE"  Top=161                  DataField=Identnr7
  Label81 "TK"  Top=185                  DataField=Identnr8
  Label82 "DB"  Top=209                  DataField=Identnr9
  Label84 "HO"  Top=232                  DataField=Identnr10
  Label17 "WE"  Top=256                  DataField=Identnr11
  Label53 "SI"  Top=280                  DataField=Identnr12
```

### ARTIKELPREISE-Grid, vollständige 15-Spalten-Liste (TFRMARTIKELTSP)

```
dbgArtikelPreise: TDBGrid  DataSource=dsArtikelPreise
  LIEFERNAME "Lieferant" | MENGEVON "Menge von" | MENGEBIS "Menge bis"
  | EKBRUTTO "Ek. Preis" | Mindestmenge "VP-Einheit" | Lieferzeit
  | Preiseinheit | BESTELLNR "Bestell-Nr." | RABATT | Kupferzahl "Kupferbasis"
  | BEZEICHNUNG | DATUM | Angebotnummer | Ufaktor "Faktor" | UEinheit "Einheit"
```

Keine Spalte heißt "LEK" – frühere Lesart des Screenshots war falsch.

### Material-Tab (TFRM8D, DataSource=dsBelegPos): K-Button, DruckID-Nr., Artikel-ersetzen-Button

```
object pnlKalkulation: TPanel
  Caption = 'K'; OnClick = 'pnlKalkulationClick'      -- "K" = Kalkulation
object lblLhnr2: TLabel
  Caption = 'DruckID-Nr.'
object dbecbldnr: TDBComboBox
  DataField = 'IndentNrDruck'; DataSource = 'dsBelegPos'
  Items.Strings = ('Voll' 'Halb' 'Ohne')
object pnlFam: TPanel     Caption = 'FAM'; OnClick = 'pnlFamClick'
object pnlBGS: TPanel     Caption = 'BGS'; OnClick = 'pnlBGSClick'
object pnlArtersetz: TPanel  Caption = '<-'; OnClick = 'pnlArtersetzClick'   -- neu entdeckt
```

Kein "L"-Button auf diesem Tab. Das einzige `Caption = 'L'` im ganzen
Formular ist `Panel1` im separaten Kostenvoranschlag-Grid (Funktion
weiterhin unklar).

### Versand-Ausgang-Tab (TFRM8D): eigener, reicherer Feldsatz statt Spiegel-Tab

```
dbername1/2/3, dberstrasse, dberplz, dberort, dberkundenr  -- Lieferadresse (dsRepKopf: Name1-3/Strasse/Plz/Ort/KUNDENUMMER)
dberv1..dberv7   DataField VFELD1..VFELD7
dberbetrag1/2    DataField BETRAG1/BETRAG2
eberabw          DataField ABWICKLUNG
dbRkm/dberkmfaktor/dberkmwert     DataField RKM/RKMFAKTOR/RKMWERT
dbRstd/dbeRSTDFAKTOR/dbeRSTDWERT  DataField RSTD/RSTDFAKTOR/RSTDWERT
```

Labels bestätigen die Zuordnung: "Transport"/"Verpackung"/"Gewicht" (Kopf),
"Abholung"/"Zustellung bis"/"Frachtzahler"/"Besteller" (Termine/Parteien),
"km"/"Faktor" und "Std."/"Faktor" (zwei Std./Faktor/Wert-Rechenblöcke wie
im Kostenvoranschlag, hier für Versandkosten).

### REPBESCHREIB-Box: Größe bestätigt die Zuordnung

```
object dbmREPBESCHREIB: TDBMemo
  Left = 1; Top = 1; Width = 343; Height = 197; Align = 'alClient'
  DataField = 'REPBESCHREIB'; DataSource = 'dsRepKopf'
```

343×197px, füllt seinen Container vollständig – bestätigt die große
Fläche rechts im Reparatur-Beschr.-Tab.

## Echte DFM-Extraktion (2026-09-09): Werkzeug + drei Korrekturen

Ab hier auf Basis eines selbstgebauten Decoders für das binäre Delphi-DFM-
Format (`docs/legacy-schema/dfm-tool/`), nicht mehr auf `strings`-Textsuche
gestützt. Details zum Werkzeug: [`dfm-tool/README.md`](dfm-tool/README.md).
Alle 471 Formulare aus `Herrmann.exe` liegen dekodiert unter
[`forms-dfm/`](../../legacy-schema/forms-dfm).

### Korrektur 1: "Kommision"-Tab, echte FieldNames

```
object dbgKomm: TDBGrid
  DataSource = 'dsKomm'
  Columns = <
    item0 = { FieldName = 'Kw' }
    item1 = { FieldName = 'Jahr' }
    item2 = { FieldName = 'Anzahl'; Title.Caption = 'Restmenge' }
    item3 = { FieldName = 'Sollmenge' }
    item4 = { FieldName = 'Stuecknummer'; Title.Caption = 'Baugruppe' }
    item5 = { FieldName = 'stbez'; Title.Caption = 'Bezeichnung' }
    item6 = { FieldName = 'Prodmenge' }
    item7 = { FieldName = 'Fertig' }
    item8 = { FieldName = 'Auftragnummer'; Visible = False }
    item9 = { FieldName = 'Kunde'; Visible = False }
  >
```

Vorherige Vermutung (`Restmenge = Sollmenge - Buchmenge` berechnet,
`Baugruppe`/`Bezeichnung` = `STUECKLISTEN.NUMMER`/`.BEZEICHNUNG1`) war
falsch – reale Feldnamen sind `Anzahl`/`Stuecknummer`/`stbez` (eigene
Aliase, SQL-Quelle weiterhin nicht im Klartext auffindbar).

### Korrektur 2+3: Reparatur-Belegmaske ist intern `TFRM8D`

Kein separates `TFRMREPARATUR` gefunden – die komplette Belegmaske
(Kostenvoranschlag/Material/Versand-Tabs) ist die Delphi-Klasse `TFRM8D`.
Das Positionsgrid im Kostenvoranschlag-Tab bindet an `dsrepkpos`
(`REPKPOS`), nicht an `BELEGPOS`:

```
object dbcDruckenK: TDBCheckBox
  Caption = 'nicht drucken'; DataField = 'drucken'; DataSource = 'dsrepkpos'
object dbcrepkbuchen: TDBCheckBox
  Caption = 'nicht buchen'; DataField = 'buchen'; DataSource = 'dsrepkpos'
object Panel1: TPanel
  Caption = 'L'; OnClick = 'Panel1Click'          -- echter Action-Button, Zweck unklar
object DBCheckBox2: TDBCheckBox
  Caption = 'Rep. Lager'; DataField = 'replager'; DataSource = 'dsrepkpos'
object DBCheckBox6: TDBCheckBox
  Caption = 'Übern.'; DataField = 'uebernahme'; DataSource = 'dsrepkpos'
```

Frühere Vermutung `REPAUFTRAG.UEBERNOMMEN` für "Übern." war falsch – reales
Feld ist `REPKPOS.UEBERNAHME`. "Rep. Lager" auf diesem Grid ist
`REPKPOS.REPLAGER`, nicht `BELEGPOS.REPLAGER` (das bleibt für das separate
Material-Tab-Grid bestehen).

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

**Positions-Zuordnung jetzt vollständig geklärt (2026-09-09), doppelt
codebestätigt und per Live-Screenshot bestätigt.** Die Labels neben den
`IdentNr1-12`-Feldern wurden über die Top-Koordinaten in zwei unabhängigen
DFM-Formularen (`TFRMARTIKELINFO2.dfm.txt` zeigt Position 1-9,
`TFRMARTIKELTSP.dfm.txt` alle 12) den Edit-Feldern zugeordnet
(Label-`Top` ≈ Feld-`Top` + 4px, in beiden Formularen identisch und
durchgängig konsistent):

| IdentNr | Code |
|---|---|
| 1 | BT |
| 2 | LH |
| 3 | FY |
| 4 | NK |
| 5 | KO |
| 6 | VK |
| 7 | BE |
| 8 | TK |
| 9 | DB |
| 10 | HO |
| 11 | WE |
| 12 | SI |

Vom Nutzer live per Screenshot bestätigt (`ID-Nummer`-Panel zeigt exakt
diese 12 Labels in dieser Reihenfolge). Klarnamen bekannt nur für BT
(Bombardier), LH (Liebherr), NK (Noske Käser) – für FY/KO/VK/BE/TK/DB/HO/WE/SI
kein Legendentext, kein Tooltip, kein Pascal-Kommentar gefunden, der sie
auflöst; nur toter Code mit `Z:\dokument\Liebherr\...`-Pfaden (Zeichnungsablage,
keine Feldbindung) und ein separater, unabhängiger Mechanismus
(`btnInsertHerstellerClick`/`TInsertHerstellerArtikel`, echte n:m-Zuordnung
Artikel↔`HERSTELLER`-Stammdatentabelle mit Klarnamen, aber ohne Bezug zu
den 12 festen `IdentNr`-Kürzelfeldern) wurden dabei gefunden. Auflösung der
restlichen Klarnamen bräuchte Live-Zugriff auf die `HERSTELLER`-Tabelle
(x86-Firebird-Zugriffskette, in dieser Session nicht verfügbar) oder
Werkswissen.

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

## Nummernkreise: Beleg-Nummernformat und Reparatur-Präfix "RB9" (2026-09-09)

**Mechanismus (codebestätigt):** Jede Belegart hat einen eigenen, admin-
konfigurierbaren Nummernkreis. Der Dialog `TFRMNUMMERKREISDLG`
("Nummernkreise") zeigt pro Gruppe vier Einstellungen – `Kennung` (freier
Text-Präfix, `NUMMERNPARAM.KENNUNG D_VARCHAR10`), `Jahr`
(nichts/4-stellig/2-stellig), `Monat/Periode` (nichts/Monat/Periode) und
`Stellen` (5/4/3-stellig für die laufende Nummer). Backing-Tabelle:
`NUMMERNPARAM (OID, NAME, KENNUNG, JAHR, MONATPER, STELLENOFFSET, MODULID)`.
Der eigentliche Zähler ist kein Tabellenfeld, sondern ein Firebird-
Generator: `Select GEN_ID(..., 1) from ID` zieht atomar die nächste Nummer,
`Set Generator ... to ...` setzt ihn im Dialog manuell zurück (mit Guard
"Neue Nummer liegt nicht im gültigen Bereich!" gegen Rückwärtssprünge unter
bereits vergebene Nummern).

**Reparatur hat einen eigenen, dedizierten Generator**, bestätigt direkt in
`HMS/Module/Belege/8D/F8D.pas`:

```pascal
DataModul.GetNewNummer('G_Nr8D');
```

`G_Nr8D` ist vollständig getrennt von z.B. `G_NrAngebot` – Reparatur-Nummern
und Angebots-/Kostenvoranschlag-Nummern laufen über unterschiedliche Zähler,
nicht nur unterschiedliche Präfixe auf demselben Zähler.

**Zurückgezogene Fehlannahme:** eine frühere Deutung dieser Session hielt
eine Ziffer im Nummernformat (Beispiel `RB926xxxx`) für einen Monatscode.
**Falsch** – nach Nutzerauskunft (Domänenwissen, nicht Code-Beleg) dient die
`9` ausschließlich dazu, Reparatur-Nummern von anderen Belegen zu
unterscheiden, die nur `26xxxx` (Jahr + laufende Nummer, ohne Zusatzziffer)
zeigen, z.B. Kostenvoranschlag. Plausibelste technische Erklärung: die `9`
ist vermutlich Teil der konfigurierten `Kennung` selbst (`Kennung = "RB9"`
als ganzer String), nicht separat berechnet – frei admin-vergeben,
unabhängig vom internen Pascal-Namen `G_Nr8D`.

**Endgültig geklärt, jetzt mit Code-Beleg statt Vermutung:** die frühere
Beobachtung, dass `fidReparaturValue = 159` zufällig auf `9` endet (neben
`fid8DValue = 154`, `fid8DInternValue = 156`, `fid8DNeuValue = 165` aus
`UConsts.pas`), wird durch die tatsächliche Nummer-Bau-Funktion
`TBuildNummer.doBuildNumer` (`HMS/Module/UDBWorkObjects.pas`) widerlegt:

```pascal
function TBuildNummer.doBuildNumer(AKenn: string; AJahr, AMonPer,
  AOffset: TNummernParams; ANumer: Integer; NoKenn: Boolean): string;
begin
  if NoKenn = False then Result := AKenn;
  case AJahr of
    npJahrZwei: Result := Result + copy(IntToStr(YearOf(Date)), 3, 2);
    npJahrVier: Result := Result + IntToStr(YearOf(Date));
  end;
  case AMonPer of
    npMonat: Result := Result + SetStellen(MonthOf(Date), 1);   // IMMER 2-stellig (z.B. "09")
    npPeriode: ... '01'/'02'/'03'/'04' ...                       // IMMER 2-stellig
  end;
  case AOffset of
    npOffset4: Result := Result + SetStellen(ANumer, 3);         // 4-stellige laufende Nummer
  end;
end;
```

Jeder der drei Bausteine nach `Kennung` (Jahr/Monat-Periode/laufende
Nummer) liefert entweder nichts oder einen Block von mindestens zwei
Zeichen – Monat wäre zwingend zweistellig (`"09"`, nicht `"9"`). Eine
einzelne, nackte Ziffer wie die `9` in `RB926xxxx` kann aus keinem dieser
Bausteine stammen. Sie muss also Teil des `Kennung`-Strings selbst sein:
`Kennung = "RB9"` (drei Zeichen, frei im Nummernkreis-Dialog eingetragen).

Bestätigt außerdem, wie die richtige Kennung pro Belegart gefunden wird
(`TGetBelegKennung.doGetKennung`):

```pascal
function TGetBelegKennung.doGetKennung(AModulID: Integer): string;
begin
  Result := '';
  Load(FCDS, TSQLGetNummerKeisByModulID.Create(AModulID));
  if not FCDS.IsEmpty then Result := FCDS.FieldByName('Kennung').AsString;
end;
```

Pro `MODULID` (z.B. `fid8DValue = 154`) existiert genau eine
`NUMMERNPARAM`-Zeile mit eigener `Kennung` – die Auswahl läuft über
`MODULID`, der `Kennung`-**Inhalt** ist aber reiner Admin-Freitext, ohne
jede algorithmische Verbindung zum Belegart-Code. Die
`fidReparaturValue=159`-Beobachtung war damit eine reine Zahlenkoinzidenz,
kein Mechanismus.

### Dritter Nummernkreis: "Projekt"-Nummern (`KonstProjekte`/`KonstSMT.BAUGRUPPE`) sind reiner Freitext

Der Suchdialog `TFRMPROJEKTSUCHENDLG` in `ProjektzeitenHM.exe` ("Projekte -
Suchen", aufgerufen über den "Projekt suchen"-Pfad im Stempel-Dialog)
zeigt eine dritte, von Beleg-Nummernkreisen und `G_Nr8D` komplett getrennte
Nummernwelt. Live-Screenshot-Beispiele: `12001`–`12012` (lückenlos
durchgehend), `11005`/`11008`/`11013`/`11016`/`11019`/`11020`/`11024`
(Lücken durch den "aktive"-Filter erklärbar), `10027`/`10045`, `09032`,
`08031`, `04040`, `00101`. Das Muster passt auf `YY` (2-stelliges Jahr) +
`NNN` (3-stellige laufende Nummer je Jahr), mit `00` vermutlich als
Sammel-Pseudojahr für "kein spezifisches Projekt" (`00101` = "Vorrat
allgemein"/"INTERN").

**Codegegenprobe in `HMS/Module/ProjektZeit/UProjekteTSP.pas` zeigt: das
Muster ist eine Anwender-Konvention, kein Systemmechanismus:**

```pascal
procedure TCustomProjektObject.doNew;
begin
  Load(FCDS, TSQLGetTSPOneProjekt.Create(-564654654));
  FCDS.Append;
  FOID := dmServer.GetNewID('G_KonstProjekte');  // nur die interne OID wird generiert
  FCDS.Edit;
  FCDS.FieldByName('OID').AsInteger := FOID;
end;

procedure TCustomProjektObject.doSaveData;
begin
  FCDS.Edit;
  ...
  FCDS.FieldByName('Baugruppe').AsString := FBaugruppe;  // reiner Freitext, keine Formatierung
  ...
end;
```

`KONSTPROJEKTE.BAUGRUPPE`/`KONSTSMT.BAUGRUPPE` sind `D_VARCHAR10` ohne
jede Format-Validierung – anders als bei Belegen (`NUMMERNPARAM` +
Firebird-Generator) oder Reparatur (`G_Nr8D`) gibt es hier keinen
Nummernkreis-Mechanismus. Das YY-NNN-Muster in den Live-Daten ist eine von
den Konstrukteuren/Anwendern selbst eingehaltene Namenskonvention, kein
codeseitig erzwungenes Format. Nur die interne `OID` wird automatisch
vergeben (`G_KonstProjekte`), für den Anwender unsichtbar.

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

## Option C: Zugriff auf die aktuelle Live-Datenbank (Stand 2026-09-08)

Bisherige Quellen (2011er-DB-Kopie, 2018er-Pascal-Code, EXE-String-Extraktion)
durch echten Zugriff auf die **tagesaktuelle Produktiv-Datenbank** ergänzt.
`DbConfig.ini` im `Herrmann_Work`-Verzeichnis verweist auf einen Firebird-Server
im Firmennetz (`192.100.0.116:E:\TES_Data\IBDB.FDB`, passt zum bekannten
DHCP-Bereich, siehe Memory `project_herrmann_network_dhcp`) – ein direkter
Netzwerkzugriff war aber gar nicht nötig: Im übergeordneten Ordner
`Herrman Work Test` lag bereits eine lokale Kopie `IBDB.FDB` (2.186.559.488
Bytes ≈ 2,04 GB, Dateidatum 2026-09-08 14:13), erkennbar am Pfad als dieselbe
Datenbank wie auf dem Server referenziert.

**Verbindung:** dieselbe x86-Firebird-2.5.9-Embedded-Engine wie für die
2011er-DB (x64-Embedded schlägt weiterhin mit "not a valid database" fehl).
Login `sysdba`/`masterkey` (Firebird-Default) funktioniert – im
Embedded-Modus wird das im Programmcode gefundene Credential-Beispiel
(`gds32aufrufe.pas`, ursprünglich nur für eine Benutzerverwaltungs-Demo
gehalten) tatsächlich für den echten produktiven Datenbankzugriff verwendet.

### Aktualitätsnachweis

```sql
SELECT MAX(BELEGDATUM), MIN(BELEGDATUM), COUNT(*) FROM BELEG;
-- MAX_D: 8-SEP-2026   MIN_D: 11-DEC-2002   ANZ: 161183
```

`MAX(BELEGDATUM)` = Prüfungsdatum selbst → zweifelsfrei die tagesaktuelle
Produktivdatenbank, kein Backup mit Verzögerung.

### Schema-Wachstum 2011 → 2026: 194 → 437 Tabellen (+243), keine Tabelle entfernt

```sql
SELECT COUNT(*) FROM rdb$relations WHERE rdb$system_flag = 0 AND rdb$view_blr IS NULL; -- 437 Tabellen
SELECT COUNT(*) FROM rdb$relations WHERE rdb$system_flag = 0 AND rdb$view_blr IS NOT NULL; -- 47 Views
SELECT COUNT(*) FROM rdb$procedures WHERE rdb$system_flag = 0; -- 111 Prozeduren
```

Vollständiger DDL-Export: [`full_schema_current.sql`](full_schema_current.sql)
(19.373 Zeilen, vs. 6.931 in der 2011er-Version). Tabellendiff (`comm` gegen
die 2011er-Tabellenliste) bestätigt: **0 Tabellen entfernt, 243 neu
hinzugekommen** – exakt das in der Kernbeobachtung des Hauptdokuments
beschriebene "nichts wird aufgeräumt"-Muster, jetzt mit echten Zahlen statt
Einzelbeispielen belegt.

Neue Tabellen gruppieren sich in klar erkennbare, seit 2011 komplett neu
entstandene Subsysteme:

- **Prozess-/Arbeitsplan-Modul**: `PROZESSMAIN`, `PROZESSSTRUKTUR`,
  `PROZESSABTEILUNGEN`, `PROZESSGRUPPEN`, `PROZESSZEITEN(-K/-S)`,
  `PROZESSOBJEKTE`, `PROZESSLINK`, `VIPROZESSCROSS` – ein zusätzlicher
  Workflow-/Arbeitsschritt-Layer neben der alten `PRODUKTION`/`PRODSCHRITTE`-Kette.
- **AOI-Testintegration** (Automated Optical Inspection): `PMESSAOI`,
  `PFEHLERAOI`, `PFEHLERAOIFILES`, `PRODFEHLERAOI`, `PRODFEHLERTESTER`,
  `SNRFEHLER` – Anbindung automatischer optischer Prüfgeräte/Tester an die
  Fertigung, 2011 nicht vorhanden.
- **Aufgaben-/Terminverwaltung**: `TODO`, `TODOLINKS`, `TODOPARAM`,
  `USERTODO`, `USERTODOAKTION`, `CHECKLISTENKOPF`, `CHECKLISTENTODO`,
  `TERMINE`, `TERMINPROTOKOLL`, `OBJEKTTERMINE`.
- **Zertifikate/Qualität/Regulatorik**: `ZERTIFIKATE`, `ZERTI_QUALI`,
  `ZERTIQUALICROSS`, `NORMROHS` (RoHS-Konformität) – bestätigt die bereits
  dokumentierte Vermutung, dass regulatorische Felder erst nach 2011 kamen,
  jetzt mit konkreter Tabelle statt nur den XRechnung/Gelangensbestätigung-Funden.
- **Historisierung**: `BELEGHISTORY`, `BELEGPOSHISTORY`, `DATUMHISTORY` –
  anders als bisher angenommen ("keine Audit-Trail-Tabellen gefunden") gibt es
  inzwischen doch eine Änderungshistorie, nur eben erst nach 2011 eingeführt.
- **Multi-Währung/Zahlung**: `WECHSELKURSE`, `BANKEN`, `TEILZAHLUNG`.
- **Artikel-Ergänzungen**: `ALTERNATIVARTIKEL` (Substitutionsartikel),
  `ARTLIEFERFREIGABE` (Lieferantenfreigabe je Artikel), `HERSTELLERALIAS`,
  `ADRESSBEWERTUNG`, `ADRGESAMTRABATTE`.
- **Jahres-Schnappschusstabellen statt echter Historie**: pro Jahr neu
  angelegte, im Namen datierte Tabellen (`INVENTUR020111201` …
  `INVENTUR020251215`, `PROD020111201` … `PROD020251215`,
  `LAGERPAH_241217`/`LAGERPIR_241217`/`LAGERPSZ_241217` usw.) – die
  Jahresinventuren werden offenbar manuell per neu erstellter Tabelle
  eingefroren statt in einer versionierten/historisierten Struktur
  gespeichert.

### Views bestätigen bisher aus `strings` vermutete Join-Ketten

```sql
CREATE VIEW V_PRODMATERIAL (...) AS
select P.OID, P.KW, P.Jahr, P.Menge, P.Fertig, P.Status,
  A.OID, A.Nummer, P.Beginndatum, A.name1, A.Adrnr, A.Liefertermin,
  S.Nummer,
  M.Artoid, M.Artnr, M.Bezeichnung1, M.Bezeichnung2,
  M.Anzahl, M.Sollmenge, M.Buchmenge,
  M.einheitmenge, M.ASOID, M.OID, M.Zelle
from Produktion P
  join Beleg A on A.OID = P.AuftragOID
  join Stuecklisten S on S.oid = P.Artoid
  left join Prodartikel M on (m.Soid = P.OID);

CREATE VIEW V_BEREITMATERIAL (...) AS
select P.OID, P.KW, P.Jahr, P.Menge - coalesce(P.Uebernommen, 0),
  A.OID, A.Nummer, A.name1, A.Adrnr, A.Liefertermin,
  S.Nummer, S.OID,
  M.Artoid, M.Artnr, M.Bezeichnung1, M.Bezeichnung2,
  M.Anzahl, M.ASOID, NoSplit
from ProduktionBereit P, Beleg A, Stuecklisten S, Stuecklistenartikel M
where (P.Status is null or P.Status > -1)
  and S.OID = M.Soid and S.OID = P.ArtOID and A.OID = P.AuftragOID;
```

`V_BEREITMATERIAL` bestätigt außerdem einen bisher nicht dokumentierten
Rechenschritt: "bereite Menge" ist nicht die geplante Menge, sondern
`Menge - coalesce(Uebernommen, 0)` – also die geplante Produktionsmenge
abzüglich bereits kommissionierter/übernommener Menge.

### Stored-Procedure-Quelltexte: `isql -a` liefert nur Stubs, echter Code über `rdb$procedure_source`

Auffälligkeit beim Schema-Export: `isql -a` gibt für alle 111 Prozeduren nur
`CREATE PROCEDURE ... AS BEGIN SUSPEND; END` aus – ein Extraktions-Artefakt
dieser isql-Version/-Kombination, nicht ein leerer Prozedurkörper. Bestätigt
über `SELECT OCTET_LENGTH(RDB$PROCEDURE_SOURCE) FROM RDB$PROCEDURES WHERE
RDB$PROCEDURE_NAME = 'P_BESTANDV'` → 344 Bytes vorhanden. Direkter Zugriff via
`SET BLOB ALL; SELECT RDB$PROCEDURE_NAME, RDB$PROCEDURE_SOURCE FROM
RDB$PROCEDURES ORDER BY RDB$PROCEDURE_NAME;` liefert alle echten Quelltexte,
abgelegt unter [`all_procedure_sources.sql`](all_procedure_sources.sql).

Zwei zentrale, bisher nur aus String-Fragmenten vermutete Berechnungen jetzt
vollständig bekannt:

```sql
-- P_BESTANDV: Bestand = Summe aller Lagerbuchungen, Schrott-/Sperrlager ausgenommen
CREATE PROCEDURE P_BESTANDV (AOID INTEGER) RETURNS (BESTAND NUMERIC(15,2)) AS
DECLARE VARIABLE ZUB NUMERIC(15,2);
BEGIN
  SELECT SUM(MENGE) FROM LAGERBUCHUNG
  WHERE ArtOID = :AOID
    AND (LAGEROID IN (SELECT OID FROM Lagerorte WHERE coalesce(art,'0') <> 'S') OR LAGEROID = 0)
  INTO :ZUB;
  IF (:ZUB IS NULL) THEN ZUB = 0; ELSE ZUB = :ZUB;
  BESTAND = ZUB;
  SUSPEND;
END

-- P_BEDARF: Nettoverfügbarkeit = offene Bestellmenge + Bestand - offener Produktionsbedarf
CREATE PROCEDURE P_BEDARF (AOID INTEGER) RETURNS (BEDARF NUMERIC(15,2)) AS
DECLARE VARIABLE ZUB NUMERIC(15,2); DECLARE VARIABLE ABB NUMERIC(15,2); DECLARE VARIABLE BST NUMERIC(15,2);
BEGIN
  SELECT SUM(STCK)-SUM(GELIEFERT) FROM BELEGPOS P, BELEG B
    WHERE B.BELEGART = 105 AND B.OID = P.SOID AND B.ABGESCHLOSSEN <> 'T' AND ARTOID = :AOID
  INTO :ZUB;
  IF (:ZUB IS NULL) THEN ZUB = 0; ELSE ZUB = :ZUB;
  SELECT SUM(SOLLMENGE-BUCHMENGE) FROM PRODARTIKEL A, PRODUKTION P
    WHERE P.OID = A.SOID AND P.STATUS <> -1 AND A.ARTOID = :AOID
  INTO :ABB;
  IF (:ABB IS NULL) THEN ABB = 0; ELSE ABB = :ABB;
  SELECT BESTAND FROM P_BESTANDV(:AOID) INTO :BST;
  IF (:BST IS NULL) THEN BST = 0; ELSE BST = :BST;
  BEDARF = ZUB + BST - ABB;
  SUSPEND;
END
```

`P_BESTANDV` bestätigt: der Bestand ist rein buchungsbasiert (Summe
`LAGERBUCHUNG.MENGE`), nicht aus einer separaten Bestandstabelle gelesen –
passt zu Odoos Stock-Move-Ledger-Prinzip (`stock.move` + berechneter
`stock.quant`), nicht zu einem direkt editierbaren Bestandsfeld. `P_BEDARF`
zeigt, dass "Bedarf" im Altsystem tatsächlich eine **Nettoverfügbarkeit**
ist (kann negativ werden = echter Fehlbedarf, positiv = Überschuss), nicht
ein reiner Bedarfswert – Namensgebung ist irreführend.

Es existieren zehn weitere `P_BESTAND*`-Varianten (`P_BESTANDBLOCK`,
`P_BESTANDMINDEST`, `P_BESTANDNACH`, `P_BESTANDREP`, `P_BESTANDSCHROTT`,
`P_BESTANDSPERR`, `P_BESTANDSPERR2`, `P_BESTANDVNEW`,
`P_BESTAND_MINDESTKONT`) – jeweils Bestandsvarianten für Block-/Mindest-/
Sperr-/Schrottlager, nicht einzeln nachverfolgt, aber vollständiger
Quelltext liegt in `all_procedure_sources.sql` vor.

## Prozess-Modul: als BPM-System gebaut, in der Praxis nur als Aktivitäts-Zeitstempel genutzt (2026-09-08)

Quelle: `HMS/Module/UProzessObjects.pas` (5220 Zeilen, Autor HJE, "ab 11 2012"
laut Kopfkommentar), `HMS/Module/Prozess/FProzessDlg.pas`/`.dfm`, Live-DB.

**Konzept laut Kopfkommentar:**

```
Beschreibung:  - Process überwachung
                 Process-Objekt: Produktion, Auftrag, Kunde, Zeitrahmen,
                 Baugruppe (alle Unterbaugruppen als eigene Processobjekte),
                 MaterialObjekt, PersonalObjekt .....

 Konzept ProzessLink:  Verbindung zwischen Modul, Objektart.... und Zeiterfassung
                       Zeit wird auf Link gestempelt

 Konzept Zeiterfassung:   Auf ProzessLink angestempelt
                          Ablauf:
                          Diff zwischen Beginn (Anwesenheit) und erster Prozess
                          Diff zwischen Prozessen
                          Diff zwischen letzter Prozess und Ende (Anwesenheit)
                          ergibt Prozesszeiten
                          -> Tätigkeiten als Prozess anlegen
```

Die Tabellenstruktur bildet ein vollständiges kleines BPM-System ab:
`PROZESSMAIN` (Prozessdefinitionen: OID/UserID/ProzessID/GruppenID/
Bezeichnung/Beschreibung) → `PROZESSSTRUKTUR` (Teilprozess-Hierarchie:
ParentProzessID/ClientProzessID/Nummer/Sortier/TodoID, mehrfach gleiche
Unterprozesse erlaubt) → `PROZESSABTEILUNGEN` (Abteilungszuordnung) →
`PROZESSOBJEKTE` (generischer Link zu *jedem* Modul-Objekt via
`ModulID`/`ObjektID`, plus `TodoID`) → `PROZESSLINK` (verbindet Prozess +
Objektart + Datum, sortierbar) → `PROZESSZEITEN` (die eigentlichen
Zeitstempel).

**`PROZESSZEITEN.ProjektID` ist ein echter FK auf `KonstSMT.OID`,
bestätigt über eine Report-Query in den Herrmann.exe-Strings:**

```sql
Select Z.Tag, Z.Monat, Z.Jahr, Z.zeit, P.Bezeichnung as Prozess, J.Projektname,
  J.Baugruppe as ProjektNummer
from ProzessZeiten Z
left join ProzessMain P on P.OID = Z.ProzessID
left join KonstSMT J on J.OID = Z.ProjektID
where Z.UserID = :parOID order by Zeit
```

Bemerkenswert: dieselbe Query joint auch `ProzessMain` – obwohl diese
Tabelle laut Live-Datenprüfung oben 0 Zeilen hat. Entweder ist auch dieser
Report-Query-Pfad tot, oder er läuft nur ins Leere (liefert `NULL` für
`Prozess`), ohne zu scheitern. Nicht weiter verfolgt.

Der Typkatalog zeigt den beabsichtigten Umfang – praktisch jede Tätigkeit im
Betrieb sollte als "Prozess" stempelbar sein:

```pascal
TProzessObjektArten = (obaProjekt = 0, obaProzess = 1, obaRep = 2, obaLaufkarte = 3,
  obaAnwesendBeginn = 4, obaAnwesendEnde = 44, obaWartung = 5, obaPruefung = 6,
  obaPause = 88, obaBesprechung = 89, obaSchulung = 90, obaReinigung = 91,
  obaNone = 99, obaAll = 98, obaUser = 97, obaANummer = 50, obaAngebot = 51,
  obaAuftrag = 52, obaBaugruppe = 53, oba8D = 54, obaVue = 55, obaBeleg = 56,
  obaProtokoll = 57);
```

**Live-Datenprüfung (2026-09-08) zeigt: die Definitionsschicht wurde nie
produktiv benutzt.**

```sql
SELECT COUNT(*) FROM PROZESSMAIN;        -- 0
SELECT COUNT(*) FROM PROZESSGRUPPEN;     -- 0
SELECT COUNT(*) FROM PROZESSSTRUKTUR;    -- 0
SELECT COUNT(*) FROM PROZESSABTEILUNGEN; -- 0
SELECT COUNT(*) FROM PROZESSOBJEKTE;     -- 0
SELECT COUNT(*) FROM PROZESSLINK;        -- 1.825
SELECT COUNT(*) FROM PROZESSZEITEN;      -- 355.389
SELECT COUNT(*) FROM WARTUNG;            -- 1
SELECT COUNT(*) FROM PROTOKOLL;          -- 0
```

`FProzessDlg.dfm` (Caption "Prozesse", Grid mit Spalten Bezeichnung/
Beschreibung, Button "Drucken") ist die zugehörige Verwaltungsmaske für
`PROZESSMAIN` – existiert im UI, wird aber laut Datenlage nie benutzt. Auch
das an dieselben Objekte angeschlossene Kalibrierungs-/Wartungs-Subsystem
(`TCustomProzessWartungsValue`: Nummer/Bezeichnung/Messbereich/Fälligkeit/
Kalibrierintervall/Status, mit automatischem Mail-Dämon `TMailProzessWartung`
bei Fälligkeit) hat nur 1 Zeile in `WARTUNG` – ebenfalls praktisch tot.

**Was tatsächlich aktiv ist:** ausschließlich die Zeitstempel-Ebene
`PROZESSZEITEN`, mit klarer Nutzungsschwerpunkt-Verteilung:

```sql
SELECT OBJEKTART, COUNT(*) FROM PROZESSZEITEN GROUP BY OBJEKTART ORDER BY 2 DESC;
-- OBJEKTART=0      156.257   (obaProjekt – generische Projektzeit)
-- OBJEKTART=154    133.636   (identisch mit BELEGART 154 = Reparatur!)
-- OBJEKTART=20001   65.492   (nicht im kleinen Enum – vermutlich Modul-spezifischer Code)
-- OBJEKTART=7591436      2   (Ausreißer/Datenmüll)
-- OBJEKTART=31640052     2   (Ausreißer/Datenmüll)
```

`OBJEKTART=154` fällt sofort auf: das ist derselbe numerische Code wie
`BELEG.BELEGART=154` (Reparatur), an anderer Stelle in diesem Dokument
mehrfach bestätigt – hier offenbar direkt wiederverwendet statt über das
kleine `TProzessObjektArten`-Enum. Damit ist belegt: `PROZESSZEITEN` wird in
der Praxis überwiegend für **Zeitbuchung je einzelnem Reparaturvorgang** und
generische Projektzeit genutzt (zusammen 290k von 355k Zeilen) – eine
feingranulare, tätigkeitsbezogene Ergänzung zur klassischen
Kommt/Geht-Zeiterfassung (`ZEITEN`/`ZEITGRUND`), nicht das ursprünglich in
den Kopfkommentaren beschriebene generische Prozessmodell.

**`PROZESSZEITENK`/`PROZESSZEITENS` sind Migrationsartefakte, kein
eigenständiges Konzept.** `HMS/Module/Parameter/DTextkonstanten.pas` enthält
eine einmalige Datenreparaturroutine:

```pascal
// 1. Daten verschieben
TExecuteSQL.Execute('insert into prozesszeitens select * from prozesszeiten', ...);
ShowMessage('Daten gesichert');
// ... läuft User→Jahr→Monat→Tag durch, korrigiert unvollständige
//     Stempel-Paare (Marker ProzessID=999) in cdsKorrekt2 ...
TExecuteSQL.Execute('Delete from prozesszeiten', ...);
TExecuteSQL.Execute('insert into prozesszeiten select * from prozesszeitenk', ...);
ShowMessage('Update beendet');
```

`ProzessZeitenS` = **S**icherung (Backup der Originaldaten vor der Reparatur),
`ProzessZeitenK` = **K**orrektur (bereinigte Ersatzdaten, danach zurück nach
`PROZESSZEITEN` kopiert). Die nahezu identischen, aber nicht exakt gleichen
Zeilenzahlen (187.031 bzw. 188.528 gegenüber 355.389 in `PROZESSZEITEN`
heute) passen zu diesem Bild: Momentaufnahmen zum Reparaturzeitpunkt,
`PROZESSZEITEN` ist seither weitergewachsen.

**Querverweis Laufkarten:** `TDBLaufkartenObject.NewLaufkarte`
(`UProzessObjects.pas`) erzeugt eine neue Laufkarte über ein internes
`TDBProzessLinkObject` – die bereits im Produktions-Abschnitt dokumentierten
Laufkarten sind technisch also selbst eine `PROZESSLINK`-Instanz, nicht ein
eigenständiger Mechanismus.

## ProjektzeitenHM.exe: eigenständige Stempel-Anwendung schreibt PROZESSZEITEN (2026-09-09)

Quelle: `ProjektzeitenHM.exe` (5,3 MB, Stand 2021-04-13, liegt neben
`Herrmann.exe` in `Herrmann_Work`) – eine vom Hauptprogramm **getrennte**
Delphi-Anwendung, eigene 59 DFM-Forms (per `dfm-tool` extrahiert), eigenes
Icon/Verknüpfung auf dem Desktop. Anders als `Herrmann.exe` löst dieses Exe
SQL nicht serverseitig auf, sondern hat es hart im Client-Code verdrahtet –
dadurch liegt hier zusätzliche, aus Herrmann.exe selbst nicht extrahierbare
Logik offen.

**"HIT" ist der Hersteller, keine Hardware.** `DbConfig.ini` im selben
Ordner referenziert `D:\HIT-Software\Warenwirtschaft\V3.0\Herrmann\DB\IBDB.FDB`
und die Splash-Meldung im Exe lautet `"HIT Software - 1.0 wird geladen..."`
– HIT-Software ist der Hersteller der gesamten Warenwirtschaft, "Herrmann"
der kundenspezifische Instanzname. `TClientDataSetHit` (in allen DFMs dieses
und des Hauptprogramms) ist folglich eine herstellereigene Delphi-Komponente.
Gezielt nach Hardware-Terminal-Anbindung gesucht (COM-Port/Barcode/RFID/
Kartenleser-Strings) – keine Treffer. Gestempelt wird ausschließlich über
UI-Buttons in `TFRMZEITPROJEKTDLG` ("Projektzeiten"): *1. Beginn eintragen →
2. Ende eintragen → 3. Rep./Fert.-Nummer eintippen (→|-Taste) oder Projekt
suchen → 4. Speichern*.

**Manipulationsschutz über Netzwerk-Zeitserver.** Die Form enthält
`IdTime1: TIdTime, Host = '192.100.0.38'` – die Stempelzeit wird von einem
dedizierten internen Zeitserver geholt statt von der lokalen PC-Uhr,
verhindert also Zeitstempel-Manipulation über die Systemuhr.

**Vollständige Spaltenliste für `PROZESSZEITEN`-Inserts, aus dem Exe-Code:**

```sql
Insert into PROZESSZEITEN (OID, FirstID, USERID, ProzessID, ProjektID, ObjektArt,
  Tag, Monat, Jahr, Zeit, Zeit2, Bemerkung, Taetigkeit, Projekt)
  Values (...)
Update Prozesszeiten Set Zeit2 = '...' Where OID = :parOID
Select * from ProzessZeiten where UserID = :parOID and Tag = :parTag
  and Monat = :parMOnat and Jahr = :parJahr and prozessid <> 999
  order by Zeit, prozessID
Delete from ProzessZeiten where FIRSTID = ...
```

`Zeit`/`Zeit2` sind Beginn/Ende desselben Stempel-Paars (Ende wird per
`UPDATE` nachgetragen), `FirstID` gruppiert alle Zeilen einer
Stempel-Session (löschbar als Ganzes). Der Filter `prozessid <> 999`
bestätigt **unabhängig** den bereits oben dokumentierten Fund aus
`DTextkonstanten.pas` ("Marker ProzessID=999" bei der
Stempel-Paar-Korrektur) – hier taucht derselbe Sonderwert in einer
komplett anderen, weiterhin aktiv benutzten Anwendung als Live-Filter auf,
nicht nur in einer einmaligen historischen Reparaturroutine.

**`Mitarbeiterqualicross` – Doppelverwendung, eine davon mit
Ablauflogik:**

```sql
Select S.* from Benutzer B, Konstprodschritte S, Mitarbeiterqualicross C
  where B.OID = C.Masteroid and S.oid = C.clientoid and C.MasterOID = :parUserOID
select S.*, C.Ablaufdatum, C.IsEntry from Benutzer B, Qualifikationen S,
  Mitarbeiterqualicross C where B.OID = :parUserOID and S.oid = C.MasterOID
  and C.clientoid = B.OID
```

Dieselbe Kreuztabelle verknüpft (a) Mitarbeiter↔Produktionsschritt
(`Konstprodschritte`) und (b) Mitarbeiter↔Qualifikation
(`Qualifikationen`) **mit Verfallsdatum** (`Ablaufdatum`, `IsEntry`) – zwei
fachlich unterschiedliche Beziehungen über dieselbe generische Tabelle,
nur über die Zieltabelle im Join unterschieden. Codebestätigte Logik, kein
reiner Verknüpfungs-Zufallsfund.

**`ZeitPerso` – vollständige Feldliste über `cdsKommt`
(`TDMBENUTZERZEITERFASSUNG.dfm`):** `PID, Tag, monat, jahr, datum,
beginn/beginnori, ende/endeori, art, waz, pause, wotag, tagstd, tagmin,
gesmin, Bemerkung, apm, Feiertag, Fehleintrag, Schicht, Schichtsoll` plus
berechnetes `calcPause`. Damit ist der Tabellenname für die klassische
Kommt/Geht-Zeiterfassung jetzt sicher `ZeitPerso` (oben im Prozess-Modul-
Abschnitt noch als "`ZEITEN`" vermutet). Bemerkenswert:
**Original- und Korrekturwert werden parallel gehalten**
(`beginn`/`beginnori`, `ende`/`endeori`) – ein echter Audit-Trail für
nachträgliche Korrekturen, unabhängig von den in `ZEITGRUND` bereits
dokumentierten Zuschlagsfeldern.

**`BENUTZER` als Login-Konto und Personalakte in einem Datensatz.**
`cdsBenutzer` (`TDMBENUTZERZEITERFASSUNG.dfm`) deklariert neben den
bereits als "vermutlich Altlast" eingestuften ~35 Ein-Zeichen-Modul-Flags
(`ADRESSEN`, `ARTIKEL`, `RECHNUNG`, `DBADMIN`, …) auch vollständige
Personaldaten direkt auf demselben Datensatz: `MAGEBDAT`/`MAGEBORT`
(Geburt), `MASTAAT`, `MAFAMSTAND`, `MAKINDER`, `MAKONFESSION`,
`MABANK`/`MABLZ`/`MAKONTO`/`mabic`/`maiban`, `URLAUBGES`/`URLAUBGEN` plus
berechneter Resturlaub (`calcUrlaubRest`). Ergänzt den bereits
dokumentierten Befund "Berechtigung ist der aktive Mechanismus, nicht die
BENUTZER-Flags" (System/Firmendaten-Abschnitt oben) um einen Datenpunkt:
die Modul-Flags sind zumindest strukturell auch in dieser zweiten,
unabhängigen Anwendung noch vollständig verdrahtet, nicht nur im
Hauptprogramm mitgeschleppt.

**Sicherheitsrelevanter Nebenbefund:** Login-Prüfung erfolgt als
Klartextvergleich, kein Hash: `Select OID from Benutzer where Login =
:parLogin and Pw = :parPW and Coalesce(Aktiv, 'F') = 'T'`.

## Stückliste: Kopf-Zahlenfelder "22094"/"110376" sind interne OIDs (2026-09-08)

DFM-Ausschnitt aus `TFRMSTUECKLISTENTSP.dfm.txt`, direkt neben dem
Nummernfeld der Stückliste:

```
object dbeNummer: TDBEdit
  DataField = 'NUMMER'
  DataSource = 'dsStueckliste'
end
object dbeoid: TDBEdit
  Left = 736  Top = 12  Width = 53
  Color = 14802903
  DataField = 'OID'
  DataSource = 'dsStueckliste'
  ReadOnly = True
end
object dbesoid: TDBEdit
  Left = 796  Top = 12  Width = 53
  Color = clWhite
  DataField = 'Artoid'
  DataSource = 'dsStueckliste'
end
```

Zwei schreibgeschützte Felder unmittelbar rechts neben der eigentlichen
Stücklisten-Nummer: `dbeoid` = `STUECKLISTEN.OID` (die interne ID des
Stücklisten-Datensatzes selbst), `dbesoid` = `STUECKLISTEN.ARTOID` (die
interne ID des verknüpften Artikels). Live-DB-Abgleich bestätigt den
Wertebereich:

```sql
SELECT MIN(OID), MAX(OID) FROM STUECKLISTEN;  -- 126 .. 22758
SELECT MIN(OID), MAX(OID) FROM ARTIKEL;       -- 52801 .. 114927
```

Beide im Screenshot beobachteten Zahlen ("22094" für das erste, "110376" für
das zweite Feld) liegen exakt in diesen Wertebereichen – reine technische
OID-Anzeige zur internen Referenz/zum Debugging, keine fachliche Bedeutung.

## Herrmann.dpr: der überwiegende Quellcode liegt außerhalb von `Herrmann_Work` (2026-09-08)

`HMS/Module/Herrmann.dpr` ist die tatsächliche Hauptprojektdatei. Ihre
`uses`-Klausel referenziert jede Unit über einen expliziten relativen Pfad:

```pascal
uses
  FAdressen in '..\Standard\Module\Adressen\FAdressen.pas' {frmAdressen},
  ...
  DServer in '..\..\..\..\ERP-Software\D2000\V0.0\Server\DServer.pas' {dmServer: TDataModule},
  UArtikelObject in '..\..\..\..\ERP-Software\D2000\V0.0\UArtikelObject.pas',
  UDBWorkObjects in '..\..\..\..\ERP-Software\D2000\V0.0\UDBWorkObjects.pas',
  UBelegObject in '..\..\..\..\ERP-Software\D2000\V0.0\UBelegObject.pas',
  ...
```

Ausgezählt: **195 von 196** `in '...'`-Pfadangaben zeigen auf
`..\..\..\..\ERP-Software\D2000\...` (Unterordner `V0.0`, `V3.1\ZeroVersion`,
`V4.0`) – aufgelöst von `HMS/Module/Herrmann.dpr` aus vier Ebenen nach oben,
also `<Herrman Work Test-Elternordner>\ERP-Software\D2000\...`. Dieser
Ordner **existiert auf diesem Rechner nicht**:

```bash
$ find "/c/Users/waldemar.toews/Desktop" -maxdepth 1 -iname "ERP-Software"
# (kein Treffer)
```

Nur eine kleine Minderheit der Units (`FAdressen`, `DAdressen`,
`FGruppenDialog`, `FBenutzer`, `FTextbau`, `UArtikelObjectTSP` u. a.) liegt
über lokale Pfade (`..\Standard\Module\...` bzw.
`Module\Global\GlobalObjects\...`) tatsächlich innerhalb von
`Herrmann_Work`.

**Konsequenz für die beiden dokumentierten `UArtikelObject.pas`-Kopien**
(`HMS/Module/UArtikelObject.pas`, 2017, größer; `HMS/Module/Global/
GlobalObjects/UArtikelObject.pas`, 2014, kleiner): Die `.dpr` referenziert
**keine von beiden** – die tatsächlich aktive Quelle liegt laut Projektdatei
unter `ERP-Software\D2000\V0.0\UArtikelObject.pas`, einem hier nicht
vorhandenen Pfad. Dasselbe gilt unverändert für `UBelegObject.pas` und
`UDBWorkObjects.pas`. Beide lokal vorhandenen Kopien sind damit als
verwaiste/frühere Zwischenstände einzustufen (vermutlich Reste eines
Refactoring-/Migrationsversuchs), nicht als "die eine aktive Version" zu
identifizieren.

**Einordnung für alle bereits gelesenen Formular-Quelldateien** (F8D.pas,
FAuftragTSP.pas, FBestellungTSP.pas, FProduktion.pas, FLieferscheinTSP.pas,
FRechnungTSP.pas, FMitarbeiterZeiterfassung.pas): diese liegen zufällig
*zusätzlich* lokal unter `HMS/Module/...` vor (sonst wären sie über den
gegebenen Zugriff gar nicht lesbar gewesen) – die `.dpr` bestätigt aber nicht,
dass exakt diese lokalen Kopien dem produktiv gebauten Stand entsprechen.
Die dort gewonnenen Erkenntnisse bleiben verlässlich, weil sie im Rahmen
dieser Recherche jeweils zusätzlich gegen DFM (UI-Struktur) und/oder Live-DB
(Datenwerte) gegengeprüft wurden – reiner Pascal-Code-Fund ohne
Zweitquelle wäre ab jetzt mit dieser Einschränkung zu lesen.

## Zeiterfassung: Zuschlagsformel geklärt – nur Minutenzählung, kein Prozentsatz (2026-09-08)

`HMS/Module/Zeiterfassung/UConstsZeit.pas` definiert die Zeitfenster:

```pascal
ZeitNachtBeginn = '01.01.2000 22:00';
ZeitNachtEnde = '01.01.2000 06:00:00';
ZeitSpaetBeginn = '01.01.2000 14:00:00';
ZeitSpaetEnde = '01.01.2000 22:00:00';
ZeitSpaetZuschlagBeginn = '01.01.2000 20:00:00';
ZeitSpaetZuschlagEnde = '01.01.2000 23:59:59';
```

`HMS/Module/Zeiterfassung/UZeitenWork.pas` (`TWorkTimeObject`) berechnet daraus
ausschließlich Minutenwerte, keine Prozentsätze oder Euro-Beträge:

```pascal
function TWorkTimeObject.GetFeiertagszeit: Integer;
begin
  ...
  if FFeier = 'J' then
  begin // Fallunterscheidung über Nacht
    if IsUeberNacht = True then
      FFeierTagMinuten := Round((StrToTime('23:59:59') - StrToTime(ABeginnZeit)) * 24 * 60);
  end
  else if IsUeberNacht = True then
  begin
    // Prüft, ob der FOLGETAG ein Feiertag ist (Beginn Werktag, Ende Feiertag)
    ANextDayTimeObject.GetFeiertag;
    if ANextDayTimeObject.FFeier = 'J' then
      FFeierTagMinuten := FFeierTagMinuten + Round((StrToTime(AEndeZeit)) * 24 * 60);
  end;
  Result := FFeierTagMinuten;
end;

function TWorkTimeObject.GetSonntagszeit: Integer;
begin
  ...
  if Wochentag = 'So' then
    FSonnMinuten := Round(StrToTime(AEndeZeit)*24*60) - round(StrToTime(ABeginnZeit)*24*60) - 1
  ...
end;
```

Die resultierenden Properties (`Nachtminuten`, `SonnMinuten`,
`FeiertagsMinuten`) werden **an keiner Stelle im gesamten `HMS`-Baum**
weiterverarbeitet (keine Treffer für `.Nachtminuten`/`.SonnMinuten`/
`.FeiertagsMinuten` außerhalb ihrer eigenen Definition in
`UZeitenWork.pas`) – sie dienen ausschließlich der Anzeige/dem Export, nicht
einer internen Lohnberechnung.

Die Tabelle `ZEITGRUND` hat dennoch eigene, dafür augenscheinlich vorgesehene
Spalten:

```sql
CREATE TABLE ZEITGRUND (OID D_OID, WAZ D_DOUBLE, PAUSEREG D_DOUBLE, RAUSE9 D_DOUBLE,
  SONNZUSCHLAG D_DOUBLE, FEIERZUSCHLAG D_DOUBLE, NACHTZUSCHLAG D_DOUBLE,
  MAZ D_DOUBLE, MOAZ D_DOUBLE, MOPAUSE D_DOUBLE, ... (je Wochentag AZ/PAUSE) ...
  PID INTEGER, URLAUB CHAR(12), ...);
```

Live-Datenprüfung (2026-09-08, 99 Zeilen):

```sql
SELECT COUNT(*) FROM ZEITGRUND WHERE SONNZUSCHLAG IS NOT NULL;   -- 0
SELECT COUNT(*) FROM ZEITGRUND WHERE FEIERZUSCHLAG IS NOT NULL;  -- 0
SELECT COUNT(*) FROM ZEITGRUND WHERE NACHTZUSCHLAG IS NOT NULL;  -- 0

SELECT FIRST 3 PID, WAZ, PAUSEREG, MOAZ, MOPAUSE, URLAUB FROM ZEITGRUND;
-- PID=1: WAZ=40.0, URLAUB=30   (regulär befüllt)
-- PID=6: WAZ=40.0, PAUSEREG=0.5, URLAUB=30
```

**Schlussfolgerung:** Die drei Zuschlagsspalten existieren im Schema, sind
aber in der produktiven Nutzung komplett ungenutzt (0 von 99 Zeilen befüllt),
während benachbarte Konfigurationsfelder derselben Tabelle normal gepflegt
werden. Zusammen mit dem Code-Befund (Minutenzählung ohne
Weiterverarbeitung) belegt das zweifelsfrei: die Sonn-/Feiertags-/
Nachtzuschlagsberechnung (Minuten × Prozentsatz = Euro) ist **kein
Bestandteil des ERP**, sondern läuft extern (Lohnbüro/Payroll-Software), die
vermutlich die exportierten Rohminuten als Eingabe nutzt.

## Rechnung: "Vertreterprovision1Click" ist ein Label/Code-Mismatch (2026-09-08)

`HMS/Module/Belege/FRechnungTSP.pas`, Zeile 423:

```pascal
procedure TfrmRechnungTSP.Vertreterprovision1Click(Sender: TObject);
var
  ABelegArtObject: TBelegArtObject;
begin
  inherited;
  ABelegArtObject := TFrmlieferscheinDlg.Execute(DataModul.GetCDSController,
    DataModul.cdsBelegPosRefOID.AsInteger);
  if ABelegArtObject.FBelegOID > 0 then
    FormController.Show(ABelegArtObject.FBelegart, TOIDParam.Create(ABelegArtObject.FBelegOID));
  ABelegArtObject.Free;
end;
```

Der Methodenname (und damit der Delphi-Komponentenname `Vertreterprovision1`)
suggeriert Provisionslogik. Die DFM zeigt aber die tatsächliche Beschriftung:

```
object Vertreterprovision1: TMenuItem
  Caption = 'Belege zeigen'
  OnClick = 'Vertreterprovision1Click'
end
```

`TFrmlieferscheinDlg` (`HMS/Module/Belege/FLieferscheinDlg.pas`) ist ein
generischer "zeig mir die verknüpften Belege/Lieferscheine zu dieser
Position/diesem Artikel"-Dialog – exakt derselbe Aufruf-Pattern findet sich
in `FAuftragTSP.pas:647` und `FAuftragH.pas:640` (dort mit `cdsBelegPosOID`
statt `cdsBelegPosRefOID`), wo er unzweifelhaft der Belegnavigation dient,
nicht der Provisionsberechnung.

**Schlussfolgerung:** Kein funktionaler Bug, sondern ein reines
Namens-Artefakt – vermutlich wurde der Menüpunkt aus einem anderen Formular
kopiert und nur die Caption angepasst, nicht der Komponentenname. Reiht sich
ein in dasselbe wiederkehrende Muster wie `tsh8dl`/"Belastungsanzeige":
UI-Beschriftung im Lauf der Zeit geändert, interner Code-Identifier nicht
nachgezogen. Die eigentliche Vertreterprovisions-Logik (`ProvPos`,
`BELEGPOS.PROVISION`, `ADRESSEN.PROVISION`/`PROVISION2`) ist bereits an
anderer Stelle in diesem Dokument belegt (Abschnitt Vertreterabrechnung).

## Reproduktion

```bash
strings -n 4 Herrmann_Work/Herrmann.exe > exe_strings_ascii.txt
strings -n 4 -e l Herrmann_Work/Herrmann.exe > exe_strings_unicode.txt
grep -in "xrechnung\|leitweg\|peppol\|gelangen" exe_strings_ascii.txt exe_strings_unicode.txt
```

### Reproduktion (Live-DB-Zugriff, Option C)

```bash
# x86 Firebird-2.5.9-Embedded-Engine (identisch zur 2011er-DB-Auswertung)
isql.exe "C:\...\Herrman Work Test\IBDB.FDB" -user SYSDBA -password masterkey

# Vollschema-Export
isql.exe <db> -user SYSDBA -password masterkey -a -o full_schema_current.sql

# Stored-Procedure-Quelltexte (isql -a liefert hier nur Stubs!)
SET BLOB ALL;
SELECT RDB$PROCEDURE_NAME, RDB$PROCEDURE_SOURCE
FROM RDB$PROCEDURES ORDER BY RDB$PROCEDURE_NAME;
```
