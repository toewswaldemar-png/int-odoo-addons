from odoo import fields, models


class IntFilemanagerDocument(models.Model):
    _inherit = "int.filemanager.document"

    # Where on the disk of the server the file was read in from (below the root folder of the
    # settings), so that a second reading in skips what is there.
    origin_path = fields.Char(groups="base.group_system", copy=False)

    # A hash index only finds an equal path (a btree index fails above about 2.7 KB).
    _origin_path_index = models.Index("USING hash (origin_path)")
