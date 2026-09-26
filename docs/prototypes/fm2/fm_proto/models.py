import logging
import os
import time

import psycopg2

from odoo import api, fields, models
from odoo.exceptions import UserError

from . import blobstore

_logger = logging.getLogger(__name__)
GC_GRACE_SECONDS = int(os.environ.get("FM_PROTO_GC_GRACE", "3600"))


class FmBlob(models.Model):
    _name = "fm.blob"
    _description = "Prototyp Blob"

    sha256 = fields.Char(required=True, index=True)
    size = fields.Float(digits=False)  # Integer ist int4 (max ~2,1 GB) - zu klein fuer Dateigroessen

    _sha_uniq = models.UniqueIndex("(sha256)")

    @api.model
    def _get_or_create(self, sha, size):
        blob = self.search([("sha256", "=", sha)], limit=1)
        if blob:
            return blob
        try:
            with self.env.cr.savepoint():
                return self.create({"sha256": sha, "size": size})
        except psycopg2.errors.UniqueViolation:
            return self.search([("sha256", "=", sha)], limit=1)

    @api.autovacuum
    def _gc_blobs(self):
        """Wie ir.attachment._gc_file_store: frische Transaktion, Tabellensperre als erstes Statement,
        dann nur Kandidaten aus der Checkliste loeschen, die keine fm.blob-Zeile (mehr) haben. Zeilen ohne
        Revision werden vorher entfernt (Bytes nie vor der Zeile, I4)."""
        cr = self.env.cr
        cr.commit()
        cr.execute("SET LOCAL lock_timeout TO '10s'")
        cr.execute("LOCK fm_blob, fm_revision IN SHARE ROW EXCLUSIVE MODE")
        # 1) Zeilen ohne Revision (nach Schonfrist) -> Checkliste
        cr.execute("""
            SELECT b.id, b.sha256 FROM fm_blob b
            WHERE NOT EXISTS (SELECT 1 FROM fm_revision r WHERE r.blob_id = b.id)
              AND b.create_date < (now() at time zone 'utc') - make_interval(secs => %s)""", [GC_GRACE_SECONDS])
        rows = cr.fetchall()
        for _id, sha in rows:
            blobstore.mark_for_gc(self.env, sha)
        if rows:
            cr.execute("DELETE FROM fm_blob WHERE id IN %s", [tuple(r[0] for r in rows)])
        # 2) Checkliste abarbeiten
        cl = os.path.join(blobstore.root(self.env), "checklist")
        removed = kept = 0
        now = time.time()
        for name in (os.listdir(cl) if os.path.isdir(cl) else []):
            marker = os.path.join(cl, name)
            if now - os.path.getmtime(marker) < GC_GRACE_SECONDS:
                continue
            cr.execute("SELECT 1 FROM fm_blob WHERE sha256 = %s", [name])
            if cr.fetchone():
                kept += 1
            else:
                p = blobstore.blob_path(self.env, name)
                if os.path.exists(p):
                    os.unlink(p)
                    removed += 1
            os.unlink(marker)
        cr.commit()
        _logger.info("fm blob gc: %d Zeilen ohne Revision, %d Dateien entfernt, %d behalten", len(rows), removed, kept)
        return len(rows), removed, kept


class FmNode(models.Model):
    _name = "fm.node"
    _description = "Prototyp Knoten"
    _parent_store = True
    _parent_name = "parent_id"

    name = fields.Char(required=True)
    parent_id = fields.Many2one("fm.node", index=True, ondelete="restrict")
    parent_path = fields.Char(index=True)
    is_dir = fields.Boolean()
    active = fields.Boolean(default=True)
    current_revision_id = fields.Many2one("fm.revision")
    size = fields.Float(related="current_revision_id.blob_id.size")
    sha256 = fields.Char(related="current_revision_id.blob_id.sha256")

    _name_uniq = models.UniqueIndex("(COALESCE(parent_id, 0), name) WHERE active IS TRUE")

    def _add_revision(self, blob, origin, operation_key=None):
        self.ensure_one()
        self.lock_for_update()
        no = (self.current_revision_id.revision_no or 0) + 1
        rev = self.env["fm.revision"].create({
            "node_id": self.id, "blob_id": blob.id, "revision_no": no, "origin": origin,
            "operation_key": operation_key,
        })
        self.current_revision_id = rev
        return rev


class FmRevision(models.Model):
    _name = "fm.revision"
    _description = "Prototyp Revision"
    _order = "node_id, revision_no desc"

    node_id = fields.Many2one("fm.node", required=True, index=True, ondelete="cascade")
    blob_id = fields.Many2one("fm.blob", required=True, index=True, ondelete="restrict")
    revision_no = fields.Integer(required=True)
    origin = fields.Char()
    operation_key = fields.Char(index=True)

    _rev_uniq = models.UniqueIndex("(node_id, revision_no)")


class FmUpload(models.Model):
    _name = "fm.upload"
    _description = "Prototyp Upload in Stuecken"

    operation_key = fields.Char(required=True)
    parent_id = fields.Many2one("fm.node")
    name = fields.Char(required=True)
    size_expected = fields.Float(digits=False)
    state = fields.Selection([("open", "offen"), ("done", "fertig")], default="open")
    node_id = fields.Many2one("fm.node")
    revision_id = fields.Many2one("fm.revision")

    _op_uniq = models.UniqueIndex("(operation_key)")

    def _tmp_path(self):
        return os.path.join(blobstore.tmp_dir(self.env), "upload_%s.part" % self.operation_key)

    def _received(self):
        p = self._tmp_path()
        return os.path.getsize(p) if os.path.exists(p) else 0
