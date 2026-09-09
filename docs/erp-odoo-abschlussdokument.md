# Abschlussdokument: Feldkatalog mit Info-/Verknüpfungs-/Logik-Klassifikation

Zusammenfassung des gesamten Reverse-Engineering (Sept. 2026) aus
[`erp-odoo-modulvergleich.md`](erp-odoo-modulvergleich.md) und
[`legacy-schema/aktuelle-exe-validierung.md`](legacy-schema/aktuelle-exe-validierung.md),
neu geordnet nach einer dritten Dimension: **welche Rolle spielt ein Feld
technisch**, nicht nur "wie heißt das Odoo-Äquivalent".

## Die drei Kategorien

| Kategorie | Bedeutung | Kriterium für diese Einstufung |
|---|---|---|
| **Info** | Reine Speicherung, keine bekannte Downstream-Wirkung | Default – alles, was nicht nachweislich verknüpft oder logiktragend ist |
| **Verknüpfung** | Referenz auf einen anderen Datensatz/eine andere Tabelle | Echter Fremdschlüssel (OID) **oder** Nummer-/String-basierter Verweis **oder** Live-Join/View |
| **Logik** | Löst Code-Verzweigung, Berechnung, Gate oder automatisiertes Verhalten aus | Nur vergeben, wenn ein Pascal-Codepfad, eine Stored-Procedure-Bedingung oder ein bewiesenes Gate gefunden wurde – **nicht** bei bloß plausiblen Flags ohne Codebeleg |

**Wichtige Einschränkung:** Diese Klassifikation ist nur so vollständig wie
die zugrundeliegende Recherche. Sie deckt die Felder ab, die in den beiden
Quelldokumenten bereits einzeln geprüft wurden – überwiegend Stammdaten
(Adressen, Artikel, Stückliste) und die zentralen Belegflüsse (Einkauf,
Produktion, Vertrieb, Reparatur, System/Firmendaten, Prozess-Modul). Die
243 seit 2011 neu hinzugekommenen Tabellen (siehe Live-DB-Abschnitt in
`erp-odoo-modulvergleich.md`) sind bis auf die dort explizit genannten
Ausnahmen (Prozess-Modul) **nur auf Schemaebene bekannt, nicht klassifiziert**
– für sie liegt keine Codebestätigung vor, ob ein Feld Info, Verknüpfung
oder Logik ist.

Wo die Kategorie nicht codebestätigt, sondern nur plausibel ist, steht ein
`(?)` dahinter – konsistent mit den Unsicherheits-Vermerken in den
Quelldokumenten.

---

## Adressen

### Suchmaske

| Feld | DB-Feld | Kategorie | Anmerkung |
|---|---|---|---|
| Name 1/2/3, Kurzname, Strasse, Plz, Ort | `ADRESSEN.NAME1-3`/`STRASSE`/`PLZ`/`ORT` | Info | |
| Debit.-Nr. / Kredit.-Nr. | `ADRESSEN.DEBNR`/`KREDNR` | Info | vermutlich UI-Ableitung für "Art" (?), nicht codebestätigt |
| Gruppe / Nr. | `ADRESSEN.GRUPPE`-Referenz | Verknüpfung | ReadOnly, nur über Auswahl-Button befüllbar |
| Ansprechpartner | eigene Tabelle je Adresse | Verknüpfung | 1:n |
| "Adressen Filtern" (Checkbox) | kein Datenfeld | Logik | reine Sucheinstellung |
| "Sortierung" (Radiobuttons) | kein Datenfeld | Logik | bestimmt, welches der acht Felder als aktiver Suchschlüssel dient |
| "letzte Suche" | kein Datenfeld | Logik | wiederholt letzte Suchausführung |

### Detailmaske "Allgemein"

