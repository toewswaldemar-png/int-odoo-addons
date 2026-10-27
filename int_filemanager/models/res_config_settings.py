import importlib.util
import shutil

from odoo import api, fields, models, tools

from ..tools.programs import LIMIT_PROGRAMS, missing_programs, probe
from .int_filemanager_cron import PREVIEW_ENABLED_DEFAULT, SETTINGS, TRASH_ENABLED_DEFAULT
from .res_users_settings import OPEN_MODE_PARAMETER, OPEN_MODES


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # A selection: Odoo does not save a False of a checkbox that is on by default.
    int_filemanager_preview_enabled = fields.Selection(
        [("1", "Show them as PDF"), ("0", "Offer them for download only")],
        string="Word, Excel and PowerPoint files",
        config_parameter="int_filemanager.preview_enabled",
        default="1" if PREVIEW_ENABLED_DEFAULT else "0",
        help="LibreOffice makes a PDF of each file in the background, and the preview shows "
        "it. The files themselves are not changed; the download is the original.",
    )
    int_filemanager_preview_seconds = fields.Integer(
        string="Time per file (seconds)",
        config_parameter="int_filemanager.preview_seconds",
        default=SETTINGS["preview_seconds"][0],
        help="A file that takes longer gets no preview. A run of the scheduled action is as long "
        "as the limit of Odoo for it (limit_time_real_cron); a file never gets more than that.",
    )
    int_filemanager_preview_max_size_mib = fields.Integer(
        string="Largest file (MiB)",
        config_parameter="int_filemanager.preview_max_size_mib",
        default=SETTINGS["preview_max_size_mib"][0],
        help="A bigger file gets no preview.",
    )

    int_filemanager_default_open_mode = fields.Selection(
        OPEN_MODES,
        string="Open documents with",
        config_parameter=OPEN_MODE_PARAMETER,
        default=OPEN_MODES[0][0],
        help="What opens a document in the list and the kanban. Every user can choose otherwise "
        "in their preferences.",
    )

    # The numbers are at least 1 (see ``SETTINGS``): Odoo does not save a 0 of a number field, and
    # the field would show its default again.
    int_filemanager_upload_max_gb = fields.Integer(
        string="Largest upload (GB)",
        config_parameter="int_filemanager.upload_max_gb",
        default=SETTINGS["upload_max_gb"][0],
        help="Only users of the filemanager may send this much; every other user keeps the limit of "
        "Odoo. The server holds the file twice while it arrives (see the notes for the operator).",
    )
    int_filemanager_upload_max_age_hours = fields.Integer(
        string="Hours a failed upload is kept",
        config_parameter="int_filemanager.upload_max_age_hours",
        default=SETTINGS["upload_max_age_hours"][0],
        help="An upload that never ended leaves a temporary file. The cleaning of the database "
        "deletes it after this many hours.",
    )
    int_filemanager_zip_max_gb = fields.Integer(
        string="Largest download as ZIP (GB)",
        config_parameter="int_filemanager.zip_max_gb",
        default=SETTINGS["zip_max_gb"][0],
        help="More files than this are refused: download them in parts. A slow line keeps a worker "
        "of the server busy for the whole download.",
    )

    # A selection, like the preview: Odoo does not save a False of a checkbox that is on by default.
    int_filemanager_trash_enabled = fields.Selection(
        [("1", "Delete them after some days"), ("0", "Keep them until someone deletes them")],
        string="Archived documents",
        config_parameter="int_filemanager.trash_enabled",
        default="1" if TRASH_ENABLED_DEFAULT else "0",
        help="Archived documents are the trash: everyone who may change them can restore them. "
        "Deleting is final, the files go with the documents.",
    )
    int_filemanager_trash_days = fields.Integer(
        string="Days in the trash",
        config_parameter="int_filemanager.trash_days",
        default=SETTINGS["trash_days"][0],
        help="After this many days the cleaning of the database deletes an archived document.",
    )

    # Status of the previews of the office files (nothing is saved).
    int_filemanager_preview_state = fields.Char(
        string="Preview", compute="_compute_int_filemanager_preview_status"
    )
    int_filemanager_thumbnail_state = fields.Char(
        string="Pictures of PDFs", compute="_compute_int_filemanager_preview_status"
    )
    int_filemanager_preview_done = fields.Integer(
        string="Files with preview", compute="_compute_int_filemanager_preview_status"
    )
    int_filemanager_preview_waiting = fields.Integer(
        string="Files waiting", compute="_compute_int_filemanager_preview_status"
    )
    int_filemanager_preview_failed = fields.Integer(
        string="Files failed", compute="_compute_int_filemanager_preview_status"
    )

    @api.model
    @tools.ormcache("program")
    def _int_filemanager_program_version(self, program):
        """Return what the program says to ``--version``.

        It starts a process, and the screen asks again at every change of a field, so the answer
        is cached until the cache of the registry is cleared (a restart, an update of a module).
        """
        return probe([program, "--version"]).strip()

    @api.depends_context("uid")
    def _compute_int_filemanager_preview_status(self):
        counts = self.env["int.filemanager.document"]._preview_counts()
        program = shutil.which("soffice")
        missing = missing_programs(*LIMIT_PROGRAMS)
        if not program:
            state = self.env._("Stopped: LibreOffice is not installed on the server.")
        elif missing:
            state = self.env._(
                "Stopped: %(programs)s is missing on the server (GNU coreutils).", programs=", ".join(missing)
            )
        else:
            state = self.env._("Ready. %(version)s", version=self._int_filemanager_program_version(program))
        if importlib.util.find_spec("pypdfium2"):
            thumbnails = self.env._("Ready.")
        else:
            thumbnails = self.env._("Stopped: the Python package pypdfium2 is not installed on the server.")
        for settings in self:
            settings.int_filemanager_preview_state = state
            settings.int_filemanager_thumbnail_state = thumbnails
            settings.int_filemanager_preview_done = counts["done"]
            settings.int_filemanager_preview_waiting = counts[False]
            settings.int_filemanager_preview_failed = counts["failed"]
