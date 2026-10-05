# Feature Specification: Ablage großer Dateien im Dateimanager (Blob-Ansatz)

**Feature Branch**: `feature/int-filemanager-v2` (Spec-Ordner `003-blob-ansatz`)

**Created**: 2026-10-05

**Status**: Draft, Ansatz und Transport entschieden (Prüfung und Nachprüfung in
`research.md`, Plan in `plan.md`; Ansatz: Datei nach Hash im Filestore, Hash an der
Version, ohne Blob-Tabelle)

**Input**: "Prüfe einen Blob-Ansatz mit Speckit, ohne Rücksicht auf die bisherige
Umsetzung."

## Umfang

Gegenstand ist, **wie Dateiinhalte gespeichert, hochgeladen, ausgeliefert und aufgeräumt
werden**, wenn man bei null beginnt. Maßgeblich sind die verbindlichen Regeln
(`CLAUDE.md`, `docs/odoo_regeln/`), die Odoo-19-Referenz und der Odoo-19-Quellcode in
`docs/odoo/`. **Nicht Gegenstand:** die bisherige Umsetzung (sie dient weder als Vorgabe
noch als Vergleich), Vorschauen und Texterkennung, die Ordnerstruktur, die
Benutzeroberfläche.

**Entscheidungen des Nutzers (2026-10-05):** Dateien bis etwa 5 GB, ein abgebrochener
Upload muss fortsetzbar sein; gleicher Inhalt wird immer nur einmal gespeichert; die
Ablage muss mit Odoo-Bordmitteln gesichert und kopiert werden können (Filestore).

**Entscheidungen des Nutzers (2026-10-06):** Ansatz **Option D'** (Hash an der Version,
keine Blob-Tabelle) und Transport der Teile als **Multipart** über Odoos
`file_upload_service`.

## User Scenarios & Testing _(mandatory)_

### User Story 1 - Eine große Datei hochladen und nach einem Abbruch fortsetzen (Priority: P1)

Wer eine Datei von mehreren Gigabyte hochlädt, verliert bei einem Verbindungsabbruch
nicht alles: Der Upload macht dort weiter, wo er aufgehört hat. Der Server hält die
Datei nie vollständig im Arbeitsspeicher.

**Why this priority**: Das ist der Grund, warum Odoos Standardweg (Anhang als Bytes im
Speicher, 128 MB je Anfrage) nicht reicht.

**Independent Test**: Eine 3-GB-Testdatei wird in Teilen hochgeladen, die Verbindung
nach der Hälfte gekappt, der Upload fortgesetzt; am Ende stimmt der SHA-256 der
abgelegten Datei mit dem der Quelle überein, und der Arbeitsspeicher des Workers bleibt
unter dem Limit.

**Acceptance Scenarios**:

1. **Given** ein Upload mit 40 % übertragenen Daten, **When** der Client nach einem
   Abbruch den Stand abfragt und ab dort sendet, **Then** wird die Datei vollständig und
   unverändert abgelegt.
2. **Given** ein Teil, der schon angekommen ist, **When** er erneut gesendet wird,
   **Then** wird er ignoriert und nichts doppelt geschrieben.
3. **Given** ein Teil, der eine Lücke ließe, **When** er gesendet wird, **Then** wird er
   abgelehnt.
4. **Given** ein Teil, der mitten im Körper abgebrochen ist (oder ein Absturz zwischen
   Schreiben und Merken des Standes), **When** der Client ab dem bestätigten Stand neu
   sendet, **Then** enthält die Datei keine Reste des abgebrochenen Teils.
5. **Given** ein Upload, dessen Gesamtgröße nicht der angekündigten entspricht, **When**
   er abgeschlossen werden soll, **Then** wird er abgelehnt und nichts abgelegt.
6. **Given** eine große Datei, **When** der Client den Abschluss anstößt, **Then** läuft
   er im Hintergrund, der Client sieht den Fortgang und das Ergebnis, und das Zeitlimit
   des Proxys spielt keine Rolle.

---

### User Story 2 - Gleicher Inhalt liegt nur einmal auf der Platte (Priority: P1)

Dieselbe Datei an mehreren Stellen, mehrere Versionen mit gleichem Inhalt und kopierte
Ordner kosten keinen zusätzlichen Speicherplatz, auch wenn sie gleichzeitig hochgeladen
werden.

