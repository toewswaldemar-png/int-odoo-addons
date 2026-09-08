# Modulvergleich: aktuelles ERP ↔ Odoo 19

Stand: 2026-08-31 (Menü/Feldübersicht), Validierung 2026-09-08, erweitert um
Live-DB-Zugriff 2026-09-08. Ausgangspunkt war ein Screenshot der
Hauptmenü-Übersicht des aktuellen (Windows-Legacy-)ERP-Systems. Zweck dieses
Dokuments: Einordnung, welche Odoo-Standardmodule bzw. bestehende
`int_`-Addons die einzelnen Bereiche abdecken, und wo Lücken bestehen.

## Quellenlage (Reverse Engineering, Stand 2026-09-08)

Die Screenshot-Angaben wurden gegen vier unterschiedlich aktuelle Quellen
geprüft:

| Quelle | Stand | Inhalt |
|---|---|---|
| `IBDB.GDB` (Firebird/InterBase-DB, aus `db/BAK/IBDB.zip`) | 2011-11-09 | Vollständiges DDL-Schema (194 Tabellen), extrahiert via `isql -a`; abgelegt unter [`legacy-schema/full_schema.sql`](legacy-schema/full_schema.sql) |
| `HMS/Module/*.pas` (Delphi-Quellcode) | bis 2018-11 | Datenmodul-/Geschäftslogik; jüngste Datei-Timestamps liegen bei Nov. 2018 |
| `Herrmann.exe` (kompiliertes aktuelles Programm) | 2026-09-06 | String-/Ressourcenextraktion (`strings` auf ASCII + UTF-16LE) aus dem produktiv gebauten Binary |
| `IBDB.FDB` (lokale Kopie der Produktiv-DB, `Herrman Work Test/IBDB.FDB`) | **2026-09-08 (tagesaktuell)** | Vollständiges DDL-Schema (437 Tabellen, 47 Views, 111 Stored Procedures) direkt aus der Live-Datenbank, inkl. vollständiger Prozedur-/View-Quelltexte; abgelegt unter [`legacy-schema/full_schema_current.sql`](legacy-schema/full_schema_current.sql) und [`legacy-schema/all_procedure_sources.sql`](legacy-schema/all_procedure_sources.sql) |

**Wichtige Erkenntnis:** Die 2011er-DB-Kopie und der lokal vorliegende
Pascal-Quellcode (bis 2018) waren beide veraltet und bildeten nur den
**stabilen Datenkern** korrekt ab. Mit dem Live-DB-Zugriff (Option C, siehe
unten) ist diese Lücke jetzt geschlossen: alle vier Quellen zusammen decken
Datenbankebene (aktuell), UI-Ebene (471 DFM-Formulare aus der EXE) und
Geschäftslogik-Ebene (2018er-Pascal-Code der zentralen Formulare) ab. Alle
„bestätigt"/„korrigiert"-Vermerke beziehen sich auf diesen Quellen-Mix; wo
ein Fund nur aus der 2011/2018-Kombination stammt und (noch) nicht gegen die
Live-DB nachgeprüft wurde, ist das im jeweiligen Abschnitt vermerkt.

**Wichtige Einschränkung zum Pascal-Quellcode (geklärt 2026-09-08):** Die
`HMS/Module/Herrmann.dpr`-Projektdatei zeigt, dass `Herrmann_Work` **kein
eigenständig baubares Projekt** ist. 195 von 196 `uses`-Zeilen verweisen über
relative Pfade (`..\..\..\..\ERP-Software\D2000\...`) auf einen separaten,
auf diesem Rechner nicht vorhandenen Quellbaum – nur eine Handvoll Formulare
(`FAdressen`, `FBenutzer`, `FTextbau` u. a.) liegen tatsächlich lokal unter
`HMS/Standard/Module/...`. Das bedeutet: der überwiegende Teil der bisher
gelesenen Geschäftslogik-Dateien (F8D.pas, FAuftragTSP.pas,
FBestellungTSP.pas, FProduktion.pas, FLieferscheinTSP.pas, FRechnungTSP.pas,
FMitarbeiterZeiterfassung.pas u. a.) liegt zufällig *zusätzlich* lokal in
`Herrmann_Work` vor (sonst wären sie gar nicht lesbar gewesen), ist aber laut
Projektdatei **nicht** die vom echten Build referenzierte Quelle. Für die in
diesem Dokument zitierten Formulare ist das unkritisch, da deren Code separat
gegen DFM/Live-DB gegengeprüft wurde. Bei zwei tatsächlich **doppelt
vorhandenen** Dateien (`UArtikelObject.pas`/`UBelegObject.pas`/
`UDBWorkObjects.pas`, einmal unter `HMS/Module/` von 2017, einmal unter
`HMS/Module/Global/GlobalObjects/` von 2014) zeigt die `.dpr` eindeutig: **keine
von beiden ist die aktive Quelle** – referenziert wird stattdessen
`..\..\..\..\ERP-Software\D2000\V0.0\UArtikelObject.pas`, ein Pfad, der in
diesem Verzeichnisbaum nicht existiert. Beide lokalen Kopien sind damit als
verwaiste/veraltete Zwischenstände einzuordnen, nicht als Kandidaten für
"welche ist aktiv".

## Aktuelles Menü (Ist-Zustand)

- **System**: Textkonstanten, Grundlagen, Db-Administration, Formulareinstellungen,
  Druckereinstellungen, Export, Projekte
- **Firmendaten**: Mitarbeiter, Benutzer, Textbausteine, Wareneingang, Warenausgang,
  Mitarbeiter Zeit, Auswertungen, Auslieferung, Gelangensbestätigung
- **Stammdaten**: Adressen, Adressgruppen, Artikel, Artikelgruppen, Stückliste,
  Stücklistengruppen, Geräte, Rep-Bestellung, Status Reparaturen
- **Einkauf**: Anfragen, Rahmenbestellung, Bestellung, Rechnungsprüfung,
  Bestellliste, 8D Lieferant, Rahmen Reparatur, Eingangsrechnungen, SammelBeleg,
  Beistellung
- **Produktion**: Produktion, Produktionsarten, Laufkarten, Protokoll, 8DIntern,
  FAM, 8D-Kunde, EngpassCockpit, Cockpit, Begleitschein, Engpass Reparaturen,
  Übersicht Stücklisten
- **Vertrieb**: Angebot, Hauptauftrag/Bestellung, Lieferschein, Rechnung,
  Abschlussrechnung, Mahnung, Vertreterabrechnung, Reparatur, Prodauftrag

## Modulzuordnung

| Bereich (aktuelles ERP) | Odoo-Äquivalent | Anmerkung |
|---|---|---|
| **Stammdaten**: Adressen/-gruppen | `contacts` (res.partner) | 1:1 abgedeckt |
| Artikel/-gruppen, Stückliste/-gruppen | `product` + `mrp.bom` | Stücklisten = BOMs, Standard-Odoo |
| Geräte | kein direktes Standardmodul | ggf. Custom-Feld/-Modell nötig (Seriennummern? `stock.lot`?) |
| Rep-Bestellung, Status Reparaturen | `repair` (Repair Orders) | passt zu `int_repair_workshop` |
| **Einkauf**: Anfragen, Rahmenbestellung, Bestellung, Rechnungsprüfung, Bestellliste | `purchase` | RFQ, Blanket Orders (Enterprise), 3-way-match |
| 8D Lieferant, Rahmen Reparatur | `quality` (8D-Reports) + `repair` | Odoo Quality hat "5 Why"/MRP-Anbindung, kein natives 8D-Formular – evtl. Custom. *Validiert 2026-09-09: der Sub-Tab "Belastungsanzeige" in der Artikelinfo trägt intern durchgängig die Steuerelement-Namen `tsh8dl`/`dbg8dL`/`ds8dl` – Label wurde offenbar nachträglich von "8D Lieferant" auf "Belastungsanzeige" geändert, ohne die Komponenten umzubenennen. Fachlich naheliegend: eine 8D-Lieferantenreklamation mündet oft in eine Belastung (Chargeback) des Lieferanten – beide Konzepte teilen sich hier ein Formular. **Erweitert 2026-09-09 über vollständige DFM-Extraktion**: Das geht noch weiter – die komplette Reparatur-Belegmaske (Kostenvoranschlag/Material/Versand-Tabs, alles bisher unter "Reparatur" dokumentierte) ist intern als Delphi-Klasse **`TFRM8D`** implementiert. Es gibt kein separates `TFRMREPARATUR`-Formular – "Reparatur" und "8D" waren also ursprünglich ein und dasselbe Formular, nur die UI-Beschriftung wurde im Lauf der Zeit auf "Reparatur" umgestellt* |
| Eingangsrechnungen, Beistellung | `account` (Vendor Bills) | Beistellung (Kundenmaterial) kein direktes Pendant, oft über Kit/Consignment gelöst |
| **Produktion**: Produktion, Produktionsarten, Laufkarten, Protokoll, FAM | `mrp` (Manufacturing Orders, Work Orders) | Laufkarten ≈ Arbeitsscheine/Shop Floor |
| 8DIntern, 8D-Kunde | `quality` + Custom | wie oben |
| EngpassCockpit, Cockpit, Engpass Reparaturen | kein Standardmodul | Kapazitätsplanung/Bottleneck-Dashboards meist Custom oder `mrp` + Studio-Views |
| Begleitschein, Übersicht Stücklisten | `stock` (Delivery/Transfer) + `mrp.bom`-Reports | |
| **Vertrieb**: Angebot, Hauptauftrag/Bestellung, Lieferschein, Rechnung | `sale` + `stock` + `account` | Kernprozess 1:1 |
| Abschlussrechnung, Mahnung, Vertreterabrechnung | `account` (Follow-up/Reminders) + Commission-Apps | Vertreterabrechnung eher Custom/Marketplace-App |
| Reparatur, Prodauftrag | `repair`, `mrp` | |
| **Firmendaten**: Mitarbeiter, Benutzer | `hr` + Odoo-Benutzerverwaltung | |
| Wareneingang/-ausgang, Auslieferung | `stock` | |
| Gelangensbestätigung | kein Standard | EU-Ausfuhrnachweis, meist Lokalisierungs-/Custom-Modul. *Validiert 2026-09-08: reale Felder `GelangenDatum`/`GelangAngefordert` auf `Belegpos`, `GelangenKopf`/`GelangenFuss`-Textbausteine, eigener Excel-Export (`TCreateGelangenExcel`) und Dialog (`TfrmGelangenDlg`); ebenfalls nicht in der 2011-DB, erst später ergänzt* |
| **System**: Textkonstanten, Textbausteine | `mail.template` / Odoo Studio | |

## Detailvergleich: Adressen (Stammdaten → Adressen-Suchen)

Feldebene der "Adressen - Suchen"-Maske gegen `res.partner`.

**Validiert 2026-09-09 über Live-Screenshot + DFM-Feldbindungen — wichtige
Korrektur der ursprünglichen Lesart:** Die rechte Box "Sortierung" ist **kein
Sortier-Menü für die Ergebnisliste**, sondern eine Radiobutton-Auswahl
(`rbtName1`/`rbtName2`/`rbtName3`/`rbtKurzname`/`rbtPlz`/`rbtOrt`/`rbtDebNr`/
`rbtKredNr`), die festlegt, **welches der acht Eingabefelder als aktiver
Suchschlüssel dient** – `rbtName1` ist standardmäßig aktiv. Das ist eine
grundsätzlich andere Suchlogik als in Odoo, wo alle gefüllten Filterfelder
gleichzeitig kombiniert (UND-verknüpft) würden.

| Feld (aktuelles ERP) | Odoo-Äquivalent | Anmerkung |
|---|---|---|
| Name 1 | `name` | |
| Name 2 | kein Standardfeld | Odoo kennt keine mehrzeilige Firmenbezeichnung; oft über `street2` zweckentfremdet oder Custom-Feld nötig |
| Name 3 | kein Standardfeld | wie Name 2, z. B. für "c/o"-Zeilen; Custom-Feld nötig |
| Kurzname | kein Standardfeld | am ehesten `ref`, aber semantisch anders belegt (interne Referenz statt Kurzname) |
| Strasse | `street` | |
| Plz / Ort | `zip` / `city` | |
| Debit.-Nummer / **allg. Nummer** | kein 1:1-Feld | Odoo nutzt Partner-ID/`ref`; eine eigenständige, ggf. anders formatierte Debitorennummer braucht Custom-Feld + eigene Sequenz. *Validiert: nur **ein** Eingabefeld (`edtDebNr`), "allg. Nummer" ist eine zweite Beschriftungszeile für dasselbe Feld – die Debitorennummer dient offenbar zugleich als allgemeine Nummernsuche, kein separates zweites Feld* |
| Kredit.-Nummer | kein 1:1-Feld | analog zur Debitorennummer, i. d. R. Custom-Feld |
| Ansprechpartner | Kontaktpersonen (`res.partner` mit `parent_id`) | bestätigt: eigene Tabelle je Adresse mit Anrede, Name, Vorname, Fon, Fax, Mobil, E-Mail, Funktion je Kontakt – bildet sich sehr gut auf Odoos Kontaktpersonen-Modell ab (Titel/Vorname-Nachname/`phone`/`mobile`/`email`/`function` sind alles native Felder auf `res.partner`); einer der saubersten 1:1-Fälle in diesem Vergleich |
| Gruppe / Nr. | `category_id` (Partner-Tags) | "Nr." als zusätzliche Nummerierung innerhalb der Gruppe hat kein Pendant, ggf. Custom. *Validiert: `edtGruppe` ist **ReadOnly** (`Color clSilver`) – nicht direkt eintippbar, nur über einen Auswahl-Button befüllbar, mit separatem `edtGruppeBez` für die Bezeichnung daneben* |
| "Adressen Filtern" (Checkbox) | Odoo-Suchfilter/-Views | kein Datenfeld, sondern Sucheinstellung – in Odoo über Standard-Filter/Gruppierung gelöst. *Validiert: `cbxFilter`, standardmäßig **aktiv** (`Checked=True`)* |
| *(neu entdeckt)* "letzte Suche"-Button | kein Pendant | `btnLastSearch` – wiederholt die zuletzt ausgeführte Suche, in Odoo allenfalls über gespeicherte Filter nachbaubar |
| *(neu entdeckt)* "Alle markieren"-Button | `select all` (nativ in Odoo-Listenansichten) | generische, in mehreren Formularen wiederverwendete Beschriftung, nicht Adressen-spezifisch |

**Beobachtung:** Die größte strukturelle Lücke ist die dreizeilige Namensfelder-Logik
(Name 1–3) sowie eigenständige, frei formatierbare Debitoren-/Kreditorennummern
getrennt von der internen Odoo-ID. Beides wäre bei einer Migration entweder per
Custom-Feld auf `res.partner` oder durch Umgewöhnung an Odoos Kontaktmodell
(Firma + Kontaktpersonen statt Namenszeilen) zu lösen. Hinzu kommt jetzt die
validierte Erkenntnis, dass die Suche selbst anders funktioniert als
angenommen (ein aktives Suchfeld statt kombinierter Filter) – bei einer
Odoo-Migration ohnehin hinfällig, da Odoos Suchleiste mehrere Kriterien nativ
kombiniert.

## Detailvergleich: Adressen (Detailmaske, Reiter "Allgemein")

Zusätzliche Felder gegenüber der Suchmaske, aus der Datensatzansicht eines
konkreten Adress-/Kontaktdatensatzes:

| Feld (aktuelles ERP) | Odoo-Äquivalent | Anmerkung |
|---|---|---|
| Nummer | interne ID / `ref` | |
| Anlage / Änderung (Datum) | `create_date` / `write_date` | in Odoo Systemfelder, nicht standardmäßig auf dem Formular sichtbar |
| Anrede: Firma / Person | `company_type` | passt direkt |
| Art: Allgemein / Kunde / Lieferant (exklusiv) | `customer_rank` / `supplier_rank` | **struktureller Unterschied**: Odoo behandelt Kunde/Lieferant nicht exklusiv – ein Partner kann beides gleichzeitig sein, hier ist es eine Radio-Auswahl. *Validiert 2026-09-08: kein eigenes Exklusiv-Feld im Schema gefunden (weder 2011-DB noch aktuelle EXE) – `DebNr` und `KredNr` sind unabhängige Felder, die "Exklusivität" ist vermutlich reine UI-Logik, nicht im Datenmodell erzwungen. Live-Beispiel 2026-09-09 (Railpool GmbH): "Kunde" ausgewählt, `DebNr` gefüllt (11722), `KredNr` leer – starkes Indiz für die Ableitungs-These, aber weiterhin keine direkte Steuerelement-Bindung gefunden, also kein endgültiger Beweis* |
| Postfach | kein Feld | Custom-Feld nötig. *Validiert 2026-09-09: tatsächlich zwei getrennte Felder `POSTFACH` + `POSTFACHPLZ` (eigene Postleitzahl fürs Postfach, unabhängig von der Straßen-PLZ) – noch granularer als ursprünglich angenommen* |
| Ansprechpartner-Funktion (Spalte "Funkti..." im Kontaktgrid) | `function` (natives Feld auf `res.partner`) | passt inhaltlich, aber *Validiert 2026-09-09: real ist es kein eigenes `FUNKTION`-Feld auf `ADRESSENANSPRECH`, sondern das wiederverwendete Feld `NOTIZ` (`Select distinct Notiz from AdressenAnsprech order by Notiz` liefert die Dropdown-Werteliste) – dasselbe Feld-Wiederverwendungsmuster wie mehrfach in der Reparaturmaske* |
| Lkz (Ländercode) | `country_id` | |
| Etikette (Checkbox) | kein Feld | Druck-/Etikettensteuerung, vermutlich Custom oder Report-Filter |
| inaktiv (Checkbox) | `active` (Archivierung) | **Semantikunterschied**: Odoos `active=False` blendet den Datensatz komplett aus Standard-Views aus; falls "inaktiv" hier nur einen Status markiert und der Datensatz weiter sichtbar bleiben soll, braucht es ein eigenes Feld statt `active` |
| gesperrt (Checkbox) | kein Feld | z. B. Liefer-/Bestellsperre – Custom-Feld, da semantisch verschieden von `active` |
| nicht bewerten (Checkbox) | kein Feld | Ausschluss aus Lieferantenbewertung – ggf. Anknüpfungspunkt an `quality`-Modul |
| ist Vertreter (Checkbox) | kein Feld | am ehesten über Partner-Tag/Kategorie lösbar |
| Buyer Ref. | kein Feld | Custom |
| unsere Nummer bei Kunde/Lieferant | kein Feld | eigene Kundennummer beim Geschäftspartner – kein Odoo-Standardfeld (zu unterscheiden von `ref`, das die eigene interne Nummer ist) |
| Fon / Fon 2 / Fax / Mobil | `phone` / `mobile` | Odoo kennt nur je ein Feld für Telefon und Mobil, kein zweites Telefonfeld, Fax in neueren Odoo-Versionen entfernt. *Validiert 2026-09-09: `FON2` existiert als eigenständiges Feld (mehrfach als Referenz bestätigt), unabhängig von `FON1` – die Odoo-Lücke ist damit real, nicht nur vermutet* |
| E-M@il Zentral / Rechnung / Vertrieb / Einkauf / GL / Info (je mit CC/BCC) | `email` (ein Feld) + Kontaktpersonen mit Adresstyp | Odoo löst mehrere Zwecke eher über zusätzliche Kontakt-Datensätze (Rechnungsadresse, Lieferadresse) statt über mehrere E-Mail-Felder am selben Partner; CC/BCC pro Zweck hat kein Pendant. *Validiert 2026-09-08 anhand der aktuellen EXE (SQL-String aus dem Adressen-Ladeformular): reale Feldnamen sind `EMail` (Zentral), `EmailBuchhaltung` (Rechnung), `EMailVT` (Vertrieb), `EmailEK` (Einkauf), `EmailGL`, `EmailInfo`, dazu je ein CC/BCC-Paar (`BUCHHALTUNGCC/BCC`, `VTCC/BCC`, `EKCC/BCC`, `GLCC/BCC`, `InfoCC/BCC`, `EmailCC/BCC`) sowie separate Versand-Flags `MailAngebot`, `MailAuftrag`, `MailLieferschein`, `MailRechnung`, `MailBestellung` und Rechnungskopie-Routing `RechCopyAll/Norm/VT/Fibu/Opos` – die Behauptung war korrekt, sogar granularer als zunächst dokumentiert* |
| WWW | `website` | |
| XRechnung-Block (Buyerreferenz, Endpoint, Contractnr, Leitweg ID, eigene ID, ID Kunde) | Peppol-/E-Invoicing-Felder (`peppol_eas`, `peppol_endpoint`) bzw. deutsche Lokalisierung | thematisch verwandt (E-Rechnungspflicht), aber nicht feldgleich – bei einer Migration eigener Prüfpunkt, da B2B-E-Rechnungspflicht in Deutschland gerade schrittweise scharf geschaltet wird. *Validiert 2026-09-08: reale Feldnamen `LeitwegID` und `BuyerRef`/`BuyerReference` auf `Adressen`, dazu `Xemail`/`Xrech`-Flags; ruft extern `xrechnung.exe` auf (liegt lokal unter `Herrmann_Work/20211007/XRechnung.exe`). Existiert weder in der 2011-DB noch im 2018er-Quellcode – nachweislich erst danach eingeführt (passt zur E-Rechnungspflicht 2024/2025)* |

