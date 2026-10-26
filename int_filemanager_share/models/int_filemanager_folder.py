from odoo import models


class IntFilemanagerFolder(models.Model):
    _name = "int.filemanager.folder"
    _inherit = ["int.filemanager.folder", "int.filemanager.shareable"]
    _share_target = "folder_id"