**Why this priority**: Entscheidung des Nutzers; bestimmt die Struktur der Ablage.

**Independent Test**: Zehn gleichzeitige Uploads desselben neuen Inhalts unter
verschiedenen Namen ergeben zehn Einträge, aber genau eine Datei auf der Platte, und
kein Upload scheitert.

**Acceptance Scenarios**:

1. **Given** zwei Uploads mit identischem Inhalt, **When** beide fertig sind, **Then**
   gibt es eine Datei auf der Platte und zwei Verweise.
2. **Given** zwei gleichzeitige Uploads desselben neuen Inhalts, **When** beide
   abschließen, **Then** gelingen beide und verweisen auf dieselbe Datei.

---

### User Story 3 - Sicherung und Kopie einer Datenbank enthalten die Dateien (Priority: P2)

Wer eine Odoo-Datenbank sichert, wiederherstellt oder dupliziert, bekommt die
Dateiinhalte mit, ohne ein eigenes Verfahren.

**Why this priority**: Entscheidung des Nutzers.

**Independent Test**: Eine Datenbank mit Dateien wird über Odoos Sicherung gesichert und
in eine neue Datenbank wiederhergestellt; alle Dateien sind lesbar und stimmen im Hash
überein.

**Acceptance Scenarios**:

1. **Given** eine Datenbank mit Dateien, **When** sie dupliziert wird, **Then** sind die
   Dateien in der Kopie vorhanden.

---

### User Story 4 - Auslieferung mit Rechten, Teilabruf und Zwischenspeicher (Priority: P2)

Wer eine Datei herunterlädt, bekommt sie nur mit dem Recht an dem Datensatz, zu dem sie
gehört. Große Dateien werden gestreamt (nicht geladen), Teilabrufe (Videos) und bedingte
Abrufe (ETag) funktionieren, und hinter nginx kann der Server die Auslieferung
übergeben.

**Why this priority**: Ohne sie ist die Ablage nicht benutzbar; Rechte sind die
Sicherheitsgrundlage.

**Independent Test**: Ein Nutzer ohne Recht bekommt 403/404; mit Recht bekommt er einen
Teilabruf (`Range`) korrekt beantwortet; ein zweiter Abruf mit `If-None-Match`
liefert 304.

**Acceptance Scenarios**:

1. **Given** ein Nutzer ohne Leserecht am Datensatz, **When** er die Datei abruft,
   **Then** wird der Zugriff verweigert.
2. **Given** eine Datei von 2 GB, **When** ein Teilabruf angefragt wird, **Then**
   liefert der Server nur diesen Bereich, ohne die Datei zu laden.

---

### User Story 5 - Nicht mehr gebrauchte Dateien verschwinden, ohne laufende Vorgänge zu stören (Priority: P3)

Wird die letzte Version gelöscht, die auf einen Inhalt zeigt, gibt ein Aufräum-Lauf den
Platz nach einer Schonfrist wieder frei; die Frist beginnt mit dem Löschen der letzten
Version (Markierung), nicht beim letzten Hochladen. Ein Vorgang, der den Inhalt gerade
verwendet (Upload, Kopieren, Wiederherstellen), verliert ihn nicht.

**Why this priority**: Sonst wächst die Ablage unbegrenzt; Fehler hier verlieren Daten.

**Independent Test**: Eine Datei ohne Verweis bleibt innerhalb der Schonfrist, danach
wird sie entfernt; eine Datei mit Verweis wird nie entfernt; ein Upload, der während des
Laufs abschließt, behält seine Datei.

**Acceptance Scenarios**:

1. **Given** eine Datei, auf die keine Version mehr verweist und deren Markierung älter
   als die Schonfrist ist, **When** der Aufräum-Lauf läuft, **Then** wird sie entfernt.
2. **Given** eine Datei, die ein laufender Vorgang gerade ablegt, **When** der Lauf
   startet, **Then** bleibt sie erhalten (an jedem Punkt des Ablegens).
3. **Given** ein Inhalt, dessen letzte Version eben gelöscht wurde, **When** der Lauf
   läuft, **Then** bleibt der Inhalt erhalten und wird erst nach der Schonfrist
   entfernt.
4. **Given** eine Version, die von einem Inhalt kopiert oder wiederhergestellt wird,
   **When** der Lauf gleichzeitig läuft, **Then** gelingt das Kopieren oder wird sauber
   abgelehnt, und die Datei bleibt erhalten.

