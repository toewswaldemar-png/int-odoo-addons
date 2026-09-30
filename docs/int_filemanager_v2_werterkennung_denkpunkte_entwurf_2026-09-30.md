# int_filemanager 2: Werterkennung – Denkpunkte 1–3 (Entwurf)

Entwurf des Dauerlaufs (Aufgabe A3), Stand 2026-09-30. **Keine Entscheidung, keine Freigabe.** Das
[Konzept Oberfläche/Kasten-Auswahl](int_filemanager_v2_werterkennung_oberflaeche_konzept_2026-09-29.md) ist nicht angefasst;
was hier steht, übernimmt der Nutzer (oder nicht). Behandelt werden Abschnitt 11 des Konzepts, Punkte 1 (Datenmodell),
2 (Rechte) und 3 (Leistung).

## 0. Abdeckung und Methode

| Was | Wie geprüft | Nicht geprüft |
|---|---|---|
| Datenmodell heute | Code gelesen: `field_value`, `extraction_field`, `extraction_hint`, `apply_field_values`/`suggest_field_values` im Knoten, `value_types.py` (Dauer-Einheiten) | Oberflächen-Code (existiert für die neuen Teile noch nicht) |
| Verhalten der `x_`-Felder in Odoo | Quellcode `base/models/ir_model.py` im Image `odoo:19.0-hm-test` (Namensregel, Typwechsel, Umbenennen, Löschen) | mehrere Odoo-Prozesse im laufenden Betrieb (nur aus Konzept 10.7 bekannt: laden beim nächsten Aufruf neu) |
| Rechte | Zugriffsliste, Bereichs-Regeln und HTTP-Tests des Moduls gelesen | keine neuen Tests geschrieben (Produktivcode nicht Teil dieser Aufgabe) |
| Leistung „Vorschlagen“ | **Messung** im Wegwerf-Container `dl_bench` (Image `odoo:19.0-hm-test`), echter Code von `value_suggest.py`/`value_types.py`, **synthetische** Seiten (keine privaten Daten); Skript [`prototypes/werterkennung/perf_suggest_bench.py`](prototypes/werterkennung/perf_suggest_bench.py) | reale Dokumente; Umwandeln/Texterkennung; Nachlesen und QR (Code existiert noch nicht) |
| Leistung „Spalten“ | **Messung** im Wegwerf-Container `dl_pg` (PostgreSQL 16): 1 Mio. Knoten, 2,4 Mio. Werte; Skript [`prototypes/werterkennung/perf_spalten.sql`](prototypes/werterkennung/perf_spalten.sql) | **Odoos Schreibweg (ORM)** – nur reines SQL gemessen; Betrieb unter gleichzeitiger Last |

Beide Container sind wieder entfernt; Live-Instanz und `fmtest_*` unberührt.

## 1. Datenmodell im Detail

### 1.1 Herkunft (`source`) und Prüfstatus

**Heute:** `field_value.source` kennt `rule` (Vorschlag übernommen) und `manual` (getippt). `apply_field_values` macht aus
allem außer „rule“ ein „manual“, und `_check_origin` verlangt bei „rule“ eine Regel des Felds.

**Vorschlag:** `source` sagt nur, **wo der Wert gefunden wurde**: `rule`, `manual`, neu `area` (aus gezogenem/gemerktem
Kasten oder Markierung) und `qr` (GiroCode). **„Automatisch übernommen“ ist keine Herkunft, sondern eine Prüfart** und
gehört an das Dokument:

| Feld am Knoten (neu) | Art | Bedeutung |
|---|---|---|
| `review_state` | Auswahl `unreviewed` / `reviewed` / `auto`; leer = nicht in der Prüfung | Prüfstatus (N4), vom System gesetzt, getrennt vom Freigabestatus `status_id` |
| `review_uid`, `review_date` | Nutzer, Zeitpunkt | „geprüft von, am“ |
| `review_revision_id` | Fassung | Prüfung gilt nur, solange dies die aktuelle Fassung ist; eine neue Fassung macht sie hinfällig, ohne Zurücksetzen (gleiches Prinzip wie `field_value.revision_id`) |

