from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    int_ui_showcase_flag = fields.Boolean(
        "Showcase Flag", config_parameter="int_ui_showcase.flag"
    )
    int_ui_showcase_text = fields.Char(
        "Showcase Text", config_parameter="int_ui_showcase.text"
    )
    int_ui_showcase_integer = fields.Integer(
        "Showcase Number", config_parameter="int_ui_showcase.integer", default=5
    )
    int_ui_showcase_mode = fields.Selection(
        [("light", "Light"), ("normal", "Normal"), ("strict", "Strict")],
        "Showcase Mode",
        config_parameter="int_ui_showcase.mode",
        default="normal",
    )
    int_ui_showcase_url = fields.Char(
        "Showcase URL",
        config_parameter="int_ui_showcase.url",
        default="https://www.odoo.com",
    )
