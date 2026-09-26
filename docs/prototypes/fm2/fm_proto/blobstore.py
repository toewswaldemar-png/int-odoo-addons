"""Prototyp Blob-Speicher (int_filemanager 2, Konzept Abschnitt 5). Inhaltsadressiert, unveraenderlich.

Ablage:   <root>/<sha[0:2]>/<sha[2:4]>/<sha>
Temp:     <root>/tmp/<name>            (selbes Dateisystem, damit link() ohne Kopie geht)
Checkliste fuer den Aufraeumjob: <root>/checklist/<sha>  (Muster ir.attachment._mark_for_gc)
"""
import hashlib
import logging
import os

from odoo.tools import config

_logger = logging.getLogger(__name__)
CHUNK = 1024 * 1024
EMPTY_SHA = hashlib.sha256(b"").hexdigest()
FAULT_FILE = os.environ.get("FM_PROTO_FAULT_FILE", "")


def fault(stage):
    """Fehlerinjektion fuer Tests: Datei enthaelt '<stufe>' oder '<stufe>:exit'."""
    if not FAULT_FILE or not os.path.exists(FAULT_FILE):
        return
    spec = open(FAULT_FILE).read().strip()
    name, _sep, mode = spec.partition(":")
    if name == stage:
        if mode == "exit":
            os._exit(137)
        raise RuntimeError("Fehlerinjektion an Stufe %s" % stage)


def root(env):
    return os.path.join(config.filestore(env.cr.dbname), "fm")


def blob_path(env, sha):
    return os.path.join(root(env), sha[0:2], sha[2:4], sha)


def tmp_dir(env):
    d = os.path.join(root(env), "tmp")
    os.makedirs(d, exist_ok=True)
    return d


def _fsync_dir(path):
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def mark_for_gc(env, sha):
    d = os.path.join(root(env), "checklist")
    os.makedirs(d, exist_ok=True)
    open(os.path.join(d, sha), "ab").close()


def hash_file(path):
    h = hashlib.sha256()
    size = 0
    with open(path, "rb") as f:
        while chunk := f.read(CHUNK):
            h.update(chunk)
            size += len(chunk)
    return h.hexdigest(), size


def adopt_temp(env, tmp_path, keep_tmp=False):
    """Temp-Datei als Blob uebernehmen. Gibt (sha, size, deduped) zurueck. Wird VOR dem Commit aufgerufen:
    die Datei liegt danach unveraenderlich unter ihrem Hash, ein Abbruch hinterlaesst hoechstens einen
    unreferenzierten Blob (steht in der Checkliste, der Aufraeumjob entfernt ihn)."""
    with open(tmp_path, "rb+") as f:
        os.fsync(f.fileno())
    sha, size = hash_file(tmp_path)
    final = blob_path(env, sha)
    os.makedirs(os.path.dirname(final), exist_ok=True)
    mark_for_gc(env, sha)
    fault("before_link")
    try:
        os.link(tmp_path, final)          # scheitert, wenn schon vorhanden: kein Ueberschreiben (I2)
        deduped = False
    except FileExistsError:
        deduped = True
    if not keep_tmp:
        os.unlink(tmp_path)
    _fsync_dir(os.path.dirname(final))
    fault("after_link")
    return sha, size, deduped


def write_stream_to_temp(env, stream, name):
    """Liest einen Datei-Stream in eine Temp-Datei (fuer Import und einfache Uploads)."""
    tmp_path = os.path.join(tmp_dir(env), name)
    with open(tmp_path, "wb") as out:
        while chunk := stream.read(CHUNK):
            out.write(chunk)
    return tmp_path


def ensure_empty_blob(env):
    """Blob fuer leeren Inhalt (Datei auf 0 Bytes gekuerzt)."""
    final = blob_path(env, EMPTY_SHA)
    if not os.path.exists(final):
        tmp = os.path.join(tmp_dir(env), "empty_%d" % os.getpid())
        open(tmp, "wb").close()
        adopt_temp(env, tmp)


def adopt_hashed(env, tmp_path, sha, size):
    """Wie adopt_temp, aber mit dem beim Empfang berechneten Hash (19.6): kein erneutes Lesen. Odoo hat den Hash
    selbst berechnet, I2 bleibt erfuellt. Die Temp-Datei wurde vom Schreiber bereits mit fsync geschrieben."""
    final = blob_path(env, sha)
    os.makedirs(os.path.dirname(final), exist_ok=True)
    mark_for_gc(env, sha)
    try:
        os.link(tmp_path, final)          # kein Ueberschreiben (I2)
        deduped = False
    except FileExistsError:
        deduped = True
    _fsync_dir(os.path.dirname(final))
    return sha, size, deduped