| Feld | DB-Feld | Kategorie | Anmerkung |
|---|---|---|---|
| Nummer | interne ID | Verknüpfung | |
| Anlage/Änderung | Systemdatum | Info | |
| Anrede Firma/Person | `ADRESSEN.ANREDE`-Typ | Info | |
| Art: Kunde/Lieferant | kein eigenes Feld gefunden | Logik (?) | vermutlich aus `DEBNR`/`KREDNR`-Belegung UI-seitig abgeleitet, nicht im Datenmodell erzwungen |
| Postfach/PostfachPlz | `ADRESSEN.POSTFACH`/`POSTFACHPLZ` | Info | |
| Ansprechpartner-Funktion | `ADRESSENANSPRECH.NOTIZ` (wiederverwendet) | Info | Dropdown aus `Select distinct Notiz` |
| Lkz | `ADRESSEN.LKZ`-Feld | Verknüpfung | Ländercode-Referenz |
| Etikette (Checkbox) | `ADRESSEN`-Flag | Logik (?) | vermutlich Druck-/Etikettensteuerung |
| inaktiv (Checkbox) | `ADRESSEN`-Flag | Logik | Statusflag, semantisch ≠ Odoo `active` |
| gesperrt (Checkbox) | `ADRESSEN`-Flag | Logik (?) | vermutlich Liefer-/Bestellsperre, analog `SPERRE` bei Artikel |
| nicht bewerten (Checkbox) | `ADRESSEN.BEWERTEN` | Logik | **codebestätigt**: `coalesce(A.Bewerten,'F')` als Gate in Bestell-/Lieferquoten-Queries |
| ist Vertreter (Checkbox) | `ADRESSEN.ISVERTRETER` | Logik | treibt `V_Vertreter`-View/Provisionsberechnung |
| Buyer Ref. / unsere Nummer bei Kunde | `ADRESSEN`-Felder | Info | |
| Fon/Fon2/Fax/Mobil | `ADRESSEN.FON1`/`FON2`/`FAX`/`MOBIL` | Info | |
| E-Mail-Adressen (Zentral/Rechnung/Vertrieb/Einkauf/GL/Info) + CC/BCC | `EMail`/`EmailBuchhaltung`/`EMailVT`/`EmailEK`/`EmailGL`/`EmailInfo` + `*CC`/`*BCC` | Info | reine Adressdaten |
| Versand-Flags `MailAngebot`/`MailAuftrag`/`MailLieferschein`/`MailRechnung`/`MailBestellung` | `ADRESSEN`-Flags | Logik | steuern automatischen Mailversand je Belegtyp |
| Rechnungskopie-Routing `RechCopyAll/Norm/VT/Fibu/Opos` | `ADRESSEN`-Flags | Logik | steuern, wer Rechnungskopien erhält |
| WWW | `ADRESSEN.WWW` | Info | |
| LeitwegID / BuyerRef (XRechnung) | `ADRESSEN.LEITWEGID`/`BUYERREF` | Info | |
| Xemail / Xrech-Flags | `ADRESSEN`-Flags | Logik | steuern, ob `XRechnung.exe` extern aufgerufen wird |

### Reiter "Sonstiges" / "Kartei"

| Feld | DB-Feld | Kategorie | Anmerkung |
|---|---|---|---|
| Bemerkung | `ADRESSEN.BEMERKUNG` | Info | |
| Bedingungen Lieferant/Kunde | `ADRESSEN.ZKONDI`/`VERSAND` | Verknüpfung | Referenz auf Konditionswerte |
| Bedingungen Herrmann | `ADRESSEN.ZKONDIL`/`VERSANDL` | Verknüpfung | eigene, zweite Konditionsreferenz |
| Liefertage (7 Checkboxen) | `ADRESSEN.LIEFERTAGE` | Info | ein positionscodierter String |
| Lieferadressen-Grid | `ADRESSENLIEFER` | Verknüpfung | 1:n |
| Kartei (Preis-/Bestellhistorie) | Live-Join `BELEG`+`BELEGPOS` | Verknüpfung | nicht gespeichert, jedes Mal neu berechnet |

---

## Artikel

### Kernfelder (Addon-Vergleich)

| Feld | DB-Feld | Kategorie | Anmerkung |
|---|---|---|---|
| Artikelnummer, Kurzbezeichnung, Bestellnummer, Einheit | `ARTNR`/`KURZBEZEICHNUNG`/`BESTELLNR`/`EINHEIT` | Info | |
| Hauptlieferant | `ARTIKEL.HAUPTLIEFERANT` | Verknüpfung | FK auf `ADRESSEN.OID` – im `int_legacy_erp_import`-Addon fälschlich als `Char` statt `Many2one` modelliert |
| Gruppe | `ARTIKEL.GRUPPE` | Verknüpfung | FK auf `ARTIKELGRUPPEN.GID` – gleicher Addon-Fehler |
| Hersteller-Ident-Codes BT/LH/FY/…/SI | `ARTIKEL.IDENTNR1-12` | Info | reine Kennzeichnungswerte |

