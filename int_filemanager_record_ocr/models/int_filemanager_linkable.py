from odoo import fields, models
from odoo.fields import Domain


class IntFilemanagerLinkable(models.AbstractModel):
    _inherit = "int.filemanager.linkable"

    document_search = fields.Char(
        string="Document contains",
        compute="_compute_document_search",
        search="_search_document_search",
    )

    def _compute_document_search(self):
        self.document_search = False

    def _search_document_search(self, operator, value):
        """Search the records with a document whose file contains these words (``content_search``).

        Only the documents that the user sees take part: ``any`` applies the rules of the link
        and of the document.
        """
        return Domain(
            "link_ids", "any", [("document_id", "any", [("content_search", operator, value)])]
        )