**Beobachtung:** Neben den bereits genannten Namens-/Nummernfeldern zeigt die
Detailmaske zwei weitere strukturelle Unterschiede: (1) Kunde/Lieferant ist hier
exklusiv, in Odoo nicht: (2) mehrere zweckgebundene E-Mail-Felder mit eigenem
CC/BCC pro Adresse gibt es in Odoo nicht in dieser Form. Der XRechnung-Block ist
inhaltlich der einzige Bereich mit einer nativen Odoo-Entsprechung (Peppol/E-Invoicing),
aber ohne 1:1-Feldabgleich.

### Adress-Info, Reiter "Sonstiges"

Validiert 2026-09-09 über Live-Screenshot + Feldreferenzen aus der aktuellen
EXE. Bisher nicht dokumentierter dritter Bereich der Adress-Detailmaske:

| UI-Element | DB-Feld | Anmerkung |
|---|---|---|
| Bemerkung | `ADRESSEN.BEMERKUNG` (`VARCHAR200`) | |
| "Bedingungen des Lieferanten / Kunden" (Zahlung/Versand) | `ADRESSEN.ZKONDI`/`VERSAND` | Konditionen des Geschäftspartners |
| "Bedingungen Herrmann" (Zahlung/Versand) | `ADRESSEN.ZKONDIL`/`VERSANDL` | Herrmanns **eigene** Konditionen diesem Partner gegenüber – Label an anderer Stelle sogar als "Bedingungen Herrmann (Angebot)" gefunden |
| Liefertage (Mo–So, 7 Checkboxen) | `ADRESSEN.LIEFERTAGE` (`VARCHAR30`) | ein einzelnes Feld, als 7 Checkboxen dargestellt – vermutlich positionscodierter String, ein Zeichen je Wochentag |
| Lieferadressen-Grid (Name 1/2, Strasse, Lkz, Plz, Ort) | eigene Tabelle `ADRESSENLIEFER` | echte 1:n-Tabelle je Hauptadresse |

**Beobachtung:** Zwei getrennte Konditionen-Paare pro Adresse (Partner-Konditionen
vs. Herrmanns eigene Konditionen) sind ein struktureller Unterschied zu Odoo,
das nur ein Zahlungsbedingungsfeld (`property_payment_term_id`) je Partner
kennt, keine "unsere vs. seine Bedingungen"-Trennung. Lieferadressen
(`ADRESSENLIEFER`) ist dagegen der sauberste Fall auf diesem Tab – bildet sich
1:1 auf Odoos Mehrfach-Lieferadressen ab (`res.partner` mit `type='delivery'`).

### Adress-Info, Reiter "Kartei"

Validiert 2026-09-09 über Live-Screenshot + Feldreferenzen. Dritter,
bisher nicht dokumentierter Bereich der Adress-Detailmaske: eine
**Preis-/Bestellhistorie je Artikel für diesen Kunden**. Technisch:
`TTabSheet tshKartei` → `TDBGrid dbgBeleg` → `DataSource dsKartei`, gespeist
über eine Stored Procedure `TSQLGetKartei` (Name bestätigt, genauer
SQL-Text nicht extrahierbar). Sehr ähnliches, eindeutig zuordenbares Muster
an anderer Stelle im Programm:

```sql
select B.Belegdatum, B.Adrnr, B.Name1, B.Ort, P.Artnr, P.Stck, P.Text, P.Epreis
from Beleg B, Belegpos P
where B.oid = p.soid and B.Belegart = :parArt and B.Adroid = :parAdr
  and B.Belegdatum between :parVon and :parBis
order by Belegdatum, Artnr
```

Zeigt jede Position aus jedem Beleg dieses Kunden – im Live-Beispiel sichtbar
an denselben Artikelnummern (1014 "4-Leiter Durchgangsklemme", 1088
"Kontakt-Stift Han-C 2,5 AG"), die über mehrere Jahre und Belege hinweg
wiederkehren, inkl. Preisentwicklung (Artikel 1014: 2,42€ in 2019 → 3,22€ in
2026). Funktional eine Preishistorie je Artikel/Kunde für die
Kostenvoranschlags-Erstellung.

Odoo-Bezug: am ehesten über einen gefilterten `sale.order.line`-Bericht
(Partner+Produkt) nachbaubar, aber kein dediziertes, kundenbezogenes
Kartei-Tab wie hier.

## Detailvergleich: Artikel

Abgleich der `ARTIKEL`-Tabelle (2011-Schema, 130 Spalten) gegen die bereits
bestehenden Testballon-Felder aus [`int_legacy_erp_import`](../int_legacy_erp_import/models/product_template.py)
(`x_alt_artnr`, `x_alt_kurzbezeichnung`, `x_alt_bestellnr`, `x_alt_hauptlieferant`,
`x_alt_gruppe`, `x_alt_einheit`, `x_alt_hersteller_ref_ids`), plus Gegenprobe
über die aktuelle EXE.

| Feld (Addon) | Reales DB-Feld | Typ lt. Schema | Anmerkung |
|---|---|---|---|
| `x_alt_artnr` | `ARTIKEL.ARTNR` | `VARCHAR(30)` | bestätigt, Char-Feld korrekt |
| `x_alt_kurzbezeichnung` | `ARTIKEL.KURZBEZEICHNUNG` | `VARCHAR(30)` | bestätigt, Char-Feld korrekt |
| `x_alt_bestellnr` | `ARTIKEL.BESTELLNR` | `VARCHAR(60)` | bestätigt; existiert zusätzlich lieferantenspezifisch auf `ARTIKELPREISE.BESTELLNR` (je Lieferant eigene Bestellnummer) – Addon-Feld bildet nur den Artikel-Kopfwert ab |
| `x_alt_hauptlieferant` | `ARTIKEL.HAUPTLIEFERANT` | `INTEGER` (Fremdschlüssel) | **Typ-Diskrepanz**: Addon modelliert als `Char` ("Hauptlieferant-Code"), real ist es eine Ganzzahl-Referenz auf `ADRESSEN.OID`. Validiert über die aktuelle EXE: eigene Query `Select OID, Name1, ... from Adressen where not Krednr is NULL ... order by coalesce(HauptLieferant, 'F') Desc` bestätigt den Verweis auf Lieferanten-Adressen. Sollte als `Many2one` auf `res.partner` modelliert werden, nicht als Freitext |
| `x_alt_gruppe` | `ARTIKEL.GRUPPE` | `INTEGER` (Fremdschlüssel) | **Typ-Diskrepanz**: Addon modelliert als `Char` ("Gruppe"), real eine Ganzzahl-Referenz. Validiert über aktuelle EXE: `... Artikel A left join Artikelgruppen G on G.GID = coalesce(A.Gruppe,-1)` – Join gegen `ARTIKELGRUPPEN.GID`, nicht `.OID`. Sollte als `Many2one`/`product.category`-Verknüpfung modelliert werden |
| `x_alt_einheit` | `ARTIKEL.EINHEIT` | `VARCHAR(10)` | bestätigt, Char-Feld korrekt (kürzelbasiert wie `uom.uom`, kein FK im Altsystem) |
| `x_alt_hersteller_ref_ids` (`product.legacy.manufacturer.ref`, Codes BT/LH/FY/NK/KO/VK/BE/TK/DB/HO/WE) | `ARTIKEL.IDENTNR1` … `IDENTNR5` (2011-Schema) bzw. bis `IDENTNR12` (aktuelle EXE) | `VARCHAR(60)` je Slot | **Endgültig bewiesen 2026-09-09 über echte DFM-Extraktion** (vorher nur per Wertevergleich plausibilisiert): Labels und Eingabefelder im "ID-Nummer"-Groupbox sind über identische Y-Koordinaten eindeutig gepaart – `BT`(Top 20)→`dbeid1`(Top 16, `DataField=Identnr1`), `LH`(43)→`dbeid2`(39, `Identnr2`), `FY`(67)→`dbeid3`(63, `Identnr3`), `NK`(90)→`Identnr4`, `KO`(114)→`Identnr5`, `VK`(138)→`Identnr6`, `BE`(161)→`Identnr7`, `TK`(185)→`Identnr8`, `DB`(209)→`Identnr9`, `HO`(232)→`Identnr10`, `WE`(256)→`Identnr11`, `SI`(280)→`Identnr12`. Damit ist **`BT`=`IDENTNR1` … `SI`=`IDENTNR12`** zweifelsfrei belegt, nicht mehr nur eine Vermutung. **Weiterhin offen:** Der 12. Code **"SI"** fehlt im Addon (nur 11 Codes gepflegt) – das Selection-Feld ist unvollständig |

**Beobachtung:** Die einfachen Textfelder (Artikelnummer, Kurzbezeichnung,
Bestellnummer, Einheit) sind im Addon korrekt nachgebildet. Die beiden
Referenzfelder Hauptlieferant und Gruppe sind dagegen als Freitext statt als
Fremdschlüssel modelliert – das funktioniert für einen reinen Anzeige-Testballon,
würde aber bei einem echten Import zu unverknüpften Werten führen (keine
Beziehung zu `res.partner`/`product.category`, keine Wiederverwendung
bestehender Odoo-Datensätze). Die Hersteller-Ident-Referenzen sind strukturell
richtig als flexible Zeilen statt starrer Spalten modelliert (das ist sogar eine
Verbesserung ggü. dem starren Altsystem-Schema); die Code-zu-Spalten-Zuordnung
ist inzwischen über einen Live-Screenshot geklärt (siehe oben), fehlt dem Addon
aber noch der zwölfte Code "SI".

### Artikel-Karteikarte: weitere Tabs und Felder

Validiert 2026-09-09 über Live-Screenshot. Die volle Artikelmaske hat sechs
Reiter (Allgemein/Zusätzlich/Preise & Referenzen/Lagerorte/Anlagen/Alternative)
– der Testballon-Addon deckt nur eine Handvoll Felder aus "Allgemein" ab. Zwei
weitere Funde aus diesem Reiter:

- **"Bestände/Nummern"-Block ist berechnet, nicht direkt gespeichert.** Die
  Felder (Bestand verfügbar, Bestellt, Bedarf Prod.Auftrag, Fertigung offen,
  Auftrag ges., Abruf.Auftrag offen, Auftrag zu Liefern) binden nicht an rohe
  `ARTIKEL`-Spalten, sondern an ein separates Dataset `dsInfoBestand` mit
  Computed-Feldern (`Prodoffen`, `Produktion`, `Bestellt`, `Auftrag`) –
  vermutlich gespeist über eine Stored Procedure `P_Bestand` (an anderer
  Stelle referenziert: `Select Bestand from P_Bestand(A.OID)`). Reiht sich
  ein in das bereits beim EngpassCockpit gesehene Muster vorberechneter
  Status-Panels.
- **Erneute Feld-Wiederverwendung, diesmal bei Steuerelement statt DB-Feld:**
  Das Label "Fertigung offen" sitzt auf einem Steuerelement namens
  `lblMeldebestand` (Meldebestand = Nachbestellpunkt), "Bedarf Prod.Auftrag"
  auf `lblReserviert` (Reserviert = reservierter Bestand) – die
  Beschriftungen wurden offenbar nachträglich geändert, ohne die
  Komponenten umzubenennen.

#### Reiter "Zusätzlich": größtenteils bereits bekannte Felder, zwei weitere Label-Vertauschungen

Validiert 2026-09-09 über Live-Screenshot + direkte DFM-Bindungen. Die
meisten Felder dieses Tabs waren bereits aus dem 2011er-Schema bekannt und
werden hier nur mit ihrer UI-Beschriftung bestätigt: `WAMONAT`/`WAJAHR`/
`WEMONAT`/`WEJAHR` (WA/WE Monat/Jahr), `GEWICHT`/`VOLUMEN`, `TEILEART`/
`WARENSCHLUESSEL`, `KUPFERZAHL`/`EDELMETALLZAHL`, `VERSCHLEISSTEIL`/
`ERSATZTEIL`/`QSPFLICHT` (als Ja/Nein-Radiogruppen), `INVDATUM`,
`BESCHAFFUNGSSCHLUESSEL`/`CHARACTERSCHLUESSEL`/`DISPOSITIONSART`,
`MINDESTBESTANDALT`/`NEU`, `TAGE_HALT`/`ZEIT_HALT` ("Verarbeitung innerhalb"
Tagen/Stunden).

Zwei weitere Fälle vertauschter Feldbeschriftungen (Ergänzung zum bereits im
Reparatur-Abschnitt dokumentierten Muster):

| UI-Feld | DB-Feld | Anmerkung |
|---|---|---|
| "Änderungstext" | `ARTIKELTEXTE.TEXTINTERN` (`dbebemerkung`) | Bindungsname spricht für "Interner Text" – Caption sitzt vertauscht |
| "Interner Text" | `ARTIKELTEXTE.TEXTZUSATZ` (`gbeTextZusatz`) | genau umgekehrt zur natürlichen Lesart |
| "Zeugnispflicht - Text" (Checkbox) | `ARTIKEL.AOFTEST` | Beschriftung nennt Zeugnispflicht, gebunden ist das AOF-Test-Feld |
| Funktionstest (Checkbox, zum Vergleich) | `ARTIKEL.FUNKTIONSTEST` | hier korrekt zugeordnet |
| Inventurbestand | `ARTIKEL.BESTAND` | **wiederverwendet** – kein eigenes Feld, zeigt den allgemeinen Bestandswert |
| **Zeugnistext (EK)** | **`ARTIKEL.Zeugnistext`** | **neu entdeckt** – kein Feld im 2011-Schema, spätere Ergänzung, direkt über `DBEdit20`→`DataField Zeugnistext` bestätigt |

#### Reiter "Preise / Referenzen": Preisfelder größtenteils direkt, "alter Wert" ist berechnet

Validiert 2026-09-09 über Live-Screenshot + DFM-Bindungen.

| UI-Feld | DB-Feld | Bindungsnachweis |
|---|---|---|
| USt.-Satz | `ARTIKEL.MWST` | `dbcbxMwst` → `DataField MWST`, Dropdown-Werte **Voll/Halb/Ohne/Dupo** (4 statt der erwarteten 2 Optionen) |
| Einkauf | `ARTIKEL.EKNETTO` | `dbeEKNetto` → `DataField EKNetto` |
| Verkauf | `ARTIKEL.VKNETTO` | `dbeVKNetto` → `DataField VKNETTO` |
| (VK Brutto) | berechnet | `dbeVKBrutto` → `DataField calcVPBrutto` (Computed, kein Rohfeld) |
| Kalkulation / Angebotspreis (Datumsteil) | `ARTIKEL.KALKPREISUPDATE` | `dbtKalkDatum` → `DataField Kalkpreisupdate` |
| kein Preisupdate (Checkbox) | `ARTIKEL.noAutoUpdate` | **neu entdeckt**, nicht im 2011-Schema, `DBCheckBox8` → `DataField noAutoUpdate` |
| **alter Wert / Letzter RP** | **kein `ARTIKEL`-Feld** | `dbeLEK` bindet an `dsInfoBestand` (dasselbe Computed-Dataset wie "Bestand verfügbar"/"Bedarf Prod.Auftrag" auf dem Allgemein-Tab), nicht an `dsArtikel` – live aus der Bestellhistorie abgeleitet. Live-Beleg: Wert `2,92`/`22.10.2024` entspricht exakt der zweitletzten Bestellzeile (Beleg 241990, Riegler & Co.KG) aus dem Einkauf-Tab |
| Lieferantenpreis-Grid | `ARTIKELPREISE` | **Korrigiert 2026-09-09 über echte DFM-Extraktion** (`dbgArtikelPreise: TDBGrid`, `DataSource=dsArtikelPreise`): **15 Spalten**, keine davon heißt "LEK" – die ursprüngliche Lesart des Screenshots war falsch/unvollständig. Reale Spalten: `LIEFERNAME`("Lieferant"), `MENGEVON`("Menge von"), `MENGEBIS`("Menge bis"), `EKBRUTTO`("Ek. Preis"), **`Mindestmenge`("VP-Einheit" – Label/Feld-Diskrepanz)**, `Lieferzeit`, `Preiseinheit`, `BESTELLNR`("Bestell-Nr."), `RABATT`, `Kupferzahl`("Kupferbasis"), `BEZEICHNUNG`, `DATUM`, `Angebotnummer`, `Ufaktor`("Faktor"), `UEinheit`("Einheit") |