### Weitere Tabs

| Feld/Block | DB-Feld | Kategorie | Anmerkung |
|---|---|---|---|
| Bestand verfügbar/Bestellt/Bedarf Prod.Auftrag/Fertigung offen/Auftrag ges. | `dsInfoBestand`-Computed-Felder, gespeist über `P_Bestand`/`P_BestandV` | Logik | live berechnet, kein Rohfeld |
| WAMONAT/WAJAHR/WEMONAT/WEJAHR, GEWICHT/VOLUMEN, TEILEART/WARENSCHLUESSEL, KUPFERZAHL/EDELMETALLZAHL | direkte `ARTIKEL`-Felder | Info | |
| VERSCHLEISSTEIL/ERSATZTEIL/QSPFLICHT/AOFTEST/FUNKTIONSTEST (Flags) | `ARTIKEL`-Booleans | Info | plausible Gates für QS-/Ersatzteilprozesse, aber nicht codebestätigt |
| Inventurbestand | `ARTIKEL.BESTAND` (wiederverwendet) | Info | |
| Zeugnistext (EK) | `ARTIKEL.Zeugnistext` | Info | erst später ergänzt |
| USt.-Satz | `ARTIKEL.MWST` | Logik | steuert MwSt-Berechnung, 4 Werte (Voll/Halb/Ohne/Dupo) |
| Einkauf/Verkauf-Preis | `EKNETTO`/`VKNETTO` | Info | |
| VK Brutto | Computed (`calcVPBrutto`) | Logik | berechnet aus Netto+MwSt |
| kein Preisupdate (Checkbox) | `ARTIKEL.noAutoUpdate` | Logik | schaltet automatische Preisaktualisierung ab |
| alter Wert / Letzter RP | `dsInfoBestand`-Computed | Logik | live aus Bestellhistorie abgeleitet |
| Lieferantenpreis-Grid (15 Spalten) | `ARTIKELPREISE` | Verknüpfung | 1:n je Lieferant |
| Lager-Bestände (links) | `SUM(LAGERBUCHUNG.MENGE)` je Standort | Logik | live aggregiert, kein gespeicherter Wert |
| `LAGERORTE.ART='S'` | `LAGERORTE.ART` | Logik | **codebestätigt** (`P_BESTANDV`): schließt Schrott-/Sperrlager von der Bestandsberechnung aus |
| Lagerplätze-Grid (rechts) | `LAGERPLAETZE`+`LAGERPLATZCROSS` | Verknüpfung | Bin-Level-Zuordnung mit Menge |
| Kupferzuschlag/m | `ARTIKEL.KUPFERZAHL`/`KUPFERFAKTOR` | Logik | **codebestätigt** über `TGetKupferZuschlag`-Prozedur |
| ARTIKEL.STUECKOID | Verknüpfung | Verknüpfung | FK auf `STUECKLISTEN.OID`, steuert Sichtbarkeit des "Fertigungsteil"-Links |
| ARTIKEL.SPERRE | `ARTIKEL.SPERRE` | Logik | **codebestätigt** (`P_ARTDIREKTSTATUS`): blockiert Direktlieferanten-Status |

### Stückliste (BOM)

| Feld | DB-Feld | Kategorie | Anmerkung |
|---|---|---|---|
| Melden/Freigegeben AV/Freigegeben GL/geprüft | `STUECKLISTEN`-Flags | Logik (?) | plausible Freigabe-Gates, nicht einzeln codebestätigt |
| Ausg./Status/Abmessung | `AUSG`/`STATUS`/`ABMESS` | Info | |
| ID-Nummer (BT/LH/…) | `IDENTNR1-12` | Info | Spiegelung zu `ARTIKEL` |
| Zustand Z./S. | `AUSGZ`/`AUSGST` | Info | |
| Bearb./Gepr./Freig. (2 Zeilen) | `B1`/`G1`/`F1`, `B2`/`G2`/`F2` | Info | Sign-off-Initialen |
| Änd./Datum | `STUECKLISTEN.ANLAGE` (wiederverwendet) | Info | |
| Material-Grid | `STUECKLISTENARTIKEL` | Verknüpfung | echte BOM-Zeilen |
| Kopf-OIDs ("22094"/"110376") | `STUECKLISTEN.OID`/`.ARTOID` | Verknüpfung | reine interne ID-Anzeige, ReadOnly |
| keine Splittung (Checkbox) | `STUECKLISTEN.NOSPLITT` | Logik | steuert Splitt-Verhalten bei Produktionsstart |
| SCHRITTZEIT1-7/RUESTZEIT1-7 | `STUECKLISTEN`-Felder | Logik | Routing-Zeitdaten, fließen in Produktionsplanung |

