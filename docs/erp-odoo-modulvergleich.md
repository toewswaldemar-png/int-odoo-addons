# Modulvergleich: aktuelles ERP ↔ Odoo 19

Stand: 2026-08-31. Ausgangspunkt war ein Screenshot der Hauptmenü-Übersicht des
aktuellen (Windows-Legacy-)ERP-Systems. Zweck dieses Dokuments: Einordnung,
welche Odoo-Standardmodule bzw. bestehende `int_`-Addons die einzelnen Bereiche
abdecken, und wo Lücken bestehen.

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
| Gelangensbestätigung | kein Standard | EU-Ausfuhrnachweis, meist Lokalisierungs-/Custom-Modul |
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
| Art: Allgemein / Kunde / Lieferant (exklusiv) | `customer_rank` / `supplier_rank` | **struktureller Unterschied**: Odoo behandelt Kunde/Lieferant nicht exklusiv – ein Partner kann beides gleichzeitig sein, hier ist es eine Radio-Auswahl |
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
| E-M@il Zentral / Rechnung / Vertrieb / Einkauf / GL / Info (je mit CC/BCC) | `email` (ein Feld) + Kontaktpersonen mit Adresstyp | Odoo löst mehrere Zwecke eher über zusätzliche Kontakt-Datensätze (Rechnungsadresse, Lieferadresse) statt über mehrere E-Mail-Felder am selben Partner; CC/BCC pro Zweck hat kein Pendant |
| WWW | `website` | |
| XRechnung-Block (Buyerreferenz, Endpoint, Contractnr, Leitweg ID, eigene ID, ID Kunde) | Peppol-/E-Invoicing-Felder (`peppol_eas`, `peppol_endpoint`) bzw. deutsche Lokalisierung | thematisch verwandt (E-Rechnungspflicht), aber nicht feldgleich – bei einer Migration eigener Prüfpunkt, da B2B-E-Rechnungspflicht in Deutschland gerade schrittweise scharf geschaltet wird |

**Beobachtung:** Neben den bereits genannten Namens-/Nummernfeldern zeigt die
Detailmaske zwei weitere strukturelle Unterschiede: (1) Kunde/Lieferant ist hier
exklusiv, in Odoo nicht: (2) mehrere zweckgebundene E-Mail-Felder mit eigenem
CC/BCC pro Adresse gibt es in Odoo nicht in dieser Form. Der XRechnung-Block ist
inhaltlich der einzige Bereich mit einer nativen Odoo-Entsprechung (Peppol/E-Invoicing),
aber ohne 1:1-Feldabgleich.

## Detailvergleich: Reparatur (Belegmaske)

Screenshot der Reparaturauftrags-Belegmaske (Kunde, Beleg/Kostenvoranschlag,
Gerät-Block, Dokumentenbuttons). Abgleich gegen `repair.order` inkl. der bereits
vorhandenen `int_repair_workshop`-Felder (`x_auftragsart`, `x_eingangsdatum`,
`x_lieferdatum`, `x_verfuegbare_arbeitstage`, `x_werkstattstufe`,
`x_stufe_mitarbeiter`, `x_geraete_snr`):

