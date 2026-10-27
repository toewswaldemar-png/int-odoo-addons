from odoo import api, fields, models
from odoo.exceptions import ValidationError

from .int_filemanager_share import (
    SHARE_BRAKE,
    SHARE_CREATORS,
    SHARE_DEFAULT_EXTENSIONS,
    SHARE_DEFAULT_FILES,
    SHARE_DEFAULT_FILE_MB,
    SHARE_DEFAULT_TOTAL_MB,
    SHARE_INVALID_TOKENS,
    SHARE_MAX_FILES,
    SHARE_MAX_FILE_MB,
    SHARE_MAX_TOTAL_MB,
    SHARE_PASSWORD_LENGTH,
    SHARE_PASSWORD_TRIES_IP,
    SHARE_PASSWORD_TRIES_SHARE,
    SHARE_REQUESTS_PER_MINUTE,
    SHARE_UNLOCK_HOURS,
    SHARE_UPLOADS_PER_MINUTE,
)

# The settings of the shares that are numbers (at least 1, see the constraint).
SHARE_NUMBERS = (
    "int_filemanager_share_default_file_mb",
    "int_filemanager_share_default_total_mb",
    "int_filemanager_share_default_files",
    "int_filemanager_share_max_file_mb",
    "int_filemanager_share_max_total_mb",
    "int_filemanager_share_max_files",
    "int_filemanager_share_password_length",
    "int_filemanager_share_unlock_hours",
    "int_filemanager_share_invalid_tokens",
    "int_filemanager_share_requests_per_minute",
    "int_filemanager_share_uploads_per_minute",
    "int_filemanager_share_password_tries_ip",
    "int_filemanager_share_password_tries_share",
)


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # The shares (links for guests). The numbers are at least 1: Odoo does not save a 0 of a
    # number field, and the field would show its default again.
    int_filemanager_share_creators = fields.Selection(
        [
            ("user", "All filemanager users"),
            ("admin", "Filemanager administrators only"),
        ],
        string="Who makes shares",
        config_parameter="int_filemanager.share_creators",
        default=SHARE_CREATORS,
        help="Whoever may make a share can give the folders and files that they see.",
    )
    int_filemanager_share_default_file_mb = fields.Integer(
        string="Largest file (MB)",
        config_parameter="int_filemanager.share_default_file_mb",
        default=SHARE_DEFAULT_FILE_MB,
    )
    int_filemanager_share_default_total_mb = fields.Integer(
        string="All files together (MB)",
        config_parameter="int_filemanager.share_default_total_mb",
        default=SHARE_DEFAULT_TOTAL_MB,
    )
    int_filemanager_share_default_files = fields.Integer(
        string="Number of files",
        config_parameter="int_filemanager.share_default_files",
        default=SHARE_DEFAULT_FILES,
    )
    int_filemanager_share_default_extensions = fields.Char(
        string="Allowed endings",
        config_parameter="int_filemanager.share_default_extensions",
        default=SHARE_DEFAULT_EXTENSIONS,
        help="Separated by commas: pdf, jpg. Empty: every ending, except those that can run as "
        "a program or a page.",
    )
    int_filemanager_share_max_file_mb = fields.Integer(
        string="Largest file (MB)",
        config_parameter="int_filemanager.share_max_file_mb",
        default=SHARE_MAX_FILE_MB,
    )
    int_filemanager_share_max_total_mb = fields.Integer(
        string="All files together (MB)",
        config_parameter="int_filemanager.share_max_total_mb",
        default=SHARE_MAX_TOTAL_MB,
    )
    int_filemanager_share_max_files = fields.Integer(
        string="Number of files",
        config_parameter="int_filemanager.share_max_files",
        default=SHARE_MAX_FILES,
    )
    int_filemanager_share_password_length = fields.Integer(
        string="Shortest password",
        config_parameter="int_filemanager.share_password_length",
        default=SHARE_PASSWORD_LENGTH,
    )
    int_filemanager_share_unlock_hours = fields.Integer(
        string="Hours the password is kept",
        config_parameter="int_filemanager.share_unlock_hours",
        default=SHARE_UNLOCK_HOURS,
        help="A guest who typed the password of a share does not type it again for this long, "
        "in the same browser tab.",
    )
    int_filemanager_share_brake = fields.Selection(
        [("1", "On"), ("0", "Off")],
        string="Brake on requests",
        config_parameter="int_filemanager.share_brake",
        default=SHARE_BRAKE,
        help="Limits how many requests one address may send: made-up addresses of shares, and "
        "the requests to a share. Not the brake on wrong passwords: that one is always on.",
    )
    int_filemanager_share_invalid_tokens = fields.Integer(
        string="Wrong addresses in 10 minutes",
        config_parameter="int_filemanager.share_invalid_tokens",
        default=SHARE_INVALID_TOKENS,
        help="After this many addresses of shares that do not exist, an address is turned away "
        "for ten minutes (whoever has a right link is not).",
    )
    int_filemanager_share_requests_per_minute = fields.Integer(
        string="Requests to a share in a minute",
        config_parameter="int_filemanager.share_requests_per_minute",
        default=SHARE_REQUESTS_PER_MINUTE,
    )
    int_filemanager_share_uploads_per_minute = fields.Integer(
        string="Uploads to a share in a minute",
        config_parameter="int_filemanager.share_uploads_per_minute",
        default=SHARE_UPLOADS_PER_MINUTE,
        help="Files that one address may send to a share in a minute. The limits of the share "
        "itself (size, number, total) do not depend on it.",
    )
    int_filemanager_share_password_tries_ip = fields.Integer(
        string="Wrong passwords of an address in 10 minutes",
        config_parameter="int_filemanager.share_password_tries_ip",
        default=SHARE_PASSWORD_TRIES_IP,
    )
    int_filemanager_share_password_tries_share = fields.Integer(
        string="Wrong passwords of a share in 10 minutes",
        config_parameter="int_filemanager.share_password_tries_share",
        default=SHARE_PASSWORD_TRIES_SHARE,
        help="From all addresses together.",
    )

    @api.constrains(*SHARE_NUMBERS)
    def _check_int_filemanager_share_numbers(self):
        """Check that every number is at least 1 and that a new share does not start above what a share may be.
        """
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
