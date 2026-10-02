import logging
import os
from datetime import timedelta

import psycopg2

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools import SQL

from .. import blobstore

_logger = logging.getLogger(__name__)

# Above this size finish_upload() hands the upload to a cron: hashing a large
# file (about a minute for 3 GB) takes too long for one request.
DEFAULT_LARGE_FILE_THRESHOLD_MB = 256
LARGE_FILE_THRESHOLD_PARAM = "int_filemanager.upload_large_file_threshold_mb"
# Unfinished uploads are removed after this time.
DEFAULT_EXPIRY_HOURS = 24
EXPIRY_PARAM = "int_filemanager.upload_expiry_hours"


def _remove_if_exists(path):
    try:
        os.remove(path)
    except OSError:
        _logger.warning("could not remove upload temp file %s", path, exc_info=True)


class IntFilemanagerUpload(models.Model):
    """A chunked upload in progress.

    Lives across the requests of one upload (init, chunks, finish), so each of
    them can be retried or resumed without losing what was already received.
    """

    _name = "int_filemanager.upload"
    _description = "Filemanager v2 chunked upload in progress"

    # One upload per operation key, so a repeated request finds the same row.
    operation_id = fields.Many2one(
        "int_filemanager.operation", required=True, index=True
    )
    # Either a new file (target_parent_id + target_name) or a new revision of an
    # existing one (target_node_id).
    target_parent_id = fields.Many2one(
        "int_filemanager.node", index=True, ondelete="cascade"
    )
    target_name = fields.Char()
    target_node_id = fields.Many2one(
        "int_filemanager.node", index=True, ondelete="cascade"
    )
    # With target_node_id: the revision the client started from (conflict check).
    base_revision_id = fields.Many2one("int_filemanager.revision", index=True)
    # Optional: the client may not know the size upfront. Float, not Integer: an
    # int4 column overflows above 2 GiB.
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
    # Outcome for the client (node and revision ids, hash) or why it failed; an
    # upload finished by the cron has no request left to return it in.
    result = fields.Json()
    error = fields.Char()

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
        """Start a chunked upload.

        The target is either a new file (``target_parent_id`` and ``target_name``)
        or a new revision of ``target_node_id`` based on ``base_revision_id``.
        """
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

        # Users cannot write uploads themselves (temp_file is a server path); the
        # target rights were checked above.
        upload = self.sudo().create(vals)
        result = {"upload_id": upload.id}
        operation.write({"result": result})
        return result

    @api.model
    def upload_chunk(self, upload_id, offset, data):
        """Append ``data`` at ``offset`` to the upload.

        A chunk already received is ignored, so a retry is harmless; a chunk
        that leaves a gap is rejected. The upload row is locked, so two chunks
        of the same upload cannot interleave.
        """
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
        # The rule limits uploads to their owner, so reading one proves ownership.
        upload.check_access("read")

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
            upload.sudo().write({"temp_file": temp_path})

        with open(temp_path, "ab") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())

        upload.sudo().write({"received_size": offset + len(data)})
        return {"received_size": upload.received_size}

    @api.model
    def upload_status(self, upload_id):
        """Return the upload's progress and outcome, to resume or poll it."""
        upload = self.browse(upload_id).exists()
        if not upload:
            raise UserError(self.env._("This upload does not exist any more."))
        upload.check_access("read")
        return {
            "upload_id": upload.id,
            "state": upload.state,
            "received_size": upload.received_size,
            "expected_size": upload.expected_size,
            "result": upload.result,
            "error": upload.error,
        }

    @api.model
    def cancel_upload(self, upload_id):
        """Cancel the upload and remove its partial temp file right away."""
        upload = self.browse(upload_id).exists()
        if not upload:
            return True
        upload.check_access("read")
        if upload.state == "processing":
            raise UserError(
                self.env._(
                    "This upload is already being processed; it cannot be cancelled."
                )
            )
        temp_file = upload.temp_file
        upload.sudo().unlink()
        if temp_file:
            self.env.cr.postcommit.add(lambda: _remove_if_exists(temp_file))
        return True

    @api.model
    def finish_upload(self, upload_id, operation_key, target_name=None):
        """Turn the received data into a file or a new revision.

        Large uploads are handed to a cron; the client then polls upload_status().
        ``target_name`` retries under another name after a name conflict,
        without sending the data again.
        """
        operation, is_new = self.env["int_filemanager.operation"]._get_or_create(
            operation_key
        )
        if not is_new:
            return operation.result

        upload = self.browse(upload_id)
        upload.check_access("read")
        if upload.state != "open":
            raise UserError(self.env._("This upload is not open."))
        if not upload.temp_file:
            raise UserError(self.env._("This upload has not received any data yet."))
        if target_name and upload.target_parent_id:
            upload.sudo().write({"target_name": target_name})

        if upload.received_size > self._large_file_threshold_bytes():
            upload.sudo().write({"state": "processing"})
            result = {"upload_id": upload.id, "state": "processing"}
            operation.write({"result": result})
            return result

        result = self._finish_now(upload, operation)
        operation.write({"result": result})
        return result

    def _finish_now(self, upload, operation):
        """Store the upload's data as a blob and attach it to its target node."""
        sha256, size = blobstore.hash_file(upload.temp_file)
        blobstore.adopt_hashed(self.env, upload.temp_file, sha256, keep_tmp=True)
        blob = self.env["int_filemanager.blob"].sudo()._get_or_create(sha256, size)
        blobstore.ensure_on_disk(self.env, sha256, upload.temp_file)

        Node = self.env["int_filemanager.node"]
        if upload.target_node_id:
            node = upload.target_node_id
            # Rights can change between init and finish (an upload may take hours).
            node.check_access("write")
            current = Node._lock_and_check_base_revision(
                node, upload.base_revision_id.id or False
            )
            attach_result = Node._attach_revision(
                node, current, blob.id, size, "upload", operation
            )
        else:
            try:
                with self.env.cr.savepoint():
                    new_node = Node._create_below(
                        upload.target_parent_id,
                        {"name": upload.target_name, "is_dir": False},
                    )
            except psycopg2.errors.UniqueViolation:
                # No state change: the request is rolled back anyway. The upload
                # stays open, so the client can finish it under another name.
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

        attach_result["sha256"] = sha256
        upload.sudo().write({"state": "done", "result": attach_result, "error": False})
        self.env.cr.postcommit.add(lambda: _remove_if_exists(upload.temp_file))
        return attach_result

    @api.model
    def _cron_finish_pending(self):
        """Finish the uploads that were too large to finish in their request.

        One at a time with a commit after each, so one bad upload does not
        block the others. Tests call _finish_pending_one() directly, because
        the test cursor does not allow the commit.
        """
        pending = self.search([("state", "=", "processing")], limit=20)
        for upload in pending:
            self._finish_pending_one(upload)
            # Commit per upload, so a later failure does not undo the earlier ones.
            self.env["ir.cron"]._commit_progress(processed=1)

    def _finish_pending_one(self, upload):
        """Finish one upload with the uploader's rights, not the cron's.

        Whoever may no longer write there gets a failed upload, not a file.
        """
        as_uploader = upload.with_user(upload.create_uid)
        try:
            with self.env.cr.savepoint():
                as_uploader._finish_now(as_uploader, upload.operation_id)
        except (UserError, AccessError) as exc:
            upload.sudo().write({"state": "failed", "error": str(exc)})
        except Exception:
            _logger.exception("failed to finish upload %s", upload.id)
            upload.sudo().write(
                {"state": "failed", "error": self.env._("Internal error.")}
            )

    @api.model
    def _cron_expire_orphaned_uploads(self):
        """Remove expired unfinished or failed uploads and their temp files."""
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