---

## Einkauf/Bestellung

| Feld | DB-Feld | Kategorie | Anmerkung |
|---|---|---|---|
| `BELEG.BELEGART` | `BELEG.BELEGART` | **Logik** | zentraler Diskriminator – bestimmt, ob ein Beleg als Bestellung(105)/Rahmenbestellung(74)/Anfrage(118)/… behandelt wird |
| `BELEG.NUMMER`/`BELEGDATUM`/`ADROID` | direkte Felder | Info/Verknüpfung | `ADROID` = FK auf Lieferant |
| `BELEG.BEARBEITER`+Kontaktfelder | Info | Info | redundant zum Benutzerprofil |
| `BELEG.LIEFERTERMIN`/`BESTELLTERMIN`/`WUNSCHTERMIN` | Info | Info | drei parallele Termine, kein Odoo-Pendant |
| `BELEG.RAHMENNR`/`ABRUFMENGE`/`ABRUFARTIKEL`/`ABRUFPREIS`/`KONTRAKT` | Rahmenbestellungs-Felder | Verknüpfung | Abruf-gegen-Kontrakt-Modell |
| `BELEGPOS.RAHMENOID` | `BELEGPOS.RAHMENOID` | Verknüpfung | verknüpft Bestellposition mit Rahmenbestellung, Restmenge live nachgerechnet (nicht gespeichert) |
| `BELEGPOS.ARTOID`/`ARTNR`/`STCK`/`EPREIS` | Kernfelder | Verknüpfung/Info | `ARTOID` = FK |
| `BELEGPOS.GELIEFERT` | Info | Info | |
| `BELEGPOS.GEPRUEFT`/`RECHFREIGABE` | Flags | Logik | **codebestätigt** (`FBestellungTSP.pas`, `btnBuchenClick`): blockieren die Wareneingangsbuchung bei prüfpflichtigen Artikeln |
| `BELEGPOS.ZEUGNIS` | Flag | Logik | **codebestätigt**: gleiches Gate wie `GEPRUEFT` bei zeugnispflichtigen Artikeln |
| `BELEGPOS.REPLAGER` | Flag | Logik | **codebestätigt**: schaltet auf separaten Buchungspfad `TBucheKanbanArtikel.ExecuteReplager` um |
| `dbeAusschuss` (Ausschussmenge) | `BELEGPOS`-Feld | Logik | **codebestätigt**: > 0 löst automatisch `CreateBelastungsAnzeige` ("8D Lieferant") + Excel-Export aus |
| `BELEGPOS.RGNRLIEF`/`RGNRINTERN` | Info | Info | Rechnungsnummer je Position statt je Beleg |
| `BELEGPOS.BESTTERMIN`/`BESTBEMERK` | Info | Info | |

---

## Produktion

| Feld | DB-Feld | Kategorie | Anmerkung |
|---|---|---|---|
| `KONSTPRODART`/`KONSTPRODSTRASSEN`/`KONSTPRODSCHRITTE`/`KONSTPRODMASCHINEN` | Vorlagen-Tabellen | Verknüpfung | Routing-Vorlagen, referenziert von `PRODUKTION` |
| `PRODUKTION.STATUS` | `PRODUKTION.STATUS` | Logik | **codebestätigt** (`P_BEDARF`, EngpassCockpit-Query): `STATUS=-1` filtert aktiv aus Bedarfs-/Verfügbarkeitsberechnung heraus |
| `PRODUKTION.KW`/`JAHR` | `PRODUKTION`-Felder | Info | **codebestätigt** (`FProduktion.pas`, `actInFertigungExecute`): Ergebnis einer echten Werktage-Rückwärtsterminierung, keine freie Eingabe |
| EngpassCockpit-Zähler (`CountBPos`/`CountRest`/`CountBestDat`/`CountNotBestellt`/`CountNOAB`/`CountKP`, `CriticPath`, `EKStatus`) | `PRODUKTION`-Spalten | Logik | vorberechnete Status-/Engpasswerte, treiben die Cockpit-Anzeige |
| `KONSTPRODFEHLER.KRITISCH` | Flag | Logik | Fehlerkatalog-Schweregrad |
| `PRODFEHLER.FREI_DURCH`/`FREI_AM` | Freigabe-Felder | Logik | Freigabe-Workflow für erkannte Fehler |
| Laufkarten | kein eigenes Objekt | Verknüpfung | über generischen `BELEG`-Kopf mit variablem `BELEGART`-Parameter gerendert; technisch eine `PROZESSLINK`-Instanz (siehe Prozess-Modul) |
| `BEGLEITSCHEIN.AUSFALLNR` | Feld | Verknüpfung | verweist vermutlich auf `REPAUSFALL` |
| `BELEG.FAMID` | Feld | Verknüpfung | Fertigungsauftragsmappe, dateibasiert (`*_FM.xls`) statt DB-gestützt |

