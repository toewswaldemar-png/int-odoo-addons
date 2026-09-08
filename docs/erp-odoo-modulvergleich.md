# Modulvergleich: aktuelles ERP ↔ Odoo 19

Stand: 2026-08-31 (Menü/Feldübersicht), Validierung 2026-09-08. Ausgangspunkt war
ein Screenshot der Hauptmenü-Übersicht des aktuellen (Windows-Legacy-)ERP-Systems.
Zweck dieses Dokuments: Einordnung, welche Odoo-Standardmodule bzw. bestehende
`int_`-Addons die einzelnen Bereiche abdecken, und wo Lücken bestehen.

## Quellenlage (Reverse Engineering, Stand 2026-09-08)

Die Screenshot-Angaben wurden gegen drei unterschiedlich aktuelle Quellen
geprüft:

| Quelle | Stand | Inhalt |
|---|---|---|
| `IBDB.GDB` (Firebird/InterBase-DB, aus `db/BAK/IBDB.zip`) | 2011-11-09 | Vollständiges DDL-Schema (194 Tabellen), extrahiert via `isql -a`; abgelegt unter [`legacy-schema/full_schema.sql`](legacy-schema/full_schema.sql) |
| `HMS/Module/*.pas` (Delphi-Quellcode) | bis 2018-11 | Datenmodul-/Geschäftslogik; jüngste Datei-Timestamps liegen bei Nov. 2018 |
| `Herrmann.exe` (kompiliertes aktuelles Programm) | 2026-09-06 | String-/Ressourcenextraktion (`strings` auf ASCII + UTF-16LE) aus dem produktiv gebauten Binary |

**Wichtige Erkenntnis:** Die DB-Kopie und der lokal vorliegende Pascal-Quellcode
sind beide veraltet (2011 bzw. 2018) und bilden nur den **stabilen Datenkern**
korrekt ab. Neuere, regulatorisch getriebene Felder (v. a. XRechnung/Peppol,
eingeführt im Zuge der deutschen E-Rechnungspflicht 2024/2025) fehlen in
beiden Quellen komplett. Das `Herrmann_Work`-Verzeichnis enthält jedoch
laufend aktualisierte kompilierte Programmversionen (u. a. `Herrmann.exe` vom
06.09.2026, nur 2 Tage vor dieser Prüfung) – daraus lassen sich per
String-Extraktion auch aktuelle Feldnamen/SQL-Fragmente gewinnen, ohne den
Quellcode selbst zu haben. Alle nachfolgenden „bestätigt"/„korrigiert"-Vermerke
beziehen sich auf diesen Dreiklang.

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
| 8D Lieferant, Rahmen Reparatur | `quality` (8D-Reports) + `repair` | Odoo Quality hat "5 Why"/MRP-Anbindung, kein natives 8D-Formular – evtl. Custom |
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

Feldebene der "Adressen - Suchen"-Maske gegen `res.partner`:

| Feld (aktuelles ERP) | Odoo-Äquivalent | Anmerkung |
|---|---|---|
| Name 1 | `name` | |
| Name 2 | kein Standardfeld | Odoo kennt keine mehrzeilige Firmenbezeichnung; oft über `street2` zweckentfremdet oder Custom-Feld nötig |
| Name 3 | kein Standardfeld | wie Name 2, z. B. für "c/o"-Zeilen; Custom-Feld nötig |
| Kurzname | kein Standardfeld | am ehesten `ref`, aber semantisch anders belegt (interne Referenz statt Kurzname) |
| Strasse | `street` | |
| Plz / Ort | `zip` / `city` | |
| Debit.-Nummer | kein 1:1-Feld | Odoo nutzt Partner-ID/`ref`; eine eigenständige, ggf. anders formatierte Debitorennummer braucht Custom-Feld + eigene Sequenz |
| Kredit.-Nummer | kein 1:1-Feld | analog zur Debitorennummer, i. d. R. Custom-Feld |
| Ansprechpartner | Kontaktpersonen (`res.partner` mit `parent_id`) | bestätigt: eigene Tabelle je Adresse mit Anrede, Name, Vorname, Fon, Fax, Mobil, E-Mail, Funktion je Kontakt – bildet sich sehr gut auf Odoos Kontaktpersonen-Modell ab (Titel/Vorname-Nachname/`phone`/`mobile`/`email`/`function` sind alles native Felder auf `res.partner`); einer der saubersten 1:1-Fälle in diesem Vergleich |
| Gruppe / Nr. | `category_id` (Partner-Tags) | "Nr." als zusätzliche Nummerierung innerhalb der Gruppe hat kein Pendant, ggf. Custom |
| "Adressen Filtern" (Checkbox) | Odoo-Suchfilter/-Views | kein Datenfeld, sondern Sucheinstellung – in Odoo über Standard-Filter/Gruppierung gelöst |

