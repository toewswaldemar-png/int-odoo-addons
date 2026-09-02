"""Zentraler Snapshot-/Schreibdienst für alle drei Auslöser, die eine
bestehende Filemanager-Datei überschreiben: ONLYOFFICE-Sync
(models/ir_attachment.py), Upload-Überschreiben und Version-Restore (beide
controllers/main.py). Ein Ort statt drei leicht unterschiedlicher
Implementierungen - sichert den alten Inhalt als Version und schreibt den
neuen Inhalt atomar (Temp-Datei + os.replace), unter einer session-weiten
PostgreSQL-Advisory-Sperre über den GESAMTEN Ablauf. Eine transaktions-
gebundene Sperre (pg_advisory_xact_lock) würde bereits beim Commit des
Snapshot-Schritts wieder freigegeben, lange bevor der eigentliche
Schreibvorgang fertig ist - zwei gleichzeitige Schreibvorgänge auf dieselbe
Datei könnten sich sonst gegenseitig eine Zwischenversion wegschreiben.

Ruft absichtlich KEIN index_upsert() nach dem Schreiben auf: der Watcher
beobachtet den ganzen Baum per inotify und aktualisiert den Index selbst,
sobald der echte Dateisystem-MODIFY passiert - ein zusätzlicher direkter
Aufruf hier würde exakt das Race auslösen, das bereits im bestehenden
Kommentar in ir_attachment.py dokumentiert ist (überlappende Transaktionen
auf dieselbe int_filemanager.file-Zeile, von Postgres mit "could not
serialize access due to concurrent update" abgelehnt)."""

import base64
import hashlib
import logging
import os
import tempfile
from contextlib import contextmanager

import psycopg2

from odoo import _
from odoo.api import SUPERUSER_ID, Environment
from odoo.exceptions import UserError
from odoo.fields import Datetime
from odoo.modules.registry import Registry
from odoo.tools import config

from .path_utils import get_root, make_shareable

_logger = logging.getLogger(__name__)

DEFAULT_VERSION_MAX_SIZE_MB = 200


def _raw_connect(dbname):
    """Eigene, dedizierte psycopg2-Verbindung außerhalb von Odoos
    Connection-Pool - ein Session-Advisory-Lock auf einer gepoolten
    Verbindung würde beim Zurückgeben an den Pool nicht automatisch
    freigegeben und könnte unabsichtlich einen späteren, völlig unabhängigen
    Request blockieren."""
    return psycopg2.connect(
        dbname=dbname,
        host=config.get("db_host") or None,
        port=config.get("db_port") or None,
        user=config.get("db_user") or None,
        password=config.get("db_password") or None,
    )


@contextmanager
def _file_write_lock(dbname, file_id):
    conn = _raw_connect(dbname)
    conn.autocommit = True
    cur = conn.cursor()
    try:
        cur.execute("SELECT pg_advisory_lock(%s)", (file_id,))
        yield
    finally:
        try:
            cur.execute("SELECT pg_advisory_unlock(%s)", (file_id,))
        finally:
            cur.close()
            conn.close()


def _run_own_cursor(dbname, fn):
    """Frischer Cursor/Env, fn(env) ausführen, committen, schließen - exakt
    das etablierte Muster aus watcher.py._run() für Schreibvorgänge
    außerhalb der Haupt-Request-Transaktion (kein env.cr.commit() mitten in
    einem Controller)."""
    reg = Registry(dbname)
    with reg.cursor() as cr:
        env = Environment(cr, SUPERUSER_ID, {})
        result = fn(env)
        cr.commit()
        return result


def _next_version_no(env, file_id):
    env.cr.execute(
        "SELECT COALESCE(MAX(version_no), 0) + 1 FROM int_filemanager_version WHERE file_id = %s",
        (file_id,),
    )
    return env.cr.fetchone()[0]


