# int_filemanager v2 – Aufgabenliste für den Dauerlauf (Entwurf, wartet auf Freigabe)

Stand 2026-09-30, Liste vom Nutzer freigegeben (Probelauf mit A8). Zweck: Claude arbeitet unbeaufsichtigt, bis die Nutzungsgrenzen
erreicht sind, pausiert dann bis zum Reset und macht danach weiter. **Mechanik:** geplante Aufgabe (scheduled task `v2-dauerlauf`);
jeder Lauf ist eine frische Sitzung ohne Vorwissen, liest diese Liste, arbeitet und setzt am Ende den nächsten Termin
(`update_scheduled_task` mit `fireAt`). Läuft nur, solange die App offen und der Rechner wach ist. Diese Liste ist der **einzige Ort für den Fortschritt** (nicht der Chat-Verlauf): nach jeder
Aufgabe Kästchen setzen, Ergebnis kurz eintragen, committen.

## Spielregeln

**Nur ohne offene Entscheidung.** Das Prüf-Fenster-Konzept hat **keine Freigabe**. Es wird nichts gebaut, das dazugehört
(keine Modelle, keine Oberfläche, keine Änderung an Konzept-Text). Ergebnisse stehen in **neuen Entwurfs-Dokumenten**
(`docs/…_entwurf_….md`); der Nutzer entscheidet danach, was ins Konzept übernommen wird.

**Erlaubt:** Lesen (Repo, Odoo-Quellcode im Image `odoo:19.0-hm-test`), Entwurfs-Dokumente schreiben, Tests **nur
ergänzen** (nie bestehende abschwächen), Testläufe auf Tower in eigenen Wegwerf-Containern/-Datenbanken mit Präfix
`dl_` (danach wieder entfernen), Commit + Push auf Branch `feature/int-filemanager-v2`.

**Nicht erlaubt:** Änderungen am Produktivcode von `int_filemanager` (außer der Nutzer gibt es je Aufgabe frei),
Live-Instanzen (HM-SRV, Container `odoo`/`odoo_db` auf Tower), Löschen von Bestehendem (Testcontainer `fmtest_*`,
`fmv2_*`, Freigabe `fmv2blobs`, Sammlung unter `/mnt/user/test/…`), Push auf `master`, private Testdaten ins Repo oder in
Berichte, Zugangsdaten irgendwo speichern. Bei Unklarheit: Aufgabe überspringen und Frage unten unter „Fragen an den Nutzer“
eintragen, nicht raten.

**Grenzen (vor jedem Schritt mit `get_usage` prüfen):**
- 5-Stunden-Fenster ≥ **85 %** → laufenden Schritt beenden, committen, Stand eintragen, Wecker auf `resetsAt` des Fensters.
- Wochenlimit ≥ **85 %** (Nutzerentscheidung 2026-09-30) → wie oben, Wecker auf `resetsAt` des Wochenlimits.
- Jeder Lauf beginnt frisch und erledigt **höchstens ein Aufgaben-Paket** (eine Aufgabe, bei kleinen zwei); Kontext ≥ **50 %** →
  Stand eintragen und den Lauf beenden, der nächste Termin führt weiter.
- Große Läufe (`v2check.sh`, volle Suite) nur, wenn danach noch mindestens 10 Prozentpunkte Luft bleiben.

**Prüfen/Committen:** Skill `pruefen-und-committen`. Volle Suite und `v2check` nur einmal vor dem letzten Commit einer
Aufgabenrunde, sonst gezielte Tests.

## Aufgaben

Reihenfolge = Priorität. Kästchen `[ ]` offen, `[x]` fertig (mit Commit-Hash und einem Satz Ergebnis).

- [ ] **A1 Rennszenarien nachlaufen lassen.** `tools/v2check/race.sh` ist seit W-1 nicht mehr gelaufen. Zwei-Worker-Instanz
  auf Tower aufsetzen (Präfix `dl_`), Szenarien laufen lassen, Ergebnis in Übergabe 4.0 eintragen, aufräumen.
  Fertig, wenn: alle Szenarien grün oder jede rote Stelle mit Ursache dokumentiert.
- [ ] **A2 Testlücken Schritt 3 klären.** `lock_timeout_triggers_retry` (fehlende „Sperre halten“-Stufe in `tests/tower/fault.py`)
  und `move_against_delete` (`trash()` ohne `fault_point`) sowie A4 (Aufräumjob ohne Auslöser): je Lücke Lösung mit
  Alternativen und Aufwand als Entwurf beschreiben. Nur reinen Testcode (`fault.py`, Treiber) darf Claude ändern; alles, was
  Produktivcode berührt, wird nur vorgeschlagen. Fertig, wenn: Entwurf mit Empfehlung je Lücke liegt.