---

### Edge Cases

- Der Server stürzt mitten im Upload oder zwischen Ablegen der Datei und Eintragen des
  Verweises ab: nichts Sichtbares bleibt zurück, übrig gebliebene Dateien räumt der Lauf
  auf.
- Zwei Vorgänge legen gleichzeitig denselben neuen Inhalt ab.
- Der Aufräum-Lauf trifft eine Datei, die ein anderer Vorgang eben verwendet.
- Das Dateisystem ist voll, oder die Zwischendatei liegt auf einem anderen Dateisystem
  als die Ablage.
- Der Client sendet einen falschen Hash oder einen Teil mit falschem Versatz.
- Die Datei ist größer als das erlaubte Maximum, oder ein Teil ist größer als das Limit
  der Anfrage.
- Eine Datei hat 2 GiB oder mehr (die Größenangabe in der Datenbank darf nicht
  überlaufen).
- Ein Wert, der als Hash ausgegeben wird, ist manipuliert und enthält Zeichen, die in
  einem Pfad nichts verloren haben.
- Ein Upload bleibt liegen und wird nie abgeschlossen.
- Ein Teil bricht mitten im Körper ab, oder der Server stürzt zwischen Schreiben und
  Merken des Standes ab.
- Der Abschluss einer großen Datei dauert länger als das Zeitlimit des Proxys (kalte
  Platte).
- Eine spätere Tabelle (Vorschau, Freigabe) braucht einen Inhalt: Sie verweist auf die
  Version und trägt keinen eigenen Hash, sonst wäre der Inhalt für den Aufräum-Lauf
  unsichtbar.
- Ein Aufräum-Lauf trifft einen Inhalt, dessen Version gleichzeitig kopiert oder
  wiederhergestellt wird.
- Ein Modell außer der Version bekommt eine Hash-Spalte (der Lauf sähe sie nicht).

## Requirements _(mandatory)_

### Functional Requirements

**Ablage**

- **FR-001**: Dateiinhalte MÜSSEN unterhalb des Odoo-Filestores liegen
  (`config.filestore(<db>)`), damit Sichern, Wiederherstellen und Duplizieren sie
  einschließen.
- **FR-002**: Jeder Inhalt MUSS unter seinem SHA-256 abgelegt werden; gleicher Inhalt
  MUSS genau eine Datei auf der Platte ergeben, auch bei gleichzeitigem Ablegen. Hash
  und Größe stehen an dem Datensatz, der auf den Inhalt verweist; es gibt keine
  gemeinsame Zeile je Inhalt.
- **FR-003**: Das Anlegen einer Datei an ihrem Endnamen MUSS atomar sein: der Endname
  existiert ganz oder gar nicht. Ein vorhandener Endname MUSS unangetastet bleiben (kein
  Ersetzen, auch nicht durch gleichen Inhalt), damit ein gleichzeitiger Leser nie einen
  fehlenden Namen sieht. Legen zwei Vorgänge gleichzeitig denselben Inhalt ab, gewinnt
  der erste.
- **FR-004**: Dateigrößen bis mindestens 5 GB MÜSSEN darstellbar sein; die Größenangabe
  darf bei 2 GiB nicht überlaufen.
- **FR-005**: Pfade MÜSSEN ausschließlich aus einem geprüften Hash (64 Hexzeichen)
  gebildet werden; jeder andere Wert MUSS abgelehnt werden.

**Upload**

- **FR-006**: Ein Upload MUSS in Teilen möglich und nach einem Abbruch ab dem zuletzt
  bestätigten Stand fortsetzbar sein; der Server MUSS die Datei nie vollständig im
  Arbeitsspeicher halten.
- **FR-007**: Ein bereits empfangener Teil MUSS ignoriert, ein Teil mit Lücke abgelehnt
  werden; zwei Teile desselben Uploads dürfen sich nicht überlagern. Ein abgebrochener
  Teil DARF keine Reste in der Zwischendatei hinterlassen (vor dem Anhängen wird auf den
  bestätigten Stand abgeschnitten).
- **FR-008**: Teilgröße und Gesamtgröße MÜSSEN begrenzt sein (Systemparameter); der
  Server MUSS Versatz und Größen als unvertrauenswürdige Eingabe prüfen.
