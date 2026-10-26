import shutil

from odoo import api, fields, models, tools

from ..tools.programs import LIMIT_PROGRAMS, missing_programs, probe
from .int_filemanager_cron import PREVIEW_ENABLED_DEFAULT, SETTINGS
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

    # Status of the previews of the office files (nothing is saved).
    int_filemanager_preview_state = fields.Char(
        string="Preview", compute="_compute_int_filemanager_preview_status"
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
        """What the program says to ``--version``. It starts a process, and the screen asks again
        at every change of a field: the answer is kept until the cache of the registry is cleared
        (a restart, an update of a module)."""
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
        for settings in self:
            settings.int_filemanager_preview_state = state
            settings.int_filemanager_preview_done = counts["done"]
            settings.int_filemanager_preview_waiting = counts[False]
            settings.int_filemanager_preview_failed = counts["failed"]
