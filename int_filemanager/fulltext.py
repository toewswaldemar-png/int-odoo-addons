import os
import re
import tempfile

# v1 bewusst nur PDF + reine Textformate - Office-Dokumente (docx/xlsx/...) und Bilder sind ein
# eigener, spaeterer Schritt (siehe docs/int_filemanager_paperoffice_recherche.md, Baustein 1/1b).
# Bilder insbesondere bewusst NICHT enthalten: die meisten Bilder im Bestand sind private Fotos,
# nicht Scans - blindes OCR darueber waere reine Rechenzeitverschwendung ohne Nutzen.
PLAIN_TEXT_EXTENSIONS = {"txt", "md", "csv", "log", "json"}
PDF_EXTENSIONS = {"pdf"}

# Ein PDF mit weniger Text pro Seite als dieser Schwellenwert gilt als Scan ohne nutzbaren
# Textlayer und wird per OCR nachbearbeitet - digital erzeugte PDFs (die meisten E-Rechnungen)
# haben bereits einen Textlayer und sparen sich damit den teuren OCR-Schritt komplett.
MIN_CHARS_PER_PAGE_FOR_TEXT_LAYER = 20

OCR_LANGUAGES = "deu+eng"


class FulltextTooLarge(Exception):
    """Datei ueberschreitet das konfigurierte Groessenlimit fuer ihren Fulltext-Typ - analog zu
    mediameta.MetaTooLarge: wird abgelehnt statt stillschweigend uebersprungen."""


def ext_of(name):
    i = name.rfind(".")
    return name[i + 1:].lower() if i != -1 else ""


def fulltext_type_of(name):
    """None fuer alles ausserhalb der in v1 unterstuetzten Typen - siehe Kommentar oben."""
    ext = ext_of(name)
    if ext in PLAIN_TEXT_EXTENSIONS:
        return "plain"
    if ext in PDF_EXTENSIONS:
        return "pdf"
    return None


def _extract_plain(abs_path):
    with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
        return {"content_text": f.read()}


def _pdfplumber_words_per_page(pdf_path):
    # Lazy-Import: pdfplumber wird nur bei tatsaechlichem PDF-Zugriff gebraucht. Ersetzt seit
    # Phase B (docs/int_filemanager_ocr_selbstdefinierte_felder.md) PyPDF2/odoo.tools.pdf.PdfReader
    # als einzigen Extraktionsweg fuer PDFs - liefert Wort-Boxen direkt in PDF-Punkt-Koordinaten,
    # dieselbe Bibliothek fuer digitale UND (nach OCRmyPDF) gescannte PDFs, kein zweiter
    # Extraktionsweg mehr noetig. PyMuPDF bewusst nicht gewaehlt (AGPL, nicht mit der bisherigen
    # freizuegigen Lizenzfamilie vereinbar).
    import pdfplumber

    with pdfplumber.open(pdf_path) as pdf:
        return [page.extract_words(use_text_flow=False) for page in pdf.pages]


def _build_indexed_text(pages_words):
    """Baut den Volltext UND eine parallele Liste von Wort-Boxen mit exaktem Zeichen-Offset in
    GENAU diesem Text auf - beide aus denselben Tokens im selben Durchlauf, damit ein
    Regex-Treffer im Text sich verlustfrei auf seine zugrundeliegenden Wort-Boxen zurueckfuehren
    laesst (siehe _locate_span in _match_patterns). page ist 1-basiert."""
    chunks = []
    word_index = []
    offset = 0
    for page_no, words in enumerate(pages_words, start=1):
        for w in words:
            token = w["text"]
            start = offset
            chunks.append(token)
            offset += len(token)
            word_index.append(
                {"start": start, "end": offset, "page": page_no, "x0": w["x0"], "y0": w["top"], "x1": w["x1"], "y1": w["bottom"]}
            )
            chunks.append(" ")
            offset += 1
        chunks.append("\n")
        offset += 1
    return "".join(chunks), word_index


def pdf_word_index(abs_path):
    """Rein lesende, guenstige (KEINE OCR) Wort-Positions-Ermittlung gegen die aktuell auf der
    Platte liegende Datei - fuer den Kurzschluss-Pfad in filemanager_file.py wenn content_text
    schon gecacht ist und nur frische Positionen fuer eine erneute interaktive Analyse gebraucht
    werden. Liefert [] statt eines Fehlers, wenn die Datei (nicht mehr) lesbar ist oder keinen
    Textlayer hat - z.B. ein Scan, dessen OCR-Textlayer beim letzten Lauf nur in einer bereits
    wieder geloeschten Temp-Datei existierte (siehe _extract_pdf: die Originaldatei wird von
    OCRmyPDF nie ueberschrieben)."""
    try:
        _, word_index = _build_indexed_text(_pdfplumber_words_per_page(abs_path))
    except Exception:
        return []
    return word_index


