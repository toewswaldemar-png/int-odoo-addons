from odoo import fields, models


class IntFilemanagerDocument(models.Model):
    _inherit = "int.filemanager.document"

    # Path of the imported file on the disk of the server (below the root folder of the
    # settings). A second import skips what is there already.
    origin_path = fields.Char(groups="base.group_system", copy=False)

    # A hash index only finds an equal path, which is all that is needed (a btree index fails
    # above about 2.7 KB).
    _origin_path_index = models.Index("USING hash (origin_path)")