- **FR-009**: Beim Abschluss MUSS der Server die Gesamtgröße gegen die angekündigte
  prüfen, den SHA-256 selbst berechnen und, wenn der Client einen erwartet, auf
  Übereinstimmung prüfen.
- **FR-010**: Ein Vorgang MUSS wiederholbar sein: ein wiederholter Teil, Abschluss oder
  Statusabruf wirkt genau einmal bzw. liefert denselben Stand (über den Status des
  Uploads, ohne eigenen Schlüssel).

**Auslieferung und Rechte**

- **FR-011**: Der Zugriff auf einen Inhalt MUSS an das Recht auf den Datensatz gebunden
  sein, der darauf verweist; Nutzer haben keinen unmittelbaren Zugriff auf Dateien oder
  Hashes.
- **FR-012**: Die Auslieferung MUSS streamen, `Range` und `ETag` unterstützen und die
  Übergabe an nginx erlauben (Pfad unterhalb des Filestores).

**Aufräumen**

- **FR-013**: Ein Inhalt, auf den keine Version mehr verweist, MUSS nach einer
  Schonfrist entfernt werden, unabhängig davon, auf welchem Weg die Version gelöscht
  wurde (auch durch Löschen des Ordners). Jeder Löschweg MUSS den Inhalt vor dem Löschen
  markieren; die Schonfrist zählt ab der Markierung. Nur die Version trägt einen Hash,
  der Aufräum-Lauf fragt diese Tabelle ab; spätere Tabellen mit Inhaltsbezug verweisen
  auf die Version, und ein Test MUSS jedes andere Modell mit einer Hash-Spalte
  aufdecken. Die Schonfrist MUSS gegen Werte unter einer Mindestdauer geschützt sein.
- **FR-014**: Der Aufräum-Lauf MUSS gleichzeitige Vorgänge schützen (Upload, Kopieren,
  Wiederherstellen): eine Datei, deren Ablage noch nicht abgeschlossen ist oder auf die
  gerade eine Version verweist, darf nicht verloren gehen. Eine einzelne Datei, die sich
  nicht löschen lässt, DARF den Lauf nicht abbrechen oder endlos wiederholen lassen.
- **FR-015**: Übrig gebliebene Zwischendateien und abgebrochene Uploads MÜSSEN nach
  einer Frist aufgeräumt werden.

**Betrieb**

- **FR-018**: Der Abschluss eines Uploads (Größenprüfung, Hash, Ablegen, Version
  anlegen) MUSS im Hintergrund laufen können, ohne Abhängigkeit vom Zeitlimit des
  Proxys; der Nutzer MUSS den Fortgang und das Ergebnis erfahren.
- **FR-019**: Der Ablageort MUSS über Odoos Einstellungen (`--data-dir` oder ein Volume
  für den Unterordner) auf einen großen Datenträger legbar sein, ohne dass Zwischendatei
  und Ablage das Dateisystem wechseln. Für große Bestände MUSS eine Sicherung aus
  Datenbank-`dump` und Dateiabgleich des Ordners möglich und beschrieben sein.
- **FR-020**: Das Senden eines Teils MUSS durch Odoos CSRF-Schutz und eine Zeilenregel
  auf den Eigentümer des Uploads geschützt sein. Die Auslieferung großer Dateien SOLL
  über `--x-sendfile` an nginx übergeben werden können.

**Qualität**

- **FR-016**: Die Umsetzung MUSS die Regeln in `docs/odoo_regeln/` einhalten und jede
  Abweichung im Plan begründen (Complexity Tracking).
- **FR-017**: Jede Fehlerbehebung MUSS einen Test haben, der ohne sie fehlschlägt;
  Gleichzeitigkeit und Absturz MÜSSEN mit echten Prozessen getestet werden, nicht nur
  simuliert.

### Key Entities

- **Inhalt**: eine Datei auf der Platte, benannt nach ihrem SHA-256; keine eigene Zeile
  in der Datenbank und keine Rechte.
- **Verweis**: ein Datensatz (z. B. eine Version), der Hash und Größe eines Inhalts
  trägt und die Rechte hat; es ist die einzige Tabelle mit Hash.
- **Upload**: ein laufender, fortsetzbarer Hochladevorgang mit Zwischendatei,
  angekündigter Größe, Stand und Eigentümer (der Anleger).