---

## Vertrieb (Angebot/Auftrag/Lieferschein/Rechnung)

| Feld | DB-Feld | Kategorie | Anmerkung |
|---|---|---|---|
| `BELEG.BELEGART` | `BELEG.BELEGART` | **Logik** | derselbe zentrale Diskriminator wie bei Einkauf/Reparatur (100/101/102/103/104/108/115) |
| `BELEG.HAUPTAUFTRAG` | `BELEG.HAUPTAUFTRAG` | Verknüpfung | **codebestätigt** (`FAuftragTSP.pas`, `btnInsertClick`): Selbstreferenz bei Neuanlage, Belegnummer-basiert statt OID-FK |
| `BELEG.ABGESCHLOSSEN` | Flag | Logik | Gate in mehreren Übergängen (Lieferschein→Rechnung, Rahmenbestellungs-Abschluss) |
| `DataModul.AllPreisGeprueft` | berechneter Wert über `BELEGPOS.GEPRUEFT` je Position | Logik | **codebestätigt** (`FLieferscheinTSP.pas`, `pmiRechnungClick`): Gate, blockiert Lieferschein→Rechnung |
| `BELEGPOSMAHN` | eigene Tabelle | Verknüpfung | Mahnstufen-Verknüpfung zur Rechnung |
| `BELEGPOS.PROVISION` / `ADRESSEN.PROVISION`/`PROVISION2` | Felder | Logik | fließen in `V_Vertreter`-Provisionsberechnung |
| `FIsInProd`-Prüfung beim Speichern | Laufzeitprüfung | Logik | **codebestätigt** (`FAuftragTSP.pas`, `btnSaveClick`): erzeugt `TSetProdWarning`, wenn eine bereits in Fertigung befindliche Position geändert wird |
| `TEXT=''`-Positionszeilen | Laufzeit-Cleanup | Logik | werden beim Speichern automatisch entfernt, `POSNR` neu vergeben |
| `CopyChangeBelegGutschrift` | Prozedur | Logik | **codebestätigt** (`FRechnungTSP.pas`): erzeugt Gutschrift mit Rückbezug auf `HAUPTAUFTRAG`+Rechnungsnummer |
| "Vertreterprovision1Click" (Menüpunkt) | ruft `TFrmlieferscheinDlg` mit `cdsBelegPosRefOID` | Verknüpfung | **kein** Provisionsfeld – echte Caption "Belege zeigen", zeigt verknüpfte Lieferscheine |

---

## Reparatur (Belegmaske)