**Beobachtung:** Die größte strukturelle Lücke ist die dreizeilige Namensfelder-Logik
(Name 1–3) sowie eigenständige, frei formatierbare Debitoren-/Kreditorennummern
getrennt von der internen Odoo-ID. Beides wäre bei einer Migration entweder per
Custom-Feld auf `res.partner` oder durch Umgewöhnung an Odoos Kontaktmodell
(Firma + Kontaktpersonen statt Namenszeilen) zu lösen.

## Detailvergleich: Adressen (Detailmaske, Reiter "Allgemein")

Zusätzliche Felder gegenüber der Suchmaske, aus der Datensatzansicht eines
konkreten Adress-/Kontaktdatensatzes:

| Feld (aktuelles ERP) | Odoo-Äquivalent | Anmerkung |
|---|---|---|
| Nummer | interne ID / `ref` | |
| Anlage / Änderung (Datum) | `create_date` / `write_date` | in Odoo Systemfelder, nicht standardmäßig auf dem Formular sichtbar |
| Anrede: Firma / Person | `company_type` | passt direkt |
| Art: Allgemein / Kunde / Lieferant (exklusiv) | `customer_rank` / `supplier_rank` | **struktureller Unterschied**: Odoo behandelt Kunde/Lieferant nicht exklusiv – ein Partner kann beides gleichzeitig sein, hier ist es eine Radio-Auswahl. *Validiert 2026-09-08: kein eigenes Exklusiv-Feld im Schema gefunden (weder 2011-DB noch aktuelle EXE) – `DebNr` und `KredNr` sind unabhängige Felder, die "Exklusivität" ist vermutlich reine UI-Logik, nicht im Datenmodell erzwungen* |
| Postfach | kein Feld | Custom-Feld nötig |
| Lkz (Ländercode) | `country_id` | |
| Etikette (Checkbox) | kein Feld | Druck-/Etikettensteuerung, vermutlich Custom oder Report-Filter |
| inaktiv (Checkbox) | `active` (Archivierung) | **Semantikunterschied**: Odoos `active=False` blendet den Datensatz komplett aus Standard-Views aus; falls "inaktiv" hier nur einen Status markiert und der Datensatz weiter sichtbar bleiben soll, braucht es ein eigenes Feld statt `active` |
| gesperrt (Checkbox) | kein Feld | z. B. Liefer-/Bestellsperre – Custom-Feld, da semantisch verschieden von `active` |
| nicht bewerten (Checkbox) | kein Feld | Ausschluss aus Lieferantenbewertung – ggf. Anknüpfungspunkt an `quality`-Modul |
| ist Vertreter (Checkbox) | kein Feld | am ehesten über Partner-Tag/Kategorie lösbar |
| Buyer Ref. | kein Feld | Custom |
| unsere Nummer bei Kunde/Lieferant | kein Feld | eigene Kundennummer beim Geschäftspartner – kein Odoo-Standardfeld (zu unterscheiden von `ref`, das die eigene interne Nummer ist) |
| Fon / Fon 2 / Fax / Mobil | `phone` / `mobile` | Odoo kennt nur je ein Feld für Telefon und Mobil, kein zweites Telefonfeld, Fax in neueren Odoo-Versionen entfernt |
| E-M@il Zentral / Rechnung / Vertrieb / Einkauf / GL / Info (je mit CC/BCC) | `email` (ein Feld) + Kontaktpersonen mit Adresstyp | Odoo löst mehrere Zwecke eher über zusätzliche Kontakt-Datensätze (Rechnungsadresse, Lieferadresse) statt über mehrere E-Mail-Felder am selben Partner; CC/BCC pro Zweck hat kein Pendant. *Validiert 2026-09-08 anhand der aktuellen EXE (SQL-String aus dem Adressen-Ladeformular): reale Feldnamen sind `EMail` (Zentral), `EmailBuchhaltung` (Rechnung), `EMailVT` (Vertrieb), `EmailEK` (Einkauf), `EmailGL`, `EmailInfo`, dazu je ein CC/BCC-Paar (`BUCHHALTUNGCC/BCC`, `VTCC/BCC`, `EKCC/BCC`, `GLCC/BCC`, `InfoCC/BCC`, `EmailCC/BCC`) sowie separate Versand-Flags `MailAngebot`, `MailAuftrag`, `MailLieferschein`, `MailRechnung`, `MailBestellung` und Rechnungskopie-Routing `RechCopyAll/Norm/VT/Fibu/Opos` – die Behauptung war korrekt, sogar granularer als zunächst dokumentiert* |
| WWW | `website` | |
| XRechnung-Block (Buyerreferenz, Endpoint, Contractnr, Leitweg ID, eigene ID, ID Kunde) | Peppol-/E-Invoicing-Felder (`peppol_eas`, `peppol_endpoint`) bzw. deutsche Lokalisierung | thematisch verwandt (E-Rechnungspflicht), aber nicht feldgleich – bei einer Migration eigener Prüfpunkt, da B2B-E-Rechnungspflicht in Deutschland gerade schrittweise scharf geschaltet wird. *Validiert 2026-09-08: reale Feldnamen `LeitwegID` und `BuyerRef`/`BuyerReference` auf `Adressen`, dazu `Xemail`/`Xrech`-Flags; ruft extern `xrechnung.exe` auf (liegt lokal unter `Herrmann_Work/20211007/XRechnung.exe`). Existiert weder in der 2011-DB noch im 2018er-Quellcode – nachweislich erst danach eingeführt (passt zur E-Rechnungspflicht 2024/2025)* |

