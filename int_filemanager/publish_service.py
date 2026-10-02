"""Ablauf "Datenbank hat Vorrang" (docs/int_filemanager_konzept_db_vorrang_2026-09-24.md, 4.1) -
Durchstich fuer das Upload-Ueberschreiben. Die uebrigen Schreibwege (ONLYOFFICE, WebDAV-PUT, Text,
Restore) laufen bis zu ihrer Umstellung weiter ueber write_service.snapshot_and_write().

Grundsatz: Der Request-Commit ist verbindlich, die Platte folgt.

  Request (stage_overwrite)   Zeile sperren (lock_for_update), neuen Inhalt als Filestore-Blob in
                              pending_content ablegen, revision+1, share_state='pending'; der
                              postcommit-Hook wird ZULETZT registriert. Kein Zugriff auf den Share,
                              keine eigene DB-Verbindung, kein Advisory-Lock - Odoos retrying() darf den
                              Request beliebig wiederholen.
  Hook / Cron (publish_pending)
    Phase A (eigener Cursor)  Zeile sperren, Zustand pruefen, alten Plattenstand als Version sichern
                              (Herkunft 'extern', wenn er vom Indexstand abweicht), pending_version_id
                              setzen, COMMIT - die Sicherung ist dauerhaft, bevor die Datei ersetzt wird.
    Phase B (eigener Cursor)  EINE Transaktion, Zeilensperre bis zum Ende: stat erneut pruefen (hat sich die
                              Datei seit der Sicherung geaendert -> zurueck zu Phase A), verwaiste Temp-
                              Dateien des Vorgangs entfernen (nur bei Wiederholung), Temp-Datei im selben
                              Ordner, fsync, os.replace, fsync des Elternordners, Index nachziehen
                              (index_upsert), share_state='synced', pending_* leeren, COMMIT.
  Jede Stufe ist wiederholbar: ein Abbruch an beliebiger Stelle laesst share_state='pending', der
  naechste Lauf (Cron alle 5 Minuten) setzt genau dort wieder an, ohne Doppelversion.

Der Hook selbst faengt jede Ausnahme (Odoos Callbacks.run wuerde sonst trotz Commit einen 500
liefern, siehe Konzept Abschnitt 3). Im Testmodus laufen postcommit-Hooks nicht (TestCursor) -
publish_pending() ist deshalb direkt aufrufbar.

Uebergangsloesung: suppress_watcher() haelt den heutigen Watcher fuer den Pfad heraus; sie entfaellt,
sobald der Watcher nur noch Zulieferer ist (Konzept 4.5)."""

import base64
import hashlib
import logging
import os
import tempfile
from datetime import datetime, timedelta

from odoo import _
from odoo.api import SUPERUSER_ID, Environment
from odoo.exceptions import LockError, UserError, ValidationError
from odoo.modules.registry import Registry

from .index_utils import index_upsert
from .path_utils import make_shareable, suppress_watcher
from .write_service import DEFAULT_VERSION_MAX_SIZE_MB

_logger = logging.getLogger(__name__)

# Begrenzte Wiederholung, wenn sich die Datei zwischen Lesen und Austausch aendert (Konzept 4.1).
MAX_STABLE_ATTEMPTS = 3
CHUNK = 1024 * 1024
# Toleranz beim Vergleich Plattenstand <-> Index (mtime im Index ist sekundengenau, lokale Zeit).
EXTERN_MTIME_TOLERANCE_S = 2.0
TEMP_PREFIX = ".int_filemanager_tmp_"

# --- Fehlerinjektion (nur Tests) ------------------------------------------------------------
# Aktiv nur, wenn ein Test _fault_stage setzt bzw. die Umgebungsvariable
# INT_FILEMANAGER_FAULT_FILE auf eine Datei zeigt, die "<stufe>[:exit]" enthaelt (Testinstanz mit
# echten Prozessen; ":exit" beendet den Prozess hart mit os._exit). In Produktion ist weder das eine
# noch das andere gesetzt: ein Aufruf kostet dann nur zwei Vergleiche.
_fault_stage = None
_test_hooks = {}  # stufe -> callable(), fuer Tests, die zwischen zwei Stufen extern eingreifen
FAULT_FILE_ENV = "INT_FILEMANAGER_FAULT_FILE"