| Feld | DB-Feld | Kategorie | Anmerkung |
|---|---|---|---|
| `BELEG.BELEGART=154` | Diskriminator | **Logik** | identifiziert den Beleg als Reparatur, steuert die gesamte `TFRM8D`-Formularlogik |
| `REPKOPF.BELEGNUMMER` | Feld | Verknüpfung | Nummer-basierte Verknüpfung zu `BELEG` (kein FK) |
| `REPAUFTRAG.GERAETID` | Feld | Verknüpfung | FK auf `REPARTIKEL.OID` (Gerätestamm) |
| `REPARTIKEL.GRUPPE` | Feld | Verknüpfung | FK auf `REPGRUPPEN.OID` |
| `BELEG.ABSCHLAGAUFTRAG` (Rahmen) | Feld | Verknüpfung | **codebestätigt** (`btnRahmenClick`): setzt Bezug auf gewählten Rahmen-Beleg |
| `REPKOPF.GEDRUCKT` | Flag | Info | |
| `ADRESSEN.BEWERTEN` | Flag | Logik | (siehe Adressen) |
| `REPKOPF.LIEFSCHNR`/`LIEFSCHDATUM` | Felder | Verknüpfung | Bezug zum Ausgangs-Lieferschein |
| `REPARTIKEL.IDENTNR`/`.BEZEICHNUNG` vs. `REPAUFTRAG.SERIENNR` | Felder | Info | IdentNr = Typ/Modell (modellweit gleich), Seriennr = Exemplar-spezifisch – **codebestätigt über Zwei-Belege-Vergleich** |
| `BELEGPOS.SNRALT`/`SNRNEU` | Felder | Info | Seriennummer je Materialzeile |
| `BELEGPOS.DRUCKEN`/`BUCHEN` (+ `REPKPOS`-Äquivalente) | Flags | Logik | steuern, ob eine Position gedruckt/gebucht wird |
| `BELEG.FAMID`/`RefOID` | Feld | Verknüpfung | **codebestätigt** (`F8D.pas`, `pnlFamClick`): verknüpft Position mit `TFAMObject`-Datensatz |
| `BEGLEITSCHEIN`/`RefOID2` (BGS) | Feld | Verknüpfung | **codebestätigt**: gleicher Mechanismus wie FAM, anderer Typ-Flag |
| `lblFam`/`lblBgs`-Einfärbung | Laufzeitlogik | Logik | **codebestätigt** (`dbcgPosPaintPanel`): grün wenn `RefOID`/`RefOID2` > 0 |
| `BELEGPOS.INDENTNRDRUCK` (DruckID-Nr.) | Feld | Logik | steuert, wie vollständig die Identnummer beim Druck erscheint (Voll/Halb/Ohne) |
| `BELEG.FROMBELEGART` (KVA1/KVA2) | Feld | Logik | **codebestätigt** (`btnAktiv1/2Click`): schaltet zwischen zwei parallelen Kostenvoranschlägen um |
| `BELEG.PUFFERLAGER` | Flag | Logik | **codebestätigt**: Guard, verhindert KVA-Reaktivierung nach Lieferschein-Erzeugung |
| `ADRESSEN.ABWUST` | Feld | Logik | **codebestätigt** (`btnSearchAdrClick`): überschreibt `BELEG.MWSTSATZ` beim Kundenwechsel |
| `BELEG.ENDPRUEFUSER`/`ENDPRUEFDATUM` | Felder | Info | gesetzt über Endprüfung-Button |
| `REPKOPF.KST1-5`/`KFKT1-5`/`KWERT1-5` | Felder | Logik | **codebestätigt** (`dbeefExit`→`TChangeThreeFieldsDB`): Std.×Faktor=Wert, automatisch neu berechnet |
| `REPKPOS.REPLAGER`/`UEBERNAHME` | Flags | Info | eigene Instanz getrennt von `BELEGPOS`-Äquivalenten |
| `REPKOPF.KDLSNR`/`SPEDITION`/`SPEDNR`/`VEDATUM`/`TRANSPORT` | Versand-Eingang-Felder | Info | |
| `REPKOPF.FREI` | Flag | Info | ein Feld für beide Checkboxen "frei"/"unfrei" |
| `REPKOPF.RKM`/`RKMFAKTOR`/`RKMWERT`, `RSTD`/`RSTDFAKTOR`/`RSTDWERT` | Versand-Ausgang-Felder | Logik | km/Std. × Faktor = Wert, gleiches Berechnungsmuster wie Kostenvoranschlag |
| `REPKOPF.TECHNIKER`/`ANREDE`/`RARTIKELNR`/`USTIDENT` (wiederverwendet) | Felder | Info | Meldungs-Nr./Herkunft-Ort/-Einheit/Bezugsnummer – reine Feld-Zweckentfremdung, keine Logik |
| `REPKOPF.AUSFALL`/`FEHLER`/`REPBESCHREIB` | Felder | Info | drei getrennte Erzählperspektiven |
| `InfoDokumente`/`InfoNotizen` (`ModulID`+`ObjektID`) | generische Tabellen | Verknüpfung | anwendungsweiter polymorpher Schlüssel, nicht reparaturspezifisch |
| Reparaturhistorie (Geräte-Info-Tab) | Live-Join `Beleg`/`Repkopf`/`RepAuftrag`/`RepArtikel` | Verknüpfung | nicht gespeichert |

---

## System & Firmendaten

