# Prototypen Werterkennung (2026-09-29)

Wegwerf-Skripte aus der Planung, **kein Modulcode**; Vorlage für W-3/W-4 und W-6
(`docs/int_filemanager_v2_werterkennung_plan_2026-09-29.md`). Enthalten keine Dokumente oder persönlichen Daten.

| Datei | Zweck | Aufruf (Tower, Wegwerf-Container ohne Netz) |
|---|---|---|
| `keyword_search.py` | Stichwort-Modus: Katalog aus 18 Feldern, Suche **A** im Text (Wert in den nächsten 6 Wörtern) und **B** nach Seitenlage (rechts daneben / darunter, Spaltengrenze = großer Wortabstand), Wertarten Nummer (auch in Leerzeichen-Gruppen), Datum, Betrag (Einheit davor oder dahinter), ct/kWh, kWh, Zeitraum, Dauer; Prüfziffern USt-IdNr./Gläubiger-ID. Liest noch das **alte** Wortlisten-Format v1 (Wörter als Objekte) – für v2 anpassen | `docker run --rm --network none --entrypoint python3 -e PYTHONPATH=/usr/lib/python3/dist-packages -v <dir>:/data odoo:19.0-hm-test /data/keyword_search.py /data/<wortliste>.json` |
| `classify.py` | teilt PDFs in digital / Scan mit Scanner-Text / Scan ohne Text (Bildanteil je Seite) | `docker run --rm --user 0 --network none -v /mnt/user/test/werterkennung:/docs:ro -v <out>:/out fmconverter:dev python /out/classify.py /docs` |
| `ocrcompare.py` | Scanner-Text gegen `--redo-ocr` gegen `--force-ocr` (Anteil sauberer Wörter) | wie oben, braucht `classes.tsv` aus `classify.py` |
| `runall.py` | Wortliste über die ganze Sammlung, Kennzahlen + `index.json`, Wortlisten als `NNNN.json` (liegt auf Tower unter `<out>/_tools/`) | `docker run -d -u 0 --network none -w /app -e PYTHONPATH=/app -e CONVERTER_OCR_TOOL_TIMEOUT_S=900 -v /mnt/user/test/werterkennung:/docs:ro -v <out>:/out fmconverter:dev sh -c "python /out/_tools/runall.py > /out/run.log 2>&1"` – **ohne** `CONVERTER_OCR_TOOL_TIMEOUT_S` gilt beim direkten Aufruf (ohne `server.py`) das kurze Werkzeuglimit von 25 s, große Scans scheitern dann |