class FaultInjected(RuntimeError):
    pass


def fault_point(stage):
    hook = _test_hooks.get(stage)
    if hook is not None:
        hook()
    spec = _fault_stage
    if spec is None:
        path = os.environ.get(FAULT_FILE_ENV)
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as f:
                spec = f.read().strip()
        except OSError:
            return
    name, _sep, mode = (spec or "").partition(":")
    if name != stage:
        return
    if mode == "exit":
        os._exit(137)
    raise FaultInjected(f"Fehlerinjektion an Stufe {stage!r}")


# --- Hilfsfunktionen -------------------------------------------------------------------------


def _max_bytes(env):
    max_mb = int(
        env["ir.config_parameter"].sudo().get_param("int_filemanager.version_max_size_mb", str(DEFAULT_VERSION_MAX_SIZE_MB))
    )
    return max_mb, max_mb * 1024 * 1024


def _stat_key(st):
    return (st.st_size, st.st_mtime_ns, st.st_ino)


def _sha256_of_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(CHUNK):
            h.update(chunk)
    return h.hexdigest()


def _read_stable(path):
    """Datei lesen und dabei sicherstellen, dass sie sich waehrend des Lesens nicht geaendert hat
    (stat vor/nach dem Lesen). Rueckgabe: (bytes, stat_key)."""
    for _attempt in range(MAX_STABLE_ATTEMPTS):
        before = _stat_key(os.stat(path))
        with open(path, "rb") as f:
            data = f.read()
        if _stat_key(os.stat(path)) == before:
            return data, before
    raise UserError(_("Die Datei ändert sich ständig, Sicherung nicht möglich."))


def _remove_stale_temps(abs_dir, file_id):
    """Entfernt Temp-Dateien dieses Vorgangs im Zielordner (Rest eines harten Abbruchs zwischen
    Schreiben und os.replace). Bedingungslos - ohne Altersgrenze -, weil nur der Halter der
    Zeilensperre (Phase B) Temp-Dateien dieser Datei anlegt. Nur bei einem Wiederholungslauf
    aufgerufen: der Erstlauf scannt den Ordner nie (bei sehr grossen Ordnern auf CIFS teuer)."""
    prefix = f"{TEMP_PREFIX}{file_id}_"
    try:
        with os.scandir(abs_dir) as it:
            for entry in it:
                if entry.name.startswith(prefix) and entry.is_file(follow_symlinks=False):
                    try:
                        os.remove(entry.path)
                        _logger.info("Verwaiste Temp-Datei entfernt: %s", entry.path)
                    except OSError:
                        pass
    except OSError:
        pass


def _fsync_dir(path):
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _differs_from_index(rec, st):
    """True, wenn der Plattenstand vom zuletzt indexierten Stand abweicht (Herkunft 'extern').
    Solange nicht jeder App-Schreibweg den Index selbst pflegt (Konzept B4), kann das auch ein
    App-Stand sein, den der Watcher noch nicht nachgezogen hat - die Herkunft ist ein Hinweis."""
    if int(st.st_size) != int(rec.size or 0):
        return True
    if not rec.mtime:
        return True
    return abs((datetime.fromtimestamp(st.st_mtime) - rec.mtime).total_seconds()) > EXTERN_MTIME_TOLERANCE_S


def _next_version_no(env, file_id):
    env.cr.execute(
        "SELECT COALESCE(MAX(version_no), 0) + 1 FROM int_filemanager_version WHERE file_id = %s", (file_id,)
    )
    return env.cr.fetchone()[0]


def _is_current(rec, expected_revision):
    return rec.share_state == "pending" and (expected_revision is None or rec.revision == expected_revision)


# --- Request-Teil ----------------------------------------------------------------------------


