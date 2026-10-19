import logging
import os
import posixpath
from typing import NamedTuple

from werkzeug.security import safe_join

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools import SQL

_logger = logging.getLogger(__name__)

IMPORT_ROOT_PARAMETER = "int_filemanager.import_root"
CRON_XMLID = "int_filemanager.int_filemanager_import_cron"
# Why ``_run_order`` stopped working on an order.
ENDED, BUSY, TIME_UP = "ended", "busy", "time_up"


class Source(NamedTuple):
    """Where a reading in starts: the root of the settings and the folder below it."""

    root: str
    relative: str


class IntFilemanagerImport(models.Model):
    """An order to read a folder of the disk into a folder of the filemanager.

    Two steps, both done by the scheduled action in small batches that survive a restart:
    *checking* lists the folder (one line per folder, file and oddity, so the report shows what
    would happen), *reading in* then copies. The files on the disk are never changed.
    The lines (``int.filemanager.import.line``) are the queue and the protocol.
    """

    _name = "int.filemanager.import"
    _description = "Filemanager import"
    _order = "id desc"
    _check_company_auto = True

    name = fields.Char(required=True, copy=False)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company, index=True
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("scanning", "Checking"),
            ("scanned", "Checked"),
            ("running", "Reading in"),
            ("done", "Done"),
        ],
        required=True,
        default="draft",
        readonly=True,
        copy=False,
    )
    source_path = fields.Char(
        string="Folder",
        help="The folder to read in, below the root folder of the settings. Empty: the root "
        "folder itself.",
    )
    root_path = fields.Char(
        string="Root folder", compute="_compute_root_path", help="Set in the settings."
    )
    target_folder_id = fields.Many2one(
        "int.filemanager.folder",
        string="Into folder",
        required=True,
        check_company=True,
        ondelete="restrict",
        help="The folders and files come below this folder.",
    )
    message = fields.Char(string="Last problem", readonly=True, copy=False)
    line_ids = fields.One2many("int.filemanager.import.line", "import_id")
    # The figures below are read from the lines when the state changes (and every time the
    # form is loaded); a line is not watched, that would cost a recompute for each file.
    line_count = fields.Integer(compute="_compute_counts")
    folder_count = fields.Integer(compute="_compute_counts")
    file_count = fields.Integer(compute="_compute_counts")
    total_size = fields.Float(compute="_compute_counts")
    pending_count = fields.Integer(compute="_compute_counts")
    done_count = fields.Integer(compute="_compute_counts")
    skipped_count = fields.Integer(compute="_compute_counts")
    excluded_count = fields.Integer(compute="_compute_counts")
    error_count = fields.Integer(compute="_compute_counts")
    clash_count = fields.Integer(compute="_compute_counts")
    progress = fields.Float(compute="_compute_counts")

    @api.depends_context("uid")
    def _compute_root_path(self):
        root = self.env["ir.config_parameter"].sudo().get_param(IMPORT_ROOT_PARAMETER)
        for record in self:
            record.root_path = root or False

    @api.depends("state")
    def _compute_counts(self):
        names = [
            "line_count",
            "folder_count",
            "file_count",
            "total_size",
            "pending_count",
            "done_count",
            "skipped_count",
            "excluded_count",
            "error_count",
            "clash_count",
            "progress",
        ]
        counts = {record.id: dict.fromkeys(names, 0) for record in self}
        # The first line (no path) is the folder itself; it is not counted.
        Line = self.env["int.filemanager.import.line"].sudo()
        for import_, kind, state, count, size in Line._read_group(
            [("import_id", "in", self.ids), ("path", "!=", "")],
            ["import_id", "kind", "state"],
            ["__count", "size:sum"],
        ):
            figures = counts[import_.id]
            figures["line_count"] += count
            figures[f"{kind}_count"] += count
            figures[f"{state}_count"] += count
            if kind == "file" and state in ("pending", "done", "error"):
                figures["total_size"] += size or 0
        for import_, count in Line._read_group(
            [("import_id", "in", self.ids), ("clash", "=", True)],
            ["import_id"],
            ["__count"],
        ):
            counts[import_.id]["clash_count"] = count
        for record in self:
            figures = counts[record.id]
            if figures["line_count"]:
                figures["progress"] = (
                    100.0 * (figures["line_count"] - figures["pending_count"]) / figures["line_count"]
                )
            record.update(figures)

    @api.ondelete(at_uninstall=False)
    def _unlink_except_busy(self):
        if self.filtered(lambda record: record.state in ("scanning", "running")):
            raise UserError(self.env._("Stop the reading in first."))

    # ---- Buttons -----------------------------------------------------------------------

    def action_scan(self):
        """List the folder: one line for every folder and file (nothing is copied yet)."""
        for record in self:
            if record.state not in ("draft", "scanned"):
                raise UserError(self.env._("The folder is being checked or read in already."))
            record._source()  # a wrong folder is told now, not by the scheduled action
        for record in self:
            record._restart_scan()
            record.message = False
        self._trigger_cron()

    def action_start(self):
        """Copy what the check found."""
        if self.filtered(lambda record: record.state != "scanned"):
            raise UserError(self.env._("Check the folder first."))
        self.write({"state": "running", "message": False})
        self._trigger_cron()

    def action_stop(self):
        """Stop where it is; "Read in" continues, "Check" starts again."""
        stopped = self.filtered(lambda record: record.state in ("scanning", "running"))
        stopped.filtered(lambda record: record.state == "scanning").write({"state": "draft"})
        stopped.filtered(lambda record: record.state == "running").write({"state": "scanned"})

    def action_retry_errors(self):
        """Read in again the files that failed."""
        self.env["int.filemanager.import.line"].sudo().search(
            [("import_id", "in", self.ids), ("state", "=", "error")]
        ).write({"state": "pending", "message": False})
        self.filtered(lambda record: record.state == "done").write({"state": "running"})
        self._trigger_cron()

    def action_open_lines(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Lines of %(name)s", name=self.name),
            "res_model": "int.filemanager.import.line",
            "view_mode": "list",
            "domain": [("import_id", "=", self.id), ("path", "!=", "")],
        }

    def _trigger_cron(self):
        # The scheduled action belongs to the superuser, the administrator only wakes it.
        self.env.ref(CRON_XMLID).sudo()._trigger()

    def _restart_scan(self):
        """Throw away the lines and begin with the folder itself."""
        self.ensure_one()
        # SQL, not ``unlink``: an order has a line for every folder and file of the disk (many
        # thousands), which ``unlink`` would load and check one by one. Hence the flush before
        # and the invalidation after.
        self.env["int.filemanager.import.line"].flush_model()
        self.env.execute_query(
            SQL("DELETE FROM int_filemanager_import_line WHERE import_id = %s", self.id)
        )
        self.env["int.filemanager.import.line"].invalidate_model()
        # The first line stands for the folder itself: the folders and files in it hang below it.
        self.env["int.filemanager.import.line"].sudo().create(
            {
                "import_id": self.id,
                "kind": "folder",
                "path": "",
                "name": "",
                "state": "done",
                "folder_id": self.target_folder_id.id,
            }
        )
        self.state = "scanning"

    # ---- The disk ----------------------------------------------------------------------

    def _source(self):
        """The root and the folder to read in, checked: both exist and the folder lies in the root.

        The settings are written by the system administrators only. A link inside the folder
        that leads out of the root is found by comparing real paths.
        """
        self.ensure_one()
        value = self.env["ir.config_parameter"].sudo().get_param(IMPORT_ROOT_PARAMETER)
        if not value or not os.path.isabs(value):
            raise UserError(
                self.env._("Set the root folder for reading in first (Settings > Filemanager).")
            )
        root = os.path.realpath(value)
        if not os.path.isdir(root):
            raise UserError(self.env._("The root folder %(root)s does not exist.", root=root))
        relative = posixpath.normpath((self.source_path or "").strip().replace("\\", "/").strip("/"))
        path = safe_join(root, "" if relative == "." else relative)
        real = os.path.realpath(path) if path else None
        if not real or not (real == root or real.startswith(root + os.sep)) or not os.path.isdir(real):
            raise UserError(
                self.env._(
                    "The folder %(folder)s is not a folder below the root folder.",
                    folder=self.source_path or "",
                )
            )
        relative = os.path.relpath(real, root).replace(os.sep, "/")
        return Source(root, "" if relative == "." else relative)

    # ---- The scheduled action ----------------------------------------------------------

    @api.model
    def _cron_run(self):
        """Check and read in the orders that were started, as long as the time of this run allows.

        One step is one folder listed or one file copied, and each step is committed
        (``_commit_progress``): after a restart the work goes on where it stopped. When the time
        is up it returns with work left, Odoo calls it again at once.
        """
        assert self.env.context.get("cron_id") == self.env.ref(CRON_XMLID).id, (
            "Meant for cron usage only"
        )
        cron = self.env["ir.cron"]
        busy = False
        for record in self.search([("state", "in", ("scanning", "running"))], order="id"):
            outcome = record._run_order()
            if outcome == TIME_UP:
                cron._commit_progress(remaining=1)
                return
            busy = busy or outcome == BUSY
        cron._commit_progress(remaining=int(busy))

    def _run_order(self):
        """Do the steps of this order one after the other, each one committed.

        :return: why it ended: ``ENDED`` (done, stopped or stopped by a problem), ``BUSY``
            (another transaction holds the order; the next run tries again) or ``TIME_UP``
        """
        self.ensure_one()
        cron = self.env["ir.cron"]
        while True:
            # Locked for the length of one step: a user who stops the order waits for it.
            if not self.try_lock_for_update():
                return BUSY
            scanning = self.state == "scanning"
            if not scanning and self.state != "running":
                return ENDED  # stopped meanwhile
            try:
                source = self._source()
            except UserError as error:
                # The settings or the folder changed under the order: stop it, say why.
                _logger.warning("Reading in %s stopped: %s", self.name, error.args[0])
                self.action_stop()
                self.message = error.args[0]
                cron._commit_progress()
                return ENDED
            processed = self._scan_step(source) if scanning else self._copy_step(source)
            if not processed:
                self.state = "scanned" if scanning else "done"
                cron._commit_progress()
                return ENDED
            if not cron._commit_progress(processed):
                return TIME_UP

    def _scan_step(self, source):
        """List one more folder; return how many were listed (0: all are)."""
        self.ensure_one()
        line = self.env["int.filemanager.import.line"].search(
            [("import_id", "=", self.id), ("kind", "=", "folder"), ("listed", "=", False)],
            order="id",
            limit=1,
        )
        if not line:
            return 0
        line._list_directory(source)
        return 1

    def _copy_step(self, source):
        """Read in one more line; return how many were done (0: none is left)."""
        self.ensure_one()
        line = self.env["int.filemanager.import.line"].search(
            [("import_id", "=", self.id), ("state", "=", "pending")], order="id", limit=1
        )
        if not line:
            return 0
        line._read_in(source)
        return 1
