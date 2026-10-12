from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    int_filemanager_import_root = fields.Char(
        string="Root folder",
        config_parameter="int_filemanager.import_root",
        help="Only what lies below this folder of the server can be read into the filemanager. "
        "An absolute path, e.g. /mnt/hm-daten.",
    )
