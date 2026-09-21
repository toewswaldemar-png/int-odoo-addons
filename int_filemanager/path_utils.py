import contextlib
import os
import secrets
import threading
import unicodedata
from datetime import datetime

from odoo.exceptions import ValidationError

from .mediameta import AUDIO_EXTENSIONS, IMAGE_EXTENSIONS, PDF_EXTENSIONS

DEFAULT_ROOT = "/mnt/hm-daten"

# --- Watcher-Unterdrueckung fuer App-eigene Aenderungen ------------------------------------
# Grundproblem, live 2026-09-21 gefunden (docs/int_filemanager_papierkorb_konzept.md): jede
# App-eigene Dateisystem-Operation (Upload, Loeschen/Papierkorb, Wiederherstellen, Umbenennen,
# Verschieben) wird vom Watcher UNABHAENGIG noch einmal gesehen und fuehrt zu einem zweiten,
# parallelen Versuch, denselben Index-Datensatz zu pflegen - unabhaengig davon, ob man das per
# Datenbank-Lock zu verhindern versucht (nicht moeglich: Odoo setzt seine Cursor auf
# REPEATABLE READ, sql_db.py - eine Transaktion sieht nach dem Warten auf einen Lock trotzdem
# nur ihren eingefrorenen Schnappschuss, niemals den aktuellen Stand). inotify selbst kann
# ohnehin nicht unterscheiden, wer eine Aenderung ausgeloest hat (dokumentierte Linux-
# Einschraenkung, man7.org/linux/man-pages/man7/inotify.7.html) - die App muss es also selbst
# wissen und dem Watcher mitteilen, statt zu versuchen, das Ergebnis hinterher zu reparieren.
#
# In-Memory statt DB, KEIN Zeitfenster/Timeout: markiert einen absoluten Pfad fuer die Dauer der
# tatsaechlichen Operation (try/finally, siehe suppress()), nicht fuer eine geschaetzte Dauer -
# funktioniert, weil Watcher und Webserver im selben Python-Prozess laufen (workers=0, bewusste
# Entscheidung, siehe [[project_hm_odoo_filemanager]]). Ein abgestuerzter Prozess verliert die
# Markierung automatisch beim Neustart, kein dauerhaft haengender Zustand moeglich. Absolute statt
# relative Pfade: beide Seiten (Watcher-Ereignis, App-Aufrufer) haben sie ohnehin schon vorliegen,
# keine DB-Abfrage fuer die reine Pruefung noetig.
_suppressed_paths = set()
_suppressed_lock = threading.Lock()


@contextlib.contextmanager
def suppress_watcher(*abs_paths):
    """Markiert die gegebenen absoluten Pfade, solange der Kontext laeuft, als "wird gerade von
    der App selbst bearbeitet" - watcher.py._process_batch() ueberspringt eigene
    Indexierungsversuche fuer diese Pfade in dieser Zeit. Um jede App-eigene Operation legen, die
    eine echte Dateisystem-Aenderung macht UND selbst den Index pflegt (siehe Aufrufer in
    controllers/main.py, index_utils.py)."""
    with _suppressed_lock:
        for p in abs_paths:
            _suppressed_paths.add(p)
    try:
        yield
    finally:
        with _suppressed_lock:
            for p in abs_paths:
                _suppressed_paths.discard(p)


def is_watcher_suppressed(abs_path):
    with _suppressed_lock:
        return abs_path in _suppressed_paths

# Nur fuer friendly_fallback_name() - mediameta.py hat bewusst kein Video (Phase 4 hat Video
# explizit ausgeklammert), aber fuer die Wortwahl beim Umbenennen reicht die Dateiendung, keine
# echte Metadatenextraktion noetig. Dieselben drei Endungen wie
# filemanager_controller_mixin.js's VIDEO_EXTENSIONS (Browser-abspielbar ohne Zusatz-Codec).
_VIDEO_EXTENSIONS = {"mp4", "webm", "ogv"}

_TYPE_WORDS = {
    **{ext: "Foto" for ext in IMAGE_EXTENSIONS},
    **{ext: "Scan" for ext in PDF_EXTENSIONS},
    **{ext: "Audio" for ext in AUDIO_EXTENSIONS},
    **{ext: "Video" for ext in _VIDEO_EXTENSIONS},
}


