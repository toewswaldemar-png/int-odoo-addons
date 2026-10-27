from odoo import fields, models


class IntFilemanagerFolder(models.Model):
    _inherit = "int.filemanager.folder"

    model_folder_ids = fields.One2many(
        "int.filemanager.model.folder",
        "folder_id",
        string="Upload folder for",
        # Administrators only, like the settings themselves: they are the ones with a right on
        # the model, and a field that is only left out of the view could be written through
        # RPC by every user of the filemanager.
        groups="int_filemanager.int_filemanager_group_admin",
        help="The kinds of record whose uploaded files go to this folder, for example "
        "contacts. Whoever may change such a record can upload files there, without access to "
        "the folder.",
    )
