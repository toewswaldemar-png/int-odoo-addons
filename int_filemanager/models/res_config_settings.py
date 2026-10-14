from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    int_filemanager_import_root = fields.Char(
        string="Root folder",
        config_parameter="int_filemanager.import_root",
        help="Only what lies below this folder of the server can be read into the filemanager. "
        "An absolute path, e.g. /mnt/hm-daten.",
    )

    int_filemanager_time_reserve = fields.Integer(
        string="Time reserve (seconds)",
        config_parameter="int_filemanager.time_reserve",
        default=15,
        help="The text of the files is read in runs of the scheduled action. A run stops this "
        "long before Odoo's own time limit for it would stop (and restart) the server.",
    )
    int_filemanager_memory_mib = fields.Integer(
        string="Memory per file (MiB)",
        config_parameter="int_filemanager.memory_mib",
        default=1024,
        help="How much memory the reading of one file may use. A file that needs more is "
        "skipped, and read again if this is raised.",
    )
    int_filemanager_text_block_kib = fields.Integer(
        string="Text block (KiB)",
        config_parameter="int_filemanager.text_block_kib",
        default=64,
        help="The text of files without pages (Word, Excel, plain text) is saved in blocks of "
        "this size.",
    )
    int_filemanager_text_cut_bytes = fields.Integer(
        string="Largest page (bytes)",
        config_parameter="int_filemanager.text_cut_bytes",
        default=650000,
        help="The most text kept of one page of a PDF (in bytes, not letters). More is cut off.",
    )
    int_filemanager_work_mem_mib = fields.Integer(
        string="Memory of the search (MiB)",
        config_parameter="int_filemanager.work_mem_mib",
        default=128,
        help="The database may use this much memory for one search in the text of the files "
        "(for this search only). A word that is on very many pages needs it, or takes minutes.",
    )
    int_filemanager_max_attempts = fields.Integer(
        string="Tries per file",
        config_parameter="int_filemanager.max_attempts",
        default=3,
        help="A file that stops the reading or is too slow is tried this many times.",
    )

    # Status of the reading of the files (nothing is saved).
    int_filemanager_text_missing = fields.Integer(
        string="Not yet looked at", compute="_compute_int_filemanager_text_status"
    )
    int_filemanager_text_pending = fields.Integer(
        string="Waiting", compute="_compute_int_filemanager_text_status"
    )
    int_filemanager_text_running = fields.Integer(
        string="Running", compute="_compute_int_filemanager_text_status"
    )
    int_filemanager_text_done = fields.Integer(
        string="Done", compute="_compute_int_filemanager_text_status"
    )
    int_filemanager_text_empty = fields.Integer(
        string="Without text", compute="_compute_int_filemanager_text_status"
    )
    int_filemanager_text_skipped = fields.Integer(
        string="Skipped", compute="_compute_int_filemanager_text_status"
    )
    int_filemanager_text_failed = fields.Integer(
        string="Failed", compute="_compute_int_filemanager_text_status"
    )
    int_filemanager_text_budget = fields.Char(
        string="Time of a run", compute="_compute_int_filemanager_text_status"
    )
    int_filemanager_text_reader = fields.Char(
        string="PDF reader", compute="_compute_int_filemanager_text_status"
    )
    int_filemanager_text_lastcall = fields.Datetime(
        string="Last run", compute="_compute_int_filemanager_text_status"
    )

    @api.depends_context("uid")
    def _compute_int_filemanager_text_status(self):
        Text = self.env["int.filemanager.text"]
        counts = Text._status()
        mode, limit, seconds, bounded = Text._budget()
        if bounded:
            budget = self.env._(
                "%(seconds)s s (%(mode)s server, limit of Odoo %(limit)s s)",
                seconds=seconds,
                mode=mode,
                limit=limit,
            )
        else:
            budget = self.env._("%(seconds)s s (Odoo has no limit)", seconds=seconds)
        if seconds < 10:
            budget += " " + self.env._(
                "Too short: no file is read. Raise the limit of Odoo for scheduled actions "
                "(limit_time_real_cron) or lower the time reserve."
            )
        version = Text._tools()
        reader = (
            self.env._("pdfminer %(version)s", version=version)
            if version
            else self.env._("not installed: PDF files are not read")
        )
        cron = self.env.ref("int_filemanager.int_filemanager_text_cron", raise_if_not_found=False)
        for settings in self:
            settings.int_filemanager_text_missing = counts["missing"]
            settings.int_filemanager_text_pending = counts["pending"]
            settings.int_filemanager_text_running = counts["running"]
            settings.int_filemanager_text_done = counts["done"]
            settings.int_filemanager_text_empty = counts["empty"]
            settings.int_filemanager_text_skipped = counts["skipped"]
            settings.int_filemanager_text_failed = counts["failed"]
            settings.int_filemanager_text_budget = budget
            settings.int_filemanager_text_reader = reader
            settings.int_filemanager_text_lastcall = cron.sudo().lastcall if cron else False
