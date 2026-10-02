# Odoo allgemein — Plattform-Analyse

Stand 2026-09-21. Ergänzt [`erp-odoo-modulvergleich.md`](erp-odoo-modulvergleich.md) (Feld-für-Feld-
Reverse-Engineering des Legacy-ERP) und [`erp-odoo-abschlussdokument.md`](erp-odoo-abschlussdokument.md)
(Info/Verknüpfung/Logik-Klassifikation) — jene beiden Dokumente untersuchen das **Altsystem** sehr
detailliert und benennen an vielen Stellen nur beiläufig ein "Odoo-Äquivalent". Dieses Dokument dreht
den Fokus um: **Odoo selbst**, systematisch und detailliert, als Grundlage für eine informierte
Migrationsentscheidung. Reine Analyse, keine Umsetzung, keine Entscheidung vorweggenommen.

**Methodik/Grenzen:** Web-Recherche zu Odoo 19 (aktuelle Version laut den in diesem Repo bereits
etablierten Fakten — `int_filemanager` läuft produktiv auf Odoo 19) plus Abgleich mit dem, was in
diesem Repo bereits über die eigene Odoo-Instanz bekannt ist (`int-odoo-addons`, `int_filemanager`,
`int_repair_workshop`, `int_generic`, `int_legacy_erp_import`, `int_fleet_kanban_width`). **Keine
Live-Prüfung gegen HM-SRV/Tower in dieser Session** — insbesondere die Frage "läuft dort Community
oder Enterprise" ist nicht direkt geprüft, nur indirekt aus Indizien erschlossen (siehe Abschnitt 2).
Alle Quellen sind pro Abschnitt verlinkt; wo Aussagen versionsabhängig/umstritten sind (z.B.
Accounting-Umfang in Community), ist das ausdrücklich vermerkt.

---

## 1. Architektur-Grundlagen (kurzer Rahmen, nicht neu für dieses Repo)

Odoo ist ein monolithischer Python/PostgreSQL-Application-Server mit einem Modul-/App-System: jede
"App" (Verkauf, Einkauf, Lager, Fertigung, …) ist ein Addon (wie `int_filemanager` selbst), das
Modelle (`models.Model`), Views (XML), Sicherheitsregeln (`ir.rule`/`ir.model.access`) und Daten
mitbringt und sich per `depends` in andere Apps einhängt — exakt das Muster, das dieses Repo für
seine eigenen `int_*`-Module bereits konsequent nutzt. Zentrale, immer wiederkehrende Bausteine, die
in praktisch jeder App vorkommen (und die auch `int_filemanager` bereits mehrfach nutzt, siehe
die Recherche `int_filemanager_odoo_native_integration_2026-09-21.md` (nur im Git-Tag `docs-vor-aufraeumen-2026-10-02`, Pfad `docs/archiv/recherchen-odoo-bausteine/`)):

- **ORM + PostgreSQL**: ein Modell = eine Tabelle, Felder = Spalten, `Many2one`/`One2many`/
  `Many2many` = Fremdschlüssel-Beziehungen — der direkte strukturelle Gegenpart zu den im Altsystem
  gefundenen "Nummern-Match statt FK"-Mustern (`BELEG.HAUPTAUFTRAG`, `REPKOPF.BELEGNUMMER`), siehe
  Abschnitt 6.
- **`ir.rule`/`ir.model.access`**: zeilen- bzw. modellweite Zugriffsregeln — der native Gegenpart zur
  Altsystem-`BERECHTIGUNG`-Tabelle (`USERID`/`MODULID`/`FORMID`/`STATUS`/`MANDANTID`).
- **`company_id` + Multi-Company**: siehe Abschnitt 7, direkter Bezug zum Altsystem-Feld
  `BENUTZER.MANDANT`.
- **Automatisierte Aktionen, Cron, Server-Aktionen**: siehe bereits die Recherche `int_filemanager_odoo_native_integration_2026-09-21.md` (nur im Git-Tag `docs-vor-aufraeumen-2026-10-02`, Pfad `docs/archiv/recherchen-odoo-bausteine/`), Punkt 3.

---

## 2. Editionen & Lizenzmodell