Begründung: Ein Wert kann per Regel gefunden und trotzdem automatisch übernommen sein. Wer beides in `source` mischt,
kann „automatisch, nie angesehen“ und „per Regel gefunden“ nicht mehr getrennt filtern.

| Alternative | Vor-/Nachteil |
|---|---|
| `auto` als weiterer `source`-Wert | eine Spalte weniger, aber Fundort und Prüfart vermischt |
| Prüfstatus je Wert statt je Dokument | feiner, aber „nächstes ungeprüftes Dokument“ und die Abarbeitungsliste brauchen die Dokument-Ebene |

**Offene Produktfrage (Fragen unten):** Welche Dateien zählen als „ungeprüft“? Beginnt jede Datei mit `unreviewed`, füllt
sich die Abarbeitungsliste mit dem ganzen Bestand (Ordner, Bilder, Musik …). Empfehlung: Spalte leer, bis ein Dokument **in
die Prüfung aufgenommen** wird (Eingangsordner, Schritt 7, oder Knopf „zur Prüfung vormerken“). Nebeneffekt: kein
Nachtrag für vorhandene Zeilen; eine Spalte ohne Standardwert anzuhängen kostet auch bei 1,4 Mio. Zeilen Millisekunden
(Messung Konzept 10.7, hier bestätigt: 0,16 s für zehn Spalten bei 1 Mio. Zeilen).

Schreibweg: `review_state` wird nur in `apply_field_values` (Nutzer: `reviewed`) und im Automatikweg (`auto`) gesetzt, nie
über ein `write` von außen (siehe 1.5).

### 1.2 Gemerkte Kästen (`int_filemanager.extraction_area`) und Absender-Schalter

Muster ist `extraction_hint` (Absender + Beschriftung, `hit_count`, `last_date`, eindeutige Kombination als
`models.Constraint`). Vorschlag:

| Feld von `extraction_area` | Art | Anmerkung |
|---|---|---|
| `partner_id` | Many2one `res.partner`, Pflicht, `ondelete="cascade"`, Index | Absender; anders als bei Hinweisen **kein „für alle“** (Konzept 5.5: Pflicht) |
| `page` | Integer | `1…n`, `-1` = letzte Seite (Summen), Vorbild Paperless |
| `x0`, `top`, `x1`, `bottom` | Float | **relativ zur Seite 0…1** (wie Odoos Extract API), damit andere Seitengrößen passen |
| `anchor_label` | Char | normalisierte Beschriftung im Kasten (Verschiebung, Konzept 6.2); leer = nur gemerkte Lage, **dann ohne Vorrang** |
| `anchor_x`, `anchor_top` | Float | Lage des Ankers relativ zur Seite; daraus die Verschiebung |
| `field_ids` | Many2many `extraction_field` | Felder, die beim Speichern aus diesem Kasten kamen (bestimmt die Feldliste, Konzept 4.4) |
| `hit_count`, `last_date` | Integer, Datetime | wie bei `extraction_hint` |

Eindeutigkeit: **keine** SQL-Eindeutigkeit (mehrere Kästen desselben Absenders auf einer Seite sind normal). Stattdessen:
ein neuer Kasten, der einen vorhandenen desselben Absenders und derselben Seite zu einem großen Teil überdeckt
(Schwelle, z. B. 80 %, beim Bau festlegen), aktualisiert diesen.

**Absender-Schalter „automatisch übernehmen“ (U1/U3):** nicht an `res.partner` (Fremdtabelle, Schreiben braucht
Partner-Rechte, das Feld erschiene in jedem Partner-Formular). Vorschlag: kleines Modell `int_filemanager.extraction_sender`
mit `partner_id` (eindeutig), `auto_mode` (Boolean, nur Verwalter), `clean_streak` (bestätigte Dokumente ohne Korrektur in
Folge, Konzept 10.4), `last_change`. Die Alternative (Feld an `res.partner`) hat ein Modell weniger, verzahnt sich aber mit
einem Fremdmodell → **nicht empfohlen**.

Rechte: wie `extraction_hint` – Nutzer lesen **nicht** (die Liste würde verraten, von welchen Absendern es Dokumente in
fremden Bereichen gibt, so begründet schon in `_extraction_specs`), Verwalter lesen und löschen; geschrieben wird nur
über Methoden. Löschen eines Absenders entfernt Kästen und Schalter (`cascade`), Dokumente und Werte bleiben.