**Beobachtung:** Auch hier zeigt sich das bereits mehrfach dokumentierte
Muster berechneter Anzeigepanels statt gespeicherter Werte – "alter Wert"
wirkt wie ein Stammdatenfeld, ist aber tatsächlich eine Live-Ableitung aus
der Belegzeilen-Historie.

#### Reiter "Lagerorte": zwei getrennte Ebenen, beide live berechnet bzw. neu ergänzt

Validiert 2026-09-09. Zwei unabhängige Grids mit unterschiedlicher Herkunft.

**Links "Lager - Bestände"** – Bestand je Standort, vollständig live berechnet:

```sql
Select L.Lager, Sum(B.Menge) as Bestand from Lagerorte L
left join Lagerbuchung B on B.LagerOID = L.OId and B.Artoid = :parOID and Storno = 'F'
group by L.lager
```

| UI-Spalte | Herkunft |
|---|---|
| Standortcode (H-01, P01, S01…) | `LAGERORTE.LAGER` |
| Betrag | `SUM(LAGERBUCHUNG.MENGE)` je Standort, live aggregiert – kein gespeicherter Bestandswert |

**Bonusfund:** vollständige Stored-Procedure-Definition im Klartext gefunden:

```sql
ALTER PROCEDURE P_BESTANDV (AOID INTEGER) RETURNS (BESTAND NUMERIC(15,2)) AS
  ...
  SELECT SUM(MENGE) FROM LAGERBUCHUNG WHERE ArtOID = :AOID
    AND (LAGEROID IN (SELECT OID from Lagerorte where coalesce(art,'0') <> 'S') OR LAGEROID = 0)
  INTO :ZUB; ...
```

Zeigt: `LAGERORTE` hat ein Feld **`ART`**, das Standorttypen unterscheidet –
`'S'` kennzeichnet vermutlich Schrott-/Sperrlager, die bei der "echten"
verfügbaren Bestandsberechnung explizit ausgeschlossen werden. Erklärt die
separaten S01/S02/S03-Zeilen neben den regulären Standorten.

**Rechts "Lagerplätze"** – eigenständige, feingranulare Bin-Verwaltung mit
Artikelzuordnung, **nicht im 2011-Schema vorhanden** (spätere Ergänzung):

```sql
select p.Name, p.beschreibung, c.menge from lagerplatzcross C, lagerplaetze P, Artikel A
where C.isentry = 'T' and C.Artoid = A.Oid and P.oid = C.masteroid And A.Artnr = '...'
```

| UI-Spalte | DB-Feld |
|---|---|
| Name | `LAGERPLAETZE.NAME` (z. B. "A-01.01") |
| Beschreibung | `LAGERPLAETZE.BESCHREIBUNG` |
| Voll (Checkbox) | vermutlich `LAGERPLAETZE`-Feld – nicht direkt bestätigt |

`LAGERPLAETZE` (Bin-Stammdaten) + `LAGERPLATZCROSS` (Artikel-zu-Bin-Zuordnung
mit `MENGE`/`ISENTRY`) bilden eine deutlich feinere Lagerplatzverwaltung als
das einfache `ARTIKEL.LAGERORT`/`LAGERPLATZ`-Textfeld aus dem 2011er-Schema –
echte Bin-Level-Verwaltung mit Mengenzuordnung, vergleichbar mit Odoos
mehrstufiger `stock.location`-Hierarchie.

### "Fertigungsteil" → Stückliste: STUECKLISTEN-Schema fast vollständig bestätigt

Validiert 2026-09-09 über zwei Live-Screenshots (Artikel-Link "Fertigungsteil"
+ die per Doppelklick geöffnete Stückliste). `ARTIKEL.STUECKOID` ist die
Verknüpfung – der Link erscheint nur, wenn diese Referenz gesetzt ist
(bestätigt über eine bereits bekannte Query: `coalesce(StueckOID, 0) > 0`).
Die Stückliste selbst bestätigt fast das komplette `STUECKLISTEN`-Schema:

| UI-Feld | DB-Feld | Anmerkung |
|---|---|---|
| Melden | `STUECKLISTEN.MELDEN` (`BOOLEAN`) | exakter Namenstreffer |
| Freigegeben AV | `STUECKLISTEN.FREIGABEAV` (`BOOLEAN`) | exakter Namenstreffer |
| Freigegeben GL | vermutlich `STUECKLISTEN.FREIGABE` (`BOOLEAN`) | zweites Freigabefeld, GL = Geschäftsleitung |
| geprüft | `STUECKLISTEN.GEPRUEFT` (`VARCHAR30`) | Feld ist Text (vermutlich Prüfer-Kürzel), UI zeigt nur leer/nicht-leer als Checkbox |
| Ausg. | `STUECKLISTEN.AUSG` (`VARCHAR30`) | exakter Namenstreffer |
| Status | `STUECKLISTEN.STATUS` (`VARCHAR30`) | exakter Namenstreffer |
| Abmessung | `STUECKLISTEN.ABMESS` (`VARCHAR60`) | exakter Namenstreffer |
| ID-Nummer (BT/LH/…) | `STUECKLISTEN.IDENTNR1-3` (2011-Schema; im Live-Beispiel sind 12 Slots sichtbar wie bei `ARTIKEL` – vermutlich ebenso gewachsen) | BT/LH-Werte identisch mit den Artikel-Werten – bestätigt die im Schema bereits angelegte Spiegelung zwischen `ARTIKEL` und `STUECKLISTEN` |
| Zustand Z. / Zustand S. | `STUECKLISTEN.AUSGZ` (`dbeausgz`) / `AUSGST` (`dbeausgst`) | *Nachträglich bestätigt 2026-09-09 über direkte DFM-Bindung* |
| Bearb. / Gepr. / Freig. (zwei Zeilen) | `STUECKLISTEN.B1`/`G1`/`F1` (Zeile 1), `B2`/`G2`/`F2` (Zeile 2) | *Bestätigt 2026-09-09*: zwei Sign-off-Zeilen (Initialen), **keine separaten Datumsfelder je Zeile** im Schema – die im Screenshot dreifach gleich angezeigten Daten stammen vermutlich alle aus einem gemeinsamen Feld, nicht aus drei unabhängigen Zeitstempeln |
| Änd./Datum | `STUECKLISTEN.ANLAGE` (`dbeaenddat`) | **wiederverwendet** – Feld heißt fachlich "Anlage" (Erstellungsdatum), hier als Änderungsdatum gebunden; wieder das etablierte Feld-Wiederverwendungsmuster |
| Material-Grid (Sort/Artikel/Anzahl/Einheit/BezeichnungA/B/Bemerkung) | `STUECKLISTENARTIKEL` (`NUMMER`/`ARTOID`/`ANZAHL`/`EINHEIT`/`BEZEICHNUNG1`/`BEZEICHNUNG2`/`BEMERKUNG`) | vollständiger 1:1-Treffer – das sind die echten BOM-Zeilen |
| Zweites ID-Nummer-Panel (neben dem Material-Grid) | vermutlich `STUECKLISTENARTIKEL.IDENTNR1-5`, gebunden an die aktuell markierte Materialzeile | plausibel (im Beispiel leer, während das Kopf-Feld links befüllt ist), aber keine direkte Steuerelement-Bindung gefunden – nicht bewiesen |
| "22094" / "110376" (Kopfbereich, mit @-/Personen-Icon) | `STUECKLISTEN.OID` (`dbeoid`) / `STUECKLISTEN.ARTOID` (`dbesoid`) | *Geklärt 2026-09-08 über DFM+Live-DB*: zwei nebeneinanderliegende, schreibgeschützte `TDBEdit`-Felder (`dbeoid`/`dbesoid`, direkt neben `dbeNummer`) – reine interne OID-Anzeigen (Stückliste selbst / verknüpfter Artikel), keine fachlichen Werte. Live-DB bestätigt den Wertebereich: `STUECKLISTEN.OID` bis 22758, `ARTIKEL.OID` bis 114927 – beide Beispielzahlen liegen exakt in diesen Bereichen |
| "keine Splittung" (Checkbox, an anderer Stelle desselben Tabs) | `STUECKLISTEN.NOSPLITT` (`BOOLEAN`) | *Bestätigt 2026-09-09*, exakter Namenstreffer |
| Rechtes Baum-Panel | — | zeigt ein Expand-Symbol ("+") vor dem obersten Eintrag – bestätigt eine echte Hierarchie (mehrstufige Baugruppen), keine Flachliste; vergleichbar mit verschachtelten `mrp.bom`-Strukturen in Odoo |

**Querverweis zu Produktion:** `STUECKLISTEN` hat zusätzlich `SCHRITTZEIT1`–`7`
und `RUESTZEIT1`–`7` (Schritt-/Rüstzeiten für bis zu 7 Arbeitsgänge) – erklärt
den Tab "Arbeitsgänge / Material" und verknüpft sich direkt mit den bereits
im Produktions-Abschnitt dokumentierten `KONSTPRODSCHRITTE`/`PMANNZEIT`/
`PMASCHZEIT`-Feldern. Die Stückliste trägt also selbst schon
Routing-Zeitdaten, nicht nur Materialstammdaten – Odoo trennt das sauberer
in `mrp.bom` (Material) vs. `mrp.routing.workcenter` (Zeiten je Arbeitsgang).

### Artikelinfo (F2): Bedarfs-/Preis-/Verbrauchsübersicht

Validiert 2026-09-09 über Live-Screenshot + Label-Reihenfolge aus der EXE
(`Tfrmartikelinfo2`/`FArtikelinfo2`). Eigenständiges Nachschlagefenster, per
F2 aus dem Artikelkontext aufrufbar, mit einem "Artikel"-Eingabefeld +
"aktualisieren"-Button für Sprünge zu anderen Artikeln.

| Block | Feld | DB-Bezug |
|---|---|---|
| Bedarf | Produktion / Auftrag | `dsInfoBestand.Produktion`/`.Auftrag` (bereits aus der Artikelmaske bekannt) |
| Bedarf | Reserviert | `ARTIKEL.RESERVIERT` |
| Bedarf | Bestellt | `dsInfoBestand.Bestellt` |
| Bedarf | **Geliefert** *(neu)* | vermutlich aggregiertes `BELEGPOS.GELIEFERT` |
| Bedarf | **Rahmenbestellung offen** *(neu, Querverweis Einkauf)* | offene Abrufmenge aus Rahmenbestellungen (Belegart 74) für diesen Artikel – Label exakt bestätigt |
| Preise | EK/VK/Aufschlag %/LEK (vom)/MEK | `ARTIKEL.EKNETTO`/`VKNETTO`/`AUFSCHLAG`/`LEK`/`MEK` |
| Preise | **alter EK (vom)** *(neu)* | historischer EK-Wert mit Datum, kein Feld im 2011-Schema identifiziert – vermutlich spätere Ergänzung |
| Verbrauch 12/24/36 Monate | Fertigung/Lieferschein/Lager/Reparatur | rollierende Verbrauchsstatistik nach denselben vier Belegkategorien, die auch sonst im System wiederkehren |
| Kupferzuschlag / m | `ARTIKEL.KUPFERZAHL`/`KUPFERFAKTOR` | bestätigt über `Select Kupferzahl, Gewicht from Artikel where OID = :parOID` und Prozedur `TGetKupferZuschlag` – Rohstoff-Preisgleitklausel für kupferhaltige Bauteile, in Odoo kein natives Äquivalent |
| Reiter Buchungen/Teileverwendung/Einkauf/Vertrieb/Reservierung/Kommission/Inventurwerte | Grids für zugehörige Belege | erklärt über benachbarte Double-Click-Handler im selben Formular (`dbgBestellungenDblClick`, `dbgRepDblClick`, `dbgAngeboteDblClick`, `dbgAuftragDblClick`, `dbgLieferscheinTSPDblClick`, `dbgRechnungenDblClick`, `dbgRahmenbestellungDblClick`, `dbg8dLDblClick`) – jeder Tab zeigt vermutlich alle Belege des jeweiligen Typs, in denen dieser Artikel vorkommt |
| ID-Nummer/Zeichnung-Panels (rechts) | dieselben `IDENTNR`/`ZEICHNUNGSNR`-Felder wie im Artikelstamm | **Geklärt 2026-09-09 über echte DFM-Extraktion: echter Programmierfehler, kein Datenartefakt.** Die Zeichnung-Spalte bindet zeilenweise an `Zeichnung`(BT)/`ZeichnungsNr2`(LH)/`ZeichnungsNr3`(FY, erwartet)/`ZeichnungsNr4`(NK)/… – aber `DBEdit10` (FY-Zeile, `Top=67`) ist fälschlich **ebenfalls** an `DataField = 'ZeichnungsNr2'` gebunden statt an `ZeichnungsNr3` (`DBEdit9`, LH-Zeile, `Top=43`, dieselbe Bindung). Klassischer Copy-Paste-Fehler im Originalformular: `DBEdit10` wurde offenbar aus `DBEdit9` dupliziert, das `DataField` aber nie angepasst. Beide Felder sind `ReadOnly`, der Fehler ist also rein anzeigeseitig (keine Datenkorruption), macht aber `ZeichnungsNr3` in diesem Dialog dauerhaft unsichtbar – selbst falls dort echte Daten stehen, zeigt die FY-Zeile immer den LH-Wert |

#### Reiter "Buchungen": Lagerbewegungsjournal, vollständig aufgeklärt

Validiert 2026-09-09 – exakte SQL-Query gefunden. Zwei baugleiche Tabellen
bilden die Sub-Tabs **Aktive**/**Historie**:

```sql
with AllBuchung as (
  select 'Aktiv' as Art, ... from lagerbuchung where artoid = :parOID
  union
  select 'Hist ' as Art, ... from lagerbuchung_HIST where artoid = :parOID2
)
```

`LAGERBUCHUNG`/`LAGERBUCHUNG_HIST` (baugleich: `OID`, `ARTOID`, `POSOID`,
`BELEGOID`, `LAGEROID`, `AUFTRAGOID`, `BUCHUNGSOID`, `MENGE`, `BEMERKUNG`,
`DATUM`, `STORNO`).

| Grid-Spalte | Herkunft |
|---|---|
| BUCHDATUM | `LAGERBUCHUNG.DATUM` |
| MENGE | `LAGERBUCHUNG.MENGE` |
| **Bestand** | **kein gespeicherter Wert** – live berechnete laufende Summe aller Buchungen bis zu diesem Datum (korrelierte Subquery `Sum(Menge) ... where Datum <= L.Datum`) |
| Nummer / BELEGDATUM | verlinkter `BELEG` (über `BELEGOID`/`AUFTRAGOID`), außer bei Fertigungs-/Inventurbuchungen – dann `L.Belegoid`/`L.Datum` direkt |
| VORGANGART | **berechnet, kein Feld**: `'Produktion'` bei Bemerkungstext wie `Fertigmeldung%`/`%Prod%`, sonst die Belegbezeichnung des verknüpften Belegs |
| BEMERKUNG | `LAGERBUCHUNG.BEMERKUNG` – reines Freitextfeld; "Inventur…Wert: …" ist einfach hineingeschriebener Text, kein strukturiertes Feld |
| **BG** (Baugruppe) | bei Materialentnahmen während der Produktion (`Bemerkung like 'Entna%'`) per Subquery über `PRODUKTION`→`STUECKLISTEN` ermittelt: zeigt die übergeordnete Baugruppe, aus der das Material entnommen wurde |

**Beobachtung:** Mehrere fachlich unterschiedliche Vorgänge (reguläre
Belegbuchungen, Fertigungsentnahmen, Inventurzählungen) werden über
Bemerkungstext-Mustererkennung (`LIKE 'Fertigmeldung%'`, `'%Inven%'`,
`'Entna%'`) unterschieden statt über ein strukturiertes Typfeld – Freitext
übernimmt hier die Rolle einer fehlenden Kategorisierungsspalte. Odoo würde
das über `stock.move` mit einem echten `picking_type_id` lösen.

#### Reiter "Teileverwendung": Where-used-Bericht, Gegenstück zur Stückliste

Validiert 2026-09-09 über zwei Live-Screenshots (einmal leer, einmal mit
Daten). Zeigt, in welchen übergeordneten Baugruppen der aktuelle Artikel als
Bauteil verwendet wird – umgekehrte Richtung zur Stückliste. Bestätigter
Mechanismus:

```sql
Select A.OID, S.Nummer from Stuecklistenartikel A, Stuecklisten S
where A.ArtOID = :parOID and A.Soid = S.OID
```

| UI-Spalte | DB-Feld |
|---|---|
| Nummer | `STUECKLISTEN.NUMMER` (der übergeordneten Baugruppe) |
| Bezeichnung | `STUECKLISTEN.BEZEICHNUNG1` (der übergeordneten Baugruppe) |
| Pos | `STUECKLISTENARTIKEL.NUMMER` (Position innerhalb der Baugruppe) |
| Menge | `STUECKLISTENARTIKEL.ANZAHL` |

Live-Beispiel: ein Artikel erscheint in Baugruppe "2927 – Druckschutzklappen
System kpl" an Position 33 mit Menge 1,00 – bestätigt exakt die erwartete
Spaltenzuordnung. Beim zuvor gezeigten Klimagerät (40803-ETL) ist die Liste
leer, weil dieses selbst die oberste Ebene seiner eigenen Stückliste ist und
in keiner anderen Baugruppe als Bauteil vorkommt.

Odoo-Bezug: entspricht nativ Odoos "Where Used"/"Used In"-Funktion auf
`product.template` (invertierte `bom_line_ids`) – kein struktureller
Unterschied, funktional 1:1 abbildbar.

#### Reiter "Einkauf": Bestellhistorie je Artikel, vollständig über DFM bestätigt

Validiert 2026-09-09. Fünf Sub-Tabs: Bestelliste/Anfrage/**Bestellung**/
Rahmenbestellung/Belastungsanzeige. Grid-Spalten des "Bestellung"-Sub-Tabs
(`TCheckDBGrid dbgBestellungen` → `DataSource dsBestellungen`) direkt aus der
DFM-Spaltendefinition, keine Vermutung nötig:

| UI-Spalte | `FieldName` | DB-Feld |
|---|---|---|
| Belegnr. | `Nummer` | `BELEG.NUMMER` |
| Lieferdatum | `Liefertermin` | `BELEGPOS.LIEFERTERMIN` |
| Name | `name1` | `BELEG.NAME1` |
| Artikel | `artnr` | `BELEGPOS.ARTNR` |
| Menge | `stck` | `BELEGPOS.STCK` |
| Geliefert | `Geliefert` | `BELEGPOS.GELIEFERT` |
| Preis | `Epreis` | `BELEGPOS.EPREIS` |
| **Rp-Preis** | `Lieferpreis` | `BELEGPOS.LIEFERPREIS` – eigenständiges Feld für den tatsächlichen Lieferpreis, unabhängig vom bestellten Preis; erklärt Live-Beispiele mit stark abweichenden Preis-/Rp-Preis-Werten |
| Preis PE | `PreisPreiseinheit` | `BELEGPOS.PREISPREISEINHEIT` |
| Rabatt | `RABATT` | `BELEGPOS.RABATT` |
| PE | `Preiseinheit` | `BELEGPOS.PREISEINHEIT` |
| G. (Checkbox) | `abgeschlossen` | vermutlich `BELEG.ABGESCHLOSSEN` je Zeile mitgeführt |

Der "Rahmenbestellung"-Sub-Tab bestätigt dieselben, bereits aus dem
Einkaufs-Kapitel bekannten `BELEG`-Felder direkt über die DFM-Spalten:
`Abrufmenge`→"Menge", `Bestelltermin`→"Laufz. von", `Liefertermin`→"Laufz. bis",
`Rahmennr`, `Abrufpreis`, `projekt`.

#### Reiter "Vertrieb": Verkaufs-/Reparaturhistorie je Artikel

Validiert 2026-09-09. Fünf Sub-Tabs: Angebot/Auftrag/Lieferschein/Rechnung/
**Reparatur**. Der Reparatur-Sub-Tab entspricht exakt einer bereits früher
gefundenen `UNION`-Query (siehe Reparatur-Abschnitt weiter unten), jetzt mit
sichtbarem UI-Kontext und echten Daten:

```sql
select B.Nummer, B.Name1, B.Belegdatum, trim(K.Anrede) as Herkunft,
  P0.stck, P0.text, P0.Artnr, p0.soid, 'Mat.' as Art
from Belegpos P0, Beleg B, Repkopf K
where B.Belegart = 154 and P0.Soid = B.oid and B.nummer = K.Belegnummer and P0.ArtOID = :parOID
union select ..., 'Kost1.' as Art from Repkpos P1, Beleg B, Repkopf K where ...
union select ..., 'Kost2.' as Art from Repkpos2 P1, Beleg B, Repkopf K where ...
union select ..., 'St...' as Art from Repbuchartikel P3, Beleg B, Repkopf K where ...
```

| UI-Spalte | Herkunft | DB-Feld |
|---|---|---|
| Beleg | `B.Nummer` | `BELEG.NUMMER` |
| Datum | `B.Belegdatum` | `BELEG.BELEGDATUM` |
| Name | `B.Name1` | `BELEG.NAME1` (Kunde) |
| Stck. | `P0.stck` | `BELEGPOS.STCK` |
| Artikel | `P0.text` | **`BELEGPOS.TEXT`** – trotz Spaltentitel "Artikel" wird die Beschreibung angezeigt, nicht `ARTNR` |
| Art | Literal `'Mat.'`/`'Kost1.'`/`'Kost2.'`/`'St...'` | keine Spalte, sondern Konstante je `UNION`-Zweig – kennzeichnet die Quelltabelle (`Belegpos`/`Repkpos`/`Repkpos2`/`Repbuchartikel`) |
| Herkunft | `trim(K.Anrede)` | `REPKOPF.ANREDE`, wiederverwendet – Live-Werte wie "Kassel", "Bellinzona", "Kamenz" bestätigen endgültig, dass dieses Feld hier als Einsatzort dient (siehe auch Korrektur im Reparatur-Abschnitt) |

**Funktionsweise:** artikelübergreifende Reparaturhistorie – für welchen
Kunden, an welchem Standort und wann ein bestimmtes Ersatzteil verbaut
wurde, über vier interne Positions-/Verbrauchstabellen hinweg
zusammengeführt. Die übrigen vier Sub-Tabs zeigen vermutlich dieselbe
Grid-Form mit `Belegart` 100/101/102/103 statt 154, ohne die
REPKPOS/REPBUCHARTIKEL-Zusatzquellen (nicht einzeln geprüft).

#### Reiter "Reservierung (Auftrag)": Materialbedarf anderer Fertigungsaufträge

Validiert 2026-09-09. Bestätigte Query:

```sql
Select Anzahl, Prodmenge, Artnr, Bezeichnung1, Kw, Jahr
from V_BereitMaterial
where Artoid = :parOID And not ProdOID = :parAuftrag
```

| UI-Spalte | Herkunft |
|---|---|
| Anzahl | `V_BereitMaterial.Anzahl` |
| KW | `V_BereitMaterial.Kw` |
| Jahr | `V_BereitMaterial.Jahr` |

Zeigt Zeilen der View nur mit den drei relevanten Spalten (`Artnr`/
`Bezeichnung1` entfallen, da der Artikel bereits im Fenstertitel steht;
`Prodmenge` im Grid nicht übernommen). `V_BereitMaterial` ist dieselbe
View-Familie, die dem "Materialengpass"-Indikator im **EngpassCockpit**
(Produktions-Kapitel) zugrunde liegt: `not ProdOID = :parAuftrag` schließt
den aktuell betrachteten Auftrag aus und zeigt, ob dieser Artikel
anderweitig – für andere Fertigungsaufträge – bereits benötigt/reserviert
ist, gegliedert nach Kalenderwoche/Jahr des Bedarfstermins.

Odoo-Bezug: am ehesten Odoos Bedarfsvorschau (Reservierungen aus offenen
`mrp.production`/`sale.order`-Zeilen), aber mit konkreten Terminen statt der
hier nativen KW/Jahr-Granularität.

#### Reiter "Kommision": offener Kommissionierbedarf je Baugruppe

**Korrigiert 2026-09-09 durch echte DFM-Extraktion** (siehe
[dfm-tool/](legacy-schema/dfm-tool/README.md) – ein selbstgebauter Decoder
für das binäre Delphi-DFM-Format, direkt aus `Herrmann.exe` extrahiert).
Die vorherige Version dieser Zeile stützte sich nur auf plausibilisierte
Feldnamen aus verwandten Queries; jetzt liegt die exakte Grid-Spaltendefinition
vor (`dbgKomm: TDBGrid`, `DataSource = dsKomm`, Tab `tshKomm`):

| UI-Spalte | Reales `FieldName` | Anmerkung |
|---|---|---|
| KW | `Kw` | |
| Jahr | `Jahr` | |
| Restmenge | **`Anzahl`** | kein berechnetes `Sollmenge-Buchmenge`, sondern ein eigenes, so benanntes Datensatzfeld – frühere Vermutung war falsch |
| SOLLMEN(GE) | `Sollmenge` | |
| Baugruppe | **`Stuecknummer`** | ein eigener Alias, nicht direkt `STUECKLISTEN.NUMMER` – frühere Vermutung falsch |
| Bezeichnung | **`stbez`** | eigener Alias (vermutlich "Stückliste Bezeichnung"), nicht `STUECKLISTEN.BEZEICHNUNG1` direkt |
| Prodmenge | `Prodmenge` | |
| Fertig | `Fertig` | |
| *(im Grid ausgeblendet, aber im Dataset vorhanden)* | `Auftragnummer`, `Kunde` | `Visible = False` – zwei weitere Felder, die das Dataset mitführt, aber nicht anzeigt |

Die zugrundeliegende SQL-Quelle (`V_ProdMaterial` o. Ä.) bleibt weiterhin
nicht im Klartext auffindbar – Aliase wie `Anzahl`/`Stuecknummer`/`stbez`
werden vermutlich dynamisch im Pascal-Code gesetzt (siehe Grenzen der
DFM-Methode im Tool-README).

**Funktionsweise:** zeigt, für welche Baugruppen/Fertigungsaufträge dieser
Artikel noch offen ist (`Sollmenge - Buchmenge > 0`, also noch nicht
vollständig aus dem Lager entnommen/gebucht), gegliedert nach
Kalenderwoche/Jahr. Funktional eng verwandt mit "Reservierung (Auftrag)",
aber mit Fokus auf den tatsächlichen Kommissionierstatus statt bloßer
Reservierung. Alle drei Tabs (EngpassCockpit, Reservierung, Kommission)
greifen auf dieselbe `V_ProdMaterial`/`V_BereitMaterial`-Sichtenfamilie
zurück – ein zentraler, wiederverwendeter Verfügbarkeits-Berechnungskern für
die gesamte Produktionsplanung.

#### Reiter "Inventurwerte": jede Inventur ist eine eigene Datenbanktabelle

Validiert 2026-09-09 – bemerkenswertester Einzelfund im gesamten
Artikelinfo-Fenster. Bestätigte, dynamisch gebaute Query:

```sql
Select cast('<tabellenname>' as varchar30) as Inventur,
  cast(Inventurdatum as varchar10) as Vom,
  Artnr, Bezeichnung1, Bestand as Sollbestand, Istbestand, Lagerorte
from <tabellenname> where OID = ...
UNION Select ... from <nächste Tabelle> ...
-- (dynamisch pro vorhandener Inventur-Tabelle wiederholt)

with AllInv as ( ... ) Select * from AllInv order by Inventur desc
```

**Die Spalte "INVENTUR" enthält keinen Code, sondern den tatsächlichen
Tabellennamen.** Format entschlüsselt: `Inventur0` + Datum als `JJJJMMTT`
(z. B. `Inventur020251215` = 15.12.2025, `Inventur020210104` = 04.01.2021 –
beide gegen die zugehörige VOM-Spalte verifiziert). **Für jede einzelne
Inventurzählung wird offenbar eine eigene, neue Tabelle angelegt**, nicht
eine Zeile in einer gemeinsamen Tabelle – dieser Tab führt sie per
dynamisch gebautem `UNION` zu einer historischen Liste zusammen. Passt zum
bereits dokumentierten Muster datierter Einzeltabellen (`ARTIKEL_N`,
`PRODARTIKEL020100727`, `INVENT0701`), hier aber als durchgängiges,
jährlich wiederkehrendes Verfahren statt einmaliger Altlast – der
extremste bisher gefundene Ausprägung dieses Architekturmusters.

| UI-Spalte | Herkunft |
|---|---|
| INVENTUR | Tabellenname selbst (als Text gecastet) |
| VOM | `Inventurdatum`-Spalte der jeweiligen Tabelle |
| SOLLBESTAND | `Bestand`-Spalte, umbenannt (wiederverwendet) |
| ISTBESTAND | `Istbestand` |
| LAGERORTE | `Lagerorte` (kommagetrennte Liste, z. B. "H-01,") |

Odoo-Bezug: entspricht `stock.inventory`/`stock.quant` mit Inventurhistorie,
aber ohne separate Tabellen je Zählung – in Odoo sind alle Inventuren Zeilen
derselben Tabelle.

## Detailvergleich: Einkauf/Bestellung

Anders als bei Adressen/Artikel/Reparatur lag hier noch kein Screenshot-basierter
Vorvergleich vor – dieser Abschnitt ist direkt aus dem realen Schema und der
aktuellen EXE abgeleitet (reines Reverse Engineering, keine Validierung
bestehender Behauptungen).

**Kernbefund:** Es gibt zwei parallele Tabellenwelten. `BESTELLKOPF`/`BESTELLPOS`
(2011-Schema, schlanke Struktur mit ca. 20 Feldern) existieren zwar noch und
werden von einer neueren Statistik-Prozedur `P_BestellPos` sowie vereinzelten
einfachen Inserts angesprochen – der eigentliche Bestellprozess läuft aber, wie
bei Auftrag/Lieferschein/Reparatur, über den generischen `BELEG`/`BELEGPOS`-Kopf
mit unterschiedlichen `BELEGART`-Werten (bestätigt über die Formular-ID-
Konstanten in `HMS/Module/UConsts.pas` – lokal unter `Herrmann_Work/`, nicht
Teil dieses Repos – und über Live-SQL aus der aktuellen EXE):

| Menüpunkt | BELEGART | Beleg-Ebene |
|---|---|---|
| Bestellung | 105 | `BELEG`/`BELEGPOS`, `fidBestellungValue` |
| Rahmenbestellung | 74 | `BELEG` (Kopf mit Abruf-Feldern), `fidBlockBestellungValue` |
| Anfrage | 118 | `BELEG`, `fidAnfrageValue` |
| Rechnungsprüfung | – (kein eigener Belegtyp) | Flags auf `BELEGPOS` (`GEPRUEFT`, `RECHFREIGABE`) |
| Bestellliste | – | reine Listenansicht über `BELEG` mit `Belegart = 105` |

Rahmenbestellungen (Belegart 74) sind kein separates Objekt, sondern ein
`BELEG`-Kopf mit eigenen Abruf-Feldern (`ABRUFMENGE`, `ABRUFARTIKEL`,
`ABRUFPREIS`, `RAHMENNR`), gegen den einzelne reguläre Bestellpositionen über
`BELEGPOS.RAHMENOID` "abgerufen" werden – Restmenge wird dabei nicht aus der
gespeicherten Spalte gelesen, sondern live nachgerechnet:

```sql
Select B.Abrufmenge, B.oid, B.Nummer as Rahmennr, B.Name1 as RahmenLiefer,
  (Select coalesce(Sum(geliefert), 0) from Belegpos P where P.Rahmenoid = B.OID)
from beleg B where Abrufartikel = :parOID and B.Belegart = 74 and Abgeschlossen = 'F'
```

| Feld (aktuelles ERP) | Odoo-Äquivalent | Anmerkung |
|---|---|---|
| `BELEG.NUMMER`/`BELEGDATUM`/`ADROID` (Lieferant) | `purchase.order.name`/`date_order`/`partner_id` | nativ |
| `BELEG.BEARBEITER`/`BEARBEITERFON`/`BEARBEITERFAX`/`BEARBEITEREMAIL` | `user_id` | Odoo hat nur den Benutzer als Sachbearbeiter, keine separaten Kontaktfelder je Beleg – die wären hier redundant zum Benutzerprofil gepflegt |
| `BELEG.LIEFERTERMIN`/`BESTELLTERMIN`/`WUNSCHTERMIN` (3 verschiedene Termine) | `date_planned` (ein Feld) | **Lücke**: Odoo kennt nur einen geplanten Termin je Order, das Altsystem unterscheidet Liefer-/Bestell-/Wunschtermin auf Kopfebene zusätzlich zu `BELEGPOS.LIEFERTERMIN`/`LIEFERTERMINSOLL`/`ABTERMIN` je Position |
| `BELEG.KOPFTEXT`/`FUSSTEXT` | Notizen (`notes` o.ä.) | kein separates Kopf-/Fußtext-Konzept, wie bereits bei Reparatur notiert |
| `BELEG.RAHMENNR`/`ABRUFMENGE`/`ABRUFARTIKEL`/`ABRUFPREIS`/`KONTRAKT` (Rahmenbestellung, Belegart 74) | kein Standardmodul | Odoo Community hat kein Blanket-Order-Konzept; Enterprise `purchase.requisition` kommt am nächsten, ist aber strukturell anders (RFQ-Bündelung statt Abruf-gegen-Kontrakt) |
| `BELEGPOS.ARTOID`/`ARTNR`/`BESTELLMENGE`(`STCK`)/`EPREIS` | `purchase.order.line` (`product_id`/`product_qty`/`price_unit`) | nativ |
| `BELEGPOS.GELIEFERT` (gelieferte Menge) | `qty_received` | nativ, 1:1 |
| `BELEGPOS.RAHMENOID`/`RAHMENTEXT`/`ABRAHMEN` | kein Feld | Verknüpfung einer Bestellposition zu ihrer Rahmenbestellung – ohne natives Blanket-Order-Konzept in Odoo Community entfällt auch diese Verlinkung |
| `BELEGPOS.GEPRUEFT`/`RECHFREIGABE` (Rechnungsprüfung) | implizit über Rechnungsabgleich (`qty_invoiced` vs. `qty_received`) | Odoo hat keinen expliziten "geprüft"/"freigegeben"-Haken auf der Bestellzeile, sondern automatischen 3-Way-Match; eine manuelle Freigabe-Checkbox wie hier fehlt |
| `BELEGPOS.RGNRLIEF`/`RGNRINTERN` (Lieferanten-/interne Rechnungsnummer je Position) | `account.move.ref` (auf Rechnungsebene, nicht je Zeile) | **struktureller Unterschied**: Rechnungsnummern hängen hier an der Bestellzeile, in Odoo an der Rechnung als Ganzes |
| `BELEGPOS.BESTTERMIN`/`BESTBEMERK` | kein 1:1-Feld | zusätzliche Bestell-Termin-/Bemerkungsfelder je Position, über die üblichen Liefertermine hinaus |

**Beobachtung:** Der Bestellkern (Kopf/Position, Lieferant, Menge, Preis,
Liefertermin/-menge) deckt sich gut mit `purchase.order`. Die beiden größten
Lücken sind strukturell, nicht nur fehlende Felder: (1) das Abruf-gegen-Rahmen-
Modell für Rahmenbestellungen hat in Odoo Community keine Entsprechung, und
(2) die Rechnungsprüfung hängt hier an einzelnen Bestellzeilen-Flags statt an
einem eigenständigen 3-way-match-Prozess wie in Odoo.

### Pascal-Quellcode (FBestellungTSP.pas): Wareneingangsbuchung löst 8D-Belastung aus

Validiert 2026-09-10 durch Lesen von `HMS/Module/Bestellung/FBestellungTSP.pas`
(1960 Zeilen, Klasse `TfrmBestellungTSP`, Stand 2018). Klärt den bisher nur
über Formularnamen vermuteten Zusammenhang zwischen "8D Lieferant" und
"Belastungsanzeige" (siehe Artikelinfo-Abschnitt) mit konkretem Code:

- **`btnBuchenClick`** (Wareneingang buchen) ist mit Qualitäts-Gates verriegelt: ist der Artikel `ISPruefeArtikel`/`ISZeugnisArtikel`-pflichtig, blockiert die Buchung, bis `BELEGPOS.GEPRUEFT='T'` bzw. ein neu gefundenes Feld `BELEGPOS.ZEUGNIS='T'` gesetzt ist.
- **Bestätigt: Kanban-Buchungsmechanismus.** `TBucheKanbanArtikel.Execute(...)` bucht den Artikelbestand normalerweise; ist `BELEGPOS.REPLAGER='T'`, läuft stattdessen `TBucheKanbanArtikel.ExecuteReplager(...)` – ein separater Buchungspfad fürs Reparatur-Lager, bestätigt die schon gefundene Sonderrolle von `REPLAGER`.
- **Der Auslöser für "8D Lieferant"/"Belastungsanzeige" ist jetzt bewiesen:** Ist beim Buchen eine Ausschussmenge (`dbeAusschuss`) > 0 eingetragen, ruft `btnBuchenClick` automatisch `CreateBelastungsAnzeige` auf. Diese Prozedur legt einen neuen `BELEG` mit `fidBelastungValue` an, mit dem Bezeichnungstext **"8D Lieferant"** wörtlich im Code (`TCreateBeleg.Execute(fidBelastungValue, ..., 'G_NrBelastung', '', '8D Lieferant', ...)`) – endgültige Bestätigung, dass Belastungsanzeige und 8D-Lieferant-Reklamation ein und derselbe Vorgang sind, ausgelöst durch Ausschuss bei der Wareneingangsprüfung.
- **Erklärt die `*_FM.xls`-Dateien im Herrmann_Work-Ordner:** `CreateBelastungsAnzeige` ruft am Ende `TCreateExcel8D.Execute(...)` auf und schreibt die Datei nach `CurrentEnvirement.Pfade.AchtDLPath` – automatisch generierte Excel-Exporte je 8D-Vorgang. Das sind exakt die zu Sitzungsbeginn gefundenen `*_FM.xls`-Dateien im Wurzelverzeichnis.
- Feldbestätigungen aus den `TSetBelegField`/`TSetBelegPosField`-Aufrufen: `Bearbeiter`, `Bestelltermin`, `BestellNr`, `Liefname3` (befüllt mit der **Nummer der ursprünglichen Bestellung** – erneute Feld-Zweckentfremdung), `Bearbeiterfon`, `Achtdnrlieferant`, `Bestellmenge`, `Ausschussmenge`.

## Detailvergleich: Produktion

Wie beim Einkauf: reines Reverse Engineering ohne Screenshot-Vorlage, direkt
aus Schema + Live-SQL der aktuellen EXE abgeleitet.

**Struktur:** Zwei Ebenen – Routing-*Vorlagen* (`KONST...`-Tabellen, wieder-
verwendbare Produktionsarten) und konkrete Fertigungsaufträge (`PRODUKTION` +
Ableger). Beide zusammen bilden fast 1:1 Odoos `mrp`-Modell ab:

| Vorlage (aktuelles ERP) | Odoo-Äquivalent | Instanz (aktuelles ERP) | Odoo-Äquivalent |
|---|---|---|---|
| `KONSTPRODART` (Produktionsart, mit `PRODSTRASSE`) | `mrp.routing` (Konzept) | `PRODUKTION` (Fertigungsauftrag) | `mrp.production` |
| `KONSTPRODSTRASSEN` (Produktionsstraße) | – (kein direktes Pendant, am ehesten Arbeitsplatz-Gruppierung) | – | – |
| `KONSTPRODSCHRITTE` (`PMANNZEIT`/`PMASCHZEIT`/`PMASCH`) | `mrp.routing.workcenter` (Mann-/Maschinenzeit je Schritt) | `PRODSCHRITTE` (`PRODMENGE`/`FERTIGMENGE` je Schritt) | `mrp.workorder` |
| `KONSTPRODMASCHINEN` (`ZKONFIG`/`ZPRODUKT`) | `mrp.workcenter` (Rüst-/Stückzeit) | `PRODZEITEN`/`PRODZEITENSCHRITT` (Zeitbuchung je Nutzer/Schritt) | `mrp.workcenter.productivity` |
| `KONSTPRODFEHLER` (Fehlerkatalog, `KRITISCH`-Flag) | `quality.point`/Fehlerkatalog | `PRODFEHLER` (`FEHLERANZAHL`, `KRITISCH`, `FREI_DURCH`/`FREI_AM` = Freigabe-Workflow) | `quality.check`/`quality.alert` |

**EngpassCockpit/Cockpit sind kein eigenes Modul, sondern vorberechnete Spalten
direkt auf `PRODUKTION`.** Bestätigt über die reale Ladequery der aktuellen EXE:

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

Die UI unterscheidet außerdem explizit zwei Engpass-Dimensionen
("Materialengpass, Materialstatus", "Personalengpass") – im Schema nicht als
eigene Felder, sondern aus den `Count*`-Spalten plus `EKStatus`/`CriticPath`
abgeleitet. Odoo hat kein eingebautes Bottleneck-Cockpit dieser Art; am
nächsten kommt eine kombinierte Auswertung aus offenen `mrp.workorder` +
`stock.warehouse.orderpoint`/Beschaffungsausnahmen, aber ohne die hier
vorberechneten Engpass-Zähler.

| Menüpunkt | Reales Backing | Odoo-Äquivalent | Anmerkung |
|---|---|---|---|
| Laufkarten | **kein eigenes Objekt** | `mrp.workorder`-Report | Wird über den generischen `BELEG`-Kopf mit variablem `BELEGART`-Parameter gerendert, wobei fachfremde Felder umbenannt wiederverwendet werden (z. B. `RECHNAME2 as Arbeitsschritt`, `Achtdnrlieferant as Verantwortl`) – ungewöhnliches, aber bestätigtes Wiederverwendungsmuster |
| Begleitschein | eigene Tabelle `BEGLEITSCHEIN` (`Bezeichnung`, `Ausfallnr`, `Ausfertigung`, `Artikelname`, `Snr`, `Identnr`) | `stock.picking`-Lieferschein/Report | Laut Code-Kommentar ("siehe auch Reparaturbegleitschein") mit Reparatur cross-referenziert, `Ausfallnr` verweist vermutlich auf `REPAUSFALL` |
| FAM | kein eigenes Feld/Tabelle, nur `BELEG.FAMID` + Dateiablage (`FAM\*.xls`, siehe `Herrmann_Work\*_FM.xls`) | kein Pendant | Fertigungsauftragsmappe ist dateibasiert, nicht datenbankgestützt – für eine Odoo-Migration ohnehin nicht 1:1 übertragbar |
| 8DIntern / 8D-Kunde | `PRODFEHLER` + `KONSTPRODFEHLER` (Katalog) | `quality.alert` (kein natives 8D-Formular) | Bestätigt bereits im Modulzuordnungs-Abschnitt vermutete Lücke, jetzt mit konkretem Tabellenbezug |
| Übersicht Stücklisten | `STUECKLISTEN`/`STUECKLISTENARTIKEL` (siehe Artikel-Abschnitt) | `mrp.bom`-Report | nativ abbildbar |

**Beobachtung:** Der Fertigungskern (Routing-Vorlage → Fertigungsauftrag →
Arbeitsschritt → Zeitbuchung) deckt sich strukturell überraschend gut mit
Odoos `mrp`-Modell – auffälliger als bei Einkauf oder Reparatur. Die größte
Eigenheit ist das EngpassCockpit: kein separates Modul, sondern zehn
vorberechnete Zähler-/Statusspalten direkt auf dem Fertigungsauftrag, die bei
jeder Anzeige neu abgefragt (nicht in Odoo-typischer Reporting-Manier live
aggregiert) werden – eine Migration müsste diese Vorberechnung entweder als
computed fields auf `mrp.production` nachbauen oder durch eine
Standard-Odoo-Reporting-Ansicht ersetzen.

### Pascal-Quellcode (FProduktion.pas): "In Fertigung nehmen"-Workflow

Validiert 2026-09-10 durch Lesen von `HMS/Module/Produktion/FProduktion.pas`
(2521 Zeilen, Klasse `TfrmProduktion`). `actInFertigungExecute` ist der
Übergang von `PRODUKTIONBEREIT` (Bereitstellungs-Vormerkung) zu einer
tatsächlich terminierten `PRODUKTION`-Zeile:

1. Prüft Artikelsperre (`TGetArtikelsperre.GetSperrebyStueckOID`) – bricht mit Fehlermeldung ab, wenn der Artikel gesperrt ist.
2. Prüft Auftragsstatus (`TGetProdAuftragStatus`).
3. Bietet eine **Splitt-Entscheidung** an (`TfrmVorlaufDlg`): nicht splitten (`nichtSplitten`, ganze Menge in einem Fertigungslauf) oder nach Baugruppen aufteilen (`inBaugruppensplitten`).
4. **Terminierung rückwärts vom Bedarfstermin:** `TGetWorkDays.Execute(AProdDatum, AVorlauf, Zurueck)` zieht die Vorlaufzeit in **Werktagen** (nicht Kalendertagen) vom Bedarfsdatum ab, um den Produktionsstart zu bestimmen – daraus werden `KW`/`Jahr` für die neue `PRODUKTION`-Zeile abgeleitet (`WeekOf`/`YearOf`).
5. `TSetFertigung.Create(...)` legt den eigentlichen Fertigungsauftrag an.

Bestätigt damit, dass die überall auftauchenden `KW`/`Jahr`-Felder aus einer
echten Werktage-Rückwärtsterminierung stammen, nicht aus freier Eingabe.

## Detailvergleich: Vertrieb

Wieder reines Reverse Engineering ohne Screenshot-Vorlage. Angebot, Auftrag,
Lieferschein und Rechnung folgen demselben Muster wie Bestellung/Reparatur:
derselbe `BELEG`/`BELEGPOS`-Kopf, unterschieden nur über `BELEGART`
(bestätigt über `UConsts.pas` + Live-SQL):

| Menüpunkt | BELEGART | Bestätigung |
|---|---|---|
| Angebot | 100 | `AngeboteBG`-Query |
| Auftrag | 101 | `AuftragRestWert`-Query |
| Lieferschein | 102 | `case when B.Belegart = 102 then 'Lieferschein'` |
| Rechnung | 103 | `B.Belegart = 103` |
| Mahnung | 104 | `fidMahnungValue`, `BELEGPOSMAHN`-Verknüpfungstabelle |
| Abschlagrechnung (**nicht** "Abschlussrechnung"!) | 108 | `fidRechnungAbschlagValue`; UI-Strings "Abschlagrechnung1", "abzgl. Zahlung zu Abschlagrechnung Nr." |
| Vertreterabrechnung | 115 | `B.BelegArt = 115`, View `V_Vertreter` |

**Korrektur zum ursprünglichen Menüpunkt:** Was im Screenshot als
"Abschlussrechnung" gelesen wurde, heißt im System durchgängig
**"Abschlagrechnung"** – das ist eine Anzahlungs-/Teilrechnung (mit Verrechnung
gegen die Schlussrechnung: "abzgl. Zahlung zu Abschlagrechnung Nr. ..."), keine
Schlussrechnung nach Teillieferungen. Das ändert die Odoo-Zuordnung deutlich
zum Positiven: Odoo hat mit `sale.advance.payment.inv`/Anzahlungsrechnungen
ein natives Äquivalent, während eine echte "Abschlussrechnung" (Sammelrechnung
über mehrere Lieferscheine) in Odoo umständlicher wäre.

**Dokumentenkette:** Lieferschein/Rechnung referenzieren den ursprünglichen
Auftrag über `BELEG.HAUPTAUFTRAG` (Belegnummer, kein OID-Fremdschlüssel):

```sql
Select B.HauptAuftrag as Auftrag, b.Nummer, b.AdrNr, b.OID as BelegOID, b.netto,
  b.Belegdatum, bp.Bestellnr, b.endpruefdatum, b.name1, b.abgeschlossen,
  bp.Epreis, bp.stck, bp.Rabatt, bp.GPreis, bp.Geliefert, bp.artnr, bp.text
from Beleg b, Belegpos bp
where (b.Belegart = :art) and bp.artoid = :oid and b.oid = bp.soid
ORDER by B.Belegdatum desc
```

Das entspricht in Odoo grob der Kette `sale.order` → `stock.picking`/
`account.move` mit `origin`-Feld, nur dass hier die Belegnummer (nicht die
OID) die Klammer bildet – ein Bruch der referenziellen Integrität ist damit
strukturell möglich (Nummern können sich theoretisch überschneiden), was
Odoos FK-basierte Verknüpfung nicht zulässt.

| Feld/Bereich (aktuelles ERP) | Odoo-Äquivalent | Anmerkung |
|---|---|---|
| `BELEG.HAUPTAUFTRAG` (Auftragsbezug auf Folgebelegen) | `origin`-Feld (`stock.picking`/`account.move`) | funktional ähnlich, aber String-/Nummernbezug statt FK |
| Mahnung: `BELEGPOSMAHN` (`RECHNR`, `RECHOID`, `MAHNKZ`, eigene `NETTO`/`MWST`/`BRUTTO`) | `account.move`-Follow-up-Reports | Odoo bucht Mahnstufen nicht als eigenen Beleg mit eigener Positions-/Summenkopie, sondern als Report über offene Posten |
| Vertreterabrechnung: `V_Vertreter`-View, `BELEGPOS.PROVISION`, `ADRESSEN.PROVISION`/`PROVISION2`/`ISVERTRETER` | kein natives Modul | bestätigt bereits vermutete Lücke; Provisionssatz sitzt sowohl am Vertreter (Adressen) als auch potenziell je Belegposition (Override) |
| Prodauftrag (Auftrag → Fertigungsauftrag) | `mrp.production` mit `origin` = `sale.order` | bestätigt über UI-Klassen `TCreateProdAuftrag`/`TfrmProdAuftragDlg`, erzeugt einen `PRODUKTION`/`PRODUKTIONBEREIT`-Datensatz (siehe Produktion-Abschnitt) aus dem Auftrag heraus – funktional entspricht das Odoos automatischer MO-Erzeugung aus `sale.order.line`, hier aber ein expliziter manueller Dialog statt automatischer Regel |
| Reparatur | siehe eigener Abschnitt oben | Reparatur läuft als `BELEG` mit `BELEGART = 154`, taucht im Vertriebsmenü nur als weiterer Belegtyp neben Angebot/Auftrag/Rechnung auf |

**Beobachtung:** Der Vertriebskern bestätigt die schon vermutete gute
Odoo-Passung (`sale`+`stock`+`account`), mit einer wichtigen Korrektur
(Abschlagrechnung statt Abschlussrechnung – eher eine Stärke als eine Lücke)
und einer strukturellen Eigenheit: Der gesamte Belegfluss hängt an der
Belegnummer als lose Klammer (`HAUPTAUFTRAG`), nicht an Fremdschlüsseln – bei
einer Migration nach Odoo würde das durch echte FK-Referenzen ersetzt und
dadurch tendenziell robuster.

### Pascal-Quellcode (FAuftragTSP.pas): HAUPTAUFTRAG-Ursprung, Beleg-Kette, tote Menüpunkte

Validiert 2026-09-10 durch Lesen von `HMS/Module/Belege/FAuftragTSP.pas`
(1222 Zeilen, Klasse `TfrmAuftragTSP`):

- **`HAUPTAUFTRAG` entsteht als Selbstreferenz bei Neuanlage:** `btnInsertClick` setzt beim Anlegen eines neuen Auftrags `BELEG.HAUPTAUFTRAG := BELEG.NUMMER` (die eigene Nummer) – das ist die "Wurzel" der später von Lieferschein/Rechnung übernommenen Belegkette, jetzt mit Code belegt statt nur vermutet.
- **Auftrag → Lieferschein bestätigt:** `pmiLieferscheinClick` ruft `DataModul.CopyChangeBelegAuftragLieferschein(...)` auf (eine Beleg-Kopier-Prozedur), danach `DataModul.SetFullGeliefert(...)`.
- **Vier Menüpunkte sind tote Hüllen:** `pmiBestellungClick`, `pmiSammellieferscheinClick`, `pmiRechnungClick`, `pmiSammelrechnungClick`, `Abschlagrechnung1Click` und `Schlussrechnung1Click` enthalten **keinen Code** (nur ein Kommentarzeichen) – diese Menüpunkte existieren in der UI, tun aber nichts. Rechnungserzeugung läuft vermutlich ausschließlich vom Lieferschein aus, nicht direkt vom Auftrag.
- **Stillgelegte Versionierung gefunden:** `btnSaveClick` enthält einen komplett auskommentierten Block, der bei Änderung eines bereits gespeicherten Belegs einen neuen Änderungsindex angelegt hätte (`TCloneBeleg.Execute`, `BELEG.AendIndex` über `TGetNextIndex`) – eine Revisionsverwaltung, die im Code vorbereitet, aber deaktiviert ist.
- **Produktionswarnung:** Wird eine Position geändert (Menge/Termin/Artikel), die bereits `FIsInProd` (in Fertigung) ist, erzeugt `btnSaveClick` automatisch eine `TSetProdWarning` – ein Cross-Modul-Sicherheitsnetz zwischen Vertrieb und Produktion.
- **Speichern räumt automatisch auf:** leere Positionszeilen (`TEXT=''`) werden beim Speichern gelöscht, Positionsnummern (`POSNR`) werden aus der Sortierspalte (`POS`) neu vergeben.

### Pascal-Quellcode (FLieferscheinTSP.pas/FRechnungTSP.pas): der echte Rechnungsweg + Gutschrift

Validiert 2026-09-10. Bestätigt die im Auftrag-Formular vermutete Lücke:
Rechnungserzeugung läuft nicht vom Auftrag, sondern **ausschließlich vom
Lieferschein aus**.