| Feld | DB-Feld | Kategorie | Anmerkung |
|---|---|---|---|
| `BENUTZER`-Flag-Spalten (>50, je Menüpunkt) | Flags | Info | **codebestätigt als Altlast**: keine Lesezugriffe mehr in der aktuellen EXE gefunden |
| `BERECHTIGUNG` (`USERID`/`MODULID`/`FORMID`/`STATUS`/`MANDANTID`) | Tabelle | Logik | **codebestätigt aktiv**: `Select * from Berechtigung where UserID=... and FormID=...` – steuert Formularzugriff |
| `BENUTZER.MANDANT`/`BERECHTIGUNG.MANDANTID` | Felder | Verknüpfung | Multi-Company-Zuordnung |
| `BENUTZER` Login-Felder (`LOGIN`/`PW`/`MAIL`) | Felder | Info | |
| `BENUTZER` `MA*`-Personalakte-Felder | Felder | Info | vermischt mit Login in derselben Tabelle |
| `ZEITEN` (Beginn/Ende/Tätigkeit/Projekt/KM/KFZ/Spesen) | Felder | Info | freie Tätigkeitsbuchung |
| `ZEITGRUND.MOAZ/-PAUSE` … `SOAZ/-PAUSE` (je Wochentag) | Felder | Logik | Soll-Arbeitszeit-/Pausenmodell, treibt Monatsabschluss-Berechnung |
| `ZEITGRUND.SONNZUSCHLAG`/`FEIERZUSCHLAG`/`NACHTZUSCHLAG` | Felder | **Info, nicht Logik** | Spalten existieren, sind aber in der Live-DB bei allen 99 Zeilen NULL – **keine tatsächliche Berechnungswirkung im ERP nachweisbar** |
| `TWorkTimeObject`-Minutenzähler (Nacht/Sonntag/Feiertag) | Laufzeitberechnung, nicht persistiert als Zuschlag | Logik | **codebestätigt**: zählt Minutenanteile in festen Zeitfenstern, aber ohne Weiterverarbeitung zu einem Euro-Betrag im ERP selbst |
| `ZEITPERSO` (`TAGSOLL`/`TAGSTD`/`TAGMIN`/`GESMIN`) | Felder | Logik | Tages-Soll/-Ist-Abgleich |
| `TEXTBAUSTEINE.VON`/`BIS` | Felder | Logik | steuert Gültigkeitszeitraum eines Textbausteins |

---

## Prozess-Modul

| Feld | DB-Feld | Kategorie | Anmerkung |
|---|---|---|---|
| `PROZESSMAIN`/`-GRUPPEN`/`-STRUKTUR`/`-ABTEILUNGEN`/`-OBJEKTE` | Tabellen | Verknüpfung (theoretisch) | als generisches BPM-System konzipiert, **aber 0 Zeilen in der Live-DB** – Verknüpfungsrolle nie tatsächlich genutzt |
| `PROZESSOBJEKTE.ModulID`+`ObjektID` | Felder | Verknüpfung | generischer polymorpher Link zu jedem Modul-Objekt (Konzept, ungenutzt) |
| `PROZESSZEITEN.OBJEKTART` | Feld | Logik | **codebestätigt aktiv**: `0`=Projekt (156.257 Buchungen), `154`=Reparatur-Zeitbuchung (133.636 Buchungen, identischer Code wie `BELEGART`) |
| `PROZESSZEITEN.ProzessID = 999` | Feld/Wert | Logik | **codebestätigt aktiv**: reservierter Marker, in `ProjektzeitenHM.exe` als Live-Filter (`prozessid <> 999`) genutzt, nicht nur historisch in der Migrationsroutine |
| `PROZESSZEITEN.FirstID`/`Zeit`/`Zeit2` | Felder | Logik | **codebestätigt**: `FirstID` gruppiert eine Stempel-Session (als Ganzes löschbar), `Zeit`/`Zeit2` sind Beginn/Ende desselben Stempel-Paars (`Zeit2` per nachträglichem `UPDATE`) |
| `PROZESSZEITENK`/`-S` | Tabellen | Info | Migrationsartefakte (Sicherung/Korrektur einer einmaligen Datenreparatur), kein eigenständiges Konzept |
| `Mitarbeiterqualicross.Ablaufdatum`/`IsEntry` | Felder | Logik | **codebestätigt**: dieselbe Kreuztabelle verknüpft Mitarbeiter↔Produktionsschritt UND Mitarbeiter↔Qualifikation mit Verfallsdatum – zwei Beziehungen, nur über die Zieltabelle im Join unterschieden |
| `ZeitPerso.beginn`/`beginnori`, `ende`/`endeori` | Felder | Logik | **codebestätigt**: Original- und Korrekturwert werden parallel gehalten – echter Audit-Trail für nachträgliche Zeitkorrekturen |
| `WARTUNG.KALIBINTERVALL`/`FAELLIGKEIT`/`NEXTTERMIN` | Felder | Logik (theoretisch) | Kalibrierungs-Fälligkeitslogik mit Mail-Dämon vorhanden, aber nur 1 Zeile live – praktisch ungenutzt |
| `TDBLaufkartenObject` → `TDBProzessLinkObject` | Codeverknüpfung | Verknüpfung | **codebestätigt**: Laufkarten sind technisch eine `PROZESSLINK`-Instanz |