def _ocr_pdf_searchable(abs_path):
    """Baut mit OCRmyPDF (statt rohem pytesseract/pdf2image) eine durchsuchbare Kopie mit
    korrekt positioniertem, unsichtbarem Textlayer in einer Temp-Datei - Tesseract laeuft
    weiterhin intern (siehe Dockerfile), wird aber nicht mehr direkt aufgerufen. Schreibt NIE in
    die Originaldatei zurueck (bewusste Entscheidung): ein automatischer Analyse-/Cron-Schritt
    soll nie unbemerkt die vom Nutzer verwaltete Originaldatei veraendern (mtime/Hash wuerden
    sonst Versionierung/Dedup verwirren) - die Temp-Datei existiert nur fuer die Dauer dieses
    einen pdfplumber-Durchlaufs und wird danach vom Aufrufer wieder geloescht. force_ocr=True:
    die eigene Textlayer-Heuristik oben hat bereits entschieden, dass der vorhandene Textlayer
    (falls ueberhaupt einer existiert) unbrauchbar ist - OCRmyPDF soll ihn ersetzen statt mit
    einem Fehler abzubrechen, weil es selbst noch (unzureichenden) Text vorfindet."""
    import ocrmypdf

    fd, out_path = tempfile.mkstemp(suffix=".pdf")
    os.close(fd)
    try:
        ocrmypdf.ocr(abs_path, out_path, language=OCR_LANGUAGES, force_ocr=True, progress_bar=False)
    except Exception:
        os.remove(out_path)
        raise
    return out_path


def _extract_pdf(abs_path):
    pages_words = _pdfplumber_words_per_page(abs_path)
    text, word_index = _build_indexed_text(pages_words)

    if pages_words and len(text) / len(pages_words) < MIN_CHARS_PER_PAGE_FOR_TEXT_LAYER:
        # Praktisch kein Textlayer - vermutlich ein Scan, per OCRmyPDF nachbearbeiten. Anders als
        # das fruehere rohe pytesseract.image_to_string() liefert das auch gleich Wort-Positionen
        # fuer das PDF-Highlighting (Phase C), keine eigene Pixel->Punkt-Umrechnung noetig.
        ocr_path = _ocr_pdf_searchable(abs_path)
        try:
            pages_words = _pdfplumber_words_per_page(ocr_path)
            text, word_index = _build_indexed_text(pages_words)
        finally:
            os.remove(ocr_path)

    # "_word_index" beginnt bewusst mit "_": kein echtes Feld auf int_filemanager.file -
    # filemanager_file.py::_extract_fulltext_for_record poppt es aus dem Ergebnis heraus, BEVOR
    # der Rest per self.write() gespeichert wird (siehe dort).
    return {"content_text": text, "_word_index": word_index}


_EXTRACTORS = {"plain": _extract_plain, "pdf": _extract_pdf}


def extract_fulltext(abs_path, fulltext_type, max_bytes):
    """Analog zu mediameta.extract_metadata: liest abs_path nur, wenn die Datei waehrend des
    Vorgangs nachweislich unveraendert blieb (stat vor/nach identisch). Gibt None zurueck bei
    Aenderung/kurzem Verschwinden waehrenddessen (Aufrufer belaesst pending), raised
    FulltextTooLarge bei Ueberschreitung des Groessenlimits (definitiver Fehlerzustand)."""
    try:
        before = os.stat(abs_path)
    except OSError:
        return None

    if max_bytes and before.st_size > max_bytes:
        raise FulltextTooLarge(
            "Datei zu groß für Volltextextraktion (%d Bytes, Limit %d Bytes)." % (before.st_size, max_bytes)
        )

    result = _EXTRACTORS[fulltext_type](abs_path)

    try:
        after = os.stat(abs_path)
    except OSError:
        return None
    if before.st_size != after.st_size or before.st_mtime_ns != after.st_mtime_ns:
        return None

    result["ocr_source_size"] = after.st_size
    result["ocr_source_mtime_ns"] = str(after.st_mtime_ns)
    return result


# --- Interaktive Werterkennung (nur fuer den Analyse-Endpunkt, nicht den Hintergrund-Cron) ------
# Bewusst einfache Regex statt eines Sprachmodells (Nutzerentscheidung 2026-09-05) - keine externe
# Abhaengigkeit, keine laufenden Kosten pro Dokument, dafuer erwartungsgemaess eingeschraenkter als
# eine echte KI-Erkennung. Die Muster selbst liegen seit 2026-09-07 nicht mehr hier als Konstanten,
# sondern im admin-konfigurierbaren int_filemanager.extraction_pattern-Modell (siehe
# models/filemanager_extraction_pattern.py, "Dateimanager > Konfiguration > Erkennungsmuster") -
# diese Funktion liest sie nur noch aus, aendert nichts an der Auswertungslogik selbst.