- **Lieferschein → Rechnung** (`FLieferscheinTSP.pas`, `pmiRechnungClick`): zwei Gates müssen erfüllt sein – der Beleg darf nicht bereits `ABGESCHLOSSEN='T'` sein, und **`DataModul.AllPreisGeprueft` muss `True` sein** ("Übernahme nicht möglich, nicht alle Preise geprüft."). Erst dann `DataModul.CopyChangeBelegLieferschein(...)`, mit automatisch generiertem Referenztext `'Liefer-/Leistungsdatum: ' + Belegdatum + ' Lieferschein: ' + Nummer` – erklärt die entsprechende Textzeile auf gedruckten Rechnungen.
- **Gutschrift-Mechanismus bestätigt** (`FRechnungTSP.pas`, `RechnungnachGutschriftkopieren1Click`): `DataModul.CopyChangeBelegGutschrift(...)` erzeugt aus einer Rechnung eine Gutschrift, unter Rückbezug auf `HAUPTAUFTRAG` und die ursprüngliche Rechnungsnummer. Es gibt zusätzlich eine Variante "mit Rückbuchung" (`RechnungnachGutschriftkopierenmitRckbuchung1Click`). Strukturell einer der saubersten Fälle in diesem Vergleich – entspricht ziemlich genau Odoos `account.move`-Typ `out_refund` (Gutschrift mit Bezug auf die Ursprungsrechnung).
- **Einfaches Rechnungs-Kopieren** (`Rechnungkopieren1Click`) existiert separat von der Gutschrift-Funktion – legt eine neue, unabhängige Rechnung aus derselben Vorlage an.
- **"Vertreterprovision1Click" ist ein Label/Code-Mismatch, keine Provisionsfunktion.** Der Methodenname suggeriert Provisionslogik, aber die tatsächliche DFM-`Caption` des Menüpunkts lautet **"Belege zeigen"**. Der Handler ruft `TFrmlieferscheinDlg.Execute(..., cdsBelegPosRefOID)` auf – denselben generischen "zeig mir die verknüpften Lieferscheine zu dieser Position"-Dialog, der auch von `FAuftragTSP.pas`/`FAuftragH.pas` verwendet wird. Vermutlich wurde ein Menüpunkt aus einem anderen Formular kopiert/umbenannt, dabei nur die Caption angepasst, nicht der Delphi-Komponentenname – reiht sich damit in dasselbe Muster ein wie `tsh8dl`/"Belastungsanzeige" (UI-Label geändert, Code-Identifier nicht). *Aufgeklärt 2026-09-08 über Live-DB-Zugriff/DFM, siehe Beleg in `aktuelle-exe-validierung.md`.*

### Pascal-Quellcode (FMitarbeiterZeiterfassung.pas): Monatsauswertung, Zuschlagsberechnung geklärt

Kurz gegengeprüft (`HMS/Module/Zeiterfassung/FMitarbeiterZeiterfassung.pas`,
1790 Zeilen). `WriteMonatNew` bestätigt eine echte Monatsabschluss-Berechnung:
`TGetTagesSumme`/`TFQZeitform.ExecuteNoPrint` aggregieren die Tageszeiten,
`WerktageImMonat(..., 5)` zählt die Werktage (Fünf-Tage-Woche) im Monat, und
`TGrundValues.GetValues` lädt die Grunddaten (`ZEITGRUND` je Mitarbeiter,
`PID`-bezogen) für den Soll-Zeit-Vergleich.

**Zuschlagsformel abschließend geklärt (2026-09-08, über `UZeitenWork.pas` +
Live-DB):** Das Altsystem berechnet selbst **keinen** Zuschlags-Prozentsatz
oder -Betrag. `TWorkTimeObject` (`UZeitenWork.pas`) zählt ausschließlich die
**Minutenanteile**, die in feste Zeitfenster fallen –
Nacht 22:00–06:00 (`ZeitNachtBeginn`/`ZeitNachtEnde` in `UConstsZeit.pas`),
Sonntag (`GetSonntagszeit`, per Wochentag-Prüfung) und Feiertag
(`GetFeiertagszeit`, inkl. eigener Übernacht-Fallunterscheidung: Beginn an
einem Werktag, Ende an einem Feiertag zählt anteilig). Die Tabelle
`ZEITGRUND` hat zwar eigene, augenscheinlich dafür vorgesehene Spalten
`SONNZUSCHLAG`/`FEIERZUSCHLAG`/`NACHTZUSCHLAG` (`D_DOUBLE`, je Mitarbeiter) –
**in der Live-DB (Stand 2026-09-08) sind diese bei allen 99 Zeilen NULL**,
während andere Konfigurationsfelder derselben Tabelle (`WAZ`=40,
`URLAUB`=30) normal befüllt sind. Die eigentliche
Sonn-/Feiertags-/Nachtzuschlagsberechnung (Prozentsatz → Euro) findet damit
nachweislich **außerhalb des ERP** statt (externe Lohn-/Payroll-Verarbeitung);
das System liefert nur die rohen Minutenwerte als Exportgrundlage. Die
Vermutung "täglich unterschiedliche Zuschlags-/Pausenregelung" aus der
Kernbeobachtung bezieht sich entsprechend auf die Arbeitszeit-/Pausenfelder
(`MOAZ`/`MOPAUSE` … `SOAZ`/`SOPAUSE`, je Wochentag) in `ZEITGRUND`, nicht auf
einen dort tatsächlich hinterlegten Zuschlagssatz.

## Detailvergleich: System & Firmendaten

Letzter Abschnitt des ursprünglichen Menübaums, wieder reines Reverse
Engineering ohne Screenshot-Vorlage.

**Berechtigungssystem – zwei parallele Mechanismen, nur einer aktiv:**
`BENUTZER` ist eine sehr breite Tabelle mit über 50 einzelnen `CHAR(1)`
Ja/Nein-Spalten, je eine pro Menüpunkt (`ARTIKEL`, `LIEFERSCHEIN`, `RECHNUNG`,
`BESTELLUNG`, `DBADMIN`, `PRODUKTION`, `WARENAUSGANG`, `REPARATUR` …) – ein
Berechtigungs-Flag pro Spalte statt einer Rechte-Tabelle. Daneben gibt es
`BERECHTIGUNG` (`USERID`, `MODULID`, `FORMID`, `STATUS`, `MANDANTID`), eine
normalisierte, formularbezogene ACL-Tabelle. **Nur `BERECHTIGUNG` wird in der
aktuellen EXE noch abgefragt** (`Select * from Berechtigung where UserID = :parUserID
and FormID = :parFormID`) – die breiten `BENUTZER`-Flag-Spalten sind
vermutlich Altlast aus einer früheren Systemversion. `MANDANTID` bestätigt
zusätzlich echte Mandantenfähigkeit (Multi-Company).

**Mitarbeiter/Benutzer sind ein und dieselbe Tabelle:** `BENUTZER` enthält
neben Login-Feldern (`LOGIN`, `PW`, `MAIL`) auch vollständige Personalakte-
Felder mit `MA`-Präfix (`MAGEBDAT`, `MAGEBORT`, `MASTAAT`, `MAGESCHLECHT`,
`MAFAMSTAND`, `MAKONFESSION`, Bankverbindung `MABANK`/`MABLZ`/`MAKONTO`,
Urlaubskontingent `URLAUBGES`/`URLAUBGEN`/`URLAUBJAHR`). Daneben existieren
zusätzlich eigenständige `PERSONAL`/`PERSALLG`-Tabellen (siehe Artikel-/
Reparatur-Abschnitte für die Tabellenliste) – ob diese noch parallel gepflegt
werden oder Altlast sind, ließ sich mit den verfügbaren Quellen nicht klären
(keine Insert/Update-Treffer in den extrahierten EXE-Strings gefunden).

**Mitarbeiterzeit ist deutlich granularer als ein einfaches Kommen/Gehen:**
Neben der schlichten Tätigkeits-Zeitbuchung `ZEITEN` (Beginn/Ende, Tätigkeit,
Projekt, sogar `KM`/`KFZ`/`SPESEN` für Reisekosten) gibt es ein eigenes
Schichtmodell: `ZEITGRUND` definiert je Mitarbeiter (`PID`) Soll-Arbeitszeit
und Pausenregelung **pro Wochentag einzeln** (`MOAZ`/`MOPAUSE` Montag,
`DIAZ`/`DIPAUSE` Dienstag, … bis Sonntag) plus Zuschlagssätze
(`SONNZUSCHLAG`, `FEIERZUSCHLAG`, `NACHTZUSCHLAG`) und Urlaubskonten
(`URLAUB`, `URLAUBVOR`, `UEBERVOR` = Überstunden-Vortrag). `ZEITPERSO` bucht
die tatsächlichen Kommt-/Geht-Zeiten mit Tages-Soll/-Ist-Abgleich
(`TAGSOLL`/`TAGSTD`/`TAGMIN`/`GESMIN`), `ZEITDIENSTSOLL` verwaltet Feiertage/
Schichtplan im Voraus.

| Bereich (aktuelles ERP) | Odoo-Äquivalent | Anmerkung |
|---|---|---|
| `BERECHTIGUNG` (Formular-ACL je Benutzer + Mandant) | `res.groups`/`ir.model.access`/`ir.rule` | Odoo ist rollenbasiert (Gruppen), das Altsystem eher individuell je Benutzer/Formular – granularer, aber ohne Rollenwiederverwendung |
| `BENUTZER.MANDANT`/`BERECHTIGUNG.MANDANTID` | `res.company` (Multi-Company) | strukturell vergleichbar, native Odoo-Funktion |
| `BENUTZER` (Login + Personalakte in einer Tabelle) | `res.users` + `hr.employee` (zwei getrennte Modelle) | Odoo trennt System-Login von Personalakte bewusst; das Altsystem vermischt beides – bei einer Migration müsste das aufgeteilt werden |
| `ZEITEN` (freie Tätigkeitsbuchung mit Projekt-/KM-/Spesenbezug) | `account.analytic.line`/`hr_timesheet` | nativ abbildbar, inkl. Reisekosten am ehesten über `hr_expense` statt Zeiterfassung |
| `ZEITGRUND` (Soll-Zeit + Zuschläge je Wochentag) | `resource.calendar` (Arbeitszeitmodell) | Odoo-Kalender kennt Wochentag-Arbeitszeiten nativ, aber keine eingebauten Zuschlagssätze (Sonn-/Feiertags-/Nachtzuschlag) – das wäre `hr_payroll`-Terrain (Enterprise) |
| `ZEITPERSO` (Ist-Zeiten mit Tages-Soll-Abgleich) | `hr.attendance` | nativ abbildbar |
| `TEXTBAUSTEINE` (`VON`/`BIS`-Gültigkeit, `BELEG`-Bezug) | `mail.template`/Odoo Studio | bereits in der Modulzuordnung vermutet, jetzt mit Feldbezug bestätigt; Gültigkeitszeitraum je Textbaustein hat in Odoo kein natives Pendant |
| `TRANSLATE` (`SPRACHE1`/`2`/`3`, vermutlich "Textkonstanten") | Odoo-Übersetzungssystem (`.po`-Dateien/`ir.translation`) | strukturell ähnlich (mehrsprachige Begriffstabelle), aber Odoo übersetzt über Sprachdateien, nicht über eine fachliche Datentabelle |

**Beobachtung:** Der auffälligste Fund ist nicht eine Feld-Lücke, sondern ein
Strukturbruch: `BENUTZER` vermischt drei eigentlich getrennte Odoo-Konzepte
(Login, Personalakte, Berechtigungen) in einer einzigen, sehr breiten Tabelle
– mit einem zweiten, jüngeren Berechtigungsmechanismus (`BERECHTIGUNG`)
daneben, der die alten Flag-Spalten offenbar abgelöst hat, ohne dass diese
entfernt wurden. Für eine Odoo-Migration wäre das Auseinanderziehen von
Login/Personalakte/Rechten eher eine Vereinfachung als eine Lücke.

## Detailvergleich: Reparatur (Belegmaske)

Screenshot der Reparaturauftrags-Belegmaske (Kunde, Beleg/Kostenvoranschlag,
Gerät-Block, Dokumentenbuttons). Abgleich gegen `repair.order` inkl. der bereits
vorhandenen `int_repair_workshop`-Felder (`x_auftragsart`, `x_eingangsdatum`,
`x_lieferdatum`, `x_verfuegbare_arbeitstage`, `x_werkstattstufe`,
`x_stufe_mitarbeiter`, `x_geraete_snr`).

**Validiert 2026-09-08 (Reales Schema + aktuelle EXE):** Reparaturaufträge laufen
über den generischen `BELEG`/`BELEGPOS`-Belegkopf mit `BELEGART = 154`, ergänzt
um eine per `BELEGNUMMER` (nicht per Fremdschlüssel-OID!) verknüpfte
Satellitentabelle `REPKOPF` für reparaturspezifische Felder. Das Gerät selbst
steckt in `REPARTIKEL` (Gerätestamm), verlinkt über `REPAUFTRAG.GERAETID`.
Referenz-Query aus der aktuellen EXE:

```sql
SELECT B.OID, B.Name1, B.nummer, ..., T.ORDERNR, T.ORDERZAEHL, T.IDENTNR,
  T.Bezeichnung as ABezeichnung, T.Status, R.Ustident, R.Kname, G.Bezeichnung as Gruppe,
  R.Gewaehr, R.GewaehrH, R.famnr, R.Techniker, R.Schlagwort, R.liefschnr,
  Fehler, Ausfall, RepBeschreib, B.Abschlagauftrag as Rahmen
From Beleg B
  left join RepKopf R on R.Belegnummer = B.Nummer
  left join Repauftrag S on S.Belegnummer = B.nummer
  left join RepArtikel T on T.OID = S.Geraetid
  left join RepGruppen G on G.OID = T.Gruppe
WHERE B.Belegart = 154
```

**Zusätzlich validiert 2026-09-09 anhand eines Live-Screenshots** der
Belegmaske (Auftrag 9260929, Kunde Railpool GmbH) – bestätigt praktisch jedes
Feld unten nochmals visuell und liefert vier bisher nicht dokumentierte
Details: einen direkten "Produktion >"-Button im Gerät-Block (Sprung von
Reparatur zu `PRODUKTION`), `Snr Alt`/`Snr Neu`-Felder auf Positionsebene
(bestätigt `BELEGPOS.SNRALT`/`SNRNEU` im Reparatur-Kontext), die Checkboxen
"nicht drucken"/"nicht buchen" je Position (Kehrwert von
`BELEGPOS.DRUCKEN`/`BUCHEN`), sowie **FAM**- und **BGS**-Buttons direkt auf
der Positionszeile (bestätigt `BELEG.FAMID` bzw. `BEGLEITSCHEIN`-Zugriff
schon auf Ebene einzelner Reparaturpositionen, nicht nur am Belegkopf).

| Feld/Bereich (aktuelles ERP) | Odoo-Äquivalent | Anmerkung |
|---|---|---|
| Kunde + Ansprechpartner | `partner_id` | nativ |
| Beleg-Nr. + Typ (Kostenvoranschlag/Auftrag/…) | `name` + `state` | Odoo kennt den Lebenszyklus als Status (quotation → confirmed → under_repair → done), nicht als eigenständige, separat nummerierte Belegtypen |
| Datum/Sparte | `date_order` | "Sparte" (Geschäftsbereich) hat kein natives Feld |
| Bearbeiter | `user_id` | nativ |
| Rahmen (Rahmenauftrag, mit Detail-Link) | kein Standardfeld | passt zu "Rahmenbestellung"/"Rahmen Reparatur" aus dem Einkaufsmenü – Odoo hat kein Konzept für Rahmen-/Blanket-Reparaturaufträge. *Validiert: reales Feld ist `BELEG.ABSCHLAGAUFTRAG` (per Alias `as Rahmen` in der obigen Query) – liegt also am generischen Belegkopf, nicht bei REPKOPF. Live-Beispiel: Feld tatsächlich befüllt (Wert `260020`), kein Leerfeld* |
| Abgeschlossen / Gedruckt (Checkboxen) | `state == 'done'` deckt "Abgeschlossen" | "Gedruckt" (Beleg wurde gedruckt) hat kein natives Flag. *Validiert: `REPKOPF.GEDRUCKT` (`CHAR(1)`) bestätigt* |
| Bewerten (Checkbox) | kein Feld | siehe bereits notiertes "nicht bewerten" bei Adressen – Anknüpfungspunkt Lieferanten-/Auftragsbewertung. *Validiert: reales Feld ist `ADRESSEN.BEWERTEN` (`coalesce(A.Bewerten, 'F')` mehrfach in Bestell-/Lieferquoten-Queries verwendet) – liegt am Kunden, nicht am Reparaturbeleg selbst. Live-Beispiel: Checkbox tatsächlich aktiv gesetzt, also produktiv genutzt und nicht nur theoretisch vorhanden* |
| Bestell-/Liefertermin | `schedule_date` bzw. bereits eigenes `x_lieferdatum` | Liefertermin schon durch `int_repair_workshop` abgedeckt |
| Bestellnummer (Kunden-PO) | kein Feld auf `repair.order` | `sale.order` hat `client_order_ref`, `repair.order` nicht – Lücke |
| Lieferschein-Ausg | `stock.picking`-Verknüpfung | Reparatur erzeugt in Odoo Lieferungen, aber keine eigene "Lieferschein-Ausgang"-Referenz auf dem Formular. *Validiert: `REPKOPF.LIEFSCHNR`/`LIEFSCHDATUM` bestätigt* |
| Gerät: GID, Gruppe, IdentNr, Seriennr, Bezeichnung | `product_id` + `lot_id` (Serien-/Losnummer) | Produkt/Serie nativ vorhanden; GID/Gruppe/IdentNr sind eigene Geräte-Stammdaten (siehe bereits notierte Lücke bei "Geräte" in den Stammdaten). *Validiert: `REPARTIKEL.OID`(GID)/`.IDENTNR`/`.BEZEICHNUNG`, `REPARTIKEL.GRUPPE` → FK auf `REPGRUPPEN.OID`, Seriennummer sitzt aber nicht auf REPARTIKEL selbst, sondern auf `REPAUFTRAG.SERIENNR` (je Auftrag, nicht je Gerätestammsatz). Live-Beispiel: GID 17442, Gruppe "TKL AC3", IdentNr "3EGM064970R0001", Bezeichnung "Klimagerät FRR TRAXX AC3", Seriennr "0085/2015" – UI-Label lautet wörtlich "GID", nicht nur intern so benannt. Der Gerät-Block hat zusätzlich einen direkten **"Produktion >"-Button**, der offenbar auf einen zugehörigen `PRODUKTION`-Datensatz springt – bisher nicht dokumentierte Reparatur→Produktion-Verlinkung.*

  **Semantik von GID/IdentNr/Seriennr geklärt (Vergleich zweier Belege, 2026-09-09):** Ein zweiter Beleg zeigt GID `18866`, gleiche Gruppe "TKL AC3", gleiche Bezeichnung und **gleiche IdentNr `3EGM064970R0001`**, aber andere Seriennr `1023/2022`. Damit: `IDENTNR` ist die Hersteller-Typ-/Modellnummer (modellweit gleich über alle Exemplare), `GID` (`REPARTIKEL.OID`) ist die interne ID des einzelnen physischen Exemplars, `SERIENNR` (`REPAUFTRAG.SERIENNR`) die Herstellerseriennummer genau dieses Exemplars. `REPARTIKEL` ist damit ein Hybrid aus Typ- und Instanzdaten in einer Zeile – Odoo trennt das sauberer in `product.template`(≈IdentNr)/`product.product` und `stock.lot`(≈GID+Seriennr) |
