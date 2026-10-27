# Prompt: Review von int_filemanager gegen Odoo 19 (zweite Runde)

Den Text unter dem Strich in eine neue Sitzung im Ordner `int-odoo-addons` kopieren.

---

Du prüfst die Module `int_filemanager`, `int_filemanager_share`, `int_filemanager_ocr`, `int_filemanager_image_editor`, `int_filemanager_import`, `int_filemanager_record` und `int_filemanager_record_ocr` streng nach Odoo 19. Du **änderst nichts**, du liest, prüfst und berichtest.

## 1. Maßstab und Reihenfolge

Es gilt die Reihenfolge aus `CLAUDE.md`. Zusammenfassungen und Regeldestillate sind keine Quelle.

1. Die passende Seite der offiziellen Doku in `docs/odoo19_reference/` (Backend: `backend/`, Frontend: `frontend/`) und `docs/owl2_reference/` lesen.
2. Das tatsächliche Verhalten im Odoo-Code unter `docs/odoo/` prüfen und mit einem vergleichbaren Kernmodul belegen (zum Beispiel `project`, `hr`, `account`, `mail`, `product`, `stock`, `portal`, `website`, `web`).
3. Bei Widerspruch oder Unklarheit einen kleinen reproduzierbaren Test beschreiben oder ausführen. Bestätigte Abweichungen zwischen Doku und Core gehören nach `docs/odoo19_abweichungen.md`.

Ein Befund gilt nur, wenn du drei Dinge nennst: die Stelle im Repo (`Datei:Zeile`), die Stelle in Doku oder Core, und was ein Odoo-Kernmodul an dieser Stelle anders oder gleich macht. Was du nicht belegen kannst, kennzeichnest du als **Vermutung**.

## 2. Vorarbeit lesen, nichts wiederholen

Lies zuerst: `docs/int_filemanager/umsetzung_review.md` (die 20 Punkte der ersten Runde, alle umgesetzt), `docs/int_filemanager/erkenntnisse.md` (Messungen, Odoo-Eigenheiten, Entscheidungen, Invarianten), `docs/int_filemanager/modulaufteilung.md` und die Konzeptdokumente der Erweiterungsmodule in `docs/int_filemanager_*/`.

- Schlage nichts vor, was dort schon umgesetzt oder bewusst verworfen ist. Willst du eine Entscheidung trotzdem in Frage stellen, nenne den Grund aus `erkenntnisse.md` und sage, was dagegen spricht.
- Die vier Invarianten und der Satz "Kein Schlüssel im Kontext nimmt einem Nutzer eine Prüfung ab" gelten. Ein Vorschlag darf sie nicht aufweichen.
- Offene Punkte aus Abschnitt 7 von `erkenntnisse.md` zählen nur, wenn du eine neue Begründung oder einen konkreten Entwurf hast.

## 3. Prüfbereiche

Gehe jeden Bereich durch und lass keinen aus, auch wenn du dort nichts findest (dann schreibe "geprüft, kein Befund").