### 1.3 Wertart → echte Spalte (N9)

Die typisierten Spalten in `field_value` bleiben die Quelle; die `x_`-Spalte am Knoten ist der **Spiegel der aktuellen
Fassung**. Vorschlag:

| Wertart | Spalten am Knoten | Odoo-Typ | Anmerkung |
|---|---|---|---|
| `number`, `word`, `iban`, `vat`, `email` | 1 | `char` | Nummer bleibt Text (führende Nullen) |
| `date` | 1 | `date` | – |
| `period` | 3: von, bis, Dauer | `date`, `date`, `float` | Ein Wert ist Zeitraum **oder** Dauer (Wochen, Monate, Jahre laut `_DURATION_UNITS`); Dauer in **Monaten** spiegeln, Wochen-Dauern nicht (Umrechnung ungenau) – offen, Frage 2 |
| `amount` | 2: Betrag, Währung | `monetary` + `many2one res.currency` | `monetary` braucht in Odoo ein Währungsfeld |
| `quantity` | 1 | `float` | Einheit steht im Katalogfeld (`extraction_field.unit`, genau eine je Feld); abweichende Einheit im Dokument nicht spiegeln – Frage 2 |
| U-7 Verknüpfung | 1 | `many2one` (Ziel im Katalogfeld) | `ondelete="set null"` |
| U-7 Auswahl | 1 | `selection` | Optionen als `ir.model.fields.selection`; Option entfernen leert die Werte |
| U-7 Ankreuzfeld, Prozent, Telefon, Monat | 1 | `boolean`, `float`, `char`, `date` (erster Tag) | Monat als Datum ermöglicht Gruppieren nach Monat mit Odoo-Mitteln |

Verhalten von Odoo, im Quellcode belegt (`ir_model.py`): Name eines manuellen Felds muss mit `x_` beginnen (SQL-Prüfung) und
darf nur Buchstaben, Ziffern und Unterstrich enthalten, höchstens 63 Zeichen; **Typwechsel nicht möglich** („drop it and
create it again“) – passt zur bestehenden Sperre der Wertart nach dem ersten Wert; **Umbenennen** geht (Spalte wird
umbenannt, aber nur ein Feld je Aufruf); **Löschen** entfernt die Spalte.

**Namensschema (Vorschlag): `x_fm_<id des Katalogfelds>`** (bei mehreren Spalten mit Endung `_from`, `_to`, `_duration`,
`_currency`), nie aus dem Namen abgeleitet. Umbenennen (auch einer Übersetzung) berührt die Spalte nicht, keine Kollision
mit Studio- oder Nutzerfeldern, immer gültig und kurz. Die **Bezeichnung** (`field_description`) folgt dem Katalognamen
und wird beim Umbenennen nachgezogen; Export und Pivot zeigen die Bezeichnung. Alternative lesbare Namen
(`x_fm_wasserverbrauch`): schöner für Filter von Hand, aber jedes Umbenennen würde ein Spaltenumbenennen (Sonderzeichen,
Länge, Doppelte) → **nicht empfohlen**. Die Zuordnung Katalogfeld ↔ Spalten ist aus `id` und Wertart **berechenbar**
und muss nicht gespeichert werden; „Spalten neu aufbauen“ legt Fehlendes an und meldet Verwaistes.

**Archivieren/Löschen (N9):** Odoo hat für Spalten keinen „nur ausblenden“-Schalter außer `groups` an `ir.model.fields`
(wirkt echt: Zugriffsfehler beim Lesen, auch in Export und Pivot). Vorschlag: archivierte Felder bekommen `groups` auf eine
leere Verwalter-Gruppe; **nicht geprüft**, ob dies alle Ansichten sauber ausblendet – beim Bau ausprobieren. Löschen nur als
Verwalter-Aktion mit Rückfrage über `ir.model.fields.unlink` (`DROP COLUMN` in der Messung: 3,8 s für zwei Spalten, siehe 3.2).