- [ ] **A3 Konzept Abschnitt 11, Punkte 1–3 als Entwurf** (Datenmodell im Detail, Rechte je neuem Aufruf, Leistung): am Odoo-Code
  und mit Messungen auf Tower an Wegwerf-Daten belegen; Alternativen zeigen; Abdeckung angeben. Ergebnis:
  `docs/int_filemanager_v2_werterkennung_denkpunkte_entwurf_2026-09-30.md`. Fertig, wenn: jeder Unterpunkt Vorschlag, Beleg
  und Restrisiko hat.
- [ ] **A4 Konzept Abschnitt 11, Punkte 4, 5, 7** (Oberflächen-Zustände, Abnahmekriterien je Scheibe U-1…U-10 nach dem Muster
  „fertig, wenn“ von W-1…W-6, Übersetzung): gleicher Entwurfsordner, gleiche Regeln.
- [ ] **A5 Übergang von v1 (Punkt 6).** v1-Modelle (`extracted_value`, Muster) gegen das v2-Schema legen: Mengen und Beispiele
  aus einer Kopie/Wegwerf-DB (nie Live-Daten ändern), Vorschlag „übernehmen / verwerfen / neu erkennen“ je Feld.
- [ ] **A6 Gegenlesen des v2-Codes.** Alle seit Tag `int_filemanager-v1` geänderten Dateien mit `codex -p review exec …`
  und eigener Durchsicht prüfen, jeden Befund selbst am Code verifizieren, Befundliste nach Schwere in
  `docs/review/` ablegen. Nichts ändern. Fertig, wenn: Liste liegt, mit „bestätigt / nicht bestätigt“ je Befund.
- [ ] **A7 Tower-Image und Sicherheitsstand (Befund A5).** Nur Analyse: fehlt `odoo:19.0-hm-test` (19.0-20260908) noch ein
  Sicherheits-Fix aus 19.0? Auswirkungen und Vorschlag für Update-Weg (nicht ausführen).
- [ ] **A8 Doku auf Stand bringen.** `docs/README.md` und Übergabe 4.0 gegen den tatsächlichen Repo-Stand abgleichen
  (Konzept-Commits bis c94cac1, neue Entwurfs-Dokumente), Widersprüche auflisten und beheben, wo es nur Nachtragen ist.
- [ ] **A9 Lebende v2-Dokumente in Unterordner umziehen (nur Umzug, kein Inhalt).** Die im Abschnitt „int_filemanager 2 (lebend)“ von
  `docs/README.md` aufgeführten Dokumente per `git mv` nach `docs/int_filemanager_v2/` verschieben (Dateinamen unverändert; `review/`,
  `prototypes/`, `archiv/`, `erp/`, `sonstiges/` bleiben, wo sie sind; `odoo_konventionen` bleibt in `docs/`). Danach alle Verweise anpassen: `docs/README.md`,
  `CLAUDE.md`, die Dokumente untereinander, Skripte unter `tools/` und Kommentare im Code (`grep -rn` nach jedem alten Dateinamen im ganzen Repo), sowie
  den Pfad in dieser Liste. Prüfen mit einem kleinen Skript, das alle relativen Markdown-Links in `docs/` und `CLAUDE.md` auflöst.
  Nicht anfassen: den Inhalt der Konzepte, den Text der Nutzerentscheidungen. Memory-Dateien außerhalb des Repos meldet der Lauf nur im
  Bericht (der Nutzer bzw. die nächste interaktive Sitzung zieht sie nach). Fertig, wenn: 0 kaputte Links, `git status` zeigt nur Umzüge/Verweis-Änderungen,
  pre-commit grün. Das Aufteilen des Konzepts in Themen-Dateien ist **nicht** Teil dieser Aufgabe (erst nach Freigabe des Prüf-Fenster-Konzepts).

## Ablauf je Lauf

1. `get_usage` lesen; Grenzen oben prüfen (bei Überschreitung sofort den nächsten Termin auf `resetsAt` setzen und beenden).
2. Erste offene Aufgabe wählen, `git pull` auf dem Branch, dann arbeiten.
3. Ergebnis + Commit-Hash hier eintragen, Kästchen setzen, committen und pushen.
4. Grenzen erneut prüfen; passt noch eine Aufgabe, weiter bei 2, sonst nächsten Termin setzen und beenden (kurz nach `resetsAt`, falls
   eine Grenze erreicht ist, sonst in ca. 10 Minuten). Sind alle Aufgaben `[x]`: Skill `sitzung-abschliessen`, Nutzer melden,
   Aufgabe `v2-dauerlauf` deaktivieren, **keinen** neuen Termin setzen.

## Fragen an den Nutzer (Claude trägt hier ein, statt zu raten)

(leer)