**Beobachtung:** Neben den bereits genannten Namens-/Nummernfeldern zeigt die
Detailmaske zwei weitere strukturelle Unterschiede: (1) Kunde/Lieferant ist hier
exklusiv, in Odoo nicht: (2) mehrere zweckgebundene E-Mail-Felder mit eigenem
CC/BCC pro Adresse gibt es in Odoo nicht in dieser Form. Der XRechnung-Block ist
inhaltlich der einzige Bereich mit einer nativen Odoo-Entsprechung (Peppol/E-Invoicing),
aber ohne 1:1-Feldabgleich.

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
| `x_alt_hersteller_ref_ids` (`product.legacy.manufacturer.ref`, Codes BT/LH/FY/NK/KO/VK/BE/TK/DB/HO/WE) | `ARTIKEL.IDENTNR1` … `IDENTNR5` (2011-Schema) bzw. bis `IDENTNR12` (aktuelle EXE) | `VARCHAR(60)` je Slot | **Teilweise bestätigt, teilweise offen**: Es gibt kein eigenes Hersteller-Referenz-Modell in der DB – stattdessen 5 (2011) bzw. bis zu 12 (aktuell) generische, positionsbasierte `IDENTNRn`-Spalten direkt auf `ARTIKEL` (auch gespiegelt auf `STUECKLISTEN`/`STUECKLISTENARTIKEL`). Die 11 Codes im Addon passen zahlenmäßig zu den positionsbasierten Slots, aber welche feste Position (`IDENTNR1`…`IDENTNR11`) zu welchem Code (BT, LH, …) gehört, ließ sich aus dem verfügbaren 2018er-Quellcode nicht ableiten (nur toter, auskommentierter Code mit Netzlaufwerkspfaden `Z:\dokument\Liebherr\...` gefunden, keine Feldbindung). Für eine belastbare Zuordnung bräuchte es entweder die Formularbeschriftungen aus der laufenden Anwendung (Screenshot der Artikel-Karteikarte mit den 11 Identifikationszeilen) oder eine DFM-Analyse einer aktuelleren Quellcode-Version |

**Beobachtung:** Die einfachen Textfelder (Artikelnummer, Kurzbezeichnung,
Bestellnummer, Einheit) sind im Addon korrekt nachgebildet. Die beiden
Referenzfelder Hauptlieferant und Gruppe sind dagegen als Freitext statt als
Fremdschlüssel modelliert – das funktioniert für einen reinen Anzeige-Testballon,
würde aber bei einem echten Import zu unverknüpften Werten führen (keine
Beziehung zu `res.partner`/`product.category`, keine Wiederverwendung
bestehender Odoo-Datensätze). Die Hersteller-Ident-Referenzen sind strukturell
richtig als flexible Zeilen statt starrer Spalten modelliert (das ist sogar eine
Verbesserung ggü. dem starren Altsystem-Schema), aber die genaue
Code-zu-Spalten-Zuordnung bleibt ein offener Punkt.

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