### 1.4 Was beim Umbenennen eines Katalogfelds passiert

- **Name (übersetzbar):** nur die Spaltenbezeichnung folgt; Werte, Lernhinweise und Kästen hängen an der `id`.
- **Wertart:** bleibt gesperrt, sobald Werte da sind (besteht).
- **Einheit eines Mengenfelds:** heute änderbar (`write` sperrt nur `value_type`). Änderte sie sich, stünden alte und neue
  Einheiten in einer Spalte. Vorschlag: **wie die Wertart sperren** (Frage 3).
- Die Namensprüfung bleibt eine Python-Prüfung (bewusst, wegen JSON-Übersetzungen).

### 1.5 Befund: „nur vom System befüllt“ (N9) hält nicht von selbst

Die Zugriffsliste gibt Dateimanager-Nutzern **Schreibrecht auf den ganzen Knoten** (`access_int_filemanager_node_user`,
1,1,1,1), begrenzt nur durch die Bereichs-Regel `rule_node_scope_write`. Eine `x_`-Spalte am Knoten wäre damit für jeden
Nutzer mit Schreibrecht auf die Datei per `call_kw`/JSON-2 beschreibbar, vorbei an `apply_field_values` (Fassungsprüfung,
Wert erneut lesen). „Schreibgeschützt“ in der Oberfläche (`readonly`) ist keine Sicherung.

**Vorschlag:** `write` und `create` des Knotens (überschrieben schon für `_clean_name`) lehnen die verwalteten Spalten und
die Prüfstatus-Felder ab, wenn `not self.env.su`. Der eigene Weg schreibt über `sudo()` (wie `apply_field_values` heute bei
den Werten), ein Nutzeraufruf nie; `env.su` lässt sich vom Client nicht setzen (anders als ein Kontextwert). Dazu
`copy=False` auf den Spalten, damit Kopieren einer Datei keine Werte mitnimmt. **Test (später, mit U-7):** HttpCase nach
Muster `test_json2_values_cannot_be_written_directly`, je Spaltenart. Restrisiko: andere `sudo()`-Stellen (Watcher,
Import) könnten die Spalten ebenfalls schreiben; die Ablehnung schützt nur vor Nutzerzugriff. Das Verhalten von
`env.su` bei `call_kw` ist Odoo-Grundwissen und **nicht in diesem Lauf nachgestellt**.

## 2. Rechte je neuem Server-Aufruf

Muster W-5: **Recht auf den Knoten als Nutzer prüfen, dann erst `sudo()`**; nichts aus dem Client übernehmen; `revision_id`
prüfen; Tests: Nicht-Admin auf fremdem Knoten über `call_kw` **und** JSON-2 → verweigert (Vorlage
`tests/test_v2_field_value_http.py`), alte Fassung → Fehler. Die Prüfung steht **in** der Methode, nicht im Controller (alle
Aufrufe sind `@api.model`-Methoden des Knotens und über beide Wege erreichbar).