- **Merkzettel**: Vermerk je Datei, die beim Ablegen oder Löschen einer Version markiert
  wurde, mit Zeitstempel; nach der Schonfrist entscheidet der Aufräum-Lauf, ob die Datei
  noch gebraucht wird.

## Success Criteria _(mandatory)_

### Measurable Outcomes

- **SC-001**: Eine 3-GB-Datei lässt sich nach Abbruch fortsetzen; der SHA-256 stimmt mit
  der Quelle überein; die Speichernutzung des Workers wächst um weniger als 512 MB.
- **SC-002**: Zehn gleichzeitige Uploads desselben neuen Inhalts: 0 Fehler, genau 1
  Datei auf der Platte.
- **SC-003**: Sicherung und Wiederherstellung einer Datenbank mit 100 Dateien (Zip,
  sowie `dump` plus Dateiabgleich des Ordners): 100 von 100 Dateien lesbar, Hashes
  gleich.
- **SC-004**: Ein Absturz an jedem festgelegten Punkt (vor dem Ablegen, nach dem
  Ablegen, vor dem Eintragen, vor dem Commit) hinterlässt nichts Sichtbares und
  höchstens aufräumbare Reste.
- **SC-005**: Ein Teilabruf einer 2-GB-Datei wird beantwortet, ohne dass der Worker mehr
  als 50 MB zusätzlich belegt.
- **SC-006**: Nach der Schonfrist ist der Platz einer unreferenzierten Datei frei;
  referenzierte Dateien sind in 100 % der Läufe erhalten.
- **SC-007**: Kein Pfad entsteht aus einem Wert, der kein gültiger Hash ist (Test mit
  manipulierten Werten).
- **SC-008**: Der Abschluss einer 3-GB-Datei nach Kaltlesung (Seitencache geleert)
  gelingt, ohne dass die Anfrage des Clients länger als wenige Sekunden dauert; der
  Client sieht das Ergebnis.
- **SC-009**: Aufräum-Lauf gegen gleichzeitiges Hochladen, Kopieren und Wiederherstellen
  (echte Prozesse, jede Reihenfolge an jedem Punkt): 0 verlorene Dateien, 0 Läufe, die
  endlos wiederholen.

## Assumptions

- Zwischenablage und Ablage liegen im selben Dateisystem (Hardlink ohne Kopieren); sonst
  fällt der Abschluss auf `shutil.move` mit anschließendem Umbenennen zurück (im Plan
  beschrieben).
- Das Maximum (5 GB) und die Schonfrist (Standard 24 Stunden, Mindestdauer 1 Stunde)
  sind Systemparameter.
- Der Reverse-Proxy (nginx) lässt Teile der gewählten Größe und die nötige Zeit zu. Auf
  dem Tower geprüft: `client_max_body_size` 2000m, Zeitlimit 90 s; HM-SRV ist nicht
  geprüft.
- Der Abschluss einer 5-GB-Datei (Hashen, Ablegen) dauert auf dem Tower warm rund 25 s;
  eine Kaltlesung ist nicht gemessen und kann länger als das Proxy-Zeitlimit von 90 s
  dauern. Deshalb läuft der Abschluss im Hintergrund (Cron mit `_trigger`). Das
  Zeitlimit des Crons (`limit_time_real_cron`, folgt `limit_time_real`, Standard 120 s,
  Tower 1800 s) gilt weiter und muss für den echten Bestand über der Kaltlesezeit der
  größten Datei liegen; auf HM-SRV ist es nicht geprüft.
- Der Filestore liegt auf dem Tower derzeit auf der Cache-SSD (92 GB frei, nicht für
  Terabyte geeignet). Der Ordner `int_filemanager` muss für den echten Bestand auf den
  Array-Share verlegt werden; Odoos Zip-Sicherung (kopiert den Filestore ganz in einen
  Temp-Ordner und zippt ihn) ist dafür nur für kleine Bestände geeignet.
- Ein Teil beträgt standardmäßig 8 MiB und bleibt weit unter dem Anfragelimit (Standard
  128 MiB).
- Ein Hash-Kollisionsfall bei SHA-256 gilt als ausgeschlossen.
- Die Transportart der Teile ist im Plan entschieden: HTTP-Route je Teil als Multipart
  über Odoos `file_upload_service` (auf dem Tower gemessen, vom Nutzer am 2026-10-06
  bestätigt).
