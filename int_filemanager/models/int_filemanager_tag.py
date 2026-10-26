from odoo import fields, models


class IntFilemanagerTag(models.Model):
    _name = "int.filemanager.tag"
    _description = "Filemanager tag"
    _order = "name"

    name = fields.Char(required=True)
    color = fields.Integer(default=0)

    # Case aside, like the names of folders and documents: "Invoice" and "invoice" are one tag.
    _name_uniq = models.UniqueIndex(
        '(lower(name COLLATE "und-x-icu"))', "A tag with this name already exists."
    )