---

## Gesamtbild: die vier wiederkehrenden Logik-/Verknüpfungsmuster

Über alle Bereiche hinweg wiederholen sich dieselben vier technischen Muster
– das ist die eigentliche Erkenntnis dieser Klassifikation, wichtiger als
jede einzelne Feldzeile:

1. **Ein einziges Diskriminator-Feld trägt die gesamte Logik eines Bereichs.**
   `BELEG.BELEGART` (74/100–105/108/115/118/154) entscheidet nicht nur, *was*
   ein Beleg ist, sondern *wie* er sich verhält – welche Satellitentabelle
   (`REPKOPF`, `BESTELLKOPF`-Rest, `BELEGPOSMAHN`) mitgeladen wird, welche
   Buttons/Menüpunkte aktiv sind, welche Gates greifen. Odoo verteilt dieselbe
   Information stattdessen auf eigenständige Modelle – der Diskriminator
   selbst verschwindet bei einer Migration, sein *Verhalten* muss aber pro
   Zielmodell nachgebaut werden.
2. **Verknüpfungen sind selten Fremdschlüssel, meist Nummern-Matches oder
   generische ModulID/ObjektID-Paare.** `BELEG.HAUPTAUFTRAG`, `REPKOPF.BELEGNUMMER`,
   `PROZESSOBJEKTE.ModulID+ObjektID`, `InfoDokumente.ModulID+ObjektID` – vier
   verschiedene Varianten desselben Grundproblems: keine erzwungene
   referenzielle Integrität. Odoos FK-Modell ersetzt das durchgängig robuster,
   nicht nur anders.
3. **Logik sitzt überwiegend in Gates (Boolean-Flags, die einen Übergang
   blockieren) und in Std.×Faktor=Wert-Berechnungsmustern**, nicht in
   komplexen Workflows. `AllPreisGeprueft`, `PUFFERLAGER`, `BEWERTEN`,
   `GEPRUEFT`/`ZEUGNIS` folgen demselben Muster wie `KST×KFKT=KWERT` und
   `RKM×RKMFAKTOR=RKMWERT` – einfache, aber konsistent wiederkehrende
   Bausteine, die sich in Odoo eher als Constraints/Computed Fields als als
   eigene Workflow-Engine nachbilden ließen.
4. **Ambitionierte Logik-Schichten, die nie produktiv wurden, existieren
   neben aktiv genutzten schlankeren Nachfolgern.** Das Prozess-Modul (BPM-
   Definitionsschicht: 0 Zeilen) neben der aktiv genutzten Zeitstempel-Ebene;
   die `WARTUNG`-Kalibrierungslogik (1 Zeile) neben funktionierenden anderen
   QS-Mechanismen; die breiten `BENUTZER`-Rechte-Flags neben der aktiv
   abgefragten `BERECHTIGUNG`-Tabelle. Bei einer Migration lohnt sich vorher
   ein Live-Daten-Check wie hier, bevor eine ganze Tabellenfamilie 1:1
   nachgebaut wird – ein leeres Schema ist keine Anforderung.

Dieses Dokument ersetzt keinen der beiden Quelldokumente, sondern bündelt sie
unter der Info/Verknüpfung/Logik-Perspektive für eine künftige
Migrationsentscheidung. Für Feldbelege (SQL, Pascal-Code, DFM-Bindungen)
siehe [`erp-odoo-modulvergleich.md`](erp-odoo-modulvergleich.md) und
[`legacy-schema/aktuelle-exe-validierung.md`](legacy-schema/aktuelle-exe-validierung.md).
