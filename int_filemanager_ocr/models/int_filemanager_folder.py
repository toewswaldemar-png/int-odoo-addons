from odoo import api, fields, models


class IntFilemanagerFolder(models.Model):
    _inherit = "int.filemanager.folder"

    ocr_images = fields.Selection(
        [
            ("inherit", "Like the parent folder"),
            ("on", "On"),
            ("off", "Off"),
        ],
        string="Text recognition in images",
        # Administrators only: a field that is only left out of the view could be written through
        # RPC by every user of the filemanager, and would start the recognition of images.
        groups="int_filemanager.int_filemanager_group_admin",
        required=True,
        default="inherit",
        help="Whether the text in the images of this folder (JPEG, PNG, TIFF ...) is recognized, "
        "so that the search finds it. A top folder that says 'like the parent folder' is off. "
        "Nothing is recognized unless the text recognition is switched on in the settings.",
    )
    # What ``ocr_images`` comes to for this folder after the parent is looked at. Administrators
    # only, like ``ocr_images``: otherwise a user could switch the recognition on through RPC.
    ocr_images_active = fields.Boolean(
        string="Images are recognized here",
        compute="_compute_ocr_images_active",
        store=True,
        recursive=True,
        groups="int_filemanager.int_filemanager_group_admin",
    )

    @api.depends("ocr_images", "parent_id.ocr_images_active")
    def _compute_ocr_images_active(self):
        for folder in self:
            if folder.ocr_images == "inherit":
                # A top folder has no parent to ask: off.
                folder.ocr_images_active = folder.parent_id.ocr_images_active
            else:
                folder.ocr_images_active = folder.ocr_images == "on"