| Feld/Bereich (aktuelles ERP) | Odoo-Äquivalent | Anmerkung |
|---|---|---|
| Kunde + Ansprechpartner | `partner_id` | nativ |
| Beleg-Nr. + Typ (Kostenvoranschlag/Auftrag/…) | `name` + `state` | Odoo kennt den Lebenszyklus als Status (quotation → confirmed → under_repair → done), nicht als eigenständige, separat nummerierte Belegtypen |
| Datum/Sparte | `date_order` | "Sparte" (Geschäftsbereich) hat kein natives Feld |
| Bearbeiter | `user_id` | nativ |
| Rahmen (Rahmenauftrag, mit Detail-Link) | kein Standardfeld | passt zu "Rahmenbestellung"/"Rahmen Reparatur" aus dem Einkaufsmenü – Odoo hat kein Konzept für Rahmen-/Blanket-Reparaturaufträge. *Validiert: reales Feld ist `BELEG.ABSCHLAGAUFTRAG` (per Alias `as Rahmen` in der obigen Query) – liegt also am generischen Belegkopf, nicht bei REPKOPF* |
| Abgeschlossen / Gedruckt (Checkboxen) | `state == 'done'` deckt "Abgeschlossen" | "Gedruckt" (Beleg wurde gedruckt) hat kein natives Flag. *Validiert: `REPKOPF.GEDRUCKT` (`CHAR(1)`) bestätigt* |
| Bewerten (Checkbox) | kein Feld | siehe bereits notiertes "nicht bewerten" bei Adressen – Anknüpfungspunkt Lieferanten-/Auftragsbewertung. *Validiert: reales Feld ist `ADRESSEN.BEWERTEN` (`coalesce(A.Bewerten, 'F')` mehrfach in Bestell-/Lieferquoten-Queries verwendet) – liegt am Kunden, nicht am Reparaturbeleg selbst* |
| Bestell-/Liefertermin | `schedule_date` bzw. bereits eigenes `x_lieferdatum` | Liefertermin schon durch `int_repair_workshop` abgedeckt |
| Bestellnummer (Kunden-PO) | kein Feld auf `repair.order` | `sale.order` hat `client_order_ref`, `repair.order` nicht – Lücke |
| Lieferschein-Ausg | `stock.picking`-Verknüpfung | Reparatur erzeugt in Odoo Lieferungen, aber keine eigene "Lieferschein-Ausgang"-Referenz auf dem Formular. *Validiert: `REPKOPF.LIEFSCHNR`/`LIEFSCHDATUM` bestätigt* |
| Gerät: GID, Gruppe, IdentNr, Seriennr, Bezeichnung | `product_id` + `lot_id` (Serien-/Losnummer) | Produkt/Serie nativ vorhanden; GID/Gruppe/IdentNr sind eigene Geräte-Stammdaten (siehe bereits notierte Lücke bei "Geräte" in den Stammdaten). *Validiert: `REPARTIKEL.OID`(GID)/`.IDENTNR`/`.BEZEICHNUNG`, `REPARTIKEL.GRUPPE` → FK auf `REPGRUPPEN.OID`, Seriennummer sitzt aber nicht auf REPARTIKEL selbst, sondern auf `REPAUFTRAG.SERIENNR` (je Auftrag, nicht je Gerätestammsatz)* |
| Kopftext / Fusstext | kein 1:1-Feld | am ehesten `quotation_notes`/interne Notizen, aber kein separates Kopf-/Fußtext-Konzept |
| Material | Reparaturzeilen (`repair.order.line`) | nativ abgedeckt |
| Versand Eingang / Versand Ausgang | kein Feld | Wareneingang/-ausgang des Reparaturgeräts explizit als eigener Vorgang – in Odoo nur implizit über Lagerbewegungen, nicht als Belegfeld. *Validiert: `REPKOPF.WEINGANGDATUM` (Versand Eingang) bestätigt; für "Versand Ausgang" kein eigenes Feld gefunden – vermutlich deckungsgleich mit Lieferschein-Ausg. (`LIEFSCHNR`/`LIEFSCHDATUM`)* |
| Reparatur-Beschr. | Beschreibungs-/Diagnosefeld | größtenteils nativ abbildbar. *Validiert: `REPKOPF.REPBESCHREIB` (`VARCHAR(600)`) exakt bestätigt, dazu `REPKOPF.AUSFALL` (`VARCHAR(600)`, Ausfallbeschreibung) als verwandtes Zusatzfeld* |
| Anlagen | `ir.attachment` | nativ |
| Bemerkungen | interne Notizen | nativ |
| Stl. Material | `mrp.bom`-Materialliste | nativ über Stückliste abbildbar |
| Geräte Info | kein Standardmodell | wie oben, eigene Geräte-Stammdaten |
| Fehlerzuordnung | kein Standardfeld | Fehler-/Defektklassifizierung – Anknüpfungspunkt an `quality`-Modul, thematisch verwandt mit den bereits notierten 8D-Lücken. *Validiert: `REPKOPF.FEHLER` (`VARCHAR(2000)`) bestätigt, aber als Freitextfeld – keine strukturierte Klassifizierung/Enum im Altsystem, insofern auch dort keine echte "Zuordnung" zu festen Fehlerkategorien* |
| *(kein Feld in der Belegmaske, aber vom Addon abgebildet)* `x_werkstattstufe` | Selection (6 Werkstattstufen) | **Nicht im Altsystem-Schema gefunden**: `REPARTIKEL.STATUS` sieht auf den ersten Blick passend aus, hält aber laut aktueller EXE Gerätelebenszyklus-Werte wie `'Im Einsatz'` (`Update Repartikel set ... Status = 'Im Einsatz'`), nicht Werkstatt-Durchlaufstufen. Für die sechs Stufen (Außenreinigung/Eingangsprüfung/Gesamtreinigung/In Bearbeitung/Endprüfung/Verpacken) wurden zwar passende UI-Elemente gefunden (`btnEndpruefung`, Label-Captions "Reinigung"/"Reparatur"/"Endprüfung"/"Abwicklung"), aber kein rückführbares Datenbankfeld – vermutlich reine Anzeigelogik im alten Formular, kein persistenter Status. `x_werkstattstufe` ist damit wohl eine **Odoo-seitige Neukonzeption**, keine 1:1-Migration eines Altsystem-Felds |

