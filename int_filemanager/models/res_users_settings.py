from odoo import api, fields, models

OPEN_MODE_PARAMETER = "int_filemanager.default_open_mode"
OPEN_MODES = [("single", "Single click"), ("double", "Double click")]


class ResUsersSettings(models.Model):
    _inherit = "res.users.settings"

    # The size of the cards of the kanban of documents. The core keeps what a user picks in the
    # views here (it reaches the browser in `user.settings`), so it holds on every device.
    int_filemanager_tile_size = fields.Selection(
        [("small", "Small"), ("medium", "Medium"), ("large", "Large")],
        string="Size of the document cards",
        default="medium",
        required=True,
    )
    # What opens a document in the list and the kanban: one click (like the core) or two, so that
    # a click alone only selects. "default" follows the setting of the filemanager (see
    # `int_filemanager_default_open_mode` of `res.config.settings`).
    int_filemanager_open_mode = fields.Selection(
        [("default", "Default"), *OPEN_MODES],
        string="Open documents with",
        default="default",
        required=True,
    )
    # What the browser needs: the choice of the user, or the default if there is none.
    int_filemanager_open_mode_resolved = fields.Selection(
        OPEN_MODES,
        string="Open documents with (resolved)",
        compute="_compute_int_filemanager_open_mode_resolved",
    )

    @api.depends("int_filemanager_open_mode")
    def _compute_int_filemanager_open_mode_resolved(self):
        default = self.env["ir.config_parameter"].sudo().get_param(
            OPEN_MODE_PARAMETER, OPEN_MODES[0][0]
        )
        for settings in self:
            mode = settings.int_filemanager_open_mode
            settings.int_filemanager_open_mode_resolved = default if mode == "default" else mode