# Nur Kontakte ab dieser Namenslaenge pruefen - kurze Namen (z.B. "AG", "GmbH"-Fragmente durch
# schlechte OCR) wuerden sonst reihenweise falsch-positiv im Fliesstext "gefunden".
_MIN_PARTNER_NAME_LENGTH = 5


def _locate_span(word_index, start, end):
    """Bildet einen Zeichenbereich (z.B. match.span(group_index)) auf eine Umriss-Box ab, indem
    alle Woerter herangezogen werden, deren eigener Bereich den Treffer ueberlappt (ein Treffer
    kann mehrere Woerter umfassen, z.B. "12.345,67") - die Box ist die Vereinigung all dieser
    Wort-Boxen. None, wenn kein Wort ueberlappt (z.B. reine Textdatei ohne word_index) oder der
    Treffer ueber eine Seitengrenze hinweg reicht (seltener Randfall, dann lieber keine Markierung
    als eine falsche - der Wert selbst bleibt trotzdem korrekt erkannt)."""
    if not word_index:
        return None
    hits = [w for w in word_index if w["end"] > start and w["start"] < end]
    if not hits:
        return None
    pages = {w["page"] for w in hits}
    if len(pages) > 1:
        return None
    return {
        "page": hits[0]["page"],
        "x0": min(w["x0"] for w in hits),
        "y0": min(w["y0"] for w in hits),
        "x1": max(w["x1"] for w in hits),
        "y1": max(w["y1"] for w in hits),
    }


def _match_patterns(env, text, word_index):
    """Jedes aktive Erkennungsmuster liefert unabhaengig sein eigenes Ergebnis - kein gemeinsamer
    Slot pro target_field mehr (seit 2026-09-19 vereinheitlicht, vorher gab es einen Sonderpfad
    fuer drei fest verdrahtete Felder date/invoice_number/amount, die inzwischen entfernt sind -
    siehe docs/int_filemanager_ocr_selbstdefinierte_felder.md, Abschnitt "Vereinheitlichung").
    Liefert zusaetzlich die Position im PDF (Phase C), sofern word_index vorhanden und der Treffer
    nicht ueber eine Seitengrenze reicht. Ein einzelnes ungueltiges Muster (sollte durch die
    Konstraint auf dem Modell nicht vorkommen, aber IndexError bei einer zu hoch gewaehlten
    group_index ist erst zur Matchzeit pruefbar) wird uebersprungen statt die gesamte Erkennung
    abzubrechen."""
    matches = []
    patterns = env["int_filemanager.extraction_pattern"].sudo().search([], order="sequence, id")
    for rec in patterns:
        try:
            match = re.compile(rec.pattern, re.IGNORECASE if rec.ignore_case else 0).search(text)
        except re.error:
            continue
        if not match:
            continue
        try:
            value = match.group(rec.group_index)
            span = match.span(rec.group_index)
        except IndexError:
            continue
        if not value:
            continue
        position = _locate_span(word_index, span[0], span[1])
        matches.append({
            "pattern_id": rec.id,
            "pattern_name": rec.name,
            "value": value,
            "page": position["page"] if position else False,
            "x0": position["x0"] if position else False,
            "y0": position["y0"] if position else False,
            "x1": position["x1"] if position else False,
            "y1": position["y1"] if position else False,
        })
    return matches


def suggest_from_text(env, text, word_index=None):
    """Liefert Vorschlaege aus bereits vorhandenen Daten (Tags, Kontakte) plus simplen
    Regex-Treffern - erfindet nichts, schlaegt nur vor, was schon im System existiert bzw. ein
    einfaches Muster im Text ist. Ergebnis ist zur Kontrolle durch den Nutzer gedacht, nicht zur
    automatischen Uebernahme. Tags/Kontakt kommen inkl. Namen (nicht nur IDs) zurueck, damit der
    Kontroll-Dialog sie ohne weiteren Roundtrip direkt anzeigen kann. word_index (Phase B, optional)
    sind Wort-Boxen fuer die erkannten Felder (matches) - None/leer bei Klartextdateien oder wenn
    keine Positionen ermittelt werden konnten (matches liefert dann trotzdem die Werte, nur ohne
    Position)."""
    text_lower = text.lower()

    tag_matches = env["int_filemanager.tag"].sudo().search([])
    suggested_tags = [
        {"id": t.id, "name": t.name} for t in tag_matches if t.name and t.name.lower() in text_lower
    ]

    suggested_partner = False
    partners = env["res.partner"].sudo().search([("name", "!=", False)], limit=2000)
    for partner in partners:
        if len(partner.name) >= _MIN_PARTNER_NAME_LENGTH and partner.name in text:
            suggested_partner = {"id": partner.id, "name": partner.display_name}
            break

    matches = _match_patterns(env, text, word_index or [])

    return {
        "suggested_tags": suggested_tags,
        "suggested_partner": suggested_partner,
        "matches": matches,
    }