| Aufruf | Prüfung vor dem `sudo` | Wer | Test (Vorschlag) |
|---|---|---|---|
| `suggest_field_values(node_id, areas=[…])` (erweitert) | `check_access("read")` (besteht); Kästen: Anzahl begrenzen (z. B. ≤ 20), Seite gültig, Werte in 0…1 – Fehler statt stilles Abschneiden | Leserecht | fremder Knoten; Kasten außerhalb 0…1; zu viele Kästen |
| `read_selection(node_id, revision_id, field_id, start, end)` | Leserecht; `revision_id` = aktuelle Fassung; `start`/`end` im Text; **Länge begrenzen** (~200 Zeichen); Feld existiert und ist aktiv | Leserecht (speichert nichts) | fremder Knoten; alte Fassung; Markierung über die ganze Datei |
| `create_field_from_pair(label, value_type, …)` | **Verwalter** (Gruppe), nicht „Schreibrecht auf einen Knoten“; Wertart aus der Liste; Name eindeutig | Verwalter | Nutzer → AccessError über `call_kw` und JSON-2 |
| „Feld vorschlagen“ | Leserecht auf den Knoten; Texte und Längen begrenzen; **Nachricht enthält nur, was der Nutzer selbst sehen darf** (kein Pfad/Absender aus fremden Bereichen) | Leserecht | fremder Knoten verweigert; Nachricht ohne unlesbaren Pfad |
| Kasten merken (in `apply_field_values`) | Schreibrecht (besteht); Absender = der **am Knoten** bestätigte Absender, nicht frei wählbar; Lage gültig | Schreibrecht | fremder Absender in den Daten → Fehler |
| Gelerntes ansehen | Zugriffsliste | Verwalter | Nutzer sieht nichts |
| Gelerntes löschen, „Kästen dieses Absenders verwerfen“, Absender-Schalter | Verwalter (U3) | Verwalter | Nutzer → AccessError |
| „Spalten aus den Werten neu aufbauen“ | Verwalter; in Stapeln (3.2) | Verwalter | Nutzer → AccessError; Abbruch mittendrin lässt Spalten benutzbar |
| Prüfstatus setzen | nur innerhalb `apply_field_values`, nie eigener Aufruf | – | `write({"review_state": …})` durch Nutzer → verweigert (1.5) |
| Ausschnitt nachlesen (Umwandler-Aufgabe) | Leserecht **vor** dem Einstellen; Abholen des Ergebnisses wieder mit Knotenrecht (Paperless-Lücke: Seitenbild ohne Rechteprüfung) | Leserecht | fremder Knoten: weder Auftrag noch Ergebnis |

Querschnitt:
- Neue Modelle nur mit Verwalter-Zeile in `ir.model.access.csv`. Eine Bereichs-Regel für `extraction_area` ist nicht nötig,
  solange nur Verwalter lesen. Würde das Gelernte für Nutzer sichtbar, bräuchte es eine Regel „nur Absender, zu denen der
  Nutzer Dokumente lesen darf“ (teure Abfrage) → Verwalter-only lassen.
- Die Spalten am Knoten folgen automatisch den Knoten-Regeln. Für sensible Felder (Gehalt) `groups` an `ir.model.fields`
  (U-7 „Gruppen-Sichtbarkeit“); Test: `read_group`/Export ohne Gruppe verweigert.

## 3. Leistung

### 3.1 Vorschlagen bei langen Dokumenten (Messung)

Aufbau: synthetische Rechnungsseiten (45 Zeilen, ~8 % mit Beschriftung und Wert: Nummer, Datum, Betrag, IBAN,
USt-IdNr., Verbrauch), 8 Felder mit Stichwörtern, echter Code von `value_suggest.suggest`, ein Prozess, je Seitenzahl eine
Messung.

| Seiten | Wörter | Wortliste (JSON) | JSON lesen | `Page` bauen | `suggest` | Speicher-Spitze |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 387 | 0,02 MB | 0,002 s | 0,002 s | 0,04 s | 0,4 MB |
| 10 | 3.746 | 0,20 MB | 0,02 s | 0,02 s | 0,05 s | 1,3 MB |
| 50 | 19.127 | 1,04 MB | 0,12 s | 0,08 s | 0,20 s | 6,6 MB |
| 100 | 37.933 | 2,10 MB | 0,22 s | 0,18 s | 0,43 s | 13 MB |
| 300 | 113.482 | 6,45 MB | 0,69 s | 0,56 s | 1,37 s | 40 MB |
| 1000 | 379.378 | 22,2 MB | 2,3 s | 2,0 s | 4,5 s | 140 MB |

**Befund:** linear in der Wortzahl, keine Ausreißer. 100 Seiten ≈ 0,8 s insgesamt (lesen + `Page` + `suggest`); die Obergrenze
des Umwandlers (500.000 Wörter, `MAX_WORDS`) läge extrapoliert bei ≈ 8–10 s und ≈ 190 MB in **einem** Odoo-Prozess. Weitere
Grenzen heute: Odoo liest Wortlisten bis 40 MB (`MAX_WORDS_BYTES`), der Umwandler liest Text nicht gescannter PDFs nur bis
Seite 400 (`MAX_PDF_TEXT_PAGES`), Texterkennung bis 2.000 Seiten (`MAX_OCR_PAGES`), Text bis 2 Mio. Zeichen.

