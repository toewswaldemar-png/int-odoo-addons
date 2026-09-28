import logging
import os
import time

import psycopg2

from odoo import api, fields, models

from .. import blobstore, fault

_logger = logging.getLogger(__name__)

# Longer than a backup run, so a blob the database backup still refers to is
# not removed before the blob backup has run.
DEFAULT_GC_GRACE_HOURS = 24
GC_GRACE_PARAM = "int_filemanager.blob_gc_grace_hours"


class IntFilemanagerBlob(models.Model):
    """Stored content, identified by its hash.

    Users have no access rights on blobs: the content is only reached
    through a node whose rights were checked first.
    """

    _name = "int_filemanager.blob"
    _description = "Filemanager v2 blob (content, by hash)"

    sha256 = fields.Char(required=True, index=True)
    # Float, not Integer: an int4 column overflows for files above 2 GiB.
    size = fields.Float(required=True)
    state = fields.Selection([("present", "Present")], default="present", required=True)
    # Renewed whenever a write uses this blob; the cleanup job only removes rows
    # unused for longer than its grace period.
    last_used = fields.Datetime(index=True)
    revision_ids = fields.One2many("int_filemanager.revision", "blob_id")

    _sha256_uniq = models.Constraint(
        "UNIQUE(sha256)", "A blob with this hash already exists."
    )

    @api.model
    def _get_or_create(self, sha256, size):
        """Return the blob row for ``sha256``, creating it if needed.

        A concurrent writer of the same content is handled here: Odoo does
        not retry a request on a unique violation.
        """
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
        """Remove blobs nothing refers to any more, after their grace period.

        Like ``ir.attachment._gc_file_store``, this wrapper only handles the
        transaction and the table lock; the logic is in _gc_blobs_unsafe(),
        which tests call directly.
        """
        cr = self.env.cr
        # Start a fresh transaction so that the LOCK is its first statement and
        # its snapshot sees everything committed so far.
        cr.commit()  # pylint: disable=unknown-option-value,invalid-commit
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
        cr.commit()  # pylint: disable=unknown-option-value,invalid-commit
        _logger.info(
            "int_filemanager blob gc: %d w/o revision, %d file(s) removed, %d kept",
            stale_count,
            removed,
            kept,
        )

    def _gc_blobs_unsafe(self):
        """Sweep without transaction handling; return (stale rows, removed, kept)."""
        cr = self.env.cr
        # The SQL below must see pending ORM writes.
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