def get_root(env):
    root = env["ir.config_parameter"].sudo().get_param("int_filemanager.root_path", DEFAULT_ROOT)
    return os.path.realpath(root)


def resolve_path(env, rel_path):
    """Resolve a client-supplied relative path to an absolute path, guaranteed
    to stay inside the configured filemanager root (blocks path traversal)."""
    root = get_root(env)
    rel_path = (rel_path or "").strip().lstrip("/\\")
    target = os.path.realpath(os.path.join(root, rel_path))
    if target != root and not target.startswith(root + os.sep):
        raise ValidationError("Ungültiger Pfad.")
    return target


def to_relative(env, abs_path):
    """Inverse of resolve_path: validates that abs_path is inside root and
    returns the path relative to it."""
    root = get_root(env)
    abs_path = os.path.realpath(abs_path)
    if abs_path == root:
        return ""
    if not abs_path.startswith(root + os.sep):
        raise ValidationError("Pfad liegt außerhalb des Filemanager-Stammverzeichnisses.")
    return os.path.relpath(abs_path, root)


def safe_name(name):
    """Validate a plain file/folder name (no path separators, no . / ..).
    Normalisiert auf NFC, damit Unicode-aequivalente, aber unterschiedlich
    kodierte Namen (z.B. von macOS-SMB-Clients, die NFD liefern) nicht als
    unterschiedliche Pfade behandelt werden - relevant fuer die
    Schutzordner-Pfadpraefix-Erkennung in acl_rules.py."""
    name = unicodedata.normalize("NFC", (name or "").strip())
    if not name or name in (".", "..") or "/" in name or "\\" in name:
        raise ValidationError("Ungültiger Name.")
    return name


def friendly_fallback_name(name):
    """Ersetzt Uploads mit erkennbar bedeutungslosem Namen (kein einziger Buchstabe
    irgendwo im Namen - z.B. rein numerische IDs von Handy-/Cloud-Uploads wie
    "17890421015741792308593513700259.jpg") durch ein sprechendes Schema
    Typ_JJJJMMTT_HHMMSS_xxxx.<ext>, Typ anhand der Endung aus _TYPE_WORDS (Default
    "Dokument"). Enthaelt der Name mindestens einen Buchstaben, gilt er als bereits
    sinnvoll benannt und bleibt unveraendert - kein Ersatz fuer z.B. "Rechnung_2026.pdf"."""
    stem, ext = os.path.splitext(name)
    if any(ch.isalpha() for ch in stem):
        return name
    ext = ext.lstrip(".").lower()
    word = _TYPE_WORDS.get(ext, "Dokument")
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = secrets.token_hex(2)
    base = f"{word}_{stamp}_{suffix}"
    return f"{base}.{ext}" if ext else base


def make_shareable(abs_path, is_dir):
    """The share's existing files/folders (created via Samba) are all 777/666
    so any Windows user can write to them regardless of SMB user mapping.
    os.makedirs/f.save() create with the container's own uid:gid (100:101)
    and default umask instead, which locks other users out - override it."""
    try:
        os.chmod(abs_path, 0o777 if is_dir else 0o666)
    except PermissionError:
        # Live als Bug gefunden 2026-09-16: SMB-Mounts mit fixen file_mode/dir_mode-
        # Optionen (hier file_mode=0777,dir_mode=0777, siehe die drei Unraid-Remote-Share-
        # Mounts) liefern neu angelegte Dateien/Ordner bereits MIT den gewuenschten 0777/
        # 0666-Rechten aus - der Server verweigert dort ein nachtraegliches chmod
        # (PermissionError/EPERM), weil er die Rechte einheitlich ueber die Mount-Option
        # vorgibt statt sie pro Datei individuell zu verwalten. chmod ist in diesem Fall
        # ueberfluessig, nicht fehlgeschlagen - ein Upload darf daran nicht scheitern
        # (500-Fehler trotz bereits erfolgreich geschriebener Datei, siehe controllers/
        # main.py: upload()).
        pass