**Vorschläge daraus:**
1. Heute liest jeder `suggest_field_values`-Aufruf die **ganze** Wortliste und baut die `Page` neu. Beim Ziehen und
   Anpassen von Kästen käme derselbe Aufruf mehrfach hintereinander. **Empfehlung:** Kasten-Vorschläge rechnen nur die
   Wörter im Kasten (die Wörter sind nach Position sortiert, ein Ausschnitt ist billig); die Kosten hingen dann nicht von der
   Seitenzahl ab. **Nicht gemessen**, beim Bau vorher/nachher messen.
2. Die Wortliste nicht ganz an den Browser schicken: 1.000 Seiten = 22 MB JSON. Falls der Browser Wörter braucht (zum
   Anklicken), Aufruf „Wörter einer Seite“.
3. **Harte Zeitgrenze** für die Oberfläche (z. B. 10 s, danach Meldung „Dokument zu lang für Vorschläge – Kasten ziehen“).
   Die bestehende `slow`-Meldung warnt nur im Log. Wert beim Bau unter Last einstellen.
4. **Nachlesen und QR** laufen im Umwandler, nicht in Odoo. Vorschlag für feste Grenzen: Nachlesen eines Ausschnitts höchstens
   5 s Wartezeit, danach „läuft im Hintergrund“ mit Bus-Meldung; QR nur Seiten 1–3 und letzte Seite (dort stehen
   Überweisungsträger), höchstens 10 s je Dokument. **Beides nicht gemessen** (Code fehlt); vor dem Bau eine Messreihe an
   der Sammlung (Zeit je Seite, Anteil mit Treffer).

### 3.2 Neuaufbau der Spalten über den Bestand (Messung)

Aufbau: PostgreSQL 16, Knoten-Tabelle mit 1 Mio. Zeilen (15 Spalten, zwei Indizes), Werte-Tabelle mit 2,4 Mio. Zeilen
(300.000 Dokumente × 8 Werte, eindeutiger Index `(node_id, field_id)`), dann 10 Spalten angehängt. **Reines SQL, nicht
Odoos Schreibweg.**

| Vorgang | Dauer | Anmerkung |
|---|---:|---|
| 10 Spalten anhängen | 0,16 s | nur Metadaten |
| **eine** Spalte für 300.000 Dokumente füllen | **59 s** | Tabelle wächst 134 → 178 MB (tote Zeilen) |
| danach `VACUUM` | 24 s | – |
| **8 Spalten** in **einem** `UPDATE` für 300.000 Dokumente | **91 s** | nur ~1,5× statt 8× → **alle Spalten in einem Durchgang** |
| **ein** Dokument speichern (1 Zeile, 2 Spalten) | 0,1 ms | unkritisch |
| 2 Spalten löschen | 3,8 s | – |
| Summe je Datum über echte Spalte (100.000 Treffer) | 148 ms | – |
| dasselbe über die Werte-Tabelle (Selbst-Verknüpfung) | 101 ms | **nicht langsamer** als die echte Spalte |

**Befund:**
- Ein Neuaufbau über 300.000 Dokumente kostet in SQL **anderthalb Minuten** plus Aufräumen. Über Odoos ORM ist es um
  Größenordnungen mehr (Rechteprüfung, Cache je Zeile) – **nicht gemessen**. Der Verwalter-Knopf darf deshalb **kein
  einzelner Aufruf** sein: (a) Stapel von z. B. 1.000 Dokumenten in einem Cron-Lauf (`ir.cron`, Fortschritt sichtbar) oder
  (b) SQL am ORM vorbei (schnell, aber ohne `write_date`, Verlauf, Registry-Pflege). Empfehlung: **(a)** mit ORM für die
  Korrektheit; SQL nur als dokumentierte Reparatur. ORM-Zeit beim Bau messen, Zielwert legt der Nutzer fest.
- **Für Auswertungen bringen echte Spalten keine Zeitersparnis** (Summe/Gruppieren über die Werte-Tabelle war hier sogar
  schneller). Ihr Vorteil ist die **Bedienung mit Odoo-Bordmitteln** (Spalten in der Liste, Filter, Export „eine Zeile je
  Datei“), nicht Tempo. Das stützt Konzept 10.7 (N9) in der Begründung, nicht mit Geschwindigkeit.
  (Grenze der Messung: eine einfache Summe; Pivot über mehrere Felder wurde nicht verglichen.)
