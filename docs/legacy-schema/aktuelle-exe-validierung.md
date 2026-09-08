# Validierung gegen die aktuelle Herrmann.exe (Stand 2026-09-06)

Belege für die "Validiert 2026-09-08"-Vermerke in
[`../erp-odoo-modulvergleich.md`](../erp-odoo-modulvergleich.md). Extrahiert per
`strings -n 4` (ASCII) und `strings -n 4 -e l` (UTF-16LE) auf
`Herrmann_Work/Herrmann.exe` (06.09.2026) – kein Quellcode, nur eingebettete
Strings/SQL-Fragmente aus dem kompilierten Binary.

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
