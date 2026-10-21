from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.misc import format_duration, human_size

from .int_filemanager_share import SHARE_DEFAULTS
from .res_users_settings import OPEN_MODE_PARAMETER, OPEN_MODES

# The settings of the shares that are numbers (at least 1, see the constraint).
SHARE_NUMBERS = tuple(
    f"int_filemanager_{key}"
    for key, default in SHARE_DEFAULTS.items()
    if isinstance(default, int)
)


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

    int_filemanager_ocr_enabled = fields.Boolean(
        string="Recognize the text in scans",
        config_parameter="int_filemanager.ocr_enabled",
        help="Scanned pages (PDF files without text) get a text layer, so that the search finds "
        "their words. Pictures are read in the folders that have it switched on. The files "
        "themselves are not changed.",
    )
    int_filemanager_ocr_languages = fields.Char(
        string="Recognition languages",
        config_parameter="int_filemanager.ocr_languages",
        default="deu+eng",
        help="The languages of the text, as Tesseract names them, joined by +: deu+eng.",
    )
    int_filemanager_ocr_jobs = fields.Integer(
        string="Cores",
        config_parameter="int_filemanager.ocr_jobs",
        default=1,
        help="How many processor cores one text recognition may use.",
    )
    # A selection: Odoo does not save a 0 of a number field, and 0 is a priority.
    int_filemanager_ocr_nice = fields.Selection(
        [
            ("19", "Lowest: the web pages come first"),
            ("10", "Low"),
            ("5", "Medium"),
            ("0", "Normal: like the web pages"),
        ],
        string="Priority",
        config_parameter="int_filemanager.ocr_nice",
        default="19",
        help="How much of the processor the recognition takes when the server is busy.",
    )
    int_filemanager_ocr_deskew = fields.Selection(
        [("1", "Straighten and turn the pages"), ("0", "Leave the pages as they are")],
        string="Pages",
        config_parameter="int_filemanager.ocr_deskew",
        default="1",
        help="Straightening and turning make the recognition better and the time longer.",
    )
    int_filemanager_ocr_output_type = fields.Selection(
        [("pdf", "PDF"), ("pdfa", "PDF/A (archive)")],
        string="Type of the new PDF",
        config_parameter="int_filemanager.ocr_output_type",
        default="pdf",
        help="PDF/A takes longer and makes the file bigger.",
    )

    int_filemanager_default_open_mode = fields.Selection(
        OPEN_MODES,
        string="Open documents with",
        config_parameter=OPEN_MODE_PARAMETER,
        default=OPEN_MODES[0][0],
        help="What opens a document in the list and the kanban. Every user can choose otherwise "
        "in their preferences.",
    )

    int_filemanager_access_via_record = fields.Boolean(
        string="Access through linked records",
        help="Whoever may read a record (a contact, say) may also read the documents linked to "
        "it, without a right on their folder. Off: only the folders decide, and a file uploaded "
        "to a record is seen by those who see its upload folder.",
    )

    # The shares (links for guests). The numbers are at least 1: Odoo does not save a 0 of a
    # number field, and the field would show its default again.
    int_filemanager_share_creators = fields.Selection(
        [
            ("user", "All filemanager users"),
            ("admin", "Filemanager administrators only"),
        ],
        string="Who makes shares",
        config_parameter="int_filemanager.share_creators",
        default=SHARE_DEFAULTS["share_creators"],
        help="Whoever may make a share can give the folders and files that they see.",
    )
    int_filemanager_share_default_file_mb = fields.Integer(
        string="Largest file (MB)",
        config_parameter="int_filemanager.share_default_file_mb",
        default=SHARE_DEFAULTS["share_default_file_mb"],
    )
    int_filemanager_share_default_total_mb = fields.Integer(
        string="All files together (MB)",
        config_parameter="int_filemanager.share_default_total_mb",
        default=SHARE_DEFAULTS["share_default_total_mb"],
    )
    int_filemanager_share_default_files = fields.Integer(
        string="Number of files",
        config_parameter="int_filemanager.share_default_files",
        default=SHARE_DEFAULTS["share_default_files"],
    )
    int_filemanager_share_default_extensions = fields.Char(
        string="Allowed endings",
        config_parameter="int_filemanager.share_default_extensions",
        default=SHARE_DEFAULTS["share_default_extensions"],
        help="Separated by commas: pdf, jpg. Empty: every ending, except those that can run as "
        "a program or a page.",
    )
    int_filemanager_share_max_file_mb = fields.Integer(
        string="Largest file (MB)",
        config_parameter="int_filemanager.share_max_file_mb",
        default=SHARE_DEFAULTS["share_max_file_mb"],
    )
    int_filemanager_share_max_total_mb = fields.Integer(
        string="All files together (MB)",
        config_parameter="int_filemanager.share_max_total_mb",
        default=SHARE_DEFAULTS["share_max_total_mb"],
    )
    int_filemanager_share_max_files = fields.Integer(
        string="Number of files",
        config_parameter="int_filemanager.share_max_files",
        default=SHARE_DEFAULTS["share_max_files"],
    )
    int_filemanager_share_password_length = fields.Integer(
        string="Shortest password",
        config_parameter="int_filemanager.share_password_length",
        default=SHARE_DEFAULTS["share_password_length"],
    )
    int_filemanager_share_unlock_hours = fields.Integer(
        string="Hours the password is kept",
        config_parameter="int_filemanager.share_unlock_hours",
        default=SHARE_DEFAULTS["share_unlock_hours"],
        help="A guest who typed the password of a share does not type it again for this long, "
        "in the same browser tab.",
    )
    int_filemanager_share_brake = fields.Selection(
        [("1", "On"), ("0", "Off")],
        string="Brake on requests",
        config_parameter="int_filemanager.share_brake",
        default=SHARE_DEFAULTS["share_brake"],
        help="Limits how many requests one address may send: made-up addresses of shares, and "
        "the requests to a share. Not the brake on wrong passwords: that one is always on.",
    )
    int_filemanager_share_invalid_tokens = fields.Integer(
        string="Wrong addresses in 10 minutes",
        config_parameter="int_filemanager.share_invalid_tokens",
        default=SHARE_DEFAULTS["share_invalid_tokens"],
        help="After this many addresses of shares that do not exist, an address is turned away "
        "for ten minutes (whoever has a right link is not).",
    )
    int_filemanager_share_requests_per_minute = fields.Integer(
        string="Requests to a share in a minute",
        config_parameter="int_filemanager.share_requests_per_minute",
        default=SHARE_DEFAULTS["share_requests_per_minute"],
    )
    int_filemanager_share_uploads_per_minute = fields.Integer(
        string="Uploads to a share in a minute",
        config_parameter="int_filemanager.share_uploads_per_minute",
        default=SHARE_DEFAULTS["share_uploads_per_minute"],
        help="Files that one address may send to a share in a minute. The limits of the share "
        "itself (size, number, total) do not depend on it.",
    )
    int_filemanager_share_password_tries_ip = fields.Integer(
        string="Wrong passwords of an address in 10 minutes",
        config_parameter="int_filemanager.share_password_tries_ip",
        default=SHARE_DEFAULTS["share_password_tries_ip"],
    )
    int_filemanager_share_password_tries_share = fields.Integer(
        string="Wrong passwords of a share in 10 minutes",
        config_parameter="int_filemanager.share_password_tries_share",
        default=SHARE_DEFAULTS["share_password_tries_share"],
        help="From all addresses together.",
    )

    # Status of the text recognition (nothing is saved).
    int_filemanager_ocr_state = fields.Char(
        string="Recognition", compute="_compute_int_filemanager_ocr_status"
    )
    int_filemanager_ocr_tools = fields.Char(
        string="Programs", compute="_compute_int_filemanager_ocr_status"
    )
    int_filemanager_ocr_wait = fields.Integer(
        string="Scans waiting", compute="_compute_int_filemanager_ocr_status"
    )
    int_filemanager_ocr_running = fields.Integer(
        string="Scans running", compute="_compute_int_filemanager_ocr_status"
    )
    int_filemanager_ocr_done = fields.Integer(
        string="Scans done", compute="_compute_int_filemanager_ocr_status"
    )
    int_filemanager_ocr_failed = fields.Integer(
        string="Scans failed", compute="_compute_int_filemanager_ocr_status"
    )
    int_filemanager_ocr_left = fields.Char(
        string="Still to do", compute="_compute_int_filemanager_ocr_status"
    )
    int_filemanager_ocr_pdf_size = fields.Char(
        string="Recognized PDFs", compute="_compute_int_filemanager_ocr_status"
    )
    int_filemanager_ocr_notes = fields.Text(
        string="Notes", compute="_compute_int_filemanager_ocr_status"
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
    def _compute_int_filemanager_ocr_status(self):
        status = self.env["int.filemanager.text"]._ocr_status()
        tools, counts = status["tools"], status["counts"]
        reasons = {
            "off": self.env._("Off."),
            "missing_dependency": self.env._(
                "Stopped: ocrmypdf or Tesseract is not installed on the server."
            ),
            "missing_language": self.env._("Stopped: Tesseract lacks a language that is asked for."),
            "disk_full": self.env._("Paused: the disk is full."),
            "bad_setup": self.env._("Stopped: the program does not take the settings."),
        }
        state = (
            self.env._("Ready.")
            if status["ready"]
            else reasons.get(status["reason"], self.env._("Stopped."))
        )
        if status["detail"]:
            state += f" ({status['detail']})"
        if not tools["program"]:
            installed = self.env._("not installed")
        elif not tools["tesseract"]:
            installed = self.env._("ocrmypdf is there, Tesseract is not")
        else:
            installed = self.env._(
                "ocrmypdf %(version)s, Tesseract with %(languages)s",
                version=tools["version"] or "?",
                languages=", ".join(sorted(tools["languages"])) or self.env._("no language"),
            )
        left = self.env._("%(pages)s pages", pages=status["pages_left"])
        if status["pages_left"]:
            left += " " + self.env._(
                "(about %(time)s hours of work)", time=format_duration(status["seconds_left"] / 3600)
            )
        notes = []
        if status["lc_ctype"] == "C":
            notes.append(
                self.env._(
                    "The database has the character set C: capital umlauts are not folded, "
                    "so the search finds a word with a capital Ü only by its capital."
                )
            )
        notes.append(
            self.env._(
                "A run of the scheduled action is as long as the limit of Odoo for it "
                "(limit_time_real_cron). A longer limit gives the recognition more work per run."
            )
        )
        for settings in self:
            settings.int_filemanager_ocr_state = state
            settings.int_filemanager_ocr_tools = installed
            settings.int_filemanager_ocr_wait = counts["wait"]
            settings.int_filemanager_ocr_running = counts["running"]
            settings.int_filemanager_ocr_done = counts["done"]
            settings.int_filemanager_ocr_failed = counts["failed"]
            settings.int_filemanager_ocr_left = left
            settings.int_filemanager_ocr_pdf_size = human_size(status["pdf_size"]) or "0 Bytes"
            settings.int_filemanager_ocr_notes = "\n".join(notes)

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

    @api.constrains(*SHARE_NUMBERS)
    def _check_int_filemanager_share_numbers(self):
        """At least 1, and a new share must not start above what a share may be."""
        pairs = (
            ("int_filemanager_share_default_file_mb", "int_filemanager_share_max_file_mb"),
            ("int_filemanager_share_default_total_mb", "int_filemanager_share_max_total_mb"),
            ("int_filemanager_share_default_files", "int_filemanager_share_max_files"),
        )
        for settings in self:
            for name in SHARE_NUMBERS:
                if settings[name] < 1:
                    raise ValidationError(
                        self.env._(
                            "%(field)s: at least 1.",
                            field=settings._fields[name]._description_string(self.env),
                        )
                    )
            for default, maximum in pairs:
                if settings[default] > settings[maximum]:
                    raise ValidationError(
                        self.env._(
                            "%(field)s: the start value is above the limit.",
                            field=settings._fields[default]._description_string(self.env),
                        )
                    )

    @api.model
    def get_values(self):
        res = super().get_values()
        rule = self.env.ref("int_filemanager.int_filemanager_document_rule_record")
        res["int_filemanager_access_via_record"] = rule.sudo().active
        return res

    def set_values(self):
        super().set_values()
        self.env["int.filemanager.link"]._toggle_access_via_record(
            self.int_filemanager_access_via_record
        )
