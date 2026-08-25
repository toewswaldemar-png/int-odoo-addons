import logging
import os
from datetime import datetime

from odoo import fields, models

from ..path_utils import get_root, to_relative

_logger = logging.getLogger(__name__)


class HmFilemanagerFile(models.Model):
    _name = "hm_filemanager.file"
    _description = "Filemanager-Datei"
    _order = "is_dir desc, name"

    name = fields.Char(index=True)
    path = fields.Char(
        required=True,
        index=True,
        help="Pfad relativ zum Filemanager-Stammverzeichnis.",
    )
    parent_path = fields.Char(index=True, help="Pfad des übergeordneten Ordners (leer = Wurzel).")
    is_dir = fields.Boolean(string="Ist Ordner", index=True)
    size = fields.Float(string="Größe (Bytes)")
    mtime = fields.Datetime(string="Geändert")
    last_seen = fields.Datetime(
        help="Zeitpunkt des letzten Scans, bei dem dieser Eintrag noch auf der Platte existierte.",
    )
    tag_ids = fields.Many2many("hm_filemanager.tag", string="Tags")

    _path_uniq = models.Constraint("UNIQUE(path)", "Für diesen Pfad existiert bereits ein Metadaten-Eintrag.")

    def _cron_scan_filemanager(self):
        self._scan_and_reconcile()

    def _scan_and_reconcile(self, batch_size=2000):
        """Full filesystem scan, reconciling the search index with disk state.
        Runs in batches with periodic commits since the tree can hold hundreds
        of thousands of entries; safe to call repeatedly (upsert by path)."""
        root = get_root(self.env)
        scan_started = fields.Datetime.now()
        Model = self.env["hm_filemanager.file"].sudo()
        batch = []

        def flush():
            if not batch:
                return
            paths = [v["path"] for v in batch]
            existing_by_path = {r.path: r for r in Model.search([("path", "in", paths)])}
            to_create = []
            for vals in batch:
                rec = existing_by_path.get(vals["path"])
                if rec:
                    rec.write(vals)
                else:
                    to_create.append(vals)
            if to_create:
                Model.create(to_create)
            batch.clear()
            self.env.cr.commit()

        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]
            rel_dir = to_relative(self.env, dirpath)
            for name in dirnames + [f for f in filenames if not f.startswith(".")]:
                abs_path = os.path.join(dirpath, name)
                try:
                    st = os.stat(abs_path)
                    is_dir = os.path.isdir(abs_path)
                except OSError:
                    continue
                rel = f"{rel_dir}/{name}" if rel_dir else name
                batch.append({
                    "name": name,
                    "path": rel,
                    "parent_path": rel_dir or False,
                    "is_dir": is_dir,
                    "size": 0 if is_dir else st.st_size,
                    "mtime": datetime.fromtimestamp(st.st_mtime),
                    "last_seen": scan_started,
                })
                if len(batch) >= batch_size:
                    flush()
        flush()

        stale = Model.search([("last_seen", "<", scan_started)])
        if stale:
            _logger.info("hm_filemanager: removing %s stale index entries", len(stale))
            stale.unlink()
            self.env.cr.commit()

        _logger.info("hm_filemanager: scan finished, index reconciled with %s", root)