| | **Community** | **Enterprise** |
|---|---|---|
| Kosten | kostenlos, Open Source (LGPL-3, Teile AGPL-3) | Abo, je nach Plan/Region stark schwankend — grob **€19,90–32/Nutzer/Monat** im "Custom"-Plan, günstigere "Standard"-Pläne regional ab ca. $9/Nutzer/Monat, ein Einzel-App-Gratisplan existiert ebenfalls |
| Hosting | selbst betrieben (wie hier: Docker/Unraid) oder auf beliebiger eigener Infrastruktur | Odoo Online (SaaS, kein Custom-Code), Odoo.sh (PaaS, Git-Deploy, Custom-Code erlaubt) oder ebenfalls selbst gehostet |
| Enterprise-exklusive Apps | — | **Studio**, **Documents**, **Sign**, **Quality**, **Field Service**, **Helpdesk**, **Approvals**, **Planning** (alle per Recherche bestätigt Enterprise-only) |
| Accounting | "Invoicing" per Default; volle Buchhaltungsfunktion technisch vorhanden, aber nur über eine versteckte Gruppen-Einstellung ("Full Accounting" unter Einstellungen → Nutzer & Firmen → Gruppen) aktivierbar — **umstrittener/versionsabhängiger Punkt, vor Ort verifizieren** | volle Buchhaltung inkl. Bank-Feed-Automatisierung, offizieller Support |
| Customizing | nur per Code (genau der Weg, den dieses Repo mit den `int_*`-Modulen bereits geht) | zusätzlich Studio (Low-Code-Editor für Views/Felder/Automatisierung) |

**Indiz zur eigenen Instanz (nicht live geprüft, nur erschlossen):** Das durchgängige Muster in
diesem Repo — eigenes `int_filemanager` statt der nativen Documents-App, eigenes
`int_filemanager.status`-Ampelmodell statt Approvals, eigene Werkstattstufen-Felder
(`int_repair_workshop`) statt Planning/Field Service — spricht stark für **Community Edition,
selbst gehostet**. Das ist aber eine Schlussfolgerung aus Verhalten, keine bestätigte Tatsache;
vor jeder Planung, die auf einer Enterprise-App aufbauen würde, unbedingt direkt prüfen
(`Apps`-Menü durchsuchen bzw. `Einstellungen → Technisch → Datenbankstruktur → Module` auf die
exakten Modulnamen `documents`/`quality`/`approvals`/`planning`/`sign`/`helpdesk`/`industry_fsm`
prüfen).

