import logging
import time
import uuid
from datetime import timedelta

import psycopg2

from odoo import api, fields, models

from .. import blobstore, converter_client, fault

_logger = logging.getLogger(__name__)

CONVERTER_URL_PARAM = "int_filemanager.converter_url"
CONVERTER_TIMEOUT_PARAM = "int_filemanager.converter_timeout_s"
DEFAULT_CONVERTER_TIMEOUT_S = 60
# One cron run stops starting new jobs after this long.
RUN_BUDGET_S = 45
CLAIM_BATCH = 5
# A job whose worker died is released this long after it was taken.
LEASE_MINUTES = 10
MAX_ATTEMPTS = 3
MAX_CLAIM_CONFLICTS = 5
ENQUEUE_BATCH = 500
TILE_SPEC = "400x300"
# What the explorer shows first: the rows of the folder the user is looking at.
VISIBLE_PRIORITY = 100
MAX_REQUESTED_NODES = 200
# The converter is asked for JPEG tiles of these types only (for now).
TILE_MIMES = ("image/jpeg",)


class IntFilemanagerDerivative(models.Model):
    """Something derived from a blob: a thumbnail, later previews, text, metadata.

    Users have no access rights: the result is only served by the preview
    route, after the rights on the revision were checked. Odoo only stores and
    serves the result; the converter is the only one that opens the bytes.
    """

    _name = "int_filemanager.derivative"
    _description = "Filemanager v2 derived file"
    _order = "priority desc, id"

    source_blob_id = fields.Many2one(
        "int_filemanager.blob", required=True, index=True, ondelete="restrict"
    )
    kind = fields.Selection([("tile", "Thumbnail")], required=True)
    spec = fields.Char(required=True)
    state = fields.Selection(
        [
            ("pending", "Pending"),
            ("running", "Running"),
            ("done", "Done"),
            ("failed", "Failed"),
            ("not_applicable", "Not applicable"),
        ],
        default="pending",
        required=True,
        index=True,
    )
    # May be the source blob itself (a tiny JPEG can be its own thumbnail).
    derived_blob_id = fields.Many2one(
        "int_filemanager.blob", index=True, ondelete="restrict"
    )
    mime = fields.Char()
    priority = fields.Integer(default=0)
    attempts = fields.Integer()
    next_try_at = fields.Datetime()
    lease_until = fields.Datetime()
    started_at = fields.Datetime()
    finished_at = fields.Datetime()
    tool = fields.Char()
    tool_version = fields.Char()
    # Technical text, for administrators only (no user has access to this model).
    error = fields.Char()

    _source_kind_spec_uniq = models.Constraint(
        "UNIQUE(source_blob_id, kind, spec)",
        "This blob already has this derived file.",
    )

    # ------------------------------------------------------------------
    # queue
    # ------------------------------------------------------------------

    @api.model
    def _cron_run(self):
        """Queue the missing jobs and work through the open ones."""
        params = self.env["ir.config_parameter"].sudo()
        url = params.get_param(CONVERTER_URL_PARAM)
        if not url:
            return
        self._enqueue_missing()
        timeout = int(
            params.get_param(CONVERTER_TIMEOUT_PARAM, DEFAULT_CONVERTER_TIMEOUT_S)
        )
        deadline = time.monotonic() + RUN_BUDGET_S
        done_any = False
        claim_conflicts = 0
        while time.monotonic() < deadline:
            # A fresh transaction, so the claim below sees what other runs committed
            # (Odoo's REPEATABLE READ would otherwise fail on a row they just took).
            self.env.flush_all()
            self.env["ir.cron"]._commit_progress()
            try:
                jobs = self._claim_jobs()
            except psycopg2.errors.SerializationFailure:
                # Another run took rows of this batch between our snapshot and our
                # lock (SKIP LOCKED does not skip rows changed since the snapshot).
                # Genuine and harmless: start over in a new transaction.
                self.env.cr.rollback()
                self.env.invalidate_all()
                claim_conflicts += 1
                if claim_conflicts > MAX_CLAIM_CONFLICTS:
                    break
                continue
            if not jobs:
                break
            # Everything the calls need is read before the commit: no statement, and so
            # no open transaction, while the converter works.
            plan = [
                (job, job.source_blob_id.sha256, job.kind, job.spec) for job in jobs
            ]
            self.env["ir.cron"]._commit_progress()
            fault.fault_point("derivative_after_claim")
            for position, (job, sha256, kind, spec) in enumerate(plan):
                try:
                    done_any |= job._run(url, timeout, sha256, kind, spec)
                except converter_client.ConverterUnavailable as exc:
                    _logger.warning("converter not available: %s", exc)
                    # The rest of this batch was taken but not started: free it now
                    # instead of after its lease.
                    jobs[position + 1 :].write(
                        {"state": "pending", "lease_until": False}
                    )
                    self.env["ir.cron"]._commit_progress()
                    self._notify_ready(done_any)
                    return
                self.env["ir.cron"]._commit_progress(processed=1)
        self._notify_ready(done_any)

    @api.model
    def _enqueue_missing(self):
        """Create jobs for current revisions that have none yet.

        Done here, not in the write paths, so those stay untouched. Only
        current revisions: an old revision had its thumbnail when it was current.
        """
        self.env.flush_all()
        cr = self.env.cr
        cr.execute(
            """
            SELECT DISTINCT b.id
            FROM int_filemanager_node n
            JOIN int_filemanager_revision r ON r.id = n.current_revision_id
            JOIN int_filemanager_blob b ON b.id = r.blob_id
            WHERE n.active AND n.mime IN %s AND b.size > 0
              AND NOT EXISTS (
                  SELECT 1 FROM int_filemanager_derivative d
                  WHERE d.source_blob_id = b.id AND d.kind = 'tile' AND d.spec = %s)
            LIMIT %s
            """,
            [TILE_MIMES, TILE_SPEC, ENQUEUE_BATCH],
        )
        for (blob_id,) in cr.fetchall():
            try:
                with cr.savepoint():
                    self.create(
                        {"source_blob_id": blob_id, "kind": "tile", "spec": TILE_SPEC}
                    )
            except psycopg2.errors.UniqueViolation:
                # Another run queued it at the same time: nothing to do.
                continue

    @api.model
    def _claim_jobs(self):
        """Mark open jobs as taken; the caller commits before calling the converter."""
        self.env.flush_all()
        self.env.cr.execute(
            """
            SELECT id FROM int_filemanager_derivative
            WHERE (state = 'pending' AND (
                       next_try_at IS NULL
                       OR next_try_at <= (now() at time zone 'utc')))
               OR (state = 'running'
                   AND lease_until < (now() at time zone 'utc'))
            ORDER BY priority DESC, id
            LIMIT %s
            FOR UPDATE SKIP LOCKED
            """,
            [CLAIM_BATCH],
        )
        jobs = self.browse([row[0] for row in self.env.cr.fetchall()])
        if jobs:
            now = fields.Datetime.now()
            jobs.write(
                {
                    "state": "running",
                    "started_at": now,
                    "lease_until": now + timedelta(minutes=LEASE_MINUTES),
                }
            )
        return jobs

    def _run(self, url, timeout, sha256, kind, spec):
        """Convert one blob; return True if a result was stored.

        The arguments are read by the caller before its commit, so that no query
        runs (and no transaction is open) while the converter works.
        """
        self.ensure_one()
        try:
            with converter_client.convert(url, sha256, kind, spec, timeout) as result:
                if result.state == "done":
                    return self._store_result(result)
                self._finish(result)
        except converter_client.ConverterUnavailable:
            # Not the file's fault: hand the job back without counting an attempt.
            self.write({"state": "pending", "lease_until": False})
            raise
        return False

    def _finish(self, result):
        """Record a failure or "not applicable"; retry a failure a few times."""
        if not self.exists():
            return
        values = {
            "tool": result.tool,
            "tool_version": result.tool_version,
            "error": result.error,
            "lease_until": False,
            "finished_at": fields.Datetime.now(),
        }
        if result.state == "failed" and self.attempts + 1 < MAX_ATTEMPTS:
            wait = timedelta(minutes=2 ** (self.attempts + 1))
            values.update(
                state="pending",
                attempts=self.attempts + 1,
                next_try_at=fields.Datetime.now() + wait,
            )
        else:
            values.update(state=result.state, attempts=self.attempts + 1)
        self.write(values)

    def _store_result(self, result):
        """Store the converter's bytes as a blob and link them to this job.

        Same order as a user upload: the file is linked under its hash first,
        the database row follows in a short transaction, the temp file is kept
        until after the commit so the cleanup job cannot take the blob away.
        """
        tmp_path = blobstore.write_stream_to_temp(
            self.env, result.stream, f"derivative_{self.id}_{uuid.uuid4().hex}"
        )
        try:
            sha256, size = blobstore.hash_file(tmp_path)
            blobstore.adopt_hashed(self.env, tmp_path, sha256, keep_tmp=True)
            fault.fault_point("derivative_after_link")
            blob = self.env["int_filemanager.blob"]._get_or_create(sha256, size)
            blobstore.ensure_on_disk(self.env, sha256, tmp_path)
            stored = bool(self.exists())
            if stored:
                # The job may be gone (its source was purged meanwhile); then the
                # blob stays unreferenced and the cleanup job removes it.
                self.write(
                    {
                        "state": "done",
                        "derived_blob_id": blob.id,
                        "mime": result.mime,
                        "tool": result.tool,
                        "tool_version": result.tool_version,
                        "error": False,
                        "lease_until": False,
                        "finished_at": fields.Datetime.now(),
                    }
                )
            self.env["ir.cron"]._commit_progress()
            return stored
        finally:
            blobstore.remove_if_exists(tmp_path)

    @api.model
    def _notify_ready(self, done_any):
        """Tell open explorers to look again; carries no data of its own."""
        if done_any:
            self.env["bus.bus"]._sendone(
                self.env.ref("int_filemanager.group_filemanager_user"),
                "int_filemanager_preview_ready",
                {},
            )

    # ------------------------------------------------------------------
    # what the explorer asks for
    # ------------------------------------------------------------------

    @api.model
    def _tile_for_blob(self, blob):
        """Return the finished tile job of ``blob``, or an empty recordset."""
        return self.sudo().search(
            [
                ("source_blob_id", "=", blob.id),
                ("kind", "=", "tile"),
                ("state", "=", "done"),
                ("derived_blob_id", "!=", False),
            ],
            limit=1,
        )
