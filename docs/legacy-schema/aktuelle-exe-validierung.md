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
