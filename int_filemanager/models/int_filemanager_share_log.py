from odoo import fields, models


class IntFilemanagerShareLog(models.Model):
    """Share log events about a node.

    Path and file name are kept as text, so the log outlives the node.
    """

    _inherit = "int_filemanager.share_log"

    node_id = fields.Many2one("int_filemanager.node", ondelete="set null", index=True)
