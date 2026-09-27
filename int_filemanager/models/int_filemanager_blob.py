import logging
import os
import time

import psycopg2

from odoo import api, fields, models

from .. import blobstore, fault

_logger = logging.getLogger(__name__)

# Konzept 5 "Aufraeumen": longer than a backup run, so a blob the backup's DB
# snapshot still references cannot be collected before the blob backup ran too.
DEFAULT_GC_GRACE_HOURS = 24
GC_GRACE_PARAM = "int_filemanager.blob_gc_grace_hours"


class IntFilemanagerBlob(models.Model):
    """Content-addressed storage row for one file's bytes (Konzept 5). No
    user-facing ACL at all (A1): the hash alone says nothing about who may
    read the content it names, so access only ever goes through a method
    that already checked the node under the caller's identity first."""

    _name = "int_filemanager.blob"
    _description = "Filemanager v2 blob (content, by hash)"

    sha256 = fields.Char(required=True, index=True)
    # Float, not Integer (int4 overflows above ~2 GiB, Pruefbericht Nr. 33-35/19.2).
    size = fields.Float(required=True)
    state = fields.Selection([("present", "Present")], default="present", required=True)
    # Set (or renewed) whenever a write reuses this blob; the cleanup job only removes
    # rows whose last_used is older than its grace period (A4, Konzept 5 "Aufraeumen").
    last_used = fields.Datetime(index=True)
    revision_ids = fields.One2many("int_filemanager.revision", "blob_id")

    _sha256_uniq = models.Constraint(
        "UNIQUE(sha256)", "A blob with this hash already exists."
    )

    @api.model
    def _get_or_create(self, sha256, size):
        """Idempotent, race-safe row lookup (Konzept 6 "Anlegen"): `retrying()`
        does not retry a `UniqueViolation` (A3), so a concurrent writer of the
        same content must be handled locally with a savepoint instead of
        letting the whole request fail."""
        blob = self.search([("sha256", "=", sha256)], limit=1)
        if blob:
            blob.write({"last_used": fields.Datetime.now()})
            return blob
        try:
            with self.env.cr.savepoint():
                return self.create(
                    {"sha256": sha256, "size": size, "last_used": fields.Datetime.now()}
                )
        except psycopg2.errors.UniqueViolation:
            blob = self.search([("sha256", "=", sha256)], limit=1)
            blob.write({"last_used": fields.Datetime.now()})
            return blob

    def _gc_grace_hours(self):
        return int(
            self.env["ir.config_parameter"]
            .sudo()
            .get_param(GC_GRACE_PARAM, DEFAULT_GC_GRACE_HOURS)
        )

    @api.autovacuum
    def _gc_blobs(self):
        """Same split as Odoo's own `ir.attachment._gc_file_store`/
        `_gc_file_store_unsafe`: this wrapper only owns the transaction
        boundaries (fresh transaction, table lock as the FIRST statement -
        else the snapshot `_gc_blobs_unsafe` queries might not see rows a
        concurrent writer just committed, Odoo's own comment on that method
        and the review's "Snapshot-Befund 3"). `_gc_blobs_unsafe` holds the
        actual decision logic and is what tests call directly - `TestCursor`
        cannot run this wrapper's `cr.commit()` without breaking the test's
        own rollback-based isolation."""
        cr = self.env.cr
        # Ends whatever transaction ir.autovacuum._run_vacuum_cleaner's shuffled
        # queue of sibling methods left open, so LOCK below is the first statement
        # of a fresh one (Odoo's own ir_attachment._gc_file_store does the same).
        cr.commit()  # pylint: disable=invalid-commit
        cr.execute("SET LOCAL lock_timeout TO '10s'")
        try:
            cr.execute(
                "LOCK int_filemanager_blob, int_filemanager_revision"
                " IN SHARE ROW EXCLUSIVE MODE"
            )
        except psycopg2.errors.LockNotAvailable:
            cr.rollback()
            return
        stale_count, removed, kept = self._gc_blobs_unsafe()
        # Releases the table lock; the filesystem deletes are not transactional
        # anyway, so nothing is lost by committing here rather than at the cron's end.
        cr.commit()  # pylint: disable=invalid-commit
        _logger.info(
            "int_filemanager blob gc: %d w/o revision, %d file(s) removed, %d kept",
            stale_count,
            removed,
            kept,
        )

    def _gc_blobs_unsafe(self):
        """The actual sweep, without any transaction/lock handling of its own
        (see `_gc_blobs`). Returns (stale_row_count, files_removed, files_kept)."""
        cr = self.env.cr
        # The raw SQL below would otherwise not see any blob/revision write still
        # sitting in the ORM's cache from earlier in this same transaction.
        self.env.flush_all()
        grace_hours = self._gc_grace_hours()
        cr.execute(
            """
            SELECT id, sha256 FROM int_filemanager_blob b
            WHERE NOT EXISTS (
                SELECT 1 FROM int_filemanager_revision WHERE blob_id = b.id
            ) AND last_used < (now() at time zone 'utc') - make_interval(hours => %s)
            """,
            [grace_hours],
        )
        stale = cr.fetchall()
        for _id, sha256 in stale:
            fault.fault_point("blob_gc_after_dedup_check")
            blobstore.mark_for_gc(self.env, sha256)
        if stale:
            cr.execute(
                "DELETE FROM int_filemanager_blob WHERE id IN %s",
                [tuple(r[0] for r in stale)],
            )

        removed = kept = 0
        checklist_dir = blobstore.checklist_dir(self.env)
        grace_seconds = grace_hours * 3600
        for sha256 in os.listdir(checklist_dir):
            marker = os.path.join(checklist_dir, sha256)
            if time.time() - os.path.getmtime(marker) < grace_seconds:
                continue
            cr.execute("SELECT 1 FROM int_filemanager_blob WHERE sha256 = %s", [sha256])
            if cr.fetchone():
                kept += 1
            else:
                blob_path = blobstore.blob_path(self.env, sha256)
                if os.path.exists(blob_path):
                    os.unlink(blob_path)
                    removed += 1
                fault.fault_point("blob_gc_after_delete_before_commit")
            os.unlink(marker)
        return len(stale), removed, kept