def snapshot_and_write(env, file_record, new_content, *, operation):
    """new_content: rohe Bytes des neuen Dateiinhalts. Sichert den
    vorherigen Inhalt als Version (falls die Datei bereits existiert und
    innerhalb der Größengrenze liegt) und schreibt den neuen Inhalt atomar.

    Lehnt das Überschreiben komplett ab (UserError), wenn bestehender oder
    neuer Inhalt die konfigurierte Versionierungs-Größengrenze überschreitet
    - kein stilles Überschreiben ohne Sicherung, insbesondere für den
    ONLYOFFICE-Pfad, wo es keinen sinnvollen Bestätigungsdialog dafür gibt."""
    root = get_root(env)
    abs_path = os.path.join(root, file_record.path)
    dbname = env.cr.dbname

    max_mb = int(
        env["ir.config_parameter"].sudo().get_param(
            "int_filemanager.version_max_size_mb", str(DEFAULT_VERSION_MAX_SIZE_MB)
        )
    )
    max_bytes = max_mb * 1024 * 1024
    if len(new_content) > max_bytes:
        raise UserError(_("Datei zu groß für automatische Versionierung (Grenze liegt bei %d MB).") % max_mb)
    if os.path.exists(abs_path) and os.path.getsize(abs_path) > max_bytes:
        raise UserError(
            _("Bestehende Datei überschreitet die Versionierungs-Größengrenze (%d MB) - Überschreiben abgelehnt.")
            % max_mb
        )

    with _file_write_lock(dbname, file_record.id):
        return _do_snapshot_and_write(dbname, file_record, abs_path, new_content, operation)


def _do_snapshot_and_write(dbname, file_record, abs_path, new_content, operation):
    file_id = file_record.id
    started_at = Datetime.now()

    journal_id = _run_own_cursor(
        dbname,
        lambda jenv: jenv["int_filemanager.write_journal"]
        .sudo()
        .create({"file_id": file_id, "operation": operation, "stage": "created", "started_at": started_at})
        .id,
    )

    def _update_journal(**vals):
        _run_own_cursor(
            dbname,
            lambda jenv: jenv["int_filemanager.write_journal"].sudo().browse(journal_id).write(vals),
        )

    try:
        old_content = None
        if os.path.exists(abs_path):
            with open(abs_path, "rb") as f:
                old_content = f.read()

        version_id = None
        old_sha256 = None
        if old_content is not None:
            old_sha256 = hashlib.sha256(old_content).hexdigest()

            def _create_version(jenv, _old_content=old_content, _old_sha256=old_sha256):
                version_no = _next_version_no(jenv, file_id)
                return (
                    jenv["int_filemanager.version"]
                    .sudo()
                    .create(
                        {
                            "file_id": file_id,
                            "version_no": version_no,
                            "content": base64.b64encode(_old_content),
                            "size": len(_old_content),
                            "content_sha256": _old_sha256,
                        }
                    )
                    .id
                )

            version_id = _run_own_cursor(dbname, _create_version)
        _update_journal(stage="snapshot_committed", version_id=version_id, old_sha256=old_sha256)

        new_sha256 = hashlib.sha256(new_content).hexdigest()
        tmp_fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(abs_path), prefix=".int_filemanager_tmp_")
        try:
            with os.fdopen(tmp_fd, "wb") as f:
                f.write(new_content)
                f.flush()
                os.fsync(f.fileno())
            _update_journal(stage="temp_synced", temp_path=tmp_path, new_sha256=new_sha256)

            os.replace(tmp_path, abs_path)
        except Exception:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise
        # os.replace() uebernimmt die Rechte der Temp-Datei (mkstemp: 0600) -
        # ohne diesen Fix waere die Datei fuer die Samba-Freigabe nicht mehr
        # beschreibbar, siehe path_utils.make_shareable().
        make_shareable(abs_path, is_dir=False)
        _update_journal(stage="replaced")

        _update_journal(stage="done", finished_at=Datetime.now())
        return {"version_id": version_id, "new_sha256": new_sha256}
    except Exception as exc:
        _update_journal(stage="failed", error=str(exc), finished_at=Datetime.now())
        raise
