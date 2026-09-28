import logging
import os
import uuid
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError

from .. import zip_stream

_logger = logging.getLogger(__name__)

# A finished archive is kept this long, then removed with its row.
DEFAULT_KEEP_HOURS = 24


def _remove_if_exists(path):
    try:
        os.remove(path)
    except OSError:
        # A file that is already gone is the goal, not an error.
        if os.path.exists(path):
            _logger.warning("could not remove zip file %s", path, exc_info=True)


class IntFilemanagerZipJob(models.Model):
    """A large ZIP download, packed in the background.

    A cron packs the selection with the requester's rights and notifies the
    requester over the bus when it is ready.
    """

    _name = "int_filemanager.zip_job"
    _description = "Filemanager v2 ZIP download job"
    _order = "id desc"

    name = fields.Char(required=True)
    node_ids_json = fields.Json(required=True)
    state = fields.Selection(
        [
            ("pending", "Pending"),
            ("processing", "Processing"),
            ("done", "Done"),
            ("failed", "Failed"),
        ],
        default="pending",
        required=True,
        index=True,
    )
    size = fields.Float()
    file_name = fields.Char()
    error = fields.Char()
    expires_at = fields.Datetime(index=True)

    def _path(self):
        return os.path.join(zip_stream.zips_dir(self.env), self.file_name)

    @api.model
    def request_zip(self, node_ids, operation_key):
        """Return a direct download URL for a small selection, or start a job.

        For a job the caller waits for the bus message or polls zip_job_status().
        """
        operation, is_new = self.env["int_filemanager.operation"]._get_or_create(
            operation_key
        )
        if not is_new:
            return operation.result

        _entries, total, name = zip_stream.collect_entries(self.env, node_ids)
        if total <= zip_stream.direct_max_bytes(self.env):
            ids = ",".join(str(i) for i in node_ids)
            result = {"mode": "direct", "url": f"/int_filemanager/v2/zip?ids={ids}"}
        else:
            # sudo() keeps the requester as create_uid (the job is built and downloaded
            # as that user); the rights were checked by collect_entries above. Users
            # get read access only - a writable file_name would be a path to any file.
            job = self.sudo().create({"name": name, "node_ids_json": list(node_ids)})
            result = {"mode": "job", "job_id": job.id, "size": total}
        operation.write({"result": result})
        return result

    @api.model
    def zip_job_status(self, job_id):
        job = self.browse(job_id).exists()
        if not job:
            raise UserError(self.env._("This download does not exist any more."))
        job.check_access("read")
        return {
            "job_id": job.id,
            "state": job.state,
            "name": job.name,
            "size": job.size,
            "error": job.error,
            "url": f"/int_filemanager/v2/zip/job/{job.id}"
            if job.state == "done"
            else None,
        }

    @api.model
    def _cron_build_zips(self):
        """Build pending ZIPs, committing after each so one failure blocks nothing."""
        for job in self.search([("state", "=", "pending")], limit=5):
            self._build_one(job)
            self.env["ir.cron"]._commit_progress(processed=1)

    def _build_one(self, job):
        """Pack one job with the requester's rights, not the cron's."""
        as_user = job.with_user(job.create_uid)
        tmp_path = None
        try:
            with self.env.cr.savepoint():
                entries, total, _name = zip_stream.collect_entries(
                    as_user.env, job.node_ids_json
                )
                file_name = f"{job.id}-{uuid.uuid4().hex}.zip"
                final = os.path.join(zip_stream.zips_dir(self.env), file_name)
                tmp_path = final + ".part"
                zip_stream.write_zip(entries, tmp_path)
                os.replace(tmp_path, final)
                tmp_path = None
                job.sudo().write(
                    {
                        "state": "done",
                        "size": os.path.getsize(final),
                        "file_name": file_name,
                        "expires_at": fields.Datetime.now()
                        + timedelta(hours=DEFAULT_KEEP_HOURS),
                    }
                )
        except (UserError, AccessError) as exc:
            job.sudo().write({"state": "failed", "error": str(exc)})
        except Exception:
            _logger.exception("failed to build zip job %s", job.id)
            job.sudo().write(
                {"state": "failed", "error": self.env._("Internal error.")}
            )
        finally:
            if tmp_path:
                _remove_if_exists(tmp_path)
        self.env["bus.bus"]._sendone(
            job.create_uid.partner_id,
            "int_filemanager_zip",
            {"job_id": job.id, "state": job.state, "name": job.name},
        )

    @api.model
    def _cron_expire_zips(self):
        """Remove expired jobs and their archives."""
        for job in self.search([("expires_at", "<", fields.Datetime.now())]):
            if job.file_name:
                _remove_if_exists(job._path())
            job.unlink()