def stage_overwrite(env, file_record, new_content):
    """Ueberschreiben einer bereits indexierten Datei vormerken. Laeuft in der Request-Transaktion,
    fasst den Share nicht an. Rueckgabe: {"skipped": True} bei unveraendertem Inhalt, sonst
    {"state": "pending", "revision": n, "sha256": ...}."""
    rec = file_record.sudo()
    abs_path = rec._absolute_path()
    max_mb, max_bytes = _max_bytes(env)
    if len(new_content) > max_bytes:
        raise UserError(_("Datei zu groß für automatische Versionierung (Grenze liegt bei %d MB).") % max_mb)
    if os.path.exists(abs_path) and os.path.getsize(abs_path) > max_bytes:
        raise UserError(
            _("Bestehende Datei überschreitet die Versionierungs-Größengrenze (%d MB) - Überschreiben abgelehnt.") % max_mb
        )

    try:
        rec.lock_for_update()
    except LockError:
        raise UserError(_("Diese Datei wird gerade gespeichert. Bitte in wenigen Sekunden erneut versuchen.")) from None
    if rec.share_state == "pending":
        # Ein frueher Vorgang ist noch nicht auf dem Share. Ihn zu ueberschreiben wuerde einen bereits
        # bestaetigten Stand verwerfen - stattdessen ablehnen; der Cron holt den alten Vorgang nach.
        raise UserError(_("Für diese Datei läuft noch ein vorheriger Schreibvorgang. Bitte kurz warten und erneut versuchen."))

    sha = hashlib.sha256(new_content).hexdigest()
    if os.path.isfile(abs_path) and os.path.getsize(abs_path) == len(new_content) and _sha256_of_file(abs_path) == sha:
        # Byteidentisch (Regelfall: Dokument nur geoeffnet) - keine neue Version, kein Vorgang.
        return {"skipped": True, "sha256": sha}

    revision = (rec.revision or 0) + 1
    # Schreiben ueber die ORM: erst die ir.attachment-Zeile, dann der Blob (Reihenfolge des Core;
    # siehe Konzept 4.1 - der GC raeumt Blobs ohne committete Zeile ab).
    rec.with_context(int_filemanager_syncing_index=True).write(
        {
            "pending_content": base64.b64encode(new_content),
            "pending_sha256": sha,
            "pending_version_id": False,
            "revision": revision,
            "share_state": "pending",
        }
    )
    fault_point("stage_before_commit")
    dbname = env.cr.dbname
    file_id = rec.id
    # Zuletzt registrieren; verworfen bei Rollback/Retry. Im Hook den Zustand aus der DB pruefen.
    env.cr.postcommit.add(lambda: publish_after_commit(dbname, file_id, revision))
    return {"state": "pending", "revision": revision, "sha256": sha}


# --- Hook / Cron -----------------------------------------------------------------------------


def publish_after_commit(dbname, file_id, revision):
    """postcommit-Hook: faengt JEDE Ausnahme (sonst 500 trotz Commit), der Zustand bleibt 'pending'."""
    try:
        status = publish_pending(dbname, file_id, expected_revision=revision)
        _logger.debug("publish_after_commit file=%s revision=%s -> %s", file_id, revision, status)
    except Exception:
        _logger.exception(
            "Veroeffentlichen fuer int_filemanager.file %s (Revision %s) fehlgeschlagen - bleibt 'pending', "
            "der Cron holt es nach.",
            file_id,
            revision,
        )