| Kopftext / Fusstext | kein 1:1-Feld | am ehesten `quotation_notes`/interne Notizen, aber kein separates Kopf-/Fußtext-Konzept |
| Material | Reparaturzeilen (`repair.order.line`) | nativ abgedeckt. **Funktionsweise (validiert 2026-09-09):** jede Grid-Zeile ist ein `BELEGPOS`-Datensatz mit `SOID` = dieser Reparaturbeleg; Spalten Pos./Artikel/Menge/Einheit/Text/E-Preis/Rabatt/G-Preis = `POSNR`/`ARTNR`(`ARTOID`)/`STCK`/`EINHEIT`/`TEXT`/`EPREIS`/`RABATT`/`GPREIS`. Für Druck-/Übersichtszwecke werden `BELEGPOS` **und** eine zweite, im 2011-Schema noch nicht vorhandene Tabelle `REPBUCHARTIKEL` per `UNION` zusammengeführt (`... union select ... from REPBUCHARTIKEL K2 where K2.soid = :parOID2`) – vermutlich tatsächlich aus dem Lager gebuchtes Verbrauchsmaterial getrennt von kalkulierten Positionen |
| *(Positionszeile, per Screenshot 2026-09-09 neu entdeckt)* Snr Alt/Neu, "nicht drucken"/"nicht buchen", FAM-Button, BGS-Button, "K"-Button, DruckID-Nr. | `lot_id` (Serie) deckt Snr; für Druck-/Buchungsflags und FAM/BGS kein Pendant | Snr Alt/Neu bestätigt `BELEGPOS.SNRALT`/`SNRNEU` – Seriennummer des aus-/eingebauten Teils **je Materialzeile**, nicht nur am Gerät. "nicht drucken"/"nicht buchen" bestätigt `BELEGPOS.DRUCKEN`/`BUCHEN` (invertiert dargestellt), belegt durch Live-Query mit `coalesce(Drucken, 'F') = 'F'`-Filter. FAM/BGS bestätigen `BELEG.FAMID`/`BEGLEITSCHEIN` schon auf Positions-, nicht nur Belegebene erreichbar. **Korrigiert 2026-09-09 über echte DFM-Extraktion**: Auf dem Material-Tab (`TFRM8D`, `DataSource=dsBelegPos`) existiert nur ein **"K"-Button** (`pnlKalkulation`, `OnClick=pnlKalkulationClick`). Ein "L"-Button existiert auf diesem Tab **nicht** – das einzige "L" im ganzen Formular sitzt auf dem separaten Kostenvoranschlag-Grid (`Panel1`). **Beide jetzt über den Pascal-Quellcode (`F8D.pas`) zweifelsfrei geklärt**: `pnlKalkulationClick` ruft `TfrmKalkulation.Execute(...)` auf – **"K" = Kalkulation**, öffnet den Preiskalkulationsdialog für diese Position. `Panel1Click` (das "L" auf dem Kostenvoranschlag-Grid) ruft `TfrmLangtext.Execute(...)` auf – **"L" = Langtext**, ein Editor für einen längeren Freitext zur Position. **"DruckID-Nr." korrigiert**: bindet an `BELEGPOS.INDENTNRDRUCK`, Dropdown mit Voll/Halb/Ohne – *nicht* eine MwSt-Übersteuerung wie zunächst vermutet (diese Vermutung ist durch den Quellcode widerlegt: `pnlFamClick` liest `cdsBelegPosIndentNrDruck.AsString` direkt als `AFam.IDENTNR` – ein Mehrwertsteuer-Kürzel würde dort keinen Sinn ergeben). Plausibler: steuert, in welchem Umfang die Ident-/Teilenummer der Position **auf dem Druck erscheint** (vollständig/gekürzt/gar nicht) – z. B. aus Wettbewerbsschutz-Gründen gegenüber Kunden. Nebenfund: ein weiterer Button `pnlArtersetz` ("<-", Artikel ersetzen) |
| Versand Eingang / Versand Ausgang | kein Feld | Wareneingang/-ausgang des Reparaturgeräts explizit als eigener Vorgang – in Odoo nur implizit über Lagerbewegungen, nicht als Belegfeld. *Vollständig validiert 2026-09-09 (eigener Tab, nicht nur ein Datumsfeld): `REPKOPF.KDLSNR` (Kundenlieferschein-Nr.), `SPEDITION`/`SPEDNR` (Spediteur/Frachtbrief-Nr.), `VEDATUM` (Datum), `TRANSPORT` (Transportkosten), `SENDNUMMER`/`SENDORT` (Sendungsnr./Ort) – alle über DFM-Steuerelementbindung bestätigt. Die Checkboxen "frei"/"unfrei" binden beide auf dasselbe Feld `FREI` (Frei-Haus vs. Empfänger zahlt), keine zwei getrennten Felder. **"Versand Ausgang" korrigiert 2026-09-09**: **kein Spiegel-Tab**, sondern eigenständig mit deutlich reicherem Feldsatz – eigener Lieferadress-Block (`Name1`/`Name2`/`NAME3`/`Strasse`/`Plz`/`Ort`/`KUNDENUMMER`, alle auf `dsRepKopf`), sieben freie Verwendungsfelder `VFELD1`–`VFELD7`, zwei Preisfelder `BETRAG1`/`BETRAG2`, ein `ABWICKLUNG`-Feld, sowie zwei komplette Kosten-Rechenblöcke fürs Ausgangsversand: **`RKM`/`RKMFAKTOR`/`RKMWERT`** (kilometerbasiert: km × Faktor = Wert) und **`RSTD`/`RSTDFAKTOR`/`RSTDWERT`** (stundenbasiert) – strukturell dasselbe Std./Faktor/Wert-Muster wie die Kostenvoranschlag-Kalkulationszeilen, hier für die Versandkostenberechnung* |
| Reparatur-Beschr. | Beschreibungs-/Diagnosefeld | größtenteils nativ abbildbar. *Vollständig validiert 2026-09-09 (eigener Tab mit drei Textfeldern für drei Erzählperspektiven, nicht nur ein Feld): `REPKOPF.AUSFALL` (Kundenmeldung, Box "Fehlerbeschreibung aus Meldung"), `REPKOPF.FEHLER` (eigene technische Fehleranalyse, zweite Box), `REPKOPF.REPBESCHREIB` (eigentliche Reparaturbeschreibung) – alle über DFM-`TDBMemo`-Bindung bestätigt. Dazu Meldungskontext-Felder: `TECHNIKER` (wiederverwendet als "Meldungs-Nr./Ausfall-Nr."), `FAMNR`, `AUSBAUDATM`/`EINSATZZEIT`, `SCHLAGWORT`, `ANREDE` (wiederverwendet als "Herkunft-Ort"), `RARTIKELNR` (wiederverwendet als "Herkunft-Einheit"), `USTIDENT` (wiederverwendet als "Bezugsnummer"), `KNAME` – siehe eigener Unterabschnitt unten* |
| Anlagen | `ir.attachment` | nativ |
| Bemerkungen | interne Notizen | nativ |
| Stl. Material | `mrp.bom`-Materialliste | nativ über Stückliste abbildbar |
| Geräte Info | kein Standardmodell | wie oben, eigene Geräte-Stammdaten. *Validiert 2026-09-09: eigener Tab mit drei Teilen – Reparaturhistorie des Geräts (`Beleg`/`RepAuftrag`/`RepArtikel`-Join), generische Dokumentenanhänge (`InfoDokumente`) und vermutlich Notizen (`InfoNotizen`), siehe eigener Unterabschnitt unten. `InfoDokumente`/`InfoNotizen` sind anwendungsweit wiederverwendbar (Schlüssel `ModulID`+`ObjektID`), nicht reparaturspezifisch – strukturell ungewöhnlich nah an Odoos `ir.attachment` (`res_model`+`res_id`)* |
| Fehlerzuordnung (Button im UI tatsächlich mit Tippfehler "Fehlerzuordnumg" beschriftet, Screenshot 2026-09-09) | kein Standardfeld | Fehler-/Defektklassifizierung – Anknüpfungspunkt an `quality`-Modul, thematisch verwandt mit den bereits notierten 8D-Lücken. *Validiert: `REPKOPF.FEHLER` (`VARCHAR(2000)`) bestätigt, aber als Freitextfeld – keine strukturierte Klassifizierung/Enum im Altsystem, insofern auch dort keine echte "Zuordnung" zu festen Fehlerkategorien* |
| *(kein Feld in der Belegmaske, aber vom Addon abgebildet)* `x_werkstattstufe` | Selection (6 Werkstattstufen) | **Nicht im Altsystem-Schema gefunden**: `REPARTIKEL.STATUS` sieht auf den ersten Blick passend aus, hält aber laut aktueller EXE Gerätelebenszyklus-Werte wie `'Im Einsatz'` (`Update Repartikel set ... Status = 'Im Einsatz'`), nicht Werkstatt-Durchlaufstufen. Für die sechs Stufen (Außenreinigung/Eingangsprüfung/Gesamtreinigung/In Bearbeitung/Endprüfung/Verpacken) wurden zwar passende UI-Elemente gefunden (`btnEndpruefung`, Label-Captions "Reinigung"/"Reparatur"/"Endprüfung"/"Abwicklung"), aber kein rückführbares Datenbankfeld – vermutlich reine Anzeigelogik im alten Formular, kein persistenter Status. `x_werkstattstufe` ist damit wohl eine **Odoo-seitige Neukonzeption**, keine 1:1-Migration eines Altsystem-Felds. *Korrektur 2026-09-09: Die Label-Captions "Reparatur"/"Reinigung"/"Abwicklung"/"Endprüfung" haben doch ein Datenbankfeld – sie gehören zur Kalkulationstabelle im Kostenvoranschlag-Tab (`REPKOPF.KST2-5`/`KFKT2-5`/`KWERT2-5`, siehe unten). Das ist aber eine reine Kostenkategorisierung (Stunden × Faktor = Wert je Phase), kein Werkstatt-Durchlaufstatus – die Kernaussage bleibt: für `x_werkstattstufe` als Status-Feld gibt es weiterhin keine Altsystem-Entsprechung, nur zufällig gleich benannte Kalkulationszeilen* |

**Beobachtung:** `int_repair_workshop` ist bewusst auf die Werkstattstufen-Logik
begrenzt – es dient als Listenansicht/Übersicht für die Mitarbeiter in der
Produktion, nicht als Ersatz für die kommerzielle Belegmaske. Die oben
aufgeführten Felder (Bestellnummer, Rahmenauftrag, Versand Ein-/Ausgang,
Fehlerzuordnung) sind entsprechend keine Lücken *dieses Moduls*, sondern liegen
außerhalb seines Scopes; sie wären, falls überhaupt, Sache eines eigenen
Beleg-/Auftragsmoduls. Geräte-Stammdaten (GID/Gruppe/IdentNr) bleiben davon
unabhängig eine durchgängige Lücke über alle bisher verglichenen Masken hinweg.

### Kostenvoranschlag-Tab: Kalkulation nach Bearbeitungsphase

Validiert 2026-09-09 anhand eines Live-Screenshots plus DFM-Feldbindungen aus
der aktuellen EXE. Der Tab zeigt fünf Kalkulationszeilen (Befundung,
Reparatur, Reinigung, Abwicklung, Endprüfung), je mit den Spalten Std./
Faktor/Wert. Die DFM-Steuerelemente sind direkt an `REPKOPF` gebunden
(`DataSource: dsRepKopf`), Feld für Feld nachweisbar am Präfix-Muster der
Steuerelementnamen (`dbebs`/`dbebf`/`dbebw` = Befundung, `dbers`/… =
Reparatur, usw.):

| UI-Zeile | Std. | Faktor | Wert |
|---|---|---|---|
| Befundung | `REPKOPF.KST1` | `REPKOPF.KFKT1` | `REPKOPF.KWERT1` |
| Reparatur | `KST2` | `KFKT2` | `KWERT2` |
| Reinigung | `KST3` | `KFKT3` | `KWERT3` |
| Abwicklung | `KST4` | `KFKT4` | `KWERT4` |
| Endprüfung | `KST5` | `KFKT5` | `KWERT5` |

Das erklärt die fünf `KST`/`KFKT`/`KWERT`-Slots im Schema: Stunden × Faktor
(Stundensatz-Multiplikator) = Wert, separat je Bearbeitungsphase.

Der separate Block "Endprüfung: von … am …" (unterhalb der Kalkulation, mit
eigener Checkbox) ist **nicht** dieselbe Endprüfung-Zeile, sondern bindet an
`BELEG.ENDPRUEFUSER` ("von") und `BELEG.ENDPRUEFDATUM` ("am") – wer/wann die
Endprüfung am Beleg insgesamt durchgeführt hat, unabhängig vom Kalkulationswert.

Das Positionsgrid darunter ist strukturell identisch zum Material-Tab
(`BELEGPOS`), mit zwei zusätzlichen, dort nicht vorhandenen Flags:

| Feld | DB-Bezug | Anmerkung |
|---|---|---|
| "Rep. Lager" | `REPKPOS.REPLAGER` | **korrigiert 2026-09-09** über echte DFM-Extraktion: `DBCheckBox2`, `DataField = replager`, `DataSource = dsrepkpos` – auf **diesem** (Kostenvoranschlag-)Grid ist die Quelle `REPKPOS`, nicht `BELEGPOS` (das Material-Tab hat sein eigenes, separates `BELEGPOS.REPLAGER`) |
| "Übern." | **`REPKPOS.UEBERNAHME`** | **korrigiert 2026-09-09**: `DBCheckBox6`, `DataField = uebernahme`, `DataSource = dsrepkpos`. Die frühere Vermutung (`REPAUFTRAG.UEBERNOMMEN`) war falsch – reales Feld ist `UEBERNAHME` auf `REPKPOS`, derselben Positionstabelle wie "Rep. Lager" |
| "nicht drucken"/"nicht buchen" (auf diesem Grid) | `REPKPOS.DRUCKEN`/`BUCHEN` | ebenfalls `DataSource = dsrepkpos` – eigene Instanz dieser Flags, getrennt von `BELEGPOS.DRUCKEN`/`BUCHEN` im Material-Tab |
| "L"-Button neben dem Positionsgrid | bestätigt als echter Action-Button | `TPanel` mit `Caption = 'L'`, `OnClick = Panel1Click` – Komponentenname generisch/nie umbenannt (Panel1), passt zum bereits mehrfach beobachteten Muster nachträglich hinzugefügter Funktionen. Was der Klick genau auslöst, bleibt ohne Pascal-Quellcode zu diesem Formular offen |

Odoo hat für dieses phasenweise Stunden×Faktor-Kalkulationsmodell kein
natives Äquivalent – `repair.order.line` kennt Menge×Einzelpreis, aber keine
Aufteilung der Gesamtkalkulation nach Bearbeitungsphasen mit eigenem
Stundensatz-Faktor je Phase.

### Versand-Eingang-Tab: Frachtdaten der eingehenden Sendung

Validiert 2026-09-09 über Live-Screenshot + DFM-Feldbindungen. Bildet den
Wareneingang der Reparatursendung ab (Frachtdaten des vom Kunden
eintreffenden Pakets), vollständig auf `REPKOPF` gebunden:

| UI-Feld | DB-Feld | Bindungsnachweis |
|---|---|---|
| Kundenlieferschein Nr. | `REPKOPF.KDLSNR` (`VARCHAR30`) | DFM-Referenz `KDLSNR` |
| Spedition | `REPKOPF.SPEDITION` (`CHAR40`) | `dbeSPEDITION` → `DataField SPEDITION` |
| Speditions-Nr. / Frachtbrief-Nr. | `REPKOPF.SPEDNR` (`CHAR40`) | `dbeSPEDNR` → `DataField SPEDNR` |
| Datum | `REPKOPF.VEDATUM` | `dbeVEDATUM` → `DataField VEDATUM` |
| Transportkosten | `REPKOPF.TRANSPORT` (`FLOAT`) | `dbeTransport` → `DataField Transport` |
| "frei" / "unfrei" (Checkboxen) | **beide** `REPKOPF.FREI` | `dbcfrei`/`dbcunfrei` binden auf dasselbe Feld – zwei sich gegenseitig ausschließende Ansichten eines Boolean-Felds, keine zwei getrennten Felder |
| Sendungsnummer | `REPKOPF.SENDNUMMER` (`CHAR15`) | `dbeSENDNUMMER` → `DataField SENDNUMMER` |
| Ort | `REPKOPF.SENDORT` (`CHAR40`) | `dbeSENDORT` → `DataField SENDORT` |

Live-Beispiel: Kundenlieferschein-Nr. `LS 56010832/104` – gleiches
Präfix-/Nummernmuster wie die Bestellnummer `LS 56010756/104` des
Hauptbelegs desselben Kunden (Railpool GmbH), deutet auf einen gemeinsamen
kundeninternen Belegkreis hin.

Odoo-Bezug: am ehesten Trackingfelder auf `stock.picking` (Spediteur,
Sendungsnummer), aber ohne eigenes Frachtkosten-Feld und ohne die
frei/unfrei-Frachtbedingung als eigenes Konzept.

### Reparatur-Beschr.-Tab: drei Textfelder für drei Erzählperspektiven

Validiert 2026-09-09 über Live-Screenshot + DFM-Feldbindungen. Auffälligstes
Muster: **massive Feldwiederverwendung** – von acht sichtbaren UI-Feldern
sind drei an inhaltlich fachfremde `REPKOPF`-Spalten gebunden.

| UI-Feld | DB-Feld | Bindungsnachweis | Hinweis |
|---|---|---|---|
| Meldungs-Nr. / Ausfall-Nr. (ein Eingabefeld) | `REPKOPF.TECHNIKER` | `dbeTECHNIKER` → `DataField TECHNIKER` | wiederverwendet – Feld heißt fachlich "Techniker" |
| FAM - Nummer | `REPKOPF.FAMNR` | `dbeFamnr` → `DataField Famnr` | direkt |
| Herkunft-Ort | `REPKOPF.ANREDE` | `dbeHerkunft` → `DataField Anrede` | **wiederverwendet** – Feld heißt fachlich "Anrede". *Endgültig bestätigt 2026-09-09 über die Artikelinfo (Reiter Vertrieb→Reparatur): dieselbe Query liefert echte Werte wie "Kassel", "Bellinzona", "Kamenz", "Dessau" – eindeutig Einsatzorte, keine Anrede-Werte* |
| Herkunft-Einheit | `REPKOPF.RARTIKELNR` | `DBEdit15` → `DataField RARTIKELNR` | wiederverwendet |
| Ausbaudatum | `REPKOPF.AUSBAUDATM` | `dbeAUSBAUDATM` → `DataField AUSBAUDATM` | direkt |
| Einsatzzeit | `REPKOPF.EINSATZZEIT` | `dbeEINSATZZEIT` → `DataField EINSATZZEIT` | direkt |
| Schlagwort (Dropdown) | `REPKOPF.SCHLAGWORT` | `dbcschlagwort` → `DataField Schlagwort` | direkt |
| Bezugsnummer | `REPKOPF.USTIDENT` | `DBEdit17` → `DataField USTIDENT` | **wiederverwendet** – Feld heißt fachlich "USt-IdNr." |
| K-Name (Einzeilenfeld) | `REPKOPF.KNAME` | `DBEdit19` → `DataField KName` | direkt |
| Fehlerbeschreibung aus Meldung (Memo, befüllt) | `REPKOPF.AUSFALL` | `dbmAUSFALL` → `DataField AUSFALL` | Kundenmeldungstext |
| zweite Memo-Box (leer im Beispiel) | `REPKOPF.FEHLER` | `dbmFEHLER` → `DataField FEHLER` | eigene technische Fehleranalyse |
| große Fläche rechts – **bestätigt 2026-09-09 über DFM-Größenangabe** (343×197px, `Align=alClient`, füllt seinen Container vollständig aus) | `REPKOPF.REPBESCHREIB` | `dbmREPBESCHREIB` → `DataField REPBESCHREIB` | eigentliche Reparaturbeschreibung, namensgebend für den Tab |