1. **Modell und ORM:** Felddefinitionen, Indizes (`index=`, `UniqueIndex`, Trigram), Compute/Depends/Store, `_read_group`, Constraints, `ondelete`, `create`/`write`/`unlink`, Mixins, `mail.thread`-Einstellungen (`_mail_post_access`, Tracking).
2. **Sicherheit:** Gruppen, ACL, Record Rules, `sudo()`, Kontext-Schlüssel, öffentliche Routen, CSRF, Rate-Limits, Pfad- und Dateinamen, Mimetype und Auslieferung (Content-Disposition, nosniff), Gastzugriff.
3. **Controller und HTTP:** Routen, `auth`, `methods`, Streaming, Fehlerantworten, Firmenkontext, Größenlimits.
4. **Hintergrundjobs:** `ir.cron`, `@api.autovacuum`, Batches, Zeitbudget, Locking, Wiederanlauf, Verhalten bei Fehlern.
5. **Datei- und Datenhaltung:** Blob-Ablage, Garbage Collector, Deinstallation, Backup und Wiederherstellung, Verhalten mit mehreren Workern.
6. **Views und Daten (XML):** Listen, Kanban, Formulare, Suche, Suchpanel, Aktionen, Menüs, Einstellungen, Demo-Daten, Manifest, `noupdate`.
7. **Frontend (Owl, JS):** Patches und Erweiterungen gegen die Muster der Doku, Registries, Services, Hooks, Speicherlecks, Fehlerbehandlung, Hoot-Tests.
8. **Oberfläche und Bedienung:** Arbeitsabläufe aus Sicht der Nutzerrollen (Leser, Nutzer, Administrator, Gast), Mobil (`isSmall`, Touch), Tastatur, Barrierefreiheit (Rollen, Labels, Fokus), Dunkelmodus und RTL, Leerzustände, Fehlermeldungen, Texte.
9. **Übersetzung:** `.pot`/`.po`, `_t`/`env._`, Platzhalter statt Verkettung, Pluralformen.
10. **Tests:** Abdeckung nach Risiko (nicht nach Zeilen), fehlende Tours, Hoot, Lasttests, Flakiness.
11. **Leistung und Skalierung:** Abfragepläne der Record Rules, Indizes, große Bäume, 100.000+ Dokumente, Speicher beim Streamen.
12. **Betrieb und Wartung:** Einstellungen, Statusanzeigen, Protokolle, Dokumentation, Upgrade-Pfad, Abhängigkeit von privaten Odoo-APIs.
13. **Fachliche Lücken:** Was ein Dateimanager im Odoo-Umfeld üblicherweise bietet und hier fehlt (im Vergleich zu dem, was Odoo-Module und Anwender erwarten, nicht zu Fremdprodukten).

Bereiche, an die du selbst zusätzlich denkst und die hier nicht stehen, gehören dazu.

## 4. Ausgabe

Liefere **genau 20 Vorschläge**, absteigend nach Nutzen im Verhältnis zum Aufwand, über alle Bereiche verteilt (nicht mehr als drei im selben Bereich). Jeder Vorschlag hat dieselben Felder:

| Feld | Inhalt |
|---|---|
| Titel | ein Satz, was sich ändert |
| Bereich | aus Abschnitt 3 |
| Befund | was der Code heute tut, mit `Datei:Zeile` |
| Odoo-Beleg | Doku-Seite und Core-Datei samt Zeile, dazu das vergleichbare Kernmodul |
| Wirkung | wer es merkt: Nutzer, Administrator, Betrieb, Entwickler; messbar, wo möglich |
| Vorschlag | konkrete Änderung, welche Dateien, welcher Odoo-Mechanismus |
| Aufwand / Risiko | klein, mittel, groß; was kaputtgehen kann, welche Tests nötig sind |
| Sicherheit des Befunds | belegt oder Vermutung |

Schließe mit drei Listen: was du geprüft hast und für in Ordnung hältst, was du nicht prüfen konntest (zum Beispiel ohne Browser oder Testserver) und was du aus der Vorarbeit bewusst nicht wiederholt hast.

## 5. Regeln

- Nur lesen. Keine Dateien im Repo ändern, außer wenn ich dich danach bitte.
- Antworte auf Deutsch, Code und Bezeichner bleiben englisch.
- Keine neuen Regeln für das Repository erfinden (`CLAUDE.md`: dieses Repository definiert keine zusätzlichen Odoo-Coding-, Review- oder Prozessregeln).
- Zahlen (Zeilen, Anzahl, Zeiten) nur nennen, wenn du sie gemessen oder nachgezählt hast.
- Kein Vorschlag ohne Gegenprobe: Suche vor dem Aufschreiben noch einmal im Code, ob die Stelle nicht schon in einem anderen Modul oder Test gelöst ist.
