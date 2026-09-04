import os
import re

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


def _ocr_pdf(abs_path):
    # Lazy-Import: pytesseract/pdf2image (und die System-Binaries tesseract/poppler, siehe
    # Dockerfile) werden nur gebraucht, wenn tatsaechlich ein Scan-PDF ohne Textlayer auftaucht -
    # die meisten Aufrufe (Textlayer vorhanden) kommen nie hier an.
    import pytesseract
    from pdf2image import convert_from_path

    images = convert_from_path(abs_path, dpi=200)
    return "\n".join(pytesseract.image_to_string(img, lang=OCR_LANGUAGES) for img in images)


def _extract_pdf(abs_path):
    from odoo.tools.pdf import PdfReader

    with open(abs_path, "rb") as f:
        reader = PdfReader(f, strict=False)
        pages_text = [page.extract_text() or "" for page in reader.pages]
    text = "\n".join(pages_text)

    if reader.pages and len(text) / len(reader.pages) < MIN_CHARS_PER_PAGE_FOR_TEXT_LAYER:
        # Praktisch kein Textlayer - vermutlich ein Scan, per OCR nachbearbeiten.
        text = _ocr_pdf(abs_path)

    return {"content_text": text}


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
# eine echte KI-Erkennung.

_DATE_RE = re.compile(r"\b(\d{1,2})[.\/](\d{1,2})[.\/](\d{2,4})\b")
_INVOICE_NO_RE = re.compile(
    r"(?:Rechnung(?:s-?nr\.?|snummer)|Invoice\s*No\.?|Beleg-?Nr\.?)\s*[:.]?\s*([A-Za-z0-9\-/]+)",
    re.IGNORECASE,
)
_AMOUNT_RE = re.compile(r"(\d{1,3}(?:\.\d{3})*,\d{2})\s*(?:€|EUR)")

# Nur Kontakte ab dieser Namenslaenge pruefen - kurze Namen (z.B. "AG", "GmbH"-Fragmente durch
# schlechte OCR) wuerden sonst reihenweise falsch-positiv im Fliesstext "gefunden".
_MIN_PARTNER_NAME_LENGTH = 5


def suggest_from_text(env, text):
    """Liefert Vorschlaege aus bereits vorhandenen Daten (Tags, Kontakte) plus simplen
    Regex-Treffern - erfindet nichts, schlaegt nur vor, was schon im System existiert bzw. ein
    einfaches Muster im Text ist. Ergebnis ist zur Kontrolle durch den Nutzer gedacht, nicht zur
    automatischen Uebernahme. Tags/Kontakt kommen inkl. Namen (nicht nur IDs) zurueck, damit der
    Kontroll-Dialog sie ohne weiteren Roundtrip direkt anzeigen kann."""
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

    date_match = _DATE_RE.search(text)
    invoice_match = _INVOICE_NO_RE.search(text)
    amount_match = _AMOUNT_RE.search(text)

    return {
        "suggested_tags": suggested_tags,
        "suggested_partner": suggested_partner,
        "suggested_date": date_match.group(0) if date_match else False,
        "suggested_invoice_number": invoice_match.group(1) if invoice_match else False,
        "suggested_amount": amount_match.group(1) if amount_match else False,
    }