- **Tabellenaufblähung:** ein Neuaufbau erzeugt tote Zeilen (+ bis ~50 % Größe bei 30 % betroffener Zeilen); Autovacuum räumt
  nicht sofort auf → nach großen Läufen `VACUUM` einplanen.
- **Spaltenzahl:** 1–3 Spalten je Katalogfeld ergäben bei 18 Startfeldern und eigenen ~30–50 Spalten an einer Tabelle mit
  heute ~15. Bei gezielten `read`-Aufrufen mit Feldliste kein Mehraufwand; **nicht gemessen:** `search_read` ohne Feldliste
  (holt alle Spalten). Beim Bau prüfen, dass Listen mit Feldliste lesen.

### 3.3 Weitere Punkte

- **Registry-Neuladen** je Spalte ≈ 0,1 s (Konzept 10.7); andere Prozesse laden beim nächsten Aufruf neu. Mehrere Felder auf
  einmal anlegen (Feldvorlage) sollte **ein** Neuladen auslösen (ein `create` mit mehreren Zeilen).
- **Neuaufbau gegen laufende Bestätigungen:** je Dokument dieselbe Knotensperre nehmen (Muster
  `_lock_and_check_base_revision`) oder nur Dokumente schreiben, deren `write_date` sich seit dem Start nicht änderte.

## 4. Zusammenfassung: Vorschlag, Beleg, Restrisiko

| Unterpunkt | Vorschlag | Beleg | Restrisiko |
|---|---|---|---|
| 1.1 Herkunft/Prüfstatus | `source`: rule/manual/area/qr; Prüfstatus am Knoten mit Fassungsbezug; leer bis „in Prüfung“ | Code gelesen | Frage 1 offen |
| 1.2 Kästen, Absender-Schalter | `extraction_area` (relative Lage, Anker), `extraction_sender`; Verwalter-Rechte | Code gelesen (Muster `extraction_hint`) | Überdeckungs-Schwelle; Anker erst mit echten Dokumenten prüfbar |
| 1.3 Spalten je Wertart | Tabelle oben, Namen `x_fm_<id>` | Quellcode `ir_model.py` | Zeitraum/Dauer und Mengen-Einheit (Frage 2); `groups` als „Ausblenden“ nicht ausprobiert |
| 1.4 Umbenennen | Spalte hängt an `id`; Einheit sperren | Code gelesen | Einheit-Sperre ändert bestehendes Verhalten (Frage 3) |
| 1.5 Schreibschutz | Ablehnung in `write`/`create` bei `not env.su`, `copy=False` | Zugriffsliste + Regeln gelesen | nicht nachgestellt; `env.su` aus Odoo-Wissen |
| 2 Rechte | Tabelle oben, Prüfung in der Methode | Muster W-5 | Form der Nachricht „Feld vorschlagen“ offen |
| 3.1 Vorschlagen | linear; Ausschnitt im Kasten; Zeitgrenze | **Messung** (synthetisch) | echte Dokumente (viele Tabellen) können anders liegen; Ausschnitts-Effekt ungemessen |
| 3.2 Neuaufbau | Cron-Stapel, alle Spalten in einem Durchgang | **Messung** (SQL) | ORM-Zeit unbekannt |

## 5. Fragen an den Nutzer

1. **Was zählt als „ungeprüft“?** Alle Dateien mit erkanntem Text – oder nur, was ausdrücklich in die Prüfung kommt
   (Eingangsordner, Knopf „zur Prüfung vormerken“)? Empfehlung: nur Letzteres (1.1).
2. **Dauer und Mengen-Einheit in der Spalte:** Dauern in Wochen nicht spiegeln (Umrechnung in Monate ungenau), Mengen mit
   abweichender Einheit nicht spiegeln und im Prüf-Fenster darauf hinweisen? Empfehlung: ja (1.3).
3. **Einheit eines Mengenfelds sperren**, sobald Werte da sind, wie die Wertart? Heute änderbar. Empfehlung: ja (1.4).
