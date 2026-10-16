from odoo import fields, models


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
