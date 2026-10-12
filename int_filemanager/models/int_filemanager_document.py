import mimetypes
import os

from odoo import api, fields, models


class IntFilemanagerDocument(models.Model):
    """A file: an ordinary record with a binary field.

    ``attachment=True`` makes Odoo keep the content in ``ir.attachment`` and its filestore;
    nothing here stores or reads bytes itself.
    """

    _name = "int.filemanager.document"
    _description = "Filemanager document"
    _inherit = ["mail.thread"]
    _order = "name"

    name = fields.Char(required=True)
    folder_id = fields.Many2one(
        "int.filemanager.folder", required=True, index=True, ondelete="restrict"
    )
    data = fields.Binary(string="File", attachment=True, required=True)
    mimetype = fields.Char(compute="_compute_mimetype", store=True)
    # Float, not Integer: an int4 column overflows above 2 GiB.
    size = fields.Float(compute="_compute_size", store=True)
    active = fields.Boolean(default=True)
    tag_ids = fields.Many2many(
        "int.filemanager.tag",
        "int_filemanager_document_tag_rel",
        "document_id",
        "tag_id",
        string="Tags",
    )
    company_id = fields.Many2one(
        related="folder_id.company_id", store=True, index=True
    )

    _name_per_folder = models.UniqueIndex(
        '(folder_id, lower(name COLLATE "und-x-icu")) WHERE active',
        "A document with this name already exists in this folder.",
    )

    @api.depends("name")
    def _compute_mimetype(self):
        for document in self:
            document.mimetype = (
                mimetypes.guess_type(document.name or "")[0] or "application/octet-stream"
            )

    @api.depends("data")
    def _compute_size(self):
        # The size is the attachment's own; the content is not read.
        sizes = dict(
            self.env["ir.attachment"]
            .sudo()
            ._read_group(
                [
                    ("res_model", "=", self._name),
                    ("res_field", "=", "data"),
                    ("res_id", "in", self.ids),
                ],
                ["res_id"],
                ["file_size:sum"],
            )
        )
        for document in self:
            document.size = sizes.get(document.id, 0)

    def copy_data(self, default=None):
        """A copy lands in the same folder, where the name is taken: give it a free one.

        Move the copy afterwards by editing its folder (list: select, click the folder).
        """
        vals_list = super().copy_data(default)
        if default and "name" in default:
            return vals_list
        for document, vals in zip(self, vals_list, strict=True):
            stem, extension = os.path.splitext(document.name)
            taken = set(
                self.with_context(active_test=False)
                .search([("folder_id", "=", document.folder_id.id)])
                .mapped("name")
            )
            name = self.env._("%(stem)s (copy)%(extension)s", stem=stem, extension=extension)
            number = 2
            while name.lower() in {other.lower() for other in taken}:
                name = self.env._(
                    "%(stem)s (copy %(number)s)%(extension)s",
                    stem=stem,
                    number=number,
                    extension=extension,
                )
                number += 1
            vals["name"] = name
        return vals_list
