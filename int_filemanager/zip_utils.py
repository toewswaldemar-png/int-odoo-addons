import os
import zipfile

# Konfigurierbare Limits, analog zu fulltext.py/mediameta.py (int_filemanager.fulltext_max_bytes_*,
# meta_max_bytes_*) - Ablehnung mit Fehlermeldung statt stillschweigend zu haengen/abzuschneiden.
# Ein ZIP-Inhaltsverzeichnis lesen ist billig (kein Dekomprimieren fuer infolist() noetig), deshalb
# hier bewusst KEIN Pending-State/Cron wie bei OCR/Thumbnails - synchron beim Oeffnen des Dialogs.
DEFAULT_ZIP_MAX_BYTES = 200 * 1024 * 1024
DEFAULT_ZIP_MAX_ENTRIES = 5000


class ZipTooLarge(Exception):
    """Archiv-Datei oder Eintragsanzahl ueberschreitet das konfigurierte Limit."""


def _config_int(env, key, default):
    param = env["ir.config_parameter"].sudo().get_param(key)
    if param:
        try:
            return int(param)
        except ValueError:
            pass
    return default


def list_entries(env, abs_path):
    """Flache Liste (Pfad als Praefix im Namen, keine Ordner-Rekonstruktion - Nutzerentscheidung
    2026-09-12) von {name, size, compress_size, is_dir} pro Archiveintrag. Das Limit auf die
    Datei selbst deckt keine Zip-Bombs mit winzigem komprimierten, aber riesigem entpacktem
    Gesamtinhalt ab - fuer den internen Hausgebrauch dieses Dateimanagers (kein oeffentlicher
    Endpunkt) bewusst nicht weiter gehaertet, siehe extract_entry() fuer die Grenze pro
    Einzeldatei."""
    max_bytes = _config_int(env, "int_filemanager.zip_max_bytes", DEFAULT_ZIP_MAX_BYTES)
    size = os.path.getsize(abs_path)
    if max_bytes and size > max_bytes:
        raise ZipTooLarge(
            "ZIP-Datei zu groß zum Anzeigen (%d Bytes, Limit %d Bytes)." % (size, max_bytes)
        )

    max_entries = _config_int(env, "int_filemanager.zip_max_entries", DEFAULT_ZIP_MAX_ENTRIES)
    with zipfile.ZipFile(abs_path) as zf:
        infolist = zf.infolist()
        if max_entries and len(infolist) > max_entries:
            raise ZipTooLarge(
                "ZIP-Datei hat zu viele Einträge (%d, Limit %d)." % (len(infolist), max_entries)
            )
        return [
            {
                "name": info.filename,
                "size": info.file_size,
                "compress_size": info.compress_size,
                "is_dir": info.is_dir(),
            }
            for info in infolist
        ]


def extract_entry(env, abs_path, entry):
    """Liest genau einen Archiveintrag vollstaendig in den Speicher und gibt die Rohbytes zurueck
    - kein Schreiben aufs Dateisystem (Nutzerentscheidung 2026-09-12: nur Einzeldatei-Download,
    kein Entpacken in den Ordner), deshalb auch kein Zip-Slip-Pfadtraversal-Risiko wie bei einem
    echten Extrahieren. file_size (unkomprimiert, aus dem zentralen Verzeichnis - kein
    Dekomprimieren noetig, um ihn zu kennen) wird trotzdem gegen dasselbe Limit wie die Gesamtdatei
    geprueft, damit ein einzelner stark komprimierter Eintrag (Zip Bomb) nicht durchrutscht."""
    max_bytes = _config_int(env, "int_filemanager.zip_max_bytes", DEFAULT_ZIP_MAX_BYTES)
    with zipfile.ZipFile(abs_path) as zf:
        info = zf.getinfo(entry)
        if max_bytes and info.file_size > max_bytes:
            raise ZipTooLarge(
                "Eintrag zu groß zum Herunterladen (%d Bytes, Limit %d Bytes)." % (info.file_size, max_bytes)
            )
        return zf.read(info)
