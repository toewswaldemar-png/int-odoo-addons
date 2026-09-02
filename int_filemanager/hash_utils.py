import hashlib
import os

_CHUNK_SIZE = 1024 * 1024


def compute_stable_hash(abs_path):
    """Liest abs_path blockweise und hasht mit SHA-256, aber nur wenn die Datei
    waehrend des Lesens nachweislich unveraendert blieb (stat() vor und nach dem
    Lesen identisch in Groesse und mtime_ns). Gibt (sha256_hex, size, mtime_ns) bei
    einem stabilen Lesevorgang zurueck, sonst None - der Aufrufer behandelt None
    immer als "kann jetzt nicht sicher gehasht werden, spaeter erneut versuchen",
    nie als harten Fehler (verhindert, dass ein Hash aus einem Mischzustand
    gespeichert wird, waehrend ein anderer Prozess gerade schreibt)."""
    try:
        before = os.stat(abs_path)
    except OSError:
        return None

    digest = hashlib.sha256()
    try:
        with open(abs_path, "rb") as f:
            for chunk in iter(lambda: f.read(_CHUNK_SIZE), b""):
                digest.update(chunk)
    except OSError:
        return None

    try:
        after = os.stat(abs_path)
    except OSError:
        return None

    if before.st_size != after.st_size or before.st_mtime_ns != after.st_mtime_ns:
        return None

    return digest.hexdigest(), after.st_size, str(after.st_mtime_ns)
