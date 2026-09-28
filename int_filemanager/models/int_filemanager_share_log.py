from odoo import fields, models


class IntFilemanagerShareLog(models.Model):
    """v2 extension of the share log (filemanager_share_log.py, v1): events are about a
    node now. path/filename remain text snapshots, so a log outlives a deleted or
    renamed node (hence ondelete="set null", not cascade)."""

    _inherit = "int_filemanager.share_log"

    node_id = fields.Many2one("int_filemanager.node", ondelete="set null", index=True)