Funktional trennt der Tab drei Erzählperspektiven auf denselben Vorgang:
was der Kunde gemeldet hat (`AUSFALL`), was die eigene Diagnose ergibt
(`FEHLER`), und was tatsächlich repariert wurde/wird (`REPBESCHREIB`) – dazu
Meldungs-Metadaten (wer/wo/wann/Referenz). Odoo hätte dafür `description`
(ein Feld) plus ggf. Chatter-Notizen, aber keine strukturell getrennten
Kunde-/Diagnose-/Reparatur-Textfelder.

### Geräte-Info-Tab: Reparaturhistorie + generisches Anhänge-/Notizsystem

Validiert 2026-09-09 über Live-Screenshot + Live-SQL. Drei Teile mit
unterschiedlicher Datenherkunft:

**Links, "Reparatur"/"Datum":** echte Service-Historie dieses Geräts —
bestätigt über eine Query, die exakt Beleg/RepKopf/RepAuftrag/RepArtikel
für dieses `GeraetID` zusammenführt:

```sql
Select B.OID, Name1, Ort, Nummer, AdrNr, Belegdatum, Gedruckt, Abgeschlossen,
  Hauptauftrag, Liefstrasse, Orderzaehl, Ordernr
from Beleg B, Repkopf K
  left join RepAuftrag A on A.Belegnummer = K.Belegnummer
  left join RepArtikel R on R.OID = A.Geraetid
WHERE B.Belegart = 154 And K.Belegnummer = B.Nummer and B.Abgeschlossen = 'F'
Order By Nummer DESC
```

**Mitte, "Dokument":** **kein** reparaturspezifisches Objekt, sondern die
anwendungsweite, polymorphe Anhänge-Tabelle `InfoDokumente`
(`ModulID`+`ObjektID` als generischer Fremdschlüssel, `BenutzerID`+`GlobalU`
für Sichtbarkeit, `Pfad` als Dateireferenz) – vermutlich auch in anderen
Modulen (Artikel, Adressen …) wiederverwendet, nicht auf Reparatur/Geräte
beschränkt.

**Rechts, unbeschriftet:** vermutlich `InfoNotizen` (gleiches
`ModulID`/`ObjektID`/`GlobalU`-Schema wie `InfoDokumente`, nur `Notiz`-Text
statt Dateipfad) – strukturell plausibel, aber keine Query gefunden, die
eindeutig dieses dritte Grid referenziert.

**Bemerkenswert:** Das `InfoDokumente`/`InfoNotizen`-Muster (generische
Tabelle, polymorpher Schlüssel `ModulID`+`ObjektID`) ist einer der wenigen
Fälle in diesem gesamten Vergleich, wo das Altsystem bereits **näher an
Odoos Architektur liegt als umgekehrt** – vergleichbar mit `ir.attachment`
(`res_model`+`res_id`), nicht mit einer Odoo-Lücke.

### Pascal-Quellcode (F8D.pas): Geschäftslogik hinter der Reparaturmaske

Validiert 2026-09-10 durch Lesen des tatsächlichen Formular-Quellcodes
(`HMS/Module/Belege/8D/F8D.pas`, 1880 Zeilen, Delphi-Klasse `Tfrm8D` –
identisch mit dem über DFM bereits gefundenen `TFRM8D`). Klärt mehrere
zuvor nur aus Feldnamen erschlossene Mechanismen mit echtem Code:

- **FAM- und BGS-Button sind dieselbe Objektklasse, nur unterschiedlich "getypt".** `pnlFamClick` und `pnlBGSClick` sind fast identischer Code: beide legen ein `TFAMObject` an (`AFam.New(famFam)` bzw. `AFam.New(famBGS)`), befüllen es aus denselben Quellfeldern und verknüpfen es über `BELEGPOS.RefOID` (FAM) bzw. `RefOID2` (BGS) mit der Position. `BEGLEITSCHEIN` ist damit vermutlich keine eigenständige fachliche Tabelle, sondern derselbe `TFAMObject`-Mechanismus mit einem anderen Typ-Flag.
  - Konkrete Feldherkunft beim Anlegen: `AFam.STANDORT := dbeHerkunft.Text` (bestätigt erneut `ANREDE`-Wiederverwendung als Standort), `AFam.AUSFALLNR := dbeFamnr.Text` (bestätigt `TECHNIKER`-Wiederverwendung), `AFam.ARTIKELNR := AArtObj.HauptLiefer` (Hauptlieferant wird zu einem lesbaren Code aufgelöst), `AFam.IDENTNR := cdsBelegPosIndentNrDruck.AsString` – **das widerlegt die zuvischenzeitliche MwSt-Übersteuerungs-Theorie für "DruckID-Nr."** (siehe Korrektur oben).
- **"F"/"B"-Mini-Labels sind Statusanzeigen, keine reinen Präfixe:** `dbcgPosPaintPanel` färbt `lblFam`/`lblBgs` grün, wenn `BELEGPOS.RefOID`/`RefOID2` > 0 ist (FAM/BGS bereits angelegt), sonst weiß.
- **Rahmen-Button 100 % bestätigt:** `btnRahmenClick` setzt `BELEG.ABSCHLAGAUFTRAG := <gewählter Rahmen-Beleg>.Nummer` – exakt wie aus der SQL-Query abgeleitet.
- **Endprüfung-Button 100 % bestätigt:** öffnet eine Benutzersuche, setzt danach `BELEG.ENDPRUEFUSER`/`ENDPRUEFDATUM` auf den gewählten Namen bzw. heutiges Datum.
- **Kostenvoranschlag-Kalkulation bestätigt als echte Multiplikation:** `dbeefExit` ruft `TChangeThreeFieldsDB.ExecuteDB(dbees, dbeef, dbeew, ChangeFieldThree, MathMultiplikation, 1)` – Std. × Faktor = Wert wird bei Änderung eines der drei Felder automatisch neu berechnet, nicht nur Anzeige dreier unabhängiger Werte.
- **Neuer Fund: zwei parallele Kostenvoranschläge (KVA1/KVA2).** `btnAktiv1Click`/`btnAktiv2Click` (Groupboxen `grpkva1`/`grpkva2`) schreiben `BELEG.FROMBELEGART := 2` bzw. `1` und markieren die aktive Gruppe farbig – das System unterstützt also zwei alternative Kostenvoranschlagsversionen pro Reparaturbeleg, von denen eine als Quelle für den Folgebeleg (Lieferschein/Auftrag) markiert wird. Eine Guard-Prüfung (`BELEG.PUFFERLAGER = 'T'`) verhindert die erneute Aktivierung, wenn schon ein Lieferschein erzeugt wurde.
- **Neuer Fund: `ADRESSEN.ABWUST`.** `btnSearchAdrClick` überschreibt `BELEG.MWSTSATZ` mit `AAdressObject.AbwUst` beim Kundenwechsel – ein kundenspezifischer, abweichender MwSt-Satz auf Adressebene, bisher nicht dokumentiert.
- **Werkstattstufen-Frage endgültig verneint:** keine einzige Fundstelle für "Werkstatt"/"Reinigung"/"Eingangsprüfung"/"Verpacken" im gesamten Formular-Quellcode – bestätigt zusätzlich zur bereits fehlenden DB-Spalte, dass es dafür im Altsystem keinerlei Persistenz gibt.
- **UX-Detail:** Das große `REPBESCHREIB`-Textfeld ändert beim Fokussieren dynamisch Position/Breite (`Left`/`Width` wechseln zwischen 415/350 unfokussiert und 19/650 fokussiert) – erklärt, warum die Feldgröße in Screenshots unterschiedlich wirken kann.

## Validierung gegen die aktuelle Live-Datenbank (Option C, Stand 2026-09-08)

Vollständige Belege in
[`legacy-schema/aktuelle-exe-validierung.md`](legacy-schema/aktuelle-exe-validierung.md#option-c-zugriff-auf-die-aktuelle-live-datenbank-stand-2026-09-08).
Die tagesaktuelle Produktiv-Datenbank (`MAX(BELEGDATUM) = 8-SEP-2026`, 161.183
Belege) lag bereits als lokale 2-GB-Kopie vor, kein Netzwerkzugriff auf den im
Firmennetz gefundenen Firebird-Server (`192.100.0.116`) nötig.

**Schema-Wachstum 2011 → 2026: 194 → 437 Tabellen (+243), 0 entfernt.** Reines
additives Wachstum – bestätigt Architekturmuster 3 unten (Alt+Neu-Koexistenz)
nicht mehr nur an Einzelbeispielen, sondern mit vollständigen Zahlen. Die 243
neuen Tabellen bilden mehrere seit 2011 komplett neu entstandene Subsysteme:

- **Prozess-/Arbeitsplan-Modul** (`PROZESSMAIN` u. a.) – zusätzlicher
  Workflow-Layer neben der alten `PRODUKTION`/`PRODSCHRITTE`-Kette.
- **AOI-Testintegration** (`PMESSAOI`, `PFEHLERAOI`, `PRODFEHLERTESTER`,
  `SNRFEHLER`) – automatische optische Inspektion/Tester an die Fertigung
  angebunden, kein Odoo-Standardpendant (am ehesten `quality` + Custom).
- **Aufgaben-/Terminverwaltung** (`TODO`, `CHECKLISTENKOPF`, `TERMINE`) –
  deckt sich mit Odoos `project`/`calendar`, aktuell ohne Odoo-Anbindung.
- **Zertifikate/Regulatorik** (`ZERTIFIKATE`, `NORMROHS`) – bestätigt erneut,
  dass regulatorische Anforderungen (wie schon bei XRechnung/Gelangens­bestätigung
  festgestellt) erst nach 2011 in die DB kamen.
- **Historisierung** (`BELEGHISTORY`, `BELEGPOSHISTORY`, `DATUMHISTORY`) –
  Korrektur einer früheren Annahme: es gibt inzwischen doch einen
  Änderungs-Audit-Trail, nur eben erst nach 2011 eingeführt.
- **Multi-Währung/Zahlung** (`WECHSELKURSE`, `BANKEN`, `TEILZAHLUNG`).
- **Jahres-Schnappschusstabellen** (`INVENTUR02...`, `PROD02...`,
  `LAGERPAH_.../LAGERPIR_.../LAGERPSZ_...`) statt echter Historisierung –
  jede Jahresinventur bekommt eine eigene, im Namen datierte Tabelle.

**Zentrale Bestandslogik jetzt vollständig statt fragmentarisch bekannt.**
Der `isql -a`-Schemaexport lieferte für alle 111 Stored Procedures nur Stubs
(`BEGIN SUSPEND; END`) – über direkten Zugriff auf
`rdb$procedures.rdb$procedure_source` liegen jetzt alle echten Quelltexte vor
([`all_procedure_sources.sql`](legacy-schema/all_procedure_sources.sql)).
Damit bestätigt: **Bestand ist rein buchungsbasiert** (`P_BESTANDV` summiert
`LAGERBUCHUNG.MENGE`, Schrott-/Sperrlager ausgenommen – kein direkt
editierbares Bestandsfeld, passt strukturell zu Odoos Stock-Move-Ledger-Prinzip
statt zu einem simplen Mengenfeld), und **"Bedarf" ist eigentlich eine
Nettoverfügbarkeit** (`P_BEDARF` = offene Bestellmenge + Bestand − offener
Produktionsbedarf, kann negativ werden = echter Fehlbedarf). Die Views
`V_ProdMaterial`/`V_BereitMaterial` bestätigen 1:1 die aus `strings` bereits
vermuteten Join-Ketten `Produktion→Beleg→Stücklisten→Prodartikel`; zusätzlich
neu: "bereite Menge" rechnet sich als `Menge − Uebernommen`, nicht als reine
Planmenge.

## Kernbeobachtung

Stand 2026-09-08: Der komplette ursprüngliche Menübaum (System, Firmendaten,
Stammdaten, Einkauf, Produktion, Vertrieb, Reparatur) ist jetzt gegen das
reale Schema, den 2018er-Quellcode und die aktuelle EXE geprüft, nicht mehr
nur aus Screenshots abgeleitet. Über alle sechs Detailvergleiche hinweg
zeichnen sich vier wiederkehrende Architekturmuster ab, die wichtiger sind als
einzelne Feld-Lücken:

**1. Ein einziger polymorpher Beleg trägt fast das gesamte System.**
`BELEG`/`BELEGPOS` mit dem Unterscheidungsfeld `BELEGART` bildet Angebot,
Auftrag, Lieferschein, Rechnung, Mahnung, Abschlagrechnung, Bestellung,
Rahmenbestellung, Anfrage, Vertreterabrechnung, Reparatur und sogar
Laufkarten ab (Belegarten 74/100–105/108/115/118/154, siehe Einzelabschnitte).
Odoo modelliert dieselben Vorgänge dagegen als eigenständige Objekte
(`sale.order`, `purchase.order`, `repair.order`, `account.move` …). Eine
Migration entbündelt damit zwangsläufig eine einzige breite Tabelle in
mehrere Odoo-Modelle – strukturell die größte Einzelverschiebung, nicht
einzelne fehlende Felder.

**2. Verknüpfungen laufen oft über Belegnummern, nicht über Fremdschlüssel.**
`REPKOPF`↔`BELEG` (Reparatur), `BELEG.HAUPTAUFTRAG` (Vertriebskette) und
`BELEGPOS.ABRAHMEN` (Rahmenbestellung) hängen an String-/Nummern-Matches statt
an OID-FKs – referenzielle Integrität wird hier nicht von der Datenbank
erzwungen. Odoos FK-Modell wäre an diesen Stellen robuster, nicht nur anders.

**3. Alte und neue Mechanismen koexistieren, ohne dass Altes entfernt wurde.**
Mehrfach bestätigt: `BESTELLKOPF`/`BESTELLPOS` (2011, kaum noch genutzt) neben
dem eigentlich aktiven `BELEG`/`BELEGPOS`; die breiten Berechtigungs-Flags auf
`BENUTZER` neben der jüngeren, tatsächlich abgefragten `BERECHTIGUNG`-Tabelle;
vermutlich auch `PERSONAL`/`PERSALLG` neben den `MA*`-Feldern direkt auf
`BENUTZER`. **Mit dem Live-DB-Zugriff 2026-09-08 jetzt auch quantitativ
belegt:** 194 → 437 Tabellen zwischen 2011 und 2026, keine einzige entfernt
(siehe Abschnitt "Validierung gegen die aktuelle Live-Datenbank" oben). Das
System ist über Jahrzehnte gewachsen, ohne aufzuräumen – eine Migration wäre
hier eher eine Chance zur Vereinfachung als ein Verlust.

**4. Die Datenlage ist newer als angenommen, wo es auf Regulatorik ankommt.**
Sowohl die 2011-DB als auch der 2018er-Quellcode fehlen bei XRechnung/Peppol
und Gelangensbestätigung komplett – beides nur über die aktuelle EXE (Stand
06.09.2026) nachweisbar, inzwischen auch direkt in der Live-DB bestätigt
(u. a. eigene `NORMROHS`-Tabelle für RoHS-Konformität). Wer künftig mit den
älteren Quellen arbeitet, muss diesen Altersunterschied im Kopf behalten,
statt Abwesenheit in der DB als Abwesenheit im Live-System misszuverstehen
(wie es mir bei der Adressen-Prüfung anfangs selbst passiert ist) – und auch
umgekehrt: die frühere Annahme "kein Audit-Trail vorhanden" war ebenfalls nur
ein Artefakt der veralteten Quelle, `BELEGHISTORY`/`BELEGPOSHISTORY` existieren
in der aktuellen DB.

**Bestätigte Lücken ohne Odoo-Standardentsprechung** (mit konkretem Feldbezug
statt Vermutung): Geräte-Stammdaten (GID/Gruppe/IdentNr, durchgängig über
Reparatur *und* Produktion), das Abruf-gegen-Rahmen-Modell der
Rahmenbestellung (Belegart 74), die Vertreterabrechnung/Provisionsberechnung
(`V_Vertreter`-View), Mehrfach-Zweck-E-Mail-Felder mit CC/BCC, die täglich
unterschiedliche Arbeitszeit-/Pausenregelung der Mitarbeiterzeit (`ZEITGRUND`,
je Wochentag eigene Soll-Arbeitszeit-/Pausenfelder – die dort ebenfalls
vorgesehenen `*ZUSCHLAG`-Spalten sind dagegen in der Live-DB durchgängig leer,
siehe Zeiterfassungs-Abschnitt oben), sowie zwei erst über die Live-DB
gefundene Bereiche: die **AOI-Testintegration**
(automatische optische Inspektion in der Fertigung, `PMESSAOI`/`PFEHLERAOI`/
`SNRFEHLER`) und das separate **Prozess-/Arbeitsplan-Modul** (`PROZESSMAIN`
u. a.) neben der klassischen `PRODUKTION`/`PRODSCHRITTE`-Kette.

**Bessere Passung als ursprünglich angenommen:** "Abschlussrechnung" stellte
sich als Fehllesung heraus – real ist es "Abschlagrechnung" (Anzahlung), wofür
Odoo mit `sale.advance.payment.inv` eine native Lösung hat. Auch der
Fertigungskern (Routing-Vorlage → Fertigungsauftrag → Arbeitsschritt →
Zeitbuchung) bildet sich überraschend sauber auf `mrp` ab.

Dieser Vergleich ist ein Gedankengang zur Einordnung, keine Migrationsentscheidung.
Siehe auch Memory-Eintrag zur Odoo-Integration als noch offenem Thema.