def _phase_a(dbname, file_id, expected_revision, is_retry=False):
    """Sperren, Zustand pruefen, alten Plattenstand als Version sichern. Rueckgabe:
    ("skip", status) | ("published", None) wenn die Platte schon den neuen Stand hat |
    ("replace", (abs_path, new_bytes, snapshot_stat_key_or_None, ist_wiederholung))."""
    with Registry(dbname).cursor() as cr:
        env = Environment(cr, SUPERUSER_ID, {})
        # Sperre als ERSTES Statement dieser Transaktion: der Snapshot entsteht dort und sieht den
        # zuletzt committeten Zustand (Konzept 3, "Snapshot-Test").
        rec = env["int_filemanager.file"].browse(file_id).try_lock_for_update()
        if not rec:
            return "skip", ("locked" if env["int_filemanager.file"].browse(file_id).exists() else "gone")
        if not _is_current(rec, expected_revision):
            return "skip", "noop"
        fault_point("hook_before_snapshot")

        try:
            abs_path = rec._absolute_path()
        except ValidationError:
            # Whatever wrote the row, a path that leaves the root is never published to.
            rec.share_state = "conflict"
            _logger.error("int_filemanager.file %s: path %r leaves the root", rec.id, rec.path)
            return "skip", "conflict"
        pending_sha = rec.pending_sha256
        new_bytes = base64.b64decode(rec.pending_content or b"")
        if hashlib.sha256(new_bytes).hexdigest() != pending_sha:
            # Blob passt nicht zum vorgemerkten Hash: nicht raten, nicht veroeffentlichen.
            rec.share_state = "conflict"
            _logger.error("int_filemanager.file %s: pending_content passt nicht zu pending_sha256", rec.id)
            return "skip", "conflict"

        st = None
        try:
            st = os.stat(abs_path)
        except FileNotFoundError:
            pass  # Datei extern entfernt: die App-Fassung gewinnt und legt sie neu an, keine Sicherung noetig

        if st is not None and st.st_size == len(new_bytes) and _sha256_of_file(abs_path) == pending_sha:
            return "published", None  # Ersetzen war schon erfolgt (Abbruch nach os.replace)

        snapshot_key = None
        # Wiederholung: Cron-Lauf oder ein frueherer Lauf hat schon gesichert (pending_version_id)
        retry = is_retry or bool(rec.pending_version_id)
        if st is not None:
            _max_mb, max_bytes = _max_bytes(env)
            if st.st_size > max_bytes:
                rec.share_state = "conflict"
                _logger.error("int_filemanager.file %s: Plattenstand ueber der Versionsgroessengrenze", rec.id)
                return "skip", "conflict"
            old_bytes, snapshot_key = _read_stable(abs_path)
            old_sha = hashlib.sha256(old_bytes).hexdigest()
            reusable = rec.pending_version_id
            if reusable and reusable.content_sha256 == old_sha:
                pass  # dieselbe Sicherung aus einem frueheren, abgebrochenen Lauf
            else:
                version = env["int_filemanager.version"].create(
                    {
                        "file_id": rec.id,
                        "version_no": _next_version_no(env, rec.id),
                        "content": base64.b64encode(old_bytes),
                        "size": len(old_bytes),
                        "content_sha256": old_sha,
                        "origin": "extern" if _differs_from_index(rec, st) else "app",
                    }
                )
                rec.pending_version_id = version
        return "replace", (abs_path, new_bytes, snapshot_key, retry)
    # commit erfolgt beim Verlassen des with-Blocks


def _replace_on_disk(abs_path, new_bytes, file_id):
    tmp_fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(abs_path), prefix=f"{TEMP_PREFIX}{file_id}_")
    try:
        with os.fdopen(tmp_fd, "wb") as f:
            f.write(new_bytes)
            f.flush()
            os.fsync(f.fileno())
        fault_point("hook_after_temp_written")
        os.replace(tmp_path, abs_path)
    except BaseException:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise
    # os.replace() uebernimmt die Rechte der Temp-Datei (mkstemp: 0600) - fuer Samba wieder freigeben.
    make_shareable(abs_path, is_dir=False)
    _fsync_dir(os.path.dirname(abs_path))


