# Prototypen Werterkennung (2026-09-29)

Wegwerf-Skripte aus der Planung, **kein Modulcode**; Vorlage für W-3/W-4 und W-6
(Plan im Git-Tag `docs-vor-aufraeumen-2026-10-02`, Entscheidungen in `docs/int_filemanager_v2_entscheidungen.md`). Enthalten keine Dokumente oder persönlichen Daten.

| Datei | Zweck | Aufruf (Tower, Wegwerf-Container ohne Netz) |
|---|---|---|
| `keyword_search.py` | Stichwort-Modus: Katalog aus 18 Feldern, Suche **A** im Text (Wert in den nächsten 6 Wörtern) und **B** nach Seitenlage (rechts daneben / darunter, Spaltengrenze = großer Wortabstand), Wertarten Nummer (auch in Leerzeichen-Gruppen), Datum, Betrag (Einheit davor oder dahinter), ct/kWh, kWh, Zeitraum, Dauer; Prüfziffern USt-IdNr./Gläubiger-ID. Liest noch das **alte** Wortlisten-Format v1 (Wörter als Objekte) – für v2 anpassen | `docker run --rm --network none --entrypoint python3 -e PYTHONPATH=/usr/lib/python3/dist-packages -v <dir>:/data odoo:19.0-hm-test /data/keyword_search.py /data/<wortliste>.json` |
| `classify.py` | teilt PDFs in digital / Scan mit Scanner-Text / Scan ohne Text (Bildanteil je Seite) | `docker run --rm --user 0 --network none -v /mnt/user/test/werterkennung:/docs:ro -v <out>:/out fmconverter:dev python /out/classify.py /docs` |
| `ocrcompare.py` | Scanner-Text gegen `--redo-ocr` gegen `--force-ocr` (Anteil sauberer Wörter) | wie oben, braucht `classes.tsv` aus `classify.py` |
| `runall.py` | Wortliste über die ganze Sammlung, Kennzahlen + `index.json`, Wortlisten als `NNNN.json` (liegt auf Tower unter `<out>/_tools/`) | `docker run -d -u 0 --network none -w /app -e PYTHONPATH=/app -e CONVERTER_OCR_TOOL_TIMEOUT_S=900 -v /mnt/user/test/werterkennung:/docs:ro -v <out>:/out fmconverter:dev sh -c "python /out/_tools/runall.py > /out/run.log 2>&1"` – **ohne** `CONVERTER_OCR_TOOL_TIMEOUT_S` gilt beim direkten Aufruf (ohne `server.py`) das kurze Werkzeuglimit von 25 s, große Scans scheitern dann |

## W-6: Messung an der Sammlung (ab 2026-09-29)

Private Daten (Stichprobe mit erkannten Werten, Ergebnisse je Runde) liegen **nur** auf Tower unter
`/mnt/user/test/werterkennung_w6/` (`chmod 700`): `w6_sample.json` (Aufteilung nach Absendern, 40 Dokumente, Vorschläge),
`runde<N>.json` (Bewertung des Nutzers), `korrekturen.json` (Antworten, die ein anderes Feld meinten, für `w6_recheck.py` richtiggestellt; die Runden-Dateien bleiben unverändert). Nie ins Repo, nicht in Berichte mit Werten.

| Datei | Zweck | Aufruf |
|---|---|---|
| `w6_sample.py` | Absender je Dokument (USt-IdNr. → IBAN, außer IBANs in ≥ 20 Dokumenten = eigene Konten → Mail-Domain → Ordner), Aufteilung der Absender 60/40 in Übungs-/Prüfteil (fester Zufallswert), Stichprobe 24 + 16 Dokumente mit ≥ 2 Feldern, je Absender höchstens eins, und deren Vorschläge. **Ist `w6_sample.json` schon da, bleiben Stichprobe und Aufteilung fest**, nur die Vorschläge werden neu berechnet (nach jeder Regeländerung) | `/tmp/w6` mit `fm/__init__.py`, `fm/value_types.py`, `fm/value_suggest.py`, `int_filemanager_extraction_field.xml` und diesem Skript anlegen, dann `docker run --rm -u 0 --network none -w / -v /tmp/w6:/m:ro -v /mnt/user/test/werterkennung_words_v3:/w:ro -v /mnt/user/test/werterkennung_w6:/out --entrypoint python3 odoo:19.0-hm-test /m/w6_sample.py` |
| `w6_review.py` | lokale Abhak-Seite je Runde (nicht veröffentlichen): links das Original von `G:\Meine Ablage\Privat`, rechts je Feld ✓ / ✗ (mit richtigem Wert oder Alternative) / „steht nicht drin“, fehlende Werte nachtragen, Fortschritt im Browser, „Ergebnis speichern“ lädt `werterkennung_runde<N>.json` herunter | `w6_sample.json` von Tower in einen temporären Ordner holen, `py w6_review.py <temp>/w6_sample.json <runde> <erstes> <anzahl> [practice\|check]`; Ergebnis als `runde<N>.json` nach Tower, Seite und lokale Kopien danach löschen |
| `w6_recheck.py` | prüft die aktuellen Vorschläge der Stichprobe gegen die Antworten früherer Runden: Genauigkeit, gefunden, und jedes Feld, das seit der Runde richtig bzw. nicht mehr richtig ist (nach jeder Regeländerung: nichts Richtiges darf falsch werden). Gibt Werte nur in dieser Liste aus – Ausgabe nicht ins Repo | nach `w6_sample.py`, mit `/tmp/w6` wie dort und `-v /mnt/user/test/werterkennung_w6:/out`: `... /m/w6_recheck.py 1 [2 ...]` |
| `w4_collection.py` | Abdeckung und Laufzeit der Vorschläge über alle Wortlisten (nur Zahlen) | wie `w6_sample.py`, mit `-v /mnt/user/test/werterkennung_words_v3:/w:ro` |
