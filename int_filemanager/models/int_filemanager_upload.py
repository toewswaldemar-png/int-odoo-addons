import logging
import os
from datetime import timedelta

import psycopg2

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools import SQL

from .. import blobstore

_logger = logging.getLogger(__name__)

# Konzept 7: "ab einer Grenze (z. B. 256 MB) setzt finish den Upload auf
# 'processing'" - re-hashing a huge file (19.1: ~51-56s for 3 GB) is too slow
# for one request.
DEFAULT_LARGE_FILE_THRESHOLD_MB = 256
LARGE_FILE_THRESHOLD_PARAM = "int_filemanager.upload_large_file_threshold_mb"
# Konzept 7 "Verwaiste Uploads raeumt ein Cron nach Ablauf auf" - no exact
# number given there; matches the blob GC's own grace-period order of size.
DEFAULT_EXPIRY_HOURS = 24
EXPIRY_PARAM = "int_filemanager.upload_expiry_hours"


def _remove_if_exists(path):
    try:
        os.remove(path)
    except OSError:
        _logger.warning("could not remove upload temp file %s", path, exc_info=True)


class IntFilemanagerUpload(models.Model):
    """An in-progress chunked upload (Konzept 6/7): survives across the
    several requests one upload takes (init/chunk/finish) so any of them can
    be retried or resumed without losing what was already received."""

    _name = "int_filemanager.upload"
    _description = "Filemanager v2 chunked upload in progress"

    # One upload per idempotency key (Konzept 4 "operation_id (eindeutig)"): a repeated
    # chunk/finish request for the same key must find this same row, not create another.
    operation_id = fields.Many2one(
        "int_filemanager.operation", required=True, index=True
    )
    # Exactly one of the two is set: a new file (target_parent_id + target_name) or
    # a new revision of an existing one (target_node_id) - Konzept 6 "Hochladen (neu)"
    # / "Neue Fassung".
    target_parent_id = fields.Many2one(
        "int_filemanager.node", index=True, ondelete="cascade"
    )
    target_name = fields.Char()
    target_node_id = fields.Many2one(
        "int_filemanager.node", index=True, ondelete="cascade"
    )
    # Only meaningful with target_node_id: the same I6 base-revision protection a
    # single-request create_new_revision() already has (Konzept 6).
    base_revision_id = fields.Many2one("int_filemanager.revision", index=True)
    # Float and nullable: the client may not know the size upfront (Konzept 7), and
    # Float avoids the int4 ceiling (19.2) other size fields in this module work around.
    expected_size = fields.Float()
    received_size = fields.Float(default=0.0)
    temp_file = fields.Char()
    state = fields.Selection(
        [
            ("open", "Open"),
            ("processing", "Processing"),
            ("done", "Done"),
            ("failed", "Failed"),
        ],
        default="open",
        required=True,
    )
    expires_at = fields.Datetime()

    _operation_id_uniq = models.Constraint(
        "UNIQUE(operation_id)", "This operation already has an upload in progress."
    )

    def _large_file_threshold_bytes(self):
        mb = int(
            self.env["ir.config_parameter"]
            .sudo()
            .get_param(LARGE_FILE_THRESHOLD_PARAM, DEFAULT_LARGE_FILE_THRESHOLD_MB)
        )
        return mb * 1024 * 1024

    def _expiry_hours(self):
        return int(
            self.env["ir.config_parameter"]
            .sudo()
            .get_param(EXPIRY_PARAM, DEFAULT_EXPIRY_HOURS)
        )

    @api.model
    def init_upload(
        self,
        target_parent_id,
        target_name,
        target_node_id,
        base_revision_id,
        expected_size,
        operation_key,
    ):
        """Konzept 7 "init": Vorgangs-ID, Groesse, Ziel. Exactly one target
        shape - a new file (parent + name) or a new revision of an existing
        one (node + its base revision, same I6 protection a single-request
        create_new_revision() already has)."""
        operation, is_new = self.env["int_filemanager.operation"]._get_or_create(
            operation_key
        )
        if not is_new:
            return operation.result

        if bool(target_node_id) == bool(target_parent_id and target_name):
            raise UserError(
                self.env._(
                    "Specify either a target folder and name for a new file,"
                    " or an existing file to revise - not both."
                )
            )

        Node = self.env["int_filemanager.node"]
        vals = {
            "operation_id": operation.id,
            "expected_size": expected_size or False,
            "expires_at": fields.Datetime.now() + timedelta(hours=self._expiry_hours()),
        }
        if target_node_id:
            node = Node.browse(target_node_id)
            node.check_access("write")
            vals["target_node_id"] = target_node_id
            vals["base_revision_id"] = base_revision_id or False
        else:
            parent = Node.browse(target_parent_id)
            parent.check_access("write")
            vals["target_parent_id"] = target_parent_id
            vals["target_name"] = target_name

        upload = self.create(vals)
        result = {"upload_id": upload.id}
        operation.write({"result": result})
        return result

    @api.model
    def upload_chunk(self, upload_id, offset, data):
        """Konzept 7 "chunk": append at the exact next offset. A chunk that
        repeats one already received is a no-op (idempotent retry, Konzept
        19.1); a chunk with a gap is rejected rather than silently accepted
        out of order. Locked the same way as any other multi-request write
        (Konzept 6) - two chunks for the same upload must not race."""
        data = blobstore.decode_content(data)
        upload = self.browse(upload_id)
        cr = self.env.cr
        cr.execute("SET LOCAL lock_timeout TO '5s'")
        cr.execute(
            SQL(
                "SELECT id FROM int_filemanager_upload WHERE id = %s FOR UPDATE",
                upload_id,
            )
        )
        upload.invalidate_recordset(["received_size", "temp_file", "state"])
        upload.check_access("write")

        if upload.state != "open":
            raise UserError(self.env._("This upload is not open for more chunks."))
        if offset > upload.received_size:
            raise UserError(
                self.env._("This chunk does not continue where the upload left off.")
            )
        if offset < upload.received_size:
            return {"received_size": upload.received_size}

        temp_path = upload.temp_file
        if not temp_path:
            temp_path = os.path.join(
                blobstore.tmp_dir(self.env), f"upload_{upload.operation_id.id}"
            )
            upload.write({"temp_file": temp_path})

        with open(temp_path, "ab") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())

        upload.write({"received_size": offset + len(data)})
        return {"received_size": upload.received_size}

    @api.model
    def finish_upload(self, upload_id, operation_key):
        """Konzept 7 "finish": hash the received temp file, then attach it
        the same way a single-request write would - unless it is large
        enough that doing so now would hold this request open too long, in
        which case a cron finishes it instead and the caller polls
        upload.state."""
        operation, is_new = self.env["int_filemanager.operation"]._get_or_create(
            operation_key
        )
        if not is_new:
            return operation.result

        upload = self.browse(upload_id)
        upload.check_access("write")
        if upload.state != "open":
            raise UserError(self.env._("This upload is not open."))
        if not upload.temp_file:
            raise UserError(self.env._("This upload has not received any data yet."))

        if upload.received_size > self._large_file_threshold_bytes():
            upload.write({"state": "processing"})
            result = {"upload_id": upload.id, "state": "processing"}
            operation.write({"result": result})
            return result

        result = self._finish_now(upload, operation)
        operation.write({"result": result})
        return result

    def _finish_now(self, upload, operation):
        """The actual attach step, shared by finish_upload's synchronous
        path and _cron_finish_pending's asynchronous one. Runs as the
        recordset's own user (never sudo on the node/revision side, only
        the blob side - I7, same as create_file/create_new_revision)."""
        sha256, size = blobstore.hash_file(upload.temp_file)
        blobstore.adopt_hashed(self.env, upload.temp_file, sha256, keep_tmp=True)
        blob = self.env["int_filemanager.blob"].sudo()._get_or_create(sha256, size)
        blobstore.ensure_on_disk(self.env, sha256, upload.temp_file)

        Node = self.env["int_filemanager.node"]
        if upload.target_node_id:
            node = upload.target_node_id
            current = Node._lock_and_check_base_revision(
                node, upload.base_revision_id.id or False
            )
            attach_result = Node._attach_revision(
                node, current, blob.id, size, "upload", operation
            )
        else:
            try:
                with self.env.cr.savepoint():
                    new_node = Node.with_context(mail_create_nolog=True).create(
                        {
                            "name": upload.target_name,
                            "parent_id": upload.target_parent_id.id,
                            "scope_id": upload.target_parent_id.scope_id.id,
                            "is_dir": False,
                        }
                    )
            except psycopg2.errors.UniqueViolation:
                # Not upload.write({"state": "failed"}): a real request that raises
                # rolls back its whole transaction (Odoo's own dispatch layer does
                # this - odoo.tests.common._assertRaises models it faithfully, which
                # is how this was actually found), so a write made right before this
                # raise would never persist anyway. The upload stays "open" with its
                # bytes intact - the client can finish it again once the name is
                # free, and the orphan-expiry cron is the fallback if it never does.
                raise UserError(
                    self.env._(
                        "A file or folder named %(name)s already exists here.",
                        name=upload.target_name,
                    )
                ) from None
            Node._touch_active_parent(upload.target_parent_id)
            attach_result = Node._attach_revision(
                new_node, None, blob.id, size, "upload", operation
            )

        upload.write({"state": "done"})
        attach_result["sha256"] = sha256
        self.env.cr.postcommit.add(lambda: _remove_if_exists(upload.temp_file))
        return attach_result

    @api.model
    def _cron_finish_pending(self):
        """Konzept 7: uploads finish_upload marked 'processing' because they
        were too large to hash within that request get attached here
        instead, one at a time so a single bad upload cannot block the
        others behind it. Split from _finish_pending_one the same way
        int_filemanager.blob splits _gc_blobs/_gc_blobs_unsafe: tests call
        the latter directly, since TestCursor forbids the per-item commit
        here (Odoo's own test framework, not just TransactionCase's
        isolation convention)."""
        pending = self.search([("state", "=", "processing")], limit=20)
        for upload in pending:
            self._finish_pending_one(upload)
            # Odoo's own per-item progress commit (v1 precedent: filemanager_file.py
            # _cron_compute_hashes) instead of a raw cr.commit() - one bad upload must
            # not roll back the ones already finished earlier in this same run.
            self.env["ir.cron"]._commit_progress(processed=1)

    def _finish_pending_one(self, upload):
        try:
            self._finish_now(upload, upload.operation_id)
        except Exception:
            _logger.exception("failed to finish upload %s", upload.id)
            upload.write({"state": "failed"})

    @api.model
    def _cron_expire_orphaned_uploads(self):
        """Konzept 7 "Verwaiste Uploads raeumt ein Cron nach Ablauf auf": an
        upload nobody ever finished (or that failed) past its expiry is
        removed, along with whatever partial temp file it left behind."""
        expired = self.search(
            [
                ("state", "in", ["open", "failed"]),
                ("expires_at", "<", fields.Datetime.now()),
            ]
        )
        for upload in expired:
            if upload.temp_file:
                _remove_if_exists(upload.temp_file)
        expired.unlink()