def _phase_b(dbname, file_id, expected_revision, abs_path, new_bytes, snapshot_key, retry, already_replaced):
    """Ersetzen und Abschliessen unter EINER Zeilensperre: dieselbe Transaktion haelt die Sperre, bis
    Datei ersetzt, Index nachgezogen und share_state='synced' committet ist. Wer die Sperre hat, ist
    der einzige Schreiber dieser Datei (andere App-Schreibvorgaenge bekommen sofort LockError, der
    Cron ueberspringt sie). Rueckgabe: 'published' | 'locked' | 'noop' | 'conflict' |
    'resnapshot' (Datei hat sich seit der Sicherung geaendert -> Phase A erneut)."""
    with Registry(dbname).cursor() as cr:
        env = Environment(cr, SUPERUSER_ID, {})
        rec = env["int_filemanager.file"].browse(file_id).try_lock_for_update()
        if not rec:
            return "locked"  # ein anderer Lauf schliesst gerade ab (oder Zeile geloescht) - Cron holt nach
        if not _is_current(rec, expected_revision):
            return "noop"
        if not already_replaced and rec.pending_sha256 != hashlib.sha256(new_bytes).hexdigest():
            return "noop"  # ein neuerer Vorgang hat den Inhalt ausgetauscht
        with suppress_watcher(abs_path):
            if not already_replaced:
                # stat direkt vor dem Austausch (Konzept 4.1): hat sich die Datei seit der Sicherung
                # geaendert (oder ist sie neu aufgetaucht), wird ERST der neue Stand gesichert.
                try:
                    current = _stat_key(os.stat(abs_path))
                except FileNotFoundError:
                    current = None
                if current != snapshot_key:
                    return "resnapshot"
                if retry:
                    _remove_stale_temps(os.path.dirname(abs_path), file_id)
                _replace_on_disk(abs_path, new_bytes, file_id)
                fault_point("hook_after_replace")
            index_upsert(env, abs_path)
            rec.with_context(int_filemanager_syncing_index=True).write(
                {
                    "share_state": "synced",
                    "pending_content": False,
                    "pending_sha256": False,
                    "pending_version_id": False,
                }
            )
            fault_point("hook_before_finalize_commit")
        return "published"


def publish_pending(dbname, file_id, expected_revision=None, is_retry=False):
    """Einen vorgemerkten Inhalt auf den Share veroeffentlichen. Idempotent und einzeln aufrufbar
    (Hook, Cron, Tests). Rueckgabe: 'published' | 'locked' | 'gone' | 'noop' | 'conflict'."""
    for _attempt in range(MAX_STABLE_ATTEMPTS):
        action, payload = _phase_a(dbname, file_id, expected_revision, is_retry)
        if action == "skip":
            return payload
        if action == "published":
            abs_path = _abs_path_of(dbname, file_id)
            status = _phase_b(dbname, file_id, expected_revision, abs_path, b"", None, False, True)
        else:
            abs_path, new_bytes, snapshot_key, retry = payload
            fault_point("hook_after_snapshot_commit")
            status = _phase_b(dbname, file_id, expected_revision, abs_path, new_bytes, snapshot_key, retry, False)
        if status != "resnapshot":
            return status
    raise UserError(_("Die Datei ändert sich ständig, Veröffentlichen nicht möglich."))


def _abs_path_of(dbname, file_id):
    with Registry(dbname).cursor() as cr:
        env = Environment(cr, SUPERUSER_ID, {})
        return env["int_filemanager.file"].browse(file_id)._absolute_path()


def publish_all_pending(env, min_age_seconds=30, limit=50):
    """Cron-Einstieg: pending-Zeilen nachholen, die nicht mehr frisch sind (ein gerade laufender Hook
    soll nicht gedoppelt werden). Ein Fehler bei einer Datei stoppt die anderen nicht."""
    cutoff = datetime.utcnow().replace(microsecond=0) - timedelta(seconds=min_age_seconds)
    recs = env["int_filemanager.file"].sudo().search(
        [("share_state", "=", "pending"), ("write_date", "<=", cutoff)], limit=limit, order="write_date"
    )
    dbname = env.cr.dbname
    results = {}
    for rec_id in recs.ids:
        try:
            results[rec_id] = publish_pending(dbname, rec_id, is_retry=True)
        except Exception:
            _logger.exception("Cron: Veroeffentlichen fuer int_filemanager.file %s fehlgeschlagen", rec_id)
            results[rec_id] = "error"
    return results
