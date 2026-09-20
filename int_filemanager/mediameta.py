import base64
import os
from datetime import datetime
from io import BytesIO

from PIL import ExifTags, Image
from odoo.tools.pdf import PdfReader

IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "gif", "webp", "bmp", "tiff", "tif"}
PDF_EXTENSIONS = {"pdf"}
AUDIO_EXTENSIONS = {"mp3", "wav", "flac", "ogg", "m4a", "aac", "wma"}

THUMBNAIL_MAX_SIZE = (320, 320)
# Fuer die Vollbildvorschau (Nutzerfeedback 2026-09-20: "Bild baut sich schrittweise auf" bei
# Handyfotos mit mehreren MB) - deutlich groesser als das Kachel-Thumbnail, aber immer noch weit
# unter typischen Kamera-Aufloesungen (4000x3000+). Kein Bildschirm braucht mehr als das zum
# verlustfrei wirkenden Betrachten, das echte Original bleibt fuer "Original herunterladen"
# weiterhin unangetastet erreichbar (siehe controllers/main.py:download).
PREVIEW_MAX_SIZE = (1920, 1920)

# EXIF-Tag-ID fuer "DateTimeOriginal" (Kamera-Aufnahmezeitpunkt) - per Name statt
# fest verdrahteter Zahl nachgeschlagen, damit die Zuordnung nicht stillschweigend
# von einer bestimmten Pillow-Version abhaengt.
_EXIF_DATETIME_ORIGINAL_TAG = next(k for k, v in ExifTags.TAGS.items() if v == "DateTimeOriginal")


class MetaTooLarge(Exception):
    """Datei ueberschreitet das konfigurierte Groessenlimit fuer ihren
    Medientyp - wird abgelehnt statt stillschweigend uebersprungen (analog
    zur Grossdatei-Entscheidung bei der Versionierung in Phase 3)."""


def ext_of(name):
    i = name.rfind(".")
    return name[i + 1:].lower() if i != -1 else ""


def media_type_of(name):
    """None fuer alles ausserhalb der drei in v1 unterstuetzten Medientypen -
    Video ist bewusst nicht enthalten (kein Extraktions-Tooling im Image)."""
    ext = ext_of(name)
    if ext in IMAGE_EXTENSIONS:
        return "image"
    if ext in PDF_EXTENSIONS:
        return "pdf"
    if ext in AUDIO_EXTENSIONS:
        return "audio"
    return None


def _resized_jpeg(img, max_size):
    resized = img.copy()
    resized.thumbnail(max_size)
    if resized.mode not in ("RGB", "L"):
        resized = resized.convert("RGB")
    buf = BytesIO()
    resized.save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue())


def _extract_image(abs_path):
    with Image.open(abs_path) as img:
        width, height = img.size
        taken_at = None
        try:
            exif = img.getexif()
            raw = exif.get(_EXIF_DATETIME_ORIGINAL_TAG)
            if raw:
                # Naiv uebernommen (Kamera-Lokalzeit) - keine Zeitzonenumrechnung,
                # bewusste Vereinfachung fuer v1 (siehe Ausbauplan Phase 4).
                taken_at = datetime.strptime(raw, "%Y:%m:%d %H:%M:%S")
        except (ValueError, TypeError, SyntaxError):
            taken_at = None
        # Beide Groessen aus demselben bereits dekodierten Bild (.copy() statt erneutem
        # Image.open()) - eine Datei wird fuer Kachel-Thumbnail UND Vollbild-Vorschau nur einmal
        # von der Platte gelesen/dekodiert.
        thumbnail = _resized_jpeg(img, THUMBNAIL_MAX_SIZE)
        preview = _resized_jpeg(img, PREVIEW_MAX_SIZE)
    return {
        "thumbnail": thumbnail,
        "preview": preview,
        "media_width": width,
        "media_height": height,
        "taken_at": taken_at,
    }


def _extract_pdf(abs_path):
    # Nur die Seitenzahl - eine gerenderte Vorschau bräuchte poppler/PyMuPDF,
    # das im Image nicht vorhanden ist (empirisch geprüft, siehe Ausbauplan).
    # strict=False: reale PDFs (z.B. von Scannern) haben oft eine
    # geringfügig fehlerhafte xref-Tabelle - dafür soll die Seitenzahl-
    # Extraktion nicht hart fehlschlagen, wenn eine Reparatur möglich ist.
    with open(abs_path, "rb") as f:
        reader = PdfReader(f, strict=False)
        page_count = len(reader.pages)
    return {"page_count": page_count}


def _extract_audio(abs_path):
    import mutagen

    audio = mutagen.File(abs_path, easy=True)
    if audio is None:
        raise ValueError("Nicht erkanntes Audioformat.")

    def first(key):
        vals = audio.tags.get(key) if audio.tags else None
        return vals[0] if vals else None

    return {
        "audio_duration": float(getattr(audio.info, "length", 0.0) or 0.0),
        "audio_title": first("title"),
        "audio_artist": first("artist"),
        "audio_album": first("album"),
    }


_EXTRACTORS = {"image": _extract_image, "pdf": _extract_pdf, "audio": _extract_audio}


def extract_metadata(abs_path, media_type, max_bytes):
    """Liest abs_path fuer die Metadatenextraktion, aber nur wenn die Datei
    waehrend des Vorgangs nachweislich unveraendert blieb (stat() vor und
    nach dem Lesen identisch in Groesse und mtime_ns - dasselbe Verfahren wie
    hash_utils.compute_stable_hash in Phase 1, verhindert, dass Metadaten aus
    einem Mischzustand gespeichert werden, waehrend ein anderer Prozess
    gerade schreibt). Gibt None zurueck, wenn die Datei sich waehrenddessen
    aenderte oder kurz verschwand - der Aufrufer belaesst den Datensatz dann
    auf pending und versucht es beim naechsten Cron-Lauf erneut, statt das
    als Fehler zu werten.

    Raises MetaTooLarge, wenn die Datei das konfigurierte Limit fuer ihren
    Medientyp ueberschreitet - das ist ein definitiver Zustand (Aufrufer
    markiert error), keine transiente Bedingung."""
    try:
        before = os.stat(abs_path)
    except OSError:
        return None

    if max_bytes and before.st_size > max_bytes:
        raise MetaTooLarge(
            "Datei zu groß für Metadatenextraktion (%d Bytes, Limit %d Bytes)." % (before.st_size, max_bytes)
        )

    result = _EXTRACTORS[media_type](abs_path)

    try:
        after = os.stat(abs_path)
    except OSError:
        return None
    if before.st_size != after.st_size or before.st_mtime_ns != after.st_mtime_ns:
        return None

    result["meta_source_size"] = after.st_size
    result["meta_source_mtime_ns"] = str(after.st_mtime_ns)
    return result
