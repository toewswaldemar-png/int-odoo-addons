from odoo import api, fields, models

from .res_users_settings import OPEN_MODES


class ResUsers(models.Model):
    _inherit = "res.users"

    # The choice is kept in `res.users.settings` (the browser reads it there); the field here
    # puts it in the preferences of the user (the way the calendar does with its privacy).
    int_filemanager_open_mode = fields.Selection(
        [("default", "Default"), *OPEN_MODES],
        string="Open documents with",
        compute="_compute_int_filemanager_open_mode",
        inverse="_inverse_int_filemanager_open_mode",
    )

    @property
    def SELF_READABLE_FIELDS(self):
        return super().SELF_READABLE_FIELDS + ["int_filemanager_open_mode"]

    @property
    def SELF_WRITEABLE_FIELDS(self):
        return super().SELF_WRITEABLE_FIELDS + ["int_filemanager_open_mode"]

    @api.depends("res_users_settings_id.int_filemanager_open_mode")
    def _compute_int_filemanager_open_mode(self):
        for user in self:
            # sudo: the settings of a user are no one else's business, but the user reads theirs
            user.int_filemanager_open_mode = (
                user.sudo().res_users_settings_id.int_filemanager_open_mode or "default"
            )

    def _inverse_int_filemanager_open_mode(self):
        for user in self.filtered(lambda user: user._is_internal()):
            settings = self.env["res.users.settings"].sudo()._find_or_create_for_user(user)
            settings.int_filemanager_open_mode = user.int_filemanager_open_mode