**Quellen:** [Odoo Editions Comparison](https://www.odoo.com/page/editions), [Odoo Pricing 2026 (OEC.sh)](https://oec.sh/odoo-pricing), [Odoo Community vs Enterprise 2026 (silentinfotech)](https://silentinfotech.com/blog/odoo-1/odoo-community-vs-enterprise-true-cost-comparison-2026-461), [Accounting: Community vs Enterprise (Odoo-Forum)](https://www.odoo.com/forum/help-1/accounting-community-vs-enterprise-271286), [Odoo Community Edition Guide 2026](https://oec.sh/odoo-pricing/community), [Odoo Hosting Types (OEC.sh)](https://oec.sh/blog/odoo-hosting-types-explained)

---

## 3. Die Odoo Community Association (OCA) — die "vierte Quelle"

Neben Odoo S.A.s eigenem Community-/Enterprise-Angebot pflegt die OCA (gemeinnütziger Verein,
Schweiz) über 1000 produktionsreife Module unter LGPL-3/AGPL-3, in über 250 GitHub-Repositories,
mit Code-Review-Pflicht vor Aufnahme. Praktisch relevant für dieses Projekt: **wo eine
Enterprise-App fehlt (Community-Edition, Abschnitt 2), lohnt sich vor jedem Eigenbau ein Blick in
die OCA**, ob es dort bereits eine geprüfte, freie Alternative gibt — genau das Prinzip, das
die Recherche `int_filemanager_odoo_native_integration_2026-09-21.md` (nur im Git-Tag `docs-vor-aufraeumen-2026-10-02`, Pfad `docs/archiv/recherchen-odoo-bausteine/`) bereits für den Automatisierungs-Ersatz
(`ir.actions.server` statt `base_automation`) vorschlägt, hier verallgemeinert. Konkret für die
in Abschnitt 2 genannten Enterprise-Lücken existieren OCA-Pendants für u.a. Field Service
(`OCA/field-service`), Quality-ähnliche QMS-Module und diverse Approval-Engines — vor jeder
Eigenentwicklung zu prüfen, nicht vorauszusetzen, dass sie zum jeweiligen Zeitpunkt aktuell/
gepflegt sind.

**Quelle:** [About | The Odoo Community Association (OCA)](https://www.odoo-community.org/about), [Best OCA Modules for Odoo 18/19 (2026 Guide)](https://oec.sh/guides/oca-modules-guide)

---

## 4. App-Landschaft, gespiegelt an den bereits reverse-engineerten Legacy-Bereichen

Dieser Abschnitt ist bewusst entlang derselben Gliederung wie `erp-odoo-modulvergleich.md`
aufgebaut (Adressen, Artikel, Einkauf, Produktion, Vertrieb, Reparatur, System/Zeiterfassung,
Prozess-Modul), damit sich beide Dokumente direkt gegenüberstellen lassen.

### 4a. Adressen → Contacts (`res.partner`)

Odoos `res.partner` ist bereits das, was das Altsystem mit `ADRESSEN` + Kind-Tabellen
(`ADRESSENANSPRECH`, `ADRESSENLIEFER`, `ADRESSENPROJEKT`, `ADRESSENARTRABATT`) nachbildet — nativ
als **ein** hierarchisches Modell (Firma → Kontaktpersonen als Child-`res.partner`, nicht als
separate Tabelle). Der im Altsystem schemabestätigte "Kunde UND Lieferant gleichzeitig, kein
festes Typfeld"-Befund (`DEBNR`/`KREDNR` unabhängig) entspricht **exakt** Odoos eigenem
`customer_rank`/`supplier_rank`-Modell (bereits in `erp-odoo-modulvergleich.md` selbst als
Parallele vermerkt) — einer der saubersten 1:1-Treffer im gesamten Vergleich. Lieferadressen
(`ADRESSENLIEFER`) → native `type='delivery'`-Kind-Kontakte. Artikelspezifische Rabatte
(`ADRESSENARTRABATT`) → native Preislisten (`product.pricelist`) mit Kunden-/Produktregeln, kein
Custom-Modell nötig. Die sieben Zertifikats-Slots (`ZERTI1-7`) und die Liefertreue-Kennzahlen
(`KUNDLIEFERTREUE01-05`) haben **kein** direktes natives Odoo-Äquivalent — ersteres deckt sich
strukturell gut mit dem bereits bestehenden `int_filemanager`-Verknüpfungsmuster (`res_reference`
auf `res.partner`, siehe vorheriges Dokument), letzteres wäre ein Custom-Feld/eine kleine
Auswertung.

### 4b. Artikel → Inventory/Sales (`product.template`/`product.product`)

`int_legacy_erp_import` hat bereits einen Teilimport begonnen — die dort laut
`erp-odoo-modulvergleich.md` gefundenen Modellierungsfehler (`HAUPTLIEFERANT`/`GRUPPE` als
`Char` statt `Many2one`) sind ein konkreter Datenpunkt, kein allgemeiner Odoo-Befund: Odoo selbst
bietet für beides native `Many2one`-Felder (`seller_ids`/Lieferantenpreisliste,
`categ_id`/Produktkategorie). Die Lagerbestandslogik des Altsystems (live aggregiert aus
`LAGERBUCHUNG`, `LAGERORTE.ART='S'` schließt Schrott-/Sperrlager aus) entspricht strukturell
Odoos `stock.quant`/`stock.location`-System — "Schrottlager ausschließen" ist dort über
`usage`-Typ bzw. eine gezielte Standort-Domain lösbar, kein Sonderfall. Die BOM
(`STUECKLISTEN`/`STUECKLISTENARTIKEL`) mit Routing-Zeitdaten (`SCHRITTZEIT1-7`/`RUESTZEIT1-7`)
entspricht Odoos `mrp.bom` + Arbeitsplänen (siehe 4d, Manufacturing). Der Kupferzuschlag
(codebestätigt über `TGetKupferZuschlag`) hat **kein** natives Odoo-Äquivalent — das ist eine
domänenspezifische, dynamische Rohstoffpreis-Aufschlagsberechnung, die es so in keiner Standard-
ERP-Preisengine gibt; müsste als Custom-Preisregel (Server-Aktion oder Compute-Feld auf
Bestellzeile) nachgebaut werden, unabhängig von Community/Enterprise.

### 4c. Einkauf → Purchase

Der zentrale `BELEG.BELEGART`-Diskriminator (Bestellung/Rahmenbestellung/Anfrage) entspricht in
Odoo **keinem** einzelnen Feld, sondern separaten Modellen (`purchase.order`,
Anfrage=`purchase.order` im Entwurfsstatus). Die Rahmenbestellungs-Logik
(`RAHMENNR`/`ABRUFMENGE`/`ABRUFARTIKEL`/`ABRUFPREIS`/`KONTRAKT`, Restmenge live nachgerechnet) hat
ein **direktes natives Äquivalent**: Odoos **Blanket Orders** (`purchase.requisition`-Modell,
Teil der "Purchase Agreements"-Funktion, **Community-verfügbar**, keine Enterprise-Einschränkung
laut Recherche) — langfristige Liefervereinbarungen mit vorab festgelegten Preisen, aus denen
einzelne Abrufe (RfQs) erzeugt werden, strukturell fast deckungsgleich mit dem Altsystem-Konzept.
Die Freigabe-Gates (`GEPRUEFT`/`RECHFREIGABE`/`ZEUGNIS`, blockieren die Wareneingangsbuchung) und
das automatische 8D-Lieferantenbewertungs-Verfahren bei Ausschuss (`dbeAusschuss` → automatischer
Excel-Export) haben **kein** direktes natives Äquivalent in Community — Odoos eigenes
Lieferanten-Qualitätsmanagement für sowas ist Teil der **Quality-App (Enterprise-only)**. Ohne
Enterprise wäre das ein Custom-Gate (Constraint/Server-Aktion auf `purchase.order.line`), analog
zum bereits im Filemanager etablierten `authz.require()`-Gate-Muster.

### 4d. Produktion → Manufacturing (MRP)

Odoos Manufacturing-App ist **Community-verfügbar** (Kern-MRP, nicht Enterprise-exklusiv) und
deckt BOM (mehrstufig, mit Versionierung, Phantom-BOMs für nicht separat bevorratete Baugruppen),
Arbeitspläne/Routings und Arbeitsplätze (Work Centers, mit Kapazitäts-/Effizienzfaktoren) nativ
ab — strukturell ein direkter Treffer für `STUECKLISTEN`+Routing-Zeitfelder. Das
`PRODUKTION.STATUS`-Gate (`STATUS=-1` filtert aus Bedarfsberechnung) entspricht Odoos nativer
Fertigungsauftrags-Statusmaschine (`draft`/`confirmed`/`progress`/`done`/`cancel`, automatisch aus
der Bedarfsplanung ausgeschlossen bei `cancel`). Die live berechneten EngpassCockpit-Zähler
(`CountBPos`/`CriticPath`/`EKStatus`) entsprechen Odoos MRP-Bedarfsplanungslauf
(Replenishment/"Wiederbeschaffung"), der ähnliche Engpass-/Fehlteil-Information liefert, aber
nicht in identischer Kennzahlenform — eine 1:1-Dashboard-Nachbildung bräuchte eigene Reports.
**Qualitätsprüfungen direkt im Routing** ("Quality checks can be embedded at any operation")
sind hingegen ein **Enterprise-Feature** (Quality-App-Integration in MRP) — im Altsystem die
Entsprechung zu den Freigabe-Flags (`Melden`/`Freigegeben AV`/`Freigegeben GL`/`geprüft`). Die
Fertigungsauftragsmappe (`BELEG.FAMID`, dateibasiert, `*_FM.xls`) hat in Odoo **kein**
Äquivalent als Datei-basiertes Konzept — das wäre ein Anwendungsfall für genau die Art
Datensatz-Datei-Verknüpfung, die `int_filemanager` bereits bietet (siehe Repo-Kontext-Abschnitt
im vorherigen Dokument, Punkt 8).

**Quellen:** [Manufacturing — Odoo 19.0 documentation](https://www.odoo.com/documentation/19.0/applications/inventory_and_mrp/manufacturing.html), [Work centers — Odoo 19.0](https://www.odoo.com/documentation/19.0/applications/inventory_and_mrp/manufacturing/advanced_configuration/using_work_centers.html), [Blanket orders — Odoo 19.0](https://www.odoo.com/documentation/19.0/applications/inventory_and_mrp/purchase/manage_deals/blanket_orders.html)

### 4e. Vertrieb → Sales/Invoicing

Derselbe `BELEG.BELEGART`-Diskriminator (100–104/108/115) wird in Odoo auf `sale.order` (Angebot/
Auftrag) und `account.move` (Rechnung/Gutschrift) verteilt, mit einer echten Status-Kette
(`quotation`→`sale`→Rechnung) statt eines einzelnen Felds — das im Abschlussdokument bereits als
"Gesamtbild"-Muster 1 benannte Verhalten ("Odoo verteilt dieselbe Information auf eigenständige
Modelle"). `BELEG.HAUPTAUFTRAG` (Selbstreferenz, Belegnummer-basiert) entspricht Odoos
`origin`-Feld (Text-Referenz zurück auf den Ursprungsbeleg) bzw. bei echten Rückverfolgungsketten
den nativen `Many2one`-Verknüpfungen zwischen Angebot→Auftrag→Rechnung — hier löst Odoo das
Nummer-Match-Problem des Altsystems (Muster 2 im Abschlussdokument) tatsächlich strukturell auf,
nicht nur kosmetisch. Das `AllPreisGeprueft`-Gate (blockiert Lieferschein→Rechnung, wenn nicht
jede Position geprüft) hat kein 1:1-Äquivalent, ließe sich aber als einfacher `@api.constrains`
auf `sale.order.line` nachbauen — genau das in Muster 3 des Abschlussdokuments beschriebene
"Gate/Boolean-Flag"-Prinzip, das sich in Odoo als Constraint statt als eigene Workflow-Engine
abbildet. Provisionsberechnung (`V_Vertreter`-View) hat kein natives Odoo-Kernäquivalent
(Provisionsverwaltung ist typischerweise ein CRM/Sales-Zusatzmodul, teils OCA, teils
Enterprise-Spielarten je nach Ausprägung — nicht abschließend recherchiert).

### 4f. Reparatur → Repair (`repair.order`) — bereits in Nutzung, siehe Abschnitt 5

Wird wegen der direkten Relevanz für `int_repair_workshop` in einem eigenen Abschnitt (5)
vertieft behandelt, nicht hier verkürzt.

### 4g. System & Firmendaten → Employees/Time Off/Attendances/Payroll

`BENUTZER.MANDANT`/`BERECHTIGUNG.MANDANTID` (Mandantenfähigkeit) → Odoos natives Multi-Company
(`company_id`, Abschnitt 7) — **wichtiger Fund**: das Altsystem ist bereits mandantenfähig
angelegt, das ist also keine hypothetische künftige Anforderung, sondern eine im Bestand bereits
vorgesehene (wenn auch laut `erp-odoo-abschlussdokument.md` nicht abschließend geprüfte)
Struktur. Vor einer Migrationsplanung sollte konkret geklärt werden, ob `MANDANT` in der Live-DB
tatsächlich mit mehr als einem Wert belegt ist (analog der bereits im Abschlussdokument
demonstrierten Praxis, "leeres Schema ist keine Anforderung" — dort am Prozess-Modul-Beispiel mit
0 Zeilen gezeigt).

Die Zeiterfassung (`ZEITEN`, `ZEITGRUND`, `ZEITPERSO`, `TWorkTimeObject`) mit ihrem
Soll-Arbeitszeit-/Zuschlagsmodell (Sonntag/Feiertag/Nacht) entspricht am ehesten der Kombination
aus **Attendances** (Kommt-/Geht-Zeiterfassung, Community-verfügbar) + **Time Off** + **Payroll**.
Der entscheidende, bereits recherchierte Befund: Odoos natives **Payroll**-Modul arbeitet über
"Work Entries" (ein Eintrag pro Arbeits-/Abwesenheitstyp), automatisch aus Attendances/Time
Off/Planning generiert — spezifische **Nacht-/Feiertagszuschlag-Prozentsätze pro Vertrag** sind
laut Recherche eher eine **Zusatz-App-Fähigkeit** (spezialisierte Schichtplanungs-Apps), nicht
selbstverständlicher Kernbestandteil von Payroll selbst — hier vor einer Migrationsplanung
gezielt nachprüfen, ob das vorhandene Zuschlagsmodell (im Altsystem laut Codebefund ohnehin nur
teilweise tatsächlich bis zum Euro-Betrag durchgerechnet, siehe `ZEITGRUND.SONNZUSCHLAG`-Befund
"in der Live-DB durchgehend NULL") überhaupt noch in vollem Umfang gebraucht wird, oder ob dieser
Teil laut Live-Daten längst ein totes Feature ist (Parallele zu Muster 4 im Abschlussdokument).
`ZeitPerso.beginn`/`beginnori` (echter Audit-Trail für Zeitkorrekturen) entspricht strukturell
Odoos generischem Chatter-/Änderungslog-Mechanismus (bereits in `int_filemanager` über
`mail.thread` genutzt) — dort automatisch für jedes Feld, ohne eigene Original/Korrektur-Spalten.

Die `BERECHTIGUNG`-Tabelle (aktiv genutzt, `BENUTZER`-Flag-Spalten hingegen als Altlast
identifiziert) — genau das Odoo-native `ir.model.access`/`ir.rule`-Paar, mit demselben
"Modell-Ebene + Datensatz-Ebene"-Prinzip, nur granularer (Odoo kann zusätzlich auf Feldebene über
Gruppen einschränken).

**Quellen:** [Work entries — Odoo 19.0](https://www.odoo.com/documentation/19.0/applications/hr/payroll/work_entries.html), [Odoo Time Off](https://www.odoo.com/app/time-off)

### 4h. Prozess-Modul → Project/Timesheets/Automation

Das im Altsystem als generisches, aber weitgehend ungenutztes BPM-Konzept angelegte Prozess-Modul
(`PROZESSMAIN`/`-STRUKTUR`/`-OBJEKTE`, 0 Zeilen) hätte in Odoo als grobe Entsprechung die
**Project**-App (Aufgaben, Stufen, Automatisierungsregeln pro Stufe) — aber da dieser Teil des
Altsystems laut eigenem Befund nie produktiv wurde, ist das eher eine theoretische Zuordnung.
Praktisch relevanter: die **tatsächlich aktiv genutzte** Zeitstempel-Ebene
(`PROZESSZEITEN.OBJEKTART`, `FirstID`-Session-Gruppierung, 0=Projekt/154=Reparatur) entspricht
Odoos **Timesheets**-App (`account.analytic.line`, buchbar auf Projekt **und** — relevant hier —
auch auf einen Reparaturauftrag, da `repair.order` ebenfalls analytisch verbuchbar ist, siehe
Abschnitt 5). Der generische `ModulID`+`ObjektID`-Polymorphie-Mechanismus
(`PROZESSOBJEKTE`, aber auch `InfoDokumente`/`InfoNotizen` bei Reparatur) ist strukturell exakt
das, was `ir.attachment`s `res_model`/`res_id`-Paar nativ leistet — bereits in
die Recherche `int_filemanager_odoo_native_integration_2026-09-21.md` (nur im Git-Tag `docs-vor-aufraeumen-2026-10-02`, Pfad `docs/archiv/recherchen-odoo-bausteine/`) (Punkt 2) als Anschlusspunkt
identifiziert, hier zusätzlich bestätigt durch einen weiteren, unabhängigen Fund im Altsystem
selbst (das Altsystem hat also bereits **zwei separate** Ad-hoc-Umsetzungen desselben Polymorphie-
Bedarfs: `InfoDokumente`/`InfoNotizen` UND `PROZESSOBJEKTE`, jeweils eigenständig statt geteilt
— ein Beleg dafür, wie oft dieser Bedarf im Betrieb tatsächlich auftritt, und ein zusätzliches
Argument, warum Odoos **ein** generischer Mechanismus (`ir.attachment`) hier strukturell sauberer
wäre als der Altsystem-Ansatz mit mehreren Parallelimplementierungen).

---

## 5. Vertiefung: Odoo Repair (`repair.order`) — direkter Abgleich mit dem Reparatur-Modul

Besonders relevant, weil `int_repair_workshop` **bereits produktiv auf dem nativen `repair`-Modul
aufsetzt** (nicht neu gebaut wie `int_filemanager`) — hier lohnt der genaueste Abgleich.

**Was die native Repair-App laut Recherche abdeckt:** Reparaturauftrag anlegen (Produkt, Kunde,
Techniker, Priorität, Termin), automatischer Lagerabgang der verbauten Teile in Echtzeit,
Warnungen bei Teilemangel, vollständiger Workflow inkl. Kundenfreigabe und Rechnungsstellung,
lückenlose Protokollierung jeder Aktion.

**Abgleich mit den im Altsystem gefundenen Reparatur-Spezifika:**

| Altsystem-Fund | Native Repair-App | Einschätzung |
|---|---|---|
| Zwei parallele Kostenvoranschläge (`FROMBELEGART` KVA1/KVA2, `btnAktiv1/2Click`) | kein natives "zwei parallele Angebote"-Konzept bekannt | vermutlich Custom-Erweiterung nötig, wie es `int_repair_workshop` mit den sieben Werkstattstufen bereits tut |
| FAM/BGS-Verknüpfung (`RefOID`/`RefOID2`, farbcodierte Anzeige) | generische `ir.attachment`/Chatter-Verknüpfung, kein farbcodiertes Zwei-Typ-Pendant | näher an Abschnitt 4h/Punkt 2 des vorherigen Dokuments als an Repair selbst |
| KST/KFKT/KWERT + RKM/RKMFAKTOR/RKMWERT (Std./km × Faktor = Wert) | keine native "Faktor×Menge=Wert"-Kalkulationszeile in Repair bekannt | Custom-Feld/Compute, analog Kupferzuschlag (4b) |
| `ADRESSEN.ABWUST` überschreibt `MWSTSATZ` beim Kundenwechsel | Steuer-Zuordnung läuft in Odoo generisch über Fiscal Position (`account.fiscal.position`), nicht Repair-spezifisch | eher ein 4e-Thema (Steuerlogik) als ein Repair-Thema |
| 8D-Belastungsanzeige bei Ausschuss (automatischer Excel-Export) | keine native Entsprechung, siehe 4c | Custom-Server-Aktion |
| Reparaturhistorie (Live-Join Beleg/Repkopf/RepAuftrag/RepArtikel) | native Chatter-Historie + `repair.order`-Suchfilter nach Produkt/Seriennummer | strukturell näher an nativ als im Altsystem, da Odoo Seriennummern-Rückverfolgung (`lot_id`) als Kernfeature hat |

**Fazit für diesen Abschnitt:** Die Basis-Reparaturabwicklung ist bereits gut durch die native App
gedeckt (weshalb `int_repair_workshop` bewusst nur **ergänzt**, nicht ersetzt — "Odoos bestehende
Felder werden bewusst weiterverwendet statt dupliziert", eigene Aussage des Moduls). Die im
Altsystem gefundenen Besonderheiten (Doppel-KVA, Zeit×Faktor-Kalkulation, 8D-Verfahren) haben
überwiegend **keine** native Entsprechung — das ist aber keine Repair-App-Schwäche, sondern
erwartbar: das sind sehr firmenspezifische Prozessdetails, für die auch ein Neubau auf Odoo-Basis
denselben Custom-Anteil bräuchte wie heute in `int_repair_workshop` bereits praktiziert.

**Quellen:** [Repair | Odoo Apps Store](https://apps.odoo.com/apps/modules/category/Repair/browse), [How to Manage Repair Orders in Odoo 18 Repairs App?](https://www.netilligence.io/blog/how-to-manage-repair-orders-in-odoo-18-repairs-app/)

---

## 6. Die vier wiederkehrenden Muster aus dem Abschlussdokument — wie Odoo jedes davon löst

Direkter Rückbezug auf "Gesamtbild: die vier wiederkehrenden Logik-/Verknüpfungsmuster" in
`erp-odoo-abschlussdokument.md` — dort als Erkenntnis über das Altsystem formuliert, hier
gespiegelt: **wie löst Odoo strukturell genau dasselbe Problem**, nicht nur "wie heißt das
Äquivalent".

1. **Diskriminator-Feld (`BELEG.BELEGART`) → eigenständige Modelle.** Bereits mehrfach oben
   belegt (4c/4e/4f) — Odoo verzichtet komplett auf ein zentrales "was ist dieser Beleg"-Feld,
   weil jeder Belegtyp sein eigenes Modell mit eigener Zustandsmaschine ist. Vorteil: Verhalten
   ist typsicher statt laufzeitgeprüft. Nachteil (bereits im Abschlussdokument richtig benannt):
   bei einer Migration verschwindet der Diskriminator nicht einfach, sein *Verhalten* muss pro
   Zielmodell explizit nachgebaut werden — kein Automatismus.
2. **Nummern-Match/`ModulID`+`ObjektID` → echte Fremdschlüssel bzw. `ir.attachment`s generisches
   Polymorphie-Paar.** Siehe 4e (Odoos `Many2one`-Ketten) und 4h (der `ir.attachment`-Vergleich).
   Odoos FK-Modell erzwingt referenzielle Integrität auf DB-Ebene (`ON DELETE`-Verhalten,
   `NOT NULL`-Constraints) — im Altsystem laut eigenem Befund nirgends erzwungen.
3. **Gates (Boolean-Flags) + Faktor×Menge=Wert-Berechnung → Constraints/Compute-Felder.**
   Odoos `@api.constrains`/`@api.depends`-Mechanismus ist genau dafür gebaut — kein
   Workflow-Engine-Overhead nötig für einfache Gates, wie im Abschlussdokument selbst bereits
   richtig eingeordnet ("eher als Constraints/Computed Fields als als eigene Workflow-Engine").
   Für die wenigen Fälle, die tatsächlich mehrstufige Freigaben sind (KVA1/KVA2,
   Rechnungsfreigabe), böte Odoo zusätzlich die **Enterprise**-Approvals-App oder — Community-
   sicher — ein eigenes `state_selection`-Feld, exakt das bereits in `int_filemanager` bewährte
   Ampel-Muster (siehe die PaperOffice-Recherche (nur im Git-Tag `docs-vor-aufraeumen-2026-10-02`: `docs/int_filemanager_paperoffice_recherche.md`), Baustein 4).
4. **Ambitionierte, nie produktiv gewordene Logik-Schichten neben schlankeren aktiv genutzten
   Nachfolgern → dasselbe Risiko gilt für eine Odoo-Migration selbst.** Die im Abschlussdokument
   formulierte Lehre ("ein leeres Schema ist keine Anforderung") gilt nicht nur für das
   Altsystem, sondern als Methodik-Hinweis für die Migration selbst: vor dem Nachbau **jedes**
   hier aufgeführten Altsystem-Bereichs in Odoo sollte derselbe Live-Daten-Check erfolgen, der
   bereits beim Prozess-Modul (0 Zeilen) und der `WARTUNG`-Kalibrierung (1 Zeile) angewendet
   wurde — nicht jedes Schema verdient eine 1:1-Odoo-Entsprechung.

---

## 7. Multi-Company vertieft — direkter Bezug zum Altsystem-Fund `BENUTZER.MANDANT`

Odoos Multi-Company-Architektur: **eine** gemeinsame PostgreSQL-Datenbank für alle Firmen,
Isolation über ein `company_id`-Feld auf praktisch jedem transaktionalen Datensatz, durchgesetzt
über `ir.rule`-Domains (`('company_id', 'in', company_ids)`) — strukturell exakt dasselbe Prinzip
wie das bereits im Repo etablierte Schutzordner-ACL-Muster (`acl_rules.py`), nur auf
Firmenebene statt Pfadebene. Stammdaten (Produkte, Kontakte) können je Datensatz **global**
(Firmenfeld leer) oder **firmenspezifisch** gehalten werden — flexibler als eine starre
Alles-oder-nichts-Trennung. Wichtiger Hinweis aus der Recherche für Entwickler: ein Default für
`company_id` muss konsequent in jedem Schreibpfad gesetzt sein (UI, Skripte, automatisierte
Aktionen, API) — sonst schlagen Datensätze in bestimmten Kontexten fehl, ein Muster, das dem
bereits in diesem Modul etablierten Sorgfaltsgrad bei sicherheitsrelevanten Feldern entspricht
(vgl. `protected_folder_id`-Pflege in `int_filemanager`).

**Bezug zum Altsystem:** `BENUTZER.MANDANT` + `BERECHTIGUNG.MANDANTID` zeigen, dass Mandantentrennung
im Altsystem bereits als Konzept existiert — Odoo hätte dafür mit seinem nativen Multi-Company-
System eine **strukturell robustere, aber im Kern gleichwertige** Lösung. Vor jeder
Migrationsplanung: prüfen, ob `MANDANT` in der Live-DB tatsächlich mehrere unterschiedliche Werte
trägt (nicht nur schemabestätigt, sondern **datenbestätigt**, im Sinne der bereits etablierten
Sorgfalt dieses Projekts) — nur dann ist Multi-Company überhaupt ein relevantes Zielbild, sonst
wäre eine Single-Company-Instanz einfacher und ausreichend.

**Quellen:** [Multi-company Guidelines — Odoo 19.0 documentation](https://www.odoo.com/documentation/19.0/developer/howtos/company.html), [Odoo Multi-Company Setup: 2026 Step-by-Step Guide](https://ecosire.com/blog/odoo-multi-company-setup-guide)

---

## 8. Einordnung: wo Odoo strukturell überlegen ist, wo eigener Aufwand bleibt

**Strukturell klar überlegen** (kein Diskussionsbedarf, unabhängig von Community/Enterprise):
erzwungene referenzielle Integrität statt Nummern-Matches (Muster 2), Zustandsmaschinen statt
Diskriminator-Feld (Muster 1), generischer Audit-Trail über Chatter statt manueller
Original/Korrektur-Spaltenpaare, generische Datei-/Dokumenten-Verknüpfung über
`ir.attachment.res_model`/`res_id` statt mehrfacher Ad-hoc-`ModulID`/`ObjektID`-Implementierungen.

**Community deckt bereits gut ab:** Kontakte/Kunde-Lieferant-Dualität, Blanket Orders
(Rahmenbestellungen), Kern-Manufacturing (BOM/Routing/Work Centers), Kern-Reparaturabwicklung
(siehe Abschnitt 5), Timesheets, Attendances, Multi-Company.

**Enterprise nötig (oder OCA-Alternative prüfen) für:** Quality-App-Integration in
Einkauf/Fertigung (Freigabe-/Zeugnis-Gates, 4c/4d), Field Service/Planning (falls
Außendienst-Reparaturen relevant werden), Documents/Sign/Approvals/Studio (bereits im vorherigen
Dokument behandelt), differenzierte Schicht-/Nachtzuschlag-Payroll-Automatisierung (4g).

**Bleibt in jedem Fall Custom-Aufwand, Odoo-Edition unabhängig:** Kupferzuschlag/domänenspezifische
Preisaufschläge (4b), Faktor×Menge=Wert-Sonderkalkulationen (KST/KFKT, RKM/RKMFAKTOR, 5),
8D-Lieferantenbewertungsprozess (4c), Doppel-Kostenvoranschlag-Konzept (5) — durchweg
firmenspezifische Prozesslogik, die kein Standard-ERP (nicht nur Odoo) vorgefertigt mitbringt.
Genau der Custom-Anteil, den dieses Repo mit seinen `int_*`-Modulen bereits konsequent so
handhabt — eine Odoo-Migration würde diesen Aufwand nicht eliminieren, aber auf eine strukturell
robustere Basis stellen (Muster 1–2 oben) statt ihn zusätzlich zu den bestehenden
Altsystem-Schwächen zu tragen.

---

## Verweis

Dieses Dokument ersetzt nicht `erp-odoo-modulvergleich.md`/`erp-odoo-abschlussdokument.md`
(dort: Feldbelege aus dem Altsystem-Code), sondern liefert die fehlende Gegenseite — eine
eigenständige, detaillierte Betrachtung dessen, was Odoo als Zielplattform tatsächlich mitbringt.
Für eine Migrationsentscheidung sollten alle drei Dokumente zusammen gelesen werden.