**Beobachtung:** `int_repair_workshop` ist bewusst auf die Werkstattstufen-Logik
begrenzt – es dient als Listenansicht/Übersicht für die Mitarbeiter in der
Produktion, nicht als Ersatz für die kommerzielle Belegmaske. Die oben
aufgeführten Felder (Bestellnummer, Rahmenauftrag, Versand Ein-/Ausgang,
Fehlerzuordnung) sind entsprechend keine Lücken *dieses Moduls*, sondern liegen
außerhalb seines Scopes; sie wären, falls überhaupt, Sache eines eigenen
Beleg-/Auftragsmoduls. Geräte-Stammdaten (GID/Gruppe/IdentNr) bleiben davon
unabhängig eine durchgängige Lücke über alle bisher verglichenen Masken hinweg.

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
`BENUTZER`. Das System ist über Jahrzehnte gewachsen, ohne aufzuräumen – eine
Migration wäre hier eher eine Chance zur Vereinfachung als ein Verlust.

**4. Die Datenlage ist newer als angenommen, wo es auf Regulatorik ankommt.**
Sowohl die 2011-DB als auch der 2018er-Quellcode fehlen bei XRechnung/Peppol
und Gelangensbestätigung komplett – beides nur über die aktuelle EXE (Stand
06.09.2026) nachweisbar. Wer künftig mit diesen Quellen arbeitet, muss diesen
Altersunterschied im Kopf behalten, statt Abwesenheit in der DB als
Abwesenheit im Live-System misszuverstehen (wie es mir bei der
Adressen-Prüfung anfangs selbst passiert ist).

**Bestätigte Lücken ohne Odoo-Standardentsprechung** (mit konkretem Feldbezug
statt Vermutung): Geräte-Stammdaten (GID/Gruppe/IdentNr, durchgängig über
Reparatur *und* Produktion), das Abruf-gegen-Rahmen-Modell der
Rahmenbestellung (Belegart 74), die Vertreterabrechnung/Provisionsberechnung
(`V_Vertreter`-View), Mehrfach-Zweck-E-Mail-Felder mit CC/BCC, und die
täglich unterschiedliche Zuschlags-/Pausenregelung der Mitarbeiterzeit
(`ZEITGRUND`).

**Bessere Passung als ursprünglich angenommen:** "Abschlussrechnung" stellte
sich als Fehllesung heraus – real ist es "Abschlagrechnung" (Anzahlung), wofür
Odoo mit `sale.advance.payment.inv` eine native Lösung hat. Auch der
Fertigungskern (Routing-Vorlage → Fertigungsauftrag → Arbeitsschritt →
Zeitbuchung) bildet sich überraschend sauber auf `mrp` ab.

Dieser Vergleich ist ein Gedankengang zur Einordnung, keine Migrationsentscheidung.
Siehe auch Memory-Eintrag zur Odoo-Integration als noch offenem Thema.