| Feld/Bereich (aktuelles ERP) | Odoo-Äquivalent | Anmerkung |
|---|---|---|
| Kunde + Ansprechpartner | `partner_id` | nativ |
| Beleg-Nr. + Typ (Kostenvoranschlag/Auftrag/…) | `name` + `state` | Odoo kennt den Lebenszyklus als Status (quotation → confirmed → under_repair → done), nicht als eigenständige, separat nummerierte Belegtypen |
| Datum/Sparte | `date_order` | "Sparte" (Geschäftsbereich) hat kein natives Feld |
| Bearbeiter | `user_id` | nativ |
| Rahmen (Rahmenauftrag, mit Detail-Link) | kein Standardfeld | passt zu "Rahmenbestellung"/"Rahmen Reparatur" aus dem Einkaufsmenü – Odoo hat kein Konzept für Rahmen-/Blanket-Reparaturaufträge |
| Abgeschlossen / Gedruckt (Checkboxen) | `state == 'done'` deckt "Abgeschlossen" | "Gedruckt" (Beleg wurde gedruckt) hat kein natives Flag |
| Bewerten (Checkbox) | kein Feld | siehe bereits notiertes "nicht bewerten" bei Adressen – Anknüpfungspunkt Lieferanten-/Auftragsbewertung |
| Bestell-/Liefertermin | `schedule_date` bzw. bereits eigenes `x_lieferdatum` | Liefertermin schon durch `int_repair_workshop` abgedeckt |
| Bestellnummer (Kunden-PO) | kein Feld auf `repair.order` | `sale.order` hat `client_order_ref`, `repair.order` nicht – Lücke |
| Lieferschein-Ausg | `stock.picking`-Verknüpfung | Reparatur erzeugt in Odoo Lieferungen, aber keine eigene "Lieferschein-Ausgang"-Referenz auf dem Formular |
| Gerät: GID, Gruppe, IdentNr, Seriennr, Bezeichnung | `product_id` + `lot_id` (Serien-/Losnummer) | Produkt/Serie nativ vorhanden; GID/Gruppe/IdentNr sind eigene Geräte-Stammdaten (siehe bereits notierte Lücke bei "Geräte" in den Stammdaten) |
| Kopftext / Fusstext | kein 1:1-Feld | am ehesten `quotation_notes`/interne Notizen, aber kein separates Kopf-/Fußtext-Konzept |
| Material | Reparaturzeilen (`repair.order.line`) | nativ abgedeckt |
| Versand Eingang / Versand Ausgang | kein Feld | Wareneingang/-ausgang des Reparaturgeräts explizit als eigener Vorgang – in Odoo nur implizit über Lagerbewegungen, nicht als Belegfeld |
| Reparatur-Beschr. | Beschreibungs-/Diagnosefeld | größtenteils nativ abbildbar |
| Anlagen | `ir.attachment` | nativ |
| Bemerkungen | interne Notizen | nativ |
| Stl. Material | `mrp.bom`-Materialliste | nativ über Stückliste abbildbar |
| Geräte Info | kein Standardmodell | wie oben, eigene Geräte-Stammdaten |
| Fehlerzuordnung | kein Standardfeld | Fehler-/Defektklassifizierung – Anknüpfungspunkt an `quality`-Modul, thematisch verwandt mit den bereits notierten 8D-Lücken |

**Beobachtung:** `int_repair_workshop` ist bewusst auf die Werkstattstufen-Logik
begrenzt – es dient als Listenansicht/Übersicht für die Mitarbeiter in der
Produktion, nicht als Ersatz für die kommerzielle Belegmaske. Die oben
aufgeführten Felder (Bestellnummer, Rahmenauftrag, Versand Ein-/Ausgang,
Fehlerzuordnung) sind entsprechend keine Lücken *dieses Moduls*, sondern liegen
außerhalb seines Scopes; sie wären, falls überhaupt, Sache eines eigenen
Beleg-/Auftragsmoduls. Geräte-Stammdaten (GID/Gruppe/IdentNr) bleiben davon
unabhängig eine durchgängige Lücke über alle bisher verglichenen Masken hinweg.

## Kernbeobachtung

Der Fertigungs- und Vertriebskern (Artikel, Stücklisten, Angebot → Auftrag →
Lieferschein → Rechnung, Produktion) deckt Odoo-Standard sehr gut ab. Die
Lücken liegen fast vollständig im **Reparatur- und Qualitäts-Bereich**
(8D-Prozesse, Engpass-Cockpits, Beistellung, Gelangensbestätigung) – genau die
Themen, an denen mit `int_repair_workshop` bereits angesetzt wird.

Dieser Vergleich ist ein Gedankengang zur Einordnung, keine Migrationsentscheidung.
Siehe auch Memory-Eintrag zur Odoo-Integration als noch offenem Thema.
